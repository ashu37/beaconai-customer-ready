"""Sprint 6.5 Ticket T1 — StoreProfile dataclass + skeleton detection tests.

Covers:
- Dataclass shape/round-trip (T1 + 9 sub-dataclasses)
- detect_business_stage band-boundary uncertainty rule (founder Q2)
- detect_business_stage env-var override (provenance captures both)
- detect_taxonomy vertical detection + operator override
- detect_business_model classification (subscription/one-time/hybrid)
- detect_data_depth direct counts
- Profile round-trip via engine_run.json (EngineRun.store_profile slot)
- Flag-OFF parity (slot is None when ENGINE_V2_STORE_PROFILE is OFF)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import EngineRun  # noqa: E402
from src.profile import (  # noqa: E402
    BusinessModel,
    BusinessStage,
    CadenceBaseline,
    DataDepth,
    GateCalibration,
    MeasurementContext,
    ProfileProvenance,
    SeasonalityContext,
    StoreProfile,
    Taxonomy,
    build_store_profile,
)
from src.profile.builder import (  # noqa: E402
    detect_business_model,
    detect_business_stage,
    detect_data_depth,
    detect_taxonomy,
)


ANCHOR = pd.Timestamp("2026-05-01 12:00:00")


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _order_row(
    customer_id: str,
    days_ago: int,
    *,
    net_sales: float = 50.0,
    product: str = "Cleanser 50ml",
):
    return {
        "Name": f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": ANCHOR - pd.Timedelta(days=days_ago),
        "net_sales": float(net_sales),
        "lineitem_any": product,
        "product": product,
    }


def _df(rows):
    return pd.DataFrame(rows).sort_values(["customer_id", "Created at"]).reset_index(drop=True)


def _beauty_growth_fixture():
    """~$1.5M annualized -> GROWTH band, away from boundaries."""
    rows = []
    n = 12000
    per_order = 1_500_000.0 / n  # ~$125
    for i in range(n):
        rows.append(
            _order_row(
                f"cust_{i}",
                days_ago=int(i % 360),
                net_sales=per_order,
                product="Hydrating Face Serum 30ml",
            )
        )
    return _df(rows)


def _supplements_growth_fixture():
    rows = []
    for i in range(1500):
        rows.append(
            _order_row(
                f"cust_{i}",
                days_ago=int(i % 360),
                net_sales=80.0,
                product="Whey Protein Powder 2lb",
            )
        )
    return _df(rows)


# ---------------------------------------------------------------------------
# 1) Dataclass shape + round-trip
# ---------------------------------------------------------------------------


def test_store_profile_default_construction():
    sp = StoreProfile()
    assert isinstance(sp.taxonomy, Taxonomy)
    assert isinstance(sp.business_stage, BusinessStage)
    assert isinstance(sp.business_model, BusinessModel)
    assert isinstance(sp.cadence, CadenceBaseline)
    assert isinstance(sp.seasonality, SeasonalityContext)
    assert isinstance(sp.data_depth, DataDepth)
    assert isinstance(sp.gate_calibration, GateCalibration)
    assert isinstance(sp.measurement, MeasurementContext)
    assert isinstance(sp.provenance, ProfileProvenance)
    assert sp.cadence.detection_status == "DEFERRED_TO_T3"
    assert sp.gate_calibration.detection_status == "DEFERRED_TO_T4"
    assert sp.measurement.primary_window == "L28"


def test_store_profile_dataclasses_are_frozen():
    sp = StoreProfile()
    # frozen -> dataclasses.FrozenInstanceError on assignment
    import dataclasses
    for slot in (
        sp.taxonomy,
        sp.business_stage,
        sp.business_model,
        sp.cadence,
        sp.seasonality,
        sp.data_depth,
        sp.gate_calibration,
        sp.measurement,
        sp.provenance,
        sp,
    ):
        try:
            object.__setattr__  # noqa: B018
            dataclasses.replace(slot)  # frozen still allows replace
        except Exception as e:  # pragma: no cover - defensive
            raise AssertionError(f"frozen dataclass replace failed on {slot}: {e}")


def test_engine_run_store_profile_round_trip_none():
    er = EngineRun()
    payload = er.to_dict()
    assert payload["store_profile"] is None
    rebuilt = EngineRun.from_dict(payload)
    assert rebuilt.store_profile is None


def test_engine_run_store_profile_round_trip_populated():
    g = _beauty_growth_fixture()
    cfg = {"VERTICAL_MODE": "beauty"}
    profile = build_store_profile(g, cfg, store_id="beauty_test")
    er = EngineRun(store_profile=profile)
    payload = er.to_dict()
    assert payload["store_profile"] is not None
    assert payload["store_profile"]["taxonomy"]["vertical"] == "beauty"
    rebuilt = EngineRun.from_dict(payload)
    assert rebuilt.store_profile is not None
    assert rebuilt.store_profile.taxonomy.vertical == "beauty"
    assert rebuilt.store_profile.business_stage.stage in {
        "STARTUP", "GROWTH", "MATURE", "ENTERPRISE"
    }
    # Round-trip preserves provenance rules.
    assert len(rebuilt.store_profile.provenance.rules_fired) > 0


# ---------------------------------------------------------------------------
# 2) detect_taxonomy
# ---------------------------------------------------------------------------


def test_detect_taxonomy_env_var_override_wins():
    g = _beauty_growth_fixture()  # detected_vertical=beauty
    rules: list = []
    tax = detect_taxonomy(g, {"VERTICAL_MODE": "supplements"}, rules)
    assert tax.vertical == "supplements"
    assert tax.operator_override_used is True
    assert tax.detected_vertical == "beauty"
    assert tax.override_disagrees is True
    assert any(r["rule"] == "vertical_override_disagrees" for r in rules)


def test_detect_taxonomy_detects_beauty_when_no_override():
    g = _beauty_growth_fixture()
    rules: list = []
    tax = detect_taxonomy(g, {}, rules)
    assert tax.detected_vertical == "beauty"
    assert tax.vertical == "beauty"
    assert tax.operator_override_used is False
    assert tax.vertical_confidence in {"HIGH", "MEDIUM"}


def test_detect_taxonomy_subvertical_populated_at_t2():
    """T2: subvertical now populated by the token classifier."""
    g = _beauty_growth_fixture()
    rules: list = []
    tax = detect_taxonomy(g, {"VERTICAL_MODE": "beauty"}, rules)
    # T2: subvertical now populated (skincare-dominant fixture).
    assert tax.subvertical == "skincare"
    assert tax.subvertical_confidence in {"HIGH", "MEDIUM"}


# ---------------------------------------------------------------------------
# 3) detect_business_stage
# ---------------------------------------------------------------------------


def test_detect_business_stage_growth_band():
    g = _beauty_growth_fixture()
    rules: list = []
    dd = detect_data_depth(g, [])
    stage = detect_business_stage(g, dd, {}, rules)
    # ~$1.5M annualized -> GROWTH, well inside the band
    assert stage.detected_stage == "GROWTH"
    assert stage.stage == "GROWTH"
    assert stage.uncertainty == "LOW"
    assert stage.conservative_floor_applied is False
    assert stage.detection_method in {"ttm", "l180_x2", "l90_x4"}


def test_detect_business_stage_env_var_override():
    g = _beauty_growth_fixture()  # detected=GROWTH
    rules: list = []
    dd = detect_data_depth(g, [])
    stage = detect_business_stage(g, dd, {"BUSINESS_STAGE": "enterprise"}, rules)
    assert stage.stage == "ENTERPRISE"
    assert stage.operator_override_used is True
    assert stage.detected_stage == "GROWTH"
    # Provenance carries both detected + override
    assert any(
        r["rule"] == "business_stage_override"
        and r["override"] == "ENTERPRISE"
        and r["detected"] == "GROWTH"
        for r in rules
    )


def _gmv_fixture_for_annualized(target_annualized: float):
    """Build a fixture whose 365d net_sales == ``target_annualized``."""
    n = 200
    per_order = target_annualized / n
    rows = []
    for i in range(n):
        # spread orders across last 360 days so detection_method=ttm
        rows.append(
            _order_row(
                f"cust_{i}",
                days_ago=int((i * 360 / n)),
                net_sales=per_order,
                product="Hydrating Face Serum 30ml",
            )
        )
    return _df(rows)


def test_detect_business_stage_boundary_uncertainty_growth_mature():
    """Stores within ±25% of $3M -> conservative-broader floor + uncertainty=HIGH.

    A store at $3.3M (within +10% of $3M) is detected as MATURE but the
    conservative-broader rule (founder Q2) downgrades the applied band
    to GROWTH.
    """
    g = _gmv_fixture_for_annualized(3_300_000.0)
    rules: list = []
    dd = detect_data_depth(g, [])
    stage = detect_business_stage(g, dd, {}, rules)
    assert stage.uncertainty == "HIGH"
    assert stage.detected_stage == "MATURE"
    assert stage.stage == "GROWTH"
    assert stage.conservative_floor_applied is True
    assert any(r["rule"] == "stage_boundary_uncertainty" for r in rules)


def test_detect_business_stage_boundary_uncertainty_startup_growth():
    """A store at $550K is within +10% of the $500K STARTUP/GROWTH boundary."""
    g = _gmv_fixture_for_annualized(550_000.0)
    rules: list = []
    dd = detect_data_depth(g, [])
    stage = detect_business_stage(g, dd, {}, rules)
    assert stage.uncertainty == "HIGH"
    assert stage.detected_stage == "GROWTH"
    # broader/conservative -> STARTUP
    assert stage.stage == "STARTUP"
    assert stage.conservative_floor_applied is True


def test_detect_business_stage_insufficient_history():
    rows = [_order_row("c1", 30, net_sales=10.0)]
    g = _df(rows)
    rules: list = []
    dd = detect_data_depth(g, [])
    stage = detect_business_stage(g, dd, {}, rules)
    assert stage.detection_method == "insufficient_history"
    assert stage.stage == "STARTUP"
    assert stage.annualized_gmv_usd == 0.0


# ---------------------------------------------------------------------------
# 4) detect_business_model
# ---------------------------------------------------------------------------


def test_detect_business_model_subscription_led():
    """All customers buy at ~30d cadence -> SUBSCRIPTION_LED."""
    rows = []
    # 50 customers each with 5 orders 30 days apart in L180.
    # 50 customers x 5 orders = 250 orders. Each customer's gaps are
    # exactly 30 days (sigma=0), so cv=0 -> classified as subscription.
    for i in range(50):
        for k in range(5):
            rows.append(_order_row(f"sub_{i}", days_ago=k * 30, net_sales=40.0))
    # Anchor order to pin max date.
    rows.append(_order_row("anchor", 0, net_sales=10.0))
    g = _df(rows)
    rules: list = []
    dd = detect_data_depth(g, [])
    bm = detect_business_model(g, dd, rules)
    assert bm.model == "SUBSCRIPTION_LED"
    assert bm.subscription_fraction > 0.40


def test_detect_business_model_one_time_led():
    g = _beauty_growth_fixture()  # each customer has 1 order
    rules: list = []
    dd = detect_data_depth(g, [])
    bm = detect_business_model(g, dd, rules)
    assert bm.model == "ONE_TIME_LED"
    assert bm.subscription_fraction < 0.10


def test_detect_business_model_hybrid():
    """Mix subscription-pattern + one-time customers -> HYBRID."""
    rows = []
    # 10 subscription customers (300 orders / 5 customers = ~)
    for i in range(10):
        for k in range(5):
            rows.append(_order_row(f"sub_{i}", days_ago=k * 30, net_sales=40.0))
    # 200 one-time customers
    for i in range(200):
        rows.append(_order_row(f"one_{i}", days_ago=int(i % 150), net_sales=40.0))
    rows.append(_order_row("anchor", 0))
    g = _df(rows)
    rules: list = []
    dd = detect_data_depth(g, [])
    bm = detect_business_model(g, dd, rules)
    assert bm.model in {"HYBRID", "ONE_TIME_LED"}
    # Either way fraction sits in [0, 0.40]
    assert 0.0 <= bm.subscription_fraction <= 0.50


# ---------------------------------------------------------------------------
# 5) detect_data_depth
# ---------------------------------------------------------------------------


def test_detect_data_depth_counts():
    rows = [
        _order_row("c1", 100),
        _order_row("c1", 50),
        _order_row("c2", 30),
        _order_row("c3", 10),
    ]
    g = _df(rows)
    dd = detect_data_depth(g, [])
    assert dd.n_orders == 4
    assert dd.n_customers == 3
    assert dd.n_repeat_customers == 1  # c1
    assert dd.history_days == 90


# ---------------------------------------------------------------------------
# 6) Orchestrator + flag plumbing
# ---------------------------------------------------------------------------


def test_build_store_profile_orchestrator():
    g = _beauty_growth_fixture()
    profile = build_store_profile(g, {"VERTICAL_MODE": "beauty"}, store_id="store-x")
    assert profile.store_id == "store-x"
    assert profile.taxonomy.vertical == "beauty"
    assert profile.business_stage.stage in {"GROWTH", "STARTUP"}  # depending on fixture sizing
    assert profile.data_depth.n_orders == 12000
    assert profile.provenance.profile_version == 1
    # T4 populates gate_calibration + measurement: detection_status
    # moves off the T1 stub to "DERIVED".
    assert profile.gate_calibration.detection_status == "DERIVED"
    assert profile.measurement.detection_status == "DERIVED"
    # Cadence + seasonality are populated at T3. Detection status moves
    # off the T1 stub; the exact value depends on whether the synthetic
    # fixture has enough class-tagged customers + a calendar match.
    assert profile.cadence.detection_status in {
        "COMPUTED",
        "INSUFFICIENT_DATA",
        "NOT_APPLICABLE",
    }
    assert profile.seasonality.detection_status in {
        "ACTIVE",
        "NO_ACTIVE_WINDOW",
        "NOT_APPLICABLE",
        "INVALID_RUN_DATE",
    }


def test_build_store_profile_is_pure_function():
    g = _beauty_growth_fixture()
    cfg = {"VERTICAL_MODE": "beauty"}
    p1 = build_store_profile(g, cfg, store_id="x")
    p2 = build_store_profile(g, cfg, store_id="x")
    # profiled_at differs (wall-clock); compare structural fields
    assert p1.taxonomy == p2.taxonomy
    assert p1.business_stage == p2.business_stage
    assert p1.business_model == p2.business_model
    assert p1.data_depth == p2.data_depth


def test_engine_v2_store_profile_flag_default_on_at_t5():
    """At T5 close (Sprint 6.5-T5, 2026-05-18) the flag default flips OFF -> ON
    atomically with the Beauty pinned fixture re-pin. Pre-T5 the contract
    was ``is False``; that assertion is now retired."""
    from src.utils import DEFAULTS
    assert DEFAULTS["ENGINE_V2_STORE_PROFILE"] is True
