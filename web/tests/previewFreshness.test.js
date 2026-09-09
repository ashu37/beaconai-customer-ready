import test from "node:test";
import assert from "node:assert/strict";
import { PREVIEW_STATE, previewFreshness } from "../src/previewFreshness.js";

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
  assert.match(result.message, /out of date/);
});

test("a newly approved brand shell makes an unchanged preview stale", () => {
  // The copy has not moved, but every email now renders differently, so the
  // picture on screen is no longer what a send would produce.
  const result = previewFreshness({ ...base, activeTemplateVersion: 3 });
  assert.equal(result.state, PREVIEW_STATE.stale);
});

test("a failed refresh is reported, not hidden behind the last good render", () => {
  const result = previewFreshness({ ...base, lastRefreshFailed: true });
  assert.equal(result.state, PREVIEW_STATE.failed);
  assert.equal(result.canRetry, true);
  assert.match(result.message, /may not match/);
});

test("nothing rendered yet is loading, not stale", () => {
  const result = previewFreshness({ ...base, renderedSignature: null });
  assert.equal(result.state, PREVIEW_STATE.loading);
});

test("an unconfigured shell outranks everything else", () => {
  const result = previewFreshness({ ...base, currentSignature: "sig-9", setupRequired: true });
  assert.equal(result.state, PREVIEW_STATE.unavailable);
  assert.equal(result.canRetry, false);
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
