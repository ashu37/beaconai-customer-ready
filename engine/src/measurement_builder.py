"""Phase 5.6 — Measured/Directional PlayCard builder.

This module wires one carefully-scoped pathway from M3 candidate
detection + the existing aligned KPI snapshot into a typed
:class:`~src.engine_run.PlayCard` with ``evidence_class`` of
``DIRECTIONAL`` (Phase 5.6 conservative default).

What this module is NOT:

- It is NOT a generic measurement engine.
- It does NOT introduce fabricated p-values, CIs, observed effects,
  or saturated confidence claims.
- It does NOT call :func:`src.sizing.size_play` with a non-intervention
  signal as ``observed_effect``. The current supporting signal
  (``returning_customer_share``) is a *state* statistic, not an
  intervention effect, so using it as ``p_action`` would be a sizing
  fabrication. Phase 5.6 explicitly suppresses revenue ranges on the
  built card and surfaces a "Why no $ projection" context block.
- It does NOT lower the materiality floor.
- It does NOT bypass M5 guardrails or the M7 abstain state machine.
- It does NOT label any expert prior as ``causal``.

What it does (Phase 5.6 contract):

- Identify ONE candidate worth surfacing as DIRECTIONAL today:
  ``first_to_second_purchase`` (preferred replacement for
  journey_optimization per memory.md).
- Read the existing aligned KPI snapshot for ``returning_customer_share``
  on L28 (and verify sign-stability across L56 and L90).
- Build a typed :class:`~src.engine_run.Measurement` carrying the
  metric name, observed delta, n, primary window, sign-stability
  count, and the L28 p-value as ``p_internal`` (NEVER rendered to
  the merchant).
- Build a typed :class:`~src.engine_run.PlayCard` with
  ``evidence_class=DIRECTIONAL`` and a *suppressed*
  :class:`~src.engine_run.RevenueRange` whose ``drivers`` list names
  the suppression reason.

The DS Architect's QA Change 4 still applies: the card must not show
a $ headline. Per the M8 renderer, directional cards may show a range
chip when ``revenue_range.suppressed=False``; here we keep them
suppressed because we do not have a calibrated lift estimate.

Hard guards:

- The pathway only fires when the supporting signal has L28 p < 0.05.
- The pathway only fires when ``consistency_across_windows >= 2`` is
  observed (sign agreement across L28 / L56 / L90 deltas).
- The pathway only fires when the audience has cleared the M3 builder's
  minimum-N threshold (``preliminary_rejection_reason is None``).
- The pathway only fires when the candidate is NOT already in the
  legacy-emitted ``recommendations`` list (no double-emission).
- All inputs are optional / defensively read; on any failure, the
  function returns ``None`` and the engine falls through to its
  prior ABSTAIN_SOFT behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import numpy as np
import pandas as pd

from .engine_run import (
    Audience,
    DescriptiveDistribution,
    DistributionKind,
    EvidenceClass,
    EvidenceSourceChip,
    Measurement,
    NonLiftAtom,
    OpportunityContext,
    PlayCard,
    Provenance,
    RevenueRange,
    RevenueRangeSource,
    Sensitivity,
    WindowCorroboration,
    WouldBeMeasuredBy,
    build_descriptive_distribution,
)
from .measurement_observed import (
    MultiWindowAgreement,
    ObservedEffectResult,
    compute_multi_window_sign_agreement,
    compute_two_proportion_observed,
    compute_welch_t_observed,
)


# ---------------------------------------------------------------------------
# S-FE-descriptive-distribution (L-EV-19 / L-EV-20) — fixed per-kind bin
# edges + the producer seam that binds the discarded builder series onto the
# typed Audience.descriptive_distribution atom.
#
# Binning convention (chosen, fixed, documented): each kind has fixed edges
# so a chart is comparable across runs / stores. ``build_descriptive_distribution``
# counts ``[edges[i], edges[i+1])`` with the final bin closed on the right and
# clamps out-of-range observations into the edge bins (no observation
# dropped). ``len(counts) == len(bins) - 1``. DESCRIPTIVE-ONLY: observed
# counts only — no rate, no dollar, no lift (L-EV-20).
# ---------------------------------------------------------------------------

#: Fixed bin edges keyed by DistributionKind value.
_DESCRIPTIVE_BIN_EDGES: Dict[str, List[float]] = {
    # Dormancy days-since-last-order. Covers the union of the Beauty
    # (21-45d) and supplements (60-120d) windows plus tails to 180d.
    "DORMANCY_DAYS": [0.0, 21.0, 30.0, 45.0, 60.0, 90.0, 120.0, 180.0],
    # Reorder-gap days (per-customer days since last in-class purchase).
    "REORDER_GAP_DAYS": [0.0, 15.0, 30.0, 45.0, 60.0, 90.0, 120.0, 180.0],
    # Per-customer typical AOV (the band the bundle threshold sits above).
    "AOV_GAP": [0.0, 25.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0, 500.0],
    # Per-customer discount fraction. Eligible cohort is >=0.5 by
    # construction; the full [0,1] edge set keeps the chart honest about
    # the floor.
    "DISCOUNT_FRACTION": [0.0, 0.25, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
}


def _maybe_build_descriptive_distribution(
    candidate: Any,
) -> Optional[DescriptiveDistribution]:
    """Bind the discarded builder series (stashed on ``AudienceResult``) into
    the typed :class:`DescriptiveDistribution` atom for the 4 distributional
    plays.

    Returns ``None`` when the builder did not stash a kind (every
    non-distributional play) so the outer ``Audience.descriptive_distribution``
    stays ``None`` (structural "not a distributional play"). When a kind IS
    stashed, the atom is ALWAYS built — an empty / absent series yields a
    typed ``suppressed=True`` atom (L-EV-20), never a silent omission.
    """
    raw_kind = getattr(candidate, "descriptive_kind", None)
    if raw_kind is None:
        return None
    try:
        kind = DistributionKind(str(raw_kind))
    except (ValueError, TypeError):
        return None
    series = getattr(candidate, "descriptive_series", None)
    marker = getattr(candidate, "descriptive_marker", None)
    bin_edges = _DESCRIPTIVE_BIN_EDGES.get(kind.value)
    return build_descriptive_distribution(
        kind, series, marker=marker, bin_edges=bin_edges
    )


# ---------------------------------------------------------------------------
# Configuration knobs
# ---------------------------------------------------------------------------


#: Significance threshold for the supporting metric on the primary window.
PHASE5_DIRECTIONAL_P_MAX: float = 0.05

#: Required sign-agreement count across windows. Phase 5.6 default 2 to
#: keep the bar conservative; L28+L56 sign agreement is the minimum.
PHASE5_DIRECTIONAL_MIN_CONSISTENCY: int = 2

#: Windows scanned for sign agreement (in priority order).
PHASE5_WINDOWS: tuple[str, ...] = ("L28", "L56", "L90")


# ---------------------------------------------------------------------------
# Phase 5.6 supported play -> supporting metric map.
#
# Kept tiny and explicit: only ``first_to_second_purchase`` is wired
# today. New entries require: (a) a registered audience builder, (b) a
# defensible supporting signal in ``aligned``, (c) a documented reason
# the supporting signal is at least *directional* of the play's effect.
# ---------------------------------------------------------------------------


# S13.6-T1a (Option D, founder + DS approved 2026-05-30): the engine-
# authored ``recommendation_text`` and ``why_now_template`` slots are
# stripped per Pivot 2. Downstream narration agents compose merchant copy
# from the typed contract surface (play_id, metric, audience, rationale).
@dataclass(frozen=True)
class _SupportingSignal:
    play_id: str
    metric: str
    rationale: str  # short docstring for the receipts


_SUPPORTED: Dict[str, _SupportingSignal] = {
    "first_to_second_purchase": _SupportingSignal(
        play_id="first_to_second_purchase",
        metric="returning_customer_share",
        rationale=(
            "returning_customer_share is the per-window fraction of "
            "customers with prior order history. It is a directional "
            "indicator of retention health, not a measured first-to-second "
            "conversion lift. Phase 5.6 surfaces this as a directional "
            "card with suppressed revenue range."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _safe_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _resolve_aov_for_context(
    aligned: Optional[Dict[str, Any]],
    *,
    primary_window: str = "L28",
) -> Optional[tuple[float, str]]:
    """Resolve a defensible store-observed AOV for the opportunity context block.

    Phase 5.1 follow-up: prefer the primary window's AOV (consistent with
    every other V2 surface that already reads ``aligned[primary_window].aov``).
    Fall back to ``L56`` if the primary window is unusable, then ``L90``.
    Return ``None`` when no defensible AOV is available — never fabricate.

    Returns:
        ``(aov, window_label)`` if a positive AOV is available, else ``None``.
    """

    if not aligned:
        return None
    fallback_chain = [primary_window, "L56", "L90"]
    seen: set[str] = set()
    for window in fallback_chain:
        if window in seen:
            continue
        seen.add(window)
        bucket = aligned.get(window) or {}
        aov_raw = bucket.get("aov") if isinstance(bucket, dict) else None
        aov = _safe_float(aov_raw)
        if aov is not None and aov > 0:
            return aov, window
    return None


def _build_opportunity_context(
    audience_size: int,
    aligned: Optional[Dict[str, Any]],
    *,
    primary_window: str = "L28",
) -> Optional[OpportunityContext]:
    """Phase 5.1 follow-up: build an OpportunityContext when both audience
    size and a defensible recent AOV are available. Returns ``None``
    otherwise — never fabricates.

    The addressable value is the simple multiplicative ``audience_size *
    aov`` so the renderer can present it explicitly as "the size of the
    audience if the play converts" — not as a forecast.
    """

    if audience_size <= 0:
        return None
    resolved = _resolve_aov_for_context(aligned, primary_window=primary_window)
    if resolved is None:
        return None
    aov, window_label = resolved
    addressable_value = float(audience_size) * float(aov)
    # S13.6-T3 (DS R1, founder approved 2026-05-30): the four addressable-
    # opportunity numerics now live in the typed ``NonLiftAtom`` wrapper.
    # ``value`` == ``monthly_revenue_estimate`` by construction
    # (``audience_size * aov_used``); ``semantic`` is the closed-set
    # Literal that names the constraint at the type system.
    non_lift = NonLiftAtom(
        value=float(addressable_value),
        semantic="addressable_opportunity",
        aov_used=float(aov),
        monthly_revenue_estimate=float(addressable_value),
    )
    return OpportunityContext(
        audience_size=int(audience_size),
        non_lift=non_lift,
        aov_window=window_label,
        aov_source="store_observed",
    )


def _audience_size_driver(
    audience_size: int, profile_field_ref: Optional[str] = None
) -> Dict[str, Any]:
    """Build the standard ``audience_size`` driver dict.

    Sprint 6.5 Ticket T4: when the audience-floor came from
    ``profile.gate_calibration``, cite the YAML cell-path on the
    driver so reviewers can trace the floor back to
    ``gate_calibration.yaml``. ``profile_field_ref`` is omitted (the
    key is absent) when None so the legacy / flag-OFF dict shape is
    byte-identical to today's prior-anchored output.
    """

    d: Dict[str, Any] = {
        "name": "audience_size",
        "source": "store_observed",
        "value": int(audience_size),
    }
    if profile_field_ref:
        d["profile_field_ref"] = str(profile_field_ref)
    return d


def _audience_floor_sensitivity_driver(
    audience_size: int,
    audience_floor: int,
    posterior_value: float,
    aov: float,
    *,
    profile_field_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """Sprint 6 Ticket T3.y — audience-floor sensitivity driver.

    Closes the DS architect 2026-05-19 "firewall leak": on validated-path
    PlayCards, the heuristic uncertainty of the audience-floor cell in
    ``gate_calibration.yaml`` silently inherits into the dollar
    projection. The :func:`_audience_size_driver` cites the floor's
    ``profile_field_ref`` but the ``revenue_range`` carries no
    sensitivity envelope showing how the dollar p50 would have moved if
    the floor were authored differently.

    Semantics (this is the load-bearing distinction):
    - Sensitivity is on the FLOOR, not the audience. The audience is
      observed data (e.g. 356 customers cleared a floor of 200). The
      question we surface: if the floor were authored at floor*0.75 or
      floor*1.25, how would the surfaced revenue range have moved?
    - Floor *0.75 / *1.25 span. A cohort comfortably clearing all three
      variants → audience unchanged at every variant → p50_low ==
      p50_high == current p50 (robustness signal).
    - A cohort near the floor: at the upper variant, audience drops to
      0 → revenue_p50 at that variant = $0 → p50_low = $0 (floor-fragile
      signal).

    p50 formula at each variant:
        audience_at_variant = current_audience if current_audience >= variant_floor else 0
        p50_at_variant = audience_at_variant * posterior_value * aov

    Returns a typed driver dict mirroring the
    :func:`_audience_size_driver` discipline:
    ``profile_field_ref`` is echoed from the sibling audience_size
    driver so reviewers can trace both citations back to the same YAML
    cell.
    """

    floor = int(audience_floor)
    floor_minus = int(round(floor * 0.75))
    floor_plus = int(round(floor * 1.25))

    def _p50(variant_floor: int) -> float:
        eff_audience = audience_size if audience_size >= variant_floor else 0
        return round(float(eff_audience) * float(posterior_value) * float(aov), 2)

    p50_at_floor = _p50(floor)
    p50_at_minus = _p50(floor_minus)
    p50_at_plus = _p50(floor_plus)
    p50_low = min(p50_at_floor, p50_at_minus, p50_at_plus)
    p50_high = max(p50_at_floor, p50_at_minus, p50_at_plus)

    d: Dict[str, Any] = {
        "name": "audience_floor_sensitivity",
        "source": "computed",
        "value": {
            "floor_value": floor,
            "floor_minus_25pct": floor_minus,
            "floor_plus_25pct": floor_plus,
            "revenue_p50_at_floor": p50_at_floor,
            "revenue_p50_at_floor_minus_25pct": p50_at_minus,
            "revenue_p50_at_floor_plus_25pct": p50_at_plus,
            "p50_low": p50_low,
            "p50_high": p50_high,
        },
        "notes": (
            f"if audience floor were +/-25%, revenue_p50 would shift to "
            f"${p50_low}-${p50_high}"
        ),
    }
    if profile_field_ref:
        d["profile_field_ref"] = str(profile_field_ref)
    return d


def _sign_agreement_count(
    aligned: Optional[Dict[str, Any]],
    metric: str,
    primary_window: str = "L28",
) -> int:
    """Count windows whose ``delta[metric]`` shares the sign of the
    primary window's delta. Returns 0 when the primary delta is
    missing or zero."""

    if not aligned:
        return 0
    primary = (aligned.get(primary_window) or {}).get("delta", {})
    primary_d = _safe_float(primary.get(metric))
    if primary_d is None or primary_d == 0:
        return 0

    primary_sign = 1 if primary_d > 0 else -1
    count = 1  # the primary window itself agrees with itself
    for w in PHASE5_WINDOWS:
        if w == primary_window:
            continue
        wd = (aligned.get(w) or {}).get("delta", {})
        d = _safe_float(wd.get(metric))
        if d is None or d == 0:
            continue
        if (1 if d > 0 else -1) == primary_sign:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Sprint 6.5 Ticket T4 (R1) — multi-window evidence corroboration.
#
# Sign-only check at MVP; magnitude-ratio band deferred. Per the
# DS architect 2026-05-18 multi-window memo, this primitive runs on
# BOTH ``build_directional_play_card`` and ``build_prior_anchored_play_card``
# to close the asymmetry today's pathways carry.
# ---------------------------------------------------------------------------


#: p-value threshold for the per-window sign check (R1). Looser than the
#: PHASE5 directional p_max=0.05 because R1 is a CORROBORATION read, not
#: a gating-criterion read.
R1_SIGN_P_MAX: float = 0.10


def _window_corroboration_sign_only(
    aligned: Optional[Dict[str, Any]],
    metric: str,
    *,
    primary_window: str,
    agreement_windows: Optional[List[str]] = None,
    p_max: float = R1_SIGN_P_MAX,
) -> Optional[WindowCorroboration]:
    """Compute the typed ``WindowCorroboration`` for one metric.

    Returns ``None`` only when the primary window cannot establish a
    sign (no aligned, no primary delta, primary delta is zero). When
    the primary establishes a sign but no agreement window contributes
    a confident signal, returns :data:`WindowCorroboration.NEUTRAL`
    (the "no opinion" outcome).

    CORROBORATED: every non-primary window in ``agreement_windows`` shows
    a same-sign delta as the primary at p < ``p_max``.
    CONTRADICTED: at least one non-primary window shows an opposite-sign
    delta at p < ``p_max``.
    NEUTRAL: agreement windows are missing data, mixed, or below
    ``p_max``.
    """

    if not aligned:
        return None

    primary = aligned.get(primary_window) or {}
    primary_delta = _safe_float((primary.get("delta") or {}).get(metric))
    if primary_delta is None or primary_delta == 0:
        return None
    primary_sign = 1 if primary_delta > 0 else -1

    if agreement_windows is None:
        agreement_windows = [w for w in PHASE5_WINDOWS if w != primary_window]
    else:
        agreement_windows = [w for w in agreement_windows if w != primary_window]
    if not agreement_windows:
        return WindowCorroboration.NEUTRAL

    same_sign_confident = 0
    opposite_sign_confident = 0
    confident_total = 0
    for w in agreement_windows:
        wd = (aligned.get(w) or {}).get("delta", {})
        wp = (aligned.get(w) or {}).get("p", {})
        d = _safe_float(wd.get(metric))
        p = _safe_float(wp.get(metric))
        if d is None or d == 0:
            continue
        if p is None or p >= p_max:
            continue
        confident_total += 1
        sign = 1 if d > 0 else -1
        if sign == primary_sign:
            same_sign_confident += 1
        else:
            opposite_sign_confident += 1

    if opposite_sign_confident >= 1:
        return WindowCorroboration.CONTRADICTED
    if same_sign_confident == len(agreement_windows):
        return WindowCorroboration.CORROBORATED
    return WindowCorroboration.NEUTRAL


def _prior_anchored_window_corroboration(
    aligned: Optional[Dict[str, Any]],
    *,
    metric: str,
    primary_window: str,
    agreement_windows: List[str],
) -> Optional[WindowCorroboration]:
    """Prior-anchored pathway parity for R1 (closes the DS architect §1
    asymmetry).

    At S6.5 MVP the prior-anchored pathway has no per-window cohort
    recalculation (e.g. winback_dormant_cohort's reactivation_rate is
    not stored in ``aligned`` per window). The faithful behavior is:
    read ``aligned[w].delta[metric]`` exactly like the directional
    primitive; when the metric is unavailable across the windows
    (typical at S6.5 cold start), return :data:`WindowCorroboration.NEUTRAL`
    so the prior-anchored card still emits a typed value rather than
    leaving the field ``None``. This pins the field's presence on
    BOTH pathways (test 22) without fabricating a per-window signal.
    """

    res = _window_corroboration_sign_only(
        aligned,
        metric,
        primary_window=primary_window,
        agreement_windows=agreement_windows,
    )
    if res is None:
        # Primary has no signal in aligned (likely; reactivation_rate is
        # not a typical aligned-snapshot metric at S6.5). Emit NEUTRAL to
        # pin field-presence parity with the directional pathway.
        return WindowCorroboration.NEUTRAL
    return res


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def build_directional_play_card(
    candidate: Any,
    aligned: Optional[Dict[str, Any]],
    *,
    primary_window: str = "L28",
    p_max: float = PHASE5_DIRECTIONAL_P_MAX,
    min_consistency: int = PHASE5_DIRECTIONAL_MIN_CONSISTENCY,
    store_profile: Optional[Any] = None,
    profile_flag_on: bool = False,
) -> Optional[PlayCard]:
    """Phase 5.6: build a directional PlayCard from an M3 Candidate.

    Returns:
        A typed :class:`PlayCard` with ``evidence_class=DIRECTIONAL`` and
        ``revenue_range.suppressed=True`` (no calibrated lift), OR
        ``None`` when the supporting signal does not meet the Phase 5.6
        bar.

    Pre-conditions:
        - ``candidate.play_id`` is in :data:`_SUPPORTED`.
        - ``candidate.preliminary_rejection_reason is None`` (audience
          cleared M3 minimum-N gate).
        - The supporting signal for the play has L28 p < ``p_max``.
        - Sign agreement across windows is >= ``min_consistency``.

    Post-conditions:
        - ``revenue_range.suppressed = True`` always (Phase 5.6).
        - ``measurement.p_internal`` carries the L28 p-value but
          ``measurement.observed_effect`` is the L28 *delta*, not an
          intervention effect.
        - The card carries no ``p =`` / ``q =`` / ``CI`` strings; the
          renderer will format the ``Measurement`` block in plain text.

    The function is total: no exceptions are raised on partial input.
    """

    if candidate is None or aligned is None:
        return None

    play_id = str(getattr(candidate, "play_id", "") or "")
    cfg_entry = _SUPPORTED.get(play_id)
    if cfg_entry is None:
        return None

    # Audience must have cleared the M3 minimum-N gate.
    if getattr(candidate, "preliminary_rejection_reason", None):
        return None

    audience_size = _safe_int(getattr(candidate, "audience_size", None)) or 0
    if audience_size <= 0:
        return None

    # Sprint 6.5 Ticket T4: when ``ENGINE_V2_STORE_PROFILE`` is ON and a
    # ``StoreProfile`` is passed in, take ``primary_window`` +
    # ``agreement_windows`` from ``profile.measurement``; otherwise
    # preserve the caller's primary_window default for flag-OFF
    # byte-identity. ``agreement_windows`` is always
    # ``{L28, L56, L90} \ primary_window`` when not profile-derived.
    agreement_windows: List[str] = [w for w in PHASE5_WINDOWS if w != primary_window]
    if profile_flag_on and store_profile is not None:
        meas_ctx = getattr(store_profile, "measurement", None)
        if meas_ctx is not None:
            primary_window = str(getattr(meas_ctx, "primary_window", primary_window))
            aw = list(getattr(meas_ctx, "agreement_windows", []) or [])
            if aw:
                agreement_windows = [w for w in aw if w != primary_window]

    metric = cfg_entry.metric
    primary = aligned.get(primary_window) or {}
    primary_p = _safe_float((primary.get("p") or {}).get(metric))
    primary_delta = _safe_float((primary.get("delta") or {}).get(metric))
    primary_value = _safe_float(primary.get(metric))
    if primary_p is None or primary_delta is None:
        return None
    if primary_p >= p_max:
        return None
    if primary_delta == 0:
        return None

    consistency = _sign_agreement_count(aligned, metric, primary_window)
    if consistency < min_consistency:
        return None

    # Identified n on the primary window (used as the cohort size for
    # the supporting metric, not the play audience size).
    meta = primary.get("meta") or {}
    n_recent = _safe_int(meta.get("identified_recent"))

    # Sprint 6.5 Ticket T4 (R1): typed multi-window corroboration. Only
    # emitted when the profile flag is ON, so flag-OFF byte-identity
    # holds on every pinned fixture.
    window_corroboration: Optional[WindowCorroboration] = None
    if profile_flag_on:
        window_corroboration = _window_corroboration_sign_only(
            aligned,
            metric,
            primary_window=primary_window,
            agreement_windows=agreement_windows,
        )

    # Build the typed Measurement. ``observed_effect`` = the L28 delta
    # (relative change), so the renderer can summarize "metric moved
    # +6.6%" without claiming intervention lift. ``p_internal`` is the
    # L28 p-value but is NEVER rendered to merchants (M9 contract).
    measurement = Measurement(
        metric=metric,
        observed_effect=primary_delta,
        n=n_recent,
        primary_window=primary_window,
        consistency_across_windows=consistency,
        p_internal=primary_p,
        window_corroboration=window_corroboration,
    )

    # S13.6-T1a: engine-authored ``why_now`` stripped per Pivot 2.
    # Direction + magnitude flow via the typed Measurement.observed_effect
    # + Observation deltas; downstream narration recomposes the prose.

    audience = Audience(
        id=f"phase5_{play_id}",
        definition=getattr(candidate, "segment_definition", None) or "single-purchase cohort",
        size=audience_size,
        fraction_of_base=None,
    )

    # Phase 5.6: suppress revenue range. We do not have a calibrated
    # intervention effect for this play, so dollar projections would
    # be fabrication. Drivers preserve the suppression rationale for
    # receipts / debug.html.
    # S13.6-T7a: paired ``suppression_reason`` wraps the existing
    # producer string at the seam per DS Q1 (no producer rewrite).
    from .engine_run import RevenueRangeSuppressionReason as _RRSR_DI
    suppressed_range = RevenueRange(
        p10=None,
        p50=None,
        p90=None,
        source=None,
        drivers=[
            {
                "name": "suppression_reason",
                "source": "measurement_builder_v2",
                "value": "directional_no_intervention_effect",
                "rationale": (
                    "supporting signal is a state statistic, not an "
                    "intervention effect; revenue suppressed until "
                    "campaign realization data calibrates lift"
                ),
            },
            {
                "name": cfg_entry.metric,
                "source": "store_observed",
                "value": primary_value,
                "primary_window": primary_window,
                "delta": primary_delta,
                "consistency_across_windows": consistency,
            },
        ],
        suppressed=True,
        suppression_reason=_RRSR_DI.DIRECTIONAL_NO_INTERVENTION_EFFECT,
    )

    # Phase 5.1 follow-up: addressable opportunity context (body copy only).
    # Populated only when audience size and a defensible recent AOV are
    # both available. Omit silently otherwise so the card never carries a
    # fabricated dollar number.
    opportunity_context = _build_opportunity_context(
        audience_size,
        aligned,
        primary_window=primary_window,
    )

    # S13.6-T6: typed MechanismIntent atom. Lazy import keeps
    # decide.py -> measurement_builder.py ordering clean.
    from .decide import _build_mechanism_intent as _build_mech_intent
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.DIRECTIONAL,
        confidence_label="Emerging",
        # S13.6-T1a: ``recommendation_text`` / ``why_now`` stripped.
        audience=audience,
        measurement=measurement,
        revenue_range=suppressed_range,
        inventory=None,
        conflicts=None,
        launch_window=None,
        opportunity_context=opportunity_context,
        # S13.6-T2: klaviyo_brief_inputs removed (founder lock-in #6).
        receipts_ref=None,
        # S13.6-T6: typed MechanismIntent atom; None for unmapped play_ids.
        mechanism_intent=_build_mech_intent(play_id),
    )


# ---------------------------------------------------------------------------
# Sprint 6 Ticket T1 — prior-anchored PlayCard pathway
#
# Parallel to ``build_directional_play_card`` (which requires a p-value /
# delta gate from the aligned KPI snapshot). The prior-anchored pathway
# is for Tier-B plays whose evidence is COHORT EXISTENCE — the audience
# IS the directional signal. The PlayCard posterior is anchored on a
# validation-status-aware prior via :func:`src.sizing.bayesian_blend`.
#
# Cold-start posture (T1.5 default state): when no campaign outcomes have
# flowed back yet, ``observed_k = observed_n = 0`` and the posterior
# collapses to the prior. This is the honest cold-start state, not a
# bug. The ``blend_provenance`` driver block surfaces it explicitly so
# downstream agents / merchants can see "this estimate IS the Klaviyo
# benchmark; will calibrate toward your store's reality as outcomes
# import" (Phase 9 outcome loop, Sprint 10+).
#
# Validation-status routing (per Sprint 7.5 contract):
#   - validated_external / validated_internal / elicited_expert →
#     non-suppressed RevenueRange, source=BLEND.
#   - heuristic_unvalidated / placeholder → suppressed RevenueRange
#     with ``drivers[].reason="prior_unvalidated"``; decide.py's
#     ``_route_prior_unvalidated_holds`` then re-routes the PlayCard
#     into Considered with ReasonCode.PRIOR_UNVALIDATED.
# ---------------------------------------------------------------------------


# S13.6-T1a: ``recommendation_text`` + ``why_now_template`` slots stripped
# from the prior-anchored signal config per Pivot 2. ``mechanism_text``
# survives because mechanism flows separately through priors metadata at
# the merchant-facing surface (priors_loader.get_mechanism), and the
# wording here documents the operational substrate the engine is acting
# on (not narrated merchant copy).
@dataclass(frozen=True)
class _PriorAnchoredSignal:
    play_id: str
    prior_play_id: str  # the play_id under which the prior is authored
    prior_key: str
    metric: str
    would_be_measured_by: WouldBeMeasuredBy
    mechanism_text: str


_PRIOR_ANCHORED: Dict[str, _PriorAnchoredSignal] = {
    "winback_dormant_cohort": _PriorAnchoredSignal(
        play_id="winback_dormant_cohort",
        prior_play_id="winback_21_45",
        prior_key="base_rate",
        metric="reactivation_rate",
        would_be_measured_by=WouldBeMeasuredBy.LAPSED_REACTIVATION_IN_30D,
        mechanism_text=(
            "Email the dormant repeat-buyer cohort with a structured "
            "winback offer; measure reactivation within 30 days."
        ),
    ),
    # Sprint 6 Ticket T3 — replenishment_due.
    # S6-T3.x re-key (2026-05-19): consumes the dedicated
    # ``replenishment_due.base_rate`` block authored under the
    # validated_external 2026-05-19 Gemini Deep Research memo
    # (config/priors_sources/replenishment_due__base_rate__beauty.md).
    # Supersedes D-S6-2 (which routed to bestseller_amplify.bundle_value).
    # Beauty side is validated_external (Klaviyo PERL Cosmetics +
    # Klaviyo H&B 2026 benchmark); supplements side has NO matching
    # block by design (DS architect verdict 2026-05-19: do not author
    # a supplements stub for code-symmetry) and therefore routes to
    # Considered with PRIOR_UNVALIDATED via the standard refusal path
    # in ``_route_prior_unvalidated_holds``.
    #
    # The base_rate prior is a probability rate (0.0-1.0) so the
    # ``audience * posterior * aov`` revenue formula is dimensionally
    # coherent — no double-counting (the dollar-vs-rate category error
    # under D-S6-2 is resolved).
    # Sprint 7 Ticket T2 — cohort_journey_first_to_second.
    # Reuses the validated_external first_to_second_purchase.base_rate
    # prior (S7.5-T2 promotion; bsandco DTC RPR 2026 memo,
    # effective_n=156110, wildcard ``applies_to: { vertical: "*" }``).
    # No new memo authored — the lowest-risk S7 builder per IM plan.
    # Retires the legacy first_to_second_purchase directional proxy in
    # ``build_directional_play_card`` at S7-T2.5 (this ticket ships the
    # impl + flag OFF; legacy proxy untouched per IM preserved
    # out-of-scope discipline through one sprint past T2.5).
    "cohort_journey_first_to_second": _PriorAnchoredSignal(
        play_id="cohort_journey_first_to_second",
        prior_play_id="first_to_second_purchase",
        prior_key="base_rate",
        metric="first_to_second_conversion_rate",
        would_be_measured_by=WouldBeMeasuredBy.FIRST_TO_SECOND_PURCHASE_IN_30D,
        mechanism_text=(
            "Email the 30-90d post-first-purchase cohort a value-led "
            "second-purchase nudge with best-next-product education; "
            "measure second purchase within 30 days."
        ),
    ),
    # Sprint 7 Ticket T3 — aov_lift_via_threshold_bundle.
    # Consumes the dual-tier ``aov_lift_via_threshold_bundle.base_rate``
    # prior block (S7 priors-wiring, validated by DS 2026-05-20):
    #   - Beauty entry: validated_external (Memo 2, ACCEPT as-is) →
    #     pseudo_n=30 via PSEUDO_N_BY_STATUS.
    #   - Supplements entry: elicited_expert (Memo 3 DOWNGRADED per DS
    #     verdict — cross-vertical evidence laundering safeguard
    #     KI-NEW-J) → pseudo_n=10 via PSEUDO_N_BY_STATUS.
    # Both entries route through the prior block's entry list; the
    # standard ``get_prior`` lookup will resolve the per-vertical entry
    # by ``applies_to.vertical`` and validation_status follows the
    # block's authored value. Both validated_external + elicited_expert
    # are in PSEUDO_N_BY_STATUS so both verticals are blend-permitted
    # and emit ``source=BLEND`` (NOT suppressed). The asymmetric audience
    # floor (D-FLOOR-aov_lift_via_threshold_bundle: beauty + mixed_beauty
    # cells, no supplements per-play cell) is the SOLE asymmetric seam;
    # supplements falls back to ``_default_by_stage`` per D-S6.5-4.
    # The legacy ``bestseller_amplify`` play is operationally distinct
    # (static pre-purchase bundle; M2 measured-margin pathway via
    # Recommended Experiment allowlist) and is preserved untouched.
    "aov_lift_via_threshold_bundle": _PriorAnchoredSignal(
        play_id="aov_lift_via_threshold_bundle",
        prior_play_id="aov_lift_via_threshold_bundle",
        prior_key="base_rate",
        metric="aov_threshold_crossing_conversion_rate",
        would_be_measured_by=(
            WouldBeMeasuredBy.AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D
        ),
        mechanism_text=(
            "Email customers $5-$15 below the merchant AOV threshold with "
            "a curated cross-sell SKU that would complete the threshold; "
            "no discount code; measure threshold-crossing conversion "
            "within 14 days."
        ),
    ),
    # Sprint 7 Ticket T1 — discount_dependency_hygiene.
    # Beauty-only activation by design: ``applies_to.vertical = "beauty"``
    # routes the supplements path to ``PRIOR_UNVALIDATED`` Considered via
    # the standard S7.5-T3 refusal in ``_route_prior_unvalidated_holds``
    # (no supplements prior block authored per DS Memo-4 REJECT verdict).
    # Anchors on the validated_external Beauty-only
    # ``discount_dependency_hygiene.base_rate.beauty`` prior (DS-validated
    # 2026-05-20; Klaviyo H&B 2026 omnichannel benchmark + envelope
    # caveat — KI-NEW-K envelope re-fit at effective_n=60 deferred to
    # Sprint 8 calibration sweep; today's range_p10/p90 are text-derived
    # from the source memo, not Beta(0.66, 29.34) CDF-derived). The
    # legacy ``discount_hygiene`` play_id is operationally distinct
    # (M2 measured-margin pathway; KI-21 Recommended Experiment
    # allowlist); both coexist by founder Q1 default 2026-05-20.
    "discount_dependency_hygiene": _PriorAnchoredSignal(
        play_id="discount_dependency_hygiene",
        prior_play_id="discount_dependency_hygiene",
        prior_key="base_rate",
        metric="discount_dependency_hygiene_full_price_conversion_rate",
        would_be_measured_by=(
            WouldBeMeasuredBy.DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D
        ),
        mechanism_text=(
            "Suppress discount codes for 14 days across all channels for "
            "the discount-conditioned cohort; send a value-led, no-urgency, "
            "full-price reminder; measure full-price repeat purchase "
            "within 14 days post-send."
        ),
    ),
    "replenishment_due": _PriorAnchoredSignal(
        play_id="replenishment_due",
        prior_play_id="replenishment_due",
        prior_key="base_rate",
        metric="replenishment_conversion_rate",
        would_be_measured_by=(
            WouldBeMeasuredBy.REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW
        ),
        mechanism_text=(
            "Email the cadence-due cohort with a structured "
            "replenishment reminder; measure whether the next "
            "in-class purchase falls within the next cadence window."
        ),
    ),
}


def _vertical_winback_window(vertical: Optional[str]) -> str:
    v = (vertical or "").strip().lower()
    if v == "supplements":
        return "60-120 days ago"
    return "21-45 days ago"


# ---------------------------------------------------------------------------
# Sprint 7.6 Ticket T1 — winback observed-effect computation (B-1).
#
# Computes per-store lapse_recovery_rate observed-effect across {L28, L56,
# L90} anchors using the T0 helper. For each anchor at ``now - W days``,
# builds the historical dormant cohort under the SAME vertical-aware
# winback rule the M3 builder uses (last-order in [wb_lo, wb_hi] days
# before the anchor, ≥2 prior orders, no orders in the 28d before the
# anchor) and counts how many placed an order in the W-day window
# immediately after the anchor (the "recovered" k).
#
# Prior window for the z-test is the W-day window BEFORE the recent
# window for the SAME dormant cohort definition (sliding the anchor back
# another W days). This gives a defensible recent-vs-prior contrast on
# the cohort's own lapse-recovery rate rather than against an arbitrary
# reference.
#
# Gated by ``ENGINE_V2_OBSERVED_EFFECT_WINBACK`` (default OFF at T1;
# T1.5 flips). When the flag is OFF, this function is not called and the
# prior-anchored card seam falls through to the cold-start
# ``observed_k = observed_n = 0`` default — byte-identical to today.
# ---------------------------------------------------------------------------


def _winback_window_bounds(vertical: Optional[str]) -> Tuple[int, int]:
    v = (vertical or "").strip().lower()
    if v == "supplements":
        return (60, 120)
    return (21, 45)


def _dormant_cohort_at_anchor(
    g: pd.DataFrame,
    *,
    anchor: pd.Timestamp,
    wb_lo: int,
    wb_hi: int,
) -> set:
    """Return customer_ids that meet the dormant-cohort rule at ``anchor``.

    Mirrors :func:`audience_builders.winback_dormant_cohort_candidates`:

    1. Last order on/before anchor falls in [wb_lo, wb_hi] days before
       anchor.
    2. >=2 prior orders on/before anchor.
    3. No orders in the 28d immediately before anchor (already
       self-reactivated).

    Pure read on ``g``; never mutates.
    """
    if g is None or g.empty or "customer_id" not in g.columns or "Created at" not in g.columns:
        return set()
    gg = g.copy()
    gg["Created at"] = pd.to_datetime(gg["Created at"], errors="coerce")
    gg = gg[~gg["Created at"].isna()]
    if gg.empty:
        return set()

    on_or_before = gg[gg["Created at"] <= anchor]
    if on_or_before.empty:
        return set()

    last_by_cust = on_or_before.groupby("customer_id")["Created at"].max()
    days_since = (anchor - last_by_cust).dt.days
    recency_ids = set(
        days_since[(days_since >= wb_lo) & (days_since <= wb_hi)].index.astype(str)
    )
    if not recency_ids:
        return set()

    order_counts = on_or_before["customer_id"].astype(str).value_counts()
    repeat_ids = set(order_counts[order_counts >= 2].index)

    pre28_start = anchor - pd.Timedelta(days=28)
    pre28_active_ids = set(
        on_or_before[
            (on_or_before["Created at"] > pre28_start)
            & (on_or_before["Created at"] <= anchor)
        ]["customer_id"].astype(str).unique()
    )

    return (recency_ids & repeat_ids) - pre28_active_ids


def _reactivated_count(
    g: pd.DataFrame,
    *,
    cohort_ids: set,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> int:
    """Count cohort customers with at least one order in (start, end]."""
    if not cohort_ids or g is None or g.empty:
        return 0
    if "customer_id" not in g.columns or "Created at" not in g.columns:
        return 0
    gg = g.copy()
    gg["Created at"] = pd.to_datetime(gg["Created at"], errors="coerce")
    gg = gg[~gg["Created at"].isna()]
    if gg.empty:
        return 0
    cust = gg["customer_id"].astype(str)
    mask = (
        cust.isin(cohort_ids)
        & (gg["Created at"] > window_start)
        & (gg["Created at"] <= window_end)
    )
    return int(gg.loc[mask, "customer_id"].astype(str).nunique())


def compute_winback_observed_effect(
    g: Optional[pd.DataFrame],
    *,
    vertical: Optional[str],
) -> Tuple[Optional[ObservedEffectResult], Optional[MultiWindowAgreement]]:
    """Compute multi-window observed lapse_recovery_rate for winback.

    Returns a tuple ``(primary_result_L28, multi_window_agreement)``.
    ``primary_result_L28`` is the L28 window's observed result and is
    what the caller threads into ``observed_k`` / ``observed_n`` on the
    prior-anchored card.  ``multi_window_agreement`` is the sign-
    agreement across all three windows for stash on the card's
    measurement payload.

    Returns ``(None, None)`` when ``g`` is empty or no anchor produced
    a non-zero cohort (honest zero-data fallback; caller MUST keep
    ``observed_k = observed_n = 0`` so the posterior collapses to the
    prior).
    """
    if g is None or g.empty:
        return None, None
    if "Created at" not in g.columns or "customer_id" not in g.columns:
        return None, None

    wb_lo, wb_hi = _winback_window_bounds(vertical)

    maxd = pd.to_datetime(g["Created at"], errors="coerce").max()
    if pd.isna(maxd):
        return None, None

    windows = ("L28", "L56", "L90")
    window_days = {"L28": 28, "L56": 56, "L90": 90}

    per_window: Dict[str, ObservedEffectResult] = {}
    primary: Optional[ObservedEffectResult] = None

    for w in windows:
        W = window_days[w]
        # Recent window: cohort at anchor = maxd - W; recovery measured
        # in (anchor, maxd].
        recent_anchor = maxd - pd.Timedelta(days=W)
        recent_cohort = _dormant_cohort_at_anchor(
            g, anchor=recent_anchor, wb_lo=wb_lo, wb_hi=wb_hi
        )
        recent_n = len(recent_cohort)
        recent_k = _reactivated_count(
            g,
            cohort_ids=recent_cohort,
            window_start=recent_anchor,
            window_end=maxd,
        )

        # Prior window: cohort at anchor = maxd - 2W; recovery measured
        # in (prior_anchor, recent_anchor].
        prior_anchor = maxd - pd.Timedelta(days=2 * W)
        prior_cohort = _dormant_cohort_at_anchor(
            g, anchor=prior_anchor, wb_lo=wb_lo, wb_hi=wb_hi
        )
        prior_n = len(prior_cohort)
        prior_k = _reactivated_count(
            g,
            cohort_ids=prior_cohort,
            window_start=prior_anchor,
            window_end=recent_anchor,
        )

        res = compute_two_proportion_observed(recent_k, recent_n, prior_k, prior_n)
        per_window[w] = res
        if w == "L28":
            primary = res

    agreement = compute_multi_window_sign_agreement(per_window)
    return primary, agreement


# ---------------------------------------------------------------------------
# Sprint 7.6 Ticket T2 — replenishment_due observed-effect computation (B-2).
#
# Computes per-store ``due_cohort_reorder_rate`` observed-effect across
# {L28, L56, L90} anchors using the T0 helper. For each window W, an anchor
# is placed at ``maxd - W``; the "due cohort" at the anchor is customers
# whose most-recent in-class purchase on/before the anchor falls in
# ``[median_gap * 0.8, median_gap * 1.2]`` days before the anchor, where
# ``median_gap`` is that customer's own median inter-purchase gap on the
# in-class SKU set (requires >=2 in-class purchases on/before the anchor).
# k = members who placed an additional in-class purchase in (anchor, maxd].
# The prior window anchors W days earlier on the SAME due-cohort rule, with
# k measured in (anchor_prior, anchor_recent].
#
# Beauty in-class membership uses ``replenishment_parser.get_size_regex``
# (matches the M3 builder's beauty path). Supplements is SKIPPED — the
# replenishment_parser returns None for vertical=supplements (KI-27), so
# the helper returns ``(None, None)`` and the caller keeps
# ``observed_k = observed_n = 0`` for that vertical (DATA_QUALITY_FLAG:
# replenishment_parser_unavailable continues to apply elsewhere).
#
# Gated by ``ENGINE_V2_OBSERVED_EFFECT_REPLENISHMENT`` (default OFF at T2;
# T2.5 flips conditional on tripwire). Flag-OFF -> helper not invoked,
# cold-start path remains in force, byte-identical to today.
# ---------------------------------------------------------------------------


def _beauty_in_class_key(text: str) -> Optional[str]:
    """Return canonical beauty in-class key for a SKU text, or ``None``.

    Mirrors :func:`audience_builders.replenishment_due_candidates._beauty_key`
    so the observed-effect path classifies SKUs the same way the M3 builder
    does. Returns ``None`` when the size regex does not match.
    """
    try:
        from .replenishment_parser import get_size_regex
        rx = get_size_regex("beauty")
        if not rx:
            return None
        import re as _re
        m = _re.search(rx, text or "", flags=_re.IGNORECASE)
        if m is None:
            return None
        try:
            return str(m.group(0))
        except IndexError:
            return text
    except Exception:
        return None


def _due_cohort_at_anchor(
    g_inclass: pd.DataFrame,
    *,
    anchor: pd.Timestamp,
    low_factor: float = 0.8,
    high_factor: float = 1.2,
) -> Tuple[set, Dict[str, pd.Timestamp]]:
    """Return ``(cohort_ids, last_purchase_by_cust)`` for the due cohort.

    Members: customers with >=2 in-class purchases on/before ``anchor``
    whose days-since-last-in-class-purchase falls in
    ``[median_gap * low_factor, median_gap * high_factor]``, where
    ``median_gap`` is the per-customer median inter-purchase gap (days)
    on the in-class purchase sequence.

    ``g_inclass`` must already be filtered to in-class rows only
    (``_sku_key`` non-null). Pure read.
    """
    if g_inclass is None or g_inclass.empty:
        return set(), {}
    on_or_before = g_inclass[g_inclass["Created at"] <= anchor]
    if on_or_before.empty:
        return set(), {}
    cohort: set = set()
    last_by_cust: Dict[str, pd.Timestamp] = {}
    for cust_id, sub in on_or_before.groupby("customer_id", sort=True):
        ts = (
            pd.to_datetime(sub["Created at"], errors="coerce")
            .dropna()
            .sort_values()
            .reset_index(drop=True)
        )
        if len(ts) < 2:
            continue
        diffs = ts.diff().dropna().dt.total_seconds() / 86400.0
        if diffs.empty:
            continue
        median_gap = float(np.median(np.asarray(diffs.tolist(), dtype=float)))
        if median_gap <= 0:
            continue
        last_ts = ts.iloc[-1]
        days_since = float((anchor - last_ts).total_seconds() / 86400.0)
        if days_since < 0:
            continue
        lower = median_gap * low_factor
        upper = median_gap * high_factor
        if lower <= days_since <= upper:
            cid = str(cust_id)
            cohort.add(cid)
            last_by_cust[cid] = last_ts
    return cohort, last_by_cust


def _inclass_reorder_count(
    g_inclass: pd.DataFrame,
    *,
    cohort_ids: set,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> int:
    """Count cohort customers with at least one in-class order in
    (start, end]. ``g_inclass`` must already be in-class-filtered."""
    if not cohort_ids or g_inclass is None or g_inclass.empty:
        return 0
    cust = g_inclass["customer_id"].astype(str)
    mask = (
        cust.isin(cohort_ids)
        & (g_inclass["Created at"] > window_start)
        & (g_inclass["Created at"] <= window_end)
    )
    return int(g_inclass.loc[mask, "customer_id"].astype(str).nunique())


def compute_replenishment_observed_effect(
    g: Optional[pd.DataFrame],
    *,
    vertical: Optional[str],
) -> Tuple[Optional[ObservedEffectResult], Optional[MultiWindowAgreement]]:
    """Compute multi-window observed due_cohort_reorder_rate.

    Returns ``(primary_result_L28, multi_window_agreement)``. Beauty only;
    supplements path returns ``(None, None)`` per KI-27 (parser
    unavailable). Honest zero-data fallback when ``g`` is empty, missing
    required columns, or no in-class SKU rows survive classification.
    """
    if g is None or g.empty:
        return None, None
    needed = {"Created at", "customer_id", "lineitem_any"}
    if not needed.issubset(set(g.columns)):
        return None, None
    v = (vertical or "").strip().lower()
    # Supplements skipped at T2 (KI-27). Mixed routes through beauty
    # classifier only at T2 to match the conservative B-2 wire-in scope;
    # supplements-side observed-effect lands when KI-27 resolves.
    if v == "supplements":
        return None, None

    gg = g.copy()
    gg["Created at"] = pd.to_datetime(gg["Created at"], errors="coerce")
    gg = gg[~gg["Created at"].isna()]
    if gg.empty:
        return None, None
    gg["customer_id"] = gg["customer_id"].astype(str)
    gg["lineitem_any"] = gg["lineitem_any"].astype(str)

    maxd = gg["Created at"].max()
    if pd.isna(maxd):
        return None, None

    # In-class filter via beauty size regex (matches M3 builder).
    keys = gg["lineitem_any"].map(_beauty_in_class_key)
    gg = gg.assign(_sku_key=keys)
    gg = gg[gg["_sku_key"].notna() & (gg["_sku_key"] != "")]
    if gg.empty:
        return None, None

    windows = ("L28", "L56", "L90")
    window_days = {"L28": 28, "L56": 56, "L90": 90}

    per_window: Dict[str, ObservedEffectResult] = {}
    primary: Optional[ObservedEffectResult] = None

    for w in windows:
        W = window_days[w]
        recent_anchor = maxd - pd.Timedelta(days=W)
        recent_cohort, _ = _due_cohort_at_anchor(gg, anchor=recent_anchor)
        recent_n = len(recent_cohort)
        recent_k = _inclass_reorder_count(
            gg,
            cohort_ids=recent_cohort,
            window_start=recent_anchor,
            window_end=maxd,
        )

        prior_anchor = maxd - pd.Timedelta(days=2 * W)
        prior_cohort, _ = _due_cohort_at_anchor(gg, anchor=prior_anchor)
        prior_n = len(prior_cohort)
        prior_k = _inclass_reorder_count(
            gg,
            cohort_ids=prior_cohort,
            window_start=prior_anchor,
            window_end=recent_anchor,
        )

        res = compute_two_proportion_observed(recent_k, recent_n, prior_k, prior_n)
        per_window[w] = res
        if w == "L28":
            primary = res

    agreement = compute_multi_window_sign_agreement(per_window)
    return primary, agreement


# ---------------------------------------------------------------------------
# Sprint 7.6 Ticket T3 — discount_dependency_hygiene observed-effect (B-3).
#
# Per ARCHITECTURE_PLAN.md §III B-3:244-246, the supporting metric is
# ``heavy_discount_share_of_revenue_l28`` — the fraction of L28 revenue
# attributable to the heavy-discount-conditioned cohort, compared to the
# L28-prior fraction. Two-proportion z-test on the revenue fractions
# (revenue-weighted, NOT order-counted) because the play's economic claim
# is margin, which scales with revenue.
#
# Cohort definition (mirrors the M3 builder at
# ``audience_builders.discount_dependency_hygiene_candidates``): customers
# whose >=50% of historical orders on/before the anchor carried a non-zero
# discount_rate. The cohort is recomputed at each window's anchor so the
# observed-effect contrast is honest recent-vs-prior on the SAME rule the
# M3 builder uses.
#
# Per-window computation (W in {L28, L56, L90}, anchor = maxd - W):
#   recent:  k = sum(net_sales) on cohort orders in (anchor, maxd]
#            n = sum(net_sales) on ALL orders in (anchor, maxd]
#   prior:   k = sum(net_sales) on cohort orders in (anchor - W, anchor]
#            n = sum(net_sales) on ALL orders in (anchor - W, anchor]
# k and n are passed to ``compute_two_proportion_observed`` as
# ``round(k)`` / ``round(n)`` to preserve revenue-weighting semantics
# through the z-test cell-count contract.
#
# Supplements: helper short-circuits to (None, None) per DS Memo-4 REJECT
# verdict (no supplements prior block by design; Path-D dormant). The
# caller keeps observed_k = observed_n = 0 so the posterior collapses to
# the prior on supplements unconditionally.
#
# Gated by ``ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE`` (default OFF at
# T3; T3.5 flips). Flag-OFF -> helper not invoked, cold-start path remains
# in force, byte-identical to today.
# ---------------------------------------------------------------------------


def _heavy_discount_cohort_at_anchor(
    g: pd.DataFrame,
    *,
    anchor: pd.Timestamp,
    min_frac: float = 0.5,
) -> set:
    """Return customer_ids whose historical-on-or-before-anchor order
    history has fraction-of-discounted-orders >= ``min_frac``.

    Mirrors :func:`audience_builders.discount_dependency_hygiene_candidates`:
    NaN ``discount_rate`` coerced to 0.0 (safe default — treat unknown
    discount as no-discount; alternative would inflate the fraction toward
    1.0 for customers with incomplete instrumentation). Pure read on ``g``.
    """
    if g is None or g.empty:
        return set()
    if "customer_id" not in g.columns or "discount_rate" not in g.columns:
        return set()
    if "Created at" not in g.columns:
        return set()
    gg = g[g["Created at"] <= anchor]
    if gg.empty:
        return set()
    is_disc = (pd.to_numeric(gg["discount_rate"], errors="coerce").fillna(0.0) > 0.0).astype(int)
    per_cust = pd.DataFrame({
        "customer_id": gg["customer_id"].astype(str).values,
        "is_disc": is_disc.values,
    })
    grouped = per_cust.groupby("customer_id")["is_disc"].agg(
        total="count", disc="sum"
    )
    if grouped.empty:
        return set()
    frac = grouped["disc"] / grouped["total"]
    return set(frac[frac >= float(min_frac)].index.astype(str).tolist())


def _revenue_in_window(
    g: pd.DataFrame,
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    cohort_ids: Optional[set] = None,
) -> float:
    """Sum ``net_sales`` on rows in (window_start, window_end].

    When ``cohort_ids`` is provided, restrict to rows whose ``customer_id``
    is in the cohort; otherwise sum all rows in the window.
    """
    if g is None or g.empty:
        return 0.0
    if "Created at" not in g.columns or "net_sales" not in g.columns:
        return 0.0
    mask = (g["Created at"] > window_start) & (g["Created at"] <= window_end)
    if cohort_ids is not None:
        if not cohort_ids:
            return 0.0
        mask = mask & g["customer_id"].astype(str).isin(cohort_ids)
    if not mask.any():
        return 0.0
    vals = pd.to_numeric(g.loc[mask, "net_sales"], errors="coerce").fillna(0.0)
    # Clamp to non-negative — refunds-as-negative-rows do not subtract
    # from the heavy-discount share denominator in an honest reading of
    # "share of revenue."
    vals = vals.clip(lower=0.0)
    return float(vals.sum())


def compute_discount_hygiene_observed_effect(
    g: Optional[pd.DataFrame],
    *,
    vertical: Optional[str],
) -> Tuple[Optional[ObservedEffectResult], Optional[MultiWindowAgreement]]:
    """Compute multi-window observed ``heavy_discount_share_of_revenue``.

    Returns ``(primary_result_L28, multi_window_agreement)``. The primary
    L28 result is what the caller threads into ``observed_k`` / ``observed_n``
    on the prior-anchored card; ``k`` and ``n`` are revenue dollars
    rounded to int (revenue-weighted z-test cell counts).

    Supplements: returns ``(None, None)`` per DS Memo-4 REJECT (Path-D
    dormant). Honest zero-data fallback when ``g`` is empty, missing
    required columns, or no anchor produced a non-zero denominator.

    Per plan §III B-3:245: two-proportion z-test on revenue fractions
    (revenue-weighted), p<0.05 gate consumed downstream; multi-window
    sign-agreement >=2 evaluated downstream in T6.
    """
    if g is None or g.empty:
        return None, None
    needed = {"Created at", "customer_id", "discount_rate", "net_sales"}
    if not needed.issubset(set(g.columns)):
        return None, None
    v = (vertical or "").strip().lower()
    # Supplements is Path-D dormant per DS Memo-4 REJECT. Short-circuit
    # so the caller's cold-start (observed_k = observed_n = 0) path
    # remains in force on supplements unconditionally.
    if v == "supplements":
        return None, None

    gg = g.copy()
    gg["Created at"] = pd.to_datetime(gg["Created at"], errors="coerce")
    gg = gg[~gg["Created at"].isna()]
    if gg.empty:
        return None, None
    gg["customer_id"] = gg["customer_id"].astype(str)

    maxd = gg["Created at"].max()
    if pd.isna(maxd):
        return None, None

    windows = ("L28", "L56", "L90")
    window_days = {"L28": 28, "L56": 56, "L90": 90}

    per_window: Dict[str, ObservedEffectResult] = {}
    primary: Optional[ObservedEffectResult] = None

    for w in windows:
        W = window_days[w]
        recent_anchor = maxd - pd.Timedelta(days=W)
        prior_anchor = maxd - pd.Timedelta(days=2 * W)

        # Cohort definitions: recompute the heavy-discount cohort at
        # each anchor using only on-or-before-anchor history (no future
        # leakage into either contrast cell).
        recent_cohort = _heavy_discount_cohort_at_anchor(gg, anchor=recent_anchor)
        prior_cohort = _heavy_discount_cohort_at_anchor(gg, anchor=prior_anchor)

        recent_k = _revenue_in_window(
            gg,
            window_start=recent_anchor,
            window_end=maxd,
            cohort_ids=recent_cohort,
        )
        recent_n = _revenue_in_window(
            gg, window_start=recent_anchor, window_end=maxd
        )

        prior_k = _revenue_in_window(
            gg,
            window_start=prior_anchor,
            window_end=recent_anchor,
            cohort_ids=prior_cohort,
        )
        prior_n = _revenue_in_window(
            gg, window_start=prior_anchor, window_end=recent_anchor
        )

        # Revenue-weighted: pass rounded dollars as z-test cell counts so
        # a $200 heavy-discount order contributes 200 to k (not 1). The
        # T0 helper's small-cell Fisher route still applies when any cell
        # < 5 (e.g. very low-revenue windows).
        res = compute_two_proportion_observed(
            int(round(recent_k)),
            int(round(recent_n)),
            int(round(prior_k)),
            int(round(prior_n)),
        )
        per_window[w] = res
        if w == "L28":
            primary = res

    agreement = compute_multi_window_sign_agreement(per_window)
    return primary, agreement


# ---------------------------------------------------------------------------
# Sprint 7.6 Ticket T4 — cohort_journey_first_to_second observed-effect (B-4).
#
# Per plan B-4:258-261: two-proportion z-test on cohort-defined first-to-second
# rates across {L28, L56, L90} windows.
#
# BERKSON INVARIANT (load-bearing; see tests/test_berkson_invariant.py +
# project memory ``project_journey_p_zero.md`` 2026-04-30, original fix in
# commit 554960d / Phase 4.1):
#
#   For each window W, the cohort denominator MUST be defined on
#   first-purchase dates falling in the EARLY HALF of the window
#   [anchor - W, anchor - W/2). Customers whose first purchase falls in the
#   LATE HALF [anchor - W/2, anchor] are excluded from the denominator
#   because they mechanically cannot have had a full half-window of time to
#   place a second order — including them as denominators-without-converters
#   structurally biases the rate downward (Berkson confound).
#
# Numerator = early-half-cohort customers whose SECOND purchase occurred on
# or before ``anchor``. Recent window anchors at ``maxd``; prior window
# anchors at ``maxd - W`` and follows the SAME early-half cohort rule on
# its own [maxd - 2W, maxd - 1.5W) sub-interval.
#
# Vertical scope per plan B-4: applies to "*" (all verticals). No
# supplements short-circuit (the validated_external first_to_second_purchase
# prior is wildcard-vertical per S7.5-T2, mirroring the audience builder).
# ---------------------------------------------------------------------------


def _first_order_by_customer(g: pd.DataFrame) -> "pd.Series":
    """Return ``customer_id -> first Created at`` (per-customer min)."""
    return g.groupby("customer_id")["Created at"].min()


def _second_order_by_customer(g: pd.DataFrame) -> Dict[str, pd.Timestamp]:
    """Return ``customer_id -> second-order Created at`` for customers
    with >=2 distinct orders. Customers with only one order are absent
    from the mapping (they have no second order yet)."""
    out: Dict[str, pd.Timestamp] = {}
    for cust_id, sub in g.groupby("customer_id", sort=True):
        ts = (
            pd.to_datetime(sub["Created at"], errors="coerce")
            .dropna()
            .sort_values()
            .reset_index(drop=True)
        )
        if len(ts) < 2:
            continue
        out[str(cust_id)] = ts.iloc[1]
    return out


def _journey_window_cell(
    first_by_cust: "pd.Series",
    second_by_cust: Dict[str, pd.Timestamp],
    *,
    cohort_start: pd.Timestamp,
    cohort_end: pd.Timestamp,
    second_deadline: pd.Timestamp,
) -> Tuple[int, int]:
    """Return ``(k, n)`` for a single recent-or-prior cell.

    n = customers whose FIRST purchase falls in ``[cohort_start, cohort_end)``
        (the EARLY HALF of the window — Berkson invariant).
    k = of those, customers whose SECOND purchase occurred on or before
        ``second_deadline``.
    """
    mask = (first_by_cust >= cohort_start) & (first_by_cust < cohort_end)
    cohort_ids = set(first_by_cust.index[mask].astype(str))
    n = len(cohort_ids)
    if n == 0:
        return 0, 0
    k = 0
    for cid in cohort_ids:
        sec = second_by_cust.get(cid)
        if sec is not None and sec <= second_deadline:
            k += 1
    return int(k), int(n)


def compute_journey_first_to_second_observed_effect(
    g: Optional[pd.DataFrame],
    *,
    vertical: Optional[str] = None,
) -> Tuple[Optional[ObservedEffectResult], Optional[MultiWindowAgreement]]:
    """Compute multi-window observed first-to-second-purchase rate.

    Returns ``(primary_result_L28, multi_window_agreement)``.

    BERKSON INVARIANT (see tests/test_berkson_invariant.py +
    project_journey_p_zero.md memory 2026-04-30): cohort denominators are
    defined on EARLY-HALF-OF-WINDOW first-purchase dates only. The late
    half is excluded from the denominator to prevent structural rate
    deflation (customers in the late half mechanically cannot have had
    time to place a second order).

    Per plan B-4:258-261: two-proportion z-test on first-to-second rates,
    multi-window sign-agreement across {L28, L56, L90} evaluated
    downstream in T6.
    """
    if g is None or g.empty:
        return None, None
    if "Created at" not in g.columns or "customer_id" not in g.columns:
        return None, None

    gg = g.copy()
    gg["Created at"] = pd.to_datetime(gg["Created at"], errors="coerce")
    gg = gg[~gg["Created at"].isna()]
    if gg.empty:
        return None, None
    gg["customer_id"] = gg["customer_id"].astype(str)

    maxd = gg["Created at"].max()
    if pd.isna(maxd):
        return None, None

    first_by_cust = _first_order_by_customer(gg)
    second_by_cust = _second_order_by_customer(gg)

    windows = ("L28", "L56", "L90")
    window_days = {"L28": 28, "L56": 56, "L90": 90}

    per_window: Dict[str, ObservedEffectResult] = {}
    primary: Optional[ObservedEffectResult] = None

    for w in windows:
        W = window_days[w]
        half = pd.Timedelta(days=W // 2)
        Wd = pd.Timedelta(days=W)

        # Recent window: anchor = maxd. Early half = [maxd - W, maxd - W/2).
        # Second-order deadline = maxd.
        recent_k, recent_n = _journey_window_cell(
            first_by_cust,
            second_by_cust,
            cohort_start=maxd - Wd,
            cohort_end=maxd - half,
            second_deadline=maxd,
        )

        # Prior window: anchor = maxd - W. Early half =
        # [maxd - 2W, maxd - 1.5W). Second-order deadline = maxd - W.
        prior_anchor = maxd - Wd
        prior_k, prior_n = _journey_window_cell(
            first_by_cust,
            second_by_cust,
            cohort_start=prior_anchor - Wd,
            cohort_end=prior_anchor - half,
            second_deadline=prior_anchor,
        )

        res = compute_two_proportion_observed(recent_k, recent_n, prior_k, prior_n)
        per_window[w] = res
        if w == "L28":
            primary = res

    agreement = compute_multi_window_sign_agreement(per_window)
    return primary, agreement


# ---------------------------------------------------------------------------
# Sprint 7.6 Ticket T5 — aov_lift_via_threshold_bundle observed-effect (B-5).
#
# Per plan B-5:249 + IM continuation plan §3 T5: DUAL statistical test.
#   1. Welch's t-test on audience-level order AOV (recent vs prior window),
#      method="welch_t".
#   2. Two-proportion z-test on `near_threshold_aov_share` --- fraction of
#      orders whose net_sales falls in [0.7T, 0.95T] (recent vs prior),
#      method="z_pooled" / "fisher_exact" via the T0 helper.
#
# BOTH tests must reach p<0.10 jointly for downstream T6 eligibility. T5
# itself only computes + stashes both signals on blend_provenance; the
# joint-gate decision lives in T6 (ENGINE_V2_OBSERVED_ELIGIBILITY_GATE).
#
# Multi-window sign-agreement across {L28, L56, L90} is computed on the
# AOV (Welch) delta direction.
#
# Vertical scope per plan B-5:248: BEAUTY ONLY. Supplements is
# unconditionally vertical-excluded; helper returns (None, None) on
# vertical=="supplements" (mirrors T3 short-circuit pattern; the audience
# builder also short-circuits supplements at audience_builders.py:997-1007).
#
# Helper signature shape: returns
# ``(welch_primary_L28, MultiWindowAgreement)`` --- the 2-tuple matches
# T1/T3/T4 single-channel contract. The z-prop band-share results for
# {L28, L56, L90} are folded into ``MultiWindowAgreement.windows`` under
# synthetic labels ``L28_band`` / ``L56_band`` / ``L90_band`` alongside
# the AOV windows ``L28`` / ``L56`` / ``L90`` so the joint-test consumer
# (T6) can read both p-values off a single channel without breaking the
# T1/T2/T3/T4 single-channel contract.
# ---------------------------------------------------------------------------


def _resolve_aov_bundle_threshold(
    g: pd.DataFrame,
    cfg: Optional[Mapping[str, Any]],
) -> Optional[float]:
    """Re-derive the AOV-bundle threshold T inside the helper.

    Mirrors the resolution order in
    ``audience_builders.aov_lift_via_threshold_bundle_candidates`` under
    flag ``ENGINE_V2_AOV_THRESHOLD_FROM_DATA`` (T7.5 ON in current state):

      1. L90 P60 from data, requires L90 order count >= 200.
      2. cfg["AOV_BUNDLE_THRESHOLD_USD"].
      3. ``None`` (data_missing).

    Returns ``None`` when neither path resolves to a positive value.
    """
    cfgm = dict(cfg or {})
    flag_from_data = bool(cfgm.get("ENGINE_V2_AOV_THRESHOLD_FROM_DATA", True))

    cfg_thr_raw = cfgm.get("AOV_BUNDLE_THRESHOLD_USD")
    try:
        cfg_thr: Optional[float] = (
            float(cfg_thr_raw) if cfg_thr_raw is not None else None
        )
    except (TypeError, ValueError):
        cfg_thr = None
    if cfg_thr is not None and cfg_thr <= 0:
        cfg_thr = None

    if flag_from_data and "Created at" in g.columns and "net_sales" in g.columns:
        try:
            gg = g.copy()
            gg["Created at"] = pd.to_datetime(gg["Created at"], errors="coerce")
            gg = gg[~gg["Created at"].isna()]
            if not gg.empty:
                maxd = gg["Created at"].max()
                l90_start = maxd - pd.Timedelta(days=90)
                gl90 = gg[gg["Created at"] >= l90_start].copy()
                gl90["net_sales"] = pd.to_numeric(gl90["net_sales"], errors="coerce")
                gl90 = gl90[~gl90["net_sales"].isna()]
                if int(len(gl90)) >= 200:
                    p60 = float(np.percentile(gl90["net_sales"].to_numpy(), 60))
                    if p60 > 0:
                        return float(p60)
        except Exception:
            pass

    return cfg_thr


def _aov_bundle_window_cells(
    g: pd.DataFrame,
    *,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    threshold: float,
) -> Tuple[List[float], int, int]:
    """For a window ``[window_start, window_end]``, return:

    - ``aov_values``: per-order net_sales (continuous; fed to Welch-t).
    - ``band_k``: count of orders with net_sales in [0.7T, 0.95T].
    - ``band_n``: total order count in window.

    Honest zero-data: returns ``([], 0, 0)`` on empty / missing columns.
    """
    if "Created at" not in g.columns or "net_sales" not in g.columns:
        return [], 0, 0
    gg = g.copy()
    gg["Created at"] = pd.to_datetime(gg["Created at"], errors="coerce")
    gg = gg[~gg["Created at"].isna()]
    gg = gg[
        (gg["Created at"] >= window_start) & (gg["Created at"] <= window_end)
    ]
    gg["net_sales"] = pd.to_numeric(gg["net_sales"], errors="coerce")
    gg = gg[~gg["net_sales"].isna()]
    if gg.empty:
        return [], 0, 0
    values = gg["net_sales"].astype(float).tolist()
    lower = 0.7 * float(threshold)
    upper = 0.95 * float(threshold)
    band_mask = (gg["net_sales"] >= lower) & (gg["net_sales"] <= upper)
    band_k = int(band_mask.sum())
    band_n = int(len(gg))
    return values, band_k, band_n


def compute_aov_bundle_observed_effect(
    g: Optional[pd.DataFrame],
    *,
    vertical: Optional[str],
    cfg: Optional[Mapping[str, Any]] = None,
) -> Tuple[Optional[ObservedEffectResult], Optional[MultiWindowAgreement]]:
    """Compute multi-window dual-test observed effect for B-5 aov_bundle.

    Returns ``(welch_primary_L28, multi_window_agreement)``.

    The primary L28 result is the WELCH-T result on order-level AOV
    (``method="welch_t"``, ``k=None``). The z-prop band-share results for
    each of {L28, L56, L90} are folded into
    ``MultiWindowAgreement.windows`` under labels
    ``L28_band`` / ``L56_band`` / ``L90_band`` (alongside the AOV windows
    ``L28`` / ``L56`` / ``L90``) so the joint-test eligibility consumer
    (T6) can read both p-values from a single channel.

    Sign-agreement is computed across the AOV (Welch) windows only --- the
    band-share entries are added to the windows map AFTER agreement
    computation so they do not double-count toward sign-agreement.

    Supplements: returns ``(None, None)`` per plan B-5:248 vertical
    exclusion (mirrors the builder-side gate at
    audience_builders.py:997-1007).

    Honest zero-data: returns ``(None, None)`` when ``g`` is empty,
    required columns are missing, or the threshold cannot be resolved.
    """
    if g is None or g.empty:
        return None, None
    if "Created at" not in g.columns or "net_sales" not in g.columns:
        return None, None
    v = (vertical or "").strip().lower()
    if v == "supplements":
        return None, None

    gg = g.copy()
    gg["Created at"] = pd.to_datetime(gg["Created at"], errors="coerce")
    gg = gg[~gg["Created at"].isna()]
    if gg.empty:
        return None, None

    threshold = _resolve_aov_bundle_threshold(gg, cfg)
    if threshold is None or threshold <= 0:
        return None, None

    maxd = gg["Created at"].max()
    if pd.isna(maxd):
        return None, None

    windows = ("L28", "L56", "L90")
    window_days = {"L28": 28, "L56": 56, "L90": 90}

    welch_per_window: Dict[str, ObservedEffectResult] = {}
    band_per_window: Dict[str, ObservedEffectResult] = {}
    primary: Optional[ObservedEffectResult] = None

    for w in windows:
        W = window_days[w]
        recent_start = maxd - pd.Timedelta(days=W)
        recent_end = maxd
        prior_start = maxd - pd.Timedelta(days=2 * W)
        prior_end = recent_start

        recent_vals, recent_band_k, recent_band_n = _aov_bundle_window_cells(
            gg, window_start=recent_start, window_end=recent_end, threshold=threshold,
        )
        prior_vals, prior_band_k, prior_band_n = _aov_bundle_window_cells(
            gg, window_start=prior_start, window_end=prior_end, threshold=threshold,
        )

        welch_res = compute_welch_t_observed(recent_vals, prior_vals)
        band_res = compute_two_proportion_observed(
            recent_band_k, recent_band_n, prior_band_k, prior_band_n,
        )

        welch_per_window[w] = welch_res
        band_per_window[w] = band_res
        if w == "L28":
            primary = welch_res

    # Sign-agreement on the AOV (Welch) windows only.
    agreement = compute_multi_window_sign_agreement(welch_per_window)

    # Fold band-share results in under synthetic labels so the joint-test
    # consumer (T6) can read both p-values off the single stash channel.
    combined_windows: Dict[str, ObservedEffectResult] = dict(agreement.windows or {})
    for w, res in band_per_window.items():
        combined_windows[f"{w}_band"] = res

    agreement = MultiWindowAgreement(
        sign_agreement_count=int(agreement.sign_agreement_count),
        dominant_sign=int(agreement.dominant_sign),
        windows=combined_windows,
    )
    return primary, agreement


def build_prior_anchored_play_card(
    candidate: Any,
    aligned: Optional[Dict[str, Any]],
    *,
    vertical: Optional[str] = None,
    subvertical: Optional[str] = None,
    primary_window: str = "L28",
    observed_k: int = 0,
    observed_n: int = 0,
    store_profile: Optional[Any] = None,
    profile_flag_on: bool = False,
    orders_df: Optional[pd.DataFrame] = None,
    observed_effect_enabled: bool = False,
    observed_replenishment_enabled: bool = False,
    observed_discount_hygiene_enabled: bool = False,
    observed_journey_enabled: bool = False,
    observed_aov_bundle_enabled: bool = False,
    cfg: Optional[Mapping[str, Any]] = None,
) -> Optional[PlayCard]:
    """Build a PlayCard whose posterior is anchored on a typed prior.

    Returns:
        A typed :class:`PlayCard`. When the resolved prior is
        ``validated_*`` / ``elicited_expert``, ``revenue_range`` is
        non-suppressed with ``source=BLEND`` and a ``blend_provenance``
        driver. When the prior is ``heuristic_unvalidated`` /
        ``placeholder``, the PlayCard's ``revenue_range`` is suppressed
        with a ``prior_unvalidated`` driver so decide.py's
        ``_route_prior_unvalidated_holds`` re-routes the card into
        Considered with :data:`ReasonCode.PRIOR_UNVALIDATED`.

    Returns ``None`` when the candidate is not in the supported set, has
    not cleared the audience floor, or the prior is missing entirely
    (e.g. mixed-vertical KI-19 conservative-min refusal).

    Cold-start posture: when ``observed_k = observed_n = 0`` (default)
    the Bayesian posterior collapses to the prior. The
    ``blend_provenance`` block reports this honestly via
    ``store_data_status = "no_outcome_history"`` and
    ``posterior_ratio = "prior_dominant"``.
    """

    if candidate is None:
        return None

    play_id = str(getattr(candidate, "play_id", "") or "")
    cfg_entry = _PRIOR_ANCHORED.get(play_id)
    if cfg_entry is None:
        return None

    if getattr(candidate, "preliminary_rejection_reason", None):
        return None

    audience_size = _safe_int(getattr(candidate, "audience_size", None)) or 0
    if audience_size <= 0:
        return None

    # Sprint 6.5 Ticket T4 — profile-driven primary_window + agreement_windows.
    # When flag is OFF or profile is None, behavior is byte-identical
    # to today's prior-anchored pathway (primary_window param wins).
    agreement_windows: List[str] = [w for w in PHASE5_WINDOWS if w != primary_window]
    if profile_flag_on and store_profile is not None:
        meas_ctx = getattr(store_profile, "measurement", None)
        if meas_ctx is not None:
            primary_window = str(getattr(meas_ctx, "primary_window", primary_window))
            aw = list(getattr(meas_ctx, "agreement_windows", []) or [])
            if aw:
                agreement_windows = [w for w in aw if w != primary_window]

    # Resolve the prior. Mixed vertical routes through resolve_mixed_prior
    # so KI-19 conservative-min applies (heuristic_unvalidated wins the
    # blend's validation_status when either side is unvalidated).
    from .priors_loader import (
        PriorValidationStatus,
        get_prior,
        resolve_mixed_prior,
    )
    from .sizing import PSEUDO_N_BY_STATUS, bayesian_blend

    v = (vertical or "").strip().lower() or None
    if v == "mixed":
        prior = resolve_mixed_prior(
            cfg_entry.prior_play_id, key=cfg_entry.prior_key
        )
    else:
        prior = get_prior(
            cfg_entry.prior_play_id,
            vertical=v,
            subvertical=subvertical,
            key=cfg_entry.prior_key,
        )
    if prior is None:
        return None

    # AOV for revenue range. Reuse the directional builder's resolver.
    resolved_aov = _resolve_aov_for_context(aligned, primary_window=primary_window)
    aov_val: Optional[float] = resolved_aov[0] if resolved_aov else None

    # Sprint 7.6 Ticket T1 — B-1 winback observed-effect wiring.
    # When ``observed_effect_enabled=True`` (set by main.py only when
    # ``ENGINE_V2_OBSERVED_EFFECT_WINBACK`` is ON) and ``orders_df`` is
    # provided, compute the per-store lapse_recovery_rate observed effect
    # on the SAME dormant-cohort rule the M3 builder uses, across
    # {L28, L56, L90} anchors, and thread the primary (L28) (k, n) into
    # the Bayesian blend below. The multi-window sign-agreement is
    # stashed on the blend_provenance driver for downstream eligibility-
    # gate / copy-ladder consumers (T6).
    #
    # Flag-OFF / orders_df-None path: ``observed_k`` / ``observed_n`` are
    # taken straight from caller defaults (0/0 cold-start) and the
    # posterior collapses to the prior — byte-identical to today.
    # ``observed_agreement`` is the single multi-window sign-agreement
    # stash channel for the prior-anchored card seam. Whichever per-play
    # observed-effect path runs (winback / replenishment / future Tier-B)
    # writes into it; the blend_provenance emit step below reads it once.
    observed_agreement: Optional[MultiWindowAgreement] = None
    if (
        observed_effect_enabled
        and orders_df is not None
        and play_id == "winback_dormant_cohort"
    ):
        try:
            primary_obs, observed_agreement = compute_winback_observed_effect(
                orders_df, vertical=vertical
            )
        except Exception:
            primary_obs = None
            observed_agreement = None
        if primary_obs is not None and primary_obs.n > 0 and primary_obs.k is not None:
            observed_k = int(primary_obs.k)
            observed_n = int(primary_obs.n)

    # Sprint 7.6 Ticket T2 — B-2 replenishment_due observed-effect wiring.
    # Independent enable kwarg ``observed_replenishment_enabled`` is set
    # by main.py only when ``ENGINE_V2_OBSERVED_EFFECT_REPLENISHMENT`` is
    # ON. Beauty-only at T2; helper short-circuits supplements (KI-27).
    # Flag-OFF / orders_df-None path: cold-start (0/0) remains in force.
    if (
        observed_replenishment_enabled
        and orders_df is not None
        and play_id == "replenishment_due"
    ):
        try:
            primary_obs_r, replenish_agreement = compute_replenishment_observed_effect(
                orders_df, vertical=vertical
            )
        except Exception:
            primary_obs_r = None
            replenish_agreement = None
        if (
            primary_obs_r is not None
            and primary_obs_r.n > 0
            and primary_obs_r.k is not None
        ):
            observed_k = int(primary_obs_r.k)
            observed_n = int(primary_obs_r.n)
        if replenish_agreement is not None:
            observed_agreement = replenish_agreement

    # Sprint 7.6 Ticket T3 — B-3 discount_dependency_hygiene observed-effect
    # wiring. Independent enable kwarg ``observed_discount_hygiene_enabled``
    # is set by main.py only when ``ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE``
    # is ON. Beauty-only at T3; helper short-circuits supplements per DS
    # Memo-4 REJECT (Path-D dormant). Flag-OFF / orders_df-None path: cold-
    # start (0/0) remains in force, byte-identical to today.
    if (
        observed_discount_hygiene_enabled
        and orders_df is not None
        and play_id == "discount_dependency_hygiene"
    ):
        try:
            primary_obs_d, discount_agreement = compute_discount_hygiene_observed_effect(
                orders_df, vertical=vertical
            )
        except Exception:
            primary_obs_d = None
            discount_agreement = None
        if (
            primary_obs_d is not None
            and primary_obs_d.n > 0
            and primary_obs_d.k is not None
        ):
            observed_k = int(primary_obs_d.k)
            observed_n = int(primary_obs_d.n)
        if discount_agreement is not None:
            observed_agreement = discount_agreement

    # Sprint 7.6 Ticket T4 — B-4 cohort_journey_first_to_second observed-effect
    # wiring. Independent enable kwarg ``observed_journey_enabled`` is set by
    # main.py only when ``ENGINE_V2_OBSERVED_EFFECT_JOURNEY`` is ON. Vertical
    # scope per plan B-4: applies to "*" (all verticals). Helper enforces the
    # Berkson invariant (early-half-window cohort denominators only) — see
    # tests/test_berkson_invariant.py + project_journey_p_zero.md memory
    # 2026-04-30. Flag-OFF / orders_df-None path: cold-start (0/0) remains
    # in force, byte-identical to today.
    if (
        observed_journey_enabled
        and orders_df is not None
        and play_id == "cohort_journey_first_to_second"
    ):
        try:
            primary_obs_j, journey_agreement = compute_journey_first_to_second_observed_effect(
                orders_df, vertical=vertical
            )
        except Exception:
            primary_obs_j = None
            journey_agreement = None
        if (
            primary_obs_j is not None
            and primary_obs_j.n > 0
            and primary_obs_j.k is not None
        ):
            observed_k = int(primary_obs_j.k)
            observed_n = int(primary_obs_j.n)
        if journey_agreement is not None:
            observed_agreement = journey_agreement

    # Sprint 7.6 Ticket T5 --- B-5 aov_lift_via_threshold_bundle observed-effect
    # wiring. Independent enable kwarg ``observed_aov_bundle_enabled`` is set
    # by main.py only when ``ENGINE_V2_OBSERVED_EFFECT_AOV_BUNDLE`` is ON.
    # Vertical scope per plan B-5:248: BEAUTY ONLY. Helper short-circuits
    # supplements. Dual statistical test --- Welch-t on order-level AOV +
    # two-proportion z-test on near-threshold band share, BOTH must reach
    # p<0.10 jointly to drive T6 eligibility (T6 reads the stash; T5 only
    # computes + stashes). Flag-OFF / orders_df-None path: cold-start (0/0)
    # remains in force, byte-identical to today.
    #
    # Blend channel: Welch primary has ``k=None`` (continuous metric);
    # the existing card-seam guard at L1858 requires ``primary.k is not
    # None`` to thread ``observed_k`` / ``observed_n``. We use the L28
    # band-share cell counts (folded into the agreement payload under
    # ``L28_band``) as the blend channel proxy --- this mirrors T3's
    # revenue-weighted-counts-as-blend pattern.
    if (
        observed_aov_bundle_enabled
        and orders_df is not None
        and play_id == "aov_lift_via_threshold_bundle"
    ):
        try:
            primary_obs_a, aov_bundle_agreement = compute_aov_bundle_observed_effect(
                orders_df, vertical=vertical, cfg=cfg,
            )
        except Exception:
            primary_obs_a = None
            aov_bundle_agreement = None
        if aov_bundle_agreement is not None:
            observed_agreement = aov_bundle_agreement
            # Thread the band-share L28 (k, n) into the blend channel.
            l28_band = (aov_bundle_agreement.windows or {}).get("L28_band")
            if (
                l28_band is not None
                and l28_band.n > 0
                and l28_band.k is not None
            ):
                observed_k = int(l28_band.k)
                observed_n = int(l28_band.n)

    # Pull store-observed reactivation, if any. Cold start (no flag, no
    # outcome data) keeps ``observed_k = observed_n = 0`` and posterior
    # = prior.
    obs_k = max(0, int(observed_k or 0))
    obs_n = max(0, int(observed_n or 0))
    store_value: float = 0.0
    if obs_n > 0:
        store_value = float(obs_k) / float(obs_n)
    else:
        # Cold-start: posterior collapses to prior. Pass store_value =
        # prior_value so bayesian_blend reduces to the prior even with a
        # non-zero pseudo_n.
        store_value = float(prior.value)

    # Sprint 6.5 Ticket T4: route through ``effective_pseudo_n`` so the
    # profile cap (when flag is ON) lowers the validated-path weight.
    # Per-status caps from ``PSEUDO_N_BY_STATUS`` still apply as the
    # ceiling; profile cannot raise above them (Part III-1 pseudo_N
    # policy invariant). S7.5-T3 validated-vs-heuristic refusal logic
    # is unchanged: heuristic_unvalidated / placeholder still get
    # pseudo_n=0 from the helper (they refuse outright at the routing
    # seam below, not via the blend weight).
    from .sizing import effective_pseudo_n
    pseudo_n = effective_pseudo_n(
        prior.validation_status,
        store_profile=store_profile,
        profile_flag_on=profile_flag_on,
    )
    pseudo_n_source: Optional[str] = None
    if profile_flag_on and store_profile is not None:
        gc = getattr(store_profile, "gate_calibration", None)
        if gc is not None:
            pseudo_n_source = (gc.profile_field_refs or {}).get("pseudo_n_default")

    posterior = bayesian_blend(
        prior_value=float(prior.value),
        pseudo_n=int(pseudo_n),
        store_value=float(store_value),
        n_observed=obs_n,
    )

    audience = Audience(
        id=f"s6_t1_{play_id}",
        definition=getattr(candidate, "segment_definition", None)
        or "dormant repeat-buyer cohort",
        size=audience_size,
        fraction_of_base=None,
        # S-FE-descriptive-distribution (L-EV-19): bind the discarded builder
        # series (dormancy / AOV-gap / reorder-gap / discount-fraction) into
        # the typed atom for the 4 distributional plays; None for any other
        # prior-anchored play (no kind stashed). DESCRIPTIVE-ONLY (L-EV-20).
        descriptive_distribution=_maybe_build_descriptive_distribution(candidate),
    )

    # Sprint 6.5 Ticket T4 (R1) — prior-anchored window_corroboration
    # (closes the DS architect §1 asymmetry vs. the directional pathway).
    window_corroboration: Optional[WindowCorroboration] = None
    if profile_flag_on:
        window_corroboration = _prior_anchored_window_corroboration(
            aligned,
            metric=cfg_entry.metric,
            primary_window=primary_window,
            agreement_windows=agreement_windows,
        )

    measurement = Measurement(
        metric=cfg_entry.metric,
        observed_effect=None,  # No observed effect at T1.5 cold start.
        n=audience_size,  # Cohort size — the directional signal itself.
        primary_window=primary_window,
        consistency_across_windows=None,
        p_internal=None,
        window_corroboration=window_corroboration,
    )

    blend_provenance: Dict[str, Any] = {
        "name": "blend_provenance",
        "source": "bayesian_blend",
        "prior_value": round(float(prior.value), 6),
        "prior_source_class": prior.source_class,
        "prior_validation_status": prior.validation_status.value,
        "prior_source_artifact": prior.source_artifact,
        "prior_effective_n": prior.effective_n,
        "pseudo_n": int(pseudo_n),
        "observed_k": obs_k,
        "observed_n": obs_n,
        "store_data_status": (
            "no_outcome_history" if obs_n == 0 else "store_outcomes_observed"
        ),
        "posterior_value": round(float(posterior), 6),
        "posterior_ratio": (
            "prior_dominant" if obs_n < pseudo_n else "store_dominant"
        ),
        "expected_calibration_path": "phase_9_outcome_loop",
        "applies_to": dict(prior.applies_to or {}),
    }
    if pseudo_n_source is not None:
        # Sprint 6.5 Ticket T4: cite the profile field path on the
        # blend_provenance driver so reviewers can trace cold-start
        # weight back to ``profile.gate_calibration.pseudo_n_default``.
        blend_provenance["profile_field_ref"] = pseudo_n_source

    # Sprint 7.6 Ticket T1 — stash multi-window sign-agreement on the
    # blend_provenance driver when the observed-effect path computed it.
    # Consumed by T6 eligibility gate / copy ladder. Emitted only when
    # we actually ran the observed-effect path (flag ON + orders_df) so
    # the cold-start serialization stays byte-identical at flag-OFF.
    if observed_agreement is not None:
        blend_provenance["observed_sign_agreement_count"] = int(
            observed_agreement.sign_agreement_count
        )
        blend_provenance["observed_dominant_sign"] = int(
            observed_agreement.dominant_sign
        )
        blend_provenance["observed_windows"] = {
            w: {
                "k": (None if r.k is None else int(r.k)),
                "n": int(r.n),
                "effect": (None if r.effect is None else round(float(r.effect), 6)),
                "p_value": (
                    None if r.p_value is None else round(float(r.p_value), 6)
                ),
                "sign": int(r.sign),
                "method": r.method,
            }
            for w, r in (observed_agreement.windows or {}).items()
        }

        # S7.6-CLI-FIX (DS verdict 2026-05-23,
        # agent_outputs/ecommerce-ds-architect-s7_6-cli-wiring-gap-verdict-2026-05-23.md):
        # Surface the primary-window observed-effect numerics on the
        # canonical typed Measurement slot so engine_run.json receipts
        # carry them on Tier-B Recommended cards. The data was already
        # being computed and stashed in ``blend_provenance.observed_windows``;
        # the typed Measurement slot was reading ``None`` because the
        # prior-anchored builder constructed Measurement above (line 2189)
        # before observed_agreement was available. ``drivers[]`` remains
        # the source of truth for downstream decide.py consumers; this
        # only mirrors the primary-window numerics into the canonical
        # receipt slot (3 fields per DS verdict §2, no more, no less).
        primary_obs_result = (observed_agreement.windows or {}).get(primary_window)
        if primary_obs_result is not None and int(primary_obs_result.n) > 0:
            if primary_obs_result.effect is not None:
                measurement.observed_effect = round(float(primary_obs_result.effect), 6)
            measurement.n = int(primary_obs_result.n)
            if primary_obs_result.p_value is not None:
                measurement.p_internal = round(float(primary_obs_result.p_value), 6)

    # Sprint 6.5 Ticket T4: audience-floor citation. When the flag is ON
    # and the profile carries a per-play floor for this play_id, emit
    # the YAML cell-path so reviewers can trace the floor back to
    # gate_calibration.yaml. Empty string when not profile-driven.
    audience_floor_ref: Optional[str] = None
    if profile_flag_on and store_profile is not None:
        gc = getattr(store_profile, "gate_calibration", None)
        if gc is not None:
            audience_floor_ref = (gc.profile_field_refs or {}).get(
                f"audience_floor.{play_id}"
            )

    # Routing on validation_status (Sprint 7.5 contract):
    blend_permitted = prior.validation_status in PSEUDO_N_BY_STATUS

    # S13.6-T1a (Option D): engine-authored ``why_now`` stripped per
    # Pivot 2. Window-text dispatch and per-play ``direction_window``
    # selection are retired with it. Downstream narration recomposes
    # window framing from typed Audience.size + Audience.definition +
    # priors metadata + the per-play mechanism_text.

    if not blend_permitted:
        # Heuristic_unvalidated / placeholder → suppressed range with
        # ``prior_unvalidated`` reason. decide.py's
        # ``_route_prior_unvalidated_holds`` will move this PlayCard
        # into Considered with PRIOR_UNVALIDATED.
        drivers: List[Dict[str, Any]] = [
            _audience_size_driver(audience_size, audience_floor_ref),
            blend_provenance,
            {
                "name": "suppression_reason",
                "source": "measurement_builder_v2",
                "value": "prior_unvalidated",
                "reason": "prior_unvalidated",
                "rationale": (
                    "prior validation_status is "
                    f"{prior.validation_status.value}; refusing to anchor a "
                    "merchant-facing dollar projection on an unvalidated "
                    "benchmark per Sprint 7.5 contract"
                ),
            },
        ]
        # S13.6-T7a: paired ``suppression_reason`` wraps the existing
        # producer string ``"prior_unvalidated"`` at the seam per DS Q1.
        from .engine_run import RevenueRangeSuppressionReason as _RRSR_PU
        revenue_range = RevenueRange(
            p10=None, p50=None, p90=None,
            source=None,
            drivers=drivers,
            suppressed=True,
            suppression_reason=_RRSR_PU.PRIOR_UNVALIDATED,
        )
    else:
        # Validated → non-suppressed, BLEND-sourced range.
        if aov_val is None or aov_val <= 0:
            # AOV missing — cannot project dollars. Suppress, but with a
            # store-side reason (not prior_unvalidated) so the play is
            # NOT routed to PRIOR_UNVALIDATED.
            drivers = [
                _audience_size_driver(audience_size, audience_floor_ref),
                blend_provenance,
                {
                    "name": "suppression_reason",
                    "source": "measurement_builder_v2",
                    "value": "aov_unavailable",
                    "reason": "aov_unavailable",
                },
            ]
            # S13.6-T7a: paired ``suppression_reason`` wraps the
            # existing producer string ``"aov_unavailable"`` at the
            # seam per DS Q1.
            from .engine_run import RevenueRangeSuppressionReason as _RRSR_AU
            revenue_range = RevenueRange(
                p10=None, p50=None, p90=None,
                source=None,
                drivers=drivers,
                suppressed=True,
                suppression_reason=_RRSR_AU.AOV_UNAVAILABLE,
            )
        else:
            p10 = max(0.0, float(prior.range_p10))
            p50 = float(posterior)
            p90 = max(p50, float(prior.range_p90))
            rev_p10 = round(audience_size * p10 * aov_val, 2)
            rev_p50 = round(max(rev_p10, audience_size * p50 * aov_val), 2)
            rev_p90 = round(max(rev_p50, audience_size * p90 * aov_val), 2)
            drivers = [
                _audience_size_driver(audience_size, audience_floor_ref),
                {"name": "aov", "source": "store_observed", "value": round(aov_val, 2), "window": resolved_aov[1]},
                blend_provenance,
            ]
            # Sprint 6 Ticket T3.y — audience-floor sensitivity driver on
            # validated-path prior-anchored PlayCards. Closes the DS
            # architect 2026-05-19 firewall leak: the floor heuristic
            # uncertainty silently inheriting into the dollar projection
            # is now surfaced as a typed envelope.
            #
            # Flag-OFF guards (mirror _audience_size_driver discipline):
            # only emit when the profile flag is ON, a profile is
            # attached, the audience-floor profile_field_ref is cited
            # (i.e. the floor came from profile.gate_calibration, not a
            # hardcoded default), AND we can recover the floor scalar
            # from the profile. Any missing piece → omit entirely so the
            # flag-OFF / no-profile path stays byte-identical.
            if (
                profile_flag_on
                and store_profile is not None
                and audience_floor_ref
                and prior.validation_status == PriorValidationStatus.VALIDATED_EXTERNAL
            ):
                gc = getattr(store_profile, "gate_calibration", None)
                floor_val: Optional[int] = None
                if gc is not None:
                    floor_by_play = getattr(gc, "audience_floor_by_play_id", None) or {}
                    raw_floor = floor_by_play.get(play_id)
                    if raw_floor is not None:
                        try:
                            floor_val = int(raw_floor)
                        except (TypeError, ValueError):
                            floor_val = None
                if floor_val is not None and floor_val > 0:
                    drivers.append(
                        _audience_floor_sensitivity_driver(
                            audience_size=int(audience_size),
                            audience_floor=int(floor_val),
                            posterior_value=float(posterior),
                            aov=float(aov_val),
                            profile_field_ref=audience_floor_ref,
                        )
                    )
            revenue_range = RevenueRange(
                p10=rev_p10, p50=rev_p50, p90=rev_p90,
                source=RevenueRangeSource.BLEND,
                drivers=drivers,
                suppressed=False,
            )

    opportunity_context = _build_opportunity_context(
        audience_size, aligned, primary_window=primary_window
    )

    # S8-T1: typed EvidenceSourceChip population. The prior-anchored
    # builder serves all 4 wired Tier-B plays (winback_dormant_cohort,
    # discount_dependency_hygiene, cohort_journey_first_to_second,
    # aov_lift_via_threshold_bundle) plus the dormant-by-design
    # replenishment_due (KI-NEW-G honest-dormancy preserved; the
    # dormant path returns no card so no chip is emitted in practice).
    # Every card emitted here is Tier-B by construction; chip is
    # ``STORE_OBSERVED`` when ``ENGINE_V2_TIER_CHIP`` is ON, ``None``
    # otherwise (preserves M0 + Beauty + Supplements byte-identity at
    # flag OFF default; T1.5 atomic flip flips ON with fixture re-pin).
    evidence_source: Optional[EvidenceSourceChip] = None
    if cfg is not None and bool(cfg.get("ENGINE_V2_TIER_CHIP", False)):
        evidence_source = EvidenceSourceChip.STORE_OBSERVED

    # S8-T2: typed Sensitivity block population. Independent flag from
    # the chip per DS Q7 verdict 2026-05-24 §4 (separate
    # ``ENGINE_V2_SENSITIVITY``; atomic T2.5 flip ships separately).
    # Only emits on the validated, non-suppressed BLEND path — i.e.
    # ``revenue_range.source == BLEND`` AND ``not revenue_range.suppressed``
    # (mirrors IM plan Part B S8-T2 acceptance criterion 2: suppressed
    # cards + targeting cards leave the field ``None``). The helper at
    # :func:`src.sizing.compute_sensitivity` reuses the same
    # :func:`bayesian_blend` + ``audience * posterior * aov`` math the
    # live revenue_range uses; no parallel sizing math.
    sensitivity: Optional[Sensitivity] = None
    if (
        cfg is not None
        and bool(cfg.get("ENGINE_V2_SENSITIVITY", False))
        and revenue_range is not None
        and revenue_range.source == RevenueRangeSource.BLEND
        and not revenue_range.suppressed
        and aov_val is not None
        and aov_val > 0.0
        and audience_size > 0
    ):
        from .sizing import compute_sensitivity
        sensitivity = compute_sensitivity(
            prior_value=float(prior.value),
            prior_range_p10=float(prior.range_p10),
            prior_range_p90=float(prior.range_p90),
            pseudo_n=int(pseudo_n),
            store_value=float(store_value),
            n_observed=int(obs_n),
            audience_size=int(audience_size),
            aov=float(aov_val),
        )

    # S8-T3: typed Provenance audit object population. Independent flag
    # from chip/sensitivity per S7.6 atomic-flip discipline
    # (``ENGINE_V2_EB_BLEND``; default OFF; T3.5 atomic flip is a
    # separate dispatch). Only emits on the validated, non-suppressed
    # BLEND path — i.e. ``revenue_range.source == BLEND`` AND
    # ``not revenue_range.suppressed``. HEURISTIC_UNVALIDATED +
    # PLACEHOLDER priors land on the suppressed path so the gate below
    # naturally enforces DS §5 invariant 2 (refusal): no audit object
    # for a refused status. The helper at
    # :func:`src.sizing.compute_provenance` reuses
    # :func:`effective_pseudo_n` + :data:`PSEUDO_N_BY_STATUS` — no new
    # pseudo_N policy, no parallel blend math. THIRD and final S8
    # additive PlayCard field per DS verdict 2026-05-24 §5 invariant 12.
    provenance: Optional[Provenance] = None
    if (
        cfg is not None
        and bool(cfg.get("ENGINE_V2_EB_BLEND", False))
        and revenue_range is not None
        and revenue_range.source == RevenueRangeSource.BLEND
        and not revenue_range.suppressed
    ):
        from .sizing import compute_provenance
        provenance = compute_provenance(
            prior=prior,
            prior_key=str(cfg_entry.prior_key),
            observed_n=int(obs_n),
            store_profile=store_profile,
            profile_flag_on=profile_flag_on,
        )

    # S13.6-T6: typed MechanismIntent atom. Lazy import keeps
    # decide.py -> measurement_builder.py ordering clean.
    from .decide import _build_mechanism_intent as _build_mech_intent
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.DIRECTIONAL,
        confidence_label="Emerging",
        # S13.6-T1a: ``recommendation_text`` / ``why_now`` stripped.
        audience=audience,
        measurement=measurement,
        revenue_range=revenue_range,
        inventory=None,
        conflicts=None,
        launch_window=None,
        opportunity_context=opportunity_context,
        would_be_measured_by=cfg_entry.would_be_measured_by,
        # S13.6-T2: klaviyo_brief_inputs removed (founder lock-in #6).
        receipts_ref=None,
        evidence_source=evidence_source,
        sensitivity=sensitivity,
        provenance=provenance,
        # S13.6-T6: typed MechanismIntent atom; None for unmapped play_ids.
        mechanism_intent=_build_mech_intent(play_id),
    )


def build_prior_anchored_recommendations(
    candidates: Iterable[Any],
    aligned: Optional[Dict[str, Any]],
    *,
    vertical: Optional[str] = None,
    subvertical: Optional[str] = None,
    existing_recommendation_ids: Iterable[str] = (),
    primary_window: str = "L28",
    store_profile: Optional[Any] = None,
    profile_flag_on: bool = False,
    allowed_play_ids: Optional[Iterable[str]] = None,
    orders_df: Optional[pd.DataFrame] = None,
    observed_effect_enabled: bool = False,
    observed_replenishment_enabled: bool = False,
    observed_discount_hygiene_enabled: bool = False,
    observed_journey_enabled: bool = False,
    observed_aov_bundle_enabled: bool = False,
    cfg: Optional[Mapping[str, Any]] = None,
) -> List[PlayCard]:
    """Iterate candidates and emit prior-anchored PlayCards (S6-T1).

    Mirrors :func:`build_directional_recommendations` but for the Tier-B
    cohort-existence pathway. Caller threads ``vertical`` / ``subvertical``
    so the prior lookup honors the run's scope.

    Sprint 6.5 Ticket T4: ``store_profile`` + ``profile_flag_on`` are
    forwarded so the prior-anchored pathway emits R1
    ``window_corroboration`` (closing the DS architect §1 asymmetry)
    and so the R2 cadence-derived ``primary_window`` overrides the
    caller's default under flag-ON.
    """

    existing = {str(p) for p in existing_recommendation_ids or []}
    allowed: Optional[set] = (
        {str(p) for p in allowed_play_ids} if allowed_play_ids is not None else None
    )
    out: List[PlayCard] = []
    for cand in candidates or []:
        play_id = str(getattr(cand, "play_id", "") or "")
        if not play_id or play_id in existing:
            continue
        if play_id not in _PRIOR_ANCHORED:
            continue
        if allowed is not None and play_id not in allowed:
            continue
        card = build_prior_anchored_play_card(
            cand,
            aligned,
            vertical=vertical,
            subvertical=subvertical,
            primary_window=primary_window,
            store_profile=store_profile,
            profile_flag_on=profile_flag_on,
            orders_df=orders_df,
            observed_effect_enabled=observed_effect_enabled,
            observed_replenishment_enabled=observed_replenishment_enabled,
            observed_discount_hygiene_enabled=observed_discount_hygiene_enabled,
            observed_journey_enabled=observed_journey_enabled,
            observed_aov_bundle_enabled=observed_aov_bundle_enabled,
            cfg=cfg,
        )
        if card is not None:
            out.append(card)
    return out


def build_directional_recommendations(
    candidates: Iterable[Any],
    aligned: Optional[Dict[str, Any]],
    *,
    existing_recommendation_ids: Iterable[str] = (),
    primary_window: str = "L28",
    store_profile: Optional[Any] = None,
    profile_flag_on: bool = False,
) -> List[PlayCard]:
    """Iterate candidates and produce 0+ directional PlayCards.

    Phase 5.6 keeps the surface conservative: only one play wired
    today. The function is the call-site entry point used by main.py.

    Sprint 6.5 Ticket T4: ``store_profile`` + ``profile_flag_on`` are
    forwarded to ``build_directional_play_card`` so R1
    ``window_corroboration`` is emitted under flag-ON and the R2
    cadence-derived ``primary_window`` overrides the caller's default.
    """

    existing = {str(p) for p in existing_recommendation_ids or []}
    out: List[PlayCard] = []
    for cand in candidates or []:
        play_id = str(getattr(cand, "play_id", "") or "")
        if not play_id:
            continue
        if play_id in existing:
            continue
        if play_id not in _SUPPORTED:
            continue
        card = build_directional_play_card(
            cand,
            aligned,
            primary_window=primary_window,
            store_profile=store_profile,
            profile_flag_on=profile_flag_on,
        )
        if card is not None:
            out.append(card)
    return out


__all__ = [
    "PHASE5_DIRECTIONAL_P_MAX",
    "PHASE5_DIRECTIONAL_MIN_CONSISTENCY",
    "PHASE5_WINDOWS",
    "build_directional_play_card",
    "build_directional_recommendations",
    "build_prior_anchored_play_card",
    "build_prior_anchored_recommendations",
]
