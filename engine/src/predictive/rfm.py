"""RFM (Recency × Frequency × Monetary) segmentation substrate (Sprint 12 — T1).

Deterministic per-customer segmentation via classical Hughes (1994) /
Kumar & Reinartz (2018) Recency-Frequency-Monetary scoring. R/F/M
quintile scores are computed via ``pd.qcut`` (rank-based binning,
robust to long-tail monetary distributions) and mapped to 11
industry-canonical named segments. Produces a typed ``ModelCard``
describing fit health under the four-state ``ModelFitStatus``
vocabulary documented in ``src/predictive/model_card.py``.

S12-T1 ship constraints
=======================

- Flag-OFF land. Behind ``ENGINE_V2_ML_RFM`` (default OFF).
- No PlayCard consumes the fit output. Surfaces only on
  ``engine_run.predictive_models["rfm"]`` when the flag is ON (T1.5
  atomic flip wires it; T1 is module + schema only).
- Parquet per-customer assignment artifact at
  ``data/<store_id>/predictive/rfm.parquet`` is written **only when
  fit_status in {VALIDATED, PROVISIONAL}**. INSUFFICIENT_DATA / REFUSED
  produce a ModelCard with no parquet artifact (privacy posture, D-3
  deletion semantics).

DS-locked validation metrics (sign-off 2026-05-28)
==================================================

PRIMARY gate: **segment_monotonicity_spearman** — Spearman rank
correlation between the named-segment LTV-rank-order (Champions →
Lost) and observed mean monetary value per segment. The segmentation
IS the answer; this is an **internal-consistency** check, NOT a
holdout / fit-quality metric. VALIDATED floors stage-keyed
{startup 0.60, growth 0.65, mature 0.70, enterprise 0.70};
PROVISIONAL floor 0.40; REFUSED below 0.40.

SECONDARY REFUSED guard: **quintile_coverage_min** — smallest
quintile-occupancy ratio across the three dimensions. Below the
``refused_quintile_coverage_min`` (default 0.05) → REFUSED
(degenerate quintile collapse — e.g. ``pd.qcut`` ties dominate or
the distribution is bimodal-with-spikes).

RFM is INDEPENDENT of BG/NBD (DS-locked)
========================================

Per DS S12 plan review §F: RFM's signal (per-customer R/F/M quintile
position) has no structural dependency on the gap-time signal that
BG/NBD/survival evaluate. **RFM DOES NOT CHAIN ON BG/NBD.**
``fit_rfm`` accepts no ``bgnbd_model_card`` argument and fits
independently regardless of BG/NBD's fit status. Mirrors CF (S11-T2)
posture, deliberate architectural divergence from ``fit_survival``.

Named segment mapping rules (industry-canonical bands)
======================================================

R quintile = 1 (oldest recency) through 5 (most recent purchase).
F quintile = 1 (lowest frequency) through 5 (highest frequency).
M quintile = 1 (lowest spend) through 5 (highest spend).

Mapping (first-match wins; documented for DS review):

1.  **Champions** — R=5 AND F>=4 AND M>=4. Top-of-funnel VIPs.
2.  **Cannot Lose Them** — R<=2 AND F>=4 AND M>=4. Lapsed VIPs;
    high-value historically but trending dormant.
3.  **Loyal Customers** — F>=4 AND M>=4 AND R==3. Established
    regulars with decent recency.
4.  **At Risk** — R<=2 AND F>=3 AND M>=3. Long-lapsed high-value
    customers (less extreme than Cannot Lose Them).
5.  **Need Attention** — R==3 AND F>=3 AND M>=3. Established
    customers showing slippage in recency.
6.  **Potential Loyalists** — R>=4 AND F>=2 AND M>=3 AND F<=3.
    Recent buyers building frequency.
7.  **Promising** — R>=4 AND F<=2 AND M>=3. Recent, decent spend,
    low frequency — recent first-or-second purchase of meaningful
    size.
8.  **New Customers** — R==5 AND F==1. Just bought first time
    recently.
9.  **About To Sleep** — R==2 AND F>=2 AND M>=2. Recently lapsed,
    decent history.
10. **Hibernating** — R<=2 AND F<=3 AND M<=3 AND F>=2. Low
    engagement, dormant.
11. **Lost** — R==1 AND F==1. Long-lapsed, single-purchase.

Anything that does not match the above is bucketed as **Hibernating**
(default catchall — low engagement, no distinguishing signal).

The LTV-rank-order used by the segment-monotonicity Spearman
(highest-realized-LTV → lowest):

  Champions → Cannot Lose Them → Loyal Customers → At Risk →
  Need Attention → Potential Loyalists → Promising →
  New Customers → About To Sleep → Hibernating → Lost.

References: Hughes (1994) "Strategic Database Marketing"; Kumar &
Reinartz (2018) "Customer Relationship Management"; this exact
band set follows Crowder/Putler industry-canonical schemas.

Thresholds: KI-NEW-P extension (speculative-until-S14 calibration).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .model_card import (
    ModelCard,
    ModelFitStatus,
    RfmSegmentDistributionSuppressionReason,
    SegmentBand,
    _load_model_fit_thresholds,
)


# ---------------------------------------------------------------------------
# Segment vocabulary + LTV rank order (DS-reviewed)
# ---------------------------------------------------------------------------

# Highest-LTV-first ranking used by segment_monotonicity_spearman.
SEGMENT_LTV_RANK_ORDER: Tuple[str, ...] = (
    "Champions",
    "Cannot Lose Them",
    "Loyal Customers",
    "At Risk",
    "Need Attention",
    "Potential Loyalists",
    "Promising",
    "New Customers",
    "About To Sleep",
    "Hibernating",
    "Lost",
)

# Map: segment name -> integer rank (1 = highest-expected-LTV).
_SEGMENT_RANK: Dict[str, int] = {
    name: idx + 1 for idx, name in enumerate(SEGMENT_LTV_RANK_ORDER)
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_monetary_column(orders_df: pd.DataFrame) -> Optional[str]:
    """Pick the monetary column. Preference: ``total`` -> ``revenue`` -> ``amount``."""

    for col in ("total", "revenue", "amount", "order_total"):
        if col in orders_df.columns:
            return col
    return None


def _compute_rfm_table(
    orders_df: pd.DataFrame,
    *,
    snapshot_date: pd.Timestamp,
    monetary_col: str,
) -> pd.DataFrame:
    """Aggregate orders to per-customer R/F/M raw values.

    Returns a DataFrame with columns:
      - ``customer_id``
      - ``recency_days``: integer days since most recent purchase
        (lower = better; will be reversed when binned to quintile).
      - ``frequency``: number of orders observed in the window.
      - ``monetary``: sum of monetary column across orders.
    """

    df = orders_df[["customer_id", "order_date", monetary_col]].copy()
    df["order_date"] = pd.to_datetime(df["order_date"])
    df[monetary_col] = pd.to_numeric(df[monetary_col], errors="coerce").fillna(0.0)
    grouped = df.groupby("customer_id").agg(
        last_purchase=("order_date", "max"),
        frequency=("order_date", "count"),
        monetary=(monetary_col, "sum"),
    )
    grouped["recency_days"] = (snapshot_date - grouped["last_purchase"]).dt.days.astype(int)
    grouped = grouped.reset_index()[
        ["customer_id", "recency_days", "frequency", "monetary"]
    ]
    return grouped


def _safe_qcut(series: pd.Series, q: int = 5, *, reverse: bool = False) -> pd.Series:
    """``pd.qcut`` with duplicate-edge handling. Returns ints in [1, q].

    Uses raw values (NOT rank-first) so genuine value collapse — e.g.
    99% of customers at the same monetary spike — surfaces as bin
    collapse and is caught by ``quintile_coverage_min``. ``duplicates=
    "drop"`` is used so identical edges don't crash; the result may
    have fewer than ``q`` unique bins, which is exactly the signal we
    want the coverage min to detect.

    ``reverse=True`` flips the quintile mapping (used for R, where
    LOWER days-since-purchase should map to a HIGHER quintile).
    """

    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() == 0 or s.nunique() < 2:
        # All NaN or all equal → single bucket; coverage_min will be 0.
        binned = pd.Series([0] * len(s), index=s.index)
    else:
        try:
            binned = pd.qcut(s, q=q, labels=False, duplicates="drop")
        except (ValueError, TypeError):
            binned = pd.Series([0] * len(s), index=s.index)
    binned = binned.fillna(0).astype(int) + 1  # shift to 1..k
    if reverse:
        # Map highest-bin -> 1, lowest-bin -> q (so lowest recency_days = highest R-score).
        max_bin = int(binned.max()) if len(binned) > 0 else 1
        binned = max_bin + 1 - binned
    return binned


def _assign_segment(r: int, f: int, m: int) -> str:
    """Industry-canonical (R, F, M) -> named-segment mapping.

    First-match wins. See module docstring for the exact band table.
    """

    # 1. Champions
    if r == 5 and f >= 4 and m >= 4:
        return "Champions"
    # 2. Cannot Lose Them
    if r <= 2 and f >= 4 and m >= 4:
        return "Cannot Lose Them"
    # 3. Loyal Customers
    if f >= 4 and m >= 4 and r == 3:
        return "Loyal Customers"
    # 4. At Risk
    if r <= 2 and f >= 3 and m >= 3:
        return "At Risk"
    # 5. Need Attention
    if r == 3 and f >= 3 and m >= 3:
        return "Need Attention"
    # 6. Potential Loyalists
    if r >= 4 and 2 <= f <= 3 and m >= 3:
        return "Potential Loyalists"
    # 7. Promising
    if r >= 4 and f <= 2 and m >= 3:
        return "Promising"
    # 8. New Customers
    if r == 5 and f == 1:
        return "New Customers"
    # 9. About To Sleep
    if r == 2 and f >= 2 and m >= 2:
        return "About To Sleep"
    # 10. Lost (single-purchase + long-lapsed)
    if r == 1 and f == 1:
        return "Lost"
    # 11. Hibernating (default catchall — low engagement, no distinguishing signal)
    return "Hibernating"


def _quintile_coverage_min(
    r_scores: pd.Series, f_scores: pd.Series, m_scores: pd.Series
) -> float:
    """Smallest min-quintile-occupancy ratio across R/F/M.

    For each dimension, compute ``min(count_per_quintile) / total``
    where ``count_per_quintile`` is the size of the smallest of the 5
    quintile buckets. Below ``refused_quintile_coverage_min`` (default
    0.05) → REFUSED (signals ``pd.qcut`` collapse from ties).
    """

    total = max(1, len(r_scores))

    def _one(series: pd.Series) -> float:
        counts = series.value_counts()
        # Reference the *expected* 5 buckets — missing buckets count as 0.
        present = counts.reindex(range(1, 6), fill_value=0)
        return float(present.min()) / float(total)

    return float(min(_one(r_scores), _one(f_scores), _one(m_scores)))


def _segment_monotonicity_spearman(
    segment_assignments: pd.Series, monetary_per_customer: pd.Series
) -> Optional[float]:
    """Spearman rank correlation between segment-LTV-rank and observed mean monetary per segment.

    Per DS verdict §F (IM spec verbatim): "Spearman rank correlation
    between (named-segment-rank-ordered-by-expected-LTV) and (observed
    mean monetary value per customer within each segment)" —
    **segment-mean basis**, one (rank, mean_monetary) pair per
    populated segment, NOT per-customer.

    Returns ``None`` when fewer than 2 segments are populated (rank
    correlation undefined).

    Note: higher segment-rank-number = lower LTV in
    ``SEGMENT_LTV_RANK_ORDER``. Spearman is sign-flipped so that
    positive correlation = correct ordering (higher-LTV segments have
    higher mean monetary).
    """

    if len(segment_assignments) < 2:
        return None

    df = pd.DataFrame(
        {
            "segment": segment_assignments.values,
            "monetary": pd.to_numeric(monetary_per_customer, errors="coerce").values,
        }
    )
    df = df.dropna(subset=["segment", "monetary"])
    if df.empty:
        return None
    df["segment_rank"] = df["segment"].map(_SEGMENT_RANK)
    df = df.dropna(subset=["segment_rank"])
    if df.empty:
        return None

    # Aggregate to mean monetary per segment.
    by_segment = df.groupby("segment").agg(
        segment_rank=("segment_rank", "first"),
        mean_monetary=("monetary", "mean"),
    )

    if len(by_segment) < 2:
        return None
    if by_segment["mean_monetary"].nunique() < 2:
        return None

    from scipy.stats import spearmanr  # local import

    # Sign-flip: segment_rank ascends as LTV descends; monetary descends
    # for correct ordering → negative Spearman; negate so positive =
    # correct ordering.
    rho, _p = spearmanr(
        by_segment["segment_rank"].values, by_segment["mean_monetary"].values
    )
    if rho is None or not np.isfinite(rho):
        return None
    return float(-rho)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fit_rfm(
    transactions_df: pd.DataFrame,
    profile: Any,
    *,
    store_id: str = "",
    data_dir: Optional[Path] = None,
    seed: int = 0,
    yaml_path: Optional[Path] = None,
) -> ModelCard:
    """Fit deterministic RFM segmentation and return a typed ``ModelCard``.

    Arguments:

    - ``transactions_df``: schema ``customer_id``, ``order_date``,
      plus one of ``total`` / ``revenue`` / ``amount`` / ``order_total``
      (monetary column). Other columns ignored.
    - ``profile``: ``StoreProfile`` (for stage-keyed threshold lookup).

    **RFM is INDEPENDENT of BG/NBD.** No ``bgnbd_model_card`` argument.
    No chained refusal. RFM fits on its own regardless of BG/NBD
    status. This is a deliberate architectural divergence from
    ``fit_survival`` (per DS S12 plan review §F).

    Flow:

    1. **INSUFFICIENT_DATA gate.** Below the absolute customers floor
       (50, DS-locked) OR below stage-keyed ``n_customers_validated``
       floor for VALIDATED — see four-state classifier below — but
       NEVER below absolute_customers_floor → INSUFFICIENT_DATA. No
       segmentation. No parquet.
    2. Compute per-customer R/F/M raw values (recency_days, frequency,
       monetary) using snapshot = max(order_date).
    3. ``pd.qcut`` each dimension to 5 quintiles (R reversed so
       lowest-recency-days = R5). Tie-collapse handled via
       rank-then-bin + duplicate-drop.
    4. Map (R, F, M) tuple to named segment (11 named buckets).
    5. Compute ``segment_monotonicity_spearman`` (signed for "higher
       LTV → higher monetary") and ``quintile_coverage_min``.
    6. Four-state classifier per DS thresholds.
    7. Parquet write only for VALIDATED/PROVISIONAL.

    Returns the ModelCard. The caller (S13 audience-builder) decides
    whether the fit status permits consumption.
    """

    thresholds_full = _load_model_fit_thresholds(profile, yaml_path=yaml_path)
    rfm_thr = thresholds_full["rfm"]
    relax = thresholds_full["rfm_relaxation_factors"]
    guards = thresholds_full["rfm_guards"]

    n_customers_validated = rfm_thr["n_customers_validated"]
    spearman_validated = rfm_thr["segment_monotonicity_spearman_validated"]
    coverage_validated = rfm_thr["quintile_coverage_min_validated"]
    provisional_spearman_floor = relax["provisional_segment_monotonicity_spearman_floor"]
    provisional_coverage_floor = relax["provisional_quintile_coverage_min_floor"]
    absolute_customers_floor = guards["absolute_customers_floor"]
    refused_coverage = guards["refused_quintile_coverage_min"]

    # Training-window days for ModelCard reporting.
    training_window_days = (
        int(
            (
                pd.to_datetime(transactions_df["order_date"]).max()
                - pd.to_datetime(transactions_df["order_date"]).min()
            ).days
        )
        if (not transactions_df.empty and "order_date" in transactions_df.columns)
        else 0
    )

    # ---- Step 1: INSUFFICIENT_DATA gate ----------------------------------
    # NOTE: NO chained refusal on BG/NBD. RFM is independent (DS-locked).
    monetary_col = _resolve_monetary_column(transactions_df)
    if (
        transactions_df.empty
        or monetary_col is None
        or "customer_id" not in transactions_df.columns
        or "order_date" not in transactions_df.columns
    ):
        return ModelCard(
            model_name="rfm",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            parameters={},
            training_window_days=training_window_days,
            n_observed=0,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
            # S-FE-rfm-segment-distribution (L-EV-15/17): RULE-A typed
            # absence. The segmentation did not clear the inferential gate
            # (REFUSED / INSUFFICIENT_DATA) — RFM has no descriptive twin,
            # so it suppresses as a unit (None bands + paired reason), never
            # a fabricated/partial distribution.
            segment_distribution=None,
            segment_distribution_suppression_reason=(
                RfmSegmentDistributionSuppressionReason.FIT_NOT_VALIDATED
            ),
        )

    n_customers = int(transactions_df["customer_id"].nunique())
    if n_customers < absolute_customers_floor:
        return ModelCard(
            model_name="rfm",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            parameters={},
            training_window_days=training_window_days,
            n_observed=n_customers,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
            # S-FE-rfm-segment-distribution (L-EV-15/17): RULE-A typed
            # absence. The segmentation did not clear the inferential gate
            # (REFUSED / INSUFFICIENT_DATA) — RFM has no descriptive twin,
            # so it suppresses as a unit (None bands + paired reason), never
            # a fabricated/partial distribution.
            segment_distribution=None,
            segment_distribution_suppression_reason=(
                RfmSegmentDistributionSuppressionReason.FIT_NOT_VALIDATED
            ),
        )

    # ---- Step 2: per-customer R/F/M ---------------------------------------
    snapshot_date = pd.to_datetime(transactions_df["order_date"]).max()
    try:
        rfm_table = _compute_rfm_table(
            transactions_df, snapshot_date=snapshot_date, monetary_col=monetary_col
        )
    except Exception as exc:  # noqa: BLE001
        return ModelCard(
            model_name="rfm",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=[f"rfm_table_failed:{type(exc).__name__}"],
            parameters={},
            training_window_days=training_window_days,
            n_observed=n_customers,
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
            # S-FE-rfm-segment-distribution (L-EV-15/17): RULE-A typed
            # absence. The segmentation did not clear the inferential gate
            # (REFUSED / INSUFFICIENT_DATA) — RFM has no descriptive twin,
            # so it suppresses as a unit (None bands + paired reason), never
            # a fabricated/partial distribution.
            segment_distribution=None,
            segment_distribution_suppression_reason=(
                RfmSegmentDistributionSuppressionReason.FIT_NOT_VALIDATED
            ),
        )

    if len(rfm_table) < absolute_customers_floor:
        return ModelCard(
            model_name="rfm",
            fit_status=ModelFitStatus.INSUFFICIENT_DATA,
            fit_warnings=[],
            parameters={},
            training_window_days=training_window_days,
            n_observed=int(len(rfm_table)),
            metrics={},
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
            # S-FE-rfm-segment-distribution (L-EV-15/17): RULE-A typed
            # absence. The segmentation did not clear the inferential gate
            # (REFUSED / INSUFFICIENT_DATA) — RFM has no descriptive twin,
            # so it suppresses as a unit (None bands + paired reason), never
            # a fabricated/partial distribution.
            segment_distribution=None,
            segment_distribution_suppression_reason=(
                RfmSegmentDistributionSuppressionReason.FIT_NOT_VALIDATED
            ),
        )

    # ---- Step 3: quintile scoring -----------------------------------------
    # R reversed: lowest recency_days = highest R-quintile.
    rfm_table["r_quintile"] = _safe_qcut(rfm_table["recency_days"], q=5, reverse=True)
    rfm_table["f_quintile"] = _safe_qcut(rfm_table["frequency"], q=5, reverse=False)
    rfm_table["m_quintile"] = _safe_qcut(rfm_table["monetary"], q=5, reverse=False)

    # ---- Step 4: named-segment mapping ------------------------------------
    rfm_table["segment_name"] = rfm_table.apply(
        lambda row: _assign_segment(
            int(row["r_quintile"]), int(row["f_quintile"]), int(row["m_quintile"])
        ),
        axis=1,
    )

    # ---- Step 5: metrics --------------------------------------------------
    coverage_min = _quintile_coverage_min(
        rfm_table["r_quintile"], rfm_table["f_quintile"], rfm_table["m_quintile"]
    )

    spearman = _segment_monotonicity_spearman(
        rfm_table["segment_name"], rfm_table["monetary"]
    )

    # ---- Step 6: classify -------------------------------------------------
    # REFUSED guard on quintile collapse (secondary).
    if coverage_min < refused_coverage:
        return ModelCard(
            model_name="rfm",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=["quintile_collapse"],
            parameters={
                "n_customers": float(len(rfm_table)),
            },
            training_window_days=training_window_days,
            n_observed=int(len(rfm_table)),
            metrics={
                "segment_monotonicity_spearman": spearman,
                "quintile_coverage_min": coverage_min,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
            # S-FE-rfm-segment-distribution (L-EV-15/17): RULE-A typed
            # absence. The segmentation did not clear the inferential gate
            # (REFUSED / INSUFFICIENT_DATA) — RFM has no descriptive twin,
            # so it suppresses as a unit (None bands + paired reason), never
            # a fabricated/partial distribution.
            segment_distribution=None,
            segment_distribution_suppression_reason=(
                RfmSegmentDistributionSuppressionReason.FIT_NOT_VALIDATED
            ),
        )

    if spearman is None or not np.isfinite(spearman):
        return ModelCard(
            model_name="rfm",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=["spearman_unmeasurable"],
            parameters={
                "n_customers": float(len(rfm_table)),
            },
            training_window_days=training_window_days,
            n_observed=int(len(rfm_table)),
            metrics={
                "segment_monotonicity_spearman": spearman,
                "quintile_coverage_min": coverage_min,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
            # S-FE-rfm-segment-distribution (L-EV-15/17): RULE-A typed
            # absence. The segmentation did not clear the inferential gate
            # (REFUSED / INSUFFICIENT_DATA) — RFM has no descriptive twin,
            # so it suppresses as a unit (None bands + paired reason), never
            # a fabricated/partial distribution.
            segment_distribution=None,
            segment_distribution_suppression_reason=(
                RfmSegmentDistributionSuppressionReason.FIT_NOT_VALIDATED
            ),
        )

    if spearman < provisional_spearman_floor:
        return ModelCard(
            model_name="rfm",
            fit_status=ModelFitStatus.REFUSED,
            fit_warnings=["segment_monotonicity_below_floor"],
            parameters={
                "n_customers": float(len(rfm_table)),
            },
            training_window_days=training_window_days,
            n_observed=int(len(rfm_table)),
            metrics={
                "segment_monotonicity_spearman": spearman,
                "quintile_coverage_min": coverage_min,
            },
            fit_timestamp=_now_iso(),
            parquet_schema_version=1,
            # S-FE-rfm-segment-distribution (L-EV-15/17): RULE-A typed
            # absence. The segmentation did not clear the inferential gate
            # (REFUSED / INSUFFICIENT_DATA) — RFM has no descriptive twin,
            # so it suppresses as a unit (None bands + paired reason), never
            # a fabricated/partial distribution.
            segment_distribution=None,
            segment_distribution_suppression_reason=(
                RfmSegmentDistributionSuppressionReason.FIT_NOT_VALIDATED
            ),
        )

    # VALIDATED requires BOTH thresholds: spearman + coverage + n_customers.
    is_validated = (
        spearman >= spearman_validated
        and coverage_min >= coverage_validated
        and len(rfm_table) >= n_customers_validated
    )
    status = ModelFitStatus.VALIDATED if is_validated else ModelFitStatus.PROVISIONAL

    parameters: Dict[str, float] = {
        "n_customers": float(len(rfm_table)),
        "n_segments_observed": float(rfm_table["segment_name"].nunique()),
    }

    # S-FE-rfm-segment-distribution (L-EV-17): populate the aggregate bands
    # ONLY on VALIDATED / PROVISIONAL (the segmentation cleared its
    # inferential gate). RFM has no descriptive twin — on the suppressed
    # branches above the card carries None + FIT_NOT_VALIDATED instead.
    segment_distribution = _compute_segment_distribution(rfm_table["segment_name"])

    card = ModelCard(
        model_name="rfm",
        fit_status=status,
        fit_warnings=[],
        parameters=parameters,
        training_window_days=training_window_days,
        n_observed=int(len(rfm_table)),
        metrics={
            "segment_monotonicity_spearman": spearman,
            "quintile_coverage_min": coverage_min,
        },
        fit_timestamp=_now_iso(),
        parquet_schema_version=1,
        segment_distribution=segment_distribution,
        segment_distribution_suppression_reason=None,
    )

    # ---- Step 7: write parquet (VALIDATED / PROVISIONAL only) ------------
    if data_dir is not None and store_id:
        _write_rfm_parquet(
            rfm_table=rfm_table,
            data_dir=Path(data_dir),
            store_id=store_id,
        )

    return card


def _compute_segment_distribution(segment_name: pd.Series) -> List[SegmentBand]:
    """Aggregate the per-customer ``segment_name`` series into typed bands.

    S-FE-rfm-segment-distribution (L-EV-17). AGGREGATE-ONLY + DESCRIPTIVE:
    each band carries ``{segment_name, n, share}`` — the observed count and
    its fraction of the analyzed customer base. NO per-customer rows, NO
    monetary magnitude (the per-customer monetary that drove the quintiles
    is deliberately not surfaced here — L-EV-17/20).

    Ordering convention: ``n`` DESCENDING, ties broken by canonical LTV
    rank (:data:`SEGMENT_LTV_RANK_ORDER`; Champions first) for stable,
    deterministic output across runs. ``share = n / total`` where
    ``total = len(segment_name)`` (the analyzed base); shares sum to ~1.0
    (float rounding). Only segments actually observed produce a band
    (``<= 11``); a zero-count segment is omitted, never emitted as ``n=0``.
    """

    counts = segment_name.value_counts()
    total = int(counts.sum())
    if total <= 0:
        return []

    bands = [
        SegmentBand(
            segment_name=str(name),
            n=int(n),
            share=float(n) / float(total),
        )
        for name, n in counts.items()
    ]
    # Stable canonical sort: n descending, then LTV rank ascending
    # (unknown names sort last via a large sentinel rank).
    bands.sort(
        key=lambda b: (-b.n, _SEGMENT_RANK.get(b.segment_name, len(SEGMENT_LTV_RANK_ORDER) + 1))
    )
    return bands


def _write_rfm_parquet(
    *,
    rfm_table: pd.DataFrame,
    data_dir: Path,
    store_id: str,
) -> Path:
    """Write per-customer RFM assignment to parquet.

    Schema (parquet_schema_version=1):

    - ``customer_id``: str
    - ``r_quintile``: int (1..5; 5 = most recent)
    - ``f_quintile``: int (1..5; 5 = highest frequency)
    - ``m_quintile``: int (1..5; 5 = highest monetary)
    - ``segment_name``: str (one of the 11 named segments)
    - ``parquet_schema_version``: int (constant 1)
    """

    out = pd.DataFrame(
        {
            "customer_id": rfm_table["customer_id"].astype(str),
            "r_quintile": rfm_table["r_quintile"].astype(int),
            "f_quintile": rfm_table["f_quintile"].astype(int),
            "m_quintile": rfm_table["m_quintile"].astype(int),
            "segment_name": rfm_table["segment_name"].astype(str),
            "parquet_schema_version": 1,
        }
    )
    out_dir = data_dir / store_id / "predictive"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "rfm.parquet"
    out.to_parquet(target, index=False)
    return target


__all__ = ["fit_rfm", "SEGMENT_LTV_RANK_ORDER"]
