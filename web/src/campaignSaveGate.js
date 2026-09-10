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
  no_approved_preview: "Wait for the preview to load, so you can see what would be sent before sending it.",
  preview_moved_on: "This preview is out of date — refresh it and check the email before sending.",
};

// A stable string for a draft, so "what is on screen" can be compared with
// "what was persisted". Keys are sorted because object order is not meaningful
// and would otherwise produce false mismatches.
export function draftSignature(edits) {
  const source = edits || {};
  const keys = Object.keys(source).filter((key) => source[key] !== undefined).sort();
  return JSON.stringify(keys.map((key) => [key, source[key]]));
}

// The signature of everything a save persists for a campaign. The destination is
// a separate column but the same question: has the merchant changed something
// that has not been written down yet? Leaving it out let an unsaved destination
// look like a saved campaign.
export function campaignSignature({ edits, destinationUrl } = {}) {
  return draftSignature({ ...(edits || {}), __destination: destinationUrl ?? null });
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
 * @param {string|null} args.approvedRenderSignature  the draft the ON-SCREEN
 *   preview was rendered from, or null if no preview has succeeded. Handoff
 *   binds to a specific rendering, so there has to BE one.
 * @returns {{ok: true, revision: number|undefined} | {ok: false, reason: string, message: string}}
 */
export function canHandoff({
  status,
  currentSignature,
  savedSignature,
  savedRevision,
  hasCampaignRow = true,
  approvedRenderSignature = null,
  requireApprovedPreview = true,
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

  // The server requires the previewed template version and render fingerprint,
  // so a handoff without a successful preview cannot be honoured — and should
  // not be attempted. More to the point: sending an email nobody has seen is
  // what the approval binding exists to prevent.
  if (requireApprovedPreview) {
    if (approvedRenderSignature === null || approvedRenderSignature === undefined) {
      return { ok: false, reason: "no_approved_preview", message: HANDOFF_BLOCKED.no_approved_preview };
    }
    if (approvedRenderSignature !== currentSignature) {
      return { ok: false, reason: "preview_moved_on", message: HANDOFF_BLOCKED.preview_moved_on };
    }
  }

  return { ok: true, revision: savedRevision };
}
