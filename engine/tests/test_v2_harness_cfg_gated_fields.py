"""Sprint 8 Ticket T1.6 — harness-level coverage for flag-gated producer fields.

Background (per DS verdict 2026-05-24 §Q4 + new invariant 16):

S8-T1 landed the ``EvidenceSourceChip`` enum, the ``PlayCard.evidence_source``
field, the ``ENGINE_V2_TIER_CHIP`` flag, and the producer gate at
``src/measurement_builder.py:2428-2430``. However the 4 prior-anchored
builder callsites in ``src/main.py`` (winback at L1332, replenishment at
L1378, journey at L1426, discount at L1478) did NOT thread ``cfg=cfg``, so
the producer gate was unreachable from :func:`src.main.run` — the flag was
dead code regardless of state for 4 of 5 Tier-B builders. (The 5th, AOV
bundle at L1536, already threaded ``cfg=cfg`` via the S7.6-T5 observed-
effect work.) The producer-direct tests in
``tests/test_s8_t1_evidence_source_chip.py`` constructed ``cfg`` manually
and called the helper directly, so they missed the wiring gap.

T1.6 deliverables in this module:

1. **Harness-level coverage test** (Deliverable 2): runs
   ``python -m src.main`` end-to-end on ``healthy_beauty_240d`` with
   ``ENGINE_V2_TIER_CHIP`` parametrized OFF and ON, and asserts the
   3 wired Tier-B Recommended cards' ``evidence_source`` is ``None``
   vs ``"STORE_OBSERVED"`` respectively. Reads
   ``receipts/engine_run.json`` directly (not the rendered briefing.html
   — the renderer does not surface the chip today).

2. **Structural callsite pin** (Deliverable 3): parses ``src/main.py``
   and asserts every call to ``build_prior_anchored_recommendations``
   threads ``cfg=cfg`` as a kwarg. Pattern-protects S8-T2 (Sensitivity),
   S8-T3 (provenance), and S13 (ML AUDIENCE) — all of which will
   reuse this seam — from re-discovering the same bug.

This module is the canonical home of DS invariant 16 (DS-locked
2026-05-24): every flag-gated PlayCard field — defined as any attribute
whose population branches on ``cfg.get("FLAG", ...)`` in the producer —
must be exercised by at least one harness-level test that calls
``run_action_engine`` (here via the synthetic harness subprocess) with
the flag forced ON and asserts the field populates on at least one
rendered card. T2/T3/S13 each append a row to the harness parametrize
when they land.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.synthetic_harness import run_scenario  # noqa: E402


# ---------------------------------------------------------------------------
# Harness coverage — Deliverable 2 (DS verdict §Q3 item 2 + §Q5 invariant 16)
# ---------------------------------------------------------------------------


_SCENARIO_NAME = "healthy_beauty_240d"

# Pinned post-S8-T0 env superset matching tests/test_slate_regression_beauty_brand.py
# (the existing Beauty harness pin). T1.6 layers ENGINE_V2_TIER_CHIP on top
# (parametrized OFF/ON below). All other flags are deliberately fixed to
# pin the harness invocation byte-for-byte.
_BEAUTY_ENV_OVERRIDES_BASE: dict[str, str] = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "VERTICAL_MODE": "beauty",
    "WINDOW_POLICY": "auto",
}

# The 3 Tier-B builders that activate on Beauty under the
# post-S7-T2.5/T1.5/T3.5 pinned flag stack (see tests/test_slate_regression_beauty_brand.py
# EXPECTED_RECOMMENDED_PLAY_IDS). aov_lift_via_threshold_bundle is the 4th
# wired Tier-B but lands in Considered on Beauty under the T7.5-deferred
# posture, not Recommended — so it does not carry the chip-on-Recommended
# contract this test pins. The chip producer still fires for it (covered
# by S8-T1's producer-direct tests at flag ON).
_WIRED_TIER_B_RECOMMENDED_ON_BEAUTY = {
    "winback_dormant_cohort",
    "discount_dependency_hygiene",
    "cohort_journey_first_to_second",
}


def _run_beauty_harness_and_load_engine_run(
    tier_chip_flag: bool,
) -> dict:
    """Run the Beauty harness once with ENGINE_V2_TIER_CHIP set to the
    requested value, return the receipts/engine_run.json payload.

    Wraps ``run_scenario`` from tests/synthetic_harness.py (the same
    runner used by tests/test_slate_regression_beauty_brand.py). Subprocess
    invocation guarantees we exercise the real ``python -m src.main``
    entry point including cfg construction via ``get_config()``.
    """
    env_overrides = dict(_BEAUTY_ENV_OVERRIDES_BASE)
    env_overrides["ENGINE_V2_TIER_CHIP"] = "true" if tier_chip_flag else "false"

    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "t1_6"
        result = run_scenario(
            _SCENARIO_NAME,
            out_dir,
            env_overrides=env_overrides,
            timeout_sec=300,
        )
        assert result.returncode == 0, (
            f"synthetic harness for {_SCENARIO_NAME!r} failed "
            f"(rc={result.returncode}, tier_chip_flag={tier_chip_flag}). "
            f"stderr (last 500 chars): {result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), (
            f"engine_run.json not produced at {receipts}; harness rc=0 "
            f"but receipts missing."
        )
        return json.loads(receipts.read_text(encoding="utf-8"))


def _recommended_cards(engine_run: dict) -> List[dict]:
    return list(engine_run.get("recommendations") or [])


def _evidence_source_by_play_id(cards: List[dict]) -> dict:
    return {
        str(c.get("play_id")): c.get("evidence_source")
        for c in cards
        if c.get("play_id") is not None
    }


@pytest.mark.parametrize(
    "tier_chip_flag,expected_evidence_source",
    [
        (False, None),
        (True, "STORE_OBSERVED"),
    ],
    ids=["flag_off_evidence_source_None", "flag_on_evidence_source_STORE_OBSERVED"],
)
def test_evidence_source_populates_via_main_harness(
    tier_chip_flag: bool,
    expected_evidence_source: Optional[str],
) -> None:
    """Harness-level invariant-16 contract on the Beauty 240d fixture.

    With ``ENGINE_V2_TIER_CHIP`` toggled via env, run ``python -m src.main``
    end-to-end and assert that the 3 wired Tier-B Recommended cards on
    Beauty carry the expected ``evidence_source`` value:

    - Flag OFF (default): all 3 cards have ``evidence_source = None``
      (byte-identity contract — the field is serialized as JSON null /
      Python None on the recommendations[] payload).
    - Flag ON: all 3 cards have ``evidence_source = "STORE_OBSERVED"``
      (the producer gate at src/measurement_builder.py:2428-2430 fires
      and emits ``EvidenceSourceChip.STORE_OBSERVED``, which serializes
      to the upper-snake string value).

    This is the test that would have caught S8-T1's cfg-wiring gap
    (4 of 5 callsites missing ``cfg=cfg`` in src/main.py). T1.6 added
    ``cfg=cfg`` to the 4 missing callsites; if a future ticket regresses
    the wiring on any of the 3 Beauty-Recommended builders, this test
    fails at flag ON with ``evidence_source = None`` and points the
    fixer at the gap.
    """
    engine_run = _run_beauty_harness_and_load_engine_run(tier_chip_flag)
    cards = _recommended_cards(engine_run)
    es_map = _evidence_source_by_play_id(cards)

    missing = _WIRED_TIER_B_RECOMMENDED_ON_BEAUTY - set(es_map.keys())
    assert not missing, (
        f"Beauty harness did not surface expected Tier-B Recommended "
        f"play_ids; missing={missing}; got={sorted(es_map.keys())}. "
        f"If the Beauty slate composition changed, update "
        f"_WIRED_TIER_B_RECOMMENDED_ON_BEAUTY and re-pin "
        f"tests/test_slate_regression_beauty_brand.py first."
    )

    for play_id in _WIRED_TIER_B_RECOMMENDED_ON_BEAUTY:
        actual = es_map.get(play_id)
        assert actual == expected_evidence_source, (
            f"S8-T1.6 harness contract violation: play_id={play_id!r} "
            f"tier_chip_flag={tier_chip_flag} expected_evidence_source="
            f"{expected_evidence_source!r} actual={actual!r}. "
            f"At flag ON, the producer gate at "
            f"src/measurement_builder.py:2428-2430 must populate "
            f"evidence_source=STORE_OBSERVED on every wired Tier-B "
            f"Recommended card. At flag OFF, every card must have "
            f"evidence_source=None (the byte-identity contract). If "
            f"this fails at flag ON, the most likely cause is a "
            f"regression of the cfg=cfg kwarg on the callsite in "
            f"src/main.py — see the structural pin test below."
        )


# ---------------------------------------------------------------------------
# Harness coverage — S8-T2 Sensitivity (DS invariant 16 — new row per ticket)
# ---------------------------------------------------------------------------
#
# DS invariant 16 (DS-locked 2026-05-24): every flag-gated PlayCard field
# must be exercised by at least one harness-level test. S8-T2 appends this
# row for ``ENGINE_V2_SENSITIVITY -> sensitivity``. The same Beauty 240d
# harness pin used above is reused; the assertion shape mirrors the chip
# contract (None at flag OFF, populated at flag ON) but with the field-
# specific structure (an Optional dict carrying the four scenario
# revenue_ranges + pseudo_n_used + notes).


def _sensitivity_by_play_id(cards: List[dict]) -> dict:
    return {
        str(c.get("play_id")): c.get("sensitivity")
        for c in cards
        if c.get("play_id") is not None
    }


def _run_beauty_harness_with_sensitivity_flag(
    sensitivity_flag: bool,
) -> dict:
    """Run the Beauty harness once with ENGINE_V2_SENSITIVITY set to
    the requested value, return the receipts/engine_run.json payload.

    Distinct from :func:`_run_beauty_harness_and_load_engine_run` because
    S8-T2 must verify the flag is independently observable (DS Q7 §4
    separate-flag verdict). Keeps the chip default (post-T1.5 ON) and
    layers only the sensitivity flag.
    """
    env_overrides = dict(_BEAUTY_ENV_OVERRIDES_BASE)
    env_overrides["ENGINE_V2_SENSITIVITY"] = "true" if sensitivity_flag else "false"

    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "t2"
        result = run_scenario(
            _SCENARIO_NAME,
            out_dir,
            env_overrides=env_overrides,
            timeout_sec=300,
        )
        assert result.returncode == 0, (
            f"synthetic harness for {_SCENARIO_NAME!r} failed "
            f"(rc={result.returncode}, sensitivity_flag={sensitivity_flag}). "
            f"stderr (last 500 chars): {result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), (
            f"engine_run.json not produced at {receipts}; harness rc=0 "
            f"but receipts missing."
        )
        return json.loads(receipts.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "sensitivity_flag,expected_populated",
    [
        (False, False),
        (True, True),
    ],
    ids=["flag_off_sensitivity_None", "flag_on_sensitivity_populated"],
)
def test_sensitivity_populates_via_main_harness(
    sensitivity_flag: bool,
    expected_populated: bool,
) -> None:
    """Harness-level invariant-16 contract on the Beauty 240d fixture
    for the S8-T2 ``sensitivity`` field.

    With ``ENGINE_V2_SENSITIVITY`` toggled via env, run
    ``python -m src.main`` end-to-end and assert that the wired Tier-B
    Recommended cards on Beauty carry the expected ``sensitivity`` shape:

    - Flag OFF (default): every wired Tier-B card has
      ``sensitivity = None`` (byte-identity contract).
    - Flag ON: every wired Tier-B card on the validated, non-suppressed
      BLEND path has ``sensitivity`` populated as a dict with the four
      scenario keys + pseudo_n_used + notes.

    This is the test that would catch a cfg-wiring regression on the
    new flag (parallel to the S8-T1.6 test for ``evidence_source``).
    The structural callsite pin below already protects cfg=cfg wiring
    on every prior-anchored builder callsite; this test catches a
    threading regression at the producer-gate seam.
    """
    engine_run = _run_beauty_harness_with_sensitivity_flag(sensitivity_flag)
    cards = _recommended_cards(engine_run)
    sens_map = _sensitivity_by_play_id(cards)

    missing = _WIRED_TIER_B_RECOMMENDED_ON_BEAUTY - set(sens_map.keys())
    assert not missing, (
        f"Beauty harness did not surface expected Tier-B Recommended "
        f"play_ids; missing={missing}; got={sorted(sens_map.keys())}."
    )

    for play_id in _WIRED_TIER_B_RECOMMENDED_ON_BEAUTY:
        actual = sens_map.get(play_id)
        if expected_populated:
            assert actual is not None, (
                f"S8-T2 harness contract violation: play_id={play_id!r} "
                f"ENGINE_V2_SENSITIVITY=True but sensitivity={actual!r}; "
                f"expected populated dict. At flag ON, the producer at "
                f"src/measurement_builder.py must populate Sensitivity "
                f"on every wired Tier-B Recommended card with a "
                f"validated, non-suppressed BLEND revenue_range. If "
                f"this fails at flag ON, check (a) cfg=cfg threading "
                f"on the callsite in src/main.py (the structural pin "
                f"below would catch the kwarg-missing case), or (b) "
                f"the card landed on the suppressed / prior-unvalidated "
                f"path (which legitimately leaves sensitivity=None)."
            )
            # Shape-check: the four scenario keys + pseudo_n_used + notes.
            assert isinstance(actual, dict), (
                f"{play_id}: sensitivity should serialize as dict; "
                f"got {type(actual).__name__}"
            )
            for key in (
                "scenario_observed_n_halved",
                "scenario_observed_n_doubled",
                "scenario_prior_shifted_down",
                "scenario_prior_shifted_up",
                "pseudo_n_used",
                # S13.6-T1a (Option D): ``notes`` gated behind
                # INCLUDE_DEBUG_FIELDS=False default per Pivot 2;
                # dropped from harness JSON by design.
            ):
                assert key in actual, (
                    f"{play_id}: sensitivity dict missing key {key!r}; "
                    f"got keys={sorted(actual.keys())}"
                )
        else:
            assert actual is None, (
                f"S8-T2 harness contract violation: play_id={play_id!r} "
                f"ENGINE_V2_SENSITIVITY=False but sensitivity={actual!r}; "
                f"expected None (byte-identity contract)."
            )


# ---------------------------------------------------------------------------
# Harness coverage — S8-T3 Provenance (DS invariant 16 — new row per ticket)
# ---------------------------------------------------------------------------
#
# DS invariant 16 (DS-locked 2026-05-24): every flag-gated PlayCard field
# must be exercised by at least one harness-level test. S8-T3 appends this
# row for ``ENGINE_V2_EB_BLEND -> provenance``. Same Beauty 240d harness
# pin used above; the assertion shape mirrors the chip + sensitivity
# contract (None at flag OFF, populated at flag ON) but with the field-
# specific structure (an Optional dict carrying the typed audit object —
# prior_play_id + validation_status + pseudo_n_used + pseudo_n_cap +
# observed_n + weight_observed + weight_prior + prior_source + notes).


def _provenance_by_play_id(cards: List[dict]) -> dict:
    return {
        str(c.get("play_id")): c.get("provenance")
        for c in cards
        if c.get("play_id") is not None
    }


def _run_beauty_harness_with_eb_blend_flag(
    eb_blend_flag: bool,
) -> dict:
    """Run the Beauty harness once with ENGINE_V2_EB_BLEND set to the
    requested value, return the receipts/engine_run.json payload.

    Distinct from the chip + sensitivity harnesses above because S8-T3
    must verify the flag is independently observable (DS Q7 §4
    separate-flag verdict + S7.6 atomic-flip discipline). Keeps the chip
    + sensitivity defaults at their post-T1.5/T2.5 ON state and layers
    only the EB-blend flag.
    """
    env_overrides = dict(_BEAUTY_ENV_OVERRIDES_BASE)
    env_overrides["ENGINE_V2_EB_BLEND"] = "true" if eb_blend_flag else "false"

    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "t3"
        result = run_scenario(
            _SCENARIO_NAME,
            out_dir,
            env_overrides=env_overrides,
            timeout_sec=300,
        )
        assert result.returncode == 0, (
            f"synthetic harness for {_SCENARIO_NAME!r} failed "
            f"(rc={result.returncode}, eb_blend_flag={eb_blend_flag}). "
            f"stderr (last 500 chars): {result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), (
            f"engine_run.json not produced at {receipts}; harness rc=0 "
            f"but receipts missing."
        )
        return json.loads(receipts.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "eb_blend_flag,expected_populated",
    [
        (False, False),
        (True, True),
    ],
    ids=["flag_off_provenance_None", "flag_on_provenance_populated"],
)
def test_provenance_populates_via_main_harness(
    eb_blend_flag: bool,
    expected_populated: bool,
) -> None:
    """Harness-level invariant-16 contract on the Beauty 240d fixture
    for the S8-T3 ``provenance`` field.

    With ``ENGINE_V2_EB_BLEND`` toggled via env, run ``python -m src.main``
    end-to-end and assert that the wired Tier-B Recommended cards on
    Beauty carry the expected ``provenance`` shape:

    - Flag OFF (default): every wired Tier-B card has ``provenance =
      None`` (byte-identity contract).
    - Flag ON: every wired Tier-B card on the validated, non-suppressed
      BLEND path has ``provenance`` populated as a dict with the typed
      audit fields.

    This is the test that would catch a cfg-wiring regression on the
    new flag (parallel to the S8-T1.6 + S8-T2 harness tests). The
    structural callsite pin below already protects cfg=cfg wiring on
    every prior-anchored builder callsite; this test catches a threading
    regression at the producer-gate seam.
    """
    engine_run = _run_beauty_harness_with_eb_blend_flag(eb_blend_flag)
    cards = _recommended_cards(engine_run)
    prov_map = _provenance_by_play_id(cards)

    missing = _WIRED_TIER_B_RECOMMENDED_ON_BEAUTY - set(prov_map.keys())
    assert not missing, (
        f"Beauty harness did not surface expected Tier-B Recommended "
        f"play_ids; missing={missing}; got={sorted(prov_map.keys())}."
    )

    for play_id in _WIRED_TIER_B_RECOMMENDED_ON_BEAUTY:
        actual = prov_map.get(play_id)
        if expected_populated:
            assert actual is not None, (
                f"S8-T3 harness contract violation: play_id={play_id!r} "
                f"ENGINE_V2_EB_BLEND=True but provenance={actual!r}; "
                f"expected populated dict. At flag ON, the producer at "
                f"src/measurement_builder.py must populate Provenance on "
                f"every wired Tier-B Recommended card with a validated, "
                f"non-suppressed BLEND revenue_range. If this fails at "
                f"flag ON, check (a) cfg=cfg threading on the callsite "
                f"in src/main.py (the structural pin below would catch "
                f"the kwarg-missing case), or (b) the card landed on "
                f"the suppressed / prior-unvalidated path (which "
                f"legitimately leaves provenance=None per DS §5 "
                f"invariant 2)."
            )
            assert isinstance(actual, dict), (
                f"{play_id}: provenance should serialize as dict; "
                f"got {type(actual).__name__}"
            )
            for key in (
                "prior_play_id",
                "prior_key",
                "validation_status",
                "pseudo_n_used",
                "pseudo_n_cap",
                "observed_n",
                "weight_observed",
                "weight_prior",
                "prior_source",
                # S13.6-T1a (Option D): ``notes`` gated behind
                # INCLUDE_DEBUG_FIELDS=False default per Pivot 2.
            ):
                assert key in actual, (
                    f"{play_id}: provenance dict missing key {key!r}; "
                    f"got keys={sorted(actual.keys())}"
                )
            # DS §5 invariant 5 (pseudo_n_used <= pseudo_n_cap) AND
            # invariant 1 (cap from locked PSEUDO_N_BY_STATUS table).
            assert int(actual["pseudo_n_used"]) <= int(actual["pseudo_n_cap"])
            assert int(actual["pseudo_n_cap"]) in {30, 15, 10}
        else:
            assert actual is None, (
                f"S8-T3 harness contract violation: play_id={play_id!r} "
                f"ENGINE_V2_EB_BLEND=False but provenance={actual!r}; "
                f"expected None (byte-identity contract)."
            )


# ---------------------------------------------------------------------------
# Harness coverage — S8-T4 Play Library wave 1 (DS invariant 16 — new row)
# ---------------------------------------------------------------------------
#
# DS invariant 16 extension for S8-T4: even though Play Library wave 1 is
# a refactor-only ticket (folder-only restructure; no new flag-gated
# PlayCard field; byte-identical contract at BOTH flag states), the
# refined sub-rule from DS verdict 2026-05-24 §Q3 still applies: flag-ON
# routing behavior must be exercised by a harness-level test that runs
# main.run_action_engine end-to-end with the flag forced ON. The
# acceptance contract is:
#
#   - All 3 wired Tier-B Recommended cards on Beauty still fire (so the
#     migration did not silently break the recommendation pipeline).
#   - replenishment_due continues to produce zero audience on Beauty
#     (KI-NEW-G honest-dormancy preserved — load-bearing per DS §3 Q6).


def _run_beauty_harness_with_play_library_flag(
    play_library_flag: bool,
) -> dict:
    """Run the Beauty harness once with ENGINE_V2_PLAY_LIBRARY_WAVE1 set
    to the requested value, return the receipts/engine_run.json payload.
    Keeps the chip + sensitivity + EB-blend defaults at their post-T1.5
    / T2.5 / T3.5 ON state.
    """
    env_overrides = dict(_BEAUTY_ENV_OVERRIDES_BASE)
    env_overrides["ENGINE_V2_PLAY_LIBRARY_WAVE1"] = (
        "true" if play_library_flag else "false"
    )

    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "t4"
        result = run_scenario(
            _SCENARIO_NAME,
            out_dir,
            env_overrides=env_overrides,
            timeout_sec=300,
        )
        assert result.returncode == 0, (
            f"synthetic harness for {_SCENARIO_NAME!r} failed "
            f"(rc={result.returncode}, play_library_flag={play_library_flag}). "
            f"stderr (last 500 chars): {result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), (
            f"engine_run.json not produced at {receipts}; harness rc=0 "
            f"but receipts missing."
        )
        return json.loads(receipts.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "play_library_flag",
    [False, True],
    ids=["flag_off", "flag_on"],
)
def test_play_library_wave1_byte_identical_recommendations(
    play_library_flag: bool,
) -> None:
    """Harness-level S8-T4 contract on the Beauty 240d fixture.

    With ``ENGINE_V2_PLAY_LIBRARY_WAVE1`` toggled via env, run
    ``python -m src.main`` end-to-end and assert that:

    1. All 3 wired Tier-B Recommended cards on Beauty fire (the migration
       did not silently break the recommendation pipeline).
    2. ``replenishment_due`` does NOT appear in Recommended (preserved as
       honest-dormant per KI-NEW-G — the play is consumer-dormant on
       Beauty by design because the per-SKU repeat-buyer distribution
       sits below D-S6-4's N>=30 floor).

    This pins both the consult-and-verify wiring (at flag ON, the
    integrity check from plays.assert_identity_with_legacy() must pass
    without raising) and the honest-dormancy contract (the play library
    refactor must not accidentally activate replenishment_due on Beauty).
    """
    engine_run = _run_beauty_harness_with_play_library_flag(play_library_flag)
    cards = _recommended_cards(engine_run)
    play_ids = {str(c.get("play_id")) for c in cards if c.get("play_id")}

    # (1) wired Tier-B Recommended cards still fire.
    missing = _WIRED_TIER_B_RECOMMENDED_ON_BEAUTY - play_ids
    assert not missing, (
        f"S8-T4 harness contract violation: play_library_flag={play_library_flag} "
        f"missing expected wired Tier-B Recommended cards on Beauty: "
        f"{missing}. Got play_ids={sorted(play_ids)}. If the consult-and-verify "
        f"check (plays.assert_identity_with_legacy()) drifted, the engine "
        f"would refuse to start at flag ON; if the underlying audience or "
        f"measurement builder behavior changed, the byte-identical contract "
        f"is broken — STOP and escalate."
    )

    # (2) replenishment_due NOT in Recommended (honest-dormancy preserved).
    assert "replenishment_due" not in play_ids, (
        f"S8-T4 KI-NEW-G regression: play_library_flag={play_library_flag} — "
        f"replenishment_due appeared in Recommended on Beauty. It must "
        f"remain consumer-dormant (cohort_n=0 per D-S6-4 N>=30 floor; "
        f"per-SKU repeat-buyer distribution sits below threshold by "
        f"design). If this fails, the migration accidentally bypassed "
        f"the honest-dormancy gate."
    )


# ---------------------------------------------------------------------------
# Structural callsite pin — Deliverable 3 (DS verdict §Q3 item 3)
# ---------------------------------------------------------------------------


_BUILDER_CALL_NAMES = (
    # Local aliases used inside src/main.py per-builder blocks.
    "_build_prior_anchored",
    "_build_prior_anchored_t3",
    "_build_prior_anchored_t2",
    "_build_prior_anchored_t1",
    "_build_prior_anchored_t3b",
    # Future S8-T2/T3/S13 builders may import under new aliases; include
    # the bare function name too so direct calls (not aliased) are caught.
    "build_prior_anchored_recommendations",
)


def _iter_prior_anchored_callsites(main_text: str):
    """Yield (line_number_1based, snippet) for every callsite that invokes
    one of the prior-anchored builder aliases. Multi-line calls are
    captured up to the matching closing paren.
    """
    lines = main_text.splitlines()
    # Match `<alias>(` but NOT the import line `... as _build_prior_anchored,`
    # (the import has no opening paren immediately after the alias name).
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(n) for n in _BUILDER_CALL_NAMES) + r")\s*\("
    )
    for i, line in enumerate(lines, start=1):
        m = pattern.search(line)
        if m is None:
            continue
        # Skip import statements (defensive — pattern already excludes
        # them because imports use ` as <alias>,` not `<alias>(`).
        stripped = line.lstrip()
        if stripped.startswith(("from ", "import ")):
            continue
        # Capture until balanced paren close.
        depth = 0
        captured: List[str] = []
        for j in range(i - 1, len(lines)):
            captured.append(lines[j])
            for ch in lines[j]:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
            if depth == 0 and len(captured) > 0:
                break
        snippet = "\n".join(captured)
        yield (i, m.group(1), snippet)


def test_every_build_prior_anchored_callsite_threads_cfg_kwarg():
    """Structural pattern-pin: every call to ``build_prior_anchored_recommendations``
    (under any local alias) MUST pass ``cfg=cfg`` (or ``cfg=cfg_local``)
    as a kwarg.

    Rationale (DS verdict 2026-05-24 §Q3 item 3 + §Q5 invariant 16):
    this converts "remember to thread cfg" from tribal knowledge into a
    CI gate. S8-T2 (ENGINE_V2_SENSITIVITY), S8-T3 (ENGINE_V2_PROVENANCE),
    and S13 (ENGINE_V2_ML_AUDIENCE) all add new flag-gated fields on the
    same producer seam; without this pin, each could silently regress
    the wiring the way S8-T1 did.

    **S13.5-T1 (KI-NEW-L collapse, 2026-05-30):** the five legacy
    callsites in ``src/main.py:1604-1898`` have been collapsed into a
    single canonical call inside
    :func:`src.dispatch_prior_anchored.dispatch_prior_anchored_builders`.
    The test now scans ``src/dispatch_prior_anchored.py`` and expects
    exactly **one** callsite (the dispatch loop's single per-iteration
    call). The cfg-threading invariant is unchanged; only the location
    moved. See ``tests/test_s13_5_single_emission_point.py`` for the
    complementary AST pin that ``src/main.py`` itself no longer calls
    :func:`build_prior_anchored_recommendations` directly.
    """
    dispatch_path = REPO_ROOT / "src" / "dispatch_prior_anchored.py"
    text = dispatch_path.read_text(encoding="utf-8")

    callsites = list(_iter_prior_anchored_callsites(text))
    assert callsites, (
        "Structural pin found zero callsites of build_prior_anchored_recommendations "
        "in src/dispatch_prior_anchored.py — either the regex regressed or "
        "the dispatch helper was removed. If removed deliberately, delete "
        "this test."
    )

    # Hard-pin the expected callsite count. Post-S13.5-T1 the dispatch
    # helper makes exactly ONE call per dispatch-table iteration (the
    # iteration runs inside a `for` loop, but the call expression
    # itself appears once in source). Adding a 6th prior-anchored
    # builder = appending a row to the dispatch table; this number
    # stays at 1.
    EXPECTED_CALLSITE_COUNT = 1
    assert len(callsites) == EXPECTED_CALLSITE_COUNT, (
        f"Structural pin expected exactly {EXPECTED_CALLSITE_COUNT} "
        f"callsite of build_prior_anchored_recommendations in "
        f"src/dispatch_prior_anchored.py; got {len(callsites)} at lines "
        f"{[ln for ln, _, _ in callsites]}. If you intentionally added "
        f"a second canonical call, update EXPECTED_CALLSITE_COUNT and "
        f"confirm cfg is threaded on every call."
    )

    failures: List[str] = []
    for line_no, alias, snippet in callsites:
        # Post-S13.5-T1 the dispatch helper threads cfg via a local
        # alias (``cfg_local``) so the helper can normalize ``None``
        # to ``{}`` once at the top. Accept either ``cfg=cfg`` (legacy
        # main.py shape) or ``cfg=cfg_local`` (dispatch helper shape);
        # both satisfy the DS-locked invariant of "cfg threaded on
        # every callsite".
        if "cfg=cfg" not in snippet and "cfg=cfg_local" not in snippet:
            first_lines = "\n    ".join(snippet.splitlines()[:5])
            failures.append(
                f"src/dispatch_prior_anchored.py:{line_no} call to "
                f"{alias}(...) does not thread cfg=cfg / cfg=cfg_local. "
                f"Snippet:\n    {first_lines}\n"
            )

    assert not failures, (
        "S8-T1.6 structural pin violations (cfg=cfg kwarg missing on "
        "build_prior_anchored_recommendations callsites):\n\n"
        + "\n".join(failures)
        + "\nEvery callsite MUST thread cfg= so the producer gate at "
        "src/measurement_builder.py:2428-2430 (and any future flag-gated "
        "fields added under S8-T2 / S8-T3 / S13) is reachable from "
        "src.main.run via the dispatch helper. See DS verdict 2026-05-24 "
        "§Q3 item 3 + S13.5-T1 KI-NEW-L collapse."
    )
