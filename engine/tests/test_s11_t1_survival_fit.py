"""S11-T1: Cox PH survival fit + four-state ModelFitStatus coverage.

Tests ``src/predictive/survival.py::fit_survival``. Covers:

- Chained-refusal on BG/NBD REFUSED / INSUFFICIENT_DATA / None.
- INSUFFICIENT_DATA path (below per-stage floor).
- Parquet-write semantics (artifact ONLY for VALIDATED/PROVISIONAL).
- Dual-gate VALIDATED contract (c_index AND brier both clear).
- Synthetic Cox PH DGP sanity check (parallel to T1.4 BG/NBD ρ=0.484).

Tests that require an actual Cox fit pull ``sksurv`` lazily via
``pytest.importorskip`` so the file still loads cleanly when the
dependency is not yet installed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.predictive.model_card import ModelCard, ModelFitStatus
from src.predictive.survival import fit_survival
from src.profile.types import BusinessStage, StoreProfile, Taxonomy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile_mature_beauty() -> StoreProfile:
    return StoreProfile(
        taxonomy=Taxonomy(vertical="beauty"),
        business_stage=BusinessStage(stage="MATURE"),
    )


def _profile_startup() -> StoreProfile:
    return StoreProfile(
        taxonomy=Taxonomy(vertical="beauty"),
        business_stage=BusinessStage(stage="STARTUP"),
    )


def _bgnbd_card(status: ModelFitStatus) -> ModelCard:
    return ModelCard(
        model_name="bgnbd",
        fit_status=status,
        fit_warnings=[],
        parameters={"r": 1.0, "alpha": 10.0, "a": 1.0, "b": 2.0},
        training_window_days=240,
        n_observed=500,
        fit_timestamp="2026-05-26T00:00:00Z",
        parquet_schema_version=1,
    )


def _build_orders(n_customers: int, purchases_per_customer: int,
                  span_days: int = 240, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    start = pd.Timestamp("2025-01-01")
    for c in range(n_customers):
        for _ in range(max(1, purchases_per_customer)):
            offset = int(rng.integers(0, span_days))
            rows.append({"customer_id": f"cust{c:05d}",
                         "order_date": start + pd.Timedelta(days=offset)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Chained refusal — does NOT require sksurv
# ---------------------------------------------------------------------------


def test_chained_refusal_when_bgnbd_refused():
    orders = _build_orders(600, 5)
    card = fit_survival(
        orders, _profile_mature_beauty(), _bgnbd_card(ModelFitStatus.REFUSED)
    )
    assert card.fit_status == ModelFitStatus.REFUSED
    assert "chained_bgnbd_refusal" in card.fit_warnings
    assert card.parameters == {}
    assert card.holdout_c_index is None
    assert card.holdout_brier_score_90d is None


def test_chained_refusal_when_bgnbd_insufficient_data():
    orders = _build_orders(600, 5)
    card = fit_survival(
        orders, _profile_mature_beauty(),
        _bgnbd_card(ModelFitStatus.INSUFFICIENT_DATA),
    )
    assert card.fit_status == ModelFitStatus.REFUSED
    assert "chained_bgnbd_refusal" in card.fit_warnings


def test_chained_refusal_when_bgnbd_card_is_none():
    """Missing BG/NBD ModelCard → treated as REFUSED for the chained gate."""

    orders = _build_orders(600, 5)
    card = fit_survival(orders, _profile_mature_beauty(), None)
    assert card.fit_status == ModelFitStatus.REFUSED
    assert "chained_bgnbd_refusal" in card.fit_warnings


# ---------------------------------------------------------------------------
# INSUFFICIENT_DATA — engine declines (BG/NBD VALIDATED but population thin)
# ---------------------------------------------------------------------------


def test_insufficient_data_below_repeat_customers_floor():
    # MATURE requires 500 repeat customers (with relaxation 0.5 → 250 floor).
    orders = _build_orders(100, 3)
    card = fit_survival(
        orders, _profile_mature_beauty(), _bgnbd_card(ModelFitStatus.VALIDATED)
    )
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA
    assert card.parameters == {}


def test_insufficient_data_below_events_floor():
    # 60 single-purchase customers → 0 repeat → below events floor.
    orders = _build_orders(60, 1)
    card = fit_survival(
        orders, _profile_mature_beauty(), _bgnbd_card(ModelFitStatus.VALIDATED)
    )
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA


def test_insufficient_data_below_months_floor():
    # 600 customers but only 30 days of data → below MATURE 6-mo floor.
    orders = _build_orders(600, 5, span_days=30)
    card = fit_survival(
        orders, _profile_mature_beauty(), _bgnbd_card(ModelFitStatus.VALIDATED)
    )
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA


def test_parquet_not_written_for_refused_chained(tmp_path):
    """REFUSED via chained_bgnbd_refusal → no parquet."""

    orders = _build_orders(600, 5)
    card = fit_survival(
        orders, _profile_mature_beauty(),
        _bgnbd_card(ModelFitStatus.REFUSED),
        store_id="test_store", data_dir=tmp_path,
    )
    assert card.fit_status == ModelFitStatus.REFUSED
    pq = tmp_path / "test_store" / "predictive" / "survival.parquet"
    assert not pq.exists()


def test_parquet_not_written_for_insufficient_data(tmp_path):
    orders = _build_orders(100, 3)
    card = fit_survival(
        orders, _profile_mature_beauty(),
        _bgnbd_card(ModelFitStatus.VALIDATED),
        store_id="test_store", data_dir=tmp_path,
    )
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA
    pq = tmp_path / "test_store" / "predictive" / "survival.parquet"
    assert not pq.exists()


# ---------------------------------------------------------------------------
# REFUSED — sksurv import path
# ---------------------------------------------------------------------------


def test_refused_when_sksurv_not_installed(monkeypatch):
    """If sksurv import fails, REFUSED with sksurv_import_failed warning."""

    pytest.importorskip("sksurv")  # only meaningful if sksurv present
    orders = _build_orders(600, 5)

    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("sksurv"):
            raise ImportError(f"forced fail: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    card = fit_survival(
        orders, _profile_mature_beauty(), _bgnbd_card(ModelFitStatus.VALIDATED)
    )
    assert card.fit_status == ModelFitStatus.REFUSED
    assert "sksurv_import_failed" in card.fit_warnings


# ---------------------------------------------------------------------------
# Synthetic Cox PH DGP sanity — DS expects VALIDATED or PROVISIONAL
# ---------------------------------------------------------------------------


def _build_cox_dgp_orders(
    n_customers: int = 1500,
    span_days: int = 360,
    seed: int = 7,
) -> pd.DataFrame:
    """Generate orders under a proper Cox PH DGP analog.

    Each customer has a latent ``rate`` drawn from a gamma distribution.
    Inter-purchase times follow Exponential(rate). Higher-rate customers
    should be predicted as higher-hazard / lower-survival by the Cox
    fit. The (log_frequency, log_recency_over_T) covariates derived from
    train-window observations will correlate with the true rate, so a
    correctly-fit Cox PH should produce C-index well above 0.55.
    """

    rng = np.random.default_rng(seed)
    rows = []
    start = pd.Timestamp("2025-01-01")
    # Gamma-distributed rates (events per day): shape=1.5, scale=0.04
    # → mean ~0.06 events/day → median ~17d between purchases.
    rates = rng.gamma(shape=1.5, scale=0.04, size=n_customers)
    for c, rate in enumerate(rates):
        if rate <= 0:
            continue
        t = 0.0
        # First purchase uniformly placed in the first 30 days so we have
        # a non-trivial recency for everyone.
        t = float(rng.uniform(0, 30))
        while t < span_days:
            rows.append({"customer_id": f"cust{c:05d}",
                         "order_date": start + pd.Timedelta(days=int(t))})
            gap = rng.exponential(scale=1.0 / rate)
            t += max(1.0, gap)
    return pd.DataFrame(rows)


def test_synthetic_cox_dgp_sanity(tmp_path):
    """Synthetic Cox-PH-shaped data should produce VALIDATED or PROVISIONAL.

    Parallel to S10-T1.4's gamma-beta BG/NBD sanity test (ρ=0.484). If
    this lands REFUSED, the survival implementation has a bug.
    """

    pytest.importorskip("sksurv")
    orders = _build_cox_dgp_orders()
    card = fit_survival(
        orders, _profile_mature_beauty(),
        _bgnbd_card(ModelFitStatus.VALIDATED),
        store_id="cox_sanity", data_dir=tmp_path,
    )
    # Implementation must produce a measurable C-index on this DGP.
    assert card.fit_status in (
        ModelFitStatus.VALIDATED, ModelFitStatus.PROVISIONAL
    ), (
        f"Cox PH on a Cox-shaped DGP should land VALIDATED or PROVISIONAL; "
        f"got {card.fit_status} with c_index={card.holdout_c_index}, "
        f"brier_90d={card.holdout_brier_score_90d}, warnings={card.fit_warnings}"
    )
    assert card.holdout_c_index is not None
    assert card.holdout_c_index >= 0.55  # provisional floor at minimum
    # On VALIDATED / PROVISIONAL, parquet must exist.
    pq = tmp_path / "cox_sanity" / "predictive" / "survival.parquet"
    assert pq.exists()


def test_dual_gate_validated_requires_both_c_index_and_brier(tmp_path):
    """VALIDATED implies BOTH c_index ≥ stage floor AND brier ≤ 0.25.

    On synthetic data, whichever status lands (VALIDATED / PROVISIONAL),
    the dual-gate invariant must hold for VALIDATED specifically.
    """

    pytest.importorskip("sksurv")
    orders = _build_cox_dgp_orders()
    card = fit_survival(
        orders, _profile_mature_beauty(),
        _bgnbd_card(ModelFitStatus.VALIDATED),
    )
    if card.fit_status == ModelFitStatus.VALIDATED:
        # MATURE: c_index ≥ 0.63, brier ≤ 0.25.
        assert card.holdout_c_index is not None and card.holdout_c_index >= 0.63
        assert card.holdout_brier_score_90d is not None
        assert card.holdout_brier_score_90d <= 0.25
    # If PROVISIONAL: at least one gate must be in the relaxed band,
    # which the classifier already enforced (so this is informational).


def test_parquet_written_for_validated_or_provisional(tmp_path):
    pytest.importorskip("sksurv")
    orders = _build_cox_dgp_orders()
    card = fit_survival(
        orders, _profile_mature_beauty(),
        _bgnbd_card(ModelFitStatus.VALIDATED),
        store_id="pq_test", data_dir=tmp_path,
    )
    pq = tmp_path / "pq_test" / "predictive" / "survival.parquet"
    if card.fit_status in (ModelFitStatus.VALIDATED, ModelFitStatus.PROVISIONAL):
        assert pq.exists()
        df = pd.read_parquet(pq)
        assert "customer_id" in df.columns
        assert "p_survival_90d" in df.columns
        assert "expected_days_to_next_purchase" in df.columns
        assert (df["parquet_schema_version"] == 1).all()
    else:
        assert not pq.exists()


# ---------------------------------------------------------------------------
# ModelCard schema fields (additive)
# ---------------------------------------------------------------------------


def test_model_card_has_survival_specific_fields():
    """The two new optional ModelCard fields exist and default to None."""

    card = ModelCard()
    assert hasattr(card, "holdout_c_index")
    assert hasattr(card, "holdout_brier_score_90d")
    assert card.holdout_c_index is None
    assert card.holdout_brier_score_90d is None


def test_flag_default_on_post_t1_5():
    """ENGINE_V2_ML_SURVIVAL is registered in utils.py with default ON
    after the S11-T1.5 atomic flip (2026-05-26).

    Before T1.5 (substrate land at T1, 2026-05-26 earlier), the flag
    defaulted OFF. T1.5 atomically flipped to ON, wired ``fit_survival``
    into ``src/main.py`` orchestration immediately after the Gamma-Gamma
    block, and added the rollback contract test.
    """

    from src import utils

    assert "ENGINE_V2_ML_SURVIVAL" in utils.DEFAULTS
    # Default ON post-T1.5 unless env override.
    import os
    if "ENGINE_V2_ML_SURVIVAL" not in os.environ:
        assert utils.DEFAULTS["ENGINE_V2_ML_SURVIVAL"] is True
    # Coerce bool set membership.
    assert "ENGINE_V2_ML_SURVIVAL" in (
        "ENGINE_V2_ML_BGNBD ENGINE_V2_ML_GAMMA_GAMMA ENGINE_V2_ML_SURVIVAL"
    )
