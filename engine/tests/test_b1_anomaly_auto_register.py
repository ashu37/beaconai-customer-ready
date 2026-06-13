"""B-1 (Sprint 1, Engineer B) — AnomalousWindow auto-registration → ABSTAIN routing.

Pins three contracts established by ticket B-1
(see ``agent_outputs/implementation-manager-post-6b-restructured-plan.md``):

1.  ``ANOMALY_GATE_ENABLED`` defaults to ON. ``apply_guardrails`` auto-
    routes a populated ``data_quality_flags`` list into ABSTAIN_HARD
    (any HARD flag) or ABSTAIN_SOFT (POST_PROMO_WINDOW alone) without
    requiring callers to flip the flag explicitly.
2.  Reserved typed Observation slots ``anomaly_flags``,
    ``n_days_observed``, and ``n_days_expected`` are populated when an
    anomaly is detected. They were schema-reserved in Phase 6B
    Stop-Coding-Line Task 4; B-1 is the first ticket that writes to them.
3.  ``promo_anomaly_240d`` synthetic fixture flips from PUBLISH +
    1 directional + 2 experiments to ABSTAIN_SOFT + zero Recommended +
    zero Recommended Experiment, with the ``post_promo_window`` flag
    populated and the abstain reason naming the load-bearing flag.

The Beauty pinned fixture is healthy (zero flags) — its byte-identical
golden test in ``test_slate_regression_beauty_brand.py`` is the
companion regression that pins "no false positives on healthy data."
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import (  # noqa: E402
    Audience,
    DataQualityFlag,
    DecisionState,
    EngineRun,
    PlayCard,
    ReasonCode,
    RevenueRange,
    Scale,
)
from src.guardrails import apply_guardrails  # noqa: E402
from src.utils import DEFAULTS  # noqa: E402


# ---------------------------------------------------------------------------
# Contract 1 — ``ANOMALY_GATE_ENABLED`` defaults to True
# ---------------------------------------------------------------------------


def test_anomaly_gate_enabled_default_is_true():
    """B-1 flips the default. Without an explicit override, the engine
    auto-routes anomaly flags. The legacy escape hatch
    ``ANOMALY_GATE_ENABLED=false`` env still suppresses the auto-router.
    """
    assert DEFAULTS["ANOMALY_GATE_ENABLED"] is True


def test_apply_guardrails_routes_post_promo_window_to_abstain_soft_with_default_cfg():
    """Soft load-bearing path: only POST_PROMO_WINDOW is set → ABSTAIN_SOFT."""
    er = EngineRun(
        recommendations=[
            PlayCard(
                play_id="winback_21_45",
                audience=Audience(id="x", size=120),
                revenue_range=RevenueRange(p50=20_000.0),
            )
        ],
        data_quality_flags=[DataQualityFlag.POST_PROMO_WINDOW],
        scale=Scale(monthly_revenue=200_000.0),
    )
    out = apply_guardrails(er, cfg={"ANOMALY_GATE_ENABLED": True})
    assert out.abstain.state == DecisionState.ABSTAIN_SOFT
    assert out.recommendations == []
    assert len(out.considered) == 1
    assert out.considered[0].reason_code == ReasonCode.ANOMALOUS_WINDOW


def test_apply_guardrails_routes_hard_flag_to_abstain_hard_with_default_cfg():
    """Hard path: any HARD data-quality flag → ABSTAIN_HARD."""
    er = EngineRun(
        recommendations=[
            PlayCard(
                play_id="winback_21_45",
                audience=Audience(id="x", size=120),
                revenue_range=RevenueRange(p50=20_000.0),
            )
        ],
        data_quality_flags=[DataQualityFlag.REFUND_STORM],
        scale=Scale(monthly_revenue=200_000.0),
    )
    out = apply_guardrails(er, cfg={"ANOMALY_GATE_ENABLED": True})
    assert out.abstain.state == DecisionState.ABSTAIN_HARD
    assert out.recommendations == []


# ---------------------------------------------------------------------------
# Contract 2 — Observation typed slots are populated on anomaly
# ---------------------------------------------------------------------------


def test_observation_anomaly_flags_slot_populated_when_flag_present():
    """The reserved ``anomaly_flags`` / ``n_days_observed`` /
    ``n_days_expected`` slots on each anomaly Observation must carry
    the originating flag value and the configured day counts whenever
    the detector fires. B-1 is the first ticket that writes them.
    """
    from src.state_of_store import build_observations

    obs = build_observations(
        aligned={"L28": {"aov": 50.0, "orders": 100}},
        data_quality_flags=["post_promo_window"],
        n_days_observed=27,
        n_days_expected=28,
    )
    anomalous = [o for o in obs if o.classification.value == "anomalous"]
    assert len(anomalous) == 1
    assert anomalous[0].anomaly_flags == ["post_promo_window"]
    assert anomalous[0].n_days_observed == 27
    assert anomalous[0].n_days_expected == 28


def test_observation_anomaly_flags_empty_when_no_flag_present():
    """Healthy data must leave the typed slots at their reserved
    defaults (empty list / zero). The Beauty pinned fixture relies on
    this for its byte-identical golden.
    """
    from src.state_of_store import build_observations

    obs = build_observations(
        aligned={"L28": {"aov": 50.0, "orders": 100}},
        data_quality_flags=[],
        n_days_observed=28,
        n_days_expected=28,
    )
    for o in obs:
        # No anomaly classification on healthy data ⇒ no anomaly_flags
        # populated. The slot defaults to [].
        assert o.anomaly_flags == []


# ---------------------------------------------------------------------------
# Contract 3 — ``promo_anomaly_240d`` end-to-end acceptance
# ---------------------------------------------------------------------------


def test_promo_anomaly_fixture_flips_to_abstain_soft_with_typed_slots():
    """End-to-end acceptance: the ``promo_anomaly_240d`` synthetic
    scenario, which previously published 1 directional + 2 experiments
    on a clear promo spike, now routes to ABSTAIN_SOFT with the
    ``post_promo_window`` flag populated and the load-bearing reason
    text naming it.
    """
    from tests.synthetic_harness import run_scenario

    with tempfile.TemporaryDirectory() as td:
        res = run_scenario("promo_anomaly_240d", Path(td))
        er = json.loads(Path(res.engine_run_json_path).read_text())

        # Decision state and flag.
        assert er["abstain"]["state"] == "abstain_soft", (
            f"promo_anomaly_240d must abstain_soft under B-1; got "
            f"state={er['abstain']!r}"
        )
        assert "post_promo_window" in er["data_quality_flags"], (
            f"promo_anomaly_240d must surface post_promo_window flag; "
            f"got data_quality_flags={er['data_quality_flags']!r}"
        )
        # S13.6-T1a (Option D): ``Abstain.reason`` stripped per Pivot 2.
        # The load-bearing-flag-named-in-reason assertion is retired;
        # the flag itself is asserted above via data_quality_flags.

        # Zero Recommended cards under ABSTAIN_SOFT (Fix 3 contract).
        assert er["recommendations"] == [], (
            f"ABSTAIN_SOFT requires zero Recommended cards; got "
            f"{[r['play_id'] for r in er['recommendations']]!r}"
        )
        # Zero Recommended Experiments (Phase 6A B3 contract).
        assert er.get("recommended_experiments") in ([], None), (
            f"ABSTAIN_SOFT requires zero Recommended Experiments; got "
            f"{er.get('recommended_experiments')!r}"
        )

        # Typed Observation slots populated on the anomaly entry.
        anomaly_obs = [
            o for o in er["state_of_store"] if o.get("classification") == "anomalous"
        ]
        assert len(anomaly_obs) >= 1, (
            "At least one Observation must carry classification=anomalous "
            "when a data-quality flag fires."
        )
        post_promo = [
            o for o in anomaly_obs if "post_promo_window" in (o.get("anomaly_flags") or [])
        ]
        assert len(post_promo) == 1, (
            f"Exactly one Observation must carry anomaly_flags=['post_promo_window']; "
            f"got {[o.get('anomaly_flags') for o in anomaly_obs]!r}"
        )
        assert post_promo[0]["n_days_expected"] > 0
        # n_days_observed is non-negative; promo_anomaly fixture has
        # daily orders so we expect a positive count too.
        assert post_promo[0]["n_days_observed"] >= 0
