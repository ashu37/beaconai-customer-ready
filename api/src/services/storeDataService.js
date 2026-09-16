// Everything BeaconAI holds for one store, in one place: what it is, how to
// hand it to the merchant, and how to erase it.
//
// The list below is the single definition. It is checked against the database
// catalogue at run time (`assertEveryTableIsAccountedFor`), so a table added
// later without a rule here fails loudly instead of being quietly left behind
// when a merchant asks to be deleted. That check is the point of the design:
// the tables that get missed are always the derived ones nobody remembers —
// recipients, exclusions, measurements, audiences — and each of those is keyed
// by a campaign or a run, not by the shop.
//
// Deletion order is explicit and does not rely on ON DELETE CASCADE: some of
// these foreign keys cascade and some are NO ACTION, and a reader should not
// have to know which to see that the order is right.

const fs = require("node:fs/promises");
const path = require("node:path");

const { pool, query } = require("../db");

const DIRECT = "shop_domain = $1";
const VIA_CAMPAIGN = "campaign_id IN (SELECT id FROM clean.campaigns WHERE shop_domain = $1)";
const VIA_RUN = "run_id IN (SELECT run_id FROM clean.engine_run_snapshots WHERE shop_domain = $1)";

/**
 * Children first, then their parents. `retain` marks a table deletion
 * deliberately leaves alone, with the reason; everything else is erased.
 */
const STORE_TABLES = [
  // Campaign-derived. None of these carries a shop_domain.
  { table: "clean.campaign_measurements", scope: VIA_CAMPAIGN },
  { table: "clean.campaign_recipient_exclusions", scope: VIA_CAMPAIGN },
  { table: "clean.campaign_recipients", scope: VIA_CAMPAIGN, sensitive: ["email"] },
  { table: "clean.campaigns", scope: DIRECT },

  // Run-derived.
  { table: "clean.engine_audiences", scope: VIA_RUN },
  { table: "clean.engine_run_snapshots", scope: DIRECT },
  { table: "clean.analysis_jobs", scope: DIRECT },

  // Sync.
  { table: "clean.active_sync", scope: DIRECT },
  { table: "clean.sync_runs", scope: DIRECT },

  // Brand design.
  { table: "clean.brand_email_active", scope: DIRECT },
  { table: "clean.brand_email_templates", scope: DIRECT },

  // Provider assets.
  { table: "clean.klaviyo_assets", scope: DIRECT },

  // Store records.
  { table: "clean.order_line_items", scope: DIRECT },
  { table: "clean.refunds", scope: DIRECT },
  { table: "clean.refunds_quarantine", scope: DIRECT },
  { table: "clean.orders", scope: DIRECT },
  { table: "clean.customers", scope: DIRECT, sensitive: ["email"] },
  { table: "clean.product_variants", scope: DIRECT },
  { table: "clean.products", scope: DIRECT },
  { table: "clean.shop", scope: DIRECT },

  // Raw event log.
  { table: "raw.shopify_events", scope: DIRECT },
  { table: "raw.klaviyo_events", scope: DIRECT },

  // Access.
  { table: "clean.sessions", scope: DIRECT },
  { table: "clean.oauth_states", scope: DIRECT },
  { table: "clean.store_access", scope: DIRECT },
  // Tokens are encrypted at rest; export redacts them rather than handing a
  // merchant a file that can act on their Shopify and Klaviyo accounts.
  { table: "clean.connections", scope: DIRECT, secret: true },

  // Deliberately kept. It records that a privacy request arrived and when it
  // was completed — the evidence the deletion happened — and holds no customer
  // data beyond the shop domain and the subject identifiers Shopify sent.
  // Those identifiers are cleared when the request completes; see
  // completePrivacyRequest.
  {
    table: "clean.privacy_requests",
    scope: DIRECT,
    retain: "the record that a request was received and completed",
  },
];

const BY_TABLE = new Map(STORE_TABLES.map((entry) => [entry.table, entry]));

/**
 * Fails when the catalogue holds a clean/raw table this module says nothing
 * about. Called by both export and deletion, so neither can silently under-
 * report — "we deleted everything" has to mean everything that exists.
 */
async function assertEveryTableIsAccountedFor(run = query) {
  const { rows } = await run(
    `SELECT n.nspname || '.' || c.relname AS name
       FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE c.relkind IN ('r', 'p') AND n.nspname IN ('clean', 'raw')
      ORDER BY 1`
  );
  const unknown = rows.map((r) => r.name).filter((name) => !BY_TABLE.has(name));
  if (unknown.length) {
    throw new Error(
      `storeDataService does not know how ${unknown.join(", ")} is scoped to a store. ` +
      `Add it to STORE_TABLES with the column that ties a row to a shop (and whether ` +
      `deletion should erase or retain it) before exporting or deleting store data.`
    );
  }
}

/** Row counts per table for one store, for a report or a confirmation. */
async function countStoreData(shopDomain, run = query) {
  await assertEveryTableIsAccountedFor(run);
  const counts = {};
  for (const { table, scope } of STORE_TABLES) {
    const { rows } = await run(`SELECT count(*)::int AS n FROM ${table} WHERE ${scope}`, [shopDomain]);
    counts[table] = rows[0].n;
  }
  return counts;
}

function redactSecrets(entry, row) {
  if (!entry.secret) return row;
  const out = {};
  for (const [key, value] of Object.entries(row)) {
    const isSecret = /token|key|secret/i.test(key);
    out[key] = isSecret ? (value == null ? null : "[redacted]") : value;
  }
  return out;
}

/**
 * The store's data, written as one JSON file per table plus a manifest.
 *
 * Access tokens are redacted: this file goes to the merchant, and a copy of
 * their Shopify and Klaviyo credentials is not theirs to be handed in a
 * download — they hold those in the accounts themselves.
 */
async function exportStoreData(shopDomain, outDir) {
  await assertEveryTableIsAccountedFor();
  await fs.mkdir(outDir, { recursive: true });

  const files = [];
  const counts = {};
  for (const entry of STORE_TABLES) {
    const { rows } = await query(`SELECT * FROM ${entry.table} WHERE ${entry.scope}`, [shopDomain]);
    const name = `${entry.table.replace(".", "_")}.json`;
    await fs.writeFile(
      path.join(outDir, name),
      JSON.stringify(rows.map((row) => redactSecrets(entry, row)), null, 2)
    );
    counts[entry.table] = rows.length;
    files.push(name);
  }

  const manifest = {
    shopDomain,
    exportedAt: new Date().toISOString(),
    counts,
    files,
    notes: [
      "Access tokens are redacted: they are held in your Shopify and Klaviyo accounts, not here.",
      "Campaign recipients, exclusions, measurements and engine audiences are keyed by campaign or run, not by shop; they are included.",
    ],
  };
  await fs.writeFile(path.join(outDir, "manifest.json"), JSON.stringify(manifest, null, 2));
  return manifest;
}

/**
 * Erase one store, in one transaction. Either all of it goes or none of it
 * does — a half-deleted store is worse than an undeleted one, because the next
 * attempt reports counts that look finished.
 *
 * @returns {Promise<{shopDomain, deleted: object, retained: object, engineFiles: string[]}>}
 */
async function deleteStoreData(shopDomain, { engineDir = null } = {}) {
  const client = await pool.connect();
  const run = (text, params) => client.query(text, params);
  let deleted = {};
  let storeIds = [];
  try {
    await assertEveryTableIsAccountedFor(run);
    await run("BEGIN");

    // Read before deleting: the engine's directories are named by store_id,
    // which only the snapshot rows know.
    const ids = await run(
      `SELECT DISTINCT store_id FROM clean.engine_run_snapshots WHERE shop_domain = $1 AND store_id IS NOT NULL`,
      [shopDomain]
    );
    storeIds = ids.rows.map((r) => r.store_id);

    for (const { table, scope, retain } of STORE_TABLES) {
      if (retain) continue;
      const result = await run(`DELETE FROM ${table} WHERE ${scope}`, [shopDomain]);
      deleted[table] = result.rowCount;
    }
    await run("COMMIT");
  } catch (error) {
    await run("ROLLBACK").catch(() => {});
    throw error;
  } finally {
    client.release();
  }

  // Outside the transaction: a filesystem removal cannot be rolled back, so it
  // follows the commit rather than risking files removed for a store still in
  // the database.
  const engineFiles = [];
  const root = engineDir || process.env.BEACONAI_ENGINE_DIR;
  if (root) {
    for (const storeId of storeIds) {
      // storeId comes from our own column, but it becomes a path here, so it is
      // resolved and checked rather than trusted.
      const dir = path.resolve(root, "data", storeId);
      const base = path.resolve(root, "data");
      if (dir !== base && dir.startsWith(base + path.sep)) {
        await fs.rm(dir, { recursive: true, force: true });
        engineFiles.push(dir);
      }
    }
  }

  const retained = {};
  for (const { table, scope, retain } of STORE_TABLES) {
    if (!retain) continue;
    const { rows } = await query(`SELECT count(*)::int AS n FROM ${table} WHERE ${scope}`, [shopDomain]);
    retained[table] = { rows: rows[0].n, reason: retain };
  }

  return { shopDomain, deleted, retained, engineFiles };
}

module.exports = {
  STORE_TABLES,
  assertEveryTableIsAccountedFor,
  countStoreData,
  deleteStoreData,
  exportStoreData,
};
