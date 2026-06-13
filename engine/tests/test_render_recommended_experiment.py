"""Phase 6A Ticket B1 — Recommended Experiment renderer tests.

Pins the V2 renderer contract for the Recommended Experiment section
introduced by Ticket B1. The data flow into the renderer is:

- Ticket A4 added :data:`EngineRun.recommended_experiments` and the
  decide-layer eligibility selector (behind ``ENGINE_V2_SLATE``).
- Ticket A4.5 plumbed live Phase 5 / M3 candidates from ``main.py`` into
  ``decide()`` so the field is populated end-to-end.
- Ticket B1 (this) renders the populated list as a merchant-facing
  section between Recommended Now and Watching.

Hard rules under test (per
``agent_outputs/implementation-manager-campaign-slate-plan.md`` §B1 and
``agent_outputs/campaign-slate-contract-final.md``):

- Section CSS class is ``recommended-experiment``.
- Section appears AFTER ``section.recommended`` and BEFORE
  ``section.watching`` in DOM order.
- Each card in ``engine_run.recommended_experiments`` renders exactly
  one ``article.play-card`` under ``section.recommended-experiment``.
- The ``would_be_measured_by`` enum is rendered with one of the three
  approved merchant-readable strings; free-text rendering is forbidden.
- The Phase 5.1 opportunity-context block renders verbatim via the
  existing helper (no copy edits, no math change).
- The "This is not projected lift" disclaimer appears on the card.
- ``revenue_range.suppressed=True`` is preserved (no $ headline).
- Standalone $ headline is forbidden in this section (M8 invariant).
- ABSTAIN_SOFT path renders zero experiment cards.
- ABSTAIN_HARD path renders the data-quality memo and the experiment
  section MUST NOT appear.

This file is the red-first forcing function for B1. The renderer MUST
emit ``section.recommended-experiment`` ONLY when the list is non-empty
and the wrapper class MUST be the literal ``recommended-experiment`` so
DOM-only readers can target it.
"""
from __future__ import annotations

import re
from typing import List

import pytest

from src.engine_run import (
    Abstain,
    Audience,
    DataQualityFlag,
    DataWindow,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Measurement,
    NonLiftAtom,
    OpportunityContext,
    PlayCard,
    RevenueRange,
    RevenueRangeSource,
    Scale,
    WatchedSignal,
    WouldBeMeasuredBy,
)
from src.storytelling_v2 import (
    OPPORTUNITY_CONTEXT_CLASS,
    OPPORTUNITY_CONTEXT_DISCLAIMER,
    render_engine_run,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


# Match any standalone dollar amount with at least one digit after $.
_DOLLAR_RE = re.compile(r"\$[\d][\d,]*")


def _experiment_card(
    *,
    play_id: str,
    audience_size: int,
    would_be_measured_by: WouldBeMeasuredBy,
    with_opportunity: bool = True,
) -> PlayCard:
    """Build a Recommended Experiment-shaped PlayCard.

    Mirrors the shape produced by
    ``src.decide._select_recommended_experiments`` (Ticket A4):
    ``evidence_class=TARGETING``, ``measurement=None``,
    ``revenue_range.suppressed=True`` with an
    ``experiment_no_calibrated_lift`` driver, and a populated
    ``would_be_measured_by`` enum value.
    """
    audience = Audience(
        size=audience_size,
        definition="recent buyers in eligible segment",
    )
    revenue_range = RevenueRange(
        suppressed=True,
        drivers=[{"reason": "experiment_no_calibrated_lift"}],
    )
    opp = None
    if with_opportunity:
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


def _publish_engine_run_with_experiments(
    experiments: List[PlayCard],
    *,
    recommendations: List[PlayCard] = None,
) -> EngineRun:
    er = EngineRun(
        store_id="b1_test",
        anchor_date="2026-04-30T00:00:00",
        data_window=DataWindow(primary_window="L28"),
        cold_start=False,
        data_quality_flags=[],
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=list(recommendations or []),
        recommended_experiments=list(experiments),
        considered=[],
        watching=[
            WatchedSignal(
                metric="aov",
                current=58.0,
                prior=55.6,
                trend="up",
                threshold_to_act="AOV moves +5% sustained 2 windows",
            ),
        ],
        scale=Scale(monthly_revenue=180000, materiality_floor=5400),
    )
    return er


def _abstain_soft_engine_run() -> EngineRun:
    er = _publish_engine_run_with_experiments([])
    er.abstain = Abstain(
        state=DecisionState.ABSTAIN_SOFT,
    )
    # ABSTAIN_SOFT contract (Ticket A4): recommended_experiments forced to [].
    er.recommended_experiments = []
    return er


def _abstain_hard_engine_run() -> EngineRun:
    er = _publish_engine_run_with_experiments([])
    er.abstain = Abstain(
        state=DecisionState.ABSTAIN_HARD,
    )
    er.data_quality_flags = [DataQualityFlag.BFCM_OVERLAP]
    er.recommended_experiments = []
    return er


def _extract_section(html: str, section_class: str) -> str:
    """Return the substring of ``html`` for the section with the given class.

    Uses a simple ``<section ... class="...{section_class}..."`` -> matching
    ``</section>`` scan. The renderer does not nest sections.
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


def _count_play_cards_under_section(html: str, section_class: str) -> int:
    section = _extract_section(html, section_class)
    if not section:
        return 0
    # Each play card is wrapped in <article ... class="play-card ...">.
    return section.count("<article")


# ---------------------------------------------------------------------------
# Section presence and card count
# ---------------------------------------------------------------------------


def test_section_renders_when_recommended_experiments_non_empty():
    """Non-empty list -> section renders with the contract CSS class."""
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
            ),
        ]
    )
    html = render_engine_run(er)
    assert 'class="recommended-experiment"' in html


def test_section_absent_when_recommended_experiments_empty():
    """Empty list -> the section MUST NOT render at all (clean DOM)."""
    er = _publish_engine_run_with_experiments([])
    html = render_engine_run(er)
    assert 'class="recommended-experiment"' not in html


def test_section_renders_one_card_per_experiment():
    """List of 2 experiments -> exactly 2 ``article`` cards in the section."""
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
            ),
            _experiment_card(
                play_id="bestseller_amplify",
                audience_size=1475,
                would_be_measured_by=WouldBeMeasuredBy.INCREMENTAL_ORDERS_IN_14D,
            ),
        ]
    )
    html = render_engine_run(er)
    count = _count_play_cards_under_section(html, "recommended-experiment")
    assert count == 2, f"expected 2 cards under section.recommended-experiment, got {count}"


def test_section_renders_zero_cards_when_list_empty_via_publish():
    """Sanity: PUBLISH state with empty list still renders no section."""
    er = _publish_engine_run_with_experiments([])
    html = render_engine_run(er)
    count = _count_play_cards_under_section(html, "recommended-experiment")
    assert count == 0


# ---------------------------------------------------------------------------
# DOM order: Recommended Now -> Recommended Experiment -> Watching
# ---------------------------------------------------------------------------


def test_section_appears_between_recommended_and_watching():
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
            ),
        ]
    )
    html = render_engine_run(er)
    rec_idx = html.find('class="recommended"')
    exp_idx = html.find('class="recommended-experiment"')
    watch_idx = html.find('class="watching"')
    assert rec_idx >= 0, "Recommended Now section missing"
    assert exp_idx >= 0, "Recommended Experiment section missing"
    assert watch_idx >= 0, "Watching section missing"
    assert rec_idx < exp_idx < watch_idx, (
        f"DOM order wrong: recommended={rec_idx} experiment={exp_idx} watching={watch_idx}"
    )


# ---------------------------------------------------------------------------
# Title and lede
# ---------------------------------------------------------------------------


def test_section_title_is_recommended_experiment():
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
            ),
        ]
    )
    html = render_engine_run(er)
    section = _extract_section(html, "recommended-experiment")
    assert "Recommended Experiment" in section


def test_section_lede_frames_send_and_measure_not_proven_lift():
    """The lede frames experiments as send-and-measure, never as proven lift."""
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
            ),
        ]
    )
    html = render_engine_run(er)
    section = _extract_section(html, "recommended-experiment")
    # Loose substring match: "measure" must appear in the lede framing.
    assert "measure" in section.lower(), (
        "Recommended Experiment lede must frame the section as send-and-measure."
    )


# ---------------------------------------------------------------------------
# would_be_measured_by enum -> approved display copy
# ---------------------------------------------------------------------------


_WOULD_BE_MEASURED_DISPLAY = {
    WouldBeMeasuredBy.INCREMENTAL_ORDERS_IN_14D: (
        "We will measure incremental orders in 14 days."
    ),
    WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D: (
        "We will measure email-attributed revenue in 7 days."
    ),
    WouldBeMeasuredBy.REPEAT_PURCHASE_IN_30D: (
        "We will measure repeat purchase in 30 days."
    ),
}


@pytest.mark.parametrize(
    "enum_value,expected_text",
    list(_WOULD_BE_MEASURED_DISPLAY.items()),
)
def test_would_be_measured_by_enum_renders_approved_display_copy(
    enum_value, expected_text
):
    """Each enum value maps to exactly the contract-approved merchant copy."""
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2000,
                would_be_measured_by=enum_value,
            ),
        ]
    )
    html = render_engine_run(er)
    section = _extract_section(html, "recommended-experiment")
    assert section, "Recommended Experiment section did not render"
    assert expected_text in section, (
        f"Expected approved display copy {expected_text!r} for enum "
        f"{enum_value!r}; section: {section!r}"
    )


def test_no_free_text_would_be_measured_by_rendering():
    """The raw enum string must never appear; only the approved display copy."""
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2000,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
            ),
        ]
    )
    html = render_engine_run(er)
    # Raw enum value (UPPER_SNAKE_CASE) must not appear in merchant HTML.
    assert "EMAIL_ATTRIBUTED_REVENUE_IN_7D" not in html
    assert "INCREMENTAL_ORDERS_IN_14D" not in html
    assert "REPEAT_PURCHASE_IN_30D" not in html


# ---------------------------------------------------------------------------
# Phase 5.1 opportunity-context block
# ---------------------------------------------------------------------------


def test_opportunity_context_block_renders_on_experiment_card():
    """The Phase 5.1 helper must render verbatim on experiment cards."""
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
                with_opportunity=True,
            ),
        ]
    )
    html = render_engine_run(er)
    section = _extract_section(html, "recommended-experiment")
    assert section, "Recommended Experiment section did not render"
    # The block helper class is the deterministic marker.
    assert OPPORTUNITY_CONTEXT_CLASS in section, (
        "Phase 5.1 opportunity-context block is missing on Recommended "
        "Experiment cards."
    )


def test_opportunity_context_disclaimer_renders_on_experiment_card():
    """The 'This is not projected lift' disclaimer appears verbatim."""
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
                with_opportunity=True,
            ),
        ]
    )
    html = render_engine_run(er)
    section = _extract_section(html, "recommended-experiment")
    assert "not projected lift" in section, (
        "Disclaimer 'not projected lift' must render on experiment cards."
    )


# ---------------------------------------------------------------------------
# Send-to-N audience framing
# ---------------------------------------------------------------------------


def test_audience_size_renders_with_people_framing():
    """The audience block reuses the existing 'N people' framing."""
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
            ),
        ]
    )
    html = render_engine_run(er)
    section = _extract_section(html, "recommended-experiment")
    # The existing audience block emits "<N> people"; reuse pins this.
    assert "2,251" in section
    assert "people" in section


# ---------------------------------------------------------------------------
# revenue_range.suppressed remains true
# ---------------------------------------------------------------------------


def test_revenue_range_suppressed_remains_true_on_experiment_cards():
    """The selector stamps suppressed=True; the renderer must not unset it."""
    cards = [
        _experiment_card(
            play_id="discount_hygiene",
            audience_size=2251,
            would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
        ),
        _experiment_card(
            play_id="bestseller_amplify",
            audience_size=1475,
            would_be_measured_by=WouldBeMeasuredBy.INCREMENTAL_ORDERS_IN_14D,
        ),
    ]
    er = _publish_engine_run_with_experiments(cards)
    # Pin the structural invariant on the EngineRun first.
    for c in er.recommended_experiments:
        assert c.revenue_range is not None
        assert c.revenue_range.suppressed is True

    # Render and confirm no $ value leaks into the experiment section.
    html = render_engine_run(er)
    section = _extract_section(html, "recommended-experiment")
    # The opportunity-context block emits 'about $X' framing; that is allowed
    # body copy. We must not see a standalone $ headline outside the
    # opportunity-context block.
    # Strip the opportunity-context block, then assert no $ pattern remains.
    stripped = _strip_opportunity_blocks(section)
    assert not _DOLLAR_RE.search(stripped), (
        f"Recommended Experiment card has a standalone $ headline outside "
        f"the opportunity-context block: {stripped!r}"
    )


def _strip_opportunity_blocks(section_html: str) -> str:
    """Remove every ``play-card-opportunity`` div for the M8 invariant scan."""
    out = section_html
    while True:
        idx = out.find(OPPORTUNITY_CONTEXT_CLASS)
        if idx < 0:
            break
        open_idx = out.rfind("<div", 0, idx)
        if open_idx < 0:
            break
        # Match the closing </div> for this block. The opportunity-context
        # block is structured as <div class="...">...</div> with a fixed
        # depth of one (no nested divs in this helper).
        close_idx = out.find("</div>", idx)
        if close_idx < 0:
            break
        out = out[:open_idx] + out[close_idx + len("</div>") :]
    return out


# ---------------------------------------------------------------------------
# ABSTAIN_SOFT path
# ---------------------------------------------------------------------------


def test_abstain_soft_renders_zero_experiment_cards():
    """ABSTAIN_SOFT forces recommended_experiments=[]; no section renders."""
    er = _abstain_soft_engine_run()
    html = render_engine_run(er)
    count = _count_play_cards_under_section(html, "recommended-experiment")
    assert count == 0
    # No section wrapper either, since the contract is "render no section
    # when the list is empty".
    assert 'class="recommended-experiment"' not in html


# ---------------------------------------------------------------------------
# ABSTAIN_HARD path
# ---------------------------------------------------------------------------


def test_abstain_hard_does_not_render_experiment_section():
    """ABSTAIN_HARD path renders only the data-quality memo."""
    er = _abstain_hard_engine_run()
    html = render_engine_run(er)
    assert 'class="recommended-experiment"' not in html
    # And confirm the memo path was selected.
    assert "Data quality memo" in html


# ---------------------------------------------------------------------------
# Forbidden-token guards inside the experiment section (light invariant pin)
# ---------------------------------------------------------------------------


def test_no_forbidden_statistical_strings_in_experiment_section():
    """Sanity: none of the existing forbidden statistical tokens leak in."""
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
            ),
        ]
    )
    html = render_engine_run(er)
    section = _extract_section(html, "recommended-experiment")
    forbidden = [
        "p =",
        "q =",
        "p-value",
        "q-value",
        "confidence_score",
        "final_score",
        "CI [",
        "p_internal",
        "ci_internal",
    ]
    for needle in forbidden:
        assert needle not in section, (
            f"Forbidden statistical token {needle!r} appeared in "
            f"section.recommended-experiment"
        )


def test_no_aura_or_beacon_score_in_experiment_section():
    """Phase 5.5 forbidden-token sweep extension (light pin)."""
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="bestseller_amplify",
                audience_size=1475,
                would_be_measured_by=WouldBeMeasuredBy.INCREMENTAL_ORDERS_IN_14D,
            ),
        ]
    )
    html = render_engine_run(er)
    section = _extract_section(html, "recommended-experiment")
    for needle in ["Aura", "aura", "Beacon Score", "beacon_score"]:
        assert needle not in section


# ---------------------------------------------------------------------------
# Sibling sections still render
# ---------------------------------------------------------------------------


def test_recommended_now_section_still_renders_with_experiment_section():
    """Adding the new section must not remove the existing Recommended Now."""
    rec_card = PlayCard(
        play_id="first_to_second_purchase",
        evidence_class=EvidenceClass.DIRECTIONAL,
        audience=Audience(size=5560, definition="L28 first-time buyers"),
        measurement=Measurement(
            metric="returning_customer_share",
            observed_effect=0.045,
            n=5560,
            primary_window="L28",
            consistency_across_windows=3,
        ),
        revenue_range=RevenueRange(
            suppressed=True,
            source=RevenueRangeSource.STORE_OBSERVED,
        ),
    )
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
            ),
        ],
        recommendations=[rec_card],
    )
    html = render_engine_run(er)
    assert 'class="recommended"' in html
    assert 'class="recommended-experiment"' in html
    assert 'class="watching"' in html
