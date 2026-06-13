# S7.6-T4 — cohort_journey_first_to_second observed-effect wiring (flag OFF)

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `a867308`

---

## 1. Ticket scope

Implement per-store two-proportion z-test on cohort-defined first-to-second rates for the Tier-B prior-anchored `cohort_journey_first_to_second` play, per plan B-4:234. Mirrors T3 discount_hygiene precedent (commit `fc2de84`).

Adds `compute_journey_first_to_second_observed_effect` helper in `measurement_builder.py`. **CRITICAL Berkson invariant:** cohort denominators are defined on early-half-of-window first-purchase dates per `tests/test_berkson_invariant.py` and `project_journey_p_zero.md` 2026-04-30 memory (original resolution commit `554960d` Phase 4.1). Multi-window sign-agreement across {L28, L56, L90}.

Flag `ENGINE_V2_OBSERVED_EFFECT_JOURNEY` default OFF; flag-ON behavior verified via unit tests including Berkson regression case.

## 2. Files changed

- `src/main.py` (+11 lines).
- `src/measurement_builder.py` (+193 lines).
- `src/utils.py` (+17 lines).
- `tests/test_s7_6_t4_journey_observed_effect.py` (new, 442 lines).

## 3. Behavior change

None at flag-OFF. Beauty + Supplements pinned fixtures byte-identical; M0 byte-identical.

## 4. Tests added / modified

New test file (442 lines) including Berkson regression case. Specific test count + suite delta: not recorded in commit message.

## 5. Risks + mitigations

- **Berkson confound is the load-bearing invariant** on this builder. Cohort denominators MUST use early-half-window first-purchase dates. The regression test pins this; any future rewrite of the helper must preserve it.

## 6. Follow-ups / known-issues opened

- T4.5 atomic flip (landed at `2f1c17c`, rollup summary).

## 7. Commit ref

`a867308`
