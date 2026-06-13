# S13.7-T2 follow-up fix — manifest.artifacts.engine_run pointer

## Approved scope

Contract bug flagged by DS at S13 sprint-close: `manifest.artifacts.engine_run`
was written as the literal string `"engine_run.json"`. Because the manifest
itself lives at `data/<store_id>/runs/<run_id>/manifest.json`, that string,
when resolved as a path relative to the manifest's directory, points at
`data/<store_id>/runs/<run_id>/engine_run.json` — a file that does not
exist. The immutable snapshot is actually written one directory up, at
`data/<store_id>/runs/<run_id>.json` (sibling file), by
`src/memory/snapshot.py::write_immutable_snapshot`.

Fix: change the manifest's `engine_run` field to `f"../{run_id}.json"` so
that MCP agents following the pointer relative to the manifest's own
directory arrive at the real snapshot file.

Scope is strictly the pointer string + tests + tool docstring. The
snapshot path, the manifest schema_version, and the main.py wiring are
unchanged.

## Patch summary

1. `src/run_manifest.py`
   - L34 (docstring schema example): `"engine_run": "engine_run.json"` →
     `"engine_run": "../<run_id>.json"` (placeholder form; the actual
     value is interpolated at write time).
   - `write_run_manifest` docstring: added a "Note" block stating that
     `artifacts.engine_run` is relative to the manifest's own directory
     and resolves to `../<run_id>.json`.
   - L155 (the actually-written value inside `_build_manifest`):
     `"engine_run": "engine_run.json"` → `"engine_run": f"../{run_id}.json"`.
     `run_id` is already a kwarg in scope on `_build_manifest`.

2. `tools/validate_engine_run.py`
   - L8 (module docstring usage example): example path
     `data/<store_id>/runs/<run_id>/engine_run.json` →
     `data/<store_id>/runs/<run_id>.json`.
   - L104–105 (`main()` usage string): same path correction.

3. `tests/test_s13_7_t2_manifest.py`
   - `test_manifest_written_after_run`: assertion updated from
     `artifacts["engine_run"] == "engine_run.json"` to
     `artifacts["engine_run"] == f"../{run_id}.json"`.
   - Added `test_manifest_engine_run_pointer_resolves_to_snapshot_file`:
     plants a fake `<run_id>.json` snapshot at the canonical runs/
     location, invokes `write_run_manifest`, reads back the manifest,
     resolves `artifacts.engine_run` relative to the manifest's parent
     directory via `pathlib.Path.resolve()`, and asserts the resolved
     path equals the snapshot file and exists on disk.

## Files changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/run_manifest.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tools/validate_engine_run.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s13_7_t2_manifest.py`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s13.7-t2-fix-manifest-path-summary.md`
  (this file)

## Tests / checks run

- `python -m pytest tests/test_s13_7_t2_manifest.py -v` → 8 passed
  (4 original + 3 materialize_audience_csvs structural + 1 new
  resolution test).
- `python -m pytest tests/ -x -q --deselect tests/test_phase5_considered_always.py`
  → 781 passed, 7 skipped, 10 deselected, 1 failed.
  - The one failure is
    `tests/test_recommended_experiment_forbidden_tokens.py::test_negative_control_universal_token_in_recommendation_text_is_detected`.
  - Confirmed pre-existing on HEAD by stashing the patch and rerunning
    the same test — it fails identically (the test injects no
    `calibrated` token; it expects a literal that is no longer present
    in the rendered section). Unrelated to this manifest pointer fix.

## Behavior changes

- The `engine_run` value inside the manifest now contains a relative
  path (`../<run_id>.json`) instead of a bare filename.
- MCP consumers that join `manifest.parent / manifest.artifacts.engine_run`
  will now find the immutable snapshot file. Previously they would have
  resolved to a non-existent path.
- No change to the snapshot file itself, no change to manifest
  `schema_version`, no change to where the manifest is written.

## Artifacts added

- New test `test_manifest_engine_run_pointer_resolves_to_snapshot_file`
  in `tests/test_s13_7_t2_manifest.py`.

## Remaining risks

- Any downstream consumer that hardcoded `manifest.artifacts.engine_run`
  as a bare filename will need to start treating it as a relative path.
  At present, no such consumer exists in-tree (the only readers are the
  manifest tests and not-yet-built MCPs); this is the moment to fix
  before a wrong consumer ships.
- Schema version was deliberately not bumped per ticket instruction.
  If a future MCP wants to discriminate on schema, that bump is
  on follow-up work, not this fix.

## Follow-up work

- When narration / assembly MCPs are wired up, ensure their snapshot
  loaders join the manifest path with `artifacts.engine_run` via
  `pathlib.Path` rather than treating the value as a bare filename.
- Pre-existing failure in
  `test_negative_control_universal_token_in_recommendation_text_is_detected`
  is a separate, unrelated bug — owner / KI assignment is outside this
  ticket.

Deviation check: none
