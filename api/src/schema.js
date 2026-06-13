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
    CREATE TABLE IF NOT EXISTS clean.engine_runs (
      id SERIAL PRIMARY KEY,
      shop_domain TEXT NOT NULL,
      input JSONB NOT NULL,
      output JSONB NOT NULL,
      created_at TIMESTAMP DEFAULT NOW()
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
}

module.exports = { initSchema };
