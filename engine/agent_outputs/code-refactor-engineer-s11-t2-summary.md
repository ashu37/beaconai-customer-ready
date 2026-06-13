# S11-T2 — Collaborative Filtering substrate (implicit ALS, FLAG-OFF) — Refactor summary

**Sprint / Ticket:** S11-T2 (third predictive substrate after S10-T1 BG/NBD, S10-T2 G-G, S11-T1 survival).
**Posture:** FLAG-OFF land. New module + ModelCard schema extension + business-stage-keyed thresholds + tests. NO orchestration wire-up (deferred to T2.5).
**Engineer protocol:** changes staged only; orchestrator commits. No self-commit performed.
**Deviation check:** none.

---

## 1. Files changed (staged, not committed)

| File | Status | Line range / change |
|---|---|---|
| `requirements.txt` | MODIFIED | New line 6: `implicit>=0.7,<0.8  # S11-T2 Collaborative Filtering ALS (implicit feedback); mac-ARM wheels available`. Prior pins preserved (`scipy>=1.11.0,<1.13`, `lifetimes==0.11.3`, `scikit-survival>=0.22,<0.24`). |
| `config/gate_calibration.yaml` | MODIFIED | Appended `model_fit_thresholds.cf` block at L566–580 with stage-keyed cells {startup/growth/mature/enterprise} per dispatch spec verbatim, `relaxation_factors`, and ALS hyperparameter sub-keys. Inline comment block L549–565 documents DS-locked semantics + "speculative-until-S14 (KI-NEW-P extension)" + the load-bearing "CF is INDEPENDENT of BG/NBD" pin. |
| `src/predictive/__init__.py` | MODIFIED | Docstring updated to reference `ENGINE_V2_ML_CF` and the DS-locked CF-vs-survival architectural divergence ("CF is INDEPENDENT of BG/NBD per DS S11 plan review §A.6 ... `fit_cf` takes no `bgnbd_model_card` argument"). |
| `src/predictive/model_card.py` | MODIFIED | (a) `ModelCard` dataclass at L165–184 gains two additive `Optional[float] = None` fields: `holdout_top_k_recall` (PRIMARY gating for CF) + `coverage_at_k` (DIAGNOSTIC only — does NOT gate). Docstring L146–155 documents both. (b) Three new fallback constants `_FALLBACK_CF_STAGE_CELL`, `_FALLBACK_CF_RELAXATION`, `_FALLBACK_CF_HYPERPARAMS` at L257–278 (mature-cell shape; matches YAML). (c) `_load_model_fit_thresholds` extended L613–711 to parse `model_fit_thresholds.cf`, emit `cf` / `cf_relaxation_factors` / `cf_hyperparameters` subdicts alongside the existing `bgnbd` / `gamma_gamma` / `survival` blocks; broader-stage HIGH-uncertainty rule inherited (CF block uses the same `resolved_stage`). |
| `src/predictive/cf.py` | NEW (634 lines) | `fit_cf(orders_df, profile, *, store_id, data_dir, seed, yaml_path) -> ModelCard`. **No `bgnbd_model_card` argument — CF independence pinned at the API surface.** Flow: (1) INSUFFICIENT_DATA gate (item-col present + stage-keyed customer / item / per-user-interaction floors); (2) time-based holdout split (60d window, capped at ¼ of span — mirrors `bgnbd.py::_time_based_holdout_split` shape); (3) sparse `csr_matrix` customer×item interaction; (4) lazy import `from implicit.als import AlternatingLeastSquares`; (5) ALS fit (`factors=als_factors, regularization=als_reg, iterations=als_iterations, random_state=seed, use_gpu=False`); (6) holdout metrics — `top-K recall @ K=10` (gating) + `coverage @ 10` (diagnostic); (7) four-state classifier; (8) parquet write only for VALIDATED/PROVISIONAL — `data/<store_id>/predictive/cf.parquet` with `customer_id`, `lookalike_customer_id`, `similarity_score`, `rank`, `parquet_schema_version=1`. Non-finite factors → REFUSED with `non_finite_factors` warning. Missing `implicit` → REFUSED with `implicit_import_failed`. Cosine top-N look-alikes computed in pure numpy (library-agnostic, fast at our scale; self-matches excluded via diagonal-to-`-inf`). |
| `src/utils.py` | MODIFIED | (a) `ENGINE_V2_ML_CF` added to `DEFAULTS` at L943–944 with default `"false"`. (b) Added to the `_coerce` bool set at L1224 (S10-T1.5 lesson binding — done at T2, NOT T2.5). |
| `tests/test_s11_t2_cf_fit.py` | NEW (370 lines) | 14 tests covering INSUFFICIENT_DATA paths (customer floor / item floor / interactions-per-user floor / missing item column), the CF-independence-from-BG/NBD contract (`test_fit_cf_signature_does_not_accept_bgnbd_model_card` + `test_independent_of_bgnbd_no_chained_refusal`), parquet write semantics (not-written for INSUFFICIENT_DATA / REFUSED; schema for VALIDATED/PROVISIONAL), simulated `implicit` ImportError → REFUSED, synthetic latent-segment ALS DGP sanity (positive control), additive ModelCard fields, and `ENGINE_V2_ML_CF` default-OFF. |
| `tests/test_s11_t2_cf_threshold_loader.py` | NEW (94 lines) | 8 tests: per-stage cell lookup (startup / growth / mature / enterprise), relaxation factors, ALS hyperparameter defaults, profile=None fallback, additive coexistence with bgnbd/gamma_gamma/survival blocks, HIGH-uncertainty broadening (MATURE→GROWTH). |

Net: **2 new files, 6 modified files.**

---

## 2. `implicit` install + pin

- Pinned `implicit>=0.7,<0.8` in `requirements.txt`.
- Installed version on dev box (mac-ARM, Python 3.14): **`implicit==0.7.3`**.
- BLAS dependency: no install-time gotcha encountered — `implicit` 0.7.x ships pre-built mac-ARM wheels; no source build required.
- Smoke import (`from implicit.als import AlternatingLeastSquares`) passes cleanly under the existing `scipy<1.13` pin — no scipy version conflict.

---

## 3. ModelCard + threshold loader extensions (recap)

- **ModelCard additive fields:** `holdout_top_k_recall: Optional[float] = None` (PRIMARY gating metric for CF) + `coverage_at_k: Optional[float] = None` (DIAGNOSTIC ONLY — operator-visible popularity-bias signal; does NOT gate acceptance). Round-trip through `engine_run.to_dict()` / `from_dict()` is automatic — both fields are `Optional[float]` so the existing `_to_jsonable` path is unchanged.
- **Threshold loader** now returns three additional keys at the top level: `cf`, `cf_relaxation_factors`, `cf_hyperparameters`. Stage resolution + HIGH-uncertainty broadening are shared with the existing `bgnbd`/`survival` paths (single `resolved_stage` consulted across all four blocks).
- Hardcoded mature-cell fallbacks are aligned to the YAML mature row (`min_customers=200`, `min_items=100`, `top_k_recall_validated=0.08`) so the loader degrades gracefully when the YAML is missing or the stage cell is absent.

---

## 4. Synthetic ALS DGP sanity check result

**Positive control — parallel to T1.4 BG/NBD ρ=0.484 and S11-T1 survival C-index=0.838.**

Latent-segment DGP: 400 customers, 150 items, 6 segments, 12 purchases per customer, 90% within-segment preference, 240d span, seed=2026, MATURE/beauty profile.

Result:

| Field | Value |
|---|---|
| `fit_status` | **VALIDATED** |
| `holdout_top_k_recall` (recall@10) | **0.3444** |
| `coverage_at_k` (coverage@10) | **1.000** |
| `n_observed` (customers post-train-split) | 400 |
| `fit_warnings` | `[]` |

recall@10 = 0.34 sits well above the MATURE VALIDATED floor (0.08) and the PROVISIONAL floor (0.03). This is the load-bearing confirmation that the CF implementation correctly recovers signal from a healthy latent-factor DGP. The test `test_synthetic_implicit_feedback_dgp_sanity` pins `fit_status in {VALIDATED, PROVISIONAL}` and `recall >= 0.03` — actual run lands VALIDATED, comfortably above both bands.

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

No diff vs HEAD. Atomic re-pin tests + synthetic fixture sha tests all green in the suite run (see §6).

---

## 6. Test / suite status

- **S11-T2 targeted tests:** 22 passed (14 in `test_s11_t2_cf_fit.py`, 8 in `test_s11_t2_cf_threshold_loader.py`).
- **Full suite (excluding the pre-existing wall-clock flake `TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh`):** **1995 passed, 14 skipped, 1 deselected, 4 xfailed, 2 xpassed** in 1548s (≈25:48).
- The deselected test is the pre-existing inventory-CSV-freshness wall-clock check (CSV is 9 days old vs `INVENTORY_MAX_AGE_DAYS=7`); dispatch explicitly directs not to chase it.
- All atomic-repin tests (`test_s6_5_t5_atomic_repin.py`, `test_s6_t1_5_winback_dormant_repin.py`, `test_s7_priors_enum_cross_pin.py`), engine_v2 shadow tests, and synthetic fixture tests (other than the deselected flake) are green.

---

## 7. CF independence preserved (explicit confirmation)

**CF is INDEPENDENT of BG/NBD. No chained refusal. Pinned at four layers:**

1. **API surface.** `fit_cf` signature contains no `bgnbd_model_card` / `bgnbd_card` argument. Pinned by `test_fit_cf_signature_does_not_accept_bgnbd_model_card` (uses `inspect.signature`).
2. **Module docstring (`src/predictive/cf.py` L38–46 + `src/predictive/__init__.py` L10–14).** Explicit "CF DOES NOT CHAIN ON BG/NBD" with the DS verdict citation (DS S11 plan review §A.6 + S11-T1.5 review §F).
3. **YAML inline comment (`config/gate_calibration.yaml` L562–565).** "DO NOT chain CF on BG/NBD" load-bearing comment co-located with the threshold block.
4. **Behavioral test (`test_independent_of_bgnbd_no_chained_refusal`).** Builds a healthy ALS DGP, constructs a REFUSED BG/NBD ModelCard alongside (deliberately NOT passed), runs `fit_cf`, and asserts the CF output is determined by the data alone with no `chained_bgnbd_refusal` warning (which is survival-only).

No `None`-as-REFUSED short-circuit copy-pasted from `src/predictive/survival.py`. No global side-channel coupling. CF runs end-to-end whether BG/NBD is OFF, REFUSED, or VALIDATED.

---

## 8. Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| `implicit` 0.7.3 mac-ARM wheel availability (BLAS deps) | Low — confirmed installs cleanly on this dev box; pre-built wheels available | KI-NEW-Q (lifetimes/scikit-survival/implicit maintenance) covers vendor-fork escape hatch (~3 days BLAS-bound) per IM plan §H |
| CF thresholds speculative-until-S14 | Known | KI-NEW-P extension at S11-T3; DS-locked at §C.5; ≥3 beta merchants per stage at S14 closure |
| Synthetic CF fixtures (healthy_beauty_240d / healthy_supplements_240d) lack co-purchase structure → CF on real fixture runs would likely land REFUSED / INSUFFICIENT_DATA | Expected (Pivot 5) | Synthetics retain honest posture; real VALIDATED evidence at S14. Substrate ships flag-OFF anyway. |
| `coverage_at_k` = 1.0 on the DGP sanity case may not reflect real-merchant catalogs | Diagnostic only | Coverage does NOT gate; surfaced as operator popularity-bias signal only. Real-merchant evidence at S14. |
| `implicit.AlternatingLeastSquares.recommend` per-customer loop inside `_top_k_recall_and_coverage` is O(N) Python | Performance — fine for fit/eval at substrate-test scale (≤ few thousand customers) | T2.5 wire is for orchestration; production scale-out is a S14 concern |
| `Python 3.14 + numpy + scipy<1.13` compatibility risk under future scipy bumps | Low — orthogonal to T2 | Pin window unchanged |

---

## 9. Behavior changes

- `engine_run.predictive_models` slot still untouched at T2 (no orchestration wire — that is T2.5). Flag default OFF; no runtime difference for any current engine invocation.
- PlayCard stubs unchanged. ReasonCode enum unchanged. No `apply_guardrails_to_injected` paths touched.
- Threshold loader now emits additional CF subdicts; callers reading the existing keys (`bgnbd`, `gamma_gamma`, `survival`, `resolved_stage`, `vertical_override_applied`) see no change.
- New `ModelCard.holdout_top_k_recall` + `coverage_at_k` fields are additive `Optional[float] = None` — existing dataclass instantiation paths and JSON serialization are byte-compatible.

---

## 10. Deviation-check statement

**Deviation check: none.**

Every dispatch-mandated artifact landed exactly per the brief: `implicit>=0.7,<0.8` pin, YAML CF block at the documented schema, `src/predictive/cf.py` with the documented `fit_cf(orders_df, profile, *, store_id, data_dir, ...)` signature (no BG/NBD coupling), ModelCard additive fields, threshold loader `cf` subdict, `ENGINE_V2_ML_CF` flag default-OFF + added to `_coerce` bool set at T2, the seven required tests in `test_s11_t2_cf_fit.py` plus the threshold-loader test file, all 5 briefing fixtures byte-identical, suite green modulo the pre-existing wall-clock flake. PlayCard stubs untouched, no ReasonCode additions, no orchestration wire-up.

---

## 11. Recommended T2.5 dispatch context (atomic flip — parallel to S11-T1.5)

When dispatching S11-T2.5, the brief should mirror the S11-T1.5 atomic-flip shape and include:

1. **Atomic single-commit flip** of `ENGINE_V2_ML_CF` `false → true` together with the orchestration wire-up. Both land in one commit so rollback is one git revert (S10-T1.5 / S11-T1.5 precedent).
2. **Orchestration wire-up at `src/main.py:1048–1086`-equivalent block** (post-survival PREDICTIVE_FIT block). Ordering: BG/NBD → G-G → survival → CF. **Do NOT read `engine_run.predictive_models["bgnbd"]`** when invoking `fit_cf` — independence pin. Write the returned `ModelCard` to `engine_run.predictive_models["cf"]`.
3. **Rollback-cleanliness test updates.** Update `tests/test_s10_t1_5_bgnbd_rollback.py` and `tests/test_s11_t1_5_survival_rollback.py` `_run_and_load` helpers to explicitly set `ENGINE_V2_ML_CF=false` so each rollback assertion remains clean under the new CF default-ON.
4. **New rollback test** `tests/test_s11_t2_5_cf_rollback.py` mirroring the survival rollback shape: with `ENGINE_V2_ML_CF=false`, `engine_run.predictive_models` MUST NOT contain a `cf` entry; all 5 briefing.html shas remain byte-identical with the flag OFF.
5. **CF-on-BG/NBD-OFF independence test** at the orchestration layer: `test_cf_runs_on_bgnbd_off_independence` — pins that CF runs to its own four-state classification when `ENGINE_V2_ML_BGNBD=false`.
6. **briefing.html byte-identity is still a hard gate** at T2.5 (flag-on path produces no PlayCard side-effects until S13).
7. **Cf parquet path** — confirm `data/<store_id>/predictive/cf.parquet` is wiped by the existing D-3 store-wipe path (no new deletion route needed per IM plan §C.7).
8. **Deviation check: none** in commit body.

---

## 12. Outputs

- **Summary file:** `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s11-t2-summary.md` (this document).
- **Code module:** `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/cf.py`.
- **Tests:**
  - `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t2_cf_fit.py`
  - `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t2_cf_threshold_loader.py`
- **Modified:** `requirements.txt`, `config/gate_calibration.yaml`, `src/predictive/__init__.py`, `src/predictive/model_card.py`, `src/utils.py`.

---

## 13. Commit message recommendation (for orchestrator)

Suggest **one commit for all S11-T2 changes** (substrate ticket; mirrors S11-T1 single-commit landing). The IM plan §D-T2 suggested commits A–E (install pin / YAML / module+schema / flag / tests) but the changes are tightly coupled and small enough that one atomic commit is cleaner; alternatively split into A (install + YAML + flag) and B (module + schema + tests). Recommended single-commit body:

```
S11-T2: CF (implicit ALS) substrate — flag-OFF + ModelCard + thresholds + tests

- requirements.txt: pin implicit>=0.7,<0.8 (installed 0.7.3 on mac-ARM; pre-built wheels, no BLAS source build needed)
- config/gate_calibration.yaml: append model_fit_thresholds.cf block with stage-keyed cells {startup/growth/mature/enterprise} + relaxation factors + ALS hyperparameters (DS-locked 2026-05-26)
- src/predictive/cf.py (NEW): fit_cf(orders_df, profile, *, store_id, data_dir, ...) — no bgnbd_model_card argument; CF is INDEPENDENT of BG/NBD per DS S11 §A.6; time-based holdout (60d); top-K recall@10 (gating) + coverage@10 (diagnostic); four-state classifier; per-customer top-N look-alikes parquet (VALIDATED/PROVISIONAL only)
- src/predictive/model_card.py: additive ModelCard.holdout_top_k_recall + coverage_at_k; threshold loader returns cf/cf_relaxation_factors/cf_hyperparameters subdicts; fallback constants aligned to YAML mature cell
- src/predictive/__init__.py: docstring update + CF independence pin
- src/utils.py: ENGINE_V2_ML_CF default "false"; added to _coerce bool set at T2 (S10-T1.5 lesson)
- tests/test_s11_t2_cf_fit.py (NEW, 14 tests): INSUFFICIENT_DATA paths, CF-independence-from-BG/NBD contract, parquet semantics, simulated implicit ImportError, synthetic latent-segment DGP sanity (VALIDATED @ recall=0.34), schema, additive fields, default-OFF
- tests/test_s11_t2_cf_threshold_loader.py (NEW, 8 tests): per-stage cells, relaxation, hyperparams, profile=None fallback, additive coexistence with bgnbd/gamma_gamma/survival, HIGH-uncertainty broadening

DGP sanity: recall@10=0.344, coverage@10=1.000, VALIDATED. Suite: 1995p/14s/1d (wall-clock flake)/4xf/2xp. All 5 briefing.html shas byte-identical.

Flag-OFF land. Orchestration wire-up + atomic flip = S11-T2.5.

Deviation check: none.
```
