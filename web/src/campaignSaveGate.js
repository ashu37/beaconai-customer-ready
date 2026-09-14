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
  design_moved_on: "Your email design changed since this preview. Check the updated preview before sending.",
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
 * @param {string|null} args.campaignKey  the campaign being handed off, and
 * @param {string|null} args.approvedRenderCampaignKey  the campaign that
 *   rendering was made for. A preview of another campaign — even one with
 *   identical copy — is not a review of this one.
 * @param {number|null} args.approvedRenderTemplateVersion  the design version
 *   the preview used, and
 * @param {number|null} args.activeTemplateVersion  the design active now.
 *   Approval binds to revision, rendering AND design; the campaign id alone
 *   is not enough.
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
  campaignKey = null,
  approvedRenderCampaignKey = null,
  approvedRenderTemplateVersion = null,
  activeTemplateVersion = null,
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
    if (campaignKey != null && approvedRenderCampaignKey != null && approvedRenderCampaignKey !== campaignKey) {
      return { ok: false, reason: "no_approved_preview", message: HANDOFF_BLOCKED.no_approved_preview };
    }
    if (approvedRenderSignature !== currentSignature) {
      return { ok: false, reason: "preview_moved_on", message: HANDOFF_BLOCKED.preview_moved_on };
    }
    if (activeTemplateVersion != null && approvedRenderTemplateVersion != null
      && Number(approvedRenderTemplateVersion) !== Number(activeTemplateVersion)) {
      return { ok: false, reason: "design_moved_on", message: HANDOFF_BLOCKED.design_moved_on };
    }
  }

  return { ok: true, revision: savedRevision };
}

// Whether the final review has to render the email itself before a draft can be
// created. The preview normally comes from the Edit step, but an approved
// campaign reopened after a reload lands straight on the final step, where
// nothing had rendered it — so the handoff gate refused with "no approved
// preview" and the merchant had to go back a step (found on the deployed app,
// 2026-09-14). The final step renders when there is no render for the email as
// it stands now, or when the design has moved on since.
export function reviewNeedsRender({ rendered, currentSignature, activeTemplateVersion = null } = {}) {
  if (!rendered || rendered.campaignSignature == null) return true;
  if (rendered.campaignSignature !== currentSignature) return true;
  if (activeTemplateVersion != null && rendered.templateVersion != null
    && Number(rendered.templateVersion) !== Number(activeTemplateVersion)) return true;
  return false;
}
