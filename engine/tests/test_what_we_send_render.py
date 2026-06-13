"""Phase 6B Ticket C1 — Surface "What we'd send" mechanism copy.

Pins the V2 renderer contract for the new "What we'd send:" line surfaced
on Recommended Now (directional + measured) and Recommended Experiment
cards. The mechanism string is loaded from ``config/priors.yaml`` via the
priors metadata accessor (Phase 6A Ticket A3) and rendered at render
time only — it is NOT a typed PlayCard field.

Hard rules under test (per
``agent_outputs/implementation-manager-phase6b-founder-feedback-plan.md``
§3 and the Ticket C1 acceptance criteria):

- The line renders as
  ``<p class="play-card__what-we-send"><strong>What we'd send:</strong>
  {escaped mechanism}</p>``.
- Render on Recommended Now (directional / measured) cards.
- Render on Recommended Experiment cards.
- Do NOT render on Considered cards.
- Do NOT render on Watching rows (rows are metric-only li elements).
- Do NOT render under ABSTAIN_HARD (no recommended cards exist there).
- If the mechanism string is missing/empty for a play, omit the line
  entirely (no empty box, no placeholder copy).

The test fixtures use real play_ids that carry metadata in priors.yaml
(``discount_hygiene``, ``bestseller_amplify``) so the mechanism lookup
hits the production priors metadata path. ``winback_21_45`` carries no
metadata block in priors.yaml today and is used as the
"missing mechanism" negative-control fixture.
"""
from __future__ import annotations

import re

from src.engine_run import (
    Abstain,
    Audience,
    DataWindow,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Measurement,
    NonLiftAtom,
    OpportunityContext,
    PlayCard,
    ReasonCode,
    RejectedPlay,
    RevenueRange,
    Scale,
    WatchedSignal,
    WouldBeMeasuredBy,
)
from src.priors_loader import get_play_metadata
from src.storytelling_v2 import render_engine_run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_WWS_CLASS: str = "play-card__what-we-send"


def _extract_section(html: str, section_class: str) -> str:
    """Return the substring of ``html`` for the section with the given class.

    Mirrors the simple section extractor used by
    ``tests/test_render_recommended_experiment.py``.
    """
    needle = f'class="{section_class}"'
    idx = html.find(needle)
    if idx < 0:
        return ""
    open_idx = html.rfind("<section", 0, idx)
    if open_idx < 0:
        return ""
    close_idx = html.find("</section>", idx)
    if close_idx < 0:
        return ""
    return html[open_idx : close_idx + len("</section>")]


def _experiment_card(
    *,
    play_id: str,
    audience_size: int,
    would_be_measured_by: WouldBeMeasuredBy,
) -> PlayCard:
    """Build a Recommended Experiment-shaped PlayCard.

    Mirrors the shape produced by
    ``src.decide._select_recommended_experiments`` (Ticket A4) plus the
    ``opportunity_context`` populated by Ticket B1.5.
    """
    audience = Audience(
        size=audience_size,
        definition="recent buyers in eligible segment",
    )
    revenue_range = RevenueRange(
        suppressed=True,
        drivers=[{"reason": "experiment_no_calibrated_lift"}],
    )
    opp = OpportunityContext(
        audience_size=audience_size,
        non_lift=NonLiftAtom(
            value=float(audience_size) * 69.0,
            semantic="addressable_opportunity",
            aov_used=69.0,
            monthly_revenue_estimate=float(audience_size) * 69.0,
        ),
        aov_window="L28",
        aov_source="store_observed",
    )
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.TARGETING,
        audience=audience,
        measurement=None,
        revenue_range=revenue_range,
        opportunity_context=opp,
        would_be_measured_by=would_be_measured_by,
    )


def _directional_card(
    *,
    play_id: str,
    audience_size: int = 2251,
) -> PlayCard:
    """Build a directional Recommended Now-shaped PlayCard.

    Mirrors the directional shape produced by Phase 5 (evidence_class =
    DIRECTIONAL, no measurement effect rendered, opportunity context
    populated, revenue_range suppressed).
    """
    audience = Audience(
        size=audience_size,
        definition="single-purchase customers",
    )
    revenue_range = RevenueRange(suppressed=True)
    opp = OpportunityContext(
        audience_size=audience_size,
        non_lift=NonLiftAtom(
            value=float(audience_size) * 59.0,
            semantic="addressable_opportunity",
            aov_used=59.0,
            monthly_revenue_estimate=float(audience_size) * 59.0,
        ),
        aov_window="L28",
        aov_source="store_observed",
    )
    measurement = Measurement(
        metric="returning_customer_share",
        consistency_across_windows=3,
    )
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.DIRECTIONAL,
        audience=audience,
        measurement=measurement,
        revenue_range=revenue_range,
        opportunity_context=opp,
    )


def _publish_engine_run(
    *,
    recommendations=None,
    recommended_experiments=None,
    considered=None,
    watching=None,
) -> EngineRun:
    return EngineRun(
        store_id="c1_test",
        anchor_date="2026-04-30T00:00:00",
        data_window=DataWindow(primary_window="L28"),
        cold_start=False,
        data_quality_flags=[],
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=list(recommendations or []),
        recommended_experiments=list(recommended_experiments or []),
        considered=list(considered or []),
        watching=list(
            watching
            or [
                WatchedSignal(
                    metric="aov",
                    current=58.0,
                    prior=55.6,
                    trend="up",
                    threshold_to_act="AOV moves +5% sustained 2 windows",
                ),
            ]
        ),
        scale=Scale(monthly_revenue=180_000.0, materiality_floor=5_400.0),
    )


# ---------------------------------------------------------------------------
# Required tests (per Ticket C1 acceptance)
# ---------------------------------------------------------------------------


def test_mechanism_renders_on_recommended_directional() -> None:
    """A directional Recommended Now card whose play_id carries a
    mechanism in priors.yaml MUST render the "What we'd send:" line
    inside ``section.recommended``.

    We use ``discount_hygiene`` as the play_id (it is one of the two
    plays with a metadata block in ``config/priors.yaml`` today)
    stamped as DIRECTIONAL so this test exercises the directional /
    measured render path in :func:`_render_measured_card`.
    """
    md = get_play_metadata("discount_hygiene")
    assert md is not None and md.mechanism, (
        "Test fixture sanity: discount_hygiene must have a mechanism in "
        "config/priors.yaml for this test to be meaningful."
    )
    expected_mechanism = md.mechanism

    er = _publish_engine_run(
        recommendations=[
            _directional_card(play_id="discount_hygiene"),
        ],
    )
    html = render_engine_run(er)
    section = _extract_section(html, "recommended")
    assert section, "section.recommended did not render"

    assert _WWS_CLASS in section, (
        f"Expected the {_WWS_CLASS!r} class to appear inside "
        f"section.recommended for a directional card whose play_id has a "
        f"mechanism string in priors.yaml."
    )
    assert "What we&#x27;d send:" in section or "What we'd send:" in section, (
        "Expected the 'What we'd send:' label to render inside "
        "section.recommended."
    )
    assert expected_mechanism in section, (
        f"Expected the priors.yaml mechanism string {expected_mechanism!r} "
        "to render verbatim inside section.recommended."
    )


def test_mechanism_renders_on_recommended_experiment() -> None:
    """A Recommended Experiment card whose play_id carries a mechanism
    in priors.yaml MUST render the "What we'd send:" line inside
    ``section.recommended-experiment``.
    """
    md = get_play_metadata("bestseller_amplify")
    assert md is not None and md.mechanism, (
        "Test fixture sanity: bestseller_amplify must have a mechanism in "
        "config/priors.yaml for this test to be meaningful."
    )
    expected_mechanism = md.mechanism

    er = _publish_engine_run(
        recommended_experiments=[
            _experiment_card(
                play_id="bestseller_amplify",
                audience_size=1475,
                would_be_measured_by=WouldBeMeasuredBy.REPEAT_PURCHASE_IN_30D,
            ),
        ],
    )
    html = render_engine_run(er)
    section = _extract_section(html, "recommended-experiment")
    assert section, "section.recommended-experiment did not render"

    assert _WWS_CLASS in section, (
        f"Expected the {_WWS_CLASS!r} class to appear inside "
        f"section.recommended-experiment."
    )
    assert "What we&#x27;d send:" in section or "What we'd send:" in section, (
        "Expected the 'What we'd send:' label inside "
        "section.recommended-experiment."
    )
    assert expected_mechanism in section, (
        f"Expected the priors.yaml mechanism string {expected_mechanism!r} "
        "to render verbatim inside section.recommended-experiment."
    )


def test_mechanism_absent_on_considered_and_watching() -> None:
    """The "What we'd send:" line MUST NOT appear inside
    ``section.considered`` or ``section.watching``. Considered is not
    the place for action copy; Watching is metric-only.

    We populate Considered with a play_id whose metadata block exists
    (``discount_hygiene``) so the mechanism string would be available
    if the renderer mistakenly looked it up. The test forces the
    section-scope rule: the line is absent regardless of metadata
    availability.
    """
    rejected = RejectedPlay(
        play_id="discount_hygiene",
        reason_code=ReasonCode.NO_MEASURED_SIGNAL,
    )
    er = _publish_engine_run(
        considered=[rejected],
        watching=[
            WatchedSignal(
                metric="aov",
                current=58.0,
                prior=55.6,
                trend="up",
                threshold_to_act="AOV moves +5% sustained 2 windows",
            ),
        ],
    )
    html = render_engine_run(er)
    considered_section = _extract_section(html, "considered")
    watching_section = _extract_section(html, "watching")

    assert considered_section, "section.considered did not render"
    assert watching_section, "section.watching did not render"

    assert _WWS_CLASS not in considered_section, (
        f"{_WWS_CLASS!r} must NOT appear inside section.considered "
        "(Considered is not the place for action copy)."
    )
    assert "What we'd send" not in considered_section and (
        "What we&#x27;d send" not in considered_section
    ), (
        "'What we'd send' label must NOT appear inside section.considered."
    )

    assert _WWS_CLASS not in watching_section, (
        f"{_WWS_CLASS!r} must NOT appear inside section.watching "
        "(Watching rows are metric-only)."
    )
    assert "What we'd send" not in watching_section and (
        "What we&#x27;d send" not in watching_section
    ), (
        "'What we'd send' label must NOT appear inside section.watching."
    )


def test_mechanism_omits_when_string_missing() -> None:
    """When a play_id has NO metadata block in ``config/priors.yaml``,
    the renderer MUST omit the "What we'd send:" line entirely on its
    Recommended Now / Recommended Experiment card.

    ``winback_21_45`` carries the legacy list-form priors block with no
    ``metadata:`` section, so :func:`get_play_metadata` returns
    ``None`` for it (verified inline as a sanity check).

    Hard rule: silence is preferable to hallucination. We do NOT render
    an empty paragraph, an empty box, or placeholder copy.
    """
    md = get_play_metadata("winback_21_45")
    assert md is None, (
        "Test fixture sanity: winback_21_45 must have NO metadata block "
        "in config/priors.yaml for this test to be meaningful."
    )

    # 1. Recommended Now (directional) — no mechanism, line omitted.
    er_directional = _publish_engine_run(
        recommendations=[_directional_card(play_id="winback_21_45")],
    )
    html_directional = render_engine_run(er_directional)
    rec_section = _extract_section(html_directional, "recommended")
    assert rec_section, "section.recommended did not render"
    assert _WWS_CLASS not in rec_section, (
        f"{_WWS_CLASS!r} must NOT render when the play_id has no "
        "mechanism in priors.yaml."
    )
    assert "What we'd send" not in rec_section and (
        "What we&#x27;d send" not in rec_section
    ), (
        "'What we'd send' label must NOT appear when mechanism is missing."
    )

    # 2. Recommended Experiment — no mechanism, line omitted.
    er_experiment = _publish_engine_run(
        recommended_experiments=[
            _experiment_card(
                play_id="winback_21_45",
                audience_size=686,
                would_be_measured_by=WouldBeMeasuredBy.REPEAT_PURCHASE_IN_30D,
            ),
        ],
    )
    html_experiment = render_engine_run(er_experiment)
    exp_section = _extract_section(html_experiment, "recommended-experiment")
    assert exp_section, "section.recommended-experiment did not render"
    assert _WWS_CLASS not in exp_section, (
        f"{_WWS_CLASS!r} must NOT render when the play_id has no "
        "mechanism in priors.yaml."
    )
    assert "What we'd send" not in exp_section and (
        "What we&#x27;d send" not in exp_section
    ), (
        "'What we'd send' label must NOT appear when mechanism is missing."
    )

    # 3. Defensive: no orphan empty <p> with the WWS class anywhere.
    assert "<p class=\"play-card__what-we-send\"></p>" not in html_directional
    assert "<p class=\"play-card__what-we-send\"></p>" not in html_experiment


# ---------------------------------------------------------------------------
# Phase 6B Ticket C1.5 tightening: exercise the realistic Beauty fixture path
# ---------------------------------------------------------------------------


def test_mechanism_renders_for_first_to_second_purchase_directional() -> None:
    """Phase 6B Ticket C1.5: the Beauty Brand pinned-slate Recommended Now
    card is ``first_to_second_purchase`` (an evidence_class=DIRECTIONAL
    card). Before C1.5 that play carried no metadata block in
    ``config/priors.yaml`` and the renderer correctly omitted the
    "What we'd send:" line. C1.5 adds the metadata block; this test
    pins that the directional ``first_to_second_purchase`` card now
    surfaces the priors-authored mechanism string verbatim.

    This test tightens the C1 contract: the original
    :func:`test_mechanism_renders_on_recommended_directional` artificially
    stamped ``discount_hygiene`` as DIRECTIONAL; this test exercises the
    realistic Beauty Brand fixture's actual directional play_id end-to-end.
    """
    md = get_play_metadata("first_to_second_purchase")
    assert md is not None and md.mechanism, (
        "Phase 6B Ticket C1.5 contract: first_to_second_purchase must "
        "carry a metadata block with a non-empty mechanism string in "
        "config/priors.yaml. If this assertion fires, Ticket C1.5 has "
        "been reverted or the YAML drifted."
    )
    expected_mechanism = md.mechanism

    er = _publish_engine_run(
        recommendations=[_directional_card(play_id="first_to_second_purchase")],
    )
    html = render_engine_run(er)
    section = _extract_section(html, "recommended")
    assert section, "section.recommended did not render"

    assert _WWS_CLASS in section, (
        f"Expected the {_WWS_CLASS!r} class to appear inside "
        f"section.recommended for the first_to_second_purchase directional "
        "card now that priors.yaml carries its mechanism metadata."
    )
    assert "What we&#x27;d send:" in section or "What we'd send:" in section, (
        "Expected the 'What we'd send:' label to render for "
        "first_to_second_purchase."
    )
    assert expected_mechanism in section, (
        f"Expected the priors.yaml mechanism string {expected_mechanism!r} "
        "to render verbatim inside section.recommended for "
        "first_to_second_purchase."
    )
