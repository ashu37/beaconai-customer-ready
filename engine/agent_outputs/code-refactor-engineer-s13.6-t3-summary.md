# S13.6-T3 — OpportunityContext NonLiftAtom typed wrapper (DS R1) — Summary

**Sprint / ticket:** Sprint 13.6 Ticket T3.
**Scope locks:** DS R1 verbatim (`agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md`); founder approved 2026-05-30 (Q1 of the 5-question gate); HIGHEST SINGLE RISK on the contract surface per DS readiness review Part 6 §7.
**Date:** 2026-05-31.
**Deviation check: none.**

---

## 1. File change table

| Path | Lines added | Lines removed | Net |
|---|---:|---:|---:|
| `src/engine_run.py` | ~80 | ~38 | +42 |
| `src/measurement_builder.py` | ~12 | ~9 | +3 |
| `src/storytelling_v2.py` | ~7 | ~2 | +5 |
| `tests/test_phase5_1_opportunity_context.py` | ~38 | ~19 | +19 |
| `tests/test_recommended_experiment_opportunity_context.py` | ~12 | ~9 | +3 |
| `tests/test_display_name_render.py` | ~17 | ~5 | +12 |
| `tests/test_what_we_send_render.py` | ~17 | ~5 | +12 |
| `tests/test_render_recommended_experiment.py` | ~8 | ~3 | +5 |
| `tests/test_recommended_experiment_forbidden_tokens.py` | ~8 | ~3 | +5 |
| `tests/test_storytelling_v2_layout.py` | ~8 | ~3 | +5 |
| `tests/test_s13_renderer_non_consumption.py` | ~14 | 0 | +14 |
| `tests/test_s13_6_t3_non_lift_atom_wrapper.py` (NEW) | ~225 | 0 | +225 |
| `scripts/s13_6_t3_repin.py` (NEW) | ~80 | 0 | +80 |

Net diff is overwhelmingly producer-side wrapper construction + test-surface structural rewires. No semantic test was weakened.

---

## 2. Test counts

- **Before T3 (baseline at 25a4488):** 2187 passed / 10 failed / 15 skipped / 6 xfailed (full suite, 35:28).
- **After T3:** 2187 passed / 10 failed / 15 skipped / 6 xfailed (full suite, 35:28).
- **Delta:** 0 regressions. All 10 failures are pre-existing, reproducible on baseline (verified via `git stash`):
  - `test_phase5_considered_always.py::test_abstain_soft_briefing_renders_populated_considered_section` (pre-existing).
  - `test_recommended_experiment_forbidden_tokens.py::test_negative_control_*` x4 (T1a artifact — these tests inject text into the stripped `recommendation_text` field).
  - `test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1`, `test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off` (pre-existing).
  - `test_s3_memory_event_schemas.py::test_recommendation_emitted_payload_to_dict`, `…_payload_supports_null_evidence` (pre-existing).
  - `test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh` (pre-existing).
- **NEW tests (10):** `tests/test_s13_6_t3_non_lift_atom_wrapper.py` — 10 cases covering dataclass introspection, field types incl. closed-set Literal, re-export, end-to-end producer, JSON shape, round-trip, AST sweep of `src/` for stripped reads, and no-flag invariant.
- **EXTENDED:** `tests/test_s13_renderer_non_consumption.py` — added two patterns (`OpportunityContext.aov`, `OpportunityContext.addressable_value`) to the renderer grep pin (covers `briefing.py`, `storytelling_v2.py`, `debug_renderer.py`).

---

## 3. Inventory results

### `OpportunityContext(...)` constructor sites — rewired

| File | Line | Status |
|---|---|---|
| `src/measurement_builder.py` | 233 | Rewired — constructs `NonLiftAtom`, passes as `non_lift=`. |
| `src/engine_run.py` | 1533 (`_from_dict_opportunity_context`) | Rewired — deserializes `non_lift` sub-dict, no legacy fallback. |
| `tests/test_display_name_render.py` | 114, 153 | Rewired (2 sites). |
| `tests/test_what_we_send_render.py` | 103, 141 | Rewired (2 sites). |
| `tests/test_render_recommended_experiment.py` | 105 | Rewired. |
| `tests/test_recommended_experiment_forbidden_tokens.py` | 100 | Rewired. |
| `tests/test_storytelling_v2_layout.py` | 71 | Rewired. |
| `tests/test_phase5_1_opportunity_context.py` | 351, 511, 552 | Rewired (3 sites). |

### `opp.aov` / `opp.addressable_value` reads — rewired

| File | Line(s) | Old | New |
|---|---|---|---|
| `src/storytelling_v2.py` | 371, 372 | `opp.aov`, `opp.addressable_value` | `opp.non_lift.aov_used`, `opp.non_lift.value` |
| `tests/test_phase5_1_opportunity_context.py` | 137-141, 644-650 | `opp.aov`, `opp.addressable_value` | `opp.non_lift.aov_used`, `opp.non_lift.value`, `opp.non_lift.monthly_revenue_estimate`, `opp.non_lift.semantic` |
| `tests/test_recommended_experiment_opportunity_context.py` | 149-152, 205, 220-223, 251-252, 318-319 | various `opp.aov` / `opp.addressable_value` / `actual.aov` / `actual.addressable_value` | corresponding `non_lift.*` path |

### `opp.aov_used` / `opp.monthly_revenue_estimate` reads

Pre-T3 these aliases existed at the top level of `OpportunityContext` and were unused by both renderers and tests (introduced at Phase 6B Task 2 for the agent-swarm contract; no live consumer). Post-T3 they live inside `NonLiftAtom`. No call-site path-update needed because the only references were in the dataclass definition itself.

### AST sweep result over `src/`

After the rewire, an AST `Attribute` walk over all `.py` files in `src/` confirms **zero** live reads of `.addressable_value`. Test `tests/test_s13_6_t3_non_lift_atom_wrapper.py::test_ast_sweep_no_stripped_oc_reads_in_src` pins this going forward.

---

## 4. `engine_run.json` SHA before / after

The SHA WILL change because every PlayCard's `opportunity_context` JSON sub-tree restructures from `{aov, aov_used, addressable_value, monthly_revenue_estimate, audience_size, aov_window, aov_source}` to `{audience_size, non_lift:{value, semantic, aov_used, monthly_revenue_estimate}, aov_window, aov_source}`.

New SHAs captured via `scripts/s13_6_t3_repin.py` (caveat: `fit_timestamp` is wall-clock, so these record the at-commit moment only — the load-bearing post-T3 gates are the structural tests, NOT this ledger):

| Scenario | post_s13_6_t3 SHA |
|---|---|
| `healthy_beauty_240d` | `6edd0ccac181ec58fdd05fa6eefa294e0dcb1e2eced4c80729f88dc68ae8b39e` |
| `healthy_supplements_240d` | `44543f11dc571b7b7ac4c5c66df914e25c381d41bb9c08b2a055835a80d6e2b9` |
| `small_store_240d` | `1062cba38cd9c49b8c0919ae5bd429909800ee206045439a499c5ae102160307` |
| `cold_start_45d` | `ff329c15f6a6e14cda6156879827007bca88a4e409dcae632ff453497c02e1b3` |
| `healthy_beauty_low_inventory_240d` | `121b4ab4ec84c2b4a57aa0badc22e122575a99b843037f8362e69baf47b85cfe` |

`briefing.html` is NOT pinned (canary retired at T1a per Pivot 2 addendum). Renderer was confirmed to run without raising — new test `test_engine_run_json_carries_non_lift_sub_object` exercises the path; existing `test_directional_card_with_audience_and_aov_carries_opportunity_context` also exercises end-to-end render.

---

## 5. Confirmations

- **`NonLiftAtom` is a dataclass** with exactly the four DS-R1-locked fields: `value: float`, `semantic: Literal["addressable_opportunity"]`, `aov_used: float`, `monthly_revenue_estimate: float`. Pinned via `test_non_lift_atom_has_exactly_four_fields` + `test_non_lift_atom_field_types_match_ds_r1_lock` (closed-set Literal verified via `get_args`).
- **`OpportunityContext.aov` is GONE.** Pinned via `test_opportunity_context_no_longer_carries_aov_or_addressable_value`.
- **`OpportunityContext.addressable_value` is GONE.** Same test pin.
- **`OpportunityContext.non_lift: NonLiftAtom`** — pinned via `test_opportunity_context_carries_non_lift_typed_as_non_lift_atom`.
- **Every emitted PlayCard with a populated `opportunity_context` has `non_lift: NonLiftAtom`** with `semantic == "addressable_opportunity"`. Pinned by `test_measurement_builder_produces_non_lift_atom` (end-to-end producer call) + `test_engine_run_json_carries_non_lift_sub_object` (round-trip).
- **No T1a/T1b/T2-stripped/typed fields re-touched.** Confirmed by inspection: `recommendation_text`, `why_now`, `reason_text`, `evidence_snapshot`, `would_fire_if`, `Abstain.reason`, `Observation.text`, `klaviyo_brief_inputs` — none referenced by T3. The renderer non-consumption pin was EXTENDED (not modified) with two new patterns.
- **No T4+ scope touched.** No edits to `FitWarning` (T4), no `schema_version` bump (T5), no `MechanismIntent` enum (T6), no RULE A null_reason patterns (T7), no null-reason enum registry (T7.5).
- **No `bool _do_not_narrate_as_lift` flag introduced.** Pinned by `test_no_do_not_narrate_as_lift_flag_introduced` (greps all `src/` for the forbidden literal). DS R1 explicitly rejected this as "type-safety theatre"; the wrapper IS the guardrail.
- **No fallbacks** (`oc.aov or oc.non_lift.aov_used`). Strict cutover — `_from_dict_opportunity_context` returns `None` when the new `non_lift` sub-object is absent rather than reading legacy keys. Renderer reads `opp.non_lift.*` directly; no shim.
- **Re-export.** `from src.engine_run import NonLiftAtom` works (defined locally in the schema-authority file per DS R6 and added to `__all__`).
- **AST sweep** over `src/` shows zero `.addressable_value` attribute reads remain. Pinned for regression.

---

## 6. Risks encountered + mitigations

| Risk | Mitigation |
|---|---|
| Highest-contract-shape-risk ticket — JSON consumers might rely on `aov` / `addressable_value` keys. | Inventory grep ran first; only the two renderer reads (`storytelling_v2.py:366-367`) and 8 test files carried these names. All rewired. The from-dict path is strict (no silent fallback), so any missed consumer fails loudly. |
| `_from_dict_opportunity_context` could silently degrade if the JSON shape regresses. | New strict check: returns `None` if `non_lift` is absent or `semantic != "addressable_opportunity"`. Round-trip test pins both shapes. |
| Pre-existing 10 failing tests could mask a regression. | Verified post-T3 failure set is IDENTICAL to baseline (same 10 tests, same node IDs) via `git stash` comparison. |
| `\.addressable_value\b` grep could false-positive on `_round_addressable_value` (the renderer helper function name). | The new renderer non-consumption pattern is scoped (anchored to `.addressable_value\b` or `addressable_value\s*=`) and verified to produce zero hits on the three renderer modules. `_round_addressable_value` is a function name (`_round_addressable_value(`), not matched by either form. |
| AST sweep could miss aliased reads (e.g. `x = card.opportunity_context; x.addressable_value`). | The `ast.Attribute` walk catches `node.attr` regardless of receiver, so any read of `.addressable_value` is flagged. The test is over the whole `src/` tree. |

---

## 7. Behavior changes

- `OpportunityContext` carries `audience_size`, `aov_window`, `aov_source`, and the new `non_lift: NonLiftAtom`. Top-level monetary numerics (`aov`, `addressable_value`, `aov_used`, `monthly_revenue_estimate`) are GONE — the four addressable-opportunity numerics now live exclusively inside the typed wrapper.
- JSON shape of every emitted `opportunity_context` block restructures. New shape:
  ```json
  "opportunity_context": {
    "audience_size": 286,
    "non_lift": {
      "value": 19734.0,
      "semantic": "addressable_opportunity",
      "aov_used": 69.0,
      "monthly_revenue_estimate": 19734.0
    },
    "aov_window": "L28",
    "aov_source": "store_observed"
  }
  ```
- Renderer surface (`storytelling_v2.py::_render_opportunity_context_block`) reads `opp.non_lift.aov_used` and `opp.non_lift.value`. Rendered HTML for the opportunity-context block is byte-identical to pre-T3 (same `_fmt_money` + `_round_addressable_value` inputs, same disclaimer).
- `briefing.html` is not pinned. Confirmed runnable end-to-end via the five re-pin fixtures (all produced an `engine_run.json` successfully).

---

## 8. Artifacts added

- `tests/test_s13_6_t3_non_lift_atom_wrapper.py` — 10 cases.
- `scripts/s13_6_t3_repin.py` — engine_run.json SHA ledger helper (modeled on T2).
- `agent_outputs/code-refactor-engineer-s13.6-t3-summary.md` — this file.

---

## 9. Follow-up work

- DS review of T3 atomic commit.
- T4 (FitWarning typed registry), T5 (schema_version 2.0.0 + CHANGELOG note for the OpportunityContext restructure), T6 (MechanismIntent closed enum), T7 (RULE A null_reason patterns), T7.5 (null-reason enum registry), T8 (S13.6 sprint-close).
- Pre-existing failures (10 baseline) remain out of scope; if any are tied to the T1a strip (the 4 `test_negative_control_*` cases), they should be retired or rewired in a follow-up cleanup ticket — not part of T3.
