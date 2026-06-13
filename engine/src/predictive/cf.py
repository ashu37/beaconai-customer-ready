"""Collaborative Filtering (implicit ALS) fit (Sprint 11 — T2).

Wraps a classical Alternating Least Squares implicit-feedback model via
``implicit.als.AlternatingLeastSquares`` (Ben Frederickson; widely used
recommender library). Produces a typed ``ModelCard`` describing fit
health under the four-state ``ModelFitStatus`` vocabulary documented in
``src/predictive/model_card.py``.

S11-T2 ship constraints
=======================

- Flag-OFF land. Behind ``ENGINE_V2_ML_CF`` (default OFF).
- No PlayCard consumes the fit output. Surfaces only on
  ``engine_run.predictive_models["cf"]`` when the flag is ON (T2.5
  atomic flip wires it; T2 is module + schema only).
- Parquet per-customer look-alikes artifact at
  ``data/<store_id>/predictive/cf.parquet`` is written **only when
  fit_status in {VALIDATED, PROVISIONAL}**. INSUFFICIENT_DATA / REFUSED
  produce a ModelCard with no parquet artifact (privacy posture, D-3
  deletion semantics).
- ``implicit`` is imported lazily inside ``fit_cf`` so the module imports
  without the dep present (INSUFFICIENT_DATA tests do not need
  ``implicit``).

DS-locked validation metrics (sign-off 2026-05-26)
==================================================

PRIMARY gate: **top-K recall @ K=10** between the implicit-ALS top-10
recommendation list for each customer and the held-out
customer×item interactions. VALIDATED floors stage-keyed
{startup 0.05, growth 0.06, mature 0.08, enterprise 0.10}; PROVISIONAL
floor 0.03; REFUSED below 0.03 or on convergence failure.

SECONDARY diagnostic: **coverage @ 10** (fraction of catalog items
appearing in any user's top-10 list). Operator-visible
popularity-bias warning surface; **does NOT gate** acceptance.

CF is INDEPENDENT of BG/NBD (DS-locked)
========================================

Per DS S11 plan review §A.6 + S11-T1.5 review §F: CF's signal
(user-item co-occurrence / implicit feedback matrix) does not structurally
depend on the gap-time signal that BG/NBD/survival evaluate. **CF DOES
NOT CHAIN ON BG/NBD.** ``fit_cf`` accepts no ``bgnbd_model_card``
argument and fits independently regardless of BG/NBD's fit status. This
is a deliberate architectural divergence from ``fit_survival``.

Look-alikes only (NOT item-affinity) at S11
============================================

S11 ships customer-side ALS factors only. Per-customer top-N look-alike
customers (similarity = cosine in latent factor space). Item-affinity
(cross-sell) is a reusable artifact from the same factor matrices and
can be added in a later sprint without re-fitting ALS. Lock per IM
plan §C Q1 + DS verdict §(a) change 8.

Thresholds: KI-NEW-P extension (speculative-until-S14 calibration).
"""

from __future__ import annotations

import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .model_card import ModelCard, ModelFitStatus, _load_model_fit_thresholds


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_item_column(orders_df: pd.DataFrame) -> Optional[str]:
    """Pick the item-identifier column from the orders frame.

    Preference order: ``sku`` → ``product_id`` → ``product_title``. Returns
    ``None`` when no item column is present (engine still has an
    interaction matrix if we fall back to a constant — but CF on a
    single-item catalog is degenerate, so we surface INSUFFICIENT_DATA in
    that case).
    """

    for col in ("sku", "product_id", "product_title"):
        if col in orders_df.columns:
            return col
    return None


def _time_based_holdout_split(
    orders_df: pd.DataFrame,
    *,
    desired_window_days: float = 60.0,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split orders into ``[t0, t_split]`` train and ``(t_split, t_end]`` holdout.

    Mirrors ``src/predictive/bgnbd.py::_time_based_holdout_split`` shape;
    window capped at ~25% of observed span (defensive for tiny frames).
    """

    if orders_df.empty:
        return orders_df.iloc[0:0].copy(), orders_df.iloc[0:0].copy()

    od = pd.to_datetime(orders_df["order_date"])
    span_days = float((od.max() - od.min()).days)
    if span_days <= 1.0:
        return orders_df.iloc[0:0].copy(), orders_df.iloc[0:0].copy()
    window_days = float(min(desired_window_days, max(1.0, span_days / 4.0)))
    t_split = od.max() - pd.Timedelta(days=window_days)
    df = orders_df.copy()
    df["order_date"] = od
    train = df.loc[df["order_date"] <= t_split].copy()
    holdout = df.loc[df["order_date"] > t_split].copy()
    return train, holdout


def _build_interaction_matrix(
    train_orders: pd.DataFrame,
    item_col: str,
) -> Tuple[Any, List[str], List[str]]:
    """Build a sparse customer × item interaction matrix.

    Values are integer order-counts (NOT binarized); ``implicit`` handles
    confidence-weighting downstream via its ``alpha`` parameter (we use
    library defaults). Returns ``(csr_matrix, customer_ids, item_ids)``
    where the id lists give row/col -> id mapping.
    """

    from scipy.sparse import csr_matrix  # local import

    sub = train_orders[["customer_id", item_col]].copy()
    sub["customer_id"] = sub["customer_id"].astype(str)
    sub[item_col] = sub[item_col].astype(str)
    # Group counts.
    counts = (
        sub.groupby(["customer_id", item_col]).size().reset_index(name="n")
    )

    customer_ids = sorted(counts["customer_id"].unique().tolist())
    item_ids = sorted(counts[item_col].unique().tolist())
    c_idx = {c: i for i, c in enumerate(customer_ids)}
    i_idx = {it: i for i, it in enumerate(item_ids)}

    rows = counts["customer_id"].map(c_idx).to_numpy()
    cols = counts[item_col].map(i_idx).to_numpy()
    vals = counts["n"].astype(float).to_numpy()

    mat = csr_matrix(
        (vals, (rows, cols)),
        shape=(len(customer_ids), len(item_ids)),
        dtype=np.float32,
    )
    return mat, customer_ids, item_ids


def _top_k_recall_and_coverage(
    user_items: Any,
    holdout_orders: pd.DataFrame,
    customer_ids: List[str],
    item_ids: List[str],
    item_col: str,
    estimator: Any,
    *,
    k: int = 10,
) -> Tuple[float, float, int]:
    """Compute top-K recall + coverage @ K against the holdout window.

    Returns ``(recall, coverage, n_eval_customers)``.

    - ``recall``: mean over held-out customers of
      ``|recommended_top_k ∩ heldout_items| / |heldout_items|``.
    - ``coverage``: fraction of catalog items that appear in any
      customer's top-K list (operator diagnostic; not gating).
    - ``n_eval_customers``: count of held-out customers that exist in
      the training customer set (eligible for recall evaluation).
    """

    if holdout_orders.empty:
        return 0.0, 0.0, 0

    c_idx = {c: i for i, c in enumerate(customer_ids)}
    i_idx = {it: i for i, it in enumerate(item_ids)}

    ho = holdout_orders[["customer_id", item_col]].copy()
    ho["customer_id"] = ho["customer_id"].astype(str)
    ho[item_col] = ho[item_col].astype(str)
    # Held-out customer -> set of held-out item indices that exist in the
    # train catalog (items the model could plausibly recommend).
    grouped = ho.groupby("customer_id")[item_col].apply(
        lambda s: {i_idx[v] for v in s.unique() if v in i_idx}
    )

    union_top_k_items: set = set()
    recalls: List[float] = []
    n_eval = 0

    for cust, true_items in grouped.items():
        if not true_items:
            continue
        ci = c_idx.get(cust)
        if ci is None:
            continue
        n_eval += 1
        try:
            ids, _scores = estimator.recommend(
                ci,
                user_items[ci],
                N=k,
                filter_already_liked_items=False,
            )
        except Exception:  # noqa: BLE001
            # Skip un-rankable customers (empty interaction row, etc).
            continue
        topk = {int(x) for x in np.asarray(ids).tolist()}
        union_top_k_items.update(topk)
        hit = len(topk & true_items)
        recalls.append(hit / max(1, len(true_items)))

    recall = float(np.mean(recalls)) if recalls else 0.0
    coverage = (
        float(len(union_top_k_items) / max(1, len(item_ids)))
        if item_ids
        else 0.0
    )
    return recall, coverage, n_eval


def fit_cf(
    orders_df: pd.DataFrame,
    profile: Any,
    *,
    store_id: str = "",
    data_dir: Optional[Path] = None,
    seed: int = 0,
    yaml_path: Optional[Path] = None,
) -> ModelCard:
    """Fit implicit ALS collaborative filtering and return a typed ``ModelCard``.

    Arguments:

    - ``orders_df``: schema ``customer_id``, ``order_date``, plus one of
      ``sku``/``product_id``/``product_title`` (item column). Other
      columns ignored.
    - ``profile``: ``StoreProfile`` (for stage-keyed threshold lookup).

    **CF is INDEPENDENT of BG/NBD.** No ``bgnbd_model_card`` argument.
    No chained refusal. CF fits on its own regardless of BG/NBD status.
    This is a deliberate architectural divergence from ``fit_survival``
    (per DS S11 plan review §A.6).

    Flow:

    1. **INSUFFICIENT_DATA gate.** Below stage-keyed floors on customers /
       items / interactions-per-user → INSUFFICIENT_DATA. No fit. No
       parquet.
    2. Time-based holdout split (60d window default — long enough for
       honest recall@10 evaluation, short enough to leave training mass).
    3. Build sparse customer × item interaction matrix from train slice.
    4. Fit ``AlternatingLeastSquares()`` via lazy import. Convergence
       failure (NaN factors) or fit exception → REFUSED.
    5. Compute metrics: top-K recall @ K=10 (gating) + coverage @ K=10
       (diagnostic).
    6. Classify under four-state rule: recall ≥ stage VALIDATED floor →
       VALIDATED; ∈ [PROVISIONAL_floor, validated) → PROVISIONAL;
       < PROVISIONAL_floor → REFUSED.
    7. On {VALIDATED, PROVISIONAL}: write top-N look-alikes parquet
       (N=20 by default) to ``<data_dir>/<store_id>/predictive/cf.parquet``.

    Returns the ModelCard. The caller (S13 audience-builder) decides
    whether the fit status permits consumption.
    """

    thresholds_full = _load_model_fit_thresholds(profile, yaml_path=yaml_path)
    cf_thr = thresholds_full["cf"]
    relax = thresholds_full["cf_relaxation_factors"]
    hyper = thresholds_full["cf_hyperparameters"]

    min_customers = cf_thr["min_customers"]
    min_items = cf_thr["min_items"]
    min_interactions_per_user = cf_thr["min_interactions_per_user"]
    recall_validated = cf_thr["top_k_recall_validated"]
    recall_provisional_floor = relax["provisional_top_k_recall_floor"]

    top_k = hyper["top_k"]
    top_n_lookalikes = hyper["top_n_lookalikes_per_customer"]
    als_factors = hyper["als_factors"]
    als_reg = hyper["als_regularization"]
    als_iterations = hyper["als_iterations"]

    training_window_days = (
        int(
            (
                pd.to_datetime(orders_df["order_date"]).max()
                - pd.to_datetime(orders_df["order_date"]).min()
            ).days
        )
        if not orders_df.empty
        else 0
    )

    # ---- Step 1: INSUFFICIENT_DATA gate -----------------------------------
    # NOTE: NO chained refusal on BG/NBD. CF is independent (DS-locked).
    item_col = _resolve_item_column(orders_df)
    if item_col is None or orders_df.empty:
        return ModelCard(
            model_name="cf",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            parameters={},
            training_window_days=training_window_days,
            n_observed=0,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    n_customers = int(orders_df["customer_id"].nunique())
    n_items = int(orders_df[item_col].nunique())
    # Customers with at least min_interactions_per_user total orders.
    by_cust = orders_df.groupby("customer_id").size()
    n_active_customers = int((by_cust >= min_interactions_per_user).sum())

    if (
        n_customers < min_customers
        or n_items < min_items
        or n_active_customers < min_customers
    ):
        return ModelCard(
            model_name="cf",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            parameters={},
            training_window_days=training_window_days,
            n_observed=n_customers,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # ---- Step 2: time-based holdout split ---------------------------------
    train_orders, holdout_orders = _time_based_holdout_split(
        orders_df, desired_window_days=60.0
    )
    if train_orders.empty or holdout_orders.empty:
        return ModelCard(
            model_name="cf",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            parameters={},
            training_window_days=training_window_days,
            n_observed=n_customers,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # ---- Step 3: build interaction matrix ---------------------------------
    try:
        user_items, customer_ids, item_ids = _build_interaction_matrix(
            train_orders, item_col
        )
    except Exception as exc:  # noqa: BLE001
        return ModelCard(
            model_name="cf",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=[f"matrix_build_failed:{type(exc).__name__}"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=n_customers,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    if len(customer_ids) < min_customers or len(item_ids) < min_items:
        return ModelCard(
            model_name="cf",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            parameters={},
            training_window_days=training_window_days,
            n_observed=len(customer_ids),
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # ---- Step 4: fit ALS (lazy import) ------------------------------------
    try:
        from implicit.als import AlternatingLeastSquares  # type: ignore
    except ImportError:
        return ModelCard(
            model_name="cf",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=["implicit_import_failed"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=len(customer_ids),
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    fit_warnings: List[str] = []
    estimator: Any = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            estimator = AlternatingLeastSquares(
                factors=int(als_factors),
                regularization=float(als_reg),
                iterations=int(als_iterations),
                random_state=int(seed),
                use_gpu=False,
            )
            estimator.fit(user_items, show_progress=False)
        except Exception as exc:  # noqa: BLE001
            return ModelCard(
                model_name="cf",
                fit_status=ModelFitStatus.REFUSED,
                fit_warnings=[f"fit_exception:{type(exc).__name__}"],
                parameters={},
                training_window_days=training_window_days,
                n_observed=len(customer_ids),
                metrics={},
                fit_timestamp=_now_iso(),
                parquet_schema_version=1,
            )
        for w in caught:
            name = type(w.message).__name__
            if "Convergence" in name:
                fit_warnings.append("convergence_warning")

    # Sanity: non-finite user/item factors → REFUSED (convergence failure).
    try:
        user_factors = np.asarray(estimator.user_factors, dtype=float)
        item_factors = np.asarray(estimator.item_factors, dtype=float)
    except Exception:  # noqa: BLE001
        user_factors = np.array([])
        item_factors = np.array([])

    if (
        user_factors.size == 0
        or item_factors.size == 0
        or not np.all(np.isfinite(user_factors))
        or not np.all(np.isfinite(item_factors))
    ):
        return ModelCard(
            model_name="cf",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + ["non_finite_factors"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=len(customer_ids),
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # ---- Step 5: holdout metrics ------------------------------------------
    try:
        recall, coverage, n_eval = _top_k_recall_and_coverage(
            user_items,
            holdout_orders,
            customer_ids,
            item_ids,
            item_col,
            estimator,
            k=int(top_k),
        )
    except Exception as exc:  # noqa: BLE001
        return ModelCard(
            model_name="cf",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + [f"recall_eval_failed:{type(exc).__name__}"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=len(customer_ids),
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # ---- Step 6: classify -------------------------------------------------
    if recall is None or not np.isfinite(recall):
        return ModelCard(
            model_name="cf",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + ["holdout_recall_unmeasurable"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=len(customer_ids),
            metrics={
                "holdout_top_k_recall": recall,
                "coverage_at_k": coverage,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    if recall < recall_provisional_floor:
        return ModelCard(
            model_name="cf",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + ["holdout_recall_below_floor"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=len(customer_ids),
            metrics={
                "holdout_top_k_recall": recall,
                "coverage_at_k": coverage,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    is_validated = (
        recall >= recall_validated
        and not fit_warnings
    )
    status = ModelFitStatus.VALIDATED if is_validated else ModelFitStatus.PROVISIONAL

    parameters: Dict[str, float] = {
        "als_factors": float(als_factors),
        "als_regularization": float(als_reg),
        "als_iterations": float(als_iterations),
        "n_customers": float(len(customer_ids)),
        "n_items": float(len(item_ids)),
        "n_eval_customers": float(n_eval),
    }

    card = ModelCard(
        model_name="cf",
        fit_status=status,
        fit_warnings=fit_warnings,
        parameters=parameters,
        training_window_days=training_window_days,
        n_observed=int(len(customer_ids)),
        metrics={
            "holdout_top_k_recall": recall,
            "coverage_at_k": coverage,
        },
        fit_timestamp=_now_iso(),
        parquet_schema_version=1,
    )

    # ---- Step 7: write parquet (VALIDATED / PROVISIONAL only) -------------
    if data_dir is not None and store_id:
        _write_lookalikes_parquet(
            user_factors=user_factors,
            customer_ids=customer_ids,
            data_dir=Path(data_dir),
            store_id=store_id,
            top_n=int(top_n_lookalikes),
        )

    return card


def _write_lookalikes_parquet(
    *,
    user_factors: np.ndarray,
    customer_ids: List[str],
    data_dir: Path,
    store_id: str,
    top_n: int = 20,
) -> Path:
    """Write per-customer top-N look-alike customers to parquet.

    Schema (parquet_schema_version=1):

    - ``customer_id``: str
    - ``lookalike_customer_id``: str
    - ``similarity_score``: float (cosine similarity in latent factor
      space; range [-1, 1], typically [0, 1]).
    - ``rank``: int (1..top_n).
    - ``parquet_schema_version``: int (constant 1).

    Self-matches are excluded. Computed in pure numpy (cosine over the
    user_factors matrix); ``implicit``'s native
    ``similar_users`` is also valid but the numpy form is library-agnostic
    and equally fast at our scale.
    """

    f = user_factors.astype(np.float32, copy=False)
    norms = np.linalg.norm(f, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    f_norm = f / norms
    # Cosine similarity matrix (N x N).
    sim = f_norm @ f_norm.T
    n = sim.shape[0]
    # Exclude self by setting diagonal to -inf.
    np.fill_diagonal(sim, -np.inf)
    # Argsort descending, take top_n.
    k = min(top_n, max(1, n - 1))
    # argpartition is O(N) — sufficient at our scale; sort the top-k.
    idx_part = np.argpartition(-sim, kth=k - 1, axis=1)[:, :k]
    rows: List[Dict[str, Any]] = []
    for i in range(n):
        cand = idx_part[i]
        cand_scores = sim[i, cand]
        order = np.argsort(-cand_scores)
        ranked = cand[order]
        for r, j in enumerate(ranked, start=1):
            rows.append(
                {
                    "customer_id": str(customer_ids[i]),
                    "lookalike_customer_id": str(customer_ids[int(j)]),
                    "similarity_score": float(sim[i, int(j)]),
                    "rank": int(r),
                    "parquet_schema_version": 1,
                }
            )
    out = pd.DataFrame(rows)
    out_dir = data_dir / store_id / "predictive"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "cf.parquet"
    out.to_parquet(target, index=False)
    return target


__all__ = ["fit_cf"]
