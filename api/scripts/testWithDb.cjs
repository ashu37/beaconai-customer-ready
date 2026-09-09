#!/usr/bin/env node
// Runs the test suite against a REAL, disposable Postgres.
//
// embedded-postgres unpacks an actual postgres binary into a temp directory, so
// advisory locks, transactional DDL, JSONB and window functions all behave as
// they do in production — which matters, because most of what these tests check
// is transaction and locking behaviour that a SQL emulator would fake.
//
// The cluster is created fresh, used, and deleted. It never touches a
// configured DATABASE_URL: TEST_DATABASE_URL is what the suite reads, and it is
// set here to the throwaway cluster.
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");

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
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "beaconai-testdb-"));
  const port = await freePort();
  const pg = new EmbeddedPostgres({
    databaseDir: dataDir,
    user: "postgres",
    password: "postgres",
    port,
    persistent: false,
    onLog: () => {},
    onError: () => {},
  });

  let started = false;
  let code = 1;
  try {
    await pg.initialise();
    await pg.start();
    started = true;
    await pg.createDatabase("beaconai_test");

    const url = `postgres://postgres:postgres@127.0.0.1:${port}/beaconai_test`;
    console.log(`[test] disposable postgres on port ${port}`);

    code = await new Promise((resolve) => {
      const child = spawn(
        process.execPath,
        [
          "--test",
          // One database, shared by every file, and each integration file
          // truncates before it runs. In parallel they wipe each other's rows
          // mid-test and fail in ways that look like product bugs.
          "--test-concurrency=1",
          ...(process.argv.slice(2).length ? process.argv.slice(2) : ["tests/**/*.test.js"]),
        ],
        {
          cwd: path.resolve(__dirname, ".."),
          stdio: "inherit",
          env: { ...process.env, TEST_DATABASE_URL: url, PGSSLMODE: "disable" },
        }
      );
      child.on("close", resolve);
    });
  } finally {
    if (started) await pg.stop().catch(() => {});
    fs.rmSync(dataDir, { recursive: true, force: true });
  }
  process.exit(code);
}

main().catch((error) => {
  console.error("[test] could not start the disposable database:", error.message);
  process.exit(1);
});
