# S10-T2 Summary — Gamma-Gamma fit module (re-submitted post DS review)

**Status:** Re-submitted post DS-rejection on 2026-05-26. One required fix
applied. Patch otherwise unchanged.

**Deviation check:** none. Single DS-required bug fix +
holdout-empty warning. No scope expansion. T2.5 atomic flip remains
out of scope. Flag stays OFF.

## DS-diagnosed bug (original review)

`src/predictive/gamma_gamma.py::_compute_holdout_metrics` computed:

```python
pred_total = pred * train_summary["frequency"]
```

`pred` was the G-G **per-transaction** posterior mean. Multiplying by
**train-window frequency** produced predicted TRAINING-window total
spend, while `obs_total` is HOLDOUT-window spend (window_days ≈
min(30, span/4) ≈ 30 of ~240 days). The resulting ratio was
time-window-mismatched by roughly `train_span / holdout_window ≈ 7-8x`.
The observed pre-fix sanity-check agg_ratio of 6.02 at seed=7 is
exactly what this bug predicts — not a property of the synthetic DGP.

This masqueraded as "Option γ honest refusal" but was an implementation
bug.

## Fix shape applied

**Chose:** BG/NBD-card-conditioned form with per-day-rate proxy
fallback (DS-recommended primary + DS-approved fallback).

Predicted total spend over the holdout window now uses BG/NBD's
`conditional_expected_number_of_purchases_up_to_time(window_days,
freq, recency, T)` per customer:

```python
pred_total_holdout = pred_per_order_spend * pred_purchases_holdout
```

Implementation:

1. `_compute_holdout_metrics` signature extended (keyword-only):
   `window_days: float`, `train_span_days: float`,
   `bgnbd_params: Optional[Dict[str, float]] = None`.
2. When `bgnbd_params` has finite `r/alpha/a/b`, re-instantiate a
   `lifetimes.BetaGeoFitter(penalizer_coef=0.0)`, set its `.params_`
   from the dict (matches T1.4's pathway), and call
   `conditional_expected_number_of_purchases_up_to_time(window_days,
   freq, recency, T)`.
3. Fallback (no BG/NBD params, or any exception in the rigorous path):
   per-day-rate proxy `train_freq * (window_days / train_span_days)`.
4. `fit_gamma_gamma` extracts `bgnbd_params` from the chained-refusal
   input's `ModelCard.parameters` (filtered to finite floats) and
   derives `train_span_days` from the train-slice `order_date` range.

The chained-refusal input is already in scope (T2 dispatch), so no
new plumbing was added — the existing argument carries the BG/NBD
parameters.

## Sanity-check re-run (synthetic G-G DGP, seed=7)

Run via `tests/test_s10_t2_gamma_gamma_fit.py::test_validated_or_provisional_on_synthetic_gamma_gamma_generator`
inputs (n_customers=600, seed=7, freq_monetary_correlation=0.0):

| metric        | pre-fix | post-fix |
|---------------|---------|----------|
| fit_status    | REFUSED (`holdout_agg_ratio_out_of_band`) | **PROVISIONAL** |
| Spearman      | ~0.17   | **0.1677** |
| agg_ratio     | **6.02**  | **0.8643** |
| n_observed    | 501     | 501      |
| fit_warnings  | [agg_ratio out-of-band] | **[]**   |

Meets DS re-acceptance criterion: Spearman ∈ [0.10, 0.20) AND
agg_ratio ∈ [0.4, 1.6] → PROVISIONAL. No escalation needed.

Note on this specific run: the test's `_make_bgnbd_card` helper builds
a synthetic BG/NBD ModelCard with empty `parameters={}` (it does not
fit an actual BG/NBD). So this run exercised the per-day-rate proxy
fallback path, not the rigorous BG/NBD-conditioned path. The proxy
rate at window_days=30, train_span_days≈210 is ≈0.143 — which
correctly window-aligns the aggregate ratio. When a real BG/NBD card
with fitted parameters is plumbed (production path post T2.5), the
rigorous BG/NBD-conditioned branch will take over automatically.

## Additional required change: `holdout_empty` warning

Pre-fix, `obs_total = 0` caused `agg_ratio = sum_pred_total / 1.0`
(a misleadingly large number) which silently REFUSED via the
band-gate with `holdout_agg_ratio_out_of_band` — operators could not
distinguish "no holdout data" from "real calibration miss."

Post-fix behavior:

- `_compute_holdout_metrics` returns `out["holdout_empty"] = 1.0`
  when either (a) `holdout_orders.empty`, or (b) the sum of observed
  holdout spend against the train customer universe is ≤ 0.
- In that case `agg_ratio` is returned as `None` (no meaningless
  ratio).
- `fit_gamma_gamma` appends `"holdout_empty"` to `fit_warnings` and
  short-circuits to `REFUSED` with that as the sole reason on the
  card — before the `rank_spearman` / `agg_ratio` band gates fire.
  This isolates "no holdout data" from genuine calibration miss in
  the audit trail.

## Files changed

- `src/predictive/gamma_gamma.py`
  - `_compute_holdout_metrics` signature extended (3 keyword-only
    args). agg_ratio block rewritten window-aligned. `holdout_empty`
    sentinel added to return dict.
  - `fit_gamma_gamma` Step 6 derives `train_span_days`, extracts
    `bgnbd_params` from chained ModelCard, threads them in; appends
    `holdout_empty` warning when set and short-circuits to REFUSED
    before downstream band gates.
  - Module docstring "agg_ratio" description updated to reflect the
    window-aligned definition.

No other files changed. No tests added — the existing 12 tests
(synthetic-DGP, chained-refusal, INSUFFICIENT_DATA, independence,
threshold loader, Pearson-r helper, flag-OFF discipline) still
pass unchanged. A dedicated unit test pinning the `holdout_empty`
short-circuit is a fast-follow if DS wants it pinned explicitly.

## Suite status

- Targeted: `tests/test_s10_t2_gamma_gamma_fit.py` — 12 passed, 0
  failed (2.76s).
- Full suite: **1940 passed, 14 skipped, 4 xfailed, 2 xpassed** in
  1343s. Same shape as the pre-fix suite — no regressions, no new
  failures.
- briefing.html byte-identity: preserved by construction. Flag
  `ENGINE_V2_ML_GAMMA_GAMMA` remains OFF; T2 has no orchestration
  wire-up; the flag-OFF
  `test_flag_off_engine_run_predictive_models_unchanged` test
  passes. Synthetic-fixture + atomic-repin pin tests across the 5
  fixtures pass inside the green suite.
- Single-demote-channel invariant: preserved (no edits in
  `src/main.py`, no new injection blocks, no call into
  `apply_guardrails*`).

## Constraints check

- [x] Flag stays OFF.
- [x] No T2.5 orchestration wire-up.
- [x] briefing.html sha byte-identity preserved across all 5
      fixtures.
- [x] Full suite green.
- [x] No commit by refactor agent — orchestrator commits.
- [x] Single-demote-channel invariant preserved.

## Return

Fix shape: **BG/NBD-card-conditioned (primary) + per-day-rate proxy
(fallback)**. Sanity-check re-run at seed=7: **PROVISIONAL**,
Spearman=0.1677, agg_ratio=0.8643, warnings=[]. Suite: **1940
passed**. Ready for DS re-review.
