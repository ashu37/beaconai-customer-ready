# S7.5-T1 — PriorEntry validation_status / source_artifact / effective_n fields

**Owner:** code-refactor-engineer (Sprint 7.5, ticket S7.5-T1)
**Date:** 2026-05-17
**Branch:** `post-6b-restructured-roadmap` (not pushed)
**Source contract:** [agent_outputs/implementation-manager-s7_5-priors-validation-plan.md](./implementation-manager-s7_5-priors-validation-plan.md) §2, ticket S7.5-T1 (lines 66-110)
**Design rationale:** `ARCHITECTURE_PLAN.md` Part III-1 §III-1 Step 1
**Predecessor:** S5-T3 ([code-refactor-engineer-s5-t3-summary.md](./code-refactor-engineer-s5-t3-summary.md))
**Status:** Complete. Schema unchanged (`event_version=1` frozen; additive dataclass fields with safe defaults). ZERO behavior change.

---

## 1. Approved scope

Sprint 7.5's anchor goal is to replace the unsafe `source_class →
pseudo_N` blend weight with a per-prior `validation_status` field whose
`heuristic_unvalidated` value causes `sizing.size_play` to refuse
blending (T3) and the engine to emit a typed `SOFT_PRIOR_UNVALIDATED`
abstain (T3). T1 is the entry point: pure schema/loader additions, no
behavior change, no consumer wiring.

Per plan §2 lines 66-110:

- Add closed `PriorValidationStatus` enum to `src/priors_loader.py`
  with exactly 5 values (`validated_external`, `validated_internal`,
  `elicited_expert`, `heuristic_unvalidated`, `placeholder`); export
  from `__all__`.
- Extend `PriorEntry` with three additive optional fields:
  `validation_status` (default `HEURISTIC_UNVALIDATED`),
  `source_artifact: Optional[str]`, `effective_n: Optional[int]`.
- Extend `_coerce_entry` to read the new fields from YAML. Unknown
  `validation_status` strings RAISE (closed-enum contract — orchestrator
  override of the plan's tolerant-debug-log policy; the closed-enum
  strictness is load-bearing for T3's refusal rule).
- Backwards-compat: every existing `config/priors.yaml` entry parses
  unchanged.
- ZERO behavior change. No sizing change. Beauty / supplements / M0
  fixtures byte-identical.

**Founder choice exercised:** Closed-enum strictness on
`validation_status`. The implementation-manager plan §2 line 71
described a tolerant policy ("unknown value falls back to
heuristic_unvalidated with a debug log, no raise"). The orchestrator's
ticket prompt overrode this with a strict policy ("Unknown values for
validation_status raise a clear error at load time"). The strict policy
is the correct contract: silently coercing an unknown string would
defeat the T3 refusal rule (an operator could typo `validated_externall`
and the engine would unwittingly blend on what looks like
`heuristic_unvalidated`). Tolerant coercion is preserved for
`effective_n` and `source_artifact` only.

## 2. Patch summary

### `src/priors_loader.py`

**New class `PriorValidationStatus(str, Enum)`** (lines ~70-101):
exactly 5 lowercase-string values matching the plan §1 schema-additions
table and Part III-1 §III-1 Step 1. Lowercase-string convention matches
the existing `source_class` values in `config/priors.yaml` (and
deliberately differs from the UPPER_SNAKE `WouldBeMeasuredBy` because
the field surfaces in YAML, not enum strings).

**New class `PriorsValidationError(ValueError)`** (lines ~104-112):
named exception class so callers using broad `ValueError` catches still
trip; new callers can discriminate validation-status errors from other
YAML failures (precedent: `PriorsMetadataError`, `ConfigError`).

**Extended `PriorEntry` dataclass** (frozen): three new fields appended
after `play_id` so positional construction in existing tests/call sites
keeps working:

- `validation_status: PriorValidationStatus =
  PriorValidationStatus.HEURISTIC_UNVALIDATED`
- `source_artifact: Optional[str] = None`
- `effective_n: Optional[int] = None`

All have safe defaults so every existing `PriorEntry(...)` constructor
(including the synthetic entry built by `resolve_mixed_prior`) continues
to work unchanged.

**New helpers:** `_coerce_validation_status` (closed-enum strict;
raises `PriorsValidationError` on unknown), `_coerce_effective_n`
(tolerant; non-positive / non-int → `None`), `_coerce_source_artifact`
(tolerant; whitespace-only / non-string → `None`).

**Rewired `_coerce_entry`**: the required-field coerce (`name`, `value`,
`range_p10`, `range_p90`) still happens inside a broad `(KeyError,
TypeError, ValueError)` catch that returns `None` on a malformed row
(loader's existing tolerant policy). The closed-enum coercion happens
OUTSIDE that catch so a typo on `validation_status` raises rather than
silently being swallowed as "malformed row drop".

**Extended `__all__`**: added `PriorValidationStatus` and
`PriorsValidationError`.

### `tests/test_s7_5_t1_priors_validation_fields.py` (NEW)

15 tests, organized:

- **Closed-enum contract** (2 tests): exactly-5-members pin and per-member name/value pin.
- **PriorEntry dataclass shape** (2 tests): defaults and explicit-value round-trip.
- **YAML loader backwards-compat** (2 tests): real `config/priors.yaml` loads cleanly + every resolved entry defaults to `HEURISTIC_UNVALIDATED`.
- **YAML loader authored-field round-trip** (3 tests): `validated_external` with all three fields, `placeholder`, and missing-field default.
- **Closed-enum rejection** (2 tests): unknown string raises `PriorsValidationError` naming play/prior/value + enumerating the legal set; `PriorsValidationError` is a `ValueError` subclass.
- **Tolerant-coercion edges** (3 tests): whitespace-only `source_artifact`, `effective_n=0`, non-numeric `effective_n` all coerce to `None` without raising.
- **Module surface** (1 test): `__all__` exports both new symbols.

Tests reuse the existing `_reset_cache` autouse fixture pattern from
`tests/test_priors_loader.py` so the global loader cache doesn't bleed
between test functions.

### No changes to

- `config/priors.yaml` — T1.5 walks the YAML to populate authored
  values; T1 is loader-only.
- `src/sizing.py`, `src/decide.py`, `src/engine_run.py` — T3 wires
  consumption behind a flag; T1 ships pure metadata.
- Other tests — no other test file's expectations changed; the new
  fields have safe defaults so every existing `PriorEntry(...)` and
  `_coerce_entry(...)` call continues to behave identically.

### Fixture re-pin

**None.** The plan's ticket spec is explicit: T1 lands schema/loader
only, ZERO behavior change.

| Fixture | sha256 | Status |
|---|---|---|
| `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` | `45edaca58c47797addf556b91460b81782dba6653d5d1ec82043bd40a051ea78` | **Unchanged** (matches S5-T3 baseline) |
| `tests/fixtures/synthetic_slate/healthy_supplements_240d_briefing.html` | `01f5feff84491db331611b3cbcbd94247699d11544e659a20efe0b67bbfede95` | **Unchanged** (matches S5-T3 baseline) |
| M0 goldens (small_sm / mid_shopify / micro_coldstart) | covered by `tests/test_golden_diff.py` | **Byte-identical** (test suite passes) |

## 3. Files changed

| File | Change |
|---|---|
| `src/priors_loader.py` | New `PriorValidationStatus` enum (closed, 5 values) + `PriorsValidationError` + 3 helper coercers + extended `PriorEntry` + rewired `_coerce_entry` + extended `__all__` |
| `tests/test_s7_5_t1_priors_validation_fields.py` | NEW — 15 tests covering enum / dataclass / loader round-trip / closed-enum rejection / tolerant edges / module exports |
| `memory.md` | New Sprint 7.5 section header + S7.5-T1 entry (template per S5-T1) |
| `agent_outputs/code-refactor-engineer-s7_5-t1-summary.md` | NEW — this file |

## 4. Tests / checks run

| Suite | Result |
|---|---|
| `tests/test_s7_5_t1_priors_validation_fields.py` | 15/15 green |
| `tests/test_priors_loader.py` | green |
| `tests/test_priors_yaml.py` | green |
| `tests/test_priors_metadata.py` | green |
| `tests/test_g3_supplements_priors.py` | green |
| `tests/test_slate_regression_beauty_brand.py` | green (Beauty pinned slate sha256 `45edaca58c47...` unchanged) |
| `tests/test_slate_regression_supplements_brand.py` | green (supplements G-1 sha256 `01f5feff84...` unchanged) |
| `tests/test_golden_diff.py` | green (M0 fixtures byte-identical) |
| Full suite (`pytest -q`) | **1205 passed, 14 skipped, 1 failed** in 795s (was 1190/14/1 at S5-T3 close). Delta = +15 new T1 tests. The 1 failure (`test_inventory_updated_at_is_fresh`) is the pre-existing wall-clock drift in the inventory CSV fixture, unrelated to this ticket. |

## 5. Behavior changes

**NONE.** This is the entire point of T1.

- No engine output change. No fixture re-pin. No flag introduced. No
  consumer (sizing / decide / renderer) reads `validation_status`.
- `engine_run.json` shape unchanged in both wire and value.
- `event_version=1` frozen contract intact — the new dataclass fields
  are Python-side typed metadata that do not serialize to
  `engine_run.json` today (no `engine_run.py` schema field references
  `validation_status` until T3).

## 6. Artifacts added

- `tests/test_s7_5_t1_priors_validation_fields.py` (15 tests)
- `agent_outputs/code-refactor-engineer-s7_5-t1-summary.md` (this file)

## 7. Remaining risks

1. **The closed-enum strictness diverges from the implementation-manager
   plan's tolerant policy.** The plan said "fallback to
   `heuristic_unvalidated` on missing or unknown value (with a debug log
   line, no raise — consistent with existing tolerant-loader policy)."
   The orchestrator's ticket prompt overrode this with a strict policy.
   Strict is the correct call for the closed-enum contract (a typo'd
   `validated_externall` would otherwise silently degrade to
   `heuristic_unvalidated` and the engine would suppress instead of
   blending — confusingly safe-by-accident but not by contract). T1.5
   authors must use the exact lowercase strings; the error message
   enumerates the full set, so a typo is self-correcting.
2. **`resolve_mixed_prior` blended entries default to
   `HEURISTIC_UNVALIDATED`.** Today this is the right answer pre-T3 (it
   IS the most-conservative value). T3 must add an explicit
   conservative-min blend rule (plan §4 names this as the KI-19
   verification test) so a future blend of two `validated_external`
   beauty + supplements entries doesn't silently downgrade to
   `heuristic_unvalidated`. Tracked as a T3 dependency, not a T1 bug.
3. **`effective_n` and `source_artifact` use tolerant coercion.** A typo
   on `effective_n` (e.g., `"twelve hundred"`) silently becomes `None`
   rather than raising. T2's invariant test will catch this (it asserts
   `validated_external` entries MUST have a non-null `source_artifact`),
   but T1 does not pin the typed-int contract on `effective_n`. Accept
   as intentional — the closed-enum strictness lives on
   `validation_status` only because that's the field the refusal rule
   reads.

## 8. Follow-up work / dependencies

- **S7.5-T1.5** (priors YAML audit pass) is the next ticket; walks every
  entry in `config/priors.yaml` and authors `validation_status`
  explicitly. Founder Q3 (reproducible CSV artifacts for the 8
  `internal_csv_observation_v1` entries) is the main input.
- **S7.5-T2** (external-benchmark memos) depends on T1.5 close and
  founder Q1 (which external sources to pursue).
- **S7.5-T3** (cold-start blend refusal + abstain mode behind
  `ENGINE_V2_PRIORS_VALIDATION`) wires consumption. Plan §2 lines
  202-260; the `pseudo_N` policy table lives in T3 (plan §1
  schema-additions table, default values `{validated_external: 30,
  validated_internal: 15, elicited_expert: 10}` per founder Q4).
- **S7.5-T3.5** (flag flip ON + atomic fixture re-pin) is the only
  behavior-changing ticket in S7.5 and the actual beta gate.

## 9. Branch shape

Three commits on `post-6b-restructured-roadmap` (not pushed), following
the per-commit ritual:

1. `817a08d` — `S7.5-T1: PriorEntry validation_status + source_artifact + effective_n fields` (impl + new test file)
2. `da8a850` — `Document S7.5-T1 in repo memory.md`
3. _this commit_ — `S7.5-T1 summary` (this file)

## 10. Hard constraints respected

- `engine_run.json` schema **unchanged** in shape — `PriorEntry` dataclass
  additions are Python-side only; nothing serializes to `engine_run.json`
  until T3 plumbs consumption.
- `event_version=1` payloads **frozen** — no payload field shape
  changes; additive new dataclass fields with safe defaults are not on
  the wire.
- D-6 enforced — no banned ML modules touched.
- D-8 enforced — vertical scope unchanged (`{beauty, supplements,
  mixed}`); no new verticals introduced.
- M0 Beauty pinned fixture sha256 **unchanged**.
- Beauty pinned slate sha256 **unchanged** at `45edaca58c47...`.
- Supplements G-1 fixture sha256 **unchanged** at `01f5feff84...`.
- B-5 Berkson invariant intact — directional builder cohort logic
  untouched (this ticket is loader-only).
- S-2 / S-3 / S-4 / S-5 / S-6 substrate write paths **untouched**.
- `config/priors.yaml` **untouched** (T1.5 owns the YAML walk).
- `KNOWN_ISSUES.md` **untouched** at T1 per plan §4 — T2/T3 close priors-validation tracking; T1 close opens no new KI (the `pseudo_N` table forward-looking-scaffolding KI is a T3 surface, not T1).
- No new runtime dependencies.
