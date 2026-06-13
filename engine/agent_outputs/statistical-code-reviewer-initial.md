# BeaconAI Action Engine — Statistical Audit

## 1. Executive Summary

The engine surfaces statistical confidence and revenue projections that are partially defensible, but the current code mixes valid tests, fabricated p-values, and cherry-picked statistics in the same pipeline. The five highest-severity issues, ranked:

1. **Fabricated p-values, effects, and CIs are still injected into Phase 2 fallbacks (category_expansion only is unfixed; subscription_nudge, routine_builder are partially fixed)** and then flow into BH-FDR, gates, and merit score together with real p-values. Critical.
2. **Multi-window p-value merging cherry-picks the minimum p across overlapping windows**, then BH-FDR is applied to that cherry-picked set — selection bias plus invalid FDR. Critical.
3. **Subscription_nudge and routine_builder produce a p-value from a comparison that is not a test of the recommended action**; effect size is a hardcoded constant. The "p" reported is unrelated to the "effect" reported. High.
4. **`confidence_score` triple/quadruple-counts the same p-value**, and `final_score` adds another q-based significance term plus a CI-based confidence term. p propagates into 4–6 places before tiering. High.
5. **BH-FDR is applied to mathematically dependent p-values within a window** (`returning_customer_share` and `new_customer_rate` are computed as `1 − x` of each other and given the same p, then BH treats them as two independent tests). Medium.

There are also clear instances of survivorship bias (subscription audience), overlapping-window bias (L7⊂L28⊂L56⊂L90 are tested as if independent), heuristic-as-evidence in revenue formulas, and a hardcoded "repeat-rate bias correction" multiplier with no statistical justification.

---

## 2. Critical Findings

### C-1. Hardcoded p-values, effects, and CIs in Phase 2 fallback candidates
Severity: critical. Methodology flaw plus implementation issue.

`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py`, in `_compute_candidates`:
- `frequency_accelerator` (lines ~3362–3380): `effect_abs=0.20, p=0.03, ci_low=0.15, ci_high=0.25`
- `aov_momentum` (lines ~3422–3440): `p=0.04, ci_low=aov_growth*1.2, ci_high=aov_growth*1.8`
- `retention_mastery` (lines ~3485–3503): `effect_abs=0.07, p=0.02, ci_low=0.05, ci_high=0.10`
- `journey_optimization` (lines ~3550–3568): `effect_abs=0.30, p=0.05, ci_low=0.20, ci_high=0.40`
- `category_expansion` (lines ~3614–3632): `effect_abs=0.40, p=0.04, ci_low=0.30, ci_high=0.50`

These are constants, not measured. Why this matters:
- They feed `benjamini_hochberg` (line 1332) alongside real p-values, polluting the q-value calculation.
- They feed `confidence_from_ci` (`/Users/atul.jena/Projects/Personal/beaconai/src/scoring.py:21`), which returns 0.9 because the CIs trivially exclude 0 — so merit score gets a 0.10 × 0.9 boost from a fabricated interval.
- They feed `_calculate_business_confidence` and inflate confidence_score, which drives PRIMARY/QUICK_WINS tier assignment.

Mitigation that exists: `enhance_template_action_with_real_stats` (line 4016) replaces the assumed p/effect/CI for `frequency_accelerator`, `retention_mastery`, `journey_optimization`, `aov_momentum` with multi-window stats — but **only if `ENABLE_ENHANCED_STATISTICS=True` AND multi-window aligned data is supplied**. If single-window mode is used, the hardcoded values are used as-is. And `category_expansion` is not in the enhanced allow-list at all (line 4035), so its fabricated stats always pass through.

This matches the prior memory ("Phase 2 hardcoded stats — fallbacks remain for category_expansion/subscription_nudge/routine_builder/discount_hygiene"). category_expansion is the most exposed: still 100% fabricated stats in production paths.

User-visible impact: a play with no actual statistical evidence can be tagged "High confidence" / PRIMARY tier and recommended at the top of the briefing because of constants in the source code.

---

### C-2. Multi-window p-value cherry-picking, then FDR over the cherry-picked set
Severity: critical. Methodology flaw.

`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py:_merge_multiwindow_candidates` (line 1210), specifically lines 1231–1241:

```
# Update source_window to the one with strongest signal (lowest p-value)
current_p = existing.get('p', 1.0)
new_p = c.get('p', 1.0)
if new_p < current_p:
    existing['p'] = new_p
    existing['q'] = c.get('q', existing.get('q'))
    existing['n'] = c.get('n', existing.get('n'))
    existing['effect_abs'] = c.get('effect_abs', existing.get('effect_abs'))
```

And line 1248: `existing[key_metric] = min(existing[key_metric], c[key_metric])` for `p_value`.

Why this is wrong:
- L7, L28, L56, L90 share data: L90 contains L56 contains L28 contains L7. Running the same test across these windows produces correlated p-values; the minimum is biased downward (this is the multiple-testing winner's curse against the same null).
- Effect size is taken from whichever window had the lowest p, not from a meta-analytic combination, so the "effect" reported is the most extreme realization in any window.
- After this merge, `benjamini_hochberg` runs on the merged list (`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py:1330`). BH assumes the p-values are valid; here they have already been selected for being smallest-of-K, so they are not p-values under H0 anymore.

Note that `combine_multiwindow_statistics` exists in `/Users/atul.jena/Projects/Personal/beaconai/src/stats.py:334` and uses Fisher's method + inverse-variance weighting — that's the right shape — but the path that flows into the gate (`_compute_multiwindow_candidates`) calls `_merge_multiwindow_candidates`, which cherry-picks. The proper combiner is only invoked through `enhance_template_action_with_real_stats` for 4 specific play_ids.

User-visible impact: candidates appear far more significant than they are; PRIMARY tier is reachable via window-shopping.

---

### C-3. p-value and effect size are decoupled / unrelated for subscription_nudge, routine_builder, empty_bottle
Severity: critical. Methodology flaw.

`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py`:

**subscription_nudge** (lines 2966–3086):
- Effect: `effect_abs: 0.05` constant (line 3074), commented as "weekly proxy effect (selection heuristic)."
- p-value: `p_sub = two_proportion_z_test(xA, nA, xB, nB)` where xA/nA and xB/nB are two prior cohorts (180–270 days ago vs 90–180 days ago) of customers with ≥3 same-product orders, tested for whether they had any order in the next 28 days. This tests **temporal baseline drift in a survivorship-selected cohort**, not the lift of a subscription nudge.
- Survivorship: audience = customers with `orders_product >= 3` (line 2982). These are people who already have the behavior the play is supposed to encourage. Their next-28d conversion is dominated by their history, not by the nudge.

**routine_builder** (lines 3091–3186):
- Effect: `effect_rb = 0.08` constant (line 3148), commented "weekly proxy effect."
- p-value: `p_rb = welch_t_test(aA, aB)` (line 3163) where aA/aB are AOV samples of the same audience in two prior 60-day periods. This tests whether the audience's AOV was stable over time, not whether bundling will change AOV. Also has the survivorship issue: audience is "single-product skincare buyers in last 60 days."
- Fallback when sample is too small: `p_rb = 0.06 if audience_rb<80 else 0.03` (line 3163, 3165). These are also hardcoded.

**empty_bottle** (lines 3189–3293):
- Effect: `effect_abs: conv_weekly` where `conv_weekly = 0.10` (line 3219), constant.
- p-value: comparing two historical depletion-window cohorts' 14-day reorder rates (lines 3253–3263). Same pattern: tests cohort-stability, not the play.
- Fallback: `p_eb = 0.06 if audience_eb<80 else 0.05` (lines 3272, 3275). Hardcoded.

This matches the prior memory items about subscription_nudge multiplier-vs-baseline conflation and routine_builder Welch-t producing p-value with no effect plumbed.

User-visible impact: the action carries a numeric p-value that suggests a tested hypothesis, but the hypothesis tested is not "does this play work"; it is "did this audience already do this thing in the past."

---

### C-4. Confidence score double/triple-counts the same p-value
Severity: high. Methodology flaw.

`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py`:
- `_calculate_business_confidence` (line 2405) is the function actually used (line 2497).
- It blends `_calculate_statistical_confidence(p)` (line 2387; pure step function on p) at 0.6 weight with a "business context" term at 0.4 weight.
- The "business context" term itself is `(gate_score + signal_bonus) / 125 * context_multiplier * safety_multiplier`, where:
  - `gate_score` (line 2281) gives 25 points if `p < threshold` (line 2292).
  - `signal_bonus` (line 2309) gives up to 25 points based on `-log10(p)` (line 2331).
  - `safety_multiplier` (line 2367) penalizes by p again: 0.05x if p≥1, 0.2x if p>0.8, 0.6x if p>0.5 (lines 2378–2383).

So a single p-value is mapped to a score, then again to a gate pass, then again to a -log10 bonus, then again to a safety multiplier. Then `compute_score` in `/Users/atul.jena/Projects/Personal/beaconai/src/scoring.py:5` adds:
- `0.25 * significance` based on q-value
- `0.10 * confidence` based on `confidence_from_ci` (which is itself a function of whether the CI excludes 0 — same evidence as p)

`final_score` and `confidence_score` are both used in tier assignment (`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py:2549`), so the same evidence drives the cell on both axes of the tier matrix. A single strong (or fabricated) p-value will move a candidate from WATCHLIST to PRIMARY by hitting all six p-keyed terms simultaneously.

User-visible impact: confidence appears to be made of "many factors" but is mostly p, raised to several powers.

---

### C-5. BH-FDR over dependent / duplicated p-values within a window
Severity: medium-high. Methodology flaw.

`/Users/atul.jena/Projects/Personal/beaconai/src/utils.py:kpi_snapshot_with_deltas` lines 1741, 1754:

```
# new_customer_rate is 1 - returning; mirror p-value
p["new_customer_rate"] = pval_ret
...
qvals = _bh_adjust(p_list, alpha=alpha)
```

The list submitted to BH includes 5 metrics: `aov`, `discount_rate`, `repeat_rate_within_window`, `returning_customer_share`, `new_customer_rate`. The last two are perfectly redundant (one is `1 - other`, and the code literally copies the same p-value across them). Including the duplicate inflates the multiple-testing burden without gaining a real test, so q-values for the truly independent metrics get conservatively biased.

This is not catastrophic (BH stays valid in the sense of bounding FDR; the practical effect is reduced power for valid metrics), but it indicates BH was wired in mechanically.

---

## 3. Moderate Findings

### M-1. Cohort enhancement is half-implemented and asymmetric
`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py:_enhance_candidates_with_cohorts` (line 2587), `_run_cohort_statistical_test` (line 2667).

- `_run_cohort_statistical_test` returns `effect_abs: 0.0, p: 1.0` as a placeholder (lines 2691–2693). So any path that calls it produces no meaningful test.
- In `_enhance_candidates_with_cohorts` line 2644: `if pooled_p < original_p: # Only improve, never worsen`. This is one-sided cherry-picking — cohort pooling can only reduce p, never increase it. Combined with `consistency_bonus` in `pool_cohort_results` (`/Users/atul.jena/Projects/Personal/beaconai/src/utils.py:1235`) that arbitrarily reduces p by up to 20%, this is a confidence-inflator with no statistical interpretation.
- Cohorts in `detect_customer_cohorts` (`/Users/atul.jena/Projects/Personal/beaconai/src/utils.py:1112`) are heavily overlapping (loyal_customers ⊂ recent_active, high_value ⊂ loyal_customers in many stores). Pooling p-values across overlapping cohorts violates the independence assumption Fisher's method assumes — and the code then takes `max` of p (line 1231), which is a different combiner than Fisher's.

Currently this code path is gated by `ENABLE_COHORT_POOLING` (line 2599), which appears off by default — so the impact today is limited. If turned on, it would be a critical issue.

User-visible impact today: limited (off by default). If switched on: same class of issue as C-2.

### M-2. Hardcoded "repeat-rate bias correction" multiplier
`/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` line 1639: `bias_corrections = {7: 1.0, 28: 0.95, 56: 0.90, 90: 0.85}`.

- This multiplies the in-window repeat rate by an arbitrary factor before reporting and before significance testing (the rate is then used to construct x1/n1 for the two-proportion test on line 1728–1730 by `int(round(rep1*id1))`).
- There is no defensible statistical reason for these specific factors. If the goal is to correct for length-biased sampling or cohort-completion bias, the correction should be derived, not pulled from a dict.
- Because it scales the rate AND the integer success count fed to the proportion test, it perturbs both the point estimate AND the test statistic. The significance in `kpi_snapshot_with_deltas` is therefore based on a biased version of the data when this flag is on.

Default is on (`ENABLE_REPEAT_RATE_BIAS_CORRECTION=True` per `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py:593`).

### M-3. Survivorship bias in subscription_nudge and routine_builder audience definitions
- subscription_nudge audience (line 2982): `cohort = rep[rep['orders_product'] >= rep["_thr"]]` — customers who already bought the same product 3+ times in 90 days. Their "conversion" likelihood in the next 28 days is largely the historical probability that frequent buyers re-buy. Recommending "promote subscriptions to people who already act like subscribers" is fine as targeting; presenting their next-28d order rate as a measured-effect of the nudge is not.
- routine_builder audience (lines 3098–3122): customers who recently bought skincare and have only ever bought one product. Their AOV is low by definition, so any "lift" to AOV via bundling is mechanically confounded with their first cross-product purchase regardless of the play.

### M-4. Revenue projections rely on multipliers as if baseline = 0
`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py:calculate_28d_revenue` (line 930):

- `subscription_nudge` (line 991): `base_revenue = converted * aov * first_month_multiplier` where `first_month_multiplier = 1.15`. The audience of "already 3+ same-SKU buyers" was already going to generate revenue. Multiplying their AOV by 1.15 and reporting that as the projected play-attributable revenue treats the entire revenue stream as incremental.
- `frequency_accelerator` (lines 994–1001): `current_frequency = metrics.get('repeat_rate', 0.3) + 0.5` is a heuristic literal — there is no measured "current_frequency" called out in features. Then `freq_lift = 0.20` is a constant per-vertical "lift," and the entire `audience * conversion_rate * current_frequency * freq_lift * aov` is reported as base_revenue. None of the multipliers come from a measured pre/post comparison on this audience.
- `aov_momentum` (lines 1003–1012): uses `aov_growth_rate` from observed data (good) but multiplies by a fixed `growth_acceleration = 1.5` (constant), so the "amplification" is asserted not measured.
- `retention_mastery` (lines 1014–1021): `churn_reduction = 0.07 if vertical == 'beauty' else 0.06` — constant per vertical, not measured for this store. `customer_ltv = aov * 4.5` is also a constant.
- `journey_optimization` (lines 1023–1029): `improvement = 0.30` constant.
- `category_expansion` (lines 1031–1036): `expansion_rate = 0.40` constant.

These are all heuristic projections labeled as `expected_$` and surfaced to merchants in `expected_range` and "28-Day Impact" badges (`/Users/atul.jena/Projects/Personal/beaconai/src/storytelling.py:408`). The numbers are treated as forecasts rather than as model assumptions.

User-visible impact: revenue ranges in the briefing imply data-driven forecasting where the only data-driven inputs are audience size and AOV; the "lift" is from per-vertical constants.

### M-5. `evidence_for_action` mixes labeled heuristics with implicit-evidence claims
`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py:3890` — subscription is honestly labeled `(heuristic)` (line 3906); routine_builder is not labeled (line 3911). Treatment should be consistent.

### M-6. AOV "Welch t-test on per-order net_sales" tests order-level dispersion, not period AOV
`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py:2854–2857` and `kpi_snapshot_with_deltas` line 1698–1701.

The comment on line 2848 acknowledges this: "This tests whether individual order sizes differ, not true period-level AOV." That's correct but not innocuous: the engine reports `effect_pct = (m1 - m2) / m2` and calls it AOV change, then propagates it. Welch t on order-level net_sales gives a p-value about the mean of a heavy-tailed, possibly bimodal distribution (orders with discounts vs without, large-cart vs small-cart). With n in the thousands, p will easily fall below 0.05 for any tiny seasonal shift, even though period-level AOV is structurally a weighted ratio.

Acceptable as a heuristic, but the resulting p is more significant than it should be for what the engine implies it tests.

---

## 4. Low-Priority Findings

### L-1. `_calculate_calibrated_confidence` is dead code
`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py:2151`. Defined but never called. Just remove it; today it has no impact but it confuses readers about which confidence formula is in use.

### L-2. `subscription_nudge` empirical p ignores the 3-month gap between cohorts
`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py:3034–3056`. Cohort A is 90–180 days ago, cohort B is 180–270 days ago. The "next-28d conversion" is then the period right after each cohort end, which is itself a different time of year. This is a between-cohort comparison without seasonality controls. Compounds C-3 but is not the headline issue.

### L-3. Saturation guard uses an estimated customer base
`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py:_estimate_customer_base` line 587: `base = monthly_revenue / max(aov * 1.5, 1e-6)` (i.e., divide monthly revenue by ~1.5×AOV to get estimated active base). This is a heuristic; it works but should be labeled as such in any debug receipts.

### L-4. The Welch t-test in `welch_t_test` returns only a p-value, no effect/SE
`/Users/atul.jena/Projects/Personal/beaconai/src/stats.py:126`. So when called from `_compute_candidates` for `routine_builder` (line 3163), the effect cannot be plumbed even in principle. This is exactly the "Welch-t produces p-value only, no measured effect" memory item — confirmed unresolved.

### L-5. Wilson CI for difference is constructed by combining endpoints incorrectly
`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py:2796–2799`:
```
r1_lo, r1_hi = wilson_ci(x1, n1, alpha=0.05)
r0_lo, r0_hi = wilson_ci(x2, n2, alpha=0.05)
ci_lo_diff = r1_lo - r0_hi
ci_hi_diff = r1_hi - r0_lo
```
This is the Bonferroni-of-marginals construction — it gives a valid but overly conservative CI for the difference. The correct CI for the difference of two proportions has already been computed inside `two_proportion_test` (line 78–84 of stats.py: `ci_low/ci_high` for `p1-p2`). Using that one would be both simpler and tighter.

### L-6. `_calculate_statistical_confidence` is a step function, not a smooth mapping
`/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py:2387`. A p-value of 0.0099 maps to 0.95 confidence; 0.0101 maps to 0.80. The discontinuity is harmless statistically but causes confidence to flicker between p≈0.01 boundaries.

### L-7. `aov_momentum` linear regression on overlapping weekly windows
`/Users/atul.jena/Projects/Personal/beaconai/src/stats.py:calculate_aov_momentum_stats_single_window` (line 582). The "weeks" are constructed as 7-day windows ending at maxd, maxd-7, maxd-14, etc., which are non-overlapping — fine. But the p-value from linregress assumes residuals are independent; weekly AOV is autocorrelated. Reported p will under-state uncertainty. Heuristic acceptable, but not a legitimate p in the strict sense.

---

## 5. False Alarms / Acceptable Heuristics (cleared)

- **`benjamini_hochberg` implementation** (`/Users/atul.jena/Projects/Personal/beaconai/src/stats.py:139`) is correct: standard BH, monotone-from-the-tail, NaN-safe. The bug is in *what is fed to it*, not the implementation.
- **`two_proportion_test`** (`stats.py:34`) is correct: pooled SE for the test, unpooled SE for the CI, optional continuity correction, Fisher fallback for sparse counts in `two_proportion_z_test` (line 108). Good.
- **`welch_t_test`** (`stats.py:126`) is correct via scipy. (Limitations are about how it is used, not the call.)
- **`wilson_ci`** (`stats.py:88`) is correct.
- **`combine_multiwindow_statistics`** (`stats.py:334`) is mathematically correct (Fisher's method for p, inverse-variance weighting for effect, valid SE-based CI). Underused: only called via `enhance_template_action_with_real_stats` for 4 plays.
- **journey_optimization Berkson confound** mentioned in prior memory: the early-half/late-half cross-period definition in `calculate_journey_stats_single_window` (`/Users/atul.jena/Projects/Personal/beaconai/src/stats.py:543–561`) does base "complex_journey_customers" on early-half counts, not full-period counts, which is the fix per commit 554960d. Verified fixed.
- **Seasonal multipliers** (`/Users/atul.jena/Projects/Personal/beaconai/src/utils.py:get_seasonal_multiplier` line 959) are clearly labeled heuristics, not statistical claims.
- **`compute_decay_multiplier`** is a clearly heuristic adjustment that is documented as such.
- **Identity key construction** in `_identity_key` (`utils.py:1441`) is reasonable: prefer email, fall back to customer_id, then billing-name+province. Minor risk of cross-store conflation but defensible for Shopify-like data.
- **`aligned_windows`** (`utils.py:1313`) constructs non-overlapping recent vs prior windows of equal length — correct for a single-window test. The overlap issue is across L7/L28/L56/L90, not within a window's recent/prior.

---

## 6. Status of Prior Known Issues

Based on the memory items provided:

- **Phase 2 hardcoded stats** — partially resolved.
  - Fixed for `frequency_accelerator`, `retention_mastery`, `journey_optimization`, `aov_momentum` *only when multi-window is enabled and `ENABLE_ENHANCED_STATISTICS` is on* (via `enhance_template_action_with_real_stats`).
  - **Still hardcoded in single-window mode for all 5 plays.**
  - **Still hardcoded always for `category_expansion`** (not in the enhanced allow-list at line 4035).
  - subscription_nudge effect is constant 0.05 (line 3074); routine_builder effect is constant 0.08 (line 3148); empty_bottle effect is constant 0.10 (line 3219); discount_hygiene fallback constants exist in `get_effect_params` line 542–546.

- **journey_optimization Berkson confound** — resolved in `calculate_journey_stats_single_window`. Verified.

- **subscription_nudge Phase 4.2 deferred** — confirmed unresolved. Multiplier-vs-baseline conflation in `calculate_28d_revenue` line 991. Survivorship on ≥3-SKU audience confirmed line 2982.

- **routine_builder Phase 4.2 deferred** — confirmed unresolved. Welch-t on prior-cohort AOVs at line 3163 produces a p-value while the effect remains the constant 0.08.

- **Engine output structurally anemic** — out of scope here, but the audit findings (especially C-3 and C-4) confirm that the engine has limited *measured* evidence to surface, even though it surfaces many numeric quantities.

---

## 7. Recommended Minimum Statistical Bar for Phase 1

If the goal is a Shopify app that does not over-promise to merchants, the minimum bar should be:

1. **No hardcoded p-values, q-values, CIs, or effect sizes in any candidate dict.** If a play cannot produce a measured stat, set it to `np.nan` and let the gate/score treat it as "no evidence" rather than "fabricated evidence." This is a one-day fix for category_expansion specifically (`action_engine.py:3614–3632`).

2. **Either drop the cherry-pick merge or replace it with `combine_multiwindow_statistics`.** The combiner is already implemented in `stats.py:334`; rerouting `_compute_multiwindow_candidates` to use it for all candidates (not just the four enhanced ones) is the right call. Until that ships, label confidence as "heuristic" in the briefing for any candidate that went through `_merge_multiwindow_candidates`.

3. **Decouple "p-value present" from "statistical significance asserted."** Plays where the p-value is from a different comparison than the recommended action (subscription_nudge, routine_builder, empty_bottle) should not surface a p-value in any user-visible artifact; the briefing should say "targeting heuristic" not "evidence."

4. **Pick one place where p drives confidence and remove the other three.** Either statistical_confidence(p) OR gate_score's p-term OR signal_bonus's -log10(p) OR safety_multiplier's p — not all four. This is the single biggest source of overconfident PRIMARY tier assignments.

5. **Drop `new_customer_rate` from the BH list in `kpi_snapshot_with_deltas`** since its p is identical to `returning_customer_share`. One-line fix.

6. **Remove `bias_corrections = {7: 1.0, 28: 0.95, 56: 0.90, 90: 0.85}`** or replace with a documented derivation. If you keep it, do NOT apply it before the proportion test — apply it only to the displayed value with a clear "(adjusted)" label.

7. **Be explicit about which revenue projections are heuristic.** `expected_range` and the "28-Day Impact" chip in `storytelling.py:408` should carry a label when the underlying lift constants are per-vertical defaults. Today subscription_nudge bullets are labeled "(heuristic)" in `evidence_for_action:3906`; extend that to all plays whose `effect_abs` is constant.

8. **Disable `ENABLE_COHORT_POOLING` (or remove the dead path).** `_run_cohort_statistical_test` returns placeholder p=1.0 and the pooling logic only-improves p — keeping a switch around half-implemented logic is a future foot-gun.

These steps are all small, none requires redesign, and together they remove the most acute overclaiming risk before merchants see briefings.

---

Files referenced (all absolute):
- `/Users/atul.jena/Projects/Personal/beaconai/ENGINE.md`
- `/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/stats.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/scoring.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/features.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/storytelling.py`
