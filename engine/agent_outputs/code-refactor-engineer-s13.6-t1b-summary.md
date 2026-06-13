# S13.6-T1b (Option D, bundled atomic commit) — Summary

**Sprint/ticket:** S13.6-T1b — Strip `Observation.text` from the contract surface (atomic-split sibling of T1a per DS R5).
**Authorization:** Founder + DS approved 2026-05-31 per the IM plan (§5 Phase 2 T1b spec) + DS R5 split rationale. Option D playbook reused (single bundled atomic commit covering dataclass strip + renderer-side cleanup + producer-side strip + test surgery + new strip test + extended grep pin + engine_run.json SHA re-pin + summary file).
**Status:** Staged in working tree, ready for orchestrator commit. Engine remains runnable. All new tests + all directly affected modules green. 5-fixture engine_run.json SHA re-pin completed via the new `scripts/s13_6_t1b_repin.py` harness.

---

## 1. Files changed

| File | Change | +/− |
|---|---|---|
| `src/engine_run.py` | Stripped `Observation.text: str` field; updated docstring; dropped `text=` read from `_from_dict_observation` (legacy `text` key dropped silently on round-trip). | +11/−7 |
| `src/state_of_store.py` | Removed `text=...` kwarg from all 7 `Observation(...)` constructor sites (AOV, repeat-rate not-computed, repeat-rate normal, orders, returning-customer-share, net-sales, anomaly flag). Updated docstring to note the slot was stripped. `_fmt_money` / `_fmt_pct` helpers retained as conservative dead-code (no scope expansion). | +5/−12 |
| `src/storytelling_v2.py` | Replaced the single `ob.text` consumer in `render_state_of_store` with a call to a new `_synthesize_observation_sentence(ob)` helper that composes a short sentence from typed numerics: `supporting_metric` + `classification` + `delta_pct` + `anomaly_flags`. Added `_METRIC_LABEL_OVERRIDES` map. | +57/−2 |
| `tests/test_s13_renderer_non_consumption.py` | Extended `STRIPPED_PATTERNS` with a new `Observation.text` entry covering `ob.text` / `obs.text` / `observation.text` / `Observation(text=...)` patterns across `briefing.py` + `storytelling_v2.py` + `debug_renderer.py`. | +14/−0 |
| `tests/test_s13_6_t1b_observation_text_strip.py` | NEW. 6 cases: dataclass-fields introspection (`text` absent, typed numerics preserved), `to_dict()` key absence, end-to-end JSON serialization sweep on a Beauty-shaped fixture (3 classification branches), AST sweep over `src/` for remaining `Observation(text=...)` kwarg producers, legacy-dict round-trip (stale `text` key dropped silently). | +210/−0 |
| `tests/fixtures/pinned_sha_ledger.json` | Added `post_s13_6_t1b` engine_run.json SHA per fixture (T1a SHAs preserved). Updated `_meta.ticket` → `S13.6-T1b`. Added `post_s13_6_t1b_definition` field. Updated `diff_confined_to` lists to call out the new `state_of_store[*].text REMOVED` line. | +14/−14 |
| `tests/test_decide.py` | Bulk-stripped 10 `text=` kwargs from `Observation(...)` constructors. | +0/−10 |
| `tests/test_render_v2.py` | Stripped 4 `text=` kwargs; added `delta_pct=0.042` to the MOVED Observation in `_publish_engine_run` so synthesis produces a non-empty delta clause; loosened `"AOV moved up"` substring assertion to `"AOV moved"` (synthesis grammar omits "up"); rewrote `test_state_of_store_orders_moved_first_then_held` to provide `supporting_metric` + `delta_pct` so the two ordered observations produce distinct synthesized strings. | +12/−4 |
| `tests/test_engine_run_schema.py` | Stripped 1 multi-line + 1 inline `text=` kwarg (`Observation(text="held")` → `Observation()`). | +1/−2 |
| `tests/test_internal_stats_not_rendered.py` | Stripped 1 inline `text=` kwarg. | +1/−1 |
| `tests/test_phase5_no_aura_beacon.py` | Stripped 2 `text=` kwargs. | +0/−2 |
| `tests/test_phase5_watching_signals.py` | Stripped 6 `text=` kwargs. Rewrote `test_state_of_store_suppresses_repeat_rate_when_no_identified_customers` to assert on the typed `classification` / `current` / `delta_pct` slots (the "not computed" suppression is now structural, no longer a prose substring). | +13/−6 |
| `tests/test_storytelling_v2_layout.py` | Stripped 1 `text=` kwarg. | +0/−1 |
| `tests/test_watching_fallback.py` | Stripped 3 `text=` kwargs. | +0/−3 |
| `tests/test_watching_load_bearing_priority.py` | Stripped 3 `text=` kwargs. | +0/−3 |
| `tests/test_observations.py` | Replaced `"bfcm_overlap" in anomalous[0].text` with the typed-slot assertion `anomaly_flags == ["bfcm_overlap"]` + `supporting_metric == "bfcm_overlap"`. | +4/−1 |
| `tests/test_inventory_blocked_in_considered.py` | Fixed pre-existing broken T1a-leftover state in `test_inventory_blocked_considered_card_has_merchant_readable_reason_text` (the test body referenced an undefined `lower` local because the T1a strip elided the assignment). Replaced with a typed `reason_code == ReasonCode.INVENTORY_BLOCKED` assertion + a comment explaining the strip rationale. This was a regression from T1a, not introduced by T1b — but it would have failed the suite, so it is fixed in this commit. | +5/−6 |
| `scripts/s13_6_t1b_repin.py` | NEW. Modeled on `scripts/s13_6_t1a_repin.py`. Computes post-T1b engine_run.json SHA on the 5 pinned synthetic fixtures. Same caveat about ML `fit_timestamp` wall-clock drift carries forward. | +69/−0 |
| `agent_outputs/code-refactor-engineer-s13.6-t1b-summary.md` | This file. | new |

---

## 2. Producer + consumer inventory (executed)

### `Observation.text` field

- **Removed from dataclass:** `src/engine_run.py:471-501` (`Observation` definition).
- **Removed from round-trip:** `src/engine_run.py:_from_dict_observation` (`text=d.get("text", "")` line dropped; legacy dicts with a `text` key are accepted but the key is silently dropped per the same pattern used for T1a-stripped `Abstain.reason`).

### Producers (writer sites) cleaned

**`src/state_of_store.py` — 7 sites:**
- L130-140 (AOV)
- L148-156 (repeat-rate "not computed" branch)
- L158-170 (repeat-rate normal branch)
- L176-188 (orders)
- L196-212 (returning-customer share)
- L218-234 (net sales)
- L242-253 (per-flag anomaly observation)

**Test fixtures — 31 producer sites** across 9 test files (sweep done by a small in-line script using a regex on `text=...` kwarg lines inside `Observation(...)` constructors). One missed inline-form site at `tests/test_engine_run_schema.py:93` (`Observation(text="held")` on a single line) was caught by the post-sweep grep audit and fixed manually.

### Renderer / consumer sites cleaned

**`src/storytelling_v2.py:535`** — the single `text = (ob.text or "").strip()` line was the only renderer consumer. Replaced with `text = _synthesize_observation_sentence(ob).strip()`. The new helper composes a short sentence from typed numerics:

- `ANOMALOUS` → `f"Data quality flag: {anomaly_flags[0] or supporting_metric}"` (falls back to `"Data quality flag noted"` if both are empty).
- `MOVED` → `f"{metric_label} moved {fmt_pct(delta_pct)}"` (omits the delta clause when `delta_pct is None`).
- `HELD` → `f"{metric_label} held"`.

The renderer remains runnable; round-trip + 5-fixture SHA harness + end-to-end smoke confirmed.

### Other modules (audited, no changes needed)

- `src/briefing.py` — no `Observation` reads (only `EngineRun.briefing_meta` / file I/O).
- `src/debug_renderer.py` — no `Observation` reads (table only renders `recommendations` / `considered`).
- `src/decide.py` — imports `Observation` for type hints only; no `.text` reads.
- `src/measurement_builder.py` — comment-only reference at L605 ("Observation deltas").
- `src/outcome_log.py` — confirmed via `grep -n "Observation\|\.text" src/outcome_log.py` → no `Observation` references at all. T1a synthesis pattern not needed.
- `src/main.py` — no `Observation` constructor calls (state-of-store production is delegated to `build_observations` in `state_of_store.py`).

---

## 3. Unexpected consumers found + how handled

1. **`tests/test_observations.py:87`** `assert "bfcm_overlap" in anomalous[0].text` was a prose-substring read not in the original brief's enumerated consumer list. Handled by converting to typed-slot assertions on `anomaly_flags` + `supporting_metric` (the data the prose was synthesizing from).

2. **`tests/test_phase5_watching_signals.py:177-179`** asserted on `"0.0%" not in rr.text` and `"not computed" in rr.text.lower()`. The "not computed" suppression is now structural (classification HELD, `current/prior/delta_pct` all None), so the test was rewritten to assert on those typed slots directly.

3. **`tests/test_inventory_blocked_in_considered.py:147-158`** carried a broken T1a-leftover that referenced an undefined `lower` local (the T1a strip script removed the assignment but kept the use). This was a pre-existing failure on the post-T1a tree (verified via `git stash` + re-run), not a T1b regression. Fixed in this commit because it would otherwise block the suite.

4. **`test_engine_run_schema.py:93` inline form `Observation(text="held")`** was missed by my multi-line-aware strip script (the regex only matched lines starting with `text=...`). Caught by post-sweep grep audit + fixed manually.

---

## 4. SHAs before / after

### `engine_run.json` SHAs (re-pinned at this commit)

| Fixture | `post_s13_6_t1a` | `post_s13_6_t1b` (NEW) |
|---|---|---|
| healthy_beauty_240d | `88aee4c61583768423ca34dce5d7b4609a5cf4eafb10f0905f2df02e8ea84cab` | `c501dae64b949213870f95b8a0060aec08813118394c180c7fee16a8bddb626f` |
| healthy_supplements_240d | `691e63281940a3f05960128f968259aa6501db1ee05c0d5abe42c70906f18519` | `03dddfe7cf7b4a0508cb314b2e7d354b0dcb2cd44dac98f6d8dcf2dcc11b1ce9` |
| small_store_240d | `2bcee38701103e706c2c77c60d3ce9dc421c4886e7cc9ebc269fae0fd0e646ca` | `76eec1c48901865f337d8a049c9f6da95bc1ac34946fbfeaf9216401b2502615` |
| cold_start_45d | `156021afd3cdafeec141d424ee4dca22150a34bb9ab5e3d533323e21d356a09d` | `aafb6adc2932213aabbfb86504da08ad987340f2224efe1ef5245e4e2a1ac3c4` |
| healthy_beauty_low_inventory_240d | `7d3811eeac2227a81eeaef027d1237bd999974f49071ebe390aa5fa2c3d52078` | `dea47b7510fe1425973e78d68050799dbf4d76cd66a238cb3bdc6f4ec42066db` |

### `briefing.html` SHAs

- **NOT PINNED** (T1a retired the canary on 2026-05-30; this ticket preserves that retirement).
- Renderer was smoke-tested end-to-end on a Beauty-shaped `EngineRun` carrying all three classification branches; produced 5,574 bytes of well-formed HTML; substrings `"AOV moved"`, `"Repeat rate held"`, and `"Data quality flag"` all appear in the synthesized state-of-store paragraph.
- The 5-fixture re-pin harness runs the full pipeline (including the renderer) without `AttributeError`.

### Re-pin harness

- **Approach:** NEW `scripts/s13_6_t1b_repin.py`, copied from `scripts/s13_6_t1a_repin.py` with header re-wording. Picked the new-file approach rather than extending the existing T1a script to keep each strip ticket's harness self-contained and historically traceable — same low friction either way (file is 69 lines).
- **Caveat preserved:** engine_run.json contains wall-clock `fit_timestamp` values from S10-S12 ML ModelCards; these SHAs record the at-commit moment, not byte-stable re-runs. The load-bearing post-T1b test gates are the new `tests/test_s13_6_t1b_observation_text_strip.py` + extended `tests/test_s13_renderer_non_consumption.py` — not this ledger.

---

## 5. Confirmation checklist (per brief)

- [x] `Observation.text` not present on the `Observation` dataclass (`tests/test_s13_6_t1b_observation_text_strip.py::test_observation_dataclass_has_no_text_field`).
- [x] `text` key not in `to_dict()` output on a representative fixture (`test_engine_run_to_dict_drops_observation_text_key`).
- [x] `text` key not in emitted JSON on a Beauty-shaped fixture covering MOVED + HELD + ANOMALOUS branches (`test_engine_run_emitted_json_drops_observation_text_key`).
- [x] AST sweep over `src/` for `Observation(text=...)` kwarg producers — 0 offenders (`test_ast_no_remaining_observation_text_kwarg_producers`).
- [x] Legacy-dict round-trip silently drops `text` key (`test_from_dict_observation_drops_legacy_text_key_silently`).
- [x] Outcome log untouched — `grep "Observation\|\.text" src/outcome_log.py` confirmed no references; the T1a synthesis pattern is not needed here.
- [x] No T1a-stripped fields re-touched — the T1a 6-prose strip + `Abstain.reason` + `notes` gating all preserved; `test_s13_6_t1a_prose_field_strip.py` + `test_s13_renderer_non_consumption.py` stay green.
- [x] `INCLUDE_DEBUG_FIELDS` posture preserved — T1a's flag default OFF is unchanged; `Observation.text` was a single `str` slot, not a `List[str]` debug-debris block, so no new flag gate was needed.
- [x] No scope expansion: `klaviyo_brief_inputs`, `OpportunityContext`, `Any` slots, `schema_version`, `mechanism`, RULE A null_reason fields, AST dormancy registry, single-demote-channel invariant — all untouched.

---

## 6. Tests / checks

### Test counts

- **Affected modules (focused run, 137 tests):** all green.
- **Suite scope verified:** `tests/test_s13_6_t1b_observation_text_strip.py` (NEW, 6 cases) + extended `tests/test_s13_renderer_non_consumption.py` (21 cases: 18 original from T1a + 3 new × the new `Observation.text` pattern × 3 renderer modules) + every test module touched by the strip (test_decide / test_render_v2 / test_storytelling_v2_layout / test_engine_run_schema / test_internal_stats_not_rendered / test_observations / test_phase5_no_aura_beacon / test_phase5_watching_signals / test_watching_fallback / test_watching_load_bearing_priority / test_inventory_blocked_in_considered) — all green.
- **Broader suite (excluding slow shadow/golden tests):** 2130 passed, 9 failed. All 9 failures verified pre-existing on the pre-T1b tree (`git stash` + re-run; same 9 tests fail without my changes). They are:
  - `tests/test_phase5_considered_always.py::test_abstain_soft_briefing_renders_populated_considered_section` (renderer regression from T1a — "Would fire" copy removed).
  - 4 × `tests/test_recommended_experiment_forbidden_tokens.py::test_negative_control_*` (renderer regression from T1a — recommendation_text rendering removed so negative-control injection points no longer surface).
  - `tests/test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1` (DEFAULTS env override; orthogonal).
  - `tests/test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off` (orthogonal).
  - 2 × `tests/test_s3_memory_event_schemas.py::test_recommendation_*_payload_*` (memory-event constructor requires `evidence_snapshot=` — orthogonal pre-existing).

None of these 9 are introduced or worsened by T1b. They are documented here for orchestrator review (recommend tracking in `KNOWN_ISSUES.md` or as a T1a follow-up ticket; out of T1b scope per the brief's "no silent scope expansion" rule).

### Renderer smoke

End-to-end on a 3-Observation `EngineRun` (1 MOVED with `delta_pct=0.042`, 1 HELD, 1 ANOMALOUS):
- HTML length: 5,574 bytes.
- Synthesized substrings present: `"AOV moved"`, `"Repeat rate held"`, `"Data quality flag"`.
- No `AttributeError`.

### Re-pin smoke

All 5 synthetic fixtures completed end-to-end via `scripts/s13_6_t1b_repin.py` (full pipeline including renderer); SHAs captured + written to the ledger.

---

## 7. Risks encountered + mitigations

1. **Risk:** The orderable test `test_state_of_store_orders_moved_first_then_held` originally provided no `supporting_metric`/numerics — the synthesized output would be identical for both observations and the ordering assertion would have ambiguous behavior.
   **Mitigation:** Test rewritten to provide `supporting_metric` + `delta_pct` so each Observation synthesizes to a distinct string (`"AOV moved +4.2%"` vs `"Repeat rate held"`). The intent of the test (MOVED before HELD) is preserved.

2. **Risk:** `tests/test_render_v2.py::test_publish_renders_all_three_sections_plus_state_of_store_and_dq_footer` asserted `"AOV moved up" in html`, but the synthesis grammar produces `"AOV moved +4.2%"` (no "up" — the sign is on the percent). 
   **Mitigation:** Loosened assertion to `"AOV moved" in html`, which is invariant under the synthesis grammar.

3. **Risk:** `test_phase5_watching_signals` asserted on prose substring `"not computed"` for the suppressed repeat-rate Observation. The "not computed" semantics are now structural (HELD classification + all-None numerics), not a string.
   **Mitigation:** Test rewritten to assert on the typed slots directly. The structural invariant is stronger than the prose substring.

4. **Risk:** `tests/test_inventory_blocked_in_considered.py:147` carried a pre-existing T1a-leftover that referenced undefined `lower`. Without a fix it would block the suite under T1b's larger blast radius.
   **Mitigation:** Replaced the broken assertion with a typed-slot assertion + a comment pointing back to the T1a strip rationale. Pre-existing failure, not introduced by T1b — documented in this summary's §3 + §6 for orchestrator awareness.

5. **Risk:** The bulk `text=` strip regex might have matched non-Observation `text=` kwargs elsewhere (e.g. `WatchedSignal(text=...)` if any existed).
   **Mitigation:** Pre-strip inventory confirmed `text=` only appears as an Observation kwarg in the audited files; the regex script restricted itself to test files that already imported `Observation`. Post-strip AST sweep + focused module re-run confirmed no over-strip.

---

## 8. Engine still runnable (smoke)

```
$ python3 -c "from src.engine_run import *; from src.storytelling_v2 import render_engine_run; ..."
OK len= 5574
contains AOV moved: True
contains Repeat rate held: True
contains Data quality flag: True
```

5-fixture pipeline harness completes end-to-end (renderer included). Round-trip via `EngineRun.to_dict()` + `_from_dict_observation` succeeds (legacy `text` key dropped silently).

---

## 9. Proposed commit message headline

```
S13.6-T1b: Strip Observation.text from contract surface (Pivot 2 enforcement, T1a playbook)
```

(Full body per the dispatch brief template; T1b numbers / SHAs filled in.)

---

## 10. Deviation check

`Deviation check: none` — T1b stays within the original DS R5 scope (`Observation.text` only). No T1a-stripped fields re-touched. No scope expansion to T2-onward fields. Renderer-side cleanup (Option D bundling) was already pre-approved at T1a per the brief's Option D playbook reuse. The pre-existing T1a-leftover fix at `tests/test_inventory_blocked_in_considered.py:147` is in-scope as a blocker for the T1b suite-green requirement, not a scope expansion (it was a regression from T1a, not a new behavior).
