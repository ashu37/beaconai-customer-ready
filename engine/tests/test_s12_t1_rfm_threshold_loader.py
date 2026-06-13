"""S12-T1: business-stage-keyed RFM segmentation threshold loader.

Tests the ``rfm`` / ``rfm_relaxation_factors`` / ``rfm_guards`` subdicts
surfaced by ``src/predictive/model_card.py::_load_model_fit_thresholds``.
Mirrors ``tests/test_s11_t2_cf_threshold_loader.py`` shape.
"""

from __future__ import annotations

from src.predictive.model_card import _load_model_fit_thresholds
from src.profile.types import BusinessStage, StoreProfile, Taxonomy


def _profile(stage: str, vertical: str = "mixed", uncertainty: str = "LOW") -> StoreProfile:
    return StoreProfile(
        taxonomy=Taxonomy(vertical=vertical),
        business_stage=BusinessStage(stage=stage, uncertainty=uncertainty),
    )


def test_rfm_threshold_loader_startup_cell():
    out = _load_model_fit_thresholds(_profile("STARTUP"))
    assert out["rfm"]["n_customers_validated"] == 50
    assert out["rfm"]["segment_monotonicity_spearman_validated"] == 0.60
    assert out["rfm"]["quintile_coverage_min_validated"] == 0.10


def test_rfm_threshold_loader_growth_cell():
    out = _load_model_fit_thresholds(_profile("GROWTH"))
    assert out["rfm"]["n_customers_validated"] == 200
    assert out["rfm"]["segment_monotonicity_spearman_validated"] == 0.65


def test_rfm_threshold_loader_mature_cell():
    out = _load_model_fit_thresholds(_profile("MATURE"))
    assert out["rfm"]["n_customers_validated"] == 500
    assert out["rfm"]["segment_monotonicity_spearman_validated"] == 0.70
    assert out["rfm"]["quintile_coverage_min_validated"] == 0.10


def test_rfm_threshold_loader_enterprise_cell():
    out = _load_model_fit_thresholds(_profile("ENTERPRISE"))
    assert out["rfm"]["n_customers_validated"] == 1000
    assert out["rfm"]["segment_monotonicity_spearman_validated"] == 0.70


def test_rfm_relaxation_factors_default():
    out = _load_model_fit_thresholds(_profile("MATURE"))
    rf = out["rfm_relaxation_factors"]
    assert rf["provisional_n_multiplier"] == 0.5
    assert rf["provisional_segment_monotonicity_spearman_floor"] == 0.40
    assert rf["provisional_quintile_coverage_min_floor"] == 0.05


def test_rfm_guards_defaults():
    out = _load_model_fit_thresholds(_profile("MATURE"))
    g = out["rfm_guards"]
    assert g["absolute_customers_floor"] == 50
    assert g["refused_quintile_coverage_min"] == 0.05


def test_rfm_threshold_loader_fallback_when_profile_none():
    out = _load_model_fit_thresholds(None)
    # Falls back to MATURE cell.
    assert out["rfm"]["n_customers_validated"] == 500
    assert out["rfm"]["segment_monotonicity_spearman_validated"] == 0.70


def test_rfm_threshold_loader_returned_alongside_other_blocks():
    """Additive contract: rfm subdict coexists with prior blocks."""
    out = _load_model_fit_thresholds(_profile("MATURE"))
    assert "bgnbd" in out
    assert "gamma_gamma" in out
    assert "survival" in out
    assert "cf" in out
    assert "rfm" in out
    assert "rfm_relaxation_factors" in out
    assert "rfm_guards" in out


def test_rfm_threshold_loader_stage_uncertainty_broadening():
    """HIGH uncertainty at MATURE consults GROWTH cell (same as bgnbd)."""
    out_high = _load_model_fit_thresholds(_profile("MATURE", uncertainty="HIGH"))
    out_growth = _load_model_fit_thresholds(_profile("GROWTH"))
    assert (
        out_high["rfm"]["n_customers_validated"]
        == out_growth["rfm"]["n_customers_validated"]
    )
    assert (
        out_high["rfm"]["segment_monotonicity_spearman_validated"]
        == out_growth["rfm"]["segment_monotonicity_spearman_validated"]
    )
