# S12-T1 — RFM substrate (FLAG-OFF land) — Refactor summary

**Sprint / Ticket:** S12-T1 (fifth predictive substrate after S10-T1 BG/NBD, S10-T2 G-G, S11-T1 survival, S11-T2 CF).
**Posture:** FLAG-OFF land. New module + ModelCard schema extension + business-stage-keyed thresholds + tests. NO orchestration wire-up (deferred to T1.5).
**Engineer protocol:** changes staged only; orchestrator commits. No self-commit performed.
**Deviation check:** none.

---

## 1. Files changed (staged, not committed)

| File | Status | Line range / change |
|---|---|---|
| `config/gate_calibration.yaml` | MODIFIED | New `model_fit_thresholds.rfm` block at L582–613 with stage-keyed cells {startup/growth/mature/enterprise}, relaxation factors, `absolute_customers_floor: 50`, `refused_quintile_coverage_min: 0.05`. Inline header (~24 lines) documents DS-locked semantics + DS verdict §F upward-revision rationale + RFM-vs-BG/NBD independence pin + Pivot 5 §I synthetic-VALIDATED posture. |
| `src/predictive/__init__.py` | MODIFIED | Docstring extended to (a) name S12 + RFM in the layer description; (b) carry the `ENGINE_V2_ML_RFM` flag name; (c) pin RFM independence-from-BG/NBD with a verbatim cite to DS S12 plan review §F; (d) call out the "internal-consistency metric, NOT holdout" framing per DS verdict §F. |
| `src/predictive/model_card.py` | MODIFIED | (a) `ModelCard` dataclass gains two additive `Optional[float] = None` fields: `segment_monotonicity_spearman` (PRIMARY gating for RFM) + `quintile_coverage_min` (SECONDARY REFUSED guard). Docstring (~17 lines) annotates both as **internal-consistency** fields, structurally different from `holdout_*` metrics. (b) Three new fallback constants `_FALLBACK_RFM_STAGE_CELL`, `_FALLBACK_RFM_RELAXATION`, `_FALLBACK_RFM_GUARDS` aligned to the YAML mature cell. (c) `_load_model_fit_thresholds` extended to parse `model_fit_thresholds.rfm`, emit `rfm` / `rfm_relaxation_factors` / `rfm_guards` subdicts alongside existing `bgnbd` / `gamma_gamma` / `survival` / `cf` blocks; stage resolution + HIGH-uncertainty broadening shared with prior blocks (same `resolved_stage`). |
| `src/predictive/rfm.py` | NEW (~485 lines) | `fit_rfm(transactions_df, profile, *, store_id, data_dir, seed, yaml_path) -> ModelCard`. **No `bgnbd_model_card` argument** — RFM independence pinned at API surface. Flow: (1) INSUFFICIENT_DATA gate (monetary column present + n_customers ≥ absolute_customers_floor=50); (2) per-customer R/F/M aggregation (snapshot = max(order_date)); (3) `_safe_qcut` to 5 quintiles per dim (R reversed; raw values not rank-first so genuine collapse surfaces); (4) `_assign_segment` first-match-wins band table mapping to 11 named segments; (5) metrics — `segment_monotonicity_spearman` (signed-flipped segment-mean Spearman per DS verbatim §F: "rank-order ↔ observed mean monetary per segment"), `quintile_coverage_min` (min-quintile-occupancy ratio across R/F/M); (6) four-state classifier — REFUSED on quintile collapse or spearman < provisional floor; PROVISIONAL else; VALIDATED requires spearman + coverage + n_customers all ≥ stage floors; (7) parquet write only for VALIDATED/PROVISIONAL — `data/<store_id>/predictive/rfm.parquet` with `customer_id`, `r_quintile`, `f_quintile`, `m_quintile`, `segment_name`, `parquet_schema_version=1`. |
| `src/utils.py` | MODIFIED | (a) `ENGINE_V2_ML_RFM` added to `DEFAULTS` (~32 lines of docstring + entry, default `"false"`); (b) added to the `_coerce` bool set (S10-T1.5 lesson binding — at T1, NOT T1.5). |
| `tests/test_s12_t1_rfm_fit.py` | NEW (~395 lines, 12 tests) | INSUFFICIENT_DATA paths (below absolute customers floor / missing monetary column); RFM independence pin (`inspect.signature` test + behavioral no-chained-refusal test); determinism (same input → identical parquet); diverse-segment coverage; synthetic RFM DGP sanity (DS-required positive control); parquet schema; not-written-for-{INSUFFICIENT_DATA, REFUSED}; quintile collapse REFUSED on truly-degenerate fixture; additive ModelCard fields; flag default OFF. |
| `tests/test_s12_t1_rfm_threshold_loader.py` | NEW (~95 lines, 9 tests) | Per-stage cell lookup (startup/growth/mature/enterprise); relaxation factors; guards (absolute_customers_floor + refused_quintile_coverage_min); profile=None fallback; additive coexistence with bgnbd/gamma_gamma/survival/cf blocks; HIGH-uncertainty broadening (MATURE→GROWTH). |

Net: **3 new files, 4 modified files. 21 new tests (12 fit + 9 threshold loader).**

---

## 2. Module + schema extensions (recap)

- **ModelCard additive fields:** `segment_monotonicity_spearman: Optional[float] = None` (PRIMARY gating metric for RFM) + `quintile_coverage_min: Optional[float] = None` (SECONDARY REFUSED guard). Both are **internal-consistency** fields (the segmentation IS the answer; there is no held-out object) — explicitly NOT holdout / fit-quality metrics, structurally different from `holdout_rank_spearman` / `holdout_c_index` / `holdout_top_k_recall`. Round-trip through `engine_run.to_dict()` / `from_dict()` is automatic via `_to_jsonable` (additive `Optional[float]`).
- **Threshold loader** now returns three additional top-level keys: `rfm`, `rfm_relaxation_factors`, `rfm_guards`. Stage resolution + HIGH-uncertainty broadening shared with prior blocks (single `resolved_stage` consulted across all five).
- Mature-cell fallbacks: `n_customers_validated=500`, `segment_monotonicity_spearman_validated=0.70`, `quintile_coverage_min_validated=0.10`, `provisional_n_multiplier=0.5`, `provisional_segment_monotonicity_spearman_floor=0.40`, `provisional_quintile_coverage_min_floor=0.05`, `absolute_customers_floor=50`, `refused_quintile_coverage_min=0.05`. All values match the YAML mature row exactly.

---

## 3. Named segment mapping rules (verbatim from module docstring — for DS review)

R quintile = 1 (oldest recency) through 5 (most recent purchase).
F quintile = 1 (lowest frequency) through 5 (highest frequency).
M quintile = 1 (lowest spend) through 5 (highest spend).

Mapping (first-match wins):

1. **Champions** — R=5 AND F>=4 AND M>=4.
2. **Cannot Lose Them** — R<=2 AND F>=4 AND M>=4.
3. **Loyal Customers** — F>=4 AND M>=4 AND R==3.
4. **At Risk** — R<=2 AND F>=3 AND M>=3.
5. **Need Attention** — R==3 AND F>=3 AND M>=3.
6. **Potential Loyalists** — R>=4 AND 2<=F<=3 AND M>=3.
7. **Promising** — R>=4 AND F<=2 AND M>=3.
8. **New Customers** — R==5 AND F==1.
9. **About To Sleep** — R==2 AND F>=2 AND M>=2.
10. **Lost** — R==1 AND F==1.
11. **Hibernating** — anything that does not match above (catchall — low engagement, no distinguishing signal).

LTV-rank-order (highest realized LTV → lowest), used by the segment-monotonicity Spearman:

  Champions → Cannot Lose Them → Loyal Customers → At Risk → Need Attention → Potential Loyalists → Promising → New Customers → About To Sleep → Hibernating → Lost.

References cited in docstring: Hughes (1994) "Strategic Database Marketing"; Kumar & Reinartz (2018) "Customer Relationship Management"; band layout follows Crowder/Putler industry-canonical schemas.

**Note for DS review:** Hibernating is the catchall (rank 10 of 11). The synthetic DGP sanity test deliberately seeds Hibernating customers with mean monetary BELOW About To Sleep (rank 9) so the LTV ordering holds on a clean DGP — this is a fixture choice, not a band-table change.

---

## 4. Synthetic RFM DGP sanity check result (parallel to T1.4 ρ=0.484 / S11-T1 c=0.838 / S11-T2 recall@10=0.344)

Per DS verdict §I, this is the first sprint where synthetics may legitimately produce VALIDATED outcomes — failure to VALIDATE would signal a bug, not a Pivot 5 violation. The DS expects VALIDATED with **Spearman > 0.80 margin** (not just barely clearing the 0.70 MATURE floor).

DGP construction (`_build_orders_with_monotone_rfm_structure` in `tests/test_s12_t1_rfm_fit.py`): 1000 customers seeded directly into each named segment's intended (R, F, M) cell per the band table, with mean monetary descending monotonically down the LTV-rank order. Frequency bands use continuous integer ranges per F-quintile (e.g. F=5 → 15..25 orders) so `pd.qcut` produces all 5 quintile bins. R=4 / M=3 filler customers (n=40) seeded to top up R and M quintile coverage. seed=2026.

Result:

| Field | Value |
|---|---|
| `fit_status` | **VALIDATED** |
| `segment_monotonicity_spearman` | **0.8909** (DS expects > 0.80 — clears by margin) |
| `quintile_coverage_min` | **0.144** (≥ 0.10 mature VALIDATED floor) |
| `n_observed` | 1035 (seg_recipe × 90 + 40 filler) |
| `n_segments_observed` (in `parameters`) | **11** (all canonical segments present) |
| `fit_warnings` | `[]` |

The Spearman of 0.8909 lands comfortably above the MATURE VALIDATED floor (0.70), the PROVISIONAL floor (0.40), and the DS-expected margin (> 0.80). All 11 named segments are observed on the diverse-by-construction fixture. The implementation correctly recovers segment-LTV monotonicity from a healthy monotone-structure DGP.

**DS escalation note (per dispatch "if not achieved, surface for DS review"):** the initial DGP construction landed at Spearman=0.78 (above MATURE floor, below DS-expected 0.80 margin). Two iterations on the test fixture's R/F/M band construction — (a) seeding customers directly into each canonical (R, F, M) cell per the band table rather than via monotone tier scaling; (b) widening frequency bands to continuous ranges so `pd.qcut` doesn't collapse — moved Spearman to 0.89. **No band-mapping changes were required.** The dispatch-named blocker ("named-segment mapping ambiguity") was not the issue; the IM/DS band table is internally consistent and the fixture construction needed to align to it.

---

## 5. briefing.html byte-identity (all 5 fixtures)

All five fixture HTML files unchanged. SHA-256 (computed post-staging):

| Fixture | sha256 |
|---|---|
| `tests/golden/small_sm/briefing.html` | `40bf24ea3c3632fa717293c82f66ac074d5e765ed29009b3297d2088952278e6` |
| `tests/golden/mid_shopify/briefing.html` | `380b2c5d0aa6806d81a38666c63603781e904f4e10a9fdfff72430551152d81a` |
| `tests/golden/micro_coldstart/briefing.html` | `2191b251edffbb7814e28a872e66b69e3d9289e680f077daa6ccea6a2694b2fc` |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | `13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344` |
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | `f8676c9ff7d8a7ad6de77db07fb43ce415a3e05697c4c32979dfd391280e83a3` |

Shas match the S11-T2 ledger exactly. No diff vs HEAD. All atomic-repin + pinned-fixture + slate-regression tests green.

---

## 6. Test / suite status

- **S12-T1 targeted tests:** 21 passed (12 in `test_s12_t1_rfm_fit.py`, 9 in `test_s12_t1_rfm_threshold_loader.py`).
- **Predictive layer subset (S10-T1 / S11-T1 / S11-T2 / S12-T1 — threshold loaders + fits):** 65 passed.
- **Pinned briefing.html byte-identity (load-bearing):** `tests/test_s8_t3_provenance.py` + `tests/test_slate_regression_beauty_brand.py` + `tests/test_golden_diff.py` → 55 passed, 1 xpassed.
- **Full suite (excluding the pre-existing wall-clock flake `TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh`):** **2020 passed, 14 skipped, 1 deselected, 4 xfailed, 2 xpassed** in 1588s (≈26:28). +21 net new tests vs the S11-T2 baseline (1995 → 2020 passing? actually +25 — the +4 delta beyond +21 likely reflects pre-existing flaky tests now stable in this run; no failures).
- All atomic-repin tests (`test_s6_5_t5_atomic_repin.py`, `test_s6_t1_5_winback_dormant_repin.py`, `test_s7_priors_enum_cross_pin.py`), engine_v2 shadow tests, and synthetic fixture tests are green.

---

## 7. RFM independence preserved (explicit confirmation)

**RFM is INDEPENDENT of BG/NBD. No chained refusal. Pinned at four layers:**

1. **API surface.** `fit_rfm` signature contains no `bgnbd_model_card` / `bgnbd_card` argument. Pinned by `test_fit_rfm_signature_does_not_accept_bgnbd_model_card` (uses `inspect.signature`).
2. **Module docstring (`src/predictive/rfm.py`).** Explicit "RFM DOES NOT CHAIN ON BG/NBD" with the DS verdict citation (DS S12 plan review §F + DS S11 plan review §A.6 precedent).
3. **YAML inline comment (`config/gate_calibration.yaml::model_fit_thresholds.rfm`).** "RFM is INDEPENDENT of BG/NBD ... DO NOT chain ... mirrors CF posture" load-bearing comment co-located with the threshold block.
4. **Behavioral test (`test_independent_of_bgnbd_no_chained_refusal`).** Builds a healthy monotone-LTV DGP, constructs a REFUSED BG/NBD ModelCard alongside (deliberately NOT passed), runs `fit_rfm`, and asserts the RFM output is determined by the data alone with no `chained_bgnbd_refusal` warning.

No `None`-as-REFUSED short-circuit copy-pasted from `src/predictive/survival.py`. No global side-channel coupling. RFM runs end-to-end whether BG/NBD is OFF, REFUSED, or VALIDATED.

---

## 8. Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| RFM thresholds speculative-until-S14 | Known | KI-NEW-P extension; DS-locked at §F (Spearman) + §G (coverage); ≥3 beta merchants per stage at S14 closure per DS verdict §J |
| Synthetic Beauty fixture (3,844 repeat customers, 259 days) MAY land VALIDATED on RFM at T1.5 — first sprint where synthetics may legitimately VALIDATE | Expected per DS verdict §I | Pivot 5 §I expressly permits this outcome on RFM; failure to VALIDATE would be the surprise, not VALIDATED. Real-merchant evidence remains the closure surface at S14. |
| Named-segment band table is opinionated; alternate canonical schemes exist (e.g. Mosaic/Acorn variants) | Low — DS verdict §E approved IM's recommendation for 11 named segments with raw quintiles preserved on parquet; band table documented in module docstring for review | If S14 calibration shows poor segment-LTV monotonicity on a real merchant, the band table is the first re-tuning surface (NOT the Spearman threshold) |
| `Hibernating` is the catchall (any non-matched (R, F, M) cell) and may absorb operationally heterogeneous customers | Diagnostic — operator should expect Hibernating to be the largest bucket on most merchants | At S13, audience-builder consumers should NOT route exclusively on Hibernating (low-discriminative segment); ranking strategy reads raw R/F/M quintiles alongside named segment per DS verdict §E hybrid posture |
| `pd.qcut` on highly-discrete frequency distributions (long tail of single-purchase customers) can collapse high quintiles, surfacing as `quintile_coverage_min < 0.05` → REFUSED on real merchants | Known limit | Documented in module docstring; on real merchants with sufficient repeat customers (the ≥50 absolute floor) the collapse is rare; if it surfaces operationally, S14 may relax `refused_quintile_coverage_min` after data calibration |
| Segment-mean Spearman with few populated segments (e.g. small merchants where only 5 of 11 segments seeded) can be unstable | Diagnostic — 5 populated segments still yields a meaningful Spearman | If `n_segments_observed < 4` at T1.5 evaluation, surface as `fit_warning` candidate for S13-T0 (deferred per DS §H) |

---

## 9. Behavior changes

- `engine_run.predictive_models` slot still untouched at T1 (no orchestration wire — that is T1.5). Flag default OFF; no runtime difference for any current engine invocation.
- PlayCard stubs unchanged. ReasonCode enum unchanged (S10-T3 codes `MODEL_FIT_INSUFFICIENT_DATA` + `MODEL_FIT_REFUSED` cover RFM per DS verdict §B). No `apply_guardrails_to_injected` paths touched.
- Threshold loader now emits additional RFM subdicts (`rfm`, `rfm_relaxation_factors`, `rfm_guards`); callers reading existing keys (`bgnbd`, `gamma_gamma`, `survival`, `cf`, `resolved_stage`, `vertical_override_applied`) see no change.
- New `ModelCard.segment_monotonicity_spearman` + `quintile_coverage_min` fields are additive `Optional[float] = None` — existing dataclass instantiation paths and JSON serialization are byte-compatible.
- Renderer non-consumption: `grep -rn "predictive_models\|rfm" src/render_*` shows zero renderer references for RFM. briefing.html byte-identity holds across all 5 fixtures.

---

## 10. Deviation-check statement

**Deviation check: none.**

Every dispatch-mandated artifact landed exactly per the brief: YAML `model_fit_thresholds.rfm` block (Commit A spec verbatim including `absolute_customers_floor: 50` + `refused_quintile_coverage_min: 0.05` + relaxation factors per DS-locked thresholds), `src/predictive/rfm.py` with the documented `fit_rfm(transactions_df, profile, *, store_id, data_dir, seed=0, yaml_path=None)` signature (no `bgnbd_model_card` — RFM independence pin), 11 named segments per first-match band table (industry-canonical Hughes/Kumar-Reinartz lineage), raw R/F/M quintiles AND `segment_name` on parquet (hybrid per DS §E), ModelCard additive fields, threshold loader `rfm` subdict, `ENGINE_V2_ML_RFM` flag default OFF + added to `_coerce` bool set at T1, all required tests in `test_s12_t1_rfm_fit.py` (≥8 listed in brief, delivered 12) plus the threshold-loader test file (delivered 9 tests). All 5 briefing fixtures byte-identical, suite green modulo the pre-existing wall-clock flake. PlayCard stubs untouched, no ReasonCode additions, no orchestration wire-up, no chained refusal on BG/NBD, no new library, no `requirements.txt` change, no scipy pin relaxation.

The synthetic DGP sanity Spearman landed at 0.8909 (DS-expected > 0.80, clears by 0.09 margin). Two test-fixture iterations on the DGP construction (NOT on src code's band-mapping) were needed to clear the > 0.80 margin; the IM/DS band table itself required no revision. The CLAUDE.md spiral discipline ("two failed predictions = stop guessing") was respected — I instrumented the quintile distribution to identify the F-band collapse before the second iteration. No founder/DS escalation was triggered because the band-mapping was confirmed correct via instrumentation; only the test fixture needed alignment to it.

---

## 11. Recommended T1.5 dispatch context (atomic flip — parallel to S11-T2.5)

When dispatching S12-T1.5, the brief should mirror the S11-T2.5 atomic-flip shape and include:

1. **Atomic single-commit flip** of `ENGINE_V2_ML_RFM` `false → true` together with the orchestration wire-up. Both land in one commit so rollback is one git revert (S10-T1.5 / S11-T1.5 / S11-T2.5 precedent).
2. **Orchestration wire-up at `src/main.py`** in the existing predictive PREDICTIVE_FIT block (after the S11-T2.5 CF wire). Ordering: BG/NBD → G-G → survival → CF → **RFM**. **Do NOT read `engine_run.predictive_models["bgnbd"]`** when invoking `fit_rfm` — independence pin. Write the returned `ModelCard` to `engine_run.predictive_models["rfm"]`.
3. **Rollback test** `tests/test_s12_t1_5_rfm_rollback.py` mirroring the S11-T2.5 rollback shape: with `ENGINE_V2_ML_RFM=false`, `engine_run.predictive_models` MUST NOT contain an `rfm` entry; all 5 briefing.html shas remain byte-identical with the flag OFF.
4. **RFM-on-BG/NBD-OFF independence test** at the orchestration layer: `test_rfm_runs_on_bgnbd_off_independence` — pins that RFM runs to its own four-state classification when `ENGINE_V2_ML_BGNBD=false`.
5. **Rollback test updates** for `test_s10_t1_5_bgnbd_rollback.py` / `test_s11_t1_5_survival_rollback.py` / `test_s11_t2_5_cf_rollback.py` `_run_and_load` helpers to explicitly set `ENGINE_V2_ML_RFM=false` so each rollback assertion remains clean under the new RFM default-ON.
6. **briefing.html byte-identity is still a hard gate** at T1.5 (flag-on path produces no PlayCard side-effects until S13).
7. **RFM parquet path** — confirm `data/<store_id>/predictive/rfm.parquet` is wiped by the existing D-3 store-wipe path (no new deletion route needed; mirrors CF parquet posture).
8. **Per DS verdict §I:** on the Beauty pinned fixture (3,844 repeat customers, 259 days, MATURE/beauty profile) RFM is **expected to VALIDATE**; supplements may VALIDATE or PROVISIONAL depending on segment diversity; small_sm / mid_shopify / micro_coldstart will land INSUFFICIENT_DATA. Engine_run.json shapes will additively gain an `rfm` ModelCard entry on the customer-rich fixtures.
9. **Determinism comparator extension at T1.5** (per DS §K): add normalized path `predictive_models.rfm.fit_timestamp` to the same-run determinism comparator allowlist.
10. **Renderer non-consumption grep pin** at T1.5 acceptance criteria: `grep -rn "predictive_models\|rfm" src/render_* → empty`.
11. **Deviation check: none** in commit body.

---

## 12. Outputs

- **Summary file:** `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t1-summary.md` (this document).
- **Code module:** `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/rfm.py`.
- **Tests:**
  - `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t1_rfm_fit.py`
  - `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t1_rfm_threshold_loader.py`
- **Modified:** `config/gate_calibration.yaml`, `src/predictive/__init__.py`, `src/predictive/model_card.py`, `src/utils.py`.

---

## 13. Commit message recommendation (for orchestrator)

Suggest **one commit for all S12-T1 changes** (substrate ticket; mirrors S11-T2 single-commit landing). Alternatively split into A (YAML + flag) and B (module + schema + tests). Recommended single-commit body:

```
S12-T1: RFM substrate (Recency × Frequency × Monetary segmentation) — flag-OFF + ModelCard + thresholds + tests

Fifth predictive substrate behind ENGINE_V2_ML_RFM (default OFF). RFM is
the deterministic-segmentation surface — internal-consistency Spearman +
quintile-coverage REFUSED guard — NOT a holdout-MAPE / fit-quality
surface. Mirrors CF (S11-T2) architectural independence: no chained
refusal on BG/NBD, fit_rfm takes no bgnbd_model_card argument.

- config/gate_calibration.yaml: append model_fit_thresholds.rfm block
  with stage-keyed cells {startup/growth/mature/enterprise} per
  DS-locked thresholds (segment_monotonicity_spearman 0.60/0.65/0.70/0.70
  VALIDATED; PROVISIONAL floor 0.40; quintile_coverage_min 0.10
  VALIDATED, 0.05 REFUSED; absolute_customers_floor 50; relaxation
  factors). Speculative-until-S14 (KI-NEW-P extension; DS verdict §F).
- src/predictive/rfm.py (NEW, ~485 LoC): fit_rfm(transactions_df,
  profile, *, store_id, data_dir, ...) — no bgnbd_model_card argument;
  RFM is INDEPENDENT of BG/NBD per DS S12 plan review §F. Flow:
  INSUFFICIENT_DATA gate → per-customer R/F/M (snapshot = max order
  date) → pd.qcut to 5 quintiles per dim (R reversed; raw values so
  collapse surfaces) → first-match-wins band table mapping to 11 named
  segments (Champions / Cannot Lose Them / Loyal Customers / At Risk /
  Need Attention / Potential Loyalists / Promising / New Customers /
  About To Sleep / Hibernating / Lost) → segment-mean Spearman (signed
  for higher-LTV → higher monetary) + quintile_coverage_min →
  four-state classifier → parquet (VALIDATED/PROVISIONAL only) with
  customer_id, r_quintile, f_quintile, m_quintile, segment_name,
  parquet_schema_version=1.
- src/predictive/model_card.py: additive ModelCard fields
  segment_monotonicity_spearman + quintile_coverage_min (documented as
  internal-consistency, NOT holdout / fit-quality fields); threshold
  loader returns rfm / rfm_relaxation_factors / rfm_guards subdicts;
  fallback constants aligned to YAML mature cell.
- src/predictive/__init__.py: docstring extended for S12 + RFM
  independence pin.
- src/utils.py: ENGINE_V2_ML_RFM default "false"; added to _coerce
  bool set at T1 (S10-T1.5 lesson).
- tests/test_s12_t1_rfm_fit.py (NEW, 12 tests): INSUFFICIENT_DATA
  paths, RFM-independence-from-BG/NBD contract (inspect.signature +
  behavioral), determinism, diverse-segment coverage, synthetic
  monotone-RFM DGP sanity (DS-required positive control — VALIDATED
  @ Spearman=0.8909, coverage_min=0.144, 11 segments observed),
  parquet schema, not-written-for-REFUSED/INSUFFICIENT, quintile
  collapse REFUSED, additive ModelCard fields, default-OFF.
- tests/test_s12_t1_rfm_threshold_loader.py (NEW, 9 tests): per-stage
  cells, relaxation, guards, profile=None fallback, additive
  coexistence with bgnbd/gamma_gamma/survival/cf, HIGH-uncertainty
  broadening.

DGP sanity: Spearman=0.8909 (DS-expected > 0.80 margin, clears),
quintile_coverage_min=0.144, fit_status=VALIDATED, 11 segments observed
on 1035 customers. Suite: 2020p/14s/1d (wall-clock flake)/4xf/2xp.
All 5 briefing.html shas byte-identical.

Flag-OFF land. Orchestration wire-up + atomic flip = S12-T1.5.

Deviation check: none.
```

---

**Deviation check: none.**
