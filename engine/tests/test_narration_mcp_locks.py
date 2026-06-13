"""KI-FE-7 synthetic-fixture lock tests for the Narration MCP (Phase 1).

small_sm does NOT exercise the suppression / RULE-A / None-param branches
(its one card carries mechanism_intent with {} Tier-B params and a
non-BLEND, non-suppressed revenue_range). DS §6 requires those branches be
pinned with SYNTHETIC unit fixtures before prose templates ship. These
tests build hand-rolled PlayCard / RejectedPlay objects (imported from the
schema authority) and narrate them through the MOCK LLM — so they pass
WITHOUT an ANTHROPIC_API_KEY and make no network call.

Lock -> guard mapping under test:
  L1  evidence_class never fed / never narrated as a claim
  L2  STORE_OBSERVED revenue is NOT lift
  L3  fit_warnings audit-only (never narrated)
  L6  no merchant-facing AOV; segment only from PlayCard.predicted_segment
  L7  RULE A (None mechanism) + None-param + Tier-B {}-param
  L8  dollar scrubber — only non-suppressed source=BLEND p10/p50/p90
"""

from __future__ import annotations

from src.engine_run import (
    Audience,
    EvidenceClass,
    EvidenceSourceChip,
    FitWarning,
    FitWarningLevel,
    MechanismIntent,
    MechanismType,
    ModelCardRef,
    PlayCard,
    PredictedSegment,
    RejectedPlay,
    ReasonCode,
    RevenueRange,
    RevenueRangeSource,
    RevenueRangeSuppressionReason,
)
from src.mcp.narration.atoms import project_play_card, project_rejected_play
from src.mcp.narration.guards import run_all_guards, safe_fallback_narration
from src.mcp.narration.llm_client import MockLLMClient
from src.mcp.narration.narrator import Narrator


def _narrator(responder=None) -> Narrator:
    return Narrator(MockLLMClient(responder=responder))


# ---------------------------------------------------------------------------
# RULE A / L7 — mechanism_intent is None => no mechanism line
# ---------------------------------------------------------------------------


def test_rule_a_null_mechanism_no_mechanism_line():
    card = PlayCard(
        play_id="legacy_play_no_mechanism",
        evidence_source=EvidenceSourceChip.STORE_OBSERVED,
        audience=Audience(size=500),
        mechanism_intent=None,  # RULE A
        revenue_range=None,
    )
    atoms = project_play_card(card, "recommendation")
    assert atoms.mechanism is None

    res = _narrator().narrate_atoms(atoms, run_id="r1", store_id="s1")
    assert res.guard_violations == []
    # No mechanism vocabulary should appear in the "what we'd send" line.
    what = res.what_we_d_send.lower()
    for term in ("winback", "nudge sequence", "bundle offer", "subscription"):
        assert term not in what


def test_rule_a_guard_rejects_injected_mechanism_line():
    """A misbehaving LLM that invents a mechanism for a None-mechanism card
    must trip L7 and fall back."""
    card = PlayCard(
        play_id="legacy_play_no_mechanism",
        audience=Audience(size=500),
        mechanism_intent=None,
    )
    atoms = project_play_card(card, "recommendation")

    def bad(_sys, _user):
        return (
            '{"play_thesis":"x","what_we_d_send":"We would run a winback '
            'reactivation email sequence.","evidence_summary":"y"}'
        )

    res = _narrator(responder=bad).narrate_atoms(atoms, run_id="r1", store_id="s1")
    assert res.used_fallback is True
    assert any(v.startswith("L7") for v in res.guard_violations)
    assert "winback" not in res.what_we_d_send.lower()


# ---------------------------------------------------------------------------
# L8 — suppressed revenue_range => no dollar figure
# ---------------------------------------------------------------------------


def test_suppressed_revenue_range_no_dollar_figure():
    card = PlayCard(
        play_id="winback_dormant_cohort",
        evidence_source=EvidenceSourceChip.STORE_OBSERVED,
        audience=Audience(size=800),
        revenue_range=RevenueRange(
            p10=None,
            p50=None,
            p90=None,
            source=None,
            suppressed=True,
            suppression_reason=RevenueRangeSuppressionReason.COLD_START_NO_N_OBSERVED,
        ),
        mechanism_intent=MechanismIntent(type=MechanismType.WINBACK_REACTIVATION_EMAIL,
                                         parameters={"dormancy_window_days": 21,
                                                     "offer_type": "percent_off",
                                                     "measurement_window_days": 30}),
    )
    atoms = project_play_card(card, "recommendation")
    assert atoms.allowed_dollar_figures == []
    assert "SUPPRESSED" in atoms.revenue_note

    res = _narrator().narrate_atoms(atoms, run_id="r1", store_id="s1")
    assert res.guard_violations == []
    assert "$" not in (res.play_thesis + res.what_we_d_send + res.evidence_summary)


def test_suppressed_range_guard_rejects_injected_dollar():
    card = PlayCard(
        play_id="winback_dormant_cohort",
        evidence_source=EvidenceSourceChip.STORE_OBSERVED,
        audience=Audience(size=800),
        revenue_range=RevenueRange(
            suppressed=True,
            suppression_reason=RevenueRangeSuppressionReason.AUDIENCE_ZERO,
        ),
        mechanism_intent=None,
    )
    atoms = project_play_card(card, "recommendation")

    def bad(_sys, _user):
        return ('{"play_thesis":"This is worth $12,000.","what_we_d_send":"x",'
                '"evidence_summary":"y"}')

    res = _narrator(responder=bad).narrate_atoms(atoms, run_id="r1", store_id="s1")
    assert res.used_fallback is True
    assert any(v.startswith("L8") for v in res.guard_violations)
    assert "$" not in (res.play_thesis + res.what_we_d_send + res.evidence_summary)


def test_blend_source_dollar_is_allowed():
    """A non-suppressed source=BLEND range with p10/p50/p90 IS emittable."""
    card = PlayCard(
        play_id="cohort_journey_first_to_second",
        evidence_source=EvidenceSourceChip.STORE_OBSERVED,
        audience=Audience(size=1200),
        revenue_range=RevenueRange(
            p10=1000.0, p50=2500.0, p90=4000.0,
            source=RevenueRangeSource.BLEND,
            suppressed=False,
        ),
        mechanism_intent=MechanismIntent(type=MechanismType.FIRST_TO_SECOND_NUDGE,
                                         parameters={"days_since_first_order_window": [30, 90],
                                                     "measurement_window_days": 30}),
    )
    atoms = project_play_card(card, "recommendation")
    assert atoms.allowed_dollar_figures == [1000.0, 2500.0, 4000.0]

    res = _narrator().narrate_atoms(atoms, run_id="r1", store_id="s1")
    assert res.guard_violations == []


def test_non_blend_source_dollar_is_not_allowed():
    """STORE_OBSERVED source range (the small_sm case is even None) yields
    no allowed dollar figure (L8)."""
    card = PlayCard(
        play_id="bestseller_amplify",
        evidence_source=EvidenceSourceChip.STORE_OBSERVED,
        audience=Audience(size=2000),
        revenue_range=RevenueRange(
            p50=13034.5,
            source=RevenueRangeSource.STORE_OBSERVED,
            suppressed=False,
        ),
        mechanism_intent=MechanismIntent(type=MechanismType.BESTSELLER_AMPLIFY, parameters={}),
    )
    atoms = project_play_card(card, "recommendation")
    assert atoms.allowed_dollar_figures == []
    res = _narrator().narrate_atoms(atoms, run_id="r1", store_id="s1")
    assert "$" not in (res.play_thesis + res.what_we_d_send + res.evidence_summary)


# ---------------------------------------------------------------------------
# L7 — Tier-B {}-param mechanism => mechanism named, zero params invented
# ---------------------------------------------------------------------------


def test_tier_b_empty_param_mechanism_named_no_params():
    card = PlayCard(
        play_id="bestseller_amplify",
        audience=Audience(size=2163),
        mechanism_intent=MechanismIntent(type=MechanismType.BESTSELLER_AMPLIFY, parameters={}),
        revenue_range=None,
    )
    atoms = project_play_card(card, "recommendation")
    assert atoms.mechanism == {"type": "BESTSELLER_AMPLIFY", "parameters": {}}
    res = _narrator().narrate_atoms(atoms, run_id="r1", store_id="s1")
    assert res.guard_violations == []


# ---------------------------------------------------------------------------
# L7 — TODO(S14) None-param mechanism => no fabricated dollar/share
# ---------------------------------------------------------------------------


def test_none_param_types_drop_none_params():
    for mtype, params in [
        (MechanismType.THRESHOLD_BUNDLE_OFFER,
         {"threshold_aov": None, "current_median_aov": None}),
        (MechanismType.DISCOUNT_DEPENDENCY_HYGIENE,
         {"current_discount_share": None, "target_discount_share": None}),
        (MechanismType.REPLENISHMENT_REMINDER,
         {"replenishment_window_days": None, "sku_class": None}),
    ]:
        card = PlayCard(
            play_id=mtype.value.lower(),
            audience=Audience(size=400),
            mechanism_intent=MechanismIntent(type=mtype, parameters=params),
            revenue_range=None,
        )
        atoms = project_play_card(card, "recommendation")
        # None-valued params are dropped at the projection boundary.
        assert atoms.mechanism["type"] == mtype.value
        assert atoms.mechanism["parameters"] == {}
        res = _narrator().narrate_atoms(atoms, run_id="r1", store_id="s1")
        assert res.guard_violations == []
        blob = res.play_thesis + res.what_we_d_send + res.evidence_summary
        assert "$" not in blob
        assert "%" not in blob


# ---------------------------------------------------------------------------
# L2 — STORE_OBSERVED revenue is NOT lift
# ---------------------------------------------------------------------------


def test_store_observed_blend_range_not_narrated_as_lift():
    card = PlayCard(
        play_id="cohort_journey_first_to_second",
        evidence_source=EvidenceSourceChip.STORE_OBSERVED,
        audience=Audience(size=900),
        revenue_range=RevenueRange(
            p10=500.0, p50=1500.0, p90=3000.0,
            source=RevenueRangeSource.BLEND, suppressed=False,
        ),
        mechanism_intent=None,
    )
    atoms = project_play_card(card, "recommendation")
    # The projection carries explicit not-lift framing guidance.
    assert "NOT lift" in atoms.revenue_note

    def lifty(_sys, _user):
        return ('{"play_thesis":"x","what_we_d_send":"y",'
                '"evidence_summary":"This is the incremental lift you will earn."}')

    res = _narrator(responder=lifty).narrate_atoms(atoms, run_id="r1", store_id="s1")
    assert res.used_fallback is True
    assert any(v.startswith("L2") for v in res.guard_violations)


def test_store_observed_lift_term_in_clean_output_is_clean():
    """Control: a clean STORE_OBSERVED output with no lift framing passes."""
    card = PlayCard(
        play_id="winback_dormant_cohort",
        evidence_source=EvidenceSourceChip.STORE_OBSERVED,
        audience=Audience(size=900),
        revenue_range=None,
        mechanism_intent=None,
    )
    atoms = project_play_card(card, "recommendation")
    res = _narrator().narrate_atoms(atoms, run_id="r1", store_id="s1")
    assert res.guard_violations == []


# ---------------------------------------------------------------------------
# L1 — evidence_class never fed; overclaim never narrated
# ---------------------------------------------------------------------------


def test_evidence_class_never_in_projection():
    card = PlayCard(
        play_id="x",
        evidence_class=EvidenceClass.MEASURED,  # internal tag
        evidence_source=EvidenceSourceChip.STORE_OBSERVED,  # the chip
        audience=Audience(size=100),
        mechanism_intent=None,
    )
    atoms = project_play_card(card, "recommendation")
    prompt = atoms.to_prompt_dict()
    # evidence_class must be structurally absent; only the chip is present.
    assert "evidence_class" not in prompt
    assert prompt["evidence_source"] == "STORE_OBSERVED"


def test_evidence_class_overclaim_guard():
    card = PlayCard(
        play_id="x",
        evidence_source=EvidenceSourceChip.STORE_OBSERVED,
        audience=Audience(size=100),
        mechanism_intent=None,
    )
    atoms = project_play_card(card, "recommendation")

    def bad(_sys, _user):
        return ('{"play_thesis":"We measured this on your store.",'
                '"what_we_d_send":"x","evidence_summary":"y"}')

    res = _narrator(responder=bad).narrate_atoms(atoms, run_id="r1", store_id="s1")
    assert res.used_fallback is True
    assert any(v.startswith("L1") for v in res.guard_violations)


# ---------------------------------------------------------------------------
# L3 — fit_warnings audit-only; never fed, never narrated
# ---------------------------------------------------------------------------


def test_fit_warnings_never_in_projection():
    card = PlayCard(
        play_id="x",
        evidence_source=EvidenceSourceChip.STORE_OBSERVED,
        audience=Audience(size=100),
        model_card_ref=ModelCardRef(
            strategy_used="RFM",
            fit_warnings=[FitWarning(level=FitWarningLevel.MODEL_FIT_REFUSED,
                                     substrate="bgnbd")],
        ),
        mechanism_intent=None,
    )
    atoms = project_play_card(card, "recommendation")
    prompt = atoms.to_prompt_dict()
    blob = str(prompt).lower()
    assert "fit_warning" not in blob
    assert "model_fit_refused" not in blob
    assert "bgnbd" not in blob


def test_fit_warning_leak_guard():
    card = PlayCard(play_id="x", audience=Audience(size=100), mechanism_intent=None)
    atoms = project_play_card(card, "recommendation")

    def bad(_sys, _user):
        return ('{"play_thesis":"We recommend this because the BG/NBD model refused.",'
                '"what_we_d_send":"x","evidence_summary":"y"}')

    res = _narrator(responder=bad).narrate_atoms(atoms, run_id="r1", store_id="s1")
    assert res.used_fallback is True
    assert any(v.startswith("L3") for v in res.guard_violations)


# ---------------------------------------------------------------------------
# L6 — no merchant-facing AOV; segment only from PlayCard.predicted_segment
# ---------------------------------------------------------------------------


def test_predicted_segment_only_from_playcard():
    card = PlayCard(
        play_id="x",
        audience=Audience(size=100),
        predicted_segment=PredictedSegment(segment_name="Champions",
                                           audience_modal_share=0.42, n_audience=100),
        mechanism_intent=None,
    )
    atoms = project_play_card(card, "recommendation")
    assert atoms.segment_name == "Champions"


def test_aov_term_guard():
    card = PlayCard(play_id="x", audience=Audience(size=100), mechanism_intent=None)
    atoms = project_play_card(card, "recommendation")

    def bad(_sys, _user):
        return ('{"play_thesis":"x","what_we_d_send":"y",'
                '"evidence_summary":"Their average order value is high."}')

    res = _narrator(responder=bad).narrate_atoms(atoms, run_id="r1", store_id="s1")
    assert res.used_fallback is True
    assert any(v.startswith("L6") for v in res.guard_violations)


# ---------------------------------------------------------------------------
# Considered (RejectedPlay) — L3 reason from reason_code only
# ---------------------------------------------------------------------------


def test_considered_play_narrates_without_fit_warning():
    rp = RejectedPlay(
        play_id="subscription_nudge",
        reason_code=ReasonCode.AUDIENCE_TOO_SMALL,
        audience_size=12,
        audience_definition="one-time buyers",
        held_reason_detail={"observed": 12, "floor": 50},
        mechanism=MechanismIntent(type=MechanismType.SUBSCRIPTION_NUDGE, parameters={}),
    )
    atoms = project_rejected_play(rp)
    assert atoms.reason_code == "audience_too_small"
    assert atoms.allowed_dollar_figures == []
    res = _narrator().narrate_considered(rp, run_id="r1", store_id="s1")
    assert res.guard_violations == []
    assert "$" not in (res.play_thesis + res.what_we_d_send + res.evidence_summary)


# ---------------------------------------------------------------------------
# Fallback is itself lock-clean
# ---------------------------------------------------------------------------


def test_safe_fallback_is_clean():
    card = PlayCard(
        play_id="winback_dormant_cohort",
        evidence_source=EvidenceSourceChip.STORE_OBSERVED,
        audience=Audience(size=800),
        revenue_range=RevenueRange(suppressed=True,
                                   suppression_reason=RevenueRangeSuppressionReason.AOV_ZERO),
        mechanism_intent=MechanismIntent(type=MechanismType.WINBACK_REACTIVATION_EMAIL,
                                         parameters={"dormancy_window_days": 21}),
    )
    atoms = project_play_card(card, "recommendation")
    safe = safe_fallback_narration(atoms)
    assert run_all_guards(safe, atoms) == []
    assert "$" not in " ".join(safe.values())
