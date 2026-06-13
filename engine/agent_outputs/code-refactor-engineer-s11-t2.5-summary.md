# S11-T2.5 — CF (implicit ALS) atomic flip + orchestration wire — Refactor summary

**Sprint / Ticket:** S11-T2.5 (atomic flip of the third predictive substrate landed at T2; mirrors S10-T1.5 / S10-T2.5 / S11-T1.5 cadence).
**Posture:** Single atomic commit. Flag default flip `false → true` + orchestration wire-up at `src/main.py` immediately after the survival PREDICTIVE_FIT block + rollback contract test + determinism normalization. **CF is INDEPENDENT of BG/NBD (DS-locked).**
**Engineer protocol:** changes staged only; orchestrator commits. No self-commit performed.
**Deviation check: none.**

---

## 1. Files changed (staged, not committed)

| File | Status | Line range / change |
|---|---|---|
| `src/utils.py` | MODIFIED | `ENGINE_V2_ML_CF` `DEFAULTS` entry: env default flipped `"false"` → `"true"` (S11-T2.5 2026-05-28 comment block). Already in `_coerce` bool set per T2. |
| `src/main.py` | MODIFIED | New CF PREDICTIVE_FIT block inserted IMMEDIATELY AFTER the survival block (between `[Survival] Warning...` and `# --- M5: guardrail engine ---`). Guarded by `cfg["ENGINE_V2_ML_CF"]`. Calls `fit_cf(orders, profile, store_id=..., data_dir=..., seed=0)` and writes the returned `ModelCard` to `engine_run.predictive_models["cf"]`. **NO `bgnbd_model_card` argument passed** — CF is INDEPENDENT (load-bearing comment co-located with the block). Item-column plumbing: surfaces `g["lineitem_any"]` (or `g["product"]`) as `product_title` so `fit_cf._resolve_item_column` finds it on the Shopify schema (`Lineitem name` was renamed by `compute_features`). |
| `tests/test_determinism_cross_run.py` | MODIFIED | Added `"predictive_models.cf.fit_timestamp"` to `_NESTED_NORMALIZED_PATHS` with the same precedent-comment as BG/NBD / G-G / survival. |
| `tests/test_s10_t1_5_bgnbd_rollback.py` | MODIFIED | Added `env["ENGINE_V2_ML_CF"] = "false"` in `_run_and_load` so the BG/NBD-only rollback's `predictive_models == {}` assertion stays pinned. |
| `tests/test_s10_t2_5_gamma_gamma_rollback.py` | MODIFIED | Same: added `env["ENGINE_V2_ML_CF"] = "false"`. |
| `tests/test_s11_t1_5_survival_rollback.py` | MODIFIED | Same: added `env["ENGINE_V2_ML_CF"] = "false"`. |
| `tests/test_s11_t2_5_cf_rollback.py` | NEW (~230 lines) | 4-case rollback contract: **A** flag-OFF → `cf` absent; **B** all 4 ML flags ON → CF ModelCard populated on Beauty with `fit_status` in the four-state vocabulary; **C** all 4 ML flags OFF → `predictive_models == {} or None`; **D INDEPENDENCE PIN** — `ENGINE_V2_ML_CF=true`, BG/NBD OFF → CF still fits, `fit_status` in four-state vocabulary, **`chained_bgnbd_refusal` NOT in `fit_warnings`** (the load-bearing independence assertion). |
| `tests/test_s11_t2_cf_fit.py` | MODIFIED | Renamed `test_flag_default_off` → `test_flag_default_on_after_t2_5` and inverted the assertion (`DEFAULTS["ENGINE_V2_ML_CF"] is True`). The T2 test correctly pinned the T2 flag-OFF posture; T2.5 atomically flips it and the test must follow. Docstring records the T2.5 commit-date precedent. |

Net: **1 new file (test), 7 modified files.**

---

## 2. Per-fixture CF state table

All five pinned fixtures land **INSUFFICIENT_DATA** uniformly. This matches the DS T2 review §G prediction for mid_shopify / micro_coldstart / small_sm / Supplements. For Beauty, the synthetic fixture has ~9,400 unique customers but most are one-purchase (only repeat-buyers count as `active_customers` against the MATURE floor of `min_customers=200` with `min_interactions_per_user=2`); the floor gate fires and the fit aborts cleanly before ALS runs. No fabricated `VALIDATED`. Pivot 5 posture preserved.

| Fixture | fit_status | recall@10 | coverage@10 | n_observed | training_window_days | fit_warnings |
|---|---|---|---|---|---|---|
| `small_sm` (Shopify CSV, beauty) | `INSUFFICIENT_DATA` | `None` | `None` | 2800 | 364 | `[]` |
| `mid_shopify` (Shopify CSV, beauty) | `INSUFFICIENT_DATA` | `None` | `None` | 10000 | 364 | `[]` |
| `micro_coldstart` (Shopify CSV, beauty) | `INSUFFICIENT_DATA` | `None` | `None` | 600 | 364 | `[]` |
| `healthy_supplements_240d` (synthetic) | `INSUFFICIENT_DATA` | `None` | `None` | 1199 | 259 | `[]` |
| `healthy_beauty_240d` (synthetic) | `INSUFFICIENT_DATA` | `None` | `None` | 9404 | 259 | `[]` |

(Numbers captured via direct `src.main.run()` invocation with all 4 ML flags ON, on a clean tempdir per fixture; identical methodology to T2's pin-state collection.)

**Pivot 5 implications:** No fabricated VALIDATED. The dispatch's product-level escalation (Beauty VALIDATED) does NOT apply — Beauty's `n_observed=9404` is total customers, but the `n_active_customers` (repeat buyers, ≥ 2 orders) is below the MATURE `min_customers=200` floor on the synthetic data. CF correctly surfaces INSUFFICIENT_DATA without firing ALS.

---

## 3. CF parquet artifacts

**No CF parquet artifacts written on any of the 5 fixtures.** Per `src/predictive/cf.py:558-566`, the parquet writer only fires for `fit_status in {VALIDATED, PROVISIONAL}`. All 5 fixtures land INSUFFICIENT_DATA, so no `data/<store_id>/predictive/cf.parquet` files are produced. D-3 store-wipe semantics remain a no-op for CF at this commit.

---

## 4. briefing.html sha byte-identity (all 5 fixtures)

All five pinned briefings unchanged (verified by running the byte-identity test corpus: `tests/test_golden_diff.py` [3 golden merchants] + `tests/test_slate_regression_beauty_brand.py` + `tests/test_slate_regression_supplements_brand.py` + `tests/test_s6_5_t5_atomic_repin.py` — **44 passed, 2 xfailed, 2 xpassed**).

| Fixture | sha256 (matches T2 baseline) |
|---|---|
| `tests/golden/small_sm/briefing.html` | `40bf24ea3c3632fa717293c82f66ac074d5e765ed29009b3297d2088952278e6` |
| `tests/golden/mid_shopify/briefing.html` | `380b2c5d0aa6806d81a38666c63603781e904f4e10a9fdfff72430551152d81a` |
| `tests/golden/micro_coldstart/briefing.html` | `2191b251edffbb7814e28a872e66b69e3d9289e680f077daa6ccea6a2694b2fc` |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | `13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344` |
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | `f8676c9ff7d8a7ad6de77db07fb43ce415a3e05697c4c32979dfd391280e83a3` |

The renderer does NOT read `predictive_models["cf"]` — confirmed by grep (no consumer code references the CF ModelCard outside the orchestration wire-up and tests).

---

## 5. engine_run.json sha pin status

`engine_run.json` SHAs **WILL change** for any fixture: the new `predictive_models["cf"]` ModelCard entry is additive. **No `engine_run.json` byte-pin contract exists in the test corpus** (per S10-T1.5 / S10-T2.5 / S11-T1.5 precedent). The determinism cross-run test (`tests/test_determinism_cross_run.py`) is the only `engine_run.json` byte-comparator and it now normalizes `predictive_models.cf.fit_timestamp` alongside the existing three timestamps — verified passing post-edit.

---

## 6. Rollback contract test (4 cases, especially D — independence pin)

New file `tests/test_s11_t2_5_cf_rollback.py`. All 4 cases passing:

| Case | What it pins | Result |
|---|---|---|
| **A** `test_flag_off_rollback_cf_absent` | `ENGINE_V2_ML_CF=false`, others ON → `"cf"` not in `predictive_models` | PASS |
| **B** `test_flag_on_populates_cf_on_beauty` | All 4 ML flags ON → `predictive_models["cf"]` populated, `fit_status` in four-state vocabulary, schema fields (`holdout_top_k_recall`, `coverage_at_k`) present | PASS |
| **C** `test_all_flags_off_predictive_models_empty` | All 4 ML flags OFF → `predictive_models == {}` or None | PASS |
| **D** `test_cf_runs_independently_when_bgnbd_off` | **INDEPENDENCE PIN.** CF ON, BG/NBD OFF → CF still fits independently; `fit_status` in four-state vocabulary; **`chained_bgnbd_refusal` NOT in `fit_warnings`** (this warning is survival-only — its presence here would indicate the survival/G-G chained-input pattern was incorrectly copied into the CF wire) | PASS |

---

## 7. Determinism test update

`tests/test_determinism_cross_run.py:_NESTED_NORMALIZED_PATHS` extended:

```
"store_profile.provenance.profiled_at",
"predictive_models.bgnbd.fit_timestamp",
"predictive_models.gamma_gamma.fit_timestamp",
"predictive_models.survival.fit_timestamp",
"predictive_models.cf.fit_timestamp",  # NEW (S11-T2.5)
```

`test_engine_run_json_byte_identical_after_normalization` passes (Beauty fixture, two runs, byte-identical after normalization).

---

## 8. Explicit confirmation: CF orchestration wire does NOT pass `bgnbd_model_card`

**Confirmed.** The new block at `src/main.py` immediately after `print(f"[Survival] Warning...")`:

- Reads `engine_run.store_profile` (for stage-keyed threshold lookup).
- Builds an `orders_df` from `g["customer_id"]`, `g["Created at"]`, plus item column (`lineitem_any` aliased to `product_title`).
- Calls `_fit_cf(_orders_for_cf, _profile_for_cf, store_id=..., data_dir=..., seed=0)`.
- **Does NOT** read `engine_run.predictive_models["bgnbd"]`.
- **Does NOT** pass any `bgnbd_model_card` / `bgnbd_card` argument.
- **Does NOT** chain on BG/NBD's fit_status in any way.

This is pinned at four layers (carried over from T2 plus the new orchestration-layer test):

1. **API surface.** `fit_cf` signature has no `bgnbd_model_card` parameter. (`test_fit_cf_signature_does_not_accept_bgnbd_model_card`)
2. **Module docstring.** `src/predictive/cf.py:38-46` and `src/predictive/__init__.py`.
3. **YAML inline comment.** `config/gate_calibration.yaml:562-565`.
4. **Behavioral test (orchestration layer).** `tests/test_s11_t2_5_cf_rollback.py::test_cf_runs_independently_when_bgnbd_off` (Case D — asserts CF fits with BG/NBD OFF and `chained_bgnbd_refusal` is absent from `fit_warnings`).
5. **Behavioral test (module layer).** T2's `test_independent_of_bgnbd_no_chained_refusal` (unchanged).

The orchestration wire intentionally diverges from the Gamma-Gamma block at L1018-1046 and the survival block at L1063-1087 — the new code-comment at the top of the CF block calls this out load-bearingly.

---

## 9. Suite status

- **S11-T2.5 targeted tests:** all 4 cases in `test_s11_t2_5_cf_rollback.py` PASS (82s wall).
- **Prior rollback + determinism (post-edit):** `test_s10_t1_5_bgnbd_rollback.py` (2), `test_s10_t2_5_gamma_gamma_rollback.py` (4), `test_s11_t1_5_survival_rollback.py` (4), `test_s11_t2_5_cf_rollback.py` (4), `test_determinism_cross_run.py` (6) → **20 passed in 330s**.
- **Briefing byte-identity gate (all 5 fixtures):** `test_golden_diff.py` (3) + `test_slate_regression_beauty_brand.py` + `test_slate_regression_supplements_brand.py` + `test_s6_5_t5_atomic_repin.py` → **44 passed, 2 xfailed, 2 xpassed in 172s**.
- **Full suite (initial run, 1636s / ≈27:16):** 1998 passed, 14 skipped, 4 xfailed, 2 xpassed; 2 failed: (i) `tests/test_s11_t2_cf_fit.py::test_flag_default_off` (T2 test asserting the now-flipped default — fixed by renaming to `test_flag_default_on_after_t2_5` and inverting the assertion); (ii) `tests/test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh` (pre-existing wall-clock flake — inventory CSV is 9d old vs `INVENTORY_MAX_AGE_DAYS=7`; dispatch directs not to chase). After the T2 test fix: **expected 1999 passed, 14 skipped, 1 failed (wall-clock flake), 4 xfailed, 2 xpassed.** Targeted re-run of `test_s11_t2_cf_fit.py` post-fix: **13 passed in 0.96s.**

---

## 10. Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| All 5 fixtures uniformly INSUFFICIENT_DATA — no VALIDATED / PROVISIONAL evidence path exercised in production engine | Low — exactly the Pivot 5 posture. Real VALIDATED evidence is deferred to S14 with ≥3 beta merchants. T2's synthetic latent-segment DGP test (`test_synthetic_implicit_feedback_dgp_sanity`) is the standing positive control that the fit machinery works end-to-end. | Substrate ships with the substrate-level positive control in place; orchestration ships with the four-state-vocabulary contract test. |
| ALS runtime cost when a future real-merchant fixture lands in PROVISIONAL/VALIDATED state | Out of scope at T2.5 (no fixture exercises this code path). | Performance characterization deferred to S14. |
| `implicit` mac-ARM wheel maintenance | Tracked under KI-NEW-Q (lifetimes / scikit-survival / implicit maintenance escape hatch). | No change at T2.5. |
| Determinism contract gets brittle as new ML substrates land | Low — same nested-path pattern as BG/NBD / G-G / survival; pattern is well-understood and stamped out. | Pattern will repeat if a 5th substrate lands. |

---

## 11. Behavior changes

- `ENGINE_V2_ML_CF` default `"false"` → `"true"`. The CF orchestration block at `src/main.py` now fires on every engine run by default.
- `engine_run.predictive_models["cf"]` is now populated with a CF `ModelCard` on every run; serialized into `engine_run.json` (additive — existing readers ignore unknown keys).
- `PlayCard.predicted_segment` / `PlayCard.model_card_ref` remain `None` (S13 work).
- `ReasonCode` enum unchanged (no additions).
- `apply_guardrails_to_injected` paths untouched.
- `engine_run.recommendations` is NEVER written by the CF wire — single-demote-channel invariant preserved (writes only to `predictive_models["cf"]`).
- All 5 briefing.html files are byte-identical to the pre-T2.5 baseline.

---

## 12. Deviation-check statement

**Deviation check: none.**

Every dispatch-mandated artifact landed exactly per the brief: single atomic commit shape (flag flip + orchestration wire + rollback test + determinism normalization staged together for one orchestrator commit); CF block sits IMMEDIATELY AFTER the survival block at `src/main.py`; no `bgnbd_model_card` argument passed (independence preserved at orchestration, module API, docstring, YAML, and behavioral test layers); briefing.html byte-identical for all 5 fixtures; engine_run.json shas drift only by the additive `predictive_models["cf"]` entry; determinism test extended with the `cf.fit_timestamp` nested path; prior rollback tests updated for the new flag default; new 4-case CF rollback test including the independence-pin Case D.

No deviations:
- PlayCard not modified.
- `src/decide.py`, `src/sizing.py`, `src/engine_run.py` ReasonCode enum not modified.
- No merchant-facing copy added.
- No fixtures reshaped.
- No new fixtures added.
- CF semantics (T2 logic) unchanged.
- `scipy<1.13` pin not relaxed.
- Wall-clock flake not chased.

---

## 13. Recommended T3 (sprint-close) dispatch context

Sprint 11 (CF substrate sprint) closes at T3. Recommended dispatch context for the closeout:

1. **No new substrates.** S11-T3 is a sprint-close / doc-sweep / KI-update ticket, not a fourth substrate landing.
2. **Update `KNOWN_ISSUES.md`** to record the per-fixture CF INSUFFICIENT_DATA observation as expected-not-a-bug (Pivot 5 posture; real evidence at S14).
3. **Update `STATE.md`** to list CF as the third orchestrated predictive substrate (after BG/NBD and G-G+survival), flag-default ON, INSUFFICIENT_DATA on all 5 fixtures.
4. **Update `ROADMAP.md`** for S12 / S13 sequencing: S13 wires `PlayCard.predicted_segment` + `model_card_ref` for the first substrate (likely BG/NBD or G-G); CF audience-builder consumption is a separate S13 ticket.
5. **Update `memory.md`** with the standard template-shape entry for S11-T2.5 receipt + this summary file path.
6. **DS architect sign-off** on the per-fixture state report (this summary's §2 table). The Pivot 5 caveat ("not all REFUSED is allowed; INSUFFICIENT_DATA is too") is honored; no fabricated VALIDATED.
7. **Founder briefing on the synthetic-data ceiling.** The fact that CF's INSUFFICIENT_DATA on synthetic Beauty is driven by repeat-buyer scarcity (most synthetic customers are one-purchase) is a useful data point for the S14 beta-onboarding fixture-design question. Surface this if the founder asks why CF didn't land PROVISIONAL on Beauty (it's the same Pivot 5 root cause as BG/NBD's REFUSED).

---

## 14. Outputs

- **Summary file:** `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s11-t2.5-summary.md` (this document).
- **Modified:** `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py`, `/Users/atul.jena/Projects/Personal/beaconai/src/main.py`, `/Users/atul.jena/Projects/Personal/beaconai/tests/test_determinism_cross_run.py`, `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t1_5_bgnbd_rollback.py`, `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t2_5_gamma_gamma_rollback.py`, `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t1_5_survival_rollback.py`.
- **New:** `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t2_5_cf_rollback.py`.

---

## 15. Product-level finding (if any)

**None.** No fixture landed VALIDATED. The Pivot 5 escalation path ("first VALIDATED on non-DGP-tuned synthetic; surface to founder; do not pre-celebrate") does NOT trigger. All 5 fixtures cleanly INSUFFICIENT_DATA — engineering / DS contract preserved; honest data posture maintained.

---

## 16. Commit message recommendation (for orchestrator)

Single atomic commit (mirrors S11-T1.5 / S10-T2.5 / S10-T1.5 cadence):

```
S11-T2.5: CF atomic flip — ENGINE_V2_ML_CF=true + orchestration wire (INDEPENDENT of BG/NBD)

- src/utils.py: ENGINE_V2_ML_CF default "false" -> "true" (S11-T2.5 2026-05-28)
- src/main.py: new CF PREDICTIVE_FIT block IMMEDIATELY AFTER the survival block; guarded by ENGINE_V2_ML_CF; calls fit_cf(orders, profile, store_id=..., data_dir=..., seed=0); writes ModelCard to engine_run.predictive_models["cf"]. NO bgnbd_model_card argument — CF is INDEPENDENT (DS-locked S11 plan review §A.6). Item column plumbed from g["lineitem_any"] / g["product"] surfaced as product_title.
- tests/test_determinism_cross_run.py: normalize predictive_models.cf.fit_timestamp (4th nested timestamp).
- tests/test_s10_t1_5_bgnbd_rollback.py + tests/test_s10_t2_5_gamma_gamma_rollback.py + tests/test_s11_t1_5_survival_rollback.py: add env["ENGINE_V2_ML_CF"] = "false" so the prior rollback `predictive_models == {}` assertions stay pinned under the new CF default-ON.
- tests/test_s11_t2_5_cf_rollback.py (NEW, 4 cases): A flag-OFF -> cf absent; B all 4 ML flags ON -> CF ModelCard in four-state vocab; C all 4 OFF -> predictive_models == {}; D INDEPENDENCE PIN — CF ON, BG/NBD OFF -> CF still fits, chained_bgnbd_refusal NOT in fit_warnings.

Per-fixture CF state (all 5): INSUFFICIENT_DATA uniformly. n_observed {small_sm 2800, mid_shopify 10000, micro_coldstart 600, healthy_supplements_240d 1199, healthy_beauty_240d 9404}. recall@10 None on all (floor gate fires before ALS runs — repeat-buyer scarcity on synthetic data; Pivot 5 posture). No CF parquet artifacts written. briefing.html byte-identical on all 5.

Deviation check: none.
```
