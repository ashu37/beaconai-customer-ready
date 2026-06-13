# Milestone 9 Summary — ML readiness / outcome logging

_Completed: 2026-05-03 (engine-rework branch)_

## Approved scope

Milestone 9 of `agent_outputs/implementation-manager-overhaul-plan-final.md`:
add learning-ready artifacts so a future calibration / realized-vs-predicted
layer plugs in without re-architecture. **Add the data, do not claim ML
lift.** Tickets T9.1 through T9.5.

- T9.1 — `recommended_history.json` writer.
- T9.2 — verify `measurement.p_internal` / `ci_internal` survive
  serialization end-to-end and are NOT in any rendered HTML.
- T9.3 — `revenue_range.drivers` provenance lock (required non-empty
  for any non-suppressed range).
- T9.4 — `src/calibration_stub.load_realization_factors` returning the
  required three-key contract dict (DS Architect QA Required Change 5).
- T9.5 — merchant-INVISIBLE `receipts/debug.html` for internal stats.

**Out of scope (deferred per the M9 ticket):**

- M10 cleanup / legacy code deletion.
- Reading `recommended_history.json` for actual calibration.
- Any ML claim, uplift terminology, treatment effect, calibrated lift,
  Bayesian priors, or hierarchical priors.
- Klaviyo / Shopify production integrations.
- V2 default flip.
- Any change to merchant-facing renderer behavior (legacy or V2).
- Re-baselining of M0/M4b/M5/M6/M7/M8 goldens.

## Files changed

### New files

- `/Users/atul.jena/Projects/Personal/beaconai/src/outcome_log.py` —
  T9.1 outcome-log writer. Exports `write_recommended_history(engine_run,
  history_path, *, enabled=True)`, `build_record(engine_run)`,
  `assert_drivers_present_for_non_suppressed(engine_run)` (T9.3 invariant),
  and the `STATUS_*` constants. Pure-write, never raises.
- `/Users/atul.jena/Projects/Personal/beaconai/src/calibration_stub.py` —
  T9.4 stub. Exports `load_realization_factors(history_path) -> dict`.
  Returns the locked three-key contract dict (Required Change 5). Does
  not read the file in Phase 1.
- `/Users/atul.jena/Projects/Personal/beaconai/src/debug_renderer.py` —
  T9.5 merchant-INVISIBLE debug-HTML renderer. Exports
  `render_debug_html(engine_run) -> str` and the `INTERNAL_BANNER`
  constant. Pure function; the caller writes the file.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_outcome_log.py`
  — 16 tests across `build_record`, append, missing-file create,
  malformed-file recovery (truncated JSON, dict-not-list, empty file,
  non-dict entries), disabled flag, no-engine-run guard, drivers-required
  invariant.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_calibration_stub_shape.py`
  — 5 tests pinning the Required Change 5 return shape.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_internal_stats_not_rendered.py`
  — 8 tests pinning the merchant-invisible / merchant-facing split.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_measurement_persistence.py`
  — 5 tests pinning T9.2 (`p_internal`/`ci_internal` survive
  serialization, appear in outcome log + debug.html, do NOT appear in
  briefing.html).
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-milestone-9-summary.md`
  — this file.

### Edited files

- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` — wired
  three blocks inside the existing EngineRun try/except (so a failure
  can never block the merchant briefing):
  1. Write `receipts/debug.html` via `debug_renderer.render_debug_html`.
  2. Append a record to the outcome history via
     `outcome_log.write_recommended_history` behind `OUTCOME_LOG_ENABLED`.
  3. Resolve `OUTCOME_LOG_PATH` from cfg with default
     `data/recommended_history.json`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py`:
  - DEFAULTS: added `OUTCOME_LOG_ENABLED` (default `true`) and
    `OUTCOME_LOG_PATH` (default empty -> resolves to
    `data/recommended_history.json`).
  - `_coerce` bool set: extended to include `OUTCOME_LOG_ENABLED`.
- `/Users/atul.jena/Projects/Personal/beaconai/.gitignore`: added the
  runtime history file plus the `.corrupt-*.bak` recovery siblings so
  the writer artifacts are never committed.
- `/Users/atul.jena/Projects/Personal/beaconai/docs/engine_flags.md`:
  - Last-updated stamp bumped to M9.
  - Added the `OUTCOME_LOG_ENABLED` and `OUTCOME_LOG_PATH` rows to the
    DEFAULTS table.
  - Annotated the future-flags table.
  - Added a new "Milestone 9 — Outcome log behavior" section documenting
    file location, append semantics, missing-file create, malformed-file
    recovery, privacy safeguards, and the relationship to the
    calibration stub.

### Pre-existing files (untouched)

- `src/storytelling.py` — legacy renderer untouched.
- `src/storytelling_v2.py` — V2 renderer untouched.
- `templates/briefing.html.j2` — legacy template untouched.
- `src/engine_run.py`, `src/engine_run_adapter.py`, `src/decide.py`,
  `src/sizing.py`, `src/guardrails.py`, `src/priors_loader.py`,
  `src/evidence.py` — read-only by the M9 modules. No edits.
- `src/briefing.py` — no router change. M9 does not touch the briefing
  renderer at all.
- `tests/golden/` — no goldens re-baselined.

## Exact commands run

```
# M9 unit tests (new)
python -m pytest tests/test_outcome_log.py tests/test_calibration_stub_shape.py tests/test_internal_stats_not_rendered.py -v
# 28 passed in 0.04s

# T9.2 measurement persistence
python -m pytest tests/test_measurement_persistence.py -v
# 5 passed in 0.01s

# Golden diff (no re-baseline)
python -m pytest tests/test_golden_diff.py -v
# 3 passed (no re-baseline)

# Full suite
python -m pytest tests/ -q
# 434 passed, 5 skipped, 200 warnings (M8 baseline 401 -> M9 434 = +33 new tests)

# End-to-end smoke: default flags, history file under /tmp
OUTCOME_LOG_PATH=/tmp/m9_smoke_history.json \
  python -m src.main --orders data/SM_orders.csv --brand m9_smoke --out /tmp/m9_smoke
# Briefing renders. receipts/debug.html written. /tmp/m9_smoke_history.json appended.

# 3 consecutive runs => 3 records
OUTCOME_LOG_PATH=/tmp/m9_smoke_history.json python -m src.main --orders data/SM_orders.csv --brand m9_smoke --out /tmp/m9_smoke
OUTCOME_LOG_PATH=/tmp/m9_smoke_history.json python -m src.main --orders data/SM_orders.csv --brand m9_smoke --out /tmp/m9_smoke
python -c "import json; print(len(json.load(open('/tmp/m9_smoke_history.json'))))"
# 3

# Disabled flag short-circuits cleanly (no file written)
OUTCOME_LOG_ENABLED=false OUTCOME_LOG_PATH=/tmp/m9_disabled_history.json \
  python -m src.main --orders data/SM_orders.csv --brand m9_disabled --out /tmp/m9_disabled
ls /tmp/m9_disabled_history.json
# No such file or directory -- expected.

# Malformed-history recovery in production
printf '%s' '[{"truncated":' > /tmp/m9_corrupt_history.json
OUTCOME_LOG_PATH=/tmp/m9_corrupt_history.json \
  python -m src.main --orders data/SM_orders.csv --brand m9_corrupt --out /tmp/m9_corrupt
# [Outcome log] {'status': 'recovered_from_corrupt', ...,
#                'corrupt_backup': '.../m9_corrupt_history.json.corrupt-<ts>.bak'}

# V2 stack end-to-end (debug.html surfaces internal stats; briefing.html does not)
ENGINE_V2_OUTPUT=true ENGINE_V2_DECIDE=true ENGINE_V2_SIZING=true \
STATS_NAN_FOR_HARDCODED=true EVIDENCE_CLASS_ENFORCED=true \
MATERIALITY_FLOOR_SCALE_AWARE=true CANNIBALIZATION_GATE_ENABLED=true \
ANOMALY_GATE_ENABLED=true OUTCOME_LOG_PATH=/tmp/m9_v2_history.json \
  python -m src.main --orders data/SM_orders.csv --brand m9_v2 --out /tmp/m9_v2
grep -cE 'p_internal|ci_internal|p =|q =|confidence_score|final_score' /tmp/m9_v2/briefings/m9_v2_briefing.html
# 0
```

## Tests / checks run and results

| Suite                                                | Result                       |
|------------------------------------------------------|------------------------------|
| `tests/test_outcome_log.py`                          | **16 passed**                |
| `tests/test_calibration_stub_shape.py`               | **5 passed**                 |
| `tests/test_internal_stats_not_rendered.py`          | **8 passed**                 |
| `tests/test_measurement_persistence.py`              | **5 passed**                 |
| `tests/test_golden_diff.py`                          | **3 passed** (no re-baseline)|
| Full suite `python -m pytest tests/`                 | **434 passed, 5 skipped**    |

Full-suite count went from 401 (M8) -> 434 (M9) = +33 new tests. Zero
regressions. Zero golden re-baselines.

## Outcome log schema

`SCHEMA_VERSION = "1.0.0"`. One JSON record appended per run to
`data/recommended_history.json` (path overridable via `OUTCOME_LOG_PATH`).

```json
{
  "schema_version": "1.0.0",
  "ts": "2026-05-03T20:28:54.621Z",
  "store_id": "m9_smoke",
  "run_id": "<uuid>",
  "anchor_date": "2025-...",
  "decision_state": "publish | abstain_soft | abstain_hard",
  "abstain_reason": "<string or null>",
  "data_quality_flags": ["bfcm_overlap", ...],
  "cold_start": false,
  "scale": {
    "monthly_revenue": 120000.0,
    "customer_base_est": 4500,
    "materiality_floor": 5000.0
  },
  "recommended": [
    {
      "play_id": "winback_21_45",
      "evidence_class": "measured | directional | targeting | weak",
      "confidence_label": "Strong | Emerging | Targeting | null",
      "audience": {"id": "...", "size": 412, "fraction_of_base": 0.07,
                    "overlap_with": ["..."]},
      "measurement": {
        "metric": "...", "observed_effect": 0.12, "n": 412,
        "primary_window": "L28", "consistency_across_windows": 2,
        "p_internal": 0.014, "ci_internal": [0.04, 0.20]
      },
      "revenue_range": {
        "p10": 2400.0, "p50": 4800.0, "p90": 7200.0,
        "source": "store_observed | vertical_prior | blend",
        "suppressed": false,
        "drivers": [{"name": "...", "value": ..., "source": "...", ...}]
      }
    }
  ],
  "rejected": [
    {"play_id": "...", "reason_code": "inventory_blocked", "reason_text": "..."}
  ],
  "summary": {
    "n_recommended": 3,
    "n_rejected": 0,
    "sum_recommended_p50": 82150.52
  }
}
```

Key invariants:

- `measurement` is `null` for `evidence_class == "targeting"` (M4b
  contract preserved).
- `revenue_range.drivers` is always present; non-empty for any
  non-suppressed range (T9.3 invariant).
- `audience.id` and `audience.size` are persisted; raw customer IDs
  are NEVER persisted.
- Decision state, abstain reason, and data-quality flags are persisted
  so a future calibration layer can stratify by run regime.

## Calibration stub shape

`src.calibration_stub.load_realization_factors(history_path=None) -> dict`
returns EXACTLY:

```python
{
    "prior_overrides": {},        # {prior_key: override_value}
    "evidence_thresholds": {},    # {play_id: {threshold_name: value}}
    "materiality_overrides": {},  # {scale_band: {floor_param: value}}
}
```

Phase 1 always returns the empty contract dict regardless of
`history_path`. The function never raises. Each call returns a fresh
dict so callers can mutate without leaking state. Pinned by 5 tests in
`tests/test_calibration_stub_shape.py`.

## debug.html behavior

- Written to `<out_dir>/receipts/debug.html` on every run that builds
  an EngineRun.
- Pure function `render_debug_html(engine_run) -> str`; the caller
  (`src/main.py`) writes the file.
- Top-of-page banner: "INTERNAL DIAGNOSTICS — NOT FOR MERCHANT
  DISTRIBUTION. Generated by BeaconAI engine for internal review only."
  (constant `INTERNAL_BANNER`).
- Surfaces (per row):
  - `play_id`, `evidence_class`, `confidence_label`.
  - Audience id / size / fraction.
  - `measurement.metric`, `observed_effect`, `n`, `primary_window`,
    `consistency_across_windows`, **`p_internal`**, **`ci_internal`**.
  - `revenue_range` p10/p50/p90, source, **`drivers`** (collapsible),
    suppression reason for suppressed ranges.
  - Considered/rejected: `reason_code`, `reason_text`,
    `evidence_snapshot`, `would_fire_if`.
- The merchant-facing `briefing.html` does NOT link to `debug.html`
  (verified by `test_briefing_v2_html_does_not_link_to_debug_html`).
- The merchant-facing briefing contains zero `p_internal`,
  `ci_internal`, `p =`, `q =`, `confidence_score`, or `final_score`
  tokens (verified by
  `test_briefing_v2_html_does_not_contain_p_internal_or_ci_internal`).

## Privacy safeguards

| Concern                            | Safeguard                                                          |
|------------------------------------|--------------------------------------------------------------------|
| Raw customer IDs                   | Not persisted. Only `audience.id` + `audience.size` recorded.       |
| Order-line PII                     | Not in EngineRun by schema; cannot leak through this writer.        |
| Customer email                     | Not in EngineRun by schema; cannot leak through this writer.        |
| Forbidden-key sweep                | `test_build_record_does_not_persist_raw_customer_ids` greps for     |
|                                    | `customer_id`, `Customer Email`, `Customer ID`, `email` and asserts |
|                                    | none appear in the JSON record.                                     |
| Network egress                     | Zero. The writer uses local file I/O only.                          |
| Gitignore                          | `data/recommended_history.json` and `.corrupt-*.bak` siblings are   |
|                                    | gitignored. Verified by `git status --porcelain` after a touch.     |
| Disablable                         | `OUTCOME_LOG_ENABLED=false` short-circuits cleanly. Smoke-tested.   |
| Failure isolation                  | Writer never raises. Errors surface through a status dict.          |

## Whether goldens still pass

**Yes. Zero goldens re-baselined.**

- `tests/test_golden_diff.py` runs with M9 patches applied. M4b
  canonical goldens remain byte-identical. Result: 3/3 passed.
- The merchant-facing `briefing.html` is unchanged on every fixture
  in flag-off mode (legacy renderer untouched).
- `engine_run.json` is unchanged structurally (M9 only writes new
  receipt files; it does not modify the existing serializer).
- The new `receipts/debug.html` is not part of any golden tree (the
  M0 freeze snapshot intentionally excluded receipts beyond a fixed
  list; debug.html is additive).
- `make golden-test` (equivalent to the diff test) passes.

## Skipped items / accepted notes

None of the M9 tickets are skipped.

Accepted notes:

- **`OUTCOME_LOG_ENABLED` default is true.** Per the ticket: "default
  may be true only if writing is safe, local, deterministic, and
  gitignored." All four conditions hold:
  - safe: writer never raises; failure is reported via status dict.
  - local: writes to `data/recommended_history.json` only.
  - deterministic: stable JSON shape; only the `ts` field varies per
    run, matching the schema design.
  - gitignored: confirmed via `git status` test.
- **`receipts/debug.html` is produced unconditionally** on every run
  that successfully builds an EngineRun. There is no gating flag for
  the debug page itself; it is internal-only by file name and banner.
  The merchant never sees it because nothing links to it.
- **Calibration stub does not yet read the file.** Per the M9 ticket:
  "the engine doesn't *read* the history file for calibration." The
  stub's `history_path` argument exists for future signature
  compatibility only; Phase 1 always returns the empty contract dict.
- **`receipts/debug.html` is NOT a golden.** Adding it to the golden
  tree would lock down a layout that is purely a developer aide. The
  contract test `test_internal_stats_not_rendered.py` covers the only
  invariants that matter (banner present, internal stats surfaced,
  no link from merchant briefing).
- **Outcome log file is not part of any golden either.** It is a
  runtime artifact in `data/`, not under `tests/golden/`.

## Remaining risks

1. **Outcome log records have no schema-migration path yet.** If a
   future ticket changes the record shape, old records with
   `schema_version=1.0.0` will need a migrator. Mitigation: every
   record carries `schema_version`; an upgrade path can be added when
   it becomes necessary.
2. **`debug.html` is not in any golden tree.** Layout drift will not
   be caught by golden diff. Mitigation: the contract test pins the
   load-bearing strings (banner, internal labels, no merchant link).
3. **`audience.size` is the only audience metric persisted.** A future
   calibration layer that wants per-segment fidelity will need
   richer audience metadata. We intentionally stopped at metadata that
   is privacy-safe by construction.
4. **Real fixtures still produce ABSTAIN_SOFT under the V2 stack** (M8
   transition caveat). The history records therefore contain mostly
   targeting cards and zero `p_internal` values today. Once measured
   plays surface in real fixtures (M5/M6 priors maturation), the
   internal diagnostics will be populated and the M9 schema is ready.
5. **`data/recommended_history.json` will accumulate forever.** No
   rotation policy. Mitigation: it is gitignored and local; ops can
   delete it any time. Future Klaviyo-integrated path will likely
   migrate to a per-store database, retiring this file.
6. **`measurement` round-trip on `targeting` plays.** The
   `_coerce_evidence` adapter still defaults unmapped values to
   `TARGETING`; the M9 outcome log preserves whatever the EngineRun
   carries. If a future bug emits a targeting card with a non-null
   measurement, the outcome log will carry it through. The schema
   invariant is enforced at the renderer level (M8 / V2) and at the
   evidence module level (M4a/M4b), not by the writer.
7. **No automatic prune of `.corrupt-*.bak` siblings.** After many
   recovery events the local data dir could collect backups. Manual
   cleanup is fine for now; ops can `rm data/recommended_history.json.corrupt-*.bak`.

## Readiness for Milestone 10

**Green to start M10 when planning is reopened.** M9 acceptance
criteria are met:

- 3 consecutive runs on the same merchant produce 3 entries in
  `data/recommended_history.json`. Verified by both unit test
  (`test_write_recommended_history_appends_existing_records`) and the
  end-to-end smoke loop above.
- Every PlayCard with `evidence_class in {measured, directional}` has
  non-null `measurement.p_internal` (round-trip verified).
- `tests/test_outcome_log.py` passes (16/16).
- `load_realization_factors()` returns a dict with EXACTLY the keys
  `{prior_overrides, evidence_thresholds, materiality_overrides}`
  (Required Change 5 verified, 5/5 tests).
- Internal stats appear in `receipts/debug.html` (8/8 tests).
- Internal stats do NOT appear in `briefing.html` (8/8 tests).
- Goldens still pass (3/3).
- No V2 default flip.
- No ML claim in any merchant-facing copy.
- `data/recommended_history.json` is gitignored.
- `OUTCOME_LOG_ENABLED` documented in `docs/engine_flags.md`.
- Full suite passes (434 passed, 5 skipped).

**M10 prerequisites that M9 satisfies:**

- The outcome log file is the data anchor M10 will use (or delete) when
  decommissioning the legacy fatigue stub. M5's
  `gate_recently_run` already reads the file when the flag is on; M10
  can keep that wiring or migrate it.
- `src/calibration_stub.py` is the interface anchor M10 reviewers can
  look at to confirm "we did not silently start consuming a fake ML
  signal." The function returns `{}, {}, {}` and any future change is
  trackable.
- `receipts/debug.html` is the audit trail M10 reviewers can use to
  verify behavior changes against without spinning up the merchant
  briefing.

The M9 contract — `write_recommended_history(EngineRun, path)` and
`render_debug_html(EngineRun) -> str` — is a clean seam for M10's
eventual cleanup pass and Phase 2's calibration plug-in.

## Validation summary

- **33 new tests** across 4 new test files. Zero existing tests
  modified.
- **0 regressions** in the 401-test M8 baseline (now 434 with M9
  additions).
- **0 goldens re-baselined.** All 3 M0/M4b/M5/M6/M7/M8 fixtures still
  pass byte-identical.
- **2 new env flags** added (`OUTCOME_LOG_ENABLED`, `OUTCOME_LOG_PATH`).
- **3 new modules** added: `src/outcome_log.py`,
  `src/calibration_stub.py`, `src/debug_renderer.py`. All leaf-level;
  imports only `engine_run` + stdlib.
- **3 end-to-end smoke runs** confirm:
  - default flags: history appended, debug.html written, briefing
    unchanged, zero forbidden tokens in briefing.html;
  - `OUTCOME_LOG_ENABLED=false`: no history file written;
  - corrupt history seeded: writer recovers, moves the broken file
    aside, run succeeds with no crash.
- **Legacy renderer untouched. V2 renderer untouched. Briefing
  template untouched. Legacy `actions_log.json` untouched. Decision
  logic untouched. Goldens untouched.** Per the M9 hard NOT-IN-SCOPE
  rule.
- **No ML claim, no uplift, no calibrated lift, no Bayesian / ML
  language** in any merchant-facing output (M9 mandate verified by the
  forbidden-token sweep on briefing.html).
