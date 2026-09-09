const axios = require("axios");
const { config } = require("../config");

function createShopifyClient(shopDomain, accessToken) {
  if (!shopDomain || !accessToken) {
    throw new Error("shopDomain and accessToken are required");
  }

  return axios.create({
    baseURL: `https://${shopDomain}/admin/api/${config.shopify.apiVersion}`,
    headers: {
      "X-Shopify-Access-Token": accessToken,
      "Content-Type": "application/json",
    },
    timeout: 30000,
  });
}

// Returns Infinity when no explicit finite limit is given, so the caller
// paginates the resource to completion (bounded only by Shopify's pages).
// A blank/null/"all" limit means "fetch everything" — not the legacy 250 cap.
function normalizeShopifyLimit(limit) {
  if (limit == null || limit === "" || limit === "all") return Infinity;
  const parsed = Number.parseInt(limit, 10);
  if (!Number.isFinite(parsed)) return Infinity;
  return Math.max(parsed, 1);
}

function nextPagePath(linkHeader, resource) {
  const link = String(linkHeader || "");
  const next = link.split(",").find((part) => part.includes('rel="next"'));
  const pageInfo = next?.match(/[?&]page_info=([^&>]+)/)?.[1];
  return pageInfo ? `/${resource}.json?limit=250&page_info=${pageInfo}` : null;
}

// Returns the items AND how they were obtained. The second half is the point:
// a caller cannot tell a store with 400 orders from a 400-capped fetch of a
// 40,000-order store by counting rows, and Ticket A exists because a truncated
// fetch that returns 200 OK is indistinguishable from a complete one.
//
//   paginationExhausted — Shopify stopped offering a next page. This is the
//                         only evidence that the resource was read to the end.
//   truncated           — we stopped early because `totalLimit` was reached
//                         while a next page was still on offer.
async function fetchPaginatedResource(client, resource, params, totalLimit) {
  const items = [];
  let path = `/${resource}.json?limit=${Math.min(totalLimit, 250)}${params ? `&${params}` : ""}`;
  let pages = 0;
  let paginationExhausted = false;

  while (path && items.length < totalLimit) {
    const response = await client.get(path);
    items.push(...(response.data[resource] || []));
    pages += 1;
    path = nextPagePath(response.headers?.link, resource);
    if (!path) paginationExhausted = true;
  }

  const capped = items.length > totalLimit;
  return {
    items: capped ? items.slice(0, totalLimit) : items,
    meta: {
      resource,
      fetched: capped ? totalLimit : items.length,
      pages,
      paginationExhausted,
      requestedCap: Number.isFinite(totalLimit) ? totalLimit : null,
      // A next page was still on offer when we stopped: rows exist that this
      // sync did not see.
      truncated: !paginationExhausted,
    },
  };
}

// `resources` is per-resource fetch metadata, keyed by resource name. Callers
// that only want the rows can keep destructuring shop/products/customers/orders
// and ignore it.
async function fetchShopifyData({ shopDomain, accessToken, limit, productStatus = "active" }) {
  const client = createShopifyClient(shopDomain, accessToken);
  const totalLimit = normalizeShopifyLimit(limit);
  const productStatusParam = productStatus ? `status=${encodeURIComponent(productStatus)}` : "";

  const [shopRes, products, customers, orders] = await Promise.all([
    client.get("/shop.json"),
    fetchPaginatedResource(client, "products", productStatusParam, totalLimit),
    fetchPaginatedResource(client, "customers", "", totalLimit),
    fetchPaginatedResource(client, "orders", "status=any", totalLimit),
  ]);

  return {
    shop: shopRes.data.shop,
    products: products.items,
    customers: customers.items,
    orders: orders.items,
    resources: {
      shop: { resource: "shop", fetched: shopRes.data.shop ? 1 : 0, pages: 1, paginationExhausted: true, requestedCap: null, truncated: false },
      products: products.meta,
      customers: customers.meta,
      orders: orders.meta,
    },
  };
}

module.exports = {
  createShopifyClient,
  fetchShopifyData,
  fetchPaginatedResource,
  normalizeShopifyLimit,
};
