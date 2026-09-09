const { pool, query } = require("../db");
const { fetchShopifyData } = require("./shopifyClient");
const {
  saveRawShopifyData,
  upsertAllShopifyData,
  getEngineInput,
} = require("./shopifyRepository");
const { buildEngineInputSnapshot, SNAPSHOT_SCHEMA_VERSION } = require("./engineInputSnapshot");

// How much order history the ENGINE needs, taken from the engine, not invented
// here. engine/src/profile/builder.py::_annualized_gmv_from_orders returns
// `insufficient_history` below 90 days and annualizes from L90/L180/TTM above
// it; engine/src/utils.py's window policy tops out at L90. So 90 days is the
// point below which the engine cannot characterise the store at all, and 180 is
// the point where it stops extrapolating a quarter into a year.
const REQUIRED_COVERAGE_DAYS = 90;
const PREFERRED_COVERAGE_DAYS = 180;

// Shopify hides orders older than 60 days from apps without `read_all_orders`.
// A store with exactly ~60 days of visible history has almost certainly hit
// that, and the merchant deserves to be told which of the two it is: "your
// store is new" and "we are not allowed to read your history" look identical in
// the data and have opposite remedies.
const SHOPIFY_DEFAULT_ORDER_WINDOW_DAYS = 60;
const ALL_ORDERS_SCOPE = "read_all_orders";

class SyncNotReadyError extends Error {
  constructor(readiness) {
    super(readiness.reasons[0]?.message || "Store data is not ready for analysis.");
    this.name = "SyncNotReadyError";
    this.statusCode = 409;
    this.readiness = readiness;
  }
}

function fail(code, message, detail = {}) {
  return { code, message, ...detail };
}

// Validation that can be decided from the fetch alone, before anything is
// written. Truncation is the headline case: an explicit `limit` that stops
// mid-resource returns 200 OK with a plausible-looking row count.
function validateFetch(data, requestedLimit) {
  const failures = [];

  if (!data.shop) {
    failures.push(fail("shop_missing", "Shopify did not return the shop record."));
  }

  for (const [name, meta] of Object.entries(data.resources || {})) {
    if (name === "shop") continue;
    if (meta.truncated) {
      failures.push(
        fail("resource_truncated", `The ${name} fetch stopped at the requested limit with more pages available.`, {
          resource: name,
          fetched: meta.fetched,
          requestedCap: meta.requestedCap,
        })
      );
    }
  }

  if ((data.orders || []).length === 0) {
    failures.push(fail("no_orders", "The store returned no orders, so there is nothing to analyse."));
  }

  return { failures, requestedLimit: requestedLimit == null ? null : String(requestedLimit) };
}

// Validation that needs the normalized input: how much history the engine will
// actually see. `shopifyScope` is the granted scope string, used only to explain
// short coverage — never to assert coverage we did not observe.
function validateCoverage(coverage, shopifyScope) {
  const failures = [];

  if (!coverage || coverage.known !== true) {
    // Unknown coverage is not verified coverage. It is emphatically not zero.
    failures.push(fail("coverage_unknown", "No order in this sync carries a readable date, so the covered period is unknown."));
    return failures;
  }

  if (coverage.daysCovered < REQUIRED_COVERAGE_DAYS) {
    const scopes = String(shopifyScope || "").split(/[,\s]+/).filter(Boolean);
    const missingAllOrders = !scopes.includes(ALL_ORDERS_SCOPE);
    const looksLikeScopeCeiling =
      missingAllOrders && coverage.daysCovered >= SHOPIFY_DEFAULT_ORDER_WINDOW_DAYS - 5;

    failures.push(
      fail(
        "coverage_below_required",
        looksLikeScopeCeiling
          ? `Only ${coverage.daysCovered} days of orders are visible, which is the ceiling Shopify applies without the ${ALL_ORDERS_SCOPE} scope. The engine needs ${REQUIRED_COVERAGE_DAYS}.`
          : `Only ${coverage.daysCovered} days of order history are available; the engine needs ${REQUIRED_COVERAGE_DAYS}.`,
        {
          daysCovered: coverage.daysCovered,
          requiredDays: REQUIRED_COVERAGE_DAYS,
          likelyScopeCeiling: looksLikeScopeCeiling,
          missingScope: looksLikeScopeCeiling ? ALL_ORDERS_SCOPE : null,
        }
      )
    );
  }

  return failures;
}

function declaredCoverage(coverage, shopifyScope) {
  const scopes = String(shopifyScope || "").split(/[,\s]+/).filter(Boolean);
  return {
    ...coverage,
    requiredDays: REQUIRED_COVERAGE_DAYS,
    preferredDays: PREFERRED_COVERAGE_DAYS,
    meetsRequired: coverage?.known === true && coverage.daysCovered >= REQUIRED_COVERAGE_DAYS,
    meetsPreferred: coverage?.known === true && coverage.daysCovered >= PREFERRED_COVERAGE_DAYS,
    // What we were ALLOWED to request, recorded so a short history can later be
    // attributed to permission rather than to the store.
    grantedAllOrdersScope: scopes.length ? scopes.includes(ALL_ORDERS_SCOPE) : null,
  };
}

async function beginSyncRun({ shopDomain, requestedLimit }) {
  const { rows } = await query(
    `INSERT INTO clean.sync_runs (shop_domain, status, schema_version, requested_limit)
     VALUES ($1, 'running', $2, $3)
     RETURNING id, started_at`,
    [shopDomain, SNAPSHOT_SCHEMA_VERSION, requestedLimit == null ? null : String(requestedLimit)]
  );
  return rows[0];
}

// Terminal status for a sync that did not publish. Runs on the POOL, never on
// the transaction that just rolled back — otherwise the record of the failure
// would be discarded along with the failure.
async function finishSyncRun(id, { status, failureReason, validationFailures, resourceManifest, declaredCoverage: coverage }) {
  await query(
    `UPDATE clean.sync_runs
        SET status = $2,
            finished_at = NOW(),
            failure_reason = $3,
            validation_failures = COALESCE($4::jsonb, validation_failures),
            resource_manifest = COALESCE($5::jsonb, resource_manifest),
            declared_coverage = COALESCE($6::jsonb, declared_coverage)
      WHERE id = $1`,
    [
      id,
      status,
      failureReason || null,
      validationFailures ? JSON.stringify(validationFailures) : null,
      resourceManifest ? JSON.stringify(resourceManifest) : null,
      coverage ? JSON.stringify(coverage) : null,
    ]
  );
}

/**
 * Fetch a store and publish it, or refuse to.
 *
 * The transaction below writes the clean tables, reads the normalized input
 * back out of them, validates it, and only then commits. Publishing inside the
 * transaction and validating the read-back is deliberate: it is the only way
 * the snapshot is built from exactly the rows an analysis would later read,
 * with no second projection to drift. Nothing is visible to any other
 * transaction until COMMIT, so an incomplete fetch still never becomes
 * published data — it is rolled back whole, and the previous complete snapshot
 * survives untouched.
 */
async function runSync({ shopDomain, accessToken, limit, shopifyScope, fetchData = fetchShopifyData }) {
  const run = await beginSyncRun({ shopDomain, requestedLimit: limit });

  let data;
  try {
    data = await fetchData({ shopDomain, accessToken, limit });
  } catch (error) {
    const reason = error.response?.data ? JSON.stringify(error.response.data) : error.message;
    await finishSyncRun(run.id, { status: "failed", failureReason: reason });
    error.syncRunId = run.id;
    throw error;
  }

  const resourceManifest = data.resources || {};
  const fetchCheck = validateFetch(data, limit);

  if (fetchCheck.failures.length) {
    await finishSyncRun(run.id, {
      status: "incomplete",
      failureReason: fetchCheck.failures[0].code,
      validationFailures: fetchCheck.failures,
      resourceManifest,
    });
    return { published: false, syncRunId: run.id, status: "incomplete", validationFailures: fetchCheck.failures, resourceManifest };
  }

  const client = await pool.connect();
  let outcome;
  try {
    await client.query("BEGIN");
    // Serializes publication per shop for the rest of this transaction. Two
    // syncs of the same store can fetch concurrently; only one can publish.
    await client.query("SELECT pg_advisory_xact_lock(hashtext($1))", [shopDomain]);

    // An older sync must not overwrite a newer one. Compare start times, not
    // finish times: the sync that began later saw the newer store.
    const active = await client.query(
      `SELECT sync_run_id, started_at FROM clean.active_sync WHERE shop_domain = $1`,
      [shopDomain]
    );
    const activeStartedAt = active.rows[0]?.started_at;
    if (activeStartedAt && new Date(activeStartedAt) > new Date(run.started_at)) {
      throw Object.assign(new Error("A newer sync has already published for this shop."), {
        code: "superseded_by_newer_sync",
      });
    }

    await saveRawShopifyData(shopDomain, data, client);
    await upsertAllShopifyData(shopDomain, data, client);

    const input = await getEngineInput(shopDomain, client);
    const snapshot = buildEngineInputSnapshot(input);
    const coverage = declaredCoverage(snapshot.coverage, shopifyScope);
    const coverageFailures = validateCoverage(snapshot.coverage, shopifyScope);

    if (coverageFailures.length) {
      throw Object.assign(new Error(coverageFailures[0].message), {
        code: "insufficient_coverage",
        validationFailures: coverageFailures,
        declaredCoverage: coverage,
      });
    }

    await client.query(
      `UPDATE clean.sync_runs
          SET status = 'complete',
              finished_at = NOW(),
              published_at = NOW(),
              resource_manifest = $2::jsonb,
              declared_coverage = $3::jsonb,
              validation_failures = '[]'::jsonb,
              input_snapshot = $4::jsonb
        WHERE id = $1`,
      [run.id, JSON.stringify(resourceManifest), JSON.stringify(coverage), JSON.stringify(snapshot)]
    );

    await client.query(
      `INSERT INTO clean.active_sync (shop_domain, sync_run_id, published_at, started_at)
       VALUES ($1, $2, NOW(), $3)
       ON CONFLICT (shop_domain) DO UPDATE SET
         sync_run_id = EXCLUDED.sync_run_id,
         published_at = EXCLUDED.published_at,
         started_at = EXCLUDED.started_at`,
      [shopDomain, run.id, run.started_at]
    );

    await client.query("COMMIT");
    outcome = {
      published: true,
      syncRunId: run.id,
      status: "complete",
      resourceManifest,
      declaredCoverage: coverage,
      counts: {
        shop: Boolean(input.shop),
        products: (input.products || []).length,
        customers: (input.customers || []).length,
        orders: (input.orders || []).length,
        orderRows: snapshot.rowCount,
      },
    };
  } catch (error) {
    await client.query("ROLLBACK").catch(() => {});
    const isIncomplete = error.code === "insufficient_coverage";
    // Postgres puts its own SQLSTATE on `error.code`, so a bare code would
    // record "23505" as the reason a merchant's sync failed. Keep the message.
    const ours = error.code === "insufficient_coverage" || error.code === "superseded_by_newer_sync";
    await finishSyncRun(run.id, {
      status: isIncomplete ? "incomplete" : "failed",
      failureReason: ours ? error.code : `${error.code ? `${error.code}: ` : ""}${error.message}`,
      validationFailures: error.validationFailures || null,
      resourceManifest,
      declaredCoverage: error.declaredCoverage || null,
    });
    if (isIncomplete) {
      return {
        published: false,
        syncRunId: run.id,
        status: "incomplete",
        validationFailures: error.validationFailures,
        declaredCoverage: error.declaredCoverage,
        resourceManifest,
      };
    }
    error.syncRunId = run.id;
    throw error;
  } finally {
    client.release();
  }

  return outcome;
}

async function getActiveSync(shopDomain) {
  const { rows } = await query(
    `SELECT s.id, s.status, s.provenance, s.started_at, s.finished_at, s.published_at,
            s.schema_version, s.resource_manifest, s.declared_coverage
       FROM clean.active_sync a
       JOIN clean.sync_runs s ON s.id = a.sync_run_id
      WHERE a.shop_domain = $1`,
    [shopDomain]
  );
  return rows[0] || null;
}

// The published input itself. Analysis reads THIS, not a fresh SELECT over the
// clean tables — a later read would silently pick up whatever the next sync
// wrote halfway through.
async function getActiveInputSnapshot(shopDomain) {
  const { rows } = await query(
    `SELECT s.id, s.input_snapshot, s.declared_coverage
       FROM clean.active_sync a
       JOIN clean.sync_runs s ON s.id = a.sync_run_id
      WHERE a.shop_domain = $1`,
    [shopDomain]
  );
  if (!rows.length || !rows[0].input_snapshot) return null;
  return { syncRunId: rows[0].id, snapshot: rows[0].input_snapshot, coverage: rows[0].declared_coverage };
}

async function getLatestSyncRun(shopDomain) {
  const { rows } = await query(
    `SELECT id, status, started_at, finished_at, failure_reason, validation_failures,
            resource_manifest, declared_coverage
       FROM clean.sync_runs
      WHERE shop_domain = $1
      ORDER BY started_at DESC
      LIMIT 1`,
    [shopDomain]
  );
  return rows[0] || null;
}

// Does this shop have clean rows that no sync_run vouches for? True for every
// store synced before this ticket. Reported as unknown provenance — never
// backfilled into a fabricated "complete" sync.
async function hasLegacyData(shopDomain) {
  const { rows } = await query(
    `SELECT EXISTS (SELECT 1 FROM clean.orders WHERE shop_domain = $1) AS present`,
    [shopDomain]
  );
  return Boolean(rows[0]?.present);
}

async function getLatestEngineRunProvenance(shopDomain) {
  const { rows } = await query(
    `SELECT run_id, sync_run_id, input_provenance, created_at
       FROM clean.engine_run_snapshots
      WHERE shop_domain = $1
      ORDER BY created_at DESC
      LIMIT 1`,
    [shopDomain]
  );
  return rows[0] || null;
}

/**
 * Whether a NEW analysis may run, and why not.
 *
 * The asymmetry is intentional and is the pilot rule from the plan: a failed or
 * incomplete sync blocks a new analysis, but never hides the existing one. Old
 * briefings stay readable as history, marked stale — deleting a merchant's last
 * good briefing because today's sync failed would be its own kind of lie.
 */
async function getSyncStatus(shopDomain) {
  const [active, latest, legacy, latestRun] = await Promise.all([
    getActiveSync(shopDomain),
    getLatestSyncRun(shopDomain),
    hasLegacyData(shopDomain),
    getLatestEngineRunProvenance(shopDomain),
  ]);

  const reasons = [];
  if (!active) {
    reasons.push(
      legacy
        ? fail("legacy_unverified_input", "This store's data predates verified sync. Re-sync before running a new analysis.")
        : fail("never_synced", "This store has not completed a sync yet.")
    );
  }
  if (latest && latest.status === "running") {
    reasons.push(fail("sync_running", "A sync is in progress."));
  }
  if (latest && (latest.status === "failed" || latest.status === "incomplete")) {
    reasons.push(
      fail(
        latest.status === "failed" ? "last_sync_failed" : "last_sync_incomplete",
        latest.status === "failed"
          ? "The most recent sync failed. Retry it before running a new analysis."
          : "The most recent sync came back incomplete. Retry it before running a new analysis.",
        { validationFailures: latest.validation_failures || [] }
      )
    );
  }

  const analysisProvenance = !latestRun
    ? null
    : latestRun.input_provenance === "fixture"
      ? "fixture"
      : latestRun.sync_run_id == null
        ? "legacy_unverified"
        : active && latestRun.sync_run_id === active.id
          ? "verified"
          : "verified_stale";

  return {
    ready: reasons.length === 0,
    reasons,
    active: active
      ? {
          syncRunId: active.id,
          publishedAt: active.published_at,
          startedAt: active.started_at,
          coverage: active.declared_coverage,
          resources: active.resource_manifest,
          schemaVersion: active.schema_version,
        }
      : null,
    latest: latest
      ? {
          syncRunId: latest.id,
          status: latest.status,
          startedAt: latest.started_at,
          finishedAt: latest.finished_at,
          failureReason: latest.failure_reason,
          validationFailures: latest.validation_failures || [],
          coverage: latest.declared_coverage,
        }
      : null,
    analysis: latestRun
      ? {
          runId: latestRun.run_id,
          syncRunId: latestRun.sync_run_id,
          provenance: analysisProvenance,
          // Readable as history, visibly not current.
          stale: analysisProvenance !== "verified",
          createdAt: latestRun.created_at,
        }
      : null,
    legacyDataPresent: legacy,
  };
}

// The gate itself. Called by the engine-run endpoint, not only by a disabled
// button — a button is a suggestion, and this is the thing that has to hold.
async function assertReadyForAnalysis(shopDomain) {
  const status = await getSyncStatus(shopDomain);
  if (!status.ready) throw new SyncNotReadyError(status);
  return status;
}

module.exports = {
  ALL_ORDERS_SCOPE,
  PREFERRED_COVERAGE_DAYS,
  REQUIRED_COVERAGE_DAYS,
  SyncNotReadyError,
  assertReadyForAnalysis,
  declaredCoverage,
  getActiveInputSnapshot,
  getActiveSync,
  getSyncStatus,
  runSync,
  validateCoverage,
  validateFetch,
};
