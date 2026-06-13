# S6.5-T4 — Gate calibration + R1 window_corroboration + R2 cadence-derived primary window

**Owner:** code-refactor-engineer (Sprint 6.5, ticket T4)
**Date:** 2026-05-18
**Branch:** `post-6b-restructured-roadmap` (not pushed)
**Source contract:** [agent_outputs/implementation-manager-s6_5-store-profile-layer-plan.md](./implementation-manager-s6_5-store-profile-layer-plan.md) §S6.5-T4 (post-49e90d5)
**Predecessors:** [T1](./code-refactor-engineer-s6_5-t1-summary.md), [T2](./code-refactor-engineer-s6_5-t2-summary.md), [T3](./code-refactor-engineer-s6_5-t3-summary.md)
**Status:** Complete. Flag `ENGINE_V2_STORE_PROFILE` still default OFF. All 5 pinned fixtures byte-identical under flag OFF. **STOP for founder review on the curated ~40-cell table + R1/R2 probes below before T5 begins.**

---

## 1. Approved scope

The load-bearing ticket of Sprint 6.5. Three coupled features land in a single 3-commit handoff:

- **`config/gate_calibration.yaml`** — load-bearing artifact carrying per-(play, vertical, subvertical, stage) `audience_floors`, per-stage `materiality_floors_usd`, per-(vertical, subvertical) `primary_window` (FALLBACK ONLY — R2 makes cadence-derived the primary path), per-(vertical, subvertical) `agreement_windows`, per-stage `pseudo_n_default`. Window set pinned to `{L28, L56, L90}` (L42 deferred).
- **`derive_gate_calibration(taxonomy, stage, cadence, data_depth, business_model)`** — pure function (test: 100 runs identical). DS architect §2.3 stage-uncertainty broader-cell fallback. REFUSED subvertical → `mixed_<vertical>` row. Cell-not-found → conservative architecture-default + `gate_calibration_cell_missing` provenance fire. R2 primary_window derivation (cadence-derived for non-SUBSCRIPTION_LED stores with COMPUTED cadence for the subvertical; static fallback otherwise).
- **R1 + R2 multi-window evidence wiring across all 4 consumers** under `ENGINE_V2_STORE_PROFILE` flag (default OFF; T5 owns the atomic flip):
  - `src/audience_builders.py::winback_dormant_cohort_candidates` — floor reads from `profile.gate_calibration.audience_floor_by_play_id["winback_dormant_cohort"]`.
  - `src/measurement_builder.py::build_directional_play_card` + `build_prior_anchored_play_card` — primary_window + agreement_windows from `profile.measurement`; R1 `window_corroboration` emitted on both pathways (closes the DS architect §1 directional/prior-anchored asymmetry).
  - `src/guardrails.py::gate_materiality` (called from `apply_guardrails`) — materiality floor from `profile.gate_calibration.materiality_floor_usd`; fallback `scale_aware_materiality_floor(monthly_revenue)`.
  - `src/decide.py` — new `_route_window_disagreement_holds` (CONTRADICTED → Considered with `WINDOW_DISAGREEMENT`); new `_apply_window_corroboration_bumps` (CORROBORATED bumps Emerging → Strong within MEASURED/DIRECTIONAL tier ceiling).
  - `src/sizing.py::effective_pseudo_n` — validated-path cold-start weight = `min(PSEUDO_N_BY_STATUS[status], profile.gate_calibration.pseudo_n_default)`. Profile can only LOWER the weight; S7.5-T3 refusal logic unchanged for heuristic_unvalidated / placeholder.

## 2. Schema additions (all additive within `event_version=1`)

- `ReasonCode.WINDOW_DISAGREEMENT` — new enum value with considered-card + would-fire-if copy templates.
- `WindowCorroboration` — new typed enum: `CORROBORATED | NEUTRAL | CONTRADICTED`.
- `PlayCard.measurement.window_corroboration: Optional[WindowCorroboration] = None` — defaults to `None` under flag OFF; populated by both directional + prior-anchored pathways under flag ON. Round-trips via `_coerce_enum` in `_from_dict_measurement`.
- `PlayCard.drivers[].profile_field_ref: Optional[str]` — additive driver-dict key cited on `audience_size` and `blend_provenance` drivers when the floor / pseudo_n came from profile. Pre-T4 dict shape preserved (key absent → byte-identical).
- `StoreProfile.gate_calibration.pseudo_n_default: Optional[int]`, `StoreProfile.gate_calibration.profile_field_refs: Dict[str, str]` — new fields on the T1 `GateCalibration` sub-dataclass.
- `StoreProfile.measurement.primary_window_source: str` — new field on the T1 `MeasurementContext` sub-dataclass (`"cadence_derived" | "subscription_led_static" | "cadence_fallback_static" | "default"`).
- Pre-T4 payloads round-trip cleanly: all new fields have safe defaults.

## 3. R1 — window_corroboration (multi-window evidence)

`src/measurement_builder.py::_window_corroboration_sign_only` — sign-only check at MVP (magnitude-ratio band deferred). p < 0.10 looser than directional gate p < 0.05 because R1 is a CORROBORATION read, not a gating-criterion read.

Rules:
- **CORROBORATED**: every non-primary window in `agreement_windows` shows same-sign delta as primary at p < 0.10. Confidence bumps Emerging → Strong on MEASURED/DIRECTIONAL cards; Targeting never bumps; Strong stays Strong.
- **CONTRADICTED**: ≥1 non-primary window shows opposite-sign delta at p < 0.10. Card routes to Considered with `WINDOW_DISAGREEMENT` + merchant-readable copy ("Different time windows of your data disagree on this trend — we'd want one more month of data before recommending.").
- **NEUTRAL**: low data on agreement windows, mixed signs, or no significant deltas. No behavior change.

Prior-anchored parity via `_prior_anchored_window_corroboration`: at S6.5 MVP, `reactivation_rate` is not typically present in `aligned[window]` per window, so the helper degrades to `NEUTRAL` (pins field-presence parity with directional WITHOUT fabricating a per-window signal). The closure of the DS architect §1 asymmetry is in the field being PRESENT on the prior-anchored card's measurement, not in the value computed today; the helper structure supports a per-window cohort recomputation in S11 when outcome history is available.

## 4. R2 — cadence-derived primary window

`derive_gate_calibration` round-to-nearest of `{L28, L56, L90}` using `_round_cadence_to_window(median_days)`:
- 28 → L28; 42 → L28 (equidistant; earlier-init wins);
- 43 → L56; 72 → L56; 73 → L56 (equidistant); 74 → L90; 90 → L90.

Routing:
- `business_model == SUBSCRIPTION_LED` → static YAML cell ALWAYS (DS architect risk #4: subscription cadence is contractual, not behavioral). Provenance: `subscription_led_static_window`.
- COMPUTED cadence with per-class median for the resolved subvertical → cadence-derived. Provenance: `cadence_derived_primary_window`.
- Otherwise → static YAML cell. Provenance: `cadence_fallback_static_window`.

`agreement_windows` is always `{L28, L56, L90} \ primary_window` (R1 invariant).

## 5. Tests

New: `tests/test_s6_5_t4_gate_calibration.py` (39 tests; the 32-item IM plan list verbatim plus 7 belt-and-suspenders extras).

Coverage:
- **derive_gate_calibration** pure function pin (100 runs identical).
- **Stage-uncertainty HIGH** → broader cell consulted; provenance fires.
- **Subvertical REFUSED** → `mixed_<vertical>` row consulted; provenance fires.
- **Cell-not-found** → conservative default + provenance fire.
- **R2** — Beauty/skincare 53d → L56 + `cadence_derived` source; Supplements/protein 40d → L28; Supplements/nootropics 75d → L90; INSUFFICIENT_DATA → static fallback; SUBSCRIPTION_LED → static short-circuit.
- **Round-to-nearest** boundary table (28 / 42 / 43 / 72 / 73 / 74 / 90).
- **Audience builder** — flag ON reads profile floor (Beauty pinned cohort=428 passes growth/skincare floor 200); flag OFF rejects under hardcoded 500.
- **Measurement (directional)** — flag OFF emits `window_corroboration=None`; flag ON emits a typed value.
- **R1** — CORROBORATED bumps confidence (Emerging → Strong); CONTRADICTED routes to Considered; NEUTRAL no-op; agreement_windows excludes primary; Targeting never bumps; Strong stays Strong; prior-anchored helper returns NEUTRAL when metric absent.
- **gate_materiality** — profile floor override under flag ON; scale-aware fallback under flag OFF.
- **effective_pseudo_n** — profile lowers VALIDATED_EXTERNAL from 30 → 20 under flag ON; flag OFF preserves cap; profile never raises above status cap (ELICITED_EXPERT cap 10 stays 10).
- **YAML schema** — `heuristic_unvalidated` tag; 4-stage coverage on winback_dormant_cohort × every populated subvertical + mixed; winback fully populated, other plays via `_default_by_stage`.
- **WINDOW_DISAGREEMENT** ReasonCode + copy templates + would-fire-if templates exist; merchant-facing phrase "disagree" pinned.
- **PlayCard.drivers[].profile_field_ref** cites `gate_calibration.audience_floors.winback_dormant_cohort.beauty.skincare.growth` on the canonical Beauty growth/skincare profile.
- **event_version=1** round-trip: `window_corroboration` survives `EngineRun.to_dict()` → `EngineRun.from_dict()` with `_coerce_enum`.
- **L42 deferred** — YAML `windows_pinned` is exactly `{L28, L56, L90}`; `_GATE_CALIBRATION_WINDOWS` constant matches.
- **Flag-OFF byte-identity** — local schema-defaults test; broader pinned-fixture sha256 invariants verified across the existing `tests/test_slate_regression_*` and `tests/test_s6_t1_5_*` suites (18 tests, 65s).

## 6. Founder Review — ~40 cells + R1/R2 probes (per founder Q4 + 2026-05-18 multi-window decision)

### 6.1 Curated gate_calibration.yaml cells

**audience_floors.winback_dormant_cohort (full table — the only Tier-B builder shipped through S6-T1.5)**

| Cell | startup | growth | mature | enterprise |
|---|---:|---:|---:|---:|
| beauty/skincare | 80 | 200 | 500 | 1500 |
| beauty/cosmetics | 80 | 200 | 500 | 1500 |
| beauty/haircare | 80 | 200 | 500 | 1500 |
| beauty/personal_care | 80 | 200 | 500 | 1500 |
| mixed_beauty (REFUSED subv fallback) | 120 | 300 | 700 | 2000 |
| supplements/protein | 60 | 150 | 400 | 1200 |
| supplements/multivitamin | 60 | 150 | 400 | 1200 |
| supplements/probiotics | 60 | 150 | 400 | 1200 |
| supplements/nootropics | 60 | 150 | 400 | 1200 |
| supplements/functional | 60 | 150 | 400 | 1200 |
| mixed_supplements (REFUSED subv fallback) | 100 | 250 | 600 | 1500 |

**audience_floors._default_by_stage** (consumed by all 13 other plays via the `_default` cell):

| stage | startup | growth | mature | enterprise |
|---|---:|---:|---:|---:|
| default | 50 | 150 | 400 | 1200 |

**materiality_floors_usd** (per stage, replaces `scale_aware_materiality_floor` under flag-ON):

| stage | startup | growth | mature | enterprise |
|---|---:|---:|---:|---:|
| $ floor | 800 | 2000 | 4500 | 12000 |

**primary_window** (FALLBACK ONLY — R2 makes cadence-derived the primary path; consulted when subscription-led OR cadence INSUFFICIENT_DATA):

| vertical | skincare | cosmetics | haircare | personal_care | protein | multivitamin | probiotics | nootropics | functional |
|---|---|---|---|---|---|---|---|---|---|
| beauty | L28 | L28 | L56 | L28 | — | — | — | — | — |
| supplements | — | — | — | — | L56 | L56 | L56 | L90 | L56 |

**pseudo_n_default** (per stage; cold-start blend weight cap, only LOWERS the validated-path PSEUDO_N_BY_STATUS):

| stage | startup | growth | mature | enterprise |
|---|---:|---:|---:|---:|
| pseudo_n | 10 | 20 | 30 | 50 |

Every cell carries `validation_status: heuristic_unvalidated`. Cell-by-cell calibration deferred to S10+ outcome-driven recalibration loop (Phase 9 outcome importer).

### 6.2 R2 cadence-derived primary window probe (per fixture)

| Fixture | detected stage | business_model | cadence (median) | primary_window | source | agreement_windows |
|---|---|---|---|---|---|---|
| Beauty pinned (`healthy_beauty_240d_orders.csv`, `VERTICAL_MODE=beauty`) | GROWTH (LOW) | ONE_TIME_LED (sub_frac=0.07) | skincare:53d | **L56** | **cadence_derived** | [L28, L90] |
| Supplements G-1 (`healthy_supplements_240d_orders.csv`, `VERTICAL_MODE=supplements`) | STARTUP (HIGH uncertainty, detected=GROWTH) | SUBSCRIPTION_LED (sub_frac=0.97) | functional:38, multivitamin:39, probiotics:40, protein:40 | **L56** | **subscription_led_static** | [L28, L90] |

**R2 founder envelope checks PASS:**
- Beauty/skincare cadence 53d → L56 (NOT the static L28 sketch). The primary_window has flipped on the founder anchor case.
- SUBSCRIPTION_LED short-circuit verified on Supplements G-1 (cadence median 38–40d would have rounded to L28 under cadence-derived, but `subscription_led_static_window` provenance fires and the static cell L56 wins).

**35–48d quantization gap acknowledged:** Supplements G-1's per-class medians (38–40d) sit in the 35–48d gap between L28 and L56. With L42 deferred, these land on L28 if cadence-derived path fires (39 is closer to 28 than 56: 39-28=11 vs 56-39=17). Since the fixture is SUBSCRIPTION_LED, the gap is not exercised today on this fixture; if a future one-time-led supplements store has 38–40d cadence, it will round to L28 — a known calibration target.

### 6.3 R1 window_corroboration distribution probe (illustrative; flag OFF in production)

R1 fires only under flag ON. The illustrative probe is structural rather than fixture-data-driven because the synthetic fixtures' aligned snapshots do not exhibit cross-window sign disagreement on the wired directional metric (`returning_customer_share`). The 39-test suite covers all three states with synthetic aligned input:

- **CORROBORATED** path (synthetic): all 3 windows same-sign + p<0.10 → confidence bumps Emerging→Strong.
- **CONTRADICTED** path (synthetic): primary L28 vs. L56 sign disagree at p<0.10 → Considered with `WINDOW_DISAGREEMENT`.
- **NEUTRAL** path (default on synthetic fixtures today): no agreement-window has confident sign data → no behavior change.

On the pinned Beauty + supplements fixtures under flag-ON dry-run: every R1 outcome is NEUTRAL (the aligned snapshots are too consistent for CONTRADICTED, and the synthetic data does not exhibit cross-window p<0.10 confidence on agreement windows for the metric beyond primary). The R1 mechanism is wired and tested; live-data CORROBORATED / CONTRADICTED rates will only materialize against a real beta store's signal mix.

### 6.4 Per-fixture projected card-count delta under flag-ON (T5 dry-run, NOT committed)

| Fixture | Today's behavior (flag OFF) | Projected flag-ON behavior | Delta |
|---|---|---|---|
| Beauty pinned slate | winback_dormant_cohort cohort=428 < floor=500 → Considered (`audience_too_small`) | cohort=428 ≥ profile floor=200 (beauty/skincare/growth cell) → **Recommended Now** (prior-anchored, Klaviyo validated_external) | **+1 Recommended Now** |
| Supplements G-1 | winback cohort below floor → already in Considered | profile floor=60 (supplements/functional/startup); cohort still below floor (synthetic data has small dormant pool); primary_window L28 → L56 on any directional supplements card if one fires | window changes on existing supplements cards; cohort still below floor; **NO new Recommended Now** (still PRIOR_UNVALIDATED on supplements winback per S7.5-T3) |
| M0 small_sm / mid_shopify / micro_coldstart | legacy `ENGINE_V2_SIZING=false` path; `engine_run.store_profile=None` | profile activation does NOT touch the legacy path (M0 fixtures stay on `engine_run.store_profile=None`) | **0 change** |

### 6.5 L42 deferral pin

`config/gate_calibration.yaml::windows_pinned = [L28, L56, L90]`. `src.profile.builder._GATE_CALIBRATION_WINDOWS = ("L28", "L56", "L90")`. Test #32 enforces the set is exactly three windows.

**Known calibration target:** the 35–48d cadence gap (no window between L28 and L56) — affects supplements/protein, supplements/multivitamin, supplements/probiotics on stores with 35–48d cadence. Deferred to post-beta per founder 2026-05-18.

### 6.6 Subscription-led prioritization confirmation (founder Q5)

Slate-ordering by subscription-led status is **deferred to S6-T3 per founder Q5**. T4's only S6.5 behavior involving SUBSCRIPTION_LED is the R2 short-circuit to static primary_window (DS architect risk #4: subscription cadence is contractual, not behavioral, so cadence-derived window would mis-attribute). No slate ordering change in S6.5.

### 6.7 STOP pending orchestrator approval

T5 does **NOT** auto-start. Founder approval on the ~40-cell table + R1/R2 probes above is the gate. If founder approves, T5 will:
1. Flip `ENGINE_V2_STORE_PROFILE` default OFF → ON in `src/utils.py`.
2. Atomically re-pin Beauty + supplements G-1 fixture sha256 constants (Sprint 2 Risk #4 discipline).
3. Author `tests/test_s6_5_t5_atomic_repin.py` (~12 tests) with the hard-stop sanity checks.

If founder requests cell-value changes (e.g. winback floor 200 → 150 for beauty/growth/skincare): the change lands in T4 (this commit chain) before T5 begins, NOT inside T5.

## 7. Hard constraints respected

- D-5 / D-6 / D-8 intact (no Shopify/Klaviyo, no banned ML modules, vertical scope unchanged).
- B-4 role-uniqueness intact (no slate edits at T4; consumers are wired but flag default OFF).
- B-5 Berkson invariant intact (profile is descriptive; R1 is per-window sign-only, not cross-period cohort comparison).
- S-2..S-6 substrate write paths untouched.
- Schema-additive only within `event_version=1` (3 schema additions listed in §2; all defaults preserve pre-T4 round-trip).
- No new runtime dependencies.
- S7.5-T3 validated-vs-heuristic refusal logic UNCHANGED: `effective_pseudo_n` only parameterizes the cold-start weight INSIDE the validated path; heuristic_unvalidated / placeholder still refuse outright.

## 8. Commit list

1. `S6.5-T4: gate_calibration.yaml + derive_gate_calibration + consumer wiring + R1 window_corroboration + R2 cadence-derived primary window (flag default OFF)`
2. `Document S6.5-T4 in repo memory.md`
3. (this commit) — `S6.5-T4 summary + founder-review checkpoint`

## Backfill from memory.md (migration trim 2026-05-25)

## Sprint 6.5 Ticket T4.y.1 closeout (2026-05-18)

**Status:** Complete. Atomic two-part fix per founder direction. ONE
commit covers (a) `.env` leak deletion (gitignored, so local-only;
documented in commit body), (b) symmetric band-check provenance fix.

**Commit:** `28410fe S6.5-T4.y.1: remove stale VERTICAL_MODE=beauty
from .env + fix conservative-broader band-check on lower side of
boundary`

**File (visible in diff):** `src/profile/builder.py` (15+/8- lines in
`detect_business_stage`).

**Behavior fix:**
- Part A (`.env`): removed `VERTICAL_MODE=beauty` from `.env` line 32
  (gitignored; local-filesystem change). Beauty detector verified to
  return `vertical=beauty (HIGH)` from data alone. Supplements detector
  returns `vertical=supplements (HIGH), subvertical=functional (LOW),
  business_model=SUBSCRIPTION_LED (sub_fraction=0.97 HIGH)`.
- Part B (`detect_business_stage`): `stage_boundary_uncertainty`
  provenance rule now fires whenever `uncertainty=HIGH` (within ±25%
  of ANY boundary), regardless of direction. Previously only fired
  when the broader-stage downgrade was available — at the STARTUP
  floor (e.g. supplements G-1 at $496K) the rule was silently absent.
  `conservative_floor_applied` remains a SEPARATE flag, True only
  when a downgrade applies (`False` at STARTUP floor). Both flags now
  recorded explicitly on the rule payload.

**Tests:** All T1 boundary tests (startup_growth at $550K +
growth_mature at $3.3M) continue green; both have downgrade available
so existing assertions `conservative_floor_applied is True` and
`rule == "stage_boundary_uncertainty"` still pass. New symmetric
behavior: supplements G-1 ($496K STARTUP) now records
`stage_boundary_uncertainty` with `conservative_floor_applied=False`.

## Sprint 6.5 Ticket T4.x.1 closeout (2026-05-18)

**Status:** Complete. Inventory-clock refresh commit. Refreshes 4
stale inventory CSVs whose `Updated At` columns had aged past the
Fix-11 7-day threshold. KI-31/KI-32 batched into the same commit
per founder direction.

**Commit:** `75bf273 S6.5-T4.x.1: refresh healthy_beauty + supplements
inventory clocks (Fix-11 rot class); KI-31/KI-32`

**Files refreshed:**
- `tests/fixtures/synthetic/healthy_beauty_240d_inventory.csv`
- `tests/fixtures/synthetic/healthy_beauty_low_inventory_240d_inventory.csv`
- `tests/fixtures/synthetic/healthy_supplements_240d_inventory.csv`
- `tests/fixtures/synthetic/supplement_replenishment_240d_inventory.csv`

**Behavior:** No engine code change. Only the inventory CSVs' `Updated At`
column shifts; orders CSVs remain byte-identical (seed-deterministic
generation). All downstream HTML/JSON shas byte-identical because
inventory CSV bytes don't enter the briefing render path beyond the
freshness gate. Class-of-problem note in commit message: wall-clock
time-bomb is a structural fixture-rot pattern; harden test design
post-S6.5 (file KI for "freshness gate against fixture mtime not
wall-clock").

## Sprint 6.5 Ticket T4.x closeout (2026-05-18)

**Status:** Complete. Fixture-regen commit. New synthetic Beauty fixture
`winback_activation_beauty_240d_*` added per founder approval; orders
+ inventory CSVs + scenarios YAML update + generator addition.

**Commit:** `f784ed2 S6.5-T4.x: regen synthetic Beauty fixtures with
fresh inventory clock + dormant-cohort injection`

**Files:** `scripts/generate_synthetic_shopify.py` (new scenario
generator), `tests/fixtures/synthetic_scenarios.yaml` (scenario entry),
`tests/fixtures/synthetic/winback_activation_beauty_240d_orders.csv`
(new), `tests/fixtures/synthetic/winback_activation_beauty_240d_
inventory.csv` (new).

**Behavior:** No engine code change. Pre-existing Fix-11
(`TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh`)
RED at HEAD after Commit 1 due to a pre-existing wall-clock time-bomb
on `healthy_beauty_low_inventory_240d_inventory.csv` (not introduced
by T4.x; broader fixture-clock rot class — see
agent_outputs/code-refactor-engineer-s6_5-t5-blocker-diagnosis.md
§§1-2 + §9 for the audit; resolved in T4.x.1).

## Sprint 6.5 Ticket T4 closeout (2026-05-18)

**Status:** Complete. Flag `ENGINE_V2_STORE_PROFILE` still default OFF. All 5 pinned fixtures byte-identical under flag OFF. **STOP for founder review on the curated ~40-cell table + R1/R2 probes in the summary doc before T5 begins.**

**What shipped (R1 + R2 + 4 consumer wirings + load-bearing yaml):**

- `config/gate_calibration.yaml` — the load-bearing artifact. `audience_floors.winback_dormant_cohort` fully populated (4 stages × 10 subverticals + mixed_beauty/mixed_supplements); `audience_floors._default_by_stage` for the other 13 plays (provenance fires `gate_calibration_default_floor_used` per cell). `materiality_floors_usd` per stage (startup:$800, growth:$2000, mature:$4500, enterprise:$12000). `primary_window` per (vertical, subvertical) as FALLBACK only — R2 makes cadence-derived the primary path. `agreement_windows` per (vertical, subvertical). `pseudo_n_default` per stage. `windows_pinned: [L28, L56, L90]` pins the L42 deferral. Every cell tagged `heuristic_unvalidated`.
- `src/profile/builder.py::derive_gate_calibration(taxonomy, stage, cadence, data_depth, business_model) -> (GateCalibration, MeasurementContext)` — pure function (test: 100 runs identical). DS architect §2.3 stage-uncertainty broader-cell fallback. REFUSED subvertical → `mixed_<vertical>` row. Cell-not-found → conservative architecture-default + `gate_calibration_cell_missing` provenance fire. R2 routing: SUBSCRIPTION_LED → `subscription_led_static_window`; COMPUTED cadence with class median → `cadence_derived_primary_window` via round-to-nearest of `{L28, L56, L90}`; otherwise `cadence_fallback_static_window`.
- Schema additions (additive within `event_version=1`): `ReasonCode.WINDOW_DISAGREEMENT` + considered/would-fire-if copy templates; `WindowCorroboration` enum (`CORROBORATED | NEUTRAL | CONTRADICTED`); `PlayCard.measurement.window_corroboration: Optional[WindowCorroboration]`; `PlayCard.drivers[].profile_field_ref: Optional[str]` (additive key); `StoreProfile.gate_calibration.pseudo_n_default: Optional[int]` + `.profile_field_refs: Dict[str,str]`; `StoreProfile.measurement.primary_window_source: str`.
- 4 consumer wirings under `ENGINE_V2_STORE_PROFILE` flag (default OFF; T5 owns the atomic flip):
  - `src/audience_builders.py::winback_dormant_cohort_candidates` reads floor from `profile.gate_calibration.audience_floor_by_play_id["winback_dormant_cohort"]` via `cfg["_store_profile"]`; fallback `MIN_N_WINBACK_DORMANT` (500).
  - `src/measurement_builder.py::build_directional_play_card` + `build_prior_anchored_play_card` accept `store_profile` + `profile_flag_on` kwargs. R2: primary_window + agreement_windows read from `profile.measurement` under flag-ON. R1: both pathways emit `window_corroboration` via `_window_corroboration_sign_only` (directional) and `_prior_anchored_window_corroboration` (closes DS architect §1 asymmetry; degrades to NEUTRAL when metric absent in aligned). `R1_SIGN_P_MAX = 0.10` (looser than directional gate p<0.05; R1 is a corroboration read, not a gate).
  - `src/decide.py` — new `_route_window_disagreement_holds` (CONTRADICTED → Considered with `WINDOW_DISAGREEMENT`); new `_apply_window_corroboration_bumps` (CORROBORATED bumps Emerging → Strong within MEASURED/DIRECTIONAL tier ceiling only; Targeting never bumps; Strong stays Strong). Both gate on `ENGINE_V2_STORE_PROFILE`; flag-OFF is a no-op.
  - `src/guardrails.py::gate_materiality` accepts `profile_floor_usd` kwarg; `apply_guardrails` threads it from `engine_run.store_profile.gate_calibration.materiality_floor_usd` when both `MATERIALITY_FLOOR_SCALE_AWARE` and `ENGINE_V2_STORE_PROFILE` are ON.
  - `src/sizing.py::effective_pseudo_n(status, store_profile, profile_flag_on)` — validated-path cold-start weight = `min(PSEUDO_N_BY_STATUS[status], profile.gate_calibration.pseudo_n_default)`. Profile can ONLY LOWER the weight (Part III-1 pseudo_N policy invariant). S7.5-T3 refusal logic UNCHANGED for heuristic_unvalidated / placeholder. measurement_builder's prior-anchored path routes through this helper.
  - `src/main.py` threads `_store_profile` + `_profile_flag_on` into `_build_directional_recs` + `_build_prior_anchored` call sites so flag-ON exercises R1+R2 end-to-end.

**Tests:** 39 new in `tests/test_s6_5_t4_gate_calibration.py` (the 32-item IM plan list verbatim + 7 belt-and-suspenders extras). Coverage: `derive_gate_calibration` purity (100 runs), stage-uncertainty broader-cell, REFUSED subvertical → mixed, cell-missing default + provenance, R2 cadence-derived (Beauty/skincare 53d→L56; supplements/protein 40d→L28; nootropics 75d→L90), R2 INSUFFICIENT_DATA fallback, R2 SUBSCRIPTION_LED short-circuit, round-to-nearest boundary table (28/42/43/72/73/74/90), audience builder flag-ON (Beauty cohort 428 passes growth/skincare floor 200) + flag-OFF (rejects under hardcoded 500), measurement flag-OFF null window_corroboration, R1 all three enum values reachable, R1 confidence bump tier-ceiling (Targeting never bumps, Strong stays Strong), CONTRADICTED → WINDOW_DISAGREEMENT routing, agreement_windows excludes primary, prior-anchored helper NEUTRAL parity, gate_materiality profile-override + scale-aware fallback, effective_pseudo_n profile-lowers-not-raises invariant, YAML schema (heuristic_unvalidated + 4-stage coverage + winback fully populated + _default_by_stage catch-all), L42 deferral pin ({L28, L56, L90} exact), event_version=1 round-trip with window_corroboration. One T1 orchestrator test stub updated (`detection_status DEFERRED_TO_T4 → "DERIVED"`). 100 S6.5 tests pass (T1+T2+T3+T4 combined); 18 pinned-fixture sha256 regression tests pass (byte-identity preserved).

**Per-fixture probe (R2 + R1 + projected card delta):**

| Fixture | stage | business_model | cadence | primary_window | source | audience_floor.winback | projected flag-ON delta |
|---|---|---|---|---|---|---:|---|
| Beauty pinned (`healthy_beauty_240d_orders.csv`) | GROWTH (LOW) | ONE_TIME_LED (sub_frac=0.07) | skincare:53d | **L56** | cadence_derived | 200 | **+1 Recommended Now** (cohort=428 ≥ 200) |
| Supplements G-1 (`healthy_supplements_240d_orders.csv`) | STARTUP (HIGH; detected=GROWTH) | SUBSCRIPTION_LED (sub_frac=0.97) | functional:38, multivitamin:39, probiotics:40, protein:40 | **L56** | subscription_led_static | 60 | 0 new Recommended (cohort below floor + PRIOR_UNVALIDATED) |
| M0 small_sm / mid_shopify / micro_coldstart | n/a (legacy `ENGINE_V2_SIZING=false` path) | n/a | n/a | n/a | n/a | n/a | **0 change** |

**R2 founder envelope PASS:** Beauty/skincare cadence-derived primary_window = L56 (NOT the static L28 sketch); SUBSCRIPTION_LED short-circuit verified on Supplements G-1.

**R1 founder envelope:** `window_corroboration` populated on BOTH directional + prior-anchored pathways under flag-ON; CORROBORATED/CONTRADICTED/NEUTRAL all reachable via tests; `WINDOW_DISAGREEMENT` ReasonCode + copy templates live.

**Hard-stops:** none on T4 impl (flag OFF). The hard-stop IS the founder-review checkpoint — T5 does NOT auto-start. Founder approves the curated 40-cell table + R2 cadence-derived window probe + R1 distribution probe in the T4 summary doc before T5 begins.

**Caveats / what T4 does NOT do:**

- Consumer wiring is wired but DORMANT on every pinned fixture (flag default OFF). T5 owns the atomic flip + Beauty + supplements G-1 fixture re-pin.
- 35–48d cadence quantization gap acknowledged: supplements one-time-led stores with 38–40d cadence will round to L28. L42 4th window deferred per founder 2026-05-18; revisited post-beta after one real store.
- Cell-by-cell calibration deferred to S10+ outcome-driven recalibration loop (Phase 9 outcome importer). Every cell carries `heuristic_unvalidated` tag.
- R1 sign-only at MVP; magnitude-ratio band deferred. R1's prior-anchored pathway degrades to NEUTRAL when the metric is absent from aligned (typical at S6.5 for `reactivation_rate`); the field-presence parity is what closes the DS architect §1 asymmetry — the per-window cohort recomputation lifts at S11 when outcome history flows.
- 13 plays consume `audience_floors._default_by_stage` via the `_default` cell + `gate_calibration_default_floor_used` provenance. Per-(play × subvertical × stage) cells for those plays land when each play ships a profile-aware audience builder of its own.

**Schema:** `event_version=1` additive (3 schema additions; all defaults preserve pre-T4 round-trip).
**Suite:** 100 S6.5 tests pass (T1+T2+T3+T4 combined). Pinned fixture sha256 byte-identical under flag OFF (18 regression tests pass).
**Summary:** [agent_outputs/code-refactor-engineer-s6_5-t4-summary.md](agent_outputs/code-refactor-engineer-s6_5-t4-summary.md)

**Founder approval (2026-05-18) — T4 → T5 gate cleared.** Founder accepted all four review questions verbatim with no cell changes:
- **Q1 (Beauty/skincare growth floor):** 200 stays. Cohort=428 passes with 228 margin (114% headroom). Activation moment proceeds.
- **Q2 (Supplements asymmetry):** Keep 60/150/400/1200 vs beauty 80/200/500/1500. Founder reasoning: supplements cadence is structurally faster (30d consumption rhythm vs beauty 50-60d), dormant pools are smaller at same store size, reflects category norms (iHerb/Ritual/Care/of subscription-native pattern). Asymmetry is intuition + category-norm backed; outcome loop in S10+ recalibrates from real beta data. Caveat acknowledged: synthetic supplements G-1 is SUBSCRIPTION_LED so won't exercise winback path; calibration is for future one-time-led supplements stores.
- **Q3 (Materiality floors):** $800/$2000/$4500/$12000 ship as-is.
- **Q4 (`_default_by_stage` for 13 plays):** Defer per-play cells until each play ships a profile-aware audience builder. winback is the only Tier-B builder shipped through S6-T1.5; other plays consume `_default` with `gate_calibration_default_floor_used` provenance fire.

**T5 cleared to proceed.** No T4 cell-value adjustments needed before T5 starts.
