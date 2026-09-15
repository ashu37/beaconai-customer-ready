const { Pool } = require("pg");
const { config } = require("./config");

const sslMode = process.env.PGSSLMODE;

function poolFor(connectionString) {
  const usesSupabase = /supabase\.com/.test(connectionString || "");
  return new Pool({
    connectionString,
    connectionTimeoutMillis: Number(process.env.PG_CONNECTION_TIMEOUT_MS || 10000),
    idleTimeoutMillis: Number(process.env.PG_IDLE_TIMEOUT_MS || 30000),
    ssl: sslMode === "disable" ? false : usesSupabase ? { rejectUnauthorized: false } : undefined,
  });
}

// Requests run as the application role (DATABASE_URL).
const pool = poolFor(config.databaseUrl);

// Schema changes run as the table owner (MIGRATION_DATABASE_URL). The same pool
// when no separate owner connection is configured, as in development.
const migrationPool = config.migrationDatabaseUrl && config.migrationDatabaseUrl !== config.databaseUrl
  ? poolFor(config.migrationDatabaseUrl)
  : pool;

async function query(text, params) {
  return pool.query(text, params);
}

async function migrationQuery(text, params) {
  return migrationPool.query(text, params);
}

async function closePools() {
  await pool.end();
  if (migrationPool !== pool) await migrationPool.end();
}

module.exports = { closePools, migrationPool, migrationQuery, pool, query };
