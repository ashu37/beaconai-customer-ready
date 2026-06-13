# ROADMAP — BeaconAI

**Cadence:** live; refreshed per sprint plan / sprint close.
**Last refresh:** 2026-06-01 (post-S13.7 close).
**Replaces:** `ARCHITECTURE_PLAN.md` Part II sequencing + "What This Plan Does NOT Do" L88-98.

For "why this sequence" see `PIVOTS.md`. For open behavior/contract issues see `KNOWN_ISSUES.md`. For the present-tense engine description see `STATE.md`.

---

## 1. Current sprint

**Sprint 13.5 — KI-NEW-L collapse (queued).** Next: collapse the 5 V2 prior-anchored injection blocks at `src/main.py:1380-1597` into a single `dispatch_prior_anchored_builders` function keyed by the `_PRIOR_ANCHORED` registry — DS-locked invariant-preservation per `KNOWN_ISSUES.md::KI-NEW-L` (single-demote-channel; 3-channel `priority_prepend`; `Measurement.observed_effect/p_internal/n` surfacing; per-builder byte-identity on pinned slates). Dedicated single-ticket structural-cleanup window between S13-T4 and S14-T1. Not yet dispatched.

**S13.7 just closed (SHIPPED 2026-06-01).** Sprint 13.7 — Agent handoff completion — shipped all 4 tickets (T1 + T2 + T3 + T7b + T4-CLOSE). Key outcomes: audience resolver materializes per-PlayCard `audiences/<aud_def_id>.csv` at run time (`src/audience_resolver.py`); `manifest.json` per run enumerates all artifacts (`src/run_manifest.py`); `docs/mechanism_contract.md` is the DS-locked narration-agent spec for all 10 `MechanismType` values; deferred null-reason enums landed (`StoreProfileNullReason` + `ModelCardAbsenceReason` + `CohortDiagnosticsAbsenceReason`; KI-NEW-AA closed); `_surface_mechanism_for_play` dead code deleted from `src/decide.py` (KI-NEW-AB C2 closed); `schemas/engine_run.v2.json` published as the agent-readable JSON Schema for v2.0.0. D-S13.7-1 through D-S13.7-5 locked. `src/segments.py` hard-retired; legacy segment CSV path removed.

**S13.6 just closed (SHIPPED 2026-06-01).** Sprint 13.6 — engine_run.json agent-contract cleanup — completed all 10 tickets (T1a + T1b + T2 + T3 + T4 + T5 + T6 + T7 + T7.5 + T8-CLOSE). Schema frozen at v2.0.0. Key outcomes: prose fields stripped (Pivot 2 ratification); `MechanismType` closed enum + `MechanismIntent` typed atom on PlayCard; RULE A null-reason enum registry (3 shipped pairs: RevenueRange / MonthDelta / PredictedSegment); `INCLUDE_DEBUG_FIELDS` flag (default OFF); YAML-lookup renderer fallback retired at T8; `src/engine_run.py` is single-file schema authority. D-S13.6-1 through D-S13.6-5 locked. KI-NEW-AA (StoreProfile null-reason gap) and KI-NEW-AB (dead-code cleanup) deferred to S13.7-T7b.

**S13 just closed (SHIPPED 2026-05-29).** Sprint 13 — Integration / consumer wiring — was the **beta-blocking consumer-wiring sprint** and the most architecturally important sprint in S10-S13. All 8 tickets shipped (T0 + T1 + T1.5 + T2 + T2.5 + T3 + T3.5 + T4-CLOSE):

- **T0 — ModelCard refactor** (`722bcb3`): authoritative `metrics: Dict[str, float]` storage; `InitVar` legacy kwargs + `__getattr__` shim for back-compat; substrate producers (bgnbd / gamma_gamma / survival / cf / rfm) write `metrics={...}` directly. No flag; pure substrate refactor.
- **T1 + T1.5 — Ranking-strategy module + atomic flip** (`4c087dc`, `b646d29`): NEW `src/predictive/ranking_strategy.py` with `AudienceIntent` str-Enum (`GENERAL` / `REPLENISHMENT_TIMING` / `LOOKALIKE_EXPANSION`) + intent-conditional chains; `ENGINE_V2_RANKING_STRATEGY_CHAIN` flipped ON at T1.5; NO consumer wire at T1.5 (T2 owns it).
- **T2 + T2.5 — PlayCard consumer wiring + ML-fit gate transition** (`187af49`, `af2a80e`): NEW `src/predictive/consumer_wiring.py` populates `PlayCard.predicted_segment` + `PlayCard.model_card_ref`; **Q-S13-4 LOCK** at `src/engine_run.py:167-183` (ML-fit ReasonCodes emit ONLY on `model_card_ref.fit_warnings`, NEVER on `RejectedPlay.reason_code`); modal-segment stability floor (`n<50` OR `share<0.30` → segment_name=None); Option II post-injection wire-site (after `apply_guardrails_to_injected`); AST-aware `test_reason_code_precedence_invariant.py` refactor; REQUIRED `tests/test_s13_ml_fit_never_demotes.py` 5-fixture runtime test; **ML-fit gate transitioned DORMANT → LIVE at T2.5** (emitter wired via `fit_warnings` only; never demotes between slate roles).
- **T3 + T3.5 — month_2_delta typed slot + atomic flip** (`a97ab54`, `43e2ffe`): NEW `MonthDelta` dataclass + `EngineRun.month_2_delta` slot; NEW isolated `src/predictive/month_2_delta.py` (6 substrates diffed); 21-day floor + lineage-change constraint suppressing `segment_shifts` when `audience_definition_version` bumps; orchestration wire AFTER T2 consumer-wiring (NOT in forbidden `L1380-1597`); REQUIRED positive-control synthetic; `ENGINE_V2_MONTH_2_DELTA` flipped ON at T3.5 with 4-case rollback (Case D = INDEPENDENCE PIN); ML-fit-never-demotes extended with a month-2 sequence per DS S13 plan review §F.
- **T4-CLOSE — Sprint-close docs** (this commit): KI-NEW-W/X/Y/Z filed; KI-NEW-P extended to ~30+ numbers across S13 consumer-side calibration cells; KI-NEW-L S13.5 commitment restated; STATE §4 ML-fit LIVE revision; PIVOTS Pivot 5 §G.3 three-precondition clarifier; DECISIONS D-S13-1 through D-S13-4.

**S13 outcome:** All **6 predictive substrates now have CONSUMERS** (BG/NBD + G-G + survival + CF + RFM + retention). `PlayCard.predicted_segment` + `PlayCard.model_card_ref` LIVE. `EngineRun.month_2_delta` LIVE as **substrate-state-delta per Pivot 8** (NOT realized-outcome delta; cold-start month-2 flows through EB n_observed shift, not ML refit). ML-fit gate transitioned DORMANT → LIVE at T2.5 — emitter wired via `fit_warnings` only per Q-S13-4 LOCK; never demotes between slate roles; pinned by `tests/test_s13_ml_fit_never_demotes.py` 5-fixture runtime + month-2 extension + AST-aware `tests/test_reason_code_precedence_invariant.py`. small_sm framing per the §G.3 three-precondition clarifier on Pivot 5 (predicted_segment.segment_name populates only when (a) RFM VALIDATED, (b) modal-segment floor cleared, AND (c) DECIDE produces ≥1 PlayCard for the audience — four-gate architecture working as designed).

**S13 follow-ups:**
- KI-NEW-P **extended to ~30+ numbers across S13 consumer-side calibration cells** — chain selection precedence (per intent: 3 intents × 5 substrates = 15 positional cells), modal-segment floor (n_audience + modal_share), 21-day floor for month_2_delta, retention CI delta sign correctness. Closure window opens at S14 real-merchant data across all 6 substrates.
- KI-NEW-W (stale-parquet across REFUSED runs; consumer-presence-gating does not detect cross-run lineage drift; defer S14 or dedicated artifact-lifecycle ticket).
- KI-NEW-X (§G.3 framing precondition; honest finding documented per Pivot 5; not a defect).
- KI-NEW-Y (intent-mapping YAML promotion at S14; `_INTENT_BY_PLAY_ID` acceptable hardcoded at S13).
- KI-NEW-Z (Option II wire-site process discipline; technical decision correct, process should have been "raise then proceed").
- KI-NEW-L S13.5 commitment honored (collapse window between S13-T4 and S14-T1).

**S12 just closed (SHIPPED 2026-05-28).** Sprint 12 — ML Predictive Layer Part 3 — shipped all 4 substrate tickets (T1 + T1.5 + T2 + T2.5) and sprint-close docs (T3-CLOSE):
- **RFM substrate** (custom code; no third-party library) — 11 named segments, internal-consistency `segment_monotonicity_spearman` gating + `quintile_coverage_min < 0.05` REFUSED guard. Stage-keyed VALIDATED Spearman floors `0.60 / 0.65 / 0.70 / 0.70`. **INDEPENDENT of BG/NBD** (4-layer pin). Flag `ENGINE_V2_ML_RFM` flipped ON at T1.5.
- **Retention curves substrate** (custom code + numpy bootstrap; no third-party library) — NEW `RetentionCard` dataclass (separate from `ModelCard`; reuses `ModelFitStatus` via Option A vocab-stacking), NEW top-level `EngineRun.cohort_diagnostics` slot (architecturally distinct from `predictive_models`; first occupant). Stage-keyed `bootstrap_ci_width_at_month_3` ceilings `0.25 / 0.20 / 0.15 / 0.15` VALIDATED. **REFUSED gate: cumulative-retention monotonicity violation** (DS-locked promotion from tertiary diagnostic per S12 plan review §G). **INDEPENDENT** of BG/NBD. NO parquet artifact. Flag `ENGINE_V2_ML_RETENTION` flipped ON at T2.5.
- Both substrates are **INDEPENDENT** — no chained refusal. RFM is the explicit **floor** of the S13 ranking-strategy chain.
- Rollback contract tests landed for both (Case D = INDEPENDENCE PIN).

**S12 outcome (Pivot 5 honest synthetic extended):** 10 fixture × substrate cells across the 5 pinned fixtures: **2 VALIDATED** (RFM `small_sm` Spearman=0.93; retention `healthy_supplements_240d` VALIDATED via degenerate bootstrap n=38), **1 PROVISIONAL** (retention Beauty, `cohort_count=6` below MATURE 12 VALIDATED floor — matches DS T2 §I prediction), **7 REFUSED / INSUFFICIENT_DATA** (RFM Beauty/Supplements/mid_shopify/micro_coldstart all REFUSED via `quintile_collapse` on synthetic monetary distributions — synthetic-DGP shape, NOT calibration miss). No fixture reshaped to manufacture VALIDATED coverage. Synthetic VALIDATEDs are **structural-correctness signals, NOT predictive-accuracy claims** per Pivot 5 S12-T2.5 clarifier. Real VALIDATED evidence comes from S14 real-merchant data.

**S12 follow-ups:**
- KI-NEW-P (stage-grid threshold calibration suite) — **extended to ~30+ numbers across all 6 substrates** (BG/NBD + G-G + survival + CF + RFM + retention) with three distinct closure-criteria shapes (per-customer ranker calibration vs RFM segment-LTV vs retention CI-honesty). Closure remains deferred to S14 real-merchant data.
- KI-NEW-T (Retention CI=0.0 degenerate-bootstrap on Supplements n=38) — filed; Pivot-5-consistent ACCEPT; closure trigger = S14 `min_cohort_size_floor` recalibration.
- KI-NEW-U (stale flag-default-off tests cleanup for `ENGINE_V2_ML_RFM` + `ENGINE_V2_ML_RETENTION`) — filed; closure trigger = T3-CLOSE OR next maintenance pass.
- KI-NEW-V (DS T1.5/T2.5 nits backlog: `_quintile_coverage_min` docstring vs implementation; synthetic monetary-DGP calibration; DS prediction-framework discipline note) — filed.
- PlayCard stubs `predicted_segment` and `model_card_ref` stay None at S12 close — S13 wires them.

**S11 closed (SHIPPED 2026-05-28).** Sprint 11 — ML Predictive Layer Part 2 — shipped all 5 tickets (T1 + T1.5 + T2 + T2.5 + T3):
- Cox PH survival substrate via `scikit-survival>=0.22,<0.24` (substituted for `lifelines` per DS S11 plan review §B; same Cox PH math, better-maintained, sklearn-ecosystem). Dual-gate `ModelFitStatus` (`c_index ≥ stage_floor` AND `brier@90d ≤ stage_ceiling`). Chained-refusal on BG/NBD REFUSED/INSUFFICIENT_DATA.
- Collaborative filtering substrate via `implicit>=0.7,<0.8` (ALS). Primary gating metric `top_k_recall@10`; `coverage_at_k` is operator-visible diagnostic only (does NOT gate). **CF is INDEPENDENT of BG/NBD** — `fit_cf` API takes no `bgnbd_model_card` argument (4-layer pin: docstring + signature + test + YAML comment).
- Atomic flips of `ENGINE_V2_ML_SURVIVAL` + `ENGINE_V2_ML_CF` with rollback contract tests (including Case D INDEPENDENCE PIN).
- Additive `ModelCard` fields: `holdout_c_index`, `holdout_brier_score_90d` (survival); `holdout_top_k_recall`, `coverage_at_k` (CF).

**S11 outcome (Pivot 5 honest synthetic extended):** 5/5 pinned fixtures REFUSED via `chained_bgnbd_refusal` on survival; 5/5 INSUFFICIENT_DATA on CF (synthetic-data repeat-buyer ceiling: `n_active_customers` < stage `min_customers`). No fixture reshaped to manufacture VALIDATED coverage. VALIDATED path verified by in-code synthetic sanity for both substrates (Cox PH c=0.838; ALS recall@10=0.344). Real VALIDATED evidence comes from S14 real-merchant data.

**S11 follow-ups:**
- KI-NEW-P (stage-grid threshold calibration suite) — **extended to ~30 numbers across all 4 ML models** (BG/NBD + G-G + survival + CF). Closure remains deferred to S14 real-merchant data.
- KI-NEW-Q (operator parquet query CLI) — filed at S11-T3 per founder ack; closure trigger = post-beta operator-tooling sprint.
- KI-NEW-R (ML library vendor-fork escape hatches: `lifetimes` + `scikit-survival` + `implicit`) — filed; closure trigger = AWS migration / post-beta dependency consolidation OR forced incompatibility.
- KI-NEW-S (wall-clock flake on `test_inventory_updated_at_is_fresh`) — filed; closure trigger = post-beta synthetic-fixture maintenance pass.
- PlayCard stubs `predicted_segment` and `model_card_ref` stay None at S11 close — S13 wires them.

ML predictive layer lives in the AUDIENCE step of the pipeline — it does not add plays; it ranks customers within each play's audience.

---

## 2. Beta-blocking sequence (S9 → S14)

Refreshed post-S8 from `ENGINE_OVERVIEW.md` §6 and `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md`. Target: private beta launch at S14 close, ~12 wall-clock weeks from S9 kickoff.

| Sprint | Scope (one line) | Beta-critical? |
|---|---|---|
| **S9** | post-beta lifecycle/cleanup (deferred) — store-profile-as-learned-artifact, Play Library wave 2, play lifecycle prerequisite | no — post-beta deferred (out of beta-critical sequence; picks up after S14) |
| **S10** | ML Predictive Layer Part 1 — BG/NBD + Gamma-Gamma + four-state `ModelFitStatus` (4th gate, dormant) — **SHIPPED 2026-05-26** | yes — month-1 wow surface |
| **S11** | ML Predictive Layer Part 2 — survival (`scikit-survival`) + collaborative filtering (`implicit`) — **SHIPPED 2026-05-28** | yes — drives `replenishment_due` ranking |
| **S12** | ML Predictive Layer Part 3 — statistical RFM (custom; INDEPENDENT of BG/NBD; floor of ranking chain) + cohort retention curves (custom + numpy bootstrap; `cohort_diagnostics` slot) — **SHIPPED 2026-05-28** | yes — month-2 return surface |
| **S13** | Integration — ML feeds AUDIENCE via `ranking_strategy` (`BG/NBD → CF → survival → RFM (floor) → recency`) + intent-conditional chains (`AudienceIntent`); `predicted_segment` + `model_card_ref` on PlayCard; `month_2_delta` typed slot; ML-fit gate DORMANT → LIVE (Q-S13-4 LOCK; never demotes); S13-T0 ModelCard refactor (`metrics: Dict[str,float]`) — **SHIPPED 2026-05-29** | yes — last beta-critical sprint |
| **S13.5** | KI-NEW-L collapse — 5 V2 prior-anchored injection blocks at `src/main.py:1380-1597` → 1 `dispatch_prior_anchored_builders` keyed by `_PRIOR_ANCHORED` registry; DS-locked invariant-preservation | no (structural cleanup; engine behavior unchanged) |
| **S13.6** | engine_run.json agent-contract cleanup — prose strip, `MechanismIntent` typed atom, RULE A null-reason registry, `NonLiftAtom` wrapper, typed `FitWarning`, schema v2.0.0 freeze — **SHIPPED 2026-06-01** | no (contract hardening; behavioral surface unchanged) |
| **S13.7** | Agent handoff completion — audience resolver (`src/audience_resolver.py`), `manifest.json` per run (`src/run_manifest.py`), `docs/mechanism_contract.md` narration-agent spec, deferred null-reasons (KI-NEW-AA closed), dead-code sweep (`_surface_mechanism_for_play`), `schemas/engine_run.v2.json` published — **SHIPPED 2026-06-01** | no (handoff hardening; behavioral surface unchanged) |
| **S14** | Private beta launch — onboard 1–2 hand-picked merchants; calibration report; KI-30-class fixes | yes — gating |

**Ordering rationale (load-bearing):** affinity-then-survival-then-uplift sequencing per `agent_outputs/beacon-ml-roadmap-reconciled-review.md`. ML predictive layer (S10-S13) is the beta-blocking sequence. Lifecycle work in S9 is the post-beta learning loop that compounds month-over-month — month-2-return value comes from the ML refit on 30 more days of data, not from lifecycle infrastructure. ML predictive layer lives in the AUDIENCE step of the pipeline — it does not add plays; it ranks customers within each play's audience.

**Three orthogonal gates** preserved across the sequence: cohort p-value (per builder), priors `validation_status` (per prior, S7.5 contract), `ModelFitStatus` (per model, S10+).

---

## 2.5. Frontend / agent-handoff track (parallel to the engine sequence)

The merchant-facing handoff layer (engine → MCP agents → frontend) runs as a separate phased track. Full architecture + the 8 DS locks live in `docs/handoff_architecture.md`; this is the index.

| Phase | Scope | Status |
|---|---|---|
| **Phase 0** | Fixture / green run on disk + `audience_resolver` hardening (DS lock 4) | ✅ SHIPPED (canonical fixture `small_sm`; demo run `beauty_brand`) |
| **Phase 1** | Narration MCP (LLM-authored, mock-mode; 8 DS locks structural) | ✅ SHIPPED (mock-mode; real-key cutover gated on KI-FE-8) |
| **Phase 2** | Integration spine — Express broker + 3 swappable seams (stdio/REST) | ✅ SHIPPED |
| **Phase 3** | Frontend slate + approval UI + **Evidence Layer visual projection** | ✅ SHIPPED (slate + approval; evidence-viz members M1–M5/M7/M8 + M-DIST + per-mechanism map; Intelligence wired to the contract, mocks deleted) |
| **Phase 4** | Assembly MCP + Klaviyo CSV download (local e2e milestone) | **NEXT** (not started) |
| **Phase 5** | AWS hosting | DEFERRED |

### Evidence Layer — spec authority (engine-owned)

`docs/evidence_layer.md` is the DS/contract authority for the **Evidence Layer**: the typed, gated set of atoms (M1–M9) that justify a play, each bound to a frozen typed field, with **visualization a first-class member**. DS-defined 2026-06-02 (L-EV-1..12), extended 2026-06-02 with **L-EV-13..20** (the descriptive/inferential viz-gating frame, the refused-data posture, the dashboard boundary, the per-mechanism selection-map architecture, and the `Audience.descriptive_distribution` primitive). Locked at `docs/DECISIONS.md::D-S14-1`. The engine's role is to **emit the typed atoms** (`measurement`, `revenue_range`, `cohort_diagnostics`, `predicted_segment`, plus the S-FE additive `Audience.descriptive_distribution` + RFM `segment_distribution`) and the **claim/prose projection** via the narration MCP (Phase 1). The L-EV-1..12 frame is assemblable from v2.0.0 (convention-only; candidate `PlayCard.evidence_layer_ref` deferred); L-EV-19/17 added the only schema change — the **additive 2.0.0 → 2.1.0 bump** (Audience.descriptive_distribution + RFM segment_distribution; freeze intact).

> **The visual projection (the charts) is FRONTEND work** — tracked in the frontend repo's `ROADMAP.md` (Phase 3, ✅ SHIPPED: the beta-min viz set M1/M3/M4/M5/M7 + the deferred M2/M8 + M-DIST + the per-mechanism selection map + Intelligence wired to the contract), referencing this spec as authority. It does not belong to the engine sequence.

---

## 3. Carry-forward items from S8

Per DS S8-scope verdict on the S8 plan (`agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md`) these are NOT process residue — they carry into S9 / S10 work:

1. **EB blend full payoff gated on Phase 9 outcome ingestion (S15+).** S8 shipped the contract; the math earns its keep only with multi-month feedback. Documented honestly in the S8 close.
2. **Play Library wave 2+ migration — post-beta.** S8 wave 1 covered 3 of 14 plays. Waves 2+ fold into the S9 post-beta lifecycle/cleanup window alongside KI-NEW-L (registry-driven dispatch replaces 5 injection blocks organically).
3. **KI-NEW-L / M / N — anchored S13.5 + S14-T3.** KI-NEW-L collapses 5 V2 prior-anchored injection blocks at `src/main.py:1380-1597` into a single PRIOR_ANCHORED dispatch — scheduled S13.5 per memory.md L1921 commitment (between S13-T4 atomic flip and S14-T1 beta-launch dispatch). KI-NEW-M/N — `_dedupe_rejections` typed-code priority policy and experiment-promotion provenance preserve — both deferred to S14-T3 post-beta-merchant-feedback.
4. **`evidence_source` chip + `sensitivity` block frontend consumption deferred.** Both ship in `engine_run.json` at S8 close. The renderer surface (debug HTML today, future frontend app) does not yet display either. Deferred until the frontend app activates.
5. **S10–S13 ML predictive layer extends `predicted_segment` + `model_card_ref` stubs additively** on the S8 typed surface. The S8 chip / sensitivity / provenance contract is the substrate the ML cards pattern-match against.

---

## 4. Post-beta deferrals (S15+)

Confirmed deferred — not part of the beta-blocking sequence:

- **Phase 9 outcome ingestion loop** (`outcome_observed` importer + calibration writer + last-month-outcome briefing surface). Entry conditions tracked at `KNOWN_ISSUES.md::KI-1` through `KI-5`. Was the previous plan's S10; reframed post-beta. Payoff window is month 3+ of installed-base data.
- **Causal uplift modeling.** Requires accumulated Phase 9 outcome rows. Post-PMF.
- **Klaviyo API / Shopify network calls.** D-5 forbids in v1. Manual JSON import only. AWS migration is the right moment to revisit.
- **Trust-math operator tooling** (replay CLI, backtest, sensitivity-audit CLIs). Founder-internal, not merchant-facing.
- **Portfolio optimization** (S22+).
- **LLM mechanism generation** (S26+).
- **Multi-channel / federated learning.** Far post-PMF.
- **V2 legacy cleanup workstream.** Until the legacy pipeline becomes a maintenance burden — not before.
- **Cross-merchant pooling for sub-threshold-N merchants** (BG/NBD / Cox PH cold-start floor). Privacy + multi-tenancy implications unscoped.
- **Substrate disk growth optimization / TTLs.** No retention limits today (per D-2 forever-retention). AWS migration time.

---

## 5. What we are NOT building

Distilled from `ARCHITECTURE_PLAN.md` "What This Plan Does NOT Do" L88-98, founder decisions D-1..D-8, and the reconciled ML-roadmap review. These are permanent non-goals within the beta scope.

**Vertical and product scope:**
- **No vertical expansion.** Hard-locked at `{beauty, supplements, mixed}` per D-8. `mixed` means literal beauty+supplements blend, NOT unknown-vertical fallback. Refused at engine entry.
- **No frontend app inside engine scope.** Engine emits typed `engine_run.json`; the frontend renderer is downstream. `briefing.html` is debug-only and retires when the frontend activates.
- **No agentic narration / copy generation in the engine.** Per the Phase 6B Stop-Coding Line — framing, narration, mechanism phrasing is the downstream agent swarm's job. Engine emits typed fields.

**Statistical / claim discipline:**
- **No fabricated outcome inference.** Engine cannot claim a recommendation "worked" or "didn't work" without realized campaign data. See `play-lifecycle-discussion-reconciled.md` §"Product / Science Boundary".
- **No "calibrated" or uplift terminology in merchant-facing copy** absent measured holdout data.
- **No `confidence_score`, `final_score`, BeaconAI score**, or numeric confidence percentages in V2 surface.
- **No multi-window min-p cherry-picking.** Replaced by sign-agreement + combined statistics.
- **No "learning" `CONFIDENCE_MODE`** that relaxes thresholds.

**ML scope (D-N banned use cases):**
- **No ML for outcome claims** without realized outcome data. ML scores per customer feed AUDIENCE ranking, not measured-effect claims.
- **No neural / RL / uplift models in beta.** Classical Fader/Hardie + Kaplan-Meier + Cox PH + ALS + RFM only — the D-6 carve-out is peer-reviewed-classical only.
- **No cross-merchant pooling.** Per-merchant, per-vertical fits only. Privacy posture per D-2.
- **No per-customer scores in `engine_run.json`.** Parquet artifacts under `data/<store_id>/predictive/` only. Audience-aggregate summaries reach the JSON.

**Integration scope:**
- **No Klaviyo / Shopify network calls** in the local engine path. D-5 manual import only.
- **No automatic campaign send.** Merchant approval gate is hard, even post-integration.
- **No PII in predictive artifacts.** `customer_id` only.

**Process scope:**
- **No big-bang rewrites.** Every sprint ships a runnable engine.
- **No reshaping synthetic fixtures to fire builders.** Honest dormancy is the product (S7.6 synthetic-fixture honesty rule).

---

## 6. Pointers

- **Open behavior / contract issues:** `KNOWN_ISSUES.md` (KI-1..KI-5 = Phase 9 entry conditions; KI-NEW-L anchored at S13.5; KI-NEW-M/N anchored at S14-T3 post-beta-merchant-feedback).
- **Why this sequence (founder bends in the river):** `PIVOTS.md` — especially the beta success reframe (month-1-wow + month-2-return), the ML-as-audience-ranking pivot, and the lifecycle-before-ML ordering.
- **Present-tense engine description:** `STATE.md`.
- **Product / merchant journey / future state:** `PRODUCT.md`.
- **Active execution roadmap (authoritative parent):** `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md`.
- **S9 lifecycle prerequisite framing:** `agent_outputs/play-lifecycle-discussion-reconciled.md`.
- **ML sprint ordering rationale:** `agent_outputs/beacon-ml-roadmap-reconciled-review.md`.
- **S8 carry-forward source verdict:** `agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md`.

---

## Sources

- `ENGINE_OVERVIEW.md` §6 redesign plan + table (lines 88-117).
- `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` — authoritative S6–S14 roadmap (current execution plan).
- `agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md` — S8 plan with the 6 carry-forward items above.
- `agent_outputs/beacon-ml-roadmap-reconciled-review.md` — load-bearing for ML sprint ordering (affinity-then-survival-then-uplift; lifecycle ships before ML).
- `agent_outputs/play-lifecycle-discussion-reconciled.md` — load-bearing for Sprint 9 lifecycle prerequisite (audience-stability + lineage-key + outcome-seam discipline).
- `ARCHITECTURE_PLAN.md` "What This Plan Does NOT Do" L88-98 — distilled into the deferrals + non-goals sections.
- `KNOWN_ISSUES.md` for KI-NEW-L/M/N and Phase 9 entry conditions (KI-1..KI-5).
- `memory.md` last two sprints (S7.6, S8) for active sprint status; founder decisions D-1..D-8 at L173-182.
- `agent_outputs/ecommerce-ds-architect-doc-audit-2026-05-24.md` — Revisions section for the doc-migration trigger that paused S9 dispatch.
