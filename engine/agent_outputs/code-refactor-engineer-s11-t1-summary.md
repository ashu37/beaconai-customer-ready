# S11-T1 — Cox PH survival substrate + ModelCard ext + business-stage thresholds (FLAG-OFF land)

**Date:** 2026-05-26
**Ticket:** S11-T1 — `ENGINE_V2_ML_SURVIVAL` flag-OFF substrate
**Branch:** `post-6b-restructured-roadmap`
**Engineer:** code-refactor-engineer
**Deviation check:** none.

---

## 1. Approved scope (restated)

Implement the Cox PH survival predictive substrate behind a new flag
`ENGINE_V2_ML_SURVIVAL` (default OFF). T1 ships:

1. `scikit-survival>=0.22,<0.24` added to `requirements.txt`; pip
   install verified end-to-end on mac-ARM / Python 3.14.
2. New `model_fit_thresholds.survival` block in
   `config/gate_calibration.yaml` per IM plan §B.5 v2 (stage-keyed
   floors + relaxation factors; dual-gate c_index + brier@90d).
3. New module `src/predictive/survival.py` with
   `fit_survival(transactions_df, profile, bgnbd_model_card) -> ModelCard`
   — chained-refusal on BG/NBD REFUSED/INSUFFICIENT_DATA, four-state
   classifier with dual gate, parquet writer.
4. Additive `ModelCard` fields: `holdout_c_index`,
   `holdout_brier_score_90d`. `_load_model_fit_thresholds` now returns
   `survival` + `survival_relaxation_factors` subdicts.
5. New flag `ENGINE_V2_ML_SURVIVAL` (default OFF) in `src/utils.py`
   `DEFAULTS` + `_coerce` bool set.
6. 22 new tests across two files (threshold loader + fit shape).

**Out of scope (T1.5):** flag flip, `src/main.py` orchestration wire,
PlayCard.predicted_segment / model_card_ref population, ReasonCode
additions (S10-T3 codes cover survival per DS verdict §(a)-12), CF
substrate (T2).

---

## 2. Patch summary

| Action | File | Notes |
|---|---|---|
| MODIFIED | `requirements.txt` | `scikit-survival>=0.22,<0.24` added (L5); `scipy<1.13` and `lifetimes==0.11.3` pins preserved |
| MODIFIED | `config/gate_calibration.yaml` | Append `model_fit_thresholds.survival` block (L519-538) with per-stage cells + relaxation_factors |
| MODIFIED | `src/utils.py` | New flag `ENGINE_V2_ML_SURVIVAL` default `false` (after L877); added to `_coerce` bool set (L1189) |
| MODIFIED | `src/predictive/model_card.py` | Additive ModelCard fields `holdout_c_index`, `holdout_brier_score_90d`; `_FALLBACK_SURVIVAL_STAGE_CELL` + `_FALLBACK_SURVIVAL_RELAXATION`; loader returns `survival` + `survival_relaxation_factors` subdicts |
| MODIFIED | `src/predictive/__init__.py` | Docstring extended to mention survival |
| NEW | `src/predictive/survival.py` | `fit_survival` + helpers; lazy `sksurv` import; dual-gate classifier; parquet writer |
| NEW | `tests/test_s11_t1_survival_threshold_loader.py` | 8 tests — stage cells, relaxation, fallback, broadening, additive return |
| NEW | `tests/test_s11_t1_survival_fit.py` | 14 tests — chained refusal (3), INSUFFICIENT_DATA (3), no-parquet on REFUSED/INSUFFICIENT (2), sksurv import REFUSED (1), synthetic Cox DGP VALIDATED (1), dual-gate invariant (1), parquet write (1), additive ModelCard fields (1), flag default (1) |

Total tests added: **22 passed**.

Line ranges (post-edit):
- `src/predictive/survival.py`: full new module (~700 LoC including docstrings).
- `src/predictive/model_card.py`: ModelCard fields at L156-167; `_FALLBACK_SURVIVAL_*` at L227-243; loader survival block at L489-561.
- `config/gate_calibration.yaml`: survival block at L519-538.
- `src/utils.py`: flag definition L878-911 (approx); `_coerce` set L1189.

---

## 3. `scikit-survival` install + dependency posture

**Install result:** `scikit-survival 0.23.1` (latest in the `>=0.22,<0.24` range) installed cleanly on mac-ARM / Python 3.14.0 via the project's pipenv venv (`/Users/atul.jena/.local/share/virtualenvs/beaconai-2t4ze8Gg`). Build wheels generated for `scikit-survival`, `scikit-learn`, `ecos`; transitive deps `joblib`, `numexpr`, `osqp`, `threadpoolctl`, `setuptools` installed without conflict.

**Smoke test confirmed:**
```python
from sksurv.linear_model import CoxPHSurvivalAnalysis
from sksurv.metrics import concordance_index_censored, integrated_brier_score
```
all import cleanly.

**Coexistence with `lifetimes==0.11.3`:** verified — `BetaGeoFitter` fits a synthetic frame end-to-end under the post-install environment.

**scipy version posture (advisory):** the dev venv shipped `scipy 1.16.3` BEFORE this ticket (under Python 3.14 the `scipy<1.13` pin in `requirements.txt` could not be enforced because scipy 1.12 has no Python-3.14 wheels and source-builds fail). This is a pre-existing condition that S10-T1's hard pin is silently bypassed by the venv. `lifetimes` still functions under scipy 1.16.3 (BG/NBD fits cleanly in smoke test); the pin remains in `requirements.txt` per dispatch (preserved unchanged). On Python ≤ 3.12 the pin holds normally. **No T1 change here** — flagged for operator awareness, not blocking.

---

## 4. Synthetic Cox PH DGP sanity check (required by dispatch — analog to T1.4 ρ=0.484)

Generated 1500 customers with gamma-distributed Poisson purchase rates (shape=1.5, scale=0.04 → mean 0.06 events/day) over a 360-day span; inter-purchase times Exponential(rate). The true rate heterogeneity is what Cox PH on (log_frequency, log_recency_over_T) covariates should recover.

| Field | Value |
|---|---|
| rows (orders) | 30,878 |
| unique customers | 1,500 |
| customers in survival frame (train + non-degenerate time) | 1,497 |
| events observed (holdout-window purchase) | 1,311 |
| **fit_status** | **VALIDATED** |
| **C-index** | **0.838** |
| **Brier @ 90d** | **0.044** |
| Cox PH coefs | log_frequency = 1.22, log_recency_over_T = 4.73 |

C-index 0.838 is well above the MATURE VALIDATED floor (0.63) and PROVISIONAL floor (0.55); Brier 0.044 is well below the VALIDATED max (0.25). The dual gate clears comfortably. This confirms the survival implementation correctly recovers signal from a proper Cox PH DGP.

This is the **DS-required positive control**: parallel to T1.4's BG/NBD ρ=0.484 sanity result on the proper BG/NBD generator. The 5 pinned synthetic fixtures will (per Pivot 5 / Option γ extension) still land REFUSED or INSUFFICIENT_DATA at T1.5 because their order timing is uniform-uniform (no per-customer rate heterogeneity); that is the honest empirical truth, not an implementation bug. Real merchant data with true rate heterogeneity should clear the gate.

---

## 5. Tests / checks run

- **S11-T1 module tests:** `PYTHONPATH=. pytest tests/test_s11_t1_*.py`
  → **22 passed**. No skips. Synthetic Cox PH DGP sanity passes
  VALIDATED.

- **Full suite:** `PYTHONPATH=. pytest`
  → **1969 passed, 14 skipped, 4 xfailed, 2 xpassed, 1 failed** in
  1559s (≈26 min). The 1 failure is
  `test_synthetic_fixtures_8_11.py::test_inventory_updated_at_is_fresh`
  — the pre-existing wall-clock flake explicitly called out in the
  dispatch ("DO NOT chase"). +22 net new tests vs S10 baseline (1947 →
  1969 passing).

- **Pinned briefing.html byte identity (load-bearing):**
  `tests/test_s8_t3_provenance.py::test_pinned_fixtures_byte_identical_under_s8_t3_flag_off`
  → **PASS**. All five pinned briefing.html files
  (`healthy_beauty_240d`, `healthy_supplements_240d`, `small_sm`,
  `mid_shopify`, `micro_coldstart`) sha256 unchanged.

- **Full-pipeline regen tests:** `tests/test_slate_regression_beauty_brand.py`
  + `tests/test_golden_diff.py` → **21 passed, 1 xpassed**. All 5
  fixtures regenerate byte-identical end-to-end.

- **Flag default check:** `ENGINE_V2_ML_SURVIVAL` default `False`
  verified via `tests/test_s11_t1_survival_fit.py::test_flag_default_off`.

- **Renderer reads `predictive_models["survival"]`?** NO — `grep -rn
  "survival" src/main.py src/engine_run.py` shows zero renderer
  references; only `engine_run.py` schema bucket
  (`predictive_models: Dict[str, Any]`) and the new `survival.py`
  writer touch the key.

---

## 6. Behavior changes

- **Flag OFF (default):** zero behavior change. No new code path runs
  from `src/main.py` (no orchestration wire — that is T1.5).
  `engine_run.predictive_models` continues to serialize without a
  `survival` key on every pinned fixture. Renderer untouched.
  Briefing.html shas unchanged.

- **Flag ON (T1.5 will flip):** `fit_survival` becomes callable from
  the predictive-fit step (which itself is wired in T1.5, not T1). At
  T1 the function is callable from tests but not invoked from
  `src/main.py` orchestration.

- **ModelCard additive fields:** `holdout_c_index` +
  `holdout_brier_score_90d` default to `None` for non-survival
  ModelCards (BG/NBD + Gamma-Gamma). Round-trips byte-identical on
  pre-S11 fixtures (additive — None elides during `_to_jsonable`).

---

## 7. Artifacts added

- `src/predictive/survival.py` (NEW)
- `tests/test_s11_t1_survival_threshold_loader.py` (NEW)
- `tests/test_s11_t1_survival_fit.py` (NEW)
- `agent_outputs/code-refactor-engineer-s11-t1-summary.md` (this file)

Config / requirements edits:
- `requirements.txt` L5: `scikit-survival>=0.22,<0.24`.
- `config/gate_calibration.yaml` L519-538: `model_fit_thresholds.survival` block.
- `src/utils.py`: `ENGINE_V2_ML_SURVIVAL` flag (after L877) + `_coerce` set membership (L1189).
- `src/predictive/model_card.py`: ModelCard schema extension + threshold-loader survival subdict.
- `src/predictive/__init__.py`: docstring extension.

No `src/main.py`, `src/sizing.py`, `src/decide.py`, `src/guardrails.py`,
`src/engine_run.py`, or PlayCard schema edits.

---

## 8. Remaining risks

1. **scipy `<1.13` pin is silently bypassed on Python 3.14 dev envs.**
   The pin is preserved in `requirements.txt` per dispatch, but
   Python-3.14 wheels for scipy 1.12 do not exist and source-builds
   fail. The current venv ships scipy 1.16.3 by necessity. `lifetimes`
   still fits cleanly under that scipy; `scikit-survival 0.23.1`
   declares `scipy>=1.3.2` (open upper bound) so no conflict on the
   install side. **No action requested at T1** — this is a
   pre-existing condition. Founder may want to revisit at S15+
   (post-beta), as the pin's load-bearing claim against scipy 1.13's
   `lifetimes` regression no longer holds on the dev machine.

2. **Synthetic pinned fixtures will land REFUSED / INSUFFICIENT_DATA on
   survival at T1.5.** This is the predicted Pivot 5 / Option γ
   outcome — same posture as T1.4 reported for BG/NBD (3 REFUSED + 2
   INSUFFICIENT_DATA). The DGP-sanity test confirms the
   implementation is correct; the fixtures lack the per-customer rate
   heterogeneity Cox PH requires. Real merchant data at S14 calibration
   is the true validation surface. T1.5 must accept honestly per
   Pivot 5.

3. **Brier-score computation uses a two-point integrated form when
   `sksurv.metrics.brier_score` (single-time) is unavailable.** The
   implementation prefers `brier_score` over `integrated_brier_score`
   because the latter needs ≥2 time points and gating is at a single
   horizon (90d). Both branches are present and guarded; the
   synthetic DGP exercises the `brier_score` path successfully
   (Brier=0.044). On odd holdout-window shapes where 90d lies near a
   domain boundary, the integration path may have minor numerical
   sensitivity — acceptable per DS verdict (Brier is a gate, not a
   downstream magnitude).

4. **`expected_days_to_next_purchase` parquet column uses a 50%-survival
   inversion via a per-customer grid sample.** sksurv StepFunction
   objects don't support direct quantile inversion. The grid spans
   each function's observed domain (1 to upper-bound) at 200 points;
   the first time at which S(t) ≤ 0.5 is taken. Right-censored when
   no grid time clears the 0.5 boundary (capped at domain upper
   bound). This is a per-customer convenience surface S13 may consume;
   precision is sufficient for ranking but not for week-level
   magnitudes — documented in the writer docstring.

5. **No `src/main.py` orchestration test.** T1.5 will add the
   end-to-end harness test (engine_run.predictive_models["survival"]
   populated when flag is ON, chained-refusal observable when BG/NBD
   is REFUSED).

6. **PlayCard.predicted_segment + model_card_ref stay None.** No S11-T1
   consumer of the survival ModelCard. S13 wires the populating
   producers per IM plan.

---

## 9. Follow-up work (T1.5 dispatch context)

1. **Atomic flip:** `ENGINE_V2_ML_SURVIVAL` default `false → true`.
2. **`src/main.py` wire:** add a new survival-fit step **inside the
   existing BG/NBD + G-G orchestration block** (per IM plan §B / §D-T1
   reference at `src/main.py:971-1046`). Pass the same-run BG/NBD
   ModelCard to `fit_survival` as the `bgnbd_model_card` argument
   (chained-refusal input). Write the resulting ModelCard into
   `engine_run.predictive_models["survival"]`. **Single-demote-channel
   invariant preserved** — writes only to predictive_models, never to
   `engine_run.recommendations`.
3. **Fixture re-pin posture:** briefing.html shas MUST stay
   byte-identical for all 5 fixtures (renderer doesn't read
   `predictive_models`). Engine_run.json shapes will additively gain a
   `predictive_models.survival` ModelCard entry on Beauty + Supplements
   + small_sm; mid_shopify + micro_coldstart will see
   `INSUFFICIENT_DATA` ModelCards. No `engine_run.json` byte-identity
   contract exists in the test suite (only briefing.html), so this is
   additive.
4. **`requirements.txt` is ALREADY DONE for T1.5** — scikit-survival
   pin landed at T1 (per dispatch §"Commit A"). T1.5 does NOT need to
   touch requirements.txt.
5. **Expected fixture statuses under flag-ON (per honest synthetic
   posture):** 3-5 of 5 land REFUSED or INSUFFICIENT_DATA. This is
   the documented Pivot 5 / Option γ extension outcome — DS sign-off
   for shipping with that outcome was previously granted at S10-T1.5
   close (parallel argument applies here). Founder may pre-decide
   whether T1.5 fixture re-pin is needed or whether the absence of an
   engine_run.json byte-pin makes T1.5 effectively a one-commit flag
   flip + main.py wire.

No founder blockers. No DS-architect blockers. No engineering
ambiguities.

---

## 10. Commit message (recommended; orchestrator commits, NOT me)

```
S11-T1: Cox PH survival substrate + ModelCard ext + thresholds (FLAG-OFF land)

New module src/predictive/survival.py wraps scikit-survival's
CoxPHSurvivalAnalysis behind ENGINE_V2_ML_SURVIVAL (default OFF).
fit_survival(orders_df, profile, bgnbd_model_card) returns a typed
ModelCard under the four-state ModelFitStatus vocabulary; chained
refusal short-circuits when BG/NBD is REFUSED or INSUFFICIENT_DATA;
dual gate on C-index + Brier@90d per DS verdict 2026-05-26.

- scikit-survival>=0.22,<0.24 in requirements.txt; lifetimes + scipy
  pins preserved. scikit-survival 0.23.1 installs cleanly on mac-ARM /
  Python 3.14.
- model_fit_thresholds.survival block in gate_calibration.yaml with
  stage-keyed cells (c_index VALIDATED 0.62 startup/growth, 0.63
  mature/enterprise; Brier@90d ≤ 0.25) and relaxation factors
  (c_index 0.55 / Brier 0.35).
- ModelCard additive fields: holdout_c_index, holdout_brier_score_90d.
  _load_model_fit_thresholds returns survival + survival_relaxation_factors
  subdicts alongside bgnbd + gamma_gamma.
- ENGINE_V2_ML_SURVIVAL flag default OFF; added to _coerce bool set
  (S10-T1.5 lesson binding — flag definition lands at T1, not T1.5).
- 22 new tests: chained refusal (3), INSUFFICIENT_DATA gates (3),
  parquet write-only-for-VALIDATED/PROVISIONAL, dual-gate VALIDATED
  invariant, additive ModelCard fields, threshold loader (8). Synthetic
  Cox PH DGP sanity passes VALIDATED with C-index=0.838, Brier@90d=0.044
  on 1311 events / 1497 customers — confirms implementation.
- Full suite: 1969 passed, 14 skipped, 4 xfailed, 2 xpassed, 1 failed
  (pre-existing test_inventory_updated_at_is_fresh wall-clock flake;
  not chased per dispatch).
- All 5 pinned briefing.html fixtures byte-identical
  (test_s8_t3_provenance + test_slate_regression_beauty_brand +
  test_golden_diff all PASS).
- DS-locked substitution: scikit-survival (NOT lifelines) for the new
  Cox PH surface per ds-architect-s11-plan-review.md §(b).
- PlayCard.predicted_segment + model_card_ref stay None. No ReasonCode
  additions (S10-T3 codes cover survival per DS verdict §(a)-12).
- No orchestration wire — T1.5.
- Single-demote-channel invariant preserved (writes only to
  engine_run.predictive_models).

Deviation check: none.
```

---

**Deviation check: none.**
