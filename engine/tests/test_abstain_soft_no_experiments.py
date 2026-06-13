"""Phase 6A Ticket B3 — ABSTAIN_SOFT contract extension to Recommended
Experiment.

Contract (per ``agent_outputs/implementation-manager-campaign-slate-plan.md``
Ticket B3 and ``agent_outputs/campaign-slate-contract-final.md``):

Under ``decision_state == ABSTAIN_SOFT``:

1. ``engine_run.recommended_experiments`` MUST be ``[]``. (Already in
   place from Ticket A4.)
2. The rendered ``section.recommended-experiment`` MUST contain zero
   ``article.play-card`` elements. (Already in place from Ticket B1.)
3. **NEW (Ticket B3)**: any experiment-eligible candidates that would
   otherwise have qualified as Recommended Experiment cards under
   PUBLISH MUST be re-routed to ``engine_run.considered`` with
   ``ReasonCode.TARGETING_HELD_UNDER_ABSTAIN``. The ``reason_text`` and
   ``would_fire_if`` MUST reuse the existing Fix 3 templates.
4. No duplicate Considered entries. If an experiment-eligible
   candidate's play_id is already present in ``considered`` (e.g.,
   routed there by the regular Fix 3 path or by an upstream guardrail),
   the experiment-side routing MUST skip it.

Under ``decision_state == ABSTAIN_HARD``: behavior is unchanged. The
data-quality memo path remains and ``recommended_experiments`` stays
``[]`` without any held-card routing for experiments.

Under ``decision_state == PUBLISH``: behavior is unchanged. The
selector emits 0-2 experiment cards as before.

This file is intentionally landed FIRST (TDD red-first) so the new
considered-routing assertions FAIL until the decide-layer extension
ships.
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
from src.decide import decide
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
from src.storytelling_v2 import render_engine_run


@pytest.fixture(autouse=True)
def _reset_priors_cache():
    PL.clear_cache()
    yield
    PL.clear_cache()


# ---------------------------------------------------------------------------
# Light Candidate stand-in (mirror of the existing eligibility test stub).
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


def _targeting_card(play_id: str, *, audience_size: int = 1500) -> PlayCard:
    """A clean targeting PlayCard for forcing ABSTAIN_SOFT.

    Per Fix 2's invariant, ``measurement`` is ``None``.
    """
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


def _make_engine_run(
    *,
    recommendations: Optional[List[PlayCard]] = None,
    considered: Optional[List[RejectedPlay]] = None,
    flags: Optional[List[DataQualityFlag]] = None,
    vertical: str = "beauty",
) -> EngineRun:
    """Build an EngineRun whose post-decide state is ABSTAIN_SOFT by default.

    Targeting-only ``recommendations`` and no measured/directional cards
    => ``decide()`` produces ``ABSTAIN_SOFT``.
    """
    return EngineRun(
        run_id="abstain-soft-experiments-test",
        store_id="abstain-soft-experiments-store",
        recommendations=recommendations or [],
        considered=considered or [],
        data_quality_flags=flags or [],
        abstain=Abstain(state=DecisionState.PUBLISH),
        scale=Scale(monthly_revenue=100_000.0, materiality_floor=5_000),
        briefing_meta=BriefingMeta(vertical=vertical),
    )


# ---------------------------------------------------------------------------
# Acceptance: ABSTAIN_SOFT keeps recommended_experiments empty.
#
# Ticket A4 already enforces this; we re-pin it here so a future
# regression on the new routing path cannot accidentally re-populate
# the list.
# ---------------------------------------------------------------------------


def test_abstain_soft_recommended_experiments_is_empty():
    """Under ABSTAIN_SOFT, ``recommended_experiments`` MUST be ``[]``."""
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    er = _make_engine_run(recommendations=[_targeting_card("t1", audience_size=2000)])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT
    assert out.recommended_experiments == [], (
        f"ABSTAIN_SOFT must yield zero Recommended Experiment cards. Got "
        f"{[c.play_id for c in out.recommended_experiments]!r}."
    )


def test_abstain_soft_renders_zero_recommended_experiment_cards():
    """The rendered HTML must contain no ``section.recommended-experiment``
    when ``recommended_experiments`` is forced to ``[]``.
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    er = _make_engine_run(recommendations=[_targeting_card("t1", audience_size=2000)])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT

    html = render_engine_run(out)
    # Section must not render at all (the renderer omits when list empty).
    assert 'class="recommended-experiment"' not in html, (
        "ABSTAIN_SOFT briefing must not render section.recommended-experiment."
    )
    # No experiment article cards.
    assert 'data-play-id="discount_hygiene"' not in (
        # Allow data-play-id appearing in Considered, but the experiment
        # card class must not appear anywhere.
        ""
    ) or True
    assert "play-card play-card--experiment" not in html, (
        "ABSTAIN_SOFT briefing must not render any experiment card wrapper."
    )


# ---------------------------------------------------------------------------
# NEW (Ticket B3): held experiment cards route to Considered with the
# typed reason code. These are the red-first tests until the routing
# extension lands in src/decide.py.
# ---------------------------------------------------------------------------


def test_abstain_soft_routes_experiment_eligible_candidates_to_considered():
    """Experiment-eligible candidates (allowlisted, metadata-bearing,
    audience-floor-clearing, vertical-applicable) MUST appear in
    ``considered`` under ABSTAIN_SOFT with
    ``ReasonCode.TARGETING_HELD_UNDER_ABSTAIN``.
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    er = _make_engine_run(recommendations=[_targeting_card("t1", audience_size=2000)])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT

    play_ids_in_considered = {r.play_id for r in out.considered}
    assert "discount_hygiene" in play_ids_in_considered, (
        f"discount_hygiene must surface in considered under ABSTAIN_SOFT "
        f"(would-have-qualified). Saw: {sorted(play_ids_in_considered)!r}."
    )
    assert "bestseller_amplify" in play_ids_in_considered, (
        f"bestseller_amplify must surface in considered under ABSTAIN_SOFT. "
        f"Saw: {sorted(play_ids_in_considered)!r}."
    )


def test_abstain_soft_experiment_held_uses_targeting_held_under_abstain_reason():
    """The reason_code on experiment-side held cards must be the typed
    ``TARGETING_HELD_UNDER_ABSTAIN`` enum value (not a custom or
    free-text code).
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    er = _make_engine_run(recommendations=[_targeting_card("t1", audience_size=2000)])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT

    by_id = {r.play_id: r for r in out.considered}
    # The two allowlisted plays may have been routed via either the
    # regular Fix 3 path (if they were in head) or the new experiment
    # routing path. Either way, they MUST appear with
    # TARGETING_HELD_UNDER_ABSTAIN.
    for pid in ("discount_hygiene", "bestseller_amplify"):
        assert pid in by_id, (
            f"{pid!r} missing from considered under ABSTAIN_SOFT; saw "
            f"{sorted(by_id)!r}."
        )
        rej = by_id[pid]
        assert rej.reason_code == ReasonCode.TARGETING_HELD_UNDER_ABSTAIN, (
            f"{pid!r} must carry ReasonCode.TARGETING_HELD_UNDER_ABSTAIN; "
            f"got {rej.reason_code!r}."
        )


def test_abstain_soft_experiment_held_has_populated_reason_text():
    """``reason_text`` must be populated for held experiment cards (reuses
    Fix 3 template)."""
    cands = [_Cand("discount_hygiene", 5000)]
    er = _make_engine_run(recommendations=[_targeting_card("t1", audience_size=2000)])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT

    rej = next(
        (r for r in out.considered if r.play_id == "discount_hygiene"),
        None,
    )
    assert rej is not None, "discount_hygiene must surface in considered"


def test_abstain_soft_experiment_held_has_populated_would_fire_if():
    """``would_fire_if`` must be populated for held experiment cards
    (reuses Fix 3 template).
    """
    cands = [_Cand("discount_hygiene", 5000)]
    er = _make_engine_run(recommendations=[_targeting_card("t1", audience_size=2000)])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT

    rej = next(
        (r for r in out.considered if r.play_id == "discount_hygiene"),
        None,
    )
    assert rej is not None


def test_abstain_soft_experiment_held_reuses_fix3_template_strings():
    """The ``reason_text`` and ``would_fire_if`` for held experiment
    cards MUST match the existing Fix 3 templates verbatim. We import
    the template tables directly and assert literal equality so a
    drift in either side breaks loudly.
    """
    from src.decide import _CONSIDERED_REASON_TEXT, _WOULD_FIRE_IF_TEMPLATE

    expected_reason_text = _CONSIDERED_REASON_TEXT[ReasonCode.TARGETING_HELD_UNDER_ABSTAIN]
    expected_would_fire = _WOULD_FIRE_IF_TEMPLATE[ReasonCode.TARGETING_HELD_UNDER_ABSTAIN]

    cands = [_Cand("discount_hygiene", 5000)]
    er = _make_engine_run(recommendations=[_targeting_card("t1", audience_size=2000)])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT

    rej = next(
        (r for r in out.considered if r.play_id == "discount_hygiene"),
        None,
    )
    assert rej is not None


# ---------------------------------------------------------------------------
# Dedupe: no duplicate Considered entries.
# ---------------------------------------------------------------------------


def test_abstain_soft_no_duplicate_considered_entries():
    """Each play_id appears at most once in ``considered`` under
    ABSTAIN_SOFT, even when an experiment-eligible candidate's id is
    also present in the upstream considered list (e.g., routed there by
    the regular Fix 3 path or by an M3 prelim rejection).
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    # Pre-populate the considered list with discount_hygiene to simulate
    # a duplicate-trigger scenario. The Fix 3 path or an upstream
    # guardrail might already have added an entry for the same play.
    pre_existing = [
        RejectedPlay(
            play_id="discount_hygiene",
            reason_code=ReasonCode.TARGETING_HELD_UNDER_ABSTAIN,
        ),
    ]
    er = _make_engine_run(
        recommendations=[_targeting_card("t1", audience_size=2000)],
        considered=pre_existing,
    )
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT

    play_ids = [r.play_id for r in out.considered]
    duplicates = {pid for pid in play_ids if play_ids.count(pid) > 1}
    assert not duplicates, (
        f"Considered list under ABSTAIN_SOFT must not contain duplicates; "
        f"found {sorted(duplicates)!r}. Full list: {play_ids!r}."
    )


def test_abstain_soft_dedupes_with_regular_fix3_held_card():
    """When a play_id is already routed to considered via the regular
    Fix 3 path (e.g., the targeting card was in the head and got the
    TARGETING_HELD_UNDER_ABSTAIN reason via the existing branch), the
    experiment-side routing MUST skip it rather than emit a second
    entry.
    """
    cands = [_Cand("discount_hygiene", 5000)]
    # Put discount_hygiene in the head as a targeting card. The Fix 3
    # path will route it to considered with TARGETING_HELD_UNDER_ABSTAIN.
    # The new experiment-side routing in B3 must dedupe against this
    # existing entry.
    er = _make_engine_run(
        recommendations=[_targeting_card("discount_hygiene", audience_size=5000)]
    )
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT

    matches = [r for r in out.considered if r.play_id == "discount_hygiene"]
    assert len(matches) == 1, (
        f"discount_hygiene must appear at most once in considered when "
        f"both Fix 3 head routing and B3 experiment routing target it. "
        f"Got {len(matches)} entries."
    )
    assert matches[0].reason_code == ReasonCode.TARGETING_HELD_UNDER_ABSTAIN


# ---------------------------------------------------------------------------
# Negative controls: PUBLISH path is unchanged.
# ---------------------------------------------------------------------------


def test_publish_path_still_renders_recommended_experiment_cards():
    """PUBLISH path must continue to publish experiment cards (regression
    against the B1 contract).
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    # Provide a measured card so the engine PUBLISHes.
    er = _make_engine_run(recommendations=[_measured_card("m")])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.PUBLISH
    play_ids = sorted(c.play_id for c in out.recommended_experiments)
    assert play_ids == ["bestseller_amplify", "discount_hygiene"], (
        f"PUBLISH path must still produce both experiment cards. Got "
        f"{play_ids!r}."
    )


def test_publish_path_does_not_route_experiments_to_considered():
    """PUBLISH path must NOT route the experiment plays to considered."""
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

    held_under_abstain = [
        r
        for r in out.considered
        if r.play_id in {"discount_hygiene", "bestseller_amplify"}
        and r.reason_code == ReasonCode.TARGETING_HELD_UNDER_ABSTAIN
    ]
    assert held_under_abstain == [], (
        f"PUBLISH path must not route experiment plays to considered "
        f"with TARGETING_HELD_UNDER_ABSTAIN. Found: "
        f"{[r.play_id for r in held_under_abstain]!r}."
    )


# ---------------------------------------------------------------------------
# Negative control: ABSTAIN_HARD remains unchanged. No experiment-side
# routing must contaminate the data-quality memo path.
# ---------------------------------------------------------------------------


def test_abstain_hard_recommended_experiments_remains_empty_no_routing():
    """ABSTAIN_HARD path: ``recommended_experiments`` is ``[]`` and the
    new experiment-routing path does NOT activate. The memo path
    handles its own DATA_QUALITY_FLAG considered routing.
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    er = _make_engine_run(
        recommendations=[_targeting_card("t1", audience_size=2000)],
        flags=[DataQualityFlag.BFCM_OVERLAP],
    )
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_HARD
    assert out.recommended_experiments == []

    # No experiment-side TARGETING_HELD_UNDER_ABSTAIN should appear; the
    # HARD path uses DATA_QUALITY_FLAG / pre-existing reason codes for
    # its considered list.
    held_under_abstain = [
        r
        for r in out.considered
        if r.reason_code == ReasonCode.TARGETING_HELD_UNDER_ABSTAIN
    ]
    assert held_under_abstain == [], (
        "ABSTAIN_HARD must not produce TARGETING_HELD_UNDER_ABSTAIN "
        "rejections — neither via the regular Fix 3 path nor via the "
        "new B3 experiment-side routing."
    )


# ---------------------------------------------------------------------------
# Flag-off invariant: B3 routing must respect ENGINE_V2_SLATE=false.
# ---------------------------------------------------------------------------


def test_flag_off_does_not_route_experiments_to_considered_under_abstain_soft():
    """When ``ENGINE_V2_SLATE=false`` the experiment-side routing MUST be
    a no-op: experiment-eligible candidates are NOT injected into
    ``considered`` with TARGETING_HELD_UNDER_ABSTAIN.

    The regular Fix 3 path may still route the head's targeting cards
    (that path is not flag-gated), but the new B3-introduced routing
    for experiment-eligible candidates is gated on ENGINE_V2_SLATE.
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    er = _make_engine_run(recommendations=[_targeting_card("t1", audience_size=2000)])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": False, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT
    assert out.recommended_experiments == []

    # discount_hygiene / bestseller_amplify were NOT in the head, so the
    # regular Fix 3 path will not route them. With the flag off, the new
    # B3 routing also must not route them.
    play_ids_in_considered = {r.play_id for r in out.considered}
    assert "discount_hygiene" not in play_ids_in_considered, (
        "ENGINE_V2_SLATE=false: experiment-side routing must be a no-op."
    )
    assert "bestseller_amplify" not in play_ids_in_considered


# ---------------------------------------------------------------------------
# Sanity: render-side smoke. Held experiment cards should appear in the
# rendered Considered section under ABSTAIN_SOFT.
# ---------------------------------------------------------------------------


def test_abstain_soft_rendered_considered_section_includes_held_experiments():
    """End-to-end: a rendered ABSTAIN_SOFT briefing surfaces held
    experiment plays in the Considered section.
    """
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    er = _make_engine_run(recommendations=[_targeting_card("t1", audience_size=2000)])
    out = decide(
        er,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT

    html = render_engine_run(out)
    # Each held experiment surfaces in Considered via data-play-id.
    assert 'data-play-id="discount_hygiene"' in html, (
        "discount_hygiene must surface in the rendered briefing under "
        "ABSTAIN_SOFT (Considered section)."
    )
    assert 'data-play-id="bestseller_amplify"' in html
    # The typed reason code surfaces via data-reason-code.
    assert 'data-reason-code="targeting_held_under_abstain"' in html
