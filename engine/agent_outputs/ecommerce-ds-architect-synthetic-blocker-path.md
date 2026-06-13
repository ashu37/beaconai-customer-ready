# DS Architect Path — Synthetic Phase 5 Blocker Fixes

## Scientific Verdict

The PM path is scientifically sound and correctly scoped. I ratify it with one structural strengthening (the targeting-measurement invariant gets a synthetic-matrix-wide regression test, not just a unit test), one explicit guardrail on `inventory_blocked` (fenced to keep it from sliding into measurement-design work), and one cold-start ordering decision (defensive one-liner now, architectural reorder Phase 6).

The blocker fix pass is plumbing and contract enforcement, not new science. After these fixes the engine will be founder/manual-test-ready on the synthetic matrix in the sense that the merchant-visible artifact will not lie, will not crash, will not silently violate the targeting-measurement invariant on receipts, and will not contradict itself between callout and Recommended section.

I do not concede founder readiness on the deeper measurement-design question (`returning_customer_share` as the supporting metric for `first_to_second_purchase`), but per scope rules that is Phase 6 work, not blocker work, and I am not reopening it here. Founder testing on this matrix will likely produce near-uniform ABSTAIN_SOFT pages on healthy fixtures even after the blocker fixes ship; that is the correct epistemic outcome given the current measurement design and is acceptable for the blocker pass.

## Agreed Product Decisions

The following PM decisions are scientifically safe and I ratify them as binding scope:

1. ABSTAIN_SOFT renders zero cards in Recommended. Tightening the prior contract from "0–2 targeting cards" to "0 cards" is the correct contract under any decision-system frame: the page must not visually contradict the callout. Held targeting plays move into Considered with an appropriate reason code.
2. Cold-start must produce a renderable ABSTAIN_HARD briefing, not a Python traceback. Non-negotiable.
3. Inventory state must be visible somewhere on a low-inventory briefing via a typed reason on a Considered card. Minimum surface only — text the merchant can parse, no numeric stock detail.
4. The targeting-measurement invariant must hold on receipts, not just on the rendered surface. Promoted from "internal concern" to blocker.
5. Materiality footer line restored on every non-ABSTAIN_HARD V2 briefing.
6. `VERTICAL_MODE` propagated per scenario in the test harness.
7. Reporter rewrite to read `briefing.html` DOM, not `candidate_debug.json`.
8. Fixture re-tuning is matrix-validity work, not engine work, but must ship in the same pass.

The PM's scenario-level expected-merchant-experience matrix (six scenarios) is the right minimum bar. Implementation-manager treats it as the acceptance contract.

The PM's hard scope-out list is correct. I add nothing to it and I subtract nothing from it.

## Scientific Blockers

In priority order. All seven must be fixed before founder/manual testing.

1. **Cold-start crash (`charts.py:273-274`).** Pre-existing legacy matplotlib defect. V2 ABSTAIN_HARD path is unreachable for any thin-history merchant. Highest severity because the failure mode is a Python traceback.
2. **Targeting-measurement invariant violated structurally on receipts.** `engine_run.json::recommendations[].measurement.p_internal` is non-null with saturated values (`0.0`, `1.6e-72`) on cards whose `evidence_class == "targeting"`. M4b contract violation. The renderer hides it today; hiding is not safety.
3. **Inventory gate not surfacing through V2 considered list.** `gate_inventory` runs in M5 against legacy PlayCards; `populate_considered_from_candidates` reads M3 detector candidates only. Compounded by `bestseller_amplify` not being produced as an M3 base candidate on the low-inventory fixture.
4. **ABSTAIN_SOFT contract drift.** `MAX_ABSTAIN_SOFT_TARGETING_CARDS = 2` plus permissive `decide.py:893-895`. Resolved by PM: drop to zero, route held plays into Considered.
5. **Materiality footer line missing on all six synthetic briefings.** Regression vs `agent_outputs/phase5_samples/beauty_brand_v2_briefing.html`.
6. **`VERTICAL_MODE` not propagated per scenario.** All six ran as beauty. Test-harness defect.
7. **Reporter reads internal artifacts.** Misrepresents merchant-visible state in 5 of 6 scenarios. Test-tooling fix.

## Guardrails For Implementation

1. **`inventory_blocked` reason code stays minimum-surface only.** The minimum acceptable contract is: when a low-inventory hero SKU is detected on the M3 detector, `bestseller_amplify` carries `preliminary_rejection_reason = "inventory_blocked"` and the V2 considered card renders text like "Hero SKU at low stock; held until restock." Implementation-manager rejects any task in this pass that:
   - Defines a vertical-specific low-stock threshold beyond the existing M5 `cover_days < N` rule.
   - Adds multi-SKU aggregation logic for low-stock detection.
   - Surfaces inventory state as a numeric (cover_days, units_left) on the merchant card.
   - Generalizes the `inventory_blocked` pattern to other guardrails (audience-overlap, materiality, anomaly) in this pass.

2. **Targeting-measurement invariant fix is structural, not cosmetic.** A "fix" that only nulls measurement at the renderer is not acceptable. The structural test must run against the synthetic matrix's `engine_run.json` files, not just a unit-level constructed object.

3. **Cold-start fix stays defensive in this pass.** No architectural reorder of `main.py -> charts -> adapter -> V2`. The architectural reorder is real Phase 6 work.

4. **No causal prior added anywhere.** Phase 5.6 directional pathway stays at `revenue_range.suppressed = true`. Opportunity context block (Phase 5.1) stays as-is.

5. **No fixture changes that retarget the engine.** Fixture re-tuning is for fixture realism only. If a re-tuned fixture still does not exercise a pathway, that is acceptable — the engine refusing to fire on a fixture without the signal is correct behavior.

6. **No reporter logic that infers merchant state from internal JSON.** Reporter parses `briefing.html` DOM. May read `engine_run.json::briefing_meta` for vertical/scenario context only.

## ABSTAIN_SOFT Decision-System Contract

I ratify the PM's decision: zero cards in Recommended under ABSTAIN_SOFT. Held targeting plays move to Considered.

From a decision-system perspective:

1. **Page-level non-contradiction.** A merchant must not read "No primary play this month" and then see a non-empty Recommended section directly below. Cannot be patched by callout copy.
2. **Decision-state invariant alignment.** The Phase 1 reconciled invariant says "0 measured/directional in recommendations => ABSTAIN_SOFT, never PUBLISH." The corollary "ABSTAIN_SOFT => recommendations is empty" completes the state machine.
3. **Targeting plays are not lost.** They route into Considered with a typed reason code; the merchant still sees them and still sees `would_fire_if` text.

The Phase 1 memory phrasing of "0–2 targeting cards (suppressed/labeled)" is hereby tightened to zero for the blocker-fix pass forward. This supersedes the prior phrasing.

**Code surface:**
- `src/storytelling_v2.py`: `MAX_ABSTAIN_SOFT_TARGETING_CARDS` -> 0.
- `src/decide.py`: when `decision_state == "abstain_soft"`, `engine_run.recommendations = []`, and any targeting plays previously in `recommendations` are routed into `engine_run.considered` with a typed reason code (e.g., `targeting_held_under_abstain`).
- New test `tests/test_abstain_soft_no_recommendations.py` constructs an EngineRun where the legacy adapter would produce 2 targeting cards under abstain_soft, runs `decide()`, asserts `len(engine_run.recommendations) == 0` and the 2 plays appear in `engine_run.considered`.

## Targeting Measurement Invariant

PM asked me to pick (a) post-hoc clear with assertion, (b) reclassify before measurement is built, or (c) both.

**Pick: (c) both, in the cheap form.**

Rationale: the M4b reclassification happens after `_build_measurement_from_legacy` runs. The cheapest correct fix is two complementary surfaces:

1. **Post-hoc clear with assertion (primary, mandatory).** In `engine_run_adapter._action_to_play_card` (or the terminal step that produces the PlayCard), after evidence class is finalized: if `evidence_class == "targeting"` then `measurement = None`. Add `assert evidence_class != "targeting" or measurement is None, f"Invariant violation: targeting card with non-null measurement on play {play_id}"` immediately after.

2. **Early-return guard at M3 layer (secondary, optional).** In `_build_measurement_from_legacy`, return `None` early when the registry says the play is targeting. One-line guard. If implementation-manager finds this is more than a few lines, drop it and ship (1) alone.

**Why both:** (1) alone is correctness-sufficient but leaves wasted work and a structural defect that recurs. (1)+(2) form a ratchet. The assertion in (1) must raise, not warn — a warning here is the same defect that let saturated stats leak in legacy.

**Pinned structural test (forcing function):**

Two tests in `tests/test_targeting_measurement_invariant.py`:

1. Unit-level: construct an EngineRun where a targeting play has a non-null Measurement, run the terminal adapter/decide step, assert the engine raises or coerces.
2. **Matrix-wide regression guard:** run all 6 synthetic fixtures, for each `engine_run.json` assert:
   ```
   for card in recommendations + considered:
       if card.evidence_class == "targeting":
           assert card.measurement is None
   ```

Test (2) is the regression guard that would have caught promo_anomaly's `1.6e-72` and `0.0` p-internal leaks. Land test first, watch it fail, then ship the fix.

## Inventory / Guardrail Visibility Recommendation

PM proposed `preliminary_rejection_reason="inventory_blocked"` in M3 `detect_candidates`. **Ratified.**

1. **M3 is the canonical V2 source of truth for the considered list.** Putting `inventory_blocked` in M3 surfaces it through the existing pipeline without a new merge step.
2. **Conceptually clean.** Inventory data is an input to candidate detection, not a post-hoc filter on a candidate that already exists.

**Two structural sub-tasks under this:**

1. **Confirm `bestseller_amplify` is currently produced as a base candidate on the low-inventory fixture.** Per the synthetic e2e review, it is not — `candidate_debug.json` shows only `retention_mastery`. This is a separate audience-builder defect that must land in the same pass. If the audience-builder fix is non-trivial (more than a few lines), implementation-manager flags back to PM/DS rather than expanding the blocker pass.

2. **Validate the inventory CSV is being read on the low-inventory fixture.** The "228 days stale" artifact in receipts suggests the validator may be silently dropping the CSV. The fixture-runner-clock fix (PM's "low_inventory CSV reads as 228 days stale") covers this; verify it lands before claiming `inventory_blocked` surfaces correctly.

**Risk note:** if the M3 audience builder for `bestseller_amplify` requires re-thinking bestseller-cohort detection on a low-inventory fixture (e.g., the cohort is small *because* inventory is low), that is a measurement-design rathole — flag back. The acceptable shape: M3 detects the candidate based on historical purchase patterns, *then* the inventory check fires as the rejection reason.

## Cold-Start Recommendation

**Pick: defensive one-liner now. Architectural reorder is Phase 6.**

1. **Bounded fix.** Filter `None` from `recent`/`prior` lists before `ax.bar` (or coerce to `0` with an absence flag). One line.
2. **Architectural reorder is the right long-term shape but a larger refactor.** Doing it during the blocker pass risks breaking the legacy default path while V2 is flag-gated.
3. **`None`-safe, not falsy-safe.** Code as `[v for v in recent if v is not None]`, not `[v for v in recent if v]`. Zero is a legitimate value.
4. **Verify on cold_start_45d specifically.** After the fix, `briefing.html` exists, contains the ABSTAIN_HARD memo, and `engine_run.json` shows `data_quality_flag: INSUFFICIENT_HISTORY` (or equivalent). If the fix unblocks cold_start_45d but reveals a downstream crash, flag back rather than chasing.
5. **Visual check post-fix.** Implementation-manager runs cold_start_45d end-to-end and visually inspects the resulting briefing.html to confirm the chart placeholder is sensible, not just non-crashing.

The architectural reorder (V2 ABSTAIN_HARD upstream of legacy chart rendering) carries forward as a Phase 6 follow-up note in the blocker-pass summary, not as scope creep.

## Reporter / Fixture Recommendations

**Merchant-visible vs internal split (binding for the reporter rewrite):**

Merchant-visible (reporter must read):
- `briefing.html` DOM. Count cards in each section by parsing the rendered HTML.
- `engine_run.json::briefing_meta` for vertical and scenario metadata only (test-context, not state inference).

Internal (reporter must NOT read):
- `candidate_debug.json` (any field).
- `engine_run.json::recommendations[]`, `::considered[]`, `::watching[]` for state inference. May be read only as a structural sanity check (DOM count vs JSON count).
- `v2_sizing_shadow.json`, `receipts/debug.html`, `actions_log` (legacy).

**Fixture retuning — minimum necessary:**

1. `healthy_beauty_240d` L28 returning_customer_share sign re-tune so the L28 delta is positive at the Sep 18 anchor with sign-stable agreement across L56/L90.
2. `supplement_replenishment_240d`: cap returning-customer share below 100%; fix within-window repeat-rate definition; ensure `subscription_nudge` and `empty_bottle` have non-degenerate audiences (loyal-SKU repeater cohort + size-token product metadata).
3. `promo_anomaly_240d`: move anchor or move spike so the spike is within L56.
4. `low_inventory` runner-clock alignment so the inventory CSV is current at run time.

Out of scope for the blocker pass: generator process-driven redesign, tiny-base ratio guard, new fixture archetypes.

## In-Scope For Implementation Manager

Engine plumbing (priority order):
1. **Cold-start defensive fix** in `src/charts.py:273-274`. One line. Verify cold_start_45d produces ABSTAIN_HARD briefing.
2. **Targeting-measurement invariant enforcement.** Both surfaces (post-hoc clear with assertion + M3 early-return guard if cheap). New `tests/test_targeting_measurement_invariant.py` with unit-level + matrix-wide regression tests.
3. **ABSTAIN_SOFT contract enforcement.** `MAX_ABSTAIN_SOFT_TARGETING_CARDS = 0`. Clear `recommendations[]` and route to `considered` in `decide.py`. New `tests/test_abstain_soft_no_recommendations.py`.
4. **Inventory M5 -> V2 considered wiring.** `preliminary_rejection_reason="inventory_blocked"` in M3 `detect_candidates`. Confirm/fix `bestseller_amplify` as a base candidate on the low-inventory fixture.
5. **Materiality footer line restoration.** Compare against `agent_outputs/phase5_samples/beauty_brand_v2_briefing.html`. Fix and add presence test for every non-ABSTAIN_HARD briefing.

Test harness:
6. **Per-scenario `VERTICAL_MODE` propagation.** Assert `engine_run.json::briefing_meta.vertical` matches each scenario's YAML.
7. **Reporter rewrite.** `briefing.html` DOM parser (BeautifulSoup acceptable). Outputs counts of Recommended/Considered/Watching as rendered, plus footer presence and abstain-callout presence.

Fixture retuning:
8. `healthy_beauty_240d` L28 sign.
9. `supplement_replenishment_240d` returning-share/repeat-rate/cohort/metadata.
10. `promo_anomaly_240d` anchor or spike.
11. `low_inventory` runner-clock.

## Out-Of-Scope For Implementation Manager

Implementation-manager rejects any task in this list. Binding.

- Any change to evidence classes, taxonomy, or recommendation tiers.
- Any change to materiality floors.
- Any V2 default flip.
- Any M10 cleanup, including legacy emitter deletion or `journey_optimization` removal from legacy.
- Any reopening of M0–M9, Phase 5, or Phase 5.1 work.
- Any addition of a causal prior. Phase 5.6 stays at `revenue_range.suppressed = true`.
- Any opportunity-context extension. Not extended to targeting cards or Considered cards.
- Restoration of fake p-values, fake CIs, `confidence_score`, `final_score`, legacy dollar projections on targeting cards, Aura, Beacon Score.
- Reason-code taxonomy expansion beyond `inventory_blocked` (no `vertical_not_applicable`, no `materiality_floor_failed` rendering).
- Watching-section never-empty contract.
- Below-scale memo for sub-floor stores.
- State-of-store fact-count determinism.
- Watching copy rewording.
- `returning_customer_share` replacement.
- Supplement-vertical directional pathway, supplement causal prior, replenishment-cycle play.
- Tiny-base ratio guard in state-of-store.
- Materiality floor stamping on `engine_run.json::Scale.materiality_floor`.
- Generator process-driven redesign.
- Architectural reorder of V2 ABSTAIN_HARD upstream of chart rendering.
- Lifecycle memory, recommendation carryover, fatigue logic. Out by hard constraint.
- Vertical-specific inventory thresholds, multi-SKU aggregation, numeric stock surfaces on merchant cards.

## Notes For Implementation Manager

**On execution order:**

1. **Land the structural tests before the fixes.** For both the targeting-measurement invariant and the ABSTAIN_SOFT contract: write the test first, watch it fail on the current matrix, then ship the fix. This confirms the test catches the defect rather than passing vacuously.

2. **The audience-builder fix for `bestseller_amplify` on low-inventory is the highest-risk sub-task.** If it requires re-thinking bestseller-cohort detection logic, that is a measurement-design rathole — flag back. Acceptable shape: M3 detects the candidate based on historical purchase patterns; inventory check fires as the rejection reason after.

3. **The defensive cold-start fix should not silently mask future cold-start defects.** Run cold_start_45d end-to-end and visually inspect the resulting briefing.html. The chart placeholder/empty-state must be sensible, not just non-crashing.

**Where I went beyond what PM asked:**

1. **Targeting-measurement invariant fix shape.** PM proposed (a) post-hoc clear with assertion. I picked (c) both, with M3 early-return as a one-liner ratchet. If implementation-manager finds (b) takes more than a few lines, drop it and ship (a) alone. The structural test is what matters; the fix shape is secondary.

2. **Structural test is two tests, not one.** PM described a single unit test. I extended to (i) the unit test and (ii) a matrix-wide assertion against all six fixtures' `engine_run.json` files. Test (ii) is the regression guard that would have caught promo_anomaly. Both must land.

**Where I disagree with PM but accept the call:**

PM scoped the cold-start fix as defensive one-liner now and architectural reorder as Phase 6. I agree on the call but flag that the architectural reorder eliminates an entire class of "legacy crashes upstream of V2 abstain" defects, not just this one. Carry it forward as a Phase 6 follow-up note in the blocker-pass summary.

**Where I do NOT revisit (per PM's request):**

The ABSTAIN_SOFT + Targeting cards contract. PM decided zero. Ratified. Phase 1 memory's "0–2 targeting cards" phrasing is hereby tightened to zero for the blocker-fix pass forward. This is contract finalization, not re-litigation.
