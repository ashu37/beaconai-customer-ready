"""Gamma-Gamma fit (Sprint 10 — T2).

Mirrors the ``src/predictive/bgnbd.py`` module shape for the
Fader-Hardie-Lee Gamma-Gamma per-customer monetary-value model via the
``lifetimes`` package (``GammaGammaFitter``). Produces a typed
``ModelCard`` under the four-state ``ModelFitStatus`` vocabulary
documented in ``src/predictive/model_card.py``.

S10-T2 ship constraints:

- Flag-OFF land. Behind ``ENGINE_V2_ML_GAMMA_GAMMA`` (default OFF).
- No PlayCard consumes the fit output. Surfaces only on
  ``engine_run.predictive_models["gamma_gamma"]`` when the flag is ON
  (T2.5 atomic flip wires it; T2 is module + schema only).
- Parquet per-customer artifact at
  ``data/<store_id>/predictive/gamma_gamma.parquet`` is written **only
  when fit_status in {VALIDATED, PROVISIONAL}**. INSUFFICIENT_DATA /
  REFUSED produce a ModelCard with no parquet artifact (privacy
  posture, D-3 deletion semantics).
- ``lifetimes`` is imported lazily inside ``fit_gamma_gamma`` so the
  module imports without the dep present (tests for chained-refusal /
  INSUFFICIENT_DATA do not need ``lifetimes``).

DS-locked validation metric (sign-off 2026-05-26)
=================================================

PRIMARY gate: **Spearman rank correlation** between predicted
per-customer monetary value and observed holdout-window spend. Same
time-based holdout shape as the T1.4 BG/NBD swap.

SECONDARY diagnostics on the ModelCard (NOT gating):

- ``holdout_agg_ratio``: ``sum(predicted_spend) /
  max(sum(observed_holdout_spend), 1)`` — calibration sanity check.
- Pearson-r on ``(frequency, monetary)`` per customer — the
  Gamma-Gamma INDEPENDENCE ASSUMPTION test. Surfaced as
  ``fit_warnings=["gg_independence_violated"]`` if ``|r| > 0.10``, but
  does NOT use as primary gate (advisory cutoff, per
  ``src/predictive/model_card.py`` docstring).
- ``holdout_mape`` retained on the ModelCard for diagnostic
  continuity (parallel to BG/NBD T1.4); does NOT gate.

Chained refusal (IM plan §C.2): if the same engine_run's BG/NBD
ModelCard is ``REFUSED`` or ``INSUFFICIENT_DATA``, Gamma-Gamma
short-circuits to ``REFUSED`` with ``fit_warnings=["chained_bgnbd_refusal"]``.
Rationale: we cannot rank per-customer monetary value if we cannot
rank customer aliveness at all.

Thresholds: KI-NEW-Q-territory (speculative-until-S14, parallel to
KI-NEW-P-v2 for BG/NBD Spearman). The same value across stages is
acceptable — kept stage-keyed for forward-compat.
"""

from __future__ import annotations

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


def _build_monetary_summary(
    orders_df: pd.DataFrame, observation_end: pd.Timestamp
) -> pd.DataFrame:
    """Aggregate ``orders_df`` into the Gamma-Gamma RFM-M summary frame.

    Expected ``orders_df`` schema (subset is sufficient):

    - ``customer_id``: str
    - ``order_date``: datetime64[ns]
    - ``order_value``: float (per-order monetary value, > 0)

    Returns one row per customer with columns ``frequency`` (repeat
    purchases), ``monetary_value`` (mean order value across the
    customer's repeat orders — the Gamma-Gamma convention; the first
    order is excluded to mirror the BG/NBD ``frequency`` definition),
    ``T`` (days between first purchase and observation_end), and
    ``recency`` (days between first and last purchase).
    """

    if orders_df.empty:
        return pd.DataFrame(
            columns=["customer_id", "frequency", "recency", "T", "monetary_value"]
        )

    df = orders_df[["customer_id", "order_date", "order_value"]].copy()
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["order_value"] = pd.to_numeric(df["order_value"], errors="coerce")
    df = df.dropna(subset=["order_value"])
    df = df.loc[df["order_value"] > 0].copy()

    # First-order date per customer (to exclude from the monetary mean
    # under the Gamma-Gamma convention).
    grouped = df.groupby("customer_id")
    first_order = grouped["order_date"].transform("min")
    df["is_repeat"] = df["order_date"] > first_order

    agg = grouped.agg(
        first=("order_date", "min"),
        last=("order_date", "max"),
        n_orders=("order_date", "count"),
    ).reset_index()
    agg["frequency"] = agg["n_orders"] - 1
    agg["recency"] = (agg["last"] - agg["first"]).dt.days.astype(float)
    agg["T"] = (observation_end - agg["first"]).dt.days.astype(float)

    repeats = df.loc[df["is_repeat"]]
    if repeats.empty:
        agg["monetary_value"] = 0.0
    else:
        monetary = repeats.groupby("customer_id")["order_value"].mean()
        agg["monetary_value"] = (
            agg["customer_id"].map(monetary).fillna(0.0).astype(float)
        )

    return agg[
        ["customer_id", "frequency", "recency", "T", "monetary_value"]
    ]


def _repeat_with_monetary_count(orders_df: pd.DataFrame) -> int:
    """Count customers with >=2 monetary observations (per IM §C.4).

    A customer qualifies for Gamma-Gamma fit when they have at least
    two positive-value orders — the first is excluded under the
    Gamma-Gamma convention; the remaining orders supply the
    per-customer monetary mean.
    """

    if orders_df.empty or "order_value" not in orders_df.columns:
        return 0
    df = orders_df[["customer_id", "order_value"]].copy()
    df["order_value"] = pd.to_numeric(df["order_value"], errors="coerce")
    df = df.dropna(subset=["order_value"])
    df = df.loc[df["order_value"] > 0]
    if df.empty:
        return 0
    counts = df.groupby("customer_id").size()
    # Need ≥ 2 positive-value orders → ≥ 1 repeat with monetary signal.
    # IM §C.4 requires ≥ 2 monetary observations (i.e. ≥ 2 positive orders).
    return int((counts >= 2).sum())


def _time_based_holdout_split(
    orders_df: pd.DataFrame,
    observation_end: pd.Timestamp,
    *,
    desired_window_days: float = 30.0,
) -> Tuple[pd.DataFrame, pd.DataFrame, float]:
    """Split orders into ``[t0, t_split]`` train and ``(t_split, t_end]`` holdout.

    Mirrors ``src/predictive/bgnbd.py::_time_based_holdout_split``. The
    actual window is ``min(desired_window_days, span_days // 4)`` so we
    never consume more than ~25% of the observed span as holdout.
    """

    if orders_df.empty:
        return orders_df.iloc[0:0].copy(), orders_df.iloc[0:0].copy(), 0.0

    od = pd.to_datetime(orders_df["order_date"])
    span_days = float((observation_end - od.min()).days)
    window_days = float(min(desired_window_days, max(1.0, span_days / 4.0)))
    t_split = observation_end - pd.Timedelta(days=window_days)
    df = orders_df.copy()
    df["order_date"] = od
    train = df.loc[df["order_date"] <= t_split].copy()
    holdout = df.loc[df["order_date"] > t_split].copy()
    return train, holdout, window_days


def _pearson_r_freq_monetary(summary: pd.DataFrame) -> Optional[float]:
    """Pearson correlation between (frequency, monetary_value).

    Returns ``None`` when undefined (zero variance on either side, or
    fewer than 2 customers). Public helper for direct unit-testing of
    the Gamma-Gamma independence-assumption check.
    """

    if summary.empty or len(summary) < 2:
        return None
    freq = np.asarray(summary["frequency"], dtype=float)
    mon = np.asarray(summary["monetary_value"], dtype=float)
    if np.nanstd(freq) == 0.0 or np.nanstd(mon) == 0.0:
        return None
    try:
        r = float(np.corrcoef(freq, mon)[0, 1])
    except Exception:  # noqa: BLE001 — diagnostic
        return None
    if not np.isfinite(r):
        return None
    return r


def _compute_holdout_metrics(
    fitter: Any,
    train_summary: pd.DataFrame,
    holdout_orders: pd.DataFrame,
    *,
    window_days: float,
    train_span_days: float,
    bgnbd_params: Optional[Dict[str, float]] = None,
) -> Dict[str, Optional[float]]:
    """Compute the three Gamma-Gamma holdout metrics.

    - ``rank_spearman``: PRIMARY gating metric — Spearman rank
      correlation between per-customer predicted conditional expected
      average profit (Gamma-Gamma posterior mean) and observed mean
      per-order spend in the holdout window.
    - ``agg_ratio``: window-aligned aggregate calibration ratio,
      ``sum(predicted_holdout_total_spend) /
      max(sum(observed_holdout_spend), 1.0)``. The predicted holdout
      total is ``pred_per_order_spend * predicted_holdout_purchases``,
      where ``predicted_holdout_purchases`` is obtained from the
      provided BG/NBD parameters via
      ``conditional_expected_number_of_purchases_up_to_time(window_days,
      freq, recency, T)`` (DS-required, 2026-05-26). If BG/NBD params
      are not usable, falls back to the per-day-rate proxy
      ``train_freq * (window_days / train_span_days)``. Diagnostic only
      — does NOT gate.
    - ``mape``: retained for diagnostic continuity (parallel to BG/NBD
      T1.4); does NOT gate.

    Customer universe = train_summary (we have train-fit RFM-M to
    predict from). Holdout-only customers are excluded by construction.

    Returns ``out["holdout_empty"]`` as ``1.0`` (truthy sentinel) when
    holdout_orders is empty / has no positive monetary observations
    against the train customer universe — surfaced as a fit_warning by
    the caller so a misleading ``agg_ratio`` doesn't drive a band-gate
    REFUSAL without an audit trail.
    """

    out: Dict[str, Optional[float]] = {
        "rank_spearman": None,
        "agg_ratio": None,
        "mape": None,
        "holdout_empty": None,
    }

    if train_summary.empty:
        return out

    # --- Per-customer observed holdout mean order value + total spend ---
    if holdout_orders.empty:
        observed_mean = pd.Series(
            0.0, index=train_summary["customer_id"].values, dtype=float
        )
        observed_total = pd.Series(
            0.0, index=train_summary["customer_id"].values, dtype=float
        )
        out["holdout_empty"] = 1.0
    else:
        ho = holdout_orders.copy()
        ho["order_value"] = pd.to_numeric(ho["order_value"], errors="coerce")
        ho = ho.dropna(subset=["order_value"])
        means = ho.groupby("customer_id")["order_value"].mean()
        totals = ho.groupby("customer_id")["order_value"].sum()
        observed_mean = (
            train_summary["customer_id"].map(means).fillna(0.0).astype(float)
        )
        observed_total = (
            train_summary["customer_id"].map(totals).fillna(0.0).astype(float)
        )
        observed_mean.index = train_summary["customer_id"].values
        observed_total.index = train_summary["customer_id"].values

    # --- Per-customer predicted conditional expected average profit ---
    try:
        predicted = fitter.conditional_expected_average_profit(
            train_summary["frequency"],
            train_summary["monetary_value"],
        )
    except Exception:  # noqa: BLE001 — diagnostic
        return out

    pred = np.asarray(predicted, dtype=float)
    obs_mean = np.asarray(observed_mean.values, dtype=float)
    obs_total = np.asarray(observed_total.values, dtype=float)

    if len(pred) == 0 or len(obs_mean) == 0 or len(pred) != len(obs_mean):
        return out

    # --- Spearman (primary gating) ---
    if np.nanstd(obs_mean) == 0.0 or np.nanstd(pred) == 0.0:
        out["rank_spearman"] = None
    else:
        try:
            from scipy.stats import spearmanr  # type: ignore

            rho = spearmanr(pred, obs_mean).correlation
            if rho is None or not np.isfinite(rho):
                out["rank_spearman"] = None
            else:
                out["rank_spearman"] = float(rho)
        except Exception:  # noqa: BLE001
            out["rank_spearman"] = None

    # --- Aggregate calibration ratio (diagnostic, window-aligned) ---
    # DS-required (2026-05-26): predicted total must be window-aligned
    # to the holdout window. Predicted per-order spend × predicted
    # number of purchases in the holdout window per customer.
    #
    # Preferred path: BG/NBD-card-conditioned conditional expected
    # purchases over ``window_days``, using the BG/NBD ModelCard
    # parameters from the chained-refusal input. Mirrors how T1.4's
    # BG/NBD holdout metric is computed.
    #
    # Fallback proxy: per-day-rate ``train_freq * (window_days /
    # train_span_days)`` — used only when BG/NBD params are absent or
    # the BG/NBD-conditioned predictor raises.
    train_freq = np.asarray(train_summary["frequency"], dtype=float)
    pred_purchases_holdout: Optional[np.ndarray] = None
    if (
        bgnbd_params is not None
        and all(
            k in bgnbd_params and np.isfinite(bgnbd_params[k])
            for k in ("r", "alpha", "a", "b")
        )
    ):
        try:
            from lifetimes import BetaGeoFitter  # type: ignore

            bg = BetaGeoFitter(penalizer_coef=0.0)
            bg.params_ = pd.Series(
                {
                    "r": float(bgnbd_params["r"]),
                    "alpha": float(bgnbd_params["alpha"]),
                    "a": float(bgnbd_params["a"]),
                    "b": float(bgnbd_params["b"]),
                }
            )
            pp = bg.conditional_expected_number_of_purchases_up_to_time(
                float(window_days),
                train_summary["frequency"],
                train_summary["recency"],
                train_summary["T"],
            )
            arr = np.asarray(pp, dtype=float)
            if arr.shape == train_freq.shape and np.all(np.isfinite(arr)):
                pred_purchases_holdout = arr
        except Exception:  # noqa: BLE001 — fall through to proxy
            pred_purchases_holdout = None

    if pred_purchases_holdout is None:
        # Per-day-rate proxy (DS-approved fallback).
        rate = (
            float(window_days) / float(train_span_days)
            if train_span_days and train_span_days > 0.0
            else 0.0
        )
        pred_purchases_holdout = train_freq * rate

    pred_total_holdout = pred * pred_purchases_holdout
    sum_obs_total = float(np.nansum(obs_total))
    sum_pred_total = float(np.nansum(pred_total_holdout))

    if sum_obs_total <= 0.0:
        # No positive observed holdout spend against the train universe.
        # Surface explicitly rather than dividing by max(_,1) and quoting
        # a meaningless large ratio. agg_ratio stays None; caller adds
        # a holdout_empty warning and gates accordingly.
        out["holdout_empty"] = 1.0
        out["agg_ratio"] = None
    else:
        out["agg_ratio"] = sum_pred_total / sum_obs_total

    # --- MAPE (diagnostic; not gating) ---
    with np.errstate(divide="ignore", invalid="ignore"):
        denom = np.maximum(obs_mean, 1.0)
        mape = float(np.mean(np.abs(obs_mean - pred) / denom))
    if not np.isfinite(mape):
        out["mape"] = None
    else:
        out["mape"] = mape

    return out


def fit_gamma_gamma(
    orders_df: pd.DataFrame,
    profile: Any,
    bgnbd_model_card: Optional[ModelCard] = None,
    *,
    store_id: str = "",
    data_dir: Optional[Path] = None,
    seed: int = 0,  # reserved; GammaGammaFitter is deterministic
    yaml_path: Optional[Path] = None,
) -> ModelCard:
    """Fit Gamma-Gamma and return a typed ``ModelCard``.

    ``orders_df`` schema: ``customer_id``, ``order_date``,
    ``order_value``. Other columns are ignored.

    Flow:

    1. **Chained-refusal short-circuit.** If ``bgnbd_model_card`` is
       ``REFUSED`` or ``INSUFFICIENT_DATA``, return ``REFUSED`` with
       ``chained_bgnbd_refusal`` warning. No fit attempted. No parquet.
    2. **INSUFFICIENT_DATA gate.** If fewer than the configured floor
       (``repeat_customers_validated``, default 50) customers have ≥ 2
       monetary observations → ``INSUFFICIENT_DATA``. No fit. No parquet.
    3. **Independence check.** Pearson-r on (frequency, monetary) per
       customer. If ``|r| > pearson_r_violation_threshold`` (default
       0.10), add ``gg_independence_violated`` to ``fit_warnings``.
       Continue (advisory, not gating).
    4. **Time-based holdout split** (``window_days = min(30,
       span/4)``). Re-build the RFM-M summary on the train slice.
    5. **Fit** ``lifetimes.GammaGammaFitter`` on the train slice
       (frequency, monetary_value). Catch convergence warnings + fit
       exceptions → ``REFUSED``.
    6. **Compute holdout metrics** (Spearman, agg_ratio, MAPE).
    7. **Classify** per DS thresholds:
       - VALIDATED: Spearman ≥ ``holdout_rank_spearman_validated``
         (0.20) AND ``agg_ratio_min ≤ agg_ratio ≤ agg_ratio_max``
         ([0.5, 1.5]) AND independence not flagged AND no warnings.
       - REFUSED: Spearman < ``provisional_rank_spearman_floor`` (0.10)
         OR ``agg_ratio`` outside [0.4, 1.6].
       - PROVISIONAL: otherwise.
    8. **Parquet write** for {VALIDATED, PROVISIONAL} only.

    Returns the ModelCard.
    """

    thresholds_full = _load_model_fit_thresholds(profile, yaml_path=yaml_path)
    gg_thr = thresholds_full["gamma_gamma"]
    relax_gg = thresholds_full["gamma_gamma_relaxation_factors"]
    indep = thresholds_full["gamma_gamma_independence_check"]

    repeat_floor = gg_thr["repeat_customers_validated"]
    rank_validated = gg_thr["holdout_rank_spearman_validated"]
    agg_min_validated = gg_thr["agg_ratio_min"]
    agg_max_validated = gg_thr["agg_ratio_max"]
    rank_floor = relax_gg["provisional_rank_spearman_floor"]
    agg_min_provisional = relax_gg["provisional_agg_ratio_min"]
    agg_max_provisional = relax_gg["provisional_agg_ratio_max"]
    independence_threshold = indep["pearson_r_violation_threshold"]

    # Default training window (overwritten below once observation_end resolved).
    training_window_days = 0
    if not orders_df.empty and "order_date" in orders_df.columns:
        od = pd.to_datetime(orders_df["order_date"])
        if not od.empty:
            training_window_days = int((od.max() - od.min()).days)

    # ---- Step 1: chained-refusal short-circuit -----------------------------
    if bgnbd_model_card is not None and bgnbd_model_card.fit_status in (
        ModelFitStatus.REFUSED,
        ModelFitStatus.INSUFFICIENT_DATA,
    ):
        return ModelCard(
            model_name="gamma_gamma",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=["chained_bgnbd_refusal"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=0,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # ---- Step 2: INSUFFICIENT_DATA gate -----------------------------------
    repeat_with_monetary = _repeat_with_monetary_count(orders_df)
    if repeat_with_monetary < int(repeat_floor):
        return ModelCard(
            model_name="gamma_gamma",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat_with_monetary,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # ---- Step 4: time-based split + train summary ------------------------
    od = pd.to_datetime(orders_df["order_date"])
    observation_end = od.max()
    train_orders, holdout_orders, window_days = _time_based_holdout_split(
        orders_df, observation_end, desired_window_days=30.0
    )
    train_obs_end = observation_end - pd.Timedelta(days=window_days)
    full_summary = _build_monetary_summary(orders_df, observation_end)
    train_summary = _build_monetary_summary(train_orders, train_obs_end)

    # Gamma-Gamma is fit on customers with frequency ≥ 1 and positive
    # monetary_value. Filter the train summary accordingly.
    fit_frame = train_summary.loc[
        (train_summary["frequency"] >= 1)
        & (train_summary["monetary_value"] > 0)
    ].copy()

    if fit_frame.empty:
        return ModelCard(
            model_name="gamma_gamma",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=["empty_train_window_after_holdout_split"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat_with_monetary,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # ---- Step 3: independence check (advisory) ----------------------------
    fit_warnings: list = []
    pearson_r = _pearson_r_freq_monetary(fit_frame)
    if pearson_r is not None and abs(pearson_r) > float(independence_threshold):
        fit_warnings.append("gg_independence_violated")

    # ---- Step 5: fit GammaGammaFitter -------------------------------------
    try:
        from lifetimes import GammaGammaFitter  # type: ignore
    except ImportError:
        return ModelCard(
            model_name="gamma_gamma",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + ["lifetimes_import_failed"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat_with_monetary,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    fitter: Any = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            fitter = GammaGammaFitter(penalizer_coef=0.01)
            fitter.fit(
                fit_frame["frequency"],
                fit_frame["monetary_value"],
            )
        except Exception as exc:  # noqa: BLE001 — convergence failure surfaces here
            return ModelCard(
                model_name="gamma_gamma",
                fit_status=ModelFitStatus.REFUSED,
                fit_warnings=fit_warnings + [f"fit_exception:{type(exc).__name__}"],
                parameters={},
                training_window_days=training_window_days,
                n_observed=repeat_with_monetary,
                metrics={},
                fit_timestamp=_now_iso(),
                parquet_schema_version=1,
            )
        for w in caught:
            name = type(w.message).__name__
            if "Convergence" in name or "ConvergenceWarning" in str(w.message):
                fit_warnings.append("convergence_warning")

    # ---- Step 6: holdout metrics -------------------------------------------
    # Derive the train-window span for the per-day-rate fallback proxy.
    if not train_orders.empty:
        tod = pd.to_datetime(train_orders["order_date"])
        train_span_days = float((tod.max() - tod.min()).days)
    else:
        train_span_days = 0.0

    bgnbd_params: Optional[Dict[str, float]] = None
    if bgnbd_model_card is not None and isinstance(
        getattr(bgnbd_model_card, "parameters", None), dict
    ):
        bgnbd_params = {
            k: float(v)
            for k, v in bgnbd_model_card.parameters.items()
            if isinstance(v, (int, float))
            and np.isfinite(float(v))
        }

    metrics = _compute_holdout_metrics(
        fitter,
        fit_frame,
        holdout_orders,
        window_days=float(window_days),
        train_span_days=train_span_days,
        bgnbd_params=bgnbd_params,
    )
    rank_spearman = metrics["rank_spearman"]
    agg_ratio = metrics["agg_ratio"]
    holdout_mape = metrics["mape"]
    if metrics.get("holdout_empty"):
        fit_warnings.append("holdout_empty")

    # ---- Step 7: classify ---------------------------------------------------
    if "convergence_warning" in fit_warnings:
        return ModelCard(
            model_name="gamma_gamma",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings,
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat_with_monetary,
            metrics={
                "holdout_mape": holdout_mape,
                "holdout_rank_spearman": rank_spearman,
                "holdout_agg_ratio": agg_ratio,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    if "holdout_empty" in fit_warnings:
        return ModelCard(
            model_name="gamma_gamma",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings,
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat_with_monetary,
            metrics={
                "holdout_mape": holdout_mape,
                "holdout_rank_spearman": rank_spearman,
                "holdout_agg_ratio": agg_ratio,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    if rank_spearman is None or not math.isfinite(rank_spearman):
        return ModelCard(
            model_name="gamma_gamma",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + ["holdout_rank_spearman_unmeasurable"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat_with_monetary,
            metrics={
                "holdout_mape": holdout_mape,
                "holdout_rank_spearman": rank_spearman,
                "holdout_agg_ratio": agg_ratio,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # Out-of-band on EITHER axis → REFUSED.
    if rank_spearman < float(rank_floor):
        return ModelCard(
            model_name="gamma_gamma",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + ["holdout_rank_spearman_below_floor"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat_with_monetary,
            metrics={
                "holdout_mape": holdout_mape,
                "holdout_rank_spearman": rank_spearman,
                "holdout_agg_ratio": agg_ratio,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    if agg_ratio is None or agg_ratio < float(agg_min_provisional) or agg_ratio > float(agg_max_provisional):
        return ModelCard(
            model_name="gamma_gamma",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + ["holdout_agg_ratio_out_of_band"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat_with_monetary,
            metrics={
                "holdout_mape": holdout_mape,
                "holdout_rank_spearman": rank_spearman,
                "holdout_agg_ratio": agg_ratio,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # VALIDATED requires: Spearman at/above the validated cutoff, agg_ratio
    # inside the validated band, independence not flagged, no other warnings.
    is_validated = (
        rank_spearman >= float(rank_validated)
        and agg_ratio is not None
        and float(agg_min_validated) <= agg_ratio <= float(agg_max_validated)
        and "gg_independence_violated" not in fit_warnings
        and not fit_warnings
    )
    status = ModelFitStatus.VALIDATED if is_validated else ModelFitStatus.PROVISIONAL

    parameters = {
        "p": float(getattr(fitter, "params_", {}).get("p", float("nan"))),
        "q": float(getattr(fitter, "params_", {}).get("q", float("nan"))),
        "v": float(getattr(fitter, "params_", {}).get("v", float("nan"))),
    }

    card = ModelCard(
        model_name="gamma_gamma",
        fit_status=status,
        fit_warnings=fit_warnings,
        parameters=parameters,
        training_window_days=training_window_days,
        n_observed=repeat_with_monetary,
        metrics={
            "holdout_mape": holdout_mape,
            "holdout_rank_spearman": rank_spearman,
            "holdout_agg_ratio": agg_ratio,
        },
        fit_timestamp=_now_iso(),
        parquet_schema_version=1,
    )

    # ---- Step 8: parquet write (VALIDATED / PROVISIONAL only) --------------
    if data_dir is not None and store_id:
        full_eligible = full_summary.loc[
            (full_summary["frequency"] >= 1)
            & (full_summary["monetary_value"] > 0)
        ].copy()
        if not full_eligible.empty:
            _write_parquet(
                full_eligible, fitter, data_dir=Path(data_dir), store_id=store_id
            )

    return card


def _write_parquet(
    summary: pd.DataFrame,
    fitter: Any,
    *,
    data_dir: Path,
    store_id: str,
) -> Path:
    """Write per-customer expected average spend to parquet.

    Schema (parquet_schema_version=1):

    - ``customer_id``: str
    - ``expected_avg_spend``: float >= 0 (Gamma-Gamma posterior mean
      per-order spend)
    - ``parquet_schema_version``: int (constant 1)
    """

    exp_spend = fitter.conditional_expected_average_profit(
        summary["frequency"], summary["monetary_value"]
    )
    out = pd.DataFrame({
        "customer_id": summary["customer_id"].astype(str),
        "expected_avg_spend": np.asarray(exp_spend, dtype=float),
        "parquet_schema_version": 1,
    })
    out_dir = data_dir / store_id / "predictive"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "gamma_gamma.parquet"
    out.to_parquet(target, index=False)
    return target


__all__ = ["fit_gamma_gamma", "_pearson_r_freq_monetary"]
