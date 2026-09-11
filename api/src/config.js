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
  // Origins allowed to send the session cookie. A credentialed request is
  // refused by the browser against a wildcard origin, so this has to be an
  // explicit list — and an explicit list is what stops any site sending a
  // logged-in merchant's cookie to this API.
  corsOrigins: (process.env.CORS_ORIGINS || "")
    .split(",").map((origin) => origin.trim()).filter(Boolean),
  // Campaign assessment policy (RESULTS_UI_SPEC §6.2). Unset by default: the
  // floors and critical value await statistical review, and until all three
  // are set campaign results report descriptive figures with no comparison.
  campaignAssessmentPolicy: (() => {
    const minCustomersPerArm = Number(process.env.CAMPAIGN_ASSESSMENT_MIN_CUSTOMERS_PER_ARM);
    const minPurchasersPerArm = Number(process.env.CAMPAIGN_ASSESSMENT_MIN_PURCHASERS_PER_ARM);
    const criticalValue = Number(process.env.CAMPAIGN_ASSESSMENT_CRITICAL_VALUE);
    return [minCustomersPerArm, minPurchasersPerArm, criticalValue].every((v) => Number.isFinite(v) && v > 0)
      ? { minCustomersPerArm, minPurchasersPerArm, criticalValue }
      : null;
  })(),
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
    // Not read from the environment on purpose: a deployment has no reason to
    // talk to any other host. Tests point it at a local fake provider by
    // assigning to it directly.
    apiBaseUrl: "https://a.klaviyo.com/api",
  },
};

module.exports = { config };
