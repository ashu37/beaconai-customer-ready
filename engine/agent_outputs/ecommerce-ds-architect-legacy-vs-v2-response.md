# DS Architect Response — Legacy vs V2 Beauty Brand Output

## Scientific Verdict

**The legacy output is scientifically indefensible. The V2 output is scientifically defensible but operationally inert on this dataset.** Neither is correct as a final product.

The legacy artifact (`out/legacy_beauty_brand/`) renders three "PRIMARY/QUICK_WIN" plays whose statistics — `journey_optimization` `effect_abs=0.9165`, `ci_low=0.8944`, `ci_high=0.9386`, `p=1e-10` — are template-fabricated and would not survive a half-hour conversation with any analyst. The 95% CI half-width of ±0.022 around an effect of 0.92 implies a standard error of ~0.011 on n=2,686, which is the kind of statistical signature that comes out of a hardcoded baseline (`baseline_rate: 0.15` is even visible in the receipts) being subtracted from a raw conversion proportion, not from a real causal estimate. `frequency_accelerator`'s `p=1e-10` with effect `-0.063` and CI `[-0.102, -0.023]` is similarly saturated. These are not p-values; they are placeholders that the engine has been computing as if they were measured statistics, and the legacy renderer surfaces them as "Strong signal — High confidence — $4,283–$9,043 range." That is the fabricated-statistics failure mode the M0–M9 plan was explicitly built to retire.

The V2 artifact (`out/manual_test_beauty_brand/`) does the right epistemic thing: it abstains soft, leaves `recommendations=[]`, `actions_log.json=[]`, `v2_sizing_shadow.records=[]`, surfaces `materiality_floor=$10,000` against `monthly_revenue=$94,405` (the contract-mandated `max($10k, 3%)` for the $1–5M ARR tier), and refuses to render any dollar headline it can't defend. But the abstain is so total that the artifact contains zero plays, zero considered, zero watching, on a healthy brand with `validation_score: 100, data_quality_grade: A` and 9,620 clean orders. The rejection list — the contract's wow surface — is empty *not because the engine had nothing to consider* but because the V2 spine throws away M3 detect output and re-derives plays from a legacy adapter that drops them all to `targeting`, then suppresses every targeting card because no causal prior exists. This is a structural failure mode, not a data-driven one, and a sophisticated merchant will read the V2 page as "broken" rather than as "honest."

The PM is right that the product surface is unshippable in either form. But the PM's recommended fix ("port legacy's execution plan, channel/sequence/offer/holdout structure, into V2 cards") is risky on its own — most of legacy's "execution plan" content is *also* template-generated text not tied to any measured signal at this store. Bringing the form across without bringing the priors and the detection wiring along would just relocate the trust collapse from "fabricated CI on a card" to "fabricated execution plan on a card." The right fix is narrower than the PM's path: surface the rejection list always (with honest reason codes), wire one measured/directional play that has a real signal on this dataset (`returning_customer_share` is screaming at the engine), and replace the abstain-soft callout's engineering-jargon string. Everything else can wait.

## What The Legacy Output Gets Right

1. **The KPI snapshot is sound.** `out/legacy_beauty_brand/receipts/run_summary.json::aligned.L28` shows correctly computed AOV ($68.71), orders (1,374), net sales ($94,404.94), discount rate (2.69%), returning_customer_share (91.5%), and per-window deltas. The multi-window structure (L7/L28/L56/L90) with prior comparisons is correctly engineered. These are real metrics on a real dataset.

2. **The validation infrastructure runs and reports honestly.** `validation_report.json` reports `overall_status: green`, `validation_score: 100`, `data_quality_grade: A` with 9,620 clean orders, 100% financial completeness, AOV consistency confirmed, no anomalies. This is correct: beauty_brand has clean data and the engine knows it.

3. **The legacy `returning_customer_share` test is a real, defensible measurement.** L28 shows `p = 9.509e-05`, L56 shows `p = 1.5e-30`, L90 shows `p = 4.15e-139`, deltas range from +6.6% (L28) to +257% (L90). These are real two-proportion tests on real cohort splits. The signal is huge and consistent across windows. The engine *correctly identifies* that `returning_customer_share` and `new_customer_rate` are the two measured-significant signals across multiple windows. The failure is downstream — that signal does not connect to any of the recommended plays.

4. **The state-of-store framing ("here's where you are, here's the seasonal context") is the right product chrome.** Aura/Beacon Score aside (it is a confidence-laundering artifact, see below), the underlying observation that this brand is healthy and trending up on returning-customer share is correct.

5. **The execution plan structure is valuable as a *form*.** Audience CSV path, channel, sequence, offer ladder with discount cap, numbered execution steps, holdout percent, success metric — that structure is what a Klaviyo-publishing agent will need to consume. The form is right; the *bindings* between the form and any measured evidence are wrong.

## What The Legacy Output Gets Wrong

1. **`journey_optimization` is template-fabricated, presented as measured.** `candidate_debug.json::journey_optimization` shows `effect_abs: 0.9164898563939408`, `ci_low: 0.8943619988045737`, `ci_high: 0.9386177139833078`, `p: 1e-10`, `q: 1.5e-10`, `confidence_score: 1.0`, `baseline_rate: 0.15`, `effect_floor: 0.1`. The CI half-width of 0.022 around an effect of 0.92 on n=2,686 implies SE ≈ 0.011, which is consistent with a Wald CI on a proportion of 0.95 — i.e. the "effect" is almost certainly the conversion rate itself (or `1 - 0.15` against a hardcoded baseline), not a measured uplift. `p=1e-10` is the saturated lower bound — essentially "p was computed as effectively zero," which is the signature of a degenerate test. **This play is heuristic-only, surfaced as measured. The legacy briefing renders "Strong signal — High confidence — $4,283–$9,043 range" on top of this.** This is the single biggest scientific defect in legacy.

2. **`frequency_accelerator` is similarly saturated.** `effect_abs: -0.063`, `p: 1e-10`, `ci_low: -0.102`, `ci_high: -0.023` on n=2,586. A CI of width 0.079 with `p=1e-10` is internally inconsistent — the implied z-score is enormous, but the ratio of effect to CI half-width is only ~1.6. This is two different statistics being shown side-by-side as if they came from the same test. The `window_effects` field shows L28 effect of +0.011, L56 of -0.071, L90 of -0.194 — *the sign flips between windows* — but the merged record still claims `p=1e-10`. This is the legacy min-p / multi-window cherry-picking failure that M4b was built to retire (see M4b summary: "Legacy `_merge_multiwindow_candidates` ... explicitly compared per-window p-values and replaced `source_window` with the lowest-p window's data").

3. **`retention_mastery`'s CI crosses zero with `p=0.043`, but is rendered "Strong signal."** `candidate_debug.json::retention_mastery` shows `effect_abs: 0.0094`, `ci_low: -0.0303`, `ci_high: 0.0492`. The CI literally includes zero. The play correctly fails the engine's `effect_floor` gate (`failed: ["effect_floor"]`) but is then rendered in the briefing with "Strong signal" badge and a $3,092–$9,276 "expected range." The rendering layer is decoupled from the stats layer: a play whose CI excludes a non-trivial effect is being shown as confident.

4. **The legacy "Strong signal" / "Moderate signal" badges are bucketed labels with no calibration to evidence strength.** `confidence_score: 1.0` for `journey_optimization` is a *saturated* score — the legacy `_calculate_business_confidence` formula multiplies a bucketed p-confidence (0.95 at p<0.001) by gate_score, signal_bonus, and safety_multiplier, all of which are p-derived, so a p of 1e-10 floors at 1.0 by construction. This is the multi-counting-of-the-same-p-value defect the M4b summary explicitly retired (`gate_score + signal_bonus + safety_multiplier` triple-count, plus the bucketed term).

5. **The "Monthly Growth Opportunity" hero (when populated) is a sum of independent forecasts with no audience-overlap correction, no incrementality discount, no scale cap.** Legacy expected_$ for the three actions (journey $6,119 + frequency $3,927 + retention $4,417 = $14,463) violates the V2 invariant `sum(p50) <= 0.25 * monthly_revenue` ratio is 15%, so this passes by accident — but on a smaller store the same logic would routinely produce sum-impact > monthly revenue.

6. **The audiences for `journey_optimization` (n=279), `frequency_accelerator` (n=445), and `retention_mastery` (n=258) overlap heavily** but the engine ranks them as if they were independent. `engine_run.json::scale.customer_base_est` would put the active base around 962 (L28 identified_recent), so 279+445+258 = 982 customers being targeted with overlapping plays is essentially the entire active base counted multiple times. The cannibalization gate is exactly what M5 added; legacy doesn't have it.

7. **The `expected_$` calculation embeds a Klaviyo-style benchmark stack.** `revenue_breakdown.conversion_rate: 0.815, incrementality_base: 0.9, decay_base: 1.0` — the breakdown shows the multiplier stack the M0–M9 review explicitly retired. This is "vertical benchmarks treated as causal lift" rather than "observed effect on this store."

8. **`expected_$` differs between `actions_log` ($6,119) and `backlog` ($7,955) for the same `journey_optimization` candidate** — different incrementality/decay multipliers applied to different paths. This is the kind of artifact that suggests the sizing layer is not a single function with provenance.

9. **The `Aura Score` (`overall: 77, tier: healthy`, components revenue_health=85, customer_health=98.6, margin_health=58.6, growth_health=65, ltv_health=49.1) is a confidence-laundering composite.** It is a convex combination of metrics with no clear product use, no calibration, and no documentation of what "85/100 revenue_health" actually means causally. The merchant reads "Healthy 77" as a verdict; it is just five rescaled KPIs averaged together. This should not survive into V2 in any form.

## Classifying Each Legacy Play

Per the M4b `TARGETING_RECLASSIFY_PLAYS` set (`subscription_nudge`, `routine_builder`, `empty_bottle`, `category_expansion`, `bestseller_amplify`, `vip_no_discount_nurture`, `replenishment_reminder`) and the substantive evidence each play carries on this dataset:

- **`journey_optimization`** — **heuristic-only**, dressed as measured. The "effect" of 0.9165 is structurally a conversion-rate-vs-hardcoded-baseline calculation, not a causal estimate. Should be reclassified as `targeting` or removed from the legacy emitter outright. The `[Enhanced with real multi-window statistics: L28, L56, L90]` annotation is misleading because what is "enhanced" is the cosmetic composition of three saturated p-values, not the underlying validity of the test.
- **`frequency_accelerator`** — **directional at best, mis-labeled measured**. The L28/L56/L90 effects are +0.011 / -0.071 / -0.194 — sign-disagreeing across windows. Under M4b's `compute_consistency_across_windows` semantics this would yield consistency=0 (no agreement with any combiner sign). The `p=1e-10` is the legacy min-p artifact, not a Fisher-combined statistic. Genuine evidence class on this dataset is `weak` or `directional`, not measured.
- **`retention_mastery`** — **directional**. p=0.043 at L28, but CI `[-0.030, +0.049]` crosses zero, and the engine itself marks `failed: ["effect_floor"]`. This is a legitimate "we see something small but it's below our material-effect floor" outcome; legacy correctly demotes it to `Watchlist` but then renders it with "Strong signal" badge anyway, which is the labeling defect.
- **All non-emitted plays** (`subscription_nudge`, `bestseller_amplify`, `category_expansion`, `routine_builder`, `empty_bottle`, etc.) — **targeting-only**. Per the M4b reclassification set. They should never carry merchant-facing p/q/CI/effect.

So the answer to "what evidence class is each play on this dataset?": one heuristic-fabricated, one weak/directional with sign instability, one directional-below-floor, zero genuinely measured. The legacy briefing surfaces them as one "Strong" PRIMARY and two "QUICK_WINS" with high-confidence chips. That is the gap.

## What The V2 Output Gets Right

1. **No fabricated stats anywhere in the merchant-facing artifact.** `briefing.html` contains no `p =`, `q =`, `CI`, `confidence_score`, `final_score`, or numeric confidence percentage. Verified by inspection of the file. The forbidden-string contract holds.

2. **Decision state is correct given the inputs.** `engine_run.json::abstain.state="abstain_soft"` is the right call when zero measured/directional plays cleared the gates. `recommendations=[]` is consistent. `data_quality_flags=[]` is consistent (no anomalies were detected).

3. **Scale-aware materiality is computed correctly.** `scale.materiality_floor: $10,000` against `monthly_revenue: $94,404.94` ≈ 10.6% of monthly revenue. For a $1.1M ARR brand, the contract specifies `max($10k, 3%)` for the $1–5M tier — $10k is the binding constraint here (3% of $94k ≈ $2.8k), so the floor is correctly the $10k absolute minimum. This is the kind of scale-aware reasoning that should be invisible to the merchant but defensible to a sophisticated reviewer.

4. **State-of-store paragraph is structurally honest.** `state_of_store[].text` produces `"AOV (L28): $69 (1.7% vs prior). Repeat rate (L28): 34.0% (-3.7% vs prior). Orders (L28): 1374 (0.0% vs prior)."` — three typed Observations, each with a metric, value, and delta. No statistical signature, no jargon, no derived score.

5. **Receipts are internally consistent.** `actions_log.json=[]`, `candidate_debug.json::counts.actions=0`, `v2_sizing_shadow.records=[]`, `recommendations=[]` all align. The V2 stack does not produce a single number it can't trace back to a driver.

6. **`debug.html` is correctly separated.** Banner intact, internal-only, not linked from `briefing.html`. Internal stats (which on this run are absent because no measured play surfaced) would appear here, not in the merchant view.

7. **`new_customer_rate` BH dedup is in effect.** `run_summary.json` (V2) shows `new_customer_rate.p: null` where legacy showed `9.5e-05` — this is the M4a T4a.6 correctness fix removing the duplicate hypothesis test that was previously double-counted. (Mechanically: `new_customer_rate = 1 - returning_customer_share`, so the two BH entries were testing the same hypothesis. The dedup is correct.)

## What The V2 Output Gets Wrong

1. **The engine has zero recommendations not because there is no signal in the data — there demonstrably *is* signal (`returning_customer_share` at L28 with `p=9.5e-05`, +6.6% delta) — but because the V2 spine doesn't carry that signal to any play.** The PM correctly identified this in Question 2. The architectural defect is in `engine_run_adapter.py::_coerce_evidence` defaulting unmapped plays to `targeting`, combined with M3 detect not feeding `decide()` with measurement on the candidates it builds. The result: the only path to a measured card is through the legacy emitter, and the legacy emitter only emits the three template-fabricated plays this analysis already flagged as fabricated. There is no measured pathway *for any genuine signal in the data* on the V2 spine. **This is a wiring defect, not a conservative gate.**

2. **The rejection list is empty even though plays were considered.** `engine_run.json::considered=[]`. But `out/legacy_beauty_brand/candidate_debug.json` shows the legacy emitter built three candidates (`frequency_accelerator`, `retention_mastery`, `journey_optimization`) and the legacy run also emitted `subscription_nudge`, `bestseller_amplify`, `category_expansion`, etc. into segments. The V2 receipts give zero record of any of these being considered. The contract's wow surface — "we thought about X, here's why we held it" — is structurally absent on a brand where the engine objectively *did think about* eight or nine plays. This is the M3-detect-not-wired-into-decide defect surfacing as a product gap.

3. **The Watching builder is too strict.** `state_of_store` has `Orders (L28): 1374 (0.0% vs prior)` with `classification="held", change_magnitude=0.0`. Per `src/decide.py::build_watching` (M7 summary), HELD observations require non-zero `change_magnitude` to become `WatchedSignal` entries. So a perfectly flat orders metric on a healthy brand produces zero watching signals. **The right Watching surface for this dataset is `returning_customer_share`** — it is the most significant, most consistent, most directional signal across all four windows (L7 p=0.198 directional, L28 p=9.5e-05, L56 p=1.5e-30, L90 p=4.2e-139) with a +6.6% L28 delta — but `returning_customer_share` is not in the M7 watching threshold table (which is hardcoded to `aov`, `repeat_rate_within_window`, `orders` per the M7 summary "remaining risks #4"). So even when V2 has a real signal in the data, it can't surface it because the schema only watches three metrics.

4. **The abstain-soft reason text is engineering jargon.** "no measured or directional recommendation cleared materiality + cannibalization gating" appears verbatim in `briefing.html` and `engine_run.json::abstain.reason`. The PM is right that this is the load-bearing sentence and it's the most jargon-leaky string in the merchant view. Scientifically honest, narratively unusable.

5. **The page subtitle promises content that isn't there.** `briefing.html` subtitle: "No measured opportunities cleared; review the considered list and watching signals." Both lists are empty. The page directs the merchant to surfaces it doesn't render.

6. **The `repeat_rate_within_window` value differs between legacy and V2** (PM Q1). Legacy `run_summary.json` L28: `0.3229`, V2 L28: `0.3399`. Same anchor date. The 1.7% absolute difference is consistent with the M4a `ENABLE_REPEAT_RATE_BIAS_CORRECTION` default flip (true→false), which removes a survivor-bias correction that legacy was applying. **V2's number (0.3399) is closer to the raw observed value; legacy's (0.3229) is the bias-corrected value.** Neither is "wrong" per se, but the M0–M9 plan turned the correction off without surfacing it, and the merchant-facing copy now says "Repeat rate: 34.0%" without telling the merchant the methodology changed. Internally we know which is right; externally, both numbers are floating around.

7. **`materiality_floor: $10,000` is rendered without explanation.** The DQ footer says "Materiality floor: $10,000" with no merchant-facing definition. A non-technical operator has no model for what this number does.

8. **`v2_sizing_shadow.records=[]` is uninformative.** The shadow file's purpose was to show V2's would-be sizing vs legacy's `expected_$` (per M6 summary: "V2 p50 should be smaller than legacy on heuristic plays"). On this run there were no recommendations to size, so there's nothing to compare. The PM's Q4 is right: shadow records for the *suppressed* legacy candidates would actually answer the question "what does V2 think these plays are worth, given that legacy thinks $14,463?"

## Evidence / Claim Assessment

Quoting specific receipts fields:

| Claim source | Field | Real or fabricated? | Comment |
|---|---|---|---|
| Legacy `candidate_debug.json::journey_optimization.effect_abs` | `0.9165` | **Fabricated / template** | Equals `1 - baseline_rate (0.15) - some adjustment`; matches the conversion-rate pattern, not an uplift |
| Legacy `candidate_debug.json::journey_optimization.p` | `1e-10` | **Saturated lower bound** | Numerical floor, not a real p-value |
| Legacy `candidate_debug.json::journey_optimization.ci_low/high` | `[0.894, 0.939]` | **Fabricated** | Wald CI on a proportion, not on an effect |
| Legacy `candidate_debug.json::journey_optimization.confidence_score` | `1.0` | **Saturated** | Multi-counted p-value formula floors at 1.0 |
| Legacy `candidate_debug.json::frequency_accelerator.p` | `1e-10` | **Min-p cherry-pick** | `window_effects` show sign flips L28→L56→L90 (+0.011, -0.071, -0.194); the merged record reflects min-p selection from one window, not Fisher combination |
| Legacy `candidate_debug.json::frequency_accelerator.ci_low/high` | `[-0.102, -0.023]` | **Real for one window, mis-presented as multi-window** | The CI is for the L90 window's effect; merged record presents it as if it applied to a combined estimate |
| Legacy `candidate_debug.json::retention_mastery.p` | `0.0434` | **Real** but |effect|=0.94% with CI crossing zero | Engine correctly fails effect_floor; renderer over-states confidence |
| Legacy `run_summary.json::aligned.L28.p.returning_customer_share` | `9.5e-05` | **Real** | Genuine two-proportion test; large effect; not connected to any recommended play |
| Legacy `run_summary.json::aligned.L56.p.discount_rate` | `0.00178` | **Real, directional** | -15.4% delta; could feed `discount_hygiene` if priors allowed it to size |
| Legacy `actions[].expected_$` | `$6,119, $3,927, $4,417` | **Heuristic forecast** | Audience × baseline_rate × benchmark stack (incrementality, decay, conversion_rate); not store-observed |
| Legacy `actions[].confidence_label` | `"High"` | **Mis-calibrated label** | Bucketed from saturated `confidence_score=1.0`; not a calibrated probability of effect |
| V2 `engine_run.json::abstain.state` | `"abstain_soft"` | **Honest** | Correct given zero measured/directional cleared gates |
| V2 `engine_run.json::scale.materiality_floor` | `10000.0` | **Defensible** | Contract-mandated for $1–5M tier |
| V2 `engine_run.json::state_of_store[].text` | "Repeat rate (L28): 34.0% (-3.7% vs prior)" | **Real** | But methodology change vs legacy not surfaced |
| V2 `engine_run.json::considered=[]` | empty | **Defect** | Legacy considered ≥3 plays; V2 spine doesn't surface them |
| V2 `engine_run.json::watching=[]` | empty | **Defect** | `returning_customer_share` is a real, persistent, directional signal not in the watching schema |

So among legacy's PRIMARY/QUICK_WINS surface: **0 measured, 1 directional below floor, 2 heuristic-as-measured**. Among V2's surface: **0 measured, 0 directional, 0 surfaced — but real signal exists in the data and is being swallowed by the architecture**.

## Decision-Logic Assessment

V2 *correctly* separates measured evidence from targeting/business logic at the structural level:

- `evidence_class == "targeting"` ⇒ `measurement is null` (M4b contract, enforced by `_build_measurement_from_legacy` early-return).
- Targeting cards never carry standalone dollar headlines (M8 invariant, pinned by `tests/test_targeting_no_dollar_headline.py`).
- Targeting plays without causal priors are suppressed by the M6 sizer (`v2_sizing_shadow.json` shows `suppressed=true` with `suppression_reason="targeting_non_causal_prior"` on previous fixtures).
- Measured plays go through `combine_multiwindow_statistics` (Fisher + inverse-variance), not min-p selection (M4b combiner reroute, pinned by `test_legacy_min_p_path_not_used_on_v2_combiner_output`).
- `consistency_across_windows` is a pre-combination sign-agreement count, not a p-vote (M4b, pinned by `test_not_a_p_value_vote`).

These are all real, defensible, and tested.

But V2 *fails* to translate that separation into a useful product because:

- The M3 `detect_candidates()` pure builders exist but do not feed `decide()`. M7 explicitly composes the existing legacy-adapter EngineRun rather than rebuilding from M3 candidates (per M7 summary: "M3 candidate detection is not re-wired into `decide()`").
- The legacy adapter's `_coerce_evidence` defaults unmapped values to `TARGETING`, so the only plays the V2 spine sees are reclassified as targeting before they can carry measurement.
- M5/M6/M7 then correctly suppress targeting plays without causal priors, *but the architectural mistake was that no path to "measured" exists for any real signal at this store.*

This is the *correct* statistical behavior given the inputs, but the inputs are wrong. The DS Architect's task is to call this out: V2 isn't being too conservative in its gates — it is being correctly conservative on a feed of plays that has been pre-reclassified to all-targeting by the adapter. The fix is upstream, not in the gates.

## Materiality Assessment

The materiality logic is scientifically correct and practically sensible:

- Tiered floor: `<$1M → max($5k, 2%)`, `$1–5M → max($10k, 3%)`, `>$5M → max($25k, 5%)`.
- For beauty_brand: $94k monthly revenue × 12 ≈ $1.13M ARR → $1–5M tier → `max($10k, 3% × $94k) = max($10k, $2.83k) = $10k`. Receipt confirms `materiality_floor: 10000.0`. Correct.

But the materiality floor's *interaction* with the spine has a defect that should be acknowledged:

- The floor is binding-by-default on small-mid stores because $10k absolute > 3% scaling for any store under $333k monthly revenue (i.e. $4M ARR). Below that, the absolute floor dominates and is independent of the store's signal-to-noise ratio.
- The PM's Q5 is right to ask: would `discount_hygiene` clear a $5k floor? Looking at `discount_rate` at L56 (`p=0.00178`, delta=-15.4% on a base of 2.94%), the absolute revenue impact of a discount-hygiene play is plausibly in the $2k–$8k range on this brand. It would *not* clear $10k. Whether the floor should be lower for beauty specifically is a calibration question — but lowering it without empirical realization data is itself a fabrication.
- **The right answer to "should the floor be lower" is "we don't know yet, but the calibration stub is the place where we'll know once we have realization data."** Today the M9 calibration stub returns `{}, {}, {}`. Once we have N>=10 published plays with realized revenue lift, `materiality_overrides` is the field where a beauty-specific floor calibration lives. Lowering the floor pre-emptively is fabrication; lowering it post-calibration is science.

The **practical concern** is that the binding $10k floor combined with all-targeting reclassification means *no play can ever fire* on a sub-$1M-ARR beauty store. That is a structural product dead-end, but the fix is to put a measured pathway upstream, not to lower the floor.

## Is The Current Abstain Behavior Appropriate For This Dataset?

**No — but not for the reason the PM gave.**

`abstain_soft` is the *technically correct* state for "zero measured/directional cleared the gates." But the dataset has real, defensible signal at multiple windows (`returning_customer_share`, `discount_rate`) — the engine has *plenty* to say. The abstain is being triggered by a wiring defect (M3 detect not feeding decide), not by an actual absence of evidence.

The right decision states for this dataset under a correctly-wired engine would be:

- **One PUBLISH-eligible measured/directional play tied to `returning_customer_share`** (a `first_to_second_purchase` or `at_risk_repeat_buyer_rescue` play that uses the +6.6% L28 returning-share signal).
- **A populated Considered list** with the heuristic plays held for cause: `journey_optimization` held for "no measurement design supports this play at this store"; `bestseller_amplify` held for "targeting-only with non-causal vertical prior"; `subscription_nudge` held for "targeting-only with non-causal vertical prior"; etc.
- **A Watching entry** for `discount_rate` (L56 directional, L90 directional but inconsistent) and `returning_customer_share` (signal magnitude is too large to ignore but no causal play wires from it yet).

Under the *current* architecture, abstain_soft is the only legal outcome. Under the *correct* architecture, this dataset should produce one PUBLISH and a substantive considered list. The abstain is the symptom; the cause is M3-detect-not-wired-and-no-measured-play-uses-returning-share.

## Recommendation Types That Are Scientifically Valid

Per the M0–M9 reconciled plan and the data we see in this fixture, three recommendation types can be scientifically honest *without* requiring measured-lift claims:

1. **Measured play with observed effect** — requires `evidence_class="measured"`, non-null `Measurement.observed_effect` from a real two-sample test on store-observed data, `consistency_across_windows >= 2`, `n >= min_n`, `p_internal < 0.05` (internal only, not rendered). Example for this dataset: a `first_to_second_purchase` play that uses the `returning_customer_share` measurement directly.

2. **Directional play with sign-stable signal across windows but below-effect-floor magnitude** — requires real per-window stats, sign agreement on ≥2 windows, but combined effect smaller than the M5 effect_floor. Renders as Emerging confidence, no $-headline (range chip only if a causal prior exists), explicit "Watching for confirmation" framing. Example: `discount_hygiene` on L56 (real p, real direction) but small effect.

3. **Targeting play (audience-only, no measured lift claim)** — requires evidence_class="targeting", measurement=null, audience definition, AOV reference. Renders with mandatory disclaimer: "This is a who-to-send-to recommendation, not a measured-lift forecast." No $-headline. Example: `bestseller_amplify` (audience exists, no causal prior, just "send to top buyers").

Specifically **forbidden**: (a) any heuristic play surfaced as measured (legacy `journey_optimization` is the canonical violation); (b) any benchmark-derived dollar projection on a targeting card; (c) any "Strong signal" / "High confidence" badge that is not derived from a real `p_internal` on real per-window stats; (d) any sum-of-impact hero number that isn't capped at 25% of monthly revenue and isn't audience-overlap-corrected.

Specifically **allowed but not yet implemented**: a **structural recommendation** type — "your store is healthy, here's what we're watching, no play this month" — when the evidence is genuinely thin. This is the "graceful degradation" path the PM correctly identified as missing.

## What Evidence Should Be Required For Each Recommendation Type

- **Measured** ⇒ store-observed effect from a two-sample test on store data; n ≥ play-specific min_n; p_internal < 0.05; CI excludes zero in the same direction; consistency_across_windows ≥ 2; effect ≥ effect_floor; sized using observed effect, not benchmark.
- **Directional** ⇒ store-observed effect; sign agrees across ≥ 2 windows pre-combination; p_internal < 0.10 or one-sided p < 0.05; effect may be below-floor; sizing suppressed (range-chip only if a causal vertical prior exists).
- **Targeting** ⇒ audience can be deterministically built from the data; minimum audience size (typically 50+); no measurement claim; sizing suppressed unless a causal prior exists; mandatory disclaimer.
- **Structural / "do nothing"** ⇒ all of: no measured plays cleared; healthy data quality (`grade: A`); no anomalies; rendered as a dignified "this is a healthy month" memo, not three empty placeholders.

## What Claims Should Be Allowed Or Forbidden

Allowed:
- "We observed `metric` change by X% (n=N) over the window."
- "Audience: K people meeting these criteria."
- "Estimated range $X–$Y based on `<vertical_prior, source_class=causal>` for stores like yours" (only when a causal prior exists).
- "We held this play because <specific reason from the rejection enum>."
- "We're watching `metric` because <delta description>; we'll act if <threshold>."

Forbidden:
- "Strong signal / High confidence" without a tied calibrated probability.
- Single dollar hero forecasts on a targeting card.
- Multi-window p < 0.0001 type claims when one of the windows had a sign disagreement.
- Aggregated "monthly opportunity" sums uncorrected for audience overlap.
- Any benchmark-derived effect presented as if it were store-observed.
- Saturated `confidence_score: 1.0` displayed as confidence.
- Composite "health scores" (Aura/Beacon) as a product claim.

## Practical Scientific Recommendation

**The smallest scientifically valid change that improves usefulness:** wire the M3 detect path into `decide()` for the one play type that has a real signal on this dataset, and surface the rejection list always.

Concretely (in priority order):

1. **Surface the rejection list always.** Even on this run, the legacy emitter built three candidates and the audience-builder considered ≥6 plays. Have `decide()` populate `considered[]` with deterministic reason codes for every play that was detected/considered but didn't recommend, even when `decision_state == abstain_soft`. Reason code enum already exists. This single change converts the empty page into a "we considered 8 plays, here's why we held each" page. **No new claims required; this is purely surfacing audit-trail information that the engine already has.**

2. **Add `returning_customer_share` to the Watching threshold table** in `src/decide.py::build_watching` (M7 hardcoded list of `aov`, `repeat_rate_within_window`, `orders`). This is a 5-line change. The signal is real (L28 p=9.5e-05, +6.6% delta), persistent across windows, and cannot honestly be ignored. Add a fourth metric and a threshold-to-act template ("Reach out to your data team if this drops below X% / climbs above Y%"). The Watching surface stops being empty on healthy brands.

3. **Replace the abstain-soft callout reason text.** The PM's exact rewrite is the right move: "Your store is in good shape this month. We didn't find a play with strong enough evidence to recommend. Here's what we're watching." Two strings, one PR. This is the single most-jargon-dense five words on the merchant page.

4. **Author one causal prior** for `first_to_second_purchase` or `at_risk_repeat_buyer_rescue` keyed off `returning_customer_share` movement, scoped to `vertical: beauty`. Mark it `source_class: causal` with `applies_to: {vertical: beauty}` and *explicitly note in `priors.yaml` what evidence the causal claim rests on* (e.g. "based on N published runs from beauty merchants where the play realized X% reactivation"). This is the keystone change that lets V2 produce a non-empty Recommended on this dataset. **Without this, the engine is structurally locked into ABSTAIN_SOFT for beauty.**

5. **Wire one M3 audience builder through to a measured PlayCard** in the V2 spine. The legacy adapter's `_coerce_evidence` defaulting to TARGETING is the choke point. For one play (the same first_to_second/at_risk play), have M3 detect produce a Candidate with the `returning_customer_share` measurement attached, and have the M7 `decide()` consume that Candidate as measured-class with the M6 sizer producing a non-suppressed range from the causal prior. This is the "Detect → Size → Recommend" spine the M0–M9 plan promised but didn't ship.

What I am **not** recommending:
- Do not ship legacy as the merchant artifact. The fabricated CIs are unrecoverable on inspection.
- Do not "port legacy's execution plan" wholesale into V2 (PM #5). Most of the execution plan content is template-generated and would just relocate the trust collapse.
- Do not lower the materiality floor pre-empirically.
- Do not reintroduce the Aura/Beacon composite score in V2 in any form.
- Do not flip `ENGINE_V2_OUTPUT=true` as the default until the considered-list-always change ships and the abstain-soft text is rewritten. Today's V2 page is too austere to be the merchant-facing default.

## Risks / Guardrails

1. **Causal-prior authoring is itself a fabrication risk.** Authoring "this play has a causal lift of X%" without realization data is the same defect the M0–M9 plan was built to retire. The mitigation: every `causal` prior must have a `source` field that names the realization data it rests on, the N runs that produced it, and the date of the most recent calibration. A causal prior with N=0 underlying observations is no better than an expert prior dressed up.

2. **Adding `returning_customer_share` to Watching is safe; using it as a ranking input is not.** The metric is observational and confounded by cohort definition. Using it as a watching signal ("we'll act if this drops below X%") is honest. Using it as the basis of an "expected revenue lift" projection on a play that targets it would re-introduce the legacy defect.

3. **The M3-detect-into-decide wiring is the single most fragile change.** It will require the Candidate schema to optionally carry measurement when the play is detected from a real per-window stat (e.g. `first_to_second_purchase` reading `returning_customer_share`), without re-introducing the forbidden `p`/`q`/`CI` fields on the Candidate dataclass for plays that don't have them. The M3 contract was "no statistics on Candidate"; the right move is to add an optional `Measurement` block, not to leak per-stat fields onto Candidate.

4. **Beware of "anchor metric drift."** Legacy and V2 are reporting different `repeat_rate_within_window` values for the same anchor (0.3229 vs 0.3399) due to the M4a bias-correction default flip. This is invisible to a reviewer who hasn't read the M4a summary. If the V2 page becomes the default merchant artifact, the founder will see a 1.7-point shift in the headline repeat-rate metric on the *same data* across the cutover. Document this prominently or freeze the methodology choice with a versioned `metric_version` string in the briefing footer.

5. **`v2_sizing_shadow.records=[]` is silent failure.** When there's nothing to size, the file is empty — and the founder cannot tell whether the engine had no candidates or whether the shadow logic broke. Recommend: emit shadow records for *suppressed* candidates as well (not just for non-suppressed ones), so the file shows "we considered N candidates, sized M as suppressed, would have produced $X p50 on each." This is what the PM's Q4 was driving at and it's right.

6. **The `Aura Score` is still being computed in the V2 path** (`run_summary.json` shows `aura_score.overall: 77, tier: healthy`). It is not surfaced in the V2 briefing.html, but it is still in receipts. As long as it's not rendered, this is fine. But any future agent reading receipts could re-introduce it. Recommend: kill the Aura computation entirely in V2-default mode, or at minimum, gate it behind an explicit "legacy_compat" flag.

7. **The M9 outcome log is currently writing records of an engine that produces nothing.** `recommended_history.json` will accumulate empty `recommended[]` records. That's correct behavior, but when calibration eventually reads this file, it will see "100 runs, 0 recommended plays, 0 realized lift" and the calibration stub will (correctly) return `{}, {}, {}` forever. **The calibration loop cannot start until the engine starts publishing.** This is a bootstrapping risk: V2 needs at least one real published recommendation to start producing realization data, which means the causal-prior authoring (#4 above) is not optional for the long-term ML readiness story — it's the entry condition.

8. **Open question on `frequency_accelerator` reclassification** (PM Q7). It is *not* in the M4b `TARGETING_RECLASSIFY_PLAYS` set, which suggests V2 considers it measured/directional. But the L28/L56/L90 effects of +0.011/-0.071/-0.194 sign-flip across windows; under M4b's `compute_consistency_across_windows` semantics this would yield consistency=0. So either (a) frequency_accelerator should be added to the targeting reclassification set because its multi-window stats are unreliable on most stores, or (b) it should be allowed to surface as directional with `consistency_across_windows=0` and ranked accordingly (which would mean it correctly never reaches PUBLISH on this dataset). My recommendation: option (b) — let the consistency check do its job rather than hardcoding the reclassification.

9. **Open question on the `journey_optimization` candidate**. The legacy emitter is still building it. M4b reclassifies it as `targeting`, which suppresses its stats. But the cleaner fix is to *remove the candidate entirely* from the legacy emitter — it is a template that has no measurement design at this store and no causal prior anywhere, so its only product role is to produce a confused targeting card. The PM's Q3 is right to suggest deletion over reclassification.
