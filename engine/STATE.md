# STATE.md — What is true in the BeaconAI engine right now

**Cadence:** Live. Updated at every sprint close.
**Last refresh:** 2026-06-03 (post S-FE additive schema bump to v2.1.0).
**Scope:** Current pipeline, current slate, current invariants, current beta-readiness.
**Out of scope:** History, supersession chains, why prior shapes were rejected (see `PIVOTS.md`), what's next (see `ROADMAP.md`).

If you are an agent or human asking *"what does the engine do today?"* — this file answers in one pass.

---

## 1. Engine pipeline today

Every play in the registry passes through 5 sequential layers on each monthly run:

```
PROFILE  →  AUDIENCE  →  MEASUREMENT  →  SIZING  →  DECIDE
```

| Layer | Question it answers | Today's source of truth |
|---|---|---|
| **PROFILE** | What kind of store is this? Vertical × sub-vertical × stage × cadence. Determines audience floors, materiality floors, primary window (e.g., L28 vs L60), and seasonality calendar. | `src/store_profile.py`, gated by `ENGINE_V2_STORE_PROFILE`. Stage-aware `pseudo_n_default` may only *lower* the per-status cap. |
| **AUDIENCE** | Given the CSV, who are the customers this play targets? | `src/audience_builders.py`. One audience builder per play. |
| **MEASUREMENT** | What evidence does this store actually show for this play? Cohort signal, p-value, sign-agreement across windows. | `src/measurement_builder.py`. `_SUPPORTED` registry + `_PRIOR_ANCHORED` registry (the five Tier-B builders). Observed-effect populated at `src/measurement_builder.py:2252-2270`. |
| **SIZING** | Given audience size, AOV, and a validated prior, what defensible revenue range can we publish? | `src/sizing.py`. `bayesian_blend` + `effective_pseudo_n` + `PSEUDO_N_BY_STATUS`. Refusal-first on unvalidated priors. |
| **DECIDE** | Does this clear the three orthogonal gates? Which slate lane? | `src/decide.py`. Slate assembly, role-uniqueness, demote-channel routing, considered truncation. |

The engine runs this pipeline once per play in the registry, then ranks the results into a slate. Output is a typed `engine_run.json`. `briefing.html` is debug-only and will retire when the frontend app activates.

---

## 2. The slate (engine output today)

Four lanes, capped:

| Lane | Meaning | Cap |
|---|---|---|
| **Recommended Now** | Send this. Evidence is on the merchant's store. | ≤ 3 |
| **Recommended Experiment** | Try this. Industry pattern + audience fits. Measure after. | ≤ 2 |
| **Considered** | We looked at this; here's why we didn't recommend it (typed `ReasonCode`). | ≤ 6 rendered |
| **Watching** | Not ready yet; tracking the signal that would trigger it. | ≤ 4 |

If no play clears the gates → `ABSTAIN_SOFT` (slate empty above the fold; typed reason emitted).

### Role-uniqueness invariant
No `play_id` appears in more than one of {Recommended Now, Recommended Experiment, Considered} in a given run. Watching is exempt by design. Enforced at the DECIDE seam (Phase 6A Ticket B4).

---

## 3. Evidence tiers

Every `PlayCard` carries a typed `evidence_source` chip (S8-T1, default ON):

| Tier | `evidence_source` value | Lane | Meaning |
|---|---|---|---|
| **A — Causal** | `STORE_MEASURED` | Recommended Now | Lift measured on this store via counterfactual. Requires Phase 9 outcome history. Not produced today. |
| **B — Directional** | `STORE_OBSERVED` | Recommended Now | Cohort signal observed on this store; industry-validated prior anchors the revenue range via Bayesian blend. |
| **C — Prior** | `INDUSTRY_PRIOR` | Recommended Experiment | Validated prior + audience fits; no store cohort signal yet. |
| **D — Observational** | `OBSERVATIONAL` | Considered | Audience identified, no effect claim. |

The legacy `measured | directional | targeting | weak` enum is retired in the V2 typed surface.

---

## 4. The orthogonal gates — three active + one LIVE

A play surfaces only if it clears the active orthogonal gates, each protecting a different failure mode. Today: **three active + one LIVE** (the ML-fit gate transitioned **DORMANT → LIVE at S13-T2.5**; substrate landed at S10 and extended at S11–S12 to six predictive substrates — BG/NBD + Gamma-Gamma + Cox PH survival + CF/ALS + RFM + retention — and S13 wired the consumers).

| Gate | Question | Layer | Status | Failure mode it protects against |
|---|---|---|---|---|
| **Audience-floor gate** | Does the audience clear the per-vertical / per-stage materiality floor? | AUDIENCE | ACTIVE | Recommending a play whose audience is too small to matter. |
| **Cohort p-value gate** | Is the cohort-level signal real or noise? `p < 0.05` on supporting metric + sign-agreement across windows (joint-p < 0.10 amendment per S7.6 T6.5). | MEASUREMENT | ACTIVE | Surfacing noise as evidence. |
| **Prior-validation gate** | Can we defend the prior anchoring this revenue range? | SIZING | ACTIVE | Laundering unvalidated heuristics as Bayesian math. |
| **ML-fit gate (`ModelFitStatus`)** | Can we trust ML scores per-customer on this merchant? Four-state enum {VALIDATED, PROVISIONAL, INSUFFICIENT_DATA, REFUSED}. Substrate spans **6 predictive substrates with CONSUMERS at S13** (BG/NBD + Gamma-Gamma + Cox PH survival + CF/ALS + RFM + retention). Per-customer rankers (5 substrates) write `ModelCard`s to `EngineRun.predictive_models`; the cohort-aggregate retention substrate writes a `RetentionCard` to the top-level `EngineRun.cohort_diagnostics` slot. | AUDIENCE | **LIVE — emitter wired at S13-T2.5; ML-fit NEVER demotes (precedence-pin)** | Per-customer ranking on a misfit model. |

The three active gates are orthogonal: a play with strong cohort signal + heuristic-unvalidated prior surfaces in Recommended Now with a *suppressed* revenue range, not no card.

**ML-fit gate LIVE behavior (post-S13):** ML-fit is the **lowest precedence** of the four — it **NEVER demotes between slate roles**. Per Q-S13-4 LOCK (DS S13 plan review §B; `docs/DECISIONS.md::D-S13-1`), ML-fit ReasonCodes (`MODEL_FIT_INSUFFICIENT_DATA`, `MODEL_FIT_REFUSED`) emit **ONLY on `PlayCard.model_card_ref.fit_warnings`**, and **NEVER on `RejectedPlay.reason_code`**. ML-fit triggers a silent fallback **within audience ranking**: `BG/NBD → CF → survival → RFM (floor) → recency` (RFM = floor; recency = last-resort). DS-locked precedence: `(1) audience-floor → (2) cohort p-value → (3) prior-validation → (4) ML-fit`. **Contract anchors:** `tests/test_s13_ml_fit_never_demotes.py` 5-fixture runtime + month-2 extension; AST-aware `tests/test_reason_code_precedence_invariant.py`; `src/engine_run.py:167-183` LOAD-BEARING comment.

**New typed slots LIVE at S13:**
- **`PlayCard.predicted_segment`** — populated by `src/predictive/consumer_wiring.py::populate_play_card_consumers` per `predicted_segment.segment_name` with the modal-segment stability floor (`n_audience<50` OR `audience_modal_share<0.30` → `segment_name=None`; audit fields uncensored; `docs/DECISIONS.md::D-S13-2`).
- **`PlayCard.model_card_ref`** — populated with `strategy_used`, `fit_status_chain`, `fit_warnings` (grammar `"{LEVEL}:{substrate}"` per `docs/DECISIONS.md::D-S13-4`; 3 LEVELS: `PROVISIONAL_SELECTED`, `MODEL_FIT_INSUFFICIENT_DATA`, `MODEL_FIT_REFUSED`).
- **`EngineRun.month_2_delta`** — populated by `src/predictive/month_2_delta.py::detect_month_2_delta` as **substrate-state-delta** per Pivot 8 (NOT realized-outcome delta; cold-start month-2 flows through the EB n_observed shift, not ML refit). 21-day floor + lineage-change constraint per `docs/DECISIONS.md::D-S13-3`.

**Ranking-strategy chain at S13 LIVE:** `BG/NBD → CF → survival → RFM (floor) → recency`. Intent-conditional reorderings per `AudienceIntent` str-Enum (`GENERAL` / `REPLENISHMENT_TIMING` / `LOOKALIKE_EXPANSION`); `_INTENT_BY_PLAY_ID` is hardcoded at S13 (5-entry closed map; promotion to `config/play_intents.yaml` tracked at `KNOWN_ISSUES.md::KI-NEW-Y`).

**ML substrate composition rules (S11+S12-locked):** survival CHAINS BG/NBD (`fit_survival` takes `bgnbd_model_card`; chained-refusal short-circuits when BG/NBD is REFUSED/INSUFFICIENT_DATA). CF, RFM, and retention are **INDEPENDENT of BG/NBD** (their `fit_*` APIs take no `bgnbd_model_card` argument; 4-layer pin per substrate: docstring + signature + Case D rollback test + YAML comment). The "BG/NBD VALIDATED + survival REFUSED" outcome is a *valid orthogonal-failure case* (covariates don't add discriminative power), not a contradiction.

**`cohort_diagnostics` vs `predictive_models` (S12-T2 lock):** `EngineRun.cohort_diagnostics: Dict[str, Any]` is architecturally distinct from `predictive_models`. Cohort-aggregate diagnostics (NOT per-customer rankers) land there; retention is the first occupant. `RetentionCard` is a NEW dataclass alongside `ModelCard`, reusing the `ModelFitStatus` enum via Option A vocab-stacking; cumulative-retention monotonicity violation is a REFUSED gate. No parquet artifact for retention (curves are JSON-shaped). See `docs/DECISIONS.md::D-S12-1`.

---

## 5. Current invariants (load-bearing in production today)

These are guarantees the engine makes on every run. Originating verdicts referenced for traceability; rationale lives in `PIVOTS.md` and the cited verdicts.

1. **Observed-effect surfacing tripwire.** Every Tier-B Recommended card populates `Measurement.observed_effect`, `Measurement.p_internal`, `Measurement.n` from `blend_provenance`. Source: S7.6 CLI fix verdict (`agent_outputs/ecommerce-ds-architect-s7_6-cli-wiring-gap-verdict-2026-05-23.md`). Tripwire: `tests/test_s7_6_c1_priority_prepend_invariant.py::test_tier_b_recommended_cards_surface_observed_effect_on_beauty`.

2. **Single-demote-channel invariant.** No code path appends to `engine_run.recommendations` after `apply_guardrails` without routing through `apply_guardrails_to_injected` (`src/guardrails.py`). New injection blocks at `src/main.py:1380-1597` are forbidden without explicit founder + DS sign-off. Source: S7.6 C2 (`CLAUDE.md` Subagent Handoff Discipline § 2026-05-22).

3. **Three-channel `priority_prepend`.** Tier-B prior-anchored cards demoted via *any* of the three reject channels (`eligibility_rejects`, `prior_unvalidated_rejects`, `window_disagreement_rejects`) are prepended into Considered ahead of `pre_existing` so the `MAX_CONSIDERED_RENDERED=6` truncation cannot silently drop them. Source: S7.6 T5.6 verdict.

4. **T6 eligibility gate + joint-p<0.10.** Builders that stash `*_band` per-window posteriors are gated on the joint p-value across primary + agreement windows, with a 0.10 threshold.

5. **`pseudo_N` table locked at {30, 15, 10}.** `PSEUDO_N_BY_STATUS = {VALIDATED_EXTERNAL: 30, VALIDATED_INTERNAL: 15, ELICITED_EXPERT: 10}`. Locked through S8–S14. Source: S8 verdict (`agent_outputs/ecommerce-ds-architect-s8-pseudo_n-and-ki-new-k-verdict-2026-05-24.md`); lock decision recorded in `docs/DECISIONS.md`. Implementation: `src/sizing.py:87-91`.

6. **`effective_n` is metadata only.** Never overrides the per-status `pseudo_N` cap; never enters the blend formula as a weight. A prior with `effective_n=156,110` still gets `pseudo_N=30`. Source: same S8 verdict §2.

7. **`gate_calibration.pseudo_n_default` can only LOWER the per-status cap, never raise.** Enforced via `min(status_cap, profile_default)` at `src/sizing.py:131-139`. Stage-aware tightening is a YAML edit, not a code change. Source: same S8 verdict §1.

8. **`RevenueRange.source = "blend"` for Bayesian-blended posteriors.** No `blend_empirical_bayes` sibling literal. Source: S8 verdict §5 invariant 9.

9. **`HEURISTIC_UNVALIDATED` and `PLACEHOLDER` priors never enter `bayesian_blend`.** They route to Considered with `ReasonCode.PRIOR_UNVALIDATED` and `revenue_range.suppressed=True`. Refusal, not low-weight blend. Source: S7.5-T3 + S8 verdict §2.

10. **No `Prior.pseudo_N` per-prior override field.** Validation-status is the single dial; per-prior numeric overrides would bypass per-status cap discipline. Source: S8 verdict §6 F2.

11. **Play Library wave-1 byte-identity by construction.** `consult_play_library_if_enabled` at `src/play_registry.py` asserts spec.yaml-resolved callables ARE identity-equal to the legacy registry callables (not just equivalent) at engine startup, on every run with `ENGINE_V2_PLAY_LIBRARY_WAVE1=ON`. Source: S8-T4/T4.5 verdict.

12. **Stop-Coding Line.** Engine emits typed fields in `engine_run.json`. Narration, framing, and copy belong to downstream renderers. `briefing.html` is debug-only.

---

## 6. Current flag defaults

`docs/engine_flags.md` is the source of truth for live flag values. STATE.md does not duplicate; consult that file for any specific flag.

S7.6 / S8 flags worth knowing about by name (all currently default ON unless noted, post-S8 close):

- `ENGINE_V2_DECIDE`, `ENGINE_V2_OUTPUT`, `ENGINE_V2_SLATE` — slate surface active.
- `ENGINE_V2_TIER_CHIP`, `ENGINE_V2_SENSITIVITY`, `ENGINE_V2_EB_BLEND` — three S8 additive PlayCard fields. Independently flag-gated per atomic-flip discipline.
- `ENGINE_V2_PLAY_LIBRARY_WAVE1` — three plays migrated to `plays/<play_id>/` directory tree; identity assertion enforced at startup.
- `ENGINE_V2_BUILDER_WINBACK_DORMANT`, `ENGINE_V2_BUILDER_DISCOUNT_DEPENDENCY_HYGIENE`, `ENGINE_V2_BUILDER_COHORT_JOURNEY_FIRST_TO_SECOND`, `ENGINE_V2_BUILDER_AOV_BUNDLE` — four wired Tier-B builders, ON.
- `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` — dormant by design on Beauty (KI-NEW-G honest-dormancy preserved).
- `ENGINE_V2_STORE_PROFILE` — PROFILE layer active.
- `RECENTLY_RUN_FATIGUE_ENABLED` — OFF (per Sprint 1 closeout).

For exact defaults and override paths, read `docs/engine_flags.md` (refreshed 2026-05-25, post-S8 close).

---

## 7. Current beta-readiness

**End-to-end engine state (post-S8, on the two pinned synthetic fixtures):**

- **Tier-B builder pool — 4 of 5 fire honestly on Beauty:**
  - `winback_dormant_cohort` — `observed_n=448`, store-dominant posterior.
  - `discount_dependency_hygiene` — `observed_n=224,077`, store-dominant posterior.
  - `cohort_journey_first_to_second` — `observed_n=603`, store-dominant, Berkson-protected (early-half cohort definition).
  - `aov_lift_via_threshold_bundle` — joint-fail demotes honestly to Considered with `SIGNAL_INCONSISTENT_ACROSS_WINDOWS`.
- **5th builder — `replenishment_due` — dormant on Beauty by design.** Honest dormancy preserved (KI-NEW-G RESOLVED-AS-DOCUMENTED). Will activate on real-merchant data when the replenishment-due cohort materializes.

- **Trust-surface contract on every Tier-B Recommended card:**
  - `Measurement.observed_effect / p_internal / n` (S7.6 CLI fix)
  - `evidence_source = "STORE_OBSERVED"` (S8-T1.5)
  - `sensitivity = {6-key block}` (S8-T2.5)
  - `provenance = {audit object}` (S8-T3.5)
  - `revenue_range.source = "blend"` + `drivers[].blend_provenance`

- **Supplements posture:** `aov_lift_via_threshold_bundle` is vertically excluded per the B-5 248 seam at `src/audience_builders.py:969-979`. Supplements goes from "ABSTAIN_SOFT, 0 cards" to non-empty only after S10–S13 ML AUDIENCE layer + Tier-B activation on supplements-specific signal.

- **Priors envelopes — Beauty Beta re-fit landed at S8-T0:** `discount_dependency_hygiene.base_rate.beauty` and `replenishment_due.base_rate.beauty` re-fit. SciPy-authoritative percentiles shipped to `config/priors.yaml`. See commit `77086fd` and S8-T0 verdict for math; numeric values are not inlined here.

- **Real-merchant private-beta onboarding (S14) is unblocked once S10–S13 ML AUDIENCE layer lands.** No further engine work is required to make the S8 trust-surface contract beta-ready.

---

## 8. Key files (current code map)

Pipeline layers:
- `src/store_profile.py` — PROFILE layer (vertical × sub-vertical × stage × cadence, gate calibration).
- `src/audience_builders.py` — AUDIENCE layer; one builder per play.
- `src/measurement_builder.py` — MEASUREMENT layer; `_SUPPORTED` + `_PRIOR_ANCHORED` registries; observed-effect surfacing at `2252-2270`.
- `src/sizing.py` — SIZING layer; `PSEUDO_N_BY_STATUS` (87-91), `effective_pseudo_n` (99-139), `bayesian_blend` (142-179).
- `src/decide.py` — DECIDE layer; slate assembly, role-uniqueness, demote-channel routing, considered truncation.

Surface:
- `src/engine_run.py` — **schema authority (v2.1.0; frozen 2.x — additive OK, breaking → 3.0.0)**; re-exports all contract types via `__all__`. Typed PlayCard schema: `EvidenceSourceChip`, `Sensitivity`, `Provenance`, `MechanismIntent`, `RejectedPlay`, `DescriptiveDistribution`. See §10 for the contract surface summary.
- `src/guardrails.py` — `apply_guardrails_to_injected` (single-demote-channel invariant helper).
- `src/main.py` — orchestration; per-play dispatch loop. Five V2 prior-anchored injection blocks at `1380-1597` (collapse deferred to S13.5 per KI-NEW-L).

Configuration & registry:
- `src/utils.py` — `DEFAULTS` + `get_config`; flag inventory in `docs/engine_flags.md`.
- `src/play_registry.py` — legacy play registry + `consult_play_library_if_enabled` (Play Library identity assertion).
- `config/priors.yaml` — priors + validation_status + effective_n metadata.
- `plays/<play_id>/` — Play Library wave-1 directory tree (3 plays migrated; 11 unmigrated in legacy locations).

Agent handoff (S13.7):
- `src/audience_resolver.py` — `materialize_audience_csvs()`: per-PlayCard CSV at `data/<store_id>/runs/<run_id>/audiences/<aud_def_id>.csv` (columns: customer_id, aov_individual, predicted_segment, rank_score). SUBSTRATE_REFUSED → empty CSV with header row. Source: D-S13.7-1.
- `src/run_manifest.py` — `write_run_manifest()`: per-run `manifest.json` enumerating engine_run.json + audience CSVs + parquets + retention. Source: D-S13.7-2.
- `schemas/engine_run.v2.json` — generated JSON Schema for the v2.1.0 contract (52 $defs; generated by `tools/generate_schema.py`). Agent-tooling only; not read at runtime.
- `docs/mechanism_contract.md` — DS-locked narration-agent spec for all 10 `MechanismType` values and their `parameters` shapes. Source: D-S13.7-3.
- `docs/evidence_layer.md` — the Evidence Layer / visualization spec authority (the closed 9-member set M1–M9 + viz-as-member gating; locks L-EV-1..20; the descriptive/inferential frame). Convention-only over the typed atoms; the engine emits atoms, narration/frontend assemble the projections.

Substrate:
- `src/memory/events.py` — per-merchant SQLite event log (recommendation_emitted, considered, campaign_sent, calibration_updated, outcome_observed).

Tests pinning load-bearing invariants:
- `tests/test_s7_6_c1_priority_prepend_invariant.py` — observed-effect tripwire + three-channel priority_prepend.
- `tests/test_s7_5_t3_priors_validation_refusal.py` — HEURISTIC_UNVALIDATED refusal.
- `tests/test_v2_harness_cfg_gated_fields.py` — DS invariant 16 (cfg-wiring discipline).
- `tests/test_s8_flag_independence.py` — independent flag matrix.
- `tests/test_s13_7_t1_audience_resolver.py` — audience CSV materialization + SUBSTRATE_REFUSED empty-CSV contract.
- `tests/test_s13_7_t2_manifest.py` — manifest.json per run + audience_materialization_status.
- `tests/test_s13_7_t7b_deferred_null_reasons.py` — StoreProfileNullReason + ModelCardAbsenceReason + CohortDiagnosticsAbsenceReason enum contracts.

---

## 9. What is NOT in the engine today

For each deferred item, see `ROADMAP.md` for the resume condition. Listed here only so a reader knows the boundary.

- **No outcome calibration loop.** Phase 9 (outcome ingestion → prior recalibration) is post-beta.
- **No causal uplift modeling.** Requires accumulated Phase 9 outcomes.
- **No ML predictive layer yet.** BG/NBD + Gamma-Gamma LTV, survival, collaborative filtering, RFM, retention curves all land S10–S13. `ModelFitStatus` gate is dormant until then.
- **No frontend app.** `briefing.html` is the only renderer today and is debug-only.
- **No Klaviyo API calls.** Publish is manual (D-5).
- **No outcome-import API.** Manual JSON import only.
- **No multi-channel publishing, no LLM-generated mechanism copy, no portfolio optimization, no replay/backtest CLIs.** Far post-PMF.
- **Supplements is structurally quiet.** `aov_lift_via_threshold_bundle` vertically excluded; supplements Tier-B activation depends on S10–S13 + real-merchant data.
- **5 V2 prior-anchored injection blocks at `src/main.py:1380-1597` not yet collapsed.** Scheduled S13.5 per KI-NEW-L.
- **`Measurement.consistency_across_windows` field not populated.** Founder-confirmed not in scope (2026-05-24).
- **`src/segments.py` retired at S13.7-T1.** Legacy `segments/*.csv` path removed. Audience CSVs now written to `data/<store_id>/runs/<run_id>/audiences/` by `src/audience_resolver.py`.

---

## 10. Output contract surface (v2.1.0; additive within the 2.x freeze)

**Refreshed:** 2026-06-03 (S-FE additive schema bump).

The contract is `engine_run.json` produced by `src/engine_run.py`. Schema version **v2.1.0**. The 2.x line is frozen in the sense that additive changes stay within 2.x and breaking changes → 3.0.0; the v2.0.0 freeze (S13.6) holds — the S-FE work added fields only. `schemas/engine_run.v2.json` (regenerated by `tools/generate_schema.py`; **52 $defs**) covers all dataclasses and enums.

**S-FE additive bump (2.0.0 → 2.1.0; DS APPROVE):**
- **`Audience.descriptive_distribution: Optional[DescriptiveDistribution]`** — the binned descriptive series for the 4 distributional plays (`kind`/`bins`/`counts`/`marker` + RULE-A `suppressed`/`suppression_reason`). New `$defs`: `DescriptiveDistribution`, `DistributionKind` (closed 4-member), `DescriptiveDistributionSuppressionReason` (closed 3-member). Descriptive-only (L-EV-20): no dollar/lift field; engine emits the series, never a chart-spec.
- **RFM `ModelCard.segment_distribution: Optional[List[SegmentBand]]`** — aggregate named-segment bands (`{segment_name, n, share}`), populated only when RFM `fit_status ∈ {VALIDATED, PROVISIONAL}`; paired `RfmSegmentDistributionSuppressionReason` (closed 2-member). New `$defs`: `SegmentBand`, `RfmSegmentDistributionSuppressionReason`.
- Both are additive Optionals (older runs / non-RFM cards deserialize as `None`); the freeze is intact (additive OK, breaking → 3.0.0). The Evidence Layer / viz spec authority is **`docs/evidence_layer.md`** (L-EV-1..20).

**Key properties of the v2.x surface (S13.7 additive changes in bold):**

- **Zero engine-authored prose.** All prose fields stripped at S13.6-T1a (Pivot 2 ratification). `recommendation_text`, `why_now`, `RejectedPlay.reason_text/evidence_snapshot/would_fire_if`, `Abstain.reason`, `notes` debris — all gone. Engine emits typed atoms only.
- **`MechanismIntent` on `PlayCard`.** `PlayCard.mechanism_intent: Optional[MechanismIntent]` carries `type: MechanismType` (closed 10-member enum) + `parameters: Dict[str, Any]`. Renderer reads `mechanism_intent.type.value` directly; YAML-lookup fallback retired. `RejectedPlay.mechanism` retyped `Optional[str] → Optional[MechanismIntent]`. Source: `docs/DECISIONS.md::D-S13.6-4`. **`docs/mechanism_contract.md` is the DS-locked narration-agent spec for all 10 `MechanismType` values and their `parameters` shapes (S13.7-T3).** Source: `docs/DECISIONS.md::D-S13.7-3`.
- **RULE A null-reason pattern.** Every `Optional` field whose absence signals missing data is paired with a `<field>_null_reason: Optional[<Enum>]`. Flag-OFF defaults are exempt via `# null_reason_exempt:` annotation. **6 shipped pairs at S13.7:** `RevenueRange.suppression_reason` / `EngineRun.month_2_delta_null_reason` / `PredictedSegment.segment_name_null_reason` / **`EngineRun.store_profile_null_reason` (S13.7-T7b)**. Agent-reference vocabulary enums (no paired fields): **`ModelCardAbsenceReason` (3 members) + `CohortDiagnosticsAbsenceReason` (2 members) (S13.7-T7b)**. `CustomerIdsNullReason` (2 members) declared (S13.7-T1; field pairing deferred to S14). Source: `docs/DECISIONS.md::D-S13-5` + `D-S13.6-5` + `D-S13.7-4`.
- **`INCLUDE_DEBUG_FIELDS` flag (default OFF).** Debug-only fields (`Sensitivity`, `Provenance`, `notes` debris) are omitted from `engine_run.json` when OFF. Flip ON for internal dev runs. Source: `docs/engine_flags.md::INCLUDE_DEBUG_FIELDS`.
- **Single-file schema authority.** `src/engine_run.py` re-exports all contract types via `__all__`. Agents read one file; no schema fragmentation. Source: `docs/DECISIONS.md::D-S13.6-2`.

**Pinning tests for S13.6 contract invariants:**
- `tests/test_s13_6_t6_mechanism_intent_atom.py` — 28 tests; `MechanismType` closed enum, `MechanismIntent` shape, producer coverage, JSON round-trip.
- `tests/test_s13_6_t7a_no_silent_nulls.py` — AST sweep + RULE A per-row invariants; closed-set enum coverage pins (9 / 5 / 4 members).
- `tests/test_null_reason_registry.py` — registry comment block coverage; 3 shipped pairs + 4 deferred documented.

---

## Sources

- `ENGINE_OVERVIEW.md` §§2, 3, 5, 6, 8, 8.5 (pipeline, slate, current state, tiers, gates).
- `ARCHITECTURE_PLAN.md` Part I §A (Tier definitions), Part IV (Store Profile Layer), LOAD-BEARING UPDATE blocks 1–9 (distilled to current-state facts only).
- `agent_outputs/ecommerce-ds-architect-s8-pseudo_n-and-ki-new-k-verdict-2026-05-24.md` (pseudo_N lock, KI-NEW-K close, S14-readiness invariants).
- `agent_outputs/ecommerce-ds-architect-s8-t0-scipy-percentile-followup-2026-05-24.md` (SciPy-authoritative percentiles, methodological lesson).
- `agent_outputs/ecommerce-ds-architect-s7_6-cli-wiring-gap-verdict-2026-05-23.md` (observed-effect surfacing tripwire).
- `agent_outputs/campaign-slate-contract-final.md` — origin of the pinned-slate regime + Beauty fixture sha lineage.
- `agent_outputs/m0-m9-final-review-reconciled.md` — Ready-with-caveats verdict closing V2 M0-M9 milestone.
- `CLAUDE.md` Subagent Handoff Discipline section (single-demote-channel invariant authority).
- `docs/engine_flags.md` (live flag values — STATE.md references, does not duplicate; refreshed 2026-05-25, post-S8 close).
- `docs/DECISIONS.md` (founder-locked decisions D-1..D-8 + pseudo_N table lock).

*End of STATE.md.*
