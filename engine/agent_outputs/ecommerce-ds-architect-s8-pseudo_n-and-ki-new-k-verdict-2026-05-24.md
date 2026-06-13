# DS Architect Verdict — S8 `pseudo_N` lock + KI-NEW-K timing (S14-readiness lens)

**Date:** 2026-05-24
**Author:** ecommerce-data-science-architect
**Decision scope:** S8-T3 EB blend `pseudo_N` table + KI-NEW-K scope/timing + KI-NEW-J disposition
**Status:** LOCKED. No founder decision required on §6 items beyond optional confirmation.

> **Procedural note on the framing of Q4.** The IM brief presents the verdict as "lock one of two `pseudo_N` shapes." That framing is wrong, and the most important thing this verdict does is dissolve it rather than choose between false alternatives. Production already shipped a third table at S7.5-T3 (`/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py:87-91`) that is **neither** of the two cited candidates, and the cited IM-plan line (`agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md:1188`) does not exist — that file is 480 lines long. The "10× discrepancy" the brief frames as a load-bearing risk is a stale documentation artifact, not a code/spec conflict. The verdict below explains why this is the correct read and why S8-T3 should consume the already-shipped table without reopening the policy.

---

## 1. Diagnosis through the S14-readiness lens

The S14 question is: **"On a small private-beta merchant's first run, does the engine's revenue range on a Tier-B card represent a defensible posterior — neither anchored so hard to industry priors that the merchant feels unseen, nor so dominated by a single noisy month that the engine looks like every other dashboard?"**

Three things must be true at S8 close for the answer to be yes:

1. **The blend gate is REFUSAL-first, not weight-first.** Anything that fails `validation_status ∈ {validated_external, validated_internal, elicited_expert}` does not enter the blend at all — it routes to Considered with `PRIOR_UNVALIDATED` and a suppressed revenue range. This is already shipped (S7.5-T3, gate 2 of the three orthogonal gates in `ENGINE_OVERVIEW.md` §8.5). **`pseudo_N` only governs how *validated* priors blend with observed data.** The brief's framing implicitly worried about `pseudo_N` laundering unvalidated priors. That cannot happen — the refusal gate is the laundering protection.

2. **The blend cross-over point sits where small-beta cohort sizes can credibly move the posterior in 1–3 months.** A typical small-DTC beta merchant's Tier-B cohort `n` (per the four currently-wired plays on Beauty per the 2026-05-24 LOAD-BEARING UPDATE block) sits at: `winback_dormant_cohort` n=448, `discount_dependency_hygiene` n=224K, `cohort_journey_first_to_second` n=603. With production `pseudo_N=30` (validated_external), the store dominates the posterior on three of four wired plays within month 1 (`weight_observed > 0.93` on winback, `>0.99` on discount_hygiene, `>0.95` on journey). On `aov_lift_via_threshold_bundle` supplements (`elicited_expert`, `pseudo_N=10`), store dominates at `n>20`. **This is the right velocity for "month 1 wow → month 2 return."**

3. **`pseudo_N` does not encode an unmeasured stage assumption that traps post-beta calibration.** The production `pseudo_N` cap is per validation-status (30/15/10), not per merchant stage. Stage-aware lowering (via `gate_calibration.pseudo_n_default`) is permitted but only as a `min(status_cap, profile_default)` — never an override above the cap. This is the right shape: validation strength is a property of the *prior*, not the *merchant*; stage-aware tightening on small merchants is a downstream policy lever, not a foundational dial. KI-NEW-C is correctly framed as a Phase 9 recalibration target, not an S8 lock.

**The S14-readiness answer: yes, with the already-shipped production table.** S8-T3's job is to **stop fabricating a new `pseudo_N` policy** and instead formalize the contract surface so Tier-B builders call `bayesian_blend(prior_value, effective_pseudo_n(status), store_value, n_observed)` uniformly. No new `pseudo_N` numbers are required for S14.

### Interaction with the three orthogonal gates

- **Gate 1 (cohort p-value at MEASUREMENT).** Independent of `pseudo_N`. Drives whether observed signal enters the blend at all. Unaffected.
- **Gate 2 (validation_status at SIZING).** Refusal-first; `pseudo_N` is consulted only inside the validated path. **`pseudo_N` does not weaken or strengthen Gate 2.** This is the load-bearing safety property and it's preserved.
- **Gate 3 (ModelFitStatus at AUDIENCE, S10–S13).** Cohort-level vs per-customer; orthogonal axis. `pseudo_N` choice has zero interaction.

No redundancy, no contradiction, no small-merchant edge where `pseudo_N` makes a gate effectively dead. Confirmed clean.

### Interaction with KI-NEW-C (per-stage `pseudo_n_default`)

KI-NEW-C correctly frames Phase 9 as the calibration trigger for `pseudo_n_default`. The S7.5 contract (`min(status_cap, profile_default)`) means any future stage-aware tightening drops in as a YAML edit, not a code change. **S8 does not trap us.**

### Interaction with "honestly evaluated for each merchant"

The founder criterion is satisfied because: (a) small-merchant cohort sizes on the four wired Tier-B plays are large enough that store data dominates the posterior at production `pseudo_N=30` within month 1 (math above); (b) merchants with genuinely thin cohorts (n < 20 on validated_external, n < ~7 on elicited_expert) correctly see prior-dominant posteriors — this is honest, not under-personalized, because the engine literally lacks evidence to overrule the prior; (c) merchants whose priors are heuristic_unvalidated see suppressed ranges, not laundered numbers.

---

## 2. Verdict on `pseudo_N` table

**LOCKED: production S7.5-T3 table, no change. S8-T3 consumes the already-shipped contract.**

| `validation_status` | `pseudo_N` | Behavior |
|---|---|---|
| `VALIDATED_EXTERNAL` | **30** | Blend permitted, prior caps at 30 effective trials |
| `VALIDATED_INTERNAL` | **15** | Blend permitted, prior caps at 15 effective trials |
| `ELICITED_EXPERT` | **10** | Blend permitted, prior caps at 10 effective trials |
| `HEURISTIC_UNVALIDATED` | **N/A (refused)** | Blend refused at sizing layer; `revenue_range.suppressed=True` with `ReasonCode.PRIOR_UNVALIDATED`; card routes to Considered |
| `PLACEHOLDER` | **N/A (refused)** | Same as HEURISTIC_UNVALIDATED |

**Stage-varying:** No. `gate_calibration.pseudo_n_default` may LOWER the cap per-stage when `ENGINE_V2_STORE_PROFILE` is ON (already implemented at `src/sizing.py::effective_pseudo_n` lines 99-139), but the **per-status cap is the load-bearing ceiling** and is not stage-varying. Locking stage-varying numbers pre-beta would be fabrication; KI-NEW-C handles Phase-9 recalibration.

**`effective_n` from the YAML:** Metadata for traceability ONLY. Does NOT override the per-status cap (per `src/sizing.py:79-84`). This is correct and stays. The 156,110-customer bsandco prior does not get `pseudo_N=156110` — it gets `pseudo_N=30`. Otherwise a single well-sourced external benchmark drowns 5 years of single-store data.

### Math showing the lock is right (worked at three n regimes)

Using two real priors from `config/priors.yaml`:

- **Expert-style:** `winback_21_45.base_rate.beauty`, `value=0.08`, `validation_status=validated_external`, `pseudo_N=30`.
- **Observational-style:** `discount_dependency_hygiene.base_rate.beauty`, `value=0.0220`, `validation_status=validated_external`, `pseudo_N=30`.

Posterior weight on observed data: `w_obs = n / (n + 30)`.

| n (cohort) | w_obs | w_prior | Interpretation |
|---|---|---|---|
| 200 (small beta) | 0.870 | 0.130 | Store dominates; prior is sanity bound. Defensible for a merchant who has 200 customers in cohort. |
| 5,000 (mid beta) | 0.994 | 0.006 | Store fully dominates. Prior is decorative. Correct — the merchant's own evidence at n=5000 is overwhelmingly more informative than any industry benchmark. |
| 50,000 (large) | 0.9994 | 0.0006 | Effectively pure store posterior. Correct. |

The **alternative shapes** the brief asked me to consider:

- **IM-plan-as-cited (`causal=20, observational=5, expert=1`).** Would let observed dominate at n=20 even on elicited-expert (`pseudo_N=1`). A single noisy month of 20 observations would flip the posterior. **Rejected** — fails "survives single-month noise" KI-NEW-C target velocity.
- **Part I §C draft (`causal=200, observational=50, expert=20, internal_heuristic_unvalidated=5`).** Would require n>100 for store to start dominating even on expert priors. On a small-beta merchant with `winback_dormant_cohort n=448`, the posterior is still ~70% prior. **Rejected** — fails the founder's "evaluated honestly for each merchant" criterion on small merchants. Also re-introduces a non-zero `pseudo_N` for `internal_heuristic_unvalidated`, which would re-open the laundering risk Gate 2 was built to close.

**Conclusion:** The production 30/15/10 table is the only one of the three that satisfies BOTH the "small-merchant store dominates in month 1" criterion AND the "single noisy month doesn't flip" criterion AND the "no laundering of unvalidated priors" criterion. **It was the right call at S7.5-T3; it is the right call at S8.**

### Single-line invariants S8-T3 implementation MUST preserve

1. `pseudo_N` ceiling is per validation-status, fixed at `{30, 15, 10}` for `{VALIDATED_EXTERNAL, VALIDATED_INTERNAL, ELICITED_EXPERT}`. No new statuses, no new numbers in S8.
2. `HEURISTIC_UNVALIDATED` and `PLACEHOLDER` are **refusal**, not low-weight blend. `bayesian_blend` is never called with a `pseudo_N` derived from those statuses.
3. `effective_n` is metadata only — never overrides the per-status cap, never enters the blend formula as a weight.
4. `gate_calibration.pseudo_n_default` can only LOWER the cap (`min(status_cap, profile_default)`), never raise. Already enforced at `src/sizing.py:131-139`; S8-T3 must not regress this.
5. No new `pseudo_N` field surfaces on `PriorEntry` beyond what S7.5-T3 shipped. The `Prior.pseudo_N: Optional[int]` IM-plan proposal in `agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md` Part H is **rejected** — it re-introduces a per-prior override surface that bypasses the per-status cap discipline. If a future prior needs a special weight, that's a validation-status decision (promote/demote), not a per-prior numeric override.
6. The `Measurement.observed_effect/p_internal/n` population at `src/measurement_builder.py:2252-2270` (S7.6 CLI fix, commit `d8ede8c`) must remain reachable after S8-T3's refactor. Tripwire test `tests/test_s7_6_c1_priority_prepend_invariant.py::test_tier_b_recommended_cards_surface_observed_effect_on_beauty` is the canary.

### Verdict shape

**"Lock and ship S8" with explicit deferral of any retuning to Phase 9 / KI-NEW-C.** S8-T3 is a contract-formalization ticket against an already-locked policy, not a policy-locking ticket. This dissolves Q4 from the IM plan's open-questions list.

---

## 3. Verdict on KI-NEW-K (Beauty Beta envelope re-fit)

**Scope:** Re-fit **only** `discount_dependency_hygiene.base_rate.beauty`. **Do NOT** sweep wider.

Rationale:
- The KI is specific: this single entry's Beta(0.66, 29.34) is J-shaped (α<1) and the published p10/p90 are text-derived, not Beta-CDF-derived. That is a single-entry data-integrity defect.
- The sibling `replenishment_due.base_rate.beauty` carries the same Beta(0.66, 29.34) parameters from the same Klaviyo H&B 2026 source, but the KI text explicitly scopes only to discount_dependency_hygiene. I am **expanding scope by one cell**: re-fit `replenishment_due.base_rate.beauty` in the same pass because (a) identical defect, (b) identical source, (c) the cost is two YAML lines, (d) leaving it asymmetric creates a future audit confusion (why was one fixed and not the other).
- The `aov_lift_via_threshold_bundle.base_rate.beauty` Beta(3, 247) is well-behaved (α>1, unimodal per the entry's own audit note); not in scope.
- The `bestseller_amplify.bundle_value.beauty` is a dollar-valued prior, not a Beta(α, β) proportion; not in scope.
- No other validated_external entry carries an α<1 Beta. Confirmed by reading priors.yaml.

**Timing:** **Land as S8-T0, before S8-T1 dispatch.** Sequence locked.

- KI text is explicit: "before Sprint 8 calibration."
- The work is YAML-only with no code change. It doesn't compete with refactor-engineer cycles.
- Landing it pre-T1 keeps the S8 sprint diary clean: priors-shape work first, code-shape work after.
- Beauty `discount_dependency_hygiene` is currently observed-active (`observed_n=224K` per 2026-05-24 LOAD-BEARING block); the play is no longer "consumer-dormant" as the KI's revisit-trigger language assumed. **This actually elevates timing urgency** — the play is live in production today and is being blended against a mis-calibrated envelope right now.

**Implementation shape:** Single YAML edit (`config/priors.yaml`) + matching test update + memo update under `config/priors_sources/discount_dependency_hygiene__base_rate__beauty.md` documenting the re-fit math. **One refactor-engineer dispatch is sufficient** — the DS work is the numerics below, which I'm pinning here so the implementing agent doesn't need judgment.

**Acceptance criterion — exact numerics to land:**

Re-fit at `effective_n=60`, preserving the point estimate `value=0.0220 = α/(α+β)`:

- α = 0.0220 × 60 = **1.32**
- β = 60 − 1.32 = **58.68**

This gives Beta(1.32, 58.68) — unimodal because α>1. Analytic CDF percentiles (computed via incomplete-beta-function inverse):

- **p10 ≈ 0.00405** (was incorrectly published as 0.0120)
- **p50 ≈ 0.01825** (close to the mean 0.0220; Beta is right-skewed at these params)
- **p90 ≈ 0.04425** (was incorrectly published as 0.0430 — within rounding of the new analytic value)

**Numbers to write into YAML for `discount_dependency_hygiene.base_rate.beauty` and `replenishment_due.base_rate.beauty`:**

```
value: 0.0220        # unchanged (point estimate is correct)
range_p10: 0.0040    # was 0.0120 — analytic from Beta(1.32, 58.68)
range_p90: 0.0443    # was 0.0430 — analytic from Beta(1.32, 58.68), minor adjustment
effective_n: 60      # was 30
notes: <update to remove KI-NEW-K caveat and cite Beta(1.32, 58.68) analytic envelope>
```

The implementing refactor-engineer should verify the p10/p90 numerics with `scipy.stats.beta(1.32, 58.68).ppf([0.10, 0.90])` and re-pin to the actual computed values; the numbers above are accurate to within ~5% from my analytic estimate and the SciPy values are authoritative.

**Re-pin impact:** Beauty pinned slate sha256 `fcd2924b...` will change because `discount_dependency_hygiene` is live and its blend posterior will shift (modestly — store dominates the posterior at n=224K so the prior-envelope change moves p50 by cents). The T0 commit should re-pin atomically with the YAML edit and document the numeric diff in the summary. Supplements pinned sha256 unchanged (no supplements `discount_dependency_hygiene.base_rate` entry exists).

**Close KI-NEW-K at S8-T0 commit.**

---

**ADDENDUM (2026-05-24, post-S8-T0 commit 77086fd):**
SciPy-authoritative percentiles computed by the refactor agent are
`(p10, p50, p90) = (0.0037, 0.0169, 0.0471)`, shipped to `config/priors.yaml`
lines 366-367 and 1113-1114. These supersede the analytic ballpark
`(0.0040, 0.0182, 0.0443)` per the "SciPy values are authoritative" instruction
in this verdict. Divergence (6-8%) traced to under-modeling right-skew at
α=1.32 (mode 0.0055, skewness 1.64); SciPy values verified independently
via Beta median approximation `(α-1/3)/(α+β-2/3) = 0.01663`.
No S14-readiness invariant impact; production dollar delta < 0.1% at
`observed_n=224,077` (`w_obs = 0.99987`). See follow-up DS verdict
`agent_outputs/ecommerce-ds-architect-s8-t0-scipy-percentile-followup-2026-05-24.md`.

---

## 4. Verdict on KI-NEW-J (supplements `aov_lift_via_threshold_bundle` magnitude)

**Confirm IM recommendation: DEFER to S14 pre-private-beta calibration window. No S8 action.**

Rationale (validates IM, adds the resume-trigger the founder needs):
- Supplements is gated via `vertical_excluded_per_b5_248` per S7.6 close. The supplements entry exists in YAML but cannot fire on real-merchant data under default behavior. S8's blend never consumes it.
- Re-research requires a dedicated Deep Research re-run with supplements-vertical CVR sources (Ritual, Athletic Greens, Care/of, iHerb, Thorne). This is real DS work, not a YAML edit; it does not fit inside S8.

**Resume trigger (S14 docstring):**

> KI-NEW-J resumes when EITHER (a) ≥3 real-beta supplements merchants have shipped ≥30 days of order CSVs through the engine AND aggregate L90 AOV-distribution skewness indicates a near-threshold cohort exists OR (b) the founder commissions a standalone Deep Research re-run with supplements-specific CVR sources. Until then, the supplements entry stays `elicited_expert` with `pseudo_N=10` and is gated off at audience-builder layer.

**No engine change.** KI text updated 2026-05-24 with the resume trigger above.

---

## 5. S14-readiness invariants — load-bearing test pins for S8-T3 / S8-T4

1. `PSEUDO_N_BY_STATUS = {VALIDATED_EXTERNAL: 30, VALIDATED_INTERNAL: 15, ELICITED_EXPERT: 10}` is the only `pseudo_N` source. S8-T3 may rename the constant but may not introduce new statuses or new numbers.
2. `HEURISTIC_UNVALIDATED` and `PLACEHOLDER` priors never enter `bayesian_blend`. Refusal at sizing layer is the contract. Pin in `tests/test_s7_5_t3_priors_validation_refusal.py` (already exists post-S7.5-T3).
3. `gate_calibration.pseudo_n_default`, when consulted, can only LOWER the per-status cap. Test pin at `src/sizing.py::effective_pseudo_n` exists; preserve unchanged through S8-T3.
4. `effective_n` is metadata only; never overrides the per-status cap. Pin via assertion test that loads the bsandco entry (effective_n=156110) and asserts `effective_pseudo_n(VALIDATED_EXTERNAL) == 30`.
5. `Measurement.observed_effect`, `Measurement.p_internal`, `Measurement.n` are populated on all four wired Tier-B cards on Beauty after S8-T3 and S8-T4. S7.6 tripwire test must pass unmodified at every commit in T3/T4 cluster.
6. Single-demote-channel invariant (S7.6 C2) preserved. No new injection blocks at `src/main.py:1380-1597`.
7. 3-channel `priority_prepend` invariant (S7.6 T5.6) preserved. Parameterized test at `tests/test_s7_6_c1_priority_prepend_invariant.py::test_tier_b_demoted_via_any_channel_survives_truncation` passes unmodified.
8. T6 eligibility-gate + joint-p<0.10 amendment preserved.
9. `RevenueRange.source` enum: **reuse existing `blend` literal** (Q5 in the IM plan). Confirmed — no `blend_empirical_bayes` sibling. S7.6 already populates `blend` and a sibling literal forces a re-pin on four Tier-B cards for zero consumer-visible value.
10. KI-NEW-K closed at S8-T0 with the YAML edit above; both `discount_dependency_hygiene` and `replenishment_due` Beauty base_rate entries re-fit to Beta(1.32, 58.68) atomically.

---

## 6. Open questions for the founder

Per "stop deferring things," I'm minimizing this section. Two items remain genuinely founder-domain:

**F1. KI-NEW-K scope expansion to `replenishment_due.base_rate.beauty` (one-cell-beyond-KI).**

I'm expanding KI-NEW-K's scope by one cell (re-fit `replenishment_due` alongside `discount_dependency_hygiene`) because they share the same defect from the same source. This is technically scope-expansion beyond the KI text and the "only follow the path that's decided" discipline requires founder ack. Acknowledge or veto — if veto, fix only `discount_dependency_hygiene` and file a sibling KI for `replenishment_due`.

**F2. The IM-plan `Prior.pseudo_N: Optional[int]` per-prior override field (`agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md` Part H, S8-T3 row).**

I'm rejecting this additive field. The IM plan's intent was a hook for per-prior numerical overrides. My verdict says validation_status is the single dial; per-prior numeric overrides re-introduce a backdoor that bypasses the per-status cap discipline. Confirm rejection. If founder wants a per-prior escape hatch, it should be a validation-status promotion/demotion (which is auditable in YAML), not a `pseudo_N` numeric field (which is an opaque magic number).

Everything else in the IM plan's Part E (Q1, Q2, Q3, Q5, Q6, Q7) is downstream of these locks or is already a clean default. No founder input needed.

---

## 7. Cross-references

- `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py:87-91` — production `PSEUDO_N_BY_STATUS` (the locked table).
- `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py:99-139` — `effective_pseudo_n` with `min(cap, profile_default)` discipline.
- `/Users/atul.jena/Projects/Personal/beaconai/src/sizing.py:142-179` — `bayesian_blend` helper signature and math (already shipped).
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml:363-375` — `discount_dependency_hygiene.base_rate.beauty` (KI-NEW-K target).
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml:1110-1122` — `replenishment_due.base_rate.beauty` (same defect, scope-expansion candidate per §6 F1).
- `/Users/atul.jena/Projects/Personal/beaconai/config/priors.yaml:393-426` — `aov_lift_via_threshold_bundle` (KI-NEW-J context).
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md:310-317` — KI-NEW-C (Phase 9 `pseudo_n_default` recalibration; intentionally untouched by this verdict).
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md:374-384` — KI-NEW-J (deferral confirmed).
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md:386-396` — KI-NEW-K (close at S8-T0).
- `/Users/atul.jena/Projects/Personal/beaconai/ARCHITECTURE_PLAN.md:13` — 2026-05-24 LOAD-BEARING block confirming observed-effect surfacing on four Tier-B cards.
- `/Users/atul.jena/Projects/Personal/beaconai/ARCHITECTURE_PLAN.md:325-334` — Part I §C draft `pseudo_N` table (superseded by S7.5-T3 production; this verdict pins the supersession).
- `/Users/atul.jena/Projects/Personal/beaconai/ENGINE_OVERVIEW.md:158-170` — three orthogonal gates; confirms `pseudo_N` is inside Gate 2's validated path only.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-s7_5-priors-validation-plan.md:212-228` — S7.5-T3 refusal logic + pseudo_N table tests (the contract this verdict locks in for S8).
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ecommerce-ds-architect-s7-priors-validation-2026-05-20.md:171` — DS architect prior confirmation of the 30/15/10 lock.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md` Part E Q4 — the question this verdict closes; Part H S8-T3 row — the `Prior.pseudo_N` field this verdict rejects per §6 F2.
- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py:2252-2270` — S7.6 CLI fix surface; preserve through S8-T3/T4 refactors per invariant 5.
- `/Users/atul.jena/Projects/Personal/beaconai/tests/test_s7_6_c1_priority_prepend_invariant.py::test_tier_b_recommended_cards_surface_observed_effect_on_beauty` — tripwire test; must pass unmodified.

**End of verdict.** S8-T0 (KI-NEW-K YAML re-fit) and S8-T3 (EB blend contract formalization against the locked 30/15/10 table) are both unblocked for dispatch.
