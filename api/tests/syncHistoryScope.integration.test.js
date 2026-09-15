const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { config } = require("../src/config");
const { startApi } = require("./helpers/httpApp");
const { buildShopifyStartUrl } = require("../src/services/oauthService");

// Blocker 2: a store whose Shopify token lacks read_all_orders is asked to
// reconnect BEFORE a sync fetches anything, once the app requests that scope.
const SHOP = "history-scope.myshopify.com";
const ASKS = "read_products,read_customers,read_orders,read_all_orders";

let api;
const originalScopes = config.shopify.scopes;
test.before(async () => { if (db.available) api = await startApi(); });
test.after(async () => {
  config.shopify.scopes = originalScopes;
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

async function connect(grantedScope) {
  await query(
    `INSERT INTO clean.connections (shop_domain, shopify_access_token, shopify_scope)
     VALUES ($1, 'shpat_test', $2)`,
    [SHOP, grantedScope]
  );
}

const syncRuns = async () => (await query(`SELECT count(*)::int AS n FROM clean.sync_runs WHERE shop_domain = $1`, [SHOP])).rows[0].n;

suite("a store without full-history access is asked to reconnect instead of syncing", async () => {
  await db.resetDatabase();
  config.shopify.scopes = ASKS;
  await connect("read_products,read_customers,read_orders");

  const response = await api.post("/sync/shopify", { shopDomain: SHOP });
  assert.equal(response.status, 200);
  assert.equal(response.body.published, false);
  assert.equal(response.body.status, "reconnect_required");
  assert.equal(response.body.validationFailures[0].code, "reconnect_for_history");
  assert.equal(response.body.validationFailures[0].action, "reconnect_shopify");
  assert.equal(await syncRuns(), 0, "nothing was fetched or recorded");

  // Settings learns the same thing, so the merchant can reconnect before syncing.
  const status = await api.get(`/connections/status?shopDomain=${SHOP}`);
  assert.equal(status.body.status.shopify.history.reconnectRequired, true);

  // Reconnecting goes through the install URL, which asks for the scope, so it can grant it.
  const saved = { clientId: config.shopify.clientId, clientSecret: config.shopify.clientSecret };
  Object.assign(config.shopify, { clientId: "client", clientSecret: "secret" });
  try {
    const url = new URL(await buildShopifyStartUrl({ shop: SHOP, browserNonce: "browser-nonce-1" }));
    assert.ok(url.searchParams.get("scope").split(",").includes("read_all_orders"));
  } finally {
    Object.assign(config.shopify, saved);
  }
});

// When the app does not ask for the scope, or the store granted it, the route
// goes on to a real fetch — historyAccess covers those decisions without
// reaching Shopify (syncValidation.test.js).
