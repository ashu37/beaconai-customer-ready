# T5.5 Joint-Gate Enforcement Verdict — DS Architect

**Date:** 2026-05-23
**Author:** ecommerce-ds-architect
**Scope:** Verdict-only. No code edits. Responds to T5.5 probe empirical finding (joint test fail with 20x posterior shift if flipped as-is).

---

**Q1 — Where is the joint-p<0.10 check architecturally supposed to live?**

T5's helper `compute_aov_bundle_observed_effect` (`src/measurement_builder.py:1773-1869`) computes both Welch-t (L1845) and z-prop (L1846) per window and stashes them under `L28/L56/L90` + `L28_band/L56_band/L90_band` (L1860-1868). The docstring at L1788-1789 explicitly states the design intent: *"so the joint-test eligibility consumer (T6) can read both p-values from a single channel."* The helper inspects neither p-value as a gate; it only short-circuits on data-absence (L1802-1818) and on the B-5:248 supplements carve-out (L1807-1808). T5 was designed as compute-and-stash; the joint gate was always scoped to T6, not the helper. The existing tests confirm this contract: `test_compute_aov_bundle_only_welch_passes` (tests L190-220) and `test_compute_aov_bundle_only_zprop_passes` (L223-260) assert `not joint_pass` on the returned p-values — they do NOT assert `(None, None)`. They assert the partial result returns and is readable. Treating `vertical_excluded_per_b5_248` as the analog for joint-fail is a category error: that's a structural carve-out (this builder cannot ever fire for this vertical), not a sample-realization gate. Mirroring it would conflate "no signal possible" with "signal possible, this window failed it."

**Q2 — Does T6 spec need amendment?**

Yes. T6 as specified (`agent_outputs/implementation-manager-s7_6-continuation-plan.md:157`) only gates on `sign_agreement_count<2`. That predicate is necessary but not sufficient for any builder with a joint condition. Sign-agreement on the Welch leg alone can equal 2 while the z-prop leg is pure noise — exactly the Beauty probe case. The plan B-5:251 contract says BOTH legs must reach p<0.10 on L28; the only place that contract can be honored without re-architecting helpers is the T6 eligibility gate. T6 must read `agreement.windows["L28"].p_value` AND `agreement.windows["L28_band"].p_value` (both already stashed per L1860-1868) and downgrade to Considered with `SIGNAL_INCONSISTENT_ACROSS_WINDOWS` (or a new `SIGNAL_JOINT_TEST_FAILED` reason) when either is None or ≥0.10. This is a per-builder predicate; T3/T4 helpers have single tests and don't carry a `_band` channel, so the joint clause is a no-op for them.

**Q3 — Option A.**

T5.5 must be held until T6 ships with the amended predicate. Option C looks smaller but is architecturally wrong: it overloads the helper with policy that was deliberately externalized (per L1788 docstring), invalidates two intentionally-written test cases that pin the compute-and-stash contract, and sets a precedent that every future joint or multi-leg builder must hard-gate at the helper — which removes the analyst's ability to inspect partial signals downstream and breaks the symmetry where T6 owns ALL eligibility logic. The cost of A (one spec clause + slightly larger T6 + one sequence swap) is real but bounded; the cost of C is architectural drift that the founder will pay for in S8 when the next multi-leg builder lands.

**Q4 — N/A (Option A selected).**

If C were forced: the smallest shape would be a post-compute guard at L1855-1869 returning `(None, None)` when `welch_per_window["L28"].p_value` or `band_per_window["L28"].p_value` is None-or-≥0.10. But this would require flipping the asserts in `test_compute_aov_bundle_only_welch_passes` (L211-220) and `test_compute_aov_bundle_only_zprop_passes` (L241-260) from "joint_pass is False on returned values" to "primary is None" — which changes the helper's contract from "report what was observed" to "report only what passed." That contract change is the architectural drift cited in Q3.

**Q5 — Founder criterion check.**

Both options produce honest behavior; the third honest outcome (surface in Recommended Now with claim-string acknowledging joint failure) is NOT honest — a card in Recommended Now whose posterior shifted 20x off a noise leg is the exact "tool recommending the usual" failure mode the founder named, no matter what the why_now string says. Posterior placement IS the claim. The only honest placements when joint-p>0.10 are (a) Considered with `SIGNAL_INCONSISTENT_ACROSS_WINDOWS` or (b) Watching/cold-start with posterior=prior. Option A delivers (a); Option C delivers (b). Both honest. A is architecturally cleaner. The "stop deferring" directive is satisfied because A doesn't defer T5.5 indefinitely — it sequences T5.5 AFTER T6.5 within the same sprint, which is the originally-intended dependency order per `agent_outputs/implementation-manager-s7_6-continuation-plan.md:32` (T6 critical path explicitly does not require T5 wired-on first).

---

**Refactor agent should pick Option A — no other deviation.**

---

**Key file paths referenced:**
- `src/measurement_builder.py` (L1773-1869 helper; L1788-1789 design-intent docstring; L1855-1868 stash structure; L2105-2127 card-seam wiring)
- `src/measurement_observed.py` (L197-245 Welch helper)
- `tests/test_s7_6_t5_aov_bundle_observed_effect.py` (L190-220, L223-260 joint-failure tests pinning compute-and-stash contract)
- `agent_outputs/implementation-manager-s7_6-continuation-plan.md` (L32 critical path; L101-116 T6 spec; L157 eligibility predicate to amend)
