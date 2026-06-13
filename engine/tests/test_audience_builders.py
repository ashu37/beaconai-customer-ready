"""Milestone 3 T3.1: per-builder unit tests for src/audience_builders.py.

Each builder is exercised on a small synthetic ``g`` / ``aligned`` fixture
so the rule and the rejection-reason path are both covered. No
statistics, scoring, or revenue is computed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import audience_builders as ab  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic-fixture helpers
# ---------------------------------------------------------------------------

ANCHOR = pd.Timestamp("2025-08-25 12:00:00")


def _row(
    customer_id: str,
    days_ago: int,
    *,
    name: str = None,
    net_sales: float = 50.0,
    discount_rate: float = 0.0,
    units_per_order: int = 1,
    lineitem: str = "Cleanser 50ml",
    category: str = "skincare",
):
    created = ANCHOR - pd.Timedelta(days=days_ago)
    return {
        "Name": name or f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": created,
        "net_sales": float(net_sales),
        "discount_rate": float(discount_rate),
        "units_per_order": int(units_per_order),
        "lineitem_any": lineitem,
        "category": category,
        "first_seen": created,
        "is_repeat": 0,
        "prev_purchase": pd.NaT,
        "days_since_last": np.nan,
    }


def _build_g(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df.sort_values(["customer_id", "Created at"]).reset_index(drop=True)
    df["first_seen"] = df.groupby("customer_id")["Created at"].transform("min")
    df["is_repeat"] = (df["Created at"] > df["first_seen"]).astype(int)
    df["prev_purchase"] = df.groupby("customer_id")["Created at"].shift(1)
    df["days_since_last"] = (df["Created at"] - df["prev_purchase"]).dt.days
    return df


def _last_only_g_for_winback() -> pd.DataFrame:
    """100 customers each with a single order N days before anchor (N=30)."""
    rows = [_row(f"c{i}", 30) for i in range(100)]
    g = _build_g(rows)
    # For a single-purchase customer, days_since_last is NaN; rebuild it as
    # "days since the order itself" so the winback cohort can match. The
    # legacy segment builder treats the last row's days_since_last as the
    # cohort filter even when there is no prior; mirror that by patching.
    g["days_since_last"] = (ANCHOR - g["Created at"]).dt.days
    return g


# ---------------------------------------------------------------------------
# winback_21_45
# ---------------------------------------------------------------------------


def test_winback_21_45_passes_when_cohort_large():
    g = _last_only_g_for_winback()
    cfg = {"MIN_N_WINBACK": 50}
    res = ab.winback_21_45(g, {"window_days": 28}, cfg)
    assert res.play_id == "winback_21_45"
    assert res.audience_size == 100
    assert res.preliminary_rejection_reason is None
    assert "21-45" in res.segment_definition or "21" in res.segment_definition


def test_winback_21_45_rejects_when_too_small():
    rows = [_row(f"c{i}", 30) for i in range(5)]
    g = _build_g(rows)
    g["days_since_last"] = (ANCHOR - g["Created at"]).dt.days
    cfg = {"MIN_N_WINBACK": 75}
    res = ab.winback_21_45(g, {"window_days": 28}, cfg)
    assert res.audience_size == 5
    assert res.preliminary_rejection_reason == "audience_too_small"


def test_winback_21_45_handles_empty_frame():
    g = pd.DataFrame(columns=["Created at", "customer_id", "days_since_last"])
    res = ab.winback_21_45(g, {}, {})
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason in ("data_missing", "audience_too_small")


# ---------------------------------------------------------------------------
# bestseller_buyers
# ---------------------------------------------------------------------------


def test_bestseller_buyers_picks_top_product_buyers():
    rows = []
    # 60 customers buy "Hot Serum 50ml" (top by sales because higher price)
    for i in range(60):
        rows.append(_row(f"hot{i}", 5, lineitem="Hot Serum 50ml", net_sales=200.0))
    # 30 customers buy "Cold Lotion 30ml"
    for i in range(30):
        rows.append(_row(f"cold{i}", 5, lineitem="Cold Lotion 30ml", net_sales=20.0))
    g = _build_g(rows)
    res = ab.bestseller_buyers(g, {}, {"MIN_N_SKU": 30})
    assert res.play_id == "bestseller_amplify"
    assert res.audience_size == 60
    assert res.preliminary_rejection_reason is None


def test_bestseller_buyers_rejects_small_audience():
    rows = [_row(f"c{i}", 5, lineitem="Only 50ml", net_sales=10.0) for i in range(10)]
    g = _build_g(rows)
    res = ab.bestseller_buyers(g, {}, {"MIN_N_SKU": 30})
    assert res.audience_size == 10
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# discount_dependent_buyers
# ---------------------------------------------------------------------------


def test_discount_dependent_buyers_passes():
    rows = [_row(f"c{i}", 5, discount_rate=0.10) for i in range(40)]
    g = _build_g(rows)
    res = ab.discount_dependent_buyers(g, {"window_days": 28}, {"MIN_N_SKU": 30})
    assert res.play_id == "discount_hygiene"
    assert res.audience_size == 40
    assert res.preliminary_rejection_reason is None


def test_discount_dependent_buyers_rejects_small():
    rows = [_row(f"c{i}", 5, discount_rate=0.10) for i in range(5)]
    g = _build_g(rows)
    res = ab.discount_dependent_buyers(g, {"window_days": 28}, {"MIN_N_SKU": 30})
    assert res.audience_size == 5
    assert res.preliminary_rejection_reason == "audience_too_small"


def test_discount_dependent_buyers_missing_columns():
    g = pd.DataFrame({"Created at": [ANCHOR], "customer_id": ["c1"]})
    res = ab.discount_dependent_buyers(g, {"window_days": 28}, {})
    assert res.preliminary_rejection_reason == "data_missing"


# ---------------------------------------------------------------------------
# subscription_candidates
# ---------------------------------------------------------------------------


def test_subscription_candidates_handles_empty():
    g = pd.DataFrame(columns=["Created at", "customer_id"])
    res = ab.subscription_candidates(g, {}, {})
    assert res.play_id == "subscription_nudge"
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "data_missing"


def test_subscription_candidates_small_data_rejects():
    # Build minimal data but not enough for the >=50 audience floor.
    rows = []
    for i in range(3):
        for k in range(4):  # 4 orders of same product per customer
            rows.append(_row(f"c{i}", 5 + k, lineitem="Daily Vitamin"))
    g = _build_g(rows)
    res = ab.subscription_candidates(g, {}, {"MIN_N_SKU": 60})
    # This should be either too_small (cohort returns 3 < 50 floor) or
    # data_missing if g_items returns empty in this micro fixture.
    assert res.audience_size <= 3
    assert res.preliminary_rejection_reason in ("audience_too_small", "data_missing")


# ---------------------------------------------------------------------------
# routine_completion_candidates
# ---------------------------------------------------------------------------


def test_routine_completion_filters_to_skincare_singles():
    rows = []
    # 80 single-product skincare buyers (recent)
    for i in range(80):
        rows.append(_row(f"sk{i}", 10, category="skincare", lineitem="Cleanser 50ml"))
    # 5 multi-product skincare buyers
    for i in range(5):
        rows.append(_row(f"mp{i}", 10, category="skincare", lineitem="Cleanser 50ml"))
        rows.append(_row(f"mp{i}", 11, category="skincare", lineitem="Toner 50ml"))
    g = _build_g(rows)
    res = ab.routine_completion_candidates(g, {}, {"MIN_N_SKU": 60})
    assert res.play_id == "routine_builder"
    assert res.audience_size == 80
    assert res.preliminary_rejection_reason is None


def test_routine_completion_rejects_when_no_skincare():
    rows = [_row(f"x{i}", 10, category="supplements") for i in range(80)]
    g = _build_g(rows)
    res = ab.routine_completion_candidates(g, {}, {"MIN_N_SKU": 60})
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# depletion_window_buyers
# ---------------------------------------------------------------------------


def test_depletion_window_targets_sized_buyers():
    rows = []
    # 30ml depletion = 25 days. 70 customers each have two 30ml orders 25
    # days apart, so days_since_last on their most recent order is 25,
    # putting them in the +/-3 day depletion window.
    for i in range(70):
        rows.append(_row(f"o{i}", 50, lineitem="Cream 30ml"))
        rows.append(_row(f"o{i}", 25, lineitem="Cream 30ml"))
    g = _build_g(rows)
    res = ab.depletion_window_buyers(g, {}, {"MIN_N_SKU": 60})
    assert res.play_id == "empty_bottle"
    assert res.audience_size == 70
    assert res.preliminary_rejection_reason is None


def test_depletion_window_no_size_token_rejects():
    rows = [_row(f"o{i}", 25, lineitem="Generic SKU") for i in range(80)]
    g = _build_g(rows)
    res = ab.depletion_window_buyers(g, {}, {"MIN_N_SKU": 60})
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "data_missing"


# ---------------------------------------------------------------------------
# repeat_cohort
# ---------------------------------------------------------------------------


def test_repeat_cohort_excludes_recent_orders():
    rows = []
    # Anchor row: holds maxd at ANCHOR.
    rows.append(_row("anchor", 0))
    # 60 customers with 2 orders, last order >14d ago -> eligible.
    for i in range(60):
        rows.append(_row(f"r{i}", 60))
        rows.append(_row(f"r{i}", 30))
    # 10 customers with 2 orders but a recent (within 14d) order -> excluded.
    for i in range(10):
        rows.append(_row(f"x{i}", 60))
        rows.append(_row(f"x{i}", 5))
    g = _build_g(rows)
    res = ab.repeat_cohort(g, {}, {})
    assert res.play_id == "frequency_accelerator"
    assert res.audience_size == 60
    assert res.preliminary_rejection_reason is None


def test_repeat_cohort_too_few_passes_threshold():
    rows = []
    rows.append(_row("anchor", 0))
    for i in range(10):
        rows.append(_row(f"r{i}", 60))
        rows.append(_row(f"r{i}", 30))
    g = _build_g(rows)
    res = ab.repeat_cohort(g, {}, {})
    assert res.audience_size == 10
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# aov_growth_cohort
# ---------------------------------------------------------------------------


def test_aov_growth_cohort_active_7_30():
    rows = [_row("anchor", 0)]
    rows += [_row(f"a{i}", 15) for i in range(40)]
    g = _build_g(rows)
    res = ab.aov_growth_cohort(g, {}, {})
    assert res.play_id == "aov_momentum"
    assert res.audience_size == 40
    assert res.preliminary_rejection_reason is None


def test_aov_growth_cohort_too_small_rejects():
    rows = [_row("anchor", 0)]
    rows += [_row(f"a{i}", 15) for i in range(5)]
    g = _build_g(rows)
    res = ab.aov_growth_cohort(g, {}, {})
    assert res.audience_size == 5
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# retention_at_risk
# ---------------------------------------------------------------------------


def test_retention_at_risk_finds_valuable_inactive():
    rows = [_row("anchor", 0)]  # holds anchor at maxd=ANCHOR
    # 30 valuable inactive customers (2+ historical orders, 60 days idle).
    for i in range(30):
        rows.append(_row(f"v{i}", 200))
        rows.append(_row(f"v{i}", 60))
    # 20 single-purchase inactive customers (excluded).
    for i in range(20):
        rows.append(_row(f"s{i}", 60))
    g = _build_g(rows)
    res = ab.retention_at_risk(g, {}, {})
    assert res.play_id == "retention_mastery"
    assert res.audience_size == 30
    assert res.preliminary_rejection_reason is None


def test_retention_at_risk_under_threshold():
    rows = [_row("anchor", 0)]
    for i in range(5):
        rows.append(_row(f"v{i}", 200))
        rows.append(_row(f"v{i}", 60))
    g = _build_g(rows)
    res = ab.retention_at_risk(g, {}, {})
    assert res.audience_size == 5
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# journey_one_purchase_cohort
# ---------------------------------------------------------------------------


def test_journey_one_purchase_cohort_recent_60d():
    rows = [_row(f"j{i}", 30) for i in range(60)]
    g = _build_g(rows)
    res = ab.journey_one_purchase_cohort(g, {}, {})
    assert res.play_id == "journey_optimization"
    assert res.audience_size == 60
    assert res.preliminary_rejection_reason is None


def test_journey_one_purchase_cohort_rejects_small():
    rows = [_row(f"j{i}", 30) for i in range(10)]
    g = _build_g(rows)
    res = ab.journey_one_purchase_cohort(g, {}, {})
    assert res.audience_size == 10
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# single_category_buyers
# ---------------------------------------------------------------------------


def test_single_category_buyers_picks_single_lineitem_repeats():
    rows = []
    # 50 customers with 2 orders of the same lineitem.
    for i in range(50):
        rows.append(_row(f"s{i}", 60, lineitem="OneSKU"))
        rows.append(_row(f"s{i}", 30, lineitem="OneSKU"))
    # 10 customers with 2 orders of two distinct lineitems (excluded).
    for i in range(10):
        rows.append(_row(f"m{i}", 60, lineitem="A"))
        rows.append(_row(f"m{i}", 30, lineitem="B"))
    g = _build_g(rows)
    res = ab.single_category_buyers(g, {}, {})
    assert res.play_id == "category_expansion"
    assert res.audience_size == 50
    assert res.preliminary_rejection_reason is None


def test_single_category_buyers_threshold_rejects():
    rows = []
    for i in range(5):
        rows.append(_row(f"s{i}", 60, lineitem="OneSKU"))
        rows.append(_row(f"s{i}", 30, lineitem="OneSKU"))
    g = _build_g(rows)
    res = ab.single_category_buyers(g, {}, {})
    assert res.audience_size == 5
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# single_purchase_cohort (first_to_second_purchase)
# ---------------------------------------------------------------------------


def test_single_purchase_cohort_finds_first_orderers():
    rows = []
    # 70 single-order customers
    for i in range(70):
        rows.append(_row(f"f{i}", 30))
    # 5 multi-order customers (excluded)
    for i in range(5):
        rows.append(_row(f"r{i}", 60))
        rows.append(_row(f"r{i}", 30))
    g = _build_g(rows)
    res = ab.single_purchase_cohort(g, {}, {})
    assert res.play_id == "first_to_second_purchase"
    assert res.audience_size == 70
    assert res.preliminary_rejection_reason is None


def test_single_purchase_cohort_threshold_rejects():
    rows = [_row(f"f{i}", 30) for i in range(10)]
    g = _build_g(rows)
    res = ab.single_purchase_cohort(g, {}, {})
    assert res.audience_size == 10
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# Builder registry coverage
# ---------------------------------------------------------------------------


def test_builders_registered_for_legacy_play_refs():
    """Every legacy emitted play in the registry resolves to a builder."""

    from src.play_registry import PLAYS

    legacy_emitted = {
        "winback_21_45",
        "bestseller_amplify",
        "discount_hygiene",
        "subscription_nudge",
        "routine_builder",
        "empty_bottle",
        "frequency_accelerator",
        "aov_momentum",
        "retention_mastery",
        "journey_optimization",
        "category_expansion",
    }
    missing = []
    for pid in legacy_emitted:
        play_def = PLAYS[pid]
        if ab.get_builder(play_def.audience_builder_ref) is None:
            missing.append((pid, play_def.audience_builder_ref))
    assert not missing, f"missing builders for: {missing}"


def test_audience_result_carries_no_forbidden_fields():
    """AudienceResult MUST NOT carry stats/scoring fields."""

    res = ab.AudienceResult(
        play_id="winback_21_45",
        segment_definition="x",
        audience_size=0,
    )
    forbidden = {
        "p",
        "p_value",
        "q",
        "q_value",
        "ci_low",
        "ci_high",
        "score",
        "rank",
        "confidence",
        "revenue",
        "expected_$",
        "measured_effect",
    }
    for f in forbidden:
        assert not hasattr(res, f), f"AudienceResult unexpectedly carries '{f}'"
