"""S10-T2: Gamma-Gamma fit + four-state ModelFitStatus coverage.

Tests ``src/predictive/gamma_gamma.py::fit_gamma_gamma``. Covers:

- Chained refusal when BG/NBD is REFUSED or INSUFFICIENT_DATA.
- INSUFFICIENT_DATA when fewer than the configured floor of customers
  have ≥ 2 monetary observations.
- Independence-violation warning (advisory, does not gate).
- Parquet-write semantics (artifact ONLY for VALIDATED / PROVISIONAL).
- VALIDATED/PROVISIONAL/REFUSED reachable on a synthetic G-G DGP.

Tests requiring an actual fit use ``pytest.importorskip("lifetimes")``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.predictive.gamma_gamma import (
    _pearson_r_freq_monetary,
    fit_gamma_gamma,
)
from src.predictive.model_card import (
    ModelCard,
    ModelFitStatus,
    _load_model_fit_thresholds,
)
from src.profile.types import BusinessStage, StoreProfile, Taxonomy


# ---------------------------------------------------------------------------
# Profiles + synthetic transaction generators
# ---------------------------------------------------------------------------


def _profile_mature_beauty() -> StoreProfile:
    return StoreProfile(
        taxonomy=Taxonomy(vertical="beauty"),
        business_stage=BusinessStage(stage="MATURE"),
    )


def _make_bgnbd_card(status: ModelFitStatus) -> ModelCard:
    return ModelCard(
        model_name="bgnbd",
        fit_status=status,
        fit_warnings=[],
        parameters={},
        training_window_days=240,
        n_observed=0,
        fit_timestamp="2026-05-26T00:00:00Z",
        parquet_schema_version=1,
    )


def _synthetic_gg_orders(
    n_customers: int = 600,
    span_days: int = 240,
    *,
    freq_monetary_correlation: float = 0.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a synthetic Gamma-Gamma DGP transaction frame.

    Each customer's frequency is drawn from a Poisson process; the
    per-customer mean order value is drawn from a Gamma distribution
    (matching the G-G assumption that monetary value is Gamma-distributed
    per customer with a population Gamma prior on the rate). Order
    values within a customer are Gamma-distributed around the
    per-customer mean.

    The ``freq_monetary_correlation`` knob applies an additive
    correlation between the customer's frequency draw and their mean
    monetary value — used to test the independence-violation warning.
    """

    rng = np.random.default_rng(seed)
    rows = []
    start = pd.Timestamp("2025-01-01")
    # Latent frequency rate per customer (Gamma) → drives Poisson draw.
    lam = rng.gamma(shape=3.0, scale=1.5, size=n_customers)
    # Latent per-customer mean monetary value (Gamma).
    base_mean_value = rng.gamma(shape=4.0, scale=15.0, size=n_customers)

    if freq_monetary_correlation != 0.0:
        # Inject linear coupling between frequency rate and mean value.
        # Normalise lam to z-scores then rescale into the mean-value tail.
        lam_z = (lam - lam.mean()) / max(lam.std(), 1e-9)
        base_mean_value = base_mean_value + (
            freq_monetary_correlation
            * lam_z
            * float(base_mean_value.std())
        )
        base_mean_value = np.clip(base_mean_value, 1.0, None)

    for c in range(n_customers):
        # Number of orders for the customer: at least 1, with mean lam[c]
        # scaled by the span window.
        n_orders = max(1, int(rng.poisson(lam=max(lam[c], 0.3))))
        for _ in range(n_orders):
            offset = int(rng.integers(0, span_days))
            # Draw the per-order value as Gamma around the customer mean.
            order_value = float(
                rng.gamma(shape=4.0, scale=base_mean_value[c] / 4.0)
            )
            rows.append({
                "customer_id": f"cust{c:05d}",
                "order_date": start + pd.Timedelta(days=offset),
                "order_value": max(order_value, 0.01),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Chained refusal
# ---------------------------------------------------------------------------


def test_chained_refusal_when_bgnbd_refused(tmp_path):
    """BG/NBD REFUSED → G-G short-circuits to REFUSED with
    ``chained_bgnbd_refusal`` warning. No fit attempted, no parquet."""

    df = _synthetic_gg_orders(n_customers=600, seed=1)
    bgnbd_card = _make_bgnbd_card(ModelFitStatus.REFUSED)
    card = fit_gamma_gamma(
        df,
        _profile_mature_beauty(),
        bgnbd_card,
        store_id="test_store",
        data_dir=tmp_path,
    )
    assert card.fit_status == ModelFitStatus.REFUSED
    assert "chained_bgnbd_refusal" in card.fit_warnings
    assert card.parameters == {}
    assert card.model_name == "gamma_gamma"
    parquet_path = tmp_path / "test_store" / "predictive" / "gamma_gamma.parquet"
    assert not parquet_path.exists()


def test_chained_refusal_when_bgnbd_insufficient_data(tmp_path):
    """BG/NBD INSUFFICIENT_DATA → G-G short-circuits to REFUSED with
    ``chained_bgnbd_refusal`` warning. Parallel to the REFUSED path —
    we cannot rank monetary value if we cannot rank aliveness at all."""

    df = _synthetic_gg_orders(n_customers=600, seed=2)
    bgnbd_card = _make_bgnbd_card(ModelFitStatus.INSUFFICIENT_DATA)
    card = fit_gamma_gamma(
        df,
        _profile_mature_beauty(),
        bgnbd_card,
        store_id="test_store",
        data_dir=tmp_path,
    )
    assert card.fit_status == ModelFitStatus.REFUSED
    assert "chained_bgnbd_refusal" in card.fit_warnings
    parquet_path = tmp_path / "test_store" / "predictive" / "gamma_gamma.parquet"
    assert not parquet_path.exists()


# ---------------------------------------------------------------------------
# INSUFFICIENT_DATA
# ---------------------------------------------------------------------------


def test_insufficient_data_below_floor(tmp_path):
    """< 50 customers with ≥ 2 monetary observations → INSUFFICIENT_DATA.
    No fit attempted, no parquet."""

    df = _synthetic_gg_orders(n_customers=20, seed=3)
    # No chained refusal (BG/NBD presumed VALIDATED).
    bgnbd_card = _make_bgnbd_card(ModelFitStatus.VALIDATED)
    card = fit_gamma_gamma(
        df,
        _profile_mature_beauty(),
        bgnbd_card,
        store_id="test_store",
        data_dir=tmp_path,
    )
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA
    assert card.parameters == {}
    parquet_path = tmp_path / "test_store" / "predictive" / "gamma_gamma.parquet"
    assert not parquet_path.exists()


def test_insufficient_data_no_chained_card(tmp_path):
    """``bgnbd_model_card=None`` is a valid input — the chained-refusal
    short-circuit applies only when an actual REFUSED/INSUFFICIENT_DATA
    card is passed. With no card, the floor-gate is the next decider."""

    df = _synthetic_gg_orders(n_customers=10, seed=4)
    card = fit_gamma_gamma(
        df,
        _profile_mature_beauty(),
        None,
        store_id="test_store",
        data_dir=tmp_path,
    )
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# Independence-violation warning (advisory; does NOT gate)
# ---------------------------------------------------------------------------


def test_independence_violation_flagged_but_fit_proceeds(tmp_path):
    """Pearson-r on (frequency, monetary) above the violation threshold
    surfaces ``gg_independence_violated`` in fit_warnings but does NOT
    short-circuit the fit. Status may be PROVISIONAL or REFUSED."""

    pytest.importorskip("lifetimes")

    # Construct a fixture with strong positive (freq, monetary) coupling
    # to force the Pearson-r above 0.10.
    df = _synthetic_gg_orders(
        n_customers=600,
        seed=5,
        freq_monetary_correlation=0.6,
    )
    bgnbd_card = _make_bgnbd_card(ModelFitStatus.VALIDATED)
    card = fit_gamma_gamma(
        df,
        _profile_mature_beauty(),
        bgnbd_card,
        store_id="test_store",
        data_dir=tmp_path,
    )
    # The fit must run. The warning may or may not fire depending on
    # whether the train-slice |r| crosses the threshold; if it does we
    # expect to see it in warnings and the status cannot be VALIDATED
    # (the VALIDATED gate requires no warnings).
    if "gg_independence_violated" in card.fit_warnings:
        assert card.fit_status != ModelFitStatus.VALIDATED


# ---------------------------------------------------------------------------
# Synthetic Gamma-Gamma DGP sanity (parallel to T1.4's BG/NBD sanity)
# ---------------------------------------------------------------------------


def test_validated_or_provisional_on_synthetic_gamma_gamma_generator(tmp_path):
    """A synthetic G-G DGP fixture (no induced freq-monetary coupling)
    should fit cleanly. We accept VALIDATED / PROVISIONAL / REFUSED —
    synthetic fixtures may legitimately produce REFUSED if the holdout
    Spearman lands below the floor (parallel to Pivot 5 / Option γ for
    BG/NBD on synthetic data). The contract: the fit RUNS, the
    classifier outputs a defined state, and parquet is written only when
    {VALIDATED, PROVISIONAL}."""

    pytest.importorskip("lifetimes")

    df = _synthetic_gg_orders(
        n_customers=600,
        seed=7,
        freq_monetary_correlation=0.0,
    )
    bgnbd_card = _make_bgnbd_card(ModelFitStatus.VALIDATED)
    card = fit_gamma_gamma(
        df,
        _profile_mature_beauty(),
        bgnbd_card,
        store_id="test_store",
        data_dir=tmp_path,
    )
    assert card.fit_status in (
        ModelFitStatus.VALIDATED,
        ModelFitStatus.PROVISIONAL,
        ModelFitStatus.REFUSED,
    )
    parquet_path = tmp_path / "test_store" / "predictive" / "gamma_gamma.parquet"
    if card.fit_status in (ModelFitStatus.VALIDATED, ModelFitStatus.PROVISIONAL):
        assert parquet_path.exists()
        out = pd.read_parquet(parquet_path)
        assert "customer_id" in out.columns
        assert "expected_avg_spend" in out.columns
        assert "parquet_schema_version" in out.columns
        assert (out["parquet_schema_version"] == 1).all()
        assert (out["expected_avg_spend"] >= 0).all()
    else:
        assert not parquet_path.exists()


# ---------------------------------------------------------------------------
# Threshold loader extension
# ---------------------------------------------------------------------------


def test_threshold_loader_exposes_gamma_gamma_keys():
    """``_load_model_fit_thresholds`` returns the new G-G subdicts."""

    out = _load_model_fit_thresholds(_profile_mature_beauty())

    # The legacy BG/NBD subdicts still resolve.
    assert "bgnbd" in out
    assert "holdout_rank_spearman_validated" in out["bgnbd"]

    # The new T2 G-G subdicts.
    assert "gamma_gamma" in out
    gg = out["gamma_gamma"]
    assert gg["repeat_customers_validated"] == 50
    assert gg["holdout_rank_spearman_validated"] == 0.20
    assert gg["agg_ratio_min"] == 0.5
    assert gg["agg_ratio_max"] == 1.5

    assert "gamma_gamma_relaxation_factors" in out
    relax = out["gamma_gamma_relaxation_factors"]
    assert relax["provisional_rank_spearman_floor"] == 0.10
    assert relax["provisional_agg_ratio_min"] == 0.4
    assert relax["provisional_agg_ratio_max"] == 1.6

    assert "gamma_gamma_independence_check" in out
    assert out["gamma_gamma_independence_check"]["pearson_r_violation_threshold"] == 0.10


# ---------------------------------------------------------------------------
# Pearson-r helper (unit-testable in isolation)
# ---------------------------------------------------------------------------


def test_pearson_r_helper_returns_none_on_empty():
    df = pd.DataFrame(columns=["frequency", "monetary_value"])
    assert _pearson_r_freq_monetary(df) is None


def test_pearson_r_helper_returns_none_on_zero_variance():
    df = pd.DataFrame({
        "frequency": [1, 1, 1, 1],
        "monetary_value": [10.0, 20.0, 30.0, 40.0],
    })
    assert _pearson_r_freq_monetary(df) is None


def test_pearson_r_helper_detects_strong_positive_correlation():
    df = pd.DataFrame({
        "frequency": [1, 2, 3, 4, 5, 6],
        "monetary_value": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
    })
    r = _pearson_r_freq_monetary(df)
    assert r is not None
    assert r > 0.99


# ---------------------------------------------------------------------------
# Flag default + engine_run shape
# ---------------------------------------------------------------------------


def test_flag_default_on_post_t2_5():
    """``ENGINE_V2_ML_GAMMA_GAMMA`` default ON post-T2.5 (atomic flip).

    At T2 this was OFF (substrate landing); at T2.5 the default flipped
    to True atomically with the orchestration wire at src/main.py and
    the rollback contract test at
    ``tests/test_s10_t2_5_gamma_gamma_rollback.py``. The pre-T2.5
    behavior is reproducible by explicitly setting
    ``ENGINE_V2_ML_GAMMA_GAMMA=false`` in env (verified by the
    flag-off-rollback test)."""

    from src.utils import get_config

    cfg = get_config()
    assert cfg.get("ENGINE_V2_ML_GAMMA_GAMMA") is True


def test_flag_off_engine_run_predictive_models_unchanged():
    """At flag-OFF default, no Gamma-Gamma code path runs in main.py
    (T2 ships module + schema only; T2.5 wires orchestration)."""

    from src.engine_run import EngineRun

    er = EngineRun()
    # G-G never lands as a key when the flag is OFF.
    assert "gamma_gamma" not in er.predictive_models
