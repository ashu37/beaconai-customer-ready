# BeaconAI — Locked Decisions Registry

**Purpose:** single source of truth for founder-locked engine defaults, per-play floors, per-vertical windows, prior selection choices, hard-stop envelopes, and other heuristic values that are NOT obvious from the code. Each entry documents WHAT was decided, WHY, WHERE in code it lives, HOW to override it, and WHAT tests will break if you change it.

**Audience:** future you, future agents, future contributors. Read this BEFORE adjusting any heuristic value. The values in code are deliberate; the rationale is here.

## How to use this file

- **Adding entries:** every founder-locked decision gets an ID (`D-<sprint>-<n>`), a one-line title, decision body, source-of-truth code path, override mechanism, and pinning tests. Append to the right category below.
- **Updating entries:** when a value changes, update the entry in-place and add a `Superseded by` line at the bottom of the original. Don't delete old decisions — they're audit history.
- **When to file:** any founder Q that gets locked in memory.md sprint-anchor or sprint-closeout sections should also be filed here. The bar is "would a future agent need to know this to make a sensible change."
- **What goes IN:** per-play floors, per-vertical windows, prior consumption choices, hard-stop envelopes, refusal logic semantics, gate calibration cells (curated), deferred-to-later decisions (KI-style, but for decisions that were CONSCIOUSLY locked, not unresolved).
- **What stays OUT:** code patterns/conventions (derivable from code); transient sprint state (lives in memory.md); founder strategy axioms (lives in memory.md D-1 through D-8); unresolved bugs (lives in KNOWN_ISSUES.md).
- **Status values:** `active` (current locked value) / `superseded` (replaced by a newer decision; keep entry for audit) / `under review` (founder has signaled willingness to revisit; new decision pending).

## Index by category

1. [Per-play audience floors](#1-per-play-audience-floors)
2. [Per-play prior consumption](#2-per-play-prior-consumption)
3. [Per-vertical window selection (multi-window evidence)](#3-per-vertical-window-selection-multi-window-evidence)
4. [Hard-stop envelopes (activation moments)](#4-hard-stop-envelopes-activation-moments)
5. [Refusal logic semantics](#5-refusal-logic-semantics)
6. [Stage / business-model detection rules](#6-stage--business-model-detection-rules)
7. [Cadence inference parameters](#7-cadence-inference-parameters)
8. [Subvertical taxonomy authority](#8-subvertical-taxonomy-authority)
9. [Seasonality calendar windows](#9-seasonality-calendar-windows)
10. [Deferred decisions (consciously-locked-as-deferred)](#10-deferred-decisions-consciously-locked-as-deferred)

---

## 1. Per-play audience floors

### D-S6.5-1 — Beauty `winback_dormant_cohort` audience floor (per stage)

- **Status:** active
- **Date locked:** 2026-05-18 (founder review on S6.5-T4 founder gate)
- **Decision:** Per-stage audience floors for `winback_dormant_cohort` on Beauty are `{startup:80, growth:200, mature:500, enterprise:1500}`. Per-subvertical (skincare/cosmetics/haircare/personal_care) all use the same values within Beauty.
- **Why:** Tracks the synthetic Beauty cohort = 356 customers passing the growth/skincare floor of 200 with 156 margin. The activation moment lands cleanly. Materiality floor `$2000` independently gates dollar-impact.
- **Source-of-truth:** `config/gate_calibration.yaml` → `audience_floors.winback_dormant_cohort.beauty.<subvertical>`
- **Consumed at:** `src/audience_builders.py::winback_dormant_cohort_candidates` (reads via `cfg["_store_profile"].gate_calibration.audience_floor_by_play_id["winback_dormant_cohort"]`).
- **Override mechanism:** Edit `config/gate_calibration.yaml` cell values; no code change required.
- **Pinning tests:** `tests/test_s6_5_t4_gate_calibration.py`; `tests/test_s6_5_t5_atomic_repin.py` test #10 pins growth floor = 200.
- **Safe to adjust?** Adjusting floor values requires fixture re-pin (Beauty pinned slate sha256 will shift if cohort count crosses floor). Outside-fixture impact: real beta stores' card surfaces change.

### D-S6.5-2 — Supplements `winback_dormant_cohort` audience floors (per stage)

- **Status:** active
- **Date locked:** 2026-05-18
- **Decision:** Per-stage audience floors for `winback_dormant_cohort` on supplements are `{startup:60, growth:150, mature:400, enterprise:1200}`. Asymmetric to Beauty (lower).
- **Why:** Supplements is structurally faster-cadence than beauty (30-day consumption rhythm vs 50-60d); dormant pools are smaller at any given store size; reflects iHerb/Ritual/Care/of subscription-native category norms. Founder rejected the "match beauty" symmetric alternative explicitly with full understanding that it's intuition + category-norm backed, not data-backed yet. Outcome loop in S10+ recalibrates from real beta data. Caveat: synthetic supplements G-1 is SUBSCRIPTION_LED so doesn't exercise winback anyway; calibration is for future one-time-led supplements stores.
- **Source-of-truth:** `config/gate_calibration.yaml` → `audience_floors.winback_dormant_cohort.supplements.<subvertical>`
- **Override mechanism:** Edit YAML; no code change.
- **Pinning tests:** `tests/test_s6_5_t4_gate_calibration.py`
- **Safe to adjust?** Same as D-S6.5-1 — requires fixture re-pin if cohort crosses floor.

### D-S6.5-3 — Mixed-vertical `winback_dormant_cohort` floors (REFUSED subvertical fallback)

- **Status:** active
- **Date locked:** 2026-05-18
- **Decision:** `mixed_beauty` floors `{120, 300, 700, 2000}`; `mixed_supplements` floors `{100, 250, 600, 1500}`. Both higher than the per-subvertical rows in the same vertical (more conservative on uncertain stores).
- **Why:** A store whose taxonomy subvertical resolved to REFUSED (mixed) has weaker signal; broader floor protects against false-activation.
- **Source-of-truth:** `config/gate_calibration.yaml` → `audience_floors.winback_dormant_cohort.mixed_<vertical>`
- **Pinning tests:** Same as D-S6.5-1/2.

### D-S6.5-4 — `_default_by_stage` floors for the other 13 plays

- **Status:** active
- **Date locked:** 2026-05-18 (founder Q4 on S6.5-T4 founder gate)
- **Decision:** All plays OTHER than `winback_dormant_cohort` read from `_default_by_stage` = `{startup:50, growth:150, mature:400, enterprise:1200}`. No per-subvertical cells until each play ships a profile-aware audience builder.
- **Why:** Honors S7.5 discipline — don't invent per-cell numbers we can't defend. Per-subvertical floors get authored when the play's builder lands (S6-T3 `replenishment_due`, S7-T1/T2/T3 for the final 3 Tier-B builders). Cell-missing provenance fires `gate_calibration_default_floor_used` for auditability.
- **Source-of-truth:** `config/gate_calibration.yaml` → `audience_floors._default_by_stage`
- **Pinning tests:** `tests/test_s6_5_t4_gate_calibration.py` validates the default-stage row presence.
- **Safe to adjust?** Cheap — no per-play fixture impact today. Becomes load-bearing once Tier-B builders consume the default cell with non-zero audience.

### D-FLOOR-replenishment_due — `replenishment_due` audience floor (per stage, beauty-only, S6-T3.5 Commit B)

- **Status:** LOCKED
- **Date locked:** 2026-05-19 (S6-T3.5 Commit B; ecommerce-ds-architect audit 2026-05-19, agent `a17b73e5aeaa940ed`)
- **Decision:** Per-stage audience floors for `replenishment_due`:

  | stage      | beauty subverticals | mixed_beauty (1.5×) |
  |------------|---------------------|---------------------|
  | startup    |                  60 |                  90 |
  | growth     |                 150 |                 225 |
  | mature     |                 350 |                 525 |
  | enterprise |                1000 |                1500 |

  Uniform across all 4 Beauty subverticals (`skincare`, `cosmetics`, `haircare`, `personal_care`). REFUSED subvertical falls through to `mixed_beauty`. **No supplements cell by design** — resolver returns `None` (NOT zero, NOT cascading to `_default_by_stage`); the missing key is the auditable "no cell" signal, aligned with the asymmetric prior posture under D-PRIORS-replenishment_due_supplements_deferred / D-S6-2.1.
- **Why:** `replenishment_due` is a behavioral predicate (window of ±½-cadence around each customer's next predicted purchase date, per D-S6-5). The addressable universe is structurally smaller than the dormant winback pool because it activates only on customers entering the due window in the look-ahead horizon, not all dormant accounts. One notch BELOW the winback floors per stage reflects this. Materiality floor (`$2000` at growth) remains the binding $-impact gate; the audience floor governs posterior coherence (per-merchant rate estimation has enough cohort to avoid noise), not prior tightness.
- **Source-of-truth:** `config/gate_calibration.yaml` → `audience_floors.replenishment_due.{beauty.<subvertical> | mixed_beauty}.<stage>`
- **Consumed at:** `src/profile/builder.py::derive_gate_calibration` (strict resolver `_resolve_audience_floor_cell_strict` — does NOT cascade); surfaces on `profile.gate_calibration.audience_floor_by_play_id["replenishment_due"]` (key omitted for supplements).
- **Override mechanism:** `ENGINE_V2_BUILDER_REPLENISHMENT_DUE` flag (currently OFF; flips ON in S6-T3.5 Commit C atomic re-pin). YAML cell values editable; no code change required to adjust per-stage numbers.
- **Pinning tests:** `tests/test_s6_t3_5_replenishment_due_floor_resolver.py` (42 cases: 16 beauty subverticals × 4 stages, 4 mixed_beauty × 4 stages, 20 supplements-returns-None, 2 builder-integration); Commit C atomic-repin tests (`tests/test_s6_5_t5_atomic_repin.py`, `tests/test_slate_regression_beauty_brand.py`, `tests/test_slate_regression_supplements_brand.py`).
- **Safe to adjust?** Phase 9 outcome-driven recalibration alongside winback floors (D-S6.5-1/2). Tracked at KI-NEW-B. Numeric value changes require fixture re-pin of every changed artifact in the 5 pinned fixtures.
- **Source-of-truth audit:** DS-architect attribution — ecommerce-ds-architect 2026-05-19 audit (agent `a17b73e5aeaa940ed`); founder-locked grid in Path A execution plan.

### D-FLOOR-discount_dependency_hygiene — `discount_dependency_hygiene` audience floor (per stage, beauty-only, S7 founder lock)

- **Status:** LOCKED
- **Date locked:** 2026-05-20 (founder-locked grid 2026-05-20; ecommerce-ds-architect priors-validation memo 2026-05-20, agents `a427cc139d6e357fc` + `a17b73e5aeaa940ed`)
- **Decision:** Per-stage audience floors for `discount_dependency_hygiene`:

  | stage      | beauty subverticals | mixed_beauty (1.5×) |
  |------------|---------------------|---------------------|
  | startup    |                  40 |                  60 |
  | growth     |                 100 |                 150 |
  | mature     |                 250 |                 375 |
  | enterprise |                 750 |                1125 |

  Uniform across all 4 Beauty subverticals (`skincare`, `cosmetics`, `haircare`, `personal_care`). REFUSED subvertical falls through to `mixed_beauty`. **Conditional bump rule:** when store-level discount-fraction > 40% (heavy-promo posture per DS architect 2026-05-20), floor BUMPS UP to `{startup:80, growth:200, mature:500, enterprise:1500}` — parity with D-S6.5-1 winback grid. Bump applies uniformly across the 4 beauty subverticals; `mixed_beauty` stays at 1.5×. **No supplements cell by design** — supplements `discount_dependency_hygiene` routes `PRIOR_UNVALIDATED` per DS Memo-4 REJECT verdict (tracked at KI-NEW-J).
- **Why:** DS architect rationale 2026-05-20 — the discount-dependency cohort (customers with >N orders all on promo) is structurally thinner than the winback dormant pool: typically 5-15% of file in heavy-promo Beauty stores, smaller still in disciplined-promo stores. Floors tighten by ~50% from the D-S6.5-1 winback-mirror (`{80, 200, 500, 1500}`) to reflect the narrower addressable universe. The conditional bump restores winback-mirror parity precisely when the cohort widens (>40% discount-fraction stores have 25-35% of file in the dependency cohort), preserving posterior coherence at the upper end of the heavy-promo distribution. Materiality floor remains the binding $-impact gate; the audience floor governs posterior coherence, not prior tightness.
- **Source-of-truth:** `config/gate_calibration.yaml` → `audience_floors.discount_dependency_hygiene.{beauty.<subvertical> | mixed_beauty}.<stage>` (cells authored at S7-T1 builder ticket per S6-T3.5 Commit B precedent — one floor authoring per builder ticket).
- **Consumed at:** `src/profile/builder.py::derive_gate_calibration` (strict resolver `_resolve_audience_floor_cell_strict` — does NOT cascade); surfaces on `profile.gate_calibration.audience_floor_by_play_id["discount_dependency_hygiene"]` (key omitted for supplements). Conditional bump applies in the builder via a discount-fraction posture predicate on `profile.commerce_posture`.
- **Override mechanism:** S7-T1 builder flag (TBD at S7-T1 sprint planning). YAML cell values editable; no code change required to adjust per-stage numbers or the 40%-discount-fraction threshold.
- **Pinning tests:** Will land at S7-T1 (`tests/test_s7_t1_discount_dependency_hygiene_floor_resolver.py`-style following the D-FLOOR-replenishment_due 42-case pattern: beauty subverticals × stages, mixed_beauty × stages, supplements-returns-None, builder-integration, plus dedicated cases for the discount-fraction >40% conditional bump).
- **Safe to adjust?** Phase 9 outcome-driven recalibration alongside D-S6.5-1/2 and D-FLOOR-replenishment_due. Tracked at KI-NEW-B (audience-floor recalibration sweep). Numeric value changes will require fixture re-pin of every changed artifact in the pinned fixtures once S7-T1 ships.
- **Source-of-truth audit:** DS-architect attribution — ecommerce-ds-architect 2026-05-20 priors-validation memo (`agent_outputs/ecommerce-ds-architect-s7-priors-validation-2026-05-20.md`, agents `a427cc139d6e357fc` + `a17b73e5aeaa940ed`); founder-locked grid 2026-05-20.

### D-FLOOR-aov_lift_via_threshold_bundle — `aov_lift_via_threshold_bundle` audience floor (per stage, beauty-only, S7 founder lock)

- **Status:** LOCKED
- **Date locked:** 2026-05-20 (founder-locked grid 2026-05-20; ecommerce-ds-architect priors-validation memo 2026-05-20, agents `a427cc139d6e357fc` + `a17b73e5aeaa940ed`)
- **Decision:** Per-stage audience floors for `aov_lift_via_threshold_bundle`:

  | stage      | beauty subverticals | mixed_beauty (1.5×) |
  |------------|---------------------|---------------------|
  | startup    |                  40 |                  60 |
  | growth     |                 100 |                 150 |
  | mature     |                 250 |                 375 |
  | enterprise |                 750 |                1125 |

  Uniform across all 4 Beauty subverticals (`skincare`, `cosmetics`, `haircare`, `personal_care`). REFUSED subvertical falls through to `mixed_beauty`. **No supplements cell despite supplements appearing in `vertical_applicability` of `priors.yaml`** — supplements ships at `elicited_expert` tier per DS DOWNGRADE (Path-D-style activation contingent on real beta data + tighter cohort signals; tracked at KI-NEW-J). Supplements `aov_lift_via_threshold_bundle` routes `PRIOR_UNVALIDATED` until the elicited_expert→validated_external pathway opens.
- **Why:** DS architect rationale 2026-05-20 — the near-threshold cohort (customers whose current cart or recent AOV sits within a configurable band of the bundle threshold) is a snapshot constraint structurally narrower than the first-to-second window cohort (which is a time-window constraint accumulating over the look-ahead horizon). Floors mirror D-FLOOR-discount_dependency_hygiene values rather than D-S6.5-1 winback to reflect the snapshot-vs-window thinness: at growth a typical Beauty store has ~100 customers in the near-threshold band vs ~200 in the dormant winback pool. Tightening ~50% from winback-mirror preserves posterior coherence on the thinner cohort. Materiality floor remains the binding $-impact gate.
- **Source-of-truth:** `config/gate_calibration.yaml` → `audience_floors.aov_lift_via_threshold_bundle.{beauty.<subvertical> | mixed_beauty}.<stage>` (cells authored at S7-T3 builder ticket per S6-T3.5 Commit B precedent — one floor authoring per builder ticket).
- **Consumed at:** `src/profile/builder.py::derive_gate_calibration` (strict resolver `_resolve_audience_floor_cell_strict` — does NOT cascade); surfaces on `profile.gate_calibration.audience_floor_by_play_id["aov_lift_via_threshold_bundle"]` (key omitted for supplements).
- **Override mechanism:** S7-T3 builder flag (TBD at S7-T3 sprint planning). YAML cell values editable; no code change required to adjust per-stage numbers.
- **Pinning tests:** Will land at S7-T3 (`tests/test_s7_t3_aov_lift_via_threshold_bundle_floor_resolver.py`-style following the D-FLOOR-replenishment_due 42-case pattern: beauty subverticals × stages, mixed_beauty × stages, supplements-returns-None, builder-integration).
- **Safe to adjust?** Phase 9 outcome-driven recalibration alongside D-S6.5-1/2, D-FLOOR-replenishment_due, and D-FLOOR-discount_dependency_hygiene. Tracked at KI-NEW-B (audience-floor recalibration sweep) and KI-NEW-J (supplements elicited_expert→validated_external pathway). Numeric value changes will require fixture re-pin of every changed artifact in the pinned fixtures once S7-T3 ships.
- **Source-of-truth audit:** DS-architect attribution — ecommerce-ds-architect 2026-05-20 priors-validation memo (`agent_outputs/ecommerce-ds-architect-s7-priors-validation-2026-05-20.md`, agents `a427cc139d6e357fc` + `a17b73e5aeaa940ed`); founder-locked grid 2026-05-20; DS DOWNGRADE rationale for supplements deferral documented in implementation-manager S7 planning refresh.

### D-FLOOR-cohort_journey_first_to_second — `cohort_journey_first_to_second` audience floor (per stage, symmetric across verticals, S7-T2 clerical lock)

- **Status:** LOCKED
- **Date locked:** 2026-05-20 (S7-T2 Commit A; clerical lock per IM plan Gap B; DS architect ratification optional because the underlying prior is wildcard)
- **Decision:** Per-stage audience floors for `cohort_journey_first_to_second`:

  | stage      | beauty | mixed_beauty (1.5×) | supplements | mixed_supplements (1.5×) |
  |------------|-------:|--------------------:|------------:|-------------------------:|
  | startup    |     40 |                  60 |          40 |                       60 |
  | growth     |    100 |                 150 |         100 |                      150 |
  | mature     |    300 |                 450 |         300 |                      450 |
  | enterprise |   1000 |                1500 |        1000 |                     1500 |

  Uniform across all 4 Beauty subverticals (`skincare`, `cosmetics`, `haircare`, `personal_care`) AND all 5 Supplements subverticals (`protein`, `multivitamin`, `probiotics`, `nootropics`, `functional`). REFUSED subvertical falls through to the matching `mixed_<vertical>` row. **Symmetric across verticals because the underlying S7.5-T2 prior is wildcard** (`first_to_second_purchase.base_rate.*`, `applies_to.vertical: "*"`, validated_external bsandco 2026 DTC RPR memo, effective_n=156110) — the prior itself does not argue for per-vertical floor asymmetry, so the floor grid does not either. This is the ONLY S7 builder cell shipping with supplements coverage at S7-T2 (T1 + T3 are beauty-only per D-FLOOR-discount_dependency_hygiene + D-FLOOR-aov_lift_via_threshold_bundle).
- **Why:** First-time buyers in a 30-90 day age window are a recurring stream that accumulates over the look-ahead horizon — structurally LARGER than dormant winback or near-threshold or replenishment-cadence cohorts at every stage. Floors land BELOW winback (D-S6.5-1: 80/200/500/1500) and BELOW replenishment_due (D-FLOOR-replenishment_due: 60/150/350/1000) to reflect the recurring-stream economics: the same percent-of-base translates to a larger raw N for a window-accumulating cohort than for a snapshot cohort. Materiality floor (`$2000` at growth) remains the binding $-impact gate; the audience floor governs posterior coherence (per-merchant rate estimation has enough cohort to avoid noise), not prior tightness. The wildcard prior means the same Beta posterior parameters apply across verticals; symmetric floors keep activation behavior coherent across the vertical surface.
- **Source-of-truth:** `config/gate_calibration.yaml` → `audience_floors.cohort_journey_first_to_second.{beauty.<subvertical> | mixed_beauty | supplements.<subvertical> | mixed_supplements}.<stage>`
- **Consumed at:** `src/profile/builder.py::derive_gate_calibration` (strict resolver `_resolve_audience_floor_cell_strict` — does NOT cascade to `_default_by_stage`); surfaces on `profile.gate_calibration.audience_floor_by_play_id["cohort_journey_first_to_second"]`. The strict resolver returns a value for every (vertical, subvertical, stage) tuple covered by the grid above; when a (subvertical) is REFUSED, the mixed-vertical fallback row applies.
- **Override mechanism:** `ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND` flag (default OFF at S7-T2; flips ON in S7-T2.5 atomic with the Beauty pinned slate + supplements G-1 fixture re-pin). YAML cell values editable; no code change required to adjust per-stage numbers.
- **Pinning tests:** `tests/test_s7_t2_cohort_journey_first_to_second_builder.py` (S7-T2 builder + measurement_builder + enum cross-pin + floor-resolver coverage; full floor-resolver matrix tests follow the D-FLOOR-replenishment_due 42-case pattern in the same file).
- **Safe to adjust?** Phase 9 outcome-driven recalibration alongside D-S6.5-1/2, D-FLOOR-replenishment_due, D-FLOOR-discount_dependency_hygiene, and D-FLOOR-aov_lift_via_threshold_bundle. Tracked at KI-NEW-B (audience-floor recalibration sweep). Numeric value changes will require fixture re-pin of every changed artifact in the 5 pinned fixtures once S7-T2.5 ships.
- **Source-of-truth audit:** clerical lock per implementation-manager S7 planning refresh (`agent_outputs/implementation-manager-s7-planning-refresh.md` Section 3 Gap B); DS architect ratification optional because the underlying prior is wildcard (no per-vertical asymmetry argument to litigate).

### D-S6-1 — `winback_dormant_cohort` hardcoded floor (legacy fallback)

- **Status:** active (fallback only; superseded by D-S6.5-1/2 under flag-ON)
- **Date locked:** 2026-05-17 (S6-T1 ship)
- **Decision:** Legacy hardcoded floor `MIN_N_WINBACK_DORMANT = 500` when `ENGINE_V2_STORE_PROFILE=false`.
- **Why:** Pre-profile-layer baseline. Architecture-plan default. Caused the synthetic Beauty 356-cohort to fail floor → triggered S6.5 sprint.
- **Source-of-truth:** `src/audience_builders.py` (constant near `winback_dormant_cohort_candidates`)
- **Override mechanism:** Flip `ENGINE_V2_STORE_PROFILE=true` to route to per-stage floors (D-S6.5-1/2).
- **Pinning tests:** `tests/test_s6_t1_winback_dormant_cohort.py`
- **Safe to adjust?** Flag-OFF path only matters for legacy/rollback; tighten via the profile layer instead.

---

## 2. Per-play prior consumption

### D-S6-2 — `replenishment_due` prior selection (Q3, locked 2026-05-18)

- **Status:** superseded
- **Decision:** S6-T3 `replenishment_due` consumes existing `bestseller_amplify.bundle_value.beauty` (validated_external bsandco prior from S7.5-T2) on the Beauty path. No new prior YAML authoring at T3. Supplements path falls into heuristic_unvalidated via the same prior block (bsandco is Beauty-only) → routes to Considered with `PRIOR_UNVALIDATED` per S7.5-T3 refusal logic.
- **Why:** Cleanest path — no new YAML, no new memo authoring. Semantically: bestseller_amplify and replenishment_due both target repeat-purchase behavior. Authoring a dedicated `replenishment_due.base_rate` block would start as heuristic_unvalidated (no external memo) → no Beauty activation at T3.5. Defer the dedicated block to a future memo-pending ticket.
- **Source-of-truth:** `src/measurement_builder.py::_SUPPORTED["replenishment_due"]` (when S6-T3 lands)
- **Override mechanism:** Add `replenishment_due.base_rate.<vertical>.<source>` block to `config/priors.yaml`; flip the measurement_builder dispatch to consume it.
- **Pinning tests:** `tests/test_s6_t3_replenishment_due_builder.py` (when S6-T3 lands)
- **Safe to adjust?** Requires Beauty + supplements fixture re-pin at T3.5 and possibly a new external memo if you want validated_external status on a dedicated prior.
- **Superseded by:** D-S6-2.1 (2026-05-19, S6-T3.x). DS architect audit 2026-05-19 identified a category error: `bestseller_amplify.bundle_value.beauty` is per-customer DOLLARS ($45 / range $25-$75), not a probability rate; the prior-anchored pathway's `audience × posterior × aov` formula double-counts AOV when posterior is dollar-typed. Re-purposing the bundle_value memo would also invalidate the `validated_external` claim across all 3 S7.5-T2 promotions. 2026-05-19 Gemini Deep Research unlocked Path A — dedicated `replenishment_due.base_rate.beauty` block at `validated_external` status (Klaviyo PERL Cosmetics + H&B 2026 cross-flow, see `config/priors_sources/replenishment_due__base_rate__beauty.md`).

### D-S6-2.1 — `replenishment_due` prior re-keyed to dedicated `base_rate.beauty` block (S6-T3.x, locked 2026-05-19)

- **Status:** active
- **Decision:** `replenishment_due` consumes a dedicated `replenishment_due.base_rate.beauty` block authored at `validation_status: validated_external`, `value=0.0220`, `range_p10=0.0120`, `range_p90=0.0430`, `effective_n=30`, backed by the 2026-05-19 Gemini Deep Research memo at `config/priors_sources/replenishment_due__base_rate__beauty.md`. Supersedes D-S6-2's bundle_value routing. Supplements path has NO `replenishment_due.base_rate` block by design (asymmetric posture) and routes to Considered with `PRIOR_UNVALIDATED` via the standard S7.5-T3 refusal logic when no matching block for the vertical exists.
- **Why:** Resolves the D-S6-2 dollar-vs-rate category error: `base_rate` is a probability rate (0.0-1.0) so `audience × posterior × aov` is dimensionally coherent. Preserves the validated_external integrity of the existing bsandco bundle_value memo (bestseller_amplify still consumes it; only its USE as a replenishment_due prior was invalidated). Supplements asymmetry is DS-architect-endorsed (memo 2026-05-19): authoring a supplements stub for code-symmetry would fabricate a prior to satisfy code shape; the asymmetric reason code (Beauty validated_external activation vs. supplements PRIOR_UNVALIDATED refusal) is informative.
- **Source-of-truth:** `config/priors.yaml::plays.replenishment_due.priors[name=base_rate, applies_to.vertical=beauty]`; `src/measurement_builder.py::_PRIOR_ANCHORED["replenishment_due"]` (now points at `prior_play_id="replenishment_due"`, `prior_key="base_rate"`).
- **Memo:** `config/priors_sources/replenishment_due__base_rate__beauty.md` (Gemini Deep Research 2026-05-19; saved verbatim per process discipline in commit `011c7cc` BEFORE wiring).
- **Override mechanism:** To author a supplements counterpart, add a `replenishment_due.base_rate` block with `applies_to: { vertical: supplements }` AND author its own external memo under `config/priors_sources/`. To re-anchor the Beauty prior, write a new memo and update the YAML value + last_updated; never silently change the value.
- **Pinning tests:** `tests/test_s6_t3_x_prior_rekey.py` (this ticket); `tests/test_s7_5_t2_external_priors.py` covers the validated_external schema discipline.
- **Safe to adjust?** Numeric value changes require fixture re-pin at T3.5 (envelope hard-stop D-S6-3 enforced). Adding the supplements block requires fixture re-pin AND a new memo.

### D-S7.5-1 — 3 validated_external promotions in priors.yaml

- **Status:** active
- **Date locked:** 2026-05-17 (S7.5-T2)
- **Decision:** Three priors promoted from `heuristic_unvalidated` to `validated_external` with external memo documentation:
  1. `winback_21_45.base_rate` (vertical: beauty) — Klaviyo 2026 H&B benchmarks (effective_n=30).
  2. `bestseller_amplify.bundle_value` (vertical: beauty) — bsandco source (effective_n=30).
  3. `first_to_second_purchase.base_rate` (all-vertical, bsandco source, effective_n=30).
- **Why:** External benchmark memos exist (`config/priors_sources/`); validated against published Klaviyo H&B numbers and bsandco bundle-value benchmarks. effective_n=30 is the founder-locked default cap for validated_external (D-S7.5-3).
- **Source-of-truth:** `config/priors.yaml` block-level `validation_status` field
- **Memos:** `config/priors_sources/winback_21_45__base_rate__beauty.md`, `config/priors_sources/bestseller_amplify__bundle_value__beauty.md`, `config/priors_sources/first_to_second_purchase__base_rate__all.md`
- **Pinning tests:** `tests/test_s7_5_t2_external_priors.py`
- **Safe to adjust?** Demoting a prior to heuristic_unvalidated requires fixture re-pin (activated cards may revert to Considered). Adding new validated_external requires a new memo + founder approval.

### D-S7.5-2 — All other priors stay `heuristic_unvalidated`

- **Status:** active
- **Decision:** Every prior in `priors.yaml` not in D-S7.5-1 carries `validation_status: heuristic_unvalidated`. They route to `PRIOR_UNVALIDATED` Considered per S7.5-T3 refusal logic and do NOT activate cards in Recommended Now.
- **Why:** Honest posture — no external benchmark backing means no validation claim. The 8 `internal_csv_observation_v1` priors (winback_21_45 supplements/mixed, orders_per_customer, discount_hygiene margin_recovery, empty_bottle base_rate, frequency_accelerator base_rate supplements/mixed) had values hardcoded in `src/action_engine.py` with no reproducible derivation found in repo grep (per memory.md S7.5-T1.5 audit). The `source: internal_csv_observation_v1` tag remains as a descriptive label but is no longer a validation claim.
- **Source-of-truth:** `config/priors.yaml`
- **Pinning tests:** `tests/test_s7_5_t1_priors_validation_fields.py`

---

## 3. Per-vertical window selection (multi-window evidence)

### D-S6.5-5 — Primary window is cadence-derived, not statically configured (R2)

- **Status:** active
- **Date locked:** 2026-05-18 (DS architect multi-window memo; founder approved R1+R2 for T4)
- **Decision:** Per-cohort `primary_window` is derived from cadence by `round_to_nearest({L28, L56, L90}, cadence.median_reorder_days_by_sku_class[class])`. Static `(vertical, subvertical) → primary_window` lookup in `gate_calibration.yaml` is FALLBACK ONLY (consulted when cadence is INSUFFICIENT_DATA, or for SUBSCRIPTION_LED stores per D-S6.5-6).
- **Why:** Beauty/skincare cadence is 53d on the synthetic fixture. Static sketch said L28 → wrong window for skincare. Cadence-derived correctly resolves to L56. Original IM-plan sketch was data-blind.
- **Source-of-truth:** `src/profile/builder.py::derive_gate_calibration` (the round_to_nearest logic)
- **Override mechanism:** Force-static via the YAML by emptying the cadence baseline (set `business_model=SUBSCRIPTION_LED` artificially), or extend `_GATE_CALIBRATION_WINDOWS` to add a 4th window (see D-S6.5-7).
- **Pinning tests:** `tests/test_s6_5_t4_gate_calibration.py` tests #9-11
- **Safe to adjust?** Changing the round-to-nearest set requires re-pin; changing the cadence-derivation logic is structural.

### D-S6.5-6 — SUBSCRIPTION_LED stores short-circuit to static window (R2 gate)

- **Status:** active
- **Date locked:** 2026-05-18 (DS architect risk #4)
- **Decision:** When `business_model == SUBSCRIPTION_LED`, primary_window reads from static `gate_calibration.yaml` cell, NOT cadence-derived. Provenance fires `subscription_led_static_window`.
- **Why:** Subscription cadence is contractual (the merchant set the 30-day cycle), not behavioral. Cadence-derived window would mirror the subscription interval and miss the underlying one-time-buyer rhythm if any.
- **Source-of-truth:** `src/profile/builder.py::derive_gate_calibration` (the SUBSCRIPTION_LED branch)
- **Pinning tests:** `tests/test_s6_5_t4_gate_calibration.py` test #12

### D-S6.5-7 — L42 4th window deferred to post-beta

- **Status:** active (deferred-by-decision; revisit trigger documented)
- **Date locked:** 2026-05-18 (founder rejected option to add L42 to the window set)
- **Decision:** Window set is exactly `{L28, L56, L90}`. No 4th window (L42) added.
- **Why:** 35-48d cadence stores fall awkwardly between L28 and L56 (round to L28 with quantization). Synthetic supplements fixture 38-40d cluster is acknowledged as known calibration target but synthetic-only — no real beta data yet to justify expansion.
- **Revisit trigger:** After one real beta store with cadence in 35-48d band.
- **Source-of-truth:** `src/profile/builder.py::_GATE_CALIBRATION_WINDOWS = ("L28", "L56", "L90")`; `config/gate_calibration.yaml::windows_pinned: [L28, L56, L90]`
- **Override mechanism:** Add 4th window to BOTH the constant tuple AND the YAML; update the round-to-nearest logic; re-pin all fixtures.
- **Pinning tests:** Test #32 in `tests/test_s6_5_t4_gate_calibration.py` enforces the exact 3-window set.

### D-S6.5-8 — `window_corroboration` is a confidence modifier, not a vote (R1)

- **Status:** active
- **Date locked:** 2026-05-18 (DS architect multi-window memo)
- **Decision:** Primary window decides p-value (unchanged). The two non-primary windows produce `PlayCard.measurement.window_corroboration ∈ {CORROBORATED, NEUTRAL, CONTRADICTED}`. `CORROBORATED` bumps confidence_label one notch within the card's evidence-tier ceiling (Tier B Emerging→Strong eligible; Tier C corroboration recorded but does not bump label; Tier D never bumps). `CONTRADICTED` routes card to Considered with `WINDOW_DISAGREEMENT` ReasonCode. NEUTRAL is no-op.
- **Why:** Legacy multi-window weighted-vote (0.30/0.60/0.10) was numerology — weights had no principled derivation. Sign-only agreement check is interpretable; weighted magnitudes are not. R1 closes the asymmetry where directional pathway used `_sign_agreement_count` but prior-anchored did not.
- **Source-of-truth:** `src/measurement_builder.py::_window_corroboration_sign_only` + `_prior_anchored_window_corroboration`; `src/decide.py::_apply_window_corroboration_bumps` + `_route_window_disagreement_holds`
- **Override mechanism:** R1 gates on `ENGINE_V2_STORE_PROFILE`; flag-OFF is a no-op. Magnitude-ratio band (deferred at MVP) would extend the check from sign-only to magnitude-aware.
- **Pinning tests:** Tests #16-23 in `tests/test_s6_5_t4_gate_calibration.py`

### D-S6.5-9 — Confidence bump never crosses evidence-tier boundary

- **Status:** active
- **Decision:** `CORROBORATED` confidence bump applies only WITHIN the card's evidence-tier ceiling. Tier C (prior-anchored) corroboration is recorded in provenance (`corroboration_observed_no_bump`) but does NOT promote label to a level that implies Tier B (directional/measured) evidence.
- **Why:** Promoting Tier C → Tier B would imply we have measured cohort behavior when we only have a corroborating prior signal. Misrepresents evidence class.
- **Source-of-truth:** `src/decide.py::_apply_window_corroboration_bumps`
- **Pinning tests:** Test #23 in `tests/test_s6_5_t4_gate_calibration.py`

---

## 4. Hard-stop envelopes (activation moments)

### D-S6.5-10 — Beauty winback posterior envelope check at S6.5-T5

- **Status:** active (precedent set; reused at S6-T3.5)
- **Date locked:** 2026-05-17 (S6.5-T5 acceptance criteria)
- **Decision:** Beauty winback posterior `revenue_range.p50` must land inside the Klaviyo `validated_external` prior's `[range_p10, range_p90]` envelope. Out-of-envelope → STOP and escalate, not auto-re-pin.
- **Why:** The activation moment is the first time a `validated_external` prior anchors a posterior on a real fixture. A posterior outside the prior's full uncertainty range means either the prior doesn't fit the cohort semantically or the `bayesian_blend` has a bug. STOP discipline catches both.
- **Source-of-truth:** Hard-stop #6 in `tests/test_s6_5_t5_atomic_repin.py`
- **Verified at T5:** p50=$1686.50 inside [Klaviyo p10, Klaviyo p90] envelope. PASS.

### D-S6-3 — `replenishment_due` posterior envelope check at S6-T3.5

- **Status:** active (locked 2026-05-18, Q5; envelope citation refreshed 2026-05-19 at S6-T3.5 Commit B)
- **Decision:** Same envelope-style rule as D-S6.5-10. Beauty replenishment_due posterior p50 must land inside the prior's `[range_p10, range_p90]` window. The prior is now `replenishment_due.base_rate.beauty` (per D-S6-2.1, S6-T3.x re-key) with `[range_p10=0.0120, range_p90=0.0430]`. Out-of-envelope → STOP. The earlier citation pointed at `bestseller_amplify.bundle_value.beauty`; that prior is no longer the replenishment_due anchor (still load-bearing for the bestseller_amplify native consumer; do not touch).
- **Why:** Same precedent as S6.5-T5. Wider envelope (p10-p90 is the full uncertainty range) accepted over tighter ±30%-of-p50 alternative because legitimate store-data-driven posterior shifts (which is what we want as outcome history accumulates) shouldn't trip the hard-stop.
- **Source-of-truth:** Will land in `tests/test_s6_t3_5_replenishment_due_repin.py` (when S6-T3.5 ships).

---

## 5. Refusal logic semantics

### D-S7.5-3 — `pseudo_n` cap per validation status

- **Status:** active
- **Date locked:** 2026-05-17 (S7.5-T1, founder Q4)
- **Decision:** `PSEUDO_N_BY_STATUS = {VALIDATED_EXTERNAL: 30, VALIDATED_INTERNAL: 15, ELICITED_EXPERT: 10}`. Heuristic_unvalidated and placeholder are deliberately ABSENT — they trigger refusal, not blend weight.
- **Why:** Intentional prior-weakness posture — the absolute numbers (30/15/10) are tunable; the **ordering** (external > internal > elicited) is the load-bearing claim, not the absolute magnitudes. Bayesian blend cold-start weight scales with prior validation strength: external benchmark = strongest prior support → biggest pseudo_n (slowest shift toward store-observed). Heuristic/placeholder cannot be blended at all — refused outright. Earlier "founder Q4 locked" framing implied the magnitudes were calibrated; they were not — they were chosen to give validated_external priors a defensibly slow shift profile against expected per-merchant outcome volumes (K=3 minimum for play-level priors per Loop B+ design).
- **Source-of-truth:** `src/sizing.py::PSEUDO_N_BY_STATUS`
- **Override mechanism:** Profile gate_calibration `pseudo_n_default[stage]` can ONLY LOWER the cap (e.g., growth stage default=20 caps the validated_external pseudo_n at 20). Never raise above status cap. Pinned by D-S6.5-11.
- **Pinning tests:** `tests/test_s7_5_t1_priors_validation_fields.py`, `tests/test_s6_5_t4_gate_calibration.py` test #15
- **Revisit trigger:** KI-NEW-C — recalibrate per-stage `pseudo_n_default` (and revisit the per-status cap magnitudes) against real beta posterior-shift velocity once Phase 9 outcome data lands. Preserve the validated_external > validated_internal > elicited_expert ordering; only the magnitudes should move.

### D-S6.5-11 — Profile `pseudo_n_default` only lowers, never raises

- **Status:** active
- **Date locked:** 2026-05-18 (S6.5-T4 effective_pseudo_n design)
- **Decision:** `effective_pseudo_n = min(PSEUDO_N_BY_STATUS[status], profile.gate_calibration.pseudo_n_default[stage])`. Profile parameterizes the cold-start weight INSIDE the validated path; it cannot expand it beyond the status cap.
- **Why:** Lower pseudo_n lets store data move the posterior faster as outcome history accumulates. Allowing profile to RAISE pseudo_n would weaken priors arbitrarily. The "profile lowers" rule preserves D-S7.5-3 as the upper bound.
- **Source-of-truth:** `src/sizing.py::effective_pseudo_n`
- **Pinning tests:** Test #15 in `tests/test_s6_5_t4_gate_calibration.py`

### D-S7.5-4 — `PRIOR_UNVALIDATED` refusal routes to Considered

- **Status:** active
- **Date locked:** 2026-05-17 (S7.5-T3)
- **Decision:** When a card's prior carries `heuristic_unvalidated` or `placeholder` validation_status, the card routes to Considered with `ReasonCode.PRIOR_UNVALIDATED` rather than activating in Recommended Now. Even if cohort and materiality gates pass.
- **Why:** No external benchmark backing means no defensible posterior. Activating a card on a fabricated prior would put unfounded numbers in front of merchants.
- **Source-of-truth:** `src/decide.py` (the PRIOR_UNVALIDATED routing); `src/sizing.py` (the refusal trigger)
- **Pinning tests:** `tests/test_s7_5_t3_blend_refusal.py`
- **Active impact:** Supplements winback stays in Considered (heuristic_unvalidated supplements winback prior); Beauty winback activates (Klaviyo validated_external).

---

## 6. Stage / business-model detection rules

### D-S6.5-12 — Stage bands

- **Status:** active
- **Date locked:** 2026-05-17 (S6.5-T1)
- **Decision:** Annualized GMV → stage: `STARTUP <$500K`, `GROWTH $500K-$3M`, `MATURE $3M-$20M`, `ENTERPRISE >$20M`. GMV estimated via TTM / L180×2 / L90×4 based on history depth.
- **Why:** Architecture proposal default. Reflects DTC industry conventions for revenue bands.
- **Why these specific numbers:** $500K / $3M / $20M are DTC industry-convention round numbers — not empirically derived from this engine's data or a calibration study. They sit at conventional inflection points operators use casually to describe DTC store maturity. The band values are MVP defaults; the ±25% boundary-uncertainty rule (D-S6.5-13) is what protects against false stage assignment at the edges, not the absolute band values.
- **Source-of-truth:** `src/profile/builder.py::detect_business_stage`
- **Override mechanism:** `BUSINESS_STAGE` env var (per-run operator override).
- **Pinning tests:** `tests/test_s6_5_t1_store_profile.py`
- **Revisit trigger:** KI-NEW-E — replace the discrete band + ±25% rule with a continuous uncertainty function once real beta-merchant GMV distributions are observed.

### D-S6.5-13 — Conservative-broader band-boundary rule (Q2, symmetric)

- **Status:** active
- **Date locked:** 2026-05-17 (founder Q2); fixed to be symmetric on lower-side of boundary at S6.5-T4.y.1 (2026-05-18)
- **Decision:** When GMV is within ±25% of ANY band boundary (either side), record `uncertainty=HIGH` + `stage_boundary_uncertainty` provenance rule. When the applied band can be downgraded one notch (NOT at the STARTUP floor), set `conservative_floor_applied=True` and use the broader (smaller-store) band.
- **Why:** Detection at boundary is noisy. Downgrading to the broader band protects against over-aggressive plays on borderline stores. Symmetric per founder Q2 contract — fires on BOTH sides of the boundary, not just above.
- **Source-of-truth:** `src/profile/builder.py::detect_business_stage`
- **Pinning tests:** `tests/test_s6_5_t1_store_profile.py` boundary-uncertainty tests; T4.y.1 supplements G-1 envelope test (verifies $496K within ±25% of $500K triggers HIGH at STARTUP floor).

### D-S6.5-14 — Business-model classification thresholds

- **Status:** active
- **Date locked:** 2026-05-17 (S6.5-T1)
- **Decision:** Customers with ≥3 orders at σ/μ <0.3 inter-order gap contribute their L180 orders to the subscription bucket. `subscription_fraction >40%` → SUBSCRIPTION_LED, `<10%` → ONE_TIME_LED, else HYBRID.
- **Why:** Subscription-led detection driven by inter-order regularity, not order count alone. The 40%/10% bands provide a hybrid middle ground for stores with significant non-subscription revenue.
- **Source-of-truth:** `src/profile/builder.py::detect_business_model`
- **Pinning tests:** `tests/test_s6_5_t1_store_profile.py` business-model tests

### D-S6.5-15 — `VERTICAL_MODE` env var removed from .env (2026-05-18)

- **Status:** active (resolution; superseded the legacy operator-override usage)
- **Decision:** `VERTICAL_MODE=beauty` was removed from repo-root `.env` at T4.y.1. The Store Profile Layer's detector is now authoritative for every fixture. The `VERTICAL_MODE` env var mechanism still exists in `src/profile/builder.py::detect_taxonomy` but is no longer pre-populated.
- **Why:** Stale single-vertical-era artifact was leaking into supplements runs and contaminating taxonomy detection (supplements fixture forced to beauty.skincare.startup). Removing the env var restored correct per-fixture detection.
- **Source-of-truth:** Absence of the line in `.env`; `src/profile/builder.py::detect_taxonomy:344` honors the env var when set.
- **Override mechanism:** Set `VERTICAL_MODE=<vertical>` at process invocation for one-off per-run override testing. Do NOT add it back to `.env`.

---

## 7. Cadence inference parameters

### D-S6-4 — Per-SKU cadence-inference floor (Q2, locked 2026-05-18)

- **Status:** active
- **Decision:** S6-T3 `replenishment_due_candidates` requires N=30 customers-with-≥2-repeat-purchases per SKU. SKUs below floor contribute zero audience without crash.
- **Why:** Cadence median statistically meaningful at N=30. Lower (N=15) raises Type I risk on small samples; higher (N=50) risks zero-audience no-op on Beauty fixture. Same N=30 floor used at S6.5-T3 `compute_cadence_baseline`.
- **Source-of-truth:** Will land in `src/audience_builders.py::replenishment_due_candidates` at S6-T3
- **Pinning tests:** Will land in `tests/test_s6_t3_replenishment_due_builder.py` test #3

### D-S6.5-16 — Right-censored empirical median (cadence baseline)

- **Status:** active
- **Date locked:** 2026-05-17 (S6.5-T3)
- **Decision:** `compute_cadence_baseline` uses pure-pandas right-censored empirical median per SKU class. Customers with only 1 in-class purchase are right-censored (do NOT contribute to median). Per-class N=30 floor; below floor → `method="INSUFFICIENT_DATA"`. K-M (Kaplan-Meier) survival fit deferred to S11.
- **Why:** Pure-pandas MVP avoids `lifelines` dependency at S6.5 (D-6 ban). Right-censoring drops the singleton-customer bias that would otherwise pull medians toward the early part of a customer's history. K-M will recover the dropped contribution when S11 unblocks the ML predictive layer.
- **Source-of-truth:** `src/profile/cadence.py::compute_cadence_baseline`
- **Override mechanism:** S11 will add a Cox PH survival fit and replace right-censored empirical median.
- **Pinning tests:** `tests/test_s6_5_t3_cadence_seasonality.py` cadence-envelope tests + D-6 import-ban pin
- **2026-05-28 footnote — `lifelines` → `scikit-survival` substitution (S11-T1, commit `3cfa06b`):** `ROADMAP.md` §1 L13 and §2 L42 originally referenced `lifelines` as the S11 Cox PH dependency. S11-T1 substituted `scikit-survival>=0.22,<0.24` per `agent_outputs/ds-architect-s11-plan-review.md` §B. **Rationale:** same Cox PH math (proportional-hazards regression with right-censoring); `scikit-survival` is better-maintained, actively developed, sklearn-ecosystem-backed (`BaseEstimator` / `score()` interface), and ships pre-built mac-ARM wheels; zero refactor cost because S11 is a greenfield substrate (no existing survival call sites to migrate). **Out of scope:** S10's `lifetimes==0.11.3` pin (BG/NBD + Gamma-Gamma) stays — `lifetimes` covers the Pareto/NBD + Gamma-Gamma family that `scikit-survival` does not; that refactor is deferred to post-beta S15+ if `lifetimes` maintenance becomes a burden. **Tracked dependency risk:** `KI-NEW-R` (3-library vendor-fork escape hatch — `lifetimes` + `scikit-survival` + `implicit`).

### D-S12-1 — `cohort_diagnostics` slot architecturally separate from `predictive_models`

- **Status:** active
- **Date locked:** 2026-05-28 (S12-T2; DS S12 plan review §C verdict lock)
- **Decision:** New top-level `EngineRun.cohort_diagnostics: Dict[str, Any]` slot lives alongside `predictive_models`. Cohort-aggregate diagnostics (NOT per-customer rankers) land here. First occupant: retention (`RetentionCard`, S12-T2.5). A NEW `RetentionCard` dataclass (separate from `ModelCard`) **reuses the `ModelFitStatus` enum** per the S11 Option A vocab-stacking precedent — labels shared, namespace-disambiguated by dataclass identity. No parquet artifacts for cohort-aggregate diagnostics (curves are JSON-shaped and live directly on the slot).
- **Why:** `ModelCard` is contractually a per-customer ranker shape — load-bearing fields are `holdout_rank_spearman`, `holdout_c_index`, `holdout_top_k_recall`, `coverage_at_k`, `parquet_schema_version`. Forcing a cohort-aggregate diagnostic (no held-out object, no per-customer parquet) into that slot inverts the schema's invariants. Future cohort-aggregate diagnostics — cohort-AOV evolution, cohort-frequency evolution, churn-hazard-by-cohort — all want this same slot, not the per-customer-ranker slot. DS S12 plan review §C rejected the alternative ("shoehorn into `predictive_models[retention]`") explicitly.
- **Source-of-truth:** `src/engine_run.py::EngineRun.cohort_diagnostics` field + tolerant `_from_dict_engine_run` extension; `src/predictive/model_card.py::RetentionCard` dataclass; `src/predictive/retention.py::fit_retention` (no `data_dir` argument — retention writes no parquet).
- **Override mechanism:** Architectural lock; not a value to tune. Future cohort-aggregate diagnostics extend the same dict.
- **Pinning tests:** `tests/test_s12_t2_retention_fit.py` (`cohort_diagnostics` round-trip via `EngineRun.to_dict()/from_dict()`; pre-S12 payloads default `{}`); `tests/test_s12_t2_5_retention_rollback.py::Case B` (architectural pin: `"retention"` MUST be in `cohort_diagnostics`, NOT in `predictive_models`).
- **Safe to adjust?** Structural change. Removing or renaming the slot would break `event_version=1` additive contract and the S13 ranking-strategy consumer wiring.
- **Cross-link:** `agent_outputs/ds-architect-s12-plan-review.md` §C; `agent_outputs/code-refactor-engineer-s12-t2-summary.md`; `agent_outputs/code-refactor-engineer-s12-t2.5-summary.md`; `STATE.md` §4 (predictive layer composition).

### D-S13-1 — Q-S13-4 LOCK: ML-fit ReasonCodes emit ONLY on `model_card_ref.fit_warnings`, NEVER on `RejectedPlay.reason_code`

- **Status:** active (LOCKED)
- **Date locked:** 2026-05-29 (S13-T2; DS S13 plan review §B verdict lock)
- **Decision:** `ReasonCode.MODEL_FIT_INSUFFICIENT_DATA` and `ReasonCode.MODEL_FIT_REFUSED` emit ONLY on `PlayCard.model_card_ref.fit_warnings` (the `List[str]` channel). **NEVER on `RejectedPlay.reason_code`.** ML-fit gate is the fourth orthogonal demotion gate (lowest precedence) — it **NEVER demotes between slate roles**; it only triggers a silent fallback within the audience-ranking chain.
- **Why:** Structural-incoherence rationale per DS S13 plan review §B: a card cannot be both in Recommended Now (slate role) AND in Considered (demoted role) for the same `play_id`. ML-fit failure is silent fallback within audience ranking, not a slate-role transition. The four-gate orthogonality survives only if ML-fit stays out of the demote-channel surface. The earlier S10-T3 speculative wiring ("S13 wires `src/decide.py` to populate these on `RejectedPlay.reason_code`") is REVERSED here.
- **Source-of-truth:** `src/engine_run.py:167-183` LOAD-BEARING comment block (revised at S13-T2 per Q-S13-4 LOCK); `src/predictive/consumer_wiring.py::populate_play_card_consumers` (the only emitter); `src/predictive/ranking_strategy.py::rank_audience` (produces the fit_warnings strings).
- **Override mechanism:** Architectural lock; not a value to tune. Any future code path appending `ReasonCode.MODEL_FIT_*` to `RejectedPlay.reason_code` violates this decision and must be reverted.
- **Pinning tests:** `tests/test_s13_ml_fit_never_demotes.py` (5-fixture runtime test extended at T3.5 with month-2 sequence per DS S13 plan review §F); AST-aware `tests/test_reason_code_precedence_invariant.py` (negative invariant: no `Assign` / `AnnAssign` / `Call(RejectedPlay, reason_code=...)` node carries `ReasonCode.MODEL_FIT_*`; `ranking_strategy.py` allowlist REMOVED at T2 — chain-walker fit_warnings are operator-trace strings, NOT ReasonCode emissions).
- **Safe to adjust?** Structural change with multiple test anchors. Reversal requires founder + DS sign-off + revision of `STATE.md` §4 ML-fit precedence framing.
- **Cross-link:** `agent_outputs/ds-architect-s13-plan-review.md` §B; `agent_outputs/code-refactor-engineer-s13-t2-summary.md`; `agent_outputs/code-refactor-engineer-s13-t2.5-summary.md`; `STATE.md` §4 (ML-fit LIVE block); `docs/engine_flags.md` (S13 audit copy).

### D-S13-2 — Modal-segment stability floor on `predicted_segment.segment_name`

- **Status:** active (LOCKED)
- **Date locked:** 2026-05-29 (S13-T2; DS S13 plan review §D.4 verdict lock)
- **Decision:** `PlayCard.predicted_segment.segment_name = None` when `n_audience < 50` OR `audience_modal_share < 0.30`. Audit fields (`audience_modal_share`, `n_audience`) populate uncensored regardless of the floor outcome — operators can read the floor decision without inferring it.
- **Why:** A modal segment derived from a tiny audience (`n_audience<50`) or from a non-modal-ish share (`audience_modal_share<0.30`) is not a defensible segment label — it would be label-laundering. The floor enforces "only publish a segment_name when the data supports the claim"; audit fields stay uncensored so operators can see the floor decision rather than a silent absence.
- **Source-of-truth:** `src/predictive/consumer_wiring.py::populate_play_card_consumers` (modal-segment floor evaluation); `src/engine_run.py::PredictedSegment` (extended at T2 with `segment_name`, `audience_modal_share`, `n_audience` fields, all `Optional`, default `None`).
- **Override mechanism:** Floor numeric values (50, 0.30) are calibration cells per `KI-NEW-P` consumer-side extension; closure trigger = S14 real-merchant data + DS recalibration verdict.
- **Pinning tests:** `tests/test_s13_t2_predicted_segment_population.py` (`n<50` → `segment_name=None` with audit fields uncensored; `share<0.30` → `segment_name=None` with audit fields uncensored; happy path populates all 3 fields).
- **Safe to adjust?** Cheap calibration adjustment (numeric values) post-S14 evidence; structural floor itself is locked.
- **Cross-link:** `agent_outputs/ds-architect-s13-plan-review.md` §D.4; `agent_outputs/code-refactor-engineer-s13-t2-summary.md`; `KNOWN_ISSUES.md::KI-NEW-P` (consumer-side calibration cells); `STATE.md` §4 (new typed slots block).

### D-S13-3 — Lineage-change constraint for `month_2_delta` (21-day floor + segment-shift suppression on audience-definition-version bump)

- **Status:** active (LOCKED)
- **Date locked:** 2026-05-29 (S13-T3; DS S13 plan review §D.2 verdict lock)
- **Decision:** Two coupled constraints govern `EngineRun.month_2_delta` population:
  1. **21-day floor:** `MonthDelta` does NOT populate when `days_between < 21` (computed from anchor_date, day-precision).
  2. **Lineage-change suppression:** when `audience_definition_version` bumps between prior and current runs, `segment_shifts` is suppressed (`= None`) with a `"lineage_changed_segment_shift_incomparable"` note. `substrate_fit_status_changes` remains comparable; `retention_ci_at_month_3_delta` remains comparable.
- **Why:** (1) Intra-cycle noise (days_between<21) would surface as month-over-month state change — fabrication of signal. The 21-day floor pins the substrate to roughly month-over-month cadence without claiming exact 30-day intervals. (2) When an audience definition version bumps, a v1-customer-set vs v2-customer-set comparison is comparing apples to oranges; "segment shift" measured across the bump would be a definition artifact, not a real shift. Suppressing `segment_shifts` (not faking it as `{}`) signals the incomparability explicitly. Substrate-fit-status and retention-CI metrics remain comparable because they are population-level posture statements that survive audience-definition drift.
- **Source-of-truth:** `src/predictive/month_2_delta.py::MONTH_2_DAY_FLOOR` (= 21) + `LINEAGE_CHANGED_NOTE` (= `"lineage_changed_segment_shift_incomparable"`); `_compute_segment_shifts` (returns `{}` when missing, `None` reserved for lineage-suppression case); `_extract_audience_definition_version` (probes top-level → briefing_meta → playcard fallback).
- **Override mechanism:** 21-day floor is calibration per `KI-NEW-P` consumer-side cells; lineage-change-constraint structure is architectural lock.
- **Pinning tests:** `tests/test_s13_t3_month_2_delta_positive_control.py` (21-day floor + boundary; lineage-change suppression; substrate-fit-status detection survives lineage change); `tests/test_s13_t3_5_month_2_delta_rollback.py` Case D INDEPENDENCE PIN.
- **Safe to adjust?** Floor numeric value cheap to recalibrate post-S14; lineage-change constraint structure is locked.
- **Cross-link:** `agent_outputs/ds-architect-s13-plan-review.md` §D.2 + §G.2; `agent_outputs/code-refactor-engineer-s13-t3-summary.md`; `agent_outputs/code-refactor-engineer-s13-t3.5-summary.md`; `PIVOTS.md::Pivot 8` (Beta success reframe — substrate-state-delta, NOT realized-outcome delta).

### D-S13-4 — `fit_warnings` shape (List[str] with `"{LEVEL}:{substrate}"` prefix grammar)

- **Status:** active (LOCKED)
- **Date locked:** 2026-05-29 (S13-T2; DS S13 plan review §D.3 verdict lock)
- **Decision:** `PlayCard.model_card_ref.fit_warnings: List[str]`. Each entry follows the strict prefix grammar `"{LEVEL}:{substrate}"`. 3 LEVELS:
  - `PROVISIONAL_SELECTED` — chain walker selected a PROVISIONAL fit because no upstream VALIDATED existed.
  - `MODEL_FIT_INSUFFICIENT_DATA` — substrate REFUSED on a data-floor (`min_customers` / `min_cohort_size` / `min_interactions_per_user` etc.).
  - `MODEL_FIT_REFUSED` — substrate REFUSED on a fit-quality gate (Spearman / c_index / brier / recall floor; monotonicity / quintile-coverage REFUSED gates).
- **Why:** Operators need an unambiguous parse — `string.split(":", 1)` lifts level + substrate cleanly. Without a fixed grammar, consumers would need substring matches or substrate-specific parsing. The 3-LEVEL closed set covers every fit-warning surface across the 6 substrates without exposing per-substrate vocabulary leakage.
- **Source-of-truth:** `src/predictive/ranking_strategy.py::rank_audience` (constructs `fit_warnings` entries during chain walk); `src/engine_run.py::ModelCardRef.fit_warnings` field (extended at T2).
- **Override mechanism:** Architectural lock on grammar; LEVEL set is closed.
- **Pinning tests:** `tests/test_s13_t2_predicted_segment_population.py` (fit_warnings grammar pin: PROVISIONAL_SELECTED + MODEL_FIT_REFUSED + MODEL_FIT_INSUFFICIENT_DATA cases); `tests/test_ranking_strategy_positive_control.py` (17 positive-control synthetics exercise all 3 LEVELS).
- **Safe to adjust?** Adding a 4th LEVEL would be structural; renaming any existing LEVEL breaks operator parsers. Both require founder + DS sign-off.
- **Cross-link:** `agent_outputs/ds-architect-s13-plan-review.md` §D.3; `agent_outputs/code-refactor-engineer-s13-t1-summary.md`; `agent_outputs/code-refactor-engineer-s13-t2-summary.md`; `docs/engine_flags.md` (S13 audit copy: `fit_warnings` grammar bullet).

### D-S13-5 — RULE A (flag-aware) absence-of-data pattern + 3 closed-set null-reason enums

- **Status:** active (LOCKED)
- **Date locked:** 2026-06-01 (S13.6-T7a; DS adjudication 2026-06-01 retract/revise of original §(e) triage + founder approval 2026-06-01)
- **Decision:** Revised RULE A verbatim from the DS adjudication 2026-06-01:
  > **RULE A (revised):** For every Optional field F on a contract surface, if F is None AND the relevant feature flag is ON, then F's paired `<F>_null_reason` MUST be set. Flag-OFF default-None is exempt and MUST be marked with a source-level annotation: `# null_reason_exempt: default-None when ENGINE_V2_<FLAG_NAME> is OFF`. The AST sweep test enforces: every Optional field either (i) has a paired `_null_reason` on the same contract, OR (ii) carries the `null_reason_exempt:` annotation with a named flag. No silent Optionals.
  
  Three closed-set null-reason enums land in `src/engine_run.py`:
  - `RevenueRangeSuppressionReason` (9 members; matches the producer string literals byte-for-byte per DS Q1 so producers wrap the existing string at the seam without rewrites)
  - `MonthDeltaNullReason` (5 members; `LINEAGE_CHANGED` reserved as forward-compat — S13-T3 lineage-bump nulls inner `segment_shifts`, not the wrapper)
  - `PredictedSegmentNullReason` (4 members; inner-field shape — applies to `segment_name`, NOT the wrapper, per D-S13-2 audit-field preservation)
  
  Three paired `_null_reason` fields land on the corresponding dataclasses:
  - `RevenueRange.suppression_reason: Optional[RevenueRangeSuppressionReason]` — paired with the existing `suppressed: bool` flag (invariant: `suppressed=True` ⇔ `suppression_reason is set`).
  - `EngineRun.month_2_delta_null_reason: Optional[MonthDeltaNullReason]` — paired with `month_2_delta: Optional[MonthDelta]`. Producer `detect_month_2_delta` returns a 2-tuple `(value, reason)` so the pairing is enforced at the seam.
  - `PredictedSegment.segment_name_null_reason: Optional[PredictedSegmentNullReason]` — paired with the inner `segment_name: Optional[str]` field.
- **Why:** Pre-T7a, every "absent value" carried only a producer-side string literal in `drivers` or an implicit None on a wrapper field. Downstream agents (narration / Klaviyo) had no closed-set surface to branch on — substring matching on driver strings is the anti-pattern the contract was designed to retire. Flag-aware framing (vs. the original §(e) "ALL Optionals MUST pair") avoids forcing artificial paired fields on every Optional whose absence is structurally meaningful (e.g., `Measurement is None when evidence_class == TARGETING` is the canonical encoding; pairing it would invert its semantics).
- **Source-of-truth:** `src/engine_run.py` (3 enums + 3 paired fields + per-Optional `# null_reason_exempt:` annotations); `src/sizing.py::_suppressed_range` (seam wrap for 6 RevenueRange producer-string literals); `src/measurement_builder.py` (3 RevenueRange producer sites); `src/decide.py` (1 RevenueRange producer site at the experiment-card path); `src/predictive/month_2_delta.py::detect_month_2_delta` (tuple-return seam); `src/predictive/consumer_wiring.py::_compute_modal_segment` (4-tuple-return seam).
- **Override mechanism:** Adding a new producer-side suppression string requires (a) adding the enum member with the matching string value, (b) wiring it at the seam, (c) updating the closed-set membership test. Adding a new paired `_null_reason` field on a new Optional requires a new closed-set enum + wiring + AST sweep test update.
- **Pinning tests:** `tests/test_s13_6_t7a_no_silent_nulls.py` — AST sweep enforces RULE A on every Optional in `src/engine_run.py`; per-row strict invariants on each paired field; closed-set enum coverage pins (9 / 5 / 4 members); round-trip + strict-cutover carry-forward.
- **Safe to adjust?** Adding enum members is additive within v2.0.0. Removing or renaming members is structural — requires founder + DS sign-off. Removing the AST sweep test is structural — RULE A is the load-bearing invariant.
- **Cross-link:** `agent_outputs/code-refactor-engineer-s13.6-t7-summary.md` (engineer halt analysis + T7a post-execution summary); DS adjudication 2026-06-01 (T7 split into T7a/T7b; founder approved 2026-06-01); `CHANGELOG` v2.0.0 block in `src/engine_run.py` (T7a entry). DEFERRED to S13.7 (T7b): substrate refusal-card audit + `StoreProfileNullReason` paired enum (producer surface not yet aligned with DS §(e) members `PROFILE_NOT_LOADED` | `ONBOARDING_INCOMPLETE`); a TODO(T7b) annotation marks the deferral on `EngineRun.store_profile`. DEFERRED to S13.7+: `CustomerIdsNullReason`.

### D-S13.6-1 — Pivot 2 ratification: engine emits zero merchant-facing prose on contract surface

- **Status:** active (LOCKED)
- **Date locked:** 2026-05-30 (S13.6-T1a; founder + DS approved)
- **Decision:** `recommendation_text`, `why_now`, `RejectedPlay.reason_text`, `RejectedPlay.evidence_snapshot`, `Observation.text`, and `notes` debris stripped at S13.6-T1a (Option D). `briefing.html` byte-identity pin retired; `engine_run.json` SHA is the new canary.
- **Why:** Embedding narration in the engine couples decision logic to presentation (Pivot 2). The agentic swarm reads typed atoms, not formatted prose. Stripping prose fields completes the Stop-Coding Line.
- **Source-of-truth:** `src/engine_run.py` (stripped dataclass fields); `src/decide.py` (`_apply_copy_ladder` deleted); `src/storytelling_v2.py` (renderer updated at T8).
- **Pinning tests:** `engine_run.json` SHA ledger (`tests/fixtures/pinned_sha_ledger.json`).
- **Safe to adjust?** Structural lock — reversal requires founder + DS sign-off + PIVOTS.md revision.
- **Cross-link:** `PIVOTS.md::Pivot 2` (T1a addendum + T6/T8 addendum); `agent_outputs/code-refactor-engineer-s13.6-t1a-summary.md`.

### D-S13.6-2 — Schema authority: `src/engine_run.py` re-exports all contract types

- **Status:** active (LOCKED)
- **Date locked:** 2026-05-30 (S13.6-T2; DS R6)
- **Decision:** `src/engine_run.py` is the single source of truth for the contract surface. All contract types are re-exported from this file via `__all__`. Agents read one file.
- **Why:** Prevents schema fragmentation where types lived in multiple modules (`predictive/model_card.py`, `predictive/month_2_delta.py`, etc.). Single-file authority eliminates "which module has the canonical definition" ambiguity for narration agents.
- **Source-of-truth:** `src/engine_run.py::__all__`.
- **Safe to adjust?** Adding types to `__all__` is additive. Removing requires DS sign-off.
- **Cross-link:** `agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md` DS R6.

### D-S13.6-3 — `NonLiftAtom` wrapper for `OpportunityContext.opportunity`

- **Status:** active (LOCKED)
- **Date locked:** 2026-05-30 (S13.6-T3; DS R1)
- **Decision:** `OpportunityContext.opportunity` is wrapped in a `NonLiftAtom` dataclass — a type-system constraint, not a sibling flag. Prevents narration agents from misnarrating addressable-opportunity values as lift.
- **Why:** Without a wrapper, a narration agent reading a bare float has no type-safe signal that it is an opportunity-size estimate, not a predicted revenue lift. The `NonLiftAtom` makes the semantics visible at the type level.
- **Source-of-truth:** `src/engine_run.py::NonLiftAtom`; `src/engine_run.py::OpportunityContext.opportunity`.
- **Safe to adjust?** Structural — removing the wrapper would silently re-expose the misnarration risk. Requires DS sign-off.
- **Cross-link:** `agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md` DS R1.

### D-S13.6-4 — `MechanismType` closed enum (10 members) + `MechanismIntent` dataclass on `PlayCard`

- **Status:** active (LOCKED)
- **Date locked:** 2026-06-01 (S13.6-T6; DS §(d) + founder approval; Option C adjudicated)
- **Decision:** `MechanismType(str, Enum)` with 10 DS-audited members (`WINBACK_REACTIVATION_EMAIL`, `FIRST_TO_SECOND_NUDGE`, `THRESHOLD_BUNDLE_OFFER`, `DISCOUNT_DEPENDENCY_HYGIENE`, `REPLENISHMENT_REMINDER`, `BESTSELLER_AMPLIFY`, `CATEGORY_EXPANSION`, `SUBSCRIPTION_NUDGE`, `ROUTINE_BUILDER`, `LOOKALIKE_HIGH_VALUE_PROSPECT`). `MechanismIntent` dataclass carries `type: MechanismType` + `parameters: Dict[str, Any]`. `PlayCard.mechanism_intent: Optional[MechanismIntent]` added. `RejectedPlay.mechanism` retyped `Optional[str] → Optional[MechanismIntent]`. YAML-lookup fallback in renderer retired at T8.
- **Why:** Typed enum atoms let narration agents branch on mechanism type without string-matching. Closed set prevents inventing new mechanism types without DS audit. See `PIVOTS.md::Pivot 2` T6/T8 addendum.
- **Source-of-truth:** `src/engine_run.py::MechanismType`, `MechanismIntent`; `src/decide.py::_PLAY_ID_TO_MECHANISM_TYPE`, `_build_mechanism_intent`.
- **Pinning tests:** `tests/test_s13_6_t6_mechanism_intent_atom.py` (28 tests).
- **Safe to adjust?** Adding enum members requires DS audit. Renaming or removing members is structural. `_PLAY_ID_TO_MECHANISM_TYPE` must be updated for any new Tier-B builder.
- **Cross-link:** `agent_outputs/code-refactor-engineer-s13.6-t6-summary.md`; `agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md` §(d).

### D-S13.6-5 — RULE A softened to flag-aware: `null_reason_exempt` annotation for flag-OFF defaults

- **Status:** active (LOCKED)
- **Date locked:** 2026-06-01 (S13.6-T7a; DS adjudication 2026-06-01 + founder approval)
- **Decision:** Absence of data must be a typed signal, EXCEPT when the field is `None` due to config-state (flag OFF) rather than absence-of-data. `# null_reason_exempt: <justification>` annotation used for flag-OFF defaults. 77 exempt annotations applied at T7a. DS retracted strict triage §(e); revised RULE A approved by founder 2026-06-01.
- **Why:** The original strict RULE A ("all Optionals must pair") would force artificial `_null_reason` fields on fields whose `None` encodes a structural truth (e.g., `Measurement is None` when `evidence_class == TARGETING`). Flag-aware framing separates "absence due to config off" (exempt) from "absence due to missing data" (must pair).
- **Source-of-truth:** `src/engine_run.py` (per-Optional `# null_reason_exempt:` annotations + 3 shipped paired enums); `tests/test_s13_6_t7a_no_silent_nulls.py` (AST sweep + RULE A enforcement).
- **Safe to adjust?** Adding new Optional fields requires either a paired `_null_reason` enum or an explicit `null_reason_exempt` annotation with named flag. The AST sweep test enforces this.
- **Cross-link:** `docs/DECISIONS.md::D-S13-5` (the original RULE A locked decision — this entry records the flag-aware softening); `agent_outputs/code-refactor-engineer-s13.6-t7-summary.md`; `KNOWN_ISSUES.md::KI-NEW-AA` (StoreProfile gap deferred to S13.7-T7b).

### D-S6-5 — Tolerance window for `replenishment_due` audience

- **Status:** active (locked 2026-05-18 as part of S6-T3 handoff)
- **Decision:** Per-SKU tolerance window for audience selection is half the cadence median (e.g., 30d cadence → ±15d). Documented in candidate's `audience_definition` text.
- **Why:** Loose-enough to capture realistic delay variance; tight-enough that a customer who hasn't reordered in 2× cadence is dormant, not replenishment-due. Future ticket can tighten.
- **Source-of-truth:** Will land in `src/audience_builders.py::replenishment_due_candidates`
- **Pinning tests:** Will land in `tests/test_s6_t3_replenishment_due_builder.py` test #14

---

## 8. Subvertical taxonomy authority

### D-S6.5-17 — Sephora + iHerb as token-dictionary source-of-truth (Q1)

- **Status:** active
- **Date locked:** 2026-05-17 (founder Q1)
- **Decision:** `config/subvertical_taxonomy.yaml` token vocabulary is an MVP token vocabulary scraped from two industry-leader DTC catalogs (Sephora for beauty, iHerb for supplements); not exhaustive and not authoritative beyond MVP cohort coverage. Source URLs documented inline. Tokens tagged `validation_status: heuristic_unvalidated` with same discipline as priors.
- **Why:** Two industry-leader DTC catalogs cover the subvertical space well enough for MVP cohort discrimination. Outcome-driven recalibration deferred to S10+ (Phase 9 outcome importer); real beta-merchant catalogs are expected to contain tokens these two leaders don't carry (e.g., niche actives, regional brands, white-label SKUs).
- **Source-of-truth:** `config/subvertical_taxonomy.yaml`
- **Pinning tests:** `tests/test_s6_5_t2_subvertical_classifier.py`
- **Per-cell token counts:** beauty/skincare 25, cosmetics 22, haircare 20, personal_care 20; supplements/protein 20, multivitamin 21, probiotics 16, nootropics 18, functional 20. All ≥15 (hard-stop floor pinned by test).
- **Revisit trigger:** KI-NEW-D — audit token vocabulary against real beta-merchant catalogs once Phase 9 outcome data lands; add missing-but-frequent tokens, deprecate Sephora/iHerb-specific tokens that don't appear in beta data.

### D-S6.5-18 — Subvertical classifier confidence thresholds

- **Status:** active
- **Decision:** Revenue-weighted argmax classifier. HIGH if leader/runner ratio ≥3.0 AND leader share ≥0.30. MEDIUM if ratio ≥2.0. LOW if ratio ≥1.3. Else `mixed_<vertical>` + LOW.
- **Why:** MVP threshold curve calibrated against synthetic fixtures; recalibrate against real beta confusion matrix when outcome data lands. The 3.0/2.0/1.3 step values produce clean confidence stratification on the synthetic G-1 / Beauty fixtures but are NOT empirically derived from real merchant catalog distributions; they were tuned to give the synthetic fixtures defensible HIGH/MEDIUM/LOW labels. Originally framed as "DS architect §8.1" — that framing overstated the empirical backing.
- **Source-of-truth:** `src/profile/builder.py::detect_subvertical`
- **Pinning tests:** `tests/test_s6_5_t2_subvertical_classifier.py` gap-threshold tests
- **Revisit trigger:** KI-NEW-F — once real beta-merchant subvertical mix data is available, build a confusion matrix (predicted subvertical vs. founder-confirmed-truth subvertical) and recalibrate the leader/runner-ratio thresholds against false-positive / false-negative tradeoffs.

---

## 9. Seasonality calendar windows

### D-S6.5-19 — Five named seasonality windows (Q3 verbatim)

- **Status:** active
- **Date locked:** 2026-05-17 (founder Q3 — accept DS architect calendar verbatim)
- **Decision:** Exactly 5 named windows in `config/seasonality_calendars.yaml`:
  - BFCM_tail: 11-20 → 12-05 (both verticals; `valid_for_year: 2026`)
  - January_resolution: 01-01 → 01-21 (supplements primary; beauty minor)
  - Mothers_Day: 05-01 → 05-12 (beauty)
  - Back_to_school: 08-15 → 09-05 (mixed/personal_care)
  - Summer_skin: 06-01 → 08-01 (beauty/skincare)
- **Why:** Conjectural annotations — the DS architect's plausibility judgment on which seasonality moments matter for DTC beauty/supplements, not empirical validation against this engine's data or external benchmarks. The five named windows cover the high-leverage DTC moments operators typically reference (BFCM, New Year, Mother's Day, Back-to-school, Summer skin); they do NOT come from a measured study of conversion-rate lift inside each window. The "accept verbatim" framing in earlier rounds overstated their evidence basis.
- **Source-of-truth:** `config/seasonality_calendars.yaml`
- **Pinning tests:** `tests/test_s6_5_t3_cadence_seasonality.py` window-presence + YAML schema tests
- **Revisit trigger:** KI-NEW-A — validate the five named windows against Phase 9 outcome data. Add windows whose realized-outcome lift is consistently meaningful; demote / remove windows whose claimed seasonality is not visible in real beta data.

### D-S6.5-20 — Seasonality is annotation-only, never a revenue multiplier

- **Status:** active
- **Decision:** `SeasonalityContext.expected_lift_range` is always `[low, high]` (never a point). `SeasonalityContext` carries NO `revenue_multiplier`, `p_value_adjust`, `lift_multiplier`, or `scale_factor` field. Surfaced as merchant context only; NEVER consumed as a numerical scalar in revenue, p-value, or slate-ordering equations.
- **Why:** Part III §8 discipline. Treating heuristic seasonality estimates as exact multipliers would inject fabricated numerics into engine output. The range tells merchants what to expect; the engine doesn't pretend to predict the exact effect.
- **Source-of-truth:** `src/profile/types.py::SeasonalityContext` (typed dataclass with no multiplier field)
- **Pinning tests:** `tests/test_s6_5_t3_cadence_seasonality.py` no-multiplier-field test (asserts the negative)

---

## 10. Deferred decisions (consciously-locked-as-deferred)

### D-S6.5-21 — Subscription-led slate-ordering deferred to S6-T3 (Q5)

- **Status:** deferred (target: S6-T3)
- **Date locked:** 2026-05-17 (founder Q5)
- **Decision:** Slate ordering by `business_model == SUBSCRIPTION_LED` (e.g., prioritize `replenishment_due` over `winback_dormant_cohort`) is deferred to S6-T3. S6.5 only DETECTS `business_model` and emits to profile.business_model; no consumer reads it for slate-ordering at S6.5 close.
- **Why:** Keeps S6.5 behavior surface to ONE flip (T5). Subscription-led ordering ships when `replenishment_due` lands (S6-T3) because that's the play that benefits most from the ordering swap.
- **Revisit at:** S6-T3 (current sprint, pending).
- **Source-of-truth:** Detection lives in `src/profile/builder.py::detect_business_model`; consumer wiring will land in S6-T3.

### D-S6-6 — KI-27 (empty_bottle.vertical_applicable expansion to supplements) stays accepted

- **Status:** deferred (revisit when supplements coverage reaches 100% or founder confirms otherwise)
- **Date locked:** 2026-05-18 (S6-T2 close)
- **Decision:** `play_registry::PLAYS["empty_bottle"].vertical_applicable` stays `frozenset({"beauty", "mixed"})`. NOT expanded to include supplements at S6-T2 close.
- **Why:** S6-T2 supplements parser shipped at 5/10 G-1 SKU coverage. Expanding `vertical_applicable` would silently skip half the supplements catalog from `empty_bottle` audience generation — partial-coverage behavior the engine should refuse. Real path to 100% coverage likely needs Shopify product-metadata integration (post-beta).
- **Revisit trigger:** Either (a) founder confirms expansion despite partial coverage, or (b) supplements coverage reaches 100% via a weight-to-serving conversion design.
- **Source-of-truth:** `src/play_registry.py::PLAYS["empty_bottle"].vertical_applicable`; `KNOWN_ISSUES.md` KI-27

### D-S6.5-22 — Per-play audience floors authored only for active builders

- **Status:** active discipline (not just deferred — active rule)
- **Decision:** Per-(play × vertical × subvertical × stage) audience floor cells in `gate_calibration.yaml` are authored ONLY for plays that have shipped a profile-aware audience builder (currently just `winback_dormant_cohort`). All other plays consume `_default_by_stage` until each gets a profile-aware builder.
- **Why:** Honors S7.5 discipline — don't invent per-cell numbers we can't defend. Padding 14 plays × 10 subverticals × 4 stages = ~560 cells with heuristic_unvalidated guesses is the S7.5 anti-pattern. Per-play cells land when each play's builder ships.
- **Revisit trigger:** Each Tier-B builder ticket (S6-T3 replenishment_due; S7-T1 discount_hygiene; S7-T2 journey_first_to_second; S7-T3 aov_bundle) adds its play's per-subvertical row.
- **Source-of-truth:** `config/gate_calibration.yaml` (the missing cells are intentional; `gate_calibration_default_floor_used` provenance fire makes the fallback auditable).

---

---

## 11. Agent handoff + artifact architecture (S13.7)

### D-S13.7-1 — Audience customer_id resolver (`src/audience_resolver.py`)

- **Status:** active (LOCKED)
- **Date locked:** 2026-06-01 (S13.7-T1; DS end-to-end-flow-readiness §Critical gap 1 + DS R4)
- **Decision:** For each recommended PlayCard (in `recommendations` + `recommended_experiments`), the engine materializes `data/<store_id>/runs/<run_id>/audiences/<audience_definition_id>.csv` with columns `customer_id`, `aov_individual`, `predicted_segment`, `rank_score`. SUBSTRATE_REFUSED path: always writes empty CSV with header row — never silent absence (per DS R4). `src/segments.py` hard-retired; legacy `segments/*.csv` path removed.
- **Why:** `PlayCard.audience_definition_id` must produce a concrete customer list operators can upload to Klaviyo post-approval. Legacy `segments/*.csv` covered only hardcoded segments and was incompatible with v2 ML-ranked audiences. The empty-CSV-on-refused path preserves the artifact-manifest contract: every recommended PlayCard has a corresponding CSV path even when substrate scores are unavailable.
- **Source-of-truth:** `src/audience_resolver.py::materialize_audience_csvs`; `src/main.py` call site (after `write_immutable_snapshot`, before `_emit_substrate_events`); `src/segments.py` (raises `NotImplementedError` on import — retired).
- **Override mechanism:** Structural lock; column schema and path template are the v2 audience handoff contract.
- **Pinning tests:** `tests/test_s13_7_t1_audience_resolver.py` (6 tests); `tests/test_null_reason_registry.py` (asserts `CustomerIdsNullReason` EXISTS).
- **Safe to adjust?** Column additions are additive. Path template change requires operator tooling update. `aov_individual = 0.0` is a known gap (parquet schema v1 limitation); tracked in T1 summary.
- **Cross-link:** `agent_outputs/code-refactor-engineer-s13.7-t1-summary.md`; `agent_outputs/ds-architect-end-to-end-flow-readiness.md` §Critical gap 1 + §5; `docs/DECISIONS.md::D-S13.7-5`.

### D-S13.7-2 — Per-run `manifest.json` at `data/<store_id>/runs/<run_id>/manifest.json`

- **Status:** active (LOCKED)
- **Date locked:** 2026-06-01 (S13.7-T2; DS end-to-end-flow-readiness §Critical gap 3)
- **Decision:** `src/run_manifest.py::write_run_manifest` writes a `manifest.json` per engine run enumerating: `engine_run.json` path, audience CSVs (with materialization status per `audience_definition_id`), parquet artifacts (glob), retention curves path, retention metadata. Agents scan one file to find all artifacts. `audience_materialization_status: "SUPPRESSED_SUBSTRATE_REFUSED"` annotated for refused substrates.
- **Why:** Without a manifest, agent builders must discover artifacts by convention (knowing the path template) or by walking the run directory. A single manifest file closes the discovery gap and makes the status of each audience CSV legible without opening it.
- **Source-of-truth:** `src/run_manifest.py::write_run_manifest`; `src/main.py` call site (immediately after `materialize_audience_csvs`).
- **Override mechanism:** Structural lock; manifest schema is the agent handoff contract. Non-fatal on write failure (try/except, does not abort run).
- **Pinning tests:** `tests/test_s13_7_t2_manifest.py` (7 tests); `tests/test_s13_7_t2_schema_generator.py` (6 tests).
- **Safe to adjust?** Adding manifest keys is additive. Removing or renaming existing keys requires agent tooling update.
- **Cross-link:** `agent_outputs/code-refactor-engineer-s13.7-t2-summary.md`; `agent_outputs/ds-architect-end-to-end-flow-readiness.md` §Critical gap 3; `schemas/engine_run.v2.json` (generated schema artifact shipped at T2).

### D-S13.7-3 — `docs/mechanism_contract.md` is the DS-locked narration-agent spec

- **Status:** active (LOCKED)
- **Date locked:** 2026-06-01 (S13.7-T3; DS adjudication #3 2026-05-30; D-S13.6-4)
- **Decision:** `docs/mechanism_contract.md` is the single file that narration agents and assembly agents code against to understand the meaning and parameter shape of every `MechanismType` value. All 10 `MechanismType` members are specified with their `parameters` dict keys, value types, and implementation notes (including `None`-valued keys where the decide-seam does not yet populate the per-merchant source). Changes to this file require DS review + `src/engine_run.py` version bump.
- **Why:** Typed enum atoms (`MechanismType`) let narration agents branch on mechanism type without string-matching. Without the contract doc, agents must reverse-engineer parameter shapes from `src/decide.py::_parameters_for_mechanism` source code, coupling agent development to engine internals. The doc decouples the two surfaces.
- **Source-of-truth:** `docs/mechanism_contract.md`; `src/engine_run.py::MechanismType` (10-member closed enum); `src/decide.py::_parameters_for_mechanism` (producer).
- **Override mechanism:** DS review + engine_run.py version bump required for any change to enum members or parameter shapes. Doc-only clarifications (implementation notes, examples) require no version bump.
- **Pinning tests:** `tests/test_s13_6_t6_mechanism_intent_atom.py` (28 tests pin the `MechanismType` closed enum and `MechanismIntent` shape).
- **Safe to adjust?** Adding a new `MechanismType` member requires: (a) add enum member, (b) add `_parameters_for_mechanism` case, (c) update `docs/mechanism_contract.md`, (d) version bump. Renaming or removing members is structural.
- **Cross-link:** `agent_outputs/code-refactor-engineer-s13.7-t3-summary.md`; `docs/DECISIONS.md::D-S13.6-4` (origin of `MechanismType` closed enum).

### D-S13.7-4 — Deferred null-reason enums + dead-code sweep (KI-NEW-AA closed)

- **Status:** active (LOCKED)
- **Date locked:** 2026-06-01 (S13.7-T7b; KI-NEW-AA, KI-NEW-AB)
- **Decision:** Four deferred items from S13.6-T7a now resolved at S13.7-T7b:
  1. `StoreProfileNullReason` (2 members: `PROFILE_NOT_LOADED`, `ONBOARDING_INCOMPLETE`) declared; `EngineRun.store_profile_null_reason: Optional[StoreProfileNullReason]` paired field added (additive, v2.x.x). Wired at the `ENGINE_V2_STORE_PROFILE` exception path in `src/main.py`. KI-NEW-AA closed.
  2. `ModelCardAbsenceReason` (3 members: `SUBSTRATE_NOT_RUN`, `SUBSTRATE_REFUSED`, `INSUFFICIENT_DATA`) declared as agent-reference vocabulary — no paired EngineRun field (dict key absence is self-documenting per DS T7b retraction).
  3. `CohortDiagnosticsAbsenceReason` (2 members: `INSUFFICIENT_COHORT_DEPTH`, `SUBSTRATE_REFUSED`) declared as agent-reference vocabulary — no paired EngineRun field (same pattern as ModelCardAbsenceReason).
  4. `_surface_mechanism_for_play` dead code deleted from `src/decide.py` (zero call sites confirmed by grep; KI-NEW-AB C2 closed). `targeting_non_causal_prior` cleanup (KI-NEW-AB C1) deferred to S14 — active call sites + pinned test assertions remain.
- **Why:** RULE A (D-S13-5 / D-S13.6-5) requires that Optional fields under default-ON flags pair with null-reason enums. `store_profile` is gated by `ENGINE_V2_STORE_PROFILE` which defaults ON — narration agents seeing `store_profile=None` needed a typed reason. The dict-absence-reason vocabulary enums (`ModelCardAbsenceReason`, `CohortDiagnosticsAbsenceReason`) provide agent-reference vocabulary without introducing misleading paired fields on dict slots where key absence is the canonical signal.
- **Source-of-truth:** `src/engine_run.py::StoreProfileNullReason`, `ModelCardAbsenceReason`, `CohortDiagnosticsAbsenceReason`, `EngineRun.store_profile_null_reason`; `src/main.py` (wiring on exception path); `src/decide.py` (`_surface_mechanism_for_play` deletion block).
- **Override mechanism:** Adding enum members is additive within v2.x.x. Removing or renaming requires DS sign-off. `ONBOARDING_INCOMPLETE` is forward-compat and not yet emitted by any producer (TODO(S14)).
- **Pinning tests:** `tests/test_s13_7_t7b_deferred_null_reasons.py` (7 passed, 1 skipped); `tests/test_null_reason_registry.py` (flipped 3 deferred assertions to shipped).
- **Safe to adjust?** Adding enum members is additive. `ONBOARDING_INCOMPLETE` wiring to a producer (S14) is the next step.
- **Cross-link:** `agent_outputs/code-refactor-engineer-s13.7-t7b-summary.md`; `docs/DECISIONS.md::D-S13-5` (RULE A origin); `KNOWN_ISSUES.md::KI-NEW-AA` (RESOLVED); `KNOWN_ISSUES.md::KI-NEW-AB` (partial — C2 closed, C1 deferred S14).

### D-S13.7-5 — Engine handoff posture: immutable runs, filesystem-only

- **Status:** active (LOCKED)
- **Date locked:** 2026-06-01 (S13.7-T4 sprint close; DS end-to-end-flow-readiness §founder recommendation #6)
- **Decision:** The engine writes to `data/<store_id>/runs/<run_id>/`. Agents read from that directory. No Postgres / API layer between engine and agents through synthetic validation (per DS founder recommendation). This posture is locked through S14 private beta. Post-S14 (AWS migration), storage backend swaps via the already-abstracted substrate API without engine changes.
- **Why:** A filesystem-only handoff is the simplest path to end-to-end synthetic validation. An API layer between engine and agents would require spec, auth, and test infrastructure that adds no decision-engine value before real merchants are onboarded. The substrate API abstraction (`open_memory`, `append_event`, `write_immutable_snapshot`) already isolates the storage concern; AWS migration is the right moment to introduce Postgres/S3.
- **Source-of-truth:** `src/run_manifest.py` (manifest at run dir); `src/audience_resolver.py` (audience CSVs at run dir); `PRODUCT.md §8` (Approval-State Seam).
- **Override mechanism:** AWS migration when it lands. Engine changes are abstraction-layer swaps, not architecture changes.
- **Pinning tests:** None beyond the manifest and resolver tests. Structural posture lock.
- **Safe to adjust?** Post-S14 AWS migration is the designed override path. Not a value to tune before then.
- **Cross-link:** `agent_outputs/ds-architect-end-to-end-flow-readiness.md` §founder recommendation #6; `PRODUCT.md §8` (Approval-State Seam); `docs/DECISIONS.md::D-S13.7-1` (audience resolver); `docs/DECISIONS.md::D-S13.7-2` (manifest.json).

### D-S14-1 — Evidence Layer locks (L-EV-1..20) + the 2.1.0 additive schema bump

- **Status:** active (LOCKED)
- **Date locked:** 2026-06-02/03 (Evidence Layer spec DS-defined 2026-06-02, founder-ratified; the `Audience.descriptive_distribution` 2.1.0 bump FOUNDER-AUTHORIZED 2026-06-02; RFM `segment_distribution` shipped 2026-06-03)
- **Decision:** Two settled bodies of work, locked together at the S-FE handoff-layer turn:
  1. **The Evidence Layer is a first-class spec** (`docs/evidence_layer.md`): the closed 9-member set (M1–M9), each bound to a frozen typed field; **visualization is a member, not a bolt-on** (renders an already-typed series — no chart-spec, no PNG, no invented series); one unified SHOWN / SHOWN-WITH-CAVEAT / SUPPRESSED state across number + prose + viz; the tier selects membership, the four gates select existence/lane; assembly seam = Narration MCP authors the claim projection, Frontend authors the visual projection, the engine emits atoms only. Locks **L-EV-1..12** (the consumer-side-view frame, assemblable from v2.0.0 convention-only) + **L-EV-13..20** (the descriptive/inferential frame governing viz gating; the refused-data posture — REFUSED-for-data-integrity SUPPRESSES the descriptive series, REFUSED-for-horizon/precision shows the observed series + suppresses only the inferential overlay; the dashboard boundary "what decision does this pixel justify?"; the per-mechanism selection-map architecture; and the `DescriptiveDistribution` primitive + descriptive-only gating).
  2. **The schema bumped 2.0.0 → 2.1.0, additive** (the v2.0.0 freeze holds — additive OK, breaking → 3.0.0): `Audience.descriptive_distribution` (`DescriptiveDistribution` atom + `DistributionKind` closed 4-member enum + `DescriptiveDistributionSuppressionReason` closed 3-member enum) per **L-EV-19/20**, and RFM `ModelCard.segment_distribution` (`SegmentBand` aggregate bands + `RfmSegmentDistributionSuppressionReason` closed 2-member enum) per **L-EV-17/18**. The DistributionKind / SegmentBand closed sets and the suppression-reason enums are closed-set locks; both new surfaces are descriptive-only (count/share axis, NO dollar/lift/projected overlay — an inferential overlay is a REJECT-class breach per L-EV-6/20).
- **Why:** "The evidence layer" was used informally but never defined as a planned artifact; the spec names it, makes viz a member under one suppression discipline, and closes the laundering paths (a descriptive series must never be narrated as a forward claim). The two additive fields unblock the distributional-play and RFM-segment charts that were under-served by generic-scalar members — the blocker was a discarded builder-computed series (L-EV-18), not a missing gate, so no gate was relaxed.
- **Source-of-truth:** `docs/evidence_layer.md` (§§1–8 + the L-EV-1..20 lock table); `src/engine_run.py` (`DescriptiveDistribution`, `DistributionKind`, `DescriptiveDistributionSuppressionReason`, `Audience.descriptive_distribution`, `schema_version="2.1.0"`); `src/predictive/model_card.py` (`SegmentBand`, `RfmSegmentDistributionSuppressionReason`, `ModelCard.segment_distribution`); `schemas/engine_run.v2.json` (52 $defs).
- **Override mechanism:** Adding members to the closed enums or fields is additive within 2.x. Removing/renaming members, or adding a dollar/lift surface to a descriptive viz, requires DS sign-off (the latter is a decision-integrity breach). The Evidence Layer membership (9 members) is closed — a new member requires DS re-review.
- **Pinning tests:** `tests/test_s_fe_descriptive_distribution.py` (22 tests; descriptive-only guard, closed-set enums, binning + suppression); `tests/test_s_fe_rfm_segment_distribution.py` (11 tests; aggregate-only shape, VALIDATED/PROVISIONAL gate, RULE-A suppression); `tests/test_s13_6_t5_schema_version_2_0_0.py` (version literals updated to 2.1.0; CHANGELOG anchor preserved).
- **Safe to adjust?** Additive enum/field changes are cheap (no fixture re-pin — `briefing.html` does not consume either field; the synthetic `engine_run.json` SHAs are documentation-only per `pinned_sha_ledger.json::engine_run_json_sha_caveat`). Removing the descriptive-only constraint is a structural decision-integrity change.
- **Cross-link:** `docs/evidence_layer.md`; `agent_outputs/code-refactor-engineer-s-fe-descriptive-distribution-summary.md`; `agent_outputs/code-refactor-engineer-s-fe-rfm-segment-distribution-summary.md`; `KNOWN_ISSUES.md::KI-NEW-AE` (Considered-lane limitation) + `KI-NEW-AF` (stale RFM-flag test); `docs/DECISIONS.md::D-S13-2` (modal floor, carried by M5) + `D-S12-1` (`cohort_diagnostics` slot, M7's source).

---

## Conventions

**ID format.** `D-<sprint>-<n>` where `<sprint>` is the sprint that locked the decision (S6, S6.5, S7.5, etc) and `<n>` is the per-sprint sequence number. IDs are stable across edits.

**Source-of-truth field.** Always a file path or YAML path. Where a decision is enforced in multiple places, list all of them.

**Override mechanism field.** Explicit instructions for "if you want to change this, do X." Includes env vars, YAML edits, code constants, and "would require fixture re-pin" tags.

**Pinning tests field.** Tests that will fail if the value is silently changed. Future agents grep for these to understand blast radius.

**Safe to adjust field.** Either "cheap (no fixture impact)" or "requires fixture re-pin" or "structural change (multiple code surfaces)." Helps the agent scope the change before starting.

**Date format.** ISO-8601 (YYYY-MM-DD).

---

Last updated: 2026-06-03 (S-FE handoff-layer turn: D-S14-1 NEW (LOCKED) — Evidence Layer locks L-EV-1..20 (the closed 9-member set + viz-as-member + descriptive/inferential frame + refused-data posture + dashboard boundary + per-mechanism selection map) consolidated from the L-VIZ verdict + handoff DS locks, AND the additive schema bump 2.0.0 → 2.1.0 (Audience.descriptive_distribution + RFM ModelCard.segment_distribution; the DistributionKind/SegmentBand closed sets + suppression-reason enum locks); cited to docs/evidence_layer.md + the two S-FE summaries; v2.0.0 freeze intact (additive OK, breaking → 3.0.0). Earlier 2026-06-01 (S13.7-T4 sprint close: D-S13.7-1 through D-S13.7-5 NEW (LOCKED) — audience resolver / manifest.json / mechanism_contract.md / deferred null-reasons (KI-NEW-AA closed) / engine handoff posture. Earlier 2026-06-01 (S13.6-T8 sprint close: D-S13.6-1 through D-S13.6-5 NEW (LOCKED) — Pivot 2 ratification / schema authority / NonLiftAtom / MechanismType enum / RULE A flag-aware softening. Earlier 2026-06-01 S13.6-T7a: D-S13-5 NEW (LOCKED) — RULE A flag-aware absence-of-data pattern + 3 closed-set null-reason enums (RevenueRangeSuppressionReason 9 members / MonthDeltaNullReason 5 members / PredictedSegmentNullReason 4 members) + 3 paired _null_reason fields (RevenueRange.suppression_reason / EngineRun.month_2_delta_null_reason / PredictedSegment.segment_name_null_reason); DS adjudication 2026-06-01 retracts/revises original §(e) triage; founder approved 2026-06-01; T7 split into T7a (this entry) + T7b (substrate refusal-card audit + StoreProfileNullReason — DEFERRED to S13.7); pinned by tests/test_s13_6_t7a_no_silent_nulls.py AST sweep + per-row strict invariants. Earlier 2026-05-29 (S13 close: D-S13-1 NEW (LOCKED) — Q-S13-4 LOCK; ML-fit ReasonCodes emit ONLY on `model_card_ref.fit_warnings`, NEVER on `RejectedPlay.reason_code`; pinned by `tests/test_s13_ml_fit_never_demotes.py` 5-fixture runtime + month-2 extension + AST-aware `tests/test_reason_code_precedence_invariant.py`. D-S13-2 NEW (LOCKED) — modal-segment stability floor: `predicted_segment.segment_name = None` when `n_audience<50` OR `audience_modal_share<0.30`; audit fields uncensored. D-S13-3 NEW (LOCKED) — lineage-change constraint for month_2_delta: 21-day floor + segment_shifts suppression on audience_definition_version bump. D-S13-4 NEW (LOCKED) — `fit_warnings` shape: `List[str]` with `"{LEVEL}:{substrate}"` grammar; 3 closed LEVELS (PROVISIONAL_SELECTED, MODEL_FIT_INSUFFICIENT_DATA, MODEL_FIT_REFUSED). Earlier 2026-05-28 (S12 close: D-S12-1 NEW (LOCKED) — `cohort_diagnostics` slot architecturally separate from `predictive_models`; per DS S12 plan review §C; pinned at S12-T2/T2.5; first occupant retention). Earlier 2026-05-20 (S7 D-FLOOR locks: D-FLOOR-discount_dependency_hygiene NEW (LOCKED) + D-FLOOR-aov_lift_via_threshold_bundle NEW (LOCKED); both beauty-only, both DS-tightened ~50% from winback-mirror per ecommerce-ds-architect priors-validation memo 2026-05-20; cross-linked to KI-NEW-B (audience-floor recalibration sweep); D-FLOOR-aov_lift_via_threshold_bundle additionally cross-linked to KI-NEW-J (supplements elicited_expert→validated_external pathway). Floor cells land at S7-T1 / S7-T3 builder tickets per S6-T3.5 Commit B precedent. Earlier 2026-05-19 (S6-T3.5 Commit B): D-FLOOR-replenishment_due NEW (LOCKED); D-S6-3 envelope citation refreshed to `replenishment_due.base_rate.beauty [p10=0.0120, p90=0.0430]` superseding the bundle_value citation. Earlier 2026-05-19: S6-T3.x re-key: D-S6-2 superseded by D-S6-2.1; framing demoted on D-S6.5-12, D-S6.5-17, D-S6.5-18, D-S6.5-19, D-S7.5-3 with `Revisit trigger` lines added pointing to KI-NEW-A..F).
