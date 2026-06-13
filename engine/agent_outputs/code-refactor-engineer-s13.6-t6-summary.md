# code-refactor-engineer — S13.6-T6 summary

**Ticket:** S13.6-T6 — `MechanismIntent` typed atom (Option C bundled atomic commit)
**Date:** 2026-05-31 (resume + execution after the halt + DS adjudication)
**Status:** READY TO COMMIT (engine remains runnable; ledger atomically populated; tests green)

## Scope (revised by DS adjudication on T6 halt; founder approved Option C)

DS verdict on the halt:

- **ADD** `PlayCard.mechanism_intent: Optional[MechanismIntent]` — new additive field, narration agents read the typed atom from the contract (Pivot 2 reaffirmation).
- **RETYPE** `RejectedPlay.mechanism: Optional[str] -> Optional[MechanismIntent]` — completion of T1a prose-strip discipline; the field T1a missed by accident.
- Storytelling consumer rewire DEFERRED to S13.6-T8 (DS Q7 sequencing).
- `priors.yaml` UNCHANGED at T6 (DS Q3c; becomes renderer-side debug-only fallback post-T8).
- DS extends (does NOT retract) original §(d) verdict — the closed-enum lock holds; only the target dataclass needed correcting.

Per founder lock-in #4 (2026-05-30): "Engine ships structured atoms only; narration agents render copy."

## Patch summary

**Schema (DS R6 single-file authority, `src/engine_run.py`):**

- New `MechanismType(str, Enum)` — 10 audit-locked DS §(d) members (`WINBACK_REACTIVATION_EMAIL`, `FIRST_TO_SECOND_NUDGE`, `THRESHOLD_BUNDLE_OFFER`, `DISCOUNT_DEPENDENCY_HYGIENE`, `REPLENISHMENT_REMINDER`, `BESTSELLER_AMPLIFY`, `CATEGORY_EXPANSION`, `SUBSCRIPTION_NUDGE`, `ROUTINE_BUILDER`, `LOOKALIKE_HIGH_VALUE_PROSPECT`). String values equal member names (UPPER_SNAKE_CASE) matching the `WouldBeMeasuredBy` precedent. Closed-set rejection via the standard enum constructor.
- New `MechanismIntent` dataclass — `type: MechanismType` + `parameters: Dict[str, Any] = field(default_factory=dict)`. DS §(d) field-name choice (`type`, not `mechanism_type`) followed verbatim.
- ADDED `PlayCard.mechanism_intent: Optional[MechanismIntent] = None` (additive within v2.0.0 contract freeze per founder lock-in #3).
- RETYPED `RejectedPlay.mechanism: Optional[str] -> Optional[MechanismIntent]`.
- Both new types re-exported via `engine_run.__all__` per DS R6 single-file authority.
- New `_from_dict_mechanism_intent` helper — strict per T3/T4 precedent: `None` / non-dict / legacy str shape -> `None`. Unknown `type` values raise `ValueError` via the closed-enum lock.
- `_from_dict_play_card` round-trips `mechanism_intent`.
- `_from_dict_rejected` routes `mechanism` through the typed-atom deserializer (legacy prose-str shape returns `None` by design — strict cutover; not silently re-parsed).
- CHANGELOG v2.0.0 entry for T6 added (replaces the prior "T6 (pending)" placeholder); records the ADD on PlayCard + RETYPE on RejectedPlay framing, the 5-spec'd / 4-Tier-B parameters acceptance, the strict deserialization carry-forwards, and the deferred T8 storytelling rewire.

**Producer (`src/decide.py`):**

- New `_PLAY_ID_TO_MECHANISM_TYPE` closed map (9 play_ids -> 10 mappings, including the `first_to_second_purchase` / `cohort_journey_first_to_second` aliases).
- New `_parameters_for_mechanism(mtype)` helper — returns DS §(d) parameter dict for the 5 spec'd types (values sourced from the `_PRIOR_ANCHORED` registry constants + existing builder constants per DS Q2 pick (b); marked `TODO(S14): source from real-merchant config` where the knob currently uses a sensible default); returns `{}` for the 4 Tier-B types + `LOOKALIKE_HIGH_VALUE_PROSPECT` per DS §(d) acceptance.
- New `_build_mechanism_intent(play_id)` helper — returns `None` for unmapped play_ids (strict — do not invent); otherwise returns the typed atom.
- The 4 RejectedPlay producer sites swapped from `_surface_mechanism_for_play` (returns YAML prose str) to `_build_mechanism_intent` (returns the typed atom):
  - `populate_considered_from_candidates` (~L814)
  - `_route_window_disagreement_holds` (~L1339)
  - `_route_prior_unvalidated_holds` (~L1443)
  - `_route_observed_effect_eligibility_holds` (~L1672)
- The experiment PlayCard producer (`_build_experiment_play_cards` at decide.py ~L2072) now populates `mechanism_intent`.
- `_surface_mechanism_for_play` is retained per DS Q3c — the docstring documents its new status as the renderer-side debug fallback path (called only from `storytelling_v2._mechanism_for_play`); producers no longer call it for `RejectedPlay.mechanism`.

**Producer (`src/measurement_builder.py`):**

- Both prior-anchored PlayCard construction sites (`build_prior_anchored_play_card` suppressed path at L661 + non-suppressed path at L2438) populate `mechanism_intent=_build_mechanism_intent(play_id)` via a lazy import (avoids `decide.py <-> measurement_builder.py` import-ordering churn).

**Producer (`src/engine_run_adapter.py`):**

- Legacy `_action_to_play_card` PlayCard construction populates `mechanism_intent` for completeness (lazy import; returns `None` for unmapped legacy play_ids).

**Renderer compatibility shim (`src/storytelling_v2.py`):**

- `_rej_has_t3z_fields`: when `rej.mechanism is None` the T3.z lede does NOT activate (preserves section-scope rule — Considered is not the place for action copy when the producer did not populate). When the producer emitted a typed `MechanismIntent`, the renderer counts that as a populated T3.z field.
- `render_rejected_card`: when `rej.mechanism` is a `MechanismIntent`, the renderer falls back to the `_mechanism_for_play(rej.play_id)` YAML lookup (priors.yaml is the established renderer-side fallback per DS Q3c). No engine-authored prose is introduced; the same YAML string that pre-T6 producers wrote into the field is now sourced via play_id lookup at render time. The T8 consumer rewire will compose copy from `type + parameters` structurally.

**Repin (`scripts/s13_6_t6_repin.py` + `tests/fixtures/pinned_sha_ledger.json`):**

- New repin script modelled on `scripts/s13_6_t5_repin.py`.
- Ledger populated atomically with `post_s13_6_t6` SHAs for all 5 pinned fixtures + cumulative `diff_confined_to` annotations + `post_s13_6_t6_definition` meta block.

## Files changed

| File | Change |
|---|---|
| `src/engine_run.py` | Add `MechanismType` enum + `MechanismIntent` dataclass; add `PlayCard.mechanism_intent` field; retype `RejectedPlay.mechanism`; add `_from_dict_mechanism_intent`; wire round-trip; extend `__all__`; CHANGELOG v2.0.0 T6 entry. |
| `src/decide.py` | Add `MechanismIntent` / `MechanismType` imports; add `_PLAY_ID_TO_MECHANISM_TYPE` map, `_parameters_for_mechanism`, `_build_mechanism_intent`; swap 4 RejectedPlay producer sites; wire `_build_experiment_play_cards` PlayCard producer; update `_surface_mechanism_for_play` docstring (retained, no behavior change). |
| `src/measurement_builder.py` | Wire `mechanism_intent` on both `build_prior_anchored_play_card` PlayCard return sites (lazy import). |
| `src/engine_run_adapter.py` | Wire `mechanism_intent` on `_action_to_play_card` PlayCard return (lazy import). |
| `src/storytelling_v2.py` | Compatibility shim at `_rej_has_t3z_fields` + `render_rejected_card`: typed `MechanismIntent` falls back to `_mechanism_for_play` YAML lookup; `None` preserves the pre-T6 "no mechanism rendered" behavior. |
| `scripts/s13_6_t6_repin.py` | NEW — captures post-T6 SHAs on the 5 pinned fixtures. |
| `tests/fixtures/pinned_sha_ledger.json` | New `post_s13_6_t6` SHA entries + cumulative `diff_confined_to` notes + `_meta.post_s13_6_t6_definition`. |
| `tests/test_s13_6_t6_mechanism_intent_atom.py` | NEW — 23 tests covering the closed enum, dataclass shape, PlayCard/RejectedPlay annotations, producer helper coverage (9 mapped play_ids + unmapped None), Tier-B empty-params acceptance, JSON-shape serialization, strict deserialization (legacy str -> None), re-export sanity, AST sweep over `src/` for literal `mechanism="<str>"` construction. |
| `tests/test_s6_t3_5_considered_surface_population.py` | Update 3 assertions from `rej.mechanism.strip() != ""` to `isinstance(rej.mechanism, MechanismIntent)` per the T6 contract retype. |

## Tests run

- `tests/test_s13_6_t6_mechanism_intent_atom.py`: **23 passed**.
- All S13.6 tests (T1a / T1a-outcome-log / T1b / T2 / T3 / T4 / T5 / T6): **86 passed**.
- Focused sweep (`decide`, `measurement`, `s6_t3`, `s7_priors`, `considered`, `rejected`, `t1a`, `t1b`): **305 passed, 1 pre-existing failure** (`tests/test_s3_memory_event_schemas.py::test_recommendation_considered_payload_supports_null_evidence` — pre-existing T1a-related; reproduces on the baseline `git stash`).
- Full suite (`-x` deferred; deselected pre-existing): **2233 passed, 15 skipped, 6 xfailed, 9 pre-existing baseline failures**.
- Repin script (`python scripts/s13_6_t6_repin.py`): all 5 pinned fixtures produced an `engine_run.json` and a SHA; engine remains runnable end-to-end.

Pre-existing baseline failures (NOT introduced by T6 — confirmed via `git stash` re-run):
1. `tests/test_phase5_considered_always.py::test_abstain_soft_briefing_renders_populated_considered_section` (T1a `would_fire_if` strip).
2. `tests/test_recommended_experiment_forbidden_tokens.py::test_negative_control_*` (4 tests; T1a `recommendation_text` strip).
3. `tests/test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1` + `tests/test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off` (ML flag default drift).
4. `tests/test_s3_memory_event_schemas.py::test_recommendation_emitted_payload_to_dict` + `test_recommendation_considered_payload_supports_null_evidence` (T1a `evidence_snapshot` strip).
5. `tests/test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh` (synthetic fixture date drift).

## Behavior changes

- `engine_run.json` SHA shifts for every PlayCard (new `mechanism_intent` field; populated on mapped play_ids, null on unmapped) AND for every emitted `RejectedPlay` (`mechanism` shape change str -> typed object; null on unmapped). New `post_s13_6_t6` SHAs in the ledger.
- `briefing.html` renderer continues to surface the "What we'd send" mechanism string on Considered cards via the YAML-lookup fallback path. Section-scope rule preserved (no mechanism line on Considered when the producer left `rej.mechanism` as `None`). Watching cards remain metric-only.
- The renderer never raises on `RejectedPlay.mechanism` being a `MechanismIntent` — the shim treats typed atoms as "defer to YAML lookup."

## Artifacts added

- `scripts/s13_6_t6_repin.py`
- `tests/test_s13_6_t6_mechanism_intent_atom.py`
- `agent_outputs/code-refactor-engineer-s13.6-t6-summary.md` (this file, replacing the prior halt summary)

## Remaining risks

1. **Renderer YAML-fallback feels like a stopgap.** It is — DS Q7 explicitly defers the structural render to T8. Acceptable because (a) priors.yaml is the established renderer-side fallback per DS Q3c, (b) no engine-authored prose is introduced, (c) the typed atom is in the contract so narration agents can consume it independently of the local renderer.
2. **Pre-existing baseline failures unrelated to T6.** Logged above; they are T1a / S12 follow-ups, not T6 regressions.
3. **Tier-B + lookalike parameters are `{}` placeholders.** Acceptable for v2.0.0 per DS §(d) ("flesh out at S14+"). When narration agents render Tier-B mechanism copy from `type + {}`, they will produce a "structured but content-empty" atom — narration must handle that gracefully.
4. **`_PLAY_ID_TO_MECHANISM_TYPE` is the load-bearing map.** Adding a new typed Tier-B builder in the future requires extending this map (plus the optional `_parameters_for_mechanism` branch). The audit confirmed zero unmapped emission sites on Beauty + Supplements fixtures at T6.
5. **`_surface_mechanism_for_play` retained.** Per DS Q3c, it stays as the renderer-side debug fallback path called from `storytelling_v2._mechanism_for_play`. Removing it cleanly is part of T8 scope.

## Follow-up work (T8 dependency)

- **S13.6-T8 (DS Q7):** rewire `storytelling_v2._render_what_we_send` + `_mechanism_for_play` to compose merchant-facing copy from `PlayCard.mechanism_intent` (typed atom) directly, retiring the YAML-string lookup at render time. priors.yaml `metadata.mechanism` becomes debug-only post-T8.
- **Pivot 2 reaffirmation addendum** lands on `PIVOTS.md` at T8 close (NOT this commit; DS Q7 sequencing).
- **S13.7-T3 (DS §(d)):** publish `docs/mechanism_contract.md` documenting the per-type parameters shape spec; tighten the `TODO(S14): source from real-merchant config` markers.
- **S14+:** flesh out Tier-B parameters dict; promote `LOOKALIKE_HIGH_VALUE_PROSPECT` to a producer-emitted mechanism.

## Deviation check

One — Option C scope (ADD on PlayCard + RETYPE on RejectedPlay + defer storytelling consumer rewire to T8) was approved by DS adjudication + founder 2026-05-31. The dispatch brief's original "retype `PlayCard.mechanism`" framing was factually incorrect (the field did not exist on PlayCard); Option C resolves the surprise and ships the contract intent. No further deviations.

### DS Revision (2026-06-01)

**DS finding (Q5):** the 5 spec'd `parameters` dicts shipped in the initial T6 execution did not match DS §(d) verbatim keys for 4 of 5 types. WINBACK matched as-shipped; FIRST_TO_SECOND, THRESHOLD_BUNDLE, DISCOUNT_DEPENDENCY, and REPLENISHMENT each carried a different (engine-side knob) key set. DS APPROVE-WITH-CHANGES: rewrite `_parameters_for_mechanism` to the §(d) verbatim sets, add 5 verbatim-key tests, re-pin SHAs.

**4-type rewrite (`src/decide.py` `_parameters_for_mechanism`):**

- `FIRST_TO_SECOND_NUDGE`: `{days_since_first_order_window: [30, 90], measurement_window_days: 30}`. `days_since_first_order_window` sourced from the `cohort_journey_first_to_second_candidates` builder constants at `src/audience_builders.py` L716 (DS-locked 2026-05-19). `measurement_window_days` text-derived from the `_PRIOR_ANCHORED["cohort_journey_first_to_second"].mechanism_text` ("...second purchase within 30 days.").
- `THRESHOLD_BUNDLE_OFFER`: `{threshold_aov: None, current_median_aov: None}`. Both `None` with `# TODO(S14)` markers — the decide-seam does not have a source today (`threshold_aov` is a per-merchant bundle target $ amount not on the registry; `current_median_aov` lives on store_profile / measurement context and is not threaded to the MechanismIntent producer).
- `DISCOUNT_DEPENDENCY_HYGIENE`: `{current_discount_share: None, target_discount_share: None}`. Both `None` with `# TODO(S14)` markers — `compute_heavy_discount_share_of_revenue` exists in `measurement_builder.py` but is not threaded to the decide-seam; the discount_dependency builder + registry entry expose neither as an instance/registry attribute.
- `REPLENISHMENT_REMINDER`: `{replenishment_window_days: None, sku_class: None}`. Both `None` with `# TODO(S14)` markers — the `replenishment_due_candidates` builder computes per-SKU cadence median at runtime (`src/audience_builders.py` L351-358) and yields one cohort per in-class SKU; there is no single store-level `replenishment_window_days` int or single `sku_class` string on the decide-seam.

Per DS posture: `None` + `# TODO(S14): source from <seam>` markers are preferable to silent substitution. The §(d) key sets are now contract-faithful; values are honest about seam absence.

**5 verbatim-key tests** added to `tests/test_s13_6_t6_mechanism_intent_atom.py` (new section 11). Each asserts `set(mi.parameters.keys()) == {<DS §(d) keys verbatim>}` for the 5 spec'd types. FIRST_TO_SECOND additionally asserts `days_since_first_order_window` is a 2-int list (DS §(d) typing). Existing 23 tests preserved; suite is now 28p.

**Re-pinned SHAs (`tests/fixtures/pinned_sha_ledger.json`):**

| Fixture | Pre-revision SHA | Post-revision SHA |
|---|---|---|
| healthy_beauty_240d | 51205f48… | a0205a29… |
| healthy_supplements_240d | 5ace439c… | be366fe2… |
| small_store_240d | f982e8c3… | 248d5de5… |
| cold_start_45d | 9c488f96… | 6fde7cb2… |
| healthy_beauty_low_inventory_240d | 85293ade… | 4597df61… |

**Out of scope for this revision (unchanged):** enum, dataclass field annotations, `_build_mechanism_intent` signature, 5 producer wiring sites, renderer shim, CHANGELOG, priors.yaml, storytelling_v2 — all PASSED at the initial T6 DS verdict and were not touched.

**Deviation check: none.** DS APPROVE-WITH-CHANGES revision within the approved Option C scope; the original "Deviation check: one" still describes the parent scope.
