# Code Refactor Engineer — Phase 6A Ticket A2 Summary

_Date: 2026-05-04_
_Branch: `engine-rework`_
_Baseline commit: `375506e` (post-A1)_
_Scope: Phase 6A Ticket A2 ONLY from `agent_outputs/implementation-manager-campaign-slate-plan.md`._

## Approved Scope

Add an enum-backed `would_be_measured_by` field to `PlayCard` as a purely additive schema-only change. Field exists, defaults to `None`, optional, round-trips cleanly through `EngineRun.to_dict()` / `EngineRun.from_dict()`. NO producer in the engine populates the field in this ticket. NO renderer reads the field. NO Recommended Experiment behavior, no priors metadata, no decide-layer eligibility filter, no role-uniqueness assertion, no ABSTAIN_SOFT extension, no forbidden-token sweep extension, no goldens re-baselined.

## Patch Summary

1. **`src/engine_run.py`** — added a new `class WouldBeMeasuredBy(str, Enum)` with exactly three members locked by the contract (`INCREMENTAL_ORDERS_IN_14D`, `EMAIL_ATTRIBUTED_REVENUE_IN_7D`, `REPEAT_PURCHASE_IN_30D`). Added `would_be_measured_by: Optional[WouldBeMeasuredBy] = None` to `PlayCard`. Extended `_from_dict_play_card` to coerce the new field via the existing `_coerce_enum` helper (single-line addition; reuses the same coercion path used by `evidence_class`, `reason_code`, `data_quality_flags`, etc.).

2. **`tests/test_engine_run_schema.py`** — added `WouldBeMeasuredBy` to the existing import block; added three new tests at the end of the file pinning default-`None` round-trip, per-member parametrized round-trip, and the locked enum-string set. The pre-existing `test_round_trip_fully_populated_run` was NOT modified — it stays a valid baseline that exercises the schema with the field at its default.

3. **`tests/test_would_be_measured_by_enum.py`** (NEW) — 14 tests covering the enum surface, the additive PlayCard field default, and the serialization round-trip on every member.

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py`
  - Added `class WouldBeMeasuredBy(str, Enum)` after `class RevenueRangeSource` (line ~129).
  - Added `would_be_measured_by: Optional[WouldBeMeasuredBy] = None` field on `PlayCard` between `opportunity_context` and `klaviyo_brief_inputs` (line ~322).
  - Added `would_be_measured_by=_coerce_enum(WouldBeMeasuredBy, d.get("would_be_measured_by"))` line in `_from_dict_play_card` (line ~570). Reuses the existing `_coerce_enum` helper which raises `ValueError` for unrecognized strings and returns `None` for `None` payloads.

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_engine_run_schema.py`
  - Added `WouldBeMeasuredBy` to the imports block.
  - Added three new tests at the end of the file: `test_play_card_would_be_measured_by_defaults_to_none_in_round_trip`, `test_play_card_would_be_measured_by_round_trips_each_member` (parametrized over all 3 members), `test_would_be_measured_by_enum_values_are_uppercase_snake`.

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_would_be_measured_by_enum.py` (NEW)
  - 14 tests across 3 sections:
    - **Enum surface (4):** `test_would_be_measured_by_has_exactly_three_members`, `test_would_be_measured_by_string_values_match_names`, `test_would_be_measured_by_invalid_value_rejected` (3 cases: lowercase, unknown member, empty string), `test_would_be_measured_by_is_str_enum`.
    - **PlayCard default (3):** `test_play_card_would_be_measured_by_defaults_to_none`, `test_play_card_constructor_accepts_optional_field`, `test_play_card_constructor_accepts_each_enum_value`.
    - **Round-trip (7):** `test_default_play_card_omits_or_nulls_field_in_to_dict`, `test_play_card_with_none_round_trips`, `test_play_card_round_trip_for_each_enum_member` (parametrized x 3 = 3 test cases), `test_omitted_field_round_trips`, `test_invalid_serialized_value_raises_on_from_dict`.

No other files modified. No `src/decide.py`, no `src/storytelling_v2.py`, no `src/storytelling.py`, no `priors.yaml`, no `priors_loader.py`, no `main.py`, no `utils.py`, no goldens, no fixtures.

## Schema Serialization Layer

- **Schema layer:** plain Python `@dataclass`es from `dataclasses`; enums are `str`-mixin `Enum` subclasses.
- **Serialization helper:** `_to_jsonable(obj)` in `src/engine_run.py` — recursively walks dataclasses, lists, dicts, and unwraps enums via `Enum.value`. Handles `Optional[Enum]` automatically because `_to_jsonable(None)` returns `None` and `_to_jsonable(<Enum>)` returns the enum's string value. **No new code path needed for the `to_dict` direction.** Verified by `test_default_play_card_omits_or_nulls_field_in_to_dict`.
- **Deserialization helper:** `_coerce_enum(enum_cls, value)` in `src/engine_run.py` — returns `None` for `None`, idempotent for already-coerced enums, calls `enum_cls(value)` otherwise. Free-text strings raise `ValueError` from the enum constructor itself. The `_from_dict_play_card` function calls `_coerce_enum(WouldBeMeasuredBy, d.get("would_be_measured_by"))` — single line, mirrors how `evidence_class` is coerced. Missing keys round-trip to `None` because `dict.get` returns `None` by default; verified by `test_omitted_field_round_trips`.

## Exact Commands Run

```bash
# Red-first (BEFORE the schema change landed)
python -m pytest tests/test_would_be_measured_by_enum.py -v
# -> ImportError: cannot import name 'WouldBeMeasuredBy' from 'src.engine_run'

# Green (AFTER the schema change landed)
python -m pytest tests/test_would_be_measured_by_enum.py -v
# -> 14 passed in 0.02s

python -m pytest tests/test_engine_run_schema.py -v
# -> 12 passed in 0.02s (was 7 before A2; +5 new cases including parametrized members)

python -m pytest tests/test_golden_diff.py -v
# -> 3 passed (NO re-baseline)

# A1 territory regression sweep
python -m pytest tests/test_render_v2.py tests/test_decide.py \
                 tests/test_watching_load_bearing_priority.py \
                 tests/test_phase5_watching_signals.py
# -> 73 passed (renderer + builder watching behavior unchanged)

# Full suite
python -m pytest tests/ -q
# -> 712 passed, 14 skipped, 0 failed in 115.40s
```

`tests/test_phase5_3_watching.py` does NOT exist (also noted in the A1 summary); the equivalent file is `tests/test_phase5_watching_signals.py`, which was run above and passes 9/9.

## Tests / Checks Run

| Check | Result | Notes |
|---|---|---|
| `tests/test_would_be_measured_by_enum.py` (NEW) | **14 passed** | Red-first ImportError captured before schema landed |
| `tests/test_engine_run_schema.py` | **12 passed** | Was 7 pre-A2; +5 new (1 default + 3 parametrized + 1 invariant) |
| `tests/test_golden_diff.py` | **3 passed (no re-baseline)** | M0 byte-identical |
| `tests/test_render_v2.py` | 25 passed | A1 watching cap unchanged |
| `tests/test_decide.py` | 34 passed | A1 builder unchanged |
| `tests/test_watching_load_bearing_priority.py` | 5 passed | A1 contract intact |
| `tests/test_phase5_watching_signals.py` | 9 passed | Phase 5.3 contract intact |
| Full suite `pytest tests/ -q` | **712 passed, 14 skipped, 0 failed** | Pre-A2 baseline 693 passed; +19 = 14 new file + 5 schema additions |

## Did The New Tests FAIL Before The Fix?

**Yes — red-first evidence captured.**

Before any change to `src/engine_run.py`, `python -m pytest tests/test_would_be_measured_by_enum.py -v` produced:

```
ImportError: cannot import name 'WouldBeMeasuredBy' from 'src.engine_run'
```

The schema change landed second. After the enum + field were added, all 14 new tests passed on first run. The 5 new schema-test cases (in the existing `test_engine_run_schema.py`) likewise relied on the same imports and would have failed identically had the schema change been delayed.

## Goldens

- `tests/test_golden_diff.py` -> **3 passed, 0 re-baselined**.
- M0 legacy goldens (`tests/golden/{small_sm, mid_shopify, micro_coldstart}/*`): byte-identical.
- This is the expected outcome because (a) no producer in the engine populates `would_be_measured_by` in Ticket A2, (b) no renderer reads the field, and (c) the legacy adapter `legacy_actions_from_engine_run()` does not project the new field into legacy outputs. The field surfaces only in V2 receipts (where it serializes as `"would_be_measured_by": null`), and V2 receipts are not pinned as goldens.

## Confirmation A1 Behavior Is Intact

A2 did NOT touch any A1 territory:

- `src/storytelling_v2.py` not modified.
- `src/decide.py` not modified.
- `_LOAD_BEARING_WATCH_METRICS` unchanged (still includes `aov`).
- `MAX_WATCHING_RENDERED = 4` unchanged.
- Empty-HELD MOVED-load-bearing fallback in `build_watching` unchanged.

A1 contracts cited and verified passing post-A2:

- `tests/test_watching_load_bearing_priority.py` — 5/5 passed (cap=4, load-bearing prioritization, Phase 5.3 compatibility, small_store_240d e2e load-bearing-row presence).
- `tests/test_render_v2.py::test_watching_section_caps_at_four` and `test_watching_section_caps_at_four_with_seven_signals_phase6a` — both passed.
- `tests/test_phase5_watching_signals.py` — 9/9 passed (Phase 5.3 stable-watching, flat-load-bearing surfacing, non-load-bearing exclusion).
- `tests/test_decide.py` — 34/34 passed including the narrowed-to-`ctr` MOVED-exclusion and zero-change tests.

## Behavior Changes

None at the engine level. This is a purely additive schema-only ticket.

- Every `PlayCard` constructed by every existing producer continues to default `would_be_measured_by` to `None`.
- Every `EngineRun.to_dict()` payload now contains a `would_be_measured_by: null` key inside each `recommendations[*]` entry. This is forward-compatible with any consumer that ignores unknown keys; it does NOT appear in legacy adapter output.
- `EngineRun.from_dict()` accepts payloads that omit the key entirely (round-trips to `None`) and payloads that include the key with `null` (also `None`). It rejects payloads with a free-text string for the field via the standard `ValueError` from `_coerce_enum`.

The merchant-facing briefing.html is unchanged on every fixture because no renderer reads the field.

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_would_be_measured_by_enum.py` — 14 tests pinning the enum surface, the field default, and the round-trip for every enum member plus the omitted-field and invalid-value cases.

No new sample HTML / receipts / docs / fixtures were added. No goldens modified.

## Remaining Risks

1. **No producer populates the field yet.** This is intentional per A2's scope, but it means a downstream V2 consumer that already reads receipts will see `would_be_measured_by: null` on every PlayCard. Any consumer that treats the presence of the key as a signal must wait for Ticket B-series wiring.

2. **Legacy adapter does not stamp the field.** The legacy adapter (`src.adapters.engine_run.legacy_actions_from_engine_run`) does not project `would_be_measured_by` into legacy `actions_log.json` output. Cross-checked: legacy adapter does not write per-card extra metadata beyond what M0 froze. Documented in the implementation plan's risk #6. No action required for A2.

3. **UPPER_SNAKE_CASE deviates from prior enum convention.** `EvidenceClass`, `DecisionState`, `ReasonCode`, `DataQualityFlag`, `ObservationClassification`, and `RevenueRangeSource` all use lowercase string values. `WouldBeMeasuredBy` uses UPPER_SNAKE_CASE because the contract-final spec locks that casing for these outcome metric names (they will be referenced by the same string in priors-metadata YAML in Ticket A3 and in `recommended_history.json` later). The convention split is now pinned by `test_would_be_measured_by_string_values_match_names` and `test_would_be_measured_by_enum_values_are_uppercase_snake`. A future agent who tries to "normalize" the casing must update both the YAML and the history schema in lockstep.

4. **`evidence_class` invariant not yet enforced in code.** The contract states cards in `recommended_experiments` MUST have `evidence_class == TARGETING` and a populated `would_be_measured_by`. A2 is schema-only and does NOT enforce this. The constraint will be enforced in Ticket A4 (decide-layer experiment-eligibility filter) and in Ticket B4 (role-uniqueness invariant). For now, a stray producer COULD set `would_be_measured_by` on a measured card without raising. This is acceptable for A2 because no producer sets the field at all.

5. **Round-trip key insertion order is preserved by Python's `dict`.** `_to_jsonable` walks `asdict(obj)` which preserves dataclass field declaration order, so `would_be_measured_by` consistently appears between `opportunity_context` and `klaviyo_brief_inputs` in serialized output. If a future ticket re-orders the dataclass fields, golden snapshot tests on V2 JSON receipts (none today, but pinned in B6) would diff. Not a current risk.

## Readiness for Phase 6A Ticket B-series

**Ready.** A2 establishes the schema seam that B-series Recommended Experiment producer/renderer work depends on:

- `WouldBeMeasuredBy` enum is locked and importable from `src.engine_run`.
- `PlayCard.would_be_measured_by` is in place, defaulting to `None`, round-trips cleanly.
- The standard `_coerce_enum` helper handles both directions of serialization; no new helper to learn.
- The free-text-rejection contract is pinned at the schema layer, so any future producer that tries to populate the field with a free-text string will fail at `from_dict` time (the contract-final spec's hard rule "No `would_be_measured_by` rendered as free-text on Recommended Experiment; must be enum-backed or omit the field" is now mechanically enforceable upstream of any renderer).

Per the implementation plan, the next ticket in execution order is A3 (priors metadata schema + loader). However, the prompt I received explicitly named "B-series — Recommended Experiment producer/renderer" as the follow-up. Both A3 and the B-series can begin now without further A2 work.

Suggested ordering for the next agent:
1. **A3** (priors metadata: `audience_floor`, `mechanism`, `vertical_applicability`, `would_be_measured_by` UPPER_SNAKE_CASE strings, `audience_archetype`) — config + loader only, no behavior change.
2. **A4** (decide-layer eligibility filter + new `EngineRun.recommended_experiments` field).
3. **B1** (renderer for the new section).
4. **B2-B6** as planned.

No follow-up cleanup or re-review is required before the next ticket begins.

## Git Status

Per convention, changes are NOT committed. Files left unstaged for review:

- 1 modified `src/` file: `engine_run.py`.
- 1 modified test file: `test_engine_run_schema.py`.
- 1 new test file: `test_would_be_measured_by_enum.py`.
- 1 new doc file: this summary.
- No goldens modified.
- No legacy `src/storytelling.py` modified.
- No A1 files (`src/decide.py`, `src/storytelling_v2.py`, watching tests) modified.
