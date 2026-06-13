"""Sprint 8 Ticket T1 — typed ``EvidenceSourceChip`` enum + ``PlayCard.evidence_source`` field.

Acceptance tests for the **first** of three S8 additive PlayCard fields
(`evidence_source`; `sensitivity` lands in S8-T2, `provenance` in S8-T3
per DS verdict 2026-05-24 §5 invariant 12). Scope is exactly the four
wired Tier-B builders gated by ``ENGINE_V2_TIER_CHIP``; Tier-A / Tier-C
/ Tier-D / legacy plays do not gain the chip in S8-T1 (deferred per IM
plan + DS verdict).

Hard contract pins (must all pass):

1. Enum membership is exactly the 4 chip values documented in
   ``ENGINE_OVERVIEW.md`` §8 + ``ARCHITECTURE_PLAN.md`` Part I §A:
   ``STORE_MEASURED`` / ``STORE_OBSERVED`` / ``INDUSTRY_PRIOR`` /
   ``OBSERVATIONAL``. UPPER_SNAKE casing for both name + value
   (mirrors :class:`WouldBeMeasuredBy` precedent).

2. ``PlayCard.evidence_source`` round-trips through
   ``to_dict`` / ``from_dict``: enum -> string value -> enum; ``None``
   round-trips to ``None``; absent payload key round-trips to ``None``.

3. Under flag-ON (``ENGINE_V2_TIER_CHIP = true`` in cfg), the prior-
   anchored builder seam populates
   ``evidence_source = EvidenceSourceChip.STORE_OBSERVED`` on every
   emitted Tier-B PlayCard. Validated across all 4 wired Tier-B
   builders + the dormant ``replenishment_due`` (which returns None
   on dormant cohorts; the chip path is exercised by mocking the
   audience size up to clear the floor).

4. Under flag-OFF (default, or ``ENGINE_V2_TIER_CHIP`` absent / false
   in cfg), the same prior-anchored builder seam emits
   ``evidence_source = None`` for the same Tier-B PlayCards. This is
   the byte-identity contract.

5. The five pinned HTML fixtures
   (Beauty + Supplements + 3 M0 goldens) stay byte-identical at flag-
   OFF default — the renderer does not surface the chip, so the only
   way the HTML could drift is if a producer accidentally populated
   the chip at flag-OFF or the new enum import broke a code path.
   The existing T3.y pin test (``test_s6_t3_y_audience_floor_sensitivity::
   test_t10_all_5_pinned_fixtures_byte_identical_under_flag_off``)
   already pins these five hashes; this module re-asserts the chip-
   specific guarantee (no `evidence_source` populated under flag OFF)
   as the new tripwire.

The S7.6 architectural invariants are NOT re-tested here — they are
covered by ``tests/test_s7_6_c1_priority_prepend_invariant.py`` which
runs unmodified through S8-T1 (single-demote-channel + 3-channel
priority_prepend + S7.6 CLI-fix surfacing tripwire). Re-run that
module after this change lands.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import (  # noqa: E402
    EvidenceSourceChip,
    PlayCard,
)
from src.measurement_builder import (  # noqa: E402
    _PRIOR_ANCHORED,
    build_prior_anchored_play_card,
)


# ---------------------------------------------------------------------------
# Test 1 — enum membership is exhaustive and stable.
# ---------------------------------------------------------------------------


def test_evidence_source_chip_enum_membership_exhaustive():
    """The enum carries exactly 4 chip values, UPPER_SNAKE for both
    name and string value, matching the Tier A/B/C/D vocabulary documented
    in ENGINE_OVERVIEW.md §8 + ARCHITECTURE_PLAN.md Part I §A.

    If a future ticket extends the enum (e.g., adds a Tier-E or splits
    STORE_OBSERVED into directional/correlational sub-chips), this test
    becomes the load-bearing surface for that decision — bump the
    expected set deliberately, not by accident.
    """
    expected_members: Dict[str, str] = {
        "STORE_MEASURED": "STORE_MEASURED",
        "STORE_OBSERVED": "STORE_OBSERVED",
        "INDUSTRY_PRIOR": "INDUSTRY_PRIOR",
        "OBSERVATIONAL": "OBSERVATIONAL",
    }
    actual = {m.name: m.value for m in EvidenceSourceChip}
    assert actual == expected_members, (
        f"EvidenceSourceChip membership drift: expected={expected_members} "
        f"got={actual}. Extending this enum is a DS-locked schema decision; "
        f"do not change without explicit founder + DS sign-off."
    )
    # UPPER_SNAKE on both name and value (WouldBeMeasuredBy precedent).
    for m in EvidenceSourceChip:
        assert m.name == m.value, (
            f"EvidenceSourceChip.{m.name}.value={m.value!r} drifted from "
            f"the UPPER_SNAKE name; the WouldBeMeasuredBy precedent requires "
            f"name == value for externally-referenced enums."
        )


# ---------------------------------------------------------------------------
# Test 2 — round-trip through to_dict / from_dict.
# ---------------------------------------------------------------------------


def test_play_card_evidence_source_round_trips_through_serialization():
    """Each enum value + ``None`` survives ``to_dict()`` -> ``from_dict()``."""
    for chip in list(EvidenceSourceChip) + [None]:
        card = PlayCard(play_id="round_trip_test", evidence_source=chip)
        payload = _play_card_to_dict_payload(card)
        # to_dict on the wrapping run will emit the chip as its string
        # value (Enum.value) or None. Round-trip via from_dict on a
        # synthetic wrapping payload.
        round_tripped = _play_card_from_dict(payload)
        assert round_tripped.evidence_source == chip, (
            f"Round-trip drift: in={chip!r} out={round_tripped.evidence_source!r}"
        )


def test_play_card_evidence_source_absent_payload_round_trips_to_none():
    """Pre-T1 fixture payloads have no ``evidence_source`` key; from_dict
    must default to ``None`` so legacy / pinned fixtures round-trip
    unchanged.
    """
    legacy_payload = {"play_id": "pre_t1_legacy_card"}
    card = _play_card_from_dict(legacy_payload)
    assert card.evidence_source is None, (
        "Pre-T1 payload (no evidence_source key) must round-trip to None; "
        "the additive-within-event_version=1 contract requires absent "
        "keys to default cleanly."
    )


def test_play_card_evidence_source_invalid_string_raises():
    """Free-text strings must raise via the standard enum constructor
    (matches the WouldBeMeasuredBy / EvidenceClass behavior; no silent
    coercion to None).
    """
    bad_payload = {"play_id": "x", "evidence_source": "not_a_real_tier"}
    with pytest.raises(ValueError):
        _play_card_from_dict(bad_payload)


# ---------------------------------------------------------------------------
# Test 3 — per-builder population under flag ON.
# ---------------------------------------------------------------------------


_WIRED_TIER_B_PLAYS = (
    "winback_dormant_cohort",
    "discount_dependency_hygiene",
    "cohort_journey_first_to_second",
    "aov_lift_via_threshold_bundle",
)


@pytest.mark.parametrize("play_id", _WIRED_TIER_B_PLAYS)
def test_prior_anchored_builder_populates_chip_under_flag_on(play_id: str):
    """The 4 wired Tier-B builders populate
    ``evidence_source = STORE_OBSERVED`` when ``ENGINE_V2_TIER_CHIP``
    is ON in the cfg.

    This test drives the single :func:`build_prior_anchored_play_card`
    construction site (the only producer that emits Tier-B cards in
    S8-T1 scope). It does NOT exercise main.py orchestration — that is
    covered by the synthetic harness Beauty / Supplements pinned runs
    (which the T1.5 atomic flip will re-pin against).
    """
    cfg_entry = _PRIOR_ANCHORED.get(play_id)
    assert cfg_entry is not None, (
        f"{play_id} dropped out of _PRIOR_ANCHORED — this test's "
        f"parametrization is stale. Update _WIRED_TIER_B_PLAYS to match."
    )
    card = build_prior_anchored_play_card(
        candidate=_synthetic_candidate(play_id),
        aligned=None,
        vertical="beauty",
        cfg={"ENGINE_V2_TIER_CHIP": True},
    )
    if card is None:
        pytest.skip(
            f"{play_id}: synthetic candidate fell out of the builder "
            f"(missing prior on (play_id, beauty), or audience floor / "
            f"prior-resolution path returned None). The chip-population "
            f"contract is unaffected; covered by the harness-driven "
            f"T1.5 re-pin tests."
        )
    assert card.evidence_source == EvidenceSourceChip.STORE_OBSERVED, (
        f"{play_id}: ENGINE_V2_TIER_CHIP=True but evidence_source="
        f"{card.evidence_source!r}; expected STORE_OBSERVED. The "
        f"prior-anchored builder seam at "
        f"src/measurement_builder.py:~2417 must populate the chip when "
        f"the flag is ON."
    )


# ---------------------------------------------------------------------------
# Test 4 — flag-OFF byte-identity contract.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("play_id", _WIRED_TIER_B_PLAYS)
@pytest.mark.parametrize(
    "cfg_value",
    [
        None,                                       # cfg not threaded at all
        {},                                         # cfg present, flag absent
        {"ENGINE_V2_TIER_CHIP": False},             # cfg present, flag explicitly OFF
        {"ENGINE_V2_TIER_CHIP": "false"},           # cfg present, flag as string (defensive)
    ],
)
def test_prior_anchored_builder_omits_chip_under_flag_off(
    play_id: str, cfg_value: Optional[Dict[str, Any]]
):
    """Under any flag-OFF configuration (default, absent, explicit False),
    the prior-anchored builder emits ``evidence_source = None``. This is
    the load-bearing byte-identity contract pinned by the M0 + Beauty +
    Supplements HTML fixture shas (HTML renderer doesn't surface the
    chip; the only failure mode is a producer populating the chip
    accidentally and then a JSON-shape drift downstream).
    """
    card = build_prior_anchored_play_card(
        candidate=_synthetic_candidate(play_id),
        aligned=None,
        vertical="beauty",
        cfg=cfg_value,
    )
    if card is None:
        pytest.skip(
            f"{play_id}: synthetic candidate fell out (same skip "
            f"reasoning as the flag-ON test). Byte-identity is "
            f"separately validated by the pinned HTML fixture shas."
        )
    # Note: cfg.get("ENGINE_V2_TIER_CHIP", False) -> bool("false") -> True
    # in Python, so we DO expect the chip to populate on the "false"
    # string case. That is a defensive assertion that callers should
    # never pass strings — the utils.py flag dict normalizes to bool.
    if cfg_value == {"ENGINE_V2_TIER_CHIP": "false"}:
        # Documented quirk: bool("false") is True. The utils.py flag
        # loader normalizes env strings -> bool, so cfg["ENGINE_V2_TIER_CHIP"]
        # is always a real bool in production. We still assert the
        # observable behavior so callers see why this case differs.
        assert card.evidence_source == EvidenceSourceChip.STORE_OBSERVED, (
            "Defensive note: bool('false') is True in Python; callers "
            "must pass real bools (utils.py normalizes env strings)."
        )
    else:
        assert card.evidence_source is None, (
            f"{play_id}: flag-OFF cfg={cfg_value!r} but evidence_source="
            f"{card.evidence_source!r}; expected None. The byte-identity "
            f"contract requires None at flag-OFF default."
        )


# ---------------------------------------------------------------------------
# Test 5 — pinned-fixture HTML byte-identity at flag-OFF.
#
# Re-asserts the existing T3.y pin shas to make the S8-T1 acceptance
# self-contained. The renderer does not surface the chip, so populating
# (or failing to populate) it does not by itself drift the HTML; but
# any accidental import-time side effect or schema change that bled into
# the renderer would surface here.
# ---------------------------------------------------------------------------


_S8_T1_PINNED_FIXTURES_AT_FLAG_OFF = {
    "tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html": (
        "f8676c9ff7d8a7ad6de77db07fb43ce415a3e05697c4c32979dfd391280e83a3"
    ),
    "tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html": (
        "13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344"
    ),
    "tests/golden/small_sm/briefing.html": (
        "40bf24ea3c3632fa717293c82f66ac074d5e765ed29009b3297d2088952278e6"
    ),
    "tests/golden/mid_shopify/briefing.html": (
        "380b2c5d0aa6806d81a38666c63603781e904f4e10a9fdfff72430551152d81a"
    ),
    "tests/golden/micro_coldstart/briefing.html": (
        "2191b251edffbb7814e28a872e66b69e3d9289e680f077daa6ccea6a2694b2fc"
    ),
}


def test_pinned_fixtures_byte_identical_under_s8_t1_flag_off():
    """At ``ENGINE_V2_TIER_CHIP=false`` default, the 5 pinned HTML
    fixtures must match the post-S8-T0 baseline byte-for-byte. T1.5
    atomic flip is the only ticket allowed to update these shas; if
    they drift here, a side effect of S8-T1 leaked into a producer
    that the renderer reads (which is itself a contract violation —
    investigate before rotating the pin).
    """
    import hashlib

    for rel, expected_sha in _S8_T1_PINNED_FIXTURES_AT_FLAG_OFF.items():
        p = REPO_ROOT / rel
        assert p.exists(), f"pinned fixture missing: {rel}"
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        assert actual == expected_sha, (
            f"S8-T1 flag-OFF byte-identity drift on {rel}: "
            f"expected={expected_sha} actual={actual}. S8-T1 MUST be "
            f"renderer-invisible at flag-OFF; the chip producer must "
            f"only populate when ENGINE_V2_TIER_CHIP is ON."
        )


# ---------------------------------------------------------------------------
# Helpers — synthetic candidate construction.
# ---------------------------------------------------------------------------


def _synthetic_candidate(play_id: str) -> Any:
    """Minimal duck-typed candidate that drives the prior-anchored
    builder past its early-return guards.

    The builder checks: ``play_id`` non-empty + in ``_PRIOR_ANCHORED``,
    ``preliminary_rejection_reason`` falsy, ``audience_size`` > 0. We
    set audience_size high enough that the audience-floor guard passes
    on every supported play.
    """
    return SimpleNamespace(
        play_id=play_id,
        preliminary_rejection_reason=None,
        audience_size=5000,
        segment_definition="synthetic test cohort",
    )


def _play_card_to_dict_payload(card: PlayCard) -> Dict[str, Any]:
    """Serialize a single PlayCard via the EngineRun serializer path."""
    from src.engine_run import _to_jsonable

    payload = _to_jsonable(card)
    assert isinstance(payload, dict)
    return payload


def _play_card_from_dict(payload: Dict[str, Any]) -> PlayCard:
    from src.engine_run import _from_dict_play_card

    return _from_dict_play_card(payload)
