"""S12-T2: Retention threshold loader stage-cell lookup + fallback tests.

Covers ``_load_model_fit_thresholds`` returning a ``retention`` subdict
alongside ``bgnbd`` / ``gamma_gamma`` / ``survival`` / ``cf`` / ``rfm``,
with per-stage cell lookup, relaxation factors, guards, and graceful
fallback when YAML / profile is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.predictive.model_card import _load_model_fit_thresholds
from src.profile.types import BusinessStage, StoreProfile, Taxonomy


def _profile(stage: str) -> StoreProfile:
    return StoreProfile(
        taxonomy=Taxonomy(vertical="beauty"),
        business_stage=BusinessStage(stage=stage.upper()),
    )


# ---------------------------------------------------------------------------
# Per-stage cell lookup
# ---------------------------------------------------------------------------


def test_retention_startup_cell():
    out = _load_model_fit_thresholds(_profile("startup"))
    cell = out["retention"]
    assert cell["cohort_count_validated"] == 6
    assert cell["bootstrap_ci_width_at_month_3_max_validated"] == 0.25


def test_retention_growth_cell():
    out = _load_model_fit_thresholds(_profile("growth"))
    cell = out["retention"]
    assert cell["cohort_count_validated"] == 12
    assert cell["bootstrap_ci_width_at_month_3_max_validated"] == 0.20


def test_retention_mature_cell():
    out = _load_model_fit_thresholds(_profile("mature"))
    cell = out["retention"]
    assert cell["cohort_count_validated"] == 12
    assert cell["bootstrap_ci_width_at_month_3_max_validated"] == 0.15


def test_retention_enterprise_cell():
    out = _load_model_fit_thresholds(_profile("enterprise"))
    cell = out["retention"]
    assert cell["cohort_count_validated"] == 12
    assert cell["bootstrap_ci_width_at_month_3_max_validated"] == 0.15


# ---------------------------------------------------------------------------
# Relaxation factors
# ---------------------------------------------------------------------------


def test_retention_relaxation_factors_present():
    out = _load_model_fit_thresholds(_profile("mature"))
    relax = out["retention_relaxation_factors"]
    assert relax["provisional_n_multiplier"] == 0.5
    assert relax["provisional_bootstrap_ci_width_at_month_3_max"] == 0.35


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def test_retention_guards_present():
    out = _load_model_fit_thresholds(_profile("mature"))
    guards = out["retention_guards"]
    assert guards["absolute_cohort_count_floor"] == 3
    assert guards["bootstrap_iterations"] == 1000
    assert guards["months_horizon"] == 12
    assert guards["min_cohort_size_floor"] == 20
    assert guards["cumulative_retention_monotonicity_violation_refused"] is True


# ---------------------------------------------------------------------------
# Profile=None fallback (mature)
# ---------------------------------------------------------------------------


def test_retention_profile_none_falls_back_to_mature():
    out = _load_model_fit_thresholds(None)
    cell = out["retention"]
    # Mature cell values per YAML.
    assert cell["cohort_count_validated"] == 12
    assert cell["bootstrap_ci_width_at_month_3_max_validated"] == 0.15


# ---------------------------------------------------------------------------
# Additive coexistence with prior substrates' subdicts
# ---------------------------------------------------------------------------


def test_retention_does_not_disturb_prior_substrates():
    out = _load_model_fit_thresholds(_profile("mature"))
    # Prior substrates' subdicts remain present.
    for key in (
        "bgnbd",
        "gamma_gamma",
        "survival",
        "cf",
        "rfm",
        "retention",
    ):
        assert key in out


def test_retention_independent_of_resolved_stage_uncertainty_broadening():
    """HIGH-uncertainty broadening (MATURE→GROWTH) — retention block respects it."""
    profile = StoreProfile(
        taxonomy=Taxonomy(vertical="beauty"),
        business_stage=BusinessStage(stage="MATURE", uncertainty="HIGH"),
    )
    out = _load_model_fit_thresholds(profile)
    # Broader stage = growth.
    assert out["resolved_stage"] == "growth"
    cell = out["retention"]
    # Growth cell values.
    assert cell["cohort_count_validated"] == 12
    assert cell["bootstrap_ci_width_at_month_3_max_validated"] == 0.20


def test_retention_yaml_missing_returns_fallback(tmp_path):
    """YAML missing → fallback mature cell."""
    nonexistent = tmp_path / "does_not_exist.yaml"
    out = _load_model_fit_thresholds(_profile("mature"), yaml_path=nonexistent)
    cell = out["retention"]
    # Fallback constants (mature parity).
    assert cell["cohort_count_validated"] == 12
    assert cell["bootstrap_ci_width_at_month_3_max_validated"] == 0.15
    guards = out["retention_guards"]
    assert guards["absolute_cohort_count_floor"] == 3
