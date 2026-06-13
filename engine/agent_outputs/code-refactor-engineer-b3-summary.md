# B-3 — Hardcoded-fallback regression test

**Owner:** code-refactor-engineer
**Date:** 2026-05-09
**Sprint:** Sprint 1 (Engineer B track, Bucket A Beta blocker)
**Source contract:** [agent_outputs/implementation-manager-post-6b-restructured-plan.md](./implementation-manager-post-6b-restructured-plan.md) §1, ticket B-3
**Audit reference:** [agent_outputs/post-6b-stop-coding-audit.md](./post-6b-stop-coding-audit.md) §B-3
**Status:** Complete; pure test, no behavior change; full suite green; M0 Beauty pinned fixture byte-identical.

---

## Scope delivered

Single new test file. Zero `src/` edits.

Pins the trust-contract surface: a Phase 2 fallback constant (`effect=0.05`, `effect=0.08`, `effect=0.10`, `p=0.05`, etc.) leaking into rendered `engine_run.json` on a structurally-at-risk play is a CI failure, not a silent regression.

## Files changed

| File | Change |
|---|---|
| [tests/test_no_hardcoded_fallbacks_in_payload.py](../tests/test_no_hardcoded_fallbacks_in_payload.py) | NEW — 6 tests |

No production code touched.

## Risk set

`TARGETING_RECLASSIFY_PLAYS` (the M4b reclassify list) plus a defensive `empty_bottle` membership guard:

- `subscription_nudge` (`effect=0.05` per audit)
- `routine_builder` (`effect=0.08` per audit)
- `empty_bottle` (`effect=0.10`, `p=0.05/0.06` per audit)
- `category_expansion`
- `bestseller_amplify`
- `vip_no_discount_nurture`
- `replenishment_reminder`

Scoping the assertion to the risk set (rather than every PlayCard) keeps false positives manageable: a legitimately-computed `effect_abs == 0.05` on `first_to_second_purchase` (wired through the real M3 + multiwindow combiner path) does NOT trip the test. Only at-risk plays do.

## Forbidden constants

`{0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.15, 0.20, 0.30, 0.40}` — the verbatim list from the audit. Tolerance: `1e-9` (the audit's constants are all 2-3 sigfigs so exact-equality with float-round tolerance is safe).

## Fields scanned

For each at-risk PlayCard's `measurement` block:

- `effect_abs` — legacy serialization field name
- `observed_effect` — public `Measurement` dataclass field name
- `p_internal` — internal p-value (never rendered to merchant; persisted for ML-readiness)

`measurement is None` (the targeting-class case after Phase 4.2 / G-4 reclassification) is clean by construction and the scanner correctly returns zero violations for it.

## Surfaces scanned

`recommendations` + `recommended_experiments` + `considered`. The `considered` list is `RejectedPlay`-shaped and does not currently carry a typed `measurement` block — the scan iterates anyway to future-proof against any later contract evolution that adds one.

## Tests

| # | Test | Purpose |
|---|---|---|
| 1 | `test_risk_set_membership_pin` | Defensive: forces founder-level review if the at-risk set is tightened |
| 2 | `test_no_hardcoded_fallbacks_on_beauty_pinned_slate` | Beauty fixture: zero violations (current state) |
| 3 | `test_no_hardcoded_fallbacks_on_synthetic_supplements_run` | Supplements synthetic: zero violations (current state) |
| 4 | `test_scanner_self_test_detects_forbidden_constant` | Scanner positive-detect on a synthetic at-risk card |
| 5 | `test_scanner_self_test_ignores_non_risk_play` | Scanner negative on `first_to_second_purchase` with `effect_abs=0.05` |
| 6 | `test_scanner_self_test_ignores_missing_measurement` | Scanner negative on `measurement=None` |

## Hard constraints respected

- No production code touched.
- `engine_run.json` schema unchanged.
- M0 Beauty pinned fixture byte-identical.
- Engine remains runnable.
- No banned ML scaffolding.

## Test results

| Suite | Result |
|---|---|
| `tests/test_no_hardcoded_fallbacks_in_payload.py` | 6/6 |
| **Full suite** | **956 passed, 14 skipped, 0 failed** (~3 min 28 s) |

## Out of scope (deliberately not touched)

- Full G-1 supplements pinned slate fixture — Sprint 4 ticket (Engineer A track). When that lands, this test naturally extends to the new fixture by replacing the harness scenario name; no code edits required to the assertion logic.
- Any behavior change to "fix" a future violation — per audit §B-3, the test is the contract; if it fails, fix the emitter, not the test (and re-pin the test before merging the emitter fix).
- Per-vertical scoping refinement — the current scan is vertical-agnostic; if a vertical-specific Phase 2 fallback ever ships (e.g. apparel-flavored constant), the assertion still catches it because the forbidden-constant list is upstream of the vertical filter.

## Risks observed (none unresolved)

- Float-equality brittleness: mitigated by `EQUALITY_TOL=1e-9` against 2-3-sigfig audit constants.
- Test could become noisy if a play emitter gets refactored to use bona-fide computed `effect_abs` values that happen to land in the forbidden set — that's a real signal worth surfacing (per audit, the right response is widening the scanner's risk-set scope or proving the value is not a fallback).

## Commit shape

Single commit (`d219060`) for the ticket, separate commit for `memory.md` (`50358de`).

## Next ticket

B-5 (Berkson-class invariant test) — pin the cohort-must-be-defined-on-early-half-counts invariant for behavioral-subset audiences with later-window outcomes; explicitly assert `subscription_nudge` and `routine_builder` ship `evidence_class=targeting` with `measurement=None`.
