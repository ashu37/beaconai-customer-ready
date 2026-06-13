# S7.6-T2.5-fix — lower D-S6-4 per-SKU floor 30 -> 10 + per-stage profile cell

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `506c703`

---

## 1. Ticket scope

Per DS architect scope card 2026-05-22 (`agent_outputs/ecommerce-ds-architect-t2_5-floor-scope-card-2026-05-22.md`): N=30 per-SKU was imported as a textbook 'median stability' rule of thumb without ICP validation. DS computed <20% of representative small-DTC merchants (~50 SKUs, ~1,200 customers) would clear it. ICP fit requires N=10. This commit lowers the default and adds a per-stage profile-driven resolver, freeing `replenishment_due` (T2 wiring at `b0c9980`) to actually fire on Beauty + Supplements pinned fixtures WHEN the atomic flip ticket flips `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` ON.

This commit is inert at runtime under default flags — builder remains OFF, briefings unchanged. Atomic flip + Beauty/Supplements re-pin remains deferred per Path (c) DS verdict (see `s7_6-t2_5-deferred-summary.md`).

## 2. Files changed

- `src/audience_builders.py` — default 30 -> 10 at line 422; profile-driven resolution mirroring `_default_by_stage` pattern at lines 559-573 (profile cell wins over env override wins over default) (+34 lines).
- `config/gate_calibration.yaml` — new `replenishment_due_per_sku_floor` cell `{startup: 8, growth: 12, mature: 20, enterprise: 30}` (+25 lines).
- `src/profile/types.py` — `GateCalibration` gains optional `replenishment_due_per_sku_floor: Optional[int] = None` (back-compat default; `from_dict` parser updated) (+12 lines).
- `src/profile/builder.py` — new `_resolve_replenishment_due_per_sku_floor` per-stage resolver (mirrors `_resolve_pseudo_n_default` shape) wired into `derive_gate_calibration`; `profile_field_refs` records source (+37 lines).
- `tests/test_s7_6_t2_5_fix_floor.py` (new, 259 lines).
- `tests/test_s6_t3_replenishment_due_builder.py` — T3 below-floor test re-anchored to N=5 (below new N=10 default; was 25 vs old N=30); T13 comment language refresh (+21 lines diff).

## 3. Behavior change

Inert at runtime under default flags (builder still OFF until the deferred atomic flip lands). Resolver precedence: profile cell > env override > default. M0 byte-identical; Beauty sha256 `1a5a35eb67898e6...` unchanged; Supplements sha256 `13a91e6cd320...` unchanged.

## 4. Tests added / modified

New: `tests/test_s7_6_t2_5_fix_floor.py` pins default=10, env-override precedence, profile-cell per-stage values (8/12/20/30), profile-cell > env precedence, `ENGINE_V2_STORE_PROFILE` off path, `GateCalibration` back-compat default None, YAML cell shape.

Modified: `tests/test_s6_t3_replenishment_due_builder.py` (T3 below-floor case re-anchored).

Suite: 1703p baseline -> 1727p / 14s / 4xf / 2xp / 0f.

## 5. Risks + mitigations

- **DS-locked floor change.** Single-source-of-truth scope card cited in commit; founder approved DS recommendation to lower N=30 -> N=10 for ICP fit.
- **Atomic flip itself remains deferred Path (c).** Lowering the floor is necessary but not sufficient; observed-effect gate + priority_prepend infrastructure (landed later in sprint) jointly required for honest placement.

## 6. Follow-ups / known-issues opened

- T2.5 atomic flip still deferred Path (c); KI-NEW-G covers the architectural gap (see existing `s7_6-t2_5-deferred-summary.md`).

## 7. Commit ref

`506c703`
