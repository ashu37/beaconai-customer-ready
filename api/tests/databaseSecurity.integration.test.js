const test = require("node:test");
const assert = require("node:assert/strict");
const { Pool } = require("pg");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query, pool } = require("../src/db");
const { initSchema } = require("../src/schema");
const {
  applyAccessControls,
  databaseSecurityProblems,
  inspectDatabaseSecurity,
} = require("../src/services/databaseSecurity");

// PR A, A1: the application role, Supabase's API roles, grants, policies and
// row-level security, tested together. The disposable database mirrors Supabase
// by creating `anon` and `authenticated` and giving them the risky privileges a
// default project can have.

const APP = "beaconai_app";
let appPool;

async function ensureRole(sql) {
  await query(`DO $$ BEGIN ${sql}; EXCEPTION WHEN duplicate_object THEN NULL; END $$;`);
}

function urlAs(user, password) {
  const url = new URL(db.TEST_DATABASE_URL);
  url.username = user;
  url.password = password;
  return url.toString();
}

async function asRole(role, sql) {
  const client = await pool.connect();
  try {
    await client.query(`SET ROLE ${role}`);
    return await client.query(sql);
  } finally {
    await client.query("RESET ROLE").catch(() => {});
    client.release();
  }
}

test.before(async () => {
  if (!db.available) return;
  await ensureRole(`CREATE ROLE anon NOLOGIN`);
  await ensureRole(`CREATE ROLE authenticated NOLOGIN`);
  await ensureRole(`CREATE ROLE ${APP} LOGIN PASSWORD 'app-test-password' NOSUPERUSER NOBYPASSRLS`);
  await ensureRole(`CREATE ROLE accidental_reader NOLOGIN`);
  appPool = new Pool({ connectionString: urlAs(APP, "app-test-password") });
});
test.after(async () => {
  if (appPool) await appPool.end();
  if (db.available) await db.closeDatabase();
});

suite("the Supabase API roles get nothing, even after risky grants", async () => {
  await db.resetDatabase();
  // What a permissive project can hold before the controls run.
  await query(`GRANT USAGE ON SCHEMA clean, raw TO anon, authenticated`);
  await query(`GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA clean TO anon, authenticated`);
  await query(`INSERT INTO clean.customers (id, shop_domain, email, created_at) VALUES ('c1', 's.myshopify.com', 'c1@example.com', NOW())`);

  await initSchema();

  for (const role of ["anon", "authenticated"]) {
    await assert.rejects(() => asRole(role, `SELECT * FROM clean.customers`), /permission denied/, role);
    await assert.rejects(() => asRole(role, `SELECT * FROM clean.connections`), /permission denied/, role);
    await assert.rejects(() => asRole(role, `SELECT * FROM raw.shopify_events`), /permission denied/, role);
  }

  // A table created later does not inherit anything for them either.
  await query(`CREATE TABLE IF NOT EXISTS clean.later_table (id int)`);
  try {
    await assert.rejects(() => asRole("anon", `SELECT * FROM clean.later_table`), /permission denied/);
  } finally {
    await query(`DROP TABLE clean.later_table`);
  }
});

suite("the application role can do its work, and nothing beyond it", async () => {
  await db.resetDatabase();
  await appPool.query(`INSERT INTO clean.customers (id, shop_domain, email, created_at) VALUES ('c2', 's.myshopify.com', 'c2@example.com', NOW())`);
  const { rows } = await appPool.query(`SELECT email FROM clean.customers WHERE id = 'c2'`);
  assert.equal(rows[0].email, "c2@example.com");
  await appPool.query(`INSERT INTO clean.sessions (id, shop_domain, expires_at) VALUES ('s1', 's.myshopify.com', NOW() + INTERVAL '1 day')`);
  await appPool.query(`INSERT INTO clean.privacy_requests (shop_domain, topic) VALUES ('s.myshopify.com', 'shop/redact')`);
  await appPool.query(`DELETE FROM clean.customers WHERE id = 'c2'`);

  // No schema changes and no policy changes.
  await assert.rejects(() => appPool.query(`ALTER TABLE clean.customers ADD COLUMN sneaky text`), /must be owner|permission denied/);
  await assert.rejects(() => appPool.query(`ALTER TABLE clean.customers DISABLE ROW LEVEL SECURITY`), /must be owner|permission denied/);
  await assert.rejects(() => appPool.query(`CREATE TABLE clean.app_made (id int)`), /permission denied/);
});

suite("row-level security holds for any role without the application policy", async () => {
  await db.resetDatabase();
  await query(`INSERT INTO clean.customers (id, shop_domain, email, created_at) VALUES ('c3', 's.myshopify.com', 'c3@example.com', NOW())`);
  // Someone grants a role table access by mistake.
  await query(`GRANT USAGE ON SCHEMA clean TO accidental_reader`);
  await query(`GRANT SELECT ON clean.customers TO accidental_reader`);
  try {
    const { rows } = await asRole("accidental_reader", `SELECT * FROM clean.customers`);
    assert.equal(rows.length, 0, "the grant alone reads nothing: no policy names this role");
  } finally {
    await query(`REVOKE ALL ON clean.customers FROM accidental_reader`);
    await query(`REVOKE ALL ON SCHEMA clean FROM accidental_reader`);
  }
});

suite("the self-check passes for the application role and names each weakness otherwise", async () => {
  await db.resetDatabase();

  const healthy = await inspectDatabaseSecurity((text, params) => appPool.query(text, params), { appRole: APP });
  assert.deepEqual(databaseSecurityProblems(healthy), []);
  assert.equal(healthy.runtimeRole.name, APP);
  assert.equal(healthy.apiRoles.anon.tableGrants, 0);
  assert.deepEqual(healthy.rlsDisabled, []);

  // The owner / superuser connection is exactly what production must not use.
  const owner = databaseSecurityProblems(await inspectDatabaseSecurity(query, { appRole: APP }));
  assert.ok(owner.some((p) => /superuser/.test(p)));
  assert.ok(owner.some((p) => /not beaconai_app/.test(p)));

  await query(`ALTER ROLE ${APP} BYPASSRLS`);
  try {
    const bypass = databaseSecurityProblems(await inspectDatabaseSecurity((t, p) => appPool.query(t, p), { appRole: APP }));
    assert.ok(bypass.some((p) => /BYPASSRLS/.test(p)), bypass.join(" | "));
  } finally {
    await query(`ALTER ROLE ${APP} NOBYPASSRLS`);
  }

  await query(`ALTER TABLE clean.shop OWNER TO ${APP}`);
  try {
    const owns = databaseSecurityProblems(await inspectDatabaseSecurity((t, p) => appPool.query(t, p), { appRole: APP }));
    assert.ok(owns.some((p) => /owns 1 application table/.test(p)), owns.join(" | "));
  } finally {
    await query(`ALTER TABLE clean.shop OWNER TO CURRENT_USER`);
  }

  await query(`GRANT SELECT ON clean.orders TO anon`);
  await query(`ALTER TABLE clean.refunds DISABLE ROW LEVEL SECURITY`);
  try {
    const leaky = databaseSecurityProblems(await inspectDatabaseSecurity((t, p) => appPool.query(t, p), { appRole: APP }));
    assert.ok(leaky.some((p) => /anon holds 1 table privilege/.test(p)), leaky.join(" | "));
    assert.ok(leaky.some((p) => /Row-level security is off on: clean\.refunds/.test(p)), leaky.join(" | "));
  } finally {
    await applyAccessControls(query, { appRole: APP });
  }
  assert.deepEqual(databaseSecurityProblems(await inspectDatabaseSecurity((t, p) => appPool.query(t, p), { appRole: APP })), []);
});
