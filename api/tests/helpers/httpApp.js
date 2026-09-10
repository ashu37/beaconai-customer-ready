// Mounts the real router on an ephemeral port so route-level behaviour can be
// tested through actual HTTP — middleware, status codes, JSON bodies and all.
// The alternative, calling the service functions directly, cannot catch a route
// that verifies one thing and then acts on another, which is the class of bug
// these tests exist for.
const express = require("express");
const http = require("node:http");

async function startApi() {
  const { router } = require("../../src/routes");
  const app = express();
  app.use(express.json({ limit: "10mb" }));
  app.use("/api", router);

  const server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  const base = `http://127.0.0.1:${port}/api`;

  // Tests run against the REAL access boundary. A session is derived from the
  // shop the request is about, so tests read as "this shop's merchant does X"
  // rather than bypassing the guard. Pass `session: null` to be anonymous, or a
  // different shop to be someone else.
  function authHeaders(session, inferred) {
    const { issueSession } = require("../../src/services/sessionService");
    if (session === null) return {};
    const shop = session || inferred;
    return shop ? { authorization: `Bearer ${issueSession(shop)}` } : {};
  }

  return {
    base,
    async post(path, body, { session } = {}) {
      const response = await fetch(`${base}${path}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(session, body?.shopDomain),
        },
        body: JSON.stringify(body),
      });
      return { status: response.status, body: await response.json() };
    },
    async get(path, { session } = {}) {
      // Infer the shop from a /:shopDomain path segment or a shopDomain query,
      // so existing tests keep meaning what they meant.
      const inferred = decodeURIComponent(
        path.match(/[?&]shopDomain=([^&]+)/)?.[1]
        || path.match(/\/(?:campaigns|results|sync\/status|engine\/input|stats\/series|engine\/atul\/latest)\/([^/?]+)/)?.[1]
        || ""
      ) || null;
      const response = await fetch(`${base}${path}`, { headers: authHeaders(session, inferred) });
      return { status: response.status, body: await response.json() };
    },
    async close() {
      await new Promise((resolve) => server.close(resolve));
    },
  };
}

module.exports = { startApi };
