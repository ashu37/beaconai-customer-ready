import test from "node:test";
import assert from "node:assert/strict";
import { analysisOutcome, isNarrationPending, thesisPlaceholder } from "../src/analysisJob.js";

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
