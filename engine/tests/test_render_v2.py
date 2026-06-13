"""V2 renderer tests for Milestone 8.

Covers:

- Three-section layout for PUBLISH (state-of-store + Recommended +
  Considered + Watching + DQ footer).
- ABSTAIN_SOFT: standard layout, "no measured opportunities cleared"
  callout, optional 0-2 targeting cards (no $ headlines), watching /
  considered render where available so the page is still useful.
- ABSTAIN_HARD: data-quality memo, NO recommendations rendered.
- Rejected/considered card content (T8.2).
- Watching deterministic signals (T8.1).
- Data-quality footer flags + window metadata (T8.1).
- Forbidden statistical strings absent (M8 contract).
"""
from __future__ import annotations

from src.engine_run import (
    Abstain,
    Audience,
    BriefingMeta,
    DataQualityFlag,
    DataWindow,
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
from src.storytelling_v2 import (
    DIRECTIONAL_CARD_CLASS,
    MEASURED_CARD_CLASS,
    REJECTED_CARD_CLASS,
    TARGETING_CARD_CLASS,
    TARGETING_CARD_DISCLAIMER,
    render_data_quality_footer,
    render_engine_run,
    render_recommended_section,
    render_state_of_store,
    render_watching_section,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _measured_card() -> PlayCard:
    return PlayCard(
        play_id="winback",
        evidence_class=EvidenceClass.MEASURED,
        confidence_label="Strong",
        audience=Audience(
            id="aud_lapsed",
            definition="L28 lapsed customers",
            size=2400,
            fraction_of_base=0.18,
        ),
        measurement=Measurement(
            metric="returning_customer_share",
            observed_effect=0.045,
            n=2400,
            primary_window="L28",
            consistency_across_windows=3,
            p_internal=0.012,  # internal-only; must not render
            ci_internal=[0.010, 0.080],  # internal-only; must not render
        ),
        revenue_range=RevenueRange(
            p10=4500.0,
            p50=8000.0,
            p90=12500.0,
            source=RevenueRangeSource.STORE_OBSERVED,
            drivers=[{"name": "lift_estimate", "value": 0.045}],
            suppressed=False,
        ),
    )


def _directional_card() -> PlayCard:
    return PlayCard(
        play_id="discount_hygiene",
        evidence_class=EvidenceClass.DIRECTIONAL,
        confidence_label="Emerging",
        audience=Audience(
            id="aud_full_price",
            definition="Buyers who paid full price in L28",
            size=900,
            fraction_of_base=0.07,
        ),
        measurement=Measurement(
            metric="discount_share",
            observed_effect=0.032,
            n=900,
            primary_window="L28",
            consistency_across_windows=2,
            p_internal=0.06,
        ),
        revenue_range=RevenueRange(
            p10=1500.0,
            p50=2800.0,
            p90=4500.0,
            source=RevenueRangeSource.BLEND,
            drivers=[],
            suppressed=False,
        ),
    )


def _targeting_card_suppressed() -> PlayCard:
    return PlayCard(
        play_id="bestseller_amplify",
        evidence_class=EvidenceClass.TARGETING,
        confidence_label="Targeting",
        audience=Audience(
            id="aud_bestseller",
            definition="L28 buyers who purchased the top SKU",
            size=1500,
            fraction_of_base=0.12,
        ),
        revenue_range=RevenueRange(
            p10=None,
            p50=None,
            p90=None,
            source=RevenueRangeSource.VERTICAL_PRIOR,
            drivers=[],
            suppressed=True,
        ),
    )


def _publish_engine_run() -> EngineRun:
    return EngineRun(
        store_id="acme_co",
        anchor_date="2026-04-30T00:00:00",
        data_window=DataWindow(
            primary_window="L28",
            available_windows=["L7", "L28", "L56", "L90"],
            anchor_quality="good",
        ),
        cold_start=False,
        data_quality_flags=[],
        abstain=Abstain(state=DecisionState.PUBLISH),
        state_of_store=[
            Observation(
                supporting_metric="aov",
                change_magnitude=0.042,
                delta_pct=0.042,
                classification=ObservationClassification.MOVED,
            ),
            Observation(
                supporting_metric="repeat_rate_within_window",
                change_magnitude=0.001,
                classification=ObservationClassification.HELD,
            ),
        ],
        recommendations=[_measured_card(), _directional_card(), _targeting_card_suppressed()],
        considered=[
            RejectedPlay(
                play_id="category_expansion",
                reason_code=ReasonCode.AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY,
            ),
            RejectedPlay(
                play_id="journey_optimization",
                reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR,
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
        scale=Scale(monthly_revenue=180000, customer_base_est=4200, materiality_floor=5400),
        briefing_meta=BriefingMeta(vertical="beauty"),
    )


def _abstain_soft_engine_run() -> EngineRun:
    er = _publish_engine_run()
    er.abstain = Abstain(
        state=DecisionState.ABSTAIN_SOFT,
    )
    # Targeting-only fallback set.
    er.recommendations = [_targeting_card_suppressed()]
    return er


def _abstain_hard_engine_run() -> EngineRun:
    er = _publish_engine_run()
    er.abstain = Abstain(
        state=DecisionState.ABSTAIN_HARD,
    )
    er.data_quality_flags = [DataQualityFlag.BFCM_OVERLAP]
    # ABSTAIN_HARD must render no recommendations regardless of input.
    er.recommendations = [_measured_card()]
    er.considered = []
    return er


# ---------------------------------------------------------------------------
# T8.1 — Three-section renderer + state-of-store paragraph
# ---------------------------------------------------------------------------


def test_publish_renders_all_three_sections_plus_state_of_store_and_dq_footer():
    er = _publish_engine_run()
    html = render_engine_run(er)
    # State of store section.
    assert 'class="state-of-store"' in html
    # S13.6-T1b: state-of-store text is synthesized from typed numerics.
    assert "AOV moved" in html
    # Recommended section.
    assert 'class="recommended"' in html
    assert MEASURED_CARD_CLASS in html
    assert DIRECTIONAL_CARD_CLASS in html
    assert TARGETING_CARD_CLASS in html
    # Considered section.
    assert 'class="considered"' in html
    assert REJECTED_CARD_CLASS in html
    # Watching section.
    assert 'class="watching"' in html
    # DQ footer.
    assert 'class="dq-footer"' in html


def test_state_of_store_orders_moved_first_then_held():
    # S13.6-T1b: state-of-store text is synthesized from typed numerics
    # (supporting_metric + classification + delta_pct); the renderer no
    # longer reads a prose ``Observation.text`` field.
    obs = [
        Observation(
            supporting_metric="repeat_rate_within_window",
            classification=ObservationClassification.HELD,
        ),
        Observation(
            supporting_metric="aov",
            delta_pct=0.042,
            classification=ObservationClassification.MOVED,
        ),
    ]
    html = render_state_of_store(obs, store_id="acme_co")
    # MOVED observation appears before HELD in the rendered text.
    assert html.index("AOV moved") < html.index("Repeat rate held")


def test_state_of_store_empty_renders_fallback_sentence():
    html = render_state_of_store([], store_id="quiet_store")
    assert "State of store" in html
    assert "Not enough clean signal" in html


# ---------------------------------------------------------------------------
# T8.2 — Rejected-play card
# ---------------------------------------------------------------------------


def test_rejected_card_contains_reason_evidence_and_would_fire_if():
    er = _publish_engine_run()
    html = render_engine_run(er)
    # S13.6-T1a (Option D): ``reason_text`` / ``evidence_snapshot`` /
    # ``would_fire_if`` stripped per Pivot 2. Renderer surfaces only the
    # humanized reason_code summary; detail / snapshot / would-fire-if
    # prose composition is downstream's job.
    assert "Expected impact is below the materiality floor" in html
    # Reason code attribute on the card for tooling.
    assert 'data-reason-code="materiality_below_floor"' in html
    assert 'data-reason-code="audience_overlap_with_higher_priority"' in html


def test_rejected_section_caps_at_six_cards():
    er = _publish_engine_run()
    er.considered = [
        RejectedPlay(
            play_id=f"play_{i}",
            reason_code=ReasonCode.CAP_EXCEEDED,
        )
        for i in range(10)
    ]
    html = render_engine_run(er)
    rendered_count = html.count(REJECTED_CARD_CLASS)
    # Section caps at 6; only six cards may render.
    assert rendered_count <= 6


# ---------------------------------------------------------------------------
# T8.3 — Abstain renderers
# ---------------------------------------------------------------------------


def test_abstain_hard_renders_data_quality_memo_and_no_recommendations():
    er = _abstain_hard_engine_run()
    html = render_engine_run(er)
    assert "briefing-v2--abstain-hard" in html
    assert "Data quality memo" in html
    # Recommendation cards must NOT render under ABSTAIN_HARD.
    assert MEASURED_CARD_CLASS not in html
    assert DIRECTIONAL_CARD_CLASS not in html
    assert TARGETING_CARD_CLASS not in html
    # Considered cards must NOT render under ABSTAIN_HARD (no plays at all).
    assert REJECTED_CARD_CLASS not in html
    # Flag explanation.
    assert "Black Friday" in html or "BFCM" in html.upper()
    # S13.6-T1a (Option D): ``Abstain.reason`` stripped per Pivot 2.
    # The "anomalous window" / "BFCM overlap" engine-authored reason
    # text no longer renders; downstream composes from
    # data_quality_flags + decision_state.
    # Guidance for what merchant should check.
    assert "What to check" in html
    # DQ footer should still render the flag.
    assert 'class="dq-footer"' in html


def test_abstain_soft_renders_callout_and_layout_not_error_page():
    er = _abstain_soft_engine_run()
    html = render_engine_run(er)
    # Standard layout sections present.
    assert 'class="state-of-store"' in html
    assert 'class="recommended"' in html
    assert 'class="considered"' in html
    assert 'class="watching"' in html
    assert 'class="dq-footer"' in html
    # Explicit ABSTAIN_SOFT callout. Phase 5.1: merchant-readable label.
    assert "abstain-callout" in html
    assert "abstain-callout--soft" in html
    assert "No primary play this month" in html


def test_abstain_soft_renders_zero_targeting_cards():
    """Synthetic Blocker Fix 3 (PM-resolved contract):

    ``MAX_ABSTAIN_SOFT_TARGETING_CARDS`` was tightened from 2 to 0.
    The renderer must drop every targeting card under ABSTAIN_SOFT
    even if a caller wires the EngineRun with cards still in
    ``recommendations``. ``decide()`` is the canonical path that
    re-routes those cards into Considered; the renderer is the
    second line of defense.
    """
    er = _abstain_soft_engine_run()
    # Pad with extra targeting cards to verify the cap is zero.
    er.recommendations = [
        _targeting_card_suppressed(),
        _targeting_card_suppressed(),
        _targeting_card_suppressed(),
        _targeting_card_suppressed(),
    ]
    html = render_engine_run(er)
    target_count = html.count(TARGETING_CARD_CLASS)
    assert target_count == 0, (
        f"Expected zero targeting cards under ABSTAIN_SOFT (Fix 3), got {target_count}"
    )
    # Phase 5.1 callout still renders even when cards are dropped.
    assert "No primary play this month" in html


def test_abstain_soft_with_no_targeting_cards_still_renders_useful_sections():
    er = _abstain_soft_engine_run()
    er.recommendations = []  # zero cards to render
    html = render_engine_run(er)
    # The page must still feel useful.
    assert 'class="state-of-store"' in html
    assert 'class="watching"' in html
    assert 'class="considered"' in html
    # And explicitly tell the merchant nothing cleared (Phase 5.1 copy).
    assert "No primary play this month" in html


# ---------------------------------------------------------------------------
# T8.5 — Targeting card visual treatment
# ---------------------------------------------------------------------------


def test_targeting_card_has_disclaimer_and_no_dollar_headline():
    er = _publish_engine_run()
    html = render_engine_run(er)
    assert TARGETING_CARD_DISCLAIMER in html
    # Targeting card has dashed border via wrapper class; assert class hook.
    assert TARGETING_CARD_CLASS in html


def test_targeting_card_with_suppressed_range_shows_audience_aov_context_not_dollars():
    er = EngineRun(
        store_id="cold_start",
        recommendations=[_targeting_card_suppressed()],
        scale=Scale(monthly_revenue=18000),
    )
    html = render_engine_run(er)
    # Audience size present.
    assert "1,500" in html
    # Disclaimer present.
    assert TARGETING_CARD_DISCLAIMER in html
    # Suppressed-context block tells merchant why no $.
    assert "Why no $ projection" in html


# ---------------------------------------------------------------------------
# Watching section
# ---------------------------------------------------------------------------


def test_watching_section_renders_signals_with_metric_trend_and_threshold():
    signals = [
        WatchedSignal(
            metric="aov",
            current=58.0,
            prior=55.6,
            trend="up",
            threshold_to_act="AOV moves +5% sustained 2 windows",
        ),
        WatchedSignal(
            metric="repeat_rate_within_window",
            current=0.18,
            prior=0.18,
            trend="flat",
            threshold_to_act=None,
        ),
    ]
    html = render_watching_section(signals)
    assert "watching-list" in html
    assert "aov" in html
    assert "repeat rate within window" in html
    assert "Threshold to act:" in html
    # Trend arrows: rendered as &uarr;/&darr;/&rarr; (HTML entities).
    assert "&uarr;" in html  # up
    assert "&rarr;" in html  # flat


def test_watching_section_caps_at_four():
    signals = [
        WatchedSignal(metric=f"metric_{i}", trend="up", threshold_to_act=None)
        for i in range(8)
    ]
    html = render_watching_section(signals)
    # Count opening <li ...> rows; each has class="watching-row" exactly once.
    assert html.count('<li class="watching-row"') <= 4


def test_watching_section_caps_at_four_with_seven_signals_phase6a():
    """Phase 6A Ticket A1 cap pin: 7 input signals render exactly 4 rows.

    Tightens :func:`test_watching_section_caps_at_four`'s ``<= 4``
    inequality to ``== 4`` so a future regression that drops the cap
    silently to 3 (or restores it to 7) trips this test.
    """
    from src.storytelling_v2 import MAX_WATCHING_RENDERED

    assert MAX_WATCHING_RENDERED == 4

    signals = [
        WatchedSignal(metric=f"metric_{i}", trend="up", threshold_to_act=None)
        for i in range(7)
    ]
    html = render_watching_section(signals)
    assert html.count('<li class="watching-row"') == MAX_WATCHING_RENDERED


def test_watching_section_empty_renders_explicit_empty_state():
    html = render_watching_section([])
    assert "Watching" in html
    assert "No deterministic signals" in html


# ---------------------------------------------------------------------------
# Data-quality footer
# ---------------------------------------------------------------------------


def test_dq_footer_renders_flags_and_window_metadata():
    html = render_data_quality_footer(
        [DataQualityFlag.POST_PROMO_WINDOW],
        data_window=DataWindow(
            primary_window="L28",
            available_windows=["L7", "L28", "L56", "L90"],
            anchor_quality="good",
        ),
        scale=Scale(monthly_revenue=180000, materiality_floor=5400),
    )
    assert "dq-footer" in html
    assert "post-promotion" in html.lower()
    assert "Primary window: L28" in html
    assert "Anchor quality: good" in html
    assert "$180,000" in html
    assert "$5,400" in html


def test_dq_footer_with_no_flags_shows_explicit_no_flags_text():
    html = render_data_quality_footer(
        [],
        data_window=DataWindow(primary_window="L28"),
        scale=Scale(monthly_revenue=100000),
    )
    assert "No data-quality flags" in html


# ---------------------------------------------------------------------------
# Forbidden statistical strings (M8 contract invariant)
# ---------------------------------------------------------------------------


def test_publish_html_contains_no_forbidden_statistical_strings():
    er = _publish_engine_run()
    html = render_engine_run(er)
    for needle in ["p =", "q =", "p-value", "q-value", "confidence_score", "final_score", "p_internal", "ci_internal"]:
        assert needle not in html, f"forbidden: {needle!r}"


def test_abstain_soft_html_contains_no_forbidden_statistical_strings():
    er = _abstain_soft_engine_run()
    html = render_engine_run(er)
    for needle in ["p =", "q =", "confidence_score", "final_score", "p_internal", "ci_internal"]:
        assert needle not in html


def test_abstain_hard_html_contains_no_forbidden_statistical_strings():
    er = _abstain_hard_engine_run()
    html = render_engine_run(er)
    for needle in ["p =", "q =", "confidence_score", "final_score", "p_internal", "ci_internal"]:
        assert needle not in html


# ---------------------------------------------------------------------------
# Recommended section: cap and badges
# ---------------------------------------------------------------------------


def test_recommended_section_renders_badges_for_each_class():
    er = _publish_engine_run()
    html = render_recommended_section(er.recommendations, scale=er.scale, abstain=er.abstain)
    assert "Strong" in html  # measured
    assert "Emerging" in html  # directional
    assert "Targeting" in html  # targeting


def test_recommended_section_empty_renders_placeholder():
    html = render_recommended_section([], scale=Scale(), abstain=Abstain(state=DecisionState.PUBLISH))
    assert "Recommended" in html
    assert "No recommendations to publish" in html


# ---------------------------------------------------------------------------
# Smoke: full document is well-formed-ish (open/close tags balance approx)
# ---------------------------------------------------------------------------


def test_full_document_contains_html_doctype_and_title():
    er = _publish_engine_run()
    html = render_engine_run(er)
    assert html.startswith("<!DOCTYPE html>")
    assert "<title>" in html
    assert "</html>" in html


# ---------------------------------------------------------------------------
# Legacy adapter: T8.7
# ---------------------------------------------------------------------------


def test_legacy_actions_from_engine_run_round_trip_minimum_fields():
    from src.engine_run_adapter import legacy_actions_from_engine_run

    er = _publish_engine_run()
    bundle = legacy_actions_from_engine_run(er)
    assert "actions" in bundle
    assert "watchlist" in bundle
    assert "pilot_actions" in bundle
    assert "backlog" in bundle
    assert isinstance(bundle["actions"], list)
    # One action per recommendation.
    assert len(bundle["actions"]) == len(er.recommendations)
    # First action is winback (measured), expected_$ from the non-suppressed range.
    first = bundle["actions"][0]
    assert first["play_id"] == "winback"
    assert first["expected_$"] == 8000.0
    assert first["evidence_class"] == "measured"
    # Suppressed targeting card has expected_$ = None.
    suppressed_action = next(
        a for a in bundle["actions"] if a["play_id"] == "bestseller_amplify"
    )
    assert suppressed_action["expected_$"] is None
    # Backlog mirrors considered list entries.
    assert len(bundle["backlog"]) == len(er.considered)
    backlog_first = bundle["backlog"][0]
    assert "play_id" in backlog_first
    assert "reason_code" in backlog_first


def test_legacy_actions_from_empty_engine_run_returns_empty_bundle():
    from src.engine_run_adapter import legacy_actions_from_engine_run

    bundle = legacy_actions_from_engine_run(None)
    assert bundle["actions"] == []
    assert bundle["watchlist"] == []
    assert bundle["pilot_actions"] == []
    assert bundle["backlog"] == []
