const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const http = require("node:http");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { config } = require("../src/config");
const {
  buildKlaviyoStartUrl,
  handleKlaviyoCallback,
  resolveStoredKlaviyoToken,
} = require("../src/services/oauthService");

const SHOP = "pkce-shop.myshopify.com";

// Klaviyo's token endpoint, close enough to answer the two requests this flow
// makes and to record exactly what was sent. What the exchange carries is the
// whole point of PKCE, so a test that replaced this function could not see it.
async function startFakeTokenEndpoint({ status = 200, body = null } = {}) {
  const requests = [];
  const server = http.createServer((req, res) => {
    let raw = "";
    req.on("data", (chunk) => { raw += chunk; });
    req.on("end", () => {
      requests.push({
        path: req.url,
        authorization: req.headers.authorization,
        form: Object.fromEntries(new URLSearchParams(raw)),
      });
      res.writeHead(status, { "content-type": "application/json" });
      res.end(JSON.stringify(body || {
        access_token: `access-${requests.length}`,
        refresh_token: `refresh-${requests.length}`,
        expires_in: 3600,
        scope: "accounts:read campaigns:write",
      }));
    });
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));

  const previous = { tokenUrl: config.klaviyo.tokenUrl, id: config.klaviyo.clientId, secret: config.klaviyo.clientSecret };
  config.klaviyo.tokenUrl = `http://127.0.0.1:${server.address().port}/oauth/token`;
  config.klaviyo.clientId = "test-client-id";
  config.klaviyo.clientSecret = "test-client-secret";

  return {
    requests,
    async close() {
      Object.assign(config.klaviyo, { tokenUrl: previous.tokenUrl, clientId: previous.id, clientSecret: previous.secret });
      await new Promise((resolve) => server.close(resolve));
    },
  };
}

function stateFrom(url) {
  return new URL(url).searchParams.get("state");
}

suite("the authorization link carries the challenge for a verifier we kept", async () => {
  await db.resetDatabase();
  const fake = await startFakeTokenEndpoint();
  try {
    const url = new URL(await buildKlaviyoStartUrl({ shopDomain: SHOP, returnTo: null }));

    assert.equal(url.searchParams.get("code_challenge_method"), "S256");
    const challenge = url.searchParams.get("code_challenge");
    assert.ok(challenge, "the authorization request carries a challenge");
    // Only the challenge travels through the browser; the verifier stays here.
    assert.ok(!url.toString().includes("code_verifier"));

    // The stored verifier is encrypted at rest, and hashes to the challenge
    // that was sent — so the two really are a pair.
    const { rows } = await query(
      `SELECT code_verifier FROM clean.oauth_states WHERE state = $1`,
      [url.searchParams.get("state")]
    );
    assert.ok(rows[0].code_verifier.startsWith("v1:"), "stored encrypted, not in the clear");

    const exchange = await handleKlaviyoCallback({ state: stateFrom(url.toString()), code: "auth-code" });
    assert.equal(exchange.shopDomain, SHOP);
    const sentVerifier = fake.requests[0].form.code_verifier;
    assert.ok(sentVerifier.length >= 43 && sentVerifier.length <= 128, `verifier length ${sentVerifier.length} is within 43-128`);
    assert.equal(
      crypto.createHash("sha256").update(sentVerifier).digest("base64url"),
      challenge,
      "the verifier sent at exchange matches the challenge sent at authorize"
    );
  } finally {
    await fake.close();
  }
});

suite("two connection attempts never share a verifier", async () => {
  await db.resetDatabase();
  const fake = await startFakeTokenEndpoint();
  try {
    const first = new URL(await buildKlaviyoStartUrl({ shopDomain: SHOP, returnTo: null }));
    const second = new URL(await buildKlaviyoStartUrl({ shopDomain: SHOP, returnTo: null }));
    assert.notEqual(first.searchParams.get("code_challenge"), second.searchParams.get("code_challenge"));
    assert.notEqual(first.searchParams.get("state"), second.searchParams.get("state"));
  } finally {
    await fake.close();
  }
});

suite("a state cannot be replayed, and one without a verifier is refused", async () => {
  await db.resetDatabase();
  const fake = await startFakeTokenEndpoint();
  try {
    const url = await buildKlaviyoStartUrl({ shopDomain: SHOP, returnTo: null });
    const state = stateFrom(url);
    await handleKlaviyoCallback({ state, code: "auth-code" });

    // Consumed. A second callback carrying it is not another connection.
    await assert.rejects(
      () => handleKlaviyoCallback({ state, code: "auth-code" }),
      /missing, expired, or already used/
    );

    // A row written without a verifier (anything predating PKCE) is refused
    // here rather than sent to Klaviyo to be refused there.
    await query(
      `INSERT INTO clean.oauth_states (state, provider, shop_domain, expires_at)
       VALUES ('legacy-state', 'klaviyo', $1, NOW() + INTERVAL '5 minutes')`,
      [SHOP]
    );
    const before = fake.requests.length;
    await assert.rejects(
      () => handleKlaviyoCallback({ state: "legacy-state", code: "auth-code" }),
      /Start connecting Klaviyo again/
    );
    assert.equal(fake.requests.length, before, "and Klaviyo was never asked");
  } finally {
    await fake.close();
  }
});

suite("a refresh renews the token and sends no verifier", async () => {
  await db.resetDatabase();
  const fake = await startFakeTokenEndpoint();
  try {
    const url = await buildKlaviyoStartUrl({ shopDomain: SHOP, returnTo: null });
    await handleKlaviyoCallback({ state: stateFrom(url), code: "auth-code" });

    // The stored token is about to expire, which is what triggers a refresh.
    await query(
      `UPDATE clean.connections SET klaviyo_expires_at = NOW() - INTERVAL '1 minute' WHERE shop_domain = $1`,
      [SHOP]
    );

    const token = await resolveStoredKlaviyoToken(SHOP);
    const refresh = fake.requests[1];
    assert.equal(refresh.form.grant_type, "refresh_token");
    assert.equal(refresh.form.refresh_token, "refresh-1", "the stored refresh token, decrypted");
    assert.equal(refresh.form.code_verifier, undefined, "a refresh carries no verifier");
    assert.equal(
      refresh.authorization,
      `Basic ${Buffer.from("test-client-id:test-client-secret").toString("base64")}`
    );
    assert.equal(token, "access-2", "the caller gets the renewed token");
  } finally {
    await fake.close();
  }
});
