# Store Profile Layer — Architectural Proposal

**Author:** ecommerce-ds-architect
**Date:** 2026-05-17
**Status:** Under founder review — pre-S6.5 decision

**Verdict:** Build it. As a new Sprint 6.5, before S6-T2 (supplements parser) and before any further Tier-B builders ship. The founder's instinct is correct: today's engine dives into math against an under-profiled store, and the gates fail in the wrong direction (false ABSTAINs on healthy $1-3M stores, not false POSITIVES). Every Tier-B builder we ship without a Profile Layer hardcodes another set of "mature, single-vertical, fast-cycle" assumptions that we will have to unwind in S8 anyway. The cost of the MVP profile is ~1 sprint (5-7 working days); the cost of NOT building it now is that S6-T2, S6-T3, and S7's three builders each re-litigate floors/windows/seasonality in their own ad hoc way.

This proposal defines a typed `StoreProfile` step that runs first in the pipeline, produces a single audited artifact, and parameterizes every downstream gate. Crucially: it is a profile, not a predictor. It descriptively classifies the store from its CSV; it does not forecast. That keeps it cheap, defensible, and outside the ML predictive layer (Sprints 10-13).

---

## 1. Architectural shape

### Where it lives

```
  PROFILE   →   AUDIENCE   →   MEASUREMENT   →   SIZING   →   DECIDE
  (NEW)         (existing)     (existing)        (existing)   (existing)
```

`PROFILE` runs once per engine_run, before any candidate detection. Its output is a typed `StoreProfile` dataclass persisted on `engine_run.json` under a top-level `store_profile` slot (additive, `event_version=1`-safe).

Every downstream system reads from `StoreProfile` instead of from env vars or hardcoded constants:

| Downstream consumer | Reads from profile |
|---|---|
| Audience floors | `profile.gate_calibration.audience_floor_by_play_id` |
| Materiality floors | `profile.gate_calibration.materiality_floor_usd` |
| Primary measurement window | `profile.measurement.primary_window` |
| Multi-window agreement set | `profile.measurement.agreement_windows` |
| Seasonality discounts/annotations | `profile.seasonality.active_context` |
| Prior selection (sub-vertical) | `profile.taxonomy.subvertical` |
| Bayesian blend `pseudo_n` | `profile.calibration.pseudo_n_default` |
| ModelFitStatus thresholds (S10+) | `profile.data_depth.model_fit_thresholds` |

### Schema sketch

```python
@dataclass(frozen=True)
class StoreProfile:
    store_id: str
    profile_version: int
    profiled_at: datetime

    taxonomy: Taxonomy                   # vertical + subvertical + confidence
    business_stage: BusinessStage        # STARTUP|GROWTH|MATURE|ENTERPRISE
    business_model: BusinessModel        # ONE_TIME_LED|SUBSCRIPTION_LED|HYBRID

    cadence: CadenceBaseline             # per-SKU-class median reorder gap
    seasonality: SeasonalityContext      # active window + calendar entries
    data_depth: DataDepth                # history_days, n_customers, n_orders

    gate_calibration: GateCalibration    # all per-(vertical, subvertical, stage) floors
    measurement: MeasurementContext      # primary_window + agreement_windows

    provenance: ProfileProvenance        # which rules fired, with what inputs
```

The dataclass is frozen + provenance-bearing. Every recommendation downstream cites the profile fields it consumed in its `drivers[]` block.

---

## 2. The dimensions

### 2.1 Vertical detection (KEEP existing, formalize)

- Today: `VERTICAL_MODE` env var; operator-asserted.
- Profile-MVP: keep env-var override as authoritative, but compute a detected vertical from product title heuristics + a confidence score. If operator override disagrees with detected vertical at HIGH confidence, emit a typed `vertical_override_disagrees` warning on the profile.
- Technique: keyword dictionary over product titles weighted by line-item revenue share. >70% revenue-weighted match = HIGH confidence.

### 2.2 Sub-vertical detection (NEW)

- Within beauty: {skincare, cosmetics, haircare, personal_care, mixed_beauty}
- Within supplements: {protein, multivitamin, probiotics, nootropics, functional, mixed_supplements}
- Technique (MVP): revenue-weighted token classifier over product titles. Token dictionary lives in `config/subvertical_taxonomy.yaml`. Classify a SKU as belonging to a subvertical iff its title matches that subvertical's tokens AND not its rivals'. Subvertical = revenue-weighted argmax with second-largest gap check (if leader has <2x revenue share over runner-up, label as `mixed_<vertical>`).
- Confidence: HIGH if leader has >3x runner-up; MEDIUM if 2x-3x; LOW or REFUSED otherwise → routes to `mixed_<vertical>` and downstream gets the conservative (broader) prior.
- Cost: ~150 LOC + a YAML taxonomy.

### 2.3 Business stage (auto-detect, replacing env var)

- Today: `BUSINESS_STAGE` env var was removed in V2; floors hardcoded at MATURE.
- Profile-MVP: annualized GMV computed from L90 (or L180 if available) orders × 4 (or 2). Bands:
  - STARTUP: <$500K annualized
  - GROWTH: $500K – $3M
  - MATURE: $3M – $20M
  - ENTERPRISE: >$20M
- Caveat: profile emits `business_stage_uncertainty: HIGH` when L90 falls within ±25% of a band boundary; downstream uses broader (more conservative) floor.
- Operator override: `BUSINESS_STAGE` env var still wins; both detected + override recorded in provenance.

### 2.4 Business model (NEW)

- One-time-led | subscription-led | hybrid.
- Technique: fraction of L180 orders that come from customers with ≥3 orders at near-constant inter-order gap (σ/μ < 0.3). If >40% → subscription-led; <10% → one-time-led; else hybrid.
- MVP scope: detect and emit the label; defer behavior changes to S7 except for one: subscription-led stores get `replenishment_due` prioritized over `winback_dormant_cohort` in the slate.

### 2.5 Cycle baseline (per-SKU-class reorder gap)

- Technique (MVP): Kaplan-Meier median residual life per SKU class. For each subvertical-tagged SKU class with ≥30 customers having ≥2 purchases of that class, fit a K-M curve over inter-purchase gaps. Use `lifelines.KaplanMeierFitter` if available; pure-pandas empirical median otherwise.
- MVP simplification: if `lifelines` is not yet a dependency at S6.5, ship right-censored empirical median as a stopgap. Replace with K-M during S11 (`lifelines` arrives anyway).

### 2.6 Seasonality exposure (NEW)

- The MVP claim: "in this calendar window, this vertical historically experiences a demand shift; the engine should annotate, NOT discount."
- Technique (MVP):
  1. `config/seasonality_calendars.yaml` with named windows per vertical: BFCM (both), January_resolution (supplements), Mothers_Day (beauty), Back_to_school (mixed/personal_care), Summer_skin (beauty/skincare).
  2. At profile time, compute whether `run_date` falls inside any active window.
  3. Emit `seasonality.active_context = SeasonalityContext(window_name, vertical_expected_lift_direction, vertical_expected_lift_magnitude_range, source_artifact)`. The magnitude is a range, not a point, and never multiplies into revenue ranges.
- What it does NOT do (MVP): STL decomposition, year-over-year regression, store-specific seasonality fitting. Deferred to post-beta.
- The trap to avoid: treating "BFCM lifts CTR by 30%" as a causal lift. It is an observational benchmark on confounded marketing performance. The Market Research Integration discipline applies.

### 2.7 Data depth (NEW, cheap)

- `history_days`, `n_customers`, `n_orders`, `n_repeat_customers`, `n_subscription_orders`.
- Why: K-M fits, BG/NBD fits, RFM bands, retention curves (S10-S12) all have minimum data thresholds. The profile is where those checks live.

### 2.8 Gate calibration (the integration layer)

This is the load-bearing block. It is a deterministic function of the other dimensions:

```python
def derive_gate_calibration(taxonomy, stage, cadence, data_depth) -> GateCalibration:
    """Pure function. Same inputs → same outputs. Auditable."""
    audience_floor_by_play_id = lookup_floor_table(
        play_id_set=ALL_PLAYS,
        vertical=taxonomy.vertical,
        subvertical=taxonomy.subvertical,
        stage=stage,
    )
    materiality_floor_usd = STAGE_TO_MATERIALITY_FLOOR[stage] * subvertical_aov_scaler(taxonomy)
    primary_window = subvertical_primary_window(taxonomy, cadence)
    agreement_windows = subvertical_agreement_windows(taxonomy, cadence, data_depth)
    return GateCalibration(...)
```

**Concrete floor table sketch (`config/gate_calibration.yaml`):**

```yaml
audience_floors:
  winback_dormant_cohort:
    beauty:
      skincare:    { startup: 80,  growth: 200, mature: 500, enterprise: 1500 }
      cosmetics:   { startup: 100, growth: 250, mature: 600, enterprise: 1800 }
    supplements:
      protein:     { startup: 120, growth: 300, mature: 700, enterprise: 2000 }
      multivitamin:{ startup: 100, growth: 250, mature: 600, enterprise: 1800 }
materiality_floors_usd:
  startup: 800
  growth:  2000
  mature:  4500
  enterprise: 12000
primary_window:
  beauty:
    skincare:    L28
    cosmetics:   L28
    haircare:    L56
  supplements:
    protein:     L60
    multivitamin: L60
    nootropics:  L90
agreement_windows:
  beauty:
    skincare:    [L28, L56, L90]
  supplements:
    protein:     [L56, L90, L180]
    nootropics:  [L90, L180]
```

These numbers are starting heuristics, not validated. They should be tagged `heuristic_unvalidated` in the YAML and routed through the same `validation_status` discipline the priors system uses.

---

## 3. How the profile parameterizes the engine

Concrete behavioral examples (assuming MVP profile lands):

- **Synthetic Beauty fixture (356 customers, growth stage, skincare):** floor drops from 500 → 200. Card lands in Recommended Now with materiality_floor=$2000 instead of $4500. Solves the failure mode that triggered this proposal.
- **Mature supplements protein store (1,500 repeat customers):** primary window = L60 (not L28); agreement windows = {L56, L90, L180}; floor = 700. Signal that L28 was "noisy" is no longer a question — L28 is no longer the primary window.
- **Startup beauty haircare (180 customers, $200K GMV):** floor = 80; materiality_floor = $800. Engine can recommend; previously would have ABSTAIN'd. Confidence chip downgraded to "Emerging — Small Store" so merchants understand the caveat.
- **Mid-Dec run on a beauty/skincare store:** profile emits `seasonality.active_context.window_name = "BFCM_tail"`. Every PlayCard whose primary window ends in late November/early December gets a `seasonality_caveat` driver. ABSTAINs cite seasonal confound. Engine does NOT silently multiply revenue ranges by 1.3x.
- **Mixed-vertical store:** subvertical = `mixed_<vertical>` with LOW confidence → priors layer's KI-19 conservative-min rule continues to apply → suppressed revenue ranges. Profile doesn't fix the mixed problem; it just makes the routing explicit.

---

## 4. Implementation cost (honest)

**MVP profile (Sprint 6.5):**

- `src/profile/builder.py` — ~400 LOC (taxonomy, stage, business_model, data_depth, gate_calibration derivation).
- `src/profile/seasonality.py` — ~150 LOC (calendar lookup, active-window detection).
- `src/profile/cadence.py` — ~120 LOC (right-censored empirical median or K-M wrapper).
- `src/engine_run.py` — +60 LOC (StoreProfile dataclass + round-trip).
- `config/subvertical_taxonomy.yaml` — new, ~150 lines.
- `config/seasonality_calendars.yaml` — new, ~80 lines.
- `config/gate_calibration.yaml` — new, ~200 lines (the central table).
- `src/audience_builders.py`, `src/measurement_builder.py`, `src/decide.py` — ~200 LOC of replacements (read from profile instead of constants).
- Tests — ~60 new tests covering profile derivation, profile→gate routing, fixture re-pin under each profile shape.

**Total: ~1,400 LOC + 3 YAMLs + ~60 tests. Engineer-weeks: ~1 sprint (5-7 working days) for a focused engineer.**

This fits in a single sprint if scoped tightly to MVP. The full vision (embedding-based subvertical, store-specific seasonality fits, K-M with covariates, ML-driven stage detection) is multi-sprint and post-beta.

---

## 5. Risks & tradeoffs

- **Misclassification of subvertical.** Failure mode: cross-category store gets labeled "skincare" and gets the wrong floor/window. Mitigation: the `mixed_<vertical>` fallback with conservative-min priors already exists (KI-19).
- **Cell sparsity.** With 2 verticals × 4-6 subverticals × 4 stages × N plays = a lot of cells. Many will have unstable starting floors. Mitigation: every cell is a `heuristic_unvalidated` config value, and we don't pretend otherwise.
- **Audit complexity.** Every recommendation now cites the profile that drove its gates. Acceptable cost.
- **Backward compat with `VERTICAL_MODE` / `BUSINESS_STAGE` env vars.** Both stay as operator overrides with provenance recording both detected and override values. No breaking change.
- **Beta-launch implications.** S6.5 inserts one sprint; downstream sprints get easier because each Tier-B builder now consumes profile values instead of hardcoding floors. Net: maybe +0.5 sprint to total beta timeline, possibly net-zero.
- **Subtle one:** the profile becomes the single point of failure. A bug in stage detection breaks every gate. Mitigation: pin the profile derivation in tests; provenance makes it inspectable; operator override is the safety valve.

---

## 6. Where this fits in the sprint plan

**Recommendation: insert as S6.5, immediately after S6-T1.5 (winback flag flip) and before S6-T2 (supplements parser).**

Rationale:
- S6-T1 winback already needs the profile (it's the play that surfaced the problem; 356 < 500 floor).
- S6-T2 (supplements unit-coherence parser) builds the SKU class taxonomy that the cadence dimension depends on.
- S6-T3 (`replenishment_due`) is the play most dependent on cadence-aware primary windows.
- S7 ships three more Tier-B builders. Each one would re-encode floors/windows ad hoc.

| Sprint | Status |
|---|---|
| S6-T1, T1.5 | Done / in-flight |
| **S6.5 (NEW)** | **Store Profile Layer MVP** — 1 sprint, ~5-7 days |
| S6-T2 | supplements parser — now consumes `profile.taxonomy.subvertical` |
| S6-T3 | `replenishment_due` — now consumes `profile.measurement.primary_window` + `profile.cadence` |
| S7 | three Tier-B builders — each consumes profile.gate_calibration |
| S8 | tier formalization + EB blend + Play Library — Play Library refactor folds each play's profile dependencies into its folder |
| S10-S13 | ML predictive layer — `ModelFitStatus` thresholds read from `profile.data_depth` |

**Do NOT subsume into S8 Play Library refactor.** That would couple two structural changes and risks bundling. Profile first, then Library refactor cleanly imports profile contracts.

---

## 7. MVP vs Full vision

**MVP (S6.5, beta-blocking):**
- Vertical detection (formalize existing)
- Subvertical: token classifier with revenue-weighted argmax + 2x gap check
- Stage: L90×4 annualized GMV banded with operator override
- Business model: detected, emitted, but only `replenishment_due` priority change in MVP
- Cadence: right-censored empirical median per SKU class (defer K-M to S11)
- Seasonality: calendar lookup with annotation-only (no p-value adjustments, no revenue multipliers)
- Data depth: history_days, n_customers, n_orders
- Gate calibration: deterministic derivation; YAML-driven; all cells `heuristic_unvalidated`
- Profile dataclass on engine_run.json with full provenance

**Full vision (post-beta):**
- Embedding-based subvertical clustering
- Store-specific STL seasonality decomposition
- K-M with Cox PH covariates for cadence (lands organically in S11)
- ML-driven stage detection (LTV-aware, not just GMV)
- Profile calibration loop: outcome data → cell-by-cell floor recalibration (post Phase 9)
- Per-merchant seasonality calendars (learned from ≥2 years of history)

---

## 8. On market research / benchmarks

The seasonality magnitudes and the Klaviyo / Shopify benchmarks already in `priors.yaml` are observational averages from marketing-performance reporting, not causal lift. The profile must treat them the same way the priors validation discipline does: every seasonality magnitude is `heuristic_unvalidated` until we can cite a defensible source artifact; observational benchmarks become calibration ranges for sanity-checking the engine's revenue outputs, not direct inputs to revenue math.

- Use benchmarks as priors for Bayesian blending (already the discipline)
- Use them as range constraints for catching engine outputs that are wildly off
- Do NOT use them as causal lift multipliers on revenue ranges
- Do NOT use seasonality magnitudes to bump cohort signals

---

## Final architectural recommendation

Build the Store Profile Layer as Sprint 6.5, between S6-T1.5 and S6-T2. Scope it to the MVP defined above. Ship the typed `StoreProfile` dataclass, the three YAMLs (subvertical taxonomy, seasonality calendars, gate calibration), and the deterministic derivation pipeline. Re-pin the Beauty + supplements fixtures atomically with the flag flip. Defer K-M, embeddings, STL, and store-specific seasonality to post-beta.

**Answer to the founder's L28/L56-vs-L90 question:** Confirmed and refined. L28/L56 is fine for beauty/skincare and beauty/cosmetics (median reorder gap 30-45 days). For supplements, L28 is structurally too short — most supplements subverticals have 60-90 day reorder cadence, so L28 captures partial cohorts of high-frequency customers and misses the bulk of the replenishment signal. The correct fix is NOT "add L90 everywhere" but "let the profile pick primary + agreement windows per subvertical": beauty/skincare stays {L28, L56, L90}; supplements/protein moves to L60 primary with {L56, L90, L180} agreement; supplements/nootropics moves to L90 primary with {L90, L180} agreement (and accepts that data-depth REFUSAL is more common). The window choice is a downstream consequence of cadence detection, not a config knob; once the profile exists, it falls out for free.
