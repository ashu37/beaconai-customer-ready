# Code Refactor Engineer — S13.7-T7b Summary

**Ticket:** S13.7-T7b — Deferred null-reason enums + dead-code sweep
**Date:** 2026-06-01
**Closes:** KI-NEW-AA (StoreProfileNullReason); partial KI-NEW-AB (C2 shipped; C1 deferred)
**Branch:** post-6b-restructured-roadmap
**Deviation check:** none

---

## Approved scope

Three sub-tasks:

- A: `StoreProfileNullReason` enum + `EngineRun.store_profile_null_reason` paired field + main.py wiring
- B: `ModelCardAbsenceReason` + `CohortDiagnosticsAbsenceReason` enums declared (dict-field vocab; no paired EngineRun fields)
- C: Dead-code sweep — `_surface_mechanism_for_play` from decide.py (C2); `targeting_non_causal_prior` from sizing.py (C1)
- D: Update `test_null_reason_registry.py` deferred assertions; write `tests/test_s13_7_t7b_deferred_null_reasons.py`
- SHA ledger: re-pin with T7b definition entry

---

## Sub-task outcomes

### A — StoreProfileNullReason (KI-NEW-AA closed)

`StoreProfileNullReason` was NOT previously declared. Added with 2 members:
- `PROFILE_NOT_LOADED = "profile_not_loaded"` — `build_store_profile` raised
- `ONBOARDING_INCOMPLETE = "onboarding_incomplete"` — reserved forward-compat

`EngineRun.store_profile_null_reason: Optional[StoreProfileNullReason] = None` added immediately after `store_profile`. `_from_dict_engine_run` wired with strict-cutover carry-forward (pre-T7b key absence → `None`).

`src/main.py` wired at the `ENGINE_V2_STORE_PROFILE` block:
- Flag OFF → both `store_profile` and `store_profile_null_reason` stay `None` (exempt)
- Flag ON + success → both `None` (profile loaded; no null-reason needed)
- Flag ON + exception → `store_profile=None` + `store_profile_null_reason=PROFILE_NOT_LOADED`

`TODO(S14)` comment placed in enum docstring and field comment: distinguish `ONBOARDING_INCOMPLETE` when onboarding-state taxonomy is formalized.

### B — ModelCardAbsenceReason + CohortDiagnosticsAbsenceReason (dict vocab only)

Both enums declared per DS T7b retraction of `Dict[k, AbsenceReason]` pattern:

`ModelCardAbsenceReason` (3 members): `SUBSTRATE_NOT_RUN`, `SUBSTRATE_REFUSED`, `INSUFFICIENT_DATA`
`CohortDiagnosticsAbsenceReason` (2 members): `INSUFFICIENT_COHORT_DEPTH`, `SUBSTRATE_REFUSED`

No paired `_null_reason` fields on `EngineRun` — dict key absence is self-documenting per DS adjudication.

All 3 new enums added to `__all__` per DS R6 single-file authority.

### C1 — targeting_non_causal_prior (DEFERRED)

`grep -rn "targeting_non_causal_prior"` found active call sites:
- `src/sizing.py` L615 and L777 — live suppression-reason string
- Test pins in `tests/test_sizing.py`, `tests/test_s7_5_t3_blend_refusal.py`, `tests/test_internal_stats_not_rendered.py`, `tests/test_outcome_log.py`

Cannot delete without producer rewrite per DS Q1. Test `test_dead_code_targeting_non_causal_prior_skipped` uses `pytest.skip` with documented rationale referencing KI-NEW-AB.

### C2 — _surface_mechanism_for_play (SHIPPED)

`grep -rn "_surface_mechanism_for_play"` found:
- `src/decide.py:662` — function definition only
- `src/decide.py:696` — comment reference only (no call)
- `src/engine_run.py` — comment references only
- Zero call sites anywhere

Function deleted from `src/decide.py`. Replaced with a comment block documenting the removal rationale and confirming the renderer-side mirror `storytelling_v2._mechanism_for_play` is independent.

### D — test updates

`tests/test_null_reason_registry.py` — flipped 3 deferred `assert not hasattr` assertions to `assert hasattr` with member-count + `__all__` coverage. Added `EngineRun.store_profile_null_reason` field existence assertion.

`tests/test_s13_7_t7b_deferred_null_reasons.py` — 8 tests written (7 pass, 1 skip):
- `test_store_profile_null_reason_enum_declared` — PASSED
- `test_store_profile_null_reason_field_on_engine_run` — PASSED
- `test_store_profile_null_reason_round_trips_via_to_dict` — PASSED
- `test_store_profile_null_reason_none_when_not_set` — PASSED
- `test_model_card_absence_reason_declared` — PASSED
- `test_cohort_diagnostics_absence_reason_declared` — PASSED
- `test_dead_code_targeting_non_causal_prior_skipped` — SKIPPED (active call sites; KI-NEW-AB)
- `test_dead_code_surface_mechanism_for_play_removed` — PASSED

### SHA ledger

`post_s13_7_t7b_definition` entry added to `_meta` in `tests/fixtures/pinned_sha_ledger.json`. No individual fixture sha values added — the ledger's `engine_run_json_sha_caveat` notes these are wall-clock unstable and documentation-only. The `test_engine_v2_shadow.py` golden tests (3 passed) confirm the non-synthetic fixtures are unaffected.

---

## Files changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` — 3 new enums, 1 new field on EngineRun, __all__ additions, CHANGELOG T7b entry, registry comment update, _from_dict_engine_run wiring
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` — StoreProfile block wired with null_reason on exception path
- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py` — `_surface_mechanism_for_play` deleted (C2)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_null_reason_registry.py` — deferred assertions flipped to shipped
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s13_7_t7b_deferred_null_reasons.py` — NEW (8 tests)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/fixtures/pinned_sha_ledger.json` — T7b definition entry added

---

## Tests / checks run

```
tests/test_s13_7_t7b_deferred_null_reasons.py   7 passed, 1 skipped
tests/test_null_reason_registry.py              1 passed
tests/test_s13_6_t7a_no_silent_nulls.py        20 passed
tests/test_engine_v2_shadow.py                  3 passed
tests/ -x -q (full suite)                      596 passed, 7 skipped, 1 pre-existing failure
```

Pre-existing failure: `tests/test_phase5_considered_always.py::test_abstain_soft_briefing_renders_populated_considered_section` — confirmed pre-existing (fails on the unmodified branch HEAD; not introduced by this ticket).

---

## Behavior changes

1. `EngineRun.to_dict()` now emits `"store_profile_null_reason": null` for all existing fixtures (new null-valued key). Additive per the v2.x.x schema freeze rule.
2. When `ENGINE_V2_STORE_PROFILE=true` and `build_store_profile` raises, `engine_run.store_profile_null_reason` is set to `"profile_not_loaded"` instead of staying `None`.
3. `_surface_mechanism_for_play` is gone from `src/decide.py` — no call sites existed, so runtime behavior is identical.
4. `ModelCardAbsenceReason` and `CohortDiagnosticsAbsenceReason` are now importable vocabulary enums (no runtime behavior change).

---

## Remaining risks

1. **KI-NEW-AB C1 deferred:** `targeting_non_causal_prior` string in `src/sizing.py` is documented dead code under `ENGINE_V2_PRIORS_VALIDATION=true` but has pinned test assertions. Full removal requires a producer rewrite per DS Q1 and test re-pin. Not a correctness issue — the path is defensive-dead, not incorrect.

2. **ONBOARDING_INCOMPLETE not yet emitted:** The `ONBOARDING_INCOMPLETE` member is declared and forward-compat but never set by any producer. `TODO(S14)` comment placed in enum docstring. Until the beta onboarding flow formalizes a distinct "incomplete" state, all None-store-profile cases under flag-ON will receive `PROFILE_NOT_LOADED`.

3. **Dict absence-reason vocabulary is informational only:** `ModelCardAbsenceReason` and `CohortDiagnosticsAbsenceReason` are declared but not consumed by any producer or test at the emission site. They are agent-reference vocabulary per the DS T7b retraction. Consumption wiring is S14+ scope.

---

## Follow-up work

- S14: Distinguish `ONBOARDING_INCOMPLETE` from `PROFILE_NOT_LOADED` when beta onboarding-state taxonomy is formalized
- S14: Consume `ModelCardAbsenceReason` + `CohortDiagnosticsAbsenceReason` at the predictive-substrate emission sites (flag-off path vs. data-insufficient path distinction)
- KI-NEW-AB (C1) open: `targeting_non_causal_prior` cleanup requires producer rewrite; file as S14 ticket when `ENGINE_V2_PRIORS_VALIDATION` dead-code sweep is scoped
