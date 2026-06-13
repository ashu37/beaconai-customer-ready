"""Phase 5.6 — Wire one measured/directional pathway.

The Beauty Brand fixture has a defensible directional signal on
``returning_customer_share``: L28 p ~= 9.5e-05, +6.6% delta, with
positive direction across L56 and L90. Phase 5.6 surfaces this as a
DIRECTIONAL PlayCard for ``first_to_second_purchase`` with a *suppressed*
revenue range (no calibrated lift; revenue would be a fabrication).

Tests cover:
- A synthetic candidate + aligned snapshot produces a directional
  PlayCard when the supporting signal meets the bar.
- The PlayCard carries a valid Measurement.
- The card has ``revenue_range.suppressed=True`` (no $ projection).
- The V2 briefing has at least one populated Recommended card under
  these conditions.
- No forbidden statistical strings appear in merchant HTML.
- A targeting-only / weak-signal pathway still becomes ABSTAIN_SOFT.
- Hard data-quality flags still drive ABSTAIN_HARD.
"""
from __future__ import annotations

from src.decide import decide
from src.detect import Candidate
from src.engine_run import (
    Abstain,
    DataQualityFlag,
    DecisionState,
    EngineRun,
    EvidenceClass,
    PlayCard,
    Scale,
)
from src.measurement_builder import (
    PHASE5_DIRECTIONAL_MIN_CONSISTENCY,
    PHASE5_DIRECTIONAL_P_MAX,
    build_directional_play_card,
    build_directional_recommendations,
)
from src.storytelling_v2 import render_engine_run


# ---------------------------------------------------------------------------
# Helpers — synthetic Beauty-style aligned snapshot
# ---------------------------------------------------------------------------


def _beauty_aligned() -> dict:
    """Synthetic aligned snapshot mirroring the Beauty Brand pattern:
    returning_customer_share L28 p ~= 9.5e-05, +6.6%, positive across
    L56 and L90."""
    return {
        "L28": {
            "returning_customer_share": 0.915,
            "delta": {"returning_customer_share": 0.066},
            "p": {"returning_customer_share": 9.5e-5},
            "meta": {"identified_recent": 962},
        },
        "L56": {
            "returning_customer_share": 0.83,
            "delta": {"returning_customer_share": 0.32},
            "p": {"returning_customer_share": 1e-30},
            "meta": {"identified_recent": 1296},
        },
        "L90": {
            "returning_customer_share": 0.68,
            "delta": {"returning_customer_share": 2.5},
            "p": {"returning_customer_share": 4e-139},
            "meta": {"identified_recent": 1457},
        },
    }


def _f2s_candidate(audience_size: int = 1500) -> Candidate:
    return Candidate(
        play_id="first_to_second_purchase",
        audience_size=audience_size,
        segment_definition="customers with exactly one historical order",
        data_used=["g.customer_id", "g.Name"],
        preliminary_rejection_reason=None,
        cold_start=False,
    )


# ---------------------------------------------------------------------------
# build_directional_play_card — happy path
# ---------------------------------------------------------------------------


def test_build_directional_card_when_signal_meets_bar():
    cand = _f2s_candidate()
    aligned = _beauty_aligned()
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    assert card.play_id == "first_to_second_purchase"
    assert card.evidence_class == EvidenceClass.DIRECTIONAL


def test_directional_card_has_valid_measurement():
    cand = _f2s_candidate()
    aligned = _beauty_aligned()
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    m = card.measurement
    assert m is not None
    assert m.metric == "returning_customer_share"
    assert m.observed_effect is not None
    assert m.consistency_across_windows is not None
    assert m.consistency_across_windows >= PHASE5_DIRECTIONAL_MIN_CONSISTENCY
    assert m.primary_window == "L28"
    # p_internal lives on the EngineRun for ML calibration but must NOT
    # render in merchant HTML; that constraint is enforced separately.
    assert m.p_internal is not None and m.p_internal < PHASE5_DIRECTIONAL_P_MAX


def test_directional_card_revenue_range_is_suppressed():
    """Phase 5.6 contract: until calibrated lift exists, no $ projection."""
    cand = _f2s_candidate()
    aligned = _beauty_aligned()
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    rr = card.revenue_range
    assert rr is not None
    assert rr.suppressed is True
    assert rr.p10 is None and rr.p50 is None and rr.p90 is None


# ---------------------------------------------------------------------------
# build_directional_play_card — guards (no-fire conditions)
# ---------------------------------------------------------------------------


def test_does_not_fire_when_audience_below_minimum():
    cand = Candidate(
        play_id="first_to_second_purchase",
        audience_size=10,
        segment_definition="too small",
        data_used=[],
        preliminary_rejection_reason="audience_too_small",
    )
    card = build_directional_play_card(cand, _beauty_aligned())
    assert card is None


def test_does_not_fire_when_p_value_above_threshold():
    cand = _f2s_candidate()
    aligned = _beauty_aligned()
    aligned["L28"]["p"]["returning_customer_share"] = 0.30
    card = build_directional_play_card(cand, aligned)
    assert card is None


def test_does_not_fire_when_signs_disagree_across_windows():
    cand = _f2s_candidate()
    aligned = _beauty_aligned()
    # Force opposite signs across windows -> consistency = 1 (only L28).
    aligned["L56"]["delta"]["returning_customer_share"] = -0.05
    aligned["L90"]["delta"]["returning_customer_share"] = -0.10
    card = build_directional_play_card(cand, aligned)
    assert card is None


def test_does_not_fire_for_unsupported_play_id():
    cand = Candidate(
        play_id="bestseller_amplify",
        audience_size=2000,
        segment_definition="bestseller buyers",
        data_used=[],
        preliminary_rejection_reason=None,
    )
    card = build_directional_play_card(cand, _beauty_aligned())
    assert card is None


def test_does_not_fire_when_aligned_is_none():
    assert build_directional_play_card(_f2s_candidate(), None) is None


def test_skips_candidate_already_in_recommendations():
    cand = _f2s_candidate()
    cards = build_directional_recommendations(
        [cand],
        _beauty_aligned(),
        existing_recommendation_ids=["first_to_second_purchase"],
    )
    assert cards == []


# ---------------------------------------------------------------------------
# End-to-end: V2 briefing renders a populated Recommended card
# ---------------------------------------------------------------------------


def test_v2_briefing_renders_directional_recommended_card():
    cand = _f2s_candidate()
    aligned = _beauty_aligned()
    card = build_directional_play_card(cand, aligned)
    assert card is not None

    er = EngineRun(
        store_id="phase5",
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[card],
        scale=Scale(monthly_revenue=120_000.0, materiality_floor=10_000.0),
    )
    out = decide(er)
    assert out.abstain.state == DecisionState.PUBLISH
    html = render_engine_run(out)
    # The directional card surfaces with its merchant-readable copy
    # (display_name from play_registry per Phase 6B Ticket C3).
    assert "Second-purchase nudge for one-and-done buyers" in html
    assert "Emerging" in html  # directional badge label


def test_directional_card_briefing_has_no_forbidden_statistical_strings():
    cand = _f2s_candidate()
    aligned = _beauty_aligned()
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    er = EngineRun(
        store_id="phase5",
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[card],
    )
    html = render_engine_run(er)
    forbidden = [
        "p =", "q =", "p-value", "q-value",
        "confidence_score", "final_score",
        "p_internal", "ci_internal",
        "Aura", "Beacon Score", "/100",
    ]
    for token in forbidden:
        assert token not in html, f"Directional card briefing leaks {token!r}"


def test_directional_card_briefing_does_not_show_dollar_amount():
    """Phase 5.6: revenue range is suppressed; no $ figure should render."""
    cand = _f2s_candidate()
    aligned = _beauty_aligned()
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    er = EngineRun(
        store_id="phase5",
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[card],
    )
    html = render_engine_run(er)
    # The DIRECTIONAL card class wrapper is present.
    assert "play-card--directional" in html
    # No range chip element rendered (suppressed). The class string
    # appears in the inline <style> CSS regardless; we only check that
    # no <span> uses the class as an attribute.
    assert 'class="play-card-range-chip"' not in html
    # And the chip's text fragment is absent.
    assert "Estimated range" not in html


# ---------------------------------------------------------------------------
# Acceptance: targeting-only still ABSTAIN_SOFT
# ---------------------------------------------------------------------------


def test_targeting_only_still_yields_abstain_soft():
    targeting_card = PlayCard(
        play_id="bestseller_amplify",
        evidence_class=EvidenceClass.TARGETING,
    )
    er = EngineRun(recommendations=[targeting_card])
    out = decide(er)
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT


def test_hard_data_quality_flag_still_yields_abstain_hard():
    """Phase 5.6 must NOT bypass the M5 anomaly hard gate."""
    cand = _f2s_candidate()
    aligned = _beauty_aligned()
    card = build_directional_play_card(cand, aligned)
    assert card is not None
    er = EngineRun(
        recommendations=[card],
        data_quality_flags=[DataQualityFlag.REFUND_STORM],
    )
    out = decide(er)
    assert out.abstain.state == DecisionState.ABSTAIN_HARD
    assert out.recommendations == []
