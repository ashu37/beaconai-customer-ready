# Code Refactor Engineer — Phase 6A Ticket A3 Summary

_Date: 2026-05-04_
_Branch: `engine-rework`_
_Baseline commit: `e11f7c5` (post-A2)_
_Scope: Phase 6A Ticket A3 ONLY from `agent_outputs/implementation-manager-campaign-slate-plan.md`._

## Approved Scope

Add per-play `metadata:` blocks to `config/priors.yaml` for the two
first-ship-allowlisted plays (`bestseller_amplify`, `discount_hygiene`).
Extend `src/priors_loader.py` with typed metadata support: a
loader-side `AudienceArchetype` enum (lowercase, contract-locked),
a `PlayMetadata` frozen dataclass, and a public
`get_play_metadata(play_id) -> Optional[PlayMetadata]` function.
**Config + loader only. NO runtime engine behavior changes.** No
decide-layer eligibility filter, no `EngineRun.recommended_experiments`,
no renderer changes, no `PlayCard.would_be_measured_by` population, no
new role section, no slate-diversity rule. Goldens must pass without
re-baseline.

## Patch Summary

1. **`config/priors.yaml`** — converted the per-play structure for
   `bestseller_amplify` and `discount_hygiene` from the legacy list form
   (`plays.<play_id>: [<prior>, ...]`) to the dict form
   (`plays.<play_id>: {metadata: {...}, priors: [<prior>, ...]}`). The
   `metadata:` blocks contain the five required fields:
   `audience_floor` (positive int), `mechanism` (non-empty string),
   `vertical_applicability` (list of vertical strings),
   `would_be_measured_by` (UPPER_SNAKE_CASE matching
   `WouldBeMeasuredBy` from A2), `audience_archetype` (lowercase
   matching the loader-side `AudienceArchetype`). All other plays
   remain in their existing list form, untouched.

2. **`src/priors_loader.py`** — purely additive:
   - Added `AudienceArchetype(str, Enum)` with the 8 contract-locked
     lowercase members (`first_time_buyer`, `lapsed_buyer`,
     `discount_buyer`, `hero_sku_buyer`, `replenishment_buyer`,
     `full_price_buyer`, `vip_loyalist`, `no_archetype`).
   - Added `PriorsMetadataError(ValueError)` so callers can
     discriminate metadata-specific failures from other YAML failures
     (subclass of `ValueError` for backwards-compatibility).
   - Added `@dataclass(frozen=True) class PlayMetadata` with the five
     typed fields, mirroring the existing `PriorEntry` convention.
   - Added a private `_extract_play_block(doc, play_id)` helper that
     returns `(priors_list, metadata_dict)` and tolerates BOTH the
     legacy list form and the new dict form. `get_prior` and
     `list_priors_for_play` now both go through this helper, so plays
     in the dict form keep resolving for sizing (the only existing
     runtime consumer of priors).
   - Added `_coerce_metadata_enum(...)` (mirrors the
     `_coerce_enum`-style helper used in `engine_run.py`) and
     `_coerce_metadata(play_id, raw)` which validates each metadata
     field, raises `PriorsMetadataError` on missing/invalid values, and
     returns a typed `PlayMetadata`.
   - Added the public `get_play_metadata(play_id, *, path=None) ->
     Optional[PlayMetadata]`. Returns `None` for plays that do not
     carry a `metadata:` block. Raises on malformed metadata.
   - Updated `__all__` to export `PlayMetadata`, `AudienceArchetype`,
     `PriorsMetadataError`, `get_play_metadata`.

3. **`tests/test_priors_yaml.py`** — schema-validation tests now walk
   either the legacy list form or the dict-form's `priors:` sub-list.
   Renamed `test_every_play_block_is_a_list` →
   `test_every_play_block_is_well_formed` to reflect the dual-form
   contract; the assertion still rejects any other shape. New small
   helper `_priors_list_for_play` normalises both forms. The four
   downstream tests (`test_every_prior_has_required_keys`,
   `test_every_prior_has_allowed_source_class`,
   `test_value_ranges_are_ordered`, `test_applies_to_is_a_dict`) use
   the helper and continue to assert the priors-row contract on every
   play. **No prior contract was loosened.**

4. **`tests/test_priors_metadata.py` (NEW)** — 21 tests covering the
   acceptance criteria.

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml`
  - `bestseller_amplify` and `discount_hygiene` converted to dict form
    with `metadata` + `priors` keys. All other plays untouched. No
    prior values changed.
- `/Users/atul.jena/Projects/Personal/beaconai/src/priors_loader.py`
  - Added `AudienceArchetype` enum, `PriorsMetadataError`,
    `PlayMetadata` dataclass, `_coerce_metadata_enum`,
    `_coerce_metadata`, `_extract_play_block`, `get_play_metadata`.
  - Updated `get_prior` and `list_priors_for_play` to read priors via
    `_extract_play_block` so they keep working for both list-form and
    dict-form plays.
  - Added a top-of-module import: `from .engine_run import WouldBeMeasuredBy`.
  - Updated `__all__`.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_priors_yaml.py`
  - Added `_priors_list_for_play` helper.
  - Renamed `test_every_play_block_is_a_list` →
    `test_every_play_block_is_well_formed`; tightened the assertion to
    accept dict form only when the dict has a `priors:` list.
  - Updated the four downstream walker tests to use the helper.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_priors_metadata.py` (NEW)
  - 21 tests across enum surface, dataclass surface, real-config
    metadata loading, legacy-form preservation, and synthetic invalid
    fixtures.

No other files modified. No `src/decide.py`, no
`src/storytelling_v2.py`, no `src/storytelling.py`, no
`src/engine_run.py`, no `src/sizing.py`, no goldens, no fixtures.

## Loader Convention Used

- **Schema layer:** plain Python `@dataclass(frozen=True)` (matches the
  existing `PriorEntry`); enums are `str`-mixin `Enum` subclasses
  (matches `EvidenceClass`, `DecisionState`, `ReasonCode`,
  `WouldBeMeasuredBy`, etc.).
- **Enum coercion helper:** the loader did NOT previously have an
  `_coerce_enum`-style helper (the priors loader was permissive and
  fell back to `None` instead of raising). Phase 6A Ticket A3
  introduces a new metadata-specific helper `_coerce_metadata_enum`
  that:
  - Mirrors the `engine_run._coerce_enum` shape (idempotent on
    already-coerced enums; calls `enum_cls(value)` otherwise).
  - Raises `PriorsMetadataError` (a `ValueError` subclass) instead of a
    raw `ValueError`, so test failures point at the YAML block and
    field name. The error message lists the valid enum values.
- **Why not reuse `engine_run._coerce_enum` directly:** that helper is
  private to the schema module and silently returns `None` for
  unrecognized values rather than naming the offending YAML location.
  The metadata helper enforces hard validation at load time (per the
  prompt's "must raise a clear, named error at load time" requirement)
  and reuses the underlying `enum_cls(value)` constructor — same call
  the engine helper makes — so the coercion mechanic is identical.

## Casing Decision For `AudienceArchetype`

**Lowercase string values** (e.g. `hero_sku_buyer`, `discount_buyer`).

Rationale, per the prompt's instructions:

1. The campaign-slate contract
   (`agent_outputs/campaign-slate-contract-final.md`) consistently
   lists archetypes as lowercase strings: `hero_sku_buyer`,
   `discount_buyer`, `lapsed_buyer`, etc. (lines 99, 215). The contract
   document never uses an UPPER_SNAKE_CASE archetype.
2. The implementation-manager plan locks the initial archetype set in
   the same lowercase form (line 77, line 377): `{first_time_buyer,
   lapsed_buyer, discount_buyer, hero_sku_buyer, replenishment_buyer,
   full_price_buyer, vip_loyalist, no_archetype}`.
3. The metadata YAML schema in the same plan (line 405, line 414)
   writes the archetype as a lowercase YAML scalar:
   `audience_archetype: hero_sku_buyer`.
4. The prompt's instructions explicitly state: "Match exactly what
   appears in `agent_outputs/campaign-slate-contract-final.md` if it
   specifies casing — read the contract before deciding. Otherwise
   default to lowercase as written in the YAML schema below." Both the
   contract and the YAML schema use lowercase.

This **deviates from** the A2 `WouldBeMeasuredBy` UPPER_SNAKE_CASE
convention. The split is intentional and now pinned by tests. A future
agent extending the archetype enum must use lowercase.

## Exact Commands Run

```bash
# Red-first (BEFORE the loader/YAML changes landed)
python -m pytest tests/test_priors_metadata.py -v
# -> 16 failed, 5 passed in 0.15s
# (the 5 that passed were existing-loader smoke tests reused from the
# real config; the 16 that failed asserted on the new loader surface
# that did not yet exist.)

# Green (AFTER the loader/YAML changes landed)
python -m pytest tests/test_priors_metadata.py -v
# -> 21 passed in 0.19s

# Priors regression (existing loader + YAML schema tests must still pass)
python -m pytest tests/test_priors_metadata.py tests/test_priors_loader.py tests/test_priors_yaml.py -v
# -> 44 passed in 0.39s

# Engine-run schema (A2 contract intact)
python -m pytest tests/test_engine_run_schema.py -v
# -> 12 passed in 0.05s

# Goldens (M0 byte-identical)
python -m pytest tests/test_golden_diff.py -v
# -> 3 passed (no re-baseline)

# A1 + A2 territory regression
python -m pytest tests/test_render_v2.py tests/test_decide.py \
                 tests/test_watching_load_bearing_priority.py \
                 tests/test_phase5_watching_signals.py \
                 tests/test_would_be_measured_by_enum.py -q
# -> 87 passed in 3.24s

# Cross-cutting Fix 1-11 invariants
python -m pytest tests/test_targeting_no_dollar_headline.py \
                 tests/test_phase5_no_aura_beacon.py \
                 tests/test_targeting_measurement_invariant.py \
                 tests/test_abstain_soft_no_recommendations.py \
                 tests/test_inventory_blocked_in_considered.py \
                 tests/test_materiality_footer_present.py \
                 tests/test_matrix_vertical_propagation.py \
                 tests/test_reporter_dom_only.py \
                 tests/test_synthetic_fixtures_8_11.py -q
# -> 114 passed, 3 skipped

# Sizing (the only existing runtime consumer of priors_loader)
python -m pytest tests/test_sizing.py -v
# -> all pass (priors lookups still resolve for both YAML forms)

# Full suite
python -m pytest tests/ -q
# -> 733 passed, 14 skipped, 0 failed in 116.95s
```

`tests/test_phase5_3_watching.py` does NOT exist; the equivalent file
is `tests/test_phase5_watching_signals.py`.

## Tests / Checks Run

| Check | Result | Notes |
|---|---|---|
| `tests/test_priors_metadata.py` (NEW) | **21 passed** | Red-first failure captured (16 fail) before loader landed |
| `tests/test_priors_loader.py` | 15 passed | All existing loader tests intact |
| `tests/test_priors_yaml.py` | 8 passed | Renamed `test_every_play_block_is_a_list` → `_is_well_formed`; helpers handle both YAML forms |
| `tests/test_engine_run_schema.py` | 12 passed | A2 contract intact |
| `tests/test_golden_diff.py` | **3 passed (no re-baseline)** | M0 byte-identical |
| `tests/test_render_v2.py` | 25 passed | A1 watching cap unchanged |
| `tests/test_decide.py` | 34 passed | A1 builder unchanged |
| `tests/test_watching_load_bearing_priority.py` | 5 passed | A1 contract intact |
| `tests/test_phase5_watching_signals.py` | 9 passed | Phase 5.3 contract intact |
| `tests/test_would_be_measured_by_enum.py` | 14 passed | A2 enum surface intact |
| `tests/test_sizing.py` | 24 passed | Sizing still resolves priors via the loader for both YAML forms |
| Fix 1-11 invariants (9 files) | 114 passed, 3 skipped | All synthetic-fix contracts intact |
| Full suite `pytest tests/ -q` | **733 passed, 14 skipped, 0 failed** | Pre-A3 baseline 712 passed; +21 = exactly the new test file |

## Did The New Tests FAIL Before The Fix?

**Yes — red-first evidence captured.**

Before any change to `src/priors_loader.py` or `config/priors.yaml`,
`python -m pytest tests/test_priors_metadata.py -v` produced:

```
ImportError: cannot import name 'AudienceArchetype' from 'src.priors_loader'
AttributeError: module 'src.priors_loader' has no attribute 'PlayMetadata'
AttributeError: module 'src.priors_loader' has no attribute 'PriorsMetadataError'
AttributeError: module 'src.priors_loader' has no attribute 'get_play_metadata'
```

→ **16 failed, 5 passed.** The 5 that passed were the loader-existence
smoke tests (`test_existing_plays_still_load_via_load_priors`,
`test_get_prior_still_resolves_*`, `test_list_priors_for_play_*`,
`test_get_prior_still_resolves_for_legacy_list_form_plays`) which
exercise the existing `load_priors`/`get_prior` surface that A3 must
preserve — passing them red was the correct signal that the
no-regression invariant held.

After the loader and YAML changes landed, all 21 tests passed on first
run. One test (`test_play_metadata_dataclass_is_importable`) initially
failed because I used `hasattr(cls, field_name)` on a frozen dataclass
without defaults; corrected to use `dataclasses.fields(cls)` (the
canonical introspection path) and re-ran green.

## Goldens

- `tests/test_golden_diff.py` → **3 passed, 0 re-baselined**.
- M0 legacy goldens (`tests/golden/{small_sm, mid_shopify,
  micro_coldstart}/*`): byte-identical.
- This is the expected outcome because (a) no producer in the engine
  reads `get_play_metadata` in Ticket A3, (b) the YAML form change
  (list → dict) is invisible to `get_prior` because the loader's
  `_extract_play_block` helper handles both forms, (c) sizing's prior
  lookups for `bestseller_amplify` and `discount_hygiene` resolve
  identically before and after (verified by the test
  `test_get_prior_still_resolves_for_metadata_carrying_play`).

## Confirmation A1 + A2 Behavior Is Intact

A3 did NOT touch any A1 or A2 territory:

- `src/storytelling_v2.py` not modified.
- `src/decide.py` not modified.
- `src/engine_run.py` not modified.
- `MAX_WATCHING_RENDERED = 4` unchanged.
- `_LOAD_BEARING_WATCH_METRICS` unchanged.
- Empty-HELD MOVED-load-bearing fallback in `build_watching` unchanged.
- `WouldBeMeasuredBy` enum unchanged; `PlayCard.would_be_measured_by`
  field unchanged.

Cited tests verifying contracts post-A3:

- `tests/test_watching_load_bearing_priority.py` — 5/5 passed (A1).
- `tests/test_render_v2.py::test_watching_section_caps_at_four*` —
  passed (A1).
- `tests/test_phase5_watching_signals.py` — 9/9 passed (A1 / Phase 5.3).
- `tests/test_decide.py` — 34/34 passed (A1).
- `tests/test_would_be_measured_by_enum.py` — 14/14 passed (A2).
- `tests/test_engine_run_schema.py` — 12/12 passed (A2 round-trip,
  including the parametrized member round-trip and the
  UPPER_SNAKE_CASE invariant).

## Behavior Changes

None at the engine runtime level.

- The merchant-facing `briefing.html` is unchanged on every fixture
  because no renderer reads `get_play_metadata`.
- `EngineRun.to_dict()` payloads are unchanged because no producer
  populates `would_be_measured_by` yet (A2's invariant).
- `src/sizing.py` resolves priors through `get_prior`, which now goes
  through `_extract_play_block`. For `bestseller_amplify` and
  `discount_hygiene` the resolved priors are identical (same `value`,
  `range_p10`, `range_p90`, `source_class`, `applies_to` for every
  scope tested). For all other plays nothing changed because their
  YAML form is unchanged. Smoke-tested via `test_sizing.py` and the
  full suite.
- The loader exposes three new public symbols (`AudienceArchetype`,
  `PlayMetadata`, `PriorsMetadataError`) and one new public function
  (`get_play_metadata`). No engine code calls any of them yet.

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_priors_metadata.py`
  — 21 tests across enum surface, dataclass surface, real-config
  metadata loading, legacy-form preservation, and synthetic invalid
  fixtures (invalid enum values, zero/negative `audience_floor`,
  missing required keys, empty `mechanism`, valid synthetic round-trip,
  legacy list-form play returning `None` metadata).

No new sample HTML / receipts / docs / fixtures. No goldens modified.

## Remaining Risks

1. **Round-trip serializer not provided.** The prompt's optional
   acceptance criterion was: "Round-trip: the parsed `PlayMetadata`
   re-serializes (if the loader exposes a serializer) to a dict that
   equals the source YAML. If no serializer exists, skip this
   assertion." The loader does NOT today expose a serializer; the
   round-trip assertion is correctly skipped. Adding a serializer is
   out of A3 scope (no consumer needs it yet); if a future agent wants
   to write metadata back to YAML, that is a separate ticket.

2. **Two YAML forms now co-exist.** `bestseller_amplify` and
   `discount_hygiene` use the dict form; every other play uses the
   list form. This is intentional — A3 is purely additive — but a
   reviewer skimming the YAML may be surprised by the structural split.
   Documented in the YAML comments and in `_extract_play_block`.

3. **`PriorsMetadataError` is a `ValueError` subclass.** Tests catch
   `(ValueError, PriorsMetadataError)` so callers using the broader
   `ValueError` surface (e.g. `pytest.raises(ValueError)`) still trip.
   New callers can discriminate metadata-specific errors. If a future
   agent decides to widen the error hierarchy (e.g. introduce
   `PriorsLoaderError` as the parent), the public class name remains a
   valid marker.

4. **`vertical_applicability` is validated as a list of strings only.**
   The prompt allows "validate against existing vertical names if a
   canonical set already exists in the codebase; otherwise accept free
   strings." There is no canonical vertical-name enum on the engine
   side today (`VERTICAL_MODE` is a free-string env var), so the
   loader accepts free strings. Ticket A4's eligibility filter will be
   the natural place to cross-check `vertical_applicability` against
   the resolved `VERTICAL_MODE`.

5. **Importing `WouldBeMeasuredBy` at module load.** The loader now
   imports from `src.engine_run` at top-of-module. Smoke-tested for
   circular-import: `python -c "from src import priors_loader"` works,
   the full suite passes, and `engine_run.py` does NOT import
   `priors_loader` (verified). If a future ticket adds an
   `engine_run` → `priors_loader` import, that introduces a cycle and
   must be resolved by lazy-importing on the engine_run side.

6. **Test-file rename is mechanical.**
   `test_every_play_block_is_a_list` → `test_every_play_block_is_well_formed`
   is a single test name change in `tests/test_priors_yaml.py`. Any
   future tooling or CI that filters by the old name will need
   updating; the contract the test asserts is strictly stronger than
   the old contract.

## Readiness For The Next Phase 6A Ticket

**Ready for Ticket A4.**

A4 (decide-layer eligibility filter + new
`EngineRun.recommended_experiments` field) consumes the surface A3
delivered:

- `priors_loader.get_play_metadata(play_id)` returns a typed
  `PlayMetadata` for both first-ship-allowlisted plays
  (`bestseller_amplify`, `discount_hygiene`) and `None` for every
  other play. A4's eligibility filter can iterate candidate plays,
  call `get_play_metadata`, and gate by `audience_floor`,
  `vertical_applicability`, `would_be_measured_by` presence, and
  `audience_archetype`.
- `AudienceArchetype` is the locked taxonomy for A4's slate-diversity
  rule (Ticket B5 will pin it as a property test).
- `WouldBeMeasuredBy` (A2) and `PlayMetadata` (A3) are decoupled — A4
  can populate `PlayCard.would_be_measured_by` from
  `PlayMetadata.would_be_measured_by` without any further loader work.
- The full suite is at 733 passed, 14 skipped — clean baseline for
  A4's red-first work.

A4 is also free to begin in parallel with any B-series renderer ticket
because B-series only reads `EngineRun.recommended_experiments`, which
A4 populates.

No follow-up cleanup or re-review is required before A4 begins.

## Git Status

Per convention, changes are NOT committed. Files left unstaged for
review:

- 1 modified config file: `config/priors.yaml` (only
  `bestseller_amplify` and `discount_hygiene` blocks restructured;
  values unchanged).
- 1 modified `src/` file: `priors_loader.py` (purely additive plus
  the helper-routed read in `get_prior` / `list_priors_for_play`).
- 1 modified test file: `tests/test_priors_yaml.py` (helper added;
  one test renamed; four downstream tests use the helper).
- 1 new test file: `tests/test_priors_metadata.py`.
- 1 new doc file: this summary.
- No goldens modified.
- No legacy `src/storytelling.py` modified.
- No A1 files (`src/decide.py`, `src/storytelling_v2.py`) modified.
- No A2 files (`src/engine_run.py`) modified.
