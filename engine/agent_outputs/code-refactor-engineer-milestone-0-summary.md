# Milestone 0 — Code Refactor Engineer Summary

_Completed: 2026-05-01 (engine-rework branch)_

## Approved scope

Implement only Milestone 0 of `agent_outputs/implementation-manager-overhaul-plan-final.md`:
freeze current engine outputs as golden fixtures so subsequent milestones can
prove "no regression with flag off." Six tickets: T0.1 fixtures, T0.2 freeze
script, T0.3 pytest, T0.4 `_FORCE_SINGLE_WINDOW` cleanup, T0.5 flag inventory
doc, T0.6 default-test integration.

## Files changed

### New files
- `tests/fixtures/merchants.yaml` — 3 pinned merchants (micro/cold-start, small `SM_*`, mid Shopify) with anchor dates and notes (T0.1).
- `scripts/freeze_golden.py` — driver that runs the engine end-to-end per merchant, normalizes non-deterministic fields, and writes golden artifacts. Supports `--regenerate` and `--merchant <id>` (T0.2).
- `tests/test_golden_diff.py` — pytest that re-runs the engine for each merchant and diffs against `tests/golden/{id}/`. Failure prints unified diff and instructs the dev how to regenerate (T0.3).
- `tests/golden/micro_coldstart/`, `tests/golden/small_sm/`, `tests/golden/mid_shopify/` — frozen artifacts (briefing.html + 6 receipts JSON files per merchant; ~320 KB total).
- `docs/engine_flags.md` — full flag inventory: 50+ keys via `DEFAULTS`, plus 14 direct `os.getenv` reads, plus 12 forward-looking flags scheduled by later milestones, with per-flag M10 disposition (T0.5).
- `Makefile` — `make test`, `make golden-test`, `make golden-regenerate` targets. No GitHub Actions added (none existed; plan said don't add) (T0.6).
- `agent_outputs/code-refactor-engineer-milestone-0-summary.md` — this file.

### Edited files
- `src/action_engine.py` — `select_actions` (around line 3785): replaced hardcoded `cfg['_FORCE_SINGLE_WINDOW'] = False` with `cfg.setdefault('_FORCE_SINGLE_WINDOW', False)` and rewrote the comment to explain the M0 cleanup (T0.4).
- `src/utils.py` — added `_FORCE_SINGLE_WINDOW: False` to `DEFAULTS` and added the key to the bool-coerce set in `_coerce()` so `.env` overrides parse correctly (T0.4).

## Exact commands run (and outcomes)

| Command | Result |
|---|---|
| `python -m src.main --orders data/shopify_orders_micro_*.csv --brand test_micro --out /tmp/...` | pass — engine ran end-to-end |
| `python -m src.main --orders data/SM_orders.csv --brand test_sm --out /tmp/...` | pass — 3 PRIMARY actions selected |
| `python -m src.main --orders data/shopify_orders_small.csv --brand test_small --out /tmp/...` | pass |
| `python -m src.main --orders data/shopify_orders_mid.csv --brand test_mid --out /tmp/...` | pass |
| `python scripts/freeze_golden.py --regenerate` | pass — wrote 3 golden trees |
| `python -m pytest tests/test_golden_diff.py -v` | **3 passed in 27.82s** |
| `make golden-test` | **3 passed** |
| `make test` | **3 passed** |
| `python scripts/freeze_golden.py --merchant micro_coldstart` (dry-run) | pass — `all 1 merchant(s) match golden` |
| Probe: edited `tier = "moderate" -> "moderate_GOLDEN_PROBE"` in `src/utils.py:2086`, ran `pytest`, **1 failed** (mid_shopify drift detected with unified diff), then reverted | pass — confirms test is not vacuous |

After revert, full pytest still passes 3/3.

## Tests/checks run

- `pytest tests/test_golden_diff.py -v` (3 parametrized cases, all pass).
- Manual end-to-end smoke runs against all 3 fixture CSVs before and after the T0.4 edit; `diff` of `_briefing.html` between two runs is empty (zero bytes drift); `run_summary.json` matches modulo path-bearing fields (charts_abs, segments).
- Anti-vacuity probe: deliberate constant change triggers a clean failure with a unified diff.

## Artifacts created

```
tests/fixtures/merchants.yaml
scripts/freeze_golden.py
tests/test_golden_diff.py
docs/engine_flags.md
Makefile
tests/golden/
  micro_coldstart/
    briefing.html
    receipts/{run_summary,actions_log,validation_report,engine_validation_report,dataframe_debug,df_for_charts_counts}.json
  small_sm/
    briefing.html
    receipts/{...same 6 files...}
  mid_shopify/
    briefing.html
    receipts/{...same 6 files...}
agent_outputs/code-refactor-engineer-milestone-0-summary.md
```

Total golden footprint: ~320 KB (small enough to commit).

## Behavior changes

None merchant-facing. The only code-path change is T0.4: a hardcoded
`cfg['_FORCE_SINGLE_WINDOW'] = False` was replaced with
`cfg.setdefault('_FORCE_SINGLE_WINDOW', False)`. Verified by:

- Grep confirms no caller in the codebase passes `_FORCE_SINGLE_WINDOW` in cfg.
- All three fixture briefings produced byte-identical HTML in two consecutive runs.
- Pytest still passes after the edit.

## Normalization rules (so reviewers know what gets ignored)

The freeze script and pytest apply identical normalization:

- ISO-8601 timestamps (full match) anywhere in JSON values -> `<TIMESTAMP>`.
- Dict values under any key in `{ts, timestamp, validation_timestamp, generated_at, updated_at}` -> `<TIMESTAMP>`.
- Dict values under `run_id` -> `<RUN_ID>`.
- Any string containing the per-run output dir path -> rewritten to `<RUN_ROOT>` (handles macOS `/private/...` aliasing).
- HTML content gets the same string-level normalization.

Captured artifacts per merchant (whitelist; everything else is discarded as
noise): `briefing.html` plus six receipts JSON files. Charts (PNGs), segments
ZIPs, copy assets, and per-run debug CSVs are NOT in the golden set — they
are non-deterministic by construction (zip metadata, matplotlib font glyph
warnings, etc.) and would force frequent benign regenerations.

## Skipped items

None. T0.4 was completed without skipping; verified zero-behavior-change.

## Readiness for Milestone 1

Green to start M1. The golden harness is deterministic, the test is
sensitivity-verified, and the cfg surface for `_FORCE_SINGLE_WINDOW` is
explicit. Open items the M1 author should be aware of:

1. **`engine_run.json` golden coverage**: M1 will add `receipts/engine_run.json`. The freeze script's `RECEIPTS_FILES_TO_FREEZE` whitelist needs that filename appended, and goldens regenerated, when M1 lands. Document this in the M1 PR description.

2. **Path normalization**: per-run absolute paths under `charts_abs` / `segments` in `run_summary.json` are stripped to `<RUN_ROOT>`-relative form. If M1 surfaces additional path-bearing fields, the normalization helper in `scripts/freeze_golden.py:_normalize_json_obj` handles them automatically (path stripping runs over every string value), but verify with a regenerate + diff cycle.

3. **Anchor dates are implicit**: `tests/fixtures/merchants.yaml` records anchor dates for documentation, but the engine still derives anchors from the CSV's max `Created at`. If a future ticket adds explicit `--anchor` support to `main.py`, the fixture YAML is the canonical source — wire the freeze script to pass it through.

4. **No CI**: There is no GitHub Actions workflow (none existed; plan said don't add). The Makefile target is the local entry point. If/when CI is set up, point it at `make test`.

5. **Charts and segments not in golden**: If a future milestone wants chart determinism, that needs a separate ticket (matplotlib font fallback warnings already produce noise).

6. **Mid_shopify is the most diff-sensitive fixture**: in the anti-vacuity probe it was the merchant whose aura score landed in the 50-65 band and surfaced the drift. Small_sm and micro_coldstart didn't. M4 reviewers should expect mid_shopify to be the loudest signal during decision-logic surgery.
