const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { startApi } = require("./helpers/httpApp");
const {
  authorizedForShop,
  issueSession,
  readSession,
  sessionCookie,
} = require("../src/services/sessionService");

let api;
test.before(async () => { if (db.available) api = await startApi(); });
test.after(async () => {
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

test("a session names exactly the shop it was issued for", () => {
  const token = issueSession("acme.myshopify.com");
  assert.equal(readSession(token).shopDomain, "acme.myshopify.com");
});

test("a forged or altered token authenticates nobody", () => {
  const token = issueSession("acme.myshopify.com");
  const [body] = token.split(".");

  // Every one of these is simply "not authenticated". Distinguishing them for
  // the caller would only help someone probing.
  for (const bad of [
    `${body}.notthesignature`,
    `${body}.`,
    body,
    "",
    null,
    undefined,
    // The shop swapped, signature kept: the signature covers the body.
    `${Buffer.from(JSON.stringify({ shop: "victim.myshopify.com", exp: Date.now() + 1000 })).toString("base64url")}.${token.split(".")[1]}`,
  ]) {
    assert.equal(readSession(bad), null, `should reject: ${String(bad).slice(0, 40)}`);
  }
});

test("an expiry cannot be extended by editing the token", () => {
  // The expiry is inside the signed body, so rewriting it invalidates the
  // signature rather than buying more time.
  const expired = issueSession("acme.myshopify.com", { ttlMs: -1 });
  assert.equal(readSession(expired), null);

  const forged = `${Buffer.from(JSON.stringify({ shop: "acme.myshopify.com", exp: Date.now() + 99999999 })).toString("base64url")}.${expired.split(".")[1]}`;
  assert.equal(readSession(forged), null);
});

test("the session cookie is not readable by page scripts", () => {
  const cookie = sessionCookie(issueSession("acme.myshopify.com"));
  assert.match(cookie, /HttpOnly/);
  assert.match(cookie, /SameSite=Lax/);
  assert.match(cookie, /Path=\//);
});

test("a shop session speaks for one shop only", () => {
  const req = { auth: { kind: "shop", shopDomain: "acme.myshopify.com" } };
  assert.equal(authorizedForShop(req, "acme.myshopify.com"), true);
  assert.equal(authorizedForShop(req, "other.myshopify.com"), false);
  assert.equal(authorizedForShop(req, null), false);
  assert.equal(authorizedForShop({}, "acme.myshopify.com"), false);
});

test("a founder credential may act for any shop", () => {
  // Reconciliation is a founder task by design; this is the operator path.
  const req = { auth: { kind: "founder", shopDomain: null } };
  assert.equal(authorizedForShop(req, "acme.myshopify.com"), true);
});

suite("an unauthenticated request is refused whatever shop it names", async () => {
  await db.resetDatabase();
  const anonymous = await api.get("/campaigns/1/delivery?shopDomain=acme.myshopify.com");
  assert.equal(anonymous.status, 401);
  assert.match(anonymous.body.error, /Sign in/);
});

suite("the session endpoint reports who the caller is", async () => {
  const anonymous = await api.get("/session");
  assert.equal(anonymous.body.authenticated, false);
  assert.equal(anonymous.body.shopDomain, null);

  const signed = await api.get("/session", { session: "acme.myshopify.com" });
  assert.equal(signed.body.authenticated, true);
  assert.equal(signed.body.shopDomain, "acme.myshopify.com");
});
