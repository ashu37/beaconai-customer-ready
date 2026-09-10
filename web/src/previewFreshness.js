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

// Wording is the approved specification's, verbatim. These are the sentences a
// merchant reads before deciding an email is ready to send, so they are part of
// the contract rather than incidental copy.
export const PREVIEW_MESSAGE = {
  stale: "This preview is out of date.",
  designChanged: "Your email design changed. Refresh the preview and review it again.",
  failed: "We couldn't update the preview. The email below is an earlier version.",
  failedNoPrior: "We couldn't update the preview.",
  unavailable: "Your store's email design isn't set up yet. Your pilot contact needs to finish setup.",
  current: "Preview up to date",
  loading: "Updating preview…",
};

export const PREVIEW_ACTION = {
  stale: "Refresh preview",
  designChanged: "Refresh preview",
  failed: "Retry preview",
  unavailable: "Check setup again",
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
    return {
      state: PREVIEW_STATE.unavailable,
      message: PREVIEW_MESSAGE.unavailable,
      action: PREVIEW_ACTION.unavailable,
      canRetry: true,
      blocksCreation: true,
    };
  }
  if (loading) {
    return { state: PREVIEW_STATE.loading, message: PREVIEW_MESSAGE.loading, action: null, canRetry: false, blocksCreation: true };
  }

  // A failed refresh leaves the PREVIOUS render on screen. Saying nothing would
  // present stale markup as current, so the failure is surfaced and retryable.
  if (lastRefreshFailed) {
    // With no prior render there is no "earlier version" to point at, and
    // claiming one would be a lie about what is on screen.
    return {
      state: PREVIEW_STATE.failed,
      message: renderedSignature === null ? PREVIEW_MESSAGE.failedNoPrior : PREVIEW_MESSAGE.failed,
      action: PREVIEW_ACTION.failed,
      canRetry: true,
      blocksCreation: true,
    };
  }

  // Nothing rendered yet is not the same as stale.
  if (renderedSignature === null) {
    return { state: PREVIEW_STATE.loading, message: PREVIEW_MESSAGE.loading, action: null, canRetry: true, blocksCreation: true };
  }

  const contentMoved = renderedSignature !== currentSignature;
  // A new approved shell changes every email's appearance, including one already
  // previewed — so the picture is out of date even though the copy has not moved.
  const shellMoved =
    renderedTemplateVersion !== null &&
    activeTemplateVersion !== null &&
    renderedTemplateVersion !== activeTemplateVersion;

  // A changed DESIGN gets its own sentence. "Out of date" would leave the
  // merchant looking for an edit they did not make.
  if (shellMoved) {
    return {
      state: PREVIEW_STATE.stale, designChanged: true,
      message: PREVIEW_MESSAGE.designChanged, action: PREVIEW_ACTION.designChanged,
      canRetry: true, blocksCreation: true,
    };
  }
  if (contentMoved) {
    return {
      state: PREVIEW_STATE.stale, designChanged: false,
      message: PREVIEW_MESSAGE.stale, action: PREVIEW_ACTION.stale,
      canRetry: true, blocksCreation: true,
    };
  }

  return {
    state: PREVIEW_STATE.fresh, message: PREVIEW_MESSAGE.current,
    action: null, canRetry: true, blocksCreation: false,
  };
}
