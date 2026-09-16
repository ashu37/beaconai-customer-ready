const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { config } = require("../src/config");
const { handleShopifyWebhook } = require("../src/services/shopifyWebhookService");
const {
  exportCustomerData,
  pendingPrivacyRequests,
  redactCustomer,
} = require("../src/services/privacyRequestService");
const { upsertAllShopifyData } = require("../src/services/shopifyRepository");

// PR B, B4: one customer's request, which is not the same as deleting a store.

const SHOP = "privacy.myshopify.com";
const SUBJECT = "erin@example.com";
const OTHER = "sam@example.com";

// The webhook signature is checked against the app's client secret, which a
// test run has no reason to hold.
config.shopify.clientSecret = "test-shopify-secret";

test.after(async () => {
  if (db.available) await db.closeDatabase();
});

function shopifyOrder(id, customerId, email) {
  return {
    id,
    email,
    total_price: "42.00",
    created_at: "2026-02-01T10:00:00Z",
    processed_at: "2026-02-01T10:00:00Z",
    currency: "USD",
    customer: { id: customerId, email, first_name: "Erin", last_name: "Vasquez" },
    billing_address: { address1: "9 Harbour Road", city: "Cork", phone: "+353-21-000" },
    shipping_address: { address1: "9 Harbour Road", city: "Cork" },
    phone: "+353-21-000",
    line_items: [{ id: `li-${id}`, quantity: 1, price: "42.00", product_id: "p1" }],
  };
}

async function populate() {
  await query(`INSERT INTO clean.shop (shop_domain, iana_timezone, currency) VALUES ($1, 'UTC', 'EUR')`, [SHOP]);
  await upsertAllShopifyData(SHOP, {
    customers: [
      { id: "cust-1", email: SUBJECT, created_at: "2026-01-01T00:00:00Z", state: "enabled", tags: "vip",
        email_marketing_consent: { state: "subscribed" } },
      { id: "cust-2", email: OTHER, created_at: "2026-01-02T00:00:00Z", state: "enabled", tags: "new" },
    ],
    orders: [shopifyOrder("o1", "cust-1", SUBJECT), shopifyOrder("o2", "cust-2", OTHER)],
  });

  const run = "run-privacy";
  const sync = await query(
    `INSERT INTO clean.sync_runs (shop_domain, status, started_at) VALUES ($1, 'complete', NOW()) RETURNING id`,
    [SHOP]
  );
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run, sync_run_id, input_provenance)
     VALUES ($1, $2, 'privacy', '{}'::jsonb, $3, 'verified')`,
    [run, SHOP, sync.rows[0].id]
  );
  await query(
    `INSERT INTO clean.engine_audiences (run_id, audience_definition_id, play_id, materialization_status, customer_ids)
     VALUES ($1, 'aud-1', 'winback', 'MATERIALIZED', ARRAY['cust-1','cust-2'])`,
    [run]
  );
  const campaign = await query(
    `INSERT INTO clean.campaigns (shop_domain, play_id, run_id, status) VALUES ($1, 'winback', $2, 'sent') RETURNING id`,
    [SHOP, run]
  );
  const campaignId = campaign.rows[0].id;
  await query(
    `INSERT INTO clean.campaign_recipients (campaign_id, customer_id, arm, email)
     VALUES ($1, 'cust-1', 'treated', $2), ($1, 'cust-2', 'holdout', $3)`,
    [campaignId, SUBJECT, OTHER]
  );
  await query(
    `INSERT INTO clean.campaign_measurements (campaign_id, window_days, arm, n_customers, n_orders, revenue)
     VALUES ($1, 30, 'treated', 1, 1, 42), ($1, 30, 'holdout', 1, 1, 42)`,
    [campaignId]
  );
  return { campaignId, runId: run };
}

suite("a data request gathers what is held about that customer, and only them", async () => {
  await db.resetDatabase();
  await populate();

  const data = await exportCustomerData(SHOP, { email: SUBJECT });
  assert.equal(data.found, true);
  assert.deepEqual(data.customers.map((c) => c.id), ["cust-1"]);
  assert.deepEqual(data.orders.map((o) => o.id), ["o1"]);
  assert.deepEqual(data.campaignMemberships.map((m) => m.arm), ["treated"]);
  assert.equal(data.audiences.length, 1, "being in an audience is data about them too");

  const serialised = JSON.stringify(data);
  assert.ok(!serialised.includes(OTHER), "another customer's data is not in the answer");

  // Looked up by Shopify's customer id just as well as by email.
  const byId = await exportCustomerData(SHOP, { customerId: "cust-1" });
  assert.deepEqual(byId.customers.map((c) => c.id), ["cust-1"]);

  const missing = await exportCustomerData(SHOP, { email: "nobody@example.com" });
  assert.equal(missing.found, false);
});

suite("a redaction removes everything personal and leaves the merchant's records standing", async () => {
  await db.resetDatabase();
  const { campaignId } = await populate();

  const result = await redactCustomer(SHOP, { email: SUBJECT });
  assert.equal(result.found, true);
  assert.deepEqual(result.customerIds, ["cust-1"]);

  const customer = await query(`SELECT * FROM clean.customers WHERE id = 'cust-1'`);
  assert.equal(customer.rows[0].email, null);
  assert.equal(customer.rows[0].tags, null);
  assert.equal(customer.rows[0].email_marketing_consent, null);
  assert.ok(customer.rows[0].redacted_at instanceof Date);

  // The order stays — it is the merchant's business record — with nothing
  // personal left in it, including inside the stored payload.
  const order = await query(`SELECT * FROM clean.orders WHERE id = 'o1'`);
  assert.equal(order.rows[0].email, null);
  assert.equal(order.rows[0].total_price, "42.00", "the money is the merchant's record");
  const raw = JSON.stringify(order.rows[0].raw);
  for (const leaked of ["Vasquez", "Harbour Road", "+353-21-000", SUBJECT]) {
    assert.ok(!raw.includes(leaked), `${leaked} survived in clean.orders.raw`);
  }
  assert.ok(raw.includes("line_items"), "the order's contents are untouched");

  // Membership stays, the address goes: the measurement is computed from arms.
  const recipients = await query(
    `SELECT customer_id, arm, email FROM clean.campaign_recipients WHERE campaign_id = $1 ORDER BY customer_id`,
    [campaignId]
  );
  assert.deepEqual(recipients.rows.map((r) => r.arm), ["treated", "holdout"]);
  assert.equal(recipients.rows[0].email, null);
  assert.equal(recipients.rows[1].email, OTHER, "the other customer is untouched");

  const measurements = await query(
    `SELECT arm, n_customers, revenue FROM clean.campaign_measurements WHERE campaign_id = $1 ORDER BY arm`,
    [campaignId]
  );
  assert.deepEqual(measurements.rows.map((m) => m.n_customers), [1, 1], "aggregate counts are kept");

  const other = await query(`SELECT email, tags FROM clean.customers WHERE id = 'cust-2'`);
  assert.equal(other.rows[0].email, OTHER);
});

suite("a later sync does not put a redacted customer's details back", async () => {
  await db.resetDatabase();
  await populate();
  await redactCustomer(SHOP, { email: SUBJECT });

  // Shopify keeps returning the record for a while after a redact request.
  await upsertAllShopifyData(SHOP, {
    customers: [
      { id: "cust-1", email: SUBJECT, created_at: "2026-01-01T00:00:00Z", state: "enabled", tags: "vip" },
      { id: "cust-2", email: OTHER, created_at: "2026-01-02T00:00:00Z", state: "enabled", tags: "regular" },
    ],
  });

  const customer = await query(`SELECT email, tags FROM clean.customers WHERE id = 'cust-1'`);
  assert.equal(customer.rows[0].email, null, "the sync refilled a redacted customer");
  const other = await query(`SELECT tags FROM clean.customers WHERE id = 'cust-2'`);
  assert.equal(other.rows[0].tags, "regular", "an ordinary customer still updates normally");
});

function signed(topic, body) {
  const raw = Buffer.from(JSON.stringify(body));
  return {
    rawBody: raw,
    headers: {
      "x-shopify-topic": topic,
      "x-shopify-shop-domain": SHOP,
      "x-shopify-webhook-id": `wh-${topic}-${crypto.randomUUID()}`,
      "x-shopify-hmac-sha256": crypto
        .createHmac("sha256", config.shopify.clientSecret)
        .update(raw)
        .digest("base64"),
    },
  };
}

suite("a customers/redact webhook is recorded, carried out, and its identifiers dropped", async () => {
  await db.resetDatabase();
  await populate();

  const response = await handleShopifyWebhook(
    signed("customers/redact", { shop_id: 1, customer: { id: "cust-1", email: SUBJECT } })
  );
  assert.equal(response.status, 200);

  const customer = await query(`SELECT email, redacted_at FROM clean.customers WHERE id = 'cust-1'`);
  assert.equal(customer.rows[0].email, null, "the request was recorded but never carried out");

  const request = await query(`SELECT * FROM clean.privacy_requests WHERE topic = 'customers/redact'`);
  assert.equal(request.rows.length, 1);
  assert.ok(request.rows[0].completed_at instanceof Date);
  assert.ok(
    !JSON.stringify(request.rows[0].payload).includes(SUBJECT),
    "the completed request still holds the email it was about"
  );
  assert.deepEqual(await pendingPrivacyRequests(SHOP), []);
});

suite("a shop/redact webhook erases the store", async () => {
  await db.resetDatabase();
  await populate();

  const response = await handleShopifyWebhook(signed("shop/redact", { shop_id: 1, shop_domain: SHOP }));
  assert.equal(response.status, 200);

  for (const table of ["clean.customers", "clean.orders", "clean.campaigns", "clean.shop", "clean.campaign_recipients"]) {
    const scope = table === "clean.campaign_recipients"
      ? `campaign_id IN (SELECT id FROM clean.campaigns WHERE shop_domain = $1)`
      : `shop_domain = $1`;
    const { rows } = await query(`SELECT count(*)::int AS n FROM ${table} WHERE ${scope}`, [SHOP]);
    assert.equal(rows[0].n, 0, `${table} still holds rows for the redacted shop`);
  }

  const request = await query(`SELECT completed_at FROM clean.privacy_requests WHERE topic = 'shop/redact'`);
  assert.ok(request.rows[0].completed_at instanceof Date, "the record of the request survives the deletion");
});

suite("an unsigned privacy webhook does nothing at all", async () => {
  await db.resetDatabase();
  await populate();

  const { rawBody, headers } = signed("customers/redact", { customer: { id: "cust-1", email: SUBJECT } });
  const response = await handleShopifyWebhook({
    rawBody,
    headers: { ...headers, "x-shopify-hmac-sha256": "bm90LWEtc2lnbmF0dXJl" },
  });
  assert.equal(response.status, 401);

  const customer = await query(`SELECT email FROM clean.customers WHERE id = 'cust-1'`);
  assert.equal(customer.rows[0].email, SUBJECT, "an unsigned request redacted a customer");
  const requests = await query(`SELECT count(*)::int AS n FROM clean.privacy_requests`);
  assert.equal(requests.rows[0].n, 0);
});
