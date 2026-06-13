# DS Architect Verdict — S8 Q3/Q6/Q7 (2026-05-24)

**Date:** 2026-05-24
**Author:** ecommerce-data-science-architect
**Parent verdict:** agent_outputs/ecommerce-ds-architect-s8-pseudo_n-and-ki-new-k-verdict-2026-05-24.md
**Decision scope:** Q3 (KI-NEW-L/M/N bundling) + Q6 (Play Library wave 1 selection) + Q7 (Sensitivity flag bundling)
**Status:** LOCKED.

---

## 1. S14-readiness framing (brief)

Refer to parent verdict §1 for the full framing. The compressed restatement: S14 success is *"on a small private-beta merchant's first run, the engine produces a defensible posterior + an honest evidence chain a skeptical operator can audit."* Three lenses apply to every Q here:

- **(a) Does this preserve the three orthogonal gates + the three S7.6 architectural invariants + the S7.6 CLI fix surfacing?** Non-negotiable.
- **(b) Does this make S13's ML AUDIENCE integration cleaner or messier?** S13 extends `PlayCard` with `predicted_segment` + `model_card_ref` and wires `ranking_strategy` into the 5 Tier-B audience builders. Anything that touches `PlayCard` shape, `_PRIOR_ANCHORED` dispatch, or audience-builder seams in S8 must leave S13 a single-commit integration.
- **(c) Does this resolve a known papercut before a real merchant sees it, or is it engineering hygiene that beta data should inform?** Founder said "stop deferring things" *and* "I will ship whenever I trust the engine." These are not in tension if we defer engineering hygiene where beta data is genuinely informative, and bundle anything that affects what a real merchant sees.

---

## 2. Q3 verdict — KI-NEW-L / M / N bundling

### KI-NEW-L (collapse 5 V2 prior-anchored injection blocks → 1 PRIOR_ANCHORED dispatch)

**Verdict: DEFER to a dedicated structural-cleanup sprint between S13 and S14 (call it S13.5).** Do NOT bundle into S8. Do NOT defer to "S9" as the IM plan suggests because no S9 exists in the revised roadmap (the IM revised plan jumps S8 → S10).

**Reasoning anchored in S14-readiness:**

1. **Lens (a) — invariant risk is maximal here.** The 5 blocks at `src/main.py:1380-1597` are the exact code surface where the three S7.6 architectural invariants live: single-demote-channel via `apply_guardrails_to_injected`, 3-channel `priority_prepend` (`8a2d726`), and the S7.6 CLI fix surfacing at `src/measurement_builder.py:2252-2270` (which is one call-frame away from these injection blocks because the builder writes the `drivers[*].blend_provenance` stash that the CLI fix reads). The S7.6-T7.5 spiral was three consecutive failed predictions about where a card died across exactly this code surface. Collapsing 5 builder-specific blocks into a registry-driven dispatch is a refactor that simultaneously touches all three invariants; a missed one is silent regression in beta-prep validation.

2. **Lens (b) — S13 actively makes this collapse easier.** S13-T1 extends the 5 Tier-B audience builders with `ranking_strategy: Optional[Literal[...]] = None` (per IM revised plan line 229). Post-S13, every Tier-B builder has been touched and re-validated. The natural moment to collapse the 5 injection blocks is *after* S13's builder-signature audit, because S13's per-builder tests give the collapse a fresh per-builder safety net. Doing the collapse in S8 (before S13's signature audit) means we collapse against today's 5 builder signatures and then have to re-validate the collapsed dispatch survives S13's signature change. Two refactor passes instead of one.

3. **Lens (c) — beta merchants do not see this papercut.** The 5 blocks vs 1 dispatch is engineering hygiene. A real merchant sees zero behavioral difference. Deferring does not affect "ship whenever I trust the engine."

4. **R-S8.4 mitigation already holds.** Per IM plan Part F: no new Tier-B builders are planned through S13. The 5-block surface does not grow during S8–S13.

**Resume trigger:** **Immediately after S13-T4 atomic flip lands and Beauty + Supplements re-pin completes.** That is the moment when (a) all 5 Tier-B builders have been re-audited under the `ranking_strategy` extension, (b) per-builder tests are freshest, (c) S14 onboarding has not yet started so re-pin churn doesn't hit a real merchant baseline. Call it S13.5 — a single 3-day structural-cleanup ticket dispatched to refactor-engineer with explicit invariant-preservation acceptance criteria.

**Invariants the S13.5 implementing refactor must preserve (pinned here so the future ticket has them):**

1. Single-demote-channel — every collapsed dispatch path must route through `apply_guardrails_to_injected`. No direct `engine_run.recommendations.append` in the new dispatch function.
2. 3-channel `priority_prepend` — collapsed dispatch must invoke the priority_prepend path for `cap_exceeded` + `eligibility_rejects` + `prior_unvalidated_rejects` + `window_disagreement_rejects`. Parameterized test at `tests/test_s7_6_c1_priority_prepend_invariant.py::test_tier_b_demoted_via_any_channel_survives_truncation` must pass unmodified.
3. `Measurement.observed_effect/p_internal/n` population at `src/measurement_builder.py:2252-2270` reachable from every collapsed dispatch path. Tripwire test `test_tier_b_recommended_cards_surface_observed_effect_on_beauty` is the canary; re-run after every commit in the collapse cluster.
4. Per-builder behavior byte-identical pre-collapse vs post-collapse on Beauty + Supplements pinned slates. Re-pin only if drift is provably correct (and then atomic flag flip per S7.6 discipline).

---

### KI-NEW-M (`_dedupe_rejections` first-wins-vs-last-wins-typed-code policy)

**Verdict: DEFER to S14 calibration window OR post-beta.** Do NOT bundle into S8.

**Reasoning:**

1. **Lens (c) decides this.** The KI text itself says "engine behavior is honest today; the reasons displayed are correct, just sometimes less specific than they could be." This is exactly the class of papercut where beta merchant feedback (S14-T3 "any blocker fixes surfaced") is genuinely informative. Designing the typed-reason priority map without knowing which reason-collisions confuse real operators is fabrication.
2. **Lens (a) is benign.** No invariant interaction.
3. **Lens (b) is benign.** S13 does not touch `_dedupe_rejections`.

**Resume trigger:** When S14-T3 surfaces ≥2 distinct beta-merchant reports of "the reason on this Considered card doesn't match what I'd expect" AND the implementing agent can map both to a `_dedupe_rejections` collision (vs an upstream reason being genuinely wrong). Until then, the existing first-wins behavior is acceptably honest.

---

### KI-NEW-N (experiment-promotion provenance-preserve at `src/decide.py:2080-2087`)

**Verdict: DEFER, paired with KI-NEW-M (same S14-or-later resolution window).** Do NOT bundle into S8.

**Reasoning:**

1. **Lens (c) decides.** Experiment promotion fires rarely on current fixtures; a low-frequency surface today. The IM-plan-cited 2-day cost is real but the value is unmeasured until S14 surfaces "why is this an experiment" questions from a real merchant.
2. **R-S8.1 stress test argues against bundling.** S8 already lands `evidence_source` + `sensitivity` + `provenance` additive on `PlayCard`. Adding a fourth additive field (`promoted_from_considered_reason`) in the same sprint expands the `event_version=1` optional surface beyond comfortable bounds. Each additive field adds a small but non-zero risk of an additive-vs-non-additive policy slip that forces a `event_version=2` bump and pushes beta.
3. **Lens (b) is benign.** S13 does not touch the experiment-promotion seam.

**Resume trigger:** Same as KI-NEW-M — S14-T3 beta-merchant feedback that the experiment surface needs upstream provenance. Natural bundling with KI-NEW-M as a "decide-layer provenance hygiene" mini-ticket if/when both surface.

---

### Aggregate S8 sprint shape implication

S8 stays at the IM-default 4-ticket scope (T0 [landed] + T1 + T2 + T3 + T4). No T5/T6/T7. Sprint duration stays ~2 weeks. Re-pin event count stays at 3 (T1.5/T2.5 bundled per Q7 below, T3.5, T4.5 = 3 events; T0 already landed). Schema-additive surface stays at 3 new PlayCard fields, not 4. R-S8.1 mitigated.

---

## 3. Q6 verdict — Play Library wave 1 selection

**Verdict: CONCUR with IM default.** Wave 1 = `winback_dormant_cohort` + `replenishment_due` + `discount_dependency_hygiene`. Do NOT substitute `cohort_journey_first_to_second` for `replenishment_due`.

**Reasoning anchored in S14-readiness:**

1. **Honest-dormancy is the test.** Per KI-NEW-G (2026-05-23 RESOLVED-AS-DOCUMENTED-EXPECTED-BEHAVIOR), `replenishment_due` is genuinely dormant on Beauty pinned fixture by design — the per-SKU repeat-buyer distribution sits below the floor. *This is the most valuable wave-1 test case the migration template can have.* If the migration accidentally activates the play (e.g., by misrouting the floor resolver or by silently bypassing D-S6-4), the byte-identical contract breaks and we catch the regression immediately. Substituting `cohort_journey_first_to_second` would test only the active path — which means the migration template's correctness on dormant plays is not verified until wave 2, which is post-S8. That's a structural-correctness gap the founder cannot trust without real-beta data, and "evaluated honestly for each merchant" includes "honestly evaluated as dormant when dormant."

2. **S13 forward-compat.** All three IM-default plays are S6/S7-wired Tier-B builders. S13-T1 extends all 5 Tier-B audience builders with `ranking_strategy`. Wave 1's three plays span both `winback_dormant_cohort` (S6 first-builder) and `replenishment_due` (S6 second-builder) and `discount_dependency_hygiene` (S7 first-builder) — covering the full S6 + S7 builder-style surface. S13's per-builder integration meets the new `plays/<play_id>/` template surface at three diverse points rather than three same-shaped points. Substituting `cohort_journey_first_to_second` (also S7) would narrow the coverage to two S7-style builders.

3. **Re-pin churn.** The IM plan asserts T4 is "zero re-pin target." That holds independent of which 3 plays migrate — refactor is byte-identical by contract. The 3-active-plays vs 1-dormant-plus-2-active framing in the brief slightly overweights re-pin economics; with zero re-pin target on T4.5, both options have the same re-pin cost (zero). The honest-dormancy test value (above) is the load-bearing factor, not re-pin count.

4. **R-S8.3 mitigation.** IM plan correctly notes the 3 IM-default plays are "the cleanest candidates" with no legacy entanglement. Substituting `cohort_journey_first_to_second` is also clean (it's S7-T2 work), so this lens doesn't differentiate.

**Founder note:** This concurrence is conditional on KI-NEW-G's 2026-05-23 honest-dormancy resolution holding. If the founder is uncomfortable shipping a wave-1 plan that includes a play that produces zero audience on the Beauty pinned fixture, the substitution becomes a defensible founder call — but the cost is losing the only structural-correctness test the migration template has for the dormant path.

---

## 4. Q7 verdict — S8-T2 Sensitivity flag bundling

**Verdict: RECOMMEND SEPARATE FLAG `ENGINE_V2_SENSITIVITY` with independent T2.5 atomic flip.** Do NOT bundle with `ENGINE_V2_TIER_CHIP`. Override the IM default.

**Reasoning anchored in S14-readiness:**

1. **The S7.6 lesson is "instrument over predict."** The S7.6-T7.5 spiral cost three consecutive failed predictions because flag flips bundled multiple behavioral changes into one re-pin moment, hiding which sub-change caused observed drift. The atomic per-ticket flag flip discipline (S7.6 T*N* + T*N*.5 pattern) is *load-bearing DS discipline* — it exists to make blast-radius observable. Bundling chip + sensitivity under one flag re-introduces the exact failure mode S7.6 was built to prevent.

2. **The two changes are independently observable.** `EvidenceSourceChip` is a single-enum additive field. `Sensitivity` is a 4-scenario dataclass with `compute_sensitivity()` math in `sizing.py`. They have different blast radii (sensitivity scenarios involve numeric perturbation math that can drift on floating-point edge cases; the chip is a deterministic table lookup). Flipping them together means if Beauty's pinned slate shifts unexpectedly at T1.5/T2 bundled flip, we don't know whether it's the chip mapping table or the sensitivity math.

3. **Re-pin churn math (the IM tradeoff text overweights this).** IM proposes "two flip events vs three" as the bundle argument.
   - **Bundled:** T1.5 (chip + sensitivity flip + re-pin) + T3.5 (EB blend flip + re-pin) + T4.5 (Play Library flip + target-zero-re-pin) = **2 numeric re-pin events.**
   - **Separate:** T1.5 (chip flip + re-pin) + T2.5 (sensitivity flip + re-pin) + T3.5 (EB blend flip + re-pin) + T4.5 (Play Library flip + target-zero-re-pin) = **3 numeric re-pin events.**
   - One additional re-pin event. Each re-pin event under S7.6 discipline is one atomic commit (`git add` + `pytest` + sha256-pin update + summary doc). Empirically per S7.6 ledger, this is ~30-60 minutes of refactor-engineer time per event. **Cost: ~1 hour.** Benefit: blast-radius isolation on the load-bearing typed surface that beta merchants will pattern-match against. **Trade is obviously correct.**

4. **"Stop deferring things" does not apply here.** The founder's instruction targets deferred *scope* (deferring KI fixes, deferring sprint deliverables). Separate flags do not defer anything — both ship in S8, same sprint, ~1-day separation. The instruction is being misread by IM as "minimize sprint commit count," which is not what the founder said.

5. **S13 forward-compat slightly favors separate.** S13's atomic flip on `ENGINE_V2_ML_AUDIENCE` is itself an atomic-per-ticket pattern (per IM revised plan S13-T4). The closer S8's pattern stays to S7.6+S13's pattern, the easier the on-ramp for the agent landing S13.

**Override the IM default. Separate flag. Atomic T2.5 flip.**

---

## 5. S14-readiness invariants — load-bearing test pins this verdict implies

Extends parent verdict §5 (renumbering preserved; new items 11-15):

11. **KI-NEW-L deferred to S13.5; no S8 ticket touches the 5 injection blocks at `src/main.py:1380-1597`** except through the existing-per-play extension pattern. S8-T4 Play Library wave 1 explicitly does not collapse the blocks (per IM plan line 180). Acceptance criterion on every S8 ticket: line-range `1380-1597` of `src/main.py` shows additions only within the existing per-builder block boundaries; no new top-level dispatch, no removal of existing blocks.
12. **KI-NEW-M / KI-NEW-N deferred to S14-driven resolution window.** No `_dedupe_rejections` policy change in S8. No `promoted_from_considered_reason` field added in S8. PlayCard additive surface in S8 is capped at exactly 3 new fields: `evidence_source`, `sensitivity`, `provenance`.
13. **Play Library wave 1 = `{winback_dormant_cohort, replenishment_due, discount_dependency_hygiene}`.** Test pin: `tests/test_s8_t4_play_library_wave1_migration.py` asserts exactly these three `play_id`s have a `plays/<play_id>/spec.yaml` artifact post-T4.5. `replenishment_due` produces zero audience on Beauty pinned fixture post-migration (honest-dormancy preserved).
14. **`ENGINE_V2_SENSITIVITY` is a distinct flag from `ENGINE_V2_TIER_CHIP`.** Test pin: env-override matrix at `tests/test_s8_flag_independence.py` asserts all 4 combinations `(chip ∈ {OFF, ON}) × (sensitivity ∈ {OFF, ON})` produce distinct, predictable `engine_run.json` shapes. Atomic flip discipline: T1.5 flips `ENGINE_V2_TIER_CHIP` only; T2.5 flips `ENGINE_V2_SENSITIVITY` only; each with its own fixture re-pin commit.
15. **S13.5 ticket scoped before S14 dispatch.** Before S14-T1 (first private-beta merchant onboarding) commits land, the KI-NEW-L collapse must be either (a) DONE per the resume trigger above, or (b) explicitly re-deferred to post-beta with founder + DS sign-off. Reason: KI-NEW-L deferral is conditional on "no new Tier-B builders through S13" (R-S8.4 mitigation); if that condition breaks, the KI escalates.

---

## 6. Open questions for the founder

Per "stop deferring things" + "tell me what to do," minimized. One genuine founder-domain item:

**F1. KI-NEW-L resume trigger as S13.5 (vs IM's "S9" framing).**

The IM plan defers KI-NEW-L to "S9," but the IM revised plan's roadmap has no S9 — it jumps S8 → S10. I'm resolving this by defining the resume trigger as a single S13.5 ticket *between* S13 close and S14-T1 dispatch, anchored on the reasoning in §2 (S13's per-builder audit gives the collapse a fresh safety net). The founder should ack this calendaring or veto if the post-S13/pre-S14 window is reserved for something else (e.g., S14 dry-run on Beauty + Supplements before real-merchant onboarding). If vetoed, KI-NEW-L defers to post-beta entirely, and §5 invariant 15 escalates: "no new Tier-B builders post-S13" becomes a hard rule, not a mitigation.

**No other founder input needed.** Q3 (KI-M, KI-N), Q6, Q7 are fully locked above.

---

## 7. Cross-references

- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md` Part D (KI bundling tradeoff text) + Part E Q3/Q6/Q7 (open questions) + Part F R-S8.1/R-S8.4 (risk register) + Part I (fixture re-pin schedule)
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` §B-S8 (line 103-116, ticket structure) + §B-S13 lines 215-244 (ML AUDIENCE integration, S13-T1 `ranking_strategy` extension at line 229)
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ecommerce-ds-architect-s8-pseudo_n-and-ki-new-k-verdict-2026-05-24.md` §1 (S14-readiness framing this verdict inherits), §5 (invariants list this verdict extends)
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md:346-358` — KI-NEW-G (honest-dormancy precedent for Q6, RESOLVED-AS-DOCUMENTED 2026-05-23)
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md:411-420` — KI-NEW-L (5-block collapse, S13.5 deferral target)
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md:422-430` — KI-NEW-M (`_dedupe_rejections` policy, S14 deferral target)
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md:432-440` — KI-NEW-N (experiment-promotion provenance, S14 deferral target)
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py:1380-1597` — the 5 injection-block surface KI-NEW-L collapses; load-bearing invariant boundary
- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py:2252-2270` — S7.6 CLI fix surface; must remain reachable through any S8-T3/T4 refactor and S13.5 collapse
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s7_6_c1_priority_prepend_invariant.py` — S7.6 tripwire test (must pass unmodified through all S8 commits + S13.5 collapse)
- `/Users/atul.jena/Projects/Personal/beaconai/CLAUDE.md` Subagent Handoff Discipline (load-bearing handoff rules + single-demote-channel invariant)
- `/Users/atul.jena/Projects/Personal/beaconai/memory.md` lines 578-580 — S7.6 forward-scaffolding for S13 (`predicted_segment`, `model_card_ref`, `ranking_strategy` kwarg in production)
- `/Users/atul.jena/Projects/Personal/beaconai/ENGINE_OVERVIEW.md` §8.5 (three orthogonal gates)

**End of verdict.** S8 ticket dispatch unblocked with the following locks: 4-ticket scope (T0 landed + T1 + T2 + T3 + T4), `ENGINE_V2_SENSITIVITY` separate flag, Play Library wave 1 = `{winback_dormant_cohort, replenishment_due, discount_dependency_hygiene}`. KI-NEW-L scheduled for S13.5; KI-NEW-M + KI-NEW-N deferred to S14-driven window. Awaiting founder ack on §6 F1 only.
