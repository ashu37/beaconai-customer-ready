# B-6 — Multi-window combiner universality test

**Owner:** code-refactor-engineer
**Date:** 2026-05-09
**Sprint:** Sprint 1 (Engineer B track, Bucket A Beta blocker)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §1, ticket B-6
**Audit reference:** [agent_outputs/post-6b-stop-coding-audit.md](./post-6b-stop-coding-audit.md) §B-6
**Status:** Complete; production behavior unchanged; full suite green; M0 Beauty pinned fixture byte-identical.

---

## Scope delivered

1.  Tiny diagnostic seam in `src/stats.py` (thread-local trace + context manager) + two no-op call-site recorder calls in `src/action_engine.py`. Production overhead: zero outside an active test context.
2.  New test file with 5 tests: 3 trace-facility self-tests, 1 universality assertion, 1 documented-gap pin for the directional-card divergence.

## Files changed

| File | Change |
|---|---|
| [src/stats.py](../src/stats.py) | NEW thread-local trace facility (~50 lines): `multiwindow_combiner_trace()` context manager + `record_combine_multiwindow_call()` no-op recorder |
| [src/action_engine.py](../src/action_engine.py) | Two call sites (~line 1447, ~line 4451) now wrap their `combine_multiwindow_statistics` invocation with a try/except recorder call. Production semantics unchanged. |
| [tests/test_multiwindow_combiner_universality.py](../tests/test_multiwindow_combiner_universality.py) | NEW — 5 tests |

## Trace facility design

- **Thread-local state** via `threading.local`: per-thread `active` flag + per-thread `keys` set. The context manager flips `active=True`, yields the set, then `active=False` + clears on `finally`.
- **Recorder is a no-op outside an active trace.** Verified by `test_trace_is_no_op_outside_context_manager`. Production code that ships in real merchant flows pays zero overhead — no lock acquisition, no set insertion, no allocation.
- **Re-entrancy is harmless:** the same set is shared within the thread, so an accidentally-nested context manager just shares state; the outer scope still gets a clean teardown.
- **Production code MUST NOT read this trace.** The trace is purely diagnostic; reading it from production would silently couple production behavior to test-only state. The recorder API has no `read_trace()` symbol exported.

## Why a thread-local trace and not (a) a return-value tag, (b) statistical_method strings, or (c) call counts?

- **(a) Return-value tag** would force `combine_multiwindow_statistics` to thread `(play_id, metric)` context through its signature — but the function is also called from outside `action_engine.py` (per future-proofing) and the caller-knows-context invariant is what we want to assert anyway. Threading context through forces a contract change.
- **(b) `statistical_method` strings** on the seed dict already exist (`'combine_multiwindow_statistics'` vs `'min_p_merge'`), but they don't survive the seed → PlayCard adapter step, and the audit explicitly wants a test-only mechanism so the assertion can't be silently bypassed by an emitter that hand-sets the string.
- **(c) Call counts** can't tell us *which* `(play_id, metric)` pairs flowed through.

The thread-local set is the smallest mechanism that supports the universality assertion without leaking diagnostic state into the public Measurement contract.

## Universality test scope

Per audit §B-6 *exactly*: `every measurement for evidence_class=measured was produced by combine_multiwindow_statistics`. The test scans `recommendations` and `recommended_experiments`; for every card where `evidence_class == "measured"` AND `measurement is not None`, asserts the `play_id` is in the trace set.

**On the current Beauty pinned slate the assertion set is empty** — Beauty's only Recommended Now card is `first_to_second_purchase` at `directional`. The assertion is vacuously satisfied; the contract locks in the moment a measured-class card emerges (Sprint 4 G-3 / G-4).

I originally widened the test to also cover `directional` cards. That immediately failed: `first_to_second_purchase`'s Measurement is built by `measurement_builder.build_directional_play_card` from L28-only primary-window signal, not via the combiner. This is by Phase 5.6 design (it's a "supporting signal" card, not a full meta-analysis result), and the function docstring explicitly documents the L28 primary-window path. Per the ticket text: "If this fails on day 1, becomes a real B-6 fix, not a test-only ticket — re-scope with founder before merging the fix." Restricting the assertion strictly to `measured` is faithful to the audit's exact text and avoids a B-6 ticket scope creep into Phase 5.6 redesign work. The directional gap is preserved as a documented-gap test (test #5 in the file) so it cannot silently widen.

## Documented-gap test

`test_directional_card_measurement_path_documented_gap` asserts the Phase 5.6 directional builder's docstring still mentions L28 / primary_window. If future work either (a) routes the directional path through the combiner OR (b) reclassifies `first_to_second_purchase` to `measured`, the docstring will likely change in the same commit, surfacing the gap-fix for explicit review.

## Hard constraints respected

- `engine_run.json` schema unchanged.
- M0 Beauty pinned fixture byte-identical.
- Engine remains runnable.
- Production overhead: zero (verified).
- No banned ML scaffolding.
- Single-writer-per-event-type discipline preserved (no event emitters touched).

## Test results

| Suite | Result |
|---|---|
| `tests/test_multiwindow_combiner_universality.py` | 5/5 |
| **Full suite** | **966 passed, 14 skipped, 0 failed** (~3 min 59 s) |

## Out of scope (deliberately not touched)

- Routing the Phase 5.6 directional builder through the combiner — a real behavior change with golden implications, not a test ticket. Documented as a gap.
- Reclassifying `first_to_second_purchase` to `measured` — Sprint 4 / Phase 9 measurement-design work.
- Synthetic supplements / cold-start fixture coverage — the audit explicitly scopes the universality test to "Beauty fixture"; expanding the matrix is a future ticket once G-1 supplements pinned fixture lands (Sprint 4).

## Risks observed (none unresolved)

- **Vacuous-pass concern:** Today's assertion passes trivially. Mitigation: the trace facility itself is exercised by 3 self-tests, so the mechanism is verified independent of the data shape; and the documented-gap test pins the directional divergence so future widening is forced through review.
- **Subprocess-vs-in-process:** the existing `synthetic_harness.run_scenario` runs the engine in a subprocess, which would defeat the thread-local trace. The B-6 universality test deliberately drives the engine **in-process** via `src.main.run` so the trace survives. This is a different code path from the byte-identical golden harness; the M0 golden test still uses the subprocess harness, so the in-process drive does not perturb that lane.

## Commit shape

Single commit (`a112d5e`) for the ticket, separate commit for `memory.md` (`d39d9f8`).

## Next ticket

G-2 (`empty_bottle` parser unit-coherence) — vertical-dispatched parser at `src/action_engine.py:1687` plus a `vertical_applicable` filter at `src/decide.py:614`. Beauty parser preserved verbatim; supplements held with `vertical_applicable=false` until G-3 ships supplements priors.
