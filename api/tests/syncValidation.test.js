const test = require("node:test");
const assert = require("node:assert/strict");

process.env.DATABASE_URL = process.env.DATABASE_URL || "postgres://unused/unused";

const {
  ALL_ORDERS_SCOPE,
  REQUIRED_COVERAGE_DAYS,
  declaredCoverage,
  historyAccess,
  validateCoverage,
  validateFetch,
} = require("../src/services/syncService");

function fetchResult({ truncated = false, orders = 1, shop = { id: 1 } } = {}) {
  const meta = (resource) => ({
    resource, fetched: 250, pages: 1, requestedCap: truncated ? 250 : null,
    paginationExhausted: !truncated, truncated,
  });
  return {
    shop,
    orders: Array.from({ length: orders }, (_, i) => ({ id: i })),
    resources: { shop: meta("shop"), orders: meta("orders"), customers: meta("customers"), products: meta("products") },
  };
}

function codes(failures) {
  return failures.map((f) => f.code);
}

test("a complete fetch raises nothing", () => {
  assert.deepEqual(codes(validateFetch(fetchResult(), null).failures), []);
});

test("a truncated resource is a validation failure naming the resource", () => {
  const { failures } = validateFetch(fetchResult({ truncated: true }), 250);
  assert.ok(codes(failures).includes("resource_truncated"));
  const orders = failures.find((f) => f.resource === "orders");
  assert.equal(orders.requestedCap, 250);
  assert.match(orders.message, /more pages available/);
});

test("a store with no orders cannot be analysed", () => {
  const { failures } = validateFetch(fetchResult({ orders: 0 }), null);
  assert.ok(codes(failures).includes("no_orders"));
});

test("a missing shop record is a validation failure", () => {
  const { failures } = validateFetch(fetchResult({ shop: null }), null);
  assert.ok(codes(failures).includes("shop_missing"));
});

test("coverage at or above the engine's requirement passes", () => {
  assert.deepEqual(validateCoverage({ known: true, daysCovered: REQUIRED_COVERAGE_DAYS }, "read_orders"), []);
  assert.deepEqual(validateCoverage({ known: true, daysCovered: 400 }, "read_orders"), []);
});

test("coverage below the engine's requirement blocks", () => {
  const failures = validateCoverage({ known: true, daysCovered: 30 }, `read_orders,${ALL_ORDERS_SCOPE}`);
  assert.deepEqual(codes(failures), ["coverage_below_required"]);
  assert.equal(failures[0].daysCovered, 30);
  assert.equal(failures[0].requiredDays, REQUIRED_COVERAGE_DAYS);
  assert.equal(failures[0].likelyScopeCeiling, false, "the scope was granted; the store really is young");
});

test("short coverage at Shopify's 60-day ceiling names the missing scope", () => {
  // The distinction that matters to a merchant: "your store is new" and "we are
  // not allowed to read your history" look identical in the data.
  const failures = validateCoverage({ known: true, daysCovered: 60 }, "read_orders,read_customers");
  assert.equal(failures[0].likelyScopeCeiling, true);
  assert.equal(failures[0].missingScope, ALL_ORDERS_SCOPE);
  assert.match(failures[0].message, /read_all_orders/);
});

test("unknown coverage blocks and is not reported as zero", () => {
  const failures = validateCoverage({ known: false, daysCovered: null }, "read_orders");
  assert.deepEqual(codes(failures), ["coverage_unknown"]);
  assert.match(failures[0].message, /unknown/);
});

test("declared coverage records what was permitted, not only what was seen", () => {
  const granted = declaredCoverage({ known: true, daysCovered: 200 }, `read_orders,${ALL_ORDERS_SCOPE}`);
  assert.equal(granted.meetsRequired, true);
  assert.equal(granted.meetsPreferred, true);
  assert.equal(granted.grantedAllOrdersScope, true);

  const unknownScope = declaredCoverage({ known: true, daysCovered: 200 }, null);
  assert.equal(unknownScope.grantedAllOrdersScope, null, "no scope string is unknown, not false");

  const shallow = declaredCoverage({ known: true, daysCovered: 120 }, "read_orders");
  assert.equal(shallow.meetsRequired, true);
  assert.equal(shallow.meetsPreferred, false);
});

const { fetchedOrderCreatedCoverage } = require("../src/services/engineInputSnapshot");

test("a store is told to reconnect only when the app asks for full history and its token lacks it", () => {
  const asks = "read_products,read_customers,read_orders,read_all_orders";
  const doesNotAsk = "read_products,read_customers,read_orders";

  assert.deepEqual(historyAccess({ requestedScopes: asks, grantedScope: "read_products,read_orders" }),
    { requested: true, granted: false, reconnectRequired: true });
  assert.deepEqual(historyAccess({ requestedScopes: asks, grantedScope: "read_orders,read_all_orders" }),
    { requested: true, granted: true, reconnectRequired: false });
  // Before Shopify approves the scope the app does not ask for it, and a
  // reconnect could not grant it, so nobody is sent round in a loop.
  assert.equal(historyAccess({ requestedScopes: doesNotAsk, grantedScope: "read_orders" }).reconnectRequired, false);
  // A token whose scopes are unknown (environment token, or granted before scopes
  // were stored) is not assumed to be missing it.
  assert.deepEqual(historyAccess({ requestedScopes: asks, grantedScope: null }),
    { requested: true, granted: null, reconnectRequired: false });
});

test("the 60-day hint is judged on created_at, the date Shopify's window uses", () => {
  // Orders processed over 85 days but created within the last 60: the window cut them.
  const processed85 = { known: true, daysCovered: 85 };
  const created60 = { known: true, daysCovered: 60 };
  const ceiling = validateCoverage(processed85, "read_orders", { createdCoverage: created60, appRequestsAllOrders: true });
  assert.equal(ceiling[0].likelyScopeCeiling, true);
  assert.equal(ceiling[0].missingScope, ALL_ORDERS_SCOPE);
  assert.equal(ceiling[0].action, "reconnect_shopify");

  // A young store: 60 days by processed_at, but everything was created in the last 20.
  const young = validateCoverage({ known: true, daysCovered: 60 }, "read_orders", { createdCoverage: { known: true, daysCovered: 20 }, appRequestsAllOrders: true });
  assert.equal(young[0].likelyScopeCeiling, false, "nothing sits at the window's edge");
  assert.equal(young[0].action, null);

  // The scope was granted: short history is the store's, not the window's.
  const granted = validateCoverage(processed85, `read_orders,${ALL_ORDERS_SCOPE}`, { createdCoverage: created60, appRequestsAllOrders: true });
  assert.equal(granted[0].likelyScopeCeiling, false);

  // The app does not ask for the scope yet: explained, but reconnect is not offered.
  const notRequested = validateCoverage(processed85, "read_orders", { createdCoverage: created60, appRequestsAllOrders: false });
  assert.equal(notRequested[0].likelyScopeCeiling, true);
  assert.equal(notRequested[0].action, null);
});

test("created_at coverage ignores processed_at", () => {
  const coverage = fetchedOrderCreatedCoverage([
    { created_at: "2026-07-15T10:00:00Z", processed_at: "2026-01-01T10:00:00Z" },
    { created_at: "2026-07-17T10:00:00Z", processed_at: "2026-07-17T10:00:00Z" },
  ]);
  assert.equal(coverage.daysCovered, 3);
  assert.equal(coverage.earliestOrderAt, "2026-07-15T10:00:00.000Z");
});
