const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {
  buildEngineInputSnapshot,
  coverageFromDates,
  fetchedOrderCoverage,
  shopLocalNaive,
  snapshotToCsv,
} = require("../src/services/engineInputSnapshot");

const FIXTURE_DIR = path.join(__dirname, "fixtures");
const input = JSON.parse(fs.readFileSync(path.join(FIXTURE_DIR, "engineInput.sample.json"), "utf8"));

test("the normalized input matches the golden CSV", () => {
  // This golden started as the byte-for-byte output of the PRE-refactor
  // writeOrdersCsv. Every column still matches it — quoted cells, the embedded
  // newline, the synthetic line item for an order with none, null handling —
  // EXCEPT "Created at", which changed deliberately when the timestamp defect
  // was fixed. See the test below for what changed and why.
  const golden = fs.readFileSync(path.join(FIXTURE_DIR, "engineInput.sample.golden.csv"), "utf8");
  assert.equal(snapshotToCsv(buildEngineInputSnapshot(input)), golden);
});

test("dates are the shop's wall clock, not UTC and not the server's zone", () => {
  // The fixture shop is America/New_York. Order #1001 was placed at
  // 2026-01-04T09:30:00Z.
  //
  // Before the fix the CSV carried "2026-01-04T09:30:00.000Z" — and worse, that
  // instant was itself wrong, because the value had been stored with its offset
  // dropped and read back in whatever zone the API process ran in.
  //
  // Now it carries 04:30 — 09:30Z expressed in the store's own zone, with no
  // offset suffix, which is the shape a Shopify orders CSV export has and the
  // shape engine/tests/fixtures/synthetic/healthy_beauty_240d_orders.csv uses.
  // The engine buckets these into days, weeks and L7/L28/L56/L90 windows, and a
  // merchant's day is their store's day.
  const snapshot = buildEngineInputSnapshot(input);
  assert.equal(snapshot.timeZone, "America/New_York");
  assert.equal(snapshot.timeZoneSource, "shop");
  assert.equal(snapshot.orderRows[0]["Created at"], "2026-01-04T04:30:00");
  assert.ok(!snapshot.orderRows[0]["Created at"].endsWith("Z"), "no zone suffix; the engine expects naive local");

  // And DST is honoured rather than a fixed offset: January is EST (-5),
  // April is EDT (-4).
  assert.equal(snapshot.orderRows[2]["Created at"], "2026-04-14T14:05:00", "18:05Z in April is -4, not -5");
});

test("a shop with no usable time zone falls back to UTC, and says so", () => {
  const noZone = buildEngineInputSnapshot({ ...input, shop: { ...input.shop, iana_timezone: null } });
  assert.equal(noZone.timeZone, "UTC");
  assert.equal(noZone.timeZoneSource, "missing_fallback_utc");
  assert.equal(noZone.orderRows[0]["Created at"], "2026-01-04T09:30:00");

  const badZone = buildEngineInputSnapshot({ ...input, shop: { ...input.shop, iana_timezone: "Mars/Olympus" } });
  assert.equal(badZone.timeZone, "UTC");
  assert.equal(badZone.timeZoneSource, "invalid_fallback_utc", "an unusable zone is not silently treated as absent");
});

test("wall-clock formatting is independent of the process time zone", () => {
  // The whole defect was a value that changed meaning with the reader's zone.
  const instant = new Date("2026-01-04T09:30:00.000Z");
  assert.equal(shopLocalNaive(instant, "America/New_York"), "2026-01-04T04:30:00");
  assert.equal(shopLocalNaive(instant, "UTC"), "2026-01-04T09:30:00");
  assert.equal(shopLocalNaive(instant, "Asia/Kolkata"), "2026-01-04T15:00:00", "a half-hour offset");
  assert.equal(shopLocalNaive(instant, "Pacific/Auckland"), "2026-01-04T22:30:00");
});

test("the snapshot counts rows, not orders", () => {
  const snapshot = buildEngineInputSnapshot(input);
  assert.equal(snapshot.orderCount, 3);
  assert.equal(snapshot.rowCount, 4, "order 1001 has two line items");
  assert.equal(snapshot.shop.shop_domain, "fixture-shop.myshopify.com");
});

test("coverage is measured on instants, not on the zone-less CSV strings", () => {
  const { coverage } = buildEngineInputSnapshot(input);
  assert.equal(coverage.known, true);
  // Anchored on processed_at (Jan 4 → Jun 1), NOT the identical created_at
  // stamps every one of these rows carries from being API-imported. Reported as
  // true instants: re-parsing the CSV's naive strings would read them in
  // whatever zone the process runs in, which is the defect this fix removes.
  assert.equal(coverage.earliestOrderAt, "2026-01-04T09:30:00.000Z");
  assert.equal(coverage.latestOrderAt, "2026-06-01T12:00:00.000Z");
  assert.equal(coverage.daysCovered, 149);
});

test("undated orders yield unknown coverage, never zero days", () => {
  const coverage = coverageFromDates(["", "not a date"]);
  assert.equal(coverage.known, false);
  assert.equal(coverage.daysCovered, null);
  assert.equal(coverage.earliestOrderAt, null);
});

test("a single day of orders covers one day, not zero", () => {
  const coverage = coverageFromDates([
    "2026-03-01T01:00:00.000Z",
    "2026-03-01T23:00:00.000Z",
  ]);
  assert.equal(coverage.daysCovered, 1);
});

test("an empty store is unknown coverage, not a zero-day store", () => {
  const snapshot = buildEngineInputSnapshot({ shop: null, orders: [], order_line_items: [] });
  assert.equal(snapshot.rowCount, 0);
  assert.equal(snapshot.coverage.known, false);
  assert.equal(snapshotToCsv(snapshot).trim().split("\n").length, 1, "header only");
});

test("fetched coverage measures one fetch, not the accumulated tables", () => {
  // Same processed_at-first precedence as the normalized projection, so the two
  // numbers are directly comparable.
  const coverage = fetchedOrderCoverage([
    { processed_at: "2026-05-01T00:00:00.000Z", created_at: "2026-09-01T00:00:00.000Z" },
    { processed_at: "2026-05-30T00:00:00.000Z", created_at: "2026-09-01T00:00:00.000Z" },
    { created_at: "2026-05-15T00:00:00.000Z" },
  ]);
  assert.equal(coverage.known, true);
  assert.equal(coverage.earliestOrderAt, "2026-05-01T00:00:00.000Z");
  assert.equal(coverage.daysCovered, 30);
});

test("a fetch of undated orders is unknown coverage", () => {
  assert.equal(fetchedOrderCoverage([{ id: 1 }, { id: 2 }]).known, false);
  assert.equal(fetchedOrderCoverage([]).known, false);
});

// Residual records are no longer detected by date. A record absent from the
// fetch but dated inside the covered period is invisible to any range check, so
// the reconciliation is a membership query against the clean tables — see
// "the published input is the fetched generation, not the union" in
// syncService.integration.test.js.
