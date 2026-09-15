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

/**
 * Where a completed connection may send the browser: a path on this app, or a
 * URL on the configured web origin. Anything else — another site, a
 * protocol-relative `//host`, a `javascript:` URL — is dropped for the default
 * success page, so a crafted start link cannot turn sign-in into a redirect to a
 * look-alike site.
 */
function safeReturnTo(value) {
  if (!value || typeof value !== "string") return null;
  const raw = value.trim();
  let webOrigin;
  try {
    webOrigin = new URL(config.webBaseUrl).origin;
  } catch (_) {
    return null;
  }
  if (raw.startsWith("/")) {
    if (raw.startsWith("//") || raw.startsWith("/\\")) return null;
    try {
      const resolved = new URL(raw, webOrigin);
      return resolved.origin === webOrigin ? resolved.toString() : null;
    } catch (_) {
      return null;
    }
  }
  try {
    const url = new URL(raw);
    return url.origin === webOrigin && /^https?:$/.test(url.protocol) ? url.toString() : null;
  } catch (_) {
    return null;
  }
}

// The browser that started a connection holds a random nonce in a short-lived
// cookie; the state row holds only its hash.
const OAUTH_BROWSER_COOKIE = "beaconai_oauth";
const OAUTH_BROWSER_TTL_SECONDS = 15 * 60;

function newBrowserNonce() {
  return crypto.randomBytes(24).toString("base64url");
}

function hashBrowserNonce(nonce) {
  return crypto.createHash("sha256").update(String(nonce)).digest("hex");
}

function browserCookieAttributes(maxAge) {
  const secure = /^https:/i.test(config.apiBaseUrl || config.webBaseUrl || "") ? "; Secure" : "";
  return `Path=/api/oauth; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${secure}`;
}

function oauthBrowserCookie(nonce) {
  return `${OAUTH_BROWSER_COOKIE}=${encodeURIComponent(nonce)}; ${browserCookieAttributes(OAUTH_BROWSER_TTL_SECONDS)}`;
}

function clearOauthBrowserCookie() {
  return `${OAUTH_BROWSER_COOKIE}=; ${browserCookieAttributes(0)}`;
}

function successRedirect(provider, shopDomain) {
  const url = new URL(config.webBaseUrl);
  url.searchParams.set("connected", provider);
  if (shopDomain) url.searchParams.set("shop", shopDomain);
  return url.toString();
}

// Token encryption lives in tokenCrypto.js (keyring, separate from session
// signing). Re-exported below for existing callers.
const { decryptToken, encryptToken } = require("./tokenCrypto");
const { reactivateAfterReinstall } = require("./storeAccessService");

// The address Shopify calls when the app is uninstalled, subscribed per store
// after install. Compliance topics are configured in the app settings instead.
function webhookAddress() {
  return `${config.apiBaseUrl.replace(/\/$/, "")}/webhooks/shopify`;
}

async function registerUninstallWebhook(shopDomain, accessToken) {
  const url = `https://${shopDomain}/admin/api/${config.shopify.apiVersion}/webhooks.json`;
  try {
    await axios.post(url, {
      webhook: { topic: "app/uninstalled", address: webhookAddress(), format: "json" },
    }, { headers: { "X-Shopify-Access-Token": accessToken, "Content-Type": "application/json" }, timeout: 10000 });
  } catch (error) {
    // 422 "address for this topic has already been taken": already subscribed.
    if (error.response?.status === 422) return;
    throw error;
  }
}

// PKCE (RFC 7636), which Klaviyo requires. A fresh verifier per authorization
// request, 43-128 characters of high entropy: 32 random bytes in base64url are
// 43. The challenge is its SHA-256, and only the challenge travels through the
// browser — so an authorization code intercepted there cannot be exchanged
// without the verifier, which never leaves this server.
function createPkcePair() {
  const codeVerifier = crypto.randomBytes(32).toString("base64url");
  const codeChallenge = crypto.createHash("sha256").update(codeVerifier).digest("base64url");
  return { codeVerifier, codeChallenge };
}

async function createOauthState({ provider, shopDomain, returnTo, browserNonce, pkce = false }) {
  if (!browserNonce) throw new Error("An OAuth flow must be bound to the browser that starts it.");
  // Abandoned attempts expire but were never deleted, so the table only grew,
  // each row holding an encrypted verifier. Swept here, an hour past expiry, on
  // the path that creates them.
  await query(`DELETE FROM clean.oauth_states WHERE expires_at < NOW() - INTERVAL '1 hour'`).catch(() => {});
  const state = crypto.randomBytes(24).toString("hex");
  const { codeVerifier, codeChallenge } = pkce ? createPkcePair() : {};
  await query(
    `INSERT INTO clean.oauth_states (state, provider, shop_domain, return_to, code_verifier, browser_hash, expires_at)
     VALUES ($1, $2, $3, $4, $5, $6, NOW() + INTERVAL '15 minutes')`,
    [
      state, provider, shopDomain || null, safeReturnTo(returnTo),
      codeVerifier ? encryptToken(codeVerifier) : null, hashBrowserNonce(browserNonce),
    ],
  );
  return { state, codeChallenge: codeChallenge || null };
}

// Consumed only by the browser that started it. A callback carrying a valid
// state but no matching nonce leaves the row in place (so the real browser can
// still finish) and fails — the case where someone else's callback link is
// opened in this browser.
async function consumeOauthState({ state, provider, browserNonce }) {
  if (!state || !browserNonce) {
    throw new Error("OAuth state is missing, expired, already used, or from another browser.");
  }
  const result = await query(
    `DELETE FROM clean.oauth_states
     WHERE state = $1 AND provider = $2 AND expires_at > NOW()
       AND browser_hash IS NOT NULL AND browser_hash = $3
     RETURNING state, provider, shop_domain, return_to, code_verifier`,
    [state, provider, hashBrowserNonce(browserNonce)],
  );
  if (!result.rows[0]) {
    throw new Error("OAuth state is missing, expired, already used, or from another browser.");
  }
  const row = result.rows[0];
  return { ...row, code_verifier: decryptToken(row.code_verifier) };
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

async function buildShopifyStartUrl({ shop, returnTo, browserNonce }) {
  requireOauthConfig("shopify");
  const shopDomain = normalizeShopDomain(shop);
  // No PKCE: Shopify's authorization-code flow does not accept a challenge.
  const { state } = await createOauthState({ provider: "shopify", shopDomain, returnTo, browserNonce });
  const url = new URL(`https://${shopDomain}/admin/oauth/authorize`);
  url.searchParams.set("client_id", config.shopify.clientId);
  url.searchParams.set("scope", config.shopify.scopes);
  url.searchParams.set("redirect_uri", callbackUrl("shopify"));
  url.searchParams.set("state", state);
  return url.toString();
}

async function handleShopifyCallback(queryParams, { browserNonce } = {}) {
  requireOauthConfig("shopify");
  verifyShopifyHmac(queryParams);
  const shopDomain = normalizeShopDomain(queryParams.shop);
  const state = await consumeOauthState({ state: queryParams.state, provider: "shopify", browserNonce });
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

  // A reinstall lifts an uninstall block; a founder disable is not lifted by the
  // merchant signing in, and no session is issued for it (routes.js checks).
  await reactivateAfterReinstall(shopDomain);
  // So an uninstall reaches us. Best effort: a failure here must not fail the
  // sign-in, and is logged without the token.
  await registerUninstallWebhook(shopDomain, accessToken).catch((error) => {
    console.error(`[oauth] could not register app/uninstalled for ${shopDomain}: ${error.response?.status || error.message}`);
  });

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
async function buildKlaviyoStartUrl({ shopDomain: authorizedShopDomain, returnTo, browserNonce }) {
  // Checked BEFORE the config: an unauthenticated caller should be told to sign
  // in, not told which environment variables this deployment is missing.
  if (!authorizedShopDomain) throw new Error("An authenticated shop is required to connect Klaviyo.");
  requireOauthConfig("klaviyo");
  const shopDomain = normalizeShopDomain(authorizedShopDomain);
  const { state, codeChallenge } = await createOauthState({
    provider: "klaviyo", shopDomain, returnTo, browserNonce, pkce: true,
  });
  const url = new URL(config.klaviyo.authorizeUrl);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", config.klaviyo.clientId);
  url.searchParams.set("redirect_uri", callbackUrl("klaviyo"));
  url.searchParams.set("scope", config.klaviyo.scopes);
  url.searchParams.set("state", state);
  // Klaviyo requires PKCE for public AND confidential clients, so this is not
  // optional hardening — without it the exchange is refused.
  url.searchParams.set("code_challenge", codeChallenge);
  url.searchParams.set("code_challenge_method", "S256");
  return url.toString();
}

async function handleKlaviyoCallback(queryParams, { browserNonce } = {}) {
  requireOauthConfig("klaviyo");
  const state = await consumeOauthState({ state: queryParams.state, provider: "klaviyo", browserNonce });
  if (!queryParams.code) {
    throw new Error("Klaviyo callback is missing code.");
  }

  // The verifier for THIS authorization request, gone from the table the moment
  // the state was consumed. Its absence means the row predates PKCE or was
  // written by something that skipped it; either way the exchange would be
  // refused by Klaviyo, and starting the connection again is the fix.
  if (!state.code_verifier) {
    throw new Error("This Klaviyo connection is missing its security code. Start connecting Klaviyo again.");
  }

  const form = new URLSearchParams();
  form.set("grant_type", "authorization_code");
  form.set("code", queryParams.code);
  form.set("redirect_uri", callbackUrl("klaviyo"));
  form.set("code_verifier", state.code_verifier);

  const basic = Buffer.from(`${config.klaviyo.clientId}:${config.klaviyo.clientSecret}`).toString("base64");
  const response = await axios.post(config.klaviyo.tokenUrl, form.toString(), {
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
      // What THIS store's token was actually granted, with no fallback to what
      // the app asks for. null when there is no OAuth token or it predates
      // scope tracking: unknown, not missing.
      grantedScopes: row?.shopify_access_token ? row.shopify_scope || null : null,
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

// One refresh per store at a time. A page load fires several Klaviyo-backed
// requests together; with an expired token each used to refresh on its own, all
// presenting the same refresh token. Klaviyo rotates refresh tokens, so every
// refresh after the first could be refused and those requests failed ("Check in
// Klaviyo", "Couldn't reach Klaviyo") until a later call picked up the stored
// winner. Concurrent callers now share the one refresh in flight. In-process only:
// the pilot runs a single instance.
const klaviyoRefreshInFlight = new Map();

async function refreshKlaviyoToken(shopDomain, refreshToken) {
  const form = new URLSearchParams();
  // No verifier here: PKCE binds one authorization code to one browser
  // exchange. A refresh is this server talking to Klaviyo with its own
  // client credentials, and Klaviyo's refresh request takes only the grant
  // type and the refresh token.
  form.set("grant_type", "refresh_token");
  form.set("refresh_token", refreshToken);
  const basic = Buffer.from(`${config.klaviyo.clientId}:${config.klaviyo.clientSecret}`).toString("base64");
  const response = await axios.post(config.klaviyo.tokenUrl, form.toString(), {
    headers: {
      Authorization: `Basic ${basic}`,
      "Content-Type": "application/x-www-form-urlencoded",
      revision: config.klaviyo.revision,
    },
    timeout: 30000,
  });
  const nextAccessToken = response.data.access_token;
  if (!nextAccessToken) return null;
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

async function resolveStoredKlaviyoToken(shopDomain) {
  const row = await getConnection(shopDomain);
  if (row?.klaviyo_access_token) {
    const expiresAt = row.klaviyo_expires_at ? new Date(row.klaviyo_expires_at).getTime() : 0;
    const refreshToken = decryptToken(row.klaviyo_refresh_token);
    const shouldRefresh = refreshToken && expiresAt && expiresAt < Date.now() + 120000;
    if (shouldRefresh) {
      let pending = klaviyoRefreshInFlight.get(shopDomain);
      if (!pending) {
        pending = refreshKlaviyoToken(shopDomain, refreshToken)
          .finally(() => klaviyoRefreshInFlight.delete(shopDomain));
        klaviyoRefreshInFlight.set(shopDomain, pending);
      }
      const nextAccessToken = await pending;
      if (nextAccessToken) return nextAccessToken;
    }
    return decryptToken(row.klaviyo_access_token);
  }
  if (row?.klaviyo_private_key) return row.klaviyo_private_key;
  // Same rule: the configured key is the configured shop's, not a default for
  // whoever asks.
  return ownsGlobalCredentials(shopDomain) ? config.klaviyo.privateKey : null;
}

module.exports = {
  OAUTH_BROWSER_COOKIE,
  clearOauthBrowserCookie,
  newBrowserNonce,
  oauthBrowserCookie,
  safeReturnTo,
  webhookAddress,
  ownsGlobalCredentials,
  buildShopifyStartUrl,
  handleShopifyCallback,
  buildKlaviyoStartUrl,
  handleKlaviyoCallback,
  getConnectionStatus,
  resolveStoredShopifyToken,
  resolveStoredKlaviyoToken,
};
