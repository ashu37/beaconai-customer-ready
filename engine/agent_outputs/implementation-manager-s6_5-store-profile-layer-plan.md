# Sprint 6.5 — Store Profile Layer MVP: Implementation Manager Plan

**Owner:** implementation-manager
**Date:** 2026-05-17
**Branch target:** `post-6b-restructured-roadmap`
**Source contract:** `agent_outputs/ds-architect-store-profile-layer-proposal.md` (founder-accepted 2026-05-17)
**Predecessor sprint:** Sprint 6, ticket S6-T1.5 (winback flag flip; closeout 2026-05-17)
**Successor sprint:** Sprint 6, ticket S6-T2 (supplements parser) — **gated on S6.5 close**

---

## 1. Sprint S6.5 overview

### Anchor goal
Insert a typed `PROFILE` step at the head of the engine pipeline that descriptively classifies the store from its CSV and parameterizes every downstream gate (audience floors, materiality floors, primary/agreement windows, prior selection, seasonality annotations). Ship the typed `StoreProfile` dataclass, three new YAMLs (`subvertical_taxonomy.yaml`, `seasonality_calendars.yaml`, `gate_calibration.yaml`), and the deterministic derivation pipeline. Re-pin Beauty + supplements fixtures atomically with the flag flip. The synthetic Beauty fixture's 356-customer winback cohort — which failed the 500-floor under S6-T1.5 and routed to Considered with `AUDIENCE_TOO_SMALL` — is the test the activation moment must pass: under S6.5-T5, that cohort lands as Recommended Now with the Klaviyo `validated_external` prior finally exercised end-to-end.

### Why this sprint (the activation moment)
S7.5 installed the priors-validation contract and S6-T1.5 wired the first `validated_external` prior path on the winback card — but the synthetic Beauty fixture (356 customers, growth-stage skincare) sits below the hardcoded 500 floor and routes to Considered. The DS architect diagnosed this as a structural symptom: the engine is gating against an under-profiled store with mature-stage, single-vertical, fast-cycle floors hardcoded as constants. Without a profile layer, every Tier-B builder S6/S7 ships will re-encode those constants and we will unwind them in S8 anyway. S6.5 is the cheapest moment to fix the root cause: 5 Tier-B builders × hardcoded floors becomes 1 typed `StoreProfile.gate_calibration` table parameterized by detected stage + subvertical + cadence. It also unblocks the $1-3M growth-stage segment the founder validation cohort targets.

### Total duration estimate
**~7 working days** across 5 commit-shaped tickets (T1 + T2 + T3 + T4 + T5). Each ticket follows the team's three-commit ritual (impl + memory.md + summary doc). T4 is the load-bearing ticket and carries an explicit founder-review checkpoint before the YAML cells freeze.

### Beta-blocking status
**YES — beta-blocking.** External beta blocked until founder-validation on the gate_calibration.yaml starting cells AND on the Beauty/supplements atomic re-pin. Downstream sprints (S6-T2, S6-T3, S7) consume `profile.gate_calibration` / `profile.measurement.primary_window` / `profile.cadence` and cannot start ad hoc floor encoding. S6.5 is the structural unlock; until it lands, S6-T2 stays HELD.

### Schema additions table

| Field / type | Surface | Where | event_version |
|---|---|---|---|
| `StoreProfile` (frozen dataclass) | top-level `engine_run.store_profile` slot | `src/engine_run.py` + new `src/profile/types.py` | 1 (additive) |
| `Taxonomy(vertical, subvertical, subvertical_confidence, override_disagrees)` | sub-dataclass | same | 1 (additive) |
| `BusinessStage` enum `{STARTUP, GROWTH, MATURE, ENTERPRISE}` + `BusinessStageContext(detected, override_used, uncertainty)` | sub-dataclass + enum | same | 1 (additive) |
| `BusinessModel` enum `{ONE_TIME_LED, SUBSCRIPTION_LED, HYBRID}` | sub-dataclass | same | 1 (additive) |
| `CadenceBaseline(per_sku_class_median_days, method)` | sub-dataclass | same | 1 (additive) |
| `SeasonalityContext(active_window, expected_lift_direction, expected_lift_range, source_artifact)` | sub-dataclass | same | 1 (additive) |
| `DataDepth(history_days, n_customers, n_orders, n_repeat_customers, n_subscription_orders)` | sub-dataclass | same | 1 (additive) |
| `GateCalibration(audience_floor_by_play_id, materiality_floor_usd, primary_window, agreement_windows, pseudo_n_default)` | sub-dataclass | same | 1 (additive) |
| `MeasurementContext(primary_window, agreement_windows)` | sub-dataclass | same | 1 (additive) |
| `ProfileProvenance(detected_values, override_values, rules_fired, profile_built_at)` | sub-dataclass | same | 1 (additive) |
| `PlayCard.drivers[].profile_field_ref: Optional[str]` | new optional string on existing typed driver block | `src/engine_run.py` | 1 (additive) |

**All additions Optional / additive within `event_version=1` frozen contract** (Sprint 2 freeze carve-out for typed enum/field additions, precedent: S7.5-T1 / S6-T1).

### Feature flags table

| Flag | Default at introduction | Flipped ON in | Removal milestone |
|---|---|---|---|
| `ENGINE_V2_STORE_PROFILE` | OFF | S6.5-T5 (atomic with re-pin) | S8 Play Library fold (after beta with flag ON) |

No other flags introduced. Profile derivation runs unconditionally when ON; consumers read from `engine_run.store_profile` and fall back to today's hardcoded constants when `store_profile is None` (the flag-OFF branch). The fall-back path is the load-bearing structural-inertness guarantee at T1-T4.

### Fixture re-pin schedule

| Ticket | Beauty pinned slate | supplements G-1 | M0 small_sm/mid_shopify/micro_coldstart |
|---|---|---|---|
| S6.5-T1 | byte-identical | byte-identical | byte-identical |
| S6.5-T2 | byte-identical | byte-identical | byte-identical |
| S6.5-T3 | byte-identical | byte-identical | byte-identical |
| S6.5-T4 (founder-review checkpoint) | byte-identical (consumers wired but flag OFF) | byte-identical | byte-identical |
| **S6.5-T5 (atomic flag-flip)** | **re-pinned** — winback card promotes Considered → Recommended Now (floor drops 500 → 200 per growth/skincare cell); materiality floor drops $4500 → $2000; $ range non-suppressed | **re-pinned** — winback card stays in Considered but with `PRIOR_UNVALIDATED` reason (heuristic_unvalidated supplements prior unchanged); primary window moves L28 → L60 for any supplements directional card; `store_profile` slot populated with provenance | byte-identical (M0 fixtures hit STARTUP/data-depth-refused branches; floor changes do not surface new cards) |

### Behavior changes by ticket boundary

| After ticket | Behavior change? | What changed |
|---|---|---|
| S6.5-T1 | No | Profile dataclass + skeleton built; engine path unchanged (flag default OFF). |
| S6.5-T2 | No | Subvertical taxonomy + classifier ship behind flag OFF. |
| S6.5-T3 | No | Cadence + seasonality modules ship behind flag OFF. |
| S6.5-T4 (impl) | No | Gate calibration derivation wired; consumers read profile-or-fallback. **Founder review on YAML cell values before T5.** |
| S6.5-T5 | **YES** (intentional re-pin) | Flag default flips ON. Beauty winback activates Klaviyo validated_external prior at the Recommended Now lane. Supplements primary window per profile. Atomic re-pin in same commit (Sprint 2 Risk #4 discipline). |

---

## 2. Per-ticket plan

---

### S6.5-T1 — `StoreProfile` dataclass + dimension detection skeleton (impl, flag default OFF)

**Title:** Typed `StoreProfile` dataclass + skeleton detection for taxonomy / business_stage / business_model / data_depth; flag-gated (default OFF); zero behavior change.

**Scope (files touched):**
- New `src/profile/__init__.py` — exports `build_store_profile`, `StoreProfile`.
- New `src/profile/types.py` — `@dataclass(frozen=True)` for `StoreProfile`, `Taxonomy`, `BusinessStageContext`, `BusinessModel` (enum + context), `DataDepth`, `CadenceBaseline` (stub), `SeasonalityContext` (stub), `GateCalibration` (stub), `MeasurementContext` (stub), `ProfileProvenance`. All sub-dataclasses `frozen=True`. `to_dict` / `from_dict` round-trip helpers per the existing `engine_run.py` pattern.
- New `src/profile/builder.py` — `build_store_profile(aligned, csv_summary, cfg) -> StoreProfile`. Today implements:
  - `_detect_vertical(aligned, cfg)` — formalize today's `VERTICAL_MODE` env-var read; emit detected vertical + confidence score against keyword dictionary over product titles weighted by line-item revenue share. Override-vs-detected disagreement recorded in `Taxonomy.override_disagrees` typed flag.
  - `_detect_business_stage(aligned) -> BusinessStageContext` — annualized GMV from L90 × 4 (or L180 × 2 if available). Band: STARTUP <$500K, GROWTH $500K–$3M, MATURE $3M–$20M, ENTERPRISE >$20M. `BUSINESS_STAGE` env-var override wins; both detected + override recorded in provenance. Uncertainty `HIGH` when L90 falls within ±25% of band boundary.
  - `_detect_business_model(aligned) -> BusinessModel` — fraction of L180 orders from customers with ≥3 orders at σ/μ < 0.3 inter-order gap. >40% → SUBSCRIPTION_LED; <10% → ONE_TIME_LED; else HYBRID. MVP scope: detect-and-emit only; no behavior change in T1.
  - `_compute_data_depth(aligned) -> DataDepth` — history_days, n_customers, n_orders, n_repeat_customers, n_subscription_orders.
  - Subvertical token classifier scaffold (`_classify_subvertical`) returns `Taxonomy.subvertical = "mixed_<vertical>"` and confidence `REFUSED` today; T2 populates the token dictionary.
  - Cadence + seasonality + gate_calibration return stub instances (None-valued fields); T3 + T4 populate them.
- `src/engine_run.py` — additive `StoreProfile` slot on top-level `EngineRun`; `Optional[StoreProfile] = None`. `to_dict` / `from_dict` round-trip wired.
- `src/main.py` — when `cfg.get("ENGINE_V2_STORE_PROFILE", False)`, call `build_store_profile(...)` and attach to `EngineRun.store_profile`. When flag OFF, slot stays `None` (every existing fixture byte-identical).
- `src/utils.py` — register `ENGINE_V2_STORE_PROFILE` in `_BOOL_FLAGS` (default OFF). `BUSINESS_STAGE` + `VERTICAL_MODE` env vars stay as operator overrides; profile records both detected and override in provenance. No env var removed.
- `tests/test_s6_5_t1_store_profile_skeleton.py` — **new**. ~15 tests:
  1. Skeleton dataclass round-trip clean
  2. Beauty fixture detected vertical = beauty, confidence HIGH
  3. supplements fixture detected vertical = supplements, confidence HIGH
  4. `VERTICAL_MODE=apparel` still routes to B-7 ABSTAIN_HARD (vertical_guard before profile builder)
  5. Beauty L90 → annualized GMV → stage band (assert calibrated against the synthetic fixture's known GMV)
  6. `BUSINESS_STAGE=enterprise` override wins, both recorded in provenance
  7. Band-boundary uncertainty test: GMV near $3M boundary → `uncertainty=HIGH`, downstream consumer reads broader floor
  8. Business model detection on Beauty (one-time-led)
  9. Business model detection on a synthetic subscription fixture (mock)
  10. Data depth fields populate from fixture aligned
  11. Subvertical stub returns mixed_<vertical> with REFUSED confidence at T1
  12. Provenance carries every detected value + every override
  13. Flag OFF: every existing fixture sha256 byte-identical to S6-T1.5 close
  14. Flag ON + Beauty: `EngineRun.store_profile != None`, but Beauty fixture sha256 STILL byte-identical (cards consume profile only at T4; until then profile is dormant payload)
  15. `event_version=1` schema test still passes

**Acceptance criteria:**
- [ ] `StoreProfile` dataclass round-trips through `to_dict` / `from_dict` for Beauty + supplements + M0 fixtures.
- [ ] `engine_run.store_profile` is `None` when flag OFF on every existing fixture.
- [ ] Flag ON: profile is populated but every PlayCard / decision is byte-identical (consumers read from profile at T4 only).
- [ ] Vertical detection agrees with `VERTICAL_MODE` env var on Beauty + supplements fixtures (no `override_disagrees` warning).
- [ ] Stage detection on synthetic Beauty fixture produces GROWTH (founder-confirmed envelope).
- [ ] All 1267 + 15 = ~1282 tests pass (S6-T1.5 close baseline + 15 new).
- [ ] Beauty / supplements / M0 fixture sha256 byte-identical.

**Test deliverables:** `tests/test_s6_5_t1_store_profile_skeleton.py` (~15 tests). Aim for ~1282 total.

**Schema additions:** `StoreProfile` + 9 sub-dataclasses on `engine_run.py` (all Optional / frozen).

**Fixture re-pin:** **No.**

**Behavior change:** **No.**

**Dependencies:** S6-T1.5 closed (winback flag flip + atomic re-pin).

**Estimated duration:** ~2 days.

**Commit boundary (3 commits per S5/S7.5/S6 pattern):**
1. `S6.5-T1: StoreProfile dataclass + dimension detection skeleton + ENGINE_V2_STORE_PROFILE flag (default OFF)`
2. `Document S6.5-T1 in repo memory.md`
3. `S6.5-T1 summary` → `agent_outputs/code-refactor-engineer-s6_5-t1-summary.md`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s6_5-t1-summary.md`

**Hard-stops:** none (skeleton ticket; T5 owns hard-stop discipline).

---

### S6.5-T2 — Sub-vertical token classifier + `config/subvertical_taxonomy.yaml`

**Title:** Author the subvertical token dictionary + confidence-scored classifier; flag still default OFF.

**Scope (files touched):**
- New `config/subvertical_taxonomy.yaml` — **the load-bearing artifact for T2**. Token dictionary per (vertical, subvertical) populated from category-name vocabulary scraped from Sephora / iHerb / Amazon supplements taxonomy (founder Q1 below decides authoritative source). Subverticals:
  - `beauty`: skincare, cosmetics, haircare, personal_care, mixed_beauty
  - `supplements`: protein, multivitamin, probiotics, nootropics, functional, mixed_supplements
  - Each subvertical block carries `tokens: [list of canonical tokens]` + `negative_tokens: []` (anti-classification) + `notes` field documenting the source authority. Every entry tagged `validation_status: heuristic_unvalidated` mirroring priors discipline.
- `src/profile/builder.py::_classify_subvertical` — populate. Algorithm per DS architect §2.2:
  1. Tokenize product title (lowercase, strip punctuation, split on whitespace).
  2. For each SKU, score each subvertical = sum(token_matches) − sum(negative_token_matches).
  3. Tag SKU's subvertical = argmax (ties → `mixed_<vertical>`).
  4. Aggregate revenue-weighted argmax across SKUs.
  5. Confidence:
     - HIGH if leader has >3x runner-up by revenue share
     - MEDIUM if 2x–3x
     - LOW if 1.5x–2x
     - REFUSED otherwise → `mixed_<vertical>` (routes to KI-19 conservative-min prior downstream)
- `src/profile/taxonomy_loader.py` — YAML loader (mirrors `priors_loader.py` shape). Tolerant parser; unknown keys log + skip per the team's pattern.
- `tests/test_s6_5_t2_subvertical_classifier.py` — **new**. ~18 tests:
  1–6. Per-subvertical token-dictionary smoke (one positive SKU each)
  7. Negative-token suppression (e.g., a "hair vitamin" SKU is NOT classified as haircare)
  8. Revenue-weighted argmax (3 SKUs, 1 dominates by revenue)
  9. 2x gap → MEDIUM confidence
  10. 1.5x gap → LOW confidence
  11. Sub-2x gap → REFUSED → `mixed_<vertical>`
  12. Beauty fixture classifies as skincare with HIGH confidence (founder envelope)
  13. supplements fixture classifies as protein OR multivitamin OR mixed_supplements (envelope to be set per fixture audit; LOW or REFUSED also acceptable)
  14. Cross-category synthetic store (50/50 skincare + cosmetics) → `mixed_beauty` with LOW or REFUSED confidence
  15. YAML loader rejects unknown subvertical key
  16. YAML schema test pins exactly the 11 subverticals listed above
  17. Token dictionary case-insensitive match
  18. Flag OFF: every existing fixture sha256 byte-identical

**Acceptance criteria:**
- [ ] Beauty fixture classifies skincare HIGH on the synthetic fixture.
- [ ] supplements fixture classifies to a single subvertical with at least MEDIUM, OR routes to mixed_supplements (founder accepts either at T2 close; T4 will calibrate gate cells accordingly).
- [ ] All `subvertical_taxonomy.yaml` entries carry `validation_status: heuristic_unvalidated` and a `source_authority` field naming the scraped taxonomy.
- [ ] Beauty / supplements / M0 fixture sha256 byte-identical.

**Test deliverables:** `tests/test_s6_5_t2_subvertical_classifier.py` (~18 tests). Aim for ~1300 total.

**Schema additions:** none (subvertical already on `Taxonomy` from T1).

**Fixture re-pin:** **No.**

**Behavior change:** **No.**

**Dependencies:** S6.5-T1.

**Estimated duration:** ~1.5 days.

**Commit boundary:**
1. `S6.5-T2: subvertical token classifier + config/subvertical_taxonomy.yaml`
2. `Document S6.5-T2 in repo memory.md`
3. `S6.5-T2 summary` → `agent_outputs/code-refactor-engineer-s6_5-t2-summary.md`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s6_5-t2-summary.md`

**Hard-stops:** none.

---

### S6.5-T3 — Cadence baseline + seasonality calendar lookup

**Title:** Author `src/profile/cadence.py` + `src/profile/seasonality.py` + `config/seasonality_calendars.yaml`; flag still default OFF.

**Scope (files touched):**
- New `src/profile/cadence.py` — `compute_cadence_baseline(aligned, subvertical_sku_assignment) -> CadenceBaseline`. MVP uses **right-censored empirical median** per SKU class (pure-pandas; K-M deferred to S11). For each subvertical-tagged SKU class with ≥30 customers having ≥2 purchases of that class, compute inter-purchase gap empirical median. Censoring: customers with only 1 purchase in the SKU class do NOT contribute to the median (right-censored treatment placeholder; K-M will recover them in S11). Below `N=30` per class → `method=INSUFFICIENT_DATA`, baseline=None for that class.
- New `src/profile/seasonality.py` — `lookup_active_seasonality(run_date, vertical, subvertical) -> SeasonalityContext`. Reads `config/seasonality_calendars.yaml`. Returns `active_window_name` (or None), `expected_lift_direction` (+/-/none), `expected_lift_range` (range, never a point), `source_artifact` (path to the calendar memo).
- New `config/seasonality_calendars.yaml` — named windows per vertical:
  - BFCM_tail: 2026-11-20 → 2026-12-05 (both verticals)
  - January_resolution: 01-01 → 01-21 (supplements; minor for beauty)
  - Mothers_Day: 05-01 → 05-12 (beauty)
  - Back_to_school: 08-15 → 09-05 (mixed/personal_care)
  - Summer_skin: 06-01 → 08-01 (beauty/skincare)
  - Every window tagged `validation_status: heuristic_unvalidated`; lift ranges are observational benchmarks per Part III §8 discipline (annotations only, NEVER revenue multipliers).
- `src/profile/builder.py` — wire `compute_cadence_baseline` + `lookup_active_seasonality` into `build_store_profile`. Cadence + seasonality fields on `StoreProfile` now populate.
- `tests/test_s6_5_t3_cadence_seasonality.py` — **new**. ~14 tests:
  1. Cadence median computed on Beauty skincare class (founder envelope: 30–45 days)
  2. Cadence median computed on supplements protein class (envelope: 60–90 days)
  3. Below-N=30 class returns `INSUFFICIENT_DATA`
  4. Pure-pandas implementation has no `lifelines` import
  5. Seasonality lookup: 2026-11-25 + beauty/skincare → BFCM_tail active
  6. Seasonality lookup: 2026-05-05 + beauty → Mothers_Day active
  7. Seasonality lookup: 2026-07-15 + supplements → no active window
  8. Seasonality lookup: 2026-01-10 + supplements/multivitamin → January_resolution active
  9. `expected_lift_range` is always a range (never a point); test asserts `[low, high]` shape
  10. `source_artifact` resolves to file path under `config/priors_sources/` (or seasonality-equivalent dir)
  11. Seasonality NEVER produces a revenue multiplier (assert no float-multiplied field on profile)
  12. Flag OFF: every existing fixture sha256 byte-identical
  13. YAML schema pin: exactly 5 named windows above
  14. Calendar windows produce annotations only (no p-value adjustment)

**Acceptance criteria:**
- [ ] Beauty fixture: cadence median for skincare class is finite + inside [20, 60] days.
- [ ] supplements fixture: cadence median for primary supplements class is finite + inside [40, 120] days OR returns `INSUFFICIENT_DATA` (per fixture data).
- [ ] Today's date (2026-05-17) → Mothers_Day inactive (window already closed); no active seasonality.
- [ ] Seasonality calendar memo files exist under `config/priors_sources/seasonality/` or equivalent.
- [ ] Beauty / supplements / M0 fixture sha256 byte-identical.

**Test deliverables:** `tests/test_s6_5_t3_cadence_seasonality.py` (~14 tests). Aim for ~1314 total.

**Schema additions:** none (sub-dataclasses already on `StoreProfile` from T1; T3 populates them).

**Fixture re-pin:** **No.**

**Behavior change:** **No.**

**Dependencies:** S6.5-T2.

**Estimated duration:** ~1.5 days.

**Commit boundary:**
1. `S6.5-T3: cadence baseline + seasonality calendar lookup`
2. `Document S6.5-T3 in repo memory.md`
3. `S6.5-T3 summary` → `agent_outputs/code-refactor-engineer-s6_5-t3-summary.md`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s6_5-t3-summary.md`

**Hard-stops:** none.

---

### S6.5-T4 — Gate calibration + multi-window evidence (the load-bearing ticket) — founder-review checkpoint

**Title:** Author `config/gate_calibration.yaml` + deterministic `derive_gate_calibration()`; wire consumers (audience_builders, measurement_builder, decide, sizing) to read from profile; **ship R1 (window_corroboration) + R2 (cadence-derived primary window)** per DS architect multi-window memo (2026-05-18); flag still default OFF; **pause for founder approval before T5**.

**Multi-window evidence design (founder-approved 2026-05-18):**
- **R1 — `window_corroboration` as confidence modifier.** Primary window decides point estimate + p-value (unchanged). The two non-primary windows in `agreement_windows` produce a typed `PlayCard.measurement.window_corroboration` field with values `CORROBORATED | NEUTRAL | CONTRADICTED`. Trust engine reads it: CORROBORATED → confidence_label bumps one notch within its tier ceiling; CONTRADICTED → demote to Considered with new `WINDOW_DISAGREEMENT` ReasonCode; NEUTRAL → no change. Sign-only check (magnitude-ratio band deferred). Excludes primary from its own agreement check. **Closes the asymmetry:** today's directional pathway has `_sign_agreement_count`; the prior-anchored pathway does not. R1 brings prior-anchored to parity.
- **R2 — Cadence-derived primary window per cohort.** Replace the static `(vertical, subvertical) → primary_window` lookup with `primary_window = round_to_nearest({L28, L56, L90}, cadence.median_reorder_days_by_sku_class[class])`. Fallback to the static sketch table when cadence is INSUFFICIENT_DATA. **Gate OFF for SUBSCRIPTION_LED stores** (DS architect risk #4: subscription cadence is contractual, not behavioral; sub-led keeps static table read). Provenance records `cadence_derived_primary_window` (or `subscription_led_static_window`) rule fire.
- **L42 4th window — DEFERRED.** Founder decision (2026-05-18): ship T4 with `{L28, L56, L90}` only. Document 35–48d cadence as a known quantization gap; revisit after one real beta store. The synthetic supplements fixture's 38–40d cluster is acknowledged as a known calibration target, not blocking.

**Scope (files touched):**
- New `config/gate_calibration.yaml` — **the load-bearing artifact**. Per DS architect §2.8 sketch:
  - `audience_floors:` per (play_id, vertical, subvertical, stage) cell. Starting cells per the architecture proposal sketch (winback_dormant_cohort beauty/skincare × {startup:80, growth:200, mature:500, enterprise:1500}, etc.) plus full coverage across all 14 plays × {beauty, supplements} × {5 beauty subverticals + 5 supplements subverticals} × 4 stages. Every cell tagged `validation_status: heuristic_unvalidated`.
  - `materiality_floors_usd:` per stage (startup:$800, growth:$2000, mature:$4500, enterprise:$12000). Per architecture proposal.
  - `primary_window:` per (vertical, subvertical) — **fallback only**, consulted when cadence is INSUFFICIENT_DATA. Sketch (beauty/skincare→L28; beauty/cosmetics→L28; beauty/haircare→L56; supplements/protein→L60; supplements/multivitamin→L60; supplements/nootropics→L90) becomes the fallback, NOT the primary path. R2 makes cadence-derived the primary path.
  - `agreement_windows:` per (vertical, subvertical) — the two non-primary windows in `{L28, L56, L90}`. R1 consumes this.
  - `pseudo_n_default:` per stage (cold-start blend weight defaults; reuses S7.5 `PSEUDO_N_BY_STATUS` semantics).
- `src/profile/builder.py::derive_gate_calibration(taxonomy, stage, cadence, data_depth, business_model) -> GateCalibration` — pure function, same inputs → same outputs. Auditable. Falls back to broader cell when `stage.uncertainty=HIGH` (DS architect §2.3). Cell-not-found returns conservative architecture-default constants and records `rules_fired += ["gate_calibration_cell_missing"]` in provenance. **R2:** when `business_model != SUBSCRIPTION_LED` AND cadence is populated for the relevant SKU class, `primary_window` is derived from cadence (round-to-nearest of {L28, L56, L90}); else falls back to the static `gate_calibration.yaml` cell. `agreement_windows` is always `{L28, L56, L90} \ primary_window`.
- `src/audience_builders.py` — `winback_dormant_cohort_candidates` (and any other Tier-B audience builder shipped to date) reads floor from `profile.gate_calibration.audience_floor_by_play_id[<play_id>]` when `cfg["ENGINE_V2_STORE_PROFILE"]` is ON; falls back to hardcoded `AUDIENCE_FLOOR_DEFAULT_500` when OFF or when profile is None. Both paths exercised in tests.
- `src/measurement_builder.py` — `_SUPPORTED` consumers read `primary_window` from `profile.measurement.primary_window` when ON; fall back to current per-play hardcoded primary window when OFF. **R1 wiring:** both `build_directional_play_card` and `build_prior_anchored_play_card` now emit `window_corroboration` on the returned `PlayCard.measurement`. Directional pathway's existing `_sign_agreement_count` is the basis; prior-anchored pathway gets a parallel implementation that reads cohort behavior on each agreement window and applies sign-only check. `CORROBORATED` requires both non-primary windows to show same-sign delta as primary at p<0.10 each; `CONTRADICTED` requires ≥1 non-primary window to show opposite-sign delta at p<0.10; else `NEUTRAL`.
- `src/decide.py` — materiality floor reads from `profile.gate_calibration.materiality_floor_usd` when ON; falls back to today's `_MATERIALITY_FLOOR_BY_TIER` constants when OFF. **R1 wiring:** `window_corroboration == "CORROBORATED"` bumps confidence_label one notch within its tier ceiling (Emerging → Trustworthy where trust-tier permits; never crosses tier boundaries). `window_corroboration == "CONTRADICTED"` routes the card to Considered with new ReasonCode `WINDOW_DISAGREEMENT`. `NEUTRAL` is a no-op. **New ReasonCode** `WINDOW_DISAGREEMENT` lands in the `ReasonCode` enum + the considered-card copy template.
- `src/sizing.py` — `pseudo_n` default reads from `profile.gate_calibration.pseudo_n_default[stage]` when ON; falls back to `PSEUDO_N_BY_STATUS` when OFF. **Note:** validated-vs-heuristic refusal logic (S7.5-T3) is unchanged; profile only parameterizes the cold-start weight inside the validated path.
- `tests/test_s6_5_t4_gate_calibration.py` — **new**. ~28 tests (was ~20; R1+R2 add ~8):
  1. `derive_gate_calibration` is a pure function (same inputs → same outputs across 100 runs)
  2. Beauty/growth/skincare cell present + matches sketch table
  3. Supplements/mature/protein cell present + matches sketch table
  4. Cell-not-found returns conservative default + records provenance rule fire
  5. Stage-uncertainty HIGH → broader (more conservative) floor used
  6. Subvertical REFUSED → mixed_<vertical> cell consulted
  7. Audience builder reads floor from profile when ON (Beauty 356-customer cohort → would-pass at growth/skincare floor 200)
  8. Audience builder reads hardcoded 500 when OFF (today's behavior preserved)
  9. **R2:** Beauty/skincare with cadence=53d → primary_window=L56 (not L28; cadence-derived overrides sketch) + provenance fires `cadence_derived_primary_window`
  10. **R2:** Supplements/protein with cadence=40d → primary_window=L28 (round-to-nearest), supplements/nootropics with cadence=75d → L90
  11. **R2:** Cadence INSUFFICIENT_DATA → falls back to gate_calibration.yaml static cell + provenance fires `cadence_fallback_static_window`
  12. **R2:** SUBSCRIPTION_LED business_model → always reads static cell, NEVER cadence-derived; provenance fires `subscription_led_static_window`
  13. Measurement builder falls back to today's window when flag OFF
  14. Decide layer reads materiality floor from profile
  15. Sizing reads pseudo_n_default from profile
  16. **R1:** `window_corroboration` field present on `PlayCard.measurement` for both directional + prior-anchored pathways
  17. **R1:** `CORROBORATED` when both non-primary windows same-sign at p<0.10 → confidence_label bumps one notch within tier ceiling
  18. **R1:** `CONTRADICTED` when ≥1 non-primary window opposite-sign at p<0.10 → card routes to Considered with `WINDOW_DISAGREEMENT` ReasonCode
  19. **R1:** `NEUTRAL` (low data on agreement windows, mixed signs, or no significant deltas) → no behavior change
  20. **R1:** `agreement_windows` excludes primary from its own agreement check (`{L28, L56, L90} \ primary`)
  21. **R1:** `WINDOW_DISAGREEMENT` ReasonCode in enum + considered-card copy template exists
  22. **R1:** Prior-anchored pathway parity — `build_prior_anchored_play_card` emits `window_corroboration` (closes the directional/prior-anchored asymmetry)
  23. **R1:** Confidence bump from CORROBORATED never crosses tier boundary (Tier C cannot promote to Tier B)
  24. All gate_calibration.yaml cells carry `validation_status: heuristic_unvalidated`
  25. Every cell has 4-tuple stage coverage (no missing-stage rows)
  26. YAML schema validation: 14 plays × 10 subverticals × 4 stages cells present OR documented gap
  27. Flag OFF: every existing fixture sha256 byte-identical (R1 + R2 + all consumers dormant)
  28. Flag ON on Beauty fixture (T5 dry-run, NOT committed): cadence-derived primary_window flips skincare from L28 → L56; card-count delta to be documented in T4 summary
  29. `PlayCard.drivers[].profile_field_ref` cites `gate_calibration.audience_floors.winback_dormant_cohort.beauty.skincare.growth` (or equivalent path)
  30. Provenance carries every consumed profile field
  31. `event_version=1` schema test still passes
  32. L42 deferred: assert window set is exactly `{L28, L56, L90}` in gate_calibration.yaml schema (pins the deferred-L42 decision)

**Acceptance criteria:**
- [ ] `derive_gate_calibration` is deterministic (pure-function test).
- [ ] Every consumer (audience_builders, measurement_builder, decide, sizing) has both flag-ON and flag-OFF paths tested.
- [ ] All cells tagged `heuristic_unvalidated`.
- [ ] Beauty / supplements / M0 fixture sha256 byte-identical under flag OFF.
- [ ] **R2:** Beauty/skincare cadence-derived primary_window = L56 (not the static L28 sketch); subscription-led short-circuit verified.
- [ ] **R1:** `window_corroboration` populated on both directional + prior-anchored pathways; CORROBORATED/CONTRADICTED/NEUTRAL all reachable; `WINDOW_DISAGREEMENT` ReasonCode lives in the enum + considered-card copy template.
- [ ] **Founder review checkpoint hit:** before T5 begins, paste the gate_calibration.yaml curated ~40-cell table + the projected per-fixture card delta + the R2 cadence-derived window probe (Beauty/skincare 53d → L56; supplements probe) into `agent_outputs/code-refactor-engineer-s6_5-t4-summary.md` and PAUSE.

**Test deliverables:** `tests/test_s6_5_t4_gate_calibration.py` (~28 tests). Aim for ~1350 total.

**Schema additions** (all additive within `event_version=1`):
- `PlayCard.drivers[].profile_field_ref: Optional[str]`
- `PlayCard.measurement.window_corroboration: Optional[Literal["CORROBORATED", "NEUTRAL", "CONTRADICTED"]]`
- `ReasonCode.WINDOW_DISAGREEMENT` (new enum value)

**Fixture re-pin:** **No** (flag OFF; consumers are wired but dormant on every fixture).

**Behavior change:** **No** (until T5 flips the flag).

**Dependencies:** S6.5-T3.

**Estimated duration:** ~3 days (was ~2; R1 + R2 add ~1 day — gate_calibration.yaml authoring + 4 consumer wirings + R1 prior-anchored parity + R2 cadence rounding logic + ~8 extra tests + ReasonCode wiring).

**Commit boundary:**
1. `S6.5-T4: gate_calibration.yaml + derive_gate_calibration + consumer wiring + R1 window_corroboration + R2 cadence-derived primary window (flag default OFF)`
2. `Document S6.5-T4 in repo memory.md`
3. `S6.5-T4 summary + founder-review checkpoint`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s6_5-t4-summary.md`

**Hard-stops at T4:** none on impl (flag OFF). Founder review is the gating action between T4 and T5; T5 does NOT auto-start.

**Founder-review checkpoint contents (T4 summary doc):**
1. Curated ~40-cell gate_calibration.yaml table (founder Q4: not full ~560-cell table).
2. **R2 cadence-derived primary window probe:** Beauty/skincare 53d → L56 (was L28 sketch); supplements G-1 per-class cadence-derived window readout (38–40d cluster expected to land on L28 with the quantization gap acknowledged).
3. **R1 `window_corroboration` distribution probe:** under flag-ON, per pinned fixture, how many cards land CORROBORATED vs NEUTRAL vs CONTRADICTED (illustrative — not a behavior gate at T4 since flag is OFF).
4. Per-fixture projected card-count delta under flag-ON (Beauty: skincare window changes L28→L56 may shift card count; supplements: possibly window changes on existing cards).
5. Cell-by-cell sanity-check of the architecture proposal sketch numbers (founder Q4).
6. Subscription-led prioritization decision confirmation (founder Q5 — slate-ordering deferred to S6-T3; R2 short-circuit is the only S6.5 behavior).
7. L42 deferral pin: assert window set is `{L28, L56, L90}`; document 35–48d quantization gap.
8. STOP pending orchestrator approval.

---

### S6.5-T5 — Atomic flag flip + Beauty + supplements fixture re-pin (closes Sprint 6.5)

**Title:** Flip `ENGINE_V2_STORE_PROFILE` default OFF → ON; atomic Beauty + supplements G-1 re-pin in the SAME commit (Sprint 2 Risk #4 discipline).

**Scope (files touched):**
- `src/utils.py` — flip `ENGINE_V2_STORE_PROFILE` default to `True` in `_BOOL_FLAGS`.
- `tests/test_slate_regression_beauty_brand.py` — update pinned sha256 constant from S6-T1.5 close value (`<S6_T1_5_BEAUTY_SHA>`) to new sha. Diff scope: +1 Recommended Now card for `winback_dormant_cohort` on Beauty (audience 356, growth/skincare floor 200, materiality $2000, validated_external Klaviyo prior → non-suppressed BLEND range).
- `tests/test_slate_regression_supplements_brand.py` — update pinned sha256 constant from `01f5feff84...` / `feb03500c1...` (whichever is current at S6-T1.5 close) to new sha. Diff scope: `store_profile` slot populated; primary window on any supplements directional card moves L28 → L60; any new Considered routing follows.
- `tests/test_s6_5_t5_atomic_repin.py` — **new**. ~12 tests:
  1. Beauty new sha256 pin
  2. supplements G-1 new sha256 pin
  3. M0 goldens byte-identical (M0 fixtures hit STARTUP / data-depth-refused branches; no surface change)
  4. Beauty winback card's posterior numerics match `bayesian_blend(prior_value=0.08, pseudo_n=30, store_value=<observed>, n_observed=356)`
  5. Beauty winback card's `drivers[].profile_field_ref` cites `gate_calibration.audience_floors.winback_dormant_cohort.beauty.skincare.growth`
  6. supplements engine_run.store_profile is populated with full provenance
  7. supplements primary_window on any new directional card = L60
  8. Beauty `store_profile.business_stage.detected = GROWTH`
  9. Beauty `store_profile.taxonomy.subvertical = "skincare"` with HIGH confidence
  10. Beauty `store_profile.gate_calibration.audience_floor_by_play_id["winback_dormant_cohort"] = 200`
  11. Beauty `store_profile.gate_calibration.materiality_floor_usd = 2000`
  12. Operator override: `VERTICAL_MODE=supplements` on Beauty fixture → `Taxonomy.override_disagrees = True` AND override wins (provenance records both)

**Acceptance criteria (hard-stop discipline ACTIVE):**
- [ ] Beauty pinned slate sha256 updates from `<current>` to a new pinned constant.
- [ ] Beauty winback card lands in Recommended Now (NOT Considered) — the activation moment.
- [ ] supplements G-1 sha256 updates from `<current>` to a new pinned constant.
- [ ] supplements winback card stays in Considered with `PRIOR_UNVALIDATED` (heuristic_unvalidated supplements prior unchanged).
- [ ] M0 goldens byte-identical (sanity check: profile activation does NOT touch the legacy `ENGINE_V2_SIZING=false` path).
- [ ] Beauty's winback `revenue_range.p50` is inside the Klaviyo prior's `[range_p10, range_p90]` envelope.
- [ ] No M-invariant regression.

**Hard-stops (per founder Q4 pattern from S6-T1.5):** STOP and ping orchestrator if:
1. Profile detection produces nonsense (e.g., Beauty fixture detects as supplements).
2. Gate calibration produces an empty slate on Beauty (where one was expected).
3. Beauty's `business_stage.detected != GROWTH` (envelope check).
4. Beauty's `subvertical != "skincare"` with confidence < HIGH.
5. supplements winback card lands in Recommended Now (validation gate broken — heuristic_unvalidated prior should still suppress).
6. M0 goldens shift unexpectedly (legacy path should be unreachable from profile wiring).
7. Subscription-led / one-time-led detection produces a result that contradicts the fixture's known purchase patterns.
8. Any cell-lookup miss triggers default-fallback on Beauty/supplements (envelope is full-coverage at known fixtures).

**Test deliverables:** `tests/test_s6_5_t5_atomic_repin.py` (~12 tests). Aim for ~1346 total.

**Schema additions:** none (T1–T4 already shipped them).

**Fixture re-pin:** **YES** — Beauty + supplements G-1 atomically in the SAME commit (Sprint 2 Risk #4 discipline; same pattern as S-3 closeout, S7.5-T3.5, S6-T1.5).

**Behavior change:** **YES**.

**Dependencies:** S6.5-T4 + **founder approval on T4 review checkpoint**.

**Estimated duration:** ~1 day.

**Commit boundary:**
1. Atomic commit: `S6.5-T5: flip ENGINE_V2_STORE_PROFILE ON + atomic Beauty + supplements re-pin (closes Sprint 6.5)`. Single commit covers `src/utils.py` flag flip + both regression test sha pins + new T5 test file.
2. `Document S6.5-T5 in repo memory.md`
3. `S6.5-T5 summary` → `agent_outputs/code-refactor-engineer-s6_5-t5-summary.md`

**Summary doc filename:** `agent_outputs/code-refactor-engineer-s6_5-t5-summary.md`

---

## 3. Risk register for S6.5

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| R-1 | **Sub-vertical misclassification on cross-category stores.** A real "skincare + cosmetics + haircare" store labeled as skincare gets the wrong primary_window and floor table cell. | Medium | DS architect's `mixed_<vertical>` fallback with REFUSED confidence + KI-19 conservative-min priors. T2's confidence-scoring test pins LOW/REFUSED behavior. T5's hard-stop catches Beauty fixture misclassification. |
| R-2 | **Cell sparsity in `gate_calibration.yaml`.** With 14 plays × 11 subverticals × 4 stages = 616 cells. Many starting cells unstable / unvalidated. | High | Every cell tagged `heuristic_unvalidated`. T4 derive function falls back to conservative-default constants when a cell is missing AND records provenance rule fire (so missing cells are auditable, not silent). Cell-by-cell validation deferred to outcome-driven recalibration post-Phase 9 (S10+). |
| R-3 | **Backward-compat regression on `BUSINESS_STAGE` / `VERTICAL_MODE` env vars.** Founder or beta operator sets env override; profile silently ignores OR overwrites detected value without recording. | Medium | T1's tests pin both detected + override paths. `Taxonomy.override_disagrees` typed flag + `ProfileProvenance` records both values. S-1.7 lessons-learned applied (no silent laundering). |
| R-4 | **The synthetic Beauty fixture STILL doesn't activate after profile lands.** T5 flips the flag and the winback card stays in Considered — the structural fix doesn't work. | Medium | T5 hard-stop discipline: STOP and ping orchestrator on activation-moment failure. The 356-customer cohort at growth/skincare floor=200 is the founder envelope; if it fails, root-cause before re-pinning. Possible causes (debug order): (a) profile detects wrong stage → fix detection; (b) gate cell missing → author cell; (c) decide.py reads wrong field path → fix wiring. |
| R-5 | **Seasonality calendar maintenance burden over time.** Hardcoded BFCM 2026-11-20 dates need annual refresh; if forgotten, profile silently emits stale annotations. | Low (now) / Medium (year-2) | T3's seasonality calendar uses month-day pattern (no year) where possible. Where year-anchored (BFCM), YAML carries an explicit `valid_for_year` field and the loader logs a warning when `run_date.year > valid_for_year + 1`. Annual maintenance lands as a year-end KI ticket. |
| R-6 | **Profile becomes a single point of failure.** A bug in stage detection breaks every gate, on every play, on every fixture. | Medium | Profile derivation is pinned in T1 tests across all 5 fixtures. Provenance makes the failure inspectable in `engine_run.json`. Operator overrides (`BUSINESS_STAGE` / `VERTICAL_MODE`) remain the safety valve. Flag-OFF rollback is one-line. |
| R-7 | **Audit complexity — every recommendation now cites profile fields.** Reviewers need to trace `PlayCard.drivers[].profile_field_ref` → `gate_calibration.yaml` cell → derivation rule. | Low (acceptable cost) | `ProfileProvenance.rules_fired` is the audit trail. Summary doc in T5 demonstrates one end-to-end trace for the Beauty winback card. Document the trace template in `docs/profile_audit_walkthrough.md` (optional, defer to S9 if T5 ships under deadline). |

---

## 4. KIs touched / closed

| KI | Status going into S6.5 | S6.5 interaction | Status exiting S6.5 |
|---|---|---|---|
| KI-18 (`empty_bottle.vertical_applicable` excludes supplements) | accepted (HELD by S6-T2 supplements parser, gated on S6.5) | S6.5 does NOT touch the supplements parser. KI-18 stays HELD; S6-T2 unblocks immediately after S6.5-T5 close and reads `profile.taxonomy.subvertical` for SKU-class assignment. | accepted (unchanged; ETA closes inside S6-T2 post-S6.5) |
| KI-19 (`mixed` vertical semantics) | tracked / partially resolved by G-3 `resolve_mixed_prior` | T2 routes LOW/REFUSED confidence to `mixed_<vertical>` which already triggers KI-19 conservative-min priors. KI-19's contract is now exercised end-to-end on every cross-category store. | tracked (contract exercised; no formal close in S6.5) |
| KI-27 (`empty_bottle` clean-skipped on supplements) | accepted | S6.5 does NOT touch KI-27. Stays gated on S6-T2 post-S6.5. | accepted (unchanged; ETA closes inside S6-T2 post-S6.5 IF parser coverage sufficient) |
| KI-29 (campaign-aggregate feedback loop) | tracked (Year-2 enhancement) | Untouched. | tracked. |
| KI-30 (per-play evidence visualization spec) | tracked | Untouched (Part III-3 stop-coding line still applies). | tracked. |
| KI-31 (cap-trim Considered list visibility) — IF FILED | tracked (potentially) | S6.5 does NOT touch Considered cap logic. Profile parameterizes floors, not slate caps. | unchanged. |
| New: per-vertical floor metadata fragmentation | partially in `routine_builder.metadata.audience_floor_by_vertical` (config/priors.yaml line 426) | T4 consolidates ALL per-vertical floor logic into `gate_calibration.yaml`. `routine_builder.metadata.audience_floor_by_vertical` becomes the second source-of-truth for floors — file a KI ("dual-source floor authority pending S8 fold") and document that `gate_calibration.yaml` wins when both are set. | new KI filed; resolution deferred to S8 Play Library refactor. |

---

## 5. What S6.5 does NOT do

- **No K-M cadence fitting** — `lifelines` is not added as a dependency. Cadence baseline uses right-censored empirical median pure-pandas. K-M with Cox PH covariates lands in S11.
- **No STL seasonality decomposition** — calendar lookup only. Store-specific seasonality fitting deferred post-beta.
- **No embedding-based sub-vertical clustering** — token classifier only. Embedding clustering deferred post-beta.
- **No ML-driven stage detection** — GMV banding only. LTV-aware stage detection deferred post-beta.
- **No outcome-driven cell-by-cell floor recalibration** — every cell is `heuristic_unvalidated`. Outcome-driven calibration loop lands in S10 (Phase 9 outcome importer).
- **No new Tier-B builders** — those are S6-T2 / S6-T3 / S7 (held until S6.5 close).
- **No new priors** — `replenishment_due.base_rate` ships in S6-T3 (not S6.5).
- **No renderer / HTML work** — Part III-3 engine-only-JSON scope still applies. The renderer / "Confidence chip" / "Emerging — Small Store" copy referenced in the DS architect §3 examples is downstream Swarm consumer work, NOT engine scope.
- **No Shopify / Klaviyo network calls** — D-5 still binding.
- **No removal of `BUSINESS_STAGE` / `VERTICAL_MODE` env vars** — both stay as operator overrides.

---

## 6. Open questions for the founder

| # | Question | Sensible default if no answer |
|---|---|---|
| Q1 | **Token-dictionary authoritative source.** For `subvertical_taxonomy.yaml`, which taxonomies are authoritative for token-list construction? Options: (a) Sephora's product categories for beauty + iHerb's for supplements; (b) Amazon's beauty + supplements category trees; (c) DS architect's curated list (no external authority). | (a) Sephora + iHerb. Cite each YAML entry's `source_authority` with the scraped URL. |
| Q2 | **Stage band ±25% boundary uncertainty.** Accept the DS architect's `uncertainty=HIGH` rule (broader/more-conservative floor used downstream) for stores within ±25% of a band boundary? | Yes, accept. The conservative-broader rule is the safe default. |
| Q3 | **Seasonality window dates.** Accept the DS architect's calendar (BFCM 11/20–12/05; January_resolution 1/1–1/21; Mothers_Day 5/1–5/12; Back_to_school 8/15–9/05; Summer_skin 6/1–8/1) verbatim, or override per vertical? | Accept verbatim for T3; revisit annually as a KI. |
| Q4 | **Gate calibration starting floor values — review cell-by-cell before flag flip.** T4 founder-review checkpoint pauses pending your sign-off on the floor table. Will you review the full ~616-cell table, or a curated subset (Beauty/skincare/growth + supplements/protein/mature + a few others)? | Curated subset of ~20 high-leverage cells (Beauty/skincare × all stages, supplements/protein × all stages, plus `mixed_<vertical>` rows). Defer full-table review to S8 Play Library fold. |
| Q5 | **Subscription-led prioritization of `replenishment_due` over `winback_dormant_cohort`.** Accept this single behavior change in S6.5 (per DS architect §2.4), or defer to S6-T3 / S7? | **Defer to S6-T3.** S6.5's MVP detects business_model and emits the label, but the slate-ordering behavior change ships when `replenishment_due` lands. Keeps S6.5's behavior surface to ONE flip (T5). |

---

## 7. Beta-launch checklist update

S6.5 adds the following items to the beta-launch checklist:

- [ ] `engine_run.json` carries a non-null `store_profile` slot on every successful run (B-7 ABSTAIN_HARD runs may omit; document).
- [ ] `store_profile.provenance` cites every detected value and every operator override (no silent overrides).
- [ ] `store_profile.taxonomy.subvertical` is HIGH or MEDIUM confidence on at least one beta merchant per vertical (calibration sanity check; LOW/REFUSED is acceptable but flagged in beta intake).
- [ ] `store_profile.business_stage.detected` is consistent with the beta merchant's self-reported stage on intake (envelope check; significant disagreement → manual review before launch).
- [ ] `gate_calibration.yaml` cells consumed by any beta merchant's run have been founder-reviewed (curated subset per Q4).
- [ ] `seasonality_calendars.yaml` annotations on beta runs do NOT multiply into any `revenue_range.p50` (test pin per T3 #11).
- [ ] `subvertical_taxonomy.yaml` source_authority fields populated for every entry.
- [ ] Operator-override path (`BUSINESS_STAGE=<x>` and `VERTICAL_MODE=<x>`) tested end-to-end on at least one beta merchant.
- [ ] Beauty + supplements pinned-slate re-pin documented in S6.5-T5 summary with full per-fixture before/after card-count deltas.
- [ ] M0 goldens byte-identical at S6.5-T5 close (legacy path unreachable from profile wiring).
