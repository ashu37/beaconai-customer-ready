# S7.6-T6 — eligibility gate + 3-state copy ladder + joint-p amendment (flag OFF)

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `45033dd`

---

## 1. Ticket scope

Wire the eligibility gate that consumes observed-effect data stashed by T1/T3/T4/T5 helpers on `blend_provenance` and routes joint-fail / sign-disagreement cards to Considered with `SIGNAL_INCONSISTENT_ACROSS_WINDOWS`.

Two clauses per DS architect verdict 2026-05-23 (`agent_outputs/ecommerce-ds-architect-t5_5-joint-gate-verdict-2026-05-23.md`):
- **Clause 1:** `observed_n > OBSERVED_MIN_ELIGIBILITY_N` AND `sign_agreement_count < 2`.
- **Clause 2 (DS amendment):** for builders stashing `*_band` windows (detect-by-keys; currently only `aov_lift_via_threshold_bundle`), joint p<0.10 must hold on BOTH L28 AND L28_band windows.

**3-state copy ladder** per `posterior_ratio = observed_n / (observed_n + pseudo_n)`:
- cold-start (`<0.2`) keeps `why_now` byte-identical
- accumulating (`[0.2, 0.6)`) prepends "Cohort signal is accumulating - "
- mature (`>=0.6`) prepends "Cohort signal dominates - "

Idempotent on re-application.

Gate seam: new `decide.py::_route_observed_eligibility_holds()`, mirroring the Sprint 7.5 `_route_prior_unvalidated_holds` precedent. Runs AFTER the prior-unvalidated and window-disagreement routes so the demote channel stays single. Reuses existing `ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS`.

New flag `ENGINE_V2_OBSERVED_ELIGIBILITY_GATE` default OFF + `OBSERVED_MIN_ELIGIBILITY_N` default 30. T6.5 flips. T5.5 re-sequenced to AFTER T6.5 per DS verdict (otherwise Beauty's noise-dominated AOV-bundle observed-effect would surface).

## 2. Files changed

- `src/decide.py` (+273 lines).
- `src/utils.py` (+33 lines).
- `tests/test_s7_6_t6_eligibility_gate.py` (new, +465 lines).

## 3. Behavior change

Flag-OFF: strict no-op (kept = input, refused = []). M0 + Beauty + Supplements pinned briefings byte-identical.

Flag-ON unit tests pin the load-bearing T5.5 probe case: aov_bundle card with 3-window AOV sign-agreement but band p>=0.10 demotes to Considered with `SIGNAL_INCONSISTENT_ACROSS_WINDOWS` instead of surfacing in Recommended with 20x noise-driven posterior shift.

T1/T2/T3/T4 single-test observed-effect behavior unchanged (joint clause is no-op because their stash carries no `*_band` keys; detect-by-keys shape is extensible to future multi-leg builders without play_id hardcode).

## 4. Tests added / modified

24 new tests in `tests/test_s7_6_t6_eligibility_gate.py`. Suite 1766p / 14s / 4xf / 2xp (from 1742p baseline = +24 new T6 tests, zero regressions).

## 5. Risks + mitigations

- **Detect-by-keys vs play_id hardcode** — chosen intentionally so future multi-leg builders don't need gate edits.
- **Gate ordering** — runs AFTER prior-unvalidated and window-disagreement so the single-demote-channel invariant is not violated.

## 6. Follow-ups / known-issues opened

- T6.5 flag flip (landed at `6d312d3`).
- T5.5 atomic flip unblocked (landed at `de01df4`).
- T5.6 priority_prepend generalization required to handle gate output (landed at `8a2d726`).

## 7. Commit ref

`45033dd`
