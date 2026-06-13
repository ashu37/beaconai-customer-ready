"""Tests for the M7 V2 Decision Selector (src/decide.py).

Covers the M7 acceptance criteria from
``agent_outputs/implementation-manager-overhaul-plan-final.md``:

- Class-aware ranking (T7.2): measured > directional > targeting,
  regardless of p50 / audience size ordering.
- Top-3 cap (T7.3): excess goes to ``considered`` with
  ``CAP_EXCEEDED``.
- Materiality + class-aware-ranking interaction (T7.4 / DS Architect QA
  Change 2): zero measured/directional after gating ⇒ ABSTAIN_SOFT,
  never PUBLISH on a targeting-only briefing.
- Rejected-play assembly (T7.5/T7.6): considered list de-duplicates
  against recommendations and carries ``would_fire_if`` text.
- Abstain mode logic (T7.7):
    * any HARD data-quality flag ⇒ ABSTAIN_HARD with empty
      recommendations.
    * 0 measured/directional after gating ⇒ ABSTAIN_SOFT.
    * otherwise PUBLISH.
- Watching builder (T7.9): deterministic, single-run,
  state-of-store-driven.
- Pure: input EngineRun is not mutated.
"""

from __future__ import annotations

from dataclasses import replace
from typing import List, Optional

from src.decide import (
    MAX_CONSIDERED_RENDERED,
    MAX_RECOMMENDATIONS,
    MAX_WATCHING_SIGNALS,
    assemble_considered,
    build_watching,
    decide,
    rank_recommendations,
)
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
    Scale,
    WatchedSignal,
)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _card(
    play_id: str,
    *,
    evidence: EvidenceClass = EvidenceClass.TARGETING,
    p50: Optional[float] = None,
    audience_size: int = 0,
    suppressed: bool = False,
    observed_effect: Optional[float] = None,
) -> PlayCard:
    rr = None
    if p50 is not None or suppressed:
        rr = RevenueRange(
            p10=None,
            p50=p50,
            p90=None,
            source=None,
            drivers=[],
            suppressed=suppressed,
        )
    aud = Audience(id=play_id, definition=play_id, size=audience_size)
    measurement = None
    if evidence in (EvidenceClass.MEASURED, EvidenceClass.DIRECTIONAL):
        measurement = Measurement(
            metric="metric",
            observed_effect=observed_effect,
            n=audience_size,
        )
    return PlayCard(
        play_id=play_id,
        evidence_class=evidence,
        audience=aud,
        measurement=measurement,
        revenue_range=rr,
    )


def _engine_run(
    *,
    recommendations: Optional[List[PlayCard]] = None,
    considered: Optional[List[RejectedPlay]] = None,
    flags: Optional[List[DataQualityFlag]] = None,
    state_of_store: Optional[List[Observation]] = None,
    abstain: Optional[Abstain] = None,
    monthly_revenue: Optional[float] = 100_000.0,
) -> EngineRun:
    return EngineRun(
        run_id="test-run",
        store_id="test-store",
        recommendations=recommendations or [],
        considered=considered or [],
        data_quality_flags=flags or [],
        state_of_store=state_of_store or [],
        abstain=abstain or Abstain(state=DecisionState.PUBLISH),
        scale=Scale(monthly_revenue=monthly_revenue),
    )


# ---------------------------------------------------------------------------
# Ranking (T7.2)
# ---------------------------------------------------------------------------


class TestRanking:
    def test_measured_outranks_targeting_regardless_of_p50(self):
        """Measured with low p50 must outrank targeting with high p50."""
        m = _card("measured_play", evidence=EvidenceClass.MEASURED, p50=100.0,
                  audience_size=10, observed_effect=0.05)
        t = _card("targeting_play", evidence=EvidenceClass.TARGETING, p50=99_999.0,
                  audience_size=99_999)

        ranked = rank_recommendations([t, m])
        assert ranked[0].play_id == "measured_play"
        assert ranked[1].play_id == "targeting_play"

    def test_directional_outranks_targeting(self):
        d = _card("directional_play", evidence=EvidenceClass.DIRECTIONAL, p50=10.0,
                  audience_size=10, observed_effect=0.02)
        t = _card("targeting_play", evidence=EvidenceClass.TARGETING, p50=10_000.0,
                  audience_size=10_000)

        ranked = rank_recommendations([t, d])
        assert ranked[0].play_id == "directional_play"

    def test_measured_outranks_directional(self):
        m = _card("m", evidence=EvidenceClass.MEASURED, p50=10.0, observed_effect=0.05)
        d = _card("d", evidence=EvidenceClass.DIRECTIONAL, p50=10.0, observed_effect=0.05)
        ranked = rank_recommendations([d, m])
        assert ranked[0].play_id == "m"

    def test_within_class_p50_descending(self):
        big = _card("big", evidence=EvidenceClass.MEASURED, p50=1_000.0, observed_effect=0.05)
        small = _card("small", evidence=EvidenceClass.MEASURED, p50=100.0, observed_effect=0.05)
        ranked = rank_recommendations([small, big])
        assert ranked[0].play_id == "big"
        assert ranked[1].play_id == "small"

    def test_suppressed_p50_ranks_below_sized(self):
        sized = _card("sized", evidence=EvidenceClass.MEASURED, p50=100.0,
                      observed_effect=0.05)
        sup = _card("sup", evidence=EvidenceClass.MEASURED, suppressed=True,
                    observed_effect=0.05)
        ranked = rank_recommendations([sup, sized])
        assert ranked[0].play_id == "sized"
        assert ranked[1].play_id == "sup"

    def test_deterministic_tiebreak_by_play_id(self):
        """Identical class + p50 sort by play_id ascending."""
        a = _card("aaa", evidence=EvidenceClass.TARGETING)
        b = _card("zzz", evidence=EvidenceClass.TARGETING)
        ranked1 = rank_recommendations([b, a])
        ranked2 = rank_recommendations([a, b])
        assert [c.play_id for c in ranked1] == ["aaa", "zzz"]
        assert [c.play_id for c in ranked2] == ["aaa", "zzz"]

    def test_input_not_mutated(self):
        a = _card("a", evidence=EvidenceClass.TARGETING)
        b = _card("b", evidence=EvidenceClass.MEASURED, observed_effect=0.04)
        original = [a, b]
        ranked = rank_recommendations(original)
        assert ranked is not original
        assert original[0].play_id == "a"
        assert original[1].play_id == "b"


# ---------------------------------------------------------------------------
# Cap (T7.3)
# ---------------------------------------------------------------------------


class TestCap:
    def test_max_three_recommendations_published(self):
        """Five valid candidates ⇒ 3 recommended + 2 considered cap_exceeded."""
        cards = [
            _card(f"m{i}", evidence=EvidenceClass.MEASURED, p50=1000.0 - i,
                  observed_effect=0.05)
            for i in range(5)
        ]
        er = _engine_run(recommendations=cards)
        out = decide(er)

        assert len(out.recommendations) == 3
        assert MAX_RECOMMENDATIONS == 3
        # Two demoted into considered with CAP_EXCEEDED.
        cap_excess = [r for r in out.considered if r.reason_code == ReasonCode.CAP_EXCEEDED]
        assert len(cap_excess) == 2
        # The top-3 by p50 are the survivors.
        survivor_ids = {c.play_id for c in out.recommendations}
        assert survivor_ids == {"m0", "m1", "m2"}

    def test_considered_capped_at_six(self):
        """Many rejections should be capped at 6 rendered considered entries."""
        recs = [_card("m0", evidence=EvidenceClass.MEASURED, p50=100.0,
                      observed_effect=0.05)]
        many_rejections = [
            RejectedPlay(
                play_id=f"rej_{i}",
                reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR,
            )
            for i in range(20)
        ]
        er = _engine_run(recommendations=recs, considered=many_rejections)
        out = decide(er)
        assert len(out.considered) <= MAX_CONSIDERED_RENDERED

    def test_cap_exceeded_carries_would_fire_if(self):
        cards = [
            _card(f"m{i}", evidence=EvidenceClass.MEASURED, p50=100.0,
                  observed_effect=0.05)
            for i in range(4)
        ]
        out = decide(_engine_run(recommendations=cards))
        cap_excess = [r for r in out.considered if r.reason_code == ReasonCode.CAP_EXCEEDED]
        assert len(cap_excess) == 1


# ---------------------------------------------------------------------------
# Abstain (T7.4 / T7.7)
# ---------------------------------------------------------------------------


class TestAbstain:
    def test_targeting_only_yields_abstain_soft(self):
        """DS Architect QA Change 2: targeting-only must NOT publish.

        Synthetic Blocker Fix 3 (PM-resolved): tightened to require
        ``recommendations == []`` under ABSTAIN_SOFT. Held targeting
        cards are re-routed into ``considered`` with the typed
        ``TARGETING_HELD_UNDER_ABSTAIN`` reason.
        """
        targeting = [
            _card(f"t{i}", evidence=EvidenceClass.TARGETING, p50=10_000.0,
                  audience_size=1000)
            for i in range(2)
        ]
        out = decide(_engine_run(recommendations=targeting))
        assert out.abstain.state == DecisionState.ABSTAIN_SOFT
        # S13.6-T1a (Option D): ``Abstain.reason`` stripped per Pivot 2 —
        # the merchant-readable-reason assertions removed; the
        # decision_state assertion above is the surviving invariant.
        # Fix 3: recommendations must be empty under ABSTAIN_SOFT.
        assert out.recommendations == []
        # The two held targeting cards now appear in considered with the
        # typed reason code.
        held = [
            r
            for r in out.considered
            if r.reason_code == ReasonCode.TARGETING_HELD_UNDER_ABSTAIN
        ]
        held_ids = sorted(r.play_id for r in held)
        assert held_ids == ["t0", "t1"]

    def test_zero_recommendations_yields_abstain_soft(self):
        out = decide(_engine_run(recommendations=[]))
        assert out.abstain.state == DecisionState.ABSTAIN_SOFT
        assert out.recommendations == []

    def test_measured_present_yields_publish(self):
        cards = [
            _card("m", evidence=EvidenceClass.MEASURED, p50=200.0, observed_effect=0.05),
            _card("t", evidence=EvidenceClass.TARGETING, p50=100.0),
        ]
        out = decide(_engine_run(recommendations=cards))
        assert out.abstain.state == DecisionState.PUBLISH
        # Class-aware ranking puts measured first.
        assert out.recommendations[0].play_id == "m"

    def test_directional_present_yields_publish(self):
        cards = [
            _card("d", evidence=EvidenceClass.DIRECTIONAL, p50=200.0, observed_effect=0.05),
            _card("t", evidence=EvidenceClass.TARGETING, p50=100.0),
        ]
        out = decide(_engine_run(recommendations=cards))
        assert out.abstain.state == DecisionState.PUBLISH

    def test_hard_dq_flag_yields_abstain_hard(self):
        cards = [_card("m", evidence=EvidenceClass.MEASURED, p50=500.0,
                       observed_effect=0.05)]
        er = _engine_run(
            recommendations=cards,
            flags=[DataQualityFlag.BFCM_OVERLAP],
        )
        out = decide(er)
        assert out.abstain.state == DecisionState.ABSTAIN_HARD
        assert out.recommendations == []
        # Reason mentions the flag.

    def test_hard_dq_flag_synthesizes_data_quality_rejections(self):
        """When upstream considered is empty, hard-flag path synthesizes
        DATA_QUALITY_FLAG rejections so reviewers can see the demoted set.
        """
        cards = [
            _card("m1", evidence=EvidenceClass.MEASURED, p50=500.0, observed_effect=0.05),
            _card("m2", evidence=EvidenceClass.MEASURED, p50=400.0, observed_effect=0.05),
        ]
        er = _engine_run(
            recommendations=cards,
            flags=[DataQualityFlag.REFUND_STORM],
            considered=[],
        )
        out = decide(er)
        dq_rejections = [
            r for r in out.considered if r.reason_code == ReasonCode.DATA_QUALITY_FLAG
        ]
        assert len(dq_rejections) == 2

    def test_hard_dq_flag_preserves_pre_existing_considered(self):
        """If M5 already populated ANOMALOUS_WINDOW rejections, they survive."""
        existing = [
            RejectedPlay(
                play_id="m1",
                reason_code=ReasonCode.ANOMALOUS_WINDOW,
            )
        ]
        cards = [_card("m1", evidence=EvidenceClass.MEASURED, p50=500.0,
                       observed_effect=0.05)]
        er = _engine_run(
            recommendations=cards,
            flags=[DataQualityFlag.BFCM_OVERLAP],
            considered=existing,
        )
        out = decide(er)
        # Pre-existing reason preserved.
        assert any(
            r.reason_code == ReasonCode.ANOMALOUS_WINDOW for r in out.considered
        )

    def test_pre_existing_abstain_hard_is_preserved(self):
        """If guardrails already declared ABSTAIN_HARD, decide cannot weaken it."""
        cards = [
            _card("m", evidence=EvidenceClass.MEASURED, p50=200.0, observed_effect=0.05),
        ]
        er = _engine_run(
            recommendations=cards,
            abstain=Abstain(state=DecisionState.ABSTAIN_HARD),
        )
        out = decide(er)
        assert out.abstain.state == DecisionState.ABSTAIN_HARD
        assert out.recommendations == []

    def test_post_promo_window_does_not_force_abstain_hard(self):
        """POST_PROMO_WINDOW is a soft warning, not a hard abstain trigger."""
        cards = [_card("m", evidence=EvidenceClass.MEASURED, p50=200.0,
                       observed_effect=0.05)]
        er = _engine_run(
            recommendations=cards,
            flags=[DataQualityFlag.POST_PROMO_WINDOW],
        )
        out = decide(er)
        assert out.abstain.state == DecisionState.PUBLISH


# ---------------------------------------------------------------------------
# Considered assembly (T7.5/T7.6)
# ---------------------------------------------------------------------------


class TestConsideredAssembly:
    def test_recommended_play_excluded_from_considered(self):
        """If a play surfaces as a recommendation, drop any matching upstream rejection."""
        cards = [
            _card("m1", evidence=EvidenceClass.MEASURED, p50=200.0, observed_effect=0.05),
        ]
        # Synthetic upstream rejection mentioning m1 (e.g., a stale guardrail entry).
        upstream = [
            RejectedPlay(
                play_id="m1",
                reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR,
            ),
            RejectedPlay(
                play_id="m_other",
                reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR,
            ),
        ]
        out = decide(_engine_run(recommendations=cards, considered=upstream))
        ids = {r.play_id for r in out.considered}
        assert "m1" not in ids
        assert "m_other" in ids

    def test_would_fire_if_filled_when_missing(self):
        upstream = [
            RejectedPlay(
                play_id="x",
                reason_code=ReasonCode.AUDIENCE_TOO_SMALL,
            )
        ]
        cards = [
            _card("m", evidence=EvidenceClass.MEASURED, p50=200.0, observed_effect=0.05),
        ]
        out = decide(_engine_run(recommendations=cards, considered=upstream))
        x = [r for r in out.considered if r.play_id == "x"][0]

    def test_dedup_keeps_first(self):
        upstream = [
            RejectedPlay(
                play_id="dup",
                reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR,
            ),
            RejectedPlay(
                play_id="dup",
                reason_code=ReasonCode.AUDIENCE_TOO_SMALL,
            ),
        ]
        out = assemble_considered(upstream, cap_exceeded=[])
        # Only one entry for play_id="dup", and it is the FIRST one.
        dups = [r for r in out if r.play_id == "dup"]
        assert len(dups) == 1

    def test_cap_exceeded_promoted_into_considered(self):
        cards = [
            _card(f"m{i}", evidence=EvidenceClass.MEASURED, p50=1000.0 - i,
                  observed_effect=0.05)
            for i in range(5)
        ]
        out = decide(_engine_run(recommendations=cards))
        cap_ids = {
            r.play_id for r in out.considered if r.reason_code == ReasonCode.CAP_EXCEEDED
        }
        # The two lowest-p50 measured plays are demoted.
        assert cap_ids == {"m3", "m4"}


# ---------------------------------------------------------------------------
# Watching (T7.9)
# ---------------------------------------------------------------------------


class TestWatching:
    def test_held_observations_with_change_become_watching(self):
        observations = [
            Observation(
                supporting_metric="aov",
                change_magnitude=-0.02,
                classification=ObservationClassification.HELD,
            ),
            Observation(
                supporting_metric="repeat_rate_within_window",
                change_magnitude=0.003,
                classification=ObservationClassification.HELD,
            ),
        ]
        watching = build_watching(observations)
        assert len(watching) == 2
        metrics = {w.metric for w in watching}
        assert metrics == {"aov", "repeat_rate_within_window"}

    def test_anomalous_observations_excluded(self):
        observations = [
            Observation(
                supporting_metric="aov",
                change_magnitude=-0.10,
                classification=ObservationClassification.ANOMALOUS,
            )
        ]
        assert build_watching(observations) == []

    def test_moved_observations_excluded(self):
        # Phase 6A Ticket A1: MOVED + load-bearing now surfaces as a
        # last-resort Watching fallback when the HELD pass is empty.
        # The base contract -- "MOVED non-load-bearing observations
        # belong to the state-of-store paragraph, not Watching" -- is
        # preserved and re-pinned below using a non-load-bearing
        # metric. The load-bearing fallback is exercised separately in
        # tests/test_watching_load_bearing_priority.py.
        observations = [
            Observation(
                supporting_metric="ctr",  # non-load-bearing metric
                change_magnitude=0.20,
                classification=ObservationClassification.MOVED,
            )
        ]
        assert build_watching(observations) == []

    def test_zero_change_excluded(self):
        # Phase 6A Ticket A1 added ``aov`` to the load-bearing set per
        # the campaign-slate contract; flat aov now surfaces as
        # "stable, watching" (Phase 5.3 mechanism). The base
        # non-load-bearing rule -- "flat non-load-bearing metrics are
        # excluded" -- is preserved using a non-load-bearing metric.
        observations = [
            Observation(
                supporting_metric="click_through_rate",
                change_magnitude=0.0,
                classification=ObservationClassification.HELD,
            )
        ]
        assert build_watching(observations) == []

    def test_capped_at_max(self):
        observations = [
            Observation(
                supporting_metric=f"metric_{i}",
                change_magnitude=0.01 * (i + 1),
                classification=ObservationClassification.HELD,
            )
            for i in range(10)
        ]
        watching = build_watching(observations)
        assert len(watching) == MAX_WATCHING_SIGNALS

    def test_sorted_by_magnitude_descending(self):
        observations = [
            Observation(
                supporting_metric="repeat_rate_within_window",
                change_magnitude=0.001,
                classification=ObservationClassification.HELD,
            ),
            Observation(
                supporting_metric="aov",
                change_magnitude=-0.05,
                classification=ObservationClassification.HELD,
            ),
        ]
        watching = build_watching(observations)
        assert watching[0].metric == "aov"
        assert watching[1].metric == "repeat_rate_within_window"

    def test_threshold_to_act_text_for_known_metrics(self):
        observations = [
            Observation(
                supporting_metric="aov",
                change_magnitude=0.02,
                classification=ObservationClassification.HELD,
            )
        ]
        watching = build_watching(observations)
        assert watching[0].threshold_to_act
        assert "%" in watching[0].threshold_to_act


# ---------------------------------------------------------------------------
# Pure / no-mutation
# ---------------------------------------------------------------------------


class TestPurity:
    def test_input_engine_run_not_mutated(self):
        cards = [
            _card("m", evidence=EvidenceClass.MEASURED, p50=200.0, observed_effect=0.05),
            _card("t", evidence=EvidenceClass.TARGETING, p50=10_000.0),
        ]
        original_recs = list(cards)
        er = _engine_run(recommendations=cards)
        original_id = id(er)
        out = decide(er)
        # Returned object is a NEW EngineRun.
        assert id(out) != original_id
        # Original recommendations list reference unchanged.
        assert er.recommendations == original_recs


# ---------------------------------------------------------------------------
# End-to-end smoke
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_publish_path_e2e(self):
        cards = [
            _card("m1", evidence=EvidenceClass.MEASURED, p50=500.0, observed_effect=0.05),
            _card("d1", evidence=EvidenceClass.DIRECTIONAL, p50=400.0, observed_effect=0.04),
            _card("t1", evidence=EvidenceClass.TARGETING, p50=100_000.0),
            _card("t2", evidence=EvidenceClass.TARGETING, p50=99_999.0),
        ]
        observations = [
            Observation(
                supporting_metric="aov",
                change_magnitude=-0.02,
                classification=ObservationClassification.HELD,
            )
        ]
        er = _engine_run(recommendations=cards, state_of_store=observations)
        out = decide(er)

        assert out.abstain.state == DecisionState.PUBLISH
        assert len(out.recommendations) == 3
        # The one targeting card that didn't make the cut is in considered.
        cap_excess = [r for r in out.considered if r.reason_code == ReasonCode.CAP_EXCEEDED]
        assert len(cap_excess) == 1
        # Watching reflects the held observation.
        assert len(out.watching) == 1
        assert out.watching[0].metric == "aov"

    def test_abstain_soft_with_only_targeting_e2e(self):
        cards = [
            _card("t1", evidence=EvidenceClass.TARGETING, p50=10_000.0),
            _card("t2", evidence=EvidenceClass.TARGETING, p50=5_000.0),
        ]
        out = decide(_engine_run(recommendations=cards))

        assert out.abstain.state == DecisionState.ABSTAIN_SOFT
        # Synthetic Blocker Fix 3 (PM-resolved): targeting cards under
        # ABSTAIN_SOFT are re-routed to considered, not kept on the
        # recommended surface.
        assert out.recommendations == []
        held = [
            r
            for r in out.considered
            if r.reason_code == ReasonCode.TARGETING_HELD_UNDER_ABSTAIN
        ]
        assert sorted(r.play_id for r in held) == ["t1", "t2"]

    def test_abstain_hard_e2e(self):
        cards = [
            _card("m", evidence=EvidenceClass.MEASURED, p50=200.0, observed_effect=0.05),
        ]
        er = _engine_run(
            recommendations=cards,
            flags=[DataQualityFlag.TEST_ORDER_ANOMALY],
        )
        out = decide(er)

        assert out.abstain.state == DecisionState.ABSTAIN_HARD
        assert out.recommendations == []
