# Milestone 1 — Code Refactor Engineer Summary

_Completed: 2026-05-01 (engine-rework branch)_

## Approved scope

Milestone 1 of `agent_outputs/implementation-manager-overhaul-plan-final.md`:
additive `EngineRun` schema, anomaly detection, typed `Observation`
builder, validation extension. **Receipts-only** — nothing in M1 changes
merchant-facing output. Tickets T1.1, T1.2, T1.3, T1.4, T1.5, T1.6.

## Files changed

### New files

- `src/engine_run.py` — typed PM-Q2 dataclass schema (`EngineRun`,
  `PlayCard`, `RejectedPlay`, `WatchedSignal`, `Observation`,
  `Audience`, `Measurement`, `RevenueRange`, `Inventory`, `Conflicts`,
  `LaunchWindow`, `Scale`, `BriefingMeta`, `DataWindow`, `Abstain`).
  Includes 5 typed enums (`EvidenceClass`, `DecisionState`,
  `ReasonCode` with all 12 codes including `cap_exceeded`,
  `DataQualityFlag`, `ObservationClassification`,
  `RevenueRangeSource`). Provides `to_dict()` / `from_dict()` for
  round-trip serialization. T1.1.
- `src/anomaly.py` — 5 pure-function detectors (`detect_bfcm_overlap`,
  `detect_post_promo_window`, `detect_refund_storm`,
  `detect_test_order_anomaly`, `detect_insufficient_clean_history`)
  combined into `detect_anomalous_windows`. Loads thresholds from
  `config/anomaly_thresholds.yaml`. T1.2.
- `config/anomaly_thresholds.yaml` — conservative default thresholds
  per detector. Schema-versioned. T1.2.
- `src/state_of_store.py` — `build_observations(aligned, scale,
  data_quality_flags)` returns 3–5 typed `Observation` records. No
  prose templating. T1.4.
- `src/engine_run_adapter.py` — `build_engine_run_from_legacy()` maps
  the legacy `actions_bundle` dict into a typed `EngineRun`. Lossy by
  design; documented. T1.3.
- `tests/test_engine_run_schema.py` — 7 tests: instantiation,
  round-trip, enum coercion, the 12 reason codes are declared, the 5
  data quality flags are declared, T1.6 empty-list serialization
  invariant.
- `tests/test_anomaly.py` — 16 tests: each detector positive + negative
  on synthetic in-memory fixtures; combiner determinism; thresholds
  YAML loadable; empty-DF safety.
- `tests/test_observations.py` — 8 tests: 3–5 observation cardinality,
  metric coverage, classification thresholds, anomaly surface,
  graceful degradation on missing/partial input.
- `agent_outputs/code-refactor-engineer-milestone-1-summary.md` — this
  file.

### Edited files

- `src/main.py` — imports `build_engine_run_from_legacy`; after
  `write_actions_log`, builds an `EngineRun` and writes
  `receipts/engine_run.json`. Wrapped in try/except so an adapter bug
  cannot fail a run. **No other changes** — legacy `actions_bundle`
  shape, `actions_log.json`, briefing render path, and validation
  pipeline are untouched. T1.3.
- `src/validation.py` — adds `AnomalousWindowCheck` class (T1.5). The
  class is **NOT registered** in `DataValidationEngine.__init__`'s
  default `self.checks` list; gating it behind opt-in
  `include_anomaly_check=False` preserves the M0 `validation_report.json`
  golden contract on fixtures whose L28 happens to overlap BFCM. M5
  will flip the default and gate accordingly. The detector output is
  already surfaced in `engine_run.json` via the legacy adapter. See
  "Skipped items" below for the precise rationale.

## Exact commands run (and outcomes)

| Command | Result |
|---|---|
| `python -m pytest tests/test_engine_run_schema.py tests/test_anomaly.py tests/test_observations.py -v` | **31 passed** |
| `python -m pytest tests/test_golden_diff.py -v` | **3 passed** (M0 still green) |
| `python -m pytest tests/ -v` | **34 passed** total |
| `make test` | **34 passed** |
| `python -m src.main --orders data/shopify_orders_micro_*.csv --brand m1_smoke --out /tmp/m1_smoke_run` | pass — `engine_run.json` produced; 3 state-of-store observations; 0 recommendations; abstain=abstain_soft (no legacy actions) |
| `python -m src.main --orders data/SM_orders.csv --brand m1_small --out /tmp/m1_small_run` | pass — `engine_run.json` produced; 3 recommendations mapped from legacy bundle; scale.monthly_revenue computed |

## Tests / checks run

- 31 new tests across 3 new test files, all green.
- 3 M0 golden diff tests, all green (briefing.html byte-identical for
  all three fixtures).
- Two end-to-end smoke runs (`shopify_orders_micro_*.csv`,
  `SM_orders.csv`) confirm `receipts/engine_run.json` is produced and
  schema-valid. No new errors in stdout/stderr.

## Whether M0 golden diff still passes

**YES.** All three M0 golden trees (`micro_coldstart`, `small_sm`,
`mid_shopify`) match byte-for-byte after every M1 change. Verified
twice during implementation (after the validation.py edit was
recalibrated to opt-in, and again after the adapter wiring landed).
This is the central acceptance criterion for M1; it holds.

The decision tree:
- `engine_run.json` is intentionally **NOT** in
  `RECEIPTS_FILES_TO_FREEZE` (preferred option (a) per the M1
  instructions). M1 does not touch the M0 freeze list.
- `validation_report.json` IS in the M0 freeze list. To preserve the
  golden contract, `AnomalousWindowCheck` is **defined** in M1 but
  **not auto-registered** in `DataValidationEngine`. M5 will flip the
  default and add the gating layer.

## Artifacts created

```
src/engine_run.py
src/anomaly.py
src/state_of_store.py
src/engine_run_adapter.py
config/anomaly_thresholds.yaml
tests/test_engine_run_schema.py
tests/test_anomaly.py
tests/test_observations.py
agent_outputs/code-refactor-engineer-milestone-1-summary.md
```

Plus, on every engine run going forward:

```
{out_dir}/receipts/engine_run.json
```

A typical small-merchant `engine_run.json` is ~3 KB.

## Behavior changes

None merchant-facing. Verified:

- `briefing.html` byte-identical against all 3 M0 goldens.
- `validation_report.json` byte-identical against all 3 M0 goldens (no
  new check key).
- `actions_log.json`, `run_summary.json`, `engine_validation_report.json`,
  `dataframe_debug.json`, `df_for_charts_counts.json` all unchanged.
- Two new behaviors:
  - `receipts/engine_run.json` is produced (additive; not in golden
    set; not consumed by the renderer in M1).
  - `AnomalousWindowCheck` class is importable for downstream code
    (M5 will register it).

## Skipped items and why

- **`AnomalousWindowCheck` is NOT auto-registered** in
  `DataValidationEngine.__init__`. The M1 ticket text says "surfaces
  in the validation report". Doing so unconditionally would add a new
  top-level key (`Anomalous Window`) to `validation_report.json`,
  which IS in the M0 golden whitelist, on every fixture whose L28
  overlaps BFCM (e.g., a Dec-anchored fixture). That breaks the M0
  golden contract — the central acceptance criterion. The class is
  defined, importable, and its M5 caller can flip it on with
  `DataValidationEngine(include_anomaly_check=True)`. Detector output
  IS surfaced in M1 via `engine_run.json` (the new receipts file)
  through `build_engine_run_from_legacy` -> `detect_anomalous_windows`.
  This preserves both the M1 ticket intent (detector surfaces in
  receipts) and the M0 contract.

  *Assumption:* "validation report" in T1.5 means "any receipts
  artifact" since both `validation_report.json` and `engine_run.json`
  are receipts. The fixed point is the M0 golden contract, which the
  instructions promote above all else ("M0 goldens still pass" is
  acceptance criterion).

- **No `data/recommended_history.json` writer.** That's M9 (T9.1),
  not M1.

- **No `evidence.py` / classifier.** That's M4a (T4a.4), not M1.

- **No fabricated-stats removal.** Legacy `journey_optimization`,
  `frequency_accelerator`, etc. continue to expose their hardcoded
  p/effect/CI on the legacy bundle, and the adapter carries those
  values into `engine_run.json` as-is. The M4a milestone is the
  boundary where these get NaN'd. M1's contract is to
  *not pre-empt* that work.

- **No play registry / priors.yaml** (M2).

- **No detect/select/decide split** (M3/M7).

- **No renderer flip.** Briefing still reads the legacy actions
  bundle. M8 is the renderer flip.

## Readiness for Milestone 2

Green to start M2. Open items the M2 author should be aware of:

1. **`engine_run.json` is not in goldens.** M2 can leave it that way
   or add it once the schema is stable. M2 itself does not need to
   touch the freeze list.

2. **`build_engine_run_from_legacy` is lossy.** M2's play registry
   should provide the canonical mapping from `play_id` -> default
   `evidence_class`, which the adapter currently approximates as
   `EvidenceClass.TARGETING` when missing. Wire that in M2/M3.

3. **`measurement.p_internal` / `ci_internal` are populated by the
   legacy bundle for any candidate with stats today** — including
   fabricated ones. M4a will NaN them. Until M4a, treat
   `p_internal == 1e-10` and similar as fabricated artifacts.

4. **`scale.materiality_floor` is None.** M5 (T5.3) computes the
   scale-aware floor.

5. **`considered` and `watching` lists are always empty in M1**
   regardless of input. M5/M7 populate them. The schema slot exists.

6. **`AnomalousWindowCheck` opt-in.** When M5 wires gating, the call
   site in `main.py` should construct
   `DataValidationEngine(include_anomaly_check=True)` and add the
   golden regeneration to that PR's migration list. This is the only
   place where M5 will need to break the existing
   `validation_report.json` golden contract; it is otherwise additive.

7. **No engine-side anchor support.** The engine still derives anchor
   from `aligned['anchor']`; the EngineRun adapter passes that through
   as `anchor_date`. If a future ticket adds explicit `--anchor`
   support, also wire it through the adapter.

8. **No new env flags in M1.** Per the M1 instructions, M1 is
   additive and on by default since it is receipts-only. There is no
   `ENGINE_V2`-style flag to flip.

## Risks (and how M1 mitigates them)

- **Adapter exception ⇒ run fails.** Mitigated: the
  `engine_run.json` write block in `main.py` is wrapped in
  try/except. An adapter bug logs a `[EngineRun]` warning and the run
  continues normally.

- **Schema drift between M1 and M2/M5.** Mitigated: `EngineRun`
  carries `schema_version = "1.0.0"`. Bump on incompatible changes.

- **Anomaly detector false positives change merchant output.**
  Mitigated: detectors are receipts-only in M1; not auto-registered
  in the validation gating path; M5 will tune thresholds before the
  gating layer flips on.

- **Round-trip lossy because Python `enum.Enum.value` collisions.**
  Mitigated: all enum values are unique strings; round-trip is tested
  with a fully-populated `EngineRun` that exercises every enum
  member.

## Validation summary

- 34 tests pass (3 M0 golden + 7 schema + 16 anomaly + 8 observation).
- 0 changes to merchant-facing output.
- 0 changes to legacy `actions_bundle` shape.
- 0 new env flags.
- 1 new receipts file: `engine_run.json`.
- 5 new modules: `engine_run.py`, `anomaly.py`, `state_of_store.py`,
  `engine_run_adapter.py`, plus `tests/test_*.py` triple.
- 1 new config: `config/anomaly_thresholds.yaml`.
- 1 surgical edit to `main.py` (4-line block, try/except guarded).
- 1 surgical addition to `validation.py` (new class + opt-in
  registration).
