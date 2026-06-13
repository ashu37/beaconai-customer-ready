# Code Refactor Engineer — Phase 6A Ticket A4 Summary

_Date: 2026-05-05_
_Branch: `engine-rework`_
_Baseline commit: `d8b7859` (post-A3)_
_Scope: Phase 6A Ticket A4 ONLY from `agent_outputs/implementation-manager-campaign-slate-plan.md`._

## Approved Scope

Add the Recommended Experiment decide-layer eligibility filter behind
`ENGINE_V2_SLATE`, default OFF. Compute
`EngineRun.recommended_experiments` but do NOT render a new section.

This is a decide-layer-only ticket. The renderer is untouched. With
the flag OFF, `recommended_experiments` is always `[]` and no slate
logic runs. With the flag ON, eligibility is filtered against the
allowlist `{discount_hygiene, bestseller_amplify}`, the priors
metadata block (Ticket A3), the per-play `audience_floor`, the current
`VERTICAL_MODE`, an inventory-block check, audience-overlap (<30%) vs
Recommended Now, slate diversity by `audience_archetype`, and a hard
cap of 2 cards. Both abstain branches force the list to `[]`.

## Patch Summary

1. **`src/engine_run.py`** — added
   `recommended_experiments: List[PlayCard] = field(default_factory=list)`
   to `EngineRun`. Updated `_from_dict_engine_run` to round-trip the
   new field through the existing `_from_dict_play_card` helper. The
   field is optional and the `to_dict` path (`_to_jsonable`) handles
   the new field automatically because the serializer walks every
   dataclass field.

2. **`src/utils.py`** — registered the new feature flag
   `ENGINE_V2_SLATE` (default `false`) using the same env-driven
   convention as `ENGINE_V2_DECIDE` / `ENGINE_V2_OUTPUT`. Added the key
   to the bool-coercion set in `_coerce` so `.env` overrides work.

3. **`src/decide.py`** — additive only:
   - Added `MAX_RECOMMENDED_EXPERIMENT: int = 2`.
   - Added
     `RECOMMENDED_EXPERIMENT_ALLOWLIST: frozenset[str] = frozenset({"discount_hygiene", "bestseller_amplify"})`.
   - Added `RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD: float = 0.30`.
   - Added `_select_recommended_experiments(...)` — a pure helper that
     returns 0–2 PlayCards. Reads metadata via
     `priors_loader.get_play_metadata` (overridable via the
     `metadata_lookup` kwarg for test fault-injection).
   - Imported `Audience` and `RevenueRange` so the selector can
     synthesize cards.
   - Extended `decide()` with an optional `candidates: Optional[Iterable]
     = None` kwarg. Inside `decide()`, the slate flag is read from
     `cfg["ENGINE_V2_SLATE"]`; vertical is resolved from
     `cfg["VERTICAL_MODE"]` / `cfg["VERTICAL"]` / `briefing_meta.vertical`.
   - All three branches (ABSTAIN_HARD, ABSTAIN_SOFT, PUBLISH) now
     write `recommended_experiments` on the returned EngineRun. Both
     abstain branches force `[]`. The PUBLISH branch invokes
     `_select_recommended_experiments`. Belt-and-suspenders: the
     selector itself short-circuits on abstain states and on
     `flag_on=False`.
   - Updated `__all__` to export the new constants.

4. **`tests/test_recommended_experiment_eligibility.py` (NEW)** —
   22 tests covering schema round-trip, constants, flag-off /
   flag-on through `decide()`, and every eligibility rule via direct
   helper calls. Includes a property-style invariant sweep over a
   small set of synthesized candidate inputs.

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py`
  - Added `recommended_experiments` field on `EngineRun` (with a
    Phase 6A Ticket A4 docstring block).
  - Extended `_from_dict_engine_run` to round-trip the new field.
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py`
  - Added `ENGINE_V2_SLATE` to `DEFAULTS` (default `false`).
  - Added `ENGINE_V2_SLATE` to the bool-coercion set in `_coerce`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py`
  - Added `Audience` and `RevenueRange` to the imports.
  - Added `MAX_RECOMMENDED_EXPERIMENT`,
    `RECOMMENDED_EXPERIMENT_ALLOWLIST`,
    `RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD` constants.
  - Added `_select_recommended_experiments(...)` helper.
  - Extended `decide()` signature with optional `candidates` kwarg.
  - All three return paths now stamp `recommended_experiments`.
  - Updated `__all__`.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_recommended_experiment_eligibility.py` (NEW)
  - 22 tests across schema, constants, flag-off / flag-on through
    `decide()`, eligibility rules, and a property-style invariant test.

No other files modified. No `src/storytelling.py`, no
`src/storytelling_v2.py`, no `src/main.py`, no
`src/engine_run_adapter.py`, no `src/sizing.py`, no
`config/priors.yaml`, no goldens, no fixtures.

## Selector Design

`_select_recommended_experiments` is a pure function. Signature:

```python
def _select_recommended_experiments(
    candidates: Iterable[Any],
    *,
    recommendations: Iterable[PlayCard],
    flag_on: bool,
    decision_state: DecisionState,
    vertical: Optional[str],
    metadata_lookup=None,
) -> List[PlayCard]
```

- Accepts duck-typed candidates (any object with `play_id`,
  `audience_size`, `segment_definition`, `preliminary_rejection_reason`,
  `audience_overlap`). The real `src.detect.Candidate` and the test
  stand-ins both satisfy this.
- `metadata_lookup` defaults to `priors_loader.get_play_metadata` and
  is overridable in tests to simulate missing or shared-archetype
  metadata. Late binding keeps the priors-loader dependency lazy and
  avoids any new import cycle.

Filter pipeline (short-circuits on each rule):

1. flag off → `[]`
2. ABSTAIN_SOFT / ABSTAIN_HARD → `[]`
3. allowlist gate
4. role-uniqueness vs `recommendations`
5. inventory block (`preliminary_rejection_reason == "inventory_blocked"`)
6. metadata exists
7. mechanism non-empty
8. audience floor
9. vertical applicability
10. `would_be_measured_by` present
11. audience overlap < 0.30 vs every Recommended Now card
12. deterministic sort: `(-audience_size, play_id)`
13. slate diversity: dedup by `audience_archetype`
14. cap at 2

Output cards are stamped with:
- `evidence_class = EvidenceClass.TARGETING`
- `audience` from the candidate
- `measurement = None`
- `revenue_range = RevenueRange(suppressed=True, drivers=[{"reason": "experiment_no_calibrated_lift"}])`
- `would_be_measured_by` copied from `metadata.would_be_measured_by`

## decide() Wiring

The slate selector runs inside `decide()` only when the
abstain-state machine returned `PUBLISH`. The ABSTAIN_HARD and
ABSTAIN_SOFT branches both write `recommended_experiments=[]` on the
returned EngineRun. The selector itself also enforces the
abstain-zero contract, so the invariant is true even if a future
caller wires the helper directly.

`decide()` resolves the vertical in priority order:
`cfg["VERTICAL_MODE"]` → `cfg["VERTICAL"]` → `briefing_meta.vertical`.
The flag is read from `cfg["ENGINE_V2_SLATE"]` and defaults to
`False` if `cfg` is `None` or the key is missing.

`main.py` is intentionally NOT changed in A4. The plan's wiring
("pass `_phase5_cands` through to `decide()`") is the natural next
step but is deliberately left for a follow-on edit so this ticket
remains pure decide-layer work. With `ENGINE_V2_SLATE=true` and no
`candidates` kwarg, the selector receives an empty iterable and
returns `[]`. Once `main.py` plumbs candidates, the flag will
activate the slate end-to-end without any further edit to `decide()`.

## Exact Commands Run

```bash
# Red-first (BEFORE schema + selector landed)
python -m pytest tests/test_recommended_experiment_eligibility.py -v
# -> 22 failed (ImportError on EngineRun.recommended_experiments,
#    src.decide.MAX_RECOMMENDED_EXPERIMENT, _select_recommended_experiments).

# Green (AFTER schema + selector landed)
python -m pytest tests/test_recommended_experiment_eligibility.py -v
# -> 22 passed in 0.23s

# Schema + priors regression
python -m pytest tests/test_engine_run_schema.py \
                 tests/test_would_be_measured_by_enum.py \
                 tests/test_priors_metadata.py \
                 tests/test_priors_loader.py \
                 tests/test_priors_yaml.py \
                 tests/test_golden_diff.py -v
# -> 73 passed in 27.95s

# A1/A2/A3 territory regression
python -m pytest tests/test_render_v2.py tests/test_decide.py \
                 tests/test_watching_load_bearing_priority.py \
                 tests/test_phase5_watching_signals.py -q
# -> 73 passed in 3.37s

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

# Full suite
python -m pytest tests/ -q
# -> 755 passed, 14 skipped, 0 failed in 118.46s
```

## Tests / Checks Run

| Check | Result | Notes |
|---|---|---|
| `tests/test_recommended_experiment_eligibility.py` (NEW) | **22 passed** | Red-first failure captured before any source change |
| `tests/test_engine_run_schema.py` | 12 passed | A2 contract intact |
| `tests/test_would_be_measured_by_enum.py` | 14 passed | A2 enum surface intact |
| `tests/test_priors_metadata.py` | 21 passed | A3 loader intact |
| `tests/test_priors_loader.py` | 15 passed | Existing loader smoke intact |
| `tests/test_priors_yaml.py` | 8 passed | YAML schema intact |
| `tests/test_golden_diff.py` | **3 passed (no re-baseline)** | M0 byte-identical |
| `tests/test_render_v2.py` | 25 passed | A1 watching cap unchanged; renderer untouched |
| `tests/test_decide.py` | 34 passed | M7 contract intact; new selector additive |
| `tests/test_watching_load_bearing_priority.py` | 5 passed | A1 contract intact |
| `tests/test_phase5_watching_signals.py` | 9 passed | Phase 5.3 contract intact |
| Fix 1–11 invariants (9 files) | 114 passed, 3 skipped | All synthetic-fix contracts intact |
| Full suite `pytest tests/ -q` | **755 passed, 14 skipped, 0 failed** | Pre-A4 baseline 733 passed; +22 = exactly the new test file |

## Did The New Tests FAIL Before The Fix?

**Yes — red-first evidence captured.** Before any change to
`src/engine_run.py`, `src/utils.py`, or `src/decide.py`,
`python -m pytest tests/test_recommended_experiment_eligibility.py -v`
produced 22 failures with the following signatures:

```
AttributeError: 'EngineRun' object has no attribute 'recommended_experiments'
ImportError: cannot import name 'MAX_RECOMMENDED_EXPERIMENT' from 'src.decide'
ImportError: cannot import name 'RECOMMENDED_EXPERIMENT_ALLOWLIST' from 'src.decide'
ImportError: cannot import name '_select_recommended_experiments' from 'src.decide'
```

After the schema field, the constants, and the helper landed, all
22 tests passed on first run.

## Goldens

- `tests/test_golden_diff.py` → **3 passed, 0 re-baselined**.
- M0 legacy goldens (`tests/golden/{small_sm, mid_shopify,
  micro_coldstart}/*`): byte-identical.
- This is the expected outcome because (a) the new field defaults to
  `[]` on every EngineRun built today, (b) no producer in `main.py`
  populates it yet, (c) the legacy adapter does not project the new
  field into legacy outputs, and (d) no renderer reads the field.
  The field surfaces only in V2 receipts as
  `"recommended_experiments": []`, and V2 receipts are not pinned as
  goldens.

## Confirmation A1 + A2 + A3 Behavior Is Intact

A4 did NOT modify A1 territory:
- `src/storytelling_v2.py` not modified.
- `MAX_WATCHING_RENDERED = 4` unchanged.
- `_LOAD_BEARING_WATCH_METRICS` unchanged.
- Empty-HELD MOVED-load-bearing fallback in `build_watching` unchanged.

A4 added two imports (`Audience`, `RevenueRange`) to `src/decide.py`
and added new constants + a new helper. No existing function in
`src/decide.py` was modified except `decide()` itself, which gained
an optional `candidates` kwarg and a `recommended_experiments=` arg
on the three `replace()` calls. No other behavior changed:
- `MAX_RECOMMENDATIONS = 3` unchanged.
- `MAX_CONSIDERED_RENDERED = 6` unchanged.
- `MAX_WATCHING_SIGNALS = 4` unchanged.
- `rank_recommendations` unchanged.
- `assemble_considered` unchanged.
- `populate_considered_from_candidates` unchanged.
- `build_watching` unchanged.
- `_decide_abstain_state` unchanged.

A4 did NOT modify A2 territory:
- `WouldBeMeasuredBy` enum unchanged.
- `PlayCard.would_be_measured_by` field unchanged.

A4 did NOT modify A3 territory:
- `config/priors.yaml` unchanged.
- `src/priors_loader.py` unchanged.
- `AudienceArchetype`, `PlayMetadata`, `PriorsMetadataError`,
  `get_play_metadata` unchanged.

Cited tests verifying contracts post-A4:
- `tests/test_watching_load_bearing_priority.py` — 5/5 passed (A1).
- `tests/test_render_v2.py` — 25/25 passed (renderer untouched).
- `tests/test_phase5_watching_signals.py` — 9/9 passed (Phase 5.3).
- `tests/test_decide.py` — 34/34 passed (M7).
- `tests/test_would_be_measured_by_enum.py` — 14/14 passed (A2).
- `tests/test_engine_run_schema.py` — 12/12 passed (A2 round-trip).
- `tests/test_priors_metadata.py` — 21/21 passed (A3).
- `tests/test_priors_loader.py` — 15/15 passed.
- `tests/test_priors_yaml.py` — 8/8 passed.

## Behavior Changes

None at the merchant-facing level. With the flag OFF, `decide()`
returns the same EngineRun shape as before, plus a new
`recommended_experiments: []` field in the serialized JSON. With
the flag ON but no `candidates` plumbed through, the selector
receives an empty iterable and returns `[]`. The renderer is
unchanged.

`EngineRun.to_dict()` payloads now include
`"recommended_experiments": []` at the top level (or a populated
list when the slate fires). This is additive and forward-compatible.

`receipts/engine_run.json` will start carrying the new key on every
run. No consumer reads it yet.

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_recommended_experiment_eligibility.py`
  — 22 tests pinning schema round-trip, constants, decide-layer
  flag-off / flag-on, every eligibility rule, and a property-style
  invariant sweep.

No new sample HTML / receipts / docs / fixtures. No goldens
modified.

## Remaining Risks

1. **`main.py` not yet plumbing candidates into `decide()`.** With
   `ENGINE_V2_SLATE=true` end-to-end, the selector is a no-op
   because nothing passes `candidates=` to `decide()`. The natural
   follow-on edit is one line in `src/main.py` near the existing
   `if bool(cfg.get("ENGINE_V2_DECIDE", False)): ... engine_run =
   _v2_decide(engine_run, cfg=cfg)` block, passing
   `candidates=_phase5_cands`. Deliberately deferred so A4 stays
   pure decide-layer work; flagged here as a known open item.

2. **No producer populates `would_be_measured_by` on Recommended Now
   cards.** A4 only stamps the field on
   `recommended_experiments` cards. Existing measured / directional
   PlayCards continue to default `would_be_measured_by=None`. Per
   the contract this is correct: only experiments need the field.

3. **`evidence_class` not enforced as TARGETING on inputs.** The
   selector iterates M3 candidates (which have no
   `evidence_class`); the output is stamped TARGETING by
   construction. Test
   `test_rejects_measured_or_directional_candidate` covers the
   role-uniqueness path: an allowlisted play_id that is already a
   measured PlayCard in `recommendations` is excluded from
   experiments. The structural invariant "no PlayCard in two roles"
   becomes a defensive assertion in Ticket B4.

4. **Recently-run-fatigue is a no-op today.** Per the ticket scope
   no outcome-log read was added. The selector simply skips this
   gate. When `recommended_history.json` becomes non-stub
   (Phase 6B+), the rule can be wired with a single additional
   filter step inside `_select_recommended_experiments`; no
   schema changes will be needed.

5. **Allowlist is hard-coded.** The contract pins
   `{discount_hygiene, bestseller_amplify}`. A future agent who
   wants to expand this will edit the constant in `src/decide.py`
   alongside adding metadata blocks in `config/priors.yaml`. No
   YAML-driven allowlist was introduced because the contract
   explicitly limits first ship.

6. **`vertical` resolution falls back to `briefing_meta.vertical`.**
   This matches A3's expectation but means an EngineRun built
   without a vertical anywhere will fail rule 9 silently. The
   default `briefing_meta.vertical=None` in EngineRun(default)
   means rule 9 is bypassed (treated as no constraint). This is
   conservative — a missing vertical does not block the play —
   but worth flagging for the renderer ticket where the
   `vertical_applicability` chip might surface to the merchant.

7. **Audience overlap source = M3 candidate's `audience_overlap`
   dict.** Pre-computed by `compute_audience_overlap`. The dict
   may not include every Recommended Now card's `play_id` (e.g.
   if the rec is a directional card built post-detect). Missing
   keys are treated as 0.0 overlap (permissive). Acceptable for
   first ship; can be tightened by re-running overlap on the
   live audiences before the selector if needed.

## Readiness for Phase 6A Ticket B-series

**Ready for Ticket B1 (renderer for Recommended Experiment).**

A4 establishes the data contract B1 depends on:

- `EngineRun.recommended_experiments: List[PlayCard]` exists,
  defaults to `[]`, round-trips via `to_dict` / `from_dict`.
- Each card carries
  `evidence_class=TARGETING`,
  `audience.size`,
  `audience.definition`,
  `revenue_range.suppressed=True`,
  `would_be_measured_by` (Ticket A2 enum).
- Selector enforces the abstain contract; B1 can rely on the
  invariant "ABSTAIN_SOFT / ABSTAIN_HARD ⇒ list is empty" without
  re-checking.
- Property test sweeps cover the cap, the diversity, the overlap
  threshold, and the `would_be_measured_by` presence.
- Full suite at 755 passed, 14 skipped — clean baseline for B1.

A4 is also a clean prerequisite for B3 (ABSTAIN_SOFT extension to
zero experiments) and B4 (role-uniqueness invariant). Both can
build on the existing decide-layer scaffolding without revisiting
A4 internals.

The orchestrator should next run the implementation manager / PM /
DS Architect on the B-series, or proceed directly to Ticket B1
following the same prompt cadence used for A1–A4.

## Git Status

Per convention, changes are NOT committed. Files left unstaged for
review:

- 3 modified `src/` files: `engine_run.py`, `utils.py`, `decide.py`.
- 1 new test file: `test_recommended_experiment_eligibility.py`.
- 1 new doc file: this summary.
- No goldens modified.
- No legacy `src/storytelling.py` modified.
- No `src/storytelling_v2.py` (renderer) modified.
- No `src/main.py` modified.
- No `config/priors.yaml` modified.
- No `src/priors_loader.py` modified.
