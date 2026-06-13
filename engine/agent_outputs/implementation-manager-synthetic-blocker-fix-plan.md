# Implementation Plan — Synthetic Phase 5 Blocker Fixes

_Author: Implementation Manager_
_Date: 2026-05-04_
_Status: Plan only. No code edits performed in this pass. Hand-off to code-refactor-engineer at the bottom._
_Sources: `agent_outputs/synthetic-phase5-e2e-final-review.md`, `agent_outputs/product-strategy-pm-synthetic-blocker-path.md` (binding), `agent_outputs/ecommerce-ds-architect-synthetic-blocker-path.md` (binding, ratifies PM), prior plan thread `agent_outputs/implementation-manager-overhaul-plan-final.md`._

## Implementation Verdict

The synthetic Phase 5 e2e review surfaces a small set of plumbing defects between layers that already exist (legacy adapter -> M5 guardrails -> M3 detect -> V2 considered -> V2 renderer), plus one product-contract decision (resolved by PM: ABSTAIN_SOFT -> 0 cards in Recommended), plus a test-harness defect (per-scenario VERTICAL_MODE not propagated, reporter reads internal JSON), plus four fixture-realism gaps. None require new science, no new evidence tier, no new causal prior, no opportunity-context extension, no lifecycle memory, no M10 cleanup, no V2 default flip, no materiality floor change.

This is a contract-enforcement and plumbing pass. The engine remains runnable after every fix. Tests land before fixes where DS specifically asked for it (targeting-measurement invariant matrix-wide regression test; ABSTAIN_SOFT no-recommendations test). The plan is structured as 11 ordered fixes (5 engine, 2 harness, 4 fixture) sequenced so that (a) the cold-start crash unblocks the matrix immediately, (b) structural tests land before the structural fix, and (c) fixture re-tuning is the last thing because it depends on the matrix runner being honest about what `briefing.html` shows.

After this pass, the synthetic matrix re-run should clear 8 of 9 of the PM founder-test acceptance criteria; the 9th is gated on the low_inventory CSV runner-clock fix landing cleanly enough that `bestseller_amplify` actually surfaces as a candidate.

## Scope

In scope (locked by PM + DS):

Engine plumbing (5 fixes):
1. Cold-start defensive one-liner in `src/charts.py:273-274`.
2. Targeting-measurement invariant enforcement (post-hoc clear with assertion at adapter terminal step + early-return guard in `_build_measurement_from_legacy` if cheap; structural matrix-wide regression test).
3. ABSTAIN_SOFT contract enforcement (`MAX_ABSTAIN_SOFT_TARGETING_CARDS` -> 0; `decide()` clears `recommendations[]` and routes held targeting plays into `considered` with typed reason code).
4. Inventory M5 -> V2 considered wiring (preliminary_rejection_reason="inventory_blocked" in M3 `detect_candidates`; confirm/fix `bestseller_amplify` as a base candidate on low-inventory fixture only if cheap; flag back if it opens a measurement-design rathole).
5. Materiality footer line restoration on every non-ABSTAIN_HARD V2 briefing (regression vs `agent_outputs/phase5_samples/beauty_brand_v2_briefing.html`).

Test harness (2 fixes):
6. Per-scenario `VERTICAL_MODE` propagation; assert `engine_run.json::briefing_meta.vertical` matches each scenario's YAML.
7. Reporter rewrite to parse `briefing.html` DOM (BeautifulSoup acceptable). Reporter must NOT read `candidate_debug.json` or `engine_run.recommendations[]` for state inference; may read `engine_run.json::briefing_meta` only as test-context.

Fixture retuning (4 fixes):
8. `healthy_beauty_240d` L28 returning_customer_share sign at the Sep 18 anchor (positive, sign-stable across L56/L90).
9. `supplement_replenishment_240d` cap returning-share <100%; fix within-window repeat-rate definition; loyal-SKU repeater cohort; size-token product metadata.
10. `promo_anomaly_240d` move anchor or move spike so spike is within L56.
11. `low_inventory` runner-clock alignment (CSV must not read as 228 days stale at run time).

## Non-Goals

Hard out for this pass (binding from PM + DS, do not re-litigate):

- No change to evidence classes, taxonomy, or recommendation tiers (measured / directional / targeting stay; Strong / Emerging / Targeting buckets stay).
- No change to materiality floors. Stays at the M5 contract values.
- No V2 default flip. Stays behind flags.
- No M10 cleanup, including legacy emitter deletion or `journey_optimization` removal from legacy.
- No reopening of M0-M9, Phase 5, or Phase 5.1 work.
- No new causal prior. Phase 5.6 directional pathway stays at `revenue_range.suppressed=true`.
- No opportunity-context extension. Phase 5.1 already added the addressable-value block; do not extend to targeting cards or to Considered cards.
- No restoration of fake p-values, fake CIs, `confidence_score`, `final_score`, legacy dollar projections on targeting cards, Aura, Beacon Score.
- No reason-code taxonomy expansion beyond the new `inventory_blocked` (or equivalent) and the new `targeting_held_under_abstain` (or equivalent). No `vertical_not_applicable`, no `materiality_floor_failed` rendering in this pass.
- No Watching-section never-empty contract, no below-scale memo, no state-of-store fact-count determinism, no Watching copy rewording. All Phase 6.
- No `returning_customer_share` replacement. Phase 6 measurement-design work.
- No supplement-vertical directional pathway, no replenishment-cycle play, no supplement causal prior.
- No tiny-base ratio guard in state-of-store.
- No materiality floor stamping on `engine_run.json::Scale.materiality_floor`. Phase 6 receipts-completeness work.
- No generator process-driven redesign.
- No architectural reorder of V2 ABSTAIN_HARD upstream of chart rendering. Defensive one-liner only.
- No vertical-specific inventory thresholds, no multi-SKU aggregation, no numeric stock surfaces on merchant cards.
- No lifecycle memory, no recommendation carryover semantics across runs, no fatigue logic.
- No production integrations (Klaviyo, Shopify network calls).

## Ordered Fix Plan

The fixes are ordered to keep the engine runnable after each step, to land structural tests before the corresponding fix, and to put the cheapest unblock first so the matrix can re-run iteratively.

---

### Fix 1 — Cold-start defensive one-liner

**goal**
`cold_start_45d` must produce a renderable `briefing.html` with the ABSTAIN_HARD memo, not a Python traceback. Bound to a single change in `src/charts.py:273-274`.

**why it matters**
Highest-severity defect in the matrix. The failure mode is a Python traceback, which is unsurvivable for a "data scientist replacement" product on the most common low-data case. Unblocking this is also the cheapest single change in the pass, so it goes first.

**likely files**
- `src/charts.py:270-274` — filter `None` from `recent` and `prior` before `ax.bar`. None-safe (not falsy-safe): `[v for v in recent if v is not None]`. Zero is a legitimate value.

**acceptance criteria**
- `cold_start_45d` synthetic scenario runs end-to-end without raising.
- The resulting `briefing.html` exists and contains the ABSTAIN_HARD data-quality memo layout (per `src/storytelling_v2.py` ABSTAIN_HARD branch).
- `engine_run.json` shows `data_quality_flag: INSUFFICIENT_HISTORY` (or the existing equivalent).
- Visual inspection of the chart placeholder is sensible (a placeholder image, not a half-empty bar chart).
- Default flags-off path (legacy renderer) on existing pinned fixtures stays byte-identical to the M0 goldens.

**tests**
- Existing `tests/test_golden_diff.py` continues to pass with no goldens re-baselined.
- New regression test (lightweight): construct a `_collect_window_metric_rows` result containing a `None` in `recent`/`prior`, call into the chart helper, assert no exception is raised. Pin the None-safe behavior at the unit level.
- Manual visual: run `cold_start_45d` and open the resulting `briefing.html`; chart placeholder is sensible.

**rollback / safety notes**
- Single-line change. Fully reversible by reverting the comprehension filter.
- Must be `is not None`, NOT a falsy filter. Zero is a legitimate metric value and removing zeros corrupts the chart.
- If the fix unblocks `cold_start_45d` but reveals a downstream crash, flag back to PM/DS rather than chasing. Do not expand scope.
- The architectural reorder (V2 ABSTAIN_HARD upstream of chart rendering) is explicitly Phase 6. Do not attempt it here.

---

### Fix 2 — Targeting-measurement invariant: structural tests first, then the fix

**goal**
Any PlayCard with `evidence_class == "targeting"` MUST have `measurement is None`, on receipts, not just on the rendered surface. Today saturated `p_internal` (0.0, 1.6e-72) leaks through on `promo_anomaly` targeting cards.

**why it matters**
DS Architect promoted this from "internal concern" to blocker. The renderer hides it today; hiding is not safety. Future regressions can leak through. The structural fix and the matrix-wide regression test make the invariant a forcing function.

**likely files**
- `tests/test_targeting_measurement_invariant.py` — NEW file, two tests:
  - Unit test: construct an EngineRun where a targeting-class PlayCard carries a non-null Measurement, run the terminal adapter/decide step, assert it raises or coerces measurement to None.
  - Matrix-wide regression test: load each of the 6 fixtures' `engine_run.json` (after the matrix runs), iterate `recommendations + considered`, assert `card.evidence_class == "targeting"` implies `card.measurement is None`.
- `src/engine_run_adapter.py` (terminal step around `_action_to_play_card`, lines 202-218) — post-hoc clear with assertion. After the PlayCard is constructed, if `evidence_class == TARGETING` then force `measurement = None` and `assert measurement is None`. The existing early-return at `_build_measurement_from_legacy:112-113` already short-circuits when the legacy action's `evidence_class == "targeting"` is set, but the leak path is candidates that arrive WITHOUT that legacy stamp and only get reclassified by M4b later. The post-hoc clear at the terminal step closes that gap.
- `src/measurement_builder.py` (around `_SUPPORTED` map, lines 108-130) — DS calls out that the early-return guard in `_build_measurement_from_legacy` is already there. Do NOT touch the `_SUPPORTED` map (Phase 5.6 / Phase 6 contract). Only verify the early-return is wired correctly. If a small additional early-return guard at the M3-derived path is required, drop it if non-trivial and ship the post-hoc clear alone.

**acceptance criteria**
- Both tests in `tests/test_targeting_measurement_invariant.py` exist and FAIL on the current matrix (run the test before the fix, watch it fail, then ship the fix and watch it pass — DS-specified order).
- After the fix, both tests pass.
- After the fix, none of the 6 fixtures' `engine_run.json` carries a targeting card with a non-null measurement object.
- The renderer-side targeting no-dollar-headline invariant test (`tests/test_targeting_no_dollar_headline.py`) continues to pass (this is the cosmetic guarantee; the new matrix test is the structural guarantee).
- No legacy goldens re-baselined.

**tests**
- `tests/test_targeting_measurement_invariant.py` (new) — unit + matrix-wide.
- `tests/test_targeting_no_dollar_headline.py` (existing) — must continue to pass.
- `tests/test_golden_diff.py` (existing) — must continue to pass with no re-baseline.

**rollback / safety notes**
- The post-hoc clear is a structural enforcement, not a stats change. Reverting it does not break legacy.
- The matrix-wide regression test depends on the matrix runner producing `engine_run.json` for each fixture; this lands after Fix 7 (reporter / harness has been rewritten and the matrix is honest), but the unit test alone can land before Fix 7 and is enough to validate the engine-level fix.
- Acceptable degraded form per DS: ship post-hoc clear alone if the M3 early-return guard is more than a few lines.
- Assertion must `raise`, not warn. A warning here is the same defect that let saturated stats leak in legacy.

---

### Fix 3 — ABSTAIN_SOFT contract enforcement: structural test first, then the fix

**goal**
When `decision_state == abstain_soft`, `engine_run.recommendations` MUST be empty. Held targeting plays move to `engine_run.considered` with a typed reason code (`targeting_held_under_abstain` or equivalent).

**why it matters**
PM-decided contract: zero cards in Recommended under ABSTAIN_SOFT. Today `promo_anomaly` renders the "No primary play this month" callout with 2 Targeting cards directly below it. The page contradicts itself.

**likely files**
- `tests/test_abstain_soft_no_recommendations.py` — NEW file. Construct an EngineRun where the legacy adapter would emit 2 targeting cards under abstain_soft, run `decide()`, assert `len(engine_run.recommendations) == 0` and the 2 plays appear in `engine_run.considered` with the new reason code.
- `src/storytelling_v2.py:77` — `MAX_ABSTAIN_SOFT_TARGETING_CARDS = 2` -> `MAX_ABSTAIN_SOFT_TARGETING_CARDS = 0`. Update the docstring comment on the same line that says "PM Q4: 0-2" to reflect the tightened contract.
- `src/storytelling_v2.py:626-628` — the `cards = cards[:MAX_ABSTAIN_SOFT_TARGETING_CARDS]` line will now slice to zero. Remove the line entirely OR keep it for clarity; either is fine. If the call site has a side effect on the empty-message text (line 645-650), verify the empty-message branch still produces sensible copy.
- `src/decide.py` ABSTAIN_SOFT branch (around the `_decide_abstain_state -> ABSTAIN_SOFT` transition near lines 866-871, plus the `decide()` body around line 893-895) — when state transitions to `ABSTAIN_SOFT`, take the current `head` (capped recommendations) and route any targeting-class cards into `engine_run.considered` with `reason_code = TARGETING_HELD_UNDER_ABSTAIN` (new) or repurpose `NO_MEASURED_SIGNAL` if PM accepts that (PM doc line 67 says "appropriate reason code, e.g. `targeting_non_causal_prior` or equivalent"). Then clear `engine_run.recommendations = []`.
- `src/engine_run.py` — if a new `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN` enum value is introduced, add it to the enum. If reusing an existing code is preferred (e.g., `NO_MEASURED_SIGNAL`), do not extend the enum; pick whichever keeps the change smallest. PM and DS both accept either.
- `src/decide.py:_PRELIM_REASON_MAP` (lines 370-379) — no change needed. `_PRELIM_REASON_MAP` only maps M3 detector preliminary reasons; the new path maps a decide-state transition, not a candidate's preliminary reason.

**acceptance criteria**
- `tests/test_abstain_soft_no_recommendations.py` exists and FAILS on the current code path (PM contract violation visible). After the fix, it passes.
- After the fix: on `promo_anomaly_240d`, `briefing.html`'s Recommended section is empty (or shows only the "No targeting plays met audience-floor and overlap rules this run." or equivalent empty-message), the formerly-rendered 2 targeting plays appear in Considered with the new reason code.
- ABSTAIN_SOFT-callout copy unchanged (Phase 5.1 reason text stays).
- PUBLISH-with-targeting-cards behavior unchanged: targeting cards still render in Recommended when `decision_state == publish`.
- `tests/test_render_v2.py` continues to pass (any test currently asserting MAX_ABSTAIN_SOFT_TARGETING_CARDS == 2 must be updated to 0 in this PR; treat that as part of this fix's scope).
- No legacy goldens re-baselined.

**tests**
- `tests/test_abstain_soft_no_recommendations.py` (new).
- `tests/test_render_v2.py` (existing; may need a one-line update).
- `tests/test_decide.py` (existing; may need an update if any test asserts targeting-cards-allowed-under-abstain).
- `tests/test_targeting_no_dollar_headline.py` (existing) — still passes (no targeting card under abstain_soft means the assertion is vacuously true on those scenarios; PUBLISH scenarios still exercise it).

**rollback / safety notes**
- Two-line semantic change with explicit test backing. Reverting reverts cleanly.
- Held targeting plays are NOT lost; they appear in Considered with `would_fire_if` text. Merchant still sees them.
- Phase 1 memory phrasing of "0-2 targeting cards" is hereby tightened to 0 per PM. Add a one-line note in the next commit message referencing PM's decision.

---

### Fix 4 — Inventory M5 -> V2 considered wiring (`inventory_blocked`)

**goal**
`healthy_beauty_low_inventory_240d` must surface inventory state on at least one Considered card, with merchant-readable copy. Minimum surface only: typed reason code + parseable text. No numeric stock detail. No vertical-specific thresholds. No multi-SKU aggregation.

**why it matters**
Whole point of the low_inventory fixture is for a merchant to read the page and see that a hero SKU is held because of stock. Today the briefing is byte-substitutable with the healthy beauty briefing. If a merchant cannot see inventory state on this page, the engine has failed its claim of operational awareness.

**likely files**
- `src/action_engine.py` — M3 `detect_candidates` (the function that emits `bestseller_amplify` candidates and the audience builder for it). When the existing M5 `gate_inventory` would reject `bestseller_amplify` for low cover days on the hero SKU, M3 must stamp the candidate with `preliminary_rejection_reason = "inventory_blocked"`. PM and DS picked this path: M3 stays the canonical V2 source of truth; we do not add a new merge step from M5 PlayCards into the considered list.
- `src/decide.py:_PRELIM_REASON_MAP` (lines 370-379) — add `"inventory_blocked": ReasonCode.INVENTORY_BLOCKED`. If `ReasonCode.INVENTORY_BLOCKED` does not exist in the enum, add it. Phase 5.2 already wires the rest of the considered-list pipeline; this map entry is the integration point.
- `src/decide.py:_CONSIDERED_REASON_TEXT` (around line 433+) — add a merchant-readable line for `INVENTORY_BLOCKED`: "Hero SKU at low stock; held until restock." (verbatim from PM doc; do not invent fancier copy in this pass).
- `src/decide.py:_WOULD_FIRE_IF_TEMPLATE` (per Phase 5 considered-list pipeline) — add a would-fire-if entry for `INVENTORY_BLOCKED`: "Would fire when stock on the hero SKU recovers above the cover-days threshold."
- `src/engine_run.py` `ReasonCode` enum — add `INVENTORY_BLOCKED = "inventory_blocked"` if not already present.
- `src/action_engine.py` `bestseller_amplify` audience builder — verify the candidate is produced as an M3 base candidate on the low-inventory fixture. Per the synthetic e2e review, today it is not. If the audience-builder fix is small (a few lines), land it. If it requires re-thinking bestseller-cohort detection (e.g., the cohort is small *because* inventory is low), STOP and FLAG BACK to PM/DS. The acceptable shape: M3 detects the candidate based on historical purchase patterns, *then* the inventory check fires as the rejection reason.

**acceptance criteria**
- On `healthy_beauty_low_inventory_240d`, `briefing.html`'s Considered section contains at least one card for `bestseller_amplify` with `data-reason-code="inventory_blocked"` and merchant-readable copy referencing low stock on the hero SKU.
- The reason code in `engine_run.json::considered[]` is the typed `INVENTORY_BLOCKED`.
- No numeric stock detail (cover_days, units_left) appears on the merchant card. Internal receipts may carry it.
- No vertical-specific thresholds are introduced. Existing `gate_inventory` cover-days rule is the only mechanism.
- No multi-SKU aggregation logic is added.
- The fix does not change behavior on the other 5 fixtures (no inventory blocking on healthy beauty, supplement, etc., because their fixtures do not carry low cover days).

**tests**
- `tests/test_inventory_blocked_in_considered.py` (new): construct an EngineRun where M3 produces a `bestseller_amplify` candidate with `preliminary_rejection_reason="inventory_blocked"`; run `populate_considered_from_candidates` and `decide()`; assert the Considered list contains a card with reason_code INVENTORY_BLOCKED and the expected merchant-readable text.
- `tests/test_inventory_blocked_e2e.py` (new, after harness/fixture fixes land): run the `low_inventory` fixture end-to-end; assert briefing.html DOM contains a Considered card with `data-reason-code="inventory_blocked"` (or the equivalent rendered marker) and copy referencing low stock.
- Existing M5 `gate_inventory` tests must continue to pass.
- Existing `tests/test_golden_diff.py` must continue to pass; no goldens re-baselined.

**rollback / safety notes**
- The main rathole risk is the `bestseller_amplify` audience builder. DS specifically called this out: if the fix is non-trivial, flag back. Do NOT expand scope to a measurement-design redesign of bestseller-cohort detection.
- Acceptable degraded form: if `bestseller_amplify` cannot be made to surface as a base candidate on the low-inventory fixture without measurement-design work, the inventory_blocked reason code can still surface on whichever play *is* an M3 base candidate AND has hero-SKU exposure. PM accepts a less-polished surface in this pass.
- The inventory CSV "228 days stale" runner-clock artifact (Fix 11) must land before this fix can be validated end-to-end. Sequence: ship the engine plumbing for inventory_blocked first; validate against the e2e fixture only after Fix 11.
- No change to the M5 `gate_inventory` cover-days threshold. No new vertical-specific thresholds.

---

### Fix 5 — Materiality footer line restoration

**goal**
Every non-ABSTAIN_HARD V2 briefing renders the "We only recommend primary plays that could realistically add at least $X this month for a store your size." footer line. Regression vs `agent_outputs/phase5_samples/beauty_brand_v2_briefing.html`.

**why it matters**
PM identified this as the single piece of self-explaining copy that tells a merchant *why* the page is honest about not having a recommendation. Its absence on all six synthetic briefings turns ABSTAIN_SOFT into "engine is broken" from the merchant's point of view. Phase 5.4 already rewrote the footer copy; the regression is somewhere in the wiring between `engine_run.scale.materiality_floor` and the renderer.

**likely files**
- `src/storytelling_v2.py` (data-quality footer section, around `dq-footer__scale`) — verify the conditional that gates the footer line. The Phase 5 sample shows `Monthly revenue est.: $94,405` AND `We only recommend primary plays that could realistically add at least $10,000 this month for a store your size.` Both come from `Scale`. The synthetic briefings show neither (or only the monthly revenue line). The regression is likely:
  - (a) `Scale.materiality_floor` is `None` on the synthetic runs because the M5 materiality gate did not stamp it on the EngineRun, OR
  - (b) the renderer's conditional checks `if Scale.materiality_floor is not None` and silently drops the line on null.
- `src/guardrails.py` — verify that `apply_guardrails` (or whatever sets the materiality floor) actually stamps `engine_run.scale.materiality_floor` even when the gate does not reject anything. If it's only set on rejection paths, that's the regression: stamp it unconditionally on every EngineRun.
- `src/decide.py` — verify the materiality-floor value flows through to the final EngineRun returned by `decide()`. No re-tune; just verify provenance.
- `agent_outputs/phase5_samples/beauty_brand_v2_briefing.html` — read this file to confirm the exact rendered line and class names. The footer test should grep for the load-bearing substring "We only recommend primary plays that could realistically add at least".

**acceptance criteria**
- On every non-ABSTAIN_HARD V2 briefing across the 6 synthetic fixtures (healthy_beauty, low_inventory, supplement, small_store, promo_anomaly), the footer line "We only recommend primary plays that could realistically add at least $X this month..." is present in `briefing.html`.
- On `cold_start_45d` (ABSTAIN_HARD), the footer line is allowed to be absent (ABSTAIN_HARD layout). Verify by reading the existing ABSTAIN_HARD branch in `storytelling_v2.py`; the data-quality memo layout intentionally suppresses this line.
- The exact dollar value rendered matches `Scale.materiality_floor` from the EngineRun receipts.
- No restoration of "Materiality floor: $X" jargon string; only the Phase 5.4 merchant-readable copy.

**tests**
- `tests/test_phase5_materiality_copy.py` (existing) continues to pass.
- `tests/test_materiality_footer_present.py` (new): for each of the 5 non-ABSTAIN_HARD synthetic fixtures' `briefing.html`, assert the substring "We only recommend primary plays that could realistically add at least" is present. For `cold_start_45d`, assert it is absent (or at least: assert the data-quality memo layout is rendered).
- `tests/test_golden_diff.py` (existing) — must continue to pass with no re-baseline.

**rollback / safety notes**
- This is plumbing, not a content change. PM's hypothesis is "config drift or renderer regression". Investigate before assigning to the fix; if it turns out to be a one-line conditional, ship it. If it turns out to be a deeper materiality-floor-not-stamped-on-EngineRun defect, the fix is still small (stamp it unconditionally in M5 or the legacy adapter).
- Do NOT lower the materiality floor. Do NOT change the M5 contract values.

---

### Fix 6 — Per-scenario `VERTICAL_MODE` propagation in test harness

**goal**
Every synthetic scenario's `VERTICAL_MODE` (declared in its YAML metadata) is propagated into the engine run. `engine_run.json::briefing_meta.vertical` must match the scenario's declared vertical.

**why it matters**
All six synthetic scenarios ran as `beauty` today. The supplement scenario validates nothing about supplement-vertical behavior. Until fixed, the matrix is structurally unable to validate vertical-specific behavior.

**likely files**
- The synthetic test harness/runner (per the user's note: "the synthetic test harness/runner code (per-scenario VERTICAL_MODE, reporter that reads candidate_debug.json)"). Locate this file in the matrix runner code (likely under `tests/` or a top-level synthetic-runner script). Read each scenario's YAML, set `VERTICAL_MODE` env var (or the cfg dict equivalent) per-scenario, and confirm the engine reads it.
- `src/engine_run_adapter.py:244-252` (`_briefing_meta_from_cfg`) — already reads `cfg.get("VERTICAL_MODE")`. The defect is upstream: the runner is not setting `VERTICAL_MODE` per-scenario. No engine code change required.

**acceptance criteria**
- For each of the 6 scenarios, `engine_run.json::briefing_meta.vertical` matches the YAML-declared `VERTICAL_MODE`.
- A new harness-level assertion fails the matrix run if any scenario's actual vertical does not match the declared vertical.

**tests**
- `tests/test_matrix_vertical_propagation.py` (new): for each scenario YAML, parse the declared vertical; load the scenario's `engine_run.json`; assert `briefing_meta.vertical == declared_vertical`.
- No engine-level test changes.

**rollback / safety notes**
- Pure harness change. Reverting reverts the per-scenario env-var setting.
- Does not touch engine code. Does not change merchant-facing output.

---

### Fix 7 — Reporter rewrite (DOM-only)

**goal**
Reporter parses `briefing.html` DOM and outputs Recommended / Considered / Watching counts as rendered, plus footer presence and abstain-callout presence. Reporter must NOT read `candidate_debug.json` or `engine_run.recommendations[]` for state inference. May read `engine_run.json::briefing_meta` for vertical/scenario context only.

**why it matters**
The reporter materially misrepresented merchant-facing state in 5 of 6 scenarios by reading internal artifacts. Until rewritten, no automated test summary on this matrix can be trusted. It must ship in the same pass because no founder should look at the matrix summary table while it claims the inverse of the merchant-visible state.

**likely files**
- The synthetic matrix reporter (per the user's note). Locate the existing reporter in the harness code. Rewrite its data-source layer to parse `briefing.html` with BeautifulSoup (acceptable per the brief).
- DOM selectors:
  - Recommended count: `section.recommended article.play-card` (excluding rejected). Filter by class containing `play-card--measured`, `play-card--directional`, or `play-card--targeting`.
  - Considered count: `section.considered article.play-card--rejected`.
  - Watching count: `section.watching ul.watching-list li.watching-row`.
  - Abstain-soft callout presence: `div.abstain-callout--soft` exists.
  - Abstain-hard memo presence: any element with class `abstain-hard__reason` or `abstain-hard__flag`.
  - Footer line presence: substring "We only recommend primary plays that could realistically add at least" within `footer.dq-footer`.
- The reporter may parse `engine_run.json::briefing_meta` for vertical / scenario tag only, NOT for `recommendations[]` / `considered[]` / `watching[]` counts.
- `candidate_debug.json` is internal; reporter must not read it. If the reporter currently does, delete that read path.

**acceptance criteria**
- Reporter output for each scenario matches what `briefing.html` actually shows (Recommended count, Considered count, Watching count, footer presence, abstain-callout presence, vertical from briefing_meta).
- For `small_store_240d` the reporter says "0 Recommended, 6 Considered, 0 Watching" matching the briefing.
- For `cold_start_45d` after Fix 1 lands, the reporter says ABSTAIN_HARD memo present.
- For `promo_anomaly_240d` after Fix 3 lands, the reporter says 0 Recommended, ABSTAIN_SOFT callout present.
- A reporter sanity assertion: DOM-derived counts agree with `engine_run.json::recommendations[]`/`considered[]`/`watching[]` lengths (consistency check, not a state-inference path).
- No regression on the existing reporter consumers in CI.

**tests**
- `tests/test_reporter_dom_only.py` (new): on a known synthetic briefing.html, run the reporter, assert it reports the DOM-visible counts. Verify it does not change its output when `candidate_debug.json::pilot_actions` or `engine_run.json::recommendations[]` is mutated (mock the read path).

**rollback / safety notes**
- Pure harness change. Reverting reverts the parser layer.
- BeautifulSoup is acceptable; do not pull in a heavier HTML parser.
- The reporter must use `engine_run.json::briefing_meta` for context only; if the reviewer finds it being used for state inference, fail the PR.
- This fix lands the structural test infrastructure that Fix 2's matrix-wide regression test relies on (because that test reads `engine_run.json` from each fixture's run). The matrix-wide regression test in Fix 2 can land before Fix 7 (since it reads `engine_run.json`, not the reporter), but the merchant-visible Pass/Fail summary needs Fix 7.

---

### Fix 8 — `healthy_beauty_240d` L28 returning_customer_share sign

**goal**
The fixture generator must produce a positive L28 returning_customer_share delta at the Sep 18 anchor, with sign-stable agreement across L56/L90, so the Phase 5.6 directional `first_to_second_purchase` pathway can fire.

**why it matters**
Today the fixture L28 delta is -1.7% — wrong sign. The directional gate correctly does not fire; the fixture does not exercise the canonical pathway it claims to. Without retuning, healthy_beauty's `briefing.html` is the wrong reference for what a "healthy store with directional signal" looks like.

**likely files**
- The synthetic fixture generator and the YAML metadata for `healthy_beauty_240d`. Locate per the user's note: "the synthetic fixture generator and YAML metadata".
- The retune is fixture-realism only: adjust the cohort-dynamics knob so the Sep 18 anchor's L28 delta is positive (e.g., +5% to +10%) AND the L56 and L90 deltas have the same sign.

**acceptance criteria**
- After regenerating: `kpi_snapshot_with_deltas["L28"]["returning_customer_share"]["delta"]` is positive.
- The L56 and L90 deltas are also positive (sign-stable, satisfies `consistency_across_windows >= 2`).
- After fix, running the engine on `healthy_beauty_240d` produces `decision_state == publish` with one directional `first_to_second_purchase` PlayCard in `recommendations`. (PM accepts `abstain_soft` if the re-tune still does not produce the signal — fixture deferral acceptable.)

**tests**
- Existing `tests/test_phase5_measured_pathway.py` continues to pass on the new fixture.
- New asserts in the matrix runner: on `healthy_beauty_240d`, the briefing.html Recommended section contains 1 card (or 0, with explicit comment that the re-tune did not land the signal — flag back if so).

**rollback / safety notes**
- Pure fixture change. Reverting reverts the YAML and regenerated CSV.
- Do not retune the engine to make this fixture fire. Retune the fixture to actually carry the signal it claims.

---

### Fix 9 — `supplement_replenishment_240d` realism

**goal**
Cap returning-customer share <100%; fix within-window repeat-rate definition; add explicit loyal-SKU repeater cohort; add size-token product metadata so `subscription_nudge` and `empty_bottle` have non-degenerate audiences.

**why it matters**
Today the fixture has 100% returning customers with 0.8% within-window repeat rate — internally inconsistent. `subscription_nudge` audience is degenerate (12 customers). `empty_bottle` audience is 0 because no size-token metadata. The fixture cannot validate supplement-vertical behavior even if the engine does the right thing.

**likely files**
- Synthetic fixture generator + YAML for `supplement_replenishment_240d`.
- Generator logic for: returning-share cap (must be <100%), within-window repeat-rate definition (clarify the formula), loyal-SKU repeater cohort generation (a non-trivial subset of customers buys the same SKU multiple times within 90 days), size-token product metadata (each product carries a size token like "30ct", "60ct" so `empty_bottle` can compute depletion windows).

**acceptance criteria**
- After regenerating: returning_customer_share at the anchor is <100% (e.g., 65-90%).
- `repeat_rate_within_window` is internally consistent with returning-share definition.
- `subscription_nudge` audience size on this fixture is in the hundreds, not 12.
- `empty_bottle` audience size is non-zero.
- Vertical-mode propagation (Fix 6) means the engine actually runs as `VERTICAL_MODE=supplements` on this fixture.

**tests**
- New asserts in the matrix runner: on `supplement_replenishment_240d`, the Considered list contains `subscription_nudge` and `empty_bottle` cards with non-trivial audience sizes. The vertical in `engine_run.json::briefing_meta.vertical` is "supplements".

**rollback / safety notes**
- Pure fixture change.
- Do NOT add a supplement-vertical directional pathway in this pass. That is Phase 6.
- Do NOT add a supplement causal prior.

---

### Fix 10 — `promo_anomaly_240d` anchor / spike alignment

**goal**
Move the anchor or move the spike so the May spike is within L56 of the run anchor. The anomaly gate cannot fire on a spike outside its window.

**why it matters**
Today the fixture's promo spike is in May, but the run anchor is in Sep — outside L56 (and outside L90). The anomaly gate is structurally unable to detect the spike. The fixture cannot validate anomaly-window detection.

**likely files**
- Synthetic fixture generator + YAML for `promo_anomaly_240d`. Either:
  - Move the run anchor to within ~56 days of the promo spike (e.g., set anchor to mid-July).
  - Or move the spike to within ~56 days of the Sep anchor (e.g., move the spike to early August).
- PM and DS both accept either; pick whichever requires fewer changes to other parts of the fixture.

**acceptance criteria**
- After re-tune, the spike is within L56 of the anchor.
- Running the engine on `promo_anomaly_240d` produces an anomaly data-quality flag (or, after Fix 3, ABSTAIN_SOFT with the targeting plays correctly routed to Considered, not Recommended). PM doc accepts `abstain_soft` or `abstain_hard` in the blocker pass; either is acceptable as long as the contract holds.
- The renderer copy on `briefing.html` no longer shows ABSTAIN_SOFT callout AND a non-empty Recommended section.

**tests**
- New asserts in the matrix runner: on `promo_anomaly_240d`, briefing.html Recommended count is 0; ABSTAIN_SOFT or ABSTAIN_HARD callout/memo present.

**rollback / safety notes**
- Pure fixture change.
- Anomaly-detection threshold tuning is NOT in scope. The fix is fixture realism only.

---

### Fix 11 — `low_inventory` runner-clock alignment

**goal**
The low_inventory CSV must not read as 228 days stale at run time. Align the runner clock to the anchor date so the inventory CSV is current at run time.

**why it matters**
Today the inventory data is silently dropped because the CSV is "228 days stale". This means even if Fix 4 lands the `inventory_blocked` reason code in M3, the low_inventory fixture cannot produce the merchant-visible inventory state because the inventory CSV is not being read. Fix 4's e2e validation depends on this fix landing first.

**likely files**
- Synthetic fixture generator + harness runner for `low_inventory`. Align the anchor / runner clock to the CSV's most recent inventory date (or regenerate the inventory CSV with dates relative to the anchor).
- The fixture's YAML may declare an explicit anchor date; ensure the harness runner sets the same date as `now()` for the engine run (most engines have a `--anchor-date` or equivalent override; verify via the existing runner code).

**acceptance criteria**
- After re-tune, running the engine on `low_inventory` does not show "228 days stale" in any data-quality flag.
- The inventory CSV is read; `gate_inventory` evaluates against current cover-days.
- After both Fix 4 and Fix 11 land, `briefing.html` on `low_inventory` contains a Considered card for `bestseller_amplify` with `data-reason-code="inventory_blocked"`.

**tests**
- New asserts in the matrix runner: on `low_inventory`, no "stale data" data-quality flag; inventory data is read.

**rollback / safety notes**
- Pure harness/fixture change.
- Does not touch engine staleness thresholds.

## Scenario Acceptance Matrix

The six scenarios from PM, with the acceptance contract code-refactor-engineer must validate against. Reporter (Fix 7) is the canonical source of truth for "visible" counts; `engine_run.json` is a structural sanity check.

| # | Scenario | Decision State | Visible Recommended | Considered | Watching | Guardrail Behavior | Product P/F |
|---|---|---|---|---|---|---|---|
| 1 | `healthy_beauty_240d` | `publish` (preferred, after Fix 8) or `abstain_soft` (acceptable if re-tune does not land) | 1 directional `first_to_second_purchase` (publish) OR 0 (abstain_soft) | 6 | >=1 | None firing destructively; materiality floor stamped, no anomaly flag | publish: pass; abstain_soft: soft pass (engine refused honestly, fixture defer acceptable) |
| 2 | `healthy_beauty_low_inventory_240d` | `abstain_soft` | 0 | 6 (incl. `bestseller_amplify` with `reason_code=inventory_blocked` and copy "Hero SKU at low stock; held until restock.") | >=1 | M3 stamps `inventory_blocked` on `bestseller_amplify`; no other guardrail firing destructively | pass iff inventory_blocked card visible in Considered |
| 3 | `supplement_replenishment_240d` | `abstain_soft` | 0 | 6 (with non-degenerate audiences for `subscription_nudge` and `empty_bottle` after Fix 9) | >=1 | `engine_run.json::briefing_meta.vertical == "supplements"` (Fix 6) | pass iff vertical=supplements AND non-degenerate Considered audiences |
| 4 | `small_store_240d` | `abstain_soft` | 0 | 6 (reason codes may collapse to `audience_too_small` / `no_measured_signal`; PM accepts) | 0 (acceptable for blocker pass) | Materiality floor stamped on EngineRun; footer line renders | pass — correct epistemic abstain |
| 5 | `cold_start_45d` | `abstain_hard` with `data_quality_flag=INSUFFICIENT_HISTORY` | 0 (forced empty by ABSTAIN_HARD) | 0 (forced empty by ABSTAIN_HARD) | 0 | ABSTAIN_HARD path; chart placeholder sensible | pass iff briefing.html exists AND ABSTAIN_HARD memo renders AND no Python traceback |
| 6 | `promo_anomaly_240d` | `abstain_soft` (current reality) or `abstain_hard` (after Fix 10 if anomaly gate fires) | 0 (formerly 2 — Fix 3 routes them to Considered) | 6 (incl. the formerly-Recommended targeting plays with reason `targeting_held_under_abstain` or equivalent) | 0 acceptable | Either ABSTAIN_SOFT contract enforced (Fix 3) OR anomaly DQ flag fires (after Fix 10) | pass iff Recommended count == 0 AND no targeting card shows non-null measurement on receipts |

Cross-scenario contract (must hold on every scenario):

- No `briefing.html` shows ABSTAIN_SOFT callout AND a non-empty Recommended section. Zero exceptions.
- Materiality footer line renders on every non-ABSTAIN_HARD briefing.
- No `engine_run.json::recommendations[]` carries `evidence_class == "targeting"` AND non-null `measurement`.
- `briefing_meta.vertical` matches the YAML-declared vertical.
- No forbidden statistical strings: `p =`, `q =`, `CI`, `confidence_score`, `final_score`, `Aura`, `Beacon Score`, numeric confidence percentage.
- Reporter output matches `briefing.html` DOM, not internal JSON.

## Test Strategy

Tests are organized into three tiers, all must pass for the pass to be considered done:

**Tier 1 — Unit tests (land before fixes per DS):**
- `tests/test_targeting_measurement_invariant.py::test_unit_targeting_with_measurement_raises` — construct EngineRun with `evidence_class=targeting` AND non-null Measurement, assert raise/coerce. LAND BEFORE Fix 2.
- `tests/test_abstain_soft_no_recommendations.py::test_abstain_soft_clears_recommendations` — construct EngineRun where adapter would emit 2 targeting cards under abstain_soft, run `decide()`, assert `len(recommendations) == 0` AND 2 cards in `considered`. LAND BEFORE Fix 3.
- `tests/test_inventory_blocked_in_considered.py` — unit-level wiring of `preliminary_rejection_reason="inventory_blocked"` -> ReasonCode -> rendered text. LAND WITH Fix 4.
- Lightweight chart-helper unit test for None-safety in `recent`/`prior`. LAND WITH Fix 1.

**Tier 2 — Matrix-wide structural regression tests (run against the 6 fixtures' `engine_run.json`):**
- `tests/test_targeting_measurement_invariant.py::test_matrix_no_targeting_with_measurement` — DS-required forcing function; iterates all 6 `engine_run.json` files, asserts no targeting card with non-null measurement. LAND WITH Fix 2 (after a sample matrix has run).
- `tests/test_materiality_footer_present.py` — for each non-ABSTAIN_HARD briefing.html, assert footer substring. LAND WITH Fix 5.
- `tests/test_matrix_vertical_propagation.py` — assert briefing_meta.vertical matches YAML. LAND WITH Fix 6.
- `tests/test_no_abstain_soft_with_recommendations.py` — for each briefing.html, if abstain-soft callout present, Recommended count is 0. LAND WITH Fix 3.

**Tier 3 — End-to-end matrix run + reporter:**
- Run all 6 scenarios end-to-end with the full V2 flag stack.
- Reporter (Fix 7) parses each `briefing.html` DOM and outputs the Pass/Fail table.
- Existing tests (`tests/test_phase5_*`, `tests/test_targeting_no_dollar_headline.py`, `tests/test_render_v2.py`, `tests/test_decide.py`, `tests/test_golden_diff.py`) must continue to pass.
- Default-flags-off path stays byte-identical to M0 goldens.

**Run order:**
1. Fix 1 lands (cold-start) -> all 6 scenarios at minimum produce a renderable briefing.html.
2. Fix 2 unit test lands (failing) -> Fix 2 ships -> matrix regression test lands.
3. Fix 3 unit test lands (failing) -> Fix 3 ships -> matrix abstain-soft test lands.
4. Fix 4 lands.
5. Fix 5 lands.
6. Fix 6 lands.
7. Fix 7 lands -> all matrix structural regression tests now have a clean reporter to consume.
8. Fixes 8-11 land -> matrix re-runs cleanly.
9. Final pass: all tests green; matrix-wide DS regression test green.

## Reporter / Harness Changes

**Reporter (Fix 7):**
- New file or replacement of the existing reporter module in the synthetic harness layer.
- Data sources allowed:
  - `briefing.html` parsed via BeautifulSoup. Source of truth for Recommended/Considered/Watching counts, footer presence, abstain-callout presence.
  - `engine_run.json::briefing_meta.vertical` and similar context fields. Read-only for context.
- Data sources forbidden:
  - `candidate_debug.json` (any field).
  - `engine_run.json::recommendations[]`, `considered[]`, `watching[]` for state inference. Allowed only as a sanity-check assertion (DOM count == JSON count).
  - `v2_sizing_shadow.json`, `receipts/debug.html`, `actions_log` (legacy).
- Output format:
  - Per-scenario row: scenario name, decision_state (from briefing copy), Recommended count (DOM), Considered count (DOM), Watching count (DOM), footer-present (bool), abstain-callout (none / soft / hard), vertical, pass/fail flag.
  - Aggregate: pass count out of 6.

**Harness (Fix 6):**
- Per-scenario YAML reader extended to read the `vertical` field (or whatever the YAML calls it).
- Engine invocation per-scenario sets `VERTICAL_MODE` env var (or cfg dict equivalent).
- Sanity assertion at end of each run: `engine_run.json::briefing_meta.vertical == declared_vertical` else fail the matrix run for that scenario.

**No engine code change for Fix 6 or Fix 7.**

## Fixture Changes

Four fixtures retuned. All changes are realism-only; no engine retunes.

- `healthy_beauty_240d`: L28 returning_customer_share at Sep 18 anchor must be positive with sign-stable agreement across L56/L90.
- `supplement_replenishment_240d`: cap returning-share <100%; fix within-window repeat-rate definition; loyal-SKU repeater cohort; size-token product metadata.
- `promo_anomaly_240d`: move anchor or move spike so spike is within L56.
- `low_inventory`: align runner clock to anchor date so the inventory CSV is current at run time.

Out of scope:
- No new fixture archetypes.
- No generator process-driven redesign (Phase 6).
- No tiny-base ratio guard.

## Risks

1. **`bestseller_amplify` audience-builder rathole (Fix 4).** Highest-risk sub-task. If the M3 audience builder requires re-thinking bestseller-cohort detection on the low-inventory fixture (e.g., the cohort is small *because* inventory is low, not because of historical patterns), DO NOT expand scope. Flag back to PM/DS. Acceptable degraded form: the inventory_blocked reason code can surface on whichever play is an M3 base candidate AND has hero-SKU exposure. Maximum allowed: 5-10 lines of audience-builder code; anything more is rathole.
2. **Cold-start defensive fix masks downstream defects (Fix 1).** Filtering `None` in `recent`/`prior` may unblock `cold_start_45d` only to reveal another crash deeper in the chart-rendering or briefing-assembly path. If so, flag back rather than chasing. The architectural reorder is Phase 6.
3. **Matrix-wide regression test in Fix 2 depends on Fix 7.** The DS-required matrix-wide test reads each fixture's `engine_run.json`. It needs the matrix to run cleanly first, which depends on Fix 1. Ship the unit-level test in Fix 2 before Fix 7; ship the matrix-wide test after Fix 1 has unblocked the matrix.
4. **ABSTAIN_SOFT contract change (Fix 3) might break existing tests in `test_render_v2.py` or `test_decide.py` that assert MAX_ABSTAIN_SOFT_TARGETING_CARDS == 2 or assert targeting cards under abstain_soft.** Code-refactor-engineer must update those tests as part of Fix 3's PR. Treat that as in-scope; the contract changed, the tests follow.
5. **Materiality footer regression (Fix 5) cause unknown.** Could be (a) materiality floor not stamped on EngineRun, or (b) renderer conditional silently dropping null values. Investigate before fixing. If it turns out to be a deeper materiality-floor-not-stamped defect, the fix is still small (stamp it unconditionally), but allocate time for the investigation.
6. **Fixture re-tunes (Fixes 8-11) might still not produce the expected merchant-visible signal.** PM accepts `abstain_soft` on `healthy_beauty_240d` if the L28 re-tune does not land the directional signal. If after re-tune the canonical Phase 5.6 pathway still does not fire, that is a Phase 6 measurement-design conversation, NOT a blocker conversation.
7. **Reporter rewrite (Fix 7) blocks the matrix Pass/Fail summary.** If BeautifulSoup is not already a project dependency, add it to `requirements.txt` (or equivalent). It is a small, well-known dependency; should not be controversial.

## Definition Of Done

The pass is done when:

1. All 11 fixes have shipped as their own PR-sized tickets (no monolith commit).
2. The full pytest suite (currently 507 passed, 5 skipped) passes with the new tests added: target ~520-530 passed, 5 skipped.
3. `tests/test_golden_diff.py` continues to pass with NO goldens re-baselined.
4. The matrix runner produces 6 valid `briefing.html` files (no Python tracebacks).
5. The reporter (Fix 7) outputs a Pass/Fail table where all 6 scenarios meet the contract in the Scenario Acceptance Matrix above (subject to the fixture-defer accommodation on `healthy_beauty_240d`).
6. The DS-required matrix-wide regression test (`tests/test_targeting_measurement_invariant.py::test_matrix_no_targeting_with_measurement`) passes.
7. PM's 9-point founder-test acceptance contract is met for at least 8 of 9 (item 4 depends on Fix 11 landing cleanly enough that `bestseller_amplify` is an M3 base candidate; if that turns out to require measurement-design work, PM accepts a less-polished surface).
8. Default-flags-off (legacy renderer) on existing pinned fixtures stays byte-identical to M0 goldens.
9. memory.md updated with a "Phase 5.2 — Synthetic Blocker Fixes Complete" section once the work lands. (memory update is the code-refactor-engineer's responsibility per existing convention.)

The pass is NOT done if:
- Any of the hard-out items in Non-Goals were touched.
- The architectural reorder of cold-start was attempted.
- The materiality floor was changed.
- Any new causal prior was added.
- V2 default was flipped.
- Lifecycle memory was added.
- Fake stats were restored.
- M10 cleanup was performed.

## Handoff Prompt For Code Refactor Engineer

You are the code-refactor-engineer. Implement the synthetic Phase 5 blocker fixes per the plan in `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-synthetic-blocker-fix-plan.md`.

**Read first (in order):**
1. `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-synthetic-blocker-fix-plan.md` (this plan, binding).
2. `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/product-strategy-pm-synthetic-blocker-path.md` (PM contract, binding).
3. `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ecommerce-ds-architect-synthetic-blocker-path.md` (DS ratification, binding).
4. `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/synthetic-phase5-e2e-final-review.md` (defect catalog).
5. `/Users/atul.jena/Projects/Personal/beaconai/memory.md` (existing engine memory; do not re-litigate M0-M9 / Phase 5 / Phase 5.1).
6. `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/phase5_samples/beauty_brand_v2_briefing.html` (reference for the materiality footer regression).

**Work order (one PR per fix):**
1. Fix 1 — cold-start defensive one-liner in `src/charts.py:273-274`.
2. Fix 2 — targeting-measurement invariant: land `tests/test_targeting_measurement_invariant.py` (unit-level) FIRST, watch it fail; then ship the post-hoc clear with assertion in `src/engine_run_adapter.py` terminal `_action_to_play_card` step; then add the matrix-wide regression test (after Fix 7 reporter has produced the matrix engine_run.json files cleanly).
3. Fix 3 — ABSTAIN_SOFT contract: land `tests/test_abstain_soft_no_recommendations.py` FIRST, watch it fail; then `MAX_ABSTAIN_SOFT_TARGETING_CARDS = 0` in `src/storytelling_v2.py`; clear `engine_run.recommendations = []` and route held targeting to `engine_run.considered` in `src/decide.py` ABSTAIN_SOFT branch; update existing tests that assert the old contract.
4. Fix 4 — `inventory_blocked` wiring: stamp `preliminary_rejection_reason="inventory_blocked"` in M3 `detect_candidates` in `src/action_engine.py`; add `INVENTORY_BLOCKED` to `ReasonCode` enum in `src/engine_run.py` if missing; extend `_PRELIM_REASON_MAP` and `_CONSIDERED_REASON_TEXT` and `_WOULD_FIRE_IF_TEMPLATE` in `src/decide.py`; verify/fix `bestseller_amplify` as a base candidate on the low-inventory fixture ONLY IF the fix is a few lines — flag back if non-trivial.
5. Fix 5 — materiality footer restoration: investigate why `Scale.materiality_floor` is null on synthetic runs vs the Phase 5 sample; stamp it unconditionally in M5 / legacy adapter / wherever the regression is; add `tests/test_materiality_footer_present.py` against the 5 non-ABSTAIN_HARD synthetic briefings.
6. Fix 6 — per-scenario `VERTICAL_MODE` propagation in the synthetic harness; assert `engine_run.json::briefing_meta.vertical` matches each scenario's YAML.
7. Fix 7 — reporter rewrite to parse `briefing.html` DOM via BeautifulSoup; reporter MUST NOT read `candidate_debug.json` or `engine_run.recommendations[]` for state inference.
8. Fix 8 — re-tune `healthy_beauty_240d` fixture so L28 returning_customer_share delta at Sep 18 anchor is positive with sign-stable L56/L90.
9. Fix 9 — re-tune `supplement_replenishment_240d` fixture (cap returning-share <100%, fix within-window repeat-rate, loyal-SKU repeater cohort, size-token metadata).
10. Fix 10 — re-tune `promo_anomaly_240d` (move anchor or spike so spike is within L56).
11. Fix 11 — align `low_inventory` runner clock so inventory CSV is current at run time.

**Hard constraints:**
- Do not touch anything in the Non-Goals list. Re-read it before each fix.
- Do not lower materiality floors.
- Do not flip V2 default.
- Do not add causal priors.
- Do not extend opportunity-context block.
- Do not perform M10 cleanup.
- Do not re-open M0-M9 / Phase 5 / Phase 5.1.
- Do not restore fake p-values, fake CIs, `confidence_score`, `final_score`.
- Do not add lifecycle memory or fatigue logic.
- Do not add Klaviyo or Shopify network calls.
- Land structural tests BEFORE structural fixes for Fix 2 and Fix 3 specifically (DS-mandated forcing function).
- Each fix is one PR. No monolith commit.
- After each fix: run the full test suite. Default-flags-off must stay byte-identical to M0 goldens.

**Flag-back conditions (stop and ask):**
- Fix 4: `bestseller_amplify` audience builder requires more than ~5-10 lines (measurement-design rathole).
- Fix 1: defensive `None` filter unblocks the crash but reveals a downstream chart/briefing crash.
- Fix 5: materiality footer regression cause is deeper than expected (e.g., materiality floor not flowing through several layers).
- Fix 8: re-tuned `healthy_beauty_240d` still does not produce a positive L28 delta after a reasonable cohort-dynamics adjustment.
- Any fix: legacy goldens diff. Do not re-baseline. Stop and ask.

**Done when:** Definition Of Done section above.

**Memory update:** After all 11 fixes ship and the full test suite passes, append a new section to `/Users/atul.jena/Projects/Personal/beaconai/memory.md` titled "Phase 5.2 — Synthetic Blocker Fixes Complete" that summarizes what was changed (5 engine fixes, 2 harness fixes, 4 fixture fixes), the test count delta, the matrix Pass/Fail final state, and any Phase 6 follow-ups discovered (e.g., architectural reorder of cold-start, `returning_customer_share` replacement, opportunity context for Considered cards, Watching never-empty contract, below-scale memo, generator process-driven redesign, materiality floor stamping on `engine_run.json::Scale.materiality_floor`, supplement-vertical directional pathway).
