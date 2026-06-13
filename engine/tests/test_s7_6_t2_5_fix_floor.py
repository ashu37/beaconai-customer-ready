"""Sprint 7.6 Ticket T2.5-fix — per-SKU floor lowered N=30 -> N=10.

Per DS architect scope card 2026-05-22 (agent_outputs/
ecommerce-ds-architect-t2_5-floor-scope-card-2026-05-22.md):

  The legacy default of N=30 at src/audience_builders.py:422 was
  imported as a textbook median-stability rule of thumb without ICP
  validation. <20% of representative small-DTC merchants (~50 SKUs,
  ~1,200 customers) clear N=30 per SKU class. The fix lowers the
  default to N=10 and adds a per-stage profile cell
  ``replenishment_due_per_sku_floor: {startup: 8, growth: 12,
  mature: 20, enterprise: 30}`` at config/gate_calibration.yaml,
  consumed by ``replenishment_due_candidates`` via the same profile
  read pattern as the existing ``_default_by_stage`` audience-floor
  resolution (src/audience_builders.py:559-573).

Resolution order pinned by this test file:

  1. Profile cell (when ``ENGINE_V2_STORE_PROFILE`` is ON and a
     ``_store_profile`` is attached to cfg).
  2. Env override ``MIN_N_REPLENISHMENT_DUE_PER_SKU``.
  3. Default ``10``.

NOTE: ``ENGINE_V2_BUILDER_REPLENISHMENT_DUE`` remains default-OFF;
this fix is shape-only at the audience-builder seam. The atomic flip
(rendering ``replenishment_due`` into pinned briefings) is a
separate ticket (T2.5 atomic flip) that re-pins fixture sha256s.
This file does NOT re-pin pinned briefings.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import audience_builders as ab  # noqa: E402
from src.profile.builder import derive_gate_calibration  # noqa: E402
from src.profile.types import (  # noqa: E402
    BusinessModel,
    BusinessStage,
    CadenceBaseline,
    DataDepth,
    GateCalibration,
    StoreProfile,
    Taxonomy,
)


ANCHOR = pd.Timestamp("2026-05-01 12:00:00")


# ---------------------------------------------------------------------------
# Helpers (mirror the synthetic-row builders in
# test_s6_t3_replenishment_due_builder.py).
# ---------------------------------------------------------------------------


def _row(customer_id: str, days_ago: int, lineitem: str, *, net: float = 30.0):
    return {
        "Name": f"#{customer_id}-{days_ago}",
        "customer_id": str(customer_id),
        "Created at": ANCHOR - pd.Timedelta(days=days_ago),
        "net_sales": net,
        "lineitem_any": lineitem,
    }


def _make_g(rows):
    return (
        pd.DataFrame(rows)
        .sort_values(["customer_id", "Created at"])
        .reset_index(drop=True)
    )


def _beauty_rows(n_customers: int, *, cadence_days: int = 30, last_offset: int = 30):
    rows = [_row("anchor", 0, "Filler item no size token")]
    for i in range(n_customers):
        rows.append(_row(f"c{i}", last_offset + 2 * cadence_days, "Cleanser 50ml"))
        rows.append(_row(f"c{i}", last_offset + cadence_days, "Cleanser 50ml"))
        rows.append(_row(f"c{i}", last_offset, "Cleanser 50ml"))
    return rows


def _make_profile_with_stage(stage: str) -> StoreProfile:
    gate, meas = derive_gate_calibration(
        taxonomy=Taxonomy(
            vertical="beauty", subvertical="skincare",
            vertical_confidence="HIGH", subvertical_confidence="HIGH",
        ),
        stage=BusinessStage(stage=stage, uncertainty="LOW"),
        cadence=CadenceBaseline(detection_status="INSUFFICIENT_DATA"),
        data_depth=DataDepth(),
        business_model=BusinessModel(model="ONE_TIME_LED"),
    )
    return StoreProfile(
        store_id="t2_5_fix",
        taxonomy=Taxonomy(
            vertical="beauty", subvertical="skincare",
            vertical_confidence="HIGH", subvertical_confidence="HIGH",
        ),
        business_stage=BusinessStage(stage=stage, uncertainty="LOW"),
        business_model=BusinessModel(model="ONE_TIME_LED"),
        cadence=CadenceBaseline(detection_status="INSUFFICIENT_DATA"),
        gate_calibration=gate,
        measurement=meas,
    )


# ---------------------------------------------------------------------------
# 1) Default-OFF (no profile, no env) → 12 contributors clear new N=10 floor.
# ---------------------------------------------------------------------------


def test_default_floor_is_n10_twelve_customers_clear():
    rows = _beauty_rows(12, cadence_days=30, last_offset=30)
    g = _make_g(rows)
    cfg = {"VERTICAL_MODE": "beauty"}
    res = ab.replenishment_due_candidates(g, {}, cfg)
    # 12 contributors >= new default N=10 floor; SKU bucket clears,
    # all 12 customers land in the cadence-due window (last_offset == cadence_days).
    assert res.audience_size == 12, (
        f"Expected 12 customers in audience under N=10 default; got "
        f"{res.audience_size}. seg={res.segment_definition!r}"
    )
    assert res.preliminary_rejection_reason is None


def test_default_floor_blocks_below_n10():
    # 5 customers < N=10 default; SKU silently skipped, audience empty.
    rows = _beauty_rows(5, cadence_days=30, last_offset=30)
    g = _make_g(rows)
    res = ab.replenishment_due_candidates(g, {}, {"VERTICAL_MODE": "beauty"})
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# 2) Env override > default. ``MIN_N_REPLENISHMENT_DUE_PER_SKU=20`` blocks
#    a 15-customer cohort even though it would clear the N=10 default.
# ---------------------------------------------------------------------------


def test_env_override_raises_floor_above_default():
    rows = _beauty_rows(15, cadence_days=30, last_offset=30)
    g = _make_g(rows)
    cfg = {
        "VERTICAL_MODE": "beauty",
        "MIN_N_REPLENISHMENT_DUE_PER_SKU": 20,
    }
    res = ab.replenishment_due_candidates(g, {}, cfg)
    # 15 < env-set 20 ⇒ SKU below floor ⇒ zero audience.
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "audience_too_small"
    # The segment-definition mirrors the resolved floor (still appears as
    # 20 in the seg string because env wins over default when profile is off).
    assert "N>=20" in res.segment_definition


# ---------------------------------------------------------------------------
# 3) Profile cell resolves per-stage (8 / 12 / 20 / 30 per YAML).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stage,expected_floor",
    [
        ("STARTUP", 8),
        ("GROWTH", 12),
        ("MATURE", 20),
        ("ENTERPRISE", 30),
    ],
)
def test_profile_cell_resolves_per_stage(stage: str, expected_floor: int):
    prof = _make_profile_with_stage(stage)
    assert prof.gate_calibration.replenishment_due_per_sku_floor == expected_floor
    # Provenance field-ref is recorded so consumers can cite it.
    assert prof.gate_calibration.profile_field_refs.get(
        "replenishment_due_per_sku_floor"
    ) == f"gate_calibration.replenishment_due_per_sku_floor.{stage.lower()}"


def test_profile_cell_wins_over_env_in_audience_builder():
    # Profile=GROWTH (cell=12); env says 30; builder must read 12 (profile
    # wins per documented resolution order). 15 customers >= 12 ⇒ clears;
    # would have FAILED at env=30.
    prof = _make_profile_with_stage("GROWTH")
    rows = _beauty_rows(15, cadence_days=30, last_offset=30)
    g = _make_g(rows)
    cfg = {
        "VERTICAL_MODE": "beauty",
        "ENGINE_V2_STORE_PROFILE": True,
        "_store_profile": prof,
        "MIN_N_REPLENISHMENT_DUE_PER_SKU": 30,
    }
    res = ab.replenishment_due_candidates(g, {}, cfg)
    assert res.audience_size == 15, (
        f"Profile cell (growth=12) MUST win over env=30; expected 15 "
        f"contributors in audience, got {res.audience_size}."
    )
    assert "N>=12" in res.segment_definition


def test_profile_off_falls_back_to_env_or_default():
    # Profile attached but ENGINE_V2_STORE_PROFILE flag OFF ⇒ profile
    # cell is IGNORED, env override wins.
    prof = _make_profile_with_stage("STARTUP")  # cell=8
    rows = _beauty_rows(15, cadence_days=30, last_offset=30)
    g = _make_g(rows)
    cfg = {
        "VERTICAL_MODE": "beauty",
        "ENGINE_V2_STORE_PROFILE": False,
        "_store_profile": prof,
        "MIN_N_REPLENISHMENT_DUE_PER_SKU": 25,
    }
    res = ab.replenishment_due_candidates(g, {}, cfg)
    # 15 < env-25 ⇒ silently skipped, no audience.
    assert res.audience_size == 0
    assert res.preliminary_rejection_reason == "audience_too_small"


# ---------------------------------------------------------------------------
# 4) GateCalibration default field is None (back-compat: pre-T2.5-fix
#    constructions without the new arg still produce a valid object).
# ---------------------------------------------------------------------------


def test_gate_calibration_default_replenishment_field_is_none():
    g = GateCalibration()
    assert g.replenishment_due_per_sku_floor is None


# ---------------------------------------------------------------------------
# 5) YAML cell shape pin — guards against accidental cell removal /
#    rename. The four stage keys must each carry the DS-locked int.
# ---------------------------------------------------------------------------


def test_yaml_cell_shape_pinned():
    from src.profile.builder import load_gate_calibration
    block = load_gate_calibration()
    cell = block.get("replenishment_due_per_sku_floor")
    assert isinstance(cell, dict), (
        "replenishment_due_per_sku_floor cell missing from "
        "config/gate_calibration.yaml"
    )
    assert cell == {
        "startup": 8,
        "growth": 12,
        "mature": 20,
        "enterprise": 30,
    }, cell
