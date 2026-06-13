# S6.5-T3 — Cadence baseline + seasonality calendar lookup

**Owner:** code-refactor-engineer (Sprint 6.5, ticket T3)
**Date:** 2026-05-17
**Branch:** `post-6b-restructured-roadmap` (not pushed)
**Source contract:** [agent_outputs/implementation-manager-s6_5-store-profile-layer-plan.md](./implementation-manager-s6_5-store-profile-layer-plan.md) §S6.5-T3
**Predecessors:** [S6.5-T1](./code-refactor-engineer-s6_5-t1-summary.md), [S6.5-T2](./code-refactor-engineer-s6_5-t2-summary.md)
**Status:** Complete. Flag still default OFF. The 5 pinned fixtures byte-identical (no consumer reads `cadence` / `seasonality` in S6.5 until T4 wires gate calibration and T5 flips the flag).

---

## 1. Approved scope

Author `src/profile/cadence.py` + `src/profile/seasonality.py` +
`config/seasonality_calendars.yaml`; populate the T1-stub
`CadenceBaseline` and `SeasonalityContext` sub-dataclasses inside
`build_store_profile`. No consumer wiring at T3 — the values are
descriptive of the store; T4 will use them to derive
`gate_calibration` cells.

## 2. Cadence module (`src/profile/cadence.py`)

`compute_cadence_baseline(aligned, subvertical_sku_assignment) ->
CadenceBaseline`. Pure-pandas right-censored empirical median per
sub-vertical-tagged SKU class. D-6 invariant: no `lifelines` / `sklearn`
/ `statsmodels` / `implicit` / `lightfm` imports (test pins this).
K-M lifts the censored-customers contribution at S11.

Algorithm:

1. Tag each order line with a SKU class via the T2 token taxonomy
   (positive-score argmax; ties drop). `build_subvertical_sku_assignment`
   exposes `{title -> class}` for reuse from the builder.
2. Per customer × class: collect inter-purchase gaps in days
   (consecutive timestamps within the same class).
3. Customers with only 1 in-class purchase are right-censored and do
   NOT contribute to the empirical median.
4. Per class: ≥30 contributing customers → median(gaps) with
   `method="empirical_median"`; else `INSUFFICIENT_DATA` and no entry
   in `median_reorder_days_by_sku_class`.
5. `global_median_reorder_days` = pooled median across all gaps that
   contributed (else `None`).

## 3. Seasonality module (`src/profile/seasonality.py`)

`lookup_active_seasonality(run_date, vertical, subvertical) ->
SeasonalityContext`. Reads `config/seasonality_calendars.yaml`.
`mixed` / `other_refused` verticals short-circuit to
`detection_status="NOT_APPLICABLE"`. Per window:

- MM-DD inclusive window match (wrap-around supported).
- Optional `valid_for_year` guard (used by BFCM_tail per founder Q3).
- `applies_to` rows are `{vertical, subvertical}`; `subvertical: null`
  is a wildcard over the vertical.

Active matches return `(active_window_name, expected_lift_direction,
expected_lift_range, source_artifact, detection_status="ACTIVE")`.
`expected_lift_range` is **always** a `[low, high]` pair; the
descriptive `SeasonalityContext` dataclass carries NO
`revenue_multiplier` / `p_value_adjust` / `lift_multiplier` field
(test asserts the negative). Per Part III §8: annotations only,
never a numerical scalar in a revenue or significance equation.

## 4. Seasonality YAML (`config/seasonality_calendars.yaml`)

Founder Q3 (2026-05-17): exactly the 5 windows below, accepted
verbatim. Every window is tagged `validation_status:
heuristic_unvalidated`. Cell-by-cell validation lands post-beta.

| Window | start_md | end_md | applies_to | expected_lift_direction | expected_lift_range |
|---|---|---|---|---|---|
| BFCM_tail | 11-20 | 12-05 | beauty (all), supplements (all) — valid_for_year:2026 | + | [0.20, 0.60] |
| January_resolution | 01-01 | 01-21 | supplements (all + multivitamin + functional), beauty/skincare | + | [0.10, 0.30] |
| Mothers_Day | 05-01 | 05-12 | beauty (all + skincare + cosmetics) | + | [0.05, 0.20] |
| Back_to_school | 08-15 | 09-05 | beauty/personal_care, supplements/multivitamin | + | [0.05, 0.15] |
| Summer_skin | 06-01 | 08-01 | beauty/skincare | + | [0.05, 0.15] |

`source_artifact` for each window is a `config/priors_sources/seasonality/<name>.md` memo (heuristic rationale, not a measured estimate).

## 5. Builder wiring (`src/profile/builder.py`)

`build_store_profile` gained two private helpers:

- `_build_cadence(g, taxonomy, rules_fired)` — skipped (with
  provenance fire `cadence_skipped_unsupported_vertical`) when
  `taxonomy.vertical` is `mixed` / `other_refused`; otherwise loads
  the T2 taxonomy, builds the `{title -> class}` assignment, and
  calls `compute_cadence_baseline`. Provenance fire `cadence_computed`
  records detection_status, the populated classes, and the global
  median.
- `_build_seasonality(g, taxonomy, cfg, rules_fired)` — resolves
  `run_date` from `cfg["RUN_DATE"]` if present, otherwise the orders
  DataFrame's max `Created at`, otherwise returns
  `detection_status="INVALID_RUN_DATE"`. Provenance fire
  `seasonality_lookup` records the resolved run_date, active window,
  and detection_status.

## 6. Schema changes

Additive on existing T1 sub-dataclasses (no new sub-dataclasses;
`event_version=1` frozen contract preserved):

- `CadenceBaseline.method_by_sku_class: Dict[str, str]` (new field;
  defaults to empty dict; tracks `"empirical_median"` vs
  `"INSUFFICIENT_DATA"` per class).
- `SeasonalityContext.expected_lift_direction: Optional[str]`
  (`"+"`, `"-"`, `"none"`, or `None`).
- `SeasonalityContext.expected_lift_range: Optional[List[float]]`
  (always `[low, high]` shape or `None`).
- `SeasonalityContext.source_artifact: Optional[str]` (relative repo
  path to the heuristic memo).

`store_profile_from_dict` round-trips all four new fields with
type-safe parsing; pre-T3 payloads (missing the fields) deserialize
to the safe defaults so the legacy fixtures' `store_profile=None` slot
is unaffected.

## 7. Tests

New: `tests/test_s6_5_t3_cadence_seasonality.py` (19 tests). The 14
items from the IM plan §S6.5-T3 list are all covered; a few items
land as multiple tests to keep each assertion focused.

Coverage:

- **Cadence envelopes (3 tests):** Beauty skincare in [20, 60]; supplements protein in [40, 120] OR INSUFFICIENT_DATA; below-N=30 → INSUFFICIENT_DATA.
- **D-6 invariant (1 test):** cadence.py contains no `lifelines` / `sklearn` / `statsmodels` / `implicit` / `lightfm` import.
- **Seasonality lookups (5 tests):** BFCM_tail on 2026-11-25; Mothers_Day on 2026-05-05; Mothers_Day closed on 2026-05-17 (founder envelope); no active window mid-July supplements; January_resolution on 2026-01-10 supplements/multivitamin.
- **Lift-range shape (2 tests):** every YAML window has a `[low, high]` pair; the active-context return mirrors the pair.
- **Source artifact (1 test):** active context's `source_artifact` resolves to an existing file under `config/priors_sources/seasonality/`.
- **No revenue multiplier (1 test):** `SeasonalityContext` carries no `revenue_multiplier` / `p_value_adjust` / `lift_multiplier` / `scale_factor` field.
- **Flag-OFF parity (1 test):** `EngineRun.store_profile` round-trips `None` cleanly.
- **YAML schema (2 tests):** exactly 5 named windows; YAML path pin.
- **Annotations-only (1 test):** every YAML window tagged `validation_status: heuristic_unvalidated`.
- **End-to-end via `build_store_profile` (2 tests):** populates cadence + seasonality for Beauty/skincare/BFCM; seasonality inactive on 2026-05-17.

## 8. Per-fixture probe (founder envelope check)

Probed via `src.profile.build_store_profile` on the pinned synthetic
fixtures (orders DataFrame standardized via
`src.utils.standardize_customer_key`, net_sales = qty × price):

| Fixture | cadence.classes | global median | seasonality 2026-05-17 |
|---|---|---|---|
| Beauty pinned slate (VERTICAL_MODE=beauty) | `{"skincare": 53}` ✓ (inside [20, 60]) | 53 d | NO_ACTIVE_WINDOW ✓ (Mothers_Day closed by 05-13) |
| Supplements G-1 (VERTICAL_MODE=supplements) | `{"functional": 38, "multivitamin": 39, "probiotics": 40, "protein": 40}` ✓ (protein inside [40, 120]) | 39 d | NO_ACTIVE_WINDOW |
| M0 small_sm / mid_shopify / micro_coldstart | n/a (flag OFF → engine_run.store_profile is None) | n/a | n/a |

**All three founder envelope acceptance criteria PASS:**

- Beauty skincare median 53 d ∈ [20, 60] ✓
- Supplements protein median 40 d ∈ [40, 120] ✓
- 2026-05-17 → Mothers_Day inactive (window 05-01..05-12 closed) ✓

## 9. Behavior change

**None.** Flag still default OFF (`ENGINE_V2_STORE_PROFILE=false`).
No consumer reads `cadence` / `seasonality` in S6.5 until T4 wires
the gate-calibration cells (and even then, T4 only reads
descriptively; T5 is the atomic flip + re-pin). The 5 pinned
fixtures are byte-identical.

## 10. Hard constraints respected

- D-5/D-6/D-8 invariants intact (no Shopify/Klaviyo, no banned ML
  modules, vertical scope unchanged).
- B-4 role-uniqueness intact (no slate edits).
- B-5 Berkson invariant intact (cadence is descriptive of the store,
  not a cross-period cohort comparison).
- S-2..S-6 substrate write paths untouched.
- Schema-additive only within `event_version=1` (no new sub-dataclass;
  4 new optional fields with safe defaults).
- No new runtime dependencies (`pyyaml`, `numpy`, `pandas` already
  in `requirements.txt`).

## 11. Out of scope (T3)

- Consumer wiring (T4: `audience_builders`, `measurement_builder`,
  `decide`, `sizing` read `cadence` + `seasonality` indirectly via
  derived `gate_calibration` cells).
- Subscription-led slate ordering (founder Q5 deferred to S6-T3).
- New replenishment-due base rate from cadence (Q5; S6-T3+).
- K-M-based right-censored survival fit (deferred to S11).

## 12. Commit list

1. `S6.5-T3: cadence baseline + seasonality calendar lookup`
2. `Document S6.5-T3 in repo memory.md`
3. (this commit) — `S6.5-T3 summary`

## Backfill from memory.md (migration trim 2026-05-25)

## Sprint 6.5 Ticket T3 closeout (2026-05-17)

**Status:** Complete. Flag still default OFF. All 5 pinned fixtures byte-identical (no consumer reads `cadence` / `seasonality` in S6.5 until T4 derives gate-calibration cells; T5 owns the atomic flip + re-pin).

**What shipped:**

- `config/seasonality_calendars.yaml` — schema_version 1.0.0, validation_status `heuristic_unvalidated`. Exactly 5 named windows per founder Q3 (BFCM_tail / January_resolution / Mothers_Day / Back_to_school / Summer_skin). Each window carries `start_md`, `end_md`, optional `valid_for_year`, an `applies_to` list of `{vertical, subvertical}` rows (null subvertical = wildcard over the vertical), `expected_lift_direction`, `expected_lift_range` (always `[low, high]`, never a point), and `source_artifact` (relative path to a heuristic memo). 5 thin memos live under `config/priors_sources/seasonality/`. Per Part III §8: annotations only — `expected_lift_range` is NEVER a revenue or significance multiplier.
- `src/profile/cadence.py::compute_cadence_baseline(aligned, subvertical_sku_assignment)` — pure-pandas right-censored empirical median per sub-vertical-tagged SKU class. Customers with only 1 in-class purchase are right-censored (do NOT contribute to the median). Per-class N=30 floor; below the floor → `method="INSUFFICIENT_DATA"` and no entry in `median_reorder_days_by_sku_class`. K-M lifts the censored contribution at S11. D-6 invariant pinned by a test (no `lifelines` / `sklearn` / `statsmodels` / `implicit` / `lightfm` imports).
- `src/profile/seasonality.py::lookup_active_seasonality(run_date, vertical, subvertical, calendars=None)` — YAML lookup with MM-DD inclusive (wrap-around supported) + optional `valid_for_year` guard. `mixed` / `other_refused` short-circuit to `NOT_APPLICABLE`. Active matches return `(active_window_name, expected_lift_direction, expected_lift_range, source_artifact, ACTIVE)`. `SeasonalityContext` carries NO `revenue_multiplier` / `p_value_adjust` field (test pins the negative).
- `src/profile/builder.py` — `_build_cadence` + `_build_seasonality` helpers wired into `build_store_profile`. `run_date` resolved from `cfg["RUN_DATE"]` else orders.max(`Created at`) else `INVALID_RUN_DATE`. Provenance fires `cadence_computed` + `seasonality_lookup` with detection_status, classes, run_date, active window.
- `src/profile/types.py` — schema-additive on `CadenceBaseline` and `SeasonalityContext` (no new sub-dataclasses; `event_version=1` frozen contract preserved): adds `CadenceBaseline.method_by_sku_class: Dict[str,str]`, `SeasonalityContext.expected_lift_direction: Optional[str]`, `SeasonalityContext.expected_lift_range: Optional[List[float]]`, `SeasonalityContext.source_artifact: Optional[str]`. `store_profile_from_dict` round-trips all four with type-safe parsing; pre-T3 payloads deserialize cleanly with the safe defaults.

**Tests:** 19 new in `tests/test_s6_5_t3_cadence_seasonality.py`. Coverage: cadence envelopes (Beauty skincare in [20, 60]; supplements protein in [40, 120] OR INSUFFICIENT_DATA; below-N=30 → INSUFFICIENT_DATA); D-6 invariant pin; 5 seasonality lookup paths (BFCM_tail / Mothers_Day / Mothers_Day-closed-today / mid-July supplements no-window / January_resolution multivitamin); lift-range `[low, high]` shape on every YAML window AND on every active context; source_artifact file-existence; no-revenue-multiplier field on the dataclass; YAML schema (exactly 5 windows + path pin); every window tagged `heuristic_unvalidated`; end-to-end via `build_store_profile`. One T1 orchestrator-test stub updated to accept the populated T3 detection_status values (the bare-dataclass default test still asserts the `DEFERRED_TO_T3` constant). Full suite 1322 passed / 14 skipped (was 1303 passed); the one wall-clock flake `test_inventory_updated_at_is_fresh` is the documented pre-existing fail from S6-T1.5 closeout, unrelated to T3.

**Per-fixture probe (founder envelope check):**

| Fixture | cadence classes | global median | seasonality (2026-05-17) |
|---|---|---|---|
| Beauty pinned slate (VERTICAL_MODE=beauty) | `{"skincare": 53}` ✓ (in [20, 60]) | 53 d | NO_ACTIVE_WINDOW ✓ (Mothers_Day closed by 05-13) |
| Supplements G-1 (VERTICAL_MODE=supplements) | `{"functional": 38, "multivitamin": 39, "probiotics": 40, "protein": 40}` ✓ (protein in [40, 120]) | 39 d | NO_ACTIVE_WINDOW |
| M0 small_sm / mid_shopify / micro_coldstart | n/a (flag OFF → engine_run.store_profile is None) | n/a | n/a |

**All three founder envelope acceptance criteria PASS:** Beauty skincare 53d ∈ [20, 60]; Supplements protein 40d ∈ [40, 120]; Mothers_Day inactive on 2026-05-17.

**Hard-stops:** none on T3 impl (flag OFF). No re-pin.

**Caveats / what T3 does NOT do:**

- Cadence + seasonality remain DESCRIPTIVE in S6.5. No consumer reads them until T4 maps them into gate-calibration cells. T4 will derive `primary_window` and (potentially) materiality from cadence percentiles; the actual gate-cell calibration is the load-bearing T4 work.
- `SeasonalityContext.expected_lift_range` is annotation-only. Consumers may surface the range to merchants as context but MUST NOT consume it as a numerical scalar in any revenue, p-value, or slate-ordering equation (Part III §8 discipline; T4/T5 will not change this).
- K-M survival fit deferred to S11. The MVP right-censored empirical median drops singleton customers (they do not contribute to the per-class median).

**Schema:** `event_version=1` additive (4 new optional fields on existing T1 sub-dataclasses; all defaults preserve pre-T3 round-trip).
**Suite:** 1322 passed / 14 skipped (1 pre-existing wall-clock fail unrelated to T3).
**Summary:** [agent_outputs/code-refactor-engineer-s6_5-t3-summary.md](agent_outputs/code-refactor-engineer-s6_5-t3-summary.md)
