const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { config } = require("../src/config");
const { handleShopifyWebhook } = require("../src/services/shopifyWebhookService");
const {
  exportCustomerData,
  pendingPrivacyRequests,
  recordDelivery,
  redactCustomer,
  writeCustomerExport,
} = require("../src/services/privacyRequestService");
const { upsertAllShopifyData } = require("../src/services/shopifyRepository");
const { buildEngineInputSnapshot } = require("../src/services/engineInputSnapshot");

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

// Each buyer's details are their OWN. A fixture that gives both customers the
// same name cannot tell "the subject was redacted" from "everyone was".
const PERSON = {
  "cust-1": { first: "Erin", last: "Vasquez", street: "9 Harbour Road", phone: "+353-21-000111" },
  "cust-2": { first: "Sam", last: "Ngata", street: "4 Mill Lane", phone: "+353-21-000222" },
};

function shopifyOrder(id, customerId, email) {
  const who = PERSON[customerId];
  return {
    id,
    email,
    total_price: "42.00",
    created_at: "2026-02-01T10:00:00Z",
    processed_at: "2026-02-01T10:00:00Z",
    currency: "USD",
    customer: { id: customerId, email, first_name: who.first, last_name: who.last },
    billing_address: { address1: who.street, city: "Cork", phone: who.phone },
    shipping_address: { address1: who.street, city: "Cork", province: "Munster", country: "Ireland" },
    phone: who.phone,
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
  for (const leaked of ["Vasquez", "Harbour Road", "+353-21-000111", SUBJECT]) {
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

// --- Review findings on PR #63 ----------------------------------------------

suite("a later order sync does not put a redacted customer's details back", async () => {
  await db.resetDatabase();
  await populate();
  await redactCustomer(SHOP, { email: SUBJECT });

  // Shopify keeps returning the order in full after a customers/redact request.
  await upsertAllShopifyData(SHOP, { orders: [shopifyOrder("o1", "cust-1", SUBJECT)] });

  const order = await query(`SELECT email, raw, total_price FROM clean.orders WHERE id = 'o1'`);
  assert.equal(order.rows[0].email, null, "the resync restored the order's email column");
  const raw = JSON.stringify(order.rows[0].raw);
  for (const leaked of ["Vasquez", "Harbour Road", "+353-21-000111", SUBJECT]) {
    assert.ok(!raw.includes(leaked), `the resync restored ${leaked} in clean.orders.raw`);
  }
  // The order is still the merchant's record, and still attributed.
  assert.equal(order.rows[0].total_price, "42.00");
  const attributed = await query(`SELECT customer_id FROM clean.orders WHERE id = 'o1'`);
  assert.equal(attributed.rows[0].customer_id, "cust-1");

  // An un-redacted customer's order syncs normally.
  const other = await query(`SELECT email, raw FROM clean.orders WHERE id = 'o2'`);
  assert.equal(other.rows[0].email, OTHER);
  assert.ok(JSON.stringify(other.rows[0].raw).includes("Mill Lane"));
});

suite("a data request stays outstanding until an export exists and delivery is recorded", async () => {
  await db.resetDatabase();
  await populate();

  const response = await handleShopifyWebhook(
    signed("customers/data_request", { shop_id: 1, customer: { id: "cust-1", email: SUBJECT } })
  );
  assert.equal(response.status, 200);

  // Not completed by the webhook: nothing has reached the merchant yet.
  const pending = await pendingPrivacyRequests(SHOP);
  assert.equal(pending.length, 1, "the request was closed before anyone had the data");
  const id = pending[0].id;
  assert.equal(pending[0].payload.customer_email, SUBJECT, "the subject is still there to act on");

  const outDir = await fs.mkdtemp(path.join(os.tmpdir(), "beaconai-privacy-"));
  try {
    const { file, found } = await writeCustomerExport(id, outDir);
    assert.equal(found, true);
    const written = JSON.parse(await fs.readFile(file, "utf8"));
    assert.deepEqual(written.customers.map((c) => c.id), ["cust-1"]);
    assert.deepEqual(written.orders.map((o) => o.id), ["o1"]);
    assert.ok(!JSON.stringify(written).includes(OTHER));

    // Producing the file is not delivering it.
    assert.equal((await pendingPrivacyRequests(SHOP)).length, 1);

    // Delivery has to say how.
    await assert.rejects(() => recordDelivery(id, ""), /how it was delivered/);

    const done = await recordDelivery(id, "emailed the merchant 2026-09-16");
    assert.ok(done.completed_at instanceof Date);
    assert.deepEqual(await pendingPrivacyRequests(SHOP), []);

    const row = await query(`SELECT payload FROM clean.privacy_requests WHERE id = $1`, [id]);
    assert.equal(row.rows[0].payload.result.delivered, "emailed the merchant 2026-09-16");
    assert.ok(!JSON.stringify(row.rows[0].payload).includes(SUBJECT), "identifiers survive delivery");

    await assert.rejects(() => recordDelivery(id, "again"), /already complete/);
  } finally {
    await fs.rm(outDir, { recursive: true, force: true });
  }
});

/**
 * Every text-ish value stored anywhere in clean/raw, with the column it came
 * from. Deliberately catalogue-driven rather than a list: the redaction bugs
 * found so far were all a place nobody thought to look.
 */
async function everyStoredValue() {
  const { rows: columns } = await query(
    `SELECT c.table_schema AS schema, c.table_name AS name, c.column_name AS column
       FROM information_schema.columns c
       JOIN pg_class pc ON pc.relname = c.table_name
       JOIN pg_namespace pn ON pn.oid = pc.relnamespace AND pn.nspname = c.table_schema
      WHERE c.table_schema IN ('clean', 'raw')
        AND pc.relkind = 'r'
        AND c.data_type IN ('text', 'character varying', 'json', 'jsonb', 'ARRAY')
      ORDER BY 1, 2, 3`
  );

  const found = [];
  for (const col of columns) {
    const { rows } = await query(
      `SELECT "${col.column}"::text AS value FROM "${col.schema}"."${col.name}" WHERE "${col.column}" IS NOT NULL`
    );
    for (const row of rows) {
      if (row.value) found.push({ where: `${col.schema}.${col.name}.${col.column}`, value: row.value });
    }
  }
  return found;
}

suite("after a redaction no trace of the customer is left anywhere in the database", async () => {
  await db.resetDatabase();
  await populate();

  // The copies the orders table is not: the rows an analysis was computed from,
  // and the payloads every sync wrote.
  const input = {
    shop: { shop_domain: SHOP, currency: "EUR", iana_timezone: "UTC" },
    orders: [
      { ...shopifyOrder("o1", "cust-1", SUBJECT), customer_id: "cust-1", raw: shopifyOrder("o1", "cust-1", SUBJECT) },
      { ...shopifyOrder("o2", "cust-2", OTHER), customer_id: "cust-2", raw: shopifyOrder("o2", "cust-2", OTHER) },
    ],
    order_line_items: [],
    customers: [],
    products: [],
  };
  const snapshot = buildEngineInputSnapshot(input);
  assert.ok(
    JSON.stringify(snapshot).includes("Vasquez"),
    "the fixture must actually contain the name, or this test proves nothing"
  );
  await query(`UPDATE clean.sync_runs SET input_snapshot = $2::jsonb WHERE shop_domain = $1`, [
    SHOP,
    JSON.stringify(snapshot),
  ]);
  await query(
    `INSERT INTO raw.shopify_events (shop_domain, resource_type, payload) VALUES
       ($1, 'orders', $2::jsonb),
       ($1, 'customers', $3::jsonb)`,
    [
      SHOP,
      JSON.stringify([shopifyOrder("o1", "cust-1", SUBJECT), shopifyOrder("o2", "cust-2", OTHER)]),
      JSON.stringify([
        { id: "cust-1", email: SUBJECT, first_name: "Erin", last_name: "Vasquez", phone: "+353-21-000111" },
        { id: "cust-2", email: OTHER, first_name: "Sam", last_name: "Ngata" },
      ]),
    ]
  );

  const before = await everyStoredValue();
  assert.ok(before.some((v) => v.value.includes(SUBJECT)), "the fixture must contain the subject's email");

  await redactCustomer(SHOP, { email: SUBJECT });

  const after = await everyStoredValue();
  for (const trace of ["Vasquez", "Harbour Road", "+353-21-000111", SUBJECT]) {
    const leaks = after.filter((v) => v.value.includes(trace));
    assert.deepEqual(
      leaks.map((l) => l.where),
      [],
      `"${trace}" is still stored after the redaction`
    );
  }

  // The other customer is untouched, everywhere.
  assert.ok(after.some((v) => v.value.includes(OTHER)), "the other customer was redacted too");
  assert.ok(after.some((v) => v.value.includes("Ngata")), "the other customer's name was removed too");
});

suite("a redacted customer's analysis input keeps its shape and its identity", async () => {
  await db.resetDatabase();
  await populate();
  const input = {
    shop: { shop_domain: SHOP, currency: "EUR", iana_timezone: "UTC" },
    orders: [
      { ...shopifyOrder("o1", "cust-1", SUBJECT), customer_id: "cust-1", raw: shopifyOrder("o1", "cust-1", SUBJECT) },
      { ...shopifyOrder("o3", "cust-1", SUBJECT), customer_id: "cust-1", raw: shopifyOrder("o3", "cust-1", SUBJECT) },
      { ...shopifyOrder("o2", "cust-2", OTHER), customer_id: "cust-2", raw: shopifyOrder("o2", "cust-2", OTHER) },
    ],
    order_line_items: [], customers: [], products: [],
  };
  await query(`UPDATE clean.sync_runs SET input_snapshot = $2::jsonb WHERE shop_domain = $1`, [
    SHOP, JSON.stringify(buildEngineInputSnapshot(input)),
  ]);

  await redactCustomer(SHOP, { email: SUBJECT });

  const { rows } = await query(`SELECT input_snapshot FROM clean.sync_runs WHERE shop_domain = $1`, [SHOP]);
  const redacted = rows[0].input_snapshot.orderRows;
  assert.equal(redacted.length, 3, "no analysis row was dropped");
  assert.equal(redacted.filter((r) => r.Total === "42").length, 3, "the amounts are unchanged");

  // The engine groups by Customer Email when the column is present. Blanking it
  // would merge every redacted buyer into one; a pseudonym keeps one value per
  // person and still names nobody.
  const mine = redacted.filter((r) => r.customer_id === "cust-1");
  assert.equal(mine.length, 2);
  assert.deepEqual(new Set(mine.map((r) => r["Customer Email"])), new Set(["redacted-cust-1"]));
  assert.deepEqual(mine.map((r) => r["Billing Name"]), ["", ""]);
  assert.deepEqual(mine.map((r) => r["Shipping Country"]), ["", ""]);

  const theirs = redacted.filter((r) => r.customer_id === "cust-2");
  assert.equal(theirs[0]["Customer Email"], OTHER);
  assert.equal(theirs[0]["Billing Name"], "Sam Ngata", "an un-redacted buyer's row is untouched");
});
