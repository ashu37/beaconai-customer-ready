const test = require("node:test");
const assert = require("node:assert/strict");

const { seedRefusal } = require("../src/scripts/seedGuard");

// PR B, B2: the seed writes fabricated orders and campaigns. The case the guard
// exists for is a laptop whose api/.env points at the hosted database.

test("a database on this machine is seedable", () => {
  for (const url of [
    "postgres://postgres:postgres@localhost:5432/beaconai",
    "postgres://postgres@127.0.0.1:5432/beaconai",
  ]) {
    assert.equal(seedRefusal({ DATABASE_URL: url }), null, url);
  }
});

test("a hosted database is refused, and the message says why and how", () => {
  const refusal = seedRefusal({
    DATABASE_URL: "postgres://beaconai_app.abc:pw@aws-0-us-east-1.pooler.supabase.com:5432/postgres",
  });
  assert.ok(refusal, "not refused");
  assert.match(refusal, /pooler\.supabase\.com/);
  assert.match(refusal, /SEED_ALLOW_REMOTE=1/);
  // The reason, not just the rule: this is what the founder needs to weigh.
  assert.match(refusal, /audiences the engine computes/);
});

test("NODE_ENV is not what decides it", () => {
  // The dangerous run has no NODE_ENV at all.
  const refusal = seedRefusal({
    DATABASE_URL: "postgres://u:p@db.example.com:5432/postgres",
    NODE_ENV: "development",
  });
  assert.ok(refusal, "a remote database is refused whatever NODE_ENV says");
});

test("an unset or unreadable connection string is refused, not assumed local", () => {
  assert.match(seedRefusal({}), /DATABASE_URL is not set/);
  assert.ok(seedRefusal({ DATABASE_URL: "host=/var/run/postgresql dbname=beaconai" }));
});

test("the override is explicit", () => {
  assert.equal(
    seedRefusal({ DATABASE_URL: "postgres://u:p@db.example.com:5432/postgres", SEED_ALLOW_REMOTE: "1" }),
    null
  );
});
