const { Pool } = require("pg");
const { config } = require("./config");

const usesSupabase = /supabase\.com/.test(config.databaseUrl || "");
const sslMode = process.env.PGSSLMODE;

const pool = new Pool({
  connectionString: config.databaseUrl,
  connectionTimeoutMillis: Number(process.env.PG_CONNECTION_TIMEOUT_MS || 10000),
  idleTimeoutMillis: Number(process.env.PG_IDLE_TIMEOUT_MS || 30000),
  ssl: sslMode === "disable" ? false : usesSupabase ? { rejectUnauthorized: false } : undefined,
});

async function query(text, params) {
  return pool.query(text, params);
}

module.exports = { pool, query };
