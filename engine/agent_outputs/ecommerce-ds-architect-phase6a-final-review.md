# Phase 6A — DS Architect Final Review

## Verdict
**Accepted.** Phase 6A is scientifically acceptable for founder/manual testing of the BeaconAI Action Engine. The trust contract holds end-to-end across all four merchant-facing sections on the pinned Beauty Brand slate. I would let a merchant rely on this output tomorrow under the explicit caveats listed below.

## Scientific honesty contract

The contract holds across the four sections.

- Recommended Now (`first_to_second_purchase`): rendered as `data-evidence-class="directional"`, badge "Emerging" (not "Strong"), `Why now` text describes the *direction* of returning-customer share with `direction agrees across 3 windows` — no p-value, no CI, no q-value, no `confidence_score`, no causal claim, no `Aura` / `Beacon Score`. The opportunity-context block uses `about $329.0k addressable order value` with the verbatim disclaimer "This is not projected lift; it shows the size of the audience if the play converts." This is the load-bearing forcing function. `revenue_range` is suppressed (no `$ p50` headline, no chip larger than the disclaimer).
- Recommended Experiment (`discount_hygiene`, `bestseller_amplify`): `data-evidence-class="targeting"`, badge "Run as experiment", no `Observed:` line, no measurement block, no statistical claim. `would_be_measured_by` rendered exclusively via the contract-locked enum-to-display mapping ("We will measure email-attributed revenue in 7 days." / "We will measure repeat purchase in 30 days."). Raw enum strings (`EMAIL_ATTRIBUTED_REVENUE_IN_7D` etc.) are absent from the rendered HTML, confirmed by the B2 sweep and verified against the pinned briefing.
- Watching: single `aov` row with `trend="down"` and a literal threshold-to-act sentence. No dollar context, no predictive claim.
- Considered: 4 cards, each with typed `data-reason-code`, `Why held`, `Would fire if`, and an `evidence_snapshot` audience-only line. No dollar context, no statistical claim.

The 19 universal-forbidden tokens (`calibrated`, `uplift`, `ATE`, `ITT`, `treatment effect`, `expected lift`, `forecast`, `predicted`, `p =`, `q =`, `p-value`, `q-value`, `confidence_score`, `final_score`, `p_internal`, `ci_internal`, `Aura`, `Beacon Score`, `beacon_score`) have zero occurrences in `section.recommended-experiment`. The phrase "projected lift" appears exactly twice (one per experiment card), each occurrence inside the verbatim `OPPORTUNITY_CONTEXT_DISCLAIMER` allowlist. The B2 allowlist mechanism is exact-string `str.replace`, not regex; defended by `test_disclaimer_phrase_remains_allowed_at_exact_string` against a future copy edit silently widening the allowlist.

## Recommended Experiment safety (targeting-only)

Safe. Both experiment cards are mechanically targeting-only:

- `evidence_class = TARGETING` is stamped at the selector seam (`src/decide.py::_select_recommended_experiments`) and pinned at the schema layer (`PlayCard.measurement` is `None` on every output card; the `evidence_class == "targeting" ⇒ measurement is null` invariant is enforced in `tests/test_targeting_measurement_invariant.py` Fix 2).
- `revenue_range = RevenueRange(suppressed=True, drivers=[{"reason": "experiment_no_calibrated_lift"}])` is hard-stamped at write time. The renderer additionally never calls `_render_revenue_range_chip` on experiment cards — belt-and-suspenders against any future producer that mis-stamps `suppressed=False`.
- `would_be_measured_by` is the future-tense send-and-measure framing, NOT a measurement claim. The display copy ("We will measure ...") is enum-keyed via `_WOULD_BE_MEASURED_BY_DISPLAY_COPY` in `src/storytelling_v2.py`; free-text rendering is forbidden and tested.
- `Observed:` line, `Why now:` line, range chip, dollar headline — all absent on the experiment cards in the pinned fixture. Confirmed by direct DOM inspection of `tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html` and by `tests/test_targeting_no_dollar_headline.py` (M8 invariant).
- The contract-locked allowlist `{discount_hygiene, bestseller_amplify}` is the only set of plays that can reach this section. Every other targeting play is structurally barred even if it has full priors metadata (Ticket A4 rule 3).

The "Run as experiment" framing is the merchant-readable expression of the contract: this is a hypothesis we will test, not a play we have evidence for.

## Opportunity context defensibility

Defensible. The opportunity context is `audience_size × store_observed_AOV(L28)`. It is NOT a projection.

- The math is `2,251 × $59 = ~$133.2k` for `discount_hygiene`. No realization factor, no probability weighting, no causal prior, no multiplier. Verified in `src/measurement_builder._build_opportunity_context` (Phase 5.1) and reused verbatim by the experiment selector (Ticket B1.5).
- The AOV source is `aligned[L28]['aov']` with deterministic fallback to L56 then L90, returning `None` (and thus omitting the block) when no defensible positive AOV exists. NaN, zero, missing keys, and missing `aligned` all route to `None` — pinned by 5 explicit tests in `tests/test_recommended_experiment_opportunity_context.py`.
- The disclaimer "This is not projected lift; it shows the size of the audience if the play converts" is rendered verbatim per card and is enforced as the only allowlisted occurrence of "projected lift" in the section.
- The `data-aov-source="store_observed"` and `data-aov-window="L28"` attributes are scraper-readable provenance.

This is a sizing context, framed as a sizing context, with the negation disclaimer as the forcing function. It is the largest defensible interpretation of the fixture's data without invoking any causal claim. A merchant reading "$133.2k addressable order value" alongside "This is not projected lift" should correctly understand it as audience × AOV reach, not as forecast revenue.

The single risk worth noting: Phase 5.1 AOV is L28 store-observed AOV across all customers, not the AOV of the targeted sub-audience. This is acknowledged in the contract; merchants who interpret it as "AOV of the targeted segment" will be slightly off. Caveat — not a blocker, because the disclaimer correctly limits the claim to "size of the audience if the play converts."

## No-fake-stat / no-forecast / no-causal-claim audit

Pass. I went through the pinned briefing line by line.

- No `p =`, `q =`, `p-value`, `q-value`, `confidence_score`, `final_score`, `p_internal`, `ci_internal` appear anywhere.
- No `Aura`, `Beacon Score`, `beacon_score` appear anywhere.
- No `calibrated`, `uplift`, `ATE`, `ITT`, `treatment effect` appear anywhere.
- No `expected lift`, `forecast`, `predicted` appear anywhere.
- "projected lift" appears 3 times: 1 on the Recommended Now directional card and 2 on the Recommended Experiment cards, each inside the verbatim disclaimer.
- "measure" appears in future tense only ("We will measure ...") on experiment cards. "measured" (past tense, evidence claim) is absent from `section.recommended-experiment` — pinned by `test_measured_past_tense_absent_from_experiment_section`.
- "evidence" / "evidence-backed" do not appear in visible body copy on experiment cards. The string `data-evidence-class="targeting"` is a CSS/scraper data attribute, not merchant-facing copy; visible-text scoping in B2 is the correct contract layer.
- The Recommended Now directional card carries `Observed: returning customer share (direction agrees across 3 windows)`. This is a *direction* claim about a *state* statistic, NOT a treatment-effect claim. It is consistent with the contract's "directional" evidence class.
- Watching threshold copy is "+/- 5% to fire an AOV play" — a rule-based action threshold, not a forecast.
- Considered cards carry "would fire when at least one measured or directional play clears evidence and materiality this run" — an internal-eligibility statement, not a merchant-facing claim about lift.

## Decision-core invariants (ABSTAIN_SOFT, role uniqueness, overlap, diversity)

All four invariants are correctly enforced.

- **ABSTAIN_SOFT (Ticket B3).** Under ABSTAIN_SOFT, `engine_run.recommended_experiments == []` is enforced both at the EngineRun construction seam in `decide()` and inside the selector itself (rule 2). A `publish_shadow=True` call computes the would-have-qualified set so held experiment-eligible candidates route into Considered with `ReasonCode.TARGETING_HELD_UNDER_ABSTAIN`, populated `reason_text` and `would_fire_if` reused verbatim from Fix 3 templates. Dedupe is three-layered: (1) `already_routed` set inside the ABSTAIN_SOFT branch, (2) `_dedupe_rejections` inside `assemble_considered`, (3) the renderer iterates the deduped list. Pinned by 14 tests including a regression that verifies ABSTAIN_SOFT renders zero `<section class="recommended-experiment">` cards.
- **Role uniqueness (Ticket B4).** `_assert_role_uniqueness(engine_run)` runs at the end of every `decide()` return path (PUBLISH, ABSTAIN_SOFT, ABSTAIN_HARD) and checks all three pairwise overlaps among `recommendations`, `recommended_experiments`, `considered`. Watching is intentionally exempt (it is metric-keyed, not play-keyed). The Beauty Brand fixture is the e2e forcing function: `discount_hygiene` and `bestseller_amplify` arrive in `engine_run.considered` as `no_measured_signal` from upstream Phase 5 routing, then get promoted to `recommended_experiments` by the slate selector; the B6 PUBLISH-branch filter drops them from Considered so the assertion does not fire. This is the correct fix — the alternative would have been to suppress the assertion, which would have been the wrong direction.
- **Cannibalization (Ticket B5).** Strict `< 0.30` overlap with every Recommended Now card. Threshold is exclusive on 0.30 (i.e., 0.30 itself is rejected). Pairwise check across every Recommended Now card, not just the top one. Missing overlap entries default to 0.0 — permissive, but pinned as the documented contract; if M3 ever stops emitting overlap entries for some recs, a heavily overlapping experiment could slip through. Documented as a future-tightening risk, not a blocker.
- **Slate diversity (Ticket B5).** Locked `AudienceArchetype` enum (8 lowercase values) is the dedupe key. Beauty Brand happy-path: `discount_hygiene → discount_buyer`, `bestseller_amplify → hero_sku_buyer` — distinct, both survive. Property tests (64 random sets) assert unique archetypes per run. A separate property test (32 random sets under same-archetype override) confirms the dedupe is hard regardless of input permutation.
- **Cap.** Hard cap 2 on `recommended_experiments`, hard cap 4 on Watching, hard cap 3 on `recommendations`, hard cap 6 on `considered` (rendered). All four caps survive the property-style invariants.

## Beauty Brand pinned regression — fixture acceptability

Acceptable as a regression fixture, with one operational caveat.

The pinned fixture (`tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`, 12,634 bytes, sha256 `3ace01703ae16b9d31ea685eac0421c29cb8450794c2b5c2732fcaad60125e7a`) is byte-stable across three back-to-back harness invocations and is not coupled to the M0 legacy goldens (lives in a separate `tests/fixtures/synthetic_slate/` lane). The slate row matches the contract:

- 1 Recommended Now: `first_to_second_purchase`, audience 5,560, addressable about $329.0k, directional.
- 2 Recommended Experiment: `discount_hygiene` (audience 2,251, $133.2k), `bestseller_amplify` (audience 1,475, $87.3k), each with the appropriate `would_be_measured_by` mapping and the disclaimer block.
- 1 Watching: `aov` trending down, threshold "+/- 5% to fire an AOV play".
- 4 Considered: `winback_21_45`, `subscription_nudge` (audience_too_small with audience=2), `routine_builder`, `empty_bottle` (audience=0).
- decision_state = `publish`.

The "Considered is repetitive" baseline caveat (3 of 4 cards collapse to `no_measured_signal`) is acknowledged but not blocking — that is a Considered-list quality issue, not a trust-contract issue.

Operational caveat: the fixture required pinning `WINDOW_POLICY=auto` in `_B6_ENV_OVERRIDES` to defend against suite-order env contamination from `.env`. This is a real but bounded fragility: any future B6-style fixture must explicitly pin every env key whose default differs from `.env`. Not a blocker for founder testing, but it means the byte-stable snapshot test can break in confusing ways if a future test in the suite reloads `src.utils` against a polluted `os.environ`. Documented in the B6 summary; the failure message points the future engineer at the right fix.

The `empty_bottle` Considered card carries `data-reason-code="no_measured_signal"` despite audience=0; the contract-final spec named this card as `audience_too_small`. This is a minor coding inconsistency (the reason code on this card does not match the stated baseline reason code) but does not violate the trust contract — both reasons are typed, both have populated `reason_text` and `would_fire_if`. Treat as a Phase 6B Considered-list quality fix, not a blocker.

## Manual/founder testing readiness

Ready. The full V2+slate stack on `healthy_beauty_240d` produces a publishable, scientifically defensible briefing. Suite is green at 900 passed, 14 skipped, 0 failed. M0 legacy goldens remain byte-identical. The kill switch (`ENGINE_V2_SLATE=false`) reverts everything to the post-Phase-5.1 baseline byte-identically — useful for an A/B comparison during testing.

For founder testing I recommend running with the full stack on at least three scenarios already covered by the synthetic harness:

1. `healthy_beauty_240d` (the pinned slate row, the happy path).
2. `small_store_240d` (ABSTAIN_SOFT, B3 routes 2 held experiments to Considered, Watching contains load-bearing metrics via the A1 fallback).
3. `cold_start_45d` (ABSTAIN_HARD, data-quality memo path, both lists empty).

The `promo_anomaly_240d` scenario will produce 1 Recommended Now + 2 Recommended Experiment because AnomalousWindowCheck auto-registration is deferred to Phase 6B. Document this for the founder so the output is interpreted correctly: this scenario is known to overclaim until the gate is wired.

## Caveats to carry forward

1. **AnomalousWindow auto-registration deferred (accepted).** `promo_anomaly_240d` will publish a directional Recommended Now and a 2-card experiment slate even when the run is dominated by a promo spike. This is the biggest live trust gap in Phase 6A. Acceptable for founder testing because the founder can interpret the data; not acceptable for a merchant-facing GA. Phase 6B priority.
2. **AOV in opportunity context is store-wide L28, not segment AOV.** A discount-prone-buyer segment may have a materially different AOV than the store average. The disclaimer correctly limits the claim ("size of the audience if the play converts") but the merchant's natural reading may be slightly inflated. Document for the founder; consider per-segment AOV in Phase 6B+.
3. **Recently-run-fatigue is a NO-OP.** A merchant running this monthly will see the same `discount_hygiene` and `bestseller_amplify` experiment cards every run regardless of prior adoption. This will feel naggy after run 2. Phase 6B+ when `recommended_history.json` is non-stub.
4. **Considered list collapses to `no_measured_signal` for most rejected plays.** Visible in the pinned fixture — `winback_21_45`, `routine_builder`, `empty_bottle` all carry the same reason. A merchant looking at Considered for differentiation between plays will not find it. Differentiated reason codes are a Phase 6B+ concern.
5. **`empty_bottle` Considered card has `audience=0` but `reason_code=no_measured_signal`.** The contract baseline named this `audience_too_small`. Minor reason-code consistency bug; not a trust violation. Phase 6B cleanup.
6. **`audience_overlap` missing-key default of 0.0 is permissive.** If M3 stops populating overlap dicts for some Recommended Now plays, a heavily overlapping experiment could slip through. Pin a future-tightening test that asserts overlap entries exist for every (rec-now, experiment-candidate) pair before the cannibalization gate runs. Phase 6B.
7. **`WINDOW_POLICY=auto` env-pin in B6 fixture.** Suite-order env contamination is mitigated for B6 but the harness does not auto-decontaminate every env key; a future synthetic fixture must explicitly pin its env. Documented but fragile.
8. **The B6 PUBLISH-branch considered-filter is ordering-coupled to `assemble_considered` running before `_select_recommended_experiments`.** A future refactor that reorders these calls will silently break the role-uniqueness invariant. The defensive `_assert_role_uniqueness(out)` will catch it — but as a hard `decide()` failure, not a quiet regression. Document the ordering constraint in the comment block above the filter (already done).
9. **`projected lift` allowlist is exact-string.** Any copy edit to `OPPORTUNITY_CONTEXT_DISCLAIMER` (paraphrase, casing change, word reorder) without updating the constant in lockstep would trip the B2 sweep. This is a feature, not a bug — document for future copywriters.
10. **`would_be_measured_by` outcome metrics are not yet computable end-to-end.** `email_attributed_revenue_in_7d` requires Klaviyo wiring that does not exist; `incremental_orders_in_14d` requires a control group definition that is not specified; `repeat_purchase_in_30d` is the only one that is computable from Shopify data alone. The future-tense framing is honest, but the "we will measure" promise is a check the engine cannot yet cash. Phase 6B+ when outcome wiring lands.

## Blockers (if any)

**None.** No issue I found rises to the level of blocking founder/manual testing. The accepted deferrals named in the prompt (inventory loader pandas-compat, AnomalousWindow auto-registration, `empty_bottle` ct/lb/mg parser, lifecycle maintenance, recommended_history fatigue, revenue_range unsuppression) are correctly out of scope. The trust contract holds end-to-end on the new slate.
