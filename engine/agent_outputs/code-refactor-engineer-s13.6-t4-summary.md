# S13.6-T4 — FitWarning typed grammar (D-S13-4 structural)

**Sprint/ticket:** S13.6-T4 — replace `ModelCardRef.fit_warnings: List[str]`
(`"{LEVEL}:{substrate}"` string grammar that lived in code comments only)
with typed `List[FitWarning(level: FitWarningLevel, substrate: str)]`.

Per `docs/DECISIONS.md::D-S13-4` (grammar lock origin). Sibling of T1a /
T1b / T2 / T3 per DS R5 atomic-split discipline.

## File change table

| Path | Lines added | Lines removed | Net |
|------|------------:|--------------:|----:|
| `src/engine_run.py` | ~80 | ~10 | +70 |
| `src/predictive/ranking_strategy.py` | ~45 | ~25 | +20 |
| `src/predictive/consumer_wiring.py` | 3 | 2 | +1 |
| `tests/test_ranking_strategy_positive_control.py` | ~25 | ~20 | +5 |
| `tests/test_s13_t2_predicted_segment_population.py` | ~15 | ~12 | +3 |
| `tests/test_s13_renderer_non_consumption.py` | ~22 | 0 | +22 |
| `tests/test_s13_6_t4_fit_warning_typed.py` (NEW) | ~270 | — | +270 |
| `scripts/s13_6_t4_repin.py` (NEW) | ~90 | — | +90 |
| **Total** | **~550** | **~70** | **+480** |

(Approximate; exact diff produced by `git diff --stat` post-stage.)

## Test counts

| | Before | After | Delta |
|---|---:|---:|---:|
| `tests/test_s13_6_t4_fit_warning_typed.py` (NEW) | — | 9 | +9 |
| `tests/test_ranking_strategy_positive_control.py` | 16 | 16 | 0 (re-typed) |
| `tests/test_s13_t2_predicted_segment_population.py` | 13 | 13 | 0 (re-typed) |
| `tests/test_s13_renderer_non_consumption.py` | parametric | parametric +3 string-grammar patterns × 3 modules = +9 | +9 |
| `tests/test_s13_ml_fit_never_demotes.py` (Q-S13-4 LOCK runtime) | 6 | 6 | 0 (still green) |
| `tests/test_reason_code_precedence_invariant.py` (AST LOCK pin) | 4 | 4 | 0 (still green) |

Wide non-harness run: **595 passed, 7 skipped, 1 unrelated pre-existing
failure** (`tests/test_phase5_considered_always.py::test_abstain_soft_briefing_renders_populated_considered_section`
— asserts `"Would fire"` in HTML; `would_fire_if` was stripped at S13.6-T1a;
confirmed pre-existing on `git stash` revert; **not** caused by T4).
Wall clock: 461s.

## Inventory results

### Producer sites (rewired)

Single producer of the LEGACY string grammar in `src/`:

- `src/predictive/ranking_strategy.py::rank_audience` — 5 append sites,
  all rewired from `f"{LEVEL}:{substrate_name}"` to
  `FitWarning(level=FitWarningLevel.X, substrate=substrate_name)`.
- `src/predictive/consumer_wiring.py::populate_play_card_consumers` —
  copies `result.fit_warnings` via `list(...)`; no string construction.
  Docstring updated to reflect typed shape; no behavior change.

The string-prefix tokens (`MODEL_FIT_INSUFFICIENT_DATA`,
`MODEL_FIT_REFUSED`) also appear in `src/engine_run.py` (the `ReasonCode`
enum values — distinct from `FitWarningLevel`; surfaced via
`RejectedPlay.reason_code` only) and in `src/predictive/cf.py` /
`survival.py` / `bgnbd.py` / `gamma_gamma.py` / `rfm.py` / `retention.py`
as SUBSTRATE-LEVEL `card.fit_warnings` debug strings (e.g.
`"chained_bgnbd_refusal"`, `"holdout_recall_below_floor"`, etc.). Those
live on `ModelCard.fit_warnings` (per-substrate `List[str]` audit), NOT
on `ModelCardRef.fit_warnings` (the grammar-bound surface). Per DS scope
(T4 retypes `ModelCardRef.fit_warnings` only — substrate-internal
`ModelCard.fit_warnings` is out of scope), these are not touched. Surfaced
here explicitly so DS can confirm the partition.

### Consumer sites in tests (rewired)

- `tests/test_ranking_strategy_positive_control.py` — 9 string-literal
  assertions rewritten as `FitWarning(level, substrate)` constructions
  via a `_fw` helper + level aliases (`_INSUF`, `_REFUSED`, `_PROV`).
- `tests/test_s13_t2_predicted_segment_population.py` — 2 typed-grammar
  assertion blocks rewritten (`"PROVISIONAL_SELECTED:rfm" in ...` →
  `FitWarning(...) in ...`) plus 2 `any(...)` walks switched to read
  `.level` + `.substrate`.

### Other consumer sites found

- `tests/test_s13_t3_small_sm_golden_e2e.py:163` reads
  `mcr.get("fit_warnings")` only for a `pytest.skip` honest-report
  payload (no assertion on shape). Will receive `List[Dict]` post-T4;
  prints fine.
- AST-aware `tests/test_reason_code_precedence_invariant.py` enforces
  `RejectedPlay.reason_code` ≠ `ReasonCode.MODEL_FIT_*` at the **AST**
  level; the test is shape-agnostic w.r.t. the `fit_warnings` typing
  change and remains green untouched.
- No renderer (`src/briefing.py`, `src/storytelling_v2.py`,
  `src/debug_renderer.py`) reads `fit_warnings`. Confirmed via grep
  (zero hits in those 3 modules). Operator-only audit per STATE.md §4.

## Q-S13-4 LOCK preservation confirmation

- `tests/test_s13_ml_fit_never_demotes.py` — **6 passed** (5 parametric
  fixtures + month-2 sequence pin). 58s wall clock.
- `tests/test_reason_code_precedence_invariant.py` — **4 passed**
  (AST-aware sweep finds zero `RejectedPlay(reason_code=ReasonCode.MODEL_FIT_*)`
  assignments in `src/`).

ML-fit warnings emit ONLY on `PlayCard.model_card_ref.fit_warnings`
(now typed); NEVER on `RejectedPlay.reason_code`. The structural typing
change does not weaken the invariant — it strengthens it: the typed
`FitWarning` cannot accidentally coerce into a `ReasonCode` enum.

## `engine_run.json` SHA

- **Before (post-T3):** carried forward from `scripts/s13_6_t3_repin.py`.
  Per IM-plan caveat, SHAs include wall-clock `fit_timestamp` debris from
  S10-S12 ModelCards; the load-bearing gate is the structural test, not
  the ledger.
- **After (post-T4):** re-pinned via NEW `scripts/s13_6_t4_repin.py`
  (5-fixture sweep, modeled on `s13_6_t3_repin.py`).
- **JSON shape diff:**
  - Before: `"fit_warnings": ["PROVISIONAL_SELECTED:cf", ...]`
  - After: `"fit_warnings": [{"level": "PROVISIONAL_SELECTED", "substrate": "cf"}, ...]`

The SHA on every recommendation card carrying a populated
`model_card_ref.fit_warnings` WILL move; cards with empty
`fit_warnings` are byte-identical to post-T3 for that block.

`briefing.html`: NOT pinned (canary retired at T1a). Confirmed
operator-only audit field — renderers do not consume `fit_warnings`.

## Deserialization policy chosen

**Option (a) — strict cutover** per T3 precedent (DS Q12).

Rationale (preserved from ticket brief): `fit_warnings` is an
operator-only audit field per STATE.md §4. Pre-T4 `List[str]`
`"{LEVEL}:{substrate}"` snapshots deserialize to an **empty list** —
no rehydration needed. Lossy migration (option b) would require
colon-parsing legacy strings into `FitWarning` instances at deserialize
time; the added surface area is not justified given operator-only
consumption.

Implementation: `_from_dict_fit_warning` accepts the post-T4 dict
shape (`{"level": ..., "substrate": ...}`) only. Non-dict entries
return `None` and are filtered out of the `_from_dict_model_card_ref`
list-builder, so legacy strings degrade gracefully to `fit_warnings=[]`.

Defensive extension: `_from_dict_fit_warning` also accepts
already-typed `FitWarningLevel` enum instances on the `level` key
(observed when callers route through bare `dataclasses.asdict`, which
does NOT unwrap nested Enums — the canonical `EngineRun.to_dict` /
`_to_jsonable` path does unwrap). This is back-compat for the
existing T2 `test_predicted_segment_roundtrip` test which uses
`asdict` rather than `to_dict`.

## Carry-forward T5 CHANGELOG note

> Pre-T4 `engine_run.json` snapshots:
> `model_card_ref.fit_warnings` deserializes to an empty list (strict
> cutover per T3 precedent — operator-only audit field; no
> rehydration needed).
>
> Post-T4 shape: each entry is
> `{"level": "<FitWarningLevel value>", "substrate": "<name>"}`.

## Confirmations

- **`FitWarningLevel`** is a `(str, Enum)` with EXACTLY 3 members:
  `PROVISIONAL_SELECTED`, `MODEL_FIT_INSUFFICIENT_DATA`,
  `MODEL_FIT_REFUSED`. Closed set. Pinned by
  `test_fit_warning_level_is_str_enum_with_exactly_three_members`.
- **`FitWarning`** is a `@dataclass` with `level: FitWarningLevel` and
  `substrate: str`. Pinned by
  `test_fit_warning_is_dataclass_with_level_and_substrate`.
- **`ModelCardRef.fit_warnings`** annotation is `List[FitWarning]`.
  Pinned by
  `test_model_card_ref_fit_warnings_typed_to_list_of_fit_warning` via
  `typing.get_type_hints` + `typing.get_origin` / `get_args`.
- **Re-export:** `FitWarning` and `FitWarningLevel` both in
  `src/engine_run.__all__`. Pinned by
  `test_fit_warning_and_level_reexported_from_engine_run`.
- **No T1a / T1b / T2 / T3 re-touch.** Diff confined to (a) typed-grammar
  insertion in `engine_run.py`, (b) producer rewire in
  `ranking_strategy.py`, (c) doc-only update in `consumer_wiring.py`,
  (d) two test re-typings, (e) NEW T4 test + repin script + extended
  renderer non-consumption grep pin.
- **No T5+ scope touched:** `schema_version` not bumped;
  `mechanism` not touched; RULE A `null_reason` not introduced; T7.5
  registry not touched; sprint-close not run.

## Risks encountered + mitigations

1. **Circular import risk.** `ranking_strategy.py` now imports
   `FitWarning` / `FitWarningLevel` from `src.engine_run`.
   `engine_run.py` itself imports from `src.predictive.model_card`
   (not `ranking_strategy`); `model_card` imports only stdlib +
   yaml. No cycle. **Mitigation:** verified via direct interpreter
   exec (`python -c "from src.predictive.ranking_strategy import rank_audience"`).
2. **`asdict` vs `to_dict` enum-unwrap divergence.** Bare
   `dataclasses.asdict` does not coerce nested `Enum` values to
   their string `.value`, so a round-trip through `asdict(mcr)` →
   `_from_dict_model_card_ref` would have failed with a strict
   `FitWarningLevel(<enum>)` parse. **Mitigation:**
   `_from_dict_fit_warning` accepts already-typed `FitWarningLevel`
   on the `level` key in addition to string values. Caught by
   the existing `test_predicted_segment_roundtrip` test on first
   run; fixed before final test sweep.
3. **Pre-existing unrelated test failure.** `test_phase5_considered_always.py::test_abstain_soft_briefing_renders_populated_considered_section`
   fails on the `assert "Would fire" in html` check. Confirmed by
   `git stash` revert that this is pre-existing (post-T1a strip of
   `would_fire_if`) and **not** caused by T4. Surfaced here so DS /
   orchestrator can decide whether to file a separate fix ticket.

## Deviation check

Deviation check: none.

---

Brief return message to orchestrator follows in the chat reply.
