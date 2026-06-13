# Sprint 12 — ML Predictive Layer Part 3 (RFM + Retention Curves) — Implementation Plan

**Author:** implementation-manager
**Date:** 2026-05-28
**Branch baseline:** `post-6b-restructured-roadmap` (post-S11 close 2026-05-28)
**Status:** v2 — DS-revised, founder-acked 2026-05-28, dispatchable (per founder protocol — plan-only; code-refactor-engineer dispatch for S12-T1 pending orchestrator action)
**Supersedes:** none. Extends `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` Part B §"Sprint 12" with ticket-level detail.
**Parent active read path:** `PRODUCT.md`, `STATE.md`, `PIVOTS.md`, `ROADMAP.md`
**Pattern parent:** `agent_outputs/implementation-manager-s10-ml-part1-plan.md` (BG/NBD + G-G; atomic-flip cadence origin) and `agent_outputs/implementation-manager-s11-ml-part2-plan.md` v2 (survival + CF; DS-revised cadence).
**Discipline:** Subagent Handoff Discipline (`CLAUDE.md` L27-46); Documentation Discipline (`CLAUDE.md` L68-80); per-ticket loop is refactor → DS review → orchestrator commits+pushes → next ticket (founder-locked 2026-05-25); each refactor dispatch MUST require `agent_outputs/code-refactor-engineer-s12-<ticket>-summary.md`.

---

## REVISION HISTORY

```
REVISION HISTORY
- 2026-05-28 v1 — initial dispatch draft (RFM + retention curves; mirrors S10/S11 atomic-flip cadence; ModelCard refactor decision surfaced as Q-S12-1)
- 2026-05-28 v2 — RFM Spearman floors revised UP (0.50/0.55/0.60 → 0.60/0.65/0.70/0.70; PROVISIONAL 0.30 → 0.40); retention CI-width floors revised DOWN (0.30/0.25/0.20/0.20 → 0.25/0.20/0.15/0.15; PROVISIONAL 0.40 → 0.35); cumulative-retention-monotonicity-violation promoted to REFUSED gate; positive-control retention fixture required at T2; renderer-non-consumption grep pin at T1.5/T2.5; ModelCard refactor DEFERRED to S13-T0 (not S15+); KI-NEW-P sub-bullet must call out categorical-different closure shapes for RFM/retention vs ranker substrates. Per ds-architect-s12-plan-review.md and founder ack 2026-05-28.
```

---

## Part A — Scope clarification

### A.1 What S12 is

ROADMAP.md §1 verbatim (L13, post-S11 close):

> **Sprint 12 — ML Predictive Layer Part 3 (queued).** Next: statistical RFM + cohort retention curves with bootstrapped CIs. Not yet dispatched.

ROADMAP.md §2 verbatim (L43):

> | **S12** | ML Predictive Layer Part 3 — statistical RFM + cohort retention curves with bootstrapped CIs | yes — month-2 return surface |

Two substrates land at S12 close. Unlike S10/S11 the two are operationally **different shapes**:

1. **RFM** — per-customer ranking (deterministic Recency × Frequency × Monetary quintile segment). Sits at the AUDIENCE-layer `ranking_strategy` chain. Per `docs/engine_flags.md` L128 verbatim (S11-T3 close), the chain is `BG/NBD → CF → survival → RFM → recency`. **RFM is the explicit ML floor of the chain; recency is the absolute last-resort non-ML fallback** — RFM is therefore load-bearing for the S13 graceful-degradation contract.
2. **Retention curves** — cohort-level diagnostics (% of cohort retained at month 1/2/3/…, with bootstrapped CIs). **Not a per-customer ranker.** Operationally distinct from the other five predictive substrates.

Both ship flag-OFF land → atomic-flip cadence, mirroring S10's T1/T1.5 and S11's T1/T1.5/T2/T2.5 pattern.

PlayCard stubs `predicted_segment` and `model_card_ref` stay None at S12 close. ROADMAP.md §1 (post-S11 close) verbatim:

> PlayCard stubs `predicted_segment` and `model_card_ref` stay None at S11 close — S13 wires them.

S12 inherits that posture. S13 wires the consumers.

### A.2 Storage decision — RFM uses `predictive_models["rfm"]`; retention uses a NEW `cohort_diagnostics` slot — DECIDE PIN

**RFM** is shape-compatible with the existing `EngineRun.predictive_models: Dict[str, Any]` slot at `src/engine_run.py:1006`. Per-customer ranking; ModelCard with stage-keyed thresholds; parquet under `data/<store_id>/predictive/`. **Lands as `engine_run.predictive_models["rfm"]`.**

**Retention curves** are NOT per-customer rankings. They produce a cohort × month-since-acquisition matrix of retention rates with bootstrapped lower/upper CIs. Forcing them into `predictive_models["retention"]` would:
- Misrepresent the schema (a `ModelCard` slot whose contract was designed for per-customer ranking metric vocabulary — Spearman, C-index, recall@10 — would carry a single scalar like "median CI width" that doesn't map cleanly to those gates).
- Conflate two D-2/D-3 deletion semantics (per-customer parquet vs cohort-aggregate dict).
- Force the S13 ranking_strategy reader to special-case "retention" as a non-ranker entry in a Dict supposedly of rankers.

**Decision: NEW top-level slot `EngineRun.cohort_diagnostics: Dict[str, Any]`** (additive within `event_version=1`; same additive-precedent as `predictive_models` at S10). Retention curves land at `engine_run.cohort_diagnostics["retention"]`. The schema is forward-compatible with future cohort-level diagnostics (e.g., cohort AOV-evolution curves, cohort frequency-evolution curves) which will also not fit the ranker-style ModelCard contract.

**Note on ModelCard vs RetentionCard.** RFM gets a `ModelCard` (extended additive fields — see §E.1). Retention curves get a new **`RetentionCard`** dataclass with its own fields: `cohort_count`, `min_cohort_size`, `bootstrap_ci_width_at_month_3`, `bootstrap_iterations`, `fit_status: ModelFitStatus` (vocabulary reused — same four-state enum), `fit_warnings`, `fit_timestamp`. Reusing `ModelFitStatus` keeps the operator-readable status vocabulary uniform across all six predictive substrates without forcing the retention card into the ModelCard's ranker-metric shape.

### A.3 Chained refusal — both substrates are INDEPENDENT

**RFM is independent of BG/NBD / G-G / survival / CF.** RFM is deterministic segmentation on raw orders — Recency = days since last order, Frequency = order count in window, Monetary = total spend in window. No fit step. No probabilistic dependence on any other substrate. **RFM runs on its own four-state vocabulary on its own data shape.**

**Retention curves are independent of all five other substrates.** Cohort retention is computed on first-purchase-month cohorts directly from the orders frame. No dependence on any per-customer ranker.

**No new chained-refusal paths in S12.** This contrasts with S10's G-G chains BG/NBD and S11's survival chains BG/NBD. The S12 substrates are both first-principles cohort/segment statistics.

### A.4 Orchestration position

Today's predictive blocks land in `src/main.py` in this order (verified at L1048-L1155):

1. BG/NBD block (S10-T1.5).
2. Gamma-Gamma block (S10-T2.5; chains BG/NBD).
3. **Survival block (S11-T1.5; chains BG/NBD).** L1048-L1087.
4. **CF block (S11-T2.5; INDEPENDENT of BG/NBD).** L1089-L1155.
5. `apply_guardrails` (M5) at L1157+.

S12 inserts **two new blocks immediately after the CF block** (L1156, before guardrails):

```
... [existing CF block ends ~L1155]
[NEW S12-T1.5 RFM block — guarded by ENGINE_V2_ML_RFM — independent of all prior models]
[NEW S12-T2.5 retention curves block — guarded by ENGINE_V2_ML_RETENTION — independent of all prior models; writes to engine_run.cohort_diagnostics]
... [guardrails ~L1157]
```

Both new blocks write only to `engine_run.predictive_models` (RFM) or `engine_run.cohort_diagnostics` (retention); **neither writes to `engine_run.recommendations`** — single-demote-channel invariant (PIVOTS.md Pivot 7) preserved. No edits to `src/main.py:1380-1597` (KI-NEW-L is S13.5).

---

## Part B — RFM substrate spec

### B.1 What it models

**Unit of analysis: per customer.** One RFM segment label per customer per merchant per run. The three component scores:

- **Recency (R):** days since most recent order, computed over the primary observation window (default 365 days from `MAX(order_date)`).
- **Frequency (F):** total order count in the primary observation window.
- **Monetary (M):** total spend in the primary observation window.

Each component gets a quintile (1..5) via `pandas.qcut` with deterministic tie-breaking. Higher score = more recent / more frequent / more spend.

### B.2 Segment scheme — DECIDE: 11 named segments (NOT 125 raw 5×5×5 cells)

Two options were considered. **Decision: 11 named segments** (Champions, Loyal Customers, Potential Loyalists, New Customers, Promising, Need Attention, About to Sleep, At Risk, Cannot Lose Them, Hibernating, Lost). This is the canonical RFM scheme attributed to Putler / Arthur Hughes 1996; well-documented in DTC/CRM literature.

Justification:
1. **S13 consumer surface.** The S13 `ranking_strategy` fallback chain consumes a per-customer ordinal ranking. 11 named segments produce a coarse but interpretable ranking (Champions > Loyal > Potential Loyalists > … > Lost) that an audience builder can sort on cleanly. 125 raw cells produce per-customer noise that the audience builder would re-collapse anyway.
2. **Merchant-facing interpretability (future).** When the frontend renders ML-derived audience labels (post-Stop-Coding-Line; the swarm narrates), "Champions" / "At Risk" / "Hibernating" are human-readable. 125 raw cell IDs ("R5-F3-M2") are not.
3. **Stability vs noise.** Quintile cuts on small merchants (<200 customers) produce unstable raw cells but stable named segments because the named mapping aggregates over similar cells.
4. **Cold-start coverage.** Below 50 customers, raw quintile cuts collapse (DS verdict — `ds-architect-s10-cold-start-and-eb-interaction.md` Part 5 L121 verbatim: "RFM cold-start: <50 customers → INSUFFICIENT_DATA (quintile cuts collapse)"). Named segments degrade more gracefully on borderline-50-customer merchants because the segment-definition rule is RFM-band-based, not strict-quintile-based.

**The raw (R, F, M) quintile triplet is still surfaced** on the parquet (columns `r_score`, `f_score`, `m_score`) for operator inspection and forward compatibility (a later sprint could re-derive a different segmentation from the same triplet without re-fitting).

**Q-S12-A (founder)** — confirm named-segments scheme over raw 125-cell. If founder prefers raw, the parquet schema in §B.7 is unchanged and only the `segment_label` column derivation rule changes.

### B.3 Library — DECIDE: custom code (`pandas.qcut` + a 30-line segment-mapping table). NO third-party RFM library.

Justification:
1. **`lifetimes` does not provide RFM segmentation** — only BG/NBD / Gamma-Gamma probabilistic models. (`lifetimes.utils.summary_data_from_transaction_data` produces frequency/recency/T inputs to BG/NBD but does not return RFM segments.)
2. **No mature peer-reviewed-classical RFM-segmentation library exists in PyPI** comparable to `lifetimes` / `scikit-survival` / `implicit`. The math is `pd.qcut` plus a band-mapping dict; <200 lines total. Vendor-fork cost for a hypothetical RFM library would be smaller than the integration cost — zero net benefit to a library dependency.
3. **D-6 compliance** (PRODUCT.md L96 verbatim): "ML models EXPLICITLY BANNED for the planning horizon: quiz contextual bandits (LinUCB/Thompson), VIP/loyalty tier optimization, …" — RFM is classical statistics, not the banned VIP/loyalty optimization. Custom code keeps the math fully auditable.
4. **No new third-party dependency** → KI-NEW-R (3-library vendor-fork escape hatch) does NOT extend to a fourth library at S12. Maintenance posture improves.

**Implementation surface:** `src/predictive/rfm.py` (~150-200 lines) with two public functions:

- `fit_rfm(orders_df, profile, *, store_id, data_dir, thresholds: dict) -> ModelCard` — produces the ModelCard with stage-keyed thresholds + writes parquet on VALIDATED/PROVISIONAL.
- (private) `_assign_named_segment(r_score, f_score, m_score) -> str` — the 11-segment mapping.

### B.4 Validation metric — DECIDE: dual-gate (segment monotonicity on historical-LTV AND quintile coverage)

**RFM has no fit step.** It's deterministic segmentation. So "good fit" is not a likelihood / convergence story. Instead, it's a **validity-of-segmentation** story.

**PRIMARY gating metric (DS-LOCKED 2026-05-28): segment monotonicity on observed historical LTV.**

After segmentation, compute observed mean revenue-per-customer (over the same observation window) per named segment. The segments have a canonical ordering: Champions > Loyal Customers > Potential Loyalists > New Customers > Promising > Need Attention > About to Sleep > At Risk > Cannot Lose Them (tie/edge case) > Hibernating > Lost. **VALIDATED requires Spearman rank correlation between segment-order and observed-mean-revenue ≥ stage-keyed floor (0.60/0.65/0.70/0.70 across startup/growth/mature/enterprise — see §B.5; DS-revised UP from v1's 0.50/0.55/0.60).** If higher-RFM segments don't have higher observed revenue, the segmentation has failed to capture economically-meaningful structure on this merchant.

**Rationale for v2 upward revision (per `agent_outputs/ds-architect-s12-plan-review.md` §F verbatim):** "RFM is the **explicit ML floor of the ranking chain**. If the floor itself has weak monotonicity, the chain's degradation surface is misleading." Spearman 0.50 is barely-better-than-random ordinal agreement on a deterministic segmentation; should not VALIDATE on the chain floor. The new floors leave noise headroom at startup (0.60) and reflect the expectation that a $1M+ ARR brand with 500+ customers should have very strong F-vs-M monotonicity (0.70 at mature/enterprise).

Why this metric is operationally honest:
- It mirrors the S10 BG/NBD pattern of gating on the same ordinal-ranking question the S13 consumer asks (`holdout_rank_spearman` for BG/NBD; segment-order-vs-observed-revenue for RFM).
- It's testable on a deterministic positive-control synthetic (e.g., construct a population where higher-frequency customers genuinely have higher revenue and assert Spearman ≈ 1.0 — analogous to S11-T1's c-index=0.838 positive control and S11-T2's recall@10=0.344 positive control).

**SECONDARY REFUSED guard (DS-LOCKED 2026-05-28): quintile coverage.**

Surfaces a degenerate-quintile failure: if `pd.qcut` collapses (e.g., 90% of customers have F=1 so the F-quintile cuts to 1 or 2 bins), the segmentation is noise. Surface as `quintile_coverage_min` on the ModelCard — the smallest fraction of customers in any of the 5 R-, F-, or M-bins. **A REFUSED rule fires when `quintile_coverage_min < 0.05`** (any one bin holds <5% of customers — quintile has collapsed).

**Tertiary diagnostic (does NOT gate, operator-visible only): inter-quintile separation via Mann-Whitney U on adjacent named segments.** DS APPROVE (`ds-architect-s12-plan-review.md` §F): useful for surfacing adjacent-segment collapse in operator inspection.

**DS sign-off status:** **CLOSED — DS-LOCKED 2026-05-28** per `agent_outputs/ds-architect-s12-plan-review.md` §F. Q-S12-B closed; thresholds locked per §B.5 below.

### B.5 Business-stage-keyed thresholds (DS-LOCKED 2026-05-28)

Mirror the existing `config/gate_calibration.yaml::model_fit_thresholds.<model>` block shape from `bgnbd` / `gamma_gamma` / `survival` / `cf`. Schema to append (locked per `agent_outputs/ds-architect-s12-plan-review.md` §F):

```yaml
model_fit_thresholds:
  # ... (existing bgnbd, gamma_gamma, survival, cf blocks unchanged)
  rfm:
    by_business_stage:
      startup:    {n_customers_validated: 50,   segment_monotonicity_spearman_validated: 0.60, quintile_coverage_min_validated: 0.10}
      growth:     {n_customers_validated: 200,  segment_monotonicity_spearman_validated: 0.65, quintile_coverage_min_validated: 0.10}
      mature:     {n_customers_validated: 500,  segment_monotonicity_spearman_validated: 0.70, quintile_coverage_min_validated: 0.10}
      enterprise: {n_customers_validated: 1000, segment_monotonicity_spearman_validated: 0.70, quintile_coverage_min_validated: 0.10}
    relaxation_factors:
      provisional_n_multiplier: 0.5
      provisional_segment_monotonicity_spearman_floor: 0.40
      provisional_quintile_coverage_min_floor: 0.05
    absolute_customers_floor: 50                # DS L121 "<50 customers → INSUFFICIENT_DATA"
    refused_quintile_coverage_min: 0.05         # REFUSED secondary guard
```

Lock posture (DS-LOCKED):
- `absolute_customers_floor: 50` is **DS-locked** from `ds-architect-s10-cold-start-and-eb-interaction.md` Part 5 L121 verbatim: "RFM cold-start: <50 customers → INSUFFICIENT_DATA (quintile cuts collapse)". Do not relax.
- Spearman floors (0.60/0.65/0.70/0.70) and PROVISIONAL floor (0.40) are **DS-locked 2026-05-28** per `ds-architect-s12-plan-review.md` §F (revised UP from v1's 0.50/0.55/0.60 and 0.30). Speculative-until-S14 closure under KI-NEW-P remains — DS-locked at fit-time, real-merchant calibration at S14.
- `quintile_coverage_min_validated: 0.10` and `refused_quintile_coverage_min: 0.05` DS-approved per §F.
- Renamed `customers_validated` → `n_customers_validated` for naming parity with ModelCard field shape per DS-locked schema.

### B.6 Four-state classifier mapping

- **VALIDATED** — `n_customers ≥ n_customers_validated` (stage-keyed); `segment_monotonicity_spearman ≥ segment_monotonicity_spearman_validated` AND `quintile_coverage_min ≥ quintile_coverage_min_validated`; no warnings.
- **PROVISIONAL** — `n_customers` between `absolute_customers_floor` and `n_customers_validated`; OR `segment_monotonicity_spearman` between `provisional_segment_monotonicity_spearman_floor=0.40` and `segment_monotonicity_spearman_validated`; OR `quintile_coverage_min` between `provisional_quintile_coverage_min_floor=0.05` and `quintile_coverage_min_validated`. Ranking usable (S13 consumes); absolute segment-label semantics not quotable to merchant.
- **INSUFFICIENT_DATA** — `n_customers < absolute_customers_floor=50`. Engine declines to fit. No parquet.
- **REFUSED** — `n_customers ≥ 50` (cleared the floor) but `segment_monotonicity_spearman < 0.40` (segmentation captures no economic signal — DS-revised UP from 0.30) OR `quintile_coverage_min < refused_quintile_coverage_min=0.05` (quintile collapsed despite N≥50). ModelCard with `fit_warnings`, no parquet.

### B.7 Parquet schema

`data/<store_id>/predictive/rfm.parquet` — written only when `fit_status ∈ {VALIDATED, PROVISIONAL}`. **Per-customer** segment label + raw scores. Columns:

| Column | Type | Notes |
|---|---|---|
| `customer_id` | str | D-2 / D-3 wipe-unit; same key as BG/NBD / G-G / survival / CF parquets. |
| `r_score` | int | 1..5 quintile (5 = most recent). |
| `f_score` | int | 1..5 quintile (5 = most frequent). |
| `m_score` | int | 1..5 quintile (5 = highest monetary). |
| `recency_days` | float | Raw days since last order. |
| `frequency_window` | int | Raw order count in observation window. |
| `monetary_window` | float | Raw spend in observation window. |
| `segment_label` | str | One of the 11 named segments. |
| `parquet_schema_version` | int | Pinned `1` at S12-T1. |

D-2/D-3 deletion semantics: parquet lives under `data/<store_id>/predictive/` — already the wipe-unit. No new directory boundary. INSUFFICIENT_DATA / REFUSED → no parquet (deletion is a no-op).

PII posture: `customer_id` only — no name, email. Per ROADMAP §5 L103 verbatim ("No PII in predictive artifacts. `customer_id` only.") preserved.

### B.8 D-2/D-3 deletion semantics

Same as S10/S11 substrates: per-store data dir cleanup subsumes (`data/<store_id>/predictive/` is the wipe unit). No new boundary.

---

## Part C — Retention curves spec

### C.1 What it models

**Unit of analysis: per cohort × month-since-acquisition.** Output is a matrix:

| `cohort` (first-purchase month) | `months_since_acquisition` | `retention_rate` | `ci_lower_95` | `ci_upper_95` | `n_cohort` |
|---|---|---|---|---|---|
| 2025-06 | 1 | 0.42 | 0.36 | 0.48 | 180 |
| 2025-06 | 2 | 0.31 | 0.26 | 0.37 | 180 |
| … | … | … | … | … | … |

**Retention rate** at month M = (count of cohort customers who placed ≥1 order between months [M-1, M] of their first purchase) / (count of cohort customers).

**Bootstrapped 95% CIs** via numpy bootstrap (`n_bootstrap=1000` default; pinned at S12-T1). Resample cohort customers with replacement; recompute retention rate per resample; take 2.5/97.5 percentiles of the bootstrap distribution.

### C.2 Library — DECIDE: custom code (numpy + pandas; ~100 lines). NO third-party library.

Three options were considered:

1. **`lifelines.KaplanMeierFitter`** — would compute survival functions per cohort. **REJECT.** Two reasons: (a) `lifelines` is not currently a dependency (S11 explicitly chose `scikit-survival` over `lifelines` per DS verdict — see `agent_outputs/ds-architect-s11-plan-review.md` §(b)). Adding `lifelines` at S12 reopens that decision. (b) Kaplan-Meier produces a continuous-time survival function; cohort retention is **discrete monthly** by design (months-since-acquisition, not days). KM forces a continuous-time semantics on a discrete-time question; the conversion adds noise without adding signal.

2. **`scikit-survival`** (already a dependency from S11) — same KM functionality. **REJECT** for the same discrete-vs-continuous reason. `scikit-survival` is designed for right-censored continuous-time survival, not cohort retention curves.

3. **Custom code** — empirical monthly retention computation + numpy bootstrap. ~100 lines. **CHOSEN.**

Justification (matches §B.3 rationale for RFM):
- The math is `groupby(cohort, months_since)` + `mean(churned_or_active)` + numpy bootstrap. Straightforward.
- No new third-party dependency → KI-NEW-R does not extend.
- Discrete-monthly semantics matches the operational question ("of customers who first bought in June 2025, what fraction returned in month 1, month 2, …").
- D-6 compliance trivial (classical statistics, not banned ML).

**Implementation surface:** `src/predictive/retention.py` (~100-150 lines) with one public function:

- `fit_retention(orders_df, profile, *, store_id, data_dir, thresholds: dict, seed: int = 0) -> RetentionCard` — produces the RetentionCard (new dataclass; see §A.2) and writes a cohort-aggregate JSON artifact (NOT a per-customer parquet — see §C.7).

### C.3 Cohort definition

**Cohort = first-purchase calendar month.** Customer X who placed first order on 2025-06-14 belongs to cohort `2025-06`. Cohort retention at month M = fraction of cohort with ≥1 order in `[first_order_date + (M-1)*30d, first_order_date + M*30d]`.

**Cohort window — stage-keyed** (see §C.5): startup looks at the last 6 cohorts; growth/mature/enterprise at the last 12 cohorts. Older cohorts are truncated to keep the diagnostic recent.

**Months-since-acquisition cap — pinned at 12 months** (the natural retention-curve horizon for DTC). Beyond month 12 the curve is computationally cheap to extend, but for the S13 month-2-return wow surface, the first 6-12 months carry the information.

**Berkson-style confound protection.** Per S6.5 (`agent_outputs/code-refactor-engineer-phase4_1-summary.md`-style precedent) and the resolved KI on `journey_optimization` cross-period cohorts (`memory.md` 2026-04-30): cohort definitions on first-purchase month avoid the early-half / late-half cross-period bias that bit `journey_optimization`. Retention curves use the same early-cohort-only logic — only customers whose first purchase falls in the cohort window are counted in the cohort denominator; later customers don't pollute it.

### C.4 Validation metric — DS-LOCKED: dual-gate (cohort count AND bootstrap CI width) + cumulative-monotonicity REFUSED guard

**PRIMARY gating metric (DS-LOCKED 2026-05-28): bootstrap CI width at month 3.**

Operational question: "Is the retention curve informative enough to publish?" Wide CIs at month 3 (the canonical first-look retention checkpoint for DTC) mean the cohorts are too small / too noisy. VALIDATED requires `bootstrap_ci_width_at_month_3 ≤ stage_keyed_floor` (DS-revised DOWN: 0.15 for mature/enterprise — see §C.5).

**SECONDARY gating metric (DS-LOCKED): cohort count.**

DS verdict `ds-architect-s10-cold-start-and-eb-interaction.md` Part 5 L121 verbatim: "Retention curves: <3 cohorts → INSUFFICIENT_DATA." Three is the absolute floor (you need at least 3 cohorts to see retention-curve *variation*, not a single curve). VALIDATED requires `cohort_count ≥ 6` (stage-keyed; 6 for startup, 12 for growth/mature/enterprise — see §C.5).

**Gate composition (DS-LOCKED):** AND, not OR. Per `ds-architect-s12-plan-review.md` §G verbatim: "CI-width without cohort_count is statistical artifact; cohort_count without CI-width is shape-only. Both are necessary."

**REFUSED guard (NEW, DS-PROMOTED 2026-05-28): cumulative-retention monotonicity violation.**

Cumulative retention defined as "% ever returned in [0, M]" **cannot mathematically rise** as M increases. A cumulative-retention monotonicity violation indicates a data-shape bug or cohort-definition error — surface as REFUSED, not diagnostic-only.

Per `ds-architect-s12-plan-review.md` §G verbatim: "DS revises: monotonicity violation in CUMULATIVE retention is a REFUSED condition (it indicates a data-shape bug or cohort-definition error — retention cannot mathematically rise in the cumulative definition)."

Surface as `cumulative_retention_monotonicity_violation: bool` on the RetentionCard. When True → fit_status = REFUSED with warning `cumulative_retention_monotonicity_violation`.

**Tertiary diagnostic (does NOT gate, DS-confirmed): period-retention monotonicity.**

Period-based retention ("active in (M-1, M]") can be non-monotone but should not invert dramatically. Surface as `period_retention_inversion_count` on the RetentionCard — count of cohorts where period-retention rises >10pp month-to-month. Operator-visible only; does not gate.

**POSITIVE-CONTROL FIXTURE REQUIREMENT (NEW, DS-REQUIRED 2026-05-28):** Per `ds-architect-s12-plan-review.md` §K verbatim: "add a deterministic positive-control fixture (e.g., 12 monthly cohorts of 200 customers each with stable 40% month-1 retention by construction) and assert `bootstrap_ci_width_at_month_3 < 0.10` + `cumulative_retention_monotonicity_violation == False`. Mirrors S11-T1 c-index positive control. Required for T2 acceptance." See T2 acceptance criteria below.

**DS sign-off status:** **CLOSED — DS-LOCKED 2026-05-28** per `agent_outputs/ds-architect-s12-plan-review.md` §G. Q-S12-C closed.

### C.5 Business-stage-keyed thresholds (DS-LOCKED 2026-05-28)

```yaml
model_fit_thresholds:
  # ... (existing rfm block above)
  retention:
    by_business_stage:
      startup:    {cohort_count_validated: 6,  bootstrap_ci_width_at_month_3_max_validated: 0.25}
      growth:     {cohort_count_validated: 12, bootstrap_ci_width_at_month_3_max_validated: 0.20}
      mature:     {cohort_count_validated: 12, bootstrap_ci_width_at_month_3_max_validated: 0.15}
      enterprise: {cohort_count_validated: 12, bootstrap_ci_width_at_month_3_max_validated: 0.15}
    relaxation_factors:
      provisional_n_multiplier: 0.5
      provisional_bootstrap_ci_width_at_month_3_max: 0.35
    absolute_cohort_count_floor: 3              # DS L121 "<3 cohorts → INSUFFICIENT_DATA"
    bootstrap_iterations: 1000
    months_horizon: 12
    min_cohort_size_floor: 20                   # cohort with <20 customers is dropped from the diagnostic
    cumulative_retention_monotonicity_violation_refused: true   # DS-PROMOTED 2026-05-28 (§C.4)
```

Lock posture (DS-LOCKED):
- `absolute_cohort_count_floor: 3` is **DS-locked** from `ds-architect-s10-cold-start-and-eb-interaction.md` Part 5 L121.
- CI-width floors (0.25/0.20/0.15/0.15) and PROVISIONAL ceiling (0.35) are **DS-locked 2026-05-28** per `ds-architect-s12-plan-review.md` §G (revised DOWN from v1's 0.30/0.25/0.20/0.20 and 0.40). Rationale: "A 30pp band on a quantity that itself is typically 20-50% is not informative for ranking purposes. A mature DTC merchant with 12 cohorts of 50+ customers each should comfortably hit ≤0.15 CI width."
- `bootstrap_iterations: 1000` DS APPROVE (§G).
- `months_horizon: 12` DS APPROVE (§G).
- `min_cohort_size_floor: 20` DS APPROVE (§G).
- `cumulative_retention_monotonicity_violation_refused: true` — DS-PROMOTED to REFUSED (§C.4, §G).
- All CI-width floors remain **speculative-until-S14** under KI-NEW-P closure; DS-locked at fit-time.

### C.6 Four-state classifier mapping

- **VALIDATED** — `cohort_count ≥ cohort_count_validated` AND `bootstrap_ci_width_at_month_3 ≤ bootstrap_ci_width_at_month_3_max_validated` AND `cumulative_retention_monotonicity_violation == False`; no warnings.
- **PROVISIONAL** — `cohort_count` between `absolute_cohort_count_floor` and `cohort_count_validated`; OR `bootstrap_ci_width_at_month_3` between `bootstrap_ci_width_at_month_3_max_validated` and `provisional_bootstrap_ci_width_at_month_3_max=0.35`. Diagnostic surfaced with caveat band. (Cumulative-monotonicity must still hold; violation routes to REFUSED.)
- **INSUFFICIENT_DATA** — `cohort_count < 3`. Engine declines to compute. No artifact.
- **REFUSED** — `cohort_count ≥ 3` (cleared floor) AND any of:
  - `bootstrap_ci_width_at_month_3 > 0.35` (CIs too wide despite enough cohorts — DS-revised DOWN from 0.40);
  - `cumulative_retention_monotonicity_violation == True` (DS-PROMOTED 2026-05-28 from tertiary-diagnostic to REFUSED — cumulative retention mathematically cannot rise; violation = data-shape bug or cohort-definition error).
  RetentionCard with `fit_warnings`, no artifact.

### C.7 Storage — `engine_run.cohort_diagnostics["retention"]` + JSON artifact (NOT parquet)

Retention output is **cohort-aggregate**, not per-customer. The natural storage shape is a small JSON dict embedded in `engine_run.cohort_diagnostics["retention"]` (the new top-level slot from §A.2):

```json
{
  "cohort_diagnostics": {
    "retention": {
      "fit_status": "VALIDATED",
      "cohort_count": 12,
      "min_cohort_size": 47,
      "bootstrap_ci_width_at_month_3": 0.18,
      "bootstrap_iterations": 1000,
      "fit_warnings": [],
      "curves": [
        {"cohort": "2025-06", "month": 1, "retention_rate": 0.42, "ci_lower_95": 0.36, "ci_upper_95": 0.48, "n_cohort": 180},
        {"cohort": "2025-06", "month": 2, "retention_rate": 0.31, "ci_lower_95": 0.26, "ci_upper_95": 0.37, "n_cohort": 180},
        ...
      ],
      "fit_timestamp": "2026-05-28T15:30:00Z"
    }
  }
}
```

For VALIDATED/PROVISIONAL fits, **also write a sidecar JSON** to `data/<store_id>/predictive/retention.json` mirroring the same shape. This matches the `model_card.json` mirror precedent S10/S11 established (operator-only artifact for direct inspection without parsing the full `engine_run.json`).

**No parquet for retention.** Cohort-aggregate ≤200 rows per merchant (12 cohorts × 12 months max). JSON is the right shape; parquet is overkill.

D-2/D-3 deletion semantics: `data/<store_id>/predictive/retention.json` lives under the existing wipe unit. INSUFFICIENT_DATA → no artifact. REFUSED → RetentionCard surfaces with `fit_warnings` but no `retention.json` sidecar.

### C.8 Chained refusal

**Retention curves are INDEPENDENT** of all five other substrates (BG/NBD / G-G / survival / CF / RFM). Cohort retention is computed directly from the orders frame; no probabilistic dependence on a per-customer ranker. Confirmed §A.3.

---

## Part D — Ticket decomposition

S12 follows the S10/S11 atomic-flip cadence. **Five tickets** (T1, T1.5, T2, T2.5, T3-CLOSE), ~15 commits, two atomic flips. Each ticket's refactor dispatch brief MUST include the path `agent_outputs/code-refactor-engineer-s12-<ticket>-summary.md` per founder protocol (locked 2026-05-25, CLAUDE.md Subagent Handoff Discipline). Per-ticket loop: refactor → DS review → orchestrator commits+pushes → next ticket. Each commit body MUST carry `Deviation check: none.` (per S11 v2 §P precedent).

**No S12-T0 lineage-fatigue analog.** Audited at plan-draft time: no latent correctness debt parallels to S10-T0's lineage-keyed fatigue bug. Greenfield substrate. (Mirrors S11 §G Q3 → DS-confirmed.) See Part G Q-S12-D.

### S12-T1 — RFM substrate + ModelCard wiring + stage-keyed thresholds (FLAG OFF)

**Scope:**
- New `src/predictive/rfm.py`:
  - `fit_rfm(orders_df, profile, *, store_id, data_dir, thresholds: dict) -> ModelCard`
  - `_assign_named_segment(r_score, f_score, m_score) -> str` private — 11-segment mapping table.
  - Cold-start guard returns ModelCard with `fit_status=INSUFFICIENT_DATA` when `n_customers < absolute_customers_floor=50`.
  - Quintile-collapse guard returns REFUSED when `quintile_coverage_min < 0.05`.
  - Segment-monotonicity computation (Spearman against observed mean revenue per segment).
  - Parquet writer to `data/<store_id>/predictive/rfm.parquet` when status ∈ {VALIDATED, PROVISIONAL}.
- Extend `src/predictive/model_card.py::_load_model_fit_thresholds` to read `model_fit_thresholds.rfm` block. Add `_FALLBACK_RFM_STAGE_CELL` + `_FALLBACK_RFM_RELAXATION` constants mirroring `_FALLBACK_CF_*` shape at L261-278.
- Append `model_fit_thresholds.rfm` block to `config/gate_calibration.yaml` (§B.5 verbatim schema).
- New flag `ENGINE_V2_ML_RFM` in `src/utils.py` `DEFAULTS` table, default `"false"`. **CRITICAL — T1.5 lesson:** add `ENGINE_V2_ML_RFM` to the `_coerce` bool set IN T1 (not T1.5).
- ModelCard additive fields (see Part E.1 — IF the field-count refactor lands first per Q-S12-1; otherwise additive fields):
  - `segment_monotonicity_spearman: Optional[float] = None`
  - `quintile_coverage_min: Optional[float] = None`
- NO library install. No `requirements.txt` edit (custom code only).

**Acceptance criteria (T1):**
- `fit_rfm` returns ModelCard with correct four-state classification across the (`n_customers`, `monotonicity_spearman`, `quintile_coverage_min`) decision matrix.
- Cold-start (<50 customers) → INSUFFICIENT_DATA; no parquet written.
- Degenerate quintile → REFUSED with `quintile_coverage_collapsed` warning; no parquet.
- Positive-control synthetic (population where higher-frequency genuinely has higher revenue) → VALIDATED with `segment_monotonicity_spearman > 0.80`. **Mirrors S11-T1 Cox PH c=0.838 positive control and S11-T2 ALS recall@10=0.344 positive control.**
- Flag OFF → engine output byte-identical to pre-T1; all 5 pinned fixtures (`tests/fixtures/synthetic_slate/healthy_beauty_240d_*`, `healthy_supplements_240d_*`, etc.) round-trip unchanged.
- `_coerce` bool set contains `ENGINE_V2_ML_RFM` (pinned by `tests/test_s12_t1_rfm_fit.py::test_flag_in_coerce_bool_set`).
- Stage-keyed thresholds match DS-locked §B.5 (`n_customers_validated` ∈ {50,200,500,1000}; `segment_monotonicity_spearman_validated` ∈ {0.60,0.65,0.70,0.70}; PROVISIONAL Spearman floor = 0.40).
- Commit body carries `Deviation check: none.`

**Files touched (NEW):**
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/rfm.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t1_rfm_fit.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t1_threshold_loader_rfm.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t1_model_card_additive.py`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t1-summary.md`

**Files touched (MODIFIED):**
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/model_card.py` — RFM threshold loader extension + additive ModelCard fields (or `metrics: Dict[str, float]` refactor — see Q-S12-1).
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` — `ENGINE_V2_ML_RFM` flag + `_coerce` bool set.
- `/Users/atul.jena/Projects/Personal/beaconai/config/gate_calibration.yaml` — RFM block append.

**Expected outcome (Pivot 5):** see Part E.5 — synthetics likely VALIDATE on RFM (first substrate to plausibly do so).

### S12-T1.5 — RFM atomic flip + orchestration wire + rollback test

**Scope:**
- New orchestration block in `src/main.py` immediately after the CF block (~L1156, before guardrails). Mirrors the structural pattern of L1063-L1087 (survival) / L1115-L1155 (CF) — try/except wrapper, flag-gated, writes only to `engine_run.predictive_models["rfm"]`.
- Flip `ENGINE_V2_ML_RFM` default from `"false"` to `"true"` in `src/utils.py:DEFAULTS`.
- Atomic-flip discipline: orchestration wire + flag flip + any fixture re-pin in a single commit (the S7.6 risk #4 lesson — Risk #6 in S11 plan).
- Determinism comparator extension: `_NESTED_NORMALIZED_PATHS` in `tests/test_determinism_cross_run.py` extended with the new `rfm.fit_timestamp` path.
- Predecessor rollback-test updates: `tests/test_s10_t1_5_bgnbd_rollback.py`, `tests/test_s11_t1_5_survival_rollback.py`, `tests/test_s11_t2_5_cf_rollback.py` — `_run_and_load` helpers set `ENGINE_V2_ML_RFM=false` for clean rollback assertions.
- NEW rollback test: `tests/test_s12_t1_5_rfm_rollback.py` — pins that `ENGINE_V2_ML_RFM=false` reproduces pre-T1.5 sha exactly.

**Acceptance criteria (T1.5):**
- All 5 pinned fixtures' `briefing.html` byte-identical pre/post T1.5 flip (RFM is operator-only via `engine_run.predictive_models["rfm"]`; renderer does NOT consume).
- `engine_run.predictive_models["rfm"]` ModelCard populated on all 5 fixtures with status reflecting the actual fit.
- Rollback contract: `ENGINE_V2_ML_RFM=false` reproduces pre-T1.5 engine_run.json (`predictive_models["rfm"]` absent).
- Privacy envelope test extended: no per-customer RFM scores in `engine_run.json`; only ModelCard and parquet.
- All four predecessor rollback tests still pass with the new flag wired into their `_run_and_load` helpers.
- **Renderer non-consumption grep pin (NEW, DS-REQUIRED 2026-05-28):** `grep -rn "predictive_models\|cohort_diagnostics" src/render_*` returns empty. Confirms renderer does NOT consume either field; briefing.html byte-identity holds by construction. Pinned per `ds-architect-s12-plan-review.md` §K.
- Commit body carries `Deviation check: none.` (per S11 v2 §P precedent).

**Files touched (MODIFIED):**
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` (orchestration block ~L1156).
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` (flag default flip).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_determinism_cross_run.py`.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t1_5_bgnbd_rollback.py`.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t1_5_survival_rollback.py`.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t2_5_cf_rollback.py`.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_privacy_envelope.py` (extended).
- Possibly pinned fixture re-pins if RFM landing actually VALIDATES on synthetics (see Part E.5).

**Files touched (NEW):**
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t1_5_rfm_rollback.py`
- `/Users/atul.jena/Projects/Personal/beaconai/data/<store_id>/predictive/rfm.parquet` (runtime, VALIDATED/PROVISIONAL only).
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t1.5-summary.md`

### S12-T2 — Retention curves substrate + RetentionCard wiring + stage-keyed thresholds (FLAG OFF)

**Scope:**
- New `src/predictive/retention.py`:
  - `fit_retention(orders_df, profile, *, store_id, data_dir, thresholds: dict, seed: int = 0) -> RetentionCard`.
  - Empirical retention computation per cohort × month.
  - Numpy bootstrap (`n_bootstrap=1000`, seed-deterministic).
  - Cold-start guard (`cohort_count < 3` → INSUFFICIENT_DATA).
  - REFUSED guard (`bootstrap_ci_width_at_month_3 > 0.40` despite cohort_count ≥ 3).
  - JSON sidecar writer to `data/<store_id>/predictive/retention.json` when status ∈ {VALIDATED, PROVISIONAL}.
- New `RetentionCard` dataclass in `src/predictive/model_card.py` (alongside `ModelCard` — same module, different shape). Fields per §A.2: `cohort_count`, `min_cohort_size`, `bootstrap_ci_width_at_month_3`, `bootstrap_iterations`, `fit_status: ModelFitStatus`, `fit_warnings`, `curves: List[Dict]`, `fit_timestamp`. Reuses `ModelFitStatus` four-state enum.
- New top-level field `EngineRun.cohort_diagnostics: Dict[str, Any] = field(default_factory=dict)` on `src/engine_run.py` (additive within `event_version=1`; same additive-precedent as `predictive_models` at L1006).
- Extend `_load_model_fit_thresholds` to read `model_fit_thresholds.retention` block + `_FALLBACK_RETENTION_*` constants.
- Append `model_fit_thresholds.retention` block to `config/gate_calibration.yaml` (§C.5 verbatim).
- New flag `ENGINE_V2_ML_RETENTION` in `src/utils.py` `DEFAULTS`, default `"false"`. Add to `_coerce` bool set IN T2.
- NO library install. No `requirements.txt` edit.

**Acceptance criteria (T2):**
- `fit_retention` returns RetentionCard with correct four-state classification.
- Cold-start (cohort_count < 3) → INSUFFICIENT_DATA; no JSON artifact.
- High-CI-width despite enough cohorts → REFUSED with `bootstrap_ci_width_exceeded` warning.
- **Positive-control retention fixture test (NEW, DS-REQUIRED 2026-05-28) — `test_synthetic_retention_dgp_sanity`:** deterministic positive-control fixture (12 monthly cohorts × 200 customers each @ stable 40% month-1 retention by construction). Assertions per `ds-architect-s12-plan-review.md` §K verbatim:
  - `bootstrap_ci_width_at_month_3 < 0.10`.
  - `cumulative_retention_monotonicity_violation == False`.
  - `fit_status == VALIDATED`.
  Mirrors S11-T1 Cox PH c-index synthetic positive control (c=0.838 VALIDATED) and S11-T2 ALS recall@10=0.344 VALIDATED. **Load-bearing implementation-correctness check before engine reaches real merchant data.**
- Flag OFF → engine output byte-identical to pre-T2; all 5 pinned fixtures round-trip unchanged; `cohort_diagnostics={}` field present (empty dict default) and tolerated by `_from_dict_engine_run` for pre-S12 fixtures.
- `_coerce` bool set contains `ENGINE_V2_ML_RETENTION`.
- Cumulative-retention monotonicity check implemented; violation routes to REFUSED (§C.4).
- Commit body carries `Deviation check: none.`

**Files touched (NEW):**
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/retention.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t2_retention_fit.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t2_threshold_loader_retention.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t2_retention_card_round_trip.py`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t2-summary.md`

**Files touched (MODIFIED):**
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/model_card.py` — `RetentionCard` dataclass + threshold loader extension.
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` — `cohort_diagnostics` field on EngineRun + `_from_dict_engine_run` tolerated-as-missing extension (mirrors L1006 `predictive_models` precedent verbatim).
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` — `ENGINE_V2_ML_RETENTION` flag + `_coerce` bool set.
- `/Users/atul.jena/Projects/Personal/beaconai/config/gate_calibration.yaml` — retention block append.

### S12-T2.5 — Retention atomic flip + orchestration wire + rollback test

**Scope:**
- New orchestration block in `src/main.py` immediately after the RFM block (~L1156+RFM-block-size). Same try/except structural pattern. Writes only to `engine_run.cohort_diagnostics["retention"]`.
- Flip `ENGINE_V2_ML_RETENTION` default `"false"` → `"true"`.
- Determinism comparator extension: `_NESTED_NORMALIZED_PATHS` extended with `cohort_diagnostics.retention.fit_timestamp` (NEW path-prefix — first slot under `cohort_diagnostics`).
- Predecessor rollback-test updates: all four prior rollback tests set `ENGINE_V2_ML_RETENTION=false`.
- NEW rollback test: `tests/test_s12_t2_5_retention_rollback.py`.

**Acceptance criteria (T2.5):**
- All 5 pinned fixtures' `briefing.html` byte-identical pre/post T2.5 flip.
- `engine_run.cohort_diagnostics["retention"]` RetentionCard populated on all 5 fixtures.
- Rollback contract: `ENGINE_V2_ML_RETENTION=false` reproduces pre-T2.5 engine_run.json (`cohort_diagnostics={}`).
- Privacy envelope test extended: no per-customer data in `cohort_diagnostics["retention"]`; only cohort-aggregate stats.
- All five predecessor rollback tests still pass.
- **Renderer non-consumption grep pin (NEW, DS-REQUIRED 2026-05-28):** `grep -rn "predictive_models\|cohort_diagnostics" src/render_*` returns empty. Confirms renderer does NOT consume either field; briefing.html byte-identity holds by construction. Pinned per `ds-architect-s12-plan-review.md` §K.
- Commit body carries `Deviation check: none.`

**Files touched (NEW):**
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t2_5_retention_rollback.py`
- `/Users/atul.jena/Projects/Personal/beaconai/data/<store_id>/predictive/retention.json` (runtime, VALIDATED/PROVISIONAL only).
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t2.5-summary.md`

**Files touched (MODIFIED):**
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` (retention orchestration block).
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` (flag default flip).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_determinism_cross_run.py` (extended).
- All four prior `*_rollback.py` (extended).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_privacy_envelope.py` (extended).

### S12-T3-CLOSE — Docs + KI-NEW-P extension + sprint-close

**Scope (documentation-only, mirrors S11-T3-CLOSE):**
- `memory.md` — append six template-shaped entries (T1, T1.5, T2, T2.5, T3, CLOSE) each ≤15 lines per `CLAUDE.md` L62 rule. Narrative goes in summary files.
- `ROADMAP.md` — header refresh; §1 rewrite (S13 queued; S12 summary block; S12 outcome paragraph including Pivot 5 status — see Part E.5; follow-ups: KI-NEW-P extended to ~40 numbers across 6 substrates). §2 L43 S12 row marked **SHIPPED 2026-05-28+**.
- `STATE.md` — header refresh; §4 gate table ML-fit row updated to note substrate now spans 6 substrates (BG/NBD + G-G + survival + CF + **RFM + retention**); gate still DORMANT (S13 wires). §4 ranking-strategy chain text confirms RFM=floor / recency=last-resort per `docs/engine_flags.md` L128 verbatim.
- `docs/engine_flags.md` — header refresh; §"S10-S11 predictive layer" renamed to "S10-S12 predictive layer" with intro paragraph noting S12 added RFM (per-customer ranker, ML chain floor) + retention curves (cohort diagnostic, new `cohort_diagnostics` slot); new "S12 predictive flags" subtable; ranking-strategy fallback chain restated (`BG/NBD → CF → survival → RFM → recency` — unchanged; RFM is the explicit ML floor as documented at S11-T3).
- `docs/DECISIONS.md` — no substitution footnote needed (no library substitution at S12). One additive footnote on `D-S6.5-16` noting the S12 substrates are custom-code (no new third-party dependency; KI-NEW-R unchanged).
- `KNOWN_ISSUES.md` — extend KI-NEW-P title and body to include RFM + retention threshold cells (covers all 6 ML/diagnostic substrates under one KI). **Mandatory new sub-bullet (DS-REQUIRED 2026-05-28) calling out categorical-different closure shapes** per `ds-architect-s12-plan-review.md` §J verbatim:
  - BG/NBD / G-G / survival / CF closure: realized customer behavior vs predicted ranking → calibration plot.
  - **RFM closure:** realized 90d / 180d / 365d LTV-per-segment vs the segmentation snapshot → does the operator-readable "Champions are highest-LTV" claim hold up?
  - **Retention closure:** realized cohort retention curves vs the bootstrapped CI bands at S12 fit → are the CIs honest, or do real cohorts drift outside the band more often than 5%?
  Real-merchant calibration data for RFM/retention means something **different** than for BG/NBD/G-G/survival/CF. NO new KI letters by default (KI-NEW-Q + R + S filed at S11; nothing new warrants a letter unless an edge case surfaces during S12).
- `agent_outputs/INDEX.md` — Sprint 12 section.
- ROADMAP.md `lifelines → scikit-survival` text already updated at S11; no further substitution at S12.

**Acceptance criteria (T3-CLOSE):**
- All seven doc surfaces updated.
- Six `memory.md` entries are template-shape (≤15 lines each).
- KI-NEW-P extended (single entry; not a new letter) WITH the categorical-different-closure-shapes sub-bullet (DS-REQUIRED 2026-05-28; three bullets distinguishing ranker-substrate closure vs RFM segment-LTV-holdup closure vs retention CI-honesty closure).
- `briefing.html` byte-identity preserved by construction (zero code change).
- `agent_outputs/INDEX.md` regen date refresh + file count update.
- Commit body carries `Deviation check: none.`

**Files touched (NEW):**
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t3-close-summary.md`

**Files touched (MODIFIED):**
- `/Users/atul.jena/Projects/Personal/beaconai/memory.md`
- `/Users/atul.jena/Projects/Personal/beaconai/ROADMAP.md`
- `/Users/atul.jena/Projects/Personal/beaconai/STATE.md`
- `/Users/atul.jena/Projects/Personal/beaconai/docs/engine_flags.md`
- `/Users/atul.jena/Projects/Personal/beaconai/docs/DECISIONS.md` (light footnote — optional)
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/INDEX.md`

---

## Part E — Cross-cutting risks and ModelCard refactor decision

### E.1 ModelCard field-count refactor — Q-S12-1 DECISION

DS S11 plan review §(d) Q5 verbatim:

> **CONFIRM additive at S11.** At S12 if RFM + retention adds 3+ more optional fields, refactor to `Dict[str, float] metrics` shape. Plan ahead, do not act at S11.

**S12's additive field count to ModelCard if no refactor:**
1. `segment_monotonicity_spearman: Optional[float]` (RFM primary gate)
2. `quintile_coverage_min: Optional[float]` (RFM secondary diagnostic)

That's **2 fields, not 3**. Retention does NOT add ModelCard fields — it uses a separate `RetentionCard` dataclass (§A.2). Retention's fields (`cohort_count`, `bootstrap_ci_width_at_month_3`, etc.) live on `RetentionCard`, not on `ModelCard`.

**Strict reading of the DS gate:** "3+ more optional fields" → 2 additions does NOT trigger the refactor.

**DS-LOCKED 2026-05-28 (per `ds-architect-s12-plan-review.md` §H): DEFER the `Dict[str, float] metrics` refactor — additive at S12 like S10/S11. Refactor moment is S13-T0 (NOT S15+).** Reasons:
1. **2 fields is below the DS-stated threshold** (3+). Strict letter of the S11 verdict.
2. **Refactor cost mid-beta-blocking-sequence is real.** Touching `src/predictive/model_card.py:99-185` (ModelCard dataclass) mid-S12 means a coordinated rewrite of every read site across `src/predictive/{bgnbd,gamma_gamma,survival,cf,rfm}.py` and every test that asserts on a specific field name. Same beta-blocking-risk argument as DS's S11 §(b).4 verdict on `lifetimes` refactor: "unjustified risk for zero S11 benefit."
3. **`RetentionCard` already absorbed pressure** away from ModelCard by splitting cohort-aggregate fields onto a separate dataclass.
4. **The real refactor moment is S13-T0** (DS-revised down from "S15+" in v1). Per `ds-architect-s12-plan-review.md` §H verbatim: "DEFER to S13, NOT S15+. Lock the refactor as an explicit S13-T0 candidate ticket in ROADMAP. If S13 wires consumers without organic pressure, defer further. If S13 wiring touches 4+ read sites with `if model_card.holdout_X is not None`, refactor there."

**Action at S12-T3-CLOSE (ROADMAP.md update):** add an S13 entry note `"S13-T0 ModelCard refactor candidate, contingent on S13 wiring touching 4+ field-presence checks."` This gives S13 plan time to plan around it.

**Q-S12-1:** CLOSED — DS-LOCKED DEFER to S13-T0; founder acked 2026-05-28.

### E.2 Synthetic fixture posture — RFM might VALIDATE on synthetics (Pivot 5 implication)

**Cold-start floor:** RFM needs ≥50 customers. Retention needs ≥3 cohorts.

The pinned Beauty synthetic fixture (`tests/fixtures/synthetic_slate/healthy_beauty_240d_*`) per the S10-T1 receipt §3: **3,844 repeat customers + 15,133 orders + 259 days**. This is well above the RFM 50-customer floor (and likely above the retention 3-cohort floor too — 259 days ≈ 8.6 months of cohorts).

**Pivot 5 implication:** S12 may be the **FIRST SPRINT WHERE SUBSTRATE LEGITIMATELY VALIDATES on the pinned synthetics**. Contrast:
- S10: 5/5 REFUSED on BG/NBD (synthetic doesn't honor BG/NBD assumptions); chained 5/5 REFUSED on G-G.
- S11: 5/5 REFUSED on survival (chained); 5/5 INSUFFICIENT_DATA on CF (synthetic-data repeat-buyer ceiling).
- S12: RFM (deterministic, not probabilistic — no fit assumptions to violate) is likely to **VALIDATE** on Beauty if segment-monotonicity-on-observed-LTV clears the floor. Retention may VALIDATE if cohort count ≥6 and CIs are tight enough.

**This is acceptable and EXPECTED per Pivot 5.** RFM is deterministic statistics — its validity depends on whether the synthetic *has* economically-meaningful customer-frequency variation, not on whether the synthetic fits an upstream library's likelihood. A synthetic that DIDN'T have monotonic segment structure would itself be a fixture-honesty failure.

**Fixture re-pin implication for T1.5 / T2.5:** Since RFM is operator-only via `predictive_models["rfm"]` and the renderer does NOT consume `predictive_models`, `briefing.html` byte-identity should hold even if RFM VALIDATES. **No fixture re-pin expected.** Same logic applies to retention via `cohort_diagnostics["retention"]`.

If a fixture re-pin IS required (e.g., the determinism comparator surfaces a stable hash change that the test enforces), the atomic-flip discipline applies (single commit per S11 §L Risk #7).

### E.3 Determinism comparator — 2 new fit_timestamp paths

Per S11 §E.3 and §L pattern. Add to `tests/test_determinism_cross_run.py::_NESTED_NORMALIZED_PATHS`:
- `predictive_models.rfm.fit_timestamp` (added at T1.5)
- `cohort_diagnostics.retention.fit_timestamp` (added at T2.5; first path under new top-level slot)

**Edge case:** the retention bootstrap is seed-deterministic (default `seed=0`). Verify the bootstrap distribution itself is byte-identical across runs with the same seed (i.e., the `curves[].ci_lower_95` / `ci_upper_95` values themselves should not vary; only `fit_timestamp` should be normalized).

### E.4 `_coerce` bool set — pre-emptive add at substrate ticket

Per S11 §E.4 + S10-T1.5 lesson + S10-T2 pre-emptive pattern. Add `ENGINE_V2_ML_RFM` at T1 (not T1.5); add `ENGINE_V2_ML_RETENTION` at T2 (not T2.5). Pinned by per-ticket flag-in-coerce-bool-set tests.

### E.5 Synthetic outcome expectations summary (founder-visible)

| Fixture | Substrate | Expected status | Rationale |
|---|---|---|---|
| Beauty 240d | RFM | **VALIDATED** (likely) | 3,844 repeat customers + 259d window; deterministic segmentation; monotonicity-on-observed-LTV should clear floor. **First synthetic VALIDATED in the S10-S12 sequence.** |
| Beauty 240d | retention | **VALIDATED or PROVISIONAL** (likely) | 259d ≈ 8.6 months → ~6-8 cohorts; CI widths depend on per-cohort N. |
| Supplements 240d | RFM | **PROVISIONAL or VALIDATED** | 1,200 customers + 972 L28 orders; smaller than Beauty but well above 50-floor. |
| Supplements 240d | retention | **PROVISIONAL** | Fewer cohorts (~6); CIs wider on smaller cohorts. |
| Other 3 pinned | RFM/retention | **case-by-case** | Depends on each fixture's customer/cohort counts. |

**Real VALIDATED evidence still comes from S14 real-merchant data** — synthetic VALIDATED on RFM does NOT supersede the KI-NEW-P closure criterion ("≥3 real beta merchants per stage cell with realized-vs-predicted ranking/calibration data").

### E.6 Ranking-strategy chain documentation

At S12-T3-CLOSE, `docs/engine_flags.md` L128 verbatim chain stays:

> `BG/NBD → CF → survival → RFM → recency`

S12 makes RFM the **substrate-present floor of the ML rung** (previously documented at S11-T3 as the planned floor; S12 makes it operationally real). Recency stays the absolute last-resort non-ML fallback. Per `ds-architect-s10-cold-start-and-eb-interaction.md` Part 5 L121 verbatim:

> **RFM is the ranking-strategy floor** — below RFM there's only recency-order. Recommend that S12 explicitly designate RFM as the floor in the ranking-strategy chain's documentation, with recency as the absolute last-resort.

T3-CLOSE makes this designation explicit in the audit copy.

---

## Part F — KI filing posture for S12 close

### KI-NEW-P extension (single entry; not a new letter)

Extend the existing KI-NEW-P title from:
> KI-NEW-P — ModelFitStatus stage-grid threshold calibration suite (BG/NBD + Gamma-Gamma + survival + CF)

To:
> KI-NEW-P — ModelFitStatus stage-grid threshold calibration suite (BG/NBD + Gamma-Gamma + survival + CF + RFM + retention)

Extend the **What** block to cover all 6 substrates + ~40-number stage-grid framing (was ~30 numbers at S11 close). Add the following 2026-05-28 sub-bullets:

- "Synthetic Beauty RFM landed [VALIDATED|PROVISIONAL|REFUSED] (segment_monotonicity_spearman=<value>, quintile_coverage_min=<value>) — first synthetic with non-REFUSED ML substrate." (Outcome confirmed at T1.5 receipt §4.)
- "Synthetic Beauty retention landed [VALIDATED|PROVISIONAL|REFUSED] (cohort_count=<value>, bootstrap_ci_width_at_month_3=<value>)." (Outcome at T2.5 receipt §4.)
- "RFM is deterministic — VALIDATED on synthetic does NOT subordinate the S14 real-merchant calibration criterion. Closure remains stage-cell × ≥3 merchants per stage."

**MANDATORY new sub-bullet (DS-REQUIRED 2026-05-28) — categorical-different closure shapes** per `ds-architect-s12-plan-review.md` §J verbatim. RFM/retention have **categorically different** closure shapes from BG/NBD/G-G/survival/CF:

- **BG/NBD / G-G / survival / CF closure:** realized customer behavior vs predicted ranking → calibration plot.
- **RFM closure:** realized 90d / 180d / 365d LTV-per-segment vs the segmentation snapshot → does the operator-readable "Champions are highest-LTV" claim hold up?
- **Retention closure:** realized cohort retention curves vs the bootstrapped CI bands at S12 fit → are the CIs honest, or do real cohorts drift outside the band more often than 5%?

Real-merchant calibration data for RFM/retention means something different than for the prior four substrates. These three closure-criteria shapes go into the KI-NEW-P sub-bullet at T3-CLOSE as an explicit note.

**Closure criterion (extended from S11):** each stage cell needs ≥3 real beta merchants per stage with the substrate-appropriate realized-vs-predicted data (ranker-calibration for BG/NBD/G-G/survival/CF; segment-LTV-holdup for RFM; CI-honesty for retention).

### No new KI letters at S12 close (default posture)

KI-NEW-Q (operator parquet CLI), KI-NEW-R (3-library vendor-fork), KI-NEW-S (wall-clock flake) all filed at S11-T3 close. S12 does NOT add a new third-party library (custom code for both substrates), so KI-NEW-R does NOT extend. S12 does not introduce new test flakes. **No new KI letters expected.** If T1/T2 surfaces a genuinely new failure mode, file at T3 with letter `KI-NEW-T`.

---

## Part G — Open questions — ALL CLOSED 2026-05-28 (DS-LOCKED + founder ack)

All 8 questions closed at v2 per `agent_outputs/ds-architect-s12-plan-review.md` §L and founder ack 2026-05-28.

| # | Question | Domain | Verdict (DS-LOCKED + founder-acked 2026-05-28) | Status |
|---|---|---|---|---|
| Q-S12-1 | ModelCard field-count refactor — pre-emptive at S12-T0/T1, or defer? | DS | **DEFER to S13-T0** (not S15+) per §H. Add ROADMAP S13 note "S13-T0 ModelCard refactor candidate, contingent on S13 wiring touching 4+ field-presence checks." | CLOSED |
| Q-S12-A | RFM segment scheme — 11 named segments or raw 5×5×5=125 cells? | DS-tech / founder-product | **11 named segments + raw quintile triplet preserved on parquet** per §E. | CLOSED |
| Q-S12-B | RFM Spearman thresholds | DS-LOCK | **0.60 / 0.65 / 0.70 / 0.70 (PROVISIONAL 0.40)** per §F. v1's 0.50/0.55/0.60 + PROVISIONAL 0.30 revised UP. | CLOSED |
| Q-S12-C | Retention CI-width thresholds + gate composition | DS-LOCK | **0.25 / 0.20 / 0.15 / 0.15 (PROVISIONAL 0.35)** per §G. v1's 0.30/0.25/0.20/0.20 + PROVISIONAL 0.40 revised DOWN. Plus cumulative-retention-monotonicity-violation **PROMOTED to REFUSED** (was tertiary diagnostic). Gate composition AND, not OR. | CLOSED |
| Q-S12-D | S12-T0 analog (correctness debt)? | DS | **No T0.** DS re-read confirmed; greenfield substrate. | CLOSED |
| Q-S12-E | Storage for retention — `cohort_diagnostics` top-level slot or `predictive_models["retention"]`? | DS | **New top-level `EngineRun.cohort_diagnostics` slot** per §C. `RetentionCard` dataclass alongside ModelCard, reusing `ModelFitStatus` enum (vocab-stacking Option A). | CLOSED |
| Q-S12-F | Library posture — custom code vs `lifelines.KaplanMeierFitter`? | DS | **Custom code; no `lifelines`** per §D. KM is right-censored continuous-time; our object is discrete-monthly empirical retention. `pd.qcut` for RFM; numpy bootstrap for retention. | CLOSED |
| Q-S12-G | Pivot 5 honest-synthetic posture — accept that RFM (and possibly retention) WILL VALIDATE on synthetics for the first time? | DS / founder | **Yes — Pivot-5-consistent.** RFM on healthy Beauty (3,844 repeat customers) SHOULD VALIDATE; failure would indicate a bug. Real-merchant KI-NEW-P closure at S14 remains the gate. | CLOSED |
| Q-S12-H | KI letter posture — extend KI-NEW-P only, OR file new letters? | DS | **Extend KI-NEW-P only**, with mandatory categorical-different-closure-shapes sub-bullet per §J. No new KI letter. | CLOSED |

---

## Part H — Files / functions affected (absolute paths)

### NEW

- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/rfm.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/retention.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t1_rfm_fit.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t1_threshold_loader_rfm.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t1_model_card_additive.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t1_5_rfm_rollback.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t2_retention_fit.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t2_threshold_loader_retention.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t2_retention_card_round_trip.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t2_5_retention_rollback.py`
- `/Users/atul.jena/Projects/Personal/beaconai/data/<store_id>/predictive/rfm.parquet` (per-store, runtime, VALIDATED/PROVISIONAL only)
- `/Users/atul.jena/Projects/Personal/beaconai/data/<store_id>/predictive/retention.json` (per-store, runtime, VALIDATED/PROVISIONAL only — NOT parquet)
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t1-summary.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t1.5-summary.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t2-summary.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t2.5-summary.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t3-close-summary.md`

### MODIFIED

- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/model_card.py` — 2 additive ModelCard fields (`segment_monotonicity_spearman`, `quintile_coverage_min`); new `RetentionCard` dataclass; `_load_model_fit_thresholds` extended for rfm + retention blocks; fallback constants for both. (OR `Dict[str, float] metrics` refactor at T0 if Q-S12-1 approved.)
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` — NEW top-level field `cohort_diagnostics: Dict[str, Any] = field(default_factory=dict)`; `_from_dict_engine_run` tolerated-as-missing extension (mirrors L1006 `predictive_models` precedent).
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` L1156+ — TWO new orchestration blocks (RFM after CF; retention after RFM). Both flag-gated, write only to `engine_run.predictive_models["rfm"]` or `engine_run.cohort_diagnostics["retention"]`. NO edits to L1380-L1597 (KI-NEW-L is S13.5).
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` — 2 new flags (`ENGINE_V2_ML_RFM` at T1, `ENGINE_V2_ML_RETENTION` at T2). BOTH added to `_coerce` bool set in the substrate ticket.
- `/Users/atul.jena/Projects/Personal/beaconai/config/gate_calibration.yaml` — append `model_fit_thresholds.rfm` at T1; append `model_fit_thresholds.retention` at T2.
- `/Users/atul.jena/Projects/Personal/beaconai/docs/engine_flags.md` — S12 flag entries + ranking-strategy chain restatement at T3-CLOSE.
- `/Users/atul.jena/Projects/Personal/beaconai/docs/DECISIONS.md` — (optional) light footnote on `D-S6.5-16` noting S12 substrates are custom-code; KI-NEW-R unchanged.
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md` — KI-NEW-P extension at T3-CLOSE (title + body to cover RFM + retention; ~40 numbers across 6 substrates).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_determinism_cross_run.py` — `_NESTED_NORMALIZED_PATHS` extended at T1.5 (rfm.fit_timestamp) and T2.5 (cohort_diagnostics.retention.fit_timestamp).
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t1_5_bgnbd_rollback.py`, `tests/test_s11_t1_5_survival_rollback.py`, `tests/test_s11_t2_5_cf_rollback.py` — `_run_and_load` helpers extended at T1.5 + T2.5 to set new flags `=false`.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_v2_harness_cfg_gated_fields.py` — DS invariant 16 extension at T1 + T2.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_privacy_envelope.py` — extended at T1.5 (no per-customer RFM scores in `engine_run.json`) + T2.5 (no per-customer data in `cohort_diagnostics`).
- `/Users/atul.jena/Projects/Personal/beaconai/memory.md` — template-shape entries at each ticket close.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/INDEX.md` — Sprint 12 section at T3-CLOSE.
- `/Users/atul.jena/Projects/Personal/beaconai/ROADMAP.md` — §1 + §2 row update at T3-CLOSE.
- `/Users/atul.jena/Projects/Personal/beaconai/STATE.md` — §4 light update at T3-CLOSE (6 substrate models now present; dormant gate structure unchanged).

### UNCHANGED (load-bearing — DO NOT TOUCH)

- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py` — slate assembly, role-uniqueness, single-demote-channel invariant. No S12 changes.
- `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py` — `PSEUDO_N_BY_STATUS = {30,15,10}` locked through S14 per STATE.md §5 invariant 5.
- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py` — no MEASUREMENT-layer change.
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py:1380-1597` — five V2 prior-anchored injection blocks. KI-NEW-L is S13.5.
- `/Users/atul.jena/Projects/Personal/beaconai/src/guardrails.py` — single-demote-channel invariant authority.
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml` — frozen.
- `/Users/atul.jena/Projects/Personal/beaconai/src/audience_builders.py` — no new builder through S13 per DS invariant 15.
- Renderer surface (`src/render_briefing.py` / templates / `briefing.html`) — `predictive_models` AND `cohort_diagnostics` never surfaced merchant-facing at S12 (operator-only).
- `PlayCard.predicted_segment` / `PlayCard.model_card_ref` stubs at `src/engine_run.py:837-838` — stay None at S12 close. S13 wires.
- `ReasonCode` enum at `src/engine_run.py:73` — S10-T3's `MODEL_FIT_*` additions cover all 6 substrates without modification (RFM and retention route through the same ML-fit gate, lowest precedence).
- `tests/test_reason_code_precedence_invariant.py` — precedence pin unchanged; covers RFM + retention.
- Existing S10/S11 substrates: `src/predictive/{bgnbd,gamma_gamma,survival,cf}.py` — UNCHANGED.
- `lifetimes==0.11.3`, `scikit-survival>=0.22,<0.24`, `implicit>=0.7,<0.8` — no new pin at S12. `requirements.txt` unchanged.

---

## Part I — New artifacts produced at each stage

| Ticket | Artifact |
|---|---|
| T1 | `src/predictive/rfm.py`; rfm block in `config/gate_calibration.yaml::model_fit_thresholds`; 2 additive ModelCard fields (`segment_monotonicity_spearman`, `quintile_coverage_min`) — OR `metrics: Dict[str, float]` refactor if Q-S12-1 approved; `ENGINE_V2_ML_RFM` flag in DEFAULTS + `_coerce` bool set; threshold-loader extension. |
| T1.5 | `data/<store_id>/predictive/rfm.parquet` (per-customer segment + raw scores when VALIDATED/PROVISIONAL); `engine_run.predictive_models["rfm"]` ModelCard surfaced operator-only; new RFM-rollback test. |
| T2 | `src/predictive/retention.py`; retention block in `config/gate_calibration.yaml::model_fit_thresholds`; new `RetentionCard` dataclass; new `EngineRun.cohort_diagnostics` top-level field; `ENGINE_V2_ML_RETENTION` flag in DEFAULTS + `_coerce` bool set; threshold-loader extension. |
| T2.5 | `data/<store_id>/predictive/retention.json` (cohort × month retention + CIs when VALIDATED/PROVISIONAL); `engine_run.cohort_diagnostics["retention"]` RetentionCard surfaced operator-only; new retention-rollback test. |
| T3-CLOSE | KI-NEW-P extended to ~40 numbers across 6 substrates; `docs/engine_flags.md` S12 predictive flags + ranking-strategy chain restatement (RFM = explicit ML floor); ROADMAP.md S12 marked SHIPPED; STATE.md §4 6-substrate noting; sprint-close memory.md entries; `agent_outputs/INDEX.md` S12 section. |

---

## Part J — Feature flag strategy

| Flag | Lands | Default at land | Flips to ON | Rollback path |
|---|---|---|---|---|
| `ENGINE_V2_ML_RFM` | S12-T1 | `false` | S12-T1.5 (atomic) | env override `=false` reproduces pre-T1.5 sha |
| `ENGINE_V2_ML_RETENTION` | S12-T2 | `false` | S12-T2.5 (atomic) | env override `=false` reproduces pre-T2.5 sha |

Both added to `_coerce` bool set at the substrate ticket (T1 / T2), not the flip ticket. Predecessor rollback tests (S10-T1.5, S11-T1.5, S11-T2.5) updated at each flip.

No flag removed at S12. `RECENTLY_RUN_FATIGUE_ENABLED` stays OFF.

---

## Part K — Acceptance criteria summary (sprint-level)

| # | Criterion | Test home |
|---|---|---|
| 1 | RFM fits per merchant when `ENGINE_V2_ML_RFM` ON; ModelCard four-state populated across (n_customers, monotonicity, quintile_coverage) decision matrix | `tests/test_s12_t1_rfm_fit.py` |
| 2 | RFM is INDEPENDENT of BG/NBD / G-G / survival / CF (runs to own four-state regardless of upstream substrate status) | `tests/test_s12_t1_rfm_fit.py::test_independence` |
| 3 | Positive-control synthetic VALIDATES RFM (Spearman > 0.80 on monotonic-by-construction population) | `tests/test_s12_t1_rfm_fit.py::test_positive_control_validates` |
| 4 | Retention fits per merchant when `ENGINE_V2_ML_RETENTION` ON; RetentionCard four-state populated | `tests/test_s12_t2_retention_fit.py` |
| 5 | Retention is INDEPENDENT of all 5 prior substrates | `tests/test_s12_t2_retention_fit.py::test_independence` |
| 6 | Positive-control synthetic VALIDATES retention (tight CI width at month 3) | `tests/test_s12_t2_retention_fit.py::test_positive_control_validates` |
| 7 | All 5 pinned fixtures `briefing.html` byte-identical pre/post S12 (operator-only ML output) | `test_slate_regression_*` + `test_golden_diff` + `test_s8_t3_provenance` |
| 8 | Rollback contracts: both flags `=false` reproduce pre-S12 shape exactly | `tests/test_s12_t1_5_rfm_rollback.py`, `tests/test_s12_t2_5_retention_rollback.py` |
| 9 | Privacy envelope: no per-customer scores in `engine_run.json`; no per-customer data in `cohort_diagnostics`. INSUFFICIENT_DATA writes neither artifact | `tests/test_s10_privacy_envelope.py` extended at T1.5 + T2.5 |
| 10 | ReasonCode precedence (S10-T3) holds with RFM + retention wired; ML-fit-only failure does NOT route to Considered | `tests/test_reason_code_precedence_invariant.py` (unchanged) |
| 11 | Determinism comparator handles 2 new fit_timestamps + 1 new top-level slot `cohort_diagnostics` | `tests/test_determinism_cross_run.py` |
| 12 | Both flags in `_coerce` bool set at substrate ticket, not flip ticket | `tests/test_s12_t1_rfm_fit.py::test_flag_in_coerce_bool_set`, `tests/test_s12_t2_retention_fit.py::test_flag_in_coerce_bool_set` |
| 13 | Threshold loader resolves rfm + retention stage cells | `tests/test_s12_t1_threshold_loader_rfm.py`, `tests/test_s12_t2_threshold_loader_retention.py` |
| 14 | ModelCard additive (2 new fields) preserves `event_version=1` round-trip; OR if refactor approved, `metrics: Dict[str, float]` shape passes round-trip | `tests/test_s12_t1_model_card_additive.py`, existing `test_engine_run_round_trip` |
| 15 | RetentionCard round-trips via `engine_run.to_dict()` / `from_dict()` | `tests/test_s12_t2_retention_card_round_trip.py` |
| 16 | DS invariant 16: harness-level test exercises every new flag-gated producer field | `tests/test_v2_harness_cfg_gated_fields.py` extended |
| 17 | KI-NEW-P extended at S12-T3 with rfm + retention stage cells (single entry, not a new letter) | `KNOWN_ISSUES.md` review |
| 18 | Single-demote-channel invariant preserved: no append to `engine_run.recommendations` from S12 code | code review + `tests/test_s7_6_c1_priority_prepend_invariant.py` (unchanged) |
| 19 | All S12 commit bodies carry `Deviation check: none.` | git log review at sprint close |
| 20 | Ranking-strategy chain documentation at T3-CLOSE: RFM = explicit ML floor; recency = absolute last-resort | `docs/engine_flags.md` review |

---

## Part L — Risks and rollback strategy

| Risk | Mitigation | Rollback |
|---|---|---|
| RFM segment-monotonicity metric not defensible per DS | DS sign-off at T1 dispatch (Q-S12-B) before code lands; revise metric in plan + dispatch brief | If post-T1 review flags metric, revert T1; redo with revised metric |
| Retention CI-width primary gate not defensible per DS | DS sign-off at T1 dispatch (Q-S12-C); revise in plan + brief | Revert T2; redo |
| Synthetic VALIDATED on RFM triggers fixture re-pin (operator surprise) | Atomic-flip single-commit pattern; T1.5 receipt §4 documents the outcome | Revert single commit reverts both flag-flip and re-pin |
| ModelCard field-count refactor needed sooner than expected | Q-S12-1 surfaces decision pre-T1; if approved, refactor at T0 (own ticket) | If refactor introduced silently mid-T1, escalate to founder + DS; revert |
| Bootstrap CI computation non-deterministic across runs (seed bug) | `seed=0` default; test pins byte-identical CI across two runs with same seed | Re-fit with explicit seed; re-pin determinism comparator |
| `cohort_diagnostics` round-trip silently breaks pre-S12 fixtures | `_from_dict_engine_run` tolerated-as-missing extension verified at T2 dispatch | Revert; redo schema with stricter default-empty handling |
| `_coerce` gap discovered at flip ticket (T1.5/T2.5 lesson regression) | Dispatch brief pins this requirement at substrate ticket (T1 / T2) | Re-dispatch T1 or T2 with patch |
| RFM / retention thresholds too lax → false VALIDATED on beta merchants | KI-NEW-P extension at T3; closure criterion = ≥3 merchants per stage; founder retune turn | thresholds live in YAML — change → re-fit → re-pin |
| Fixture re-pin races atomic flip | Single-commit pattern (S7.6 Risk #4) | Revert commit reverts both |
| Renderer accidentally consumes `predictive_models["rfm"]` or `cohort_diagnostics` | Grep at S12-T1.5 + T2.5: `grep -rn "predictive_models\\|cohort_diagnostics" src/render_*` returns nothing | If accidental consumption surfaces, revert + re-architect |
| Existing S10-T2.5 orchestration block line numbers shift as new blocks land | Reference function names + flag names, not line numbers, in dispatch briefs | n/a |
| KI-NEW-L (injection blocks at L1380-1597) accidentally edited | DO-NOT-TOUCH list in §H; pre-dispatch review | revert |
| Retention curves on small fixtures produce too few cohorts → INSUFFICIENT_DATA (Pivot 5 — expected, not a failure) | RetentionCard surfaces status; no parquet | n/a |
| Single-demote-channel violation slips in via orchestration block | Code review on dispatch brief; tests pin no `recommendations` writes from `src/predictive/rfm.py` or `src/predictive/retention.py` | revert; redo with no `recommendations` touch |

---

## Part M — What not to touch yet

- `src/decide.py` — no DECIDE-layer change at S12.
- `src/main.py:1380-1597` — five V2 prior-anchored injection blocks. KI-NEW-L is S13.5.
- `src/sizing.py` `PSEUDO_N_BY_STATUS` table — locked through S14.
- `src/measurement_builder.py` — no MEASUREMENT-layer change.
- `src/audience_builders.py` — no new builder through S13 per DS invariant 15.
- `src/guardrails.py` — single-demote-channel authority.
- `config/priors.yaml` — frozen.
- Renderer surface — `predictive_models` AND `cohort_diagnostics` operator-only at S12.
- `PlayCard.predicted_segment` / `PlayCard.model_card_ref` stubs at `src/engine_run.py:837-838` — stay None at S12 close. S13 wires.
- `ReasonCode` enum — no new codes at S12.
- Existing S10/S11 substrates (`src/predictive/{bgnbd,gamma_gamma,survival,cf}.py`) — UNCHANGED.
- `requirements.txt` — no new pin (custom code for both S12 substrates).
- `KNOWN_ISSUES.md` — pre-dispatch S12 plan does NOT edit; KI-NEW-P extended at S12-T3 close only.
- `memory.md` — entries only at ticket close, template-shape per CLAUDE.md rule.
- `PIVOTS.md` — no direction change at S12. (S11 pattern: SKIP per DS confirmation.)
- `ARCHITECTURE_PLAN.md` — archived per Phase 2 cutover. Untouched.
- S10/S11 PlayCard / ModelCard contracts — additive only (2 new optional ModelCard fields), no schema break.

---

## Part N — Summary of resolved items at v2 (all Qs CLOSED)

1. **Q-S12-1 — ModelCard refactor:** CLOSED — DEFER to S13-T0 (per DS §H + founder ack 2026-05-28). ROADMAP S13 entry note added at T3-CLOSE.
2. **Q-S12-B + Q-S12-C — DS sign-off on RFM + retention validation metrics and thresholds:** CLOSED — DS-LOCKED at v2 (§B.5, §C.5). RFM Spearman floors UP, retention CI-width floors DOWN, cumulative-monotonicity REFUSED, positive-control retention fixture required.
3. **Synthetic RFM / retention outcome:** still unknown until fit runs (Pivot-5-consistent). DS expects RFM to VALIDATE on healthy Beauty (3,844 repeat customers); failure would indicate a bug. T1.5 / T2.5 receipts pin the outcome.
4. **Retention curves on supplements:** supplements fixture has fewer cohorts (~6 if 240d window). Likely PROVISIONAL on retention under DS-tightened CI-width floors. Honest dormancy preserved.
5. **D-6 compliance:** both substrates are classical statistics (RFM = deterministic quintile + named-segment mapping; retention = empirical retention + numpy bootstrap). Neither is in the D-6 banned list (PRODUCT.md L96). Confirmed within D-6's "peer-reviewed-classical only" carve-out per ROADMAP §5 L100 verbatim.

**Dispatch readiness:** v2 is dispatchable. Next action is orchestrator dispatch of code-refactor-engineer S12-T1 brief (RFM substrate + ModelCard wiring + DS-locked thresholds + flag OFF), with brief requiring `agent_outputs/code-refactor-engineer-s12-t1-summary.md` per founder protocol.

---

## Sources

Verbatim-quoted in plan body:
- `PRODUCT.md` §6 D-6 (banned ML use-cases); §5 beta posture month-1-wow / month-2-return; §6 L96 verbatim.
- `STATE.md` §4 (three-active + one-dormant gate); §5 invariant 5 (`PSEUDO_N` lock); §7 (synthetic-fixture posture).
- `PIVOTS.md` Pivot 5 (synthetic-fixture honesty rule); Pivot 7 (single-demote-channel invariant); Pivot 8 (month-1-wow / month-2-return).
- `ROADMAP.md` §1 L13 verbatim (S12 anchor); §2 L43 verbatim (S12 row); §5 L100 verbatim (D-6 classical-only); §5 L102-103 verbatim (no cross-merchant pooling; PII posture).
- `KNOWN_ISSUES.md` KI-NEW-P (extended at S11-T3; S12-T3 extends with RFM + retention cells); KI-NEW-Q / R / S filed at S11-T3.
- `agent_outputs/INDEX.md` Sprint 10 + 11 sections.
- `agent_outputs/implementation-manager-s10-ml-part1-plan.md` — pattern parent.
- `agent_outputs/implementation-manager-s11-ml-part2-plan.md` v2 — cadence mirror; ModelCard field-count refactor watermark (§G Q5); DS-substituted library posture.
- `agent_outputs/ds-architect-s10-plan-review.md` + `agent_outputs/ds-architect-s10-cold-start-and-eb-interaction.md` Part 5 L121 verbatim (RFM cold-start ≥50 customers; retention ≥3 cohorts; RFM as ranking floor).
- `agent_outputs/ds-architect-s11-plan-review.md` §(d) Q5 verbatim (S12 refactor trigger at 3+ additive fields).
- `agent_outputs/code-refactor-engineer-s10-t1-summary.md` §3 (Beauty fixture: 3,844 repeat customers + 15,133 orders + 259 days).
- `agent_outputs/code-refactor-engineer-s11-t1-summary.md` + `s11-t2-summary.md` (positive-control synthetic pattern: c=0.838, recall@10=0.344).
- `agent_outputs/code-refactor-engineer-s11-t3-close-summary.md` (sprint-close documentation pattern; KI extension posture; KI-NEW-P scope to ~30 numbers).
- `src/predictive/model_card.py` (ModelCard dataclass L98-185; `_load_model_fit_thresholds` pattern; `_FALLBACK_*` constants L244-278).
- `src/predictive/__init__.py`, `src/predictive/{bgnbd,gamma_gamma,survival,cf}.py` (substrate pattern S12 mirrors).
- `src/main.py` L1048-L1155 (S11 survival + CF orchestration blocks — pattern for RFM + retention insertion).
- `src/engine_run.py` L1006 (`predictive_models: Dict[str, Any]` precedent for `cohort_diagnostics`); L837-838 (PlayCard stubs).
- `src/utils.py` L848-953 (ML flag-default pattern); `_coerce` bool set.
- `config/gate_calibration.yaml::model_fit_thresholds` blocks (bgnbd / gamma_gamma / survival / cf — pattern for rfm + retention append).
- `docs/engine_flags.md` L128 verbatim (ranking-strategy fallback chain `BG/NBD → CF → survival → RFM → recency`).
- `CLAUDE.md` Subagent Handoff Discipline (L27-46); Documentation Discipline (L68-80); memory.md template-shape rule; single-demote-channel invariant.

*End of plan (v2 — DS-revised + founder-acked 2026-05-28; dispatchable for S12-T1).*
