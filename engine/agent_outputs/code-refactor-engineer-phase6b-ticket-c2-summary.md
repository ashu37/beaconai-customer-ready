# Phase 6B Ticket C2 — Reorder briefing sections (Watching before Considered)

**Status:** Applied. Suite green (908 passed / 14 skipped / 0 failed). M0 goldens byte-identical. Beauty Brand pinned slate fixture refreshed and re-pinned by byte-equality.

## Approved Scope

A DOM-ordering change in the V2 renderer only. The four role sections render in the new order:

```
Recommended Now → Recommended Experiment → Watching → Considered → DQ footer
```

No copy, no styling, no decide/selector logic, no schema, no legacy renderer touched.

## Patch Summary

1. **`src/storytelling_v2.py`** — In `render_engine_run()`, the body concatenation order swapped `considered_html` and `watching_html` so Watching renders before Considered. The variable definitions and the helper renderers (`render_considered_section`, `render_watching_section`) are unchanged. Added a 4-line in-line comment explaining the merchant reading order ("what to do now → what to test → what to monitor → what we held").

2. **`tests/test_storytelling_v2_layout.py`** — New file. Two tests:
   - `test_section_order_recommended_experiment_watching_considered` — pins all five DOM markers (`recommended`, `recommended-experiment`, `watching`, `considered`, `dq-footer`) and asserts the strict ordering.
   - `test_watching_appears_before_considered_when_no_experiments` — covers the no-experiment path so the bare swap (not just the four-section path) is regression-protected.

3. **`tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`** — Re-pinned via the synthetic harness with the same `_B6_ENV_OVERRIDES` env superset used by the B6 regression test. The file went from sha256 `48d61b89b3a6bb5b7c29d776ceec7fe8ba396522df4362651f7e476bf04726fe` (13,278 bytes, prior order) to **sha256 `5fa9f697967566eab1a3d66a2d7edd6776b68cc166ca9677262f9e5f84e80b53`** (13,278 bytes, new order). The byte length is unchanged because only the order of two sections flipped. The B6 test (`test_briefing_matches_pinned_fixture_bytewise`) enforces byte-equality against the on-disk fixture directly — there is no separate hash constant to update.

### Note on the SHA256 fixture-pin

The prompt described "the SHA256 fixture-pin in the B6 test." The current B6 test (`tests/test_slate_regression_beauty_brand.py::test_briefing_matches_pinned_fixture_bytewise`) does byte-equality against the file's bytes on disk; there is no SHA256 constant in the test or in source to update. Refreshing the on-disk fixture is the canonical pin update for this contract. The new sha256 (`5fa9f697...`) is recorded above for traceability.

## Files Changed

- `src/storytelling_v2.py` — swapped two lines in the `body` concatenation inside `render_engine_run`, plus a 4-line explanatory comment.
- `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` — refreshed via harness (Watching now precedes Considered).
- `tests/test_storytelling_v2_layout.py` — new file, 156 lines, 2 tests.

`git status --short`:
```
 M src/storytelling_v2.py
 M tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html
?? tests/test_storytelling_v2_layout.py
```

## Exact Commands Run

```
# 1. Verified initial state of section-order test landscape
grep -rn "considered.*watching\|watching.*considered" tests/

# 2. Patched src/storytelling_v2.py (swap considered_html ↔ watching_html in render_engine_run body)

# 3. Created tests/test_storytelling_v2_layout.py
python -m pytest tests/test_storytelling_v2_layout.py -q
# → 2 passed in 0.04s

# 4. Confirmed B6 byte-stability test now fails (proves swap is real and detected)
python -m pytest tests/test_slate_regression_beauty_brand.py::test_briefing_matches_pinned_fixture_bytewise -q
# → 1 failed (expected: same length 13278/13278, first diff at byte 9287 inside section markers)

# 5. Re-pinned the Beauty Brand fixture via the harness with the same
#    _B6_ENV_OVERRIDES superset used by the test
python /tmp/refresh_b6_fixture.py
# → Wrote tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html (13278 bytes)
# → sha256: 5fa9f697967566eab1a3d66a2d7edd6776b68cc166ca9677262f9e5f84e80b53

# 6. Re-ran B6 in full
python -m pytest tests/test_slate_regression_beauty_brand.py -q
# → 19 passed in 35.17s

# 7. Confirmed M0 legacy goldens byte-identical
python -m pytest tests/test_golden_diff.py -q
# → 3 passed in 27.55s

# 8. Full suite
python -m pytest -q
# → 908 passed, 14 skipped, 200 warnings in 170.16s (0:02:50)
```

## Test Results

| Lane                                          | Result           |
|-----------------------------------------------|------------------|
| `tests/test_storytelling_v2_layout.py`        | 2 passed        |
| `tests/test_slate_regression_beauty_brand.py` | 19 passed       |
| `tests/test_golden_diff.py` (M0)              | 3 passed        |
| Full `pytest -q`                              | 908 passed / 14 skipped / 0 failed |

Suite count delta: 906 → 908 (added 2 tests in `test_storytelling_v2_layout.py`). No tests required inversion: a global grep confirmed no pre-C2 test asserted Considered before Watching positionally; the closest was `test_section_appears_between_recommended_and_watching` in `tests/test_render_recommended_experiment.py`, which asserts `rec_idx < exp_idx < watch_idx` and continues to hold under the new order (Recommended → Experiment → Watching → Considered → DQ).

## Behavior Changes

**Merchant-visible:** Briefing pages rendered with the V2 stack (`ENGINE_V2_DECIDE` + `ENGINE_V2_OUTPUT` + `ENGINE_V2_SLATE`) now show Watching before Considered. Both section bodies are unchanged (titles, ledes, card markup, copy, styling all identical). The held / muted Considered section sits last before the data-quality footer instead of interrupting the action-forward sections.

**Engine-visible:** None. `decide()` outputs, the typed `EngineRun` schema, the considered/watching list contents, the role-uniqueness invariant, the abstain branches, and the legacy renderer (`src/storytelling.py`) are all untouched. M0 legacy goldens are byte-identical.

**Pinned fixture:** The Beauty Brand pinned slate fixture's bytes have changed (sha256 `48d61b89...` → `5fa9f697...`). The byte length is identical (13,278). The first diff occurs at byte 9287, where the section ordering flips inside the rendered briefing.html — exactly the intended change.

## Out-of-Scope Items NOT Touched

- `src/storytelling.py` (legacy M0 renderer) — untouched.
- `tests/golden/` (M0 fixtures) — untouched, byte-identical.
- `src/decide.py`, selector logic, role-uniqueness invariant — untouched.
- Section copy, ledes, badges, and CSS — untouched.
- `src/engine_run.py` (typed schema) — untouched.

## Readiness for Ticket C3

This patch is **complete** for Ticket C2. The patch is minimal (one swap in one function plus an explanatory comment), the new layout test pins the contract going forward, and the B6 byte-stable fixture is re-pinned. Pre-conditions for Ticket C3 (whatever it sequences next from the Phase 6B founder-feedback plan) are unchanged: V2 renderer remains a pure function, `decide()` is unchanged, all flag gates remain in place. Stopping here per the orchestrator hand-back contract.
