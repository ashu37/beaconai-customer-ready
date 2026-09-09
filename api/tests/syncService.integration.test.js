const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");

// Skips wholesale without TEST_DATABASE_URL. See tests/helpers/db.js.
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { runSync, getSyncStatus, getActiveInputSnapshot } = require("../src/services/syncService");

const SHOP = "integration-shop.myshopify.com";
const OTHER_SHOP = "other-shop.myshopify.com";

async function syncWith(payload, options = {}) {
  return runSync({
    shopDomain: options.shopDomain || SHOP,
    accessToken: "token",
    limit: options.limit,
    shopifyScope: options.shopifyScope || "read_orders,read_all_orders",
    fetchData: async () => payload,
  });
}

test.after(async () => {
  if (db.available) await db.closeDatabase();
});

suite("a complete sync publishes and becomes the active input", async () => {
  await db.resetDatabase();
  const result = await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(200) }));

  assert.equal(result.published, true);
  assert.equal(result.status, "complete");
  assert.equal(result.declaredCoverage.meetsRequired, true);

  const active = await getActiveInputSnapshot(SHOP);
  assert.equal(active.syncRunId, result.syncRunId);
  assert.equal(active.snapshot.rowCount, 4);

  const status = await getSyncStatus(SHOP);
  assert.equal(status.ready, true, "a complete sync makes analysis allowed");
  assert.deepEqual(status.reasons, []);
});

suite("a truncated fetch never reaches the clean tables", async () => {
  await db.resetDatabase();
  const result = await syncWith(
    db.shopifyPayload({ orders: db.ordersSpanning(200), truncated: true }),
    { limit: 4 }
  );

  assert.equal(result.published, false);
  assert.equal(result.status, "incomplete");
  assert.ok(result.validationFailures.some((f) => f.code === "resource_truncated"));

  const orders = await query(`SELECT count(*)::int AS n FROM clean.orders WHERE shop_domain = $1`, [SHOP]);
  assert.equal(orders.rows[0].n, 0, "nothing was written at all");

  const status = await getSyncStatus(SHOP);
  assert.equal(status.ready, false);
  assert.equal(status.active, null);
  assert.equal(status.reasons[0].code, "never_synced");
});

suite("insufficient history rolls back the publication whole", async () => {
  await db.resetDatabase();
  // 30 days of orders: fetched cleanly, but below the engine's 90-day floor.
  const result = await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(30) }));

  assert.equal(result.published, false);
  assert.equal(result.status, "incomplete");
  assert.equal(result.validationFailures[0].code, "coverage_below_required");

  // The rows were written inside the transaction and rolled back with it — the
  // point being that no other reader ever saw them.
  const orders = await query(`SELECT count(*)::int AS n FROM clean.orders WHERE shop_domain = $1`, [SHOP]);
  assert.equal(orders.rows[0].n, 0);
  assert.equal(await getActiveInputSnapshot(SHOP), null);
});

suite("a failed sync preserves the last complete snapshot", async () => {
  await db.resetDatabase();
  const good = await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(200) }));
  assert.equal(good.published, true);

  await assert.rejects(() =>
    runSync({
      shopDomain: SHOP, accessToken: "token", shopifyScope: "read_orders",
      fetchData: async () => { throw new Error("Shopify 503"); },
    })
  );

  const active = await getActiveInputSnapshot(SHOP);
  assert.equal(active.syncRunId, good.syncRunId, "the good input is still the active one");

  const status = await getSyncStatus(SHOP);
  assert.equal(status.ready, false, "a failed attempt blocks a NEW analysis");
  assert.equal(status.reasons[0].code, "last_sync_failed");
  assert.ok(status.active, "but the published input remains readable");
});

suite("an older sync cannot supersede a newer one", async () => {
  await db.resetDatabase();
  const payload = db.shopifyPayload({ orders: db.ordersSpanning(200) });
  const first = await syncWith(payload);

  // Stand in for a concurrent sync that started later and published first: the
  // active pointer now carries a start time ahead of any sync beginning now.
  // The one that starts after this must refuse to overwrite it.
  await query(
    `UPDATE clean.active_sync SET started_at = NOW() + interval '1 hour' WHERE shop_domain = $1`,
    [SHOP]
  );

  await assert.rejects(() => syncWith(payload), /newer sync/);

  const active = await query(`SELECT sync_run_id FROM clean.active_sync WHERE shop_domain = $1`, [SHOP]);
  assert.equal(active.rows[0].sync_run_id, first.syncRunId, "the newer input is untouched");

  const refused = await query(
    `SELECT status, failure_reason FROM clean.sync_runs WHERE shop_domain = $1 ORDER BY id DESC LIMIT 1`,
    [SHOP]
  );
  assert.equal(refused.rows[0].status, "failed");
  assert.equal(refused.rows[0].failure_reason, "superseded_by_newer_sync",
    "the refusal is recorded outside the rolled-back transaction");
});

suite("re-syncing the same store does not duplicate refunds", async () => {
  await db.resetDatabase();
  const orders = db.ordersSpanning(200);
  orders[0].refunds = [
    {
      id: 77001, created_at: new Date().toISOString(),
      transactions: [{ amount: "50.00" }],
      refund_line_items: [{ line_item_id: 9000, quantity: 1 }],
    },
  ];
  const payload = db.shopifyPayload({ orders });

  await syncWith(payload);
  await syncWith(payload);
  await syncWith(payload);

  const refunds = await query(`SELECT count(*)::int AS n FROM clean.refunds WHERE shop_domain = $1`, [SHOP]);
  assert.equal(refunds.rows[0].n, 1, "three syncs, one refund");
});

suite("one shop's sync does not publish for another", async () => {
  await db.resetDatabase();
  await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(200) }));

  const other = await getSyncStatus(OTHER_SHOP);
  assert.equal(other.active, null);
  assert.equal(other.ready, false);
  assert.equal(other.legacyDataPresent, false);
});

suite("clean rows with no sync run are reported as legacy, not verified", async () => {
  await db.resetDatabase();
  // Exactly the state every store is in before this ticket ships.
  await query(
    `INSERT INTO clean.orders (id, shop_domain, name, created_at, total_price)
     VALUES ('legacy-1', $1, '#1', NOW(), 10)`,
    [SHOP]
  );

  const status = await getSyncStatus(SHOP);
  assert.equal(status.legacyDataPresent, true);
  assert.equal(status.ready, false, "legacy input cannot back a new analysis");
  assert.equal(status.reasons[0].code, "legacy_unverified_input");
});

suite("a briefing built from an earlier sync is marked stale, not deleted", async () => {
  await db.resetDatabase();
  const first = await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(200) }));
  await query(
    `INSERT INTO clean.engine_run_snapshots
       (run_id, shop_domain, store_id, engine_run, sync_run_id, input_provenance)
     VALUES ('run-1', $1, 'store', '{}'::jsonb, $2, 'verified')`,
    [SHOP, first.syncRunId]
  );

  let status = await getSyncStatus(SHOP);
  assert.equal(status.analysis.provenance, "verified");
  assert.equal(status.analysis.stale, false);

  const second = await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(200) }));
  assert.notEqual(second.syncRunId, first.syncRunId);

  status = await getSyncStatus(SHOP);
  assert.equal(status.analysis.runId, "run-1", "the old briefing is still there");
  assert.equal(status.analysis.provenance, "verified_stale");
  assert.equal(status.analysis.stale, true);
});

suite("a run with no sync_run_id reads as legacy provenance", async () => {
  await db.resetDatabase();
  await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(200) }));
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run)
     VALUES ('run-legacy', $1, 'store', '{}'::jsonb)`,
    [SHOP]
  );

  const status = await getSyncStatus(SHOP);
  assert.equal(status.analysis.provenance, "legacy_unverified");
  assert.equal(status.analysis.stale, true);
});
