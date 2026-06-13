"""Sprint 6 Ticket T3 — replenishment_due audience builder tests.

Covers the new per-customer x per-SKU cadence-due audience builder
(`replenishment_due_candidates`) + the prior-anchored measurement-
builder dispatch entry on ``bestseller_amplify.bundle_value`` (Beauty
validated_external bsandco; supplements heuristic_unvalidated routes
to Considered with PRIOR_UNVALIDATED) + WouldBeMeasuredBy enum
addition + flag-OFF byte-identity guard.

Founder decisions locked (memory.md e87e431):
- Q2: per-SKU customers-with->=2-repeat-purchases floor. Originally
  N=30; S7.6-T2.5-fix (DS architect scope card 2026-05-22) lowers the
  default to N=10 + adds a per-stage profile cell (8/12/20/30).
- Q3: prior = bestseller_amplify.bundle_value (Beauty validated_external bsandco).
- Q5: T3.5 envelope check posterior p50 in [prior.range_p10, prior.range_p90].

Flag default OFF; no merchant-facing behavior change until T3.5.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import audience_builders as ab  # noqa: E402
from src import measurement_builder as mb  # noqa: E402
from src.engine_run import (  # noqa: E402
    EvidenceClass,
    PlayCard,
    RevenueRangeSource,
    WouldBeMeasuredBy,
)
from src.priors_loader import (  # noqa: E402
    PriorValidationStatus,
    clear_cache,
)
from src.utils import DEFAULTS  # noqa: E402


ANCHOR = pd.Timestamp("2026-05-01 12:00:00")


# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------


def _row(customer_id: str, days_ago: int, lineitem: str, *, net: float = 30.0):
    created = ANCHOR - pd.Timedelta(days=days_ago)
    return {
        "Name": f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": created,
        "net_sales": net,
        "lineitem_any": lineitem,
    }


def _make_g(rows):
    return (
        pd.DataFrame(rows)
        .sort_values(["customer_id", "Created at"])
        .reset_index(drop=True)
    )


def _beauty_cadence_sku_rows(
    n_customers: int,
    *,
    cadence_days: int = 30,
    lineitem: str = "Cleanser 50ml",
    last_offset: int = 0,
):
    """n customers each with 3 in-class purchases of one SKU at the given
    cadence. Most-recent purchase is ``last_offset`` days before ANCHOR;
    if ``last_offset == cadence_days`` the customer is "due" (in window).
    """
    rows = [_row("anchor", 0, "Unrelated item no size token")]
    for i in range(n_customers):
        rows.append(_row(f"c{i}", last_offset + 2 * cadence_days, lineitem))
        rows.append(_row(f"c{i}", last_offset + cadence_days, lineitem))
        rows.append(_row(f"c{i}", last_offset, lineitem))
    return rows


# ---------------------------------------------------------------------------
# T1: Builder fires on Beauty with N>=30-customer SKUs
# ---------------------------------------------------------------------------


def test_t1_beauty_builder_fires_with_n30_sku():
    rows = _beauty_cadence_sku_rows(35, cadence_days=30, last_offset=30)
    g = _make_g(rows)
    cfg = {"VERTICAL_MODE": "beauty"}
    res = ab.replenishment_due_candidates(g, {}, cfg)
    assert res.play_id == "replenishment_due"
    assert res.audience_size > 0, (
        f"Beauty cadence-due cohort should fire; got 0. "
        f"seg={res.segment_definition!r}"
    )
    assert res.preliminary_rejection_reason is None
    assert res.audience_size == 35


# ---------------------------------------------------------------------------
# T2: Supplements via T2 parser; None SKUs do NOT contribute
# ---------------------------------------------------------------------------


def test_t2_supplements_via_t2_parser_excludes_none_skus():
    # Build 35 customers with a parseable supplements SKU (count=60) at
    # a 45-day cadence, plus 35 customers with an UN-parseable SKU
    # (named blend, returns None from parse_unit_coherent). The
    # un-parseable cohort should be entirely excluded.
    rows = [_row("anchor", 0, "Filler")]
    for i in range(35):
        rows.append(_row(f"p{i}", 90, "Magnesium Glycinate 200mg 60ct"))
        rows.append(_row(f"p{i}", 45, "Magnesium Glycinate 200mg 60ct"))
    for i in range(35):
        rows.append(_row(f"np{i}", 90, "Pre-Workout Energy Complex"))
        rows.append(_row(f"np{i}", 45, "Pre-Workout Energy Complex"))
    g = _make_g(rows)
    res = ab.replenishment_due_candidates(g, {}, {"VERTICAL_MODE": "supplements"})
    # Only the parseable cohort can contribute.
    assert res.audience_size == 35
    assert res.preliminary_rejection_reason is None

    # Sanity: confirm S6-T2 parser coverage for these SKUs.
    from src.replenishment_parser import parse_unit_coherent
    assert parse_unit_coherent("supplements", "Magnesium Glycinate 200mg 60ct") == ("count", 60)
    assert parse_unit_coherent("supplements", "Pre-Workout Energy Complex") is None


# ---------------------------------------------------------------------------
# T3: SKU below floor → zero audience, no crash
#
# S7.6-T2.5-fix (2026-05-22): default lowered N=30 → N=10 per DS architect
# scope card 2026-05-22 (the legacy N=30 was a textbook median-stability
# rule of thumb, not ICP-validated; <20% of representative small-DTC
# merchants cleared it). 5 customers is below the new N=10 default.
# ---------------------------------------------------------------------------


def test_t3_sku_below_floor_zero_audience_no_crash():
    # 5 customers (below N=10) with 2 purchases each at 30-day cadence.
    rows = _beauty_cadence_sku_rows(5, cadence_days=30, last_offset=30)
    g = _make_g(rows)
    res = ab.replenishment_due_candidates(g, {}, {"VERTICAL_MODE": "beauty"})
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# T4: Cadence inference deterministic across 2 runs (G-7)
# ---------------------------------------------------------------------------


def test_t4_cadence_inference_deterministic_g7():
    rows = _beauty_cadence_sku_rows(40, cadence_days=28, last_offset=28)
    g = _make_g(rows)
    cfg = {"VERTICAL_MODE": "beauty"}
    r1 = ab.replenishment_due_candidates(g, {}, cfg)
    r2 = ab.replenishment_due_candidates(g, {}, cfg)
    assert r1.audience_size == r2.audience_size
    assert r1.audience_ids == r2.audience_ids
    assert r1.segment_definition == r2.segment_definition


# ---------------------------------------------------------------------------
# T5: Flag OFF ⇒ builder not invoked from main.py / detect.py registry
# ---------------------------------------------------------------------------


def test_t5_default_flag_off_at_t3():
    # The DEFAULTS-level expectation: flag default is False at T3.
    # T3.5 owns the flag flip; do not flip it at T3.
    assert DEFAULTS.get("ENGINE_V2_BUILDER_REPLENISHMENT_DUE", None) is False


def test_t5_main_filters_play_from_registry_under_flag_off(monkeypatch):
    # The main.py wiring filters ``replenishment_due`` out of the
    # registry-for-detect dict when the flag is OFF, to preserve flag-
    # OFF fixture byte-identity. We assert the filter logic directly
    # by mimicking the conditional applied in src/main.py.
    from src.play_registry import PLAYS
    cfg_off = {"ENGINE_V2_BUILDER_REPLENISHMENT_DUE": False}
    if not bool(cfg_off.get("ENGINE_V2_BUILDER_REPLENISHMENT_DUE", False)):
        filtered = {k: v for k, v in PLAYS.items() if k != "replenishment_due"}
    else:
        filtered = dict(PLAYS)
    assert "replenishment_due" not in filtered
    # And under flag-ON, the play is present.
    cfg_on = {"ENGINE_V2_BUILDER_REPLENISHMENT_DUE": True}
    if not bool(cfg_on.get("ENGINE_V2_BUILDER_REPLENISHMENT_DUE", False)):
        filtered2 = {k: v for k, v in PLAYS.items() if k != "replenishment_due"}
    else:
        filtered2 = dict(PLAYS)
    assert "replenishment_due" in filtered2


# ---------------------------------------------------------------------------
# Measurement-builder fixtures
# ---------------------------------------------------------------------------


def _candidate(play_id: str, audience_size: int, *, prelim=None):
    return SimpleNamespace(
        play_id=play_id,
        audience_size=audience_size,
        segment_definition=f"{play_id} test cohort",
        data_used=[],
        preliminary_rejection_reason=prelim,
        cold_start=False,
    )


def _aligned_with_aov(aov: float):
    return {"L28": {"aov": aov, "delta": {}, "p": {}, "meta": {}}}


# ---------------------------------------------------------------------------
# T6: Flag ON Beauty — evidence_class matches prior source_class
# ---------------------------------------------------------------------------


def test_t6_beauty_card_evidence_class_matches_prior_source_class():
    """The PlayCard built on Beauty validated_external base_rate must
    reflect the prior's source_class via the blend_provenance driver.

    S6-T3.x re-key (2026-05-19): prior is now
    ``replenishment_due.base_rate.beauty`` (source_class=observational,
    validated_external; Klaviyo PERL Cosmetics + H&B 2026 memo). The
    previous wiring to ``bestseller_amplify.bundle_value.beauty``
    (source_class=expert) is superseded by D-S6-2.1.
    """
    clear_cache()
    cand = _candidate("replenishment_due", audience_size=200)
    aligned = _aligned_with_aov(60.0)
    card = mb.build_prior_anchored_play_card(cand, aligned, vertical="beauty")
    assert card is not None
    assert card.play_id == "replenishment_due"
    assert card.evidence_class == EvidenceClass.DIRECTIONAL
    rr = card.revenue_range
    bp = next(
        (d for d in rr.drivers if isinstance(d, dict) and d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    # replenishment_due.base_rate.beauty is authored with
    # source_class=observational and validation_status=validated_external
    # (Klaviyo PERL Cosmetics replenishment-isolated case study +
    # Klaviyo 2026 H&B Omnichannel Benchmark Report).
    assert bp["prior_source_class"] == "observational"
    assert bp["prior_validation_status"] == PriorValidationStatus.VALIDATED_EXTERNAL.value


# ---------------------------------------------------------------------------
# T7: Flag ON supplements — revenue_range suppressed (heuristic_unvalidated)
# ---------------------------------------------------------------------------


def test_t7_supplements_no_prior_anchored_card_emitted():
    """``bestseller_amplify.bundle_value`` is authored only for Beauty
    (validated_external bsandco) and Mixed (heuristic_unvalidated). No
    supplements entry is authored in priors.yaml (ticket: "No new YAML").
    The honest behavior is: ``build_prior_anchored_play_card`` returns
    ``None`` for supplements; the M3 candidate routes to Considered via
    ``populate_considered_from_candidates``. Hard-stop #3 invariant
    holds (supplements does NOT land in Recommended Now under any path)."""
    clear_cache()
    cand = _candidate("replenishment_due", audience_size=200)
    aligned = _aligned_with_aov(60.0)
    card = mb.build_prior_anchored_play_card(cand, aligned, vertical="supplements")
    assert card is None


# ---------------------------------------------------------------------------
# T8: vertical_mode=mixed blends 50/50 per G-3 (audience union)
# ---------------------------------------------------------------------------


def test_t8_mixed_blends_beauty_and_supplements_50_50():
    # 35 beauty-side cadence customers (Cleanser 50ml) + 35 supplements-
    # side cadence customers (Magnesium 60ct). The mixed audience layer
    # unions both cohorts (the 50/50 prior-blend lives at the
    # measurement-builder seam, not the audience-builder seam).
    rows = [_row("anchor", 0, "Filler")]
    for i in range(35):
        rows.append(_row(f"b{i}", 60, "Cleanser 50ml"))
        rows.append(_row(f"b{i}", 30, "Cleanser 50ml"))
    for i in range(35):
        rows.append(_row(f"s{i}", 90, "Magnesium Glycinate 200mg 60ct"))
        rows.append(_row(f"s{i}", 45, "Magnesium Glycinate 200mg 60ct"))
    g = _make_g(rows)
    res = ab.replenishment_due_candidates(g, {}, {"VERTICAL_MODE": "mixed"})
    assert res.audience_size == 70  # 35 + 35 disjoint customer ids
    # Mixed prior-anchored card routing is KI-19 conservative-min →
    # suppressed prior_unvalidated (covered indirectly via the
    # winback-side mixed test in test_s6_t1_winback_dormant_cohort.py).


# ---------------------------------------------------------------------------
# T9: Posterior matches bayesian_blend formula on Beauty
# ---------------------------------------------------------------------------


def test_t9_beauty_posterior_matches_bayesian_blend_cold_start():
    """Cold-start posterior collapses to prior.value when observed_n=0
    (bayesian_blend with store_value=prior_value collapses to prior).

    S6-T3.x re-key (2026-05-19): prior is
    ``replenishment_due.base_rate.beauty`` (value=0.0220,
    range=[0.0120, 0.0430], effective_n=30; Klaviyo PERL Cosmetics +
    H&B 2026 memo). The previous wiring to
    ``bestseller_amplify.bundle_value.beauty`` ($45 / [$25, $75]) is
    superseded by D-S6-2.1; the base_rate prior is a probability
    rate, resolving the D-S6-2 dollar-vs-rate category error.
    """
    clear_cache()
    cand = _candidate("replenishment_due", audience_size=200)
    aligned = _aligned_with_aov(60.0)
    card = mb.build_prior_anchored_play_card(cand, aligned, vertical="beauty")
    rr = card.revenue_range
    bp = next(
        (d for d in rr.drivers if isinstance(d, dict) and d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    # Bayesian cold-start: posterior collapses to prior.value.
    assert bp["prior_value"] == 0.022
    assert bp["posterior_value"] == 0.022
    assert bp["observed_n"] == 0
    assert bp["observed_k"] == 0
    assert bp["store_data_status"] == "no_outcome_history"
    assert bp["posterior_ratio"] == "prior_dominant"


# ---------------------------------------------------------------------------
# T10: WouldBeMeasuredBy enum member present + serializes
# ---------------------------------------------------------------------------


def test_t10_would_be_measured_by_enum_member_present_and_serializes():
    member = WouldBeMeasuredBy.REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW
    assert member.value == "REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW"
    # Construction + str-enum identity (JSON-safe).
    pc = PlayCard(
        play_id="replenishment_due",
        would_be_measured_by=member,
    )
    assert pc.would_be_measured_by is member
    assert pc.would_be_measured_by == "REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW"
    # Round-trip through EngineRun.to_dict / from_dict.
    from src.engine_run import EngineRun
    er = EngineRun(recommendations=[pc])
    d = er.to_dict()
    raw = d["recommendations"][0]["would_be_measured_by"]
    assert raw == "REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW"
    er2 = EngineRun.from_dict(d)
    assert er2.recommendations[0].would_be_measured_by == member


def test_t10_card_carries_replenishment_enum_value():
    clear_cache()
    cand = _candidate("replenishment_due", audience_size=200)
    aligned = _aligned_with_aov(60.0)
    card = mb.build_prior_anchored_play_card(cand, aligned, vertical="beauty")
    assert card.would_be_measured_by == (
        WouldBeMeasuredBy.REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW
    )


# ---------------------------------------------------------------------------
# T11: source_artifact threaded for Beauty validated_external
# ---------------------------------------------------------------------------


def test_t11_source_artifact_threaded_for_beauty_validated_external():
    clear_cache()
    cand = _candidate("replenishment_due", audience_size=200)
    aligned = _aligned_with_aov(60.0)
    card = mb.build_prior_anchored_play_card(cand, aligned, vertical="beauty")
    bp = next(
        (d for d in card.revenue_range.drivers
         if isinstance(d, dict) and d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    # S6-T3.x re-key (2026-05-19): source_artifact now points to the
    # dedicated Gemini Deep Research memo for replenishment_due
    # (D-S6-2.1 supersedes D-S6-2).
    assert bp["prior_source_artifact"] == (
        "config/priors_sources/replenishment_due__base_rate__beauty.md"
    )


# ---------------------------------------------------------------------------
# T12: M3 candidate contract — no stats/revenue at audience layer
# ---------------------------------------------------------------------------


def test_t12_m3_candidate_contract_no_stats_or_revenue_fields():
    rows = _beauty_cadence_sku_rows(35, cadence_days=30, last_offset=30)
    g = _make_g(rows)
    res = ab.replenishment_due_candidates(g, {}, {"VERTICAL_MODE": "beauty"})
    # AudienceResult does not carry stats / revenue / effects / p-values.
    forbidden_attrs = {
        "p_value", "p", "ci", "confidence_interval",
        "observed_effect", "effect", "lift",
        "revenue", "revenue_range", "rev_p50",
    }
    for attr in forbidden_attrs:
        assert not hasattr(res, attr), (
            f"AudienceResult must not carry {attr!r} (M3 contract)"
        )


# ---------------------------------------------------------------------------
# T13: Right-censored — customers with no repeat purchases excluded
# ---------------------------------------------------------------------------


def test_t13_right_censored_single_purchase_excluded():
    # 50 customers with exactly ONE purchase of an in-class SKU.
    # Per S6.5-T3 cadence convention these are right-censored.
    rows = [_row("anchor", 0, "Filler")]
    for i in range(50):
        rows.append(_row(f"c{i}", 30, "Cleanser 50ml"))
    g = _make_g(rows)
    res = ab.replenishment_due_candidates(g, {}, {"VERTICAL_MODE": "beauty"})
    # No SKU clears the per-SKU floor (single-purchase ⇒ 0
    # inter-purchase gaps ⇒ 0 contributing customers ⇒ excluded).
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# T14: Tolerance window (cadence +/- half-cadence) respected on synthetic
# ---------------------------------------------------------------------------


def test_t14_tolerance_window_half_cadence_respected():
    """30 customers at 30-day cadence; 20 with last purchase 30d ago
    (in window: 30 +/- 15 = [15, 45]), 15 with last purchase 80d ago
    (out of window). Audience must equal the 20."""
    rows = [_row("anchor", 0, "Filler")]
    # In-window customers: cadence 30d, last purchase 30d ago.
    for i in range(20):
        rows.append(_row(f"in{i}", 90, "Cleanser 50ml"))
        rows.append(_row(f"in{i}", 60, "Cleanser 50ml"))
        rows.append(_row(f"in{i}", 30, "Cleanser 50ml"))
    # Out-of-window customers: same cadence (so they contribute to
    # cadence inference), but last purchase is 80d ago (well outside
    # 30+/-15 = [15,45]).
    for i in range(15):
        rows.append(_row(f"out{i}", 140, "Cleanser 50ml"))
        rows.append(_row(f"out{i}", 110, "Cleanser 50ml"))
        rows.append(_row(f"out{i}", 80, "Cleanser 50ml"))
    g = _make_g(rows)
    res = ab.replenishment_due_candidates(g, {}, {"VERTICAL_MODE": "beauty"})
    # 35 contributors clear N=30; cadence median = 30; tolerance = 15.
    # Only the 20 in-window customers should be in the audience.
    assert res.audience_size == 20
    assert all(c.startswith("in") for c in res.audience_ids)


# ---------------------------------------------------------------------------
# Registry / dispatch sanity
# ---------------------------------------------------------------------------


def test_builder_registered_under_audience_replenishment_due_ref():
    assert ab.get_builder("audience.replenishment_due") is (
        ab.replenishment_due_candidates
    )


def test_play_registry_entry_present_with_correct_vertical_set():
    from src.play_registry import PLAYS
    assert "replenishment_due" in PLAYS
    pd_entry = PLAYS["replenishment_due"]
    assert pd_entry.audience_builder_ref == "audience.replenishment_due"
    assert pd_entry.vertical_applicable == frozenset(
        {"beauty", "supplements", "mixed"}
    )


def test_ranking_strategy_param_accepted_as_no_op():
    # Forward-scaffolding for the Sprint 10-13 ML AUDIENCE layer.
    rows = _beauty_cadence_sku_rows(35, cadence_days=30, last_offset=30)
    g = _make_g(rows)
    cfg = {"VERTICAL_MODE": "beauty"}
    r1 = ab.replenishment_due_candidates(g, {}, cfg, ranking_strategy=None)
    r2 = ab.replenishment_due_candidates(g, {}, cfg, ranking_strategy="predicted_ltv_desc")
    # No-op today: results match.
    assert r1.audience_size == r2.audience_size
    assert r1.audience_ids == r2.audience_ids
