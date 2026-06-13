# Reconciled Discussion — Campaign Slate and Play Lifecycle

_Discovery / framing only. No code edits. No implementation plan. No milestone scoping. The goal of this document is to clarify the problem, the possible directions, and the decisions still open before any implementation work begins._

## Executive Summary

Two product realities surfaced after Phase 5 stabilized V2 on the Beauty Brand fixture:

1. **Campaign slate, not single play.** Merchants paying $500–$1,000/month run multi-campaign monthly programs; a briefing that surfaces 0–1 plays reads thin against that reality.
2. **Stateless month-over-month repeat.** With ~30 more days of data the engine will likely re-recommend the same play to mostly the same cohort and present it as fresh — undermining trust on the second run.

PM and DS Architect converge that the engine cannot solve outcome lifecycle locally and must not pretend to. They diverge on whether — and how much — a thin *recommendation* lifecycle layer should be built locally now versus deferred to the agentic Klaviyo/Shopify product.

There is **one forced decision-science answer** in this discussion: the engine must not claim, today or under any local-memory architecture, that a recommended play "worked" or "didn't work" without realized campaign data. Everything else is a deliberate product call within that constraint, and the most consequential prerequisite — whether M3 audience-ids are stable across runs at all — has not yet been measured and should be checked before any lifecycle scoping.

## Why This Matters

- **Merchant trust failure on the second run is the most likely near-term failure mode.** A merchant getting the same recommendation in May and June with no acknowledgement perceives the engine as not reading itself — worse than abstain, and arrives quickly.
- **Pricing tier defensibility.** $500–$1,000/month requires the product to feel like a relationship over time, not a monthly report. Continuity is the price-defending feature, but only if it is honest.
- **Foundation for the agentic system.** The eventual detect → publish → monitor → readout loop needs anchors: a stable lineage id, a pre-registered prediction, an outcome seam. Building any of those poorly now creates rework when integration arrives; building none of them now leaves the agentic product without an attachment point.
- **The Phase 5 calibration stub (M9) currently returns `{}` and has no consumer.** Without lifecycle, it stays a contract-only artifact and decays.

## What PM Emphasized

- The merchant-perception cost of "single play, fresh each month" is large and immediate; the pricing tier cannot be defended without continuity.
- Six product options exist, ranging from full deferral (Option 1) to a stubbed agentic loop (Option 6); the cleanest forward-compatible option is to define the campaign-outcome seam now without a consumer (Option 4).
- The contract's most important unresolved question is **how the engine expresses economic context** for plays where it has no measured effect. Decline-to-quote (current V2) is austere; a typed `opportunity_context` block in parametric form is a defensible alternative.
- Multi-campaign reality is real: a merchant running 8 campaigns of which the engine recommended 1 leaves 87.5% of their program outside the engine's read. The engine can be silent (current), can ask, or — risky — can try to infer.
- PM deliberately did not collapse to a single recommendation; the choice is product-strategy-driven and should be made after the DS architect resolves what is scientifically possible.

## What DS Architect Emphasized

- **Categorical separation between engine-behavior facts and campaign-behavior facts.** The local engine can know the first set deterministically from CSV + its own M9 history. It cannot infer the second set without realized data — Klaviyo sends, Shopify orders attributed, or merchant declaration.
- **Of the nine PM-implied lifecycle states, five are CSV-supportable and four require integration or merchant declaration.** Building the latter four into the local engine without a data source for them is a category error.
- **Recommendation-lineage** (play_id × audience_definition_id × store_id) is the right primary key for "is this the same recommendation we made before?" — not play_id alone (over-suppresses) and not audience-member-set (under-suppresses on rolling cohorts). The M5 fatigue stub keying by play_id alone is wrong and should be lineage-keyed regardless of broader scope.
- **The campaign-outcome seam is a discipline, not a feature.** Defining it now — even with no consumer and no populated rows — constrains the engine's local code from drifting into outcome inference. Empty schema does its job by being a forcing function.
- **Pre-registration is the cheap-but-real win.** Storing the engine's expected direction and minimum-interesting size at recommendation time costs one schema field and makes any future readout falsifiable rather than HARK-prone.
- **The audience-identity stability problem has not been measured and should be measured before any lifecycle work.** If the M3 audience builders churn ids substantially with 30 days of additional data, lifecycle suppression is built on sand. This is a one-day investigation, not a milestone.
- **Several PM "options" reduce, on inspection, to one decision-science answer:** the engine cannot claim outcomes locally, period. Around that constraint, options remain real.

## Points Of Agreement

1. The local engine **must not fabricate outcome inference**. Any future memory architecture must respect this — and indeed the schema should be a forcing function against drift.
2. **`recommended_history.json` (M9)** is the engine-behavior log; a hypothetical `campaign_outcomes.json` is outside-world truth. They are different artifacts with different writers, different trust levels, different lifecycles. Treating one as a superset of the other is wrong.
3. The **considered list** is the highest-payoff continuity surface per unit of work. "Considered last month for the same reason; same rejection holds" is honest, cheap, and merchant-meaningful.
4. **Pre-registration of expected direction and window** at recommendation time is defensible and small.
5. **Engine-fatigue gating should be lineage-keyed** (play_id × audience_definition_id × store_id), not play_id-keyed. M5's current keying is a correctness bug regardless of broader lifecycle scope.
6. **No merchant-facing language** that implies the engine knows whether the recommendation was acted on. All such language requires merchant declaration or integration.
7. **Phase 5 should not be undone**, M10 cleanup remains out of scope for this discussion, and no V2 default flip is implied.
8. **Decline-to-quote remains correct for targeting plays.** Any economic-context block for directional plays must be parametric and merchant-controlled, never engine-claimed lift.

## Points Of Tension

1. **How much memory to add now.** PM frames it as a six-option continuum; DS frames it as a single "thin lineage layer + outcome seam stub" with several smaller correctness fixes. PM is more concerned with merchant perception; DS is more concerned with not paying for schema rework twice.
2. **Implicit-inference framing.** PM's "if `returning_customer_share` did not move, infer the merchant probably didn't run it" path is — per DS — a confounded inference identical in structure to the errors M0–M9 just removed. PM frames it as a fallback heuristic; DS rejects it as fabricated causality. **DS's position holds because the data does not support the inference.**
3. **Slate framing (Option 5).** PM offers it as a way to close the "looks thin" gap. DS pushes back: a coverage map of "what every DTC store does" easily drifts into generic playbook content unless every per-slot annotation derives from a real per-store fact. The bar is higher than the considered list, not lower.
4. **Opportunity-context block.** PM advocates a typed parametric block alongside `revenue_range` for directional plays. DS conditionally agrees — only if the parameter is rigidly merchant-controlled, never engine-picked, and labelled as a calculator-style sketch rather than a forecast. The wrong implementation re-imports the conversion-benchmark-as-causal-lift error the overhaul corrected.
5. **Negative-outcome handling without integration.** PM proposes "stop recommending what didn't work." DS says: not possible without realized data; the honest degenerate behavior after K runs of the same lineage with no status declared is **ask the merchant**, not stop. PM has not accepted what merchant-input UX cost is acceptable.
6. **Pricing-tier defense.** PM positions continuity as load-bearing for the $500–$1,000/month tier. DS notes this is a pure product call and declines to opine, but raises a deeper question: is "data-scientist replacement" compatible at all with monthly cadence and zero campaign visibility — i.e., is positioning, not memory, the actual gap?

## Product / Science Boundary

A clear partition emerges from the discussion:

- **Local engine owns (today, no integration required):** what was recommended, what audience definition, the supporting state-statistic at the time, gate/rejection state, audience-membership overlap across runs (if customer-id anchoring works), engine-fatigue gating, pre-registered expectation. All of these are facts about the engine and the data, not the campaign.

- **Agentic product owns (post-integration, Klaviyo/Shopify):** whether the merchant ran any recommendation, what was actually sent, realized opens/clicks/conversions, attributed orders, holdout / A-B / lift, per-customer fatigue, calibrated revenue ranges. None of these can be inferred from CSV.

- **Joint slot, lives in the local engine but populated externally:** `recommendation_status_external` — declared by the merchant, written by the agentic monitor, or imported. Default null. **The engine never infers values for this field.** This is the campaign-outcome seam in concrete form.

The seam is the contract that lets the local engine and the agentic product compose later without rework. Defining it now is cheap and disciplinary. Populating it requires integration or merchant input, which is out of scope for the local engine.

## Possible Directions

Five directions, roughly ordered by ambition. They are not mutually exclusive; some compose. **No choice is recommended in this document.**

**A. Status quo (defer all lifecycle).** Ship V2 as-is post-Phase 5. Acknowledge in product copy that the engine evaluates each month independently. No memory consumer beyond the receipts log.
- Pro: smallest scope; finishes Phase 5 cleanly; no schema-rework risk.
- Con: month-over-month repeat trust failure on the second real-merchant run; M9 outcome log decays; pricing tier hard to defend.

**B. Read-only memory (passive badge, no behavior change).** Engine reads `recommended_history.json` and surfaces a "previously recommended" badge on play cards whose lineage matches a prior run. Adds continuity in the considered list ("same reason held last month"). No suppression; no new states; no forbidden claims.
- Pro: smallest behavior change; closes the perception gap; honest by construction.
- Con: doesn't actually suppress repeats; merchant may demand "okay so should I run it again?" — which the engine cannot answer.

**C. Thin recommendation-lifecycle layer (DS-preferred minimum).** Adds five concepts only: `recommendation_lineage_id`, `audience_membership_overlap`, `prior_state_snapshot`, `pre_registered_expectation`, `engine_fatigue_state` (lineage-keyed). The fatigue gate (M5 stub) graduates from blunt 28-day window to lineage-aware "have we said this about this lineage K runs in a row." All concepts derive from CSV + M9 history alone.
- Pro: fixes month-over-month repeat without integration; surfaces continuity; pre-registration anchor benefits any future readout; corrects the M5 keying bug.
- Con: still half a relationship without realized outcomes; risk that "I don't know what you did" framing inconsistencies confuse the merchant.

**D. Lightweight interface (campaign-outcome seam stubbed, no consumer).** Adds the optional `data/campaign_outcomes.json` schema; engine reads it if present, falls back to A or B/C if empty. Defines `recommendation_status_external` slot but never infers it. Optionally adds a one-click merchant-input form ("did you run this? yes / no / partial").
- Pro: forward-compatible with Klaviyo agent; disciplinary against drift; merchant-input path becomes available if PM accepts the UX cost.
- Con: empty by default means seam is invisible to early merchants; merchant-input UX cost must be accepted to make negative-outcome handling honest.

**E. Composite (B + C + D).** Read-only badge for visibility; thin lifecycle layer for honest suppression and pre-registration; outcome seam for forward compatibility; merchant-input as the only path to populate the seam pre-integration.
- Pro: each piece is small and individually defensible; the engine is meaningfully more useful month-over-month while remaining honest.
- Con: meaningful schema and contract work; requires the audience-stability prerequisite to pass first; risks scope creep into Option 6 territory.

Slate framing (Option 5 in the PM doc) and the typed `opportunity_context` block are orthogonal product surface decisions and can be considered alongside any of A–E.

## Key Questions Before Implementation

These should be answered before scoping a Phase 1B / Phase 6 milestone. Each is bounded; none is open-ended.

1. **Audience-identity stability test (DS, prerequisite).** Run M3 detect twice on the same Beauty Brand fixture with byte-identical data and inspect whether `audience.id` is stable. Then run with one synthetic added order and inspect churn. **Lifecycle work is premature until this passes.** Estimated effort: one day; no milestone.

2. **Lineage primary key (DS).** Confirm the lineage formulation `(play_id, audience_definition_id, store_id)` is consistent with how M3 builders express audience identity and how M9 history records it. Decide on `audience_definition_version` policy.

3. **Memory direction commitment (joint).** Pick one of A / B / C / D / E (or another composite). The DS-preferred minimum is C + the lineage-keyed fatigue fix. PM may add B or D depending on merchant-perception priorities.

4. **Outcome-seam decision (joint, leaning DS-yes).** Define `data/campaign_outcomes.json` schema now even with no consumer (forcing-function discipline) — yes or no.

5. **Pre-registration display posture (PM).** If the engine pre-registers expected direction and window at recommendation time, does that surface to the merchant or stay internal?

6. **Merchant-input UX cost (PM).** Is a one-click "did you run this?" prompt per recommendation per month acceptable to the local CSV→HTML workflow? If no, honest negative-outcome handling is impossible pre-integration, regardless of memory architecture.

7. **Opportunity-context contract decision (joint).** Add a typed `opportunity_context` block alongside `revenue_range` for directional plays, parametric and merchant-controlled, OR keep the current decline-to-quote behavior. Affects briefing-template work and merchant economic-justification claims.

8. **Slate framing (PM).** In or out of scope. If in, every per-slot annotation must derive from a real per-store fact; otherwise out.

9. **Calibration arrival horizon (PM).** When does PM expect realized-vs-predicted data to flow into the engine — Klaviyo agent, merchant declaration, manual? Tightens or loosens the urgency of pre-registration and the outcome seam.

10. **Positioning compatibility (PM, deeper question).** Is "data-scientist replacement" defensible at monthly cadence with zero campaign visibility, regardless of memory architecture? If positioning needs to shift in the local-only era, that shift is upstream of any lifecycle work.

## What Should Not Be Decided Yet

- **Whether to flip V2 default before manual founder testing on Phase 5 completes.** Out of scope for this discussion; not a lifecycle question.
- **M10 legacy cleanup.** Out of scope for this discussion. Both agents explicitly excluded.
- **Klaviyo / Shopify integration scope or sequencing.** Belongs to a separate planning conversation about the agentic product, not this framing.
- **Final merchant-facing vocabulary for lifecycle states.** Product-strategy call to be made after structural concepts are resolved. The data structure must keep state and label decoupled regardless.
- **Whether negative-outcome inference can ever be honest from CSV alone.** Decision-science forces a "no"; this is settled, not open.
- **Whether the engine should *infer* what other campaigns the merchant is running from order/UTM data.** Decision-science forces a "no" at the play level; settled.
- **Final priority of Options A–E.** That is an implementation-planning call, not a framing call, and depends on the audience-stability test outcome and the merchant-input UX cost decision above.

## Recommended Next Conversation

A focused short-cycle decision sequence, not an implementation kickoff:

1. **Run the audience-identity stability test** on Beauty Brand and one synthetic-added-order fixture. One-day investigation. Report: does `audience.id` for `first_to_second_purchase` stay stable across two byte-identical runs, and does it churn meaningfully with 30 days of synthetic additions?
2. **PM picks the merchant-input UX posture.** One question: is a one-click "did you run this?" acceptable in the local CSV→HTML workflow? Yes / no.
3. **PM and DS converge on a memory direction (A / B / C / D / E).** With (1) and (2) answered, the choice is small.
4. **Implementation-manager phase.** Only after (1)–(3) are decided. Convert the chosen direction into a phased, low-risk plan that preserves the local CSV→HTML workflow, keeps the engine runnable after every patch, and resolves whatever subset of the eight pending questions above the chosen direction requires.

Phase 5 manual founder testing should proceed in parallel with steps 1 and 2 — it is independent of lifecycle scoping and provides additional product signal for step 3.
