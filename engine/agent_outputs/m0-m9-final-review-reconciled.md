# BeaconAI V2 M0–M9 Final Review

## Executive Verdict

**Ready for manual testing with caveats.**

Both reviewing agents (DS Architect and Product PM) independently land on the same verdict: *Ready with caveats*. The V2 stack is technically safe and structurally faithful to the frozen contract, but on every real pinned fixture today it produces ABSTAIN_SOFT with empty Recommended / Considered / Watching. The founder can validate the chrome and the safety invariants; the founder cannot validate the "memo with measured plays" experience on real data without seeding a synthetic case.

## One-Sentence Summary

The V2 system is honest, safe, and structurally a decision memo — but its first three real outputs will be near-empty ABSTAIN_SOFT pages, and the founder must understand that this is a known transition state, not a bug, before testing.

## What Both Agents Agree On

- **Verdict: Ready with caveats.** Independently reached.
- **Statistical honesty holds.** No `p =`, `q =`, `CI`, `confidence_score`, `final_score`, `p_internal`, or `ci_internal` strings appear in any V2 briefing.html. Forbidden-string sweep is mechanically pinned by `tests/test_targeting_no_dollar_headline.py`.
- **All three real fixtures render ABSTAIN_SOFT under the full V2 flag stack.** This is the single biggest fact about the current state of the system. Both agents confirmed it; both treated it as the load-bearing caveat.
- **No real-fixture PUBLISH or ABSTAIN_HARD V2 sample exists.** Those layouts are exercised only by synthetic tests (24 tests in `test_render_v2.py`).
- **The legacy adapter is the actual V2 spine, not Detect → Size → Recommend.** M3 candidate detection feeds receipts and the cannibalization gate but does not feed `decide()`. This is M7's documented choice; defer the spine rewire to post-manual-test.
- **Architectural invariants are pinned.** Targeting ⇒ measurement is null. Measured ⇒ p_internal non-null + consistency ≥ 2 (pre-combination sign agreement, not p-vote). Targeting-only ⇒ ABSTAIN_SOFT, never PUBLISH. Sum p50 ≤ 25% monthly revenue. No `data_quality_flags` on any HARD path leaks into PUBLISH.
- **debug.html ↔ briefing.html separation is clean.** debug.html lives in `receipts/`, carries an "INTERNAL DIAGNOSTICS — NOT FOR MERCHANT DISTRIBUTION" banner, is not linked from the merchant page, and is gated by tests. Sole deployment-hygiene caveat: zipping `<out>/` and emailing it would ship debug.html.
- **Calibration stub is honest.** `load_realization_factors` returns the locked `{prior_overrides, evidence_thresholds, materiality_overrides}` shape and never reads history. No ML claim leaks.
- **Privacy safeguards hold.** No raw customer IDs, no emails, no network egress, gitignored `recommended_history.json`, never-raises writer.
- **Confidence collapse is real on the V2 path.** Stepped 0.95/0.80/0.60 buckets are gone behind `EVIDENCE_CLASS_ENFORCED`; the legacy path still has them but is not exercised under the full V2 flag stack.
- **No true blockers exist.** Founder can proceed.

## DS Architect Findings

Full review: [ecommerce-ds-architect-m0-m9-review.md](ecommerce-ds-architect-m0-m9-review.md)

- The V2 spine is `legacy_adapter → guardrails → sizing → decide → V2 render → outcome log`, in that order, all behind flags. Each step is independently flag-gated.
- `src/engine_run_adapter.py:70-76` `_coerce_evidence` defaults to `EvidenceClass.TARGETING` whenever the legacy emitter doesn't stamp `evidence_class`. This is the mechanical root cause of universal ABSTAIN_SOFT on real fixtures: every legacy PRIMARY action is surfaced as targeting in EngineRun, and targeting plays are then suppressed by the M6 sizing layer because every prior in `config/priors.yaml` is `expert`/`observational`, not `causal`. The bias is conservative (no false-positive PUBLISH); it is structurally the reason no measured card has surfaced yet.
- All M5 guardrails are wired into `decide()` via `apply_guardrails` upstream, with `_decide_abstain_state` enforcing the same anomaly-HARD invariant defensively even when the M5 flag is off (belt-and-suspenders).
- `combine_multiwindow_statistics` (Fisher + inverse-variance) replaces min-p merge on the V2 path; pinned by `test_legacy_min_p_path_not_used_on_v2_combiner_output`. The combiner is correct and unit-tested but not exercised end-to-end on real data because no measured candidate has surfaced.
- ML-readiness is conservative and contract-correct: outcome log writes are local, gitignored, never-raise, and contain no PII. Calibration stub is a contract anchor, not a feature.
- **Zero true blockers.** Two optional documentation fixes recommended (founder test instructions + a one-line README in `m8_parity_review/`).

## Product PM Findings

Full review: [product-strategy-pm-m0-m9-review.md](product-strategy-pm-m0-m9-review.md)

- The V2 briefing is structurally faithful to the frozen contract: state-of-store → Recommended → Considered → Watching → DQ footer. Vocabulary is clean (no "measured" / "directional" / "evidence_class" leaks). Strong / Emerging / Targeting labels are correct. Targeting card disclaimer is verbatim from the contract.
- **One jargon leak survived:** the ABSTAIN_SOFT callout reason text ("no measured or directional recommendation cleared materiality + cannibalization gating") is the single most engineering-flavored string a merchant will see. Suggested rewrite: "No play in this month's analysis met our impact threshold for your store."
- **Empty-state hazard:** `small_sm` and `micro_coldstart` produce three sections of italic empty-state placeholders in a row (Recommended empty, Considered empty, Watching empty). The page is one notch above a 404. The PM contract Q1 explicitly warned against this; today's state hits that warning.
- **micro_coldstart silent dead-end:** monthly revenue est. $3,150, materiality floor $5,000. No play can ever fire. The page silently abstains without explaining the structural impossibility. Possible candidate for routing to ABSTAIN_HARD with `INSUFFICIENT_CLEAN_HISTORY` instead.
- **mid_shopify "Repeat rate: 0.0%"** renders as if it were a real signal; suggests data-not-computed rather than actually-zero. Should be guarded.
- **Considered (rejection list) is the contract's wow surface, and it's empty on every real fixture.** This is the biggest gap between contract promise and current rendering on real data.
- **Visual polish is austere** vs. legacy. M10 cosmetic; not a blocker. Founder should not interpret "ugly" as "broken."
- **Soft blocker noted, recommend accepting it.** Because the founder is testing whether the *product surface* is correct, not whether the engine selects well today.

## Disagreements and Resolution

Both agents reached the same verdict. The framing differs in two places, and the differences are not material:

1. **"Blockers vs. soft blockers."** DS Architect: zero blockers; the universal-ABSTAIN_SOFT outcome is the correct conservative failure mode. Product PM: one *soft* blocker — empty-everywhere on real data means the founder cannot test the heart of the product, but recommends accepting it as a caveat (Path A) rather than relaxing gates (Path B). **Resolution:** treat as a caveat, not a blocker. Both agents agree on the test plan.

2. **"What is the founder actually testing?"** DS Architect frames the test as: validate that V2 fails closed safely. Product PM frames the test as: validate that the merchant-facing memo is dignified. **Resolution:** both. Both reviews list complementary, non-overlapping inspection items. The reconciled "What To Inspect Manually" section below combines them.

There are no substantive disagreements about the state of the code, the safety of the system, or the readiness for manual testing.

## Blockers Before Manual Testing

**None.**

Both agents independently confirmed zero true blockers. The system passes every load-bearing safety invariant. There is no path through the V2 flag stack that fabricates stats, recommends during anomalies, double-counts audiences, or renders misleading dollar amounts.

## Minimum Fixes Before Manual Testing

Optional. None blocks. Pick zero, one, or two; do not delay testing for any of these.

1. **(PM #1, recommended)** Reword the ABSTAIN_SOFT callout reason in `src/decide.py` reason-text builder + `src/storytelling_v2.py` fallback (one or two strings). Replace "no measured or directional recommendation cleared materiality + cannibalization gating" with merchant-readable copy such as "No play in this month's analysis met our impact threshold for your store." This is the single most jargon-leaky string in the merchant view today.
2. **(DS #1, recommended)** Add a one-line README in `agent_outputs/m8_parity_review/` (or in the founder's local test notes) stating: "All three real fixtures will render ABSTAIN_SOFT under the full V2 stack. This is a documented transition state, not a bug. PUBLISH-state real-fixture rendering returns when measured plays are wired into the V2 detect path." Prevents misreading the test result.
3. **(PM #3)** Add a one-line "what this means" hint under empty-state placeholders so the page does not read as three blank sections in a row. Two strings in `storytelling_v2.py`.
4. **(PM #2)** Suppress the "Repeat rate: 0.0%" line on `mid_shopify` if the value is "not computed" rather than "actually zero." Single guard in the state-of-store builder.

If you want only the smallest possible pre-test surface, do (1) and (2). The rest can wait until the manual test informs the priorities.

## Caveats to Keep in Mind While Testing

- All three real pinned fixtures will render ABSTAIN_SOFT with the full V2 flag stack. This is expected, conservative, and documented. The renderer is correct; the gating is so tight on the current legacy-emitter inputs that nothing surfaces measured.
- The legacy adapter is the actual V2 spine. M3 detect and pure audience builders exist but are not the authoritative input to `decide()`. The architectural promise of "Detect → Size → Recommend" is structurally aspirational today; safety invariants are still met.
- All `config/priors.yaml` priors are `expert` or `observational`. Zero are `causal`. This is the structural reason every targeting card has `revenue_range.suppressed = True` under M6.
- `_coerce_evidence` defaults to TARGETING when the legacy emitter doesn't stamp `evidence_class`. This is why nothing surfaces measured on real data. Conservative bias only.
- No real-fixture PUBLISH or ABSTAIN_HARD V2 sample exists. Those layouts are pinned by synthetic tests (`tests/test_render_v2.py` x24, `tests/test_decide.py`).
- `legacy_actions_from_engine_run` exists but is not wired into `main.py`. Legacy `actions_log.json` is parallel exhaust. Non-issue for manual testing; becomes blocking only at M10 default flip.
- `consistency_across_windows` is computed but not used as a ranking tiebreaker (M7 known limitation).
- Watching threshold-to-act table is hardcoded to three metrics (`aov`, `repeat_rate_within_window`, `orders`).
- Calibration stub returns empty overrides on every call. Contract anchor, not a feature.
- `data/recommended_history.json` accumulates forever; manual cleanup is fine.
- POST_PROMO_WINDOW is a soft warning, not ABSTAIN_HARD (per M5 contract).
- V2 CSS is austere vs. legacy. Cosmetic; M10 cleanup will polish.
- `debug.html` is unconditional. If you ever zip `<out>/` and share it, debug.html goes too. Share only `briefings/<brand>_briefing.html`.
- `OUTCOME_LOG_ENABLED` defaults true. Acceptable: local, gitignored, never-raises, no PII.
- `micro_coldstart` has materiality floor ($5,000) above monthly revenue ($3,150). The page silently abstains without explaining this structural impossibility. The founder may want to decide whether stores in this state should be routed elsewhere.

## What To Inspect Manually

### `briefing.html` (V2)

For each of the three real fixtures (small_sm, mid_shopify, micro_coldstart):

1. **State-of-store paragraph** — are the three facts (AOV, repeat rate, orders) non-trivially store-specific, or do they read as a metric tuple?
2. **ABSTAIN_SOFT callout reason text** — is the load-bearing sentence comprehensible to a merchant? (Today: it leaks "materiality + cannibalization gating" jargon.)
3. **Three empty-state sections in a row** — does the page feel dignified or 404-adjacent?
4. **mid_shopify "Repeat rate: 0.0%"** — does this read as a real signal or as a missing computation surfaced as fact?
5. **micro_coldstart structural dead-end** — does the page acknowledge that materiality floor > monthly revenue, or does it silently abstain without explanation?
6. **Forbidden-string spot-check** — confirm by eye that no `p =`, `q =`, `CI`, `final_score`, `confidence_score`, numeric confidence percent, or "evidence_class" leaks into any visible copy. (Tests pin this; spot-check anyway.)
7. **Layout polish** — austerity is intentional. M10 will theme. Do not interpret "ugly" as "broken." Compare side-by-side with `agent_outputs/m8_parity_review/small_sm_legacy_briefing.html` to see what visual fidelity was traded for honesty.

### Synthetic-only inspections (because real fixtures don't trigger them)

8. **PUBLISH layout** — pass a hand-built EngineRun with at least one measured play through `render_engine_run` to see the green left-border, "Strong" badge, and a real range chip. Without this, you have not seen the heart of the product.
9. **ABSTAIN_HARD layout** — seed `data_quality_flags=[REFUND_STORM]` (or any HARD flag) and run end-to-end to validate the data-quality memo on real chrome.
10. **Considered (rejection list) on a synthetic** — seed a fixture where one play passes and another is held; confirm the "Why held / Would fire if:" copy is dignified.
11. **Targeting card with one surviving recommendation** — confirm the audience block + AOV + "Why no $ projection" context block reads as a recommendation, not as an absence.

### `receipts/engine_run.json`

12. Confirm `decision_state` matches the briefing (ABSTAIN_SOFT for the three real fixtures).
13. Confirm `recommendations[].evidence_class` is "targeting" everywhere on real data, not "measured."
14. Confirm `recommendations[].measurement` is `null` on every targeting card (contract invariant).
15. Confirm `recommendations[].revenue_range.suppressed` is `true` for all targeting cards (M6 conservative-prior outcome).
16. Confirm `considered[]` reason codes are populated (even if briefing renders empty Considered).
17. Confirm `data_quality_flags` is `[]` on the three real fixtures (none should trigger HARD).

### `receipts/debug.html`

18. Confirm `INTERNAL DIAGNOSTICS — NOT FOR MERCHANT DISTRIBUTION` banner is at the top.
19. Confirm `p_internal`, `ci_internal`, `consistency_across_windows`, `evidence_class`, observed effect, n, drivers, and reason codes are all visible — this is the engineer-facing artifact.
20. Confirm `briefing.html` does NOT link to `debug.html`.
21. Note for deployment: do not include `receipts/` in any merchant-facing email/zip. Share only `briefings/<brand>_briefing.html`.

### `data/recommended_history.json`

22. After two or three runs, confirm the file exists, is JSON-parseable, and contains `schema_version: "1.0.0"`.
23. Grep for `customer_id`, `Customer Email`, `Customer ID`, `email` — confirm zero hits.
24. Confirm `audience.id` is a string label and `audience.size` is an integer; no raw IDs.
25. Confirm the file is in `.gitignore`.

## Expected Current Behavior

**Acceptable.** Universal ABSTAIN_SOFT on real fixtures under the full V2 stack is the correct, conservative failure mode of a Phase 1 system whose `_coerce_evidence` defaults to `TARGETING` and whose priors are all `expert`/`observational` (no `causal` priors). The behavior is data-driven, deterministic, and safe. It is not concerning; it is not blocking. **It is, however, a surprise the founder should be primed for** — without context, three near-empty pages in a row will read as "the engine is broken." With context, they read as "the engine refused to lie and we have not yet wired the path that would let it speak with confidence."

## Recommended Manual Test Command

```bash
# Full V2 flag stack — this is the steady-state founder test
ENGINE_V2_OUTPUT=true \
ENGINE_V2_DECIDE=true \
ENGINE_V2_SIZING=true \
STATS_NAN_FOR_HARDCODED=true \
EVIDENCE_CLASS_ENFORCED=true \
TARGETING_RECLASSIFY_PLAYS=true \
MATERIALITY_FLOOR_SCALE_AWARE=true \
CANNIBALIZATION_GATE_ENABLED=true \
ANOMALY_GATE_ENABLED=true \
INVENTORY_GATE_ENABLED=true \
RECENTLY_RUN_FATIGUE_ENABLED=true \
OUTCOME_LOG_ENABLED=true \
python -m src.main --csv data/SM_orders.csv --out out/manual_test_small_sm

# Repeat for mid_shopify and micro_coldstart fixtures (use the same CSVs the M0 goldens pinned)
```

Then a **contrast run** with M4b flags off (so the legacy emitter still labels measured plays measured) to see what the M5/M6/M7 layers do on a non-empty input:

```bash
ENGINE_V2_OUTPUT=true \
ENGINE_V2_DECIDE=true \
MATERIALITY_FLOOR_SCALE_AWARE=true \
CANNIBALIZATION_GATE_ENABLED=true \
ANOMALY_GATE_ENABLED=true \
OUTCOME_LOG_ENABLED=true \
python -m src.main --csv data/SM_orders.csv --out out/manual_test_small_sm_contrast
```

If the exact module entrypoint differs (`python -m src.main` vs. a Makefile target vs. a CLI script), substitute the project's actual entry — the meaningful part is the env-flag stack. The Makefile already has a `golden-test` target; check there for the canonical entry.

## Pass / Fail Criteria for Founder Testing

**Pass** if all of the following hold:

1. The full V2 flag stack runs end-to-end on all three real fixtures without raising.
2. `briefing.html` for each fixture is renderable in a browser and shows a State-of-store paragraph + Recommended/Considered/Watching sections + DQ footer.
3. No fabricated stats appear in any merchant-facing copy (forbidden-string sweep stays at 0).
4. Targeting cards (when they appear, e.g. on the contrast run) show audience + disclaimer + "Why no $ projection" / source-labeled range chip — but no standalone dollar headline.
5. `engine_run.json` invariants hold: targeting ⇒ measurement null; sum p50 ≤ 25% monthly revenue; decision state matches briefing.
6. `recommended_history.json` writes successfully on every run with no PII.
7. `debug.html` is produced, banner is intact, not linked from briefing.
8. The synthetic PUBLISH and ABSTAIN_HARD inspections (items 8–11 above) render as expected layouts.

**Fail / report back** if any of the following hold:

1. Any forbidden string (`p =`, `q =`, `CI`, `final_score`, `confidence_score`, numeric confidence percent) leaks into a V2 briefing.
2. A targeting card shows a standalone dollar headline.
3. PUBLISH is reached on a real fixture with zero measured/directional plays.
4. ABSTAIN_HARD is reached but the briefing still lists recommendations (cleared-list invariant violated).
5. Sum of `revenue_range.p50` exceeds 25% of monthly revenue.
6. `recommended_history.json` contains any string matching `customer_id`, `Customer Email`, `Customer ID`, or `email`.
7. Any V2-flag run raises an unhandled exception in `decide()`, `apply_guardrails`, or the V2 renderer.
8. `briefing.html` links to or includes content from `debug.html`.

If any of items 1–8 (Fail) trigger, that is a real bug, not a caveat — stop, report, and fix.

## What Not To Reopen

Do not relitigate any of the following unless manual testing reveals a blocker:

- Whether to overhaul the engine.
- Whether to remove fake stats.
- Whether evidence classes (Strong / Emerging / Targeting) are the right merchant vocabulary.
- Whether targeting plays should hide p / q / CI / dollar headlines.
- Whether ABSTAIN_HARD and ABSTAIN_SOFT are the right two abstain modes.
- Whether V2 should be built behind flags.
- Whether `consistency_across_windows` is a pre-combination sign-agreement count (it is; locked in M4b).
- Whether `combine_multiwindow_statistics` replaces min-p (it does; locked in M4b).
- Whether the rejection list is a first-class output (it is; locked in M7).
- Whether the calibration stub returns the three-key dict (it does; locked in M9).
- Whether the legacy adapter or M3 detect feeds `decide()` today (legacy adapter does; M3 wiring is post-manual-test work).
- The 3-tier scale-aware materiality floor structure (locked in M5).
- Whether targeting plays without causal priors are suppressed (they are; locked in M6).

## Recommended Next Step

**Start manual testing.**

Optionally, before testing, do PM minimum-fix #1 (reword the ABSTAIN_SOFT callout reason) and DS minimum-fix #1 (add a one-line context note about the expected ABSTAIN_SOFT outcome). Both are sub-30-minute changes and meaningfully improve the test fidelity. Neither blocks.

After manual testing, return with findings and decide whether the next priority is:
- Wire M3 detect into `decide()` so the spine becomes Detect → Size → Recommend on real data (highest-value follow-on).
- Author one or more `causal` priors for the highest-value plays (`winback_21_45`, `frequency_accelerator`) so PUBLISH becomes reachable on real data.
- M10 cleanup and V2 default flip.

Do not start M10 cleanup yet — that decision should wait until the manual test confirms V2 is the product the founder wants to ship.
