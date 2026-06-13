# DS Architect Response — Phase 5 Beauty Brand Sample

## Scientific Verdict (Ship / Hold)

**Ship the card. Hold the dollar number. Suppression is correct, and "Emerging" with no $ is the only honest renderable state for this evidence today.**

The Phase 5 wiring did the right thing on the hardest call: the engineer refused to feed a state statistic (`returning_customer_share`) into the sizer as if it were an intervention effect. That single act of restraint is what separates this output from the legacy `journey_optimization` fabrication. The card is shippable as a directional/Emerging surface; a $ range is not.

The card has *one* defect that should block ship as-is: `measurement.n=962` is the wrong denominator for the claim being implied. Fix that field, and the card is honest. Everything else is acceptable.

## Is `revenue_range.suppressed=true` Correct?

**Yes. Unambiguously yes.**

First-principles reasoning. `returning_customer_share` is a cohort *composition* statistic: of customers active in window W, what fraction had any prior order before W. A move from 84.9% to 91.5% can be produced by any of:

1. The numerator growing (more reactivation among prior customers) — what the play actually targets.
2. The denominator shrinking (fewer new customers acquired, so the same returners are a larger share of a smaller pool) — what frequently drives this metric in practice on a flat-orders month.
3. A shift in identification rate (more orders carrying customer IDs).
4. A cohort-definition seam (customers whose first-ever order falls just outside the window edge).

A `revenue_range` would imply a counterfactual claim: "if we send this play to the 286 single-purchase audience, we expect $X–$Y of incremental revenue." None of the four mechanisms above support that claim. The +6.6% delta is consistent with `orders` being flat (0.0%) and `repeat_rate_within_window` being *down* 3.7% — i.e. the share moved largely because the new-customer side of the ratio softened, not because returners surged. That is the opposite of evidence for a first-to-second nudge having lift.

**Translation rule the engine should hold to:** a state statistic on a cohort cannot be sized without a measurement design that maps the state-statistic delta to an audience-level intervention effect. No such mapping exists at this store. Suppression is the correct call.

What would have to change before $ is allowed:

- **Either** a calibrated causal prior for `first_to_second_purchase` keyed off realization data (N≥10 published runs of this play with measured second-order conversion lift), with the prior explicitly tagged `source_class: causal` and the realization N stamped on the driver.
- **Or** a holdout-design measurement on this store: send the play to a randomized fraction of the 286-person audience, hold out the rest, measure 28-day second-order conversion delta. Then the engine has an *observed* per-store effect to size from.

Until one of those exists, suppression is the only defensible state.

## Can We Put A Number On This Card Today, Or Not?

**No. None of the proposed alternatives clear the bar. The merchant-readable label must continue to be "no $ range until campaign realization data calibrates lift." Verdict against each option:**

(a) **Reach-based "potential audience revenue" (286 × AOV × baseline conversion).** Reject. This is value-at-stake dressed as expected impact, and the merchant *will* read it as an expected impact. 286 × $69 × 0.10 = $1,973 is not a forecast — it is "what the audience would be worth if every tenth of them converted at full AOV." A number that depends entirely on a baseline-conversion assumption (which we don't have for this store, on this play, with this audience definition) is a fabrication wearing arithmetic. It also re-introduces the legacy `expected_$ = audience × baseline_rate × benchmark_stack` defect that M0–M9 was built to retire.

(b) **Wide-prior range using the existing `first_to_second_purchase` expert prior.** Reject *as currently configured*. The existing prior is `source_class: expert`, not `causal`. The M6 sizer correctly suppresses targeting/expert priors. To make this honest the prior would have to be (i) re-classed as `causal`, (ii) carry a `source` field naming the realization data it rests on, and (iii) pass a wide enough range that the merchant reads it as a range and not a forecast. The engineering constraint in the brief — "do not approve relabeling an expert prior as causal without realization data" — is the binding constraint. We have no such data. The prior cannot honestly be promoted today.

The narrower question — "what would the prior values have to look like for this to be honest?" — has an answer: `p10/p50/p90` would have to be derived from at least N≥10 prior published runs of this play across comparable beauty merchants, with realized second-order conversion deltas measured against a hold-out, and the range would have to be wide enough that the p90/p10 ratio is at least ~3x to communicate uncertainty. We don't have those inputs.

(c) **"Hold-out vs control" simulated range using observed cohort dynamics.** Reject. There is no holdout in the data. Simulating one from observational cohort dynamics requires a structural assumption (typically a parallel-trends or matched-cohort assumption) that this engine cannot validate at the single-store level. Doing this simulation and putting the output on the card would be a model-based fabrication; it would survive technical inspection less well than the suppressed state because it would *look* like a measured number.

(d) **Non-monetary surrogate ("expected reactivations: 10–25 customers" from industry-typical first-to-second rates).** Reject for the merchant view, but **accept as a debug-receipt entry** if the engineer wants to scaffold for the eventual causal prior. The same problem as (a) and (b): a "10–25 customer" range backed by a nameless industry typical-rate is the same fabrication in different units. If you want it in `receipts/debug.html` as `expected_reactivations_under_industry_prior_DO_NOT_RENDER`, fine — it is internal scratch space. Do not surface it on the card. Once the merchant sees the number, it becomes the headline.

(e) **Stay suppressed.** **Correct.** This is the only option that does not import a defect.

**The merchant-readable label that should appear on the card today** (it currently does not appear on the card; the card has no $-related copy at all, which is also acceptable but a missed opportunity to *educate* the merchant about why no number is shown):

> "We don't yet have enough campaign-result history for this play on stores like yours to project revenue. Once you've run this play and we've measured what it actually drove, we'll start sizing it."

That sentence does the product work the suppressed `revenue_range` is structurally doing, in merchant English. It is honest. It is forward-looking. It explains the suppression without pretending the engine has a secret number it isn't sharing.

## The Unit-Of-Analysis Question (Audience vs Measurement Cohort)

**There is a serious unit-of-analysis defect in the card and it is the single highest-priority thing to fix before this scales beyond Beauty Brand.**

The play targets the 286-person *single-purchase cohort*. The supporting metric is computed on the 962-person *identified-recent cohort* (which by definition includes the very customers the play is *not* targeting — the multi-purchase repeat customers, who *are* the numerator of `returning_customer_share`).

Concretely, `returning_customer_share` rose from 84.9% to 91.5% on a denominator that is mostly customers who were *already returning customers* before the window. The play targets the *opposite* group — the 286 customers who have *not* yet returned. The signal is being read off cohort A and the action is being taken on cohort B, with no statistical bridge between them.

This is not a fatal flaw — there is a defensible narrative ("the broader retention environment on this store is strengthening, so a first-to-second nudge is more likely to land now than it was 28 days ago"), and that's roughly what the `why_now` text says. But that narrative is *correlational atmospherics*, not evidence. The card should not be promoted past Emerging on this evidence, and the receipts must be explicit that the supporting signal is measured on a different cohort than the audience.

**Concrete fix to the JSON schema:** add a `measurement.measurement_cohort` field that names the cohort the metric was computed on (here: `"identified_recent"`), distinct from `audience.id` (here: `"phase5_first_to_second_purchase"`), and have the renderer surface a one-line disclosure: "Signal observed on the broader returning-customer trend, not on the 286-person target audience directly."

## Measurement Fields — Are They Right?

Field by field:

- `metric: "returning_customer_share"` — correct, but the name conflates "store-level state metric" with "play-level measurement." Rename internally to make the state-statistic class explicit (`metric_class: state_statistic` vs `metric_class: intervention_effect`). The renderer doesn't have to surface it; the receipts must distinguish it.

- `observed_effect: 0.0659` — **not the right thing for this play.** The +6.6% L28 delta in cohort returning-share is the *supporting signal*, not the play's observed effect. The play has *no observed effect* yet because there is no measurement design on this store for the first-to-second intervention. Putting the cohort delta in the `observed_effect` field implies (to any future agent reading the schema) "the play moved this metric by 6.6%." It did not — the play has not yet been run.

  **Fix:** rename the field on directional cards to `supporting_signal_effect` or move it under a `supporting_signal` block: `{metric, store_observed_value, store_observed_delta, primary_window, consistency_across_windows, p_internal, measurement_cohort}`. Reserve `Measurement.observed_effect` for the play's *own* effect once it has been measured against a holdout. This is a schema-level distinction, not a copy change.

- `n: 962` — **wrong.** This is the cohort-wide identified-recent count, used as the denominator of the `returning_customer_share` proportion test. The implied claim of "n=962" on this play card is "the evidence behind this recommendation rests on 962 observations." That is literally not true: the 962 is the *supporting metric's* sample size; the *play's* n is 286 (the target audience), and the play has zero outcome observations because no campaign has run.

  **Right answer:** `n` on a directional card should be the audience size (286), not the supporting metric's denominator. The supporting metric's `n` belongs in the `supporting_signal` block as a separate field (`supporting_signal.n_proportion: 962`). Two distinct numbers, two distinct purposes, two distinct receipts.

- `primary_window: "L28"` — correct.

- `consistency_across_windows: 3` — see next section.

- `p_internal: 9.5e-05` — **defensible as an internal field that is never rendered**, which the engineer correctly does. The p-value is a real two-proportion z-test on real cohort splits, and its job here is to be a gating threshold (`p < 0.05` clears the directional bar). It must continue to never appear in the merchant view. The forbidden-string sweep correctly pins this.

- `ci_internal: null` — fine for now. If you ever add a CI for the supporting metric, mark it `ci_internal_supporting_signal` to prevent future agents from reading it as the play's effect CI.

## Watching vs State-Of-Store Routing — Adjudication

**`returning_customer_share` should be in BOTH state_of_store AND watching, surfacing different framings of the same metric. The current "state_of_store only" routing is a routing defect, not a deliberate design choice.**

Reasoning. The two surfaces serve different product jobs:

- **State of store** = "here's a fact about your store right now." Backwards-looking. Descriptive.
- **Watching** = "here's a metric we're tracking and what would change our recommendation if it moves." Forwards-looking. Decision-coupled.

`returning_customer_share` is the *load-bearing* signal behind the only Recommended card on the page. The merchant deserves to know two things: (1) where it is today, (2) what change in it would alter the recommendation. State-of-store carries (1); Watching carries (2). They are not redundant; they are complementary.

The Phase 5 implementation routed it to state_of_store only because the M7 Watching builder filters HELD observations and `returning_customer_share` got classified `moved` rather than `held`. That's a classification artifact, not a product decision. The right answer:

- Add `returning_customer_share` to Watching unconditionally when it is the supporting signal of a Recommended card, regardless of `classification`. The `threshold_to_act` text would read something like: "Reach out if returning-customer share drops below 85% — that would weaken the case for the first-to-second nudge."
- Keep it in state_of_store as the descriptive fact.

The renderer should make the *linkage* visible: the Recommended card cites the metric, state-of-store reports the level, Watching commits the engine to a threshold that would change the recommendation.

**Yes, it is OK to surface a metric in state-of-store *and* drive a directional recommendation from it.** That is in fact the *correct* product behavior — anything else hides the support. What is *not* OK is driving a directional recommendation from a metric that is not surfaced anywhere on the page; that's a black box.

## Considered List — Scientific Honesty

**The repetition is a defect of clarity, not honesty. The string is technically defensible but operationally misleading.**

The five-of-six "No measured signal yet for this play at this store" cards conflate three meaningfully different states:

1. **Has an audience builder, has a registry entry, but no measurement design exists on this store's data** (e.g., `bestseller_amplify`, `routine_builder`). This is "we know who to send to but don't know what would happen." The right reason text is closer to: *"This is a who-to-send-to recommendation. We can identify a 489-person audience, but we don't yet measure what this play actually drives at your store."*

2. **Has a measurement design but didn't clear the gate** (e.g., a play whose supporting metric had `p > 0.05` or `consistency < 2` or `effect < effect_floor`). Different reason text: *"We measured this play's supporting signal but the evidence isn't strong enough yet."*

3. **Has neither — the registry entry is there for vertical applicability but the play is not yet measurable at all** (e.g., `empty_bottle` with `audience: 0`). Different reason text again: *"This play doesn't apply at your store yet; the audience is empty."*

Today the engine collapses (1), (2), and (3) into the same string for five different plays, which makes the considered list look like the engine ran the same shallow check five times. That is not honest. The receipts (the `reason_code` enum) actually distinguish these states; the *rendered text* doesn't.

**Fix:** wire the `reason_code` enum to distinct merchant-readable strings. The current `_PRELIM_REASON_MAP` and `ReasonCode` infrastructure already exists for this; the templates just need to be written. This is a small change with high product clarity.

The `subscription_nudge` card with `reason_code: audience_too_small` and the distinct `"Eligible audience is below the minimum send threshold this run"` string is the model — that one card is honest because its reason is specific. Make all five look like that one.

## State Of Store — Methodological Notes

**`returning_customer_share` (+6.6%) and `repeat_rate_within_window` (-3.7%) are NOT measuring the same thing. The fact that they moved in opposite directions is consistent and probably correct — but the engine should surface them with their distinct definitions, because a sophisticated merchant will spot the apparent contradiction and lose trust.**

The two metrics:

- `returning_customer_share` = (customers in window with ≥1 prior order before window) / (customers in window). This is a *composition* statistic. Goes up when the new-customer share of the window shrinks.
- `repeat_rate_within_window` = (customers in window with ≥2 orders *during* window) / (customers in window with ≥1 order during window). This is a *within-window repeat* statistic. Goes up when customers are buying multiple times in the same 28 days.

These are nearly orthogonal definitions. A flat-orders, soft-acquisition month with no within-window-repeat can drive `returning_customer_share` up (denominator effect) while `repeat_rate_within_window` falls (genuinely fewer second orders inside the window). That looks like exactly what's happening on Beauty Brand: orders flat (0.0%), AOV up modestly (+1.7%), within-window repeat down (-3.7%), but the cohort composition is shifting toward returners (+6.6%).

This is also a strong piece of evidence that `returning_customer_share` is *not* signaling a retention surge — it is signaling an acquisition softening. **That's relevant to the recommendation.** A first-to-second nudge to single-purchase customers is *more* defensible in an environment where in-window repeat is falling (because customers who would have come back on their own are not, so the nudge is more likely to be the difference) — but it is *less* defensible if the underlying cause is that the new-customer pool itself is shrinking. The engine cannot disambiguate this without trend data on identified vs unidentified customer counts.

**Methodological recommendations to the engineer:**

1. Add a one-line internal-only note on the receipts that flags when `returning_customer_share` and `repeat_rate_within_window` move in opposite directions, since that is the dominant pattern when the change is denominator-driven rather than numerator-driven.
2. Surface the *new customer count* delta as a state-of-store fact alongside the two retention metrics. If new customers are down 15% MoM, the +6.6% `returning_customer_share` is mostly an arithmetic shadow.
3. Consider adding an internal `returning_customer_share` decomposition: how much of the delta is numerator-driven (more returning customers) vs denominator-driven (fewer new customers). This is a high-value receipts-only field that future agents should read before sizing.

## Smallest Change With Highest Scientific Value

**Author one calibrated causal prior for `first_to_second_purchase`, scoped to `vertical: beauty`, with `source_class: causal` and `realization_n: 0` stamped on the driver.**

Specific. Narrow. Highest scientific value-per-line.

What this looks like concretely. Add to `config/priors.yaml`:

```yaml
first_to_second_purchase:
  source_class: causal
  applies_to: { vertical: beauty }
  source: "expert prior pending realization data; will recalibrate after N>=10 published runs"
  realization_n: 0
  p_action_p10: 0.04
  p_action_p50: 0.08
  p_action_p90: 0.14
  incremental_orders_per_responder: 1.0
  effective_aov_factor: 0.85   # discount-adjusted, conservative
```

That single config entry, plus `source_class: causal` recognition in the M6 sizer, produces a *wide, conservative* `revenue_range` on the Beauty Brand card with full provenance. For audience=286 × p_action × inc_orders × AOV ($69) × 0.85, the range is approximately:

- p10: 286 × 0.04 × 1.0 × $69 × 0.85 ≈ $670
- p50: 286 × 0.08 × 1.0 × $69 × 0.85 ≈ $1,340
- p90: 286 × 0.14 × 1.0 × $69 × 0.85 ≈ $2,350

That range is below the $10k materiality floor, so the card *still* wouldn't carry a $ headline on this brand. But the receipts now have a numeric range, the `revenue_range.suppressed=true` would now be driven by **materiality**, not by **prior class** — which is a meaningfully different (and more defensible) suppression reason. And the moment realization data exists, that prior gets recalibrated and the suppression flips on whichever brand crosses the floor first.

**Why this is the highest-value change:**

- It is *one config file edit*, not a code change.
- It explicitly does *not* relabel an existing expert prior as causal — it adds a *new* causal prior with `realization_n: 0` and a `source` field that tells every future reader "this is a placeholder pending data." The forcing function against trust collapse is on the prior file itself, not on a downstream rendering check.
- It unlocks the $-suppression-by-materiality vs $-suppression-by-prior-class distinction, which is the actual product semantics the merchant cares about. The current "no $ because no causal prior" is the engine confessing to its own architectural state; "no $ because the prior says it wouldn't clear $10k for a store your size" is the engine doing real work.
- It generates the bootstrapping realization data the M9 calibration loop needs. Today `recommended_history.json` accumulates empty records forever because the engine never publishes a measured/causal-prior card. One causal prior breaks the bootstrap deadlock.
- It is *reversible* in one line if the realization data, when it lands, contradicts the placeholder values.

**What this change does NOT do:** it does not let the engine claim a measured effect. The card stays Emerging/directional. The receipts continue to show `revenue_range.suppressed: true`, but with `suppression_reason: "below_materiality_floor"` instead of `"directional_no_intervention_effect"`. That's the right answer — suppression for an economic reason, not an evidence-class reason.

## Risks / Guardrails

1. **The causal-prior placeholder is itself a fabrication risk if it leaks into a "calibrated lift" claim.** The mitigation is the `realization_n: 0` field and the `source` string explicitly naming it as pre-data. Any future agent that reads the prior must check `realization_n` before treating the prior as anything other than a wide range. Add a contract test: `assert prior.realization_n >= 10 or revenue_range.merchant_facing_label != "calibrated"`.

2. **The unit-of-analysis defect (n=962 used for a 286-audience play) is the schema-level latent defect that will bite when the engine generalizes to other directional plays.** The fix is to split `Measurement` into `audience_n` and `supporting_signal_n` as distinct fields, with the renderer reading audience_n. Defer if Phase 5 is locked, but file as the next-phase top-priority schema fix.

3. **The `returning_customer_share`-driven recommendation is a single-supporting-signal recommendation. If the supporting signal flips next month, the recommendation flips.** Today the engine has no mechanism to communicate "we recommended this last month and we're un-recommending it now because the signal weakened." The watching threshold + outcome log are the right home for this, but the M9 calibration stub doesn't yet read history. Track as the M10+ calibration-loop dependency.

4. **The "Considered" list templating risks normalizing five different held-states into one apparent reason. If a future agent reads the rendered HTML to seed a downstream Klaviyo briefing generator, all five plays will look identical and the agent may treat them as substitutable.** They are not. The reason-code enum already encodes the distinction; the renderer just doesn't surface it. Fix the templating before any downstream agent reads the considered list as input.

5. **The `state_of_store` cap was relaxed from 5 to 7 in Phase 5.3 to fit the new metrics. This is intentional but the M1 contract docstring still says 3-5.** Drift like this is how schemas decay. Sync the docstring; if 5 was the right product cap, drop one of the less-load-bearing observations rather than relax the cap.

6. **`watching[].current` and `watching[].prior` being null while `trend` is populated is a defect**, not a deliberate simplification. The Watching surface is supposed to anchor the threshold-to-act number ("act if it drops below X%") to the *current* level. Without `current`, the threshold is unanchored and the merchant cannot evaluate it against today's value. Populate both fields from `state_of_store[].supporting_metric` lookups before ship. If the engineer's choice was "we don't have a current value because the supporting metric isn't in the watching schema yet," that's the same routing defect from question 6 — fixing the routing fixes the null fields automatically.

7. **The Phase 5.7 `journey_optimization` suppression is V2-only.** The legacy emitter still produces it. If a future change flips `ENGINE_V2_OUTPUT=true` as default before M10 cleanup deletes the legacy candidate, journey_optimization could re-leak via the legacy adapter. The defense in `decide()` filters it again, but the deeper fix (delete the candidate from the legacy emitter) is M10 work and shouldn't be deferred indefinitely.

## 5-Bullet Summary For Orchestrator

- **Suppression is correct.** A state statistic (cohort returning-share) cannot be sized as if it were an intervention effect. The engineer's refusal to feed `returning_customer_share` into the sizer is the load-bearing scientific call of Phase 5 and it is right. Do not approve any of the five proposed paths to a $ number today; all of them re-introduce the legacy fabrication defect in different units.
- **The card has one shippable defect: `measurement.n: 962` is the supporting metric's denominator, not the play's n.** The right value is the audience size (286). The `n` field's implied claim ("the evidence rests on 962 observations") is false; the play has zero outcome observations and a 286-person target. Schema fix: split `Measurement` into `audience_n` (286) and `supporting_signal_n` (962). Until that's split, the field is misleading any downstream agent that reads it.
- **`returning_customer_share` should be in BOTH state-of-store AND watching.** The current state-of-store-only routing is a classification artifact (M7 watching builder filters HELD observations), not a product decision. A metric that is the load-bearing signal of a Recommended card must appear in Watching with a threshold-to-act, otherwise the merchant has no way to know what would change the recommendation.
- **Smallest, highest-value change to make the card carry a $ range honestly: add ONE causal-class prior for `first_to_second_purchase` with `source_class: causal`, `applies_to: {vertical: beauty}`, `realization_n: 0`, and a wide, conservative `p_action_p10/p50/p90`.** This is one config file edit. It does not relabel an existing expert prior. It produces a $670–$2,350 range on Beauty Brand (still below materiality), shifts the suppression reason from "no causal prior" to "below materiality floor" (which is the right economic semantics), and unlocks the bootstrap path for realization-data-driven calibration. The merchant card stays Emerging/no-$; the receipts now do real work.
- **The "Considered" list is templated to five identical strings for five distinct held-states.** This is technically defensible but operationally misleading; a future agent reading the considered list as input to a downstream campaign generator will treat all five as substitutable when they are not. The `reason_code` enum already encodes the distinction — the renderer needs five strings, not one. Fix before any downstream agent consumes the considered list.
