# B-5 — Berkson-class invariant test

**Owner:** code-refactor-engineer
**Date:** 2026-05-09
**Sprint:** Sprint 1 (Engineer B track, Bucket A Beta blocker)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §1, ticket B-5
**Audit reference:** [agent_outputs/post-6b-stop-coding-audit.md](./post-6b-stop-coding-audit.md) §B-5
**Status:** Complete; pure test, no behavior change; full suite green; M0 Beauty pinned fixture byte-identical.

---

## Scope delivered

Single new test file. Zero `src/` edits.

Pins TWO distinct invariants whose joint effect blocks the Berkson confound from re-entering the engine after the 554960d fix.

## Files changed

| File | Change |
|---|---|
| [tests/test_berkson_invariant.py](../tests/test_berkson_invariant.py) | NEW — 5 tests |

## Invariant A — structural cohort-definition rule

For any candidate where audience is a behavioral subset of one window AND outcome is observed in a later, overlapping window, cohort denominator must be defined on **early-half counts only**. The 554960d fix on `calculate_journey_stats_single_window`'s cross-period branch is the canonical implementation.

Two sub-tests exercise this:

1. **`test_journey_stats_returns_none_on_berkson_shaped_input`** — pure-1-order shape (every customer has exactly one whole-period order). Function bails to `None` via the `n>=15` guard at the function head — that's the correct early bail.
2. **`test_journey_stats_handles_mixed_simple_and_complex_journeys_without_collapse`** — mixed shape: 160 simple-journey customers (1 order each, spread across the period) + 40 complex-journey customers (3 orders each, all clustered in early half). The pre-554960d branch could emit `effect_abs ≈ 1.0` here; the test asserts `effect_abs < 0.95` if the function returns a result.

The test does NOT directly inspect the cohort-definition code — that would just duplicate the implementation. It exercises the function with adversarial input and asserts the fixed-behavior contract.

## Invariant B — M4b reclassification contract

`subscription_nudge` and `routine_builder` carry the same Berkson shape today (≥3-SKU survivor cohort and bundle-attach cohort respectively per audit §B-5). M4b's `TARGETING_RECLASSIFY_PLAYS` ships them at `evidence_class=targeting` with `measurement=None` so the fabricated Phase-2 effect constants never reach a rendered card.

Two sub-tests exercise this:

1. **`test_subscription_nudge_and_routine_builder_ship_targeting_with_no_measurement`** — runs Beauty pinned slate end-to-end; for every PlayCard surface (`recommendations`, `recommended_experiments`) where these play_ids appear, asserts `evidence_class == "targeting"` AND `measurement is None`. Considered list is `RejectedPlay`-shaped (no evidence_class field) so the assertion correctly skips it.
2. **`test_subscription_nudge_and_routine_builder_membership_pin`** — defensive pin: both play_ids must remain in `TARGETING_RECLASSIFY_PLAYS`. Per audit §B-5 / §G-4, the right resolution if measurement design later improves is to ship them at `evidence_class=measured` *with a real measurement*, NOT to drop them from the reclassify list while their emitter still emits the Phase 2 `effect_abs=0.05/0.08` constants.

## Self-test

`test_synthetic_subscription_nudge_with_measurement_would_fail` constructs a hand-rolled engine_run dict with a violating `subscription_nudge` card and asserts the structural assertion logic catches it. Pins the failure mode so a future scanner refactor cannot silently weaken detection.

## Hard constraints respected

- No production code touched.
- `engine_run.json` schema unchanged.
- M0 Beauty pinned fixture byte-identical.
- Engine remains runnable.
- No banned ML scaffolding.

## Test results

| Suite | Result |
|---|---|
| `tests/test_berkson_invariant.py` | 5/5 |
| **Full suite** | **961 passed, 14 skipped, 0 failed** (~3 min 49 s) |

## Out of scope (deliberately not touched)

- G-4 redesign (reclassify `subscription_nudge` / `routine_builder` permanently as targeting at the emitter level, not just M4b flag-gated) — Sprint 4 ticket on Engineer B's track. B-5 pins the current contract so G-4's re-pin is defensible.
- Behavior fix to `calculate_journey_stats_single_window` — the 554960d fix is correct; B-5 is the regression test for that fix, not a redo.
- Other Berkson-bait detectors not yet in the engine — the structural test only exercises the one detector currently at risk; new candidate emitters will need their own per-detector tests.

## Risks observed (none unresolved)

- The structural test relies on synthesized DataFrames; a future change to the function's expected input column shape (`Created at`, `customer_id`, `Name`, `Total`) would break the test as a feature, not a bug — the test would fail on input-schema drift, surfacing the contract change.

## Commit shape

Single commit (`6342bc9`) for the ticket, separate commit for `memory.md` (`cb5f172`).

## Next ticket

B-6 (multi-window combiner universality test) — assert every `measurement` block on Beauty pinned slate where `evidence_class=measured` was produced via `combine_multiwindow_statistics`, not min-p merge. Instrument `src/stats.py:334` with a thread-local trace flag readable by the test.
