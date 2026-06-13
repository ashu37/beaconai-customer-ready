"""Sprint 5 Ticket S5-T3 (resolves KI-22) — cadence-coherence flag.

Pins the contract:

- New typed enum value ``DataQualityFlag.METRIC_INCOHERENT_FOR_CADENCE``
  is additive within the Sprint 2 ``event_version=1`` freeze.
- The pure helper ``src.cadence_coherence`` computes the median
  customer-level reorder gap and fires when that gap exceeds
  ``DEFAULT_THRESHOLD_RATIO (0.8)`` × ``window_days``.
- On the supplements vertical, the engine propagates the existing
  stdout advisory into ``engine_run.data_quality_flags`` AND suppresses
  the misleading ``repeat_rate_within_window`` Watching row (founder
  call: suppress, not relabel).
- The flag is ADVISORY — it is NOT in ``src.decide._HARD_DQ_FLAGS``,
  so the supplements run stays ``ABSTAIN_SOFT``, not ``ABSTAIN_HARD``.
- Beauty path is unaffected (cadence < window on Beauty).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.cadence_coherence import (  # noqa: E402
    DEFAULT_THRESHOLD_RATIO,
    cadence_exceeds_window,
    compute_median_customer_reorder_gap_days,
    evaluate,
)
from src.decide import _HARD_DQ_FLAGS  # noqa: E402
from src.engine_run import DataQualityFlag  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Threshold pin (single source of truth, not scattered magic constant)
# ---------------------------------------------------------------------------


def test_default_threshold_ratio_pinned() -> None:
    """The 0.8 threshold is pinned in one place. If a future ticket
    re-tunes it, this assertion forces an explicit re-pin."""
    assert DEFAULT_THRESHOLD_RATIO == 0.8


# ---------------------------------------------------------------------------
# 2. Pure helper semantics
# ---------------------------------------------------------------------------


def test_compute_median_gap_returns_none_on_empty_df() -> None:
    df = pd.DataFrame({"customer_id": [], "Created at": []})
    assert compute_median_customer_reorder_gap_days(df) is None


def test_compute_median_gap_returns_none_when_no_repeat_customers() -> None:
    df = pd.DataFrame(
        {
            "customer_id": ["c1", "c2", "c3"],
            "Created at": pd.to_datetime(
                ["2026-01-01", "2026-01-05", "2026-01-10"]
            ),
        }
    )
    # All single-order customers -> no gap defined.
    assert compute_median_customer_reorder_gap_days(df) is None


def test_compute_median_gap_basic_two_customers() -> None:
    df = pd.DataFrame(
        {
            "customer_id": ["c1", "c1", "c2", "c2"],
            "Created at": pd.to_datetime(
                ["2026-01-01", "2026-02-01", "2026-01-01", "2026-02-10"]
            ),
        }
    )
    # c1 gap = 31d, c2 gap = 40d -> median = 35.5
    gap = compute_median_customer_reorder_gap_days(df)
    assert gap is not None
    assert 30.0 <= gap <= 41.0


def test_cadence_exceeds_window_fires_when_gap_above_threshold() -> None:
    # 30d gap, 28d window: 30 > 0.8*28 = 22.4 -> fires
    assert cadence_exceeds_window(30.0, 28) is True


def test_cadence_exceeds_window_does_not_fire_at_boundary() -> None:
    # 22.4d = exactly threshold; strict > so this returns False.
    assert cadence_exceeds_window(22.4, 28) is False


def test_cadence_exceeds_window_does_not_fire_below_threshold() -> None:
    # Beauty-shape: gap < threshold (e.g. 10d on 28d window).
    assert cadence_exceeds_window(10.0, 28) is False


def test_cadence_exceeds_window_fail_closed_on_missing_inputs() -> None:
    assert cadence_exceeds_window(None, 28) is False
    assert cadence_exceeds_window(30.0, None) is False
    assert cadence_exceeds_window(30.0, 0) is False


def test_evaluate_returns_flag_and_gap_tuple() -> None:
    df = pd.DataFrame(
        {
            "customer_id": ["c1", "c1", "c2", "c2"],
            "Created at": pd.to_datetime(
                ["2026-01-01", "2026-02-15", "2026-01-01", "2026-02-15"]
            ),
        }
    )
    # ~45d gap on a 28d window -> fires.
    should_flag, gap = evaluate(df, 28)
    assert should_flag is True
    assert gap is not None
    assert gap >= 22.4


def test_evaluate_on_beauty_shape_does_not_fire() -> None:
    # Beauty-shape: customers reorder roughly weekly.
    rows = []
    for i in range(20):
        rows.append({"customer_id": f"c{i}", "Created at": pd.Timestamp("2026-01-01")})
        rows.append({"customer_id": f"c{i}", "Created at": pd.Timestamp("2026-01-08")})
    df = pd.DataFrame(rows)
    should_flag, gap = evaluate(df, 28)
    assert should_flag is False
    assert gap == 7.0


# ---------------------------------------------------------------------------
# 3. Enum is declared and additive
# ---------------------------------------------------------------------------


def test_enum_member_declared() -> None:
    assert DataQualityFlag.METRIC_INCOHERENT_FOR_CADENCE.value == (
        "metric_incoherent_for_cadence"
    )


def test_new_flag_is_advisory_not_hard() -> None:
    """The flag MUST NOT push the run to ABSTAIN_HARD. KI-22 documents
    this as advisory; including it in ``_HARD_DQ_FLAGS`` would silently
    flip the supplements run's decision_state."""
    assert (
        DataQualityFlag.METRIC_INCOHERENT_FOR_CADENCE not in _HARD_DQ_FLAGS
    )


# ---------------------------------------------------------------------------
# 4. End-to-end: supplements fires the flag; Beauty does not
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def supplements_engine_run() -> dict:
    from tests.synthetic_harness import run_scenario

    env = {
        "ENGINE_V2_OUTPUT": "true",
        "ENGINE_V2_DECIDE": "true",
        "ENGINE_V2_SLATE": "true",
        "ENGINE_V2_SIZING": "true",
        "VERTICAL_MODE": "supplements",
        "WINDOW_POLICY": "auto",
    }
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "s5t3_supp"
        result = run_scenario(
            "healthy_supplements_240d",
            out_dir,
            env_overrides=env,
            timeout_sec=300,
        )
        assert result.returncode == 0, result.stderr[-500:]
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists()
        return json.loads(receipts.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def beauty_engine_run() -> dict:
    from tests.synthetic_harness import run_scenario

    env = {
        "ENGINE_V2_OUTPUT": "true",
        "ENGINE_V2_DECIDE": "true",
        "ENGINE_V2_SLATE": "true",
        "ENGINE_V2_SIZING": "true",
        "VERTICAL_MODE": "beauty",
        "WINDOW_POLICY": "auto",
    }
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "s5t3_beauty"
        result = run_scenario(
            "healthy_beauty_240d",
            out_dir,
            env_overrides=env,
            timeout_sec=300,
        )
        assert result.returncode == 0, result.stderr[-500:]
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists()
        return json.loads(receipts.read_text(encoding="utf-8"))


def test_supplements_engine_run_emits_cadence_flag(
    supplements_engine_run: dict,
) -> None:
    flags = supplements_engine_run.get("data_quality_flags") or []
    assert "metric_incoherent_for_cadence" in flags, (
        f"Expected ``metric_incoherent_for_cadence`` in supplements "
        f"data_quality_flags; got {flags!r}. KI-22 close: supplements "
        f"reorder cadence (28-45d) > 0.8 * 28d window."
    )


def test_supplements_decision_state_stays_abstain_soft(
    supplements_engine_run: dict,
) -> None:
    """The new flag is advisory — it must NOT push to ABSTAIN_HARD."""
    abstain = supplements_engine_run.get("abstain") or {}
    assert abstain.get("state") == "abstain_soft"


def test_supplements_watching_suppresses_repeat_rate(
    supplements_engine_run: dict,
) -> None:
    """Founder choice (S5-T3, plan §11): suppress the misleading
    ``repeat_rate_within_window`` Watching row when the flag fires."""
    watching = supplements_engine_run.get("watching") or []
    metrics = {str(w.get("metric")) for w in watching if w.get("metric")}
    assert "repeat_rate_within_window" not in metrics, (
        f"Expected ``repeat_rate_within_window`` suppressed on supplements "
        f"Watching when METRIC_INCOHERENT_FOR_CADENCE fires; got {metrics!r}."
    )


def test_beauty_engine_run_does_not_emit_cadence_flag(
    beauty_engine_run: dict,
) -> None:
    flags = beauty_engine_run.get("data_quality_flags") or []
    assert "metric_incoherent_for_cadence" not in flags, (
        f"Beauty cadence < window so the flag must not fire. Got {flags!r}. "
        f"If Beauty regressed into firing this flag, M0 byte-identity is "
        f"the next thing to check."
    )
