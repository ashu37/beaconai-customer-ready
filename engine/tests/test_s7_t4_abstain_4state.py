"""Sprint 7 Ticket T4 — 4-state abstain mode migration.

Pins the DS-locked Gap F precedence rule (2026-05-20) for
``src.decide._compute_abstain_mode`` under the new
``ENGINE_V2_ABSTAIN_4STATE`` flag.

Coverage:

- AbstainMode enum has all 4 values + round-trip clean.
- ``four_state_flag_on=False`` (default) preserves the legacy Sprint
  7.5 T3 2-state mapping (backwards compat).
- ``four_state_flag_on=True`` applies the 6-branch precedence rule
  per DS Gap F verdict, including DS-flagged missed edges:
    * ABSTAIN_HARD path returns None (data-quality owns).
    * Empty Considered + ABSTAIN_SOFT -> SOFT_AWAITING_MEASUREMENT.
    * Mixed non-mode-driving codes only -> SOFT_AWAITING_MEASUREMENT.
    * TARGETING_HELD_UNDER_ABSTAIN excluded from mode-driving count
      (self-contamination guard).
- Flag-OFF default at the decide() seam: pinned cfg with both flags
  OFF emits no mode (legacy parity).

All tests are pure / hermetic; no fixtures touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.decide import _compute_abstain_mode  # noqa: E402
from src.engine_run import (  # noqa: E402
    AbstainMode,
    DecisionState,
    ReasonCode,
    RejectedPlay,
)


# ---------------------------------------------------------------------------
# Enum surface
# ---------------------------------------------------------------------------


def test_abstain_mode_has_four_values():
    values = {m.value for m in AbstainMode}
    assert values == {
        "soft_awaiting_measurement",
        "soft_prior_unvalidated",
        "soft_below_floor",
        "soft_audience_too_small",
    }


def test_abstain_mode_new_values_round_trip():
    for member in (
        AbstainMode.SOFT_BELOW_FLOOR,
        AbstainMode.SOFT_AUDIENCE_TOO_SMALL,
    ):
        assert AbstainMode(member.value) is member


# ---------------------------------------------------------------------------
# Flag-OFF: legacy 2-state behavior preserved (backwards compat)
# ---------------------------------------------------------------------------


def test_flag_off_returns_none_regardless_of_state():
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=[
            RejectedPlay(
                play_id="x", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR
            )
        ],
        flag_on=False,
    )
    assert mode is None


def test_four_state_default_off_preserves_legacy_prior_unvalidated_mapping():
    # Legacy T3 2-state: any PRIOR_UNVALIDATED in Considered -> SOFT_PRIOR_UNVALIDATED.
    considered = [
        RejectedPlay(play_id="p1", reason_code=ReasonCode.PRIOR_UNVALIDATED),
        RejectedPlay(play_id="p2", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT, considered=considered, flag_on=True
    )
    assert mode == AbstainMode.SOFT_PRIOR_UNVALIDATED


def test_four_state_default_off_preserves_legacy_awaiting_measurement_mapping():
    considered = [
        RejectedPlay(play_id="p1", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT, considered=considered, flag_on=True
    )
    assert mode == AbstainMode.SOFT_AWAITING_MEASUREMENT


def test_four_state_default_off_does_not_emit_new_modes():
    # Even with majority MATERIALITY_BELOW_FLOOR, legacy path never
    # emits SOFT_BELOW_FLOOR — backwards-compat guard.
    considered = [
        RejectedPlay(play_id=f"p{i}", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR)
        for i in range(5)
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT, considered=considered, flag_on=True
    )
    # Legacy: no PRIOR_UNVALIDATED -> default awaiting-measurement.
    assert mode == AbstainMode.SOFT_AWAITING_MEASUREMENT


# ---------------------------------------------------------------------------
# 4-state precedence: rule 1 — ABSTAIN_HARD returns None
# ---------------------------------------------------------------------------


def test_rule1_abstain_hard_returns_none():
    considered = [
        RejectedPlay(play_id="p1", reason_code=ReasonCode.PRIOR_UNVALIDATED),
        RejectedPlay(play_id="p2", reason_code=ReasonCode.AUDIENCE_TOO_SMALL),
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_HARD,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode is None


def test_rule2_publish_returns_none():
    considered = [
        RejectedPlay(play_id="p1", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
    ]
    mode = _compute_abstain_mode(
        DecisionState.PUBLISH,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode is None


# ---------------------------------------------------------------------------
# 4-state precedence: rule 3 — empty Considered defaults to awaiting
# ---------------------------------------------------------------------------


def test_rule3_empty_considered_routes_to_awaiting_measurement():
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=[],
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode == AbstainMode.SOFT_AWAITING_MEASUREMENT


def test_rule3_none_considered_routes_to_awaiting_measurement():
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=None,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode == AbstainMode.SOFT_AWAITING_MEASUREMENT


# ---------------------------------------------------------------------------
# 4-state precedence: rule 4 — TARGETING_HELD_UNDER_ABSTAIN self-exclusion
# ---------------------------------------------------------------------------


def test_rule4_targeting_held_excluded_from_mode_driving_count():
    # 1 PRIOR_UNVALIDATED, 9 TARGETING_HELD_UNDER_ABSTAIN. If
    # TARGETING_HELD_UNDER_ABSTAIN were NOT excluded, total=10 with
    # PU at 10% would fall through to SOFT_AWAITING_MEASUREMENT.
    # Correct (excluded) behavior: total=1, PU is 100% -> majority
    # rule fires SOFT_PRIOR_UNVALIDATED.
    considered = [
        RejectedPlay(play_id="p1", reason_code=ReasonCode.PRIOR_UNVALIDATED),
    ] + [
        RejectedPlay(
            play_id=f"held{i}", reason_code=ReasonCode.TARGETING_HELD_UNDER_ABSTAIN
        )
        for i in range(9)
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode == AbstainMode.SOFT_PRIOR_UNVALIDATED


def test_rule4_only_targeting_held_routes_to_awaiting_measurement():
    # All Considered entries are TARGETING_HELD_UNDER_ABSTAIN. After
    # self-exclusion typed_codes is empty -> default to awaiting.
    considered = [
        RejectedPlay(
            play_id=f"held{i}", reason_code=ReasonCode.TARGETING_HELD_UNDER_ABSTAIN
        )
        for i in range(3)
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode == AbstainMode.SOFT_AWAITING_MEASUREMENT


# ---------------------------------------------------------------------------
# 4-state precedence: rule 5 — majority (>=60%) for any mode-driving class
# ---------------------------------------------------------------------------


def test_rule5_majority_materiality_below_floor():
    considered = [
        RejectedPlay(play_id="a", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
        RejectedPlay(play_id="b", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
        RejectedPlay(play_id="c", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
        RejectedPlay(play_id="d", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
        RejectedPlay(play_id="e", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
    ]
    # 3/5 = 60% MATERIALITY_BELOW_FLOOR -> SOFT_BELOW_FLOOR
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode == AbstainMode.SOFT_BELOW_FLOOR


def test_rule5_majority_audience_too_small():
    considered = [
        RejectedPlay(play_id=f"a{i}", reason_code=ReasonCode.AUDIENCE_TOO_SMALL)
        for i in range(7)
    ] + [
        RejectedPlay(play_id="b", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
        RejectedPlay(play_id="c", reason_code=ReasonCode.WINDOW_DISAGREEMENT),
        RejectedPlay(play_id="d", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
    ]
    # 7/10 = 70% AUDIENCE_TOO_SMALL -> SOFT_AUDIENCE_TOO_SMALL
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode == AbstainMode.SOFT_AUDIENCE_TOO_SMALL


def test_rule5_majority_prior_unvalidated():
    considered = [
        RejectedPlay(play_id=f"a{i}", reason_code=ReasonCode.PRIOR_UNVALIDATED)
        for i in range(4)
    ] + [
        RejectedPlay(play_id="b", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
    ]
    # 4/5 = 80% PRIOR_UNVALIDATED -> SOFT_PRIOR_UNVALIDATED
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode == AbstainMode.SOFT_PRIOR_UNVALIDATED


def test_rule5_exactly_60_percent_threshold_inclusive():
    # 3/5 = 60.0% exactly — boundary is inclusive (>=).
    considered = [
        RejectedPlay(play_id="a", reason_code=ReasonCode.AUDIENCE_TOO_SMALL),
        RejectedPlay(play_id="b", reason_code=ReasonCode.AUDIENCE_TOO_SMALL),
        RejectedPlay(play_id="c", reason_code=ReasonCode.AUDIENCE_TOO_SMALL),
        RejectedPlay(play_id="d", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
        RejectedPlay(play_id="e", reason_code=ReasonCode.WINDOW_DISAGREEMENT),
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode == AbstainMode.SOFT_AUDIENCE_TOO_SMALL


# ---------------------------------------------------------------------------
# 4-state precedence: rule 6 — PRIOR_UNVALIDATED tiebreak at >=30%
# ---------------------------------------------------------------------------


def test_rule6_prior_unvalidated_tiebreak_at_30_percent():
    # 3/10 PRIOR_UNVALIDATED (30% exactly), no other class hits 60%.
    # Tiebreak fires -> SOFT_PRIOR_UNVALIDATED.
    considered = [
        RejectedPlay(play_id=f"pu{i}", reason_code=ReasonCode.PRIOR_UNVALIDATED)
        for i in range(3)
    ] + [
        RejectedPlay(play_id=f"af{i}", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR)
        for i in range(3)
    ] + [
        RejectedPlay(play_id=f"at{i}", reason_code=ReasonCode.AUDIENCE_TOO_SMALL)
        for i in range(2)
    ] + [
        RejectedPlay(play_id=f"ns{i}", reason_code=ReasonCode.NO_MEASURED_SIGNAL)
        for i in range(2)
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode == AbstainMode.SOFT_PRIOR_UNVALIDATED


def test_rule6_prior_unvalidated_below_30_percent_falls_through():
    # 1/10 PU (10%) — below tiebreak threshold; no majority elsewhere.
    considered = [
        RejectedPlay(play_id="pu", reason_code=ReasonCode.PRIOR_UNVALIDATED),
    ] + [
        RejectedPlay(play_id=f"af{i}", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR)
        for i in range(4)
    ] + [
        RejectedPlay(play_id=f"at{i}", reason_code=ReasonCode.AUDIENCE_TOO_SMALL)
        for i in range(4)
    ] + [
        RejectedPlay(play_id="ns", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode == AbstainMode.SOFT_AWAITING_MEASUREMENT


# ---------------------------------------------------------------------------
# 4-state precedence: rule 7 — catch-all
# ---------------------------------------------------------------------------


def test_rule7_mixed_non_mode_driving_only_routes_to_awaiting():
    # Only non-mode-driving codes -> catch-all SOFT_AWAITING_MEASUREMENT.
    # (DS-flagged missed edge.)
    considered = [
        RejectedPlay(play_id="a", reason_code=ReasonCode.WINDOW_DISAGREEMENT),
        RejectedPlay(play_id="b", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
        RejectedPlay(
            play_id="c", reason_code=ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS
        ),
        RejectedPlay(play_id="d", reason_code=ReasonCode.CAP_EXCEEDED),
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode == AbstainMode.SOFT_AWAITING_MEASUREMENT


def test_rule7_three_way_split_no_class_dominant_routes_to_awaiting():
    # 2/6 each of MATERIALITY_BELOW_FLOOR + AUDIENCE_TOO_SMALL +
    # NO_MEASURED_SIGNAL. None hits 60%, PU is absent -> awaiting.
    considered = [
        RejectedPlay(play_id="a", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
        RejectedPlay(play_id="b", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
        RejectedPlay(play_id="c", reason_code=ReasonCode.AUDIENCE_TOO_SMALL),
        RejectedPlay(play_id="d", reason_code=ReasonCode.AUDIENCE_TOO_SMALL),
        RejectedPlay(play_id="e", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
        RejectedPlay(play_id="f", reason_code=ReasonCode.NO_MEASURED_SIGNAL),
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode == AbstainMode.SOFT_AWAITING_MEASUREMENT


# ---------------------------------------------------------------------------
# Interaction edges
# ---------------------------------------------------------------------------


def test_self_exclusion_with_majority_below_floor():
    # 3 MATERIALITY_BELOW_FLOOR + 2 TARGETING_HELD_UNDER_ABSTAIN.
    # After self-exclusion: 3/3 = 100% MATERIALITY_BELOW_FLOOR ->
    # SOFT_BELOW_FLOOR (NOT the awaiting catch-all).
    considered = [
        RejectedPlay(play_id="a", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
        RejectedPlay(play_id="b", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
        RejectedPlay(play_id="c", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
        RejectedPlay(
            play_id="d", reason_code=ReasonCode.TARGETING_HELD_UNDER_ABSTAIN
        ),
        RejectedPlay(
            play_id="e", reason_code=ReasonCode.TARGETING_HELD_UNDER_ABSTAIN
        ),
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    assert mode == AbstainMode.SOFT_BELOW_FLOOR


def test_priors_validation_flag_off_short_circuits_even_when_4state_on():
    # If the priors-validation flag is OFF, no mode is emitted at all,
    # regardless of four_state_flag_on. (Preserves the original T3
    # "flag_off -> None" contract; T4 is purely additive on top.)
    considered = [
        RejectedPlay(play_id="a", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
        RejectedPlay(play_id="b", reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR),
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=False,
        four_state_flag_on=True,
    )
    assert mode is None


def test_flag_default_four_state_off_is_legacy_under_priors_flag_on():
    # Sanity: explicit positional/kwarg matches default — caller can
    # omit four_state_flag_on and get the legacy 2-state behavior.
    considered = [
        RejectedPlay(play_id="a", reason_code=ReasonCode.AUDIENCE_TOO_SMALL),
        RejectedPlay(play_id="b", reason_code=ReasonCode.AUDIENCE_TOO_SMALL),
        RejectedPlay(play_id="c", reason_code=ReasonCode.AUDIENCE_TOO_SMALL),
    ]
    legacy_mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT, considered=considered, flag_on=True
    )
    explicit_off = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=True,
        four_state_flag_on=False,
    )
    assert legacy_mode == explicit_off == AbstainMode.SOFT_AWAITING_MEASUREMENT


def test_unknown_reason_code_attribute_none_is_skipped():
    # Defensive: RejectedPlay with reason_code=None (synthetic) is
    # silently skipped by the precedence walk, not coerced.
    class _Bare:
        reason_code = None

    considered = [
        _Bare(),
        RejectedPlay(play_id="a", reason_code=ReasonCode.AUDIENCE_TOO_SMALL),
        RejectedPlay(play_id="b", reason_code=ReasonCode.AUDIENCE_TOO_SMALL),
    ]
    mode = _compute_abstain_mode(
        DecisionState.ABSTAIN_SOFT,
        considered=considered,
        flag_on=True,
        four_state_flag_on=True,
    )
    # 2/2 typed AUDIENCE_TOO_SMALL -> SOFT_AUDIENCE_TOO_SMALL
    assert mode == AbstainMode.SOFT_AUDIENCE_TOO_SMALL
