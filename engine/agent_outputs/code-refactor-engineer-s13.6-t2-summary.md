# S13.6-T2 — Type 4 `Any` slots on EngineRun + remove `klaviyo_brief_inputs`

**Sprint / ticket:** S13.6-T2 (Phase 2 of the S13.5/S13.6/S13.7 plan; DS R6 schema-authority lock + founder lock-in #6 manual-Klaviyo-only).
**Founder + DS approved:** 2026-05-30 (IM v2.1; DS R6).
**Branch:** `post-6b-restructured-roadmap`.
**Deviation check:** none. T2 stays within IM v2 + DS R6 scope; T1a/T1b strips not re-touched; T3+ scope not touched.

## Patch summary

Two distinct moves, atomic-bundled per Option D playbook:

1. **Type the 3 `Any` slots on `EngineRun`** (the 4th "slot" in the ticket's enumeration is the `klaviyo_brief_inputs` removal, not a typing):
   - `store_profile: Optional[Any]` → `Optional[StoreProfile]`
   - `predictive_models: Dict[str, Any]` → `Dict[str, ModelCard]`
   - `cohort_diagnostics: Dict[str, Any]` → `Dict[str, RetentionCard]`
2. **Remove `PlayCard.klaviyo_brief_inputs` entirely** — field, `to_dict` serialization, `_from_dict_play_card` round-trip, all 3 producer sites, and the test-fixture reference. No flag, no default-empty stub. Per founder lock-in #6: manual Klaviyo upload post-approval per D-5; re-addition post-AWS-migration is out of v1 scope.

Re-exports added at the top of `src/engine_run.py` per **DS R6** (schema authority = `src/engine_run.py`; agents read one file):

```python
from .profile.types import StoreProfile
from .predictive.model_card import ModelCard, ModelFitStatus, RetentionCard
```

`ModelFitStatus` is re-exported alongside `RetentionCard` because the S12-T2 lock has `RetentionCard` re-use the same enum (vocab-stacking Option A per the dataclass docstring).

## Files changed

| Path | + | − | net |
|---|---:|---:|---:|
| `src/engine_run.py` | ~50 | ~5 | +45 |
| `src/measurement_builder.py` | 2 | 2 | 0 |
| `src/engine_run_adapter.py` | 1 | 1 | 0 |
| `tests/test_engine_run_schema.py` | 1 | 1 | 0 |
| `tests/test_s13_renderer_non_consumption.py` | 10 | 0 | +10 |
| **NEW** `tests/test_s13_6_t2_typed_any_slots.py` | 232 | 0 | +232 |
| **NEW** `scripts/s13_6_t2_repin.py` | 75 | 0 | +75 |

## Inventory results (grep audit BEFORE edit)

### `klaviyo_brief_inputs` callsites (all cleaned)

| File | Line | Role |
|---|---:|---|
| `src/engine_run.py` | 907 | PlayCard dataclass field (REMOVED) |
| `src/engine_run.py` | 1633 | `_from_dict_play_card` round-trip kwarg (REMOVED; legacy keys now dropped silently) |
| `src/measurement_builder.py` | 668 | Producer (`build_directional_play_card`) (REMOVED) |
| `src/measurement_builder.py` | 2446 | Producer (`build_prior_anchored_play_card`) (REMOVED) |
| `src/engine_run_adapter.py` | 216 | Producer (`_from_legacy_action`) (REMOVED) |
| `tests/test_engine_run_schema.py` | 129 | Test-fixture kwarg (REMOVED) |

Post-removal grep `grep -rn "klaviyo_brief_inputs" src/` returns only comment breadcrumbs noting the removal.

### Canonical type locations (audited via `grep -rn "class StoreProfile|class ModelCard|class RetentionCard|class ModelFitStatus" src/`)

| Type | Canonical location | Re-export path |
|---|---|---|
| `StoreProfile` | `src/profile/types.py:196` | `from src.engine_run import StoreProfile` |
| `ModelCard` | `src/predictive/model_card.py:99` | `from src.engine_run import ModelCard` |
| `ModelFitStatus` | `src/predictive/model_card.py:79` | `from src.engine_run import ModelFitStatus` |
| `RetentionCard` | `src/predictive/model_card.py:321` | `from src.engine_run import RetentionCard` |

**Surprise flagged (per T1a halt lesson):** the T2 brief speculated `RetentionCard` might live in `src/predictive/retention.py`. It does NOT. Per the S12-T2 lock, `RetentionCard` is defined alongside `ModelCard` inside `src/predictive/model_card.py` (the module docstring explicitly calls out the shared home + the `ModelFitStatus` re-use). `src/predictive/retention.py` holds the substrate `fit_retention` function only. Re-export was authored to the actual canonical location; the inline comment block in `engine_run.py` records the surprise.

### Producer + consumer sites for the 3 typed slots (audited; producers NOT modified beyond comments because typing is annotation-only and producers were already writing the canonical types)

- `store_profile` producer: `src/main.py:967` (`engine_run = _dc_replace_profile(engine_run, store_profile=_profile)` where `_profile = build_store_profile(...)`).
- `predictive_models` producer sites: `src/main.py:999, 1044, 1085, 1153, 1211` (BG/NBD, Gamma-Gamma, survival, CF, RFM substrates each `_dc_replace_*(predictive_models=_pm)`).
- `cohort_diagnostics` producer: `src/main.py:1267` (retention substrate `_dc_replace_ret(cohort_diagnostics=_cd)`).
- All producers already write the canonical typed objects; no producer-site code changes required for the typing.

## Test counts

- Baseline (pre-T2): **2188 collected** / 2171 passed / 9 pre-existing failed / 7 skipped / 6 xfailed.
- Post-T2: **2202 collected** / 2182 passed / 9 pre-existing failed / 7 skipped / 6 xfailed.
- Net: **+14 tests** (11 new in `test_s13_6_t2_typed_any_slots.py`; +3 parametrized cases in `test_s13_renderer_non_consumption.py` for the new `klaviyo_brief_inputs` pattern × 3 renderer modules).

**Pre-existing failures (verified by `git stash` baseline run):**
- 4 in `test_recommended_experiment_forbidden_tokens.py` (T1a fallout — `recommendation_text` strip; out of T2 scope).
- 1 in `test_phase5_considered_always.py::test_abstain_soft_briefing_renders_populated_considered_section` (T1a fallout — `would_fire_if` strip).
- 1 each in `test_s12_t1_rfm_fit.py` / `test_s12_t2_retention_fit.py` (`*_flag_default_off` assertions; pre-T2).
- 2 in `test_s3_memory_event_schemas.py` (pre-T2).
- 1 in `test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock` (clock-drift in fixture vs runner; pre-T2).

All 9 reproduce identically on the `git stash` baseline — none caused by T2.

## `engine_run.json` SHA before / after (5 pinned scenarios)

Computed via the new `scripts/s13_6_t2_repin.py` harness (modeled on T1a/T1b ledgers). Per the T1a caveat carried forward, `engine_run.json` contains wall-clock `fit_timestamp` values from S10–S12 ML ModelCards, so these SHAs record the at-commit moment only; the load-bearing post-T2 gates are the structural strip + AST sweep + dataclass introspection tests, not this ledger.

| Scenario | Post-T2 SHA |
|---|---|
| `healthy_beauty_240d` (beauty) | `35e173bd1bc4a2f656ab73142ad08a21477a8e9988cfc29efa8945d9096c6d4e` |
| `healthy_supplements_240d` (supplements) | `59fb2d070e7818294680e72ca20db065239f9affb590b8c25c056d8b74a67a6a` |
| `small_store_240d` (beauty) | `02a3cd74243c033b797b9c768c123f0c83ad678bd4c7c46b07cff77a8fba40dc` |
| `cold_start_45d` (beauty) | `f03d20887d749123d9b435a610b0dc3486c444c8f2bfc78332d1044c872a912f` |
| `healthy_beauty_low_inventory_240d` (beauty) | `1bbf909e4750908088f4b3ecd84e96c89d0c6bc3f8acd90a77ba8cdad947711a` |

The brief noted the SHA SHOULD change for the `klaviyo_brief_inputs` removal (the empty-dict field disappears from every emitted PlayCard's JSON object). The SHA SHOULD NOT change for the typing alone (annotation-level only; `_to_jsonable` recursion shape preserved). End-to-end the SHAs DO move; the structural strip + AST tests in the new test file are the load-bearing assertions, not a SHA freeze.

## Confirmations

- **4 typed slots verified via `typing.get_type_hints(EngineRun)`** — see `test_s13_6_t2_typed_any_slots.py::test_engine_run_*` (3 assertions; one per slot).
- **`PlayCard.klaviyo_brief_inputs` absent** from:
  - Dataclass fields (`dataclasses.fields(PlayCard)`).
  - `to_dict()` serialization (Beauty-shaped fixture asserted).
  - End-to-end JSON payload (`json.dumps` substring sweep).
  - AST sweep over `src/` (no remaining `klaviyo_brief_inputs=` kwarg call).
  - Grep sweep over `src/` (only comment breadcrumbs remain).
- **Re-export resolves to canonical class identity** — `test_canonical_types_reexported_from_engine_run` asserts `StoreProfile is CanonicalStoreProfile` etc. (object-identity `is`, not just equality).
- **Round-trip rehydrates typed `StoreProfile`** — `test_engine_run_round_trip_rehydrates_typed_store_profile`.
- **Legacy dicts with stale `klaviyo_brief_inputs` round-trip silently** — `test_from_dict_play_card_drops_legacy_klaviyo_brief_inputs_key`.
- **No T1a/T1b-stripped fields re-touched** — verified by `tests/test_s13_renderer_non_consumption.py` (24 → 27 passing tests with the new `klaviyo_brief_inputs` pattern added to the same matrix; T1a prose-field strip tests + T1b Observation.text tests still pass).
- **No T3+ scope touched** — `OpportunityContext`, `FitWarning`, `schema_version`, `MechanismIntent`, RULE A, null-reason registry all untouched.
- **Engine remains runnable** — all 5 pinned synthetic_scenarios fixtures completed via `scripts/s13_6_t2_repin.py` end-to-end with no errors; `engine_run.json` produced for every scenario.

## Risks encountered + mitigations

1. **`RetentionCard` not in `src/predictive/retention.py` (where the brief speculated)** — found instead at `src/predictive/model_card.py:321` per S12-T2 lock. Re-export uses the actual canonical location; the inline comment block in `engine_run.py` records the surprise so future readers can audit.
2. **Circular-import risk on the top-of-file re-export** — mitigated by verifying both `src/profile/types.py` and `src/predictive/model_card.py` carry no `from src.engine_run` import. Smoke-tested with a fresh interpreter (`python -c "from src.engine_run import EngineRun, StoreProfile, ModelCard, RetentionCard, ModelFitStatus"`) and the full test-collect step (2202 tests collected without import error).
3. **`engine_run.json` SHA will move** for the `klaviyo_brief_inputs` field disappearance. Per the T1a/T1b carry-forward caveat (wall-clock `fit_timestamp` already drifts each run), there is no static SHA pin to update; the load-bearing post-T2 gates are the structural strip + AST sweep tests, and the re-pin harness `scripts/s13_6_t2_repin.py` records the at-commit SHAs for forensics.
4. **Pre-existing test failures not addressed** (9 unrelated failures from T1a fallout + S12 flag-default + memory-event schemas + clock-drift fixture). All verified pre-existing on the `git stash` baseline; out of T2 scope per the "no silent scope expansion" mandate.

## Re-pin harness (NEW)

`scripts/s13_6_t2_repin.py` (75 lines) — clone of `scripts/s13_6_t1b_repin.py`, computes post-T2 engine_run.json SHAs across the 5 pinned synthetic_scenarios.yaml fixtures. Same wall-clock `fit_timestamp` caveat carried forward from T1a / T1b / S13-T3.5.

## Follow-up work / dependencies

- **S13.6-T3** — `NonLiftAtom` typed slot (next ticket in IM Phase 2).
- **S13.6-T4** — `FitWarning` typing.
- **S13.6-T5** — `schema_version` bump to `2.0.0` + CHANGELOG (will need to record the `klaviyo_brief_inputs` removal as a breaking schema delta, plus the three Any→typed promotions).
- **S13.6-T6** — `MechanismIntent`.
- **S13.6-T7 / T7.5** — RULE A null_reason patterns + null-reason registry.
- **S13.6-T8** — sprint-close (STATE / PIVOTS / ROADMAP / INDEX / DECISIONS / KIs).
- **Out of v1 scope (post-AWS-migration):** re-introduce a typed Klaviyo payload field if needed for the Klaviyo agent. Per founder lock-in #6 this requires explicit founder + DS sign-off documented in PIVOTS.md before any re-addition.

**DS R6 satisfied:** agents now read one file (`src/engine_run.py`) for `EngineRun`, `PlayCard`, `StoreProfile`, `ModelCard`, `ModelFitStatus`, and `RetentionCard`. The schema-authority single-file invariant is in place for the three typed contract surfaces.
