"""BG/NBD fit (Sprint 10 — T1, gating metric corrected at T1.4).

Wraps Fader-Hardie-Lee (2005) classical BG/NBD via the ``lifetimes``
package (Cam Davidson-Pilon). Produces a typed ``ModelCard`` describing
fit health under the four-state ``ModelFitStatus`` vocabulary documented
in ``src/predictive/model_card.py``.

S10-T1 ship constraints:

- Flag-OFF land. Behind ``ENGINE_V2_ML_BGNBD`` (default OFF).
- No PlayCard consumes the fit output. Surfaces only on
  ``engine_run.predictive_models["bgnbd"]`` when the flag is ON.
- Parquet per-customer artifact at
  ``data/<store_id>/predictive/bgnbd.parquet`` is written **only when
  fit_status in {VALIDATED, PROVISIONAL}**. INSUFFICIENT_DATA / REFUSED
  produce a ModelCard with no parquet artifact (privacy posture, D-3
  deletion semantics).
- ``lifetimes`` is imported lazily inside ``fit_bgnbd`` so that the
  module imports without the dep present (tests for INSUFFICIENT_DATA
  do not need ``lifetimes``).

S10-T1.4 (2026-05-26) — DS-locked metric swap:

The original T1 gating metric was per-customer frequency MAPE
(``mean(|observed - predicted| / max(observed, 1))``). DS verdict
2026-05-26 deprecated this: the denominator clamps to 1.0 for
single-purchase customers (the majority of DTC populations), so each
term ≈ predicted_value itself. The mean MAPE collapses to "mean
predicted 30-day repeat rate" by construction — it does NOT measure
error. A perfectly fit BG/NBD on a population with true 30-day repeat
probability 0.4 produces "MAPE" ≈ 0.4.

The S10 downstream consumer is RANK-ORDER for Klaviyo dispatch (per
``agent_outputs/ds-architect-s10-cold-start-and-eb-interaction.md``).
The operationally correct metric is therefore rank-order quality.

T1.4 corrections (additive on schema, no PlayCard / renderer change):

1. Holdout split is **time-based** (``t_split = t_end -
   holdout_window_days``), not 20% customer-hash. Fit on
   ``[t0, t_split]``; observe per-customer purchase count on
   ``(t_split, t_end]``.
2. **Primary gating metric: Spearman rank correlation** between
   predicted expected purchases and observed holdout-window counts.
3. **Aggregate calibration ratio** ``sum(predicted)/max(sum(observed),
   1)`` populated as an operator-visible diagnostic (does NOT gate).
4. **MAPE retained** on the ModelCard for operator-diagnostic
   continuity but **stops gating** (DS-deprecated).
"""

from __future__ import annotations

import hashlib
import math
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from .model_card import ModelCard, ModelFitStatus, _load_model_fit_thresholds


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_rfm_summary(orders_df: pd.DataFrame, observation_end: pd.Timestamp) -> pd.DataFrame:
    """Aggregate ``orders_df`` into the BG/NBD RFM summary frame.

    Expected ``orders_df`` schema (subset is sufficient):
    - ``customer_id``: str
    - ``order_date``: datetime64[ns]

    Returns one row per customer with columns ``frequency`` (repeat
    purchases), ``recency`` (days between first and last purchase),
    ``T`` (days between first purchase and observation_end).
    """

    if orders_df.empty:
        return pd.DataFrame(columns=["customer_id", "frequency", "recency", "T"])

    df = orders_df[["customer_id", "order_date"]].copy()
    df["order_date"] = pd.to_datetime(df["order_date"])

    grouped = df.groupby("customer_id")["order_date"].agg(["min", "max", "count"])
    grouped.columns = ["first", "last", "n_orders"]
    grouped = grouped.reset_index()
    grouped["frequency"] = grouped["n_orders"] - 1  # BG/NBD: repeat purchases
    grouped["recency"] = (grouped["last"] - grouped["first"]).dt.days.astype(float)
    grouped["T"] = (observation_end - grouped["first"]).dt.days.astype(float)
    return grouped[["customer_id", "frequency", "recency", "T"]]


def _data_depth_counts(orders_df: pd.DataFrame) -> Dict[str, Any]:
    """Return ``{months, repeat_customers, orders, observation_end}``.

    Months are computed from the observed order_date range
    (``(max - min).days / 30``). Repeat customers = customers with ≥ 2
    distinct orders.
    """

    if orders_df.empty:
        return {
            "months": 0.0,
            "repeat_customers": 0,
            "orders": 0,
            "observation_end": pd.Timestamp.now(),
        }
    od = pd.to_datetime(orders_df["order_date"])
    span_days = (od.max() - od.min()).days
    months = span_days / 30.0
    by_cust = orders_df.groupby("customer_id").size()
    repeat = int((by_cust >= 2).sum())
    orders = int(len(orders_df))
    return {
        "months": float(months),
        "repeat_customers": repeat,
        "orders": orders,
        "observation_end": od.max(),
    }


def _time_based_holdout_split(
    orders_df: pd.DataFrame,
    observation_end: pd.Timestamp,
    *,
    desired_window_days: float = 30.0,
) -> Tuple[pd.DataFrame, pd.DataFrame, float]:
    """Split orders into ``[t0, t_split]`` train and ``(t_split, t_end]`` holdout.

    The actual holdout window is ``min(desired_window_days,
    (observation_end - observation_start).days // 4)`` so that we never
    consume more than ~25% of the observed span as holdout (a safety
    floor for small fixtures where 30d would otherwise eat half the
    window). Returns ``(train_df, holdout_df, window_days)``.
    """

    if orders_df.empty:
        return orders_df.iloc[0:0].copy(), orders_df.iloc[0:0].copy(), 0.0

    od = pd.to_datetime(orders_df["order_date"])
    span_days = float((observation_end - od.min()).days)
    # Cap window to a quarter of the span (defensive — for tiny fixtures)
    # so we don't extrapolate past available data nor over-shrink train.
    window_days = float(min(desired_window_days, max(1.0, span_days / 4.0)))
    t_split = observation_end - pd.Timedelta(days=window_days)
    df = orders_df.copy()
    df["order_date"] = od
    train = df.loc[df["order_date"] <= t_split].copy()
    holdout = df.loc[df["order_date"] > t_split].copy()
    return train, holdout, window_days


def _compute_holdout_metrics(
    fitter: Any,
    train_summary: pd.DataFrame,
    holdout_orders: pd.DataFrame,
    *,
    horizon_days: float,
) -> Dict[str, Optional[float]]:
    """Compute the three holdout metrics (Spearman, agg_ratio, MAPE).

    Operational contract:
    - ``rank_spearman``: primary gating metric. Spearman rank
      correlation between per-customer predicted expected purchases
      over ``horizon_days`` (using train-fit params + train RFM) and
      observed purchase counts in the holdout window. ``None`` when
      observed has zero variance (rank correlation undefined).
    - ``agg_ratio``: ``sum(predicted) / max(sum(observed), 1.0)``.
      Operator-visible diagnostic; does NOT gate.
    - ``mape``: retained for operator-diagnostic continuity (DS-deprecated
      from gating 2026-05-26 — see module docstring). Computed as
      ``mean(|observed - predicted| / max(observed, 1.0))`` over the
      same per-customer vectors.

    All three metrics are computed on the SAME customer universe:
    customers present in train_summary (so we have train-fit RFM to
    predict with). Holdout-only customers are excluded by construction
    — they have no train-RFM to predict from.
    """

    out: Dict[str, Optional[float]] = {
        "rank_spearman": None,
        "agg_ratio": None,
        "mape": None,
    }

    if train_summary.empty:
        return out

    # Per-customer observed holdout order count.
    if holdout_orders.empty:
        observed = pd.Series(0, index=train_summary["customer_id"].values, dtype=float)
    else:
        observed_counts = holdout_orders.groupby("customer_id").size()
        observed = train_summary["customer_id"].map(observed_counts).fillna(0.0).astype(float)
        observed.index = train_summary["customer_id"].values

    try:
        predicted = fitter.conditional_expected_number_of_purchases_up_to_time(
            horizon_days,
            train_summary["frequency"],
            train_summary["recency"],
            train_summary["T"],
        )
    except Exception:  # noqa: BLE001 — operator diagnostic
        return out

    pred = np.asarray(predicted, dtype=float)
    obs = np.asarray(observed.values, dtype=float)

    if len(pred) == 0 or len(obs) == 0 or len(pred) != len(obs):
        return out

    # --- Spearman (primary gating) ---
    # Undefined if either side has zero variance (e.g., observed all zero,
    # or predicted constant). Surface as None → REFUSED at classifier.
    if np.nanstd(obs) == 0.0 or np.nanstd(pred) == 0.0:
        out["rank_spearman"] = None
    else:
        try:
            from scipy.stats import spearmanr  # type: ignore

            rho = spearmanr(pred, obs).correlation
            if rho is None or not np.isfinite(rho):
                out["rank_spearman"] = None
            else:
                out["rank_spearman"] = float(rho)
        except Exception:  # noqa: BLE001
            out["rank_spearman"] = None

    # --- Aggregate calibration ratio (diagnostic) ---
    sum_obs = float(np.nansum(obs))
    sum_pred = float(np.nansum(pred))
    out["agg_ratio"] = sum_pred / max(sum_obs, 1.0)

    # --- MAPE (deprecated; retained for diagnostic continuity) ---
    with np.errstate(divide="ignore", invalid="ignore"):
        denom = np.maximum(obs, 1.0)
        mape = float(np.mean(np.abs(obs - pred) / denom))
    if not np.isfinite(mape):
        out["mape"] = None
    else:
        out["mape"] = mape

    return out


def fit_bgnbd(
    orders_df: pd.DataFrame,
    profile: Any,
    *,
    store_id: str = "",
    data_dir: Optional[Path] = None,
    seed: int = 0,  # reserved for future stochastic paths; lifetimes is deterministic
    yaml_path: Optional[Path] = None,
) -> ModelCard:
    """Fit BG/NBD and return a typed ``ModelCard`` per the four-state
    ``ModelFitStatus`` vocabulary.

    ``orders_df`` schema: ``customer_id``, ``order_date``. Other columns
    are ignored.

    Flow:
    1. Resolve threshold dict via ``_load_model_fit_thresholds(profile)``.
    2. Compute data-depth counts (months / repeat / orders).
    3. If below PROVISIONAL floor → return ``INSUFFICIENT_DATA``
       ModelCard (no parquet, empty parameters; audit story: declined).
    4. Time-based holdout split (``t_split = t_end - window_days``).
       Build RFM summary on the train slice.
    5. Fit ``lifetimes.BetaGeoFitter`` on the train slice. If a
       ``ConvergenceWarning`` fires → ``REFUSED`` (no parquet; warning
       recorded).
    6. Compute holdout metrics (Spearman, agg_ratio, MAPE). Classify
       VALIDATED / PROVISIONAL / REFUSED on **Spearman** per the
       per-stage cell + relaxation floor.
    7. On {VALIDATED, PROVISIONAL}: write per-customer parquet to
       ``<data_dir>/<store_id>/predictive/bgnbd.parquet`` (when
       ``data_dir`` is provided; tests may skip write).

    Returns the ModelCard. The caller (S13 audience-builder) decides
    whether the fit status permits ranking consumption.
    """

    thresholds_full = _load_model_fit_thresholds(profile, yaml_path=yaml_path)
    bgnbd_thr = thresholds_full["bgnbd"]
    relax = thresholds_full["relaxation_factors"]

    months_floor = bgnbd_thr["months_data_validated"]
    repeat_floor = bgnbd_thr["repeat_customers_validated"]
    orders_floor = bgnbd_thr["orders_validated"]
    rank_validated = bgnbd_thr["holdout_rank_spearman_validated"]
    n_mult = relax["provisional_n_multiplier"]
    rank_provisional_floor = relax["provisional_rank_spearman_floor"]

    counts = _data_depth_counts(orders_df)
    months = counts["months"]
    repeat = counts["repeat_customers"]
    orders = counts["orders"]
    observation_end = counts["observation_end"]
    training_window_days = (
        int((observation_end - pd.to_datetime(orders_df["order_date"]).min()).days)
        if not orders_df.empty
        else 0
    )

    # ---- Step 3: cold-start floor → INSUFFICIENT_DATA ----------------------
    provisional_repeat_floor = n_mult * repeat_floor
    provisional_orders_floor = n_mult * orders_floor
    if (
        months < months_floor
        or repeat < provisional_repeat_floor
        or orders < provisional_orders_floor
    ):
        return ModelCard(
            model_name="bgnbd",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # ---- Step 4-5: time-based split + fit --------------------------------
    try:
        from lifetimes import BetaGeoFitter  # type: ignore
    except ImportError:
        # ``lifetimes`` not installed — engine declines to attempt fit.
        # Treat as REFUSED (we tried; the runtime is incapable) so the
        # operator alert surfaces. The flag-OFF default protects this
        # branch from running on installs that don't carry the dep.
        return ModelCard(
            model_name="bgnbd",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=["lifetimes_import_failed"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    train_orders, holdout_orders, window_days = _time_based_holdout_split(
        orders_df, observation_end, desired_window_days=30.0
    )

    # Re-build RFM summary against the TRAIN window. observation_end for
    # train-RFM purposes is t_split = observation_end - window_days.
    train_obs_end = observation_end - pd.Timedelta(days=window_days)
    train_summary = _build_rfm_summary(train_orders, train_obs_end)

    if train_summary.empty:
        return ModelCard(
            model_name="bgnbd",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=["empty_train_window_after_holdout_split"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    fit_warnings: list = []
    fitter: Any = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            fitter = BetaGeoFitter(penalizer_coef=0.01)
            fitter.fit(
                train_summary["frequency"],
                train_summary["recency"],
                train_summary["T"],
            )
        except Exception as exc:  # noqa: BLE001 — convergence failure surfaces here
            return ModelCard(
                model_name="bgnbd",
                fit_status=ModelFitStatus.REFUSED,
                fit_warnings=[f"fit_exception:{type(exc).__name__}"],
                parameters={},
                training_window_days=training_window_days,
                n_observed=repeat,
                metrics={},
                fit_timestamp=_now_iso(),
                parquet_schema_version=1,
            )
        for w in caught:
            name = type(w.message).__name__
            if "Convergence" in name or "ConvergenceWarning" in str(w.message):
                fit_warnings.append("convergence_warning")

    metrics = _compute_holdout_metrics(
        fitter, train_summary, holdout_orders, horizon_days=window_days
    )
    rank_spearman = metrics["rank_spearman"]
    agg_ratio = metrics["agg_ratio"]
    holdout_mape = metrics["mape"]

    # ---- Step 6: classify (Spearman-gated) -------------------------------
    # If a ConvergenceWarning fired → REFUSED regardless of metrics.
    if "convergence_warning" in fit_warnings:
        return ModelCard(
            model_name="bgnbd",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings,
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={
                "holdout_mape": holdout_mape,
                "holdout_rank_spearman": rank_spearman,
                "holdout_agg_ratio": agg_ratio,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # Spearman-based gating.
    if rank_spearman is None or not math.isfinite(rank_spearman):
        # No usable rank correlation (zero variance in observed counts,
        # or scipy missing). Cannot validate — REFUSED.
        return ModelCard(
            model_name="bgnbd",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + ["holdout_rank_spearman_unmeasurable"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={
                "holdout_mape": holdout_mape,
                "holdout_rank_spearman": rank_spearman,
                "holdout_agg_ratio": agg_ratio,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    if rank_spearman < rank_provisional_floor:
        return ModelCard(
            model_name="bgnbd",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + ["holdout_rank_spearman_below_floor"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={
                "holdout_mape": holdout_mape,
                "holdout_rank_spearman": rank_spearman,
                "holdout_agg_ratio": agg_ratio,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # VALIDATED: clears the unrelaxed floor AND Spearman at/above validated cutoff.
    is_validated = (
        repeat >= repeat_floor
        and orders >= orders_floor
        and rank_spearman >= rank_validated
        and not fit_warnings
    )
    status = ModelFitStatus.VALIDATED if is_validated else ModelFitStatus.PROVISIONAL

    parameters = {
        "r": float(getattr(fitter, "params_", {}).get("r", float("nan"))),
        "alpha": float(getattr(fitter, "params_", {}).get("alpha", float("nan"))),
        "a": float(getattr(fitter, "params_", {}).get("a", float("nan"))),
        "b": float(getattr(fitter, "params_", {}).get("b", float("nan"))),
    }

    card = ModelCard(
        model_name="bgnbd",
        fit_status=status,
        fit_warnings=fit_warnings,
        parameters=parameters,
        training_window_days=training_window_days,
        n_observed=repeat,
        metrics={
            "holdout_mape": holdout_mape,
            "holdout_rank_spearman": rank_spearman,
            "holdout_agg_ratio": agg_ratio,
        },
        fit_timestamp=_now_iso(),
        parquet_schema_version=1,
    )

    # ---- Step 7: write parquet (VALIDATED / PROVISIONAL only) -------------
    if data_dir is not None and store_id:
        # For parquet write, re-build RFM on the FULL window so per-customer
        # predictions reflect the operator's latest state, not the train slice.
        full_summary = _build_rfm_summary(orders_df, observation_end)
        _write_parquet(full_summary, fitter, data_dir=Path(data_dir), store_id=store_id)

    return card


def _write_parquet(
    summary: pd.DataFrame,
    fitter: Any,
    *,
    data_dir: Path,
    store_id: str,
) -> Path:
    """Write per-customer ``p_alive`` + expected purchases to parquet.

    Schema (parquet_schema_version=1):
    - ``customer_id``: str
    - ``p_alive``: float [0,1]
    - ``expected_purchases_30d``: float >=0
    - ``expected_purchases_180d``: float >=0
    - ``parquet_schema_version``: int (constant 1)
    """

    p_alive = fitter.conditional_probability_alive(
        summary["frequency"], summary["recency"], summary["T"]
    )
    exp_30 = fitter.conditional_expected_number_of_purchases_up_to_time(
        30.0, summary["frequency"], summary["recency"], summary["T"]
    )
    exp_180 = fitter.conditional_expected_number_of_purchases_up_to_time(
        180.0, summary["frequency"], summary["recency"], summary["T"]
    )
    out = pd.DataFrame({
        "customer_id": summary["customer_id"].astype(str),
        "p_alive": np.asarray(p_alive, dtype=float),
        "expected_purchases_30d": np.asarray(exp_30, dtype=float),
        "expected_purchases_180d": np.asarray(exp_180, dtype=float),
        "parquet_schema_version": 1,
    })
    out_dir = data_dir / store_id / "predictive"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "bgnbd.parquet"
    out.to_parquet(target, index=False)
    return target


__all__ = ["fit_bgnbd"]
