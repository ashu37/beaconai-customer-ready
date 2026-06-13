"""Phase 5.7 — V2 does not render journey_optimization.

Per memory.md: "rename or demote until onsite funnel data exists." The
legacy emitter still produces fabricated stats on this play; we
defensively suppress it on the V2 considered + recommendation paths so
the page cannot regress to a measured-rendering of journey_optimization.

The legacy emitter is intentionally NOT touched here (legacy goldens
must remain byte-identical). This filter only affects the V2 path.
"""
from __future__ import annotations

from src.decide import (
    PHASE5_V2_SUPPRESS_PLAY_IDS,
    decide,
    populate_considered_from_candidates,
)
from src.detect import Candidate
from src.engine_run import (
    Audience,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Measurement,
    PlayCard,
)
from src.play_registry import PLAYS
from src.storytelling_v2 import render_engine_run


def _candidate(play_id: str, audience_size: int = 1500) -> Candidate:
    return Candidate(
        play_id=play_id,
        audience_size=audience_size,
        segment_definition="audience",
        data_used=[],
        preliminary_rejection_reason=None,
    )


def test_journey_optimization_is_in_phase5_v2_suppress_set():
    """Forcing function: keep the suppression set intentional."""
    assert "journey_optimization" in PHASE5_V2_SUPPRESS_PLAY_IDS


def test_populate_considered_skips_journey_optimization():
    er = EngineRun(recommendations=[], considered=[])
    cands = [
        _candidate("journey_optimization"),
        _candidate("first_to_second_purchase"),
        _candidate("bestseller_amplify"),
    ]
    out = populate_considered_from_candidates(er, cands, registry=PLAYS)
    play_ids = {r.play_id for r in out.considered}
    assert "journey_optimization" not in play_ids
    assert "first_to_second_purchase" in play_ids


def test_decide_drops_journey_optimization_from_recommendations():
    """Even if the legacy adapter accidentally surfaces it, the V2 path
    drops it before ranking."""
    pc = PlayCard(
        play_id="journey_optimization",
        evidence_class=EvidenceClass.MEASURED,  # legacy stamps this
        audience=Audience(size=2000),
        measurement=Measurement(
            metric="conversion_improvement",
            observed_effect=0.35,
            n=2000,
            primary_window="L28",
            consistency_across_windows=3,
        ),
    )
    er = EngineRun(recommendations=[pc])
    out = decide(er)
    rec_ids = [c.play_id for c in out.recommendations]
    assert "journey_optimization" not in rec_ids


def test_v2_briefing_does_not_render_journey_optimization_as_measured():
    """End-to-end safety check: the merchant page never names this play."""
    pc = PlayCard(
        play_id="journey_optimization",
        evidence_class=EvidenceClass.MEASURED,
        audience=Audience(size=2000),
        measurement=Measurement(
            metric="conversion_improvement",
            observed_effect=0.35,
            n=2000,
            primary_window="L28",
            consistency_across_windows=3,
        ),
    )
    er = EngineRun(recommendations=[pc])
    out = decide(er)
    html = render_engine_run(out)
    # The humanized title would otherwise read "Journey Optimization".
    assert "Journey Optimization" not in html
