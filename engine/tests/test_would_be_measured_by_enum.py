"""Phase 6A Ticket A2: ``WouldBeMeasuredBy`` enum + additive PlayCard field.

This file pins the enum surface, the additive field default, and the
serialization round-trip on every member of the enum. No producer in the
engine populates this field in Ticket A2; A2 is a schema-only contract that
makes the field exist, default to ``None``, and round-trip cleanly.

Hard scope (Ticket A2 ONLY):

- ``WouldBeMeasuredBy`` exists with exactly three members:
  ``INCREMENTAL_ORDERS_IN_14D``, ``EMAIL_ATTRIBUTED_REVENUE_IN_7D``,
  ``REPEAT_PURCHASE_IN_30D``.
- The string value of each member equals the member name.
- Free-text strings raise ``ValueError`` at construction.
- ``PlayCard.would_be_measured_by`` defaults to ``None`` and is optional.
- A PlayCard with each enum value round-trips through
  ``EngineRun.to_dict()`` / ``EngineRun.from_dict()``.
- A PlayCard with no ``would_be_measured_by`` (default ``None``) round-trips.

These tests are red-first: they will fail to import / fail to construct
until the enum + field land in ``src.engine_run``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import (  # noqa: E402
    EngineRun,
    EvidenceClass,
    PlayCard,
    WouldBeMeasuredBy,
)


# ---------------------------------------------------------------------------
# Enum surface
# ---------------------------------------------------------------------------


def test_would_be_measured_by_has_exactly_four_members():
    # Sprint 6 Ticket T1 (2026-05-17): ``LAPSED_REACTIVATION_IN_30D``
    # added for the winback_dormant_cohort Tier-B builder.
    # Sprint 6 Ticket T3 (2026-05-18): ``REPLENISHMENT_DUE_IN_NEXT_CADENCE_WINDOW``
    # added for the replenishment_due Tier-B builder. Additive within
    # ``event_version=1`` per the Sprint 2 freeze carve-out for enum
    # extensions.
    # Sprint 7 priors-wiring (2026-05-20):
    # ``DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D`` and
    # ``AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D`` added alongside the
    # priors.yaml dict-form metadata blocks for the new
    # ``discount_dependency_hygiene`` and ``aov_lift_via_threshold_bundle``
    # play_ids (additive within ``event_version=1``).
    # Sprint 7 Ticket T2 (2026-05-20): ``FIRST_TO_SECOND_PURCHASE_IN_30D``
    # added for the cohort_journey_first_to_second Tier-B builder
    # consuming the S7.5-T2 validated_external wildcard prior.
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
    actual_names = {m.name for m in WouldBeMeasuredBy}
    assert actual_names == expected


def test_would_be_measured_by_string_values_match_names():
    """The locked spec says string value == name (UPPER_SNAKE_CASE).

    This is a deliberate departure from the lowercase convention used by
    other enums in this module (e.g. ``EvidenceClass.MEASURED == "measured"``).
    The contract-final spec uses UPPER_SNAKE_CASE for ``would_be_measured_by``
    enum strings to match how outcome-metric names are referenced elsewhere
    (e.g. priors-metadata YAML in Ticket A3 will use the same UPPER_SNAKE_CASE
    strings).
    """
    for member in WouldBeMeasuredBy:
        assert member.value == member.name


def test_would_be_measured_by_invalid_value_rejected():
    with pytest.raises(ValueError):
        WouldBeMeasuredBy("incremental_orders_in_14d")  # lowercase rejected
    with pytest.raises(ValueError):
        WouldBeMeasuredBy("FOO_BAR")
    with pytest.raises(ValueError):
        WouldBeMeasuredBy("")


def test_would_be_measured_by_is_str_enum():
    """str-Enum mixin so JSON serialization works without explicit coercion."""
    assert issubclass(WouldBeMeasuredBy, str)
    member = WouldBeMeasuredBy.INCREMENTAL_ORDERS_IN_14D
    assert member == "INCREMENTAL_ORDERS_IN_14D"


# ---------------------------------------------------------------------------
# PlayCard field default
# ---------------------------------------------------------------------------


def test_play_card_would_be_measured_by_defaults_to_none():
    pc = PlayCard(play_id="discount_hygiene")
    assert pc.would_be_measured_by is None


def test_play_card_constructor_accepts_optional_field():
    """Existing call sites (no ``would_be_measured_by`` kwarg) keep working."""
    pc = PlayCard(
        play_id="bestseller_amplify",
        evidence_class=EvidenceClass.TARGETING,
    )
    assert pc.would_be_measured_by is None
    # Setting it explicitly to None is also fine.
    pc2 = PlayCard(play_id="x", would_be_measured_by=None)
    assert pc2.would_be_measured_by is None


def test_play_card_constructor_accepts_each_enum_value():
    for member in WouldBeMeasuredBy:
        pc = PlayCard(play_id=f"play_{member.value}", would_be_measured_by=member)
        assert pc.would_be_measured_by is member


# ---------------------------------------------------------------------------
# Serialization round-trip via EngineRun
# ---------------------------------------------------------------------------


def test_default_play_card_omits_or_nulls_field_in_to_dict():
    """``to_dict`` MUST emit the field key with a null value rather than
    omitting it entirely; the existing serialization helper recurses
    through every dataclass attribute, which keeps schema clients
    forward-compatible.
    """
    pc = PlayCard(play_id="x")
    er = EngineRun(recommendations=[pc])
    payload = er.to_dict()
    assert "would_be_measured_by" in payload["recommendations"][0]
    assert payload["recommendations"][0]["would_be_measured_by"] is None


def test_play_card_with_none_round_trips():
    pc = PlayCard(play_id="x")
    er = EngineRun(recommendations=[pc])
    er2 = EngineRun.from_dict(er.to_dict())
    assert er2.recommendations[0].would_be_measured_by is None


@pytest.mark.parametrize("member", list(WouldBeMeasuredBy))
def test_play_card_round_trip_for_each_enum_member(member: WouldBeMeasuredBy):
    pc = PlayCard(
        play_id=f"play_{member.name.lower()}",
        evidence_class=EvidenceClass.TARGETING,
        would_be_measured_by=member,
    )
    er = EngineRun(recommendations=[pc])
    payload = er.to_dict()
    # Serialized form is the enum's string value.
    assert payload["recommendations"][0]["would_be_measured_by"] == member.value

    er2 = EngineRun.from_dict(payload)
    rt_pc = er2.recommendations[0]
    assert rt_pc.would_be_measured_by == member
    assert isinstance(rt_pc.would_be_measured_by, WouldBeMeasuredBy)


def test_omitted_field_round_trips():
    """If a serialized payload lacks ``would_be_measured_by`` entirely
    (e.g. produced by a pre-A2 client), ``from_dict`` must default to
    ``None`` rather than raising.
    """
    pc = PlayCard(play_id="x")
    er = EngineRun(recommendations=[pc])
    payload = er.to_dict()
    # Simulate a legacy client that does not write the field at all.
    payload["recommendations"][0].pop("would_be_measured_by", None)
    er2 = EngineRun.from_dict(payload)
    assert er2.recommendations[0].would_be_measured_by is None


def test_invalid_serialized_value_raises_on_from_dict():
    """A free-text value in the serialized form must fail at load.

    Mirrors the existing behavior for other enum fields (e.g. ``ReasonCode``
    in ``RejectedPlay``): ``_coerce_enum`` raises ``ValueError`` for an
    unrecognized string. This is the forcing function that prevents
    free-text from leaking into the field via a future producer.
    """
    pc = PlayCard(play_id="x")
    er = EngineRun(recommendations=[pc])
    payload = er.to_dict()
    payload["recommendations"][0]["would_be_measured_by"] = "free_text_metric_name"
    with pytest.raises(ValueError):
        EngineRun.from_dict(payload)
