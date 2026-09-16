const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { initSchema } = require("../src/schema");
const { minimiseKlaviyoAssetPayload } = require("../src/services/dataMinimisation");
const { upsertAllShopifyData } = require("../src/services/shopifyRepository");
const { saveKlaviyoAsset } = require("../src/services/klaviyoClient");

// PR B, B1: the copies of customer data nothing reads are gone, and the ones
// the product needs are untouched.

test.after(async () => {
  if (db.available) await db.closeDatabase();
});

const SHOP = "minimise.myshopify.com";

function shopifyCustomer(id, email) {
  return {
    id,
    email,
    created_at: "2026-01-04T10:00:00-05:00",
    state: "enabled",
    tags: "vip",
    email_marketing_consent: { state: "subscribed" },
    // Everything below is what a real Shopify payload carries and BeaconAI
    // has no use for.
    first_name: "Dana",
    last_name: "Okonkwo",
    phone: "+1-555-0100",
    note: "asked about a bulk order",
    addresses: [{ address1: "12 Rue Sainte-Catherine", city: "Montréal", zip: "H2X 1K4" }],
    last_order_id: 991,
  };
}

suite("a synced customer keeps the fields the engine uses and nothing else", async () => {
  await db.resetDatabase();
  await upsertAllShopifyData(SHOP, { customers: [shopifyCustomer("c1", "dana@example.com")] });

  const { rows } = await query(`SELECT * FROM clean.customers WHERE id = 'c1'`);
  assert.equal(rows.length, 1);
  const stored = rows[0];

  assert.equal(stored.email, "dana@example.com", "the audience build needs the email");
  assert.equal(stored.tags, "vip");
  assert.deepEqual(stored.email_marketing_consent, { state: "subscribed" });
  assert.ok(stored.created_at instanceof Date);

  assert.ok(!("raw" in stored), "the full Shopify customer record is not a column any more");
  // Nothing anywhere in the row carries the name, phone, note or address.
  const serialised = JSON.stringify(stored);
  for (const leaked of ["Okonkwo", "555-0100", "bulk order", "Sainte-Catherine"]) {
    assert.ok(!serialised.includes(leaked), `${leaked} is still stored: ${serialised}`);
  }
});

suite("an existing database has its stored customer payloads dropped on the next start", async () => {
  await db.resetDatabase();
  // Put the column and a row back, as a database created before B1 has them.
  await query(`ALTER TABLE clean.customers ADD COLUMN IF NOT EXISTS raw JSONB;`);
  await query(
    `INSERT INTO clean.customers (id, shop_domain, email, created_at, date_provenance, raw)
     VALUES ('c2', $1, 'old@example.com', NOW(), 'rederived_from_raw', $2)`,
    [SHOP, JSON.stringify(shopifyCustomer("c2", "old@example.com"))]
  );

  await initSchema();

  const { rows } = await query(
    `SELECT column_name FROM information_schema.columns
      WHERE table_schema = 'clean' AND table_name = 'customers' AND column_name = 'raw'`
  );
  assert.equal(rows.length, 0, "the column, and the payloads in it, are gone");
  const kept = await query(`SELECT email FROM clean.customers WHERE id = 'c2'`);
  assert.equal(kept.rows[0].email, "old@example.com", "the customer row itself survives");
});

suite("a saved Klaviyo asset records what was handed off, not who received it", async () => {
  await db.resetDatabase();
  await saveKlaviyoAsset({
    shopDomain: SHOP,
    assetType: "campaign_send_package",
    externalId: "01CAMPAIGN",
    payload: {
      campaign: { subject: "A second look", preview: "Picked for you" },
      audience: {
        runId: "run-7",
        audienceDefinitionId: "aud-3",
        status: "MATERIALIZED",
        count: 2,
        memberCount: 3,
        suppressedCount: 1,
        unresolvedIds: ["c9"],
        recipients: [
          { customerId: "c1", email: "dana@example.com" },
          { customerId: "c2", email: "sam@example.com" },
        ],
      },
      packageResult: {
        template: { data: { type: "template", id: "T1" } },
        html: "<p>Hello {{ first_name }}</p>",
        list: { data: { type: "list", id: "L1" } },
        importJob: { data: { type: "profile-bulk-import-job", id: "J1" } },
        campaign: { data: { type: "campaign", id: "01CAMPAIGN" } },
        messages: { data: [{ id: "M1" }] },
        assignment: { ok: true },
      },
      holdout: { treated: 2, held: 1, pct: 0.1 },
    },
  });

  const { rows } = await query(`SELECT payload FROM clean.klaviyo_assets WHERE external_id = '01CAMPAIGN'`);
  const payload = rows[0].payload;

  assert.ok(!JSON.stringify(payload).includes("@example.com"), "no recipient email survives the write");
  assert.equal(payload.audience.recipients, undefined);
  // The counts that make the row worth keeping are still there.
  assert.equal(payload.audience.count, 2);
  assert.equal(payload.audience.memberCount, 3);
  assert.equal(payload.audience.suppressedCount, 1);
  assert.equal(payload.audience.unresolvedCount, 1);
  assert.deepEqual(payload.holdout, { treated: 2, held: 1, pct: 0.1 });
  // And so are the provider ids reconciliation looks for.
  assert.equal(payload.packageResult.campaign.id, "01CAMPAIGN");
  assert.equal(payload.packageResult.list.id, "L1");
  assert.equal(payload.packageResult.messageId, "M1");
  assert.equal(payload.packageResult.templateAssigned, true);
  // The suggested copy is what "the handoff suggestion" means; it names no one.
  assert.equal(payload.campaign.subject, "A second look");
});

suite("asset rows written before B1 are redacted on the next start", async () => {
  await db.resetDatabase();
  await query(
    `INSERT INTO clean.klaviyo_assets (shop_domain, asset_type, external_id, payload)
     VALUES ($1, 'campaign_send_package', '01OLD', $2)`,
    [
      SHOP,
      JSON.stringify({
        audience: { count: 1, recipients: [{ customerId: "c1", email: "dana@example.com" }] },
        packageResult: { list: { data: { id: "L9" } }, html: "<p>body</p>" },
      }),
    ]
  );

  await initSchema();

  const { rows } = await query(`SELECT payload FROM clean.klaviyo_assets WHERE external_id = '01OLD'`);
  assert.ok(!JSON.stringify(rows[0].payload).includes("dana@example.com"));
  assert.equal(rows[0].payload.audience.count, 1, "the count it recorded is kept");
  assert.equal(rows[0].payload.packageResult.list.id, "L9");
});

test("minimising is stable: a payload already minimal is unchanged", () => {
  const once = minimiseKlaviyoAssetPayload({
    campaign: { subject: "s" },
    audience: { runId: "r", count: 4, recipients: [{ email: "a@b.c" }] },
    packageResult: { campaign: { data: { id: "X" } } },
  });
  assert.deepEqual(minimiseKlaviyoAssetPayload(once), once);
});
