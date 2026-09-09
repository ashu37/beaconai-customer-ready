const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { initSchema } = require("../src/schema");

const SHOP = "refund-migration.myshopify.com";

// Write a refund row the way the pre-fix code did: no refund_id column value,
// Shopify's id only inside `raw`.
async function insertLegacyRefund({ refundId, lineItemId, amount = "50.00" }) {
  await query(
    `INSERT INTO clean.refunds (shop_domain, order_id, created_at, line_item_id, transaction_amount, quantity, raw)
     VALUES ($1, '9001', NOW(), $2, $3, 1, $4::jsonb)`,
    [SHOP, lineItemId, amount, JSON.stringify({ id: refundId, note: "legacy" })]
  );
}

test.after(async () => {
  if (db.available) await db.closeDatabase();
});

suite("the migration backfills refund ids and quarantines existing duplicates", async () => {
  await db.resetDatabase();
  await query(`TRUNCATE clean.refunds_quarantine`).catch(() => {});

  // Three syncs before the fix meant three copies of the same refund.
  await insertLegacyRefund({ refundId: "77001", lineItemId: "9000" });
  await insertLegacyRefund({ refundId: "77001", lineItemId: "9000" });
  await insertLegacyRefund({ refundId: "77001", lineItemId: "9000" });
  // A second line item on the same refund is NOT a duplicate.
  await insertLegacyRefund({ refundId: "77001", lineItemId: "9001", amount: "10.00" });
  // A different refund entirely.
  await insertLegacyRefund({ refundId: "77002", lineItemId: "9002", amount: "20.00" });

  const before = await query(
    `SELECT count(*)::int AS n, sum(transaction_amount)::numeric AS total
       FROM clean.refunds WHERE shop_domain = $1`, [SHOP]
  );
  assert.equal(before.rows[0].n, 5);
  assert.equal(Number(before.rows[0].total), 180, "the doubled total a merchant would have been shown");

  await initSchema();

  // Backfilled from raw->>'id', which is what makes the insert guard work at all.
  const nulls = await query(
    `SELECT count(*)::int AS n FROM clean.refunds WHERE shop_domain = $1 AND refund_id IS NULL`, [SHOP]
  );
  assert.equal(nulls.rows[0].n, 0);

  const after = await query(
    `SELECT count(*)::int AS n, sum(transaction_amount)::numeric AS total
       FROM clean.refunds WHERE shop_domain = $1`, [SHOP]
  );
  assert.equal(after.rows[0].n, 3, "one row per (refund, line item)");
  assert.equal(Number(after.rows[0].total), 80);

  // Non-destructive: the extra copies were MOVED, not deleted, so the migration
  // is reversible and auditable.
  const quarantined = await query(
    `SELECT count(*)::int AS n, min(quarantine_reason) AS reason
       FROM clean.refunds_quarantine WHERE shop_domain = $1`, [SHOP]
  );
  assert.equal(quarantined.rows[0].n, 2);
  assert.equal(quarantined.rows[0].reason, "duplicate_from_resync_before_refund_id");

  // The row kept is the earliest one.
  const kept = await query(
    `SELECT id FROM clean.refunds WHERE shop_domain = $1 AND refund_id = '77001' AND line_item_id = '9000'`,
    [SHOP]
  );
  const moved = await query(
    `SELECT id FROM clean.refunds_quarantine WHERE shop_domain = $1 ORDER BY id`, [SHOP]
  );
  assert.ok(kept.rows[0].id < moved.rows[0].id);
});

suite("the migration is idempotent and leaves un-idable refunds alone", async () => {
  await db.resetDatabase();
  await query(`TRUNCATE clean.refunds_quarantine`).catch(() => {});

  await insertLegacyRefund({ refundId: "88001", lineItemId: "9000" });
  await insertLegacyRefund({ refundId: "88001", lineItemId: "9000" });
  // Shopify sent no refund id: cannot be grouped safely, so it must be left
  // exactly as found. Guessing would be worse than the duplicate.
  await query(
    `INSERT INTO clean.refunds (shop_domain, order_id, created_at, line_item_id, transaction_amount, quantity, raw)
     VALUES ($1, '9002', NOW(), '9500', '5.00', 1, '{"note":"no id"}'::jsonb)`,
    [SHOP]
  );
  await query(
    `INSERT INTO clean.refunds (shop_domain, order_id, created_at, line_item_id, transaction_amount, quantity, raw)
     VALUES ($1, '9002', NOW(), '9500', '5.00', 1, '{"note":"no id"}'::jsonb)`,
    [SHOP]
  );

  await initSchema();
  const first = await query(`SELECT count(*)::int AS n FROM clean.refunds WHERE shop_domain = $1`, [SHOP]);
  assert.equal(first.rows[0].n, 3, "one deduped pair plus both un-idable rows");

  // Running it again changes nothing.
  await initSchema();
  const second = await query(`SELECT count(*)::int AS n FROM clean.refunds WHERE shop_domain = $1`, [SHOP]);
  assert.equal(second.rows[0].n, 3);
  const quarantined = await query(
    `SELECT count(*)::int AS n FROM clean.refunds_quarantine WHERE shop_domain = $1`, [SHOP]
  );
  assert.equal(quarantined.rows[0].n, 1, "the second run quarantines nothing new");
});
