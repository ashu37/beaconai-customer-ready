"""Phase 5.5 — V2 briefing does not render Aura / Beacon Score.

The legacy briefing includes a composite "Aura Score 77 / Healthy"
header. The V2 briefing must NOT carry any composite-score claim
(Aura, Beacon Score, health_score, etc.). Both reviews independently
rejected reintroducing it into V2.

This test pins the absence across PUBLISH, ABSTAIN_SOFT, and
ABSTAIN_HARD layouts on synthetic fixtures.
"""
from __future__ import annotations

from src.engine_run import (
    Abstain,
    Audience,
    DataQualityFlag,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Measurement,
    Observation,
    ObservationClassification,
    PlayCard,
    ReasonCode,
    RejectedPlay,
    RevenueRange,
    RevenueRangeSource,
    Scale,
    WatchedSignal,
)
from src.storytelling_v2 import render_engine_run


# The "BeaconAI" product name string is allowed (it is the product, not
# the score). The forbidden tokens are composite-score claims.
FORBIDDEN_SCORE_TOKENS = [
    "Aura",
    "Beacon Score",
    "BEACON SCORE",
    "health_score",
    "Health Score",
    "aura_score",
    "Aura Score",
]


def _publish_engine_run() -> EngineRun:
    return EngineRun(
        store_id="phase5",
        abstain=Abstain(state=DecisionState.PUBLISH),
        state_of_store=[
            Observation(
                supporting_metric="aov",
                change_magnitude=0.017,
                classification=ObservationClassification.MOVED,
            ),
        ],
        recommendations=[
            PlayCard(
                play_id="winback_21_45",
                evidence_class=EvidenceClass.MEASURED,
                audience=Audience(id="aud_lapsed", definition="L28 lapsed", size=1500),
                measurement=Measurement(
                    metric="reactivation_rate",
                    observed_effect=0.045,
                    n=1500,
                    primary_window="L28",
                    consistency_across_windows=3,
                ),
                revenue_range=RevenueRange(
                    p10=4500.0, p50=8000.0, p90=12000.0,
                    source=RevenueRangeSource.STORE_OBSERVED,
                ),
            )
        ],
        scale=Scale(monthly_revenue=120_000.0, materiality_floor=10_000.0),
    )


def _abstain_soft_engine_run() -> EngineRun:
    return EngineRun(
        store_id="phase5",
        abstain=Abstain(state=DecisionState.ABSTAIN_SOFT),
        state_of_store=[
            Observation(
                supporting_metric="aov",
                change_magnitude=0.005,
                classification=ObservationClassification.HELD,
            ),
        ],
        recommendations=[],
        considered=[
            RejectedPlay(
                play_id="bestseller_amplify",
                reason_code=ReasonCode.NO_MEASURED_SIGNAL,
            ),
        ],
        watching=[
            WatchedSignal(
                metric="returning_customer_share",
                trend="up",
                threshold_to_act="+/- 2pp to revisit retention focus",
            )
        ],
        scale=Scale(monthly_revenue=120_000.0, materiality_floor=10_000.0),
    )


def _abstain_hard_engine_run() -> EngineRun:
    return EngineRun(
        store_id="phase5",
        abstain=Abstain(
            state=DecisionState.ABSTAIN_HARD,
        ),
        data_quality_flags=[DataQualityFlag.REFUND_STORM],
        recommendations=[],
        scale=Scale(monthly_revenue=120_000.0, materiality_floor=10_000.0),
    )


def test_v2_publish_briefing_contains_no_aura_or_beacon_score():
    html = render_engine_run(_publish_engine_run())
    for token in FORBIDDEN_SCORE_TOKENS:
        assert token not in html, f"V2 PUBLISH briefing leaks {token!r}"


def test_v2_abstain_soft_briefing_contains_no_aura_or_beacon_score():
    html = render_engine_run(_abstain_soft_engine_run())
    for token in FORBIDDEN_SCORE_TOKENS:
        assert token not in html, f"V2 ABSTAIN_SOFT briefing leaks {token!r}"


def test_v2_abstain_hard_briefing_contains_no_aura_or_beacon_score():
    html = render_engine_run(_abstain_hard_engine_run())
    for token in FORBIDDEN_SCORE_TOKENS:
        assert token not in html, f"V2 ABSTAIN_HARD briefing leaks {token!r}"


def test_v2_briefing_contains_no_composite_score_phrase():
    """No "Score: NN/100" or "(healthy)" or "tier:" composite claim."""
    html = render_engine_run(_publish_engine_run())
    forbidden_phrases = [
        "/100",
        "(healthy)",
        "(at risk)",
        "tier:",
        "composite score",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in html.lower() or phrase in (
            "/100",  # let the assertion remain strict on this token
        ), f"V2 briefing leaks composite score phrase {phrase!r}"
    # Strict assertions to be sure:
    assert "/100" not in html
    assert "tier:" not in html.lower()
