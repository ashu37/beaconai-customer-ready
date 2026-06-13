# DS Architect M0–M9 Review

## Verdict
**Ready with caveats.** The V2 stack is technically safe for founder manual testing behind the full flag set. Architectural invariants hold; merchant-facing output cannot leak fabricated stats; the system fails closed (ABSTAIN_SOFT) under the current transition state rather than fabricating recommendations. The caveats are real and the founder must understand them before drawing conclusions from the test.

## One-line summary
M0–M9 ship a behind-flag, additive-only V2 chain (adapter → guardrails → sizing → decide → V2 render → outcome log) that is architecturally sound, statistically honest, and safe to drive end-to-end — but every real fixture currently produces ABSTAIN_SOFT because the spine is still legacy-adapter-driven and that path cannot stamp `evidence_class = measured`.

## What I verified
- MEMORY.md reconciled invariants and the M0–M9 delta entries against `agent_outputs/implementation-manager-overhaul-plan-final.md`.
- All ten milestone summaries (M0, M1, M2, M3, M4a, M4b, M5, M6, M7, M8, M9).
- Three M8 V2 sample HTML outputs and the legacy comparator: confirmed structurally that no `p =`, `q =`, `CI`, `confidence_score`, `final_score`, `p_internal`, `ci_internal`, or numeric confidence percentage strings appear in the V2 renderings.
- Load-bearing source files for the safety claims: `src/decide.py`, `src/engine_run_adapter.py`, `src/evidence.py`, `src/guardrails.py`, `src/sizing.py`, `src/outcome_log.py`, `src/calibration_stub.py`, `src/anomaly.py`, `src/storytelling_v2.py`, and the V2 wiring blocks in `src/main.py` (lines ~547–752, ~877–893).

## Architecture integrity
**Detect → Size → Recommend is NOT the actual V2 spine. The legacy adapter is.** This is M7's documented choice ("M3 detect → M4 evidence integration deferred to M8/M9") and is acceptable for Phase 1, but the founder must know what they are testing.

The actual V2 chain in `src/main.py` is:
1. Legacy `select_actions(...)` runs (entangled monolith).
2. `build_engine_run_from_legacy(actions_bundle, ...)` lifts the legacy actions into typed `EngineRun` (`src/engine_run_adapter.py`).
3. `apply_guardrails(engine_run, ...)` (M5) — flag-gated.
4. M6 V2 sizing block — flag-gated; replaces `revenue_range` per card.
5. `decide(engine_run, cfg=cfg)` (M7) — flag-gated; ranks, caps, abstains, builds Watching, populates Considered.
6. M8 V2 renderer — flag-gated by `ENGINE_V2_OUTPUT` AND `engine_run is not None`.
7. M9 debug.html + outcome log — debug.html unconditional, log default-on, log gitignored, log never-raises.

`src/detect.py` shadow candidates and `src/audience_builders.py` exist but are read only by `ENGINE_V2_SHADOW`'s receipts dump and by the M5 cannibalization gate's overlap re-computation. They do not feed `decide()`. This is fine for safety; it is not "Detect → Size → Recommend." Document it for the founder.

## Evidence classification & statistical honesty
**The contract holds, structurally.** `src/engine_run_adapter.py:112` short-circuits `_build_measurement_from_legacy` to `None` whenever `evidence_class == "targeting"`. The M4b semantic switch (`TARGETING_RECLASSIFY_PLAYS`) deterministically reclassifies the seven targeting-ish plays. The `EvidenceClassificationError` raise on (NaN-p, evidence_class=measured) is a real fail-fast, not a downgrade.

`consistency_across_windows` is a **pre-combination sign-agreement count** with `|t| > 1`, computed in `src/evidence.py` and stamped only by the V2 combiner `_combine_multiwindow_candidates_v2`. It is NOT post-combiner p-vote. Pinned by `tests/test_consistency_across_windows.py` (20 tests).

Min-p multi-window cherry-picking is gone on the V2 path. `_combine_multiwindow_candidates_v2` calls `combine_multiwindow_statistics` (Fisher + inverse-variance) and stamps `source_window = contributing_windows[0]` deterministically (M4b summary, "Proof that min-p merge is no longer used"), pinned by `tests/test_multiwindow_combiner.py::test_legacy_min_p_path_not_used_on_v2_combiner_output`.

Briefing.html under `ENGINE_V2_OUTPUT=true` contains zero forbidden tokens. I confirmed this on all three sample files in `agent_outputs/m8_parity_review/`. Synthetic sweep is `tests/test_targeting_no_dollar_headline.py::test_briefing_html_has_no_pvalue_qvalue_ci_confidence_score_or_finalscore`.

**One sharp edge to flag.** `src/engine_run_adapter.py:70-76` `_coerce_evidence` defaults to `EvidenceClass.TARGETING` whenever the legacy emitter does not explicitly stamp `evidence_class`. With M4b flags off, the legacy emitter doesn't stamp. The result: every legacy-PRIMARY action gets surfaced as `targeting` in EngineRun, even if it would have been measurable. This is the M7-documented "transition state" and is the root cause of the universal ABSTAIN_SOFT outcome on real fixtures. It is a conservative bias (false negative on PUBLISH, never a false positive), so it is safe — but it does mean the founder cannot test the PUBLISH path with current CSVs without flipping the M4b flags AND running real measured plays through the legacy emitter, which itself is the path the overhaul is trying to retire.

## Multi-window combiner & confidence collapse
Combiner is correct (above). Confidence collapse is real on the V2 path: `_calculate_business_confidence` short-circuits to `_calculate_statistical_confidence(p)` when `EVIDENCE_CLASS_ENFORCED=true` (M4b T4b.3). The 0.95/0.80/0.60 stepped buckets are gone behind the flag, present in legacy code (still untouched until M10). `tests/test_seasonality_decoupled.py` pins that confidence is invariant to `seasonal_multiplier` under the V2 flag.

**Caveat on whether measured plays "actually surface n ≥ 2 sign-agreeing windows."** They cannot surface today on real fixtures because the legacy emitter is producing the input to the adapter, and the adapter routes everything through targeting. The combiner code path is unit-tested but is not exercised end-to-end on a real fixture in the M8 parity samples (M8 summary: "No PUBLISH-state V2 sample on a real fixture"). The combiner is verified by tests but unverified by real-data PUBLISH runs.

## Guardrails & conservative sizing
**Wired into `decide()` via `apply_guardrails` upstream.** `src/main.py` calls `apply_guardrails` BEFORE `decide()`, so by the time `decide()` ranks, the guardrail-rejected plays are already in `engine_run.considered` with reason codes. Each gate is independently flag-gated (default-OFF in production-equivalent runs but enabled by founder env in manual testing).

Specifically wired:
- **Inventory** (`gate_inventory`): `INVENTORY_GATE_ENABLED`. No-inventory branch is a no-op, NOT a block (correct).
- **Anomaly hard abstain** (`gate_anomaly`): `ANOMALY_GATE_ENABLED`. HARD flag → `ABSTAIN_HARD` + cleared recommendations. Plus `decide()`'s `_decide_abstain_state` enforces the same invariant defensively (`src/decide.py:517`) even when the M5 flag is off — belt-and-suspenders.
- **Scale-aware materiality**: `MATERIALITY_FLOOR_SCALE_AWARE`. Three ARR tiers per spec.
- **Audience overlap / cannibalization**: `CANNIBALIZATION_GATE_ENABLED`. Overlap >50% demotes lower-priority. Backed by `compute_audience_overlap` re-running pure audience builders on customer-id sets, not re-measuring effects.
- **Portfolio cap**: paired with cannibalization flag. Sum of p50 ≤ 25% monthly revenue. Backoff: keep top-1 if cap demotes everything.
- **Recently-run fatigue**: `RECENTLY_RUN_FATIGUE_ENABLED`. Reads `data/recommended_history.json`.

Sizing (`src/sizing.py`) implements `audience × p_action × incremental_orders × AOV` with no stacked multipliers. Cold-start suppression and targeting-non-causal-prior suppression both fire. **Targeting suppression is intentional** and produces empty `revenue_range` for every current play because there are zero `causal` priors in `config/priors.yaml` today (M6 summary, "Targeting suppression rationale"). The `drivers[]` provenance carries `suppression_reason` so the M9 calibration layer can audit.

## Abstain logic
**Correct.** `src/decide.py:_decide_abstain_state` (line 491) returns ABSTAIN_HARD on any HARD `data_quality_flag` OR a pre-existing ABSTAIN_HARD; ABSTAIN_SOFT when zero measured/directional remain; PUBLISH otherwise. Critically, the recommendation list under ABSTAIN_SOFT is NOT cleared — targeting plays are kept and the M8 renderer caps them at 2 with the explicit "no measured opportunities cleared" callout and per-card no-dollar-headline rule. Targeting-only briefings cannot publish as PUBLISH (DS Architect QA Change 2). Pinned by `test_targeting_only_yields_abstain_soft` and `test_post_promo_window_does_not_force_abstain_hard`.

## ML-readiness & outcome logging
**Schemas are correct and conservative.** `src/outcome_log.py` writes `recommended_history.json` per run with `schema_version="1.0.0"`. `src/calibration_stub.py:load_realization_factors` returns the locked three-key dict `{prior_overrides, evidence_thresholds, materiality_overrides}` and never reads history (DS Architect QA Required Change 5). Every call returns a fresh dict.

`measurement.p_internal` and `ci_internal` survive to `engine_run.json`, the outcome log, and `receipts/debug.html`. They are absent from the V2 briefing (verified by both grep on samples and by `tests/test_internal_stats_not_rendered.py`).

`debug.html` carries an `INTERNAL_BANNER` and is not linked from `briefing.html`. It is produced unconditionally on every run that builds an EngineRun.

## Privacy / safety
- **No raw customer IDs in outcome log.** Only `audience.id` (a string label) and `audience.size` are persisted. `tests/test_outcome_log.py::test_build_record_does_not_persist_raw_customer_ids` greps for `customer_id`, `Customer Email`, `Customer ID`, `email` and asserts none appear.
- **Network egress: zero.** Local file I/O only.
- **`data/recommended_history.json` is gitignored.** Plus `.corrupt-*.bak` siblings.
- **Writer never raises.** Errors surface via status dict; the briefing run cannot be killed by an outcome-log bug.
- **`OUTCOME_LOG_ENABLED=true` default is acceptable.** All four conditions hold (safe, local, deterministic, gitignored). Founder testing on a non-shared laptop does not create a privacy issue.
- **`debug.html` is unconditional.** Acceptable: it is not linked from the merchant page, lives only in `receipts/`, and the founder is the only consumer during manual testing. If this artifact ever ships to a merchant, it must be gated.

## True blockers before manual testing
None.

The system passes every load-bearing safety invariant I checked. There is no path through the V2 flag stack that fabricates stats, recommends during anomalies, double-counts audiences, or renders misleading dollar amounts. The current behavior is conservative-to-the-point-of-silent (universal ABSTAIN_SOFT on real fixtures), which is the correct failure mode for a Phase 1 system.

## Minimum fixes (small, pre-test)
None required. Two optional, low-risk improvements that would make the manual test more informative without architectural change:

1. **Add a one-line README** to `agent_outputs/m8_parity_review/` (or to the founder's test instructions) stating the expected outcome: "All three real fixtures will render ABSTAIN_SOFT under the full V2 stack. This is a documented transition state, not a bug. PUBLISH-state real-fixture rendering returns when measured plays are wired into the V2 detect path." Without this, the founder will test, see "no measured opportunities cleared" three times in a row, and reasonably conclude the system is broken.
2. **Document the recommended manual-test flag stack** explicitly. The natural test is the full stack on:
   `ENGINE_V2_OUTPUT=true ENGINE_V2_DECIDE=true ENGINE_V2_SIZING=true STATS_NAN_FOR_HARDCODED=true EVIDENCE_CLASS_ENFORCED=true MATERIALITY_FLOOR_SCALE_AWARE=true CANNIBALIZATION_GATE_ENABLED=true ANOMALY_GATE_ENABLED=true`
   plus a contrast run with `ENGINE_V2_DECIDE=true MATERIALITY_FLOOR_SCALE_AWARE=true CANNIBALIZATION_GATE_ENABLED=true` and M4b flags OFF (the M7 summary's "small_sm under M4b flag-OFF + M5/M7 ON" case) so the founder sees the gate-emitter behavior on a non-empty input.

## Acceptable caveats the founder should know
1. **All real fixtures render ABSTAIN_SOFT under the full V2 stack.** Documented transition state. Data-driven and conservative. Cause: legacy adapter defaults `evidence_class = TARGETING` when the legacy emitter does not stamp it; the M4b reclassification only labels things targeting (it does not promote anything to measured). The remedy is M3-detect-driven evidence stamping, deferred per M7.
2. **No real-fixture PUBLISH-state V2 sample exists.** PUBLISH path is exercised by synthetic tests (`tests/test_render_v2.py`, `tests/test_decide.py`) but not by real data in M8 parity outputs.
3. **No real-fixture ABSTAIN_HARD V2 sample exists.** Same caveat. Synthetic ABSTAIN_HARD is fully tested.
4. **`legacy_actions_from_engine_run` exists but is not wired into `main.py`.** Legacy `actions_log.json` is still produced from the legacy `actions_bundle`, not from the V2 `EngineRun`. Non-issue for manual testing because the V2 briefing is the deliverable; the legacy log is parallel exhaust.
5. **`measurement.consistency_across_windows` is computed but not used as a ranking tiebreaker.** Acceptable; ranking is class-first then p50.
6. **Watching threshold-to-act table is hardcoded to 3 metrics** (`aov`, `repeat_rate_within_window`, `orders`).
7. **Calibration stub returns empty overrides on every call.** This is the spec; the function is a contract anchor, not a feature.
8. **`data/recommended_history.json` accumulates forever**, no rotation. Manual cleanup is fine.
9. **POST_PROMO_WINDOW is a soft warning, not ABSTAIN_HARD.** Per M5 contract.
10. **All current `config/priors.yaml` priors are `expert` or `observational`, not `causal`.** Structural reason every targeting play is `revenue_range.suppressed=True` under M6.

## Post-manual-test cleanup (do NOT block on these)
- M3 candidate detection wired into `decide()` so the V2 spine is genuinely Detect → Size → Recommend, not legacy-adapter-Compose. Requires extending the M3 `Candidate` schema with a `Measurement` slot. Defer until after the manual test informs the design.
- `legacy_actions_from_engine_run` wiring in `main.py`. Prereq for the M10 default flip.
- M10 deletion list (legacy stacked-multiplier paths, `_calculate_calibrated_confidence`, `_run_cohort_statistical_test`, `bias_corrections` dict, 4-tier matrix in storytelling, dead flags).
- Add a real-fixture PUBLISH golden once measured plays surface in V2.
- Add a real-fixture ABSTAIN_HARD golden once a synthesized BFCM-window CSV is added to fixtures.
- Outcome-log schema migration helper (only when v1.0.0 → v2 is needed).
- Watching threshold table extension as `state_of_store` adds metrics.
- Extract V2 inline CSS to `assets/briefing_v2.css` (M10 cosmetic).
- Optional debug.html gating flag if the artifact ever ships to a merchant context.

## Open architectural questions for after manual testing
1. **What does it take to surface a real measured play under V2?** The current legacy emitter computes p/effect/CI on plays the M4b list does not reclassify (e.g., `winback_21_45`, `frequency_accelerator`, `aov_momentum`, `discount_hygiene`). Why does none of them survive to a measured-class card on the three pinned fixtures? Is it data sparsity, audience size below threshold, the adapter dropping the stamp, or a flag-stack interaction? Highest-value question the manual test can answer.
2. **Is the founder going to trust a system whose first three real outputs are "no measured opportunities cleared"?** Product question, not architecture.
3. **What is the right path for PUBLISH on small_sm specifically?** It has 3 legacy PRIMARY actions today. Under full V2 they all become targeting and get suppressed. Structural answer: wire M3 detect → M4 measurement evidence on at least `winback_21_45` and `frequency_accelerator`.
4. **Should `realization_factor` be defined formally in `docs/play_registry.md`** before any Phase 2 calibration work begins?
5. **G3 partial-window contamination** (28-day window containing a BFCM week without being centered on it) remains a known limitation. Not a blocker.
