# Baseline Acceptance and Campaign Slate Contract

Reconciled output from product-strategy-pm and ecommerce-ds-architect reviews, 2026-05-04. Both reviews are saved at `agent_outputs/product-strategy-pm-baseline-and-campaign-slate.md` and `agent_outputs/ecommerce-ds-architect-baseline-and-campaign-slate.md`.

Where PM and DS diverge, this file reflects the more conservative position and flags the disagreement explicitly. The conservative position is favored because the user's hard constraints prohibit lowering materiality, restoring fake stats, or weakening the existing honesty contract.

## Baseline Verdict

**Accepted with caveats.**

Both PM (Accepted with caveats) and DS (Acceptable with caveats) re-verified the baseline independently and arrived at the same conclusion. The 11 synthetic blocker fixes are the new product baseline. The canonical Beauty Brand reference output is `agent_outputs/synthetic_fixes_8_11_samples/healthy_beauty_240d_briefing.html` (post-blocker-pass), with `agent_outputs/phase5_samples/beauty_brand_engine_run.json` as the corresponding receipts file.

## Baseline Caveats

1. **Single-fixture-family directional fires.** `first_to_second_purchase` directional fires on three of six fixtures because they share the same generator family producing strongly positive returning-share trends. Do not over-generalize "engine works on healthy stores" from this evidence. (PM caveat 5; DS Part 1 §5.)

2. **`returning_customer_share` is a state statistic, not an intervention effect.** The directional card's defensibility rests entirely on three forcing functions: `revenue_range.suppressed=true` with provenance `directional_no_intervention_effect`, the Phase 5.1 opportunity-context block with the "This is not projected lift" disclaimer, and `evidence_class=directional` (never `measured`). All three must remain in place. (DS Part 1 §4.)

3. **Considered list is repetitive.** Six cards collapsing to `no_measured_signal` looks indistinguishable to a merchant and undermines play differentiation — the principal product-quality reason to evolve to a slate. (PM caveat.)

4. **Inventory loader bug at `src/load.py:626`** (pandas `groupby().apply().reset_index(name=...)` `TypeError`) blocks low-inventory e2e validation of the Fix 4 `inventory_blocked` Considered card. Fix 4 plumbing is structurally correct and unit-tested with synthetic `inventory_metrics`. One-line engineering fix. Defer; not slate-blocking.

5. **AnomalousWindowCheck not auto-registered in V2.** `promo_anomaly_240d` publishes a directional card on returning-share rather than abstaining on the spike. Phase 6 work, not slate-blocking.

6. **`empty_bottle` ml/oz parser** does not yet handle ct/lb/mg variants. `subscription_nudge` substitutes adequately for the supplement vertical's first ship. Phase 6, not slate-blocking.

## Blocking Issues, If Any

**None.** Neither PM nor DS found a baseline-blocking issue or a slate-blocking issue. The deferred items above are noted and tracked but do not block campaign-slate work.

## Campaign Slate Verdict

**Proceed to implementation planning.**

Both reviewers agreed the slate evolution is the right structural move. DS imposed material tightening on PM's proposal, summarized below. The reconciled scope below is the DS-tightened version (smaller surface, harder eligibility), which is what implementation planning should consume.

## Recommended Merchant-Facing Sections

Reconciled to **four sections** for first ship (DS argued to defer Lifecycle Maintenance until the outcome log is non-stub; PM proposed five). Order on `briefing.html`:

1. **State of Store** (existing, unchanged)
2. **Recommended Now** — measured/directional only (replaces current Recommended)
3. **Recommended Experiment** — high-quality targeting plays explicitly framed as send-and-measure
4. **Watching** (existing, cap reduced 7 → 4)
5. **Held / Considered** (existing, unchanged)
6. Data-quality footer (existing)

**Disagreement to resolve in implementation planning:** PM proposed shipping Lifecycle Maintenance as a fifth section in the first ship; DS argued to defer Lifecycle until `recommended_history.json` is non-stub (M9 calibration_stub currently returns `{}`), because Lifecycle without a recently-run-fatigue gate becomes a nag-loop and is structurally indistinguishable from Recommended Experiment.

**Reconciled position: defer Lifecycle.** Reasoning: it does not satisfy the user's "ML-readiness" intent without an outcome-log read, and shipping two near-identical sections (Recommended Experiment and Lifecycle) creates merchant confusion before the engine can differentiate them on real evidence. Reintroduce as Phase 6 work once the outcome-log feedback loop exists.

## Play Role Definitions

For each role: definition, merchant promise, expected count.

**Recommended Now**
- Definition: Plays with measured or directional evidence that cleared materiality, cannibalization, and inventory gates this run.
- Merchant promise: "Run this campaign this month; we have signal in your data that supports it."
- Expected count: 0–2. Healthy stores typically 1; ABSTAIN_SOFT stores 0.

**Recommended Experiment**
- Definition: Targeting plays with non-trivial audience and clear merchant-readable mechanism, framed as send-and-measure pilots, not as forecasted lift.
- Merchant promise: "Run this as an experiment; we will measure the result and learn whether it works for your store."
- Expected count: 0–2 (DS-tightened from PM's 0–3). Always 0 under ABSTAIN_SOFT (Fix 3 contract extends here).

**Watching**
- Definition: Metrics trending but not yet at threshold to recommend; or load-bearing metrics flat.
- Merchant promise: "Nothing to do; we're watching these and will surface a play if they cross threshold."
- Expected count: 0–4 (cap reduced from 7).

**Held / Considered**
- Definition: Plays that ran through the candidate pipeline and were rejected with a typed reason code.
- Merchant promise: "Here's what we considered and why we didn't surface it. Each one has a 'would fire if...' so you know what would unlock it."
- Expected count: 3–6.

**Lifecycle Maintenance** — DEFERRED. Definition retained for future reintroduction: cadence-driven, always-on plays the merchant should run continuously regardless of monthly variance. Phase 6.

Total visible play cards on first-ship slate: 0–6 (vs current 1–9).

## Eligibility Rules By Role

**Recommended Now**
- `evidence_class ∈ {measured, directional}`
- `consistency_across_windows >= 2`
- `p_internal < 0.05` (internal-only, never rendered)
- Audience clears scale-aware materiality
- Passes inventory + cannibalization gates
- `measurement` non-null
- Eligible play_types (current): `first_to_second_purchase` (Phase 5.6 directional pathway). Future measured/directional plays as they land.

**Recommended Experiment** (DS-tightened first-ship allowlist)
- `evidence_class == targeting`
- Audience ≥ play-specific floor (per-play in `config/priors.yaml`, NOT a global floor)
- Play has documented `mechanism` in `config/priors.yaml`
- Play has `vertical_applicable: true` for current `VERTICAL_MODE`
- `would_be_measured_by` non-null and enum-valid (mandatory PlayCard contract field)
- No inventory block
- Audience overlap with Recommended Now < 30% (cannibalization gate)
- Slate diversity: no two Recommended Experiment cards may target the same audience archetype in one run
- Recently-run fatigue: not run in prior 14 days per outcome log (NO-OP today; activates when M9 outcome log exists)
- **First-ship eligible play_types: `discount_hygiene` and `bestseller_amplify` only.** Both have clear, documented mechanisms.
- Held until outcome-log evidence: `winback_21_45`, `routine_builder`, `subscription_nudge`. These remain in Considered until the outcome log shows merchant adoption and a documented mechanism is added to `config/priors.yaml`.

**Watching**
- Trending or load-bearing metric with named threshold and named would-fire `play_id`
- `change_magnitude` resolves cleanly
- Cap 4
- Prioritization must keep load-bearing flat metrics (`returning_customer_share`, `net_sales`, `repeat_rate_within_window`, `aov`) ahead of small movers (Phase 5.3 guarantee)
- Pin a test on `small_store_240d`: if any of the four load-bearing metrics is computable, at least one must surface in Watching

**Held / Considered**
- Typed `ReasonCode`, populated `reason_text`, populated `would_fire_if`
- No change from current shipping behavior

**Cross-role rules**
- A play may be eligible for multiple roles across runs but appears in **only one role per run**. Pin as a structural assertion in `decide.py`.
- Priority order: Recommended Now > Recommended Experiment > Considered. Watching is a separate metric track, not a play track.

## Economic Context Rules By Role

**Recommended Now**
- Allowed: addressable-value block (audience × AOV, magnitude-banded, "about $X" rounding) with the "This is not projected lift" disclaimer rendered verbatim; audience size; primary-window AOV; suppressed `revenue_range`.
- Forbidden: `revenue_range.p50` headline, standalone $ p50, p/q/CI, "expected lift," "forecast," numeric confidence percentage.

**Recommended Experiment**
- Allowed: same opportunity-context block, same disclaimer; explicit "Send to N people" framing; `would_be_measured_by` metric name visible.
- Forbidden: $ headline larger than the range chip (M8 invariant); any statistical claim; "evidence," "measured," "lift," "uplift," "ATE," "ITT," "expected lift," "projected," "forecast," "predicted."

**Watching**
- Allowed: trend direction, threshold-to-act copy, named would-fire play.
- Forbidden: dollar context, predictive claim.

**Held / Considered**
- Allowed: typed `reason_text`, `would_fire_if`, `evidence_snapshot` (audience + segment definition).
- Forbidden: dollar context, $ value, statistical claim.

## Beauty Brand Expected Output

Under the reconciled (DS-tightened) first-ship contract, using the post-Fix-8/9/10/11 audiences from `agent_outputs/synthetic_fixes_8_11_samples/healthy_beauty_240d_briefing.html`:

- **Recommended Now (1)**: `first_to_second_purchase` — audience 5,560, addressable order value about $329k, directional, suppressed `revenue_range`, "not projected lift" disclaimer. Unchanged from current.
- **Recommended Experiment (2, hard cap)**: `discount_hygiene` (audience 2,251) and `bestseller_amplify` (audience 1,475). Both with `would_be_measured_by` enum populated, `revenue_range.suppressed=true`, "Send to N people — we will measure the result" framing.
- **Watching (1)**: `aov` trend (already there). Cap 4 leaves room for additional load-bearing metrics if computable.
- **Held / Considered (4)**: `winback_21_45` (audience 686, `no_measured_signal` until outcome log evidence; PM wanted Lifecycle, DS held in Considered for first ship), `routine_builder` (audience 1,926, `no_measured_signal`), `subscription_nudge` (audience 2, `audience_too_small`), `empty_bottle` (audience 0, `audience_too_small`).

Total visible plays: **6** (1 + 2 + 1 + 4 minus Watching count toward "play cards" = 7 surfaces). Page becomes scannable, differentiated, and commercially actionable.

ABSTAIN_SOFT collapses Recommended Now AND Recommended Experiment to 0; only Watching + Considered survive (Fix 3 contract extends).

## Non-Negotiable Trust Constraints

Carries forward verbatim from current contract; DS adds the bolded items.

- No fake `p`, `q`, `CI`, `confidence_score`, `final_score`, numeric confidence percentages.
- No `Aura`, `Beacon Score`.
- No targeting card with non-null `Measurement` (Fix 2 invariant).
- No targeting card with $ p50 headline or standalone dollar number larger than the range chip (M8 invariant).
- No "calibrated," "uplift," "ATE," "ITT," "treatment effect" anywhere merchant-facing.
- No "expected lift," "projected lift," "forecast," "predicted" on any role.
- No "measured" or "evidence" claim on a directional or experiment card.
- No restoration of `journey_optimization` to V2 path.
- ABSTAIN_SOFT publishes zero Recommended Now AND zero Recommended Experiment cards (extends Fix 3 to all measured/directional/experiment surfaces).
- **No `would_be_measured_by` rendered as free-text on Recommended Experiment; must be enum-backed or omit the field.**
- **No play appears in two roles in the same run.** Pin as structural assertion in `decide.py`.
- **No `revenue_range.suppressed=false` on any card whose `evidence_class != measured` AND whose `realization_factor` from `calibration_stub` is null.** Calibration stub returns `{}` today; this rule keeps suppression locked until real history exists.
- **No promotion of a Phase 5.6 directional card to `measured`** without a calibrated causal prior in `config/priors.yaml` with `source_class=causal` AND realized outcomes from `recommended_history.json` AND DS sign-off.
- **No "experiment" label on a play whose `would_be_measured_by` outcome metric is not computable from the merchant's available data.**

## Implementation Scope Recommendation

Implementation planning should consume the DS-tightened minimum safe scope:

**In scope (first ship)**

1. Add **Recommended Experiment** section to renderer.
2. Add **`would_be_measured_by`** as a mandatory enum-backed field on PlayCard in `engine_run.py`. Allowed values are a small enum (e.g., `incremental_orders_in_14d`, `email_attributed_revenue_in_7d`, `repeat_purchase_in_30d`). Free-text is forbidden.
3. Extend `config/priors.yaml` with per-play eligibility metadata: `audience_floor`, `mechanism`, `vertical_applicability`, `would_be_measured_by`, `audience_archetype`.
4. Add eligibility filter in `decide.py` for Recommended Experiment using the priors metadata.
5. First-ship Recommended Experiment allowlist: **`discount_hygiene`, `bestseller_amplify` only**. Plays without documented `mechanism` are ineligible.
6. Cannibalization gate: Recommended Experiment audience overlap < 30% with any Recommended Now card. Reuse M5 audience-overlap pairwise computation. Demote violators to Considered with `ReasonCode.AUDIENCE_OVERLAP`.
7. Slate diversity rule in `decide.py`: no two Recommended Experiment cards with the same `audience_archetype` in one run.
8. Hard cap: 2 Recommended Experiment cards per run.
9. Extend ABSTAIN_SOFT contract (Fix 3): zero Recommended Experiment cards under ABSTAIN_SOFT, with `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN` routing as today.
10. Reduce Watching cap from 7 to 4. Pin a load-bearing-metric prioritization test on `small_store_240d`.
11. Reuse Phase 5.1 opportunity-context block verbatim on Recommended Experiment cards. No new economic-context UI.
12. Extend forbidden-token sweep test (Phase 5.5) to cover Recommended Experiment cards with the additional forbidden phrases listed above.
13. Renderer-level structural assertion: no PlayCard appears in two role sections in a single briefing.
14. TDD discipline: failing test first for items 1, 2, 6, 7, 8, 9, 10, 12, 13.

**Out of scope (first ship; deferred)**

- Lifecycle Maintenance section.
- `recommended_history.json` reads (calibration_stub stays a stub).
- Recently-run-fatigue gate (NO-OP until outcome log exists).
- Additional play_types in Recommended Experiment beyond the two-play allowlist.
- AnomalousWindowCheck auto-registration.
- `empty_bottle` ct/lb/mg parser extension.
- `src/load.py:626` pandas-compat fix (clean prerequisite for low-inventory e2e validation; not slate-blocking).

## What To Defer

1. **Lifecycle Maintenance section** until `recommended_history.json` is non-stub (Phase 6).
2. **`src/load.py:626` pandas-compat fix** for low-inventory e2e validation (Phase 6 prerequisite, isolated).
3. **AnomalousWindowCheck auto-registration** for `promo_anomaly` ABSTAIN behavior (Phase 6).
4. **`empty_bottle` ct/lb/mg parser** at `src/audience_builders.py:439` (Phase 6, supplement-vertical readiness).
5. **Causal-lift calibrated priors** in `config/priors.yaml` for promoting directional cards to `measured` and unsuppressing `revenue_range` (Phase 6+, requires outcome-log cycles).
6. **Klaviyo / Shopify workflow integration** for `email_attributed_revenue_*` outcome metrics (out of slate scope).

## Questions For Implementation Manager

1. **PlayCard schema migration:** Is `would_be_measured_by` an additive field on the existing PlayCard dataclass in `engine_run.py`, or does it require a versioned schema bump? What's the impact on golden-output diffs in `tests/golden/`?

2. **Priors metadata expansion:** Adding `audience_floor`, `mechanism`, `vertical_applicability`, `would_be_measured_by`, `audience_archetype` to `config/priors.yaml` — is this one milestone or split across two (schema/load + downstream consumption)?

3. **Slate diversity archetype taxonomy:** Who owns the initial `audience_archetype` enum values? Suggest DS authors the enum (e.g., `lapsed_buyer`, `discount_buyer`, `hero_sku_buyer`, `replenishment_buyer`, `first_time_buyer`) and PM signs off, before coding starts.

4. **Renderer change scope:** Does the new "Recommended Experiment" section require a new template/partial, or can it reuse the existing Recommended-card partial with role-aware copy? Phase 5.5 forbidden-token sweep test must extend either way.

5. **PM/DS disagreement on Lifecycle:** PM proposed shipping Lifecycle in the first ship; DS deferred. The reconciled position defers. Confirm this is acceptable to PM before implementation begins, or escalate.

6. **PM/DS disagreement on Recommended Experiment cap:** PM proposed cap 3; DS proposed cap 2. Reconciled position is 2 (more conservative). Confirm before implementation.

7. **Test sequencing:** Which tests are TDD red-first (PlayCard contract, ABSTAIN_SOFT extension, role-uniqueness assertion, forbidden-token extension) vs property-test additions vs golden refresh? Implementation manager should propose the test plan ahead of code edits.

8. **Goldens:** Will the new section change `tests/golden/{small_sm,mid_shopify,micro_coldstart}/briefing.html` deterministically? Plan for a single golden refresh checkpoint after the slate is wired and stable.

9. **Beauty Brand fixture as a regression target:** Should `agent_outputs/synthetic_fixes_8_11_samples/healthy_beauty_240d_briefing.html` (or a frozen copy) become a pinned slate-regression fixture under `tests/fixtures/`?

10. **Phase numbering:** Is this work Phase 6, Phase 5.7, or a new phase entirely? Clarify so memory.md tracking stays coherent.
