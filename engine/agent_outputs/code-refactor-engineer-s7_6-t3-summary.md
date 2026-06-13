# S7.6-T3 — discount_dependency_hygiene observed-effect wiring (flag OFF)

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `fc2de84`

---

## 1. Ticket scope

Implement per-store revenue-weighted z-test on heavy-discount share for the Tier-B prior-anchored `discount_hygiene` play, per plan B-3:219. Mirrors the T1 winback observed-effect precedent (commit `e8864d8`). Adds `compute_discount_hygiene_observed_effect` helper in `measurement_builder.py`; threads observed_k, observed_n, multi-window sign-agreement into the existing `bayesian_blend` seam via the `_PRIOR_ANCHORED` dispatch.

Flag `ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE` default OFF; flag-ON behavior verified via unit tests only. Supplements remains Path-D dormant per DS Memo-4 REJECT (helper short-circuits on `vertical=supplements`).

T3.5 flip companion: separate dispatch after founder review of T3 diff + Beauty tripwire probe predicting observed_n>=30 (landed at `21bc273`).

## 2. Files changed

- `src/main.py` (+13 lines).
- `src/measurement_builder.py` (+234 lines).
- `src/utils.py` (+16 lines).
- `tests/test_s7_6_t3_discount_hygiene_observed_effect.py` (new, 482 lines).

## 3. Behavior change

None at flag-OFF. Beauty + Supplements pinned fixtures byte-identical; M0 byte-identical.

## 4. Tests added / modified

New test file (482 lines). Specific test count + suite delta: not recorded in commit message.

## 5. Risks + mitigations

- **Supplements deliberately excluded** per DS Memo-4 REJECT; helper short-circuits on vertical=supplements. Path-D contract preserved.
- **CLAUDE.md 2026-05-22 sprint discipline followed** — predict observed_n before T*.5 flip; flag stays OFF at T3, atomic flip lives at T3.5.

## 6. Follow-ups / known-issues opened

- T3.5 atomic flip (landed at `21bc273`, rollup summary).

## 7. Commit ref

`fc2de84`
