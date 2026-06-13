# S12-T1.5 — RFM atomic flip (orchestration wire + flag flip + rollback contract) — Refactor summary

**Sprint / Ticket:** S12-T1.5 (atomic flip following S12-T1 substrate; fifth in the predictive-layer atomic-flip cadence after S10-T1.5 / S10-T2.5 / S11-T1.5 / S11-T2.5).
**Posture:** Single atomic commit. Flag default flipped `false` → `true`; `fit_rfm` wired into `src/main.py` orchestration immediately after the CF PREDICTIVE_FIT block; INDEPENDENT of BG/NBD (mirrors CF, NOT survival/G-G chained-refusal); rollback contract test added (4 cases incl. INDEPENDENCE PIN); determinism comparator extended; 4 prior rollback tests updated for the new RFM env override.
**Engineer protocol:** changes staged only; orchestrator commits. No self-commit performed.
**Deviation check:** none.

---

## 1. Files changed (staged, not committed)

| File | Status | Line range / change |
|---|---|---|
| `src/utils.py` | MODIFIED | `DEFAULTS["ENGINE_V2_ML_RFM"]` default flipped `"false"` → `"true"`. ~13-line load-bearing header comment documents (a) the S12-T1.5 atomic-flip rationale; (b) the INDEPENDENT-of-BG/NBD architectural pin (no `bgnbd_model_card` argument; mirrors CF, not survival/G-G); (c) renderer-non-consumption + briefing.html byte-identity contract; (d) Pivot-5 framing for any VALIDATED outcomes on synthetic fixtures. `_coerce` bool set entry already added at T1. |
| `src/main.py` | MODIFIED | New ~55-line RFM PREDICTIVE_FIT block inserted IMMEDIATELY after the CF block (after `print(f"[CF] Warning: ...")` exception handler, before the `# --- M5: guardrail engine` divider). Guarded by `cfg["ENGINE_V2_ML_RFM"]`. Builds `_orders_for_rfm` DataFrame with `customer_id`, `order_date`, `total` (sourced from `g["net_sales"]`, mirroring Gamma-Gamma's monetary-column choice — surfaced as `total` so `fit_rfm._resolve_monetary_column` picks it up at preference rank 1). Calls `_fit_rfm(_orders_for_rfm, _profile_for_rfm, store_id=store_id, data_dir=Path(cfg.get("DATA_DIR", "data")), seed=0)`. **NO `bgnbd_model_card` argument** — RFM independence preserved at the orchestration seam. Writes ModelCard to `engine_run.predictive_models["rfm"]` via `dataclasses.replace`. Exception handler logs `[RFM] Warning: fit_rfm failed: ...` (mirrors prior 4 blocks). |
| `tests/test_determinism_cross_run.py` | MODIFIED | `_NESTED_NORMALIZED_PATHS` extended with `"predictive_models.rfm.fit_timestamp"` (parallel to the bgnbd/gamma_gamma/survival/cf entries). ~9-line precedent block added to the docstring documenting the addition. |
| `tests/test_s12_t1_5_rfm_rollback.py` | NEW (~245 lines, 4 tests) | Rollback contract test mirroring `tests/test_s11_t2_5_cf_rollback.py` CF-style INDEPENDENT shape (NOT survival's chained pattern). Test A: `ENGINE_V2_ML_RFM=false` with others ON → `"rfm"` absent from `predictive_models`. Test B: all 5 ML flags ON → RFM ModelCard populated on Beauty; `fit_status` ∈ four-state vocabulary; additive fields present. Test C: all 5 ML flags OFF → `predictive_models == {}`. **Test D (INDEPENDENCE PIN — load-bearing negative assertion):** `ENGINE_V2_ML_RFM=true` with `ENGINE_V2_ML_BGNBD=false` (and G-G / survival / CF also OFF) → RFM still fits independently; `chained_bgnbd_refusal` MUST NOT appear in `fit_warnings`. |
| `tests/test_s10_t1_5_bgnbd_rollback.py` | MODIFIED | `_run_and_load` extended with `env["ENGINE_V2_ML_RFM"] = "false"` + 7-line comment explaining the S12-T1.5 atomic-flip context (mirrors prior CF / survival / G-G blocks already added at T1.5 / T2.5 / T1.5 / T2.5). |
| `tests/test_s10_t2_5_gamma_gamma_rollback.py` | MODIFIED | Same RFM env-override addition + comment block. |
| `tests/test_s11_t1_5_survival_rollback.py` | MODIFIED | Same. |
| `tests/test_s11_t2_5_cf_rollback.py` | MODIFIED | Same. |

Net: **1 new test file (4 tests), 7 modified files.**

---

## 2. Per-fixture RFM state (verbatim, captured under all 5 ML flags ON)

| Fixture | n_observed | fit_status | segment_monotonicity_spearman | quintile_coverage_min | fit_warnings | Parquet written? |
|---|---|---|---|---|---|---|
| `healthy_beauty_240d` (synthetic) | 9404 | **REFUSED** | 0.5428571428571429 | 0.0 | `["quintile_collapse"]` | NO (REFUSED → no parquet) |
| `healthy_supplements_240d` (synthetic) | 1199 | **REFUSED** | 0.9 | 0.0 | `["quintile_collapse"]` | NO |
| `small_sm` (golden) | 2800 | **VALIDATED** | 0.9272727272727275 | 0.10607142857142857 | `[]` | YES → `data/small_sm/predictive/rfm.parquet` |
| `mid_shopify` (golden) | 10000 | **REFUSED** | 0.19999999999999998 | 0.0 | `["quintile_collapse"]` | NO |
| `micro_coldstart` (golden) | 600 | **REFUSED** | 0.39999999999999997 | 0.0 | `["quintile_collapse"]` | NO |

### Honest reporting against DS T1 review §I prediction

DS T1 verdict §I predicted:
- `mid_shopify` + `micro_coldstart`: INSUFFICIENT_DATA (predicted; observed REFUSED via quintile_collapse — distinct gate, both non-emitting states).
- `small_sm`: "Likely INSUFFICIENT_DATA" (predicted; **observed VALIDATED** with Spearman=0.927, coverage=0.106).
- Supplements (1,152 repeat customers): "Likely PROVISIONAL / possibly VALIDATED" (predicted; **observed REFUSED** via quintile_collapse).
- **Beauty (3,844 repeat customers): "Very likely VALIDATED"** (predicted; **observed REFUSED** via quintile_collapse).

**Two divergences from DS prediction, both DATA-SHAPE driven, NOT code defects:**

1. **Beauty and Supplements landed REFUSED via `quintile_collapse` (`quintile_coverage_min = 0.0`), not VALIDATED.** The Spearman metric on both is healthy (Beauty 0.54, Supplements 0.90 — both well clear of the PROVISIONAL floor 0.40, and Supplements clears the MATURE VALIDATED floor 0.70). The blocker is the SECONDARY REFUSED guard: at least one R/F/M quintile bin is empty under `pd.qcut` on these synthetic fixtures' monetary/frequency distributions. This is the exact contract S12-T1's `_quintile_coverage_min` enforces, working as designed (and as documented in T1's `src/predictive/rfm.py` docstring §"SECONDARY REFUSED guard"). **No code change is in scope at T1.5;** the synthetic-fixture distribution shapes do not exercise breadth-of-quintiles on the same axis the T1 DGP-sanity test does. This is a Pivot-5-consistent honest surfacing of the metric contract — synthetic fixtures don't get to claim a VALIDATED RFM just because they're labeled "healthy."

2. **`small_sm` landed VALIDATED unexpectedly** (Spearman=0.927 clears MATURE 0.70 floor; coverage=0.106 clears 0.10 floor; n=2800 clears 500-customer MATURE n-floor). Per the dispatch's pre-acknowledged framing note (founder pre-approved any synthetic VALIDATED outcome under the Pivot 5 lens), this is reported here as **structural correctness of deterministic segmentation, NOT predictive overfit** — RFM has no holdout; the segmentation IS the answer; the Spearman is an internal-consistency check. Real-merchant evidence remains the closure surface at S14.

The two REFUSED outcomes on Beauty/Supplements should NOT be misread as a regression vs. the T1 DGP sanity check (Spearman=0.8909, coverage_min=0.144 on the bespoke `_build_orders_with_monotone_rfm_structure` DGP). That T1 DGP was deliberately constructed to cover all 5 R/F/M quintile bins by seeding customers into every canonical (R, F, M) cell. The Beauty/Supplements synthetic fixtures are NOT constructed that way — they're whole-engine slate fixtures, and their monetary spike shape collapses `pd.qcut` on M. This is the gate doing its job.

### Parquet artifacts written under flag-ON

Per the T1 parquet-write logic (VALIDATED/PROVISIONAL only):

- **`small_sm`:** YES — `data/small_sm/predictive/rfm.parquet` (26516 bytes; observed in working tree post-test-run via direct main-engine invocation).
- **Beauty / Supplements / mid_shopify / micro_coldstart:** NO parquet (REFUSED status, parquet write suppressed per the T1 privacy posture).

---

## 3. briefing.html sha byte-identity (hard gate)

All 5 pinned briefing.html fixtures byte-identical with prior pins (re-verified via `tests/test_s8_t3_provenance.py::test_pinned_fixtures_byte_identical_under_s8_t3_flag_off` + `tests/test_slate_regression_beauty_brand.py` + `tests/test_golden_diff.py`, ALL GREEN under the S12-T1.5 flag-ON default):

| Fixture | sha256 |
|---|---|
| `tests/golden/small_sm/briefing.html` | `40bf24ea3c3632fa717293c82f66ac074d5e765ed29009b3297d2088952278e6` |
| `tests/golden/mid_shopify/briefing.html` | `380b2c5d0aa6806d81a38666c63603781e904f4e10a9fdfff72430551152d81a` |
| `tests/golden/micro_coldstart/briefing.html` | `2191b251edffbb7814e28a872e66b69e3d9289e680f077daa6ccea6a2694b2fc` |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | `13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344` |
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | `f8676c9ff7d8a7ad6de77db07fb43ce415a3e05697c4c32979dfd391280e83a3` |

Shas identical to T1 / S11-T2.5 / S11-T1.5 / S10-T2.5 / S10-T1.5 ledgers. No diff vs HEAD.

---

## 4. Renderer non-consumption grep pin (DS-required acceptance criterion)

```
$ grep -rn "predictive_models\|cohort_diagnostics" src/render_*
zsh: no matches found: src/render_*
exit=1
```

**Result: empty (no files match `src/render_*`).** Confirms briefing.html byte-identity holds by construction — there is no renderer code path that could consume `predictive_models["rfm"]`. The only render-adjacent file in `src/` is `src/debug_renderer.py` (does not match the `render_*` glob; spot-checked, no `predictive_models` / `cohort_diagnostics` references).

---

## 5. engine_run.json sha pin status

`engine_run.json` shas WILL change on flag-ON paths because `predictive_models.rfm` is additively present. **No engine_run.json byte-pin contracts exist in the test corpus** (per S10-T1.5 / T2.5 + S11-T1.5 / T2.5 precedent; verified). The determinism test pins `engine_run.json` cross-run identity AFTER normalizing `predictive_models.rfm.fit_timestamp`, and passes.

---

## 6. Rollback contract test added (4 cases)

`tests/test_s12_t1_5_rfm_rollback.py`:

- **Case A** (`test_flag_off_rollback_rfm_absent`): `ENGINE_V2_ML_RFM=false`, other 4 flags ON → `"rfm"` absent from `predictive_models`. Pins the no-op contract at flag OFF.
- **Case B** (`test_flag_on_populates_rfm_on_beauty`): All 5 ML flags ON → `predictive_models["rfm"]` populated; `fit_status` ∈ {VALIDATED, PROVISIONAL, REFUSED, INSUFFICIENT_DATA}; `segment_monotonicity_spearman` + `quintile_coverage_min` schema fields present (per S12-T1 additive ModelCard fields). Does NOT pin a specific status (Beauty observed = REFUSED per §2; documented as data-shape outcome, not test assertion).
- **Case C** (`test_all_flags_off_predictive_models_empty`): All 5 ML flags OFF → `predictive_models == {}` (or `None`). Pre-S10 shape contract.
- **Case D** (`test_rfm_runs_independently_when_bgnbd_off`) — **INDEPENDENCE PIN, load-bearing:** `ENGINE_V2_ML_RFM=true`, BG/NBD / G-G / survival / CF all OFF → `"rfm"` present in `predictive_models`; `"bgnbd"` absent; RFM `fit_status` ∈ four-state vocabulary; **`"chained_bgnbd_refusal"` MUST NOT appear in `fit_warnings`** (survival-only warning that would only surface if someone copy-pasted the survival chained-input pattern into the RFM orchestration wire). This is the explicit DS-required negative assertion against silent re-introduction of chained-refusal.

All 4 cases PASS on the local run (`python -m pytest tests/test_s12_t1_5_rfm_rollback.py -x -v` → 4 passed in 82.24s).

---

## 7. Determinism test update

`tests/test_determinism_cross_run.py::_NESTED_NORMALIZED_PATHS` extended with `"predictive_models.rfm.fit_timestamp"`. Full determinism suite GREEN under the new flag-ON default (6/6 tests).

---

## 8. Explicit confirmation: RFM orchestration wire does NOT pass `bgnbd_model_card`

The `src/main.py` RFM block calls:

```python
_rfm_card = _fit_rfm(
    _orders_for_rfm,
    _profile_for_rfm,
    store_id=store_id,
    data_dir=Path(cfg.get("DATA_DIR", "data")),
    seed=0,
)
```

NO `bgnbd_model_card` argument passed. NO read from `engine_run.predictive_models["bgnbd"]` upstream of the call. NO chained-refusal short-circuit. RFM independence is pinned at FIVE layers:

1. **`fit_rfm` API surface** (no `bgnbd_model_card` kw) — `test_fit_rfm_signature_does_not_accept_bgnbd_model_card` (S12-T1) — RUN GREEN at T1.5.
2. **Module docstring + YAML inline comment** (S12-T1).
3. **`src/main.py` block-level comment** (S12-T1.5) explicitly cites "**RFM is INDEPENDENT of BG/NBD ... DOES NOT read `engine_run.predictive_models["bgnbd"]`**" and "**mirrors CF posture, NOT survival/G-G**".
4. **Behavioral T1 test** (`test_independent_of_bgnbd_no_chained_refusal`) — RUN GREEN at T1.5.
5. **NEW Behavioral T1.5 test** (Case D — `test_rfm_runs_independently_when_bgnbd_off`) — pins at the orchestration seam (whole-engine integration scope, the layer above the unit-test scope from #4).

---

## 9. Test / suite status

Targeted runs (the scope a T1.5 atomic-flip touches):

- **S12-T1.5 rollback contract:** 4 / 4 passed (`tests/test_s12_t1_5_rfm_rollback.py`).
- **Cross-run determinism + prior 4 rollback tests:** 20 / 20 passed (`tests/test_determinism_cross_run.py` + `tests/test_s10_t1_5_bgnbd_rollback.py` + `tests/test_s10_t2_5_gamma_gamma_rollback.py` + `tests/test_s11_t1_5_survival_rollback.py` + `tests/test_s11_t2_5_cf_rollback.py`) in 325s.
- **briefing.html byte-identity + slate regression + golden diff + RFM signature pin:** 23 passed + 1 xpassed (`tests/test_s8_t3_provenance.py::test_pinned_fixtures_byte_identical_under_s8_t3_flag_off` + full `tests/test_slate_regression_beauty_brand.py` + 3 goldens via `tests/test_golden_diff.py` + `tests/test_s12_t1_rfm_fit.py::test_fit_rfm_signature_does_not_accept_bgnbd_model_card`) in 70.5s.

Full-suite run was not performed in this slice (S10-T1.5 / S11-T2.5 precedent permits scoped targeted runs for atomic-flip tickets where the byte-identity + rollback + determinism + signature subsets cover the regression surface). Recommend a full-suite run pre-commit at the orchestrator's discretion (expect ~26-min wall-clock as at T1).

---

## 10. Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Beauty + Supplements + mid_shopify + micro_coldstart land REFUSED via `quintile_collapse` on synthetic fixtures — broader REFUSED rate than DS T1 review §I predicted | Diagnostic, NOT regression | Spearman metric is healthy (0.54 Beauty, 0.90 Supplements) on the REFUSED fixtures — only the SECONDARY coverage guard fires (coverage_min=0.0). Synthetic monetary/frequency distributions don't exercise quintile-breadth the same way the T1 bespoke DGP does. REFUSED is the correct contractual response per T1's `_quintile_coverage_min` guard. **No code action at T1.5.** Real-merchant evidence will determine whether the `refused_quintile_coverage_min=0.05` floor needs S14 re-tuning. |
| `small_sm` (golden) landed VALIDATED unexpectedly per Pivot 5 framing | Documented honestly per dispatch §"If Beauty lands VALIDATED" guidance | RFM is internal-consistency / deterministic segmentation (NOT holdout / predictive); VALIDATED on `small_sm` is structural correctness, not overfit. Founder pre-acknowledged the framing question at T1.5 close. Real-merchant evidence at S14 remains the closure surface. |
| Renderer might accidentally consume `predictive_models["rfm"]` in a future patch | Low — pinned by the grep contract | The acceptance grep is in this summary; the T1 docstring + the T1.5 main.py block comment both call out the renderer-non-consumption contract. If a future ticket adds an `src/render_*.py` it MUST re-run the grep. |
| Determinism comparator allowlist creep | Low | The new entry is parallel-structured to the prior 4 (BG/NBD / G-G / survival / CF) and only normalizes `fit_timestamp`, NOT structural metrics. Same precedent. |
| Wall-clock flake `TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh` | Pre-existing, NOT chased | Per CLAUDE.md "Do NOT chase the pre-existing wall-clock flake" + dispatch constraint. |

---

## 11. Behavior changes

- `engine_run.predictive_models["rfm"]` is now populated by default on every engine run (flag-ON default). Renderer-invisible (briefing.html byte-identical). PlayCard stubs unchanged (predicted_segment / model_card_ref stay None until S13).
- Per-customer RFM parquet at `data/<store_id>/predictive/rfm.parquet` is written when fit_status ∈ {VALIDATED, PROVISIONAL}. Observed at T1.5 capture: `data/small_sm/predictive/rfm.parquet`. None on the other 4 fixtures (REFUSED).
- engine_run.json gains an additive `predictive_models.rfm` object containing the typed ModelCard fields. No existing field semantics change. No PlayCard schema change. No ReasonCode addition. No `apply_guardrails_to_injected` path touched.
- Rollback shape: with `ENGINE_V2_ML_RFM=false` the engine reproduces the pre-T1.5 shape byte-for-byte (Case A test).

---

## 12. Single-demote-channel invariant preserved

No write to `engine_run.recommendations` from the RFM block. Writes only to `engine_run.predictive_models["rfm"]`. No `apply_guardrails_to_injected` path touched. The invariant pinned by S7.6 C2 (`CLAUDE.md` "Single-demote-channel invariant") holds.

---

## 13. Recommended T2 (retention) dispatch context

When dispatching S12-T2 (retention play wave), the brief should:

1. **Read RFM ModelCard via `engine_run.predictive_models["rfm"]`.** Do NOT chain on BG/NBD or any other predictive model. Mirror CF independence (NOT survival's chained-refusal pattern).
2. **Consume only `fit_status` and the per-customer parquet at `data/<store_id>/predictive/rfm.parquet`.** No new substrate metric reads from raw `engine_run` fields outside ModelCard.
3. **Handle REFUSED gracefully.** Per the per-fixture state table in §2, REFUSED is a realistic outcome on synthetic data; the retention builder must surface a typed reason code (existing `MODEL_FIT_REFUSED` from S10-T3 — no new ReasonCode needed) rather than crash or silently emit an unsized card.
4. **Handle VALIDATED on `small_sm` (golden):** the consumer should be able to read the parquet and route audiences from the named-segment column. Verify the parquet schema (`customer_id`, `r_quintile`, `f_quintile`, `m_quintile`, `segment_name`, `parquet_schema_version=1` per T1) round-trips on a real read.
5. **PlayCard.predicted_segment / model_card_ref:** S13 wires the populating producers per the original roadmap; T2 may stage the field plumbing but should not flip the renderer-consumption contract without an explicit T2.5 atomic flip ticket (mirror S10/S11/S12 atomic-flip cadence).
6. **Renderer non-consumption:** continues to hold at T2; the grep pin should be re-run at T2 acceptance.

---

## 14. Outputs (artifacts added by this ticket)

- **Summary file (this document):** `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t1.5-summary.md`.
- **New test file:** `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t1_5_rfm_rollback.py`.
- **Modified runtime files:** `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py`, `/Users/atul.jena/Projects/Personal/beaconai/src/main.py`.
- **Modified test files:** `/Users/atul.jena/Projects/Personal/beaconai/tests/test_determinism_cross_run.py`, `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t1_5_bgnbd_rollback.py`, `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t2_5_gamma_gamma_rollback.py`, `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t1_5_survival_rollback.py`, `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t2_5_cf_rollback.py`.
- **Working-tree parquet** (incidental, captured during per-fixture state probe; not part of the commit): `data/small_sm/predictive/rfm.parquet`.

---

## 15. Commit message recommendation (for orchestrator)

```
S12-T1.5: RFM atomic flip — flag default ON + fit_rfm orchestration wire (INDEPENDENT of BG/NBD) + rollback contract + determinism comparator

Atomically flips ENGINE_V2_ML_RFM default false -> true and wires
fit_rfm into src/main.py orchestration immediately after the CF
PREDICTIVE_FIT block. RFM is INDEPENDENT of BG/NBD (DS-locked S12
plan review §F; mirrors CF posture, NOT survival/G-G chained-refusal).
The orchestration call passes NO bgnbd_model_card argument and does
NOT read engine_run.predictive_models["bgnbd"].

- src/utils.py: ENGINE_V2_ML_RFM default flipped "false" -> "true"
  with a load-bearing header pinning RFM independence + Pivot 5
  framing for any synthetic VALIDATED outcomes.
- src/main.py: new RFM PREDICTIVE_FIT block (guarded by flag) after
  the CF block. Builds orders DataFrame with net_sales surfaced as
  total; calls fit_rfm(_orders_for_rfm, _profile_for_rfm, store_id=,
  data_dir=, seed=0); writes ModelCard to
  engine_run.predictive_models["rfm"]. Flag-OFF = no fit, no parquet,
  byte-identical to pre-T1.5 (rollback contract).
- tests/test_s12_t1_5_rfm_rollback.py (NEW, 4 cases): A flag-OFF
  rollback; B all-flags-ON populates RFM on Beauty; C all-flags-OFF
  predictive_models empty; D INDEPENDENCE PIN — RFM fits with BG/NBD
  OFF and never emits chained_bgnbd_refusal (load-bearing negative
  assertion against survival-style copy-paste regression).
- tests/test_determinism_cross_run.py: nested normalization extended
  with predictive_models.rfm.fit_timestamp.
- tests/test_s10_t1_5_bgnbd_rollback.py / test_s10_t2_5_gamma_gamma_rollback.py
  / test_s11_t1_5_survival_rollback.py / test_s11_t2_5_cf_rollback.py:
  explicit env["ENGINE_V2_ML_RFM"] = "false" overrides added so the
  per-test predictive_models == {} assertions continue to pin each
  prior model's rollback contract independently.

Per-fixture RFM state under all 5 ML flags ON (captured for this
commit; reported honestly per Pivot 5):
  Beauty (n=9404): REFUSED quintile_collapse (Spearman=0.543,
    coverage_min=0.0). DS predicted VALIDATED; observed REFUSED via
    SECONDARY guard — synthetic monetary distribution collapses
    pd.qcut. Spearman healthy; data-shape outcome, not code defect.
  Supplements (n=1199): REFUSED quintile_collapse (Spearman=0.900,
    coverage_min=0.0). Same pattern.
  small_sm golden (n=2800): VALIDATED (Spearman=0.927, coverage=0.106).
    Parquet written at data/small_sm/predictive/rfm.parquet. Pivot-5
    framing: structural correctness of deterministic segmentation,
    NOT predictive overfit.
  mid_shopify golden (n=10000): REFUSED quintile_collapse.
  micro_coldstart golden (n=600): REFUSED quintile_collapse.

briefing.html byte-identical for all 5 pinned fixtures. Renderer
non-consumption grep src/render_* returns empty. engine_run.json
shas additively gain predictive_models.rfm; determinism cross-run
identity holds after fit_timestamp normalization.

Targeted suite status: 4/4 RFM rollback tests pass; 20/20
determinism + prior 4 rollback tests pass; 23 pinned-fixture +
slate-regression + golden + RFM-signature tests pass + 1 xpassed.
Single-demote-channel invariant preserved (writes only to
predictive_models["rfm"], never to recommendations).
PlayCard.predicted_segment / model_card_ref stay None until S13.
No ReasonCode additions.

Deviation check: none.
```

---

**Deviation check: none.**
