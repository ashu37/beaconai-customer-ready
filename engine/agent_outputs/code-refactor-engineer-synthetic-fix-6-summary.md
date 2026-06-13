# Code Refactor Engineer — Synthetic Blocker Fix 6 Summary

_Date: 2026-05-04_
_Scope: Fix 6 ONLY from `agent_outputs/implementation-manager-synthetic-blocker-fix-plan.md`._

## Approved Scope

Per-scenario `VERTICAL_MODE` propagation in the synthetic harness. Every synthetic scenario must run with its declared vertical, and `engine_run.json::briefing_meta.vertical` must match the scenario YAML / metadata.

The synthetic Phase 5 e2e review found that all six scenarios were running as `beauty`, including `supplement_replenishment_240d`. That invalidated vertical-specific scenario testing.

Fix 6 is a pure harness / test-utility change. No engine code, no decision logic, no detection logic, no renderer touched.

## Patch Summary

The codebase did not have a dedicated synthetic harness module. The matrix had been driven by ad-hoc shell loops in the e2e review, which never set `VERTICAL_MODE` per scenario. Two pieces are added:

1. A small reusable harness module (`tests/synthetic_harness.py`) that:
   - Loads scenario metadata from `tests/fixtures/synthetic_scenarios.yaml`.
   - Maps the YAML `category` field to the engine's `VERTICAL_MODE` value (engine accepts `beauty | supplements | mixed`).
   - Builds a per-scenario subprocess environment with `VERTICAL_MODE` set, plus the V2 flag stack and a `PYTHONPATH` that lets the subprocess run from any cwd.
   - Invokes `python -m src.main` as a subprocess for one scenario at a time.
   - Reads `<out_dir>/receipts/engine_run.json` and surfaces `briefing_meta.vertical`.
   - Provides an `assert_vertical_propagated(result)` helper that fails loudly on mismatch — the Fix 6 forcing function.
2. A test file (`tests/test_matrix_vertical_propagation.py`) that pins:
   - The mapper contract (`beauty -> beauty`, `supplement -> supplements`, `lifestyle -> mixed`).
   - The expected declared vertical for each of the six scenarios in the YAML.
   - Env-construction unit tests (per-scenario, override-resistance, V2 flag stack, `PYTHONPATH`).
   - `read_briefing_meta_vertical` and `assert_vertical_propagated` semantics.
   - End-to-end runs (opt-in via `RUN_VERTICAL_PROPAGATION_E2E=1`) for both a beauty scenario AND the supplement scenario, proving end-to-end stamping.

### One additional harness behavior worth flagging

`src/utils.py` lines 14-27 contain a manual `.env` fallback that fires when `python-dotenv` is not installed. That fallback unconditionally overwrites `os.environ` from the repo's `.env`, including `VERTICAL_MODE=beauty` set by the existing `.env`. If the harness ran the subprocess from the repo root, the `.env` file at the repo root would clobber the per-scenario `VERTICAL_MODE` and we would be back to the original Fix 6 defect.

The harness avoids this entirely by:

- Setting `cwd=<out_dir>` (a fresh tmp directory with no `.env`) for the subprocess.
- Setting `PYTHONPATH=<repo_root>` so `python -m src.main` is still importable.

This is a harness-only workaround. The engine-side `.env` fallback is unchanged. Documented as a remaining risk for future Fix 7 reporter authors.

## Files Changed

- **NEW** `/Users/atul.jena/Projects/Personal/beaconai/tests/synthetic_harness.py` — synthetic scenario harness module (load_scenarios, vertical_for_scenario, build_env_for_scenario, run_scenario, read_briefing_meta_vertical, assert_vertical_propagated).
- **NEW** `/Users/atul.jena/Projects/Personal/beaconai/tests/test_matrix_vertical_propagation.py` — 36 tests (34 unit + 2 opt-in E2E).
- **NEW** `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-synthetic-fix-6-summary.md` — this summary.

No `src/` files modified. No tests outside this PR touched. No goldens re-baselined.

## Where Vertical Is Declared

- **YAML path:** `/Users/atul.jena/Projects/Personal/beaconai/tests/fixtures/synthetic_scenarios.yaml`
- **YAML field:** `category` (per-scenario, sibling of `seed`, `anchor_date`, etc.)
- **Allowed YAML values today:** `beauty`, `supplement`, `lifestyle`.

The engine reads `VERTICAL_MODE` from cfg/env (see `src/utils.py::get_vertical_mode` and `src/utils.py::VERTICAL_CONFIG`). Engine-side allowed values are `beauty | supplements | mixed`.

The harness mapper bridges the two (see `tests/synthetic_harness.py::CATEGORY_TO_VERTICAL`):

| YAML `category` | engine `VERTICAL_MODE` |
|---|---|
| `beauty` | `beauty` |
| `supplement` | `supplements` |
| `lifestyle` | `mixed` |
| _(missing)_ | `beauty` (documented default) |
| _(unknown)_ | `beauty` (documented default) |

The default is `beauty` rather than fail-hard because (a) `beauty` is the most-tested vertical, (b) it matches the historical pre-Fix-6 behavior so a missing field never silently degrades a scenario's run, (c) tests in `test_matrix_vertical_propagation.py` pin both the declared-category cases AND the default-fallback case so the default cannot drift silently.

## How `VERTICAL_MODE` Is Propagated

End-to-end flow per scenario:

```
load_scenarios()                     # parse synthetic_scenarios.yaml
  -> scenario_cfg = scenarios[name]

vertical_for_scenario(scenario_cfg)
  -> reads scenario_cfg["category"]
  -> CATEGORY_TO_VERTICAL[category]   # or DEFAULT_VERTICAL
  -> returns "beauty" | "supplements" | "mixed"

build_env_for_scenario(scenario_cfg, base_env=os.environ)
  -> copies base_env
  -> drops pre-existing VERTICAL_MODE / VERTICAL  # operator shell sanitization
  -> env["VERTICAL_MODE"] = vertical
  -> env["PYTHONPATH"]    = <repo_root>          # so subprocess can run from
                                                 #  any cwd (.env-free)
  -> sets ENGINE_V2_DECIDE / ENGINE_V2_OUTPUT / ENGINE_V2_SHADOW /
     ENGINE_V2_SIZING / STATS_NAN_FOR_HARDCODED / EVIDENCE_CLASS_ENFORCED
     (the canonical V2 flag stack)
  -> returns env

run_scenario(name, out_dir)
  -> subprocess.run(
       [python, "-m", "src.main", "--orders", ..., "--brand", name, "--out", out_dir],
       env=env,
       cwd=out_dir,     # tmp dir, no .env clobber
     )
  -> read_briefing_meta_vertical(out_dir)
     -> opens out_dir/receipts/engine_run.json
     -> returns briefing_meta["vertical"]
  -> returns ScenarioRunResult(declared_vertical, actual_vertical, ...)

assert_vertical_propagated(result)
  -> raises AssertionError if actual_vertical != declared_vertical
     OR if actual_vertical is None
```

The engine-side path that consumes this is unchanged: `src/engine_run_adapter.py::_briefing_meta_from_cfg` (line 296-304) reads `cfg.get("VERTICAL_MODE")` first, then `cfg.get("VERTICAL")`. With `VERTICAL_MODE` set in the subprocess env, `get_config()` in `src/utils.py` picks it up via the env-override loop (lines 681-683), and the adapter stamps it onto `EngineRun.briefing_meta.vertical`.

## Scenario Vertical: Before vs After

| Scenario | YAML `category` | Pre-Fix-6 `briefing_meta.vertical` | Post-Fix-6 `briefing_meta.vertical` | Match |
|---|---|---|---|---|
| `healthy_beauty_240d` | `beauty` | `beauty` (incidentally correct) | `beauty` | OK |
| `healthy_beauty_low_inventory_240d` | `beauty` | `beauty` (incidentally correct) | `beauty` | OK |
| `supplement_replenishment_240d` | `supplement` | `beauty` (the Fix 6 defect) | **`supplements`** | OK |
| `small_store_240d` | `lifestyle` | `beauty` (no scenario-specific propagation) | `mixed` | OK |
| `cold_start_45d` | `beauty` | `beauty` (incidentally correct, but engine crashed pre-Fix-1) | `beauty` | OK |
| `promo_anomaly_240d` | `beauty` | `beauty` (incidentally correct) | `beauty` | OK |

All 6 scenarios now stamp the declared vertical. The supplement scenario (the one the e2e review explicitly called out as wrong) now correctly runs as `supplements`. The lifestyle (`small_store`) scenario now runs as `mixed` (no engine vertical for "lifestyle" exists; `mixed` is the closest match per the mapper documentation).

## Exact Commands Run

```
# 1. Run new tests (unit-level only).
python -m pytest tests/test_matrix_vertical_propagation.py -v
# 36 collected -> 34 passed, 2 skipped (E2E tests opt-in)

# 2. Run end-to-end (opt-in) — proves the env makes it to engine_run.json.
RUN_VERTICAL_PROPAGATION_E2E=1 \
  python -m pytest \
    tests/test_matrix_vertical_propagation.py::TestEndToEndVerticalPropagation -v
# 2 passed (initial run with no harness cwd-escape: 1 failed, 1 passed —
#  expected, that surfaced the .env clobber. Fixed by setting cwd to tmp
#  and PYTHONPATH to repo root.)

# 3. Manual all-six-scenarios run (script).
python -c "...run_scenario for all 6 ... print result..."
# All 6 produced engine_run.json with the expected vertical.
# (See "Scenario Vertical: Before vs After" table.)

# 4. Golden diff (no re-baseline).
python -m pytest tests/test_golden_diff.py -v
# 3 passed.

# 5. Full suite.
python -m pytest tests/ -q
# 657 passed, 14 skipped, 0 failed.
```

## Tests / Checks Run

| Check | Result |
|---|---|
| `tests/test_matrix_vertical_propagation.py` (NEW) — unit tests | 34 passed, 2 skipped (opt-in E2E) |
| `tests/test_matrix_vertical_propagation.py::TestEndToEndVerticalPropagation` (opt-in) | 2 passed (supplement + beauty real subprocess runs) |
| Manual all-six-scenarios E2E (`run_scenario` for each) | 6/6 declared == actual; all rc=0 |
| `tests/test_golden_diff.py` | 3 passed (no re-baseline) |
| Full suite `pytest tests/ -q` | **657 passed, 14 skipped, 0 failed** |

Pre-Fix-6 baseline (post-Fix-5) was 621 passed + 12 skipped.
Post-Fix-6 is 657 passed + 14 skipped — exactly +36 new tests added, +2 new opt-in skips, with no previously-passing test moving.

## Goldens

`tests/test_golden_diff.py`: 3 fixtures (`small_sm`, `mid_shopify`, `micro_coldstart`) all pass byte-for-byte against the pinned golden tree. No file under `tests/golden/` was modified. No `--baseline` / `--regenerate` invocation was used. No engine code was touched in this fix, so legacy goldens cannot move.

## Behavior Changes

- A new harness module exists at `tests/synthetic_harness.py`. Other tests / scripts can import from it.
- A new test file `tests/test_matrix_vertical_propagation.py` is collected by pytest and adds 36 tests (34 always-on + 2 opt-in E2E).
- No engine behavior changes. No `src/` files touched. No flag defaults changed. No materiality / sizing / decision-state semantics changed.
- Fix 1 (cold-start chart None-safety): unchanged. Fix 2 (targeting-measurement invariant): unchanged. Fix 3 (ABSTAIN_SOFT contract): unchanged. Fix 4 (inventory-blocked wiring): unchanged. Fix 5 (materiality footer): unchanged.
- M0 goldens (legacy): byte-identical.

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/synthetic_harness.py` — new harness module.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_matrix_vertical_propagation.py` — new test file.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-synthetic-fix-6-summary.md` — this summary.

## Remaining Risks

1. **The repo's `.env` file still clobbers env vars when `python-dotenv` is not installed.** `src/utils.py::14-27` has a manual `.env` fallback that unconditionally overwrites `os.environ`. The harness escapes this by running the subprocess from a `.env`-free cwd plus `PYTHONPATH=<repo_root>`. If a future contributor reorganizes the harness to run from the repo root, the propagation will silently break. The unit test `test_pythonpath_includes_repo_root` and the documented note in `synthetic_harness.run_scenario` are the forcing functions. Fixing the manual `.env` fallback to use `setdefault` is out of Fix 6's scope but would be a one-line follow-up that benefits all callers.
2. **`python-dotenv`-installed environments behave differently from non-installed ones.** The harness's `.env`-free cwd avoids the difference, but a future test author running ad-hoc shell commands inside the repo root (without going through the harness) will silently get the `.env`'s `VERTICAL_MODE=beauty` regardless of any `VERTICAL_MODE=...` they prepend. This is the original Fix 6 defect and only harness invocations are protected.
3. **The harness assumes the V2 flag stack is the canonical configuration.** Default invocation enables `ENGINE_V2_*` flags and the M4 evidence flags so the matrix exercises the V2 path (matching the e2e review's intent). A caller wanting to test the legacy path can pass `extra_v2_flags=False`. If the V2 default ever flips, this harness default may become redundant or wrong-direction; revisit with M10 cleanup.
4. **`small_store_240d` (`lifestyle`) maps to `mixed` not a dedicated lifestyle vertical.** The engine has no `lifestyle` `VERTICAL_MODE`. `mixed` is the closest match per `src/utils.py::VERTICAL_CONFIG`. If a future PM wants a dedicated lifestyle vertical, the engine work is bigger than a mapping change.
5. **Opt-in E2E tests (`RUN_VERTICAL_PROPAGATION_E2E=1`) take ~30-60s per scenario and are skipped by default.** A future CI contributor who wants to run them must opt in. Pin against documentation drift via the unit-level tests, which always run.
6. **`ScenarioRunResult.briefing_html_path` returns the `<out_dir>/briefings` directory, not a specific file.** Fix 7 (reporter rewrite) will need to glob the briefings dir to find the per-brand HTML. Out of scope for Fix 6.

## Readiness Assessment For Fix 7

Ready to proceed to Fix 7 (reporter rewrite to parse `briefing.html` DOM via BeautifulSoup). Specifically:

- Full suite (657 passed, 14 skipped) is clean; no goldens re-baselined.
- The synthetic harness now produces durable per-scenario `engine_run.json` artifacts via `run_scenario()`. Fix 7's reporter can consume these (reporter must NOT read `recommendations[]` / `considered[]` for state inference; it may read `briefing_meta.vertical` for context, which Fix 6 now guarantees is correct).
- The deferred matrix-wide regression test from Fix 2 (assert no targeting card carries non-null measurement across all six fixture engine_run.json files) becomes implementable once Fix 7 lands and the harness can iterate over per-scenario receipts.
- No code-level discovery from Fix 6 changes the planned shape of Fix 7. Fix 7 is a pure harness-layer reporter; the harness scaffolding is already in place.
- BeautifulSoup is not yet a project dependency. Per the IM plan, Fix 7 will add it to `requirements.txt`.

## Git Status

Per convention, changes are NOT committed. Files left unstaged so the user can review the diff before committing. Current state at the close of Fix 6:

- 1 new harness module: `tests/synthetic_harness.py`.
- 1 new test file: `tests/test_matrix_vertical_propagation.py`.
- 1 new doc file: this summary.
- No `src/` files modified.
- No prior-fix files modified.

`memory.md`, the prior-fix files (`tests/test_charts_none_safe.py`, `tests/test_targeting_measurement_invariant.py`, `tests/test_abstain_soft_no_recommendations.py`, `tests/test_inventory_blocked_in_considered.py`, `tests/test_materiality_footer_present.py`, `src/charts.py`, `src/engine_run.py`, `src/storytelling_v2.py`, `src/decide.py`, `src/detect.py`, `src/main.py`, `src/engine_run_adapter.py`, and the prior-fix summaries) remain unstaged from Fixes 1-5 per the prior-pass briefs.
