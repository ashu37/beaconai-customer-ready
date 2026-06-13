"""Retention curves substrate (Sprint 12 — T2).

Cohort-aggregate empirical retention with bootstrap confidence intervals.
Customers are bucketed into cohorts by first-purchase month; for each
cohort, we compute period (per-month) and cumulative (ever-returned-by-
month-M) retention rates and 95% bootstrap CIs. Produces a typed
``RetentionCard`` describing fit health under the four-state
``ModelFitStatus`` vocabulary documented in
``src/predictive/model_card.py``.

S12-T2 ship constraints
=======================

- Flag-OFF land. Behind ``ENGINE_V2_ML_RETENTION`` (default OFF).
- No PlayCard consumes the fit output. Surfaces only on
  ``engine_run.cohort_diagnostics["retention"]`` when the flag is ON
  (T2.5 atomic flip wires it; T2 is module + schema only).
- **No parquet artifact.** The retention object is JSON-shaped (per-
  cohort dict of curves + CIs) and lives directly inside
  ``engine_run.cohort_diagnostics``. Mirrors the IM plan §C and DS
  verdict §C storage decision.

Architectural separation (DS-locked 2026-05-28)
===============================================

Retention is a **cohort-aggregate diagnostic**, NOT a per-customer
ranker. It therefore lives in a NEW top-level
``EngineRun.cohort_diagnostics`` slot — NOT ``predictive_models``. The
``predictive_models`` Dict is contractually a per-customer-ranker shape
(holdout_rank_spearman, c_index, top-K recall, parquet artifacts); a
cohort-aggregate diagnostic inverts those invariants. Future cohort-
aggregate diagnostics (cohort-AOV evolution, cohort-frequency, churn-
hazard-by-cohort) will share the same slot.

Retention is INDEPENDENT (no chained refusal)
=============================================

Retention takes no chained input — it does not consume BG/NBD,
Gamma-Gamma, survival, CF, or RFM model cards. ``fit_retention`` accepts
no ``bgnbd_model_card`` argument and fits independently of those
substrates' status. Mirrors CF (S11-T2) and RFM (S12-T1) posture.

DS-locked validation metrics (sign-off 2026-05-28)
==================================================

PRIMARY gate: **bootstrap_ci_width_at_month_3** — mean across analyzed
cohorts of the 95% percentile bootstrap CI width on cumulative retention
at month-3. Tight CIs (small width) → informative curve. Stage-keyed
VALIDATED floors {startup 0.25, growth 0.20, mature 0.15, enterprise
0.15}; PROVISIONAL ceiling 0.35; REFUSED above 0.35.

SECONDARY gate: **cohort_count_validated** floor (stage-keyed). Must
also clear (AND, not OR — per DS §G "CI-width without cohort_count is
statistical artifact; cohort_count without CI-width is shape-only").

REFUSED gate: **cumulative_retention_monotonicity_violation** — if any
cohort's cumulative-retention curve is non-monotonic, the fit is
REFUSED. Mathematically a violation on the "ever-returned-in-[0, M]"
definition is impossible (a customer who has ever returned cannot
un-return); a violation therefore signals a data-shape bug (duplicate
orders excluded, drift in cohort definition, mis-bucketed dates).
DS-mandated promotion from tertiary-diagnostic (v1) to REFUSED
(2026-05-28).

INSUFFICIENT_DATA gate: below absolute cohort_count floor (3) OR below
min_cohort_size floor (20) → no retention curves computed; no parquet.

Cumulative-retention definition (chosen)
========================================

``cumulative_retention[M]`` = fraction of cohort C with ≥1 order in
calendar months **strictly after the acquisition month**, i.e. in
[first_month+1, first_month+M]. By convention
``cumulative_retention[0] = 0.0`` (no post-acquisition months observed
yet). For M ≥ 1, the curve is **monotonically non-decreasing**
(a customer who has ever returned cannot un-return). The REFUSED gate
fires when ANY cohort violates this monotone direction.

This framing excludes the acquisition month from the "retention" count
— it measures genuine come-backs, not the trivial 100%-at-M0 floor.
Mirrors the standard DTC analytics retention-curve convention
(Reichheld 1990; Pfeifer & Carraway 2000).

``period_retention[M]`` = fraction of cohort C with ≥1 order in the
month [first_month + M, first_month + M + 1) (open-right). At M=0 this
is 1.0 by construction (cohort definition). For M ≥ 1 it is NOT
expected to be monotone in either direction (it's the natural per-month
return rate, which decays from month 1 and then noisily floats). It is
diagnostic-only — not gated.

Bootstrap procedure
===================

For each cohort × month, resample customers with replacement
``bootstrap_iterations`` times (default 1000), compute the retention
rate per resample, and derive the 95% percentile CI (2.5th and 97.5th
percentiles). ``seed=0`` default for determinism — same input + same
seed → byte-identical CI bounds.

References: Bain & Co Reichheld (1990) "Zero Defections"; Pfeifer &
Carraway (2000) "Modeling customer relationships as Markov chains";
Cohort-curve framing follows standard DTC analytics conventions
(no third-party library — see DS verdict §D rationale).

Thresholds: KI-NEW-P extension (speculative-until-S14 calibration).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .model_card import RetentionCard, ModelFitStatus, _load_model_fit_thresholds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _month_floor(ts: pd.Timestamp) -> pd.Timestamp:
    """Floor a timestamp to the first day of its calendar month (UTC-naive)."""
    return pd.Timestamp(year=ts.year, month=ts.month, day=1)


def _months_between(start: pd.Timestamp, end: pd.Timestamp) -> int:
    """Integer months from start month to end month (both month-floored)."""
    return (end.year - start.year) * 12 + (end.month - start.month)


def _build_customer_active_months(
    orders_df: pd.DataFrame,
) -> Tuple[Dict[str, set], Dict[str, pd.Timestamp]]:
    """Return per-customer set of active month-indices (calendar months) and
    each customer's first-purchase month timestamp.

    Output:
      - ``active_months[customer_id]``: set of month-floor Timestamps the
        customer placed at least one order in.
      - ``first_month[customer_id]``: month-floor Timestamp of the
        customer's earliest order.
    """
    df = orders_df[["customer_id", "order_date"]].copy()
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["month"] = df["order_date"].apply(_month_floor)

    active_months: Dict[str, set] = {}
    first_month: Dict[str, pd.Timestamp] = {}
    for cust, grp in df.groupby("customer_id"):
        months = set(grp["month"].tolist())
        active_months[str(cust)] = months
        first_month[str(cust)] = min(months)

    return active_months, first_month


def _compute_cohort_curves(
    cohort_customer_ids: List[str],
    cohort_first_month: pd.Timestamp,
    active_months: Dict[str, set],
    months_horizon: int,
) -> Tuple[List[float], List[float]]:
    """For one cohort, compute period and cumulative retention vectors
    of length ``months_horizon + 1`` (M=0..months_horizon inclusive).

    Cumulative definition: fraction of cohort with ≥1 order in months
    [first_month, first_month+M]. Non-decreasing in M.

    Period definition: fraction of cohort with ≥1 order in the specific
    month bucket first_month+M.
    """
    n = len(cohort_customer_ids)
    period = [0.0] * (months_horizon + 1)
    cumulative = [0.0] * (months_horizon + 1)
    if n == 0:
        return period, cumulative

    # Precompute month-offset bucket Timestamps for the horizon.
    bucket_months: List[pd.Timestamp] = []
    cur = cohort_first_month
    bucket_months.append(cur)
    for _ in range(months_horizon):
        # advance by one calendar month
        if cur.month == 12:
            cur = pd.Timestamp(year=cur.year + 1, month=1, day=1)
        else:
            cur = pd.Timestamp(year=cur.year, month=cur.month + 1, day=1)
        bucket_months.append(cur)

    period_counts = [0] * (months_horizon + 1)
    # cumulative_counts tracks customers who have ordered in months
    # strictly AFTER the acquisition month (post-acquisition retention).
    # M=0 is always 0 by definition (no post-acquisition months yet);
    # for M ≥ 1, count is monotonically non-decreasing.
    cumulative_counts = [0] * (months_horizon + 1)

    for cid in cohort_customer_ids:
        months = active_months.get(cid, set())
        ever_returned_post_acq = False
        for m_idx, bucket in enumerate(bucket_months):
            if bucket in months:
                period_counts[m_idx] += 1
                if m_idx >= 1:
                    ever_returned_post_acq = True
            if m_idx >= 1 and ever_returned_post_acq:
                cumulative_counts[m_idx] += 1

    for m_idx in range(months_horizon + 1):
        period[m_idx] = float(period_counts[m_idx]) / float(n)
        cumulative[m_idx] = float(cumulative_counts[m_idx]) / float(n)

    return period, cumulative


def _bootstrap_cumulative_ci(
    cohort_customer_ids: List[str],
    cohort_first_month: pd.Timestamp,
    active_months: Dict[str, set],
    months_horizon: int,
    *,
    iterations: int,
    rng: np.random.Generator,
) -> Tuple[List[float], List[float]]:
    """Percentile bootstrap CI (95%) for cumulative retention at each month.

    Resamples customers with replacement ``iterations`` times. For each
    resample, computes the cumulative-retention vector and stacks them.
    Returns (lower[2.5pct], upper[97.5pct]) vectors of length
    ``months_horizon + 1``.
    """
    n = len(cohort_customer_ids)
    if n == 0 or iterations <= 0:
        zeros = [0.0] * (months_horizon + 1)
        return zeros, zeros

    # Precompute per-customer cumulative active-by-month vector once.
    # cumulative_active_vec[c_idx][m_idx] = 1 if customer ever-returned by
    # month m (in [first_month, first_month+m]); else 0.
    bucket_months: List[pd.Timestamp] = []
    cur = cohort_first_month
    bucket_months.append(cur)
    for _ in range(months_horizon):
        if cur.month == 12:
            cur = pd.Timestamp(year=cur.year + 1, month=1, day=1)
        else:
            cur = pd.Timestamp(year=cur.year, month=cur.month + 1, day=1)
        bucket_months.append(cur)

    # Post-acquisition cumulative: M=0 is 0 by definition; for M ≥ 1,
    # the indicator becomes 1 once the customer orders in any month
    # strictly after acquisition. Matches _compute_cohort_curves.
    per_customer_cumulative = np.zeros((n, months_horizon + 1), dtype=np.int8)
    for c_idx, cid in enumerate(cohort_customer_ids):
        months = active_months.get(cid, set())
        ever_post_acq = 0
        for m_idx, bucket in enumerate(bucket_months):
            if m_idx >= 1 and bucket in months:
                ever_post_acq = 1
            if m_idx >= 1:
                per_customer_cumulative[c_idx, m_idx] = ever_post_acq
            # m_idx == 0 stays 0 (initialized zero).

    # Vectorized bootstrap: sample indices, sum along axis 0, divide by n.
    lower = np.zeros(months_horizon + 1, dtype=float)
    upper = np.zeros(months_horizon + 1, dtype=float)
    sample_indices = rng.integers(0, n, size=(iterations, n))
    # Compute resampled retention rates per iteration per month.
    retention_per_iter = np.zeros((iterations, months_horizon + 1), dtype=float)
    for it in range(iterations):
        idxs = sample_indices[it]
        resampled = per_customer_cumulative[idxs]
        retention_per_iter[it] = resampled.sum(axis=0) / float(n)

    lower = np.percentile(retention_per_iter, 2.5, axis=0)
    upper = np.percentile(retention_per_iter, 97.5, axis=0)
    return [float(x) for x in lower], [float(x) for x in upper]


def _detect_monotonicity_violation(cumulative: List[float]) -> bool:
    """Returns True if ``cumulative`` is NOT monotonically non-decreasing
    (the "ever returned by month M" definition is non-decreasing). A
    tiny floating-point tolerance is applied to allow for re-derivation
    noise; conceptually violations should not arise from correct data.
    """
    eps = 1e-9
    for i in range(1, len(cumulative)):
        if cumulative[i] < cumulative[i - 1] - eps:
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fit_retention(
    transactions_df: pd.DataFrame,
    profile: Any,
    *,
    store_id: str = "",
    seed: int = 0,
    yaml_path: Optional[Path] = None,
) -> RetentionCard:
    """Fit empirical cohort retention curves and return a typed ``RetentionCard``.

    Arguments:

    - ``transactions_df``: schema ``customer_id``, ``order_date`` (plus
      any other columns, which are ignored). No monetary column required —
      retention is a counts-only curve.
    - ``profile``: ``StoreProfile`` (for stage-keyed threshold lookup).
    - ``store_id``: forwarded for fingerprinting (no parquet is written).
    - ``seed``: RNG seed for bootstrap CI (default 0 for determinism).
    - ``yaml_path``: optional override for testing.

    **Retention is INDEPENDENT.** No ``bgnbd_model_card`` argument. No
    chained refusal on any prior substrate. Retention fits on its own
    regardless of BG/NBD / G-G / survival / CF / RFM fit status.

    Flow:

    1. **INSUFFICIENT_DATA gate.** Below absolute cohort_count floor (3)
       OR below min_cohort_size floor (20) → no retention curves
       computed. No parquet (retention does not write parquet anyway).
    2. Cohort construction: group customers by first-purchase month.
    3. For each cohort (with sufficient look-forward window to observe
       month-3), compute period and cumulative retention plus bootstrap
       CIs.
    4. Compute ``bootstrap_ci_width_at_month_3`` (mean across analyzed
       cohorts of the upper-minus-lower CI at month 3).
    5. Check cumulative-retention monotonicity violation across all
       cohorts.
    6. Four-state classifier per DS thresholds:
       - REFUSED if monotonicity violation OR CI width > provisional
         ceiling OR cohort_count < absolute floor (after attempted fit).
       - VALIDATED if CI width ≤ stage VALIDATED floor AND cohort_count
         ≥ stage VALIDATED floor AND no monotonicity violation.
       - PROVISIONAL otherwise (provisional band).

    Returns the RetentionCard. The caller (S13 audience-builder) decides
    whether the fit status permits consumption. The card is intended to
    be written to ``engine_run.cohort_diagnostics["retention"]`` by the
    orchestrator at T2.5.
    """

    thresholds_full = _load_model_fit_thresholds(profile, yaml_path=yaml_path)
    ret_thr = thresholds_full["retention"]
    relax = thresholds_full["retention_relaxation_factors"]
    guards = thresholds_full["retention_guards"]

    cohort_count_validated = int(ret_thr["cohort_count_validated"])
    ci_width_validated_max = float(ret_thr["bootstrap_ci_width_at_month_3_max_validated"])
    provisional_n_multiplier = float(relax["provisional_n_multiplier"])
    provisional_ci_width_max = float(relax["provisional_bootstrap_ci_width_at_month_3_max"])
    absolute_cohort_floor = int(guards["absolute_cohort_count_floor"])
    bootstrap_iterations = int(guards["bootstrap_iterations"])
    months_horizon = int(guards["months_horizon"])
    min_cohort_size_floor = int(guards["min_cohort_size_floor"])
    monotonicity_refused = bool(
        guards["cumulative_retention_monotonicity_violation_refused"]
    )

    fit_timestamp = _now_iso()

    # ---- Pre-flight: empty / schema-incomplete -> INSUFFICIENT_DATA -------
    if (
        transactions_df is None
        or transactions_df.empty
        or "customer_id" not in transactions_df.columns
        or "order_date" not in transactions_df.columns
    ):
        return RetentionCard(
            model_name="retention",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            cohort_count=0,
            min_cohort_size=0,
            bootstrap_ci_width_at_month_3=None,
            cumulative_retention_monotonicity_violation=False,
            months_horizon=months_horizon,
            cohorts={},
            bootstrap_iterations=bootstrap_iterations,
            seed=seed,
            fit_timestamp=fit_timestamp,
            parquet_schema_version=1,
        )

    # ---- Build per-customer active month sets -----------------------------
    active_months, first_month = _build_customer_active_months(transactions_df)

    # ---- Cohort grouping: customers by first-purchase month ---------------
    cohorts_membership: Dict[pd.Timestamp, List[str]] = {}
    for cid, fm in first_month.items():
        cohorts_membership.setdefault(fm, []).append(cid)

    # Snapshot = max month in the data; only cohorts with at least
    # ``months_horizon`` (=12) months of forward visibility are full-horizon,
    # but for the primary gate we need month-3 visibility — require at
    # least 3 months of look-forward (cohort_first_month + 3 <= snapshot).
    snapshot_ts = _month_floor(pd.to_datetime(transactions_df["order_date"]).max())

    eligible_cohorts: List[Tuple[pd.Timestamp, List[str]]] = []
    for first_m, members in cohorts_membership.items():
        if len(members) < min_cohort_size_floor:
            continue
        if _months_between(first_m, snapshot_ts) < 3:
            # Cannot observe month-3 retention yet — exclude from primary gate.
            continue
        eligible_cohorts.append((first_m, members))

    cohort_count = len(eligible_cohorts)
    min_cohort_size = (
        min(len(m) for _, m in eligible_cohorts) if eligible_cohorts else 0
    )

    # ---- INSUFFICIENT_DATA gate ------------------------------------------
    if cohort_count < absolute_cohort_floor or min_cohort_size < min_cohort_size_floor:
        return RetentionCard(
            model_name="retention",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            cohort_count=cohort_count,
            min_cohort_size=min_cohort_size,
            bootstrap_ci_width_at_month_3=None,
            cumulative_retention_monotonicity_violation=False,
            months_horizon=months_horizon,
            cohorts={},
            bootstrap_iterations=bootstrap_iterations,
            seed=seed,
            fit_timestamp=fit_timestamp,
            parquet_schema_version=1,
        )

    # ---- Compute per-cohort curves + bootstrap CIs -----------------------
    cohorts_out: Dict[str, Any] = {}
    monotonicity_violation = False
    rng = np.random.default_rng(seed)
    ci_width_at_month_3_per_cohort: List[float] = []

    # Process cohorts in stable sorted order for determinism.
    eligible_cohorts_sorted = sorted(eligible_cohorts, key=lambda kv: kv[0])

    for first_m, members in eligible_cohorts_sorted:
        # Truncate horizon based on what's observable for this cohort.
        observable_horizon = min(
            months_horizon, _months_between(first_m, snapshot_ts)
        )
        period, cumulative = _compute_cohort_curves(
            members,
            first_m,
            active_months,
            observable_horizon,
        )
        ci_lower, ci_upper = _bootstrap_cumulative_ci(
            members,
            first_m,
            active_months,
            observable_horizon,
            iterations=bootstrap_iterations,
            rng=rng,
        )

        if _detect_monotonicity_violation(cumulative):
            monotonicity_violation = True

        if len(cumulative) >= 4:  # M=0..3 inclusive
            ci_width_at_month_3_per_cohort.append(
                float(ci_upper[3] - ci_lower[3])
            )

        cohort_key = first_m.strftime("%Y-%m")
        cohorts_out[cohort_key] = {
            "period_retention": period,
            "cumulative_retention": cumulative,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "n_customers": int(len(members)),
        }

    bootstrap_ci_width_at_month_3: Optional[float] = (
        float(np.mean(ci_width_at_month_3_per_cohort))
        if ci_width_at_month_3_per_cohort
        else None
    )

    # ---- Four-state classifier -------------------------------------------
    fit_warnings: List[str] = []

    # REFUSED gate 1: monotonicity violation.
    if monotonicity_violation and monotonicity_refused:
        fit_warnings.append("cumulative_retention_monotonicity_violation")
        return RetentionCard(
            model_name="retention",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings,
            cohort_count=cohort_count,
            min_cohort_size=min_cohort_size,
            bootstrap_ci_width_at_month_3=bootstrap_ci_width_at_month_3,
            cumulative_retention_monotonicity_violation=True,
            months_horizon=months_horizon,
            cohorts=cohorts_out,
            bootstrap_iterations=bootstrap_iterations,
            seed=seed,
            fit_timestamp=fit_timestamp,
            parquet_schema_version=1,
        )

    # REFUSED gate 2: CI width above provisional ceiling.
    if (
        bootstrap_ci_width_at_month_3 is not None
        and bootstrap_ci_width_at_month_3 > provisional_ci_width_max
    ):
        fit_warnings.append("bootstrap_ci_width_above_provisional_ceiling")
        return RetentionCard(
            model_name="retention",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=fit_warnings,
            cohort_count=cohort_count,
            min_cohort_size=min_cohort_size,
            bootstrap_ci_width_at_month_3=bootstrap_ci_width_at_month_3,
            cumulative_retention_monotonicity_violation=False,
            months_horizon=months_horizon,
            cohorts=cohorts_out,
            bootstrap_iterations=bootstrap_iterations,
            seed=seed,
            fit_timestamp=fit_timestamp,
            parquet_schema_version=1,
        )

    # VALIDATED: CI width ≤ stage VALIDATED floor AND cohort_count ≥ stage
    # VALIDATED floor AND no monotonicity violation.
    is_validated = (
        bootstrap_ci_width_at_month_3 is not None
        and bootstrap_ci_width_at_month_3 <= ci_width_validated_max
        and cohort_count >= cohort_count_validated
        and not monotonicity_violation
    )

    # PROVISIONAL: CI width ≤ provisional ceiling, cohort_count ≥
    # provisional_n_multiplier × VALIDATED floor.
    provisional_cohort_floor = max(
        absolute_cohort_floor,
        int(np.ceil(provisional_n_multiplier * cohort_count_validated)),
    )

    if is_validated:
        status = ModelFitStatus.VALIDATED
    elif (
        bootstrap_ci_width_at_month_3 is not None
        and bootstrap_ci_width_at_month_3 <= provisional_ci_width_max
        and cohort_count >= provisional_cohort_floor
    ):
        status = ModelFitStatus.PROVISIONAL
        if (
            bootstrap_ci_width_at_month_3 is not None
            and bootstrap_ci_width_at_month_3 > ci_width_validated_max
        ):
            fit_warnings.append("bootstrap_ci_width_above_validated_floor")
        if cohort_count < cohort_count_validated:
            fit_warnings.append("cohort_count_below_validated_floor")
    else:
        # Catch-all: fit attempted but neither VALIDATED nor PROVISIONAL.
        # Treat as REFUSED (e.g. cohort_count below provisional floor after
        # attempted fit). NOT INSUFFICIENT_DATA — we tried.
        status = ModelFitStatus.REFUSED
        fit_warnings.append("retention_below_provisional_thresholds")

    return RetentionCard(
        model_name="retention",
        fit_status=status,
        fit_warnings=fit_warnings,
        cohort_count=cohort_count,
        min_cohort_size=min_cohort_size,
        bootstrap_ci_width_at_month_3=bootstrap_ci_width_at_month_3,
        cumulative_retention_monotonicity_violation=monotonicity_violation,
        months_horizon=months_horizon,
        cohorts=cohorts_out,
        bootstrap_iterations=bootstrap_iterations,
        seed=seed,
        fit_timestamp=fit_timestamp,
        parquet_schema_version=1,
    )


__all__ = ["fit_retention"]
