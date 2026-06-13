# Product PM Review — Phase 5 Beauty Brand Sample

## Headline Verdict (Ship / Don't Ship for manual testing)

**Ship — with one small follow-up that should land before the merchant clicks the link.** Phase 5 has substantively closed the gap from "page looks broken" to "page reads as a competent monthly memo with one directional play and a transparent held-list." The Beauty Brand briefing now has:

- A populated state-of-store paragraph with five facts, including the new `Returning-customer share (L28): 91.5% (6.6% vs prior)` line that previously had no home in the merchant view.
- One Recommended directional card (`First To Second Purchase`, "Emerging" badge, audience=286, why-now grounded in the actual signal).
- Six Considered cards with audience snapshots and would-fire-if rationale.
- Two Watching rows with thresholds.
- A merchant-readable materiality footer ("We only recommend primary plays that could realistically add at least $10,000 this month for a store your size.").
- Forbidden-string contract still holds. No fabricated CIs, no `confidence_score`, no Aura.

The previous review's verdict was "0/10 actionable, 7/10 trustworthy." This is now roughly **5/10 actionable, 7/10 trustworthy** — actionability rose without trust falling. That's the trade-off the contract was designed to enable.

The reason this is *manual testing* shippable rather than *merchant-default* shippable is the gap I detail under "What's Missing For Shippability" — primarily: no $-value anchor on the page, and the Recommended card is missing the channel/sequence/offer/holdout/success-metric block needed for the merchant to actually publish from it. Manual testing with a hands-on operator is fine; default-flip at scale is not yet.

## Is One Play Enough?

**Yes. One good directional play is the right answer for this brand at this calibration stage.** The instinct to say "we should surface more" is the wrong instinct — it's the instinct that produced the legacy fabrication problem.

Concretely:

- The dataset has *one* defensible, sign-stable, high-significance signal: `returning_customer_share` +6.6% across 3 windows. Phase 5 surfaces exactly that. Loosening to surface more would either (a) re-promote `journey_optimization` (template stats, no measurement design) or (b) loosen the directional gate below `consistency >= 2` and `p < 0.05`, both of which break the contract.
- The "1 Recommended + 6 Considered + 2 Watching" ratio is honest about what the engine can defend at this brand's data depth. A merchant reading "we evaluated 7 plays, one cleared the bar this month, here are the six we held and why" is reading a data scientist's monthly memo. That *is* the data-scientist replacement product — not "here are 3 sprints to launch."
- The previous artifact had 0/0/0. This has 1/6/2. The improvement curve is right.

The refinement I would push for is **labeling discipline on the one play**. Today it says "Send a structured first-to-second purchase nudge to single-purchase customers." That's fine. What it does not yet say is "this is an emerging signal, not a calibrated recommendation" — the "Emerging" badge is the only signal of that. I would consider adding a one-line caveat under the recommendation text in directional cards. Not urgent.

## On The "We Need A Revenue Projection" Ask

**Position: Option (c) — add an audience-value surrogate, clearly labeled as reach not lift. Do not add a $ headline. Specifically: "Reachable revenue: 286 customers x $69 AOV = $19,734 if 100% repurchase at AOV. We are not predicting that outcome; this is the addressable size, not the lift."**

I'm rejecting (a), (b), (d), (e). Reasoning, direct:

**(a) Ship as-is with no $ — too austere.** The user's instinct is right. A merchant looking at a card that says "286 people, customers with exactly one historical order" with no dollar context cannot prioritize this against their other monthly work. They cannot tell their CMO "we should do this because." The page becomes a data-scientist artifact again, not a merchant artifact. The vision is "data-scientist replacement" — and a data scientist would put a number on the table, even a hedged one. Refusing all numbers is over-correction.

**(b) Soft range from the existing expert prior in priors.yaml — do not do this.** This is exactly what the DS Architect rejected and what memory.md flags repeatedly. The expert prior was authored with no realization data behind it. Rendering it as a $ range — even hedged — creates a number the merchant will quote back, anchor on, and grade us against next month. This is the legacy fabrication trap with new copy. Do not.

**(c) Audience-value surrogate with reach-not-lift caveat — yes, this.** A "reachable revenue" line is computed from two things the engine already knows (audience size, AOV) and two things it does not pretend to know (response rate, lift). The math is transparent: 286 x $69 = $19,734. The framing is honest: "this is who you can talk to, not what they will spend." It gives the merchant a unit to prioritize against, anchors the play in store-specific scale, and crucially does not require any prior — no fabrication, no relabeling. The receipts already carry both inputs (`audience.size: 286` in the engine_run, `AOV: $69` in state_of_store).

The exact rendered string I would specify: **"Reachable revenue: ~$19,700 (286 customers x $69 AOV). This is your addressable size if every customer placed one order at AOV. It is not a lift forecast — published campaign results will calibrate the realistic share."**

That phrasing satisfies five things at once:
1. Gives the merchant a $ anchor.
2. Is computed from store-observed inputs only.
3. Carries no causal prior.
4. Includes an explicit "not a lift forecast" caveat.
5. Forecloses the "I expected $20K and got $300" gotcha because the framing was never that.

The chip color/style should be visually distinct from a sized range chip — consider a neutral grey "Reach: $19,700" pill, not the blue range chip used for measured plays. This keeps the visual discipline that *actual* sized ranges come from causal priors and *reach* is an audience surrogate.

**(d) Wait for calibrated causal prior — too long, and bad product instinct.** This is the engineer's chosen path and it is correct *as a constraint on what we can call lift*. It is wrong as the answer to "what number goes on the page." The merchant doesn't need lift; they need scale. Reach gives them scale.

**(e) Use legacy expected_$ field — categorically no.** Re-introduces the fabrication. Memory.md, the M0–M9 plan, and the Phase 5 summary all foreclose this. Off the table.

**Why not a sixth option?** I considered "show audience size only and let the merchant compute" (essentially current state). Same problem as (a) — too austere, no anchor. I considered "show projected open/click and infer" — too many assumptions stack up. (c) is the cleanest minimum.

**Caveat on (c):** the moment the engine has *any* causal prior (M9 calibration loop fires), the reach surrogate should be replaced with a real sized range. Reach is a stop-gap, not the destination. A code comment in the renderer noting this is mandatory.

## Recommended Card — Is It Publish-Ready?

**No, not for default-flip. Yes-enough for a hands-on manual tester.**

What's there today:
- Title: "First To Second Purchase".
- Class badge: "Emerging".
- Recommendation: "Send a structured first-to-second purchase nudge to single-purchase customers."
- Why-now: "Returning-customer share moved up 6.6% on L28 with consistent direction across L56/L90 windows. The retention trend supports a measured first-to-second nudge to the single-purchase cohort."
- Audience: 286 people, "customers with exactly one historical order."
- Observed metric line: "returning customer share (direction agrees across 3 windows)."

What's missing vs the original PM ask (channel, sequence, offer ladder, holdout %, success metric, audience CSV path):

- **Channel**: not on the card. A merchant cannot tell from this whether to send email, SMS, or onsite. Default for `first_to_second_purchase` should be email; this should be on the card.
- **Sequence**: not on the card. Default cadence (e.g., "send 7d / 14d / 28d after first order") should be on the card.
- **Offer ladder**: not on the card. Default (e.g., "10% off second order, escalate to 15% if no response after 14d") should be on the card.
- **Holdout %**: not on the card. The contract requires this for measurement. 15% is the legacy default; should be present.
- **Success metric**: not on the card. "Second-order conversion rate within 28 days" is the obvious one.
- **Audience CSV path**: not on the card. Without this, the merchant cannot export the 286 to Klaviyo. This is the most operationally blocking gap.

For a hands-on operator doing manual testing, the why-now + audience definition is enough to reason about whether the recommendation makes sense. They can construct the segment themselves. For a real merchant in default-flip, this is not enough.

The DS Architect's pushback (deferred from the previous review) was that the legacy execution-plan content is template-generated and not bound to evidence. That pushback is valid for the *content* of the offer/sequence — but not for the *structure*. The structure (channel slot, sequence slot, offer slot, holdout slot, success-metric slot, audience CSV slot) is merchant operational data that does not require evidence binding. The default values can be carried in the play registry, not fabricated stats.

**Recommendation**: the smallest follow-up should add channel + audience CSV path + success-metric to the directional card. Sequence and offer ladder can be defaults pulled from the play registry. Holdout % can be a fixed 15% default. None of this requires any new statistical machinery.

## Considered List — Quality Assessment

**Acceptable for shipping; not yet the wow surface it could be.**

The repetition is real and noticeable. Five of six considered cards say verbatim:

> "No measured signal yet for this play at this store; held as targeting until campaign outcomes calibrate the lift."
> "Would fire once the audience can be measured against a valid comparison group."

Reading the cards in sequence, this lands as templated. The variation comes from the audience snapshot (e.g., "Audience: 432 people | last purchase 21-45 days before anchor" vs "Audience: 962 people | customers with discounted orders in last 28 days"), which is genuinely informative and play-specific. So it's not *all* template — but the *reason* and *would_fire_if* lines are.

The user-trust impact is mixed. On the one hand, the repetition tells the merchant honestly: "we don't have a measurement design for any of these yet, that's the same problem across the board." That's a true statement and worth saying. On the other hand, six identical reason lines reads as the engine not having actually thought about each play individually.

**What I'd push for in the next iteration (not blocking ship):**
1. **Differentiate would-fire-if by play.** Winback fires once we see post-campaign return rate. Bestseller-amplify fires once we see a clear top-revenue SKU vs adjacent SKU lift. Discount-hygiene fires once we see margin recovery on full-price audiences. Each play has a *different* future-evidence trigger; today they all say the same thing.
2. **Differentiate reason text by reason code.** `subscription_nudge` already does this correctly — its reason is "Audience is too small to send" with detail "Eligible audience is below the minimum send threshold this run." That's specific. The other five could similarly specialize: e.g., `bestseller_amplify` could say "No SKU shows a clear differential against adjacent SKUs in the relevant window yet." Same reason code, more play-specific copy.
3. **Order matters.** Today the considered list ordering looks arbitrary. Consider ordering by audience size descending, or by "closeness to firing" (which the engine doesn't compute today but could).

Repetition is acceptable for shipping because the alternative is an empty page. But "templated" was one of the things merchants complain about when they say BeaconAI feels like a rules engine. This is a real risk to monitor.

## Watching List — Quality Assessment

**Two defects, neither fully blocking. Fix at least one before default-flip.**

**Defect 1: `returning_customer_share` is not in Watching.** The previous review explicitly asked for it to be there. Phase 5 put it in `state_of_store` instead. That is *a* legitimate home but it is not the *right* home for a load-bearing trend.

The semantic difference matters: state_of_store is "here's what your store looks like right now." Watching is "here's a metric that has moved enough to potentially fire a play next month." `returning_customer_share` at +6.6% L28 with sign-stable direction across L56/L90 is *exactly* the watching-list semantic — it's the load-bearing signal supporting the directional play, and the merchant should see "we are watching this and will tell you if it changes."

**My call: it should be in both.** State_of_store as a fact ("Returning-customer share is 91.5%, up 6.6% vs prior"). Watching as a forward-looking signal ("Returning-customer share moved up. Threshold to act: drops below baseline would re-evaluate retention plays"). The two surfaces serve different merchant questions. Today only one is populated.

**Defect 2: `current` and `prior` are null on both Watching rows.**

```json
"watching": [
  {"metric": "net_sales", "current": null, "prior": null, "trend": "up", "threshold_to_act": "+/- 10% to revisit revenue plays"},
  {"metric": "orders", "current": null, "prior": null, "trend": "flat", "threshold_to_act": "+/- 10% to fire an orders-driven play"}
]
```

The HTML rendering compensates by simply not displaying current/prior values, which is why this isn't visually broken. But the schema contract from the M7 plan was that watching rows carry `current` and `prior`. A future agent or the eventual Klaviyo-publishing agent that reads this JSON will see nulls and not know whether the values are missing because the engine couldn't compute them, or missing because the engine chose not to populate. **This is a real defect.** Net sales is $94,405 and orders is 1374 — both are computed and present in state_of_store. They should be present in watching too.

Severity: blocking for default-flip, not blocking for manual testing (because a manual tester won't read the JSON, only the HTML).

## State Of Store — Quality Assessment

**Five Observations is at the upper edge of acceptable. Borderline-too-dense but defensible.**

The set is:
1. AOV (L28): $69 (1.7% vs prior)
2. Repeat rate (L28): 34.0% (-3.7% vs prior)
3. Returning-customer share (L28): 91.5% (6.6% vs prior)
4. Orders (L28): 1374 (0.0% vs prior)
5. Net sales (L28): $94,405 (1.7% vs prior)

Concerns:

- **Repeat rate (34%) vs returning-customer share (91.5%) confuses non-technical merchants.** These are conceptually distinct metrics (within-window repeat vs cross-period returning), but a merchant reading both will wonder why the numbers look so different. Either we collapse them or we add a clarifying gloss. I'd push for a one-line gloss in the next iteration: "Repeat rate measures customers who placed more than one order *in the L28 window*. Returning-customer share measures customers in the L28 window who had any prior order before the window."
- **Orders flat (0.0%) and net sales up (+1.7%) is an internally inconsistent narrative** — if orders are flat and AOV is up 1.7%, then net sales should be up ~1.7%. Which it is. But the merchant reading "orders flat, net sales up" without the AOV gloss may pause and try to reconcile. The Observation set is internally consistent; it's just that surfacing all 5 forces the merchant to do that reconciliation.
- **The original M1 contract said 3-5 Observations.** Phase 5 relaxed the cap to 7 (per the engineer's note). 5 is still within original spec, but we are now at the upper edge.

For shipping: leave it at 5. For next iteration: consider whether AOV and net sales can be collapsed into a "revenue health" line ("$94,405 / month, up 1.7% — driven by 0% order change, 1.7% AOV change") to reduce the apparent density. Not blocking.

## What's Missing For Shippability

In priority order for default-flip (not for manual testing — manual testing is shippable now):

1. **Reach surrogate ($-value-on-page)** per Option (c) above. Single highest item.
2. **Watching `current`/`prior` populated** for `net_sales` and `orders`.
3. **`returning_customer_share` added to Watching list** alongside its state_of_store presence.
4. **Audience CSV path on the directional card.** Without this the merchant cannot publish.
5. **Channel + holdout % + success-metric on the directional card.** Three default fields from the play registry.
6. **Differentiated would-fire-if copy per play** in the considered list.

Items 1-3 are pre-default-flip. Items 4-5 are pre-Klaviyo-agent. Item 6 is polish.

## Smallest Follow-Up To Ship Default V2

**One tightly-scoped phase, three changes:**

1. **Add a "Reachable revenue" reach chip to the directional card** computed as `audience.size × state_of_store.aov`, rendered as a neutral grey pill with the explicit "not a lift forecast" caveat in the card body. ~30 lines in `storytelling_v2.py`. No new schema field needed if rendered from existing fields; if persisted as a separate field on `PlayCard`, add `reachable_revenue: { value, formula, caveat }` to the schema.

2. **Populate Watching `current`/`prior`** by reading from state_of_store / aligned data. ~10 lines in `decide.py::build_watching`. Add `returning_customer_share` to the Watching list when its move is significant.

3. **Add channel + audience CSV path + holdout % + success-metric defaults** to the play registry, surface them on the directional card. The defaults can be hardcoded in `config/play_registry.yaml` or similar; the renderer reads them. ~50 lines across registry + render. No fabrication risk because these are operational defaults, not statistical claims.

That's the entire follow-up. None of it requires a causal prior, no forbidden strings, no materiality changes, no statistical machinery. The engineer can land this in a focused day or two.

Then flip the default. Beauty Brand will produce a populated, defensible, publishable briefing on the V2 path.

## Open Risks / Things The Engineer Should Know

1. **"Reachable revenue" is the soft underbelly.** If we ship it, merchants will quote it. Even with the caveat, "$19,700" is what they remember. Write the rendered string carefully and consider A/B testing the framing once we have realization data. Specifically: do not let the chip be visually similar to a sized $-range chip. Different color, different label ("Reach" not "Range"), different position.

2. **The directional card today reads "Send a structured first-to-second purchase nudge"** — that copy is generic enough to feel templated on inspection. Once the executable defaults (channel/cadence/offer) land on the card, that genericness goes away. Until then it's a small risk.

3. **`returning_customer_share` is a state statistic, not an intervention effect.** The Phase 5 summary explicitly notes this and the receipts/debug.html documents it. The risk is that a future agent — possibly a future ML training loop reading `recommended_history.json` — treats the `observed_effect=0.066` as a measured lift. The forcing function in `measurement_builder._SupportingSignal.rationale` is the only thing preventing this. Worth a code comment at the top of `measurement_builder.py` flagging this.

4. **One play is the right answer for *this* dataset, but the engine should produce 0–3.** Phase 5 happens to produce 1 because the data has one signal. If the next dataset has 0 directional signals, we go back to ABSTAIN_SOFT. The merchant will need that to land gracefully. Phase 5's ABSTAIN_SOFT copy + populated considered list is probably enough — but the manual test should include at least one fixture that hits ABSTAIN_SOFT to confirm.

5. **The Phase 5.7 `journey_optimization` suppression is on the V2 path only.** Memory.md and the Phase 5 summary both flag this. If anyone flips the default before deleting `journey_optimization` from the legacy emitter (M10 work), and there's a bug in the V2 wiring, the saturated stats could leak. The V2 filter is a defense-in-depth, not a fix. M10 cleanup needs to actually delete the legacy emitter for `journey_optimization`.

6. **The state_of_store cap is now 7 in code but the M1 contract docstring still says 3-5.** Documentation drift. Worth a comment-only PR to sync.

7. **"Data scientist replacement" positioning compatibility** — addressed directly: yes, this is compatible. A real data scientist's monthly memo on a healthy brand looks like this — one play with a clear hypothesis, six things they considered and held, two trends to watch. The risk is that a non-technical merchant reads "one play this month" as "the engine didn't do much." That's a copy-and-positioning problem, not a content problem. The first state-of-store paragraph and the considered list are doing the work of showing the merchant the engine is reasoning. As long as they read those, the positioning holds. If they only read the recommendation header and decide based on count, we have a UX problem.

## 5-Bullet Summary For Orchestrator

- **Ship for manual testing now. Defer default-flip until one small follow-up lands.** The Phase 5 Beauty Brand briefing is a real, defensible, useful artifact — a populated state-of-store, one Emerging directional play with grounded why-now, six honest held cards, two watching rows, merchant-readable copy, zero fabrication. This is a step-change improvement over the M0-M9 baseline (0/0/0 -> 1/6/2).

- **On the user's revenue-projection ask: pick Option (c) — add a reach surrogate, not a lift estimate.** Render "Reachable revenue: ~$19,700 (286 customers x $69 AOV)" with an explicit "not a lift forecast" caveat. Computed from store-observed inputs only, no causal prior required, no fabrication. Reject the legacy expected_$ option (e), reject the expert-prior soft range (b), reject ship-with-no-$ (a). The merchant needs an anchor; reach gives one without lying.

- **One play is the right answer for this brand at this calibration depth.** Loosening to surface more would re-import the legacy fabrication pattern. The right product move is to make the *one* play more publish-ready (channel, audience CSV path, holdout %, success metric on the card) rather than to surface a second one with thinner evidence.

- **Two real defects to fix pre-default-flip.** (1) Watching rows have `current`/`prior` as null in the JSON despite the values being present in state_of_store. (2) `returning_customer_share` belongs in Watching as well as state_of_store — it's the load-bearing signal supporting the recommendation, and Watching is where forward-looking trends live.

- **The smallest follow-up is three concrete changes**: reach chip on the directional card, Watching schema populated, play-registry defaults (channel / CSV path / holdout / success metric) surfaced on the directional card. None requires a causal prior, none breaks the forbidden-string contract, none touches materiality. After that lands, flip `ENGINE_V2_OUTPUT=true` as default and the Beauty Brand fixture becomes the canonical "this is what BeaconAI looks like" sample.
