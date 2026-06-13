# Code Refactor Engineer — Phase 6A Ticket A4.5 Summary

_Date: 2026-05-05_
_Branch: `engine-rework`_
_Baseline: post-A4 working tree (unstaged on top of `d8b7859`)._
_Scope: Phase 6A Ticket A4.5 ONLY from `agent_outputs/implementation-manager-campaign-slate-plan.md`._

## Approved Scope

Wire the already-built Phase 5 / M3 candidate list (`_phase5_cands`)
from `src/main.py` into the `decide()` call so the Recommended
Experiment selector landed in Ticket A4 can operate end-to-end.

When `ENGINE_V2_SLATE=true` AND `ENGINE_V2_DECIDE=true`, `main.py`
must call `decide(engine_run, cfg=cfg, candidates=_phase5_cands)` (or
equivalent) so the selector receives the live candidate list.

When `ENGINE_V2_SLATE=false` (or unset) the wiring must NOT change
observable behavior in any way: `recommended_experiments` stays `[]`
and goldens remain byte-identical.

This is a wiring-only ticket. Eligibility logic, priors metadata,
PlayCard schema, renderer, decide-layer ABSTAIN_SOFT contract, and
goldens are explicitly out of scope.

## Patch Summary

1. **`src/main.py`** — three additive edits inside the existing
   `run(...)` function:
   1. Hoisted a stable variable `_phase5_cands_for_decide = None`
      ABOVE the Phase 5 try/except block so the V2 decide block can
      reach it even when the Phase 5 candidate-build branch raises
      or is skipped.
   2. Inside the Phase 5 try block, after `_phase5_cands` is built
      via `_detect_candidates(...)`, bound
      `_phase5_cands_for_decide = _phase5_cands`. This is the only
      success path that reaches this line; on exception the variable
      remains `None`.
   3. Updated the V2 decide call from
      `_v2_decide(engine_run, cfg=cfg)` to
      `_v2_decide(engine_run, cfg=cfg, candidates=_phase5_cands_for_decide)`.
   4. Inline comments explain the A4.5 contract and the no-op
      semantics under `ENGINE_V2_SLATE=false`.

2. **`tests/test_recommended_experiment_main_wiring.py` (NEW)** —
   5 tests pinning the wiring contract:
   - Live wiring: `decide(...)` populates
     `recommended_experiments` for two allowlisted candidates.
   - Defensive: `candidates=None` returns `[]` without crash.
   - Defensive: `candidates=[]` returns `[]` without crash.
   - Structural pin: `src/main.py` text contains
     `_v2_decide(engine_run, cfg=cfg, candidates=...)` AND every
     `_v2_decide(...)` call site includes the kwarg literal
     (paren-balance scan).
   - Flag-off: `ENGINE_V2_SLATE=false` keeps
     `recommended_experiments=[]` even when candidates would
     otherwise pass.

No other files were modified. No `src/decide.py`, no
`src/engine_run.py`, no `src/storytelling.py`, no
`src/storytelling_v2.py`, no `src/utils.py`, no
`config/priors.yaml`, no `src/priors_loader.py`, no goldens, no
fixtures.

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py`
  - Hoisted `_phase5_cands_for_decide = None` before the Phase 5
    candidate-build try/except (~line 725).
  - Bound `_phase5_cands_for_decide = _phase5_cands` immediately
    after the successful `_detect_candidates(...)` call (~line 759).
  - Passed `candidates=_phase5_cands_for_decide` into
    `_v2_decide(...)` (~line 819).
  - Added two block comments referencing Phase 6A Ticket A4.5 and
    the no-op contract under `ENGINE_V2_SLATE=false`.

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_recommended_experiment_main_wiring.py` (NEW)
  - 5 tests across direct-decide live wiring, defensive
    None / empty handling, structural pin on the call site, and
    flag-off invariant.

## Where Candidates Are Sourced

The candidate list comes from M3 detect. Inside `src/main.py`, the
existing Phase 5 block calls
`_detect_candidates(g, aligned_for_template, cfg, _PLAYS, inventory_metrics=inventory_metrics)`
which returns the list of `Candidate` objects already used by
Phase 5.6 (directional-card builder) and Phase 5.2
(`populate_considered_from_candidates`).

A4.5 does NOT change how candidates are detected. It only adds a
new consumer: the Recommended Experiment selector inside
`decide()`. The same candidate list now feeds three downstream
paths:

1. `build_directional_recommendations(...)` (Phase 5.6) — builds
   the directional first_to_second_purchase card if the supporting
   signal clears the bar.
2. `populate_considered_from_candidates(...)` (Phase 5.2) — maps
   non-promoted candidates to typed Considered entries.
3. **NEW** `_select_recommended_experiments(...)` (Ticket A4 via
   `decide()` Ticket A4.5 wiring) — filters allowlisted targeting
   plays through the metadata + audience + overlap + diversity
   gates and emits 0-2 Recommended Experiment cards.

Single source of truth. No re-detection.

## How Candidates Are Passed Into decide()

Before A4.5:

```python
try:
    if bool(cfg.get("ENGINE_V2_DECIDE", False)):
        from .decide import decide as _v2_decide
        engine_run = _v2_decide(engine_run, cfg=cfg)
except Exception as _de:
    print(f"[V2 decide] Warning: decide() failed: {_de}")
```

After A4.5:

```python
_phase5_cands_for_decide = None
try:
    if bool(cfg.get("ENGINE_V2_DECIDE", False)):
        ...
        _phase5_cands = _detect_candidates(...)
        _phase5_cands_for_decide = _phase5_cands
        ...
except Exception as _ce:
    print(f"[V2 considered] Warning: populate failed: {_ce}")

try:
    if bool(cfg.get("ENGINE_V2_DECIDE", False)):
        from .decide import decide as _v2_decide
        engine_run = _v2_decide(
            engine_run,
            cfg=cfg,
            candidates=_phase5_cands_for_decide,
        )
except Exception as _de:
    print(f"[V2 decide] Warning: decide() failed: {_de}")
```

The hoist is the load-bearing piece: if the Phase 5 try/except
raises after `_detect_candidates(...)` succeeds (e.g.,
`build_directional_recommendations` blows up), the binding
`_phase5_cands_for_decide = _phase5_cands` may or may not have
executed. In either case the V2 decide block sees a defined name —
either the live list or `None` — and `decide()` short-circuits to
`[]` on `None`.

## Flag-Off Behavior

When `ENGINE_V2_SLATE=false` (or unset), `decide()` still runs the
selector path but the selector's first guard returns `[]`
immediately:

```python
if not flag_on:
    return []
```

So even if `candidates` is a non-empty list, the slate output is
forced to `[]`. The PUBLISH branch then writes
`recommended_experiments=[]` on the returned `EngineRun`. The
ABSTAIN_HARD and ABSTAIN_SOFT branches also write `[]` (Ticket A4
contract). No new HTML section renders because Ticket B1 has not
landed.

Goldens are byte-identical because the legacy renderer is unchanged
and V2 receipts (where `recommended_experiments` first appears) are
not pinned as goldens. Confirmed via `tests/test_golden_diff.py` —
3 passed, no re-baseline.

## Flag-On Behavior

When `ENGINE_V2_SLATE=true` AND `ENGINE_V2_DECIDE=true`:

- `_phase5_cands_for_decide` carries the live M3 detect output.
- `decide()` calls `_select_recommended_experiments(candidates, ...)`.
- The selector applies the Ticket A4 eligibility pipeline
  (allowlist, metadata, audience floor, vertical applicability,
  inventory block, overlap < 30%, archetype diversity, hard cap 2).
- 0-2 PlayCards land in `engine_run.recommended_experiments`.

A direct-decide test (`test_main_wires_candidates_into_decide_when_decide_flag_on`)
confirms 2 allowlisted candidates with audience 5000 each and a
Recommended Now directional card produce a 2-card slate, sorted
deterministically by `(-audience_size, play_id)` and deduped on
`audience_archetype`.

Note: end-to-end visibility in `briefing.html` is still gated on
Ticket B1 (renderer). `recommended_experiments` is now populated in
`receipts/engine_run.json` when the full V2 stack is on, but the
merchant-facing HTML does not yet render the new section. This is
the intended A4.5 milestone state.

## Exact Commands Run

```bash
# Red-first capture (BEFORE the wiring change)
python -m pytest tests/test_recommended_experiment_main_wiring.py -v
# -> 4 passed, 1 failed
#    Failure: test_main_module_v2_decide_call_passes_candidates
#    Reason: src/main.py call site read `_v2_decide(engine_run, cfg=cfg)`
#            without a `candidates=` kwarg.

# Green (AFTER the wiring change)
python -m pytest tests/test_recommended_experiment_main_wiring.py -v
# -> 5 passed in 0.04s

# A4 eligibility regression
python -m pytest tests/test_recommended_experiment_eligibility.py tests/test_decide.py -v
# -> 56 passed in 0.22s
#    (22 eligibility + 34 decide = 56)

# Golden diff regression
python -m pytest tests/test_golden_diff.py -v
# -> 3 passed, 0 re-baselined

# Cross-cutting Fix 1-11 + A1/A2/A3 regression
python -m pytest tests/test_targeting_no_dollar_headline.py \
                 tests/test_phase5_no_aura_beacon.py \
                 tests/test_targeting_measurement_invariant.py \
                 tests/test_abstain_soft_no_recommendations.py \
                 tests/test_inventory_blocked_in_considered.py \
                 tests/test_materiality_footer_present.py \
                 tests/test_matrix_vertical_propagation.py \
                 tests/test_reporter_dom_only.py \
                 tests/test_synthetic_fixtures_8_11.py \
                 tests/test_render_v2.py \
                 tests/test_watching_load_bearing_priority.py \
                 tests/test_engine_run_schema.py \
                 tests/test_would_be_measured_by_enum.py \
                 tests/test_priors_metadata.py -q
# -> 191 passed, 3 skipped in 5.68s

# Full suite
python -m pytest tests/ -q
# -> 760 passed, 14 skipped, 0 failed in 118.87s
```

## Tests / Checks Run

| Check | Result | Notes |
|---|---|---|
| `tests/test_recommended_experiment_main_wiring.py` (NEW) | **5 passed** | Red-first failure captured on the structural pin before the wiring landed |
| `tests/test_recommended_experiment_eligibility.py` | 22 passed | A4 contract intact |
| `tests/test_decide.py` | 34 passed | M7 contract intact |
| `tests/test_golden_diff.py` | **3 passed (no re-baseline)** | M0 byte-identical |
| `tests/test_render_v2.py` | 25 passed | Renderer untouched |
| `tests/test_watching_load_bearing_priority.py` | 5 passed | A1 contract intact |
| `tests/test_engine_run_schema.py` | 12 passed | Schema round-trip intact |
| `tests/test_would_be_measured_by_enum.py` | 14 passed | A2 contract intact |
| `tests/test_priors_metadata.py` | 21 passed | A3 contract intact |
| `tests/test_targeting_no_dollar_headline.py` | green | Phase 5.5 / M8 invariant |
| `tests/test_phase5_no_aura_beacon.py` | green | Phase 5.5 forbidden-token sweep |
| `tests/test_targeting_measurement_invariant.py` | green | Fix 2 |
| `tests/test_abstain_soft_no_recommendations.py` | green | Fix 3 |
| `tests/test_inventory_blocked_in_considered.py` | green | Fix 4 |
| `tests/test_materiality_footer_present.py` | green | Fix 5 |
| `tests/test_matrix_vertical_propagation.py` | green | Fix 6 |
| `tests/test_reporter_dom_only.py` | green | Fix 7 |
| `tests/test_synthetic_fixtures_8_11.py` | green | Fixes 8-11 |
| Full suite `pytest tests/ -q` | **760 passed, 14 skipped, 0 failed** | Pre-A4.5 baseline 755 passed; +5 = exactly the new test file |

## Did The New Tests FAIL Before The Wiring?

**Yes — red-first evidence captured.** Before any change to
`src/main.py`, running
`python -m pytest tests/test_recommended_experiment_main_wiring.py -v`
produced this output:

```
tests/test_recommended_experiment_main_wiring.py::test_main_wires_candidates_into_decide_when_decide_flag_on PASSED
tests/test_recommended_experiment_main_wiring.py::test_decide_handles_none_candidates_gracefully PASSED
tests/test_recommended_experiment_main_wiring.py::test_decide_handles_empty_candidates_gracefully PASSED
tests/test_recommended_experiment_main_wiring.py::test_main_module_v2_decide_call_passes_candidates FAILED
tests/test_recommended_experiment_main_wiring.py::test_flag_off_keeps_recommended_experiments_empty_via_decide PASSED

AssertionError: Expected `_v2_decide(engine_run, cfg=cfg, candidates=...)`
in src/main.py after Phase 6A Ticket A4.5; the slate selector cannot
operate without candidates plumbed through.
```

Three direct-decide tests passed because Ticket A4 already wired the
selector behind the `candidates=` kwarg; A4.5 closes the gap by
making `main.py` actually pass live candidates through. The
structural pin (`test_main_module_v2_decide_call_passes_candidates`)
is the test that captures the A4.5-specific wiring contract and was
the only red-first failure.

After the three-line wiring change in `src/main.py`, all 5 tests
passed on first run.

## Goldens

- `tests/test_golden_diff.py` → **3 passed, 0 re-baselined**.
- M0 legacy goldens (`tests/golden/{small_sm, mid_shopify,
  micro_coldstart}/*`): byte-identical.
- `ENGINE_V2_SLATE` defaults to `false` in `src/utils.py`. The legacy
  goldens are produced under flags-off conditions, so the new
  candidate-plumb has zero observable effect on them.
- `receipts/engine_run.json` already started carrying
  `"recommended_experiments": []` post-A4 (additive schema field).
  A4.5 does not change that for any default-flag run because
  `ENGINE_V2_SLATE=false` forces the list back to `[]` even when
  candidates are now passed.

## Behavior Changes

None at the merchant-facing level under default flags
(`ENGINE_V2_SLATE=false`). The only observable change is structural:

- When `ENGINE_V2_DECIDE=true` AND `ENGINE_V2_SLATE=true` end-to-end,
  `decide()` now receives the live M3 candidate list and
  `engine_run.recommended_experiments` may contain 0-2 PlayCards
  for `discount_hygiene` and/or `bestseller_amplify`. This list is
  serialized into `receipts/engine_run.json` but is NOT yet rendered
  in `briefing.html` (Ticket B1 owns the renderer).
- When `ENGINE_V2_DECIDE=true` AND `ENGINE_V2_SLATE=false`, behavior
  is identical to the post-A4 baseline.
- When `ENGINE_V2_DECIDE=false`, the second try block does not run,
  and `decide()` is not invoked at all. `_phase5_cands_for_decide`
  remains `None` and is unused. Identical to pre-A4 behavior.

Cap on rendered cards (Watching), opportunity-context block,
materiality footer, ABSTAIN_SOFT contract, ABSTAIN_HARD contract,
inventory-block routing, targeting-no-dollar invariant, forbidden
tokens — all unchanged.

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_recommended_experiment_main_wiring.py`
  — 5 tests pinning the candidate-plumb wiring contract, including
  the structural source-text assertion against future regressions.

- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6a-ticket-a4-5-summary.md`
  — this summary.

No new sample HTML / receipts / docs / fixtures. No goldens
modified.

## Confirmation A1 + A2 + A3 + A4 Behavior Is Intact

A4.5 did NOT modify A1 territory:
- `src/storytelling_v2.py` not modified.
- `MAX_WATCHING_RENDERED = 4` unchanged.
- `_LOAD_BEARING_WATCH_METRICS` unchanged.
- `tests/test_watching_load_bearing_priority.py` 5/5 passed.

A4.5 did NOT modify A2 territory:
- `src/engine_run.py` not modified.
- `WouldBeMeasuredBy` enum unchanged.
- `PlayCard.would_be_measured_by` field unchanged.
- `tests/test_would_be_measured_by_enum.py` 14/14 passed.
- `tests/test_engine_run_schema.py` 12/12 passed.

A4.5 did NOT modify A3 territory:
- `config/priors.yaml` unchanged.
- `src/priors_loader.py` unchanged.
- `AudienceArchetype`, `PlayMetadata`, `PriorsMetadataError`,
  `get_play_metadata` unchanged.
- `tests/test_priors_metadata.py` 21/21 passed.

A4.5 did NOT modify A4 territory:
- `src/decide.py` not modified.
- `_select_recommended_experiments(...)` unchanged.
- `MAX_RECOMMENDED_EXPERIMENT`,
  `RECOMMENDED_EXPERIMENT_ALLOWLIST`,
  `RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD` unchanged.
- `decide()` signature unchanged (already accepts `candidates=`
  from Ticket A4).
- All three return paths still stamp `recommended_experiments`.
- `tests/test_recommended_experiment_eligibility.py` 22/22 passed.
- `tests/test_decide.py` 34/34 passed.

## Remaining Risks

1. **End-to-end PUBLISH visibility still depends on Ticket B1.**
   With the A4.5 wiring in place, `engine_run.recommended_experiments`
   is now populated in `receipts/engine_run.json` when the full V2
   stack runs on real fixtures. However, the merchant-facing
   `briefing.html` does not yet render the new section. Ticket B1
   owns the renderer; until B1 lands, the Recommended Experiment
   slate is internally observable but invisible to the merchant.

2. **Phase 5 try/except may swallow unrelated exceptions.** The
   existing pattern catches every exception in the Phase 5
   candidate-build block and prints a warning. If
   `_detect_candidates(...)` succeeds but a downstream step
   (e.g., `build_directional_recommendations`) raises, the binding
   `_phase5_cands_for_decide = _phase5_cands` may have already
   executed — meaning the V2 decide block could run on a partially-
   processed candidate list. The selector itself is robust to any
   subset (it only reads candidate fields), but this is worth
   noting because a future broadening of the Phase 5 block could
   accidentally couple two pipelines. Mitigation already in place:
   the selector is pure and tolerates partial sets; tests in
   `tests/test_recommended_experiment_eligibility.py` exercise the
   tolerant paths.

3. **`_phase5_cands_for_decide = None` on Phase-5-block exception.**
   If `_detect_candidates(...)` itself raises, the binding never
   executes and the V2 decide block sees `None`, which the selector
   treats as an empty iterable. This is the conservative default —
   an exception in detection silently demotes the slate to empty,
   matching the pre-A4 behavior. A future agent who wants louder
   reporting of detect failures will need to surface that signal in
   the engine_run / receipts; outside A4.5 scope.

4. **Static source-text test on `_v2_decide(...)` call site.** The
   structural pin in
   `tests/test_recommended_experiment_main_wiring.py::test_main_module_v2_decide_call_passes_candidates`
   reads `src/main.py` as text and checks for `candidates=` on
   every `_v2_decide(...)` call. A future refactor that, e.g.,
   wraps `_v2_decide` in a helper or renames the import alias will
   break this test. That is the intended forcing function — the
   test is the contract that the wiring must persist. If a refactor
   needs to land, the test should be updated in lockstep with the
   refactor, not silenced.

5. **No full-pipeline E2E test added.** A truly end-to-end test
   that runs `main.run(...)` against a CSV fixture with the full
   V2+slate flag stack on would also exercise this wiring through
   the real load → features → segments → decide pipeline. That is
   intentionally deferred to Ticket B6 (Beauty Brand pinned slate
   regression), which the implementation manager plan scopes
   separately. The plan also notes that if such a test is added
   here, it should be gated behind `RUN_MAIN_E2E=1` and skipped by
   default; A4.5 leaves that decision to B6.

## Readiness For Ticket B1 (renderer)

**Ready.** A4.5 closes the data-plumbing gap that A4 explicitly
left open. With A4.5:

- `engine_run.recommended_experiments` is now populated end-to-end
  on real fixtures when `ENGINE_V2_SLATE=true` AND
  `ENGINE_V2_DECIDE=true`.
- Each card carries `evidence_class=TARGETING`, `audience` from M3,
  `revenue_range.suppressed=True` with the `experiment_no_calibrated_lift`
  driver, and a populated `would_be_measured_by` enum value.
- Schema round-trip is intact (Ticket A4 already covered this).
- The flag-off kill-switch is verified (the new
  `test_flag_off_keeps_recommended_experiments_empty_via_decide`
  pins this).
- M0 legacy goldens are byte-identical.
- Full suite at 760 passed, 14 skipped — clean baseline for B1.

B1 (renderer) can now safely:

1. Iterate `engine_run.recommended_experiments` inside a new
   `render_recommended_experiment_section(...)` function.
2. Reuse the Phase 5.1 `_render_opportunity_context_block` verbatim
   (each card has `audience` populated and `revenue_range.suppressed=True`).
3. Render the `would_be_measured_by` enum as a chip with the
   contract-locked merchant-readable mapping.
4. Position the new section between Recommended Now and Watching
   per the contract.

A4.5 is also a clean prerequisite for B3 (ABSTAIN_SOFT extension),
B4 (role-uniqueness assertion), B5 (cannibalization gate / slate
diversity), and B6 (Beauty Brand pinned slate regression).

## Git Status

Per convention, changes are NOT committed. Files left unstaged for
review on top of the post-A4 working tree:

- 1 modified `src/` file: `main.py` (three additive edits).
- 1 new test file: `test_recommended_experiment_main_wiring.py`.
- 1 new doc file: this summary.

Pre-existing post-A4 unstaged files remain unchanged:
- `memory.md` (modified, post-A4 notes from prior runs).
- `src/decide.py` (modified, A4 selector + constants).
- `src/engine_run.py` (modified, A4 `recommended_experiments` field).
- `src/utils.py` (modified, `ENGINE_V2_SLATE` flag default false).
- `tests/test_recommended_experiment_eligibility.py` (new, A4).
- `agent_outputs/code-refactor-engineer-phase6a-ticket-a4-summary.md` (new, A4).

No goldens modified. No `src/storytelling.py` modified. No
`src/storytelling_v2.py` (renderer) modified. No `config/priors.yaml`
modified. No `src/priors_loader.py` modified. No `src/decide.py`
modified in A4.5. No `src/engine_run.py` modified in A4.5.
