# DS Architect — Baseline Acceptance and Campaign Slate Review

## Part 1 — Independent baseline verification

### 1. 11 synthetic blocker fixes
Scientifically acceptable. Fix 2 (post-hoc clear of `Measurement` on `evidence_class==targeting` in `engine_run_adapter._action_to_play_card`) closes the structural leak at the receipts level rather than the renderer, which was the right move. Fix 3 enforces `ABSTAIN_SOFT => recommendations==[]` with `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN` routing — this eliminates the page-contradicts-itself defect on `promo_anomaly`. Fixes 8–11 are fixture-realism only, no engine retune, and `tests/test_synthetic_fixtures_8_11.py` pins them. None of the fixes invented stats, lifted suppression, or weakened materiality. The TDD sequencing (failing test → fix) is honored on Fixes 2 and 3 per the engineer summaries.

### 2. Honesty-constraint compliance
Compliant on the canonical `agent_outputs/synthetic_fixes_8_11_samples/healthy_beauty_240d_briefing.html` and on the Phase 5.1 Beauty Brand sample. `recommendations[0]` for `first_to_second_purchase` carries `revenue_range.suppressed=true` with `p10/p50/p90=null` and a `suppression_reason=directional_no_intervention_effect` driver; `p_internal` (9.5e-05) and `consistency_across_windows=3` stay in `engine_run.json`/`debug.html` and out of merchant HTML. No `confidence_score`, `final_score`, `Aura`, `Beacon Score`, `p =`, `q =`, `CI`, or numeric confidence percentage in V2 briefings (forbidden-token sweep test in Phase 5.5). ABSTAIN_SOFT scenarios show `recommendations==0` everywhere. Materiality footer renders the merchant-readable sentence on all five non-ABSTAIN_HARD samples.

### 3. Inventory-loader deferral
Defer. `src/load.py:626` `groupby().apply().reset_index(name=...)` `TypeError` is a pandas-version compatibility bug, not a science defect. Its blast radius is `inventory_metrics is None`, which makes Fix 4's `inventory_blocked` stamp short-circuit at `detect.py:373-378`. The Fix 4 plumbing is unit-tested with synthetic `inventory_metrics`; the structural contract is sound. This is a one-line engineering fix, isolated, and does not impede campaign-slate discussion. Document it as a known gap on the low_inventory `inventory_blocked` Considered card.

### 4. Beauty Brand directional first_to_second_purchase
Acceptable as a baseline. Three forcing functions are in place: (a) `revenue_range.suppressed=true` with provenance `directional_no_intervention_effect` ("supporting signal is a state statistic, not an intervention effect"), (b) Phase 5.1 opportunity-context block with explicit "This is not projected lift" disclaimer, (c) `evidence_class=directional` (never `measured`). The card is honest about what it is: a sign-stable trend in `returning_customer_share` across L28/L56/L90, used to motivate a campaign whose realized lift is not yet known. The card must NOT be promoted to `measured` or unsuppressed without a calibrated causal prior backed by realized outcomes — memory.md's downstream instruction already pins this.

### 5. Remaining science issues that could block slate
None blocking. Documented but not blockers: (a) `returning_customer_share` is a state statistic; the directional card's defensibility rests entirely on suppression + disclaimer (memory.md Phase 5 acceptance note). (b) The directional card fires on three of six fixtures because they share the same generator family — do not over-generalize "engine works on healthy stores." (c) AnomalousWindowCheck not auto-registered; promo_anomaly publishes a directional card on returning-share, not abstaining on the spike. Phase 6 work, not slate-blocking.

### Verdict
**Acceptable with caveats.**

## Part 2 — Review of PM's campaign-slate contract

### Validity of proposed sections
**Recommended Now**: Valid. Cleanly maps to `evidence_class ∈ {measured, directional}` with materiality + cannibalization gates. PM's bar (`p_internal < 0.05` internal-only, `consistency_across_windows >= 2`) matches the existing Phase 5.6 directional pathway in `src/measurement_builder.py`. Keep cap at 0–2.

**Recommended Experiment**: Conditionally valid. Defensible only if it carries a binding `would_be_measured_by` field on the PlayCard (not just copy), `revenue_range.suppressed=true` always, and a vertical/play-mechanism eligibility filter that prevents "any targeting list with audience >= floor" from qualifying. Without these, this section becomes the rebranded TARGETING list and re-introduces the operator-framing risk the engine just removed. See guardrails section below.

**Lifecycle Maintenance**: Valid in concept, weak in current evidence base. Lifecycle is cadence-driven (table-stakes winback/replenishment), so the evidence bar is "play exists, audience non-trivial, vertical-applicable, not recently-run." It must not carry `Measurement`, must not carry `revenue_range.p50`. Disagreement with PM: I would NOT promote `winback_21_45` to Lifecycle on the *first* run; promote it to Lifecycle only after one outcome-log cycle has confirmed the merchant ran it without crash. Until then it sits in Recommended Experiment.

**Watching**: Valid. Reducing cap from 7 to 4 is fine if Phase 5.3's "load-bearing flat metrics surface" guarantee is preserved — see open-question answer.

**Held / Considered**: Valid. Already shipping correctly with typed `ReasonCode` + `would_fire_if`.

### Recommended Experiment without measured lift — defensibility and guardrails
"Send-and-measure with audience × AOV addressable order value" is defensible *only* with these structural guardrails, and only as bounded operational suggestion, not as scientific recommendation:

1. The PlayCard MUST carry `evidence_class=targeting` and `measurement=null` (Fix 2 invariant unchanged).
2. `revenue_range.suppressed=true` is non-negotiable. The Phase 5.1 opportunity-context block is the *only* economic surface allowed; magnitude-band rounded ("about $X"); the "This is not projected lift" disclaimer renders verbatim.
3. The card MUST carry a binding `would_be_measured_by` enum field (e.g., `incremental_orders_in_14d`, `email_attributed_revenue_in_7d`) — not free-text, not "we will measure this." This is the discipline that prevents the section from becoming a generic idea generator.
4. Header copy must say "Experiment" not "Recommendation"; CTA must read "Run as a pilot — we will measure the result," never "Run this campaign."
5. Forbidden phrases on this card: "expected lift," "projected," "forecast," "predicted," "measured," "evidence," any p/q/CI/$ headline.

Without point 3 (`would_be_measured_by` as a contract field), Recommended Experiment leaks as fake projection by implication — the merchant sees "audience × AOV ≈ $329k" and reads it as upside. Point 3 forces every experiment to declare its own outcome metric, which is also the hook for the M9 outcome log to calibrate later.

### Evidence bar per role (concrete)

- **Recommended Now**: `evidence_class ∈ {measured, directional}`; `consistency_across_windows >= 2`; `p_internal < 0.05` (internal-only, never rendered); audience clears scale-aware materiality; passes inventory + cannibalization gates; `measurement` non-null.
- **Recommended Experiment**: `evidence_class == targeting`; audience ≥ play-specific floor (NOT a global floor); play has documented `mechanism` in `config/priors.yaml` (e.g., "discount-fatigue reduction"); play has `vertical_applicable: true` for current `VERTICAL_MODE`; `would_be_measured_by` non-null and enum-valid; no inventory block; no audience overlap with Recommended Now > 30%.
- **Lifecycle Maintenance**: `evidence_class == targeting`; play registered as `lifecycle: true` in `config/priors.yaml` (a small allowlist, NOT every targeting play); audience ≥ floor; `recently_run_fatigue` check passes (>= 14 days since last run per outcome log).
- **Watching**: trending or load-bearing metric with named threshold and named would-fire `play_id`; `change_magnitude` resolves cleanly; cap 4.
- **Held / Considered**: typed `ReasonCode`, populated `reason_text`, populated `would_fire_if`. No change.

### Allowed vs forbidden economic context per role

**Recommended Now**: addressable-value block (audience × AOV magnitude-banded, "not projected lift" disclaimer); revenue_range only when calibrated lift exists (none today); audience size; primary_window AOV. Forbidden: standalone $ p50, p/q/CI, "expected lift," "forecast," numeric confidence percentage.

**Recommended Experiment**: same opportunity-context block, same disclaimer; explicit "Send to N people" framing; `would_be_measured_by` metric name visible. Forbidden: $ headline larger than the range chip (M8 invariant); any statistical claim; "evidence," "measured," "lift," "uplift," "ATE," "ITT."

**Lifecycle Maintenance**: audience size; cadence ("monthly," "weekly"); prior-run reference iff `recommended_history.json` has a clean outcome. Forbidden: $ context entirely (lifecycle is table stakes, not insight-driven; quantifying it implies a forecast). Disagreement with PM: I would NOT render the addressable-value block on Lifecycle. The block was added (Phase 5.1) for *suppressed-revenue directional* cards where merchants need economic context to decide whether to pilot. Lifecycle is a continuous program; quantifying it as "$X addressable" is closer to fake projection because the merchant is already running it.

**Watching**: trend direction, threshold, named would-fire play. No $ context.

**Held / Considered**: typed reason_text, would_fire_if, evidence_snapshot (audience + segment definition). No $ context.

### Additional forbidden claims (DS additions)

Beyond PM's list:
- No `would_be_measured_by` rendered as free-text on Recommended Experiment; must be enum-backed (or omit the field).
- No play appears in two roles in the same run (PM has this; pinning it as a structural assertion in `decide.py`).
- No `recommended_history.json` reads on cold-start stores or stores without a prior outcome record (avoids fabricating a "you've run this before" signal).
- No `revenue_range.suppressed=false` on any card whose `evidence_class != measured` AND whose `realization_factor` from `calibration_stub` is null. The calibration stub returns `{}` today; this rule keeps suppression locked until real history exists.
- No "experiment" label on a play whose `would_be_measured_by` outcome metric is not actually computable from the merchant's available data (e.g., no email-attributed revenue if the merchant has no Klaviyo connection — once that connection exists; for now this is moot but should be a contract).
- No promotion of a Phase 5.6 directional card to `measured` without a calibrated causal prior in `config/priors.yaml` with `source_class=causal` AND realized outcomes from `recommended_history.json` AND DS sign-off. The downstream instruction in memory.md already says this; pin it as a runtime assertion.

### Discipline against generic idea generation

The risk: Recommended Experiment becomes "any targeting list with audience ≥ floor" — i.e., the engine devolves into a heuristic recommender that hides behind "send-and-measure" framing.

The structural disciplines that prevent this:

1. **Per-play eligibility, not global eligibility.** Each play in `config/priors.yaml` declares its own `audience_floor`, `mechanism`, `vertical_applicability`, and `would_be_measured_by`. A play with no documented mechanism is ineligible for Recommended Experiment, regardless of audience size.
2. **Hard cap of 3 Recommended Experiment cards per run.** PM has this; pin it as a `decide.py` assertion.
3. **Cannibalization gate.** No Recommended Experiment whose audience overlaps > 30% with a Recommended Now card. Existing M5 audience-overlap pairwise computation is the input.
4. **Recently-run fatigue.** If `recommended_history.json` shows the play ran in the prior 14 days with no outcome recorded, demote to Considered with `ReasonCode.RECENTLY_RUN_FATIGUE`.
5. **Slate diversity rule.** No two Recommended Experiment cards may target the same audience segment archetype (e.g., not two "discount-buyer" plays). Define archetypes in priors.yaml.
6. **`would_be_measured_by` is mandatory and enum-backed.** Forces every experiment to declare its measurement design up-front, which doubles as the discipline that lets M9's outcome log calibrate over time.

Without rules 1, 4, and 6, the section degrades into generic. With them, it stays operationally useful and ML-ready.

### Minimum scientifically safe scope

Smallest version of the slate that ships without inviting honesty violations:

1. **Recommended Now** (existing Phase 5.6 directional pathway, unchanged). Cap 0–2.
2. **Recommended Experiment** with hard cap **2** (not PM's 3), `would_be_measured_by` enum field on PlayCard (engine_run.py addition), per-play eligibility gates from priors.yaml, cannibalization gate against Recommended Now, `revenue_range.suppressed=true` enforced, and the Phase 5.1 opportunity-context block reused verbatim. Eligible play allowlist for the first ship: `discount_hygiene`, `bestseller_amplify` only — both have clear mechanisms. Hold `winback_21_45`, `routine_builder`, `subscription_nudge` until they have outcome-log evidence of merchant adoption.
3. **Held / Considered** unchanged.
4. **Watching** unchanged (cap reduction to 4 is fine but not load-bearing for safety).
5. **Defer Lifecycle Maintenance to a follow-up phase**. Lifecycle as a section requires `recommended_history.json` to be a non-stub input (it is currently a stub per M9 memory note: "Calibration stub does not read history yet"). Without history, Lifecycle is structurally indistinguishable from Recommended Experiment, and shipping both creates merchant confusion about which to run. Ship Lifecycle once the outcome log has at least one merchant cycle of real records.

This minimum slate gives the merchant: 1 directional Recommended Now card (when signal exists), up to 2 honestly-framed Send-and-Measure experiments with audience × AOV context, plus the existing Considered + Watching + footer. Total 0–6 visible plays. Honest, differentiated, and commercially defensible at $500–$1,000/month without inviting fake-projection drift.

## Answers to PM's open questions

- **Is `winback_21_45` defensibly Lifecycle vs Recommended Experiment given current evidence_class is targeting and no causal prior exists?** Recommended Experiment for now. Promote to Lifecycle only after outcome-log shows the merchant ran it once without crash AND a causal prior is added in `config/priors.yaml` with `source_class=causal`. Lifecycle implies "table-stakes always-on"; that claim requires evidence the engine doesn't yet have. Today, treat winback as a high-quality experiment.

- **Should Lifecycle render under ABSTAIN_SOFT, or does Fix 3 extend?** Lifecycle should render under ABSTAIN_SOFT — but only if Lifecycle ships, which I'm arguing to defer. Rationale: ABSTAIN_SOFT means "no measured/directional opportunity cleared this month"; it doesn't mean "stop running your retention program." Lifecycle is cadence-driven and orthogonal to monthly insight. The Fix 3 contract should explicitly carve Lifecycle out: ABSTAIN_SOFT zeroes Recommended Now and Recommended Experiment, but Lifecycle survives. When Lifecycle ships, add a fourth `ReasonCode.LIFECYCLE_HELD_UNDER_ABSTAIN_HARD` for the ABSTAIN_HARD case (data-quality memo, no Lifecycle either).

- **Watching cap reduction 7 → 4 — does this break Phase 5.3 load-bearing flat metrics?** No, but be careful: Phase 5.3 raised the cap from 5 to 7 *because* load-bearing flat metrics now surface (returning_customer_share, net_sales added). Reducing to 4 is fine *if* the prioritization keeps load-bearing flat metrics ahead of small movers. Pin a test asserting that on `small_store_240d` (currently Watching=0), if any of {returning_customer_share, net_sales, repeat_rate_within_window, aov} is computable, at least one shows. Don't lose the "stable, watching" signal in pursuit of a tighter cap.

- **Should Recommended Experiment require `would_be_measured_by` as a contract field on PlayCard?** Yes, mandatory. This is the single structural discipline that prevents the section from becoming a generic idea generator AND the M9 calibration hook. Add as enum (not free-text) to `engine_run.py` PlayCard. Forbidden values: free-text strings, "we will measure this." Required values: a named outcome metric the engine knows how to read from CSV (`incremental_orders_in_14d`, `email_attributed_revenue_in_7d`, `repeat_purchase_in_30d`, etc.). Add to `recommended_history.json` schema as a join key for outcome calibration.

- **Does `bestseller_amplify` as Recommended Experiment require new measurement-design milestone?** No new milestone. The Phase 5.1 opportunity-context block + `would_be_measured_by` enum is sufficient for the first ship. `bestseller_amplify`'s mechanism ("amplify hero SKU during demand window") is well-documented; the audience builder is M3-stable; the outcome metric (incremental orders attributed to the hero SKU within 14 days) is computable from order CSVs. Once outcome-log has cycles, Phase 6 can add a calibrated lift prior to allow a non-suppressed range. Until then, suppress and use opportunity-context.

- **Should engine read `recommended_history.json` to suppress Lifecycle plays run in prior 14 days?** Yes, mandatory if Lifecycle ships. Otherwise Lifecycle becomes a nag-loop. Implementation: extend `calibration_stub.load_realization_factors()` (currently returns `{}`) to a thin `recommended_history.json` reader that returns `{play_id: last_run_date}`. The 14-day fatigue gate sits in `decide.py` and demotes recently-run plays to Considered with `ReasonCode.RECENTLY_RUN_FATIGUE`. This is also the hook that lets Phase 6 add real causal-lift calibration.

- **Does `empty_bottle` ml/oz parser limitation block supplement Lifecycle entirely, or can `subscription_nudge` substitute?** `subscription_nudge` substitutes adequately for the supplement vertical's first ship. The `empty_bottle` ct/lb/mg parser extension is a clean, scoped engine ticket (extend the regex at `src/audience_builders.py:439`); ship it Phase 6 as part of the supplement-vertical readiness pass. Do NOT block the slate on it. Note that `subscription_nudge` audience on supplements is now 505 post-Fix-9, which clears the M3 floor and gives the vertical a non-degenerate Lifecycle (or Recommended Experiment) candidate.

## Recommended changes to PM contract

1. **Reduce Recommended Experiment cap from 3 to 2** for first ship. Tightens the surface; PM can revisit after one outcome-log cycle.
2. **Defer Lifecycle Maintenance** to a follow-up phase, after outcome log is non-stub.
3. **Mandatory enum-backed `would_be_measured_by`** PlayCard field for Recommended Experiment. Free-text version is unacceptable.
4. **Restrict first-ship Recommended Experiment allowlist** to `discount_hygiene` and `bestseller_amplify` only. Other targeting plays move to Considered until they have a documented mechanism in `config/priors.yaml` and outcome-log evidence.
5. **Per-play `audience_floor` in priors.yaml**, not a global floor. Prevents the "any list ≥ X qualifies" failure mode.
6. **No addressable-value block on Lifecycle** if/when Lifecycle ships. The block is for suppressed-revenue insight cards (Phase 5.1 contract); extending it to cadence-driven plays risks fake-projection drift.
7. **Slate diversity rule**: no two Recommended Experiment cards may target the same audience archetype in one run.
8. **Cannibalization gate against Recommended Now**: any Recommended Experiment audience overlapping > 30% with a Recommended Now card is demoted to Considered with `ReasonCode.AUDIENCE_OVERLAP`.
9. **Lifecycle ABSTAIN_SOFT carve-out** (when shipped): Lifecycle survives ABSTAIN_SOFT (cadence-driven, orthogonal to monthly insight); Lifecycle is suppressed under ABSTAIN_HARD.
10. **Phase 6 follow-up ticket**: fix `src/load.py:626` `reset_index(name=...)` pandas-compat bug. Required to validate Fix 4's `inventory_blocked` Considered card end-to-end. Out of slate scope but a clean prerequisite.
