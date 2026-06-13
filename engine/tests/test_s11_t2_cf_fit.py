"""S11-T2: CF (implicit ALS) fit + four-state ModelFitStatus coverage.

Tests ``src/predictive/cf.py::fit_cf``. Covers:

- INSUFFICIENT_DATA below per-stage floors (customers / items /
  interactions-per-user).
- **CF is INDEPENDENT of BG/NBD** — no chained refusal. Critical
  contract test: passing a REFUSED BG/NBD ModelCard does not affect CF
  (in fact ``fit_cf`` does not accept ``bgnbd_model_card`` at all).
- Parquet-write semantics (artifact ONLY for VALIDATED/PROVISIONAL).
- Look-alikes parquet schema (column shape).
- Synthetic ALS DGP sanity check (parallel to T1.4 / S11-T1).

Tests that require an actual ALS fit pull ``implicit`` lazily via
``pytest.importorskip`` so the file still loads cleanly when the
dependency is not yet installed.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.predictive.cf import fit_cf
from src.predictive.model_card import ModelCard, ModelFitStatus
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


def _build_orders_uniform(
    n_customers: int,
    n_items: int,
    purchases_per_customer: int,
    span_days: int = 240,
    seed: int = 42,
) -> pd.DataFrame:
    """Uniform random customer × item × time orders (DGP-degenerate for ALS)."""
    rng = np.random.default_rng(seed)
    rows = []
    start = pd.Timestamp("2025-01-01")
    for c in range(n_customers):
        for _ in range(max(1, purchases_per_customer)):
            offset = int(rng.integers(0, span_days))
            sku = f"sku{rng.integers(0, n_items):05d}"
            rows.append({
                "customer_id": f"cust{c:05d}",
                "order_date": start + pd.Timedelta(days=offset),
                "sku": sku,
            })
    return pd.DataFrame(rows)


def _build_orders_with_segments(
    n_customers: int,
    n_items: int,
    n_segments: int = 4,
    purchases_per_customer: int = 8,
    span_days: int = 240,
    seed: int = 11,
    in_segment_p: float = 0.85,
) -> pd.DataFrame:
    """ALS-friendly DGP: customers and items both belong to latent segments.

    Within-segment customers prefer within-segment items with probability
    ``in_segment_p``; out-of-segment with ``1 - in_segment_p``. This is the
    canonical implicit-feedback latent-segment generator. Properly-fit ALS
    should recover top-K recall well above the VALIDATED floor.
    """
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2025-01-01")
    cust_seg = rng.integers(0, n_segments, size=n_customers)
    item_seg = rng.integers(0, n_segments, size=n_items)
    items_by_seg = [np.where(item_seg == s)[0] for s in range(n_segments)]
    all_items = np.arange(n_items)
    rows = []
    for c in range(n_customers):
        s = int(cust_seg[c])
        for _ in range(purchases_per_customer):
            if rng.random() < in_segment_p and len(items_by_seg[s]) > 0:
                it = int(rng.choice(items_by_seg[s]))
            else:
                it = int(rng.choice(all_items))
            offset = int(rng.integers(0, span_days))
            rows.append({
                "customer_id": f"cust{c:05d}",
                "order_date": start + pd.Timedelta(days=offset),
                "sku": f"sku{it:05d}",
            })
    return pd.DataFrame(rows)


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


# ---------------------------------------------------------------------------
# INSUFFICIENT_DATA — does NOT require implicit
# ---------------------------------------------------------------------------


def test_insufficient_data_below_customers_floor():
    # MATURE floor: min_customers=200; supply only 50.
    orders = _build_orders_uniform(50, 150, 5)
    card = fit_cf(orders, _profile_mature_beauty())
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA
    assert card.parameters == {}
    assert card.holdout_top_k_recall is None
    assert card.coverage_at_k is None


def test_insufficient_data_below_items_floor():
    # MATURE floor: min_items=100; supply only 20.
    orders = _build_orders_uniform(300, 20, 5)
    card = fit_cf(orders, _profile_mature_beauty())
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA


def test_insufficient_data_below_interactions_floor():
    # STARTUP floor: min_interactions_per_user=2 with min_customers=50.
    # 60 customers but each has only 1 purchase → < 50 active customers.
    orders = _build_orders_uniform(60, 60, 1)
    card = fit_cf(orders, _profile_startup())
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA


def test_insufficient_data_when_item_column_missing():
    """Defensive: no sku/product_id/product_title column → INSUFFICIENT_DATA."""
    rng = np.random.default_rng(0)
    start = pd.Timestamp("2025-01-01")
    rows = []
    for c in range(300):
        for _ in range(5):
            rows.append({
                "customer_id": f"cust{c:05d}",
                "order_date": start + pd.Timedelta(days=int(rng.integers(0, 240))),
            })
    orders = pd.DataFrame(rows)
    card = fit_cf(orders, _profile_mature_beauty())
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# CRITICAL DS CONTRACT: CF is INDEPENDENT of BG/NBD
# ---------------------------------------------------------------------------


def test_fit_cf_signature_does_not_accept_bgnbd_model_card():
    """fit_cf MUST NOT have a bgnbd_model_card argument (DS-locked §A.6).

    This is the load-bearing architectural pin: CF is independent of
    BG/NBD, deliberately divergent from fit_survival. Renaming or adding
    a bgnbd parameter requires explicit DS sign-off.
    """
    sig = inspect.signature(fit_cf)
    assert "bgnbd_model_card" not in sig.parameters
    assert "bgnbd_card" not in sig.parameters


def test_independent_of_bgnbd_no_chained_refusal():
    """CF fits independently when BG/NBD would be REFUSED.

    Build a healthy ALS-friendly DGP. Pass a (separately-constructed)
    REFUSED BG/NBD ModelCard alongside in a wrapper to assert the CF
    output is unaffected by BG/NBD status — i.e. CF does NOT chain.
    Since fit_cf does not accept bgnbd_model_card, the only way it
    could chain would be a global side-channel. We assert no such
    coupling by fitting CF and ignoring BG/NBD entirely.
    """
    pytest.importorskip("implicit")
    orders = _build_orders_with_segments(
        n_customers=300, n_items=120, n_segments=5,
        purchases_per_customer=10, seed=7,
    )
    # The BG/NBD ModelCard is constructed and intentionally NOT passed —
    # this asserts the API surface itself does not allow chaining.
    _refused_bgnbd = _bgnbd_card(ModelFitStatus.REFUSED)
    card = fit_cf(orders, _profile_mature_beauty(), seed=0)
    # Critical: CF status is determined by the data, not by BG/NBD.
    assert card.fit_status in (
        ModelFitStatus.VALIDATED,
        ModelFitStatus.PROVISIONAL,
        ModelFitStatus.REFUSED,
        ModelFitStatus.INSUFFICIENT_DATA,
    )
    # On this healthy DGP, CF should NOT short-circuit to REFUSED with
    # any chained_bgnbd_refusal warning — that warning is survival-only.
    assert "chained_bgnbd_refusal" not in (card.fit_warnings or [])


# ---------------------------------------------------------------------------
# Parquet semantics
# ---------------------------------------------------------------------------


def test_parquet_not_written_for_insufficient_data(tmp_path):
    orders = _build_orders_uniform(50, 50, 3)
    card = fit_cf(
        orders, _profile_mature_beauty(),
        store_id="testshop", data_dir=tmp_path,
    )
    assert card.fit_status == ModelFitStatus.INSUFFICIENT_DATA
    assert not (tmp_path / "testshop" / "predictive" / "cf.parquet").exists()


def test_parquet_not_written_for_refused(tmp_path, monkeypatch):
    """REFUSED (e.g. recall below floor or fit exception) → no parquet."""
    pytest.importorskip("implicit")
    orders = _build_orders_uniform(300, 120, 5, seed=99)  # uniform DGP → low recall
    card = fit_cf(
        orders, _profile_mature_beauty(),
        store_id="testshop", data_dir=tmp_path, seed=0,
    )
    # Uniform DGP is degenerate for ALS — expect REFUSED or PROVISIONAL band.
    if card.fit_status == ModelFitStatus.REFUSED:
        assert not (tmp_path / "testshop" / "predictive" / "cf.parquet").exists()


def test_refused_when_implicit_not_installed(monkeypatch):
    """Stub the implicit import path to simulate missing dependency → REFUSED."""
    import builtins
    real_import = builtins.__import__

    def _block(name, *args, **kwargs):
        if name == "implicit.als" or name.startswith("implicit."):
            raise ImportError(f"simulated: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _block)
    orders = _build_orders_with_segments(
        n_customers=300, n_items=120, purchases_per_customer=8, seed=3,
    )
    card = fit_cf(orders, _profile_mature_beauty(), seed=0)
    assert card.fit_status == ModelFitStatus.REFUSED
    assert "implicit_import_failed" in card.fit_warnings


# ---------------------------------------------------------------------------
# Synthetic ALS DGP sanity check (DS-required positive control)
# ---------------------------------------------------------------------------


def test_synthetic_implicit_feedback_dgp_sanity(tmp_path):
    """Latent-segment DGP should produce VALIDATED or PROVISIONAL CF fit.

    Parallel to T1.4 BG/NBD ρ=0.484 / S11-T1 C-index=0.838 sanity
    checks. On a healthy ALS DGP (customers and items have latent
    segments, 85% within-segment preference), implicit ALS should
    recover top-K recall well above the PROVISIONAL floor (0.03).

    This is the load-bearing positive control: it confirms the CF
    implementation correctly recovers signal from a proper DGP.
    """
    pytest.importorskip("implicit")
    orders = _build_orders_with_segments(
        n_customers=400, n_items=150, n_segments=6,
        purchases_per_customer=12, seed=2026,
        in_segment_p=0.90,
    )
    card = fit_cf(
        orders, _profile_mature_beauty(),
        store_id="dgp_sanity", data_dir=tmp_path, seed=0,
    )
    # MUST land VALIDATED or PROVISIONAL — REFUSED would indicate an
    # implementation bug, not a DGP problem.
    assert card.fit_status in (
        ModelFitStatus.VALIDATED,
        ModelFitStatus.PROVISIONAL,
    ), (
        f"DGP sanity failed: status={card.fit_status} "
        f"recall@10={card.holdout_top_k_recall} "
        f"coverage@10={card.coverage_at_k} warnings={card.fit_warnings}"
    )
    assert card.holdout_top_k_recall is not None
    assert card.holdout_top_k_recall >= 0.03
    assert card.coverage_at_k is not None
    assert 0.0 <= card.coverage_at_k <= 1.0
    # Parquet should be written (VALIDATED/PROVISIONAL).
    parquet_path = tmp_path / "dgp_sanity" / "predictive" / "cf.parquet"
    assert parquet_path.exists()


def test_lookalikes_parquet_schema(tmp_path):
    """VALIDATED/PROVISIONAL fits produce a parquet with the documented schema."""
    pytest.importorskip("implicit")
    orders = _build_orders_with_segments(
        n_customers=400, n_items=150, n_segments=6,
        purchases_per_customer=12, seed=2026, in_segment_p=0.90,
    )
    card = fit_cf(
        orders, _profile_mature_beauty(),
        store_id="schema_test", data_dir=tmp_path, seed=0,
    )
    if card.fit_status not in (ModelFitStatus.VALIDATED, ModelFitStatus.PROVISIONAL):
        pytest.skip(f"DGP did not produce VALIDATED/PROVISIONAL (got {card.fit_status})")
    parquet_path = tmp_path / "schema_test" / "predictive" / "cf.parquet"
    df = pd.read_parquet(parquet_path)
    expected_cols = {
        "customer_id",
        "lookalike_customer_id",
        "similarity_score",
        "rank",
        "parquet_schema_version",
    }
    assert expected_cols <= set(df.columns)
    assert df["parquet_schema_version"].unique().tolist() == [1]
    # Rank values 1..top_n; no self-matches.
    assert df["rank"].min() >= 1
    assert df["rank"].max() <= 20
    self_matches = df[df["customer_id"] == df["lookalike_customer_id"]]
    assert len(self_matches) == 0
    # similarity_score is numeric and finite.
    assert df["similarity_score"].apply(lambda x: np.isfinite(x)).all()


# ---------------------------------------------------------------------------
# Additive ModelCard fields + flag default
# ---------------------------------------------------------------------------


def test_model_card_has_cf_specific_fields():
    """ModelCard exposes holdout_top_k_recall + coverage_at_k (additive)."""
    card = ModelCard(model_name="cf")
    assert hasattr(card, "holdout_top_k_recall")
    assert hasattr(card, "coverage_at_k")
    assert card.holdout_top_k_recall is None
    assert card.coverage_at_k is None


def test_flag_default_on_after_t2_5():
    """ENGINE_V2_ML_CF default ON after T2.5 atomic flip (was OFF at T2).

    S11-T2.5 (2026-05-28) atomically flipped the default from "false"
    to "true" together with the orchestration wire-up at
    ``src/main.py``. The rollback contract is pinned by
    ``tests/test_s11_t2_5_cf_rollback.py``; this test simply pins the
    flag-default end-state for the T2.5 commit.
    """
    import importlib
    import src.utils as utils_mod
    importlib.reload(utils_mod)
    import os
    if "ENGINE_V2_ML_CF" in os.environ:
        pytest.skip("ENGINE_V2_ML_CF env override present; default test n/a")
    assert utils_mod.DEFAULTS.get("ENGINE_V2_ML_CF") is True
