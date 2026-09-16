const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const {
  STORE_TABLES,
  assertEveryTableIsAccountedFor,
  countStoreData,
  deleteStoreData,
  exportStoreData,
} = require("../src/services/storeDataService");

// PR B, B3: one store's data, exported and erased — derived rows included.

const MINE = "mine.myshopify.com";
const THEIRS = "theirs.myshopify.com";

test.after(async () => {
  if (db.available) await db.closeDatabase();
});

/** A store with a row in every table the deletion is supposed to reach. */
async function populate(shop, { storeId = null } = {}) {
  await query(`INSERT INTO clean.shop (shop_domain, iana_timezone, currency) VALUES ($1, 'UTC', 'USD')`, [shop]);
  await query(
    `INSERT INTO clean.connections (shop_domain, shopify_access_token, klaviyo_private_key)
     VALUES ($1, 'encrypted-shopify-token', 'encrypted-klaviyo-key')`,
    [shop]
  );
  await query(`INSERT INTO clean.store_access (shop_domain) VALUES ($1)`, [shop]);
  await query(
    `INSERT INTO clean.sessions (id, shop_domain, expires_at) VALUES ($1, $2, NOW() + INTERVAL '1 day')`,
    [`sess-${shop}`, shop]
  );
  await query(
    `INSERT INTO clean.oauth_states (state, shop_domain, provider, expires_at)
     VALUES ($1, $2, 'shopify', NOW() + INTERVAL '10 minutes')`,
    [`state-${shop}`, shop]
  );
  await query(`INSERT INTO clean.privacy_requests (shop_domain, topic) VALUES ($1, 'shop/redact')`, [shop]);

  await query(
    `INSERT INTO clean.customers (id, shop_domain, email, created_at) VALUES ($1, $2, $3, NOW())`,
    [`cust-${shop}`, shop, `buyer@${shop}`]
  );
  await query(
    `INSERT INTO clean.orders (id, shop_domain, created_at, processed_at, total_price, customer_id)
     VALUES ($1, $2, NOW(), NOW(), 40, $3)`,
    [`order-${shop}`, shop, `cust-${shop}`]
  );
  await query(
    `INSERT INTO clean.order_line_items (id, shop_domain, order_id, quantity, price)
     VALUES ($1, $2, $3, 1, 40)`,
    [`li-${shop}`, shop, `order-${shop}`]
  );
  await query(
    `INSERT INTO clean.refunds (shop_domain, order_id, created_at, transaction_amount)
     VALUES ($1, $2, NOW(), 5)`,
    [shop, `order-${shop}`]
  );
  await query(
    `INSERT INTO clean.refunds_quarantine (shop_domain, order_id, created_at, transaction_amount)
     VALUES ($1, $2, NOW(), 5)`,
    [shop, `order-${shop}`]
  );
  await query(`INSERT INTO clean.products (id, shop_domain, title, status) VALUES ($1, $2, 'A thing', 'active')`, [`prod-${shop}`, shop]);
  await query(
    `INSERT INTO clean.product_variants (id, shop_domain, product_id, sku, price) VALUES ($1, $2, $3, 'SKU', 40)`,
    [`var-${shop}`, shop, `prod-${shop}`]
  );
  await query(`INSERT INTO raw.shopify_events (shop_domain, resource_type, payload) VALUES ($1, 'orders', '[]'::jsonb)`, [shop]);
  await query(`INSERT INTO raw.klaviyo_events (shop_domain, resource_type, payload) VALUES ($1, 'campaigns', '[]'::jsonb)`, [shop]);

  const sync = await query(
    `INSERT INTO clean.sync_runs (shop_domain, status, started_at) VALUES ($1, 'complete', NOW()) RETURNING id`,
    [shop]
  );
  const syncId = sync.rows[0].id;
  await query(
    `INSERT INTO clean.active_sync (shop_domain, sync_run_id, published_at, started_at) VALUES ($1, $2, NOW(), NOW())`,
    [shop, syncId]
  );

  const runId = `run-${shop}`;
  await query(
    `INSERT INTO clean.engine_run_snapshots (run_id, shop_domain, store_id, engine_run, sync_run_id, input_provenance)
     VALUES ($1, $2, $3, '{}'::jsonb, $4, 'verified')`,
    [runId, shop, storeId || shop.split(".")[0], syncId]
  );
  await query(
    `INSERT INTO clean.engine_audiences (run_id, audience_definition_id, play_id, materialization_status, customer_ids)
     VALUES ($1, 'aud-1', 'winback', 'MATERIALIZED', ARRAY[$2])`,
    [runId, `cust-${shop}`]
  );
  await query(`INSERT INTO clean.analysis_jobs (shop_domain, run_id, status) VALUES ($1, $2, 'complete')`, [shop, runId]);

  const tpl = await query(
    `INSERT INTO clean.brand_email_templates (shop_domain, version, html) VALUES ($1, 1, '<p>hi</p>') RETURNING id`,
    [shop]
  );
  await query(`INSERT INTO clean.brand_email_active (shop_domain, template_id) VALUES ($1, $2)`, [shop, tpl.rows[0].id]);
  await query(
    `INSERT INTO clean.klaviyo_assets (shop_domain, asset_type, external_id, payload)
     VALUES ($1, 'campaign_send_package', 'K1', '{}'::jsonb)`,
    [shop]
  );

  const campaign = await query(
    `INSERT INTO clean.campaigns (shop_domain, play_id, run_id, status) VALUES ($1, 'winback', $2, 'draft') RETURNING id`,
    [shop, runId]
  );
  const campaignId = campaign.rows[0].id;
  await query(
    `INSERT INTO clean.campaign_recipients (campaign_id, customer_id, arm, email)
     VALUES ($1, $2, 'treated', $3)`,
    [campaignId, `cust-${shop}`, `buyer@${shop}`]
  );
  await query(
    `INSERT INTO clean.campaign_recipient_exclusions (campaign_id, customer_ref, reason)
     VALUES ($1, 'cust-missing', 'no_email')`,
    [campaignId]
  );
  await query(
    `INSERT INTO clean.campaign_measurements (campaign_id, window_days, arm, n_customers, n_orders, revenue)
     VALUES ($1, 30, 'treated', 1, 1, 40)`,
    [campaignId]
  );
  return { runId, campaignId, syncId };
}

suite("every table in the database has a rule for how it is scoped to a store", async () => {
  await db.resetDatabase();
  await assertEveryTableIsAccountedFor();

  await query(`CREATE TABLE clean.a_later_table (id int, shop_domain text)`);
  try {
    await assert.rejects(
      () => assertEveryTableIsAccountedFor(),
      /clean\.a_later_table/,
      "a table added without a deletion rule must fail loudly, not be skipped"
    );
  } finally {
    await query(`DROP TABLE clean.a_later_table`);
  }
});

suite("deleting a store leaves zero rows for it in every table, and the next store untouched", async () => {
  await db.resetDatabase();
  await populate(MINE);
  await populate(THEIRS);

  const before = await countStoreData(MINE);
  for (const { table } of STORE_TABLES) {
    assert.ok(before[table] > 0, `${table} has no row to delete — the test proves nothing about it`);
  }

  const result = await deleteStoreData(MINE);

  const after = await countStoreData(MINE);
  for (const { table, retain } of STORE_TABLES) {
    if (retain) {
      assert.equal(after[table], 1, `${table} is kept deliberately: ${retain}`);
      assert.equal(result.retained[table].reason, retain);
      continue;
    }
    assert.equal(after[table], 0, `${table} still has rows for the deleted store`);
  }

  // The derived tables are the ones that get missed. Named explicitly so a
  // regression says which.
  for (const table of [
    "clean.campaign_recipients",
    "clean.campaign_recipient_exclusions",
    "clean.campaign_measurements",
    "clean.engine_audiences",
  ]) {
    assert.equal(result.deleted[table], 1, `${table} was not deleted`);
  }

  // No email of theirs survives anywhere.
  const leaked = await query(
    `SELECT count(*)::int AS n FROM clean.campaign_recipients WHERE email LIKE $1`,
    [`%${MINE}`]
  );
  assert.equal(leaked.rows[0].n, 0);

  const theirs = await countStoreData(THEIRS);
  for (const { table } of STORE_TABLES) {
    assert.ok(theirs[table] > 0, `${table} lost the other store's rows`);
  }
});

suite("deletion is all or nothing", async () => {
  await db.resetDatabase();
  await populate(MINE);

  // Something outside clean/raw holds a reference with ON DELETE NO ACTION, so
  // the campaigns DELETE fails partway through — after the four campaign-derived
  // tables have already been emptied inside the transaction.
  await query(`CREATE TABLE public.blocker (id SERIAL PRIMARY KEY, campaign_id INTEGER REFERENCES clean.campaigns(id))`);
  await query(`INSERT INTO public.blocker (campaign_id) SELECT id FROM clean.campaigns WHERE shop_domain = $1`, [MINE]);
  try {
    await assert.rejects(() => deleteStoreData(MINE));
    const after = await countStoreData(MINE);
    for (const { table } of STORE_TABLES) {
      assert.ok(after[table] > 0, `${table} was deleted although the deletion failed`);
    }
  } finally {
    await query(`DROP TABLE public.blocker`);
  }
});

suite("deleting a store removes its engine files, and only its own", async () => {
  await db.resetDatabase();
  await populate(MINE, { storeId: "mine-store" });
  await populate(THEIRS, { storeId: "theirs-store" });

  const engineDir = await fs.mkdtemp(path.join(os.tmpdir(), "beaconai-engine-"));
  try {
    for (const id of ["mine-store", "theirs-store"]) {
      await fs.mkdir(path.join(engineDir, "data", id, "runs"), { recursive: true });
      await fs.writeFile(path.join(engineDir, "data", id, "runs", "audience.csv"), "customer_id\nc1\n");
    }

    const result = await deleteStoreData(MINE, { engineDir });
    assert.deepEqual(result.engineFiles, [path.join(engineDir, "data", "mine-store")]);
    await assert.rejects(() => fs.stat(path.join(engineDir, "data", "mine-store")));
    const survivor = await fs.stat(path.join(engineDir, "data", "theirs-store"));
    assert.ok(survivor.isDirectory(), "the other store's engine files are untouched");
  } finally {
    await fs.rm(engineDir, { recursive: true, force: true });
  }
});

suite("an export hands over the store's data without handing over its credentials", async () => {
  await db.resetDatabase();
  await populate(MINE);
  await populate(THEIRS);

  const outDir = await fs.mkdtemp(path.join(os.tmpdir(), "beaconai-export-"));
  try {
    const manifest = await exportStoreData(MINE, outDir);
    assert.equal(manifest.shopDomain, MINE);
    for (const { table } of STORE_TABLES) {
      assert.equal(manifest.counts[table], 1, `${table} missing from the export`);
    }

    const customers = JSON.parse(await fs.readFile(path.join(outDir, "clean_customers.json"), "utf8"));
    assert.equal(customers[0].email, `buyer@${MINE}`, "the merchant's own data is theirs to take");

    const connections = JSON.parse(await fs.readFile(path.join(outDir, "clean_connections.json"), "utf8"));
    assert.equal(connections[0].shopify_access_token, "[redacted]");
    assert.equal(connections[0].klaviyo_private_key, "[redacted]");
    assert.equal(connections[0].shop_domain, MINE, "non-secret columns are still exported");

    // Nothing from the other store appears in any file.
    for (const name of manifest.files) {
      const contents = await fs.readFile(path.join(outDir, name), "utf8");
      assert.ok(!contents.includes(THEIRS), `${name} contains another store's data`);
    }
  } finally {
    await fs.rm(outDir, { recursive: true, force: true });
  }
});
