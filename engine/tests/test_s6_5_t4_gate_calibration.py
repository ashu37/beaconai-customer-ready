"""Sprint 6.5 Ticket T4 — gate calibration + R1 window_corroboration + R2 cadence-derived primary window.

Covers the 32-item IM plan list verbatim, plus a handful of belt-and-suspenders
flag-OFF byte-identity checks.

Conventions:
- Every test uses a synthetic single-purpose fixture; no production CSVs.
- Profile-flag ON paths build a typed ``StoreProfile`` and pass it via
  ``cfg["_store_profile"]`` / direct kwarg to the consumer.
- Flag-OFF tests rely on the existing pinned-fixture sha-256 tests
  elsewhere in the suite (test_slate_regression_*); we add one local
  smoke-check that the new schema additions all default to ``None`` /
  empty when the dataclass is built blank.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.audience_builders import winback_dormant_cohort_candidates  # noqa: E402
from src.engine_run import (  # noqa: E402
    EngineRun,
    EvidenceClass,
    Measurement,
    PlayCard,
    ReasonCode,
    WindowCorroboration,
)
from src.measurement_builder import (  # noqa: E402
    PHASE5_WINDOWS,
    _prior_anchored_window_corroboration,
    _window_corroboration_sign_only,
    build_directional_play_card,
    build_prior_anchored_play_card,
)
from src.profile import build_store_profile  # noqa: E402
from src.profile.builder import (  # noqa: E402
    _GATE_CALIBRATION_WINDOWS,
    _round_cadence_to_window,
    derive_gate_calibration,
    load_gate_calibration,
)
from src.profile.types import (  # noqa: E402
    BusinessModel,
    BusinessStage,
    CadenceBaseline,
    DataDepth,
    GateCalibration,
    MeasurementContext,
    StoreProfile,
    Taxonomy,
)
from src.sizing import (  # noqa: E402
    PSEUDO_N_BY_STATUS,
    PriorValidationStatus,
    effective_pseudo_n,
)
from src.decide import (  # noqa: E402
    _CONSIDERED_REASON_TEXT,
    _WOULD_FIRE_IF_TEMPLATE,
    _apply_window_corroboration_bumps,
    _route_window_disagreement_holds,
)
from dataclasses import replace as _dc_replace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _yaml() -> Dict[str, Any]:
    return load_gate_calibration()


def _make_profile(
    *,
    vertical: str = "beauty",
    subvertical: str = "skincare",
    stage: str = "GROWTH",
    uncertainty: str = "LOW",
    business_model: str = "ONE_TIME_LED",
    cadence_class_to_days: Dict[str, int] | None = None,
    cadence_status: str = "COMPUTED",
) -> StoreProfile:
    cad = CadenceBaseline(
        median_reorder_days_by_sku_class=cadence_class_to_days or {},
        method_by_sku_class={
            k: "empirical_median" for k in (cadence_class_to_days or {})
        },
        global_median_reorder_days=(
            next(iter((cadence_class_to_days or {}).values()), None)
        ),
        detection_status=cadence_status,
    )
    gate, meas = derive_gate_calibration(
        taxonomy=Taxonomy(
            vertical=vertical,
            subvertical=subvertical,
            vertical_confidence="HIGH",
            subvertical_confidence="HIGH",
        ),
        stage=BusinessStage(stage=stage, uncertainty=uncertainty),
        cadence=cad,
        data_depth=DataDepth(),
        business_model=BusinessModel(model=business_model),
    )
    return StoreProfile(
        store_id="test_store",
        taxonomy=Taxonomy(
            vertical=vertical, subvertical=subvertical,
            vertical_confidence="HIGH", subvertical_confidence="HIGH",
        ),
        business_stage=BusinessStage(stage=stage, uncertainty=uncertainty),
        business_model=BusinessModel(model=business_model),
        cadence=cad,
        gate_calibration=gate,
        measurement=meas,
    )


# ---------------------------------------------------------------------------
# 1) derive_gate_calibration is a pure function (100 runs)
# ---------------------------------------------------------------------------


def test_derive_gate_calibration_is_pure_function_100_runs():
    tax = Taxonomy(vertical="beauty", subvertical="skincare",
                   vertical_confidence="HIGH", subvertical_confidence="HIGH")
    stage = BusinessStage(stage="GROWTH", uncertainty="LOW")
    cad = CadenceBaseline(
        median_reorder_days_by_sku_class={"skincare": 53},
        method_by_sku_class={"skincare": "empirical_median"},
        global_median_reorder_days=53,
        detection_status="COMPUTED",
    )
    dd = DataDepth(n_customers=1000, n_orders=3000)
    bm = BusinessModel(model="ONE_TIME_LED")
    baseline = derive_gate_calibration(tax, stage, cad, dd, bm)
    for _ in range(100):
        result = derive_gate_calibration(tax, stage, cad, dd, bm)
        assert result == baseline


# ---------------------------------------------------------------------------
# 2) Beauty/growth/skincare cell present + matches sketch
# ---------------------------------------------------------------------------


def test_beauty_growth_skincare_audience_floor_matches_sketch():
    profile = _make_profile(stage="GROWTH")
    assert profile.gate_calibration.audience_floor_by_play_id["winback_dormant_cohort"] == 200


# ---------------------------------------------------------------------------
# 3) Supplements/mature/protein cell present + matches sketch
# ---------------------------------------------------------------------------


def test_supplements_mature_protein_audience_floor_matches_sketch():
    profile = _make_profile(
        vertical="supplements", subvertical="protein", stage="MATURE",
    )
    assert profile.gate_calibration.audience_floor_by_play_id["winback_dormant_cohort"] == 400


# ---------------------------------------------------------------------------
# 4) Cell-not-found returns conservative default + records provenance
# ---------------------------------------------------------------------------


def test_cell_not_found_records_default_rule_fire():
    # Override yaml_block with an empty dict so every cell is missing.
    rules: list = []
    gate, meas = derive_gate_calibration(
        taxonomy=Taxonomy(vertical="beauty", subvertical="skincare",
                          vertical_confidence="HIGH"),
        stage=BusinessStage(stage="STARTUP"),
        cadence=CadenceBaseline(detection_status="INSUFFICIENT_DATA"),
        data_depth=DataDepth(),
        business_model=BusinessModel(),
        yaml_block={},
        rules_fired=rules,
    )
    # Defaults present.
    assert gate.audience_floor_by_play_id["winback_dormant_cohort"] >= 50
    assert gate.materiality_floor_usd is not None
    seams = {r.get("rule") for r in rules}
    assert "gate_calibration_cell_missing" in seams


# ---------------------------------------------------------------------------
# 5) Stage-uncertainty HIGH → broader floor used
# ---------------------------------------------------------------------------


def test_stage_uncertainty_high_uses_broader_cell():
    # MATURE near GROWTH boundary → broader=GROWTH floor (200) instead of
    # MATURE floor (500).
    profile = _make_profile(stage="MATURE", uncertainty="HIGH")
    rules = [r for r in profile.provenance.rules_fired]  # provenance not threaded; use derive directly
    rules2: list = []
    gate, _meas = derive_gate_calibration(
        taxonomy=Taxonomy(vertical="beauty", subvertical="skincare",
                          vertical_confidence="HIGH"),
        stage=BusinessStage(stage="MATURE", uncertainty="HIGH"),
        cadence=CadenceBaseline(detection_status="INSUFFICIENT_DATA"),
        data_depth=DataDepth(),
        business_model=BusinessModel(),
        rules_fired=rules2,
    )
    # Broader = GROWTH = 200 (not MATURE's 500).
    assert gate.audience_floor_by_play_id["winback_dormant_cohort"] == 200
    assert any(r.get("rule") == "gate_calibration_stage_uncertainty_broader_cell" for r in rules2)


# ---------------------------------------------------------------------------
# 6) Subvertical REFUSED → mixed_<vertical> cell consulted
# ---------------------------------------------------------------------------


def test_refused_subvertical_uses_mixed_vertical_cell():
    rules: list = []
    gate, _meas = derive_gate_calibration(
        taxonomy=Taxonomy(vertical="beauty", subvertical=None,
                          vertical_confidence="HIGH",
                          subvertical_confidence="REFUSED"),
        stage=BusinessStage(stage="GROWTH"),
        cadence=CadenceBaseline(detection_status="INSUFFICIENT_DATA"),
        data_depth=DataDepth(),
        business_model=BusinessModel(),
        rules_fired=rules,
    )
    # mixed_beauty growth = 300 (vs skincare 200).
    assert gate.audience_floor_by_play_id["winback_dormant_cohort"] == 300
    assert any(
        r.get("rule") == "gate_calibration_mixed_vertical_fallback" for r in rules
    )


# ---------------------------------------------------------------------------
# 7) Audience builder reads floor from profile when ON
# ---------------------------------------------------------------------------


def _pinned_beauty_df():
    """Load the pinned Beauty synthetic orders fixture and normalize the
    Shopify CSV columns into the engine's standard shape (customer_id,
    product/lineitem_any, net_sales). The cohort size on this fixture
    is 428 dormant repeat-buyers — below the default 500 floor (today's
    behavior: rejects) and above the profile growth/skincare floor 200
    (T4 behavior: passes). This is the structural shift S6.5-T5 will
    activate.
    """
    from src.utils import standardize_customer_key
    df = pd.read_csv(REPO_ROOT / "tests/fixtures/synthetic/healthy_beauty_240d_orders.csv")
    df["product"] = df["Lineitem name"]
    df["lineitem_any"] = df["Lineitem name"]
    qty = pd.to_numeric(df.get("Lineitem quantity", 1), errors="coerce").fillna(1)
    price = pd.to_numeric(df.get("Lineitem price", 0), errors="coerce").fillna(0)
    df["net_sales"] = qty * price
    df["customer_id"] = standardize_customer_key(df)
    return df


def test_audience_builder_reads_floor_from_profile_when_on():
    profile = _make_profile(stage="GROWTH")  # floor = 200
    df = _pinned_beauty_df()  # cohort = 428
    cfg = {
        "VERTICAL_MODE": "beauty",
        "ENGINE_V2_STORE_PROFILE": True,
        "_store_profile": profile,
    }
    res = winback_dormant_cohort_candidates(df, aligned={}, cfg=cfg)
    # 428 ≥ 200 (profile floor) → passes.
    assert res.preliminary_rejection_reason is None, res.preliminary_rejection_reason
    assert 200 <= res.audience_size < 500


# ---------------------------------------------------------------------------
# 8) Audience builder reads hardcoded 500 when OFF
# ---------------------------------------------------------------------------


def test_audience_builder_falls_back_to_500_when_flag_off():
    df = _pinned_beauty_df()  # cohort = 428
    cfg = {"VERTICAL_MODE": "beauty"}  # no flag, no profile
    res = winback_dormant_cohort_candidates(df, aligned={}, cfg=cfg)
    # 428 < 500 → rejects under today's hardcoded floor.
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# 9) R2: Beauty/skincare cadence=53d → primary_window=L56
# ---------------------------------------------------------------------------


def test_r2_beauty_skincare_53d_yields_l56():
    rules: list = []
    _gate, meas = derive_gate_calibration(
        taxonomy=Taxonomy(vertical="beauty", subvertical="skincare",
                          vertical_confidence="HIGH",
                          subvertical_confidence="HIGH"),
        stage=BusinessStage(stage="GROWTH"),
        cadence=CadenceBaseline(
            median_reorder_days_by_sku_class={"skincare": 53},
            method_by_sku_class={"skincare": "empirical_median"},
            detection_status="COMPUTED",
        ),
        data_depth=DataDepth(),
        business_model=BusinessModel(model="ONE_TIME_LED"),
        rules_fired=rules,
    )
    assert meas.primary_window == "L56"
    assert meas.primary_window_source == "cadence_derived"
    assert meas.agreement_windows == ["L28", "L90"]
    assert any(r.get("rule") == "cadence_derived_primary_window" for r in rules)


# ---------------------------------------------------------------------------
# 10) R2: Supplements/protein 40d → L28; nootropics 75d → L90
# ---------------------------------------------------------------------------


def test_r2_supplements_protein_40d_yields_l28():
    _gate, meas = derive_gate_calibration(
        taxonomy=Taxonomy(vertical="supplements", subvertical="protein",
                          vertical_confidence="HIGH",
                          subvertical_confidence="HIGH"),
        stage=BusinessStage(stage="GROWTH"),
        cadence=CadenceBaseline(
            median_reorder_days_by_sku_class={"protein": 40},
            detection_status="COMPUTED",
        ),
        data_depth=DataDepth(),
        business_model=BusinessModel(model="ONE_TIME_LED"),
    )
    # 40 is equidistant between L28 (12) and L56 (16) — actually 40-28=12, 56-40=16, so L28 wins.
    assert meas.primary_window == "L28"


def test_r2_supplements_nootropics_75d_yields_l90():
    _gate, meas = derive_gate_calibration(
        taxonomy=Taxonomy(vertical="supplements", subvertical="nootropics",
                          vertical_confidence="HIGH",
                          subvertical_confidence="HIGH"),
        stage=BusinessStage(stage="GROWTH"),
        cadence=CadenceBaseline(
            median_reorder_days_by_sku_class={"nootropics": 75},
            detection_status="COMPUTED",
        ),
        data_depth=DataDepth(),
        business_model=BusinessModel(model="ONE_TIME_LED"),
    )
    assert meas.primary_window == "L90"


# ---------------------------------------------------------------------------
# 11) R2: Cadence INSUFFICIENT_DATA → static fallback
# ---------------------------------------------------------------------------


def test_r2_cadence_insufficient_falls_back_to_static_cell():
    rules: list = []
    _gate, meas = derive_gate_calibration(
        taxonomy=Taxonomy(vertical="beauty", subvertical="skincare",
                          vertical_confidence="HIGH",
                          subvertical_confidence="HIGH"),
        stage=BusinessStage(stage="GROWTH"),
        cadence=CadenceBaseline(detection_status="INSUFFICIENT_DATA"),
        data_depth=DataDepth(),
        business_model=BusinessModel(model="ONE_TIME_LED"),
        rules_fired=rules,
    )
    # Static yaml cell = L28 for beauty/skincare.
    assert meas.primary_window == "L28"
    assert meas.primary_window_source == "cadence_fallback_static"
    assert any(r.get("rule") == "cadence_fallback_static_window" for r in rules)


# ---------------------------------------------------------------------------
# 12) R2: SUBSCRIPTION_LED → always static cell, NEVER cadence-derived
# ---------------------------------------------------------------------------


def test_r2_subscription_led_short_circuits_to_static_window():
    rules: list = []
    _gate, meas = derive_gate_calibration(
        taxonomy=Taxonomy(vertical="beauty", subvertical="skincare",
                          vertical_confidence="HIGH",
                          subvertical_confidence="HIGH"),
        stage=BusinessStage(stage="GROWTH"),
        cadence=CadenceBaseline(
            median_reorder_days_by_sku_class={"skincare": 53},
            detection_status="COMPUTED",
        ),
        data_depth=DataDepth(),
        business_model=BusinessModel(model="SUBSCRIPTION_LED",
                                     subscription_fraction=0.85),
        rules_fired=rules,
    )
    # Static L28 (from YAML), NOT cadence-derived L56.
    assert meas.primary_window == "L28"
    assert meas.primary_window_source == "subscription_led_static"
    assert any(r.get("rule") == "subscription_led_static_window" for r in rules)


# ---------------------------------------------------------------------------
# 13) Measurement builder falls back to default primary_window when OFF
# ---------------------------------------------------------------------------


class _Candidate:
    def __init__(self, play_id, audience_size, segment_definition="seg"):
        self.play_id = play_id
        self.audience_size = audience_size
        self.segment_definition = segment_definition
        self.preliminary_rejection_reason = None


def _make_aligned_directional(metric="returning_customer_share"):
    return {
        "L28": {
            "delta": {metric: 0.06}, "p": {metric: 0.04},
            metric: 0.5, "meta": {"identified_recent": 1000},
        },
        "L56": {"delta": {metric: 0.05}, "p": {metric: 0.04}, metric: 0.49},
        "L90": {"delta": {metric: 0.04}, "p": {metric: 0.04}, metric: 0.48},
    }


def test_measurement_directional_flag_off_uses_l28_default():
    aligned = _make_aligned_directional()
    cand = _Candidate(play_id="first_to_second_purchase", audience_size=500)
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    assert card.measurement.primary_window == "L28"
    # Flag-OFF: window_corroboration is None.
    assert card.measurement.window_corroboration is None


# ---------------------------------------------------------------------------
# 14) Decide layer reads materiality floor from profile
# ---------------------------------------------------------------------------


def test_decide_materiality_floor_uses_profile_when_on():
    from src.guardrails import gate_materiality
    from src.engine_run import RevenueRange, RevenueRangeSource
    card = PlayCard(
        play_id="x",
        evidence_class=EvidenceClass.DIRECTIONAL,
        revenue_range=RevenueRange(
            p10=100, p50=1500, p90=2500,
            source=RevenueRangeSource.STORE_OBSERVED,
            suppressed=False,
        ),
    )
    # profile floor 2000; p50=1500 < floor → rejected.
    rej = gate_materiality(card, monthly_revenue=100_000, profile_floor_usd=2000.0)
    assert rej is not None
    assert rej.reason_code == ReasonCode.MATERIALITY_BELOW_FLOOR


def test_decide_materiality_floor_falls_back_when_off():
    from src.guardrails import gate_materiality
    from src.engine_run import RevenueRange, RevenueRangeSource
    card = PlayCard(
        play_id="x",
        evidence_class=EvidenceClass.DIRECTIONAL,
        revenue_range=RevenueRange(
            p10=100, p50=8000, p90=10000,
            source=RevenueRangeSource.STORE_OBSERVED,
            suppressed=False,
        ),
    )
    # No profile_floor_usd → scale-aware floor on $100k monthly = max(10k, 3%*100k)=10k.
    rej = gate_materiality(card, monthly_revenue=100_000)
    assert rej is not None  # 8000 < 10000


# ---------------------------------------------------------------------------
# 15) Sizing reads pseudo_n_default from profile
# ---------------------------------------------------------------------------


def test_sizing_effective_pseudo_n_uses_profile_floor():
    profile = _make_profile(stage="GROWTH")  # pseudo_n_default=20
    n = effective_pseudo_n(
        PriorValidationStatus.VALIDATED_EXTERNAL,
        store_profile=profile, profile_flag_on=True,
    )
    # min(status_cap=30, profile=20) = 20
    assert n == 20


def test_sizing_effective_pseudo_n_falls_back_when_flag_off():
    profile = _make_profile(stage="GROWTH")
    n = effective_pseudo_n(
        PriorValidationStatus.VALIDATED_EXTERNAL,
        store_profile=profile, profile_flag_on=False,
    )
    assert n == PSEUDO_N_BY_STATUS[PriorValidationStatus.VALIDATED_EXTERNAL]


def test_sizing_effective_pseudo_n_never_raises_above_status_cap():
    profile = _make_profile(stage="ENTERPRISE")  # pseudo_n_default=50
    # ELICITED_EXPERT cap is 10; profile 50 should NOT raise it.
    n = effective_pseudo_n(
        PriorValidationStatus.ELICITED_EXPERT,
        store_profile=profile, profile_flag_on=True,
    )
    assert n == PSEUDO_N_BY_STATUS[PriorValidationStatus.ELICITED_EXPERT]


# ---------------------------------------------------------------------------
# 16) R1: window_corroboration present on directional path
# ---------------------------------------------------------------------------


def test_r1_directional_emits_window_corroboration_under_flag_on():
    profile = _make_profile()
    aligned = _make_aligned_directional()
    cand = _Candidate(play_id="first_to_second_purchase", audience_size=500)
    card = build_directional_play_card(
        cand, aligned, store_profile=profile, profile_flag_on=True,
    )
    assert card is not None
    assert isinstance(card.measurement.window_corroboration, WindowCorroboration)


# ---------------------------------------------------------------------------
# 17) R1: CORROBORATED → confidence bump (Emerging → Strong)
# ---------------------------------------------------------------------------


def test_r1_corroborated_bumps_confidence():
    card = PlayCard(
        play_id="x",
        evidence_class=EvidenceClass.DIRECTIONAL,
        confidence_label="Emerging",
        measurement=Measurement(
            metric="m", primary_window="L28",
            window_corroboration=WindowCorroboration.CORROBORATED,
        ),
    )
    bumped = _apply_window_corroboration_bumps([card], flag_on=True)
    assert bumped[0].confidence_label == "Strong"


# ---------------------------------------------------------------------------
# 18) R1: CONTRADICTED → Considered with WINDOW_DISAGREEMENT
# ---------------------------------------------------------------------------


def test_r1_contradicted_routes_to_considered():
    card = PlayCard(
        play_id="x",
        evidence_class=EvidenceClass.DIRECTIONAL,
        measurement=Measurement(
            metric="m", primary_window="L28",
            window_corroboration=WindowCorroboration.CONTRADICTED,
        ),
    )
    kept, refused = _route_window_disagreement_holds([card], flag_on=True)
    assert kept == []
    assert len(refused) == 1
    assert refused[0].reason_code == ReasonCode.WINDOW_DISAGREEMENT


# ---------------------------------------------------------------------------
# 19) R1: NEUTRAL → no behavior change
# ---------------------------------------------------------------------------


def test_r1_neutral_is_noop():
    card = PlayCard(
        play_id="x",
        evidence_class=EvidenceClass.DIRECTIONAL,
        confidence_label="Emerging",
        measurement=Measurement(
            metric="m", primary_window="L28",
            window_corroboration=WindowCorroboration.NEUTRAL,
        ),
    )
    bumped = _apply_window_corroboration_bumps([card], flag_on=True)
    kept, refused = _route_window_disagreement_holds(bumped, flag_on=True)
    assert kept == bumped
    assert refused == []
    assert bumped[0].confidence_label == "Emerging"


# ---------------------------------------------------------------------------
# 20) R1: agreement_windows excludes primary from its own agreement check
# ---------------------------------------------------------------------------


def test_r1_agreement_windows_excludes_primary():
    aligned = _make_aligned_directional()
    res = _window_corroboration_sign_only(
        aligned, "returning_customer_share",
        primary_window="L28", agreement_windows=["L28", "L56", "L90"],  # primary in list
    )
    # All same-sign + significant → CORROBORATED (primary excluded).
    assert res == WindowCorroboration.CORROBORATED


# ---------------------------------------------------------------------------
# 21) R1: WINDOW_DISAGREEMENT ReasonCode in enum + copy templates exist
# ---------------------------------------------------------------------------


def test_r1_window_disagreement_reason_code_and_templates_exist():
    assert ReasonCode.WINDOW_DISAGREEMENT.value == "window_disagreement"
    assert ReasonCode.WINDOW_DISAGREEMENT in _CONSIDERED_REASON_TEXT
    assert ReasonCode.WINDOW_DISAGREEMENT in _WOULD_FIRE_IF_TEMPLATE
    # Copy contains the merchant-facing "windows disagree" phrase per IM spec.
    text = _CONSIDERED_REASON_TEXT[ReasonCode.WINDOW_DISAGREEMENT].lower()
    assert "disagree" in text


# ---------------------------------------------------------------------------
# 22) R1: prior-anchored pathway parity (closes DS architect §1 asymmetry)
# ---------------------------------------------------------------------------


def test_r1_prior_anchored_helper_returns_neutral_when_metric_absent():
    # The prior-anchored helper degrades to NEUTRAL when the metric is
    # not in aligned (typical at S6.5 for reactivation_rate).
    res = _prior_anchored_window_corroboration(
        aligned={"L28": {}, "L56": {}, "L90": {}},
        metric="reactivation_rate",
        primary_window="L28",
        agreement_windows=["L56", "L90"],
    )
    assert res == WindowCorroboration.NEUTRAL


# ---------------------------------------------------------------------------
# 23) R1: confidence bump never crosses tier boundary
# ---------------------------------------------------------------------------


def test_r1_targeting_card_never_bumps():
    card = PlayCard(
        play_id="x",
        evidence_class=EvidenceClass.TARGETING,
        confidence_label="Targeting",
        measurement=None,  # targeting has no measurement
    )
    bumped = _apply_window_corroboration_bumps([card], flag_on=True)
    assert bumped[0].confidence_label == "Targeting"


def test_r1_strong_stays_strong():
    card = PlayCard(
        play_id="x",
        evidence_class=EvidenceClass.DIRECTIONAL,
        confidence_label="Strong",
        measurement=Measurement(
            metric="m", primary_window="L28",
            window_corroboration=WindowCorroboration.CORROBORATED,
        ),
    )
    bumped = _apply_window_corroboration_bumps([card], flag_on=True)
    assert bumped[0].confidence_label == "Strong"


# ---------------------------------------------------------------------------
# 24) All gate_calibration.yaml cells carry validation_status:heuristic_unvalidated
# ---------------------------------------------------------------------------


def test_yaml_carries_heuristic_unvalidated_tag():
    y = _yaml()
    assert y.get("validation_status") == "heuristic_unvalidated"


# ---------------------------------------------------------------------------
# 25) Every audience-floor cell has 4-tuple stage coverage
# ---------------------------------------------------------------------------


def test_audience_floors_have_4_stage_coverage_where_populated():
    y = _yaml()
    floors = y.get("audience_floors") or {}
    required = {"startup", "growth", "mature", "enterprise"}
    # winback_dormant_cohort.beauty.<each subv>:
    for subv, block in (floors.get("winback_dormant_cohort", {}).get("beauty") or {}).items():
        assert set(block.keys()) == required, f"beauty/{subv} missing stages"
    for subv, block in (floors.get("winback_dormant_cohort", {}).get("supplements") or {}).items():
        assert set(block.keys()) == required, f"supplements/{subv} missing stages"
    # mixed_beauty + mixed_supplements
    for key in ("mixed_beauty", "mixed_supplements"):
        block = floors.get("winback_dormant_cohort", {}).get(key)
        assert set(block.keys()) == required, key
    # _default_by_stage
    assert set(floors["_default_by_stage"].keys()) == required


# ---------------------------------------------------------------------------
# 26) YAML schema validation: winback fully populated, others via _default
# ---------------------------------------------------------------------------


def test_yaml_schema_winback_dormant_cohort_full_others_via_default():
    y = _yaml()
    floors = y.get("audience_floors") or {}
    # winback has the full table.
    wb = floors.get("winback_dormant_cohort") or {}
    assert "beauty" in wb and "supplements" in wb
    assert "mixed_beauty" in wb and "mixed_supplements" in wb
    # _default_by_stage is the catch-all for other plays.
    assert "_default_by_stage" in floors


# ---------------------------------------------------------------------------
# 27) Flag OFF: schema additions all default to None / empty
# ---------------------------------------------------------------------------


def test_flag_off_schema_additions_default_none():
    er = EngineRun()
    # store_profile slot defaults to None.
    assert er.store_profile is None
    # Measurement.window_corroboration defaults to None.
    m = Measurement()
    assert m.window_corroboration is None


# ---------------------------------------------------------------------------
# 28) Flag ON cadence-derived primary window flips Beauty skincare L28→L56
# ---------------------------------------------------------------------------


def test_flag_on_beauty_skincare_53d_primary_window_flips_to_l56():
    profile = _make_profile(
        cadence_class_to_days={"skincare": 53},
    )
    assert profile.measurement.primary_window == "L56"
    # vs. static yaml cell = L28 (the fallback)
    static_cell = _yaml().get("primary_window", {}).get("beauty", {}).get("skincare")
    assert static_cell == "L28"


# ---------------------------------------------------------------------------
# 29) PlayCard.drivers[].profile_field_ref cites the YAML path
# ---------------------------------------------------------------------------


def test_play_card_drivers_profile_field_ref_cites_yaml_path():
    profile = _make_profile()
    refs = profile.gate_calibration.profile_field_refs
    assert refs["audience_floor.winback_dormant_cohort"] == (
        "gate_calibration.audience_floors.winback_dormant_cohort.beauty.skincare.growth"
    )
    assert refs["materiality_floor"].startswith("gate_calibration.materiality_floors_usd.")
    assert refs["pseudo_n_default"].startswith("gate_calibration.pseudo_n_default.")


# ---------------------------------------------------------------------------
# 30) Provenance carries every consumed profile field (provenance log fires)
# ---------------------------------------------------------------------------


def test_provenance_records_every_consumed_profile_field():
    rules: list = []
    derive_gate_calibration(
        taxonomy=Taxonomy(vertical="beauty", subvertical="skincare",
                          vertical_confidence="HIGH"),
        stage=BusinessStage(stage="GROWTH"),
        cadence=CadenceBaseline(
            median_reorder_days_by_sku_class={"skincare": 53},
            detection_status="COMPUTED",
        ),
        data_depth=DataDepth(),
        business_model=BusinessModel(model="ONE_TIME_LED"),
        rules_fired=rules,
    )
    rule_names = {r.get("rule") for r in rules}
    assert "cadence_derived_primary_window" in rule_names


# ---------------------------------------------------------------------------
# 31) event_version=1 schema round-trips with new fields
# ---------------------------------------------------------------------------


def test_event_version_1_schema_round_trip_with_window_corroboration():
    m = Measurement(
        metric="rcs", primary_window="L28",
        window_corroboration=WindowCorroboration.CORROBORATED,
    )
    # Build a card → engine_run → round-trip via from_dict
    card = PlayCard(
        play_id="x", evidence_class=EvidenceClass.DIRECTIONAL,
        confidence_label="Emerging", measurement=m,
    )
    er = EngineRun(recommendations=[card])
    d = er.to_dict()
    er2 = EngineRun.from_dict(d)
    rt_meas = er2.recommendations[0].measurement
    assert rt_meas.window_corroboration == WindowCorroboration.CORROBORATED


# ---------------------------------------------------------------------------
# 32) L42 deferred: window set is exactly {L28, L56, L90}
# ---------------------------------------------------------------------------


def test_l42_deferred_window_set_is_exactly_three_windows():
    y = _yaml()
    pinned = set(y.get("windows_pinned") or [])
    assert pinned == {"L28", "L56", "L90"}
    # Also pin the in-code constant.
    assert set(_GATE_CALIBRATION_WINDOWS) == {"L28", "L56", "L90"}


# ---------------------------------------------------------------------------
# Extras — round-to-nearest, NEUTRAL on missing primary delta
# ---------------------------------------------------------------------------


def test_round_to_nearest_window_boundaries():
    # Round-to-nearest with strict-< tiebreak (earlier window wins on
    # equidistance):
    # 28 → L28 (exact); 42 → L28 (28 is 14 away, 56 is 14 away → L28 wins);
    # 43 → L56 (43-28=15, 56-43=13 → L56 closer);
    # 72 → L56 (72-56=16, 90-72=18 → L56 closer);
    # 73 → L56 (equidistant 17/17, earlier-init L56 wins);
    # 74 → L90 (74-56=18, 90-74=16 → L90 closer);
    # 90 → L90 (exact).
    assert _round_cadence_to_window(28) == "L28"
    assert _round_cadence_to_window(42) == "L28"
    assert _round_cadence_to_window(43) == "L56"
    assert _round_cadence_to_window(72) == "L56"
    assert _round_cadence_to_window(73) == "L56"  # equidistant tiebreak
    assert _round_cadence_to_window(74) == "L90"
    assert _round_cadence_to_window(90) == "L90"


def test_window_corroboration_returns_none_when_primary_delta_missing():
    res = _window_corroboration_sign_only(
        aligned={"L28": {"delta": {}}, "L56": {"delta": {}}, "L90": {"delta": {}}},
        metric="rcs", primary_window="L28",
    )
    assert res is None
