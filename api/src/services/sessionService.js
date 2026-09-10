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

const SESSION_COOKIE = "beaconai_session";
const DEFAULT_TTL_MS = 14 * 24 * 60 * 60 * 1000;

function sign(payload) {
  return crypto
    .createHmac("sha256", config.tokenEncryptionSecret)
    .update(payload)
    .digest("base64url");
}

/**
 * A signed token bound to one shop, with an expiry inside the signature so it
 * cannot be extended by editing the token.
 */
function issueSession(shopDomain, { ttlMs = DEFAULT_TTL_MS, now = Date.now() } = {}) {
  if (!shopDomain) throw new Error("shopDomain is required to issue a session");
  const body = Buffer.from(JSON.stringify({ shop: shopDomain, exp: now + ttlMs })).toString("base64url");
  return `${body}.${sign(body)}`;
}

/**
 * The shop this token proves, or null.
 *
 * Every failure returns null rather than throwing: a malformed token, a forged
 * one and an expired one are all simply "not authenticated", and distinguishing
 * them for the caller would only help someone probing.
 */
function readSession(token, { now = Date.now() } = {}) {
  if (!token || typeof token !== "string") return null;
  const [body, signature] = token.split(".");
  if (!body || !signature) return null;

  const expected = sign(body);
  // Constant-time: the comparison is over attacker-supplied input.
  const a = Buffer.from(signature);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;

  let payload;
  try {
    payload = JSON.parse(Buffer.from(body, "base64url").toString("utf8"));
  } catch (_) {
    return null;
  }
  if (!payload?.shop || !payload?.exp || payload.exp < now) return null;
  return { shopDomain: payload.shop, expiresAt: payload.exp };
}

function parseCookies(header) {
  const out = {};
  for (const part of String(header || "").split(";")) {
    const index = part.indexOf("=");
    if (index === -1) continue;
    out[part.slice(0, index).trim()] = decodeURIComponent(part.slice(index + 1).trim());
  }
  return out;
}

// Cookie for the browser, bearer for anything scripted. Both carry the same
// signed token; neither is trusted further than its signature.
function sessionFromRequest(req, options = {}) {
  const header = req.get?.("authorization") || "";
  const bearer = header.toLowerCase().startsWith("bearer ") ? header.slice(7).trim() : null;
  const cookie = parseCookies(req.headers?.cookie)[SESSION_COOKIE] || null;
  return readSession(bearer || cookie, options);
}

function sessionCookie(token, { ttlMs = DEFAULT_TTL_MS } = {}) {
  const secure = /^https:/i.test(config.webBaseUrl || "") ? "; Secure" : "";
  // HttpOnly so page scripts cannot read it; SameSite=Lax so it survives the
  // OAuth redirect back from Shopify without riding along on cross-site posts.
  return `${SESSION_COOKIE}=${encodeURIComponent(token)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${Math.floor(ttlMs / 1000)}${secure}`;
}

/**
 * Express guard. Puts the AUTHENTICATED shop on the request; routes must use
 * that and never a shop the body or query named.
 *
 * The founder token is accepted as an operator credential and may act for any
 * shop, because reconciliation is a founder task by design. It still has to be
 * configured — an unset token authenticates nobody.
 */
function requireShopSession(req, res, next) {
  const adminToken = process.env.BEACONAI_ADMIN_TOKEN;
  if (adminToken && req.get("x-beaconai-admin-token") === adminToken) {
    req.auth = { kind: "founder", shopDomain: req.query.shopDomain || req.body?.shopDomain || null };
    next();
    return;
  }

  const session = sessionFromRequest(req);
  if (!session) {
    res.status(401).json({ ok: false, error: "Sign in to this store before using this." });
    return;
  }
  req.auth = { kind: "shop", shopDomain: session.shopDomain };
  next();
}

// Does this request speak for `shopDomain`? A founder does for any shop; a shop
// session does for exactly one.
function authorizedForShop(req, shopDomain) {
  if (!req.auth) return false;
  if (req.auth.kind === "founder") return true;
  return Boolean(shopDomain) && req.auth.shopDomain === shopDomain;
}

module.exports = {
  DEFAULT_TTL_MS,
  SESSION_COOKIE,
  authorizedForShop,
  issueSession,
  parseCookies,
  readSession,
  requireShopSession,
  sessionCookie,
  sessionFromRequest,
};
