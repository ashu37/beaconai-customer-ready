"""S11-T1: business-stage-keyed survival threshold loader.

Tests the survival subdict surfaced by
``src/predictive/model_card.py::_load_model_fit_thresholds(profile)``.
Mirrors ``tests/test_s10_t1_threshold_loader.py`` shape.
"""

from __future__ import annotations

from src.predictive.model_card import _load_model_fit_thresholds
from src.profile.types import BusinessStage, StoreProfile, Taxonomy


def _profile(stage: str, vertical: str = "mixed", uncertainty: str = "LOW") -> StoreProfile:
    return StoreProfile(
        taxonomy=Taxonomy(vertical=vertical),
        business_stage=BusinessStage(stage=stage, uncertainty=uncertainty),
    )


def test_survival_threshold_loader_startup_cell():
    out = _load_model_fit_thresholds(_profile("STARTUP"))
    assert out["survival"]["months_data_validated"] == 3
    assert out["survival"]["repeat_customers_validated"] == 200
    assert out["survival"]["censored_events_validated"] == 30
    assert out["survival"]["holdout_c_index_validated"] == 0.62
    assert out["survival"]["holdout_brier_score_90d_validated_max"] == 0.25


def test_survival_threshold_loader_growth_cell():
    out = _load_model_fit_thresholds(_profile("GROWTH"))
    assert out["survival"]["months_data_validated"] == 4
    assert out["survival"]["repeat_customers_validated"] == 300
    assert out["survival"]["censored_events_validated"] == 50
    assert out["survival"]["holdout_c_index_validated"] == 0.62


def test_survival_threshold_loader_mature_cell():
    out = _load_model_fit_thresholds(_profile("MATURE"))
    assert out["survival"]["months_data_validated"] == 6
    assert out["survival"]["repeat_customers_validated"] == 500
    assert out["survival"]["censored_events_validated"] == 100
    assert out["survival"]["holdout_c_index_validated"] == 0.63


def test_survival_threshold_loader_enterprise_cell():
    out = _load_model_fit_thresholds(_profile("ENTERPRISE"))
    assert out["survival"]["repeat_customers_validated"] == 1000
    assert out["survival"]["censored_events_validated"] == 200
    assert out["survival"]["holdout_c_index_validated"] == 0.63


def test_survival_relaxation_factors_present():
    out = _load_model_fit_thresholds(_profile("MATURE"))
    relax = out["survival_relaxation_factors"]
    assert relax["provisional_n_multiplier"] == 0.5
    assert relax["provisional_c_index_floor"] == 0.55
    assert relax["provisional_brier_score_90d_max"] == 0.35


def test_survival_threshold_loader_fallback_when_profile_none():
    """``profile=None`` → mature cell fallback for survival as well."""

    out = _load_model_fit_thresholds(None)
    # Hardcoded fallback constants mirror MATURE.
    assert out["survival"]["repeat_customers_validated"] == 500
    assert out["survival"]["holdout_c_index_validated"] == 0.63
    assert out["survival"]["holdout_brier_score_90d_validated_max"] == 0.25


def test_survival_threshold_loader_stage_uncertainty_broadening():
    """HIGH uncertainty at MATURE → reads GROWTH cell (broader)."""

    out = _load_model_fit_thresholds(_profile("MATURE", uncertainty="HIGH"))
    assert out["survival"]["repeat_customers_validated"] == 300  # growth
    assert out["survival"]["months_data_validated"] == 4  # growth


def test_survival_returned_alongside_bgnbd_and_gamma_gamma():
    """The loader returns survival alongside bgnbd + gamma_gamma — additive."""

    out = _load_model_fit_thresholds(_profile("MATURE"))
    assert "bgnbd" in out
    assert "gamma_gamma" in out
    assert "survival" in out
    assert "survival_relaxation_factors" in out
