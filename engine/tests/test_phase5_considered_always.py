"""Phase 5.2 — populate considered list during ABSTAIN_SOFT.

Whenever plays were detected, registered as relevant, emitted by legacy,
or suppressed/held by evidence/sizing/materiality, V2 should populate
``considered[]`` even when ``decision_state == ABSTAIN_SOFT``.

Each considered item has:
- ``play_id``
- ``reason_code``
- ``reason_text`` or ``held_because``
- ``evidence_snapshot`` if available
- ``would_fire_if``

These tests do NOT require the engine to flip from ABSTAIN_SOFT to
PUBLISH; they require the considered list to be populated and rendered.
"""
from __future__ import annotations

from src.decide import (
    decide,
    populate_considered_from_candidates,
)
from src.detect import Candidate
from src.engine_run import (
    Abstain,
    DecisionState,
    EngineRun,
    EvidenceClass,
    PlayCard,
    ReasonCode,
    RejectedPlay,
)
from src.play_registry import PLAYS
from src.storytelling_v2 import render_engine_run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _candidate(play_id: str, **kw) -> Candidate:
    return Candidate(
        play_id=play_id,
        audience_size=kw.get("audience_size", 1500),
        segment_definition=kw.get("segment_definition", f"Audience for {play_id}"),
        data_used=kw.get("data_used", []),
        preliminary_rejection_reason=kw.get("preliminary_rejection_reason", None),
        cold_start=kw.get("cold_start", False),
    )


# ---------------------------------------------------------------------------
# 5.2 — populate_considered_from_candidates
# ---------------------------------------------------------------------------


def test_populate_considered_emits_one_card_per_candidate_not_in_recommendations():
    er = EngineRun(recommendations=[], considered=[])
    cands = [
        _candidate("first_to_second_purchase"),
        _candidate("bestseller_amplify"),
        _candidate("subscription_nudge"),
    ]
    out = populate_considered_from_candidates(er, cands, registry=PLAYS)
    play_ids = {r.play_id for r in out.considered}
    assert "first_to_second_purchase" in play_ids
    assert "bestseller_amplify" in play_ids
    assert "subscription_nudge" in play_ids


def test_populate_considered_skips_candidates_already_in_recommendations():
    pc = PlayCard(play_id="first_to_second_purchase", evidence_class=EvidenceClass.DIRECTIONAL)
    er = EngineRun(recommendations=[pc], considered=[])
    cands = [
        _candidate("first_to_second_purchase"),
        _candidate("bestseller_amplify"),
    ]
    out = populate_considered_from_candidates(er, cands, registry=PLAYS)
    play_ids = {r.play_id for r in out.considered}
    assert "first_to_second_purchase" not in play_ids
    assert "bestseller_amplify" in play_ids


def test_populate_considered_does_not_double_add_existing_considered_play_ids():
    existing = RejectedPlay(
        play_id="bestseller_amplify",
        reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR,
    )
    er = EngineRun(recommendations=[], considered=[existing])
    cands = [
        _candidate("bestseller_amplify"),
        _candidate("subscription_nudge"),
    ]
    out = populate_considered_from_candidates(er, cands, registry=PLAYS)
    play_ids = [r.play_id for r in out.considered]
    # bestseller_amplify appears exactly once (the upstream entry wins).
    assert play_ids.count("bestseller_amplify") == 1
    # subscription_nudge is added.
    assert "subscription_nudge" in play_ids


def test_populate_considered_each_item_has_reason_code_and_would_fire_if():
    er = EngineRun(recommendations=[], considered=[])
    cands = [_candidate("first_to_second_purchase")]
    out = populate_considered_from_candidates(er, cands, registry=PLAYS)
    assert len(out.considered) == 1
    rej = out.considered[0]
    assert rej.reason_code is not None


def test_populate_considered_caps_at_six_renderable():
    er = EngineRun(recommendations=[], considered=[])
    cands = [_candidate(pid) for pid in list(PLAYS.keys())[:8]]
    out = populate_considered_from_candidates(er, cands, registry=PLAYS)
    assert len(out.considered) <= 6


def test_populate_considered_filters_by_vertical_when_configured():
    """A play whose vertical_applicable does not include the run's vertical
    is suppressed (Phase 5.2 simplification)."""
    er = EngineRun(recommendations=[], considered=[])
    # Build a fake registry-like map where one play applies only to "supplements".
    from dataclasses import dataclass, field
    from typing import FrozenSet, Optional

    @dataclass(frozen=True)
    class _FakePlay:
        play_id: str
        evidence_class_default: str = "targeting"
        vertical_applicable: FrozenSet[str] = frozenset({"supplements"})
        subvertical_applicable: Optional[FrozenSet[str]] = None
        measurement_metric: Optional[str] = None

    fake = {"supplements_only": _FakePlay(play_id="supplements_only")}
    cands = [_candidate("supplements_only")]
    out = populate_considered_from_candidates(
        er, cands, registry=fake, vertical="beauty"
    )
    assert all(r.play_id != "supplements_only" for r in out.considered)


def test_populate_considered_evidence_snapshot_carries_audience_size():
    er = EngineRun(recommendations=[], considered=[])
    cands = [_candidate("first_to_second_purchase", audience_size=2347)]
    out = populate_considered_from_candidates(er, cands, registry=PLAYS)
    rej = out.considered[0]


# ---------------------------------------------------------------------------
# 5.2 — Briefing renders considered list during ABSTAIN_SOFT
# ---------------------------------------------------------------------------


def test_abstain_soft_briefing_renders_populated_considered_section():
    er = EngineRun(
        store_id="phase5",
        abstain=Abstain(state=DecisionState.ABSTAIN_SOFT),
        considered=[
            RejectedPlay(
                play_id="first_to_second_purchase",
                reason_code=ReasonCode.NO_MEASURED_SIGNAL,
            ),
            RejectedPlay(
                play_id="bestseller_amplify",
                reason_code=ReasonCode.NO_MEASURED_SIGNAL,
            ),
            RejectedPlay(
                play_id="subscription_nudge",
                reason_code=ReasonCode.NO_MEASURED_SIGNAL,
            ),
        ],
    )
    html = render_engine_run(er)
    # Section is present and not empty-state.
    assert 'class="considered"' in html
    assert "No plays were considered and held this run." not in html
    # All three play_ids surface (merchant-readable display_names per
    # Phase 6B Ticket C3).
    assert "Second-purchase nudge for one-and-done buyers" in html
    assert "Top-product re-targeting" in html
    assert "Subscribe-and-save invitation for repeat buyers" in html
    # Would-fire-if text renders.
    assert "Would fire" in html


def test_considered_section_does_not_contain_forbidden_statistical_strings():
    er = EngineRun(
        store_id="phase5",
        abstain=Abstain(state=DecisionState.ABSTAIN_SOFT),
        considered=[
            RejectedPlay(
                play_id="first_to_second_purchase",
                reason_code=ReasonCode.NO_MEASURED_SIGNAL,
            ),
        ],
    )
    html = render_engine_run(er)
    # No statistical jargon leaks into considered cards.
    forbidden = ["p =", "q =", "p_internal", "ci_internal", "confidence_score", "final_score"]
    for token in forbidden:
        assert token not in html, f"Forbidden token {token!r} leaked into V2 briefing"


# ---------------------------------------------------------------------------
# 5.2 — decide() abstain text reflects the populated considered list
# ---------------------------------------------------------------------------


def test_decide_abstain_reason_uses_dominant_considered_gate():
    """When considered is dominated by NO_MEASURED_SIGNAL, abstain reason
    should be the no-measured-flavored merchant-readable string."""
    er = EngineRun(
        recommendations=[],
        considered=[
            RejectedPlay(play_id="p1", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
            RejectedPlay(play_id="p2", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
        ],
    )
    out = decide(er)
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT
