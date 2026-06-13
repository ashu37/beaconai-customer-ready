# S13.7-T2 — JSON Schema export + run manifest

**Ticket:** S13.7-T2
**Engineer:** code-refactor-engineer
**Date:** 2026-06-01
**Branch:** post-6b-restructured-roadmap
**Status:** COMPLETE
**Deviation check:** none

---

## Approved scope

Three deliverables per the ticket spec and DS adjudication #6:

1. `tools/generate_schema.py` — hand-written JSON Schema (draft-07) generator that walks `src/engine_run.py` dataclasses/enums and emits `schemas/engine_run.v2.json`.
2. Per-run `manifest.json` at `data/<store_id>/runs/<run_id>/manifest.json` — enumerates `engine_run.json`, audience CSVs (with materialization status), parquet artifacts, and retention.json.
3. `tools/validate_engine_run.py` — round-trip validation tool using `jsonschema` (soft dep).

Supporting changes:
- `src/audience_resolver.py`: `materialize_audience_csvs` return type `None` → `dict[str, str]` mapping `audience_definition_id` → status string.
- `src/main.py`: call `write_run_manifest` immediately after `materialize_audience_csvs`.
- Tests: `tests/test_s13_7_t2_manifest.py` (7 tests) and `tests/test_s13_7_t2_schema_generator.py` (6 tests).

---

## Files changed

| File | Change |
|---|---|
| `src/audience_resolver.py` | Return type `None` → `dict`; status tracking per aud_def_id; TODO(S13.7-T2) comment resolved |
| `src/main.py` | Capture return value of `_materialize_audience_csvs`; call `write_run_manifest` with `_mat_audience_statuses` |
| `src/run_manifest.py` | NEW — `write_run_manifest` public API + internal helpers |
| `tools/generate_schema.py` | NEW — hand-written schema generator (no new deps; `--dry-run` flag) |
| `tools/validate_engine_run.py` | NEW — round-trip validation tool (jsonschema soft dep) |
| `schemas/engine_run.v2.json` | NEW — generated schema artifact |
| `tests/test_s13_7_t2_manifest.py` | NEW — 7 tests for manifest + return-type change |
| `tests/test_s13_7_t2_schema_generator.py` | NEW — 6 tests for schema generator |

---

## Tests / checks run

```
tests/test_s13_7_t1_audience_resolver.py  — 7 passed (unchanged; return-type change backward-compat confirmed)
tests/test_s13_7_t2_manifest.py           — 7 passed
tests/test_s13_7_t2_schema_generator.py   — 6 passed
Total new tests: 13 (20 in T1+T2 combined)
Full suite: 1 pre-existing failure (test_phase5_considered_always — would_fire_if prose stripped at S13.6-T1a; pre-dates T2; NOT introduced by this patch)
```

`python tools/generate_schema.py` writes `schemas/engine_run.v2.json` (47 $defs covering all dataclasses and enums).

---

## Behavior changes

- `materialize_audience_csvs` now returns `dict[str, str]` instead of `None`. The caller in `main.py` captures the return value and passes it to `write_run_manifest`. All existing callers that ignored the return value are unaffected.
- A `manifest.json` is now written at `data/<store_id>/runs/<run_id>/manifest.json` on every successful engine run (guarded by the same try/except as `materialize_audience_csvs`; non-fatal on failure).
- `schemas/engine_run.v2.json` is the new generated schema artifact; it is NOT read at runtime — operator/agent tooling only.
- `engine_run.json` SHA and `briefing.html` are byte-identical (no runtime output changes to either).

---

## Artifacts added

- `/Users/atul.jena/Projects/Personal/beaconai/src/run_manifest.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tools/generate_schema.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tools/validate_engine_run.py`
- `/Users/atul.jena/Projects/Personal/beaconai/schemas/engine_run.v2.json`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s13_7_t2_manifest.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s13_7_t2_schema_generator.py`

---

## jsonschema dependency status

`jsonschema` is **NOT** in `requirements.txt` and was not installed in the virtual environment. Per the ticket constraint ("Do NOT add jsonschema as a hard dep if it's not already present"), it is implemented as a soft import in `tools/validate_engine_run.py` with a clear error message on `ImportError`. The schema generator uses only stdlib (`json`, `re`, `inspect`, `dataclasses`, `enum`, `argparse`).

---

## Remaining risks

- `StoreProfile` and its nested dataclasses (`Taxonomy`, `BusinessStage`, etc.) from `src/profile/types.py` are referenced as `$ref` in the schema but their nested types are not all enumerated in `$defs` (those types live in `src/profile/types.py` and were not added to `_ALL_DATACLASSES`). The schema is useful for EngineRun surface validation; deeper StoreProfile sub-type validation requires a follow-up schema-generator extension.
- `Tuple[str, str]` fields (e.g. `ModelCardRef.fit_status_chain`, `MonthDelta.substrate_fit_status_changes`) map to `{"type": "array"}` (open). This is correct per spec but provides no item-level validation.
- `jsonschema` round-trip test (`tools/validate_engine_run.py`) requires `pip install jsonschema` before first use. Can be added to `requirements.txt` as a dev dep at the S14 tooling pass.

---

## Follow-up work

- S13.7-T3: `docs/mechanism_contract.md` — per-type parameters shape spec for `MechanismIntent`.
- S13.7-T7b: `StoreProfileNullReason` + `ModelCardAbsenceReason` + `CohortDiagnosticsAbsenceReason` + `CustomerIdsNullReason` field pairing on `Audience.customer_ids` (KI-NEW-AA deferred from S13.6).
- S14 tooling: add `jsonschema` to `requirements.txt` as a dev dep; run `python tools/validate_engine_run.py` against real-merchant `engine_run.json`.
