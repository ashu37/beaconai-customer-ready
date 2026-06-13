# S7.6-C1 — priority_prepend on assemble_considered + mirror fix + truncation invariant scaffold

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `18e33b1`

---

## 1. Ticket scope

Mechanism for closing T7.5's actual gate: `cap_exceeded` entries demoted from Recommended Now were silently dropped when 6 `pre_existing` rejections filled the Considered budget. `priority_prepend` ensures Tier-B prior-anchored cards (S6/S7-wired plays: `winback_dormant_cohort`, `replenishment_due`, `discount_dependency_hygiene`, `cohort_journey_first_to_second`, `aov_lift_via_threshold_bundle`) survive truncation when they land at rank 4-6 of the tail. Discriminator: `PlayCard.would_be_measured_by is not None`.

Mirror fix on `populate_considered_from_candidates:781` closes the sibling truncation site at the M3 candidate side.

New `EngineRun.considered_truncated_count: int = 0` — flat additive scalar (mirrors `cold_start: bool` pattern, no schema bump).

Pinned-fixture invariant tests (`test_considered_truncated_count_zero_on_beauty` and `_on_supplements`) marked xfail until C2 lands; C2's `apply_guardrails_to_injected` drains the upstream injection storm at `main.py:1380-1597` so `pre_existing` fits within `MAX_CONSIDERED_RENDERED=6`. C2's hard exit criterion is flipping these two xfails to xpass.

## 2. Files changed

- `src/decide.py` (+93 lines).
- `src/engine_run.py` (+13 lines).
- `tests/test_s7_6_c1_priority_prepend_invariant.py` (new, +273 lines).

## 3. Behavior change

Beauty + Supplements fixtures byte-identical post-C1 (priority_prepend mechanism empirically inert on current pinned state — Tier-B cards either already in `head[:3]` or upstream-suppressed; no `would_be_measured_by` cards in tail to prepend). M0 byte-identical.

`considered_truncated_count` now populated on `EngineRun`; downstream contract consumers can read it.

## 4. Tests added / modified

New: `tests/test_s7_6_c1_priority_prepend_invariant.py` with mechanism tests (`test_priority_prepend_survives_truncation` + `test_assemble_considered_idempotent`) passing, plus two pinned-fixture invariant tests (`_on_beauty` + `_on_supplements`) marked **xfail until C2 lands**.

Suite delta not explicitly recorded in commit message.

## 5. Risks + mitigations

- **Mechanism inert on current synthetic fixtures.** The mechanism is forward-correct insurance; pinning by mechanism tests prevents regression. The two xfail invariant tests are the gate that C2 flips to xpass.
- **Precedent for one-off prepend exists** at `src/main.py:1639-1645` (first_to_second_purchase). C1 generalizes the pattern.
- **DS-locked per ARCHITECTURE_PLAN.md 2026-05-22** single-demote-channel invariant.

## 6. Follow-ups / known-issues opened

- C2 must drain the injection storm and flip both xfails to xpass.
- FIX `bb9fd32` mirrors the same priority_prepend to `populate_considered_from_candidates` (the candidate-side truncation site).

## 7. Commit ref

`18e33b1`
