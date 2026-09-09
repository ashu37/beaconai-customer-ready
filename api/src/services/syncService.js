const { pool, query } = require("../db");
const { fetchShopifyData } = require("./shopifyClient");
const {
  saveRawShopifyData,
  upsertAllShopifyData,
  getEngineInput,
} = require("./shopifyRepository");
const {
  buildEngineInputSnapshot,
  fetchedOrderCoverage,
  residualRowsOutsideFetch,
  SNAPSHOT_SCHEMA_VERSION,
} = require("./engineInputSnapshot");

// PILOT POLICY, not an engine requirement. The distinction matters, because
// stating it the other way round would be a false claim about the engine.
//
// What the engine actually does below 90 days: it still runs. Only
// engine/src/profile/builder.py::_annualized_gmv_from_orders declines — it
// returns `insufficient_history`, which forces annualized GMV to 0.0 and the
// store's stage to STARTUP regardless of its real size, and surfaces downstream
// as COLD_START_INSUFFICIENT_DATA (engine/src/decide.py). Above 90 days it
// annualizes from L90 (x4), above 180 from L180 (x2), and above 360 from
// trailing twelve months. Separately, the window policy in engine/src/utils.py
// tops out at L90, so no analysis window needs more than 90 days of data.
//
// So 90 days is the point below which the engine can no longer size the store
// it is advising, and 180 is where it stops multiplying a quarter by four. We
// refuse to publish below 90 as a PILOT choice: a briefing built on a
// mis-sized store is not one to put in front of the first paying merchant. A
// later release may well decide a 60-day store deserves a narrower briefing
// rather than none — that is a product decision, and it is not this one.
const PILOT_MIN_COVERAGE_DAYS = 90;
const PILOT_PREFERRED_COVERAGE_DAYS = 180;

// Retained as the old names for callers/tests that still speak in terms of a
// requirement; they refer to the same pilot policy above.
const REQUIRED_COVERAGE_DAYS = PILOT_MIN_COVERAGE_DAYS;
const PREFERRED_COVERAGE_DAYS = PILOT_PREFERRED_COVERAGE_DAYS;

// Shopify hides orders older than 60 days from apps without `read_all_orders`.
// A store with exactly ~60 days of visible history has almost certainly hit
// that, and the merchant deserves to be told which of the two it is: "your
// store is new" and "we are not allowed to read your history" look identical in
// the data and have opposite remedies.
const SHOPIFY_DEFAULT_ORDER_WINDOW_DAYS = 60;
const ALL_ORDERS_SCOPE = "read_all_orders";

class UnverifiedInputError extends Error {
  constructor(provenance, detail) {
    super(detail.message);
    this.name = "UnverifiedInputError";
    this.statusCode = 409;
    this.provenance = provenance;
    this.detail = detail;
  }
}

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
    failures.push(fail("coverage_unknown", "No order this sync fetched carries a readable date, so the period it covers is unknown."));
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
          ? `This sync reached only ${coverage.daysCovered} days of orders, which is the ceiling Shopify applies without the ${ALL_ORDERS_SCOPE} scope. The pilot requires ${PILOT_MIN_COVERAGE_DAYS} days, below which the engine cannot size the store.`
          : `This sync reached only ${coverage.daysCovered} days of order history; the pilot requires ${PILOT_MIN_COVERAGE_DAYS} days, below which the engine cannot size the store.`,
        {
          daysCovered: coverage.daysCovered,
          requiredDays: PILOT_MIN_COVERAGE_DAYS,
          policy: "pilot_min_coverage_days",
          likelyScopeCeiling: looksLikeScopeCeiling,
          missingScope: looksLikeScopeCeiling ? ALL_ORDERS_SCOPE : null,
        }
      )
    );
  }

  return failures;
}

// Both numbers, kept apart on purpose.
//
//   fetched   — what THIS sync reached. The only thing validation may judge.
//   published — what the engine will read: the accumulated clean tables, which
//               can run earlier than any single fetch because rows from
//               previous syncs stay behind when Shopify stops returning them.
//
// Collapsing these two is the bug that lets a store with 30 days of reachable
// history keep passing a 90-day check forever on the strength of rows nothing
// has re-verified since.
function declaredCoverage(fetched, shopifyScope, published = null, residualRows = null) {
  const scopes = String(shopifyScope || "").split(/[,\s]+/).filter(Boolean);
  return {
    ...fetched,
    fetched,
    published,
    // Rows the engine will read that this sync did not reach. Not an error —
    // but not verified by this sync either, and the merchant is owed the count.
    residualRowsOutsideFetch: residualRows,
    requiredDays: PILOT_MIN_COVERAGE_DAYS,
    preferredDays: PILOT_PREFERRED_COVERAGE_DAYS,
    policy: "pilot_min_coverage_days",
    meetsRequired: fetched?.known === true && fetched.daysCovered >= PILOT_MIN_COVERAGE_DAYS,
    meetsPreferred: fetched?.known === true && fetched.daysCovered >= PILOT_PREFERRED_COVERAGE_DAYS,
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

    // Judge the FETCH, not the accumulated tables. See declaredCoverage.
    const fetched = fetchedOrderCoverage(data.orders);
    const residual = residualRowsOutsideFetch(snapshot.orderRows, fetched);
    const coverage = declaredCoverage(fetched, shopifyScope, snapshot.coverage, residual);
    const coverageFailures = validateCoverage(fetched, shopifyScope);

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

/**
 * Provenance of the input behind ONE engine run, by run id.
 *
 * Separate from getSyncStatus, which answers about the newest run. A merchant
 * can be sending a campaign from a run that is not the newest, and the question
 * at handoff is about the input behind THAT run.
 */
async function getRunProvenance(runId) {
  if (!runId) return null;
  const { rows } = await query(
    `SELECT r.run_id, r.shop_domain, r.sync_run_id, r.input_provenance, r.created_at,
            s.status AS sync_status,
            s.declared_coverage,
            a.sync_run_id AS active_sync_run_id
       FROM clean.engine_run_snapshots r
       LEFT JOIN clean.sync_runs s ON s.id = r.sync_run_id
       LEFT JOIN clean.active_sync a ON a.shop_domain = r.shop_domain
      WHERE r.run_id = $1`,
    [runId]
  );
  if (!rows.length) return null;

  const row = rows[0];
  const provenance =
    row.input_provenance === "fixture"
      ? "fixture"
      : row.sync_run_id == null
        ? "legacy_unverified"
        : row.active_sync_run_id === row.sync_run_id
          ? "verified"
          : "verified_stale";

  return {
    runId: row.run_id,
    shopDomain: row.shop_domain,
    syncRunId: row.sync_run_id,
    provenance,
    coverage: row.declared_coverage,
    createdAt: row.created_at,
  };
}

/**
 * Refuse to hand a campaign to Klaviyo when the recommendation behind it was
 * built on input nothing vouches for.
 *
 * Two cases are blocked outright:
 *   fixture            — demo data. Sending a synthetic briefing's audience to
 *                        real customers is the worst outcome this file exists
 *                        to prevent.
 *   legacy_unverified  — no sync run backs the input. Every run made before
 *                        Ticket A is in this state, INCLUDING any produced by
 *                        the partial-sync incident, which has not yet been
 *                        diagnosed. They stay readable as history and cannot be
 *                        sent. Re-sync and re-run to clear it.
 *
 * `verified_stale` is allowed through: it was verified when it ran, and the
 * merchant may legitimately send a campaign from last month's briefing. It is
 * returned to the caller so the UI can say so.
 */
const BLOCKED_HANDOFF_PROVENANCE = {
  fixture: "This recommendation was generated from sample data, not from this store. It cannot be sent to real customers.",
  legacy_unverified: "This recommendation was built from store data that predates verified sync, so its input cannot be confirmed as complete. Re-sync and refresh the briefing before sending.",
  unknown_run: "The engine run behind this campaign is not on record, so the data it used cannot be confirmed. Refresh the briefing before sending.",
};

async function assertInputVerifiedForHandoff(runId) {
  const run = await getRunProvenance(runId);
  if (!run) {
    throw new UnverifiedInputError("unknown_run", { runId, message: BLOCKED_HANDOFF_PROVENANCE.unknown_run });
  }
  const blocked = BLOCKED_HANDOFF_PROVENANCE[run.provenance];
  if (blocked) throw new UnverifiedInputError(run.provenance, { ...run, message: blocked });
  return run;
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
  PILOT_MIN_COVERAGE_DAYS,
  PILOT_PREFERRED_COVERAGE_DAYS,
  PREFERRED_COVERAGE_DAYS,
  REQUIRED_COVERAGE_DAYS,
  SyncNotReadyError,
  UnverifiedInputError,
  assertInputVerifiedForHandoff,
  assertReadyForAnalysis,
  getRunProvenance,
  declaredCoverage,
  getActiveInputSnapshot,
  getActiveSync,
  getSyncStatus,
  runSync,
  validateCoverage,
  validateFetch,
};
