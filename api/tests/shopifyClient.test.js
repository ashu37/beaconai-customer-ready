const test = require("node:test");
const assert = require("node:assert/strict");

process.env.DATABASE_URL = process.env.DATABASE_URL || "postgres://unused/unused";

const { fetchPaginatedResource, normalizeShopifyLimit } = require("../src/services/shopifyClient");
const { fakePagedClient, items } = require("./helpers/fakeShopify");

test("a cap that stops mid-resource is reported as truncated", async () => {
  // 3 pages of 100 available, but the caller asked for 150.
  const client = fakePagedClient({ orders: [items(100), items(100, 100), items(100, 200)] });
  const { items: rows, meta } = await fetchPaginatedResource(client, "orders", "", 150);

  assert.equal(rows.length, 150);
  assert.equal(meta.truncated, true, "a next page was still on offer when we stopped");
  assert.equal(meta.paginationExhausted, false);
  assert.equal(meta.requestedCap, 150);
});

test("reading a resource to the end reports exhausted, not truncated", async () => {
  const client = fakePagedClient({ orders: [items(250), items(250, 250), items(7, 500)] });
  const { items: rows, meta } = await fetchPaginatedResource(client, "orders", "", Infinity);

  assert.equal(rows.length, 507);
  assert.equal(meta.paginationExhausted, true);
  assert.equal(meta.truncated, false);
  assert.equal(meta.requestedCap, null);
  assert.equal(meta.pages, 3);
});

test("a cap that happens to equal the store's size is still not exhausted", async () => {
  // The trap this whole ticket exists for: 250 rows fetched, 250 rows in the
  // store — indistinguishable by row count, distinguishable by Link header.
  const capped = fakePagedClient({ orders: [items(250), items(250, 250)] });
  const { meta: cappedMeta } = await fetchPaginatedResource(capped, "orders", "", 250);
  assert.equal(cappedMeta.truncated, true);

  const whole = fakePagedClient({ orders: [items(250)] });
  const { meta: wholeMeta } = await fetchPaginatedResource(whole, "orders", "", 250);
  assert.equal(wholeMeta.truncated, false);
  assert.equal(wholeMeta.paginationExhausted, true);
});

test("a failing page rejects rather than returning a short list", async () => {
  const client = fakePagedClient(
    { orders: [items(250), items(250, 250), items(250, 500)] },
    { failOnPage: { resource: "orders", page: 1 } }
  );
  await assert.rejects(
    () => fetchPaginatedResource(client, "orders", "", Infinity),
    /orders page 1 failed/
  );
});

test("an absent limit means fetch everything, not the legacy 250", () => {
  assert.equal(normalizeShopifyLimit(undefined), Infinity);
  assert.equal(normalizeShopifyLimit(null), Infinity);
  assert.equal(normalizeShopifyLimit(""), Infinity);
  assert.equal(normalizeShopifyLimit("all"), Infinity);
  assert.equal(normalizeShopifyLimit("300"), 300);
  assert.equal(normalizeShopifyLimit(0), 1);
});
