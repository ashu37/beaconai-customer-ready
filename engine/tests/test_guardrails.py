"""Milestone 5 — Guardrail engine tests.

Covers each gate as a pure function plus the orchestrator
``apply_guardrails`` end-to-end.

Scope (per implementation-manager-overhaul-plan-final.md M5):
- T5.1 inventory gate
- T5.2 anomalous-window gate
- T5.3 scale-aware materiality floor
- T5.4 cannibalization / audience-overlap gate (incl. portfolio cap)
- T5.5 recently-run-fatigue stub
- T5.6 bias-correction default remains off (no bypass)
- T5.7 seasonality decoupled from confidence

Each test is structurally additive: with every M5 flag OFF, the
orchestrator must be a semantic no-op.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import (  # noqa: E402
    Abstain,
    Audience,
    Conflicts,
    DataQualityFlag,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Inventory,
    LaunchWindow,
    PlayCard,
    ReasonCode,
    RejectedPlay,
    RevenueRange,
    RevenueRangeSource,
    Scale,
)
from src.guardrails import (  # noqa: E402
    DEFAULT_FATIGUE_DAYS,
    DEFAULT_MIN_COVER_DAYS,
    DEFAULT_OVERLAP_THRESHOLD,
    DEFAULT_PORTFOLIO_CAP_FRACTION,
    HARD_DATA_QUALITY_FLAGS,
    SKU_PUSH_PLAYS,
    apply_guardrails,
    enforce_portfolio_cap,
    gate_anomaly,
    gate_cannibalization,
    gate_inventory,
    gate_materiality,
    gate_recently_run,
    scale_aware_materiality_floor,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_card(
    play_id: str,
    *,
    p50: float | None = None,
    audience_id: str | None = None,
    days_of_cover: float | None = None,
    suppressed: bool = False,
    evidence_class: EvidenceClass = EvidenceClass.MEASURED,
) -> PlayCard:
    rr = None
    if p50 is not None:
        rr = RevenueRange(
            p10=None,
            p50=float(p50),
            p90=None,
            source=RevenueRangeSource.STORE_OBSERVED,
            drivers=[],
            suppressed=suppressed,
        )
    aud = None
    if audience_id is not None:
        aud = Audience(id=audience_id, definition=audience_id, size=100)
    inv = None
    if days_of_cover is not None:
        inv = Inventory(skus=["sku-1"], days_of_cover=float(days_of_cover))
    return PlayCard(
        play_id=play_id,
        evidence_class=evidence_class,
        revenue_range=rr,
        audience=aud,
        inventory=inv,
    )


def _make_engine_run(
    *,
    recommendations: list[PlayCard] | None = None,
    flags: list[DataQualityFlag] | None = None,
    monthly_revenue: float | None = 100_000.0,
) -> EngineRun:
    return EngineRun(
        run_id="test-run",
        store_id="store-1",
        recommendations=list(recommendations or []),
        considered=[],
        data_quality_flags=list(flags or []),
        scale=Scale(monthly_revenue=monthly_revenue),
    )


# ---------------------------------------------------------------------------
# T5.3 — scale-aware materiality floor
# ---------------------------------------------------------------------------


class TestScaleAwareFloor:
    def test_below_1m_arr_uses_2pct_or_5k(self):
        # ARR < $1M: max(5k, 2% * monthly_revenue)
        # monthly_revenue = $20k => ARR $240k < $1M; 2% = $400 < $5k => $5k
        assert scale_aware_materiality_floor(20_000) == 5_000.0
        # monthly_revenue = $80k => ARR $960k < $1M; 2% = $1,600 < $5k => $5k
        assert scale_aware_materiality_floor(80_000) == 5_000.0
        # monthly_revenue = $50k => 2% = $1k < $5k => $5k
        assert scale_aware_materiality_floor(50_000) == 5_000.0

    def test_1m_to_5m_arr_uses_3pct_or_10k(self):
        # $1M ARR boundary: monthly_revenue = $1M/12 ≈ $83,333.33
        # monthly_revenue = $90k => ARR $1.08M (1M-5M tier)
        # 3% = $2,700 < $10k => $10k
        assert scale_aware_materiality_floor(90_000) == 10_000.0
        # monthly_revenue = $400k => ARR $4.8M (1M-5M tier)
        # 3% = $12k > $10k => $12k
        assert scale_aware_materiality_floor(400_000) == 12_000.0

    def test_above_5m_arr_uses_5pct_or_25k(self):
        # monthly_revenue = $500k => ARR $6M (>5M tier)
        # 5% = $25k tied with absolute => $25k
        assert scale_aware_materiality_floor(500_000) == 25_000.0
        # monthly_revenue = $1M => ARR $12M; 5% = $50k > $25k => $50k
        assert scale_aware_materiality_floor(1_000_000) == 50_000.0

    def test_unknown_or_nonpositive_returns_minimum_floor(self):
        assert scale_aware_materiality_floor(None) == 5_000.0
        assert scale_aware_materiality_floor(0) == 5_000.0
        assert scale_aware_materiality_floor(-100) == 5_000.0
        assert scale_aware_materiality_floor("not-a-number") == 5_000.0

    def test_tier_boundary_is_inclusive_lower_exclusive_upper(self):
        # Exactly $1M ARR: 12 * mr == 1_000_000 => mr ≈ 83333.33
        # ARR == $1M is NOT < $1M so falls into 1M-5M tier.
        mr = 1_000_000.0 / 12.0
        floor = scale_aware_materiality_floor(mr)
        # 3% of mr ≈ $2,500 < $10k -> $10k
        assert floor == 10_000.0
        # Exactly $5M ARR: mr ≈ 416666.67 -> falls into >5M tier
        mr5 = 5_000_000.0 / 12.0
        floor5 = scale_aware_materiality_floor(mr5)
        # 5% of mr ≈ $20,833 < $25k -> $25k
        assert floor5 == 25_000.0


# ---------------------------------------------------------------------------
# T5.3 — materiality gate
# ---------------------------------------------------------------------------


class TestMaterialityGate:
    def test_below_floor_rejects_with_correct_reason(self):
        cand = _make_card("winback_21_45", p50=1_000.0)
        rej = gate_materiality(cand, monthly_revenue=80_000)  # floor=$5k
        assert rej is not None
        assert rej.reason_code == ReasonCode.MATERIALITY_BELOW_FLOOR

    def test_at_or_above_floor_returns_none(self):
        cand = _make_card("winback_21_45", p50=10_000.0)
        rej = gate_materiality(cand, monthly_revenue=80_000)
        assert rej is None

    def test_no_p50_is_no_op(self):
        cand = _make_card("winback_21_45", p50=None)
        assert gate_materiality(cand, monthly_revenue=80_000) is None

    def test_suppressed_range_is_no_op(self):
        cand = _make_card("winback_21_45", p50=100.0, suppressed=True)
        assert gate_materiality(cand, monthly_revenue=80_000) is None

    def test_no_monthly_revenue_is_no_op(self):
        cand = _make_card("winback_21_45", p50=100.0)
        assert gate_materiality(cand, monthly_revenue=None) is None
        assert gate_materiality(cand, monthly_revenue=0) is None

    def test_three_arr_tiers_each_have_correct_threshold_behavior(self):
        # Tier 1 (<$1M ARR): p50=$5,001 passes; p50=$4,999 fails
        cand_pass = _make_card("p1", p50=5_001.0)
        cand_fail = _make_card("p2", p50=4_999.0)
        assert gate_materiality(cand_pass, monthly_revenue=50_000) is None
        assert gate_materiality(cand_fail, monthly_revenue=50_000) is not None

        # Tier 2 ($1M-$5M ARR): p50=$10,001 passes; p50=$9,999 fails
        cand_pass = _make_card("p1", p50=10_001.0)
        cand_fail = _make_card("p2", p50=9_999.0)
        assert gate_materiality(cand_pass, monthly_revenue=200_000) is None
        assert gate_materiality(cand_fail, monthly_revenue=200_000) is not None

        # Tier 3 (>$5M ARR): p50=$50,001 passes; p50=$49,999 fails (5% of mr=$1M)
        cand_pass = _make_card("p1", p50=50_001.0)
        cand_fail = _make_card("p2", p50=49_999.0)
        assert gate_materiality(cand_pass, monthly_revenue=1_000_000) is None
        assert gate_materiality(cand_fail, monthly_revenue=1_000_000) is not None


# ---------------------------------------------------------------------------
# T5.1 — inventory gate
# ---------------------------------------------------------------------------


class TestInventoryGate:
    def test_non_sku_play_no_op(self):
        cand = _make_card("winback_21_45")  # not a SKU push play
        # Even with inventory_metrics being None, gate is no-op.
        assert gate_inventory(cand, None) is None

    def test_no_inventory_data_returns_none(self):
        cand = _make_card("bestseller_amplify")
        assert gate_inventory(cand, None) is None
        # Also empty df is treated as no-op.
        empty = pd.DataFrame(columns=["sku", "cover_days"])
        assert gate_inventory(cand, empty) is None

    def test_low_cover_blocks_sku_push_plays(self):
        df = pd.DataFrame({"sku": ["a", "b"], "cover_days": [9.0, 18.0]})
        for play_id in SKU_PUSH_PLAYS:
            cand = _make_card(play_id)
            rej = gate_inventory(cand, df, min_cover_days=21)
            assert rej is not None, f"expected rejection for {play_id}"
            assert rej.reason_code == ReasonCode.INVENTORY_BLOCKED

    def test_high_cover_does_not_block(self):
        df = pd.DataFrame({"sku": ["a", "b"], "cover_days": [40.0, 50.0]})
        cand = _make_card("bestseller_amplify")
        assert gate_inventory(cand, df, min_cover_days=21) is None

    def test_threshold_is_inclusive_above(self):
        # cover_days exactly equal to threshold should NOT block.
        df = pd.DataFrame({"sku": ["a"], "cover_days": [21.0]})
        cand = _make_card("bestseller_amplify")
        assert gate_inventory(cand, df, min_cover_days=21) is None
        # Just below threshold blocks.
        df2 = pd.DataFrame({"sku": ["a"], "cover_days": [20.5]})
        assert gate_inventory(cand, df2, min_cover_days=21) is not None

    def test_uses_candidate_inventory_when_present(self):
        cand = _make_card("bestseller_amplify", days_of_cover=5.0)
        # Inventory metrics is None but candidate has its own inventory.
        rej = gate_inventory(cand, None, min_cover_days=21)
        assert rej is not None
        assert rej.reason_code == ReasonCode.INVENTORY_BLOCKED

    def test_default_threshold_is_21_days(self):
        # Default M5 threshold is 21 days.
        assert DEFAULT_MIN_COVER_DAYS == 21
        df = pd.DataFrame({"sku": ["a"], "cover_days": [20.0]})
        cand = _make_card("bestseller_amplify")
        # Without an explicit threshold, default 21 must be used.
        assert gate_inventory(cand, df) is not None


# ---------------------------------------------------------------------------
# T5.2 — anomalous-window gate
# ---------------------------------------------------------------------------


class TestAnomalyGate:
    def test_no_flags_returns_none(self):
        assert gate_anomaly([]) is None
        assert gate_anomaly(None) is None

    def test_post_promo_only_does_not_trigger_hard(self):
        # B-1: POST_PROMO_WINDOW is a soft load-bearing anomaly. It now
        # routes to ABSTAIN_SOFT (per-play hold), never ABSTAIN_HARD.
        out = gate_anomaly([DataQualityFlag.POST_PROMO_WINDOW])
        assert out is not None
        state, _reason, _flags = out
        assert state == DecisionState.ABSTAIN_SOFT

    @pytest.mark.parametrize("flag", sorted(HARD_DATA_QUALITY_FLAGS, key=lambda f: f.value))
    def test_each_hard_flag_triggers_abstain_hard(self, flag):
        out = gate_anomaly([flag])
        assert out is not None
        state, reason, hard_flags = out
        assert state == DecisionState.ABSTAIN_HARD
        assert flag.value in reason
        assert flag in hard_flags

    def test_multiple_flags_combined(self):
        out = gate_anomaly(
            [DataQualityFlag.BFCM_OVERLAP, DataQualityFlag.REFUND_STORM]
        )
        assert out is not None
        state, reason, hard = out
        assert state == DecisionState.ABSTAIN_HARD
        assert "bfcm_overlap" in reason and "refund_storm" in reason


# ---------------------------------------------------------------------------
# T5.4 — cannibalization / overlap gate
# ---------------------------------------------------------------------------


class TestCannibalizationGate:
    def test_no_overlap_keeps_all(self):
        cands = [_make_card("a"), _make_card("b"), _make_card("c")]
        kept, rej = gate_cannibalization(cands, {})
        assert [c.play_id for c in kept] == ["a", "b", "c"]
        assert rej == []

    def test_below_threshold_keeps_all(self):
        cands = [_make_card("a"), _make_card("b")]
        overlap = {"a": {"b": 0.49}, "b": {"a": 0.49}}
        kept, rej = gate_cannibalization(cands, overlap)
        assert [c.play_id for c in kept] == ["a", "b"]
        assert rej == []

    def test_above_threshold_demotes_lower_priority(self):
        # Index 0 = highest priority; 'b' should be demoted.
        cands = [_make_card("a"), _make_card("b")]
        overlap = {"a": {"b": 0.6}, "b": {"a": 0.6}}
        kept, rej = gate_cannibalization(cands, overlap)
        assert [c.play_id for c in kept] == ["a"]
        assert len(rej) == 1
        assert rej[0].play_id == "b"
        assert rej[0].reason_code == ReasonCode.AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY
        # Higher-priority card was annotated with conflicts.
        assert kept[0].conflicts is not None
        assert "b" in (kept[0].conflicts.cannibalized_by or [])

    def test_three_overlapping_plays_demote_two(self):
        cands = [_make_card("a"), _make_card("b"), _make_card("c")]
        overlap = {
            "a": {"b": 0.7, "c": 0.6},
            "b": {"a": 0.7, "c": 0.5},
            "c": {"a": 0.6, "b": 0.5},
        }
        kept, rej = gate_cannibalization(cands, overlap)
        # Only 'a' (highest priority) should remain.
        assert [c.play_id for c in kept] == ["a"]
        assert sorted([r.play_id for r in rej]) == ["b", "c"]
        for r in rej:
            assert r.reason_code == ReasonCode.AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY

    def test_threshold_is_50_percent_inclusive(self):
        cands = [_make_card("a"), _make_card("b")]
        # Exactly 0.5 should fire (inclusive).
        overlap = {"a": {"b": 0.5}}
        kept, rej = gate_cannibalization(cands, overlap, threshold=0.5)
        assert [c.play_id for c in kept] == ["a"]
        assert len(rej) == 1

    def test_input_list_not_mutated(self):
        cards = [_make_card("a"), _make_card("b")]
        overlap = {"a": {"b": 0.6}}
        before = [c.play_id for c in cards]
        gate_cannibalization(cards, overlap)
        after = [c.play_id for c in cards]
        assert before == after


# ---------------------------------------------------------------------------
# T5.4 — portfolio cap
# ---------------------------------------------------------------------------


class TestPortfolioCap:
    def test_cap_fraction_default_is_25_percent(self):
        assert DEFAULT_PORTFOLIO_CAP_FRACTION == 0.25

    def test_under_cap_keeps_all(self):
        cands = [
            _make_card("a", p50=10_000.0),
            _make_card("b", p50=5_000.0),
        ]
        kept, rej = enforce_portfolio_cap(cands, monthly_revenue=100_000)
        assert [c.play_id for c in kept] == ["a", "b"]
        assert rej == []

    def test_over_cap_demotes_lowest_priority(self):
        # cap = 25k. Sums: 15k + 8k = 23k (kept) + 4k (kept too -> 27k > 25k)
        cands = [
            _make_card("a", p50=15_000.0),
            _make_card("b", p50=8_000.0),
            _make_card("c", p50=4_000.0),
        ]
        kept, rej = enforce_portfolio_cap(cands, monthly_revenue=100_000)
        assert [c.play_id for c in kept] == ["a", "b"]
        assert len(rej) == 1
        assert rej[0].play_id == "c"
        assert rej[0].reason_code == ReasonCode.CANNIBALIZATION_DEMOTED

    def test_backoff_keeps_top1_when_cap_would_drop_everything(self):
        # cap = 5k. First p50 alone ($30k) exceeds. Backoff retains top-1.
        cands = [
            _make_card("a", p50=30_000.0),
            _make_card("b", p50=20_000.0),
        ]
        kept, rej = enforce_portfolio_cap(cands, monthly_revenue=20_000)
        assert [c.play_id for c in kept] == ["a"]
        assert [r.play_id for r in rej] == ["b"]

    def test_no_revenue_returns_inputs(self):
        cands = [_make_card("a", p50=100.0)]
        kept, rej = enforce_portfolio_cap(cands, monthly_revenue=None)
        assert kept == cands
        assert rej == []


# ---------------------------------------------------------------------------
# T5.5 — recently-run-fatigue stub
# ---------------------------------------------------------------------------


class TestRecentlyRunFatigue:
    def test_no_history_file_returns_none(self, tmp_path: Path):
        cand = _make_card("winback_21_45", audience_id="winback_21_45_inactive")
        # Path doesn't exist.
        path = tmp_path / "missing.json"
        assert gate_recently_run(cand, str(path)) is None
        # Also: None path argument.
        assert gate_recently_run(cand, None) is None

    def test_empty_history_returns_none(self, tmp_path: Path):
        path = tmp_path / "recommended_history.json"
        path.write_text("[]")
        cand = _make_card("winback_21_45", audience_id="winback_21_45_inactive")
        assert gate_recently_run(cand, str(path)) is None

    def test_old_record_does_not_fire(self, tmp_path: Path):
        path = tmp_path / "recommended_history.json"
        old_ts = (
            datetime.now(timezone.utc) - timedelta(days=120)
        ).isoformat()
        path.write_text(
            json.dumps(
                [
                    {
                        "store_id": "store-1",
                        "play_id": "winback_21_45",
                        "audience_id": "winback_21_45_inactive",
                        "ts": old_ts,
                    }
                ]
            )
        )
        cand = _make_card("winback_21_45", audience_id="winback_21_45_inactive")
        assert gate_recently_run(cand, str(path)) is None

    def test_recent_record_fires_with_correct_reason(self, tmp_path: Path):
        path = tmp_path / "recommended_history.json"
        recent_ts = (
            datetime.now(timezone.utc) - timedelta(days=5)
        ).isoformat()
        path.write_text(
            json.dumps(
                [
                    {
                        "store_id": "store-1",
                        "play_id": "winback_21_45",
                        "audience_id": "winback_21_45_inactive",
                        "ts": recent_ts,
                    }
                ]
            )
        )
        cand = _make_card("winback_21_45", audience_id="winback_21_45_inactive")
        rej = gate_recently_run(cand, str(path))
        assert rej is not None
        assert rej.reason_code == ReasonCode.RECENTLY_RUN_FATIGUE

    def test_audience_mismatch_does_not_fire(self, tmp_path: Path):
        path = tmp_path / "recommended_history.json"
        recent_ts = (
            datetime.now(timezone.utc) - timedelta(days=5)
        ).isoformat()
        path.write_text(
            json.dumps(
                [
                    {
                        "store_id": "store-1",
                        "play_id": "winback_21_45",
                        "audience_id": "different-audience",
                        "ts": recent_ts,
                    }
                ]
            )
        )
        cand = _make_card("winback_21_45", audience_id="winback_21_45_inactive")
        # Both records carry audience_id and they differ -> no match.
        assert gate_recently_run(cand, str(path)) is None

    def test_default_fatigue_window_is_28_days(self):
        assert DEFAULT_FATIGUE_DAYS == 28


# ---------------------------------------------------------------------------
# Orchestrator — apply_guardrails
# ---------------------------------------------------------------------------


class TestApplyGuardrails:
    def test_all_flags_off_is_noop(self):
        run = _make_engine_run(
            recommendations=[_make_card("winback_21_45", p50=1_000.0)],
            monthly_revenue=100_000,
        )
        # No cfg keys set -> all flags off.
        out = apply_guardrails(run, cfg={})
        assert [c.play_id for c in out.recommendations] == ["winback_21_45"]
        assert out.considered == []
        assert out.abstain.state == DecisionState.PUBLISH

    def test_hard_data_quality_flag_triggers_abstain_hard(self):
        run = _make_engine_run(
            recommendations=[_make_card("winback_21_45", p50=10_000.0)],
            flags=[DataQualityFlag.BFCM_OVERLAP],
            monthly_revenue=100_000,
        )
        out = apply_guardrails(run, cfg={"ANOMALY_GATE_ENABLED": True})
        assert out.abstain.state == DecisionState.ABSTAIN_HARD
        assert out.recommendations == []
        # Considered list contains the play with ANOMALOUS_WINDOW reason.
        assert len(out.considered) == 1
        assert out.considered[0].reason_code == ReasonCode.ANOMALOUS_WINDOW

    def test_inventory_gate_blocks_low_cover_sku_play(self):
        df = pd.DataFrame({"sku": ["a"], "cover_days": [5.0]})
        run = _make_engine_run(
            recommendations=[
                _make_card("bestseller_amplify", p50=20_000.0),
                _make_card("winback_21_45", p50=10_000.0),
            ],
            monthly_revenue=200_000,
        )
        out = apply_guardrails(
            run,
            inventory_metrics=df,
            cfg={"INVENTORY_GATE_ENABLED": True},
        )
        rec_ids = [c.play_id for c in out.recommendations]
        assert "bestseller_amplify" not in rec_ids
        assert "winback_21_45" in rec_ids
        rej_ids = [r.play_id for r in out.considered]
        assert "bestseller_amplify" in rej_ids
        rej_codes = [r.reason_code for r in out.considered]
        assert ReasonCode.INVENTORY_BLOCKED in rej_codes

    def test_no_inventory_data_does_not_block(self):
        run = _make_engine_run(
            recommendations=[_make_card("bestseller_amplify", p50=20_000.0)],
            monthly_revenue=200_000,
        )
        out = apply_guardrails(
            run,
            inventory_metrics=None,
            cfg={"INVENTORY_GATE_ENABLED": True},
        )
        # Without inventory data the gate is a no-op; play survives.
        rec_ids = [c.play_id for c in out.recommendations]
        assert "bestseller_amplify" in rec_ids
        assert out.considered == []

    def test_materiality_floor_strips_below_floor(self):
        run = _make_engine_run(
            recommendations=[
                _make_card("a", p50=1_000.0),  # below $5k tier-1 floor
                _make_card("b", p50=10_000.0),  # above
            ],
            monthly_revenue=50_000,
        )
        out = apply_guardrails(
            run, cfg={"MATERIALITY_FLOOR_SCALE_AWARE": True}
        )
        assert [c.play_id for c in out.recommendations] == ["b"]
        assert any(
            r.reason_code == ReasonCode.MATERIALITY_BELOW_FLOOR
            for r in out.considered
        )
        # Scale.materiality_floor is recomputed.
        assert out.scale.materiality_floor == 5_000.0

    def test_cannibalization_demotes_overlapping_play(self):
        run = _make_engine_run(
            recommendations=[
                _make_card("a", p50=10_000.0),
                _make_card("b", p50=10_000.0),
            ],
            monthly_revenue=200_000,
        )
        overlap = {"a": {"b": 0.7}, "b": {"a": 0.7}}
        out = apply_guardrails(
            run,
            audience_overlap=overlap,
            cfg={"CANNIBALIZATION_GATE_ENABLED": True},
        )
        assert [c.play_id for c in out.recommendations] == ["a"]
        assert any(
            r.reason_code == ReasonCode.AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY
            and r.play_id == "b"
            for r in out.considered
        )

    def test_portfolio_cap_with_cannibalization_flag(self):
        # Cap = 25% of $20k = $5k. Top-1 backoff keeps "a" alone.
        run = _make_engine_run(
            recommendations=[
                _make_card("a", p50=30_000.0),
                _make_card("b", p50=20_000.0),
            ],
            monthly_revenue=20_000,
        )
        out = apply_guardrails(
            run, cfg={"CANNIBALIZATION_GATE_ENABLED": True}
        )
        assert [c.play_id for c in out.recommendations] == ["a"]

    def test_input_engine_run_not_mutated(self):
        run = _make_engine_run(
            recommendations=[_make_card("bestseller_amplify", p50=20_000.0)],
            monthly_revenue=200_000,
        )
        df = pd.DataFrame({"sku": ["a"], "cover_days": [3.0]})
        before_len = len(run.recommendations)
        before_considered = list(run.considered)
        _ = apply_guardrails(
            run, inventory_metrics=df, cfg={"INVENTORY_GATE_ENABLED": True}
        )
        # Original is unchanged.
        assert len(run.recommendations) == before_len
        assert run.considered == before_considered

    def test_combined_gates_compose(self):
        # Inventory gate + materiality gate together.
        df = pd.DataFrame({"sku": ["a"], "cover_days": [3.0]})
        run = _make_engine_run(
            recommendations=[
                _make_card("bestseller_amplify", p50=20_000.0),  # blocked by inventory
                _make_card("a", p50=100.0),  # blocked by materiality
                _make_card("b", p50=20_000.0),  # passes both
            ],
            monthly_revenue=200_000,
        )
        out = apply_guardrails(
            run,
            inventory_metrics=df,
            cfg={
                "INVENTORY_GATE_ENABLED": True,
                "MATERIALITY_FLOOR_SCALE_AWARE": True,
            },
        )
        assert [c.play_id for c in out.recommendations] == ["b"]
        rej_codes = sorted(r.reason_code.value for r in out.considered)
        assert "inventory_blocked" in rej_codes
        assert "materiality_below_floor" in rej_codes
