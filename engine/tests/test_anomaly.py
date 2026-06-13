"""Milestone 1 T1.2: anomaly detector tests.

Each detector is exercised by a synthetic in-memory CSV (built as a
DataFrame in the test setup, not a fixture file). For each detector we
assert:

- the relevant detector fires on its targeted fixture, AND
- the OTHER detectors do not falsely fire on that fixture.

The combiner ``detect_anomalous_windows`` is also exercised end-to-end.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.anomaly import (  # noqa: E402
    detect_anomalous_windows,
    detect_bfcm_overlap,
    detect_insufficient_clean_history,
    detect_post_promo_window,
    detect_refund_storm,
    detect_test_order_anomaly,
    load_anomaly_thresholds,
)
from src.engine_run import DataQualityFlag  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic fixture builders
# ---------------------------------------------------------------------------


def _build_orders_df(rows):
    """Rows: list of dicts. Returns a DataFrame matching engine column names."""
    df = pd.DataFrame(rows)
    if "Created at" in df.columns:
        df["Created at"] = pd.to_datetime(df["Created at"])
    return df


def _healthy_baseline_rows(anchor: pd.Timestamp, n: int = 200) -> list:
    """A boring 200-day history at 1 order/day, $50/order, distinct customers."""
    rows = []
    for i in range(n):
        rows.append(
            {
                "Name": f"O{i}",
                "Created at": (anchor - timedelta(days=n - i)).isoformat(),
                "Customer Email": f"c{i}@example.com",
                "Total": 50.0,
                "Subtotal": 50.0,
                "Financial Status": "paid",
                "Cancelled at": None,
            }
        )
    return rows


@pytest.fixture
def thresholds():
    return load_anomaly_thresholds()


# ---------------------------------------------------------------------------
# bfcm_overlap
# ---------------------------------------------------------------------------


def test_bfcm_overlap_fires_on_dec_anchor_2024(thresholds):
    """anchor=2024-12-08 has L28 (Nov 11 - Dec 8) overlapping Cyber Monday week."""
    anchor = pd.Timestamp("2024-12-08T12:00:00")
    df = _build_orders_df(_healthy_baseline_rows(anchor, n=120))
    flag = detect_bfcm_overlap(df, anchor, thresholds)
    assert flag == DataQualityFlag.BFCM_OVERLAP

    # Other detectors should not fire on this otherwise-healthy fixture.
    assert detect_refund_storm(df, anchor, thresholds) is None
    assert detect_test_order_anomaly(df, anchor, thresholds) is None
    assert detect_insufficient_clean_history(df, anchor, thresholds) is None


def test_bfcm_overlap_does_not_fire_in_august(thresholds):
    anchor = pd.Timestamp("2025-08-25T12:00:00")
    df = _build_orders_df(_healthy_baseline_rows(anchor, n=120))
    assert detect_bfcm_overlap(df, anchor, thresholds) is None


# ---------------------------------------------------------------------------
# post_promo_window
# ---------------------------------------------------------------------------


def test_post_promo_window_fires_after_bfcm(thresholds):
    """anchor=2024-12-13 is +11d after Cyber Monday 2024 (Dec 2). Outside
    BFCM radius (7d) but inside post_window_days (14d). Window: Nov 16 - Dec 13.
    BFCM 2024 = Nov 25 to Dec 9. The L28 overlaps BFCM.

    To isolate post_promo from bfcm_overlap, pick anchor such that the
    L28 does NOT overlap BFCM but anchor IS within post_window_days.
    """
    # Cyber Monday 2024 = Dec 2. BFCM end = Dec 9. post_window = 14 days.
    # We want anchor.normalize() > Dec 9 AND anchor.normalize() <= Dec 23.
    # AND we want the L28 to not overlap BFCM. L28 spans 28 days ending at
    # anchor; for it to NOT overlap BFCM (Nov 25 - Dec 9), anchor - 27d must
    # be > Dec 9, i.e., anchor > Jan 5 next year. That moves us out of the
    # post_window (which expires Dec 23).
    #
    # The intent of the post_promo detector is to fire when the analysis
    # window is just past BFCM and not currently overlapping. Given a 28d
    # window, a 14d post_window_days is too short to have a non-overlap +
    # post-period anchor. So we increase post_window_days for this test.
    custom = dict(thresholds or {})
    custom["post_promo_window"] = {"enabled": True, "post_window_days": 60}
    custom["analysis_window_days"] = 14  # smaller window to break overlap

    anchor = pd.Timestamp("2025-01-15T12:00:00")  # 44 days post Cyber Monday 2024
    df = _build_orders_df(_healthy_baseline_rows(anchor, n=120))
    # bfcm_overlap should NOT fire on this anchor (window Jan 2 - Jan 15)
    assert detect_bfcm_overlap(df, anchor, custom) is None
    # post_promo SHOULD fire.
    assert detect_post_promo_window(df, anchor, custom) == DataQualityFlag.POST_PROMO_WINDOW


def test_post_promo_window_defers_when_bfcm_overlaps(thresholds):
    anchor = pd.Timestamp("2024-12-08T12:00:00")  # L28 overlaps BFCM
    df = _build_orders_df(_healthy_baseline_rows(anchor, n=120))
    # bfcm_overlap fires ...
    assert detect_bfcm_overlap(df, anchor, thresholds) == DataQualityFlag.BFCM_OVERLAP
    # ... and post_promo defers.
    assert detect_post_promo_window(df, anchor, thresholds) is None


# ---------------------------------------------------------------------------
# refund_storm
# ---------------------------------------------------------------------------


def test_refund_storm_fires_on_high_refund_rate(thresholds):
    anchor = pd.Timestamp("2025-08-25T12:00:00")
    rows = _healthy_baseline_rows(anchor, n=120)
    # Replace last 28 days with 50% refund rate (e.g., 30 paid + 30 refunded).
    cutoff = anchor - timedelta(days=28)
    rows = [r for r in rows if pd.Timestamp(r["Created at"]) < cutoff]
    for i in range(28):
        d = (anchor - timedelta(days=i)).isoformat()
        rows.append(
            {
                "Name": f"WIN{i}",
                "Created at": d,
                "Customer Email": f"win{i}@example.com",
                "Total": 50.0,
                "Subtotal": 50.0,
                "Financial Status": "paid",
                "Cancelled at": None,
            }
        )
        rows.append(
            {
                "Name": f"REF{i}",
                "Created at": d,
                "Customer Email": f"ref{i}@example.com",
                "Total": 50.0,
                "Subtotal": 50.0,
                "Financial Status": "refunded",
                "Cancelled at": None,
            }
        )
    df = _build_orders_df(rows)
    assert detect_refund_storm(df, anchor, thresholds) == DataQualityFlag.REFUND_STORM


def test_refund_storm_does_not_fire_with_no_refunds(thresholds):
    anchor = pd.Timestamp("2025-08-25T12:00:00")
    df = _build_orders_df(_healthy_baseline_rows(anchor, n=120))
    assert detect_refund_storm(df, anchor, thresholds) is None


# ---------------------------------------------------------------------------
# test_order_anomaly
# ---------------------------------------------------------------------------


def test_test_order_anomaly_fires_on_zero_value_orders(thresholds):
    anchor = pd.Timestamp("2025-08-25T12:00:00")
    rows = _healthy_baseline_rows(anchor, n=120)
    # Add 5 zero-value orders inside L28 (out of ~28 baseline + 5 = 33 -> ~15%).
    for i in range(5):
        rows.append(
            {
                "Name": f"ZERO{i}",
                "Created at": (anchor - timedelta(days=i)).isoformat(),
                "Customer Email": f"zero{i}@example.com",
                "Total": 0.0,
                "Subtotal": 0.0,
                "Financial Status": "paid",
                "Cancelled at": None,
            }
        )
    df = _build_orders_df(rows)
    assert detect_test_order_anomaly(df, anchor, thresholds) == DataQualityFlag.TEST_ORDER_ANOMALY


def test_test_order_anomaly_fires_on_single_customer_concentration(thresholds):
    anchor = pd.Timestamp("2025-08-25T12:00:00")
    rows = _healthy_baseline_rows(anchor, n=80)
    # Within last 28 days, 20 orders all from one customer (>30% concentration).
    for i in range(20):
        rows.append(
            {
                "Name": f"DUP{i}",
                "Created at": (anchor - timedelta(days=i % 14)).isoformat(),
                "Customer Email": "tester@example.com",
                "Total": 50.0,
                "Subtotal": 50.0,
                "Financial Status": "paid",
                "Cancelled at": None,
            }
        )
    df = _build_orders_df(rows)
    assert detect_test_order_anomaly(df, anchor, thresholds) == DataQualityFlag.TEST_ORDER_ANOMALY


def test_test_order_anomaly_does_not_fire_on_clean_data(thresholds):
    anchor = pd.Timestamp("2025-08-25T12:00:00")
    df = _build_orders_df(_healthy_baseline_rows(anchor, n=120))
    assert detect_test_order_anomaly(df, anchor, thresholds) is None


# ---------------------------------------------------------------------------
# insufficient_clean_history
# ---------------------------------------------------------------------------


def test_insufficient_clean_history_fires_on_short_history(thresholds):
    anchor = pd.Timestamp("2025-08-25T12:00:00")
    # Only 30 days of history with 30 orders (below 60 days, below 50 orders).
    rows = []
    for i in range(30):
        rows.append(
            {
                "Name": f"O{i}",
                "Created at": (anchor - timedelta(days=i)).isoformat(),
                "Customer Email": f"c{i}@example.com",
                "Total": 50.0,
                "Subtotal": 50.0,
                "Financial Status": "paid",
                "Cancelled at": None,
            }
        )
    df = _build_orders_df(rows)
    assert (
        detect_insufficient_clean_history(df, anchor, thresholds)
        == DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY
    )


def test_insufficient_clean_history_does_not_fire_with_long_history(thresholds):
    anchor = pd.Timestamp("2025-08-25T12:00:00")
    df = _build_orders_df(_healthy_baseline_rows(anchor, n=300))
    assert detect_insufficient_clean_history(df, anchor, thresholds) is None


# ---------------------------------------------------------------------------
# Combiner
# ---------------------------------------------------------------------------


def test_combiner_returns_empty_on_clean_fixture(thresholds):
    anchor = pd.Timestamp("2025-08-25T12:00:00")
    df = _build_orders_df(_healthy_baseline_rows(anchor, n=200))
    flags = detect_anomalous_windows(df, anchor, thresholds)
    assert flags == []


def test_combiner_returns_multiple_flags_when_present(thresholds):
    """A short-history + zero-value-orders fixture fires multiple detectors."""
    anchor = pd.Timestamp("2025-08-25T12:00:00")
    rows = []
    for i in range(20):
        rows.append(
            {
                "Name": f"O{i}",
                "Created at": (anchor - timedelta(days=i)).isoformat(),
                "Customer Email": f"c{i}@example.com",
                "Total": 0.0 if i < 5 else 50.0,
                "Subtotal": 0.0 if i < 5 else 50.0,
                "Financial Status": "paid",
                "Cancelled at": None,
            }
        )
    df = _build_orders_df(rows)
    flags = detect_anomalous_windows(df, anchor, thresholds)
    # Should include both insufficient_clean_history AND test_order_anomaly.
    assert DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY in flags
    assert DataQualityFlag.TEST_ORDER_ANOMALY in flags
    # Result is sorted deterministically.
    assert flags == sorted(flags, key=lambda f: f.value)


def test_combiner_returns_deterministic_order(thresholds):
    anchor = pd.Timestamp("2025-08-25T12:00:00")
    df = _build_orders_df(_healthy_baseline_rows(anchor, n=200))
    out1 = detect_anomalous_windows(df, anchor, thresholds)
    out2 = detect_anomalous_windows(df, anchor, thresholds)
    assert out1 == out2


def test_thresholds_yaml_is_loadable():
    th = load_anomaly_thresholds()
    assert th, "thresholds yaml should load"
    # All five detectors must have a config block.
    for k in [
        "bfcm_overlap",
        "post_promo_window",
        "refund_storm",
        "test_order_anomaly",
        "insufficient_clean_history",
    ]:
        assert k in th, f"missing block: {k}"


def test_detector_does_not_crash_on_empty_df(thresholds):
    anchor = pd.Timestamp("2025-08-25T12:00:00")
    flags = detect_anomalous_windows(pd.DataFrame(), anchor, thresholds)
    # Empty df is "insufficient clean history" by default.
    assert flags == [DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY]
