# S7.6-CLI-FIX — populate Measurement.observed_effect/p_internal/n on Tier-B prior-anchored cards from blend_provenance stash

**Author:** code-refactor-engineer
**Date:** 2026-05-23
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `d8ede8c`
**Approved ticket:** S7.6-CLI-FIX — Per DS architect verdict 2026-05-23 (`agent_outputs/ecommerce-ds-architect-s7_6-cli-wiring-gap-verdict-2026-05-23.md`). Single-function surgical fix to surface observed-effect data on the canonical `Measurement` slot in `engine_run.json`. Engine math was correct; only the typed receipt slot was empty. Three fields populated from existing `blend_provenance` stash (per DS verdict §2 — `consistency_across_windows` explicitly out of scope per founder-confirmed 2026-05-23).

## 1. Approved scope

- Populate `Measurement.observed_effect` from the primary-window observed rate stashed in `blend_provenance.observed_windows`.
- Populate `Measurement.p_internal` from the L28 helper p-value carried in the `observed_windows` stash.
- Populate `Measurement.n` from `observed_n` (NOT `audience_size`).
- Two-clause tripwire test in `tests/test_s7_6_c1_priority_prepend_invariant.py` covering the four wired Tier-B plays (`winback_dormant_cohort`, `discount_dependency_hygiene`, `cohort_journey_first_to_second`, `aov_lift_via_threshold_bundle`; `replenishment_due` intentionally omitted per DS Option iii 2026-05-23).

## 2. Patch summary

Surgical insertion at `src/measurement_builder.py:2252-2270` inside `build_prior_anchored_play_card`, immediately after the `blend_provenance["observed_windows"]` stash assembly (line 2250) and within the existing `if observed_agreement is not None:` block (starting line 2231). The three fields populate only when `primary_obs_result is not None and int(primary_obs_result.n) > 0` — cold-start path stays byte-identical. `Measurement` dataclass construction at line 2189-2197 unchanged. No new PlayCard attribute added; `drivers[]` remains the source of truth and `_blend_provenance_for_card` at `src/decide.py:1524-1535` is byte-identical for the T6 copy ladder.

## 3. Files changed

- `src/measurement_builder.py` — 19 lines added at 2252-2270 populating `measurement.observed_effect = round(float(primary_obs_result.effect), 6)`, `measurement.n = int(primary_obs_result.n)`, `measurement.p_internal = round(float(primary_obs_result.p_value), 6)`.
- `tests/test_s7_6_c1_priority_prepend_invariant.py` — 101 lines appended; new test `test_tier_b_recommended_cards_surface_observed_effect_on_beauty` with two-clause invariant (drivers carries blend_provenance with observed_n>0 AND measurement.observed_effect is not None AND measurement.n>0).

## 4. Tests/checks run

- New tripwire test: PASS (4 wired Tier-B plays).
- S7.6 invariant suite (`tests/test_s7_6_c1_priority_prepend_invariant.py`): 8 passed, 2 xfailed (matches pre-state).
- M0 golden tests (small_sm, mid_shopify, micro_coldstart): byte-identical.
- Full suite: 1769 → **1770 passed**, 14 skipped, 4 xfailed, 2 xpassed, 0 failed.

## 5. Behavior changes

CLI-mode `engine_run.json` now carries `measurement.observed_effect`, `measurement.n`, and `measurement.p_internal` on Tier-B Recommended cards where the per-store observed-effect helper ran. Verified empirically on Beauty:
- `winback_dormant_cohort`: `m.observed_effect=0.057065, m.n=448, m.p_internal=0.065477`
- `discount_dependency_hygiene`: `m.observed_effect=0.038045, m.n=224077, m.p_internal=0.0`
- `cohort_journey_first_to_second`: `m.observed_effect=0.037297, m.n=603, m.p_internal=0.042212`

`drivers[]` and `_blend_provenance_for_card` semantics unchanged. Single-demote-channel invariant untouched (fix is purely inside `build_prior_anchored_play_card`).

Beauty pinned slate sha256 `fcd2924bc18d726fa18bf407c77ba433ba89a4563d3ad413a466b063c8eeb056` → **unchanged** (pin is on HTML briefing, which does not render `measurement.observed_effect`).
Supplements pinned slate sha256 `13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344` → **unchanged**.
M0 byte-identical.

## 6. Artifacts added

- `tests/test_s7_6_c1_priority_prepend_invariant.py::test_tier_b_recommended_cards_surface_observed_effect_on_beauty`
- `agent_outputs/code-refactor-engineer-s7_6-cli-fix-summary.md` (this file; backfilled 2026-05-25)

## 7. Remaining risks

- **`consistency_across_windows` deferred** per DS verdict §2 (founder-confirmed 2026-05-23: three fields only, no 4th). If this field is needed in the future, requires its own DS verdict. Documented in `Measurement` field-population docstring; do NOT silently add the 4th field.
- **`briefing.html` does NOT render the new Measurement fields.** Founder-confirmed 2026-05-24: `briefing.html` is debug-only wiring scheduled to retire when the frontend app activates. Inspection during beta-prep uses `engine_run.json` directly (canonical contract per Phase 6B Stop-Coding Line).
- **KI-NEW-O test-hygiene refresh deferred** to a separate test-hygiene pass (founder-confirmed 2026-05-24).

## 8. Follow-up work

- Orchestrator doc-sweep (memory.md + ARCHITECTURE_PLAN.md LOAD-BEARING UPDATE) to document the fix + the founder-confirmed deferrals.
- S8 prerequisite KI-NEW-K Beauty Beta envelope re-fit (DS-tracked separately).

## 9. Verbatim founder ask answers

- **Three fields populate from blend_provenance stash:** confirmed (observed_effect, n, p_internal). `consistency_across_windows` NOT populated per DS verdict §2.
- **Test scope:** four wired Tier-B plays; `replenishment_due` omitted per DS Option iii 2026-05-23.
- **Re-pin posture:** Beauty + Supplements sha256 unchanged (pin is on HTML; renderer does not surface observed_effect).
- **Suite count:** 1769 → 1770 passed (+1 = new tripwire test).
- **M0 byte-identical:** confirmed.
- **Commit sha:** `d8ede8c`.
