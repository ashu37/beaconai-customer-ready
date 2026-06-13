# Sprint 7.6 — Continuation Plan (Observed-Effect Wiring, finish-the-scope)

**Branch base:** `post-6b-restructured-roadmap` @ `d6053d0` (S7.6-C3 close)
**Suite at dispatch:** 1690p / 14s / 4xf / 2xp. Beauty + Supplements pinned briefings reflect post-S7.6 state. M0 byte-identical.
**Status convention:** S7.6-T{n} = code-behind-flag (default OFF); S7.6-T{n}.5 = flag flip + atomic fixture re-pin.
**Founder directive (2026-05-22):** finish original S7.6 scope; no "deferred" language; every ticket has an executable definition-of-done or a named upstream blocker.

---

## 1. Sprint goal

Finish original S7.6 scope: every S6/S7-wired Tier-B play surfaces with cohort-level statistical evidence (z-test or Welch-t per-store, multi-window sign-agreement across {L28,L56,L90}) feeding the EB blend at `src/sizing.py::bayesian_blend`. The cohort p-value gate referenced in ENGINE_OVERVIEW becomes empirically true on Beauty + Supplements for all five Tier-B plays in `_PRIOR_ANCHORED` (`src/measurement_builder.py:717`) — modulo two architecturally-locked carve-outs (supplements B-3 Path-D dormant per DS Memo-4; supplements B-5 vertical_excluded per plan §III B-5:248). At sprint close, every play_id in `_PRIOR_ANCHORED` either (a) emits a card with non-null `observed_n` on Beauty, or (b) has a documented architectural carve-out citing source-of-truth.

---

## 2. Ticket sequence + dependency graph

```
[done] T0 helper ─┬─► [done] T1 winback ──► [done] T1.5
                  ├─► [done] T2 replenish ──► T2.5-RESOLUTION (Path b, see §4)
                  ├─► T3 discount        ──► T3.5 flip   [Beauty only]
                  ├─► T4 journey         ──► T4.5 flip   [Berkson-pinned]
                  └─► T5 aov_bundle      ──► T5.5 flip   [Beauty only]
                                                │
[done] T7 threshold-from-data ─► [done] T7.5    │
                                                ▼
                                  T6 eligibility-gate + 3-state copy ladder
                                                ▼
                                              T6.5 flip
```

**Critical path:** T3 → T4 → T5 → T6 → T6.5. T6 depends on ≥2 builders wired beyond T1 (T3 + T4 suffice; T5 not required for T6 to flip). T2.5-RESOLUTION is independent and parallel-safe; it may land before, during, or after T3–T5.

**Estimated commit count for continuation:**
- T2.5-RES (Path b, see §4): 2 commits (KI-NEW-H scope card + ARCHITECTURE_PLAN amendment + doc-only T2.5 closeout note). No code.
- T3 + T3.5: 2 commits.
- T4 + T4.5: 2 commits.
- T5 + T5.5: 2 commits.
- T6 + T6.5: 2 commits.
- Sprint-close doc sweep (memory.md, KNOWN_ISSUES.md, this plan archive): 1 commit.
- **Total: ~11 commits.**

---

## 3. Per-ticket specs

### T3 — B-3 `discount_dependency_hygiene` observed effect (Beauty only)

- **Scope.** Revenue-weighted two-proportion z-test on `heavy_discount_share_of_revenue_l28` recent-vs-prior (plan §III B-3:244-246). For each window W ∈ {L28, L56, L90}: anchor at `maxd - W`; recent numerator = revenue from heavy-discount cohort orders in `(anchor, maxd]`; recent denominator = total revenue in same interval. Prior is the same metric shifted back W days. Cohort definition follows the M3 builder at `src/audience_builders.py:736-887` (median order discount % over L90 ≥ vertical threshold; ≥2 orders). Welch fallback NOT used here — the metric is a revenue-weighted proportion, route through T0 `compute_two_proportion_observed` with `k` = round(heavy_revenue) and `n` = round(total_revenue) to preserve revenue-weighting semantics. Supplements untouched (`vertical=="supplements"` short-circuits to `(None, None)` per DS Memo-4 REJECT precedent).
- **Files touched.** `src/measurement_builder.py` (new `compute_discount_hygiene_observed_effect` adjacent to `compute_replenishment_observed_effect` at L1107; new `observed_discount_hygiene_enabled` kwarg threaded into `build_prior_anchored_play_card` next to the existing T1/T2 enable kwargs at L1401-1444; new dispatch branch mirroring L1418-1444); `src/utils.py` DEFAULTS — add `ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE` default `"false"`; `src/main.py` — pass `observed_discount_hygiene_enabled=cfg["ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE"]` at the prior-anchored invocation site.
- **Acceptance criteria.**
  - Unit: revenue-weighting test asserts a heavy order of $200 contributes 200 to `k` (not 1).
  - Unit: supplements short-circuit returns `(None, None)`.
  - Tripwire-probe (pre-flip) on Beauty fixture: `observed_n > 0` AND `observed_k > 0` AND `posterior_value != prior_value` AND `sign_agreement_count >= 2`. If predicted-zero, name the upstream blocker (D-FLOOR-discount_dependency_hygiene or audience_floor); if floor-blocked, treat per §4 path-b precedent (scope a floor-recalibration ticket, do not regen fixture).
  - Flag-OFF parity: Beauty + Supplements sha256 byte-identical to current pins.
  - M0 goldens unchanged.
- **Test deliverables.**
  - Mechanism: extend `tests/test_s7_t1_discount_dependency_hygiene_builder.py` with 4 cases: revenue-weighting, supplements short-circuit, prior-zero short-circuit, three-window agreement.
  - Pinned-fixture: T3.5 atomic commit re-pins Beauty (Supplements unchanged).
- **Feature flag.** `ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE` (mirror T1's `ENGINE_V2_OBSERVED_EFFECT_WINBACK` naming). Default OFF at T3; T3.5 flips to ON atomically with Beauty re-pin.
- **Tripwire pre-flip discipline.** Author `scripts/s7_6_t3_5_probe.py` mirroring `scripts/s7_6_t1_5_probe.py`. Run it BEFORE drafting T3.5. If `observed_n == 0` on Beauty, the upstream blocker is the M3 builder's audience floor (D-FLOOR-discount_dependency_hygiene). DO NOT defer; instead, scope a floor-recalibration sub-ticket (T3-F) following the §4 Path-b template before T3.5. The wiring stays committed; only the activation waits.
- **Dependencies.** None beyond T0 (done). Independent of T4/T5/T6.
- **What stays unchanged.** `src/sizing.py`; supplements path; legacy `discount_hygiene` Recommended Experiment allowlist (KI-21); `_route_prior_unvalidated_holds` supplements PRIOR_UNVALIDATED refusal.

### T4 — B-4 `cohort_journey_first_to_second` observed effect (Berkson-protected)

- **Scope.** Two-proportion z-test on cohort-defined first-to-second rate (plan §III B-4:258-261). For each window W ∈ {L28, L56, L90}: define the cohort as customers whose first order falls in the **early half** of the window (per `tests/test_berkson_invariant.py` and `project_journey_p_zero.md`); `k` = those who placed a second order within 30 days of their first; `n` = cohort size. Prior window slides anchor back W days on the same early-half rule. MUST route the cohort denominator definition through (or mirror exactly) `calculate_journey_stats_single_window` — do not bypass; if no public helper exists, factor one and reuse.
- **Files touched.** `src/measurement_builder.py` (new `compute_journey_first_to_second_observed_effect`; new `observed_journey_enabled` kwarg + dispatch branch); `src/utils.py` DEFAULTS — add `ENGINE_V2_OBSERVED_EFFECT_JOURNEY` default `"false"`; `src/main.py` plumbing.
- **Acceptance criteria.**
  - `tests/test_berkson_invariant.py` continues to pass unmodified (tripwire only).
  - New test asserts the denominator at window W uses first-order dates in `[maxd - W, maxd - W/2)` (early-half), NOT `[maxd - W, maxd]` (full window).
  - Tripwire-probe: Beauty `observed_n > 0` AND `sign_agreement_count >= 2`. If zero, name upstream blocker (audience floor or insufficient first-buyer history) and apply §4 Path-b template.
  - Flag-OFF parity + M0 unchanged.
  - Supplements: card still routes through existing `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW` Considered path when the builder returns thin signal (preserves KI-20 contract).
- **Test deliverables.**
  - Mechanism: extend `tests/test_s7_t2_cohort_journey_first_to_second_builder.py` with 4 cases: early-half denominator assertion, Berkson regression re-run, three-window agreement, supplements thin-signal path.
  - Pinned-fixture: T4.5 atomic commit re-pins Beauty + Supplements.
- **Feature flag.** `ENGINE_V2_OBSERVED_EFFECT_JOURNEY`. Default OFF; T4.5 flips.
- **Tripwire pre-flip discipline.** `scripts/s7_6_t4_5_probe.py`. Predict `observed_n` first. Berkson rule is a hard floor; if it's the cause of zero-n, that's an architectural lock, not a deferral candidate — escalate to founder rather than relax the rule.
- **Dependencies.** T0 (done). Independent of T3/T5.
- **What stays unchanged.** Berkson invariant test, `calculate_journey_stats_single_window` semantics, S5-T2 `SUPPLEMENT_CADENCE_OUTSIDE_WINDOW` typed reason, the existing legacy `first_to_second_purchase` directional builder (it's preserved per IM out-of-scope discipline; observed wiring lives on the new `cohort_journey_first_to_second` play_id).

### T5 — B-5 `aov_lift_via_threshold_bundle` observed effect (dual test, Beauty only)

- **Scope.** Dual-test combiner (plan §III B-5:275-276). Welch-t on audience-level L28 AOV (recent vs prior) AND two-proportion z-test on `near_threshold_aov_share` (orders in `[0.7×T, 0.95×T]` band). Both must reach `p < 0.10` jointly to set `eligible_observed=True` on the card's measurement payload. Audience-level AOV = per-order $ values for customers in the M3 audience; threshold T uses the T7 data-derived value (`AOV_BUNDLE_THRESHOLD_USD` from L90 P60 when available, cfg fallback otherwise — T7 already merged and ON). Multi-window sign-agreement on AOV delta across {L28, L56, L90}. Supplements unconditionally returns `(None, None)` per plan §III B-5:248 and the `vertical_excluded_per_b5_248` seam in `src/audience_builders.py:969-979`.
- **Files touched.** `src/measurement_builder.py` (new `compute_aov_bundle_observed_effect` returning `((welch_result, zprop_result), agreement)`; threading splits into two observed-effect channels — adapt the existing single-channel observed-effect signature by stashing both p-values into the agreement payload; do NOT break the T1/T2/T3/T4 single-channel contract); `src/utils.py` DEFAULTS — add `ENGINE_V2_OBSERVED_EFFECT_AOV_BUNDLE`; `src/main.py` plumbing.
- **Acceptance criteria.**
  - Unit: only-one-passes (Welch p=0.05, z-prop p=0.20) → `eligible_observed=False`.
  - Unit: both-pass (both p<0.10) → `eligible_observed=True`, sign-agreement reflects AOV delta direction.
  - Unit: supplements short-circuit returns `(None, None)` regardless of fixture.
  - Tripwire-probe Beauty: both p-values surfaced; `observed_n > 0` on near-threshold band. If predicted-zero on either test, name blocker.
  - Flag-OFF parity + M0 unchanged.
- **Test deliverables.**
  - Mechanism: extend `tests/test_s7_t3_aov_lift_via_threshold_bundle_builder.py` with 5 cases: dual-pass, only-Welch-passes, only-zprop-passes, both-fail, supplements-excluded.
  - Pinned-fixture: T5.5 atomic commit re-pins Beauty (Supplements unchanged).
- **Feature flag.** `ENGINE_V2_OBSERVED_EFFECT_AOV_BUNDLE`. Default OFF; T5.5 flips.
- **Tripwire pre-flip discipline.** `scripts/s7_6_t5_5_probe.py`. Beauty AOV distribution may be thin on the [0.7T, 0.95T] band; if `observed_n < 30` on the band, the blocker is fixture-density and falls under §4 Path-b template (audience-floor or fixture-shape scope ticket, not regen).
- **Dependencies.** T0 (done), T7 (done — T7.5 already flipped, threshold is data-derived).
- **What stays unchanged.** Threshold-from-data wiring (T7.5 locked); supplements vertical_excluded gate; legacy `aov_momentum` Tier-C fallback.

### T6 — Eligibility gate + 3-state copy ladder

- **Scope.** Two-part. (a) **Eligibility gate:** at the prior-anchored card seam (post-blend, pre-render), when `observed_n > cfg["OBSERVED_MIN_ELIGIBILITY_N"]` (default 30) AND `sign_agreement_count < 2`, downgrade the card from Recommended to Considered with `ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS`. When `observed_n <= cfg threshold`, no downgrade (cold-start path stays prior-only, unchanged). (b) **3-state copy ladder:** rotate the `why_now` copy by `posterior_ratio = observed_n / (observed_n + pseudo_n_effective)` into three buckets — cold (<0.2) keeps current prior-anchored copy; accumulating (0.2-0.6) prepends "Cohort signal is accumulating — "; mature (>0.6) prepends "Cohort signal dominates — ". Copy strings centralized as module constants in `src/measurement_builder.py`. No new render slot; reuse existing `why_now`.
- **Files touched.** `src/measurement_builder.py` (post-blend seam in `build_prior_anchored_play_card` ~L1500 region; new constants `_COPY_LADDER_*`); `src/decide.py` (if downgrade routes through a decide-layer helper rather than in-builder, route through the established C2 `apply_guardrails_to_injected` precedent — single-demote-channel invariant must hold); `src/utils.py` DEFAULTS — `ENGINE_V2_OBSERVED_ELIGIBILITY_GATE` default OFF + `OBSERVED_MIN_ELIGIBILITY_N` default 30.
- **Acceptance criteria.**
  - Sign-disagreement at n=200 with opposing-sign windows → card lands in Considered with `SIGNAL_INCONSISTENT_ACROSS_WINDOWS` reason; role-uniqueness invariant holds (Phase 6A B4).
  - Cold-start (n=0) → ladder = cold → why_now byte-identical to today.
  - n=100, all-positive-sign → Recommended, accumulating copy.
  - n=10000, all-positive-sign → Recommended, mature copy.
  - Flag-OFF parity + M0 unchanged.
  - Single-demote-channel invariant test (`tests/test_s7_6_c1_priority_prepend_invariant.py` or sibling) continues to pass.
- **Test deliverables.**
  - New `tests/test_observed_eligibility_gate.py` (5 cases).
  - New `tests/test_observed_copy_ladder.py` (3 ladder buckets + 2 boundary tests at 0.2 / 0.6).
  - Pinned-fixture: T6.5 atomic commit re-pins Beauty + Supplements with whatever ladder state each card lands in.
- **Feature flag.** `ENGINE_V2_OBSERVED_ELIGIBILITY_GATE`. Default OFF; T6.5 flips. `OBSERVED_MIN_ELIGIBILITY_N` configurable via env, default 30.
- **Tripwire pre-flip discipline.** `scripts/s7_6_t6_5_probe.py` enumerates per-card ladder state across all five Tier-B plays on Beauty. If any wired card unexpectedly lands in Considered with `SIGNAL_INCONSISTENT_ACROSS_WINDOWS` post-flip, escalate to founder before re-pin — it may indicate a real signal-quality finding (acceptable) or a builder bug (must fix).
- **Dependencies.** At least T3 and T4 must land (need ≥2 builders beyond T1 carrying non-zero observed_n to exercise the gate meaningfully on the fixture). T5 not required.
- **What stays unchanged.** `storytelling_v2` renderer surface (no new slot; copy goes into existing `why_now`); decide-layer slate selector and Recommended Experiment allowlist; role-uniqueness invariant; renderer-side forbidden-token sweeps.

---

## 4. T2.5-RESOLUTION — Path (b): re-evaluate D-S6-4 floor as a scoped sub-ticket

**Chosen: Path (b).** Rationale: the T2.5 deferred summary (`agent_outputs/code-refactor-engineer-s7_6-t2_5-deferred-summary.md`) explicitly REJECTED Path (a) (fixture regen) on the documented ground that synthetic fixtures encode plausible-merchant shape and must not be reshaped to flatter branch coverage. Path (c) "deferred with reason" is the status quo and the founder has directed "stop deferring." That leaves Path (b): treat the D-S6-4 N≥30 per-SKU floor as a scoped re-evaluation. This is NOT a tuning waiver — it is the surfacing of KI-NEW-H from "Phase 9 joint recalibration" to "S7.6-T2.5-RES scope card so we know what shape the answer takes."

**Ticket T2.5-RES — definition of done:**
- (1) DS-architect dispatch authors a scope card at `agent_outputs/ds-architect-s7_6-t2_5-res-d_s6_4-floor-scope.md` answering: Is N≥30 per-SKU the right shape for `replenishment_due` cohort-formation on representative merchant data, or is it tuned too tight? What would a defensible relaxation look like (lower N, alternative aggregation across SKU class, etc.)? Does relaxation require coupled adjustment of D-S6-5 and D-FLOOR-replenishment_due per KI-NEW-H?
- (2) The scope card lands as a docs commit; it does NOT change the floor. Floor change (if any) is a downstream founder-approved ticket, not part of S7.6.
- (3) If the DS-architect verdict is "the floor is correctly shaped and Beauty fixture is genuinely insufficient for this builder's cohort definition," the verdict gets appended to `ARCHITECTURE_PLAN.md` as a LOAD-BEARING UPDATE and T2.5 activation moves to "Phase 9 real beta data only" — but with an architectural rationale in the plan, not a KI-only deferral.
- (4) `KNOWN_ISSUES.md::KI-NEW-G` updated to cross-reference the scope card and clarify Phase 9 vs scope-card resolution.

**Why not Path (a):** Reshaping the Beauty fixture to flatter T2.5 violates the DS-locked synthetic-fixture-philosophy and would silently break the "this is what a merchant looks like" contract that downstream agents rely on.

**Why not Path (c) (status quo):** Founder direction is "stop deferring." Status-quo Path (c) is the deferral.

---

## 5. Risk register

**(a) Fixture-density risk — each new wiring may discover its observed_n is zero on Beauty.** Mitigation: every T*.5 has a tripwire probe script written and run BEFORE the .5 commit. If `observed_n == 0`, the ticket pauses and names the upstream blocker (audience floor, cohort-definition floor, or fixture-shape limit). No fixture regen; no flatter-the-test fixes. The upstream blocker becomes a scoped sub-ticket per §4 template. Risk severity: HIGH likelihood on T5 (Beauty AOV distribution may be thin on the near-threshold band).

**(b) Beauty + Supplements re-pin cascade as builders start emitting non-zero observed_n.** Mitigation: each T*.5 commit is atomic (flag flip + fixture re-pin in one commit, per S2 `45edaca5` precedent). M0 goldens must remain byte-identical because Tier-B builders don't surface in M0 small-fixtures; CI assertion enforced. PR template line "M0 sha256 unchanged: yes/no — if no, escalate." Re-pin order is serialized (T3.5 → T4.5 → T5.5 → T6.5) to avoid concurrent fixture-pin races. Risk severity: MEDIUM — well-understood mechanism from S7 precedents.

**(c) Cohort p-value gate × priority_prepend interaction.** With T6 live, some cards previously surfacing in Recommended via the post-S7.6 `priority_prepend` mechanism (`src/decide.py:825-842`) may demote to Considered with `SIGNAL_INCONSISTENT_ACROSS_WINDOWS` when their observed_n crosses the 30 threshold but sign-agreement drops below 2. This is the gate working as designed. Mitigation: T6 tripwire probe enumerates per-card ladder state and downgrade decisions across all five Tier-B plays on Beauty BEFORE T6.5 flip. Any unexpected demotion gets founder sign-off as a real signal-quality finding (acceptable) vs builder bug (fix-required). Risk severity: MEDIUM — the entire point of the gate is to demote inconsistent signals, but the cascade interaction with priority_prepend needs explicit verification.

**(d) T6 copy-ladder × storytelling_v2 renderer.** The 3-state ladder writes into the existing `why_now` slot; no new render surface. Renderer-side forbidden-token sweeps (Phase 6A B2) must not flag the prepended ladder strings — verify by extending the existing token-sweep tests with the three new copy prefixes ("Cohort signal is accumulating — " / "Cohort signal dominates — ") in the allowlist. Risk severity: LOW — additive copy in an existing slot.

---

## 6. Sprint exit criteria (testable)

At sprint close, ALL of the following must hold on the Beauty pinned fixture run:

1. Every `play_id` in `_PRIOR_ANCHORED` (`src/measurement_builder.py:717`) either (a) emits a card with `blend_provenance.observed_n > 0`, or (b) has a documented architectural carve-out citing source-of-truth (supplements B-3 → DS Memo-4 REJECT; supplements B-5 → plan §III B-5:248; supplements B-2 → KI-27; B-2 Beauty → T2.5-RES verdict).
2. Every wired card carries `observed_sign_agreement_count` and `observed_dominant_sign` on its `blend_provenance` driver.
3. T6 eligibility gate ON: any card with `observed_n > 30` AND `sign_agreement_count < 2` is in Considered with `SIGNAL_INCONSISTENT_ACROSS_WINDOWS`; any card with `observed_n <= 30` is in its pre-T6 routing.
4. T6 copy-ladder ON: every wired card's `why_now` string matches one of the three documented ladder prefixes per its `posterior_ratio`.
5. Test suite: 1690p + ~20 new mechanism tests + ~10 new gate/ladder tests → target ~1720p / 14s / 4xf / 2xp. No regressions.
6. M0 goldens (small_sm, mid_shopify, micro_coldstart): byte-identical to S7.6-C3 baseline.
7. Beauty + Supplements pinned briefings re-pinned 4× over the sprint (T3.5, T4.5, T5.5, T6.5); each commit documents new sha256.
8. KI-NEW-G updated with T2.5-RES cross-reference; new KI for any genuine upstream blocker surfaced by §5(a) probes.

---

## 7. What stays unchanged (explicit no-touch)

- `src/sizing.py::bayesian_blend` EB math.
- Priors YAML files + DS Memos 1-4.
- Decide layer: role-uniqueness invariant, slate selector, Recommended Experiment allowlist, `apply_guardrails_to_injected` helper at `src/guardrails.py`, the single-demote-channel invariant.
- Renderer slate logic (Phase 6A/6B) + storytelling_v2 surface.
- `src/utils.py` DEFAULTS — only additive flag entries listed per ticket.
- M0 goldens.
- `recently_run` fatigue gate (Sprint 1 B-4, stays OFF).
- `src/memory/events.py` schema (frozen for Swarm per Sprint 2 S-3).
- Recommended-history JSON format.
- `tests/test_berkson_invariant.py` (tripwire only, never edited).
- `tests/test_s7_6_c1_priority_prepend_invariant.py` (Tier-B-presence invariant, tripwire only).
- S8-CL1/L2/L3 cleanup (KI-NEW-L/M/N) — deferred to S8 per founder direction; architectural cleanup, not provenance correctness.
- D-S6-4 / D-S6-5 / D-FLOOR-replenishment_due numeric values — T2.5-RES authors a scope card; floor changes (if any) are S8+ tickets.

---

## 8. What's NOT in this continuation plan (explicit non-goals)

- ModelFitStatus gate (S10-13 per ENGINE_OVERVIEW). Out of scope; this plan only completes the cohort p-value gate.
- Phase 9 outcome importer / calibration consumer wiring.
- Supplements B-2 observed-effect activation (KI-27 supplements replenishment parser is the upstream).
- Supplements B-3 observed-effect (DS Memo-4 REJECT).
- subscription_nudge / routine_builder observed-effect (Phase 4.2 deferred per project memory; outside `_PRIOR_ANCHORED`).
- Hard-vanish on sign-disagreement (T6 downgrades to Considered; hard-suppression is an S8 product call).
- 4th ladder state (mature+contradiction) — DS specified 3-state; expanding requires founder copy review.
- Real beta data ingestion / Shopify-Klaviyo production integrations.
- Big-bang refactor of the `_PRIOR_ANCHORED` dispatch (KI-NEW-L; deferred to S8).
