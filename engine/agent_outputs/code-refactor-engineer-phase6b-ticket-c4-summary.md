# Phase 6B Ticket C4 — Never-empty Watching copy fallback

**Status:** Applied. Suite green (922 passed / 14 skipped / 0 failed). M0 goldens byte-identical. Beauty Brand pinned fixture sha256 unchanged (`dcb45cee...`). Founder-testing-only gating unchanged.

---

## 1. Approved Scope

Render a single fallback row when the V2 Watching list is empty, but the store has >=180 days of clean history and >=1 directional State-of-Store observation. Prevents mature stores from seeing a completely empty Watching section.

Gate conditions (all three must hold):
1. `engine_run.abstain.state` is `PUBLISH` or `ABSTAIN_SOFT`
2. `engine_run.cold_start == False` AND `DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY not in engine_run.data_quality_flags`
3. At least one `state_of_store` `Observation` with a non-zero `change_magnitude`

If conditions do NOT all hold: render the existing `<p class="section__empty">No deterministic signals to watch this run.</p>` unchanged (cold-start, ABSTAIN_HARD, insufficient history).

---

## 2. Patch Summary

1. **`src/storytelling_v2.py`** — Three additions:
   - `_WATCHING_FALLBACK_TEXT` module constant (the approved copy).
   - `_has_directional_observation(engine_run)` private helper — returns True if any `state_of_store` Observation has `change_magnitude` non-None and != 0. Not exported.
   - `_render_watching_section_for_run(engine_run)` private function — evaluates all three gate conditions; delegates to `render_watching_section(engine_run.watching)` when signals are present, emits the fallback `<li class="watching-row watching-row--fallback">` when all three conditions hold, and falls back to `render_watching_section([])` (empty-section paragraph) otherwise.
   - Changed the call site in `render_engine_run` from `render_watching_section(engine_run.watching)` to `_render_watching_section_for_run(engine_run)`.
   - The public `render_watching_section(signals)` function is **unchanged**.

2. **`tests/test_watching_fallback.py`** (NEW) — 8 tests across 4 classes:
   - `TestFallbackFiresOnMatureStoreWithEmptyWatching`: 2 tests (PUBLISH + ABSTAIN_SOFT)
   - `TestFallbackDoesNotFireOnColdStart`: 4 tests (cold_start=True; INSUFFICIENT_CLEAN_HISTORY flag; no directional obs; empty state_of_store)
   - `TestFallbackDoesNotFireWhenWatchingHasRows`: 1 test
   - `TestFallbackCopyContent`: 1 test — pins the exact approved copy text

---

## 3. Files Changed

| Path | Description |
|---|---|
| `src/storytelling_v2.py` | Added `_WATCHING_FALLBACK_TEXT`, `_has_directional_observation`, `_render_watching_section_for_run`; changed call site in `render_engine_run`. Public API unchanged. |
| `tests/test_watching_fallback.py` (NEW) | 8 tests covering fallback trigger, all three gate conditions, and copy content. |

No other files changed. `src/decide.py`, `src/storytelling.py` (legacy), M0 goldens, and the Beauty Brand fixture are all untouched.

---

## 4. Design Decision: History-days Proxy

The task specification says ">=180 days of clean history (use whichever field name Task 0 confirmed)". Task 0 investigation confirmed:

- `EngineRun.scale` has no `window` field (`Scale` carries `monthly_revenue`, `customer_base_est`, `materiality_floor` only).
- `EngineRun.data_window` has `primary_window` (e.g. "L28"), `available_windows` (e.g. ["L7","L28","L56","L90"]), and `anchor_quality`. No numeric days count. Available window keys only go to L90; there are no L180/L240 keys in the engine.
- The IM plan's guidance ("use `engine_run.scale.window` or `engine_run.data_window`") is therefore inapplicable as written — neither field stores a numeric history-days value.

**Decision:** Use `cold_start == False` AND `DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY not in data_quality_flags` as the proxy for ">=180 days of clean history". This is the correct programmatic representation on the existing `EngineRun` schema:
- A 45d cold-start store has `cold_start=True` → blocked.
- A store with < 60 days clean (below the anomaly detector's `min_clean_days`) gets `INSUFFICIENT_CLEAN_HISTORY` → blocked.
- A healthy 240d store has `cold_start=False` and no `INSUFFICIENT_CLEAN_HISTORY` flag → eligible.

This is documented in both the helper docstring and the test module docstring.

---

## 5. Test Results

| Lane | Result |
|---|---|
| `tests/test_watching_fallback.py` (NEW) | **8 passed** |
| `tests/test_slate_regression_beauty_brand.py` (B6) | 19 passed |
| `tests/test_golden_diff.py` (M0) | 3 passed |
| **Full `pytest -q`** | **922 passed / 14 skipped / 0 failed** |

Suite count delta: 914 (post-C3) → 922 (+8 new tests).

---

## 6. Beauty Brand Fixture SHA256

```
sha256: dcb45ceefe5f4dd44cc05e4e539df75402cf7fe80abf4a4757ce69b8f2e0f3bb
```

Byte-identical to the post-C3 canonical. The Beauty Brand fixture has 1 AOV row in Watching — the fallback branch never fires there. No re-pin required or performed.

---

## 7. Behavior Changes

**Default-flag path (M0 / `ENGINE_V2_OUTPUT=false`):** No change. Legacy `src/storytelling.py` renderer is untouched. M0 goldens (`small_sm`, `mid_shopify`, `micro_coldstart`) are byte-identical.

**Full V2 stack (`ENGINE_V2_DECIDE=true` + `ENGINE_V2_OUTPUT=true` + `ENGINE_V2_SLATE=true`):**
- When `watching` is non-empty: no behavior change (delegates to `render_watching_section` as before).
- When `watching` is empty AND mature store AND directional observation: instead of `<p class="section__empty">No deterministic signals to watch this run.</p>`, renders `<ul class="watching-list"><li class="watching-row watching-row--fallback">Trend signals are firming up; we'll surface specific watch items here as your run-over-run history accumulates.</li></ul>`.
- When `watching` is empty AND cold-start OR insufficient history OR ABSTAIN_HARD OR no directional obs: unchanged `<p class="section__empty">` copy.

---

## 8. Remaining Risks

- The history-days proxy (`cold_start + INSUFFICIENT_CLEAN_HISTORY flag`) is coarser than a true numeric days check. A store with 95 days of clean history would pass the proxy if it is not cold-start and has no flag. This is acceptable for Phase 6B: the fallback is a single honest sentence, not a fabricated metric, so the risk of showing it slightly early is low.
- Phase 6C will populate Watching from State-of-Store metrics directly. Once that ships, the fallback row will naturally be suppressed by the presence of real rows — the fallback only fires when `watching` is empty.

## 9. Follow-up Work

- Phase 6C: populate `engine_run.watching` from State-of-Store trend stats. The fallback row will become unreachable for mature stores once Watching has real rows.
- Phase 6C: add a numeric `history_days` field to `EngineRun` (or `BriefingMeta`) to allow precise gating. The current proxy is sufficient for Phase 6B founder testing.
