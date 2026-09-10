#!/usr/bin/env node
// Boots a disposable Postgres and the API against it, for browser-level checks
// that the HTTP tests cannot make — CORS being the obvious one, since it is
// enforced by the browser and invisible to a Node client.
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const net = require("node:net");

const EmbeddedPostgres = require("embedded-postgres").default || require("embedded-postgres");

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

async function main() {
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "beaconai-devstack-"));
  const pgPort = await freePort();
  const pg = new EmbeddedPostgres({
    databaseDir: dataDir, user: "postgres", password: "postgres",
    port: pgPort, persistent: false, onLog: () => {}, onError: () => {},
  });
  await pg.initialise();
  await pg.start();
  await pg.createDatabase("beaconai_dev");

  process.env.DATABASE_URL = `postgres://postgres:postgres@127.0.0.1:${pgPort}/beaconai_dev`;
  process.env.PGSSLMODE = "disable";
  process.env.PORT = process.env.PORT || "4000";
  process.env.SHOPIFY_SHOP_DOMAIN = process.env.SHOPIFY_SHOP_DOMAIN || "devstack.myshopify.com";

  const cleanup = async () => {
    await pg.stop().catch(() => {});
    fs.rmSync(dataDir, { recursive: true, force: true });
  };
  process.on("SIGINT", async () => { await cleanup(); process.exit(0); });
  process.on("SIGTERM", async () => { await cleanup(); process.exit(0); });

  console.log(`[devstack] postgres ${pgPort}, api ${process.env.PORT}`);
  require("../src/server.js");
}

main().catch((error) => { console.error("[devstack]", error.message); process.exit(1); });
