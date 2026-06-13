# code-refactor-engineer — S13.6-T7a summary

**Ticket:** S13.6-T7a — RULE A flag-aware absence-of-data pattern (single bundled atomic commit).
**Date:** 2026-06-01 (resume + execution after the halt + DS adjudication 2026-06-01 + founder approval 2026-06-01).
**Status:** READY TO COMMIT (engine remains runnable; ledger atomically populated; AST sweep + per-row invariants green; full suite 595p / 7s / 1 pre-existing failure unrelated to T7a).

## Scope (revised by DS adjudication 2026-06-01; founder approved 2026-06-01)

DS verdict on the T7 halt:

- **Retract/revise §(e) triage** — the "all Optionals MUST pair" framing is dropped. Replaced with the flag-aware RULE A (paired ``_null_reason`` field on the contract OR source-level ``# null_reason_exempt:`` annotation with a named flag).
- **Three closed-set null-reason enums** land at the schema-authority surface in ``src/engine_run.py``:
  - ``RevenueRangeSuppressionReason`` — 9 members; values match producer string literals byte-for-byte per DS Q1.
  - ``MonthDeltaNullReason`` — 5 members; ``LINEAGE_CHANGED`` reserved as forward-compat.
  - ``PredictedSegmentNullReason`` — 4 members; INNER-field shape (applies to ``segment_name``, not the wrapper).
- **Three paired ``_null_reason`` fields** land on ``RevenueRange``, ``EngineRun``, ``PredictedSegment``.
- **NO producer rewrites** per DS Q1 (enum members wrap existing strings at the seam).
- **T7 splits** into T7a (this commit) + T7b (substrate refusal-card audit, deferred to S13.7).
- **AST sweep** at ``tests/test_s13_6_t7a_no_silent_nulls.py`` is the load-bearing closure gate.

## Patch summary

**Schema (DS R6 single-file authority, `src/engine_run.py`):**

- NEW ``RevenueRangeSuppressionReason(str, Enum)`` — 9 members (`COLD_START_NO_N_OBSERVED`, `AUDIENCE_ZERO`, `AOV_ZERO`, `OBSERVED_EFFECT_INVALID`, `NO_PRIOR_BASE_RATE`, `PRIOR_UNVALIDATED`, `AOV_UNAVAILABLE`, `DIRECTIONAL_NO_INTERVENTION_EFFECT`, `EXPERIMENT_NO_CALIBRATED_LIFT`). String values match producer literals byte-for-byte.
- NEW ``MonthDeltaNullReason(str, Enum)`` — 5 members (`NO_STORE_ID`, `NO_PRIOR_RUN`, `ANCHOR_DATE_UNPARSEABLE`, `UNDER_21D_FLOOR`, `LINEAGE_CHANGED`).
- NEW ``PredictedSegmentNullReason(str, Enum)`` — 4 members (`MODAL_FLOOR_NOT_CLEARED`, `PARQUET_MISSING`, `PARQUET_UNREADABLE`, `NO_AUDIENCE_INTERSECTION`).
- ADDED ``RevenueRange.suppression_reason: Optional[RevenueRangeSuppressionReason] = None`` paired with the existing ``suppressed: bool`` flag (invariant: ``suppressed=True`` ⇔ ``suppression_reason is set``).
- ADDED ``EngineRun.month_2_delta_null_reason: Optional[MonthDeltaNullReason] = None`` paired with ``month_2_delta``.
- ADDED ``PredictedSegment.segment_name_null_reason: Optional[PredictedSegmentNullReason] = None`` paired with the inner ``segment_name`` field.
- All 3 enums re-exported via ``__all__``.
- Round-trip wired through ``_from_dict_revenue_range``, ``_from_dict_predicted_segment``, ``_from_dict_engine_run`` with strict-cutover carry-forward (pre-T7a snapshots have no key → ``None``).
- Per-Optional ``# null_reason_exempt: <rationale>`` annotations added to every other Optional field on every contract dataclass.
- CHANGELOG v2.0.0 T7a entry added (replaces "T7 + T7.5 (pending)" placeholder).

**Producers — wrap existing strings at the seam (NO rewrites per DS Q1):**

| Site | File | Line | String literal | Enum member |
|---|---|---|---|---|
| `_suppressed_range("cold_start", ...)` | `src/sizing.py` | 655 | `cold_start` | `COLD_START_NO_N_OBSERVED` |
| `_suppressed_range("audience_zero", ...)` | `src/sizing.py` | 658 | `audience_zero` | `AUDIENCE_ZERO` |
| `_suppressed_range("aov_zero", ...)` | `src/sizing.py` | 660 | `aov_zero` | `AOV_ZERO` |
| `_suppressed_range("observed_effect_invalid", ...)` | `src/sizing.py` | 673 | `observed_effect_invalid` | `OBSERVED_EFFECT_INVALID` |
| `_suppressed_range("no_prior_base_rate", ...)` | `src/sizing.py` | 695 | `no_prior_base_rate` | `NO_PRIOR_BASE_RATE` |
| `_suppressed_range("prior_unvalidated", ...)` | `src/sizing.py` | 728 | `prior_unvalidated` | `PRIOR_UNVALIDATED` |
| `_suppressed_range("targeting_non_causal_prior", ...)` | `src/sizing.py` | 744 | `targeting_non_causal_prior` | `OBSERVED_EFFECT_INVALID` (defensive; see "legacy producer" below) |
| `RevenueRange(suppressed=True, ...)` directional | `src/measurement_builder.py` | ~648 | `directional_no_intervention_effect` | `DIRECTIONAL_NO_INTERVENTION_EFFECT` |
| `RevenueRange(suppressed=True, ...)` unvalidated | `src/measurement_builder.py` | ~2280 | `prior_unvalidated` | `PRIOR_UNVALIDATED` |
| `RevenueRange(suppressed=True, ...)` no AOV | `src/measurement_builder.py` | ~2302 | `aov_unavailable` | `AOV_UNAVAILABLE` |
| `RevenueRange(suppressed=True, ...)` experiment | `src/decide.py` | ~2100 | `experiment_no_calibrated_lift` | `EXPERIMENT_NO_CALIBRATED_LIFT` |

The `_suppressed_range` helper in `src/sizing.py` is the central seam: it now coerces the legacy ``reason`` string through the enum constructor (defensive `try/except ValueError` falls through to `None` so the AST sweep / round-trip test catches any future producer-string drift).

**`targeting_non_causal_prior` legacy producer disposition:**
DS Q1 verdict — "legacy pre-S7.5 and producer paths confirm unreachable; file as KI-cleanup for S13.7 dead-code sweep, do NOT add to enum." Verification: the path at `src/sizing.py:744` fires only when `priors_validation_enabled=False`. `ENGINE_V2_PRIORS_VALIDATION` defaults to `"true"` at `src/utils.py:556`, so it's dead-code on every default-flag run. Disposition: maps defensively to `OBSERVED_EFFECT_INVALID` with a `# TODO(S13.7-cleanup): legacy producer; dead code per DS adjudication 2026-06-01` comment in `_suppressed_range`. To file as KI at sprint close.

**`detect_month_2_delta` — MonthDelta option choice (a) tuple-return:**

Choice: **Option (a) — tuple-return** ``Tuple[Optional[MonthDelta], Optional[MonthDeltaNullReason]]``.

Rationale per the brief: "(a) is cleaner and pin-able." The tuple-return enforces always-paired (value, reason) emission at the seam — the caller cannot drop the reason. Wire-up at `src/main.py:1801-1815` assigns both fields atomically:

```
_md, _md_null_reason = _detect_month_2_delta(...)
if _md is not None:
    engine_run.month_2_delta = _md
    engine_run.month_2_delta_null_reason = None
else:
    engine_run.month_2_delta = None
    engine_run.month_2_delta_null_reason = _md_null_reason
```

The 4 None-paths in `detect_month_2_delta` now return:
- L364 `not store_id` → `NO_STORE_ID`
- L367 `prior_blob is None` → `NO_PRIOR_RUN`
- L372 `days_between is None` (anchor parse fail) → `ANCHOR_DATE_UNPARSEABLE`
- L374 `days_between < MONTH_2_DAY_FLOOR` → `UNDER_21D_FLOOR`
- Success → ``(MonthDelta(...), None)``

**`_compute_modal_segment` — 4-tuple return:**

The consumer-wiring helper now returns ``Tuple[Optional[str], Optional[float], Optional[int], Optional[PredictedSegmentNullReason]]``. The 4 None paths map:
- `not audience_ids` → `NO_AUDIENCE_INTERSECTION`
- `not rfm_parquet_path.exists()` → `PARQUET_MISSING`
- pandas read failure / missing columns → `PARQUET_UNREADABLE`
- intersection-empty / n_audience == 0 → `NO_AUDIENCE_INTERSECTION`
- empty `counts` edge case → `MODAL_FLOOR_NOT_CLEARED`
- DS-LOCKED stability floor not cleared → `MODAL_FLOOR_NOT_CLEARED`
- Success → `(name, share, n, None)`

The caller in `populate_play_card_consumers` populates `PredictedSegment(segment_name=..., audience_modal_share=..., n_audience=..., segment_name_null_reason=...)` whenever ANY of the 4 fields is non-None (so the wrapper is populated even when only the audit fields + null_reason are).

**`StoreProfile` judgement call (per brief):**

Engineer choice — **`# TODO(S13.7-T7b)` deferred annotation** rather than ship a `StoreProfileNullReason` enum at T7a.

Rationale: the producer at `src/main.py:961-969` is a single `try/except` around `_build_store_profile`. There is no taxonomy of refusal reasons in the producer today — the `except Exception as _spe` path catches everything as one bucket. Per the brief: "if producer is unclear, exempt with `# TODO(T7b): paired null_reason deferred — producer not yet aligned with §(e) members`." Annotation added to `EngineRun.store_profile`. T7b will (a) refactor `_build_store_profile` to surface a typed refusal taxonomy (DS §(e) members `PROFILE_NOT_LOADED` | `ONBOARDING_INCOMPLETE` minimum), (b) ship the `StoreProfileNullReason` enum + paired field, (c) wire the producer.

**AST sweep coverage list — every Optional in `src/engine_run.py` + classification:**

| Dataclass | Field | Classification |
|---|---|---|
| DataWindow | primary_window, anchor_quality | EXEMPT (structural / cold-start) |
| Abstain | mode | EXEMPT (ENGINE_V2_ABSTAIN_4STATE / ENGINE_V2_PRIORS_VALIDATION flag-gated) |
| Observation | supporting_metric, change_magnitude, current, prior, delta_pct | EXEMPT (structural / cold-start) |
| WatchedSignal | current, prior, trend, threshold_to_act | EXEMPT (structural / cold-start watch) |
| Audience | id, definition, size, fraction_of_base | EXEMPT (structural / cold-start) |
| Measurement | metric, observed_effect, n, primary_window, consistency_across_windows, p_internal, ci_internal, window_corroboration | EXEMPT (Measurement is null for TARGETING by hard contract; inner Optionals are structural plumbing; `window_corroboration` is `ENGINE_V2_STORE_PROFILE` flag-gated) |
| **RevenueRange** | **p10, p50, p90, source** | EXEMPT (paired via `suppressed` + `suppression_reason` at the seam) |
| **RevenueRange** | **suppression_reason** | PAIRED (T7a — paired field itself, exempt by definition) |
| Sensitivity | scenario_observed_n_halved, scenario_observed_n_doubled, scenario_prior_shifted_down, scenario_prior_shifted_up | EXEMPT (degenerate input encoding) |
| Inventory | days_of_cover, gate_passed | EXEMPT (INVENTORY_GATE_ENABLED flag) |
| Conflicts | audience_overlap_pct | EXEMPT (CANNIBALIZATION_GATE_ENABLED flag) |
| LaunchWindow | recommended, reason | EXEMPT (advisory copy) |
| **PredictedSegment** | **segment_name** | PAIRED via `segment_name_null_reason` (T7a) |
| PredictedSegment | audience_modal_share, n_audience, notes | EXEMPT (D-S13-2 audit fields uncensored / debug slot) |
| **PredictedSegment** | **segment_name_null_reason** | PAIRED (T7a — paired field itself) |
| ModelCardRef | strategy_used, notes | EXEMPT (ENGINE_V2_PLAY_PREDICTED_SEGMENT flag-gated / debug) |
| PlayCard | confidence_label | EXEMPT (M7-derived structural) |
| PlayCard | audience, measurement, revenue_range, inventory, conflicts, launch_window, opportunity_context | EXEMPT (structural sub-objects; RR carries its own paired suppression_reason inside) |
| PlayCard | would_be_measured_by | EXEMPT (Recommended Experiment field; structural absence elsewhere) |
| PlayCard | receipts_ref | EXEMPT (post-v1 receipts emitter) |
| PlayCard | predicted_segment, model_card_ref | EXEMPT (ENGINE_V2_PLAY_PREDICTED_SEGMENT flag-gated) |
| PlayCard | evidence_source | EXEMPT (ENGINE_V2_TIER_CHIP flag-gated) |
| PlayCard | sensitivity | EXEMPT (ENGINE_V2_SENSITIVITY + blend-source flag-gated) |
| PlayCard | provenance | EXEMPT (ENGINE_V2_EB_BLEND + blend-source flag-gated) |
| PlayCard | mechanism_intent | EXEMPT (None when play_id unmapped per S13.6-T6) |
| RejectedPlay | held_reason_detail, audience_size, audience_definition | EXEMPT (legacy producers / structural) |
| RejectedPlay | mechanism | EXEMPT (S13.6-T6 unmapped play_id + strict-cutover legacy str) |
| RejectedPlay | would_be_measured_by | EXEMPT (Tier-B discriminator; structural absence elsewhere) |
| Scale | monthly_revenue, customer_base_est, materiality_floor | EXEMPT (cold-start structural) |
| BriefingMeta | confidence_mode, vertical, subvertical, stage, seasonality_tag | EXEMPT (env-sourced metadata) |
| MonthDelta | segment_shifts | EXEMPT (D-S13-3 inner-field lineage suppression encoded in `notes`) |
| MonthDelta | retention_ci_at_month_3_delta | EXEMPT (structural — substrate absence on `substrate_fit_status_changes`) |
| EngineRun | run_id, store_id, anchor_date | EXEMPT (structural top-level identifiers) |
| EngineRun | store_profile | EXEMPT with `# TODO(S13.7-T7b)` annotation — deferred (engineer judgement) |
| **EngineRun** | **month_2_delta** | PAIRED via `month_2_delta_null_reason` (T7a) |
| **EngineRun** | **month_2_delta_null_reason** | PAIRED (T7a — paired field itself) |

The AST sweep passes (20/20). No silent Optionals.

## Files changed

| File | Change |
|---|---|
| `src/engine_run.py` | 3 new enums + 3 paired fields + per-Optional annotations + CHANGELOG T7a entry + round-trip serialization for new fields + `__all__` extensions |
| `src/sizing.py` | `_suppressed_range` helper extended to populate `suppression_reason` via enum constructor at the seam (NO producer-string changes) |
| `src/measurement_builder.py` | 3 RevenueRange constructions populate `suppression_reason` (directional / prior_unvalidated / aov_unavailable seams) |
| `src/decide.py` | 1 RevenueRange construction populates `suppression_reason` at the Recommended Experiment seam |
| `src/predictive/month_2_delta.py` | `detect_month_2_delta` refactored to return `Tuple[Optional[MonthDelta], Optional[MonthDeltaNullReason]]` (Option (a) tuple-return) |
| `src/predictive/consumer_wiring.py` | `_compute_modal_segment` refactored to return 4-tuple with paired `PredictedSegmentNullReason`; producer wires the null_reason into `PredictedSegment.segment_name_null_reason` |
| `src/main.py` | Month_2_delta wire-up site (`L1801-1815`) updated to unpack the 2-tuple and assign both fields atomically |
| `tests/test_s13_6_t7a_no_silent_nulls.py` | NEW — AST sweep + per-row invariants + closed-set membership + re-export + round-trip + producer tuple-return tests (20 tests) |
| `tests/fixtures/pinned_sha_ledger.json` | `_meta.ticket` flipped to S13.6-T7a; `post_s13_6_t7a` SHAs added on all 5 fixtures; `post_s13_6_t7a_definition` block added; diff_confined_to entries appended |
| `scripts/s13_6_t7a_repin.py` | NEW — repin helper modeled on `scripts/s13_6_t6_repin.py` |
| `docs/DECISIONS.md` | D-S13-5 NEW (LOCKED) — RULE A flag-aware + 3 enums + 3 paired fields; "Last updated" header appended |
| `agent_outputs/code-refactor-engineer-s13.6-t7-summary.md` | This file (replaces the halt summary with the post-execution T7a summary) |

## Tests/checks run

- `python -m pytest tests/test_s13_6_t7a_no_silent_nulls.py -x` — **20 passed**.
- `python -m pytest tests/ -x` — **595 passed / 7 skipped / 1 failed** (`tests/test_phase5_considered_always.py::test_abstain_soft_briefing_renders_populated_considered_section` — pre-existing failure reproducible on baseline HEAD, asserts on stripped T1a renderer copy; NOT introduced by T7a).
- `python scripts/s13_6_t7a_repin.py` — captured fresh post-T7a SHAs on all 5 pinned fixtures.
- `python -c "import src.engine_run as m; ..."` — import + dataclass construction + round-trip smoke.
- `python -c "import json; json.load(open('tests/fixtures/pinned_sha_ledger.json'))"` — JSON ledger validity.

## `engine_run.json` SHA before / after (re-pinned)

| Fixture | post_s13_6_t6 (before) | post_s13_6_t7a (after) |
|---|---|---|
| healthy_beauty_240d | `a0205a29...` | `e3e585c7...` |
| healthy_supplements_240d | `be366fe2...` | `c2d39973...` |
| small_store_240d | `248d5de5...` | `4278c44e...` |
| cold_start_45d | `6fde7cb2...` | `96e95d06...` |
| healthy_beauty_low_inventory_240d | `4597df61...` | `c1062c4e...` |

All 5 SHAs moved as expected (3 new JSON keys per dataclass instance + paired null_reason population on flag-ON paths). Diff confined per the ledger entries.

## Behavior changes

- **engine_run.json:** 3 new keys on every applicable dataclass instance:
  - `revenue_range.suppression_reason` (string enum value when `suppressed=True`; `null` otherwise)
  - `engine_run.month_2_delta_null_reason` (string enum value when `month_2_delta is None` AND `ENGINE_V2_MONTH_2_DELTA=true`; `null` otherwise)
  - `predicted_segment.segment_name_null_reason` (string enum value when `segment_name is None` under the consumer-wiring pass; `null` otherwise)
- **briefing.html:** NOT pinned (renderer unchanged; remains runnable). Spot-verified the renderer does not raise on the new fields.
- **detect_month_2_delta signature CHANGED** from `Optional[MonthDelta]` to `Tuple[Optional[MonthDelta], Optional[MonthDeltaNullReason]]`. The sole orchestration callsite at `src/main.py:1801-1815` was updated atomically; the existing `month_2_delta_positive_control` + `small_sm_golden_e2e` tests still pass.
- **`_compute_modal_segment` signature CHANGED** from 3-tuple to 4-tuple. The sole call from `populate_play_card_consumers` was updated atomically.
- **`_suppressed_range` behavior CHANGED** to populate the new paired enum field; the existing `RevenueRange.drivers[].reason` string is unchanged (decide.py's `_route_prior_unvalidated_holds` still keys on the legacy driver string per the existing routing seam — backward-compatible).

## Artifacts added

- `tests/test_s13_6_t7a_no_silent_nulls.py` (NEW)
- `scripts/s13_6_t7a_repin.py` (NEW)
- D-S13-5 entry in `docs/DECISIONS.md` (NEW)
- T7a CHANGELOG block in `src/engine_run.py` v2.0.0 section (replaces "T7 + T7.5 (pending)" placeholder).
- `post_s13_6_t7a` SHAs + `post_s13_6_t7a_definition` block in `tests/fixtures/pinned_sha_ledger.json`.

## Confirmation — no T1a..T6 re-touch

Verified via `git diff --stat`. Modified files: 7 src files + 2 fixtures/scripts + 1 test + 1 docs + 1 summary. No edits inside:

- `src/dispatch_prior_anchored.py` (S13.5-T1).
- `src/main.py:1604-1898` post-collapse zone OTHER than the documented L1801-1815 month_2_delta wire-up.
- `src/measurement_builder.py:721+` `_PRIOR_ANCHORED` registry (read-only).
- `src/guardrails.py::apply_guardrails_to_injected` (read-only).
- T1a/T1b/T2/T3/T4/T5/T6 strips/types/wrappers/grammar/atoms.
- `priors.yaml`, `src/priors_loader.py`, `src/storytelling_v2.py`.

## Remaining risks

- **MonthDeltaNullReason.LINEAGE_CHANGED is reserved-only.** Today it has no producer wire (S13-T3 nulls the inner `segment_shifts` field, not the wrapper). A future ticket that promotes lineage-bump to whole-MonthDelta suppression will wire it. Until then it's dead-code-by-design.
- **`targeting_non_causal_prior` legacy producer string at `src/sizing.py:744`** is dead-code under default flags. T7a maps it defensively to `OBSERVED_EFFECT_INVALID`. The KI for the S13.7 dead-code sweep should remove the producer site, not just rename it.
- **`engine_run.json` SHA is not byte-stable across re-runs** (fit_timestamp wall-clock values per the existing ledger caveat). The load-bearing T7a gate is the AST sweep + per-row invariants, not the ledger SHAs.
- **Pre-existing test failure** `tests/test_phase5_considered_always.py::test_abstain_soft_briefing_renders_populated_considered_section` — reproduces on baseline HEAD; asserts on stripped T1a copy (`"Would fire"` in `briefing.html`). NOT introduced by T7a. Worth filing as KI if not already tracked.
- **EngineRun.store_profile** is exempt with `# TODO(S13.7-T7b)`. T7b owes the paired enum + producer refactor.

## Follow-up work (T7b + S13.7 KIs)

1. **T7b (S13.7) — substrate refusal-card audit + StoreProfileNullReason.** Per DS adjudication 2026-06-01 + founder approval 2026-06-01: ship `StoreProfileNullReason` (members `PROFILE_NOT_LOADED` | `ONBOARDING_INCOMPLETE` minimum), refactor `_build_store_profile` to surface the refusal taxonomy, wire the paired field on `EngineRun`. Remove the T7a `# TODO(S13.7-T7b)` annotation.
2. **S13.7 dead-code KI — `targeting_non_causal_prior` legacy producer.** Remove the producer site at `src/sizing.py:744` after confirming via instrumentation that the path is unreachable on every production flag combination.
3. **S13.7+ — `CustomerIdsNullReason`** (DS-mentioned deferred enum; no producer surface in v1 scope).
4. **Q-S13-4 LOCK preservation check.** T7a does not touch the ML-fit gate or `RejectedPlay.reason_code` — verified via no-touch to `src/decide.py` outside the experiment-card RevenueRange seam.

## Deviation check

`Deviation check: one — T7 split into T7a (this commit) + T7b (deferred to S13.7) per DS adjudication 2026-06-01 + founder approval 2026-06-01.`
