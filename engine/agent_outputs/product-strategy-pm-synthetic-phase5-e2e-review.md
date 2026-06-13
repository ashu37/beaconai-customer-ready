# Product PM Review — Synthetic Phase 5 End-to-End

## Product Verdict

**Phase 5 V2 is not ready for founder/manual testing on this synthetic matrix.** Not because the engine is broken — the V2 contract is mostly intact and statistically honest — but because four of the six scenarios produce a near-identical merchant briefing, one scenario has a contract violation (ABSTAIN_SOFT + 2 Targeting cards rendered together), one scenario silently crashed before producing any artifact, and the test reporter is mostly reading legacy/internal artifacts rather than the merchant-visible briefing.

The headline finding: **the V2 directional pathway from Phase 5.6 (`first_to_second_purchase`) does not fire on a single one of the six synthetic scenarios.** The play that the M0–M9 reconciled review identified as the canonical Phase 5 acceptance test (Beauty Brand → 1 directional + 6 considered + 2 watching) is structurally absent across the entire synthetic matrix. The synthetic generator does not produce a `returning_customer_share` movement that clears the `p < 0.05` + `consistency >= 2` gate, so every healthy scenario lands in ABSTAIN_SOFT identical to the others.

The merchant value of Phase 5 today, on this matrix, is the populated Considered list (which is real and a genuine improvement over M9). Recommended is empty everywhere except one scenario where it is misrendered. Watching is degenerate (1 row or empty). The product is honest. It is not yet useful enough to defend a $500–$1,000/month price.

This is a pre-founder-testing red flag, not a founder-testing red flag. Fixture realism, reporter fidelity, and one renderer contract bug should be addressed before a founder is asked to inspect these pages.

## Scenario-by-Scenario Merchant Experience

### 1. healthy_beauty_240d
- **What the merchant sees:** State-of-store paragraph (4 facts). A yellow ABSTAIN_SOFT callout: "No primary play this month." Below that, one italic line "No targeting plays met audience-floor and overlap rules this run." Then 6 Considered cards (winback_21_45, bestseller_amplify, discount_hygiene, subscription_nudge, routine_builder, empty_bottle), 5 with reason `no_measured_signal` and 1 with `audience_too_small` (subscription_nudge audience=3). One Watching row: `aov ↓ down`. DQ footer with "Monthly revenue est.: $148,451." **No materiality footer line.**
- **Visible Recommended count:** 0
- **Visible Considered count:** 6
- **Visible Watching count:** 1
- **Product usefulness:** Low. The merchant gets honest "we're watching" content but no actionable next step. The reason text on every Considered card is identical ("No measured signal cleared the threshold yet" + "Would fire once the audience can be measured against a valid comparison group") — six near-identical cards, repeating boilerplate. State-of-store has the info but the page is intellectually flat.
- **Pass/Fail:** **Soft fail.** This is the canonical "healthy beauty fixture" and it should produce a directional `first_to_second_purchase` per the Phase 5.6 spec. It does not. The engine is honest but inert on what should be its strongest synthetic.
- **Why:** Returning-customer share L28 was -1.7% vs prior (down, not up). The Phase 5.6 directional gate requires sign-stable upward movement with p<0.05 and consistency>=2. The synthetic generator's "improving returning customer share (25%->40%+)" promise from the YAML did not actually flow through to L28-vs-prior delta direction at the Sep anchor. Either fixture problem or the directional gate is too narrow — DS Architect to determine, but as a PM it reads as: the canonical fixture does not exercise the canonical pathway.

### 2. healthy_beauty_low_inventory_240d
- **What the merchant sees:** Same skeleton as #1. State-of-store, ABSTAIN_SOFT callout, 6 Considered cards (identical play set, identical reason codes including `bestseller_amplify` with reason `no_measured_signal`), 1 Watching (aov down), DQ footer.
- **Visible Recommended count:** 0
- **Visible Considered count:** 6
- **Visible Watching count:** 1
- **Product usefulness:** Zero on the inventory dimension. **The hero SKU's critical low-inventory state is not visible anywhere in the briefing.** A merchant comparing this output to scenario #1 cannot tell that one of their hero products is at ≤10 units. `bestseller_amplify` renders in Considered with the generic "no measured signal" reason, not "blocked: hero SKU low inventory."
- **Pass/Fail:** **Fail.** The fixture's entire reason for existing — surfacing inventory as a held/blocked play — is not produced. The synthetic-generator-summary explicitly notes "no inventory-blocked play appeared explicitly in the considered list."
- **Why:** Two-layer cause. (a) The `inventory_blocked` reason code apparently isn't being emitted by the considered-list builder for the bestseller_amplify candidate even when stock is critical. (b) The fixture's "228 days stale" inventory timestamp warning suggests the inventory file may be silently rejected by the validator. Either way, the merchant cannot see it.

### 3. supplement_replenishment_240d
- **What the merchant sees:** State-of-store with "Returning-customer share (L28): 100.0% (0.0% vs prior)" and "Repeat rate (L28): 0.8% (154.7% vs prior)." ABSTAIN_SOFT callout. 6 Considered cards. 2 Watching rows: net_sales up + returning_customer_share flat.
- **Visible Recommended count:** 0
- **Visible Considered count:** 6
- **Visible Watching count:** 2
- **Product usefulness:** Low. The merchant of a supplement brand with literally 100% returning customers and 28-45 day reorder cycles should see a replenishment, subscription, or empty-bottle play surfaced as the headline. None do. `subscription_nudge` shows audience=12 (below floor). `empty_bottle` shows audience=0 (the size-token logic doesn't fire on this fixture). The page does not communicate replenishment as a strategic opportunity.
- **Pass/Fail:** **Fail.** No replenishment-specific surface, and the engine was run with `vertical: beauty` (visible in `engine_run.json::briefing_meta`), not `supplements`. The reporter's "1 PRIMARY journey_optimization" was reading legacy `candidate_debug.json::actions[0]`, NOT the merchant briefing. briefing.html shows zero Recommended.
- **Why:** Compounded: (a) reporter conflated legacy debug with merchant view; (b) `VERTICAL_MODE` was not set per scenario; (c) no supplement-specific pathway exists in V2 yet (no replenishment-cycle play, no causal prior); (d) the supplement-specific plays that exist (`subscription_nudge`, `empty_bottle`) are gated to behaviors the synthetic doesn't model (3+ same-product orders, size-token depletion).

### 4. small_store_240d
- **What the merchant sees:** State-of-store (3 facts: AOV, Repeat rate, Orders — Returning-customer share and Net sales NOT in the rendered HTML even though they're in engine_run.json). ABSTAIN_SOFT callout. 6 Considered cards (4 with `no_measured_signal`, 2 with `audience_too_small`). **Watching is empty:** "No deterministic signals to watch this run." DQ footer: "Monthly revenue est.: $12,974." No materiality explanation.
- **Visible Recommended count:** 0
- **Visible Considered count:** 6
- **Visible Watching count:** 0
- **Product usefulness:** Roughly correct epistemics — a $13k/month store is below all reasonable materiality floors and the engine should abstain. But the page does not say that. It just shows 6 generic Considered cards and 0 Watching, leaving the merchant with no understanding of whether the engine is broken, the data is too thin, or the store is too small.
- **Pass/Fail:** **Soft pass on safety, fail on utility.** No fake projections (good). No structural acknowledgement that this store is below the engine's economic threshold (bad). The PM contract M0-M9 review explicitly flagged the analogous `micro_coldstart` case: "the page silently abstains without explaining the structural impossibility."
- **Why:** No `MATERIALITY_FLOOR_FAILED` reason code is being emitted for considered plays at this scale. No "your store is below our recommendation threshold today; here is what we would need to see" explanatory state. No materiality footer line in the rendered HTML.

### 5. cold_start_45d
- **What the merchant sees:** **Nothing.** No briefing.html, no engine_run.json, no receipts. The engine crashed in `src/charts.py:274` (TypeError: int + None) before any output was written.
- **Visible Recommended count:** N/A (crashed)
- **Visible Considered count:** N/A (crashed)
- **Visible Watching count:** N/A (crashed)
- **Product usefulness:** Zero. A merchant uploading a 45-day CSV gets a Python traceback or, worse, a failed run with no output at all. This is the worst possible failure mode for a "data scientist replacement" product.
- **Pass/Fail:** **Hard fail.** This is the case where the V2 contract's ABSTAIN_HARD with `data_quality_flags=[INSUFFICIENT_HISTORY]` was supposed to fire. Instead the engine crashes mid-pipeline.
- **Why:** Pre-existing bug in legacy charts.py. The V2 ABSTAIN_HARD path exists in code but is never reached because the legacy chart renderer is upstream of the V2 abstain logic. Any cold-start merchant will hit this.

### 6. promo_anomaly_240d
- **What the merchant sees:** State-of-store (3 facts). Yellow ABSTAIN_SOFT callout: "No primary play this month." **AND directly below the callout, 2 Targeting cards in the Recommended section** (winback_21_45 audience 4,330, bestseller_amplify audience 3,141), each with "Why no $ projection" disclaimer. 6 Considered cards. **Watching is empty.** DQ footer.
- **Visible Recommended count:** 2 (Targeting cards rendered under Recommended despite ABSTAIN_SOFT callout)
- **Visible Considered count:** 6
- **Visible Watching count:** 0
- **Product usefulness:** Confusing and self-contradicting. A merchant reading this page sees the engine say "no primary play this month" and then immediately recommend two plays. The two cards do carry the targeting disclaimer, but the page architecture has Recommended-with-callout-AND-cards, which the contract says should be one or the other.
- **Pass/Fail:** **Hard fail on contract.** This is a contract violation: ABSTAIN_SOFT with non-empty Recommended cards. The M0-M9 review explicitly listed this as a "Fail / report back" condition: "PUBLISH is reached on a real fixture with zero measured/directional plays" — the inverse holds: ABSTAIN_SOFT is rendered while still showing recommendations. Also: no anomaly warning despite a 3.1x May spike in the data, because the spike is outside the L28/L56 lookback (fixture problem).
- **Why:** The decide() state machine and the renderer have a disagreement. `decision_state == abstain_soft` AND `recommendations[]` is non-empty (2 targeting plays). The renderer shows the callout AND the cards. Either decide() should have cleared `recommendations[]` when it set abstain_soft, or the renderer should render one or the other based on state. Today's behavior surfaces both.

## Cross-Scenario Product Patterns

1. **Five of six briefings (excluding cold_start crash) are visually near-identical.** Same skeleton: state-of-store + ABSTAIN_SOFT callout + 6 Considered cards + 0-2 Watching rows + DQ footer. The Considered card text is byte-identical across scenarios for the same play_id. A merchant looking at any two of these briefings cannot tell they are about different stores from the recommendation surface alone.

2. **The Phase 5.6 directional pathway (`first_to_second_purchase`) fires on zero scenarios.** This is the entire reason Phase 5 was greenlit. The synthetic matrix does not exercise it. Whether that is a fixture-realism problem or a gate-too-narrow problem is for DS Architect — but as a PM, the answer is: **either the fixtures need to change to exercise the canonical pathway, or the gate is wrong, or both.** Phase 5 cannot ship to production with the canonical pathway untested on synthetics.

3. **The state-of-store paragraph is inconsistent across briefings.** healthy_beauty_240d and healthy_beauty_low_inventory_240d both show 4 facts. supplement shows 5 facts. small_store, promo_anomaly show 3 facts. The Phase 5 spec relaxed the cap from 5 to 7. The renderer is producing variable counts. PM-level concern: it should be deterministic per scenario class, not random.

4. **The materiality footer line ("We only recommend primary plays that could realistically add at least $X this month for a store your size.") is missing on all six synthetic briefings.** It is present in the Phase 5 sample (`agent_outputs/phase5_samples/beauty_brand_v2_briefing.html` line 54). Either it was not enabled in this run config or the renderer dropped it on ABSTAIN_SOFT. This is a regression versus the Phase 5 sample.

5. **Considered card reason text is generic boilerplate.** Five of the six cards in healthy_beauty_240d say identical "No measured signal yet for this play at this store; held as targeting until campaign outcomes calibrate the lift." This is honest but reads as engineered text. The Phase 5.2 spec promised "merchant-readable held_because string generated from the reason code." It is templated; templating is acceptable; identical templating across five rejection cards reads as broken.

6. **The Considered list does not differentiate between "audience too small" because the play is irrelevant to this brand vs. genuinely thin audience.** `routine_builder` shows audience=0 on supplement (correct: skincare-only play). `empty_bottle` shows audience=0 on three scenarios (size-token logic). The merchant sees these as "we considered this and the audience was too small" rather than "this play does not apply to your business." The Phase 5 scope notes "Adding `vertical_not_applicable` ReasonCode" was deferred. Today this is a hidden subset and reads as the engine not understanding the brand.

7. **All six scenarios were run with `vertical: beauty`.** Even supplement_replenishment_240d (engine_run.json::briefing_meta::vertical = "beauty"). This invalidates the supplement scenario as a vertical-coverage test. The test runner is not setting VERTICAL_MODE per scenario.

## Merchant-Visible vs Internal Artifact Mismatch

The reporter's summary table conflates internal candidate_debug.json with merchant-facing briefing.html in every scenario:

| Scenario | Reporter said | briefing.html actually shows |
|---|---|---|
| healthy_beauty_240d | "2 pilot, 6 considered, 1 watching" | 0 Recommended, 6 Considered, 1 Watching |
| healthy_beauty_low_inventory_240d | "1 pilot, 6 considered, 1 watching" | 0 Recommended, 6 Considered, 1 Watching |
| supplement_replenishment_240d | "1 PRIMARY, 6 considered, 2 watching" | 0 Recommended, 6 Considered, 2 Watching |
| small_store_240d | "0 actions, 6 considered, 0 watching" | 0 Recommended, 6 Considered, 0 Watching ✓ |
| promo_anomaly_240d | "2 actions, 6 considered, 0 watching" | 2 Targeting (under ABSTAIN_SOFT), 6 Considered, 0 Watching |

The "pilots" and "PRIMARY" the reporter saw are legacy `candidate_debug.json::pilot_actions` and `actions` arrays — these are internal artifacts, not the merchant view. The product contract explicitly says: **"If briefing.html shows no Recommended cards, the merchant sees no recommendation, regardless of what internal artifacts say."** By that contract:

- Five of six scenarios have **0 merchant-visible recommendations.**
- promo_anomaly is the lone exception, and it has a **contract violation** (recommendations rendered alongside an abstain callout).
- cold_start has nothing because the engine crashed.

The reporter's framing materially misrepresents the merchant-facing state of the product. Any PM, founder, or DS reading the reporter summary alone would conclude Phase 5 is producing useful output. It is not.

## Healthy Store Assessment

healthy_beauty_240d is the canonical healthy-store fixture. It produces:
- 4-fact state-of-store
- 0 Recommended cards
- 6 Considered cards (5 generic "no_measured_signal," 1 audience_too_small)
- 1 Watching row (aov down)
- $148,451 monthly revenue, well above the $10k materiality floor

For a healthy $1.8M-ARR-pace beauty brand, this is **inadequate.** A merchant paying $500/month for an "agentic AI growth team" expects at least one defensible recommendation per month. They get a memo that says "we considered six things, none of them met our bar, here's one metric to watch."

The Phase 5 sample on the real Beauty Brand fixture (`agent_outputs/phase5_samples/beauty_brand_v2_briefing.html`) showed 1 Directional + 6 Considered + 2 Watching with returning_customer_share +6.6%. That is a defensible product surface. None of the synthetic healthy briefings reach that bar. The fixture generator is not producing the signal shape that the Phase 5.6 pathway requires, so the canonical V2 win condition does not appear anywhere.

## Low-Inventory Assessment

The low_inventory scenario is supposed to be the engine's flagship example of "we held a play because of an operational reason the merchant cares about." It does not deliver. The merchant briefing is byte-substitutable with the healthy beauty briefing — 0 Recommended, 6 generic Considered, 1 Watching, no inventory mention anywhere.

This is a high-trust-cost failure. A merchant in this state runs the engine, sees the same memo as their healthy-state competitor, and learns the engine does not see operational reality. The whole point of "data scientist replacement" is that the system reads the data and surfaces the inflection point. It did not.

The fixture itself appears valid (`bestseller_amplify` audience=1,357 is real, hero SKU is at ≤10 units per the test). The gap is in the engine: the inventory gate either is not consuming the inventory CSV at this anchor date, or is consuming it but not surfacing the result through the V2 considered-list reason-code path. DS Architect to investigate which.

**Product call:** an `inventory_block` reason code on the `bestseller_amplify` Considered card with copy like "Hero SKU is at ≤10 units; held until restock" is the minimum acceptable surface. Without it, low_inventory is not a useful synthetic.

## Supplement / Replenishment Assessment

The supplement scenario is the worst-aligned of the six. Three independent failures:

1. **Vertical mismatch.** Engine ran with `vertical: beauty`. The whole point of the scenario is to validate supplement-vertical behavior. The test harness is not propagating `VERTICAL_MODE=supplements`.

2. **No supplement-vertical play exists in V2's Phase 5.6 path.** The directional pathway is `first_to_second_purchase` only, supported by `returning_customer_share`. For a 100%-returning supplement store, that signal is degenerate (delta = 0.0% by construction). The engine has no way to express "this store has a strong replenishment cycle, run a refill nudge."

3. **The supplement-flavored plays in the Considered list (`empty_bottle`, `subscription_nudge`) do not fire on the fixture.** `empty_bottle` requires size-token depletion logic; the fixture doesn't model size tokens. `subscription_nudge` requires 3+ same-product orders; the fixture has 1,200 customers ordering 1-2 products each. So even when the registry has supplement-relevant plays, the synthetic doesn't trigger them.

A merchant running a supplement business would read this briefing and conclude the engine has no understanding of what supplement businesses are. **Pass condition for supplement vertical:** at least one play surfaced that explicitly references replenishment cadence, refill timing, or auto-ship economics. None of these exist in V2 today.

## Small Store Assessment

The small_store_240d output is the most defensible of the six on epistemic grounds and the least useful on product grounds. $12,974/month is below the implicit $10k materiality floor (or close enough that no measured impact is ≥3% of revenue). The engine correctly produces 0 Recommended, 0 Watching.

But:
- The page does not say "your store is below our recommendation scale today."
- `audience_too_small` reason fires on `winback_21_45` (135 audience) and `routine_builder` (0) but the merchant has no way to read that as "the engine works but my business is too small for it" rather than "the engine is broken."
- Watching is empty when it should at least say "we are watching for revenue to cross $20k/month."
- No materiality footer means the merchant sees "Monthly revenue est.: $12,974" with no context about what that means for the engine's behavior.

This is the case where the M0-M9 PM reconciled review explicitly flagged "the page silently abstains without explaining the structural impossibility." Phase 5 did not address this. **Product call:** small_store should either route to an ABSTAIN_HARD-flavored "below scale" memo, or the ABSTAIN_SOFT page should carry an explicit "your monthly revenue is below the threshold where we recommend paid plays today" callout.

## Cold-Start Assessment

Cold-start is a product-level catastrophe in its current state.

A merchant uploading 45 days of orders is the engine's most common low-data scenario. The expected behavior is ABSTAIN_HARD with `INSUFFICIENT_CLEAN_HISTORY` and a polite memo: "we need 90+ days to recommend with confidence." Instead the engine crashes in `src/charts.py:274` before any briefing is written.

The crash is a legacy chart-renderer bug (`TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'`), pre-existing the V2 work. The V2 abstain-state machine is theoretically capable of handling this; it never gets a chance to run because the crash is upstream.

**Blocker before founder testing.** Any founder-driven test of the engine will eventually run on a thin-history dataset, and they will hit this. Two valid fixes exist: (a) fix the legacy charts crash (defensive); (b) make the V2 ABSTAIN_HARD detection run *before* the chart renderer so cold-start never reaches that code path. Either is acceptable; the current state is not.

## Promo / Anomaly Assessment

Two distinct problems compound here:

**Problem 1 (fixture):** The synthetic-fixture-generator-summary explicitly notes the May promo spike is 120+ days before the Sep 18 anchor — outside the L28/L56 anomaly-detection window. The fixture does not test what it claims to test. To exercise anomaly detection, the anchor would need to be set within ~56 days of the promo month. **This is a fixture-design problem, not an engine problem.**

**Problem 2 (engine — and this one is severe):** The briefing renders ABSTAIN_SOFT callout AND 2 Targeting cards in Recommended simultaneously. The contract says ABSTAIN_SOFT means no Recommended cards. The renderer is producing both. From the merchant's perspective the page reads:

> "No primary play this month. We evaluated this month's plays but no primary play cleared evidence requirements. Recommended: [card 1] Winback 21-45, 4,330 people. [card 2] Bestseller Amplify, 3,141 people."

The two halves contradict each other. The targeting cards do carry "Why no $ projection" disclaimers, but a merchant reading the page top-down will trust the cards over the callout, because the cards have specifics and the callout is generic.

This is a **contract bug**, independent of the fixture issue. It would also fire on any non-synthetic store where the targeting reclassification surfaces plays but the decide() state machine routes to abstain_soft. It must be fixed before founder testing. Either:
- decide() should clear `recommendations[]` when it sets abstain_soft, OR
- the V2 renderer should suppress `recommendations[]` rendering when state == abstain_soft, OR
- abstain_soft should be relabeled to something like "we did not promote any to Primary, here are the targeting plays we have" and the callout text rewritten — but this is a bigger contract change.

The receipt also shows internal `p_internal: 1.6e-72` for bestseller_amplify, which is a saturated p-value of the kind the M0-M9 cleanup tried to remove. It is internal-only (does not leak to briefing.html), but it is the kind of internal value that the DS Architect should look at directly because saturated p-values flowing into the V2 stack at all is a concerning signal.

## Opportunity Context / Economic Framing Assessment

**Largely absent across all scenarios.** The play-lifecycle-discussion-reconciled doc surfaced opportunity_context as an unresolved product question. The synthetic outputs confirm the gap: the merchant gets no "if this works, here's what it could mean for your business" framing on any card.

The Considered cards say "would fire once the audience can be measured against a valid comparison group" — that is a process disclaimer, not economic context. There is no "this audience is X% of your active base" or "addressing this lapse would represent ~Y% of your monthly revenue at typical industry conversion."

The Targeting cards on promo_anomaly say "Targeting plays are sized only when the engine has a calibrated lift estimate for this store. Today the recommendation is who to send to, not how much it will lift" — also a process disclaimer.

The DQ footer says "Monthly revenue est.: $X" — a single number, no context.

For a $500/month product, this is thin. Merchants need to be able to answer "should I run this?" The engine is honest about not having calibrated lift, but it could surface bounded, parametric economic context (audience size × AOV × store-observed historical conversion) labeled clearly as a calculator-style sketch. The DS Architect's prior position was that this is acceptable only if rigidly merchant-controlled and never engine-claimed. The current state is "no economic framing at all" — defensible but austere.

**Product call (deferred to DS Architect for credibility check):** consider a parametric `opportunity_context` block for Considered cards that shows "audience size × your store's AOV × your store's L90 conversion-on-similar-segments = $X-$Y range, calculator-style." If DS says no, the current austerity stays.

## Considered Section Assessment

The Considered section is the strongest part of Phase 5 V2. It is real, structurally correct, and improves materially over M9.

But the synthetic matrix exposes its limits:

1. **Reason boilerplate is too generic.** Five out of six cards on healthy_beauty_240d say literally identical text. The contract said reason text should derive from reason_code; today reason_code is also dominated by `no_measured_signal`. We have variety in the data (audience sizes, segment definitions) but no variety in the rejection narrative.

2. **No `inventory_blocked` reason on the low-inventory scenario.** Already covered.

3. **No `vertical_not_applicable` reason on supplement_replenishment for routine_builder.** Audience renders as 0 with `audience_too_small`, which is misleading.

4. **No `materiality_floor_failed` reason on small_store.** A $13k/month store should see explicit materiality rejections; instead it sees `audience_too_small` and `no_measured_signal`. The reason taxonomy is incomplete relative to what the matrix actually exercises.

5. **Identical 6 plays across most scenarios.** The Considered list is more "the engine ran six builders against your data, here's what each said" than "here's what we considered and rejected for your specific business." On supplement, the same 6 plays appear that appeared on beauty. That is a registry-level signal that vertical-applicability filtering is not happening, or that the registry is too narrow.

The structure is right. The content is shallow. **Product call:** the Considered section is a wow surface only if the cards meaningfully differ. Phase 5 delivered the structure; Phase 6 needs to deliver per-card, per-scenario differentiation.

## Watching Section Assessment

Watching is the weakest section across the matrix.

- healthy_beauty_240d: 1 row (aov down)
- healthy_beauty_low_inventory_240d: 1 row (aov down)
- supplement_replenishment_240d: 2 rows (net_sales up, returning_customer_share flat)
- small_store_240d: 0 rows
- promo_anomaly_240d: 0 rows
- cold_start: N/A

A 1-row Watching list with `aov ↓ down: Threshold to act: +/- 5% to fire an AOV play` is filler. The merchant cannot act on it. The threshold language is engineering-flavored ("to fire an AOV play"), not merchant-flavored ("watch for AOV to drop another 5% before we'd recommend a price-anchoring play"). The `0-row` cases (small_store, promo_anomaly) read as broken — empty section with a section title.

The Phase 5.3 spec said "soften the M7 builder: HELD observations with `change_magnitude == 0` on a load-bearing metric (orders, net_sales) should produce a 'stable but watching' entry, not be filtered out." That logic exists in the Phase 5 sample (which shows `orders → flat` as a watching row). It is not firing on small_store_240d or promo_anomaly_240d, which are the two scenarios that most need it.

**Product call:** Watching needs to never be empty if any state-of-store fact moved more than threshold or stayed flat on a load-bearing metric. The current "No deterministic signals to watch this run." italic empty-state is a 404-adjacent experience and should not exist.

## Reporter / Interpreter Assessment

The reporter is materially unreliable as a Phase 5 product evaluator.

It correctly counts considered. It approximately counts watching. It systematically miscounts Recommended by reading legacy `candidate_debug.json::pilot_actions` and `candidate_debug.json::actions` as if they were merchant-visible recommendations. Specific examples:

- healthy_beauty_240d: reporter said "2 pilot." The actions_log is empty. The candidate_debug shows 2 entries in `pilot_actions[]` (routine_builder, retention_mastery). briefing.html shows 0 Recommended. The reporter is reading internal pipeline state.
- supplement: reporter said "1 PRIMARY journey_optimization." The engine_run.json shows `recommendations: []`. The candidate_debug shows journey_optimization in `actions[0]`. briefing.html shows 0 Recommended. The reporter is reading legacy and labeling it PRIMARY (a tier the V2 contract says does not exist for the merchant).
- promo_anomaly: reporter said "2 actions winback + bestseller." This one is approximately right — briefing.html does have 2 Targeting cards — but the reporter does not flag the contract violation (ABSTAIN_SOFT + Recommended cards).

The synthetic-fixture-generator-summary.md has its own Engine Result Summary table which uses different vocabulary ("PRIMARY / V2 Recs," "DIRECTIONAL," "CONSIDERED," "WATCHING") and produces different numbers from the reporter. This second summary is closer to right (it says 0 V2 recommendations on healthy_beauty_240d and supplement_replenishment_240d), but it also conflates legacy `pilots` with V2 "pilot."

**Blocker:** the reporter must be rewritten to read briefing.html (as DOM or bs4 parse) and count rendered cards, not internal artifacts. Until then, no automated test summary on this matrix can be trusted.

## Product Blockers Before Founder Testing

In priority order. Each is discrete.

1. **Cold-start crash in charts.py.** Any founder running the engine on thin history hits this. Either fix the chart renderer's None handling or move the V2 ABSTAIN_HARD detection upstream of charts. Non-negotiable before founder testing.

2. **Promo_anomaly contract violation: ABSTAIN_SOFT briefing renders with 2 Targeting cards in Recommended.** Decide() and renderer disagree on what to do when state==abstain_soft and recommendations[] is non-empty. This will fire on real merchant data, not just this fixture. Non-negotiable.

3. **Reporter/interpreter rewrite.** The reporter conflates legacy candidate_debug.json with merchant briefing.html in 4 of 6 scenarios. A founder running this matrix will get a misleading summary. Either fix the reporter to read briefing.html directly, or remove the misleading legacy-counts columns from the summary table.

4. **Materiality footer line missing on all six synthetic briefings.** Present in `agent_outputs/phase5_samples/beauty_brand_v2_briefing.html` line 54; absent in all six synthetic outputs. Either a config drift or a renderer regression. Easy to verify; high merchant trust impact.

5. **`VERTICAL_MODE` not set per scenario.** All six ran as beauty. supplement_replenishment is invalidated as a vertical-coverage test. Test harness change.

6. **Considered list reason text is identical across 5 of 6 cards on healthy_beauty.** "No measured signal cleared the threshold yet" + "Would fire once the audience can be measured against a valid comparison group." The Phase 5.2 spec promised reason-code-driven differentiation. Today the differentiation is in the reason code only; the rendered text is templated identically. Tighten the template or expand the reason-code enum.

7. **No inventory-blocked reason on the low-inventory scenario.** Either the inventory gate is not running on this fixture, or it is running but not surfacing through the considered-list path. The flagship inventory test fixture must produce a visible inventory signal.

## Fixture Design Issues

These are fixture-realism problems, not engine problems. They blunt the test matrix's power but do not block founder testing of the engine itself.

1. **healthy_beauty_240d returning_customer_share is -1.7% at the L28 anchor.** The YAML says "improving returning customer share (25%->40%+)." The L28-vs-prior delta does not show that improvement direction. This single fact prevents the Phase 5.6 directional pathway from firing on the canonical healthy fixture. Fix: re-tune the generator to ensure L28 returning_customer_share is increasing at the Sep anchor, with sign-stable agreement across L56/L90.

2. **promo_anomaly_240d May spike is outside the L28/L56 lookback from the Sep anchor.** Already documented in the synthetic-fixture-generator-summary. Fix: move the anchor to within 56 days of the promo month, OR move the promo to within 56 days of Sep.

3. **supplement_replenishment_240d has 100% returning customers and 0.8% within-window repeat rate.** This is internally inconsistent. A 100%-returning supplement business with 28-45-day reorder intervals should show 30-50% within-window repeat at L28. The within-window repeat rate definition appears to be doing something different from "fraction of customers in this window who have purchased before." Clarify the metric and re-tune the generator.

4. **low_inventory fixture's inventory CSV reports "228 days stale."** The synthetic-fixture-generator-summary acknowledges this is a date-relative artifact. Fix: align the test runner's clock to the anchor date so the inventory file is read as fresh.

5. **No `subscription_nudge` audience model.** Audience=3 across multiple scenarios. The play definition wants 3+ same-product orders in 90 days; the synthetic generators don't model that. To exercise subscription-cycle plays, the generator needs an explicit "loyal SKU repeater" cohort.

6. **No size-token product metadata.** Three scenarios show `empty_bottle` audience=0. The play wants depletion-from-size logic; the generator doesn't model size tokens.

7. **Reorder intervals on supplement are exact-deterministic per customer (28-45d, fixed per customer).** Real supplement businesses have customer-level dispersion. A 100%-returning rate is generator-driven, not realistic.

## Cross-cuts the test matrix does not exercise

These are scenarios the matrix should add before declaring the engine validated:

- A brand at the materiality boundary ($30-100k monthly), which is where the floor scaling actually bites.
- A brand with negative MoM revenue (recovery-mode merchant).
- A brand with discount-dependency growth (where `discount_hygiene` should fire).
- A brand with a working subscription cohort (where `subscription_nudge` should fire).
- A "second run" scenario (May data appended onto April's data, to test month-over-month repeat-recommendation behavior — the play-lifecycle issue).
- A real BFCM-window test (today all anchors are Sep 18, so seasonal multipliers are constant across the matrix).

## Issues That Can Be Deferred

- **Reason-code taxonomy expansion** (`vertical_not_applicable`, `materiality_floor_failed`, `inventory_blocked` as visible reasons). Phase 5 deferred this. Phase 6 should add. Today's hidden subset is acceptable for founder testing; not for production.
- **Opportunity context block.** Currently absent. Defer until DS Architect rules on whether the parametric calculator-style sketch is credible.
- **Watching-section rewording.** "Threshold to act: +/- 5% to fire an AOV play" reads as engineering jargon. M10 cosmetic.
- **State-of-store fact-count consistency.** Variable across scenarios (3-5 facts). Not blocking, should be deterministic.
- **`recommended_history.json` write verification on these synthetics.** Not verified mechanically; worth a manual check, but does not block.
- **Saturated p-values in promo_anomaly's targeting cards' internal `p_internal`.** Internal-only; does not leak to merchant. DS Architect to assess whether saturation in the V2 internal stats is a deeper concern.

## Phase 5 Synthetic Testing Pass/Fail Standard

**Pass standard.** All of the following must hold:

1. Every non-cold-start scenario produces a renderable briefing.html with no exceptions.
2. The cold-start scenario produces an ABSTAIN_HARD briefing.html, not a crash.
3. No briefing.html shows ABSTAIN_SOFT callout AND non-empty Recommended cards.
4. At least one scenario surfaces a non-zero Recommended (Directional or Targeting card) with merchant-readable copy.
5. The low-inventory scenario surfaces an inventory-related reason somewhere visible.
6. The materiality footer line is present on all briefings.
7. The reporter summary table reflects what briefing.html renders, not what candidate_debug.json contains.
8. All scenarios run with their declared `VERTICAL_MODE`.
9. No forbidden statistical strings (`p =`, `q =`, `CI`, `confidence_score`, `final_score`, `Aura`, `Beacon Score`) leak into any briefing.html.

**Today's pass count: 1 of 9.** Item 9 is the only one I am confident holds across the matrix without explicit verification. Items 1-8 fail somewhere across the matrix.

**Fail standard:**
- Any briefing.html crashes the renderer (item 1 — fails on cold_start).
- Any briefing.html violates a contract invariant (item 3 — fails on promo_anomaly).
- The reporter materially misrepresents merchant-visible state (item 7 — fails on 4 of 6 scenarios).

By this standard, Phase 5 synthetic testing is currently in a fail state and should not progress to founder/manual testing.

## Product Recommendation To DS Architect

The DS Architect should focus on the following questions where product-level concerns intersect with statistical/architectural ones. Each is bounded.

1. **Why does Phase 5.6's `first_to_second_purchase` directional pathway not fire on the canonical healthy_beauty_240d fixture?** The synthetic shows returning_customer_share L28 = -1.7% (negative). Is this a fixture-realism problem, a directional-gate problem, or both? Specifically: if the gate requires sign-stable upward movement and the fixture produces L28-down/L56-up/L90-up, the gate correctly rejects — but then the fixture is wrong. If the gate is rejecting upward movement with consistency<3, the gate is too narrow. Resolve which.

2. **The promo_anomaly_240d briefing renders ABSTAIN_SOFT callout with 2 non-empty Targeting cards in Recommended.** Is this a state-machine bug (decide() should clear recommendations on abstain_soft) or a renderer bug (V2 renderer should not render recommendations under abstain_soft) or a contract gap (the contract should permit Targeting cards under abstain_soft and the callout copy needs to change)? Pick one and fix.

3. **Internal `p_internal` values in promo_anomaly_240d's targeting recommendations are saturated (1.6e-72).** These are not rendered to merchant, but their presence in V2 receipts at all is the same kind of saturated stat the M0-M9 work tried to remove from legacy. Is this a residual leak from the legacy adapter's `_coerce_evidence` or is it a V2-side combiner issue?

4. **The inventory gate is not surfacing through the V2 considered-list path on healthy_beauty_low_inventory_240d.** Where does it die? Is the inventory CSV being silently rejected as stale? Is the gate firing internally but not getting a reason_code assigned in `populate_considered_from_candidates`?

5. **The Considered list shows identical reason text across 5 of 6 cards on healthy_beauty_240d.** The Phase 5.2 spec promised differentiation by reason code. Today reason code is dominated by `no_measured_signal`. Is this an enum-too-narrow issue, or are upstream gates (`audience_floor`, `effect_floor`, `materiality_floor`) not being mapped to distinct reason codes?

6. **Does the Phase 5 V2 stack support `vertical: supplements`?** Currently all synthetic runs flatten to beauty. If the registry, priors, and watching thresholds do not have supplement-specific entries, then the supplement scenario is structurally inert regardless of fixture quality.

7. **The cold-start fixture crashes in `src/charts.py` before V2 ABSTAIN_HARD can fire.** Is the fix to make ABSTAIN_HARD detection precede chart rendering, or to fix the chart's None handling, or both? Product-level preference: ABSTAIN_HARD should run first so the failure mode is a polite memo, not a crash.

8. **At what scale does the M5 materiality floor mechanism actually engage?** The small_store_240d ($13k/month) shows `materiality_floor: null` in `engine_run.json::scale`. Should it be $5k or $10k for a $13k store? If the floor is null, no plays can be rejected on materiality grounds, which is why small_store gets generic `audience_too_small` / `no_measured_signal` rejections rather than honest "below scale" rejections.

The first three are blockers before founder testing. The remaining are high-priority Phase 6 inputs.
