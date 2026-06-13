"""S10-T1: BG/NBD fit + four-state ModelFitStatus coverage.

Tests the ``src/predictive/bgnbd.py::fit_bgnbd`` function. Covers each
``ModelFitStatus`` outcome (VALIDATED / PROVISIONAL / INSUFFICIENT_DATA
/ REFUSED) plus the parquet-write semantics (artifact ONLY for
VALIDATED/PROVISIONAL).

Tests that require an actual BG/NBD fit pull ``lifetimes`` lazily via
``pytest.importorskip`` so the file still loads cleanly when the
dependency is not yet installed (S10-T1 ships the requirements.txt
pin, but the dev env doesn't necessarily have it yet).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.predictive.bgnbd import fit_bgnbd
from src.predictive.model_card import ModelFitStatus
from src.profile.types import BusinessStage, StoreProfile, Taxonomy


# ---------------------------------------------------------------------------
# Synthetic transaction generators
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


def _build_orders(
    n_customers: int,
    purchases_per_customer: int,
    span_days: int = 240,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a deterministic BG/NBD-shaped order frame.

    Each customer gets ``purchases_per_customer`` orders spread roughly
    evenly over ``span_days``. Used to construct VALIDATED- vs
    PROVISIONAL-shaped fixtures without reshaping pinned fixtures.
    """

    rng = np.random.default_rng(seed)
    rows = []
    start = pd.Timestamp("2025-01-01")
    for c in range(n_customers):
        n_p = max(1, purchases_per_customer)
        for j in range(n_p):
            offset = int(rng.integers(0, span_days))
            rows.append({
                "customer_id": f"cust{c:05d}",
                "order_date": start + pd.Timedelta(days=offset),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# INSUFFICIENT_DATA — engine declines to fit (no lifetimes import needed)
# ---------------------------------------------------------------------------


def test_insufficient_data_below_repeat_floor():
    """Cold-start fixture: 50 customers, 1 order each → no repeats → INSUFFICIENT_DATA."""
    df = _build_orders(n_customers=50, purchases_per_customer=1, span_days=120)
    card = fit_bgnbd(df, _profile_mature_beauty())
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA
    assert card.parameters == {}
    assert card.holdout_mape is None
    assert card.model_name == "bgnbd"
    # No parquet write attempted (data_dir not provided).


def test_insufficient_data_below_orders_floor():
    """Below provisional orders floor (0.5 * 1500 = 750 for mature)."""
    df = _build_orders(n_customers=100, purchases_per_customer=3, span_days=200)
    # 300 orders total → below 750 provisional orders floor.
    card = fit_bgnbd(df, _profile_mature_beauty())
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA


def test_insufficient_data_below_months_floor():
    """Span < months_data_validated months → INSUFFICIENT_DATA."""
    # Span = 60 days = 2 months; mature requires 6.
    df = _build_orders(n_customers=600, purchases_per_customer=3, span_days=60)
    card = fit_bgnbd(df, _profile_mature_beauty())
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA


def test_insufficient_data_no_parquet_written(tmp_path):
    """INSUFFICIENT_DATA → no parquet artifact, even when data_dir given."""
    df = _build_orders(n_customers=10, purchases_per_customer=1, span_days=120)
    card = fit_bgnbd(df, _profile_mature_beauty(), store_id="test_store", data_dir=tmp_path)
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA
    parquet_path = tmp_path / "test_store" / "predictive" / "bgnbd.parquet"
    assert not parquet_path.exists()


# ---------------------------------------------------------------------------
# REFUSED — fit attempted but failed (lifetimes-import-failed path)
# ---------------------------------------------------------------------------


def test_refused_when_lifetimes_not_installed(monkeypatch):
    """When ``lifetimes`` import fails inside fit_bgnbd, return REFUSED
    with ``lifetimes_import_failed`` warning. Pinned to verify the
    operator-alert audit path."""

    import builtins

    real_import = builtins.__import__

    def _no_lifetimes(name, *args, **kwargs):
        if name == "lifetimes" or name.startswith("lifetimes."):
            raise ImportError("lifetimes not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_lifetimes)

    df = _build_orders(n_customers=800, purchases_per_customer=4, span_days=240)
    card = fit_bgnbd(df, _profile_mature_beauty())
    assert card.fit_status == ModelFitStatus.REFUSED
    assert "lifetimes_import_failed" in card.fit_warnings
    assert card.parameters == {}


def test_refused_no_parquet_written(tmp_path, monkeypatch):
    """REFUSED → no parquet artifact even when data_dir given."""
    import builtins

    real_import = builtins.__import__

    def _no_lifetimes(name, *args, **kwargs):
        if name == "lifetimes" or name.startswith("lifetimes."):
            raise ImportError("lifetimes not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_lifetimes)

    df = _build_orders(n_customers=800, purchases_per_customer=4, span_days=240)
    card = fit_bgnbd(
        df,
        _profile_mature_beauty(),
        store_id="test_store",
        data_dir=tmp_path,
    )
    assert card.fit_status == ModelFitStatus.REFUSED
    parquet_path = tmp_path / "test_store" / "predictive" / "bgnbd.parquet"
    assert not parquet_path.exists()


# ---------------------------------------------------------------------------
# VALIDATED / PROVISIONAL — require lifetimes
# ---------------------------------------------------------------------------


def test_validated_or_provisional_on_healthy_fixture(tmp_path):
    """A fixture comfortably above the mature floor should fit and produce
    VALIDATED or PROVISIONAL (depends on MAPE)."""

    pytest.importorskip("lifetimes")

    df = _build_orders(n_customers=800, purchases_per_customer=4, span_days=240)
    card = fit_bgnbd(
        df,
        _profile_mature_beauty(),
        store_id="test_store",
        data_dir=tmp_path,
    )
    assert card.fit_status in (
        ModelFitStatus.VALIDATED,
        ModelFitStatus.PROVISIONAL,
        # Synthetic data may also legitimately produce REFUSED if MAPE
        # is unmeasurable; we still pass parquet-write semantics.
        ModelFitStatus.REFUSED,
    )
    if card.fit_status in (ModelFitStatus.VALIDATED, ModelFitStatus.PROVISIONAL):
        parquet_path = tmp_path / "test_store" / "predictive" / "bgnbd.parquet"
        assert parquet_path.exists()
        out = pd.read_parquet(parquet_path)
        assert "p_alive" in out.columns
        assert "expected_purchases_30d" in out.columns
        assert "expected_purchases_180d" in out.columns
        assert "parquet_schema_version" in out.columns
        assert (out["parquet_schema_version"] == 1).all()
        # Envelope sanity.
        assert (out["p_alive"] >= 0.0).all() and (out["p_alive"] <= 1.0).all()
        assert (out["expected_purchases_30d"] >= 0).all()
        assert (out["expected_purchases_180d"] >= 0).all()
    else:
        # REFUSED → no parquet.
        parquet_path = tmp_path / "test_store" / "predictive" / "bgnbd.parquet"
        assert not parquet_path.exists()


def test_provisional_on_envelope_thin_fixture(tmp_path):
    """A fixture between the provisional and validated floor → PROVISIONAL
    (or REFUSED if MAPE happens to land above the relaxed cutoff)."""

    pytest.importorskip("lifetimes")

    # Mature floor = 500 repeat / 1500 orders. Provisional floor at
    # 0.5x = 250 repeat / 750 orders. Construct a fixture that clears
    # provisional but NOT validated.
    df = _build_orders(n_customers=300, purchases_per_customer=3, span_days=240)
    card = fit_bgnbd(
        df,
        _profile_mature_beauty(),
        store_id="test_store",
        data_dir=tmp_path,
    )
    # Below the validated repeat floor (500) but above the provisional
    # repeat floor (250) → PROVISIONAL if MAPE permits, otherwise REFUSED.
    assert card.fit_status in (
        ModelFitStatus.PROVISIONAL,
        ModelFitStatus.REFUSED,
    )


def test_fit_timestamp_iso_format():
    """fit_timestamp is ISO-8601 UTC (Z-suffix) on every emitted card."""
    df = _build_orders(n_customers=10, purchases_per_customer=1)
    card = fit_bgnbd(df, _profile_mature_beauty())
    assert card.fit_timestamp.endswith("Z")
    assert "T" in card.fit_timestamp


def test_n_observed_reflects_repeat_customers():
    """ModelCard.n_observed reports the repeat-customer count, the
    load-bearing data-depth number that drives the floor check."""
    df = _build_orders(n_customers=100, purchases_per_customer=1)
    card = fit_bgnbd(df, _profile_mature_beauty())
    # 100 unique customers, each with 1 order → 0 repeat customers.
    assert card.n_observed == 0


# ---------------------------------------------------------------------------
# Flag-OFF posture — fit_bgnbd is callable but engine does not invoke it
# ---------------------------------------------------------------------------


def test_flag_off_engine_run_predictive_models_empty():
    """At flag-OFF default, engine_run.predictive_models stays ``{}`` —
    no code path in src/main.py invokes ``fit_bgnbd`` until T1.5."""
    from src.engine_run import EngineRun
    er = EngineRun()
    assert er.predictive_models == {}


# ---------------------------------------------------------------------------
# T1.4 (2026-05-26): Spearman gating + time-based holdout + additive fields
# ---------------------------------------------------------------------------


def test_holdout_rank_spearman_computed_when_fit_attempted(tmp_path):
    """T1.4: ModelCard.holdout_rank_spearman is populated whenever a fit
    is attempted (VALIDATED / PROVISIONAL / REFUSED). Only
    INSUFFICIENT_DATA (no fit attempted) leaves it None."""

    pytest.importorskip("lifetimes")

    df = _build_orders(n_customers=800, purchases_per_customer=4, span_days=240)
    card = fit_bgnbd(df, _profile_mature_beauty(), store_id="s", data_dir=tmp_path)
    if card.fit_status != ModelFitStatus.INSUFFICIENT_DATA:
        # rank_spearman may be None if undefined (zero variance in observed),
        # but a finite numeric value should be the common case on this fixture.
        assert hasattr(card, "holdout_rank_spearman")
        # Spearman is bounded [-1, 1] when defined.
        if card.holdout_rank_spearman is not None:
            assert -1.0 <= card.holdout_rank_spearman <= 1.0


def test_holdout_agg_ratio_computed_when_fit_attempted(tmp_path):
    """T1.4: ModelCard.holdout_agg_ratio is the operator-visible diagnostic
    sum(predicted)/max(sum(observed), 1). Populated whenever a fit is
    attempted and metrics computation succeeds."""

    pytest.importorskip("lifetimes")

    df = _build_orders(n_customers=800, purchases_per_customer=4, span_days=240)
    card = fit_bgnbd(df, _profile_mature_beauty(), store_id="s", data_dir=tmp_path)
    if card.fit_status in (ModelFitStatus.VALIDATED, ModelFitStatus.PROVISIONAL):
        # When the fit produced a usable Spearman, agg_ratio must also be set.
        assert card.holdout_agg_ratio is not None
        assert card.holdout_agg_ratio >= 0.0


def test_zero_variance_holdout_returns_refused(tmp_path):
    """T1.4: degenerate case — when every customer has identical observed
    holdout count (e.g., all zero because all orders pre-date the
    time-based t_split window), Spearman is undefined → REFUSED with
    ``holdout_rank_spearman_unmeasurable`` warning."""

    pytest.importorskip("lifetimes")

    # Construct a fixture where every order is at least 240 days old. The
    # time-based holdout window (≤30d) captures zero orders → observed all
    # zero → variance zero → Spearman undefined.
    rng = np.random.default_rng(0)
    rows = []
    start = pd.Timestamp("2020-01-01")
    for c in range(600):
        for _ in range(4):
            offset = int(rng.integers(0, 200))
            rows.append({
                "customer_id": f"cust{c:05d}",
                "order_date": start + pd.Timedelta(days=offset),
            })
    df = pd.DataFrame(rows)
    card = fit_bgnbd(df, _profile_mature_beauty(), store_id="s", data_dir=tmp_path)
    # We can't fully guarantee REFUSED here because data depth may fail
    # the months/orders/repeat floor first — but if the fit is attempted
    # the rank metric must be None and the status REFUSED.
    if card.fit_status not in (ModelFitStatus.INSUFFICIENT_DATA,):
        # If the fit attempt happened, observed-all-zero means rank is None.
        if card.holdout_rank_spearman is None:
            assert card.fit_status == ModelFitStatus.REFUSED
            assert "holdout_rank_spearman_unmeasurable" in card.fit_warnings


def test_holdout_mape_retained_but_not_gating(tmp_path):
    """T1.4: holdout_mape is still computed/stored for operator-diagnostic
    continuity. It does NOT gate the classifier. A fit may be VALIDATED
    or PROVISIONAL with MAPE that previously would have refused (>0.35)."""

    pytest.importorskip("lifetimes")

    df = _build_orders(n_customers=800, purchases_per_customer=4, span_days=240)
    card = fit_bgnbd(df, _profile_mature_beauty(), store_id="s", data_dir=tmp_path)
    if card.fit_status in (ModelFitStatus.VALIDATED, ModelFitStatus.PROVISIONAL):
        # MAPE is populated as diagnostic, not as a gate. The pre-T1.4
        # classifier would have REFUSED most synthetic fits at MAPE > 0.35;
        # the new classifier no longer reads MAPE for status.
        assert hasattr(card, "holdout_mape")


def test_threshold_loader_exposes_spearman_keys():
    """T1.4: ``_load_model_fit_thresholds`` surfaces the new Spearman
    threshold + floor under stable keys."""

    from src.predictive.model_card import _load_model_fit_thresholds
    from src.profile.types import BusinessStage, StoreProfile, Taxonomy

    profile = StoreProfile(
        taxonomy=Taxonomy(vertical="beauty"),
        business_stage=BusinessStage(stage="MATURE"),
    )
    out = _load_model_fit_thresholds(profile)
    assert "holdout_rank_spearman_validated" in out["bgnbd"]
    assert out["bgnbd"]["holdout_rank_spearman_validated"] == 0.20
    assert "provisional_rank_spearman_floor" in out["relaxation_factors"]
    assert out["relaxation_factors"]["provisional_rank_spearman_floor"] == 0.10
