"""V2 Decision Selector (Milestone 7).

This module composes the V2 pieces built in M1 (EngineRun schema) through M6
(conservative sizing) into the final decision layer:

    decide(engine_run, *, cfg, ...) -> EngineRun

The function takes an already-populated EngineRun (typically the output of
:func:`src.engine_run_adapter.build_engine_run_from_legacy` after
:func:`src.guardrails.apply_guardrails` and the M6 V2 sizing block) and
applies the M7 contract:

- **Class-aware ranking** within recommendations: ``measured > directional >
  targeting``. Within a class, sort by ``revenue_range.p50`` desc (with
  ``None``/suppressed treated as the lowest). This is the load-bearing rule
  per DS Architect QA Change 2: "targeting must not outrank
  measured/directional solely because of audience size or legacy
  expected_$."
- **Recommendation cap**: at most 3 PlayCards in
  ``EngineRun.recommendations``. Excess is moved to ``considered`` with
  ``reason_code = CAP_EXCEEDED``.
- **Abstain state machine**:
    * ``ABSTAIN_HARD`` ⇔ any HARD ``data_quality_flags`` is set (already
      handled by M5 ``apply_guardrails`` when ``ANOMALY_GATE_ENABLED``;
      M7 enforces the invariant defensively even if the flag is off).
      ``recommendations = []``.
    * ``ABSTAIN_SOFT`` ⇔ no ``measured`` or ``directional`` recommendation
      survives materiality + cannibalization gating, regardless of how
      many ``targeting`` plays remain. This is DS Architect QA Change 2:
      "Never publish a TARGETING-only briefing as PUBLISH." Synthetic
      Blocker Fix 3 (PM-resolved): when ABSTAIN_SOFT fires,
      ``recommendations = []``. Held targeting cards from the ranked
      head are re-routed into ``considered`` with
      ``ReasonCode.TARGETING_HELD_UNDER_ABSTAIN`` so the merchant
      sees them in the Considered section, not the Recommended one.
    * ``PUBLISH`` otherwise.
- **Considered list assembly**: union of guardrail rejections (already on
  the input EngineRun's ``considered`` field) plus M7-introduced
  rejections (cap exceeded, no measured signal under abstain_soft) and a
  ``would_fire_if`` text builder for each rejection that does not already
  have one. Cap rendered considered list at 6 (PM Q10 #6); the closest-
  to-firing 6 by simple priority order. Internal deduplication: if a
  play already appears in ``recommendations`` it is excluded from
  ``considered``; if a play appears multiple times in ``considered`` the
  earliest entry wins.
- **Watching builder**: a deterministic single-run ``WatchedSignal`` list
  built from ``state_of_store`` observations whose change is below the
  "moved" threshold but is non-trivial. Pure function, no LLM, no
  history.

What this module does NOT do (out of scope; subsequent milestones own):

- It does NOT replace the renderer (M8 owns ``storytelling_v2``).
- It does NOT change the legacy ``actions_log.json`` shape, the
  ``briefing.html`` content, or anything merchant-facing.
- It does NOT introduce ``p`` / ``q`` / ``CI`` / ``confidence_score`` /
  ``final_score`` into V2 merchant fields.
- It does NOT delete legacy code paths.
- It does NOT integrate Klaviyo / Shopify APIs.

The function is **pure** with respect to its EngineRun input: a new
``EngineRun`` is returned via :func:`dataclasses.replace`. The input is
not mutated.

Behind ``ENGINE_V2_DECIDE=true`` (default OFF), :mod:`src.main` calls
``decide()`` after the M5/M6 V2 blocks and writes the resulting
``EngineRun`` to ``receipts/engine_run.json``. With the flag OFF, the
adapter+guardrails+sizing-shadow chain runs unchanged and ``decide`` is
not invoked. The renderer is unaffected either way.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .engine_run import (
    Abstain,
    Audience,
    AbstainMode,
    DataQualityFlag,
    DecisionState,
    EngineRun,
    EvidenceClass,
    MechanismIntent,
    MechanismType,
    Observation,
    ObservationClassification,
    PlayCard,
    ReasonCode,
    RejectedPlay,
    RevenueRange,
    WatchedSignal,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


#: Maximum number of recommendations the engine ever publishes (PM Q10 #5).
MAX_RECOMMENDATIONS: int = 3

#: Maximum number of rejected plays to render in the "considered" section
#: (PM Q10 #6). The closest-to-firing 6.
MAX_CONSIDERED_RENDERED: int = 6

#: Maximum number of WatchedSignal entries in :attr:`EngineRun.watching`
#: (PM Q2 schema; M7 T7.9: 1-4 entries).
MAX_WATCHING_SIGNALS: int = 4

#: Phase 6A Ticket A4 — hard cap on the new ``recommended_experiments``
#: list. The DS-tightened first-ship contract pins this at 2 (PM Q6).
MAX_RECOMMENDED_EXPERIMENT: int = 2

#: First-ship allowlist of plays eligible for the Recommended Experiment
#: slate. Locked by the campaign-slate contract (Phase 6A Ticket A4).
#: Other targeting plays remain in Considered until the outcome log
#: feedback loop (Phase 6B+) can de-risk additional plays.
RECOMMENDED_EXPERIMENT_ALLOWLIST: frozenset[str] = frozenset(
    {"discount_hygiene", "bestseller_amplify"}
)

#: Audience-overlap threshold (Jaccard) above which a Recommended
#: Experiment candidate is demoted to Considered because it overlaps a
#: Recommended Now card too heavily.
RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD: float = 0.30

#: Class-priority weights for ranking. Higher = stronger.
_CLASS_PRIORITY: dict[EvidenceClass, int] = {
    EvidenceClass.MEASURED: 3,
    EvidenceClass.DIRECTIONAL: 2,
    EvidenceClass.TARGETING: 1,
    EvidenceClass.WEAK: 0,
}

#: HARD data-quality flags that must produce ABSTAIN_HARD with empty
#: recommendations. Mirrors ``src.guardrails.HARD_DATA_QUALITY_FLAGS``;
#: kept in sync defensively so M7 enforces the invariant even when the
#: M5 anomaly gate flag is off.
_HARD_DQ_FLAGS: frozenset[DataQualityFlag] = frozenset(
    {
        DataQualityFlag.BFCM_OVERLAP,
        DataQualityFlag.REFUND_STORM,
        DataQualityFlag.TEST_ORDER_ANOMALY,
        DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY,
        # Sprint 1 Ticket B-7: vertical hard-refuse. Set by
        # ``src.vertical_guard`` BEFORE decide() runs; included here
        # defensively so any downstream consumer that re-classifies an
        # EngineRun by its data_quality_flags treats it as ABSTAIN_HARD.
        DataQualityFlag.VERTICAL_NOT_SUPPORTED,
    }
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _coerce_evidence_class(value) -> EvidenceClass:
    if isinstance(value, EvidenceClass):
        return value
    if value is None:
        return EvidenceClass.TARGETING
    try:
        return EvidenceClass(str(value).strip().lower())
    except ValueError:
        return EvidenceClass.TARGETING


def _evidence_priority(card: PlayCard) -> int:
    """Return the integer class-priority for a PlayCard (higher = stronger)."""
    ec = _coerce_evidence_class(card.evidence_class)
    return _CLASS_PRIORITY.get(ec, 0)


def _p50_for_sort(card: PlayCard) -> float:
    """Return the p50 used for ranking (None / suppressed → -inf).

    A non-suppressed numeric p50 sorts above any suppressed or missing
    range. This aligns with the principle that an unmeasurable card
    ranks below a sized one within the same class.
    """
    rr = card.revenue_range
    if rr is None or rr.suppressed:
        return float("-inf")
    if rr.p50 is None:
        return float("-inf")
    try:
        return float(rr.p50)
    except (TypeError, ValueError):
        return float("-inf")


def _audience_size_for_sort(card: PlayCard) -> int:
    aud = card.audience
    if aud is None or aud.size is None:
        return 0
    try:
        return int(aud.size)
    except (TypeError, ValueError):
        return 0


def _is_measured_or_directional(card: PlayCard) -> bool:
    ec = _coerce_evidence_class(card.evidence_class)
    return ec in (EvidenceClass.MEASURED, EvidenceClass.DIRECTIONAL)


# ---------------------------------------------------------------------------
# Ranking (T7.2)
# ---------------------------------------------------------------------------


def rank_recommendations(cards: Iterable[PlayCard]) -> List[PlayCard]:
    """Rank PlayCards by class-first priority, then by p50, then audience.

    The sort key is ``(class_priority, p50, audience_size, play_id)``
    descending on the first three terms and ascending on ``play_id`` for
    deterministic tie-breaking. ``play_id`` ascending guarantees stable
    output across runs even when audience and p50 collide.

    Args:
        cards: any iterable of PlayCards (typically from
            ``engine_run.recommendations``).

    Returns:
        A new list with the same PlayCard instances sorted in priority
        order. Input is not mutated.
    """

    items = list(cards or [])
    return sorted(
        items,
        key=lambda c: (
            -_evidence_priority(c),
            -_p50_for_sort(c),
            -_audience_size_for_sort(c),
            str(c.play_id or ""),
        ),
    )


# ---------------------------------------------------------------------------
# Considered list
# ---------------------------------------------------------------------------


def _ensure_would_fire_if(rej: RejectedPlay) -> RejectedPlay:
    """S13.6-T1a (Option D): ``RejectedPlay.would_fire_if`` field stripped
    per Pivot 2. This helper is retained as a structural no-op so callers
    upstream don't need to be re-wired in the same commit, but it now
    returns the input unchanged. Future commits may inline ``rej`` at
    every call site.
    """

    return rej


_WOULD_FIRE_IF_TEMPLATE: dict[ReasonCode, str] = {
    ReasonCode.AUDIENCE_TOO_SMALL: (
        "Would fire if the eligible audience grows above the minimum threshold."
    ),
    ReasonCode.AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY: (
        "Would fire if this audience no longer overlaps a higher-priority play."
    ),
    ReasonCode.INVENTORY_BLOCKED: (
        # Synthetic Blocker Fix 4: merchant-readable copy. Does not
        # expose raw cover-days numbers; that detail lives on
        # internal receipts (engine_run.json / debug.html).
        "Would fire when stock on the hero SKU recovers above the cover-days threshold."
    ),
    ReasonCode.NO_MEASURED_SIGNAL: (
        "Would fire once the audience can be measured against a valid comparison group."
    ),
    ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS: (
        "Would fire if the signal is directionally consistent across multiple windows."
    ),
    ReasonCode.ANOMALOUS_WINDOW: (
        "Would fire when no hard data-quality flag affects the analysis window."
    ),
    ReasonCode.COLD_START_INSUFFICIENT_DATA: (
        "Would fire after the store accumulates 90+ days of clean order history."
    ),
    ReasonCode.CANNIBALIZATION_DEMOTED: (
        "Would fire when the portfolio cap can be respected without demoting this play."
    ),
    ReasonCode.RECENTLY_RUN_FATIGUE: (
        "Would fire after this audience has not been recommended in the last 28 days."
    ),
    ReasonCode.MATERIALITY_BELOW_FLOOR: (
        "Would fire if estimated impact cleared the store-size impact threshold."
    ),
    ReasonCode.DATA_QUALITY_FLAG: (
        "Would fire when the data-quality flag is resolved on the analysis window."
    ),
    ReasonCode.CAP_EXCEEDED: (
        "Would fire when the higher-priority recommendations are deprioritized first."
    ),
    ReasonCode.TARGETING_HELD_UNDER_ABSTAIN: (
        "Would fire when at least one measured or directional play "
        "clears evidence and materiality this run."
    ),
    # Sprint 5 Ticket S5-T2 (resolves KI-20).
    ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW: (
        "Would fire when first-to-second conversion data lands via "
        "campaign realization (Phase 9) so a cadence-aware measurement "
        "design can replace the L28 returning-customer-share proxy."
    ),
    # Sprint 7.5 Ticket T3 — prior validation refusal.
    ReasonCode.PRIOR_UNVALIDATED: (
        "Would fire once the play's base_rate prior is promoted to a "
        "validated source (see ``config/priors_sources/``)."
    ),
    # Sprint 6.5 Ticket T4 — R1 window_corroboration CONTRADICTED.
    ReasonCode.WINDOW_DISAGREEMENT: (
        "Would fire when the L28 / L56 / L90 windows agree on the "
        "direction of this signal — one more month of data should "
        "resolve the disagreement."
    ),
}


def _dedupe_rejections(rejections: Iterable[RejectedPlay]) -> List[RejectedPlay]:
    """Keep the first rejection per play_id; preserve insertion order."""

    seen: set[str] = set()
    out: List[RejectedPlay] = []
    for rej in rejections or []:
        key = str(rej.play_id or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(rej)
    return out


def assemble_considered(
    pre_existing: Iterable[RejectedPlay],
    cap_exceeded: Iterable[PlayCard] = (),
    no_measured: Iterable[PlayCard] = (),
    *,
    recommended_play_ids: Iterable[str] = (),
    priority_prepend: Iterable[PlayCard] = (),
    priority_prepend_rejects: Iterable[RejectedPlay] = (),
    engine_run: Optional[EngineRun] = None,
) -> List[RejectedPlay]:
    """Build the considered list per M7.

    Args:
        pre_existing: ``RejectedPlay`` records from upstream guardrails
            (typically ``engine_run.considered``).
        cap_exceeded: PlayCards that exceeded the recommendation cap.
            These are converted into ``RejectedPlay(reason_code=CAP_EXCEEDED)``.
        no_measured: PlayCards demoted because the abstain-soft rule
            removed all measured/directional candidates. These are
            converted into ``RejectedPlay(reason_code=NO_MEASURED_SIGNAL)``.
        recommended_play_ids: any play_ids that survived to the
            recommendations list. These are excluded from considered to
            keep the lists disjoint.
        priority_prepend: PlayCards (typically the Tier-B prior-anchored
            subset of ``cap_exceeded`` identified by
            ``would_be_measured_by is not None``) that MUST survive the
            ``[:MAX_CONSIDERED_RENDERED]`` truncation. Converted to
            ``RejectedPlay(reason_code=CAP_EXCEEDED)`` using the same
            conversion path as ``cap_exceeded`` and emitted BEFORE
            ``pre_existing`` so a flood of upstream guardrail rejections
            can no longer silently drop the load-bearing Tier-B set.
            S7.6-C1 (DS-locked 2026-05-22 single-demote-channel invariant).
        priority_prepend_rejects: RejectedPlay records (Tier-B subset
            partitioned from ``eligibility_rejects``,
            ``prior_unvalidated_rejects``, and ``window_disagreement_rejects``
            by ``would_be_measured_by is not None``) that MUST survive the
            ``[:MAX_CONSIDERED_RENDERED]`` truncation. Emitted ahead of
            ``pre_existing`` so Tier-B cards demoted via ANY single demote
            channel (not just cap-exceeded) are protected. S7.6-T5.6
            (DS verdict 2026-05-23 — restated single-demote-channel
            invariant covering all three sibling reject streams).
        engine_run: optional ``EngineRun`` whose
            ``considered_truncated_count`` we increment when the cap
            ``[:MAX_CONSIDERED_RENDERED]`` actually drops entries.
            Founder-internal CI tripwire signal — not merchant copy.

    Returns:
        A deduplicated list of RejectedPlay entries, with
        ``would_fire_if`` populated from the M7 templates when missing.
        Capped at :data:`MAX_CONSIDERED_RENDERED`.
    """

    rec_ids: set[str] = {str(pid) for pid in (recommended_play_ids or [])}
    out: List[RejectedPlay] = []

    # S7.6-C1: emit priority_prepend FIRST so the truncation cap cannot
    # silently drop Tier-B prior-anchored cards behind a flood of
    # pre_existing guardrail rejections. Conversion mirrors the
    # cap_exceeded branch below verbatim.
    for card in priority_prepend or []:
        if str(card.play_id) in rec_ids:
            continue
        rej = RejectedPlay(
            play_id=card.play_id,
            reason_code=ReasonCode.CAP_EXCEEDED,
        )
        out.append(rej)

    # S7.6-T5.6: emit Tier-B prior-anchored RejectedPlay records (from
    # eligibility_gate / prior_unvalidated / window_disagreement) ahead of
    # pre_existing so the truncation cap cannot silently drop them
    # regardless of which channel demoted them. The original typed
    # reason_code (SIGNAL_INCONSISTENT_ACROSS_WINDOWS / PRIOR_UNVALIDATED
    # / WINDOW_DISAGREEMENT) is preserved — this slot only changes
    # ordering, not reason narration.
    for rej in priority_prepend_rejects or []:
        if str(rej.play_id) in rec_ids:
            continue
        out.append(_ensure_would_fire_if(rej))

    for rej in pre_existing or []:
        if str(rej.play_id) in rec_ids:
            continue
        out.append(_ensure_would_fire_if(rej))

    for card in cap_exceeded or []:
        if str(card.play_id) in rec_ids:
            continue
        rej = RejectedPlay(
            play_id=card.play_id,
            reason_code=ReasonCode.CAP_EXCEEDED,
        )
        out.append(rej)

    for card in no_measured or []:
        if str(card.play_id) in rec_ids:
            continue
        rej = RejectedPlay(
            play_id=card.play_id,
            reason_code=ReasonCode.NO_MEASURED_SIGNAL,
        )
        out.append(rej)

    out = _dedupe_rejections(out)
    pre_trunc_len = len(out)
    truncated = out[:MAX_CONSIDERED_RENDERED]
    dropped = pre_trunc_len - len(truncated)
    if dropped > 0 and engine_run is not None:
        try:
            engine_run.considered_truncated_count = int(
                getattr(engine_run, "considered_truncated_count", 0) or 0
            ) + dropped
        except Exception:
            # Defensive: never let counter wiring break the publish path.
            pass
    return truncated


# ---------------------------------------------------------------------------
# Phase 5.2 — Populate considered from M3 candidates / registry
# ---------------------------------------------------------------------------


#: Mapping from a candidate's preliminary_rejection_reason (M3) to a
#: ReasonCode. Phase 5.2: the M3 detector emits short string codes; we
#: map them onto the typed ReasonCode enum so the V2 considered list
#: explains the hold in merchant-readable copy.
_PRELIM_REASON_MAP: dict[str, ReasonCode] = {
    "audience_zero": ReasonCode.AUDIENCE_TOO_SMALL,
    "audience_too_small": ReasonCode.AUDIENCE_TOO_SMALL,
    "no_builder": ReasonCode.NO_MEASURED_SIGNAL,
    "builder_error": ReasonCode.NO_MEASURED_SIGNAL,
    "below_min_n": ReasonCode.AUDIENCE_TOO_SMALL,
    "no_signal": ReasonCode.NO_MEASURED_SIGNAL,
    "no_data": ReasonCode.COLD_START_INSUFFICIENT_DATA,
    "missing_field": ReasonCode.NO_MEASURED_SIGNAL,
    # Synthetic Blocker Fix 4: M3 stamps SKU-pushing candidates whose
    # backing inventory is below the cover-days threshold with this
    # short code; map it onto the typed INVENTORY_BLOCKED ReasonCode so
    # the V2 considered list explains the hold in plain English.
    "inventory_blocked": ReasonCode.INVENTORY_BLOCKED,
}


#: S-3 reason-code fan-out (B-2 surface a). Maps short codes to the
#: 5 typed ReasonCodes the plan calls for: AUDIENCE_TOO_SMALL,
#: COLD_START, INVENTORY_BLOCKED, MATERIALITY_BELOW_FLOOR, DATA_QUALITY.
#:
#: Sprint 2 closeout (S-3): activated unconditionally. Beauty goldens
#: re-pinned in the same commit (plan §7 Risk #4). The map is kept
#: separate from ``_PRELIM_REASON_MAP`` so the additive provenance is
#: visible at a glance — legacy mappings on top, S-3 fan-out below —
#: and so the single-writer grep test on the typed codes can locate
#: them quickly.
_S3_FANOUT_REASON_MAP: dict[str, ReasonCode] = {
    "data_missing": ReasonCode.DATA_QUALITY_FLAG,
    "data_quality": ReasonCode.DATA_QUALITY_FLAG,
    "cold_start": ReasonCode.COLD_START_INSUFFICIENT_DATA,
    "insufficient_history": ReasonCode.COLD_START_INSUFFICIENT_DATA,
    "materiality_below_floor": ReasonCode.MATERIALITY_BELOW_FLOOR,
    "below_materiality_floor": ReasonCode.MATERIALITY_BELOW_FLOOR,
}


#: Phase 5.7 (defensive cleanup): play_ids that are NOT surfaced in the
#: V2 considered or recommendation paths. Each entry is documented with
#: the reason it is suppressed and the replacement that should appear
#: instead. The legacy emitter is intentionally NOT touched here; this
#: filter only affects the V2 path so legacy receipts stay byte-stable.
PHASE5_V2_SUPPRESS_PLAY_IDS: frozenset[str] = frozenset(
    {
        # Per memory.md: "rename or demote until onsite funnel data
        # exists". The legacy emitter still produces fabricated stats on
        # this play; first_to_second_purchase is the documented successor
        # and is the Phase 5.6 wired pathway.
        "journey_optimization",
    }
)


def _candidate_reason_code(
    cand: Any, registry_entry: Optional[Any] = None
) -> ReasonCode:
    """Map an M3 :class:`Candidate` to a typed :class:`ReasonCode`.

    Order of precedence:
    1. Explicit ``preliminary_rejection_reason`` on the candidate.
    2. Registry's ``evidence_class_default`` is "targeting" -> the play
       is held because the engine has no causal prior to size with
       (Phase 5: until calibration realization data exists).
    3. Default: NO_MEASURED_SIGNAL (the candidate exists but the
       measurement design that would let it surface as primary is not
       wired yet).
    """

    prelim = getattr(cand, "preliminary_rejection_reason", None)
    if prelim:
        key = str(prelim).strip().lower()
        code = _PRELIM_REASON_MAP.get(key)
        if code is not None:
            return code
        # S-3 reason-code fan-out (Sprint 2 closeout): consulted
        # unconditionally. Additive: only inspected for short codes NOT
        # already in _PRELIM_REASON_MAP, so existing mappings are
        # untouched. Beauty goldens were re-pinned in the same commit
        # that flipped this on (plan §7 Risk #4).
        fanout = _S3_FANOUT_REASON_MAP.get(key)
        if fanout is not None:
            return fanout

    if registry_entry is not None:
        ec = getattr(registry_entry, "evidence_class_default", None)
        if ec == "targeting":
            # Phase 5.2 reason: targeting plays are held until a causal
            # prior exists (or campaign-realization data calibrates).
            return ReasonCode.NO_MEASURED_SIGNAL

    return ReasonCode.NO_MEASURED_SIGNAL


#: Reason summary text for considered cards. Keyed by ReasonCode plus
#: a "targeting_non_causal_prior" pseudo-key for the Phase 5.2 case
#: where a registered targeting play is held because the engine has no
#: calibrated lift to size it. Phase 5.2.
_CONSIDERED_REASON_TEXT: dict[ReasonCode, str] = {
    ReasonCode.AUDIENCE_TOO_SMALL: (
        "Eligible audience is below the minimum send threshold this run."
    ),
    ReasonCode.AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY: (
        "Audience overlaps too much with a higher-priority play."
    ),
    ReasonCode.NO_MEASURED_SIGNAL: (
        "No measured signal yet for this play at this store; held as "
        "targeting until campaign outcomes calibrate the lift."
    ),
    ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS: (
        "Signal direction disagrees across the L28 / L56 / L90 windows."
    ),
    ReasonCode.MATERIALITY_BELOW_FLOOR: (
        "Estimated impact is below the materiality floor for a store this size."
    ),
    ReasonCode.CANNIBALIZATION_DEMOTED: (
        "Demoted to keep the portfolio from cannibalizing itself."
    ),
    ReasonCode.INVENTORY_BLOCKED: (
        # Synthetic Blocker Fix 4: merchant-readable copy specified by
        # PM. Raw inventory units / cover_days numbers are intentionally
        # NOT surfaced on the merchant card; they live on internal
        # receipts only.
        "Hero SKU at low stock; held until restock."
    ),
    ReasonCode.ANOMALOUS_WINDOW: (
        "Analysis window is anomalous; results not trustworthy."
    ),
    ReasonCode.COLD_START_INSUFFICIENT_DATA: (
        "Not enough clean order history to recommend this play."
    ),
    ReasonCode.RECENTLY_RUN_FATIGUE: (
        "This audience was recommended recently; held to avoid fatigue."
    ),
    ReasonCode.DATA_QUALITY_FLAG: (
        "Held due to a data-quality flag on the analysis window."
    ),
    ReasonCode.CAP_EXCEEDED: (
        "Outside the top-three recommendations this month."
    ),
    ReasonCode.TARGETING_HELD_UNDER_ABSTAIN: (
        "Held this month because no measured or directional play cleared "
        "evidence requirements; targeting plays do not publish on their own."
    ),
    # Sprint 5 Ticket S5-T2 (resolves KI-20): supplements directional
    # ``first_to_second_purchase`` honest abstain. Surfaces in Considered
    # only when the run's vertical is ``supplements`` and the directional
    # builder did not emit a Recommended card for this play.
    ReasonCode.PRIOR_UNVALIDATED: (
        "Held because the base_rate prior for this play is not yet "
        "validated against a public benchmark or internal study."
    ),
    # Sprint 6.5 Ticket T4 (R1) — multi-window evidence disagreement.
    # Routed by ``_route_window_disagreement_holds`` when
    # ``measurement.window_corroboration == CONTRADICTED``. Surfaces
    # only when ``ENGINE_V2_STORE_PROFILE`` is ON.
    ReasonCode.WINDOW_DISAGREEMENT: (
        "Different time windows of your data disagree on this trend — "
        "we'd want one more month of data before recommending."
    ),
    ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW: (
        "Typical supplement reorder cadence sits at the edge of the L28 "
        "primary window; the supporting signal for first-to-second nudge "
        "did not clear the directional bar on this store."
    ),
}


def _surface_audience_fields_from_card(card: Any) -> Tuple[Optional[int], Optional[str]]:
    """S6-T3.5 Prereq 1: extract (audience_size, audience_definition) for a
    Considered-surface :class:`RejectedPlay`.

    Reads ``card.audience.size`` and ``card.audience.definition`` from the
    upstream :class:`PlayCard`. Both legs return ``None`` when missing /
    malformed; the renderer (T3.z) field-presence-gates each branch.
    """

    aud = getattr(card, "audience", None)
    size_raw = getattr(aud, "size", None) if aud is not None else None
    aud_size: Optional[int]
    if size_raw is None:
        aud_size = None
    else:
        try:
            aud_size = int(size_raw)
        except (TypeError, ValueError):
            aud_size = None
    def_raw = getattr(aud, "definition", None) if aud is not None else None
    aud_def: Optional[str]
    if isinstance(def_raw, str) and def_raw.strip():
        aud_def = def_raw.strip()
    else:
        aud_def = None
    return aud_size, aud_def


# ---------------------------------------------------------------------------
# S13.6-T6 — typed MechanismIntent producer (DS §(d) + Option C 2026-05-31).
# NOTE (S13.7-T7b, KI-NEW-AB): ``_surface_mechanism_for_play`` was deleted here.
# It had zero call sites at S13.7-T7b — producers were switched to
# ``_build_mechanism_intent`` at S13.6-T6; the renderer-side mirror
# ``storytelling_v2._mechanism_for_play`` is its own independent copy.
# Removal confirmed by grep: only the definition and a comment reference
# existed in this file. Dead-code removal per Sub-task C of T7b.
#
# Engine-side authoring of the typed mechanism atom (closed-enum
# MechanismType + parameters dict). Replaces the engine-authored
# mechanism prose path (``_surface_mechanism_for_play``) at the producer
# seam — the renderer-side YAML prose lookup survives in
# storytelling_v2._mechanism_for_play as a debug-only fallback until the
# T8 consumer rewire.
#
# Per founder lock-in #4 (2026-05-30): "Engine ships structured atoms
# only; narration agents render copy." This helper is the substrate;
# narration agents render merchant-facing prose from ``type +
# parameters``.
#
# Mapping audit (T6 audit, 2026-05-31): the 9 mapped play_ids are the
# union of (a) the ``_PRIOR_ANCHORED`` registry in measurement_builder
# (winback_dormant_cohort, cohort_journey_first_to_second,
# aov_lift_via_threshold_bundle, discount_dependency_hygiene,
# replenishment_due), (b) legacy Tier-B builders (bestseller_amplify,
# category_expansion, subscription_nudge, routine_builder), plus the
# alias ``first_to_second_purchase`` covering the legacy directional
# proxy. Unmapped play_ids return ``None`` (strict — do not invent).
#
# Parameter values for the 5 spec'd types are sourced from the
# ``_PRIOR_ANCHORED`` registry constants where applicable (DS Q2 pick
# (b)). Where a value is not present in the registry (windowing /
# offer-type knobs that the builder author hard-coded), the helper
# carries a sensible default with an ``S14`` follow-up to source from
# real-merchant config.
# ---------------------------------------------------------------------------


# Closed map: play_id -> MechanismType. Audit-locked at T6.
_PLAY_ID_TO_MECHANISM_TYPE: Dict[str, MechanismType] = {
    # 5 spec'd types (DS §(d) parameter dicts populated below).
    "winback_dormant_cohort": MechanismType.WINBACK_REACTIVATION_EMAIL,
    "first_to_second_purchase": MechanismType.FIRST_TO_SECOND_NUDGE,
    "cohort_journey_first_to_second": MechanismType.FIRST_TO_SECOND_NUDGE,
    "aov_lift_via_threshold_bundle": MechanismType.THRESHOLD_BUNDLE_OFFER,
    "discount_dependency_hygiene": MechanismType.DISCOUNT_DEPENDENCY_HYGIENE,
    "replenishment_due": MechanismType.REPLENISHMENT_REMINDER,
    # 4 Tier-B types (parameters={} per DS §(d) acceptance).
    "bestseller_amplify": MechanismType.BESTSELLER_AMPLIFY,
    "category_expansion": MechanismType.CATEGORY_EXPANSION,
    "subscription_nudge": MechanismType.SUBSCRIPTION_NUDGE,
    "routine_builder": MechanismType.ROUTINE_BUILDER,
}


def _parameters_for_mechanism(mtype: MechanismType) -> Dict[str, Any]:
    """Return DS §(d) parameter dict for ``mtype``.

    - 5 spec'd types -> the per-type DS §(d) knob set; values copied
      out of the ``_PRIOR_ANCHORED`` registry where applicable, with
      defaults pulled from the existing builder code where the
      registry does not carry a knob. ``# TODO(S14): source from
      real-merchant config`` markers flag knobs that should move to
      per-merchant config in the S14 mechanism-contract pass.
    - 4 Tier-B types + LOOKALIKE_HIGH_VALUE_PROSPECT -> ``{}`` per
      DS §(d) acceptance ("Tier-B types: parameters empty dict
      acceptable for v2.0.0; flesh out at S14+").
    """
    if mtype is MechanismType.WINBACK_REACTIVATION_EMAIL:
        # dormancy_window_days: pulled from
        # measurement_builder._winback_window_bounds default (Beauty:
        # 21-45; supplements: 60-120); the 21-day low is the canonical
        # entry boundary on Beauty. TODO(S14): source per-vertical.
        return {
            "dormancy_window_days": 21,
            "offer_type": "percent_off",  # TODO(S14): source from merchant config
            "measurement_window_days": 30,
        }
    if mtype is MechanismType.FIRST_TO_SECOND_NUDGE:
        # DS §(d) verbatim keys:
        #   days_since_first_order_window: [int, int]
        #   measurement_window_days: int
        # ``days_since_first_order_window`` is sourced from the
        # cohort_journey_first_to_second builder constants in
        # ``src/audience_builders.py`` (the 30 <= days_since <= 90
        # filter at L716, DS-locked 2026-05-19). ``measurement_window_days``
        # is text-derived from the mechanism_text on the
        # cohort_journey_first_to_second ``_PRIOR_ANCHORED`` registry
        # entry ("...second purchase within 30 days.") — there is no
        # numeric registry knob for the measurement window today.
        return {
            "days_since_first_order_window": [30, 90],
            "measurement_window_days": 30,
        }
    if mtype is MechanismType.THRESHOLD_BUNDLE_OFFER:
        # DS §(d) verbatim keys:
        #   threshold_aov: float
        #   current_median_aov: float
        # Neither key is sourceable from the decide-seam today:
        # ``threshold_aov`` is the per-merchant bundle target ($ amount)
        # not carried on the ``aov_lift_via_threshold_bundle``
        # ``_PRIOR_ANCHORED`` registry entry; ``current_median_aov`` is
        # the store's observed median AOV which lives on the store
        # profile / measurement context, not on the registry or the
        # MechanismIntent producer seam. Per DS revision (2026-06-01):
        # set None + TODO(S14) rather than substitute a different knob.
        return {
            "threshold_aov": None,  # TODO(S14): source from per-merchant bundle target ($ amount) at decide-seam
            "current_median_aov": None,  # TODO(S14): source from store_profile observed-AOV at decide-seam
        }
    if mtype is MechanismType.DISCOUNT_DEPENDENCY_HYGIENE:
        # DS §(d) verbatim keys:
        #   current_discount_share: float
        #   target_discount_share: float
        # Neither key is sourceable from the decide-seam today:
        # ``current_discount_share`` is the store's measured
        # heavy-discount-share-of-revenue (computed in
        # ``measurement_builder.compute_heavy_discount_share_of_revenue``
        # but not threaded to the MechanismIntent producer); the
        # ``discount_dependency_hygiene`` builder + registry entry do
        # not expose either as an instance attribute / registry knob
        # at the decide-seam. Per DS revision (2026-06-01): None +
        # TODO(S14) rather than substitute suppression_window_days.
        return {
            "current_discount_share": None,  # TODO(S14): source from measurement_builder.compute_heavy_discount_share_of_revenue at decide-seam
            "target_discount_share": None,  # TODO(S14): source from per-play target on discount_dependency_hygiene builder/registry
        }
    if mtype is MechanismType.REPLENISHMENT_REMINDER:
        # DS §(d) verbatim keys:
        #   replenishment_window_days: int
        #   sku_class: str
        # The ``replenishment_due`` builder computes a per-SKU cadence
        # median at runtime (``src/audience_builders.py``
        # replenishment_due_candidates L351-358); there is no single
        # store-level ``replenishment_window_days`` int on the
        # ``_PRIOR_ANCHORED`` registry entry or the builder seam at
        # the MechanismIntent producer. Similarly ``sku_class`` is a
        # per-cohort attribute (one cohort per in-class SKU) not a
        # single decide-seam value. Per DS revision (2026-06-01):
        # None + TODO(S14) rather than substitute the next_cadence_window
        # string.
        return {
            "replenishment_window_days": None,  # TODO(S14): source from per-SKU cadence median at builder seam (replenishment_due_candidates)
            "sku_class": None,  # TODO(S14): source from in-class SKU vertical key (beauty regex / supplements unit-coherent key) at builder seam
        }
    # Tier-B + lookalike: empty per DS §(d) acceptance.
    return {}


def _build_mechanism_intent(play_id: Optional[str]) -> Optional[MechanismIntent]:
    """S13.6-T6: build the typed :class:`MechanismIntent` atom for ``play_id``.

    Returns ``None`` for any unmapped play_id (legacy plays without a
    typed atom — strict, do not invent). Otherwise returns
    :class:`MechanismIntent` with the closed-enum ``type`` and the
    DS §(d) ``parameters`` dict (or ``{}`` for Tier-B + lookalike per
    DS §(d) acceptance).
    """
    if not play_id:
        return None
    mtype = _PLAY_ID_TO_MECHANISM_TYPE.get(str(play_id))
    if mtype is None:
        return None
    return MechanismIntent(type=mtype, parameters=_parameters_for_mechanism(mtype))


def _evidence_snapshot_for_candidate(cand: Any) -> Optional[str]:
    """Build a short evidence-snapshot string for a Candidate.

    Carries audience size and the segment definition. Never includes
    p / q / CI / confidence_score.
    """

    aud_size = getattr(cand, "audience_size", None)
    segdef = getattr(cand, "segment_definition", "") or ""
    parts: List[str] = []
    if aud_size is not None:
        try:
            parts.append(f"Audience: {int(aud_size):,} people")
        except (TypeError, ValueError):
            pass
    if segdef:
        # Avoid extremely long lines.
        snippet = str(segdef)
        if len(snippet) > 140:
            snippet = snippet[:140].rstrip() + "..."
        parts.append(snippet)
    if not parts:
        return None
    return " | ".join(parts)


def populate_considered_from_candidates(
    engine_run: EngineRun,
    candidates: Iterable[Any],
    *,
    registry: Optional[Mapping[str, Any]] = None,
    vertical: Optional[str] = None,
    subvertical: Optional[str] = None,
) -> EngineRun:
    """Phase 5.2: populate ``considered[]`` from M3 detector candidates.

    For every detected candidate that is NOT in the recommendations list
    AND is NOT already represented in ``considered``, build a typed
    :class:`RejectedPlay` with:

    - ``reason_code`` mapped from the candidate's
      ``preliminary_rejection_reason`` or its registry's
      ``evidence_class_default``.
    - ``reason_text`` from :data:`_CONSIDERED_REASON_TEXT`.
    - ``evidence_snapshot`` from audience size + segment definition.
    - ``would_fire_if`` from :data:`_WOULD_FIRE_IF_TEMPLATE`.

    Plays whose ``vertical_applicable`` does not include the run's
    vertical are skipped (Phase 5.2 ``vertical_not_applicable`` is not
    yet a first-class ReasonCode; we just suppress them quietly to
    keep the considered list relevant).

    Returns a new EngineRun with the augmented considered list.
    Order: existing ``considered`` first, then new ones in registry
    iteration order. Capped at :data:`MAX_CONSIDERED_RENDERED`.
    """

    if engine_run is None:
        return EngineRun()

    cand_list = list(candidates or [])
    if not cand_list:
        return engine_run

    if registry is None:
        try:
            from .play_registry import PLAYS as _PLAYS

            registry = _PLAYS
        except Exception:
            registry = {}

    recommended_ids: set[str] = {
        str(c.play_id) for c in (engine_run.recommendations or [])
    }
    existing_considered_ids: set[str] = {
        str(r.play_id) for r in (engine_run.considered or [])
    }

    new_rejections: List[RejectedPlay] = []
    vertical_lc = (vertical or "").strip().lower() or None

    for cand in cand_list:
        play_id = str(getattr(cand, "play_id", "") or "")
        if not play_id:
            continue
        if play_id in recommended_ids:
            continue
        if play_id in existing_considered_ids:
            continue
        # Phase 5.7: suppress demoted plays from the V2 path.
        if play_id in PHASE5_V2_SUPPRESS_PLAY_IDS:
            continue

        registry_entry = registry.get(play_id) if registry else None

        # Phase 5.2: skip plays that are not applicable to this vertical.
        # We simply suppress them rather than rendering a confusing
        # "vertical_not_applicable" card. Empty applicable set means "all".
        if registry_entry is not None and vertical_lc is not None:
            applicable = getattr(registry_entry, "vertical_applicable", None)
            if applicable:
                if vertical_lc not in {str(v).strip().lower() for v in applicable}:
                    continue

        code = _candidate_reason_code(cand, registry_entry)
        reason_text = _CONSIDERED_REASON_TEXT.get(code) or "Held back."
        snapshot = _evidence_snapshot_for_candidate(cand)
        would_fire = _WOULD_FIRE_IF_TEMPLATE.get(code)

        # S6-T3.5 Prereq 1: lift the Considered-surface fields from the
        # Candidate (which already carries audience_size + segment_definition
        # by the AudienceResult contract). Mechanism comes from priors.yaml
        # via the already-shipped priors_loader.get_mechanism accessor.
        # Renderer (T3.z) field-presence-gates each branch; None values
        # fall through to the legacy render shape.
        aud_size_c = getattr(cand, "audience_size", None)
        try:
            aud_size_field = int(aud_size_c) if aud_size_c is not None else None
        except (TypeError, ValueError):
            aud_size_field = None
        aud_def_c = getattr(cand, "segment_definition", None)
        aud_def_field = (
            str(aud_def_c).strip() if isinstance(aud_def_c, str) and aud_def_c.strip() else None
        )
        # S13.6-T6: swap from YAML-prose lookup to the typed
        # MechanismIntent atom. Returns None for unmapped play_ids.
        mech_field = _build_mechanism_intent(play_id)

        new_rejections.append(
            RejectedPlay(
                play_id=play_id,
                reason_code=code,
                audience_size=aud_size_field,
                audience_definition=aud_def_field,
                mechanism=mech_field,
            )
        )

    if not new_rejections:
        return engine_run

    # S7.6-FIX (2026-05-22): priority_prepend mirror of the
    # ``assemble_considered`` seam (decide.py:343-409). The S6/S7-wired
    # Tier-B plays (``_PRIOR_ANCHORED`` registry at
    # measurement_builder.py:717) were already being typed correctly by
    # the loop above (e.g. winback_dormant_cohort -> AUDIENCE_TOO_SMALL,
    # aov_lift_via_threshold_bundle -> DATA_QUALITY_FLAG) but, when
    # appended AFTER ``engine_run.considered``, they sorted behind 6
    # legacy guardrail rejections and got truncated off by the
    # ``[:MAX_CONSIDERED_RENDERED=6]`` cap. Per founder decision
    # (CLAUDE.md 2026-05-22 single-demote-channel invariant): the
    # truncation must preferentially drop legacy plays so the
    # load-bearing Tier-B set survives.
    #
    # Partition new_rejections into the Tier-B priority set and the
    # remainder; dedup keeps the FIRST entry per play_id so a Tier-B
    # entry at the front wins over any duplicate downstream entry
    # (mirrors ``_dedupe_rejections`` contract at decide.py:329-340).
    try:
        from .measurement_builder import _PRIOR_ANCHORED as _PRIOR_ANCHORED_REG
    except Exception:
        _PRIOR_ANCHORED_REG = {}
    tier_b_new: List[RejectedPlay] = []
    non_tier_b_new: List[RejectedPlay] = []
    for rej in new_rejections:
        if str(rej.play_id) in _PRIOR_ANCHORED_REG:
            tier_b_new.append(rej)
        else:
            non_tier_b_new.append(rej)

    merged_pre = (
        tier_b_new
        + list(engine_run.considered or [])
        + non_tier_b_new
    )
    merged_dedup = _dedupe_rejections(merged_pre)
    merged = merged_dedup[:MAX_CONSIDERED_RENDERED]
    # Truncation accounting: counter increments when the cap actually
    # drops entries. Founder-internal CI tripwire signal — not merchant
    # copy. Tier-B-presence invariant test pins zero silent drops of
    # _PRIOR_ANCHORED play_ids on Beauty + Supplements fixtures.
    dropped = len(merged_dedup) - len(merged)
    new_truncated = int(
        getattr(engine_run, "considered_truncated_count", 0) or 0
    ) + max(dropped, 0)
    return replace(
        engine_run,
        considered=merged,
        considered_truncated_count=new_truncated,
    )


# ---------------------------------------------------------------------------
# Watching builder (T7.9)
# ---------------------------------------------------------------------------


def _trend_for_change(change: Optional[float]) -> Optional[str]:
    if change is None:
        return None
    try:
        c = float(change)
    except (TypeError, ValueError):
        return None
    if c > 1e-6:
        return "up"
    if c < -1e-6:
        return "down"
    return "flat"


def _threshold_text(metric: Optional[str]) -> Optional[str]:
    """Return a deterministic threshold-to-act string for known metrics.

    Per the M7 plan T7.9, the watching section says, e.g., "AOV down 2%
    -- would need 5% drop to fire AOV play." The string is template-only.
    Unknown metrics return None.

    Phase 5.3: extended to cover ``returning_customer_share`` and
    ``net_sales`` so the Beauty Brand fixture (and similar stores)
    produces at least one Watching entry on every run.
    """

    if not metric:
        return None
    m = str(metric).strip().lower()
    table = {
        "aov": "+/- 5% to fire an AOV play",
        "repeat_rate_within_window": "+/- 1pp to fire a retention play",
        "orders": "+/- 10% to fire an orders-driven play",
        "returning_customer_share": (
            "+/- 2pp to revisit retention focus"
        ),
        "net_sales": "+/- 10% to revisit revenue plays",
    }
    return table.get(m)


#: Metrics that are load-bearing for the merchant's read of the store.
#: Phase 5.3: even when these metrics are stable (zero change), we surface
#: a "stable, watching" entry so the Watching section is not empty on a
#: healthy store.
#:
#: Phase 6A Ticket A1: ``aov`` joins the load-bearing set. The campaign
#: slate contract names exactly four load-bearing metrics
#: (``returning_customer_share``, ``net_sales``,
#: ``repeat_rate_within_window``, ``aov``) and pins a
#: small_store_240d-style fixture test that asserts at least one
#: surfaces in Watching when computable. ``orders`` is retained as a
#: domain-internal load-bearing signal (Phase 5.3) but is not in the
#: contract's named four.
_LOAD_BEARING_WATCH_METRICS: frozenset[str] = frozenset(
    {
        "orders",
        "net_sales",
        "returning_customer_share",
        "repeat_rate_within_window",
        "aov",
    }
)


def build_watching(
    state_of_store: Iterable[Observation],
    *,
    max_signals: int = MAX_WATCHING_SIGNALS,
) -> List[WatchedSignal]:
    """Build a deterministic Watching section from state-of-store observations.

    Pure function. Reads only the typed Observations already on the
    EngineRun (built by :mod:`src.state_of_store` in M1). Rules:

    - HELD observations whose ``change_magnitude`` is non-zero (i.e., a
      metric moved a little, but not enough to be classified MOVED) are
      candidates.
    - HELD observations on **load-bearing metrics**
      (:data:`_LOAD_BEARING_WATCH_METRICS`) with zero change still
      surface as a "stable, watching" signal (Phase 5.3) so a healthy
      store still gets a populated Watching section.
    - ANOMALOUS observations are ignored here (they belong to the
      data-quality footer; including them would double-render).
    - MOVED observations on **non-load-bearing metrics** are ignored
      here (they belong to the state-of-store paragraph; the Watching
      section is normally about the stuff that did NOT move enough to
      act on).
    - **Phase 6A Ticket A1 fallback:** MOVED observations on load-bearing
      metrics surface as Watching only when the HELD pass produced no
      candidates AT ALL. This addresses small_store_240d-style fixtures
      where every load-bearing metric is volatile enough to be MOVED
      but the merchant still benefits from at least one "we're watching
      X" line. Phase 5.3 contract for HELD observations is unchanged.
    - The output is sorted by **load-bearing first**, then by absolute
      change magnitude descending (so the most-likely-to-act-next
      signal is first), then by metric name ascending for deterministic
      ties.
    - Capped at ``max_signals`` (default 4).
    """

    obs_list = list(state_of_store or [])
    candidates: List[WatchedSignal] = []
    for obs in obs_list:
        cls = obs.classification
        if cls != ObservationClassification.HELD:
            continue
        metric = str(obs.supporting_metric or "")
        change = obs.change_magnitude
        c: Optional[float] = None
        if change is not None:
            try:
                c = float(change)
            except (TypeError, ValueError):
                c = None

        is_load_bearing = metric in _LOAD_BEARING_WATCH_METRICS

        # Skip metrics that are missing change AND not load-bearing.
        if c is None and not is_load_bearing:
            continue

        # Skip non-load-bearing metrics with zero change.
        if c is not None and abs(c) < 1e-9 and not is_load_bearing:
            continue

        # Phase 5.3: load-bearing metrics with no/zero change render as
        # "flat" (stable, watching).
        trend = _trend_for_change(c) if c is not None else "flat"

        candidates.append(
            WatchedSignal(
                metric=metric,
                current=None,
                prior=None,
                trend=trend,
                threshold_to_act=_threshold_text(metric),
            )
        )

    # Phase 6A Ticket A1 fallback: when the HELD pass produced no
    # Watching candidates at all, surface MOVED load-bearing metrics so
    # the merchant always gets at least one "watching" line when any
    # of the four load-bearing metrics is computable. Non-load-bearing
    # MOVED observations remain excluded (they belong to the
    # state-of-store paragraph). The fallback is deliberately scoped
    # to the empty-HELD case so it cannot quietly re-classify a
    # strongly-moved AOV on a healthy store as "we are watching AOV"
    # instead of "AOV moved up X%".
    if not candidates:
        for obs in obs_list:
            if obs.classification != ObservationClassification.MOVED:
                continue
            metric = str(obs.supporting_metric or "")
            if metric not in _LOAD_BEARING_WATCH_METRICS:
                continue
            change = obs.change_magnitude
            try:
                c = float(change) if change is not None else None
            except (TypeError, ValueError):
                c = None
            trend = _trend_for_change(c) if c is not None else "flat"
            candidates.append(
                WatchedSignal(
                    metric=metric,
                    current=None,
                    prior=None,
                    trend=trend,
                    threshold_to_act=_threshold_text(metric),
                )
            )

    # Build a magnitude map for sorting, using the original observations.
    mag: dict[str, float] = {}
    for obs in obs_list:
        if obs.change_magnitude is None:
            continue
        try:
            mag[str(obs.supporting_metric or "")] = abs(float(obs.change_magnitude))
        except (TypeError, ValueError):
            continue
    # Phase 6A Ticket A1 prioritization: load-bearing metrics surface
    # ahead of non-load-bearing metrics regardless of magnitude. Within
    # each tier, sort by absolute change magnitude descending, then by
    # metric name ascending for deterministic ties.
    candidates.sort(
        key=lambda w: (
            0 if str(w.metric or "") in _LOAD_BEARING_WATCH_METRICS else 1,
            -mag.get(str(w.metric or ""), 0.0),
            str(w.metric or ""),
        )
    )

    return candidates[:max_signals]


# ---------------------------------------------------------------------------
# Abstain state machine (T7.4, T7.7)
# ---------------------------------------------------------------------------


def _has_hard_dq_flag(flags: Iterable[DataQualityFlag]) -> bool:
    for f in flags or []:
        if f in _HARD_DQ_FLAGS:
            return True
    return False


#: Default merchant-readable ABSTAIN_SOFT reason. Phase 5.1: replaces the
#: prior engineering-jargon string ("no measured or directional
#: recommendation cleared materiality + cannibalization gating") so the
#: V2 briefing reads as a useful memo, not an error page.
ABSTAIN_SOFT_DEFAULT_REASON: str = (
    "Your store is healthy this month. We did not find a play with strong "
    "enough evidence to recommend as a primary action. Here is what we "
    "evaluated and what we are watching."
)

#: Specific merchant-readable ABSTAIN_SOFT reasons keyed by the dominant
#: gate that fired. Selected in :func:`_abstain_soft_reason_text` based on
#: the upstream ``considered`` list. Phase 5.1.
ABSTAIN_SOFT_REASONS: dict[str, str] = {
    "no_measured": (
        "We evaluated this month's plays but no primary play cleared "
        "evidence requirements. See what we considered and what we are "
        "watching below."
    ),
    "materiality": (
        "We evaluated this month's plays but they were below the impact "
        "threshold for a store your size. See what we considered and "
        "what we are watching below."
    ),
    "overlap": (
        "We evaluated this month's plays but overlapping audiences "
        "reduced confidence in recommending multiple plays. See what we "
        "considered and what we are watching below."
    ),
}


def _abstain_soft_reason_text(considered: Iterable[RejectedPlay]) -> str:
    """Pick the merchant-readable ABSTAIN_SOFT reason text.

    Looks at the dominant rejection reason among ``considered`` to give
    a slightly more specific merchant-facing string. Falls back to the
    generic default. Pure function — no side effects.
    """

    recs = list(considered or [])
    if not recs:
        return ABSTAIN_SOFT_DEFAULT_REASON

    # Count the rejection reason codes; pick the most common gate.
    counts: dict[str, int] = {}
    for rej in recs:
        code = getattr(rej.reason_code, "value", None) or str(rej.reason_code or "")
        counts[code] = counts.get(code, 0) + 1
    if not counts:
        return ABSTAIN_SOFT_DEFAULT_REASON

    top_code = max(counts.items(), key=lambda kv: kv[1])[0]
    if top_code == ReasonCode.MATERIALITY_BELOW_FLOOR.value:
        return ABSTAIN_SOFT_REASONS["materiality"]
    if top_code in (
        ReasonCode.AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY.value,
        ReasonCode.CANNIBALIZATION_DEMOTED.value,
    ):
        return ABSTAIN_SOFT_REASONS["overlap"]
    if top_code in (
        ReasonCode.NO_MEASURED_SIGNAL.value,
        ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS.value,
    ):
        return ABSTAIN_SOFT_REASONS["no_measured"]
    return ABSTAIN_SOFT_DEFAULT_REASON


_MODE_DRIVING_REASONS = frozenset(
    {
        ReasonCode.PRIOR_UNVALIDATED,
        ReasonCode.MATERIALITY_BELOW_FLOOR,
        ReasonCode.AUDIENCE_TOO_SMALL,
    }
)

# Reason codes synthesized BY the ABSTAIN_SOFT path itself (Fix 3 +
# B3 experiment-side routing). These MUST be excluded from the typed
# precedence count, otherwise the mode-picker would self-contaminate
# whenever decide() routed any targeting head into Considered under an
# ABSTAIN_SOFT decision. See DS Gap F verdict (2026-05-20).
_NON_MODE_DRIVING_SELF_REASONS = frozenset(
    {ReasonCode.TARGETING_HELD_UNDER_ABSTAIN}
)


def _compute_abstain_mode(
    state: DecisionState,
    considered: Iterable[RejectedPlay],
    *,
    flag_on: bool,
    four_state_flag_on: bool = False,
) -> Optional[AbstainMode]:
    """Pick the typed :class:`AbstainMode` for an Abstain dataclass.

    Sprint 7.5 Ticket T3: only emit a typed mode when the priors-
    validation flag (``flag_on``) is ON. When flag-off, return ``None``
    so the serialized :class:`Abstain` shape stays byte-identical to
    pre-T3 runs (M0 + Beauty pinned + supplements G-1 invariant).

    Sprint 7 Ticket T4: when ``four_state_flag_on`` is ON (driven by
    ``ENGINE_V2_ABSTAIN_4STATE``), apply the DS-locked Gap F precedence
    rule across the 4-state palette. When ``four_state_flag_on`` is
    OFF (default), preserve the legacy 2-state mapping so all pinned
    fixtures remain byte-identical at T4 land:

    Legacy 2-state mapping (four_state_flag_on=False):

    - ``state != ABSTAIN_SOFT`` -> ``None``.
    - Any considered entry carries
      :data:`ReasonCode.PRIOR_UNVALIDATED` ->
      :data:`AbstainMode.SOFT_PRIOR_UNVALIDATED`.
    - Otherwise -> :data:`AbstainMode.SOFT_AWAITING_MEASUREMENT`.

    4-state precedence (four_state_flag_on=True, DS Gap F verdict
    2026-05-20):

    1. ``state == ABSTAIN_HARD`` -> ``None`` (data-quality flags own
       this; never typed-tag). Explicit pin even though Sprint 7.5
       T3 already returned ``None`` for non-SOFT states.
    2. ``state != ABSTAIN_SOFT`` -> ``None``.
    3. ``ABSTAIN_SOFT`` AND no Considered entries ->
       :data:`AbstainMode.SOFT_AWAITING_MEASUREMENT` (preserve the
       existing default; DS-flagged missed edge).
    4. Count Considered reason codes EXCLUDING
       :data:`ReasonCode.TARGETING_HELD_UNDER_ABSTAIN` (synthesized
       by the ABSTAIN_SOFT path itself; self-contamination guard).
    5. If a single mode-driving class
       (PRIOR_UNVALIDATED / MATERIALITY_BELOW_FLOOR /
       AUDIENCE_TOO_SMALL) is >=60% of the typed Considered entries,
       return that class's mode.
    6. Else if PRIOR_UNVALIDATED is materially present (>=30% of
       typed entries), return
       :data:`AbstainMode.SOFT_PRIOR_UNVALIDATED` (prior-gap is the
       strongest typed claim; tiebreak per DS verdict).
    7. Else -> :data:`AbstainMode.SOFT_AWAITING_MEASUREMENT`
       (catch-all; covers mixed reason sets and entries composed only
       of non-mode-driving codes such as WINDOW_DISAGREEMENT or
       NO_MEASURED_SIGNAL).
    """

    if not flag_on:
        return None
    # Explicit ABSTAIN_HARD pin (DS-flagged missed edge).
    if state == DecisionState.ABSTAIN_HARD:
        return None
    if state != DecisionState.ABSTAIN_SOFT:
        return None

    if not four_state_flag_on:
        # Legacy 2-state path (Sprint 7.5 T3 semantics preserved).
        for rej in considered or []:
            code = getattr(rej, "reason_code", None)
            if code == ReasonCode.PRIOR_UNVALIDATED:
                return AbstainMode.SOFT_PRIOR_UNVALIDATED
        return AbstainMode.SOFT_AWAITING_MEASUREMENT

    # 4-state precedence (T4 + DS Gap F).
    typed_codes: List[ReasonCode] = []
    for rej in considered or []:
        code = getattr(rej, "reason_code", None)
        if code is None:
            continue
        # Self-contamination guard: TARGETING_HELD_UNDER_ABSTAIN is
        # synthesized BY this path; exclude from mode-driving count.
        if code in _NON_MODE_DRIVING_SELF_REASONS:
            continue
        typed_codes.append(code)

    if not typed_codes:
        # Empty Considered (after self-exclusion) -> default to
        # awaiting-measurement (preserve existing behavior).
        return AbstainMode.SOFT_AWAITING_MEASUREMENT

    total = len(typed_codes)
    counts: Dict[ReasonCode, int] = {}
    for code in typed_codes:
        if code in _MODE_DRIVING_REASONS:
            counts[code] = counts.get(code, 0) + 1

    # Rule 5: majority rule (>=60%) for any single mode-driving class.
    for code, n in counts.items():
        if n / total >= 0.60:
            if code == ReasonCode.PRIOR_UNVALIDATED:
                return AbstainMode.SOFT_PRIOR_UNVALIDATED
            if code == ReasonCode.MATERIALITY_BELOW_FLOOR:
                return AbstainMode.SOFT_BELOW_FLOOR
            if code == ReasonCode.AUDIENCE_TOO_SMALL:
                return AbstainMode.SOFT_AUDIENCE_TOO_SMALL

    # Rule 6: PRIOR_UNVALIDATED tiebreak at >=30%.
    pu_count = counts.get(ReasonCode.PRIOR_UNVALIDATED, 0)
    if pu_count > 0 and pu_count / total >= 0.30:
        return AbstainMode.SOFT_PRIOR_UNVALIDATED

    # Rule 7: catch-all.
    return AbstainMode.SOFT_AWAITING_MEASUREMENT


def _route_window_disagreement_holds(
    recommendations: Iterable[PlayCard],
    *,
    flag_on: bool,
) -> Tuple[List[PlayCard], List[RejectedPlay]]:
    """Split incoming recs into ``(kept, refused_window_disagreement)``.

    Sprint 6.5 Ticket T4 (R1): when ``ENGINE_V2_STORE_PROFILE`` is ON,
    any incoming PlayCard whose
    ``measurement.window_corroboration == CONTRADICTED`` is routed to
    Considered with :data:`ReasonCode.WINDOW_DISAGREEMENT`. Flag-off
    path returns ``(list(recommendations), [])`` unchanged — preserves
    M0 / Beauty / supplements byte-identity.

    Targeting cards (``measurement is None``) cannot have a window
    corroboration and are passed through unchanged.
    """

    if not flag_on:
        return list(recommendations or []), []

    kept: List[PlayCard] = []
    refused: List[RejectedPlay] = []
    for card in recommendations or []:
        meas = getattr(card, "measurement", None)
        wc = getattr(meas, "window_corroboration", None) if meas is not None else None
        # Compare by enum-value for robustness across string/enum coercion.
        wc_value = wc.value if hasattr(wc, "value") else wc
        if wc_value == "CONTRADICTED":
            # S6-T3.5 Prereq 1: populate T3.z merchant-facing surface
            # fields from the PlayCard. Source values flow from the
            # validated PlayCard (audience.size / audience.definition)
            # and priors_loader.get_mechanism (already-loaded YAML
            # metadata.mechanism). Renderer branches gracefully on
            # None when a card has no Audience or no authored mechanism.
            aud_size, aud_def = _surface_audience_fields_from_card(card)
            # S13.6-T6: typed MechanismIntent atom (None for unmapped play_ids).
            mech = _build_mechanism_intent(card.play_id)
            refused.append(
                RejectedPlay(
                    play_id=str(card.play_id),
                    reason_code=ReasonCode.WINDOW_DISAGREEMENT,
                    audience_size=aud_size,
                    audience_definition=aud_def,
                    mechanism=mech,
                    # S7.6-T5.6: preserve Tier-B discriminator across demote
                    # channel so the assembly seam can prepend Tier-B cards
                    # ahead of pre_existing in assemble_considered.
                    would_be_measured_by=getattr(card, "would_be_measured_by", None),
                )
            )
        else:
            kept.append(card)
    return kept, refused


def _apply_window_corroboration_bumps(
    recommendations: Iterable[PlayCard],
    *,
    flag_on: bool,
) -> List[PlayCard]:
    """Bump ``confidence_label`` one notch on CORROBORATED cards.

    Sprint 6.5 Ticket T4 (R1): when the profile flag is ON,
    ``measurement.window_corroboration == CORROBORATED`` bumps an
    Emerging/Targeting MEASURED/DIRECTIONAL card to ``Strong`` (tier
    ceiling). Targeting cards (``measurement is None``) never bump
    because they have no per-window evidence to corroborate (Tier C
    cannot promote to Tier B). ``Strong`` cards stay ``Strong``.
    NEUTRAL / CONTRADICTED / None are no-ops here.
    """

    from dataclasses import replace

    if not flag_on:
        return list(recommendations or [])

    out: List[PlayCard] = []
    for card in recommendations or []:
        meas = getattr(card, "measurement", None)
        if meas is None:
            out.append(card)
            continue
        wc = getattr(meas, "window_corroboration", None)
        wc_value = wc.value if hasattr(wc, "value") else wc
        if wc_value != "CORROBORATED":
            out.append(card)
            continue
        # Tier ceiling: MEASURED/DIRECTIONAL → Strong (no cross-tier bump).
        if str(card.evidence_class) not in {
            "EvidenceClass.MEASURED",
            "EvidenceClass.DIRECTIONAL",
            "measured",
            "directional",
        }:
            # Targeting / weak / blocked never bump.
            out.append(card)
            continue
        current = card.confidence_label or "Emerging"
        if current == "Strong":
            out.append(card)
            continue
        out.append(replace(card, confidence_label="Strong"))
    return out


def _route_prior_unvalidated_holds(
    recommendations: Iterable[PlayCard],
    *,
    flag_on: bool,
) -> Tuple[List[PlayCard], List[RejectedPlay]]:
    """Split incoming recs into (kept, refused_as_prior_unvalidated).

    Sprint 7.5 Ticket T3: when ``ENGINE_V2_PRIORS_VALIDATION`` is ON, any
    incoming PlayCard whose ``revenue_range.drivers`` flag a
    ``prior_unvalidated`` suppression reason (emitted by
    :func:`src.sizing.size_play` under the same flag) is routed to the
    Considered list with :data:`ReasonCode.PRIOR_UNVALIDATED` rather than
    surfacing as a recommendation. Flag-off path: the function returns
    ``(list(recommendations), [])`` unchanged — preserves M0 byte-identity.
    """

    if not flag_on:
        return list(recommendations or []), []

    kept: List[PlayCard] = []
    refused: List[RejectedPlay] = []
    for card in recommendations or []:
        rr = getattr(card, "revenue_range", None)
        is_prior_unvalidated = False
        if rr is not None and getattr(rr, "suppressed", False):
            for d in getattr(rr, "drivers", None) or []:
                if isinstance(d, dict) and d.get("reason") == "prior_unvalidated":
                    is_prior_unvalidated = True
                    break
        if is_prior_unvalidated:
            # S6-T3.5 Prereq 1: populate T3.z merchant-facing surface
            # fields. PRIOR_UNVALIDATED holds carry the typed
            # "no projection" copy in the renderer; the cohort row and
            # mechanism line are still informative for the merchant.
            aud_size, aud_def = _surface_audience_fields_from_card(card)
            # S13.6-T6: typed MechanismIntent atom (None for unmapped play_ids).
            mech = _build_mechanism_intent(card.play_id)
            refused.append(
                RejectedPlay(
                    play_id=str(card.play_id),
                    reason_code=ReasonCode.PRIOR_UNVALIDATED,
                    audience_size=aud_size,
                    audience_definition=aud_def,
                    mechanism=mech,
                    # S7.6-T5.6: preserve Tier-B discriminator across demote
                    # channel so the assembly seam can prepend Tier-B cards
                    # ahead of pre_existing in assemble_considered.
                    would_be_measured_by=getattr(card, "would_be_measured_by", None),
                )
            )
        else:
            kept.append(card)
    return kept, refused


# ---------------------------------------------------------------------------
# Sprint 7.6 Ticket T6 — observed-effect eligibility gate + 3-state copy
# ladder.
#
# Architecture (per DS architect verdict 2026-05-23
# ``agent_outputs/ecommerce-ds-architect-t5_5-joint-gate-verdict-2026-05-23.md``):
#
# The Tier-B observed-effect helpers (T1 winback, T2 replenishment, T3
# discount_hygiene, T4 journey, T5 aov_bundle) compute their per-window
# results and stash a :class:`MultiWindowAgreement` payload onto the card's
# ``blend_provenance`` driver (see measurement_builder.py:2226-2250). T6
# consumes that payload at the decide-layer routing seam --- mirroring the
# Sprint 7.5 ``_route_prior_unvalidated_holds`` precedent --- and routes
# joint-fail / sign-disagreement cards to Considered with
# :data:`ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS`.
#
# The gate's predicate has TWO clauses:
#
# - **Clause 1 (original T6 spec).** ``observed_n > min_eligibility_n`` AND
#   ``sign_agreement_count < 2``  →  downgrade. Applies to ALL builders.
#
# - **Clause 2 (DS amendment).** For builders that stash ``*_band`` windows
#   (detect-by-keys; currently only ``aov_lift_via_threshold_bundle``), the
#   ``L28`` AND ``L28_band`` window p-values must BOTH be present and
#   ``< 0.10``. If either is None or ``>= 0.10`` → downgrade. The joint
#   clause is a no-op for builders whose ``windows`` dict has no ``*_band``
#   key (T1 / T2 / T3 / T4).
#
# The 3-state copy ladder bakes into ``why_now`` at the decide-layer seam
# (kept here rather than at card-build time so the entire gate behavior
# is reachable behind one flag):
#
# - ``cold`` (n=0 or n <= min_eligibility_n): why_now unchanged
#   (byte-identical to flag-OFF).
# - ``accumulating`` (posterior_ratio in [0.2, 0.6)): "Cohort signal is
#   accumulating — " prepended to why_now.
# - ``mature`` (posterior_ratio >= 0.6): "Cohort signal dominates — "
#   prepended to why_now.
#
# ``posterior_ratio = observed_n / (observed_n + pseudo_n_effective)``;
# read from the stashed ``pseudo_n`` + ``observed_n`` on
# ``blend_provenance`` (no recomputation).
# ---------------------------------------------------------------------------

# S13.6-T1a (Option D, founder + DS approved 2026-05-30): the 3-state
# ``why_now`` copy ladder constants are stripped per Pivot 2 (engine
# emits no merchant-facing prose). ``why_now`` itself is stripped from
# the PlayCard dataclass in the same commit. The copy ladder was the
# strongest Pivot-2 violation in the codebase.
_JOINT_TEST_P_MAX = 0.10  # DS verdict 2026-05-23: BOTH L28 and L28_band p<0.10


def _blend_provenance_for_card(card: PlayCard) -> Optional[Mapping[str, Any]]:
    """Return the ``blend_provenance`` driver dict on the card, if any.

    Returns None when the card has no revenue_range, no drivers, or no
    blend_provenance entry. Pure read; never mutates.
    """

    rr = getattr(card, "revenue_range", None)
    if rr is None:
        return None
    for d in getattr(rr, "drivers", None) or []:
        if isinstance(d, dict) and d.get("name") == "blend_provenance":
            return d
    return None


def _has_band_window_stash(observed_windows: Mapping[str, Any]) -> bool:
    """Detect-by-keys: does this observed-effect stash carry ``*_band`` legs?

    Currently only T5 ``aov_lift_via_threshold_bundle`` stashes band
    windows (``L28_band`` / ``L56_band`` / ``L90_band``). Future
    multi-leg builders that follow the same pattern are picked up
    automatically without a play_id hardcode.
    """

    for k in observed_windows.keys():
        if str(k).endswith("_band"):
            return True
    return False


def _eligibility_verdict(
    blend_prov: Mapping[str, Any],
    *,
    min_eligibility_n: int,
) -> str:
    """Apply the T6 eligibility predicate. Returns one of:

    - ``"pass"`` — card surfaces in Recommended Now.
    - ``"downgrade_sign_agreement"`` — Clause 1 fail.
    - ``"downgrade_joint_fail"`` — Clause 2 fail (band-stash builders only).
    - ``"pass_cold_start"`` — n ``<=`` floor; gate is a no-op for this card.
    """

    obs_n = int(blend_prov.get("observed_n") or 0)
    if obs_n <= int(min_eligibility_n):
        # Cold-start / accumulating-below-floor: gate doesn't fire.
        return "pass_cold_start"

    obs_windows = blend_prov.get("observed_windows") or {}
    if not isinstance(obs_windows, Mapping):
        obs_windows = {}

    # Clause 2 (DS amendment): joint p<0.10 on L28 AND L28_band when band
    # windows are stashed. Checked BEFORE Clause 1 so a band-stash builder
    # whose Welch leg accidentally hits 3-window sign-agreement on a noise
    # leg still demotes when the joint test fails. Per DS verdict
    # 2026-05-23: this is the load-bearing T5 amendment.
    if _has_band_window_stash(obs_windows):
        l28 = obs_windows.get("L28") or {}
        l28_band = obs_windows.get("L28_band") or {}
        l28_p = l28.get("p_value") if isinstance(l28, Mapping) else None
        l28_band_p = (
            l28_band.get("p_value") if isinstance(l28_band, Mapping) else None
        )
        joint_pass = (
            l28_p is not None
            and l28_band_p is not None
            and float(l28_p) < _JOINT_TEST_P_MAX
            and float(l28_band_p) < _JOINT_TEST_P_MAX
        )
        if not joint_pass:
            return "downgrade_joint_fail"

    # Clause 1 (original spec): sign-agreement across windows.
    sac = int(blend_prov.get("observed_sign_agreement_count") or 0)
    if sac < 2:
        return "downgrade_sign_agreement"

    return "pass"


def _ladder_state_for_blend(blend_prov: Mapping[str, Any]) -> str:
    """Return one of ``"cold"`` / ``"accumulating"`` / ``"mature"``.

    Computes ``posterior_ratio = observed_n / (observed_n + pseudo_n)``
    from the stashed values; ``pseudo_n=0`` collapses to cold to defend
    against zero-division.
    """

    obs_n = int(blend_prov.get("observed_n") or 0)
    pseudo_n = int(blend_prov.get("pseudo_n") or 0)
    if obs_n <= 0:
        return "cold"
    denom = obs_n + pseudo_n
    if denom <= 0:
        return "cold"
    ratio = float(obs_n) / float(denom)
    if ratio < 0.2:
        return "cold"
    if ratio < 0.6:
        return "accumulating"
    return "mature"


# S13.6-T1a (Option D): ``_apply_copy_ladder`` deleted per Pivot 2.
# The 3-state ``why_now`` rewriter was the strongest violation of the
# "engine emits typed contract surface; downstream narrates" rule.
# Downstream narration agents recompose any "cohort signal accumulating /
# dominates" framing from the typed ``blend_provenance`` driver
# (pseudo_n + observed_n) on RevenueRange. The DECIDE-layer eligibility
# routing is unchanged (kept-vs-refused split survives); only the prose
# rewrite is gone.


def _route_observed_eligibility_holds(
    recommendations: Iterable[PlayCard],
    *,
    flag_on: bool,
    min_eligibility_n: int,
) -> Tuple[List[PlayCard], List[RejectedPlay]]:
    """Split incoming recs into (kept_with_ladder_applied, refused_demotes).

    Mirrors :func:`_route_prior_unvalidated_holds` (Sprint 7.5 T3
    precedent) so the demote channel stays single. Flag-off path returns
    ``(list(recommendations), [])`` unchanged --- M0 / Beauty /
    Supplements byte-identity preserved.

    Cards without a ``blend_provenance`` driver (legacy / non-prior-anchored
    paths) pass through unchanged.

    Cards whose ``blend_provenance`` carries no ``observed_windows`` stash
    (helper flag OFF, no observed-effect computed yet) also pass through
    unchanged --- the ladder collapses to ``cold`` and the gate is a no-op
    when ``observed_n=0``.
    """

    if not flag_on:
        return list(recommendations or []), []

    kept: List[PlayCard] = []
    refused: List[RejectedPlay] = []
    for card in recommendations or []:
        blend_prov = _blend_provenance_for_card(card)
        if blend_prov is None:
            kept.append(card)
            continue
        verdict = _eligibility_verdict(
            blend_prov, min_eligibility_n=min_eligibility_n
        )
        if verdict in {"downgrade_sign_agreement", "downgrade_joint_fail"}:
            # Single-demote-channel: route through the existing
            # SIGNAL_INCONSISTENT_ACROSS_WINDOWS Considered surface.
            # Both joint-fail and sign-agreement-fail use the same
            # reason code per DS verdict 2026-05-23 ("either acceptable;
            # prefer existing if it semantically fits" — both fall under
            # the umbrella of "cross-window signal is not consistent").
            aud_size, aud_def = _surface_audience_fields_from_card(card)
            # S13.6-T6: typed MechanismIntent atom (None for unmapped play_ids).
            mech = _build_mechanism_intent(card.play_id)
            refused.append(
                RejectedPlay(
                    play_id=str(card.play_id),
                    reason_code=ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS,
                    audience_size=aud_size,
                    audience_definition=aud_def,
                    mechanism=mech,
                    # S7.6-T5.6: preserve Tier-B discriminator across demote
                    # channel so the assembly seam can prepend Tier-B cards
                    # ahead of pre_existing in assemble_considered.
                    would_be_measured_by=getattr(card, "would_be_measured_by", None),
                )
            )
            continue
        # PASS or PASS_COLD_START → keep. S13.6-T1a (Option D): the
        # ``_apply_copy_ladder`` why_now-rewrite step is retired with
        # ``why_now`` itself (Pivot 2).
        kept.append(card)
    return kept, refused


def _decide_abstain_state(
    recommendations: Iterable[PlayCard],
    data_quality_flags: Iterable[DataQualityFlag],
    *,
    pre_existing_state: Optional[DecisionState] = None,
    considered: Iterable[RejectedPlay] = (),
) -> Tuple[DecisionState, Optional[str]]:
    """Decide the EngineRun decision_state per M7 T7.7.

    Returns ``(state, reason)``:

    - ``ABSTAIN_HARD`` — any HARD data-quality flag is set, OR the
      pre-existing state already says ABSTAIN_HARD (M5 anomaly gate
      already cleared recommendations). Reason carries the flag list.
    - ``ABSTAIN_SOFT`` — no measured/directional recommendation
      survived gating. Reason is merchant-readable (Phase 5.1) and
      selected from :data:`ABSTAIN_SOFT_REASONS` based on the dominant
      upstream rejection gate when one exists, otherwise falls back to
      :data:`ABSTAIN_SOFT_DEFAULT_REASON`.
    - ``PUBLISH`` — at least one measured/directional remains.

    The pre-existing state is honored when it already declares
    ABSTAIN_HARD, so M7 cannot accidentally weaken a M5-set hard
    abstain.
    """

    flags = list(data_quality_flags or [])
    recs = list(recommendations or [])

    if pre_existing_state == DecisionState.ABSTAIN_HARD or _has_hard_dq_flag(flags):
        hard = sorted({f.value for f in flags if f in _HARD_DQ_FLAGS})
        reason = (
            "Hard data-quality flag(s) detected: " + ", ".join(hard)
            if hard
            else "Hard data-quality flag detected"
        )
        return DecisionState.ABSTAIN_HARD, reason

    has_measured = any(_is_measured_or_directional(c) for c in recs)
    if not has_measured:
        return (
            DecisionState.ABSTAIN_SOFT,
            _abstain_soft_reason_text(considered),
        )
    return DecisionState.PUBLISH, None


# ---------------------------------------------------------------------------
# Phase 6A Ticket A4 — Recommended Experiment selector
# ---------------------------------------------------------------------------


def _select_recommended_experiments(
    candidates: Iterable[Any],
    *,
    recommendations: Iterable[PlayCard],
    flag_on: bool,
    decision_state: DecisionState,
    vertical: Optional[str],
    metadata_lookup=None,
    aligned: Optional[Mapping[str, Any]] = None,
    publish_shadow: bool = False,
) -> List[PlayCard]:
    """Filter targeting candidates into 0-2 Recommended Experiment cards.

    Eligibility rules (per
    ``agent_outputs/campaign-slate-contract-final.md``):

    1.  ``ENGINE_V2_SLATE`` must be on (``flag_on=True``).
    2.  ``decision_state`` must be PUBLISH; ABSTAIN_SOFT and ABSTAIN_HARD
        return ``[]`` (Fix 3 contract extends here).
    3.  ``play_id`` must be in :data:`RECOMMENDED_EXPERIMENT_ALLOWLIST`.
    4.  ``play_id`` must NOT already appear in ``recommendations`` (the
        role-uniqueness invariant Ticket B4 will pin defensively).
    5.  ``preliminary_rejection_reason`` must NOT be ``"inventory_blocked"``.
    6.  ``priors_loader.get_play_metadata(play_id)`` must return a typed
        :class:`PlayMetadata`; missing metadata rejects the candidate.
    7.  ``mechanism`` must be non-empty (already enforced by the loader).
    8.  ``audience_size >= metadata.audience_floor``.
    9.  Current ``vertical`` must be in
        ``metadata.vertical_applicability``.
    10. Audience overlap (Jaccard) with every ``recommendations`` card
        must be strictly less than
        :data:`RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD` (0.30).
    11. Slate diversity: no two cards may share the same
        ``audience_archetype``. The first eligible candidate (by
        deterministic sort) wins; subsequent same-archetype candidates
        are dropped.
    12. Hard cap at :data:`MAX_RECOMMENDED_EXPERIMENT`.

    Output cards are stamped with:

    - ``evidence_class = TARGETING``
    - ``revenue_range = RevenueRange(suppressed=True, drivers=[...])``
    - ``would_be_measured_by`` copied from
      ``PlayMetadata.would_be_measured_by`` (Ticket A2 enum)
    - ``audience`` populated from the M3 candidate
    - ``opportunity_context`` populated when a defensible store-observed
      AOV is available in ``aligned`` (Phase 6A Ticket B1.5). The math
      and AOV source are identical to the Phase 5.6 directional path:
      :func:`src.measurement_builder._build_opportunity_context` with
      ``primary_window="L28"`` and ``L56``/``L90`` fallback. When
      ``aligned`` is ``None`` / empty / missing AOV, the field is
      omitted (``None``) — never fabricated. The
      ``revenue_range.suppressed=True`` invariant is unchanged; the
      two fields coexist (suppressed range = "we are not projecting
      causal lift"; opportunity_context = audience-sizing context with
      the explicit "not projected lift" disclaimer).

    The function is pure: input candidates are not mutated; a fresh
    list is returned. ``metadata_lookup`` defaults to the live
    :func:`src.priors_loader.get_play_metadata` and is overridable for
    test fault-injection (e.g., to simulate missing metadata or shared
    archetypes between two allowlisted plays).

    ``publish_shadow`` (Phase 6A Ticket B3): when ``True``, bypasses
    rule 2's ABSTAIN short-circuit so the caller can compute the
    would-have-qualified set under PUBLISH semantics. ``decide()``
    uses this to route held experiment candidates into ``considered``
    with :data:`ReasonCode.TARGETING_HELD_UNDER_ABSTAIN` under
    ABSTAIN_SOFT. The flag does NOT bypass rule 1 (``flag_on``); when
    ``ENGINE_V2_SLATE=false`` the selector still returns ``[]``, which
    keeps the new B3 routing a no-op under the kill-switch. Default is
    ``False`` (preserves the Ticket A4 abstain-zero contract).
    """

    if not flag_on:
        return []
    if not publish_shadow and decision_state in (
        DecisionState.ABSTAIN_SOFT,
        DecisionState.ABSTAIN_HARD,
    ):
        return []

    cands = list(candidates or [])
    if not cands:
        return []

    if metadata_lookup is None:
        from .priors_loader import get_play_metadata as metadata_lookup  # type: ignore

    recs = list(recommendations or [])
    rec_play_ids = {str(r.play_id) for r in recs}
    vertical_lc = (str(vertical).strip().lower() if vertical else None) or None

    eligible: List[tuple] = []
    for cand in cands:
        play_id = str(getattr(cand, "play_id", "") or "")
        if not play_id:
            continue
        if play_id not in RECOMMENDED_EXPERIMENT_ALLOWLIST:
            continue
        # Role-uniqueness: do not duplicate a Recommended Now card.
        if play_id in rec_play_ids:
            continue
        # Inventory block.
        prelim = str(getattr(cand, "preliminary_rejection_reason", "") or "").strip().lower()
        if prelim == "inventory_blocked":
            continue
        # Metadata gate.
        try:
            metadata = metadata_lookup(play_id)
        except Exception:
            metadata = None
        if metadata is None:
            continue
        # Mechanism.
        mechanism = getattr(metadata, "mechanism", None)
        if not mechanism or not str(mechanism).strip():
            continue
        # Audience floor.
        try:
            audience_size = int(getattr(cand, "audience_size", 0) or 0)
        except (TypeError, ValueError):
            audience_size = 0
        try:
            floor = int(getattr(metadata, "audience_floor", 0) or 0)
        except (TypeError, ValueError):
            floor = 0
        if audience_size < floor:
            continue
        # Vertical applicability.
        applicable = getattr(metadata, "vertical_applicability", None) or []
        if vertical_lc is not None:
            applicable_lc = {str(v).strip().lower() for v in applicable if v}
            if applicable_lc and vertical_lc not in applicable_lc:
                continue
        # would_be_measured_by must be present (the loader enforces enum-validity).
        wbm = getattr(metadata, "would_be_measured_by", None)
        if wbm is None:
            continue
        # Audience overlap with every Recommended Now card.
        overlap_map = getattr(cand, "audience_overlap", None) or {}
        too_close = False
        for rec in recs:
            try:
                o = float(overlap_map.get(str(rec.play_id), 0.0) or 0.0)
            except (TypeError, ValueError):
                o = 0.0
            if o >= RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD:
                too_close = True
                break
        if too_close:
            continue

        eligible.append((cand, metadata))

    if not eligible:
        return []

    # Deterministic sort: audience_size desc, then play_id asc. The
    # higher-audience candidate wins ties on the slate-diversity rule.
    eligible.sort(
        key=lambda t: (
            -int(getattr(t[0], "audience_size", 0) or 0),
            str(getattr(t[0], "play_id", "") or ""),
        )
    )

    # Slate diversity: dedupe by audience_archetype.
    seen_archetypes: set = set()
    deduped: List[tuple] = []
    for cand, metadata in eligible:
        archetype = getattr(metadata, "audience_archetype", None)
        key = getattr(archetype, "value", archetype)
        if key in seen_archetypes:
            continue
        seen_archetypes.add(key)
        deduped.append((cand, metadata))

    # Hard cap.
    deduped = deduped[:MAX_RECOMMENDED_EXPERIMENT]

    # Phase 6A Ticket B1.5: lazy-import the Phase 5.1 opportunity-context
    # builder so the same code path that stamps Recommended Now /
    # directional cards also stamps Recommended Experiment cards. Lazy
    # import avoids any circular dependency between decide and
    # measurement_builder.
    from .measurement_builder import _build_opportunity_context

    # Build PlayCards.
    cards: List[PlayCard] = []
    for cand, metadata in deduped:
        audience_size = int(getattr(cand, "audience_size", 0) or 0)
        audience = Audience(
            size=audience_size,
            definition=str(getattr(cand, "segment_definition", "") or "") or None,
        )
        # S13.6-T7a: paired ``suppression_reason`` wraps the existing
        # producer string ``"experiment_no_calibrated_lift"`` at the
        # seam per DS Q1 (no producer rewrite). Recommended Experiment
        # cards are TARGETING with suppressed revenue_range by design
        # (Phase 6A A4 contract).
        from .engine_run import RevenueRangeSuppressionReason as _RRSR_EXP
        revenue_range = RevenueRange(
            suppressed=True,
            drivers=[{"reason": "experiment_no_calibrated_lift"}],
            suppression_reason=_RRSR_EXP.EXPERIMENT_NO_CALIBRATED_LIFT,
        )
        # Phase 6A Ticket B1.5: populate opportunity_context using the
        # same Phase 5.1 helper the directional builder uses. Returns
        # ``None`` when ``aligned`` is missing or no defensible AOV is
        # available — the renderer's ``_render_opportunity_context_block``
        # self-hides on ``None``, so the card simply omits the
        # addressable-value sentence rather than fabricating it.
        opp_ctx = _build_opportunity_context(
            audience_size,
            aligned if isinstance(aligned, Mapping) else None,
            primary_window="L28",
        )
        play_id_str = str(getattr(cand, "play_id", "") or "")
        cards.append(
            PlayCard(
                play_id=play_id_str,
                evidence_class=EvidenceClass.TARGETING,
                audience=audience,
                measurement=None,
                revenue_range=revenue_range,
                opportunity_context=opp_ctx,
                would_be_measured_by=metadata.would_be_measured_by,
                # S13.6-T6: typed MechanismIntent atom. Returns None for
                # unmapped play_ids (strict — do not invent).
                mechanism_intent=_build_mechanism_intent(play_id_str),
            )
        )
    return cards


# ---------------------------------------------------------------------------
# Phase 6A Ticket B4: Role-uniqueness invariant assertion.
#
# A single EngineRun MUST NOT carry the same ``play_id`` in more than one
# role section. The forcing function for this rule is the trust contract
# in ``agent_outputs/campaign-slate-contract-final.md``: a merchant cannot
# see the same play surfaced under two competing framings (e.g., as both
# a measured / directional Recommended Now card and a send-and-measure
# Recommended Experiment card) in a single briefing.
#
# Scope (broader enforcement, per Ticket B4 implementation guidance):
#   - ``recommendations``           x ``recommended_experiments``  -> required
#   - ``recommendations``           x ``considered``               -> safe today
#   - ``recommended_experiments``   x ``considered``               -> safe today
#
# Why broader enforcement is safe today:
#   - PUBLISH path: ``assemble_considered(..., recommended_play_ids=...)``
#     already excludes ``recommendations`` play_ids from ``considered``;
#     ``populate_considered_from_candidates`` (called upstream) skips
#     play_ids already in ``recommendations`` or ``considered``; and the
#     experiment selector excludes any play_id already in
#     ``recommendations``. The experiment selector does not currently
#     emit play_ids that overlap with upstream ``considered`` because the
#     allowlist is small and the M3 candidate either gets stamped by the
#     upstream pipeline OR survives to the experiment role, never both.
#   - ABSTAIN_SOFT path (Ticket B3): the experiment-side held-card
#     routing dedupes against pre-existing ``considered`` AND the regular
#     Fix 3 head-routing list; ``recommended_experiments`` is forced to
#     ``[]``; ``recommendations`` is forced to ``[]``.
#   - ABSTAIN_HARD path: ``recommendations`` and ``recommended_experiments``
#     are both forced to ``[]``.
#
# The assertion is a defensive net. If a future code path violates the
# invariant, the engine will fail loudly at the end of ``decide()``
# rather than silently mis-render a briefing.
# ---------------------------------------------------------------------------


def _assert_role_uniqueness(engine_run: EngineRun) -> None:
    """Raise ``AssertionError`` if any ``play_id`` appears in more than one
    visible role section of ``engine_run``.

    Visible role sections checked:

    - ``recommendations`` (Recommended Now)
    - ``recommended_experiments`` (Recommended Experiment)
    - ``considered`` (Held / Considered)

    Watching is intentionally NOT checked: it is a metric track keyed on
    metric name, not a play track keyed on ``play_id``.

    The error message lists every duplicate ``play_id`` and the exact
    pair of role-section names that contain it. This is intended to be
    actionable for the engineer who triggers it: the duplicate is
    structurally illegal and points at a regression in either
    ``rank_recommendations``, the experiment selector, the
    ABSTAIN_SOFT B3 routing, or ``assemble_considered``.

    Args:
        engine_run: the post-decide EngineRun to audit.

    Raises:
        AssertionError: if any ``play_id`` appears in more than one of
            the three visible role sections.
    """

    rec_ids: List[str] = [
        str(c.play_id) for c in (engine_run.recommendations or []) if c is not None
    ]
    exp_ids: List[str] = [
        str(c.play_id)
        for c in (engine_run.recommended_experiments or [])
        if c is not None
    ]
    con_ids: List[str] = [
        str(r.play_id) for r in (engine_run.considered or []) if r is not None
    ]

    rec_set = set(rec_ids)
    exp_set = set(exp_ids)
    con_set = set(con_ids)

    rec_x_exp = sorted(rec_set & exp_set)
    rec_x_con = sorted(rec_set & con_set)
    exp_x_con = sorted(exp_set & con_set)

    if not (rec_x_exp or rec_x_con or exp_x_con):
        return

    parts: List[str] = []
    if rec_x_exp:
        parts.append(
            f"recommendations vs recommended_experiments: {rec_x_exp!r}"
        )
    if rec_x_con:
        parts.append(f"recommendations vs considered: {rec_x_con!r}")
    if exp_x_con:
        parts.append(f"recommended_experiments vs considered: {exp_x_con!r}")

    raise AssertionError(
        "Role-uniqueness invariant violated (Phase 6A Ticket B4): the "
        "same play_id MUST NOT appear in more than one visible role "
        "section of an EngineRun. Offending overlaps: "
        + "; ".join(parts)
        + "."
    )


# ---------------------------------------------------------------------------
# decide() — the M7 entry point
# ---------------------------------------------------------------------------


def decide(
    engine_run: EngineRun,
    *,
    cfg: Optional[Mapping] = None,
    candidates: Optional[Iterable[Any]] = None,
    aligned: Optional[Mapping[str, Any]] = None,
) -> EngineRun:
    """Apply the M7 decision selector to an EngineRun.

    Pipeline:

    1. Rank recommendations using class-first priority + p50 + audience.
    2. Apply the top-3 cap; demote the rest into ``considered`` with
       ``CAP_EXCEEDED``.
    3. Decide the abstain state:
       - ABSTAIN_HARD ⇒ recommendations = [], state = ABSTAIN_HARD.
       - ABSTAIN_SOFT ⇒ recommendations = []. Held targeting cards
         that decide() ranked into the head are re-routed into
         ``considered`` with
         ``ReasonCode.TARGETING_HELD_UNDER_ABSTAIN`` so the merchant
         can still see them in the Considered section with a typed
         reason and ``would_fire_if`` template (Synthetic Blocker
         Fix 3 — PM-resolved contract: zero Recommended cards under
         ABSTAIN_SOFT).
       - PUBLISH otherwise.
    4. Assemble the considered list (de-duplicated against
       recommendations, capped at 6).
    5. Build the Watching section deterministically from the existing
       state-of-store observations.

    Returns:
        A new ``EngineRun`` with the decision-layer fields populated.
        Inputs are not mutated.

    The function is total: it never raises. Defensive defaults preserve
    the existing values on input ambiguity. ``cfg`` is accepted for
    forward compatibility (e.g., M8 may toggle abstain-soft cap behavior
    via cfg) and is otherwise unused in M7.

    Args:
        engine_run: input EngineRun (typically the M5/M6 output).
        cfg: optional config Mapping; reads ``ENGINE_V2_SLATE``,
            ``VERTICAL_MODE``, and ``VERTICAL`` (Ticket A4).
        candidates: optional iterable of M3 :class:`Candidate` objects;
            consumed only by the Recommended Experiment selector
            (Tickets A4 / A4.5).
        aligned: optional aligned KPI snapshot (the
            ``utils.kpi_snapshot_with_deltas`` dict). Consumed only by
            the Recommended Experiment selector (Phase 6A Ticket B1.5)
            to populate the Phase 5.1 ``opportunity_context`` block on
            experiment cards. ``None`` is the safe default; the selector
            simply omits ``opportunity_context`` rather than fabricating
            an addressable value.
    """

    # 1) Rank. Phase 5.7: defensively drop demoted plays before ranking
    # so they cannot surface as primary recommendations on the V2 path.
    incoming = [
        c for c in (engine_run.recommendations or [])
        if str(c.play_id) not in PHASE5_V2_SUPPRESS_PLAY_IDS
    ]
    # Sprint 7.5 Ticket T3: route plays whose base_rate prior was refused
    # under the validation rule to Considered with PRIOR_UNVALIDATED
    # before ranking. Flag-off path is a no-op (kept = incoming, refused
    # = []) so M0 / Beauty / supplements byte-identity is preserved.
    cfg_pv_flag = bool((cfg or {}).get("ENGINE_V2_PRIORS_VALIDATION", False))
    # Sprint 7 Ticket T4: 4-state ABSTAIN_SOFT mode-picker. Default OFF;
    # T4.5 atomically flips with a pinned-fixture re-pin. Under flag-OFF
    # ``_compute_abstain_mode`` preserves the legacy Sprint 7.5 T3
    # 2-state mapping so all 5 pinned fixtures stay byte-identical.
    cfg_four_state_flag = bool(
        (cfg or {}).get("ENGINE_V2_ABSTAIN_4STATE", False)
    )
    incoming, prior_unvalidated_rejects = _route_prior_unvalidated_holds(
        incoming, flag_on=cfg_pv_flag
    )

    # Sprint 6.5 Ticket T4 (R1): route CONTRADICTED window_corroboration
    # cards to Considered with WINDOW_DISAGREEMENT; bump CORROBORATED
    # cards' confidence_label one notch within their tier ceiling. Both
    # behaviors gate on ``ENGINE_V2_STORE_PROFILE``; flag-OFF is a no-op
    # so the pinned fixtures stay byte-identical.
    cfg_profile_flag = bool((cfg or {}).get("ENGINE_V2_STORE_PROFILE", False))
    incoming, window_disagreement_rejects = _route_window_disagreement_holds(
        incoming, flag_on=cfg_profile_flag
    )
    incoming = _apply_window_corroboration_bumps(incoming, flag_on=cfg_profile_flag)

    # Sprint 7.6 Ticket T6: observed-effect eligibility gate + 3-state
    # copy ladder. Flag-OFF path is a no-op (kept = incoming, refused = [])
    # so M0 / Beauty / Supplements byte-identity is preserved. Runs AFTER
    # the prior-unvalidated and window-disagreement routes so the demote
    # channel stays single (per ARCHITECTURE_PLAN.md 2026-05-22). The DS
    # architect verdict 2026-05-23 amends Clause 1 with the joint-p<0.10
    # check (Clause 2) for builders that stash ``*_band`` windows ---
    # currently only ``aov_lift_via_threshold_bundle``.
    cfg_elig_flag = bool(
        (cfg or {}).get("ENGINE_V2_OBSERVED_ELIGIBILITY_GATE", False)
    )
    cfg_min_elig_n = int(
        (cfg or {}).get("OBSERVED_MIN_ELIGIBILITY_N", 30) or 30
    )
    incoming, eligibility_rejects = _route_observed_eligibility_holds(
        incoming,
        flag_on=cfg_elig_flag,
        min_eligibility_n=cfg_min_elig_n,
    )

    ranked = rank_recommendations(incoming)

    # 2) Cap at 3.
    head = ranked[:MAX_RECOMMENDATIONS]
    tail = ranked[MAX_RECOMMENDATIONS:]

    # 3) Decide state. Pass upstream considered list so the abstain-soft
    # reason text can be selected based on the dominant gate (Phase 5.1).
    pre_state = engine_run.abstain.state if engine_run.abstain else None
    # S13.6-T1a (Option D): ``Abstain.reason`` stripped per Pivot 2. The
    # B-1 pre-existing-reason preservation seam below is retired with it
    # — downstream narration composes anomalous-window framing from
    # data_quality_flags + decision_state.
    state, reason = _decide_abstain_state(
        head,
        engine_run.data_quality_flags or [],
        pre_existing_state=pre_state,
        considered=engine_run.considered or [],
    )

    # Phase 6A Ticket A4: Recommended Experiment selector. Default OFF;
    # when ``ENGINE_V2_SLATE`` is true and the run publishes, the
    # selector emits at most 2 PlayCards into
    # ``recommended_experiments``. Both abstain branches force the list
    # to ``[]``. The selector itself enforces the abstain contract too,
    # so this is belt-and-suspenders.
    cfg_map = dict(cfg or {})
    flag_on = bool(cfg_map.get("ENGINE_V2_SLATE", False))
    vertical = cfg_map.get("VERTICAL_MODE") or cfg_map.get("VERTICAL")
    if not vertical and engine_run.briefing_meta is not None:
        vertical = engine_run.briefing_meta.vertical

    if state == DecisionState.ABSTAIN_HARD:
        # Drop all recommendations. Move the (originally ranked) head
        # into considered with ANOMALOUS_WINDOW reasons preserved if the
        # M5 anomaly gate already populated that. If the upstream
        # considered list is empty (anomaly gate was off but a HARD flag
        # exists in receipts), we synthesize a DATA_QUALITY_FLAG entry
        # per recommendation so reviewers can see the demotion.
        # S7.6-T5.6: partition Tier-B subset of the three sibling demote
        # channels into priority_prepend_rejects so ABSTAIN_HARD's
        # assembly truncation cannot silently drop them either. Tier-B
        # cards demoted by the eligibility gate / prior_unvalidated /
        # window_disagreement routes remain visible to the merchant even
        # under a HARD data-quality flag.
        _all_channel_rejects_abst_hard = (
            list(prior_unvalidated_rejects)
            + list(window_disagreement_rejects)
            + list(eligibility_rejects)
        )
        priority_prepend_rejects_abst_hard = [
            rj for rj in _all_channel_rejects_abst_hard
            if getattr(rj, "would_be_measured_by", None) is not None
        ]
        non_priority_channel_rejects_abst_hard = [
            rj for rj in _all_channel_rejects_abst_hard
            if getattr(rj, "would_be_measured_by", None) is None
        ]
        considered_in = (
            list(engine_run.considered or [])
            + non_priority_channel_rejects_abst_hard
        )
        if not considered_in:
            for card in head:
                considered_in.append(
                    RejectedPlay(
                        play_id=card.play_id,
                        reason_code=ReasonCode.DATA_QUALITY_FLAG,
                    )
                )
        considered = assemble_considered(
            considered_in,
            cap_exceeded=tail,
            no_measured=(),
            recommended_play_ids=[],
            priority_prepend_rejects=priority_prepend_rejects_abst_hard,
            engine_run=engine_run,
        )
        new_abstain = Abstain(
            state=DecisionState.ABSTAIN_HARD,
            mode=_compute_abstain_mode(
                DecisionState.ABSTAIN_HARD,
                considered,
                flag_on=cfg_pv_flag,
                four_state_flag_on=cfg_four_state_flag,
            ),
        )
        watching = build_watching(engine_run.state_of_store or [])
        out = replace(
            engine_run,
            recommendations=[],
            recommended_experiments=[],
            considered=considered,
            abstain=new_abstain,
            watching=watching,
        )
        # Phase 6A Ticket B4: defensive role-uniqueness invariant.
        _assert_role_uniqueness(out)
        return out

    # PUBLISH or ABSTAIN_SOFT path.
    if state == DecisionState.ABSTAIN_SOFT:
        # Synthetic Blocker Fix 3 (PM-resolved contract):
        # ``decision_state == abstain_soft`` MUST produce zero Recommended
        # cards. Re-route the ranked head into ``considered`` with the
        # typed ``TARGETING_HELD_UNDER_ABSTAIN`` reason so the merchant
        # sees the held plays in the Considered section, not the
        # Recommended one. The renderer (M8) is responsible for hiding
        # the empty Recommended section behind the Phase 5.1 callout.
        held_rejections: List[RejectedPlay] = []
        for card in head:
            held_rejections.append(
                RejectedPlay(
                    play_id=card.play_id,
                    reason_code=ReasonCode.TARGETING_HELD_UNDER_ABSTAIN,
                )
            )

        # Phase 6A Ticket B3: Recommended Experiment ABSTAIN_SOFT routing.
        # Compute the experiment-eligible candidate set under PUBLISH
        # semantics (publish_shadow=True bypasses rule 2's abstain
        # short-circuit). When ``ENGINE_V2_SLATE=false`` the selector
        # still returns ``[]`` because rule 1 (flag_on) is preserved, so
        # this routing is a no-op under the kill-switch. The
        # ``recommended_experiments`` field on the returned EngineRun
        # remains ``[]`` (the abstain-zero contract from Ticket A4 is
        # unchanged); the would-have-qualified cards are routed to
        # ``considered`` with the same typed reason as the regular Fix 3
        # head routing. Dedupe against ``held_rejections`` (regular Fix 3
        # path) and against any pre-existing ``engine_run.considered``
        # entries so the same play_id never appears twice.
        existing_considered_ids = {
            str(r.play_id) for r in (engine_run.considered or [])
        }
        held_play_ids = {str(r.play_id) for r in held_rejections}
        already_routed = existing_considered_ids | held_play_ids
        experiment_shadow = _select_recommended_experiments(
            candidates,
            recommendations=head,
            flag_on=flag_on,
            decision_state=state,
            vertical=str(vertical) if vertical else None,
            aligned=aligned,
            publish_shadow=True,
        )
        for shadow_card in experiment_shadow:
            pid = str(shadow_card.play_id)
            if pid in already_routed:
                # Skip dedupe: a regular Fix 3 routing entry, an upstream
                # guardrail rejection, or an M3 prelim rejection already
                # surfaces this play in considered.
                continue
            already_routed.add(pid)
            held_rejections.append(
                RejectedPlay(
                    play_id=pid,
                    reason_code=ReasonCode.TARGETING_HELD_UNDER_ABSTAIN,
                )
            )

        # Order: existing considered (incl. M3 candidates) first, then
        # newly-held targeting cards (regular Fix 3 + B3 experiment-side),
        # then the cap-exceeded tail. The dedupe step keeps the first
        # entry per play_id, so an upstream rejection for the same
        # play_id wins over the new typed entry.
        # S7.6-T5.6: partition the three sibling demote channels here too
        # so Tier-B cards survive the ABSTAIN_SOFT truncation. ``tail`` is
        # not partitioned in the ABSTAIN_SOFT path (no head was published)
        # — it flows wholesale through cap_exceeded as before.
        _all_channel_rejects_abst_soft = (
            list(prior_unvalidated_rejects)
            + list(window_disagreement_rejects)
            + list(eligibility_rejects)
        )
        priority_prepend_rejects_abst_soft = [
            rj for rj in _all_channel_rejects_abst_soft
            if getattr(rj, "would_be_measured_by", None) is not None
        ]
        non_priority_channel_rejects_abst_soft = [
            rj for rj in _all_channel_rejects_abst_soft
            if getattr(rj, "would_be_measured_by", None) is None
        ]
        considered_in = (
            list(engine_run.considered or [])
            + non_priority_channel_rejects_abst_soft
            + held_rejections
        )
        considered = assemble_considered(
            considered_in,
            cap_exceeded=tail,
            no_measured=(),
            recommended_play_ids=[],
            priority_prepend_rejects=priority_prepend_rejects_abst_soft,
            engine_run=engine_run,
        )
        new_abstain = Abstain(
            state=state,
            mode=_compute_abstain_mode(
            state,
            considered,
            flag_on=cfg_pv_flag,
            four_state_flag_on=cfg_four_state_flag,
        ),
        )
        watching = build_watching(engine_run.state_of_store or [])
        out = replace(
            engine_run,
            recommendations=[],
            recommended_experiments=[],
            considered=considered,
            abstain=new_abstain,
            watching=watching,
        )
        # Phase 6A Ticket B4: defensive role-uniqueness invariant.
        _assert_role_uniqueness(out)
        return out

    # PUBLISH path.
    rec_play_ids = [str(c.play_id) for c in head]
    # S7.6-C1: split the cap-exceeded tail into a priority-prepend subset
    # (Tier-B prior-anchored cards identified by ``would_be_measured_by
    # is not None``) and a non-priority remainder. The prepend subset is
    # emitted BEFORE pre_existing inside ``assemble_considered`` so the
    # ``[:MAX_CONSIDERED_RENDERED]`` cap can no longer silently drop the
    # load-bearing S6/S7 survivability set
    # (winback_dormant_cohort, replenishment_due,
    # discount_dependency_hygiene, cohort_journey_first_to_second,
    # aov_lift_via_threshold_bundle). DS-locked per
    # ARCHITECTURE_PLAN.md 2026-05-22 single-demote-channel invariant.
    priority_prepend = [
        c for c in tail if getattr(c, "would_be_measured_by", None) is not None
    ]
    non_priority_tail = [
        c for c in tail if getattr(c, "would_be_measured_by", None) is None
    ]
    # S7.6-T5.6 (DS verdict 2026-05-23): the three sibling demote channels
    # (eligibility_gate, prior_unvalidated, window_disagreement) also
    # carry Tier-B cards. Partition each by ``would_be_measured_by is not
    # None`` and route the Tier-B subset into priority_prepend_rejects so
    # the assembly cap cannot silently drop them. Non-Tier-B subset
    # continues to the pre_existing slot as today.
    _all_channel_rejects = (
        list(prior_unvalidated_rejects)
        + list(window_disagreement_rejects)
        + list(eligibility_rejects)
    )
    priority_prepend_rejects = [
        rj for rj in _all_channel_rejects
        if getattr(rj, "would_be_measured_by", None) is not None
    ]
    non_priority_channel_rejects = [
        rj for rj in _all_channel_rejects
        if getattr(rj, "would_be_measured_by", None) is None
    ]
    considered = assemble_considered(
        list(engine_run.considered or []) + non_priority_channel_rejects,
        cap_exceeded=non_priority_tail,
        no_measured=(),
        recommended_play_ids=rec_play_ids,
        priority_prepend=priority_prepend,
        priority_prepend_rejects=priority_prepend_rejects,
        engine_run=engine_run,
    )
    new_abstain = Abstain(
        state=state,
        mode=_compute_abstain_mode(
            state,
            considered,
            flag_on=cfg_pv_flag,
            four_state_flag_on=cfg_four_state_flag,
        ),
    )
    watching = build_watching(engine_run.state_of_store or [])

    recommended_experiments = _select_recommended_experiments(
        candidates,
        recommendations=head,
        flag_on=flag_on,
        decision_state=state,
        vertical=str(vertical) if vertical else None,
        aligned=aligned,
    )

    # Phase 6A Ticket B6: enforce role-uniqueness across PUBLISH branch.
    # ``assemble_considered`` already excluded play_ids that survived to
    # ``recommendations`` (the head). Now that the experiment selector has
    # also resolved the Recommended Experiment slate, drop any considered
    # entry whose play_id was promoted to ``recommended_experiments`` so a
    # single play_id never appears in both visible role sections.
    # Without this filter, an upstream ``no_measured_signal`` /
    # ``audience_too_small`` rejection on an experiment-allowlisted play
    # (e.g. ``discount_hygiene``, ``bestseller_amplify``) would persist in
    # ``considered`` after the slate selector promotes it, tripping the
    # B4 ``_assert_role_uniqueness`` invariant on real Beauty-Brand-shaped
    # runs. This is the smallest deterministic decide-layer fix.
    if recommended_experiments:
        experiment_play_ids = {
            str(c.play_id) for c in recommended_experiments
        }
        considered = [
            r for r in considered
            if str(r.play_id) not in experiment_play_ids
        ]

    out = replace(
        engine_run,
        recommendations=head,
        recommended_experiments=recommended_experiments,
        considered=considered,
        abstain=new_abstain,
        watching=watching,
    )
    # Phase 6A Ticket B4: defensive role-uniqueness invariant. The
    # PUBLISH path is the only branch that can populate all three role
    # sections, so this is the most likely site for a future regression.
    _assert_role_uniqueness(out)
    return out


__all__ = [
    "ABSTAIN_SOFT_DEFAULT_REASON",
    "ABSTAIN_SOFT_REASONS",
    "MAX_CONSIDERED_RENDERED",
    "MAX_RECOMMENDATIONS",
    "MAX_RECOMMENDED_EXPERIMENT",
    "MAX_WATCHING_SIGNALS",
    "PHASE5_V2_SUPPRESS_PLAY_IDS",
    "RECOMMENDED_EXPERIMENT_ALLOWLIST",
    "RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD",
    "assemble_considered",
    "build_watching",
    "decide",
    "populate_considered_from_candidates",
    "rank_recommendations",
]
