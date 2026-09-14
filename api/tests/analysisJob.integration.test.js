const test = require("node:test");
const assert = require("node:assert/strict");

const db = require("./helpers/db");
const suite = db.available ? test : test.skip;

const { query } = require("../src/db");
const { startApi } = require("./helpers/httpApp");
const { runSync } = require("../src/services/syncService");
const { AnalysisInProgress, getLatestAnalysisJob, startAnalysisJob } = require("../src/services/analysisJobService");
const { narrationStatusOf, runProcess } = require("../src/services/atulEngineService");
const { config } = require("../src/config");

const SHOP = "analysis-shop.myshopify.com";
const OTHER = "other-analysis-shop.myshopify.com";

let api;
test.before(async () => { if (db.available) api = await startApi(); });
test.after(async () => {
  if (api) await api.close();
  if (db.available) await db.closeDatabase();
});

// A job body the test finishes when it chooses, standing in for the engine.
function controllable() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { execute: () => promise, resolve, reject };
}

function capture() {
  const box = {};
  return { box, onSettled: (p) => { box.settled = p; } };
}

suite("only one analysis runs per store, and a finished one frees the slot", async () => {
  await db.resetDatabase();
  const first = controllable();
  const hook = capture();
  const job = await startAnalysisJob({ shopDomain: SHOP, execute: first.execute, onSettled: hook.onSettled });
  assert.equal(job.status, "running");

  // A double click, a second tab: refused, and told which job is running.
  await assert.rejects(
    () => startAnalysisJob({ shopDomain: SHOP, execute: async () => "never" }),
    (error) => {
      assert.ok(error instanceof AnalysisInProgress);
      assert.equal(error.job.id, job.id);
      return true;
    }
  );

  // Another store is not held up by this one.
  const otherHook = capture();
  const other = await startAnalysisJob({ shopDomain: OTHER, execute: async () => "run-other", onSettled: otherHook.onSettled });
  assert.equal(other.status, "running");
  await otherHook.box.settled;

  first.resolve("run-9");
  await hook.box.settled;
  const done = await getLatestAnalysisJob(SHOP);
  assert.equal(done.status, "complete");
  assert.equal(done.runId, "run-9");
  assert.ok(done.finishedAt);

  const nextHook = capture();
  const next = await startAnalysisJob({ shopDomain: SHOP, execute: async () => "run-10", onSettled: nextHook.onSettled });
  assert.equal(next.status, "running", "the slot is free again");
  // Settled before the next suite resets the table, so a late write cannot land
  // on a reused job id.
  await nextHook.box.settled;
});

suite("a failed analysis says what to do, and keeps engine output out of it", async () => {
  await db.resetDatabase();
  const hook = capture();
  await startAnalysisJob({
    shopDomain: SHOP,
    execute: async () => {
      const error = new Error("Atul engine exited with code 1");
      error.stderr = "Traceback (most recent call last): secret/path/engine.py";
      throw error;
    },
    onSettled: hook.onSettled,
  });
  await hook.box.settled;
  const failed = await getLatestAnalysisJob(SHOP);
  assert.equal(failed.status, "failed");
  assert.match(failed.error, /Run it again/);
  assert.doesNotMatch(failed.error, /Traceback|engine\.py/);

  // A deadline is already a merchant-readable sentence, so it passes through.
  const timed = capture();
  await startAnalysisJob({
    shopDomain: SHOP,
    execute: async () => {
      const error = new Error("The analysis did not finish within 600s and was stopped.");
      error.code = "ETIMEDOUT";
      throw error;
    },
    onSettled: timed.onSettled,
  });
  await timed.box.settled;
  assert.equal((await getLatestAnalysisJob(SHOP)).error, "The analysis did not finish within 600s and was stopped.");
});

suite("a job left running by a dead process does not hold the slot forever", async () => {
  await db.resetDatabase();
  const staleMs = config.engineTimeoutMs + config.narrationTimeoutMs + 3 * 60 * 1000;
  await query(
    `INSERT INTO clean.analysis_jobs (shop_domain, status, started_at)
     VALUES ($1, 'running', NOW() - ($2::bigint * INTERVAL '1 millisecond'))`,
    [SHOP, staleMs]
  );

  const job = await startAnalysisJob({ shopDomain: SHOP, execute: () => new Promise(() => {}) });
  assert.equal(job.status, "running");
  const { rows } = await query(
    `SELECT status, error FROM clean.analysis_jobs WHERE shop_domain = $1 AND id <> $2`,
    [SHOP, job.id]
  );
  assert.equal(rows[0].status, "failed");
  assert.match(rows[0].error, /abandoned/);
});

suite("the run route refuses a second analysis, and the job can be polled", async () => {
  await db.resetDatabase();
  await runSync({
    shopDomain: SHOP, accessToken: "t", shopifyScope: "read_orders,read_all_orders",
    fetchData: async () => db.shopifyPayload({ orders: db.ordersSpanning(200) }),
  });
  const { rows } = await query(
    `INSERT INTO clean.analysis_jobs (shop_domain, status) VALUES ($1, 'running') RETURNING id`,
    [SHOP]
  );

  const response = await api.post("/engine/atul/run", { shopDomain: SHOP });
  assert.equal(response.status, 409);
  assert.equal(response.body.code, "analysis_in_progress");
  assert.equal(response.body.job.id, rows[0].id);

  const polled = await api.get(`/engine/atul/jobs/latest/${SHOP}`);
  assert.equal(polled.status, 200);
  assert.equal(polled.body.job.status, "running");

  const theirs = await api.get(`/engine/atul/jobs/latest/${SHOP}`, { session: OTHER });
  assert.equal(theirs.status, 403, "another store's session cannot read this store's job");
});

test("a subprocess that overruns its deadline is stopped", async () => {
  const started = Date.now();
  await assert.rejects(
    () => runProcess(process.execPath, ["-e", "setTimeout(() => {}, 10000)"], { timeoutMs: 300, label: "The analysis" }),
    (error) => {
      assert.equal(error.code, "ETIMEDOUT");
      assert.match(error.message, /The analysis did not finish within/);
      return true;
    }
  );
  assert.ok(Date.now() - started < 5000, "killed at the deadline, not left to finish");

  const ok = await runProcess(process.execPath, ["-e", "process.stdout.write('done')"], { timeoutMs: 5000 });
  assert.equal(ok.stdout, "done");
});

test("a run's narration status is honest about what the briefing can show", () => {
  const now = Date.parse("2026-09-14T12:00:00Z");
  const minutesAgo = (m) => new Date(now - m * 60 * 1000).toISOString();

  assert.equal(narrationStatusOf({ narration: { cards: [] }, narration_status: "pending", created_at: minutesAgo(1) }, now), "complete");
  assert.equal(narrationStatusOf({ narration: null, narration_status: "pending", created_at: minutesAgo(1) }, now), "pending");
  // Pending past the narration deadline will never be written: a dead process.
  const stale = (config.narrationTimeoutMs + 2 * 60 * 1000) / 60000;
  assert.equal(narrationStatusOf({ narration: null, narration_status: "pending", created_at: minutesAgo(stale) }, now), "failed");
  assert.equal(narrationStatusOf({ narration: null, narration_status: "failed", created_at: minutesAgo(1) }, now), "failed");
  assert.equal(narrationStatusOf({ narration: null, narration_status: null, created_at: minutesAgo(1) }, now), null, "runs from before narration status");
});
