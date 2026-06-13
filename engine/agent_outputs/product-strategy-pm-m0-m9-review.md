# Product PM M0–M9 Review

## Verdict
**Ready with caveats.**

The V2 stack is structurally faithful to the frozen PM contract, the rejection-list-as-wow-surface concept is wired in, and the code path is honest (no fake stats, no jargon leaking, no dollar headlines on targeting cards). The block to readiness is not the renderer — it is that **all three real fixtures render ABSTAIN_SOFT with empty Recommended, empty Considered, and (for 2 of 3) empty Watching**. The founder can manually verify the layout, but cannot test the merchant's "happy path" against real data.

## One-line summary
The V2 briefing is honest and structurally a memo, but on real fixtures it is currently three sections of italic empty-state placeholders — the founder will see the chrome, not the product.

## What I verified (esp. by reading actual V2 HTML)
Read in full:
- `agent_outputs/m8_parity_review/small_sm_v2_briefing.html` — ABSTAIN_SOFT, 0 recommended, 0 considered, 0 watching.
- `agent_outputs/m8_parity_review/mid_shopify_v2_briefing.html` — ABSTAIN_SOFT, 0 recommended, 0 considered, 1 watching (orders, down).
- `agent_outputs/m8_parity_review/micro_coldstart_v2_briefing.html` — ABSTAIN_SOFT, 0 recommended, 0 considered, 0 watching, materiality floor $5,000 vs monthly revenue est. $3,150 (below floor — silently "every play is futile").
- `agent_outputs/m8_parity_review/small_sm_legacy_briefing.html` (style block only) — confirmed legacy is the visually polished, themed page; V2 is austere by comparison.
- `src/storytelling_v2.py` lines 1–800 — verified all load-bearing copy strings, the ABSTAIN_SOFT callout, the Targeting disclaimer, the rejected-card "Why held / Would fire if" structure, and the empty-state strings.
- M0/M1/M7/M8/M9 milestone summaries — confirmed acceptance and the M8 caveat that "no PUBLISH-state V2 sample on a real fixture exists today."

Forbidden-string sweep: confirmed in M8 summary that `grep -cE 'p =|q =|p-value|q-value|confidence_score|final_score|p_internal|ci_internal'` over the 3 V2 HTML files returns 0. Cross-checked by spot-reading the rendered HTML — confirmed no leakage of `measured`, `directional`, `consistency_across_windows`, `evidence_class`, or numeric confidence percent in the user-facing prose.

## Merchant-facing experience: does this feel like a decision memo?

**Structurally yes; emotionally no, on the current 3 real fixtures.**

What's right:
- Structure follows the frozen contract exactly: header subtitle → State of store → Recommended → Considered → Watching → Data quality footer.
- The state-of-store paragraph reads correctly. `small_sm`: "AOV (L28): $110 (1.2% vs prior). Repeat rate (L28): 18.9% (19.7% vs prior). Orders (L28): 1157 (13.8% vs prior)."
- ABSTAIN_SOFT callout strings are correctly load-bearing: "No measured opportunities cleared." with reason "no measured or directional recommendation cleared materiality + cannibalization gating."
- No p-values, q-values, CIs, "final_score", "confidence_score", or numeric confidence percentages render anywhere.

What's wrong:
- State-of-store paragraph is mechanical. "Repeat rate (L28): 19.7% vs prior" is a metric label with a delta — not "your overall customer mix is the same but your VIPs spent more" (the example I wrote in the contract). Acceptable for Phase 1 but the prose ceiling today is "newspaper headline," not "DS analyst memo."
- On `mid_shopify`, repeat rate displays "0.0% (— vs prior)" — structural data issue (repeat-rate not computed), but the renderer surfaces it as if it were a fact. To a merchant this looks like the engine thinks they have zero repeat customers.
- The merchant-facing reason text in the abstain callout — "no measured or directional recommendation cleared materiality + cannibalization gating" — leaks engineering vocabulary ("materiality", "cannibalization gating"). The one place jargon survived.

## Strong / Emerging / Targeting vocabulary

**Vocabulary is clean.** No "measured", "directional", "weak", "evidence_class", or "consistency_across_windows" appears in merchant-facing copy. The visible labels are the contract-mandated three: "Strong", "Emerging", "Targeting." The Targeting card disclaimer ("This is a who-to-send-to recommendation, not a measured-lift forecast.") is verbatim from the contract.

CSS classes (`play-card--measured`, `data-evidence-class="targeting"`) carry the internal vocabulary as attributes, not as visible text, which is correct.

The CSS treatment differentiates evidence classes structurally — measured cards have a 6px solid green left border, directional has a solid amber border, targeting has a 6px **dashed** gray border. This satisfies failure-mode #6 in the contract ("confidence labels that don't change behavior" — they do change visual treatment).

**One nit:** Cannot verify the visual differentiation against a real PUBLISH fixture because none exists. The 24 V2 unit tests pin synthetic fixtures, but the founder will not see a measured card on real data today.

## ABSTAIN_SOFT layout assessment

**The layout is dignified but underwhelming.**

What works:
- Page is not a 404. Has chrome, the abstain callout is visible at the top of Recommended, and the State-of-store and Data quality sections still render.
- Callout language is honest: "No measured opportunities cleared." is the right load-bearing sentence.
- Section ordering preserves the memo structure.

What does not work on the 3 current real fixtures:
- `small_sm` and `micro_coldstart` produce **3 sections of italicized "empty-state" text in a row**:
  - Recommended: "No targeting plays met audience-floor and overlap rules this run."
  - Considered: "No plays were considered and held this run."
  - Watching: "No deterministic signals to watch this run."
- This is exactly the failure the PM contract Q1 warned against ("a 'no measured plays this month' briefing must look like a senior DS memo, not a 404"). The page is one notch above a 404 — it has a state-of-store paragraph and a DQ footer — but the middle of the page is **empty empty empty**.
- The abstain callout reason ("...cleared materiality + cannibalization gating") is the only specific thing on the page about why this happened. A merchant cannot tell whether the engine is broken, the store is uneventful, or both.
- For `micro_coldstart` (monthly revenue est. $3,150, materiality floor $5,000), the merchant gets no signal that the materiality floor is structurally above their monthly revenue — meaning **no play can ever fire**. Silent dead-end.

The PM contract Q4 explicitly says: "ABSTAIN_SOFT — no measured/directional plays clear the bar this month, but at least one targeting play is defensible. Output is: state-of-store paragraph, 'Watching' section, **1–2 conservative targeting plays clearly labeled** ... Not an empty briefing." Today's real-fixture ABSTAIN_SOFT has zero targeting plays surviving. Renderer is correct; gating is so tight nothing reaches it. **This is the headline product risk.**

## ABSTAIN_HARD layout assessment

**Synthetic-only, but the concept is right.** No real fixture currently triggers ABSTAIN_HARD, so I cannot evaluate it on real data. The synthetic tests pin the layout: "INTERNAL DIAGNOSTICS" banner → state-of-store → "Why no plays this run" memo with flag explanations → DQ footer. The memo concept (per Q4) is correctly implemented as a "data quality memo" not a "broken page." HARD flags map to plain English ("Window overlaps Black Friday / Cyber Monday", "Likely test orders contaminated the window"). PM contract on this is satisfied **structurally** — but founder cannot manually exercise it on real data without a synthetic seed.

## Targeting cards: credible without dollars?

**Mixed. The card structure is correct, but I cannot evaluate it on a real run because no targeting card actually surfaced in any of the 3 V2 sample HTMLs.**

What I verified by reading the renderer:
- Targeting cards have a fixed disclaimer: "This is a who-to-send-to recommendation, not a measured-lift forecast." Always present.
- When `revenue_range.suppressed=True` (the M8 documented current state for all targeting plays), the renderer emits a "Why no $ projection" context block: "Targeting plays are sized only when the engine has a calibrated lift estimate for this store. Today the recommendation is *who to send to*, not *how much it will lift*."
- When the range is unsuppressed, a single source-labeled chip ("Estimated range (vertical prior): $low - $high") replaces the headline number.

Concern: The "Why no $ projection" copy is the right idea, but it explains an absence. A merchant who has paid for the engine wants to see a positive value-prop on the card itself. The audience block (`<N> people` + definition) is good, but without an AOV chip or an "estimated reach value" qualitative phrase, the targeting card is borderline. **Dignified, but does not yet feel like a senior DS handing over a recommendation.** Acceptable for founder testing **provided the founder has a real fixture where a targeting card surfaces.** Currently they do not.

## Considered / Watching sections

**Considered (rejection list) is the contract's wow surface, and on real fixtures today it is empty.** Single biggest gap between what the PM contract promised and what the founder will see. Contract Q9 said: "The rejection list with reasons. 'We considered Bestseller Amplify; your top SKU is at 9 days of cover, recommending it would risk stockout.' This is the single most powerful signal that this is not a generic tool." Today: zero rejected plays surface on `small_sm`, `mid_shopify`, or `micro_coldstart`. M7's reason-code copy is good ("Audience is too small to send.", "Inventory is too low to push demand.", "Expected impact is below the materiality floor for this store."), and the "Why held / Would fire if:" structure on the rejected card is correctly contract-shaped. But none of it renders on the founder's available test data.

**Watching is filler today.** Only `mid_shopify` has 1 watched signal: "orders ↓ down — Threshold to act: +/- 10% to fire an orders-driven play." OK as a single line; on the other two fixtures Watching says "No deterministic signals to watch this run." which contributes to the "three empty sections in a row" feel.

## What the founder should inspect in briefing.html

1. The **state-of-store paragraph** on each fixture: are the three facts non-trivially store-specific, and do they survive the simple-prose ceiling without sounding like a metric dump?
2. The **abstain callout reason text** on the small_sm and mid_shopify pages — is "cleared materiality + cannibalization gating" comprehensible to a merchant? (My read: no.)
3. The **micro_coldstart fixture**: monthly revenue $3,150, materiality floor $5,000 — verify that this implies no play can ever fire and decide whether the engine should produce a different state for stores like this.
4. The **mid_shopify "Repeat rate: 0.0%"** — verify whether this is a real signal or a missing computation; if missing, suppress the metric instead of rendering it as fact.
5. **Spawn a synthetic ABSTAIN_HARD case** (e.g., set `data_quality_flags=[REFUND_STORM]`) and run end-to-end to see the data-quality memo on real chrome.
6. **Spawn a synthetic PUBLISH case** by passing a hand-built EngineRun through `render_engine_run` (or by relaxing one V2 flag and using the legacy adapter) so the founder sees a measured card with the green border, the "Strong" badge, and a real range chip. Without this, the founder cannot evaluate the heart of the product.
7. The **targeting card disclaimer placement**: confirm it does not feel disclaiming-the-recommendation-away.
8. The legacy briefing on `m8_legacy_smoke` for visual contrast — the founder should know how much visual polish was traded for honesty.

## True blockers before manual testing

**One soft blocker.** All three real fixtures rendering ABSTAIN_SOFT with **empty Recommended + empty Considered** means the founder cannot meaningfully test the "decision memo" experience on real data. The chrome is testable; the product is not. Two paths forward:

- **(A) accept it as a caveat** — founder tests synthetic fixtures for PUBLISH/ABSTAIN_HARD and the 3 real fixtures for ABSTAIN_SOFT only, knowing the decision logic will mature in Phase 2.
- **(B) loosen one knob** — temporarily lower `MATERIALITY_FLOOR` or relax the cannibalization gate on at least one real fixture so the founder can see one PUBLISH on real data, then revert.

**Recommend (A).** The founder is testing whether the *product surface* is correct, not whether the engine selects well today. (B) risks giving the founder a misleading "this works!" signal.

## Minimum fixes (small, pre-test)

These are PM-level, not engineering redesigns. Pick which to do; none individually blocks.

1. **Reword the ABSTAIN_SOFT callout reason to be merchant-readable.** "no measured or directional recommendation cleared materiality + cannibalization gating" → "No play in this month's analysis met our impact threshold for your store." Code lives in `src/decide.py` reason-text builder; one string change. (`src/storytelling_v2.py` lines ~528–532 hold the renderer's fallback copy too.)
2. **Suppress the "Repeat rate: 0.0%" line on mid_shopify** if the value is a "not computed" rather than "actually zero." Single guard in the state-of-store builder.
3. **Add a one-line "what this means" sentence under empty-state placeholders** so the page does not read as three empty sections. Suggested copy for the Considered empty state: "No plays were close enough to firing to surface here this month." For Watching: "No metric is trending toward a threshold yet." Two strings in `storytelling_v2.py` lines ~625 and 651.
4. **For `micro_coldstart`** (where materiality floor > monthly revenue): consider routing to ABSTAIN_HARD with `INSUFFICIENT_CLEAN_HISTORY` instead of ABSTAIN_SOFT, so the merchant gets the data-quality-memo treatment instead of empty empty empty.

If only one is done before testing, do #1 — it's the single most jargon-leaky string in the merchant view today.

## Acceptable caveats the founder should know

- **All real fixtures are ABSTAIN_SOFT today.** Known transition state, not a renderer bug. Test renderer's PUBLISH and ABSTAIN_HARD layouts via the synthetic tests in `tests/test_render_v2.py` (24 tests) rather than expecting them on real data.
- **No PUBLISH-state V2 sample on real data exists.** A measured card has not been seen on a real fixture under the V2 stack yet.
- **No ABSTAIN_HARD sample on real data exists.** Need synthetic seed.
- **debug.html ↔ briefing.html separation is clean.** debug.html is at `<out>/receipts/debug.html`, has a top-of-page banner ("INTERNAL DIAGNOSTICS — NOT FOR MERCHANT DISTRIBUTION"), and is verified by tests not to be linked from briefing.html. **Caveat: anyone who zips `<out>/` and emails it ships debug.html.** Deployment-hygiene risk, not a product blocker.
- **The CSS is austere by design.** Compared to legacy template (Inter, Space Grotesk, gradient hero, beacon-themed color tokens), V2 is plain system-font. M10 will extract inline CSS; visual polish lives there. Don't interpret "ugly" as "broken."
- **Targeting cards on real data, when they appear, will all have suppressed dollar ranges** (M6 "non-causal prior" default). The "Why no $ projection" block is the merchant-facing explanation. Contract-correct.
- **`recommended_history.json` is being written every run** (default `OUTCOME_LOG_ENABLED=true`). Calibration stub is honest (`load_realization_factors` returns `{prior_overrides: {}, evidence_thresholds: {}, materiality_overrides: {}}`). No ML claim leaks.
- **The would_fire_if templates** (M7) are not visually exercised on real fixtures because the considered list is empty; verified by reading `src/decide.py` template strings to be plain English. Founder can spot-check by seeding a synthetic considered list.

## Post-manual-test polish (do NOT block on these)

- Visual treatment parity with legacy (typography, color, charts). M10's inline-CSS extraction is the right time.
- LLM-generated state-of-store narrator (current is template-assembled).
- Real PUBLISH-state V2 fixture (waits on M5/M6 priors maturation).
- Surfacing the rejected list on real fixtures (waits on at least one play surviving the gates while another is held).
- Watching-section month-over-month memory (Phase 1B per the contract, requires `recommended_history.json` to be read, not just written).
- Targeting cards adding a qualitative "estimated reach value" or AOV chip to make the audience block carry more product weight.
- ABSTAIN_HARD merchant outreach copy (when refund-storm or test-order-anomaly fires, what does the merchant *do*?).

## Open product questions for after manual testing

1. Is ABSTAIN_SOFT-with-three-empty-sections survivable for a real merchant for a single month, or does it need a "what we did do" callout?
2. Should `micro_coldstart`-style stores (revenue below materiality floor) get a dedicated state, or is ABSTAIN_HARD the right destination?
3. The State of store paragraph is currently a mechanical metric tuple. At what point in Phase 2 does the LLM narrator become economically necessary vs. a nice-to-have?
4. How visible should the dashed-vs-solid border distinction be in the eventual themed CSS?
5. The "Considered" empty-state language — when nothing makes the cut, should the engine still try to surface 1–2 "closest to firing" candidates as targeting-class with a "this would have fired if X" frame? Contract Q10.6 left this open and it is now the load-bearing question.
6. Does the founder want the targeting-card "Why no $ projection" copy to mention what would unlock a $ projection?
