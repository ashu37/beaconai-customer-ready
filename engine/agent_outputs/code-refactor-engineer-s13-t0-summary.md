# Code Refactor Engineer — S13-T0 Summary

**Ticket:** S13-T0 — ModelCard refactor to `Dict[str, float] metrics` shape (FLAG-OFF; pure substrate-side schema change, no consumer wiring).
**Date:** 2026-05-29.
**Status:** STAGED. Orchestrator commits.

---

## 1. Approved scope

DS-locked T0 candidate confirmed DO per DS S13 plan review §C. Pure substrate-side schema refactor; no flag; no consumer wiring; no PlayCard changes; no `decide.py` / `sizing.py` / `main.py` orchestration changes. Renderer non-consumption was grep-verified by S13 plan §L.

Refactor target: `ModelCard.metrics: Dict[str, float]` as authoritative storage. Legacy typed Optional fields (`holdout_mape`, `holdout_rank_spearman`, `holdout_agg_ratio`, `holdout_c_index`, `holdout_brier_score_90d`, `holdout_top_k_recall`, `coverage_at_k`, `segment_monotonicity_spearman`, `quintile_coverage_min`) become read-only shims.

Per-substrate ModelCards stay distinct objects at `predictive_models[<substrate>]`. RetentionCard untouched (separate dataclass in `cohort_diagnostics`).

---

## 2. Patch summary

Substrate-side schema refactor with a 2-mechanism back-compat surface:

1. **`metrics: Dict[str, float]` authoritative storage** added to `ModelCard` as a real dataclass field (default `{}`). Serializes via `asdict()` into engine_run.json as `predictive_models["<substrate>"].metrics = {...}`.

2. **Constructor-kwarg back-compat (legacy field names):** 9 `InitVar[Optional[float]]` declarations for the legacy metric names. Pre-S13 callers passing `ModelCard(..., holdout_mape=0.21, ...)` still work — the `__post_init__` migrates the value into `self.metrics["holdout_mape"]`. Caller-passed `metrics={...}` wins for keys already present.

3. **Read-side back-compat (`card.holdout_X` reads):** `__getattr__` shim returns `self.metrics.get(name)` for the 9 legacy keys; returns `None` when absent. Closed allowlist `_LEGACY_METRIC_KEYS = frozenset({...})`. A class-attribute strip removes the lingering `None` values left by `@dataclass`'s InitVar processing so `__getattr__` actually fires.

Critically: because the legacy names are `InitVar`s (consumed by `__init__`, not stored as fields), they do NOT appear in `asdict(card)` — so engine_run.json carries ONLY `metrics`, no duplicative legacy top-level keys.

Substrate producers updated to write `metrics={...}` directly (cleaner than relying on legacy kwarg path). Constructor sites in `bgnbd.py`, `gamma_gamma.py`, `survival.py`, `cf.py`, `rfm.py` all converted.

---

## 3. Files changed

| File | Change |
|---|---|
| `src/predictive/model_card.py` (L66, L182-273, L300-322) | Added `metrics` field. Added 9 `InitVar` legacy kwargs. Added `__post_init__` migrating legacy kwargs into `metrics`. Added `__getattr__` shim + `_LEGACY_METRIC_KEYS` allowlist. Added class-attribute strip block. Docstring updated. |
| `src/predictive/bgnbd.py` (4 INSUFFICIENT_DATA/REFUSED sites + 3 metric-populated sites) | Replaced `holdout_mape=/holdout_rank_spearman=/holdout_agg_ratio=` kwargs with `metrics={}` (refusal cases) or `metrics={"holdout_mape": ..., "holdout_rank_spearman": ..., "holdout_agg_ratio": ...}`. |
| `src/predictive/gamma_gamma.py` (5 refusal sites + 6 metric-populated sites) | Same pattern as bgnbd. |
| `src/predictive/survival.py` (7 refusal sites + 6 metric-populated sites with c_index/brier_90d) | `metrics={"holdout_c_index": ..., "holdout_brier_score_90d": ...}`. |
| `src/predictive/cf.py` (9 refusal sites + 3 metric-populated sites) | `metrics={"holdout_top_k_recall": ..., "coverage_at_k": ...}`. |
| `src/predictive/rfm.py` (4 refusal sites + 4 metric-populated sites) | `metrics={"segment_monotonicity_spearman": ..., "quintile_coverage_min": ...}`. |
| `tests/test_model_card_metrics_dict_shape.py` (NEW; 8 tests) | Pins: empty default; metrics write→read; legacy shim reads; legacy constructor-kwarg routes into metrics; metrics-kwarg-wins-over-legacy precedence; JSON round-trip preserves values; **JSON does NOT carry legacy top-level keys** (metrics-only contract); refusal serializes as `metrics: {}`. |
| `tests/test_s11_t2_5_cf_rollback.py` (L163-176 → L163-181) | **Test migration (documented deviation)**: rollback test previously asserted `"holdout_top_k_recall" in card` at JSON top level. Updated to assert `"metrics" in card` and `card["metrics"].get("holdout_top_k_recall") is not None`. Same back-compat contract semantics. |
| `tests/test_s12_t1_5_rfm_rollback.py` (L167-185 → L167-185) | Same migration: `card[<legacy>]` → `card["metrics"][<legacy>]`. |

No changes to: `src/engine_run.py`, `src/main.py` orchestration, `src/decide.py`, `src/sizing.py`, `src/audience_builders.py`, `src/guardrails.py`, RetentionCard, PlayCard, fixtures, briefing renderer.

---

## 4. ModelCard refactor shape

```python
@dataclass
class ModelCard:
    model_name: str = ""
    fit_status: ModelFitStatus = ModelFitStatus.INSUFFICIENT_DATA
    fit_warnings: List[str] = field(default_factory=list)
    parameters: Dict[str, float] = field(default_factory=dict)
    training_window_days: int = 0
    n_observed: int = 0
    metrics: Dict[str, float] = field(default_factory=dict)   # NEW (authoritative)
    fit_timestamp: str = ""
    parquet_schema_version: int = 1

    # 9 InitVar back-compat constructor kwargs (NOT stored as fields):
    holdout_mape: InitVar[Optional[float]] = None
    holdout_rank_spearman: InitVar[Optional[float]] = None
    ...  # 7 more

    def __post_init__(self, holdout_mape, holdout_rank_spearman, ...):
        # Migrate non-None legacy kwargs into self.metrics (metrics={} kwarg wins).
        ...

    def __getattr__(self, name):
        if name in _LEGACY_METRIC_KEYS:
            return self.metrics.get(name)
        raise AttributeError(...)

# Strip vestigial class attributes the @dataclass decorator left behind
# (so __getattr__ actually fires for these names on instances):
for _legacy_key in _LEGACY_METRIC_KEYS:
    if _legacy_key in ModelCard.__dict__:
        delattr(ModelCard, _legacy_key)
```

**Three back-compat reads/writes proven by tests:**
- `card.holdout_rank_spearman` returns `metrics.get("holdout_rank_spearman")` — including `None` when absent. No `AttributeError`.
- `ModelCard(holdout_mape=0.21, ...)` puts `0.21` into `metrics["holdout_mape"]` via `__post_init__`.
- `ModelCard(metrics={"holdout_mape": 0.5}, holdout_mape=0.99, ...)` keeps `0.5` (explicit dict wins).

---

## 5. Substrate producer updates

| Substrate | Metrics dict keys written |
|---|---|
| `bgnbd.py` | `holdout_mape`, `holdout_rank_spearman`, `holdout_agg_ratio` |
| `gamma_gamma.py` | `holdout_mape`, `holdout_rank_spearman`, `holdout_agg_ratio` |
| `survival.py` | `holdout_c_index`, `holdout_brier_score_90d` |
| `cf.py` | `holdout_top_k_recall`, `coverage_at_k` |
| `rfm.py` | `segment_monotonicity_spearman`, `quintile_coverage_min` |

Refusal / INSUFFICIENT_DATA paths emit `metrics={}` (empty dict). No substrate logic, classifier rules, parquet semantics, fit-warning vocabulary, or threshold reads were touched — purely storage-mechanism conversion. Chained-refusal short-circuits (`bgnbd_model_card.fit_status` reads in `gamma_gamma.py:461` and `survival.py`) are unaffected — they read regular dataclass fields, not the migrated metric fields.

---

## 6. JSON serialization decision

**Picked: metrics-only in engine_run.json** (per DS recommendation in dispatch brief).

Rationale:
- `InitVar` declarations are consumed by `__init__` and never become dataclass fields → `asdict(card)` does not emit them as top-level keys.
- `@dataclass` walks declared fields only; the explicit `metrics` field is the only metric-bearing field in the JSON.
- Engine_run.json shape:
  ```json
  "predictive_models": {
    "bgnbd": {
      "model_name": "bgnbd",
      "fit_status": "VALIDATED",
      "fit_warnings": [],
      "parameters": {"r": 0.5, ...},
      "training_window_days": 180,
      "n_observed": 3844,
      "metrics": {"holdout_mape": 0.21, "holdout_rank_spearman": 0.55, "holdout_agg_ratio": 0.92},
      "fit_timestamp": "...",
      "parquet_schema_version": 1
    }
  }
  ```
- Python-object level: `card.holdout_rank_spearman` continues to work via `__getattr__` shim (legacy tests, chained consumers).
- JSON-level: consumers must read `card["metrics"]["holdout_rank_spearman"]`.

Two rollback tests (S11-T2.5 CF, S12-T1.5 RFM) asserted legacy key presence at JSON top-level. Migrated to read from `card["metrics"]` — flagged as deviation in section 11.

---

## 7. Per-fixture engine_run.json check

Spot-checked via `tests/test_slate_regression_supplements_brand.py` (Supplements pinned briefing sha) and the Beauty pinned-slate harness (`tests/test_s7_6_c1_priority_prepend_invariant.py` runs end-to-end on Beauty and asserts content). Both pass byte-identical. The relevant `predictive_models` slot is `{}` on both fixtures at current flag defaults (KI-NEW-U: ML flags are still ON in defaults, but no fixture-stage hits VALIDATED, so the slot carries refused/insufficient cards with `metrics={}`). Round-trip through `EngineRun.from_dict(EngineRun.to_dict(er))` proven in the new test file.

---

## 8. All 5 briefing.html sha confirmation

`tests/test_slate_regression_supplements_brand.py` (Supplements briefing pinned sha256) and `test_s5_t1_supplements_priors_populated.py` (sha-stability claim) — both green. The Beauty pinned content (recommended now + recommended experiment + considered + watching cards) round-trips identical through the full pipeline as evidenced by `tests/test_s7_6_c1_priority_prepend_invariant.py` (Beauty observed-effect tripwire on 4 Tier-B cards) and the broader S5/S6/S7 integration suites: all green.

Renderer does NOT consume `predictive_models` (per S13 plan §L grep verification, restated). Briefing byte-identity is preserved by construction.

---

## 9. Suite status

**Full suite: 2058 passed, 14 skipped, 4 xfailed, 2 xpassed, 3 failed in 1892s.**

**All 3 failures are pre-existing known issues explicitly excluded by the brief:**
- `tests/test_s12_t1_rfm_fit.py::test_flag_default_off_at_t1` — KI-NEW-U (stale flag-default-off test; `ENGINE_V2_ML_RFM` default flipped ON at S12-T1.5).
- `tests/test_s12_t2_retention_fit.py::test_engine_v2_ml_retention_flag_default_off` — KI-NEW-U.
- `tests/test_synthetic_fixtures_8_11.py::TestFix11LowInventoryRunnerClock::test_inventory_updated_at_is_fresh` — KI-NEW-S (wall-clock flake).

**Zero new failures from S13-T0.**

**Targeted spot-checks (all green):**
- All 62 substrate predictive tests (S10-T1 model_card + bgnbd + S11-T1 survival + S11-T2 cf + S12-T1 rfm).
- All 6 rollback test files (s10/s11/s12 × bgnbd/gg/survival/cf/rfm/retention) except the 2 known stale-flag tests above.
- All 8 tests in the new `tests/test_model_card_metrics_dict_shape.py`.
- Briefing sha pins (Supplements + Beauty content invariants).
- S7.6 priority-prepend observed-effect tripwire.

---

## 10. Behavior changes

- **Python-object level:** none. `card.holdout_X` continues to return the same float value (or None) as before via the `__getattr__` shim.
- **engine_run.json level:** `predictive_models["<substrate>"]` no longer carries top-level `holdout_mape` / `holdout_rank_spearman` / `holdout_agg_ratio` / `holdout_c_index` / `holdout_brier_score_90d` / `holdout_top_k_recall` / `coverage_at_k` / `segment_monotonicity_spearman` / `quintile_coverage_min` keys. Same values now live inside `metrics: {...}`. JSON consumers reading the legacy keys see `KeyError`; they must read from `metrics`.
- **briefing.html:** byte-identical (renderer non-consumption pinned).
- **PlayCard:** `predicted_segment` and `model_card_ref` stay None. No consumer wiring at T0.
- **Flags:** no new flag. No flag-default change.

---

## 11. Risk assessment

**Low-medium.**

1. **JSON schema break for any out-of-tree consumer parsing legacy top-level keys.** DS-recommended path per the brief; intended consequence of metrics-only-in-JSON. Two in-tree rollback tests caught this and were migrated. No other in-tree consumer found via `grep -rn '"holdout_<key>"' src/`.

2. **InitVar + same-name `@property` conflict avoided by switching to `__getattr__` + class-attribute strip.** `@dataclass`'s InitVar mechanism leaves vestigial `None` class attributes that would shadow `__getattr__`; the `delattr` block at module load eliminates them. Closed allowlist `_LEGACY_METRIC_KEYS` keeps the shim scope tight.

3. **Caller-passed `metrics={}` precedence over legacy kwargs in `__post_init__`.** Pinned by `test_metrics_dict_kwarg_wins_over_legacy_kwarg`. Subtle but covered.

4. **Pre-existing 3 known-issue failures (KI-NEW-U × 2 + KI-NEW-S × 1)** unchanged by this refactor.

5. **No risk to single-demote-channel invariant** — refactor never touches `engine_run.recommendations` or `apply_guardrails`.

6. **No risk to byte-identity on the 5 pinned fixtures** — verified.

---

## 12. Artifacts added

- `tests/test_model_card_metrics_dict_shape.py` (8 tests).
- `agent_outputs/code-refactor-engineer-s13-t0-summary.md` (this file).

No new fixtures. No new YAML.

---

## 13. Deviation check

**Deviation check: one (test migration; documented).**

Per dispatch-brief acceptance criterion #7 ("All existing predictive-layer tests pass without modification"), the rollback tests at `tests/test_s11_t2_5_cf_rollback.py` (L165-176) and `tests/test_s12_t1_5_rfm_rollback.py` (L170-185) needed updating because they pinned the JSON top-level key shape, which intentionally changes under the metrics-only-in-JSON decision (DS-recommended in the brief itself: "consumers parsing JSON should read from `metrics`").

The migration was minimal: change `assert "X" in card` → `assert "metrics" in card` plus `card["metrics"].get("X")` checks. Same back-compat contract semantics. The brief explicitly authorizes this fix path: "If a consumer parsing engine_run.json is found that reads legacy keys directly, fix that consumer to read from `metrics`."

This is the only "modification to existing tests" — all 62 substrate-fit tests (S10-T1 / S11-T1 / S11-T2 / S12-T1 / S12-T2) and the 4 other rollback test files (bgnbd / gg / survival / retention rollback) pass UNMODIFIED via the `__getattr__` shim, as required by the brief's back-compat contract.

No other deviations from the dispatched plan.

---

## 14. Recommended T1 dispatch context

T1 — `src/predictive/ranking_strategy.py` module + `AudienceIntent` enum + positive-control synthetic.

Context for T1 dispatch:
- ModelCard now exposes `card.metrics` for direct dict reads. T1 ranking-strategy fallback chain (`BG/NBD → CF → survival → RFM (floor) → recency`) should consume `metrics.get(<key>)` directly rather than the typed shim — cleaner for new code per the S13-T0 closure contract.
- The `__getattr__` shim is provided for legacy back-compat only; new T1+ code should NOT add new keys to `_LEGACY_METRIC_KEYS`.
- `RetentionCard` (the cohort-aggregate retention substrate) is unchanged at T0 and lives in `engine_run.cohort_diagnostics["retention"]`, NOT `predictive_models`. T1 ranking strategy reads BG/NBD + CF + survival + RFM ModelCards from `predictive_models`; retention is not in the ranking chain.
- `PlayCard.predicted_segment` and `PlayCard.model_card_ref` stubs are still None — T2+ wires them per IM S13 plan.
- Substrate composition rules: survival CHAINS BG/NBD; CF / RFM / retention are INDEPENDENT (4-layer pin preserved). The chained-refusal reads in `gamma_gamma.py:461` (`bgnbd_model_card.fit_status`) are unaffected by T0.

---

## 15. Commit message recommendation

```
refactor(predictive): S13-T0 ModelCard.metrics dict shape + back-compat shims

Move per-substrate ModelCard metric storage from typed Optional fields
to an authoritative metrics: Dict[str, float] dict (DS-locked, S13-T0).

- ModelCard.metrics field added; serialized into engine_run.json as
  predictive_models["<substrate>"].metrics.
- Legacy typed Optional names (holdout_mape, holdout_rank_spearman,
  holdout_agg_ratio, holdout_c_index, holdout_brier_score_90d,
  holdout_top_k_recall, coverage_at_k, segment_monotonicity_spearman,
  quintile_coverage_min) become:
    - InitVar back-compat kwargs: pre-S13 callers
      (ModelCard(..., holdout_mape=0.21, ...)) keep working;
      __post_init__ migrates values into metrics dict.
    - __getattr__ read shim: card.holdout_X returns
      metrics.get(name); None when absent.
  Net effect: object-level reads/writes back-compat;
  engine_run.json metrics-only (no duplicate legacy top-level keys).
- Substrate producers (bgnbd, gamma_gamma, survival, cf, rfm) write
  metrics={} or metrics={<key>: <val>, ...} directly. No substrate
  logic / classifier rule / parquet semantic / fit_warning vocabulary
  changes.
- Two S11/S12 rollback tests migrated from card["<legacy>"] to
  card["metrics"][<legacy>] reads (test-side migration of the
  metrics-only-in-JSON contract; DS-recommended path).
- New tests/test_model_card_metrics_dict_shape.py pins the 8
  contracts: default-empty, write/read round-trip, legacy shim reads,
  legacy-kwarg back-compat, explicit-dict precedence, JSON round-trip,
  no-legacy-keys-in-JSON, refusal-serializes-as-empty-metrics.

RetentionCard untouched (separate dataclass in cohort_diagnostics).
PlayCard.predicted_segment / model_card_ref stay None at T0.
No new flag. No briefing.html change (renderer non-consumption).
Full suite: 2058 passed; 3 pre-existing KI-NEW-U + KI-NEW-S
failures excluded per dispatch brief.

Deviation check: one (test migration; documented in
agent_outputs/code-refactor-engineer-s13-t0-summary.md §13).
```
