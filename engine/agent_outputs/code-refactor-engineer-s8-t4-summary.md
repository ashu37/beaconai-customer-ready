# S8-T4 — Play Library wave 1: fold winback_dormant_cohort + replenishment_due + discount_dependency_hygiene into plays/<play_id>/ (flag OFF, zero re-pin target)

**Author:** code-refactor-engineer
**Date:** 2026-05-24
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `a9e8bbf`
**Approved ticket:** S8-T4 — Per IM S8 plan Part B S8-T4 + DS verdict 2026-05-24 §3 Q6 wave-1 lock + §5 invariant 13 acceptance criteria. Folder-only refactor; **zero behavior change**; byte-identical contract at BOTH flag states (load-bearing migration-correctness pin). T4.5 atomic flip deferred to separate dispatch.

## 1. Approved scope

S8-T4 Play Library wave 1 — fold `winback_dormant_cohort`, `replenishment_due`, `discount_dependency_hygiene` into `plays/<play_id>/` directory layout. Behind `ENGINE_V2_PLAY_LIBRARY_WAVE1` (default OFF). Folder-only refactor; zero behavior change; byte-identical contract at both flag states.

Including dormant `replenishment_due` is load-bearing per DS Q6 verdict — stress-tests the migration template's dormant-path handling (KI-NEW-G honest-dormancy must be preserved post-migration). Substituting it would leave dormant-path correctness unverified until wave 2.

## 2. Patch summary

- Created `plays/` package with `__init__.py` + `_registry.py` exposing typed `PlayDefinition` + `get_play_definition()` + `assert_identity_with_legacy()`.
- Created 3 wave-1 play subdirectories, each with `__init__.py` + `spec.yaml` + `audience.py` (re-export) + `builder.py` (re-export) + `copy.md` (documentation-only).
- Extended `src/play_registry.py` with `consult_play_library_if_enabled(cfg)` — **pure identity-assertion design**: at flag OFF no-op; at flag ON asserts spec.yaml-resolved callables ARE identity-equal to legacy registry callables (not just equivalent). Guarantees byte-identity by construction.
- Added a single call site in `src/main.py::run` right after `cfg = get_config()`. **No touches to `src/main.py:1380-1597` injection blocks** (KI-NEW-L deferred to S13.5 per DS invariant 11).
- Added `ENGINE_V2_PLAY_LIBRARY_WAVE1` flag default OFF in `src/utils.py`; bool-coerce set updated.
- Added `tests/test_s8_t4_play_library_wave1_migration.py` (19 tests) + new harness parametrize block in `tests/test_v2_harness_cfg_gated_fields.py` (2 tests per DS invariant 16).

## 3. Files changed

- `plays/__init__.py` (new).
- `plays/_registry.py` (new) — `WAVE1_PLAY_IDS` at L29-35.
- `plays/winback_dormant_cohort/{__init__.py, spec.yaml, audience.py, builder.py, copy.md}` (new).
- `plays/replenishment_due/{__init__.py, spec.yaml, audience.py, builder.py, copy.md}` (new) — `spec.yaml:25 honest_dormancy_on_beauty: true` preserved.
- `plays/discount_dependency_hygiene/{__init__.py, spec.yaml, audience.py, builder.py, copy.md}` (new).
- `src/utils.py` — `ENGINE_V2_PLAY_LIBRARY_WAVE1` flag at L796 default OFF + bool-coerce updated.
- `src/play_registry.py` — `consult_play_library_if_enabled` helper.
- `src/main.py` — single new call site after `cfg = get_config()`.
- `tests/test_s8_t4_play_library_wave1_migration.py` — new file (19 tests).
- `tests/test_v2_harness_cfg_gated_fields.py` — new T4 parametrize block (2 tests).

## 4. Tests/checks run

- `tests/test_s8_t4_play_library_wave1_migration.py` — 19/19 passed.
- `tests/test_v2_harness_cfg_gated_fields.py` — 9/9 passed (incl. 2 new T4 parametrized rows at flag OFF + ON; harness invoked `python -m src.main` end-to-end on Beauty 240d at both flag states; ~2:47 wall time).
- `tests/test_slate_regression_beauty_brand.py` + `tests/test_slate_regression_supplements_brand.py` + `tests/test_s7_6_c1_priority_prepend_invariant.py` — pinned slates byte-identical; S7.6 tripwire passes.
- Full suite: **1861 → 1882 passed**, 14 skipped, 4 xfailed, 2 xpassed, 0 failed (+21 = 19 T4 tests + 2 harness parametrize rows).

## 5. Behavior changes

None at default OFF. At flag ON, output is also byte-identical because the consult helper only runs an integrity check (`assert_identity_with_legacy`) verifying spec.yaml-resolved callables are the exact same Python objects as legacy registry's; engine then continues with legacy code path.

## 6. Artifacts added

- spec.yaml shape (example: `plays/winback_dormant_cohort/spec.yaml`):
  ```yaml
  play_id: winback_dormant_cohort
  display_name: "Dormant repeat-buyer winback"
  audience_builder_ref: src.audience_builders.winback_dormant_cohort_candidates
  measurement_builder_ref: src.measurement_builder.build_prior_anchored_play_card
  prior_play_id: winback_21_45
  prior_keys: [base_rate]
  would_be_measured_by: LAPSED_REACTIVATION_IN_30D
  evidence_class_default: directional
  vertical_applicable: [beauty, supplements, mixed]
  ```
- `agent_outputs/code-refactor-engineer-s8-t4-summary.md` (this file; backfilled 2026-05-25).

## 7. Empirical confirmation

- All 3 wired Tier-B Recommended cards (winback_dormant_cohort, discount_dependency_hygiene, cohort_journey_first_to_second) fire on Beauty at both flag OFF and flag ON.
- `replenishment_due` does NOT appear in Recommended at either flag state (KI-NEW-G honest-dormancy preserved).
- Beauty + Supplements pinned slate sha256 unchanged (slate regression tests pass).
- S7.6 CLI fix surfacing intact (tripwire passes).
- S8-T1/T2/T3 behavior unmodified.

## 8. Remaining risks

- **T4.5 atomic flag flip dispatch must keep the zero re-pin target.** If a future patch adds behavior to the consult path (instead of pure validation), the byte-identical contract could break — the current design intentionally restricts consult to identity assertions only.
- **KI-NEW-L deferred to S13.5 per DS verdict;** 5 injection blocks at `src/main.py:1380-1597` remain untouched.
- **Wave 2+ migrations need a similar discipline** (re-export only, identity verification) to preserve zero re-pin.
- **`plays/replenishment_due/spec.yaml` `prior_keys` field** is metadata-only at wave 1 (not consumed by the dispatch); slightly stale post-S6-T3.x re-key but no engine-behavior impact (DS validation 2026-05-25 noted this as a non-blocker wave-2 cleanup).

## 9. Follow-up work

- **S8-T4.5** (separate dispatch): atomic flag flip `ENGINE_V2_PLAY_LIBRARY_WAVE1` default OFF → ON + verify all 5 pinned fixtures still byte-identical (target zero re-pin per IM Part I).
- **S8 close sweep** (orchestrator): bundle T2/T2.5/T3/T3.5/T4/T4.5 into memory.md + ARCHITECTURE_PLAN.md update.

## 10. Verbatim founder ask answers

- **List of files created under `plays/`:** `__init__.py`, `_registry.py`, 3 play subdirs (winback_dormant_cohort, replenishment_due, discount_dependency_hygiene), each with `__init__.py` + `spec.yaml` + `audience.py` + `builder.py` + `copy.md`.
- **spec.yaml shape adopted:** see Section 6 above.
- **`src/play_registry.py` extension shape:** `consult_play_library_if_enabled(cfg)` — pure identity-assertion helper.
- **Flag location + default in `src/utils.py`:** L796 (default `"false"`); bool-coerce set updated.
- **New test file name + count:** `tests/test_s8_t4_play_library_wave1_migration.py` (19 tests).
- **New parametrize row in `tests/test_v2_harness_cfg_gated_fields.py`:** 2 tests (T4 OFF/ON parametrized).
- **Suite count:** 1861 → 1882 (+21).
- **Pinned fixtures byte-identical at BOTH flag states:** confirmed (Beauty `f8676c9f...`, Supplements `13a91e6c...`, M0 3 fixtures).
- **`replenishment_due` zero audience on Beauty at both flag states:** confirmed (KI-NEW-G preserved).
- **S7.6 + S8-T1 + S8-T2 + S8-T3 tests:** all pass unmodified.
- **Commit sha:** `a9e8bbf`.
