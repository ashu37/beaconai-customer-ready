# Phase 6A Final Review

## Verdict
**Accepted with caveats.** Ready for founder/manual testing. **Not** ready for external merchant beta until the carry-forward caveats are addressed.

PM verdict: Accepted (ship to founder testing).
DS Architect verdict: Accepted (scientifically acceptable; trust contract holds end-to-end).

## Product Assessment

The Beauty Brand briefing reads like a recommendation from a teammate, not an analytics dashboard. A founder can read it cold in under 60 seconds and act:

- **Recommended Now (1 card):** `first_to_second_purchase`, audience 5,560, ~$329k addressable, directional badge "Emerging," `Why now` tied to the returning-customer-share trend.
- **Recommended Experiment (2 cards):** `discount_hygiene` (2,251 / ~$133k) and `bestseller_amplify` (1,475 / ~$87k), each with explicit "We will measure ___ in N days" and the verbatim "not projected lift" disclaimer.
- **Watching (1 row):** AOV trending down with a literal threshold-to-act sentence.
- **Considered (4 cards):** held plays with typed `Why held` and `Would fire if`.

This is the right ratio for a healthy brand: 3 things to do/test, 4 things explained-but-held, 1 thing watched. Section differentiation is clear — distinct visual treatment, distinct copy registers, distinct economic-context rules. The role-uniqueness invariant (B4) plus the B6 PUBLISH-branch considered-filter mean a play cannot smear across two roles in future runs.

`discount_hygiene` and `bestseller_amplify` are the right two first-ship experiments: clean intuitive mechanisms, audiences in the 1.5k–2.3k range, unambiguous outcome metrics, and shipped as "send and measure" rather than "we predict X% lift."

## Scientific / DS Assessment

The trust contract holds end-to-end on the pinned slate.

- **No fake stats:** zero occurrences of `p =`, `q =`, `confidence_score`, `final_score`, `Aura`, `Beacon Score`, `calibrated`, `uplift`, `ATE`, `ITT`, `treatment effect`, `expected lift`, `forecast`, or `predicted` anywhere in the rendered briefing.
- **Recommended Experiment is mechanically targeting-only:** `evidence_class = TARGETING` is stamped at the selector seam, `PlayCard.measurement is None` invariant is enforced, `revenue_range` is hard-suppressed with driver `experiment_no_calibrated_lift`, the renderer never calls the range-chip path on experiment cards, and `would_be_measured_by` is enum-keyed future-tense display copy.
- **Opportunity context is defensible, not a projection:** `audience_size × store_observed_AOV(L28)` with deterministic L56→L90 fallback and `None` when no positive AOV exists. The verbatim disclaimer "This is not projected lift; it shows the size of the audience if the play converts" is the only allowlisted occurrence of "projected lift" in the section, defended by exact-string allowlist.
- **Decision-core invariants:** ABSTAIN_SOFT collapses both Recommended sections to zero with experiment-eligible candidates routing to Considered with `TARGETING_HELD_UNDER_ABSTAIN`. Role uniqueness is asserted at every `decide()` return path across all three pairwise overlaps. Cannibalization gate is strict `< 0.30` overlap with every Recommended Now card. Slate diversity is enforced via the locked `AudienceArchetype` enum. Caps: 3/2/4/6 on recs/experiments/watching/considered.

Suite green at 900 passed, 14 skipped, 0 failed. M0 legacy goldens byte-identical. Kill switch `ENGINE_V2_SLATE=false` reverts to post-Phase-5.1 baseline byte-identically.

## Beauty Brand Slate Assessment

The pinned regression fixture (`tests/fixtures/synthetic_slate/healthy_beauty_240d_briefing.html`, 12,634 bytes, sha256 `3ace01703ae16b9d31ea685eac0421c29cb8450794c2b5c2732fcaad60125e7a`) is byte-stable across three back-to-back harness invocations and lives in a separate fixtures lane from M0 goldens.

Slate row matches the contract: 1 directional Recommended Now + 2 Recommended Experiment + 1 Watching + 4 Considered, decision_state=`publish`. The 19 B6 tests pin per-card structural framing (Run-as-experiment badge, measured-by line, opportunity-context block, disclaimer present), forbidden-token absence within `section.recommended-experiment`, and slate-shape invariants.

Operational caveat: the fixture had to pin `WINDOW_POLICY=auto` in `_B6_ENV_OVERRIDES` to defend against suite-order `os.environ` contamination from `.env`. Bounded fragility — any future B6-style fixture must explicitly pin every env key whose default differs from `.env`.

Minor coding inconsistency: the `empty_bottle` Considered card carries `data-reason-code="no_measured_signal"` despite audience=0; the contract-final spec named this card `audience_too_small`. Both reason codes are typed and have populated text — Phase 6B Considered-list quality fix, not a trust violation.

## Trust Constraints Check

| Constraint | Status |
|---|---|
| No fake p-values / q-values | Pass — zero occurrences |
| No fabricated effect sizes | Pass — `revenue_range` suppressed on experiments, `PlayCard.measurement is None` |
| No projections framed as forecasts | Pass — opportunity context is `audience × AOV` with verbatim "not projected lift" disclaimer |
| No causal claims from observational data | Pass — directional cards say `direction agrees across N windows`, experiments say `We will measure …` |
| Recommended Experiment safely targeting-only | Pass — evidence_class stamped, measurement null-invariant, revenue_range hard-suppressed |
| ABSTAIN_SOFT routing | Pass — `recommended_experiments == []` enforced at two seams, held plays routed to Considered with typed reason |
| Role uniqueness | Pass — asserted at every `decide()` return path across all three pairwise overlaps |
| Cannibalization (< 0.30 overlap) | Pass — strict, pairwise across every Recommended Now card |
| Slate diversity (archetype) | Pass — locked enum, property-tested across 64 random sets |
| Caps (3/2/4/6) | Pass — surveyed under property-style invariants |
| Forbidden-token sweep on `section.recommended-experiment` | Pass — `projected lift` exact-string allowlisted only inside disclaimer constant |

## Remaining Caveats

1. **Section ordering inversion (PM caveat).** Rendered DOM is Recommended Now → Recommended Experiment → **Considered → Watching** → DQ-footer. Contract specified Watching before Considered. Cheap fix; do before external beta.
2. **`mechanism` string loaded but not surfaced on experiment cards (PM caveat).** Priors metadata (Ticket A3) carries a merchant-readable mechanism, but the rendered card does not show it. Founders will ask "what's the actual email/campaign?" Address before external beta.
3. **AnomalousWindow auto-registration deferred (DS caveat).** `promo_anomaly_240d` will publish 1 directional + 2 experiment cards even during a promo spike. Biggest live trust gap. Acceptable for founder testing if scenario is flagged; not acceptable for GA. Phase 6B priority.
4. **AOV in opportunity context is store-wide L28, not segment AOV (DS caveat).** Disclaimer limits the claim correctly, but the merchant's natural reading may be slightly inflated for sub-segments whose AOV diverges from the store average. Phase 6B+ consider per-segment AOV.
5. **Recently-run-fatigue is a NO-OP (DS + PM caveat).** Repeated runs will surface the same two experiment cards. Mitigate with cadence guidance during founder testing; unblock with M9 outcome log.
6. **Considered list collapses to `no_measured_signal` for most rejected plays (PM + DS caveat).** 3 of 4 cards in the pinned fixture share the reason. Differentiation by audience snapshot reads acceptably but the copy is repetitive. Phase 6B+ Considered-quality refresh.
7. **`empty_bottle` Considered card reason-code mismatch (DS caveat).** `audience=0` but `reason_code=no_measured_signal` instead of `audience_too_small`. Phase 6B cleanup.
8. **`audience_overlap` missing-key default 0.0 is permissive (DS caveat).** If M3 stops emitting overlap entries for some recs, a heavily overlapping experiment could slip through. Add a future-tightening test that asserts overlap entries exist for every (rec-now, experiment-candidate) pair. Phase 6B.
9. **`WINDOW_POLICY=auto` env-pin fragility (DS caveat).** Future synthetic fixtures must explicitly pin every env key whose default differs from `.env`.
10. **B6 considered-filter is ordering-coupled (DS caveat).** Filter assumes `assemble_considered` runs before `_select_recommended_experiments`. A reorder would trip `_assert_role_uniqueness` as a hard `decide()` failure rather than a quiet regression — caught, but document the ordering constraint above the filter.
11. **`projected lift` allowlist is exact-string (DS caveat).** Any paraphrase of `OPPORTUNITY_CONTEXT_DISCLAIMER` without updating the constant in lockstep will trip the B2 sweep. Feature, not bug — document for copywriters.
12. **`would_be_measured_by` outcomes are not yet computable end-to-end (DS caveat).** `email_attributed_revenue_in_7d` needs Klaviyo wiring; `incremental_orders_in_14d` needs a control-group definition; only `repeat_purchase_in_30d` is computable from Shopify alone. Future-tense framing is honest, but the "we will measure" promise is a check the engine cannot yet cash. Phase 6B+ outcome wiring.
13. **Pinned regression covers Beauty Brand only (PM caveat).** Other verticals / health profiles (`small_store_240d`, `cold_start_45d`, supplements, low-inventory) need their own slate-row pins before we trust the shape generalizes.

## Blockers, If Any

**None.** No issue from either reviewer rises to a blocker for founder/manual testing. The accepted deferrals (inventory loader pandas-compat, AnomalousWindow auto-registration, `empty_bottle` ct/lb/mg parser, lifecycle maintenance, recommended_history fatigue, revenue_range unsuppression) are correctly out of scope and do not gate this milestone.

## Manual / Founder Testing Readiness

**Ready.** Run founder testing on at least three scenarios from the synthetic harness:

1. `healthy_beauty_240d` — the pinned slate row (happy path).
2. `small_store_240d` — ABSTAIN_SOFT, held experiments routed to Considered, Watching contains load-bearing metrics via the A1 fallback.
3. `cold_start_45d` — ABSTAIN_HARD, data-quality memo path, both Recommended sections empty.

Flag for the founder ahead of any `promo_anomaly_240d` run: that scenario will produce 1 Recommended Now + 2 Recommended Experiment because AnomalousWindow auto-registration is deferred to Phase 6B. Founders should interpret it accordingly; do not ship this scenario to external merchants until the gate is wired.

Use `ENGINE_V2_SLATE=false` for an A/B comparison against the post-Phase-5.1 baseline if a founder wants to see the pre-slate output.

## Recommended Next Step

Begin manual/founder testing on the three scenarios above. Capture founder reactions on:

- whether the 3-2-1-4 ratio reads as a recommendation vs. an analytics dump
- whether the "Run as experiment" framing is understood as send-and-measure (not as a forecast)
- whether the founder's first question after reading an experiment card is the missing `mechanism` string ("what's the actual campaign") — this validates carry-forward caveat #2
- whether section ordering (Considered before Watching) is felt as wrong — validates carry-forward caveat #1

Phase 6B should sequence (in priority order):
1. Section reordering (Watching before Considered).
2. Surface `mechanism` on experiment cards.
3. AnomalousWindow auto-registration.
4. Outcome-log wiring for `would_be_measured_by` to become a check the engine can cash.
5. Considered-list copy refresh + `empty_bottle` reason-code fix.
6. Overlap-entry-existence test as a future-tightening of the cannibalization gate.

Do not begin Phase 6B until founder testing produces signal on caveats 1–6.
