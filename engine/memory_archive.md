# BeaconAI Working Memory

This file is the canonical reconciled working memory for the BeaconAI Action Engine. Future agents (planners, implementers, reviewers) should treat the most recent reconciled section below as authoritative direction.

Sources reconciled in this section:
- agent_outputs/statistical-code-reviewer-initial.md
- agent_outputs/ecommerce-ds-architect-initial.md
- agent_outputs/skeptic-red-team-reviewer-initial.md

---

# Decision Core Phase 1 — Reconciled Working Memory

_Reconciled: 2026-05-01_

## Accepted diagnosis
- The current engine is a hypothesis/targeting recommender that presents itself too much like a forecasting and statistical-significance engine.
- The core product should be an ecommerce decision engine that recommends 0–3 high-value Play Theses, not a dashboard or long idea list.
- No recommendation is a valid successful outcome.
- The engine must explain rejected plays.

## Arbitration decisions
- Accept the DS Architect's Detect → Size → Recommend framing.
- Accept the evidence-based vs targeting/heuristic play split.
- Accept the Statistical Reviewer's requirement to remove fabricated p-values, q-values, CIs, and hardcoded effects.
- Accept the Skeptic's blockers as Phase 1 requirements, not future nice-to-haves.
- Phase 1 is a product-contract refactor, not only a stats cleanup.

## Phase 1 must-haves
1. Remove fake stats.
2. Add evidence classes: measured, directional, targeting, weak, blocked.
3. Reclassify heuristic plays so they do not expose p-values, q-values, CIs, or measured effects.
4. Stop multi-window min-p cherry-picking.
5. Simplify confidence so p-values are not counted multiple times.
6. Add abstain mode.
7. Add inventory/OOS gates.
8. Add audience-overlap and cannibalization guardrails.
9. Add anomalous-window/data-quality gates.
10. Add conservative cold-start behavior.
11. Add rejected-play explanations.
12. Add economic materiality gates.

## Play classification
- Winback: MVP-safe, evidence-based if enough history.
- Discount Hygiene: MVP-safe if discount data is reliable.
- Frequency Accelerator: MVP-safe with caveats; remove assumed lift.
- Replenishment Reminder: MVP-safe with caveats; usually targeting unless reorder pattern is strong.
- Late Reorder Rescue / Reorder Drift: MVP-safe with caveats.
- Subscription Candidate: targeting only.
- Routine Completion / Stack Expansion: targeting only.
- Bestseller Attach: targeting only plus inventory gate.
- Category Expansion: targeting only; remove fabricated stats.
- Overstock Demand Push: MVP-safe if inventory exists.
- Low-Stock Suppression: required guardrail / no-call reason.
- First-to-Second Purchase: MVP-safe and preferred replacement for Journey Optimization.
- Product Path / Next Best Product: MVP-safe with caveats.
- Full-Price Buyer Protection: MVP-safe.
- VIP No-Discount Nurture: targeting only.
- Journey Optimization: rename or demote until onsite funnel data exists.
- Retention Mastery: rename to At-Risk Repeat Buyer Rescue; remove assumed churn reduction.
- AOV Momentum: directional only; do not forecast lift from observed AOV drift.

## Revenue / impact principles
- Do not present heuristic/targeting plays with merchant-facing p-values, CIs, or measured lift.
- Avoid assumption-driven dollar forecasts for targeting plays in MVP merchant output.
- For measured/directional plays, revenue impact must be conservative and labeled.
- Total recommended impact should be capped against merchant scale.
- Economic materiality should use a scale-aware floor, e.g. max($5k, 2–5% of monthly revenue), adjusted by merchant size if needed.

## Guardrail principles
- If no candidate clears the bar, output a no-recommendation / data-not-sufficient briefing.
- Do not recommend demand generation for low-stock SKUs.
- Do not recommend multiple overlapping plays to the same audience without cannibalization adjustment.
- Suppress or downgrade recommendations during anomalous windows such as BFCM/post-promo periods, refund spikes, test-order contamination, or insufficient clean history.
- Cold-start stores should get qualitative audience ideas and tracking guidance, not confident forecasts.

## Downstream instruction
All future agents should treat this memory section as the canonical reconciled direction unless explicitly superseded.
Do not remove prior memory sections unless they directly contradict this reconciled direction.

---

# Decision Core Phase 1 — Plan & QA Outcomes

_Added: 2026-05-01_

Sources reconciled in this section:
- agent_outputs/product-strategy-pm-overhaul-requirements.md
- agent_outputs/implementation-manager-overhaul-plan.md
- agent_outputs/ecommerce-ds-architect-implementation-plan-review.md

## Product contract (from PM agent)
- **Merchant vocabulary: 3 buckets** — Strong / Emerging / Targeting. WEAK is internal-only and not surfaced merchant-facing.
- **Two abstain modes**:
  - `ABSTAIN_HARD` → data quality memo, recommendations=[].
  - `ABSTAIN_SOFT` → standard layout + "no measured" callout, 0–2 targeting cards (suppressed/labeled), no $ headlines.
- **Rejection list is a first-class output** with an 11-code `reason_code` enum, surfaced as the "Considered, not recommended" section.
- **Scale-aware materiality floors** (3 ARR tiers): `<$1M → max($5k, 2%)`, `$1–5M → max($10k, 3%)`, `>$5M → max($25k, 5%)` of monthly revenue.
- **Hard contract rules**:
  - `evidence_class == "targeting"` ⇒ `measurement = null`.
  - `revenue_range.suppressed = true` ⇒ renderer hides $; shows audience + AOV only.
  - Cold-start stores ⇒ `revenue_range.suppressed = true`.
- **Phase 1A target slice** = 14–18 working days (PM doc said 10; implementation manager corrected upward — accept 14–18).

## Implementation plan shape (from implementation-manager)
11 milestones, parallel-build-behind-flag (`ENGINE_V2`), golden-fixture freeze first.

- **M0** Golden freeze (pin current outputs as fixtures before any decision-logic touch).
- **M1** Additive `EngineRun` schema; legacy adapter `legacy_actions_from_engine_run()`.
- **M2** Play registry + `config/priors.yaml` (versioned, `source_class ∈ {observational, causal, expert}`).
- **M3** `anomaly.detect_anomalous_windows` + `data_quality_flags[]`.
- **M4** Decision-logic surgery (split into **M4a** additive nan-ing, **M4b** combiner reroute + confidence collapse — see Required Change #6).
- **M5** Guardrails (inventory, anomaly, cannibalization, materiality, recently_run_fatigue).
- **M6** Sizing: priors-driven `revenue_range` with `drivers[]` provenance.
- **M7** Decide: class-first ranking, top-3 cap, abstain logic, considered list, watching.
- **M8** Renderer flip (`ENGINE_V2_OUTPUT`); targeting cards have **no $ p50 headline**.
- **M9** ML-readiness writers: `recommended_history.json`, `calibration_stub.load_realization_factors`.
- **M10** Cleanup; each ticket as its own PR (no monolith commit).

Critical path: M0 → M1 → M2 → M4 → M7 → M8 → M10. Top breakage risk: NaN-cascade through scoring in M4.

## QA verdict on the plan (from DS architect QA)
**APPROVE WITH CHANGES.** Three architecture gaps; six required changes before engineering starts.

### Architecture gaps
- **G1.** Within-class rank-key for TARGETING is still `audience × vertical_prior` (sort-by-audience with extra steps). Mitigated by class-first ranking + M8 $-suppression on targeting cards. **Verify in M8 acceptance** that targeting cards literally render no standalone dollar headline.
- **G2.** `consistency_across_windows` is under-specified post-combiner. Without a spec, `Strong` label can silently re-import the multi-window-as-evidence error.
- **G3.** Anomalous-window detection is binary (HARD-or-not). Partial-window contamination (a 28-day window containing a BFCM week without being centered on it) is not handled — known limitation if not addressed.

### Required changes before engineering starts (6)
1. **Specify `consistency_across_windows` semantics in T4.5**: pre-combination sign-agreement count, not a post-combination p-vote. Default: `count of windows where sign(observed_effect) == sign(combiner.effect) AND |t-stat| > 1`.
2. **Add materiality + class-aware-ranking interaction rule to T7.4**: "If after materiality + cannibalization gating 0 measured/directional remain, demote to ABSTAIN_SOFT regardless of how many TARGETING plays remain. Never publish a TARGETING-only briefing as PUBLISH."
3. **NaN-handling invariant in `evidence.py`**: NaN p with `evidence_class != measured/directional` deterministically yields `confidence_label = Targeting`. NaN p with `evidence_class == measured` is an engine bug — raise.
4. **Lock M8 acceptance**: rendered targeting card HTML contains a range chip but **no standalone dollar number** larger than the range chip text. Add `tests/test_targeting_no_dollar_headline.py` as the mechanical forcing function.
5. **Expand T9.4 stub** return shape from `{}` to `{prior_overrides: {}, evidence_thresholds: {}, materiality_overrides: {}}`. The schema is the contract.
6. **Split M4** into M4a (additive nan-ing, drop redundant BH entry) and M4b (combiner reroute + confidence collapse). Reduces single-PR review burden on highest-stakes milestone.

### Nice-to-haves (not blocking)
- G3 partial-window contamination flag in T5.2 (or document as known limitation).
- Defer T7.9 Watching builder to Phase 1B unless single-run-aware version is fully specified.
- Receipts/debug.html shows `evidence_class`, `p_internal`, observed effect, `n`, drivers — **not** `_calculate_statistical_confidence`'s 0.95/0.80/0.60 stepped buckets.
- Document open question in `docs/play_registry.md`: what `realization_factor` is (ratio? regression? ITT?). Defer to Phase 2 but flag now.
- M6 shadow-compare: capture per-play distribution across fixtures, not just legacy_$ vs v2_p50 ratio.

## Final approved architecture invariants
Must hold across V2:
- `evidence_class == "targeting"` ⇒ `measurement is null`.
- `evidence_class == "measured"` ⇒ `measurement.observed_effect` non-null AND `consistency_across_windows >= 2` AND `p_internal` non-null.
- `revenue_range.suppressed == true` ⇒ renderer hides $; shows audience + AOV.
- `sum(recommendations[].revenue_range.p50) <= 0.25 * monthly_revenue`.
- 0 measured/directional in recommendations ⇒ `ABSTAIN_SOFT`, never `PUBLISH`.
- Any `data_quality_flag` ⇒ `ABSTAIN_HARD`, recommendations=[].
- `briefing.html` contains no `"p ="`, `"q ="`, `"CI"`, `"confidence_score"`, `"final_score"`, or numeric confidence percentage.

## Non-goals (Phase 1)
- Bayesian credible intervals.
- Hierarchical priors over fleet of stores.
- LLM-narrated state-of-store.
- Klaviyo / Shopify network calls.
- "Calibrated" claim in any merchant-facing copy.
- Uplift terminology (ATE, ITT, treatment effect) anywhere.
- "Learning" `CONFIDENCE_MODE` that relaxes thresholds.

## Downstream instruction (Phase 1 plan layer)
- The 6 Required Changes above must be applied to `agent_outputs/implementation-manager-overhaul-plan.md` (or accepted inline at each milestone) before M0 engineering starts.
- Subsequent agents should treat this plan layer as authoritative on the *how*; the earlier reconciled section remains authoritative on the *what*.

---

# Decision Core Overhaul — Final Planning Freeze

_Frozen: 2026-05-01_

Final implementation plan:
`agent_outputs/implementation-manager-overhaul-plan-final.md`

Planning loop is closed.
Engineering starts with Milestone 0 only.

No further PM, DS Architect, or Skeptic review is required unless:
- implementation reveals a blocker,
- the local CSV → HTML workflow breaks,
- M0 goldens cannot be created,
- or the code-refactor-engineer cannot preserve runnable behavior.

Agents must not re-litigate:
- whether to overhaul,
- whether to remove fake stats,
- whether evidence classes are needed,
- whether targeting plays hide p/q/CI,
- whether abstain mode exists,
- whether V2 should be built behind flags.

If any milestone numbering differs between this memory file and the final implementation plan, agent_outputs/implementation-manager-overhaul-plan-final.md is authoritative for milestone numbering and execution order.

# Milestone 0 Complete — Golden Freeze

Milestone 0 is complete.

Completed:
- 3 merchant fixtures pinned.
- Golden outputs created.
- Golden diff test added and passing.
- Existing CSV -> HTML workflow verified.
- No recommendation, scoring, or briefing behavior intentionally changed.
- `_FORCE_SINGLE_WINDOW` cleanup applied with byte-identical briefing diff confirmed.
- Existing flag inventory documented.
- Makefile target added.

M0 verification:
- `pytest tests/test_golden_diff.py` → 3 passed.
- Golden tree: 3 merchants × (briefing.html + 6 receipts JSON) = 21 files.
- Charts and segment ZIPs intentionally excluded from goldens due to nondeterministic font glyphs and ZIP metadata.

M0 summary:
agent_outputs/code-refactor-engineer-milestone-0-summary.md

Engineering may proceed to Milestone 1 only.

# Milestone 1 Complete — Additive EngineRun + Anomaly Foundation

Milestone 1 is complete.

Completed:
- Added typed EngineRun schema.
- Added anomaly detection module and thresholds config.
- Added typed state-of-store Observation builder.
- Added legacy-to-EngineRun adapter.
- Added receipts/engine_run.json on every run.
- Added anomaly validation class as opt-in only.
- Merchant-facing output unchanged.
- Existing CSV -> HTML workflow still runs.
- M0 golden diff remains passing.

M1 verification:
- `python -m pytest tests/ -v` → 34 passed.
- `python -m pytest tests/test_golden_diff.py -v` → 3 passed.
- Two end-to-end smoke runs produced receipts/engine_run.json.

Accepted deviation:
- AnomalousWindowCheck is defined but not auto-registered in DataValidationEngine yet, to preserve M0 validation_report.json goldens. M5 will flip/register anomaly gating.

M1 summary:
agent_outputs/code-refactor-engineer-milestone-1-summary.md

Engineering may proceed to Milestone 2 only.

# Milestone 2 Complete — Play Registry + Priors Config

Milestone 2 is complete.

Completed:
- Added typed Play Registry.
- Added config/priors.yaml.
- Added docs/play_registry.md.
- Registry covers 11 legacy emitted play IDs plus 3 new planned entries.
- Registry and priors are schema-tested.
- No runtime behavior changed.
- No merchant-facing output changed.
- Existing CSV -> HTML workflow still runs.
- M0 golden diff remains passing.

M2 verification:
- `python -m pytest tests/ -v` → 60 passed.
- `python -m pytest tests/test_golden_diff.py -v` → 3 passed.
- Smoke run on `data/SM_orders.csv` produced the legacy briefing and same 3 PRIMARY actions.

Accepted note:
- Legacy emitted play count is 11, not 10, because `empty_bottle` is its own candidate. It is now registered.
- Registry is not wired into runtime yet; M3 is the first milestone that should read PLAYS.

M2 summary:
agent_outputs/code-refactor-engineer-milestone-2-summary.md

Engineering may proceed to Milestone 3 only.

# Milestone 3 Complete — Shadow Candidate Detection

Milestone 3 is complete.

Completed:
- Added pure audience builders.
- Added shadow-only detect_candidates().
- Added Candidate schema with forbidden-fields enforcement.
- Added pairwise audience overlap computation.
- Added cold_start flag as logged-only.
- Added ENGINE_V2_SHADOW-gated receipts/v2_candidates.json.
- Default CSV -> HTML workflow remains unchanged.
- Existing recommendations and briefing UX remain unchanged.

M3 verification:
- M3 test suites: 57 passed.
- Shadow integration tested all three M0 fixtures.
- v2_candidates.json is produced only when ENGINE_V2_SHADOW=true.
- Candidate objects contain no p/q/confidence/revenue/CI/effect/score/rank/recommended fields.

Accepted notes:
- Registry contains 14 plays. M3 has builders for all legacy-emitted plays.
- at_risk_repeat_buyer_rescue and onsite_funnel_watch intentionally surface as no_builder until later milestones.
- A pre-existing ULP-level golden-test float drift exists in legacy receipts. Track separately before M4a review.

M3 summary:
agent_outputs/code-refactor-engineer-milestone-3-summary.md

Engineering may proceed to Milestone 4a only, after filing a separate golden-test float stability ticket.

Ticket: Golden-test float stability

Problem:
tests/test_golden_diff.py intermittently flakes on small_sm due to ULP-level drift in legacy JSON receipts.

Observed drifting fields:
- effect_size
- ci_high
- expected_$
- final_score

Scope:
Canonicalize float serialization in legacy receipt outputs or normalize float comparison in the golden diff test.

Constraint:
Do not change decision logic.
Do not change merchant-facing briefing.
Do not touch M4a evidence behavior.

Priority:
Before or alongside M4a review, because M4a will intentionally change stats-related outputs and needs clean diffs.

# Milestone 4a Complete — Fabricated-Stats NaN Gate + Evidence Class Field

Milestone 4a is complete.

Completed:
- Added src/evidence.py.
- Added EvidenceClass classification boundary.
- Added NaN-handling invariant:
  - targeting + NaN p => Targeting
  - measured/directional + NaN p => engine bug / raises
- Added STATS_NAN_FOR_HARDCODED flag.
- Added EVIDENCE_CLASS_ENFORCED flag.
- Added fabricated-stat NaN gate for the audit play list.
- Added NaN-safe scoring helpers.
- Added evidence_class stamping behind flag.
- Dropped duplicated new_customer_rate BH entry behind STATS_NAN_FOR_HARDCODED.
- Disabled ENABLE_COHORT_POOLING and ENABLE_REPEAT_RATE_BIAS_CORRECTION defaults.
- Renderer unchanged.
- M4b work not implemented yet.

M4a verification:
- Full suite: 184 passed, 5 skipped.
- Evidence / NaN-safety tests passed.
- Fabricated-stat integration tests passed.
- End-to-end smoke runs passed with both M4a flags on.
- Renderer untouched.
- Briefing template untouched.

Accepted behavior change:
- small_sm golden was regenerated because ENABLE_REPEAT_RATE_BIAS_CORRECTION default changed from true to false.
- This caused a mechanical repeat-rate / expected-revenue drift.
- mid_shopify and micro_coldstart goldens remained unchanged.
- This default flip was part of the approved M4a scope.

Open risk:
- Pre-existing ULP-level golden-test float flake remains unresolved.
- Track under Side Ticket — Golden-Test Float Stability before or alongside M4b review.

M4a summary:
agent_outputs/code-refactor-engineer-milestone-4a-summary.md

Engineering may proceed to Milestone 4b only, but M4b reviewers must expect substantial golden diffs.

# Milestone 4b Complete — Targeting Reclassification + Combiner Reroute

Milestone 4b is complete.

Completed:
- Reclassified targeting plays deterministically.
- Targeting plays now drop measurement in EngineRun.
- Measured/directional multi-window candidates use combine_multiwindow_statistics.
- Legacy min-p merge is bypassed on the M4b V2 path.
- consistency_across_windows is a pre-combination sign-agreement count, not a p-vote.
- Confidence path now short-circuits to single statistical confidence term when EVIDENCE_CLASS_ENFORCED=true.
- evidence_for_action labels targeting plays as targeting recommendations.
- M4b flag-on goldens regenerated.

M4b verification:
- Full suite: 217 passed, 5 skipped.
- test_consistency_across_windows.py passed.
- test_multiwindow_combiner.py passed.
- golden diff passed with M4b flags forced on.
- Renderer untouched.
- Briefing template untouched.

Accepted transition state:
- small_sm produces 0 PRIMARY actions and $0 expected impact under M4b flag-on.
- This is expected because targeting plays no longer pass measured significance gates.
- M5-M8 are responsible for guardrails, sizing, decision states, abstain, and the new Play Thesis renderer.
- Do not treat 0 PRIMARY in M4b as a final product state.

Accepted test caveat:
- tests/test_golden_diff.py now tests the M4b canonical flag-on state.
- Legacy flags-off path remains runnable but is not byte-diffed against a separate legacy golden lane.
- Add a separate flags-off lane only if needed during M5-M8.

Open risk:
- Pre-existing ULP-level golden-test float flake remains tracked under Side Ticket — Golden-Test Float Stability.

M4b summary:
agent_outputs/code-refactor-engineer-milestone-4b-summary.md

Engineering may proceed to Milestone 5 only.

# Milestone 5 Complete — Guardrail Engine

Milestone 5 is complete.

Completed:
- Added src/guardrails.py.
- Added inventory gate.
- Added anomalous-window hard abstain gate.
- Added scale-aware materiality floor.
- Added audience-overlap / cannibalization gate.
- Added portfolio cap.
- Added recently-run fatigue reader stub.
- Confirmed repeat-rate bias correction default remains off and removed bypass.
- Pinned seasonality-confidence decoupling.
- Added M5 flags, all default off.
- Renderer unchanged.
- Merchant-facing Play Thesis unchanged.

M5 verification:
- Full suite: 306 passed, 5 skipped.
- M5 guardrail tests passed.
- M4b canonical goldens still pass.
- No goldens re-baselined.
- End-to-end smoke runs passed.

Accepted caveats:
- Guardrails currently affect EngineRun receipts, not legacy actions_log or merchant-facing briefing. M7/M8 will make EngineRun authoritative.
- POST_PROMO_WINDOW is a soft warning, not ABSTAIN_HARD.
- revenue_range.seasonality_factor and launch_window.recommended are deferred to M6/M8; confidence decoupling is already enforced.

M5 summary:
agent_outputs/code-refactor-engineer-milestone-5-summary.md

Engineering may proceed to Milestone 6 only.

# Milestone 6 Complete — Conservative Economic Sizing

Milestone 6 is complete.

Completed:
- Added src/priors_loader.py.
- Added src/sizing.py.
- Added ENGINE_V2_SIZING flag, default off.
- Added conservative sizing formula:
  audience × p_action × incremental_orders × AOV.
- Added cold-start suppression.
- Added targeting suppression for non-causal priors.
- Added revenue_range.drivers[] provenance.
- Added v2_sizing_shadow.json.
- Preserved legacy calculate_28d_revenue.
- Renderer unchanged.
- Merchant-facing briefing unchanged.

M6 verification:
- Full suite: 337 passed, 5 skipped.
- Priors loader tests passed.
- Sizing tests passed.
- Golden diff passed with no re-baseline.
- End-to-end smoke runs passed.
- v2_sizing_shadow.json produced when ENGINE_V2_SIZING=true.

Accepted behavior:
- All current targeting plays are suppressed under V2 sizing because priors are expert/observational, not causal.
- This is intentional and conservative.
- Legacy expected_$ remains untouched in legacy output.
- M7 must wire measured/directional plays through the V2 decision path so observed-effect plays can receive non-suppressed ranges.

M6 summary:
agent_outputs/code-refactor-engineer-milestone-6-summary.md

Engineering may proceed to Milestone 7 only.

# Milestone 7 Complete — V2 Decision Selector

Milestone 7 is complete.

Completed:
- Added src/decide.py.
- Added decide(engine_run, cfg) -> EngineRun.
- Added class-aware ranking: measured > directional > targeting.
- Added max-3 recommendation cap.
- Added cap_exceeded considered/rejection handling.
- Added ABSTAIN_HARD, ABSTAIN_SOFT, and PUBLISH decision state logic.
- Enforced targeting-only => ABSTAIN_SOFT, never PUBLISH.
- Added considered/rejected assembly.
- Added would_fire_if templates.
- Added deterministic Watching builder.
- Added ENGINE_V2_DECIDE flag, default off.
- Renderer unchanged.
- Merchant-facing HTML unchanged.

M7 verification:
- Full suite: 371 passed, 5 skipped.
- test_decide.py passed.
- golden diff passed.
- make golden-test passed.
- No goldens re-baselined.
- End-to-end smoke runs passed.

Accepted implementation choice:
- M7 composes the existing EngineRun produced by the legacy adapter plus M5/M6 layers.
- M7 does not rebuild EngineRun directly from M3 candidates.
- This preserves M3's no-stat Candidate contract and avoids risky rewiring.

Accepted transition caveat:
- With M4b flags off, the legacy adapter can label legacy actions as targeting.
- This is a transition artifact and should not be treated as final evidence behavior.
- M8 should render from V2 EngineRun only when the full V2 flag stack is intentionally enabled.

M7 summary:
agent_outputs/code-refactor-engineer-milestone-7-summary.md

Engineering may proceed to Milestone 8 only.

# Milestone 8 Complete — V2 Play Thesis Renderer

Milestone 8 is complete.

Completed:
- Added src/storytelling_v2.py.
- Added V2 render_engine_run(engine_run) -> HTML.
- Added state-of-store lead section.
- Added Recommended section.
- Added Considered / rejected section.
- Added Watching section.
- Added data-quality footer.
- Added ABSTAIN_SOFT layout with “no measured opportunities cleared” callout.
- Added ABSTAIN_HARD data-quality memo with no recommendations rendered.
- Added targeting-card visual treatment and fixed disclaimer.
- Added targeting no-dollar-headline invariant.
- Added ENGINE_V2_OUTPUT flag, default off.
- Added briefing.py router behind ENGINE_V2_OUTPUT.
- Preserved legacy renderer as default.
- Preserved legacy briefing template and actions_log behavior.

M8 verification:
- Full suite: 401 passed, 5 skipped.
- test_render_v2.py passed.
- test_targeting_no_dollar_headline.py passed.
- golden diff passed.
- No goldens re-baselined.
- V2 smoke runs produced complete HTML for pinned fixtures.
- V2 outputs contain no p/q/CI/confidence_score/final_score strings.

Accepted transition caveat:
- All real pinned fixtures currently render as ABSTAIN_SOFT under the full V2 stack.
- This is expected from the M4b/M6 transition state and is not a renderer bug.
- Synthetic tests cover PUBLISH and ABSTAIN_HARD layouts.

Accepted wiring caveat:
- legacy_actions_from_engine_run exists but is not wired into main.py.
- Legacy consumers still read the legacy actions_bundle until a later migration step.
- Do not flip V2 output default until this wiring/default-flip decision is explicitly reviewed.

M8 summary:
agent_outputs/code-refactor-engineer-milestone-8-summary.md

Engineering may proceed to Milestone 9 only.

# Milestone 9 Complete — ML Readiness / Outcome Logging

Milestone 9 is complete.

Completed:
- Added src/outcome_log.py.
- Added src/calibration_stub.py.
- Added src/debug_renderer.py.
- Added recommended_history.json writer.
- Added OUTCOME_LOG_ENABLED and OUTCOME_LOG_PATH.
- Added calibration stub with required return shape:
  - prior_overrides
  - evidence_thresholds
  - materiality_overrides
- Added merchant-invisible receipts/debug.html.
- Added measurement persistence tests for p_internal and ci_internal.
- Added revenue_range.drivers provenance invariant.
- Added privacy safeguards:
  - no raw customer IDs
  - no customer emails
  - local file only
  - gitignored runtime history
  - writer never raises
- Merchant-facing briefing unchanged.
- V2 renderer unchanged.
- Decision logic unchanged.
- No ML claims added.

M9 verification:
- Full suite: 434 passed, 5 skipped.
- Golden diff passed.
- Outcome log append / recovery tests passed.
- Calibration stub shape tests passed.
- Internal stats appear in debug.html.
- Internal stats do not appear in briefing.html.
- No V2 default flip.
- No goldens re-baselined.

Accepted notes:
- OUTCOME_LOG_ENABLED defaults true because writing is safe, local, deterministic enough for runtime use, and gitignored.
- receipts/debug.html is produced unconditionally when EngineRun exists, but is internal-only and not linked from merchant-facing briefing.
- Calibration stub does not read history yet and always returns empty override maps.
- Outcome log has schema_version but no migration path yet; future schema changes need a migrator.

M9 summary:
agent_outputs/code-refactor-engineer-milestone-9-summary.md

Engineering may proceed to Milestone 10 only after an explicit cleanup/default-flip decision.

# Phase 5 Complete — Honest Considered List + One Measured Pathway

Phase 5 is complete.

Motivation:
- After M0–M9, V2 was scientifically honest but operationally inert on real fixtures.
- Beauty Brand rendered ABSTAIN_SOFT with empty Recommended / Considered / Watching even though the dataset has real signal.
- Goal: make V2 useful on Beauty Brand without restoring legacy's fake statistical claims.

Completed (5.1–5.7):
- 5.1 Rewrote ABSTAIN_SOFT copy.
  - Replaced "no measured or directional recommendation cleared materiality + cannibalization gating" with merchant-readable copy keyed by the dominant gate (no-evidence / materiality / overlap).
  - EngineRun abstain.reason now merchant-readable.
- 5.2 Populate Considered list during ABSTAIN_SOFT.
  - Added populate_considered_from_candidates() that maps M3 candidates to RejectedPlay entries with reason_code, reason_text, evidence_snapshot, would_fire_if.
  - Considered now renders even when decision_state == ABSTAIN_SOFT.
- 5.3 Extended Watching.
  - Added returning_customer_share and net_sales observations and thresholds.
  - Softened build_watching so flat load-bearing metrics surface as "stable, watching" instead of being filtered out.
  - Suppressed/labeled repeat_rate_within_window when no identified customers exist, instead of rendering it as 0.0%.
  - Observation cap raised from 5 to 7 to fit the new metrics.
- 5.4 Materiality footer rewritten.
  - Replaced "Materiality floor: $X" with "We only recommend primary plays that could realistically add at least $X this month for a store your size."
  - Exact numeric floor remains in receipts/debug.html.
- 5.5 Aura / Beacon Score absence verified in V2.
  - Forbidden-token sweep test added across PUBLISH, ABSTAIN_SOFT, ABSTAIN_HARD layouts.
- 5.6 Wired one directional pathway from M3 into V2.
  - Added src/measurement_builder.py producing a directional PlayCard for first_to_second_purchase when L28 returning_customer_share p<0.05 and sign agreement >=2 across windows.
  - Revenue range is suppressed (no calibrated lift; no fabrication).
  - No causal prior was added.
  - Evidence class is directional only; no measured claim.
  - p_internal / ci_internal stay in EngineRun and debug.html, not merchant briefing.
- 5.7 Defensive cleanup: journey_optimization suppressed in V2.
  - PHASE5_V2_SUPPRESS_PLAY_IDS filters journey_optimization out of considered and recommendations on the V2 path.
  - Legacy emitter unchanged.

Phase 5 verification:
- Full suite: 487 passed, 5 skipped (was 434 at end of M9; +53 new tests).
- Golden diff passed; no goldens re-baselined.
- Targeting no-dollar-headline invariant: 6 passed.
- End-to-end V2 stack runs on data/beauty_brand_orders.csv, data/SM_orders.csv, data/shopify_orders_mid.csv.
- Default-mode (no V2 flags) regression byte-identical to legacy goldens.

Beauty Brand before vs after (full V2 stack):
- Before: ABSTAIN_SOFT, recommendations=0, considered=0, watching=0; near-empty briefing with 3 empty placeholders + jargon callout + raw "Materiality floor: $10,000".
- After: PUBLISH, recommendations=1 (directional first_to_second_purchase, suppressed revenue), considered=6 (each with reason_code + would_fire_if), watching=2, merchant-readable copy, zero forbidden statistical strings.
- small_sm and mid_shopify still ABSTAIN_SOFT but now have populated Considered and Watching sections, removing the near-empty-page defect.

Accepted notes:
- returning_customer_share is a state statistic, not an intervention effect. The directional card is defensible but a future agent could be tempted to promote it to measured + non-suppressed revenue. The driver suppression note is the forcing function.
- 5.7 suppresses journey_optimization only on the V2 path; legacy emitter still produces it (M10 owns the deletion).
- 5.2 quietly drops vertical-not-applicable plays from considered rather than rendering a typed reason card. PM can reverse this later by adding a typed reason code.
- M3 detect re-runs on every V2 call; small cost, can be cached if needed.
- M1 docstring still says 3-5 observations; cap is now 7. Minor sync follow-up.

Phase 5 summary:
agent_outputs/code-refactor-engineer-phase5-summary.md

Pre-rendered Beauty Brand sample:
agent_outputs/phase5_samples/beauty_brand_v2_briefing.html

Phase 5 acceptance:
- Phase 5 is shippable as-is. Recommended next step is manual founder testing on Beauty Brand and one synthetic-realistic fixture before any M10 cleanup or V2 default flip.
- No M10 cleanup. No V2 default flip.

Downstream instruction:
Future agents should not promote the Phase 5.6 directional card to evidence_class=measured or unsuppress revenue without an explicit, calibrated causal prior backed by realized campaign outcomes. Wire at_risk_repeat_buyer_rescue similarly only after its M3 audience builder lands. Do not reintroduce Aura, Beacon Score, fake p/q/CI/confidence into V2.

# Phase 5.1 Complete — Addressable Opportunity Context

Phase 5.1 is complete.

Motivation:
- Phase 5.6 correctly suppresses revenue_range for the directional first_to_second_purchase card because returning_customer_share is a state statistic, not an intervention effect.
- Merchants still need economic context before deciding whether to run a campaign.
- Goal: render addressable opportunity context as body copy on suppressed-revenue cards without claiming projected lift.

Completed:
- Added OpportunityContext typed dataclass in src/engine_run.py:
  - audience_size, aov, addressable_value, aov_window, aov_source.
  - Round-trips through to_dict / from_dict.
- Added optional PlayCard.opportunity_context field.
- Added _resolve_aov_for_context in src/measurement_builder.py:
  - Reads aov from kpi_snapshot_with_deltas in priority order L28 -> L56 -> L90.
  - Returns None when no defensible AOV window exists; no fabrication.
- Added _build_opportunity_context, populated on the Phase 5.6 directional card when audience and AOV are both available.
- Added _render_opportunity_context_block in src/storytelling_v2.py:
  - Renders inside _render_measured_card body only.
  - Targeting renderer is untouched.
  - Renders only when revenue_range is suppressed or absent.
  - Uses "about $X" framing with magnitude-band rounding so the value never reads as a precise forecast.
  - Carries the disclaimer "This is not projected lift; it shows the size of the audience if the play converts."

Phase 5.1 verification:
- Full suite: 507 passed, 5 skipped (was 487 at end of Phase 5; +20 new tests).
- New file tests/test_phase5_1_opportunity_context.py: 20 passed.
- Targeting no-dollar-headline invariant: still passes.
- Golden diff: 3 passed; no goldens re-baselined.
- Forbidden-token sweep on Beauty Brand V2 briefing: 0 occurrences of p =, q =, CI, confidence_score, final_score, p_internal, ci_internal, expected revenue, expected impact, p50, forecast, predicted. The phrase "projected lift" appears only inside the negation disclaimer.

Beauty Brand V2 card after Phase 5.1:
- Opportunity context: "286 eligible customers x $69 recent AOV (L28) = about $19.7k addressable order value. This is not projected lift; it shows the size of the audience if the play converts."
- revenue_range.suppressed remains true; p10 / p50 / p90 remain null in engine_run.json.

Accepted notes:
- AOV is read from kpi_snapshot_with_deltas[window]["aov"]. A future change to that AOV definition would silently shift the merchant-facing addressable value. Any change to that snapshot field needs to be reviewed against this contract.
- audience x AOV is defensible for first_to_second_purchase; future directional plays may need a per-play addressable_order_multiplier if their target action is not a single full-AOV order.
- The receipts carry precise float AOV; merchant HTML rounds to e.g. "$69" / "about $19.7k". Both forms are documented in engine_run.json and briefing.html respectively.
- Block does not render on suppressed targeting cards. Targeting no-dollar-headline invariant unchanged.
- If revenue_range is later unsuppressed (e.g., calibrated lift arrives), the calibrated range wins and the opportunity-context block hides itself automatically.

Phase 5.1 summary:
agent_outputs/code-refactor-engineer-phase5-1-opportunity-context-summary.md

Phase 5.1 acceptance:
- Phase 5.1 is shippable as-is.
- No decision logic changed. No sizing logic changed. No causal prior added.
- No M10 cleanup. No V2 default flip.

Downstream instruction:
Future directional plays should reuse _build_opportunity_context rather than open-coding addressable-value math. Do not extend the block to targeting cards in a way that violates the M8 targeting-no-dollar-headline invariant. Do not present "addressable value" as projected revenue, expected revenue, p50, forecast, or expected impact in any future copy.

# Synthetic Blocker Fix 1 Complete — Cold-Start Chart Crash

Fix 1 is complete.

Completed:
- Added None-safe chart handling in src/charts.py.
- Filter uses `is not None`, so zero values are preserved.
- Added tests/test_charts_none_safe.py.
- cold_start_45d no longer crashes and now produces briefing.html.

Verification:
- New chart tests: 5 passed.
- Golden diff: 3 passed, no re-baseline.
- Full suite: 583 passed, 11 skipped.
- E2E cold_start_45d produced briefing.html with no traceback.

Accepted caveat:
- cold_start_45d now renders through the legacy path and can still produce a PRIMARY recommendation.
- This is not a Fix 1 regression.
- Merchant-honest cold-start ABSTAIN_HARD before legacy chart/rendering remains a Phase 6 architectural reorder.

Fix 1 summary:
agent_outputs/code-refactor-engineer-synthetic-fix-1-summary.md

Proceed to Synthetic Blocker Fix 2 only.

# Synthetic Blocker Fix 2 Complete — Targeting Measurement Invariant

Fix 2 is complete.

Completed:
- Added structural enforcement that targeting PlayCards cannot carry Measurement.
- Added post-hoc clear + assertion in src/engine_run_adapter.py.
- Added tests/test_targeting_measurement_invariant.py.
- Closed leak path where legacy actions coerced to TARGETING retained stale measurement/p_internal.

Verification:
- New targeting measurement invariant tests: 6 passed, 1 skipped.
- Pre-fix TDD confirmed 3 tests failed, including saturated p_internal on promo_anomaly targeting card.
- tests/test_targeting_no_dollar_headline.py: 6 passed.
- Golden diff: 3 passed, byte-identical, no re-baseline.
- V2 / forbidden-string / engine-run-schema checks: 80 passed.
- Full suite: 589 passed, 12 skipped.
- Smoke run on data/SM_orders.csv: 3 targeting recommendations, 0 measurement leaks.

Accepted caveat:
- Matrix-wide regression test remains skipped until Fix 7 reporter rewrite creates durable per-scenario engine_run.json artifacts.
- ABSTAIN_SOFT + Recommended targeting-card policy conflict remains open for Fix 3.

Fix 2 summary:
agent_outputs/code-refactor-engineer-synthetic-fix-2-summary.md

Proceed to Synthetic Blocker Fix 3 only.

# Synthetic Blocker Fix 3 Complete — ABSTAIN_SOFT Contract

Fix 3 is complete.

Completed:
- Enforced ABSTAIN_SOFT => recommendations=[].
- Added ReasonCode.TARGETING_HELD_UNDER_ABSTAIN.
- Routed held targeting cards from Recommended into Considered under ABSTAIN_SOFT.
- Added reason_text and would_fire_if templates for held targeting cards.
- Updated src/decide.py to split PUBLISH vs ABSTAIN_SOFT behavior.
- Updated src/storytelling_v2.py so MAX_ABSTAIN_SOFT_TARGETING_CARDS = 0.
- Preserved Phase 5.1 merchant-readable ABSTAIN_SOFT copy.
- Preserved PUBLISH behavior.

Verification:
- New tests/test_abstain_soft_no_recommendations.py: 11 passed.
- Pre-fix TDD confirmed 5 failures.
- Full suite: 600 passed, 12 skipped.
- Golden diff: 3 passed, no re-baseline.
- Forbidden-string and targeting no-dollar-headline tests still pass.
- E2E smoke on promo_anomaly and SM_orders:
  - 0 Recommended targeting articles.
  - 6 Considered.
  - ABSTAIN_SOFT callout present.

Fix 3 summary:
agent_outputs/code-refactor-engineer-synthetic-fix-3-summary.md

Proceed to Synthetic Blocker Fix 4 only.
# Synthetic Blocker Fix 4 Complete — Inventory Block Visibility

Fix 4 is complete.

Completed:
- Updated detect_candidates to accept optional inventory_metrics.
- SKU-pushing plays can now be stamped with preliminary_rejection_reason="inventory_blocked".
- Inventory-block stamping applies when min cover_days is below threshold.
- No-op when inventory_metrics is unavailable.
- Wired inventory_metrics through both detect_candidates call sites.
- Added "inventory_blocked" to _PRELIM_REASON_MAP.
- Confirmed ReasonCode.INVENTORY_BLOCKED already existed.
- Added merchant-readable considered reason:
  "Hero SKU at low stock; held until restock."
- Added would_fire_if copy:
  "Would fire when stock on the hero SKU recovers above the cover-days threshold."

Verification:
- New inventory-block tests: 12 passed.
- Pre-fix TDD confirmed 10 failures.
- Full suite: 612 passed, 12 skipped.
- Golden diff: 3 passed, no re-baseline.
- Existing M5 inventory gate behavior unchanged.
- Fix 2 targeting-measurement invariant unchanged.
- Fix 3 ABSTAIN_SOFT contract unchanged.
- bestseller_amplify surfaced as a base candidate with audience=1357 on low-inventory fixture.

Accepted caveat:
- Full low-inventory E2E validation is deferred until Fix 11 because the fixture currently has stale inventory / timezone issues.
- Current merchant copy says generic “Hero SKU” rather than naming the SKU; SKU-specific copy is deferred.

Fix 4 summary:
agent_outputs/code-refactor-engineer-synthetic-fix-4-summary.md

Proceed to Synthetic Blocker Fix 5 only.

# Synthetic Blocker Fix 5 Complete — Materiality Footer Restoration

Fix 5 is complete.

Completed:
- Restored merchant-readable materiality footer on V2 briefings.
- Root cause: scale.materiality_floor was None on synthetic runs because _scale_from_aligned initialized it to None and guardrail stamping only happened when MATERIALITY_FLOOR_SCALE_AWARE was enabled.
- Fixed by stamping materiality_floor unconditionally in src/engine_run_adapter.py using the existing scale_aware_materiality_floor() helper.
- Values use the same source of truth as M5 and did not change.
- Renderer now has the value needed to show:
  "We only recommend primary plays that could realistically add at least $X this month for a store your size."

Verification:
- New tests/test_materiality_footer_present.py: 9 passed.
- Phase 5.4 copy tests: 4 passed.
- M5 guardrail tests: 51 passed.
- Golden diff: 3 passed, no re-baseline.
- Full suite: 621 passed, 12 skipped.
- All six synthetic fixtures now show the merchant-readable sentence on non-ABSTAIN_HARD pages.
- No "Materiality floor:" jargon appears in V2 briefing HTML.

Accepted note:
- ABSTAIN_HARD pages may also show the sentence; the implementation plan allowed this. Suppressing it on cold-start can be a later one-line product tweak if PM wants.

Fix 5 summary:
agent_outputs/code-refactor-engineer-synthetic-fix-5-summary.md

Proceed to Synthetic Blocker Fix 6 only.
# Synthetic Blocker Fix 6 Complete — Per-Scenario Vertical Propagation

Fix 6 is complete.

Completed:
- Added tests/synthetic_harness.py.
- Added tests/test_matrix_vertical_propagation.py.
- Synthetic harness now loads scenario metadata and maps YAML category to engine VERTICAL_MODE.
- Harness builds per-scenario subprocess env and reads receipts/engine_run.json.
- Added assert_vertical_propagated().
- No engine source files changed.

Verification:
- All six synthetic scenarios now propagate declared vertical to engine_run.briefing_meta.vertical.
- supplement_replenishment_240d now runs as supplements.
- beauty scenarios run as beauty.
- New tests: 34 passed, 2 opt-in E2E skipped by default.
- Opt-in E2E passes when RUN_VERTICAL_PROPAGATION_E2E=1.
- Golden diff: 3 passed, no re-baseline.
- Full suite: 657 passed, 14 skipped.

Accepted caveat:
- src/utils.py manual .env fallback can overwrite os.environ, including VERTICAL_MODE, when python-dotenv is unavailable.
- The harness avoids this by running subprocesses from an .env-free cwd with PYTHONPATH set to repo root.
- A future cleanup should change the fallback to use setdefault semantics, but this was kept out of Fix 6 scope.

Fix 6 summary:
agent_outputs/code-refactor-engineer-synthetic-fix-6-summary.md

Proceed to Synthetic Blocker Fix 7 only.
# Synthetic Blocker Fix 7 Complete — DOM-Only Synthetic Reporter

Fix 7 is complete.

Completed:
- Added tests/synthetic_reporter.py.
- Reporter now parses briefing.html DOM as the source of truth for merchant-visible state.
- Added tests/test_reporter_dom_only.py.
- Added beautifulsoup4>=4.12.0 to requirements.txt.
- Reporter derives:
  - visible Recommended count
  - visible Considered count
  - visible Watching count
  - ABSTAIN_SOFT callout presence
  - ABSTAIN_HARD memo presence
  - materiality footer presence
- Reporter may use engine_run.briefing_meta only as context.
- Reporter no longer reads candidate_debug.json, engine_run.recommendations[], v2_sizing_shadow.json, receipts/debug.html, or actions_log.json for merchant-visible state inference.

Verification:
- New reporter tests: 17 passed.
- Negative tests monkey-patch builtins.open to prove forbidden artifacts are not opened.
- Full suite: 674 passed, 14 skipped.
- Golden diff: 3 passed, no re-baseline.
- All six synthetic scenarios run end-to-end with the new reporter wired in.

Accepted note:
- product_contract_pass remains None; verdict logic is out of scope for Fix 7.

Fix 7 summary:
agent_outputs/code-refactor-engineer-synthetic-fix-7-summary.md

Proceed to Synthetic Fixture Retuning Fixes 8–11.

# Synthetic Blocker Fixes 8–11 Complete — Fixture Retuning

Fixes 8–11 are complete.

Completed:
- Retuned healthy_beauty_240d so Phase 5.6 directional first_to_second_purchase fires.
- Retuned supplement_replenishment_240d:
  - vertical now propagates as supplements
  - returning_customer_share below 100%
  - subscription_nudge audience is non-degenerate
- Retuned promo_anomaly_240d so the August spike is inside L56.
- Retuned low_inventory fixture so inventory data reads fresh and timezone mismatch is resolved fixture-side.
- Regenerated synthetic fixture CSVs.
- Added tests/test_synthetic_fixtures_8_11.py.
- Saved sample briefings under agent_outputs/synthetic_fixes_8_11_samples/.

Verification:
- Full suite: 687 passed, 14 skipped.
- Golden diff unchanged.
- DOM reporter after fixes:
  - healthy_beauty_240d: publish, 1 Recommended, 6 Considered, 1 Watching
  - healthy_beauty_low_inventory_240d: publish, 1 Recommended, 6 Considered, 1 Watching
  - supplement_replenishment_240d: abstain_soft, 0 Recommended, 6 Considered, 0 Watching
  - small_store_240d: abstain_soft, 0 Recommended, 6 Considered, 0 Watching
  - cold_start_45d: abstain_hard, 0 Recommended, 0 Considered, 0 Watching
  - promo_anomaly_240d: publish, 1 Recommended, 6 Considered, 1 Watching

Accepted limitations:
- supplement empty_bottle audience remains 0 because parser handles ml/oz but not ct/lb; supplement-specific parser/pathway is deferred.
- promo anomaly now tests a spike inside L56, but V2 anomaly auto-registration remains Phase 6.
- low_inventory does not yet surface inventory_blocked because inventory_metrics loading is blocked by a pre-existing engine bug at src/load.py:626.

Important follow-up:
- Fix src/load.py:626 groupby().apply().reset_index(name=...) TypeError.
- This likely affects real-world inventory CSVs, not only synthetic fixtures.
- Once fixed, re-run low_inventory to validate Fix 4 e2e inventory_blocked Considered card.

Fixes 8–11 summary:
agent_outputs/code-refactor-engineer-synthetic-fixes-8-11-summary.md

Ready to re-run PM/DS synthetic e2e review with the inventory loading blocker disclosed.

## Phase 6A — Ticket A1 Accepted: Watching cap reduction + load-bearing prioritization pin

Status: Accepted with caveats on 2026-05-05.

Ticket A1 reduced the V2 Watching surface to a hard cap of 4 and pinned load-bearing prioritization for `small_store_240d`.

Files changed:
- `src/storytelling_v2.py`
  - Added `MAX_WATCHING_RENDERED: int = 4`
  - Replaced the renderer slice with `items[:MAX_WATCHING_RENDERED]`
- `src/decide.py`
  - Confirmed builder-side cap remains `MAX_WATCHING_SIGNALS = 4`
  - Extended `_LOAD_BEARING_WATCH_METRICS` to include `aov`
  - Added load-bearing-first sort behavior in `build_watching`
  - Added an empty-HELD fallback: when no HELD Watching candidates exist and MOVED load-bearing observations are computable, MOVED load-bearing metrics may surface in Watching
- Tests added/updated:
  - New `tests/test_watching_load_bearing_priority.py`
  - Updated `tests/test_render_v2.py`
  - Narrowed older non-load-bearing tests in `tests/test_decide.py` and `tests/test_phase5_watching_signals.py`

Accepted behavior:
- Rendered Watching rows are capped at 4.
- `small_store_240d` now renders at least one contract-named load-bearing Watching metric when computable.
- `small_store_240d` changed from 0 Watching rows to 4 Watching rows while preserving:
  - `decision_state = abstain_soft`
  - 0 Recommended
  - 6 Considered
  - materiality footer present
- `supplement_replenishment_240d` also gained 4 Watching rows because the MOVED-load-bearing fallback applies there too.
- M0 legacy goldens remain byte-identical.
- Full suite baseline after A1: 693 passed, 14 skipped.

Caveats:
- The MOVED-load-bearing fallback is now an intentional Phase 6A behavior. Do not remove it as an old M7/M5.3 invariant violation.
- Internal load-bearing metrics still include `orders`, but Phase 6A A1 acceptance requires at least one of the contract-named four metrics: `returning_customer_share`, `net_sales`, `repeat_rate_within_window`, or `aov`.
- No schema, priors, Recommended Experiment, lifecycle, Shopify/Klaviyo, M10 cleanup, V2 default flip, inventory loader, AnomalousWindowCheck, or empty_bottle parser work was done.

Next ticket:
- Phase 6A Ticket A2 — `would_be_measured_by` enum + additive `PlayCard` field.

## Phase 6A — Ticket A2 Accepted: `would_be_measured_by` enum + additive PlayCard field

Status: Accepted with caveats.

Ticket A2 added the schema-only seam required for future Recommended Experiment cards.

Files changed:
- `src/engine_run.py`
  - Added `class WouldBeMeasuredBy(str, Enum)`
  - Added `would_be_measured_by: Optional[WouldBeMeasuredBy] = None` to `PlayCard`
  - Extended `_from_dict_play_card` to coerce the field via existing `_coerce_enum`
- `tests/test_engine_run_schema.py`
  - Added schema round-trip coverage
- `tests/test_would_be_measured_by_enum.py`
  - New enum/default/round-trip/free-text rejection tests

Enum values:
- `INCREMENTAL_ORDERS_IN_14D`
- `EMAIL_ATTRIBUTED_REVENUE_IN_7D`
- `REPEAT_PURCHASE_IN_30D`

Accepted behavior:
- `PlayCard.would_be_measured_by` defaults to `None`.
- Existing PlayCard construction remains valid without passing the field.
- Every enum value round-trips through EngineRun serialization.
- Missing key and explicit null both deserialize to `None`.
- Invalid free-text strings raise through enum coercion.
- No producer populates the field yet.
- No renderer reads the field yet.
- Merchant-facing briefing HTML is unchanged.
- M0 legacy goldens remain byte-identical.
- Full suite baseline after A2: 712 passed, 14 skipped.

Caveats:
- `WouldBeMeasuredBy` intentionally serializes as UPPER_SNAKE_CASE, unlike several older lowercase enums. Do not normalize casing unless A3 priors metadata and future outcome-history schema are updated in lockstep.
- A2 does not enforce that only Recommended Experiment cards can carry `would_be_measured_by`; this is deferred to A4/B-series.
- V2 receipts may now include `would_be_measured_by: null` on existing PlayCards. This is additive and expected.

Next ticket:
- Phase 6A Ticket A3 — priors metadata schema + loader.

## Phase 6A — Ticket A3 Accepted: priors metadata schema + loader

Status: Accepted with caveats.

Ticket A3 added config + loader support for Recommended Experiment eligibility metadata. This was a loader-only ticket with no runtime behavior change.

Files changed:
- `config/priors.yaml`
  - Converted `bestseller_amplify` and `discount_hygiene` to dict form with:
    - `metadata`
    - `priors`
  - Added complete metadata for both first-ship allowlisted experiment plays.
  - All other plays remain in legacy list form.
- `src/priors_loader.py`
  - Added `AudienceArchetype`
  - Added `PlayMetadata`
  - Added `PriorsMetadataError`
  - Added `get_play_metadata(play_id)`
  - Added support for both legacy list-form play blocks and new dict-form blocks
- `tests/test_priors_yaml.py`
  - Updated YAML schema tests to accept both legacy list form and dict form with `priors`
- `tests/test_priors_metadata.py`
  - New test file covering metadata schema, enum validation, invalid metadata, and legacy-form preservation

Accepted behavior:
- `discount_hygiene` and `bestseller_amplify` now have complete metadata:
  - `audience_floor`
  - `mechanism`
  - `vertical_applicability`
  - `would_be_measured_by`
  - `audience_archetype`
- `get_play_metadata(play_id)` returns typed metadata for metadata-bearing plays.
- Plays without metadata return `None`.
- Invalid metadata raises `PriorsMetadataError`, a `ValueError` subclass.
- `would_be_measured_by` reuses the A2 `WouldBeMeasuredBy` enum.
- `AudienceArchetype` intentionally serializes as lowercase strings.
- Existing prior lookup behavior is preserved for both YAML forms.
- Sizing still resolves priors for metadata-bearing plays.
- No decide-layer logic consumes metadata yet.
- No PlayCard producer populates `would_be_measured_by` yet.
- No renderer changes.
- No merchant-facing behavior changes.
- M0 legacy goldens remain byte-identical.
- Full suite baseline after A3: 733 passed, 14 skipped.

Caveats:
- Two YAML forms now intentionally coexist:
  - legacy list form for most plays
  - dict form with `metadata` + `priors` for `discount_hygiene` and `bestseller_amplify`
- `AudienceArchetype` casing is intentionally lowercase, unlike A2 `WouldBeMeasuredBy`, which is UPPER_SNAKE_CASE.
- `get_play_metadata` imports `WouldBeMeasuredBy` from `engine_run`; avoid adding a reverse `engine_run -> priors_loader` import later.
- `vertical_applicability` is validated as a list of accepted vertical strings, but final eligibility against current `VERTICAL_MODE` is deferred to A4.
- No metadata serializer was added; not needed for current consumers.

Next ticket:
- Phase 6A Ticket A4 — Recommended Experiment decide-layer eligibility filter behind `ENGINE_V2_SLATE`, default OFF.

# Phase 6A Ticket A4 Complete — Recommended Experiment Eligibility Filter

Ticket A4 is complete.

Completed:
- Added EngineRun.recommended_experiments as an additive list field.
- Added ENGINE_V2_SLATE flag, default false.
- Added Recommended Experiment selector in src/decide.py.
- Selector is behind ENGINE_V2_SLATE and returns [] when flag is off.
- Selector enforces:
  - allowlist: discount_hygiene, bestseller_amplify
  - targeting-only output
  - priors metadata requirements
  - per-play audience floor
  - vertical applicability
  - would_be_measured_by presence
  - inventory-block exclusion
  - <30% overlap vs Recommended Now
  - audience_archetype diversity
  - hard cap 2
  - ABSTAIN_SOFT / ABSTAIN_HARD => []
- Added tests/test_recommended_experiment_eligibility.py.

Verification:
- New tests: 22 passed.
- Red-first confirmed 22 failures before implementation.
- Schema + priors regression: 73 passed.
- A1/A2/A3 regressions: 73 passed.
- Fix 1–11 invariants: 114 passed, 3 skipped.
- Full suite: 755 passed, 14 skipped.
- Golden diff: 3 passed, no re-baseline.

Accepted caveat:
- src/main.py does not yet pass Phase 5 candidates into decide().
- With ENGINE_V2_SLATE=true end-to-end, recommended_experiments remains [] until candidates are plumbed.
- Next ticket should wire candidates into decide() before or as part of B1 rendering.

Summary:
agent_outputs/code-refactor-engineer-phase6a-ticket-a4-summary.md

# Phase 6A Ticket A4.5 Complete — Candidate Plumbing Into Decide

Ticket A4.5 is complete.

Completed:
- Wired live Phase 5 / M3 candidates from src/main.py into decide().
- Added _phase5_cands_for_decide as a stable variable so decide() safely receives either the candidate list or None.
- Updated _v2_decide(engine_run, cfg=cfg) to pass candidates=_phase5_cands_for_decide.
- Added tests/test_recommended_experiment_main_wiring.py.

Verification:
- New tests: 5 passed.
- Red-first confirmed the structural call-site test failed before wiring.
- A4 eligibility regression: 56 passed.
- Golden diff: 3 passed, no re-baseline.
- Cross-cutting Fix 1–11 + A1/A2/A3 regression: 191 passed, 3 skipped.
- Full suite: 760 passed, 14 skipped.

Behavior:
- With ENGINE_V2_SLATE=false, recommended_experiments remains [].
- With ENGINE_V2_SLATE=true and ENGINE_V2_DECIDE=true, decide() now receives live candidates and can populate recommended_experiments.
- Merchant-facing briefing.html still does not render Recommended Experiment; Ticket B1 owns renderer.

Accepted caveat:
- If candidate detection fails, decide() receives None and the slate safely returns [].
- Full-pipeline E2E slate rendering is deferred to B1/B6.

Summary:
agent_outputs/code-refactor-engineer-phase6a-ticket-a4-5-summary.md

Proceed to Phase 6A Ticket B1 only.

# Phase 6A Ticket B1 Complete — Recommended Experiment Renderer

Ticket B1 is complete.

Completed:
- Added Recommended Experiment section to V2 briefing renderer.
- Section renders between Recommended Now and Watching/Considered flow.
- Added render_recommended_experiment_section and experiment card renderer.
- Reuses audience block and Phase 5.1 opportunity-context renderer when opportunity_context is present.
- Added enum-backed would_be_measured_by display mapping:
  - INCREMENTAL_ORDERS_IN_14D -> We will measure incremental orders in 14 days.
  - EMAIL_ATTRIBUTED_REVENUE_IN_7D -> We will measure email-attributed revenue in 7 days.
  - REPEAT_PURCHASE_IN_30D -> We will measure repeat purchase in 30 days.
- Raw enum strings are not rendered.
- ABSTAIN_SOFT renders zero experiment cards.
- ABSTAIN_HARD does not render the experiment section.
- Legacy renderer unchanged.

Verification:
- New tests/test_render_recommended_experiment.py: 20 passed.
- Red-first confirmed 12 failures before renderer implementation.
- tests/test_render_v2.py: 25 passed.
- A4/A4.5 tests: 27 passed.
- targeting no-dollar-headline tests: 6 passed.
- Golden diff: 3 passed, no re-baseline.
- Full suite: 780 passed, 14 skipped.

Accepted caveat:
- Real Recommended Experiment cards do not yet have opportunity_context populated by the A4 selector.
- Renderer is ready to display it, but producer wiring is missing.
- Before B2, add B1.5 to populate opportunity_context on Recommended Experiment cards.

Summary:
agent_outputs/code-refactor-engineer-phase6a-ticket-b1-summary.md
# Phase 6A Ticket B1.5 Complete — Opportunity Context on Recommended Experiments

Ticket B1.5 is complete.

Completed:
- Populated opportunity_context on Recommended Experiment PlayCards produced by _select_recommended_experiments.
- Reused existing Phase 5.1 _build_opportunity_context helper.
- Passed aligned=aligned_for_template from main.py into decide().
- Extended decide() and _select_recommended_experiments with aligned kwarg.
- Real Recommended Experiment cards now render addressable opportunity context when defensible AOV is available.
- If AOV is missing, zero, NaN, or unavailable across L28/L56/L90, opportunity_context remains None and the renderer omits the block.

Source of AOV:
- Same canonical source as Phase 5.6 directional path:
  kpi_snapshot_with_deltas aligned dict.
- Resolution chain:
  L28 AOV, fallback to L56, fallback to L90.
- addressable_value = audience_size × AOV.
- No multipliers, no realization factor, no causal prior.

Trust constraints preserved:
- revenue_range.suppressed remains true.
- suppression reason remains experiment_no_calibrated_lift.
- Opportunity context uses “not projected lift” disclaimer.
- No fake revenue projection or lift forecast added.
- No p/q/CI/confidence/final_score/Aura/Beacon introduced.

Verification:
- New tests/test_recommended_experiment_opportunity_context.py: 15 passed.
- Red-first confirmed 13 failures before implementation.
- Eligibility / wiring / renderer regression: 78 passed.
- Schema / decide / priors / Phase 5 regression: 91 passed.
- Cross-cutting Fix 1–11 + A1/A2 invariants: 133 passed, 3 skipped.
- Golden diff: 3 passed, no re-baseline.
- Full suite: 795 passed, 14 skipped.

Sample Beauty behavior:
- discount_hygiene experiment card renders audience 962, L28 AOV about $69, addressable value about $66.1k, and the “This is not projected lift” disclaimer.

Accepted caveat:
- _build_opportunity_context is currently underscore-prefixed; future cleanup may promote it to a public helper.
- No copy is shown when opportunity_context is omitted due to missing AOV; acceptable for now.

Summary:
agent_outputs/code-refactor-engineer-phase6a-ticket-b1-5-summary.md

Proceed to Phase 6A Ticket B2 only.

# Phase 6A Ticket B2 Complete — Recommended Experiment Forbidden-Token Sweep

Ticket B2 is complete.

Completed:
- Added scoped forbidden-token sweep for section.recommended-experiment.
- Added tests/test_recommended_experiment_forbidden_tokens.py.
- Test-only ticket; no src changes.
- Sweep scans visible merchant-facing text, not HTML attributes/classes.
- “projected lift” is allowed only inside the exact Phase 5.1 disclaimer:
  “This is not projected lift; it shows the size of the audience if the play converts.”
- “measure” / “We will measure ...” remains allowed as future-looking measurement-plan copy.
- “measured,” “evidence,” and “evidence-backed” are forbidden in visible Recommended Experiment copy.

Forbidden tokens covered:
- calibrated
- uplift
- ATE
- ITT
- treatment effect
- expected lift
- forecast
- predicted
- p =
- q =
- p-value
- q-value
- confidence_score
- final_score
- p_internal
- ci_internal
- Aura
- Beacon Score
- beacon_score
- projected lift outside exact disclaimer

Verification:
- New tests/test_recommended_experiment_forbidden_tokens.py: 33 passed.
- B1 renderer tests: 20 passed.
- B1.5 opportunity-context tests: 15 passed.
- Phase 5 forbidden-token tests: passed.
- Golden diff: 3 passed, no re-baseline.
- Full suite: 828 passed, 14 skipped.

Summary:
agent_outputs/code-refactor-engineer-phase6a-ticket-b2-summary.md

Proceed to Phase 6A Ticket B3 only.

# Phase 6A Ticket B3 Complete — ABSTAIN_SOFT Experiment Routing

Ticket B3 is complete.

Completed:
- Extended ABSTAIN_SOFT contract to Recommended Experiment.
- Under ABSTAIN_SOFT, recommended_experiments remains [].
- Experiment-eligible candidates that would have qualified under PUBLISH are routed to Considered.
- Routed entries use ReasonCode.TARGETING_HELD_UNDER_ABSTAIN.
- Reused existing Fix 3 reason_text and would_fire_if templates.
- Added publish_shadow=True option to _select_recommended_experiments for ABSTAIN_SOFT “would-have-qualified” routing.
- Added duplicate prevention against pre-existing considered entries and regular Fix 3 held entries.

Verification:
- New tests/test_abstain_soft_no_experiments.py: 14 passed.
- Red-first confirmed 6 failures before implementation.
- Fix 3 regression: 11 passed.
- B-series regressions + goldens: 78 passed.
- Golden diff: 3 passed, no re-baseline.
- Full suite: 842 passed, 14 skipped.

Behavior:
- ENGINE_V2_SLATE=false: no observable change.
- ABSTAIN_SOFT + ENGINE_V2_SLATE=true:
  - zero Recommended Experiment cards.
  - eligible experiments appear in Considered with targeting_held_under_abstain.
- PUBLISH path unchanged.
- ABSTAIN_HARD path unchanged.

Accepted caveat:
- Recently-run-fatigue is still a no-op until recommended_history/outcome log is non-stub.
- Beauty Brand e2e slate regression is still deferred to B6.

Summary:
agent_outputs/code-refactor-engineer-phase6a-ticket-b3-summary.md

Proceed to Phase 6A Ticket B4 only.

# Phase 6A Ticket B4 Complete — Role-Uniqueness Invariant

Ticket B4 is complete.

Completed:
- Added _assert_role_uniqueness(engine_run) in src/decide.py.
- Enforced no duplicate play_id across:
  - recommendations
  - recommended_experiments
  - considered
- Watching is intentionally excluded because it is a metric track, not a play track.
- Assertion runs at the end of decide() on all return paths:
  - PUBLISH
  - ABSTAIN_SOFT
  - ABSTAIN_HARD
- Assertion error names duplicate play_id and role sections.

Verification:
- New tests/test_role_uniqueness_invariant.py: 13 passed.
- Red-first confirmed ImportError before helper existed.
- B3 regression: 14 passed.
- A4 eligibility regression: 22 passed.
- decide tests: 34 passed.
- Golden diff: 3 passed, no re-baseline.
- Full suite: 855 passed, 14 skipped.

Behavior:
- Legitimate EngineRun output unchanged.
- Future duplicate-role regressions now fail loudly in decide().
- PUBLISH behavior unchanged.
- ABSTAIN_SOFT B3 routing unchanged.
- ABSTAIN_HARD unchanged.

Summary:
agent_outputs/code-refactor-engineer-phase6a-ticket-b4-summary.md

Proceed to Phase 6A Ticket B5 only.

# Phase 6A Ticket B5 Complete — Recommended Experiment Cannibalization + Diversity Tests

Ticket B5 is complete.

Completed:
- Added tests/test_recommended_experiment_cannibalization.py.
- Added tests/test_recommended_experiment_diversity.py.
- Test-only ticket; no src changes.
- Pinned Recommended Experiment overlap rule:
  - overlap < 30% survives
  - overlap >= 30% excluded
  - checked against every Recommended Now card
- Pinned slate diversity rule:
  - no two Recommended Experiment cards share audience_archetype
  - deterministic winner by sort order: higher audience, then play_id
- Added property-style tests for cap, overlap, and archetype uniqueness.
- Confirmed default priors metadata keeps discount_hygiene and bestseller_amplify distinct:
  - discount_hygiene -> discount_buyer
  - bestseller_amplify -> hero_sku_buyer

Verification:
- New cannibalization tests: 15 passed.
- New diversity tests: 11 passed.
- Role-uniqueness tests: 13 passed.
- A4 eligibility tests: 22 passed.
- B3 abstain-soft tests: 14 passed.
- decide tests: 34 passed.
- Golden diff: 3 passed, no re-baseline.
- Full suite: 881 passed, 14 skipped.

Accepted caveat:
- Candidates excluded by overlap/diversity are not currently routed into Considered with a new typed overlap/diversity reason at the selector seam.
- Existing Phase 5.2 considered pipeline may still surface them with generic/prelim reasons.
- Typed demotion reasons can be a future tightening ticket if needed.

Summary:
agent_outputs/code-refactor-engineer-phase6a-ticket-b5-summary.md

Proceed to Phase 6A Ticket B6 only.

# Phase 6A Ticket B6 Complete — Beauty Brand Slate Regression

Ticket B6 is complete.

Completed:
- Added pinned e2e slate regression for healthy_beauty_240d.
- Added tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html.
- Added tests/test_slate_regression_beauty_brand.py.
- Pinned full V2 + slate output:
  - decision_state = publish
  - Recommended Now: first_to_second_purchase
  - Recommended Experiment: discount_hygiene, bestseller_amplify
  - Watching: aov
  - Considered: winback_21_45, subscription_nudge, routine_builder, empty_bottle
- Added byte-stable snapshot check separate from M0 legacy goldens.

Important integration bug fixed:
- In PUBLISH, promoted Recommended Experiment plays were still present in Considered from upstream Phase 5 routing.
- This violated B4 role-uniqueness and caused decide() to fail inside main.py.
- Fixed by filtering Considered after experiment selection to remove play_ids promoted to recommended_experiments.
- Scoped to PUBLISH branch only.
- ENGINE_V2_SLATE=false remains unchanged.

Verification:
- New slate regression tests: 19 passed.
- Recommended Experiment forbidden-token tests: 33 passed.
- DOM reporter tests: 17 passed.
- Role-uniqueness tests: 13 passed.
- Cannibalization tests: 15 passed.
- Diversity tests: 11 passed.
- Golden diff: 3 passed, no re-baseline.
- Full suite: 900 passed, 14 skipped.
- Pinned fixture sha256:
  3ace01703ae16b9d31ea685eac0421c29cb8450794c2b5c2732fcaad60125e7a

Accepted caveats:
- WINDOW_POLICY=auto is pinned in the B6 test env to avoid suite-order contamination from .env.
- Future intentional renderer/AOV changes will require explicit fixture refresh.
- Inventory loader fix remains deferred.
- Phase 6B items remain deferred.

Summary:
agent_outputs/code-refactor-engineer-phase6a-ticket-b6-summary.md

Phase 6A Campaign Slate implementation is ready for final PM/DS review.

# Phase 6A Final Review Complete

Phase 6A Campaign Slate is accepted with caveats.

Verdict:
- Ready for founder/manual testing.
- Not ready for external merchant beta.

Accepted baseline:
- Beauty Brand slate now renders as:
  - Recommended Now: first_to_second_purchase
  - Recommended Experiment: discount_hygiene, bestseller_amplify
  - Watching: aov
  - Considered: winback_21_45, routine_builder, subscription_nudge, empty_bottle
- Trust constraints hold end-to-end.
- Full suite: 900 passed, 14 skipped.
- M0 legacy goldens byte-identical.
- ENGINE_V2_SLATE=false remains the kill switch.

Manual/founder testing scenarios:
- healthy_beauty_240d
- small_store_240d
- cold_start_45d

Do not use promo_anomaly_240d for external merchant-style testing until AnomalousWindow auto-registration is wired.

Carry-forward caveats:
- Section order should be Watching before Considered.
- Experiment card mechanism exists in priors but is not rendered.
- Recently-run fatigue is still a no-op.
- would_be_measured_by outcomes are not fully measurable end-to-end yet.
- Considered reasons are still repetitive.
- empty_bottle audience=0 reason code should become audience_too_small.
- Beauty Brand is the only pinned slate regression.

Recommended next:
- Run founder testing before Phase 6B.
- Use founder reactions to prioritize section order, mechanism rendering, anomaly gate, outcome-log wiring, and Considered copy refresh.

Final review:
agent_outputs/phase6a-final-review.md

# Phase 6B Ticket C1 Complete — What We'd Send Rendering

Ticket C1 is complete.

Completed:
- Added get_mechanism(...) accessor in src/priors_loader.py.
- Added “What we'd send:” rendering in src/storytelling_v2.py.
- Mechanism is rendered on Recommended Now / Recommended Experiment cards when a mechanism exists.
- Mechanism is not rendered on Considered cards, Watching rows, or ABSTAIN_HARD.
- No PlayCard schema change.
- No decide / selector change.
- No legacy renderer change.
- Beauty slate fixture re-pinned.

Verification:
- New tests/test_what_we_send_render.py: 4 passed.
- Red-first confirmed 2 positive-render tests failed before implementation.
- B6 slate regression: 19 passed.
- B2 forbidden-token sweep: 33 passed.
- targeting no-dollar-headline: 6 passed.
- Golden diff: 3 passed, no re-baseline.
- Full suite: 904 passed, 14 skipped.

Updated Beauty fixture:
- tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html
- New sha256: 2985e8c01b218a7bb3620a4d31d6414c191494a01ad17ed01924d48f45662675

Accepted caveat:
- first_to_second_purchase does not yet have mechanism metadata, so the Beauty Recommended Now card does not show “What we'd send.”
- C1 completed the rendering path, but a C1.5 content-only ticket should add mechanism metadata for first_to_second_purchase before C2.

Summary:
agent_outputs/code-refactor-engineer-phase6b-ticket-c1-summary.md

# Phase 6B Ticket C1.5 Complete — Opportunity Context / Mechanism Metadata

Ticket C1.5 is complete.

Completed:
- Promoted `config/priors.yaml::plays.first_to_second_purchase` to the dict form (`metadata` + `priors`).
- Added merchant-readable `mechanism` string complying with the 15-35 word limit and strict forbidden-token rules (no projected lift, no causal claims, no concrete discount amounts).
- Added typed testing for the new metadata block in `tests/test_priors_metadata.py`.
- Added render-side test for the realistic Beauty Brand directional play end-to-end in `tests/test_what_we_send_render.py`.
- Re-pinned `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` with the new mechanism line included.

Verification:
- Full suite: 906 passed, 14 skipped, 0 failed.
- Forbidden-token sweep and targeting no-dollar-headline tests passed.
- Golden diff: 3 passed, no re-baseline. M0 goldens remain byte-identical.
- Beauty Brand slate now correctly renders "What we'd send:" on both Recommended Now and Recommended Experiment cards.

Accepted caveat:
- `audience_floor` for `first_to_second_purchase` was set to 500 (matching `bestseller_amplify`), but this is currently inert as the play is not on the Phase 6A Ticket A4 experiment allowlist.

Next ticket:
- Phase 6B Ticket C2 — Section reorder (Watching before Considered).

# Phase 6B Ticket C2 Complete — Section Reorder (Watching before Considered)

Ticket C2 is complete.

Completed:
- Swapped DOM render order in `src/storytelling_v2.py` so Watching appears before Considered.
- New Render Order: Recommended Now → Recommended Experiment → Watching → Considered → DQ-footer.
- Added `tests/test_storytelling_v2_layout.py` to explicitly pin the layout sequence.
- Re-pinned `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` to reflect the new DOM order.

Verification:
- Full suite: 908 passed, 14 skipped, 0 failed.
- Layout order explicitly tested and verified end-to-end.
- Golden diff: 3 passed. M0 legacy goldens remain byte-identical (legacy renderer untouched).
- Beauty Brand fixture new SHA256: 5fa9f697967566eab1a3d66a2d7edd6776b68cc166ca9677262f9e5f84e80b53.

Next ticket:
- Phase 6B Ticket C3 — Customer-facing play-title relabel.

# Phase 6B Ticket C3 Complete — Customer-facing play-title relabel

Ticket C3 is complete.

Completed:
- Updated `display_name` on all 14 legacy and planned plays in `src/play_registry.py` to use marketing-manager voice (e.g., "Lapsed-buyer reactivation (3–6 weeks since last order)").
- Updated V2 renderer (`src/storytelling_v2.py`) to use `_card_title_for(play_id)` which pulls the merchant-readable name for `<h3>` tags.
- Preserved internal `data-play-id` HTML attributes for log/tooling stability.
- Added structural tests in `tests/test_display_name_render.py`.
- Re-pinned `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` to reflect new string lengths.

Verification:
- Full suite: 914 passed, 14 skipped, 0 failed.
- Forbidden-token sweep verified clean against all new display names.
- Golden diff: 3 passed. M0 legacy goldens remain byte-identical.
- Beauty Brand fixture new SHA256: dcb45ceefe5f4dd44cc05e4e539df75402cf7fe80abf4a4757ce69b8f2e0f3bb.

Next ticket:
- Phase 6B Ticket C4 — Never-empty Watching copy fallback.

# Phase 6B Ticket C4 Complete — Never-empty Watching copy fallback

Ticket C4 is complete.

Completed:
- Added a fallback copy row (`watching-row--fallback`) in V2 renderer when `engine_run.watching` is empty but the store has mature data and directional observations.
- Handled the lack of a numeric history-days field by safely proxying maturity via `cold_start == False` and absence of `INSUFFICIENT_CLEAN_HISTORY`.
- Retained the existing empty-state paragraph for cold-start and ABSTAIN_HARD scenarios.
- Added 8 tests in `tests/test_watching_fallback.py` covering all gate conditions.

Verification:
- Full suite: 922 passed, 14 skipped, 0 failed.
- M0 legacy goldens remain perfectly byte-identical.
- Beauty Brand pinned fixture was untouched and its SHA256 remains `dcb45ceefe5f4dd44cc05e4e539df75402cf7fe80abf4a4757ce69b8f2e0f3bb`.

# Phase 6B Complete — Founder-Feedback-Driven, Low-Risk
- Mechanism copy ("What we'd send") added to Recommended cards.
- Briefing sections reordered: Recommended Now → Recommended Experiment → Watching → Considered.
- Play titles changed to merchant-readable marketing manager voice.
- Watching section fallback copy added to prevent completely empty sections for mature stores.
- The Campaign Slate is now fully ready for Founder Testing.

# Phase 6B Stop-Coding Line Complete — Engine JSON Contract Frozen

The "Stop-Coding Line" data-layer and schema fixes are complete. The `engine_run.json` schema is now locked as the canonical product handoff to the downstream AI Agent Swarm.

Completed:
- Fixed `config/priors.yaml`: rewrote `discount_hygiene` to a suppression posture and stripped trailing measurement instructions.
- Fixed `play_registry.py`: broke display name collisions and added load-time uniqueness assertions.
- Added raw typed floats/ints to `OpportunityContext` (`aov_used`, `monthly_revenue_estimate`) and State-of-Store `Observation` (`current`, `prior`, `delta_pct`).
- Mapped freeform Considered reasons to strict Enums and reserved `held_reason_detail` struct.
- Reserved `anomaly_flags`, `n_days_observed`, `n_days_expected` typed slots in the schema.

Verification:
- Full suite: 922 passed, 14 skipped, 0 failed.
- M0 goldens remain perfectly byte-identical.
- Beauty Brand fixture re-pinned to absorb the YAML rewrite.

Status:
The core engine is FROZEN. All narration, dollar formatting, percent framing, and visual polish will be handled by the downstream AI agents reading `engine_run.json`. Do not write further UI/HTML code in the engine.

# Sprint 1 Ticket B-4/S-1 Complete — Per-merchant Directory + `store_id` Resolution

First ticket of the Post-6B Restructured Implementation Plan (Sprint 1, Engineer A track, critical path). Single PR / single commit per the bundled-ticket-ID rule (`B-4/S-1`).

Completed:
- New `src/store_id.py` module: `resolve_store_id`, `store_data_dir`, `ensure_store_dir`, `migrate_legacy_recommended_history`. Resolution precedence: `STORE_ID` env > `--brand` CLI arg > basename of orders-CSV parent dir > literal `"unknown"`. Result is sanitized to `[a-z0-9_-]+` (lowercase) so a hostile or unexpected basename can never escape the per-store directory.
- `src/main.py::run()` resolves `store_id` once near the top; both hardcoded `data/recommended_history.json` paths (guardrails `history_path` ~L596 and outcome-log `_hist_path` ~L859) replaced with `store_dir / "recommended_history.json"`. `OUTCOME_LOG_PATH` env override still wins.
- `src/guardrails.py::gate_recently_run` and `apply_guardrails` accept a new `store_id` kwarg. Match key is the lineage tuple `(play_id, audience_definition_id, store_id)`; `audience_definition_id` falls back to `audience.id` until S-2/S-3 introduces an explicit field. Defensive policy preserved: each component enforced only when BOTH the candidate and the history record carry it. Existing 2-tuple history records keep matching — no in-the-wild data migration required.
- Idempotent copy-with-attribution migration of any pre-existing shared `data/recommended_history.json` into per-store path; writes a `.migration.json` sidecar (`source_path`, `copied_at`, `source_sha256`, `store_id`). Legacy file is **never deleted** (D-3 = full wipe only).
- Three new test files: `tests/test_store_id.py` (12 unit tests for resolver + dir + migration), `tests/test_per_merchant_isolation.py` (two-merchant subprocess smoke + 3 lineage-tuple gate tests), `tests/test_no_tenant_writes_outside_store_dir.py` (CI guard scanning post-run `data/` tree to catch any missed call site).
- `.gitignore`: added `/data/*/` so per-store dirs are never committed.

Verification:
- Full suite: 939 passed, 14 skipped, 0 failed.
- M0 Beauty pinned-fixture byte-identical.
- `engine_run.json` schema unchanged.
- `RECENTLY_RUN_FATIGUE_ENABLED` flag stays default-OFF — fatigue behavior unchanged on Beauty fixture.

Out of scope (deliberately deferred):
- `audience_definition_version` field on Audience class (D-1) — S-2/S-3 work.
- `compute_lineage_id` helper — S-2.
- Substrate `memory.db` — S-2 onwards.
- Fatigue flag flip — stays OFF until founder signal.

Status:
B-4/S-1 is the critical-path prerequisite for the Sprint 2 memory substrate (S-2 onward). Without per-merchant scoping, every downstream `lineage_id`, calibration partition, and substrate event would cross-contaminate between tenants. With this ticket landed, Sprint 1 unblocks the next two tickets on Engineer A's track: B-7 (vertical hard-refuse), then G-7 (cross-run determinism CI).

# Sprint 1 Ticket B-7 Complete — Hard-refuse Non-supported Verticals

Second ticket on Engineer A's track. Single commit `113c391` on `post-6b-restructured-roadmap` (not pushed).

Completed:
- New `src/vertical_guard.py`: entry-point guard short-circuits engine when `vertical_mode` is outside `{beauty, supplements, mixed}` → ABSTAIN_HARD with `data_quality_flag = VERTICAL_NOT_SUPPORTED` and typed merchant-facing refusal copy on `Abstain.reason`. Wired into top of `src/main.py::run()` BEFORE priors loader / feature builder / play registry.
- `DataQualityFlag.VERTICAL_NOT_SUPPORTED` added to existing enum (no schema change); added to `_HARD_DQ_FLAGS` in `decide.py`; humanizer mapping in `storytelling_v2`.
- Comment line above `_ALL_VERTICALS` in `src/play_registry.py`: `mixed` is a literal beauty+supplements blend, NOT an unknown-vertical fallback.
- `src/priors_loader.py`: new `ConfigError`; raises on any non-supported top-level vertical key in `priors.yaml` (structural keys allowlisted to `{schema_version, last_reviewed, plays}`).
- 21 new tests in `tests/test_vertical_hard_refuse.py` covering all 4 acceptance fixtures + frozen-contract `_ALL_VERTICALS` test + regression guards. Closed-set assertion in `tests/test_engine_run_schema.py` extended to 6 flags (intentional tripwire).

Verification:
- Full suite: 960 passed, 14 skipped, 0 failed.
- M0 Beauty pinned fixture byte-identical (19/19).
- `engine_run.json` schema unchanged.

Out of scope (deliberately deferred):
- Threading typed `Abstain.reason` directly into V2 abstain-hard memo renderer (today the renderer humanizes the flag; both strings are byte-identical, hygiene-only follow-up).

Status:
B-7 closes the vertical-scope hard-lock per Addendum 3. Engineer A's next ticket is G-7 (cross-run determinism CI).

# Sprint 1 Ticket G-7 Complete — Cross-run Byte-identical Determinism CI

Third and final ticket on Engineer A's Sprint 1 track. Single commit `6a758ca` on `post-6b-restructured-roadmap` (not pushed). Closes the Sprint 1 Engineer A track.

Completed:
- New `src/_determinism.py`: `seed_all(seed=DEFAULT_SEED=0)` helper that seeds stdlib `random` and (best-effort) `numpy.random`. Idempotent. numpy seed wrapped in `try/except ImportError` even though numpy is a hard dep, so the helper can never break engine startup.
- `src/main.py::run()` calls `seed_all()` at engine entry, immediately after `cfg = get_config()` and BEFORE the B-7 vertical guard / B-4 store-id resolution / feature build / decide. Lazy import `from ._determinism import seed_all as _g7_seed_all` mirrors the in-file pattern used for `vertical_guard`.
- New `tests/test_determinism_cross_run.py` (6 tests) mirrors the B6 pinned-slate harness pattern. Module-scoped fixture runs `healthy_beauty_240d` twice in two distinct tempdirs under `_DETERMINISM_ENV_OVERRIDES` (V2 + slate flag stack, `VERTICAL_MODE=beauty`, `WINDOW_POLICY=auto` — same env contract as the B6 byte-stable test).
- Comparator strips `NORMALIZED_FIELDS=("run_id",)` IN THE COMPARATOR, NOT THE ARTIFACT (per ticket). Sorted-keys JSON byte-compare surfaces hidden non-determinism in dict iteration / set ordering / FP reduction order.
- Self-checks: `test_run_id_is_actually_normalized_away` proves the identity test isn't vacuous; `test_comparator_detects_simulated_unseeded_randomness` is the synthetic mutation guard (no permanent edit to `src/decide.py`); `test_default_seed_is_pinned` pins `DEFAULT_SEED == 0`.

Verification:
- Full suite: 966 passed, 14 skipped, 0 failed (was 960p/14s/0f → +6 G-7 tests).
- M0 Beauty pinned fixture byte-identical (19/19).
- `engine_run.json` schema unchanged.
- Probe before wiring confirmed only `run_id` differs run-to-run on the Beauty fixture today; comparator scope is therefore minimal-and-defensible. Adding any field to `NORMALIZED_FIELDS` later requires founder review (schema is FROZEN).

Invariants / gotchas a future reader needs:
- The seed call MUST stay at engine entry, before any analytical work. If a future refactor moves it past `decide()`, S-3's lineage-id stability acceptance test becomes unverifiable.
- `NORMALIZED_FIELDS` is intentionally narrow — extending it without first asking "why does this field vary at all?" would mask exactly the regressions G-7 exists to catch.
- `seed_all`'s numpy `try/except ImportError` is intentional defense-in-depth, not dead code: the helper must NEVER break engine startup.
- The mutation guard is synthetic by design. The ticket's "introduce `random.random()` into `src/decide.py`" wording is satisfied by the byte-comparator self-test; permanently mutating production code to test determinism would be worse than the disease.

Out of scope (deliberately deferred):
- Cross-vertical determinism (supplements, mixed) — G-1 Sprint-4 work.
- Substrate event determinism — S-3 acceptance test (now unblocked).
- Snapshot-sha256 contract — S-4.

Status:
Sprint 1 Engineer A track complete. Three commits added on `post-6b-restructured-roadmap`: B-7 doc, G-7 implementation, G-7 doc. None pushed; awaiting founder merge after Sprint 1 Engineer B track lands.

# Sprint 1 Ticket B-1 Complete — AnomalousWindow Auto-registration + ABSTAIN Routing

First ticket of the Engineer B Sprint 1 track (post-6B-restructured plan). Commit `726fbd2` on branch `sprint1-engineer-b`.

Completed:
- New `detect_promo_spike` detector in `src/anomaly.py`: fires `POST_PROMO_WINDOW` when L56 revenue >= 2.0x prior-L56 with a credible baseline (`min_prior_orders=50`, `min_prior_days_covered=28`). Calibrated against fixtures: Beauty L56 ratio = 1.17 (silent), `promo_anomaly_240d` L56 ratio = 2.28 (fires). Threshold lives in `config/anomaly_thresholds.yaml::promo_spike` so it's tunable without code edits.
- `ANOMALY_GATE_ENABLED` default flipped from `False` to `True` in `src/utils.py::DEFAULTS`. Healthy fixtures produce zero flags so M0 Beauty pinned-fixture stays byte-identical. Legacy escape hatch is `ANOMALY_GATE_ENABLED=false` env override (existing test `test_flag_off_preserves_legacy_state` updated to use the explicit override).
- `gate_anomaly` extended in `src/guardrails.py` to route `POST_PROMO_WINDOW` alone to `ABSTAIN_SOFT` (load-bearing per-play hold; recommendations cleared and demoted into `considered` with `ReasonCode.ANOMALOUS_WINDOW`). Hard flags continue to route to `ABSTAIN_HARD`. The soft path uses a distinct `would_fire_if` text so reviewers can tell the two routes apart.
- Reserved typed `Observation` slots `anomaly_flags` / `n_days_observed` / `n_days_expected` (Phase 6B Stop-Coding-Line Task 4) are now populated when an anomaly Observation is emitted. `engine_run_adapter.build_engine_run_from_legacy` computes the day counts from `analysis_window_days` config and the order stream and threads them through to `state_of_store.build_observations` via new keyword-only args.
- Phase 5.6 directional rebuild in `src/main.py` skips when `apply_guardrails` has routed the run to `ABSTAIN_HARD` OR to `ABSTAIN_SOFT` with a populated `data_quality_flags` list (sticky-abstain). The narrow gate is **deliberate**: cold-start / zero-V1-actions `ABSTAIN_SOFT` (the legacy adapter default with `data_quality_flags=[]`) still permits the rebuild because that's exactly the case Phase 5.6 was designed for. `DecisionState` import added to `main.py` for this check.
- `decide()` in `src/decide.py` preserves the `ABSTAIN_SOFT` reason text from `apply_guardrails` so the load-bearing-anomaly diagnostic ("Load-bearing window anomaly detected: post_promo_window") is not overwritten by the generic "no measured/directional" copy.
- Two new test files: `tests/test_b1_anomaly_auto_register.py` (6 tests pinning the three contracts: default-on flag, typed-slot population, end-to-end `promo_anomaly_240d` flip) and `tests/test_b1_promo_spike_detector.py` (5 unit tests for the new detector). Existing `test_anomaly_abstain.py::test_post_promo_window_alone_does_NOT_trigger_abstain_hard` and `test_guardrails.py::TestAnomalyGate::test_post_promo_only_does_not_trigger_hard` updated to reflect the new ABSTAIN_SOFT routing for the soft flag.

Verification:
- Full suite: 950 passed, 14 skipped, 0 failed (baseline 939 + 11 new B-1 tests).
- M0 Beauty pinned-fixture byte-identical (no false positives on healthy data).
- `engine_run.json` schema unchanged (typed slots were already reserved in 6B Stop-Coding; B-1 just writes to them).
- `promo_anomaly_240d` end-to-end: `decision_state` flips PUBLISH → ABSTAIN_SOFT, `recommendations`/`recommended_experiments` both `[]`, `data_quality_flags=['post_promo_window']`, anomaly Observation carries `anomaly_flags=['post_promo_window']` + `n_days_observed=28` + `n_days_expected=28`.

Out of scope (deliberately deferred):
- `ANOMALOUS_WINDOW_DETECTED` as a new typed `DataQualityFlag` enum value — the ticket text mentioned this name but reusing the existing `POST_PROMO_WINDOW` value avoids a contract churn for zero behavioral gain.
- BFCM-overlap / refund-storm / test-order-anomaly recalibration — those detectors already fire correctly; B-1 only needed a spike detector to catch `promo_anomaly_240d`.
- Full `AnomalousWindowCheck` registration in `DataValidationEngine` — the M1 receipts-only path already runs the detectors in the engine_run adapter; explicitly registering the validation check would mutate `validation_report.json` (M0 golden contract risk) for no operational benefit.

Status:
With B-1 landed, the engine's data-quality layer now auto-protects against load-bearing window anomalies on a populated flag list. Next ticket on Engineer B's track: B-3 (hardcoded-fallback regression test).

# Sprint 1 Ticket B-3 Complete — Hardcoded-fallback Regression Test

Pure test, no behavior change. Commit `d219060` on branch `sprint1-engineer-b`.

Completed:
- New test file `tests/test_no_hardcoded_fallbacks_in_payload.py` (6 tests). Scans rendered `engine_run.json` from end-to-end runs of `healthy_beauty_240d` and `supplement_replenishment_240d`. For every PlayCard whose `play_id` is in `TARGETING_RECLASSIFY_PLAYS` (`subscription_nudge`, `routine_builder`, `empty_bottle`, `category_expansion`, `bestseller_amplify`, `vip_no_discount_nurture`, `replenishment_reminder`) plus a defensive `empty_bottle` membership guard, asserts that neither `measurement.effect_abs` / `observed_effect` nor `measurement.p_internal` matches any of the Phase 2 fallback constants `{0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.15, 0.20, 0.30, 0.40}` within 1e-9 tolerance.
- Scope is intentionally narrow per the audit (post-6b §B-3): a legitimately-computed `effect_abs == 0.05` on e.g. `first_to_second_purchase` (wired through the real M3 + multiwindow combiner path) is NOT flagged. Only structurally-at-risk plays trip the assertion.
- Three scanner self-tests pin the detection logic so a future test rewrite can't silently regress the assertion shape (positive-detect on at-risk play, ignore non-risk play, ignore missing measurement).
- Risk-set membership pin: defensive assertion that `{subscription_nudge, routine_builder, empty_bottle, category_expansion, bestseller_amplify}` remain in the scan set even if `TARGETING_RECLASSIFY_PLAYS` is later pruned. Forces explicit founder-level review if scope tightens.

Verification:
- Full suite: 956 passed, 14 skipped, 0 failed (baseline 950 + 6 new B-3 tests).
- M0 Beauty pinned-fixture byte-identical.
- Beauty fixture: zero violations. Supplements synthetic: zero violations.

Out of scope (deliberately deferred):
- Full G-1 supplements pinned slate fixture (Sprint 4) — this test exercises the existing `supplement_replenishment_240d` synthetic in the meantime; when G-1 lands, this test naturally extends to the new fixture without code edits.
- Behavior change to fix any future violation — per audit §B-3, this is a trust-contract test; a real violation means re-pin this test BEFORE shipping the fix.

Status:
B-3 closes the regression-detection seam for Phase 2 hardcoded fallbacks. Next ticket on Engineer B's track: B-5 (Berkson-class invariant test).

# Sprint 1 Ticket B-5 Complete — Berkson-class Invariant Test

Pure test, no behavior change. Commit `6342bc9` on branch `sprint1-engineer-b`.

Completed:
- New test file `tests/test_berkson_invariant.py` (5 tests). Pins TWO distinct invariants whose joint effect blocks the Berkson confound from re-entering the engine after the 554960d fix:
  * **Invariant A (structural cohort-definition rule):** A Berkson-shaped order DataFrame (constructed in-test: every customer has one whole-period order; complex cohort clusters in early half) drives `calculate_journey_stats_single_window` and asserts the function either bails to `None` (the degenerate-test guard from 554960d) or returns a non-pathological result (effect_abs < 0.95, p > 1e-30). Pre-554960d, the cross-period branch would emit a near-100% complex-arm rate against a structurally-zero simple-arm rate with a saturated p-value. Two test variants: pure-1-order shape (function bails to None via the n>=15 guard) and mixed-shape with complex orders clustered in early half (function must not collapse).
  * **Invariant B (M4b reclassification contract):** Scans the rendered Beauty pinned `engine_run.json` and asserts that every PlayCard surface where `subscription_nudge` or `routine_builder` appears carries `evidence_class=targeting` with `measurement=None`. The audit (post-6b §B-5) names these as the two plays carrying the same Berkson shape today (≥3-SKU survivor cohort and bundle-attach cohort respectively).
- Defensive membership pin: asserts both play_ids remain in `TARGETING_RECLASSIFY_PLAYS`. Per audit §B-5 / §G-4, the right resolution if measurement design later improves is to ship them at `evidence_class=measured` *with a real measurement*, NOT to drop them from the reclassify list while their emitter still emits the Phase 2 `effect_abs=0.05/0.08` constants. This pin forces explicit founder-level review of any drop.
- Self-test: hand-constructed engine_run dict with a violating `subscription_nudge` card trips the assertion (pins the failure mode so a future scanner refactor cannot silently weaken detection).

Verification:
- Full suite: 961 passed, 14 skipped, 0 failed (baseline 956 + 5 new B-5 tests).
- M0 Beauty pinned-fixture byte-identical.
- Considered list: subscription_nudge and routine_builder appear there as RejectedPlay (no evidence_class / measurement field), so the structural invariant scopes correctly to recommendations + recommended_experiments only.

Out of scope (deliberately deferred):
- G-4 redesign (reclassify subscription_nudge / routine_builder permanently as targeting at the emitter level, not just M4b flag-gated) — Sprint 4 ticket on Engineer B's track. B-5 pins the current contract so G-4's re-pin is defensible.
- Behavior fix to `calculate_journey_stats_single_window` itself — the 554960d fix is correct; B-5 is the regression test for that fix, not a redo.

Status:
B-5 closes the structural Berkson-block. Next ticket on Engineer B's track: B-6 (multi-window combiner universality test).

# Sprint 1 Ticket B-6 Complete — Multi-window Combiner Universality Test

Test-only behavior, with one tiny diagnostic seam in `src/stats.py` and two no-op call-site recorder calls in `src/action_engine.py`. Commit `a112d5e` on branch `sprint1-engineer-b`.

Completed:
- New thread-local trace facility in `src/stats.py`: `multiwindow_combiner_trace()` context manager + `record_combine_multiwindow_call(play_id, metric)` recorder. Outside an active trace context the recorder is a no-op (per-thread `active=False`), so production pays zero overhead. Trace state is per-thread via `threading.local`; the context manager activates, yields the underlying `(play_id, metric)` set, and clears on exit (try/finally, even on test exception).
- Two production call sites in `src/action_engine.py` now record into the trace:
  * `_combine_multiwindow_candidates_v2` at line ~1447 (the M4b reroute that replaces the legacy min-p merge)
  * `calculate_multiwindow_<play>_stats` at line ~4451 (the per-play helper)
  Both wrapped in try/except so the recorder cannot crash production if the trace facility is ever stripped/refactored.
- New test file `tests/test_multiwindow_combiner_universality.py` (5 tests):
  * 3 self-tests for the trace facility (no-op outside context, records inside, clears on exit).
  * 1 universality test: drives the engine **in-process** via `src.main.run` (so the thread-local trace is visible) under the V2 flag stack on the Beauty pinned slate. Asserts that every PlayCard with `evidence_class=measured` AND a non-null measurement block had its `play_id` recorded by the trace.
  * 1 documented-gap test: pins the known divergence that the Phase 5.6 directional builder (`measurement_builder.build_directional_play_card`) constructs its Measurement from L28 primary-window signal directly, NOT via the combiner. The docstring contains "L28" / "primary_window" — if a future change routes the directional path through the combiner OR reclassifies `first_to_second_purchase` to `measured`, this test surfaces for explicit decision.

Important caveat (founder-visible, pinned in commit message):
- On the current Beauty pinned slate, the universality assertion is **vacuously satisfied** because Beauty has zero measured-class cards (only `first_to_second_purchase` ships, at `directional`). The contract locks in the moment a measured-class card emerges — Sprint 4 G-3 (supplements priors expansion) + G-4 (subscription_nudge / routine_builder measurement redesign) are the likely first sources. Per the implementation plan ticket text: "If this fails on day 1, becomes a real B-6 fix, not a test-only ticket — re-scope with founder before merging the fix." The current scope ships a clean trace + a vacuous assertion + a documented-gap pin, which is the conservative posture.
- Originally I extended the assertion to cover `directional` cards too; the test then failed because `first_to_second_purchase`'s Measurement is built by `build_directional_play_card` from L28-only signal (Phase 5.6 design). Restricting the assertion strictly to `evidence_class=measured` is faithful to the audit's exact text (post-6b §B-6: "every measurement for evidence_class=measured was produced by combine_multiwindow_statistics"). The directional gap is preserved as a documented-gap test rather than dropped.

Verification:
- Full suite: 966 passed, 14 skipped, 0 failed (baseline 961 + 5 new B-6 tests).
- M0 Beauty pinned-fixture byte-identical.
- Production overhead: zero (recorder no-op outside test context, verified by `test_trace_is_no_op_outside_context_manager`).

Out of scope (deliberately deferred):
- Routing the Phase 5.6 directional builder through the combiner — that's a real behavior change with goldens implications, not a test ticket. Pinned as a documented-gap test for future work.
- Reclassifying `first_to_second_purchase` to `measured` — Sprint 4 / Phase 9 measurement-design work.
- Universality scan against synthetic supplements / cold-start fixtures — the audit explicitly scopes the test to "Beauty fixture"; expanding the matrix is a future ticket once G-1 supplements pinned fixture lands.

Status:
B-6 closes the universality-assertion seam. The trace facility is the load-bearing piece; the current vacuous pass is the correct posture per the founder-scope guidance in the implementation plan. Next ticket on Engineer B's track: G-2 (`empty_bottle` parser unit-coherence).

# Sprint 1 Ticket G-2 Complete — `empty_bottle` Parser Unit-coherence (vertical_applicable filter)

Commit `b63a9b6` on branch `sprint1-engineer-b`. Per the audit recommendation (post-6b §G-2), shipped option (b) — `vertical_applicable` filter + Beauty-only parser — and explicitly deferred the supplements unit-coherent parser to Sprint 4 G-3.

Completed:
- New `config/replenishment_sizes.yaml`: per-vertical regex configuration.
  * `beauty`: regex `30ml|1 oz|1oz|50ml|1.7 oz|1.7oz|100ml|3.4 oz|3.4oz` (verbatim pre-G-2). Documented as "M0 byte-identical — refresh the pin in the same commit if you change this regex."
  * `supplements`: `size_regex: null` (stub; Sprint 4 G-3 ships count / lb / mg / serving-per-container parser). The block is present so the dispatch surface advertises the gap explicitly.
  * `mixed`: Beauty regex (catches the Beauty half of the literal beauty+supplements blend; supplements half is a no-op until G-3).
- New `src/replenishment_parser.py`: thin pure-function loader with module-level cache. Public API: `load_replenishment_sizes()`, `get_size_regex(vertical)`, `get_case_insensitive(vertical)`. Returns `None` for any vertical without parser coverage so callers must clean-skip rather than fall back to a hard-coded regex. `_reset_cache_for_tests()` exposed for unit tests only — production code MUST NOT call it.
- `src/action_engine.py:1698` (`_targeted_skus_for_play` for `empty_bottle`) refactored to use the dispatched regex via the new module. Vertical resolved from `cfg.get('VERTICAL_MODE') or cfg.get('VERTICAL') or 'beauty'`. If the dispatcher returns `None`, the function returns `[]` (defensive — the upstream `vertical_applicable` filter should already have prevented this play from reaching SKU targeting on a non-applicable vertical, but the empty list is the safe fallback).
- `src/play_registry.py::PLAYS["empty_bottle"].vertical_applicable` restricted from `_ALL_VERTICALS` to `frozenset({"beauty", "mixed"})`. The decide.py:614 vertical-applicable filter (already in place from Phase 5.2) consumes this set and clean-skips `empty_bottle` on supplements.
- New test file `tests/test_g2_empty_bottle_vertical_dispatch.py` (9 tests):
  * 5 contract tests for the parser dispatcher (Beauty regex byte-identical, mixed=Beauty, supplements=None, unknown=None, case_insensitive default=True).
  * 2 contract tests for `vertical_applicable` (exact equality + membership).
  * 2 end-to-end tests: Beauty still surfaces empty_bottle in Considered; supplements scenario clean-skips it from every surface.

Important caveats (founder-visible):
- The G-2 ticket text mentioned "audience=0 silently for apparel/food/supplements/home" — apparel/food/home are already refused at engine entry by B-7, so only supplements was a real concern. G-2 closes the supplements case via `vertical_applicable` rather than via the parser itself; Sprint 4 G-3 (or a stand-alone supplements G-2 follow-up) is where the actual parser would land.
- Other Beauty-flavored size logic still exists at `src/segments.py:176-180`, `src/action_engine.py:3591-3636`. These are tied to a different code path (segment building, `_calculate_28d_revenue`) that is M10 deletion territory or vertical-bound by other means. Per the ticket's "pick whichever path is smaller" recommendation, only the line-1698 site (the audit's specific target) was refactored.

Verification:
- Full suite: 975 passed, 14 skipped, 0 failed (baseline 966 + 9 new G-2 tests).
- M0 Beauty pinned-fixture byte-identical (regex preserved verbatim; only supplements behavior changed).
- Beauty considered list still includes empty_bottle (parser coverage exists).
- Supplements considered list no longer includes empty_bottle (clean-skipped by vertical_applicable filter).

Out of scope (deliberately deferred):
- Supplements count / lb / mg / serving-per-container parser — Sprint 4 G-3.
- Refactoring the segments.py + action_engine.py:3591+ Beauty-size logic — M10 deletion territory; not load-bearing for the engine_run.json contract.
- Apparel / food / home vertical refusal — already covered by B-7 (Engineer A's ticket, landed earlier).

Status:
G-2 is the last ticket on the Sprint 1 Engineer B track. All five tickets (B-1, B-3, B-5, B-6, G-2) shipped. Engineer A's track (B-4/S-1 done; B-7 in flight; G-7 next) reconciles with this branch in a single founder-led merge after both tracks are green.

# Sprint 2 Ticket S-2 Complete — SQLite memory.db Substrate + lineage_id Helper

First ticket of Sprint 2 (Engineer A track). Single commit `82cefa4` on `post-6b-restructured-roadmap` (not pushed). Substrate stands alone — zero engine code changes. S-3 will wire writers in `src/decide.py` next.

Completed:
- New `src/memory/store.py`: `MemoryStore` + `open_memory(store_id, base=None)`. Per-store SQLite at `data/<store_id>/memory.db`. WAL journal mode + `busy_timeout=5000` + `synchronous=NORMAL`. `PRAGMA user_version` migrations (current = 1). Schema is `events(event_id PK, event_type, lineage_id, run_id, store_id, play_id, audience_definition_id, audience_definition_version, event_version, created_at, created_seq, payload_json)` plus three indexes (`lineage_id+seq`, `run_id`, `event_type+seq`) and a one-row `event_seq` counter table seeded by the v1 migration.
- New `src/memory/lineage.py`: `compute_lineage_id(store_id, play_id, audience_definition_id, audience_definition_version) -> sha1 hex`. ALL FOUR ARGS REQUIRED per founder D-1. Length-prefixed components joined by ASCII unit separator (`\x1f`); bumping `audience_definition_version` forks the lineage cleanly. sha1 (not sha256) because lineage_id is a partition key, not a security primitive.
- Insertion-order discipline: `created_seq` is a monotonically-increasing INTEGER pulled from a one-row counter table inside the same transaction as the INSERT. `query_events` orders by `created_seq` ASC, NOT by wall-clock — same-microsecond appends still order deterministically. `created_at` is microsecond-precision UTC ISO-8601 (built directly from `time.gmtime` to dodge the `datetime.now(timezone.utc)` deprecation churn between 3.10 and 3.12+).
- Payload canonicalisation: `json.dumps(payload, sort_keys=True, separators=(",", ":"))` — two semantically-equivalent dicts serialise byte-identically. Matters for export round-trip and any future content hash.
- Concurrency contract: WAL mode + `busy_timeout` survive 2 procs × 100 appenders (verified in `test_memory_concurrent.py`). Across processes, SQLite handles the locking; within a single process, each `MemoryStore` carries its own `threading.Lock` around `append_event`.
- Downgrade refusal: opening a db with `user_version` HIGHER than `CURRENT_USER_VERSION` raises `RuntimeError`. A future Beacon build that adds migration v2 reading a v1 db works fine; today's build refusing a future db prevents silent schema mismatch.
- New `tools/inspect_memory.py` CLI: `python -m tools.inspect_memory <store_id> [--lineage-id ID] [--type T] [--run-id R] [--limit N] [--base data] [--json]`. Default output is a fixed-column human-readable table; `--json` emits NDJSON.
- New `tools/export_store.py` CLI (founder D-4 — full per-store JSON export from Day 1). Bundle keys (sorted): `_format`, `_format_version`, `events`, `exported_at`, `recommended_history`, `snapshot_index`, `snapshots`, `store_id`, `user_version`. `import_store` refuses to overwrite a populated store (`memory.db` must be zero events) — D-3's "full wipe only" is the operator's responsibility, upstream of this CLI. Round-trip acceptance test: export → wipe → import → re-export with pinned `exported_at` is byte-identical at the events list, snapshots, recommended_history, and metadata layers.
- 35 new tests: 10 lineage (`test_lineage.py`), 13 store (`test_memory_store.py` — incl. 1000-event acceptance + migration idempotency + monotonic `created_seq`), 1 concurrent (`test_memory_concurrent.py` — 200 events from 2 distinct PIDs), 6 export round-trip (`test_export_roundtrip.py`).

Verification:
- Full suite: 1037 passed, 14 skipped, 0 failed (~7m). Was 975p/14s/0f at the ticket-start baseline; +35 of those are this ticket, the rest were intervening Sprint 1 reconciliation.
- M0 Beauty pinned fixture: 19/19 byte-identical.
- `engine_run.json` schema untouched.
- No engine code changes — substrate is isolated under `src/memory/` and tools are CLI-only.

Invariants / gotchas a future reader needs:
- `created_seq` is the canonical ordering field, NOT `created_at`. If a future refactor moves the seq increment outside the INSERT transaction, two concurrent appenders can race and the timeline guarantee breaks.
- The one-row `event_seq` table uses `UPDATE ... RETURNING next_seq - 1` (SQLite ≥ 3.35; we have 3.53). Replacing this with two separate statements re-introduces the race the table was added to fix.
- `compute_lineage_id` length-prefixes each string component. Removing the prefixing re-opens the `("ab", "c")` vs `("a", "bc")` collision the unit test `test_length_prefix_prevents_concatenation_collision` pins.
- `MemoryStore` is NOT thread-safe across instances on the same db file from a single process. Open one per thread, or serialise. Across processes, WAL handles it.
- Export `_format_version` is pinned at 1. Bumping it requires a writeback migration story — the test `test_import_rejects_bad_format_version` pins the refusal so a silent partial import can't happen.
- CLIs run as `python -m tools.<name>` from the repo root (we ship `tools/__init__.py` so they're importable; running them as a script outside the repo will not find `src.memory`).

Out of scope (deliberately deferred):
- Engine writes `recommendation_emitted` / `recommendation_considered` events — S-3 (next ticket; bundles B-2 reason-code fan-out + typed `evidence_snapshot`).
- Immutable snapshot discipline + `snapshot_sha256` field on event payload — S-4.
- Read-views (`v_lineage_timeline`, `v_calibration_state`, `v_open_recommendations`, `v_lineage_recent_emissions`) + `calibration_stub` rewire — S-5.
- Manual `tools/import_campaign_sent.py` import path + Swarm contract — S-6.
- `audience_definition` field actually appearing in `engine_run.json` — S-3 (the helper is ready; the engine doesn't pass anything to it yet).

Status:
S-2 is the substrate writing-path foundation. Sprint 2 next ticket is S-3 (engine writes events; bundles B-2). Schema-freeze milestone for the Swarm team is end of S-3. With S-2 landed, the substrate is ready to accept events; with G-7 already green on Engineer A's track from Sprint 1, S-3's lineage-id stability acceptance test is unblocked.

# Sprint 2 Ticket S-1.7 Complete — Vertical Resolution Hardening

Commit `46713bb` on branch `sprint2-engineer-b` (cut from `post-6b-restructured-roadmap` at `0afaec1`). Surfaced during Sprint 1 merge manual-validation: two correctness bugs in vertical resolution were silently undermining B-7's hard-refuse contract.

Completed:
- Bug 1: `src/utils.py:382-386` `get_vertical_mode()` silently mapped any unknown vertical (e.g. `apparel`, `food`, `home`, `wellness`) to `'mixed'`. Because `'mixed'` is in `SUPPORTED_VERTICALS`, B-7's vertical_guard never fired for these inputs — the engine ran on mixed priors instead of refusing. Defeated the B-7 hard-refuse contract.
  * Fix: pass through unknown verticals as-is (lowercased + stripped). Default when no env var is set remains `'mixed'` (the literal beauty+supplements blend, NOT a fallback for unknown inputs). B-7 vertical_guard at the engine entry boundary stays the single point of refusal.
- Bug 2: `src/utils.py:14-27` manual `.env` fallback (used when `python-dotenv` is missing) did `os.environ[k] = v` unconditionally, overriding exported env vars. Already documented as a known caveat in this memory.md (Synthetic Blocker Fix 6, line 911-914). Local-dev-only but compounded Bug 1 by making the laundering hard to detect during testing.
  * Fix: changed assignment to `os.environ.setdefault(...)` so exported env vars win.
- New test file `tests/test_s1_7_vertical_resolution.py` (12 tests):
  * 7 parametrized pass-through tests (`get_vertical_mode()` does NOT launder `apparel`, `food`, `food_bev`, `home`, `wellness`, `Apparel`, ` APPAREL ` to `'mixed'`).
  * 1 default-when-unset test (`'mixed'` is preserved as the unset default).
  * 1 supported-pass-through test (`beauty`, `supplements`, `mixed` unchanged).
  * 1 end-to-end test: `VERTICAL_MODE=apparel` via `os.environ` → `main.run` produces `engine_run.json` with `abstain.state=abstain_hard`, `data_quality_flags=["vertical_not_supported"]`, no slate, no briefing.
  * 1 `.env` setdefault test: pre-exported `VERTICAL_MODE=beauty` survives a `.env` containing `VERTICAL_MODE=apparel`; un-exported keys still load from `.env`.
  * 1 grep guard: scans every `tests/**/*.py` for `VERTICAL_MODE=apparel|food|food_bev|home|wellness`; allowlists only `test_vertical_hard_refuse.py` (the B-7 acceptance test, by design). Expected count outside the allowlist: zero.

Verification:
- 12/12 new S-1.7 tests green.
- B-7 vertical hard-refuse suite + M0 Beauty pinned fixture: 40/40 green (combined run).
- Full suite: 1047 passed, 14 skipped, 0 failed.
- M0 Beauty pinned-fixture byte-identical (Beauty is in supported set so behavior unchanged).
- `engine_run.json` schema unchanged.

Important caveats:
- The `.env` setdefault fix only affects local-dev runs without `python-dotenv` installed. The synthetic-fix-6 caveat (memory.md:911) is now closed.
- `get_vertical_mode()` returning `'apparel'` (or any other unsupported value) is harmless on its own — every downstream caller (`get_vertical()`, `get_window_weights()`, `subscription_threshold_for_product()`) already uses `VERTICAL_CONFIG.get(mode, VERTICAL_CONFIG['mixed'])` as a graceful default. The point of the fix is the B-7 boundary, where `cfg.get('VERTICAL_MODE')` flows directly into the guard's `is_supported()` check.

Out of scope (deliberately deferred):
- Per-merchant `store_profile.vertical` resolver — folds into S-2's per-merchant substrate work, NOT this ticket.
- M10 collapse of legacy `VERTICAL_MODE` env paths — Phase 9.

Status:
S-1.7 is the prelude to Sprint 2 substrate work. Independent of S-2; ships before S-3 lineage_id partitioning so no vertical can ever be silently laundered into `mixed` after this commit.
# Sprint 2 Ticket S-3 Prep Complete — Reason-code Fan-out + Typed Event Schemas (NON-merging)

Commit `0ab7be9` on branch `sprint2-engineer-b`. S-3 is the engine-writes-events ticket bundled with B-2 (per implementation plan §2). The substrate writer (`src/memory/store.py::append_event`) and lineage helper (`src/memory/lineage.py::compute_lineage_id`) live behind ticket S-2, owned by Engineer A in parallel and not yet merged. This commit lands all NON-substrate S-3 work on `sprint2-engineer-b` so the final wire-up post-S-2 is a small mechanical change.

Completed:
- **Reason-code fan-out (B-2 surface a)** in `src/decide.py`. New `_S3_FANOUT_REASON_MAP` with 6 short-code → typed `ReasonCode` entries:
  * `data_missing`, `data_quality` → `DATA_QUALITY_FLAG`
  * `cold_start`, `insufficient_history` → `COLD_START_INSUFFICIENT_DATA`
  * `materiality_below_floor`, `below_materiality_floor` → `MATERIALITY_BELOW_FLOOR`
  Plus the two already mapped in `_PRELIM_REASON_MAP` (`audience_too_small`, `inventory_blocked`), this gives the 5 typed codes the plan calls for. **Activation gated behind `ENGINE_S3_REASON_FANOUT` env flag (default OFF)** so M0 Beauty pinned fixture stays byte-identical on this Sprint 2 prelude branch — flag flips ON in the S-3 final commit alongside the documented goldens re-pin per plan §7 Risk #4. Additive only: only consulted for short codes NOT already in `_PRELIM_REASON_MAP`, so existing mappings (`audience_zero`, `audience_too_small`, `no_builder`, `builder_error`, `below_min_n`, `no_signal`, `no_data`, `missing_field`, `inventory_blocked`) are untouched.
- **Typed `EvidenceSnapshot`** (B-2 surface b) in new `src/memory_events.py`. Dataclass carrying internal Measurement diagnostics one snapshot per emitted event:
  * `evidence_class` (Literal `measured | directional | targeting`), `window_label`, `effect_abs`, `p_internal`, `sample_size`, `multiwindow_agreement`, `data_quality_flags`, `measurement_design_version`.
  * `targeting` plays explicitly accept `None` for `effect_abs` / `p_internal` (Phase 6A discipline).
- **Pre-registered `ExpectedOutcome`** (audit L-E) in `src/memory_events.py`. Dataclass committing the engine to its prediction at recommendation emission time so the calibration consumer has a non-post-hoc target:
  * `expected_direction`: Literal `increase | decrease | either`
  * `min_interesting_effect_size`: float (in the unit of the play's `would_be_measured_by` enum)
  * `expected_observation_window_days`: int (must match the enum's natural window, e.g. 30 for `REPEAT_PURCHASE_IN_30D`)
- **`RecommendationEmittedPayload` + `RecommendationConsideredPayload`** in `src/memory_events.py`. Full event payload schemas with all fields the plan calls out (`run_id`, `lineage_id`, `store_id`, `play_id`, `audience_definition_id`, `audience_definition_version` per founder D-1, `role`/`reason_code`, `evidence_snapshot`, `expected_outcome`, `snapshot_path`, `snapshot_sha256`). Pinned at `RECOMMENDATION_EVENT_VERSION = 1` for the Sprint 2 freeze.
- **S-3 wire-up site stub** in `src/main.py` right after `engine_run.json` is written (line 925). Multi-line TODO block carries the exact import + call shape that S-3 will replace once S-2 lands. Pure comment — no runtime behavior change.
- **Single-writer grep test stub** in new `tests/test_single_writer_per_event_type.py`. Allowlist of writer files per event type (`recommendation_emitted`, `recommendation_considered`, `campaign_sent`, `outcome_observed`, `calibration_updated`); fails CI if any file outside the allowlist contains the literal event-type string. Today vacuous-passing for emit/considered (substrate not yet wired); blocks unauthorized second writers as soon as S-3 starts emitting.
- New test files (36 tests total):
  * `tests/test_s3_reason_code_fanout.py` (18): 9 legacy-mappings regression, 6 fan-out-flag-ON, 3 fan-out-flag-OFF inert, default fallback, unknown short code, fan-out-codes-reachable across union.
  * `tests/test_s3_memory_event_schemas.py` (6): `RECOMMENDATION_EVENT_VERSION` pinned at 1, `to_dict` shape for all 4 dataclasses, targeting None acceptance, optional fields on Considered.
  * `tests/test_single_writer_per_event_type.py` (6): 5 parametrized event types + allowlist coverage assertion.

Important caveats (founder-visible):
- **`ENGINE_S3_REASON_FANOUT` flag is default-OFF intentionally.** The flag preserves M0 Beauty pinned fixture byte-identity on this prelude branch. With it ON, Beauty's `empty_bottle` Considered card flips reason code from `no_measured_signal` (current default fallback) to `data_quality_flag` (the typed S-3 code), which perturbs the briefing HTML at byte 12277. Per plan §7 Risk #4, "re-pin goldens in S-3 commit" — the flag flips ON in the same commit that re-pins the Beauty fixture, NOT before.
- **`src/memory_events.py` will move to `src/memory/events.py` after S-2 merges.** S-2 introduces the `src/memory/` package. The flat-file location was chosen so this commit can land before S-2 without creating an empty package directory or stub `__init__.py` files. The TODO block in `src/main.py:927` calls this out explicitly.
- **What remains for S-3 final wiring** (post-S-2 rebase):
  1. Replace the TODO block in `src/main.py:927` with `from .memory.store import open_memory, append_event`, `from .memory.lineage import compute_lineage_id`, and `from .memory.events import RecommendationEmittedPayload, RecommendationConsideredPayload, EvidenceSnapshot, ExpectedOutcome, RECOMMENDATION_EVENT_VERSION`.
  2. For each `PlayCard` in `recommendations` and `recommended_experiments`, build the typed payload and call `append_event(memory, "recommendation_emitted", payload.to_dict())`. For each `RejectedPlay` in `considered`, call `append_event(... "recommendation_considered" ...)`.
  3. Lineage tuple is `(store_id, play_id, audience_definition_id, audience_definition_version)` per founder decision D-1.
  4. Move `src/memory_events.py` → `src/memory/events.py`; update the `_ALLOWED_WRITERS` allowlist in `tests/test_single_writer_per_event_type.py`.
  5. Set `ENGINE_S3_REASON_FANOUT=1` as the engine default; re-pin Beauty goldens in the same commit per plan §7 Risk #4. Remove the `_s3_fanout_enabled()` gating helper.

Verification:
- 36/36 new S-3 prep tests green.
- M0 Beauty pinned fixture byte-identical (`tests/test_slate_regression_beauty_brand.py` 19/19).
- B-7 vertical hard-refuse: 21/21.
- Full suite: 1047 passed, 14 skipped, 0 failed (~5 min).
- `engine_run.json` schema unchanged (no event payload writes happen on this branch yet).
- No banned ML scaffolding (D-6); no schema-perturbing change.

Out of scope (deliberately not touched):
- Calling `append_event` or `compute_lineage_id` — those modules are S-2 and don't exist yet.
- Engine-side substrate I/O wiring — final S-3 work, post-S-2 rebase.
- Re-pinning Beauty goldens with the typed reason codes — final S-3 work, paired with `ENGINE_S3_REASON_FANOUT=1`.
- Migrating to `src/memory/events.py` — final S-3 work, after `src/memory/` package exists.
- Writing `recommendation_emitted` / `recommendation_considered` events through any path other than the future single-writer in `decide.py` / `main.py` — single-writer discipline pinned by the new grep test.

Status:
S-3 prep complete. Engineer A's S-2 substrate is the gating dependency for S-3 final wiring. Once S-2 merges to `post-6b-restructured-roadmap`, this branch rebases and the wire-up is mechanical (~5 import lines + 2 loops + 1 file move + 1 flag flip + 1 goldens re-pin).
