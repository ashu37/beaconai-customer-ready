# Code Refactor Engineer - Synthetic Blocker Fix 7 Summary

_Date: 2026-05-04_
_Scope: Fix 7 ONLY from `agent_outputs/implementation-manager-synthetic-blocker-fix-plan.md`._

## Approved Scope

DOM-only synthetic reporter. The reporter must compute every merchant-visible scenario field by parsing the rendered `briefing.html` via BeautifulSoup. It must NOT consult `candidate_debug.json`, `engine_run.recommendations[]`, `engine_run.considered[]`, `engine_run.watching[]`, `v2_sizing_shadow.json`, `receipts/debug.html`, or `actions_log.json` for state inference. It MAY read `engine_run.json::briefing_meta` (vertical / scenario id) and `engine_run.abstain.state` for context only -- never to drive the visible counts/flags.

This is a pure harness/test-utility change. No engine source files touched. No engine decision logic, renderer behavior, or V2 product contract change. No re-baselining of goldens.

## Patch Summary

1. New module `tests/synthetic_reporter.py` with:
   - `ScenarioReport` dataclass: scenario name, declared vs. rendered vertical, decision_state_internal (CONTEXT-only), `visible_recommended_count`, `visible_considered_count`, `visible_watching_count`, `abstain_soft_callout_present`, `abstain_hard_memo_present`, `materiality_footer_present`, `product_contract_pass` (None today; not encoded), `notes`.
   - DOM helpers: `count_recommended_cards`, `count_considered_cards`, `count_watching_rows`, `detect_abstain_soft_callout`, `detect_abstain_hard_memo`, `detect_materiality_footer`.
   - Public API: `report_briefing(scenario_name, briefing_html_path, engine_run_json_path=None, declared_vertical=None)` and `report_run_dir(scenario_name, out_dir, declared_vertical=None, brand=None)`.
   - Pretty-printer `format_report_table(rows)` with the rendered_vertical / decision_state_internal columns explicitly labelled `DBG`/`CONTEXT` so any future caller cannot mistake them for merchant-visible state.
   - `MATERIALITY_FOOTER_SUBSTRING` constant pinning the Phase 5.4 load-bearing copy: `"We only recommend primary plays that could realistically add at least"`.
   - `_read_engine_run_context()` reads ONLY `briefing_meta.vertical` and `abstain.state`. No other JSON fields are touched.
2. New test file `tests/test_reporter_dom_only.py` with 17 tests covering all six required cases plus negative / regression tests.
3. `requirements.txt`: added `beautifulsoup4>=4.12.0`.

The reporter integrates cleanly with the Fix 6 harness (`tests/synthetic_harness.py`): the harness's `ScenarioRunResult` already exposes `out_dir` and `briefing_html_path`, and `report_run_dir(out_dir=..., brand=...)` wraps directly around that.

## Files Changed

- **NEW** `/Users/atul.jena/Projects/Personal/beaconai/tests/synthetic_reporter.py` -- DOM-only reporter module.
- **NEW** `/Users/atul.jena/Projects/Personal/beaconai/tests/test_reporter_dom_only.py` -- 17 tests, all passing.
- **MODIFIED** `/Users/atul.jena/Projects/Personal/beaconai/requirements.txt` -- added `beautifulsoup4>=4.12.0`.
- **NEW** `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-synthetic-fix-7-summary.md` -- this summary.

No `src/` files modified. No prior-fix files touched. No goldens re-baselined.

## Selectors Actually Used

Verified against `src/storytelling_v2.py` and `agent_outputs/phase5_samples/beauty_brand_v2_briefing.html`:

| Field | Selector(s) | Source in `storytelling_v2.py` |
|---|---|---|
| Recommended cards | `section.recommended article.play-card` minus any with class `play-card--rejected` | `render_recommended_section` (line 624+); card classes from `MEASURED_CARD_CLASS` / `DIRECTIONAL_CARD_CLASS` / `TARGETING_CARD_CLASS` (lines 100-104) |
| Considered cards | `section.considered article.play-card.play-card--rejected` | `REJECTED_CARD_CLASS = "play-card play-card--rejected"` (line 107); rendered inside `section.considered` (line 747) |
| Watching rows | `section.watching ul.watching-list li.watching-row`; falls back to `section.watching li.watching-row` | `render_watching_section` (line 762+); list class `watching-list` (line 795), row class `watching-row` (line 784) |
| ABSTAIN_SOFT callout | `div.abstain-callout.abstain-callout--soft`; falls back to `.abstain-callout--soft` | `render_recommended_section` (lines 650-655) |
| ABSTAIN_HARD memo | `main.briefing-v2--abstain-hard`; OR `p.abstain-hard__reason`; OR `li.abstain-hard__flag`; OR `section.abstain-hard` | `render_abstain_hard_memo` (line 887+); `<main class="briefing-v2 briefing-v2--abstain-hard">` at line 926 |
| Materiality footer | substring `"We only recommend primary plays that could realistically add at least"` searched within `footer.dq-footer`, falling back to whole-document text | `render_data_quality_footer` (line 840-848) |

### Deviations from suggested selectors

- **Watching rows**: The brief suggested `section.watching li.watching-row`. The renderer wraps rows in `ul.watching-list` (line 795 of `storytelling_v2.py`). The reporter prefers the `ul.watching-list li.watching-row` path and falls back to the loose form. This is a strict superset of the brief's suggestion.
- **ABSTAIN_HARD memo**: The brief suggested "class markers from the V2 abstain-hard renderer". The reporter checks four markers in priority order: the top-level `main.briefing-v2--abstain-hard` wrapper (most specific), then `p.abstain-hard__reason`, `li.abstain-hard__flag`, and `section.abstain-hard`. Any one is sufficient. This handles both the canonical full-memo render and any future partial render.
- **Materiality footer**: The brief allowed "text containing ...". The reporter scopes the search to `footer.dq-footer` first (where the renderer puts the line at lines 845-849) and falls back to the whole document so a misplaced rendering still surfaces as "present" -- the test of merchant visibility is what matters.
- **ABSTAIN_SOFT callout**: The brief suggested `.abstain-callout--soft`. The reporter prefers `div.abstain-callout.abstain-callout--soft` (the renderer emits both classes -- line 651) and falls back to the lenient form.

All selectors verified against the live Phase 5 sample HTML (1 Recommended, 6 Considered, 2 Watching, materiality footer present, no abstain callouts) and against the live end-to-end renders for all six synthetic scenarios.

## Artifacts No Longer Read for Merchant-Visible State

The reporter explicitly does NOT open any of these for state inference:

- `receipts/candidate_debug.json` -- decoy file in test 6 confirms the reporter never opens it.
- `engine_run.recommendations[]` -- test 3 (`test_mutating_engine_run_recommendations_does_not_change_dom_counts`) injects 100 fake recommendations into `engine_run.json` and confirms `visible_recommended_count` still derives from the DOM (returns 0 for the ABSTAIN_SOFT fixture).
- `engine_run.considered[]` -- never read.
- `engine_run.watching[]` -- never read.
- `v2_sizing_shadow.json` -- decoy file in test 6 confirms it is never opened.
- `receipts/debug.html` -- decoy file in test 6 confirms it is never opened.
- `actions_log.json` -- decoy file in test 6 confirms it is never opened.

The negative test (`test_reporter_does_not_read_forbidden_artifacts`) monkey-patches `builtins.open` and asserts the reporter never opens any forbidden basename even when those files are physically present in the run directory.

`engine_run.json::briefing_meta.vertical` and `engine_run.json::abstain.state` ARE read, but only as CONTEXT fields surfaced on the report row as `rendered_vertical` and `decision_state_internal`. They are NEVER used to compute any of the visible counts/flags. The pretty-printer labels both columns `DBG` / `CONTEXT` so consumers cannot mistake them.

## Tests / Checks Run

| Check | Result |
|---|---|
| `pytest tests/test_reporter_dom_only.py -v` | **17 passed** in 0.08s |
| `pytest tests/test_golden_diff.py -v` | **3 passed** (no re-baseline) |
| `RUN_VERTICAL_PROPAGATION_E2E=1 pytest tests/test_matrix_vertical_propagation.py -q` | **38 passed** (Fix 6 unaffected) |
| `pytest tests/ -q` (full suite) | **674 passed, 14 skipped** in 112s |
| End-to-end matrix run (all 6 scenarios) + new reporter | All 6 produced briefing.html, reporter agreed with merchant view |

Pre-Fix-7 baseline (post-Fix-6) was 657 passed + 14 skipped. Post-Fix-7 is 674 passed + 14 skipped -- exactly +17 new tests added with no previously-passing test moving.

## Behavior Changes

- A new harness module exists at `tests/synthetic_reporter.py`. Other tests / scripts can import from it.
- A new test file `tests/test_reporter_dom_only.py` is collected by pytest and adds 17 tests.
- `requirements.txt` now lists `beautifulsoup4>=4.12.0`.
- No engine behavior changes. No `src/` files touched. No flag defaults changed. No materiality / sizing / decision-state / renderer semantics changed.
- Fixes 1-6 unchanged. M0 goldens (legacy): byte-identical.

## Sample Before / After Reporter Row

End-to-end run on all six scenarios with the new reporter (DOM-only). Compare against the prior reporter's claims as documented in `agent_outputs/synthetic-phase5-e2e-final-review.md` lines 79-84 (the table titled "Merchant-Visible vs Internal Artifact Mismatch").

| Scenario | Prior reporter (internal-JSON-derived) | Fix 7 reporter (DOM-derived) | Briefing actually shows |
|---|---|---|---|
| `healthy_beauty_240d` | "2 pilot, 6 considered, 1 watching" | rec=0, con=6, watch=1, soft=Y, hard=N, matfoot=Y | 0 Recommended, 6 Considered, 1 Watching, ABSTAIN_SOFT callout, materiality footer |
| `healthy_beauty_low_inventory_240d` | "1 pilot, 6 considered, 1 watching" | rec=0, con=6, watch=1, soft=Y, hard=N, matfoot=Y | 0 Recommended, 6 Considered, 1 Watching, ABSTAIN_SOFT callout, materiality footer |
| `supplement_replenishment_240d` | "1 PRIMARY, 6 considered, 2 watching" | rec=0, con=6, watch=2, soft=Y, hard=N, matfoot=Y | 0 Recommended, 6 Considered, 2 Watching, ABSTAIN_SOFT callout, materiality footer; vertical now correctly `supplements` (Fix 6) |
| `small_store_240d` | "0 actions, 6 considered, 0 watching" | rec=0, con=6, watch=0, soft=Y, hard=N, matfoot=Y | 0 Recommended, 6 Considered, 0 Watching, ABSTAIN_SOFT callout, materiality footer |
| `cold_start_45d` | "crash" | rec=0, con=0, watch=0, soft=N, hard=Y, matfoot=Y | ABSTAIN_HARD memo (Fix 1 unblocked) |
| `promo_anomaly_240d` | "2 actions, 6 considered, 0 watching" | rec=0, con=6, watch=0, soft=Y, hard=N, matfoot=Y | 0 Recommended, 6 Considered, 0 Watching (Fix 3 routed targeting cards into Considered), ABSTAIN_SOFT callout, materiality footer |

The prior reporter labeled `promo_anomaly_240d` "2 actions" while the merchant saw an internally-contradictory page (Fix 3 since closed that contract gap). The Fix 7 reporter now reports `rec=0` -- matching the merchant view exactly.

The new pretty-printed table (with explicit DBG / CONTEXT labels):

```
scenario                            | vert(declared) | vert(rendered:DBG) | rec | con | watch | soft | hard | matfoot | state(DBG)
----------------------------------- | -------------- | ------------------ | --- | --- | ----- | ---- | ---- | ------- | ----------
healthy_beauty_240d                 | beauty         | beauty             | 0   | 6   | 1     | Y    | N    | Y       | abstain_soft
healthy_beauty_low_inventory_240d   | beauty         | beauty             | 0   | 6   | 1     | Y    | N    | Y       | abstain_soft
supplement_replenishment_240d       | supplements    | supplements        | 0   | 6   | 2     | Y    | N    | Y       | abstain_soft
small_store_240d                    | mixed          | mixed              | 0   | 6   | 0     | Y    | N    | Y       | abstain_soft
cold_start_45d                      | beauty         | beauty             | 0   | 0   | 0     | N    | Y    | Y       | abstain_hard
promo_anomaly_240d                  | beauty         | beauty             | 0   | 6   | 0     | Y    | N    | Y       | abstain_soft
```

## BeautifulSoup Dependency

`beautifulsoup4` was NOT a project dependency before this fix. Added to `requirements.txt` with the conservative pin `beautifulsoup4>=4.12.0`. Version 4.14.3 (and `soupsieve` 2.8.3) is what the working env has installed; both are widely deployed and license-compatible. No alternate parser dependency introduced -- the reporter uses `html.parser` (stdlib) so `lxml` is NOT required.

## Goldens

`tests/test_golden_diff.py`: 3 fixtures (`small_sm`, `mid_shopify`, `micro_coldstart`) all pass byte-for-byte against the pinned golden tree. No file under `tests/golden/` was modified. No `--baseline` / `--regenerate` invocation was used. No engine code was touched in this fix, so legacy goldens cannot move.

## Exact Commands Run

```
# 1. Install BeautifulSoup (added to requirements.txt).
pip install beautifulsoup4

# 2. New reporter tests.
python -m pytest tests/test_reporter_dom_only.py -v
# 17 passed

# 3. Golden diff (no re-baseline).
python -m pytest tests/test_golden_diff.py -v
# 3 passed

# 4. Fix 6 harness + opt-in E2E (still green).
RUN_VERTICAL_PROPAGATION_E2E=1 \
  python -m pytest tests/test_matrix_vertical_propagation.py -q
# 38 passed

# 5. Full suite.
python -m pytest tests/ -q
# 674 passed, 14 skipped

# 6. End-to-end matrix on all 6 scenarios with the new reporter wired in.
python3 -c "<harness + reporter integration; see summary body>"
# All 6 rc=0; reporter agrees with merchant view; no claim of pilot/PRIMARY
# unless those words actually appear in the merchant-facing HTML.
```

## Remaining Risks

1. **`html.parser` is stdlib but slower than `lxml` for huge HTML.** Synthetic briefings are <100KB; not a concern at this scale. If the matrix grows by ~100x, switching to `lxml` is a one-line change in `_parse_html`.
2. **Selectors are pinned to the current `storytelling_v2.py` class names.** A future renderer that adds a new wrapper section (e.g., a "Highlights" hero strip with `play-card` markup) without restricting to `section.recommended` could shift counts. Mitigation: the reporter scopes the Recommended/Considered/Watching selectors to their parent sections so a new sibling section cannot bleed into the count. The test `test_phase5_pinned_briefing_dom_counts` is the forcing function.
3. **`product_contract_pass` is `None` today.** The reporter does not yet encode a per-scenario pass/fail verdict because the pass/fail rules in the IM plan's Scenario Acceptance Matrix are policy that lives in `agent_outputs/`, not on the briefing. A future ticket can add a `verdict` layer that consumes `ScenarioReport` rows and the matrix; this is explicitly out of Fix 7 scope.
4. **The reporter classifies a scenario's vertical as a CONTEXT-only field.** Some founder-facing dashboards may want to render the vertical badge from this field; that is fine because the field is SOURCED from `briefing_meta.vertical` (which the renderer also stamps), not from any state-inference path.
5. **Decoy-file negative test relies on monkeypatching `builtins.open`.** Future contributors who add direct `Path.open()` calls (which bypass `builtins.open`) could regress the no-forbidden-read invariant without the test catching it. Mitigation: the reporter uses `Path.read_text()` and `open(...)` consistently today; a future audit can add Path.open monkeypatching if needed.

## Readiness Assessment for Fixes 8-11 (Fixture Retuning)

**Reporter is trustworthy enough to drive fixture-retuning work.**

Specifically:

- The reporter no longer claims "pilot" / "PRIMARY" unless those words are visible in the merchant-facing HTML. End-to-end matrix run confirms this on all six scenarios.
- Counts are DOM-derived and stable: `promo_anomaly_240d` reports `rec=0` (Fix 3 contract enforced), `cold_start_45d` reports `hard=Y` (Fix 1 unblocked), `supplement_replenishment_240d` reports `vertical=supplements` (Fix 6 propagated).
- Selectors are pinned in `tests/test_reporter_dom_only.py` so any future renderer drift will fail tests immediately.
- The reporter's `format_report_table` produces a per-scenario row that fixture authors can A/B against pre/post-retune to see exactly what changed for the merchant.
- The unit + matrix test split (`test_reporter_dom_only.py` for the reporter; `test_matrix_vertical_propagation.py` for the harness; the harness plus reporter together for end-to-end) covers the cross-cutting contract that Fixes 8-11 will rely on:
  - Fix 8 (`healthy_beauty_240d` L28 retune) -- can be validated by a `rec >= 1 AND directional` row from the reporter, OR confirmed-deferred when the post-retune row is still `rec=0 con=6`.
  - Fix 9 (`supplement_replenishment_240d` realism) -- can be validated by reporter showing non-degenerate Considered audience sizes (the reporter exposes the cards; size detail can be added as a future enhancement to the report row, but the existence of the cards is already DOM-visible).
  - Fix 10 (`promo_anomaly_240d` anchor/spike) -- can be validated by reporter showing either `hard=Y` (anomaly DQ flag fired) or `soft=Y AND rec=0` (Fix 3 contract).
  - Fix 11 (`low_inventory` runner-clock alignment) -- can be validated by Fix 4's `inventory_blocked` reason code surfacing as a Considered card with the merchant-readable copy on the DOM.

No code-level discovery from Fix 7 changes the planned shape of Fixes 8-11. The reporter is the right base for the fixture-retune iteration loop.

## Git Status

Per convention, changes are NOT committed. Files left unstaged so the user can review the diff before committing. Current state at the close of Fix 7:

- 1 new harness module: `tests/synthetic_reporter.py`.
- 1 new test file: `tests/test_reporter_dom_only.py`.
- 1 modified config: `requirements.txt` (one-line addition).
- 1 new doc file: this summary.
- No `src/` files modified.
- No prior-fix files modified.
