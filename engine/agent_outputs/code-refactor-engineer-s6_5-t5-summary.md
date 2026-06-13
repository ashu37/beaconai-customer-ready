# S6.5-T5 Summary + Sprint 6.5 Closeout

**Date:** 2026-05-18
**Author:** code-refactor-engineer
**Status:** Sprint 6.5 closed. Engine ready for Sprint 6-T2 resume.
**Suite:** 1377 passed / 14 skipped / 0 failed (exceeds IM plan target ~1346).

---

## 1. Commit chain (chronological)

| Commit | Title | Scope |
|---|---|---|
| `f784ed2` | S6.5-T4.x: regen synthetic Beauty fixtures with fresh inventory clock + dormant-cohort injection | New synthetic Beauty winback-activation scenario CSVs + scenarios YAML entry + generator addition. No engine code change. |
| `4a20808` | KI-31 + KI-32 fixes (separately bundled mid-T4.x lane) | Per founder direction; pre-T4.x.1. |
| `75bf273` | S6.5-T4.x.1: refresh healthy_beauty + supplements inventory clocks (Fix-11 rot class); KI-31/KI-32 | Refreshed 4 stale `*_inventory.csv` files whose `Updated At` columns had aged past the 7-day Fix-11 freshness gate. Orders CSVs byte-identical (seed-deterministic). |
| `cce4555` | S6.5-T4.y: wire build_store_profile into src/main.py pipeline pre-guardrails | 23-line `src/main.py` wiring patch. Flag-gated; still default OFF at T4.y close. Behavior change is engine_run.store_profile slot population under flag ON. |
| `28410fe` | S6.5-T4.y.1: remove stale VERTICAL_MODE=beauty from .env + fix conservative-broader band-check on lower side of boundary | Two-part atomic fix per founder direction. Part A: `.env` line 32 deletion (gitignored; local-filesystem only). Part B: symmetric `stage_boundary_uncertainty` provenance rule in `src/profile/builder.py::detect_business_stage`. |
| `8632285` | S6.5-T5: flip ENGINE_V2_STORE_PROFILE ON + atomic Beauty + supplements re-pin (closes Sprint 6.5) | Single atomic commit. `src/utils.py` flag flip + Beauty pinned slate regen + supplements G-1 sha re-affirm + new T5 test suite + 2 mechanical knock-on test updates (T1 flag-OFF assertion retirement; determinism nested-path normalization). |

---

## 2. Per-commit patch descriptions

### T4.x (`f784ed2`)
Added a new synthetic scenario `winback_activation_beauty_240d` covering the dormant-cohort injection envelope the founder approved for the activation moment. Files: `scripts/generate_synthetic_shopify.py` (new SCENARIO_GENERATORS entry), `tests/fixtures/synthetic_scenarios.yaml`, `tests/fixtures/synthetic/winback_activation_beauty_240d_orders.csv`, `tests/fixtures/synthetic/winback_activation_beauty_240d_inventory.csv`. No engine code change.

### T4.x.1 (`75bf273`)
Refreshed the `Updated At` column on 4 inventory CSVs whose mtimes had aged past the Fix-11 7-day freshness gate (`healthy_beauty_240d`, `healthy_beauty_low_inventory_240d`, `healthy_supplements_240d`, `supplement_replenishment_240d`). Orders CSVs byte-identical; only the inventory CSVs moved bytes. KI-31/KI-32 bundled per founder direction. No engine code change.

### T4.y (`cce4555`)
Added a 23-line wiring patch in `src/main.py` that calls `build_store_profile(g, cfg, store_id=brand)` inside the existing EngineRun construction try-block, behind `cfg.get("ENGINE_V2_STORE_PROFILE", False)`. The profile populates `EngineRun.store_profile` and is consumed downstream by guardrails (materiality floor), decide.py (window corroboration), and the audience builder (winback floor) — all per the T4 consumer wiring shipped earlier. Flag default still OFF at T4.y close.

### T4.y.1 (`28410fe`)
**Part A** removed the line `VERTICAL_MODE=beauty` from `.env` (line 32; gitignored, so local-filesystem only). Verified post-removal: Beauty fixture detects `vertical=beauty (HIGH)` from data alone; supplements detects `vertical=supplements (HIGH), subvertical=functional (LOW), business_model=SUBSCRIPTION_LED`.

**Part B** fixed an asymmetry in `src/profile/builder.py::detect_business_stage`. Per founder Q2 contract, the `stage_boundary_uncertainty` provenance rule must fire whenever GMV is within ±25% of ANY boundary (symmetric, both sides). The prior implementation only fired the rule inside the `broader != detected_stage` downgrade branch, so a STARTUP store at $496K had `uncertainty=HIGH` on the typed object but no dedicated `stage_boundary_uncertainty` provenance entry. The fix records both flags explicitly on the rule payload and keeps `conservative_floor_applied` separate (True only when a smaller-band downgrade is available; False at the STARTUP floor).

### T5 (`8632285`)
**Atomic flip** — `src/utils.py` `ENGINE_V2_STORE_PROFILE` default OFF -> ON.
**Beauty pinned slate regen** — `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` re-pinned to sha256 `cacb6691b387b1770502a841f9c224d1fe76e5bc3be58802eafc8c5d0fa95269`. Recommended Now slate grows from 1 card to 2 (winback_dormant_cohort added at top with Klaviyo prior anchoring posterior).
**Supplements G-1 sha re-affirm** — briefing.html byte-identical to S5-T3 pin; comment expanded to document the engine_run.json-only delta.
**New test file** — `tests/test_s6_5_t5_atomic_repin.py` (14 tests): 12 IM-plan-§S6.5-T5 hard-stops verbatim + 2 activation-moment invariants.
**Knock-on updates** — `tests/test_s6_5_t1_store_profile.py` flag-OFF assertion inverted (was T1 contract, retired at T5); `tests/test_determinism_cross_run.py` extends comparator with nested-path normalization for `store_profile.provenance.profiled_at`.

---

## 3. Envelope reconciliation table

### Beauty (`healthy_beauty_240d`) — ACTIVATION MOMENT

| Check | Pre-T5 | Post-T5 (flag ON) |
|---|---|---|
| Recommended Now count | 1 (`first_to_second_purchase`) | **2** (`winback_dormant_cohort`, `first_to_second_purchase`) |
| Recommended Experiments count | 2 (`discount_hygiene`, `bestseller_amplify`) | 2 (unchanged) |
| Considered count | 4 (incl. winback variants) | 4 (winback_dormant_cohort REMOVED — promoted; others unchanged) |
| Watching count | 1 (`aov`) | 1 (unchanged) |
| `store_profile.taxonomy.vertical` | n/a | `beauty` (HIGH) |
| `store_profile.taxonomy.subvertical` | n/a | `skincare` (HIGH) |
| `store_profile.business_stage.detected_stage` | n/a | `GROWTH` |
| `store_profile.business_stage.uncertainty` | n/a | `LOW` |
| `store_profile.business_model.model` | n/a | `ONE_TIME_LED` |
| `store_profile.gate_calibration.audience_floor_by_play_id.winback_dormant_cohort` | n/a (legacy 500) | **200** |
| `store_profile.gate_calibration.materiality_floor_usd` | n/a (legacy $4500) | **$2000** |
| Winback cohort size | 356 (was BELOW legacy 500 floor; routed to Considered) | 356 (PASSES new 200 floor; routed to Recommended Now) |
| Winback `revenue_range.p50` | n/a | **$1686.50** (inside Klaviyo prior `[range_p10, range_p90]` envelope) |
| Winback `revenue_range.p10` / `p90` | n/a | $843.25 / $2951.37 |
| Klaviyo prior activated | NO (suppressed by floor) | **YES** — `prior_value=0.08, validated_external, observational, prior_effective_n=30, pseudo_n=20` |
| Posterior numerics | n/a | `posterior_value=0.08 (prior_dominant)` — `n_observed=0` so prior dominates (effective_pseudo_n via pseudo_n_default.growth cell) |
| `profile_field_ref` on winback audience_size driver | n/a | `gate_calibration.audience_floors.winback_dormant_cohort.beauty.skincare.growth` |
| Pinned briefing.html sha256 | (previous) | **`cacb6691b387b1770502a841f9c224d1fe76e5bc3be58802eafc8c5d0fa95269`** |

**12 envelope checks all PASS.** Klaviyo `validated_external` Beauty winback prior activated end-to-end for the FIRST TIME.

### Supplements G-1 (`healthy_supplements_240d`) — CLEAN POST-T4.y.1

| Check | Pre-T5 | Post-T5 (flag ON) |
|---|---|---|
| Recommended Now count | 0 | **0** (heuristic_unvalidated prior suppresses) |
| Recommended Experiments count | 0 | 0 (unchanged) |
| Considered count | 6 | 6 (unchanged) |
| Watching count | 3 (`orders`, `net_sales`, `aov`) | 3 (unchanged) |
| `abstain.state` | `abstain_soft` | `abstain_soft` (unchanged) |
| `data_quality_flags` | `[metric_incoherent_for_cadence]` | `[metric_incoherent_for_cadence]` (unchanged) |
| `briefing_meta.vertical` | `supplements` | `supplements` (unchanged) |
| `store_profile.taxonomy.vertical` | n/a | `supplements` (HIGH) |
| `store_profile.taxonomy.subvertical` | n/a | `functional` (LOW) |
| `store_profile.taxonomy.override_disagrees` | n/a | `False` (detector and override agree) |
| `store_profile.business_stage.detected_stage` | n/a | `STARTUP` |
| `store_profile.business_stage.annualized_gmv_usd` | n/a | $496,383 (`l180_x2` method) |
| `store_profile.business_stage.uncertainty` | n/a | **`HIGH`** (T4.y.1 symmetric rule fires — within ±25% of $500K boundary) |
| `store_profile.business_stage.conservative_floor_applied` | n/a | `False` (no downgrade below STARTUP floor) |
| Provenance `stage_boundary_uncertainty` rule fires | n/a | **YES** (with `boundary=startup_growth`, `applied_stage=STARTUP`, `conservative_floor_applied=False`) |
| `store_profile.business_model.model` | n/a | `SUBSCRIPTION_LED` (subscription_fraction=0.973, HIGH confidence) |
| `store_profile.gate_calibration.audience_floor_by_play_id.winback_dormant_cohort` | n/a | **60** (STARTUP supplements cell) |
| `store_profile.gate_calibration.materiality_floor_usd` | n/a | **$800** (STARTUP) |
| `winback_dormant_cohort` lands in Recommended Now | NO | **NO** (S7.5-T3 refusal logic intact) |
| Pinned briefing.html sha256 | `01f5feff84491db331611b3cbcbd94247699d11544e659a20efe0b67bbfede95` | **`01f5feff84491db331611b3cbcbd94247699d11544e659a20efe0b67bbfede95`** (BYTE-IDENTICAL) |

The supplements sha is byte-identical because the `heuristic_unvalidated` supplements winback prior correctly suppresses any Recommended Now surfacing per S7.5-T3. The behavior delta under flag-ON is engine_run.json-only (`store_profile` slot now populated with full provenance).

### M0 legacy goldens (small_sm, mid_shopify, micro_coldstart)

All 3 byte-identical under flag-ON. Verified by re-running `tests/test_golden_diff.py` with `ENGINE_V2_STORE_PROFILE=true` forced. These fixtures hit STARTUP / data-depth-refused / insufficient-history branches; the profile activation does not surface new cards on the legacy `ENGINE_V2_SIZING=false` path.

---

## 4. Sha256 diff old -> new

| Fixture | Old sha256 | New sha256 | Delta |
|---|---|---|---|
| Beauty pinned slate | (previous pre-T5 pin) | `cacb6691b387b1770502a841f9c224d1fe76e5bc3be58802eafc8c5d0fa95269` | +1 Recommended Now card (winback_dormant_cohort) |
| Supplements G-1 | `01f5feff84491db331611b3cbcbd94247699d11544e659a20efe0b67bbfede95` | `01f5feff84491db331611b3cbcbd94247699d11544e659a20efe0b67bbfede95` | BYTE-IDENTICAL (delta is engine_run.json-only) |
| M0 small_sm | (unchanged) | (unchanged) | byte-identical |
| M0 mid_shopify | (unchanged) | (unchanged) | byte-identical |
| M0 micro_coldstart | (unchanged) | (unchanged) | byte-identical |

---

## 5. Posterior numerics with effective_pseudo_n derivation

Beauty winback `bayesian_blend(prior_value, pseudo_n, store_value, n_observed)`:

| Input | Value | Source |
|---|---|---|
| `prior_value` | 0.08 | `config/priors_sources/winback_21_45__base_rate__beauty.md` (Klaviyo `validated_external`, observational class, `prior_effective_n=30`) |
| `pseudo_n` | 20 | `store_profile.gate_calibration.pseudo_n_default = 20` (GROWTH stage cell in `gate_calibration.yaml`) |
| `store_value` | n/a (no outcome history yet) | `store_data_status=no_outcome_history`; `observed_k=0`, `observed_n=0` |
| `n_observed` | 0 | as above |

**Output:** `posterior_value = 0.08`, `posterior_ratio = prior_dominant`. The prior dominates because store has no outcome history (Phase 9 outcome loop will eventually shift this as `n_observed` accumulates).

**`effective_pseudo_n` derivation** (DS architect §2.8 + T4 contract): `effective_pseudo_n = pseudo_n × prior_validation_weight`. Klaviyo prior is `validated_external` so weight=1.0 → `effective_pseudo_n = 20`. The profile-derived `pseudo_n_default=20` (GROWTH stage) is LOWER than the legacy hardcoded 30, which is the documented "profile-lowers-not-raises invariant" from T4 — smaller `pseudo_n` lets store data move the posterior faster as outcome history flows.

---

## 6. Revenue range envelope check

Beauty winback `revenue_range`:

| Quantile | Value | Klaviyo prior envelope check |
|---|---|---|
| `p10` | $843.25 | inside envelope |
| `p50` | $1686.50 | **inside Klaviyo prior `[range_p10, range_p90]`** (the load-bearing envelope check) |
| `p90` | $2951.37 | inside envelope |
| `source` | `blend` | confirms posterior-blended (not raw store-observed) |
| `suppressed` | `False` | confirms the non-suppressed `BLEND` range from T4 wiring |

Drivers cite both `audience_size` (`profile_field_ref = gate_calibration.audience_floors.winback_dormant_cohort.beauty.skincare.growth`) and `aov` (`window=L56, value=$59.22`) plus the `blend_provenance` driver with `expected_calibration_path = phase_9_outcome_loop`.

---

## 7. 5 pinned-fixture status

| Fixture | Status under flag ON |
|---|---|
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | **RE-PINNED** to new sha (activation moment) |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | UNCHANGED (sha re-affirmed; byte-identical) |
| `tests/golden/small_sm/*` | UNCHANGED (M0 byte-identical) |
| `tests/golden/mid_shopify/*` | UNCHANGED (M0 byte-identical) |
| `tests/golden/micro_coldstart/*` | UNCHANGED (M0 byte-identical) |

---

## 8. 8 hard-stops confirmation

| # | Hard-stop | Status |
|---|---|---|
| 1 | Profile detection produces nonsense (e.g., Beauty as supplements) | PASS — Beauty detects as `beauty (HIGH)`, supplements as `supplements (HIGH)`. |
| 2 | Gate calibration produces an empty slate on Beauty | PASS — Beauty Recommended Now has 2 cards; experiments 2; considered 4; watching 1. |
| 3 | Beauty `business_stage.detected != GROWTH` | PASS — `detected_stage=GROWTH`, `uncertainty=LOW`. |
| 4 | Beauty `subvertical != skincare` with confidence < HIGH | PASS — `subvertical=skincare`, `subvertical_confidence=HIGH`. |
| 5 | Supplements winback lands in Recommended Now | PASS — supplements emits 0 Recommended Now (heuristic_unvalidated suppresses). |
| 6 | M0 goldens shift unexpectedly | PASS — `test_golden_diff.py` 3/3 pass under flag-ON. |
| 7 | business_model contradicts fixture patterns | PASS — supplements SUBSCRIPTION_LED (sub_fraction=0.973 HIGH); Beauty ONE_TIME_LED (no 3-order constant-gap customers in fixture). |
| 8 | Cell-lookup miss triggers default-fallback on Beauty/supplements winback | PASS — only `_default` play_id catch-all uses default; `winback_dormant_cohort.beauty.skincare.growth` and `.supplements.functional.startup` cells are populated. |

---

## 9. Cohort delta honest note (verbatim from founder)

> T4 §6.4 projected Beauty winback cohort=428; actual engine end-to-end output is 356. Posterior numerics still pass (revenue_range.p50=$1686.50 inside Klaviyo prior envelope). The discrepancy reflects a divergence between T4's audience-builder unit test config and the end-to-end engine's audience_definition_id resolution; investigate as KI-33 post-T5 if it matters.

---

## 10. Sprint 6.5 closeout statement

**Sprint 6.5 closed. Klaviyo validated_external Beauty winback prior activated on real fixture for the first time. Engine ready for Sprint 6-T2 resume.**

---

## 11. Invariants preserved

- D-5 / D-6 / D-8 / B-4 / B-5 intact.
- S-2..S-6 substrate write paths untouched.
- S7.5-T3 validated-vs-heuristic refusal logic UNCHANGED.
- M0 legacy goldens byte-identical.
- No new schema, no new flags, no new deps.
- Local CSV -> HTML briefing workflow preserved.
- No Shopify/Klaviyo production integrations introduced.
- No fake p-values, fake CIs, hardcoded effects, forced recommendations, or fake ML.

---

## 12. Suite reconciliation

| Phase | Count | Notes |
|---|---|---|
| Pre-T5 | 1363 passed / 14 skipped / 0 failed | T4.y.1 close baseline |
| T5 atomic landed (transient) | 1375 passed / 14 skipped / 2 failed | (1) T1 flag-OFF assertion needed inversion; (2) determinism comparator needed nested-path normalization for `profiled_at`. Both included in the same T5 atomic commit per Sprint 2 Risk #4 discipline (otherwise the commit breaks the suite). |
| T5 atomic commit (final) | **1377 passed / 14 skipped / 0 failed** | +14 from new `test_s6_5_t5_atomic_repin.py`; -2 -> +2 from the inverted/extended tests. |

Suite delta: +14 / +0 / +0 vs the pre-T5 baseline. Exceeds the IM plan target of ~1346.

---

## 13. Follow-up work (out of scope for S6.5)

- KI-33 (new): Beauty winback cohort 428-vs-356 divergence between T4 audience-builder unit test config and end-to-end engine's `audience_definition_id` resolution. Investigate post-T5 if it matters.
- Sprint 6-T2 (supplements parser; KI-18, KI-27): now unblocked; reads `profile.taxonomy.subvertical` for SKU-class assignment.
- S8 Play Library fold (post-beta): unify `routine_builder.metadata.audience_floor_by_vertical` (config/priors.yaml line 426) with `gate_calibration.yaml` per S6.5 R-X dual-source resolution.
- S10 (Phase 9 outcome loop): outcome-driven cell-by-cell floor recalibration; replaces every `heuristic_unvalidated` cell with measured posteriors.
- Fixture-rot harden (KI to file): `Updated At` freshness gates should compute against fixture mtime or anchor_date, not wall-clock, to eliminate the time-bomb pattern that T4.x.1 spent a commit repairing.

## Backfill from memory.md (migration trim 2026-05-25)

## Sprint 6.5 Ticket T5 closeout (2026-05-18)

**Status:** Complete. Sprint 6.5 closed. Atomic flag-flip + Beauty
pinned slate re-pin + supplements G-1 sha re-affirm in ONE commit
(Sprint 2 Risk #4 discipline).

**Commit:** `8632285 S6.5-T5: flip ENGINE_V2_STORE_PROFILE ON +
atomic Beauty + supplements re-pin (closes Sprint 6.5)`

**Activation moment:** The Klaviyo `validated_external` Beauty
winback prior anchors a posterior on a real fixture for the FIRST
TIME. `winback_dormant_cohort` (cohort=356) lands in Recommended Now
with `revenue_range.p50=$1686.50` inside the Klaviyo prior envelope.

**Files in the atomic commit:**
- `src/utils.py` — `ENGINE_V2_STORE_PROFILE` default OFF -> ON.
- `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`
  — pinned slate regen. New sha256
  `cacb6691b387b1770502a841f9c224d1fe76e5bc3be58802eafc8c5d0fa95269`.
- `tests/test_slate_regression_beauty_brand.py` — EXPECTED_RECOMMENDED_*
  bumped to {winback_dormant_cohort, first_to_second_purchase}; count=2.
- `tests/test_slate_regression_supplements_brand.py` — PINNED_SHA256
  re-affirmed (byte-identical to S5-T3:
  `01f5feff84491db331611b3cbcbd94247699d11544e659a20efe0b67bbfede95`);
  comment updated to document the engine_run.json-only delta.
- `tests/test_s6_5_t5_atomic_repin.py` — **NEW**. 14 tests covering
  IM-plan §S6.5-T5 12 hard-stops verbatim + 2 activation-moment
  invariants.
- `tests/test_s6_5_t1_store_profile.py` — `test_engine_v2_store_profile_
  flag_default_off` renamed/inverted (`_on_at_t5` asserts `is True`).
- `tests/test_determinism_cross_run.py` — extends comparator with
  nested-path normalization for `store_profile.provenance.profiled_at`.

**Envelope reconciliation:**
- Beauty: 2 Recommended Now cards (winback_dormant_cohort,
  first_to_second_purchase) / 2 Experiments / 4 Considered / 1
  Watching. Klaviyo prior `0.08` × `pseudo_n=20` × `n_observed=0`
  posterior = `0.08` (prior_dominant). `audience_size=356`,
  `aov=$59.22` (L56), `p50=$1686.50`, `p10=$843.25`, `p90=$2951.37`
  all inside Klaviyo envelope. `profile_field_ref =
  gate_calibration.audience_floors.winback_dormant_cohort.beauty.
  skincare.growth`. `business_stage.detected=GROWTH` with
  `uncertainty=LOW`. `audience_floor=200, materiality=$2000`.
- Supplements: 0 Recommended Now / 0 Experiments / 6 Considered /
  3 Watching (UNCHANGED). store_profile populated:
  `vertical=supplements (HIGH), subvertical=functional (LOW),
  business_model=SUBSCRIPTION_LED (0.97 HIGH), business_stage.
  detected=STARTUP, uncertainty=HIGH (T4.y.1 symmetric rule fires at
  $496K within ±25% of $500K boundary), conservative_floor_applied=
  False (no downgrade below STARTUP)`. `audience_floor.winback=60`,
  `materiality=$800` (STARTUP cells).
- M0 goldens (small_sm, mid_shopify, micro_coldstart):
  byte-identical under flag-ON (verified by re-running
  `test_golden_diff.py` with `ENGINE_V2_STORE_PROFILE=true` forced).

**Honest cohort-delta note (verbatim from founder):** T4 §6.4 projected
Beauty winback cohort=428; actual engine end-to-end output is 356.
Posterior numerics still pass (revenue_range.p50=$1686.50 inside
Klaviyo prior envelope). The discrepancy reflects a divergence between
T4's audience-builder unit test config and the end-to-end engine's
audience_definition_id resolution; investigate as KI-33 post-T5 if it
matters.

**Suite:** 1377 passed / 14 skipped / 0 failed (exceeds IM plan
target of ~1346).

**8 hard-stops all PASS:** (1) Beauty detected as beauty,
supplements as supplements; (2) Beauty gate calibration non-empty;
(3) Beauty GROWTH; (4) Beauty skincare HIGH; (5) supplements winback
NOT in Recommended Now (heuristic_unvalidated suppresses);
(6) M0 goldens byte-identical; (7) business_model detection matches
fixture patterns; (8) no cell-lookup miss triggers default-fallback
on Beauty/supplements winback cell.

**Sprint 6.5 closeout statement:** Sprint 6.5 closed. Klaviyo
validated_external Beauty winback prior activated on real fixture
for the first time. Engine ready for Sprint 6-T2 resume.

---

# Sprint 7 — priors-wiring slice (2026-05-20)
