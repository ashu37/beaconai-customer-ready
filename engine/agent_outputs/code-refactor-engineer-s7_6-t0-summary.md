# S7.6-T0 — shared observed-effect helper (`src/measurement_observed.py`)

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `713493b`

---

## 1. Ticket scope

Land a pure-function module of recent-vs-prior observed-effect primitives for Tier-B builders. No callers yet (T1-T5 will wire). Strictly additive surface — M0 / Beauty / Supplements byte-identical at flag-OFF (in fact at any setting, since no caller exists yet).

Exports:
- `compute_two_proportion_observed` — z-pooled two-proportion test with Fisher's-exact small-cell fallback.
- `compute_welch_t_observed` — Welch's t for continuous metrics.
- `compute_multi_window_sign_agreement` — sign-agreement scoring across a caller-supplied window map.

## 2. Files changed

- `src/measurement_observed.py` (new, 296 lines)
- `tests/test_measurement_observed.py` (new, 193 lines, 17 tests)

## 3. Behavior change

None. No production caller yet.

## 4. Tests added / modified

17 new tests in `tests/test_measurement_observed.py` covering numerical correctness of z-pool / Fisher / Welch primitives + sign-agreement across windows + degenerate-input handling.

Suite: 1663p / 14s / 3xf / 1xp / 0f.

## 5. Risks + mitigations

- **Unused-at-runtime contract surface.** This is intentional forward scaffolding — T1-T5 are the first callers. Tests pin numerics so the helper does NOT drift before consumers arrive.

## 6. Follow-ups / known-issues opened

- T1 (winback) is first consumer.

## 7. Commit ref

`713493b`
