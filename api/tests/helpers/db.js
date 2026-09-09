// Integration tests run against a DISPOSABLE database named by
// TEST_DATABASE_URL, and skip entirely when it is unset — so `npm test` stays
// runnable with no database, and no test can ever be pointed at a real store's
// data by accident. Every test truncates the tables it touches first.
const TEST_DATABASE_URL = process.env.TEST_DATABASE_URL || "";

if (TEST_DATABASE_URL) process.env.DATABASE_URL = TEST_DATABASE_URL;
else process.env.DATABASE_URL = process.env.DATABASE_URL || "postgres://unused/unused";

const available = Boolean(TEST_DATABASE_URL);

const TABLES = [
  "clean.active_sync",
  "clean.campaign_measurements",
  "clean.campaign_recipients",
  "clean.campaigns",
  "clean.brand_email_active",
  "clean.brand_email_templates",
  "clean.engine_audiences",
  "clean.engine_run_snapshots",
  "clean.sync_runs",
  "clean.refunds",
  "clean.refunds_quarantine",
  "clean.orders_date_backup",
  "clean.order_line_items",
  "clean.orders",
  "clean.customers",
  "clean.product_variants",
  "clean.products",
  "clean.shop",
  "clean.connections",
  "raw.shopify_events",
];

async function resetDatabase() {
  const { query } = require("../../src/db");
  const { initSchema } = require("../../src/schema");
  await initSchema();
  await query(`TRUNCATE ${TABLES.join(", ")} RESTART IDENTITY CASCADE`);
}

async function closeDatabase() {
  const { pool } = require("../../src/db");
  await pool.end();
}

// A Shopify payload shaped like fetchShopifyData's return, including the fetch
// metadata a validation decision depends on.
function shopifyPayload({ orders = [], products = [], customers = [], truncated = false } = {}) {
  const meta = (resource, fetched) => ({
    resource, fetched, pages: 1,
    paginationExhausted: !truncated, truncated,
    requestedCap: truncated ? fetched : null,
  });
  return {
    shop: { id: 1, currency: "USD", iana_timezone: "UTC", plan_name: "basic" },
    orders, products, customers,
    resources: {
      shop: { resource: "shop", fetched: 1, pages: 1, paginationExhausted: true, requestedCap: null, truncated: false },
      orders: meta("orders", orders.length),
      products: meta("products", products.length),
      customers: meta("customers", customers.length),
    },
  };
}

// Orders covering EXACTLY `days` of history, ending today. Coverage is an
// inclusive span, so the oldest order sits `days - 1` back: ordersSpanning(90)
// produces a store whose declared coverage is 90, not 91.
// `idOffset` gives a fetch its own order ids. Reusing ids makes the next sync
// UPSERT over the same rows, which is the wrong shape for testing residue:
// residual rows are orders Shopify has STOPPED returning, so they necessarily
// carry ids the current fetch does not.
function ordersSpanning(days, count = 4, idOffset = 5000) {
  const now = Date.now();
  const span = Math.max(days - 1, 0);
  return Array.from({ length: count }, (_, i) => {
    const ageDays = Math.round((span * (count - 1 - i)) / Math.max(count - 1, 1));
    const at = new Date(now - ageDays * 86400000).toISOString();
    const id = idOffset + i;
    return {
      id, name: `#${id}`,
      created_at: at, processed_at: at,
      customer: { id: `cust-${i}` }, email: `c${i}@example.com`, currency: "USD",
      subtotal_price: "50.00", total_discounts: "0", total_price: "50.00", total_tax: "0",
      financial_status: "paid", test: false,
      line_items: [{ id: idOffset * 10 + i, title: "Serum", quantity: 1, price: "50.00", total_discount: "0" }],
    };
  });
}

module.exports = { available, closeDatabase, ordersSpanning, resetDatabase, shopifyPayload, TEST_DATABASE_URL };
