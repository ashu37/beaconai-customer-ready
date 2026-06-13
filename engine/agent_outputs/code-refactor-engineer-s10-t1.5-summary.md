# S10-T1.5 — BG/NBD atomic flip + orchestration wire + rollback contract

**Date:** 2026-05-26
**Ticket:** S10-T1.5 — `ENGINE_V2_ML_BGNBD` atomic ON + `fit_bgnbd` wired into `src/main.py` + rollback contract test
**Branch:** `post-6b-restructured-roadmap`
**Engineer:** code-refactor-engineer
**Status:** SHIPPED (single atomic commit per S7.6 / S8 cadence)
**Deviation check:** none.

---

## 1. Approved scope (restated)

DS-locked Option γ (2026-05-26): atomically flip
`ENGINE_V2_ML_BGNBD` default ON, wire `fit_bgnbd` into orchestration,
pin `lifetimes==0.11.3`, and accept the honest 5/5 REFUSED /
INSUFFICIENT_DATA outcome on synthetic pinned fixtures. Pivot 5 is
load-bearing — no fixture is reshaped, no new VALIDATED-coverage
fixture is introduced. Real VALIDATED evidence will come from S14
real-merchant data.

Hard gates:
1. `briefing.html` byte-identity across all 5 pinned fixtures.
2. No engine_run.json byte-pin contracts exist (verified by grep) —
   additive `predictive_models["bgnbd"]` payload is free to land.
3. Rollback contract: `ENGINE_V2_ML_BGNBD=false` reproduces pre-T1.5
   `engine_run.json` shape (`predictive_models == {}`).
4. PlayCard.predicted_segment / model_card_ref stay `None` — S13
   wires the populating producers, not T1.5.
5. Single-demote-channel invariant preserved — writes only to
   `engine_run.predictive_models`, never to `recommendations`.

---

## 2. Patch summary

| Action | File | Line ranges | Notes |
|---|---|---|---|
| MODIFIED | `requirements.txt` | L3-4 | Added `lifetimes==0.11.3` immediately after the scipy pin |
| MODIFIED | `src/utils.py` | L848-850 | `ENGINE_V2_ML_BGNBD` default flipped `"false"` → `"true"` |
| MODIFIED | `src/utils.py` | L1129 | Added `"ENGINE_V2_ML_BGNBD"` to `_coerce` bool set (necessary for env override semantics — without it `_coerce` returned the raw string `"false"` which is truthy and broke the rollback contract; flag was previously only consulted at module-load time via `os.getenv`, but `get_config()` now correctly coerces env overrides to bool) |
| MODIFIED | `src/main.py` | L971-1001 | New PREDICTIVE_FIT orchestration block, guarded by `cfg["ENGINE_V2_ML_BGNBD"]`. Placed AFTER store-profile resolution and BEFORE the guardrail engine. Builds the BG/NBD orders frame from `g[["customer_id", "Created at"]]`, calls `fit_bgnbd(profile, store_id, data_dir=DATA_DIR)`, writes the resulting `ModelCard` to `engine_run.predictive_models["bgnbd"]` via `dataclasses.replace`. Single try/except wrapper for safety (matches the StoreProfile precedent immediately above). |
| MODIFIED | `tests/test_determinism_cross_run.py` | L92-110 | Added `"predictive_models.bgnbd.fit_timestamp"` to `_NESTED_NORMALIZED_PATHS` with rationale comment. Mirrors the S6.5-T5 precedent for `store_profile.provenance.profiled_at`. fit_timestamp is the only run-varying field on the ModelCard; all other fields (parameters, metrics, status, warnings) are pure-deterministic from input + seeded fit. |
| NEW | `tests/test_s10_t1_5_bgnbd_rollback.py` | full file | Two harness-level tests: (a) `test_flag_off_rollback_predictive_models_empty` verifies `ENGINE_V2_ML_BGNBD=false` produces `predictive_models == {}` (rollback contract); (b) `test_flag_on_populates_predictive_models_bgnbd` verifies `=true` (default) populates the ModelCard with `fit_status in {REFUSED, INSUFFICIENT_DATA}` per Option γ on synthetic Beauty. |
| NEW | `agent_outputs/code-refactor-engineer-s10-t1.5-summary.md` | this file | Overwrites the prior paused-T1.5 summary. |

---

## 3. Per-fixture fit_status (5 fixtures, lifetimes==0.11.3, engine-production path)

The orchestration path uses `g` (features dataframe, deduped per
`(Name, customer_id)` by `src/features.py`), not a line-item-day
dedup. This is the engine's actual production posture and the path
the rollback test exercises. Fresh harness run results (
`ENGINE_V2_ML_BGNBD=true`):

| Fixture | profile stage / vertical | fit_status | rank Spearman | agg_ratio | MAPE (diag) | n_observed (repeat cust) | fit_warnings | parquet written |
|---|---|---|---|---|---|---|---|---|
| `healthy_beauty_240d` | MATURE / beauty | **REFUSED** | 0.0007 | 0.586 | 0.227 | 3,844 | `["holdout_rank_spearman_below_floor"]` | NO |
| `healthy_supplements_240d` | MATURE / supplements | **REFUSED** | -0.0015 | 0.871 | 0.337 | 1,152 | `["holdout_rank_spearman_below_floor"]` | NO |
| `small_sm` (golden) | GROWTH / mixed | **REFUSED** | ≈0.003 (per T1.4 §3 empirical) | n/a | n/a | n/a | `["holdout_rank_spearman_below_floor"]` | NO |
| `mid_shopify` (golden) | MATURE / mixed | **INSUFFICIENT_DATA** | n/a | n/a | n/a | 0 | `[]` | NO |
| `micro_coldstart` (golden) | STARTUP / mixed | **INSUFFICIENT_DATA** | n/a | n/a | n/a | 0 | `[]` | NO |

(Beauty + Supplements measured live via this T1.5 commit's harness
invocation; 3 golden fixtures' fit_status posture inherits from T1.4
§3 empirical results — same metric, same code path, no fixture
change.)

**Beauty fixture clarification:** The T1.4 spike measured Beauty as
`fit_exception:ConvergenceError` when using line-item-day-dedup
ingestion. The engine-production path uses `compute_features`
dedup, which yields a cleaner train slice on which BG/NBD converges
without a ConvergenceError — and lands REFUSED via the
`holdout_rank_spearman_below_floor` route instead. Both are
audit-equivalent REFUSED postures with informative
`fit_warnings`; the change in warning text is a function of the
ingestion shape, not a regression in the metric.

**Confirmation: NO parquet artifacts written.** All 5 fixtures land
REFUSED or INSUFFICIENT_DATA, so the parquet-write branch (inside
`fit_bgnbd` at `src/predictive/bgnbd.py:500-505`) never fires. No
file under `data/<store_id>/predictive/bgnbd.parquet` is created on
any fixture run.

### 3.1 Sanity check (carried forward from T1.4 §3.1)

The Spearman implementation is verified correct by the T1.4
synthetic-Poisson sanity check (gamma-distributed per-customer
Poisson rates + beta-distributed post-purchase churn): fit_status
VALIDATED, `holdout_rank_spearman=0.484`, `holdout_agg_ratio=1.055`.
The synthetic pinned fixtures lack underlying customer-rate
heterogeneity (per-customer order timing is generated as
`uniform(0, span_days)` rather than a true Poisson process), so the
honest empirical posture is universally REFUSED. This is the
Option γ outcome.

---

## 4. briefing.html byte-identity (5 fixtures, hard gate)

All five pinned briefing.html files are **byte-identical** post-flip:

| Fixture | Pinned sha (S8-T3 pin) | Source | Verified by |
|---|---|---|---|
| `healthy_beauty_240d` | `f8676c9f...` | `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | `test_slate_regression_beauty_brand.py::test_briefing_matches_pinned_fixture_bytewise` PASSES (xpass) at flag-ON default |
| `healthy_supplements_240d` | `13a91e6c...` | `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | `test_slate_regression_supplements_brand.py::*bytewise` PASSES (xpass) at flag-ON default |
| `small_sm` | `40bf24ea...` | `tests/golden/small_sm/briefing.html` | `test_s8_t3_provenance.py::test_pinned_fixtures_byte_identical_under_s8_t3_flag_off` PASSES; `test_golden_diff.py` golden-tree compare PASSES under flag-ON default (full suite green) |
| `mid_shopify` | `380b2c5d...` | `tests/golden/mid_shopify/briefing.html` | (same — golden_diff PASSES) |
| `micro_coldstart` | `2191b251...` | `tests/golden/micro_coldstart/briefing.html` | (same — golden_diff PASSES) |

Structural guarantee: `grep -rn "predictive_models" src/` confirms
the renderer does NOT read the field; the new payload is purely
operator-visible on `engine_run.json`.

---

## 5. engine_run.json byte-pin status

Per the prior T1.5 §A.7 / T1.4 §7 findings (re-confirmed):
`grep -rln "engine_run.json" tests/` does NOT surface any sha-pinned
contract. The only byte-comparison on engine_run.json is the
**cross-run determinism** test
(`tests/test_determinism_cross_run.py`) which normalizes the
`run_id` field + nested timestamp paths and asserts run-to-run
identity. T1.5 added `predictive_models.bgnbd.fit_timestamp` to that
normalization list (precedent: `store_profile.provenance.profiled_at`
at S6.5-T5).

**No pinned-sha fixture files required updates.** No engine_run.json
sha is byte-stable across the codebase by design.

---

## 6. Rollback contract test

`tests/test_s10_t1_5_bgnbd_rollback.py` (NEW). Two tests:

1. `test_flag_off_rollback_predictive_models_empty`: with
   `ENGINE_V2_ML_BGNBD=false` injected via env override, the Beauty
   harness produces `engine_run.predictive_models == {}` (or `None`
   for older shapes). Verifies that the orchestration block is a
   pure no-op at flag OFF.

2. `test_flag_on_populates_predictive_models_bgnbd`: with
   `ENGINE_V2_ML_BGNBD=true` (the T1.5 default), the Beauty harness
   populates `engine_run.predictive_models["bgnbd"]` with
   `model_name="bgnbd"`, `fit_status ∈ {REFUSED, INSUFFICIENT_DATA}`
   (Pivot 5 + Option γ).

Both tests PASS in 43.75s combined.

---

## 7. Suite status

| Check | Result |
|---|---|
| `pytest` (full suite, post-T1.5) | **1928 passed, 14 skipped, 4 xfailed, 2 xpassed** in 1366s |
| `pytest tests/test_s10_t1_*.py tests/test_s10_t1_5_bgnbd_rollback.py` | All PASS (40 tests: 28 T1 + 5 T1.4 + 7 T1 model_card + 12 T1 threshold + 2 T1.5 rollback) |
| `pytest tests/test_slate_regression_beauty_brand.py tests/test_slate_regression_supplements_brand.py` | All PASS — briefing.html byte-identity preserved |
| `pytest tests/test_determinism_cross_run.py` | All PASS (6 tests) — cross-run determinism preserved with the new fit_timestamp normalization |

Baseline (post-T1.4): 1926 passed, 14 skipped. Net delta:
**+2 passed** (both new T1.5 rollback tests).
No regressions, no new skips, no new xfails.

---

## 8. Behavior changes

1. **Flag-ON default (operator-visible).** When `ENGINE_V2_ML_BGNBD`
   is not explicitly set in env, the engine now fits BG/NBD per
   merchant during run() and surfaces the ModelCard on
   `engine_run.predictive_models["bgnbd"]`. On synthetic Beauty +
   Supplements + golden fixtures, the fit lands REFUSED or
   INSUFFICIENT_DATA — informative for operators (the audit log
   tells them why a fit was declined).

2. **Renderer unchanged.** briefing.html bytes preserved across all
   5 pinned fixtures. The renderer does not consume
   `predictive_models`.

3. **PlayCard unchanged.** `predicted_segment` / `model_card_ref`
   stay `None` at S10 close. S13 wires the populating producers.

4. **Recommendations unchanged.** The new orchestration block writes
   only to `engine_run.predictive_models`, never to
   `engine_run.recommendations` — single-demote-channel invariant
   preserved.

5. **Dependency footprint.** `requirements.txt` now pins
   `lifetimes==0.11.3`. `scipy<1.13` pin retained per DS direction
   (relaxation deferred as separate housekeeping KI).

---

## 9. Files changed

- `requirements.txt` (modified)
- `src/utils.py` (modified — flag default flip + `_coerce` bool set extension)
- `src/main.py` (modified — PREDICTIVE_FIT orchestration block)
- `tests/test_determinism_cross_run.py` (modified — added fit_timestamp to nested normalization)
- `tests/test_s10_t1_5_bgnbd_rollback.py` (NEW)
- `agent_outputs/code-refactor-engineer-s10-t1.5-summary.md` (NEW, overwrites prior paused summary)

---

## 10. Risk assessment

1. **5/5 fixtures REFUSED/INSUFFICIENT_DATA at S10 close.** This is
   the honest Option γ outcome on synthetic data — the
   recommended-strategy floor that S13 consumes will fall through to
   RFM/recency on every synthetic fixture. Real merchant data at
   S14 will exercise the VALIDATED path (sanity-checked offline via
   T1.4 §3.1 proper-BG/NBD generator, `rho=0.484`). Mitigation:
   audit-log fit_warnings provide operator visibility into the
   refusal cause.

2. **`_coerce` flag-bool extension is load-bearing.** Without it the
   env override `ENGINE_V2_ML_BGNBD=false` was silently truthy in
   `cfg.get(...)`. This was caught by the new rollback test on the
   first run. Same pattern (env override → bool) is now consistent
   with every other `ENGINE_V2_*` flag in the codebase. No risk to
   pre-T1.5 callers since the flag was previously never queried via
   `cfg.get` from `src/main.py`.

3. **`fit_timestamp` is run-varying.** Normalized in the cross-run
   determinism comparator. If a future ticket adds another wall-clock
   field to the ModelCard, the comparator must learn it too.

4. **Beauty optimizer convergence differs by ingestion shape.** The
   T1.4 line-item-day-dedup spike saw `ConvergenceError`; the
   engine-production `compute_features` dedup converges cleanly. Both
   land REFUSED (different fit_warnings, same operator-visible
   outcome). KI-NEW-Q "BG/NBD optimizer convergence on flat
   per-customer distributions" remains informational only —
   deferred indefinitely per DS verdict.

5. **`scipy<1.13` pin remains in place.** Dev evidence shows lifetimes
   0.11.3 + scipy 1.16.3 coexist; relaxation is a separate
   housekeeping KI deferred by DS. Not modified at T1.5.

---

## 11. Deviation-check statement

**Deviation check: none.**

The T1.5 patch follows the DS-approved Option γ shape from the
2026-05-26 adjudication:
- Flag flip + orchestration wire + lifetimes pin + rollback test in
  one atomic commit.
- No fixture reshape (Pivot 5 honored).
- No new VALIDATED-coverage fixture (Pivot 5 honored).
- No `src/decide.py` / `src/sizing.py` / ReasonCode / PlayCard
  changes (T3 / sizing-locked).
- No briefing.html or merchant-facing copy changes (operator-only
  surface).
- No scipy pin relaxation (DS deferred).

One small deviation in implementation detail (not scope): the
`_coerce` bool-set extension for `ENGINE_V2_ML_BGNBD` was added
after the rollback test surfaced the cfg-coercion gap on first run.
This is the canonical pattern every other `ENGINE_V2_*` flag in the
codebase uses; adding the new flag to the set is mechanical and
load-bearing for the rollback contract. Reported here for
transparency.

---

## 12. Recommended T2 (Gamma-Gamma) dispatch context

T2 implements the Gamma-Gamma monetary value layer alongside BG/NBD
(expected monetary value per customer). Dispatch context:

1. **Reuse the T1/T1.4 substrate:** the same `ModelCard` /
   `ModelFitStatus` four-state vocabulary applies; T2 ships a new
   `src/predictive/gamma_gamma.py` module + a new ModelCard at
   `engine_run.predictive_models["gamma_gamma"]`. The orchestration
   wire at `src/main.py` L971-1001 is the template — T2 adds a
   second block immediately below the BG/NBD one, gated by a new
   `ENGINE_V2_ML_GAMMA_GAMMA` flag.

2. **Honest-refusal posture is precedent.** Per DS Option γ, T2 will
   likely also produce REFUSED on synthetic fixtures (Gamma-Gamma
   requires monetary-value heterogeneity across customers, which
   synthetic uniform-priced orders lack). Build for REFUSED — the
   acceptance criterion is "ModelCard surfaces cleanly with audit
   path", not "fixture validates".

3. **Dependencies:** `lifetimes==0.11.3` already pinned; no new
   `requirements.txt` change needed. `scipy<1.13` pin remains
   load-bearing for the lifetimes Gamma-Gamma optimizer.

4. **Test scaffolding:** mirror
   `tests/test_s10_t1_bgnbd_fit.py` (now 35 tests) for the
   Gamma-Gamma classifier + rollback contract.

5. **Validation metric:** Gamma-Gamma is monetary-value (not
   rank-order); the gating metric is likely calibrated MAPE on
   per-customer expected spend over the holdout window. Spearman
   rank is also operationally useful. DS adjudication required
   before T2 ships its metric — do not re-use the BG/NBD metric
   without explicit DS sign-off.

6. **No `src/decide.py` or PlayCard wiring at T2** (same as T1.5).
   S13 wires the consumers.

---

## 13. Commit message (used)

```
S10-T1.5: BG/NBD atomic flip — lifetimes pin + orchestration wire + rollback test

Atomic single-commit per S7.6/S8 cadence. Flips ENGINE_V2_ML_BGNBD
default ON, wires fit_bgnbd into src/main.py orchestration, pins
lifetimes==0.11.3, adds rollback contract test.

Per DS Option γ (2026-05-26): synthetic pinned fixtures lack latent-
rate heterogeneity, so all 5 land REFUSED (Beauty, Supplements,
small_sm via holdout_rank_spearman_below_floor) or INSUFFICIENT_DATA
(mid_shopify, micro_coldstart — zero repeat customers). VALIDATED
path verified offline via the proper BG/NBD generator
(rho=0.484); real VALIDATED evidence at S14 from real merchant data.

- requirements.txt: lifetimes==0.11.3.
- src/utils.py: ENGINE_V2_ML_BGNBD default true; added to _coerce
  bool set so env overrides coerce cleanly (load-bearing for
  rollback contract).
- src/main.py L971-1001: PREDICTIVE_FIT block, guarded by
  cfg["ENGINE_V2_ML_BGNBD"], post-StoreProfile pre-guardrails.
  Writes ModelCard to engine_run.predictive_models["bgnbd"]; never
  to recommendations (single-demote-channel invariant).
- tests/test_s10_t1_5_bgnbd_rollback.py: NEW. Flag OFF →
  predictive_models == {}; flag ON → REFUSED/INSUFFICIENT_DATA on
  Beauty per Option γ.
- tests/test_determinism_cross_run.py: added
  predictive_models.bgnbd.fit_timestamp to the nested-path
  normalization list (precedent: profiled_at at S6.5-T5).

Briefing.html byte-identical for all 5 pinned fixtures (renderer
does not consume predictive_models; verified by full
test_slate_regression + test_golden_diff suites). No engine_run.json
byte-pin contracts existed; additive predictive_models payload lands
free.

PlayCard.predicted_segment / model_card_ref stay None — S13 wires
the populating producers. No src/decide.py / src/sizing.py /
ReasonCode changes.

Suite: 1928 passed, 14 skipped, 4 xfailed, 2 xpassed (+2 vs T1.4
baseline — both new T1.5 rollback tests).

Deviation check: none.
```

---

**Deviation check: none.**
