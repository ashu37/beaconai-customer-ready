## First Impressions

Reading top-to-bottom in 60 seconds, this feels like a recommendation document, not an analytics dump. The flow lands cleanly: a one-sentence state of store, then "Recommended" with one specific play, then two experiments, a small Watching note, and what was held. I can act in 60 seconds — the directional play tells me to send a second-purchase nudge to ~5,560 single-purchase customers, and "What we'd send" gives me enough to forward to a marketing manager.

But the very first thing that catches my eye negatively is the **State of Store one-liner**. It buries the headline. "Repeat rate (L28): 9.0% (102.3% vs prior)" reads as a 102% growth, when it actually means 102.3% of prior (i.e., ~+2%). I had to re-read it. That is the first question I'd ask: "Wait, did my repeat rate double?"

Second question I'd ask: "Why is the Recommended Now play telling me to nudge one-and-done buyers when the State-of-Store says returning-customer share is already up 11.5%? Aren't I already winning that?" The card answers it (the trend supports doubling down), but it took thinking.

Verdict on first impressions: it feels like a product, not a dashboard. But the State-of-Store line is doing damage at the top.

## C1 Review — What We'd Send

Three "What we'd send" lines render. Let me grade each.

1. `first_to_second_purchase`: **"Email one-time buyers a value-led second-purchase nudge with best-next-product education, two sends one week apart, no blanket discount."** This is excellent. Audience, channel, posture, cadence, discount stance. I would forward this to my email manager as-is. 9/10.

2. `discount_hygiene`: **"Email a 10% off code to discount-prone buyers; track redemption rate."** This is wrong on multiple levels.
   - **It directly contradicts the play's name.** The play is now titled "Discount-dependence cleanup" (C3). A founder reads "we want to cleanup my discount dependence by sending another 10% off code"? That is incoherent.
   - "Track redemption rate" is a measurement instruction, not what we'd send. The "We will measure" line below already covers measurement.
   - The original `discount_hygiene` thesis (per the C1 plan example) was suppression — withhold codes, send full-price reminders. Sending a 10% off code is the opposite intervention.
   - This is a content bug in `priors.yaml`, not a render bug, but it surfaces here. **Must fix before beta.**

3. `bestseller_amplify`: **"Email a curated bundle of the hero SKU plus complementary products to recent buyers; track basket attach."** Good audience + channel + posture. "Track basket attach" is again a measurement statement that overlaps with the measured-by line below. 7/10 — fine to ship, would tighten in v2.

Honesty check: no projected lift, no causal "will lift", no specific dollar offer outside the broken `discount_hygiene` string. Length is right (15–35 words for the good one; the other two run short). The label "What we'd send:" reads naturally.

The bigger structural concern: the directional and experiment cards now have BOTH a "What we'd send" line and a "We will measure ___ in N days" line. On a `discount_hygiene` card the measurement is implied twice ("track redemption rate" and "We will measure email-attributed revenue in 7 days"). The two lines need to stay in their lanes — the mechanism string should be **what to send**, full stop.

## C2 Review — Section Order

Recommended Now → Recommended Experiment → Watching → Considered → DQ footer.

Reading order feels right: do this → test this → watch this → here's what we held. Watching before Considered does work, but barely — because the Watching section in this fixture is a single line ("aov ↓ down, threshold ±5%") with no merchant action attached, it is genuinely closer to filler than to a forward-looking signal. So the narrative is "do → test → here's a chart-ish nubbin → here's what we held." The order is correct; the **content of Watching** is what makes this transition feel weak, not the order itself. Order: ship as-is.

## C3 Review — Display Names

Going through the seven cards:

- "Second-purchase nudge for one-and-done buyers" — excellent. Audience + action.
- "Discount-dependence cleanup" — good intent, but as noted above it contradicts the mechanism line. Title is fine; mechanism must change.
- "Top-product re-targeting" — good, scannable.
- "Lapsed-buyer reactivation (3–6 weeks since last order)" — excellent. The parenthetical is the right kind of specificity.
- "Subscribe-and-save invitation for repeat buyers" — good.
- "Complete-the-routine bundle" — good, evocative.
- "Replenishment timing" — slightly bare. "Replenishment reminder" or "Replenishment timing nudge" reads more like an action. Minor.

No title is technical or confusing. None reads "the engineer wrote this." The ones in Considered are particularly important because the founder sees four held plays and now actually understands what each was. Big upgrade. **C3 is the strongest of the four tickets.**

One concern: "At-risk repeat-buyer rescue" appears as both the new `retention_mastery` display_name AND the new `at_risk_repeat_buyer_rescue` display_name. Two distinct play_ids with identical merchant-facing titles will be confusing the moment both fire on the same brief. Not visible in this fixture, but a beta-blocking collision waiting to happen.

## C4 Review — Watching Section

C4 fallback does not fire here — confirmed. The Beauty fixture has 1 AOV row.

Is the AOV row useful? Marginally. **"aov ↓ down. Threshold to act: +/- 5% to fire an AOV play."** This tells me AOV moved down but not enough to act. As a founder, that is genuinely useful framing — the engine is showing me what it is monitoring and what it would take to escalate. I'd give it a 6/10.

What is missing: a magnitude. State-of-Store at the top says AOV moved -0.2% on L28. The Watching row says "down." If it is down 0.2%, I don't care; if it is down 4.8% and a hair from firing, I care a lot. The Watching row should state the actual delta.

Watching as a section feels live, not placeholder, but only just. C4's fallback is the right safety net for the empty case; it would still benefit from a Phase 6C upgrade where Watching rows carry magnitude.

## Trust Check

Forbidden-token sweep on the rendered HTML:

- `predicted` — absent.
- `projected` — only inside the disclaimer string "This is not projected lift" (allowlisted, correct).
- `expected lift` / `forecast` / `calibrated` — absent.
- `p =` / `confidence score` / `uplift` / `ATE` / `ITT` / `treatment effect` — absent.

Dollar amounts present:
- `$59 recent AOV (L28)` — clearly labeled as observed.
- `about $329.0k addressable order value` (Recommended Now) and `$133.2k`, `$87.3k` (Experiments) — these are the opportunity-context lines. The disclaimer immediately below is doing real work: "This is not projected lift; it shows the size of the audience if the play converts." Good. **However**, "$329.0k addressable order value" on a Recommended Now card for a store at ~$148k/month MRR is going to be misread. The audience × AOV math (5,560 × $59 = $329k) is mathematically honest but it presents a number 2.2x the store's monthly revenue as if it were addressable. A founder will fixate on it. The disclaimer mitigates but does not neutralize. This is the single biggest trust risk on this page.
- `$148,451` monthly revenue estimate in the DQ footer — fine, neutral framing.

"Run as experiment" label on experiment cards — correctly framed as a test, not a guaranteed outcome.

## Top-5 Founder Feedback

**1. MUST FIX — `discount_hygiene` mechanism string contradicts the play.**
Card title: "Discount-dependence cleanup". Mechanism: "Email a 10% off code to discount-prone buyers; track redemption rate." This is internally inconsistent. The mechanism in `config/priors.yaml` for `discount_hygiene` must be rewritten to suppression posture (e.g., "Suppress discount codes from this segment for 14 days; send a full-price, value-led reminder of the last item viewed; no urgency framing"). Blocks trust. Beta blocker.

**2. MUST FIX — State-of-Store percentage framing.**
"Repeat rate (L28): 9.0% (102.3% vs prior)" reads as +102% growth. Should be "(+2.3% vs prior)" or "(unchanged vs prior)". This is the first thing on the page and the first thing that confuses. Render-layer fix; not in C1–C4 scope but found while doing the C1–C4 review. Beta blocker.

**3. SHOULD FIX — Opportunity context dollar amount on Recommended Now is misreadable.**
"about $329.0k addressable order value" on a $148k/month store is going to be misread as forecasted revenue regardless of the disclaimer. Either (a) cap displayed addressable value at some multiple of MRR, (b) reframe as "audience × AOV" without the $-styled bold, or (c) drop the dollarized line on Recommended Now and keep it only on Experiment cards where the "test, don't trust" frame is already loaded. Should fix.

**4. SHOULD FIX — Display-name collision between `retention_mastery` and `at_risk_repeat_buyer_rescue`.**
Both now resolve to "At-risk repeat-buyer rescue." Distinct play_ids, identical titles. Not visible in this fixture but will fire on the next brief that surfaces both. One must be retitled. Should fix.

**5. SHOULD FIX — `discount_hygiene` and `bestseller_amplify` mechanism strings include measurement instructions.**
"...track redemption rate" and "...track basket attach" duplicate the `<p class="play-card__measured-by">` line below. Mechanism = what we'd send. Drop the trailing "track X" clause from both YAML strings. Should fix.

Nice-to-have: Watching row should carry actual magnitude (-0.2%, -4.8%) not just direction. Replenishment timing could read "Replenishment reminder for likely-empty buyers". The "What we'd send" line on `first_to_second_purchase` is the gold standard — match it for the other plays.

## Verdict

**NOT READY for external merchant beta.**

Blockers:
1. `discount_hygiene` mechanism string contradicts its own card title — a paying merchant who reads "Discount-dependence cleanup" followed by "Email a 10% off code" will lose trust on the spot.
2. State-of-Store "(102.3% vs prior)" framing is read as growth, not ratio. First number on the page, miscommunicated.

Both are content/render fixes, not engine work. Both can land in a small follow-up before beta. The C1–C4 render layer itself is sound: section order is right, display names are a major upgrade, the mechanism surface is the right idea, and trust contract holds (no predicted lift, experiments correctly framed). Once the two blockers are fixed and the priors.yaml content for `discount_hygiene` and `bestseller_amplify` is tightened, this is **READY with caveats** — the caveats being the addressable-dollar misreadability on Recommended Now and the duplicate display-name on `retention_mastery` / `at_risk_repeat_buyer_rescue`.

A founder paying $500/month: the page is 80% there. The 20% gap is two specific strings, not architecture. Ship the fixes serially; do not bundle. Do not take this to external beta this week.
