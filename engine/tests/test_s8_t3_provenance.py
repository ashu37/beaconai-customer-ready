"""Sprint 8 Ticket T3 — typed ``Provenance`` dataclass + ``PlayCard.provenance``
field + EB blend contract formalization.

Acceptance tests for the **third and final** S8 additive PlayCard field
(``evidence_source`` landed in S8-T1; ``sensitivity`` landed in S8-T2;
``provenance`` lands here) per DS verdict 2026-05-24 §5 invariant 12.

Scope is exactly the four wired Tier-B builders on the validated,
non-suppressed BLEND path, gated by ``ENGINE_V2_EB_BLEND``.

Critical context (per DS verdict 2026-05-24 §1 + §2): the empirical-Bayes
blend math is ALREADY SHIPPED at ``src/sizing.py`` (S7.5-T3
``bayesian_blend`` + ``effective_pseudo_n`` + ``PSEUDO_N_BY_STATUS``
locked table 30/15/10). S8-T3 formalizes the audit contract surface; the
math is unchanged. The pinned-fixture byte-identity test below verifies
this — any drift in revenue_range numerics at flag OFF would signal an
accidental blend math change.

Hard contract pins (must all pass):

1. ``Provenance`` dataclass + ``PlayCard.provenance`` round-trip through
   ``to_dict`` / ``from_dict``: typed object -> dict -> typed object;
   ``None`` round-trips to ``None``; absent payload key round-trips to
   ``None``.

2. :func:`src.sizing.compute_provenance` math is correct:
   - ``pseudo_n_used`` equals ``PSEUDO_N_BY_STATUS[status]`` for each
     validated status (30 / 15 / 10).
   - ``pseudo_n_used + observed_n`` denominator splits cleanly into
     ``weight_observed + weight_prior == 1.0`` (within rounding).
   - Edge case ``observed_n=0`` (cold-start): weights collapse to
     prior-dominant; ``notes`` documents the degeneracy.
   - Pathological case (status with pseudo_n_cap=0) returns ``None``
     (HEURISTIC_UNVALIDATED + PLACEHOLDER refusal — DS §5 invariant 2).

3. DS §5 invariant 5 pin: ``Provenance.pseudo_n_used`` MUST NOT exceed
   ``PSEUDO_N_BY_STATUS[validation_status]`` (the per-status cap is the
   load-bearing ceiling; profile can only LOWER).

4. DS §5 invariant 2 pin: HEURISTIC_UNVALIDATED + PLACEHOLDER priors
   never produce a Provenance audit object (refusal, not low-weight
   blend).

5. Under flag-ON (``ENGINE_V2_EB_BLEND = true`` in cfg), the prior-
   anchored builder seam populates ``PlayCard.provenance`` on the four
   wired Tier-B builders **provided** the card carries a validated,
   non-suppressed BLEND revenue range.

6. Under flag-OFF (default, or ``ENGINE_V2_EB_BLEND`` absent / false in
   cfg), the same builder seam emits ``PlayCard.provenance = None`` for
   the same Tier-B cards. This is the byte-identity contract.

7. The five pinned HTML fixtures (Beauty + Supplements + 3 M0 goldens)
   stay byte-identical at flag-OFF default — the renderer does not
   surface the block, so the only way the HTML could drift is if a
   producer accidentally populated the block at flag-OFF, the new
   dataclass import broke a code path, OR the blend math accidentally
   changed (the load-bearing math-equivalence check at flag OFF).

The S7.6 architectural invariants are NOT re-tested here — they are
covered by ``tests/test_s7_6_c1_priority_prepend_invariant.py`` which
runs unmodified through S8-T3. The chip + sensitivity producers are also
unaffected; S8-T1 + S8-T2 tests pass unmodified.
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
    Provenance,
    RevenueRangeSource,
)
from src.measurement_builder import (  # noqa: E402
    _PRIOR_ANCHORED,
    build_prior_anchored_play_card,
)
from src.priors_loader import PriorEntry, PriorValidationStatus  # noqa: E402
from src.sizing import (  # noqa: E402
    PSEUDO_N_BY_STATUS,
    compute_provenance,
)


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


def _make_provenance_block() -> Provenance:
    return Provenance(
        prior_play_id="winback_21_45",
        prior_key="base_rate",
        validation_status="validated_external",
        pseudo_n_used=30,
        pseudo_n_cap=30,
        observed_n=100,
        weight_observed=round(100 / 130, 6),
        weight_prior=round(30 / 130, 6),
        prior_source="config/priors_sources/winback_21_45__base_rate__beauty.md",
        notes=[],
    )


def test_play_card_provenance_round_trips_through_serialization(monkeypatch):
    """The Provenance object survives to_dict -> from_dict; ``None``
    round-trips to ``None``.
    """
    # S13.6-T1a (Option D): flip INCLUDE_DEBUG_FIELDS ON for the notes
    # round-trip leg of this test.
    import src.utils as utils_mod
    monkeypatch.setitem(utils_mod.DEFAULTS, "INCLUDE_DEBUG_FIELDS", True)
    for block in (_make_provenance_block(), None):
        card = PlayCard(play_id="round_trip_test", provenance=block)
        payload = _play_card_to_dict_payload(card)
        round_tripped = _play_card_from_dict(payload)
        assert round_tripped.provenance == block, (
            f"Provenance round-trip drift: in={block!r} "
            f"out={round_tripped.provenance!r}"
        )


def test_play_card_provenance_absent_payload_round_trips_to_none():
    """Pre-T3 fixture payloads have no ``provenance`` key; from_dict
    must default to ``None`` so legacy / pinned fixtures round-trip
    unchanged (additive-within-event_version=1 contract).
    """
    legacy_payload = {"play_id": "pre_t3_legacy_card"}
    card = _play_card_from_dict(legacy_payload)
    assert card.provenance is None


def test_play_card_provenance_with_notes_round_trips(monkeypatch):
    # S13.6-T1a (Option D): flip INCLUDE_DEBUG_FIELDS ON for this notes
    # round-trip test.
    import src.utils as utils_mod
    monkeypatch.setitem(utils_mod.DEFAULTS, "INCLUDE_DEBUG_FIELDS", True)
    """A Provenance object with populated notes round-trips cleanly."""
    block = Provenance(
        prior_play_id="aov_lift_via_threshold_bundle",
        prior_key="base_rate",
        validation_status="elicited_expert",
        pseudo_n_used=10,
        pseudo_n_cap=10,
        observed_n=0,
        weight_observed=0.0,
        weight_prior=1.0,
        prior_source="elicitation",
        notes=["observed_n=0; posterior collapses to prior (cold-start)"],
    )
    card = PlayCard(play_id="cold_start", provenance=block)
    payload = _play_card_to_dict_payload(card)
    round_tripped = _play_card_from_dict(payload)
    assert round_tripped.provenance == block


# ---------------------------------------------------------------------------
# Test 2 — helper math correctness + DS invariant pins.
# ---------------------------------------------------------------------------


def _make_prior(
    status: PriorValidationStatus,
    *,
    play_id: str = "winback_21_45",
    source_artifact: Optional[str] = "config/priors_sources/test.md",
) -> PriorEntry:
    return PriorEntry(
        name="base_rate",
        value=0.08,
        range_p10=0.05,
        range_p90=0.12,
        source_class="observational",
        play_id=play_id,
        validation_status=status,
        source_artifact=source_artifact,
        effective_n=60,
    )


@pytest.mark.parametrize(
    "status,expected_cap",
    [
        (PriorValidationStatus.VALIDATED_EXTERNAL, 30),
        (PriorValidationStatus.VALIDATED_INTERNAL, 15),
        (PriorValidationStatus.ELICITED_EXPERT, 10),
    ],
)
def test_compute_provenance_pseudo_n_cap_matches_locked_table(
    status: PriorValidationStatus, expected_cap: int
):
    """DS verdict 2026-05-24 §5 invariant 1 pin: ``pseudo_n_cap`` MUST
    equal :data:`PSEUDO_N_BY_STATUS` for every validated status. Locked
    table 30/15/10 through S14. No new pseudo_N numbers in S8.
    """
    prior = _make_prior(status)
    prov = compute_provenance(
        prior=prior, prior_key="base_rate", observed_n=100,
    )
    assert prov is not None
    assert prov.pseudo_n_cap == expected_cap
    assert PSEUDO_N_BY_STATUS[status] == expected_cap


@pytest.mark.parametrize(
    "status",
    [PriorValidationStatus.HEURISTIC_UNVALIDATED, PriorValidationStatus.PLACEHOLDER],
)
def test_compute_provenance_refuses_unvalidated_statuses(
    status: PriorValidationStatus,
):
    """DS verdict 2026-05-24 §5 invariant 2 pin: HEURISTIC_UNVALIDATED
    + PLACEHOLDER priors NEVER produce a Provenance audit object. They
    are refusal at the sizing layer (suppressed revenue range; no
    posterior), not low-weight blend.
    """
    prior = _make_prior(status)
    prov = compute_provenance(
        prior=prior, prior_key="base_rate", observed_n=100,
    )
    assert prov is None, (
        f"refused status {status.value!r} produced a Provenance object; "
        f"DS §5 invariant 2 requires None on refusal. Got: {prov!r}"
    )


@pytest.mark.parametrize(
    "status",
    list(PSEUDO_N_BY_STATUS.keys()),
)
def test_compute_provenance_pseudo_n_used_never_exceeds_cap(
    status: PriorValidationStatus,
):
    """DS verdict 2026-05-24 §5 invariant 5 pin: ``pseudo_n_used`` MUST
    NOT exceed ``PSEUDO_N_BY_STATUS[validation_status]``. The per-status
    cap is the load-bearing ceiling; the store profile can only LOWER
    the weight, never raise it above the cap.
    """
    prior = _make_prior(status)
    for n_obs in (0, 1, 30, 100, 100_000):
        prov = compute_provenance(
            prior=prior, prior_key="base_rate", observed_n=n_obs,
        )
        assert prov is not None
        assert prov.pseudo_n_used <= prov.pseudo_n_cap, (
            f"status={status.value} observed_n={n_obs} "
            f"pseudo_n_used={prov.pseudo_n_used} exceeded "
            f"pseudo_n_cap={prov.pseudo_n_cap}; DS §5 invariant 5 "
            f"violated."
        )
        assert prov.pseudo_n_used == PSEUDO_N_BY_STATUS[status]


def test_compute_provenance_weights_sum_to_one():
    """Math correctness: ``weight_observed + weight_prior == 1.0`` for
    every non-degenerate (denominator > 0) input. Pinned across a range
    of observed_n values so the rounding boundary is exercised.
    """
    prior = _make_prior(PriorValidationStatus.VALIDATED_EXTERNAL)
    for n_obs in (1, 10, 30, 100, 1000, 224_077):
        prov = compute_provenance(
            prior=prior, prior_key="base_rate", observed_n=n_obs,
        )
        assert prov is not None
        total = prov.weight_observed + prov.weight_prior
        assert abs(total - 1.0) < 1e-5, (
            f"observed_n={n_obs} weights {prov.weight_observed} + "
            f"{prov.weight_prior} = {total}; expected sum 1.0."
        )


def test_compute_provenance_cold_start_notes_degeneracy():
    """``observed_n=0`` (cold-start): posterior collapses to prior; the
    helper must document the degeneracy via the ``notes`` field, and
    weight_observed must be 0.0 / weight_prior must be 1.0.
    """
    prior = _make_prior(PriorValidationStatus.VALIDATED_EXTERNAL)
    prov = compute_provenance(
        prior=prior, prior_key="base_rate", observed_n=0,
    )
    assert prov is not None
    assert prov.observed_n == 0
    assert prov.weight_observed == 0.0
    assert prov.weight_prior == 1.0
    assert any("observed_n=0" in n for n in prov.notes), (
        f"expected a note documenting the n=0 cold-start degeneracy; "
        f"got notes={prov.notes!r}"
    )


def test_compute_provenance_large_n_observed_dominates_posterior():
    """At large ``observed_n`` (n >> pseudo_n), ``weight_observed``
    approaches 1.0 and ``weight_prior`` approaches 0.0 — the store
    posterior dominates. Mirrors the DS verdict §2 math table.
    """
    prior = _make_prior(PriorValidationStatus.VALIDATED_EXTERNAL)
    prov = compute_provenance(
        prior=prior, prior_key="base_rate", observed_n=224_077,
    )
    assert prov is not None
    assert prov.weight_observed > 0.999
    assert prov.weight_prior < 0.001


def test_compute_provenance_surfaces_prior_metadata():
    """The audit object surfaces ``prior_play_id``, ``prior_key``,
    ``validation_status``, and ``prior_source`` so a reviewer can
    reproduce the blend without re-deriving it from
    ``drivers[*].blend_provenance``.
    """
    prior = _make_prior(
        PriorValidationStatus.VALIDATED_EXTERNAL,
        play_id="discount_dependency_hygiene",
        source_artifact="config/priors_sources/discount_dependency_hygiene__base_rate__beauty.md",
    )
    prov = compute_provenance(
        prior=prior, prior_key="base_rate", observed_n=224_077,
    )
    assert prov is not None
    assert prov.prior_play_id == "discount_dependency_hygiene"
    assert prov.prior_key == "base_rate"
    assert prov.validation_status == "validated_external"
    assert "priors_sources" in prov.prior_source


def test_compute_provenance_falls_back_to_source_class_when_no_artifact():
    """When ``prior.source_artifact`` is None, ``prior_source`` falls
    back to ``source_class`` so the audit object always carries something
    traceable.
    """
    prior = _make_prior(
        PriorValidationStatus.VALIDATED_INTERNAL,
        source_artifact=None,
    )
    prov = compute_provenance(
        prior=prior, prior_key="base_rate", observed_n=10,
    )
    assert prov is not None
    assert prov.prior_source == "observational"


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
def test_prior_anchored_builder_populates_provenance_under_flag_on(play_id: str):
    """The 4 wired Tier-B builders populate ``PlayCard.provenance`` when
    ``ENGINE_V2_EB_BLEND`` is ON AND the card carries a validated,
    non-suppressed BLEND revenue range.
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
        cfg={"ENGINE_V2_EB_BLEND": True},
    )
    if card is None:
        pytest.skip(
            f"{play_id}: synthetic candidate fell out of the builder "
            f"(missing prior, audience floor, or AOV resolution). "
            f"Provenance population contract is unaffected; harness "
            f"coverage in tests/test_v2_harness_cfg_gated_fields.py "
            f"validates the wiring."
        )
    if (
        card.revenue_range is not None
        and card.revenue_range.source == RevenueRangeSource.BLEND
        and not card.revenue_range.suppressed
    ):
        assert card.provenance is not None, (
            f"{play_id}: ENGINE_V2_EB_BLEND=True with validated BLEND "
            f"revenue_range but provenance={card.provenance!r}; "
            f"expected populated Provenance object."
        )
        # Sanity-check the populated block carries the load-bearing audit
        # fields.
        prov = card.provenance
        assert prov.validation_status in {
            "validated_external", "validated_internal", "elicited_expert",
        }, (
            f"{play_id}: Provenance.validation_status={prov.validation_status!r} "
            f"not in the validated set — DS §5 invariant 2 violated."
        )
        assert prov.pseudo_n_cap in {30, 15, 10}, (
            f"{play_id}: Provenance.pseudo_n_cap={prov.pseudo_n_cap} "
            f"not in the locked PSEUDO_N_BY_STATUS table {{30,15,10}}."
        )
        assert prov.pseudo_n_used <= prov.pseudo_n_cap, (
            f"{play_id}: DS §5 invariant 5 violated — pseudo_n_used="
            f"{prov.pseudo_n_used} > pseudo_n_cap={prov.pseudo_n_cap}."
        )
    else:
        # Suppressed / unvalidated path — field MUST stay None.
        assert card.provenance is None, (
            f"{play_id}: suppressed or non-BLEND revenue_range but "
            f"provenance populated ({card.provenance!r}); IM contract "
            f"requires provenance=None on suppressed/unvalidated paths."
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
        {"ENGINE_V2_EB_BLEND": False},              # cfg present, flag explicitly OFF
    ],
)
def test_prior_anchored_builder_omits_provenance_under_flag_off(
    play_id: str, cfg_value: Optional[Dict[str, Any]]
):
    """Under any flag-OFF configuration (default, absent, explicit False),
    the prior-anchored builder emits ``provenance = None``. Load-bearing
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
    assert card.provenance is None, (
        f"{play_id}: flag-OFF cfg={cfg_value!r} but provenance="
        f"{card.provenance!r}; expected None. The byte-identity "
        f"contract requires None at flag-OFF default."
    )


def test_prior_anchored_builder_eb_blend_flag_independent_of_chip_and_sensitivity():
    """Flag-independence (DS §5 invariant 14): toggling
    ``ENGINE_V2_EB_BLEND`` does NOT change the chip or sensitivity
    surfaces, and toggling those flags does NOT change the provenance
    surface. The three flags must be observably independent.
    """
    from src.engine_run import EvidenceSourceChip

    play_id = "winback_dormant_cohort"
    # eb_blend ON; chip OFF, sensitivity OFF
    card_a = build_prior_anchored_play_card(
        candidate=_synthetic_candidate(play_id),
        aligned=None,
        vertical="beauty",
        cfg={
            "ENGINE_V2_TIER_CHIP": False,
            "ENGINE_V2_SENSITIVITY": False,
            "ENGINE_V2_EB_BLEND": True,
        },
    )
    # eb_blend OFF; chip ON, sensitivity ON
    card_b = build_prior_anchored_play_card(
        candidate=_synthetic_candidate(play_id),
        aligned=None,
        vertical="beauty",
        cfg={
            "ENGINE_V2_TIER_CHIP": True,
            "ENGINE_V2_SENSITIVITY": True,
            "ENGINE_V2_EB_BLEND": False,
        },
    )
    if card_a is None or card_b is None:
        pytest.skip("synthetic candidate fell out; harness covers wiring")

    # card_a: only provenance populated on the validated BLEND path
    assert card_a.evidence_source is None
    assert card_a.sensitivity is None
    if (
        card_a.revenue_range is not None
        and card_a.revenue_range.source == RevenueRangeSource.BLEND
        and not card_a.revenue_range.suppressed
    ):
        assert card_a.provenance is not None

    # card_b: chip + sensitivity populated; provenance NOT populated
    assert card_b.evidence_source == EvidenceSourceChip.STORE_OBSERVED
    assert card_b.provenance is None


# ---------------------------------------------------------------------------
# Test 5 — pinned-fixture HTML byte-identity at flag-OFF.
# ---------------------------------------------------------------------------


_S8_T3_PINNED_FIXTURES_AT_FLAG_OFF = {
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


def test_pinned_fixtures_byte_identical_under_s8_t3_flag_off():
    """At ``ENGINE_V2_EB_BLEND=false`` default, the 5 pinned HTML
    fixtures must match the post-S8-T2.5 baseline byte-for-byte. T3.5
    atomic flip is the only ticket allowed to update these shas.

    This is the load-bearing math-equivalence pin per the DS verdict:
    the EB blend math is ALREADY SHIPPED and unchanged by S8-T3 (contract
    formalization only). If a fixture drifts at flag OFF, the most likely
    cause is an accidental change to the blend math (which would re-pin
    Tier-B revenue_range.p10/p50/p90 even at flag OFF).
    """
    import hashlib

    for rel, expected_sha in _S8_T3_PINNED_FIXTURES_AT_FLAG_OFF.items():
        p = REPO_ROOT / rel
        assert p.exists(), f"pinned fixture missing: {rel}"
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        assert actual == expected_sha, (
            f"S8-T3 flag-OFF byte-identity drift on {rel}: "
            f"expected={expected_sha} actual={actual}. S8-T3 MUST be "
            f"renderer-invisible at flag-OFF; the provenance producer "
            f"must only populate when ENGINE_V2_EB_BLEND is ON, AND "
            f"the EB blend math (bayesian_blend / effective_pseudo_n) "
            f"must remain unchanged from S7.5-T3 ship."
        )
