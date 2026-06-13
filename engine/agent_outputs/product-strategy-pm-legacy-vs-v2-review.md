# Product PM Review — Legacy vs V2 Beauty Brand Output

## Product Verdict

**Legacy is more useful to the merchant today; V2 is more honest and structurally correct.** Neither is shippable as-is.

The legacy briefing for beauty_brand reads as a confident, glossy sprint plan. It tells the merchant exactly what to do, who to send to, what offer to use, what the success metric is, and what dollar impact to expect — with a $14,463 hero number, a "Healthy 77" Beacon score, and three ready-to-launch action cards. The merchant can publish from it. The trust problem is that almost none of those numbers can be defended: `journey_optimization` is a template/heuristic play that the V2 work has already determined should be `targeting` (no measured lift), yet legacy renders it as "Strong signal — High confidence — $4,283–$9,043 range." The product's USP — being a data-scientist replacement — is forfeited the moment a sophisticated merchant pokes at one of those CIs.

V2 for the same data renders a 50-line page with a state-of-store paragraph and three empty section placeholders ("No targeting plays met audience-floor and overlap rules this run." / "No plays were considered and held this run." / "No deterministic signals to watch this run."). It is honest. It is also unusable. A merchant landing on this would assume the engine is broken or that they bought a subscription to nothing.

The product question is not "which output is right" — it is **"which output is closer to the eventual merchant experience and which is further from it."** Legacy is closer to the *form* (recommendation, audience, why-now, execution plan, success metric) but lies. V2 is closer to the *epistemic posture* (we only speak when we have something to say) but has lost every product surface that makes the form valuable. The smallest path to the right product is to take legacy's form and replace its claims with V2's discipline — not to ship either of these as the merchant artifact.

## What The Legacy Output Does Well

1. **It tells the merchant what to do.** Three action cards, each with: title, signal badge ("Strong signal" / "Moderate signal"), one-liner why-now ("Customers are dropping off before their second purchase. Target 279 customers to recover $6,119 in the next 28 days."), target audience size, 28-day impact, audience CSV path, channel, sequence cadence, escalating offer ladder with discount cap, 7 numbered execution steps, hold-out percent, and an explicit success metric ("Segment conversion rate: 2.5–4% within 14 days (15% holdout)").
2. **It is publish-ready.** The execution plan section reads like an ops doc: "Export Journey Optimization (279 customers) and upload to Email ESP as 'Journey_Recovery_Sep25'." This maps cleanly onto the future Klaviyo-publishing agent: it already specifies the artifact, the channel, the cadence, the offer, and the holdout.
3. **State-of-store framing is rich.** Beacon Score (77, "Healthy"), 5 sub-factors with tiny narratives, a back-to-routine seasonality banner, and a $14,463 hero opportunity number on the very first card. A merchant gets a "where am I, what should I do, and what's it worth" snapshot in 5 seconds.
4. **Visual polish.** Themed branding, gradient hero, score donut visual, charts, sprint-plan table at the bottom — it is the kind of artifact a merchant would forward to a CMO.
5. **It reads like the agentic product the vision describes.** The chrome is what the eventual product is supposed to feel like. The bones are right.

## What The Legacy Output Does Poorly

1. **It misrepresents heuristic plays as measured.** `journey_optimization` shows `effect_abs: 0.9165` and `ci_low: 0.8944, ci_high: 0.9386` in `candidate_debug.json` — those numbers are the kind of suspiciously-tight, "fabricated p/CI" pattern memory.md flagged for retirement. The legacy brief renders this as "Strong signal" with a $4,283–$9,043 range chip. There is no measurement design that supports this for journey_optimization at this store; it is template stats dressed as evidence.
2. **Hero opportunity is a sum of wishful single-play forecasts.** "Monthly Growth Opportunity $14,463" is the sum of $6,119 + $3,927 + $4,417, with no incrementality discount, no audience-overlap correction, no cannibalization guardrail, and no scale cap. This number violates the V2 invariant `sum(p50) <= 0.25 * monthly_revenue` (here 14,463 / 94,405 = 15%, lucky to be inside that cap, but only by accident).
3. **Confidence labels are decoupled from action.** "Strong signal", "Moderate signal", "High confidence" appear as evidence chips. There is no merchant-readable definition for what makes a "Strong signal" vs "Moderate" — and the underlying `confidence_score` of 1.0 for `journey_optimization` looks like a saturated computation, not a calibrated certainty.
4. **No rejection list, no abstain mode, no "considered but held."** The merchant only sees the three winners. They never learn the engine *thought about* `subscription_nudge`, `bestseller_amplify`, `category_expansion`, etc. and decided against them. The product loses the audit-trail surface entirely.
5. **Repeat metrics drift.** `run_summary.json` legacy shows `repeat_rate_within_window: 0.3229` while V2 shows `0.3399` for the same anchor. Different metric versions render different repeat rates to the merchant under "Customer Health 98." Whichever is right, both can't be — and neither is annotated.
6. **The "Plays Recommended: 1 Primary • 2 Quick Wins" framing presupposes that the answer is always "1+2."** There is no path through the legacy output to "0 plays this month, here's why, here's what we're watching."
7. **`returning_customer_share` is 91% with `p ≈ 9.5e-05` significance** — a real, measured signal — but the action surfaced is `journey_optimization` ($6,119 from a *template* effect), not anything that uses that real signal directly. The high-significance, high-volume finding is decorative; the load-bearing recommendation is template-driven.

## What The V2 Output Does Well

1. **Honest about evidence.** The page contains zero `p =`, `q =`, `CI`, `confidence_score`, `final_score`, or numeric confidence percent. The forbidden-string contract holds. There is no $14,463 hero making a promise the engine can't defend.
2. **Correct decision state.** `engine_run.json` shows `abstain.state: abstain_soft` with reason "no measured or directional recommendation cleared materiality + cannibalization gating." That is the right computational answer for this dataset under the V2 stack — the legacy plays the engine emitted reclassified as targeting, the priors are non-causal, sizing suppressed, materiality stripped them. The state machine produced a defensible outcome.
3. **Scale-aware materiality is computed.** `scale.materiality_floor: $10,000` against `monthly_revenue: $94,405` is the contract-mandated `max($10k, 3%)` for the $1–5M ARR tier. This is the kind of thing the eventual data-scientist-replacement engine should be doing automatically.
4. **State-of-store paragraph is structurally correct.** "AOV (L28): $69 (1.7% vs prior). Repeat rate (L28): 34.0% (-3.7% vs prior). Orders (L28): 1374 (0.0% vs prior)." Three typed Observations, each with a metric, a value, and a delta — no jargon, no statistical signature.
5. **No false promises in the receipts.** `actions_log.json` is `[]`. `v2_sizing_shadow.json.records` is `[]`. The downstream consumers will not be fed numbers the engine doesn't believe.
6. **The chrome of the contract is in place.** Recommended / Considered / Watching / Data Quality footer sections all exist with the right semantics. When the engine *does* have something to say, the renderer will say it.

## What The V2 Output Does Poorly

1. **The whole page is empty after one paragraph.** Merchant-visible content is: subtitle ("No measured opportunities cleared; review the considered list and watching signals."), one state-of-store paragraph (3 metrics), one ABSTAIN_SOFT callout, three "No X" italic empty-state lines, and a 4-row data-quality footer. That is the entire artifact for a $1.1M-ARR healthy beauty brand.
2. **The "review the considered list and watching signals" subtitle is a lie.** The considered list is empty. The watching list is empty. The subtitle is telling the merchant to look at things that aren't there.
3. **The abstain callout reason leaks engineering vocabulary.** "no measured or directional recommendation cleared materiality + cannibalization gating" is the load-bearing sentence on the page and contains three pieces of engineering jargon (`measured`, `directional`, `materiality + cannibalization gating`). This is the single most unforgivable string in the merchant view because it is the *one sentence the merchant will read carefully.*
4. **No path forward from the empty page.** A merchant facing this has no signal about what to do — try a different month, wait for next week, change something operational, contact support, treat this as broken? The page is silent.
5. **Considered list is empty even though the legacy run produced 3 actions.** This is the contract's wow surface — "we thought about journey_optimization, here's why we held it" — and on a brand where legacy surfaces 3 plays, V2 surfaces 0 considered. The audit trail that should exist *because the engine considered things* is absent.
6. **Watching list is empty even though state-of-store has a HELD observation.** "Orders (L28): 1374 (0.0% vs prior)" is `classification: held` in `engine_run.json` — but `change_magnitude: 0.0` causes the M7 watching builder to filter it out. The "watching" surface needs different threshold logic on flat-but-load-bearing metrics.
7. **Visual austerity.** The CSS is one inline `<style>` block with grayscale boxes and one accent color. After looking at the legacy themed brief, V2 reads as a static debug page. M10 cosmetic, but a founder sharing this with a design partner would be embarrassed.
8. **No charts, no segments, no execution plan, no offer ladder, no holdout guidance, no success metric** — the things that make legacy publish-ready do not exist in V2 at all. Even if V2 had a play to recommend, it would only render audience size + AOV + a disclaimer; the merchant still couldn't ship from it.
9. **`monthly_revenue` is $94K and `materiality_floor` is $10K (10.6% of revenue) — but no recommendation can ever clear that floor on this brand under V2's current sizing.** The V2 sizing module will keep suppressing every targeting play (priors are all expert/observational, no causal). So even if the considered list filled in, the materiality gate would empty it again. The page is structurally guaranteed to be empty until causal priors land.

## Merchant Usability Comparison

**Legacy: 8/10. V2: 2/10.**

Legacy gives a non-technical operator (DTC founder, growth marketer, agency PM) a complete thing to do this month. They can read the brief, hand it to a freelancer, and have a flow live by Friday. The artifact answers "what should I do next?" in one click.

V2 gives the same operator nothing actionable. There is no recommendation, no audience, no offer, no execution plan, no chart, no segment file. The state-of-store paragraph is the only content; the merchant cannot proceed from it.

The V2 page would be defensible if it routed to a hard data-quality memo ("we don't have enough clean history") or to a structurally explicit "this brand is healthy and there's nothing to do this month — keep doing what you're doing." Today it does neither — it abstains soft with three empty placeholders and an engineering-jargon reason. That is the worst of both worlds.

## Merchant Trust Comparison

**Legacy: 3/10. V2: 7/10.**

Legacy is highly trustable on first read and rapidly self-destructive on inspection. A junior merchant trusts it. A sophisticated merchant who clicks through to `candidate_debug.json` finds `journey_optimization` with a CI of `[0.8944, 0.9386]` and a `confidence_score: 1.0` (saturated) — and immediately distrusts not just the journey_optimization card but the entire page. The trust collapse is binary, and it happens fast for any merchant with a data background. For the eventual product positioning ("data-scientist replacement"), the legacy artifact actively burns the franchise.

V2 makes no claim it cannot defend. The page is austere because it refuses to fake anything. A sophisticated merchant inspecting V2 finds: typed observations, a defensible decision state, scale-aware materiality, no fabricated CIs, no statistical strings in the rendered HTML, no PII in `recommended_history.json`. The trust is harder to win (page is less impressive) but does not collapse on inspection.

For the *future product*, V2's trust posture is right and legacy's is wrong. For *today's product surface*, V2's trust comes at the cost of having any product at all.

## Actionability Comparison

**Legacy: 9/10. V2: 0/10.**

Legacy is end-to-end actionable. The merchant has, on one page:
- 3 audience CSVs (paths included).
- 3 channel + sequence + offer specifications.
- 3 step-by-step execution lists.
- 3 success metrics with holdout percents.
- A sprint table with owner assignments ("Conversion/UX", "CRM/Growth", "CRM/Customer Success").

V2 is not actionable at all. The only action a merchant can take is "scroll back up and re-read the empty placeholders." There is no audience surface, no offer surface, no execution surface, no holdout surface, no success metric surface.

This gap is the most important single product fact in this comparison. **The future Klaviyo-publishing and monitoring agents have something to consume from legacy and nothing to consume from V2.**

## Product Risks

1. **Founder sees V2 on real data and concludes the engine doesn't work.** The `m0-m9-final-review-reconciled.md` flagged this exact risk. The beauty_brand artifact materializes it: a healthy $1.1M-ARR brand with an A-grade data quality score (`engine_validation_report` shows `validation_score: 100`, `data_quality_grade: A`) and 9,620 clean orders gets a 50-line page with three empty sections. Without context, this reads as broken.
2. **V2 hardens an empty-output failure mode as the steady state.** Because every prior in `config/priors.yaml` is `expert`/`observational` and `_coerce_evidence` defaults to TARGETING, the V2 stack will *always* suppress every play on this dataset until measured detection is wired in or causal priors are authored. The page is not transitional; it is the architectural endpoint of the current pipeline.
3. **Legacy's "$14,463 monthly opportunity" lock-in risk.** If founders or partners see legacy first, they will anchor on the dollar number and resist a V2 that abandons it. The expectation set by legacy is the hardest thing to walk back; every V2 page will be silently graded against "but legacy gave me $14k."
4. **Considered list is the contract's wow surface and it's empty everywhere.** The product story for V2 ("here's what we held and why") collapses if the engine never populates it on real data. Today, on beauty_brand, it doesn't.
5. **The rejection vocabulary in V2 leaked through the abstain reason text.** "materiality + cannibalization gating" is the most jargon-dense five-word phrase the merchant will see. It signals to a data-savvy merchant that the engine is talking to itself, not to them.
6. **Brand-vertical priors are not yet causal, so beauty-specific dollar projections cannot exist under V2.** The product vision (vertical-aware data-scientist) requires causal priors for the verticals BeaconAI sells into; until those exist, every beauty merchant gets the same empty page that beauty_brand got.
7. **V2 has no graceful-degradation copy.** When the engine has nothing, it should say "this is a healthy month — keep doing what you're doing, and here's what we'll watch" — not three italic "no X" placeholders.

## Product Recommendation

**Do not ship either output as the merchant artifact.** Build a third surface: V2's discipline, legacy's form.

Concrete smallest-meaningful change list, in priority order:

1. **Replace the ABSTAIN_SOFT callout reason with merchant copy.** "no measured or directional recommendation cleared materiality + cannibalization gating" → "Your store is in good shape this month. We didn't find a play with strong enough evidence to recommend. Here's what we're watching." (Two strings, one PR.)

2. **When ABSTAIN_SOFT fires on a healthy brand, the page must have content other than three empty placeholders.** Surface the considered list always — even when the engine had to synthesize "this play didn't fire because no causal prior exists for your vertical yet." The merchant should never see three "No X" lines in a row. Either every section has content, or the abstain layout collapses to a single dignified memo.

3. **Suppress the legacy brief from being the default merchant artifact for any play classified as targeting.** This is largely the M4b/M6 design intent already; the bug is that legacy is still the default renderer when `ENGINE_V2_OUTPUT=false`. Flip the renderer default to V2 and accept the empty pages as the conservative outcome — *but only after fix #1 and #2 above.*

4. **Author at least one causal prior for one beauty play (winback_21_45 is the obvious candidate)** so V2 has any chance of producing a non-empty Recommended section on this dataset. Without this, V2 is locked into ABSTAIN_SOFT forever on beauty merchants and the product surface is structurally empty.

5. **Port legacy's execution plan into V2 measured/directional cards.** When V2 *does* produce a recommendation, the card today shows audience size + AOV + a 1-line disclaimer. That is not enough to publish from. Bring across legacy's channel/sequence/offer/holdout/success-metric structure (as merchant fields, not as fabricated stats) so the future Klaviyo agent has something to consume.

6. **Either kill the "Watching" empty-state or change the M7 builder threshold.** A healthy brand whose orders are flat (`change_magnitude: 0.0`) should not produce zero watching signals — flat-but-large is the most informative state. Today the builder filters it out.

7. **Hide the legacy Beacon Score / Aura Score from V2.** It is computed (`engine_run.json` carries it implicitly via `scale`), but it is also the gateway drug to "score = product." V2 is intentionally not a dashboard. Don't bring this back.

8. **Suppress monthly_revenue / materiality_floor in the merchant footer if the merchant won't understand them.** Today V2's footer prints "Materiality floor: $10,000" — a merchant has no model for what this is. Either explain it ("We only recommend plays that could realistically add at least $10K this month for a store your size") or don't show it.

The legacy output's product surface is salvageable and largely correct in form. The V2 output's epistemic posture is correct. The product is the merge.

## Questions / Notes For DS Architect

1. **`run_summary.json` reports different `repeat_rate_within_window` values for legacy (0.3229) vs V2 (0.3399) on the same dataset.** Both runs share an anchor of `2025-09-18 23:00:25.488000+00:00`. Which is correct, and is the difference attributable to `ENABLE_REPEAT_RATE_BIAS_CORRECTION=false` flipping in M4a? Merchant-facing copy on the V2 state-of-store paragraph reports 34.0% — is that the value we want them to see?

2. **`returning_customer_share` is 91% at L28 with `p = 9.5e-05` and a clear directional move (+6.6% vs prior).** That is a real, defensible signal. Why does no V2 play surface from it? Either the legacy detector doesn't emit a play that uses this metric, or the M3 detect → M7 decide path doesn't wire it through. The contract explicitly identifies "First-to-Second Purchase" as MVP-safe and preferred replacement for journey_optimization — is that play registered, detected, and able to size on this dataset?

3. **The legacy `journey_optimization` candidate has `effect_abs: 0.9165` with CI `[0.8944, 0.9386]` and `confidence_score: 1.0`.** The CI is so tight relative to the effect that it suggests the standard error has been hardcoded or zeroed. Is that template stats, and if so, should we remove the candidate from the legacy emitter outright rather than carrying it through M4b reclassification?

4. **`v2_sizing_shadow.json.records` is `[]` because there were no V2 recommendations to size.** Should we still emit shadow records for the *suppressed* legacy candidates so the founder can see what V2 *would* have computed had a measured pathway existed? Today the shadow file is uninformative on this dataset.

5. **Materiality floor of $10K vs monthly revenue of $94K = 10.6%.** Is the 3% floor on the $1–5M tier the right calibration for beauty specifically? If the floor were $5K (5%), would `discount_hygiene` (which has measured effect at L56 and L90 with `p ≈ 0.002`) clear it?

6. **The ABSTAIN_SOFT reason text is hardcoded to a single string (`no measured or directional recommendation cleared materiality + cannibalization gating`).** Could the engine produce a more specific reason — "all candidates suppressed because no causal prior exists for vertical=beauty" or "considered list emptied by materiality gate" — so the merchant copy can be generated from a fact rather than a slogan?

7. **Legacy emits `frequency_accelerator` with `p = 1e-10` (saturated)** and a CI of `[-0.1023, -0.0229]`. This is presented as Quick Win with a Moderate signal. Under V2 reclassification, is `frequency_accelerator` measured/directional or targeting? The TARGETING_RECLASSIFY_PLAYS list in M4b includes `subscription_nudge`, `routine_builder`, `empty_bottle`, `category_expansion`, `bestseller_amplify`, `vip_no_discount_nurture`, `replenishment_reminder` — `frequency_accelerator` is *not* on it, which suggests V2 considers it measured/directional. So why didn't V2 surface it?

8. **`new_customer_rate` BH dedup (M4a T4a.6) — confirm the V2 receipts are the canonical state.** Legacy `run_summary.json` shows `new_customer_rate.p = 9.5e-05` at L28; V2 shows `null`. The M4b summary called this a correctness fix. This is a question about which receipts files merchants/agents read downstream, not about correctness.
