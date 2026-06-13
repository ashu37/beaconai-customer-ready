"""S13.6-T6 tests — MechanismIntent typed atom (DS §(d) + Option C).

Coverage per the T6 dispatch brief:

1.  ``MechanismType`` closed enum has exactly the 10 DS-locked members
    (DS §(d) verbatim, audit-locked).
2.  ``MechanismIntent`` dataclass shape: ``type: MechanismType`` +
    ``parameters: Dict[str, Any]`` (default empty dict).
3.  ``PlayCard.mechanism_intent`` annotation is
    ``Optional[MechanismIntent]`` (new additive field at T6).
4.  ``RejectedPlay.mechanism`` annotation is
    ``Optional[MechanismIntent]`` (RETYPED from ``Optional[str]`` —
    completion of T1a prose-strip discipline).
5.  ``_build_mechanism_intent`` maps the 9 audit-locked play_ids to
    typed atoms; unmapped play_ids return ``None`` (strict, do not
    invent).
6.  Tier-B coverage: the 4 Tier-B types + ``LOOKALIKE_HIGH_VALUE_PROSPECT``
    accept ``parameters={}`` per DS §(d) acceptance.
7.  Emitted JSON shape: ``mechanism_intent`` / ``mechanism`` serialize
    as ``{"type": "...", "parameters": {...}}``.
8.  Strict deserialization (T3/T4 precedent): legacy ``mechanism:
    "<prose str>"`` shape returns ``None`` (NOT silently re-parsed).
9.  Re-export sanity: ``from src.engine_run import MechanismType,
    MechanismIntent`` works.
10. AST sweep: no remaining ``mechanism="<literal str>"`` construction
    of :class:`RejectedPlay` in producer modules under ``src/``.

Per founder lock-in #4 (2026-05-30): "Engine ships structured atoms
only; narration agents render copy."
"""
from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any, Dict, Optional, get_args, get_origin, get_type_hints

import pytest

import src.engine_run as engine_run_mod
from src.engine_run import (
    MechanismIntent,
    MechanismType,
    PlayCard,
    RejectedPlay,
    ReasonCode,
    _from_dict_mechanism_intent,
    _from_dict_play_card,
    _from_dict_rejected,
)


# ---------------------------------------------------------------------------
# (1) Closed-enum 10-member DS §(d) audit lock.
# ---------------------------------------------------------------------------

EXPECTED_MECHANISM_TYPE_MEMBERS = {
    "WINBACK_REACTIVATION_EMAIL",
    "FIRST_TO_SECOND_NUDGE",
    "THRESHOLD_BUNDLE_OFFER",
    "DISCOUNT_DEPENDENCY_HYGIENE",
    "REPLENISHMENT_REMINDER",
    "BESTSELLER_AMPLIFY",
    "CATEGORY_EXPANSION",
    "SUBSCRIPTION_NUDGE",
    "ROUTINE_BUILDER",
    "LOOKALIKE_HIGH_VALUE_PROSPECT",
}


def test_mechanism_type_has_exactly_ten_ds_locked_members():
    actual = {m.name for m in MechanismType}
    assert actual == EXPECTED_MECHANISM_TYPE_MEMBERS
    # Member string values equal member names (UPPER_SNAKE), matching
    # the WouldBeMeasuredBy convention.
    for m in MechanismType:
        assert m.value == m.name


def test_mechanism_type_rejects_freetext():
    with pytest.raises(ValueError):
        MechanismType("not_a_member")


# ---------------------------------------------------------------------------
# (2) MechanismIntent dataclass shape.
# ---------------------------------------------------------------------------


def test_mechanism_intent_dataclass_shape():
    field_map = {f.name: f for f in fields(MechanismIntent)}
    assert set(field_map.keys()) == {"type", "parameters"}
    hints = get_type_hints(MechanismIntent)
    assert hints["type"] is MechanismType
    # parameters: Dict[str, Any]
    assert get_origin(hints["parameters"]) is dict
    key_t, val_t = get_args(hints["parameters"])
    assert key_t is str
    assert val_t is Any


def test_mechanism_intent_parameters_defaults_to_empty_dict():
    mi = MechanismIntent(type=MechanismType.BESTSELLER_AMPLIFY)
    assert mi.parameters == {}
    # default_factory means each instance gets a fresh dict (no shared mutable).
    mi.parameters["x"] = 1
    mi2 = MechanismIntent(type=MechanismType.CATEGORY_EXPANSION)
    assert mi2.parameters == {}


# ---------------------------------------------------------------------------
# (3) PlayCard.mechanism_intent + (4) RejectedPlay.mechanism types.
# ---------------------------------------------------------------------------


def test_play_card_has_mechanism_intent_field_optional_mechanism_intent():
    hints = get_type_hints(PlayCard)
    assert "mechanism_intent" in hints
    ann = hints["mechanism_intent"]
    args = get_args(ann)
    # Optional[MechanismIntent] == Union[MechanismIntent, None]
    assert MechanismIntent in args
    assert type(None) in args


def test_rejected_play_mechanism_retyped_to_optional_mechanism_intent():
    hints = get_type_hints(RejectedPlay)
    assert "mechanism" in hints
    ann = hints["mechanism"]
    args = get_args(ann)
    assert MechanismIntent in args
    assert type(None) in args
    # Crucially: ``str`` is NO LONGER part of the annotation (T6 retype).
    assert str not in args


# ---------------------------------------------------------------------------
# (5) Producer helper coverage.
# ---------------------------------------------------------------------------


def test_build_mechanism_intent_maps_nine_audit_locked_play_ids():
    from src.decide import _build_mechanism_intent

    expected = {
        "winback_dormant_cohort": MechanismType.WINBACK_REACTIVATION_EMAIL,
        "first_to_second_purchase": MechanismType.FIRST_TO_SECOND_NUDGE,
        "cohort_journey_first_to_second": MechanismType.FIRST_TO_SECOND_NUDGE,
        "aov_lift_via_threshold_bundle": MechanismType.THRESHOLD_BUNDLE_OFFER,
        "discount_dependency_hygiene": MechanismType.DISCOUNT_DEPENDENCY_HYGIENE,
        "replenishment_due": MechanismType.REPLENISHMENT_REMINDER,
        "bestseller_amplify": MechanismType.BESTSELLER_AMPLIFY,
        "category_expansion": MechanismType.CATEGORY_EXPANSION,
        "subscription_nudge": MechanismType.SUBSCRIPTION_NUDGE,
        "routine_builder": MechanismType.ROUTINE_BUILDER,
    }
    # 10 entries covering the 9 mapped play_ids (FIRST_TO_SECOND_NUDGE
    # has the two play_id aliases: legacy + cohort_journey).
    for pid, expected_type in expected.items():
        mi = _build_mechanism_intent(pid)
        assert mi is not None, f"play_id {pid!r} should map to a MechanismIntent"
        assert mi.type is expected_type
        assert isinstance(mi.parameters, dict)


def test_build_mechanism_intent_returns_none_for_unmapped_play_ids():
    from src.decide import _build_mechanism_intent

    assert _build_mechanism_intent("definitely_not_a_real_play") is None
    assert _build_mechanism_intent("") is None
    assert _build_mechanism_intent(None) is None


def test_build_mechanism_intent_five_spec_types_carry_non_empty_parameters():
    """DS §(d): the 5 spec'd types carry per-type parameter knobs."""
    from src.decide import _build_mechanism_intent

    spec_play_ids = {
        "winback_dormant_cohort",
        "cohort_journey_first_to_second",
        "aov_lift_via_threshold_bundle",
        "discount_dependency_hygiene",
        "replenishment_due",
    }
    for pid in spec_play_ids:
        mi = _build_mechanism_intent(pid)
        assert mi is not None
        assert mi.parameters, (
            f"spec'd type {mi.type.name} for play_id {pid!r} must carry "
            f"DS §(d) parameter dict; got empty"
        )


# ---------------------------------------------------------------------------
# (6) Tier-B parameters={} acceptance per DS §(d).
# ---------------------------------------------------------------------------


def test_tier_b_types_accept_empty_parameters():
    from src.decide import _build_mechanism_intent

    tier_b_play_ids = {
        "bestseller_amplify",
        "category_expansion",
        "subscription_nudge",
        "routine_builder",
    }
    for pid in tier_b_play_ids:
        mi = _build_mechanism_intent(pid)
        assert mi is not None
        assert mi.parameters == {}, (
            f"Tier-B type {mi.type.name} should carry empty parameters per "
            f"DS §(d) acceptance; got {mi.parameters!r}"
        )


def test_lookalike_member_constructs_with_empty_parameters():
    """LOOKALIKE_HIGH_VALUE_PROSPECT is the 10th DS-locked member.

    No play_id maps to it today (the lookalike Tier-D builder is
    out-of-scope at T6); the member exists in the enum so future
    producers can construct it with ``parameters={}`` per DS §(d).
    """
    mi = MechanismIntent(type=MechanismType.LOOKALIKE_HIGH_VALUE_PROSPECT)
    assert mi.parameters == {}


# ---------------------------------------------------------------------------
# (7) JSON serialization shape via asdict.
# ---------------------------------------------------------------------------


def test_mechanism_intent_json_shape_via_asdict():
    mi = MechanismIntent(
        type=MechanismType.WINBACK_REACTIVATION_EMAIL,
        parameters={"dormancy_window_days": 21, "measurement_window_days": 30},
    )
    out = asdict(mi)
    # The Enum subclass (str, Enum) serializes as the string value
    # under asdict via the standard Enum value coercion in EngineRun's
    # to_dict path; asdict itself leaves it as the Enum instance.
    assert out["type"] in (
        MechanismType.WINBACK_REACTIVATION_EMAIL,
        "WINBACK_REACTIVATION_EMAIL",
    )
    assert out["parameters"] == {
        "dormancy_window_days": 21,
        "measurement_window_days": 30,
    }
    # And it serializes through json (because MechanismType is a str
    # subclass — Enum value is the string).
    blob = json.dumps(out, default=str)
    parsed = json.loads(blob)
    assert parsed["type"] == "WINBACK_REACTIVATION_EMAIL"
    assert parsed["parameters"]["dormancy_window_days"] == 21


def test_play_card_serializes_mechanism_intent_as_typed_object():
    card = PlayCard(
        play_id="winback_dormant_cohort",
        mechanism_intent=MechanismIntent(
            type=MechanismType.WINBACK_REACTIVATION_EMAIL,
            parameters={"dormancy_window_days": 21},
        ),
    )
    out = asdict(card)
    assert isinstance(out["mechanism_intent"], dict)
    # Enum value round-trip via json.
    blob = json.dumps(out, default=lambda x: x.value if hasattr(x, "value") else str(x))
    parsed = json.loads(blob)
    assert parsed["mechanism_intent"]["type"] == "WINBACK_REACTIVATION_EMAIL"
    assert parsed["mechanism_intent"]["parameters"]["dormancy_window_days"] == 21


def test_rejected_play_serializes_mechanism_as_typed_object():
    rej = RejectedPlay(
        play_id="discount_dependency_hygiene",
        reason_code=ReasonCode.PRIOR_UNVALIDATED,
        mechanism=MechanismIntent(
            type=MechanismType.DISCOUNT_DEPENDENCY_HYGIENE,
            parameters={"suppression_window_days": 14},
        ),
    )
    out = asdict(rej)
    assert isinstance(out["mechanism"], dict)
    assert out["mechanism"]["parameters"] == {"suppression_window_days": 14}


# ---------------------------------------------------------------------------
# (8) Strict deserialization (T3/T4 precedent).
# ---------------------------------------------------------------------------


def test_legacy_str_mechanism_round_trips_to_none_strict():
    """Pre-T6 ``RejectedPlay.mechanism: <prose str>`` shape -> ``None``.

    Strict cutover per T3/T4 precedent: legacy str shape is NOT
    silently re-parsed into a MechanismIntent.
    """
    legacy = {
        "play_id": "winback_dormant_cohort",
        "reason_code": ReasonCode.PRIOR_UNVALIDATED.value,
        "mechanism": "Email the dormant cohort with a winback offer.",
    }
    rej = _from_dict_rejected(legacy)
    assert rej.mechanism is None


def test_legacy_play_card_without_mechanism_intent_round_trips_to_none():
    """Pre-T6 PlayCard snapshots have no ``mechanism_intent`` key."""
    legacy = {
        "play_id": "winback_dormant_cohort",
        "evidence_class": "directional",
    }
    card = _from_dict_play_card(legacy)
    assert card.mechanism_intent is None


def test_mechanism_intent_round_trips_via_dict():
    payload = {
        "type": "REPLENISHMENT_REMINDER",
        "parameters": {"measurement_window": "next_cadence_window"},
    }
    mi = _from_dict_mechanism_intent(payload)
    assert mi is not None
    assert mi.type is MechanismType.REPLENISHMENT_REMINDER
    assert mi.parameters == {"measurement_window": "next_cadence_window"}


def test_mechanism_intent_deserialization_rejects_unknown_type():
    """Closed-enum lock: unknown ``type`` raises via the constructor."""
    payload = {"type": "NOT_A_MEMBER", "parameters": {}}
    with pytest.raises(ValueError):
        _from_dict_mechanism_intent(payload)


def test_mechanism_intent_deserialization_handles_missing_parameters():
    payload = {"type": "BESTSELLER_AMPLIFY"}
    mi = _from_dict_mechanism_intent(payload)
    assert mi is not None
    assert mi.parameters == {}


def test_mechanism_intent_deserialization_handles_none_and_non_dict():
    assert _from_dict_mechanism_intent(None) is None
    assert _from_dict_mechanism_intent({}) is None
    assert _from_dict_mechanism_intent("legacy prose string") is None
    assert _from_dict_mechanism_intent(123) is None


# ---------------------------------------------------------------------------
# (9) Re-export sanity.
# ---------------------------------------------------------------------------


def test_mechanism_type_and_intent_are_exported_in_all():
    assert "MechanismType" in engine_run_mod.__all__
    assert "MechanismIntent" in engine_run_mod.__all__


# ---------------------------------------------------------------------------
# (10) AST sweep: no remaining ``mechanism="<literal str>"`` construction
#      of RejectedPlay in producer modules.
# ---------------------------------------------------------------------------


SRC_DIR = Path(__file__).resolve().parent.parent / "src"


def _iter_src_files():
    for p in SRC_DIR.rglob("*.py"):
        # Skip the dataclass dataclass-definition file itself (the
        # ``mechanism: Optional[MechanismIntent] = None`` annotation
        # there is a field default, not a construction site).
        yield p


def test_ast_sweep_no_str_literal_mechanism_kwarg_on_rejected_play():
    """No producer constructs ``RejectedPlay(mechanism="<literal str>")``.

    The 4 swapped sites in src/decide.py now pass the result of
    ``_build_mechanism_intent`` (which is ``Optional[MechanismIntent]``).
    """
    offenders = []
    for path in _iter_src_files():
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name != "RejectedPlay":
                continue
            for kw in node.keywords:
                if kw.arg == "mechanism" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    offenders.append((str(path), node.lineno, kw.value.value))
    assert offenders == [], (
        "Found RejectedPlay(mechanism=<str literal>) construction sites; "
        "T6 requires the typed MechanismIntent atom via "
        "_build_mechanism_intent:\n" + "\n".join(map(str, offenders))
    )


def test_ast_sweep_no_str_literal_mechanism_intent_kwarg_on_play_card():
    """No producer constructs ``PlayCard(mechanism_intent="<literal str>")``."""
    offenders = []
    for path in _iter_src_files():
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name != "PlayCard":
                continue
            for kw in node.keywords:
                if kw.arg == "mechanism_intent" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    offenders.append((str(path), node.lineno))
    assert offenders == []


# ---------------------------------------------------------------------------
# (11) DS Revision 2026-06-01 — DS §(d) verbatim parameters key-set tests.
#
# The existing (#5) "spec'd-types-non-empty parameters" assertion in
# ``test_build_mechanism_intent_five_spec_types_carry_non_empty_parameters``
# passes today on wrong-key dicts because dicts with mismatched keys are
# still non-empty — DS Q5 caught this and required per-type verbatim key
# sets be asserted explicitly. These 5 tests close the regression hole.
#
# Per DS revision posture: values may be ``None`` (with ``# TODO(S14)``
# markers in the helper source) where the decide-seam does not have
# a source for the §(d) knob today; the test asserts the KEY SET, not
# the values, so honest None+TODO is compliant.
# ---------------------------------------------------------------------------


def test_winback_reactivation_email_parameters_match_ds_d_spec():
    from src.decide import _build_mechanism_intent

    mi = _build_mechanism_intent("winback_dormant_cohort")
    assert mi is not None
    assert mi.type is MechanismType.WINBACK_REACTIVATION_EMAIL
    assert set(mi.parameters.keys()) == {
        "dormancy_window_days",
        "offer_type",
        "measurement_window_days",
    }


def test_first_to_second_nudge_parameters_match_ds_d_spec():
    from src.decide import _build_mechanism_intent

    mi = _build_mechanism_intent("cohort_journey_first_to_second")
    assert mi is not None
    assert mi.type is MechanismType.FIRST_TO_SECOND_NUDGE
    assert set(mi.parameters.keys()) == {
        "days_since_first_order_window",
        "measurement_window_days",
    }
    # The day window is a 2-int pair (DS §(d) typing) sourced from the
    # cohort_journey_first_to_second builder's 30 <= days_since <= 90
    # filter (audience_builders.py L716, DS-locked 2026-05-19).
    win = mi.parameters["days_since_first_order_window"]
    assert isinstance(win, list)
    assert len(win) == 2
    assert all(isinstance(x, int) for x in win)


def test_threshold_bundle_offer_parameters_match_ds_d_spec():
    from src.decide import _build_mechanism_intent

    mi = _build_mechanism_intent("aov_lift_via_threshold_bundle")
    assert mi is not None
    assert mi.type is MechanismType.THRESHOLD_BUNDLE_OFFER
    assert set(mi.parameters.keys()) == {
        "threshold_aov",
        "current_median_aov",
    }


def test_discount_dependency_hygiene_parameters_match_ds_d_spec():
    from src.decide import _build_mechanism_intent

    mi = _build_mechanism_intent("discount_dependency_hygiene")
    assert mi is not None
    assert mi.type is MechanismType.DISCOUNT_DEPENDENCY_HYGIENE
    assert set(mi.parameters.keys()) == {
        "current_discount_share",
        "target_discount_share",
    }


def test_replenishment_reminder_parameters_match_ds_d_spec():
    from src.decide import _build_mechanism_intent

    mi = _build_mechanism_intent("replenishment_due")
    assert mi is not None
    assert mi.type is MechanismType.REPLENISHMENT_REMINDER
    assert set(mi.parameters.keys()) == {
        "replenishment_window_days",
        "sku_class",
    }
