# Sprint 10 — ML Predictive Layer Part 1 — Implementation Plan

**Author:** implementation-manager
**Date:** 2026-05-25
**Branch baseline:** `post-6b-restructured-roadmap` (post-S8 close, post-doc-migration cutover)
**Status:** DRAFT v2 — for founder review before any code-refactor-engineer dispatch
**Supersedes:** None. Extends `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` Part B §"Sprint 10" with ticket-level detail.
**Parent active read path:** `PRODUCT.md`, `STATE.md`, `PIVOTS.md`, `ROADMAP.md`
**Discipline:** Subagent Handoff Discipline (CLAUDE.md L27–46) — verbatim-quote load-bearing claims, never assume, atomic flag flip + fixture re-pin, no narrative outside summary files.

---

## REVISION HISTORY

```
REVISION HISTORY
- 2026-05-25 v1 — initial dispatch
- 2026-05-25 v2 — four-state ModelFitStatus; business-stage-keyed thresholds; ML-fit lowest-precedence pin; RFM floor doc; operator-only S10 output; T0 confirmed in S10; KI-NEW-P stage-grid; Deviation-check + L632 + Addendum 2 corrections (per ds-architect-s10-plan-review.md, ds-architect-s10-cold-start-and-eb-interaction.md, ds-architect-s10-vocab-stacking.md, and DS business-config inline verdict 2026-05-25)
```

Revisions in v2 incorporate four founder-accepted DS verdicts:
1. `agent_outputs/ds-architect-s10-plan-review.md` (PASS-WITH-CHANGES; 9 required changes).
2. `agent_outputs/ds-architect-s10-cold-start-and-eb-interaction.md` (four-state vocabulary; two ReasonCodes; RFM floor; month-2-return via EB).
3. `agent_outputs/ds-architect-s10-vocab-stacking.md` (Option A — keep shared VALIDATED/PROVISIONAL labels, namespace-disambiguate via dataclass + casing).
4. Inline DS verdict on business-config-keyed thresholds (extend `config/gate_calibration.yaml`, no new artifact).

---

## Part A — Framing

### A.1 What S10 is

ROADMAP.md L20–25 verbatim:

> S10 anchor goals (queued, not yet dispatched):
> 1. BG/NBD model fit per merchant (Fader/Hardie classical) producing per-customer P(alive) + expected-transactions.
> 2. Gamma-Gamma monetary-value fit producing per-customer expected-revenue, gated on BG/NBD acceptance.
> 3. `ModelFitStatus` 3rd-gate (VALIDATED / PROVISIONAL / REFUSED) — joins cohort-p and priors-validation as the third orthogonal gate.
> ML predictive layer lives in the AUDIENCE step of the pipeline — it does not add plays; it ranks customers within each play's audience.

Note: the ROADMAP quote above is the *unrevised* anchor language. Per DS verdict `ds-architect-s10-cold-start-and-eb-interaction.md`, the three-state vocabulary is superseded by a **four-state** ModelFitStatus (see §C.3). ROADMAP L20–25 should be updated at S10 close to reflect the four-state outcome (carried in S10 close-out summary, not in this plan revision).

PIVOTS.md L84–90 (Pivot 8) frames why this matters in beta:

> Beta success = month-1-wow (defensible slate on first run) + month-2-return (ML refit on 30 more days produces materially different/better recommendations).

S10 lays the first half of the ML substrate. S11/S12 add survival/CF/RFM/retention. S13 integrates ML→AUDIENCE and lands the `month_2_delta` typed surface that closes the loop on month-2-return. **S10 alone does not deliver merchant-visible month-1-wow** — see §G.1; the visible artifact at S10 close is `engine_run.predictive_models`, operator-readable JSON, not merchant-rendered.

**Linear-sequencing supersession:** Addendum 2 of `agent_outputs/beacon-ml-roadmap-reconciled-review.md` (L665–715) supersedes linear Phase 7→8→9 sequencing; S10 sits on the BEACON-TRACK substrate. The SWARM track consumes S10 ModelCard schemas as frozen contracts.

### A.2 What S10 is NOT

- Not adding plays. Per ROADMAP L25 and PIVOTS.md Pivot 8. The Tier-B 5-builder set is frozen for S10–S13 (see DS invariant 15 in `memory.md` S8 Q3/Q6/Q7 entry: "no new Tier-B builders through S13").
- Not wiring ML scores into PlayCards. That's S13-T1/T3. S10 ships ModelCards + parquet artifacts only; PlayCard contract additions are flag-OFF stubs.
- Not Phase 9 outcome calibration (deferred S15+ per ROADMAP §4).
- Not banned ML (D-6): no LinUCB/Thompson, VIP optimization, new-product targeting, bundle combinatorial, stockout, cause→core. BG/NBD + Gamma-Gamma are the explicit D-6 carve-out under "classical Fader/Hardie + peer-reviewed lineage" (`agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` L131 carve-out language).
- **Not merchant-facing.** All S10 output is operator-only via `engine_run.json`. No renderer code, no `briefing.html` changes, no merchant-facing copy.

### A.3 What is already on disk (do not re-add)

Grep on `src/engine_run.py` shows S10 PlayCard fields **already stubbed**:

- L784 `class PlayCard:`
- L814 `predicted_segment: Optional[PredictedSegment] = None`
- L815 `model_card_ref: Optional[ModelCardRef] = None`
- L771 `class ModelCardRef:` (currently carries `notes: Optional[str]` only)
- `_from_dict_predicted_segment` + `_from_dict_model_card_ref` round-trip helpers exist (L1191, L1197).

S10-T1 must **populate** the existing stub dataclasses rather than introduce them. This eliminates a PlayCard schema-additive ticket and reduces churn.

`src/memory/lineage.py` exists (substrate lineage helper from S-2). The `compute_lineage_id` helper at L28–63 requires all four args `(play_id, audience_definition_id, store_id, audience_definition_version)`. The lineage-keyed-fatigue fix lives upstream of S10 ML; see §F below.

`PlayCard.predicted_segment` and `PlayCard.model_card_ref` stubs **stay `None` at S10 close.** S13 wires the populating producers. S10 ships only the typed `engine_run.predictive_models` top-level slot.

---

## Part B — Target architecture (S10 close)

```
                                     ┌────────────────────────────────────────────┐
                                     │  PROFILE → AUDIENCE → MEASUREMENT          │
                                     │  → SIZING → DECIDE                         │
                                     │                                            │
                                     │  S10 inserts: PREDICTIVE_FIT (pre-AUDIENCE)│
                                     │     ↓                                      │
                                     │  per-store ModelCards + parquet artifacts  │
                                     └────────────────────────────────────────────┘

     New on disk under data/<store_id>/predictive/:
       - bgnbd.parquet           (customer_id, p_alive, expected_purchases_30d/180d)
                                  WRITTEN only when fit_status in {VALIDATED, PROVISIONAL}
       - gamma_gamma.parquet     (customer_id, predicted_monetary_value_30d/180d)
                                  WRITTEN only when fit_status in {VALIDATED, PROVISIONAL}
       - <model>.model_card.json (mirror of in-JSON ModelCard for offline audit)
                                  WRITTEN only when fit attempted (status != INSUFFICIENT_DATA)

     New in engine_run.json (OPERATOR-ONLY, not merchant-rendered):
       - engine_run.predictive_models: Dict[model_name, ModelCard]
         (typed slot; populated only when flag ON AND fit attempted)
         (INSUFFICIENT_DATA → no entry; REFUSED → entry present with empty parameters)

     PlayCard:
       - predicted_segment   — REMAINS Optional[PredictedSegment]=None at S10 close
                                (S13-T3 populates; S10 ships ModelCards only)
       - model_card_ref      — REMAINS Optional[ModelCardRef]=None at S10 close

     Three orthogonal gates (STATE.md §4) — precedence order documented at S10-T3:
       1. Audience-floor       (AUDIENCE)         — unchanged
       2. Cohort p-value       (MEASUREMENT)      — unchanged
       3. Prior-validation     (SIZING/PRIORS)    — unchanged
       4. ModelFitStatus       (AUDIENCE-rank)    — INSTALLED dormant in S10;
                                                    LOWEST precedence — never demotes
                                                    between slate roles; consumed S13
```

Key shape decision: **S10 inserts PREDICTIVE_FIT between CSV load and AUDIENCE, but the ModelFitStatus *gate effect* is dormant in S10.** Models fit; ModelCards land in `engine_run.json.predictive_models`; per-customer parquet artifacts persist (when status permits). No PlayCard consumes any of it. ML-fit becomes a *ranking-strategy floor* at S13 — NOT a slate-role demotion gate.

This shape is what makes S10 fixture-byte-identical until each atomic flip ticket, and what lets S10 ship without any DECIDE-layer change.

---

## Part C — Assumptions (explicit, multi-option flagged)

### C.1 BG/NBD library choice

**Default:** `lifetimes` package (Cam Davidson-Pilon / Fader & Hardie classical implementation, pure-Python, peer-reviewed lineage).

**Alternative:** `pymc-marketing` (PyMC-based Bayesian re-implementation with full posterior). Provides credible intervals natively but pulls PyMC + PyTensor as heavy deps; macOS-ARM build risk.

**Recommendation:** ship `lifetimes`. Founder confirms if Bayesian posteriors are required at S10 (recommend deferring to S15+ if any).

**Risk:** `lifetimes` is in maintenance mode; last release ~2020. Math is stable, but if the package breaks on a Python upgrade (3.13+), we own a fork. Acceptable given the math surface is small and lifted directly from Fader/Hardie (2005). Vendor-fork escape hatch deferred to a later sprint (KI-NEW-Q candidate, deferred per founder).

### C.2 Gamma-Gamma implementation

**Default:** `lifetimes.GammaGammaFitter`. Gated on BG/NBD `fit_status in {VALIDATED, PROVISIONAL}` *and* on the **frequency-monetary correlation sanity check** (formerly labeled "Gamma-Gamma independence check"). The label change reflects DS verdict honesty: the Pearson-r cutoff is an advisory ranking gate, not a theoretical independence test. The Fader-Hardie-Lee 2005 derivation assumes independence; our cutoffs are advisory thresholds at which the empirical violation makes magnitude quoting unsafe.

Thresholds live in `config/gate_calibration.yaml::model_fit_thresholds.gamma_gamma` (see §C.4):

- `|pearson_r| < 0.3` → VALIDATED (subject to other criteria).
- `0.3 ≤ |pearson_r| < 0.5` → PROVISIONAL with `fit_warnings=["frequency_monetary_correlation"]`.
- `|pearson_r| ≥ 0.5` → REFUSED for monetary inference.

Document in ModelCard docstring: "advisory cutoffs, not theoretical independence test."

### C.3 ModelFitStatus — four-state vocabulary (founder-accepted, supersedes v1 tri-state)

Per `agent_outputs/ds-architect-s10-cold-start-and-eb-interaction.md`. The closed enum `ModelFitStatus` carries **four states**:

- **`VALIDATED`** — fit converged, cold-start floor cleared, holdout MAPE < `holdout_mape_validated`, no warnings. Ranking + magnitudes both usable at S13.
- **`PROVISIONAL`** — fit converged, envelope thin (floor cleared at relaxed multipliers OR MAPE between validated and validated+addend). Ranking usable; magnitudes not quotable to merchant. Load-bearing for S13 audience-builder consumption: PROVISIONAL fit is usable for ranking, REFUSED/INSUFFICIENT_DATA is not.
- **`INSUFFICIENT_DATA`** — engine **DECLINED** to fit (below the cold-start floor for `months_data` / `repeat_customers` / `orders`). Silent fallback (no operator alert). **No parquet artifact written** (D-2/D-3 deletion-trivial). ModelCard entry present in `engine_run.predictive_models` with empty parameters; the audit story is "we didn't try."
- **`REFUSED`** — engine **tried**, fit failed (ConvergenceWarning, MAPE above the relaxed threshold, or independence-check above its REFUSED cutoff). Operator alert. ModelCard present with `fit_warnings` populated; parquet not written. The audit story is "we tried and it didn't work."

Documented load-bearing in `src/predictive/model_card.py`:

> `INSUFFICIENT_DATA` and `REFUSED` have different audit stories and different privacy semantics. `INSUFFICIENT_DATA` produces no per-customer artifact at all (D-3 deletion is a no-op). `REFUSED` produces a ModelCard with fit_warnings + diagnostic state but still no parquet.

**Vocabulary-stacking discipline (DS Option A — no rename):**

The `ModelFitStatus` enum reuses the `VALIDATED`/`PROVISIONAL` labels also used by `PriorValidationStatus`. The two are namespace-disambiguated by:
- **Different dataclasses.** `Prior.validation_status: PriorValidationStatus` vs `ModelCard.fit_status: ModelFitStatus`. Two distinct typed slots.
- **Different casing.** `PriorValidationStatus` values are lowercase (`validated_external`, `heuristic_unvalidated`, `placeholder`). `ModelFitStatus` values are uppercase (`VALIDATED`, `PROVISIONAL`, `INSUFFICIENT_DATA`, `REFUSED`).
- **Docstring cross-reference.** The `ModelCard` docstring explicitly states the parallel and the difference.
- **Docstring on `ReasonCode`.** Distinguishes `MODEL_FIT_INSUFFICIENT_DATA` (per-play, ML-fit, S13-consumed) from `COLD_START_INSUFFICIENT_DATA` at `src/engine_run.py:106` (run-level, existing).

### C.4 ModelFitStatus thresholds — business-stage-keyed via `config/gate_calibration.yaml`

**Founder-accepted (inline DS verdict 2026-05-25):** the universal threshold table in v1 §C.3 is replaced with a stage-keyed schema living in the existing `config/gate_calibration.yaml` (no new artifact). The classifier consumes a dict resolved per-store, not module-level constants.

**Schema to add (verbatim, to be appended to `config/gate_calibration.yaml`):**

```yaml
model_fit_thresholds:
  bgnbd:
    by_business_stage:
      startup:    {months_data_validated: 4, repeat_customers_validated: 150, orders_validated: 450, holdout_mape_validated: 0.30}
      growth:     {months_data_validated: 6, repeat_customers_validated: 300, orders_validated: 900, holdout_mape_validated: 0.27}
      mature:     {months_data_validated: 6, repeat_customers_validated: 500, orders_validated: 1500, holdout_mape_validated: 0.25}
      enterprise: {months_data_validated: 6, repeat_customers_validated: 1000, orders_validated: 3000, holdout_mape_validated: 0.22}
    by_vertical_months_override:
      supplements: 4   # replenishment cadence ≈45-90d; 2 cycles ≈4mo
      beauty: 6        # discretionary cadence; full loop
    relaxation_factors:
      provisional_n_multiplier: 0.5
      provisional_mape_addend: 0.10
  gamma_gamma:
    independence_pearson_r_validated: 0.3
    independence_pearson_r_provisional: 0.5
```

**Lookup precedence (most-specific wins):**

1. Resolve `stage = profile.business_stage.stage` → read `by_business_stage[stage]`.
2. For `months_data_validated` only: if `by_vertical_months_override[profile.vertical]` exists, **replace** the stage cell's months value.
3. Apply existing stage-uncertainty broadening (HIGH uncertainty → next-smaller stage cell). Free inheritance from `derive_gate_calibration` (see `src/profile/builder.py` precedent).
4. Flag-OFF / `profile=None` fallback: hardcoded `mature` cell.

**Classifier rules (per-stage cell + relaxation):**

- VALIDATED: `months_data ≥ months_data_validated` AND `repeat_customers ≥ repeat_customers_validated` AND `orders ≥ orders_validated` AND `holdout_mape < holdout_mape_validated` AND no warnings.
- PROVISIONAL: `months_data ≥ months_data_validated` AND `repeat_customers ≥ provisional_n_multiplier × repeat_customers_validated` AND `orders ≥ provisional_n_multiplier × orders_validated` AND `holdout_mape < holdout_mape_validated + provisional_mape_addend`, and not VALIDATED.
- INSUFFICIENT_DATA: below the PROVISIONAL floor on `months_data` / `repeat_customers` / `orders`. Engine declines to fit (no parquet).
- REFUSED: PROVISIONAL floor met but fit raises `ConvergenceWarning`, MAPE above `holdout_mape_validated + provisional_mape_addend`, or independence check REFUSED.

**T1 must add** a `_load_model_fit_thresholds(profile) -> dict` helper (~20 LOC) in `src/predictive/model_card.py` (or a sibling) that reads `gate_calibration.yaml`, resolves the stage cell + vertical override (`months_data` only), and returns the dict consumed by the BG/NBD classifier. The classifier function takes this dict, **NOT module-level constants.**

**Lock posture (founder-accepted):**

- The `by_business_stage` numbers are heuristic; calibration is open at KI-NEW-P (filed at S10-T3 close — see §H).
- The **vertical-override `months_data` is theory-driven (cadence math), NOT empirical — locked now**, do NOT defer to KI-NEW-P calibration.
- The relaxation factors (0.5 multiplier, 0.10 addend) are pinned across all stages until KI-NEW-P calibration data lands.

### C.5 Privacy posture

Per-customer ML scores persist to `data/<store_id>/predictive/<model_name>.parquet` **only when `fit_status in {VALIDATED, PROVISIONAL}`**. `engine_run.json` carries only ModelCards (aggregate fit metadata) at S10 close. Per-audience aggregate `predicted_segment` lands in S13, never per-customer detail.

This is load-bearing for D-2 retention semantics (parquet artifact deletion = store-wipe unit per D-3) and for the `engine_run.json` size envelope. `INSUFFICIENT_DATA` makes deletion trivial (no artifact). `REFUSED` writes the ModelCard JSON mirror but no parquet.

### C.6 Cold-start fallback (RFM as ranking-strategy floor — pin for S13)

When ML-fit returns `INSUFFICIENT_DATA` or `REFUSED` for a model, no PlayCard surfaces with `predicted_segment` filled by that model at S13. The S13 audience-builder ranking-strategy chain is documented (not coded at S10):

```
BG/NBD → CF → survival → RFM → recency
```

**RFM is the floor; recency is absolute last-resort.** INSUFFICIENT_DATA on all four ML models still produces a non-empty audience via recency. This is pinned in S13 acceptance: `test_cold_start_merchant_gets_non_empty_slate_with_rfm_fallback` (documented here for forward-compat; lives in S13, not S10).

In S10, the fallback target is "no per-customer ranking" = current default behavior. That is why S10 keeps fixtures byte-identical until each flag flip.

**Month-2-return preserved via EB, not ML.** A cold-start merchant on month-2 may still be `INSUFFICIENT_DATA` on every ML model, **but their revenue ranges shift because EB's `bayesian_blend` sees real observed data** (`n_observed` shift in `src/sizing.py`). This is the load-bearing month-2 wow path for new merchants. Pin in S13 acceptance test; document here for forward-compat.

### C.7 Determinism

Every fit is seeded. `lifetimes` BG/NBD uses `scipy.optimize.minimize` deterministically given fixed initial parameters; we pass `penalizer_coef` and a fixed seed where relevant. Gamma-Gamma is closed-form MLE — deterministic by construction. Holdout split uses `hashlib.sha1(customer_id||"holdout_v1")` modulo 5 == 0 — reproducible across runs.

---

## Part D — Ticket decomposition

S10 follows the S7.6 / S8 atomic cadence: every flag flip is its own ticket and ships with the pinned-fixture re-pin in the same commit (S3 Risk #4 discipline). Each ticket commit body carries `Deviation check: none` (or describes prior-approved deviation).

### S10-T0 — Lineage-keyed fatigue correctness fix (CONFIRMED IN S10)

**Scope:** Re-key the fatigue gate from `play_id`-only (the v1 plan misstated `src/guardrails.py:604`; actual `gate_recently_run` body starts at **`src/guardrails.py:632`**) to `lineage_id = sha1(store_id | play_id | audience_definition_id | audience_definition_version)`. The helper `src/memory/lineage.py::compute_lineage_id` (L28–63) already exists from S-2 and requires all four args.

**Files touched:**
- `src/guardrails.py:632` (current `play_id`-only fatigue key callsite — `gate_recently_run` function body).
- `src/memory/events.py` — read view query gains lineage filter.

**Why in S10-T0:** `agent_outputs/play-lifecycle-discussion-reconciled.md:47` verbatim:

> Engine-fatigue gating should be lineage-keyed (play_id × audience_definition_id × store_id), not play_id-keyed. M5's current keying is a correctness bug regardless of broader lifecycle scope.

`RECENTLY_RUN_FATIGUE_ENABLED` is currently OFF per Sprint 1 closeout (STATE.md §6), so the bug is **dormant in production**. However:
- (a) S13 turns this on as a beta-launch dependency to support `month_2_delta` lineage continuity.
- (b) The fix is ~1 day; bundling it as T0 avoids a separate ticket entirely.
- (c) The lineage helper already exists with the required 4-arg signature.

**Acceptance:**
- New test `tests/test_s10_t0_lineage_keyed_fatigue.py` (~6 tests): two distinct audiences of the same `play_id` fatigue independently; same `(play_id, audience_definition_id, store_id, audience_definition_version)` triggers fatigue; `audience_definition_version` bump forks a new lineage.
- Beauty + Supplements fixtures byte-identical (flag remains OFF default; behavior change is dormant).
- M0 byte-identical.

**Flag:** `RECENTLY_RUN_FATIGUE_ENABLED` remains OFF. T0 is a pure correctness fix; no flag flip.

**Load-bearing invariant pin:** Lineage-keyed fatigue is the audit-honest primary key for "is this the same recommendation we made before?" (`agent_outputs/ecommerce-ds-architect-play-lifecycle-discussion.md:109`).

**Commit-body Deviation check (verbatim):**

> Deviation check: none. Single-demote-channel invariant unaffected — `gate_recently_run` runs inside the guardrails pass and produces a `RejectedPlay`, not a post-guardrails injection.

---

### S10-T1 — `lifetimes` integration + BG/NBD fit + ModelCard plumbing + business-config thresholds

**Scope:**
- Add `lifetimes` to `requirements.txt` with **hard-pinned** version + `scipy<1.13` hard pin (not "verify"). The `scipy<1.13` pin is required for some `lifetimes` optimizer paths.
- New `src/predictive/__init__.py`, `src/predictive/bgnbd.py`:
  - `fit_bgnbd_model(orders_df, *, store_id, training_window_days, seed, thresholds: dict) -> Tuple[Optional[BGNBDFit], ModelCard]`
  - Cold-start guard returns `(None, ModelCard(fit_status=INSUFFICIENT_DATA, ...))` rather than raising — silent decline.
  - Fit-failure guard returns `(None, ModelCard(fit_status=REFUSED, fit_warnings=[...]))` — operator alert.
- New `src/predictive/model_card.py`:
  - `class ModelFitStatus(Enum)` — four values: `VALIDATED`, `PROVISIONAL`, `INSUFFICIENT_DATA`, `REFUSED`. Closed enum.
  - `class ModelCard` (dataclass): `model_name`, `fit_status`, `holdout_mape: Optional[float]`, `n_observed: int`, `training_window_days: int`, `fit_warnings: List[str]`, `fit_timestamp: str`, `parameters: Dict[str, float]` (BG/NBD's r/α/s/β when fit succeeded; `{}` otherwise).
  - **Docstring** explicitly states (a) the `VALIDATED`/`PROVISIONAL` parallel with `PriorValidationStatus`, (b) the casing distinction, (c) PROVISIONAL semantics: "fit converged, envelope thin, ranking may be ordered correctly but absolute LTV magnitudes should not be quoted to merchant," (d) INSUFFICIENT_DATA vs REFUSED audit-story difference, (e) the Gamma-Gamma cutoffs as "advisory cutoffs, not theoretical independence test."
  - `_load_model_fit_thresholds(profile) -> dict` helper (~20 LOC). Reads `config/gate_calibration.yaml`, resolves the stage cell + vertical override (`months_data` only), applies stage-uncertainty broadening, returns the dict.
- Append `model_fit_thresholds` block (§C.4) to `config/gate_calibration.yaml`.
- **Populate** existing `ModelCardRef` stub at `src/engine_run.py:771` (currently only `notes: Optional[str] = None`) with the matching fields. Round-trip helpers `_from_dict_model_card_ref` already exist (L1197) — extend in place.
- Wire `engine_run.json` to carry `predictive_models: Dict[str, ModelCard]` typed slot. Empty `{}` when flag OFF or no fits attempted.
- **Beauty fixture measurement spike (folded into T1's first commit).** Measure the existing Beauty fixture (sha `f8676c9f…`): count repeat customers + orders. Pin the acceptance criterion to whatever the measurement honestly returns. Beauty is `mature` stage; the floor under the new config is `repeat=500, orders=1500, mape<0.25` (matches prior universal numbers — the v1 contradiction collapses on this fixture). If Beauty does not naturally clear those numbers, accept PROVISIONAL. **Do NOT reshape the fixture (Pivot 5).**

**Files touched:**
- NEW: `src/predictive/__init__.py`, `src/predictive/bgnbd.py`, `src/predictive/model_card.py`
- MODIFIED: `src/engine_run.py` (extend `ModelCardRef`, add `predictive_models` slot on top-level run dataclass)
- MODIFIED: `src/utils.py` (new flag `ENGINE_V2_ML_BGNBD`, default OFF)
- MODIFIED: `requirements.txt` (hard pin `lifetimes`, hard pin `scipy<1.13`)
- MODIFIED: `config/gate_calibration.yaml` (append `model_fit_thresholds` block — §C.4)
- NEW tests: `tests/test_s10_t1_bgnbd_fit.py`, `tests/test_s10_t1_model_card.py`, `tests/test_s10_t1_threshold_loader.py`

**Acceptance:**
- ~22 tests covering: INSUFFICIENT_DATA on M0 micro_coldstart (silent decline, no parquet, no operator alert); VALIDATED *or* PROVISIONAL on Beauty per measured fixture honestly; PROVISIONAL on a mid-size synthetic fixture; REFUSED on a synthetic where fit raises ConvergenceWarning; deterministic fit under seed (G-7 contract); holdout MAPE thresholds; fit_warnings populated for REFUSED; no per-customer scores leak to `engine_run.json`; parquet write path correct; ModelCard round-trips JSON.
- New: `test_threshold_loader_stage_cell` (startup vs growth vs mature returns different dicts); `test_threshold_loader_vertical_override_months` (supplements stage=mature returns months=4, beauty stage=mature returns months=6); `test_threshold_loader_flag_off_fallback` (profile=None returns mature cell).
- Beauty / Supplements / M0 (3) pinned fixtures **byte-identical** (flag OFF default → `predictive_models={}`).
- DS invariant 16 honored: harness test `tests/test_v2_harness_cfg_gated_fields.py` extended to call `main.run_action_engine` with `ENGINE_V2_ML_BGNBD=true` and assert `predictive_models["bgnbd"]` populated.

**Flag:** `ENGINE_V2_ML_BGNBD` default OFF.

**Load-bearing invariant pin:** ModelCard schema is closed and additive within `event_version=1` (S8 discipline). ModelFitStatus is a closed four-value enum; new statuses require explicit founder + DS sign-off. Single source of truth for fit health.

**Commit pattern (3 commits):** impl + memory.md entry + `agent_outputs/code-refactor-engineer-s10-t1-summary.md` (per S6/S7 dispatch precedent; CLAUDE.md memory rule). Commit body carries `Deviation check: none`.

---

### S10-T1.5 — Atomic flag flip `ENGINE_V2_ML_BGNBD` ON + parquet artifacts + fixture re-pin

**Scope:**
- Flip `ENGINE_V2_ML_BGNBD` default `false → true`.
- Per-customer `p_alive`, `expected_purchases_30d`, `expected_purchases_180d` persisted to `data/<store_id>/predictive/bgnbd.parquet` — **only when `fit_status in {VALIDATED, PROVISIONAL}`**.
- ModelCard mirror written to `data/<store_id>/predictive/bgnbd.model_card.json` (audit redundancy with `engine_run.json`) **only when fit attempted** (i.e., status != INSUFFICIENT_DATA).
- Beauty + Supplements pinned slates re-pinned: `engine_run.json` gains `predictive_models.bgnbd` typed slot (Beauty per T1 measurement spike, Supplements per fixture characterization).
- M0 fixtures (3) remain **byte-identical** — BG/NBD returns INSUFFICIENT_DATA on M0 micro_coldstart (engine declines to fit silently — no ModelCard entry written for INSUFFICIENT_DATA per §C.3 audit semantics? **Clarification:** ModelCard entry IS written with `fit_status=INSUFFICIENT_DATA` and empty parameters; what is NOT written is the parquet. M0 fixtures must be re-pinned if `predictive_models["bgnbd"]` entry is added even with INSUFFICIENT_DATA — verify in T1 design; if M0 sha changes, re-pin atomically here).
- Renderer surface (`briefing.html`) byte-identical — no rendering of `predictive_models` ever (operator-only output per §A.2).

**Files touched:** `.env` / `src/utils.py` flag default; pinned-fixture sha files; test fixture mirrors.

**Tests:** ~8 new in `tests/test_s10_t1_5_bgnbd_repin.py`:
- Per-fixture before/after `predictive_models` typed slot pinned.
- Parquet artifact existence ONLY for VALIDATED/PROVISIONAL fixtures; ABSENT for INSUFFICIENT_DATA/REFUSED.
- Per-customer envelope sanity: `p_alive ∈ [0,1]`, `expected_purchases_*d ≥ 0`.
- Rollback safety: operator override `ENGINE_V2_ML_BGNBD=false` reproduces pre-T1.5 fixture sha exactly.
- Briefing.html byte-identical pre/post flip.

**Acceptance:**
- All 5 pinned fixtures (Beauty + Supplements + M0 small_sm + M0 mid_shopify + M0 micro_coldstart) deliberately re-pinned with new sha values where ModelCard entries land; M0 may stay byte-identical if `predictive_models["bgnbd"]` is omitted on INSUFFICIENT_DATA (founder-decidable detail in T1 design — recommend "INSUFFICIENT_DATA still emits ModelCard entry" for audit completeness, re-pin M0 accordingly).
- Suite green; DS invariant 16 satisfied.

**Flag:** flipped ON.

**Load-bearing invariant pin:** atomic flip + fixture re-pin in single commit (S3 Risk #4 discipline). Rollback contract enforced by test. Commit body carries `Deviation check: none`.

---

### S10-T2 — Gamma-Gamma extension for `predicted_monetary_value` per customer

**Scope:**
- New `src/predictive/gamma_gamma.py` (recommended) with `fit_gamma_gamma_model(orders_df, bgnbd_fit, *, seed, thresholds: dict) -> Tuple[Optional[GammaGammaFit], ModelCard]`.
- Chained on BG/NBD `fit_status in {VALIDATED, PROVISIONAL}`. If BG/NBD `INSUFFICIENT_DATA` → G-G `INSUFFICIENT_DATA` (chained no-fit). If BG/NBD `REFUSED` → G-G `REFUSED` (chained dependency).
- **Frequency-monetary correlation sanity check** (relabeled per DS verdict — §C.2). Thresholds read from `config/gate_calibration.yaml::model_fit_thresholds.gamma_gamma`: `|r| < 0.3` permits VALIDATED; `0.3 ≤ |r| < 0.5` → PROVISIONAL with warning; `|r| ≥ 0.5` → REFUSED for monetary inference.
- Per-customer `predicted_monetary_value_30d`, `predicted_monetary_value_180d` written to separate `data/<store_id>/predictive/gamma_gamma.parquet` (clean lineage / independent fit refusal) — only when status ∈ {VALIDATED, PROVISIONAL}.
- ModelCard for Gamma-Gamma added to `engine_run.json.predictive_models["gamma_gamma"]`.

**Files touched:**
- NEW: `src/predictive/gamma_gamma.py`
- MODIFIED: `src/utils.py` (new flag `ENGINE_V2_ML_GAMMA_GAMMA`, default OFF)
- NEW tests: `tests/test_s10_t2_gamma_gamma.py`

**Tests:** ~12 covering:
- Independence-check determinism + envelope sanity.
- Chained INSUFFICIENT_DATA when BG/NBD is INSUFFICIENT_DATA.
- Chained REFUSED when BG/NBD is REFUSED.
- Per-customer monetary value within ±3σ of historical AOV distribution.
- Degenerate AOV data REFUSED.
- Seed-determined fit.
- ModelCard plumbing (label is "frequency-monetary correlation sanity check," not "independence test").

**Acceptance:**
- Beauty + Supplements fixtures byte-identical (flag OFF default).
- New ModelCard schema round-trips.

**Flag:** `ENGINE_V2_ML_GAMMA_GAMMA` default OFF.

**Load-bearing invariant:** Gamma-Gamma chained refusal is non-negotiable — Fader-Hardie-Lee (2005) derivation requires the BG/NBD fit as input. Commit body carries `Deviation check: none`.

---

### S10-T2.5 — Atomic flag flip `ENGINE_V2_ML_GAMMA_GAMMA` ON + parquet + fixture re-pin

**Scope:** mirror of T1.5 for Gamma-Gamma. Beauty + Supplements re-pinned. M0 byte-identical (chained INSUFFICIENT_DATA).

**Tests:** ~10 covering the four-state matrix × (BG/NBD pass/fail) × (G-G pass/fail). Specifically:
- BG/NBD VALIDATED + G-G VALIDATED → both parquets present.
- BG/NBD VALIDATED + G-G REFUSED → bgnbd.parquet only.
- BG/NBD PROVISIONAL + G-G PROVISIONAL → both parquets present (magnitudes flagged not-quotable).
- BG/NBD INSUFFICIENT_DATA → G-G INSUFFICIENT_DATA, no parquet for either.
- BG/NBD REFUSED → G-G REFUSED, no parquet for either.

**Flag:** flipped ON. Commit body carries `Deviation check: none`.

**Acceptance criteria identical in shape to T1.5.**

---

### S10-T3 (CLOSE) — Three-orthogonal-gate documentation + ReasonCode precedence test + KI-NEW-P filing

**Scope:** No new model. This ticket lands the **gate-precedence test** that pins the audit story before S11 piles on more models, and files KI-NEW-P for stage-grid threshold calibration.

- New test `tests/test_reason_code_precedence_invariant.py`:
  - **Strict precedence on Considered routing**: (1) audience-floor → (2) cohort p-value → (3) prior-validation → (4) **ML-fit (lowest)**.
  - Every Considered card emits exactly one ReasonCode; the ReasonCode matches the highest-precedence failed gate.
  - **ML-fit is the lowest-precedence gate — never demotes between slate roles.** Pinned verbatim in test docstring:
    > When `MODEL_FIT_REFUSED` / `MODEL_FIT_INSUFFICIENT_DATA` is the only failing gate, the card stays in Recommended Now (or Recommended Experiment) and the audience ranking falls back to RFM/recency. Only audience-floor, cohort-p, and prior-validation failures route to Considered.
- Document the precedence in `docs/engine_flags.md` (three-orthogonal-gate ML-fit row, plus the ranking-strategy chain `BG/NBD → CF → survival → RFM → recency` documented as the S13 fallback).
- **Add two ReasonCodes to the `ReasonCode` enum at `src/engine_run.py:73`** (additive within `event_version=1`; dormant at S10 close, consumed at S13):
  - `MODEL_FIT_INSUFFICIENT_DATA = "model_fit_insufficient_data"`
  - `MODEL_FIT_REFUSED = "model_fit_refused"`
  - Both prefixed `MODEL_FIT_` to disambiguate from existing `COLD_START_INSUFFICIENT_DATA` at `src/engine_run.py:106` (run-level cold-start, different layer). The `ReasonCode` docstring is updated to document the distinction.
- **File KI-NEW-P** at sprint close (not now). Filing shape:
  - **Title:** ModelFitStatus thresholds calibration suite.
  - **Dimensions:** `business_stage × {bgnbd, gamma_gamma}`. ~20 numbers organized as 4 stage rows × 4 metrics + 2 vertical-month overrides.
  - **Closure criterion:** each stage cell needs ≥3 real beta merchants at that stage with realized-vs-predicted MAPE data; founder reviews false-VALIDATED rate (>20% = retune).
  - **Out-of-scope:** vertical-override `months_data` (theory-locked, not empirical).
  - **Filed at S10-T3 close** in `KNOWN_ISSUES.md`.
- **KI-NEW-Q** (`lifetimes` maintenance risk + vendor-fork escape hatch) and **KI-NEW-R** (operator parquet query CLI): **DEFERRED** to a later sprint per founder. Not filed at S10 close.

**Files touched:** `src/engine_run.py` (two ReasonCode enum values + docstring), `docs/engine_flags.md`, `KNOWN_ISSUES.md` (KI-NEW-P filing — at sprint close, per CLAUDE.md template-shape rule), tests new.

**Acceptance:**
- All 5 pinned fixtures byte-identical.
- New precedence test green.
- ReasonCode enum carries the two new dormant values; no consumer wired (S13).
- KI-NEW-P filed; KI-NEW-Q/R explicitly deferred.
- Suite green.

**Flag:** none. Commit body carries `Deviation check: none`.

**Load-bearing invariant pin:** three-orthogonal-gate discipline + ML-fit-lowest-precedence pinned by `tests/test_reason_code_precedence_invariant.py`. ML-fit failure routes to ranking-strategy fallback (RFM → recency), **never** to slate-role demotion.

---

### Ticket count summary (unchanged from v1: 6 tickets)

| Ticket | Scope (one line) | Commits | Flag flip? |
|---|---|---|---|
| S10-T0 | Lineage-keyed fatigue correctness fix (`src/guardrails.py:632`) | 3 | no (flag stays OFF) |
| S10-T1 | BG/NBD fit + ModelCard four-state + business-config thresholds + Beauty measurement spike | 3 | no (default OFF) |
| S10-T1.5 | Flip BG/NBD ON + parquet + re-pin | 3 | yes (atomic) |
| S10-T2 | Gamma-Gamma fit + chained {INSUFFICIENT_DATA, REFUSED} | 3 | no (default OFF) |
| S10-T2.5 | Flip G-G ON + parquet + re-pin | 3 | yes (atomic) |
| S10-T3 | Gate-precedence test + 2 MODEL_FIT_* ReasonCodes + KI-NEW-P filing | 3 | no |
| **Total** | **6 tickets** | **18 commits** | **2 atomic flips** |

Estimated duration: ~11–13 working days (slight upward revision vs v1 due to threshold-loader helper + Beauty measurement spike folded into T1). Mirrors S7.6/S8 cadence.

---

## Part E — Cross-cutting risks

### E.1 ModelFitStatus integration with the orthogonal gates — ML-fit is lowest-precedence

S10 installs ML-fit dormant. No PlayCard surfaces with `model_card_ref` populated at S10 close. The gate becomes *active* when S13-T1 wires `ranking_strategy` into audience builders. Therefore:

- **S10 cannot break the existing three gates** (audience-floor, cohort-p, prior-validation). Pinned-fixture byte-identity until each atomic flip is the only test that matters here.
- **The precedence test (T3)** pins the audit story *before* a consumer exists. If S13 violates precedence, this test fails at S13 dispatch, not after launch.
- **ML-fit lowest-precedence is load-bearing.** When `MODEL_FIT_REFUSED` / `MODEL_FIT_INSUFFICIENT_DATA` is the only failing gate, the card stays in its slate role and the *audience ranking* falls back to RFM/recency. Only audience-floor, cohort-p, and prior-validation failures route to Considered. The ranking-strategy chain `BG/NBD → CF → survival → RFM → recency` is the documented fallback path; RFM is floor; recency is last-resort.
- The single-demote-channel invariant (PIVOTS.md Pivot 7) is unaffected: S10 does not inject anything to `engine_run.recommendations`.

### E.2 Fixture / test plan

| Fixture | T0 | T1 | T1.5 | T2 | T2.5 | T3 |
|---|---|---|---|---|---|---|
| Beauty | identical | identical | **re-pin** | identical | **re-pin** | identical |
| Supplements G-1 | identical | identical | **re-pin** | identical | **re-pin** | identical |
| M0 small_sm | identical | identical | **possibly re-pin** (INSUFFICIENT_DATA card) | identical | **possibly re-pin** | identical |
| M0 mid_shopify | identical | identical | **possibly re-pin** (INSUFFICIENT_DATA card) | identical | **possibly re-pin** | identical |
| M0 micro_coldstart | identical | identical | **possibly re-pin** (INSUFFICIENT_DATA card) | identical | **possibly re-pin** | identical |

M0 re-pin uncertainty depends on T1 design decision: does `INSUFFICIENT_DATA` emit a ModelCard entry in `engine_run.predictive_models` (recommend yes, for audit completeness — re-pin M0 atomically at T1.5) or omit silently (M0 stays byte-identical)?  **Recommended:** emit ModelCard entry with `fit_status=INSUFFICIENT_DATA`, empty parameters; re-pin M0 at T1.5.

Two atomic re-pin moments only. The T1 measurement spike resolves whether Beauty clears VALIDATED naturally or accepts PROVISIONAL — see §J Q4 (now CLOSED by spike folded into T1).

### E.3 Library choice risks

- `lifetimes` is unmaintained. Mitigation: **hard-pin** version in `requirements.txt` (not "verify"); vendor-fork escape hatch documented but deferred (KI-NEW-Q candidate, deferred per founder).
- macOS-ARM `numpy`/`scipy` pin conflict possible. Mitigation: CI smoke test on `import lifetimes; from lifetimes import BetaGeoFitter; BetaGeoFitter()` added as part of T1.
- `lifetimes` historically requires `scipy<1.13` for some optimizer paths. **Hard pin** `scipy<1.13` in `requirements.txt` at T1.

### E.4 PlayCard additive contract

S10 leaves `PlayCard.predicted_segment` and `PlayCard.model_card_ref` as `Optional[...]=None` (they already exist at L814–815). No round-trip break. `event_version=1` preserved. S13-T3 is the populating ticket.

What S10 *does* add to schema:
- `engine_run.predictive_models: Dict[str, ModelCard]` (new top-level slot).
- `ModelCard` typed dataclass (new).
- `ModelFitStatus` enum (new, closed, four values).
- `ReasonCode.MODEL_FIT_INSUFFICIENT_DATA` and `ReasonCode.MODEL_FIT_REFUSED` (new dormant enum values).

All additive within `event_version=1`. DS invariant 12 cap of 3 trust-surface PlayCard fields from S8 is **not breached** — `predictive_models` is on `engine_run`, not `PlayCard`.

---

## Part F — Test plan additions for the v2 revisions

In addition to the per-ticket tests called out above:

- `tests/test_s10_t1_threshold_loader.py` — stage cell lookup; vertical-override on `months_data` only; flag-OFF fallback to mature cell; stage-uncertainty broadening (HIGH → next-smaller stage).
- `tests/test_reason_code_precedence_invariant.py` — strict precedence `(1) audience-floor → (2) cohort p-value → (3) prior-validation → (4) ML-fit`; ML-fit-only failure does NOT route to Considered, instead falls back in ranking strategy; every Considered card emits exactly one ReasonCode.
- `tests/test_s10_privacy_envelope.py` — no per-customer scores in `engine_run.json`; only ModelCards. INSUFFICIENT_DATA writes no parquet, no model_card.json mirror. REFUSED writes model_card.json mirror, no parquet.
- `tests/test_s10_t1_model_card.py` — round-trip four-state enum; PROVISIONAL semantics docstring assertion (test reads the docstring and asserts the load-bearing phrase appears).

---

## Part G — Month-1-wow / Month-2-return acceptance for S10

### G.1 What S10 alone delivers — operator-only

- `engine_run.predictive_models.bgnbd.fit_status="VALIDATED"` (or PROVISIONAL per T1 measurement spike) on a healthy Beauty store.
- `engine_run.predictive_models.gamma_gamma.fit_status="VALIDATED"` (or PROVISIONAL) on same, gated on BG/NBD.
- Per-customer parquet artifact present at `data/<store_id>/predictive/bgnbd.parquet` (and `gamma_gamma.parquet`) when status ∈ {VALIDATED, PROVISIONAL}.
- ModelCard `fit_warnings[]` empty for VALIDATED, populated for PROVISIONAL/REFUSED, empty for INSUFFICIENT_DATA (no fit attempted).
- Diagnostic-grade evidence the engine fit a model to *this* merchant's data, with declared training window + four-state cold-start status. **Operator-readable JSON. Not merchant-rendered.**

**S10 does NOT deliver merchant-visible month-1-wow.** That requires S13-T1/T3 (audience ranking + `predicted_segment` block on PlayCard). The visible artifact at S10 close is `engine_run.predictive_models` as the first model-derived JSON object — operator-readable, not merchant-rendered. There are no `briefing.html` or renderer changes in S10.

### G.2 What S10 alone delivers for month-2-return

Nothing visible. `month_2_delta` lands in S13-T2. However:

- After S10, a month-2 re-run on the same store **produces a freshly-fit BG/NBD ModelCard with a new `fit_timestamp` and shifted parameters** (r, α, s, β). The substrate that S13-T2 will diff is *present* after S10.
- Parquet artifacts are timestamped; S13-T2 reads prior month's parquet to compute per-customer LTV delta.
- **Cold-start merchant on month-2 may still be `INSUFFICIENT_DATA`** on every ML model, but their revenue ranges shift because EB's `n_observed` shift in `bayesian_blend` (`src/sizing.py:87–139`) sees real observed data. **Month-2-return is preserved through EB, not ML.** This is the load-bearing month-2 wow path for new merchants. Pin in S13 acceptance (documented here for forward-compat).

### G.3 Beta-acceptance criteria for the S10 close

| # | Criterion | Test home |
|---|---|---|
| 1 | BG/NBD fits VALIDATED or PROVISIONAL on Beauty pinned fixture (per T1 measurement spike) | `tests/test_s10_t1_bgnbd_fit.py::test_beauty_status` |
| 2 | Gamma-Gamma chains correctly: BG/NBD INSUFFICIENT_DATA → G-G INSUFFICIENT_DATA; BG/NBD REFUSED → G-G REFUSED | `tests/test_s10_t2_gamma_gamma.py::test_chained` |
| 3 | M0 micro_coldstart → INSUFFICIENT_DATA, no parquet write, no model_card.json mirror | `tests/test_s10_t1_bgnbd_fit.py::test_m0_insufficient_data` |
| 4 | ReasonCode precedence holds: every Considered card emits one ReasonCode, matched to highest-precedence failed gate; ML-fit-only failure does NOT route to Considered | `tests/test_reason_code_precedence_invariant.py` |
| 5 | DS invariant 16: harness-level test exercises every flag-gated producer field with flag forced ON | `tests/test_v2_harness_cfg_gated_fields.py` extended |
| 6 | All 5 pinned fixtures byte-identical pre/post-S10 except 2 atomic re-pin commits (T1.5, T2.5) | sha pin files |
| 7 | Rollback contract: `ENGINE_V2_ML_BGNBD=false` ∧ `ENGINE_V2_ML_GAMMA_GAMMA=false` reproduces pre-S10 Beauty/Supplements sha exactly | `tests/test_s10_t1_5_bgnbd_repin.py::test_rollback`, `tests/test_s10_t2_5_gamma_gamma_repin.py::test_rollback` |
| 8 | Privacy: no per-customer scores in `engine_run.json`; only ModelCards. INSUFFICIENT_DATA writes neither parquet nor model_card.json mirror | `tests/test_s10_privacy_envelope.py` |
| 9 | Lineage-keyed fatigue test green; flag stays OFF in production | `tests/test_s10_t0_lineage_keyed_fatigue.py` |
| 10 | Threshold loader resolves stage cell + vertical-override months correctly | `tests/test_s10_t1_threshold_loader.py` |

---

## Part H — KIs S10 affects

Cross-referenced against `KNOWN_ISSUES.md`:

| KI | S10 effect |
|---|---|
| KI-NEW-C — `pseudo_n_default` per-stage recalibration | Not directly. ML cold-start thresholds (§C.4) parallel pseudo_N posture; both rely on real-merchant data to tighten. Documents the parallel in S10-T1 summary. |
| KI-NEW-G — `replenishment_due` honest dormancy on Beauty | Unaffected. Replenishment activation is S11 survival territory; honest-dormancy preserved. |
| KI-NEW-L — Collapse 5 V2 prior-anchored injection blocks at `src/main.py:1380-1597` | **NOT in S10.** Per S8 Q3/Q6/Q7 verdict (`memory.md` 2026-05-24), KI-NEW-L is anchored at S13.5 between S13-T4 and S14-T1. The DS-locked conditional invariant 15 ("no new Tier-B builders through S13") still holds — S10 does not add a builder. |
| KI-NEW-M / KI-NEW-N | **NOT in S10.** Anchored at S14-T3 per memory.md L1921 verbatim commitment. |
| KI-NEW-K | Closed S8-T0. No S10 action. |
| KI-1 / KI-2 / KI-4 / KI-5 / KI-9 | Phase 9 entry conditions. Deferred S15+. |
| **KI-NEW-P (NEW — filed at S10-T3 close)** | ModelFitStatus thresholds calibration suite. Dimensions `business_stage × {bgnbd, gamma_gamma}`. Closure criterion: ≥3 real beta merchants per stage; founder reviews false-VALIDATED rate. Vertical-override `months_data` excluded (theory-locked). |
| **KI-NEW-Q / KI-NEW-R (DEFERRED)** | `lifetimes` maintenance + operator parquet query CLI — deferred per founder. Not filed at S10 close. |

---

## Part I — Feature flag strategy

S10 introduces 2 new flags. Per S7.6 / S8 atomic-flip discipline:

| Flag | Lands | Default at land | Flips to ON | Rollback |
|---|---|---|---|---|
| `ENGINE_V2_ML_BGNBD` | T1 | `false` | T1.5 | env override `ENGINE_V2_ML_BGNBD=false` reproduces pre-T1.5 sha |
| `ENGINE_V2_ML_GAMMA_GAMMA` | T2 | `false` | T2.5 | env override `=false` reproduces pre-T2.5 sha |

Each flag flip is its own commit, atomic with the pinned-fixture re-pin.

`RECENTLY_RUN_FATIGUE_ENABLED` — unchanged (OFF). T0 is a correctness fix to the OFF-path code; flag default unchanged.

Operator escape hatches preserved through `.env`. No flag is removed in S10.

---

## Part J — Open questions for the founder

### J.1 Q1 — Lineage-keyed fatigue scope **— CLOSED**

Founder-accepted: T0 stays in S10. 1-day envelope, flag OFF, byte-identical. Re-keys to `(play_id × audience_definition_id × store_id × audience_definition_version)`. The existing `compute_lineage_id` helper in `src/memory/lineage.py:28-63` requires all four args.

### J.2 Q2 — BG/NBD library: `lifetimes` vs `pymc-marketing` **— PROCEED WITH `lifetimes`**

Default stands; founder may revisit at S15+ if Bayesian posteriors are required.

### J.3 Q3 — ModelFitStatus thresholds **— CLOSED**

DS verdict landed. Four-state vocabulary (§C.3); business-stage-keyed thresholds via `config/gate_calibration.yaml` (§C.4); KI-NEW-P filed at S10-T3 close for calibration.

### J.4 Q4 — Beauty fixture cold-start clearance **— CLOSED (folded into T1)**

Beauty fixture measurement spike is T1's first commit. The measurement determines whether Beauty ships VALIDATED or PROVISIONAL on the new thresholds (mature cell: `repeat=500, orders=1500, mape<0.25`). Do NOT reshape the fixture (Pivot 5). Acceptance pins to whatever the measurement honestly returns.

### J.5 Q5 — Privacy envelope **— PROCEED**

Per-customer scores stay in parquet (only when status ∈ {VALIDATED, PROVISIONAL}); only ModelCards in JSON. `INSUFFICIENT_DATA` writes neither parquet nor model_card.json mirror — D-3 deletion is a no-op.

### J.6 Q6 — Parquet schema versioning **— PROCEED**

Ship at T1.5 with `parquet_schema_version=1` column. S11 additive columns must keep S10 readers working.

### J.7 Q7 — M0 fixture re-pin on INSUFFICIENT_DATA **— FOUNDER DECIDABLE in T1 design**

Recommend: INSUFFICIENT_DATA emits ModelCard entry in `engine_run.predictive_models["bgnbd"]` with empty parameters (audit completeness). Re-pin M0 fixtures atomically at T1.5. Alternative is to suppress ModelCard entry on INSUFFICIENT_DATA (M0 stays byte-identical) — but this hides the audit trail. Default: emit + re-pin.

---

## Part K — Files / functions affected (absolute paths)

NEW:
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/__init__.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/bgnbd.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/gamma_gamma.py`
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/model_card.py` (includes `_load_model_fit_thresholds` helper)
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t0_lineage_keyed_fatigue.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t1_bgnbd_fit.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t1_model_card.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t1_threshold_loader.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t1_5_bgnbd_repin.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t2_gamma_gamma.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t2_5_gamma_gamma_repin.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_privacy_envelope.py`
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_reason_code_precedence_invariant.py`
- `/Users/atul.jena/Projects/Personal/beaconai/data/<store_id>/predictive/` (per-store)
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s10-t{0,1,1_5,2,2_5,3}-summary.md` (6 receipt files; CLAUDE.md mandatory)

MODIFIED:
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` — extend `ModelCardRef` (L771); add `predictive_models` top-level slot; add `ReasonCode.MODEL_FIT_INSUFFICIENT_DATA` + `ReasonCode.MODEL_FIT_REFUSED` enum values at the `ReasonCode` block starting L73; update `ReasonCode` docstring to distinguish `MODEL_FIT_INSUFFICIENT_DATA` (per-play, ML-fit, S13-consumed) from `COLD_START_INSUFFICIENT_DATA` (L106, run-level, existing).
- `/Users/atul.jena/Projects/Personal/beaconai/src/guardrails.py:632` — lineage-keyed fatigue fix (T0). (v1's reference to L604 was incorrect; L604 is a stale comment header; the `gate_recently_run` function body starts at L632.)
- `/Users/atul.jena/Projects/Personal/beaconai/src/memory/events.py` — fatigue read view gains lineage filter.
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` — wire `PREDICTIVE_FIT` step post-CSV-load, pre-AUDIENCE; populate `engine_run.predictive_models`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` — 2 new flags.
- `/Users/atul.jena/Projects/Personal/beaconai/requirements.txt` — hard pin `lifetimes`; hard pin `scipy<1.13`.
- `/Users/atul.jena/Projects/Personal/beaconai/config/gate_calibration.yaml` — append `model_fit_thresholds` block (§C.4 verbatim schema).
- `/Users/atul.jena/Projects/Personal/beaconai/docs/engine_flags.md` — document flags + four-orthogonal-gate row with ML-fit-lowest precedence + ranking-strategy chain.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_v2_harness_cfg_gated_fields.py` — DS invariant 16 extension.
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md` — KI-NEW-P filed at S10-T3 close (not earlier).

**Unchanged (load-bearing):**
- `src/sizing.py` — `PSEUDO_N_BY_STATUS = {30,15,10}` LOCKED through S14 per STATE.md §5 invariant 5. Note: the `effective_pseudo_n` precedent at L87–139 ("profile lowers a per-status cap") is the design template for "profile lowers a per-stage ML threshold" in §C.4.
- `src/decide.py` — slate assembly, role-uniqueness, single-demote-channel. No S10 changes.
- `src/measurement_builder.py` — no S10 changes (ML-fit is AUDIENCE-rank layer, dormant in S10).
- `src/main.py:1380-1597` injection-block forbidden zone — DO NOT TOUCH (KI-NEW-L is S13.5).
- `config/priors.yaml` — no S10 changes.

---

## Part L — New artifacts produced at each stage

| Ticket | Artifact |
|---|---|
| T0 | None new — fix is to existing fatigue gate at `src/guardrails.py:632`. |
| T1 | `ModelCard` schema in `engine_run.json`; `ModelFitStatus` four-state enum; `src/predictive/` package; `_load_model_fit_thresholds` helper; appended `model_fit_thresholds` block in `config/gate_calibration.yaml`. |
| T1.5 | `data/<store_id>/predictive/bgnbd.parquet` (status ∈ {VALIDATED, PROVISIONAL}); `bgnbd.model_card.json` mirror (any status != INSUFFICIENT_DATA). Beauty/Supplements re-pinned sha; M0 likely re-pinned (founder Q7 in T1 design). |
| T2 | `GammaGammaFit` schema; chained {INSUFFICIENT_DATA, REFUSED} contract; frequency-monetary correlation sanity check (relabeled). |
| T2.5 | `data/<store_id>/predictive/gamma_gamma.parquet`; mirror json. Beauty/Supplements re-pinned sha. |
| T3 | `tests/test_reason_code_precedence_invariant.py`; two new `ReasonCode` enum values (`MODEL_FIT_INSUFFICIENT_DATA`, `MODEL_FIT_REFUSED`); KI-NEW-P filing in `KNOWN_ISSUES.md`; `docs/engine_flags.md` update. |

---

## Part M — Risks and rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| `lifetimes` install fails on operator macOS-ARM | CI smoke test at T1; **hard-pinned** version | `pip uninstall lifetimes`; `ENGINE_V2_ML_BGNBD=false` |
| `lifetimes` × `scipy>=1.13` optimizer regression | Hard pin `scipy<1.13` in `requirements.txt` at T1 | Re-pin; revert |
| BG/NBD fit on Beauty surfaces PROVISIONAL/REFUSED (fixture too small) | T1 measurement spike pins acceptance to honest measurement; PROVISIONAL accepted | n/a — model card just shows status |
| Determinism drift across runs | Fixed seed + hash-based holdout split (§C.7) | Test catches drift; bisect to fit code |
| Parquet artifact bloats disk | D-2 forever-retention; AWS migration revisits. INSUFFICIENT_DATA writes no parquet | n/a |
| ModelFitStatus thresholds wrong | KI-NEW-P calibration suite filed at S10-T3 close; ≥3 beta merchants per stage = closure | Thresholds live in `config/gate_calibration.yaml` — change → re-fit → re-pin |
| T0 (lineage-keyed fatigue) breaks downstream consumer | Flag stays OFF; behavior change dormant | n/a — pure correctness, no behavior change in production |
| Fixture re-pin races atomic flip | Single commit pattern (S3 Risk #4) | Revert commit reverts both |
| Vocabulary stacking with `PriorValidationStatus` confuses consumers | DS Option A: different dataclasses + different casing + docstring cross-references | Re-read DS verdict `ds-architect-s10-vocab-stacking.md` |

---

## Part N — What not to touch yet

- `src/decide.py` — slate assembly, role-uniqueness, single-demote-channel invariant. **S10 has no DECIDE-layer change.**
- `src/main.py:1380-1597` — five V2 prior-anchored injection blocks. KI-NEW-L is S13.5.
- `src/sizing.py` `PSEUDO_N_BY_STATUS` table — locked through S14.
- `src/measurement_builder.py` — no MEASUREMENT-layer change in S10.
- `config/priors.yaml` — frozen.
- The 5 wired Tier-B builders (`winback_dormant_cohort`, `replenishment_due`, `discount_dependency_hygiene`, `cohort_journey_first_to_second`, `aov_lift_via_threshold_bundle`) — **no new builders through S13** per DS invariant 15.
- Renderer surface (`briefing.html`) — predictive_models never surfaced merchant-facing in S10 (operator-only).
- `KNOWN_ISSUES.md` — S10 plan does not edit pre-dispatch; KI-NEW-P filed at S10-T3 close. KI-NEW-Q/R deferred per founder.
- `memory.md` — entries only at sprint close, template-shape per CLAUDE.md rule.
- `PlayCard.predicted_segment` and `PlayCard.model_card_ref` stubs at `src/engine_run.py:814–815` — stay `None` at S10 close. S13 wires them.

---

## Part O — Summary of unclear / under-specified items (post-v2)

1. **Founder Q7 (§J.7) — M0 fixture re-pin on INSUFFICIENT_DATA.** Recommend emit-ModelCard-entry + re-pin M0. Decided at T1 design time.
2. **S10 → S11 forward-compat:** survival output (S11) reads BG/NBD parquet for `last_purchase_date`. The parquet schema version (T1.5 ships `parquet_schema_version=1`) needs to be set such that S11 additive columns don't break S10 readers.
3. **Whether the two MODEL_FIT_* ReasonCodes land at S10-T3 (dormant) or S13-T1 (with consumer).** Recommend S10-T3 to pin the audit invariant before consumer ships. Founder-accepted in DS verdict.
4. **KI-NEW-Q / KI-NEW-R deferral target sprint.** Founder-deferred at S10 close, no target named. Recommend revisiting at S14 close (post-beta).

---

## Sources

- `PRODUCT.md` (§2 merchant journey, §5 beta posture, §6 D-1..D-8, §8 non-goals)
- `STATE.md` (§1 pipeline, §4 three orthogonal gates, §5 invariants 5/6/7, §6 flags, §9 not-in-engine)
- `PIVOTS.md` (Pivot 7 single-demote-channel, Pivot 8 month-1-wow / month-2-return)
- `ROADMAP.md` (§1 S10 anchor goals, §2 beta-blocking sequence, §3 carry-forward, §4 deferrals, §5 non-goals). The active read path is PRODUCT/STATE/PIVOTS/ROADMAP; `ENGINE.md` is retired to `docs/legacy/`.
- `KNOWN_ISSUES.md` (KI-NEW-L S13.5, KI-NEW-M/N S14-T3, KI-1..KI-5 Phase 9, KI-NEW-C/G; KI-NEW-P filed at S10-T3 close)
- `agent_outputs/INDEX.md` (active sprint outputs section)
- `agent_outputs/ds-architect-s10-plan-review.md` (PASS-WITH-CHANGES; 9 required changes)
- `agent_outputs/ds-architect-s10-cold-start-and-eb-interaction.md` (four-state vocabulary; two ReasonCodes; RFM floor; month-2-return via EB)
- `agent_outputs/ds-architect-s10-vocab-stacking.md` (Option A — keep shared VALIDATED/PROVISIONAL labels, namespace-disambiguate)
- Inline DS verdict on business-config-keyed thresholds (relayed in dispatch brief 2026-05-25; extends `config/gate_calibration.yaml`)
- `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` (Part B §S10 ticket scaffolding, Part C Q1/Q2/Q5, Part D R1–R8, Part F beta checklist)
- `agent_outputs/beacon-ml-roadmap-reconciled-review.md` Addendum 2 L665–715 (parallel tracks + Swarm-as-loop-closer — **supersedes linear Phase 7→8→9 sequencing**; S10 sits on BEACON-TRACK substrate; SWARM track consumes S10 ModelCard schemas as frozen contracts), L395–456 (lineage_id schema, fatigue keying bug)
- `agent_outputs/play-lifecycle-discussion-reconciled.md` L47 ("correctness bug regardless of broader lifecycle scope")
- `agent_outputs/ecommerce-ds-architect-play-lifecycle-discussion.md` L109 (lineage primary key)
- `memory.md` S8 close entries (Q3/Q6/Q7 verdict — DS invariant 15: no new Tier-B builders through S13; KI-NEW-L anchored S13.5; KI-NEW-M/N anchored S14-T3)
- `config/gate_calibration.yaml` (existing schema — extended at T1 with `model_fit_thresholds` block per §C.4)
- `src/profile/builder.py::derive_gate_calibration` (lookup pattern precedent for stage-keyed cells)
- `src/profile/types.py:49–57` (`BusinessStage` enum)
- `src/sizing.py:87–139` (`PSEUDO_N_BY_STATUS` + `effective_pseudo_n` precedent for "profile lowers a per-status cap")
- `src/engine_run.py` L73 (`ReasonCode` enum, target for two new MODEL_FIT_* values), L106 (`COLD_START_INSUFFICIENT_DATA`, run-level, distinct from new per-play codes), L771 (`ModelCardRef`), L784 (`PlayCard`), L814–815 (stubs stay None at S10), L1191/L1197 (round-trip helpers)
- `src/memory/lineage.py:28-63` (existing `compute_lineage_id` helper — requires all 4 args)
- `src/guardrails.py:632` (fatigue keying bug callsite — `gate_recently_run` function body; v1's L604 reference was incorrect)
- `CLAUDE.md` Subagent Handoff Discipline (L27–46), Documentation Discipline section

*End of plan (v2).*
