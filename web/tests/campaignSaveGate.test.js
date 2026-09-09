import test from "node:test";
import assert from "node:assert/strict";
import { canHandoff, draftSignature } from "../src/campaignSaveGate.js";

const gate = { canHandoff, draftSignature };
const sig = (edits) => draftSignature(edits);

test("a settled failure still blocks handoff", () => {
  // The reported bug: the failed request settles, leaves the in-flight map, and
  // a later flush finds nothing pending. The status is sticky, so it still
  // blocks — even though there is no longer any pending work to await.
  const edits = { subject: "Edited" };
  const result = gate.canHandoff({
    status: "failed",
    currentSignature: sig(edits),
    savedSignature: sig(edits),
    savedRevision: 3,
  });
  assert.equal(result.ok, false);
  assert.equal(result.reason, "save_failed");
});

test("a conflict blocks even when the revision moved on", () => {
  // A conflict updates the server's revision but leaves the merchant's copy
  // unresolved. Sending would freeze one of the two arbitrarily.
  const result = gate.canHandoff({
    status: "conflict",
    currentSignature: sig({ subject: "Mine" }),
    savedSignature: sig({ subject: "Mine" }),
    savedRevision: 7,
  });
  assert.equal(result.ok, false);
  assert.equal(result.reason, "save_conflicted");
});

test("a draft that does not match what was saved blocks", () => {
  const result = gate.canHandoff({
    status: "saved",
    currentSignature: sig({ subject: "Newer text" }),
    savedSignature: sig({ subject: "Older text" }),
    savedRevision: 2,
  });
  assert.equal(result.ok, false);
  assert.equal(result.reason, "unsaved_changes");
});

test("a saved draft matching the persisted state may be handed off", () => {
  const edits = { subject: "Final", preview: "Hello" };
  const result = gate.canHandoff({
    status: "saved",
    currentSignature: sig(edits),
    savedSignature: sig(edits),
    savedRevision: 5,
  });
  assert.deepEqual(result, { ok: true, revision: 5 });
});

test("an existing campaign with no known saved revision blocks", () => {
  const result = gate.canHandoff({
    status: "saved",
    currentSignature: sig({}),
    savedSignature: sig({}),
    savedRevision: undefined,
    hasCampaignRow: true,
  });
  assert.equal(result.ok, false);
  assert.equal(result.reason, "never_saved");
});

test("a campaign with no row yet needs no revision", () => {
  const result = gate.canHandoff({
    status: undefined,
    currentSignature: sig({}),
    savedSignature: sig({}),
    savedRevision: undefined,
    hasCampaignRow: false,
  });
  assert.equal(result.ok, true);
});

test("signatures ignore key order and undefined values", () => {
  assert.equal(sig({ a: "1", b: "2" }), sig({ b: "2", a: "1" }));
  assert.equal(sig({ a: "1", b: undefined }), sig({ a: "1" }));
  assert.notEqual(sig({ a: "1" }), sig({ a: "2" }));
  assert.equal(sig(undefined), sig({}));
});
