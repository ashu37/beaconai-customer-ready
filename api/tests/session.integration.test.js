const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
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
  const anonymous = await api.get("/campaigns/1/delivery?shopDomain=acme.myshopify.com", { session: null });
  assert.equal(anonymous.status, 401);
  assert.match(anonymous.body.error, /Sign in/);
});

suite("the session endpoint reports who the caller is", async () => {
  const anonymous = await api.get("/session", { session: null });
  assert.equal(anonymous.body.authenticated, false);
  assert.equal(anonymous.body.shopDomain, null);

  const signed = await api.get("/session", { session: "acme.myshopify.com" });
  assert.equal(signed.body.authenticated, true);
  assert.equal(signed.body.shopDomain, "acme.myshopify.com");
});

suite("every data route refuses an anonymous caller", async () => {
  await db.resetDatabase();
  const shop = "acme.myshopify.com";
  const q = `shopDomain=${encodeURIComponent(shop)}`;

  // Naming the shop is a claim. Each of these used to accept it as a
  // credential; this asserts none of them still does.
  const gets = [
    `/brand/context?${q}`,
    `/brand/email-template?${q}`,
    `/klaviyo/templates?${q}`,
    `/klaviyo/lists?${q}`,
    `/klaviyo/profiles?${q}`,
    `/klaviyo/sender?${q}`,
    `/sync/status/${shop}`,
    `/engine/input/${shop}`,
    `/stats/series/${shop}`,
    `/engine/atul/latest/${shop}`,
    `/campaigns/${shop}`,
    `/results/${shop}`,
    "/campaigns/1/delivery",
    "/campaigns/1/results",
  ];
  for (const path of gets) {
    const response = await api.get(path, { session: null });
    assert.equal(response.status, 401, `GET ${path} should require a session`);
  }

  const posts = [
    "/sync/shopify",
    "/engine/atul/run",
    "/copy/generate",
    "/campaigns",
    "/campaigns/audience/preview",
    "/klaviyo/campaigns/preview-html",
    "/klaviyo/campaigns/from-engine",
    "/klaviyo/campaigns/send",
  ];
  for (const path of posts) {
    const response = await api.post(path, { shopDomain: shop }, { session: null });
    assert.equal(response.status, 401, `POST ${path} should require a session`);
  }
});

suite("a session for one shop cannot act on another", async () => {
  await db.resetDatabase();
  const other = "someone-else.myshopify.com";

  // 403, not 404: the caller IS authenticated, just not for this shop, and they
  // already knew the name they sent.
  const get = await api.get(`/brand/context?shopDomain=${encodeURIComponent(other)}`, { session: "acme.myshopify.com" });
  assert.equal(get.status, 403);
  assert.match(get.body.error, /isn't the one you're signed in to/);

  const post = await api.post("/campaigns/audience/preview", { shopDomain: other, campaign: {} }, { session: "acme.myshopify.com" });
  assert.equal(post.status, 403);
});

suite("onboarding still works before a session exists", async () => {
  await db.resetDatabase();
  const shop = "acme.myshopify.com";

  // The connect flow has to render for a shop nobody has authorised yet.
  const status = await api.get(`/connections/status?shopDomain=${encodeURIComponent(shop)}`, { session: null });
  assert.equal(status.status, 200);
  assert.equal(typeof status.body.status.shopify.connected, "boolean");
  // But an unauthenticated caller learns nothing beyond the booleans.
  assert.equal(status.body.status.shopify.scopes, undefined, "granted scopes are not public");

  // The point is only that none of these is gated. /ready answers 503 in the
  // test harness because startup never marks the database ready — a correct
  // readiness answer, not a refusal.
  for (const path of ["/health", "/ready", "/session"]) {
    const response = await api.get(path, { session: null });
    assert.notEqual(response.status, 401, `${path} must not require a session`);
    assert.notEqual(response.status, 403, `${path} must not require a session`);
  }
});

suite("no route spends another shop's stored credentials", async () => {
  await db.resetDatabase();
  const mine = "mine.myshopify.com";
  const theirs = "theirs.myshopify.com";

  // Only the OTHER shop has provider credentials. If a handler resolves them
  // from the request rather than the session, the response comes back carrying
  // that shop's data — which is exactly what was reproduced.
  await query(
    `INSERT INTO clean.connections (shop_domain, shopify_access_token, klaviyo_private_key)
     VALUES ($1, 'their-shopify-token', 'their-klaviyo-key')`,
    [theirs]
  );
  await query(`INSERT INTO clean.connections (shop_domain) VALUES ($1)`, [mine]);

  // Every route that reaches a provider with a stored credential.
  const crossShopGets = [
    `/klaviyo/profiles?shopDomain=${encodeURIComponent(theirs)}`,
    `/klaviyo/lists?shopDomain=${encodeURIComponent(theirs)}`,
    `/klaviyo/sender?shopDomain=${encodeURIComponent(theirs)}`,
    `/klaviyo/templates?shopDomain=${encodeURIComponent(theirs)}`,
    `/brand/context?shopDomain=${encodeURIComponent(theirs)}`,
    `/brand/email-template?shopDomain=${encodeURIComponent(theirs)}`,
    `/sync/status/${theirs}`,
    `/engine/input/${theirs}`,
    `/stats/series/${theirs}`,
    `/engine/atul/latest/${theirs}`,
    `/campaigns/${theirs}`,
    `/results/${theirs}`,
  ];
  for (const path of crossShopGets) {
    const response = await api.get(path, { session: mine });
    assert.equal(response.status, 403, `GET ${path} must refuse a session for another shop`);
  }

  const crossShopPosts = [
    "/connections/shopify/test",
    "/connections/klaviyo/test",
    "/sync/shopify",
    "/engine/atul/run",
    "/copy/generate",
    "/campaigns",
    "/campaigns/audience/preview",
    "/klaviyo/campaigns/preview-html",
    "/klaviyo/campaigns/from-engine",
    "/klaviyo/campaigns/send",
  ];
  for (const path of crossShopPosts) {
    const response = await api.post(path, { shopDomain: theirs }, { session: mine });
    assert.equal(response.status, 403, `POST ${path} must refuse a session for another shop`);
  }
});

suite("the connection tests are not anonymous", async () => {
  await db.resetDatabase();
  const shop = "acme.myshopify.com";
  await query(
    `INSERT INTO clean.connections (shop_domain, klaviyo_private_key, shopify_access_token)
     VALUES ($1, 'a-key', 'a-token')`,
    [shop]
  );

  // These load a shop's stored credential and return the provider's response.
  // Anonymous access handed out account data to anyone who could name a shop.
  for (const path of ["/connections/klaviyo/test", "/connections/shopify/test"]) {
    const response = await api.post(path, { shopDomain: shop }, { session: null });
    assert.equal(response.status, 401, `${path} must require a session`);
  }

  // Onboarding does not need them: the booleans are public and sufficient.
  const status = await api.get(`/connections/status?shopDomain=${encodeURIComponent(shop)}`, { session: null });
  assert.equal(status.status, 200);
  assert.equal(status.body.status.klaviyo.connected, true);
  assert.equal(status.body.status.klaviyo.scopes, undefined);
});

suite("Klaviyo OAuth cannot be started for a shop you are not signed in to", async () => {
  await db.resetDatabase();
  const victim = "victim.myshopify.com";

  // Completing this flow writes credentials against whatever shop the OAuth
  // state carries. Accepting a shop from the query let anyone start it naming
  // another store and overwrite that store's Klaviyo connection.
  const anonymous = await api.get(`/oauth/klaviyo/start?shop=${encodeURIComponent(victim)}`, { session: null });
  assert.equal(anonymous.status, 401);

  // Shopify's start stays public: it IS the sign-in, and there is no session to
  // require yet.
  const shopify = await fetch(`${api.base}/oauth/shopify/start?shop=${encodeURIComponent(victim)}`, { redirect: "manual" });
  assert.notEqual(shopify.status, 401, "the sign-in route must stay reachable");
});

suite("the state a Klaviyo connection binds to comes from the session", async () => {
  const { buildKlaviyoStartUrl } = require("../src/services/oauthService");
  // Not callable without an authenticated shop at all — the shop is no longer
  // something a caller can pass in.
  await assert.rejects(
    () => buildKlaviyoStartUrl({ shopDomain: null, returnTo: null }),
    /authenticated shop is required/
  );
});

suite("an unconnected shop does not inherit the deployment's credentials", async () => {
  await db.resetDatabase();
  const { resolveStoredKlaviyoToken, resolveStoredShopifyToken } = require("../src/services/oauthService");
  const stranger = "stranger.myshopify.com";

  const previousShop = process.env.SHOPIFY_SHOP_DOMAIN;
  const previousKlaviyo = require("../src/config").config.klaviyo.privateKey;
  const previousShopify = require("../src/config").config.shopify.accessToken;
  const { config } = require("../src/config");
  config.klaviyo.privateKey = "global-klaviyo-key";
  config.shopify.accessToken = "global-shopify-token";
  config.shopify.shopDomain = "configured.myshopify.com";

  try {
    // A session for a shop with no stored credential used to reach the provider
    // with the deployment's own key and read that account's data back.
    assert.equal(await resolveStoredKlaviyoToken(stranger), null);
    assert.equal(await resolveStoredShopifyToken(stranger), null);

    // The configured shop still gets them: they are its credentials.
    assert.equal(await resolveStoredKlaviyoToken("configured.myshopify.com"), "global-klaviyo-key");
    assert.equal(await resolveStoredShopifyToken("configured.myshopify.com"), "global-shopify-token");

    // And a shop's OWN stored credential always wins.
    await query(
      `INSERT INTO clean.connections (shop_domain, klaviyo_private_key) VALUES ($1, 'their-own-key')`,
      [stranger]
    );
    assert.equal(await resolveStoredKlaviyoToken(stranger), "their-own-key");
  } finally {
    config.klaviyo.privateKey = previousKlaviyo;
    config.shopify.accessToken = previousShopify;
    config.shopify.shopDomain = previousShop;
  }
});
