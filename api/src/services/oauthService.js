const crypto = require("crypto");
const axios = require("axios");
const { query } = require("../db");
const { config } = require("../config");

const SHOPIFY_HOST_RE = /^[a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com$/;

function requireOauthConfig(provider) {
  if (provider === "shopify") {
    if (!config.shopify.clientId || !config.shopify.clientSecret) {
      throw new Error("Shopify OAuth is missing SHOPIFY_CLIENT_ID or SHOPIFY_CLIENT_SECRET.");
    }
    return;
  }
  if (provider === "klaviyo") {
    if (!config.klaviyo.clientId || !config.klaviyo.clientSecret) {
      throw new Error("Klaviyo OAuth is missing KLAVIYO_CLIENT_ID or KLAVIYO_CLIENT_SECRET.");
    }
    return;
  }
  throw new Error(`Unsupported OAuth provider: ${provider}`);
}

function normalizeShopDomain(shop) {
  const value = String(shop || config.shopify.shopDomain || "").trim().toLowerCase();
  if (!SHOPIFY_HOST_RE.test(value)) {
    throw new Error("A valid Shopify shop domain like example.myshopify.com is required.");
  }
  return value;
}

function callbackUrl(provider) {
  return `${config.apiBaseUrl.replace(/\/$/, "")}/oauth/${provider}/callback`;
}

function successRedirect(provider, shopDomain) {
  const url = new URL(config.webBaseUrl);
  url.searchParams.set("connected", provider);
  if (shopDomain) url.searchParams.set("shop", shopDomain);
  return url.toString();
}

function encryptionKey() {
  return crypto.createHash("sha256").update(config.tokenEncryptionSecret).digest();
}

function encryptToken(value) {
  if (!value) return null;
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", encryptionKey(), iv);
  const encrypted = Buffer.concat([cipher.update(String(value), "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return `v1:${iv.toString("base64")}:${tag.toString("base64")}:${encrypted.toString("base64")}`;
}

function decryptToken(value) {
  if (!value) return null;
  if (!String(value).startsWith("v1:")) return value;
  const [, ivB64, tagB64, encryptedB64] = String(value).split(":");
  const decipher = crypto.createDecipheriv("aes-256-gcm", encryptionKey(), Buffer.from(ivB64, "base64"));
  decipher.setAuthTag(Buffer.from(tagB64, "base64"));
  return Buffer.concat([
    decipher.update(Buffer.from(encryptedB64, "base64")),
    decipher.final(),
  ]).toString("utf8");
}

async function createOauthState({ provider, shopDomain, returnTo }) {
  const state = crypto.randomBytes(24).toString("hex");
  await query(
    `INSERT INTO clean.oauth_states (state, provider, shop_domain, return_to, expires_at)
     VALUES ($1, $2, $3, $4, NOW() + INTERVAL '15 minutes')`,
    [state, provider, shopDomain || null, returnTo || null],
  );
  return state;
}

async function consumeOauthState({ state, provider }) {
  const result = await query(
    `DELETE FROM clean.oauth_states
     WHERE state = $1 AND provider = $2 AND expires_at > NOW()
     RETURNING state, provider, shop_domain, return_to`,
    [state, provider],
  );
  if (!result.rows[0]) {
    throw new Error("OAuth state is missing, expired, or already used.");
  }
  return result.rows[0];
}

function verifyShopifyHmac(queryParams) {
  const { hmac, signature, ...rest } = queryParams;
  if (!hmac) throw new Error("Shopify callback is missing hmac.");
  const message = Object.keys(rest)
    .sort()
    .map((key) => `${key}=${Array.isArray(rest[key]) ? rest[key].join(",") : rest[key]}`)
    .join("&");
  const digest = crypto
    .createHmac("sha256", config.shopify.clientSecret)
    .update(message)
    .digest("hex");
  const expected = Buffer.from(digest, "utf8");
  const actual = Buffer.from(String(hmac), "utf8");
  if (expected.length !== actual.length || !crypto.timingSafeEqual(expected, actual)) {
    throw new Error("Shopify hmac verification failed.");
  }
  return signature;
}

async function buildShopifyStartUrl({ shop, returnTo }) {
  requireOauthConfig("shopify");
  const shopDomain = normalizeShopDomain(shop);
  const state = await createOauthState({ provider: "shopify", shopDomain, returnTo });
  const url = new URL(`https://${shopDomain}/admin/oauth/authorize`);
  url.searchParams.set("client_id", config.shopify.clientId);
  url.searchParams.set("scope", config.shopify.scopes);
  url.searchParams.set("redirect_uri", callbackUrl("shopify"));
  url.searchParams.set("state", state);
  return url.toString();
}

async function handleShopifyCallback(queryParams) {
  requireOauthConfig("shopify");
  verifyShopifyHmac(queryParams);
  const shopDomain = normalizeShopDomain(queryParams.shop);
  const state = await consumeOauthState({ state: queryParams.state, provider: "shopify" });
  if (state.shop_domain && state.shop_domain !== shopDomain) {
    throw new Error("Shopify callback shop does not match the OAuth state.");
  }
  if (!queryParams.code) {
    throw new Error("Shopify callback is missing code.");
  }

  const response = await axios.post(`https://${shopDomain}/admin/oauth/access_token`, {
    client_id: config.shopify.clientId,
    client_secret: config.shopify.clientSecret,
    code: queryParams.code,
  });

  const accessToken = response.data.access_token;
  if (!accessToken) throw new Error("Shopify did not return an access token.");
  await query(
    `INSERT INTO clean.connections (shop_domain, shopify_access_token, shopify_scope, updated_at)
     VALUES ($1, $2, $3, NOW())
     ON CONFLICT (shop_domain)
     DO UPDATE SET shopify_access_token = EXCLUDED.shopify_access_token,
       shopify_scope = EXCLUDED.shopify_scope,
       updated_at = NOW()`,
    [shopDomain, encryptToken(accessToken), response.data.scope || config.shopify.scopes],
  );

  return {
    provider: "shopify",
    shopDomain,
    redirectTo: state.return_to || successRedirect("shopify", shopDomain),
  };
}

/**
 * @param {object} options
 * @param {string} options.shopDomain  the AUTHENTICATED shop. Not a name from
 *   the query: completing this flow writes credentials against whatever shop the
 *   state carries, so accepting an arbitrary one let anybody overwrite another
 *   store's Klaviyo connection by starting the flow with that store's name.
 *
 * Shopify's start route stays public — it is how a merchant signs in, and there
 * is no session to require yet. Connecting Klaviyo is something an
 * already-signed-in merchant does, so there always is one.
 */
async function buildKlaviyoStartUrl({ shopDomain: authorizedShopDomain, returnTo }) {
  // Checked BEFORE the config: an unauthenticated caller should be told to sign
  // in, not told which environment variables this deployment is missing.
  if (!authorizedShopDomain) throw new Error("An authenticated shop is required to connect Klaviyo.");
  requireOauthConfig("klaviyo");
  const shopDomain = normalizeShopDomain(authorizedShopDomain);
  const state = await createOauthState({ provider: "klaviyo", shopDomain, returnTo });
  const url = new URL("https://www.klaviyo.com/oauth/authorize");
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", config.klaviyo.clientId);
  url.searchParams.set("redirect_uri", callbackUrl("klaviyo"));
  url.searchParams.set("scope", config.klaviyo.scopes);
  url.searchParams.set("state", state);
  return url.toString();
}

async function handleKlaviyoCallback(queryParams) {
  requireOauthConfig("klaviyo");
  const state = await consumeOauthState({ state: queryParams.state, provider: "klaviyo" });
  if (!queryParams.code) {
    throw new Error("Klaviyo callback is missing code.");
  }

  const form = new URLSearchParams();
  form.set("grant_type", "authorization_code");
  form.set("code", queryParams.code);
  form.set("redirect_uri", callbackUrl("klaviyo"));

  const basic = Buffer.from(`${config.klaviyo.clientId}:${config.klaviyo.clientSecret}`).toString("base64");
  const response = await axios.post("https://a.klaviyo.com/oauth/token", form.toString(), {
    headers: {
      Authorization: `Basic ${basic}`,
      "Content-Type": "application/x-www-form-urlencoded",
      revision: config.klaviyo.revision,
    },
  });

  const accessToken = response.data.access_token;
  if (!accessToken) throw new Error("Klaviyo did not return an access token.");
  const expiresIn = Number(response.data.expires_in || 0);
  const shopDomain = state.shop_domain || config.shopify.shopDomain || "unknown.myshopify.com";

  await query(
    `INSERT INTO clean.connections (
       shop_domain,
       klaviyo_access_token,
       klaviyo_refresh_token,
       klaviyo_scope,
       klaviyo_expires_at,
       updated_at
     )
     VALUES ($1, $2, $3, $4, NOW() + ($5 || ' seconds')::INTERVAL, NOW())
     ON CONFLICT (shop_domain)
     DO UPDATE SET klaviyo_access_token = EXCLUDED.klaviyo_access_token,
       klaviyo_refresh_token = EXCLUDED.klaviyo_refresh_token,
       klaviyo_scope = EXCLUDED.klaviyo_scope,
       klaviyo_expires_at = EXCLUDED.klaviyo_expires_at,
       updated_at = NOW()`,
    [
      shopDomain,
      encryptToken(accessToken),
      encryptToken(response.data.refresh_token),
      response.data.scope || config.klaviyo.scopes,
      Number.isFinite(expiresIn) && expiresIn > 0 ? expiresIn : 3600,
    ],
  );

  return {
    provider: "klaviyo",
    shopDomain,
    redirectTo: state.return_to || successRedirect("klaviyo", shopDomain),
  };
}

async function getConnection(shopDomain) {
  const result = await query(
    `SELECT shop_domain,
       shopify_access_token,
       shopify_scope,
       klaviyo_private_key,
       klaviyo_access_token,
       klaviyo_refresh_token,
       klaviyo_scope,
       klaviyo_expires_at,
       updated_at
     FROM clean.connections
     WHERE shop_domain = $1`,
    [shopDomain],
  );
  return result.rows[0] || null;
}

async function getConnectionStatus(shopDomain) {
  const row = await getConnection(shopDomain);
  return {
    shopDomain,
    shopify: {
      connected: Boolean(row?.shopify_access_token || config.shopify.accessToken),
      source: row?.shopify_access_token ? "oauth" : config.shopify.accessToken ? "env" : "none",
      scopes: row?.shopify_scope || config.shopify.scopes || null,
    },
    klaviyo: {
      connected: Boolean(row?.klaviyo_access_token || row?.klaviyo_private_key || config.klaviyo.privateKey),
      source: row?.klaviyo_access_token ? "oauth" : row?.klaviyo_private_key || config.klaviyo.privateKey ? "api_key" : "none",
      scopes: row?.klaviyo_scope || null,
      expiresAt: row?.klaviyo_expires_at || null,
    },
  };
}

// The env-configured credentials belong to ONE shop — the deployment's own
// configured store — and to no other. Falling back to them for any shop that
// had none of its own meant a session for an unconnected store reached the
// provider with the global account's key and read its data back.
//
// A shop with no stored credential now gets null, and the caller surfaces "not
// connected" rather than someone else's account.
function ownsGlobalCredentials(shopDomain) {
  return Boolean(config.shopify.shopDomain) && shopDomain === config.shopify.shopDomain;
}

async function resolveStoredShopifyToken(shopDomain) {
  const row = await getConnection(shopDomain);
  const stored = decryptToken(row?.shopify_access_token);
  if (stored) return stored;
  return ownsGlobalCredentials(shopDomain) ? config.shopify.accessToken : null;
}

async function resolveStoredKlaviyoToken(shopDomain) {
  const row = await getConnection(shopDomain);
  if (row?.klaviyo_access_token) {
    const expiresAt = row.klaviyo_expires_at ? new Date(row.klaviyo_expires_at).getTime() : 0;
    const refreshToken = decryptToken(row.klaviyo_refresh_token);
    const shouldRefresh = refreshToken && expiresAt && expiresAt < Date.now() + 120000;
    if (shouldRefresh) {
      const form = new URLSearchParams();
      form.set("grant_type", "refresh_token");
      form.set("refresh_token", refreshToken);
      const basic = Buffer.from(`${config.klaviyo.clientId}:${config.klaviyo.clientSecret}`).toString("base64");
      const response = await axios.post("https://a.klaviyo.com/oauth/token", form.toString(), {
        headers: {
          Authorization: `Basic ${basic}`,
          "Content-Type": "application/x-www-form-urlencoded",
          revision: config.klaviyo.revision,
        },
      });
      const nextAccessToken = response.data.access_token;
      if (nextAccessToken) {
        const expiresIn = Number(response.data.expires_in || 3600);
        await query(
          `UPDATE clean.connections
           SET klaviyo_access_token = $2,
             klaviyo_refresh_token = COALESCE($3, klaviyo_refresh_token),
             klaviyo_expires_at = NOW() + ($4 || ' seconds')::INTERVAL,
             updated_at = NOW()
           WHERE shop_domain = $1`,
          [
            shopDomain,
            encryptToken(nextAccessToken),
            response.data.refresh_token ? encryptToken(response.data.refresh_token) : null,
            Number.isFinite(expiresIn) && expiresIn > 0 ? expiresIn : 3600,
          ],
        );
        return nextAccessToken;
      }
    }
    return decryptToken(row.klaviyo_access_token);
  }
  if (row?.klaviyo_private_key) return row.klaviyo_private_key;
  // Same rule: the configured key is the configured shop's, not a default for
  // whoever asks.
  return ownsGlobalCredentials(shopDomain) ? config.klaviyo.privateKey : null;
}

module.exports = {
  ownsGlobalCredentials,
  buildShopifyStartUrl,
  handleShopifyCallback,
  buildKlaviyoStartUrl,
  handleKlaviyoCallback,
  getConnectionStatus,
  resolveStoredShopifyToken,
  resolveStoredKlaviyoToken,
};
