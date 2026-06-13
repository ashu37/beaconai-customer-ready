"""PlayCard consumer wiring (Sprint 13 — T2).

Post-injection mutation pass that populates
:attr:`src.engine_run.PlayCard.predicted_segment` and
:attr:`src.engine_run.PlayCard.model_card_ref` on the cards already
present on ``engine_run.recommendations``. Pure attribute mutation —
**no append to ``engine_run.recommendations``** — so the Pivot 7
single-demote-channel invariant is structurally preserved (this pass
cannot demote, route, drop, or re-order cards; it only writes to two
``Optional[...]`` typed slots that today read ``None``).

Wire location (decision recorded in
``agent_outputs/code-refactor-engineer-s13-t2-summary.md``)
=========================================================

Option II — post-injection wire at ``src/main.py`` AFTER
``apply_guardrails_to_injected`` (~L1970) and BEFORE
``_populate_considered``. Chosen over Option I (factory threading)
because the audience customer-ID set is NOT carried by the
:class:`src.detect.Candidate` object passed into
``build_prior_anchored_play_card`` — the IDs live on the
``AudienceBuildResult`` produced by the audience-builder registry
(:func:`src.audience_builders._get_audience_builder`). Re-resolving
the audience IDs from a re-run of the per-play builder mirrors the
existing cannibalization-overlap recompute at
``src/main.py:1937-1954`` (same pattern, same call).

This module is the SINGLE producer authorized to populate
``PlayCard.predicted_segment`` and ``PlayCard.model_card_ref`` at S13.
The orchestration callsite at ``src/main.py`` reads
``ENGINE_V2_PLAY_PREDICTED_SEGMENT`` and skips the call when OFF —
producing the byte-identical baseline by construction.

Flag contract
=============

- ``ENGINE_V2_PLAY_PREDICTED_SEGMENT=false`` (default at T2):
  :func:`populate_play_card_consumers` is NOT called from ``main.py``.
  ``PlayCard.predicted_segment`` and ``PlayCard.model_card_ref`` stay
  ``None`` on every card — exactly the S12-close shape.
- ``ENGINE_V2_PLAY_PREDICTED_SEGMENT=true`` (T2.5 atomic flip):
  :func:`populate_play_card_consumers` runs on every recommendation
  card. ``engine_run.json`` shape diverges from S12-close in a
  confined way (PlayCard ``predicted_segment`` + ``model_card_ref``
  keys only); ``briefing.html`` byte-identical (renderer
  non-consumption pinned at T2.5).

Q-S13-4 LOCK (DS verdict 2026-05-28, S13 plan review §B):
ML-fit ReasonCodes (``MODEL_FIT_INSUFFICIENT_DATA``,
``MODEL_FIT_REFUSED``) emit ONLY via the typed ``fit_warnings``
``List[FitWarning]`` (S13.6-T4 / D-S13-4) on
:class:`src.engine_run.ModelCardRef`. **NEVER on
``RejectedPlay.reason_code``**. This module writes the fit_warnings
list directly from the :class:`src.predictive.ranking_strategy.RankingStrategyResult`
returned by :func:`src.predictive.ranking_strategy.rank_audience`;
nothing here appends to ``engine_run.considered`` or sets any
``ReasonCode``.

Modal-segment stability floor (DS-LOCKED §D.4)
==============================================

When the audience modal segment is computable from the per-store RFM
parquet artifact, the rule is:

- ``segment_name = None`` when ``n_audience < 50`` OR
  ``audience_modal_share < 0.30``.
- ``n_audience`` and ``audience_modal_share`` are **always** populated
  when computation succeeds — operator-visible audit even when the
  surfaced name suppresses.

Rationale: RFM segments below 50 customers are statistically unstable
per S12 ``absolute_customers_floor``; below 30% modal share the audience
is segment-heterogeneous and a single-name claim would mislead.
"""

from __future__ import annotations

from dataclasses import replace as _dc_replace
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd

from src.engine_run import (
    EngineRun,
    ModelCardRef,
    PlayCard,
    PredictedSegment,
    PredictedSegmentNullReason,
)
from src.predictive.model_card import ModelCard, ModelFitStatus
from src.predictive.ranking_strategy import (
    AudienceIntent,
    RankingStrategyResult,
    rank_audience,
)


# ---------------------------------------------------------------------------
# AudienceIntent mapping per play_id (closed set, additive).
#
# The mapping is intentionally hardcoded: each new play that wants a
# non-GENERAL intent must add its row here under DS review. GENERAL is
# the safe default (BG/NBD-first chain) and matches the operational
# semantics of LTV-style ranking that covers most play types today.
#
# - ``replenishment_due`` is REPLENISHMENT_TIMING per S13 plan §B.0
#   (survival → BG/NBD → CF → RFM → recency) — Cox PH hazard is the
#   right ranker for "who needs the next reorder."
# - All other currently-wired Tier-B builders (winback_dormant_cohort,
#   discount_dependency_hygiene, cohort_journey_first_to_second,
#   aov_lift_via_threshold_bundle) are GENERAL — BG/NBD's expected
#   purchase count over the forecast horizon is the right top-of-chain
#   substrate for those audiences.
# - No LOOKALIKE_EXPANSION play is wired today (per S13 plan §B.4);
#   the mapping below is forward-compat for future ALS-driven
#   look-alike builders. If a play_id is not in this dict, it routes
#   to GENERAL.
# ---------------------------------------------------------------------------

_INTENT_BY_PLAY_ID: Dict[str, AudienceIntent] = {
    "replenishment_due": AudienceIntent.REPLENISHMENT_TIMING,
    # GENERAL plays are the implicit default (see _resolve_intent).
    # Listing them here makes the closed-mapping intent explicit for
    # future readers / DS review.
    "winback_dormant_cohort": AudienceIntent.GENERAL,
    "discount_dependency_hygiene": AudienceIntent.GENERAL,
    "cohort_journey_first_to_second": AudienceIntent.GENERAL,
    "aov_lift_via_threshold_bundle": AudienceIntent.GENERAL,
}


def _resolve_intent(play_id: str) -> AudienceIntent:
    """Return the AudienceIntent for a play_id.

    Default: GENERAL. Unknown play_ids route to GENERAL safely; the
    chain walker will still produce a typed result and any RFM/recency
    fall-through will surface on fit_warnings.
    """

    return _INTENT_BY_PLAY_ID.get(play_id, AudienceIntent.GENERAL)


# ---------------------------------------------------------------------------
# Modal-segment stability floor — DS-LOCKED §D.4.
# ---------------------------------------------------------------------------

_MODAL_SEGMENT_MIN_N: int = 50
_MODAL_SEGMENT_MIN_SHARE: float = 0.30


def _compute_modal_segment(
    audience_ids: Set[str],
    rfm_parquet_path: Path,
) -> Tuple[
    Optional[str],
    Optional[float],
    Optional[int],
    Optional[PredictedSegmentNullReason],
]:
    """Read the per-store RFM parquet; compute modal segment for an audience.

    Returns ``(segment_name, audience_modal_share, n_audience)`` with the
    DS-LOCKED stability floor applied to ``segment_name`` only — the
    audit fields (share, n) are returned uncensored when computation
    succeeds.

    Returns ``(None, None, None)`` when the parquet artifact is missing
    or the intersection of audience_ids with the RFM customer set is
    empty. ``n_audience`` reports the size of the intersection (the
    customers the audience-builder ID set AND have an RFM row), NOT the
    full audience-builder ID set size — modal-segment claim only makes
    sense over the population actually scored by RFM.
    """

    # S13.6-T7a: 4-tuple return — paired ``segment_name_null_reason``
    # is the 4th element. None on success; closed-set enum value on the
    # 4 null paths per the revised flag-aware RULE A.
    if not audience_ids:
        # No audience IDs to intersect — treat as "no intersection".
        return None, None, None, PredictedSegmentNullReason.NO_AUDIENCE_INTERSECTION
    if not rfm_parquet_path.exists():
        return None, None, None, PredictedSegmentNullReason.PARQUET_MISSING

    try:
        rfm_df = pd.read_parquet(rfm_parquet_path)
    except Exception:
        return None, None, None, PredictedSegmentNullReason.PARQUET_UNREADABLE

    if "customer_id" not in rfm_df.columns or "segment_name" not in rfm_df.columns:
        return None, None, None, PredictedSegmentNullReason.PARQUET_UNREADABLE

    rfm_df = rfm_df[["customer_id", "segment_name"]].copy()
    rfm_df["customer_id"] = rfm_df["customer_id"].astype(str)
    # Intersect audience IDs with the RFM scored set.
    audience_str = {str(x) for x in audience_ids}
    scored = rfm_df[rfm_df["customer_id"].isin(audience_str)]
    n_audience = int(scored["customer_id"].nunique())
    if n_audience == 0:
        return None, None, None, PredictedSegmentNullReason.NO_AUDIENCE_INTERSECTION

    counts = scored["segment_name"].astype(str).value_counts()
    if counts.empty:
        # Edge case: rows present but every ``segment_name`` is NaN.
        # Surfaces the audit fields (n_audience), but ``segment_name``
        # absent → mark with the modal-floor reason as the closest
        # closed-set member (no member for "empty counts").
        return None, None, n_audience, PredictedSegmentNullReason.MODAL_FLOOR_NOT_CLEARED
    modal_name = str(counts.index[0])
    modal_count = int(counts.iloc[0])
    audience_modal_share = float(modal_count) / float(n_audience)

    # DS-LOCKED stability floor — applies to segment_name ONLY.
    if (
        n_audience < _MODAL_SEGMENT_MIN_N
        or audience_modal_share < _MODAL_SEGMENT_MIN_SHARE
    ):
        return (
            None,
            audience_modal_share,
            n_audience,
            PredictedSegmentNullReason.MODAL_FLOOR_NOT_CLEARED,
        )

    return modal_name, audience_modal_share, n_audience, None


# ---------------------------------------------------------------------------
# Public surface.
# ---------------------------------------------------------------------------


# Type alias for the audience-builder resolver injected by main.py. The
# resolver maps play_id -> a zero/one-arg callable that produces an
# AudienceBuildResult-like object exposing ``audience_ids``. Encapsulated
# this way so this module does not import the audience-builder
# registry directly (keeps the module substrate-side / orchestration-
# decoupled).
AudienceIdsResolver = Callable[[str], Set[str]]


def populate_play_card_consumers(
    engine_run: EngineRun,
    *,
    audience_ids_resolver: AudienceIdsResolver,
    rfm_parquet_path: Optional[Path] = None,
) -> EngineRun:
    """Walk ``engine_run.recommendations``; populate consumer slots.

    For each PlayCard:

    1. Resolve the :class:`AudienceIntent` from play_id.
    2. Walk the intent-conditional chain via :func:`rank_audience`.
    3. Build a :class:`ModelCardRef` from the
       :class:`RankingStrategyResult` (strategy_used + fit_status_chain
       + fit_warnings).
    4. If ``rfm_parquet_path`` is provided AND exists, compute the
       audience's modal RFM segment under the DS-LOCKED stability
       floor; populate a :class:`PredictedSegment` with the modal
       triple ``(segment_name, audience_modal_share, n_audience)``.
       If the parquet is absent / unreadable / produces no
       intersection, :attr:`PlayCard.predicted_segment` stays ``None``
       on that card.

    The function mutates by ``dataclasses.replace`` (immutable-friendly)
    on each card and on ``engine_run.recommendations``. No append. No
    new :class:`RejectedPlay`. No append to ``engine_run.considered``.
    No ML-fit ReasonCode is emitted from this function — the only
    surface for ML-fit audit is ``ModelCardRef.fit_warnings`` per
    Q-S13-4 LOCK.

    Args:
        engine_run: the EngineRun after ``apply_guardrails_to_injected``
            (so recommendations is the final post-injection list).
        audience_ids_resolver: callable that maps a play_id to the
            audience customer-id set (re-resolves the audience-builder
            on the fly; mirrors the cannibalization-overlap pattern at
            ``src/main.py:1937-1954``).
        rfm_parquet_path: per-store RFM parquet artifact path (typically
            ``data/<store_id>/predictive/rfm.parquet``). When ``None``
            or non-existent, every card's ``predicted_segment`` stays
            ``None`` (model_card_ref still populates — chain-walk audit
            is independent of RFM parquet availability).

    Returns:
        The :class:`EngineRun` with ``recommendations`` rebuilt as a
        new list whose elements carry populated ``predicted_segment``
        / ``model_card_ref`` per the above rules. All other EngineRun
        fields preserved.
    """

    predictive_models: Dict[str, ModelCard] = dict(
        getattr(engine_run, "predictive_models", {}) or {}
    )
    recs = list(engine_run.recommendations or [])
    if not recs:
        return engine_run

    new_recs: List[PlayCard] = []
    for pc in recs:
        play_id = str(getattr(pc, "play_id", "") or "")
        intent = _resolve_intent(play_id)

        # (1)+(2)+(3): chain walk + ModelCardRef.
        result: RankingStrategyResult = rank_audience(predictive_models, intent)
        model_card_ref = ModelCardRef(
            strategy_used=result.strategy_used,
            fit_status_chain=list(result.fit_status_chain),
            fit_warnings=list(result.fit_warnings),
        )

        # (4): modal segment (subject to stability floor).
        predicted_segment: Optional[PredictedSegment] = None
        if rfm_parquet_path is not None:
            try:
                audience_ids = audience_ids_resolver(play_id)
            except Exception:
                audience_ids = set()
            if audience_ids:
                (
                    segment_name,
                    modal_share,
                    n_audience,
                    seg_null_reason,
                ) = _compute_modal_segment(audience_ids, rfm_parquet_path)
                # S13.6-T7a: the wrapper ``PredictedSegment`` populates
                # ONLY when audit fields are populated (D-S13-2:
                # modal-floor-not-cleared keeps audit fields uncensored
                # OR success). Pure structural-absence paths
                # (parquet_missing / parquet_unreadable /
                # no_audience_intersection) leave the OUTER wrapper
                # ``PlayCard.predicted_segment`` as ``None`` — matches
                # the pre-T7a producer contract. The inner-field
                # ``segment_name_null_reason`` is paired only on the
                # MODAL_FLOOR_NOT_CLEARED path today.
                if (
                    segment_name is not None
                    or modal_share is not None
                    or n_audience is not None
                ):
                    predicted_segment = PredictedSegment(
                        segment_name=segment_name,
                        audience_modal_share=modal_share,
                        n_audience=n_audience,
                        segment_name_null_reason=seg_null_reason,
                    )

        new_recs.append(
            _dc_replace(
                pc,
                model_card_ref=model_card_ref,
                predicted_segment=predicted_segment
                if predicted_segment is not None
                else pc.predicted_segment,
            )
        )

    return _dc_replace(engine_run, recommendations=new_recs)


__all__ = [
    "AudienceIdsResolver",
    "populate_play_card_consumers",
]
