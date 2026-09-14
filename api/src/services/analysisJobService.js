// An analysis runs in the background, one per store.
//
// The run route used to hold its HTTP request open for the whole engine run and
// the narration pass after it — about 3.5 minutes measured on Render free, and
// unbounded when either stalled. Nothing stopped a second run from starting
// alongside, and overlapping runs on one small instance slowed each other and
// lost a narration (2026-09-11). Now the route records a job and returns; the
// page polls the job, then reads the finished run like any other.
//
// "One per store" is a database guarantee (a partial unique index on running
// rows), so it holds across tabs, double clicks and instances. A job whose
// process died is not allowed to hold the slot forever: a running row older
// than both deadlines combined is marked abandoned before a new one starts.
const { config } = require("../config");
const { query } = require("../db");

class AnalysisInProgress extends Error {
  constructor(job) {
    super("An analysis for this store is already running.");
    this.name = "AnalysisInProgress";
    this.statusCode = 409;
    this.job = job;
  }
}

function abandonAfterMs() {
  return config.engineTimeoutMs + config.narrationTimeoutMs + 2 * 60 * 1000;
}

function rowToJob(row) {
  if (!row) return null;
  return {
    id: row.id,
    shopDomain: row.shop_domain,
    status: row.status,
    runId: row.run_id || null,
    error: row.error || null,
    startedAt: row.started_at,
    finishedAt: row.finished_at || null,
  };
}

async function abandonStaleJobs(shopDomain) {
  await query(
    `UPDATE clean.analysis_jobs
        SET status = 'failed', finished_at = NOW(),
            error = 'The analysis stopped responding and was abandoned. Run it again.'
      WHERE shop_domain = $1 AND status = 'running'
        AND started_at < NOW() - ($2::bigint * INTERVAL '1 millisecond')`,
    [shopDomain, abandonAfterMs()]
  );
}

async function getLatestAnalysisJob(shopDomain) {
  const { rows } = await query(
    `SELECT * FROM clean.analysis_jobs WHERE shop_domain = $1 ORDER BY started_at DESC, id DESC LIMIT 1`,
    [shopDomain]
  );
  return rowToJob(rows[0]);
}

async function finishJob(id, { status, runId = null, error = null }) {
  const { rows } = await query(
    `UPDATE clean.analysis_jobs
        SET status = $2, run_id = COALESCE($3, run_id), error = $4, finished_at = NOW()
      WHERE id = $1 AND status = 'running'
      RETURNING *`,
    [id, status, runId, error]
  );
  return rowToJob(rows[0]);
}

// What a merchant may be told when a run fails. Engine stderr and stack traces
// stay in the server log; the page gets a sentence it can act on.
function publicError(error) {
  if (error?.code === "ETIMEDOUT") return error.message;
  return "The analysis didn't finish. Run it again; if it keeps failing, contact support.";
}

/**
 * Record a running job and start `execute` without waiting for it.
 *
 * @param {object} args
 * @param {string} args.shopDomain
 * @param {boolean} [args.useFixture]
 * @param {(job) => Promise<string|null>} args.execute  does the work; resolves
 *   with the run id it produced. Its rejection marks the job failed.
 * @param {(promise: Promise) => void} [args.onSettled]  test hook: receives the
 *   background promise so a test can await it.
 * @returns {Promise<object>} the running job
 * @throws {AnalysisInProgress} when this store already has one running
 */
async function startAnalysisJob({ shopDomain, useFixture = false, execute, onSettled }) {
  await abandonStaleJobs(shopDomain);

  let job;
  try {
    const { rows } = await query(
      `INSERT INTO clean.analysis_jobs (shop_domain, status, use_fixture) VALUES ($1, 'running', $2) RETURNING *`,
      [shopDomain, Boolean(useFixture)]
    );
    job = rowToJob(rows[0]);
  } catch (error) {
    // 23505: the partial unique index — a run for this store is in flight.
    if (error.code === "23505") throw new AnalysisInProgress(await getLatestAnalysisJob(shopDomain));
    throw error;
  }

  const background = Promise.resolve()
    .then(() => execute(job))
    .then((runId) => finishJob(job.id, { status: "complete", runId: runId || null }))
    .catch(async (error) => {
      console.error(`[analysis] job ${job.id} for ${shopDomain} failed:`, error?.message || error);
      await finishJob(job.id, { status: "failed", error: publicError(error) }).catch(() => {});
    });
  if (onSettled) onSettled(background);

  return job;
}

module.exports = {
  AnalysisInProgress,
  getLatestAnalysisJob,
  startAnalysisJob,
};
