"""S11-T2: business-stage-keyed CF (implicit ALS) threshold loader.

Tests the ``cf`` / ``cf_relaxation_factors`` / ``cf_hyperparameters``
subdicts surfaced by ``src/predictive/model_card.py::
_load_model_fit_thresholds(profile)``. Mirrors
``tests/test_s11_t1_survival_threshold_loader.py`` shape.
"""

from __future__ import annotations

from src.predictive.model_card import _load_model_fit_thresholds
from src.profile.types import BusinessStage, StoreProfile, Taxonomy


def _profile(stage: str, vertical: str = "mixed", uncertainty: str = "LOW") -> StoreProfile:
    return StoreProfile(
        taxonomy=Taxonomy(vertical=vertical),
        business_stage=BusinessStage(stage=stage, uncertainty=uncertainty),
    )


def test_cf_threshold_loader_startup_cell():
    out = _load_model_fit_thresholds(_profile("STARTUP"))
    assert out["cf"]["min_customers"] == 50
    assert out["cf"]["min_items"] == 50
    assert out["cf"]["min_interactions_per_user"] == 2
    assert out["cf"]["top_k_recall_validated"] == 0.05


def test_cf_threshold_loader_growth_cell():
    out = _load_model_fit_thresholds(_profile("GROWTH"))
    assert out["cf"]["min_customers"] == 100
    assert out["cf"]["min_items"] == 75
    assert out["cf"]["top_k_recall_validated"] == 0.06


def test_cf_threshold_loader_mature_cell():
    out = _load_model_fit_thresholds(_profile("MATURE"))
    assert out["cf"]["min_customers"] == 200
    assert out["cf"]["min_items"] == 100
    assert out["cf"]["top_k_recall_validated"] == 0.08


def test_cf_threshold_loader_enterprise_cell():
    out = _load_model_fit_thresholds(_profile("ENTERPRISE"))
    assert out["cf"]["min_customers"] == 500
    assert out["cf"]["min_items"] == 200
    assert out["cf"]["top_k_recall_validated"] == 0.10


def test_cf_relaxation_factors_default():
    out = _load_model_fit_thresholds(_profile("MATURE"))
    rf = out["cf_relaxation_factors"]
    assert rf["provisional_n_multiplier"] == 0.5
    assert rf["provisional_top_k_recall_floor"] == 0.03


def test_cf_hyperparameters_defaults():
    out = _load_model_fit_thresholds(_profile("MATURE"))
    hp = out["cf_hyperparameters"]
    assert hp["top_k"] == 10
    assert hp["top_n_lookalikes_per_customer"] == 20
    assert hp["als_factors"] == 32
    assert hp["als_regularization"] == 0.01
    assert hp["als_iterations"] == 15
    assert hp["coverage_at_10_warning_threshold"] == 0.20


def test_cf_threshold_loader_fallback_when_profile_none():
    out = _load_model_fit_thresholds(None)
    # Falls back to MATURE cell.
    assert out["cf"]["min_customers"] == 200
    assert out["cf"]["min_items"] == 100
    assert out["cf"]["top_k_recall_validated"] == 0.08


def test_cf_threshold_loader_returned_alongside_other_blocks():
    """Additive contract: cf subdict coexists with bgnbd/gamma_gamma/survival."""
    out = _load_model_fit_thresholds(_profile("MATURE"))
    assert "bgnbd" in out
    assert "gamma_gamma" in out
    assert "survival" in out
    assert "cf" in out
    assert "cf_relaxation_factors" in out
    assert "cf_hyperparameters" in out


def test_cf_threshold_loader_stage_uncertainty_broadening():
    """HIGH uncertainty at MATURE consults GROWTH cell (same as bgnbd)."""
    out_high = _load_model_fit_thresholds(_profile("MATURE", uncertainty="HIGH"))
    out_growth = _load_model_fit_thresholds(_profile("GROWTH"))
    assert out_high["cf"]["min_customers"] == out_growth["cf"]["min_customers"]
    assert out_high["cf"]["top_k_recall_validated"] == out_growth["cf"]["top_k_recall_validated"]
