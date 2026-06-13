"""B-1 — unit tests for the new ``detect_promo_spike`` detector.

Calibration constraints (must hold or B-1 is not defensible):

- Beauty pinned fixture (``healthy_beauty_240d``): L56 ratio = 1.17 → does
  NOT fire. Verified indirectly by the M0 byte-identical golden.
- ``promo_anomaly_240d``: L56 ratio = 2.28 → fires POST_PROMO_WINDOW.
  Covered by the end-to-end acceptance in ``test_b1_anomaly_auto_register``.
- Other healthy fixtures all carry L56 ratio < 1.5.

The unit tests here exercise the detector against synthesized order
DataFrames so the threshold logic is testable in isolation from the
fixture pipeline.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.anomaly import detect_promo_spike  # noqa: E402
from src.engine_run import DataQualityFlag  # noqa: E402


def _build_orders(start: str, end: str, daily_revenue: float, daily_orders: int = 5) -> pd.DataFrame:
    """Synthesize a uniform order stream between ``start`` and ``end``."""
    dates = pd.date_range(start=start, end=end, freq="D")
    rows = []
    for d in dates:
        for _ in range(daily_orders):
            rows.append(
                {
                    "Created at": d,
                    "Total": float(daily_revenue) / max(1, daily_orders),
                    "Financial Status": "paid",
                }
            )
    return pd.DataFrame(rows)


def test_detector_fires_on_2x_window_revenue_ratio():
    """Window revenue 2x prior period → POST_PROMO_WINDOW."""
    # Prior 56 days at $1000/day; window 56 days at $2500/day → ratio 2.5x.
    prior = _build_orders("2025-05-01", "2025-06-25", daily_revenue=1000.0)
    window = _build_orders("2025-06-26", "2025-08-20", daily_revenue=2500.0)
    df = pd.concat([prior, window], ignore_index=True)
    flag = detect_promo_spike(df, anchor_date="2025-08-20", thresholds={
        "promo_spike": {"enabled": True, "window_days": 56, "multiplier_over_baseline": 2.0,
                         "min_prior_orders": 50, "min_prior_days_covered": 28}
    })
    assert flag == DataQualityFlag.POST_PROMO_WINDOW


def test_detector_silent_on_flat_revenue():
    """Flat revenue across both periods must NOT fire."""
    prior = _build_orders("2025-05-01", "2025-06-25", daily_revenue=1000.0)
    window = _build_orders("2025-06-26", "2025-08-20", daily_revenue=1000.0)
    df = pd.concat([prior, window], ignore_index=True)
    flag = detect_promo_spike(df, anchor_date="2025-08-20", thresholds={
        "promo_spike": {"enabled": True, "window_days": 56, "multiplier_over_baseline": 2.0,
                         "min_prior_orders": 50, "min_prior_days_covered": 28}
    })
    assert flag is None


def test_detector_silent_when_prior_period_has_no_credible_baseline():
    """Cold-start-shaped data (prior period empty) must NOT trigger
    a divide-by-zero-shaped false positive. The credibility guard on
    ``min_prior_orders`` / ``min_prior_days_covered`` must short-circuit.
    """
    # No prior, only window.
    window = _build_orders("2025-06-26", "2025-08-20", daily_revenue=5000.0)
    flag = detect_promo_spike(window, anchor_date="2025-08-20", thresholds={
        "promo_spike": {"enabled": True, "window_days": 56, "multiplier_over_baseline": 2.0,
                         "min_prior_orders": 50, "min_prior_days_covered": 28}
    })
    assert flag is None


def test_detector_disabled_returns_none():
    """``enabled: false`` must short-circuit even when the ratio is huge."""
    prior = _build_orders("2025-05-01", "2025-06-25", daily_revenue=100.0)
    window = _build_orders("2025-06-26", "2025-08-20", daily_revenue=10000.0)
    df = pd.concat([prior, window], ignore_index=True)
    flag = detect_promo_spike(df, anchor_date="2025-08-20", thresholds={
        "promo_spike": {"enabled": False}
    })
    assert flag is None


def test_detector_silent_on_empty_dataframe():
    """Defensive: empty input must not raise."""
    flag = detect_promo_spike(pd.DataFrame(), anchor_date="2025-08-20", thresholds={})
    assert flag is None
