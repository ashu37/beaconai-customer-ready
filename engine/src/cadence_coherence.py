"""Customer-level reorder-cadence coherence check.

Sprint 5 Ticket S5-T3 (resolves KI-22). The supplements vertical
already logs ``Repeat rate 0% suspiciously low ...`` via
``src.validation.MetricConsistencyCheck`` to stdout, but that advisory
never reaches the typed ``engine_run.json::data_quality_flags`` slot.
On stores where the typical customer reorder gap exceeds the active
primary-window (L28), the within-window ``repeat_rate_within_window``
metric is structurally misleading — the merchant has no signal that
the watching row is unreliable.

This module is intentionally small, isolated, and pure. It does NOT
read or write any other engine module; it consumes the orders
DataFrame already in scope at ``src.main.run`` and returns a
boolean + diagnostic float. The threshold heuristic — median
customer-level reorder gap > ``threshold_ratio * window_days`` (default
0.8) — is pinned here as the single source of truth so the test can
import the constant rather than re-deriving it.

Founder choice for this ticket (per plan §11 lines 602-608): when the
flag fires, the engine SUPPRESSES the misleading
``repeat_rate_within_window`` Watching row (caller does the suppression
on ``engine_run.watching``; this module only computes the gate).
"""

from __future__ import annotations

from typing import Optional, Tuple

#: Heuristic ratio. Median customer reorder gap > ``DEFAULT_THRESHOLD_RATIO
#: * window_days`` ⇒ cadence exceeds window. Pinned in
#: ``tests/test_s5_t3_cadence_coherence.py``; do NOT scatter this
#: magic number across modules.
DEFAULT_THRESHOLD_RATIO: float = 0.8


def compute_median_customer_reorder_gap_days(orders_df) -> Optional[float]:
    """Median gap in days between consecutive orders, per customer,
    aggregated across customers.

    Returns ``None`` when the dataframe is empty, lacks the required
    columns, or no customer has ≥2 orders (so no gap is defined).
    Pure function: never raises on shape problems — returns ``None``
    instead so the caller can fail-open.
    """

    try:
        import pandas as pd  # local import keeps this module test-friendly
    except Exception:
        return None

    if orders_df is None:
        return None
    try:
        if not hasattr(orders_df, "columns"):
            return None
        if "customer_id" not in orders_df.columns:
            return None
        if "Created at" not in orders_df.columns:
            return None
        df = orders_df[["customer_id", "Created at"]].copy()
        df["Created at"] = pd.to_datetime(df["Created at"], errors="coerce")
        df = df.dropna(subset=["customer_id", "Created at"])
        if df.empty:
            return None
        df = df.sort_values(["customer_id", "Created at"])
        # Per-customer consecutive diffs in days.
        diffs = (
            df.groupby("customer_id")["Created at"]
            .diff()
            .dt.days
            .dropna()
        )
        if diffs.empty:
            return None
        return float(diffs.median())
    except Exception:
        return None


def cadence_exceeds_window(
    median_gap_days: Optional[float],
    window_days: Optional[int],
    *,
    threshold_ratio: float = DEFAULT_THRESHOLD_RATIO,
) -> bool:
    """Return ``True`` iff ``median_gap_days > threshold_ratio *
    window_days``. Returns ``False`` on missing inputs (fail-closed:
    we'd rather under-flag than spurious-flag).
    """

    if median_gap_days is None or window_days is None:
        return False
    try:
        wd = float(window_days)
        mg = float(median_gap_days)
    except (TypeError, ValueError):
        return False
    if wd <= 0:
        return False
    return mg > threshold_ratio * wd


def evaluate(
    orders_df,
    window_days: Optional[int] = 28,
    *,
    threshold_ratio: float = DEFAULT_THRESHOLD_RATIO,
) -> Tuple[bool, Optional[float]]:
    """Convenience: compute the median gap and the threshold result in
    one call. Returns ``(should_flag, median_gap_days)``."""

    gap = compute_median_customer_reorder_gap_days(orders_df)
    return (
        cadence_exceeds_window(gap, window_days, threshold_ratio=threshold_ratio),
        gap,
    )
