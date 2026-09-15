// Whether a store may be used, and what happens when it may not.
//
// Two ways a store stops: the founder disables it, or the merchant uninstalls
// the app. Both take effect at once: every session for the store is revoked,
// queued or running work is stopped, and no caller — merchant or founder — can
// start new sync, analysis or handoff work for it. Uninstalling also deletes the
// stored Shopify and Klaviyo credentials. Deleting the store's data is a separate
// step governed by the retention policy (docs/SECURITY_HARDENING_PLAN.md, PR B).

const { pool, query } = require("../db");

class StoreDisabledError extends Error {
  constructor(shopDomain, access) {
    super(access?.uninstalled_at
      ? "BeaconAI was uninstalled from this store. Reinstall it to continue."
      : "Access for this store is turned off. Contact your pilot contact.");
    this.name = "StoreDisabledError";
    this.code = "store_disabled";
    this.statusCode = 403;
    this.shopDomain = shopDomain;
  }
}

async function getStoreAccess(shopDomain, db = { query }) {
  if (!shopDomain) return null;
  const { rows } = await db.query(
    `SELECT shop_domain, disabled_at, disabled_reason, uninstalled_at FROM clean.store_access WHERE shop_domain = $1`,
    [shopDomain]
  );
  return rows[0] || null;
}

async function isStoreActive(shopDomain, db) {
  const access = await getStoreAccess(shopDomain, db);
  return !access?.disabled_at;
}

/** Throws StoreDisabledError unless the store may be used. `db` may be a transaction client. */
async function assertStoreActive(shopDomain, db) {
  const access = await getStoreAccess(shopDomain, db);
  if (access?.disabled_at) throw new StoreDisabledError(shopDomain, access);
}

async function revokeStoreSessions(shopDomain, reason, db = { query }) {
  const { rowCount } = await db.query(
    `UPDATE clean.sessions SET revoked_at = NOW(), revoked_reason = $2
      WHERE shop_domain = $1 AND revoked_at IS NULL`,
    [shopDomain, reason]
  );
  return rowCount;
}

// Work already under way is marked stopped. The in-process job keeps running
// until its next check (assertStoreActive before each persisting stage), and
// that check refuses to write.
async function stopStoreWork(shopDomain, reason, db = { query }) {
  const jobs = await db.query(
    `UPDATE clean.analysis_jobs SET status = 'failed', error = $2, finished_at = NOW()
      WHERE shop_domain = $1 AND status = 'running'`,
    [shopDomain, reason]
  );
  const syncs = await db.query(
    `UPDATE clean.sync_runs SET status = 'failed', failure_reason = $2, finished_at = NOW()
      WHERE shop_domain = $1 AND status = 'running'`,
    [shopDomain, reason]
  );
  return { analysisJobs: jobs.rowCount, syncRuns: syncs.rowCount };
}

async function inTransaction(fn) {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const result = await fn(client);
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK").catch(() => {});
    throw error;
  } finally {
    client.release();
  }
}

async function disableStore(shopDomain, { reason = "disabled_by_founder" } = {}) {
  return inTransaction(async (client) => {
    await client.query(
      `INSERT INTO clean.store_access (shop_domain, disabled_at, disabled_reason, updated_at)
       VALUES ($1, NOW(), $2, NOW())
       ON CONFLICT (shop_domain) DO UPDATE
         SET disabled_at = COALESCE(clean.store_access.disabled_at, NOW()),
             disabled_reason = EXCLUDED.disabled_reason, updated_at = NOW()`,
      [shopDomain, reason]
    );
    const sessionsRevoked = await revokeStoreSessions(shopDomain, reason, client);
    const stopped = await stopStoreWork(shopDomain, "Access for this store was turned off.", client);
    return { shopDomain, sessionsRevoked, ...stopped };
  });
}

// Lifts the block. Revoked sessions stay revoked: the merchant signs in again.
async function enableStore(shopDomain) {
  await query(
    `UPDATE clean.store_access SET disabled_at = NULL, disabled_reason = NULL, updated_at = NOW()
      WHERE shop_domain = $1`,
    [shopDomain]
  );
  return { shopDomain, enabled: true };
}

/**
 * The merchant removed the app from Shopify. Access ends now: sessions revoked,
 * work stopped, stored credentials deleted. Store data is kept until the
 * retention policy deletes it.
 */
async function uninstallStore(shopDomain) {
  return inTransaction(async (client) => {
    await client.query(
      `INSERT INTO clean.store_access (shop_domain, disabled_at, disabled_reason, uninstalled_at, updated_at)
       VALUES ($1, NOW(), 'uninstalled', NOW(), NOW())
       ON CONFLICT (shop_domain) DO UPDATE
         SET disabled_at = NOW(), disabled_reason = 'uninstalled', uninstalled_at = NOW(), updated_at = NOW()`,
      [shopDomain]
    );
    const sessionsRevoked = await revokeStoreSessions(shopDomain, "uninstalled", client);
    const stopped = await stopStoreWork(shopDomain, "BeaconAI was uninstalled from this store.", client);
    const tokens = await client.query(
      `UPDATE clean.connections
          SET shopify_access_token = NULL, shopify_scope = NULL,
              klaviyo_access_token = NULL, klaviyo_refresh_token = NULL,
              klaviyo_private_key = NULL, klaviyo_scope = NULL, klaviyo_expires_at = NULL,
              updated_at = NOW()
        WHERE shop_domain = $1`,
      [shopDomain]
    );
    return { shopDomain, sessionsRevoked, credentialsDeleted: tokens.rowCount > 0, ...stopped };
  });
}

// A completed Shopify install for a store that had uninstalled lifts that block.
// A founder disable is not lifted by the merchant signing in.
async function reactivateAfterReinstall(shopDomain) {
  await query(
    `UPDATE clean.store_access SET disabled_at = NULL, disabled_reason = NULL, updated_at = NOW()
      WHERE shop_domain = $1 AND disabled_reason = 'uninstalled'`,
    [shopDomain]
  );
}

module.exports = {
  StoreDisabledError,
  assertStoreActive,
  disableStore,
  enableStore,
  getStoreAccess,
  isStoreActive,
  reactivateAfterReinstall,
  revokeStoreSessions,
  stopStoreWork,
  uninstallStore,
};
