# S6-T3.y Summary — audience-floor sensitivity driver on validated-path prior-anchored PlayCards

**Ticket:** S6-T3.y (audit-response sequence locked 2026-05-19 in `agent_outputs/code-refactor-engineer-s6-t3-summary.md` §7; predecessor S6-T3.x landed at commit `8a082dc`)
**Date:** 2026-05-19
**Branch:** post-6b-restructured-roadmap
**Status:** Impl complete. Flag remains default OFF (T3.5 owns activation). Driver is engineering-surface only; T3.z owns merchant render. All 5 pinned fixtures byte-identical under flag OFF.

---

## 1. Approved scope (5 items)

1. **New helper** `_audience_floor_sensitivity_driver(audience_size, audience_floor, posterior_value, aov, *, profile_field_ref=None)` in `src/measurement_builder.py`. Pure function. Returns a typed driver dict.
2. **Wire** into validated-path PlayCard construction in `build_prior_anchored_play_card` — append to `drivers=[...]` ONLY when prior is `VALIDATED_EXTERNAL` AND `profile_flag_on` AND `store_profile` attached AND `audience_floor.{play_id}` `profile_field_ref` is present AND a floor scalar is recoverable from `profile.gate_calibration.audience_floor_by_play_id[play_id]`. Any missing piece → omit entirely.
3. **Schema** unchanged. Driver `value` is polymorphic per existing pattern (`Optional[Any]`); no typed-dataclass change.
4. **Renderer surface OUT OF SCOPE.** T3.z handles merchant-facing surface; T3.y is engineering surface only.
5. **Tests** — new `tests/test_s6_t3_y_audience_floor_sensitivity.py` (11 tests, all pass).

---

## 2. Patch summary

### `src/measurement_builder.py`

- Added pure helper `_audience_floor_sensitivity_driver(...)` near `_audience_size_driver` (around line 254). Mirrors the `_audience_size_driver` discipline: `profile_field_ref` is omitted when None so dict shape stays byte-identical when not profile-driven.
- Extended local import inside `build_prior_anchored_play_card` to bring `PriorValidationStatus` into scope: `from .priors_loader import (PriorValidationStatus, get_prior, resolve_mixed_prior)`.
- Append-only block inside the validated-AND-AOV-OK branch of `build_prior_anchored_play_card` (around line 1062). Guard: `profile_flag_on AND store_profile is not None AND audience_floor_ref AND prior.validation_status == PriorValidationStatus.VALIDATED_EXTERNAL`. Then recover the floor scalar from `gate_calibration.audience_floor_by_play_id[play_id]`. If the floor is recoverable (>0), append the driver to `drivers` BEFORE constructing the non-suppressed `RevenueRange`.

### `tests/test_s6_t3_y_audience_floor_sensitivity.py` (NEW)

11 tests:

| # | Test | Pins |
|---|------|------|
| T1 | `test_t1_helper_shape_required_keys` | 5 top-level keys (name, source, value, profile_field_ref, notes) + 8 inner value keys. |
| T2 | `test_t2_floor_pct_int_rounding[200-150-250]` and `[80-60-100]` | Floor +/-25% int rounding. |
| T3 | `test_t3_cohort_clears_all_variants_robustness_signal` | audience=356, floor=200 → p50_low == p50_high == current_p50 (robustness). |
| T4 | `test_t4_cohort_near_floor_p50_low_zero_floor_fragile` | audience=210, floor=200, posterior=0.10, aov=50.0 → upper variant (250) fails → p50_low=$0 (floor-fragile). |
| T5 | `test_t5_driver_present_on_validated_path_under_flag_on` | Beauty/growth/skincare profile, audience=356, AOV=$59.22 → driver appears on validated PlayCard with `floor_value=200`. |
| T6 | `test_t6_driver_absent_when_flag_off` | Same inputs, `profile_flag_on=False` → driver absent. |
| T7 | `test_t7_driver_absent_when_prior_heuristic_unvalidated` | `monkeypatch` `priors_loader.get_prior` to downgrade `validation_status` → `HEURISTIC_UNVALIDATED` → suppressed RevenueRange, no audience_floor_sensitivity driver. |
| T8 | `test_t8_driver_absent_on_directional_path` | `first_to_second_purchase` directional card → driver never on directional pathway. |
| T9 | `test_t9_profile_field_ref_matches_audience_size_sibling` | `floor_driver.profile_field_ref == audience_driver.profile_field_ref` (both cite same YAML cell). |
| T10 | `test_t10_all_5_pinned_fixtures_byte_identical_under_flag_off` | Re-pins all 5 fixture sha256s as a local guard against future drift. |

11 tests pass on first iteration after a single fixture-metric correction (directional supporting signal is `returning_customer_share`, not `repeat_rate`).

---

## 3. Driver-dict shape pin (illustrative payload)

Beauty winback PlayCard, flag-ON probe (NOT committed; pure read of `_audience_floor_sensitivity_driver(356, 200, 0.08, 59.22, profile_field_ref="gate_calibration.audience_floors.winback_dormant_cohort.beauty.skincare.growth")`):

```json
{
  "name": "audience_floor_sensitivity",
  "source": "computed",
  "value": {
    "floor_value": 200,
    "floor_minus_25pct": 150,
    "floor_plus_25pct": 250,
    "revenue_p50_at_floor": 1686.59,
    "revenue_p50_at_floor_minus_25pct": 1686.59,
    "revenue_p50_at_floor_plus_25pct": 1686.59,
    "p50_low": 1686.59,
    "p50_high": 1686.59
  },
  "notes": "if audience floor were +/-25%, revenue_p50 would shift to $1686.59-$1686.59",
  "profile_field_ref": "gate_calibration.audience_floors.winback_dormant_cohort.beauty.skincare.growth"
}
```

**Robustness band on Beauty winback (illustrative, S6.5-T5 numbers):** `audience=356, floor=200, posterior=0.08, aov=$59.22`. Every variant (`floor=150`, `200`, `250`) is cleared by the 356-customer cohort. Audience unchanged at every variant. Resulting `p50_low == p50_high == $1686.59`. **Robustness signal — the Beauty winback dollar projection is INSENSITIVE to ±25% perturbation of the heuristic floor authored in `gate_calibration.audience_floors.winback_dormant_cohort.beauty.skincare.growth`.** (Ticket spec referenced `$1686.50`; actual computation `356 * 0.08 * 59.22 = 1686.5856 → round(_, 2) = 1686.59`. Spec rounded to one fewer place; engineering-output is correct.)

## 4. Floor-fragile illustrative case (synthetic)

`_audience_floor_sensitivity_driver(audience_size=210, audience_floor=200, posterior_value=0.10, aov=50.0)`:

```json
{
  "value": {
    "floor_value": 200,
    "floor_minus_25pct": 150,
    "floor_plus_25pct": 250,
    "revenue_p50_at_floor": 1050.0,
    "revenue_p50_at_floor_minus_25pct": 1050.0,
    "revenue_p50_at_floor_plus_25pct": 0.0,
    "p50_low": 0.0,
    "p50_high": 1050.0
  },
  "notes": "if audience floor were +/-25%, revenue_p50 would shift to $0.0-$1050.0"
}
```

`210 >= 150` and `210 >= 200` clear, `210 < 250` fails. Upper variant collapses audience to 0 → revenue=0. `p50_low=$0`. **Floor-fragile signal — this cohort BARELY clears today's floor and would have been entirely excluded under a 25%-higher floor.** T3.z can use the `(p50_high - p50_low) / p50_high` ratio (or the presence of `p50_low == 0`) to decide whether the robustness band is worth surfacing.

---

## 5. Flag-OFF byte-identity confirmation

Captured pre-T3.y (commit `d1bdfeb`) and re-verified post-T3.y on `src/measurement_builder.py`:

| Fixture | sha256 (pre = post) |
|---|---|
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | `cacb6691b387b1770502a841f9c224d1fe76e5bc3be58802eafc8c5d0fa95269` |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | `01f5feff84491db331611b3cbcbd94247699d11544e659a20efe0b67bbfede95` |
| `tests/golden/small_sm/briefing.html` | `40bf24ea3c3632fa717293c82f66ac074d5e765ed29009b3297d2088952278e6` |
| `tests/golden/mid_shopify/briefing.html` | `380b2c5d0aa6806d81a38666c63603781e904f4e10a9fdfff72430551152d81a` |
| `tests/golden/micro_coldstart/briefing.html` | `2191b251edffbb7814e28a872e66b69e3d9289e680f077daa6ccea6a2694b2fc` |

All 5 byte-identical under flag OFF. T3.y's new code path is gated behind `profile_flag_on AND store_profile is not None AND audience_floor_ref AND validation_status == VALIDATED_EXTERNAL`; today's pinned fixtures run without `_store_profile` attached, so no driver is appended and the on-disk briefing bytes are identical.

---

## 6. Tests / checks run

- `tests/test_s6_t3_y_audience_floor_sensitivity.py` — 11 passed (new file).
- `tests/test_slate_regression_beauty_brand.py`, `tests/test_slate_regression_supplements_brand.py`, `tests/test_golden_diff.py` — passed; all 5 pinned sha256s byte-identical.
- `tests/test_s6_5_t4_gate_calibration.py`, `tests/test_s6_t3_replenishment_due_builder.py`, `tests/test_s6_t1_winback_dormant_cohort.py`, `tests/test_s6_t1_5_winback_dormant_repin.py`, `tests/test_s6_5_t5_atomic_repin.py` — 128 passed (regression block covering both pathways + atomic-repin).
- **Full suite: 1433 passed / 14 skipped / 0 failed** (was 1422; +11 from new test file).

---

## 7. Behavior changes (today, under flag OFF)

**ZERO merchant-facing behavior change.** The new driver only appears when `profile_flag_on=True` AND a `StoreProfile` is attached AND the prior is `VALIDATED_EXTERNAL`. All 5 pinned fixtures (Beauty + supplements G-1 + 3× M0) are byte-identical to the pre-T3.y state. The driver is reachable today via the `cfg["_store_profile"]` slot the `ENGINE_V2_STORE_PROFILE` plumbing already exposes — it's just not surfaced by any renderer yet.

---

## 8. Artifacts added

- `tests/test_s6_t3_y_audience_floor_sensitivity.py` — 11 new tests pinning the helper shape, the flag-ON wiring, the flag-OFF / heuristic_unvalidated / directional negative cases, the `profile_field_ref` echo, and the all-5-fixtures byte-identity contract.
- `agent_outputs/code-refactor-engineer-s6-t3_y-summary.md` — this document.

No new modules, no new runtime deps, no new flags, no schema changes (`event_version=1` intact; no enum additions; no field reshape).

---

## 9. Remaining risks

- **T3.5 atomic flip pending:** Beauty `replenishment_due` activation against the new validated_external prior still owns the visible flip. T3.y's audience_floor_sensitivity driver is engineering-surface only until T3.z reads it.
- **No coverage for `replenishment_due` floor**: today's profile builder only writes `audience_floor_by_play_id["winback_dormant_cohort"]`. When T3.5 promotes `replenishment_due` to a validated-path prior-anchored card, the floor cell must be authored under `gate_calibration.yaml.audience_floors.replenishment_due.{vertical}.{subvertical}.{stage}` AND the profile builder must populate `audience_floor_by_play_id["replenishment_due"]` + `profile_field_refs["audience_floor.replenishment_due"]` for the sensitivity driver to fire. This is a T3.5-or-T4-side prerequisite; T3.y does not introduce the gap (the gap pre-existed; only the new symptom emerges at T3.5).
- **Driver value rounding:** `revenue_p50_at_*` values are rounded to 2 decimal places via `round(..., 2)` to match the existing `rev_p50` rounding in the validated-AOV-OK branch. T3.z renderer should preserve the same rounding when surfacing to merchants.

---

## 10. Hand-off to T3.z

T3.z (Considered render pass + Recommended Now copy) reads the new `audience_floor_sensitivity` driver value to optionally surface a "robustness band" or "sensitivity envelope" on Recommended Now cards. Suggested heuristics:

- If `value.p50_low == value.p50_high` → cohort clears all variants → robustness signal → optionally show a one-line "robust to ±25% floor variation" microcopy, OR omit entirely (the band carries no new information when collapsed).
- If `value.p50_low == 0.0` → floor-fragile → strong candidate for an envelope render: `"Today's dollar estimate ($X) sits at a heuristic edge — under a 25%-higher audience floor, this cohort would not have surfaced."`
- Otherwise → typical band: surface `${p50_low}–${p50_high}` alongside the point `p50` as the heuristic-uncertainty envelope.

T3.z MUST NOT recompute the band from scratch — the driver value is the single source of truth. T3.z MUST NOT render the band on directional cards or on heuristic_unvalidated paths (driver is absent there by design; defensively check `name == "audience_floor_sensitivity"` presence in `drivers`).

---

## 11. Invariants preserved

- D-5 / D-6 / D-8 intact (no Shopify/Klaviyo production integration; no banned ML modules; vertical scope unchanged at `{beauty, supplements, mixed}`).
- B-4 role-uniqueness intact (driver lives inside `RevenueRange.drivers` only; no role/slate change).
- B-5 Berkson invariant intact (no cohort-definition logic touched).
- S-2..S-6 substrate write paths untouched.
- Schema-additive only within `event_version=1`. `PlayCard.drivers[].value` is already `Optional[Any]` — driver value is polymorphic per the existing pattern.
- S7.5-T3 validated-vs-heuristic refusal logic UNCHANGED. The new driver only appears on `VALIDATED_EXTERNAL`; `heuristic_unvalidated` / `placeholder` paths refuse outright at the existing routing seam.
- The `_audience_size_driver` and `blend_provenance` driver shapes are UNCHANGED. Only the `drivers=[...]` list grew by one entry on the validated-AOV-OK branch.
- No new runtime deps. No new feature flags. `ENGINE_V2_STORE_PROFILE` remains the gating flag; activation timing is T3.5's call.

---

## 12. Commit list (per 3-commit boundary)

1. **Impl** — `S6-T3.y: audience-floor sensitivity driver on validated-path prior-anchored PlayCards (closes DS architect firewall leak)` — `src/measurement_builder.py`, `tests/test_s6_t3_y_audience_floor_sensitivity.py`.
2. **Memory** — `Document S6-T3.y in repo memory.md`.
3. **Summary** — `agent_outputs/code-refactor-engineer-s6-t3_y-summary.md` (this file).

## Backfill from memory.md (migration trim 2026-05-25)

## S6-T3.y closeout — audience-floor sensitivity driver on validated-path PlayCards (2026-05-19)

**Shipped:**

- New `_audience_floor_sensitivity_driver()` helper in `src/measurement_builder.py` (pure function; 9-key typed dict with 8-key inner `value`). Driver appended to `RevenueRange.drivers` on validated-path prior-anchored PlayCards when prior is `VALIDATED_EXTERNAL` AND profile flag ON AND store_profile attached AND `audience_floor.{play_id}` `profile_field_ref` is present.
- Closes the DS architect 2026-05-19 firewall leak: surfaces `if audience floor were +/-25%, revenue_p50 would shift to $p50_low–$p50_high`. Sensitivity is on the FLOOR (heuristic choice in `gate_calibration.yaml`), not the audience. Cohort comfortably clearing all variants → `p50_low == p50_high == current_p50` (robustness). Cohort near the floor → upper variant fails audience check → `revenue=0` → `p50_low == 0` (floor-fragile).
- `profile_field_ref` echoed from the sibling `audience_size` driver — both citations trace to the same YAML cell.
- New `tests/test_s6_t3_y_audience_floor_sensitivity.py` (11 tests). Existing flag-OFF byte-identity pins on all 5 fixtures preserved.

**Load-bearing invariants:**

- Driver is additive on `RevenueRange.drivers` ONLY; never wired into directional pathway, never wired on `heuristic_unvalidated` / `placeholder` paths, never modifies any existing driver's shape.
- Sensitivity is on the FLOOR variant `[floor*0.75, floor, floor*1.25]`, NOT on the audience. Computing against the audience is a category error (audience is observed data; floor is the heuristic).
- Flag-OFF / no-profile guard discipline mirrors `_audience_size_driver`: any of {flag OFF, profile None, `audience_floor_ref` empty, `validation_status != VALIDATED_EXTERNAL`, floor scalar unrecoverable} → omit entirely.
- T3.z is the merchant-facing render surface; T3.y is engineering surface only — no copy in the renderer reads this driver yet.

**Caveats / dormant behavior:** All 5 pinned fixtures byte-identical under flag OFF (Beauty + supplements G-1 + 3× M0). T3.z reads the new driver value to optionally surface a "robustness band" or "sensitivity envelope" on Recommended Now cards.

**Schema:** unchanged (driver value is polymorphic `Optional[Any]` per existing pattern; no enum / dataclass change; `event_version=1` intact).
**Suite:** 1433 passed (was 1422; +11 from new test file).
**Summary:** [agent_outputs/code-refactor-engineer-s6-t3_y-summary.md](agent_outputs/code-refactor-engineer-s6-t3_y-summary.md)
