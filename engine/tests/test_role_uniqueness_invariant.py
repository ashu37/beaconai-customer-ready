"""Phase 6A Ticket B4 — Role-uniqueness invariant.

Contract (per ``agent_outputs/implementation-manager-campaign-slate-plan.md``
Ticket B4 and ``agent_outputs/campaign-slate-contract-final.md``):

A single :class:`EngineRun` produced by :func:`decide` MUST NOT contain
the same ``play_id`` in more than one role section. Specifically, no
``play_id`` may appear in BOTH ``recommendations`` and
``recommended_experiments``.

This invariant is the load-bearing trust constraint that prevents a
future code path from accidentally surfacing the same play to a
merchant under two competing framings (e.g., as both a measured card
and a send-and-measure experiment). The eligibility filter from
Ticket A4 already excludes rec play_ids from the experiment selector,
so this assertion is a defensive net for future changes.

Broader enforcement (``recommendations`` / ``recommended_experiments``
/ ``considered`` all pairwise-disjoint) is also tested here. The
existing decide-layer pipeline already produces this property — ``
assemble_considered`` excludes ``recommended_play_ids``,
``populate_considered_from_candidates`` skips play_ids already in
``recommendations`` or in ``considered``, and the B3 ABSTAIN_SOFT
routing dedupes against pre-existing ``considered`` and the regular
Fix 3 head-routing list — so the broader assertion is safe to add.

This file is intentionally landed FIRST (TDD red-first) so the new
invariant assertions FAIL until the decide-layer enforcement ships.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import priors_loader as PL
from src.decide import (
    _assert_role_uniqueness,
    decide,
)
from src.engine_run import (
    Abstain,
    Audience,
    BriefingMeta,
    DataQualityFlag,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Measurement,
    PlayCard,
    ReasonCode,
    RejectedPlay,
    RevenueRange,
    Scale,
    WouldBeMeasuredBy,
)


@pytest.fixture(autouse=True)
def _reset_priors_cache():
    PL.clear_cache()
    yield
    PL.clear_cache()


# ---------------------------------------------------------------------------
# Light Candidate stand-in matching the Ticket A4/B3 test stubs.
# ---------------------------------------------------------------------------


class _Cand:
    def __init__(
        self,
        play_id: str,
        audience_size: int,
        *,
        segment_definition: str = "test segment",
        preliminary_rejection_reason: Optional[str] = None,
        audience_overlap: Optional[Dict[str, float]] = None,
    ) -> None:
        self.play_id = play_id
        self.audience_size = audience_size
        self.segment_definition = segment_definition
        self.preliminary_rejection_reason = preliminary_rejection_reason
        self.audience_overlap = dict(audience_overlap or {})


def _measured_card(play_id: str = "m") -> PlayCard:
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.MEASURED,
        audience=Audience(id=play_id, size=500),
        measurement=Measurement(
            metric="returning_customer_share",
            observed_effect=0.05,
            n=500,
            primary_window="L28",
        ),
        revenue_range=RevenueRange(p10=100, p50=200, p90=400, suppressed=False),
    )


def _targeting_card(play_id: str, *, audience_size: int = 1500) -> PlayCard:
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.TARGETING,
        audience=Audience(
            id=f"aud_{play_id}",
            definition=f"audience for {play_id}",
            size=audience_size,
        ),
        measurement=None,
        revenue_range=RevenueRange(suppressed=True),
    )


def _experiment_card(play_id: str) -> PlayCard:
    """Synthesize a Recommended Experiment-shaped PlayCard."""
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.TARGETING,
        audience=Audience(id=f"aud_{play_id}", size=1000),
        measurement=None,
        revenue_range=RevenueRange(
            suppressed=True,
            drivers=[{"reason": "experiment_no_calibrated_lift"}],
        ),
        would_be_measured_by=WouldBeMeasuredBy.REPEAT_PURCHASE_IN_30D,
    )


def _make_engine_run(
    *,
    recommendations: Optional[List[PlayCard]] = None,
    considered: Optional[List[RejectedPlay]] = None,
    flags: Optional[List[DataQualityFlag]] = None,
    vertical: str = "beauty",
) -> EngineRun:
    return EngineRun(
        run_id="role-uniqueness-test",
        store_id="role-uniqueness-store",
        recommendations=recommendations or [],
        considered=considered or [],
        data_quality_flags=flags or [],
        abstain=Abstain(state=DecisionState.PUBLISH),
        scale=Scale(monthly_revenue=100_000.0, materiality_floor=5_000),
        briefing_meta=BriefingMeta(vertical=vertical),
    )


# ---------------------------------------------------------------------------
# Direct-helper tests: the assertion fires on duplicates.
# ---------------------------------------------------------------------------


def test_helper_raises_on_duplicate_in_recommendations_and_recommended_experiments():
    """Same play_id in ``recommendations`` and ``recommended_experiments``
    MUST raise ``AssertionError``. The duplicate play_id and both role
    names MUST appear in the message.
    """
    er = EngineRun(
        recommendations=[_measured_card("dup_id")],
        recommended_experiments=[_experiment_card("dup_id")],
    )
    with pytest.raises(AssertionError) as exc:
        _assert_role_uniqueness(er)

    msg = str(exc.value)
    assert "dup_id" in msg, f"Assertion message must include duplicate play_id; got {msg!r}."
    assert "recommendations" in msg, (
        f"Assertion message must name the 'recommendations' role; got {msg!r}."
    )
    assert "recommended_experiments" in msg, (
        f"Assertion message must name the 'recommended_experiments' role; "
        f"got {msg!r}."
    )


def test_helper_raises_on_duplicate_in_recommendations_and_considered():
    """Same play_id in ``recommendations`` and ``considered`` MUST raise
    ``AssertionError``.

    Broader enforcement: the existing decide-layer pipeline keeps these
    disjoint via ``assemble_considered(recommended_play_ids=...)``. The
    assertion is a defensive net.
    """
    er = EngineRun(
        recommendations=[_measured_card("dup_rec_cons")],
        considered=[
            RejectedPlay(
                play_id="dup_rec_cons",
                reason_code=ReasonCode.CAP_EXCEEDED,
            )
        ],
    )
    with pytest.raises(AssertionError) as exc:
        _assert_role_uniqueness(er)

    msg = str(exc.value)
    assert "dup_rec_cons" in msg
    assert "recommendations" in msg
    assert "considered" in msg


def test_helper_raises_on_duplicate_in_recommended_experiments_and_considered():
    """Same play_id in ``recommended_experiments`` and ``considered``
    MUST raise. Broader enforcement.
    """
    er = EngineRun(
        recommended_experiments=[_experiment_card("dup_exp_cons")],
        considered=[
            RejectedPlay(
                play_id="dup_exp_cons",
                reason_code=ReasonCode.AUDIENCE_TOO_SMALL,
            )
        ],
    )
    with pytest.raises(AssertionError) as exc:
        _assert_role_uniqueness(er)

    msg = str(exc.value)
    assert "dup_exp_cons" in msg
    assert "recommended_experiments" in msg
    assert "considered" in msg


def test_helper_does_not_raise_on_clean_engine_run():
    """All distinct play_ids: helper MUST NOT raise."""
    er = EngineRun(
        recommendations=[_measured_card("rec_a"), _measured_card("rec_b")],
        recommended_experiments=[
            _experiment_card("exp_a"),
            _experiment_card("exp_b"),
        ],
        considered=[
            RejectedPlay(
                play_id="con_a",
                reason_code=ReasonCode.CAP_EXCEEDED,
            ),
            RejectedPlay(
                play_id="con_b",
                reason_code=ReasonCode.AUDIENCE_TOO_SMALL,
            ),
        ],
    )
    # Must not raise.
    _assert_role_uniqueness(er)


def test_helper_does_not_raise_on_empty_engine_run():
    """Empty role lists: helper MUST NOT raise."""
    er = EngineRun()
    _assert_role_uniqueness(er)


# ---------------------------------------------------------------------------
# Integration: decide() invokes the helper. PUBLISH path is clean.
# ---------------------------------------------------------------------------


def test_decide_publish_path_passes_role_uniqueness():
    """A normal PUBLISH run (one measured + two experiment candidates)
    must not raise the role-uniqueness assertion.
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    er = _make_engine_run(recommendations=[_measured_card("m")])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.PUBLISH
    # The assertion ran inside decide(); reaching this line means it
    # did not fire. Re-run it explicitly so a regression that bypasses
    # decide() is also caught.
    _assert_role_uniqueness(out)


def test_decide_publish_path_recommended_experiments_disjoint_from_recommendations():
    """No play_id appears in both ``recommendations`` and
    ``recommended_experiments`` after a PUBLISH decide() call.
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    er = _make_engine_run(recommendations=[_measured_card("m")])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    rec_ids = {str(c.play_id) for c in out.recommendations}
    exp_ids = {str(c.play_id) for c in out.recommended_experiments}
    assert rec_ids.isdisjoint(exp_ids), (
        f"recommendations and recommended_experiments share play_ids: "
        f"{rec_ids & exp_ids!r}"
    )


def test_decide_publish_path_recommended_experiments_disjoint_from_considered():
    """No play_id appears in both ``recommended_experiments`` and
    ``considered`` after a PUBLISH decide() call.
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    er = _make_engine_run(recommendations=[_measured_card("m")])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    exp_ids = {str(c.play_id) for c in out.recommended_experiments}
    con_ids = {str(r.play_id) for r in out.considered}
    assert exp_ids.isdisjoint(con_ids), (
        f"recommended_experiments and considered share play_ids: "
        f"{exp_ids & con_ids!r}"
    )


# ---------------------------------------------------------------------------
# Integration: ABSTAIN_SOFT (B3 routing) does not violate the invariant.
# ---------------------------------------------------------------------------


def test_decide_abstain_soft_b3_routing_passes_role_uniqueness():
    """ABSTAIN_SOFT with B3 experiment-side held-card routing must not
    violate the role-uniqueness invariant. Held experiment plays appear
    in ``considered`` only; ``recommended_experiments`` is ``[]``;
    ``recommendations`` is ``[]``. All three lists are pairwise disjoint
    by construction.
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    # Targeting-only head forces ABSTAIN_SOFT.
    er = _make_engine_run(
        recommendations=[_targeting_card("t1", audience_size=2000)]
    )
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT
    assert out.recommendations == []
    assert out.recommended_experiments == []
    # The held experiment plays should be in considered.
    con_ids = {str(r.play_id) for r in out.considered}
    assert "discount_hygiene" in con_ids
    # And the invariant must hold.
    _assert_role_uniqueness(out)


# ---------------------------------------------------------------------------
# Integration: ABSTAIN_HARD does not violate the invariant.
# ---------------------------------------------------------------------------


def test_decide_abstain_hard_passes_role_uniqueness():
    """ABSTAIN_HARD: ``recommendations`` and ``recommended_experiments``
    are both ``[]``. The data-quality memo path routes the originally
    ranked head into ``considered`` with DATA_QUALITY_FLAG. The
    invariant must hold.
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    er = _make_engine_run(
        recommendations=[_measured_card("m")],
        flags=[DataQualityFlag.BFCM_OVERLAP],
    )
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_HARD
    assert out.recommendations == []
    assert out.recommended_experiments == []
    _assert_role_uniqueness(out)


# ---------------------------------------------------------------------------
# Assertion message quality.
# ---------------------------------------------------------------------------


def test_assertion_message_lists_all_duplicate_play_ids():
    """Multiple duplicates: the assertion message includes every
    duplicate play_id.
    """
    er = EngineRun(
        recommendations=[
            _measured_card("dup1"),
            _measured_card("dup2"),
        ],
        recommended_experiments=[
            _experiment_card("dup1"),
            _experiment_card("dup2"),
        ],
    )
    with pytest.raises(AssertionError) as exc:
        _assert_role_uniqueness(er)
    msg = str(exc.value)
    assert "dup1" in msg
    assert "dup2" in msg


def test_assertion_message_is_actionable():
    """The assertion message must be human-readable and clearly identify
    the offending play_id and roles. Pin the format so a future
    refactor that relaxes the message text breaks loudly.
    """
    er = EngineRun(
        recommendations=[_measured_card("offender")],
        recommended_experiments=[_experiment_card("offender")],
    )
    with pytest.raises(AssertionError) as exc:
        _assert_role_uniqueness(er)
    msg = str(exc.value)
    # The play_id must be explicitly named.
    assert "offender" in msg
    # Both role names must be explicitly named.
    assert "recommendations" in msg
    assert "recommended_experiments" in msg
    # The message should not be empty / trivial.
    assert len(msg) > 20, f"Assertion message looks too terse: {msg!r}"


# ---------------------------------------------------------------------------
# Flag-off behavior: invariant still holds.
# ---------------------------------------------------------------------------


def test_decide_flag_off_passes_role_uniqueness():
    """With ``ENGINE_V2_SLATE=false`` the invariant still holds because
    ``recommended_experiments`` is forced to ``[]``.
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    er = _make_engine_run(recommendations=[_measured_card("m")])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": False, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.PUBLISH
    assert out.recommended_experiments == []
    _assert_role_uniqueness(out)
