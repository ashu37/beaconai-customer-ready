# DS Architect — S10 Cold-Start Semantics & EB Interaction

**Date:** 2026-05-25
**Reviewer:** ecommerce-ds-architect
**Context:** Founder follow-up on J.3 of `agent_outputs/ds-architect-s10-plan-review.md` (PASS-WITH-CHANGES). Question spans S10–S13 ML predictive layer and the post-S8 typed surface.

**Founder question (verbatim):** "Regarding J.3, what happens to the newly onboarded customer? Will the model always generate REFUSED threshold? What does that mean for my plays and all the EB mix that was done in previous sprints? Check with DS — what happens with cold-starts and what role do these ML models play? This question is also true for the upcoming sprints."

---

## Part 1 — Cold-start semantics: what actually happens

### Case A: Newly onboarded MERCHANT (<3 months data, <200 repeat customers, <500 orders)

**Math.** `lifetimes.BetaGeoFitter.fit()` on a frame with <200 repeat customers either (a) converges to a degenerate `(r, α, s, β)` that places nearly all mass on "dead" because the inter-purchase-time distribution has no signal, or (b) raises `ConvergenceWarning` because the likelihood surface is flat. Gamma-Gamma needs n≥2 transactions per customer for *most* customers to estimate `(p, q, γ)` honestly; below a few-hundred customers it returns numerically valid but variance-inflated parameters. **The model returns something. It is not trustworthy.**

**Engine today (post-S8, no ML).** `detect_cold_start` (`src/detect.py:117`) flags `cold_start=True` when `days_of_clean_data < 90` (default; configurable). This already drives `sizing.py:654` → `_suppressed_range("cold_start", ...)` so the **revenue range is suppressed** but the play itself still surfaces with cohort signal + suppressed dollars. Slate is non-empty if any builder produces cohort signal; revenue ranges are hidden. This is the current month-1 posture for cold-start merchants.

**Engine at S10 close (ML at REFUSED).** S10's `ENGINE_V2_ML_BGNBD` and `ENGINE_V2_ML_GAMMA_GAMMA` ship ON, but `PlayCard.predicted_segment` and `PlayCard.model_card_ref` remain `Optional[...]=None` at S10 close per plan Part B L76–78. **No PlayCard consumes ML at S10.** The ModelCard is written to `engine_run.predictive_models["bgnbd"].fit_status = "REFUSED"`. **Slate is byte-identical to S9 for cold-start merchants.** ModelFitStatus gate is dormant.

**Engine at S13 close (audience ranking ML-driven).** S13 wires ML into AUDIENCE via `ranking_strategy`. A REFUSED model means the audience builder's `ranking_strategy` falls back to RFM quintile (S12) or — if S12 also REFUSED — to recency-order. **Plays that depend exclusively on ML scoring do not surface; plays that use ML only for ranking-within-audience still surface with a degraded (non-ML) ordering.** This is the load-bearing claim that needs T3 precedence test backing.

**What the merchant sees at S10 close:** identical to S9 — cohort plays with suppressed dollar ranges. **What the merchant sees at S13 close:** identical *play set* (the 4 wired Tier-B builders' cohort logic is independent of ML), but with the within-audience customer ordering driven by recency rather than predicted LTV. The slate is not empty.

### Case B: Newly onboarded CUSTOMER within an established merchant (a single 1-order customer in a healthy fixture)

**Math.** BG/NBD specifically models `(frequency, recency, T)` where `frequency = #repeat purchases`. A 1-order customer has `frequency = 0`. `lifetimes` treats these as "one-time-buyers" and returns `P(alive) ≈ β/(β+T)` and `expected_transactions ≈ r/α × ...` — both numerically valid but driven entirely by the population-level posterior, not the individual's history. **There is no individual signal; the score IS the population prior.** This is fine for ranking *across* one-time-buyers (they will all get roughly the same score), and BG/NBD does not refuse on them.

**Engine emits.** Same as today — these customers appear in audiences keyed on first-order behavior (e.g., `cohort_journey_first_to_second`). Per-customer ML score exists but adds little ordering information for them. **No collision** — the merchant-level ModelCard is VALIDATED if the store as a whole clears the floor; individual-customer thinness is silent.

### Case C: Interaction with the existing EB layer (`bayesian_blend` / `PSEUDO_N_BY_STATUS` / `effective_pseudo_n`)

**EB does cohort-level shrinkage on the play's measured effect.** `bayesian_blend(prior_value, pseudo_n, store_value, n_observed)` collapses to the prior when `n_observed=0`, dominated by the store when `n_observed >> pseudo_n`. The note at `sizing.py:444-445` explicitly handles this: `"observed_n=0; posterior collapses to prior (cold-start)"`. This is the **cohort-effect cold-start handler** and it already works.

**ML does per-customer ranking, not effect-size estimation.** BG/NBD does not produce a cohort effect; it produces P(alive) and expected-transactions *per customer*. These quantities never enter `bayesian_blend`. They never affect `revenue_range`. They never affect `evidence_source`. They feed `ranking_strategy` (S13) only.

**Conclusion: ML does NOT duplicate EB.** They operate on different objects:
- EB: cohort-level effect → posterior point estimate → revenue range.
- ML: per-customer expected-value → audience ordering → which N customers get shipped to Klaviyo.

They are complementary, orthogonal, and the three-orthogonal-gate framing already encodes this (STATE.md §4): validation-status (EB) and ModelFitStatus (ML) live at different layers.

### Case D: Forward-looking S11/S12/S13

- **S11 survival (lifelines / Cox PH for replenishment timing).** Cold-start failure: insufficient event count (need ~30 events of the censored kind for Cox PH to fit; below that, the hazard function is flat). Same shape as BG/NBD — model fits but is untrustworthy → REFUSED.
- **S12 CF (implicit ALS look-alikes).** Cold-start failure: sparse interaction matrix. ALS needs ~50+ users × 50+ items with >2 interactions each; below that, factors are random noise. REFUSED.
- **S12 RFM (statistical).** Quintiles require ≥50 customers to be meaningful; below that, quintile cuts collapse to a few customers per bin. This is the *cleanest cold-start fallback* — when BG/NBD is REFUSED but the store has, say, 50–199 repeat customers, RFM quintiles still produce a usable ranking. RFM should be the **gravity-floor fallback** for the entire ranking-strategy chain.
- **S13 audience ranking.** `ranking_strategy` chain: BG/NBD/G-G → CF → survival → RFM → recency. Each layer's REFUSED triggers the next. **The slate degrades gracefully because the chain has a non-ML floor.**

---

## Part 2 — Relationship to EB / `bayesian_blend` / PSEUDO_N_BY_STATUS

**Q: Duplicate, complement, or conflict?** **Complement.** Different mathematical objects (cohort effect vs per-customer ranking), different pipeline layers (SIZING vs AUDIENCE), different failure modes (untrusted prior vs untrusted per-customer score). The three-orthogonal-gate framing is correct and the gates are genuinely independent.

**Q: Does ModelFitStatus correlate with `validation_status`?** They are *correlated by population* (small stores fail both — small-N hits the prior side via `n_observed=0` and the ML side via training-window-too-short) but *causally independent* (the prior's validation status depends on its source artifact + reviewer-assigned tier, not on this merchant's data). A merchant can have:
- VALIDATED ML fit + HEURISTIC_UNVALIDATED prior → revenue range suppressed (PRIOR_UNVALIDATED), but per-customer ranking trustworthy → play surfaces with ML ranking and no $.
- REFUSED ML fit + VALIDATED_EXTERNAL prior → revenue range published, audience ranked by RFM fallback → play surfaces with $ but cruder targeting.

These two cases must be distinguishable in `ReasonCode` emission. Plan T3's precedence test (audience-floor → cohort-p → prior-validation → ML-fit) is correct: ML-fit is **lowest** precedence because a REFUSED ML fit does not block the card — it only degrades the ranking. Only `audience-floor`/`cohort-p`/`prior-validation` failures *demote to Considered*; ML-fit failure stays in Recommended and falls back to RFM. **This is the load-bearing decision and the plan implies it correctly at L283–284.**

**Q: Is there an architectural seam where ML "kicks in only after EB"?** Yes — and the plan already has it. EB lives in SIZING; ML lives in AUDIENCE. The AUDIENCE layer's `ranking_strategy` is consulted **only for an audience already selected by EB-cleared SIZING**. ML refines *within* an already-cleared play. ML never gates the play itself; it only orders the customers within it.

**Q: Are PSEUDO_N values affected?** **No.** `PSEUDO_N_BY_STATUS = {30, 15, 10}` is locked through S14 (STATE.md §5 invariant 5). The ML layer does not touch sizing.py. Verified — `src/sizing.py` is in the "not touched" list at plan Part N L545.

---

## Part 3 — What does a cold-start merchant actually see month-1?

**Today (post-S8).** A merchant with <3 months data triggers `detect_cold_start=True`. Pipeline runs every play; revenue ranges are *suppressed* (`sizing.py:655`); cohort signals that clear p-value still surface as Recommended cards with suppressed $; cards without cohort signal surface in Considered with `INSUFFICIENT_DATA`-class ReasonCodes. Wow story today: "We looked at your store; here are 1–3 plays we think apply, but we cannot quote revenue impact yet." **Honest, but thin.**

**S10 close (BG/NBD+G-G REFUSED everywhere on cold-start).** Identical to today. The ModelCard appears in `engine_run.predictive_models["bgnbd"].fit_status = "REFUSED"` with `fit_warnings=["below_repeat_customer_floor"]`. **No PlayCard change.** Substrate-only, as the plan asserts (L386). Wow story is identical to S9.

**S13 close (ML-driven audience ranking).** Plays still surface (cohort logic unchanged, EB suppression unchanged), but the audience-ordering inside each play uses the RFM/recency fallback rather than predicted LTV. The merchant sees the same plays as a healthy store would see; the *quality of within-play targeting* is degraded but the slate is non-empty. **This is the load-bearing claim that should be tested explicitly** — propose a new fixture-level test at S13: `test_cold_start_merchant_gets_non_empty_slate_with_rfm_fallback`.

**There is no version of the engine in the S10–S13 plan where a cold-start merchant gets an empty slate from ML refusal.** ML refusal is *degradation*, not *demotion*.

---

## Part 4 — Threshold revision (REQUIRED)

**Yes, I revise J.3.** Three changes.

### 4.1 ModelFitStatus vocabulary should not match EB vocabulary

I considered the suggestion to map ModelFitStatus onto RESEARCH/PROVISIONAL/VALIDATED. **Reject.** EB's `validation_status` is a property of the **prior** (a static artifact about an effect size, reviewer-graded once). ModelFitStatus is a property of the **fit on this merchant's data this month** (re-computed every run). Conflating them in the vocabulary invites readers to think they're the same thing. Keep distinct enums; document the parallel in the ModelCard schema docstring.

### 4.2 The third state should be `INSUFFICIENT_DATA`, not `REFUSED`, for cold-start

This is the load-bearing change. **`REFUSED` connotes "the model failed."** For a brand-new merchant, the model didn't fail — *we declined to fit it*. These are different audit stories. Recommend:

- **VALIDATED** — fit converged, holdout MAPE < 25%, training-window + repeat-customer floors met.
- **PROVISIONAL** — fit converged, envelope thin (3–6 months OR 200–499 repeat OR holdout MAPE 25–40%). Ranking usable, magnitudes not quotable.
- **INSUFFICIENT_DATA** — we did not attempt the fit (below 3 months / 200 repeat / 500 orders). Not a failure; an enrollment-deferred state. No `ConvergenceWarning` involved.
- **REFUSED** — we attempted the fit and it failed (ConvergenceWarning raised OR holdout MAPE > 40% despite clearing the floor). This is a genuine model-side failure that operator/DS should investigate.

**Reasoning.** The two states have different downstream consequences:
- `INSUFFICIENT_DATA` → S13 ranking-strategy falls through to RFM **silently** (this is expected for a new merchant).
- `REFUSED` → S13 ranking-strategy falls through to RFM **and** writes an operator-visible alert (this is a model-health issue requiring review).

The plan currently conflates these two ("REFUSED: <3 months ∨ <200 repeat ∨ ... ∨ ConvergenceWarning raised"). Splitting them clarifies the audit story and matches D-2 / D-3 privacy semantics (we never *attempted* per-customer scoring on `INSUFFICIENT_DATA` merchants, so the deletion story is trivial — no parquet artifact exists).

### 4.3 Map to ReasonCode

For T3's enum-add at `src/engine_run.py`:
- `ReasonCode.MODEL_FIT_INSUFFICIENT_DATA` — dormant in S10, consumed at S13 for cold-start merchants.
- `ReasonCode.MODEL_FIT_REFUSED` — dormant in S10, consumed at S13 for fit-failure (rare).

Two codes, not one. **Recommend adding both at S10-T3.**

### 4.4 PROVISIONAL as the default for thin-but-healthy merchants

The plan's PROVISIONAL band (3–6 months OR 200–499 repeat OR 500–1499 orders OR MAPE 25–40%) stays. This is correct as the middle band for stores above the absolute floor but below the VALIDATED bar. PROVISIONAL fits **publish** to parquet and are **consumed** by S13 ranking-strategy with a `provisional_ranking=true` flag on the audience.

---

## Part 5 — Cross-sprint consistency (S11 / S12 / S13)

**S11 — survival (lifelines Cox PH / Kaplan-Meier).** Cold-start failure: <30 censored events. Same four-state vocabulary applies (`VALIDATED` / `PROVISIONAL` / `INSUFFICIENT_DATA` / `REFUSED`). Sprint-specific edge case: `replenishment_due` is honestly dormant on Beauty (KI-NEW-G); when survival fits on a real cosmetics merchant, the **expected** state is INSUFFICIENT_DATA for the first 90 days because replenishment events haven't accumulated. The audit story must make this normal, not alarming.

**S12 — collaborative filtering (implicit ALS) + RFM + retention curves.** ALS cold-start: matrix below ~50×50 with sparse interactions → INSUFFICIENT_DATA. RFM cold-start: <50 customers → INSUFFICIENT_DATA (quintile cuts collapse). Retention curves: <3 cohorts → INSUFFICIENT_DATA. Sprint-specific edge case: **RFM is the ranking-strategy floor** — below RFM there's only recency-order. Recommend that S12 explicitly designate RFM as the floor in the ranking-strategy chain's documentation, with recency as the absolute last-resort. This makes the degradation chain auditable.

**S13 — audience ranking integration.** The ranking-strategy chain (BG/NBD → CF → survival → RFM → recency) reads each ModelCard's `fit_status` and selects the highest-quality available. Cold-start failure: all four ML models INSUFFICIENT_DATA → recency-order fallback. **The slate does not empty.** Sprint-specific edge case: `month_2_delta` requires both months' ModelCards to be PROVISIONAL or better; INSUFFICIENT_DATA → INSUFFICIENT_DATA gives no delta, and the merchant's month-2 wow story must rely on cohort-signal evolution alone (which is fine — 30 more days of orders DOES change EB posteriors via `bayesian_blend`'s observed-N term). **Month-2-return is preserved for cold-start merchants through the EB path, not through ML.** This is the most important architectural finding of this verdict.

---

## Summary

**(a) Does cold-start kill the slate? No.** A cold-start merchant gets the same plays at S10/S11/S12/S13 as they get today, with the same revenue-range suppression. ML refusal is a *degradation of within-audience ranking*, not a demotion of the play itself. ML never gates a play's surfacing; only cohort-p, prior-validation, and audience-floor do. The S13 ranking-strategy chain (BG/NBD → CF → survival → RFM → recency) has a non-ML floor (recency), so the chain always returns *something*. Propose explicit test at S13: `test_cold_start_merchant_gets_non_empty_slate_with_rfm_fallback`.

**(b) Does ML duplicate EB? No, complement.** EB (`bayesian_blend`, PSEUDO_N) operates on **cohort-level effect estimates** in SIZING. ML (BG/NBD, G-G) operates on **per-customer ranking** in AUDIENCE. Different objects, different layers, different failure modes. `PSEUDO_N_BY_STATUS = {30,15,10}` is untouched by S10–S13 (locked per STATE.md §5 inv 5). The three-orthogonal-gate framing is genuinely orthogonal: a cold-start merchant can have a VALIDATED prior (so $ publishes) but INSUFFICIENT_DATA ML (so audience falls to RFM). The ReasonCode precedence (audience-floor → cohort-p → prior-validation → ML-fit) is correct — ML-fit is lowest because it does not demote.

**(c) What the merchant sees in cold-start month-1.** Today (S9): cohort plays with suppressed dollar ranges, EB collapsing posteriors to priors. S10 close: identical (ML is substrate-only). S13 close: identical play set, but within-audience customer ordering is RFM-fallback rather than predicted-LTV. Slate is never empty from ML alone. **Month-2-return for cold-start merchants is preserved through the EB path** (30 more days of orders shifts `n_observed` in `bayesian_blend`), not through ML. This is load-bearing.

**(d) Threshold-vocab revision (REQUIRED).** Split `REFUSED` into two states:
- `INSUFFICIENT_DATA` — below floor (we declined to fit). Silent fallback, no operator alert.
- `REFUSED` — above floor but ConvergenceWarning or holdout MAPE > 40%. Operator alert.

These have different audit stories and different privacy semantics (no parquet artifact for INSUFFICIENT_DATA). Add two ReasonCodes at S10-T3: `MODEL_FIT_INSUFFICIENT_DATA` and `MODEL_FIT_REFUSED`. Do **not** map ModelFitStatus onto RESEARCH/PROVISIONAL/VALIDATED — `validation_status` is a property of the prior artifact, ModelFitStatus is a property of this merchant's fit this month; distinct enums.

**(e) Cross-sprint consistency.** Four-state vocabulary (`VALIDATED` / `PROVISIONAL` / `INSUFFICIENT_DATA` / `REFUSED`) generalizes across S11 (survival), S12 (CF / RFM / retention), and S13 (audience ranking integration). RFM should be explicitly designated the ranking-strategy floor at S12; recency is the absolute last-resort. `replenishment_due` survival fits will sit at INSUFFICIENT_DATA for the first 90 days on real cosmetics merchants — make this expected, not alarming, in the audit copy.

---

## Required changes to S10 plan (revising prior J.3 verdict)

1. Replace tri-state (`VALIDATED`/`PROVISIONAL`/`REFUSED`) with four-state (add `INSUFFICIENT_DATA`).
2. Add **two** ReasonCodes at S10-T3: `MODEL_FIT_INSUFFICIENT_DATA` and `MODEL_FIT_REFUSED`. Both dormant in S10.
3. Document in the ModelCard schema that `INSUFFICIENT_DATA` produces no parquet artifact (D-2/D-3 deletion-trivial).
4. Add to S13 plan acceptance: `test_cold_start_merchant_gets_non_empty_slate_with_rfm_fallback`.
5. Add to S13 plan: month-2-return for cold-start merchants is preserved through EB's `n_observed` shift, not through ML — pin this in T1.5 acceptance.

## Open questions for the founder

- Confirm four-state vocabulary over tri-state? (DS strongly recommends four-state.)
- Confirm RFM as the explicit ranking-strategy floor at S12 (recency as last-resort)?
- File KI-NEW-P with the four-state thresholds rather than the tri-state version in the prior verdict.
