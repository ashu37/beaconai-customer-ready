// The pilot's access boundary.
//
// Until this, campaign routes trusted a shop domain the caller supplied. That is
// not authentication: anyone who knew or guessed a shop name could read and act
// on that store's campaigns. Naming the shop is a claim; this is what checks it.
//
// A session is issued only at the end of a completed Shopify OAuth callback —
// the one point where the shop has demonstrably authorised us — and is a signed,
// expiring token bound to that shop. Nothing else mints one.
//
// Deliberately minimal, and deliberately not a user system: the pilot has one
// merchant per store and a founder. It is a boundary, not an identity product.

const crypto = require("node:crypto");
const { config } = require("../config");
const { query } = require("../db");

const SESSION_COOKIE = "beaconai_session";
const DEFAULT_TTL_MS = 14 * 24 * 60 * 60 * 1000;

// Signed with SESSION_SECRET only. Integration tokens use a different key
// (tokenCrypto.js), so revoking sessions never touches them.
function sign(payload) {
  return crypto
    .createHmac("sha256", config.sessionSecret)
    .update(payload)
    .digest("base64url");
}

function constantTimeEqual(provided, expected) {
  const a = Buffer.from(String(provided || ""));
  const b = Buffer.from(String(expected || ""));
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

/**
 * Sign a token for an existing session row. The signature proves the token was
 * issued here; the row decides whether it still counts.
 */
function signSessionToken({ sessionId, shopDomain, expiresAt }) {
  const body = Buffer.from(JSON.stringify({ sid: sessionId, shop: shopDomain, exp: expiresAt })).toString("base64url");
  return `${body}.${sign(body)}`;
}

/**
 * Create a server-side session and return its token. The ONE place a session is
 * created is the end of a completed Shopify OAuth callback (routes.js).
 */
async function createSession(shopDomain, { ttlMs = DEFAULT_TTL_MS, now = Date.now() } = {}) {
  if (!shopDomain) throw new Error("shopDomain is required to create a session");
  const sessionId = crypto.randomBytes(24).toString("base64url");
  const expiresAt = now + ttlMs;
  await query(
    `INSERT INTO clean.sessions (id, shop_domain, expires_at) VALUES ($1, $2, to_timestamp($3 / 1000.0))`,
    [sessionId, shopDomain, expiresAt]
  );
  return { token: signSessionToken({ sessionId, shopDomain, expiresAt }), sessionId, expiresAt };
}

/**
 * What a token claims, if its signature and expiry hold — or null. Pure: whether
 * the session is still valid is authenticateToken's question.
 *
 * Every failure returns null rather than throwing: a malformed token, a forged
 * one and an expired one are all simply "not authenticated", and distinguishing
 * them for the caller would only help someone probing.
 */
function readSession(token, { now = Date.now() } = {}) {
  if (!token || typeof token !== "string") return null;
  const [body, signature] = token.split(".");
  if (!body || !signature) return null;
  if (!config.sessionSecret || !constantTimeEqual(signature, sign(body))) return null;

  let payload;
  try {
    payload = JSON.parse(Buffer.from(body, "base64url").toString("utf8"));
  } catch (_) {
    return null;
  }
  // A token without a session id predates server-side sessions and is refused.
  if (!payload?.sid || !payload?.shop || !payload?.exp || payload.exp < now) return null;
  return { sessionId: payload.sid, shopDomain: payload.shop, expiresAt: payload.exp };
}

/**
 * The live session a token stands for, or null: signature valid, row present,
 * not revoked, not expired, same shop, and the store not disabled.
 */
async function authenticateToken(token, options = {}) {
  const claim = readSession(token, options);
  if (!claim) return null;
  const { rows } = await query(
    `SELECT s.id
       FROM clean.sessions s
       LEFT JOIN clean.store_access a ON a.shop_domain = s.shop_domain
      WHERE s.id = $1 AND s.shop_domain = $2
        AND s.revoked_at IS NULL AND s.expires_at > NOW()
        AND a.disabled_at IS NULL`,
    [claim.sessionId, claim.shopDomain]
  );
  return rows.length ? claim : null;
}

function parseCookies(header) {
  const out = {};
  for (const part of String(header || "").split(";")) {
    const index = part.indexOf("=");
    if (index === -1) continue;
    try {
      out[part.slice(0, index).trim()] = decodeURIComponent(part.slice(index + 1).trim());
    } catch (_) {
      // A malformed cookie value is ignored, not a crash.
    }
  }
  return out;
}

function tokenFromRequest(req) {
  const header = req.get?.("authorization") || "";
  const bearer = header.toLowerCase().startsWith("bearer ") ? header.slice(7).trim() : null;
  return bearer || parseCookies(req.headers?.cookie)[SESSION_COOKIE] || null;
}

// Cookie for the browser, bearer for anything scripted. Both carry the same
// signed token; neither is trusted further than the session row behind it.
async function sessionFromRequest(req, options = {}) {
  return authenticateToken(tokenFromRequest(req), options);
}

async function revokeSession(sessionId, reason = "logout") {
  const { rowCount } = await query(
    `UPDATE clean.sessions SET revoked_at = NOW(), revoked_reason = $2 WHERE id = $1 AND revoked_at IS NULL`,
    [sessionId, reason]
  );
  return rowCount > 0;
}

function cookieSuffix() {
  return /^https:/i.test(config.webBaseUrl || "") ? "; Secure" : "";
}

function sessionCookie(token, { ttlMs = DEFAULT_TTL_MS } = {}) {
  // HttpOnly so page scripts cannot read it; SameSite=Lax so it survives the
  // OAuth redirect back from Shopify without riding along on cross-site posts.
  return `${SESSION_COOKIE}=${encodeURIComponent(token)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${Math.floor(ttlMs / 1000)}${cookieSuffix()}`;
}

function clearSessionCookie() {
  return `${SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0${cookieSuffix()}`;
}

function isFounderToken(provided) {
  const expected = process.env.BEACONAI_ADMIN_TOKEN;
  if (!expected || !provided) return false;
  return constantTimeEqual(provided, expected);
}

/**
 * Express guard. Puts the AUTHENTICATED shop on the request; routes must use
 * that and never a shop the body or query named.
 *
 * The founder token is accepted as an operator credential and may act for any
 * shop, because reconciliation is a founder task by design. It still has to be
 * configured — an unset token authenticates nobody — and compared in constant
 * time. Work for a disabled store is refused where it starts
 * (storeAccessService.assertStoreActive), founder or not.
 */
async function requireShopSession(req, res, next) {
  try {
    if (isFounderToken(req.get("x-beaconai-admin-token"))) {
      req.auth = { kind: "founder", shopDomain: req.query.shopDomain || req.body?.shopDomain || null };
      next();
      return;
    }

    const session = await sessionFromRequest(req);
    if (!session) {
      res.status(401).json({ ok: false, error: "Sign in to this store before using this." });
      return;
    }
    req.auth = { kind: "shop", shopDomain: session.shopDomain, sessionId: session.sessionId };
    next();
  } catch (error) {
    next(error);
  }
}

// Does this request speak for `shopDomain`? A founder does for any shop; a shop
// session does for exactly one.
function authorizedForShop(req, shopDomain) {
  if (!req.auth) return false;
  if (req.auth.kind === "founder") return true;
  return Boolean(shopDomain) && req.auth.shopDomain === shopDomain;
}

/**
 * The shop this request is entitled to act on, or null after answering.
 *
 * `requested` is whatever the caller named — a param, query or body field. It is
 * a CLAIM, and this is where it gets checked against the session rather than
 * trusted. A shop session may only ever act on its own shop; a founder
 * credential may act on the shop it names.
 *
 * Routes must use the return value and never the raw request field, or the
 * check becomes decorative.
 */
function authorizedShop(req, res, requested) {
  if (!req.auth) {
    res.status(401).json({ ok: false, error: "Sign in to this store before using this." });
    return null;
  }

  if (req.auth.kind === "founder") {
    const shop = requested || req.auth.shopDomain || null;
    if (!shop) {
      res.status(400).json({ ok: false, error: "shopDomain is required" });
      return null;
    }
    return shop;
  }

  // No shop named: the session's own shop is the only one it could mean.
  if (!requested) return req.auth.shopDomain;

  if (requested !== req.auth.shopDomain) {
    // 403, not 404: the caller IS authenticated, just not for this shop, and
    // they already knew the shop name they sent.
    res.status(403).json({ ok: false, error: "This store isn't the one you're signed in to." });
    return null;
  }
  return requested;
}

module.exports = {
  authorizedShop,
  DEFAULT_TTL_MS,
  SESSION_COOKIE,
  authenticateToken,
  authorizedForShop,
  clearSessionCookie,
  constantTimeEqual,
  createSession,
  isFounderToken,
  parseCookies,
  readSession,
  requireShopSession,
  revokeSession,
  sessionCookie,
  sessionFromRequest,
  signSessionToken,
};
