const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const { Writable } = require("node:stream");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const axios = require("axios");
const { query } = require("../src/db");
const { config, DEV_SECRET } = require("../src/config");
const { startApi } = require("./helpers/httpApp");
const { productionDatabaseProblems, productionSecretProblems } = require("../src/secretsPolicy");
const { encryptToken, decryptToken, inspectToken, tokenKeyHealth } = require("../src/services/tokenCrypto");
const { redactUrl, requestLogger } = require("../src/requestLog");
const { safeReturnTo } = require("../src/services/oauthService");
const { createSession } = require("../src/services/sessionService");
const { disableStore, StoreDisabledError } = require("../src/services/storeAccessService");
const { runSync } = require("../src/services/syncService");

// PR A of docs/SECURITY_HARDENING_PLAN.md: secrets, OAuth, revocation, logs.

const SHOP = "hardening.myshopify.com";
const FOUNDER = "founder-token-for-tests-0123456789abcdef";
const STRONG = (label) => `${label}-${"x".repeat(40)}`;

let api;
const saved = {
  admin: process.env.BEACONAI_ADMIN_TOKEN,
  shopify: { ...config.shopify },
  token: config.tokenEncryptionSecret,
  previous: config.tokenEncryptionPreviousSecret,
  session: config.sessionSecret,
  web: config.webBaseUrl,
  post: axios.post,
};

test.before(async () => {
  process.env.BEACONAI_ADMIN_TOKEN = FOUNDER;
  config.shopify.clientId = "test-client";
  config.shopify.clientSecret = "test-shopify-secret";
  if (db.available) api = await startApi();
});
test.after(async () => {
  process.env.BEACONAI_ADMIN_TOKEN = saved.admin;
  Object.assign(config.shopify, saved.shopify);
  config.tokenEncryptionSecret = saved.token;
  config.tokenEncryptionPreviousSecret = saved.previous;
  config.sessionSecret = saved.session;
  config.webBaseUrl = saved.web;
  axios.post = saved.post;
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

// --- A2. Secrets ------------------------------------------------------------

test("production refuses missing, default, short, shared or weak secrets", () => {
  const good = {
    NODE_ENV: "production",
    SESSION_SECRET: STRONG("session"),
    TOKEN_ENCRYPTION_SECRET: STRONG("token"),
    BEACONAI_ADMIN_TOKEN: STRONG("founder"),
    SHOPIFY_CLIENT_ID: "id",
    SHOPIFY_CLIENT_SECRET: "secret",
  };
  assert.deepEqual(productionSecretProblems(good), []);

  const cases = [
    [{ SESSION_SECRET: undefined }, /SESSION_SECRET is not set/],
    [{ TOKEN_ENCRYPTION_SECRET: undefined }, /TOKEN_ENCRYPTION_SECRET is not set/],
    [{ SESSION_SECRET: DEV_SECRET }, /public development default/],
    [{ TOKEN_ENCRYPTION_SECRET: "short" }, /at least 32 characters/],
    [{ TOKEN_ENCRYPTION_SECRET: STRONG("session") }, /must be different values/],
    [{ BEACONAI_ADMIN_TOKEN: "guessable" }, /BEACONAI_ADMIN_TOKEN must be at least/],
    [{ SHOPIFY_CLIENT_SECRET: undefined }, /SHOPIFY_CLIENT_SECRET is required/],
  ];
  for (const [change, message] of cases) {
    const problems = productionSecretProblems({ ...good, ...change });
    assert.ok(problems.some((p) => message.test(p)), `${JSON.stringify(change)} -> ${problems.join(" | ")}`);
    for (const problem of problems) {
      for (const value of Object.values({ ...good, ...change })) {
        if (value && value.length > 12) assert.ok(!problem.includes(value), "no secret value in a message");
      }
    }
  }
  // Development keeps its fallbacks.
  assert.deepEqual(productionSecretProblems({ NODE_ENV: "development" }), []);
});

test("production refuses to run schema changes as the application role", () => {
  // The failure this prevents: unset, the owner connection falls back to
  // DATABASE_URL and CREATE SCHEMA fails with "permission denied for database".
  const base = { NODE_ENV: "production", DATABASE_URL: "postgres://beaconai_app:x@host/postgres" };
  assert.match(productionDatabaseProblems(base)[0], /MIGRATION_DATABASE_URL is not set/);
  assert.match(
    productionDatabaseProblems({ ...base, MIGRATION_DATABASE_URL: base.DATABASE_URL })[0],
    /must differ from DATABASE_URL/
  );
  assert.deepEqual(productionDatabaseProblems({ ...base, MIGRATION_DATABASE_URL: "postgres://postgres:y@host/postgres" }), []);
  // Development runs from one connection.
  assert.deepEqual(productionDatabaseProblems({ NODE_ENV: "development" }), []);
});

test("splitting the session secret leaves stored integration tokens readable", () => {
  // Before: one secret did both jobs.
  config.tokenEncryptionSecret = STRONG("shared-before-split");
  config.sessionSecret = STRONG("shared-before-split");
  const stored = encryptToken("shpat_live_token");

  // After: the token secret keeps its value, sessions get their own.
  config.sessionSecret = STRONG("new-session-only");
  assert.equal(inspectToken(stored).status, "current");
  assert.equal(decryptToken(stored), "shpat_live_token");

  // Rotating the token key later: the previous key still opens old values, and
  // new values are written under the current key.
  config.tokenEncryptionPreviousSecret = config.tokenEncryptionSecret;
  config.tokenEncryptionSecret = STRONG("rotated-token-key");
  assert.equal(inspectToken(stored).status, "previous");
  assert.equal(decryptToken(stored), "shpat_live_token");
  assert.equal(inspectToken(encryptToken("fresh")).status, "current");

  // Without the previous key it is reported, never silently treated as empty.
  config.tokenEncryptionPreviousSecret = null;
  assert.equal(inspectToken(stored).status, "undecryptable");
  assert.throws(() => decryptToken(stored), /could not be decrypted/);

  config.tokenEncryptionSecret = saved.token;
  config.tokenEncryptionPreviousSecret = saved.previous;
  config.sessionSecret = saved.session;
});

suite("token health counts which key opens each stored token, without values", async () => {
  await db.resetDatabase();
  await query(
    `INSERT INTO clean.connections (shop_domain, shopify_access_token, klaviyo_access_token) VALUES ($1, $2, $3)`,
    [SHOP, encryptToken("a"), "legacy-plaintext"]
  );
  const counts = await tokenKeyHealth(query);
  assert.deepEqual(counts, { current: 1, previous: 0, plaintext: 1, undecryptable: 0 });
});

// --- A5. Logs -----------------------------------------------------------------

test("request logs never contain OAuth codes, state, hmac or credentials", async () => {
  const url = "/api/oauth/shopify/callback?code=CODE123&hmac=HMAC456&host=HOST789&shop=a.myshopify.com&state=STATE000&timestamp=1";
  const redacted = redactUrl(url);
  for (const secret of ["CODE123", "HMAC456", "HOST789", "STATE000"]) assert.ok(!redacted.includes(secret), secret);
  assert.match(redacted, /shop=a\.myshopify\.com/);
  assert.equal(redactUrl("/api/x?access_token=abc&api_key=def&email=a@b.c&shopDomain=s"), "/api/x?access_token=[redacted]&api_key=[redacted]&email=[redacted]&shopDomain=s");

  // Through the real logger.
  const lines = [];
  const stream = new Writable({ write(chunk, _enc, done) { lines.push(String(chunk)); done(); } });
  const logger = requestLogger({ stream });
  await new Promise((resolve) => {
    const req = { method: "GET", url, originalUrl: url, headers: {}, httpVersionMajor: 1, httpVersionMinor: 1, socket: {} };
    const res = new (require("node:events"))();
    Object.assign(res, { statusCode: 400, getHeader: () => undefined, _header: true, headersSent: true });
    logger(req, res, () => { res.emit("finish"); setImmediate(resolve); });
  });
  const line = lines.join("");
  assert.match(line, /\/api\/oauth\/shopify\/callback/);
  for (const secret of ["CODE123", "HMAC456", "STATE000"]) assert.ok(!line.includes(secret), `logged ${secret}: ${line}`);
});

// --- A3. OAuth ----------------------------------------------------------------

test("only app paths and the web origin are accepted as a return destination", () => {
  config.webBaseUrl = "https://app.beacon.example";
  assert.equal(safeReturnTo("/campaigns?x=1"), "https://app.beacon.example/campaigns?x=1");
  assert.equal(safeReturnTo("https://app.beacon.example/results"), "https://app.beacon.example/results");
  for (const bad of ["https://evil.example/", "//evil.example/x", "/\\evil.example", "javascript:alert(1)",
    "https://app.beacon.example.evil.example/", "http://app.beacon.example/", "", null]) {
    assert.equal(safeReturnTo(bad), null, `refused: ${bad}`);
  }
  config.webBaseUrl = saved.web;
});

function shopifyCallbackQuery(state, shop = SHOP) {
  const params = { code: "auth-code", shop, state, timestamp: String(Math.floor(Date.now() / 1000)) };
  const message = Object.keys(params).sort().map((k) => `${k}=${params[k]}`).join("&");
  params.hmac = crypto.createHmac("sha256", config.shopify.clientSecret).update(message).digest("hex");
  return new URLSearchParams(params).toString();
}

async function startShopify(query_ = `shop=${SHOP}`) {
  const res = await fetch(`${api.base}/oauth/shopify/start?${query_}`, { redirect: "manual" });
  const cookie = res.headers.get("set-cookie") || "";
  const nonce = decodeURIComponent((cookie.match(/beaconai_oauth=([^;]+)/) || [])[1] || "");
  const state = new URL(res.headers.get("location")).searchParams.get("state");
  return { res, cookie, nonce, state };
}

function stubShopifyExchange() {
  const calls = [];
  axios.post = async (url, body) => {
    calls.push(url);
    if (/access_token$/.test(url)) return { data: { access_token: "shpat_new", scope: "read_orders" } };
    if (/webhooks\.json$/.test(url)) return { data: { webhook: { id: 1 } } };
    throw new Error(`unexpected POST ${url}`);
  };
  return calls;
}

suite("an OAuth callback completes only in the browser that started it", async () => {
  await db.resetDatabase();
  const calls = stubShopifyExchange();
  try {
    const { res, cookie, nonce, state } = await startShopify(`shop=${SHOP}&returnTo=${encodeURIComponent("https://evil.example/phish")}`);
    assert.equal(res.status, 302);
    assert.match(cookie, /beaconai_oauth=[^;]+; Path=\/api\/oauth; HttpOnly; SameSite=Lax; Max-Age=900/);
    const row = (await query(`SELECT return_to, browser_hash FROM clean.oauth_states WHERE state = $1`, [state])).rows[0];
    assert.equal(row.return_to, null, "a foreign returnTo is not stored");
    assert.equal(row.browser_hash, crypto.createHash("sha256").update(nonce).digest("hex"));
    assert.ok(!row.browser_hash.includes(nonce));

    // Someone else's callback link opened in a browser without the cookie.
    const foreign = await fetch(`${api.base}/oauth/shopify/callback?${shopifyCallbackQuery(state)}`, { redirect: "manual" });
    assert.equal(foreign.status, 400);
    assert.equal((await foreign.json()).code, "oauth_failed");
    assert.ok(!(foreign.headers.get("set-cookie") || "").includes("beaconai_session="), "no session");
    assert.deepEqual(calls, [], "the code was never exchanged");
    assert.equal((await query(`SELECT count(*)::int n FROM clean.oauth_states WHERE state = $1`, [state])).rows[0].n, 1,
      "the real browser can still finish");

    // A browser that holds its OWN connection cookie (from starting a flow of
    // its own) is still not the browser that started this one.
    const other = await startShopify();
    const swapped = await fetch(`${api.base}/oauth/shopify/callback?${shopifyCallbackQuery(state)}`, {
      redirect: "manual", headers: { cookie: `beaconai_oauth=${encodeURIComponent(other.nonce)}` },
    });
    assert.equal(swapped.status, 400);
    assert.ok(!(swapped.headers.get("set-cookie") || "").includes("beaconai_session="));
    assert.deepEqual(calls, [], "still never exchanged");

    // The initiating browser.
    const own = await fetch(`${api.base}/oauth/shopify/callback?${shopifyCallbackQuery(state)}`, {
      redirect: "manual", headers: { cookie: `beaconai_oauth=${encodeURIComponent(nonce)}` },
    });
    assert.equal(own.status, 302);
    assert.equal(new URL(own.headers.get("location")).origin, new URL(config.webBaseUrl).origin, "default page, not evil.example");
    const setCookies = own.headers.getSetCookie();
    assert.ok(setCookies.some((c) => /^beaconai_oauth=; .*Max-Age=0/.test(c)), "binding cookie cleared");
    assert.ok(setCookies.some((c) => /^beaconai_session=.+HttpOnly/.test(c)), "session issued");
    assert.ok(calls.some((u) => /webhooks\.json$/.test(u)), "app/uninstalled subscribed after install");

    // Replay with the right cookie: already consumed.
    const replay = await fetch(`${api.base}/oauth/shopify/callback?${shopifyCallbackQuery(state)}`, {
      redirect: "manual", headers: { cookie: `beaconai_oauth=${encodeURIComponent(nonce)}` },
    });
    assert.equal(replay.status, 400);
  } finally {
    axios.post = saved.post;
  }
});

// --- A4. Revocation -------------------------------------------------------------

async function sessionStatus(token) {
  const res = await fetch(`${api.base}/session`, { headers: { authorization: `Bearer ${token}` } });
  return (await res.json()).authenticated;
}
async function protectedStatus(token) {
  const res = await fetch(`${api.base}/campaigns/${SHOP}`, { headers: { authorization: `Bearer ${token}` } });
  return res.status;
}

suite("logout ends the session on the server, not only in the browser", async () => {
  await db.resetDatabase();
  const { token, sessionId } = await createSession(SHOP);
  assert.equal(await sessionStatus(token), true);
  assert.equal(await protectedStatus(token), 200);

  const out = await fetch(`${api.base}/session/logout`, { method: "POST", headers: { authorization: `Bearer ${token}` } });
  assert.equal(out.status, 200);
  assert.match(out.headers.get("set-cookie"), /beaconai_session=; .*Max-Age=0/);

  // The same token, replayed.
  assert.equal(await sessionStatus(token), false);
  assert.equal(await protectedStatus(token), 401);
  const row = (await query(`SELECT revoked_reason FROM clean.sessions WHERE id = $1`, [sessionId])).rows[0];
  assert.equal(row.revoked_reason, "logout");

  // Another browser's session for the same store is unaffected.
  const other = await createSession(SHOP);
  assert.equal(await sessionStatus(other.token), true);
});

const founder = { "content-type": "application/json", "x-beaconai-admin-token": FOUNDER };

suite("a founder disable refuses existing sessions and stops store work", async () => {
  await db.resetDatabase();
  const { token } = await createSession(SHOP);
  await query(`INSERT INTO clean.analysis_jobs (shop_domain, status) VALUES ($1, 'running')`, [SHOP]);

  const wrong = await fetch(`${api.base}/admin/stores/${SHOP}/disable`, { method: "POST", headers: { ...founder, "x-beaconai-admin-token": `${FOUNDER}x` } });
  assert.ok([401, 403].includes(wrong.status), `a wrong founder token is refused: ${wrong.status}`);
  assert.equal((await query(`SELECT count(*)::int n FROM clean.store_access`)).rows[0].n, 0);

  const disabled = await fetch(`${api.base}/admin/stores/${SHOP}/disable`, { method: "POST", headers: founder });
  const body = await disabled.json();
  assert.equal(disabled.status, 200);
  assert.equal(body.sessionsRevoked, 1);
  assert.equal(body.analysisJobs, 1);

  assert.equal(await sessionStatus(token), false);
  assert.equal(await protectedStatus(token), 401);
  const job = (await query(`SELECT status FROM clean.analysis_jobs WHERE shop_domain = $1`, [SHOP])).rows[0];
  assert.equal(job.status, "failed");

  // No new work, even for the founder.
  for (const path of ["/sync/shopify", "/engine/atul/run", "/klaviyo/campaigns/from-engine"]) {
    const res = await fetch(`${api.base}${path}`, { method: "POST", headers: founder, body: JSON.stringify({ shopDomain: SHOP, campaign: {} }) });
    assert.equal(res.status, 403, path);
    assert.equal((await res.json()).code, "store_disabled", path);
  }
  // A fresh session cannot be created by signing in either.
  const signIn = await (async () => {
    const calls = stubShopifyExchange();
    try {
      const { nonce, state } = await startShopify();
      const res = await fetch(`${api.base}/oauth/shopify/callback?${shopifyCallbackQuery(state)}`, {
        redirect: "manual", headers: { cookie: `beaconai_oauth=${encodeURIComponent(nonce)}` },
      });
      return { res, calls };
    } finally {
      axios.post = saved.post;
    }
  })();
  assert.equal(signIn.res.status, 403);
  assert.ok(!(signIn.res.headers.get("set-cookie") || "").includes("beaconai_session="));

  // Enabling lifts the block; revoked sessions stay revoked.
  const enabled = await fetch(`${api.base}/admin/stores/${SHOP}/enable`, { method: "POST", headers: founder });
  assert.equal(enabled.status, 200);
  assert.equal(await sessionStatus(token), false);
  assert.equal(await sessionStatus((await createSession(SHOP)).token), true);
});

suite("a sync that outlives the store's access publishes nothing", async () => {
  await db.resetDatabase();
  await assert.rejects(
    () => runSync({
      shopDomain: SHOP, accessToken: "t", shopifyScope: "read_orders,read_all_orders",
      fetchData: async () => {
        await disableStore(SHOP);
        return db.shopifyPayload({ orders: db.ordersSpanning(200) });
      },
    }),
    (error) => error instanceof StoreDisabledError
  );
  const active = await query(`SELECT count(*)::int n FROM clean.active_sync WHERE shop_domain = $1`, [SHOP]);
  const orders = await query(`SELECT count(*)::int n FROM clean.orders WHERE shop_domain = $1`, [SHOP]);
  assert.equal(active.rows[0].n, 0);
  assert.equal(orders.rows[0].n, 0, "nothing from the fetch was written");
});

function signedWebhook(topic, payload, { secret = config.shopify.clientSecret, shop = SHOP, id = crypto.randomUUID() } = {}) {
  const body = Buffer.from(JSON.stringify(payload));
  return {
    body,
    headers: {
      "content-type": "application/json",
      "x-shopify-topic": topic,
      "x-shopify-shop-domain": shop,
      "x-shopify-webhook-id": id,
      "x-shopify-hmac-sha256": crypto.createHmac("sha256", secret).update(body).digest("base64"),
    },
  };
}

suite("uninstall ends access immediately; unsigned webhooks change nothing", async () => {
  await db.resetDatabase();
  await query(
    `INSERT INTO clean.connections (shop_domain, shopify_access_token, klaviyo_access_token, klaviyo_refresh_token)
     VALUES ($1, $2, $3, $4)`,
    [SHOP, encryptToken("shpat"), encryptToken("kl-access"), encryptToken("kl-refresh")]
  );
  await query(`INSERT INTO clean.customers (id, shop_domain, email, created_at) VALUES ('c1', $1, 'c1@example.com', NOW())`, [SHOP]);
  const { token } = await createSession(SHOP);

  const uninstall = signedWebhook("app/uninstalled", { id: 1, domain: SHOP });
  for (const tampered of [
    { ...uninstall.headers, "x-shopify-hmac-sha256": undefined },
    { ...uninstall.headers, "x-shopify-hmac-sha256": signedWebhook("app/uninstalled", { id: 1 }, { secret: "wrong" }).headers["x-shopify-hmac-sha256"] },
  ]) {
    const headers = Object.fromEntries(Object.entries(tampered).filter(([, v]) => v !== undefined));
    const res = await fetch(`${api.base}/webhooks/shopify`, { method: "POST", headers, body: uninstall.body });
    assert.equal(res.status, 401);
  }
  // A body changed after signing.
  const altered = await fetch(`${api.base}/webhooks/shopify`, { method: "POST", headers: uninstall.headers, body: Buffer.from(JSON.stringify({ id: 2 })) });
  assert.equal(altered.status, 401);
  assert.equal(await sessionStatus(token), true, "nothing changed");

  const res = await fetch(`${api.base}/webhooks/shopify`, { method: "POST", headers: uninstall.headers, body: uninstall.body });
  assert.equal(res.status, 200);
  assert.equal(await sessionStatus(token), false);
  const conn = (await query(`SELECT shopify_access_token, klaviyo_access_token, klaviyo_refresh_token FROM clean.connections WHERE shop_domain = $1`, [SHOP])).rows[0];
  assert.deepEqual(conn, { shopify_access_token: null, klaviyo_access_token: null, klaviyo_refresh_token: null });
  const access = (await query(`SELECT disabled_reason, uninstalled_at FROM clean.store_access WHERE shop_domain = $1`, [SHOP])).rows[0];
  assert.equal(access.disabled_reason, "uninstalled");
  assert.ok(access.uninstalled_at);
  const customers = await query(`SELECT count(*)::int n FROM clean.customers WHERE shop_domain = $1`, [SHOP]);
  assert.equal(customers.rows[0].n, 1, "data deletion follows the retention policy, not the webhook");

  // The founder cannot re-enable an uninstalled store; reinstalling does.
  const enable = await fetch(`${api.base}/admin/stores/${SHOP}/enable`, { method: "POST", headers: founder });
  assert.equal(enable.status, 409);
  stubShopifyExchange();
  try {
    const { nonce, state } = await startShopify();
    const reinstall = await fetch(`${api.base}/oauth/shopify/callback?${shopifyCallbackQuery(state)}`, {
      redirect: "manual", headers: { cookie: `beaconai_oauth=${encodeURIComponent(nonce)}` },
    });
    assert.equal(reinstall.status, 302);
    assert.ok(reinstall.headers.getSetCookie().some((c) => c.startsWith("beaconai_session=")));
  } finally {
    axios.post = saved.post;
  }
});

suite("privacy webhooks are recorded once, with only what identifies the subject", async () => {
  await db.resetDatabase();
  const payload = {
    shop_id: 9, shop_domain: SHOP,
    customer: { id: 77, email: "person@example.com", phone: "+10000000000" },
    orders_to_redact: [1001], extra_field: "not stored",
  };
  const request = signedWebhook("customers/redact", payload, { id: "webhook-1" });
  for (let i = 0; i < 2; i += 1) {
    const res = await fetch(`${api.base}/webhooks/shopify`, { method: "POST", headers: request.headers, body: request.body });
    assert.equal(res.status, 200);
  }
  const rows = (await query(`SELECT topic, payload FROM clean.privacy_requests WHERE shop_domain = $1`, [SHOP])).rows;
  assert.equal(rows.length, 1, "a redelivery is not a second request");
  assert.equal(rows[0].topic, "customers/redact");
  assert.equal(rows[0].payload.customer_id, 77);
  assert.deepEqual(rows[0].payload.orders, [1001]);
  assert.ok(!JSON.stringify(rows[0].payload).includes("not stored"));
});
