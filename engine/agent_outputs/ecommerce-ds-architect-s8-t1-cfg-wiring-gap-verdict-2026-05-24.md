# DS Architect Verdict — S8-T1.5 cfg-wiring gap

**Date:** 2026-05-24
**Author:** Ecommerce DS Architect
**Scope:** Resolution of the dead-flag bug discovered when S8-T1.5 dispatched the `ENGINE_V2_TIER_CHIP` default flip
**Related:** `agent_outputs/ecommerce-ds-architect-s8-q3-q6-q7-verdict-2026-05-24.md` (invariants 1–15)

## Empirical anchor

Verified at `src/main.py:1332, 1378, 1426, 1478, 1536` — 4 of 5 prior-anchored callsites omit `cfg=cfg`. Only the AOV-bundle callsite (L1557) threads it (added inline for S7.6-T5 observed-effect, not for the chip). The producer gate at `src/measurement_builder.py:2428-2430` is therefore unreachable for winback, replenishment_due, discount_dependency_hygiene, and cohort_journey_first_to_second. The tripwire's `evidence_source=None` for all three Tier-B Recommended cards on `healthy_beauty_240d` is the correct symptom of a missing kwarg, not a logic defect.

## Q1 — Resolution option: **OPTION B**

Insert **S8-T1.6** (cfg-thread + harness-level coverage test) as a single-purpose commit, then S8-T1.5 becomes a clean atomic flag flip.

Reasoning:

- **Atomic-flip discipline (S7.6-T7.5 lesson + my own §4 verdict).** The S7.6-T7.5 spiral happened precisely because behavioral fixes were bundled with flag flips and the agent could not distinguish whether failures were from the fix or the flip. Option A repeats that mistake at the maximal-blast-radius surface in the codebase (L1380-1597). The cost of an extra commit is hours; the cost of a bundled flip going sideways at this seam is days plus a re-pin spiral.
- **Coverage-gap closure.** Option A under time pressure typically ships with the same kind of in-builder test that already missed this bug. Option B explicitly carves out a single-purpose ticket whose acceptance criterion is "exercise the seam via `main.run_action_engine`." That is the only shape that closes the class of bug.
- **Deviation-check ergonomics (`cc7baba`).** Option A requires a `Deviation check: [describe + DS+founder sign-off]` line because it bundles a behavioral correctness fix with a default flip — see Q2. Option B's T1.6 carries `Deviation check: none` (pure correctness, no behavior change at flag default OFF), and T1.5 carries `Deviation check: none` (pure flag flip). Both ride the happy path of the new discipline.
- **Founder's "stop deferring" guidance.** Option B is one extra commit, not deferral. The clock cost is ~hours; the discipline cost of bundling is structural.

Option C (revert) is overkill — the enum, the field, the OFF-default tests, and the producer gate are all correct. Don't throw them away.

## Q2 — DS invariant 11 classification: **WITHIN exception, but with a refined sub-rule**

Adding `cfg=cfg` to an existing call inside an existing per-builder block is the *minimal* form of "additions within existing per-builder block boundaries." It is not a new top-level dispatch, not a new injection block, and not a re-shape of the demote-channel routing the invariant was written to protect (that invariant exists to defend the post-`apply_guardrails` single-demote-channel contract introduced in S7.6 C2, see CLAUDE.md handoff discipline § single-demote-channel invariant).

**Refined sub-rule for future agents (subsume into invariant 11):** Adding kwargs to existing callsites of `build_prior_anchored_recommendations` (or any pre-existing builder seam) is permitted without deviation sign-off **provided** (a) the kwarg is purely additive at the producer side (default `None` / `False` preserves prior behavior) and (b) the change does not introduce a new `engine_run = _dc_replace(engine_run, recommendations=...)` mutation. The cfg-thread fix satisfies both.

No founder + DS sign-off needed beyond this verdict. T1.6's commit body should still carry `Deviation check: none` per `cc7baba`.

## Q3 — Pattern coverage for T2 / T3 / S13: **FIX ONCE FOR ALL, in T1.6**

Per the IM plan at `agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md` Part B S8-T2 and S8-T3 — both will read additional cfg flags (`ENGINE_V2_SENSITIVITY`, `ENGINE_V2_PROVENANCE`) inside the same `build_prior_anchored_play_card` producer. S13's `ranking_strategy` extension lands on the same seam. Three future tickets, same pattern, same gap if we don't fix it now.

**T1.6 acceptance criterion (DS-locked):**
1. Add `cfg=cfg` to all 5 callsites in `src/main.py` at L1332, L1378, L1426, L1478, L1536 (L1557 already has it — verify byte-identity).
2. Add a harness-level pytest that runs `main.run_action_engine` on the Beauty 240d fixture **twice** — once with `ENGINE_V2_TIER_CHIP=False`, once with `=True` — and asserts the Recommended Tier-B cards' `evidence_source` is `None` vs `STORE_OBSERVED` respectively. This is the test that *would have* caught S8-T1's gap.
3. Add a structural pin: a test that parses `src/main.py` and asserts every call to `build_prior_anchored_recommendations` (regex match on the function name) passes `cfg=cfg` as a kwarg. This prevents future builders added under T2/T3/S13 from regressing the pattern silently.

(3) is the load-bearing one for the structural-pattern question. It is cheap, deterministic, and converts "remember to thread cfg" from tribal knowledge into a CI gate.

## Q4 — Test discipline to add

**Every flag-gated producer-side change requires both:**

- **(a) Producer-side parametrized test** (already standard; S8-T1 has this).
- **(b) Harness-level end-to-end test** that runs `main.run_action_engine` on a pinned fixture with the flag forced ON and asserts the field populates on the rendered cards (the existing T3.y / Beauty / Supplements re-pin tests already run main.py end-to-end; the new requirement is *asserting on the cfg-gated field*, not just on HTML sha).

The lighter-weight contract test (Q3 item 3 — structural pin on callsite kwargs) is a complement, not a substitute. The structural pin catches "you forgot to thread cfg." The harness test catches "you threaded cfg but the field still doesn't populate for some other reason." Both are cheap; require both.

## Q5 — New invariant 16

**Invariant 16 (DS-locked 2026-05-24):** Every flag-gated producer field — defined as any `PlayCard` attribute whose population branches on `cfg.get("FLAG", ...)` — must be exercised by at least one harness-level test that calls `main.run_action_engine` end-to-end with the flag forced ON and asserts the field populates on at least one rendered card. Producer-direct tests that construct `cfg` manually and call the builder helper do not satisfy this invariant.

**Test pin location:** `tests/test_v2_harness_cfg_gated_fields.py` (new file at T1.6; one parametrized test per (flag, expected_field) pair; start with `ENGINE_V2_TIER_CHIP → evidence_source`; T2/T3/S13 each append a row).

This complements invariant 9 (golden re-pin atomicity) — invariant 9 protects byte-identity at the default; invariant 16 protects field-population correctness when the default flips.

## Q6 — Sprint table shape: **Option (a)**

Show S8-T1 as **Done with asterisk**, add S8-T1.6 as a new row.

```
S8-T1   Done* (asterisk: chip flag is dead code at default OFF; T1.6 wires cfg, T1.5 flips)
S8-T1.6 Pending (cfg-thread fix + harness coverage test + structural callsite pin)
S8-T1.5 Pending (atomic default flip + Beauty/Supplements re-pin) — blocked by T1.6
```

Rationale: Option (b) (reclassify T1 as Incomplete) erases the signal that the enum + field + OFF-default contract did land correctly; future readers should see that T1 shipped real artifacts and T1.6 is the surgical follow-up, not that T1 failed. The asterisk + new row matches how Phase 6A B-series tickets were tracked when bundled fixes landed.

## S14-readiness lens

S14 promises a merchant-facing chip ("STORE_OBSERVED" vs "INDUSTRY_PRIOR") that signals evidence provenance honestly per merchant. Today that surface does not exist at runtime for 4 of 5 Tier-B plays regardless of flag state. T1.6 + T1.5 together make the surface real. Without T1.6, the S14 onboarding pitch is unfalsifiable — we'd be shipping a chip that the code says it can render and the runtime never does. The two-commit path is the minimum needed to make the S14 trust surface real.

---

**Bottom line:** Option B. T1.6 lands the cfg-thread + harness test + structural callsite pin (fix-once-for-all per Q3). T1.5 then flips the default atomically per S7.6 discipline. Invariant 16 added. Sprint table gets an asterisk on T1 and a new T1.6 row.
