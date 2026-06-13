# BeaconAI Sprints 6–14 — Revised Master Plan (ML Predictive Layer Reframe)

**Author:** implementation-manager
**Date:** 2026-05-17
**Branch baseline:** `post-6b-restructured-roadmap` (post-S7.5-T3.5 close, suite 1237p / 14s / 1f)
**Supersedes:** ARCHITECTURE_PLAN.md Part II §"Total scope and beta gating" arc (S6→S11) for sprints S9–S11.
**Status:** Founder-approved reframe — full plan revision authorized.

---

## Part A — Executive Summary

### The Reframe (three paragraphs)

The founder reframed beta success away from "6-month outcome-loop calibration" toward **month-1 wow → month-2 return**. The previous plan made Phase 9 outcome ingestion (S10) the single beta-blocking learning surface. That math was always 3–6 months downstream of the first authorized campaign send, which is itself downstream of the first merchant briefing. Under the previous framing, the engine had to look smart from one CSV alone in month 1 — and the previous plan offered Tier-B directional builders (S6–S7) plus an Empirical-Bayes blend (S8) as the only month-1 trust surface. That is not enough for a returning user on month 2.

The new framing introduces an **ML Predictive Layer** living in the AUDIENCE step of the pipeline (not the decision core). Five classical, well-trodden ML capabilities — BG/NBD + Gamma-Gamma probabilistic LTV, survival analysis on reorder gaps, collaborative filtering on co-purchases, statistically banded RFM segmentation, and cohort retention curves with CIs — produce **per-customer scores from CSV-only data with zero outcome history**. These scores feed the Tier-B audience builders as an *optional ranking strategy*. They do not replace the cohort p-value gate; they introduce a third orthogonal gate, `ModelFitStatus ∈ {VALIDATED, PROVISIONAL, REFUSED}`. When fit quality fails, audience composition falls back to RFM quintile ranking — never to invented confidence.

Month-1 wow comes from "your customers, scored, with per-customer expected reorder dates, churn-risk bands, and predicted LTV — surfaced as a typed `predicted_segment` block on every PlayCard." Month-2 return comes from "re-fit on this month's CSV; here's what changed: cohorts entering, retention curve extending, predicted-LTV evolution." Neither claim requires an authorized-campaign outcome event. Phase 9 outcome calibration moves to post-beta (S15+), where it earns its keep against a real installed base.

### Total sprint count and duration

- **9 sprints (S6 through S14)** to private-beta launch.
- **~15 weeks** of wall-clock engineering (S7.5 closed 2026-05-17; S6 in flight).
- **5 sprints carry beta-blocking work**: S6, S7, S8, S10, S11, S12, S13, S14 — note that under the reframe S8's EB blend is beta-enhancing rather than beta-blocking (see §3 below). The true beta-blockers are **S7 (operational content), S10–S13 (ML predictive layer), and S14 (private beta launch)**.

### What is deferred vs preserved

**Deferred to post-beta (S15+):**
- Phase 9 outcome loop (importer + calibration writer + last-month-outcome briefing surface) — was S10. Repurposed.
- Causal uplift modeling — requires accumulated Phase 9 data.
- Portfolio optimization (S22+).
- LLM mechanism generation (S26+).
- Multi-channel / federated learning — far post-PMF.
- Trust-math tooling (replay, backtest, sensitivity audit CLIs) — was S9. Operator/founder-internal, not merchant-facing. Defer.

**Preserved as-planned:**
- S6 (Tier-B builders 1 + 2 + supplements parser) — in flight.
- S7 (3 remaining Tier-B builders + journey-proxy migration + 4-state abstain).
- S7.5 (priors validation) — **DONE 2026-05-17**.
- S8 (tier formalization + EB blend + Play Library wave 1) — kept, but EB blend's payoff is reduced without Phase 9 calibration. Documented honestly: the blend layer locks the *contract*; the blend's *epistemic value* is realized only after Phase 9 returns post-beta. S8 still ships because tier formalization and the Play Library refactor are independently beta-blocking.

### The three orthogonal gates (load-bearing — read carefully)

A play surfaces as a Recommended Now card only if **all three** gates pass:

1. **Cohort p-value gate (per-builder)** — Tier-B builder's intervention-shaped supporting metric passes its primary-window significance threshold (`PHASE5_DIRECTIONAL_P_MAX=0.05`) AND sign-agreement across ≥2 of {L28, L56, L90}. Gate produces `evidence_class ∈ {measured, directional, targeting}`. Failure ⇒ no PlayCard or Considered routing.

2. **Priors `validation_status` gate (per-prior, S7.5 contract)** — every prior that anchors a `revenue_range.source=blend` posterior must carry `validation_status ∈ {validated_external, validated_internal, elicited_expert}`. `heuristic_unvalidated` and `placeholder` priors → `revenue_range.suppressed=True` with `ReasonCode.PRIOR_UNVALIDATED`. Gate is dormant until a Tier-B builder consumes a `base_rate` prior (Sprint 6 activation moment).

3. **`ModelFitStatus` gate (per-merchant, per-model, NEW in S10–S13)** — every ML model carries a `ModelCard` typed slot with `fit_status ∈ {VALIDATED, PROVISIONAL, REFUSED}` driven by holdout MAPE / log-likelihood / sample-size thresholds. `REFUSED` ⇒ audience builder falls back to deterministic RFM quintile ranking; per-customer ML scores are NOT emitted on the PlayCard. `PROVISIONAL` ⇒ scores emit but `evidence_source` chip downgrades; downstream renderer must surface the caveat. `VALIDATED` ⇒ full ML augmentation. **The three gates are independent — a play can be cohort-significant + prior-validated + model-refused (and falls back to RFM), or cohort-significant + prior-unvalidated + model-validated (and gets suppressed dollars but rich audience characterization).**

The gate independence is the audit story: every suppression / fallback / abstain points to exactly one of these three gates, and the engine emits the typed reason.

### Beta success criteria

**Month 1 (first briefing):** merchant sees their own customer base scored — predicted LTV per customer, per-cohort retention curves with CIs, RFM bands with confidence cutoffs, predicted next-purchase dates on replenishable SKUs, and at least one Tier-B Recommended Now card whose audience was filtered through the ML scoring. The "wow" is *"this engine knows my customers better than I do, before I sent it a single campaign outcome."*

**Month 2 (return briefing):** merchant sees the *delta*. New cohorts that entered. Retention curves that extended one month further out (with the prior month's curve shown as ghost-line in `engine_run.json` typed slot — renderer surface is downstream). Predicted-LTV evolution per customer. Audience that grew / shrank. The "return reason" is *"the engine re-fit on my fresh data; here's what changed."* No outcome-calibration claim is made; the math is honest about being predictive, not causal.

---

## Part B — Sprint-by-sprint plan

### Sprint 6 — First two Tier-B builders + supplements parser

- **Anchor goal:** Ship `winback_dormant_cohort` + `replenishment_due` as the first two Tier-B builders end-to-end; close KI-18 via supplements serving-count parser.
- **Why under reframe:** unchanged. Tier-B operational content is independently beta-critical regardless of the ML layer — the audience builders are the substrate the ML scores ride on top of.
- **Status:** CLOSED 2026-05-19 (PARTIAL: T3.5 Commit C deferred per Path D, KI-NEW-G resume trigger).
- **Estimated duration:** ~7 working days.
- **Beta-critical:** yes (operational-content baseline).
- **Key tickets:** S6-T1, S6-T1.5, S6-T2, S6-T3, S6-T3.5 (5 tickets × 3 commits = 15 commits). See `agent_outputs/implementation-manager-s6-tier-b-builders-plan.md` for the full ticket breakdown.
- **Schema additions:** 2 new `_SUPPORTED` entries, 2 new `WouldBeMeasuredBy` enum values, 1 new `play_id` (`replenishment_due`), 2 new feature flags (`ENGINE_V2_BUILDER_WINBACK_DORMANT`, `ENGINE_V2_BUILDER_REPLENISHMENT_DUE`).
- **Feature flags introduced:** both above; default OFF at T1/T3, flipped ON at T1.5/T3.5 atomically with fixture re-pin.
- **Fixture re-pin:** Beauty pinned slate + supplements G-1 at T1.5 AND T3.5.
- **Dependencies:** S7.5 closed.
- **Out of scope:** play registry restructure (S8), additional Tier-B builders (S7), Phase 9 outcome loop (now post-beta).
- **NEW under reframe — coordinate with ML layer:** Sprint 6's audience-builder signatures need to be *forward-compatible* with the optional `ranking_strategy` parameter that S13 will add. See §B-S13 below; the minimum intervention on the in-flight S6 work is to (a) add an optional `ranking_strategy: Optional[str] = None` kwarg to each new audience builder function with default behavior preserved when None, and (b) reserve an optional `predicted_segment: Optional[PredictedSegmentBlock] = None` field on the PlayCard dataclass. Both are no-op-when-None. They make S13 a single-commit integration rather than a multi-file refactor.
- **Closeout note:** See memory.md S6 closed-section + agent_outputs/code-refactor-engineer-s6-t3_5-summary.md. 3 architectural-limitations KIs (KI-NEW-G/H/I) filed for Phase 9 coupled recalibration.

### Sprint 7 — Remaining three Tier-B builders + 4-state abstain + journey-proxy migration

- **Anchor goal:** Ship `discount_dependency_hygiene`, `cohort_journey_first_to_second` (replacing the journey-proxy `first_to_second_purchase`), and `aov_lift_via_threshold_bundle` as the final three Tier-B builders. Migrate the legacy 2-state ABSTAIN_SOFT/PUBLISH to the typed 4-state abstain (`SOFT_AWAITING_MEASUREMENT`, `SOFT_PRIOR_UNVALIDATED`, `SOFT_BELOW_FLOOR`, `SOFT_AUDIENCE_TOO_SMALL`) per ARCHITECTURE_PLAN Part II §S7.
- **Why under reframe:** unchanged. Without S7, supplements still ships ABSTAIN-only; the operational-content beachhead requires the full 5-builder set.
- **Status:** planned.
- **Estimated duration:** ~2 weeks.
- **Beta-critical:** **yes** (the strongest single beta-blocker).
- **Key tickets (planned):** S7-T1 (`discount_dependency_hygiene` builder + flag flip), S7-T2 (`cohort_journey_first_to_second` builder + retire `first_to_second_purchase` proxy + flag flip), S7-T3 (`aov_lift_via_threshold_bundle` builder + flag flip), S7-T4 (4-state abstain migration; deprecate `ABSTAIN_SOFT` alias by S10).
- **Schema additions:** 3 new `_SUPPORTED` entries, 3 new `WouldBeMeasuredBy` enum values, 4-state abstain enum (`AbstainMode` already added at S7.5-T3; adds the two remaining values), 3 new `play_id`s.
- **Feature flags introduced:** `ENGINE_V2_BUILDER_DISCOUNT_HYGIENE`, `ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND`, `ENGINE_V2_BUILDER_AOV_BUNDLE`, `ENGINE_V2_ABSTAIN_4STATE`.
- **Fixture re-pin:** Beauty + supplements G-1 multiple times (atomic with each flag flip). KI-21 / KI-23 expected to close as supplements gains Recommended Experiment candidates.
- **Dependencies:** S6 closed.
- **Out of scope:** ML scoring (S10+), EB blend (S8), Play Library refactor (S8).

### Sprint 7.5 — Priors validation (DONE)

- **Anchor goal:** Install `validation_status` field + `bayesian_blend` helper + `SOFT_PRIOR_UNVALIDATED` abstain; flag default-ON.
- **Status:** ✅ DONE 2026-05-17 (T1, T1.5, T2, T3, T3.5).
- **Suite:** 1237p / 14s / 1f.
- **Beta-critical:** yes (the validation contract is the second of the three orthogonal gates).
- **What landed:** see `agent_outputs/implementation-manager-s7_5-priors-validation-plan.md` and memory.md S7.5-T3.5 closeout (2026-05-17). All 5 pinned fixtures byte-identical post-flip; `bayesian_blend` is contract surface ready for Sprint 6 Tier-B activation.

### Sprint 8 — Tier formalization + EB blend + Play Library wave 1

- **Anchor goal:** Lock the trust-surface PlayCard contract for beta (typed `evidence_source` chip, `sensitivity` block, `provenance` object). Ship the EB blend layer so Tier-B builders' observed effects can be blended with priors via a defensible pseudo_N. Migrate 3–4 plays into the new Play Library directory layout (`plays/<play_id>/`).
- **Why under reframe:** **modified posture.** Tier formalization is beta-blocking. The EB blend's payoff is *reduced* without Phase 9 calibration — the layer ships but its epistemic value is realized only post-beta when outcome data arrives. We ship it for contract-stability (consumers can pattern-match the typed slots from day 1) and as the *contract* the future Phase 9 calibration writer will overwrite. Document this honestly in the S8 close summary and in the merchant-facing renderer copy if any.
- **Status:** planned.
- **Estimated duration:** ~2 weeks.
- **Beta-critical:** partial — tier formalization yes; EB blend ships but is dormant value until Phase 9.
- **Key tickets:** S8-T1 (typed `EvidenceSourceChip` enum + PlayCard field), S8-T2 (`Sensitivity` typed dataclass + per-PlayCard population), S8-T3 (EB blend layer in `sizing.py`; consumed by S6/S7 Tier-B builders), S8-T4 (Play Library wave 1 — fold `winback_dormant_cohort`, `replenishment_due`, `discount_dependency_hygiene` into `plays/<play_id>/`).
- **Schema additions:** `PlayCard.evidence_source`, `PlayCard.sensitivity`, `PlayCard.provenance` (all additive in `event_version=1`).
- **Feature flags introduced:** `ENGINE_V2_TIER_CHIP`, `ENGINE_V2_EB_BLEND`, `ENGINE_V2_PLAY_LIBRARY_WAVE1`.
- **Fixture re-pin:** Beauty + supplements G-1 at each flag flip; M0 may move (first time since S5).
- **Dependencies:** S7 closed.
- **Out of scope:** Phase 9 outcome loop (post-beta), ML scoring (S10+).

### Sprint 10 — ML Predictive Layer Part 1 (BG/NBD + Gamma-Gamma)

- **Anchor goal:** Install the `lifetimes` package; fit BG/NBD model per merchant; emit per-customer `P(alive)` + `expected_purchases_in_N_days`; extend to Gamma-Gamma for `predicted_monetary_value`; install the `ModelFitStatus` enum + `ModelCard` typed schema as the third orthogonal gate.
- **Why under reframe:** **NEW beta-critical sprint.** This is the engine's first per-customer predictive surface. Month-1 wow lives here.
- **Status:** planned.
- **Estimated duration:** ~2 weeks.
- **Beta-critical:** **yes** (highest-leverage of the four new ML sprints).
- **Schema additions:** `ModelFitStatus` closed enum (`VALIDATED`, `PROVISIONAL`, `REFUSED`); `ModelCard` typed dataclass (model_name, fit_status, holdout_mape, n_observed, training_window, fit_warnings[], fit_timestamp); `engine_run.json` gains a `predictive_models: Dict[model_name, ModelCard]` typed slot. Per-customer score storage lives in `data/<store_id>/predictive/<model_name>.parquet` (NOT in `engine_run.json` — privacy / size posture per founder Q5 default).
- **Feature flags introduced:** `ENGINE_V2_ML_BGNBD` (default OFF at T1; flip ON at T1.5), `ENGINE_V2_ML_GAMMA_GAMMA` (default OFF at T2; flip ON at T2.5).
- **Fixture re-pin:** Beauty + supplements G-1 at T1.5 AND T2.5. M0 byte-identical (M0 fixtures are too small for BG/NBD cold-start thresholds — model will return `REFUSED` and audience falls back to RFM; that is the test).
- **Dependencies:** S8 closed.

#### S10 ticket breakdown

**S10-T1 — `lifetimes` integration + BG/NBD fit + ModelFitStatus + ModelCard**
- Scope: add `lifetimes` to `requirements.txt` (D-6 ML-ban carve-out: classical Fader/Hardie models with peer-reviewed lineage are explicitly permitted under the reframe; ban remains in place for uplift / neural / RL). New `src/predictive/bgnbd.py` with `fit_bgnbd_model(orders_df, *, store_id, training_window_days) -> Optional[BGNBDFit]`. Cold-start guards (≥6 months data + ≥500 repeat customers + ≥1500 orders enforced as a *hard* refusal — model returns None with `ModelCard.fit_status=REFUSED` and `fit_warnings=["below_cold_start_threshold"]`). New `src/predictive/model_card.py` with the `ModelFitStatus` enum + `ModelCard` dataclass + holdout MAPE validation (random 80/20 split on customer-period grid). Wire ModelCard into `engine_run.json` under typed `predictive_models` slot.
- Tests: `tests/test_s10_t1_bgnbd_fit.py` (~18 tests): cold-start refusal on M0 micro_coldstart fixture (audience too small), VALIDATED status on Beauty fixture with synthetic >500-repeat customers, PROVISIONAL on a synthetic mid-size cohort, deterministic fit under fixed seed (G-7 contract), holdout MAPE < 25% → VALIDATED, 25–40% → PROVISIONAL, >40% → REFUSED, fit_warnings populated correctly, no per-customer scores leak into engine_run.json, parquet artifact write path correct, `ModelCard` round-trips through engine_run.json schema.
- Acceptance: full suite green; M0 byte-identical; Beauty fixture gains `predictive_models.bgnbd` typed slot with `fit_status=VALIDATED` and per-customer parquet artifact persisted under `data/<store_id>/predictive/`.
- Flag: `ENGINE_V2_ML_BGNBD` default OFF.
- Commit pattern: impl + memory + summary (3 commits).

**S10-T1.5 — Flip `ENGINE_V2_ML_BGNBD` ON + atomic fixture re-pin + first per-customer scores persisted**
- Scope: flag flip OFF → ON. Beauty + supplements G-1 fixtures re-pinned (`engine_run.json` gains the new typed slot; HTML briefing byte-identical because renderer doesn't surface predictive_models yet). M0 byte-identical (cold-start REFUSED). Per-customer P(alive) and expected_purchases_in_30d persisted to `data/<store_id>/predictive/bgnbd.parquet`.
- Tests: `tests/test_s10_t1_5_bgnbd_repin.py` (~8 tests): per-fixture before/after `predictive_models` typed slot pinned; parquet artifact existence pinned; per-customer score envelope sanity (P(alive) ∈ [0,1], expected_purchases ≥ 0); operator override `ENGINE_V2_ML_BGNBD=false` reproduces pre-T1.5 fixture sha (rollback safety).
- Acceptance: Beauty fixture `predictive_models.bgnbd.fit_status=VALIDATED`; supplements `fit_status` depends on supplements fixture size — likely PROVISIONAL (founder Q1 below).

**S10-T2 — Gamma-Gamma extension for `predicted_monetary_value` per customer**
- Scope: extend `src/predictive/bgnbd.py` with `fit_gamma_gamma_model()` consuming the validated BG/NBD fit. Per-customer `predicted_monetary_value_in_N_days` written to the same parquet artifact (new column). ModelCard for Gamma-Gamma added to `engine_run.json` under `predictive_models.gamma_gamma`. Independent fit refusal (independence assumption between purchase frequency and monetary value is checked; Pearson r > 0.3 → fit_warnings includes "frequency_monetary_correlation" and downgrades to PROVISIONAL).
- Tests: `tests/test_s10_t2_gamma_gamma.py` (~12 tests): independence assumption check, fit numerics deterministic under seed, per-customer monetary value within sane envelope (within ±3 σ of historical AOV distribution), refusal on degenerate AOV data, ModelCard plumbing.
- Acceptance: parquet artifact gains `predicted_monetary_value_30d` and `predicted_monetary_value_180d` columns; `predictive_models.gamma_gamma.fit_status` populated.
- Flag: `ENGINE_V2_ML_GAMMA_GAMMA` default OFF.

**S10-T2.5 — Test fixtures + cold-start guards + holdout MAPE validation + flag flip ON**
- Scope: bundle the flag flip with synthetic predictive fixtures that exercise (a) VALIDATED on healthy Beauty, (b) PROVISIONAL on supplements (founder Q2 default), (c) REFUSED on M0 micro_coldstart. Atomic re-pin with flag flip per S3 Risk #4 discipline. Holdout MAPE thresholds (Q2) pinned in test.
- Tests: ~10 new tests on the three-state fixture matrix.

### Sprint 11 — ML Predictive Layer Part 2 (survival + collaborative filtering)

- **Anchor goal:** Add `lifelines` for survival analysis (Kaplan-Meier per SKU class + Cox PH per customer) + `implicit` for collaborative filtering (ALS or scikit-learn TruncatedSVD fallback). Per-customer `expected_next_purchase_date` per SKU class + top-N affinity predictions. Both wired into `engine_run.json` as typed slots.
- **Why under reframe:** survival analysis powers `replenishment_due` audience refinement (the dominant beauty/supplements use case); collaborative filtering powers `cross_sell_affinity` and `bundle_threshold` audience builders.
- **Status:** planned.
- **Estimated duration:** ~2 weeks.
- **Beta-critical:** yes.
- **Schema additions:** `predictive_models.survival`, `predictive_models.collaborative_filtering` (both `ModelCard`-shaped); per-customer parquet artifacts gain columns.
- **Feature flags:** `ENGINE_V2_ML_SURVIVAL`, `ENGINE_V2_ML_CF`.
- **Fixture re-pin:** Beauty + supplements G-1 at each ML flag flip.
- **Dependencies:** S10 closed.

#### S11 ticket breakdown

**S11-T1 — `lifelines` integration + Kaplan-Meier per SKU class + per-customer expected_next_purchase_date**
- Scope: add `lifelines` to `requirements.txt`. New `src/predictive/survival.py`. Per-SKU-class KM curve fit (SKU class = output of replenishment parser's unit-coherence layer from S6-T2). Per-customer `expected_next_purchase_date_by_sku_class` computed as the KM median residual life from the customer's last observed purchase. Optional Cox PH on `[recency, frequency, monetary]` covariates if sample size permits — gated by ModelFitStatus.
- Cold-start: per-SKU-class minimum N=50 customers with ≥2 purchases. SKU classes below threshold → KM-curve fit_status=REFUSED, individual customers in those classes get `expected_next_purchase_date_by_sku_class[class]=None`.
- Tests: ~14 tests covering per-SKU-class fit, censored-data handling (customers whose last purchase is too recent to have churned), Cox PH covariate plumbing, ModelCard population.
- Flag: `ENGINE_V2_ML_SURVIVAL` default OFF.
- Acceptance: Beauty fixture's `replenishment_due` audience can optionally be ranked by survival-model predicted next-purchase date (consumed in S13).

**S11-T1.5 — Atomic flag flip + per-customer survival scores persisted + fixture re-pin**

**S11-T2 — Collaborative filtering via `implicit` ALS + per-customer top-N affinity**
- Scope: add `implicit` to `requirements.txt` with `scikit-learn` `TruncatedSVD` as a fallback when `implicit` fails to install on macOS ARM (founder Q5 below — privacy posture should also surface a build-environment fallback decision). New `src/predictive/cf.py`. Customer × SKU implicit-feedback matrix; ALS factorization with `factors=32` default; per-customer top-N (N=10) SKU affinity scores with support counts.
- Cold-start: ≥500 customers with ≥2 distinct SKU purchases; ≥30 SKUs with ≥10 purchasers each. Below threshold → fit_status=REFUSED, audience builders fall back to most-popular-SKU ranking.
- Tests: ~14 tests covering matrix construction, ALS deterministic under fixed seed (verify across 2 runs — G-7 contract), top-N affinity envelope sanity (scores ∈ [0,1] after normalization), support_count correctly attached, ModelCard.
- Flag: `ENGINE_V2_ML_CF` default OFF.

**S11-T2.5 — Atomic flag flip + per-customer CF scores persisted + fixture re-pin**

**S11-T3 — Both survival + CF wired into engine_run.json as typed slots + integration tests**
- Scope: ensure both models' ModelCards appear in `engine_run.json.predictive_models`. Cross-model invariant tests (no customer appears with inconsistent SKU class between survival and CF outputs).
- Tests: ~6 integration tests.

### Sprint 12 — ML Predictive Layer Part 3 (RFM + retention curves)

- **Anchor goal:** Statistical RFM segmentation with confidence bands (pure pandas) + cohort retention curves with bootstrapped CIs (pure pandas + scipy). Both wired into `engine_run.json` typed slots.
- **Why under reframe:** RFM is the deterministic fallback when ML fits refuse; retention curves are the load-bearing "month-2 delta" surface that the founder cited as the return-reason mechanism.
- **Status:** planned.
- **Estimated duration:** ~1.5 weeks.
- **Beta-critical:** **yes** — the retention curve is the most direct beta-return mechanism.
- **Schema additions:** `predictive_models.rfm` + `predictive_models.cohort_retention` (both `ModelCard`-shaped); `engine_run.json` gains `cohort_retention.curves: List[CohortRetentionCurve]` with bootstrapped 5/50/95 percentiles per period-since-acquisition; `audience_segments: List[RFMSegment]` typed list with VIP / Champions / At-Risk / Hibernating / etc. bands.
- **Feature flags:** `ENGINE_V2_ML_RFM`, `ENGINE_V2_ML_RETENTION`.
- **Dependencies:** S11 closed.

#### S12 ticket breakdown

**S12-T1 — Statistical RFM segmentation with confidence bands**
- Scope: new `src/predictive/rfm.py`. R, F, M quintile assignment via `pandas.qcut` with tie-breaking; standard 11-segment naming (Champions, Loyal Customers, Potential Loyalists, New Customers, Promising, Need Attention, About to Sleep, At Risk, Cannot Lose Them, Hibernating, Lost). Per-segment confidence cutoffs via bootstrap on quintile boundaries (1000 resamples; 5/95 percentile bands on the quintile cutoffs). ModelFitStatus: VALIDATED if ≥200 customers across ≥30 days; PROVISIONAL 50–200 / 14–30 days; REFUSED below.
- Tests: ~12 tests covering quintile assignment determinism (G-7), edge cases (all customers in one segment), bootstrap CI envelope sanity, ModelCard plumbing.
- Flag: `ENGINE_V2_ML_RFM` default OFF. Flip in T1.5.

**S12-T2 — Cohort retention curves with bootstrapped CIs per acquisition cohort**
- Scope: new `src/predictive/retention.py`. Monthly acquisition cohorts (per customer's first order month). Retention curve = fraction of cohort with ≥1 order in each subsequent calendar month. Bootstrapped 5/50/95 percentile bands per (cohort, period-since-acquisition) cell via 1000-resample customer-level bootstrap. Returns `List[CohortRetentionCurve]` typed dataclass; each curve has `cohort_label`, `n_customers`, `periods: List[(period, retained_count, retained_p5, retained_p50, retained_p95)]`. Persist parquet artifact `data/<store_id>/predictive/cohort_retention.parquet`.
- Cold-start: ≥3 cohorts of ≥30 customers each AND ≥3 months observation per cohort.
- Tests: ~14 tests covering deterministic bootstrap under seed (G-7), edge cases (single cohort, single period), bootstrap CI envelope sanity, ModelCard, persistence layer round-trip.
- Flag: `ENGINE_V2_ML_RETENTION` default OFF. Flip in T2.5.

**S12-T3 — Both RFM + retention wired into engine_run.json + atomic fixture re-pin**
- Atomic flag flips for both T1 and T2 in this commit (the cleanest single re-pin). Per-fixture before/after `engine_run.json` shape pinned.

### Sprint 13 — Integration sprint (ML feeds AUDIENCE; PlayCard contract extended; month-2 delta surface)

- **Anchor goal:** Wire the ML layer's outputs into the Tier-B audience builders' optional `ranking_strategy` parameter. Extend `PlayCard` contract with `predicted_segment` block + `model_card_ref`. Add the "month-2 delta" section to `engine_run.json`. Atomic fixture re-pin + default-ON flag flip on `ENGINE_V2_ML_AUDIENCE`.
- **Why under reframe:** this sprint is what *makes* months 1 and 2 visibly different. The Tier-B builders gain per-customer ranking; the briefing's typed slots show the cross-month evolution.
- **Status:** planned.
- **Estimated duration:** ~2 weeks.
- **Beta-critical:** **yes** — last beta-critical sprint before launch.
- **Schema additions:** `PlayCard.predicted_segment: Optional[PredictedSegmentBlock] = None`, `PlayCard.model_card_ref: Optional[str] = None` (points to the upstream ModelCard for audit), `engine_run.month_2_delta: Optional[MonthTwoDelta] = None` typed slot.
- **Feature flags:** `ENGINE_V2_ML_AUDIENCE` (the unified flag for ML scores feeding audience builders). Default OFF at T1–T3, flipped ON at T4 atomically.
- **Dependencies:** S12 closed.

#### S13 ticket breakdown

**S13-T1 — Tier-B audience builders gain optional `ranking_strategy` parameter consuming ML scores**
- Scope: extend each of the 5 Tier-B builder audience functions with `ranking_strategy: Optional[Literal["rfm_quintile", "ml_predicted_ltv", "ml_survival", "ml_cf_affinity", "default"]] = None`. Default behavior (None) is preserved byte-for-byte (this is why the S6 minimum intervention pre-reserves the kwarg). When set, the audience builder reads per-customer scores from `data/<store_id>/predictive/<model_name>.parquet` and ranks the audience accordingly. Fallback: if the requested model's ModelCard is REFUSED, builder logs a fallback event and uses `rfm_quintile` (which itself falls back to insertion-order if RFM is REFUSED).
- Tests: ~16 tests covering each Tier-B builder × each ranking strategy × VALIDATED / PROVISIONAL / REFUSED ModelFitStatus combinations.
- Flag: `ENGINE_V2_ML_AUDIENCE` default OFF.

**S13-T2 — New "month-2 delta" section in `engine_run.json`**
- Scope: new `src/month_2_delta.py`. On every run, if a prior month's `engine_run.json` exists at `data/<store_id>/runs/<prior_month>/engine_run.json`, compute: (a) predicted-LTV evolution per customer (delta from prior fit), (b) cohort retention extension (new period of observation added), (c) new cohorts entering, (d) audiences that grew / shrank between runs (set diff on customer IDs per Tier-B audience). Emit as `engine_run.month_2_delta: MonthTwoDelta` typed slot. Skip silently with `month_2_delta=None` on month-1 runs (no prior run exists).
- Tests: ~12 tests covering month-1 (None), month-2 (full populated), customer-ID set ops determinism, parquet artifact reuse, model-refit-divergence handling (if prior month's BG/NBD was REFUSED and this month's is VALIDATED, delta says so).
- Flag: gated by `ENGINE_V2_ML_AUDIENCE` (same unified flag).

**S13-T3 — PlayCard contract additions (`predicted_segment` block, `model_card_ref`) wired through all 5 Tier-B builders**
- Scope: every Tier-B PlayCard, when the audience was filtered through an ML ranking strategy, gains a `predicted_segment` block summarizing the per-audience aggregate (e.g., for `winback_dormant_cohort` filtered by `ml_predicted_ltv`: predicted_segment={archetype: "high_value_dormant", p50_predicted_ltv: $X, n: Y}). `model_card_ref` points to the upstream ModelCard for audit. Privacy: per-customer scores stay in parquet, only audience-aggregate summaries reach `engine_run.json` (founder Q5 default).
- Tests: ~10 tests covering plumbing across each Tier-B builder.

**S13-T4 — Atomic fixture re-pin + flag flip on `ENGINE_V2_ML_AUDIENCE` default ON**
- Scope: single atomic commit. Beauty + supplements G-1 + M0 (if M0 fixtures size cleared cold-start; otherwise byte-identical). Per-fixture before/after card-count and `predicted_segment` block diff documented in summary.
- Hard-stop: if Beauty fixture's predicted-LTV envelope on the winback audience is outside ±3σ of the prior fit's distribution, STOP and ping orchestrator (same discipline as Sprint 6).

### Sprint 14 — Private beta launch

- **Anchor goal:** Onboard first 1–2 hand-picked merchants. Surface and fix integration issues. Pin private-beta merchant fixtures.
- **Why under reframe:** every prior sprint shipped against synthetic fixtures. The first real merchant CSVs will surface KI-30-class UX issues, schema friction, real-world-distribution edge cases on ML fits (especially around the cold-start thresholds; founder Q1 default values are speculation until validated on real data).
- **Status:** planned.
- **Estimated duration:** ~1.5 weeks.
- **Beta-critical:** **yes** — gating sprint.
- **Key tickets:** S14-T1 (first merchant CSV ingest + pinned fixture + per-customer ML fit walk-through), S14-T2 (second merchant), S14-T3 (any blocker fixes surfaced), S14-T4 (beta-launch checklist Part F).
- **Schema additions:** none expected (S13 is the contract freeze). Any required additions raise the event_version question and likely push beta.
- **Feature flags:** all S6–S13 flags become defaults-ON; remain env-overridable as operator escape hatches.
- **Dependencies:** S13 closed.
- **Out of scope:** any architectural changes; if a real merchant surfaces a need not satisfied by the current contract, it becomes a post-beta backlog item, not a S14 ticket.

---

## Part C — Open questions for the founder

### Q1 — BG/NBD cold-start thresholds

**Question:** ≥6 months data + ≥500 repeat customers + ≥1500 orders as the VALIDATED threshold; below → REFUSED with RFM fallback. Confirm or override?

**Default:** ship as proposed. The numbers are conservative against the `lifetimes` package's published guidance (which suggests ≥1000 customers and ≥3 months for a stable BG/NBD fit). Founder may want to soften to PROVISIONAL (3 months / 200 customers / 500 orders) and reserve REFUSED for true degenerate cases — that would expose more merchants to the predictive layer at the cost of wider uncertainty bands. Recommendation: stick with proposed; let S14 beta data inform a future relaxation.

### Q2 — ModelFitStatus holdout MAPE thresholds

**Question:** Holdout MAPE < 25% → VALIDATED; 25–40% → PROVISIONAL; > 40% → REFUSED. Confirm?

**Default:** ship as proposed. Industry rule-of-thumb for BG/NBD on healthy DTC data is ~15–20% MAPE; 25% is a forgiving line. Founder may want to make the bands vertical-specific (supplements has more bimodal repurchase distributions than beauty), but cross-merchant pooling is *not* on the table per Q3 below.

### Q3 — Cross-merchant pooling

**Question:** Per-merchant models only — no pooling across verticals. Confirm?

**Default:** confirm. Pooling would leak data across merchants (privacy posture violation per D-5 substrate discipline) AND across verticals (supplements ≠ beauty). The per-merchant per-vertical posture is also what makes `month_2_delta` honest — the merchant's own data is the only data the engine consumed. **Strongly recommend founder confirm.**

### Q4 — Retraining cadence

**Question:** Monthly per merchant (same cadence as the briefing run). Confirm?

**Default:** ship as proposed. Monthly is consistent with the briefing run and avoids stale-model risk. Higher cadence (weekly) adds compute cost without material accuracy gain on monthly-decision plays. Lower cadence (quarterly) risks stale `month_2_delta` (which becomes "month_4_delta"). **Strongly recommend monthly.**

### Q5 — Privacy posture: per-customer scores stay in memory.db / parquet, NEVER in `engine_run.json` typed slots

**Question:** Per-customer ML scores persist to `data/<store_id>/predictive/<model_name>.parquet` (parquet, not SQLite — predictive payloads are columnar). Only audience-aggregate `predicted_segment` blocks (n, p50, p90 across the audience) reach `engine_run.json`. Briefing HTML renders nothing per-customer. Confirm?

**Default:** confirm. This preserves D-2 privacy posture (no PII or per-customer detail in shareable artifacts) AND keeps `engine_run.json` size bounded (otherwise a 50k-customer store would emit a 50MB JSON, breaking Swarm consumers). Per-customer scores are available to operator tools and future Klaviyo Deploy Agent via the parquet artifact (D-5 manual-import only). **Strongly recommend founder confirm**; this is the load-bearing privacy contract for the ML layer.

---

## Part D — Risk register

### R1 — ML overfitting on small merchant samples (cold-start brittleness)

**What could go wrong:** A merchant with 200 repeat customers may have a BG/NBD fit that looks numerically clean but generalizes poorly to month 2 — the model memorizes idiosyncratic recency patterns. Resulting per-customer P(alive) scores feed audience builders → audience composition shifts unjustifiably month-over-month → merchant's `month_2_delta` shows churn signals that are model-noise, not customer-behavior.
**Mitigation:** the cold-start thresholds (Q1) are deliberately conservative. Holdout MAPE validation (Q2) catches degenerate fits at fit-time. `ModelFitStatus=REFUSED` cleanly falls back to RFM ranking which has no fit-step. The three-orthogonal-gate discipline ensures a REFUSED model never silently slips into PlayCards.
**Observability hook:** `ModelCard.fit_warnings[]` populated on every borderline fit. S14 beta data lets us tighten/loosen Q1/Q2 thresholds against real distributions.

### R2 — Audit complexity: how does the ModelCard typed slot keep ML interpretable?

**What could go wrong:** A skeptical merchant DS asks "why is this customer in the winback audience and not the at-risk audience?" The engine emits `PlayCard.model_card_ref=bgnbd` + `predicted_segment.archetype=high_value_dormant`, but the customer's underlying score is in a parquet artifact that's not in the briefing.
**Mitigation:** `ModelCard` carries `training_window`, `n_observed`, `fit_status`, `holdout_mape`, `fit_warnings[]`, `fit_timestamp`, and the closed-form parameters where applicable (BG/NBD's `r`, `α`, `s`, `β`). For per-customer drill, the parquet artifact is documented and queryable via a future operator CLI (S15+ post-beta tool). For the merchant DS audit story, the ModelCard is the contract surface; per-customer detail is one hop away.
**Observability hook:** `ModelCard` always present in `engine_run.json` when any ML score reaches a PlayCard.

### R3 — The "no Phase 9" trade-off: month-2 retention without outcome calibration

**What could go wrong:** Founder wagers that "engine refits on fresh CSV" is sufficient month-2 return reason. If merchants find this insufficient ("I want to know whether last month's recommendation actually worked"), beta retention drops. Phase 9 outcome loop becomes urgent post-beta.
**Mitigation:** S15+ post-beta workstream is sized and ready (the prior plan's S10 Phase 9-minimal becomes S15 Phase 9-minimal). Critically, the `recommendation_emitted` substrate (S1-S5) is already in place and humming; outcome import becomes a focused 1-2 week sprint once authorized. The reframe explicitly accepts this risk: month-2 wow comes from data-refit visibility, not outcome calibration. **This is the load-bearing reframe bet.**
**Observability hook:** S14 beta merchant feedback on month-2 retention conversation. If founder hears "but did the recommendation work?" within 6 weeks, that's the post-beta-Phase-9 trigger.

### R4 — Interaction between p-value gates (cohort-level) and ModelFitStatus (per-customer)

**What could go wrong:** A play passes cohort p-value gate (audience-level evidence) but the per-customer ML score the audience builder relies on is REFUSED. Under current design, the audience builder falls back to RFM ranking — the *audience* still surfaces, but the *predicted_segment* block on the PlayCard is downgraded. A naive consumer might assume the cohort gate's strength transfers to the per-customer claim. It does not.
**Mitigation:** the `model_card_ref` slot on every PlayCard makes the gate status auditable. Documentation (S8 tier formalization sprint) must explicitly enumerate the 3-gate matrix and call out the case where cohort-validated + model-refused → audience surfaces but per-customer claim is suppressed.
**Observability hook:** test invariant: any PlayCard with `predicted_segment != None` must have `model_card_ref != None` AND the referenced ModelCard must have `fit_status != REFUSED`.

### R5 — The 3-orthogonal-gate discipline: when does a play get suppressed and which gate did it?

**What could go wrong:** As the engine matures, suppression / fallback / abstain reasons proliferate. A given Tier-C play might pass cohort-significance, fail prior-validation, and have a REFUSED ML model — three independent failures. The engine must emit a single typed `ReasonCode` per Considered card; ambiguity breaks the audit story.
**Mitigation:** strict gate precedence on Considered routing: (1) audience-floor failures first, (2) cohort p-value failures, (3) prior-validation failures, (4) ML-fit failures. Each tier of failure gets its own ReasonCode enum value. Test pins the precedence.
**Observability hook:** `tests/test_reason_code_precedence_invariant.py` asserts that every Considered card emits exactly one ReasonCode AND that the ReasonCode matches the highest-precedence failed gate.

### R6 — Beta sample size — when do we have enough merchants to validate ML quality?

**What could go wrong:** N=1 or 2 private-beta merchants (S14) is too small to validate that cold-start thresholds (Q1) and MAPE bands (Q2) generalize. Engine ships to public beta with thresholds tuned on synthetic + 1 real merchant.
**Mitigation:** S14 explicitly produces a "calibration report" artifact: per-merchant ModelFitStatus + holdout MAPE + cold-start status across all 5 ML models. After 5–10 real merchants pass through, founder reviews the distribution and may revise Q1/Q2. This is the post-S14 / pre-public-beta calibration moment.
**Observability hook:** the calibration report is itself a typed artifact (`agent_outputs/private_beta_ml_calibration_report.md`), produced at S14-T4.

### R7 — Without Phase 9, how does the engine measure its own correctness post-launch?

**What could go wrong:** Engine is "predictive" not "causal." A bad BG/NBD fit could persist for months unnoticed because no outcome event ever contradicts it. Predicted-LTV evolves; was the prediction right?
**Mitigation:** holdout MAPE is a *retrospective* correctness check — every fit is split-validated at fit time. Month-2-delta's predicted-LTV evolution is itself a quasi-validation: large unexplained MoM swings in per-customer predicted-LTV indicate fit instability and trigger a `ModelCard.fit_warnings=["mom_instability"]` flag. The engine measures its own fit-stability; it cannot measure causal correctness without Phase 9. This is the honest answer.
**Observability hook:** `ModelCard.prior_month_consistency` field (added in S13-T2 as part of month_2_delta).

### R8 — `lifetimes` / `lifelines` / `implicit` packaging risk on operator's local Python

**What could go wrong:** macOS ARM / Python 3.10–3.12 build issues on one of the three new packages. `implicit` historically requires a C compiler. `lifetimes` and `lifelines` are pure Python but pin `numpy` / `scipy` versions that may conflict.
**Mitigation:** lock package versions in `requirements.txt`; ship `scikit-learn` `TruncatedSVD` as documented CF fallback in S11-T2; smoke-test packaging in CI before S10-T1 commit. If `implicit` fails on operator's machine, the fallback path is wired from day 1.
**Observability hook:** CI smoke-test on import + minimal-fit per ML package, added in S10-T1.

---

## Part E — KI roadmap

Walking KI-1 through KI-30. Statuses under the reframe:

| KI | Title (short) | Reframed status | Notes |
|---|---|---|---|
| KI-1 | `outcome_observed` no positive-projection test | ⏸ **Deferred to S15+ post-beta** | Was S10 closer. Phase 9 entry condition; not month-1/2-critical. |
| KI-2 | `load_realization_factors` swallows malformed sections | ⏸ **Deferred to S15+** | Same as KI-1 — Phase 9 entry. |
| KI-3 | `store_id` kwarg not plumbed | ✅ Closed S5-T1 | Done. |
| KI-4 | Calibration last-write-wins | ⏸ **Deferred to S15+** | Phase 9 entry. |
| KI-5 | `v_lineage_recent_emissions` wall-clock semantics | ⏸ **Deferred to S15+** | Phase 9 entry. |
| KI-6 | `campaign_id` per-store, not global | 🚫 Won't fix | Post-PMF / cross-store analytics. |
| KI-7 | `provider` field free-text | 🚫 Post-beta | event_version=2 — push beta. |
| KI-8 | Inbox files persist after import | 🚫 Won't fix | Operator discipline. |
| KI-9 | `sent_at` shape-only validation | ⏸ **Deferred to S15+** | Closes with KI-1 in Phase 9 importer. |
| KI-10 | Disk growth monotonic | 🚫 Won't fix | AWS migration. |
| KI-11 | Snapshot mirror not atomic | 🚫 Accepted | No live read-during-write consumer. |
| KI-12 | Fallback `snapshot_sha256=None` | 🚫 Accepted | Auditor contract. |
| KI-13 | Substrate migration one-way | 🚫 Accepted | D-2. |
| KI-14 | `UPDATE RETURNING` SQLite ≥ 3.35 | 🚫 Accepted | Runtime 3.53. |
| KI-15 | Single-writer grep evades via rST | 🚫 Accepted | Documented. |
| KI-16 | Reader-allowlist grep hack | 🚫 Post-beta | Cosmetic. |
| KI-17 | Supplements V2 speculation | ✅ Resolved | G-1. |
| KI-18 | `empty_bottle.vertical_applicable` excludes supplements | ✅ **Closing S6-T2** | In flight. |
| KI-19 | `mixed` vertical semantics | ✅ Closed S7.5-T3 | Conservative-min pinned. |
| KI-20 | Supplements zero Recommended Now | ⏸ Partial close S6-T1.5 / fully closed S7 | Tier-B activation moment. |
| KI-21 | Supplements zero Recommended Experiment | ⏸ Closes S7 | Allowlist redesign in S7. |
| KI-22 | Repeat rate 0% advisory | ✅ Closed S5-T3 | Done. |
| KI-23 | Supplements plays drop out | ⏸ Closes S7 | Broader builder set. |
| KI-24 | Supplements `subscription_nudge` generic reason | ⏸ Deferred — Phase 4.2 redesign | Not beta-critical. |
| KI-25 | Supplements `routine_builder` audience too small | ⏸ Conditional close S6 / S7 | Per-vertical floor metadata. |
| KI-26 | Observations carry `prior: null` | ✅ Closed S5-T1 | Done. |
| KI-27 | `empty_bottle` clean-skipped on supplements | ⏸ Conditional close S6-T2 | Founder Q4. |
| KI-28 | `mixed` vertical never end-to-end | ⏸ Deferred to S14 beta | Real merchant CSVs likely include mixed cases. |
| KI-29 | Loop B+ subsegment attribution | 🚫 **Deferred to S18+** | Requires Phase 9 + accumulated outcome data. |
| KI-30 | Per-play evidence visualization spec | 🚫 UX/design layer | Engine-only scope per Part III-3. |

**KIs newly closed by reframe-era sprints (S10–S13):** none directly, but the ML predictive layer surfaces new typed slots that obviate the *need* for several "I wish the engine knew more about my customers" complaints that would otherwise have generated post-beta KIs.

**New KIs likely to land:**
- **KI-31 (proposed):** Per-customer ML scores live in parquet, not memory.db. Cross-substrate query is operator-tool territory (S15+).
- **KI-32 (proposed):** ModelFitStatus thresholds (Q1/Q2) are speculation until S14 beta data. Calibration report at S14-T4.
- **KI-33 (proposed):** `month_2_delta` skips silently on month-1 runs; merchant UX may need a "first run, no comparison yet" affordance. Renderer surface — out of engine scope.

---

## Part F — Beta-launch checklist (revised)

What must be true on the day the first real merchant opens their private-beta briefing (S14-T1):

### Engine correctness
- [ ] All 5 Tier-B builders (winback_dormant_cohort, replenishment_due, discount_dependency_hygiene, cohort_journey_first_to_second, aov_lift_via_threshold_bundle) ship behind default-ON flags.
- [ ] Priors validation contract default-ON. Every `validated_external` / `validated_internal` prior carries a `source_artifact:` pointer to a memo under `config/priors_sources/`.
- [ ] All 5 ML models (BG/NBD, Gamma-Gamma, Survival, CF, RFM, Retention) ship behind default-ON flags. Each emits a `ModelCard` typed slot in `engine_run.json` with `fit_status` populated.
- [ ] Three-orthogonal-gate discipline pinned by `tests/test_reason_code_precedence_invariant.py`.
- [ ] Cold-start fallback path tested: a small merchant gets RFM-only audiences with `ModelFitStatus=REFUSED` for BG/NBD/Survival/CF; engine still produces a briefing.

### Schema discipline
- [ ] `event_version=1` frozen. Every S10–S13 schema addition is additive optional.
- [ ] Per-fixture sha256 pins updated for Beauty + supplements G-1 across every flag-flip ticket.
- [ ] M0 fixtures (small_sm, mid_shopify, micro_coldstart) ship with ModelFitStatus = REFUSED on every ML model (verifying the cold-start fallback path).

### Per-customer privacy
- [ ] No per-customer scores in `engine_run.json`. Parquet artifacts under `data/<store_id>/predictive/<model_name>.parquet` only.
- [ ] No PII (email / name / address) in any predictive parquet — customer_id only.
- [ ] Briefing HTML byte-identical to `engine_run.json`-derived rendering (no extra data leakage).

### Month-1 wow surface
- [ ] At least 1 Tier-B Recommended Now card on Beauty fixture whose audience is ML-ranked.
- [ ] `predicted_segment` block populated on at least 1 PlayCard.
- [ ] `audience_segments: List[RFMSegment]` populated on the typed slot (independent of any specific play).
- [ ] Cohort retention curves visible in `engine_run.month_2_delta` (or in a typed `cohort_retention.curves[]` field even on month-1 runs — founder confirm).

### Month-2 return surface
- [ ] `engine_run.month_2_delta` populated when prior-month run exists.
- [ ] `cohort_retention.curves[]` extends by one period vs prior month.
- [ ] At least one customer's `predicted_ltv` evolution visible in delta (aggregated; per-customer in parquet).
- [ ] At least one "new cohort entered" or "audience grew" event reflected in delta.

### Substrate
- [ ] `recommendation_emitted` events written on every Recommended Now / Recommended Experiment card (S1–S5 substrate, already humming).
- [ ] Per-merchant memory.db schema frozen.
- [ ] All S6–S13 flags become defaults-ON; operator override `<FLAG>=false` rollback contract preserved.

### Observability
- [ ] `ModelCard.fit_warnings[]` populated on every borderline fit; surfaced in `engine_run.json`.
- [ ] Calibration report artifact produced post-S14-T4 (per-merchant ML fit status distribution).

### Documentation
- [ ] `ENGINE_OVERVIEW.md` updated to reflect ML layer + the three orthogonal gates + reframed beta criteria.
- [ ] `KNOWN_ISSUES.md` reflects KI status post-S14.
- [ ] `memory.md` Sprint 14 closeout entry landed.

---

## Appendix A — File paths (absolute)

Files this plan expects to touch, create, or rename during S10–S14:

- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/__init__.py` — new package (S10-T1)
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/bgnbd.py` — new (S10-T1, S10-T2)
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/model_card.py` — new (S10-T1)
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/survival.py` — new (S11-T1)
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/cf.py` — new (S11-T2)
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/rfm.py` — new (S12-T1)
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/retention.py` — new (S12-T2)
- `/Users/atul.jena/Projects/Personal/beaconai/src/month_2_delta.py` — new (S13-T2)
- `/Users/atul.jena/Projects/Personal/beaconai/src/audience_builders.py` — extended with `ranking_strategy` kwarg (S13-T1; pre-reserved in S6 minimum-intervention)
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` — additive `ModelFitStatus`, `ModelCard`, `predictive_models`, `audience_segments`, `cohort_retention`, `month_2_delta`, `PlayCard.predicted_segment`, `PlayCard.model_card_ref`
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` — new flags (S10–S13)
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` — wire predictive fits into the run pipeline (post-CSV-load, pre-decide)
- `/Users/atul.jena/Projects/Personal/beaconai/requirements.txt` — add `lifetimes`, `lifelines`, `implicit` (with `scikit-learn` TruncatedSVD fallback)
- `/Users/atul.jena/Projects/Personal/beaconai/data/<store_id>/predictive/` — new parquet artifact directory (per-store)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_*.py` through `tests/test_s13_*.py` — new test files per ticket
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_reason_code_precedence_invariant.py` — new (R5 mitigation)
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/private_beta_ml_calibration_report.md` — produced S14-T4

---

## Ticket count + duration roll-up

| Sprint | Tickets | Commits (3/ticket) | Duration | Beta-critical |
|---|---|---|---|---|
| S6 (in flight) | 5 | 15 | ~7 days | yes |
| S7 | 4 | 12 | ~10 days | yes |
| S7.5 (done) | 5 | 15 | ~10 days | done |
| S8 | 4 | 12 | ~10 days | partial |
| S10 | 4 (T1, T1.5, T2, T2.5) | 12 | ~10 days | yes |
| S11 | 4 (T1, T1.5, T2, T2.5, T3) — 5 logical | 15 | ~10 days | yes |
| S12 | 3 (T1, T2, T3) — atomic flips bundled | 9 | ~7 days | yes |
| S13 | 4 (T1, T2, T3, T4) | 12 | ~10 days | yes |
| S14 | 4 (T1, T2, T3, T4) | 12 | ~7 days | yes |
| **Total** | **37 tickets** | **~114 commits** | **~75 working days / ~15 wall-clock weeks** | — |
