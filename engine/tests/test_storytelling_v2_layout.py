"""Phase 6B Ticket C2 -- briefing section-order layout test.

Pins the V2 renderer's top-level section order:

    Recommended -> Recommended Experiment -> Watching -> Considered ->
    Data-quality footer

The merchant-facing reading order is "what to do now" -> "what to test"
-> "what to monitor" -> "what we held". The Considered (held) section
sits LAST before the data-quality footer so the muted, held-back content
does not interrupt the action-forward sections at the top of the page.

Phase 6B Ticket C2 explicitly inverted the pre-C2 order, which placed
Considered BEFORE Watching. This test guards against silent regressions
in :func:`src.storytelling_v2.render_engine_run`'s top-level
concatenation order.
"""
from __future__ import annotations

from src.engine_run import (
    Abstain,
    Audience,
    DataWindow,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Measurement,
    NonLiftAtom,
    Observation,
    ObservationClassification,
    OpportunityContext,
    PlayCard,
    ReasonCode,
    RejectedPlay,
    RevenueRange,
    RevenueRangeSource,
    Scale,
    WatchedSignal,
    WouldBeMeasuredBy,
)
from src.storytelling_v2 import render_engine_run


def _publish_engine_run_with_all_sections() -> EngineRun:
    """Build an EngineRun whose render exercises all four role sections.

    Recommended Now (1 directional card), Recommended Experiment (1
    experiment card), Considered (1 rejected card), Watching (1 row).
    """
    rec_card = PlayCard(
        play_id="winback",
        evidence_class=EvidenceClass.DIRECTIONAL,
        confidence_label="Emerging",
        audience=Audience(id="aud_lapsed", definition="L28 lapsed buyers", size=1200),
        measurement=Measurement(metric="returning_customer_share", n=1200, primary_window="L28"),
        revenue_range=RevenueRange(
            p10=2000.0,
            p50=4000.0,
            p90=7500.0,
            source=RevenueRangeSource.STORE_OBSERVED,
            drivers=[],
            suppressed=False,
        ),
    )
    exp_card = PlayCard(
        play_id="discount_hygiene",
        evidence_class=EvidenceClass.TARGETING,
        confidence_label="Run as experiment",
        audience=Audience(id="aud_dh", definition="discounted buyers L28", size=2251),
        revenue_range=RevenueRange(suppressed=True),
        opportunity_context=OpportunityContext(
            audience_size=2251,
            non_lift=NonLiftAtom(
                value=2251 * 59.0,
                semantic="addressable_opportunity",
                aov_used=59.0,
                monthly_revenue_estimate=2251 * 59.0,
            ),
            aov_window="L28",
            aov_source="store_observed",
        ),
        would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
    )
    return EngineRun(
        store_id="layout_test",
        data_window=DataWindow(primary_window="L28"),
        abstain=Abstain(state=DecisionState.PUBLISH),
        state_of_store=[
            Observation(
                classification=ObservationClassification.MOVED,
            ),
        ],
        recommendations=[rec_card],
        recommended_experiments=[exp_card],
        considered=[
            RejectedPlay(
                play_id="empty_bottle",
                reason_code=ReasonCode.NO_MEASURED_SIGNAL,
            ),
        ],
        watching=[
            WatchedSignal(
                metric="aov",
                current=58.0,
                prior=55.6,
                trend="up",
                threshold_to_act="AOV moves +5% sustained 2 windows",
            ),
        ],
        scale=Scale(monthly_revenue=180000, materiality_floor=10000),
    )


def test_section_order_recommended_experiment_watching_considered() -> None:
    """The four role sections render in the order Recommended ->
    Recommended Experiment -> Watching -> Considered.

    Phase 6B Ticket C2 contract: the held / muted Considered section
    moves BELOW Watching so the action-forward sections sit at the top
    of the page.
    """
    er = _publish_engine_run_with_all_sections()
    html = render_engine_run(er)

    rec_idx = html.find('class="recommended"')
    exp_idx = html.find('class="recommended-experiment"')
    watch_idx = html.find('class="watching"')
    cons_idx = html.find('class="considered"')
    dq_idx = html.find('class="dq-footer"')

    assert rec_idx >= 0, "section.recommended missing"
    assert exp_idx >= 0, "section.recommended-experiment missing"
    assert watch_idx >= 0, "section.watching missing"
    assert cons_idx >= 0, "section.considered missing"
    assert dq_idx >= 0, "footer.dq-footer missing"

    assert rec_idx < exp_idx < watch_idx < cons_idx < dq_idx, (
        "DOM section order wrong. Expected "
        "recommended < recommended-experiment < watching < considered < "
        f"dq-footer; got rec={rec_idx} exp={exp_idx} watch={watch_idx} "
        f"cons={cons_idx} dq={dq_idx}."
    )


def test_watching_appears_before_considered_when_no_experiments() -> None:
    """Even when the Recommended Experiment section is omitted (empty
    list -> no section node), Watching MUST still render BEFORE
    Considered. Guards the bare swap, not just the four-section path.
    """
    er = _publish_engine_run_with_all_sections()
    er.recommended_experiments = []
    html = render_engine_run(er)

    watch_idx = html.find('class="watching"')
    cons_idx = html.find('class="considered"')

    assert watch_idx >= 0, "section.watching missing"
    assert cons_idx >= 0, "section.considered missing"
    assert watch_idx < cons_idx, (
        f"Watching must render before Considered; got watch={watch_idx} "
        f"cons={cons_idx}."
    )
