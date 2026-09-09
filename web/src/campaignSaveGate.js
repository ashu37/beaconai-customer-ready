// Whether a campaign draft is in a state that may be handed off.
//
// Pulled out of the component deliberately: this is the rule that decides
// whether an email is allowed to leave, and it needs to be testable without a
// browser. The component owns the state; this owns the decision.
//
// The failure it exists to prevent: a save fails, its request settles, and it
// then disappears from the in-flight map. A later flush finds nothing pending,
// reports success, and the handoff proceeds — freezing a record that never
// matched what the merchant had on screen.

export const HANDOFF_BLOCKED = {
  save_failed: "This campaign's last edit didn't save. Retry before sending.",
  save_conflicted: "This campaign changed elsewhere. Reload it before sending.",
  unsaved_changes: "This campaign has unsaved changes. Wait for them to save before sending.",
  never_saved: "This campaign hasn't finished saving. Try again in a moment.",
};

// A stable string for a draft-edits object, so "what is on screen" can be
// compared with "what was persisted". Keys are sorted because object order is
// not meaningful and would otherwise produce false mismatches.
export function draftSignature(edits) {
  const source = edits || {};
  const keys = Object.keys(source).filter((key) => source[key] !== undefined).sort();
  return JSON.stringify(keys.map((key) => [key, source[key]]));
}

/**
 * @param {object} args
 * @param {"saved"|"failed"|"conflict"|"saving"|undefined} args.status
 *   The LAST settled outcome for this draft. Sticky: a failure stays failed
 *   until a later save succeeds. This is why a settled failure no longer looks
 *   like "nothing pending".
 * @param {string} args.currentSignature    what is on screen now
 * @param {string|undefined} args.savedSignature  what was last persisted
 * @param {number|undefined} args.savedRevision   revision of that persisted state
 * @param {boolean} args.hasCampaignRow  false before the first save has ever landed
 * @returns {{ok: true, revision: number|undefined} | {ok: false, reason: string, message: string}}
 */
export function canHandoff({
  status,
  currentSignature,
  savedSignature,
  savedRevision,
  hasCampaignRow = true,
}) {
  if (status === "failed") {
    return { ok: false, reason: "save_failed", message: HANDOFF_BLOCKED.save_failed };
  }
  // A conflict means the server holds a version the merchant has not seen. The
  // revision moved, but their unsaved copy was never resolved against it, so
  // sending would freeze one or the other arbitrarily.
  if (status === "conflict") {
    return { ok: false, reason: "save_conflicted", message: HANDOFF_BLOCKED.save_conflicted };
  }

  // The draft must match something that was actually persisted. This is the
  // check that survives a settled failure disappearing from every pending map.
  if (currentSignature !== savedSignature) {
    return { ok: false, reason: "unsaved_changes", message: HANDOFF_BLOCKED.unsaved_changes };
  }

  if (hasCampaignRow && (savedRevision === undefined || savedRevision === null)) {
    return { ok: false, reason: "never_saved", message: HANDOFF_BLOCKED.never_saved };
  }

  return { ok: true, revision: savedRevision };
}
