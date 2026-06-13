# Code Refactor Engineer — Phase 6A Ticket A1 Summary

_Date: 2026-05-05_
_Scope: Phase 6A Ticket A1 ONLY from `agent_outputs/implementation-manager-campaign-slate-plan.md`._

## Approved Scope

Reduce the V2 Watching section cap to **4** as a single source of truth, and pin a load-bearing-metric prioritization on `small_store_240d` so that — when any of `returning_customer_share`, `net_sales`, `repeat_rate_within_window`, or `aov` is computable — at least one Watching row whose metric is in that load-bearing set surfaces in the rendered briefing.

This is a **renderer + decide-layer-`build_watching`-only** change. No PlayCard schema changes. No `would_be_measured_by`. No new Recommended Experiment section. No priors metadata. No decide-layer eligibility filter for new role. No legacy renderer change. No materiality floor change. No goldens re-baselined. No fix to `src/load.py:626`. No AnomalousWindowCheck registration. No `empty_bottle` ct/lb parser. No causal prior added.

## Patch Summary

1. **`src/storytelling_v2.py`** — added a public constant `MAX_WATCHING_RENDERED: int = 4` and replaced the magic-number slice `items[:4]` in `render_watching_section` with `items[:MAX_WATCHING_RENDERED]`. The renderer-side cap is now a single source of truth.
2. **`src/decide.py`** — extended `_LOAD_BEARING_WATCH_METRICS` to include `aov`, matching the contract-final spec's named four. Added a load-bearing-first sort key in `build_watching` so load-bearing metrics surface ahead of non-load-bearing metrics regardless of magnitude (still sorted by `-magnitude` then metric name within each tier). Added a Phase 6A Ticket A1 **fallback branch**: when the HELD pass produces zero Watching candidates AND any MOVED observation is on a load-bearing metric, those MOVED load-bearing observations surface as Watching. This addresses the small_store_240d case where every load-bearing metric is volatile enough to be classified MOVED.
3. **`tests/test_decide.py`** — narrowed two M7 watching tests (`test_moved_observations_excluded`, `test_zero_change_excluded`) to use a non-load-bearing metric (`ctr` / `click_through_rate`). The original assertions used `aov`, which is now load-bearing per Phase 6A Ticket A1; the base contract — "MOVED non-load-bearing observations belong to the state-of-store paragraph, not Watching" / "flat non-load-bearing metrics are excluded" — is preserved with the metric swap.
4. **`tests/test_phase5_watching_signals.py`** — narrowed `test_non_load_bearing_zero_change_metric_still_excluded` to use a non-load-bearing metric (`click_through_rate`). Phase 5.3's load-bearing-flat behavior is otherwise untouched and still tested by the same file.
5. **`tests/test_render_v2.py`** — added `test_watching_section_caps_at_four_with_seven_signals_phase6a` that synthesizes 7 input signals and asserts exactly 4 rendered rows AND that `MAX_WATCHING_RENDERED == 4`. The pre-existing `test_watching_section_caps_at_four` (which used `<= 4`) is preserved; the new test tightens to `==` so a regression that drops the cap silently to 3 trips this test.
6. **`tests/test_watching_load_bearing_priority.py`** (NEW) — five tests:
   - `test_max_watching_rendered_constant_is_four`
   - `test_watching_section_caps_at_four_with_seven_signals` (synth 7 → 4 rows)
   - `test_build_watching_prefers_load_bearing_metrics_under_cap` (when 4 load-bearing + 2 non-load-bearing held movers exist with the non-load-bearing carrying LARGER magnitudes, all 4 surfaced rows are still load-bearing)
   - `test_build_watching_load_bearing_priority_does_not_break_phase5_3` (Phase 5.3 flat-load-bearing behavior preserved)
   - `test_small_store_240d_renders_at_least_one_load_bearing_watching_row` (end-to-end via the synthetic harness + DOM-parsing reporter; skip when the synthetic CSV is absent)

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/storytelling_v2.py`
  - Added `MAX_WATCHING_RENDERED = 4` constant (line ~106).
  - Replaced `items[:4]` with `items[:MAX_WATCHING_RENDERED]` in `render_watching_section` (line ~782).
- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py`
  - Extended `_LOAD_BEARING_WATCH_METRICS` to add `"aov"` (line ~684).
  - Updated `build_watching` docstring to describe the Phase 6A fallback (lines ~694–717).
  - Added the empty-HELD MOVED-load-bearing fallback loop (lines ~768–793).
  - Added load-bearing-first tier in the candidates sort key (lines ~798–812).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_decide.py`
  - Swapped `aov` → `ctr` in `test_moved_observations_excluded` and `click_through_rate` in `test_zero_change_excluded`.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_phase5_watching_signals.py`
  - Swapped `aov` → `click_through_rate` in `test_non_load_bearing_zero_change_metric_still_excluded`.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_render_v2.py`
  - Added `test_watching_section_caps_at_four_with_seven_signals_phase6a` directly after the existing `test_watching_section_caps_at_four`.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_watching_load_bearing_priority.py` (NEW)

No `src/storytelling.py` (legacy renderer), no `actions_log.json` writer, no `engine_run.py` schema, no `priors_loader.py`, no `priors.yaml`, no `main.py`, no `utils.py` were modified.

## Cap Source of Truth

- **Renderer-side cap**: `src.storytelling_v2.MAX_WATCHING_RENDERED = 4` (`src/storytelling_v2.py` line ~106).
- **Builder-side cap**: `src.decide.MAX_WATCHING_SIGNALS = 4` (`src/decide.py` line ~106; pre-existing since M7).

Both are 4. The renderer takes the builder's already-capped list and re-applies its own slice defensively. No third cap exists in the codebase. No `7` cap exists for Watching anywhere; the `obs[:7]` slice in `src/state_of_store.py:220` caps the **state-of-store observation list** (not Watching) and is intentionally larger than Watching so build_watching has more candidates to pick from.

## Exact Commands Run

```bash
# Targeted
python -m pytest tests/test_watching_load_bearing_priority.py -v
python -m pytest tests/test_render_v2.py -v
python -m pytest tests/test_phase5_watching_signals.py -v
python -m pytest tests/test_decide.py -v

# Required regression
python -m pytest tests/test_golden_diff.py -v

# Cross-cutting Fix 1-11 invariants
python -m pytest tests/test_targeting_no_dollar_headline.py tests/test_phase5_no_aura_beacon.py \
                 tests/test_targeting_measurement_invariant.py tests/test_abstain_soft_no_recommendations.py \
                 tests/test_inventory_blocked_in_considered.py tests/test_materiality_footer_present.py \
                 tests/test_matrix_vertical_propagation.py tests/test_reporter_dom_only.py \
                 tests/test_synthetic_fixtures_8_11.py -q

# Full suite
python -m pytest tests/ -q

# End-to-end matrix on all six synthetic scenarios via the harness + DOM reporter.
python3 -c "<harness loop over the six scenarios; see Behavior Changes table>"
```

`tests/test_phase5_3_watching.py` does not exist; the equivalent file is `tests/test_phase5_watching_signals.py` (which has been run above and passes).

## Tests / Checks Run

| Check | Result |
|---|---|
| `tests/test_watching_load_bearing_priority.py` (NEW) | 5 passed |
| `tests/test_render_v2.py` (existing + 1 new) | 25 passed |
| `tests/test_phase5_watching_signals.py` (existing, 1 narrowed) | 9 passed |
| `tests/test_decide.py` (existing, 2 narrowed) | 34 passed |
| `tests/test_golden_diff.py` | 3 passed (no re-baseline) |
| `tests/test_targeting_no_dollar_headline.py` | 6 passed |
| `tests/test_phase5_no_aura_beacon.py` | 6 passed |
| `tests/test_targeting_measurement_invariant.py` | 6 passed, 1 skipped |
| `tests/test_abstain_soft_no_recommendations.py` | 11 passed |
| `tests/test_inventory_blocked_in_considered.py` | 12 passed |
| `tests/test_materiality_footer_present.py` | 9 passed |
| `tests/test_matrix_vertical_propagation.py` | 34 passed, 2 skipped |
| `tests/test_reporter_dom_only.py` | 17 passed |
| `tests/test_synthetic_fixtures_8_11.py` | 13 passed |
| Full suite `pytest tests/ -q` | **693 passed, 14 skipped, 0 failed** |
| End-to-end matrix run on all six synthetic scenarios | All 6 produced briefing.html with rc=0; reporter parses cleanly |

Pre-A1 baseline (post-Fix-8/9/10/11) was 687 passed + 14 skipped. Post-A1 is 693 passed + 14 skipped — exactly +6 new tests added (5 in the new file + 1 in `test_render_v2.py`); 0 previously-passing tests moved to fail; 3 existing tests narrowed to use non-load-bearing metrics so they continue to assert the base contract.

## Did The New Tests FAIL Before The Fix?

**Yes — red-first evidence captured.**

1. `tests/test_watching_load_bearing_priority.py` — initial collection failed with `ImportError: cannot import name 'MAX_WATCHING_RENDERED' from 'src.storytelling_v2'`. After adding the constant (step 1 of the patch), the cap-of-4 tests passed but `test_build_watching_prefers_load_bearing_metrics_under_cap` and `test_small_store_240d_renders_at_least_one_load_bearing_watching_row` continued to fail (the prioritization sort change and the empty-HELD fallback had not landed yet). Those two passed only after the `_LOAD_BEARING_WATCH_METRICS` extension + sort-key change + fallback branch landed.

2. `tests/test_render_v2.py::test_watching_section_caps_at_four_with_seven_signals_phase6a` — failed with the same `ImportError` on `MAX_WATCHING_RENDERED`. Passed after the constant landed.

The narrowed M7 tests (`test_moved_observations_excluded`, `test_zero_change_excluded`, `test_non_load_bearing_zero_change_metric_still_excluded`) were updated AFTER the engine change broke their `aov`-keyed assertions. Each test's purpose is preserved (the base contract about MOVED-non-load-bearing exclusion / flat-non-load-bearing exclusion); the metric was swapped to a non-load-bearing one because `aov` is now load-bearing per the contract-final spec.

## Behavior Changes

### `small_store_240d` Watching: before vs after

| | Before (pre-A1) | After (post-A1) |
|---|---|---|
| Watching rows rendered | **0** | **4** |
| Metrics surfaced | (none) | `repeat_rate_within_window`, `net_sales`, `orders`, `returning_customer_share` |
| All four are load-bearing | n/a | **yes** |
| Decision state | `abstain_soft` | `abstain_soft` (unchanged) |
| Recommended count | 0 | 0 (unchanged) |
| Considered count | 6 | 6 (unchanged) |
| Materiality footer | present | present (unchanged) |

This was the central acceptance criterion. The fixture's load-bearing metrics (aov +5.0%, repeat_rate +85%, orders +60%, returning-share +10%, net_sales +68%) all classify as MOVED on the small fixture's volatility. With the empty-HELD fallback, four MOVED load-bearing metrics surface in Watching (capped to 4), giving the merchant a useful "we are watching these" line on a tiny store that previously got an empty Watching section.

### Six-scenario synthetic matrix: before vs after

| Scenario | Pre-A1 | Post-A1 | Delta |
|---|---|---|---|
| `healthy_beauty_240d` | rec=1, con=6, watch=1, publish | rec=1, con=6, watch=1, publish | (no change) |
| `healthy_beauty_low_inventory_240d` | rec=1, con=6, watch=1, publish | rec=1, con=6, watch=1, publish | (no change) |
| `supplement_replenishment_240d` | rec=0, con=6, watch=0, abstain_soft | rec=0, con=6, watch=**4**, abstain_soft | watch +4 (fallback fired) |
| `small_store_240d` | rec=0, con=6, watch=0, abstain_soft | rec=0, con=6, watch=**4**, abstain_soft | **TICKET A1 FIX** (watch +4) |
| `cold_start_45d` | rec=0, con=0, watch=0, abstain_hard | rec=0, con=0, watch=0, abstain_hard | (no change) |
| `promo_anomaly_240d` | rec=1, con=6, watch=1, publish | rec=1, con=6, watch=1, publish | (no change) |

`supplement_replenishment_240d` also gained 4 Watching rows because its load-bearing metrics likewise classify as MOVED. The Watching section is now populated under the Ticket A1 fallback. This is consistent with the brief's intent — "load-bearing metric prioritization pin on small_store_240d" — and is not a goldens-touching change because synthetic fixtures are not golden-pinned.

### Phase 5.3 contract preservation

- HELD load-bearing flat metrics still surface as `trend="flat"` (Phase 5.3 stable-watching). Pinned in `tests/test_phase5_watching_signals.py::test_flat_returning_customer_share_produces_stable_watching_entry` and `test_flat_orders_produces_stable_watching_entry` — both still pass.
- Non-load-bearing flat metrics are still excluded (re-pinned with `click_through_rate` instead of `aov`).
- ANOMALOUS observations are still excluded from Watching (untouched).
- Cap of 4 was already in place in `build_watching`; the new fallback respects the same cap.
- Sort priority within HELD is now load-bearing-first then magnitude — `test_sorted_by_magnitude_descending` continues to pass because both `aov` and `repeat_rate_within_window` are load-bearing in the new world; aov's larger magnitude (0.05 vs 0.001) wins within the load-bearing tier.

## Goldens

- `tests/test_golden_diff.py` → **3 passed, 0 re-baselined**.
- M0 legacy goldens (`tests/golden/{small_sm, mid_shopify, micro_coldstart}/*`): byte-identical.
- No goldens touched.

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_watching_load_bearing_priority.py` — 5 new tests pinning the cap, the prioritization, the Phase 5.3-compatibility, and the small_store_240d end-to-end load-bearing-row presence.

No new sample HTML / receipts / docs were added. The Beauty Brand pinned slate fixture is Ticket B6 work.

## Remaining Risks

1. **Empty-HELD fallback is a new code path.** It surfaces MOVED load-bearing observations as Watching when the HELD pass is empty. Two scenarios (`small_store_240d`, `supplement_replenishment_240d`) now use this path. A future fixture whose load-bearing metrics all happen to be ANOMALOUS rather than MOVED would still get an empty Watching — this is intentional (ANOMALOUS metrics belong to the data-quality footer) but worth flagging.

2. **`aov` is now load-bearing.** Three tests (`test_moved_observations_excluded`, `test_zero_change_excluded`, `test_non_load_bearing_zero_change_metric_still_excluded`) had their metric swapped from `aov` to a generic non-load-bearing metric. The base contract those tests assert is preserved; the test names continue to describe their intent. A reviewer who searches for "aov is not load-bearing" anywhere in the test corpus will find this swap.

3. **`supplement_replenishment_240d` Watching went from 0 to 4.** This is a new visible behavior on a fixture whose merchant-facing briefing is otherwise unchanged. No test in the suite pinned `watch=0` for this fixture, so nothing breaks; if a downstream review wants this fixture to remain at watch=0, the answer is to give it computable HELD load-bearing metrics, not to revert Ticket A1.

4. **Phase 5.3 `_LOAD_BEARING_WATCH_METRICS` was the canonical name.** The Ticket A1 brief listed only four metrics (`returning_customer_share, net_sales, repeat_rate_within_window, aov`); the engine's set still also includes `orders` (Phase 5.3). `orders` is internally treated as load-bearing for sort/fallback purposes but is NOT in the brief's named four. The new test in `tests/test_watching_load_bearing_priority.py` enforces the brief's exact set in the small_store assertion — `orders` does NOT count toward the load-bearing-row presence requirement. small_store_240d happens to surface `orders` plus three brief-named metrics, so the assertion passes; on a future fixture where `orders` is the only surfaced metric, the small_store-style test would fail and the contract would correctly demand a brief-named metric.

5. **The fallback intentionally does NOT promote MOVED load-bearing into the state-of-store paragraph.** The state-of-store paragraph still describes them as "moved", and Watching now also contains them. Some merchants may find a metric appearing in both sections redundant; a future tightening could exclude such metrics from the state-of-store paragraph when the fallback fired. Out of Ticket A1 scope.

## Readiness for Ticket A2

**Ready.** Ticket A2 (`would_be_measured_by` enum + additive PlayCard field) is fully decoupled from Ticket A1:

- Ticket A2 touches `src/engine_run.py` (PlayCard schema), `tests/test_engine_run_schema.py`, and a new `tests/test_would_be_measured_by_enum.py`.
- Ticket A1 did not touch `src/engine_run.py`. The schema remains intact.
- The `MAX_WATCHING_RENDERED` constant is now the single source of truth for the renderer cap; Ticket A2 has no need to touch it.
- `_LOAD_BEARING_WATCH_METRICS` includes `aov`; if Ticket A2 or a later ticket adds new load-bearing metrics, this set is the single seam to extend.
- The empty-HELD MOVED fallback is local to `build_watching`; no other module reads or assumes the prior "MOVED never surfaces" invariant.
- Full suite is at 693 passed, 14 skipped — clean baseline for Ticket A2's red-first work.

No follow-up cleanup or re-review is required before A2 begins.

## Git Status

Per convention, changes are NOT committed. Files left unstaged for review.

- 2 modified `src/` files: `storytelling_v2.py`, `decide.py`.
- 3 modified test files: `test_decide.py`, `test_phase5_watching_signals.py`, `test_render_v2.py`.
- 1 new test file: `test_watching_load_bearing_priority.py`.
- 1 new doc file: this summary.
- No goldens modified.
- No legacy `src/storytelling.py` modified.
- No `engine_run.py` schema modified.
- No `priors.yaml` / `priors_loader.py` modified.
- No `main.py` / `utils.py` modified.
