"""Sprint 6 Ticket T1 — winback_dormant_cohort builder tests.

Covers the new audience builder (3-part cohort definition) plus the
prior-anchored measurement-builder pathway (cold-start posterior,
validation-status routing, mixed-vertical KI-19 refusal).

Flag-off byte-identity on pinned fixtures is asserted indirectly by
keeping ``ENGINE_V2_BUILDER_WINBACK_DORMANT`` default OFF in
``src/utils.py``; the existing slate-regression tests in
``tests/test_slate_regression_*.py`` exercise that.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import audience_builders as ab  # noqa: E402
from src import measurement_builder as mb  # noqa: E402
from src.engine_run import (  # noqa: E402
    EvidenceClass,
    RevenueRangeSource,
    WouldBeMeasuredBy,
)
from src.priors_loader import (  # noqa: E402
    PriorValidationStatus,
    clear_cache,
)


ANCHOR = pd.Timestamp("2026-05-01 12:00:00")


# ---------------------------------------------------------------------------
# Audience-builder fixture helpers
# ---------------------------------------------------------------------------


def _row(customer_id: str, days_ago: int):
    created = ANCHOR - pd.Timedelta(days=days_ago)
    return {
        "Name": f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": created,
        "net_sales": 50.0,
        "lineitem_any": "Cleanser 50ml",
    }


def _make_g(rows):
    return pd.DataFrame(rows).sort_values(["customer_id", "Created at"]).reset_index(drop=True)


def _dormant_repeat_buyer_rows(n_customers: int, *, vertical: str):
    """n_customers each with 2 prior orders, last order in window, no L28 activity.

    Always includes a single anchor customer with an order at day 0 to pin
    ``max(Created at) == ANCHOR``; that anchor customer has only ONE order
    so they fail the >=2-prior-orders filter and are excluded from the
    cohort.
    """

    last_days = 30 if vertical == "beauty" else 90
    prior_days = 180
    rows = [_row("anchor", 0)]  # single-order; pins maxd at ANCHOR
    for i in range(n_customers):
        rows.append(_row(f"c{i}", prior_days))
        rows.append(_row(f"c{i}", last_days))
    return rows


def _self_reactivated_rows(n_customers: int, *, base_id: str = "active"):
    """n customers whose last order is in L28 (already self-reactivated).

    These should be excluded by the 3-part cohort definition: their
    most-recent-order recency is < 21 days, so the recency filter drops
    them. Equivalent to the "no order in past 28d" filter for any
    customer whose recency would otherwise be in the lower band [21, 28].
    """
    rows = []
    for i in range(n_customers):
        # Two historical + one in last 14d (latest).
        rows.append(_row(f"{base_id}{i}", 180))
        rows.append(_row(f"{base_id}{i}", 30))
        rows.append(_row(f"{base_id}{i}", 14))
    return rows


# ---------------------------------------------------------------------------
# Audience-builder tests
# ---------------------------------------------------------------------------


def test_winback_dormant_beauty_window_fires_when_cohort_large():
    rows = _dormant_repeat_buyer_rows(600, vertical="beauty")
    g = _make_g(rows)
    cfg = {"VERTICAL_MODE": "beauty"}
    res = ab.winback_dormant_cohort_candidates(g, {}, cfg)
    assert res.play_id == "winback_dormant_cohort"
    assert res.audience_size == 600
    assert res.preliminary_rejection_reason is None
    assert "21-45d" in res.segment_definition


def test_winback_dormant_supplements_uses_60_120_window():
    rows = _dormant_repeat_buyer_rows(600, vertical="supplements")
    g = _make_g(rows)
    cfg = {"VERTICAL_MODE": "supplements"}
    res = ab.winback_dormant_cohort_candidates(g, {}, cfg)
    assert res.audience_size == 600
    assert "60-120d" in res.segment_definition
    assert res.preliminary_rejection_reason is None


def test_winback_dormant_below_floor_routes_audience_too_small():
    rows = _dormant_repeat_buyer_rows(100, vertical="beauty")  # below 500 floor
    g = _make_g(rows)
    cfg = {"VERTICAL_MODE": "beauty"}
    res = ab.winback_dormant_cohort_candidates(g, {}, cfg)
    assert res.audience_size == 100
    assert res.preliminary_rejection_reason == "audience_too_small"


def test_winback_dormant_self_reactivated_customers_excluded():
    # 600 dormant repeat-buyers + 200 customers whose latest order is in
    # L28 (already self-reactivated). The 3-part cohort definition
    # drops the L28-active 200.
    rows = _dormant_repeat_buyer_rows(600, vertical="beauty")
    rows.extend(_self_reactivated_rows(200))
    g = _make_g(rows)
    cfg = {"VERTICAL_MODE": "beauty"}
    res = ab.winback_dormant_cohort_candidates(g, {}, cfg)
    assert res.audience_size == 600
    assert res.preliminary_rejection_reason is None


def test_winback_dormant_single_purchase_customers_excluded():
    # 600 customers each with a SINGLE order in window. The >=2 prior
    # orders filter should drop them all.
    rows = [_row(f"c{i}", 30) for i in range(600)]
    g = _make_g(rows)
    cfg = {"VERTICAL_MODE": "beauty"}
    res = ab.winback_dormant_cohort_candidates(g, {}, cfg)
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "audience_too_small"


def test_winback_dormant_empty_frame_returns_data_missing():
    g = pd.DataFrame(columns=["Created at", "customer_id"])
    res = ab.winback_dormant_cohort_candidates(g, {}, {})
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason in ("data_missing", "audience_too_small")


def test_winback_dormant_builder_registered():
    assert ab.get_builder("audience.winback_dormant_cohort") is not None
    assert ab.get_builder("audience.winback_dormant_cohort") is (
        ab.winback_dormant_cohort_candidates
    )


# ---------------------------------------------------------------------------
# Measurement-builder (prior-anchored) tests
# ---------------------------------------------------------------------------


def _candidate(audience_size: int, *, prelim=None):
    return SimpleNamespace(
        play_id="winback_dormant_cohort",
        audience_size=audience_size,
        segment_definition="dormant repeat-buyers test cohort",
        data_used=[],
        preliminary_rejection_reason=prelim,
        cold_start=False,
    )


def _aligned_with_aov(aov: float):
    return {"L28": {"aov": aov, "delta": {}, "p": {}, "meta": {}}}


def test_prior_anchored_beauty_emits_non_suppressed_blend_range():
    clear_cache()
    cand = _candidate(audience_size=600)
    aligned = _aligned_with_aov(60.0)
    card = mb.build_prior_anchored_play_card(
        cand, aligned, vertical="beauty"
    )
    assert card is not None
    assert card.play_id == "winback_dormant_cohort"
    assert card.evidence_class == EvidenceClass.DIRECTIONAL
    assert card.would_be_measured_by == WouldBeMeasuredBy.LAPSED_REACTIVATION_IN_30D
    rr = card.revenue_range
    assert rr is not None
    assert rr.suppressed is False
    assert rr.source == RevenueRangeSource.BLEND
    # Posterior collapses to prior on cold-start.
    # Beauty winback_21_45.base_rate validated_external value=0.08.
    # rev_p50 = 600 * 0.08 * 60.0 = 2880.00
    assert abs(rr.p50 - 2880.00) < 0.01
    # blend_provenance driver present with cold-start fields.
    bp = next(
        (d for d in rr.drivers if d.get("name") == "blend_provenance"), None
    )
    assert bp is not None
    assert bp["prior_validation_status"] == PriorValidationStatus.VALIDATED_EXTERNAL.value
    assert bp["pseudo_n"] == 30
    assert bp["observed_k"] == 0
    assert bp["observed_n"] == 0
    assert bp["store_data_status"] == "no_outcome_history"
    assert bp["posterior_value"] == 0.08
    assert bp["posterior_ratio"] == "prior_dominant"
    assert bp["prior_source_artifact"] == (
        "config/priors_sources/winback_21_45__base_rate__beauty.md"
    )


def test_prior_anchored_supplements_suppresses_with_prior_unvalidated():
    clear_cache()
    cand = _candidate(audience_size=600)
    aligned = _aligned_with_aov(60.0)
    card = mb.build_prior_anchored_play_card(
        cand, aligned, vertical="supplements"
    )
    assert card is not None
    rr = card.revenue_range
    assert rr.suppressed is True
    # ``reason`` key on a suppression driver triggers
    # ``_route_prior_unvalidated_holds`` in decide.py.
    reasons = [d.get("reason") for d in rr.drivers if isinstance(d, dict)]
    assert "prior_unvalidated" in reasons
    bp = next(
        (d for d in rr.drivers if d.get("name") == "blend_provenance"), None
    )
    assert bp is not None
    assert bp["prior_validation_status"] == PriorValidationStatus.HEURISTIC_UNVALIDATED.value


def test_prior_anchored_mixed_vertical_ki19_conservative_min_refusal():
    """Mixed = 50/50 beauty+supplements blend; supplements side is
    heuristic_unvalidated, so KI-19 conservative-min downgrades the
    blended entry to heuristic_unvalidated → PlayCard suppressed with
    prior_unvalidated."""

    clear_cache()
    cand = _candidate(audience_size=600)
    aligned = _aligned_with_aov(60.0)
    card = mb.build_prior_anchored_play_card(
        cand, aligned, vertical="mixed"
    )
    assert card is not None
    rr = card.revenue_range
    assert rr.suppressed is True
    reasons = [d.get("reason") for d in rr.drivers if isinstance(d, dict)]
    assert "prior_unvalidated" in reasons


def test_prior_anchored_skips_below_floor_candidate():
    cand = _candidate(audience_size=100, prelim="audience_too_small")
    aligned = _aligned_with_aov(60.0)
    card = mb.build_prior_anchored_play_card(
        cand, aligned, vertical="beauty"
    )
    # When the audience builder set a rejection reason, the prior-
    # anchored builder bows out so populate_considered_from_candidates
    # routes the candidate to Considered with AUDIENCE_TOO_SMALL.
    assert card is None


def test_prior_anchored_unsupported_play_returns_none():
    cand = SimpleNamespace(
        play_id="bestseller_amplify",
        audience_size=500,
        segment_definition="x",
        data_used=[],
        preliminary_rejection_reason=None,
        cold_start=False,
    )
    aligned = _aligned_with_aov(60.0)
    card = mb.build_prior_anchored_play_card(cand, aligned, vertical="beauty")
    assert card is None


def test_prior_anchored_recommendations_filters_existing():
    cand = _candidate(audience_size=600)
    aligned = _aligned_with_aov(60.0)
    cards = mb.build_prior_anchored_recommendations(
        [cand],
        aligned,
        vertical="beauty",
        existing_recommendation_ids=["winback_dormant_cohort"],
    )
    assert cards == []


def test_prior_anchored_recommendations_emits_card():
    cand = _candidate(audience_size=600)
    aligned = _aligned_with_aov(60.0)
    cards = mb.build_prior_anchored_recommendations(
        [cand], aligned, vertical="beauty"
    )
    assert len(cards) == 1
    assert cards[0].play_id == "winback_dormant_cohort"


# ---------------------------------------------------------------------------
# Wiring / contract tests
# ---------------------------------------------------------------------------


def test_winback_dormant_play_registered():
    from src.play_registry import PLAYS

    assert "winback_dormant_cohort" in PLAYS
    pd_def = PLAYS["winback_dormant_cohort"]
    assert pd_def.evidence_class_default == "directional"
    assert pd_def.audience_builder_ref == "audience.winback_dormant_cohort"
    assert pd_def.measurement_metric == "reactivation_rate"
    assert "beauty" in pd_def.vertical_applicable
    assert "supplements" in pd_def.vertical_applicable
    assert "mixed" in pd_def.vertical_applicable


def test_flag_default_on_after_t1_5():
    """T1 shipped flag default OFF; T1.5 flipped to ON. This pin
    prevents an accidental rollback. Per the T1.5 fixture probe the
    flip is byte-identical on the pinned synthetic briefings — see
    code-refactor-engineer-s6-t1_5-summary.md §3."""
    from src import utils

    assert utils.get_config().get("ENGINE_V2_BUILDER_WINBACK_DORMANT") is True


def test_would_be_measured_by_enum_value_present():
    assert WouldBeMeasuredBy.LAPSED_REACTIVATION_IN_30D.value == (
        "LAPSED_REACTIVATION_IN_30D"
    )


# ---------------------------------------------------------------------------
# Sprint 10-13 ML AUDIENCE layer forward-scaffolding tests
# ---------------------------------------------------------------------------


def test_audience_builder_accepts_ranking_strategy_param_no_op():
    """Sprint 13 will populate this with a typed enum value; today it is
    accepted and ignored. Pin the signature so a future refactor cannot
    silently drop the parameter."""
    rows = _dormant_repeat_buyer_rows(600, vertical="beauty")
    g = _make_g(rows)
    cfg = {"VERTICAL_MODE": "beauty"}
    res_none = ab.winback_dormant_cohort_candidates(g, {}, cfg)
    res_strat = ab.winback_dormant_cohort_candidates(
        g, {}, cfg, ranking_strategy="predicted_ltv_desc"
    )
    # Today the parameter is a no-op: same audience either way.
    assert res_none.audience_size == res_strat.audience_size == 600
    assert res_none.preliminary_rejection_reason == res_strat.preliminary_rejection_reason


def test_playcard_has_reserved_ml_scaffolding_slots():
    """PlayCard reserves typed slots for the Sprint 10-13 ML AUDIENCE
    layer. Both default to None; no S6 producer populates them."""
    from src.engine_run import ModelCardRef, PlayCard, PredictedSegment

    pc = PlayCard(play_id="winback_dormant_cohort")
    assert pc.predicted_segment is None
    assert pc.model_card_ref is None
    # Explicit population round-trips through to_dict / from_dict.
    pc.predicted_segment = PredictedSegment(notes="sprint13_placeholder")
    pc.model_card_ref = ModelCardRef(notes="sprint13_placeholder")
    d = {
        "play_id": pc.play_id,
        "evidence_class": pc.evidence_class.value,
        "predicted_segment": {"notes": "sprint13_placeholder"},
        "model_card_ref": {"notes": "sprint13_placeholder"},
    }
    from src.engine_run import _from_dict_play_card  # noqa: PLC0415

    pc2 = _from_dict_play_card(d)
    assert pc2.predicted_segment is not None
    assert pc2.predicted_segment.notes == "sprint13_placeholder"
    assert pc2.model_card_ref is not None
    assert pc2.model_card_ref.notes == "sprint13_placeholder"


def test_detect_candidates_emits_winback_dormant():
    """End-to-end: detect_candidates dispatches to the new builder via
    the registry's audience_builder_ref."""
    from src.detect import detect_candidates

    rows = _dormant_repeat_buyer_rows(600, vertical="beauty")
    g = _make_g(rows)
    cfg = {"VERTICAL_MODE": "beauty"}
    cands = detect_candidates(g, {}, cfg)
    by_id = {c.play_id: c for c in cands}
    assert "winback_dormant_cohort" in by_id
    cand = by_id["winback_dormant_cohort"]
    assert cand.audience_size == 600
    assert cand.preliminary_rejection_reason is None
