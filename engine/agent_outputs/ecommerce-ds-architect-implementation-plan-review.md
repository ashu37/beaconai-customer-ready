# DS Architect Review — Implementation Plan QA

## Verdict

**Approve with changes.** The plan is structurally sound and faithfully sequences the reconciled direction. It correctly identifies the migration risk (entangled monolith, renderer-coupled fields) as the dominant problem and chooses a parallel-build-behind-flag strategy that keeps the engine runnable at every milestone. M0 (golden freeze) and M1 (additive contracts) are exactly the right starts.

But there are three architectural gaps that, if not closed before engineering begins, will let the worst pathologies of the current engine survive in V2 under new field names. None of them require redesign; all three are scope clarifications inside existing milestones.

---

## What the Plan Gets Right

- **M0 golden freeze before any decision-logic touch.** This is the single most important sequencing decision. The audit's #1 risk (NaN cascade through `benjamini_hochberg` / `compute_score` / `_calculate_business_confidence`) is almost guaranteed to break fixtures; pinning current outputs first turns "did we regress" from a debate into a diff.
- **Schema-before-behavior in M1.** `EngineRun` as additive in M1, populated via legacy adapter, then consumed as authoritative in M7/M8 — this is the right way to migrate a renderer-coupled monolith. The legacy adapter `legacy_actions_from_engine_run()` (T8.7) is the load-bearing piece that lets M8 flip without touching `actions_log.json` consumers.
- **M2 play registry + `config/priors.yaml`.** Extracting inline per-vertical constants into a versioned, source-classed yaml (`source_class ∈ {observational, causal, expert}`) is the correct ML-readiness hook. The `drivers[]` provenance in M6 (T6.4) is the matching write-side that makes future calibration possible without re-architecting briefings.
- **`evidence_class` as enum, not string.** T2.x and T4.3 keep this typed; PM Q5's separation of internal `evidence_class` (typed) from merchant `confidence_label` (qualitative) is preserved by T7.x.
- **Reroutes min-p merge to `combine_multiwindow_statistics` rather than rebuilding it (T4.5).** Audit cleared the combiner; not rebuilding it is correct.
- **Two abstain modes (T7.7), not one.** ABSTAIN_HARD vs ABSTAIN_SOFT correctly preserves the skeptic's distinction between "your data is unreliable" and "this month is quiet."
- **Saturation guard kept and renamed (T5.4 backoff).** The plan explicitly deviates from the DS architect's implicit removal of saturation; this is the correct call (skeptic F-4) and the deviation is called out.
- **Rejected plays as first-class output (T7.5, T8.2).** Sequenced into M7/M8, not deferred to polish. The 11-code `reason_code` enum is the contract that makes "showing the rejection work" a structural feature, not stylistic.
- **`recommended_history.json` writer in M9 (T9.1).** Even unread, persisting it is the right ML-readiness move — without it, calibration is structurally impossible later.
- **Anti-scope list ("don't redesign `_compute_candidates` as one PR", "don't generalize the registry into a rules engine").** Items 1, 4, and 6 directly address the failure mode where Phase 1 turns into a rebuild.

---

## Architecture Gaps

### G1. The merit-rank signal is still a single dollar number derived from priors

T7.2 ranks within-class by `revenue_range.p50`. For TARGETING plays, `p50` is `audience × p_action × incremental_orders × AOV` where `p_action` comes from `vertical_prior` (T6.2). This is the skeptic's D-2 / A-3 critique, and the plan inherits it.

The plan does mitigate this with class-first ranking (measured > directional > targeting), so a TARGETING play cannot outrank a MEASURED play on raw $. Good. **But** within the TARGETING bucket, the rank-key is still essentially `audience × vertical_prior`, which is a sort-by-audience-size with extra steps when vertical_prior is shared across plays in the same vertical.

This is architecturally fine if and only if the renderer in M8 (T8.5) actually suppresses the `p50` headline on targeting cards as PM Q9 #5/6 demands. The plan says it does. Verify in M8 acceptance that targeting cards literally do not display a single-number headline — only the range and the source label. If this slips, p50-as-decision returns under a new chip.

### G2. "Robustness across windows" as evidence is under-specified

T4.5 reroutes to `combine_multiwindow_statistics`. Good. But PM Q5's mapping rule for `Strong` requires `consistency_across_windows >= 2` — and the plan does not specify how that is computed for a play that ran through the combiner. Is consistency = "sign of effect agrees across windows"? "Combiner CI excludes 0 in ≥2 of 4 windows"? "P < α in ≥2 windows post-combination"?

The DS architect's original framing was: windows are robustness checks, not evidence. The combiner produces *one* p, *one* effect, *one* CI. So `consistency_across_windows` becomes either (a) a separate count of sign-agreeing windows computed pre-combination, or (b) something the combiner produces as a byproduct. The plan doesn't say which, and the difference matters because (a) preserves the right framing and (b) silently re-imports the multi-window-as-evidence error.

This needs a one-paragraph spec inside T4.5 or a new T4.5b. Default position: `consistency_across_windows = count of windows where sign(observed_effect) == sign(combiner.effect) AND |t-stat| > 1` — pre-combination, sign-only, not a p-vote.

### G3. Anomalous-window detection drives ABSTAIN_HARD only; partial-window contamination is not handled

T1.2 + T5.2 together detect BFCM/refund-storm/test-order/insufficient-clean-history and trigger ABSTAIN_HARD. But the architect's anti-pattern catalog (Hypothesis Laundering, Window Shopping) and the audit's L-2 imply a softer failure: a 28-day window that *contains* a BFCM week without being centered on it inflates measured effects without triggering ABSTAIN_HARD.

The plan's binary HARD-or-not gate misses this. The fix is small: a partial-contamination flag that *downgrades* affected plays' `evidence_class` from `measured` to `directional`, rather than abstaining the whole run. Right place is T5.2 + T4.3 (`classify_evidence` reads the flag).

This is not a showstopper for Phase 1 — without it, the engine over-classifies as MEASURED in fringe windows but does not overclaim outright (revenue ranges still suppress, materiality floor still applies). Flag it as a known limitation in `docs/engine_flags.md` if not addressed in Phase 1.

---

## DS-Risk Areas

- **NaN-cascade in M4 is correctly the top risk** (plan's Risk #1). The plan's mitigation (flag-gated rollout + golden re-baseline + 2-day budget for fixture migration) is right. The remaining concern: T4.7 collapses `_calculate_business_confidence` to `_calculate_statistical_confidence(p)` only — but for TARGETING plays, p is now NaN. T4.2 says "make scoring NaN-safe" but leaves the semantics unspecified. **Specify**: NaN-p for a TARGETING play means `confidence_label = "Targeting"` deterministically, never falls through to `Strong/Emerging`. This is a one-line invariant in `evidence.py:classify_evidence` (M4 new module).

- **T4.5's combiner reroute will move plays across `evidence_class` bands.** A play that was MEASURED via cherry-picked min-p is now DIRECTIONAL once the combiner's honest p applies. This is correct, but it will make the briefings on the small/cold-start fixtures dominated by DIRECTIONAL/TARGETING — exactly the skeptic A-2 "80% TARGETING briefing" failure mode. The plan addresses this only via the rejection list and state-of-store wow surface. Verify in M8 parity review that ABSTAIN_SOFT and Considered-not-recommended are *visually load-bearing* on the small-merchant fixture before flipping `ENGINE_V2_OUTPUT=true`.

- **Class-aware ranking interacts badly with materiality floor (T5.3).** A MEASURED play with small audience may fall below the materiality floor and become RejectedPlay; meanwhile a TARGETING play with large audience may clear the floor and become the only recommendation. The class-first ranking still surfaces the targeting play *as* the top recommendation, just by being the only one. The skeptic E-1 fatal-omission concern is met (engine demotes to ABSTAIN_SOFT when 0 measured/directional clear, T7.4) — but the *interaction* between materiality floor and the ≥1 measured/directional requirement needs to be explicit. Specify in T7.4: "If after materiality + cannibalization gating 0 measured/directional remain, demote to ABSTAIN_SOFT regardless of how many TARGETING plays remain. Do not publish a TARGETING-only briefing as PUBLISH state."

- **`p_internal` and `ci_internal` persistence is correct, but T9.2 doesn't say where they live for TARGETING plays.** PM Q2 hard-contract rule: `evidence_class = "targeting"` REQUIRES `measurement = null`. Then `p_internal` is null too. That's fine, but the receipts/debug page (T9.5) needs to display the audience-economics drivers for targeting plays in lieu of p_internal. Specify in T9.5.

- **`_calculate_statistical_confidence` is a step function (audit L-6).** T4.7 keeps it. PM Q5's `Strong / Emerging / Targeting` mapping is also a step function, which is fine merchant-facing. But the receipts page should not surface `_calculate_statistical_confidence`'s 0.95/0.80/0.60 buckets — those are an internal artifact that will read as "confidence percentages we're hiding." Specify in T9.5: receipts page shows `evidence_class`, `p_internal`, observed effect, and `n` — not the stepped confidence number.

---

## ML-Readiness Review

The plan does this part well. The five hooks PM Q8 demands are present and sequenced:

1. **`measurement.p_internal`/`ci_internal` persistence** — T1.1, T9.2 (verified-not-rendered).
2. **`revenue_range.drivers[]`** — T6.4 lock-down in T9.3.
3. **`recommended_history.json`** — T9.1 writer; T5.5 reader stub.
4. **`evidence_class` as typed enum** — T2.x, T4.3.
5. **`vertical_prior` registry** — T2.4 `config/priors.yaml`.

The matching anti-claim discipline (no "calibrated" copy, no uplift terminology, no learning CONFIDENCE_MODE) is present in the anti-scope list (items 2, 11).

**One gap**: T9.4 stubs `load_realization_factors()` returning `{}` to "establish the interface a future ML layer plugs into." But the interface as specified is too thin to be an honest hook. A real calibration model needs to write back to: (a) `priors.yaml` per-key values, (b) per-play `evidence_class` thresholds, (c) per-play `materiality_floor` adjustments. The stub should at minimum declare these three return types as null fields, so the schema is the contract.

**Specify in T9.4**: stub returns `{prior_overrides: {}, evidence_thresholds: {}, materiality_overrides: {}}` rather than `{}`. This is a one-line clarification but it is the difference between "ML hook" and "vibes."

**One concern, not a gap**: the plan correctly avoids introducing uplift/ATE/ITT terminology. However, future-state plans (Phase 2+) imply post-publish reconciliation against Klaviyo realized metrics. Before that lands, someone needs to pin down whether `realization_factor = realized_revenue / predicted_p50` is the calibration target, or something else (ITT-style, intent-to-target). The plan defers this correctly, but flag in `docs/play_registry.md` that this decision is open.

---

## Scope Concerns

- **M4 is genuinely the largest milestone.** The plan acknowledges this. The proposed week budget (week 3–4 in the 6-week plan) is honest but tight given that fixture re-baseline (T4.9) is the long pole. **Recommend** splitting M4 into M4a (T4.1, T4.2, T4.3, T4.6, T4.8 — additive nan-ing + drop redundant BH entry; flag-gated) and M4b (T4.4, T4.5, T4.7, T4.10 — reclassification + combiner reroute + confidence collapse). M4a can ship and bake for a few days before M4b lands. This isn't a blocker but reduces single-PR review burden on the highest-stakes change.

- **PM Phase 1A mapping notes 14–18 days vs PM doc's 10.** This is honest and correct. Don't relitigate.

- **M10 cleanup explicitly forbids being one commit.** Good. Each T10.x as its own PR is the right discipline.

- **Out-of-scope items are correct.** No Klaviyo integration, no Bayesian intervals, no LLM narration of state-of-store. Good.

- **One scope addition I'd argue for**: a stub `recently_run_fatigue` write path in M9 (currently T5.5 reads, T9.1 writes only the post-run snapshot). For the gate to be useful in months 2+, the writer needs to record `(audience_id, play_id, anchor_date)` tuples that the reader can query. T9.1's schema is sufficient if `plays_recommended` includes `audience_id`. Verify.

- **One scope deletion I'd argue for**: T7.9 (`watching` section builder) is sequenced as part of M7. PM Q1 lists Watching as 1–4 signals, and PM acceptance criterion #2 says "Watching is optional in Phase 1A, required in 1B." Don't ship a half-baked Watching in M7 for the sake of fullness. Either ship it complete (with prior-month threshold references that require `recommended_history.json` reads — i.e., post-M9) or defer to a Phase 1B ticket. Right call: defer the multi-month-aware version to 1B; ship a single-run version in M7 only if it can populate from the current run alone without lying about thresholds.

---

## Required Changes Before Engineering Starts

Decisive list, ≤ 6.

1. **Specify `consistency_across_windows` semantics in T4.5.** One paragraph: pre-combination sign-agreement count, not a post-combination p-vote. Without this, `Strong` label silently re-imports the multi-window-as-evidence error.

2. **Add the materiality + class-aware-ranking interaction rule to T7.4.** Explicit: "If after materiality + cannibalization gating 0 measured/directional remain, demote to ABSTAIN_SOFT regardless of how many TARGETING plays remain." Closes the failure where a TARGETING-only briefing publishes as PUBLISH.

3. **Specify NaN-handling invariant in `evidence.py` (M4 new module).** "NaN p with `evidence_class != measured/directional` deterministically yields `confidence_label = Targeting`. NaN p with `evidence_class == measured` is an engine bug; raise." One-line invariant; prevents NaN from silently becoming `Emerging` via fallthrough.

4. **Lock M8 acceptance to "no `p50` single-number headline on targeting cards."** Add to T8.5 acceptance criteria: "rendered HTML for a targeting card contains a range chip but no standalone dollar number larger than the range chip text." This is the forcing function for PM Q9 #5/6.

5. **Expand T9.4 stub return shape to `{prior_overrides, evidence_thresholds, materiality_overrides}`.** Without this, the ML hook is a return-empty-dict placeholder.

6. **Split M4 into M4a (additive nan-ing) and M4b (combiner reroute + confidence collapse).** Reduces single-PR review burden on the highest-stakes milestone.

---

## Nice-to-Have Changes

- **G3 partial-window contamination flag.** Add to T5.2 if time permits; otherwise document as known limitation.
- **Defer T7.9 Watching builder to Phase 1B** unless single-run-aware version is fully specified.
- **Add explicit stat to receipts/debug.html (T9.5):** `evidence_class`, `p_internal`, observed effect, `n`, drivers. *Not* `_calculate_statistical_confidence`'s stepped number.
- **Document open question in `docs/play_registry.md`:** what `realization_factor` is (ratio? regression? ITT?). Defer to Phase 2 but flag now.
- **In T6.6 shadow-compare:** capture not just legacy_$ vs v2_p50 ratio, but also the per-play distribution across fixtures. If V2 p50 is uniformly 0.3x of legacy on heuristic plays across all fixtures, that's a story worth telling; if it's 0.1x on some and 0.9x on others, the priors registry needs more work before M8 flip.
- **Add a `tests/test_targeting_no_dollar_headline.py`** that grep-asserts the rendered targeting card HTML for the absence of any `$X,XXX` pattern outside the range chip element. Mechanical forcing function.

---

## Final Approved Architecture Shape

```
PIPELINE (V2, behind ENGINE_V2 until M8 default-on)

  load CSVs ─► load.py + validation.py
              │
              └─► anomaly.detect_anomalous_windows(df, anchor_date)
                    └─► data_quality_flags[]   # bfcm_overlap, refund_storm,
                                                #  test_order_anomaly,
                                                #  insufficient_clean_history

  features.aligned_windows ─► aligned[L7|L28|L56|L90]

  detect.detect_candidates(g, aligned, cfg, registry)
    │   uses audience_builders (pure customer-id sets)
    │   no statistics here
    └─► [Candidate(play_id, audience_ids, audience_size,
                   fraction_of_base, primary_window)]

  for measured/directional plays:
    stats.combine_multiwindow_statistics(per-window stats)
      └─► one p, one effect, one CI; consistency = pre-combination
          sign-agreement count (NOT post-combination p-vote)

  evidence.classify_evidence(candidate, registry)
    │   measured     := metric testable + p<α + consistency>=2 + n>=min_n
    │   directional  := metric testable + sign-consistent + (p>=α | n<min_n)
    │   targeting    := registry says targeting; measurement=null
    │   weak         := only audience exists
    │   blocked      := guardrail fired
    └─► evidence_class enum (typed, not string)

  guardrails (M5)
    │   gate_inventory       (days_of_cover >= 21 for SKU plays)
    │   gate_anomaly         (data_quality_flags -> abstain_hard)
    │   gate_cannibalization (overlap>50% demote; sum p50<=25% MR)
    │   gate_materiality     (scale-aware floor: max($5k,2%) <$1M;
    │                         max($10k,3%) $1-5M; max($25k,5%) >$5M)
    │   gate_recently_run    (audience_id+play_id <= 28d ago)
    └─► RejectedPlay with reason_code (11-code enum)

  sizing.size_play(candidate, registry, priors, scale, cold_start)
    │   audience x p_action x incremental_orders x AOV
    │   measured: p_action from store-observed effect
    │   targeting: p_action from priors.yaml range (p10/p90)
    │   cold_start | targeting+observational_prior => suppressed=true
    └─► RevenueRange { p10, p50, p90, source, drivers[], suppressed }

  decide.decide(...)
    │   rank: class-first (measured > directional > targeting),
    │         then p50 within class
    │   cap: top 3 recommendations
    │   require: >=1 measured/directional, else ABSTAIN_SOFT
    │   abstain_hard: any data_quality_flag
    │   considered: top 6 closest-to-firing rejected plays
    │   watching: 1-4 typed WatchedSignal
    └─► EngineRun { recommendations, considered, watching,
                    state_of_store, abstain, data_quality_flags,
                    scale, briefing_meta }

  output (M8, behind ENGINE_V2_OUTPUT)
    │   PUBLISH       => 3 sections + state-of-store + footer
    │   ABSTAIN_SOFT  => standard layout + "no measured" callout
    │                    + 0-2 targeting (suppressed/labeled)
    │   ABSTAIN_HARD  => "Data quality memo" template, no plays
    │   targeting cards: no p50 headline; range only; fixed disclaimer
    │   receipts/debug.html: evidence_class, p_internal, drivers
    │
    └─► briefing.html  (merchant-facing; never has p, q, CI, scores)

  outcome_log (M9)
    └─► data/recommended_history.json
        { store_id, run_id, anchor_date,
          plays_recommended[{play_id, audience_id, p50, evidence_class}],
          plays_rejected[{play_id, reason_code}] }

INVARIANTS (must hold across V2)
  - evidence_class=="targeting"   => measurement is null
  - evidence_class=="measured"    => measurement.observed_effect non-null
                                     AND consistency_across_windows>=2
                                     AND p_internal non-null
  - revenue_range.suppressed=true => renderer hides $; shows audience+AOV
  - sum(recommendations[].revenue_range.p50) <= 0.25 * monthly_revenue
  - 0 measured/directional in recommendations => ABSTAIN_SOFT, never PUBLISH
  - any data_quality_flag => ABSTAIN_HARD, recommendations=[]
  - briefing.html contains no "p =", "q =", "CI", "confidence_score",
    "final_score", or numeric confidence percentage

ML HOOKS (M9, populated but unused)
  - measurement.p_internal, ci_internal (persisted, never rendered)
  - revenue_range.drivers[] (named, source-classed inputs)
  - config/priors.yaml (versioned, source_class enum, applies_to)
  - recommended_history.json (per-store append log)
  - calibration_stub.load_realization_factors() returns
    { prior_overrides:{}, evidence_thresholds:{}, materiality_overrides:{} }

NON-GOALS (Phase 1)
  - Bayesian credible intervals
  - Hierarchical priors over fleet of stores
  - LLM-narrated state-of-store
  - Klaviyo / Shopify network calls
  - "Calibrated" claim in any merchant-facing copy
  - Uplift terminology (ATE, ITT, treatment effect) anywhere
  - "Learning" CONFIDENCE_MODE that relaxes thresholds
```
