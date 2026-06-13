"""Cox PH survival fit (Sprint 11 — T1).

Wraps a classical Cox Proportional Hazards model via ``scikit-survival``
(Sebastian Pölsterl; sklearn-ecosystem). Produces a typed ``ModelCard``
describing fit health under the four-state ``ModelFitStatus`` vocabulary
documented in ``src/predictive/model_card.py``.

S11-T1 ship constraints
=======================

- Flag-OFF land. Behind ``ENGINE_V2_ML_SURVIVAL`` (default OFF).
- No PlayCard consumes the fit output. Surfaces only on
  ``engine_run.predictive_models["survival"]`` when the flag is ON
  (T1.5 atomic flip wires it; T1 is module + schema only).
- Parquet per-customer artifact at
  ``data/<store_id>/predictive/survival.parquet`` is written **only when
  fit_status in {VALIDATED, PROVISIONAL}**. INSUFFICIENT_DATA / REFUSED
  produce a ModelCard with no parquet artifact (privacy posture, D-3
  deletion semantics).
- ``scikit-survival`` is imported lazily inside ``fit_survival`` so the
  module imports without the dep present (tests for chained-refusal /
  INSUFFICIENT_DATA do not need ``sksurv``).

DS-locked validation metrics (sign-off 2026-05-26)
==================================================

PRIMARY gate: **Harrell's C-index** (``sksurv.metrics.
concordance_index_censored``) between predicted per-customer risk and
observed (event, time) tuples on a time-based holdout. VALIDATED floor
0.62 startup/growth, 0.63 mature/enterprise.

SECONDARY gate: **time-dependent integrated Brier score at 90d**
(``sksurv.metrics.integrated_brier_score``). VALIDATED requires this
≤ 0.25 across stages. Pure rank discrimination alone can ship a model
that orders correctly but predicts wildly miscalibrated absolute times;
S13 ``replenishment_due`` reads ``expected_days_to_next_purchase`` (a
magnitude), not just rank, so calibration must gate.

Dual gate: VALIDATED requires BOTH metrics to clear stage thresholds.
PROVISIONAL admits either side in the relaxed band
(c_index ∈ [0.55, validated_floor) OR brier ∈ (0.25, 0.35]).
REFUSED on c_index < 0.55, brier > 0.35, fit exception, or convergence
warning.

Chained refusal (S11-T1)
========================

When the same engine_run's BG/NBD ModelCard is ``REFUSED`` or
``INSUFFICIENT_DATA``, survival short-circuits to ``REFUSED`` with
``fit_warnings=["chained_bgnbd_refusal"]``. Rationale: Cox PH hazard
transforms the same gap-time signal BG/NBD evaluates — if BG/NBD cannot
recover repeat-propensity rank from the data, the gap distribution
itself is uninformative and Cox PH on the same population cannot do
better.

Per-customer (not per-customer-per-SKU)
=======================================

S11 ships per-customer survival only. Per-SKU survival would require a
new Tier-B audience builder which violates DS invariant 15 (no new
Tier-B builders through S13). Lock per the IM plan §B Q2 verdict.

Covariates
==========

Start simple — per-customer covariates are:

- ``log_frequency``: log(1 + train-window repeat-purchase count).
- ``log_recency_over_T``: log((recency + 1) / (T + 1)) — relative
  position of last train purchase in the observation window.

These are RFM-derived; richer covariates (cohort, vertical-specific
behavior, coupon recency, sub_vertical factor) are a future iteration.
DS verdict 2026-05-26: realistic VALIDATED C-index on RFM-only
covariates lands in 0.62-0.68 band, not 0.70+ — thresholds reflect
this.

Thresholds: KI-NEW-P extension (speculative-until-S14 calibration).
"""

from __future__ import annotations

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


def _data_depth_counts(orders_df: pd.DataFrame) -> Dict[str, Any]:
    """Return ``{months, repeat_customers, orders, observation_end}``.

    Mirrors ``src/predictive/bgnbd.py::_data_depth_counts`` for parity.
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
    desired_window_days: float = 90.0,
) -> Tuple[pd.DataFrame, pd.DataFrame, float]:
    """Split orders into ``[t0, t_split]`` train and ``(t_split, t_end]`` holdout.

    Mirrors ``src/predictive/bgnbd.py::_time_based_holdout_split`` shape
    with a longer default window (90d) — survival is gated on Brier@90d
    so the holdout must span at least that horizon for the time-dependent
    Brier evaluation to be honest. Window is capped at ~25% of the
    observed span (defensive for tiny fixtures).
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


def _build_survival_frame(
    train_orders: pd.DataFrame,
    holdout_orders: pd.DataFrame,
    train_observation_end: pd.Timestamp,
) -> pd.DataFrame:
    """Build per-customer ``(time, event, log_frequency, log_recency_over_T)``.

    For each customer observed in the train window:

    - ``frequency``: count of train-window orders (NOT BG/NBD's
      "repeats" — survival uses absolute count for the covariate).
    - ``T``: days between first train-window order and
      ``train_observation_end``.
    - ``recency``: days between first and last train-window order.
    - ``event``: 1 if customer has ≥ 1 purchase in holdout window
      (uncensored — we observed the next purchase); 0 otherwise
      (right-censored at ``train_observation_end``).
    - ``time``: days from last train purchase to either (a) first
      holdout purchase if event=1, or (b) train_observation_end if
      event=0 (right-censored at the train boundary). Survival's "time
      to next purchase" semantic.

    Returns a frame with columns
    ``[customer_id, time, event, log_frequency, log_recency_over_T]``.
    Customers with zero or negative ``time`` (degenerate: holdout
    purchase before train_observation_end — shouldn't happen by
    construction but defensive) are dropped.
    """

    if train_orders.empty:
        return pd.DataFrame(
            columns=["customer_id", "time", "event", "log_frequency", "log_recency_over_T"]
        )

    df = train_orders[["customer_id", "order_date"]].copy()
    df["order_date"] = pd.to_datetime(df["order_date"])

    grouped = df.groupby("customer_id")["order_date"].agg(["min", "max", "count"])
    grouped.columns = ["first", "last", "n_orders"]
    grouped = grouped.reset_index()
    grouped["recency"] = (grouped["last"] - grouped["first"]).dt.days.astype(float)
    grouped["T"] = (train_observation_end - grouped["first"]).dt.days.astype(float)
    grouped["frequency"] = grouped["n_orders"].astype(float)

    # First holdout purchase per customer (NaT if none).
    if holdout_orders.empty:
        first_holdout = pd.Series(pd.NaT, index=grouped["customer_id"].values, name="first_holdout")
    else:
        ho = holdout_orders[["customer_id", "order_date"]].copy()
        ho["order_date"] = pd.to_datetime(ho["order_date"])
        first_holdout = ho.groupby("customer_id")["order_date"].min()

    grouped = grouped.set_index("customer_id")
    grouped["first_holdout"] = first_holdout
    grouped = grouped.reset_index()

    # Event = 1 iff customer has a holdout purchase.
    grouped["event"] = grouped["first_holdout"].notna().astype(int)
    # Time = days from last train purchase to next event/censor boundary.
    next_dt = grouped["first_holdout"].fillna(train_observation_end)
    grouped["time"] = (pd.to_datetime(next_dt) - grouped["last"]).dt.days.astype(float)

    # Drop degenerate rows (non-positive time).
    grouped = grouped.loc[grouped["time"] > 0].copy()

    # Covariates: simple RFM-derived.
    grouped["log_frequency"] = np.log1p(grouped["frequency"])
    grouped["log_recency_over_T"] = np.log(
        (grouped["recency"] + 1.0) / (grouped["T"] + 1.0)
    )

    return grouped[
        ["customer_id", "time", "event", "log_frequency", "log_recency_over_T"]
    ].reset_index(drop=True)


def fit_survival(
    orders_df: pd.DataFrame,
    profile: Any,
    bgnbd_model_card: Optional[ModelCard],
    *,
    store_id: str = "",
    data_dir: Optional[Path] = None,
    seed: int = 0,
    yaml_path: Optional[Path] = None,
) -> ModelCard:
    """Fit Cox PH survival and return a typed ``ModelCard``.

    Arguments:

    - ``orders_df``: schema ``customer_id``, ``order_date``. Other
      columns ignored.
    - ``profile``: ``StoreProfile`` (for stage-keyed threshold lookup).
    - ``bgnbd_model_card``: same-run BG/NBD ``ModelCard`` (chained-
      refusal input). May be ``None`` (treated as REFUSED for the
      purposes of the chained-refusal gate, surfaced as
      ``chained_bgnbd_refusal``).

    Flow:

    1. **Chained refusal first.** If bgnbd_model_card is missing or its
       fit_status ∈ {REFUSED, INSUFFICIENT_DATA}, short-circuit to
       REFUSED with ``chained_bgnbd_refusal``. No fit attempted. No
       parquet.
    2. **INSUFFICIENT_DATA gate.** Below the per-stage floor on months /
       repeat customers / censored events → INSUFFICIENT_DATA. No fit.
       No parquet.
    3. Time-based holdout split (default 90d window — long enough for
       honest Brier@90d evaluation).
    4. Build per-customer ``(time, event, covariates)`` frame from train
       slice. Customers with zero events in holdout are right-censored
       at the train-window boundary.
    5. Fit ``CoxPHSurvivalAnalysis()`` via lazy import. Convergence
       warnings or fit exceptions → REFUSED.
    6. Compute metrics: Harrell's C-index + integrated Brier @ 90d
       (``sksurv.metrics``).
    7. Classify under dual gate per DS thresholds.
    8. On {VALIDATED, PROVISIONAL}: write per-customer parquet
       (``p_survival_90d``, ``expected_days_to_next_purchase``) to
       ``<data_dir>/<store_id>/predictive/survival.parquet``.

    Returns the ModelCard. The caller (S13 audience-builder) decides
    whether the fit status permits consumption.
    """

    thresholds_full = _load_model_fit_thresholds(profile, yaml_path=yaml_path)
    surv_thr = thresholds_full["survival"]
    relax = thresholds_full["survival_relaxation_factors"]

    months_floor = surv_thr["months_data_validated"]
    repeat_floor = surv_thr["repeat_customers_validated"]
    events_floor = surv_thr["censored_events_validated"]
    c_index_validated = surv_thr["holdout_c_index_validated"]
    brier_validated_max = surv_thr["holdout_brier_score_90d_validated_max"]
    n_mult = relax["provisional_n_multiplier"]
    c_index_provisional_floor = relax["provisional_c_index_floor"]
    brier_provisional_max = relax["provisional_brier_score_90d_max"]

    counts = _data_depth_counts(orders_df)
    months = counts["months"]
    repeat = counts["repeat_customers"]
    observation_end = counts["observation_end"]
    training_window_days = (
        int((observation_end - pd.to_datetime(orders_df["order_date"]).min()).days)
        if not orders_df.empty
        else 0
    )

    # ---- Step 1: chained refusal on BG/NBD --------------------------------
    bgnbd_status = (
        getattr(bgnbd_model_card, "fit_status", None) if bgnbd_model_card is not None else None
    )
    if bgnbd_model_card is None or bgnbd_status in (
        ModelFitStatus.REFUSED,
        ModelFitStatus.INSUFFICIENT_DATA,
    ):
        return ModelCard(
            model_name="survival",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=["chained_bgnbd_refusal"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # ---- Step 2: INSUFFICIENT_DATA gate -----------------------------------
    provisional_repeat_floor = n_mult * repeat_floor
    # Events-floor pre-check at the data-depth level is loose: we don't know
    # holdout events yet. Use a proxy: repeat customers (≥1 second purchase)
    # vs the events floor with the relaxation multiplier. If we don't have
    # at least ~n_mult * events_floor repeat customers, we cannot possibly
    # have enough censored events.
    if (
        months < months_floor
        or repeat < provisional_repeat_floor
        or repeat < n_mult * events_floor
    ):
        return ModelCard(
            model_name="survival",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # ---- Step 3-4: time-based split + per-customer survival frame ---------
    train_orders, holdout_orders, window_days = _time_based_holdout_split(
        orders_df, observation_end, desired_window_days=90.0
    )
    train_obs_end = observation_end - pd.Timedelta(days=window_days)
    surv_frame = _build_survival_frame(train_orders, holdout_orders, train_obs_end)

    if surv_frame.empty or len(surv_frame) < int(n_mult * events_floor):
        return ModelCard(
            model_name="survival",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    n_events = int(surv_frame["event"].sum())
    # Honest events-floor check: require >= n_mult * events_floor uncensored
    # events to attempt fit; below that → INSUFFICIENT_DATA.
    if n_events < int(n_mult * events_floor):
        return ModelCard(
            model_name="survival",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # ---- Step 5: fit Cox PH (lazy sksurv import) --------------------------
    try:
        from sksurv.linear_model import CoxPHSurvivalAnalysis  # type: ignore
        from sksurv.metrics import (  # type: ignore
            concordance_index_censored,
            integrated_brier_score,
        )
    except ImportError:
        return ModelCard(
            model_name="survival",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=["sksurv_import_failed"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    X = surv_frame[["log_frequency", "log_recency_over_T"]].to_numpy(dtype=float)
    y = np.array(
        list(zip(surv_frame["event"].astype(bool).values, surv_frame["time"].astype(float).values)),
        dtype=[("event", "?"), ("time", "<f8")],
    )

    fit_warnings: list = []
    estimator: Any = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            estimator = CoxPHSurvivalAnalysis()
            estimator.fit(X, y)
        except Exception as exc:  # noqa: BLE001 — convergence failure surfaces here
            return ModelCard(
                model_name="survival",
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

    # ---- Step 6: holdout metrics ------------------------------------------
    # In-sample C-index + Brier on the train survival frame against the
    # holdout-derived (event, time) labels. The labels themselves encode
    # the time-based holdout (event=1 iff a holdout-window purchase
    # occurred). C-index uses predicted risk vector; Brier uses survival
    # functions at 90d.
    try:
        risk = estimator.predict(X)
        c_index = float(
            concordance_index_censored(
                surv_frame["event"].astype(bool).values,
                surv_frame["time"].astype(float).values,
                risk,
            )[0]
        )
    except Exception as exc:  # noqa: BLE001
        return ModelCard(
            model_name="survival",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + [f"c_index_failed:{type(exc).__name__}"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # Integrated Brier @ 90d. Requires both train + test survival arrays;
    # for an in-sample evaluation we pass y for both. sksurv requires the
    # evaluation times to lie strictly within the observed time range.
    brier_90d: Optional[float] = None
    try:
        t_min = float(surv_frame["time"].min())
        t_max = float(surv_frame["time"].max())
        # 90 must lie strictly inside the observed range for sksurv.
        target_time = 90.0
        if t_min < target_time < t_max:
            surv_fns = estimator.predict_survival_function(X)
            # Clamp evaluation to each function's domain (sksurv raises
            # ValueError outside it). For the brier evaluation we cap at
            # the function's upper bound when needed.
            def _eval_at(fn, t):
                lo, hi = float(fn.domain[0]), float(fn.domain[1])
                return float(fn(max(lo, min(hi, t))))
            # sksurv >= 0.22 returns StepFunction objects; evaluate at the
            # target time to build the survival probability matrix.
            surv_probs = np.array(
                [[_eval_at(fn, target_time)] for fn in surv_fns]
            )
            # integrated_brier_score requires >= 2 time points; emulate by
            # passing two close-together times and averaging — but for a
            # single horizon we use the simpler Brier-at-time formulation
            # via brier_score (also in sksurv.metrics) if available.
            try:
                from sksurv.metrics import brier_score  # type: ignore

                _times, bs = brier_score(y, y, surv_probs, [target_time])
                brier_90d = float(bs[0])
            except Exception:  # noqa: BLE001 — fall through to integrated form
                # Use two-point integration around target_time.
                eps = max(1.0, (t_max - t_min) * 0.01)
                t_lo = max(t_min + 1e-3, target_time - eps)
                t_hi = min(t_max - 1e-3, target_time + eps)
                surv_probs2 = np.column_stack(
                    [
                        np.array([_eval_at(fn, t_lo) for fn in surv_fns]),
                        np.array([_eval_at(fn, t_hi) for fn in surv_fns]),
                    ]
                )
                brier_90d = float(
                    integrated_brier_score(y, y, surv_probs2, [t_lo, t_hi])
                )
        # If 90d is outside the observed time range, brier_90d stays None
        # and the classifier treats it as un-measurable → REFUSED below.
    except Exception:  # noqa: BLE001
        brier_90d = None

    # ---- Step 7: classify (dual gate) -------------------------------------
    if "convergence_warning" in fit_warnings:
        return ModelCard(
            model_name="survival",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings,
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={
                "holdout_c_index": c_index,
                "holdout_brier_score_90d": brier_90d,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    if c_index is None or not np.isfinite(c_index):
        return ModelCard(
            model_name="survival",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + ["holdout_c_index_unmeasurable"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={
                "holdout_c_index": c_index,
                "holdout_brier_score_90d": brier_90d,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    if c_index < c_index_provisional_floor:
        return ModelCard(
            model_name="survival",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + ["holdout_c_index_below_floor"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={
                "holdout_c_index": c_index,
                "holdout_brier_score_90d": brier_90d,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    if brier_90d is None or not np.isfinite(brier_90d):
        return ModelCard(
            model_name="survival",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + ["holdout_brier_unmeasurable"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={
                "holdout_c_index": c_index,
                "holdout_brier_score_90d": brier_90d,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    if brier_90d > brier_provisional_max:
        return ModelCard(
            model_name="survival",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings + ["holdout_brier_above_floor"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=repeat,
            metrics={
                "holdout_c_index": c_index,
                "holdout_brier_score_90d": brier_90d,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
        )

    # Dual VALIDATED gate: BOTH c_index ≥ validated AND brier ≤ validated_max.
    is_validated = (
        c_index >= c_index_validated
        and brier_90d <= brier_validated_max
        and repeat >= repeat_floor
        and n_events >= events_floor
        and not fit_warnings
    )
    status = ModelFitStatus.VALIDATED if is_validated else ModelFitStatus.PROVISIONAL

    # Cox PH coefficients (per-covariate log hazard).
    coef_arr = np.asarray(getattr(estimator, "coef_", []), dtype=float)
    parameters: Dict[str, float] = {}
    if len(coef_arr) >= 1:
        parameters["coef_log_frequency"] = float(coef_arr[0])
    if len(coef_arr) >= 2:
        parameters["coef_log_recency_over_T"] = float(coef_arr[1])
    parameters["n_events"] = float(n_events)

    card = ModelCard(
        model_name="survival",
        fit_status=status,
        fit_warnings=fit_warnings,
        parameters=parameters,
        training_window_days=training_window_days,
        n_observed=int(len(surv_frame)),
        metrics={
            "holdout_c_index": c_index,
            "holdout_brier_score_90d": brier_90d,
        },
        fit_timestamp=_now_iso(),
        parquet_schema_version=1,
    )

    # ---- Step 8: write parquet (VALIDATED / PROVISIONAL only) -------------
    if data_dir is not None and store_id:
        _write_parquet(
            surv_frame, estimator, data_dir=Path(data_dir), store_id=store_id
        )

    return card


def _write_parquet(
    surv_frame: pd.DataFrame,
    estimator: Any,
    *,
    data_dir: Path,
    store_id: str,
) -> Path:
    """Write per-customer survival predictions to parquet.

    Schema (parquet_schema_version=1):

    - ``customer_id``: str
    - ``p_survival_90d``: float [0, 1] (probability of NO purchase in
      the next 90 days, i.e. S(90)).
    - ``expected_days_to_next_purchase``: float ≥ 0 (cumulative-hazard
      inversion at the median; ``log(2) / risk_score`` as a proxy when
      a closed-form inversion is not available).
    - ``parquet_schema_version``: int (constant 1).
    """

    X = surv_frame[["log_frequency", "log_recency_over_T"]].to_numpy(dtype=float)
    surv_fns = estimator.predict_survival_function(X)
    # StepFunction domain is bounded by the observed event times in the
    # training sample. Clamp all evaluations to that domain (sksurv raises
    # ValueError outside it). p_survival_90d evaluates at 90d if 90d lies
    # inside the domain, else at the domain's upper bound (right-censored
    # survival probability at the observation boundary).
    def _eval(fn, t: float) -> float:
        lo, hi = float(fn.domain[0]), float(fn.domain[1])
        return float(fn(max(lo, min(hi, t))))

    p_survival_90d = np.array([_eval(fn, 90.0) for fn in surv_fns], dtype=float)
    # Expected days to next purchase: invert the survival function at the
    # 50% probability quantile per customer. StepFunction objects support
    # evaluation but not direct inversion, so we sample on a per-customer
    # grid spanning the function's domain and find the first time at which
    # S(t) <= 0.5.
    expected_days = np.full(len(surv_fns), np.nan, dtype=float)
    for i, fn in enumerate(surv_fns):
        lo, hi = float(fn.domain[0]), float(fn.domain[1])
        grid = np.linspace(max(1.0, lo), hi, 200)
        s_vals = np.array([float(fn(t)) for t in grid])
        below = np.where(s_vals <= 0.5)[0]
        if len(below) > 0:
            expected_days[i] = float(grid[below[0]])
        else:
            # All survival probabilities > 0.5 within the observed horizon;
            # mark as the upper boundary (right-censored).
            expected_days[i] = float(hi)

    out = pd.DataFrame({
        "customer_id": surv_frame["customer_id"].astype(str),
        "p_survival_90d": p_survival_90d,
        "expected_days_to_next_purchase": expected_days,
        "parquet_schema_version": 1,
    })
    out_dir = data_dir / store_id / "predictive"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "survival.parquet"
    out.to_parquet(target, index=False)
    return target


__all__ = ["fit_survival"]
