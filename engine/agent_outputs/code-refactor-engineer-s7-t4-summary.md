# S7-T4 Summary — 4-state abstain mode migration

**Ticket:** S7-T4
**Date:** 2026-05-20
**Status:** Closed (impl + B + C all landed; T4.5 flag flip + atomic re-pin separate)

## Scope

Migrate `AbstainMode` from 2-state (S7.5-T3: `SOFT_AWAITING_MEASUREMENT` + `SOFT_PRIOR_UNVALIDATED`) to 4-state by adding `SOFT_BELOW_FLOOR` + `SOFT_AUDIENCE_TOO_SMALL`. Refactor `_compute_abstain_mode` to majority-with-tiebreak precedence per DS architect Gap F verdict (2026-05-20). Pure contract evolution within event_version=1. No builder code, no flag flip on builders, renderer untouched (Stop-Coding adjacency per D-S6.5-20).

## DS-locked Gap F precedence rule (2026-05-20)

1. If `state == ABSTAIN_HARD` → `mode = None` (data-quality flags own this).
2. If considered is empty AND `state == ABSTAIN_SOFT` → `SOFT_AWAITING_MEASUREMENT`.
3. Count reason codes **EXCLUDING** `TARGETING_HELD_UNDER_ABSTAIN` (synthesized by the ABSTAIN_SOFT path; self-contamination guard per DS missed-edge finding).
4. If a single reason class (`PRIOR_UNVALIDATED`, `MATERIALITY_BELOW_FLOOR`, or `AUDIENCE_TOO_SMALL`) is ≥60% of typed Considered entries → that mode.
5. If no class hits 60% but `PRIOR_UNVALIDATED` is present at ≥30% → `SOFT_PRIOR_UNVALIDATED` (strength tiebreak).
6. Else → `SOFT_AWAITING_MEASUREMENT` (catch-all).

## Files changed

- `src/engine_run.py` (`AbstainMode`: +2 values, additive event_version=1)
- `src/decide.py` (`_compute_abstain_mode`: refactor to majority-with-tiebreak; TARGETING_HELD_UNDER_ABSTAIN exclusion centralized)
- `tests/test_s7_t4_abstain_4state.py` (NEW: 20+ tests)

## Flag posture

`ENGINE_V2_ABSTAIN_4STATE` default OFF at T4. T4.5 owns the atomic flag flip + fixture re-pin per Sprint 2 Risk #4 discipline. Per S7.5-T3 precedent (Abstain.mode shipped silent at S7.5; surface activation later), the 4-state semantic mode lands behind a flag but renderer continues to read `state` not `mode` per D-S6.5-20 Stop-Coding adjacency. Mode is contract surface, not renderer surface, until later sprint flips.

## Test coverage

- All 6 precedence branches (HARD → None, empty Considered → AWAITING, single-class ≥60% per class type, ≥30% PRIOR strength tiebreak, catch-all).
- 4 DS-flagged missed edges:
  - `ABSTAIN_HARD` returns `None` (data-quality owns)
  - Empty Considered + `ABSTAIN_SOFT` routes to `SOFT_AWAITING_MEASUREMENT` (not `None`)
  - Mixed reason sets with only non-mode-driving codes (e.g., `WINDOW_DISAGREEMENT`, `NO_MEASURED_SIGNAL`) → `SOFT_AWAITING_MEASUREMENT`
  - `TARGETING_HELD_UNDER_ABSTAIN` excluded from mode-driving count (self-contamination guard)
- Backwards compat: any existing test asserting `SOFT_PRIOR_UNVALIDATED` or `SOFT_AWAITING_MEASUREMENT` under S7.5-T3 semantics passes under the 4-state refinement.
- AbstainMode round-trip clean for all 4 values.

## Behavior changes

- **Flag OFF (default):** legacy 2-state mapping preserved byte-for-byte. Pinned fixtures byte-identical.
- **Flag ON (T4.5 will flip):** 4-state typed mode lands at the `Abstain.mode` slot on engine_run.json. Renderer untouched at T4 — surface activation is a later-sprint concern.

## Out of scope (per IM plan + DS verdict)

- Renderer changes (state vs mode reading is Stop-Coding adjacent)
- Builder code (T4 is pure contract evolution)
- Legacy `ABSTAIN_SOFT` alias deletion (S10 per IM plan)
- Flag flip + fixture re-pin (S7-T4.5)
- 30+ legacy `ABSTAIN_SOFT` call sites — they reference `state` not `mode`; no migration needed (additive at mode slot, state-stable)

## Commit chain

- Commit A `a6bcef8` — impl + tests (612 insertions / 15 deletions across 2 files; new test file 1)
- Commit B `<this commit>` — memory.md S7-T4 closeout entry
- Commit C `<next commit>` — this summary file

## Dispatch context

T4 agent (afid `aac9a413bf3d5bd63`) wrote impl + tests but the bash sandbox blocked both pytest invocation and git commits, requiring founder verification + commit assist. Memory.md entry + this summary authored by orchestrator from agent's final report. T4 agent guidance preserved verbatim in the test file docstring.

## Follow-up

- **S7-T4.5:** atomic flag flip on `ENGINE_V2_ABSTAIN_4STATE` + fixture re-pin if any fixture's `Abstain.mode` slot moves under flag-ON. Renderer migration to mode-aware copy is a different sprint (Stop-Coding adjacency at D-S6.5-20).
- **S10:** legacy `ABSTAIN_SOFT` alias deletion (one sprint cushion past T4.5).

## Backfill from memory.md (migration trim 2026-05-25)

## S7-T4 closeout — 4-state abstain mode migration (2026-05-20)

**Shipped:**
- AbstainMode enum gains SOFT_BELOW_FLOOR + SOFT_AUDIENCE_TOO_SMALL
  (additive event_version=1 per S7.5-T3 precedent). Total 4 values.
- `_compute_abstain_mode` refactored to majority-with-tiebreak rule per
  DS architect Gap F verdict (2026-05-20). 6-branch precedence walks
  Considered cards, excludes TARGETING_HELD_UNDER_ABSTAIN from count
  (self-contamination guard per DS missed-edge finding), routes
  single-class ≥60% to that mode, falls back to PRIOR_UNVALIDATED
  strength-tiebreak at ≥30%, else SOFT_AWAITING_MEASUREMENT catch-all.
- ENGINE_V2_ABSTAIN_4STATE flag default OFF. Renderer continues to read
  `state` not `mode` per D-S6.5-20 Stop-Coding adjacency; mode is
  contract surface, not renderer surface, until later sprint flips.
- 20+ new tests covering all 6 precedence branches + 4 DS-flagged missed
  edges (ABSTAIN_HARD→None, empty Considered→AWAITING_MEASUREMENT,
  mixed non-mode-driving codes→AWAITING_MEASUREMENT, self-contamination
  guard) + backwards compat with S7.5-T3 2-state semantics.

**Load-bearing invariants:**
- Flag OFF: 2-state legacy semantics preserved byte-for-byte. Any
  existing test asserting SOFT_AWAITING_MEASUREMENT or
  SOFT_PRIOR_UNVALIDATED continues to pass.
- Flag ON: TARGETING_HELD_UNDER_ABSTAIN MUST be excluded from the
  mode-driving reason count — it's synthesized by the ABSTAIN_SOFT path
  itself and would self-pollute the precedence walk.
- ABSTAIN_HARD always returns mode=None. Data-quality flags own this
  state; never typed-tag.

**Caveats / dormant behavior:** mode slot is dormant on every pinned
fixture today (renderer reads state). Surface activation lands at later
sprint when renderer migrates to mode-aware copy.

**Schema:** event_version=1 additive (2 new AbstainMode enum values).
**Suite:** 1565+ passed (was 1497 before S7-priors-wiring + S7-T2; T4
adds 20+ tests).
**Summary:** [agent_outputs/code-refactor-engineer-s7-t4-summary.md](agent_outputs/code-refactor-engineer-s7-t4-summary.md)
