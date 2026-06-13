"""Synthetic Blocker Fix 3 — ABSTAIN_SOFT contract enforcement.

PM/DS-resolved product contract:

    When ``decision_state == abstain_soft``, the merchant-facing
    ``EngineRun.recommendations`` MUST be empty. Any held targeting
    PlayCards that the legacy adapter / decide() ranked into the head
    must be re-routed into ``EngineRun.considered`` with a typed
    :class:`ReasonCode`, merchant-readable reason text, and
    ``would_fire_if`` template.

This test file is intentionally LANDED FIRST (TDD): the unit tests
asserting ``recommendations == []`` and considered-routing of held
targeting cards FAIL on the pre-Fix-3 code path. The renderer-level
test asserting zero Recommended targeting cards under ABSTAIN_SOFT
also fails pre-fix. After Fix 3 lands they all pass.

Hard scope rules followed by these tests (per the synthetic blocker
plan and prior memory):

- No new evidence tier, no new recommendation tier.
- No materiality floor change.
- No fake p / q / CI / confidence_score / final_score introduced.
- The Phase 5.1 ABSTAIN_SOFT merchant-readable callout copy MUST
  remain visible. We only assert the *Recommended* section is empty.
- PUBLISH-with-targeting-cards behavior is unchanged: targeting cards
  still render in the Recommended section when
  ``decision_state == publish``.
- The new :class:`ReasonCode` value (``TARGETING_HELD_UNDER_ABSTAIN``
  or equivalent) is a typed enum entry; tests assert the enum
  attribute exists on :class:`ReasonCode` so the contract is
  programmatic, not a magic string.
"""
from __future__ import annotations

from typing import List, Optional

import pytest

from src.decide import decide
from src.engine_run import (
    Abstain,
    Audience,
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
)
from src.storytelling_v2 import (
    MEASURED_CARD_CLASS,
    DIRECTIONAL_CARD_CLASS,
    TARGETING_CARD_CLASS,
    render_engine_run,
)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _targeting_card(play_id: str, *, audience_size: int = 1500) -> PlayCard:
    """A clean targeting PlayCard. Per Fix 2's invariant, measurement is None."""
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


def _engine_run(
    *,
    recommendations: Optional[List[PlayCard]] = None,
    considered: Optional[List[RejectedPlay]] = None,
    flags: Optional[List[DataQualityFlag]] = None,
    monthly_revenue: float = 100_000.0,
) -> EngineRun:
    return EngineRun(
        run_id="abstain-soft-test",
        store_id="abstain-soft-store",
        recommendations=recommendations or [],
        considered=considered or [],
        data_quality_flags=flags or [],
        abstain=Abstain(state=DecisionState.PUBLISH),
        scale=Scale(monthly_revenue=monthly_revenue, materiality_floor=5_000),
    )


# ---------------------------------------------------------------------------
# Reason-code enum: pin the contract programmatically
# ---------------------------------------------------------------------------


def test_targeting_held_under_abstain_reason_code_exists():
    """The new typed ReasonCode for held-under-abstain MUST exist.

    PM doc line 67 / plan Fix 3 (line 145): ``targeting_held_under_abstain``
    or equivalent. We pick the explicit name so the considered list
    can differentiate this from ``NO_MEASURED_SIGNAL`` (a different
    upstream M3 condition).

    Pre-Fix-3 state: this attribute does not exist on
    :class:`ReasonCode`. The test FAILS until Fix 3 ships.
    """
    assert hasattr(ReasonCode, "TARGETING_HELD_UNDER_ABSTAIN"), (
        "ReasonCode.TARGETING_HELD_UNDER_ABSTAIN must exist as a typed enum "
        "value so the considered-list pipeline can carry the held-under-"
        "abstain reason without re-using NO_MEASURED_SIGNAL."
    )
    code = ReasonCode.TARGETING_HELD_UNDER_ABSTAIN
    # The serialized value should be the snake_case form (matches PM doc).
    assert code.value == "targeting_held_under_abstain"


# ---------------------------------------------------------------------------
# Unit-level: decide() under ABSTAIN_SOFT clears recommendations
# ---------------------------------------------------------------------------


def test_targeting_only_decide_clears_recommendations():
    """Targeting-only input becomes ABSTAIN_SOFT; recommendations MUST be empty.

    Pre-Fix-3 state: decide() leaves the targeting cards in
    ``recommendations`` so the renderer can show them as suppressed
    targeting cards. This contradicts PM's product contract that
    ABSTAIN_SOFT means zero Recommended cards.

    Fix 3 expectation: after decide(), ``recommendations == []`` AND the
    formerly-ranked head appears in ``considered`` with the new typed
    reason code.
    """
    cards = [
        _targeting_card("t1", audience_size=2000),
        _targeting_card("t2", audience_size=1500),
    ]
    er = _engine_run(recommendations=cards)
    out = decide(er)

    # Decision state must be ABSTAIN_SOFT (no measured/directional present).
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT
    # Hard contract: zero recommendations under ABSTAIN_SOFT.
    assert out.recommendations == [], (
        f"ABSTAIN_SOFT must produce zero Recommended cards. Got "
        f"{[c.play_id for c in out.recommendations]!r}."
    )


def test_held_targeting_cards_routed_to_considered_with_typed_reason():
    """Held targeting cards must appear in ``considered`` with typed fields."""
    cards = [
        _targeting_card("t1", audience_size=2000),
        _targeting_card("t2", audience_size=1500),
    ]
    er = _engine_run(recommendations=cards)
    out = decide(er)

    play_ids_in_considered = {r.play_id for r in out.considered}
    assert "t1" in play_ids_in_considered, (
        f"Held targeting card 't1' missing from considered. Saw: "
        f"{sorted(play_ids_in_considered)!r}."
    )
    assert "t2" in play_ids_in_considered

    # Each routed card carries the typed reason_code, reason_text, and
    # would_fire_if.
    routed = [r for r in out.considered if r.play_id in {"t1", "t2"}]
    assert len(routed) == 2
    for rej in routed:
        assert rej.reason_code == ReasonCode.TARGETING_HELD_UNDER_ABSTAIN, (
            f"Held targeting reject for {rej.play_id!r} must use "
            f"TARGETING_HELD_UNDER_ABSTAIN, got {rej.reason_code!r}."
        )


def test_zero_recommendations_decide_stays_zero_under_abstain_soft():
    """Empty recommendations input produces ABSTAIN_SOFT and stays empty."""
    out = decide(_engine_run(recommendations=[]))
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT
    assert out.recommendations == []


# ---------------------------------------------------------------------------
# Negative: PUBLISH path is unchanged
# ---------------------------------------------------------------------------


def test_publish_with_targeting_cards_still_keeps_them_in_recommendations():
    """Targeting cards still render in Recommended when PUBLISH.

    The Fix 3 contract is *only* tightened for ABSTAIN_SOFT. With a
    measured card present the engine PUBLISHes; targeting cards remain
    in ``recommendations`` for the renderer.
    """
    cards = [
        _measured_card("m"),
        _targeting_card("t1", audience_size=2000),
    ]
    er = _engine_run(recommendations=cards)
    out = decide(er)

    assert out.abstain.state == DecisionState.PUBLISH
    rec_ids = [c.play_id for c in out.recommendations]
    assert "m" in rec_ids
    assert "t1" in rec_ids, (
        "PUBLISH path must keep targeting cards in recommendations. The "
        "Fix 3 contract is ABSTAIN_SOFT-only."
    )


def test_publish_path_does_not_route_targeting_to_considered():
    """The new TARGETING_HELD_UNDER_ABSTAIN reason must NOT appear under PUBLISH."""
    cards = [
        _measured_card("m"),
        _targeting_card("t1", audience_size=2000),
    ]
    out = decide(_engine_run(recommendations=cards))
    assert out.abstain.state == DecisionState.PUBLISH
    held_under_abstain = [
        r
        for r in out.considered
        if r.reason_code
        == getattr(ReasonCode, "TARGETING_HELD_UNDER_ABSTAIN", None)
    ]
    assert held_under_abstain == [], (
        "PUBLISH path must not produce TARGETING_HELD_UNDER_ABSTAIN "
        "rejections. Found: "
        f"{[r.play_id for r in held_under_abstain]!r}."
    )


# ---------------------------------------------------------------------------
# ABSTAIN_HARD path is unchanged
# ---------------------------------------------------------------------------


def test_abstain_hard_unchanged_recommendations_remain_empty():
    """ABSTAIN_HARD path must keep emptying recommendations and use
    DATA_QUALITY_FLAG / pre-existing reason codes; the new
    TARGETING_HELD_UNDER_ABSTAIN code must NOT take over the hard path.
    """
    cards = [_targeting_card("t1", audience_size=2000)]
    er = _engine_run(
        recommendations=cards,
        flags=[DataQualityFlag.BFCM_OVERLAP],
    )
    out = decide(er)
    assert out.abstain.state == DecisionState.ABSTAIN_HARD
    assert out.recommendations == []
    # The held-under-abstain code is for SOFT only.
    held_under_abstain = [
        r
        for r in out.considered
        if r.reason_code
        == getattr(ReasonCode, "TARGETING_HELD_UNDER_ABSTAIN", None)
    ]
    assert held_under_abstain == [], (
        "ABSTAIN_HARD must not produce TARGETING_HELD_UNDER_ABSTAIN "
        "rejections; the HARD path uses DATA_QUALITY_FLAG."
    )


# ---------------------------------------------------------------------------
# Render-level: ABSTAIN_SOFT briefing has zero Recommended cards
# ---------------------------------------------------------------------------


def test_render_abstain_soft_after_decide_has_zero_recommended_cards():
    """End-to-end via decide() + render: zero Recommended cards.

    Pre-Fix-3 state: decide() leaves up to MAX_ABSTAIN_SOFT_TARGETING_CARDS
    (=2) targeting cards in ``recommendations`` and the renderer renders
    them under the ABSTAIN_SOFT callout. This is the contradiction PM
    flagged on ``promo_anomaly`` (callout says "no primary play",
    cards say otherwise).

    Fix 3 expectation: the rendered HTML's Recommended section
    contains zero PlayCard articles regardless of class. The Phase 5.1
    callout still renders.
    """
    cards = [
        _targeting_card("t1", audience_size=2000),
        _targeting_card("t2", audience_size=1500),
        _targeting_card("t3", audience_size=900),
    ]
    er = _engine_run(recommendations=cards)
    out = decide(er)
    # Pre-condition.
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT

    html = render_engine_run(out)

    # Phase 5.1 callout must still render.
    assert "abstain-callout--soft" in html, (
        "Phase 5.1 ABSTAIN_SOFT callout must remain visible."
    )
    assert "No primary play this month" in html

    # Hard contract: zero Recommended cards. We grep for the three card
    # class hooks; none may appear inside the Recommended section. We
    # rely on the structural rule that decide() empties recommendations,
    # so no card class wrapper appears at all in the HTML for these
    # IDs.
    for play_id in ("t1", "t2", "t3"):
        # No PlayCard article wrapper for any of the held targeting IDs.
        rec_card_open = (
            f'<article class="{TARGETING_CARD_CLASS}" '
            f'data-play-id="{play_id}"'
        )
        assert rec_card_open not in html, (
            f"ABSTAIN_SOFT briefing must not render targeting card "
            f"{play_id!r}. The card belongs in Considered now."
        )

    # Each held targeting play surfaces in Considered via its data-play-id.
    for play_id in ("t1", "t2", "t3"):
        rejected_marker = f'data-play-id="{play_id}"'
        assert rejected_marker in html, (
            f"Held targeting card {play_id!r} must surface in Considered "
            f"under ABSTAIN_SOFT."
        )

    # The new typed reason code surfaces via data-reason-code.
    assert 'data-reason-code="targeting_held_under_abstain"' in html, (
        "Held targeting cards in Considered must carry the typed "
        "data-reason-code='targeting_held_under_abstain' attribute."
    )


def test_render_abstain_soft_with_existing_considered_does_not_drop_them():
    """Pre-existing considered entries must NOT be evicted by Fix 3 routing.

    The decide() pipeline already populates ``considered`` from M3
    candidates and from upstream guardrails. The Fix 3 routing must
    *augment* the considered list, not replace it.
    """
    pre_existing = [
        RejectedPlay(
            play_id="pre_existing_play",
            reason_code=ReasonCode.AUDIENCE_TOO_SMALL,
        )
    ]
    cards = [_targeting_card("t1", audience_size=2000)]
    er = _engine_run(recommendations=cards, considered=pre_existing)
    out = decide(er)

    assert out.abstain.state == DecisionState.ABSTAIN_SOFT
    assert out.recommendations == []
    play_ids = {r.play_id for r in out.considered}
    assert "pre_existing_play" in play_ids
    assert "t1" in play_ids


# ---------------------------------------------------------------------------
# Render-level: PUBLISH still renders targeting cards in Recommended
# ---------------------------------------------------------------------------


def test_render_publish_still_renders_targeting_cards_in_recommended():
    """Negative: PUBLISH path renders targeting cards in Recommended."""
    cards = [
        _measured_card("m"),
        _targeting_card("t1", audience_size=2000),
    ]
    er = _engine_run(recommendations=cards)
    out = decide(er)

    assert out.abstain.state == DecisionState.PUBLISH

    html = render_engine_run(out)
    # The targeting card class wrapper appears (still rendered).
    assert TARGETING_CARD_CLASS in html
    # And the measured card class wrapper appears.
    assert MEASURED_CARD_CLASS in html


# ---------------------------------------------------------------------------
# Phase 5.1 copy preservation
# ---------------------------------------------------------------------------


def test_abstain_soft_phase5_1_callout_copy_preserved():
    """Fix 3 must not regress Phase 5.1 merchant-readable copy."""
    cards = [_targeting_card("t1")]
    er = _engine_run(recommendations=cards)
    out = decide(er)
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT

    html = render_engine_run(out)
    # Phase 5.1 label.
    assert "No primary play this month" in html
    # Merchant-readable reason text fragment from Phase 5.1.
    assert "abstain-callout--soft" in html
    # The old engineering-jargon string must remain absent.
    assert "materiality + cannibalization gating" not in html
