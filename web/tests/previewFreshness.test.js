import test from "node:test";
import assert from "node:assert/strict";
import { PREVIEW_MESSAGE, PREVIEW_STATE, previewFreshness } from "../src/previewFreshness.js";

const base = {
  renderedSignature: "sig-1",
  currentSignature: "sig-1",
  renderedTemplateVersion: 2,
  activeTemplateVersion: 2,
};

test("a preview matching the current draft is fresh", () => {
  assert.equal(previewFreshness(base).state, PREVIEW_STATE.fresh);
});

test("edited copy makes the preview stale", () => {
  const result = previewFreshness({ ...base, currentSignature: "sig-2" });
  assert.equal(result.state, PREVIEW_STATE.stale);
  assert.equal(result.canRetry, true);
  assert.equal(result.message, PREVIEW_MESSAGE.stale);
  assert.equal(result.action, "Refresh preview");
  assert.equal(result.blocksCreation, true);
});

test("a newly approved brand shell says the DESIGN changed", () => {
  // The copy has not moved, but every email now renders differently. Saying
  // "out of date" would send the merchant looking for an edit they never made.
  const result = previewFreshness({ ...base, activeTemplateVersion: 3 });
  assert.equal(result.state, PREVIEW_STATE.stale);
  assert.equal(result.designChanged, true);
  assert.equal(result.message, PREVIEW_MESSAGE.designChanged);
});

test("a failed refresh is reported, not hidden behind the last good render", () => {
  const result = previewFreshness({ ...base, lastRefreshFailed: true });
  assert.equal(result.state, PREVIEW_STATE.failed);
  assert.equal(result.canRetry, true);
  assert.equal(result.message, PREVIEW_MESSAGE.failed);
  assert.equal(result.action, "Retry preview");
});

test("nothing rendered yet is loading, not stale", () => {
  const result = previewFreshness({ ...base, renderedSignature: null });
  assert.equal(result.state, PREVIEW_STATE.loading);
});

test("an unconfigured shell outranks everything else", () => {
  const result = previewFreshness({ ...base, currentSignature: "sig-9", setupRequired: true });
  assert.equal(result.state, PREVIEW_STATE.unavailable);
  assert.equal(result.message, PREVIEW_MESSAGE.unavailable);
  // Retryable: setup happens elsewhere, and the merchant should be able to
  // re-check rather than reload the page to find out it is done.
  assert.equal(result.action, "Check setup again");
  assert.equal(result.blocksCreation, true);
});

test("loading outranks staleness so the state does not flicker mid-refresh", () => {
  const result = previewFreshness({ ...base, currentSignature: "sig-2", loading: true });
  assert.equal(result.state, PREVIEW_STATE.loading);
});

test("unknown template versions do not by themselves mean stale", () => {
  assert.equal(
    previewFreshness({ ...base, renderedTemplateVersion: null, activeTemplateVersion: null }).state,
    PREVIEW_STATE.fresh
  );
});

test("a failure with nothing rendered yet does not claim an earlier version", () => {
  // "The email below is an earlier version" would be a lie when there is no
  // email below.
  const result = previewFreshness({ ...base, renderedSignature: null, lastRefreshFailed: true });
  assert.equal(result.state, PREVIEW_STATE.failed);
  assert.equal(result.message, PREVIEW_MESSAGE.failedNoPrior);
  assert.ok(!result.message.includes("earlier version"));
});

test("only a current preview allows creation", () => {
  assert.equal(previewFreshness(base).blocksCreation, false);
  for (const variant of [
    { lastRefreshFailed: true },
    { currentSignature: "moved" },
    { activeTemplateVersion: 9 },
    { setupRequired: true },
    { loading: true },
  ]) {
    assert.equal(previewFreshness({ ...base, ...variant }).blocksCreation, true, JSON.stringify(variant));
  }
});
