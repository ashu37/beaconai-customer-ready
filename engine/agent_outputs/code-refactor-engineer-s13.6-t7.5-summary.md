# S13.6-T7.5 — NULL-REASON ENUM REGISTRY: comment block + coverage test

**Ticket:** S13.6-T7.5
**Date:** 2026-06-01
**Branch:** post-6b-restructured-roadmap

## Approved scope

Per DS R7 from `agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md`:
Add a single source-of-truth NULL-REASON ENUM REGISTRY comment block in `src/engine_run.py` and a coverage test that pins all 3 shipped T7a pairs and documents the 4 deferred pairs. Comment-only change to source; no new enums, no dataclass shape changes.

## Patch summary

1. Added `# NULL-REASON ENUM REGISTRY` block (30-line comment) in `src/engine_run.py` immediately before `class RevenueRangeSuppressionReason` (first null-reason enum definition).
2. Added `- T7.5` CHANGELOG entry in the v2.0.0 block, after the T7a entry.
3. Created `tests/test_null_reason_registry.py` with one test: `test_null_reason_enum_registry_coverage`.

## Files changed

- `src/engine_run.py` — comment block added before line 958 (now ~990); T7.5 CHANGELOG entry added after T7a in v2.0.0 block
- `tests/test_null_reason_registry.py` — NEW; 1 test

## Registry comment block placement

Placed at the line immediately preceding `class RevenueRangeSuppressionReason` in `src/engine_run.py`. This is the first of the 3 shipped null-reason enums, making the registry a natural entry-point for any agent reading down the file.

## Exact field names found for the 3 shipped pairs

| Enum | Dataclass | Paired field |
|---|---|---|
| `RevenueRangeSuppressionReason` | `RevenueRange` | `suppression_reason` |
| `MonthDeltaNullReason` | `EngineRun` | `month_2_delta_null_reason` |
| `PredictedSegmentNullReason` | `PredictedSegment` (inner) | `segment_name_null_reason` |

## SHA re-pin assessment

The SHA ledger (`tests/fixtures/pinned_sha_ledger.json`) pins `engine_run.json` fixture outputs, not `engine_run.py` source text. A comment-only change to `src/engine_run.py` does not affect any serialized output. No re-pin required.

## Tests / checks run

- `python -m pytest tests/test_null_reason_registry.py -v` — 1 passed
- `python -m pytest tests/ -x -q` — 596 passed, 1 failed, 7 skipped

## Pre-existing failure

`tests/test_phase5_considered_always.py::test_abstain_soft_briefing_renders_populated_considered_section` — confirmed pre-existing on the branch before this ticket (git stash verification). The test asserts `"Would fire" in html`; the `would_fire_if` prose slot was stripped at S13.6-T1a (Pivot 2 / Option D). This failure predates T7.5 and is not introduced by this commit.

## Behavior changes

None. Comment-only source change. No dataclass shapes altered, no new enums, no producer/consumer/renderer modifications.

## Deferred pairs documented

The registry block and test both document the 4 deferred enums with KI/sprint references:
- `CustomerIdsNullReason` — S13.7-T1
- `StoreProfileNullReason` — S13.7-T7b / KI-NEW-AA
- `ModelCardAbsenceReason` — S13.7-T7b
- `CohortDiagnosticsAbsenceReason` — S13.7-T7b

The test asserts these enums do NOT yet exist; when S13.7-T7b ships those assertions become the engineer's prompt to remove them and add paired coverage.

## Deviation check

none
