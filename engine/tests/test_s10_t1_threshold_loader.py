"""S10-T1: business-stage-keyed ML-fit threshold loader.

Tests the ``_load_model_fit_thresholds(profile)`` helper in
``src/predictive/model_card.py``. The helper resolves the per-stage
acceptance dict from ``config/gate_calibration.yaml`` with optional
vertical override on ``months_data_validated`` and stage-uncertainty
broadening.
"""

from __future__ import annotations

from src.predictive.model_card import _load_model_fit_thresholds
from src.profile.types import BusinessStage, StoreProfile, Taxonomy


def _profile(stage: str, vertical: str = "mixed", uncertainty: str = "LOW") -> StoreProfile:
    return StoreProfile(
        taxonomy=Taxonomy(vertical=vertical),
        business_stage=BusinessStage(stage=stage, uncertainty=uncertainty),
    )


def test_threshold_loader_startup_cell():
    out = _load_model_fit_thresholds(_profile("STARTUP"))
    assert out["bgnbd"]["months_data_validated"] == 4
    assert out["bgnbd"]["repeat_customers_validated"] == 150
    assert out["bgnbd"]["orders_validated"] == 450
    assert out["bgnbd"]["holdout_mape_validated"] == 0.30
    assert out["resolved_stage"] == "startup"


def test_threshold_loader_growth_cell():
    out = _load_model_fit_thresholds(_profile("GROWTH"))
    assert out["bgnbd"]["repeat_customers_validated"] == 300
    assert out["bgnbd"]["orders_validated"] == 900
    assert out["bgnbd"]["holdout_mape_validated"] == 0.27


def test_threshold_loader_mature_cell():
    out = _load_model_fit_thresholds(_profile("MATURE"))
    assert out["bgnbd"]["months_data_validated"] == 6
    assert out["bgnbd"]["repeat_customers_validated"] == 500
    assert out["bgnbd"]["orders_validated"] == 1500
    assert out["bgnbd"]["holdout_mape_validated"] == 0.25


def test_threshold_loader_enterprise_cell():
    out = _load_model_fit_thresholds(_profile("ENTERPRISE"))
    assert out["bgnbd"]["repeat_customers_validated"] == 1000
    assert out["bgnbd"]["orders_validated"] == 3000
    assert out["bgnbd"]["holdout_mape_validated"] == 0.22


def test_threshold_loader_vertical_override_months_supplements():
    """Supplements at MATURE: months override → 4 (cadence math), other cells unchanged."""
    out = _load_model_fit_thresholds(_profile("MATURE", vertical="supplements"))
    assert out["bgnbd"]["months_data_validated"] == 4  # vertical override
    assert out["bgnbd"]["repeat_customers_validated"] == 500  # stage cell unchanged
    assert out["bgnbd"]["orders_validated"] == 1500
    assert out["vertical_override_applied"] is True


def test_threshold_loader_vertical_override_months_beauty():
    """Beauty at MATURE: months override → 6 (matches the stage cell already)."""
    out = _load_model_fit_thresholds(_profile("MATURE", vertical="beauty"))
    assert out["bgnbd"]["months_data_validated"] == 6
    assert out["vertical_override_applied"] is True


def test_threshold_loader_vertical_override_no_op_for_unmapped_vertical():
    """Mixed vertical: no override entry → vertical_override_applied=False."""
    out = _load_model_fit_thresholds(_profile("GROWTH", vertical="mixed"))
    assert out["vertical_override_applied"] is False
    assert out["bgnbd"]["months_data_validated"] == 6


def test_threshold_loader_stage_uncertainty_broadening():
    """HIGH uncertainty at MATURE → reads GROWTH cell (broader)."""
    out = _load_model_fit_thresholds(_profile("MATURE", uncertainty="HIGH"))
    # Should now read the growth cell.
    assert out["bgnbd"]["repeat_customers_validated"] == 300
    assert out["bgnbd"]["orders_validated"] == 900
    assert out["resolved_stage"] == "growth"


def test_threshold_loader_stage_uncertainty_at_startup_floor():
    """HIGH uncertainty at STARTUP cannot broaden further; stays at startup."""
    out = _load_model_fit_thresholds(_profile("STARTUP", uncertainty="HIGH"))
    assert out["resolved_stage"] == "startup"
    assert out["bgnbd"]["repeat_customers_validated"] == 150


def test_threshold_loader_flag_off_fallback_to_mature():
    """profile=None (flag OFF) returns the hardcoded mature cell."""
    out = _load_model_fit_thresholds(None)
    assert out["bgnbd"]["months_data_validated"] == 6
    assert out["bgnbd"]["repeat_customers_validated"] == 500
    assert out["bgnbd"]["orders_validated"] == 1500
    assert out["bgnbd"]["holdout_mape_validated"] == 0.25
    assert out["resolved_stage"] == "mature"


def test_threshold_loader_relaxation_factors_pinned():
    """Relaxation factors (multiplier, addend) are pinned across all stages."""
    for stage in ("STARTUP", "GROWTH", "MATURE", "ENTERPRISE"):
        out = _load_model_fit_thresholds(_profile(stage))
        assert out["relaxation_factors"]["provisional_n_multiplier"] == 0.5
        assert out["relaxation_factors"]["provisional_mape_addend"] == 0.10


def test_threshold_loader_gamma_gamma_cutoffs():
    """Gamma-Gamma cutoffs surface in the loader output."""
    out = _load_model_fit_thresholds(_profile("MATURE"))
    assert out["gamma_gamma"]["independence_pearson_r_validated"] == 0.3
    assert out["gamma_gamma"]["independence_pearson_r_provisional"] == 0.5
