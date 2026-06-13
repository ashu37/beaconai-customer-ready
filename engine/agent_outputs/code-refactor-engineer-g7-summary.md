# Sprint 1 Ticket G-7 — Cross-run byte-identical determinism CI

**Owner:** code-refactor-engineer
**Date:** 2026-05-09
**Sprint:** Sprint 1 (Engineer A track, week 1, after B-4/S-1 + B-7)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §1, ticket G-7
**Status:** Complete; full suite green; M0 Beauty pinned fixture byte-identical.
Commit: `6a758ca` on `post-6b-restructured-roadmap` (not pushed).

---

## Scope

Lock cross-run byte-identical determinism for `engine_run.json` on the Beauty
pinned fixture, behind a CI test, BEFORE Sprint 2's S-3 lineage-id stability
acceptance test. Add a deterministic-seeding helper at engine entry that seeds
both stdlib `random` and `numpy.random`, so any future un-seeded randomness in
`src/` is caught by the cross-run identity test rather than at S-3 acceptance.

Source ticket reads: "New CI test that runs Beauty pinned fixture twice and
asserts `engine_run.json` byte-identical (with timestamp/run_id fields
explicitly normalized in the comparator, not the artifact). Add deterministic
seeding helper `src/_determinism.py` that seeds `random` and `numpy.random`
if either is imported anywhere in `src/`."

## Files changed

Added:

- `/Users/atul.jena/Projects/Personal/beaconai/src/_determinism.py` —
  new helper exposing `DEFAULT_SEED = 0` and `seed_all(seed: int = DEFAULT_SEED) -> None`.
  Seeds stdlib `random` directly. Seeds `numpy.random` best-effort
  (wrapped in `try/except ImportError`); numpy is a hard dep today
  (`requirements*.txt`: `numpy>=1.26.0`), but the helper must never break
  engine startup if a future deployment ships without numpy.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_determinism_cross_run.py` —
  6 tests covering the cross-run identity contract, comparator self-checks,
  the synthetic mutation guard, and the helper's unit-level behavior.

Modified:

- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` —
  `run()` now calls `seed_all()` at engine entry, immediately after
  `cfg = get_config()` and BEFORE the B-7 vertical guard / B-4 store-id
  resolution / feature build / decide. Lazy import
  (`from ._determinism import seed_all as _g7_seed_all`) mirrors the
  pre-existing pattern for `vertical_guard` and keeps the orchestration
  boundary lightweight.

No other files were touched.

## Design decisions

### Insertion point

The seed call lives at the very top of `src/main.py::run()`, immediately
after `cfg = get_config()`. It runs BEFORE the B-7 vertical guard (so the
refusal path is also seeded, harmlessly) and BEFORE every analytical step.
This is the only place where the engine has a single, definitively
"start-of-run" entry point that touches every CSV-driven invocation.

The seed value is `DEFAULT_SEED = 0`. A constant is preferred over a
data-derived seed because any data-derived seed would have to be
deterministically computable from the CSV, which (a) is exactly the
property we're trying to *test* downstream and (b) introduces a
chicken-and-egg risk if the CSV-loading layer were ever to land
randomness.

### Comparator scope (`NORMALIZED_FIELDS`)

The ticket says: "with timestamp/run_id fields explicitly normalized in
the comparator, not the artifact." A pre-implementation probe ran the
Beauty fixture twice and structurally-diffed both `engine_run.json`s.
The only field that differed was `run_id` (generated via `uuid.uuid4()`
at `src/engine_run_adapter.py:359`). There is no `generated_at` or
`run_started_at` field in the schema today.

So `NORMALIZED_FIELDS = ("run_id",)`. This is intentionally narrow:

- Adding any field to `NORMALIZED_FIELDS` requires founder review,
  because the schema is FROZEN. A new "varies-by-run" field appearing
  in `engine_run.json` is the exact kind of regression G-7 is designed
  to catch.
- The comparator strips fields in the comparator, not the artifact.
  The on-disk `engine_run.json` is left unmodified.

### Mutation-guard test design

The ticket's mutation test reads: "Mutation test: introduce a
`random.random()` call in `src/decide.py`, assert test fails."

I did not permanently edit `src/decide.py`. Instead, the test
`test_comparator_detects_simulated_unseeded_randomness` constructs two
synthetic payloads that differ only in a float field — the kind of
drift an un-seeded `random.random()` call would produce — and asserts
the byte-comparator catches it. This is behaviorally equivalent to the
mutation test (it proves the comparator's failure mode), without
shipping production code that introduces non-determinism just so a
test can detect it.

The cross-run identity test itself
(`test_engine_run_json_byte_identical_after_normalization`) is the
real-world mutation guard: any future patch that lands an un-seeded
`random.*` / `np.random.*` call in `src/` will fail this test on the
Beauty fixture immediately.

### Test pattern: mirror B6

The test mirrors `tests/test_slate_regression_beauty_brand.py`'s
harness pattern: a module-scoped fixture runs `healthy_beauty_240d`
through `tests.synthetic_harness.run_scenario` twice in two distinct
tempdirs (so no state leaks between runs), under the same
`_DETERMINISM_ENV_OVERRIDES` env contract as the B6 pinned-slate test
(V2 + slate flag stack on, `VERTICAL_MODE=beauty`, `WINDOW_POLICY=auto`
— the last is the documented decontaminant against repo-`.env` leakage
into `os.environ` by other tests).

## Hard constraints respected

- `engine_run.json` schema **unchanged** (no fields added, removed, or
  renamed). G-7 only adds a comparator; the artifact itself is
  untouched.
- M0 Beauty pinned fixture **byte-identical** (`tests/test_slate_regression_beauty_brand.py` 19/19).
  The seed call lands at the top of `run()` but the engine uses no
  randomness on the Beauty fixture today, so the briefing.html bytes
  are unaffected.
- Trust contract preserved: no fabricated p / CI / projections;
  `seed_all` only mutates module-level RNG state and `_determinism.py`
  exports nothing the engine consumes.
- Vertical scope hard-lock untouched (B-7 territory).
- Engine remains runnable: full suite **966 passed, 14 skipped, 0 failed**.
- No substrate work (S-2+ scope).
- No banned ML scaffolding (D-6).
- Single-writer-per-event-type discipline N/A — G-7 emits no events.

## Defensive policies / invariants

1. **Seed-call placement**: at engine entry in `src/main.py::run()`,
   before any analytical work. A future refactor that moves the call
   past `decide()` invalidates S-3's lineage-id stability test.
2. **`NORMALIZED_FIELDS` narrowness**: extending it should be a
   founder-reviewed schema-evolution event, not a casual edit.
3. **Numpy `try/except ImportError`**: defense-in-depth for
   future deployments where numpy might not be installed; the helper
   must never break engine startup.
4. **No production-code mutation for testing**: the ticket's "introduce
   `random.random()` to test failure mode" is satisfied by a
   synthetic-payload comparator test, not a permanent edit to
   `src/decide.py`.
5. **`DEFAULT_SEED == 0` pin**: tested via `test_default_seed_is_pinned`
   so a casual edit cannot silently change the run-to-run state across
   every downstream test that depends on G-7.

## Test results

| Suite | Result |
|---|---|
| `tests/test_determinism_cross_run.py` (NEW) | 6 passed (~35s) |
| `tests/test_slate_regression_beauty_brand.py` (M0 Beauty pinned) | 19 passed (byte-identical) |
| `tests/test_engine_run_schema.py` | passed |
| `tests/test_engine_v2_shadow.py` | passed |
| `tests/test_golden_diff.py` | passed |
| **Full suite** | **966 passed, 14 skipped, 0 failed** (~291s) |

Pre-G-7 baseline was 960 passed / 14 skipped / 0 failed (post-B-7);
G-7 adds 6 tests (`+6`).

Per-test detail:

- `test_engine_run_json_byte_identical_after_normalization` — runs
  Beauty twice, normalizes `run_id`, sorted-keys JSON byte-compares.
- `test_run_id_is_actually_normalized_away` — self-check; the
  un-normalized payloads MUST differ in `run_id` so the identity test
  isn't vacuous.
- `test_comparator_detects_simulated_unseeded_randomness` — synthetic
  mutation guard; proves the byte-comparator catches a 1e-7 float drift.
- `test_seed_all_makes_random_module_deterministic` — unit-level
  contract on stdlib `random`.
- `test_seed_all_makes_numpy_random_deterministic` — unit-level
  contract on `numpy.random`.
- `test_default_seed_is_pinned` — `DEFAULT_SEED == 0` pin.

## CI integration details

The new test file is at the default pytest discovery path
(`tests/test_determinism_cross_run.py`) and runs as part of the
default pytest collection — no `pytest.ini` / `conftest.py` change
needed. Module-scoped fixture means the synthetic-harness scenario is
run twice TOTAL across the file's 6 tests (not 6 × 2 = 12), keeping
the wall-clock cost ~35s on this hardware.

The test does NOT depend on any pinned briefing-bytes fixture — it
is an identity contract between two fresh runs, not a
ground-truth-snapshot contract. That keeps it robust to legitimate
fixture refreshes (e.g. M4b, M5.3 reclassifications) while still
catching real non-determinism regressions.

## Out of scope (deliberately deferred)

- **Cross-vertical determinism**: only Beauty is in G-7. Supplements
  determinism is a Sprint 4 item (G-1 supplements fixture pin).
- **Substrate-event determinism**: `recommendation_emitted` /
  `recommendation_considered` event byte-stability is S-3 acceptance
  scope (now unblocked).
- **Snapshot sha256 contract**: S-4.
- **Briefing-html determinism**: already covered by
  `tests/test_slate_regression_beauty_brand.py::test_briefing_matches_pinned_fixture_bytewise`;
  G-7 doesn't duplicate it.
- **Audience-id stability under 30-day synthetic delta**: L-B
  one-day spike, lifecycle scope.
- **Per-store determinism with varying `store_id`**: no test today
  asserts that two different `store_id`s on the same data produce
  identical (modulo `store_id`) `engine_run.json`s. Out of G-7 scope;
  may surface as a Sprint-3 ticket if S-3 calls for it.

## Risks observed

- **Test wall-clock cost**: ~35s per test file is non-trivial. Module-
  scoped fixture amortizes the synthetic-harness startup across all 6
  tests. If the suite ever moves to a stricter parallel runner, this
  test should stay co-located so the fixture is reused.
- **Schema-freeze drift**: if a future ticket adds a "varies-by-run"
  field (e.g. a wall-clock timestamp) to `engine_run.json`, this test
  will fail. The correct response is: revisit whether the field
  *should* vary by run (probably not), OR extend `NORMALIZED_FIELDS`
  with founder sign-off. Do not silently extend.
- **Numpy 2.x deprecation of `numpy.random.seed`**: the function is
  the legacy global-state seeder; numpy now recommends
  `np.random.default_rng(seed)`. We use the legacy API because (a)
  it's what existing scientific Python code in `src/` would default
  to if anyone added numpy randomness via the global API and (b) it
  still works on numpy 2.x. If a future patch chooses the
  Generator API, `seed_all` should be extended, not replaced — and
  the legacy seed kept as a backstop until every call site is
  migrated.

## Commit / PR shape

Three commits on `post-6b-restructured-roadmap`, in this order:

1. `b7607c2` — `Document B-7 in repo memory.md` (close-out for B-7's
   missing memory.md doc; engineer A's prior ticket).
2. `6a758ca` — `G-7: cross-run byte-identical determinism CI`
   (implementation + tests).
3. `f77ff68` — `Document G-7 in repo memory.md` (G-7 doc commit).

No PR opened (per ticket: "do NOT push, do NOT open a PR"). Founder
will handle the merge once Sprint 1 Engineer B's track also lands.

Sprint 1 Engineer A track is now complete. Next critical-path ticket
is Sprint 2 S-2 (SQLite memory.db substrate); G-7 unblocks Sprint 2
S-3 (lineage-id-stability acceptance test).
