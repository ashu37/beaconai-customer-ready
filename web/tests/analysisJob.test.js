import test from "node:test";
import assert from "node:assert/strict";
import { analysisOutcome, isNarrationPending, thesisPlaceholder, waitForAnalysis, withRetries } from "../src/analysisJob.js";

test("a running or not-yet-visible job keeps the page waiting", () => {
  assert.deepEqual(analysisOutcome(null, 7), { state: "running" });
  assert.deepEqual(analysisOutcome({ id: 7, status: "running" }, 7), { state: "running" });
  // An older job surfacing before ours is visible is not our result.
  assert.deepEqual(analysisOutcome({ id: 6, status: "complete", runId: "old" }, 7), { state: "running" });
});

test("a settled job tells the page what happened", () => {
  assert.deepEqual(analysisOutcome({ id: 7, status: "complete", runId: "r-1" }, 7), { state: "complete", runId: "r-1" });
  assert.deepEqual(
    analysisOutcome({ id: 7, status: "failed", error: "The analysis did not finish within 600s and was stopped." }, 7),
    { state: "failed", message: "The analysis did not finish within 600s and was stopped." }
  );
  assert.equal(analysisOutcome({ id: 7, status: "failed" }, 7).message.includes("Run it again"), true, "a failure always says what to do");
});

test("joining a run already under way waits on whatever is latest", () => {
  assert.deepEqual(analysisOutcome({ id: 9, status: "running" }, null), { state: "running" });
  assert.deepEqual(analysisOutcome({ id: 9, status: "complete", runId: "r-9" }, null), { state: "complete", runId: "r-9" });
});

test("the thesis says it is being written only while narration is pending", () => {
  assert.equal(isNarrationPending({ narration_status: "pending" }), true);
  assert.equal(isNarrationPending({ narration_status: "complete" }), false);
  assert.equal(isNarrationPending({}), false, "runs from before narration status");
  assert.match(thesisPlaceholder("pending"), /Writing the explanation/);
  assert.equal(thesisPlaceholder("failed"), null, "a failed narration falls back to the evidence, not a promise");
  assert.equal(thesisPlaceholder(null), null);
});

test("a failed poll does not end the wait; the job's own outcome does", async () => {
  const responses = [
    new Error("Unexpected token '<', \"<!DOCTYPE \"... is not valid JSON"),
    { job: { id: 3, status: "running" } },
    new Error("Failed to fetch"),
    { job: { id: 3, status: "complete", runId: "r-3" } },
  ];
  let calls = 0;
  const outcome = await waitForAnalysis({
    getJob: async () => {
      const next = responses[calls++];
      if (next instanceof Error) throw next;
      return next;
    },
    startedJobId: 3,
    sleep: async () => {},
  });
  assert.deepEqual(outcome, { state: "complete", runId: "r-3" });
  assert.equal(calls, 4, "rode out both failed polls");
});

test("a job the server reports as failed ends the wait with its message", async () => {
  await assert.rejects(
    () => waitForAnalysis({
      getJob: async () => ({ job: { id: 3, status: "failed", error: "The analysis did not finish within 600s and was stopped." } }),
      startedJobId: 3,
      sleep: async () => {},
    }),
    /did not finish within 600s/
  );
});

test("waiting gives up at the deadline even if every poll fails", async () => {
  let clock = 0;
  await assert.rejects(
    () => waitForAnalysis({
      getJob: async () => { throw new Error("offline"); },
      startedJobId: 3,
      giveUpMs: 10000,
      pollMs: 4000,
      now: () => clock,
      sleep: async (ms) => { clock += ms; },
    }),
    /taking longer than usual/
  );
});

test("a read retries through transient failures, then reports the last one", async () => {
  let n = 0;
  const value = await withRetries(async () => { n += 1; if (n < 3) throw new Error("502"); return "ok"; }, { sleep: async () => {} });
  assert.equal(value, "ok");
  await assert.rejects(() => withRetries(async () => { throw new Error("still down"); }, { attempts: 2, sleep: async () => {} }), /still down/);
});
