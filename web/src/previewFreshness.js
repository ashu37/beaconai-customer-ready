// Is the preview on screen still a picture of the email that would be sent?
//
// Carried from Ticket B. The preview used to refetch only when the play or the
// template changed, so any other change — edited copy, a new brand shell version
// approved, a failed refresh leaving the last good render in place — left the
// merchant looking at markup that no longer matched what a send would produce.
// They would then approve THAT.
//
// Kept out of the component and tested directly: "the preview is stale" is a
// claim about correctness, not a rendering detail.

export const PREVIEW_STATE = {
  fresh: "fresh",
  loading: "loading",
  stale: "stale",
  failed: "failed",
  unavailable: "unavailable",
};

export const PREVIEW_MESSAGE = {
  stale: "This preview is out of date — refresh to see what would actually be sent.",
  failed: "The preview couldn't be refreshed. What you see may not match what would be sent.",
  unavailable: "No approved email shell is configured for this store yet.",
};

/**
 * @param {object} args
 * @param {string|null} args.renderedSignature   what the ON-SCREEN preview was rendered from
 * @param {string} args.currentSignature         what the draft says now
 * @param {number|null} args.renderedTemplateVersion  brand shell version used for it
 * @param {number|null} args.activeTemplateVersion    brand shell version now active
 * @param {boolean} args.loading
 * @param {boolean} args.lastRefreshFailed
 * @param {boolean} args.setupRequired
 */
export function previewFreshness({
  renderedSignature = null,
  currentSignature = "",
  renderedTemplateVersion = null,
  activeTemplateVersion = null,
  loading = false,
  lastRefreshFailed = false,
  setupRequired = false,
}) {
  if (setupRequired) {
    return { state: PREVIEW_STATE.unavailable, message: PREVIEW_MESSAGE.unavailable, canRetry: false };
  }
  if (loading) return { state: PREVIEW_STATE.loading, message: null, canRetry: false };

  // A failed refresh leaves the PREVIOUS render on screen. Saying nothing would
  // present stale markup as current, so the failure is surfaced and retryable.
  if (lastRefreshFailed) {
    return { state: PREVIEW_STATE.failed, message: PREVIEW_MESSAGE.failed, canRetry: true };
  }

  // Nothing rendered yet is not the same as stale.
  if (renderedSignature === null) {
    return { state: PREVIEW_STATE.loading, message: null, canRetry: true };
  }

  const contentMoved = renderedSignature !== currentSignature;
  // A new approved shell changes every email's appearance, including one already
  // previewed — so the picture is out of date even though the copy has not moved.
  const shellMoved =
    renderedTemplateVersion !== null &&
    activeTemplateVersion !== null &&
    renderedTemplateVersion !== activeTemplateVersion;

  if (contentMoved || shellMoved) {
    return { state: PREVIEW_STATE.stale, message: PREVIEW_MESSAGE.stale, canRetry: true };
  }

  return { state: PREVIEW_STATE.fresh, message: null, canRetry: true };
}
