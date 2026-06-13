"""Milestone 1 T1.1: EngineRun schema instantiation, serialization, round-trip.

These tests guard the ``src.engine_run`` typed contract:

- A default ``EngineRun()`` is instantiable, serializes to a dict, and
  round-trips through ``from_dict``.
- Empty ``data_quality_flags`` serialize as an empty list (not omitted)
  per T1.6 ("ensure it serializes even when empty").
- Enums round-trip through their string values.
- A fully-populated EngineRun (every nested record exercised) round-trips
  byte-equal through ``to_dict`` / ``from_dict``.
- The 12 reason codes (11 from PM-Q3 + ``cap_exceeded`` from M7) are all
  declared.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import (  # noqa: E402
    Abstain,
    Audience,
    BriefingMeta,
    Conflicts,
    DataQualityFlag,
    DataWindow,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Inventory,
    LaunchWindow,
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
    WouldBeMeasuredBy,
)


def test_default_instantiable_and_json_safe():
    er = EngineRun()
    payload = er.to_dict()
    # must be JSON-serializable
    raw = json.dumps(payload)
    assert isinstance(raw, str)
    # T1.6: empty data_quality_flags MUST appear, not be omitted.
    assert "data_quality_flags" in payload
    assert payload["data_quality_flags"] == []
    # state defaults to publish.
    assert payload["abstain"]["state"] == DecisionState.PUBLISH.value


def test_round_trip_empty_run():
    er = EngineRun()
    payload = er.to_dict()
    er2 = EngineRun.from_dict(payload)
    assert er2.to_dict() == payload


def test_round_trip_fully_populated_run():
    er = EngineRun(
        run_id="run-1",
        store_id="store-x",
        anchor_date="2026-05-01T12:00:00",
        data_window=DataWindow(
            primary_window="L28",
            available_windows=["L7", "L28", "L56", "L90"],
            anchor_quality="good",
        ),
        cold_start=False,
        data_quality_flags=[DataQualityFlag.BFCM_OVERLAP, DataQualityFlag.REFUND_STORM],
        abstain=Abstain(state=DecisionState.ABSTAIN_HARD),
        state_of_store=[
            Observation(
                supporting_metric="aov",
                change_magnitude=0.05,
                classification=ObservationClassification.MOVED,
            ),
            Observation(),
        ],
        recommendations=[
            PlayCard(
                play_id="winback",
                evidence_class=EvidenceClass.MEASURED,
                confidence_label="Strong",
                audience=Audience(
                    id="winback_21_45",
                    definition="bought 21-45 days ago",
                    size=200,
                    fraction_of_base=0.18,
                    overlap_with=["bestseller_amplify"],
                ),
                measurement=Measurement(
                    metric="repeat_rate_within_window",
                    observed_effect=0.04,
                    n=200,
                    primary_window="L28",
                    consistency_across_windows=3,
                    p_internal=0.012,
                    ci_internal=[0.01, 0.07],
                ),
                revenue_range=RevenueRange(
                    p10=2000.0,
                    p50=4500.0,
                    p90=7500.0,
                    source=RevenueRangeSource.STORE_OBSERVED,
                    drivers=[{"name": "observed_repeat_rate_lift", "value": 0.04}],
                    suppressed=False,
                ),
                inventory=Inventory(skus=["SKU1"], days_of_cover=42.0, gate_passed=True),
                conflicts=Conflicts(
                    cannibalized_by=["bestseller_amplify"], audience_overlap_pct=0.12
                ),
                launch_window=LaunchWindow(recommended="this_week"),
                # S13.6-T2: klaviyo_brief_inputs removed (founder lock-in #6).
                receipts_ref="debug/winback.html",
            )
        ],
        considered=[
            RejectedPlay(
                play_id="bestseller_amplify",
                reason_code=ReasonCode.AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY,
            ),
            RejectedPlay(
                play_id="overstock_demand_push",
                reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR,
            ),
        ],
        watching=[
            WatchedSignal(
                metric="aov",
                current=80.0,
                prior=82.0,
                trend="down",
                threshold_to_act="-5% vs prior",
            )
        ],
        scale=Scale(
            monthly_revenue=120000.0,
            customer_base_est=1500,
            materiality_floor=5000.0,
        ),
        briefing_meta=BriefingMeta(
            confidence_mode="learning",
            vertical="beauty",
            subvertical="skincare",
            stage="growth",
            seasonality_tag="post_summer",
        ),
    )

    payload = er.to_dict()
    # JSON serializable.
    raw = json.dumps(payload)
    payload2 = json.loads(raw)
    er2 = EngineRun.from_dict(payload2)
    assert er2.to_dict() == payload


def test_enums_round_trip_via_string_values():
    er = EngineRun(
        data_quality_flags=[DataQualityFlag.TEST_ORDER_ANOMALY],
        abstain=Abstain(state=DecisionState.ABSTAIN_SOFT),
        considered=[
            RejectedPlay(play_id="x", reason_code=ReasonCode.AUDIENCE_TOO_SMALL)
        ],
    )
    payload = er.to_dict()
    assert payload["data_quality_flags"] == ["test_order_anomaly"]
    assert payload["abstain"]["state"] == "abstain_soft"
    assert payload["considered"][0]["reason_code"] == "audience_too_small"

    er2 = EngineRun.from_dict(payload)
    assert er2.data_quality_flags == [DataQualityFlag.TEST_ORDER_ANOMALY]
    assert er2.abstain.state == DecisionState.ABSTAIN_SOFT
    assert er2.considered[0].reason_code == ReasonCode.AUDIENCE_TOO_SMALL


def test_all_reason_codes_declared():
    """The 11 PM-Q3 codes plus M7 ``cap_exceeded`` (12) plus
    Synthetic Blocker Fix 3's ``targeting_held_under_abstain`` (13)
    plus Sprint 5 S5-T2's ``supplement_cadence_outside_window`` (14 total).
    """
    expected = {
        "audience_too_small",
        "audience_overlap_with_higher_priority",
        "inventory_blocked",
        "no_measured_signal",
        "signal_inconsistent_across_windows",
        "anomalous_window",
        "cold_start_insufficient_data",
        "cannibalization_demoted",
        "recently_run_fatigue",
        "materiality_below_floor",
        "data_quality_flag",
        "cap_exceeded",
        # Fix 3 (PM-resolved): held targeting plays under ABSTAIN_SOFT.
        "targeting_held_under_abstain",
        # Sprint 5 Ticket S5-T2 (resolves KI-20): supplements
        # ``first_to_second_purchase`` honest abstain.
        "supplement_cadence_outside_window",
        # Sprint 7.5 Ticket T3: priors-validation refusal routing.
        # Surfaces in Considered only when
        # ``ENGINE_V2_PRIORS_VALIDATION=true`` and the play's base_rate
        # prior carries an unvalidated ``validation_status``.
        "prior_unvalidated",
        # Sprint 6.5 Ticket T4 (R1): multi-window evidence disagreement.
        # Surfaces in Considered only when
        # ``ENGINE_V2_STORE_PROFILE=true`` and the card's typed
        # ``measurement.window_corroboration`` is ``CONTRADICTED``.
        "window_disagreement",
        # Sprint 10 Ticket T3: predictive-layer ML-fit gate dormant
        # codes. Schema-additive within ``event_version=1``; no emitter
        # wired at S10 close (S13 consumes them). Distinct from the
        # run-level ``cold_start_insufficient_data``.
        "model_fit_insufficient_data",
        "model_fit_refused",
    }
    actual = {rc.value for rc in ReasonCode}
    assert expected == actual


def test_all_data_quality_flags_declared():
    expected = {
        "bfcm_overlap",
        "post_promo_window",
        "refund_storm",
        "test_order_anomaly",
        "insufficient_clean_history",
        # Sprint 1 Ticket B-7 (post-6B restructured plan): vertical
        # hard-refuse flag. Reuses the existing ``data_quality_flags``
        # slot; the EngineRun field itself is unchanged. Set by
        # ``src.vertical_guard`` at engine entry when ``vertical_mode``
        # is outside ``{beauty, supplements, mixed}``.
        "vertical_not_supported",
        # Sprint 5 Ticket S5-T3 (resolves KI-22): advisory flag set on
        # supplements (or any vertical) when the median customer-level
        # reorder gap exceeds 0.8 * the active primary window. Additive
        # within the Sprint 2 ``event_version=1`` freeze (additive enum
        # values on ``data_quality_flags`` are the documented carve-out).
        "metric_incoherent_for_cadence",
    }
    actual = {f.value for f in DataQualityFlag}
    assert expected == actual


def test_evidence_class_targeting_allows_null_measurement():
    pc = PlayCard(
        play_id="subscription_nudge",
        evidence_class=EvidenceClass.TARGETING,
        measurement=None,
    )
    payload = pc.__class__(**{**pc.__dict__})
    # round-trip via EngineRun
    er = EngineRun(recommendations=[pc])
    er2 = EngineRun.from_dict(er.to_dict())
    assert er2.recommendations[0].evidence_class == EvidenceClass.TARGETING
    assert er2.recommendations[0].measurement is None


# ---------------------------------------------------------------------------
# Phase 6A Ticket A2: ``would_be_measured_by`` additive PlayCard field.
# Detailed coverage lives in ``tests/test_would_be_measured_by_enum.py``;
# the cases below extend the canonical round-trip suite so the schema
# contract is pinned at the same level as the rest of PlayCard.
# ---------------------------------------------------------------------------


def test_play_card_would_be_measured_by_defaults_to_none_in_round_trip():
    er = EngineRun(recommendations=[PlayCard(play_id="x")])
    payload = er.to_dict()
    assert payload["recommendations"][0]["would_be_measured_by"] is None
    er2 = EngineRun.from_dict(payload)
    assert er2.recommendations[0].would_be_measured_by is None


@pytest.mark.parametrize("member", list(WouldBeMeasuredBy))
def test_play_card_would_be_measured_by_round_trips_each_member(member):
    pc = PlayCard(
        play_id="bestseller_amplify",
        evidence_class=EvidenceClass.TARGETING,
        would_be_measured_by=member,
    )
    er = EngineRun(recommendations=[pc])
    payload = er.to_dict()
    raw = json.dumps(payload)
    payload2 = json.loads(raw)
    er2 = EngineRun.from_dict(payload2)
    assert er2.recommendations[0].would_be_measured_by == member


def test_would_be_measured_by_enum_values_are_uppercase_snake():
    """The enum string values match the locked Phase 6A spec.

    Sprint 6 Ticket T1: ``LAPSED_REACTIVATION_IN_30D`` added for the
    winback_dormant_cohort Tier-B builder (additive enum value within
    ``event_version=1``).
    Sprint 6 Ticket T3: ``REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW``
    added for the replenishment_due Tier-B builder (additive enum
    value within ``event_version=1``).
    Sprint 7 priors-wiring (2026-05-20):
    ``DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D`` and
    ``AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D`` added alongside the
    priors.yaml dict-form metadata blocks for the new
    ``discount_dependency_hygiene`` and ``aov_lift_via_threshold_bundle``
    play_ids (additive within ``event_version=1`` per A2 precedent).
    Sprint 7 Ticket T2 (2026-05-20):
    ``FIRST_TO_SECOND_PURCHASE_IN_30D`` added for the
    ``cohort_journey_first_to_second`` Tier-B builder consuming the
    S7.5-T2 validated_external wildcard prior (additive within
    ``event_version=1``).
    """
    expected = {
        "INCREMENTAL_ORDERS_IN_14D",
        "EMAIL_ATTRIBUTED_REVENUE_IN_7D",
        "REPEAT_PURCHASE_IN_30D",
        "LAPSED_REACTIVATION_IN_30D",
        "REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW",
        "DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D",
        "AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D",
        "FIRST_TO_SECOND_PURCHASE_IN_30D",
    }
    actual = {m.value for m in WouldBeMeasuredBy}
    assert expected == actual
