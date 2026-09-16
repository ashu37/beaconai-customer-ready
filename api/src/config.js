require("dotenv").config();

// The development default. Public by definition (it is in this repository), so
// production refuses to start while any secret still falls back to it
// (secretsPolicy.js).
const DEV_SECRET = "beaconai-local-dev-secret";
const isProduction = process.env.NODE_ENV === "production";

function required(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required env var: ${name}`);
  }
  return value;
}

const config = {
  port: Number(process.env.PORT || 4000),
  // Runtime queries. In production this is the least-privilege application role
  // (no BYPASSRLS, owns nothing).
  databaseUrl: required("DATABASE_URL"),
  // Schema changes run as the table owner, separately. Unset in development,
  // where one role does both.
  migrationDatabaseUrl: process.env.MIGRATION_DATABASE_URL || null,
  // The role the grants and row-level-security policy are written for.
  appDbRole: process.env.APP_DB_ROLE || "beaconai_app",
  apiBaseUrl: process.env.API_BASE_URL || `http://localhost:${Number(process.env.PORT || 4000)}/api`,
  webBaseUrl: process.env.WEB_BASE_URL || "http://localhost:5177",
  // Origins allowed to send the session cookie. A credentialed request is
  // refused by the browser against a wildcard origin, so this has to be an
  // explicit list — and an explicit list is what stops any site sending a
  // logged-in merchant's cookie to this API.
  corsOrigins: (process.env.CORS_ORIGINS || "")
    .split(",").map((origin) => origin.trim()).filter(Boolean),
  // Campaign assessment policy. The states it gates are in
  // services/measurementService.js (assessWindow). Unset by default: the
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
  // Deadlines for the two Python subprocesses behind an analysis. Neither had
  // one: a stuck engine or a slow model call held the request, and the store's
  // analysis slot, indefinitely. Measured on Render free (2026-09-14): engine
  // ~152 s, narration ~60 s, so these leave wide headroom.
  engineTimeoutMs: Number(process.env.BEACONAI_ENGINE_TIMEOUT_MS) || 10 * 60 * 1000,
  narrationTimeoutMs: Number(process.env.BEACONAI_NARRATION_TIMEOUT_MS) || 5 * 60 * 1000,
  // Two secrets with two jobs. Sessions are signed with SESSION_SECRET, so
  // signing out every browser never touches stored integration tokens, which are
  // encrypted with TOKEN_ENCRYPTION_SECRET. They used to be one value.
  //
  // In production neither falls back to the other or to the development default:
  // secretsPolicy.js refuses to start instead. In development they fall back so
  // a fresh checkout runs.
  sessionSecret: process.env.SESSION_SECRET
    || (isProduction ? null : process.env.TOKEN_ENCRYPTION_SECRET || DEV_SECRET),
  tokenEncryptionSecret: process.env.TOKEN_ENCRYPTION_SECRET
    || (isProduction ? null : process.env.SESSION_SECRET || DEV_SECRET),
  // Read-only: tokens that still decrypt under the previous key keep working
  // while they are re-encrypted. Never used to encrypt.
  tokenEncryptionPreviousSecret: process.env.TOKEN_ENCRYPTION_SECRET_PREVIOUS || null,
  shopify: {
    shopDomain: process.env.SHOPIFY_SHOP_DOMAIN,
    accessToken: process.env.SHOPIFY_ACCESS_TOKEN,
    clientId: process.env.SHOPIFY_CLIENT_ID,
    clientSecret: process.env.SHOPIFY_CLIENT_SECRET,
    // What the app ASKS each store for at install. Full order history
    // (`read_all_orders`) is switched on by adding it here, via SHOPIFY_SCOPES,
    // once Shopify has approved it for the app; asking before approval would
    // fail the install. Nothing writes orders, so `write_orders` is not requested.
    scopes: process.env.SHOPIFY_SCOPES || "read_products,read_customers,read_orders",
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
    authorizeUrl: "https://www.klaviyo.com/oauth/authorize",
    tokenUrl: "https://a.klaviyo.com/oauth/token",
  },
};

module.exports = { config, DEV_SECRET };
