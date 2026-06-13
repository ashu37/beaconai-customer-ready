# Phase 6A — Product Final Review (PM)

## Verdict
**Accepted.** Ship to founder/manual testing.

If a Shopify founder opened this Beauty Brand briefing tomorrow, they would understand what to do, what we're testing, and what we're holding back — without us having to walk them through it. That is the bar Phase 6A had to clear and it clears it.

## Beauty Brand Slate — merchant read

Reading `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` cold, as a founder:

- **State of Store** lands as a one-line health check. Repeat rate 9.0%, returning-customer share up 11.5% — concrete, scannable, no jargon.
- **Recommended Now** has one card (`first_to_second_purchase`, 5,560 people, ~$329k addressable) with a clear "Why now" tied to the retention trend. The "not projected lift" disclaimer reads naturally as a footnote, not a legal hedge. This is the most merchant-credible single card we've produced.
- **Recommended Experiment** has two cards (`discount_hygiene` 2,251 people / ~$133k; `bestseller_amplify` 1,475 / ~$87k), each with an explicit "We will measure ___ in N days" line. This is the section that finally makes the engine feel like a teammate rather than a dashboard.
- **Considered (4 cards)** explains the held plays in one sentence each with a "Would fire if" — this is the section that previously embarrassed the product and now reads as discipline.
- **Watching** is one row (AOV trend) at the bottom.

Net read: a healthy brand gets 3 things to do/test, 4 things explained-but-held, and 1 thing being watched. That's the right ratio. It does not feel like an analytics tool; it feels like a recommendation.

## Section differentiation

Yes, clearly differentiated. Each section has distinct visual treatment (solid green border for measured/directional, dashed grey for experiment, muted grey for rejected, simple list for watching), distinct copy registers ("Run this", "Run as experiment", "Why held", "Threshold to act"), and distinct economic context rules. The role-uniqueness invariant from B4 plus the B6 e2e test mean a play cannot smear across two roles — that's what protects the differentiation from drifting in future runs.

**One caveat on rendered ordering.** The ticket B1 summary records the actual DOM order as: state-of-store → Recommended Now → Recommended Experiment → **Considered → Watching** → DQ-footer. The contract specified Recommended Now → Recommended Experiment → **Watching → Considered**. The rendered fixture confirms Considered appears before Watching. This inverts the merchant-attention pyramid (act → test → monitor → explain-the-rejects) and puts the muted "what we held back" block ahead of the load-bearing "what we're watching" track. Not a blocker for founder testing, but I'd flip it before any external merchant beta. Carry forward.

## Recommended Experiment framing

Commercially compelling without overclaiming. The "Run as experiment" badge plus the literal "We will measure email-attributed revenue in 7 days" / "We will measure repeat purchase in 30 days" gives the merchant a contract: send-to-N, measure-this-metric, learn. The opportunity-context block ("about $133.2k addressable order value") gives commercial weight; the disclaimer ("This is not projected lift; it shows the size of the audience if the play converts") prevents it from reading as a forecast.

The B2 forbidden-token sweep plus the B6 pinned per-card framing checks (Run as experiment badge / measured-by line / opportunity-context block / disclaimer present, all 4 checks per card) lock this contract structurally. Hard to weaken accidentally.

What's missing — not blocking — is the merchant-readable `mechanism` string from priors metadata. We loaded it (Ticket A3) but I do not see it surfaced on the rendered card. The merchant gets the audience and the measurement metric but not the one-line "what the email actually does." First founder will likely ask. Carry forward.

## First-ship experiment choices

`discount_hygiene` and `bestseller_amplify` are the right two. Both have clean, intuitively-true mechanisms (target discount-prone buyers with a 10% code; promote the hero SKU to recent buyers). Both have audiences in the 1.5k–2.3k range on Beauty Brand — non-trivial but not overwhelming. Both have unambiguous outcome metrics. Critically, neither requires a causal prior to be defensible because we ship them as "send and measure," not as "we predict X% lift."

The deliberate exclusions (`winback_21_45`, `routine_builder`, `subscription_nudge`) are correct: those plays' merits depend on calibration we don't have and on cohort definitions that need a recently-run-fatigue gate the outcome log doesn't yet provide. Holding them in Considered with `no_measured_signal` is honest.

## Considered section clarity

Materially less confusing than the pre-6A baseline. The post-experiment-promotion considered-filter from Ticket B6 (line ~1560 in `decide.py`) is the load-bearing fix: `discount_hygiene` and `bestseller_amplify` no longer appear in BOTH Considered (`no_measured_signal`) and Recommended Experiment in the same run. In the rendered fixture, Considered now contains only the four genuinely-held plays, each with a distinct "Why held" reason (`no_measured_signal` x3 plus `audience_too_small` x1) and an audience snapshot.

Three of the four still resolve to `no_measured_signal`. That's still slightly repetitive (PM caveat 3 from baseline acceptance), but the differentiation by audience size and segment definition reads acceptably to a founder. Improvement over baseline: clearly yes. Solved: not entirely.

## Manual/founder testing readiness

Ship-ready. Specifically:
- Healthy-brand fixture produces a 3-2-1-4 slate that a founder can read in under 60 seconds and act on.
- ABSTAIN_SOFT (B3) collapses both Recommended sections to zero, with held experiments routed to Considered with the typed `TARGETING_HELD_UNDER_ABSTAIN` reason — small/cold-start stores will not get false confidence.
- Role-uniqueness invariant (B4) plus the B6 PUBLISH-branch considered-filter mean the "same play in two places" failure mode is structurally closed.
- Forbidden-token sweep (B2) plus the no-dollar-headline invariant on experiment cards mean a founder will not see "expected lift," "projected lift," "calibrated," or any of the seven new banned phrases.
- The pinned slate fixture (B6, 19 tests) means future ticket churn cannot silently regress this exact merchant view.

What I would not do yet: external merchant beta. Founder testing only. Reasons in the next section.

## Product caveats to carry forward

1. **Section ordering inversion (Considered before Watching).** Real merchant ordering should be Recommended Now → Recommended Experiment → Watching → Considered. Current render places Considered above Watching. Cheap fix; do before external beta.

2. **`mechanism` is loaded but not surfaced on the card.** The one-line merchant-readable mechanism string is the missing piece between "audience size" and "measurement metric." Founders will ask "what's the actual email/campaign?" Add to the card body before external beta.

3. **Considered repetition still partially there.** Three of four held cards say `no_measured_signal` with effectively identical copy. Audience snapshot differentiates them, but a future Considered-copy refresh that varies the "Why held" detail per audience type would help. Defer.

4. **`revenue_range` is suppressed everywhere; opportunity-context is the only economic anchor.** The "$329k addressable" framing is doing all the commercial heavy lifting on the directional card and both experiments. This is correct given we have no causal priors. Founders WILL ask "what's the dollar value if this works." We need a defensible answer that's not "we won't say." Phase 6B+ requires the outcome log to unlock realized lift; until then, the disclaimer copy must hold the line.

5. **Beauty Brand fixture is single-vertical.** The pinned slate row is one vertical, one health profile. We have not regression-pinned `small_store_240d`, `cold_start_45d`, supplements, or low-inventory variants at the same slate-row granularity. Founder testing on multiple stores will surface where the row shape isn't this clean.

6. **Recently-run-fatigue is a structural NO-OP.** A founder running the engine repeatedly within 14 days will see the same experiments re-recommended. Mitigate with a manual cadence in founder-testing instructions, then unblock with the M9 outcome log.

7. **AnomalousWindow auto-registration deferred.** A promo-window store will publish 1 directional + 2 experiment cards instead of abstaining. Documented Phase 6B work; do not run founder testing on a store with a known recent promo spike without flagging it first.

## Blockers

**None.** The B-series invariant tests (B2, B3, B4, B5, B6) plus the role-uniqueness assertion close the failure modes that would have embarrassed us in front of a merchant. The deferrals listed in the input (inventory loader, `empty_bottle` parser, AnomalousWindow, lifecycle, recommended_history fatigue, revenue_range unsuppression) are correctly out of scope and do not gate founder testing.
