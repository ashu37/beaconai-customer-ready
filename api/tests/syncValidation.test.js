const test = require("node:test");
const assert = require("node:assert/strict");

process.env.DATABASE_URL = process.env.DATABASE_URL || "postgres://unused/unused";

const {
  ALL_ORDERS_SCOPE,
  REQUIRED_COVERAGE_DAYS,
  declaredCoverage,
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
