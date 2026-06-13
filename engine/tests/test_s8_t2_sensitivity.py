"""Sprint 8 Ticket T2 — typed ``Sensitivity`` dataclass + ``PlayCard.sensitivity`` field.

Acceptance tests for the **second** of three S8 additive PlayCard fields
(``evidence_source`` landed in S8-T1; ``sensitivity`` lands here;
``provenance`` lands in S8-T3 per DS verdict 2026-05-24 §5 invariant 12).
Scope is exactly the four wired Tier-B builders on the validated,
non-suppressed BLEND path, gated by ``ENGINE_V2_SENSITIVITY``.

Hard contract pins (must all pass):

1. ``Sensitivity`` dataclass + ``PlayCard.sensitivity`` round-trip through
   ``to_dict`` / ``from_dict``: typed scenarios -> dict -> typed scenarios;
   ``None`` round-trips to ``None``; absent payload key round-trips to
   ``None``.

2. :func:`src.sizing.compute_sensitivity` math is correct:
   - observed_n halved scenario shifts the posterior toward the prior
     (re-blend at n/2 with the same pseudo_n).
   - observed_n doubled scenario shifts the posterior toward the
     store-observed value.
   - prior_shifted_down scenario lowers the p50 (re-blend with
     prior_value * 0.75); prior_shifted_up raises it.
   - All scenarios reuse :func:`bayesian_blend` (no parallel sizing math).

3. Under flag-ON (``ENGINE_V2_SENSITIVITY = true`` in cfg), the prior-
   anchored builder seam populates ``PlayCard.sensitivity`` on the four
   wired Tier-B builders **provided** the card carries a validated,
   non-suppressed BLEND revenue range.

4. Under flag-OFF (default, or ``ENGINE_V2_SENSITIVITY`` absent / false
   in cfg), the same builder seam emits ``PlayCard.sensitivity = None``
   for the same Tier-B cards. This is the byte-identity contract.

5. The five pinned HTML fixtures (Beauty + Supplements + 3 M0 goldens)
   stay byte-identical at flag-OFF default — the renderer does not
   surface the block, so the only way the HTML could drift is if a
   producer accidentally populated the block at flag-OFF or the new
   dataclass import broke a code path.

The S7.6 architectural invariants are NOT re-tested here — they are
covered by ``tests/test_s7_6_c1_priority_prepend_invariant.py`` which
runs unmodified through S8-T2. The chip producer (``evidence_source``)
behavior is also unaffected; S8-T1 tests pass unmodified.
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
    PlayCard,
    RevenueRange,
    RevenueRangeSource,
    Sensitivity,
)
from src.measurement_builder import (  # noqa: E402
    _PRIOR_ANCHORED,
    build_prior_anchored_play_card,
)
from src.sizing import bayesian_blend, compute_sensitivity  # noqa: E402


# ---------------------------------------------------------------------------
# Test 1 — round-trip through to_dict / from_dict.
# ---------------------------------------------------------------------------


def _play_card_to_dict_payload(card: PlayCard) -> Dict[str, Any]:
    from src.engine_run import _to_jsonable

    payload = _to_jsonable(card)
    assert isinstance(payload, dict)
    return payload


def _play_card_from_dict(payload: Dict[str, Any]) -> PlayCard:
    from src.engine_run import _from_dict_play_card

    return _from_dict_play_card(payload)


def _make_sensitivity_block() -> Sensitivity:
    rr_low = RevenueRange(
        p10=10.0, p50=20.0, p90=30.0,
        source=RevenueRangeSource.BLEND,
        drivers=[],
        suppressed=False,
    )
    rr_high = RevenueRange(
        p10=40.0, p50=50.0, p90=60.0,
        source=RevenueRangeSource.BLEND,
        drivers=[],
        suppressed=False,
    )
    return Sensitivity(
        scenario_observed_n_halved=rr_low,
        scenario_observed_n_doubled=rr_high,
        scenario_prior_shifted_down=rr_low,
        scenario_prior_shifted_up=rr_high,
        pseudo_n_used=15,
        notes=["round_trip_note"],
    )


def test_play_card_sensitivity_round_trips_through_serialization(monkeypatch):
    """The Sensitivity block (every scenario populated) survives
    to_dict -> from_dict; ``None`` round-trips to ``None``.
    """
    # S13.6-T1a (Option D): ``notes`` debris gated behind
    # INCLUDE_DEBUG_FIELDS=False default. This round-trip test flips it
    # ON to exercise the legacy debug-notes path.
    import src.utils as utils_mod
    monkeypatch.setitem(utils_mod.DEFAULTS, "INCLUDE_DEBUG_FIELDS", True)
    for block in (_make_sensitivity_block(), None):
        card = PlayCard(play_id="round_trip_test", sensitivity=block)
        payload = _play_card_to_dict_payload(card)
        round_tripped = _play_card_from_dict(payload)
        assert round_tripped.sensitivity == block, (
            f"Sensitivity round-trip drift: in={block!r} "
            f"out={round_tripped.sensitivity!r}"
        )


def test_play_card_sensitivity_absent_payload_round_trips_to_none():
    """Pre-T2 fixture payloads have no ``sensitivity`` key; from_dict
    must default to ``None`` so legacy / pinned fixtures round-trip
    unchanged (additive-within-event_version=1 contract).
    """
    legacy_payload = {"play_id": "pre_t2_legacy_card"}
    card = _play_card_from_dict(legacy_payload)
    assert card.sensitivity is None, (
        "Pre-T2 payload (no sensitivity key) must round-trip to None; "
        "the additive-within-event_version=1 contract requires absent "
        "keys to default cleanly."
    )


def test_play_card_sensitivity_with_none_scenarios_round_trips(monkeypatch):
    # S13.6-T1a (Option D): flip INCLUDE_DEBUG_FIELDS ON for the notes
    # round-trip leg of this test.
    import src.utils as utils_mod
    monkeypatch.setitem(utils_mod.DEFAULTS, "INCLUDE_DEBUG_FIELDS", True)
    """A Sensitivity block with some scenarios ``None`` (degenerate-input
    helper output) round-trips cleanly. Notes survive.
    """
    rr = RevenueRange(
        p10=1.0, p50=2.0, p90=3.0,
        source=RevenueRangeSource.BLEND,
        drivers=[],
        suppressed=False,
    )
    block = Sensitivity(
        scenario_observed_n_halved=None,
        scenario_observed_n_doubled=rr,
        scenario_prior_shifted_down=None,
        scenario_prior_shifted_up=rr,
        pseudo_n_used=30,
        notes=["scenario_a_degenerate", "scenario_c_degenerate"],
    )
    card = PlayCard(play_id="partial", sensitivity=block)
    payload = _play_card_to_dict_payload(card)
    round_tripped = _play_card_from_dict(payload)
    assert round_tripped.sensitivity == block


# ---------------------------------------------------------------------------
# Test 2 — helper math correctness.
# ---------------------------------------------------------------------------


def test_compute_sensitivity_reuses_bayesian_blend_math():
    """``compute_sensitivity`` must produce p50 values that equal
    ``audience * bayesian_blend(...) * aov`` for each perturbed input.
    No parallel sizing math — the scenarios are re-runs of the live
    blend with one input perturbed.
    """
    prior_value = 0.05
    prior_p10 = 0.02
    prior_p90 = 0.10
    pseudo_n = 30
    store_value = 0.20
    n_observed = 100
    audience = 1000
    aov = 50.0

    block = compute_sensitivity(
        prior_value=prior_value,
        prior_range_p10=prior_p10,
        prior_range_p90=prior_p90,
        pseudo_n=pseudo_n,
        store_value=store_value,
        n_observed=n_observed,
        audience_size=audience,
        aov=aov,
    )

    # observed_n halved -> n=50 -> re-blend, then audience * posterior * aov
    expected_halved_posterior = bayesian_blend(
        prior_value=prior_value, pseudo_n=pseudo_n,
        store_value=store_value, n_observed=50,
    )
    expected_halved_p50 = round(audience * expected_halved_posterior * aov, 2)
    assert block.scenario_observed_n_halved is not None
    assert block.scenario_observed_n_halved.p50 == expected_halved_p50

    # observed_n doubled -> n=200
    expected_doubled_posterior = bayesian_blend(
        prior_value=prior_value, pseudo_n=pseudo_n,
        store_value=store_value, n_observed=200,
    )
    expected_doubled_p50 = round(audience * expected_doubled_posterior * aov, 2)
    assert block.scenario_observed_n_doubled is not None
    assert block.scenario_observed_n_doubled.p50 == expected_doubled_p50

    # prior shifted -25%
    expected_prior_down_posterior = bayesian_blend(
        prior_value=prior_value * 0.75, pseudo_n=pseudo_n,
        store_value=store_value, n_observed=n_observed,
    )
    expected_prior_down_p50 = round(audience * expected_prior_down_posterior * aov, 2)
    assert block.scenario_prior_shifted_down is not None
    assert block.scenario_prior_shifted_down.p50 == expected_prior_down_p50

    # prior shifted +25%
    expected_prior_up_posterior = bayesian_blend(
        prior_value=prior_value * 1.25, pseudo_n=pseudo_n,
        store_value=store_value, n_observed=n_observed,
    )
    expected_prior_up_p50 = round(audience * expected_prior_up_posterior * aov, 2)
    assert block.scenario_prior_shifted_up is not None
    assert block.scenario_prior_shifted_up.p50 == expected_prior_up_p50

    # pseudo_n_used surfaces the live pseudo_n.
    assert block.pseudo_n_used == pseudo_n


def test_compute_sensitivity_directionality():
    """When store_value > prior_value:
      - halving observed_n pulls posterior toward prior (p50 lower).
      - doubling observed_n pulls posterior toward store (p50 higher).
      - shifting prior down lowers posterior; shifting up raises it.
    """
    block = compute_sensitivity(
        prior_value=0.05,
        prior_range_p10=0.02,
        prior_range_p90=0.10,
        pseudo_n=30,
        store_value=0.20,  # higher than prior
        n_observed=100,
        audience_size=1000,
        aov=50.0,
    )
    # live posterior anchor (for reference)
    live_posterior = bayesian_blend(
        prior_value=0.05, pseudo_n=30, store_value=0.20, n_observed=100,
    )
    live_p50 = round(1000 * live_posterior * 50.0, 2)

    assert block.scenario_observed_n_halved.p50 < live_p50, (
        "halving observed_n must pull posterior toward prior (lower)"
    )
    assert block.scenario_observed_n_doubled.p50 > live_p50, (
        "doubling observed_n must pull posterior toward store (higher)"
    )
    assert block.scenario_prior_shifted_down.p50 < live_p50, (
        "shifting prior down must lower the posterior"
    )
    assert block.scenario_prior_shifted_up.p50 > live_p50, (
        "shifting prior up must raise the posterior"
    )


def test_compute_sensitivity_degenerate_audience_returns_none_scenarios():
    """``audience_size=0`` (or ``aov<=0``) on a scenario returns ``None``
    for every scenario revenue_range — the math is meaningless without
    a positive audience / aov, and the block still constructs (caller
    decides whether to attach it; the production gate at
    measurement_builder requires ``aov > 0`` AND ``audience > 0`` so
    this path is reachable only via direct helper invocation).
    """
    block = compute_sensitivity(
        prior_value=0.05,
        prior_range_p10=0.02,
        prior_range_p90=0.10,
        pseudo_n=30,
        store_value=0.10,
        n_observed=100,
        audience_size=0,
        aov=50.0,
    )
    assert block.scenario_observed_n_halved is None
    assert block.scenario_observed_n_doubled is None
    assert block.scenario_prior_shifted_down is None
    assert block.scenario_prior_shifted_up is None


def test_compute_sensitivity_observed_n_zero_notes():
    """``observed_n=0`` halves/doubles to 0; helper documents the
    degeneracy via the ``notes`` field. Scenarios still produce
    revenue_ranges (they collapse to the prior).
    """
    block = compute_sensitivity(
        prior_value=0.05,
        prior_range_p10=0.02,
        prior_range_p90=0.10,
        pseudo_n=30,
        store_value=0.05,  # cold-start convention: store = prior
        n_observed=0,
        audience_size=1000,
        aov=50.0,
    )
    assert any("observed_n=0" in n for n in block.notes), (
        f"expected a note documenting the n=0 degeneracy; got {block.notes!r}"
    )


# ---------------------------------------------------------------------------
# Test 3 — per-builder population under flag ON.
# ---------------------------------------------------------------------------


_WIRED_TIER_B_PLAYS = (
    "winback_dormant_cohort",
    "discount_dependency_hygiene",
    "cohort_journey_first_to_second",
    "aov_lift_via_threshold_bundle",
)


def _synthetic_candidate(play_id: str) -> Any:
    return SimpleNamespace(
        play_id=play_id,
        preliminary_rejection_reason=None,
        audience_size=5000,
        segment_definition="synthetic test cohort",
    )


@pytest.mark.parametrize("play_id", _WIRED_TIER_B_PLAYS)
def test_prior_anchored_builder_populates_sensitivity_under_flag_on(play_id: str):
    """The 4 wired Tier-B builders populate
    ``PlayCard.sensitivity`` when ``ENGINE_V2_SENSITIVITY`` is ON
    AND the card carries a validated, non-suppressed BLEND revenue
    range.
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
        cfg={"ENGINE_V2_SENSITIVITY": True},
    )
    if card is None:
        pytest.skip(
            f"{play_id}: synthetic candidate fell out of the builder "
            f"(missing prior, audience floor, or AOV resolution). "
            f"Sensitivity population contract is unaffected; harness "
            f"coverage in tests/test_v2_harness_cfg_gated_fields.py "
            f"validates the wiring."
        )
    # Only assert population on the validated, non-suppressed BLEND
    # path; if the synthetic candidate landed on suppressed (e.g. AOV
    # unavailable) the field must be None per IM contract.
    if (
        card.revenue_range is not None
        and card.revenue_range.source == RevenueRangeSource.BLEND
        and not card.revenue_range.suppressed
    ):
        assert card.sensitivity is not None, (
            f"{play_id}: ENGINE_V2_SENSITIVITY=True with validated BLEND "
            f"revenue_range but sensitivity={card.sensitivity!r}; "
            f"expected populated Sensitivity block. The prior-anchored "
            f"builder seam at src/measurement_builder.py must populate "
            f"the block when the flag is ON on the validated path."
        )
        # Sanity-check the populated block has at least one scenario range.
        block = card.sensitivity
        any_scenario = (
            block.scenario_observed_n_halved
            or block.scenario_observed_n_doubled
            or block.scenario_prior_shifted_down
            or block.scenario_prior_shifted_up
        )
        assert any_scenario is not None, (
            f"{play_id}: populated Sensitivity block has all-None "
            f"scenarios; expected at least one populated RevenueRange."
        )
    else:
        # Suppressed / unvalidated path — field MUST stay None.
        assert card.sensitivity is None, (
            f"{play_id}: suppressed or non-BLEND revenue_range but "
            f"sensitivity populated ({card.sensitivity!r}); IM contract "
            f"requires sensitivity=None on suppressed paths."
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
        {"ENGINE_V2_SENSITIVITY": False},           # cfg present, flag explicitly OFF
    ],
)
def test_prior_anchored_builder_omits_sensitivity_under_flag_off(
    play_id: str, cfg_value: Optional[Dict[str, Any]]
):
    """Under any flag-OFF configuration (default, absent, explicit False),
    the prior-anchored builder emits ``sensitivity = None``. Load-bearing
    byte-identity contract pinned by the M0 + Beauty + Supplements HTML
    fixture shas.
    """
    card = build_prior_anchored_play_card(
        candidate=_synthetic_candidate(play_id),
        aligned=None,
        vertical="beauty",
        cfg=cfg_value,
    )
    if card is None:
        pytest.skip(
            f"{play_id}: synthetic candidate fell out. Byte-identity is "
            f"separately validated by the pinned HTML fixture shas."
        )
    assert card.sensitivity is None, (
        f"{play_id}: flag-OFF cfg={cfg_value!r} but sensitivity="
        f"{card.sensitivity!r}; expected None. The byte-identity "
        f"contract requires None at flag-OFF default."
    )


def test_prior_anchored_builder_chip_independent_of_sensitivity_flag():
    """Flag-independence (DS §5 invariant 14): toggling
    ``ENGINE_V2_SENSITIVITY`` does NOT change the chip surface, and
    toggling ``ENGINE_V2_TIER_CHIP`` does NOT change the sensitivity
    surface. The two flags must be observably independent.
    """
    from src.engine_run import EvidenceSourceChip

    play_id = "winback_dormant_cohort"
    # chip ON, sensitivity OFF
    card_a = build_prior_anchored_play_card(
        candidate=_synthetic_candidate(play_id),
        aligned=None,
        vertical="beauty",
        cfg={"ENGINE_V2_TIER_CHIP": True, "ENGINE_V2_SENSITIVITY": False},
    )
    # chip OFF, sensitivity ON
    card_b = build_prior_anchored_play_card(
        candidate=_synthetic_candidate(play_id),
        aligned=None,
        vertical="beauty",
        cfg={"ENGINE_V2_TIER_CHIP": False, "ENGINE_V2_SENSITIVITY": True},
    )
    if card_a is None or card_b is None:
        pytest.skip("synthetic candidate fell out; harness covers wiring")

    assert card_a.evidence_source == EvidenceSourceChip.STORE_OBSERVED
    assert card_a.sensitivity is None

    assert card_b.evidence_source is None
    if (
        card_b.revenue_range is not None
        and card_b.revenue_range.source == RevenueRangeSource.BLEND
        and not card_b.revenue_range.suppressed
    ):
        assert card_b.sensitivity is not None


# ---------------------------------------------------------------------------
# Test 5 — pinned-fixture HTML byte-identity at flag-OFF.
# ---------------------------------------------------------------------------


_S8_T2_PINNED_FIXTURES_AT_FLAG_OFF = {
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


def test_pinned_fixtures_byte_identical_under_s8_t2_flag_off():
    """At ``ENGINE_V2_SENSITIVITY=false`` default, the 5 pinned HTML
    fixtures must match the post-S8-T1.5 baseline byte-for-byte. T2.5
    atomic flip is the only ticket allowed to update these shas.
    """
    import hashlib

    for rel, expected_sha in _S8_T2_PINNED_FIXTURES_AT_FLAG_OFF.items():
        p = REPO_ROOT / rel
        assert p.exists(), f"pinned fixture missing: {rel}"
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        assert actual == expected_sha, (
            f"S8-T2 flag-OFF byte-identity drift on {rel}: "
            f"expected={expected_sha} actual={actual}. S8-T2 MUST be "
            f"renderer-invisible at flag-OFF; the sensitivity producer "
            f"must only populate when ENGINE_V2_SENSITIVITY is ON."
        )
