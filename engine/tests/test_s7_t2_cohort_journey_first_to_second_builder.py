"""Sprint 7 Ticket T2 — cohort_journey_first_to_second builder tests.

Covers the new prior-anchored Tier-B builder that retires the Phase 5.6
``first_to_second_purchase`` directional proxy (legacy proxy is NOT
deleted at T2 per IM preserved-out-of-scope discipline; the new builder
ships behind ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND=false). The
builder anchors on the validated_external
``first_to_second_purchase.base_rate.*`` prior (S7.5-T2 promotion,
effective_n=156110, wildcard vertical) via
``measurement_builder.build_prior_anchored_play_card``.

Per IM plan §S7-T2 + S7 planning refresh: this is the lowest-risk
S7 ticket — no new research blocker, no new prior memo required.

Flag default OFF at T2; S7-T2.5 owns the atomic flip + fixture re-pin.
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
    RevenueRangeSource,
    WouldBeMeasuredBy,
)
from src.priors_loader import (  # noqa: E402
    AudienceArchetype,
    PriorValidationStatus,
    clear_cache,
)
from src.utils import DEFAULTS  # noqa: E402


ANCHOR = pd.Timestamp("2026-05-01 12:00:00")


# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------


def _row(customer_id: str, days_ago: int, *, net: float = 30.0):
    created = ANCHOR - pd.Timedelta(days=days_ago)
    return {
        "Name": f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": created,
        "net_sales": net,
        "lineitem_any": "Generic Product",
    }


def _make_g(rows):
    return (
        pd.DataFrame(rows)
        .sort_values(["customer_id", "Created at"])
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# T1: in-window single-purchase cohort fires
# ---------------------------------------------------------------------------


def test_t1_in_window_single_purchase_cohort_fires():
    rows = [_row("anchor", 0)]
    # 5 customers with their only purchase 45 days ago — squarely in
    # the (30, 90] window.
    for i in range(5):
        rows.append(_row(f"c{i}", 45))
    g = _make_g(rows)
    res = ab.cohort_journey_first_to_second_candidates(g, {}, {})
    assert res.play_id == "cohort_journey_first_to_second"
    # 5 customers in window; anchor is excluded (its only order is 0d
    # ago, which is OUTSIDE the 30-90d window).
    assert res.audience_size == 5
    assert res.preliminary_rejection_reason is None
    assert all(cid.startswith("c") for cid in res.audience_ids)


# ---------------------------------------------------------------------------
# T2: first purchase BEFORE the window (>90d ago) is excluded
# ---------------------------------------------------------------------------


def test_t2_first_purchase_before_window_excluded():
    rows = [_row("anchor", 0)]
    # 5 customers whose only purchase is 120 days ago — too OLD.
    for i in range(5):
        rows.append(_row(f"old{i}", 120))
    g = _make_g(rows)
    res = ab.cohort_journey_first_to_second_candidates(g, {}, {})
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# T3: first purchase AFTER the window (<30d ago) is excluded
# ---------------------------------------------------------------------------


def test_t3_first_purchase_after_window_excluded():
    rows = [_row("anchor", 0)]
    # 5 customers whose only purchase is 15 days ago — too NEW.
    for i in range(5):
        rows.append(_row(f"new{i}", 15))
    g = _make_g(rows)
    res = ab.cohort_journey_first_to_second_candidates(g, {}, {})
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# T4: customers with TWO+ purchases are excluded (no longer one-and-done)
# ---------------------------------------------------------------------------


def test_t4_customers_with_second_purchase_excluded():
    rows = [_row("anchor", 0)]
    # Repeat buyers (2 orders, most recent at 45d) — must be EXCLUDED
    # because they already made their second purchase.
    for i in range(5):
        rows.append(_row(f"rep{i}", 60))
        rows.append(_row(f"rep{i}", 45))
    # First-time buyer in window (should be INCLUDED).
    rows.append(_row("first1", 45))
    g = _make_g(rows)
    res = ab.cohort_journey_first_to_second_candidates(g, {}, {})
    assert res.audience_size == 1
    assert res.audience_ids == {"first1"}


# ---------------------------------------------------------------------------
# T5: boundary days — 30 and 90 both inclusive
# ---------------------------------------------------------------------------


def test_t5_window_boundary_inclusive_30_and_90():
    rows = [_row("anchor", 0)]
    rows.append(_row("at_30", 30))
    rows.append(_row("at_90", 90))
    rows.append(_row("at_29", 29))  # just OUTSIDE (too new)
    rows.append(_row("at_91", 91))  # just OUTSIDE (too old)
    g = _make_g(rows)
    res = ab.cohort_journey_first_to_second_candidates(g, {}, {})
    assert res.audience_ids == {"at_30", "at_90"}


# ---------------------------------------------------------------------------
# T6: ranking_strategy kwarg is accepted, validated, ignored (no-op)
# ---------------------------------------------------------------------------


def test_t6_ranking_strategy_kwarg_is_noop():
    rows = [_row("anchor", 0)] + [_row(f"c{i}", 45) for i in range(3)]
    g = _make_g(rows)
    # No kwarg.
    r_none = ab.cohort_journey_first_to_second_candidates(g, {}, {})
    # str kwarg (Sprint 13 hook value).
    r_str = ab.cohort_journey_first_to_second_candidates(
        g, {}, {}, ranking_strategy="predicted_ltv_desc"
    )
    # Non-str kwarg silently coerced to None.
    r_bad = ab.cohort_journey_first_to_second_candidates(
        g, {}, {}, ranking_strategy=42  # type: ignore[arg-type]
    )
    assert r_none.audience_size == r_str.audience_size == r_bad.audience_size
    assert r_none.audience_ids == r_str.audience_ids == r_bad.audience_ids


# ---------------------------------------------------------------------------
# T7: empty dataframe / missing columns → data_missing, no crash
# ---------------------------------------------------------------------------


def test_t7_empty_dataframe_data_missing():
    res = ab.cohort_journey_first_to_second_candidates(
        pd.DataFrame(), {}, {}
    )
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "data_missing"


def test_t7b_missing_customer_id_column_data_missing():
    g = pd.DataFrame({"Created at": [ANCHOR]})
    res = ab.cohort_journey_first_to_second_candidates(g, {}, {})
    assert res.preliminary_rejection_reason == "data_missing"


# ---------------------------------------------------------------------------
# T8: registered in BUILDERS dict + play_registry
# ---------------------------------------------------------------------------


def test_t8_builder_registered_in_BUILDERS_and_play_registry():
    assert "audience.cohort_journey_first_to_second" in ab.BUILDERS
    assert (
        ab.BUILDERS["audience.cohort_journey_first_to_second"]
        is ab.cohort_journey_first_to_second_candidates
    )
    from src.play_registry import PLAYS
    assert "cohort_journey_first_to_second" in PLAYS
    pdef = PLAYS["cohort_journey_first_to_second"]
    assert pdef.audience_builder_ref == "audience.cohort_journey_first_to_second"
    assert "base_rate" in pdef.prior_keys


# ---------------------------------------------------------------------------
# T9: flag default ON post S7-T2.5 (atomic flip + Beauty fixture re-pin)
# ---------------------------------------------------------------------------


def test_t9_default_flag_on_post_t2_5():
    # S7-T2.5 (2026-05-21): flipped from False -> True atomically with the
    # Beauty pinned slate re-pin (sha256 3d7ef3d7...). Operator override
    # ``ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND=false`` rolls back to
    # T2-close behavior in one env var (Sprint 2 Risk #4 contract).
    assert DEFAULTS.get("ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND", None) is True


def test_t9b_main_filters_play_from_registry_under_flag_off():
    # Mirror the conditional in src/main.py: when flag OFF, the
    # cohort_journey_first_to_second play is filtered OUT of
    # candidate-detection so pinned-fixture sha256 byte-identity holds.
    from src.play_registry import PLAYS
    cfg_off = {"ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND": False}
    if not bool(cfg_off.get("ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND", False)):
        filtered = {
            k: v for k, v in PLAYS.items()
            if k != "cohort_journey_first_to_second"
        }
    else:
        filtered = dict(PLAYS)
    assert "cohort_journey_first_to_second" not in filtered
    cfg_on = {"ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND": True}
    if not bool(cfg_on.get("ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND", False)):
        filtered2 = {
            k: v for k, v in PLAYS.items()
            if k != "cohort_journey_first_to_second"
        }
    else:
        filtered2 = dict(PLAYS)
    assert "cohort_journey_first_to_second" in filtered2


# ---------------------------------------------------------------------------
# T10: legacy first_to_second_purchase proxy preserved (NOT deleted)
# ---------------------------------------------------------------------------


def test_t10_legacy_proxy_preserved_in_directional_supported():
    # IM preserved-out-of-scope discipline: one sprint of cushion past
    # T2.5 before any deletion. The legacy Phase 5.6 directional builder
    # entry MUST still exist after T2.
    assert "first_to_second_purchase" in mb._SUPPORTED
    # And the legacy single_purchase_cohort audience builder + registry
    # entry MUST still resolve.
    assert "audience.single_purchase_cohort" in ab.BUILDERS
    from src.play_registry import PLAYS
    assert "first_to_second_purchase" in PLAYS


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
# T11: prior-anchored card on Beauty fires with validated_external + BLEND
# ---------------------------------------------------------------------------


def test_t11_beauty_card_validated_external_blend():
    """The wildcard validated_external prior must fire BLEND on Beauty."""
    clear_cache()
    cand = _candidate("cohort_journey_first_to_second", audience_size=200)
    aligned = _aligned_with_aov(50.0)
    card = mb.build_prior_anchored_play_card(cand, aligned, vertical="beauty")
    assert card is not None
    assert card.play_id == "cohort_journey_first_to_second"
    assert card.evidence_class == EvidenceClass.DIRECTIONAL
    assert card.would_be_measured_by == WouldBeMeasuredBy.FIRST_TO_SECOND_PURCHASE_IN_30D
    rr = card.revenue_range
    assert rr.suppressed is False
    assert rr.source == RevenueRangeSource.BLEND
    bp = next(
        (d for d in rr.drivers if isinstance(d, dict) and d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    assert bp["prior_validation_status"] == PriorValidationStatus.VALIDATED_EXTERNAL.value
    # Wildcard prior — applies_to.vertical == "*".
    assert bp["applies_to"].get("vertical") == "*"


# ---------------------------------------------------------------------------
# T12: supplements path ALSO fires (wildcard prior — symmetric activation)
# ---------------------------------------------------------------------------


def test_t12_supplements_card_also_fires_wildcard_prior():
    """Unlike replenishment_due (asymmetric by design), the
    first_to_second_purchase.base_rate prior is wildcard so supplements
    ALSO activates a validated_external card via the wildcard match path.
    """
    clear_cache()
    cand = _candidate("cohort_journey_first_to_second", audience_size=200)
    aligned = _aligned_with_aov(50.0)
    card = mb.build_prior_anchored_play_card(
        cand, aligned, vertical="supplements"
    )
    assert card is not None
    assert card.play_id == "cohort_journey_first_to_second"
    rr = card.revenue_range
    assert rr.suppressed is False
    bp = next(
        (d for d in rr.drivers if isinstance(d, dict) and d.get("name") == "blend_provenance"),
        None,
    )
    assert bp is not None
    assert bp["prior_validation_status"] == PriorValidationStatus.VALIDATED_EXTERNAL.value


# ---------------------------------------------------------------------------
# T13: enum cross-pin (S6-T3.5 latent-bug-class guard)
# ---------------------------------------------------------------------------


def test_t13_enum_cross_pin_first_to_second_purchase_in_30d():
    """Cross-pin the new WouldBeMeasuredBy member and confirm the
    AudienceArchetype FIRST_TIME_BUYER value still resolves. Latent
    enum-missing bugs are silent (lazy import in storytelling_v2 +
    decide.py swallow PriorsMetadataError) so explicit cross-pinning is
    load-bearing per the S6-T3.5 CADENCE_DUE_REPEAT_BUYER precedent.
    """
    assert (
        WouldBeMeasuredBy("FIRST_TO_SECOND_PURCHASE_IN_30D")
        is WouldBeMeasuredBy.FIRST_TO_SECOND_PURCHASE_IN_30D
    )
    # A2 round-trip: value == name.
    assert (
        WouldBeMeasuredBy.FIRST_TO_SECOND_PURCHASE_IN_30D.value
        == WouldBeMeasuredBy.FIRST_TO_SECOND_PURCHASE_IN_30D.name
    )
    # AudienceArchetype.FIRST_TIME_BUYER is the Contract-Q3 lowercase
    # value; do NOT migrate or rename. The first_to_second_purchase
    # priors block metadata uses "first_time_buyer" (lowercase).
    assert (
        AudienceArchetype("first_time_buyer")
        is AudienceArchetype.FIRST_TIME_BUYER
    )


# ---------------------------------------------------------------------------
# T14: _PRIOR_ANCHORED dispatch entry pins the prior anchor
# ---------------------------------------------------------------------------


def test_t14_prior_anchored_dispatch_entry_pins_prior():
    """The new dispatch entry MUST resolve to the validated_external
    first_to_second_purchase.base_rate prior — not a sibling like
    second_purchase_lift (placeholder) or incrementality (heuristic).
    """
    entry = mb._PRIOR_ANCHORED["cohort_journey_first_to_second"]
    assert entry.play_id == "cohort_journey_first_to_second"
    assert entry.prior_play_id == "first_to_second_purchase"
    assert entry.prior_key == "base_rate"
    assert entry.would_be_measured_by == WouldBeMeasuredBy.FIRST_TO_SECOND_PURCHASE_IN_30D


# ---------------------------------------------------------------------------
# T15: D-FLOOR-cohort_journey_first_to_second floor-resolver cell coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "vertical,subvertical,stage,expected",
    [
        ("beauty", "skincare", "STARTUP", 40),
        ("beauty", "cosmetics", "GROWTH", 100),
        ("beauty", "haircare", "MATURE", 300),
        ("beauty", "personal_care", "ENTERPRISE", 1000),
        ("supplements", "protein", "STARTUP", 40),
        ("supplements", "multivitamin", "GROWTH", 100),
        ("supplements", "probiotics", "MATURE", 300),
        ("supplements", "nootropics", "ENTERPRISE", 1000),
        ("supplements", "functional", "GROWTH", 100),
    ],
)
def test_t15_floor_resolver_cell_coverage(vertical, subvertical, stage, expected):
    from src.profile.builder import (
        _resolve_audience_floor_cell_strict,
        load_gate_calibration,
    )
    yaml_block = load_gate_calibration()
    rules_fired: list = []
    floor, source = _resolve_audience_floor_cell_strict(
        yaml_block,
        play_id="cohort_journey_first_to_second",
        vertical=vertical,
        subvertical=subvertical,
        stage=stage,
        rules_fired=rules_fired,
    )
    assert floor == expected, (
        f"floor mismatch for ({vertical}, {subvertical}, {stage}): "
        f"got {floor}, expected {expected}"
    )
    assert source is not None


@pytest.mark.parametrize(
    "vertical,stage,expected",
    [
        ("beauty", "STARTUP", 60),
        ("beauty", "GROWTH", 150),
        ("beauty", "MATURE", 450),
        ("beauty", "ENTERPRISE", 1500),
        ("supplements", "STARTUP", 60),
        ("supplements", "GROWTH", 150),
        ("supplements", "MATURE", 450),
        ("supplements", "ENTERPRISE", 1500),
    ],
)
def test_t15b_floor_resolver_mixed_fallback(vertical, stage, expected):
    """REFUSED subvertical falls through to the matching mixed_<vertical>
    row. Per the D-FLOOR-cohort_journey_first_to_second grid: 1.5×
    the per-subvertical cell (60 / 150 / 450 / 1500)."""
    from src.profile.builder import (
        _resolve_audience_floor_cell_strict,
        load_gate_calibration,
    )
    yaml_block = load_gate_calibration()
    rules_fired: list = []
    floor, source = _resolve_audience_floor_cell_strict(
        yaml_block,
        play_id="cohort_journey_first_to_second",
        vertical=vertical,
        subvertical="other_refused",
        stage=stage,
        rules_fired=rules_fired,
    )
    assert floor == expected
    assert source is not None
    # The mixed_<vertical> fallback path must record the rule.
    assert any(
        r.get("rule") == "gate_calibration_mixed_vertical_fallback"
        for r in rules_fired
    )
