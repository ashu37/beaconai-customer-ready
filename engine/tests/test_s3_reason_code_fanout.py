"""S-3 prep — reason-code fan-out (B-2 surface a).

Per implementation plan §2 ticket S-3: extend ``_candidate_reason_code``
in ``src/decide.py`` to emit ``AUDIENCE_TOO_SMALL``, ``COLD_START``,
``INVENTORY_BLOCKED``, ``MATERIALITY_BELOW_FLOOR``, ``DATA_QUALITY``
instead of collapsing all to ``NO_MEASURED_SIGNAL``.

This is **additive only** per Risk #4 in the plan: each new mapping
fires ONLY when the candidate emitted that specific short code; the
default ``NO_MEASURED_SIGNAL`` is retained for everything else. This
test pins the mapping behavior so an accidental future refactor that
collapses the fan-out can't slip through silently.

The substrate event payload work (``recommendation_considered`` event
with the typed reason_code) is wired in S-3 proper, after S-2 lands.
What ships now is the reason-code mapping itself, surfaced through
the existing ``RejectedPlay.reason_code`` field on ``EngineRun``.
"""

from __future__ import annotations

import pytest

from src.decide import (
    _candidate_reason_code,
    _PRELIM_REASON_MAP,
    _S3_FANOUT_REASON_MAP,
)
from src.engine_run import ReasonCode


class _FakeCandidate:
    """Stand-in for an M3 ``Candidate`` with only the fields
    ``_candidate_reason_code`` reads."""

    def __init__(self, prelim: str | None = None):
        self.preliminary_rejection_reason = prelim


# ---------------------------------------------------------------------------
# Pre-existing mappings (regression guard — must not change)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prelim,expected",
    [
        ("audience_zero", ReasonCode.AUDIENCE_TOO_SMALL),
        ("audience_too_small", ReasonCode.AUDIENCE_TOO_SMALL),
        ("below_min_n", ReasonCode.AUDIENCE_TOO_SMALL),
        ("no_builder", ReasonCode.NO_MEASURED_SIGNAL),
        ("builder_error", ReasonCode.NO_MEASURED_SIGNAL),
        ("no_signal", ReasonCode.NO_MEASURED_SIGNAL),
        ("missing_field", ReasonCode.NO_MEASURED_SIGNAL),
        ("no_data", ReasonCode.COLD_START_INSUFFICIENT_DATA),
        ("inventory_blocked", ReasonCode.INVENTORY_BLOCKED),
    ],
)
def test_legacy_mappings_unchanged(prelim, expected):
    """The pre-S-3 reason-code mappings must continue to fire as before.
    Additive-only contract per Risk #4."""

    assert _candidate_reason_code(_FakeCandidate(prelim)) is expected


# ---------------------------------------------------------------------------
# S-3 fan-out additions (the new ones)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prelim,expected",
    [
        ("data_missing", ReasonCode.DATA_QUALITY_FLAG),
        ("data_quality", ReasonCode.DATA_QUALITY_FLAG),
        ("cold_start", ReasonCode.COLD_START_INSUFFICIENT_DATA),
        ("insufficient_history", ReasonCode.COLD_START_INSUFFICIENT_DATA),
        ("materiality_below_floor", ReasonCode.MATERIALITY_BELOW_FLOOR),
        ("below_materiality_floor", ReasonCode.MATERIALITY_BELOW_FLOOR),
    ],
)
def test_s3_fanout_mappings_fire_unconditionally(prelim, expected):
    """Sprint 2 closeout (S-3): the fan-out is now activated
    unconditionally. The previous gating env flag
    ``ENGINE_S3_REASON_FANOUT`` has been removed, and the Beauty
    pinned fixture was re-pinned in the same commit per plan
    §7 Risk #4."""

    assert _candidate_reason_code(_FakeCandidate(prelim)) is expected


def test_default_fallback_unchanged():
    """A candidate with no ``preliminary_rejection_reason`` and no
    registry entry still defaults to ``NO_MEASURED_SIGNAL``. The
    fan-out is additive — the default did not move."""

    assert _candidate_reason_code(_FakeCandidate(None)) is ReasonCode.NO_MEASURED_SIGNAL


def test_unknown_short_code_falls_back_to_no_measured_signal():
    """A short code not in the map (e.g. a future short code that S-3
    fan-out hasn't accounted for yet) falls through to the default,
    NOT to one of the new typed codes. Pins the additive contract."""

    assert (
        _candidate_reason_code(_FakeCandidate("some_unmapped_future_code"))
        is ReasonCode.NO_MEASURED_SIGNAL
    )


def test_fanout_codes_present_across_both_maps():
    """The five fan-out ReasonCodes the plan calls for must each be
    reachable from the union of ``_PRELIM_REASON_MAP`` (always-on
    legacy mappings) and ``_S3_FANOUT_REASON_MAP`` (gated additions).

    Pinning the union prevents a future refactor from silently dropping
    a fan-out target (e.g. removing the only ``data_missing`` mapping
    entry). The split is intentional — the legacy map governs
    flag-OFF behavior; the fan-out map activates with
    ``ENGINE_S3_REASON_FANOUT=1`` once S-2 lands and goldens are
    re-pinned in the S-3 commit.
    """

    values = set(_PRELIM_REASON_MAP.values()) | set(_S3_FANOUT_REASON_MAP.values())
    required = {
        ReasonCode.AUDIENCE_TOO_SMALL,
        ReasonCode.COLD_START_INSUFFICIENT_DATA,
        ReasonCode.INVENTORY_BLOCKED,
        ReasonCode.MATERIALITY_BELOW_FLOOR,
        ReasonCode.DATA_QUALITY_FLAG,
    }
    missing = required - values
    assert missing == set(), (
        f"S-3 fan-out requires these ReasonCodes to be reachable from "
        f"_PRELIM_REASON_MAP ∪ _S3_FANOUT_REASON_MAP, but they are "
        f"missing: {missing}."
    )
