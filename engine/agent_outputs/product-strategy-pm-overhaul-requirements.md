# BeaconAI Decision-Core Overhaul — Product Strategy & Requirements

**Author:** Product Strategy PM
**Date:** 2026-05-01
**Audience:** Implementation-manager agent (sequencing); future code-refactor-engineer agent (execution).
**Status:** Working contract. Treats `memory.md` reconciled section as baseline, with explicit PM challenges where product viability disagrees.

---

## 0. Product verdict (read this first)

The reconciled direction is statistically and architecturally correct, and **not yet a product**. If we ship the 12 must-haves verbatim, we ship a defensible, conservative, frequently-abstaining recommender that a skeptical merchant will read as *"this thing mostly says it doesn't know."* That kills the "data scientist replacement" positioning faster than overclaiming did.

The product job is therefore: **keep all the trust-preserving guardrails, but redesign the briefing surface so that even a TARGETING/ABSTAIN month feels like a working data scientist, not an apology.** Honesty is a constraint, not the value proposition. The value proposition is *"a senior DS-level read of your store this month, with a recommended action set, including the call not to act."*

The single most important PM principle for this overhaul:

> The merchant is not paying for p-values. They are paying for *what to do next*, with someone they trust having ruled out what not to do. The engine must show its rejection work as proudly as its recommendations.

Three concrete consequences for the design:

1. **A "no measured plays this month" briefing must look like a senior DS memo, not a 404.** It must surface the watched signals, what would have to change for a play to fire, and a small set of conservative targeting ideas labeled as such. This is the wow surface in low-signal months.
2. **Rejected plays are first-class output, not a debug artifact.** Showing "we considered winback, here is why it didn't clear" is the visible difference between a checklist tool and a DS replacement.
3. **Phase 1 must leave a place for ML to plug in later, but must not pretend ML exists today.** Specifically: priors, calibration hooks, and play-effect logging must be modeled as schema fields populated with conservative defaults, so a future uplift/hierarchical layer can replace the defaults without re-architecting briefings.

---

## 1. Q1 — What should the merchant experience become?

A monthly briefing that reads like a 1-page memo from a senior DTC growth analyst who has spent 4 hours in the store's data. Specifically:

- **A one-paragraph "state of the store this month"** lead — three to five observed facts (what changed, what held, what looks anomalous), in plain English. No chips, no tier matrix, no scores. This is the only section guaranteed to be present every month.
- **A "Recommended this month" section, 0–3 plays.** Zero is allowed and named (see Q4, ABSTAIN). Each play has: a one-line recommendation, a single confidence label, a why-now sentence, the audience and audience definition, an honest revenue range with its source labeled, and what to send.
- **A "Considered, not recommended" section, 3–6 plays.** Each rejected play has: a one-line rejection reason in plain English ("audience too small to act on with confidence — 38 customers"; "winback already ran in the last 28 days, audience is fatigued"; "bestseller is at 9 days of cover, would accelerate stockout"). This is the new wow surface and the proof of DS-level thinking.
- **A "Watching" section, 1–4 signals.** Metrics the engine is tracking month-over-month with no recommendation yet. Tells the merchant "we're not asleep; here's what would have to move for us to act."
- **A "Data quality" footer.** Window used, customer base, confidence mode, anomalies detected (BFCM/refund storm/test orders), and any cold-start status. Compact, but present every month.

What disappears from the merchant view, vs today:
- p-values, q-values, CIs, "confidence percentage" numbers
- The 4-tier (PRIMARY/QUICK_WINS/WATCHLIST/EXPERIMENTS) matrix
- Per-play "High/Moderate/Early signal" chip stacks
- Stacked-multiplier revenue point estimates
- Anything labeled `final_score` or `confidence_score`

What stays in the merchant view, refactored:
- A revenue range per recommended play (stricter rules; see Q3 and Q5)
- A confidence label (3-bucket vocabulary; see Q5)
- The per-play "what to send" / next-step block (this is already merchant-loved; preserve)

**PM challenge to reconciled direction:** memory.md item #6 (abstain mode) is correct but under-specified. *Abstain* must not mean "empty briefing." The product cost of abstaining must be designed to be *near zero* — a no-recommendation month must be visibly informative, or merchants churn after month 2.

---

## 2. Q2 — What should the engine output contract be?

The engine's structured output must be a single object the briefing renderer, the future Klaviyo agent, the future monitor agent, and the receipts/debug system all consume. Schema (Phase 1, JSON-shaped, fields nullable where noted):

```
EngineRun {
  run_id
  store_id
  anchor_date
  data_window: { primary_window, available_windows[], anchor_quality }
  cold_start: bool
  data_quality_flags[]            # e.g. ["bfcm_overlap", "refund_storm", "test_order_anomaly"]
  abstain: { state: "publish" | "abstain_soft" | "abstain_hard", reason }
  state_of_store: [Observation]   # 3–5 plain-English facts; see below
  recommendations: [PlayCard]     # 0–3
  considered: [RejectedPlay]      # 3–6
  watching: [WatchedSignal]       # 1–4
  scale: { monthly_revenue, customer_base_est, materiality_floor }
  briefing_meta: { confidence_mode, vertical, subvertical, stage, seasonality_tag }
}

PlayCard {
  play_id
  evidence_class: "measured" | "directional" | "targeting"
  confidence_label: "Strong" | "Emerging" | "Targeting"   # merchant-facing
  recommendation_text                                     # one-line
  why_now                                                 # one-sentence
  audience: { id, definition, size, fraction_of_base, overlap_with[] }
  measurement: {                                          # null for targeting
    metric, observed_effect, n, primary_window,
    consistency_across_windows, p_internal, ci_internal   # debug-only, never rendered
  }
  revenue_range: {
    p10, p50, p90,
    source: "store_observed" | "vertical_prior" | "blend",
    drivers: [labelled assumption inputs],
    suppressed: bool                                       # true => render audience+AOV, no $
  }
  inventory: { skus[], days_of_cover, gate_passed }       # null if N/A
  conflicts: { cannibalized_by[], audience_overlap_pct }
  launch_window: { recommended, reason }
  klaviyo_brief_inputs: { ... }                           # see Q5 future-agent section
  receipts_ref                                            # link to debug detail
}

RejectedPlay {
  play_id
  reason_code                      # enum, see Q3
  reason_text                      # plain-English merchant-facing line
  evidence_snapshot                # the one number that drove the rejection
  would_fire_if                    # what would need to change
}

WatchedSignal {
  metric, current, prior, trend, threshold_to_act
}

Observation {
  text, supporting_metric, change_magnitude, classification: "moved" | "held" | "anomalous"
}
```

**Hard contract rules:**

- `measurement.p_internal` and `ci_internal` exist in the object but are NEVER rendered to the merchant. They are present so debug, future ML calibration, and the receipts page can read them. This is the ML-readiness hook (see Q8).
- `evidence_class = "targeting"` REQUIRES `measurement = null` and `revenue_range.source != "store_observed"`. Schema-enforced.
- `evidence_class = "measured"` REQUIRES non-null `measurement.observed_effect`, non-null `n`, and `consistency_across_windows >= 2`.
- `revenue_range.suppressed = true` for cold-start stores and for any TARGETING play where `vertical_prior` has not been calibrated against a comparable cohort. Renderer hides the dollar number entirely in this case.
- Sum of `recommendations[].revenue_range.p50` after de-duplication must not exceed `scale.monthly_revenue * 0.25`. If it would, the engine must demote until it doesn't (see Q4 cannibalization).

**PM challenge:** the reconciled direction does not name a structured output contract. Without one, every downstream consumer (HTML, Klaviyo agent, monitor, receipts) re-interprets fields. A schema with rendered/non-rendered separation is the single highest-leverage Phase 1 artifact. **This is non-negotiable.**

---

## 3. Q3 — Which old concepts should be preserved, renamed, or removed?

| Concept | Action | Rationale |
|---|---|---|
| `final_score` | REMOVE from merchant view; KEEP internal as `merit_p50` (just expected revenue p50) | Score-as-decision is theater; one rank-key is enough |
| `confidence_score` (numeric) | REMOVE entirely | Five things mashed into one number, none of which calibrated |
| `_calculate_business_confidence` 7-factor formula | REMOVE | Confidence theater per all three reviewers |
| 4-tier matrix (PRIMARY/QUICK_WINS/WATCHLIST/EXPERIMENTS) | REMOVE merchant-facing; collapse to recommendations / considered / watching | Two-axis was correlated >0.8 axes |
| `evidence_class` | ADD as first-class | Statistical reviewer + DS architect agree |
| `confidence_label` 3-bucket: Strong / Emerging / Targeting | ADD | Replaces tier matrix; merchant-readable; see Q9 challenge |
| Per-play `p`, `q`, `effect_abs`, `ci_low`, `ci_high` in candidate dicts | RENAME to `measurement.*` and gate on evidence_class | Architecturally cleaner, removes hardcoded fakery surface |
| `expected_$` point estimate | RENAME to `revenue_range.p50` and require p10/p90 alongside; suppressible | Range-as-defense is partial; suppression for low-data plays is the forcing function |
| Hardcoded p/effect/CI in `_compute_candidates` for fc/aov/retention/journey/category_expansion/subscription_nudge/routine_builder/empty_bottle | REMOVE; set to `np.nan` | One-day fix per stat reviewer |
| `_merge_multiwindow_candidates` min-p selection | REPLACE with `combine_multiwindow_statistics` | Combiner exists, route everything through it |
| `bias_corrections = {7:1.0, 28:0.95, 56:0.90, 90:0.85}` | REMOVE or move to display-only with "(adjusted)" label | No defensible derivation |
| `ENABLE_COHORT_POOLING` + `_run_cohort_statistical_test` placeholder | REMOVE the dead path | Foot-gun |
| `_calculate_calibrated_confidence` dead code | REMOVE | Confuses readers |
| Seasonality inside `confidence_score` | RENAME to `launch_window.recommended` + `revenue_range.seasonality_factor` (separate) | Seasonality is timing + sizing, not evidence quality |
| `Retention Mastery` play | RENAME to **At-Risk Repeat Buyer Rescue**; remove assumed churn-reduction constant | Per memory; honest about what's measured |
| `Journey Optimization` play | DEMOTE to targeting-class, RENAME to **Onsite Funnel Watch (data-pending)** | Onsite funnel data not in CSV; cannot test |
| `AOV Momentum` | KEEP, but mark as `directional` only; never `measured` | Welch on order-level is heavy-tailed per audit M-6 |
| `Subscription Candidate / Routine Completion / Bestseller Attach / Category Expansion` | RECLASSIFY to targeting-class, strip p/q/effect/CI from output | Per memory; per DS architect |
| `First-to-Second Purchase` play | ADD/PROMOTE as preferred replacement for Journey Optimization | Per memory; testable in CSV data |
| `Low-Stock Suppression` | ADD as a *guardrail*, not a play — drives `RejectedPlay` reason `inventory_blocked` | Per memory + skeptic F-2 |
| Saturation guard | KEEP and HARDEN: rename to `audience_coverage_cap` | Skeptic F-4 — without this, new revenue formula projects worse |

**Reason-code enum for `RejectedPlay.reason_code`:**
`audience_too_small`, `audience_overlap_with_higher_priority`, `inventory_blocked`, `no_measured_signal`, `signal_inconsistent_across_windows`, `anomalous_window`, `cold_start_insufficient_data`, `cannibalization_demoted`, `recently_run_fatigue`, `materiality_below_floor`, `data_quality_flag`.

This enum is the contract for "showing the rejection work." Both the briefing renderer and the future Klaviyo agent must understand all 11 codes.

---

## 4. Q4 — Which decision states are required?

Three top-level states for a `EngineRun`:

1. **PUBLISH** — at least one PlayCard with `evidence_class in {measured, directional}` cleared all guardrails, OR the targeting set is sized against an exceptionally well-defined audience and the engine is operating in a non-cold-start state. This is the normal month.

2. **ABSTAIN_SOFT** — no measured/directional plays clear the bar this month, but at least one targeting play is defensible. Output is: state-of-store paragraph, "Watching" section, 1–2 conservative targeting plays clearly labeled "Targeting recommendation, not measured", and a prominent "no measured opportunities cleared this month" callout. **Not** an empty briefing.

3. **ABSTAIN_HARD** — anomalous-window or data-quality flag triggered (BFCM overlap, refund storm, test-order anomaly, <60 days of clean data, cold-start with no defensible audience). Output is: a "Data quality memo" briefing with no plays. State-of-store, what was detected, what the merchant should check, what the engine will do next month. Visually distinct chrome.

**Per-play states (within PUBLISH):**
- `recommended` — fits the 0–3 cap, passes guardrails, ranks by class-aware merit
- `considered_rejected` — appears in "Considered, not recommended" with reason
- `watching` — metric being tracked, not actionable yet
- `suppressed_internal` — present in EngineRun debug, not shown to merchant (e.g., dead/deprecated plays)

**Cap rules (Phase 1):**
- Max 3 PUBLISHed PlayCards per run.
- At least 1 must be `evidence_class = measured` OR `directional`. If none, demote to ABSTAIN_SOFT.
- Sum of recommended `revenue_range.p50` ≤ 25% of monthly revenue (cannibalization cap).
- For any pair with audience overlap > 50%, attribute revenue only to higher-confidence; lower-confidence is demoted to "Considered" with reason `audience_overlap_with_higher_priority`.
- A single audience cannot be the target of more than 1 PUBLISHed play.

**PM challenge to reconciled direction:** memory.md treats abstain as a single binary. It is not. ABSTAIN_SOFT vs ABSTAIN_HARD is the difference between "this month is quiet" and "your data is unreliable." Merchants tolerate the former; they need to be told the latter explicitly. **Two abstain modes, not one.**

---

## 5. Q5 — Which evidence labels are useful to merchants?

**Recommended merchant-facing vocabulary (3 buckets, not 4):**

- **Strong signal in your data** — engine measured the underlying metric in this store, effect is consistent across at least 2 windows, audience clears materiality floor.
- **Emerging signal in your data** — engine measured the underlying metric, but signal is in only one window, or audience is small, or effect is borderline. Honest qualifier.
- **Targeting recommendation** — engine identified a high-value audience by definition (e.g., 3+ repeat buyers). No measured effect; range comes from vertical comparables.

**PM challenges to the reconciled 4-bucket vocabulary:**

1. **"DIRECTIONAL" is DS jargon.** Skeptic A-1 is correct. Rename to "Emerging signal in your data" — preserves the same meaning, scans correctly to a non-statistician.
2. **"WEAK" is humiliating to surface.** A WEAK card in a briefing reads "we put a bad recommendation in front of you on purpose." Drop the WEAK bucket merchant-facing entirely. Internally, WEAK candidates become RejectedPlays with reason `no_measured_signal` or `audience_too_small` — they appear in "Considered, not recommended", not as plays.
3. **"TARGETING" risks Skeptic A-1's failure mode** ("merchant hears 'targeted right' = validated"). Mitigation: pair the chip with a fixed sentence in the card body — *"This is a who-to-send-to recommendation, based on the audience definition. We have not measured the play's effect in your store."* Same words on every targeting card. Forcing function, not optional.

**Confidence label is qualitative AND deterministic.** Mapping rules:

```
Strong       := evidence_class == "measured"
                AND consistency_across_windows >= 2
                AND audience.size >= materiality_n_floor
                AND not in anomalous_window
Emerging     := evidence_class == "measured" AND not Strong
                OR evidence_class == "directional"
Targeting    := evidence_class == "targeting"
```

No numeric "confidence percentage" surfaces to the merchant ever.

**Internal-only labels (not merchant-facing) that the engine and future ML layer use:**
- `measured`, `directional`, `targeting`, `weak`, `blocked`
- These appear in the EngineRun JSON, the receipts page, and downstream agent inputs.

---

## 6. Q6 — Which guardrails are mandatory for trust?

Phase 1 must-have guardrails, ranked by what merchants will catch first:

1. **Inventory / OOS gate** (Skeptic F-2). Any SKU-pushing play (`bestseller_amplify`, `routine_builder`, `category_expansion`, `overstock_demand_push` reverse case) requires `days_of_cover ≥ 21`. Below that, becomes RejectedPlay with `reason_code = inventory_blocked`. Inventory data already exists in `load.py:585`.

2. **Audience-overlap / cannibalization** (Skeptic F-1). Pairwise overlap computed on customer ids. Overlap > 50% → demote lower-confidence play. Sum of recommended p50 capped at 25% of monthly revenue.

3. **Anomalous-window detection** (Skeptic G-2). Pre-pipeline. Detect BFCM (Nov 20–Dec 5), post-promo (any 14-day window where discount rate is >2x trailing-90 baseline), refund storm (>15% of orders refunded in window), test-order anomaly (top customer >40% of orders, or `name LIKE 'test%'` exceeds 5% of orders), <60 days of clean data after exclusions. Triggers ABSTAIN_HARD.

4. **Cold-start gate** (Skeptic G-1, inverted from architect's proposal). Stores with <90 days suppress dollar projections entirely (`revenue_range.suppressed = true`); show audience + AOV, qualitative recommendation, no $ number. The cold-start branch is the most conservative branch, not the most prior-driven.

5. **Materiality floor** (memory item #12). Per-play expected revenue p50 must clear `max($5k, 2% of monthly revenue)` for stores under $1M ARR; `max($10k, 3% of monthly revenue)` for $1M–$5M ARR; `max($25k, 5% of monthly revenue)` over $5M. Below floor → RejectedPlay with `reason_code = materiality_below_floor`. **Scale-aware, not constant.**

6. **No fabricated stats reach FDR or scoring** (Stat reviewer C-1). Hardcoded p/effect/CI for category_expansion + the rest become `np.nan`. Gate downstream consumers to treat NaN as "no evidence."

7. **Multi-window combiner replaces min-p merge** (Stat reviewer C-2). Route all plays through `combine_multiwindow_statistics` (already exists in `src/stats.py:334`).

8. **Single p-entry-point into confidence** (Stat reviewer C-4). Pick `_calculate_statistical_confidence` and remove the other three p-recodings. Does not need to be smooth; a step function is fine.

9. **Recently-run-fatigue gate** (forward-looking; Phase 1 stub). For now, exclude any play where the same `audience_id + play_id` combo was recommended in the last 28 days. Stub via persisted `recommended_history.json` keyed by store; if the file doesn't exist yet, the gate is a no-op. ML/agentic layer will replace this with real Klaviyo send history.

**Guardrails that are NOT Phase 1 (deferred with rationale):**
- Real post-publish calibration loop (requires Klaviyo monitor agent; Phase 3+)
- Bayesian credible intervals on revenue (requires prior elicitation; not Phase 1)
- Cross-store hierarchical priors (requires fleet of stores; can't have until we have)

---

## 7. Q7 — Which requirements are Phase 1 vs later?

### Verdict on the 12 must-haves in `memory.md`

| # | Must-have | Verdict | Rationale (one line) |
|---|---|---|---|
| 1 | Remove fake stats | **ACCEPTED** | One-day fix; biggest correctness gain per stat reviewer |
| 2 | Add evidence classes | **ACCEPTED** | The structural cut; everything else hangs off this |
| 3 | Reclassify heuristic plays so they don't expose p/q/CI/effect | **ACCEPTED** | Architectural correctness + product honesty; together with #2 |
| 4 | Stop multi-window min-p cherry-picking | **ACCEPTED** | Combiner already exists; mechanical fix |
| 5 | Simplify confidence so p isn't counted multiple times | **ACCEPTED** | Pick `_calculate_statistical_confidence`; delete the rest |
| 6 | Add abstain mode | **ACCEPTED WITH CHANGES** | Must be TWO modes (soft/hard), not one; soft must not look like an empty briefing — see Q4 |
| 7 | Add inventory/OOS gates | **ACCEPTED** | Showstopper per skeptic; data already loaded |
| 8 | Add audience-overlap and cannibalization guardrails | **ACCEPTED WITH CHANGES** | Phase 1 is pairwise-overlap + portfolio cap; full overlap modeling deferred to ML phase |
| 9 | Add anomalous-window/data-quality gates | **ACCEPTED** | BFCM, refund storms, test orders. Triggers ABSTAIN_HARD |
| 10 | Add conservative cold-start behavior | **ACCEPTED WITH CHANGES** | INVERT skeptic's flag of architect's proposal: cold-start = suppress $ projections, not lean on priors |
| 11 | Add rejected-play explanations | **ACCEPTED** | This is the wow surface, sequence it early |
| 12 | Add economic materiality gates | **ACCEPTED WITH CHANGES** | Make scale-aware (3 tiers by ARR), not flat |

Nothing rejected. Three accepted-with-changes.

### Phase 1 sequencing — minimal slice vs full Phase 1

**The smallest meaningful Phase 1 slice (~2 weeks of work, "Phase 1A"):**

The goal: ship a noticeably better briefing in 10 working days, without breaking the local CSV → HTML workflow.

1. **Day 1–2: Kill fabricated stats.** Set hardcoded p/effect/CI to `np.nan` for category_expansion, subscription_nudge, routine_builder, empty_bottle, frequency_accelerator (single-window mode), retention_mastery (single-window), journey_optimization (single-window), aov_momentum (single-window). Add `evidence_class` field to candidate dicts.
2. **Day 3–4: Reclassify the targeting plays.** Mark subscription_nudge, routine_builder, empty_bottle, category_expansion, bestseller_amplify, vip_no_discount_nurture, replenishment_reminder as `evidence_class="targeting"`. Their `measurement` block is null. Their revenue_range is computed from audience economics with `source="vertical_prior"`.
3. **Day 5: Collapse the tier matrix in storytelling.py.** Replace PRIMARY/QUICK_WINS/WATCHLIST/EXPERIMENTS with three sections: Recommended / Considered, not recommended / Watching. Per-card chip becomes Strong / Emerging / Targeting (or just hidden for items in the rejected/watching sections).
4. **Day 6–7: Add the rejected-play list with reason codes.** Wire 5 reason codes initially: `audience_too_small`, `no_measured_signal`, `materiality_below_floor`, `inventory_blocked`, `cold_start_insufficient_data`. The other 6 reason codes can stub in Phase 1B.
5. **Day 8: Add inventory gate** (`days_of_cover >= 21`) for SKU-pushing plays.
6. **Day 9: Add ABSTAIN_SOFT and ABSTAIN_HARD output modes.** Renderer must handle both. ABSTAIN_HARD trigger: <60 days clean data OR refund-storm flag. ABSTAIN_SOFT trigger: 0 measured/directional plays clear gates.
7. **Day 10: Add the state-of-store paragraph + Watching section.** Three observed deltas (AOV, repeat rate, top-product velocity), two watched metrics. Static template with engine-filled values; not LLM-generated yet.

**Out of Phase 1A, in Phase 1B (~next 2–3 weeks):**
- Replace `_merge_multiwindow_candidates` with `combine_multiwindow_statistics` everywhere (touches every test fixture)
- Collapse the 4–6 p-recodings in confidence to one
- Audience-overlap pairwise calculation + cannibalization demotion + 25%-of-revenue portfolio cap
- Full anomalous-window detection (BFCM, post-promo, test-order)
- Scale-aware materiality floor
- Remove dead code (`_calculate_calibrated_confidence`, `ENABLE_COHORT_POOLING` placeholder path, `bias_corrections` dict)
- Remaining 6 reason codes wired
- `recommended_history.json` stub for fatigue gate

**Out of Phase 1 entirely (Phase 2+):**
- Real calibration loop (predicted vs realized)
- Bayesian credible intervals
- LLM-generated state-of-store paragraph
- Cross-store hierarchical priors
- A/B test plumbing

**PM challenge to reconciled direction:** the reconciled list of 12 reads as if they were all equally important. They are not. Items 1, 2, 3, 6, 11 (in that order) are what change the merchant briefing the most. Items 4, 5, 7 are correctness hygiene — invisible to the merchant individually but critical for trust. Items 8, 9, 10, 12 are the difference between "ships in 2 weeks" and "ships in 6." **Sequence reflects this.**

---

## 8. Q8 — How do we preserve ML ambition without faking ML?

The test for any Phase 1 design choice should be: *"can a future uplift / hierarchical-prior / calibration model replace this rule, in place, without re-architecting the briefing?"* If not, redesign.

### Hooks Phase 1 must leave in place

1. **`measurement.p_internal` and `ci_internal`** are persisted in EngineRun JSON, never rendered. A future calibration model reads these to compute realized-vs-predicted. **Without the hidden persistence, a future ML layer would have to re-derive them.**

2. **`revenue_range.drivers[]`** is a list of named assumption inputs (e.g., `[{name: "p_action", value: 0.12, source: "vertical_prior_beauty", confidence: "low"}]`). A future uplift model overrides specific drivers (e.g., calibrates p_action per store from realized lift) without touching the formula. **Don't bake assumptions as scalars; bake them as named, auditable, replaceable inputs.**

3. **`recommended_history.json`** — even as a stub. A future ML layer reads recent recommendations, ingests realized metrics from Klaviyo/Shopify, and computes per-play, per-store calibration multipliers. **If Phase 1 doesn't persist what was recommended, calibration is impossible later.** Schema: `{store_id, run_id, anchor_date, plays_recommended[{play_id, audience_id, p50, evidence_class}], plays_rejected[{play_id, reason_code}]}`.

4. **`evidence_class`** as a typed enum (not a string-by-convention). A future uplift model can plug into the `targeting` branch (which today has no measurement) and replace it with `measured` once it has a calibrated lift. **The class transition is the ML-readiness contract.**

5. **`vertical_prior` registry** — extract the per-vertical, per-stage constants currently inline in `action_engine.py` and `analysis/conversion_rate_research_recommendations.md` into a versioned, dated artifact (`config/priors.yaml`). Each prior has: `name`, `value`, `range_p10/p90`, `source_class` (observational/causal/expert), `last_updated`, `applies_to`. **Without this registry, a future hierarchical-prior model has nowhere to write back updated values.**

6. **`Observation` type for state-of-store** — a typed list of facts, not a free-text paragraph. The renderer assembles English from the typed list. A future LLM-narrator reads the same list. **Don't templatize the prose first and try to ML-ify it later; structure the facts first.**

### What Phase 1 must NOT do (to avoid faking ML)

- Do not call any per-store output "calibrated." The only honest copy is "based on observed data" or "based on vertical priors."
- Do not promise lift figures the engine has not back-tested.
- Do not introduce a "learning" CONFIDENCE_MODE that secretly relaxes thresholds — that's the opposite of learning.
- Do not introduce uplift terminology (treatment effect, ATE, ITT) anywhere in code or output. Reserve those names for when there's actual experimentation infrastructure.

### What "real ML" will look like in Phase 3+, so Phase 1 stays compatible

- A `calibration_layer` that reads `recommended_history.json` + Klaviyo realized metrics, computes per-play `realization_factor` (realized / predicted), and writes back to the prior registry. Phase 1's `revenue_range.drivers[]` are the input-output interface.
- A `hierarchical_prior_model` over a fleet of stores that sets per-vertical p_action priors with credible intervals. Phase 1's `priors.yaml` is the swap-in target.
- An `uplift_classifier` that reclassifies a `targeting` play to `directional` once it has 50+ store-months of calibration. Phase 1's `evidence_class` enum is the surface that flips.

This is the explicit answer to "how to preserve ML ambition": **make every assumption a named, auditable, replaceable input today. The ML layer doesn't get added later; it gets plugged in.**

---

## 9. Q9 — What would make this product feel too basic?

Failure modes that would make the engine feel like Klaviyo's segment builder or a generic playbook PDF, ranked by danger:

1. **A briefing that is mostly chips and no analysis.** If the ratio of "categorical labels and audience counts" to "specific observations about this store" exceeds ~3:1, it reads as a CRM segment list. The `state_of_store` paragraph + `Considered, not recommended` rejection list are the structural defenses.

2. **Per-play recommendations that are interchangeable across stores.** If two different beauty merchants get briefings whose recommended plays differ only in audience size (same play, same copy template, same range source), the engine looks like a playbook. Defense: **the rejection list MUST be store-specific** — that's where idiosyncrasy lives. A play rejected on store A for `audience_overlap_with_higher_priority` and on store B for `inventory_blocked` is the visible signal that the engine is reading the actual data.

3. **TARGETING plays without store-specific audience explanations.** "These 320 customers have bought 3+ times in 90 days" is store-specific and good. "Promote subscriptions to your loyal customers" is generic and bad. Defense: every targeting play's `audience.definition` field must include at least one store-data quantity (a count, a SKU, a behavior threshold).

4. **No sense of memory month-over-month.** If month 2's briefing reads like month 1 with different numbers, no merchant believes there's a data scientist. Defense: `Watching` section must reference prior-month thresholds; `Considered` section should ideally surface "this play was Considered last month for the same reason — we'll keep watching." Phase 1B feature (requires `recommended_history.json`).

5. **Dollar projections that look manufactured.** If a `Targeting` play shows `$3,500–$8,200` and a `Strong` play shows `$2,800–$6,400`, the merchant correctly concludes the dollar number is not evidence of confidence. Defense: **suppress dollar projections entirely on Targeting cards in cold-start mode**, and label the source on every range.

6. **Confidence labels that don't change behavior.** If `Strong` and `Targeting` plays render with identical visual chrome, the label is decorative. Defense: targeting cards have a different border treatment, a fixed disclaimer sentence in the body ("This is a who-to-send-to recommendation, based on the audience definition. We have not measured the play's effect in your store."), and no `revenue_range.p50` headline number — just the range.

7. **No abstain.** Even one month where the engine should have refused and didn't is a credibility kill. Defense: ABSTAIN_HARD is mandatory; better to be embarrassed by an honest data-quality memo than discredited by a confident recommendation in a refund storm.

### What the wow surface actually is

In rank order:

1. **The rejection list with reasons.** "We considered Bestseller Amplify; your top SKU is at 9 days of cover, recommending it would risk stockout." This is the single most powerful signal that this is not a generic tool. **Sequence this in Phase 1A.**
2. **The state-of-store paragraph.** Three plain-English facts about *this* store this month. Not "AOV is up." But "AOV is up 7%, which on closer look is concentrated in the top 10% of customers — your overall customer mix is the same, but your VIPs spent more."
3. **The honest abstain.** A "data quality memo" briefing where the engine refuses to recommend and explains why is paradoxically the highest-trust briefing the engine can produce. It is also the briefing most other tools cannot produce.
4. **The launch-window callout.** "Run this in late August — your category sees a 1.3x demand bump going into September." Specific, store-vertical-aware, useful. (Phase 1B.)

The wow is **showing the work**, not the recommendations themselves.

**PM challenge to reconciled direction:** the reconciled memory frames trust through *what the engine doesn't claim* (no fake stats, abstain mode). That is necessary but produces a defensive product. Trust is also built by *what the engine demonstrably did* — reading the data, considering and rejecting, watching specific signals. **The product must do both. Phase 1 must include rejection list and state-of-store, not just guardrails.**

---

## 10. Q10 — Open questions that should be resolved before implementation

Sequenced — questions earlier in the list block more work later:

1. **Does the merchant briefing target a single decision-maker or a team?** If team (ops + lifecycle marketer + founder), the rejection list is more valuable — different roles parse different sections. If single founder, the state-of-store lead matters more. **Pick before designing the visual hierarchy.**

2. **Is the local CSV → HTML workflow the production product for any merchant, or strictly a prototype?** If production, the briefing template needs versioning and backwards-compat. If prototype, we can break it freely. The CLAUDE.md notes "no breaking changes to output file formats without flagging" — so prototype-with-care is the working assumption, but a clean answer would help.

3. **What is the intended cadence after Phase 1?** Monthly today. Weekly in agentic future? The cadence affects materiality floors, recently-run-fatigue gates, and the Watching section's threshold logic. **Resolve before Phase 1B.**

4. **What is "comparable" for vertical priors?** A "beauty" prior covers everything from prestige skincare to mass cosmetics. Without subdividing, the priors registry will overstate calibration quality for skincare-only stores. Subvertical config exists already (skincare/haircare/makeup/wellness/fitness). **Should priors registry be vertical-only or subvertical-aware in Phase 1?** Recommend subvertical.

5. **For the abstain modes, what's the merchant churn cost of an ABSTAIN_HARD month?** This needs a real merchant interview. If 50% of merchants would churn after one ABSTAIN_HARD, the trigger thresholds need to be very conservative (rare). If 5% would churn (because the data-quality memo is itself useful), thresholds can be aggressive.

6. **Rejection list — how many entries is right?** 3 looks thin; 10 looks like noise. Recommend cap at 6 with overflow to a "see all considered plays" expandable. Open: which 6 to surface? Recommend the 6 closest to firing (i.e., would have fired with a small change).

7. **Cross-class ranking** (Skeptic D-2, H-3). Within `recommendations`, do we rank by class first (Strong > Emerging > Targeting always) or by p50 within class? Recommend: **class-first**, then by p50 within class. A Targeting play with higher p50 should not appear above an Emerging play with measured signal. **This is a blocking decision before Phase 1B.**

8. **Does the engine ever recommend zero plays in PUBLISH state, or does PUBLISH always have ≥1?** Recommend: PUBLISH always has ≥1; zero plays = ABSTAIN_SOFT or ABSTAIN_HARD. Cleaner state machine.

9. **How does the targeting-play "fixed disclaimer" copy get reviewed?** Legal/brand review or PM-only? Affects whether the disclaimer can iterate quickly.

10. **Does the future Klaviyo agent consume `revenue_range.suppressed = true` plays?** Recommend no — suppressed-revenue plays are merchant-info-only, not actionable for budget allocation. The Klaviyo agent should only see plays with non-suppressed ranges. **This affects the EngineRun → Klaviyo handoff schema.**

11. **What's the test fixture strategy when `evidence_class` is added?** Existing snapshots will break. Recommend: golden-fixture diff with a labeled migration commit, not a quiet update.

12. **Where does subvertical-aware seasonality live now that seasonality is split out of confidence?** Two options: (a) `revenue_range.seasonality_factor` (multiplies p50), or (b) `launch_window.recommended` (advisory only, doesn't change number). Recommend both: factor for the math, window for the merchant copy. Open question: is the factor merchant-visible? Recommend no — bury in receipts.

---

# Appendix A: Verdict on each of the 12 must-haves (one-line each)

| # | Verdict | Note |
|---|---|---|
| 1. Remove fake stats | ACCEPTED | Day 1–2 of Phase 1A |
| 2. Add evidence classes | ACCEPTED | The structural cut |
| 3. Reclassify heuristic plays | ACCEPTED | Together with #2 |
| 4. Stop multi-window min-p cherry-picking | ACCEPTED | Phase 1B; combiner already exists |
| 5. Simplify confidence (no p double-count) | ACCEPTED | Phase 1B |
| 6. Add abstain mode | ACCEPTED WITH CHANGES | Two modes, not one |
| 7. Inventory/OOS gate | ACCEPTED | Day 8 of Phase 1A |
| 8. Audience-overlap / cannibalization | ACCEPTED WITH CHANGES | Pairwise + portfolio cap in Phase 1B; deeper modeling deferred |
| 9. Anomalous-window / data-quality gates | ACCEPTED | Drives ABSTAIN_HARD |
| 10. Conservative cold-start | ACCEPTED WITH CHANGES | Suppress $ projections; do NOT rely on priors |
| 11. Rejected-play explanations | ACCEPTED | Sequence early — this is the wow surface |
| 12. Economic materiality gates | ACCEPTED WITH CHANGES | Scale-aware, 3 ARR tiers |

---

# Appendix B: Phase 1 product acceptance criteria

A Phase 1A briefing is acceptable if:

1. No p-value, q-value, or CI appears in any merchant-facing rendered output.
2. The HTML briefing has three sections in this order: state-of-store, Recommended, Considered (not recommended). Watching is optional in Phase 1A, required in 1B.
3. At least one rejected-play card with a plain-English reason appears on every PUBLISH-state briefing.
4. ABSTAIN_HARD produces a "Data quality memo" with no plays rendered.
5. ABSTAIN_SOFT produces a briefing with no Strong/Emerging plays, optionally 1–2 Targeting plays clearly labeled, and an explicit "no measured opportunities cleared this month" callout.
6. Targeting cards do not display a `revenue_range.p50` headline number; they display a range with source label.
7. Cold-start stores (<90 days) suppress dollar projections entirely.
8. SKU-pushing plays do not appear when `days_of_cover < 21`.
9. EngineRun JSON contains `measurement.p_internal` and `ci_internal` for every play with a measurement, persisted to receipts.
10. `recommended_history.json` is written every run (even if no consumer reads it yet).
11. Local CSV → HTML workflow runs end-to-end on the existing test merchant fixtures with zero new infrastructure.
12. The "Considered, not recommended" cards include at least 3 reason codes wired: `audience_too_small`, `no_measured_signal`, `inventory_blocked`. Other codes can be `null` until Phase 1B.
