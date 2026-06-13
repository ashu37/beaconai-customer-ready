# DS Architect — Sprint 12 (RFM + Retention Curves) Plan Review

**Reviewer:** ecommerce-ds-architect
**Date:** 2026-05-28
**Reviewing:** agent_outputs/implementation-manager-s12-rfm-retention-plan.md (v1)
**Verdict:** APPROVE-WITH-CHANGES
**Required actions:** revise (B) threshold floors per §H.1; (C) retention gate composition per §H.2; tighten (D) ModelCard refactor framing; (E) add a positive-control monotonicity check for retention; clarify (F) S13-consumer contract for cohort_diagnostics. No code dispatch until v2 lands.

---

## A. Headline

S12 is the cleanest plan in the S10–S13 sequence. Two genuinely independent substrates, classical statistics, no chained refusal, no new library, additive schema, atomic-flip cadence proven by S10/S11. The architectural separation — `predictive_models["rfm"]` (per-customer ranker) vs new top-level `cohort_diagnostics["retention"]` (cohort aggregate) — is correct and worth locking. The remaining gaps are statistical-floor calibration (B, C), not architectural.

## B. Scope decomposition — KEEP

5 tickets, 2 atomic flips: correct shape; mirrors S11 v2.
No S12-T0: confirmed. Re-read of `src/predictive/{bgnbd,gamma_gamma,survival,cf}.py`, `src/main.py:1048-1155`, `src/decide.py`, `src/guardrails.py` shows no latent correctness debt analog to S10-T0 lineage-fatigue. S12 is greenfield.

## C. Storage — DECIDE PIN (Q-S12-E)

**Lock IM's recommendation: new top-level `EngineRun.cohort_diagnostics: Dict[str, Any]`.** Reasons that override the "shoehorn into `predictive_models[retention]`" option:

1. `ModelCard` is contractually a per-customer-ranker shape. Its load-bearing fields (`holdout_rank_spearman`, `holdout_c_index`, `holdout_top_k_recall`, `coverage_at_k`, `parquet_schema_version`) describe ranker objects. Forcing a cohort-aggregate diagnostic into that slot inverts the schema's invariants.
2. D-2/D-3 wipe semantics already cover `data/<store_id>/predictive/` regardless of file type (parquet vs JSON), so storage-policy is not a tiebreaker. But artifact *shape* is — per-customer parquet vs cohort-aggregate JSON are different objects.
3. S13 ranking-strategy consumer reads `predictive_models[*].fit_status`. A non-ranker key in that Dict forces consumer-side special-casing. Cleaner to keep the Dict ranker-pure.
4. Future cohort-aggregate diagnostics (cohort-AOV evolution, cohort-frequency evolution, churn-hazard-by-cohort) all want the same slot.

**`RetentionCard` reusing `ModelFitStatus` four-state enum:** APPROVE. This is the S11 vocab-stacking Option A precedent — labels shared, namespace-disambiguated by dataclass identity. Lock.

## D. Library — DECIDE PIN (Q-S12-F)

**Lock IM's recommendation: custom code for both substrates. Do NOT add `lifelines`.** Three reasons hold:

1. **RFM:** no third-party library does what we want. `pd.qcut` + a 30-line band mapping is the math. A dependency would be net-negative.
2. **Retention:** `lifelines.KaplanMeierFitter` and `sksurv` Kaplan-Meier are designed for **right-censored continuous-time survival**. Our object is **discrete-monthly empirical retention** (% of cohort active in calendar-month-since-acquisition). KM treats "still alive at time t" as a survival probability over continuous time; the conversion to month-bins adds noise and discards the natural cohort-month structure. The discrete-bin empirical estimator + numpy bootstrap is straightforwardly correct, audit-trivial, and aligns with how every DTC analytics tool surfaces this curve.
3. KI-NEW-R (3-library vendor-fork escape hatch) does NOT extend. Maintenance posture improves.

This is consistent with the S11 `scikit-survival` substitution rationale (right-tool-for-the-job) extended in the opposite direction: at S11 we ADDED a library because Cox PH genuinely needed one; at S12 we DECLINE one because empirical retention does not.

## E. RFM substrate — segment scheme (Q-S12-A)

**Lock IM's recommendation: 11 named segments. Raw quintile triplet preserved on parquet.** Three reasons:

1. Operational consumer (S13 ranking-strategy chain) is a coarse ordinal ranker; 11 segments give the audience-builder a stable sort key. 125 raw cells re-collapse on the consumer side.
2. Below ~200 customers, raw 125-cell occupancy is sparse and unstable; named-segment definition is band-based and degrades more gracefully near the 50-customer floor.
3. Industry-canonical names ("Champions", "At Risk", "Hibernating") are operator-readable. Raw cell IDs ("R5-F3-M2") are not.

**Critical hybrid preserved:** the parquet still carries `r_score`, `f_score`, `m_score` as int columns. A future sprint can re-derive a different segmentation without re-fitting. Lock.

## F. RFM validation metric (Q-S12-B — DS LOCK)

The plan correctly identifies that RFM is **deterministic segmentation**, not a fit, so the validity story is **internal-consistency**, not forecasting accuracy. The dual-gate proposal (segment-monotonicity Spearman + quintile-coverage REFUSED guard) is the right shape.

**Critique:** IM's draft floors (0.50/0.55/0.60) are **too lenient**. The S13 consumer reads RFM as the **explicit floor of the ranking chain**. If the floor itself has weak monotonicity, the chain's degradation surface is misleading.

A healthy DTC merchant where segmentation captures economic structure should produce Spearman ≥ 0.80 between segment-order and observed mean revenue. The literature anchor is straightforward: RFM was *designed* to rank by realized economic value; if it does not, either (a) the merchant has no F/M variation (cold-start; handled by INSUFFICIENT_DATA below 50 customers), or (b) the merchant's revenue is concentrated in atypical customers (At-Risk / Cannot-Lose-Them outliers — a real-merchant signal worth surfacing, not a VALIDATED ranker).

**LOCKED THRESHOLDS (Q-S12-B):**

| Stage | n_customers_VALIDATED | segment_monotonicity_spearman_VALIDATED | quintile_coverage_min_VALIDATED |
|---|---|---|---|
| startup | 50 | **0.60** | 0.10 |
| growth | 200 | **0.65** | 0.10 |
| mature | 500 | **0.70** | 0.10 |
| enterprise | 1000 | **0.70** | 0.10 |

Relaxation factors:
- `provisional_n_multiplier`: 0.5 (unchanged)
- `provisional_segment_monotonicity_spearman_floor`: **0.40** (was 0.30)
- `provisional_quintile_coverage_min_floor`: 0.05 (unchanged)
- `absolute_customers_floor`: 50 (DS-locked, unchanged)
- REFUSED secondary guard `quintile_coverage_min < 0.05`: APPROVE.

Rationale for the upward revision:
- Spearman 0.50 means barely-better-than-random ordinal agreement on a deterministic segmentation. That should not VALIDATE on the floor of the chain.
- Spearman 0.60 at startup leaves headroom for noise on small-N populations.
- 0.70 at mature reflects the expectation that a $1M+ ARR brand with 500+ customers should have very strong monetary-vs-frequency monotonicity (R is the noisier of the three; F and M are usually tightly aligned).
- 0.40 PROVISIONAL floor: below this, the segmentation has near-zero economic signal — better to demote to recency than to ship as ranker.
- These are still speculative-until-S14; KI-NEW-P extended.

**Mann-Whitney U as tertiary diagnostic (not gating):** APPROVE as IM proposes. Useful for surfacing adjacent-segment collapse in operator inspection.

## G. Retention substrate validation (Q-S12-C — DS LOCK)

The dual-gate proposal (bootstrap CI width at month 3 + cohort_count secondary) has a structural problem the IM acknowledged: **CI width is itself a function of cohort size**. A merchant with 12 cohorts of 200 customers each will have tight CIs; a merchant with 12 cohorts of 25 customers each will have wide CIs by Bernoulli statistics alone. The CI-width gate is therefore *partially redundant* with the cohort-size floor (`min_cohort_size_floor=20`), not orthogonal to it.

**This is acceptable** for VALIDATED, but it means the *primary gate semantics* should be: "does this curve carry usable information?" — which CI width captures. Cohort count is a necessary but not sufficient prerequisite.

**Add a third gate (NEW, DS-required): monotonicity check.** Cumulative retention (% ever returned in [0, M]) should be monotonically non-increasing as M increases. Period-retention (active in (M-1, M]) need not be monotone but should not invert dramatically (>10 percentage-point rise from month to month is suspicious). The IM has this as "tertiary diagnostic, does not gate." **DS revises: monotonicity violation in CUMULATIVE retention is a REFUSED condition** (it indicates a data-shape bug or cohort-definition error — retention cannot mathematically rise in the cumulative definition). Period-retention monotonicity stays diagnostic-only.

**LOCKED THRESHOLDS (Q-S12-C):**

| Stage | cohort_count_VALIDATED | bootstrap_ci_width_at_month_3_max_VALIDATED |
|---|---|---|
| startup | 6 | **0.25** (was 0.30) |
| growth | 12 | **0.20** (was 0.25) |
| mature | 12 | **0.15** (was 0.20) |
| enterprise | 12 | **0.15** (was 0.20) |

Relaxation factors:
- `provisional_n_multiplier`: 0.5
- `provisional_bootstrap_ci_width_at_month_3_max`: **0.35** (was 0.40)
- `absolute_cohort_count_floor`: 3 (DS-locked from prior verdict)
- `bootstrap_iterations`: 1000 (APPROVE)
- `months_horizon`: 12 (APPROVE)
- `min_cohort_size_floor`: 20 (APPROVE)
- NEW: `cumulative_retention_monotonicity_violation` → REFUSED.

Rationale for the downward revision:
- Original IM floors (0.30 / 0.25 / 0.20 / 0.20) translate to "the 95% CI band on month-3 retention spans up to 30 percentage points." A 30pp band on a quantity that itself is typically 20-50% is not informative for ranking purposes.
- A mature DTC merchant with 12 cohorts of 50+ customers each should comfortably hit ≤0.15 CI width.
- Stage-keyed because startups will legitimately have small cohorts.
- PROVISIONAL floor 0.35 still admits genuinely-thin merchants into the operator-visible band without quoting magnitudes.

**Gate composition:** keep AND (both cohort_count AND CI-width must clear). NOT OR. Reason: CI-width without cohort_count is statistical artifact; cohort_count without CI-width is shape-only. Both are necessary.

**Bootstrap CI coverage as future calibration:** out of scope for S12. Note in KI-NEW-P.

## H. ModelCard field-count refactor (Q-S12-1)

IM applies the strict letter of the S11 verdict (2 fields < 3-field trigger) → DEFER.

**DS adjudication: DEFER, but with a sharpened condition.** The strict letter is correct; the spirit is "refactor when organic pressure surfaces." Three considerations:

1. The 2 new fields (`segment_monotonicity_spearman`, `quintile_coverage_min`) are **structurally different** from prior fields — they are NOT holdout-metric / fit-quality fields; they are internal-consistency-of-deterministic-segmentation fields. Mixing them onto the same flat dataclass as `holdout_c_index` and `coverage_at_k` is mildly type-confused, but tolerable.
2. `RetentionCard` already absorbed pressure away from ModelCard.
3. The real refactor moment is when S13 wires consumer reads — at that point a `Dict[str, float] metrics` shape with namespaced keys (`rfm.segment_monotonicity_spearman`, `bgnbd.holdout_rank_spearman`) would be substantially cleaner than the current per-substrate optional-field accumulation.

**DEFER to S13, NOT S15+.** Lock the refactor as an explicit S13-T0 candidate ticket in ROADMAP. If S13 wires consumers without organic pressure, defer further. If S13 wiring touches 4+ read sites with `if model_card.holdout_X is not None`, refactor there.

**Founder action on Q-S12-1: confirm DEFER.** Not founder-domain — this is a DS architectural call. Founder may sign off but no founder veto needed.

## I. Synthetic-fixture posture (Q-S12-G — Pivot 5)

IM's reading is correct and consistent with Pivot 5. Pivot 5 forbids "fabricated VALIDATED" (reshape fixtures to fire builders), NOT "synthetics may VALIDATE when the math says they should."

**RFM on healthy Beauty (3,844 repeat customers, 259 days) SHOULD VALIDATE.** A failure to VALIDATE would indicate either:
- A bug in the segment-monotonicity computation; or
- The synthetic does not actually have monotone economic structure (a fixture-honesty problem in the opposite direction).

**Retention on Beauty (259 days ≈ 8-9 cohorts):** likely PROVISIONAL at the new tightened floors (cohort_count_validated=12 for mature). If Beauty is profiled as mature, PROVISIONAL is the honest outcome. If profiled as growth (cohort_count_validated=12 also), PROVISIONAL. If profiled as startup (cohort_count_validated=6), likely VALIDATED.

**This is the right posture.** It also gives us our first real test of whether the four-state vocabulary is operationally meaningful when at least one substrate VALIDATES.

**Critical real-merchant disclaimer:** synthetic VALIDATED on RFM does NOT subordinate the KI-NEW-P closure criterion. Real beta-merchant calibration data at S14 remains the closure gate. Surface explicitly in the KI-NEW-P extension sub-bullet at T3.

**Founder action on Q-S12-G: acknowledge.** Not founder-domain. Posture-confirmation only.

## J. KI filing posture (Q-S12-H)

**Lock IM's recommendation: extend KI-NEW-P only.**

Sharpening: RFM/retention gates are *categorically different* from BG/NBD/G-G/survival/CF gates. The latter four gate on forecasting/recovery accuracy against held-out data. RFM gates on **internal segmentation consistency** (no held-out object — the segmentation IS the answer). Retention gates on **CI tightness from bootstrap resampling** (no predictive object — the curve IS the answer).

This **does not** justify a new KI letter. But it DOES mean the KI-NEW-P sub-bullet structure must call out the difference: real-merchant calibration data for these two substrates means something different than for the prior four. Specifically:

- BG/NBD / G-G / survival / CF closure: realized customer behavior vs predicted ranking → calibration plot.
- RFM closure: realized 90d / 180d / 365d LTV-per-segment vs the segmentation snapshot → does the operator-readable "Champions are highest-LTV" claim hold up?
- Retention closure: realized cohort retention curves vs the bootstrapped CI bands at S12 fit → are the CIs honest, or do real cohorts drift outside the band more often than 5%?

These three closure-criteria shapes go into the KI-NEW-P sub-bullet at T3 as an explicit note.

No new KI letter. Founder action on Q-S12-H: acknowledge default.

## K. Cross-cutting technical pins

- **Determinism comparator extension at T1.5 + T2.5:** APPROVE the two new normalized paths (`predictive_models.rfm.fit_timestamp`, `cohort_diagnostics.retention.fit_timestamp`).
- **Bootstrap determinism:** APPROVE `seed=0` default + byte-identical CI assertion across two same-seed runs. Add explicit test pin.
- **`_coerce` bool set at T1/T2 (not T1.5/T2.5):** APPROVE (S10-T1.5 lesson).
- **`cohort_diagnostics` round-trip via `_from_dict_engine_run`:** APPROVE tolerated-as-missing extension (mirrors `predictive_models` L1006 precedent).
- **Renderer non-consumption:** APPROVE grep pin (`grep -rn "predictive_models\|cohort_diagnostics" src/render_*` → empty). Pin this in the T1.5 + T2.5 acceptance criteria.
- **Single-demote-channel invariant preserved:** S12 substrate code MUST NOT write to `engine_run.recommendations`. Pinned by code review + S7.6 C1 test (unchanged).
- **Positive-control synthetic for retention (NEW REQUIREMENT):** add a deterministic positive-control fixture (e.g., 12 monthly cohorts of 200 customers each with stable 40% month-1 retention by construction) and assert `bootstrap_ci_width_at_month_3 < 0.10` + `cumulative_retention_monotonicity_violation == False`. Mirrors S11-T1 c-index positive control. Required for T2 acceptance.

## L. Open questions adjudication summary

| # | Question | Domain | DS verdict | Founder action |
|---|---|---|---|---|
| Q-S12-1 | Defer ModelCard refactor? | DS | DEFER to S13-T0 candidate; explicit ROADMAP note | Confirm |
| Q-S12-A | 11 named segments vs 125 raw cells | DS-tech / founder-product | 11 named + raw quintiles on parquet | Confirm |
| Q-S12-B | RFM Spearman thresholds | DS-LOCK | 0.60 / 0.65 / 0.70 / 0.70 (PROVISIONAL 0.40) — see §F | Acknowledge |
| Q-S12-C | Retention CI-width thresholds | DS-LOCK | 0.25 / 0.20 / 0.15 / 0.15 (PROVISIONAL 0.35); + monotonicity-violation REFUSED — see §G | Acknowledge |
| Q-S12-D | S12-T0 correctness debt? | DS | No T0; confirmed by re-read | — |
| Q-S12-E | cohort_diagnostics slot? | DS | New top-level slot; locked | Confirm |
| Q-S12-F | Custom code, no lifelines? | DS | Custom code; locked | Confirm |
| Q-S12-G | Synthetics will VALIDATE? | DS / founder | Pivot-5-consistent; expected | Acknowledge |
| Q-S12-H | KI letter posture? | DS | Extend KI-NEW-P only with closure-shape note | Acknowledge |

## M. S11 retrospective bullets (≤5)

1. **Four-state vocabulary held up cleanly across BG/NBD + G-G + survival + CF.** S12 substrates extend the same enum without modification. No revision to the DS-locked four-state from S10. The vocab-stacking Option A (labels-shared / namespace-disambiguated) also held — no need to revisit.
2. **Library substitution at S11 (`lifelines` → `scikit-survival`) was net-positive; the same right-tool reasoning at S12 supports custom-code over `lifelines.KaplanMeierFitter`.** Lesson: the "library convenience" argument never automatically wins; the operational object shape (continuous-time censored vs discrete-bin empirical) is the deciding criterion.
3. **The S11 CF positive-control synthetic (recall@10 = 0.344 on a constructed monotone fixture) caught no real bug but DID give us the confidence to ship at recall@10 ≥ 0.08 floor.** Pattern is worth keeping. ADD: a positive-control monotonicity fixture for retention at S12-T2 (NEW REQUIREMENT in §K above). This is the S11 lesson applied forward.
4. **Threshold floors set in IM drafts have systematically come in too low.** S11 IM drafted c_index=0.65; DS revised to 0.62/0.63 (DOWN). S12 IM drafts RFM Spearman 0.50; DS revises to 0.60-0.70 (UP). The pattern is: IM drafts toward "easy to clear on synthetics"; DS revises toward "meaningful when it clears on real merchants." The S14 calibration will adjust both directions. Test-plan template should explicitly call out "floors are speculative; DS-lock at plan review, not at IM draft."
5. **`_coerce` bool-set regression at S10-T1.5 was a real lesson and the S11 / S12 plans preempt it.** Keep the pre-emptive-at-substrate-ticket pattern. No vocabulary revision needed.

## N. Required v2 changes (IM action list)

1. Update §B.5 with locked Spearman thresholds (0.60 / 0.65 / 0.70 / 0.70; PROVISIONAL floor 0.40).
2. Update §C.5 with locked CI-width thresholds (0.25 / 0.20 / 0.15 / 0.15; PROVISIONAL 0.35).
3. Promote cumulative-retention-monotonicity-violation from tertiary diagnostic to REFUSED condition in §C.4 and §C.6.
4. Add positive-control retention fixture requirement to §C and T2 acceptance criteria.
5. Add explicit renderer-non-consumption grep pin to T1.5 + T2.5 acceptance criteria.
6. Update §E.1 Q-S12-1 framing: DEFER, but explicitly NAME S13-T0 as the candidate refactor moment (not "S15+").
7. Update §F KI-NEW-P extension sub-bullet to call out the categorical-difference closure shapes for RFM (segment-LTV holdup) vs retention (CI honesty) vs the other four (ranker calibration).
8. Add `Deviation check: none.` to all commit body templates (per S11 v2 §P precedent — IM already has).

No other revisions required. v2 is dispatchable after these 8 changes land.

*End of verdict.*
