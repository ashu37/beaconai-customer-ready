const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");

// Skips wholesale without TEST_DATABASE_URL. See tests/helpers/db.js.
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const {
  assertInputVerifiedForHandoff,
  getActiveInputSnapshot,
  getSyncStatus,
  runSync,
} = require("../src/services/syncService");

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

// ---------------------------------------------------------------------------
// Review findings — regressions
// ---------------------------------------------------------------------------

suite("a genuine mid-write failure leaves nothing behind", async () => {
  await db.resetDatabase();
  const good = await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(200) }));
  assert.equal(good.published, true);
  const goodOrders = await query(`SELECT count(*)::int AS n FROM clean.orders WHERE shop_domain = $1`, [SHOP]);
  assert.equal(goodOrders.rows[0].n, 4);

  // Not a thrown stub: order #3 carries a total_price Postgres cannot cast to
  // NUMERIC, so the INSERT itself errors partway through the order loop, after
  // the shop, products, customers and the first two orders are already written
  // in this transaction. This is the real failure shape the rollback exists for.
  const orders = db.ordersSpanning(200, 5);
  orders[2].total_price = "not-a-number";

  await assert.rejects(
    () => syncWith(db.shopifyPayload({ orders })),
    /invalid input syntax for type numeric/
  );

  // Every table the import touches is back to the last published state — the
  // partially-written orders, and the raw event rows written before them, are
  // both gone.
  const after = await query(`SELECT count(*)::int AS n FROM clean.orders WHERE shop_domain = $1`, [SHOP]);
  assert.equal(after.rows[0].n, 4, "still the four orders the good sync published");
  const ids = await query(`SELECT id FROM clean.orders WHERE shop_domain = $1 ORDER BY id`, [SHOP]);
  assert.deepEqual(ids.rows.map((r) => r.id), ["5000", "5001", "5002", "5003"]);

  const rawEvents = await query(`SELECT count(*)::int AS n FROM raw.shopify_events WHERE shop_domain = $1`, [SHOP]);
  assert.equal(rawEvents.rows[0].n, 4,
    "one raw row per resource (shop, orders, products, customers) from the good sync only — not eight");

  // The published input is untouched, and the failure is recorded with a
  // readable reason rather than a bare SQLSTATE.
  const active = await getActiveInputSnapshot(SHOP);
  assert.equal(active.syncRunId, good.syncRunId);
  const failed = await query(
    `SELECT status, failure_reason FROM clean.sync_runs WHERE shop_domain = $1 ORDER BY id DESC LIMIT 1`,
    [SHOP]
  );
  assert.equal(failed.rows[0].status, "failed");
  assert.match(failed.rows[0].failure_reason, /invalid input syntax for type numeric/);

  const status = await getSyncStatus(SHOP);
  assert.equal(status.ready, false, "a failed attempt blocks a new analysis");
  assert.ok(status.active, "while the last good input stays readable");
});

suite("residue from an earlier sync cannot vouch for a short one", async () => {
  await db.resetDatabase();
  // Regression: a 200-day sync publishes, so clean.orders now spans 200 days.
  // A later sync that can only reach 30 days back must be refused — judging it
  // against the accumulated tables would pass it forever on the strength of
  // rows nothing has re-verified.
  const first = await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(200) }));
  assert.equal(first.published, true);

  // A DIFFERENT set of orders, so the 200-day rows stay behind rather than
  // being upserted over — the residue this test is actually about.
  const short = await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(30, 4, 6000) }));

  const published = await query(
    `SELECT count(*)::int AS n FROM clean.orders WHERE shop_domain = $1`, [SHOP]
  );
  assert.equal(published.rows[0].n, 4, "the short sync published nothing, so only the old rows remain");

  assert.equal(short.published, false, "the accumulated tables must not launder a short fetch");
  assert.equal(short.status, "incomplete");
  assert.equal(short.validationFailures[0].code, "coverage_below_required");
  assert.equal(short.validationFailures[0].daysCovered, 30);

  const active = await getActiveInputSnapshot(SHOP);
  assert.equal(active.syncRunId, first.syncRunId, "the good input is still active");
});

suite("declared coverage separates the fetch, the published input and the rest", async () => {
  await db.resetDatabase();
  await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(300) }));
  // A second, narrower-but-still-valid fetch under its own order ids. The
  // 300-day rows stay in the clean tables and must NOT be counted as part of
  // what this sync verified.
  const narrow = await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(120, 4, 6000) }));
  assert.equal(narrow.published, true);

  const coverage = narrow.declaredCoverage;
  assert.equal(coverage.fetched.daysCovered, 120, "what this sync reached");
  assert.equal(coverage.fetched.datedRows, 4);

  // Published is now the same generation as the fetch, by construction. The two
  // are still reported separately: if they ever disagree, the read-back lost or
  // gained rows and that is worth seeing rather than averaging away.
  assert.equal(coverage.published.datedRows, 4, "only this fetch's rows are published");
  assert.equal(coverage.policy, "pilot_min_coverage_days");
  assert.equal(coverage.meetsRequired, true);
  assert.equal(coverage.meetsPreferred, false, "120 days is under the 180-day preference");

  // The older sync's rows are named as history, not absorbed into the verified
  // input and not silently dropped either.
  assert.equal(coverage.residual.orders, 4);
  assert.ok(coverage.residual.earliestOrderAt, "and their range is recorded");

  const active = await getActiveInputSnapshot(SHOP);
  assert.equal(active.snapshot.orderCount, 4);
  assert.ok(
    active.snapshot.orderRows.every((row) => row.Name.startsWith("#6")),
    "the published input holds only the newest fetch's orders"
  );
});

suite("handoff is refused for input nothing vouches for", async () => {
  await db.resetDatabase();
  const good = await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(200) }));
  const insertRun = (runId, syncRunId, provenance) => query(
    `INSERT INTO clean.engine_run_snapshots
       (run_id, shop_domain, store_id, engine_run, sync_run_id, input_provenance)
     VALUES ($1, $2, 'store', '{}'::jsonb, $3, $4)`,
    [runId, SHOP, syncRunId, provenance]
  );

  await insertRun("run-verified", good.syncRunId, "verified");
  await insertRun("run-fixture", null, "fixture");
  await insertRun("run-legacy", null, null);

  const verified = await assertInputVerifiedForHandoff("run-verified");
  assert.equal(verified.provenance, "verified");

  // Demo data must never reach a real customer.
  await assert.rejects(() => assertInputVerifiedForHandoff("run-fixture"), (error) => {
    assert.equal(error.name, "UnverifiedInputError");
    assert.equal(error.provenance, "fixture");
    assert.match(error.message, /sample data/);
    return true;
  });

  // Every run predating verified sync — including anything the partial-sync
  // incident produced — is legacy_unverified and stops here.
  await assert.rejects(() => assertInputVerifiedForHandoff("run-legacy"), (error) => {
    assert.equal(error.provenance, "legacy_unverified");
    return true;
  });

  await assert.rejects(() => assertInputVerifiedForHandoff("run-that-does-not-exist"), (error) => {
    assert.equal(error.provenance, "unknown_run");
    return true;
  });

  await assert.rejects(() => assertInputVerifiedForHandoff(null), (error) => {
    assert.equal(error.provenance, "unknown_run");
    return true;
  });
});

suite("a stale but verified run may still be sent", async () => {
  await db.resetDatabase();
  const first = await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(200) }));
  await query(
    `INSERT INTO clean.engine_run_snapshots
       (run_id, shop_domain, store_id, engine_run, sync_run_id, input_provenance)
     VALUES ('run-stale', $1, 'store', '{}'::jsonb, $2, 'verified')`,
    [SHOP, first.syncRunId]
  );
  await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(200) }));

  // It was verified when it ran, and a merchant may legitimately send from last
  // month's briefing. Blocked would be overreach; unlabelled would be dishonest.
  const run = await assertInputVerifiedForHandoff("run-stale");
  assert.equal(run.provenance, "verified_stale");
});

suite("sync status returns everything the persistent banner renders", async () => {
  await db.resetDatabase();
  const published = await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(120) }));
  await query(
    `INSERT INTO clean.engine_run_snapshots
       (run_id, shop_domain, store_id, engine_run, sync_run_id, input_provenance)
     VALUES ('run-ui', $1, 'store', '{}'::jsonb, $2, 'verified')`,
    [SHOP, published.syncRunId]
  );

  const status = await getSyncStatus(SHOP);
  // The banner reads exactly these paths; a rename here silently blanks it.
  assert.equal(typeof status.ready, "boolean");
  assert.ok(Array.isArray(status.reasons));
  assert.equal(status.analysis.provenance, "verified");
  assert.equal(status.analysis.stale, false);
  assert.equal(status.active.coverage.known, true);
  assert.equal(status.active.coverage.daysCovered, 120);
  assert.equal(status.active.coverage.meetsRequired, true);
  assert.equal(status.active.coverage.meetsPreferred, false);
  assert.equal(typeof status.active.coverage.residual.orders, "number");
  assert.ok(Array.isArray(status.latest.validationFailures));
});

suite("the published input is the fetched generation, not the union", async () => {
  await db.resetDatabase();
  const first = await syncWith(db.shopifyPayload({ orders: db.ordersSpanning(200) }));
  assert.equal(first.published, true);
  assert.equal(first.counts.orders, 4);

  // Shopify stops returning order 5001 — deleted, or no longer visible. It sits
  // in the MIDDLE of the fetched date range, so no range check can see that it
  // is gone: this is the case a date-based residual counter reported as 0.
  const orders = db.ordersSpanning(200).filter((order) => order.id !== 5001);
  assert.equal(orders.length, 3);
  const second = await syncWith(db.shopifyPayload({ orders }));
  assert.equal(second.published, true);

  // The row is still in the clean tables — upserts never prune.
  const stillThere = await query(
    `SELECT count(*)::int AS n FROM clean.orders WHERE shop_domain = $1 AND id = '5001'`, [SHOP]
  );
  assert.equal(stillThere.rows[0].n, 1);

  // But it is NOT in the published input, and it is counted by membership.
  assert.equal(second.counts.orders, 3, "the snapshot holds only what this fetch returned");
  assert.equal(second.declaredCoverage.residual.orders, 1);
  assert.equal(second.declaredCoverage.residual.lineItems, 1);

  const active = await getActiveInputSnapshot(SHOP);
  assert.equal(active.snapshot.orderCount, 3);
  const names = active.snapshot.orderRows.map((row) => row.Name);
  assert.ok(!names.includes("#5001"), "the record this sync never saw is not in the verified input");
  assert.deepEqual(names.sort(), ["#5000", "#5002", "#5003"]);
});

suite("a line item removed from an order leaves the published input", async () => {
  await db.resetDatabase();
  const orders = db.ordersSpanning(200, 2);
  orders[0].line_items = [
    { id: 70001, title: "Serum", quantity: 1, price: "30.00", total_discount: "0" },
    { id: 70002, title: "Cleanser", quantity: 1, price: "20.00", total_discount: "0" },
  ];
  const first = await syncWith(db.shopifyPayload({ orders }));
  assert.equal(first.counts.orderRows, 3, "two line items on order one, one on order two");

  // The merchant edits the order down to a single line. The dropped line item
  // is inside every date range that matters and belongs to an order that IS in
  // the fetch — invisible to anything but a membership check.
  const edited = db.ordersSpanning(200, 2);
  edited[0].line_items = [{ id: 70001, title: "Serum", quantity: 1, price: "30.00", total_discount: "0" }];
  const second = await syncWith(db.shopifyPayload({ orders: edited }));

  assert.equal(second.declaredCoverage.residual.orders, 0, "no order is missing");
  assert.equal(second.declaredCoverage.residual.lineItems, 1, "but a line item is");

  const active = await getActiveInputSnapshot(SHOP);
  const titles = active.snapshot.orderRows.map((row) => row["Lineitem name"]);
  assert.ok(!titles.includes("Cleanser"), "the removed line is not billed to the verified input");
});

suite("a clean sync reports no residual at all", async () => {
  await db.resetDatabase();
  const payload = db.shopifyPayload({ orders: db.ordersSpanning(200) });
  await syncWith(payload);
  const again = await syncWith(payload);

  assert.equal(again.declaredCoverage.residual.orders, 0);
  assert.equal(again.declaredCoverage.residual.lineItems, 0);
  assert.equal(again.declaredCoverage.residual.earliestOrderAt, null);
  // Published coverage is the fetch's own coverage now that they are the same
  // generation; a divergence here would mean the read-back lost or gained rows.
  assert.equal(again.declaredCoverage.published.datedRows, again.declaredCoverage.fetched.datedRows);
});
