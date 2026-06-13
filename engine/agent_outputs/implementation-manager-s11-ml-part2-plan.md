# Sprint 11 — ML Predictive Layer Part 2 — Implementation Plan

**Author:** implementation-manager
**Date:** 2026-05-26
**Branch baseline:** `post-6b-restructured-roadmap` (post-S10 close 2026-05-26)
**Status:** v2 — DS-revised, dispatchable to code-refactor-engineer for S11-T1
**Supersedes:** None. Extends `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` Part B §"Sprint 11" with ticket-level detail.
**Parent active read path:** `PRODUCT.md`, `STATE.md`, `PIVOTS.md`, `ROADMAP.md`
**Pattern parent:** `agent_outputs/implementation-manager-s10-ml-part1-plan.md` (cadence mirror).
**Discipline:** Subagent Handoff Discipline (CLAUDE.md L27–46); Documentation Discipline (CLAUDE.md L68–80); per-ticket loop is refactor → DS review → orchestrator commits+pushes → next ticket (founder-locked 2026-05-25); each refactor dispatch MUST require `agent_outputs/code-refactor-engineer-<ticket>-summary.md`.

---

## REVISION HISTORY

```
REVISION HISTORY
- 2026-05-26 v1 — initial dispatch (S11 — survival + collaborative filtering, mirrors S10 atomic-flip cadence)
- 2026-05-26 v2 — lifelines → scikit-survival; c_index floor 0.65 → 0.62/0.63 stage-keyed; ADD Brier@90d ≤ 0.25 secondary survival gate; CF recall@10 floor 0.08-0.15 → 0.05/0.06/0.08/0.10 stage-keyed; PROVISIONAL recall floor 0.04 → 0.03; per ds-architect-s11-plan-review.md and founder ack 2026-05-26
```

**v2 scope of revision (DS verdict `agent_outputs/ds-architect-s11-plan-review.md`, founder ack 2026-05-26):**
- A. Library substitution `lifelines` → `scikit-survival` for the Cox PH surface (S10's `lifetimes` for BG/NBD + G-G stays — refactor deferred to S15+ post-beta).
- B. C-index VALIDATED floor revised to 0.62 (startup/growth) / 0.63 (mature/enterprise) (was 0.65 uniform).
- C. Brier-score@90d ≤ 0.25 added as a SECONDARY gating field on the survival ModelCard (NEW gating contract, not operator-visible-only).
- D. CF recall@10 VALIDATED floors revised to {startup 0.05, growth 0.06, mature 0.08, enterprise 0.10}; PROVISIONAL 0.03.
- E. Audit copy for the orthogonal-failure case "BG/NBD VALIDATED + survival REFUSED" added explicitly to T3.
- F-K. Q1-Q6 closed with DS verdicts (§G).
- L. Beauty `replenishment_due` dormancy audit copy locked verbatim for T3.
- M-N. `_coerce` bool set at T1/T2 and determinism comparator extensions pinned in dispatch briefs.
- O. KI-NEW-P scope extension (~30 numbers by S11 close).
- P. `Deviation check: none.` line on every S11 ticket commit body.
- Q. Ranking-strategy chain confirmation at S11 close.

---

## Part A — Scope clarification

### A.1 What S11 is

ROADMAP.md §2 verbatim (line 42, pre-v2):

> | **S11** | ML Predictive Layer Part 2 — survival (`lifelines`) + collaborative filtering (`implicit`) | yes — drives `replenishment_due` ranking |

ROADMAP.md §1 verbatim (line 13, pre-v2):

> **Sprint 11 — ML Predictive Layer Part 2 (queued).** Next: survival models (`lifelines` Cox PH for replenishment timing) + collaborative filtering (`implicit`). Not yet dispatched.

**v2 note (founder ack 2026-05-26):** the survival library is **`scikit-survival`** (NOT `lifelines`) per DS verdict `agent_outputs/ds-architect-s11-plan-review.md` §(b). `lifelines` is not yet a codebase dependency. `lifetimes==0.11.3` (S10) stays; that BG/NBD library is NOT refactored at S11 (beta-blocking risk for zero S11 benefit per DS §(b).4). ROADMAP §1 L13 and §2 L42 verbatim text updated at S11-T3 close from "`lifelines`" → "`scikit-survival`"; `docs/DECISIONS.md` D-FLOOR-replenishment_due footnote records the substitution rationale at the same close ticket.

Two parallel ML substrates land at S11 close, mirroring the S10 BG/NBD + Gamma-Gamma shape:

1. **Survival** — `lifelines` Cox PH for per-customer replenishment-timing hazard. Sits at the AUDIENCE layer's `ranking_strategy` chain documented at `docs/engine_flags.md` L128 verbatim:
   > `BG/NBD → CF → survival → RFM → recency`
2. **Collaborative filtering** — `implicit` ALS for per-customer look-alike similarity (audience expansion). Same chain.

Both ship flag-OFF land → atomic-flip cadence, mirroring S10's T1/T1.5 (BG/NBD) and T2/T2.5 (G-G) pattern. PlayCard stubs `predicted_segment` and `model_card_ref` stay `None` at S11 close — per ROADMAP §1 verbatim (L28):

> PlayCard stubs `predicted_segment` and `model_card_ref` stay None at S10 close — S13 wires them.

S11 inherits that posture. S13 wires the consumers.

### A.2 Parallel vs. interleaved cadence — DECISION: parallel ticket sequences (survival first, then CF)

**Decision:** ship survival as T1/T1.5, then CF as T2/T2.5. No interleaving. Justifications:

1. **Pipeline-position parallel with S10.** S10 shipped BG/NBD (T1/T1.5) then G-G (T2/T2.5). S10's G-G chained on BG/NBD. S11's survival and CF do NOT chain on each other (see §A.3), but the *cadence* — one substrate per atomic-flip pair — is the same proven loop.
2. **Smaller blast radius per ticket.** Each substrate brings its own library, parquet schema, threshold block, rollback test. Interleaving doubles the cognitive load and the rollback-contract complexity on the orchestrator.
3. **DS review queue.** Per founder protocol (locked 2026-05-25), each ticket loops through DS before the next ticket dispatches. Interleaving would force DS to keep two substrates' contracts in head simultaneously.
4. **Survival first because it consumes BG/NBD's parameters** for the BG/NBD-card-conditioned holdout-metric pattern S10-T2's re-submission established (`agent_outputs/code-refactor-engineer-s10-t2-summary.md` §"Fix shape applied"). The conditional-purchase-count pattern is already in the codebase via `src/predictive/gamma_gamma.py::_compute_holdout_metrics`; survival's holdout window benefits from re-using it. CF is independent of BG/NBD parameters (interaction matrix, not RFM dynamics).

### A.3 Chained refusal — DECISION: survival CHAINS on BG/NBD; CF is INDEPENDENT

**Survival chains on BG/NBD.** Cox PH for replenishment timing models the hazard of next-purchase. Per `ds-architect-s10-cold-start-and-eb-interaction.md` Part 5 L119 verbatim:

> **S11 — survival (lifelines Cox PH / Kaplan-Meier).** Cold-start failure: <30 censored events. Same four-state vocabulary applies … when survival fits on a real cosmetics merchant, the **expected** state is INSUFFICIENT_DATA for the first 90 days because replenishment events haven't accumulated.

If BG/NBD is REFUSED or INSUFFICIENT_DATA, the merchant has no reliable inter-purchase-time distribution at all. Survival becomes ill-conditioned on the same data BG/NBD already rejected (the hazard is a transform of the same gap-time signal). Therefore:

- BG/NBD `INSUFFICIENT_DATA` → survival `INSUFFICIENT_DATA` with `fit_warnings=["chained_bgnbd_refusal"]`.
- BG/NBD `REFUSED` → survival `REFUSED` with `fit_warnings=["chained_bgnbd_refusal"]`.
- BG/NBD `VALIDATED` or `PROVISIONAL` → survival attempts its own fit independently.

This mirrors S10's G-G chaining pattern verbatim. `agent_outputs/code-refactor-engineer-s10-t2.5-summary.md` §3 documents the contract.

**CF is independent.** ALS on a (customer × item) implicit-feedback matrix is mathematically independent of P(alive). A merchant can have a degenerate BG/NBD fit (e.g., flat inter-purchase distribution) yet a healthy item-co-occurrence matrix (because plenty of customers bought multiple items). Conversely, BG/NBD can be VALIDATED on a SKU-poor catalog where ALS factors are noise. **CF runs its own four-state classification on its own floors:**

- INSUFFICIENT_DATA: matrix below the ALS floor (see §C).
- REFUSED: ALS does not converge OR top-K recall on a held-out interaction set is below the floor.
- VALIDATED / PROVISIONAL: per its own metric envelope.

Per `ds-architect-s10-cold-start-and-eb-interaction.md` Part 5 L121 verbatim:

> **S12 — collaborative filtering (implicit ALS) + RFM + retention curves.** ALS cold-start: matrix below ~50×50 with sparse interactions → INSUFFICIENT_DATA.

Note: that verdict pre-dates ROADMAP §2's S11/S12 split. Per current ROADMAP L42 verbatim, CF lives in **S11** (not S12). S12 is RFM + retention curves. This plan honors the current ROADMAP.

### A.4 Orchestration position

Per `src/main.py` L971–1046 verbatim, the predictive blocks land in this order today:

1. L971–1001 — BG/NBD block (T1.5).
2. L1003–1046 — Gamma-Gamma block (T2.5; reads `engine_run.predictive_models["bgnbd"]`).
3. L1048+ — `apply_guardrails` (M5).

S11 inserts **two new blocks immediately after L1046** and before `apply_guardrails`:

```
... [existing G-G block ends at L1046]
[NEW S11-T1.5 survival block — guarded by ENGINE_V2_ML_SURVIVAL — reads predictive_models["bgnbd"] as chained-refusal input]
[NEW S11-T2.5 CF block — guarded by ENGINE_V2_ML_CF — independent of bgnbd]
... [guardrails at L1048]
```

This preserves the single-demote-channel invariant (PIVOTS.md Pivot 7) — both new blocks write only to `engine_run.predictive_models`, never to `engine_run.recommendations`. No new injection blocks in the L1380–1597 forbidden zone (KI-NEW-L is S13.5).

---

## Part B — Survival model spec (Cox PH)

### B.1 What it models

**Unit of analysis: per customer** (not per customer-product pair). One survival fit per merchant. The target event is "next purchase by this customer." The covariates at S11-T1 are RFM-style: `recency_days`, `historical_frequency`, `historical_avg_order_value`, plus an optional `sub_vertical` factor when available from the store profile.

**Why per-customer, not per-customer-per-product:** the wired Tier-B builder this substrate ranks for is `replenishment_due` (per STATE.md §7 L139 verbatim: "5th builder — `replenishment_due` — dormant on Beauty by design"). That builder's cohort is "customers due for a re-buy" — a per-customer audience, not a per-SKU cell. Per-SKU survival would be `replenishment_due_per_sku`, which is a different (unwired) play. Pivot 5 forbids fabricating product-shaped audiences just because the math could.

**Output per customer when VALIDATED/PROVISIONAL:**
- `expected_days_to_next_purchase` (median survival time).
- `hazard_30d`, `hazard_90d` (cumulative hazard at standard horizons).

These are operator-only at S11 close (parquet under `data/<store_id>/predictive/survival.parquet`). S13 plumbs them into `replenishment_due`'s ranking_strategy.

### B.2 Library — `scikit-survival` (v2; was `lifelines` in v1)

**`scikit-survival`** — Sebastian Pölsterl's actively-maintained sklearn-API Cox PH library. Peer-reviewed classical implementation, D-6 carve-out compliant (`PRODUCT.md` D-6) per ROADMAP §5 L100 verbatim:

> Classical Fader/Hardie + Kaplan-Meier + Cox PH + ALS + RFM only — the D-6 carve-out is peer-reviewed-classical only.

**DS rationale for substitution (v2)** — verbatim from `agent_outputs/ds-architect-s11-plan-review.md` §(b).4:

> `lifelines` and `lifetimes` are different libraries with different math heritage. There is no "consistency" argument from using `lifelines` for Cox PH just because we use `lifetimes` for BG/NBD — they share a maintainer but they are independent packages with independent maintenance risk. … `scikit-survival` is more actively maintained than `lifelines` and has a stronger institutional backer (the sklearn ecosystem); adopting it for the new survival surface reduces future maintenance debt.

**API surface used (drop-in substitute for `lifelines.CoxPHFitter`):**
- `from sksurv.linear_model import CoxPHSurvivalAnalysis` — fit Cox PH.
- `from sksurv.metrics import concordance_index_censored` — C-index source. Richer return tuple than `lifelines.utils.concordance_index` (concordant/discordant counts + tied pairs).
- `from sksurv.metrics import integrated_brier_score` — time-dependent Brier-score@90d source (NEW gating metric per §B.3 v2).
- `predict_survival_function(X)` — per-customer survival function for median-survival-time + horizon hazards.

**Library version housekeeping (v2).** `requirements.txt` adds **`scikit-survival>=0.22,<0.24`** at S11-T1 (verify current stable at install time; pin window MUST be `scipy<1.13`-compatible). Operator verifies install on dev as a commit-1 prerequisite (mirroring `agent_outputs/code-refactor-engineer-s10-t1-summary.md` §7 risk #1). `scipy<1.13` pin from S10-T1 stays.

**Mac-ARM install fallback** — verbatim from DS §(b).4: "**Fallback if `scikit-survival` install fails on mac ARM (unlikely but possible):** use **`statsmodels.duration.PHReg`** (already a dependency — zero new install). Statsmodels is well-maintained and Cox PH is in scope. API is older-style but works." This fallback path is documented in the T1 dispatch brief; refactor-engineer surfaces if needed.

**S10's `lifetimes` is NOT refactored at S11** — verbatim from DS §(b).4: "Touching `src/predictive/bgnbd.py` + `gamma_gamma.py` mid-beta-blocking-sequence with merchant onboarding 4 sprints away is unjustified risk for zero S11 benefit. **Defer S10 library refactor to post-beta (S15+).**"

**Maintenance posture mirror.** `lifetimes` is in long-tail maintenance; `scikit-survival` is actively maintained but still single-maintainer at the core. KI-NEW-Q (lifetimes maintenance risk / vendor-fork escape hatch) is the existing parent KI — extended at S11-T3 with scope `{lifetimes, scikit-survival, implicit}` and vendor-fork escape hatches documented (DS §(b).4 estimates: `scikit-survival` Cox PH math vendor-forkable in ~1 day via `scipy.optimize`; `implicit` ALS vendor-forkable in ~3 days but BLAS-bound — accept dependency risk). Filing-vs-deferral remains founder-deferred unless explicit ack at S11 close (see Part F).

### B.3 Validation metric

**Recommended primary gating metric: Harrell's concordance index (C-index).**

Justification:
1. **Operational match.** S13's consumer is the `replenishment_due` audience builder's ranking_strategy — it asks "of two customers, which one is due sooner?" That is exactly the ordinal-pair question C-index answers. The S10 BG/NBD pattern (Spearman rank correlation as the primary gate, MAPE as diagnostic-only — `src/predictive/model_card.py` L116–137 docstring verbatim) is the precedent: gate the metric the consumer actually consumes.
2. **Censored-data native.** C-index handles right-censored observations (customers who haven't repurchased yet) by construction. Spearman / NDCG would require ad-hoc censoring rules.
3. **Literature standard.** Harrell 1996, Steyerberg 2009 — same standing as Spearman for the BG/NBD case. No DS sign-off needed on the choice itself.

**SECONDARY gating metric (NEW in v2 — does gate, not operator-only): time-dependent Brier score at 90 days.**

DS verdict `agent_outputs/ds-architect-s11-plan-review.md` §(a).3 verbatim:

> add a **calibration check** that gates alongside C-index: **time-dependent Brier score at 90d ≤ 0.25** as a *secondary gate* (not operator-only). Pure rank discrimination (C-index) without calibration can ship a model that orders correctly but predicts wildly miscalibrated absolute times — and S13's `replenishment_due` consumer reads `expected_days_to_next_purchase` (a magnitude), not just rank. Without a calibration gate, PROVISIONAL/VALIDATED magnitudes are unsafe.

Brier source: `sksurv.metrics.integrated_brier_score` (DS §(b).4). Surfaced on the ModelCard as a NEW field **`holdout_brier_score_90d: Optional[float]`** (additive within `event_version=1`, same shape as `holdout_c_index`).

**Tertiary operator-visible diagnostic (does NOT gate):** time-dependent AUC at 30d (optional; if cheap to compute, surface; if not, defer to S12).

**DS sign-off status (v2):** **CLOSED — DS-locked** thresholds at §B.5 below. No mid-loop sign-off needed at T1. Verbatim from DS §(d) Q4: "REVISE FLOORS NOW (do not defer)".

**DS-locked thresholds (v2):**
- VALIDATED: `c_index ≥ c_index_validated` (stage-keyed; see §B.5 — 0.62 startup/growth, 0.63 mature/enterprise) AND `holdout_brier_score_90d ≤ 0.25`.
- PROVISIONAL: `0.55 ≤ c_index < c_index_validated` OR `0.25 < holdout_brier_score_90d ≤ 0.35`. (Either failing dimension PROVISIONALs; both passing = VALIDATED.)
- REFUSED: `c_index < 0.55` OR `holdout_brier_score_90d > 0.35` OR convergence failure OR `n_events < min_events_absolute_floor`.
- INSUFFICIENT_DATA: below the cold-start floor (months/repeat/events — see §B.5).

DS-locked rationale (verbatim §(a).2): "realistic Cox PH on DTC replenishment with RFM-only covariates lands in the **0.62–0.68 band**, not 0.70+. Beauty especially won't clear 0.65 without a `sub_vertical` factor or coupon-recency covariate." KI-NEW-P extension covers empirical re-calibration at S14.

### B.4 Four-state classifier mapping

Per `ds-architect-s10-cold-start-and-eb-interaction.md` Part 5 L119 verbatim:

> **S11 — survival (lifelines Cox PH / Kaplan-Meier).** Cold-start failure: <30 censored events. Same four-state vocabulary applies (`VALIDATED` / `PROVISIONAL` / `INSUFFICIENT_DATA` / `REFUSED`).

Concrete mapping:

- **VALIDATED** — fit converged; `n_events ≥ events_floor` (stage-keyed, see §B.5); `c_index ≥ c_index_validated` (stage-keyed 0.62/0.63) AND `holdout_brier_score_90d ≤ 0.25`; no warnings; BG/NBD VALIDATED or PROVISIONAL.
- **PROVISIONAL** — fit converged; `n_events` between `events_floor × provisional_n_multiplier` and `events_floor`; OR `c_index` between `0.55` and `c_index_validated`; OR `holdout_brier_score_90d` between `0.25` and `0.35`. Ranking usable; survival-time magnitudes not quotable to merchant.
- **INSUFFICIENT_DATA** — `n_events < events_floor × provisional_n_multiplier` OR months_data below floor OR repeat_customers below floor OR BG/NBD INSUFFICIENT_DATA. Engine declines to fit. No parquet.
- **REFUSED** — `n_events` met PROVISIONAL floor but `CoxPHSurvivalAnalysis.fit()` raised numerical/convergence exception, OR `c_index < 0.55`, OR `holdout_brier_score_90d > 0.35`, OR BG/NBD REFUSED. ModelCard with `fit_warnings`, no parquet.

**Orthogonal-failure audit case (NEW v2, DS §(a).5):** "BG/NBD VALIDATED + survival REFUSED" is a *meaningful* state, not a contradiction — BG/NBD ranks repeat-propensity well but Cox PH covariates don't add discriminative power → REFUSED on `c_index<0.55`. T3 audit copy (`docs/engine_flags.md`) calls this out as a valid orthogonal-failure case. The reverse — BG/NBD REFUSED → survival VALIDATED — is impossible by chained-refusal construction (correct invariant).

### B.5 Business-stage-keyed thresholds

Mirror the `config/gate_calibration.yaml::model_fit_thresholds.bgnbd` shape introduced at S10-T1 (`config/gate_calibration.yaml` L470–482 verbatim). Schema to append:

```yaml
model_fit_thresholds:
  # ... (existing bgnbd, gamma_gamma blocks unchanged)
  survival:
    by_business_stage:
      startup:    {months_data_validated: 4, repeat_customers_validated: 150,  events_validated: 100,  c_index_validated: 0.62, holdout_brier_score_90d_validated_max: 0.25}
      growth:     {months_data_validated: 6, repeat_customers_validated: 300,  events_validated: 200,  c_index_validated: 0.62, holdout_brier_score_90d_validated_max: 0.25}
      mature:     {months_data_validated: 6, repeat_customers_validated: 500,  events_validated: 400,  c_index_validated: 0.63, holdout_brier_score_90d_validated_max: 0.25}
      enterprise: {months_data_validated: 6, repeat_customers_validated: 1000, events_validated: 800,  c_index_validated: 0.63, holdout_brier_score_90d_validated_max: 0.25}
    by_vertical_months_override:
      supplements: 4
      beauty: 6
    relaxation_factors:
      provisional_n_multiplier: 0.5
      provisional_c_index_floor: 0.55                  # below → REFUSED
      provisional_brier_score_90d_max: 0.35            # above → REFUSED
      min_events_absolute_floor: 30                    # DS L119 "<30 censored events" = INSUFFICIENT_DATA
```

Lock posture (v2, mirrors S10-T1 §C.4):
- C-index floors **DS-locked** at 0.62 (startup/growth) / 0.63 (mature/enterprise) — REVISED from v1's uniform 0.65 per DS §(a).2. Stage-cell numbers are **speculative-until-S14**; KI-NEW-P extended with survival cells at S11-CLOSE.
- Brier@90d VALIDATED max **DS-locked at 0.25** (NEW v2 gating contract); PROVISIONAL band 0.25–0.35; REFUSED above 0.35.
- Vertical-override `months_data` is theory-driven (cadence math from S10-T1), NOT empirical — locked.
- `min_events_absolute_floor: 30` is theory-locked from the DS L119 verdict; do not relax.

### B.6 Chained refusal — survival on BG/NBD

Already specified §A.3. Survival REFUSES (with `chained_bgnbd_refusal`) when BG/NBD is REFUSED. Survival is INSUFFICIENT_DATA (with `chained_bgnbd_refusal`) when BG/NBD is INSUFFICIENT_DATA. This propagates the audit-story distinction (declined vs tried-and-failed) cleanly. **No new ReasonCode needed** — survival routes the same `MODEL_FIT_INSUFFICIENT_DATA` / `MODEL_FIT_REFUSED` codes T3 of S10 added to `src/engine_run.py:73`.

**Orthogonal-failure case (v2 NEW, DS §(a).5):** "BG/NBD VALIDATED + survival REFUSED" is preserved as a meaningful audit state in T3 copy. The reverse ("BG/NBD REFUSED → survival VALIDATED") is impossible by chained construction — correct invariant. T3 dispatch brief carries the orthogonal-failure copy verbatim in `docs/engine_flags.md`.

### B.7 Parquet schema

`data/<store_id>/predictive/survival.parquet` — written only when `fit_status ∈ {VALIDATED, PROVISIONAL}`. Columns:

| Column | Type | Notes |
|---|---|---|
| `customer_id` | str | D-2 / D-3 unit; same key as BG/NBD parquet. |
| `expected_days_to_next_purchase` | float | Median survival time predicted by Cox PH. |
| `hazard_30d` | float | Cumulative hazard at 30 days. |
| `hazard_90d` | float | Cumulative hazard at 90 days. |
| `parquet_schema_version` | int | Pinned `1` at S11-T1. |

D-2/D-3 deletion semantics: parquet lives under `data/<store_id>/predictive/` — already the wipe-unit for D-3. No new directory boundary. INSUFFICIENT_DATA → no parquet (deletion is a no-op for that merchant). REFUSED → no parquet either (only ModelCard JSON mirror).

### B.8 KI-NEW-G interaction — replenishment_due dormancy on Beauty

Per STATE.md §7 L139 verbatim:

> 5th builder — `replenishment_due` — dormant on Beauty by design. Honest dormancy preserved (KI-NEW-G RESOLVED-AS-DOCUMENTED). Will activate on real-merchant data when the replenishment-due cohort materializes.

For Beauty, survival's *fit* may still attempt — repeat customers exist on Beauty (T1 spike: 3,844 repeat customers per `agent_outputs/code-refactor-engineer-s10-t1-summary.md` §3) — but the *consumer* (S13 `replenishment_due` ranking_strategy) stays dormant because the builder itself is dormant on Beauty. **At S11 close, survival's posture on Beauty is "VALIDATED or PROVISIONAL or REFUSED per the fit's own metric envelope" — independent of `replenishment_due` builder activation.**

Per `ds-architect-s10-cold-start-and-eb-interaction.md` Part 5 L119 verbatim:

> when survival fits on a real cosmetics merchant, the **expected** state is INSUFFICIENT_DATA for the first 90 days because replenishment events haven't accumulated. The audit story must make this normal, not alarming.

That verdict refers to real-merchant cold-start (S14), not the Beauty synthetic fixture. The audit-copy in `docs/engine_flags.md` (updated at S11-T3) makes this normal-not-alarming explicit.

**v2 audit-copy lock (DS §(a).15, founder ack 2026-05-26).** T3 dispatch brief carries the following verbatim copy for `docs/engine_flags.md` Beauty-dormancy section:

> "INSUFFICIENT_DATA on Beauty's first 90 days is EXPECTED — repeat-purchase events haven't accumulated; this is product correctness, not a calibration failure."

No paraphrase permitted at the T3 dispatch.

---

## Part C — Collaborative filtering spec (implicit ALS)

### C.1 What it models

**Unit of analysis: per-customer top-N look-alikes.** Output is, per customer, the top-K similar customers (cosine similarity of latent factor vectors) for audience expansion. The S13 consumer is the AUDIENCE layer's expansion strategy on plays whose audiences are small but whose existing members have clear factor neighborhoods (e.g., `winback_dormant_cohort` could backfill from look-alikes of the dormant cohort).

**Not product-affinity at S11.** Item-item affinity ("people who bought X also bought Y") is the Klaviyo-style cross-sell signal. It IS a downstream useful artifact of ALS factors, but the S11 consumer at S13 is look-alike audience expansion, not cross-sell. ALS factors are reusable in both directions; S11 ships only the customer-side look-alike artifact. A future sprint can add the item-side without re-fitting. **Flag this for the founder as Open Question Q1 (§G).**

### C.2 Library

`implicit` — Ben Frederickson's library for implicit-feedback ALS. Per ROADMAP §2 L42 verbatim. Same D-6 carve-out as survival (peer-reviewed classical lineage; Hu, Koren, Volinsky 2008).

**Pin version housekeeping.** Add `implicit==<pin>` to `requirements.txt` at S11-T2 alongside the `lifelines` pin. Operator-verified install on dev as a commit-1 prerequisite. Same KI-NEW-Q extension shape for vendor-fork escape hatch (founder-deferred unless ack).

Mac ARM smoke test: `implicit` historically requires BLAS bindings; CI/dev install verification is mandatory at T2 dispatch (same shape as the `lifetimes` smoke test the S10-T1 receipt called out).

### C.3 Validation metric

**Recommended primary gating metric: top-K recall at K=10 on held-out interactions.**

Justification:
1. **Operational match.** S13's look-alike consumer needs to ask "for a target customer, are the top-K neighbors actually relevant?" Top-K recall is the canonical answer. NDCG is a refinement that weighs rank position — useful but adds complexity without clearly better signal at the per-merchant fit-health gate.
2. **Literature standard.** Hu/Koren/Volinsky 2008 use ranked recall; the ALS implicit-feedback paper itself reports MAP@K and recall@K. Both are in scope.
3. **K=10 default.** Matches typical look-alike audience-expansion request sizes; pinned, not configurable per stage (locked).

**Secondary diagnostic (does NOT gate):** catalog coverage (% of distinct customers reachable as a top-K neighbor of someone). Surface as `coverage_at_10` on the ModelCard. This catches the failure mode where ALS converges but only emits the same few celebrity-customers as everyone's neighbor.

**DS sign-off status (v2): CLOSED — DS-locked at §C.5.** Verbatim from DS §(a).4: "realistic recall@10 lands in the **0.04–0.10** band even on healthy data. **Recommendation:** lower VALIDATED floors to **{startup 0.05, growth 0.06, mature 0.08, enterprise 0.10}**; lower PROVISIONAL floor to 0.03." No mid-loop sign-off needed at T2.

### C.4 Four-state classifier mapping

- **VALIDATED** — ALS converges; matrix dims ≥ stage floor (customers × items × interactions); `recall_at_10 ≥ recall_at_10_validated` (stage-keyed 0.05/0.06/0.08/0.10); `coverage_at_10 ≥ coverage_floor`; no warnings.
- **PROVISIONAL** — matrix dims at relaxed floor OR `recall_at_10` between `0.03` (provisional floor) and `recall_at_10_validated`. Ranking usable; absolute audience-expansion sizes not magnitude-quotable.
- **INSUFFICIENT_DATA** — matrix dims below relaxed floor (<50 customers × <50 items × <2 interactions/customer median) per `ds-architect-s10-cold-start-and-eb-interaction.md` Part 5 L121 verbatim:
  > ALS cold-start: matrix below ~50×50 with sparse interactions → INSUFFICIENT_DATA.
  Engine declines to fit. No parquet.
- **REFUSED** — matrix met PROVISIONAL floor but ALS raises a numerical exception OR `recall_at_10 < 0.03` OR `coverage_at_10` collapses (single-neighbor degeneracy). ModelCard with `fit_warnings`, no parquet.

### C.5 Business-stage-keyed thresholds

Append to `config/gate_calibration.yaml::model_fit_thresholds`:

```yaml
model_fit_thresholds:
  # ... (existing bgnbd, gamma_gamma, survival blocks above)
  cf:
    by_business_stage:
      startup:    {customers_floor: 50,  items_floor: 50,  interactions_per_customer_median_floor: 2, recall_at_10_validated: 0.05, coverage_at_10_validated: 0.30}
      growth:     {customers_floor: 200, items_floor: 50,  interactions_per_customer_median_floor: 2, recall_at_10_validated: 0.06, coverage_at_10_validated: 0.35}
      mature:     {customers_floor: 500, items_floor: 100, interactions_per_customer_median_floor: 2, recall_at_10_validated: 0.08, coverage_at_10_validated: 0.40}
      enterprise: {customers_floor: 1000, items_floor: 200, interactions_per_customer_median_floor: 2, recall_at_10_validated: 0.10, coverage_at_10_validated: 0.45}
    relaxation_factors:
      provisional_recall_at_10_floor: 0.03
      provisional_coverage_at_10_floor: 0.15
      provisional_customers_multiplier: 0.5
    als_hyperparameters:
      factors: 64
      regularization: 0.01
      iterations: 20
      alpha: 40
```

Lock posture (v2):
- recall@10 VALIDATED floors **DS-locked** at {0.05, 0.06, 0.08, 0.10} per stage — REVISED from v1's {0.08, 0.10, 0.12, 0.15} per DS §(a).4.
- PROVISIONAL recall floor **DS-locked at 0.03** (was 0.04 in v1). REFUSED below 0.03.
- `coverage_at_10` floors unchanged from v1 (DS §(a).4: "Keep `coverage_at_10` floors as proposed").
- Stage-cell numbers are **speculative-until-S14**; KI-NEW-P extended with CF cells.
- ALS hyperparameters (factors/regularization/iterations/alpha) are literature-default (Hu 2008 alpha=40); locked at S11; founder/DS revisit only on real-merchant signal.

### C.6 Chained refusal — CF is INDEPENDENT of BG/NBD

Already specified §A.3. CF does NOT chain on BG/NBD. CF runs its own four-state classification on its own data shape (customer × item matrix).

### C.7 Parquet schema

`data/<store_id>/predictive/cf.parquet` — written only when `fit_status ∈ {VALIDATED, PROVISIONAL}`. **Per-customer top-N look-alikes** (not the full N × N similarity matrix — D-2 storage discipline, plus the dense matrix is computationally and privacy-wise unjustified). Columns:

| Column | Type | Notes |
|---|---|---|
| `customer_id` | str | Target customer. D-2 / D-3 wipe-unit. |
| `neighbor_customer_id` | str | One row per (customer, neighbor) pair, top-K = 10 neighbors. |
| `similarity_score` | float | Cosine similarity of latent factor vectors. |
| `rank` | int | 1..K rank of this neighbor for the target customer. |
| `parquet_schema_version` | int | Pinned `1` at S11-T2. |

**D-2/D-3 deletion semantics — critical.** CF stores customer-customer relationships. When merchant A is deleted (D-3 store-wipe), the `data/<merchant_a_store_id>/predictive/cf.parquet` is removed by the existing wipe path. The customer-IDs in that file are all merchant A's own customers — no cross-merchant linkage. Per ROADMAP §5 L102 verbatim:

> No cross-merchant pooling. Per-merchant, per-vertical fits only.

CF stays per-merchant. There is no cross-merchant similarity artifact. **Confirms D-2/D-3 boundary is clean** — no new deletion path needed; the existing per-store-dir wipe subsumes CF artifacts.

PII posture: `customer_id` only — no name, email, etc. Per ROADMAP §5 L103 verbatim ("No PII in predictive artifacts. `customer_id` only.") — already enforced by S10's parquet shape; S11 inherits.

### C.8 Item-affinity (cross-sell) deferral

Item-affinity ("people who bought X also bought Y") is a natural extension of the ALS item-factor matrix. It is NOT in S11 scope. Reasons:

1. ROADMAP §2 L42 lists "collaborative filtering" only; PRODUCT.md §3 says nothing about cross-sell on the slate today.
2. The S13 consumer (audience expansion) is customer-side, not product-side.
3. Klaviyo cross-sell flows are an operator-published artifact, not engine output today — D-5 manual import.

Q1 in §G v2: **CLOSED — look-alikes only confirmed by founder ack + DS §(d).Q1.** Item-side artifact deferred to a later sprint; reusable from the same factor matrices without re-fitting.

---

## Part D — Ticket decomposition

S11 follows the S7.6 / S8 / S10 atomic-flip cadence. Five tickets, ~15 commits, two atomic flips. Each ticket's refactor dispatch brief MUST include the path `agent_outputs/code-refactor-engineer-<ticket>-summary.md` per founder protocol (locked 2026-05-25, CLAUDE.md Subagent Handoff Discipline). Per-ticket loop: refactor → DS review → orchestrator commits+pushes → next ticket.

No S11-T0 lineage-fatigue analog. The lineage-keyed fatigue fix shipped at S10-T0 (`agent_outputs/code-refactor-engineer-s10-t0-summary.md`). No analogous correctness debt exists at S11 dispatch — the substrate is greenfield, not a rebuild. Documented in §G Q3.

### S11-T1 — Survival substrate (Cox PH) + ModelCard wiring + business-stage thresholds (FLAG-OFF land)

**Scope:**
- Add **`scikit-survival>=0.22,<0.24`** to `requirements.txt` (v2 — was `lifelines==<pin>` in v1). Verify install on dev — commit-1 prerequisite. T1 commit-1 smoke test: pip install succeeds end-to-end on mac-ARM; `scikit-survival` + `scipy<1.13` + existing `lifetimes==0.11.3` coexist (mirrors S10-T1 install verification per `agent_outputs/code-refactor-engineer-s10-t1-summary.md` §7 risk #1). **Fallback if mac-ARM install fails:** `statsmodels.duration.PHReg` (already a dependency — zero new install); refactor-engineer surfaces and escalates before substituting.
- New `src/predictive/survival.py`:
  - `fit_survival_model(orders_df, profile, bgnbd_model_card, *, store_id, data_dir, thresholds: dict) -> ModelCard`
  - Cold-start guard returns ModelCard with `fit_status=INSUFFICIENT_DATA` (silent decline; no parquet).
  - Chained refusal: if `bgnbd_model_card.fit_status in {REFUSED, INSUFFICIENT_DATA}`, return ModelCard with the matching status and `fit_warnings=["chained_bgnbd_refusal"]`.
  - Fit-failure guard: numerical/convergence exceptions from `sksurv.linear_model.CoxPHSurvivalAnalysis.fit()` → REFUSED with diagnostic warning.
  - C-index computation via `sksurv.metrics.concordance_index_censored` on a time-based holdout (mirror S10-T1.4 time-based holdout pattern).
  - **Brier-score@90d computation via `sksurv.metrics.integrated_brier_score` — NEW v2 GATING metric (not operator-only).** ModelCard's `holdout_brier_score_90d` populated whenever a fit attempt succeeds enough to evaluate.
  - Parquet writer to `data/<store_id>/predictive/survival.parquet` when status ∈ {VALIDATED, PROVISIONAL}.
- Extend `src/predictive/model_card.py::_load_model_fit_thresholds` to read the new `model_fit_thresholds.survival` block. Add fallback `_FALLBACK_SURVIVAL_STAGE_CELL` / `_FALLBACK_SURVIVAL_RELAXATION` constants mirroring the existing `_FALLBACK_GAMMA_GAMMA_*` shape (`src/predictive/model_card.py` L195–208 verbatim shape).
- Append `model_fit_thresholds.survival` block to `config/gate_calibration.yaml` (§B.5 verbatim schema).
- New flag `ENGINE_V2_ML_SURVIVAL` in `src/utils.py` `DEFAULTS` table, default `"false"`. **CRITICAL — T1.5 lesson:** add `ENGINE_V2_ML_SURVIVAL` to the `_coerce` bool set at `src/utils.py:1156` IN T1, not T1.5. (S10-T2 pre-emptively added `ENGINE_V2_ML_GAMMA_GAMMA` to the coerce set at T2 per the receipt; mirror that here.)
- `ModelCard` dataclass at `src/predictive/model_card.py:99-154` is extended with TWO new additive optional fields at T1 (v2):
  - `holdout_c_index: Optional[float] = None`
  - `holdout_brier_score_90d: Optional[float] = None` (NEW v2 gating field)
  Pattern: ModelCard is *additive* within event_version=1; new optional fields are safe.
- `engine_run.predictive_models["survival"]` lands at flag-OFF land = `{}` (no key present); flag-ON path lands the ModelCard.

**Files touched:**
- NEW: `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/survival.py`
- MODIFIED: `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/model_card.py` — threshold loader extension + TWO new optional fields on `ModelCard` (`holdout_c_index`, `holdout_brier_score_90d`).
- MODIFIED: `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` — new flag + `_coerce` bool set entry.
- MODIFIED: `/Users/atul.jena/Projects/Personal/beaconai/requirements.txt` — `scikit-survival>=0.22,<0.24` (v2).
- MODIFIED: `/Users/atul.jena/Projects/Personal/beaconai/config/gate_calibration.yaml` — append `model_fit_thresholds.survival` block.
- NEW tests:
  - `tests/test_s11_t1_survival_fit.py` (~12 tests — INSUFFICIENT_DATA paths, chained refusal, REFUSED, VALIDATED/PROVISIONAL via synthetic Cox PH generator, determinism).
  - `tests/test_s11_t1_threshold_loader.py` (~6 tests — stage cells, vertical-override months, broadening, fallback).
  - `tests/test_s11_t1_model_card.py` (~3 tests — `holdout_c_index` round-trip, ModelCard additive contract preserved).

**Acceptance criteria:**
1. Flag OFF default; `engine_run.predictive_models["survival"]` absent on every pinned fixture; all 5 pinned fixtures (Beauty, Supplements, M0 small_sm, M0 mid_shopify, M0 micro_coldstart) byte-identical pre-T1 vs post-T1.
2. ~21 new tests in three files; all pass.
3. Threshold loader returns survival sub-dict alongside bgnbd / gamma_gamma sub-dicts; stage cell + vertical-override months wired.
4. `ENGINE_V2_ML_SURVIVAL` in the `_coerce` bool set at T1 — `tests/test_s11_t1_survival_fit.py::test_flag_in_coerce_bool_set` pins this.
5. ModelCard contract: `holdout_c_index` AND `holdout_brier_score_90d` are the two new optional fields; existing fields (`holdout_rank_spearman`, `holdout_mape`, `holdout_agg_ratio`) untouched. `test_engine_run_round_trip` passes with a survival ModelCard payload carrying both.
6. **VALIDATED requires BOTH `c_index ≥ c_index_validated` (stage-keyed 0.62/0.63) AND `holdout_brier_score_90d ≤ 0.25`.** PROVISIONAL/REFUSED per §B.4 v2 mapping. Pinned by `tests/test_s11_t1_survival_fit.py::test_brier_secondary_gate`.
7. `scikit-survival` install verified on dev (operator confirms via commit-1 smoke test `from sksurv.linear_model import CoxPHSurvivalAnalysis; from sksurv.metrics import concordance_index_censored, integrated_brier_score`).
8. Mac-ARM coexistence smoke: `scikit-survival` + `scipy<1.13` + `lifetimes==0.11.3` install end-to-end without dependency conflict. If install fails, fallback to `statsmodels.duration.PHReg` documented in §B.2 v2; refactor-engineer escalates before substituting.
9. Commit body carries `Deviation check: none.`
10. Suite green; no regressions on existing 1944 tests.

**Flag:** `ENGINE_V2_ML_SURVIVAL` default `false`. No orchestration wire yet (T1 is substrate-only).

**Per-fixture expected outcome (flag forced ON for harness test only):**
- Beauty (3,844 repeat customers, 259 days, ~15k orders): likely PROVISIONAL or REFUSED. The honest C-index on synthetic Beauty data is unknown until the fit runs (Pivot 5 — do NOT reshape fixture to clear).
- Supplements: likely INSUFFICIENT_DATA or chained_bgnbd_refusal (BG/NBD already REFUSED on synthetic supplements per S10-T1.5).
- M0 small_sm / mid_shopify / micro_coldstart: INSUFFICIENT_DATA via chained refusal (BG/NBD already INSUFFICIENT_DATA on M0 micro_coldstart) or below survival floor directly.

**Option γ extends (likely).** Synthetics will REFUSE / INSUFFICIENT_DATA honestly across the board. This is the same posture S10's 5/5 outcome locked. Real VALIDATED evidence comes from S14 real-merchant data.

**Refactor commit pattern (3 commits):** impl + `agent_outputs/code-refactor-engineer-s11-t1-summary.md` + memory.md template-shape entry. Commit body carries `Deviation check: none.` (v2 P).

---

### S11-T1.5 — Atomic flag flip `ENGINE_V2_ML_SURVIVAL` ON + orchestration wire + parquet + rollback test

**Scope:**
- Flip `ENGINE_V2_ML_SURVIVAL` default `false → true` in `src/utils.py`.
- Wire `fit_survival_model` into `src/main.py` orchestration immediately after the G-G block (post-L1046, pre-`apply_guardrails`). Reads `engine_run.predictive_models["bgnbd"]` as chained-refusal input. Writes `ModelCard` to `engine_run.predictive_models["survival"]`. Single try/except wrapper matching the BG/NBD / G-G precedent.
- Parquet artifact written at `data/<store_id>/predictive/survival.parquet` when status ∈ {VALIDATED, PROVISIONAL}. ModelCard JSON mirror at `data/<store_id>/predictive/survival.model_card.json` when any fit attempted.
- Update `tests/test_determinism_cross_run.py::_NESTED_NORMALIZED_PATHS` — add `"predictive_models.survival.fit_timestamp"` (mirrors T1.5 + T2.5 precedent at `tests/test_determinism_cross_run.py` L99–118 per S10-T2.5 receipt).
- Update `tests/test_s10_t1_5_bgnbd_rollback.py::_run_and_load` to set `ENGINE_V2_ML_SURVIVAL=false` explicitly — keeps the BG/NBD-rollback assertion `predictive_models == {}` clean under the new default. Mirror the T2.5 receipt §10 risk #3 lesson.
- New `tests/test_s11_t1_5_survival_rollback.py` (~4 tests):
  - `test_flag_off_rollback_survival_absent` — `ENGINE_V2_ML_SURVIVAL=false` with BG/NBD ON, G-G ON: `predictive_models` contains `bgnbd` and `gamma_gamma` but NOT `survival`.
  - `test_flag_on_populates_survival_on_beauty` — all 3 ML flags ON: `predictive_models["survival"]` present; `fit_status` ∈ four-state vocabulary.
  - `test_all_flags_off_predictive_models_empty` — all 3 ML flags OFF: `predictive_models == {}`.
  - `test_survival_on_bgnbd_off_handles_missing_card` — survival ON, BG/NBD OFF: `bgnbd_model_card=None`; survival handles it cleanly; no crash. (Mirror T2.5 receipt §3.1 edge case.)
- Rename `tests/test_s11_t1_survival_fit.py::test_flag_default_off` → `test_flag_default_on_post_t1_5`, flip the assertion.

**Files touched:** `src/utils.py` (flag default flip); `src/main.py` L1046+ (new survival orchestration block, ~40 lines, structurally identical to the existing G-G block); `tests/test_determinism_cross_run.py`; `tests/test_s10_t1_5_bgnbd_rollback.py`; NEW `tests/test_s11_t1_5_survival_rollback.py`.

**Acceptance criteria:**
1. All 5 pinned briefing.html fixtures byte-identical (renderer does not consume `predictive_models`; verified via `test_slate_regression_*`, `test_golden_diff`, `test_s8_t3_provenance`). Hard gate.
2. engine_run.json has no byte-pin contract today (re-confirmed at S10-T1.5, T2.5); additive `predictive_models["survival"]` payload lands free.
3. Rollback contract: `ENGINE_V2_ML_SURVIVAL=false` reproduces the pre-T1.5 shape (`"survival"` absent from `predictive_models`).
4. PlayCard.predicted_segment / model_card_ref stay `None` — S13 wires the consumers.
5. Single-demote-channel invariant preserved — orchestration block writes only to `engine_run.predictive_models["survival"]`, never to `engine_run.recommendations`. No edits to `src/decide.py`, `src/sizing.py`, `src/main.py:1380-1597`, `src/guardrails.py` (KI-NEW-L is S13.5).
6. Determinism comparator learns the new `fit_timestamp` field — `tests/test_determinism_cross_run.py` green.
7. T1.5 rollback test contract update propagated to T1.5 BG/NBD-rollback test (env now sets `ENGINE_V2_ML_SURVIVAL=false`).
8. Suite green; +4 new tests vs T1 baseline (the 4 new rollback tests).

**Flag:** flipped ON (atomic single commit per S7.6/S8/T1.5/T2.5 cadence — orchestrator commits per founder protocol).

**Per-fixture expected outcome:** Option γ extends — 5/5 likely REFUSED or INSUFFICIENT_DATA on synthetics (Beauty's C-index unknown until the fit runs; Pivot 5 forbids reshape). Real VALIDATED evidence at S14.

**Refactor commit pattern (1 atomic commit + summary file):** S7.6/S8/T1.5/T2.5 cadence is a SINGLE staged commit; orchestrator commits. Plus `agent_outputs/code-refactor-engineer-s11-t1.5-summary.md`. Commit body carries `Deviation check: none.` (v2 P).

---

### S11-T2 — Collaborative filtering substrate (implicit ALS) + ModelCard wiring + thresholds (FLAG-OFF land)

**Scope:**
- Add `implicit==<pin>` to `requirements.txt` (pin window must be `scipy<1.13`-compatible; current stable verified at T2 commit-1). Verify install on dev (commit-1 prerequisite — mac ARM smoke test; ALS uses BLAS bindings).
- New `src/predictive/cf.py`:
  - `fit_cf_model(orders_df, profile, *, store_id, data_dir, thresholds: dict) -> ModelCard`
  - **Note: no BG/NBD chained input.** CF is independent (§A.3).
  - Cold-start guard returns ModelCard `fit_status=INSUFFICIENT_DATA` when matrix dims < 50×50 or interactions/customer median < 2.
  - Build (customer × item) implicit-feedback matrix from orders (using order line items; if line items unavailable in CSV, use order-level SKU when present; if neither, INSUFFICIENT_DATA — `data_unavailable` warning).
  - ALS fit (`implicit.als.AlternatingLeastSquares` with hyperparams from §C.5 YAML block).
  - Top-K recall @10 on a held-out interaction set (random 20% interactions held out, hash-stable per `hashlib.sha1(customer_id||item_id||"cf_holdout_v1")` mod 5 == 0 — mirrors S10's determinism §C.7).
  - Coverage @10 computation.
  - Fit-failure / non-convergence / low-recall → REFUSED.
  - Parquet writer to `data/<store_id>/predictive/cf.parquet` when status ∈ {VALIDATED, PROVISIONAL}; per-customer top-10 neighbors.
- Extend `src/predictive/model_card.py::_load_model_fit_thresholds` to read `model_fit_thresholds.cf` block. Add fallback constants.
- Append `model_fit_thresholds.cf` block to `config/gate_calibration.yaml` (§C.5 verbatim).
- New flag `ENGINE_V2_ML_CF` in `src/utils.py` DEFAULTS, default `"false"`. **CRITICAL: add to `_coerce` bool set at T2** (not T2.5).
- Add new optional fields to `ModelCard`:
  - `holdout_recall_at_10: Optional[float] = None`
  - `coverage_at_10: Optional[float] = None`
- Same dataclass additivity discipline as `holdout_c_index` at T1.

**Files touched:**
- NEW: `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/cf.py`
- MODIFIED: `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/model_card.py` — threshold loader CF block + 2 new optional ModelCard fields.
- MODIFIED: `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` — new flag + `_coerce` bool set.
- MODIFIED: `/Users/atul.jena/Projects/Personal/beaconai/requirements.txt` — `implicit==<pin>`.
- MODIFIED: `/Users/atul.jena/Projects/Personal/beaconai/config/gate_calibration.yaml` — append `model_fit_thresholds.cf` block.
- NEW tests:
  - `tests/test_s11_t2_cf_fit.py` (~14 tests — INSUFFICIENT_DATA paths (4 — customer floor, item floor, interaction floor, missing data); REFUSED (2 — non-convergence, low recall); VALIDATED/PROVISIONAL via synthetic CF generator (3); determinism (2); top-K recall correctness (1); coverage (1); CF independence from BG/NBD (1 — CF runs even when BG/NBD REFUSED)).
  - `tests/test_s11_t2_threshold_loader.py` (~5 tests — CF stage cells; ALS hyperparams read; relaxation factors).

**Acceptance criteria:**
1. Flag OFF default; all 5 pinned fixtures byte-identical.
2. ~19 new tests; all pass.
3. CF independence: `test_cf_runs_when_bgnbd_refused` — pin the contract that CF does NOT chain on BG/NBD.
4. ModelCard additivity preserved (two new optional fields: `holdout_recall_at_10`, `coverage_at_10`).
5. **VALIDATED requires `recall_at_10 ≥ recall_at_10_validated` (stage-keyed 0.05/0.06/0.08/0.10 v2)** AND `coverage_at_10 ≥ coverage_at_10_validated`. PROVISIONAL band: 0.03 ≤ recall < stage floor. REFUSED: recall < 0.03 OR coverage collapse. Pinned by `tests/test_s11_t2_cf_fit.py::test_recall_floor_stage_keyed_v2`.
6. `ENGINE_V2_ML_CF` in `_coerce` bool set at T2 (NOT T2.5) — pinned by `tests/test_s11_t2_cf_fit.py::test_flag_in_coerce_bool_set`.
7. `implicit` install verified on dev (commit-1 smoke test).
8. Commit body carries `Deviation check: none.` (v2 P).
9. Suite green.

**Flag:** `ENGINE_V2_ML_CF` default `false`.

**Per-fixture expected outcome:** Beauty has 15k orders / 9k customers — may clear customer floor for mature. Whether ALS fit converges with meaningful recall on synthetic Beauty (which lacks intentional purchase patterns) is unknown until fit runs. **Pivot 5: do not reshape.** Expected: PROVISIONAL or REFUSED on Beauty; INSUFFICIENT_DATA on Supplements + all M0 fixtures. Option γ extends (likely).

**Refactor commit pattern (3 commits):** impl + `agent_outputs/code-refactor-engineer-s11-t2-summary.md` + memory.md template-shape entry. Commit body carries `Deviation check: none.` (v2 P).

---

### S11-T2.5 — Atomic flag flip `ENGINE_V2_ML_CF` ON + orchestration wire + parquet + rollback test

**Scope:**
- Flip `ENGINE_V2_ML_CF` default `false → true`.
- Wire `fit_cf_model` into `src/main.py` orchestration immediately after the survival block (post-survival, pre-`apply_guardrails`). Order matters: BG/NBD → G-G → survival → CF. Does NOT read `engine_run.predictive_models["bgnbd"]` (independence). Writes ModelCard to `engine_run.predictive_models["cf"]`.
- Parquet at `data/<store_id>/predictive/cf.parquet` when status ∈ {VALIDATED, PROVISIONAL}.
- Update `tests/test_determinism_cross_run.py::_NESTED_NORMALIZED_PATHS` — add `"predictive_models.cf.fit_timestamp"`.
- Update `tests/test_s10_t1_5_bgnbd_rollback.py` AND `tests/test_s11_t1_5_survival_rollback.py` to explicitly set `ENGINE_V2_ML_CF=false` in their `_run_and_load` helpers (keeps their respective rollback assertions clean under the new CF default-ON).
- New `tests/test_s11_t2_5_cf_rollback.py` (~4 tests):
  - `test_flag_off_rollback_cf_absent`.
  - `test_flag_on_populates_cf_on_beauty`.
  - `test_all_flags_off_predictive_models_empty`.
  - `test_cf_runs_on_bgnbd_off_independence` — pin that CF runs to its own four-state classification when BG/NBD is OFF.
- Rename `tests/test_s11_t2_cf_fit.py::test_flag_default_off` → `test_flag_default_on_post_t2_5`.

**Acceptance criteria:** identical shape to T1.5 acceptance (briefing.html byte-identity; engine_run.json no byte-pin; rollback contract; PlayCard stubs `None`; single-demote-channel preserved; determinism comparator updated; predecessor rollback tests updated; suite green).

**Flag:** flipped ON. Atomic single commit. Commit body carries `Deviation check: none.` (v2 P).

**Per-fixture expected outcome:** Option γ extends — likely 5/5 REFUSED / INSUFFICIENT_DATA.

---

### S11-T3 (CLOSE) — Documentation + KI-NEW-P extension + ranking-strategy chain confirmation

**Scope (mirrors S10-T3 §D-T3; v2 additions inline):**
- Update `docs/engine_flags.md`:
  - Add ML-fit gate row entries for `ENGINE_V2_ML_SURVIVAL` and `ENGINE_V2_ML_CF`. Survival row includes BOTH c_index AND `holdout_brier_score_90d` as gating fields (v2 NEW).
  - Update the ranking-strategy fallback chain section (`docs/engine_flags.md` L128 verbatim chain `BG/NBD → CF → survival → RFM → recency`) to confirm all four ML rungs are now wired at substrate level. Document the chain as the *documented* (not yet code-wired) S13 strategy.
  - **NEW v2 — orthogonal-failure audit copy:** "BG/NBD VALIDATED + survival REFUSED is a valid orthogonal-failure case, not a contradiction: BG/NBD ranks repeat-propensity well but Cox PH covariates don't add discriminative power. The reverse (BG/NBD REFUSED → survival VALIDATED) is impossible by chained construction." (DS §(a).5).
  - **NEW v2 — Beauty replenishment_due dormancy audit copy, locked verbatim per DS §(a).15:** "INSUFFICIENT_DATA on Beauty's first 90 days is EXPECTED — repeat-purchase events haven't accumulated; this is product correctness, not a calibration failure."
- **NEW v2 — Update ROADMAP.md §1 L13 and §2 L42 verbatim text** from "`lifelines`" → "`scikit-survival`" (founder ack 2026-05-26).
- **NEW v2 — Update `docs/DECISIONS.md` D-FLOOR-replenishment_due footnote** with the `scikit-survival` substitution rationale per DS §(b).4.
- Extend `KNOWN_ISSUES.md::KI-NEW-P` (v2 — ~30 numbers total by S11 close):
  - Survival stage cells: 4 stages × `{months_data_validated, repeat_customers_validated, events_validated, c_index_validated, holdout_brier_score_90d_validated_max}` (5 metrics × 4 = 20 numbers, was 16 in v1) + 2 vertical-month overrides.
  - CF stage cells: 4 stages × `{customers_floor, items_floor, interactions_per_customer_median_floor, recall_at_10_validated, coverage_at_10_validated}` (5 metrics × 4 = 20 numbers; recall stage floors per v2 §C.5).
  - Sub-bullets (verbatim text in T3 dispatch brief):
    - "Survival on flat replenishment-time distributions: c_index ≈ 0.5; REFUSED expected; not a calibration issue."
    - "CF on sparse interaction matrices: recall@10 collapses to ~0; INSUFFICIENT_DATA expected for stores below 50 customers OR <2 interactions/customer median."
    - "Beauty fixture survival expected posture: PROVISIONAL or REFUSED; Beauty fixture CF expected posture: PROVISIONAL or REFUSED. Real VALIDATED evidence at S14."
    - **(NEW v2)** "Survival chained-refusal vs orthogonal-failure cases: BG/NBD VALIDATED + survival REFUSED is meaningful (Cox PH covariates don't add discriminative power on this merchant); BG/NBD REFUSED → survival REFUSED is chained and not a separate failure mode."
    - **(NEW v2)** "CF cold-start band on Beauty + Supplements: expected REFUSED on synthetics per Option γ; real-merchant evidence at S14."
  - Closure criterion: ≥3 real beta merchants per stage with realized-vs-predicted ranking AND magnitude data (NEW v2: magnitude data needed because Brier@90d gates now).
- **KI-NEW-Q extension at S11-T3 (v2 NEW per DS §(b).4):** scope becomes `{lifetimes, scikit-survival, implicit}` maintenance posture; vendor-fork escape hatches documented (`scikit-survival` Cox PH ~1 day via `scipy.optimize`; `implicit` ALS ~3 days BLAS-bound). **Filing-vs-deferral remains founder-deferred unless explicit ack at S11 close** (see Part F v2; surfaced as decision point not auto-filed).
- **KI-NEW-R (vendor-fork escape hatches)** — same founder-deferred posture; surfaced as a Part F question, not auto-filed.
- No ReasonCode additions. S10-T3 added `MODEL_FIT_INSUFFICIENT_DATA` and `MODEL_FIT_REFUSED`; survival and CF route through the same codes. ReasonCode enum is unchanged at S11.
- No precedence-test changes. The four-orthogonal-gate precedence pinned at S10-T3 (`tests/test_reason_code_precedence_invariant.py`) covers all ML models; survival and CF route through ML-fit (lowest precedence) just like BG/NBD and G-G.
- memory.md sprint-close entry (template-shape, ≤15 lines per CLAUDE.md memory rule).
- `ROADMAP.md` §1 + §2 row updated to "S11 SHIPPED 2026-05-26-or-later" (mirror S10-CLOSE pattern at `agent_outputs/code-refactor-engineer-s10-close-summary.md` §2).
- `STATE.md` §4 — the dormant 4th gate is unchanged structurally (still ML-fit). Update wording only if the substrate-coverage count of dormant predictive models changes — recommend a one-line note that BG/NBD + G-G + survival + CF are now substrate-present (S11-CLOSE-summary captures the table).
- `agent_outputs/INDEX.md` Sprint 11 section added.

**Files touched:** `docs/engine_flags.md`, `docs/DECISIONS.md` (v2 — `scikit-survival` rationale on D-FLOOR-replenishment_due), `KNOWN_ISSUES.md`, `memory.md`, `ROADMAP.md` (§1 L13 + §2 L42 verbatim updates v2), `STATE.md` (light), `agent_outputs/INDEX.md`. No code, no tests, no fixtures.

**Acceptance criteria:**
1. All 5 pinned fixtures byte-identical (documentation-only ticket).
2. KI-NEW-P extended with survival + CF cells (~30 numbers total v2); orthogonal-failure + CF cold-start sub-bullets added.
3. ROADMAP.md §1 L13 + §2 L42 verbatim text updated `lifelines` → `scikit-survival`.
4. `docs/DECISIONS.md` D-FLOOR-replenishment_due footnote carries `scikit-survival` substitution rationale.
5. `docs/engine_flags.md` carries orthogonal-failure audit copy + Beauty dormancy verbatim copy.
6. KI-NEW-Q + KI-NEW-R remain founder-deferred unless explicit ack at S11 close; otherwise filed per Part F v2.
7. memory.md entry within template envelope.
8. Sprint-close summary file `agent_outputs/code-refactor-engineer-s11-close-summary.md` present.
9. Suite green.

**Flag:** none. Commit body carries `Deviation check: none.` (v2 P).

---

### Ticket count summary

| Ticket | Scope (one line) | Commits | Flag flip? |
|---|---|---|---|
| S11-T1 | Survival substrate (Cox PH) + chained refusal on BG/NBD + thresholds | 3 | no (default OFF) |
| S11-T1.5 | Flip survival ON + orchestration wire + parquet + rollback | 1 atomic | yes (atomic) |
| S11-T2 | CF substrate (implicit ALS, independent of BG/NBD) + thresholds | 3 | no (default OFF) |
| S11-T2.5 | Flip CF ON + orchestration wire + parquet + rollback | 1 atomic | yes (atomic) |
| S11-T3 (CLOSE) | docs/engine_flags.md + KI-NEW-P extension + memory + INDEX + ROADMAP/STATE | 1 | no |
| **Total** | **5 tickets** | **9 commits** | **2 atomic flips** |

Estimated duration: ~9–11 working days. Mirrors S10's 11–13 day envelope minus T0 (no analog needed at S11) minus T1.4-style mid-sprint metric correction (which we hope to avoid via the S10 lessons — see §E).

**v2 ticket count delta:** unchanged from v1 (5 tickets, 9 commits, 2 atomic flips). Acceptance criteria changes per ticket — see updated §D-T1 / T1.5 / T2 / T2.5 / T3 above. Library substitution + dual-gate survival + revised CF floors are scope-contained within existing tickets; no new ticket needed.

---

## Part E — Cross-cutting risks

### E.1 Synthetic-fixture posture — Option γ extends

Per Pivot 5 (synthetic-fixture honesty rule) and per the S10 outcome: 5/5 synthetic fixtures REFUSED / INSUFFICIENT_DATA on BG/NBD → chained_bgnbd_refusal on G-G. Survival will inherit chained refusal on synthetics where BG/NBD is REFUSED/INSUFFICIENT_DATA. CF is independent but the synthetic fixtures lack intentional co-purchase patterns; ALS recall will likely be very low → REFUSED.

**Expected per-fixture outcome at S11-T2.5 close:**

| Fixture | BG/NBD (T1.5) | G-G (T2.5) | Survival (S11-T1.5) | CF (S11-T2.5) |
|---|---|---|---|---|
| `healthy_beauty_240d` | REFUSED | REFUSED (chained) | likely REFUSED (chained OR own metric below floor; Beauty C-index unknown) | likely PROVISIONAL OR REFUSED (own metric) |
| `healthy_supplements_240d` | REFUSED | REFUSED (chained) | REFUSED (chained) | likely INSUFFICIENT_DATA or REFUSED |
| `small_sm` (golden) | REFUSED | REFUSED (chained) | REFUSED (chained) | likely INSUFFICIENT_DATA |
| `mid_shopify` (golden) | INSUFFICIENT_DATA | REFUSED (chained) | INSUFFICIENT_DATA (chained) | likely INSUFFICIENT_DATA |
| `micro_coldstart` (golden) | INSUFFICIENT_DATA | REFUSED (chained) | INSUFFICIENT_DATA (chained) | INSUFFICIENT_DATA (below floor) |

**Will any pinned synthetic produce VALIDATED?** Almost certainly no. Same posture as S10. **Option γ extends — 5/5 REFUSED/INSUFFICIENT_DATA on synthetics is the honest beauty-of-the-engine.** Real VALIDATED evidence at S14 from real-merchant data.

**Flag for the founder:** If any S11 synthetic clears VALIDATED, that itself is a signal worth audit — it may indicate the synthetic generator inadvertently produces stronger signal for survival/CF than for BG/NBD, which would be a fixture-shape question to revisit at S14 close.

### E.2 PlayCard additive contract — no new fields at S11

S11 inherits S10's contract:
- `PlayCard.predicted_segment: Optional[PredictedSegment] = None` (stub at `src/engine_run.py:837` per the engine_run grep).
- `PlayCard.model_card_ref: Optional[ModelCardRef] = None` (stub at `src/engine_run.py:838`).

Both stay `None` at S11 close. S13 wires the populating producers.

What S11 *does* add:
- `engine_run.predictive_models["survival"]` and `engine_run.predictive_models["cf"]` entries (typed ModelCards).
- Four new optional fields on `ModelCard` itself (v2): `holdout_c_index`, **`holdout_brier_score_90d` (NEW v2 gating)**, `holdout_recall_at_10`, `coverage_at_10`. **Four optional fields, additive within `event_version=1`.**

By S11-T2.5 close `engine_run.predictive_models` carries **four entries**: `bgnbd`, `gamma_gamma`, `survival`, `cf`. engine_run.json grows. briefing.html byte-identity must hold — renderer does not consume `predictive_models` (verified at S10).

### E.3 Determinism comparator must learn 2 new fit_timestamp paths

Per S10-T2.5 risk #5 verbatim from `agent_outputs/code-refactor-engineer-s10-t2.5-summary.md` §10:
> `fit_timestamp` is run-varying. Now normalized in the cross-run determinism comparator for both BG/NBD and G-G. If a future ticket adds another wall-clock field to the ModelCard, the comparator must learn it too (same standing risk noted at T1.5 §10.3).

S11 dispatch briefs MUST require:
- T1.5: add `"predictive_models.survival.fit_timestamp"` to `tests/test_determinism_cross_run.py::_NESTED_NORMALIZED_PATHS`.
- T2.5: add `"predictive_models.cf.fit_timestamp"` to the same list.

Pre-existing rollback tests (`test_s10_t1_5_bgnbd_rollback.py`, `test_s11_t1_5_survival_rollback.py`) must have their `_run_and_load` helpers updated to set the new flags `=false` at each flip — keeps prior rollback assertions clean.

### E.4 `_coerce` bool set must include new flags from T1 / T2 (NOT T1.5 / T2.5)

S10-T1.5 lesson: the dispatch brief MUST require new flags added to the `_coerce` bool set at `src/utils.py:1156` in the *substrate* ticket (T1 for survival, T2 for CF), not at the atomic-flip ticket. The S10-T2 receipt §"Patch summary" notes:
> Already in `_coerce` bool set at L1156 (T2 pre-emptively added per T1.5 lesson) — no change there.

DO NOT have refactor-engineer discover the gap mid-flip. Pin this in T1 and T2 dispatch briefs.

### E.5 Ranking-strategy chain pinning

Per `docs/engine_flags.md` L128 verbatim:
> `BG/NBD → CF → survival → RFM → recency`. RFM is the floor; recency is the last-resort.

At S11 close, all four ML rungs in the chain are wired *at substrate level* (BG/NBD ✓ T1.5, G-G ✓ T2.5 — note: G-G isn't a chain rung but it gates magnitudes; CF ✓ S11-T2.5, survival ✓ S11-T1.5). RFM (S12) and recency (always-available) close the chain at S12.

T3 updates the chain documentation to confirm (v2 Q): "**At S11 close, all four ML rungs of the ranking-strategy chain are wired in `docs/engine_flags.md`** — BG/NBD (S10-T1.5) → CF (S11-T2.5) → survival (S11-T1.5) → RFM (S12) → recency (always-available). RFM is the non-ML floor landing at S12; S13 wires the consumer in `replenishment_due` and other ranking_strategy callsites. T3 adds survival + CF gate rows to `docs/engine_flags.md` alongside the existing BG/NBD + G-G rows."

### E.6 Library risks (parallel to S10 risks)

| Risk | Mitigation | Rollback |
|---|---|---|
| `scikit-survival` install fails on dev / mac ARM | CI smoke test at T1 commit-1; hard-pin version `>=0.22,<0.24`; documented fallback to `statsmodels.duration.PHReg` (zero new install) per DS §(b).4 | `pip uninstall scikit-survival`; flag → `false` (or substitute to statsmodels per fallback) |
| `implicit` install fails on dev / mac ARM (BLAS bindings) | CI smoke test at T2 commit-1; hard-pin version | `pip uninstall implicit`; `ENGINE_V2_ML_CF=false` |
| `scipy<1.13` pin (S10) conflicts with `scikit-survival` or `implicit` | Verify at T1 / T2 commit-1; pin windows chosen to be `scipy<1.13`-compatible; if conflict, escalate to DS/founder before relaxing | Re-pin; revert |
| Cox PH non-convergence on Beauty | REFUSED is the honest outcome (Pivot 5) | n/a — ModelCard surfaces status |
| ALS coverage collapse (everyone has the same K neighbors) | `coverage_at_10` diagnostic catches it; REFUSED | n/a |
| Survival / CF thresholds wrong | KI-NEW-P extension at T3; ≥3 beta merchants per stage at S14 = closure | thresholds live in `config/gate_calibration.yaml` — change → re-fit → re-pin |
| Determinism drift across runs | Fixed seed + hash-based holdout (mirrors S10-T1.4 time-based holdout discipline) | `test_determinism_cross_run.py` catches |
| Fixture re-pin (engine_run.json) collides with renderer changes | None expected — renderer doesn't read `predictive_models` (verified S10) | n/a |

---

## Part F — KI filing posture for S11 close

### KI-NEW-P extension (at S11-T3, NOT before) — v2 ~30 numbers total

Mirror the S10-T3 KI-NEW-P filing pattern. Current KI-NEW-P body (per the grep at KNOWN_ISSUES.md L455+) covers BG/NBD + Gamma-Gamma stage cells. S11-T3 extends with (v2 totals):

- **S10-carry (unchanged):** 4 stage rows × 4 BG/NBD metrics + 2 vertical month overrides; 4 stage rows × 2 G-G metrics (Spearman + agg_ratio band).
- **Survival stage cells (v2):** 4 stages × `{months_data_validated, repeat_customers_validated, events_validated, c_index_validated, holdout_brier_score_90d_validated_max}` = **5 metrics × 4 = 20 numbers** + 2 vertical-month overrides + `min_events_absolute_floor: 30` (theory-locked, NOT a stage cell).
- **CF stage cells (v2):** 4 stages × `{customers_floor, items_floor, interactions_per_customer_median_floor, recall_at_10_validated, coverage_at_10_validated}` = **5 metrics × 4 = 20 numbers** + ALS hyperparameters (literature-default, NOT in KI scope).
- **Sub-bullets** (verbatim text in T3 dispatch brief):
  - "Survival on flat replenishment-time distributions: c_index ≈ 0.5; REFUSED is expected, not a calibration issue."
  - "CF on sparse interaction matrices: recall@10 collapses to ~0; INSUFFICIENT_DATA is expected for stores below 50 customers OR <2 interactions/customer median."
  - "Beauty fixture survival + CF expected posture: PROVISIONAL or REFUSED. Real VALIDATED evidence at S14."
  - "Survival chained_bgnbd_refusal accounts for ≥80% of S11 synthetic outcomes (Option γ extends)."
  - **(NEW v2)** "Survival chained-refusal vs orthogonal-failure cases: BG/NBD VALIDATED + survival REFUSED is meaningful (Cox PH covariates don't add discriminative power on this merchant); BG/NBD REFUSED → survival REFUSED is chained and not a separate failure mode." (DS §(a).5)
  - **(NEW v2)** "CF cold-start band on Beauty + Supplements: expected REFUSED on synthetics per Option γ; real-merchant evidence at S14."

**Closure criterion (extension v2):** each stage cell needs ≥3 real beta merchants per stage with realized-vs-predicted ranking AND magnitude data (magnitude needed because Brier@90d gates).

**Out-of-scope for KI-NEW-P:** vertical-override `months_data` (theory-locked, same as S10-T3); `min_events_absolute_floor: 30` (theory-locked from DS verdict L119); ALS hyperparameters (literature-default; revisit only on real-merchant signal).

### KI-NEW-Q + KI-NEW-R — v2 surfacing posture

Per DS §(b).4 v2, KI-NEW-Q scope extends to `{lifetimes, scikit-survival, implicit}` maintenance posture; vendor-fork escape hatches documented (`scikit-survival` Cox PH ~1 day; `implicit` ALS ~3 days BLAS-bound). **Filing-vs-deferral remains founder-deferred** unless explicit ack at S11 close (surface as Part G Q7 v2 — new question). Same posture for KI-NEW-R.

### No new KIs at S11 close

S11 does not surface a new failure mode. Same audit-story shape as S10.

---

## Part G — Open questions for the founder (v2: Q1–Q6 CLOSED; Q7 NEW)

**v2 status summary (founder ack 2026-05-26 + DS verdict `agent_outputs/ds-architect-s11-plan-review.md` §(d)):**

| # | v1 question | v2 status |
|---|---|---|
| Q1 | CF scope (look-alikes only vs also product-affinity) | **CLOSED — look-alikes only** (DS §(d).Q1) |
| Q2 | Survival granularity (per-customer vs per-customer-per-SKU) | **CLOSED — per-customer only** (DS §(d).Q2; Pivot 5 + DS invariant 15) |
| Q3 | S11-T0 analog? | **CLOSED — no S11-T0** (DS §(d).Q3 audited `src/predictive/`, `src/main.py:971-1046`, `src/decide.py`, `src/guardrails.py`) |
| Q4 | DS sign-off on c_index + recall@10 thresholds | **CLOSED — DS-locked NOW** at §B.5 v2 (0.62/0.63 c_index, 0.25 Brier@90d) + §C.5 v2 ({0.05, 0.06, 0.08, 0.10} recall, 0.03 PROVISIONAL) |
| Q5 | ModelCard field-growth posture | **CLOSED — additive at S11** (3 new fields: `c_index`, `holdout_brier_score_90d`, `holdout_recall_at_10` + `coverage_at_10`). If S12 adds 3+ more, refactor to `Dict[str, float] metrics` shape (DS §(d).Q5) |
| Q6 | `lifelines` vs `scikit-survival` | **CLOSED — OVERRIDE to `scikit-survival`** (DS §(d).Q6) |
| Q7 (NEW v2) | File KI-NEW-Q + KI-NEW-R extensions at S11-T3 close? | **OPEN — founder-deferred per S10 pattern** unless explicit ack |

### Q1 — CF scope: customer look-alikes only, or also product-affinity? — CLOSED

**v2 verdict:** look-alikes only at S11. ALS factors reusable for product-affinity later without re-fitting. DS §(d).Q1 confirms.

DS §(d).Q1 verbatim: "CONFIRM look-alikes only." Item-side artifact can be added in a later sprint without re-fitting ALS. No founder action needed.

### Q2 — Survival: per-customer only, or per-customer-per-product? — CLOSED

**v2 verdict:** per-customer only. DS §(d).Q2 verbatim: "CONFIRM per-customer only. Per-SKU would require a new Tier-B builder, violating DS invariant 15." Pivot 5 + DS invariant 15. No founder action needed.

### Q3 — Is there an S11-T0 analog? — CLOSED

**v2 verdict:** no S11-T0. DS §(d).Q3 verbatim: "CONFIRM no S11-T0. Audited `src/predictive/`, `src/main.py:971-1046`, `src/decide.py`, `src/guardrails.py`; no correctness debt parallel to S10-T0." No founder action needed.

### Q4 — DS sign-off on c_index + recall@10 thresholds — CLOSED

**v2 verdict:** DS-locked NOW (not deferred to T1/T2 loops). DS §(d).Q4 verbatim:

> REVISE FLOORS NOW (do not defer): c_index VALIDATED 0.62/0.63 (not 0.65); PROVISIONAL 0.55; recall@10 VALIDATED {0.05, 0.06, 0.08, 0.10} per stage; PROVISIONAL 0.03. Add Brier@90d ≤ 0.25 as secondary survival gate. T1 dispatch brief carries these revised numbers verbatim.

All numbers landed in §B.5 v2 and §C.5 v2. No founder action needed.

### Q5 — `ModelCard` field-growth posture — CLOSED

**v2 verdict:** additive at S11 (3 new fields: `holdout_c_index`, `holdout_brier_score_90d`, `holdout_recall_at_10` + `coverage_at_10`). If S12 adds 3+ more optional fields, refactor to `Dict[str, float] metrics` shape at that point. DS §(d).Q5 confirms. Plan ahead; do not act at S11.

### Q6 — `lifelines` vs `scikit-survival` — CLOSED (OVERRIDE)

**v2 verdict:** use `scikit-survival`. DS §(d).Q6 verbatim:

> OVERRIDE: use `scikit-survival`. Full reasoning in §(b). The "ROADMAP consistency" / "maintainer-lineage continuity" arguments do not hold up — `lifelines` and `lifetimes` are separate packages with independent maintenance risk. `scikit-survival` is the modern, better-maintained Cox PH library. Zero refactor cost (no survival code exists yet). Update ROADMAP / DECISIONS.md text at S11-T3 close.

ROADMAP.md §1 L13 + §2 L42 verbatim updates queued at S11-T3 (Part D-T3). Founder ack received 2026-05-26.

### Q7 (NEW v2) — File KI-NEW-Q + KI-NEW-R extensions at S11-T3 close? — OPEN

Per DS §(b).4 v2, KI-NEW-Q scope extends to `{lifetimes, scikit-survival, implicit}` maintenance posture with vendor-fork escape hatches documented. Same posture for KI-NEW-R. S10 close left both founder-deferred.

**Founder decision needed at S11-T3 dispatch:** file the extensions at S11-T3 close, or continue founder-deferred posture through S14 (post-beta).

**Recommendation:** continue founder-deferred (same S10 pattern). The actual maintenance risk does not change between S11 close and S14 close; filing is administrative. If founder prefers to surface for tracking, file at S11-T3 with `Status: founder-acked, monitored, no closure criterion until S15+ AWS migration revisits dependency surface`.

---

## Part H — Files / functions affected (absolute paths)

### NEW

- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/survival.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/cf.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t1_survival_fit.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t1_threshold_loader.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t1_model_card.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t1_5_survival_rollback.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t2_cf_fit.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t2_threshold_loader.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t2_5_cf_rollback.py`
- `/Users/atul.jena/Projects/Personal/beaconai/data/<store_id>/predictive/survival.parquet` (per-store, runtime, VALIDATED/PROVISIONAL only)
- `/Users/atul.jena/Projects/Personal/beaconai/data/<store_id>/predictive/survival.model_card.json` (per-store, runtime, attempted-fit only)
- `/Users/atul.jena/Projects/Personal/beaconai/data/<store_id>/predictive/cf.parquet` (per-store, runtime, VALIDATED/PROVISIONAL only)
- `/Users/atul.jena/Projects/Personal/beaconai/data/<store_id>/predictive/cf.model_card.json`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s11-t1-summary.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s11-t1.5-summary.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s11-t2-summary.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s11-t2.5-summary.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s11-close-summary.md`

### MODIFIED

- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/model_card.py` — `ModelCard` additive fields (v2 — FOUR new optional fields total: `holdout_c_index`, **`holdout_brier_score_90d` (NEW v2)**, `holdout_recall_at_10`, `coverage_at_10`); `_load_model_fit_thresholds` extended for survival + cf blocks; fallback constants for both.
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` — verify `predictive_models: Dict[str, Any]` slot at L1006 round-trips the new entries (no schema change needed; `Any` envelope already accommodates per S10-T1 receipt §7 risk #4).
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` L1046+ — TWO new orchestration blocks (survival post-G-G; CF post-survival). Both guarded by respective flags, structurally identical to BG/NBD / G-G blocks at L971-L1046. Both write only to `engine_run.predictive_models`. NO edits to L1380-L1597 (KI-NEW-L is S13.5 — DO NOT TOUCH).
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` — 2 new flags (`ENGINE_V2_ML_SURVIVAL` at T1, `ENGINE_V2_ML_CF` at T2). BOTH added to the `_coerce` bool set at L1156 in the substrate ticket (T1 / T2 respectively), NOT at the atomic-flip ticket (S10-T1.5 lesson).
- `/Users/atul.jena/Projects/Personal/beaconai/requirements.txt` — **`scikit-survival>=0.22,<0.24` (v2)** at T1, `implicit==<pin>` at T2. `scipy<1.13` pin from S10 stays. `lifetimes==0.11.3` (S10) UNCHANGED — refactor deferred to S15+ per DS §(b).4.
- `/Users/atul.jena/Projects/Personal/beaconai/config/gate_calibration.yaml` — append `model_fit_thresholds.survival` block at T1 (§B.5 verbatim); append `model_fit_thresholds.cf` block at T2 (§C.5 verbatim).
- `/Users/atul.jena/Projects/Personal/beaconai/docs/engine_flags.md` — flag entries + ranking-strategy chain confirmation at T3; orthogonal-failure audit copy (v2); Beauty dormancy verbatim audit copy (v2).
- `/Users/atul.jena/Projects/Personal/beaconai/docs/DECISIONS.md` (v2 — NEW MODIFIED) — D-FLOOR-replenishment_due footnote: `scikit-survival` substitution rationale at T3.
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md` — KI-NEW-P extension at T3 (filed at sprint close, not earlier).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_determinism_cross_run.py` — `_NESTED_NORMALIZED_PATHS` extended at T1.5 (survival.fit_timestamp) and T2.5 (cf.fit_timestamp).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t1_5_bgnbd_rollback.py` — `_run_and_load` helper updated at T1.5 + T2.5 to set new flags `=false` for clean rollback assertions.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_v2_harness_cfg_gated_fields.py` — DS invariant 16 extension at T1 + T2 (harness test exercises new flag-gated producers).
- `/Users/atul.jena/Projects/Personal/beaconai/memory.md` — template-shape entries at each ticket close; sprint-close entry at T3.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/INDEX.md` — Sprint 11 section at T3.
- `/Users/atul.jena/Projects/Personal/beaconai/ROADMAP.md` — §1 + §2 row update at T3.
- `/Users/atul.jena/Projects/Personal/beaconai/STATE.md` — §4 light note at T3 (4 substrate models now present; dormant gate structure unchanged).

### UNCHANGED (load-bearing — DO NOT TOUCH)

- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py` — slate assembly, role-uniqueness, single-demote-channel invariant. No S11 changes.
- `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py` — `PSEUDO_N_BY_STATUS = {30,15,10}` locked through S14 per STATE.md §5 invariant 5.
- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py` — no MEASUREMENT-layer change.
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py:1380-1597` — five V2 prior-anchored injection blocks. KI-NEW-L is S13.5.
- `/Users/atul.jena/Projects/Personal/beaconai/src/guardrails.py` — single-demote-channel invariant authority. No S11 changes.
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml` — frozen.
- `/Users/atul.jena/Projects/Personal/beaconai/src/audience_builders.py` — five wired Tier-B builders unchanged; no new builder through S13 per DS invariant 15.
- Renderer surface (`src/render_briefing.py` / templates / `briefing.html`) — `predictive_models` never surfaced merchant-facing in S11 (operator-only).
- `PlayCard.predicted_segment` / `PlayCard.model_card_ref` stubs at `src/engine_run.py:837-838` — stay `None` at S11 close. S13 wires.
- `ReasonCode` enum at `src/engine_run.py:73` — S10-T3's `MODEL_FIT_*` additions are reused; no new codes at S11.
- `tests/test_reason_code_precedence_invariant.py` — precedence pin from S10-T3 covers survival + CF without modification (they route through the same ML-fit gate, lowest precedence).

---

## Part I — New artifacts produced at each stage

| Ticket | Artifact |
|---|---|
| T1 | `src/predictive/survival.py` (uses `scikit-survival` v2); survival block in `config/gate_calibration.yaml::model_fit_thresholds` (c_index 0.62/0.63 stage-keyed + Brier@90d 0.25 v2); `holdout_c_index` AND `holdout_brier_score_90d` (NEW v2) optional fields on `ModelCard`; `ENGINE_V2_ML_SURVIVAL` flag in DEFAULTS + `_coerce` bool set; survival threshold-loader extension. |
| T1.5 | `data/<store_id>/predictive/survival.parquet` (when VALIDATED/PROVISIONAL); `survival.model_card.json` mirror (when any fit attempted); `engine_run.predictive_models["survival"]` ModelCard surfaced operator-only; new survival-rollback test file. |
| T2 | `src/predictive/cf.py`; CF block in `config/gate_calibration.yaml::model_fit_thresholds`; `holdout_recall_at_10` + `coverage_at_10` optional fields on `ModelCard`; `ENGINE_V2_ML_CF` flag in DEFAULTS + `_coerce` bool set; CF threshold-loader extension. |
| T2.5 | `data/<store_id>/predictive/cf.parquet` (per-customer top-10 neighbors when VALIDATED/PROVISIONAL); `cf.model_card.json` mirror; `engine_run.predictive_models["cf"]` ModelCard surfaced; new CF-rollback test file. |
| T3 (CLOSE) | KI-NEW-P extended (survival + CF cells, ~30 numbers v2); `docs/engine_flags.md` ranking-strategy chain confirmation + orthogonal-failure copy + Beauty dormancy verbatim copy (v2); `docs/DECISIONS.md` D-FLOOR-replenishment_due footnote (v2); ROADMAP §1 L13 + §2 L42 `lifelines`→`scikit-survival` (v2); sprint-close memory.md entry; `agent_outputs/INDEX.md` S11 section; STATE light updates. |

---

## Part J — Feature flag strategy

| Flag | Lands | Default at land | Flips to ON | Rollback path |
|---|---|---|---|---|
| `ENGINE_V2_ML_SURVIVAL` | S11-T1 | `false` | S11-T1.5 (atomic) | env override `=false` reproduces pre-T1.5 sha |
| `ENGINE_V2_ML_CF` | S11-T2 | `false` | S11-T2.5 (atomic) | env override `=false` reproduces pre-T2.5 sha |

Both added to `_coerce` bool set at the substrate ticket (T1 / T2), not the flip ticket. Predecessor flag rollback tests updated at each flip (set new flag `=false` in their `_run_and_load` helpers).

No flag removed at S11. `RECENTLY_RUN_FATIGUE_ENABLED` stays OFF.

---

## Part K — Acceptance criteria summary (sprint-level)

| # | Criterion | Test home |
|---|---|---|
| 1 | Survival fits per merchant when `ENGINE_V2_ML_SURVIVAL` ON; ModelCard four-state populated correctly across BG/NBD chained-refusal × own-metric matrix | `tests/test_s11_t1_survival_fit.py` |
| 2 | Survival chains correctly: BG/NBD INSUFFICIENT_DATA → survival INSUFFICIENT_DATA (chained); BG/NBD REFUSED → survival REFUSED (chained); BG/NBD VALIDATED/PROVISIONAL → survival runs own fit | `tests/test_s11_t1_survival_fit.py::test_chained` |
| 3 | CF fits per merchant when `ENGINE_V2_ML_CF` ON; CF is INDEPENDENT of BG/NBD (runs to own four-state even when BG/NBD REFUSED) | `tests/test_s11_t2_cf_fit.py::test_independence` |
| 4 | All 5 pinned fixtures briefing.html byte-identical pre/post S11 (operator-only ML output) | `test_slate_regression_*` + `test_golden_diff` + `test_s8_t3_provenance` |
| 5 | Rollback contracts: `ENGINE_V2_ML_SURVIVAL=false` and `ENGINE_V2_ML_CF=false` reproduce pre-S11 shape exactly | `tests/test_s11_t1_5_survival_rollback.py`, `tests/test_s11_t2_5_cf_rollback.py` |
| 6 | Privacy: no per-customer scores in `engine_run.json`; only ModelCards. INSUFFICIENT_DATA writes neither parquet nor model_card.json | `tests/test_s10_privacy_envelope.py` extended at T1 + T2 |
| 7 | ReasonCode precedence (S10-T3) holds with survival + CF wired; ML-fit-only failure does NOT route to Considered | `tests/test_reason_code_precedence_invariant.py` (unchanged) |
| 8 | Determinism comparator handles 2 new fit_timestamps (survival, cf) | `tests/test_determinism_cross_run.py` |
| 9 | Both flags in `_coerce` bool set at substrate ticket, not flip ticket | `tests/test_s11_t1_survival_fit.py::test_flag_in_coerce_bool_set`, `tests/test_s11_t2_cf_fit.py::test_flag_in_coerce_bool_set` |
| 10 | Threshold loader resolves survival + CF stage cells + vertical-override (survival only) | `tests/test_s11_t1_threshold_loader.py`, `tests/test_s11_t2_threshold_loader.py` |
| 11 | ModelCard additive contract: 4 new optional fields v2 (`holdout_c_index`, `holdout_brier_score_90d`, `holdout_recall_at_10`, `coverage_at_10`) preserve `event_version=1` round-trip | `tests/test_s11_t1_model_card.py`, existing `test_engine_run_round_trip` |
| 15 (NEW v2) | Survival VALIDATED requires BOTH c_index ≥ stage-keyed floor AND Brier@90d ≤ 0.25 (dual-gate) | `tests/test_s11_t1_survival_fit.py::test_brier_secondary_gate` |
| 16 (NEW v2) | CF recall@10 stage-keyed VALIDATED floor {0.05, 0.06, 0.08, 0.10}; PROVISIONAL 0.03 | `tests/test_s11_t2_cf_fit.py::test_recall_floor_stage_keyed_v2` |
| 17 (NEW v2) | ROADMAP §1 L13 + §2 L42 verbatim text and `docs/DECISIONS.md` D-FLOOR-replenishment_due footnote updated at T3 (`lifelines` → `scikit-survival`) | doc grep at T3-CLOSE |
| 18 (NEW v2) | All S11 commit bodies carry `Deviation check: none.` (T1, T1.5, T2, T2.5, T3-CLOSE) | git log review at sprint close |
| 12 | DS invariant 16: harness-level test exercises every new flag-gated producer field with flag forced ON | `tests/test_v2_harness_cfg_gated_fields.py` extended |
| 13 | KI-NEW-P extended at S11-T3 with survival + CF stage cells | `KNOWN_ISSUES.md` review |
| 14 | Single-demote-channel invariant preserved: no append to `engine_run.recommendations` from S11 code | code review + `tests/test_s7_6_c1_priority_prepend_invariant.py` (unchanged) |

---

## Part L — Risks and rollback strategy

| Risk | Mitigation | Rollback |
|---|---|---|
| `lifelines` / `implicit` install fails on dev | CI smoke at T1/T2 commit-1; hard-pin versions | `pip uninstall …`; flag → `false` |
| `scipy<1.13` pin conflicts with new libraries | Verify at commit-1; escalate to DS/founder before relaxing | Revert pin attempt; keep `<1.13` |
| Synthetic fixtures all REFUSED / INSUFFICIENT_DATA | Pivot 5: this is honest, not a failure. Real VALIDATED at S14 | n/a — ModelCard surfaces status |
| Determinism drift across runs | Seeded fits + hash-based holdouts; new fit_timestamps normalized in comparator | `test_determinism_cross_run.py` catches; bisect |
| `_coerce` gap discovered at flip ticket (T1.5/T2.5 lesson regression) | Dispatch brief pins this requirement at substrate ticket (T1 / T2) | Re-dispatch T1 or T2 with patch |
| Survival / CF thresholds too lax → false VALIDATED on beta merchants | KI-NEW-P extension at T3; closure criterion = ≥3 merchants per stage; founder retune turn | thresholds live in YAML — change → re-fit → re-pin |
| Fixture re-pin races atomic flip | Single-commit pattern (S7.6 Risk #4) | Revert commit reverts both |
| Renderer accidentally consumes `predictive_models` | Grep at S11-T1.5: `grep -rn "predictive_models" src/render_*` returns nothing | If accidental consumption surfaces, revert + re-architect |
| ALS converges with degenerate top-K (one celebrity neighbor for all) | `coverage_at_10` diagnostic catches; REFUSED | n/a |
| CF parquet bloats disk (top-10 × all customers, large N) | Bounded by per-merchant N (10×customers rows); D-2 forever-retention acknowledged; AWS migration revisits | n/a |
| Survival on Beauty produces unexpected VALIDATED (signaling synthetic-fixture leak) | Surface in T1.5 receipt; flag for founder; KI-NEW-P sub-bullet | re-audit fixture shape if needed |
| Single-demote-channel violation slips in via orchestration block | Code review on dispatch brief; tests pin no `recommendations` writes from `src/predictive/*` | revert; redo with no `recommendations` touch |
| `ENGINE_V2_ML_GAMMA_GAMMA` orchestration block (S10-T2.5 L1003) shifts line numbers as survival/CF blocks land | Line ranges in receipts get out of date; reference function names, not line numbers, in dispatch briefs | n/a |
| KI-NEW-L (injection blocks at L1380-1597) accidentally edited | DO-NOT-TOUCH list in §H; pre-dispatch review | revert |

---

## Part M — What not to touch yet

- `src/decide.py` — no DECIDE-layer change at S11.
- `src/main.py:1380-1597` — five V2 prior-anchored injection blocks. KI-NEW-L is S13.5.
- `src/sizing.py` `PSEUDO_N_BY_STATUS` table — locked through S14.
- `src/measurement_builder.py` — no MEASUREMENT-layer change.
- `src/audience_builders.py` — five wired Tier-B builders + `replenishment_due` (dormant on Beauty per KI-NEW-G). No new builder through S13 per DS invariant 15.
- `src/guardrails.py` — single-demote-channel authority. No edits.
- `config/priors.yaml` — frozen.
- Renderer surface (`briefing.html` + templates) — `predictive_models` never surfaced merchant-facing in S11 (operator-only). The S10-T2.5 receipt §4 verified renderer does NOT read `predictive_models`.
- `PlayCard.predicted_segment` / `PlayCard.model_card_ref` stubs at `src/engine_run.py:837-838` — stay `None` at S11 close. S13 wires.
- `ReasonCode` enum — no new codes at S11.
- `KNOWN_ISSUES.md` — pre-dispatch S11 plan does NOT edit; KI-NEW-P extended at S11-T3 close. KI-NEW-Q / R deferred per founder.
- `memory.md` — entries only at ticket close, template-shape per CLAUDE.md rule.
- `PIVOTS.md` — no direction change at S11. (Same posture as S10-CLOSE §1 verbatim: "SKIP `PIVOTS.md` (DS: no direction change at S10 close).")
- `ARCHITECTURE_PLAN.md` — archived per Phase 2 cutover. Untouched.
- S10's PlayCard / ModelCard contracts — additive only (3 new optional ModelCard fields), no schema break.

---

## Part N — Summary of unclear / under-specified items (v2)

**v2: Q1–Q6 CLOSED (founder ack 2026-05-26 + DS verdict).** Remaining items:

1. **Q7 (NEW v2) — File KI-NEW-Q + KI-NEW-R extensions at S11-T3 close?** — founder-deferred posture recommended; surfaced at T3 dispatch for explicit ack.
2. **Beauty fixture survival + CF honest outcome unknown until fit runs** — accept whatever the metric returns (Pivot 5). T1.5 / T2.5 receipts pin the outcome. Option γ extends almost certainly. NEW v2: survival's dual gate (c_index + Brier@90d) makes VALIDATED on synthetics even less likely than v1 expected.

---

## Sources

Verbatim-quoted in plan body:
- `PRODUCT.md` §6 D-6 (banned ML use-cases); §5 beta posture month-1-wow / month-2-return.
- `STATE.md` §4 (three-active + one-dormant gates); §5 invariant 5 (`PSEUDO_N` lock); §7 L139 verbatim (`replenishment_due` honest dormancy on Beauty).
- `PIVOTS.md` Pivot 5 (synthetic-fixture honesty rule); Pivot 7 (single-demote-channel invariant); Pivot 8 (month-1-wow / month-2-return).
- `ROADMAP.md` §1 L13 verbatim (S11 anchor goals); §2 L42 verbatim (S11 row); §5 L100 verbatim (D-6 classical-only carve-out); §5 L102-103 verbatim (no cross-merchant pooling; PII posture).
- `KNOWN_ISSUES.md` KI-NEW-P (current body at L455+; S11-T3 extends with survival + CF cells); KI-NEW-Q / R deferred per founder.
- `agent_outputs/INDEX.md` Sprint 10 section.
- `agent_outputs/implementation-manager-s10-ml-part1-plan.md` — pattern parent; cadence mirror; threshold-loader schema precedent; `_FALLBACK_*` constant pattern; commit-pattern; risk catalog.
- `agent_outputs/ds-architect-s10-plan-review.md` — PASS-WITH-CHANGES pattern.
- `agent_outputs/ds-architect-s10-cold-start-and-eb-interaction.md` Part 5 L119 verbatim (survival cold-start <30 events = INSUFFICIENT_DATA; replenishment_due dormancy expected); Part 5 L121 verbatim (CF cold-start ~50×50 = INSUFFICIENT_DATA); Part 5 L123 verbatim (S13 ranking chain + month-2 return via EB).
- `agent_outputs/code-refactor-engineer-s10-t1-summary.md` §3 (Beauty fixture measurement: 3,844 repeat customers, 15,133 orders, 259 days); §7 risk #1 (library install discipline).
- `agent_outputs/code-refactor-engineer-s10-t2-summary.md` (BG/NBD-card-conditioned holdout pattern; reusable for survival).
- `agent_outputs/code-refactor-engineer-s10-t2.5-summary.md` §3 (chained-refusal pattern); §10 (risk catalog including determinism + rollback predecessor-test update); §"Patch summary" verbatim (`_coerce` bool set discipline — added at T2 pre-emptively per T1.5 lesson).
- `agent_outputs/code-refactor-engineer-s10-close-summary.md` §1 (sprint-close documentation pattern; SKIP PIVOTS / ARCHITECTURE_PLAN).
- `src/predictive/model_card.py` (docstring; `ModelFitStatus` four-value closed enum; `_load_model_fit_thresholds` pattern; `_FALLBACK_*` constants).
- `src/predictive/__init__.py` (package marker).
- `src/main.py` L971-L1046 (BG/NBD + G-G orchestration blocks — pattern for survival + CF insertion).
- `src/engine_run.py` L73 (`ReasonCode` enum); L837-838 (PlayCard stubs); L1006 (`predictive_models: Dict[str, Any]`).
- `src/utils.py` L848-877 (S10 flag-default pattern); L1156 (`_coerce` bool set).
- `config/gate_calibration.yaml` L470-518 (S10 `model_fit_thresholds.bgnbd` + `gamma_gamma` blocks — pattern for survival + CF append).
- `docs/engine_flags.md` L109-130 (S10 predictive-layer + ranking-strategy chain documentation).
- `CLAUDE.md` Subagent Handoff Discipline (L27-46); Documentation Discipline (L68-80); memory.md template-shape rule; single-demote-channel invariant.

*End of plan (v2 — DS-revised, dispatchable).*
