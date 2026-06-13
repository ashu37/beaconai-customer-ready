"""S7 priors-wiring — load-bearing enum/metadata cross-pin test.

The S6-T3.5 latent-enum bug (``CADENCE_DUE_REPEAT_BUYER`` authored in
``config/priors.yaml`` at S6-T3.x but missing from
``src.priors_loader.AudienceArchetype`` until T3.5 Prereq 1) is the
load-bearing precedent for this test. ``storytelling_v2`` +
``decide.py`` both lazy-import + swallow ``PriorsMetadataError``
silently, so a YAML/enum drift symptom is "merchant-facing mechanism
line never renders" — defeats the activation moment without raising.

This test pins the cross-link in both directions for EVERY priors block
that uses the Phase 6A dict form (``metadata:`` + ``priors:``):

  - every ``metadata.audience_archetype`` value MUST resolve to a
    defined :class:`src.priors_loader.AudienceArchetype` enum member
  - every ``metadata.would_be_measured_by`` value MUST resolve to a
    defined :class:`src.engine_run.WouldBeMeasuredBy` enum member

The test is scoped to dict-form blocks (the only blocks that can
author a ``metadata`` block today). Legacy list-form blocks are
untouched.

See:
  - ``memory.md`` — S7 priors-wiring (2026-05-20)
  - ``memory.md`` — S6-T3.5 latent ``CADENCE_DUE_REPEAT_BUYER`` fix
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

yaml = pytest.importorskip("yaml")

from src.engine_run import WouldBeMeasuredBy
from src.priors_loader import AudienceArchetype


PRIORS_YAML_PATH = REPO_ROOT / "config" / "priors.yaml"


def _iter_dict_form_metadata():
    """Yield ``(play_id, metadata_dict)`` for every priors block that
    uses the Phase 6A dict form (``{metadata: ..., priors: [...]}``)."""

    doc = yaml.safe_load(PRIORS_YAML_PATH.read_text())
    plays = doc.get("plays") or {}
    for play_id, block in plays.items():
        if isinstance(block, dict) and isinstance(block.get("metadata"), dict):
            yield play_id, block["metadata"]


def test_priors_yaml_has_dict_form_blocks_to_check():
    """Guard: the cross-pin test only protects what it can find. If a
    refactor accidentally demotes every dict-form block to legacy list
    form (or moves the metadata block elsewhere), the test loop below
    would silently pass — surface that.
    """

    blocks = list(_iter_dict_form_metadata())
    # Sprint 6/7 dict-form blocks expected: bestseller_amplify,
    # discount_hygiene, routine_builder, first_to_second_purchase,
    # replenishment_due, discount_dependency_hygiene (S7),
    # aov_lift_via_threshold_bundle (S7). The lower bound is permissive
    # so future additions don't break the guard; the lower bound only
    # catches accidental wholesale removal.
    assert len(blocks) >= 5, (
        f"expected at least 5 dict-form priors blocks; found {len(blocks)}: "
        f"{[p for p, _ in blocks]}"
    )


def test_every_audience_archetype_resolves_to_enum_member():
    """Cross-pin: YAML metadata -> AudienceArchetype enum."""

    valid = {m.value for m in AudienceArchetype}
    offenders: list[tuple[str, str]] = []
    for play_id, metadata in _iter_dict_form_metadata():
        archetype = metadata.get("audience_archetype")
        if archetype is None:
            offenders.append((play_id, "<missing audience_archetype>"))
            continue
        if archetype not in valid:
            offenders.append((play_id, str(archetype)))
    assert not offenders, (
        f"{len(offenders)} priors blocks carry an audience_archetype value "
        f"not present in AudienceArchetype enum: {offenders}. "
        f"Valid enum values: {sorted(valid)}. This is the same failure "
        f"mode as the S6-T3.5 latent CADENCE_DUE_REPEAT_BUYER bug."
    )


def test_every_would_be_measured_by_resolves_to_enum_member():
    """Cross-pin: YAML metadata -> WouldBeMeasuredBy enum."""

    valid = {m.value for m in WouldBeMeasuredBy}
    offenders: list[tuple[str, str]] = []
    for play_id, metadata in _iter_dict_form_metadata():
        wbm = metadata.get("would_be_measured_by")
        if wbm is None:
            offenders.append((play_id, "<missing would_be_measured_by>"))
            continue
        if wbm not in valid:
            offenders.append((play_id, str(wbm)))
    assert not offenders, (
        f"{len(offenders)} priors blocks carry a would_be_measured_by value "
        f"not present in WouldBeMeasuredBy enum: {offenders}. "
        f"Valid enum values: {sorted(valid)}."
    )


def test_s7_priors_blocks_present_and_enum_members_defined():
    """Explicit pins on the S7 priors-wiring additions.

    Catches a future drift that would (a) remove the S7 priors blocks,
    (b) demote them to legacy list form, or (c) remove the matching
    enum members.
    """

    by_play = {p: m for p, m in _iter_dict_form_metadata()}

    assert "discount_dependency_hygiene" in by_play, (
        "S7 priors-wiring discount_dependency_hygiene block missing or "
        "not in dict form"
    )
    md = by_play["discount_dependency_hygiene"]
    assert md["audience_archetype"] == "DISCOUNT_CONDITIONED_REPEAT_BUYER"
    assert md["would_be_measured_by"] == (
        "DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D"
    )
    assert (
        AudienceArchetype("DISCOUNT_CONDITIONED_REPEAT_BUYER")
        is AudienceArchetype.DISCOUNT_CONDITIONED_REPEAT_BUYER
    )
    assert (
        WouldBeMeasuredBy(
            "DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D"
        )
        is WouldBeMeasuredBy.DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D
    )

    assert "aov_lift_via_threshold_bundle" in by_play, (
        "S7 priors-wiring aov_lift_via_threshold_bundle block missing or "
        "not in dict form"
    )
    md = by_play["aov_lift_via_threshold_bundle"]
    assert md["audience_archetype"] == "THRESHOLD_NEAR_BUYER"
    assert md["would_be_measured_by"] == "AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D"
    assert (
        AudienceArchetype("THRESHOLD_NEAR_BUYER")
        is AudienceArchetype.THRESHOLD_NEAR_BUYER
    )
    assert (
        WouldBeMeasuredBy("AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D")
        is WouldBeMeasuredBy.AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D
    )


def test_enum_round_trip_for_new_s7_members():
    """A2-style round-trip: enum string equals enum member name + value
    (UPPER_SNAKE_CASE convention pinned for the S7 additions)."""

    new_archetypes = (
        AudienceArchetype.DISCOUNT_CONDITIONED_REPEAT_BUYER,
        AudienceArchetype.THRESHOLD_NEAR_BUYER,
    )
    for m in new_archetypes:
        assert m.value == m.name
        assert AudienceArchetype(m.value) is m

    new_wbm = (
        WouldBeMeasuredBy.DISCOUNT_DEPENDENCY_HYGIENE_FULL_PRICE_CONVERSION_IN_14D,
        WouldBeMeasuredBy.AOV_THRESHOLD_CROSSING_CONVERSION_IN_14D,
    )
    for m in new_wbm:
        assert m.value == m.name
        assert WouldBeMeasuredBy(m.value) is m
