"""Milestone 5 T5.2 — anomaly-abstain integration tests.

Per the M5 plan: a fixture with hard data-quality flag(s) must produce
``EngineRun.abstain.state == "abstain_hard"`` when
``ANOMALY_GATE_ENABLED=true``. With the flag off, M4b behavior is preserved.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import (  # noqa: E402
    Audience,
    DataQualityFlag,
    DecisionState,
    EngineRun,
    PlayCard,
    ReasonCode,
    RevenueRange,
    Scale,
)
from src.guardrails import apply_guardrails  # noqa: E402


def _run_with_flag(flag: DataQualityFlag) -> EngineRun:
    return EngineRun(
        recommendations=[
            PlayCard(
                play_id="winback_21_45",
                audience=Audience(id="winback_21_45_inactive", size=120),
                revenue_range=RevenueRange(p50=20_000.0),
            )
        ],
        data_quality_flags=[flag],
        scale=Scale(monthly_revenue=200_000.0),
    )


def test_refund_storm_synthetic_fixture_triggers_abstain_hard():
    run = _run_with_flag(DataQualityFlag.REFUND_STORM)
    out = apply_guardrails(run, cfg={"ANOMALY_GATE_ENABLED": True})
    assert out.abstain.state == DecisionState.ABSTAIN_HARD
    assert out.recommendations == []


def test_bfcm_overlap_triggers_abstain_hard():
    run = _run_with_flag(DataQualityFlag.BFCM_OVERLAP)
    out = apply_guardrails(run, cfg={"ANOMALY_GATE_ENABLED": True})
    assert out.abstain.state == DecisionState.ABSTAIN_HARD
    assert out.recommendations == []


def test_test_order_anomaly_triggers_abstain_hard():
    run = _run_with_flag(DataQualityFlag.TEST_ORDER_ANOMALY)
    out = apply_guardrails(run, cfg={"ANOMALY_GATE_ENABLED": True})
    assert out.abstain.state == DecisionState.ABSTAIN_HARD


def test_insufficient_clean_history_triggers_abstain_hard():
    run = _run_with_flag(DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY)
    out = apply_guardrails(run, cfg={"ANOMALY_GATE_ENABLED": True})
    assert out.abstain.state == DecisionState.ABSTAIN_HARD


def test_post_promo_window_alone_triggers_abstain_soft_under_b1():
    # B-1: POST_PROMO_WINDOW is a load-bearing window anomaly. The B-1
    # routing demotes per-play to ABSTAIN_SOFT (zero Recommended cards;
    # held plays surface in Considered with ANOMALOUS_WINDOW reason).
    run = _run_with_flag(DataQualityFlag.POST_PROMO_WINDOW)
    out = apply_guardrails(run, cfg={"ANOMALY_GATE_ENABLED": True})
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT
    assert out.recommendations == []
    assert len(out.considered) == 1
    assert out.considered[0].reason_code == ReasonCode.ANOMALOUS_WINDOW


def test_flag_off_preserves_legacy_state():
    run = _run_with_flag(DataQualityFlag.REFUND_STORM)
    # B-1 flips ``ANOMALY_GATE_ENABLED`` default to True. The escape
    # hatch ``ANOMALY_GATE_ENABLED=False`` still preserves the legacy
    # no-op semantics for callers that need to suppress the auto-router.
    out = apply_guardrails(run, cfg={"ANOMALY_GATE_ENABLED": False})
    assert out.abstain.state == DecisionState.PUBLISH
    assert len(out.recommendations) == 1


def test_recommendations_appear_in_considered_with_anomalous_window_code():
    run = _run_with_flag(DataQualityFlag.REFUND_STORM)
    out = apply_guardrails(run, cfg={"ANOMALY_GATE_ENABLED": True})
    assert len(out.considered) == 1
    assert out.considered[0].reason_code == ReasonCode.ANOMALOUS_WINDOW
    # The play_id was preserved into the rejection.
    assert out.considered[0].play_id == "winback_21_45"
