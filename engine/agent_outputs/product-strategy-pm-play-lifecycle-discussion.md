# Product PM Discussion — Campaign Slate and Play Lifecycle

## Product Question

Now that V2 produces one defensible directional play on Beauty Brand (M0–M9 + Phase 5 complete), two product realities show up that the current decision contract does not model:

1. **Slate, not single play.** Real DTC merchants paying $500–$1,000/month do not run "the one perfect play this month." Lifecycle marketers schedule a slate — a winback flow, an abandoned-browse, a VIP nurture, a launch promo — typically 4–10 active campaigns per month. A monthly briefing that surfaces exactly one directional card looks correct to a data scientist and looks thin to an operator.

2. **Stateless month-over-month.** If the engine reruns on June 1 with ~30 more days of data, the same first-to-second purchase audience is still there, the same `returning_customer_share` signal is still trending, the same gates still bind. Without lifecycle memory, the engine will re-recommend the same play to mostly the same cohort and present it as a fresh recommendation. That is the single fastest way to lose merchant trust after month 2 — worse than abstain.

The decision: should the **local engine** model some version of campaign memory and lifecycle state now, wait for the agentic Klaviyo/Shopify system, or define a lightweight interface that lets the local engine behave correctly without overbuilding?

This is a framing discussion, not an implementation plan. The output of this discussion is the set of decisions the DS Architect needs to react to before any milestone scoping happens.

## Merchant Expectations

The merchant operating this product is not a data scientist. They are usually one of three personas:

- **Founder/operator at a $500K–$3M ARR DTC brand.** Wears the marketing hat. Runs Klaviyo themselves. Wants someone smart to tell them what to ship next, and to stop them from doing dumb things. Would pay for "what to do," not for "how confident the engine is."
- **Lifecycle marketer at a $3M–$15M brand.** Already has a slate of 6–12 monthly campaigns. Wants the engine to tell them which ones to scale, which to retire, which audience is unexplored, and which experiment is mature enough to read out.
- **Agency operator running 5–20 brands.** Wants a defensible, repeatable read on each store that they can hand to the brand owner. Cares about the rejection list more than the recommendations because that is what differentiates the agency's read from a generic playbook.

What all three expect that V2 currently does not deliver:

- **Continuity.** "Last month you told me to do X. What happened?" If the engine cannot answer that, it is not a data scientist; it is a monthly horoscope.
- **A slate, not a single play.** A merchant who runs 1 campaign because the engine recommended 1 will under-ship and blame the engine for flat numbers. A merchant who runs 6 campaigns of which the engine recommended 1 cannot tell the engine what worked.
- **Knowing when not to repeat.** If the engine recommended winback last month, the merchant ran it, and the audience was hit — the engine should know not to recommend the same audience this month.
- **Knowing when to scale.** If the merchant ran the recommended play and it worked, the merchant expects "do it again, expand to this adjacent cohort" — not a different play.
- **An explanation when the play was not run.** If the engine said do X and the merchant didn't, the merchant expects either (a) "still recommended" or (b) "no longer recommended because Y changed."

Critically: **the merchant does not expect the engine to know whether they ran the play unless we ask them or unless we are integrated with their stack.** This distinction is the single most important framing point of this discussion. The local engine cannot today *know* what the merchant did. It can only know what it *recommended*.

## Pricing / Value Implications

At $500–$1,000/month the buyer is comparing against:

- **A fractional CMO or growth consultant** ($2K–$8K/month) who reviews the data, sets a slate, watches outcomes, and adjusts. The engine has to do at least a recognizable subset of this loop or it gets benchmarked against a junior analyst contract instead.
- **A Klaviyo/Triple Whale/Lifetimely-tier analytics tool** ($100–$400/month) that surfaces metrics. If the engine looks like another dashboard, the price ceiling drops by half.
- **A playbook PDF / Slack community subscription** ($50–$200/month). If the engine looks like a generic playbook with the merchant's audience sizes filled in, the price ceiling drops by 5x.

The pricing implication is sharp: a $500–$1,000/month tier requires the product to *behave like a relationship over time*, not like a monthly report. Three ways to feel like a relationship without faking ML:

1. **Memory of what was recommended** (cheap; the M9 `recommended_history.json` already persists this).
2. **A merchant-facing record of what the engine said about each play over time** ("recommended last month, still recommended this month, audience now -38 because we excluded recently-contacted").
3. **A slate framing** — even if only 1 play is measured/directional, the page should acknowledge "you are likely also running winback, abandoned-cart, post-purchase — here is how we read those signals this month" rather than presenting itself as the entire growth program.

If we ship a product that is honest, abstains correctly, and produces a single defensible card every month with no continuity, the ceiling is $200–$400/month, not $500–$1,000. The continuity is the price-defending feature.

## One Play vs Campaign Slate

The contract today (PM doc, M7, Phase 5) says: 0–3 plays per run, max-3 cap, ABSTAIN_SOFT if no measured/directional. That is correct as a recommendation rule. It is wrong as a portfolio rule.

Three competing models:

**Model A — One best play (current):** The engine surfaces 0–3 plays and the merchant treats them as the slate. Wrong: merchants run more campaigns than the engine ever recommends, so the engine is silent on the bulk of their actual spend.

**Model B — Slate-as-coverage:** The engine surfaces a *map* of the merchant's likely lifecycle slate (winback, post-purchase, abandoned-browse, replenishment, VIP, newsletter, launch) and labels each one with the engine's read: "currently scheduled here / strong signal / weak signal / nothing to add / hold back this month." The 0–3 *recommendations* still exist as the highlight, but they sit inside a slate-aware reading. This is closer to how a fractional CMO operates.

**Model C — Recommendations + acknowledgements:** The engine recommends 0–3 plays and *additionally* asks "which other campaigns are you running?" The acknowledgements are merchant-input until Klaviyo integration exists. The engine then has portfolio context for guardrails (don't recommend a play whose audience overlaps a campaign the merchant says they are already running).

These are not mutually exclusive. Phase 1 (V2 today) is Model A. The agentic future is essentially Model B with full integration. Model C is the lightweight interface that lets us approach Model B without integrations.

The framing question for the DS architect: do we keep the local engine in Model A (because it is the only honest model when the engine is blind to actual sends) and do all slate/portfolio work after Klaviyo integration? Or do we start moving toward Model B/C now via a merchant-input layer?

## Month-Over-Month Repeat Risk

This is the single biggest unsurfaced product risk in the V2 stack today.

Consider: it is June 1. The Beauty Brand engine reran. `returning_customer_share` is still trending up (the underlying signal is structural, not transient — that's the whole point of "consistency_across_windows >= 2"). The first-to-second purchase audience definition has not changed. The audience size is now 312 (was 286, +26 new single-purchase customers in May).

What does V2 produce today? It produces the same directional card, with audience 312, the same recommendation text, the same "Emerging" badge. The only difference is the deltas in the state-of-store paragraph. From the merchant's perspective this reads as: "the engine has nothing new to say."

This is not a bug in the M0–M9 stack — those milestones were honest about being stateless. It is a product-level risk that the contract does not yet address. There are several distinct flavors of "the same play came up again":

1. **Same play, mostly same audience** (286 people in month 1, 286 of which 260 overlap in month 2). This is the highest-risk flavor — the merchant who ran it last month would over-contact.
2. **Same play, mostly different audience** (286 in month 1, 312 in month 2, only 80 overlap because the cohort definition is rolling). Lower risk; arguably the merchant should re-run.
3. **Same play, audience grew because the underlying business grew** (26 new customers entered the cohort). Should be presented as "expand last month's send to the new 26."
4. **Same play, audience shrank** (e.g., merchant ran it, removed the recipients, audience now 38). Should be presented as "your previous send covered most of this audience; nothing new to do here this month."

Without knowing whether the merchant ran the play, the engine cannot distinguish (1) from (3) from (4). This is the load-bearing reason memory matters.

Even without integration, the engine *does* know what it recommended (M9 history). That is enough to support a weaker but real lifecycle behavior: **the engine can tell the merchant "I recommended this last month; here is what's the same and what changed."** That is not faking ML; it is reading its own log.

## Expected Product Behavior By Scenario

Each of these is a state the merchant can be in on the second run. The product needs an answer for each. The answer can be "we don't know yet, please tell us" or "we infer from data" or "we wait until Klaviyo is wired" — but it needs to be a deliberate answer.

### recommendation not run

Merchant did not run last month's recommendation. Engine cannot directly observe this. Two paths:

- **Implicit inference:** if `returning_customer_share` did not move in the direction the play would have produced, and audience size hasn't shrunk meaningfully, the engine infers "probably not run" and re-recommends with the same priority. Risk: false negatives if the play takes 60+ days to materialize.
- **Merchant input:** the engine asks "did you run this last month?" with three options (Yes, No, Partially). Cheapest reliable signal. UX cost: one click per recommendation per month.

Expected merchant feeling: "I see, you noticed I didn't run it. Should I now?" If the engine repeats blindly, the merchant feels unheard.

### recommendation run, results unavailable

Merchant ran last month's recommendation. Klaviyo is not wired. Engine has no realized data. Two paths:

- **Hold the play in a "watching" state.** Don't re-recommend. Surface as "you ran this on May 15 — we'll know in 14–28 days if it lifted retention."
- **Allow the merchant to mark it as "running" and enter a measurement window.** Engine treats the next 28 days as the readout window and surfaces a result expectation.

Expected merchant feeling: "the engine remembers I ran this and is waiting before its next call." This is the relationship.

### recommendation run, positive result

Merchant ran the play and the proxy metric moved in the predicted direction. Three competing options:

- **Repeat to the new audience** (rolling cohort gained 30 new entrants → recommend send to those 30).
- **Scale to an adjacent cohort** (first-to-second worked → try second-to-third).
- **Retire the play and rotate** (don't burn the channel; let the audience rest 60 days).

The right answer depends on the audience definition's refresh rate and the merchant's contact-frequency policy. The engine should not silently default to "repeat." It should recommend explicitly with the rationale.

Expected merchant feeling: "the engine saw this worked and is helping me decide what to do next." This is the data-scientist replacement claim.

### recommendation run, negative result

Merchant ran the play and the proxy metric moved against the prediction or did nothing. The engine should:

- **Mark the play as "tested, did not lift" for this store** in the calibration record.
- **Reduce its prior for this play at this store** (a real ML-readiness use of the M9 log).
- **Not recommend the same play to mostly the same audience next month.**
- **Surface the negative outcome explicitly in the briefing** — "we recommended X last month, your store did not see lift; we are not recommending it again until conditions change."

This is the trust-defining moment. A product that quietly stops recommending a play that didn't work loses credit. A product that explicitly says "this didn't work, here's why we think so, here's what we're doing about it" gains credit faster than from a positive outcome.

### same play but new audience

E.g., the cohort is rolling, last month's 286 were contacted, this month's 312 contains 80 of last month's plus 232 fresh. Three options:

- **Recommend the delta (232).** Treat as an incremental expansion.
- **Recommend the full audience but flag the overlap** ("232 are new since last send; 80 received your previous campaign and should be excluded if your contact policy rules them out").
- **Recommend the full audience and let the merchant decide.**

Recommend the delta is the cleanest if Klaviyo can produce the suppression list. Without Klaviyo integration, recommending the full audience with overlap flagged is the honest path.

### same play and mostly same audience

E.g., the cohort is stable; 286 last month, 290 this month, 270 overlap. Two options:

- **Suppress the recommendation entirely this month.** The engine acknowledges the underlying signal is unchanged and explicitly defers.
- **Re-recommend with a "you already sent this; here is what changed" framing.** The engine acknowledges the audience overlap and produces a smaller-audience refresh recommendation.

The first is cleaner. The second is the pure fractional-CMO behavior. The fatigue gate (M5 stub) is the existing seam that decides this.

## Local Engine vs Final Agentic Product Boundary

This is the central architectural question: where does play lifecycle live?

The agentic product (vision: detect → validate → generate Klaviyo bundle → approve → publish → monitor → A/B → store → learn) clearly owns the *measurement* side of lifecycle. Klaviyo gives realized opens, clicks, conversions; Shopify gives realized orders. Without those, the engine cannot truly know if a play "worked."

But the local engine already owns:

- **What was recommended** (M9 `recommended_history.json`).
- **What gates fired** (M5/M6 receipts).
- **What was rejected** (M7 considered list).
- **The audience definition** (M3 candidate builders).

That set is sufficient to support a *recommendation lifecycle* (recommended → re-recommended → suppressed → repeated → retired) even without knowing whether the merchant ran anything. It is *insufficient* to support a *campaign lifecycle* (recommended → published → measured → scaled).

The boundary, then, is:

- **Recommendation lifecycle = local engine.** The engine can and should track its own recommendations across runs. This requires no Klaviyo integration. It is implemented by reading the M9 history.
- **Campaign lifecycle = agentic product.** The engine can ingest realized outcomes from the agentic layer when it exists, but should not be designed to require them.
- **The seam is a single optional file** (e.g., `data/campaign_outcomes.json`) with a documented schema. The local engine reads it if present; produces a richer briefing if it has data; falls back gracefully if it doesn't. Klaviyo/Shopify integrations write it. A merchant could also fill it in by hand if they wanted to (a CSV input). This is the lightweight interface.

Three frames the DS architect should react to:

- **Frame 1: defer all lifecycle to the agentic product.** The local engine stays stateless. Risk: month-over-month repeat erodes trust before integration ships.
- **Frame 2: build full recommendation lifecycle locally, defer campaign lifecycle.** The engine reads its own history, suppresses repeats, surfaces continuity. No new integration needed. Risk: without realized outcomes, "lifecycle" is half a story (we know what we said, not what happened).
- **Frame 3: define the campaign-outcome seam now, populate it from a stub today (e.g., merchant input or zero rows), let the agentic product fill it later.** Engine treats outcomes as optional input. The seam becomes the contract that Klaviyo agent and monitor agent must produce. This is the "lightweight interface" option in the user's question.

Frame 3 is the architecturally cleanest. Frame 1 is the lowest immediate cost. Frame 2 is the highest near-term merchant value at moderate cost.

## Product Options

Six options, ordered roughly by ambition. Not mutually exclusive; some compose.

**Option 1 — Status quo (defer all lifecycle).** Ship V2 as-is. Acknowledge in product copy that "the engine evaluates each month independently." No memory beyond the receipts log. Pro: smallest scope, finishes Phase 5 cleanly, ships M10 as planned. Con: month-over-month repeat is real and will hit on the second Beauty Brand run.

**Option 2 — Read-only memory (single read).** Engine reads its own `recommended_history.json` on every run and surfaces a "recommended last month" badge on the play card if the same play_id was recommended in the prior 1–2 runs. No suppression, no lifecycle states; just visibility. Pro: smallest behavior change; high merchant signal. Con: doesn't actually suppress repeats, just shows them.

**Option 3 — Recommendation lifecycle (local).** Engine reads its history and applies a real lifecycle state per (play_id, audience_definition): `new` / `repeat` / `mature_repeat` / `recently_recommended_suppress`. Surfaces these states on the briefing. The fatigue gate (M5 stub) graduates from a blunt 28-day window to a smarter "have we said this about this audience N months in a row" check. Pro: fixes month-over-month repeat without any integration. Con: still doesn't know if the merchant did anything.

**Option 4 — Campaign-outcome seam (interface only, no consumer).** Define `data/campaign_outcomes.json` schema in code with an empty default. Engine reads it, branches on presence, falls back to Option 1 behavior when empty. Adds a "did you run this?" optional CLI prompt or merchant-input form. Pro: forward-compatible with Klaviyo agent; doesn't promise behavior we cannot deliver. Con: empty-by-default means the seam is invisible to early merchants.

**Option 5 — Slate framing (without lifecycle).** Reframe the briefing from "the engine's recommendation" to "the engine's read on your monthly slate." Add a section above Recommended that lists 6–10 lifecycle plays (winback, abandoned, post-purchase, replenishment, VIP, newsletter, launch) with a one-line engine read on each ("not enough signal to call," "your audience for this is healthy," "we'd revisit if X moves"). Independent of lifecycle memory. Pro: closes the "looks thin" gap on Beauty Brand-style outputs. Con: risk of adding shallow-read content that drifts toward generic playbook.

**Option 6 — Full agentic stub.** Define and stub the full lifecycle (recommend → validate → generate bundle → approve → publish → monitor → A/B → outcome → repeat/scale/retire) with the local engine playing the "recommend" and "monitor" roles only, and stubbing the Klaviyo bundle generator with a structured outline. Pro: matches the long-term vision exactly. Con: enormous scope; risks overbuilding before any integration validates the seams.

## Product Risks

**Risks of leaving the engine stateless (Option 1):**

- Month-over-month repeat is the most likely first-real-merchant trust failure. A merchant getting the same recommendation twice with no acknowledgement will assume the engine doesn't read its own outputs.
- "Single play feels thin" compounds with "single play feels stale" — by month 3 the merchant is paying $1,500 for three near-identical recommendations.
- Pricing tier unsupportable. $500–$1,000/month with no continuity is hard to defend against either a $200/month dashboard or a $4K fractional CMO.
- Phase 1's calibration stub (M9) becomes a permanent stub; without lifecycle, there is no path from history to calibrated priors.

**Risks of overbuilding memory before integrations exist (Options 3, 5, 6):**

- A "lifecycle" that reads its own log but cannot observe outcomes is half a relationship. If we surface "you ran this last month" without actually knowing, we lie. If we surface "we recommended this last month" we are honest but anemic.
- A campaign-outcome schema designed before any agent populates it will likely be wrong on first integration. Write it twice or write it later.
- Slate framing without store-specific signal devolves into generic playbook content — the exact failure mode the Phase 1 PM doc warned against (Q9 "what would make this product feel too basic").
- Local engine becomes a small product simulating a big product, which is the slowest path to either.

**Cross-cutting risks regardless of option:**

- Merchant-input UX (asking "did you run it?") needs to be light. If we add a friction step to the local CSV-to-HTML workflow, we break the "one-touch" promise.
- Adding lifecycle state introduces schema versioning. M9's `recommended_history.json` has `schema_version: "1.0.0"` but no migrator.
- Audience identity across runs is non-trivial. "Same audience" requires a stable audience-id derivation that is not just a count. If the audience builder is non-deterministic across runs, lifecycle calls drift.
- Privacy: tracking "we recommended X to audience Y last month" is fine; tracking "merchant sent to these 286 customers" is a data-handling commitment.

## Open Questions For DS Architect

These are decisions the DS Architect should react to before any milestone scoping. Each is binary or short-list; none are open-ended.

1. **Is recommendation lifecycle a Phase 1B addition, a Phase 2 feature, or post-integration?** (Frames 1/2/3 in the boundary section.)

2. **Is "audience identity across runs" a tractable problem with the current M3 audience builders?** Specifically: given the same data + 30 more days, would the `first_to_second_purchase` audience id be stable, drift slowly, or churn substantially? If churn is substantial, lifecycle suppression is meaningless and we should defer to integration.

3. **How should the engine model "we recommended this last month" without lying about whether the merchant ran it?** Two options: (a) a passive "previously recommended" badge with no behavior change; (b) an active suppression that requires merchant input or an outcome file. Both are honest; they have different UX costs.

4. **What is the right merchant-facing vocabulary for lifecycle states?** "New / Repeated / Mature / Suppressed" leaks engineering. "First call this month / We said this last month, here is what changed / Same audience as last month — hold this round" is closer to merchant English. The DS architect should confirm the data structure can support whatever vocabulary the PM eventually chooses.

5. **Should the campaign-outcome seam be defined now (Option 4) even with no consumer?** The risk of getting it wrong is a forward-compat headache. The risk of not defining it is that Klaviyo agent design later has no anchor.

6. **Slate framing (Option 5) — is the slate of likely lifecycle plays a real engine output, a static config of "things every DTC store does," or out of scope until vertical-specific play registries mature?** This affects whether the briefing has a "your slate" section in Phase 2 or whether the product accepts that the engine speaks only on what it analyzed.

7. **Repeat-suppression policy: per-audience or per-play_id?** A play recommended to a different audience next month is a different recommendation. A play recommended to the same audience next month is a repeat. The fatigue gate (M5) currently keys by play_id only.

8. **Negative-outcome handling without integration: is it possible at all?** If the engine can never know a play failed, can it ever stop recommending it? Or do we accept that until Klaviyo is wired, the engine is allowed to repeat itself with merchant override as the only correction mechanism?

9. **Calibration loop scope: is M9's `recommended_history.json` the canonical local memory, or is the eventual `data/campaign_outcomes.json` a separate artifact that the calibration stub also reads?** The current contract leaves this ambiguous; the DS architect should pick.

10. **Pricing-tier defense: is the $500–$1,000/month value claim defensible without lifecycle, by leaning on rejection-list quality and abstain honesty alone?** This is a product-strategy question masquerading as an engineering question. If yes, we can stay in Option 1 longer. If no, lifecycle becomes Phase 1B.

11. **Revenue projection vs revenue / opportunity context: how should the engine express the economic case across plays of different types?**
    - For **measured** plays the engine has an observed effect, an audience, an AOV, and a defensible range from a causal-class prior. p10/p50/p90 with `source` labeled is the right form.
    - For **directional** plays (like first-to-second on Beauty Brand today) the supporting metric is a state statistic, not an intervention effect. Phase 5.6 correctly suppresses revenue. But the merchant still needs an *opportunity sketch*: "this audience contributes $X/month at current AOV; converting Y% of them to a second purchase would add $Z" — a sizing exercise, not a forecast. Should the engine surface that as a separate "opportunity context" block, distinct from `revenue_range`? This is the most contract-relevant form question of this discussion.
    - For **targeting** plays (the six considered cards on Beauty Brand today) suppression is correct; the audience size + AOV + disclaimer is the honest form. But the merchant cannot prioritize a slate without *some* economic frame. Two options: (a) a portfolio-level "you have ~$X/month sitting in these audience definitions" footer, audience-overlap-corrected; (b) per-card audience size × AOV × "if you can convert Y%" parametric range, with the parameter explicitly merchant-controlled.
    - For **experiments / repeat / scale decisions** post-outcome, the engine has realized data and can express revenue impact directly. This is post-integration and out of scope for the local engine today.

    The DS architect should react to: should the contract carry a typed `opportunity_context` block alongside `revenue_range` for directional and targeting plays, or should the briefing simply decline to put a number on those plays at all? The current V2 chooses the second; the merchant economic-justification need pulls toward the first.

12. **Multi-campaign reality: does the contract need to acknowledge campaigns the engine did not author?** A merchant running 8 campaigns of which the engine recommended 1 has the engine speaking on 12.5% of their actual program. The engine can: (a) stay silent on the rest (current behavior, honest, thin); (b) ask the merchant to declare the rest (Option 4 territory); (c) infer from order/UTM data what is running (out of scope without Klaviyo). The pricing implication of this choice is large; the DS architect should weigh in on (c) — is there enough signal in CSV order data alone to detect that a winback or post-purchase flow is active, even if we don't know which tool sent it?

---

**Summary, no single recommendation:** the V2 stack today is honest and structurally correct but stateless and single-play. Two product realities — campaign slate and month-over-month repeat — are not yet modeled. There are six product options ranging from "defer everything" to "stub the full agentic loop." The choice depends on three DS-architect-resolvable questions: audience identity stability across runs, the cost of the campaign-outcome seam, and whether revenue-opportunity context can be expressed for directional and targeting plays without becoming fabrication.
