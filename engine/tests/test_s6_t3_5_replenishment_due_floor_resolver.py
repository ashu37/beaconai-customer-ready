"""S6-T3.5 Commit B — ``replenishment_due`` audience-floor resolver tests.

Pins the DS-locked floor grid for ``replenishment_due``:

    | stage      | beauty subverticals | mixed_beauty |
    |------------|---------------------|--------------|
    | startup    |                  60 |           90 |
    | growth     |                 150 |          225 |
    | mature     |                 350 |          525 |
    | enterprise |                1000 |         1500 |

    supplements: NO cell (resolver returns None, NOT zero, NOT default).

Asymmetric posture per ``D-FLOOR-replenishment_due`` (LOCKED 2026-05-19)
and aligned with ``D-PRIORS-replenishment_due_supplements_deferred``.

The strict resolver (``_resolve_audience_floor_cell_strict``) MUST NOT
cascade to ``_default_by_stage`` — that would silently mask the
"no cell" signal at the consumer.
"""

from __future__ import annotations

from typing import List, Optional

import pytest

from src.profile.builder import (
    _resolve_audience_floor_cell_strict,
    load_gate_calibration,
)


@pytest.fixture(scope="module")
def yaml_block() -> dict:
    return load_gate_calibration()


# ---------------------------------------------------------------------------
# Beauty subverticals: 4 stages × 4 subverticals = 16 cells, all populated
# ---------------------------------------------------------------------------

BEAUTY_SUBVERTICALS = ["skincare", "cosmetics", "haircare", "personal_care"]
EXPECTED_BEAUTY_FLOOR_BY_STAGE = {
    "STARTUP": 60,
    "GROWTH": 150,
    "MATURE": 350,
    "ENTERPRISE": 1000,
}


@pytest.mark.parametrize("subvertical", BEAUTY_SUBVERTICALS)
@pytest.mark.parametrize("stage,expected", sorted(EXPECTED_BEAUTY_FLOOR_BY_STAGE.items()))
def test_beauty_subvertical_floor(
    yaml_block, subvertical: str, stage: str, expected: int
) -> None:
    rules_fired: List[dict] = []
    floor, source = _resolve_audience_floor_cell_strict(
        yaml_block,
        play_id="replenishment_due",
        vertical="beauty",
        subvertical=subvertical,
        stage=stage,
        rules_fired=rules_fired,
    )
    assert floor == expected, (
        f"replenishment_due beauty/{subvertical}/{stage.lower()}: "
        f"expected {expected}, got {floor}"
    )
    assert source == (
        f"gate_calibration.audience_floors.replenishment_due.beauty."
        f"{subvertical}.{stage.lower()}"
    )


# ---------------------------------------------------------------------------
# mixed_beauty (REFUSED subvertical): 1.5× per-stage grid
# ---------------------------------------------------------------------------

EXPECTED_MIXED_BEAUTY_FLOOR_BY_STAGE = {
    "STARTUP": 90,
    "GROWTH": 225,
    "MATURE": 525,
    "ENTERPRISE": 1500,
}


@pytest.mark.parametrize(
    "stage,expected", sorted(EXPECTED_MIXED_BEAUTY_FLOOR_BY_STAGE.items())
)
def test_mixed_beauty_floor(yaml_block, stage: str, expected: int) -> None:
    rules_fired: List[dict] = []
    floor, source = _resolve_audience_floor_cell_strict(
        yaml_block,
        play_id="replenishment_due",
        vertical="beauty",
        subvertical="mixed",
        stage=stage,
        rules_fired=rules_fired,
    )
    assert floor == expected, (
        f"replenishment_due mixed_beauty/{stage.lower()}: "
        f"expected {expected}, got {floor}"
    )
    assert source == (
        f"gate_calibration.audience_floors.replenishment_due."
        f"mixed_beauty.{stage.lower()}"
    )
    # mixed_<vertical> fallback rule fires.
    assert any(
        r.get("rule") == "gate_calibration_mixed_vertical_fallback"
        and r.get("play_id") == "replenishment_due"
        for r in rules_fired
    )


# ---------------------------------------------------------------------------
# Supplements (all subverticals × all stages): resolver returns None
# ---------------------------------------------------------------------------

SUPPLEMENTS_SUBVERTICALS = [
    "protein",
    "multivitamin",
    "probiotics",
    "nootropics",
    "functional",
]


@pytest.mark.parametrize("subvertical", SUPPLEMENTS_SUBVERTICALS)
@pytest.mark.parametrize("stage", ["STARTUP", "GROWTH", "MATURE", "ENTERPRISE"])
def test_supplements_returns_none_not_zero(
    yaml_block, subvertical: str, stage: str
) -> None:
    rules_fired: List[dict] = []
    floor, source = _resolve_audience_floor_cell_strict(
        yaml_block,
        play_id="replenishment_due",
        vertical="supplements",
        subvertical=subvertical,
        stage=stage,
        rules_fired=rules_fired,
    )
    assert floor is None, (
        f"replenishment_due supplements/{subvertical}/{stage.lower()}: "
        f"strict resolver MUST return None (no cell), got {floor!r}. "
        f"A silently-applied default would mask the asymmetric posture "
        f"(D-FLOOR-replenishment_due + D-PRIORS-replenishment_due_supplements_deferred)."
    )
    assert source is None
    assert floor != 0, "None and 0 are NOT the same — see test name"
    # cell-missing-strict rule fires (auditable).
    assert any(
        r.get("rule") == "gate_calibration_cell_missing_strict"
        and r.get("play_id") == "replenishment_due"
        and r.get("vertical") == "supplements"
        for r in rules_fired
    )


# ---------------------------------------------------------------------------
# Integration: derive_gate_calibration omits the key for supplements,
# includes it for beauty.
# ---------------------------------------------------------------------------


def test_builder_includes_replenishment_due_for_beauty() -> None:
    from src.profile.types import (
        BusinessModel,
        BusinessStage,
        CadenceBaseline,
        DataDepth,
        Taxonomy,
    )
    from src.profile.builder import derive_gate_calibration

    gate, _ = derive_gate_calibration(
        taxonomy=Taxonomy(vertical="beauty", subvertical="skincare"),
        stage=BusinessStage(stage="GROWTH", uncertainty="LOW"),
        cadence=CadenceBaseline(),
        data_depth=DataDepth(),
        business_model=BusinessModel(model="ONE_TIME_LED"),
    )
    assert gate.audience_floor_by_play_id.get("replenishment_due") == 150


def test_builder_omits_replenishment_due_for_supplements() -> None:
    from src.profile.types import (
        BusinessModel,
        BusinessStage,
        CadenceBaseline,
        DataDepth,
        Taxonomy,
    )
    from src.profile.builder import derive_gate_calibration

    gate, _ = derive_gate_calibration(
        taxonomy=Taxonomy(vertical="supplements", subvertical="protein"),
        stage=BusinessStage(stage="GROWTH", uncertainty="LOW"),
        cadence=CadenceBaseline(),
        data_depth=DataDepth(),
        business_model=BusinessModel(model="ONE_TIME_LED"),
    )
    assert "replenishment_due" not in gate.audience_floor_by_play_id, (
        "Supplements MUST NOT receive a replenishment_due floor via "
        "_default_by_stage cascade. The asymmetric posture (no cell) "
        "must surface as a missing key, not a silently-applied default."
    )
