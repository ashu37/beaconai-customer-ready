# Founder-Style Phase 6A Review — BeaconAI Action Briefing

_Reviewer: product-strategy-pm agent, in founder voice_
_Date: 2026-05-05_
_Scope: Phase 6A Engine V2 slate (commit 585480e), founder testing tier_
_Inputs reviewed: phase6a-final-review.md; healthy_beauty_240d, small_store_240d, cold_start_45d briefings_

---

## 1. Founder-style verdict

I'd pay **$300/month** for what I'm seeing. Not $500. Not $1,000. The healthy_beauty briefing reads like a thoughtful intern's first-pass list — three things to consider, with honest framing — but it stops one inch short of being something I can hand to my marketing manager Monday morning. The small_store briefing is borderline insulting at the $500+ tier: I get six grey "we couldn't tell" cards and an empty Watching list, and the engine charges me to tell me it's stumped. The cold_start memo is fine for what it is but it's a refund event, not a value event.

Conditional path to $500–$1,000/month: (a) every Recommended Experiment card has to tell me the **actual campaign** (subject line angle, segment, send window, success bar), (b) the abstain/small-store path needs to deliver *something* directional or diagnostic instead of a wall of identical "no measured signal" cards, and (c) the Considered list needs to stop sounding like the same sentence on autoplay. Until those three things, this is a $300 tool wearing a $1,000 jacket.

---

## 2. Per-scenario assessment

### 2a. healthy_beauty_240d (the happy path)

**1. Useful?** Mostly yes. The single Recommended card (`First To Second Purchase`, 5,560 people, ~$329k addressable, "Returning-customer share moved up 11.5%") is the kind of thing I'd plan a campaign around. The two experiment cards point me at the right audiences. So yes, I'd use it.

**2. Actionable?** Half. The primary card has a clear audience definition ("customers with exactly one historical order") that any marketing manager can build in Klaviyo. But "Send a structured first-to-second purchase nudge" is not a campaign — it's a brief for a brief. What's the offer? Discount, no discount? One email, three? Subject line angle? Same problem on the experiments: "Discount Hygiene" with audience "customers with discounted orders in last 28 days" — am I *suppressing* discounts from them, or *targeting* them? I literally can't tell from the card.

**3. Trustworthy?** Yes, and this is the strongest part. "**direction agrees across 3 windows**", "This is not projected lift; it shows the size of the audience if the play converts", "We will measure email-attributed revenue in 7 days" — that language earns trust. No fake p-values, no "predicted 14.3% lift" garbage. Honest engine. I believe it.

**4. Specific enough?** The audience math is specific. The play *content* is generic. "Bestseller Amplify" — amplify how? Email blast, paid social, on-site banner? "Discount Hygiene" — what does hygiene even mean to a non-analyst founder? These names sound like internal play codes leaked into the customer surface.

**5. Would I know what to do next?** I'd know who to email. I would *not* know what to send. That's a 50% answer.

**6. Pay $500–$1,000/month?** For a healthy brand, $300–$500. Not $1,000.

**7. Hesitations?** (a) Only **one** primary play for a $148k/mo store with 5,560 single-purchase customers feels thin — am I really only allowed one bet? (b) The play names are insidery. (c) The $329k "addressable" number is impressive but the disclaimer immediately neuters it; sophisticated founders will ask "what realistic capture rate do you assume?" and there's no answer. (d) Watching has exactly one row (AOV) — feels like the engine isn't paying attention to enough things.

**8. Smallest improvement?** Add a **"What we'd send" line** to every Recommended and Recommended Experiment card. Two sentences. Audience + suggested angle + offer posture (discount-led / value-led / urgency / education) + first send-window. That alone moves this from $300 to $600.

### 2b. small_store_240d (ABSTAIN_SOFT)

**1. Useful?** No. Six identical-looking "No measured signal cleared the threshold yet" cards plus an empty Watching list reads as: *the engine couldn't think of anything*. The state-of-store header tells me Orders are at 59.9% of prior — that's a five-alarm fire — and the response is silence and a politely worded surrender.

**2. Actionable?** Zero. There's literally nothing to do. The page tells me what *would* fire ("once the audience can be measured against a valid comparison group") but not what I should do *this month* with the $13k store I actually run.

**3. Trustworthy?** This is the cruel part: it's *more* trustworthy than the healthy briefing because it refuses to fake a recommendation. But trust without value is just honesty about being useless. I'll cancel after two of these in a row.

**4. Specific enough?** No. Five of six Considered cards say verbatim: *"No measured signal yet for this play at this store; held as targeting until campaign outcomes calibrate the lift."* That's not six rejections — that's one rejection rendered six times. The audience snapshots (135 / 234 / 241 / 0 / 0 / 0) would let me distinguish "you're too small" from "you have no buyers" from "this isn't your store's pattern" — but the copy doesn't.

**5. Would I know what to do next?** No. The empty Watching section closes the door. There's no "here's what to focus on while the engine warms up" — no diagnostic narrative, no "your repeat rate dropped to 8.2% (-15%); here's what we'd watch."

**6. Pay $500–$1,000/month?** No. I'd cancel after the second one of these.

**7. Hesitations?** Orders down 40%, repeat rate down 15%, and the engine has nothing to say. The "State of store" header has *more business insight* than the entire rest of the briefing combined. That's an inversion of value. The empty Watching block is the worst single moment in any of the three documents — empty Watching on a store that's clearly bleeding is a product failure, not a data-quality outcome.

**8. Smallest improvement?** Two things: (a) Group the Considered list by *reason cluster* with one explanatory paragraph per cluster ("Three plays held because we haven't seen outcomes yet from your store; one held because the audience is too small"), and (b) **never let Watching be empty** for a store with 240 days of history — the descriptive trend stats already in State of Store can populate it.

### 2c. cold_start_45d (ABSTAIN_HARD)

**1. Useful?** As a notice, yes. As a briefing, no. It's a one-page apology framed as a "Data quality memo."

**2. Actionable?** The guidance ("confirm the analysis window is not contaminated by promotions, refunds, or test orders, and that the store has at least 90 days of clean order history") is technically actionable but reads like a support-ticket reply, not a recommendation.

**3. Trustworthy?** Yes. Refusing to recommend on insufficient history is the right call, and saying so plainly is the right framing.

**4. Specific enough?** The flag (`insufficient_clean_history`) is specific. The path forward is generic — "wait 90 days" is true but not differentiated.

**5. Would I know what to do next?** Wait. That's it.

**6. Pay $500–$1,000/month?** The whole question for an abstain page is: *do I feel like I just paid for nothing?* Right now: yes, a little. There's a billing-vs-value mismatch.

**7. Hesitations?** State of Store shows AOV $59, repeat rate 17.5%, 1,877 orders. That's a lot of life in the data. The page contradicts itself: the header says "the engine paused" but the State of Store paragraph is full of measurements. Pick a register.

**8. Smallest improvement?** Make the abstain page a **"first 90 days" plan** — not analytics, but a structured onboarding briefing: "Here are the three retention plays every Shopify store should set up while we wait for your data to warm up." Convert this from a refund event into a setup-work event. Cost almost nothing because these are static templates; restores the founder's perception of "I got something this month."

---

## 3. What feels valuable

- **The honesty register.** "direction agrees across 3 windows", "we will measure repeat purchase in 30 days", "this is not projected lift" — this is the part of the product I'd point to in a pitch. No fake stats. No "predicted lift 14.3%." That's rare and worth real money.
- **The 1 / 2 / 1 / 4 ratio on the healthy path.** Three things to do/test, one to watch, four explained-away. That ratio reads like a teammate's recommendation, not a dashboard. This is the structural win of Phase 6A.
- **Audience size + audience definition together.** "5,560 people | customers with exactly one historical order" is concrete enough that a marketing manager can build the segment. Right level of specificity.
- **The opportunity-context disclaimer.** It's the disclaimer that *makes* the $329k number usable. Without the disclaimer, that number is bullshit. With it, it's a directional sizing.
- **The directional/experiment/measured visual hierarchy.** Border colors and badges (Emerging / Run as experiment) genuinely help me triage which card to take seriously.
- **The data-quality footer**, specifically the line "We only recommend primary plays that could realistically add at least $10,000 this month for a store your size." That sentence does more for trust than any p-value would.

---

## 4. What feels weak

- **The Considered list is one rejection on autoplay.** In the healthy briefing, 3 of 4 say "No measured signal yet for this play at this store; held as targeting until campaign outcomes calibrate the lift." In small_store, 5 of 6 say it. Repetition this dense reads like a template, and template-y is the death zone for "this is a data scientist replacement."
- **No "what to actually send."** Every experiment card tells me the audience and the success metric and stops. A founder will ask, every single time: *"OK, but what's the email?"* The Phase 6A review caveat #2 anticipates this; I confirm it as the #1 founder gap.
- **Section ordering.** Considered (rejected) before Watching (forward-looking) puts the past tense before the future tense. As a founder, after I read what I'm doing, I want to know what's *coming* next, not relitigate what didn't qualify. Watching should sit second; Considered should be the back-of-the-magazine appendix.
- **Empty Watching is an active disservice.** Small_store renders `<p class="section__empty">No deterministic signals to watch this run.</p>` — for a store whose Orders are at 59.9% of prior. That's a product failure dressed up as honesty.
- **Play names leak internal taxonomy.** "Discount Hygiene", "Bestseller Amplify", "Empty Bottle", "Routine Builder", "Winback 21 45" — these read like analyst codes, not customer-facing recommendations. "Winback 21 45" is the worst offender; that's not a play name, that's a column header.
- **The abstain pages bill at the same tier as the recommendation pages.** Without a perceived-value floor on abstain runs, this is a churn driver.
- **"Recommendation" with N=1 on a healthy mid-market brand feels structurally thin.** A $148k/mo beauty store with 5,560 single-purchase customers should plausibly support 2 primary plays, not just one. The cap of 3/2/4/6 is the right shape, but the engine being conservative in the *direction of fewer recommendations* is the hardest tradeoff against price-to-value.
- **The `mechanism` string is loaded but not surfaced** (final review caveat #2). The engine *has* a merchant-readable mechanism per play and chooses not to render it. That's leaving the load-bearing piece on the floor.

---

## 5. Top 5 Phase 6B product priorities

1. **Surface a "What we'd send" / mechanism line on every Recommended and Recommended Experiment card.** Closes the largest single founder gap from section 4. The data already exists per Phase 6A caveat #2 — this is a render-layer surfacing decision, not a new build. Single biggest ARPU lever.
2. **Considered-list quality refresh: typed, differentiated reasons.** Replace the single "no measured signal" sentence with at minimum 4 distinct reason buckets that explain *why this store, this month* — e.g., "audience too small for your store size", "no outcome history yet for this play type", "trend not yet directional", "audience overlaps with primary play". Turns 6 identical cards into one informative cluster. Directly attacks the "template-y / generic" perception.
3. **Reorder sections: Recommended → Recommended Experiment → Watching → Considered.** Free win, founder-mental-model alignment. The final review already lists this as caveat #1; I confirm it from the founder seat. Watching is forward-looking; Considered is rejected; rejected goes last.
4. **Never-empty Watching for stores with sufficient history; abstain pages get a "starter play" track.** When the engine has nothing measured to recommend, populate Watching with the descriptive trends already computed in State of Store, and on hard-abstain serve a small-but-real onboarding-plays template so the page never feels like a refund event. This is the small_store / cold_start fix.
5. **Audit and rename the customer-facing play taxonomy.** "Winback 21 45" → "Lapsed-buyer reactivation (3–6 weeks since last order)". "Bestseller Amplify" → "Top-product re-targeting". "Empty Bottle" → "Replenishment timing". Internal codes can persist in `data-play-id` for engineering; the `<h3>` should read like a marketing manager wrote it. Cheap, visible, lifts perceived sophistication.

---

## 6. What NOT to build yet

- **Klaviyo / Shopify direct-publish integrations.** Premature. The recommendation surface isn't crisp enough yet to trust auto-publishing. Fix what's on the page before plumbing it to a sender.
- **Outcome-log / `would_be_measured_by` real measurement wiring.** Final review caveat #12 flags this. It's the right long-term move but it depends on (a) segment AOV, (b) control-group definition, (c) Klaviyo attribution. Don't start it before priorities 1–5 land — the engine needs to be worth measuring before measurement gets built.
- **Per-segment AOV for opportunity context.** Caveat #4. The store-wide L28 AOV with the disclaimer is good enough for now. Deferring this does not erode trust at the founder testing tier.
- **Calibrated lift / projected revenue on experiment cards.** This would *destroy* the trust win Phase 6A just shipped. Do not let any future spec sneak this in to make experiment cards "feel more concrete." The honesty is the moat.
- **More play archetypes.** The current 6–8 play library is roughly the right surface area. Adding more plays before Considered-list quality and "what we'd send" land just multiplies the volume of grey rejection cards.
- **AnomalousWindow auto-registration** is on the final review's Phase 6B list (caveat #3) and *should* be there from a trust-during-promo standpoint, but as a founder reviewing the three non-promo scenarios I'm seeing, it's not the founder-perceived gap — it's an integrity-of-engine gap. Build it, but don't sequence it ahead of priorities 1–4 above; sequence it parallel to them.
- **A/B test scaffolding inside the briefing** ("split this audience 50/50"). Fancy and tempting; structurally premature. Until the engine can measure outcomes (post #2-not-yet item above), proposing splits is theater.
- **A "score" or "confidence" number per card.** The current evidence_class badges (Emerging / Run as experiment / Measured) are doing the right job. A numeric score is one regression away from the fake-stats territory the engine just spent six tickets escaping.

---

## Source files referenced

- `agent_outputs/phase6a-final-review.md`
- `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`
- `agent_outputs/synthetic_fixes_8_11_samples/small_store_240d_briefing.html`
- `agent_outputs/synthetic_fixes_8_11_samples/cold_start_45d_briefing.html`
