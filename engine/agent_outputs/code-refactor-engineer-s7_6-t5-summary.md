# S7.6-T5 — aov_lift_via_threshold_bundle observed-effect wiring (flag OFF)

**Author:** code-refactor-engineer (backfilled 2026-05-25)
**Branch baseline:** `post-6b-restructured-roadmap`
**Commit:** `255e218`

---

## 1. Ticket scope

Implement per-store **dual** statistical test for the Tier-B prior-anchored `aov_lift_via_threshold_bundle` play per plan B-5:249: Welch's t-test on audience-level AOV (L28 recent vs prior) AND two-proportion z-test on threshold-band share, **both must reach p<0.10 joint**. Multi-window sign-agreement across {L28, L56, L90} on AOV delta.

Mirrors T4 precedent. Adds `compute_aov_bundle_observed_effect` helper. Reuses T0 helpers `compute_welch_t_observed` + `compute_two_proportion_observed`; no new scipy import. Welch primary has `k=None` (continuous), so L28 band-share cell counts are threaded as the (observed_k, observed_n) blend channel; both Welch + z-prop results are folded into `MultiWindowAgreement.windows` under L28/L56/L90 (AOV) + L28_band/L56_band/L90_band (band-share) so the joint p<0.10 consumer (T6) can read both p-values from the single stash channel without breaking the T1/T2/T3/T4 single-channel contract.

Vertical scope: Beauty only. Supplements short-circuits per plan B-5:248 (vertical exclusion enforced at `audience_builders.py` via S7.6-T7 + C3 flag flip).

Flag `ENGINE_V2_OBSERVED_EFFECT_AOV_BUNDLE` default OFF; flag-ON behavior verified via 15 new unit tests.

## 2. Files changed

- `src/main.py` (+13 lines).
- `src/measurement_builder.py` (+265 lines).
- `src/utils.py` (+17 lines).
- `tests/test_s7_6_t5_aov_bundle_observed_effect.py` (new, 471 lines, 15 tests).

## 3. Behavior change

None at flag-OFF. Beauty + Supplements pinned fixtures byte-identical (cold-start `observed_k=observed_n=0` path unchanged). M0 byte-identical.

## 4. Tests added / modified

15 new tests including joint-pass / only-Welch-passes / only-zprop-passes / supplements short-circuit / per-builder flag independence.

Suite: 1727p -> 1742p / 14s / 4xf / 2xp. Zero regressions.

## 5. Risks + mitigations

- **Dual-test design is novel** in this codebase. The `*_band` window key shape is the discriminator the T6 gate uses to detect joint-p builders; pinning by tests means future single-leg builders don't accidentally trigger the joint gate.
- **T5.5 atomic flip re-sequenced** to after T6 + T6.5 + T5.6 per DS verdict 2026-05-23 (the joint-fail path on Beauty would otherwise have produced a 20x noise-driven posterior surface).

## 6. Follow-ups / known-issues opened

- T6 (eligibility gate) consumes this contract.
- T5.5 atomic flip landed at `de01df4` (rollup summary).

## 7. Commit ref

`255e218`
