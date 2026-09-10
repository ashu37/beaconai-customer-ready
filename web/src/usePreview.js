import { useCallback, useEffect, useRef, useState } from "react";
import { PREVIEW_STATE, previewFreshness } from "./previewFreshness.js";
import { draftSignature } from "./campaignSaveGate.js";

// The preview, and what a merchant is taken to have approved.
//
// Extracted from the component because the failure it guards against is a
// closure bug, not a rendering one: a memoized refresh function captured the
// draft's identity from the render that created it, so after an edit the request
// went out with the NEW copy and was recorded against the OLD signature. The
// email on screen was current and the handoff still called it out of date.
//
// Everything a request binds to is read at CALL time, from a ref that every
// render updates, so a stale closure cannot outlive the value it closed over.

export function usePreview({
  draft,
  campaignSignature,
  campaignKey,
  brandContext,
  activeBrandTemplateVersion,
  fetchPreview,
  onPreviewRendered,
  debounceMs = 600,
}) {
  const [html, setHtml] = useState("");
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [setupRequired, setSetupRequired] = useState(false);
  // A typed, field-specific refusal — a missing or unusable destination — so the
  // UI can name the field and focus it rather than saying "preview failed".
  const [problem, setProblem] = useState(null);
  const [renderedFrom, setRenderedFrom] = useState({
    signature: null, templateVersion: null, fingerprint: null, campaignKey: null,
    effectiveDestinationUrl: null,
  });

  // Refreshed every render. `refresh` keeps a stable identity — the effects
  // below depend on it — while always seeing current values.
  const latest = useRef({});
  latest.current = { draft, campaignSignature, campaignKey, brandContext, fetchPreview, onPreviewRendered };

  const refresh = useCallback(async (overrideDraft) => {
    const bound = latest.current;
    const currentDraft = overrideDraft || bound.draft;
    if (!currentDraft) return null;

    // Captured up front so the response is recorded against the request that
    // produced it, not against whatever the component has moved on to.
    const request = {
      signature: draftSignature(currentDraft),
      campaignSignature: bound.campaignSignature,
      campaignKey: bound.campaignKey,
    };

    setLoading(true);
    try {
      const result = await bound.fetchPreview({ ...currentDraft, brandContext: bound.brandContext });

      // The merchant switched campaigns while this was in flight. Applying it
      // would show one campaign's email under another's name.
      if (latest.current.campaignKey !== request.campaignKey) return null;

      const record = {
        signature: request.signature,
        campaignSignature: request.campaignSignature,
        campaignKey: request.campaignKey,
        templateVersion: result.templateVersion ?? null,
        fingerprint: result.renderFingerprint ?? null,
        // The link the rendered button actually carries, after the campaign's
        // own destination and the design default are resolved.
        effectiveDestinationUrl: result.effectiveDestinationUrl ?? null,
      };
      setHtml(result.html || "");
      setRenderedFrom(record);
      setFailed(false);
      setSetupRequired(false);
      setProblem(null);
      if (bound.onPreviewRendered) bound.onPreviewRendered(record);
      return record;
    } catch (error) {
      if (latest.current.campaignKey !== request.campaignKey) return null;
      // The last good render stays on screen but stops being presented as
      // current. Showing nothing would be worse; showing it silently, worse still.
      setFailed(true);
      setProblem(
        error?.code === "missing_destination" || error?.code === "slot_value_rejected"
          ? { code: error.code, slot: error.slot || "cta_url", message: error.message }
          : null
      );
      if (error?.code === "brand_setup_required") {
        setSetupRequired(true);
        setHtml("");
      }
      return null;
    } finally {
      if (latest.current.campaignKey === request.campaignKey) setLoading(false);
    }
  }, []);

  // Immediate on campaign or template change.
  useEffect(() => {
    if (latest.current.draft) refresh();
  }, [campaignKey, refresh]);

  // Debounced while the merchant types. Keyed on the campaign signature, which
  // covers the destination as well as the copy — the previous field list did
  // not, so typing a destination never refreshed the preview.
  const debounce = useRef(null);
  useEffect(() => {
    if (!draft) return undefined;
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => refresh(), debounceMs);
    return () => clearTimeout(debounce.current);
  }, [campaignSignature, draft?.subject, draft?.previewText, draft?.bodyH2, draft?.bodyP1, draft?.bodyP2, draft?.cta, debounceMs, refresh, draft]);

  const flush = useCallback(() => {
    clearTimeout(debounce.current);
    return refresh();
  }, [refresh]);

  const freshness = previewFreshness({
    renderedSignature: renderedFrom.campaignKey === campaignKey ? renderedFrom.signature : null,
    currentSignature: draft ? draftSignature(draft) : "",
    renderedTemplateVersion: renderedFrom.templateVersion,
    activeTemplateVersion: activeBrandTemplateVersion ?? null,
    loading,
    lastRefreshFailed: failed,
    setupRequired,
  });

  return { html, freshness, renderedFrom, problem, refresh, flush, PREVIEW_STATE };
}
