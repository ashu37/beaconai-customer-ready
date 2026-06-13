# S-4 — Immutable snapshot discipline + snapshot_sha256

**Owner:** code-refactor-engineer (Engineer A, Sprint 3 lead-off ticket)
**Date:** 2026-05-10
**Sprint:** Sprint 3, ticket S-4
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §3, ticket S-4
**Predecessor:** S-3 ([code-refactor-engineer-s3-summary.md](./code-refactor-engineer-s3-summary.md))
**Status:** Complete. Schema freeze preserved (`event_version=1`, additive only). Full suite green.

---

## Approved scope

1. Engine writes the slate JSON to an immutable per-run path: `data/<store_id>/runs/<run_id>.json`. Never overwritten.
2. Keep `receipts/engine_run.json` as a backward-compat mutable mirror — byte-identical copy of the latest immutable run. Existing Swarm consumers see no change.
3. Compute sha256 over the immutable snapshot file at write time. Add `snapshot_sha256` to the `RecommendationEmittedPayload` and `RecommendationConsideredPayload` — additive, `event_version` stays `1`.
4. `_emit_substrate_events` populates `snapshot_sha256` on every emitted event in the run.

## Patch summary

- New `src/memory/snapshot.py`: `write_immutable_snapshot(...)` writes to `data/<store_id>/runs/<run_id>.json` (absolute path via `Path.resolve()`), refuses overwrite (`FileExistsError`), reads the on-disk bytes and computes sha256 over them, then `shutil.copyfile`s the file byte-identically to `receipts/engine_run.json`. Companion `verify_snapshot(path, expected_sha256) -> bool` for downstream audit / mutation tests. Stdlib only (`hashlib.sha256`).
- `src/memory/__init__.py` re-exports `write_immutable_snapshot` and `verify_snapshot`.
- `src/main.py`:
  - Imports `write_immutable_snapshot`.
  - Replaces the legacy `write_json(receipts/engine_run.json, ...)` call with `write_immutable_snapshot(...)`. On failure, falls back to the legacy `write_json` so the engine still produces `engine_run.json` (substrate snapshot fields then stay `None` for that run; the operator sees a `[Snapshot] Warning:` line).
  - Threads `snapshot_path` / `snapshot_sha256` into `_emit_substrate_events`, `_emit_one_play_card`, `_emit_one_rejected_play`. Both emit helpers populate the new fields on the payload (replacing the prior `None` placeholders pinned by S-3).
- New `tests/test_s4_snapshot_immutability.py` (6 tests): 5-run distinct-file uniqueness, on-disk sha256 matches event payload, mutation-byte detection via `verify_snapshot`, receipts mirror byte-identical to immutable snapshot, overwrite refusal on `run_id` collision, empty `run_id` rejection.

The `RecommendationEmittedPayload` / `RecommendationConsideredPayload` schemas already declared `snapshot_path` / `snapshot_sha256` as `Optional[str]` in S-3 prep, anticipating this ticket. **No schema change.** S-3's `event_version = 1` freeze for the Swarm team is preserved.

## Files changed

| File | Change |
|---|---|
| `src/memory/snapshot.py` | NEW — `write_immutable_snapshot`, `verify_snapshot`, internal `_sha256_file` |
| `src/memory/__init__.py` | Re-export the snapshot helpers |
| `src/main.py` | Wire `write_immutable_snapshot` into the engine_run write site; thread `snapshot_path`/`snapshot_sha256` through the substrate emitter |
| `tests/test_s4_snapshot_immutability.py` | NEW — 6 acceptance tests |
| `memory.md` | New Sprint 3 section + S-4 entry + invariants |

## Tests / checks run

| Suite | Result |
|---|---|
| `tests/test_s4_snapshot_immutability.py` | 6/6 green (89s, runs Beauty 5x via synthetic harness) |
| `tests/test_s3_substrate_emission.py` | 5/5 green |
| `tests/test_slate_regression_beauty_brand.py` | 19/19 green; sha256 unchanged |
| `tests/test_golden_diff.py` | 3/3 green; M0 byte-identical |
| Full suite (`pytest -q`) | **1090 passed, 14 skipped, 0 failed** (was 1084/14/0 at S-3 closeout) |

## Behavior changes

- The slate JSON is now produced at `data/<store_id>/runs/<run_id>.json` first, then copied to `receipts/engine_run.json`. Existing consumers reading `receipts/engine_run.json` see no change (byte-identical mirror).
- Every `recommendation_emitted` / `recommendation_considered` event written to `data/<store_id>/memory.db` now carries the immutable snapshot's absolute path and sha256 in its payload. Downstream auditors can re-hash the file and verify.
- New `data/<store_id>/runs/` directory accumulates monotonically — per founder decision D-2 (retention forever, no TTLs).

## Artifacts added

- `src/memory/snapshot.py` (new module, ~120 lines)
- `tests/test_s4_snapshot_immutability.py` (new test file, 6 tests)
- `agent_outputs/code-refactor-engineer-s4-summary.md` (this file)

## Remaining risks

1. **`data/<store_id>/runs/` grows monotonically.** Per D-2 this is intentional (no TTLs). Disk usage is a Year-2+ concern; revisit only when a real merchant produces enough runs to matter.
2. **Mirror-file write is a copy, not an atomic rename.** A reader of `receipts/engine_run.json` during the half-second between immutable-write and copy could observe a stale mirror. Risk is bounded: today's only consumer is the Swarm team running offline, and immediate post-write reads happen after both writes complete. If a real consumer needs read-during-write safety, switch to `os.replace()` of a tempfile.
3. **Fallback path leaves snapshot_sha256 as None for that run.** If `write_immutable_snapshot` raises (disk full, permission denied), the legacy `write_json` still produces `receipts/engine_run.json`, but the substrate event payload's `snapshot_sha256` field stays `None`. The operator's warning line is the operational surface; a downstream auditor must treat `snapshot_sha256 is None` as "engine couldn't produce one," not "no snapshot exists."
4. **Per-run uuid4 collision is astronomically unlikely**, but the helper raises `FileExistsError` rather than papering over it. If this fires in practice, it's a caller bug (re-using a `run_id`) we want to surface, not absorb.

## Next milestone dependencies

- **S-5 — Read-views + calibration_stub rewire.** Depends on S-3/S-4 substrate writes being stable. The `v_lineage_timeline` view will join `recommendation_emitted` rows on `lineage_id`; the new `snapshot_sha256` field is available for `v_open_recommendations` to surface.
- **S-6 — Manual `campaign_sent` import path + Swarm contract.** Independent of S-4 surface but benefits from snapshot-pinning: a Swarm consumer importing `campaign_sent` can pin the originating recommendation by `(lineage_id, snapshot_sha256)` for full audit traceability.
- Phase 9 `compute_realized_outcome` will read the immutable snapshot file directly (via `snapshot_path` on `recommendation_emitted`) to reconstruct the audience pinned at recommendation time, then verify against `snapshot_sha256` before computing the realized outcome.

## Branch shape

Per the per-commit ritual on `post-6b-restructured-roadmap` (not pushed):

1. `S-4: immutable snapshot discipline + snapshot_sha256 on events` (impl)
2. `Document S-4 in repo memory.md` (memory)
3. `S-4 summary` (this file)

## Hard constraints respected

- `engine_run.json` schema **unchanged** — `snapshot_sha256` lives in the substrate event payload only, NOT in the slate JSON.
- `event_version` stays `1` (additive field; S-3 prep already declared `snapshot_path`/`snapshot_sha256` as `Optional[str]`).
- No new dependencies — `hashlib.sha256` from stdlib, `shutil.copyfile` for byte-identical mirroring.
- `src/memory/views.*` and `src/calibration_stub.py` untouched (S-5 surface).
- `tools/import_campaign_sent.py` untouched (S-6 surface).
- M0 goldens byte-identical (Beauty pinned fixture sha256 unchanged).
