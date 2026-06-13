# Synthetic Phase 5 End-to-End Final Review

Reconciled from:
- `agent_outputs/product-strategy-pm-synthetic-phase5-e2e-review.md`
- `agent_outputs/ecommerce-ds-architect-synthetic-phase5-e2e-review.md`

## Executive Verdict

**Phase 5 V2 is not ready for founder/manual testing on this synthetic matrix.** Both reviewers agree the V2 product contract is mostly intact and statistically honest, but the matrix surfaces three engine-side structural defects and three fixture-realism gaps that compound into a near-uniform, low-utility merchant experience.

The headline:
- **0 of 6 scenarios fire the canonical Phase 5.6 directional pathway** (`first_to_second_purchase`).
- **5 of 6 briefings are visually near-identical** (ABSTAIN_SOFT skeleton with 6 boilerplate Considered cards, 0–2 Watching rows, no Recommended).
- **1 of 6 (cold_start) crashes** the engine in legacy `charts.py:273` before any V2 abstain logic can run.
- **1 of 6 (promo_anomaly) renders ABSTAIN_SOFT alongside 2 Targeting cards in Recommended** — the implementation says this is by design (`storytelling_v2.py:626-628`); the user's stated product contract says it is a violation. **The implementation contract and the user's stated contract conflict; this must be resolved.**
- **The reporter materially misrepresents merchant-facing state** in 4 of 6 scenarios by reading `candidate_debug.json::actions/pilot_actions` instead of briefing.html.

The Phase 5 V2 work itself (Phase 5.1–5.7) is sound. The defects are in:
1. The legacy emitter → adapter chain (saturated `p_internal` leak on targeting cards).
2. The wiring between M5 guardrails (inventory, materiality) and the V2 considered-list path.
3. The cold-start path (legacy charts crashes upstream of V2 ABSTAIN_HARD).
4. The synthetic generator (outcome-driven rather than process-driven; three of six fixtures fail to test what they claim).
5. The product contract itself (ambiguous about ABSTAIN_SOFT + Targeting cards).

## What The Test Matrix Shows

The matrix was designed to validate end-to-end Phase 5 V2 behavior across six merchant archetypes (healthy beauty, low inventory, supplement replenishment, small store, cold start, promo anomaly). What it actually validated:

- **Confirmed working:** The Considered list structure (typed `RejectedPlay`), the dollar-suppression contract on targeting cards, the V2 evidence-class taxonomy (TARGETING/DIRECTIONAL/MEASURED), the no-fake-projection invariant on small stores.
- **Confirmed broken:** Inventory wiring to V2 considered (low_inventory), saturated `p_internal` on targeting cards (promo_anomaly), cold-start crash path (cold_start), reason-code mapping breadth (every healthy scenario produces 5+ identical `no_measured_signal` reasons).
- **Untested due to fixture defects:** Phase 5.6 directional pathway (healthy_beauty fixture has wrong-sign returning_customer_share L28 delta); supplement vertical (test harness did not propagate `VERTICAL_MODE`, fixture has degenerate 100%-returning rate); anomaly detection (promo spike outside the analysis window).
- **Not exercised at all:** anomaly HARD DQ flags, cannibalization/overlap gate, recently-run-fatigue gate, `recommended_history.json` carryover semantics.

## Product Findings (PM)

- Five of six briefings are byte-substitutable from the merchant's point of view. A merchant cannot tell two stores apart from the recommendation surface.
- The Considered list is the strongest part of Phase 5 but its reason text is identical across 5 of 6 cards on healthy_beauty (boilerplate "no measured signal"); the structural improvement is real, the content differentiation is shallow.
- Watching is the weakest section: 1 row on healthy scenarios, empty on small_store and promo_anomaly, with engineering-flavored threshold language.
- The materiality footer line ("We only recommend primary plays that could realistically add at least $X this month") is present in the Phase 5 sample but **missing on all six synthetic briefings** — regression or config drift.
- The state-of-store paragraph fact-count is non-deterministic (3–5 facts across scenarios).
- The reporter is unreliable: it reads internal artifacts, not the merchant view, and labels things "pilot" / "PRIMARY" that the merchant never sees.
- For a $500/month product, a healthy $1.8M-ARR store getting a memo of "we considered six things, none cleared the bar, here's one metric to watch" is insufficient.

## DS / Scientific Findings

- **Architectural invariant violation** on promo_anomaly: targeting cards have non-null `Measurement` with saturated `p_internal` (1.6e-72 on bestseller_amplify, 0.0 on winback_21_45). The renderer hides this from merchants, but the M4b invariant says targeting ⇒ measurement is null. The reclassification happens *after* measurement is built, leaving stale measurement objects.
- **Cold-start crash is a pre-existing legacy `charts.py:273-274` defect** running upstream of any V2 ABSTAIN_HARD logic. One-line defensive fix unblocks; architectural fix moves V2 ABSTAIN_HARD upstream of chart rendering.
- **Inventory gate is wired in M5 but not surfacing through V2 considered** — `populate_considered_from_candidates` reads M3 detector output only; M5 guardrail rejections live on a separate path. No merge step exists. Plus on the low_inventory fixture, `bestseller_amplify` isn't even produced as a base candidate, so there's nothing for `gate_inventory` to examine regardless.
- **Materiality floor is computed but not stamped** on `engine_run.json` (`Scale.materiality_floor: null` everywhere). Receipts-completeness defect.
- **`returning_customer_share` is the wrong supporting metric for `first_to_second_purchase`.** It's a state-level statistic of cohort composition, not a directional indicator of intervention efficacy. On a healthy growing brand acquiring new customers, it falls *mechanically* — and the gate correctly does not fire. The metric needs replacement (e.g., `time_to_second_order` distribution shift, or first-to-second conversion rate within newly-acquired cohorts).
- **Tiny-base ratio antipattern in state-of-store:** repeat_rate_within_window 0.8% → +154.7% MoM is reported uncritically. Needs a minimum-base guard.
- **The `_PRELIM_REASON_MAP` (`decide.py:370-379`) only knows about M3 detector preliminary reasons**, not M5 guardrail rejections — this is the structural cause of the Considered card boilerplate.

## Scenario Pass / Fail Table

| # | Scenario | Status | Visible HTML Recommended | EngineRun recommendations[] | Considered | Watching | Decision State | Product P/F | Science P/F | Reason |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | healthy_beauty_240d | Completed | 0 | 0 | 6 | 1 | abstain_soft | **Soft fail** | Soft pass | Engine refused honestly; canonical Phase 5.6 path doesn't fire because L28 returning-share delta is -1.7% (fixture defect). |
| 2 | healthy_beauty_low_inventory_240d | Completed | 0 | 0 | 6 | 1 | abstain_soft | **Hard fail** | **Hard fail** | Inventory state not visible anywhere; M5→V2 wiring gap; bestseller_amplify not even a base candidate. |
| 3 | supplement_replenishment_240d | Completed | 0 | 0 | 6 | 2 | abstain_soft | **Hard fail** | **Hard fail** | Vertical not propagated (ran as beauty); no supplement directional pathway; degenerate 100%-returning state; reporter falsely claimed "1 PRIMARY." |
| 4 | small_store_240d | Completed | 0 | 0 | 6 | 0 | abstain_soft | **Soft pass** | Soft pass | Correct epistemic abstain on $13k/month store, but no "below-scale" memo; `materiality_floor: null`. |
| 5 | cold_start_45d | **Crashed** | N/A | N/A | N/A | N/A | N/A | **Hard fail** | **Hard fail** | Legacy `charts.py:273` matplotlib crash on `None` in `recent` array; V2 ABSTAIN_HARD path unreachable. |
| 6 | promo_anomaly_240d | Completed | **2** | 2 | 6 | 0 | abstain_soft | **Hard fail** | **Hard fail** | (a) Contract ambiguity: implementation permits 2 Targeting cards under ABSTAIN_SOFT, user's contract forbids it. (b) `p_internal` saturated (0.0, 1.6e-72) on targeting cards — invariant violation. (c) Anomaly fixture spike outside L90 lookback. |

By the PM's pass/fail standard (9 criteria), today's pass count is **1 of 9**.

## Cross-Cutting Issues

1. **The user's product contract conflicts with the implementation contract** on whether ABSTAIN_SOFT may render Targeting cards. PM reads contract = no Recommended under ABSTAIN_SOFT. Implementation (`storytelling_v2.py:626-628`, `decide.py:893-895`) was deliberately designed to keep up to 2 Targeting cards. **Both reviewers flag this; it must be resolved before founder testing.**
2. **The legacy stack feeds the V2 stack with structurally defective inputs** (saturated p-values, M5-rejected candidates lost to the merge). The V2 work is correct in isolation but the surrounding plumbing is not.
3. **The synthetic generator is outcome-driven rather than process-driven.** YAML directives like "improving returning customer share 25%->40%+" hit the lifetime aggregate but not the L28-vs-prior delta at the anchor. This pattern will keep biting Phase 6+ tests.
4. **The reason-code taxonomy enum has the right shape but the mapping is incomplete.** `inventory_blocked`, `materiality_floor_failed`, `vertical_not_applicable` are designed for or absent from the considered-list pipeline; the matrix exposes that 5 of 6 healthy considered cards land in `no_measured_signal` because nothing else can.
5. **Watching contract gap:** when every metric MOVED, Watching is empty by design. On stores where everything is in motion (small_store, promo_anomaly), the empty section reads as broken. The Phase 5.3 "load-bearing flat" rule needs a "load-bearing-stable-or-watching-when-merchant-needs-context" extension.

## Merchant-Visible vs Internal Artifact Mismatch

| Scenario | Reporter said | briefing.html actually shows |
|---|---|---|
| healthy_beauty_240d | 2 pilot, 6 considered, 1 watching | 0 Recommended, 6 Considered, 1 Watching |
| healthy_beauty_low_inventory_240d | 1 pilot, 6 considered, 1 watching | 0 Recommended, 6 Considered, 1 Watching |
| supplement_replenishment_240d | 1 PRIMARY, 6 considered, 2 watching | 0 Recommended, 6 Considered, 2 Watching |
| small_store_240d | 0 actions, 6 considered, 0 watching | 0 Recommended, 6 Considered, 0 Watching ✓ |
| cold_start_45d | crash | nothing |
| promo_anomaly_240d | 2 actions, 6 considered, 0 watching | 2 Targeting (under ABSTAIN_SOFT callout), 6 Considered, 0 Watching |

Five of six scenarios have **0 merchant-visible recommendations** by the user's stated contract. The reporter claims the opposite.

## True Blockers Before Founder Testing

Both reviewers agree on these as hard blockers. PM ordered them by product impact; DS ordered by science impact. Reconciled:

1. **Cold-start crash in `src/charts.py:273-274`.** Legacy matplotlib `ax.bar(x - width/2, recent, width, ...)` on a `recent` list containing `None`. Defensive fix is one line. Any thin-history merchant hits this. Founder testing cannot proceed without this fix.
2. **Inventory gate not surfacing through V2 considered list.** The M5 → V2 considered merge is missing. DS recommendation: add a `preliminary_rejection_reason="inventory_blocked"` path in M3 `detect_candidates` so the V2-canonical pipeline picks it up. Also: ensure `bestseller_amplify` actually surfaces as a base candidate on the low-inventory fixture (today it doesn't).
3. **Saturated `p_internal` leaks on targeting cards** — architectural invariant violation. Either drop measurement to `None` after evidence reclassification, or reclassify before measurement is built. The renderer hides it from merchants; leaving it lets future regressions surface saturated stats.
4. **Resolve the ABSTAIN_SOFT + Targeting cards contract.** Pick one: (a) implementation matches user contract → clear `recommendations[]` when `decision_state == abstain_soft` (update `storytelling_v2.py:626-628`, `decide.py:893-895`); or (b) user contract matches implementation → up to 2 Targeting cards under ABSTAIN_SOFT, with renderer copy that no longer says "no primary play" without context. Either is defensible; the current ambiguity is not.
5. **Reporter rewrite to read briefing.html, not internal JSON.** Until done, no automated test summary on this matrix can be trusted. PM's call; DS agreed.
6. **Materiality footer line missing on all six briefings.** Either config drift or a renderer regression versus the Phase 5 sample. Easy to verify.
7. **`VERTICAL_MODE` not propagated per scenario.** All six ran as beauty. Test-harness fix.

## Fixture / Reporter Issues

These are matrix-validity issues. They do not block founder testing of the engine, but they prevent the matrix from validating Phase 5 V2 acceptance until fixed.

- f1. `healthy_beauty_240d` — re-tune generator so L28 returning_customer_share delta is positive at the Sep 18 anchor with sign-stable agreement across L56/L90.
- f2. `supplement_replenishment_240d` — clarify the `repeat_rate_within_window` definition; cap returning-customer share below 100%; add explicit "loyal SKU repeater" cohort and size-token product metadata; ensure VERTICAL_MODE=supplements propagates.
- f3. `promo_anomaly_240d` — move the anchor or move the spike so the spike is within L56.
- f4. Inventory CSV "228 days stale" artifact — align test runner clock to anchor date.
- f5. The generator should be process-driven (realistic cohort dynamics) rather than outcome-driven (YAML targets).
- r1. Reporter reads `candidate_debug.json::pilot_actions/actions` and labels them "pilot" / "PRIMARY"; these are internal-only.
- r2. Reporter does not parse briefing.html DOM.

## Product Improvements Needed

- Reason-code differentiation in Considered card text (today every card on healthy_beauty says identical text).
- Watching-section never-empty contract on healthy stores when load-bearing metrics are present.
- Below-scale memo on small stores (`small_store_240d` should have an explicit "below recommendation threshold" callout).
- State-of-store fact-count consistency (deterministic per scenario class, currently 3–5 facts).
- Restore the materiality footer line.
- The two Targeting cards on promo_anomaly need rewritten copy if they're going to render under ABSTAIN_SOFT.

## Science / Decision Improvements Needed

- Replace `returning_customer_share` as the supporting metric for `first_to_second_purchase`. Use `time_to_second_order` distribution shift or first-to-second conversion rate on newly-acquired cohorts.
- Guard tiny-base ratio reporting in state-of-store (e.g., suppress `% MoM` on metrics with absolute base < threshold).
- Stamp `Scale.materiality_floor` onto `engine_run.json` even when it doesn't reject anything.
- Wire M5 guardrail rejections (inventory, materiality) into the V2 considered-list pipeline so they surface as typed reason codes.
- Move V2 ABSTAIN_HARD detection upstream of legacy chart rendering so cold-start gracefully abstains rather than crashing.
- Stop saturated `p_internal` from flowing through the legacy adapter on targeting cards (enforce measurement = null on targeting evidence class).

## What Can Be Deferred

- Reason-code taxonomy expansion (`vertical_not_applicable`, etc.) — Phase 6.
- Opportunity-context calculator-style sketch on Considered cards. **Both reviewers agree: not yet.** A parametric `audience × AOV × store conversion` block without realization data still risks reading as a forecast. Wait for calibration data.
- Watching-section copy rewording (engineering jargon → merchant language).
- Supplement-vertical directional pathway in `_SUPPORTED` (Phase 6 dependency).
- Per-card per-scenario Considered differentiation (Phase 6).
- Saturated p-values are a real architectural issue but the rendered contract correctly hides them — fixing this is a hard blocker for invariant integrity but does not block founder testing if the renderer guarantee holds.

## PM/DS Disagreements (For Implementation Manager Awareness)

DS pushed back on three PM framings:

1. **promo_anomaly contract violation.** PM called it "decide() and renderer disagree." DS countered: both agree, and it was designed in. The conflict is upstream — between user's stated contract and implementation contract. Resolution requires a product-contract decision, not a code-bug fix.
2. **healthy_beauty soft fail.** PM scored "soft fail." DS countered: should be "soft pass" for the engine and "fixture failure," because the engine refused to fire on a fixture that does not actually carry the upward signal it claims. Reconciled in the Pass/Fail table by labeling Product P/F separately from Science P/F.
3. **Saturated p-values criticality.** PM treated as "internal-only, not concerning at merchant layer." DS extended: the architectural invariant (targeting ⇒ measurement is null) is being violated. Even if the renderer hides it today, the structural defect lets future regressions leak. **DS framing is the right one.** Treating this as a hard blocker.

DS extensions PM did not raise:

- `returning_customer_share` is the wrong metric — measurement-design defect, not configuration.
- Tiny-base ratio antipattern in state-of-store deltas.
- Outcome-driven generator vs. process-driven generator as a structural matrix-quality issue.

## Recommended Next Action

**Do not proceed to founder testing.** Fix the seven blockers in priority order:

1. `charts.py:273` defensive fix (one line).
2. Inventory M5→V2 considered wiring (M3-detector path).
3. Targeting-cards-cleared-of-Measurement invariant enforcement.
4. ABSTAIN_SOFT + Targeting-cards contract resolution.
5. Reporter rewrite (briefing.html DOM parse).
6. Materiality footer regression.
7. Per-scenario VERTICAL_MODE propagation.

After fixes:

8. Re-tune the three high-severity fixtures (healthy_beauty L28 delta, supplement repeat-rate definition, promo anchor placement).
9. Re-run the matrix.
10. Re-run this end-to-end review.

Defer everything else (reason-code taxonomy expansion, opportunity context calculator, supplement vertical pathway, watching never-empty, below-scale memo) to Phase 6.

## Questions For Implementation Manager

1. **Contract decision:** can ABSTAIN_SOFT render up to 2 Targeting cards in the Recommended section, or must it always render zero? This is a one-line product-contract clarification that gates a discrete code change in `decide.py:893-895` and `storytelling_v2.py:626-628`. **Recommend: zero. Rationale: the user's stated product contract takes precedence; the page is unambiguous; the merchant is not asked to reconcile a "no primary play" callout against 2 named recommendations.**
2. **Charts crash fix scope:** defensive one-liner in `charts.py:273` (filter `None` from `recent`/`prior` before `ax.bar`), OR full architectural reorder (V2 ABSTAIN_HARD upstream of chart rendering)? **Recommend: defensive one-liner now; architectural reorder as a Phase 6 chore.**
3. **Inventory M5→V2 wiring:** add `preliminary_rejection_reason="inventory_blocked"` in M3 `detect_candidates` (DS preference), or merge M5 rejected PlayCards into `populate_considered_from_candidates` (alt path)? **DS recommendation is the cleaner path because it keeps M3 as the canonical V2 source of truth.**
4. **Saturated p-value enforcement:** drop measurement to `None` after evidence reclassification (post-hoc clear), or reclassify before measurement is built (architectural reorder)? **Recommend post-hoc clear with an assertion.** Cheaper, achieves the invariant.
5. **Materiality footer regression:** is this a config flag that got dropped, or a renderer code path that was lost? Implementation manager to investigate before assigning to a refactor task.
6. **`returning_customer_share` replacement:** Phase 6 work. Recommend implementation manager scope a sub-phase to evaluate `time_to_second_order` distribution shift as a candidate metric. Don't do it during the blocker-fix pass.
7. **Reporter rewrite:** scope it as a test-tooling chore, not as engine work. The reporter is a separate harness layer.
