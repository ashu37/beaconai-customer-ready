# BeaconAI Engine Flag Inventory

_Last updated: 2026-05-29 (post-S13 close — covers S6, S6.5, S7, S7.5, S7.6, S8, S10, S11, S12, S13)_

This document is the authoritative inventory of every runtime flag the engine
reads. It supersedes the M0–M10 framing of earlier versions: the V2 decide /
output / slate surface is live by default, and the bulk of flag activity since
M9 has been per-builder and per-observed-effect toggles delivered through the
S6 → S8 sprint series.

Audiences:

1. The reviewer who needs to confirm the cfg surface before touching decision
   logic.
2. The future cleanup author who will collapse the per-feature flags once
   every default-ON behavior has held through real-merchant beta.

Every flag below names its current default and (where traceable) the sprint
that introduced it or flipped its default. Rationale lives in
`ARCHITECTURE_PLAN.md`, `memory.md`, `PIVOTS.md`, and the per-ticket verdict
files under `agent_outputs/` — this doc only catalogs.

---

## How config flows

1. `src/utils.get_config()` builds a dict starting from `DEFAULTS`
   (`src/utils.py` ~lines 457-1038).
2. If `.env` exists in the cwd, key=value pairs override `DEFAULTS` (only for
   keys already in `DEFAULTS`; unknown keys are ignored).
3. If a matching env var is set in the process env, it overrides the `.env`
   value. Order in `get_config`: `DEFAULTS` -> `.env` file -> process env.
4. A handful of modules (`charts.py`, `action_engine.py`) call `os.getenv(...)`
   directly without going through `get_config`. Those are listed under
   "Direct env reads" below.

Atomic-flip discipline (memory.md S7.6 T*N*.5 pattern): every default OFF→ON
flip ships in its own commit atomically with the affected pinned-fixture
re-pin. Sub-features get separate flags rather than bundled toggles, because
bundled flips hid the cause of drift during the S7.6-T7.5 spiral.

---

## V2 surface flags (decide / output / slate)

| Flag | Default | Origin | Notes |
|---|---|---|---|
| `ENGINE_V2_DECIDE` | true | M7 | Routes `src.main` through `src.decide.decide(engine_run, cfg)`; replaces the legacy selector's recommendations / considered / abstain / watching on EngineRun. |
| `ENGINE_V2_OUTPUT` | true | M8 | Routes `render_briefing` through `src.storytelling_v2` (state-of-store + Recommended + Considered + Watching + data-quality footer + abstain memos). |
| `ENGINE_V2_SLATE` | true | Phase 6A T-A4 | Enables `_select_recommended_experiments` and populates `EngineRun.recommended_experiments`; with OFF the field is always `[]`. |
| `ENGINE_V2_SIZING` | false | M6 | When ON, replaces `revenue_range` on EngineRun.recommendations with `sizing.size_play(...)` output and writes `receipts/v2_sizing_shadow.json`. Legacy `calculate_28d_revenue` untouched. |
| `INCLUDE_DEBUG_FIELDS` | false | S13.6-T1a (Option D) | Gates the `notes: List[str]` operator-debug debris on S6+ typed slots (`Sensitivity`, `Provenance`, `PredictedSegment`, `ModelCardRef`, `MonthDelta`) at `engine_run.json` serialization time. Default OFF per Pivot 2 (engine emits typed contract surface only). Flip ON via env var for local debug. |

Rendering the V2 slate requires all three of `ENGINE_V2_DECIDE` +
`ENGINE_V2_OUTPUT` + `ENGINE_V2_SLATE` to be ON.

---

## INCLUDE_DEBUG_FIELDS

- **Default:** OFF (`False`)
- **Effect:** When ON, debug-only fields (e.g., `Sensitivity`, `Provenance`, debug-stripped Optional fields) are included in `engine_run.json` output. When OFF, these fields are omitted.
- **Who should flip:** Internal dev / DS runs only. Merchant-handoff runs leave OFF.
- **Introduced:** S13.6-T1a (2026-05-30)
- **Founder confirmed:** 2026-06-01 (DS §f question 3)

---

## S6 / S6.5 / S7 builder + profile flags

| Flag | Default | Origin | Notes |
|---|---|---|---|
| `ENGINE_V2_STORE_PROFILE` | true | S6.5 T1 (flipped at T5, 2026-05-18) | Attaches typed `StoreProfile` to EngineRun; PROFILE layer feeds audience floors / materiality / window selection. |
| `ENGINE_V2_BUILDER_WINBACK_DORMANT` | true | S6 T1 (flipped at T1.5, 2026-05-17) | Tier-B `winback_dormant_cohort` builder; anchors on `winback_21_45.base_rate`. |
| `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` | false | S6 T3 | Dormant on Beauty by design (KI-NEW-G RESOLVED-AS-DOCUMENTED 2026-05-23). Activation gated on real-merchant data clearing per-SKU N floor. |
| `ENGINE_V2_BUILDER_DISCOUNT_HYGIENE` | true | S7 T1 (flipped at T1.5, 2026-05-21) | Beauty-only Tier-B builder; anchors on `discount_dependency_hygiene.base_rate.beauty`. Supplements stays Path-D dormant per DS Memo-4 REJECT. |
| `ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND` | true | S7 T2 (flipped at T2.5) | Tier-B `cohort_journey_first_to_second` builder; anchors on wildcard-vertical `first_to_second_purchase.base_rate` (S7.5-T2). Retires the Phase 5.6 directional proxy. |
| `ENGINE_V2_BUILDER_AOV_BUNDLE` | true | S7 T3 (flipped at T3.5, 2026-05-21) | Dual-tier prior: Beauty validated_external Memo 2 (pseudo_n=30); supplements elicited_expert Memo 3 downgraded (pseudo_n=10) per KI-NEW-J safeguard. |
| `ENGINE_V2_PRIORS_VALIDATION` | true | S7.5 T3 (flipped at T3.5) | Sizing refuses to blend on priors carrying `validation_status in {heuristic_unvalidated, placeholder}`; decide() emits `AbstainMode.SOFT_PRIOR_UNVALIDATED` when zero firing Tier-B + zero validated Tier-C; refused plays route to Considered with `ReasonCode.PRIOR_UNVALIDATED`. Source: ARCHITECTURE_PLAN.md Part III-1. |
| `ENGINE_V2_ABSTAIN_4STATE` | true | S7 T4 (flipped at T4.5, 2026-05-21) | DS-locked Gap F majority-with-tiebreak precedence over SOFT_AWAITING_MEASUREMENT, SOFT_PRIOR_UNVALIDATED, SOFT_BELOW_FLOOR, SOFT_AUDIENCE_TOO_SMALL. `TARGETING_HELD_UNDER_ABSTAIN` excluded from the count. |

---

## S7.6 observed-effect flags

The S7.6 series wired per-store observed effects into the four firing Tier-B
builders through `src/measurement_observed.py`, threading the L28 `(k, n)`
into `bayesian_blend(observed_k, observed_n)` at the existing seam in
`src/sizing.py`. EB blend math is unchanged; these flags only change what
`(k, n)` flows in.

| Flag | Default | Origin | Notes |
|---|---|---|---|
| `ENGINE_V2_OBSERVED_EFFECT_WINBACK` | true | S7.6 T1 (flipped at T1.5, 2026-05-21) | B-1 `winback_dormant_cohort`. Helper short-circuits for supplements (heuristic_unvalidated prior). |
| `ENGINE_V2_OBSERVED_EFFECT_REPLENISHMENT` | false | S7.6 T2 | B-2. Blocked on KI-27 (replenishment_parser returns None for supplements). Helper short-circuits for supplements. |
| `ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE` | true | S7.6 T3 (flipped at T3.5, 2026-05-23) | B-3. Helper short-circuits unconditionally for supplements (Path-D Memo-4 REJECT). |
| `ENGINE_V2_OBSERVED_EFFECT_JOURNEY` | true | S7.6 T4 (flipped at T4.5, 2026-05-23) | B-4. Berkson-invariant enforced (early-half-window cohort denominators only). |
| `ENGINE_V2_OBSERVED_EFFECT_AOV_BUNDLE` | true | S7.6 T5 (flipped at T5.5) | B-5. Dual statistical test (Welch-t on order-level AOV + two-proportion z-test on near-threshold band share); both must reach p<0.10 jointly. |
| `ENGINE_V2_OBSERVED_ELIGIBILITY_GATE` | true | S7.6 T6 (flipped at T6.5, 2026-05-23) | Consumes the `MultiWindowAgreement` stash on `blend_provenance`. (1) Demotes `observed_n > OBSERVED_MIN_ELIGIBILITY_N` AND `sign_agreement_count < 2` to Considered with `SIGNAL_INCONSISTENT_ACROSS_WINDOWS`. (2) For `*_band` builders enforces joint p<0.10 on BOTH L28 AND L28_band. (3) Rewrites `why_now` per the 3-state copy ladder (cold-start / accumulating / mature) keyed off `posterior_ratio = observed_n / (observed_n + pseudo_n)`. |
| `OBSERVED_MIN_ELIGIBILITY_N` | 30 (int) | S7.6 T6 | Minimum `observed_n` below which the eligibility gate is a no-op. |
| `ENGINE_V2_AOV_THRESHOLD_FROM_DATA` | true | S7.6 T7 (flipped at T7.5) | B-5 threshold-from-data primary: L90 P60 of net_sales when L90 order count ≥ 200; falls back to `cfg["AOV_BUNDLE_THRESHOLD_USD"]`; refuses `data_missing` when neither resolves. Unconditionally excludes supplements (reverts S7-T3.5 supplements B-5 activation). Emits `threshold_source` provenance. |

---

## S8 additive PlayCard fields + library

Per DS verdict 2026-05-24 §5 invariant 12: S8 caps the additive PlayCard
surface at three new fields. Each gets its own flag per atomic-flip
discipline (bundling would hide drift causation per the S7.6-T7.5 spiral).

| Flag | Default | Origin | Notes |
|---|---|---|---|
| `ENGINE_V2_TIER_CHIP` | true | S8 T1 (flipped at T1.5) | Populates `PlayCard.evidence_source = EvidenceSourceChip.STORE_OBSERVED` on the four wired Tier-B builders via the single `measurement_builder.build_prior_anchored_play_card` site. Tier-A / Tier-C / Tier-D / legacy plays NOT populated in scope. |
| `ENGINE_V2_SENSITIVITY` | true | S8 T2 (flipped at T2.5) | Populates `PlayCard.sensitivity = Sensitivity(...)` on the four wired Tier-B builders, validated non-suppressed BLEND path only. Suppressed and prior-unvalidated paths leave the field None. |
| `ENGINE_V2_EB_BLEND` | true | S8 T3 (flipped at T3.5) | Populates `PlayCard.provenance = Provenance(...)` on the validated non-suppressed BLEND path only. Audit-contract surface only — the empirical-Bayes blend math itself ships at `src/sizing.py` (S7.5-T3); no new pseudo_N numbers, no per-prior overrides. |
| `ENGINE_V2_PLAY_LIBRARY_WAVE1` | true | S8 T4 (flipped at T4.5) | Wave 1 = {winback_dormant_cohort, replenishment_due, discount_dependency_hygiene} migrated to `plays/<play_id>/` directory layout (spec.yaml + audience.py + builder.py + copy.md). Registry consults `plays.get_play_definition(play_id)` first for wave-1 plays and asserts spec.yaml-resolved callables are identity-equal to legacy callables. Refactor-only — zero behavioral change at both flag states. |

---

## S10–S13 predictive layer + consumer wiring — ML-fit gate LIVE at S13 (6 substrates with consumers; never demotes)

Sprint 10 ships the predictive substrate (BG/NBD at T1.5, Gamma-Gamma at T2.5)
and at T3 schema-additively adds the ML-fit ReasonCodes that S13 will consume.
Sprint 11 adds two more ML rungs to the same substrate layer (Cox PH survival
at T1.5 via `scikit-survival>=0.22,<0.24`; collaborative filtering at T2.5 via
`implicit>=0.7,<0.8`). Sprint 12 adds the final two substrates: **statistical
RFM at T1.5 (custom code, 11 named segments, internal-consistency Spearman +
quintile-coverage REFUSED guard)** and **cohort retention curves at T2.5
(custom code + numpy bootstrap, `RetentionCard` separate from `ModelCard`,
new top-level `EngineRun.cohort_diagnostics` slot, cumulative-monotonicity
REFUSED gate)**. The ML-fit substrate now spans **six predictive substrates**
(BG/NBD + Gamma-Gamma + Cox PH survival + CF/ALS + RFM + retention) but the
ML-fit gate itself is the FOURTH orthogonal demotion gate, lowest
precedence. At S12 close it stayed **DORMANT**; **at S13-T2.5 it transitioned
DORMANT → LIVE** — the emitter is wired via `PlayCard.model_card_ref.fit_warnings`
ONLY per **Q-S13-4 LOCK** (DS S13 plan review §B; `docs/DECISIONS.md::D-S13-1`).
ML-fit ReasonCodes (`MODEL_FIT_INSUFFICIENT_DATA`, `MODEL_FIT_REFUSED`) **NEVER
emit on `RejectedPlay.reason_code`** — ML-fit NEVER demotes between slate roles.
Contract anchors: `tests/test_s13_ml_fit_never_demotes.py` (5-fixture runtime +
month-2 extension); AST-aware `tests/test_reason_code_precedence_invariant.py`;
`src/engine_run.py:167-183` LOAD-BEARING comment.

The S12-T2 `cohort_diagnostics` slot is **architecturally distinct** from
`predictive_models`: cohort-aggregate diagnostics (NOT per-customer rankers)
land there. Retention is the first occupant; future cohort-AOV / cohort-frequency
/ churn-hazard-by-cohort diagnostics share this slot. See `docs/DECISIONS.md::D-S12-1`.

DS-locked precedence (2026-05-26): the four orthogonal gates rank as
`(1) audience-floor → (2) cohort p-value → (3) prior-validation → (4) ML-fit`.
ML-fit failure NEVER demotes a card between slate roles — it only triggers
silent fallback within audience ranking. Only gates (1)-(3) route to Considered.

| Gate | Position | Failure ReasonCodes | Effect when failing | Active at |
|---|---|---|---|---|
| Audience-floor | 1 (highest) | `AUDIENCE_TOO_SMALL` | Demote to Considered | live |
| Cohort p-value | 2 | `NO_MEASURED_SIGNAL`, `SIGNAL_INCONSISTENT_ACROSS_WINDOWS`, `WINDOW_DISAGREEMENT`, `MATERIALITY_BELOW_FLOOR` | Demote to Considered | live |
| Prior-validation | 3 | `PRIOR_UNVALIDATED` | Demote to Considered (route via `AbstainMode.SOFT_PRIOR_UNVALIDATED` at slate level) | live (S7.5) |
| ModelFitStatus (ML-fit) | 4 (lowest) | `MODEL_FIT_REFUSED`, `MODEL_FIT_INSUFFICIENT_DATA` (emit ONLY on `model_card_ref.fit_warnings` per Q-S13-4 LOCK; **NEVER on `RejectedPlay.reason_code`**) | Silent fallback to next strategy in the ranking chain; **never demotes** between slate roles | dormant at S10; **LIVE at S13-T2.5** |

Ranking-strategy fallback chain (S13 will wire):
`BG/NBD → CF → survival → RFM (floor) → recency`. **RFM is the explicit
floor of the chain — the last deterministic-segmentation strategy before
the recency last-resort.** A REFUSED / INSUFFICIENT_DATA ModelFitStatus on
the strongest strategy silently degrades to the next; the card itself stays
in its assigned slate role.

The two `MODEL_FIT_*` ReasonCodes are schema-additive within `event_version=1`
at S10-T3 close. At S13-T2.5 the emitter wired LIVE — but only via
`PlayCard.model_card_ref.fit_warnings` (the `List[str]` channel) per Q-S13-4
LOCK. The negative invariant — `ReasonCode.MODEL_FIT_*` never appears as a
`RejectedPlay.reason_code` value — is held by the AST-aware refactor of
`tests/test_reason_code_precedence_invariant.py` at S13-T2 + the runtime
5-fixture `tests/test_s13_ml_fit_never_demotes.py` (extended at T3.5 with a
month-2 sequence per DS S13 plan review §F).

### S11 predictive flags

| Flag | Default | Origin | Notes |
|---|---|---|---|
| `ENGINE_V2_ML_SURVIVAL` | true | S11 T1 (flipped at T1.5, 2026-05-26) | Cox PH survival substrate via `scikit-survival>=0.22,<0.24` (NOT `lifelines` — DS substitution per S11 plan review §B; same Cox PH math, better-maintained, sklearn-ecosystem-backed). Dual gate: `holdout_c_index ≥ stage_floor` AND `holdout_brier_score_90d ≤ stage_ceiling`. **CHAINS BG/NBD** — when BG/NBD is REFUSED/INSUFFICIENT_DATA, survival short-circuits with `chained_bgnbd_refusal`. Parquet write only for VALIDATED/PROVISIONAL. |
| `ENGINE_V2_ML_CF` | true | S11 T2 (flipped at T2.5, 2026-05-28) | Collaborative filtering substrate via `implicit>=0.7,<0.8` (ALS). PRIMARY gating metric `holdout_top_k_recall@10`; `coverage_at_k` is operator-visible diagnostic only (does NOT gate). **INDEPENDENT of BG/NBD** — `fit_cf` API takes no `bgnbd_model_card` argument (4-layer pin: docstring + signature + Case D rollback test + YAML comment). Stage-keyed `min_customers` / `min_items` / `min_interactions_per_user` floors. Parquet write only for VALIDATED/PROVISIONAL. |

**Ranking-strategy fallback chain (DS-locked, S13 will wire):**
`BG/NBD → CF → survival → RFM → recency`. RFM is the **floor**; recency is the
**absolute last-resort**. A REFUSED / INSUFFICIENT_DATA ModelFitStatus on the
strongest strategy silently degrades to the next; the card itself stays in its
assigned slate role (ML-fit never demotes between slate roles per precedence
rule above).

### S11 audit copy (operator-readable)

Two audit cases are explicit on the operator surface (renderer-side at S13):

- **Beauty-replenishment_due dormancy story (DS S11 plan review §B.8 verbatim):**
  "INSUFFICIENT_DATA on Beauty's first 90 days is EXPECTED — repeat-purchase
  events haven't accumulated; this is product correctness, not a calibration
  failure."
- **Orthogonal-failure case (DS S11 plan review §A.5):** the outcome
  "BG/NBD VALIDATED + survival REFUSED" is a *valid orthogonal-failure case*
  (BG/NBD ranks repeat propensity well, but Cox PH covariates don't add
  discriminative power → REFUSED on `c_index < 0.55`), not a contradiction. The
  reverse — BG/NBD REFUSED → survival VALIDATED — is impossible by chained-refusal
  construction; that's the load-bearing invariant on the survival side.

### S12 predictive flags

| Flag | Default | Origin | Notes |
|---|---|---|---|
| `ENGINE_V2_ML_RFM` | true | S12 T1 (flipped at T1.5, 2026-05-28) | Statistical RFM substrate (custom code; no third-party library). 11 named segments (Champions / Cannot Lose Them / Loyal Customers / At Risk / Need Attention / Potential Loyalists / Promising / New Customers / About To Sleep / Hibernating / Lost). PRIMARY gating: `segment_monotonicity_spearman` (internal-consistency; rank-order of segments vs observed mean monetary per segment) — **NOT a holdout / fit-quality metric**. SECONDARY REFUSED guard: `quintile_coverage_min < 0.05` (binary edge-collapse detector). **INDEPENDENT of BG/NBD** — `fit_rfm` API takes no `bgnbd_model_card` argument (4-layer pin: docstring + signature + Case D rollback test + YAML comment). **RFM is the explicit floor of the S13 ranking-strategy chain.** Stage-keyed VALIDATED Spearman floors: startup 0.60 / growth 0.65 / mature 0.70 / enterprise 0.70 (PROVISIONAL floor 0.40). Parquet write only for VALIDATED/PROVISIONAL. |
| `ENGINE_V2_ML_RETENTION` | true | S12 T2 (flipped at T2.5, 2026-05-28) | Cohort retention curves with bootstrapped CIs (custom code + numpy percentile bootstrap; no third-party library). Writes a NEW `RetentionCard` dataclass (separate from `ModelCard`; reuses `ModelFitStatus` enum via Option A vocab-stacking) to the NEW top-level `EngineRun.cohort_diagnostics["retention"]` slot — **NOT `predictive_models`** (see `docs/DECISIONS.md::D-S12-1`). PRIMARY gating: stage-keyed `bootstrap_ci_width_at_month_3` ceilings (startup 0.25 / growth 0.20 / mature 0.15 / enterprise 0.15; PROVISIONAL ceiling 0.35). **REFUSED gate: cumulative-retention monotonicity violation** (cumulative "ever-returned in [first_month+1, first_month+M]" cannot mathematically decrease — violation signals data-shape pathology). **INDEPENDENT of BG/NBD** — `fit_retention` API takes no `bgnbd_model_card` argument. **NO parquet artifact** — curves are JSON-shaped and land directly on `cohort_diagnostics["retention"]["cohorts"]`. |

### S12 audit copy (operator-readable)

- **RFM REFUSED on `quintile_collapse` (synthetic Beauty/Supplements/mid_shopify/micro_coldstart):** "Synthetic monetary distributions don't support full quintile decomposition under `pd.qcut`; this is the data-shape gate working as designed." Four of five pinned fixtures land REFUSED at S12-T1.5 via this guard (only `small_sm` clears with Spearman=0.93). Pivot-5-consistent honest surfacing; real-merchant calibration of monetary-DGP breadth deferred to S14 per `KI-NEW-V.2`.
- **Retention `cumulative_retention_monotonicity_violation` REFUSED:** "Cumulative retention cannot mathematically rise on the standard 'ever-returned' definition; violation = data-shape pathology (NOT a calibration miss)." Promoted from tertiary diagnostic to REFUSED gate per DS S12 plan review §G.
- **Retention CI=0.0 degenerate-bootstrap on Supplements (`healthy_supplements_240d`, n=38):** synthetic cohort with identical Bernoulli outcomes produces CI=0.0 — mechanically clears the VALIDATED gate. Structural-correctness signal, NOT a predictive-accuracy claim. Closure trigger = S14 real-merchant calibration of `min_cohort_size_floor` (currently 20; likely tighten to ~100 once real distributions observed). See `KI-NEW-T`.

### S13 consumer-wiring flags (ML-fit gate ACTIVATION)

| Flag | Default | Origin | Notes |
|---|---|---|---|
| `ENGINE_V2_RANKING_STRATEGY_CHAIN` | true | S13 T1 (flipped at T1.5, 2026-05-29) | NEW `src/predictive/ranking_strategy.py` module. `AudienceIntent` str-Enum (`GENERAL` / `REPLENISHMENT_TIMING` / `LOOKALIKE_EXPANSION`) + frozen `_CHAIN_ORDER_BY_INTENT` mapping + `rank_audience(predictive_models, intent) -> RankingStrategyResult` pure walker. DS-LOCKED selection rule (S13 plan review §D.1): PROVISIONAL never falls through to a downstream VALIDATED. Reads `card.fit_status` as a real dataclass field (NOT via legacy `__getattr__` shim — S15+ shim-removal forward-compat). `fit_warnings` grammar `"{LEVEL}:{substrate}"` strict — 3 LEVELS: `PROVISIONAL_SELECTED`, `MODEL_FIT_INSUFFICIENT_DATA`, `MODEL_FIT_REFUSED` (`docs/DECISIONS.md::D-S13-4`). At T1.5 the flag flips ON but NO consumer wires until T2. |
| `ENGINE_V2_PLAY_PREDICTED_SEGMENT` | true | S13 T2 (flipped at T2.5, 2026-05-29) | NEW `src/predictive/consumer_wiring.py::populate_play_card_consumers`. Walks `engine_run.recommendations`, calls `rank_audience()` per card, populates `PlayCard.model_card_ref` (`strategy_used`, `fit_status_chain`, `fit_warnings`). Populates `PlayCard.predicted_segment.segment_name` from per-store RFM parquet under the **modal-segment stability floor** (`n_audience<50` OR `audience_modal_share<0.30` → `segment_name=None`; audit fields uncensored; `docs/DECISIONS.md::D-S13-2`). Hardcoded `_INTENT_BY_PLAY_ID` map (5-entry closed: `replenishment_due → REPLENISHMENT_TIMING`; all other Tier-B builders → `GENERAL`; unknown → `GENERAL`). YAML promotion at S14 tracked at `KI-NEW-Y`. Pure attribute mutation via `dataclasses.replace`; **NO append to `recommendations` or `considered`** (single-demote-channel invariant preserved). **At T2.5 the ML-fit gate transitioned DORMANT → LIVE.** Wire-site is Option II (post-injection, after `apply_guardrails_to_injected`); DS-adjudicated technically correct, process discipline note at `KI-NEW-Z`. |
| `ENGINE_V2_MONTH_2_DELTA` | true | S13 T3 (flipped at T3.5, 2026-05-29) | NEW `src/predictive/month_2_delta.py::detect_month_2_delta`. Populates `EngineRun.month_2_delta: Optional[MonthDelta]`. **Substrate-state-delta per Pivot 8** — NOT realized-outcome delta; cold-start month-2-return flows through EB n_observed shift, not ML refit. Diffs 6 substrates (BG/NBD + G-G + survival + CF + RFM + retention); absent-on-one-side surfaces as `ABSENT`. **21-day floor** (D-S13-3 LOCKED): MonthDelta does NOT populate when `days_between < 21`. **Lineage-change constraint** (D-S13-3): `segment_shifts=None` (suppressed) when `audience_definition_version` bumps; substrate-fit-status comparable; retention CI delta comparable. Orchestration wire-site is AFTER T2 consumer-wiring at `src/main.py:2040+` (NOT in forbidden `L1380-1597`). Mutates `engine_run.month_2_delta` IN-PLACE via attribute assignment ONLY; failures degrade silently with warning log. |

### S13 audit copy (operator-readable)

- **ML-fit ReasonCode emission channel (Q-S13-4 LOCK verbatim per DS S13 plan review §B):** "ML-fit ReasonCodes (`MODEL_FIT_INSUFFICIENT_DATA`, `MODEL_FIT_REFUSED`) emit ONLY on `PlayCard.model_card_ref.fit_warnings` per PlayCard. **NEVER on `RejectedPlay.reason_code`** — ML-fit never demotes between slate roles; only gates (1)–(3) above route to Considered. Structural-incoherence rationale: a card cannot be both in Recommended Now (slate role) AND in Considered (demoted role) for the same `play_id`; ML-fit failure is silent fallback within audience ranking, not a slate-role transition."
- **`fit_warnings` grammar (D-S13-4 LOCKED):** `List[str]` with `"{LEVEL}:{substrate}"` prefix format. 3 LEVELS: `PROVISIONAL_SELECTED` (chain walker selected a PROVISIONAL fit because no upstream VALIDATED existed); `MODEL_FIT_INSUFFICIENT_DATA` (substrate REFUSED on data-floor); `MODEL_FIT_REFUSED` (substrate REFUSED on fit-quality gate). Operator parses by `.split(":", 1)`.
- **AudienceIntent enum (S13-T1):** 3 closed values. `GENERAL` (default; full chain `BG/NBD → CF → survival → RFM → recency`). `REPLENISHMENT_TIMING` (head reordered to `SURVIVAL → BG/NBD → ...` because cadence-distribution is the primary signal). `LOOKALIKE_EXPANSION` (head reordered to `CF → BG/NBD → ...` because item-affinity is the primary signal). Intent-conditional reorderings are DS-locked at S13 plan review §D.1.
- **Modal-segment stability floor (D-S13-2 LOCKED):** `predicted_segment.segment_name = None` when `n_audience < 50` OR `audience_modal_share < 0.30`. Audit fields (`audience_modal_share`, `n_audience`) populate uncensored regardless — operators can read the floor outcome without inferring it. Calibration in `KI-NEW-P` consumer-side cells.
- **month_2_delta 21-day floor (D-S13-3 LOCKED):** `MonthDelta` does NOT populate when `days_between < 21`. Prevents intra-cycle noise from being read as month-over-month state change. Calibration in `KI-NEW-P` consumer-side cells.
- **month_2_delta lineage-change constraint (D-S13-3 LOCKED):** when `audience_definition_version` bumps between prior and current runs, `segment_shifts` is suppressed (= `None`) with a `"lineage_changed_segment_shift_incomparable"` note. Substrate-fit-status changes remain comparable; retention CI delta remains comparable. Without this constraint, a v1→v2 audience definition would appear to "shift segments" mechanically — fabrication.
- **§G.3 three-precondition framing (S13-T3-CLOSE, per DS T3 Q2 adjudication; `PIVOTS.md::Pivot 5` clarifier):** `predicted_segment.segment_name` populates structurally whenever (a) RFM substrate VALIDATED, (b) modal-segment floor cleared (`n_audience≥50` AND `modal_share≥0.30`), AND (c) DECIDE produces ≥1 PlayCard for the audience. **`small_sm` satisfies (a) but not (c) under default flags** — this is the four-gate architecture working as designed, NOT a defect. See `KI-NEW-X`.
- **small_sm honest finding (Pivot 5):** RFM VALIDATED on `small_sm` (Spearman=0.93 per S12-T1.5) but DECIDE produces 0 PlayCards under default flags → `predicted_segment.segment_name` never populates because there's no PlayCard for the consumer-wiring loop to attach it to. Operator reading: "the RFM substrate fits, but the slate is empty, so there's nothing to predict-segment for." Honest dormancy per Pivot 5; closure remains S14 real-merchant calibration.

---

## Pre-V2 statistical flags (mostly deletion candidates)

| Flag | Default | Origin | Notes |
|---|---|---|---|
| `STATS_NAN_FOR_HARDCODED` | false | M4a | Replaces fabricated p-values with NaN when ON. Will become default. |
| `EVIDENCE_CLASS_ENFORCED` | false | M4a | Evidence-class enforcement at decide-layer. |
| `ENABLE_COHORT_POOLING` | false | M4a T4a.8 (flipped from true) | Placeholder p=1.0 path; cohort pooling deprecated. Deletion candidate. |
| `ENABLE_REPEAT_RATE_BIAS_CORRECTION` | false | M4a T4a.8 (flipped from true; T5.6 confirms) | Hardcoded window-specific multiplier {7:1.0, 28:0.95, 56:0.90, 90:0.85} flagged as fabricated. Deletion candidate. |
| `ENABLE_ENHANCED_STATISTICS` | true | pre-V2 | Superseded by combiner reroute. Deletion candidate. |
| `ENABLE_MULTIWINDOW_SCORING` | true | pre-V2 | Multi-window analysis on. |
| `_FORCE_SINGLE_WINDOW` | false | M0 T0.4 | Explicit cfg key for M4-era decision-logic surgery; do not flip casually. |

---

## Guardrail engine flags (M5 vintage)

| Flag | Default | Origin | Notes |
|---|---|---|---|
| `INVENTORY_GATE_ENABLED` | false | M5 | Hard inventory gate. Slated to become default. |
| `ANOMALY_GATE_ENABLED` | true | M5 B-1 | Detector already runs in adapter; routes populated `data_quality_flags` into ABSTAIN_HARD (hard flags) or ABSTAIN_SOFT (POST_PROMO_WINDOW). Healthy fixtures produce zero flags so M0 byte-identical holds. |
| `CANNIBALIZATION_GATE_ENABLED` | false | M5 | Replaces `OVERLAP_MAX_RATIO`. |
| `MATERIALITY_FLOOR_SCALE_AWARE` | false | M5 | Scale-aware materiality. |
| `RECENTLY_RUN_FATIGUE_ENABLED` | false | M5 (Sprint 1 B-4/S-1 confirms OFF) | Reads gitignored `data/recommended_history.json` as read-only stub; the recently-run-fatigue gate is keyed on `(play_id, audience_definition_id, store_id)`. Stays OFF for beta month-1 (no learning loop by design per project_beta_no_learning_loop). |

---

## Outcome log (M9)

| Flag | Default | Origin | Notes |
|---|---|---|---|
| `OUTCOME_LOG_ENABLED` | true | M9 | Appends per-run JSON record to `data/recommended_history.json` (gitignored). Privacy-safe: persists `audience.id` and `audience.size`, never raw customer IDs or order-line PII. Missing file: created. Malformed file: moved aside as `<path>.corrupt-<UTC-ts>.bak`. The merchant briefing is never blocked. Each record carries `measurement.p_internal`, `ci_internal`, `observed_effect`, `n`, and revenue-range `drivers` for the internal `receipts/debug.html`. |
| `OUTCOME_LOG_PATH` | "" | M9 | Override default `data/recommended_history.json`. Empty = default. Useful for tests / ops. |

In Phase 1 the file is NOT consumed by the engine. The future calibration
layer (`src/calibration_stub.load_realization_factors`) is present as an
interface anchor only and returns the empty contract dict.

---

## Thresholds and sample-size knobs

| Flag | Default | Read in |
|---|---|---|
| `MIN_N_WINBACK` | 75 (current `.env`: 150) | action_engine |
| `MIN_N_SKU` | 30 (current `.env`: 75) | action_engine |
| `AOV_EFFECT_FLOOR` | 0.02 (current `.env`: 0.05) | action_engine |
| `REPEAT_PTS_FLOOR` | 0.02 (current `.env`: 0.03) | action_engine |
| `DISCOUNT_PTS_FLOOR` | 0.02 (current `.env`: 0.05) | action_engine |
| `FDR_ALPHA` | 0.15 | stats / action_engine |
| `MIN_SAMPLE_SIZE_FREQUENCY` | 20 | action_engine |
| `MIN_SAMPLE_SIZE_RETENTION` | 15 | action_engine |
| `MIN_SAMPLE_SIZE_JOURNEY` | 15 | action_engine |
| `MIN_SAMPLE_SIZE_AOV` | 4 | action_engine |
| `STATISTICAL_SIGNIFICANCE_THRESHOLD` | 0.1 | action_engine |
| `MATERIALITY_PCT` | 0.025 | action_engine |
| `N_SCALE` | 100 | action_engine.confidence |
| `EFFECT_BOOST_FACTOR` | 0.3 | action_engine.confidence |
| `PILOT_AUDIENCE_FRACTION` | 0.3 | action_engine |
| `PILOT_BUDGET_CAP` | 150.0 | action_engine |
| `EFFORT_BUDGET` | 8 | action_engine |
| `GROSS_MARGIN` | 0.70 | main / action_engine |

---

## Window + seasonality knobs

| Flag | Default | Read in |
|---|---|---|
| `WINDOW_POLICY` | "auto" (current `.env`: L28) | utils.choose_window |
| `L7_MIN_ORDERS` | 150 | utils.choose_window |
| `L28_MIN_ORDERS` | 250 | utils.choose_window |
| `L56_MIN_ORDERS` | 350 | utils.choose_window |
| `L90_MIN_ORDERS` | 400 | utils.choose_window |
| `SEASONAL_ADJUST` | true | utils.kpi_snapshot |
| `SEASONAL_PERIOD` | 7 | utils.kpi_snapshot |

---

## Financial floor

| Flag | Default | Read in |
|---|---|---|
| `FINANCIAL_FLOOR` | 300.0 | utils |
| `FINANCIAL_FLOOR_MODE` | "auto" (auto\|fixed) | utils.financial_floor |
| `FINANCIAL_FLOOR_FIXED` | 300.0 | utils.financial_floor |

---

## Inventory knobs

| Flag | Default | Read in |
|---|---|---|
| `INVENTORY_ENFORCEMENT_MODE` | "soft" (soft\|hard) | action_engine |
| `INVENTORY_MAX_AGE_DAYS` | 7 | action_engine |
| `INVENTORY_SAFETY_STOCK` | 0 | load.compute_inventory_metrics |
| `INVENTORY_LEAD_TIME_DAYS` | 14 | load.compute_inventory_metrics |
| `INVENTORY_SAFETY_Z` | 1.64 (~90% service level) | load.compute_inventory_metrics |
| `INVENTORY_MIN_COVER_DAYS_MAP` | "" (JSON/CSV map) | utils.parse_cover_days_map |
| `INVENTORY_ALLOW_BACKORDER` | true | action_engine |

---

## Display, vertical, confidence

| Flag | Default | Read in | Notes |
|---|---|---|---|
| `VERTICAL_MODE` | "mixed" (current `.env`: beauty) | utils + action_engine | beauty\|supplements\|mixed |
| `SUBVERTICAL` | "general" | utils.seasonality | fitness\|wellness\|skincare\|haircare\|makeup\|general (affects seasonality only) |
| `CHARTS_MODE` | "detailed" (current `.env`: minimal) | charts | detailed\|compact |
| `SHOW_L7` | true (current `.env`: False) | briefing template | |
| `CONFIDENCE_MODE` | "learning" | action_engine | conservative\|aggressive\|learning. **PM-blocked**: do not add new values; existing semantics frozen until evidence_class + label collapse lands. |
| `INTERACTION_FACTORS` | "" | utils.parse_interaction_factors | JSON or CSV (see `src/utils.py` doc) |
| `CHANNEL_CAPS` | `{"email":2,"sms":1}` | action_engine | |
| `CONFLICT_PAIRS` | `["discount_hygiene->winback_21_45", "winback_21_45->discount_hygiene"]` | action_engine | |
| `OVERLAP_MAX_RATIO` | 0.6 | action_engine | M5 cannibalization gate replaces. |
| `MIN_UNIQUE_AUDIENCE` | 400 | action_engine | |
| `FEATURES_DYNAMIC_PRODUCTS` | false (current `.env`: true) | main | |
| `FEATURES_PRODUCT_NORMALIZATION` | false (current `.env`: true) | main | |
| `CONCIERGE_MODE` | true | action_engine | informational |
| `MANUAL_VALIDATION_THRESHOLD` | 5 | validation | informational |
| `CUSTOMER_FEEDBACK_REQUIRED` | true | validation | informational |
| `VALIDATION_ALERT_CRITICAL` | true | validation | informational |

---

## Direct env reads (not in `DEFAULTS`)

These flags bypass `get_config()` and are read inline via `os.getenv()`.

| Variable | Default | Read in | Notes |
|---|---|---|---|
| `VERTICAL_MODE` / `VERTICAL` | `"mixed"` | `utils.get_vertical_mode` | Redundant with cfg key; kept for legacy compat. |
| `SUBVERTICAL` | `"general"` | `utils.get_subvertical` | Redundant with cfg key. |
| `ENABLE_COHORT_POOLING` | `"false"` | `utils.DEFAULTS` initialization | Deletion candidate. |
| `ENABLE_REPEAT_RATE_BIAS_CORRECTION` | `"false"` | `utils.DEFAULTS` initialization | Deletion candidate. |
| `L7_MIN_ORDERS` / `L28_MIN_ORDERS` / `L56_MIN_ORDERS` / `L90_MIN_ORDERS` | inherited | `utils.choose_window` | Redundant with cfg key. |
| `FINANCIAL_FLOOR_MODE` | `"auto"` | `utils.financial_floor` | Redundant with cfg key. |
| `FINANCIAL_FLOOR_FIXED` | `DEFAULTS["FINANCIAL_FLOOR"]` | `utils.financial_floor` | Redundant. |
| `F2S_WINDOW_DAYS` | `"0"` | `charts.py` ~line 1215 | Likely chart-only override. |
| `CHARTS_MODE` | `"detailed"` | `charts.py` ~line 2002 | Redundant with cfg key. |
| `ENGINE_DEBUG_CATEGORIES` | `""` | `action_engine.py` ~line 43 | Dev-only debug switch listing category names to verbose-log. |
| `BUSINESS_STAGE` | `""` (current `.env`: mature) | `action_engine.py` ~line 74 | Stage thresholds; PROFILE layer (S6.5) now owns stage detection but legacy read remains. |
| `ANNUAL_REVENUE` | `0` | `action_engine.py` ~line 80 | Used for stage auto-detect when set. |

---

## Outcome-log behavior summary

`OUTCOME_LOG_ENABLED` controls whether the engine appends a JSON record per
run to `data/recommended_history.json` (or the path in `OUTCOME_LOG_PATH`).

- Default true. Writes are local, deterministic, gitignored.
- Each record carries `store_id`, `run_id`, `anchor_date`, `decision_state`,
  recommended plays (with internal evidence diagnostics —
  `measurement.p_internal`, `ci_internal`, `observed_effect`, `n`, plus
  revenue-range `drivers`), considered/rejected plays (with reason codes),
  and key revenue/scale metadata.
- Privacy-safe: persists `audience.id` and `audience.size`, never raw
  customer IDs or order-line PII.
- Missing file: created on first run.
- Malformed file: moved aside as `<path>.corrupt-<UTC-ts>.bak`; the run
  continues with a fresh list and reports `recovered_from_corrupt` in the
  writer status. The merchant briefing is never blocked.
- Internal diagnostics persisted here are mirrored in the
  merchant-INVISIBLE `receipts/debug.html` page, which is NOT linked from
  the merchant-facing briefing.

The recently-run-fatigue gate reads the file as a read-only stub when
`RECENTLY_RUN_FATIGUE_ENABLED=true`. The calibration stub
(`src/calibration_stub.load_realization_factors`) is an interface anchor
only and returns the empty contract dict
`{prior_overrides: {}, evidence_thresholds: {}, materiality_overrides: {}}`.

To disable outcome logging entirely, set `OUTCOME_LOG_ENABLED=false`.

---

## Running the golden regression

The golden regression remains the canonical proof-of-no-regression for every
behavior-touching ticket.

```bash
make test
# or
python -m pytest tests/test_golden_diff.py
```

Regenerate goldens only when a ticket explicitly authorizes a behavior
change:

```bash
make golden-regenerate
# or
python scripts/freeze_golden.py --regenerate
```

When goldens change, the PR description must include a justification line:

> Goldens regenerated for ticket T<sprint>.<n> -- <one-line reason>.

Restrict to a single merchant:

```bash
python scripts/freeze_golden.py --regenerate --merchant small_sm
```

The fixture spec lives at `tests/fixtures/merchants.yaml`. The golden tree
lives at `tests/golden/{merchant_id}/`.

---

## Open questions

No DEFAULTS entries currently lack a documented home. All flags above trace
to either a sprint closeout in `memory.md`, a verdict file under
`agent_outputs/`, or `ARCHITECTURE_PLAN.md`. If a new flag lands without
clear lineage, it should be added here in this section pending verdict
linkage rather than guessed-at in the main tables.

Items worth flagging for future cleanup but not blocking:

- The `M0–M10` legacy framing in old PR descriptions does not match the
  current sprint vocabulary (S6 / S6.5 / S7 / S7.5 / S7.6 / S8). The flags
  themselves are accurately catalogued here; the milestone-tag language is
  historical only.
- `BUSINESS_STAGE` and `ANNUAL_REVENUE` direct env reads still live in
  `action_engine.py` even though the S6.5 PROFILE layer now owns stage
  resolution. Removal is deferred until the legacy action_engine path
  is fully retired.
- `_FORCE_SINGLE_WINDOW` is an explicit cfg key for the M4-era decision
  logic surgery and has no current owner; left in place per the M0 freeze
  contract.
