# BeaconAI Decision-Core Redesign — Skeptic / Red-Team Review

**Scope:** Adversarial review of the DS Architect's proposed three-stage decision core (`agent_outputs/ecommerce-ds-architect-initial.md`) building on `agent_outputs/statistical-code-reviewer-initial.md`.

**Stance:** Harshest reasonable read. Two reviewer personas:
1. A skeptical $1.2M-ARR DTC merchant who got burned once by an analytics tool.
2. A staff DS reviewer who has watched Shopify analytics products overclaim for a decade.

---

## Executive Verdict

- **The redesign cleans up the worst overclaiming, but it does not solve overclaiming.** It moves the lie from "p = 0.03" to "$3,500–$8,200 (p50 $5,500)." Merchants will still budget against a single number, and the engine still has no closed loop to discover the number was wrong.
- **The 4-bucket vocabulary (MEASURED / DIRECTIONAL / TARGETING / WEAK) is uncalibrated, untested, and unmoored from any validation.** Architect calls it "calibrated" without defining the calibrand. On a typical small DTC brand, the entire briefing will be TARGETING / WEAK; merchants paying for "data science" will see "we mostly assumed things" and churn. The design has no plan for that failure state.
- **MEASURED is aspirational at MVP scale.** With 90 days of orders and ~1.5K customers, the only plays that can plausibly hit MEASURED on a stable signal are winback and discount_hygiene, and even those will fail power frequently. Most months, on most stores, the new engine will be a DIRECTIONAL/TARGETING list — i.e., a slightly-better-labeled heuristic recommender. The architect doesn't say this out loud.
- **No abstain mode is a showstopper.** The architect lists what the engine should output but never the case "we have nothing defensible to recommend this month." Without an explicit refusal path, every merchant gets a forced ranked list every month, which is the original problem in a new font.
- **Cannibalization, inventory-OOS, fatigue, and audience-overlap are entirely absent from the redesign.** Stage 4 sizes plays as if each were the only one launching. A merchant who runs three "PRIMARY"-tier recommendations into the same 800-person audience in the same 28 days will discover the engine double- and triple-counted revenue. This is the failure that ends the trial.
- **The architect undersells the blast radius of "Phase 1 is small."** Reclassifying 4 plays as targeting-only, decoupling seasonality from confidence, and collapsing the tier matrix have second-order effects on briefing structure, scoring weights, and downstream Klaviyo/agentic consumers. Calling it "no new statistical machinery" is true but also misleading — the product surface and contract change materially.

---

## A. Merchant trust failure modes the design doesn't address

### A-1. The 4-bucket vocabulary is jargon laundering, not plain language
**Claim challenged:** "MEASURED / DIRECTIONAL / TARGETING / WEAK" is a clear label set a non-statistician merchant will parse correctly (architect, lines 110–117, 248).

**Why it doesn't hold up:** "Directional" is a DS-internal term. A merchant reading "Directional signal in your data" will read it as "this works." "Targeting" is even worse — to a marketer, "targeting" means "audience selection," not "we have no evidence this play works." A merchant told a play is a "Targeting recommendation" will hear "we picked the right people for you" and infer the play is validated.

**Specific failure scenario:** Merchant launches a TARGETING-labeled subscription_nudge for 320 customers, sees no lift, asks support: "It said it was a targeting recommendation — was it not supposed to convert?" Support has no answer that is both honest and reassuring.

**Severity:** Serious. Renaming labels without user testing is the same overclaiming risk in a new font.

### A-2. The design has no plan for the "80% TARGETING briefing"
**Claim challenged:** The 4-bucket vocabulary works regardless of bucket distribution.

**Why it doesn't hold up:** On a $500K–$2M ARR brand with 1–3K customers and 90 days of data, ~70–90% of plays will be TARGETING or WEAK most months. The architect never says what the briefing looks like in that case. There is no fallback presentation, no "we have no measured opportunities this month, here are best-effort targeting ideas," no merchant-facing acknowledgement that this is the expected state for small stores.

**Specific failure scenario:** Month 1 briefing for a 90-day-old store: 6 of 7 plays are TARGETING. Merchant reads it as "this product mostly guesses." Cancels.

**Severity:** Showstopper for product-market fit on the long tail of merchants the app will primarily serve.

### A-3. `p_action` for heuristic plays is Benchmark-as-Lift renamed
**Claim challenged:** Stage 4's `audience × p_action × incremental_orders × AOV` formula (architect, lines 124–137) is honest because `p_action` is "declared as an assumption with a vertical-derived range, not a point."

**Why it doesn't hold up:** A range is two points. The merchant gets p10/p50/p90 — three points — and ranks against p50. The source of `p_action` for a heuristic play is still Klaviyo/Bloomreach observational benchmarks the audit explicitly flagged as Benchmark-as-Lift (audit C-1 territory; architect's own anti-pattern #4). Wrapping it in a range chip with `assumption_source = "vertical_prior"` does not change the underlying number; it changes the label on it. The architect even concedes this implicitly in lines 195–199 ("range based on the literature… do not collapse to a point") and then the design proceeds to pick p50 as the ranking signal, collapsing it to a point.

**Specific failure scenario:** Architect says category_expansion `p_action` range is "5–25%." Engine ranks on p50 = 15%. Merchant budgets against $5,500. Reality: 2%. Engine has no learning loop to update the prior. Same overclaiming, new chip.

**Severity:** Showstopper for the agentic future state. If Klaviyo Publisher consumes p50 as the budget input, this metastasizes.

### A-4. "Range based on observed audience behavior" is still seasonality
**Claim challenged:** For evidence-based plays, `p_action` is "derived from store data (e.g., observed repeat rate uplift)" (architect, line 132).

**Why it doesn't hold up:** Per the audit, observed period-deltas are noisy seasonal/mix-shift snapshots, not effects (architect's own anti-pattern, lines 60–62). The redesign re-uses these snapshots as the input to a 28-day forecast. Calling them "audience behavior" instead of "effect estimate" is a relabel, not a fix. A merchant who sees "Repeat rate dropped 4 points in the last 28 days vs prior 28; that holds in 56 and 90" (architect's own example, line 249) will treat that as a forecastable trend even though the "holds in 56 and 90" is a tautology of nested windows.

**Severity:** Serious. The architect names this anti-pattern then keeps doing it under a new name.

---

## B. Revenue realism

### B-1. Range-as-defense doesn't survive contact with budgeting
**Claim challenged:** Vertical priors as range bounds (architect, lines 132–137, 250) protect against overclaiming because merchants see uncertainty.

**Why it doesn't hold up:** Merchants don't budget against ranges; they budget against the midpoint or the upper end. Every CFO conversation collapses a range into a number. A range chip changes the legal posture, not the budgeting behavior. Worse, with no calibration loop, the engine has no way to discover that its p50 was high by 3x — which is the audit's prediction (`expected_$` overstated by 3–5x via missing email-open-rate adjustment alone, audit / architect line 205).

**Specific failure scenario:** Merchant runs three months of recommendations, allocates $4K/mo to ad spend against engine forecasts. After three months: realized vs forecasted is 0.25x. Merchant has no way to attribute the miss to engine miscalibration vs execution vs noise. Trust gone.

**Severity:** Serious. This is the slow-death failure mode.

### B-2. No mechanism for merchants to discover an overstated range
**Claim challenged:** "Show the merchant which input drove the range. If the merchant changes `p_action` later, the projection should update." (architect, line 137)

**Why it doesn't hold up:** Merchants don't know what `p_action` should be. That's why they're paying for the engine. Letting them edit the assumption is a punt. The design has no post-publish reconciliation — no "you forecasted $5,500, you got $1,100, here's what we'll change for next month" UI or logic. The architect explicitly defers this (line 234, "Play-effect calibration loop … belongs to the agentic future state, not Phase 1") which is the same as saying "Phase 1 ships uncalibrated and stays uncalibrated."

**Severity:** Showstopper for an MVP that bills itself as "data scientist replacement."

### B-3. p50 as ranking signal is still a number that drives decisions
**Claim challenged:** "Single ranking signal: expected revenue, p50 (median of Stage 4 range)" is fundamentally honest (architect, line 142).

**Why it doesn't hold up:** A median of an assumption-driven range is an assumption. Ranking by p50 means the most-confidently-large assumption wins. A play with `p_action` range 10–30% (p50 = 20%) on a 1000-person audience outranks a play with measured 6% effect on a 200-person audience. The vocabulary buckets don't break ties because TARGETING plays with large audiences will routinely outrank MEASURED plays with small audiences on raw expected $.

**Specific failure scenario:** Engine consistently surfaces a "TARGETING" category_expansion play above a "MEASURED" winback play because the former targets 2,000 people and the latter 180. Merchant runs the former. It flops. Merchant blames the engine for ranking the wrong play first.

**Severity:** Serious. Without a class-aware ranking (e.g., MEASURED always above TARGETING when expected $ is within 1.5x), p50 ranking will surface heuristic plays at the top.

---

## C. MVP data sufficiency

### C-1. MEASURED is aspirational at MVP scale
**Claim challenged:** MEASURED ("p < α on primary window, sign consistent across the windows that have power, n ≥ min_n") (architect, line 113) is achievable on typical small DTC brands.

**Why it doesn't hold up:** For a $500K–$2M ARR brand:
- Customer base ~1–3K total, monthly cohort ~100–400.
- A two-proportion z-test on repeat rate with a 5pp shift requires roughly n ≥ 600 per arm to detect at 80% power. Most plays simply don't have the audience.
- AOV Welch on order-level data has the heavy-tail / mix-shift problem the audit flagged (M-6); even when `p < α`, the p is overstated and "MEASURED" is misleading.
- Sign-consistency across nested windows is a tautology, not evidence (architect's own observation, line 66). Demanding it as a MEASURED criterion buys little.

So MEASURED will be reachable for: (a) winback when there's a clear lapse pattern, (b) sometimes discount_hygiene, (c) sometimes frequency_accelerator. Three plays out of ten, intermittently. The other 70% of the time the engine is producing DIRECTIONAL/TARGETING/WEAK output.

**Specific failure scenario:** Merchant compares two consecutive months. Month 1: 1 MEASURED, 4 TARGETING. Month 2: 0 MEASURED, 5 TARGETING. Asks "did anything change?" The engine cannot answer because it has no temporal narrative.

**Severity:** Showstopper for the "data scientist replacement" positioning. A DS would say "I don't have power for that yet; let's instrument it." The engine just downgrades and keeps publishing.

### C-2. No learning loop is incompatible with "agentic" positioning
**Claim challenged:** Deferring cohort pooling, multi-store priors, and post-publish calibration is acceptable for MVP (architect, lines 230–236).

**Why it doesn't hold up:** The product is positioned as "agentic Shopify app that detects, validates, launches, and monitors plays." Monitor implies a feedback loop. An MVP without the loop is a recommender that publishes, recommends again next month based on the same priors, and never updates. That's a static rule engine with prior-driven forecasts — the very thing the architect critiques in the current code.

**Severity:** Yellow-flag for Phase 1 if positioned as cleanup; serious if positioned as MVP product launch. The architect doesn't pick a side.

### C-3. Single-store, single-month is too thin for any ranking signal beyond audience × AOV
**Claim challenged:** Stage 4's audience economics formula produces defensible projections without cross-store priors.

**Why it doesn't hold up:** With one store and one month, `p_action` is either store-derived (and seasonal/noisy) or vertical-derived (and miscalibrated for this store). There is no third option. The architect implicitly acknowledges this (line 277, "with no realized-impact feedback loop in the local workflow, how does the engine learn it has overstated lift? Today: it can't"). The acknowledgement is in the Risks section, not propagated into the Stage 4 design — Stage 4 still produces dollar projections as if calibration were possible.

**Severity:** Serious. The honest design surfaces audience size and AOV without a `p_action` projection until calibration exists.

---

## D. Overclaiming risk that survives the design

### D-1. `assumption_source` chips are advisory at best
**Claim challenged:** Labeling revenue ranges with `assumption_source` (architect, line 224) prevents merchants from treating vertical-prior projections as data-backed.

**Why it doesn't hold up:** Merchants read top-line numbers and ignore source chips. This is not a hypothetical — it is the empirical pattern in every analytics product where uncertainty is communicated via secondary chrome. UI/UX research is unanimous on this. The architect doesn't propose a forcing function (e.g., displaying ranges with no point estimate at all when the source is `vertical_prior`), so the chip is purely advisory.

**Severity:** Serious. To actually change behavior, the design would have to suppress the dollar number for heuristic plays and show only audience size + qualitative assumption text.

### D-2. Single-number ranking signal is a single number, regardless of how it's computed
**Claim challenged:** p50 ranking is "fundamentally honest" because it's transparent about being a median.

**Why it doesn't hold up:** Honesty about the construction does not change the consequence. p50 is the rank-key. Merchants will treat the play at the top as "the best one." If p50 is mostly driven by audience size for TARGETING plays (because `p_action` is the same range-derived prior across plays in the same vertical), the ranking is approximately a sort-by-audience-size with extra steps.

**Severity:** Serious.

---

## E. Weak plays / no-recommendation cases

### E-1. No abstain mode is a fatal omission
**Claim challenged:** The 4-bucket vocabulary handles weak cases via the WEAK label (architect, lines 116–117).

**Why it doesn't hold up:** WEAK is still in the briefing. The design never says "this month, we have no defensible recommendations, we are not publishing a ranked list." A briefing where the top 3 are TARGETING and the rest are WEAK is published with the same visual grammar as a briefing where the top 3 are MEASURED. A skeptical DS would refuse to publish; the architect's design forces publication.

**Specific failure scenario:** First three months of a new store: 0 MEASURED, 2 DIRECTIONAL (low n), rest TARGETING/WEAK. The engine publishes three monthly briefings each topped by speculative TARGETING plays. Merchant asks "where's the data science?" Correct answer: "There isn't enough data yet." The engine never says that.

**Severity:** Showstopper. The right behavior is: refuse to publish a ranked list when no candidate clears MEASURED or high-quality DIRECTIONAL on a defensible audience size; publish a "data not yet sufficient — here's what we're tracking" page instead.

### E-2. Heuristic-only briefings should degrade visually, not silently
**Claim challenged:** Stage 5 produces "a single ordered list with a confidence chip" regardless of bucket mix (architect, line 145).

**Why it doesn't hold up:** Visual chrome should change when the briefing is heuristic-dominant. If a briefing is 0/0/5/2 (MEASURED/DIRECTIONAL/TARGETING/WEAK), it should not look like a briefing that is 3/2/2/0. The merchant should visually understand they are being shown best-effort targeting, not measured opportunity. The redesign treats them identically.

**Severity:** Serious.

---

## F. Cannibalization, inventory, fatigue, audience-overlap (currently absent)

### F-1. Stage 4 sizes plays in isolation
**Claim challenged:** `projected_revenue = audience × p_action × incremental_orders × AOV` per play, ranked by p50, is sufficient (architect, lines 124–146).

**Why it doesn't hold up:** Three plays may target overlapping audiences:
- `bestseller_amplify` to top-product buyers (n=420)
- `frequency_accelerator` to repeat customers (n=380, ~70% overlap with bestseller buyers)
- `subscription_nudge` to ≥3-SKU buyers (n=180, ~85% overlap with both)

The engine adds projected revenue across these as if the audiences were disjoint. A merchant who runs all three "PRIMARY" recommendations in the same 28 days hits the same 250 customers with three campaigns, gets fatigue-driven negative response, and realizes ~25% of forecast.

**Specific failure scenario:** Sum of expected $ across PRIMARY tier > store's monthly revenue. This is the obvious credibility kill. The redesign has no audience-overlap penalty, no portfolio constraint, no cannibalization adjustment.

**Severity:** Showstopper. Any merchant running their own KPIs will catch this within one month.

### F-2. Inventory / OOS gating is not in the design at all
**Claim challenged:** The architect's three-stage design needs no inventory awareness for Phase 1.

**Why it doesn't hold up:** `bestseller_amplify` recommends pushing the top SKU. If that SKU is at 12 days of cover, the engine just told the merchant to accelerate stockout. The current code has `validation.py:618` (inventory schema validation) and `compute_inventory_metrics` in `load.py:585`, but the architect's redesign references neither. Stage 1's gating predicates ("audience > N", "feature exists") need to include "inventory cover ≥ X days for bestseller plays" and the design omits this entirely.

**Specific failure scenario:** Merchant runs bestseller_amplify, SKU goes OOS day 9 of 28, merchant blames engine for stockout, asks "why didn't it know?"

**Severity:** Showstopper for any merchant with inventory constraints (i.e., all of them).

### F-3. Fatigue / send-frequency caps not in the design
**Claim challenged:** The redesign relies on the merchant to manage fatigue.

**Why it doesn't hold up:** Once this becomes an agentic Klaviyo publisher, the engine *is* the sender. It has to know that the same audience was hit with a campaign two weeks ago. No design treatment of this.

**Severity:** Yellow-flag for Phase 1 (CSV-only); showstopper for the agentic future state.

### F-4. Current saturation guard is heuristic; redesign removes it without replacement
**Claim challenged:** The redesign cleanly replaces multiplier stacking with audience economics (architect, lines 119–137).

**Why it doesn't hold up:** The current `saturation guard` (architect, line 28) is the only existing constraint preventing a play with audience = 90% of customer base from getting a 90%-of-revenue projection. The redesign drops the multiplier stack entirely; it does not propose a replacement audience-coverage cap. So the new formula `audience × p_action × incremental_orders × AOV` will, on small stores, project plays that target 60% of the customer base at 60% of monthly revenue — worse than the current code, not better, in this dimension.

**Severity:** Serious. The redesign needs an explicit "audience as fraction of base" cap.

---

## G. Knowing when not to recommend

### G-1. Cold-start is mentioned, not specified
**Claim challenged:** "Stores with <90 days of data" handled by "mark as cold-start, default to targeting plays only, lean on vertical priors with labels" (architect, line 276).

**Why it doesn't hold up:** "Default to targeting plays with vertical priors" is exactly the maximum-overclaiming configuration: no store data, full reliance on Klaviyo benchmarks the architect's own analysis flagged as Benchmark-as-Lift. The cold-start branch as specified produces the highest-risk briefings the engine can produce. This is backwards — cold-start should be the most conservative branch (audience size + qualitative ideas, no dollar projections).

**Severity:** Serious. Inverted priority.

### G-2. No bad-data gates in the architecture
**Claim challenged:** Existing filters (refund/test-order exclusion in `load.py:180–183`) are sufficient.

**Why it doesn't hold up:** The architecture-level design needs explicit gates for:
- Test orders / draft orders / employee-discount orders (current filtering is name-pattern in `load.py`, fragile)
- Refund storms (>15% refund rate already flagged in `validation.py:574–576`, but no gating of plays)
- Post-Black-Friday / post-promo windows (a 28-day window centered on BFCM produces inflated everything; the engine should refuse to publish certain plays in these windows or label them "post-promo, not yet stable")
- Returns/chargebacks above threshold (no gate)

The architect's redesign references none of these at the architecture level.

**Specific failure scenario:** Merchant runs the engine on December 15, 28-day window straddles BFCM. AOV is up 22% vs prior, repeat rate is up 8 points, every play is MEASURED. Merchant launches all of them in January. None replicate. Merchant concludes the engine is fundamentally broken (correctly).

**Severity:** Showstopper. Anomalous-window detection has to be at the architecture level, not deferred.

### G-3. No "test order" architectural gate
**Claim challenged:** Implicit handling via name-pattern matching is enough.

**Why it doesn't hold up:** A new Shopify store with 12 test orders out of 80 will silently include them in audience counts and AOV. There is no architectural sanity check ("does the top customer account for >40% of orders? — flag as anomalous").

**Severity:** Serious. One-line gates would cover most cases.

---

## H. Specific overclaims in the architect's report

### H-1. "Phase 1 is small" undersells the blast radius
**Claim challenged:** "Phase 1 should collapse the surface area, not extend it … no new statistical machinery" (architect, line 12, line 227).

**Why it doesn't hold up:** Phase 1 as specified includes:
1. Stop fabricating stats (low blast)
2. New `evidence_class` attribute on every candidate (medium blast — it touches every output path)
3. Replace min-p with `combine_multiwindow_statistics` (medium — changes effective sensitivity, will change which plays hit MEASURED)
4. Collapse 4–6 p-recodings to one (medium-high — changes confidence numerics for every play, every test fixture, every comparison report)
5. Reclassify 4 plays as targeting-only (high — changes briefing structure, scoring weights, the 4×4 matrix collapses to a 4-list, downstream Klaviyo/agentic consumers see different fields)
6. Add `assumption_source` to revenue ranges (medium — touches storytelling, briefing template)
7. Drop seasonality from `confidence_score` (medium — changes confidence numerics again, affects every test fixture)

Items 5 and 7 alone are major product-surface changes. Calling this "small" because no new statistical functions are added is a category error — the bigger risk in this codebase is product-surface churn, not stats.

**Severity:** Yellow-flag. The seven changes are the right ones; the "small" framing will get the timeline wrong.

### H-2. "Calibrated qualitative confidence label" — calibrated against what?
**Claim challenged:** The 4-bucket vocabulary is "calibrated" (architect, line 37, line 117).

**Why it doesn't hold up:** Calibration requires:
- A target distribution (e.g., "MEASURED plays should achieve their forecast 60% of the time")
- A measurement of realized vs forecasted lift
- A rebalancing procedure when realized falls outside the target band

None of this exists. The architect explicitly defers calibration (line 234). So "calibrated" in the redesign means "I picked four labels that feel right." This is exactly the same confidence-theater pattern the architect criticizes, applied to qualitative labels instead of numeric scores.

**Severity:** Serious. Either drop "calibrated," or propose a measurement framework (even a stub) that would produce calibration data. Without the latter, the labels are vibes.

### H-3. "Two structurally distinct play classes" understates the migration
**Claim challenged:** The Evidence/Heuristic split is a clean architectural cut (architect, lines 39–44, 155–167).

**Why it doesn't hold up:** The split is correct in principle but the design doesn't address:
- How does ranking work across classes? (mixed list? class-segmented? class-weighted? — see D-2)
- How does the agentic Klaviyo publisher consume them? Different fields, different revenue conventions.
- What does the briefing layout look like? Two sections? Interleaved with class chips? (the architect waffles between "ranked separately or interleaved with a clear class label," line 164 — i.e., undecided)

This is the highest-leverage architectural decision in the redesign and it's left under-specified.

**Severity:** Serious. Blocking decision before merge.

### H-4. "Drop seasonality from confidence_score" misses that seasonality also drives revenue projections
**Claim challenged:** Move seasonality to a `recommended_launch_window` field (architect, line 209, line 225).

**Why it doesn't hold up:** Seasonality currently feeds both the confidence pipeline and (implicitly via `compute_decay_multiplier` and per-vertical effects) the revenue projection. The architect addresses the confidence side but not the revenue side. A January retention play has different expected revenue than an October one for legitimate reasons (different reach, different LTV ramp). The redesign needs to specify whether Stage 4's `p_action` or `incremental_orders` carries seasonality, or if the projection becomes seasonality-blind (which would be wrong).

**Severity:** Yellow-flag.

---

## What the architect got right (only the durable parts)

These survive attack:

1. **Diagnosing the system as a hypothesis-and-targeting recommender, not an inferential pipeline.** Correct framing. Single-store, monthly, no-experimentation cannot support frequentist confidence at the play level. This is the single most important reframing in the document.
2. **The Evidence-based vs Heuristic class split.** Correct in principle (even though the migration is under-specified — H-3). Removing fabricated p-values from heuristic plays is the single highest-leverage cleanup.
3. **Identifying min-p multi-window merge as winner's-curse selection.** Correct. The combiner already exists; routing the four-of-ten gap to it is mechanically right.
4. **Identifying confidence_score as one p-value re-encoded 4–6 ways.** Correct. The collapse to one place is right.
5. **Naming Benchmark-as-Lift, Confidence Theater, Multiplier Stacking, Hypothesis Laundering.** The anti-pattern catalog is sharp and useful as a review checklist; it will outlive the specific design proposals.
6. **Identifying that ENABLE_COHORT_POOLING is a dead switch attractor.** Correct. Disable and remove.
7. **The assertion that seasonality is a launch-timing constraint, not a confidence factor.** Correct conceptually (with the H-4 caveat about revenue-side leakage).

That's seven items. Most of the design is sound at the diagnostic level; the failures are in the prescribed Phase 1 design's silence on abstain, calibration, cannibalization, inventory, and cold-start.

---

## What needs to be added or changed before the design is mergeable

Sequenced. Each is concrete.

1. **Add an explicit abstain mode to Stage 5.** Spec the rule: "If 0 candidates clear MEASURED and fewer than 2 clear DIRECTIONAL with audience ≥ N_min, publish a 'Data not yet sufficient' briefing instead of a ranked list." Define the page. (Showstopper E-1.)

2. **Add a portfolio-level cannibalization step between Stage 4 and Stage 5.** For each pair of recommended plays, compute audience overlap; for overlapping pairs above 50%, attribute incremental revenue only to the highest-confidence play and reduce the lower one. Cap total expected $ across PRIMARY at some fraction (e.g., 25%) of monthly revenue. (Showstopper F-1.)

3. **Add inventory awareness to Stage 1 gates.** For SKU-pushing plays (`bestseller_amplify`, `routine_builder`, `category_expansion`), require `days_of_cover ≥ 21` from `inventory_metrics`. Engine refuses to recommend if not. (Showstopper F-2.)

4. **Add anomalous-window detection at Stage 0 (pre-pipeline).** Detect: BFCM/post-promo windows, refund storms, top-customer concentration spikes, test-order anomalies. Engine outputs a "data quality flag" briefing in those cases instead of plays. (Showstopper G-2.)

5. **Specify cold-start as conservative, not Klaviyo-prior-driven.** For stores with <90 days, suppress dollar projections entirely; show audience sizes and qualitative ideas labeled "no projection available — insufficient data." (Inverts G-1.)

6. **Force-suppress dollar projections for TARGETING plays in the merchant view, OR** present them as "audience × AOV" only (no `p_action` multiplication) with a clearly different visual treatment. The current proposal of "p10/p50/p90 with assumption_source chip" is not enough. (Serious A-3, D-1.)

7. **Define the calibration plan, even as a stub.** A line item that says "we will record predicted vs realized for every play that ships, beginning Phase 2, and rebalance MEASURED-tier eligibility after 50 store-months." Without this, "calibrated" is unjustified. (Serious H-2.)

8. **Resolve the cross-class ranking question.** Pick one: (a) MEASURED always above DIRECTIONAL always above TARGETING regardless of expected $, (b) within-class p50 ranking, (c) cross-class with a class-aware penalty (e.g., TARGETING expected $ multiplied by 0.4 before ranking). The current "ranked separately or interleaved" is a non-decision. (Serious D-2, H-3.)

9. **User-test the 4-bucket vocabulary with 5+ real merchants before locking it in the briefing.** "MEASURED / DIRECTIONAL / TARGETING / WEAK" needs validation that non-statisticians read it correctly, not just that it's better than p-values. (Serious A-1.)

10. **Specify what changes in the briefing visual chrome when bucket mix shifts.** A briefing dominated by TARGETING should not look like a briefing dominated by MEASURED. Define the two layouts. (Serious E-2.)

11. **Explicitly handle seasonality in Stage 4's revenue projection,** not only in confidence/launch-window. Pick whether `p_action` or `incremental_orders` carries seasonality, or declare projections seasonality-blind. (Yellow H-4.)

12. **Re-scope "Phase 1 is small."** The seven items the architect lists are correct, but items 5 and 7 are major product-surface changes; reflect that in the timeline narrative so engineering doesn't underplan. (Yellow H-1.)

Items 1–4 are blocking — without them the redesign ships overclaiming risk into the agentic future. 5–8 are mergeable-with-fixes. 9–12 are pre-launch.

---

## Files referenced (absolute)

- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ecommerce-ds-architect-initial.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/statistical-code-reviewer-initial.md`
- `/Users/atul.jena/Projects/Personal/beaconai/ENGINE.md`
- `/Users/atul.jena/Projects/Personal/beaconai/src/action_engine.py` (saturation guard, candidate compute paths referenced for cannibalization/coverage discussion)
- `/Users/atul.jena/Projects/Personal/beaconai/src/load.py` (refund/test-order filtering, inventory loading)
- `/Users/atul.jena/Projects/Personal/beaconai/src/validation.py` (refund-rate flag, inventory schema validation — exists but not gated)
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` (seasonal multiplier, BH list)
