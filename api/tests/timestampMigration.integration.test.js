const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { initSchema } = require("../src/schema");
const { getEngineInput, getWeeklySeries, upsertAllShopifyData } = require("../src/services/shopifyRepository");
const { buildEngineInputSnapshot } = require("../src/services/engineInputSnapshot");

const SHOP = "tz-shop.myshopify.com";

test.after(async () => {
  if (db.available) await db.closeDatabase();
});

async function setShopZone(zone) {
  await query(
    `INSERT INTO clean.shop (shop_domain, iana_timezone, currency)
     VALUES ($1, $2, 'USD')
     ON CONFLICT (shop_domain) DO UPDATE SET iana_timezone = EXCLUDED.iana_timezone`,
    [SHOP, zone]
  );
}

suite("an order's instant survives the database unchanged", async () => {
  await db.resetDatabase();
  await setShopZone("America/Los_Angeles");

  // The exact case from the forensic run: Postgres used to ignore this offset
  // entirely, storing the naked digits, and node-postgres read them back in the
  // reader's zone. The instant now round-trips.
  await upsertAllShopifyData(SHOP, {
    shop: { iana_timezone: "America/Los_Angeles", currency: "USD" },
    products: [], customers: [],
    orders: [{
      id: 4001, name: "#4001",
      created_at: "2025-11-15T16:15:35-08:00",
      processed_at: "2025-11-15T16:15:35-08:00",
      total_price: "50.00", line_items: [],
    }],
  });

  const { rows } = await query(`SELECT processed_at FROM clean.orders WHERE id = '4001'`);
  assert.equal(rows[0].processed_at.toISOString(), "2025-11-16T00:15:35.000Z",
    "16:15 Pacific in November is 00:15Z the next day");

  // And it reaches the engine as the store's own wall clock.
  const input = await getEngineInput(SHOP);
  const snapshot = buildEngineInputSnapshot(input);
  assert.equal(snapshot.orderRows[0]["Created at"], "2025-11-15T16:15:35");
});

suite("coverage spans are now exact", async () => {
  await db.resetDatabase();
  await setShopZone("UTC");
  // Previously impossible to assert exactly: a span measured over round-tripped
  // rows came back 299 for a 300-day range, because the shift differed across a
  // DST boundary. Deliberately spanning one here (Nov -> Mar).
  await upsertAllShopifyData(SHOP, {
    shop: { iana_timezone: "UTC", currency: "USD" }, products: [], customers: [],
    orders: [
      { id: 4101, name: "#4101", processed_at: "2025-11-01T12:00:00Z", created_at: "2025-11-01T12:00:00Z", total_price: "10.00", line_items: [] },
      { id: 4102, name: "#4102", processed_at: "2026-03-01T12:00:00Z", created_at: "2026-03-01T12:00:00Z", total_price: "10.00", line_items: [] },
    ],
  });

  const snapshot = buildEngineInputSnapshot(await getEngineInput(SHOP));
  assert.equal(snapshot.coverage.earliestOrderAt, "2025-11-01T12:00:00.000Z");
  assert.equal(snapshot.coverage.latestOrderAt, "2026-03-01T12:00:00.000Z");
  assert.equal(snapshot.coverage.daysCovered, 121, "Nov 1 to Mar 1 inclusive, across a DST change");
});

suite("a late-evening order stays in the store's own day and week", async () => {
  await db.resetDatabase();
  await setShopZone("America/Los_Angeles");

  // Sunday 2026-03-01 at 23:30 Pacific is 2026-03-02T07:30Z. Bucketed in UTC it
  // would land on Monday — a different day AND a different ISO week, which is
  // how a boundary order silently moved between windows.
  await upsertAllShopifyData(SHOP, {
    shop: { iana_timezone: "America/Los_Angeles", currency: "USD" }, products: [], customers: [],
    orders: [{
      id: 4201, name: "#4201",
      created_at: "2026-03-01T23:30:00-08:00", processed_at: "2026-03-01T23:30:00-08:00",
      customer: { id: "tz-cust-1" }, total_price: "25.00", line_items: [],
    }],
  });

  const snapshot = buildEngineInputSnapshot(await getEngineInput(SHOP));
  assert.equal(snapshot.orderRows[0]["Created at"], "2026-03-01T23:30:00",
    "March 1 in the store, not March 2 in UTC");

  const { rows } = await query(
    `SELECT date_trunc('week', created_at AT TIME ZONE 'America/Los_Angeles')::date::text AS local_week,
            date_trunc('week', created_at AT TIME ZONE 'UTC')::date::text AS utc_week
       FROM clean.orders WHERE id = '4201'`
  );
  assert.equal(rows[0].local_week, "2026-02-23", "the store's week");
  assert.notEqual(rows[0].utc_week, rows[0].local_week, "and it is genuinely a different week in UTC");
});

suite("weekly series buckets in the shop's zone, not the server's", async () => {
  await db.resetDatabase();
  await setShopZone("Pacific/Auckland");
  const now = new Date();
  await upsertAllShopifyData(SHOP, {
    shop: { iana_timezone: "Pacific/Auckland", currency: "USD" }, products: [], customers: [],
    orders: [{
      id: 4301, name: "#4301",
      created_at: now.toISOString(), processed_at: now.toISOString(),
      customer: { id: "tz-cust-2" }, total_price: "15.00", line_items: [],
    }],
  });

  const series = await getWeeklySeries(SHOP, 4);
  assert.equal(series.reduce((sum, w) => sum + w.orders, 0), 1);
});

suite("the migration recovers each row's zone from its own payload", async () => {
  await db.resetDatabase();
  await query(`DROP TABLE IF EXISTS clean.orders_date_backup`);

  // Rebuild the PRE-migration shape and write rows the way the old code did:
  // a Shopify string whose offset Postgres then discarded.
  await query(`ALTER TABLE clean.orders ALTER COLUMN processed_at TYPE TIMESTAMP USING processed_at AT TIME ZONE 'UTC'`);
  await query(`ALTER TABLE clean.orders ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC'`);
  await query(`ALTER TABLE clean.orders ALTER COLUMN cancelled_at TYPE TIMESTAMP USING cancelled_at AT TIME ZONE 'UTC'`);
  await query(`ALTER TABLE clean.orders DROP COLUMN IF EXISTS date_provenance`);

  // Recoverable: the payload retains the original offset.
  await query(
    `INSERT INTO clean.orders (id, shop_domain, created_at, processed_at, total_price, raw)
     VALUES ('m1', $1, '2025-11-15T16:15:35-08:00', '2025-11-15T16:15:35-08:00', 10,
             '{"created_at":"2025-11-15T16:15:35-08:00","processed_at":"2025-11-15T16:15:35-08:00"}'::jsonb)`,
    [SHOP]
  );
  // NOT recoverable: no date in the payload. Must be flagged, not guessed.
  await query(
    `INSERT INTO clean.orders (id, shop_domain, created_at, processed_at, total_price, raw)
     VALUES ('m2', $1, '2025-11-15T16:15:35', '2025-11-15T16:15:35', 10, '{"note":"no dates"}'::jsonb)`,
    [SHOP]
  );

  const before = await query(`SELECT id, processed_at::text AS t FROM clean.orders ORDER BY id`);
  assert.equal(before.rows[0].t, "2025-11-15 16:15:35", "the offset was discarded, as it always was");
  assert.equal(before.rows[1].t, "2025-11-15 16:15:35");

  await initSchema();

  const after = await query(`SELECT id, processed_at, date_provenance FROM clean.orders ORDER BY id`);

  // m1 is re-derived from its own payload: 16:15:35 Pacific, so 00:15:35Z next day.
  assert.equal(after.rows[0].date_provenance, "rederived_from_raw");
  assert.equal(after.rows[0].processed_at.toISOString(), "2025-11-16T00:15:35.000Z");

  // m2 keeps its digits, read as UTC, and is FLAGGED — the migration does not
  // invent a zone for a row whose zone it cannot establish.
  assert.equal(after.rows[1].date_provenance, "unverified_assumed_utc");
  assert.equal(after.rows[1].processed_at.toISOString(), "2025-11-15T16:15:35.000Z");

  // The originals are still readable.
  const backup = await query(`SELECT id, processed_at_naive::text AS t FROM clean.orders_date_backup ORDER BY id`);
  assert.deepEqual(backup.rows.map((r) => r.t), ["2025-11-15 16:15:35", "2025-11-15 16:15:35"]);

  // Idempotent: a second run neither re-converts nor re-flags.
  await initSchema();
  const again = await query(`SELECT id, processed_at, date_provenance FROM clean.orders ORDER BY id`);
  assert.equal(again.rows[0].processed_at.toISOString(), "2025-11-16T00:15:35.000Z");
  assert.deepEqual(again.rows.map((r) => r.date_provenance), ["rederived_from_raw", "unverified_assumed_utc"]);
});

suite("briefings computed before the conversion stop being sendable", async () => {
  await db.resetDatabase();
  await query(`DROP TABLE IF EXISTS clean.orders_date_backup`);
  await query(`ALTER TABLE clean.orders ALTER COLUMN processed_at TYPE TIMESTAMP USING processed_at AT TIME ZONE 'UTC'`);
  await query(`ALTER TABLE clean.orders DROP COLUMN IF EXISTS date_provenance`);

  const sync = await query(
    `INSERT INTO clean.sync_runs (shop_domain, status) VALUES ($1, 'complete') RETURNING id`, [SHOP]
  );
  await query(
    `INSERT INTO clean.engine_run_snapshots
       (run_id, shop_domain, store_id, engine_run, sync_run_id, input_provenance)
     VALUES ('run-before-tz', $1, 'store', '{}'::jsonb, $2, 'verified')`,
    [SHOP, sync.rows[0].id]
  );
  await query(
    `INSERT INTO clean.orders (id, shop_domain, created_at, processed_at, total_price, raw)
     VALUES ('t1', $1, '2025-11-15T16:15:35-08:00', '2025-11-15T16:15:35-08:00', 10,
             '{"created_at":"2025-11-15T16:15:35-08:00"}'::jsonb)`,
    [SHOP]
  );

  await initSchema();

  // The run is still there — history is never deleted — but it can no longer be
  // sent, because the windows it was computed over may have moved.
  const run = await query(`SELECT input_provenance FROM clean.engine_run_snapshots WHERE run_id = 'run-before-tz'`);
  assert.equal(run.rows[0].input_provenance, "predates_timezone_fix");

  const { assertInputVerifiedForHandoff } = require("../src/services/syncService");
  await assert.rejects(() => assertInputVerifiedForHandoff("run-before-tz", SHOP), (error) => {
    assert.equal(error.provenance, "predates_timezone_fix");
    assert.match(error.message, /analysis windows may be shifted/);
    return true;
  });
});
