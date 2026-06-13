# BeaconAI Action Engine — Ecommerce DS Architectural Review

## Executive Summary

- **The engine is a hypothesis-generation system masquerading as a forecasting + significance-testing system.** The dominant failure mode is presentational, not algorithmic: heuristics, priors, and selection rules get reported with the visual grammar of measured evidence (p-values, q-values, CIs, dollar forecasts).
- **There is no single conceptual stage in the pipeline.** Candidate generation, signal estimation, evidence weighting, economic projection, and ranking all bleed into each other. A play's "p-value" sometimes comes from the play itself, sometimes from a different cohort's stability test, sometimes from a literal hardcoded constant.
- **The decision surface is shaped by a confidence_score that is mostly a single p-value re-encoded in 4–6 ways**, multiplied with seasonality and per-vertical multipliers. This is a bench tool dressed up as a multi-factor risk score.
- **Market research (`analysis/conversion_rate_research_recommendations.md`) is being misused as direct causal lift.** Klaviyo email-conversion benchmarks (an observational marketing-performance average, conditional on opening an email) are wired in as `conversion_rate × audience` to produce dollar projections. This is a category error.
- **"Untestable" plays (subscription_nudge, routine_builder, empty_bottle, category_expansion) are being forced through the same `p / q / effect / CI` mold as testable ones.** They should be a different architectural class entirely — targeting recommendations with audience economics, not hypothesis tests.
- **The multi-window pipeline is doing the opposite of what it should.** L7/L28/L56/L90 are nested by construction; "merging" them via min-p is winner's-curse selection. A meta-analytic combiner exists (`combine_multiwindow_statistics` in `src/stats.py`) but is only used for 4 of 10 plays.
- **The right shape for this engine is: a hypothesis-and-targeting recommender with calibrated audience-level economics, NOT an inferential statistics pipeline.** A single-store, monthly-cadence, no-experimentation context cannot support frequentist confidence claims at the play level.
- **Phase 1 should collapse the surface area, not extend it.** Three stages (Detect → Size → Recommend), one merit signal, one transparent confidence label, no fabricated stats, no cherry-picked p-merging, and a shared "evidence vs heuristic" flag honored by every output.

---

## Diagnosis: What This System Actually Is, vs. What It Should Be

### What it is today

A monolithic candidate-scoring loop in `src/action_engine.py` that:

1. Pulls multi-window aligned features.
2. For each of ~10 hardcoded play templates, computes either (a) a real two-proportion / Welch test, (b) a constant p/effect/CI tuple, or (c) a test on a different audience or different time period than the recommended action.
3. Cherry-picks min-p across L7/L28/L56/L90 (`_merge_multiwindow_candidates`, line 1210).
4. Runs Benjamini–Hochberg on the cherry-picked set (line 1330).
5. Computes `final_score = 0.35 financial + 0.25 significance + 0.20 effect + 0.10 confidence + 0.10 audience` (`src/scoring.py`).
6. Computes `confidence_score = 0.6 statistical_confidence(p) + 0.4 (gate_score + signal_bonus)/125 × context_multiplier × safety_multiplier`, where every term is a function of p.
7. Multiplies an audience by a vertical-baseline conversion rate, multiplies that by a per-vertical effect-size constant, multiplies that by a per-stage execution multiplier, multiplies that by a "health boost," multiplies that by an incrementality factor and a decay factor, applies a saturation penalty, and reports the result as `expected_$` revenue.
8. Surfaces tiered cards labeled PRIMARY / QUICK_WINS / WATCHLIST / EXPERIMENTS in an HTML briefing with a "High/Moderate/Early signal" chip, a Range chip, and an Effort chip.

### What it should be

A **three-stage recommender** with explicit handoffs:

1. **Detect**: candidate plays surfaced from data structure (does this audience even exist? does this signal even move?).
2. **Size**: audience economics — projected revenue under documented assumptions, with assumption labels visible.
3. **Recommend**: rank by a single merit measure, present a **calibrated qualitative confidence label** with explicit drivers ("strong measured signal", "directional", "targeting heuristic", "no measurable signal"), not a manufactured numeric score.

There should be **two structurally distinct play classes**:

- **Evidence-based plays** (winback, frequency_accelerator, retention_mastery, journey_optimization, aov_momentum, discount_hygiene): the recommended action is a hypothesis on a metric for which the store has direct data. These can carry a measured effect and a real CI.
- **Heuristic / targeting plays** (subscription_nudge, routine_builder, empty_bottle, category_expansion, bestseller_amplify): the recommended action is a *targeting decision* (who to send to, what to bundle). These carry no inferential claim because there is no counterfactual in the data. They get an audience size, an assumption-based revenue range, and a "Why this audience" explanation — full stop.

The current system mashes both classes together and forces the second class to manufacture statistical artifacts. That is the single largest architectural defect.

---

## Where Signals Are Misinterpreted at the System Level

These are system-level issues, not the line-level statistical bugs already documented in `agent_outputs/statistical-code-reviewer-initial.md`. They are about *what kind of claim the engine is implicitly making*.

### 1. Treating cohort-stability tests as hypothesis tests on the recommended action

`subscription_nudge`, `routine_builder`, `empty_bottle` test whether *prior cohorts behaved similarly to each other*. That is a stationarity test, not a test of "will the nudge work." Reporting `p = 0.03` on a stationarity test next to a recommendation labeled "Promote subscriptions" reads, to a merchant, as "we have 97% confidence subscription promotion will lift revenue." That claim is not in the data anywhere.

The architectural fix is not "fix the test." It is **remove the test from this play class**. The play is a targeting recommendation. It should not produce a p-value at any level of the system.

### 2. Treating Shopify period-deltas as causal effect estimates

When recent AOV is higher than prior AOV, the engine reports `effect = (recent - prior)/prior` and feeds that into the merit score and the revenue projection as if it were a treatment effect. It is not. It is a noisy seasonal/mix-shift snapshot. With no counterfactual, the engine cannot distinguish "AOV grew because the customer base shifted" from "AOV grew because of a one-time promo" from "AOV grew because of a high-cart anomaly."

This isn't fixable by tightening tests. The architecture must label these as **observed change**, not **estimated effect**, and use them as triggers for the recommendation, not as inputs to a revenue forecast.

### 3. Treating overlapping windows as independent evidence

L7 ⊂ L28 ⊂ L56 ⊂ L90. The engine treats them as four pieces of evidence, picks the most favorable, and runs FDR over the result. Architecturally, **windows are not evidence; they are robustness checks.** The right framing: "the signal is consistent across windows" → high confidence; "only L7 shows it" → low confidence (recent noise). A min-p merge inverts this: it elevates the case where only the noisiest window shows the signal.

### 4. Treating per-vertical conversion-rate priors as direct multipliers

`conversion_rate = base_rate × stage × performance × health × execution × health_execution`, then `revenue = audience × conversion_rate × effect × incrementality × decay`. The chained multiplier stack is mathematically a point-estimate forecast with no stated uncertainty. With six multipliers and no confidence band on any of them, the propagated uncertainty is enormous and unreported.

The architectural correction: **forecast in audience economics**, not stacked multipliers. State a base assumption, state a range, show the merchant the assumption, and let them set their own.

### 5. Treating `final_score` and `confidence_score` as orthogonal axes

The two-axis tier matrix in `ENGINE.md` claims `final_score` measures merit and `confidence_score` measures execution risk. In practice, both are dominated by the same p-value (p enters `significance`, `confidence_from_ci`, `gate_score`, `signal_bonus`, `safety_multiplier`, and `statistical_confidence`). The "two axes" are 80% the same axis. The 4×4 tier matrix is mostly a 1×4 tier ladder.

### 6. Treating evidence quality and timing risk as the same scalar

Seasonality multipliers (`get_seasonal_multiplier`) currently nudge `confidence_score`. Seasonality is a *timing constraint on action launch*, not a confidence factor. A retention play in January is not less *evidenced* than the same play in October. Merging them collapses two distinct decisions into one number.

---

## Architectural Recommendations

### Stage 1: Candidate Generation (Detect)

**Purpose**: identify play candidates from the data structure, deterministically.

- Each play has a **gating predicate** ("audience > N", "feature exists", "category present") — pure data presence/structure, not statistical significance.
- No p-values, no effects, no CIs at this stage. A candidate is just `(play_id, audience, segment_definition)`.
- Existing code already has these predicates, scattered through `_compute_candidates`. Extract them.

**Handoff to Stage 2**: a list of `Candidate { play_id, audience_ids, segment_definition }`.

### Stage 2: Signal Estimation (Quantify what's actually there)

**Purpose**: for each candidate, compute the *one* statistic that corresponds to the claim the play makes — and only when the claim is testable.

- For evidence-based plays: compute the relevant test (two-proportion z for repeat rate, Welch for AOV with caveats, etc.) **once**, on the most stable window the data supports.
- For heuristic plays: skip this stage entirely. Set `evidence_class = "heuristic"`. No fabricated p, no fabricated effect.
- Robustness across windows is reported as a **consistency score** (count of windows in the same direction, sign-stable / sign-unstable). It is *not* a multiplier on confidence and *not* fed to FDR.

**Handoff to Stage 3**: enriched `Candidate` with `{ evidence_class, observed_effect | None, p | None, n, consistency_score, primary_window }`.

### Stage 3: Uncertainty Quantification (Be honest about what you don't know)

**Purpose**: bucket each candidate into a small, defensible confidence vocabulary. Stop manufacturing scalars.

Use **four discrete labels**, derived deterministically:

- **MEASURED**: evidence-based play, p < α on primary window, sign consistent across the windows that have power, n ≥ min_n.
- **DIRECTIONAL**: evidence-based play, sign-consistent, but p ≥ α or n < min_n.
- **TARGETING**: heuristic play with a defensible audience definition (passes Stage 1 gates, segment economics make sense). No statistical claim.
- **WEAK**: passes Stage 1 only because audience exists; fails everything else. Goes to backlog/watchlist.

The 4×4 tier matrix collapses to a 4-bucket ranked list, which is what merchants actually parse.

### Stage 4: Economic Sizing (Audience economics, not stacked multipliers)

**Purpose**: project a defensible 28-day revenue range with auditable inputs.

Replace the chain `audience × stage × performance × health × execution × effect × incrementality × decay × saturation` with a **transparent audience economics formula**:

```
projected_revenue = audience × p_action × incremental_orders_per_actor × AOV
```

where:

- `audience`: from Stage 1, observed.
- `p_action`: action-take rate. For evidence-based plays, derived from store data (e.g., observed repeat rate uplift). For heuristic plays, declared as an assumption with a vertical-derived range, not a point.
- `incremental_orders_per_actor`: 1 for transactional plays, multi-period for retention/winback. Use simple, defensible defaults.
- `AOV`: observed in store data.

Report a **range** (e.g. p10/p50/p90) generated by varying `p_action` over its assumption range, not multiplying point estimates of six multipliers. Show the merchant which input drove the range. If the merchant changes `p_action` later, the projection should update.

### Stage 5: Ranking & Output (One score, one label, one explanation)

**Purpose**: produce the briefing.

- Single ranking signal: **expected revenue, p50** (median of Stage 4 range).
- Single confidence label: from Stage 3's four-bucket vocabulary.
- Show: "Why this play, why now, who this targets, what we measured (or honestly, what we assumed), what the range depends on."
- No PRIMARY/QUICK_WINS/WATCHLIST/EXPERIMENTS matrix. A single ordered list with a confidence chip is enough.

---

## Treatment of "Untestable" Plays

This is the biggest architectural decision.

**The plays that cannot be tested with single-store data are: subscription_nudge, routine_builder, empty_bottle, category_expansion, and bestseller_amplify.** Their recommended action (introduce a subscription, build a bundle, push a cross-sell, promote a bestseller) is a *new behavior* the audience hasn't taken. By definition there is no counterfactual in observed data.

**Don't fix the tests. Reclassify the plays.**

These plays should:

1. Carry an `evidence_class = "heuristic"` flag from Stage 1 onward.
2. Surface no p-value, no q-value, no CI, no `effect_abs` in any user-visible artifact.
3. Be sized using documented audience economics with a **range**, not a point. The range is set by vertical priors (where market research finally has a legitimate role — see next section).
4. Display in the briefing with a different visual treatment ("Targeting recommendation") so a merchant immediately understands the difference from "Measured opportunity."
5. Be ranked separately or interleaved with a clear class label, not merit-mixed.

This is the cleanest version of the change. It removes ~60% of the current statistical-overclaiming risk in one architectural cut.

The alternative — instrumenting these plays for actual measurement — requires holdout/quasi-experimental design and is correctly out of scope for a single-store, monthly-cadence, no-experimentation engine. **Phase 1 should not pretend otherwise.**

---

## The Right Role for Market Research / Vertical Priors / Seasonality

`analysis/conversion_rate_research_recommendations.md` is the test case. It cites Klaviyo email-conversion benchmarks (10.34% for winback emails, 25–35% for cross-sell take-rates, etc.). Critical evaluation:

### What these benchmarks actually are

- **Klaviyo / Bloomreach email conversion benchmarks**: marketing-performance averages conditional on (a) opening the email, (b) clicking, and (c) converting. They are *channel-conditional observational averages* over heterogeneous brands.
- **Cross-sell "take-rate" benchmarks**: observational averages of customers exposed to cross-sell modules. They include selection effects (only some merchants run cross-sell, only some have it well-merchandised).
- **Subscription / churn benchmarks**: equilibrium population statistics, not lift estimates.

**None of these are causal lift estimates.** None are valid as direct multipliers in a `revenue = audience × conversion_rate × ...` chain that pretends to estimate incremental revenue.

### How they are misused today

The engine sets `base_rate = 0.18` for `bestseller_amplify` in the `beauty` vertical and multiplies it by `audience` to get "converted customers." That implicitly assumes:

1. Every customer in the audience will be reached (no email open-rate adjustment).
2. The benchmark population is exchangeable with this store's customers (no calibration).
3. The benchmark is incremental (no counterfactual baseline subtraction).

All three assumptions are wrong by default. The output is therefore biased upward by a factor that is neither known nor reported.

### How they SHOULD be used

Three legitimate roles:

1. **Sanity-check ranges, not point estimates.** A `bestseller_amplify` in beauty has a defensible take-rate *range* of, say, 5–25% based on the literature. Use the range to set the upper and lower bounds of the projection in Stage 4. Do not collapse to a point.
2. **Vertical-conditional priors for missing-data plays.** When the store has no relevant signal (e.g., a new store with 60 days of data), a vertical prior keeps the projection from going to zero. But it should be displayed as **"prior assumption — calibrate as data arrives."**
3. **Plausibility validation, not lift estimation.** Before publishing a forecast, check it against the vertical range. If projected lift exceeds the 90th percentile of the benchmark distribution, flag the recommendation as "outlier — likely overestimated."

### What they should NEVER do

- **Drive `confidence_score`.** A vertical prior is not evidence about this store. Confidence about a play in a specific store should depend only on data from that store + structural predicates.
- **Be presented to merchants as "data-backed"** without disclosing the source class. A merchant needs to know "this 28-day projection comes from Klaviyo industry averages, not your store" or they will calibrate decisions wrongly.
- **Be applied without an open-rate / reach adjustment.** If the benchmark is an email-opens-conditional rate and the engine multiplies by total audience, the projection is silently overstated by ~3–5x.

### Seasonality

Seasonality should be a **launch timing constraint**, not a confidence factor. A play with strong evidence in March is not less evidenced than the same play in November. Move seasonality out of `confidence_score` entirely; let it influence the **recommended launch window** ("Run this in Aug–Sep for 1.2x effect") and let the merchant accept or override.

---

## Sequenced Build Plan: Phase 1 vs. Defer

### Phase 1 (must ship before merchants see briefings)

In dependency order:

1. **Stop fabricating statistics.** Set `p`, `q`, `effect_abs`, `ci_low`, `ci_high` to `None`/NaN for any candidate where the value is a hardcoded constant. (Smallest possible code change with the largest correctness gain.) Already half-implemented for some plays via `enhance_template_action_with_real_stats`; complete the coverage.
2. **Introduce `evidence_class` (`measured` | `directional` | `targeting` | `weak`)** as a first-class attribute on every candidate. Drive briefing output off this attribute, not off raw `p`/`q`.
3. **Replace the min-p merge with the existing `combine_multiwindow_statistics` for all evidence-based plays.** The function already exists and is correct; rerouting `_compute_multiwindow_candidates` is a localized change.
4. **Pick ONE place where p enters confidence and remove the others.** Recommended: keep `_calculate_statistical_confidence` (or replace with the 4-bucket label), drop the gate_score/signal_bonus/safety_multiplier p-recoding. Confidence becomes a step function over a single test outcome — defensible and explainable.
5. **Reclassify subscription_nudge, routine_builder, empty_bottle, category_expansion as targeting plays.** Strip their p/q/effect/CI from all output. Add a "Targeting recommendation" visual treatment in `storytelling.py`.
6. **Add a research-prior label to revenue ranges.** When `expected_$` derives from a vertical baseline, attach `assumption_source = "vertical_prior"` and surface it ("Range based on beauty vertical assumptions, not your store's data"). Keep numbers, but make them honest.
7. **Drop seasonality from `confidence_score`.** Re-attach to a separate `recommended_launch_window` field.

These seven changes are the smallest set that makes the engine defensible. No statistical machinery is added; harmful machinery is removed.

### Defer (Phase 2+, only after Phase 1 is shipped)

- Bayesian credible intervals on revenue projections (right idea, requires real prior elicitation, distracts from cleanup).
- Cohort pooling (`ENABLE_COHORT_POOLING`): the framework is half-implemented, and the placeholder `_run_cohort_statistical_test` returns p=1.0. Disable the flag and remove the dead path until it has a real implementation.
- `repeat-rate bias correction` multiplier: either justify and document or remove. Phase 1 should remove and revisit.
- Play-effect calibration loop (recording predicted vs realized lift after publish, updating priors). Belongs to the agentic future state, not Phase 1.
- Multi-store learning / hierarchical priors. This is where the engine genuinely transcends benchmark-multiplication, but it requires a fleet of stores. Defer until you have one.

### Out of scope, explicitly

- A/B testing infrastructure inside the engine. The product is single-store, no-experimentation. Don't borrow RCT vocabulary.
- Per-merchant statistical confidence calibration. This requires post-publish realized-impact data, which the local CSV → HTML workflow cannot provide.

---

## How Confidence Should Be Communicated to a Non-Statistician Merchant

The merchant should see, per recommendation:

- **A short label**: "Measured in your data" / "Directional signal in your data" / "Targeting recommendation" / "Early — needs more data."
- **One sentence of explanation**: "Repeat rate dropped 4 points in the last 28 days vs prior 28; that holds in the 56- and 90-day views too." Or for targeting: "These 320 customers have bought the same product 3+ times in 90 days, so a subscription offer is likely to land."
- **A revenue range with a labeled source**: "$3,500–$8,200 (28d). Range based on observed audience behavior" vs "Range based on beauty-vertical industry averages."
- **No p-values, no q-values, no CIs, no confidence percentages in the merchant view.** These belong in the receipts/debug, not in the merchant briefing. A "0.73 confidence" number invites false precision; a label invites correct calibration.

The principle: **the merchant-visible confidence vocabulary should match what the system actually knows, not what looks rigorous.**

---

## Architectural Anti-Patterns Observed

Each named, with one-line explanation.

1. **Hypothesis Laundering** — running a test on cohort-A vs cohort-B and presenting the p-value as evidence for an action that targets cohort-C. (subscription_nudge, routine_builder, empty_bottle.)
2. **Window Shopping** — testing across nested time windows and reporting the most favorable result without selection correction. (`_merge_multiwindow_candidates` min-p.)
3. **Multiplier Stacking** — chaining 5+ unitless multipliers to produce a revenue forecast with no propagated uncertainty. (`calculate_28d_revenue` × `compute_conversion_multiplier` × `get_incrementality_factors` × `compute_decay_multiplier` × saturation.)
4. **Benchmark-as-Lift** — using observational marketing-performance averages as direct causal multipliers in a revenue model. (`conversion_rate_research_recommendations.md` → `get_conversion_rates`.)
5. **Confidence Theater** — recoding a single p-value into 4–6 derived terms and summing them to produce a multi-factor confidence score. (`_calculate_business_confidence`.)
6. **Tier Matrix Without Orthogonality** — constructing a 4-quadrant decision matrix on two axes that are correlated >0.8. (`final_score` × `confidence_score`.)
7. **Significance Smearing** — feeding correlated/duplicate p-values into Benjamini–Hochberg as if independent (returning_share & new_customer_rate; nested windows).
8. **Heuristic-as-Evidence** — labeling plays inconsistently: `subscription` honestly tagged "(heuristic)" in `evidence_for_action`, `routine_builder` not tagged. The architecture should make this distinction structural, not stylistic.
9. **Dead Switch Attractor** — keeping flags around half-implemented features (`ENABLE_COHORT_POOLING`, `_calculate_calibrated_confidence`) that look load-bearing but aren't. Future maintainers re-activate them assuming they work.
10. **Forecast as Decision** — treating `expected_$` as a forecast a merchant should believe, when it is actually a *ranking signal* derived from assumptions. The number lends false weight to a tiering decision.

---

## Risks and Open Questions

- **Open**: how does the engine handle stores with <90 days of data? Currently most window-based logic silently degrades; explicit Phase 1 behavior should be "mark as cold-start, default to targeting plays only, lean on vertical priors with labels."
- **Open**: with no realized-impact feedback loop in the local workflow, how does the engine learn it has overstated lift? Today: it can't. The agentic future state assumes Klaviyo publish + monitor; until then, calibration is structurally absent. Phase 1 must assume this and stay conservative.
- **Risk**: downstream agents (campaign-bundle generator, Klaviyo publisher) will consume the current `expected_$` and treat it as ground truth for budget allocation. If Phase 1 doesn't tighten the projection logic and label assumption sources, the agentic layer will silently propagate overstated forecasts into actual campaigns and ad spend.
- **Risk**: market research priors (`conversion_rate_research_recommendations.md`) are stored as point estimates inline in the codebase. They should be a versioned, dated, auditable artifact — both because benchmarks shift and because the source-class (observational vs causal) needs to travel with the number. Today there's no architectural place for this; the file lives in `analysis/` and is re-encoded as Python constants.
- **Risk**: the 4-tier vocabulary recommended above (`MEASURED / DIRECTIONAL / TARGETING / WEAK`) is opinionated; a merchant-facing test will determine whether the labels parse correctly. Plan to A/B the language with real users before locking it into the briefing template.
- **Assumption to validate**: that merchants want a recommender, not a dashboard. The current engine's confused identity ("forecast engine + significance tester + tier matrix + dashboard") suggests this hasn't been resolved at the product level. The DS architecture should follow the product decision, not paper over it.

---

## Files Referenced

- `/Users/atul.jena/Projects/Personal/beaconai/ENGINE.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/statistical-code-reviewer-initial.md`
- `/Users/atul.jena/Projects/Personal/beaconai/analysis/conversion_rate_research_recommendations.md`
- `/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/stats.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/scoring.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/features.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/segments.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/storytelling.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py`
