const { query } = require("./db");

async function initSchema() {
  await query(`CREATE SCHEMA IF NOT EXISTS raw;`);
  await query(`CREATE SCHEMA IF NOT EXISTS clean;`);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.connections (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT UNIQUE NOT NULL,
      shopify_access_token TEXT,
      klaviyo_private_key TEXT,
      shopify_scope TEXT,
      klaviyo_access_token TEXT,
      klaviyo_refresh_token TEXT,
      klaviyo_scope TEXT,
      klaviyo_expires_at TIMESTAMP,
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
    );
  `);

  await query(`ALTER TABLE clean.connections ADD COLUMN IF NOT EXISTS shopify_scope TEXT;`);
  await query(`ALTER TABLE clean.connections ADD COLUMN IF NOT EXISTS klaviyo_access_token TEXT;`);
  await query(`ALTER TABLE clean.connections ADD COLUMN IF NOT EXISTS klaviyo_refresh_token TEXT;`);
  await query(`ALTER TABLE clean.connections ADD COLUMN IF NOT EXISTS klaviyo_scope TEXT;`);
  await query(`ALTER TABLE clean.connections ADD COLUMN IF NOT EXISTS klaviyo_expires_at TIMESTAMP;`);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.oauth_states (
      state TEXT PRIMARY KEY,
      provider TEXT NOT NULL,
      shop_domain TEXT,
      return_to TEXT,
      created_at TIMESTAMP DEFAULT NOW(),
      expires_at TIMESTAMP NOT NULL
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS raw.shopify_events (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      resource_type TEXT NOT NULL,
      payload JSONB NOT NULL,
      created_at TIMESTAMP DEFAULT NOW()
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS raw.klaviyo_events (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT,
      resource_type TEXT NOT NULL,
      payload JSONB NOT NULL,
      created_at TIMESTAMP DEFAULT NOW()
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.shop (
      shop_domain TEXT PRIMARY KEY,
      iana_timezone TEXT,
      currency TEXT,
      plan_name TEXT,
      raw JSONB,
      updated_at TIMESTAMP DEFAULT NOW()
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.orders (
      id TEXT PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      name TEXT,
      created_at TIMESTAMP,
      processed_at TIMESTAMP,
      customer_id TEXT,
      email TEXT,
      currency TEXT,
      subtotal_price NUMERIC,
      total_discounts NUMERIC,
      total_price NUMERIC,
      total_tax NUMERIC,
      total_shipping_price_set JSONB,
      financial_status TEXT,
      cancelled_at TIMESTAMP,
      test BOOLEAN,
      tags TEXT,
      raw JSONB
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.order_line_items (
      id TEXT PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      order_id TEXT NOT NULL,
      product_id TEXT,
      variant_id TEXT,
      sku TEXT,
      title TEXT,
      quantity INTEGER,
      price NUMERIC,
      total_discount NUMERIC,
      raw JSONB
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.customers (
      id TEXT PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      email TEXT,
      created_at TIMESTAMP,
      state TEXT,
      email_marketing_consent JSONB,
      tags TEXT,
      raw JSONB
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.products (
      id TEXT PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      title TEXT,
      product_type TEXT,
      tags TEXT,
      status TEXT,
      raw JSONB
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.product_variants (
      id TEXT PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      product_id TEXT NOT NULL,
      sku TEXT,
      price NUMERIC,
      inventory_item_id TEXT,
      inventory_quantity INTEGER,
      raw JSONB
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.refunds (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      order_id TEXT NOT NULL,
      created_at TIMESTAMP,
      line_item_id TEXT,
      quantity INTEGER,
      transaction_amount NUMERIC,
      raw JSONB
    );
  `);

  await query(`
    CREATE TABLE IF NOT EXISTS clean.klaviyo_assets (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT,
      asset_type TEXT NOT NULL,
      external_id TEXT,
      payload JSONB NOT NULL,
      created_at TIMESTAMP DEFAULT NOW()
    );
  `);

  // Engine runs are immutable: inserted once, never updated — except `narration`,
  // which is written once by the narration pass that follows the same run.
  // The container filesystem the engine writes to is ephemeral on Render, so
  // these rows (not `engine/data/`) are what survives a restart.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.engine_run_snapshots (
      run_id TEXT PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      store_id TEXT NOT NULL,
      schema_version TEXT,
      engine_run JSONB NOT NULL,
      manifest JSONB,
      narration JSONB,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);

  await query(`
    CREATE INDEX IF NOT EXISTS engine_run_snapshots_latest
      ON clean.engine_run_snapshots (shop_domain, created_at DESC);
  `);

  // Membership is stored whole, as the engine materialized it. An array rather
  // than a row per customer: a 100k audience is ~1.2MB here vs ~100k rows, and
  // it is always read in full at send time.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.engine_audiences (
      run_id TEXT NOT NULL
        REFERENCES clean.engine_run_snapshots(run_id) ON DELETE CASCADE,
      audience_definition_id TEXT NOT NULL,
      play_id TEXT NOT NULL,
      materialization_status TEXT NOT NULL,
      customer_ids TEXT[] NOT NULL DEFAULT '{}',
      PRIMARY KEY (run_id, audience_definition_id)
    );
  `);

  await query(`
    CREATE INDEX IF NOT EXISTS engine_audiences_play
      ON clean.engine_audiences (run_id, play_id);
  `);

  // A campaign is one play the merchant acted on, in one run. Rows outlive the
  // run that produced them: the engine emits a new slate every month, and the
  // record of what was sent has to survive that. Nothing here is ever deleted.
  //
  // Keyed (shop_domain, run_id, play_id) so approving the same play twice
  // updates one row instead of creating a second campaign for the same send.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.campaigns (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      run_id TEXT NOT NULL
        REFERENCES clean.engine_run_snapshots(run_id),
      play_id TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'draft',
      template_id TEXT,
      copy JSONB,
      holdout_pct NUMERIC(4,3) NOT NULL DEFAULT 0.100,
      audience_size INTEGER,
      holdout_size INTEGER,
      klaviyo_campaign_id TEXT,
      approved_at TIMESTAMPTZ,
      sent_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE (shop_domain, run_id, play_id)
    );
  `);

  // What the MERCHANT changed, kept apart from `copy` (what the model wrote).
  // The Copy step's Suggested/Edited badge exists only to tell those apart, and
  // "Restore suggested" works by deleting a merchant key so the field falls back
  // to the agent value. They also have different lifecycles: `copy` is replaced
  // wholesale when the model reruns, `draft_edits` has to survive that untouched.
  await query(`
    ALTER TABLE clean.campaigns
      ADD COLUMN IF NOT EXISTS draft_edits JSONB;
  `);

  await query(`
    CREATE INDEX IF NOT EXISTS campaigns_by_shop
      ON clean.campaigns (shop_domain, created_at DESC);
  `);

  // Which arm each customer landed in. Written at send time and never after —
  // without this row the campaign cannot be measured later, because there is no
  // other record of who was held back.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.campaign_recipients (
      campaign_id INTEGER NOT NULL
        REFERENCES clean.campaigns(id) ON DELETE CASCADE,
      customer_id TEXT NOT NULL,
      arm TEXT NOT NULL,
      PRIMARY KEY (campaign_id, customer_id)
    );
  `);

  await query(`
    CREATE INDEX IF NOT EXISTS campaign_recipients_arm
      ON clean.campaign_recipients (campaign_id, arm);
  `);

  // One row per campaign per window per arm. Recomputed as windows mature, so
  // this is the one table here that is updated rather than append-only.
  await query(`
    CREATE TABLE IF NOT EXISTS clean.campaign_measurements (
      campaign_id INTEGER NOT NULL
        REFERENCES clean.campaigns(id) ON DELETE CASCADE,
      window_days INTEGER NOT NULL,
      arm TEXT NOT NULL,
      n_customers INTEGER NOT NULL,
      n_orders INTEGER NOT NULL,
      revenue NUMERIC(12,2) NOT NULL,
      measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (campaign_id, window_days, arm)
    );
  `);

  // Sum of each customer's squared revenue. Storing this sufficient statistic
  // alongside the sum is what lets the interval be recomputed at read time
  // without re-scanning orders — and an estimate without an interval is the
  // thing this product exists not to publish.
  await query(`
    ALTER TABLE clean.campaign_measurements
      ADD COLUMN IF NOT EXISTS revenue_sq NUMERIC(18,4) NOT NULL DEFAULT 0;
  `);
}

module.exports = { initSchema };
