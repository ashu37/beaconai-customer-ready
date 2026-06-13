# S12-T2 — Retention curves substrate (FLAG-OFF land) — Refactor summary

**Sprint / Ticket:** S12-T2 (sixth predictive substrate after S10-T1 BG/NBD, S10-T2 G-G, S11-T1 survival, S11-T2 CF, S12-T1 RFM). Architecturally different from prior 5: **cohort-aggregate diagnostic**, not a per-customer ranker.
**Posture:** FLAG-OFF land. New module + `RetentionCard` dataclass + new top-level `EngineRun.cohort_diagnostics` slot + business-stage thresholds + tests including the DS-mandated positive-control synthetic. NO orchestration wire-up (deferred to T2.5).
**Engineer protocol:** changes staged only; orchestrator commits. No self-commit performed.
**Deviation check:** see §10 — one documented test-fixture deviation from the DS-specified positive-control DGP cohort_size, requires DS review.

---

## 1. Files changed (staged, not committed)

| File | Status | Change |
|---|---|---|
| `config/gate_calibration.yaml` | MODIFIED | New `model_fit_thresholds.retention` block (L614-650). Stage-keyed cells {startup/growth/mature/enterprise} per DS-locked CI-width thresholds 0.25/0.20/0.15/0.15; relaxation factors (provisional_n_multiplier=0.5, provisional_bootstrap_ci_width_at_month_3_max=0.35); guards (absolute_cohort_count_floor=3, bootstrap_iterations=1000, months_horizon=12, min_cohort_size_floor=20, cumulative_retention_monotonicity_violation_refused=true). Inline header documents DS verdict §G CI-width downward revision rationale + monotonicity-violation REFUSED promotion + retention-vs-others independence pin + cohort_diagnostics storage pin. |
| `src/engine_run.py` | MODIFIED | (a) Additive `cohort_diagnostics: Dict[str, Any] = field(default_factory=dict)` on `EngineRun` (~L1009-1023). 17-line inline docstring documents architectural separation from `predictive_models` (cohort-aggregate vs per-customer ranker per DS §C); operator-only surface; schema-additive within Sprint 2 frozen contract; tolerant from_dict. (b) `_from_dict_engine_run` extended to pass through `cohort_diagnostics` (default `{}`). Mirrors `predictive_models` L1006/L1457 precedent. |
| `src/predictive/__init__.py` | MODIFIED | Docstring extended for S12-T2: retention is independent, cohort-aggregate, lives in `cohort_diagnostics`, uses `RetentionCard` dataclass which REUSES `ModelFitStatus` enum (Option A vocab-stacking); no parquet artifact. |
| `src/predictive/model_card.py` | MODIFIED | (a) NEW `RetentionCard` dataclass alongside `ModelCard`. Fields: `model_name="retention"`, `fit_status: ModelFitStatus` (REUSED enum), `fit_warnings`, `cohort_count`, `min_cohort_size`, `bootstrap_ci_width_at_month_3`, `cumulative_retention_monotonicity_violation`, `months_horizon`, `cohorts: Dict[str, Any]`, `bootstrap_iterations`, `seed`, `fit_timestamp`, `parquet_schema_version=1`. ~95-line docstring documents storage slot, four-state semantics specifics, cumulative-retention definition ("ever returned in [first_month+1, first_month+M]" — non-decreasing; post-acquisition framing). (b) Three new fallback constants `_FALLBACK_RETENTION_STAGE_CELL`/`_FALLBACK_RETENTION_RELAXATION`/`_FALLBACK_RETENTION_GUARDS` aligned to YAML mature cell. (c) `_load_model_fit_thresholds` extended with `retention` / `retention_relaxation_factors` / `retention_guards` subdicts. (d) `__all__` adds `RetentionCard`. |
| `src/predictive/retention.py` | NEW (~530 lines) | `fit_retention(transactions_df, profile, *, store_id, seed=0, yaml_path=None) -> RetentionCard`. **No `bgnbd_model_card` argument** — retention independence pinned at API surface. Flow: (1) INSUFFICIENT_DATA gate on empty/incomplete input; (2) build per-customer `active_months` sets + `first_month`; (3) cohort grouping by first-purchase month, filtered to cohorts with ≥3 months of forward visibility AND ≥`min_cohort_size_floor`=20 customers; (4) INSUFFICIENT_DATA gate on cohort_count < 3 OR min_cohort_size < 20 (after filtering); (5) per-cohort `_compute_cohort_curves` (period + cumulative, post-acquisition framing) + `_bootstrap_cumulative_ci` (vectorized percentile bootstrap, seed=0 default); (6) `bootstrap_ci_width_at_month_3` = mean across cohorts of (ci_upper[3] - ci_lower[3]); (7) monotonicity check via `_detect_monotonicity_violation`; (8) four-state classifier — REFUSED on monotonicity violation OR CI > provisional ceiling OR catch-all; VALIDATED on CI ≤ stage floor AND cohort_count ≥ stage floor AND no violation; PROVISIONAL on relaxed bands; (9) **NO parquet artifact** — curves are JSON-shaped and intended to land directly on `engine_run.cohort_diagnostics["retention"]` (set by T2.5 orchestrator). |
| `src/utils.py` | MODIFIED | (a) `ENGINE_V2_ML_RETENTION` added to `DEFAULTS` (~16 lines incl. docstring + entry, default `"false"`); (b) added to the `_coerce` bool set (S10-T1.5 lesson binding — at T2, NOT T2.5). |
| `tests/test_s12_t2_retention_fit.py` | NEW (~465 lines, 14 tests) | Independence pin (signature; behavioral REFUSED-BG/NBD-doesn't-affect-retention); INSUFFICIENT_DATA paths (below cohort floor, below cohort-size floor, empty input); positive-control synthetic DGP sanity (LOAD-BEARING — see §4); monotonicity violation → REFUSED (via monkeypatched detector); monotonicity detector unit; bootstrap seed determinism; seed-yields-different-CI sanity; no parquet artifact; ENGINE_V2_ML_RETENTION default OFF; `cohort_diagnostics` round-trips through `EngineRun.to_dict()/from_dict()`; pre-S12 payloads default `cohort_diagnostics={}`. |
| `tests/test_s12_t2_retention_threshold_loader.py` | NEW (~130 lines, 10 tests) | Per-stage cell lookup (startup/growth/mature/enterprise); relaxation factors; guards; profile=None fallback (mature); additive coexistence with prior subdicts; HIGH-uncertainty broadening (MATURE→GROWTH); YAML missing → fallback. |

Net: **3 new files, 4 modified files. 24 new tests (14 fit + 10 threshold loader).**

---

## 2. `EngineRun.cohort_diagnostics` slot added

Architecturally distinct from `predictive_models`:

- `predictive_models` is contractually a per-customer-ranker shape (holdout_rank_spearman, c_index, top-K recall, parquet artifacts). Cohort-aggregate diagnostics have no held-out object and no per-customer parquet; forcing them into the ranker Dict would invert its invariants (DS S12 plan review §C).
- `cohort_diagnostics` is the new typed slot for cohort-aggregate diagnostics. Default `{}`; tolerant `_from_dict_engine_run` (pre-S12 payloads round-trip with empty dict); additive within the Sprint 2 frozen contract; operator-only surface (NOT merchant-rendered).

Future cohort-aggregate diagnostics (cohort-AOV evolution, cohort-frequency, churn-hazard-by-cohort) will share this slot.

---

## 3. `RetentionCard` + `ModelFitStatus` reuse

`RetentionCard` is a NEW dataclass alongside `ModelCard`. **Reuses the existing `ModelFitStatus` four-state enum** per the S11 Option A vocab-stacking precedent — labels shared, namespace-disambiguated by dataclass identity:

- `ModelCard.fit_status: ModelFitStatus` — per-customer ranker fits (BG/NBD, G-G, survival, CF, RFM).
- `RetentionCard.fit_status: ModelFitStatus` — cohort-aggregate retention.

Two distinct typed slots; same closed enum vocabulary. No new statuses added at S12.

Four states for retention:
- **VALIDATED**: CI width ≤ stage VALIDATED floor AND cohort_count ≥ stage VALIDATED floor AND no monotonicity violation.
- **PROVISIONAL**: CI width ≤ 0.35 (provisional ceiling) AND cohort_count ≥ 0.5 × stage VALIDATED floor (clamped ≥ absolute_floor=3).
- **INSUFFICIENT_DATA**: cohort_count < absolute_floor (3) OR min_cohort_size < 20.
- **REFUSED**: cumulative-retention monotonicity violation OR CI width > 0.35 OR catch-all (attempted fit, neither VALIDATED nor PROVISIONAL).

---

## 4. Cumulative-retention definition (chosen)

**Definition**: `cumulative_retention[M]` = fraction of cohort with ≥1 order in calendar months **strictly after the acquisition month**, i.e. `[first_month+1, first_month+M]`. By convention `cumulative_retention[0] = 0.0` (no post-acquisition months observed yet). For M ≥ 1, the curve is **monotonically non-decreasing**.

This is the post-acquisition "ever returned by month M" framing — equivalent to the standard DTC analytics retention curve (Reichheld 1990; Pfeifer-Carraway 2000). Excludes the trivial 100%-at-M0 floor (everyone in the cohort has, by definition, an order in their first month).

**Why this choice over "still active":** the DS verdict §G framed monotonicity either way ("ever returned" non-decreasing OR "still active" non-increasing); both permit a REFUSED gate on direction violation. The "ever returned (post-acquisition)" definition gives a meaningful, varying signal at the bootstrap layer (Bernoulli proportions in [0, 1] that bootstrap-resample with genuine variance), whereas a literal "% with ≥1 order in [M0, M0+M]" framing collapses to 1.0 across all M (because every cohort customer has an order at M0 by cohort definition) — bootstrap CIs collapse to [1.0, 1.0] regardless of seed. The post-acquisition framing was confirmed empirically: the initial impl used the "[M0, M0+M]" framing and the bootstrap variance test (`test_bootstrap_different_seed_yields_different_ci`) instrumentation surfaced that all CIs were [1.0, 1.0] — diagnostic that the framing was collapsing. Switched to post-acquisition; both the seed-determinism and seed-difference tests now pass.

The REFUSED gate fires when any cohort has a decreasing cumulative curve (mathematically impossible on this definition — signals a data-shape bug).

---

## 5. Positive-control synthetic result (DS-required, LOAD-BEARING)

DS-mandated fixture (per dispatch + DS verdict §K): "12 monthly cohorts × 200 customers each @ stable 40% month-1 retention by construction" with assertions `bootstrap_ci_width_at_month_3 < 0.10` AND `cumulative_retention_monotonicity_violation == False` AND `fit_status == VALIDATED`.

**DEVIATION FROM DS SPEC (requires DS review at T2 sign-off):**

At cohort_size=200 and p=0.40, Bernoulli sampling variance gives a theoretical 95% Wald CI width of ~0.136:

  half-width = 1.96 · sqrt(p(1-p)/n) = 1.96 · sqrt(0.4·0.6/200) ≈ 0.0679
  full width ≈ 0.136

The percentile bootstrap converges to this Wald CI in the large-n limit (verified empirically: at n=200 the bootstrap returns CI width 0.1334). **The CI<0.10 threshold cannot be satisfied at cohort_size=200 with p=0.40 by Bernoulli arithmetic alone.** The minimum cohort size for CI<0.10 at p=0.40 is:

  n > (2·1.96/0.10)² · 0.24 ≈ 369

To preserve the DS-mandated positive-control posture (VALIDATED with CI<0.10 on a healthy DGP), the test uses **cohort_size=400** instead of 200. The "stable 40% month-1 retention by construction" semantics are preserved. The implementation is correct (the bootstrap distribution matches Wald analytic CI in the large-n limit).

**Result at cohort_size=400:**

| Field | Value |
|---|---|
| `fit_status` | **VALIDATED** |
| `bootstrap_ci_width_at_month_3` | **0.09502** (DS-required < 0.10) |
| `cumulative_retention_monotonicity_violation` | **False** |
| `cohort_count` | 12 (all eligible) |
| `min_cohort_size` | 400 |
| `fit_warnings` | `[]` |

**Flag for DS:** confirm cohort_size=400 is acceptable, OR confirm CI<0.10 threshold should be relaxed to 0.15 (consistent with the mature VALIDATED floor at 0.15 from §G), OR confirm a different DGP parameter (e.g., p=0.15 / p=0.85 has lower variance — but 0.40 was the DS-specified prior).

---

## 6. briefing.html byte-identity (all 5 fixtures)

All five fixture HTML files unchanged. SHA-256 (computed post-staging):

| Fixture | sha256 |
|---|---|
| `tests/golden/small_sm/briefing.html` | `40bf24ea3c3632fa717293c82f66ac074d5e765ed29009b3297d2088952278e6` |
| `tests/golden/mid_shopify/briefing.html` | `380b2c5d0aa6806d81a38666c63603781e904f4e10a9fdfff72430551152d81a` |
| `tests/golden/micro_coldstart/briefing.html` | `2191b251edffbb7814e28a872e66b69e3d9289e680f077daa6ccea6a2694b2fc` |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | `13a91e6cd3200831fb9c17373ad316d961a80c05d75b5e6d749e6b314416d344` |
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | `f8676c9ff7d8a7ad6de77db07fb43ce415a3e05697c4c32979dfd391280e83a3` |

All five match the S12-T1 ledger exactly. Atomic-repin tests pass (50 passed, 2 xfailed pre-existing on `tests/test_s10_t1_5_bgnbd_rollback.py` + `tests/test_s11_t1_5_survival_rollback.py`).

---

## 7. Test / suite status

- **S12-T2 targeted tests:** 14 passed in `test_s12_t2_retention_fit.py` + 10 passed in `test_s12_t2_retention_threshold_loader.py` (24 total).
- **Predictive layer subset (S10-T1 / S10-T2 / S11-T1 / S11-T2 / S12-T1 / S12-T2 — threshold loaders + fits):** 111 passed, 1 pre-existing failure (`test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1` — stale after S12-T1.5 flipped RFM default to `true`; failure reproduces on plain HEAD, NOT introduced by S12-T2).
- **briefing.html byte-identity (load-bearing):** 55 passed, 1 xpassed (`tests/test_s8_t3_provenance.py` + `tests/test_slate_regression_beauty_brand.py` + `tests/test_golden_diff.py`).
- **EngineRun round-trip:** 17 passed (`tests/test_engine_run_schema.py`).
- **Atomic-repin + rollback (S6.5, S10-T1.5, S11-T1.5, S11-T2.5, S12-T1.5):** 50 passed, 2 xfailed (pre-existing).
- Full-suite run not performed at staging-time (deferred to orchestrator pre-commit per S12-T1 precedent).

---

## 8. Retention independence + cohort_diagnostics placement (explicit confirmation)

**Retention is INDEPENDENT** — no chained refusal on any prior substrate. Pinned at four layers:

1. **API surface.** `fit_retention(transactions_df, profile, *, store_id="", seed=0, yaml_path=None) -> RetentionCard` — signature contains no `bgnbd_model_card` / `gamma_gamma_model_card` / `survival_model_card` / `cf_model_card` / `rfm_model_card` argument. Pinned by `test_fit_retention_signature_does_not_accept_bgnbd_model_card` (uses `inspect.signature` against a `forbidden` set including all five prior substrates).
2. **Module docstring** (`src/predictive/retention.py`). Explicit "Retention is INDEPENDENT (no chained refusal)" block citing DS architectural posture.
3. **YAML inline comment** (`config/gate_calibration.yaml::model_fit_thresholds.retention`). Load-bearing comment co-located with thresholds: "Retention is INDEPENDENT — no chained refusal (parallels CF + RFM independence posture)."
4. **Behavioral test** (`test_independent_of_bgnbd_no_chained_refusal`). Constructs a REFUSED BG/NBD ModelCard alongside, runs `fit_retention` on the positive-control DGP, asserts no `chained_bgnbd*` warning and the fit status is determined by the data alone.

**Retention lives in `cohort_diagnostics`, NOT `predictive_models`** — pinned at three layers:

1. **Dataclass type.** `RetentionCard` is distinct from `ModelCard`; mypy/dataclass identity prevents a `ModelCard` write-through to `predictive_models` slot.
2. **Module docstring** (`src/predictive/retention.py`). "Lives in `engine_run.cohort_diagnostics["retention"]` (NOT `predictive_models`)" — load-bearing.
3. **Round-trip test** (`test_cohort_diagnostics_round_trips_via_engine_run`). Writes the card payload to `EngineRun.cohort_diagnostics["retention"]`, round-trips through `to_dict/from_dict`, asserts the slot is preserved and re-hydrated.

**No parquet artifact.** Retention curves are JSON-shaped (per-cohort dict of `period_retention` + `cumulative_retention` + `ci_lower` + `ci_upper` + `n_customers`) and live directly inside `engine_run.cohort_diagnostics`. Pinned by `test_no_parquet_artifact_for_retention` (scans the working dir post-fit for any `*retention*.parquet`).

---

## 9. Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Retention CI-width thresholds speculative-until-S14 | Known | KI-NEW-P extension; DS-locked at §G; real-merchant calibration at S14 closure (CI-honesty closure criterion per DS verdict §J: "real cohorts drift outside the band more often than 5%?"). |
| **Positive-control DGP cohort_size deviation from DS spec (200 → 400)** | Medium — requires DS review | Documented in test docstring + this summary §5. Math demonstrates CI<0.10 is mathematically impossible at n=200 p=0.40; raising n to 400 is the smallest change that preserves the DS-required positive-control assertions. Alternative paths: relax CI<0.10 to CI<0.15 (mature VALIDATED floor parity), or change p. **Surface to DS at T2 sign-off**. |
| Cumulative-retention definition framing choice (post-acquisition, not [M0, M]) | Low | Both framings permit REFUSED-on-violation. Post-acquisition is the standard DTC convention and gives a varying signal that exercises the bootstrap; the literal "[M0, M0+M]" framing collapses to constant 1.0 (instrumented and rejected during impl). Documented in module docstring + RetentionCard docstring. |
| Bootstrap iteration count (1000) on large cohorts (~thousands) | Low | Vectorized numpy sampling; per-cohort cost is O(iter × n) on integer indicator vectors; benchmark on positive-control 12×400 fits in <1s. T2.5 should profile on the Beauty fixture (3,844 repeat customers across ~9 cohorts) to confirm no orchestration regression. |
| Cohort eligibility filter (≥3 months forward visibility) | Diagnostic | Excludes the snapshot-month cohort from the primary gate (correct: month-3 retention not observable). On a 12-month-span fixture, expect 9 eligible cohorts; on the Beauty 259-day fixture (~8.5 calendar months) expect ~5-6 eligible cohorts. Documented in module docstring. |
| Pre-existing test stale (`test_s12_t1_rfm_fit::test_flag_default_off_at_t1`) | Pre-existing — not my regression | Reproduces on HEAD without my changes. Out of S12-T2 scope; flag for follow-up cleanup (S12-T1.5 should have removed it, missed). |

---

## 10. Deviation-check statement

**Deviation check: one documented test-fixture deviation; requires DS review.**

The positive-control synthetic uses `cohort_size=400` instead of the DS-specified `cohort_size=200` because at cohort_size=200, p=0.40, the percentile bootstrap returns a 95% CI width of ~0.133 (matches Wald analytic) — mathematically below the DS-required CI<0.10 threshold is impossible at n=200 by Bernoulli arithmetic alone. The minimum n satisfying CI<0.10 at p=0.40 is ~370; 400 is the smallest round-number cohort size that clears the threshold with margin (achieved CI=0.0950). The implementation is correct; the deviation is fixture-parameter only, fully documented, and surfaces here for DS sign-off at T2 acceptance.

All other dispatch-mandated artifacts landed exactly per the brief: YAML `model_fit_thresholds.retention` block (Commit A spec verbatim), `EngineRun.cohort_diagnostics` slot (Commit B; additive, tolerant from_dict, mirrors `predictive_models` precedent), `RetentionCard` dataclass with `ModelFitStatus` reuse + module docstring documenting Option A vocab-stacking (Commit C), `src/predictive/retention.py` with the documented `fit_retention(transactions_df, profile, *, store_id, seed=0, yaml_path=None)` signature (no chained model-card args), four-state classifier per DS thresholds, NO parquet artifact, NO chained refusal on BG/NBD, monotonicity-violation REFUSED gate, threshold loader `retention` subdict, `ENGINE_V2_ML_RETENTION` flag default OFF + added to `_coerce` bool set at T2 (Commit E), all required tests in `test_s12_t2_retention_fit.py` (≥8 listed in brief, delivered 14) + threshold-loader file (delivered 10 tests). All 5 briefing fixtures byte-identical. PlayCard stubs untouched, no ReasonCode additions, no orchestration wire-up, no new library (numpy only), no `requirements.txt` change, no scipy pin relaxation.

The CLAUDE.md instrumentation discipline ("two failed predictions = stop guessing") was respected: the seed-difference test failure was instrumented (printed bootstrap CIs across seeds) before changing impl. The instrumentation surfaced that cumulative retention was collapsing to `[1.0, 1.0, ...]` under the literal "[M0, M0+M]" framing — that diagnostic drove the post-acquisition reframing, not a guess.

---

## 11. Recommended T2.5 dispatch context (atomic flip — parallel to S12-T1.5)

When dispatching S12-T2.5, the brief should mirror the S12-T1.5 atomic-flip shape:

1. **Atomic single-commit flip** of `ENGINE_V2_ML_RETENTION` `false → true` together with the orchestration wire-up. Both land in one commit so rollback is one git revert (S10-T1.5 / S11-T1.5 / S11-T2.5 / S12-T1.5 precedent).
2. **Orchestration wire-up at `src/main.py`** in the existing PREDICTIVE_FIT block after the RFM (S12-T1.5) wire. Ordering: BG/NBD → G-G → survival → CF → RFM → **retention**. **Do NOT read any prior `engine_run.predictive_models[*]` when invoking `fit_retention`** — independence pin. Write the returned `RetentionCard` (as dict via `asdict`) to `engine_run.cohort_diagnostics["retention"]`, NOT `predictive_models`.
3. **Rollback test** `tests/test_s12_t2_5_retention_rollback.py` mirroring the S12-T1.5 rollback shape: with `ENGINE_V2_ML_RETENTION=false`, `engine_run.cohort_diagnostics` MUST NOT contain a `retention` entry; all 5 briefing.html shas remain byte-identical with the flag OFF.
4. **Retention-on-BG/NBD-OFF independence test** at the orchestration layer: pins that retention runs to its own four-state classification when `ENGINE_V2_ML_BGNBD=false`.
5. **Rollback test updates** for all prior `_rollback.py` `_run_and_load` helpers to set `ENGINE_V2_ML_RETENTION=false` explicitly so each rollback assertion remains clean under the new retention default-ON.
6. **briefing.html byte-identity is still a hard gate** at T2.5.
7. **No parquet path** — retention writes nothing under `data/<store_id>/predictive/`; D-3 deletion is a no-op for retention. Verify in T2.5 acceptance.
8. **Per DS verdict §I:** on the Beauty pinned fixture (~259 days ≈ 8-9 calendar months, MATURE/beauty profile), retention is **expected to land PROVISIONAL** (cohort_count_validated=12 for mature; Beauty has ~6 eligible cohorts at 3-month forward filter); supplements similar. Engine_run.json shapes will additively gain a `cohort_diagnostics["retention"]` entry on customer-rich fixtures.
9. **Determinism comparator extension at T2.5** (per DS §K): add normalized path `cohort_diagnostics.retention.fit_timestamp` to the same-run determinism comparator allowlist.
10. **Renderer non-consumption grep pin** at T2.5 acceptance criteria: `grep -rn "cohort_diagnostics\|retention" src/render_* → empty`.
11. **Deviation check: none** in commit body (unless additional DS-noted deviations land).
12. **Hold for DS sign-off on the §5 positive-control DGP cohort_size deviation BEFORE T2.5 dispatch.**

---

## 12. Outputs

- **Summary file:** `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s12-t2-summary.md` (this document).
- **Code module:** `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/retention.py`.
- **Tests:**
  - `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t2_retention_fit.py`
  - `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s12_t2_retention_threshold_loader.py`
- **Modified:** `config/gate_calibration.yaml`, `src/engine_run.py`, `src/predictive/__init__.py`, `src/predictive/model_card.py`, `src/utils.py`.

---

## 13. Commit message recommendation (for orchestrator)

Suggest **one commit for all S12-T2 changes** (substrate ticket; mirrors S12-T1 single-commit landing):

```
S12-T2: Retention curves substrate (cohort-aggregate diagnostic) — flag-OFF + RetentionCard + cohort_diagnostics slot + thresholds + tests

Sixth predictive substrate behind ENGINE_V2_ML_RETENTION (default OFF).
Architecturally different from prior 5: cohort-aggregate (not per-
customer ranker); lives in NEW top-level EngineRun.cohort_diagnostics
slot (NOT predictive_models); uses new RetentionCard dataclass (NOT
ModelCard) which REUSES the ModelFitStatus enum (Option A vocab-
stacking). NO parquet artifact — JSON-shaped curves live in
cohort_diagnostics directly. INDEPENDENT — no chained refusal on
BG/NBD or any other substrate (mirrors CF + RFM posture); fit_retention
takes no bgnbd_model_card argument.

- config/gate_calibration.yaml: append model_fit_thresholds.retention
  block with stage-keyed cells per DS-locked thresholds
  (bootstrap_ci_width_at_month_3 0.25/0.20/0.15/0.15 VALIDATED;
  PROVISIONAL ceiling 0.35; cohort_count 6/12/12/12 VALIDATED;
  absolute_cohort_count_floor 3; bootstrap_iterations 1000;
  months_horizon 12; min_cohort_size_floor 20;
  cumulative_retention_monotonicity_violation_refused true).
  Speculative-until-S14 (KI-NEW-P extension; DS verdict §G).
- src/engine_run.py: additive EngineRun.cohort_diagnostics: Dict[str,
  Any] slot (default {}); tolerant _from_dict_engine_run round-trip.
  Cohort-aggregate diagnostics slot (NOT predictive_models which stays
  ranker-pure) per DS §C.
- src/predictive/model_card.py: NEW RetentionCard dataclass reusing
  ModelFitStatus enum (Option A vocab-stacking); cumulative_retention
  definition documented as "ever returned in [first_month+1,
  first_month+M]" (post-acquisition, non-decreasing); threshold loader
  returns retention / retention_relaxation_factors / retention_guards
  subdicts; fallback constants aligned to YAML mature cell.
- src/predictive/retention.py (NEW, ~530 LoC): fit_retention(
  transactions_df, profile, *, store_id, seed=0, yaml_path=None) — no
  chained model-card args; retention INDEPENDENT per DS §C. Flow:
  INSUFFICIENT_DATA gates (absolute cohort floor 3; min cohort size
  20) → per-cohort grouping by first-purchase month (filtered to ≥3
  months forward visibility) → per-cohort period+cumulative curves
  (post-acquisition cumulative framing) → vectorized percentile
  bootstrap CIs (seed=0 default) → bootstrap_ci_width_at_month_3
  averaged across cohorts → monotonicity check → four-state classifier
  (REFUSED on monotonicity violation or CI > 0.35) → write
  RetentionCard. NO parquet (JSON-shaped curves go to
  cohort_diagnostics directly at T2.5).
- src/predictive/__init__.py: docstring extended for S12-T2 retention
  independence + cohort-aggregate framing + cohort_diagnostics slot
  + ModelFitStatus reuse.
- src/utils.py: ENGINE_V2_ML_RETENTION default "false"; added to
  _coerce bool set at T2 (S10-T1.5 lesson).
- tests/test_s12_t2_retention_fit.py (NEW, 14 tests): INSUFFICIENT_DATA
  paths, retention-independence-from-BG/NBD contract (inspect.signature
  + behavioral), positive-control DGP sanity (LOAD-BEARING; DS-
  mandated; VALIDATED @ CI=0.0950 < 0.10 on 12×400-customer cohorts —
  see summary §5 for the documented cohort_size 200→400 deviation
  requiring DS review at T2 sign-off), monotonicity-violation REFUSED
  (via monkeypatch), monotonicity detector unit, bootstrap seed
  determinism + seed-difference sanity, no parquet artifact,
  ENGINE_V2_ML_RETENTION default OFF, cohort_diagnostics round-trip
  through EngineRun, pre-S12 payloads default {}.
- tests/test_s12_t2_retention_threshold_loader.py (NEW, 10 tests):
  per-stage cells, relaxation factors, guards, profile=None fallback,
  additive coexistence, HIGH-uncertainty broadening, YAML-missing
  fallback.

Positive-control synthetic: cohort_size=400, p=0.40, 12 cohorts.
fit_status=VALIDATED, CI@m3=0.0950, no monotonicity violation, 12
eligible cohorts. (DEVIATION from DS-specified n=200 documented in
summary §5; math requires n>~370 for CI<0.10 at p=0.40; flag for DS.)
Suite: 24 new tests pass; 55 byte-identity tests pass; all 5 briefing
shas byte-identical with S12-T1 ledger.

Flag-OFF land. Orchestration wire-up + atomic flip = S12-T2.5.

Deviation check: one — positive-control DGP cohort_size 200→400 per
Bernoulli arithmetic; requires DS sign-off at T2 acceptance. See
summary §5 + §10.
```

---

**Deviation check: one documented — positive-control DGP cohort_size 200→400. Requires DS sign-off at T2 acceptance per summary §5 + §10. All other artifacts per brief.**
