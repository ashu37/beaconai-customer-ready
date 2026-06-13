# Code Refactor Engineer — Phase 6A Ticket B4 Summary

_Date: 2026-05-05_
_Branch: `engine-rework`_
_Baseline commit: `c322453` (post-B3)_
_Scope: Phase 6A Ticket B4 ONLY from `agent_outputs/implementation-manager-campaign-slate-plan.md`._

## Approved Scope

Add a defensive structural assertion in `src/decide.py` that no
`play_id` appears in more than one role section of a single
`EngineRun`. The minimum required invariant per the ticket is:

- `recommendations` x `recommended_experiments` MUST be disjoint.

The ticket also asked for broader enforcement (also disjoint vs
`considered`) "if safe and simple." I confirmed it is safe today
because the existing decide-layer pipeline already produces this
property:

- `assemble_considered(..., recommended_play_ids=...)` excludes
  `recommendations` play_ids from `considered`.
- `populate_considered_from_candidates` (upstream) skips play_ids
  already in `recommendations` or `considered`.
- The Recommended Experiment selector (Ticket A4) excludes any
  play_id already in `recommendations`.
- The B3 ABSTAIN_SOFT routing dedupes against pre-existing
  `considered` AND the regular Fix 3 head-routing list.
- Both abstain branches force `recommendations=[]` AND
  `recommended_experiments=[]`.

So I implemented the **broader** form (recommendations /
recommended_experiments / considered all pairwise-disjoint) with one
unified helper and one unified error message that names every
offending overlap.

Out of scope and untouched: selector eligibility rules, renderer,
priors metadata, PlayCard schema, ABSTAIN_SOFT routing, materiality
floors, `revenue_range` suppression, lifecycle, legacy renderer,
goldens.

## Patch Summary

1. **`src/decide.py`** — additive only:
   - New helper `_assert_role_uniqueness(engine_run)` placed
     immediately above `decide()`. Raises `AssertionError` with a
     human-readable message naming every duplicate `play_id` and the
     pair of role sections it appears in.
   - The helper checks all three pairwise overlaps:
     - `recommendations` vs `recommended_experiments`
     - `recommendations` vs `considered`
     - `recommended_experiments` vs `considered`
   - Watching is intentionally NOT checked: it is a metric track keyed
     on metric name, not a play track keyed on `play_id`.
   - The helper is invoked at the end of `decide()` on every return
     path: ABSTAIN_HARD, ABSTAIN_SOFT, and PUBLISH. Each return path
     was refactored from `return replace(...)` to
     `out = replace(...); _assert_role_uniqueness(out); return out`.
   - The helper is module-private (single-leading-underscore). It is
     not exported via `__all__`. Callers should use `decide()`; tests
     import the helper directly by name.

2. **`tests/test_role_uniqueness_invariant.py` (NEW)** — 13 tests:
   - 5 direct-helper tests (3 raise + 2 negative controls).
   - 1 PUBLISH integration test (full `decide()` call, full assertion).
   - 2 PUBLISH disjointness tests (rec vs experiments; experiments vs
     considered).
   - 1 ABSTAIN_SOFT integration test (B3 routing path).
   - 1 ABSTAIN_HARD integration test (memo path).
   - 2 assertion-message-quality tests (multiple duplicates listed;
     message is actionable and names play_id + role names).
   - 1 flag-off test (`ENGINE_V2_SLATE=false` invariant still holds).

No other files were modified. No `src/storytelling.py`, no
`src/storytelling_v2.py`, no `src/main.py`, no `src/engine_run.py`,
no `src/utils.py`, no `config/priors.yaml`, no `src/priors_loader.py`,
no goldens, no fixtures.

## Files Changed

- `/Users/atul.jena/Projects/Personal/beaconai/src/decide.py`
  - Added `_assert_role_uniqueness(engine_run)` helper (~line 1199).
  - Refactored ABSTAIN_HARD return site to call the helper before
    returning.
  - Refactored ABSTAIN_SOFT return site to call the helper before
    returning.
  - Refactored PUBLISH return site to call the helper before
    returning.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_role_uniqueness_invariant.py` (NEW)
  - 13 tests pinning the role-uniqueness invariant: helper directly,
    `decide()` end-to-end on PUBLISH / ABSTAIN_SOFT / ABSTAIN_HARD,
    flag-off, and assertion-message quality.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6a-ticket-b4-summary.md` (NEW)
  - This summary.

## Invariant Scope Implemented

Broader enforcement (the optional/expanded form per Ticket B4
implementation guidance):

- `recommendations` x `recommended_experiments` MUST be disjoint.
- `recommendations` x `considered` MUST be disjoint.
- `recommended_experiments` x `considered` MUST be disjoint.

Watching is intentionally NOT checked. It is a metric track, not a
play track; metric names and play_ids are different identifier
spaces.

The helper is invoked at the END of `decide()` on every return path,
so the invariant is enforced on the post-dedupe, post-cap, post-
assemble EngineRun that is actually returned to the caller. This
matches the ticket guidance "If duplicate considered entries are
already deduped before this point, assert against the post-dedupe
returned EngineRun."

## Assertion Location

`src/decide.py`:

- Helper definition: just above the `decide()` entry point (~line 1199),
  in a clearly-commented section.
- Invocation sites: each of the three `return` paths inside `decide()`:
  - ABSTAIN_HARD (`if state == DecisionState.ABSTAIN_HARD: ... return`)
  - ABSTAIN_SOFT (`if state == DecisionState.ABSTAIN_SOFT: ... return`)
  - PUBLISH (the fall-through path at end of function)

The helper itself is pure (no I/O, no mutation, no side-effects) and
is therefore safe to call from arbitrary contexts; tests exercise it
directly on synthesized EngineRuns to pin the contract independently
of `decide()`.

## Duplicate Role Behavior

When the invariant is violated:

- `AssertionError` is raised inside `decide()` (or
  `_assert_role_uniqueness` if called directly).
- The message format is:

  ```
  Role-uniqueness invariant violated (Phase 6A Ticket B4): the same
  play_id MUST NOT appear in more than one visible role section of an
  EngineRun. Offending overlaps: <pair-1>: <play_ids>; <pair-2>:
  <play_ids>; ...
  ```

- Every overlapping pair is listed with the play_ids sorted for
  determinism.
- Empty role lists / `None` lists are treated as empty (helper does
  not raise on them).

Tests pin:
- Single-pair overlap (rec x experiments) raises and names both roles
  + the play_id.
- Multi-pair overlap raises and names every offending pair.
- Multiple duplicates in the same pair are all listed.
- The message contains the literal play_id, the literal role names,
  and is at least 20 characters long (sanity floor on terseness).

## PUBLISH / ABSTAIN_SOFT / ABSTAIN_HARD Regression Results

PUBLISH path:
- Existing eligibility filter (Ticket A4) excludes any allowlisted
  play_id from the experiment list when it is already in
  `recommendations`.
- `assemble_considered(..., recommended_play_ids=...)` excludes
  `recommendations` play_ids from `considered`.
- Existing test
  `test_decide_publish_path_passes_role_uniqueness` confirms the
  assertion does NOT fire on a normal PUBLISH run with one measured
  card and two experiment candidates.
- All 34 `tests/test_decide.py` PUBLISH tests pass unchanged.
- All 22 `tests/test_recommended_experiment_eligibility.py` tests pass
  unchanged.
- Goldens pass byte-identical.

ABSTAIN_SOFT path:
- B3 routing (publish-shadow plus dedupe-against-pre-existing-
  considered-and-fix3-held) already produces a disjoint set; the
  assertion does NOT fire.
- `recommendations` and `recommended_experiments` are both forced to
  `[]`, so the only nontrivial overlap to check is "is a held
  experiment play_id ALSO somewhere it shouldn't be?" — answer: no,
  by B3's dedupe layer.
- All 14 `tests/test_abstain_soft_no_experiments.py` tests pass
  unchanged.

ABSTAIN_HARD path:
- `recommendations` and `recommended_experiments` are both forced to
  `[]`. Only `considered` is non-empty (DATA_QUALITY_FLAG synthesized
  entries plus pre-existing rejections). Trivially passes the
  invariant.
- The data-quality memo path is unchanged.

## Goldens

`tests/test_golden_diff.py` -> **3 passed, 0 re-baselined**.

M0 legacy goldens (`tests/golden/{small_sm, mid_shopify,
micro_coldstart}/*`) are byte-identical. The B4 patch adds an
assertion that fires only on a structurally illegal EngineRun; under
all legitimate inputs the assertion is silent and observable behavior
is unchanged.

## Exact Commands Run

```bash
# Red-first capture (BEFORE the helper landed)
python -m pytest tests/test_role_uniqueness_invariant.py -v
# -> 1 collection error: ImportError: cannot import name
#    '_assert_role_uniqueness' from 'src.decide'.
#    All 13 tests blocked; none collected.

# Green (AFTER the helper landed)
python -m pytest tests/test_role_uniqueness_invariant.py -v
# -> 13 passed in 0.10s

# B-series + decide regressions
python -m pytest tests/test_abstain_soft_no_experiments.py \
                 tests/test_recommended_experiment_eligibility.py \
                 tests/test_decide.py -v
# -> 70 passed (14 + 22 + 34) in 0.43s

# Goldens (no re-baseline)
python -m pytest tests/test_golden_diff.py -v
# -> 3 passed in 27.01s

# Combined ticket-specified suites
python -m pytest tests/test_role_uniqueness_invariant.py \
                 tests/test_abstain_soft_no_experiments.py \
                 tests/test_recommended_experiment_eligibility.py \
                 tests/test_decide.py \
                 tests/test_golden_diff.py -q
# -> 86 passed in 28.60s

# Full suite
python -m pytest tests/ -q
# -> 855 passed, 14 skipped, 0 failed in 118.34s
```

## Tests / Checks Run

| Check | Result | Notes |
|---|---|---|
| `tests/test_role_uniqueness_invariant.py` (NEW) | **13 passed** | Red-first ImportError captured before any source change |
| `tests/test_abstain_soft_no_experiments.py` | 14 passed | B3 contract intact |
| `tests/test_recommended_experiment_eligibility.py` | 22 passed | A4 contract intact |
| `tests/test_decide.py` | 34 passed | M7 contract intact |
| `tests/test_golden_diff.py` | **3 passed (no re-baseline)** | M0 byte-identical |
| Full suite `pytest tests/ -q` | **855 passed, 14 skipped, 0 failed** | Pre-B4 baseline 842 passed; +13 = exactly the new test file |

## Did The New Tests FAIL Before The Fix?

**Yes — red-first evidence captured.** Before adding the helper to
`src/decide.py`, running
`python -m pytest tests/test_role_uniqueness_invariant.py -v` produced
a collection error:

```
ERROR collecting tests/test_role_uniqueness_invariant.py
ImportError while importing test module 'tests/test_role_uniqueness_invariant.py'.
...
E   ImportError: cannot import name '_assert_role_uniqueness' from 'src.decide'
=========================== short test summary info ============================
ERROR tests/test_role_uniqueness_invariant.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.06s ===============================
```

After the helper landed and the call sites were wired into the three
`decide()` return paths, all 13 tests passed on first run. The
red-first ImportError is the strongest possible failure signal: the
test module could not even be loaded until the contract was honored.

## Behavior Changes

Under all flag combinations and decision states tested today, the
observable EngineRun output is unchanged. The assertion is silent on
every legitimate input. It only fires when a future code path
violates the invariant — i.e., when a `play_id` would have appeared
in two role sections in a single rendered briefing.

The exception of an actual violation would be a hard failure of
`decide()` (an `AssertionError` propagates out of the function). This
is the intended forcing function: the engineer who introduces such a
regression sees a clear, actionable error message rather than a
silently mis-rendered briefing.

`receipts/engine_run.json` payloads are unchanged. Renderer output is
unchanged. Goldens are byte-identical.

## Confirmation A1 + A2 + A3 + A4 + A4.5 + B1 + B1.5 + B2 + B3 Behavior Is Intact

- `src/storytelling_v2.py` not modified — B1/B1.5/B2 contracts intact.
- `src/engine_run.py` not modified — A2/A4 schema contracts intact.
- `src/main.py` not modified — A4.5 wiring intact.
- `src/utils.py` not modified — `ENGINE_V2_SLATE` flag default unchanged.
- `config/priors.yaml` not modified — A3 metadata intact.
- `src/priors_loader.py` not modified — A3 loader intact.
- `_select_recommended_experiments(...)` not modified — A4/B3
  selector + publish_shadow contract intact.
- The B3 ABSTAIN_SOFT routing block in `decide()` is unchanged in
  behavior; only its return statement was refactored from
  `return replace(...)` to a two-line `out = replace(...);
  _assert_role_uniqueness(out); return out`.

## Artifacts Added

- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_role_uniqueness_invariant.py`
  — 13 tests pinning the role-uniqueness invariant.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-phase6a-ticket-b4-summary.md`
  — this summary.

No new sample HTML / receipts / docs / fixtures. No goldens modified.

## Remaining Risks

1. **Watching not checked.** Watching is a metric track keyed on
   metric name, not a play track. A future change that makes Watching
   keyed on play_id would need to extend `_assert_role_uniqueness` to
   include it. Documented in the helper's docstring.
2. **Helper is private.** `_assert_role_uniqueness` is not exported
   via `__all__`. A future refactor that wants to call it from
   another module would need to either promote it to public or
   import it via the underscore name. Tests already import via the
   underscore name.
3. **Custom EngineRun construction outside `decide()`.** If a future
   caller bypasses `decide()` and hand-builds an EngineRun, the
   invariant is not enforced. The helper is callable directly so a
   tightening can land later (e.g., in `engine_run_adapter` or in
   `EngineRun.__post_init__`). Not in scope for B4.
4. **Cross-run uniqueness.** This is single-run only. A play that
   appears in `recommendations` in run N and in `considered` in run
   N+1 is allowed; that is the whole point of recently-run-fatigue
   (Phase 6B+).
5. **Renderer-side dedup is unaffected.** The renderer already
   iterates the EngineRun lists as-given; a violation would show up
   visually as the same card in two sections. The B4 assertion is
   the engine-side forcing function so the renderer never has to
   make this decision.
6. **Performance.** The helper is O(R + E + C) on a single EngineRun.
   With current caps (R=3, E=2, C=6) the work is trivial. No timing
   concerns.

## Readiness for Phase 6A Ticket B5

**Ready for Ticket B5 (cannibalization gate hardening + slate
diversity assertion).**

B4 establishes the structural assertion that B5's pinned tests can
rely on as a forcing function: any cannibalization-gate or
slate-diversity regression that promotes a play to two role sections
will hit the B4 assertion before it hits B5's pinned tests. This is
the "defensive net" the B5 ticket can build on top of.

Clean baseline for B5:
- Role-uniqueness assertion live on every `decide()` return path.
- Full suite at 855 passed, 14 skipped.
- Goldens byte-identical, no re-baseline.
- A4 / B3 selector + ABSTAIN_SOFT contracts intact.

## Git Status

Per convention, changes are NOT committed. Files left unstaged on top
of the post-c322453 working tree:

- 1 modified `src/` file: `decide.py` (helper + 3 return-path
  refactors).
- 1 new test file: `test_role_uniqueness_invariant.py`.
- 1 new doc file: this summary.

No goldens modified. No `src/storytelling.py` modified. No
`src/storytelling_v2.py` modified. No `src/main.py` modified. No
`src/engine_run.py` modified. No `src/utils.py` modified. No
`config/priors.yaml` modified. No `src/priors_loader.py` modified.
