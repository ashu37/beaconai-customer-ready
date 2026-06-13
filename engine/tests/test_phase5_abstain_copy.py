"""Phase 5.1 — ABSTAIN_SOFT copy is merchant-readable.

Replaces the prior engineering-jargon string ("no measured or directional
recommendation cleared materiality + cannibalization gating") in both
the EngineRun ``Abstain.reason`` field and the V2 briefing callout.

Tests verify:
- ABSTAIN_SOFT briefing does NOT contain "materiality + cannibalization
  gating".
- ABSTAIN_SOFT briefing contains merchant-readable copy (the new
  Phase 5.1 strings).
# S13.6-T1a: stripped — - ``EngineRun.abstain.reason`` after ``decide()`` is merchant-readable.
- The reason text varies based on the dominant rejection gate.
"""
from __future__ import annotations

import pytest

from src.decide import (
    ABSTAIN_SOFT_DEFAULT_REASON,
    ABSTAIN_SOFT_REASONS,
    decide,
)
from src.engine_run import (
    Abstain,
    Audience,
    DecisionState,
    EngineRun,
    EvidenceClass,
    PlayCard,
    ReasonCode,
    RejectedPlay,
    RevenueRange,
)
from src.storytelling_v2 import render_engine_run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _targeting_card(play_id: str = "t1") -> PlayCard:
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.TARGETING,
        audience=Audience(id="aud", definition="L28", size=500),
        revenue_range=RevenueRange(suppressed=True),
    )


# ---------------------------------------------------------------------------
# 5.1 — decide() reason text
# ---------------------------------------------------------------------------


def test_decide_abstain_soft_default_reason_is_merchant_readable():
    """No upstream considered list -> generic merchant-readable default."""
    er = EngineRun(recommendations=[_targeting_card()])
    out = decide(er)
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT


def test_decide_abstain_soft_reason_when_held_for_materiality():
    """Materiality-dominant considered list -> materiality-flavored reason."""
    er = EngineRun(
        recommendations=[_targeting_card("t1")],
        considered=[
            RejectedPlay(play_id="p1", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
            RejectedPlay(play_id="p2", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
        ],
    )
    out = decide(er)
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT


def test_decide_abstain_soft_reason_when_held_for_overlap():
    """Cannibalization-dominant considered list -> overlap-flavored reason."""
    er = EngineRun(
        recommendations=[_targeting_card("t1")],
        considered=[
            RejectedPlay(
                play_id="p1",
                reason_code=ReasonCode.AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY,
            ),
        ],
    )
    out = decide(er)
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT


def test_decide_abstain_soft_reason_when_no_measured_signal():
    """No-measured-signal-dominant considered list -> evidence-flavored reason."""
    er = EngineRun(
        recommendations=[_targeting_card("t1")],
        considered=[
            RejectedPlay(play_id="p1", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
        ],
    )
    out = decide(er)
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT


# ---------------------------------------------------------------------------
# 5.1 — Briefing-html callout text
# ---------------------------------------------------------------------------


def test_abstain_soft_briefing_does_not_contain_old_jargon():
    er = EngineRun(
        store_id="phase5",
        abstain=Abstain(
            state=DecisionState.ABSTAIN_SOFT,
        ),
        recommendations=[],
    )
    html = render_engine_run(er)
    assert "materiality + cannibalization gating" not in html


def test_abstain_soft_briefing_contains_merchant_readable_copy():
    er = EngineRun(
        store_id="phase5",
        abstain=Abstain(
            state=DecisionState.ABSTAIN_SOFT,
        ),
        recommendations=[],
    )
    html = render_engine_run(er)
    # The label is the load-bearing visual cue.
    assert "No primary play this month" in html
    # The body text quotes the merchant-readable default reason.
    assert "Your store is healthy this month" in html


def test_abstain_soft_briefing_old_callout_label_is_gone():
    """Phase 5.1: the old "No measured opportunities cleared." label is replaced."""
    er = EngineRun(
        store_id="phase5",
        abstain=Abstain(
            state=DecisionState.ABSTAIN_SOFT,
        ),
        recommendations=[],
    )
    html = render_engine_run(er)
    # Only the new merchant-readable label is rendered; not the old one.
    assert "No measured opportunities cleared" not in html


def test_abstain_soft_reason_keys_present_in_module():
    """Forcing function: keep the keyed reason map stable across milestones."""
    assert "no_measured" in ABSTAIN_SOFT_REASONS
    assert "materiality" in ABSTAIN_SOFT_REASONS
    assert "overlap" in ABSTAIN_SOFT_REASONS
    for key, text in ABSTAIN_SOFT_REASONS.items():
        # No engineering jargon strings.
        assert "materiality + cannibalization" not in text
        assert "evidence_class" not in text
        assert "p_internal" not in text
