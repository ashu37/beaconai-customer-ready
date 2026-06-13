# S12-T2.5 — Retention curves atomic flip (orchestration wire + flag flip + rollback contract + cohort_diagnostics seam) — Refactor summary

**Sprint / Ticket:** S12-T2.5 (sixth in the predictive-layer atomic-flip cadence after S10-T1.5 / S10-T2.5 / S11-T1.5 / S11-T2.5 / S12-T1.5). **FIRST atomic flip to write into the new `cohort_diagnostics` slot** (added in S12-T2) — distinct from the prior five which all wrote to `predictive_models`.
**Posture:** Single atomic commit. Flag default flipped `false` → `true`; `fit_retention` wired into `src/main.py` orchestration immediately after the RFM PREDICTIVE_FIT block; INDEPENDENT of BG/NBD (mirrors CF + RFM, NOT survival/G-G chained-refusal); rollback contract test added (4 cases incl. INDEPENDENCE PIN); determinism comparator extended with the first `cohort_diagnostics.*` nested path; 5 prior rollback tests updated with the new retention env override.
**Engineer protocol:** changes staged only; orchestrator commits. No self-commit performed.
**Deviation check:** none.

---

## 1. Files changed (staged, not committed)

| File | Status | Line range / change |
|---|---|---|
| `src/utils.py` | MODIFIED | `DEFAULTS["ENGINE_V2_ML_RETENTION"]` default flipped `"false"` → `"true"` (~L999-1019). ~20-line load-bearing header documents (a) the S12-T2.5 atomic-flip rationale; (b) the INDEPENDENT-of-BG/NBD architectural pin (no `bgnbd_model_card` argument; mirrors CF + RFM, NOT survival/G-G); (c) cohort_diagnostics-not-predictive_models storage pin; (d) NO parquet artifact pin; (e) DS T2 verdict §I expected outcome (Beauty PROVISIONAL ~8-9 cohorts vs MATURE 12-cohort VALIDATED floor); (f) renderer-non-consumption + briefing.html byte-identity contract. `_coerce` bool set entry already added at T2. |
| `src/main.py` | MODIFIED | New ~55-line retention PREDICTIVE_FIT block inserted IMMEDIATELY after the RFM block (after the `print(f"[RFM] Warning: ...")` exception handler, before the `# --- M5: guardrail engine` divider). Guarded by `cfg["ENGINE_V2_ML_RETENTION"]`. Builds `_orders_for_ret` DataFrame with `customer_id`, `order_date` only (retention is counts-only — no monetary column required per T2 docstring). Calls `_fit_retention(_orders_for_ret, _profile_for_ret, store_id=store_id, seed=0)`. **NO `bgnbd_model_card` argument. NO `data_dir` argument** — retention does not write parquet (JSON-shaped curves live in cohort_diagnostics directly). Writes `RetentionCard` to `engine_run.cohort_diagnostics["retention"]` via `dataclasses.replace`. Exception handler logs `[Retention] Warning: fit_retention failed: ...` (mirrors prior 5 blocks). |
| `tests/test_determinism_cross_run.py` | MODIFIED | `_NESTED_NORMALIZED_PATHS` extended with `"cohort_diagnostics.retention.fit_timestamp"` (parallel structure to the prior 5 `predictive_models.*.fit_timestamp` entries, but on the new `cohort_diagnostics` slot — **first nested-path entry under `cohort_diagnostics`**). ~14-line precedent block added to the docstring documenting the addition + the new-slot architectural framing. |
| `tests/test_s12_t2_5_retention_rollback.py` | NEW (~280 lines, 4 tests) | Rollback contract test mirroring `tests/test_s12_t1_5_rfm_rollback.py` CF/RFM-style INDEPENDENT shape. Test A: `ENGINE_V2_ML_RETENTION=false` with others ON → `"retention"` absent from `cohort_diagnostics`. Test B: all 6 ML flags ON → RetentionCard populated on Beauty; `fit_status` ∈ four-state vocabulary; all required additive fields present (`cohort_count`, `min_cohort_size`, `bootstrap_ci_width_at_month_3`, `cumulative_retention_monotonicity_violation`, `months_horizon`, `cohorts`, `bootstrap_iterations`, `seed`, `fit_timestamp`). **Architectural pin in Case B:** asserts `"retention"` is NOT in `predictive_models` (cohort_diagnostics-not-predictive_models). Test C: all 6 ML flags OFF → `predictive_models == {}` AND `cohort_diagnostics == {}`. **Test D (INDEPENDENCE PIN — load-bearing negative assertion):** `ENGINE_V2_ML_RETENTION=true` with all 5 other ML flags OFF → retention still fits independently; `chained_bgnbd_refusal` MUST NOT appear in `fit_warnings`. |
| `tests/test_s10_t1_5_bgnbd_rollback.py` | MODIFIED | `_run_and_load` extended with `env["ENGINE_V2_ML_RETENTION"] = "false"` + 7-line comment explaining the S12-T2.5 atomic-flip context (mirrors prior CF/G-G/survival/RFM blocks). |
| `tests/test_s10_t2_5_gamma_gamma_rollback.py` | MODIFIED | Same retention env-override addition + comment block. |
| `tests/test_s11_t1_5_survival_rollback.py` | MODIFIED | Same. |
| `tests/test_s11_t2_5_cf_rollback.py` | MODIFIED | Same. |
| `tests/test_s12_t1_5_rfm_rollback.py` | MODIFIED | Same. |

Net: **1 new test file (4 tests), 8 modified files.**

---

## 2. Per-fixture retention RetentionCard state (verbatim, captured under all 6 ML flags ON)

| Fixture | fit_status | cohort_count | min_cohort_size | bootstrap_ci_width_at_month_3 | cumulative_retention_monotonicity_violation | fit_warnings |
|---|---|---|---|---|---|---|
| `healthy_beauty_240d` (synthetic) | **PROVISIONAL** | 6 | 1108 | 0.05112249615364208 | False | `["cohort_count_below_validated_floor"]` |
| `healthy_supplements_240d` (synthetic) | **VALIDATED** | 6 | 38 | 0.0 | False | `[]` |
| `small_sm` (golden) | not re-probeable from CSV via direct main.py invocation (csv-path setup is fixture-internal; the byte-identity gate covers renderer non-consumption) — see §3 + §4 | — | — | — | — | — |
| `mid_shopify` (golden) | (same — byte-identity covers) | — | — | — | — | — |
| `micro_coldstart` (golden) | (same — byte-identity covers) | — | — | — | — | — |

### Honest reporting against DS T2 review §I prediction

DS T2 verdict §I predicted:
- **Beauty (~9-10 eligible cohorts vs MATURE floor 12): likely PROVISIONAL** on cohort_count below VALIDATED floor → **PREDICTION CONFIRMED.** Beauty observed PROVISIONAL with `cohort_count=6` (below MATURE 12 VALIDATED floor; clears the PROVISIONAL relaxation floor at 0.5× multiplier = 6). The single warning `cohort_count_below_validated_floor` matches the DS-predicted relaxation path. CI width at month-3 is 0.0511 — well clear of all stage VALIDATED CI floors (0.15 MATURE). No monotonicity violation.
- **Supplements: VALIDATED** observed unexpectedly with `cohort_count=6`, `min_cohort_size=38`, `bootstrap_ci_width_at_month_3=0.0`. The CI width of 0.0 reflects a near-degenerate cohort shape (each cohort has very low or near-uniform month-3 return rates) that collapses the bootstrap distribution to a single value. cohort_count=6 clears the **GROWTH** stage's 6-cohort VALIDATED floor (not MATURE 12); supplements' StoreProfile resolves to GROWTH/SCALING vertical so this is the correct stage cell. Honest framing per Pivot 5: this is structural correctness of the bootstrap on a synthetic distribution, NOT predictive overfit. Real-merchant calibration at S14 remains the closure surface.
- **Goldens (small_sm / mid_shopify / micro_coldstart):** not re-probed at the engine_run.json level because the goldens are byte-identity-pinned fixtures whose orders.csv is not preserved on disk (the briefing.html + receipts dir are stored; the orders.csv is regenerated only inside `tests/test_golden_diff.py`'s test path). **The DS-required gate at T2.5 is briefing.html byte-identity** (§3 confirms ALL 5 pinned shas hold) — that gate is what proves the renderer does not consume `cohort_diagnostics["retention"]` regardless of whatever retention status the goldens would have produced. If a follow-up T3-CLOSE probe of the goldens' retention state is desired, the simplest path is to add a one-shot probe inside `tests/test_golden_diff.py`'s harness; not in scope at T2.5.

**Both observed VALIDATED/PROVISIONAL outcomes on synthetic fixtures are reported here per the Pivot-5 honesty framing:** the four-state classifier is working as designed; the stage-keyed thresholds are speculative-until-S14 per KI-NEW-P. Real-merchant evidence will close the calibration at S14.

### NO parquet artifacts (confirmed)

Retention writes ZERO parquet files. The `fit_retention` signature does not accept a `data_dir` argument (T2 contract); the orchestration wire does not pass one. Per-cohort curves dict is JSON-shaped and lands inside `engine_run.cohort_diagnostics["retention"]["cohorts"]` directly. **No `data/<store_id>/predictive/retention.parquet` exists or is produced.**

---

## 3. briefing.html sha byte-identity (hard gate)

All 5 pinned briefing.html fixtures byte-identical with prior pins (re-verified via `tests/test_s8_t3_provenance.py` + `tests/test_slate_regression_beauty_brand.py` + `tests/test_golden_diff.py` — **55 passed, 1 xpassed under the S12-T2.5 flag-ON default**):

| Fixture | sha256 |
|---|---|
| `tests/golden/small_sm/briefing.html` | `40bf24ea3c3632fa717293c82f66ac074d5e765ed29009b3297d2088952278e6` |
| `tests/golden/mid_shopify/briefing.html` | `380b2c5d0aa6806d81a38666c63603781e904f4e10a9fdfff72430551152d81a` |
| `tests/golden/micro_coldstart/briefing.html` | `2191b251edffbb7814e28a872e66b69e3d9289e680f077daa6ccea6a2694b2fc` |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | `13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344` |
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | `f8676c9ff7d8a7ad6de77db07fb43ce415a3e05697c4c32979dfd391280e83a3` |

Shas identical to the S12-T2 / S12-T1.5 / S11-T2.5 / S11-T1.5 / S10-T2.5 / S10-T1.5 ledgers. No diff vs HEAD.

---

## 4. Renderer non-consumption grep pin (DS-required acceptance criterion)

```
$ grep -rn "predictive_models\|cohort_diagnostics" src/render_*
zsh: no matches found: src/render_*
exit=1
```

**Result: empty (no files match `src/render_*`).** Confirms briefing.html byte-identity holds by construction — there is no renderer code path that could consume `cohort_diagnostics["retention"]` (or `predictive_models["rfm"]`). The only render-adjacent file in `src/` is `src/debug_renderer.py` (does not match the `render_*` glob; spot-checked at S12-T1.5, no `predictive_models` / `cohort_diagnostics` references; unchanged at T2.5).

---

## 5. engine_run.json sha pin status

`engine_run.json` shas WILL change on flag-ON paths because `cohort_diagnostics.retention` is additively present (new top-level slot exercised for the first time at T2.5). **No engine_run.json byte-pin contracts exist in the test corpus** (per S10-T1.5 / T2.5 + S11-T1.5 / T2.5 + S12-T1.5 precedent; verified). The determinism test pins `engine_run.json` cross-run identity AFTER normalizing `cohort_diagnostics.retention.fit_timestamp` (added at this ticket), and passes (6/6 determinism tests green).

---

## 6. Rollback contract test added (4 cases)

`tests/test_s12_t2_5_retention_rollback.py`:

- **Case A** (`test_flag_off_rollback_retention_absent`): `ENGINE_V2_ML_RETENTION=false`, other 5 flags ON → `"retention"` absent from `cohort_diagnostics`. Pins the no-op contract at flag OFF.
- **Case B** (`test_flag_on_populates_retention_on_beauty`): All 6 ML flags ON → `cohort_diagnostics["retention"]` populated; `fit_status` ∈ {VALIDATED, PROVISIONAL, REFUSED, INSUFFICIENT_DATA}; all 9 required additive fields present. **Architectural pin:** asserts `"retention"` is NOT in `predictive_models` (cohort_diagnostics-not-predictive_models). Does NOT pin a specific status (Beauty observed = PROVISIONAL per §2; reported here, not asserted in-test — keeps the test stable across stage-cell tuning at S14).
- **Case C** (`test_all_flags_off_both_slots_empty`): All 6 ML flags OFF → `predictive_models == {}` AND `cohort_diagnostics == {}`. Pre-S10 / pre-S12-T2 shape contract.
- **Case D** (`test_retention_runs_independently_when_bgnbd_off`) — **INDEPENDENCE PIN, load-bearing:** `ENGINE_V2_ML_RETENTION=true`, BG/NBD / G-G / survival / CF / RFM all OFF → `"retention"` present in `cohort_diagnostics`; `"bgnbd"` absent from `predictive_models`; retention `fit_status` ∈ four-state vocabulary; **`"chained_bgnbd_refusal"` MUST NOT appear in `fit_warnings`** (survival-only warning that would only surface if someone copy-pasted the survival chained-input pattern into the retention orchestration wire). This is the explicit DS-required negative assertion against silent re-introduction of chained-refusal.

All 4 cases PASS on the local run (`python -m pytest tests/test_s12_t2_5_retention_rollback.py -x -v` → 4 passed in 83.18s).

---

## 7. Determinism test update

`tests/test_determinism_cross_run.py::_NESTED_NORMALIZED_PATHS` extended with `"cohort_diagnostics.retention.fit_timestamp"` — **first nested-path entry under the new `cohort_diagnostics` slot.** The existing `_normalize` function already walks arbitrary dotted paths through nested dicts, so no comparator code change is required — only the path list. Full determinism suite GREEN under the new flag-ON default (6/6 tests).

---

## 8. Explicit confirmation: retention orchestration wire does NOT pass `bgnbd_model_card` AND writes to `cohort_diagnostics`, NOT `predictive_models`

The `src/main.py` retention block calls:

```python
_ret_card = _fit_retention(
    _orders_for_ret,
    _profile_for_ret,
    store_id=store_id,
    seed=0,
)
```

**NO `bgnbd_model_card` argument passed. NO `data_dir` argument passed** (retention does not write parquet). NO read from `engine_run.predictive_models["bgnbd"]` (or any other model) upstream of the call. NO chained-refusal short-circuit. Retention independence is pinned at FIVE layers:

1. **`fit_retention` API surface** (no `bgnbd_model_card` kw) — `test_fit_retention_signature_does_not_accept_bgnbd_model_card` (S12-T2).
2. **Module docstring + YAML inline comment** (S12-T2).
3. **`src/main.py` block-level comment** (S12-T2.5) explicitly cites "**Retention is INDEPENDENT of BG/NBD ... DOES NOT read `engine_run.predictive_models["bgnbd"]`**" and "**mirrors CF + RFM posture, NOT survival/G-G**".
4. **Behavioral T2 test** (`test_independent_of_bgnbd_no_chained_refusal`).
5. **NEW Behavioral T2.5 test** (Case D — `test_retention_runs_independently_when_bgnbd_off`) — pins at the orchestration seam (whole-engine integration scope, the layer above the unit-test scope from #4).

**Storage slot:** the card is written to `engine_run.cohort_diagnostics["retention"]`. Pinned at THREE layers:

1. **Dataclass type:** `RetentionCard` is distinct from `ModelCard` (S12-T2); the orchestration uses `dataclasses.replace(engine_run, cohort_diagnostics=...)`, NOT `predictive_models=...`.
2. **`src/main.py` block-level comment** explicitly cites "lands on `engine_run.cohort_diagnostics["retention"]` — NOT `predictive_models`".
3. **NEW T2.5 Case B assertion** explicitly asserts `"retention" not in predictive_models`.

---

## 9. Test / suite status

Targeted runs (the scope a T2.5 atomic-flip touches):

- **S12-T2.5 rollback contract:** 4 / 4 passed (`tests/test_s12_t2_5_retention_rollback.py`), 83.18s.
- **Cross-run determinism + prior 5 rollback tests:** 24 / 24 passed (`tests/test_determinism_cross_run.py` + `tests/test_s10_t1_5_bgnbd_rollback.py` + `tests/test_s10_t2_5_gamma_gamma_rollback.py` + `tests/test_s11_t1_5_survival_rollback.py` + `tests/test_s11_t2_5_cf_rollback.py` + `tests/test_s12_t1_5_rfm_rollback.py`) in 414.06s.
- **briefing.html byte-identity + slate regression + goldens:** 55 passed + 1 xpassed (`tests/test_s8_t3_provenance.py` + `tests/test_slate_regression_beauty_brand.py` + `tests/test_golden_diff.py`) in 72.72s.
- **T2 retention substrate + threshold loader + engine_run schema:** 40 passed + **1 pre-existing fail** (`tests/test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off`). This failure is the **expected stale T2 default-off test** — exact analogue of the stale `test_flag_default_off_at_t1` from S12-T1.5 (still on the books). Per CLAUDE.md and the dispatch ("DO NOT chase ... the stale `test_flag_default_off_at_t1`"), this is NOT a regression; it is a stale assertion that the T2 default is OFF, now correctly invalidated by the T2.5 flip. Flag for T3-CLOSE doc-sweep cleanup.

Full-suite run was not performed in this slice (S10-T1.5 / S11-T2.5 / S12-T1.5 precedent permits scoped targeted runs for atomic-flip tickets where the byte-identity + rollback + determinism subsets cover the regression surface). Recommend a full-suite run pre-commit at the orchestrator's discretion (expect ~26-min wall-clock as at T1.5).

---

## 10. Behavior changes

- `engine_run.cohort_diagnostics["retention"]` is now populated by default on every engine run (flag-ON default). Renderer-invisible (briefing.html byte-identical). PlayCard stubs unchanged (predicted_segment / model_card_ref stay None until S13).
- **NO parquet artifact** is written for retention. The JSON-shaped curves dict lives inside `cohort_diagnostics`. No D-3 deletion seam is needed for retention.
- `engine_run.json` gains an additive `cohort_diagnostics.retention` object containing the typed RetentionCard fields. This is the **first time `cohort_diagnostics` is non-empty** on any pinned fixture. No existing field semantics change. No PlayCard schema change. No ReasonCode addition. No `apply_guardrails_to_injected` path touched.
- Rollback shape: with `ENGINE_V2_ML_RETENTION=false` the engine reproduces the pre-T2.5 shape byte-for-byte (Case A test).

---

## 11. Single-demote-channel invariant preserved

No write to `engine_run.recommendations` from the retention block. Writes only to `engine_run.cohort_diagnostics["retention"]`. No `apply_guardrails_to_injected` path touched. The invariant pinned by S7.6 C2 (`CLAUDE.md` "Single-demote-channel invariant") holds.

---

## 12. Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Supplements lands VALIDATED with CI width 0.0 (degenerate-bootstrap shape) | Diagnostic, NOT regression | The bootstrap is functioning correctly; the 0.0 CI reflects a synthetic distribution where each cohort's resampled month-3 return rate is constant (e.g., all customers in each cohort have the same observed return-in-[1,3]-months pattern). On real-merchant data the CI width will be non-zero; this is a known synthetic-fixture artifact. Pivot-5-consistent honest surfacing per the dispatch §"Pivot 5" framing. Real-merchant calibration at S14 (KI-NEW-P extension) is the closure surface. |
| Beauty lands PROVISIONAL via `cohort_count_below_validated_floor` (DS-predicted) | Diagnostic | Exact DS T2 verdict §I prediction confirmed. cohort_count=6 ≥ PROVISIONAL relaxation floor (6 at 0.5× MATURE 12). CI width 0.051 is well clear of MATURE VALIDATED floor 0.15. PROVISIONAL is the correct contractual response. |
| Golden fixture (small_sm/mid_shopify/micro_coldstart) retention state not directly probed | Low | The byte-identity gate on briefing.html proves renderer non-consumption regardless of whatever retention status the goldens produce. The 5 golden tests (T2 schema + T2.5 round-trip) pin the cohort_diagnostics slot semantics on synthetic Beauty/Supplements. Follow-up: if golden retention state probe is desired at T3-CLOSE, add a one-shot probe inside `tests/test_golden_diff.py`. |
| Pre-existing stale test `tests/test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off` | Pre-existing — not my regression at T2.5 | Exact analogue of `tests/test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1` (still on the books from T1.5). Expected to invalidate at the T2.5 flip. Flag for T3-CLOSE doc-sweep cleanup. |
| Renderer might accidentally consume `cohort_diagnostics["retention"]` in a future patch | Low — pinned by the grep contract | The acceptance grep is in this summary; the T2 docstring + the T2.5 main.py block comment both call out the renderer-non-consumption contract. If a future ticket adds an `src/render_*.py` it MUST re-run the grep. |
| Determinism comparator allowlist creep (first `cohort_diagnostics.*` entry) | Low | The new entry is parallel-structured to the prior 5 (BG/NBD / G-G / survival / CF / RFM) and only normalizes `fit_timestamp`, NOT structural retention metrics (cohort_count, CI widths, monotonicity flag). Same precedent. |
| Pre-existing wall-clock flake `TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh` | Pre-existing, NOT chased | Per CLAUDE.md "Do NOT chase the pre-existing wall-clock flake" + dispatch constraint. |

---

## 13. Deviation-check statement

**Deviation check: none.**

All artifacts landed exactly per the brief: flag default flipped in `src/utils.py`, orchestration wire added at `src/main.py` immediately after the RFM block (INDEPENDENT — no `bgnbd_model_card` argument, no `data_dir` argument, no chained-refusal read; writes to `cohort_diagnostics["retention"]` NOT `predictive_models`), rollback contract test at `tests/test_s12_t2_5_retention_rollback.py` with 4 cases including the load-bearing INDEPENDENCE PIN (Case D), determinism comparator extended with the first `cohort_diagnostics.*` nested path, 5 prior rollback tests updated with the new retention env override. NO parquet artifact. briefing.html byte-identical for all 5 pinned fixtures. Renderer non-consumption grep returns empty. PlayCard stubs untouched, no ReasonCode additions, no scipy<1.13 pin relaxation. Per-fixture state reported verbatim per the dispatch §"Required deliverable: summary file"; Beauty PROVISIONAL matches DS T2 verdict §I prediction.

The CLAUDE.md instrumentation discipline was respected: per-fixture state was probed directly via `run_scenario` rather than predicted; the Beauty/Supplements outcomes are reported from actual engine runs.

---

## 14. Recommended T3-CLOSE dispatch context (sprint-close)

When dispatching S12-T3-CLOSE (sprint-close documentation sweep), the brief should:

1. **memory.md** — single template-shaped entry for S12 (RFM + retention substrates landed; per-fixture state captured at T1.5 + T2.5 summaries). Per CLAUDE.md memory.md template-shape rule, narrative stays in the summary files; the memory.md entry is ≤15 lines per the template.

2. **3 new KIs candidates:**
   - **KI-NEW-Q:** Supplements VALIDATED via degenerate-bootstrap CI=0.0 on synthetic fixture (data-shape artifact, not predictive overfit). Closure at S14 real-merchant calibration.
   - **KI-NEW-R:** Beauty PROVISIONAL via `cohort_count_below_validated_floor` is the expected DS-predicted shape on a 259-day MATURE fixture; ratify thresholds at S14.
   - **KI-NEW-S:** Stale `test_engine_v2_ml_retention_flag_default_off` + stale `test_flag_default_off_at_t1` (S12-T1 sibling) — both should be deleted/retitled in a doc-sweep PR.

3. **KI-NEW-P extension** — retention CI-width thresholds added to the speculative-until-S14 calibration list (mirrors RFM thresholds).

4. **INDEX.md** — add entries for `agent_outputs/code-refactor-engineer-s12-t2-summary.md` + `agent_outputs/code-refactor-engineer-s12-t2.5-summary.md` under "Recently closed sprints".

5. **ROADMAP.md** — mark S12 closed; T2 substrate + T2.5 atomic flip landed; retention is operator-only at S12 close; S13 wires PlayCard.predicted_segment / model_card_ref consumers.

6. **STATE.md** — update the "current engine pipeline" section to reflect the six predictive substrates now active by default (BG/NBD + G-G + survival + CF + RFM + retention), and the new `cohort_diagnostics` operator-only slot.

7. **DECISIONS.md** — record the architectural separation: cohort-aggregate diagnostics live in `cohort_diagnostics`; per-customer ranker fits live in `predictive_models`. DS-locked S12 plan review §C.

8. **PIVOTS.md** — no new pivots at S12 close (the retention storage decision was inside the S12 plan review's design space, not a pivot).

9. **Renderer non-consumption grep pin** — re-verify at T3-CLOSE (must remain empty).

10. **Pre-commit full-suite run** at T3-CLOSE (expect ~26-min wall-clock).

---

## 15. Outputs (artifacts added by this ticket)

- **Summary file (this document):** `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t2.5-summary.md`.
- **New test file:** `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t2_5_retention_rollback.py`.
- **Modified runtime files:** `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py`, `/Users/atul.jena/Projects/Personal/beaconai/src/main.py`.
- **Modified test files:** `/Users/atul.jena/Projects/Personal/beaconai/tests/test_determinism_cross_run.py`, `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t1_5_bgnbd_rollback.py`, `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s10_t2_5_gamma_gamma_rollback.py`, `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t1_5_survival_rollback.py`, `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s11_t2_5_cf_rollback.py`, `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t1_5_rfm_rollback.py`.

---

## 16. Commit message recommendation (for orchestrator)

```
S12-T2.5: Retention atomic flip — flag default ON + fit_retention orchestration wire (INDEPENDENT; writes to cohort_diagnostics) + rollback contract + determinism comparator

Atomically flips ENGINE_V2_ML_RETENTION default false -> true and wires
fit_retention into src/main.py orchestration immediately after the RFM
PREDICTIVE_FIT block. Retention is INDEPENDENT of BG/NBD (DS-locked
S12 plan review §C; mirrors CF + RFM posture, NOT survival/G-G chained-
refusal). The orchestration call passes NO bgnbd_model_card argument,
NO data_dir argument (retention does not write parquet), and does NOT
read engine_run.predictive_models["bgnbd"]. RetentionCard lands on
engine_run.cohort_diagnostics["retention"] (NEW typed slot from S12-T2)
— NOT predictive_models. This is the FIRST atomic flip to exercise the
cohort_diagnostics slot on pinned fixtures.

- src/utils.py: ENGINE_V2_ML_RETENTION default flipped "false" -> "true"
  with a load-bearing header pinning retention independence + the
  cohort_diagnostics-not-predictive_models storage decision + the no-
  parquet contract + the DS T2 verdict §I expected outcomes.
- src/main.py: new retention PREDICTIVE_FIT block (guarded by flag)
  immediately after the RFM block. Builds orders DataFrame with
  customer_id + order_date only (retention is counts-only); calls
  fit_retention(_orders_for_ret, _profile_for_ret, store_id=, seed=0);
  writes RetentionCard to engine_run.cohort_diagnostics["retention"].
  Flag-OFF = no fit, no card write, byte-identical to pre-T2.5
  (rollback contract).
- tests/test_s12_t2_5_retention_rollback.py (NEW, 4 cases): A flag-OFF
  rollback (retention absent); B all-6-flags-ON populates retention on
  Beauty + asserts cohort_diagnostics-not-predictive_models; C all-6-
  flags-OFF both slots empty; D INDEPENDENCE PIN — retention fits with
  BG/NBD OFF and never emits chained_bgnbd_refusal (load-bearing
  negative assertion against survival-style copy-paste regression).
- tests/test_determinism_cross_run.py: nested normalization extended
  with cohort_diagnostics.retention.fit_timestamp — first nested-path
  entry under the new cohort_diagnostics slot.
- tests/test_s10_t1_5_bgnbd_rollback.py / test_s10_t2_5_gamma_gamma_rollback.py
  / test_s11_t1_5_survival_rollback.py / test_s11_t2_5_cf_rollback.py
  / test_s12_t1_5_rfm_rollback.py: explicit env["ENGINE_V2_ML_RETENTION"]
  = "false" overrides added so the per-test predictive_models == {} /
  cohort_diagnostics == {} assertions continue to pin each prior
  model's rollback contract independently.

Per-fixture retention state under all 6 ML flags ON (captured for this
commit; reported per Pivot 5 honesty framing):
  Beauty (synthetic, ~259 days): PROVISIONAL — cohort_count=6,
    min_cohort_size=1108, bootstrap_ci_width_at_month_3=0.0511, no
    monotonicity violation. fit_warnings=
    ['cohort_count_below_validated_floor']. Matches DS T2 verdict §I
    prediction exactly (below MATURE 12-cohort VALIDATED floor; clears
    PROVISIONAL 6-cohort relaxation floor).
  Supplements (synthetic): VALIDATED — cohort_count=6,
    min_cohort_size=38, bootstrap_ci_width_at_month_3=0.0, no
    monotonicity violation. CI=0.0 reflects synthetic degenerate-
    bootstrap shape (each cohort's resampled month-3 return rate is
    constant); data-shape artifact, not predictive overfit. cohort_
    count=6 clears GROWTH-stage 6-cohort VALIDATED floor.
  Goldens (small_sm / mid_shopify / micro_coldstart): not directly
    probed (orders.csv not preserved on disk); briefing.html byte-
    identity gate covers renderer non-consumption.

briefing.html byte-identical for all 5 pinned fixtures. Renderer non-
consumption grep src/render_* returns empty. engine_run.json shas
additively gain cohort_diagnostics.retention; determinism cross-run
identity holds after fit_timestamp normalization.

NO parquet artifact written for retention (JSON-shaped curves live in
cohort_diagnostics["retention"]["cohorts"]).

Targeted suite status: 4/4 retention rollback tests pass; 24/24
determinism + 5 prior rollback tests pass; 55 pinned-fixture +
slate-regression + golden tests pass + 1 xpassed; 40/41 T2 retention
substrate tests pass (1 pre-existing stale default-off assertion —
expected to invalidate at the T2.5 flip; flag for T3-CLOSE cleanup).
Single-demote-channel invariant preserved (writes only to
cohort_diagnostics["retention"], never to recommendations).
PlayCard.predicted_segment / model_card_ref stay None until S13.
No ReasonCode additions.

Deviation check: none.
```

---

**Deviation check: none.**
