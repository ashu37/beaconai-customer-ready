"""Phase 5.1 follow-up — Addressable opportunity context on V2
recommended cards.

The Phase 5.6 directional card for ``first_to_second_purchase``
correctly suppresses ``revenue_range`` because the supporting signal
is a state statistic, not an intervention effect. Merchants still need
economic context before deciding whether to run a campaign. This file
pins the contract that:

- When ``revenue_range.suppressed=True`` AND a populated
  :class:`OpportunityContext` is present, the V2 directional card
  surfaces an addressable opportunity context block (audience size x
  recent AOV = addressable order value) AS BODY COPY with an explicit
  "not projected lift" disclaimer.
- When AOV is unavailable, the block is omitted (no fabrication).
- The opportunity context never appears as a hero / headline metric.
- The M8 targeting-no-dollar-headline invariant continues to hold.
- No forbidden statistical strings (p =, q =, CI, confidence_score,
  final_score, p_internal, ci_internal) appear in the V2 briefing.
- The Phase 5.6 contract that ``revenue_range.suppressed`` remains
  true on the directional card is unchanged.
"""
from __future__ import annotations

import re

from src.detect import Candidate
from src.engine_run import (
    Abstain,
    Audience,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Measurement,
    NonLiftAtom,
    OpportunityContext,
    PlayCard,
    RevenueRange,
    Scale,
)
from src.measurement_builder import (
    build_directional_play_card,
)
from src.storytelling_v2 import (
    OPPORTUNITY_CONTEXT_CLASS,
    OPPORTUNITY_CONTEXT_DISCLAIMER,
    render_engine_run,
    render_play_card,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _aligned_with_aov(aov: float = 69.0) -> dict:
    """Synthetic Beauty-style aligned snapshot with an L28 AOV."""
    return {
        "L28": {
            "aov": aov,
            "returning_customer_share": 0.915,
            "delta": {"returning_customer_share": 0.066},
            "p": {"returning_customer_share": 9.5e-5},
            "meta": {"identified_recent": 962},
        },
        "L56": {
            "aov": aov - 1,
            "returning_customer_share": 0.83,
            "delta": {"returning_customer_share": 0.32},
            "p": {"returning_customer_share": 1e-30},
            "meta": {"identified_recent": 1296},
        },
        "L90": {
            "aov": aov - 2,
            "returning_customer_share": 0.68,
            "delta": {"returning_customer_share": 2.5},
            "p": {"returning_customer_share": 4e-139},
            "meta": {"identified_recent": 1457},
        },
    }


def _aligned_without_aov() -> dict:
    """Aligned snapshot where every window's AOV is missing / non-positive."""
    return {
        "L28": {
            "returning_customer_share": 0.915,
            "delta": {"returning_customer_share": 0.066},
            "p": {"returning_customer_share": 9.5e-5},
            "meta": {"identified_recent": 962},
        },
        "L56": {
            "aov": 0,  # zero == not available
            "returning_customer_share": 0.83,
            "delta": {"returning_customer_share": 0.32},
            "p": {"returning_customer_share": 1e-30},
            "meta": {"identified_recent": 1296},
        },
        "L90": {
            "aov": None,
            "returning_customer_share": 0.68,
            "delta": {"returning_customer_share": 2.5},
            "p": {"returning_customer_share": 4e-139},
            "meta": {"identified_recent": 1457},
        },
    }


def _f2s_candidate(audience_size: int = 286) -> Candidate:
    return Candidate(
        play_id="first_to_second_purchase",
        audience_size=audience_size,
        segment_definition="customers with exactly one historical order",
        data_used=["g.customer_id", "g.Name"],
        preliminary_rejection_reason=None,
        cold_start=False,
    )


# ---------------------------------------------------------------------------
# 1. Suppressed directional PlayCard with audience + AOV renders the block
# ---------------------------------------------------------------------------


def test_directional_card_with_audience_and_aov_carries_opportunity_context():
    cand = _f2s_candidate(audience_size=286)
    aligned = _aligned_with_aov(aov=69.0)
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    # Phase 5.6 invariant unchanged: revenue range still suppressed.
    assert card.revenue_range is not None
    assert card.revenue_range.suppressed is True
    # Phase 5.1: opportunity_context populated.
    opp = card.opportunity_context
    assert opp is not None
    assert opp.audience_size == 286
    # S13.6-T3: monetary numerics live inside the NonLiftAtom wrapper.
    assert opp.non_lift.aov_used == 69.0
    assert opp.aov_window == "L28"
    assert opp.aov_source == "store_observed"
    # value = audience_size * aov_used (no realization factor).
    assert opp.non_lift.value == 286 * 69.0
    assert opp.non_lift.monthly_revenue_estimate == 286 * 69.0
    assert opp.non_lift.semantic == "addressable_opportunity"


def test_v2_briefing_renders_opportunity_context_block():
    cand = _f2s_candidate(audience_size=286)
    aligned = _aligned_with_aov(aov=69.0)
    card = build_directional_play_card(cand, aligned)
    assert card is not None

    er = EngineRun(
        store_id="phase5_1",
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[card],
        scale=Scale(monthly_revenue=120_000.0, materiality_floor=10_000.0),
    )
    html = render_engine_run(er)
    # Block class hook is present.
    assert OPPORTUNITY_CONTEXT_CLASS in html
    # Audience and AOV both surface verbatim.
    assert "286" in html
    assert "$69" in html
    # Addressable value is rounded to "about $X" framing.
    assert "about $19" in html  # 286 * 69 = 19,734 -> "about $19.7k"
    # Phrase that scopes the meaning is present.
    assert "Opportunity context" in html
    assert "addressable order value" in html


# ---------------------------------------------------------------------------
# 2. Opportunity context includes the "not projected lift" disclaimer
# ---------------------------------------------------------------------------


def test_opportunity_context_includes_not_projected_lift_disclaimer():
    cand = _f2s_candidate(audience_size=400)
    aligned = _aligned_with_aov(aov=80.0)
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    er = EngineRun(
        store_id="phase5_1",
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[card],
    )
    html = render_engine_run(er)
    # Loose substring check on the load-bearing phrase, not the entire
    # sentence, so the test is not brittle to copy edits.
    assert "not projected lift" in html


def test_opportunity_context_disclaimer_is_the_module_constant():
    """Module-level constant is the canonical merchant-facing copy."""
    assert "not projected lift" in OPPORTUNITY_CONTEXT_DISCLAIMER
    assert "size of the audience" in OPPORTUNITY_CONTEXT_DISCLAIMER


# ---------------------------------------------------------------------------
# 3. Opportunity context renders as body copy, not a hero / headline
# ---------------------------------------------------------------------------


def test_opportunity_context_does_not_render_as_hero_or_headline():
    """The opportunity context block must be body copy.

    Verified structurally: the block must (a) live inside the play
    card's <article>, (b) come AFTER the headline (h3 title + class
    badge), and (c) NOT carry any heading-level (h1/h2/h3) markup.
    """
    cand = _f2s_candidate(audience_size=286)
    aligned = _aligned_with_aov(aov=69.0)
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    er = EngineRun(
        store_id="phase5_1",
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[card],
    )
    html = render_engine_run(er)

    # The actual rendered block (not the CSS rule) carries a
    # ``class="play-card-opportunity"`` attribute. Locate it precisely
    # to discriminate from the inline <style> block.
    block_attr = f'class="{OPPORTUNITY_CONTEXT_CLASS}"'
    block_idx = html.find(block_attr)
    assert block_idx > 0, "Rendered opportunity-context block not found."

    # The card title element appears BEFORE the opportunity-context
    # block (the block is body copy, not the headline).
    title_idx = html.find('class="play-card__title"')
    assert 0 < title_idx < block_idx, (
        "Opportunity context block rendered before the headline; "
        "must be body copy."
    )

    # The class badge ("Emerging") also appears before the block.
    badge_idx = html.find(">Emerging<")
    assert 0 < badge_idx < block_idx, (
        "Opportunity context block rendered before the class badge; "
        "must be body copy below the headline."
    )

    # The block must not introduce its own h1/h2/h3 heading.
    # Find the slice that contains the block, then assert no heading
    # tag is present within it.
    block_start = html.rfind("<div", 0, block_idx)
    assert block_start >= 0
    block_end = html.find("</div>", block_idx)
    assert block_end > block_start
    block_html = html[block_start: block_end + len("</div>")]
    assert "<h1" not in block_html
    assert "<h2" not in block_html
    assert "<h3" not in block_html


def test_opportunity_context_block_uses_paragraph_markup_only():
    """Body copy should be <p> elements, never <h*> headings."""
    cand = _f2s_candidate(audience_size=286)
    aligned = _aligned_with_aov(aov=69.0)
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    html = render_play_card(card, scale=Scale(monthly_revenue=120_000))
    # The block exists and uses <p> markup.
    assert OPPORTUNITY_CONTEXT_CLASS in html
    # Find the block boundaries.
    start = html.find(OPPORTUNITY_CONTEXT_CLASS)
    block = html[start:]
    # The disclaimer/line are wrapped in <p>...</p> tags.
    assert "<p" in block.split("</div>")[0]


# ---------------------------------------------------------------------------
# 4. AOV missing -> block omitted, no fabricated value
# ---------------------------------------------------------------------------


def test_opportunity_context_omitted_when_aov_unavailable():
    cand = _f2s_candidate(audience_size=286)
    aligned = _aligned_without_aov()
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    # Phase 5.6 still fires (signal is present); only the opportunity
    # context block is omitted.
    assert card.opportunity_context is None

    er = EngineRun(
        store_id="phase5_1",
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[card],
    )
    html = render_engine_run(er)
    # No opportunity-context block markup on the rendered page.
    # The class string also lives in the <style> block; the test
    # discriminates by checking for the actual rendered <div> with the
    # class attribute (vs. the class name appearing in the CSS rules).
    assert 'class="play-card-opportunity"' not in html
    # Also no fabricated dollar value appears on the directional card.
    # We allow the materiality footer's $X copy to remain because that
    # is the page-level scale block, not the per-card opportunity block.


def test_opportunity_context_omitted_when_audience_zero():
    """Defensive: a zero audience produces no opportunity context."""
    cand = Candidate(
        play_id="first_to_second_purchase",
        audience_size=0,
        segment_definition="empty",
        data_used=[],
        preliminary_rejection_reason=None,
    )
    # audience_size <= 0 fails the directional pathway entirely.
    aligned = _aligned_with_aov(aov=69.0)
    card = build_directional_play_card(cand, aligned)
    assert card is None  # the gate also rejects zero-audience candidates


def test_opportunity_context_renders_when_revenue_range_suppressed_only():
    """The block must NOT render when revenue_range is calibrated.

    If a future change unsuppresses the range, the engine should
    surface the calibrated range; the addressable-value block is a
    fallback for the suppressed case only.
    """
    # Build a synthetic measured card with a calibrated range AND an
    # opportunity_context. The block should be hidden because
    # revenue_range is the better signal.
    from src.engine_run import RevenueRangeSource

    measured_card = PlayCard(
        play_id="winback_21_45",
        evidence_class=EvidenceClass.MEASURED,
        confidence_label="Strong",
        audience=Audience(size=200, definition="lapsed L21-L45"),
        measurement=Measurement(
            metric="reactivation_rate",
            observed_effect=0.04,
            n=200,
            primary_window="L28",
            consistency_across_windows=2,
        ),
        revenue_range=RevenueRange(
            p10=672.0,
            p50=832.0,
            p90=1056.0,
            source=RevenueRangeSource.STORE_OBSERVED,
            drivers=[],
            suppressed=False,
        ),
        opportunity_context=OpportunityContext(
            audience_size=200,
            non_lift=NonLiftAtom(
                value=16000.0,
                semantic="addressable_opportunity",
                aov_used=80.0,
                monthly_revenue_estimate=16000.0,
            ),
        ),
    )
    html = render_play_card(measured_card, scale=Scale(monthly_revenue=120_000))
    # Calibrated range chip surfaces.
    assert "Estimated range" in html
    # Addressable opportunity block is suppressed in favor of the chip.
    assert 'class="play-card-opportunity"' not in html


# ---------------------------------------------------------------------------
# 5. Forbidden tokens absent in V2 briefing
# ---------------------------------------------------------------------------


def test_opportunity_context_does_not_introduce_forbidden_tokens():
    cand = _f2s_candidate(audience_size=286)
    aligned = _aligned_with_aov(aov=69.0)
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    er = EngineRun(
        store_id="phase5_1",
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[card],
    )
    html = render_engine_run(er)
    forbidden = [
        "p =",
        "q =",
        "CI",
        "confidence_score",
        "final_score",
        "p_internal",
        "ci_internal",
    ]
    for needle in forbidden:
        assert needle not in html, (
            f"Forbidden token {needle!r} appeared in V2 briefing with "
            "opportunity context block."
        )


def test_opportunity_context_does_not_introduce_forecast_terms():
    """Hard prohibition: never call this expected revenue, projected lift,
    p50, expected impact, or any forecast term in an *affirmative* sense.

    The block intentionally contains the negation "not projected lift"
    as the load-bearing disclaimer; this test pins that no affirmative
    forecast claim is made.
    """
    cand = _f2s_candidate(audience_size=286)
    aligned = _aligned_with_aov(aov=69.0)
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    er = EngineRun(
        store_id="phase5_1",
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[card],
    )
    html = render_engine_run(er)

    # Find the actual rendered opportunity-context block (not the CSS
    # rule that also references the class name).
    block_attr = f'class="{OPPORTUNITY_CONTEXT_CLASS}"'
    block_idx = html.find(block_attr)
    assert block_idx > 0
    block_end = html.find("</div>", block_idx)
    block = html[block_idx: block_end + len("</div>")]
    block_lower = block.lower()

    # Affirmative-claim forecast tokens (not preceded by "not").
    forbidden_affirmative = [
        "expected revenue",
        "expected impact",
        "p50",
        "forecast",
        "predicted",
    ]
    for term in forbidden_affirmative:
        assert term.lower() not in block_lower, (
            f"Forecast-flavored term {term!r} appeared inside the "
            "opportunity context block."
        )

    # The phrase "projected lift" appears only inside the negation
    # ("not projected lift"). Verify it's preceded by "not ".
    if "projected lift" in block_lower:
        idx = block_lower.find("projected lift")
        prefix = block_lower[max(0, idx - 5): idx]
        assert "not " in prefix, (
            "'projected lift' appeared in the opportunity context block "
            "outside the disclaimer negation."
        )


# ---------------------------------------------------------------------------
# 6. Phase 5.6 invariants preserved: revenue_range.suppressed remains true
# ---------------------------------------------------------------------------


def test_revenue_range_remains_suppressed_with_opportunity_context():
    cand = _f2s_candidate(audience_size=286)
    aligned = _aligned_with_aov(aov=69.0)
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    rr = card.revenue_range
    assert rr is not None
    assert rr.suppressed is True
    assert rr.p10 is None and rr.p50 is None and rr.p90 is None


def test_directional_card_still_has_no_range_chip():
    """Phase 5.6 contract: suppressed range -> no range chip."""
    cand = _f2s_candidate(audience_size=286)
    aligned = _aligned_with_aov(aov=69.0)
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    er = EngineRun(
        store_id="phase5_1",
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[card],
    )
    html = render_engine_run(er)
    assert 'class="play-card-range-chip"' not in html
    assert "Estimated range" not in html


# ---------------------------------------------------------------------------
# 7. Targeting cards: invariant must hold even with opportunity context
# ---------------------------------------------------------------------------


def test_targeting_card_with_opportunity_context_still_has_no_dollar_headline():
    """Defensive: even if a targeting card carries opportunity_context
    (e.g. a future change wires it), the M8 invariant must hold.

    The opportunity context block is body copy and may legitimately
    carry $ in body text, but it MUST NOT replace the existing
    targeting-card "Why no $ projection" copy as a hero metric, and
    the existing targeting-no-dollar-headline test invariant
    (`test_targeting_no_dollar_headline.py`) must still pass.

    For this Phase 5.1 follow-up, the renderer hides the
    opportunity-context block on targeting cards entirely (the
    targeting renderer never calls the helper). This test pins that
    behavior.
    """
    targeting_card = PlayCard(
        play_id="bestseller_amplify",
        evidence_class=EvidenceClass.TARGETING,
        confidence_label="Targeting",
        audience=Audience(size=1500, definition="L28 buyers"),
        revenue_range=RevenueRange(suppressed=True, drivers=[]),
        opportunity_context=OpportunityContext(
            audience_size=1500,
            non_lift=NonLiftAtom(
                value=90_000.0,
                semantic="addressable_opportunity",
                aov_used=60.0,
                monthly_revenue_estimate=90_000.0,
            ),
        ),
    )
    html = render_play_card(targeting_card, scale=Scale(monthly_revenue=120_000))
    # Targeting card renderer does not surface opportunity_context.
    # This protects the M8 dollar-headline invariant.
    assert 'class="play-card-opportunity"' not in html
    # The card still renders as a targeting card with no standalone $.
    assert "play-card--targeting" in html


def test_existing_targeting_no_dollar_headline_invariant_still_passes():
    """Re-run the M8 forcing function inline to be doubly-sure the
    Phase 5.1 follow-up did not regress targeting-card rendering.
    """
    # Mirror the test setup from tests/test_targeting_no_dollar_headline.py
    from src.engine_run import RevenueRangeSource

    er = EngineRun(
        store_id="invariant_test",
        recommendations=[
            PlayCard(
                play_id="bestseller_amplify",
                evidence_class=EvidenceClass.TARGETING,
                confidence_label="Targeting",
                audience=Audience(size=1500, definition="L28 buyers"),
                revenue_range=RevenueRange(
                    p10=None,
                    p50=999_999,
                    p90=2_000_000,
                    source=RevenueRangeSource.STORE_OBSERVED,
                    drivers=[],
                    suppressed=True,
                ),
                opportunity_context=OpportunityContext(
                    audience_size=1500,
                    non_lift=NonLiftAtom(
                        value=90_000.0,
                        semantic="addressable_opportunity",
                        aov_used=60.0,
                        monthly_revenue_estimate=90_000.0,
                    ),
                ),
            ),
        ],
        scale=Scale(monthly_revenue=200_000, materiality_floor=4_000),
    )
    html = render_engine_run(er)
    # Targeting card rendered.
    assert "play-card--targeting" in html
    # Opportunity-context block NOT on the targeting card.
    assert 'class="play-card-opportunity"' not in html
    # No standalone dollar headline OUTSIDE the dq-footer scale block.
    # Cheap structural check: the targeting card slice must not contain
    # "$999" or "$2,000,000".
    article_start = html.find('<article class="play-card play-card--targeting"')
    assert article_start >= 0
    article_end = html.find("</article>", article_start)
    targeting_slice = html[article_start: article_end + len("</article>")]
    assert "$999" not in targeting_slice
    assert "$2,000,000" not in targeting_slice


# ---------------------------------------------------------------------------
# 8. Rounding helper sanity
# ---------------------------------------------------------------------------


def test_addressable_value_rounding_under_10k():
    """Under $10k uses nearest-$100 framing."""
    from src.storytelling_v2 import _round_addressable_value

    assert _round_addressable_value(4_212.5) == "about $4,200"
    assert _round_addressable_value(8_950.0) == "about $9,000"
    assert _round_addressable_value(99.0) == "about $100"


def test_addressable_value_rounding_under_1m():
    """$10k - $1M uses one-decimal-of-$1k framing."""
    from src.storytelling_v2 import _round_addressable_value

    s = _round_addressable_value(19_734.0)
    assert s.startswith("about $19.7k") or s.startswith("about $19.8k") or s.startswith("about $19.6k")

    s2 = _round_addressable_value(125_000.0)
    assert "k" in s2
    assert s2.startswith("about $125") or s2.startswith("about $125.0k")


def test_addressable_value_rounding_at_or_above_1m():
    """$1M+ uses one-decimal-of-$1M framing."""
    from src.storytelling_v2 import _round_addressable_value

    assert _round_addressable_value(2_500_000.0) == "about $2.5M"
    assert _round_addressable_value(1_050_000.0) == "about $1.1M"


def test_addressable_value_rounding_handles_bad_input():
    from src.storytelling_v2 import _round_addressable_value

    assert _round_addressable_value(0.0) == ""
    assert _round_addressable_value(-100.0) == ""
    assert _round_addressable_value(float("nan")) == ""


# ---------------------------------------------------------------------------
# 9. Engine run round-trip preserves opportunity_context
# ---------------------------------------------------------------------------


def test_engine_run_to_dict_round_trip_preserves_opportunity_context():
    cand = _f2s_candidate(audience_size=286)
    aligned = _aligned_with_aov(aov=69.0)
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    er = EngineRun(
        store_id="phase5_1",
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[card],
    )
    payload = er.to_dict()
    rebuilt = EngineRun.from_dict(payload)
    rebuilt_card = rebuilt.recommendations[0]
    opp = rebuilt_card.opportunity_context
    assert opp is not None
    assert opp.audience_size == 286
    # S13.6-T3: monetary numerics live inside the NonLiftAtom wrapper.
    assert opp.non_lift.aov_used == 69.0
    assert opp.non_lift.value == 286 * 69.0
    assert opp.non_lift.monthly_revenue_estimate == 286 * 69.0
    assert opp.non_lift.semantic == "addressable_opportunity"
    assert opp.aov_window == "L28"
    assert opp.aov_source == "store_observed"
