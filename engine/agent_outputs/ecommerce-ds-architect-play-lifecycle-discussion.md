# DS Architect Discussion — Play Lifecycle and Campaign Memory

## Scientific Question

Two fused questions, each with a different epistemic floor:

1. **Within-engine lifecycle (cheap, partly answerable from CSV alone).** Given the engine has a deterministic record of what it recommended last run, what fraction of "is this play still a valid recommendation?" can be answered without knowing what the merchant actually did? Concretely: can audience cohort drift, signal persistence, and "did the underlying state change since we last said this" be reasoned about from CSVs alone?

2. **Between-engine-and-merchant lifecycle (expensive, mostly unanswerable from CSV alone).** Once the engine starts tracking what it said, can it ever conclude *"this play worked"* or *"this play failed"* without realized campaign data — or is that strictly an outside-the-engine claim that requires Klaviyo/Shopify or merchant declaration?

These questions collapse into one only if we accept a category error the PM doc almost makes: treating "I recommended this last month" as evidence about the play's effectiveness. It is not. It is evidence about the engine's behavior. Distinguishing those two — and being explicit about which one each artifact answers — is the load-bearing scientific decision in this discussion.

The non-trivial part: stateless re-recommendation is *not* a pure scientific failure. If the merchant did not run the play, the recommendation may be correctly the same. The failure is the engine pretending to be informed when it has no information. That is a presentation-layer decision-science issue, not a measurement issue. Solve it as such; do not import campaign-measurement vocabulary to compensate.

## Decision-Science Risks

Eight risks ordered by severity, with the type of risk noted (so they don't all get treated as the same kind of problem):

1. **Conflating "engine repetition" with "play effectiveness" (categorical).** The PM doc's "recommendation run, positive result" / "recommendation run, negative result" branches assume the engine can know. From CSV alone, it cannot. Any product-side language that says "your store did not see lift" without realized data is fabricated causality.

2. **Implicit-inference risk on `returning_customer_share` not moving (causal).** The PM's "if `returning_customer_share` did not move, infer the play probably wasn't run" branch is a confounded inference. The metric can fail to move because (a) merchant didn't run, (b) merchant ran with bad creative/timing, (c) merchant ran with great execution but the play has zero true effect at this store, (d) seasonal mix-shift overwhelmed any treatment effect, (e) measurement window is too short. Without merchant-declared "ran/not ran" or Klaviyo send data, those five worlds are observationally identical at the store level. The engine cannot sort them. Implicit inference here is the same epistemic mistake the engine just spent M0–M9 removing.

3. **Audience identity drift (measurement).** The "first-to-second-purchase" cohort is rolling. Same definition, different members month-to-month. If lifecycle keys on `audience.id` (a string label like `first_to_second_purchase`) the engine will treat semantically different audiences as the same. If it keys on a hashed customer-id set, two stores with stable cohorts look the same as two with churning cohorts and the engine cannot tell. The right key is *neither* of these alone.

4. **Multiple comparisons across time (statistical).** If lifecycle gates re-evaluate a play every month and re-run the same significance check, the type-I error rate inflates with the number of months. A play that was Emerging at month 1 may be Emerging at month 2 not because the signal strengthened but because the same data plus 30 days mostly preserves p-values. Repeat-recommendation logic must not double-count this as new evidence.

5. **Confirmation cherry-picking via `consistency_across_windows`.** With each new month, the L28/L56/L90 window edges shift. A play that was sign-stable across 3 windows in May can be sign-stable across 3 windows in June *because the windows overlap so heavily*. Scientific consistency-across-windows is not the same as consistency-across-runs.

6. **Missing-data masquerading as null effect (measurement).** "We had no signal in this metric this month" is not evidence the play didn't work. Without a campaign-execution record, it's evidence we don't know.

7. **Cohort lifetime confounded with lifecycle status (causal).** "Audience shrank, mostly already contacted" presumes the merchant contacted them. Without integration, audience shrinkage means people moved out of the cohort definition (e.g., made a second purchase, exited the inactive window) — which could be from organic behavior, the recommended play, an unrelated campaign, or anything else.

8. **Feedback-loop calibration risk (system-design).** If the engine reads its own log and uses it to gate future recommendations, and the log has a systematic bias (e.g., it under-records ABSTAIN_HARD runs because nothing is logged), the gating becomes self-reinforcing. M9's `recommended_history.json` is currently append-only with no negative-cases lane (rejected plays aren't given the same lifecycle treatment as recommended plays).

## What Local CSV Can Support

What the engine can scientifically know from CSV + its own M9 history, without Klaviyo / merchant declaration:

1. **What it recommended in prior runs.** Read-only fact about engine behavior.
2. **The audience definition for each prior recommendation.** Stored in `recommended_history.json`.
3. **Audience size and audience-id-label across runs.** Already in M9.
4. **The state-statistic the recommendation rested on, in prior windows.** E.g., last month's `returning_customer_share` value and current month's, *as state observations*, not as treatment effects.
5. **Whether the underlying signal that triggered the prior recommendation has decayed, persisted, strengthened, or flipped sign at the state level.** This is a description of the data, not of the campaign.
6. **Cohort-overlap between prior-month audience and current-month audience**, computable as a set comparison if customer IDs are anchored.
7. **Cohort-flow accounting at the segment level.** N customers entered the inactive cohort this month; N exited. This is descriptive, not causal.
8. **Anomalous-window flags across runs.** "We were in a refund storm last month; we are not now." Useful for explaining absence of recommendation, not its effectiveness.
9. **Engine-fatigue gating.** "This audience was the target of a recommendation in the last K runs" is purely a record of engine behavior.

What CSV can *describe* but cannot *attribute*: the same set as above, but as soon as you say "because of last month's send, X moved," you have left CSV-supportable territory. Movement at state level is an *occasion to update recommendation*, not evidence the play worked.

## What Requires Campaign / Klaviyo Results

What cannot be claimed without realized campaign data (Klaviyo sends, opens, clicks, conversion attribution; or Shopify post-purchase order attribution; or merchant-declared "ran/not ran/partial"):

1. **Whether the merchant ran any recommendation** (and which audiences were in the actual send list).
2. **Whether a recommended play "worked"** in any causal sense — lift, ATE, ITT, treatment effect.
3. **Realized-vs-predicted calibration** of revenue ranges. M9's calibration stub depends entirely on this.
4. **Per-store learning-rate.** "This store does not respond to winback" is a multi-run claim that requires multiple realized-vs-predicted observations.
5. **"Negative outcome" handling.** Cannot be done without realized data. The PM's "recommendation run, negative result" branch is *only* answerable post-integration or via merchant declaration.
6. **"Scale to adjacent cohort" recommendations conditional on success.** Logic that says "since this worked, expand to second-to-third" requires the success to be observed.
7. **Audience-fatigue at the customer level** (was this specific customer recently contacted?). Engine-fatigue at the audience-definition level is local; per-recipient fatigue is Klaviyo's domain.
8. **Holdout-aware reads.** A/B/holdout enables clean reads, and is a function of the publishing layer, not the recommendation layer.

This boundary is not soft. The engine should never present in merchant copy any claim that is on the right side of this list, regardless of how much memory we add locally.

## Repeat Recommendation Taxonomy

The PM's seven states are mostly product taxonomies. Reframed in decision-science vocabulary, the scientifically meaningful distinctions reduce to a smaller set, with sharper claims about what the engine can know:

| State | What this is, scientifically | Knowable from CSV alone? |
|---|---|---|
| **New play** | Engine has no record of recommending this play_id at this audience definition in prior runs. | Yes — read M9 history. |
| **Same play, same audience definition** | play_id + audience_id_label match a prior run. | Yes. |
| **Same play, same audience members (high overlap)** | Cohort set-overlap with prior recommendation > some threshold. | Yes if customer-id anchoring is preserved across runs. |
| **Same play, different audience members (low overlap)** | Cohort set-overlap < threshold; cohort definition stable but membership rolled. | Yes, same condition. |
| **Previously recommended, status unobserved** | Engine recommended in prior run; engine has no record of execution or outcome. *This is the default state for every prior recommendation in the local-only world.* | Yes (it is just absence-of-knowledge). |
| **In measurement window** | Strictly meaningless without (a) merchant-declared run-date and (b) defined window. CSV cannot infer either. | **No.** This state requires either merchant input or campaign integration. |
| **Ready for readout** | Same as above; it is the state where the measurement window has elapsed. | **No.** |
| **Repeat / scale / stop** | Outcome-conditional decisions. Without realized outcomes, none of these are valid claims. | **No.** |
| **Suppressed by engine fatigue** | Engine declines to re-recommend because it recommended this audience ≤ K runs ago. | Yes — pure engine-behavior gate. |

So: of the nine PM-implied states, **five are CSV-supportable** (all engine-behavior states), **four require integration or merchant declaration** (all outcome-conditional states). Designing memory contracts that imply the latter four exist in the local engine is a category error.

The lightweight version of this distinction:

- **Engine-behavior states** (recommended, suppressed-by-fatigue, audience-changed, signal-persisted) — local engine owns these. Phase 1 expressible.
- **Campaign-behavior states** (run, in-window, readout, scaled, stopped) — agentic product owns these. Local engine should have a *receiving slot* for them but should never *infer* them from CSV.

## Experimentation / Holdout Implications

Decision-science honest read: the local engine should not, today, make any claim that pre-supposes an experimental design. Specifically:

1. **No "lift" framing on repeat recommendations.** If month 2 surfaces the same play, do not phrase it as "we expect X% additional lift" — that is a treatment-effect claim with no experiment.

2. **Consistency-across-runs is not consistency-across-windows.** The latter is a within-run sign-agreement test on overlapping windows of the same data. The former would be a cross-run check that the metric persisted, which is mostly a function of data autocorrelation, not signal stability. Do not promote a play to "Strong" because it was Emerging two months in a row. The window-slide is too small.

3. **Holdout design is the agentic product's domain.** Once a Klaviyo agent publishes a play, holdout/A-B becomes a publish-time decision (sample selection, randomization unit, exposure window). The local engine cannot set that policy because it does not control delivery. What the local engine *can* do today: produce audience definitions in a form that is holdout-able (deterministic, stratifiable, with a stable id). M3 audience builders are mostly there; they are not yet stratification-aware.

4. **Pre-registration is the cheap-but-real win.** If the engine records "we recommended X, expected the proxy metric to move in direction D, by approximately some honest-range over W weeks" *at recommendation time*, then later — when realized data arrives — readout is well-defined because the prediction was pre-registered. Without pre-registration, every readout is a HARK (hypothesizing after results known) opportunity. M9's outcome log already has the right hooks (`measurement.observed_effect`, `primary_window`, `revenue_range`) but doesn't pre-register the *direction and minimum interesting size*. That is a small, defensible addition.

5. **"Negative outcome" requires, at minimum, a merchant-declared comparison.** Without holdout, "did not lift" is observed-versus-counterfactual, and the counterfactual is unobservable. The honest minimum for negative readout, even with merchant declaration: pre-registered direction + a structurally simple within-store counterfactual (e.g., prior-month baseline of the proxy metric). Even this is biased, but it is at least falsifiable.

6. **"Repeat for scale" recommendations are quasi-experimental at best.** Treat as exploratory, label as such. This is post-integration territory; local engine should not stub it.

## Minimum Memory Concepts, If Needed

This section is conditional. Whether the local engine should add memory at all is itself an open product decision (PM Q1; see reactions below). If it does, the *minimum* scientifically defensible set of concepts is:

1. **A stable `recommendation_lineage_id`** — keys on (play_id, audience_definition_id, store_id) but not on audience-member-set. So a rolling cohort with the same definition gets the same lineage across runs even though members change. This is the scientifically right primary key for "is this the same recommendation we made before?"

2. **An `audience_membership_overlap` field** — fraction of current audience that was in the prior-run audience for the same lineage. This separates rolling cohorts (low overlap, fresh customers) from static cohorts (high overlap, mostly same customers). This is what lets the engine distinguish PM scenarios "same play, mostly same audience" from "same play, mostly new audience" without claiming anything about runs.

3. **A `prior_state_snapshot`** — at recommendation time, the value of the proxy metric (e.g., `returning_customer_share` L28) is captured. On subsequent runs, the engine can describe state-level change ("this metric is X now, was Y at prior recommendation") without claiming attribution. This is descriptive, not causal.

4. **A `pre-registered_expectation`** — at recommendation time, the engine records (a) which proxy metric, (b) expected sign of movement, (c) the window over which it would expect to read out, (d) a minimum-interesting magnitude. This is the pre-registration anchor. Future agentic readout reads against this.

5. **A `recommendation_status_external`** — a slot for outside-the-engine truth (merchant-declared, Klaviyo-imported, agentic-monitor-imported). Default `null` / `unobserved`. The engine never *infers* values for this field. The schema exists so that when the agentic product or merchant-input lands, the field has somewhere to live without re-architecting.

6. **An `engine_fatigue_state`** — derived deterministically from prior recommendations in the lineage: `none` / `suppress_for_K_runs` / `eligible_again`. Pure engine-behavior gate; no campaign claim. This is what the M5 fatigue stub should mature into.

7. **A `decline_to_repeat_reason`** — when the engine elects not to re-recommend a play whose lineage was recently active, it should record why: `engine_fatigue` / `signal_decayed` / `cohort_overlap_with_active_audience` / `state_changed_so_play_no_longer_applies`. Each is local-knowable.

8. **A versioning fence on `audience_definition`** — if the M3 audience builder changes (different SQL/logic), prior lineage with the old definition should not be treated as comparable. Schema needs `audience_definition_version`.

What these concepts *do not* include and should not include in Phase 1:

- No `outcome` field with engine-inferred values.
- No `lift_estimate`, `realized_effect`, `treatment_effect`.
- No `play_calibration_factor` populated by the engine without realized data.
- No `repeat_recommendation_score` that pretends to combine prior-run signal with current data.

The principle: **memory carries facts about the engine and facts about the data, not inferences about the merchant or the campaign.**

## Claims Allowed Now

The local engine, today, may honestly claim any of the following:

1. "We recommended this play to this audience definition in [prior run]." (Engine-behavior fact.)
2. "The underlying signal that supported this recommendation has [persisted / strengthened / weakened / flipped sign]." (Data description.)
3. "This audience definition has [N] new entrants since the prior run; [M] customers from the prior run remain; [K] have left the cohort." (Set arithmetic.)
4. "We are not re-recommending this play this run because we recommended it [last run]." (Engine-fatigue gate.)
5. "We expect, if this play is run, that the proxy metric will move in direction [X] over window [W]." (Pre-registered prediction; honest framing.)
6. "We are still watching [metric]; if it crosses [threshold] we will [act / decline]." (Local watching logic — this is what M7 Watching is for.)
7. "Last run we considered this play; the rejection reason was [code]; the same reason holds this run." (Continuity in rejection list, which is the most underused product surface.)

Note that none of these requires Klaviyo, merchant declaration, or any inference about what the merchant did. They are continuity from the engine's own perspective.

## Claims Forbidden Until Campaign Results Exist

The local engine must not claim, today or after any local memory addition:

1. "Your store did not see lift from this play."
2. "This worked at your store."
3. "Don't repeat this; it didn't perform last time."
4. "Scale to this adjacent cohort because the first cohort responded."
5. "We're entering a measurement window for last month's send."
6. "Calibrated lift estimate from your store's prior outcomes."
7. "X% of recipients converted."
8. Any framing implying the engine knows whether the recommendation was acted on.
9. Any framing implying the prior recommendation produced (or failed to produce) a treatment effect.
10. "Based on what worked last month..." or "based on what didn't work last month..."

These are forbidden regardless of how the local engine stores memory. Adding storage does not unlock these claims; only data unlocks them.

## Risks Of Solving Too Early

If we build full lifecycle memory locally before integration:

1. **Schema rework when integration arrives.** A schema designed before any agent populates it will be wrong on first integration. The PM doc acknowledges this. The lightweight mitigation is to define only the fields the agentic product *cannot* infer for itself (engine-behavior facts) and leave the campaign-behavior fields to be added later.

2. **Pressure to fabricate outcome inference.** Once memory exists, the temptation to populate `recommendation_status_external` from CSV-derived heuristics will be strong. M9's outcome log already creates this risk — it is mitigated only by contract discipline. Scaling memory raises the temperature.

3. **False sense of relationship.** "We recommended this last month, here's what changed" reads to the merchant as "the engine remembers what you did." If the engine then, in another section, explains it cannot know what the merchant did, the inconsistency is jarring. Either the engine commits to "I don't know what you did" framing throughout, or it asks. Half-memory is worse than either pole.

4. **Self-reinforcing engine-fatigue gates.** If the engine suppresses repeat recommendations purely on engine-behavior, with no negative feedback from outcomes, it will systematically under-recommend valid repeats. Two stores with the same audience and the same merchant non-action will see the engine drop a valid play after K runs, indefinitely.

5. **Audience-identity coupling.** Lifecycle gating that keys on `audience_definition_id` will misfire any time M3 changes audience-builder logic. Every M3 builder change becomes a memory-migration. Versioning helps but does not eliminate the cost.

6. **Feedback loops between memory and decision-state classification.** Today's V2 classifies ABSTAIN_SOFT/HARD/PUBLISH per run. Adding memory raises the question of whether classification can change *because of memory* (e.g., demote to ABSTAIN_SOFT if all eligible plays are fatigue-suppressed). Once that path exists, debugging "why did the engine abstain on this run" becomes a multi-run problem.

7. **Locking-in pre-publication assumptions.** Pre-registered predictions stored before any realized data exist will eventually be marked correct or incorrect. If our pre-registration logic is biased (e.g., always predicts the proxy metric will move in the favorable direction), readout will be biased too. We have no calibration to know.

## Risks Of Waiting Too Long

If we keep the local engine fully stateless until integration:

1. **Month-2 trust failure on real merchants is the highest near-term cost.** PM is right about this. A merchant getting the same recommendation twice with no acknowledgement does perceive the engine as not reading itself.

2. **The M9 outcome log decays into a dead artifact.** Without any consumer, the schema drift will mismatch the eventual integration's needs. Better to have *one* small consumer (read-only, for continuity badging) than zero consumers.

3. **Pre-registration anchor never gets built.** Without the recommendation-time predictions stored, post-integration readout will be retrospective and HARK-prone. Adding pre-registration *now* (just persisting the expected direction and window) costs one schema field and meaningfully improves readout quality whenever it arrives.

4. **Audience-identity stability problem festers undiscovered.** The audience-id derivation in M3 has not been stress-tested across runs. We do not know whether two consecutive Beauty Brand runs produce the same `audience.id` for `first_to_second_purchase` with byte-identical data. If they don't, lifecycle is broken regardless of when we add it.

5. **Calibration stub remains a contract anchor with no contract partner.** The M9 stub returns `{}` and exists only to signal that ML is not yet present. If we don't even have the audience-stable lineage_id concept, calibration cannot key against anything when it eventually arrives.

6. **Rejection list cannot mature.** The most under-used wow surface (per Phase 5 reviewers) is the considered list. Without continuity ("considered last month for the same reason"), the list is also stateless and reads as a fresh dismissal each run. This is the lowest-cost memory consumer and the highest merchant-perception payoff.

The asymmetry: the cost of *not* adding lineage + state-snapshot + pre-registration is concrete and recurring (every monthly run that should have been continuous and isn't); the cost of adding it cautiously is mostly schema-design work, which we already paid for in M9.

## Reactions To PM Open Questions

**Reactions to the PM's 12 numbered questions, classified by who decides.**

**Q1. "Is recommendation lifecycle a Phase 1B addition, a Phase 2 feature, or post-integration?"** *Joint product + DS call, leaning DS.* The decision-science answer: a *thin* recommendation-lifecycle layer (lineage_id, prior-state-snapshot, pre-registration of expected direction, engine-fatigue gate) can be added *before* integration without claiming outcomes and without fabricating evidence. The product call is whether the merchant-perception cost of waiting outweighs the schema-rework risk of building early. From DS perspective: build the thin lineage layer; defer outcome lifecycle.

**Q2. "Audience identity stability across runs with current M3 audience builders."** *Pure DS call, and the most important one in the list.* This needs to be answered before any lifecycle work, period. Run M3 detect twice on the same Beauty Brand fixture with identical data and inspect whether `audience.id` is stable. Then run with one extra synthetic order and see if it churns. If audience-id is a hash of the customer-set, it will churn substantially with rolling cohorts; if it's a label like `first_to_second_purchase`, it is too coarse to distinguish meaningful audience changes. Neither alone is right. The right concept is a *lineage* (definition-stable) plus an overlap fraction (membership-aware). **Until we run the stability check, lifecycle suppression is built on sand.** This is a 1-day investigation, not a milestone — and it should happen first.

**Q3. "How should the engine model 'we recommended this last month' without lying about whether the merchant ran it?"** *DS call.* Option (a) — passive "previously recommended" badge with no behavior change — is the only honest minimum. Option (b) — active suppression — requires either merchant input or outcome file and is dishonest if applied without either. The structurally honest middle is: passive badge by default; active suppression only when a `recommendation_status_external` slot is populated (by merchant input, agentic monitor, or otherwise).

**Q4. "Right merchant-facing vocabulary for lifecycle states."** *Product call, DS confirms structural support.* Whatever vocabulary PM picks, the data structure must keep the underlying state and the merchant-facing label decoupled (same reason the V2 contract decoupled `evidence_class` from `confidence_label`). The internal states are: `new`, `recurring_lineage`, `engine_fatigue_active`, `signal_decayed`, `unobserved_status_external`. PM picks the strings the merchant sees.

**Q5. "Should the campaign-outcome seam be defined now even with no consumer?"** *Joint product + system-design call, leaning yes.* Decision-science argument for yes: defining the seam now constrains *what the engine cannot infer locally* (which is the more important contract). The schema does not need a consumer to do its job — it does its job by being the place where outside-the-engine truth lives, so that the engine's local code never tries to populate it from CSV. The schema is a forcing function against the implicit-inference risk in this entire discussion. So yes — define the seam now, leave it empty. **The seam is not a feature; it's a discipline.**

**Q6. "Slate framing — real engine output, static config, or out of scope?"** *Mostly product call.* DS read: a static playbook of "what every DTC store does" coupled with engine reads on each is a coverage map, not a measurement claim. It can be honest if every per-slot annotation is itself honest ("we did not detect signal here" / "we considered this; held for reason X" / "this audience is healthy at the state level"). But coverage maps are easy to drift toward generic content, which is exactly the failure mode the PM doc warned against. DS-side recommendation: don't do slate framing in Phase 1B. If it ships, it ships only when (a) every slot's annotation derives from a real per-store fact or (b) the absence of fact is itself surfaced ("we have no signal on abandoned-browse because that data isn't in your CSV"). That's a higher bar than the considered list.

**Q7. "Repeat-suppression keying — per-audience or per-play_id?"** *DS call.* Per-lineage (play_id × audience_definition_id × store_id), not per-play_id alone, and not per-customer-set. Per-play_id alone over-suppresses (cannot recommend winback to a different cohort if winback was recommended to any cohort). Per-customer-set under-suppresses (rolling cohort changes fragment lineage, so the same definition repeated across runs gets treated as new). Per-lineage with audience-overlap fraction as a secondary gate is the right key. The fatigue gate keying by play_id alone (M5 stub) is *wrong*; it should be lineage-keyed. This is a small fix and a real correctness improvement regardless of broader lifecycle scope.

**Q8. "Negative-outcome handling without integration: is it possible at all?"** *Pure DS call. Answer: no.* The local engine cannot conclude a play failed without realized data. It can only conclude (a) we recommended this; (b) the underlying state did not move favorably; (c) we don't know if the merchant ran it. The PM's "stop recommending a play that didn't work" requires a foundation we do not have. The acceptable degenerate case: if the engine has recommended the same lineage K runs in a row with no `recommendation_status_external` populated, *the engine should ask the merchant* — not stop. Asking is honest; stopping is silent fabrication of outcome.

**Q9. "Canonical memory: M9 history vs new outcomes file?"** *DS call.* They are different artifacts, not competing ones. `recommended_history.json` is engine-behavior log (what the engine said). `campaign_outcomes.json` is outside-world truth (what happened). They have different writers (engine vs agent/merchant), different trust levels (deterministic vs declared), different lifecycles (append-only vs upsertable), and different failure modes. Treating one as a superset of the other will produce category errors. Keep them separate; the calibration stub reads both.

**Q10. "Pricing-tier defense without lifecycle."** *Pure product call, not DS.* I will not collapse it.

**Q11. "Opportunity_context block for directional/targeting plays vs decline-to-quote."** *Joint, leaning DS.* This is the deepest contract question in the PM list. DS read: a typed `opportunity_context` block alongside `revenue_range`, with an explicit *parametric* form ("if you convert Y% of [audience] at [AOV], that contributes $Z"), is honest if and only if the parameter Y is presented as merchant-controlled and not engine-claimed. The current V2 declines to quote, which is austere but defensible. Adding a parametric opportunity sketch is *also* defensible if the form is rigid and forces the merchant to set the parameter — engine produces audience × AOV, merchant fills in conversion rate, page renders the result. That's not a forecast; that's a calculator the engine pre-populated.

The wrong way to do this: engine picks Y from a vertical prior and presents the result as a range. That re-imports the conversion-benchmark-as-causal-lift error this entire overhaul corrected. The right way: parametric, merchant-controlled, labelled "your-assumption-driven sketch," not engine-claimed.

For directional plays specifically, the case is stronger because the engine has a measured proxy metric and can size *from that*. For targeting plays, the case for decline-to-quote remains stronger because the engine has nothing measured at this store. Two different answers for the two evidence classes is consistent with the broader contract.

**Q12. "Multi-campaign reality: can CSV order data alone detect that a winback or post-purchase flow is already active?"** *Pure DS call, and the answer is: weakly, not reliably, and not at the play level.* Order data + customer cohorts can produce some signals consistent with active flows (e.g., a sharp drop in the "60+ day inactive" cohort over 2 weeks could be consistent with an active winback; an unusually high reorder rate at day 45 could be consistent with a replenishment flow). But *consistent with* is not detection. All these signals have organic explanations and would have huge false-positive rates. The honest answer is: the engine should not infer active campaigns from CSV. If the merchant tells us, we can use it; otherwise we operate in the dark. The PM's option (c) — "infer from order/UTM data what is running" — is an invitation to fabricate. Decline.

UTM data, if it is in the CSV (which Shopify exports rarely include cleanly), changes the answer somewhat — UTMs are merchant-created tags and reading them is descriptive, not inferential. But the analysis assumes a Shopify-only CSV, which mostly doesn't carry UTM. So: in scope of the current local engine, the answer is no.

## Open Questions For Product

1. **Is the engine's claim of "data-scientist replacement" compatible with monthly cadence and zero campaign visibility?** A real fractional CMO has both more frequent contact with the merchant and more visibility into what was sent. The engine has neither. This is not solvable by adding memory; it's solvable only by changing cadence or integrating. PM should decide whether the positioning needs to shift in the local-only era.

2. **Audience identity stability test — when do we run it, and what is the bar for "stable enough"?** This needs to happen before any lifecycle implementation. If the M3 builders churn audience-ids substantially with 30 days of new data, lifecycle work is premature regardless of which option PM picks.

3. **If we add the recommendation-lineage concept and the merchant sees "previously recommended" badges, does the PM accept that the engine cannot say more — i.e., cannot say "still recommended" or "no longer recommended" without a recommendation_status_external slot being populated?** This is the discipline test. If merchants will receive "previously recommended" badges and will demand "okay so should I run it again?" the answer must come from either merchant input or integration. PM should commit to which.

4. **Is the agentic product's recommendation-status writer in scope before any other agentic feature?** If yes, the local engine's outcomes seam has a fast path to a real consumer and lifecycle becomes meaningful. If no, the seam stays empty and we are in passive-badge-only territory indefinitely.

5. **Negative-outcome merchant ask UX cost.** The honest behavior in Q8 is: after K runs of the same lineage with no status declared, *ask the merchant*. PM should decide if a one-click ask per recommendation per month is acceptable to the local CSV→HTML workflow. If not, we cannot do honest lifecycle even with merchant declaration.

6. **Pre-registration display posture.** If the engine starts pre-registering "we expect proxy metric X to move by ≥ Y over W weeks," does that surface to the merchant as a commitment ("we expect X% lift") or stay internal? Surfacing it raises both trust ("the engine made a falsifiable claim") and risk ("the engine was wrong"). PM call.

7. **Calibration arrival horizon.** When does PM expect the first realized-vs-predicted data to come back through any path (Klaviyo agent, merchant declaration, manual)? If the answer is "within Phase 2," local lifecycle work is tight scope. If "no near-term plan," local lifecycle is half a relationship indefinitely and PM should decide whether half-relationship is enough at the price tier.

8. **Lineage versioning policy.** If M3's `first_to_second_purchase` builder logic changes in a future milestone, do prior recommendations under the old definition (a) get treated as a fresh lineage, (b) get migrated, or (c) get dropped from continuity logic? This is a small contract decision with downstream implications.

---

**Decision-science summary, no premature collapse:** there is one decision-science answer that is *forced* — the engine cannot claim outcomes without realized data, and any memory architecture must respect that. There are several decisions that are *not* forced and should be opened to product:

- Build a thin recommendation-lineage layer locally now (yes from DS, but only if the audience-stability test passes).
- Define the campaign-outcome seam without populating it (yes from DS — it is a discipline, not a feature).
- Add pre-registration of expected direction at recommendation time (yes from DS — small, defensible, payoff-asymmetric).
- Promote the considered list to lineage-aware continuity (yes from DS — highest merchant-perception payoff per unit of work).
- Move fatigue gate from per-play_id to per-lineage keying (yes from DS — correctness fix regardless of broader scope).
- Slate framing, opportunity-context block, merchant-input UX cost — these are PM calls, not DS calls. DS confirms structural feasibility under the contract; product owns the call.
