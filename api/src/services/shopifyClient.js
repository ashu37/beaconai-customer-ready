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

async function fetchPaginatedResource(client, resource, params, totalLimit) {
  const items = [];
  let path = `/${resource}.json?limit=${Math.min(totalLimit, 250)}${params ? `&${params}` : ""}`;

  while (path && items.length < totalLimit) {
    const response = await client.get(path);
    items.push(...(response.data[resource] || []));
    path = nextPagePath(response.headers?.link, resource);
  }

  return items.slice(0, totalLimit);
}

async function fetchShopifyData({ shopDomain, accessToken, limit, productStatus = "active" }) {
  const client = createShopifyClient(shopDomain, accessToken);
  const totalLimit = normalizeShopifyLimit(limit);
  const productStatusParam = productStatus ? `&status=${encodeURIComponent(productStatus)}` : "";

  const [shopRes, products, customers, orders] = await Promise.all([
    client.get("/shop.json"),
    fetchPaginatedResource(client, "products", productStatusParam.replace(/^&/, ""), totalLimit),
    fetchPaginatedResource(client, "customers", "", totalLimit),
    fetchPaginatedResource(client, "orders", "status=any", totalLimit),
  ]);

  return {
    shop: shopRes.data.shop,
    products,
    customers,
    orders,
  };
}

module.exports = {
  createShopifyClient,
  fetchShopifyData,
};
