require("dotenv").config();

function required(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required env var: ${name}`);
  }
  return value;
}

const config = {
  port: Number(process.env.PORT || 4000),
  databaseUrl: required("DATABASE_URL"),
  apiBaseUrl: process.env.API_BASE_URL || `http://localhost:${Number(process.env.PORT || 4000)}/api`,
  webBaseUrl: process.env.WEB_BASE_URL || "http://localhost:5177",
  tokenEncryptionSecret: process.env.TOKEN_ENCRYPTION_SECRET || process.env.SESSION_SECRET || "beaconai-local-dev-secret",
  shopify: {
    shopDomain: process.env.SHOPIFY_SHOP_DOMAIN,
    accessToken: process.env.SHOPIFY_ACCESS_TOKEN,
    clientId: process.env.SHOPIFY_CLIENT_ID,
    clientSecret: process.env.SHOPIFY_CLIENT_SECRET,
    scopes: process.env.SHOPIFY_SCOPES || "read_products,read_customers,read_orders,write_orders",
    apiVersion: "2023-10",
  },
  klaviyo: {
    privateKey: process.env.KLAVIYO_PRIVATE_KEY,
    clientId: process.env.KLAVIYO_CLIENT_ID,
    clientSecret: process.env.KLAVIYO_CLIENT_SECRET,
    scopes: process.env.KLAVIYO_SCOPES || "accounts:read campaigns:read campaigns:write catalogs:read flows:read lists:write profiles:read profiles:write segments:read templates:read templates:write",
    revision: process.env.KLAVIYO_REVISION || "2026-04-15",
  },
};

module.exports = { config };
