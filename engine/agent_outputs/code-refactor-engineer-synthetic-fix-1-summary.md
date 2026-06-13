# Code Refactor Engineer — Synthetic Blocker Fix 1 Summary

_Date: 2026-05-04_
_Scope: Fix 1 ONLY from `agent_outputs/implementation-manager-synthetic-blocker-fix-plan.md`._

## Approved Scope

Cold-start defensive one-liner in `src/charts.py:273-274`. Goal: `cold_start_45d` synthetic fixture must complete and produce a renderable `briefing.html` instead of crashing in chart rendering when the per-window `recent` / `prior` series contain `None`.

Strict Non-Goals (not touched in this pass):
- No Fix 2 / Fix 3 / Fix 4 / Fix 5 / Fix 6 / Fix 7.
- No V2 decision logic change.
- No materiality floor change.
- No renderer semantics change.
- No golden re-baselining.
- No architectural reorder of V2 ABSTAIN_HARD upstream of chart rendering (Phase 6).

## Patch Summary

`src/charts.py` `create_action_multiwindow_chart()` previously called `ax.bar(...)` directly on the `recent` and `prior` lists. When a row carried `None` (the cold-start case where one window has data and another does not), matplotlib raised `TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'`. The fix filters `None` per-series with a paired x-index list, using `is not None` (NOT truthiness) so that zero metric values are preserved. If a series has no surviving values it is skipped entirely; the other series still renders.

### Before

```python
recent = [row.get('recent') for row in rows]
prior = [row.get('prior') for row in rows]

ax.bar(x - width/2, recent, width, label='Recent', color='#3B82F6')
ax.bar(x + width/2, prior, width, label='Prior', color='#BFDBFE')
```

### After

```python
recent = [row.get('recent') for row in rows]
prior = [row.get('prior') for row in rows]

# Fix 1 (synthetic blocker): matplotlib's bar() raises TypeError when an
# element is None (common on cold-start / thin-history merchants). Filter
# None values per-series with a paired x index. Use `is not None`, NOT a
# truthiness check — zero is a legitimate metric value and must not be
# dropped. The architectural reorder (V2 ABSTAIN_HARD upstream of chart
# rendering) is deferred to Phase 6 per the synthetic blocker-fix plan.
recent_x = [x[i] - width / 2 for i, v in enumerate(recent) if v is not None]
recent_vals = [v for v in recent if v is not None]
prior_x = [x[i] + width / 2 for i, v in enumerate(prior) if v is not None]
prior_vals = [v for v in prior if v is not None]

if recent_vals:
    ax.bar(recent_x, recent_vals, width, label='Recent', color='#3B82F6')
if prior_vals:
    ax.bar(prior_x, prior_vals, width, label='Prior', color='#BFDBFE')
```

The downstream loop on lines 277-295 already handled `None` correctly via `[v for v in [...] if v is not None]` and a `delta is None` short-circuit, so it required no change.

## Files Changed

- `src/charts.py` (15-line patch within `create_action_multiwindow_chart`).
- `tests/test_charts_none_safe.py` (NEW — 5 regression tests pinning None-safety and zero-preservation).

## Exact Commands Run

```
python -m pytest tests/test_charts_none_safe.py -v
git stash && python -m pytest tests/test_charts_none_safe.py::test_create_action_multiwindow_chart_handles_none_in_recent -v ; git stash pop
python -m pytest tests/test_golden_diff.py -v
python -m pytest tests/
mkdir -p /tmp/cold_start_test_out
python -m src.main --orders tests/fixtures/synthetic/cold_start_45d_orders.csv --brand "cold_start_45d" --out /tmp/cold_start_test_out
```

## Tests / Checks Run

| Check | Result |
|---|---|
| `tests/test_charts_none_safe.py` (new) | 5 passed |
| Pre-fix verification (stashed patch, ran new test) | TypeError as expected — confirmed the test would have caught the regression |
| `tests/test_golden_diff.py` | 3 passed (no goldens re-baselined) |
| Full suite `pytest tests/` | 583 passed, 11 skipped, 0 failed |
| Manual e2e: `cold_start_45d` via `src.main` | Completed without traceback; `briefings/cold_start_45d_briefing.html` written (39,777 bytes) |

## `cold_start_45d` Before / After Behavior

**Before Fix 1.** End-to-end run on `tests/fixtures/synthetic/cold_start_45d_orders.csv` raised:

```
TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'
  at matplotlib/patches.py:797 in Rectangle._convert_units
  called from src/charts.py:273  ax.bar(x - width/2, recent, width, ...)
```

The legacy chart renderer crashed before any briefing HTML was produced.

**After Fix 1.** The same end-to-end run completes. `briefings/cold_start_45d_briefing.html` (39,777 bytes) is generated. Charts emit normally; per-window rows that have `None` for one series are simply skipped on that series (the other series still renders).

Note: this fixture is currently exercising the **legacy** renderer path (default flags-off), not V2 ABSTAIN_HARD. The legacy briefing renders with one PRIMARY play (`routine_builder`) and is not the V2 ABSTAIN_HARD memo. That's expected for Fix 1: the architectural reorder of V2 ABSTAIN_HARD upstream of chart rendering is explicitly Phase 6 per the plan, and this fix is intentionally narrow. The acceptance criterion (`cold_start_45d` produces a renderable briefing instead of crashing) is met.

## Goldens NOT Re-baselined

Confirmed. `tests/test_golden_diff.py` runs the three pinned merchants (`small_sm`, `mid_shopify`, `micro_coldstart`) and all three pass byte-exact against the existing golden fixtures. No file under `tests/golden/` was modified, and no `--baseline` / `--regenerate` invocation was used.

## Downstream Risks / Crashes Discovered

None during the cold_start_45d run. The defensive filter unblocked chart rendering and the run completed through briefing assembly without surfacing a downstream crash.

Two non-blocking items observed for awareness (NOT in scope, NOT addressed):

1. The legacy renderer happily produces a PRIMARY recommendation on `cold_start_45d` (45-day fixture) rather than the V2 ABSTAIN_HARD data-quality memo. This is the architectural concern the plan explicitly defers to Phase 6 ("V2 ABSTAIN_HARD upstream of chart rendering"). Fix 1 only addresses the crash; the merchant-honest abstain layout is a separate fix.
2. Running with the V2 flag stack (`ENGINE_V2_OUTPUT=true` etc.) was not exercised in the e2e check. Fix 1 is in the legacy chart path, which is the surface where the crash happens; whether V2 takes a different path on cold-start is a question for Fix 2 onwards.

If a downstream crash had appeared, the plan said to flag back rather than chase. None did.

## Readiness Assessment for Fix 2

Ready to proceed to Fix 2 (targeting-measurement invariant). Specifically:
- The full pytest suite is clean (583 passed), so Fix 2's structural unit test (`tests/test_targeting_measurement_invariant.py`) can be landed against a known-green baseline.
- No goldens were re-baselined, so Fix 2 starts with the same M0 contract.
- The matrix runner is now able to produce a `briefing.html` for `cold_start_45d` (no traceback), which is a precondition for the eventual matrix-wide regression test in Fix 2 (`test_matrix_no_targeting_with_measurement` reads each fixture's `engine_run.json`).

No code- or data-level discovery from Fix 1 changes the planned shape of Fix 2.

## Behavior Changes (Summary)

- `create_action_multiwindow_chart` no longer crashes when `recent` or `prior` per-row values are `None`.
- Zero values are preserved (forced by `is not None`, with explicit pinning test).
- For non-`None`-bearing inputs the bars are visually identical to before — same x positions, same widths, same colors.
- No change to legacy default-flags-off behavior on the three pinned goldens.
- No change to V2 evidence classes, materiality floors, decide() logic, renderer semantics, or any other contract.

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_charts_none_safe.py`

## Follow-Up Work (out of Fix 1 scope)

- Fix 2: targeting-measurement invariant (post-hoc clear in `engine_run_adapter.py` + matrix-wide regression test).
- Phase 6: V2 ABSTAIN_HARD architectural reorder upstream of chart rendering, so cold-start does not have to lean on the defensive filter to reach the data-quality memo.
