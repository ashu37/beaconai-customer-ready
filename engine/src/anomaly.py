"""Anomalous-window detectors (Milestone 1, T1.2).

Five pure-function detectors that scan an order-level dataframe around an
``anchor_date`` and surface ``DataQualityFlag`` codes:

- ``bfcm_overlap``
- ``post_promo_window``
- ``refund_storm``
- ``test_order_anomaly``
- ``insufficient_clean_history``

The combiner ``detect_anomalous_windows`` returns the deduplicated list of
flags. These detectors are pure functions; they do not mutate inputs and
do not write any artifact. M1 surfaces flags in receipts only — gating is
M5 (``ANOMALY_GATE_ENABLED``).

Thresholds live in ``config/anomaly_thresholds.yaml``. Defaults are
conservative; the gates being OFF in M1 means even a fired flag does not
abstain or change merchant output. M5 will tune.

Inputs:
- ``df``: an order-level pandas DataFrame. Expected columns (best-effort):
  ``Created at`` (datetime-like), ``Total`` or ``Subtotal`` (numeric),
  ``Financial Status`` (str), ``Cancelled at`` (datetime-like or NaT),
  ``Name`` (order id), ``customer_id`` (or ``Customer Email``).
- ``anchor_date``: pandas-coercible date marking the end of the analysis
  window. Typically the engine's anchor (max ``Created at``).

Outputs:
- ``list[DataQualityFlag]``: zero or more flags. Order is deterministic
  (sorted by enum value).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd
import yaml

from .engine_run import DataQualityFlag


_THRESHOLDS_PATH = Path(__file__).resolve().parent.parent / "config" / "anomaly_thresholds.yaml"


def load_anomaly_thresholds(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load detector thresholds from YAML. Cached only at the call site."""
    p = Path(path) if path is not None else _THRESHOLDS_PATH
    if not p.exists():
        return {}
    try:
        return yaml.safe_load(p.read_text()) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_ts(x: Any) -> Optional[pd.Timestamp]:
    if x is None:
        return None
    try:
        ts = pd.to_datetime(x, errors="coerce")
        if pd.isna(ts):
            return None
        # Strip timezone for arithmetic safety.
        try:
            ts = ts.tz_localize(None) if ts.tzinfo else ts
        except (AttributeError, TypeError):
            pass
        return pd.Timestamp(ts)
    except Exception:
        return None


def _window_bounds(
    anchor: pd.Timestamp, window_days: int
) -> tuple[pd.Timestamp, pd.Timestamp]:
    end = anchor.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
    start = end.normalize() - pd.Timedelta(days=int(window_days) - 1)
    return start, end


def _slice_window(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if df is None or df.empty or "Created at" not in df.columns:
        return df.iloc[0:0] if df is not None else pd.DataFrame()
    ts = pd.to_datetime(df["Created at"], errors="coerce")
    try:
        ts = ts.dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    mask = (ts >= start) & (ts <= end)
    return df.loc[mask]


def _us_cyber_monday(year: int) -> pd.Timestamp:
    """US Cyber Monday: Monday after the 4th Thursday of November."""
    # First Thursday in November.
    nov1 = date(year, 11, 1)
    # weekday(): Mon=0..Sun=6; Thu=3.
    offset_to_first_thu = (3 - nov1.weekday()) % 7
    first_thu = pd.Timestamp(nov1) + pd.Timedelta(days=offset_to_first_thu)
    fourth_thu = first_thu + pd.Timedelta(weeks=3)
    cyber_monday = fourth_thu + pd.Timedelta(days=4)
    return cyber_monday.normalize()


# ---------------------------------------------------------------------------
# Detectors (pure functions; each returns 0 or 1 flag)
# ---------------------------------------------------------------------------


def detect_bfcm_overlap(
    df: pd.DataFrame, anchor_date: Any, thresholds: Dict[str, Any]
) -> Optional[DataQualityFlag]:
    """Fire when analysis window overlaps a BFCM week."""
    cfg = (thresholds or {}).get("bfcm_overlap") or {}
    if not cfg.get("enabled", True):
        return None
    anchor = _to_ts(anchor_date)
    if anchor is None:
        return None
    window_days = int((thresholds or {}).get("analysis_window_days", 28))
    radius = int(cfg.get("bfcm_radius_days", 7))
    min_overlap = int(cfg.get("min_overlap_days", 1))

    start, end = _window_bounds(anchor, window_days)
    # Consider all candidate years that the analysis window touches.
    years: Set[int] = {start.year, end.year}
    for y in years:
        cm = _us_cyber_monday(int(y))
        bfcm_start = (cm - pd.Timedelta(days=radius)).normalize()
        bfcm_end = (cm + pd.Timedelta(hours=23, minutes=59, seconds=59))
        # Overlap days, inclusive.
        overlap_start = max(start, bfcm_start)
        overlap_end = min(end, bfcm_end)
        if overlap_start <= overlap_end:
            overlap_days = (overlap_end.normalize() - overlap_start.normalize()).days + 1
            if overlap_days >= min_overlap:
                return DataQualityFlag.BFCM_OVERLAP
    return None


def detect_post_promo_window(
    df: pd.DataFrame, anchor_date: Any, thresholds: Dict[str, Any]
) -> Optional[DataQualityFlag]:
    """Fire when anchor sits in the N-day post-BFCM cooldown window.

    Distinct from ``bfcm_overlap``: this detector triggers AFTER BFCM,
    when the analysis window itself does not contain BFCM but is within
    ``post_window_days`` of it.
    """
    cfg = (thresholds or {}).get("post_promo_window") or {}
    if not cfg.get("enabled", True):
        return None
    anchor = _to_ts(anchor_date)
    if anchor is None:
        return None
    post_window = int(cfg.get("post_window_days", 14))
    radius = int(((thresholds or {}).get("bfcm_overlap") or {}).get("bfcm_radius_days", 7))

    # Did the analysis window itself overlap BFCM? If yes, this detector
    # defers to bfcm_overlap and does not also fire.
    if detect_bfcm_overlap(df, anchor_date, thresholds) is not None:
        return None

    for y in {anchor.year - 1, anchor.year}:
        cm = _us_cyber_monday(int(y))
        bfcm_end = (cm + pd.Timedelta(hours=23, minutes=59, seconds=59)).normalize()
        post_end = (bfcm_end + pd.Timedelta(days=post_window)).normalize()
        # If anchor is strictly after BFCM but inside the post window, fire.
        if (anchor.normalize() > bfcm_end) and (anchor.normalize() <= post_end):
            return DataQualityFlag.POST_PROMO_WINDOW
    # Also handle the BFCM-radius "shoulder" case where the window's start
    # is outside but its end is just past BFCM end + post_window.
    return None


def _refund_mask(df: pd.DataFrame) -> pd.Series:
    """Return a boolean mask for rows that look like refunds/cancellations."""
    if df is None or df.empty:
        return pd.Series(dtype=bool)
    mask = pd.Series(False, index=df.index)
    if "Financial Status" in df.columns:
        fs = df["Financial Status"].astype(str).str.lower()
        mask = mask | fs.str.contains("refund|chargeback|partially_refunded", regex=True, na=False)
    if "Cancelled at" in df.columns:
        cancelled = pd.to_datetime(df["Cancelled at"], errors="coerce").notna()
        mask = mask | cancelled
    return mask


def detect_refund_storm(
    df: pd.DataFrame, anchor_date: Any, thresholds: Dict[str, Any]
) -> Optional[DataQualityFlag]:
    """Fire when refund rate within the window is anomalously high."""
    cfg = (thresholds or {}).get("refund_storm") or {}
    if not cfg.get("enabled", True):
        return None
    if df is None or df.empty:
        return None
    anchor = _to_ts(anchor_date)
    if anchor is None:
        return None
    window_days = int((thresholds or {}).get("analysis_window_days", 28))

    multiplier = float(cfg.get("multiplier_over_baseline", 3.0))
    min_refunds = int(cfg.get("min_refunds", 5))
    abs_floor = float(cfg.get("absolute_rate_floor", 0.10))

    start, end = _window_bounds(anchor, window_days)
    in_window = _slice_window(df, start, end)
    prior_start = start - pd.Timedelta(days=window_days)
    prior_end = start - pd.Timedelta(seconds=1)
    in_prior = _slice_window(df, prior_start, prior_end)

    if len(in_window) == 0:
        return None
    cur_refunds = int(_refund_mask(in_window).sum())
    cur_rate = cur_refunds / max(1, len(in_window))
    prior_refunds = int(_refund_mask(in_prior).sum()) if len(in_prior) else 0
    prior_rate = prior_refunds / max(1, len(in_prior)) if len(in_prior) else 0.0

    # Absolute backstop.
    if cur_refunds >= min_refunds and cur_rate >= abs_floor:
        return DataQualityFlag.REFUND_STORM
    # Multiplier vs baseline (require non-trivial baseline + min refunds).
    if (
        cur_refunds >= min_refunds
        and prior_rate > 0
        and cur_rate >= multiplier * prior_rate
    ):
        return DataQualityFlag.REFUND_STORM
    return None


def detect_test_order_anomaly(
    df: pd.DataFrame, anchor_date: Any, thresholds: Dict[str, Any]
) -> Optional[DataQualityFlag]:
    """Fire when zero-value or single-customer concentration exceeds limits."""
    cfg = (thresholds or {}).get("test_order_anomaly") or {}
    if not cfg.get("enabled", True):
        return None
    if df is None or df.empty:
        return None
    anchor = _to_ts(anchor_date)
    if anchor is None:
        return None
    window_days = int((thresholds or {}).get("analysis_window_days", 28))
    start, end = _window_bounds(anchor, window_days)
    w = _slice_window(df, start, end)
    if len(w) == 0:
        return None

    zero_pct_threshold = float(cfg.get("zero_value_order_pct", 0.02))
    concentration_threshold = float(cfg.get("single_customer_concentration", 0.30))

    # Zero-value detection: prefer Total, fall back to Subtotal.
    value_col = None
    for c in ("Total", "Subtotal"):
        if c in w.columns:
            value_col = c
            break
    if value_col is not None:
        v = pd.to_numeric(w[value_col], errors="coerce").fillna(-1.0)
        zero_pct = float((v == 0).mean())
        if zero_pct >= zero_pct_threshold:
            return DataQualityFlag.TEST_ORDER_ANOMALY

    # Single-customer concentration.
    cust_col = None
    for c in ("customer_id", "Customer Email", "Email", "Customer ID"):
        if c in w.columns:
            cust_col = c
            break
    if cust_col is not None:
        s = w[cust_col].astype(str).str.lower().str.strip()
        s = s[s.notna() & (s != "") & (s != "nan")]
        if len(s) >= 5:
            top_share = float(s.value_counts(normalize=True).iloc[0]) if len(s) else 0.0
            if top_share >= concentration_threshold:
                return DataQualityFlag.TEST_ORDER_ANOMALY
    return None


def detect_insufficient_clean_history(
    df: pd.DataFrame, anchor_date: Any, thresholds: Dict[str, Any]
) -> Optional[DataQualityFlag]:
    """Fire when there is not enough pre-anchor history to support analysis."""
    cfg = (thresholds or {}).get("insufficient_clean_history") or {}
    if not cfg.get("enabled", True):
        return None
    if df is None or df.empty or "Created at" not in df.columns:
        return DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY
    anchor = _to_ts(anchor_date)
    if anchor is None:
        return None
    min_days = int(cfg.get("min_clean_days", 60))
    min_orders = int(cfg.get("min_clean_orders", 50))

    ts = pd.to_datetime(df["Created at"], errors="coerce")
    try:
        ts = ts.dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    valid = ts.dropna()
    if valid.empty:
        return DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY
    earliest = valid.min()
    days_of_history = max(0, (anchor.normalize() - earliest.normalize()).days)
    n_orders = int(len(valid))
    if days_of_history < min_days or n_orders < min_orders:
        return DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY
    return None


def detect_promo_spike(
    df: pd.DataFrame, anchor_date: Any, thresholds: Dict[str, Any]
) -> Optional[DataQualityFlag]:
    """B-1: fire when the analysis window contains a promo-shaped spike.

    Compares total revenue inside the ``window_days`` (default 56) ending
    at ``anchor_date`` against the immediately-prior equally-sized period.
    Fires :data:`DataQualityFlag.POST_PROMO_WINDOW` when:

    1. Prior period has at least ``min_prior_orders`` orders AND covers at
       least ``min_prior_days_covered`` days (so the baseline is credible).
    2. Window revenue >= ``multiplier_over_baseline`` x prior revenue.

    POST_PROMO_WINDOW is reused (rather than minting a new enum value) so
    the existing typed slot, reason-code mapping, and renderer wiring all
    work without contract changes. Routing in ``apply_guardrails``
    distinguishes hard flags (ABSTAIN_HARD) from POST_PROMO_WINDOW
    (ABSTAIN_SOFT) at the gate seam, not here.
    """
    cfg = (thresholds or {}).get("promo_spike") or {}
    if not cfg.get("enabled", True):
        return None
    if df is None or df.empty or "Created at" not in df.columns:
        return None
    anchor = _to_ts(anchor_date)
    if anchor is None:
        return None

    window_days = int(cfg.get("window_days", 56))
    multiplier = float(cfg.get("multiplier_over_baseline", 2.0))
    min_prior_orders = int(cfg.get("min_prior_orders", 50))
    min_prior_days_covered = int(cfg.get("min_prior_days_covered", 28))

    start, end = _window_bounds(anchor, window_days)
    in_window = _slice_window(df, start, end)
    prior_start = start - pd.Timedelta(days=window_days)
    prior_end = start - pd.Timedelta(seconds=1)
    in_prior = _slice_window(df, prior_start, prior_end)

    # Credibility guard on the baseline.
    if len(in_prior) < min_prior_orders:
        return None
    prior_ts = pd.to_datetime(in_prior["Created at"], errors="coerce").dropna()
    if prior_ts.empty:
        return None
    prior_days = max(0, (prior_ts.max().normalize() - prior_ts.min().normalize()).days + 1)
    if prior_days < min_prior_days_covered:
        return None

    # Revenue ratio. Prefer Total, fall back to Subtotal.
    value_col = None
    for c in ("Total", "Subtotal"):
        if c in df.columns:
            value_col = c
            break
    if value_col is None:
        return None
    win_rev = float(pd.to_numeric(in_window[value_col], errors="coerce").fillna(0.0).sum())
    prior_rev = float(pd.to_numeric(in_prior[value_col], errors="coerce").fillna(0.0).sum())
    if prior_rev <= 0:
        return None
    if win_rev >= multiplier * prior_rev:
        return DataQualityFlag.POST_PROMO_WINDOW
    return None


# ---------------------------------------------------------------------------
# Combiner
# ---------------------------------------------------------------------------


_DETECTORS = (
    detect_bfcm_overlap,
    detect_post_promo_window,
    detect_refund_storm,
    detect_test_order_anomaly,
    detect_insufficient_clean_history,
    detect_promo_spike,
)


def detect_anomalous_windows(
    df: pd.DataFrame,
    anchor_date: Any,
    thresholds: Optional[Dict[str, Any]] = None,
) -> List[DataQualityFlag]:
    """Run all detectors. Return a deterministic, deduplicated list of flags.

    M1: result is surfaced in ``EngineRun.data_quality_flags``. Receipts
    only — no merchant-facing output is changed.
    """
    th = thresholds if thresholds is not None else load_anomaly_thresholds()
    found: Set[DataQualityFlag] = set()
    for detector in _DETECTORS:
        try:
            flag = detector(df, anchor_date, th)
        except Exception:
            # Detectors are best-effort and must not crash the engine.
            flag = None
        if flag is not None:
            found.add(flag)
    return sorted(found, key=lambda f: f.value)
