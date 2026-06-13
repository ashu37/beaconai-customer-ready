# S7.6-T2 — B-2 replenishment_due observed-effect wiring (flag OFF)

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `b0c9980`

---

## 1. Ticket scope

Mirror the T1 winback observed-effect wiring for the `replenishment_due` Tier-B builder. New helper threads observed_k / observed_n / sign-agreement into the bayesian_blend seam at the L28 anchor for the `replenishment_due` prior-anchored card. Flag `ENGINE_V2_OBSERVED_EFFECT_REPLENISHMENT` default OFF.

## 2. Files changed

- `src/main.py` — flag-gated kwarg plumbing for replenishment block (+11 lines).
- `src/measurement_builder.py` — `compute_replenishment_observed_effect` helper (+252 lines).
- `src/utils.py` — flag default `"false"` + bool-coerce allowlist (+16 lines).
- `tests/test_s7_6_t2_replenishment_observed_effect.py` (new, 323 lines).

## 3. Behavior change

None at flag-OFF default. M0, Beauty, Supplements byte-identical.

## 4. Tests added / modified

New test file covers helper correctness + flag-OFF byte-identity + flag-ON observed-effect threading. Specific test count + suite delta: not recorded in commit message.

## 5. Risks + mitigations

- **D-S6-4 per-SKU floor N=30 blocks replenishment from firing on the synthetic Beauty fixture** at observed-effect activation time — this is the gap T2.5-fix (commit `506c703`, separate summary) closes by lowering the default to N=10 and adding a per-stage profile cell.
- **No T2.5 atomic flip landed in this sprint.** Per `code-refactor-engineer-s7_6-t2_5-deferred-summary.md`, T2.5 was deferred Path-(c) (DS verdict) until the per-SKU floor and observed-effect gate together produce honest placement; the deferral memorialized via KI-NEW-G + ARCHITECTURE_PLAN amendments at `6c7d3d3`.

## 6. Follow-ups / known-issues opened

- T2.5-fix (per-SKU floor 30 -> 10 + per-stage profile cell), committed at `506c703`.
- T2.5 atomic flip remains deferred per Path (c) DS verdict (see existing `s7_6-t2_5-deferred-summary.md`).

## 7. Commit ref

`b0c9980`
