# DS Architect Review — Synthetic Phase 5 End-to-End

## Scientific / Decision Verdict

Phase 5 V2 is **scientifically defensible but operationally degenerate** on this synthetic matrix. The system is doing what it was designed to do: refusing to lie. But the design itself has three confused decision-layer behaviors that this matrix surfaces clearly, and the matrix itself fails to exercise the canonical Phase 5.6 pathway because of fixture-realism gaps that combine with a too-narrow gate.

I agree with the PM's overall direction but disagree on framing in three places, and I extend the analysis at the science layer in five.

The core reality:

1. The directional pathway (`first_to_second_purchase`) does not fire on a single scenario. The PM treats this as ambiguous between "fixture problem" and "gate too narrow." It is **mostly a fixture problem**, with one science-layer concern: the gate is correct in spirit but the supporting metric (`returning_customer_share`) is conflated with `repeat_rate_within_window` in ways the synthetic generator does not honor.
2. The promo_anomaly "contract violation" (ABSTAIN_SOFT + 2 Targeting cards in Recommended) is **not a bug. It is the documented design** — `src/storytelling_v2.py:626-628` and `src/decide.py:893-895` explicitly preserve up to 2 targeting cards under ABSTAIN_SOFT. The PM is reading from the user's stated product contract ("no Recommended = no recommendation"), which conflicts with what the implementation contract actually says. **The PM is right that the page is self-contradicting; the implementation is right that this was designed in. The contract itself is the bug.**
3. The cold-start crash is a legacy `charts.py:273-274` defect (`ax.bar(x - width/2, recent, width, ...)` where `recent` contains None) running upstream of any V2 ABSTAIN_HARD detection. This is a pre-existing legacy bug; the V2 stack is structurally not at fault, but the V2 ABSTAIN_HARD path is unreachable for any cold-start merchant. This is the most severe defect in the matrix.

The Phase 5 V2 work itself (Phase 5.1-5.7) is sound. The legacy stack feeding it, the gating thresholds inherited from M0-M9, and the synthetic generator are where the failures live.

## Scenario-by-Scenario Scientific Assessment

### 1. healthy_beauty_240d

- **Evidence present:** L28 returning_customer_share = 41.4%, change vs prior = **-1.7%** (`engine_run.json:42-46`). Repeat rate L28 = 10.1% with a +63.3% MoM delta. AOV flat. Orders +96.8% vs prior. Net sales +96.3% vs prior. The +96% deltas suggest a comparison-window construction artifact (likely L28 vs L28-of-prior-period that includes a slow ramp).
- **Expected decision:** at-least-one directional via `first_to_second_purchase` per the YAML `expected_behaviors: at_least_one_primary_or_directional`.
- **Actual decision:** ABSTAIN_SOFT, 0 Recommended, 6 Considered (5x `no_measured_signal`, 1x `audience_too_small`), 1 Watching (aov down).
- **Scientifically valid?** Yes, given the input. The `first_to_second_purchase` pathway in `measurement_builder.py:307-321` requires `primary_p < 0.05` AND `consistency >= 2` on L28 returning_customer_share. The L28 delta is -1.7% (negative) and we cannot verify the p-value or sign-stability across L56/L90 from `engine_run.json` alone, but the PM is correct that the negative L28 delta would prevent firing if L56/L90 are positive (sign disagreement, consistency=1).
- **Likely cause if invalid:** Fixture-realism. The YAML claims "improving returning customer share (25%->40%+)" but the L28-vs-prior delta does not show that direction at the Sep 18 anchor. The synthetic generator's beauty cohort exhaustion pattern (synthetic-fixture-generator-summary item 2) is the proximate cause.
- **Pass/Fail:** **Soft fail.** Not a science blocker; engine refused to fire on a fixture that does not actually carry the signal.

### 2. healthy_beauty_low_inventory_240d

- **Evidence present:** Same shape as #1 but with hero SKU at ≤10 units. `bestseller_amplify` audience = 1,357 (`engine_run.json:64-68`).
- **Expected decision:** Inventory-blocked play visible in considered list per YAML.
- **Actual decision:** ABSTAIN_SOFT, 0 Recommended, 6 Considered. `bestseller_amplify` shows reason `no_measured_signal` (NOT `inventory_blocked`). 1 Watching (aov down).
- **Scientifically valid?** **No.** The whole purpose of this scenario is to validate that `gate_inventory()` (`src/guardrails.py:197-294`) fires on the bestseller candidate and surfaces a `INVENTORY_BLOCKED` ReasonCode. It does not. The receipts show the inventory CSV reports "228 days stale" (synthetic-fixture-generator-summary item 4) which suggests the inventory data is being either rejected by the validator or read into `inventory_metrics` but not consumed by the V2 considered-list path. `populate_considered_from_candidates` (`src/decide.py:500-599`) does not call `gate_inventory` — it maps from M3 `preliminary_rejection_reason` to typed ReasonCodes only. There is no path from "M5 inventory gate fired on a legacy candidate" to "V2 considered card with INVENTORY_BLOCKED reason."
- **Likely cause if invalid:** **Wiring defect.** The M5 `gate_inventory` rejections live on the legacy adapter side (they would attach to a PlayCard's `RejectedPlay`), but the V2 considered list is built from M3 candidates only. The two paths do not merge.
- **Pass/Fail:** **Hard fail at the science layer.** This is one of two real science blockers in the matrix.

### 3. supplement_replenishment_240d

- **Evidence present:** Returning-customer share L28 = 100.0% (delta = 0.0%, `engine_run.json:42-46`). Repeat rate L28 = 0.8% with +154.7% delta — this is highly suspicious. AOV $46. Net sales $44k (held). Customers have explicit 28-45d reorder intervals per the generator.
- **Expected decision:** Replenishment signal visible in considered or recommended.
- **Actual decision:** ABSTAIN_SOFT, 0 Recommended, 6 Considered (mostly `no_measured_signal`, plus `subscription_nudge` audience=12 and `routine_builder` audience=0 with `audience_too_small`), 2 Watching (net_sales up, returning_customer_share flat).
- **Scientifically valid?** **No, on multiple grounds.**
  - (a) `returning_customer_share` = 100% with delta = 0% by construction means the directional pathway cannot fire — the metric is a degenerate state on this fixture, not a signal.
  - (b) `briefing_meta::vertical = "beauty"` (line 122 of engine_run.json), not supplements. The vertical was not propagated. This invalidates the whole scenario as a vertical-coverage test.
  - (c) The repeat_rate_within_window value (0.8%) is suspiciously low for a 100%-returning supplement business, and the +154.7% MoM swing on a 0.8% absolute value is a noise signal, not a real movement. Reporting the ratio change on a tiny base is a known statistical antipattern.
  - (d) The PM-cited reporter claim "1 PRIMARY journey_optimization" is from `candidate_debug.json::actions`, not the merchant-visible briefing. The V2 path correctly suppresses `journey_optimization` (`src/decide.py:387-395`).
- **Likely cause if invalid:** Compound. (i) Vertical mode not propagated. (ii) `returning_customer_share` is a poor proxy for replenishment-cycle signal; supplement businesses need a `inter_purchase_interval` or `time_to_second_order` metric. (iii) The repeat_rate_within_window denominator definition appears to mismatch the YAML's mental model.
- **Pass/Fail:** **Hard fail.** The engine has no supplement-vertical pathway, and the supplement-flavored plays in the registry (`subscription_nudge`, `empty_bottle`) are gated to behaviors the generator does not model (3+ same-product orders; size-token depletion).

### 4. small_store_240d

- **Evidence present:** Net sales L28 = $12,974, customer base est. = 245. AOV $49, repeat rate 8.2% (+85.4% MoM — also a tiny-base ratio artifact). All audiences below 250.
- **Expected decision:** Conservative no-action, no fake projections.
- **Actual decision:** ABSTAIN_SOFT, 0 Recommended, 6 Considered (4x `no_measured_signal`, 2x `audience_too_small`), 0 Watching. `materiality_floor: null`.
- **Scientifically valid?** **Yes, on epistemics. No, on completeness.** The engine correctly does not recommend on this scale. But:
  - The PM is right that no `MATERIALITY_BELOW_FLOOR` ReasonCode fires. At $12,974/month, the scale-aware floor is `max($5,000, 2% * 12,974) = $5,000` per `guardrails.py:138-169`. Any plausible play that could yield $1k-$3k of incremental revenue is below floor. The materiality floor mechanism is wired (M5) but `Scale.materiality_floor` is reported as `null`. This is a receipts-completeness defect: the floor was applied but not stamped onto the EngineRun.
  - Watching = 0 is wrong on the load-bearing-metrics rule. Net sales delta of +67.9% should have surfaced as a `MOVED` observation (and thus excluded from Watching), but the generator's tiny-base swings should still have produced at least one stable load-bearing entry under the Phase 5.3 "flat" rule. This depends on which observations classified as HELD vs MOVED — likely none, because everything moved.
- **Pass/Fail:** **Soft pass.** The engine did not lie, but it left the merchant with no read on why. PM is correct that this is a "below-scale memo" gap.

### 5. cold_start_45d

- **Evidence present:** N/A. Engine crashed in `src/charts.py:273-274` before any briefing was written.
- **Expected decision:** ABSTAIN_HARD with `data_quality_flags=[INSUFFICIENT_CLEAN_HISTORY]`.
- **Actual decision:** Crash. No briefing.html, no engine_run.json.
- **Scientifically valid?** **No — but the V2 abstain logic is not at fault.** The legacy chart renderer runs upstream of the V2 abstain state machine. `gate_anomaly` (`guardrails.py:302-318`) defensively enforces the ABSTAIN_HARD invariant in `_decide_abstain_state` (`decide.py:828-872`), but that code path is never reached because matplotlib crashes on `ax.bar(x - width/2, recent, width, ...)` when `recent` contains `None`.
- **Likely cause if invalid:** Pre-existing legacy bug in `charts.py` that pre-dates the V2 stack. The V2 contract assumed cold-start would be handled by `INSUFFICIENT_CLEAN_HISTORY` flag detection in M5 → ABSTAIN_HARD in M7. Neither runs because charts.py is upstream of both.
- **Pass/Fail:** **Hard fail. Single most severe defect in the matrix.** This is the science blocker that turns "data scientist replacement" into "Python traceback" for any merchant with thin history.

### 6. promo_anomaly_240d

- **Evidence present:** Sep 18 anchor. May 2025 had a 3.1x revenue spike ($315k vs $90k baseline). The spike is **120 days before the anchor** (synthetic-fixture-generator-summary item 5), so it falls outside L28 (28d), L56 (56d), and L90 (90d) lookbacks. The current L28 has +41.8% net sales, +39.2% orders — not anomalous on the analysis window. AOV $60.
- **Expected decision:** Anomaly warning or abstain per YAML.
- **Actual decision:** ABSTAIN_SOFT with **2 Targeting cards in Recommended** (winback_21_45 audience=4,330, bestseller_amplify audience=3,141), 6 Considered, 0 Watching.
- **Scientifically valid?** **Mixed.** Three layers:
  - (a) Anomaly detection correctly does not fire because the spike is outside the analysis windows. This is a fixture problem, not an engine problem. The fixture is not testing what it claims.
  - (b) The 2 Targeting cards rendering under ABSTAIN_SOFT is the documented design (`storytelling_v2.py:626-628`: "PM contract: 0-2 targeting cards under ABSTAIN_SOFT"). It is a contract problem, not a gate problem.
  - (c) **The internal `p_internal: 1.6e-72` on `bestseller_amplify` (`engine_run.json:141`) and `p_internal: 0.0` on `winback_21_45` (line 74) are saturated p-values flowing through the V2 stack.** This is a real concern. The legacy `_compute_candidates` produces these saturated values (visible in `candidate_debug.json:80, 121`) and `engine_run_adapter._build_measurement_from_legacy` (`engine_run_adapter.py:114, 139`) passes them through to `Measurement.p_internal`. The contract correctly hides them from the merchant (no `p =` in HTML), but their presence in V2 receipts confirms the M0-M9 cleanup did not fully drain saturated stats from the data path. They flow into `EngineRun.recommendations[].measurement.p_internal` even on targeting plays — which violates the M4b architectural invariant ("targeting ⇒ measurement is null"). Looking at `engine_run_adapter.py:112-113`: it returns `None` for measurement when `evidence_class == "targeting"` — but in this case the evidence_class is "targeting" yet measurement is **not** null in the final output. This means the targeting reclassification happened **after** measurement was built, or some path bypasses the null check.
- **Likely cause if invalid:** Compound: anomaly fixture mis-constructed, ABSTAIN_SOFT contract permits targeting cards by design, and saturated p-values leak into V2 measurement records on targeting cards.
- **Pass/Fail:** **Hard fail at the science layer for the saturated p-values; also fixture failure for anomaly.**

## Evidence Classification Assessment

The evidence classes used (TARGETING, DIRECTIONAL, MEASURED) are conceptually correct and the registry assignments in `src/play_registry.py:192+` are defensible. The Phase 5.6 directional builder respects the right gates (`p < 0.05`, `consistency >= 2`).

But two things are off:

1. **`returning_customer_share` is the wrong supporting metric for `first_to_second_purchase`.** The `_SUPPORTED` map in `measurement_builder.py:108-130` correctly notes this in the rationale: "returning_customer_share is the per-window fraction of customers with prior order history. It is a directional indicator of retention health, not a measured first-to-second conversion lift." But the gate doesn't account for the metric being **non-monotonic in the play's intended outcome.** A merchant who acquired many new customers (good) sees returning-customer share *fall* (mechanically), and the play would not fire. This is exactly what happens on healthy_beauty_240d: the L28 delta is -1.7% because the customer base grew faster than the returning cohort. The metric is a **state-level statistic of cohort composition**, not a directional indicator of intervention efficacy. The Phase 5.6 wiring is conservative on dollar suppression but uncalibrated on direction.
2. **`p_internal` saturation in the legacy → V2 adapter chain is uncorrected.** `engine_run_adapter._build_measurement_from_legacy` passes `p` through verbatim (`engine_run_adapter.py:139`). `STATS_NAN_FOR_HARDCODED` flag in M4a is supposed to NaN fabricated stats, but legacy `_compute_candidates` is producing real-but-saturated p-values from large-N tests on heuristic effect sizes. These p-values reflect sample size, not effect strength, and the M4b combiner cannot know that. The contract correctly never renders them, but they pollute `Measurement.p_internal` on targeting cards.

## Sizing / Opportunity Context Assessment

Across all six runs, every `revenue_range.suppressed=true` and every `revenue_range.p10/p50/p90=null`. This is correct per Phase 5.6's "no causal prior, no calibrated lift, no dollar projection" rule.

The opportunity_context block (`measurement_builder._build_opportunity_context`, lines 191-219) is wired but not visible in any of the six engine_run.json outputs (every `opportunity_context: null`). It would only fire on a card built by `build_directional_play_card`, which never fires on these fixtures. So it is structurally unused on this matrix.

This is acceptable per the M0-M9 contract: in the absence of a measured/directional play, no opportunity sizing surfaces. The cards that do render (promo_anomaly's 2 targeting plays) correctly carry `revenue_range.suppressed=true` with `suppression_reason: "targeting_non_causal_prior"` in `drivers[]` (lines 105-110, 169-176 of promo_anomaly's engine_run.json).

The PM's question about a "parametric calculator-style sketch" for opportunity context is the right next-phase question. **My answer: no, not yet.** A parametric `audience × AOV × store-observed conversion` block on a Considered card without realization data still risks the merchant reading it as a forecast. The current austerity is correct until calibration data exists.

## Guardrail Assessment

| Gate | Status on this matrix | Verdict |
|---|---|---|
| `gate_anomaly` (HARD DQ flags) | Not exercised. No fixture triggers BFCM_OVERLAP, REFUND_STORM, TEST_ORDER_ANOMALY, or INSUFFICIENT_CLEAN_HISTORY at the analysis window. Promo_anomaly's spike is outside the window. | Untested |
| `gate_inventory` | Wired but does not surface through V2 considered-list path on healthy_beauty_low_inventory. | **Failing** |
| `scale_aware_materiality_floor` | Computes correctly per `guardrails.py:138-169` but `Scale.materiality_floor` is `null` on every engine_run.json. The floor is not stamped onto the receipts. | **Receipts defect** |
| `gate_cannibalization` (overlap) | Not exercised; no two plays surface as recommendations on the same fixture (except promo_anomaly's 2 targeting cards, where overlap was not flagged). | Untested |
| `gate_recently_run_fatigue` | Not exercised; no `recommended_history.json` carryover on first synthetic run. | Untested |

The matrix exercises one gate (inventory) and finds it broken at the wiring layer. The other four are either untested or have a receipts-completeness gap.

## Inventory Behavior Assessment

The science answer: `gate_inventory` (`guardrails.py:197-294`) is wired correctly at the M5 layer but the inventory CSV is not flowing into the V2 considered-list path. Three places it could fail, in order of likelihood:

1. **Inventory CSV "228 days stale" rejection.** The validator may be silently dropping the CSV due to date-relative `Updated At` parsing (synthetic-fixture-generator-summary item 3). Without the CSV, `inventory_metrics` is `None` and `gate_inventory` is a no-op (`guardrails.py:264-265`).
2. **Even if `gate_inventory` fires on a legacy PlayCard candidate, the V2 considered list is built from M3 detector candidates** (`decide.populate_considered_from_candidates`), not from M5-rejected legacy candidates. There is no merge step that says "if M5 rejected a legacy candidate with INVENTORY_BLOCKED, surface it on the V2 considered card for the matching M3 candidate."
3. The candidate_debug.json shows 1 base_candidate (`retention_mastery`) on the low-inventory fixture, not `bestseller_amplify`. So the legacy emitter itself didn't surface bestseller as a candidate — likely because some upstream gate dropped it. This means there is no PlayCard for `gate_inventory` to even examine, regardless of CSV freshness.

## Anomaly / Cold-Start Assessment

**Anomaly:** The fixture is mis-designed (May spike outside the Sep anchor's L90 lookback). The engine's anomaly detector (`src/anomaly.py` per the synthetic generator summary) operates on L28/L56 windows. The fixture would need anchor near June or the spike near August to be in-window. **Fixture realism gap, not engine defect.**

**Cold-start:** Engine crashes in `src/charts.py:273` (matplotlib `ax.bar(x - width/2, recent, width, ...)` where `recent = [row.get('recent') for row in rows]` returns a list containing `None`). This is a legacy charts defect that pre-dates the V2 work.

The architectural fix should be: V2 ABSTAIN_HARD detection runs **before** chart rendering. Today, the run order is approximately: legacy `main.py` → compute candidates → render charts (CRASHES HERE) → adapt to EngineRun → V2 decide. Cold-start needs INSUFFICIENT_CLEAN_HISTORY detection to fire upstream of charts.py, OR `charts.py:273` needs defensive `None`-handling (filter None values before `ax.bar`). The defensive fix is one line; the architectural fix is the right shape but a larger refactor.

## Replenishment / Supplement Assessment

The supplement scenario is the worst-aligned of the six. Three independent failures, each independently fatal to the test:

1. **Vertical not propagated.** `briefing_meta::vertical = "beauty"` (engine_run.json:122) on a supplement fixture. The V2 stack runs vertical-applicability filtering in `populate_considered_from_candidates` (`decide.py:573-577`), which means supplement-applicable plays may be incorrectly filtered as "not beauty-applicable" or beauty-applicable plays may surface where they shouldn't. The test runner is not setting `VERTICAL_MODE` per scenario.
2. **No supplement-vertical play in V2's directional path.** `_SUPPORTED` in `measurement_builder.py:108-130` contains only `first_to_second_purchase` (supported by `returning_customer_share`). For a 100%-returning supplement store, that signal is structurally degenerate (delta = 0% by construction).
3. **Supplement-flavored plays in the registry (`subscription_nudge`, `empty_bottle`) are gated to behaviors the synthetic generator does not model.** `subscription_nudge` requires 3+ same-product orders in 90d; the generator produces 1.7 orders/customer on average. `empty_bottle` requires size-token product metadata; the generator does not produce a size attribute on SKUs.

The PM is right that a merchant running a supplement business would conclude the engine has no understanding of supplement businesses. But this is **not** a Phase 5 V2 defect — it is a registry + audience-builder + fixture-realism gap that pre-dates Phase 5. The fix is to (a) propagate vertical, (b) add a `inter_purchase_interval` or `time_since_last_order` supporting metric to `_SUPPORTED`, (c) extend the synthetic generator to produce size-token metadata.

## Considered / Watching Signal Quality

**Considered list:** The structure is correct (typed `RejectedPlay` with `play_id`, `reason_code`, `reason_text`, `evidence_snapshot`, `would_fire_if`). The reason-code taxonomy is too narrow for what the matrix exercises:
- `inventory_blocked` exists in the enum but does not fire on the low-inventory scenario.
- `materiality_floor_failed` exists in the enum but does not fire on the small-store scenario.
- `vertical_not_applicable` does not exist; supplement+routine_builder shows `audience_too_small` (audience=0) instead.

`_PRELIM_REASON_MAP` in `decide.py:370-379` only knows about M3 detector preliminary reasons, not M5 guardrail rejections. This is the wiring gap that produces the boilerplate "no_measured_signal" reason on every Considered card.

**Watching list:** Correct in concept (deterministic, threshold-based, no LLM). The Phase 5.3 `_LOAD_BEARING_WATCH_METRICS` rule (`decide.py:652-659`) should produce ≥1 entry on every healthy run, but only fires when an observation classifies as HELD. On scenarios where every metric MOVED (small_store, promo_anomaly), Watching is empty by design. This is a contract gap: the contract should be "Watching has at least one entry on any non-cold-start run with ≥1 load-bearing metric" — current behavior fails that on stores where everything is in motion.

## Merchant-Visible vs Internal Artifact Analysis

I agree with the PM that the reporter's summary table conflates `candidate_debug.json::actions/pilot_actions` with merchant-visible briefing.html state. The PM enumerated this clearly and I have nothing to add at the reporter layer.

At the **science** layer, the more important separation is between:

- `engine_run.json::recommendations[]` (the V2 source of truth for what the merchant will see)
- `candidate_debug.json::candidates/actions[]` (legacy stack diagnostic)
- `v2_sizing_shadow.json::records[]` (M6 sizing receipts; empty on every fixture)

The PM is correct that `engine_run.json` is the contract. But on promo_anomaly the contract itself is ambiguous: `recommendations[]` is non-empty AND `decision_state == abstain_soft`, which the user's stated product contract calls a violation. **The implementation contract (storytelling_v2.py:627-628) explicitly permits this; the user's stated product contract forbids it. These are inconsistent.**

I cannot reconcile them as a DS — that is a product-contract decision. But the implementation is internally consistent and the PM is correct that the resulting page is self-contradicting.

## Synthetic Fixture Quality Assessment

| Fixture | Realism gap | Severity |
|---|---|---|
| healthy_beauty_240d | Customer pool exhaustion drives returning-share inflation (item 2 in generator summary). L28 delta on returning_customer_share is negative when YAML claims it should be improving. | High — invalidates the canonical Phase 5.6 acceptance test |
| healthy_beauty_low_inventory_240d | Inventory CSV stale-date artifact. | Medium — independent from the engine's wiring defect |
| supplement_replenishment_240d | 100% returning by construction makes returning_customer_share degenerate. Repeat-rate-within-window value (0.8%) inconsistent with reorder-interval design. | High — invalidates supplement test |
| small_store_240d | None — fixture is on-spec. | None |
| cold_start_45d | None — fixture is on-spec; failure is engine-side. | None |
| promo_anomaly_240d | Spike 120 days outside anchor's L90 lookback. Anomaly detection cannot see it. | High — invalidates anomaly test |

Three of six fixtures fail to test what they claim to test. The matrix as a whole is **insufficient** to validate Phase 5 V2 acceptance, independent of the science-layer issues in the engine.

The synthetic generator's deeper problem is that it is **outcome-driven** (designed to produce specific deltas) rather than **process-driven** (designed to produce realistic customer cohorts that organically yield those deltas). The "improving returning customer share 25%->40%+" YAML directive is a target the generator hits at the lifetime aggregate level but does not honor at the L28-vs-prior delta level at the anchor date.

## True Science / Decision Blockers

In priority order, with scope:

1. **Cold-start crash in `charts.py:273`.** Pre-existing legacy bug. Any cold-start merchant hits this. The V2 ABSTAIN_HARD path is unreachable. This is the only true science-level blocker before founder testing. Defensive fix is one line: filter `None` from `recent`/`prior` before `ax.bar`. Architectural fix is moving V2 ABSTAIN_HARD upstream of legacy chart rendering.

2. **Inventory gate not surfacing through V2 considered list.** `gate_inventory` runs in M5; `populate_considered_from_candidates` builds Considered from M3 detector output only. There is no merge between "M5 rejected a legacy PlayCard with INVENTORY_BLOCKED" and "V2 Considered card for the matching M3 candidate." Either:
   - Wire M5-guardrail rejections into `populate_considered_from_candidates`, OR
   - Have M3 detect_candidates consume the inventory metrics and produce a candidate with `preliminary_rejection_reason="inventory_blocked"`.

3. **Saturated `p_internal` leaks through the legacy adapter on targeting cards.** `engine_run_adapter._build_measurement_from_legacy` passes `p` through verbatim regardless of evidence class. Per the M4b invariant, targeting cards must have `measurement is None`, but promo_anomaly's `recommendations[0].measurement.p_internal = 0.0` (winback) and `recommendations[1].measurement.p_internal = 1.6e-72` (bestseller) **with `evidence_class = "targeting"`**. This is an architectural invariant violation. The renderer hides it from the merchant, but it shows that the M4b reclassification happens *after* measurement is built, leaving stale measurement objects on cards that should be measurement-null.

4. **Materiality floor not stamped on engine_run.json.** `Scale.materiality_floor: null` on every fixture even when the floor was applied. This is a receipts-completeness defect that prevents downstream merchants/agents from understanding why a play was rejected.

5. **The Phase 5.6 directional gate's supporting metric is conflated.** `returning_customer_share` is a state statistic of cohort composition, not a directional signal of first-to-second conversion. On a healthy growing brand acquiring many new customers, returning-share *falls*, and the gate correctly does not fire — but the play *should* fire. The gate is risk-averse in the wrong direction. This is a measurement-design issue more than a wiring issue, and resolving it requires either (a) using a different supporting metric (`time_to_second_order` distribution shift, or `first_to_second_conversion_rate` for newly-acquired cohorts), or (b) explicit normalization of `returning_customer_share` against new-customer acquisition rate.

## Fixture / Reporting / Deferrable Items

**Fixture realism gaps (not science blockers, but block matrix validity):**

- f1. `healthy_beauty_240d` — re-tune generator to ensure L28 returning_customer_share delta is positive at Sep 18 anchor with sign-stable agreement across L56/L90.
- f2. `supplement_replenishment_240d` — clarify the repeat_rate_within_window definition; cap returning-customer share at <100%; ensure VERTICAL_MODE propagates per scenario.
- f3. `promo_anomaly_240d` — move anchor or move spike so the spike is within L56.
- f4. Inventory CSV staleness — align test runner clock to anchor date.
- f5. Supplement generator needs explicit "loyal SKU repeater" cohort and size-token metadata.

**Reporter bugs (not science blockers):**

- r1. Reporter reads `candidate_debug.json::pilot_actions` and labels them "pilot" — these are internal-only.
- r2. Reporter does not parse briefing.html DOM; it reads internal JSON.
- r3. Reporter conflates legacy "PRIMARY" with V2 "Recommended."

**Deferrable items (Phase 6 or later):**

- d1. Reason-code taxonomy expansion: `vertical_not_applicable`, `materiality_floor_failed` as visible reasons.
- d2. Watching never-empty contract on healthy stores.
- d3. Considered card text differentiation by reason code (today is dominated by `no_measured_signal`).
- d4. Supplement vertical pathway in `_SUPPORTED`.
- d5. Per-scenario VERTICAL_MODE propagation in test harness.
- d6. Below-scale memo (small_store explicit "below scale" callout).

## Recommended Next Step

**Do NOT proceed to founder testing on this matrix until the three true science blockers are addressed.** Specifically:

1. Fix `charts.py:273` defensively (one-line None filter on `recent`/`prior`). This unblocks the cold-start ABSTAIN_HARD path and prevents any thin-history merchant from hitting a Python traceback.
2. Decide and fix the inventory-gate-to-V2-considered-list wiring. Recommend: add a `preliminary_rejection_reason="inventory_blocked"` path in M3 detect_candidates when the candidate is in `SKU_PUSH_PLAYS` and `inventory_metrics` shows cover_days below threshold. This puts the inventory signal in the V2-canonical M3 detector layer where `populate_considered_from_candidates` already reads it.
3. Add an assertion or clearing step in `engine_run_adapter._action_to_play_card` (or the M4b layer) that enforces "if `evidence_class == targeting`, then `measurement = None`." This drains the saturated `p_internal` leak on targeting cards.

After these three fixes:

4. Re-tune the synthetic generator on at least the three fixtures with realism gaps (healthy_beauty L28 delta, supplement repeat-rate definition, promo anchor placement). Without these, the matrix cannot validate Phase 5 acceptance.
5. Resolve the **product contract conflict** about whether targeting cards may render under ABSTAIN_SOFT. Today the implementation says yes (up to 2); the user's stated contract says no. Pick one. If the answer is "no Recommended under ABSTAIN_SOFT," update `storytelling_v2.py:626-628` and `decide.py:893-895` accordingly. If the answer is "up to 2 Targeting cards under ABSTAIN_SOFT," update the user's product contract document. Either is defensible; the current ambiguity is not.
6. Defer everything else (taxonomy expansion, supplement vertical pathway, opportunity context calculator, materiality footer additions) to Phase 6.

**Items I disagree with the PM on:**

- The promo_anomaly contract violation is **not a bug** at the implementation layer — it is the documented design of `storytelling_v2.py` and `decide.py`. The PM is right the page is self-contradicting; I disagree it is a "decide() vs renderer disagreement." Both agree, and they were designed to keep targeting cards. The conflict is upstream, in the user's product contract.
- The PM's "soft fail" on healthy_beauty for not firing the directional pathway should be a **soft pass** for the engine and a **fixture failure**. The engine refused to fire on a fixture that does not actually carry the upward signal it claims. Punishing the engine for being honest is the wrong frame.
- The PM's framing of saturated p-values as "internal-only, not concerning at merchant layer" understates the problem. The architectural invariant (targeting ⇒ measurement is null) is being violated in the receipts. This is the kind of structural defect that, left alone, lets future regressions surface saturated stats to merchants.

**Items I extend beyond the PM:**

- The `returning_customer_share` choice as supporting metric for `first_to_second_purchase` is a measurement-design defect, not a configuration knob. It needs replacement, not tuning.
- The `repeat_rate_within_window` ratio swings on tiny-base values (0.8% → +154.7%) are reported uncritically in state-of-store. This is a noise-amplification antipattern and should be guarded by a minimum-base threshold.
- The fixture matrix's outcome-driven generation (vs. process-driven) is a structural limitation that will keep biting Phase 6+ tests. The generator should produce realistic cohorts and let the deltas emerge, not target the deltas directly.

The Phase 5 V2 work itself is sound. The matrix exposes that the system around it (legacy emitter → adapter → V2 receipts) still has structural defects, and the synthetic fixtures themselves are not yet realistic enough to validate the canonical pathway. Both of those are the right things to fix next; neither requires rethinking the Phase 5 V2 architecture.
