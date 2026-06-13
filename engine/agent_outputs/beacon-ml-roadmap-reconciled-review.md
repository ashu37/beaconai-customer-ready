# Beacon ML Roadmap Review

**Date:** 2026-05-09
**Reconciled by:** Claude Code (synthesis of `ecommerce-ds-architect-ml-roadmap-review.md` + `product-strategy-pm-ml-roadmap-review.md`)
**Inputs:** External Beacon Product Strategy research doc, post-6B Stop-Coding audit, Phase 6A final review, lifecycle reconciled doc, current frozen `engine_run.json` contract
**Status:** Critical evaluation only. No code, no tickets, no UI/copy work.

---

## Executive Verdict

**Current architecture is the correct foundation.**

Both reviewers independently converged: the load-bearing architecture pieces (evidence_class hierarchy, abstain state machine, typed reason codes, role-uniqueness invariant, forbidden-token contract, frozen JSON ↔ Agent Swarm boundary) are *exactly* the substrate an ML product needs. They are extremely hard to retrofit. Replacing the engine to "be more ML-native" would mean rebuilding the trust rails before getting to the models — exactly the failure mode M0–M6B just dismantled.

What is missing is not architecture. It is the **empirical substrate** the architecture was designed to consume: outcome ingestion, lineage stability, calibration consumer, per-merchant scoping. That substrate is what the post-6B audit calls "lifecycle." Both reviewers independently flagged that the lifecycle bundle is **the** minimum viable ML backbone, not a nice-to-have parallel to ML modeling work.

The research doc's order (timing → incrementality → affinity) is wrong on two axes:
- **DS axis:** the architecture-implied first ML insertion is **affinity** (lowest data-sufficiency bar; cleanest fit into Recommended Experiment; cheapest first proof of seam).
- **PM axis:** the merchant-visible first move is **memory + non-Beauty pinning + anomaly hygiene**, none of which are ML.

The unifying answer: **lifecycle loop ships first, then affinity as the first model-backed play, then survival/timing, then uplift as the calibration consumer.**

---

## What Beacon Already Solved

Both reviewers independently surfaced the same 5 structural moats:

1. **Honest abstain.** ABSTAIN_HARD/SOFT collapses recommendations to `[]` rather than fabricating a slate. Klaviyo's "1.43 expected orders" is the exact failure mode Beacon designed *out*.
2. **Forbidden-token trust contract.** No path for an upstream ML signal to leak `predicted lift X%` into rendered copy without tripping a test.
3. **Typed reason-code taxonomy + first-class Considered list.** Negative space is structured. ML systems generally have no language for "considered and held."
4. **Lineage-key concept exists** (even if [src/guardrails.py:604](../src/guardrails.py#L604) keys play_id only today). The frame `(play_id, audience_definition_id, store_id)` is conceptually present.
5. **Frozen JSON contract decoupled from copy.** ML signals can change underlying numerics without breaking the Agent Swarm. Most "AI insights" products are tightly coupled to their narrative layer.

**DS-side additions:**
- `EvidenceClass {measured, directional, targeting}` is already a promotion ladder. Survival → directional. Holdout-validated → measured. No new schema needed.
- `would_be_measured_by` enum is a pre-registration commitment that the rest of the category does not make.
- `decide()` is class-aware ranking with abstain semantics. ML signals slot in **behind** candidate registry — no need to touch ranking, gating, role-uniqueness, render.

**PM-side additions:**
- Recommended Experiment as a separate role with no projections is a unique middle ground (Triple Whale projects everything; Klaviyo projects nothing).
- Considered + Watching as first-class slate roles signals credibility no competitor has.

---

## What Still Needs To Be Invented

Reconciled list (DS + PM converge on items 1–5):

1. **Outcome ingestion** ([src/calibration_stub.py:22](../src/calibration_stub.py#L22) is contract-only). Hard blocker for any ML evolution.
2. **Audience-identity stability** unverified. Per lifecycle reconciled doc §"Key Questions" #1: no one has confirmed `audience.id` is byte-stable across runs. One-day investigation; gates everything downstream.
3. **Per-merchant history scoping** (B-4 in the audit). [src/outcome_log.py:285](../src/outcome_log.py#L285) writes to one shared file. Privacy hazard + correctness wall.
4. **Calibration consumer** — the socket exists, the wire doesn't. Trailing-window mean per `(play_id, vertical, store_id)` is the honest first version.
5. **Non-Beauty pinned fixture** (G-1). Today every JSON-contract regression test is Beauty-only.

**PM-only additions (commercial-visibility gaps):**
6. **Memory** across runs (engine reads each month as if it's the first month).
7. **Realized-outcome feedback** ("we said X last month, here's what we observe").

**DS-only additions (statistical defensibility gaps):**
8. **Overlap-window leakage** ([src/features.py:46](../src/features.py#L46), [src/stats.py:334](../src/stats.py#L334)) — L7⊂L28⊂L56⊂L90. Survival models layered on this inherit the same fallacy.
9. **FDR family scope undocumented** ([src/action_engine.py:1551](../src/action_engine.py#L1551)). Adding ML emitters multiplies candidate count without governing policy.
10. **Cross-merchant pooling** for sub-threshold-N merchants ($1–2M brands often fail BG/NBD's 1,000+ active customer bar; Cox PH needs hundreds of events per stratum). Has antitrust + multi-tenancy implications not yet scoped.

---

## Evaluation Of Proposed Phased Path

### Timing Models First

**DS verdict:** Wrong as the first step. Survival is the most sophisticated, but the architecture-fit case for going first is weakest: needs cleanest data, most events per stratum, and benefits from already-running outcome ingestion. Architecture-implied first insertion is affinity.

**PM verdict:** Correct *as the first model-backed play*, but wrong as the first product move. Replenishment timing is genuinely the highest-leverage retention mechanic in consumables — but only legible to the merchant if Beacon also has memory. Without lifecycle, the timing prediction lands as "an alert, like Klaviyo" rather than "a tool that learns."

**Reconciled:** Timing is the right *flagship model-backed play*, but it ships **third** in product order — after lifecycle + non-Beauty pinning. Within ML axis specifically, timing ships **second**, after affinity demonstrates the seam.

### Incrementality Second

**DS verdict:** Wrong placement. Uplift is not a peer to survival/affinity — it's the **calibration consumer**, the promotion mechanism from directional → measured. It can't ship until outcome rows have accumulated from prior emitters. Belongs *after* lifecycle + first ML emitter, not parallel to them.

**PM verdict:** Correct as the doc's actual moat, but mis-scoped. Holdout/incrementality is not a separate ML system — it's the measurement axis the entire roadmap should compound around. Pick **measurement** as the primary roadmap axis; everything else hangs off it.

**Reconciled:** Both agents agree incrementality is the correct compounding axis but disagree with the doc on when it lands. Reframed: the **holdout/lifecycle infrastructure** ships as substrate (call it "P0 substrate"), then uplift *modeling* on top of that substrate ships **after** at least one ML emitter (affinity) has accumulated outcome rows.

### Affinity/Bundles Third

**DS verdict:** Wrong placement. Affinity is the architectural-fit *first* ML insertion: lowest data-sufficiency bar, cleanest fit into Recommended Experiment (already targeting-only, send-and-measure), cheapest first proof that an ML signal flows through the existing pipes without contract change.

**PM verdict:** Correctly placed as lower commercial urgency than churn/winback. Bundles deliver visible AOV lift and are easy to demo, but the doc's $5M-persona WTP shift is gated more by uplift-scored winback than by bundles.

**Reconciled:** **Affinity ships first within the ML axis** (DS argument: cheapest seam test). It ships as a `targeting`-class candidate to Recommended Experiment and uses the existing send-and-measure framing — no new contract surface. Bundles (combinatorial optimization on top of affinity) come later.

---

## Best First ML Capabilities

Reconciled order — what to build, in sequence, after lifecycle substrate ships:

1. **FP-growth + ALS affinity emitter** behind `bestseller_amplify` and a future `routine_builder` replacement. Stays `targeting` until calibration matures. Lowest-friction first ML insertion. Tests the seam.
2. **Replenishment timing** via discrete-time survival (gradient-boosted survival trees on per-customer hazard). Outputs per-audience expected-reorder-date with CI. Publishes as `directional` with `would_be_measured_by = REPEAT_PURCHASE_IN_30D`. PM caveat: scope as "profile property the merchant uses," not "predicted ITE the engine takes credit for."
3. **Calibration option-1 (trailing-window mean per `(play_id, vertical, store_id)`)**. Once K=3 outcome rows exist, override prior baseline with observed mean. This is the visible memory layer that PM identified as the largest perceived-value lever.
4. **Subscription churn** via Cox PH / DeepSurv — *only after* Recharge/Bold/Skio integration; properly `REQUIRES_INTEGRATION` until then.
5. **Uplift / T-learner** as calibration consumer for promotion directional → measured — *only after* K outcome rows per cohort have accumulated. PM warning: until K is large, CIs will be wide; hiding wide CIs violates trust contract; adopting before K is large is the trap.
6. **Discount elasticity (double-ML)** for `discount_hygiene` permanent promotion to directional/measured. PM note: this is the most defensible Recommended Now card in the slate because every other tool in the stack still recommends discounts blindly.

---

## Minimum Viable ML Backbone

**Both reviewers converge unambiguously: the MVP backbone is the lifecycle loop, not a model.** The post-6B audit §5 already specified it. Restated as the ML-substrate it actually is:

- **L-A:** Per-merchant history scoping (`data/<store_id>/recommended_history.json`)
- **L-B:** Audience-identity stability investigation (one-day spike, gates everything)
- **L-C:** `compute_realized_outcome` for `REPEAT_PURCHASE_IN_30D` (the only locally honest enum)
- **L-D #1:** Calibration consumer option-1 (trailing-window mean per `(play_id, vertical, store_id)`)
- **L-E:** Pre-registered expectation written at recommendation time (`expected_direction`, `min_interesting_effect_size`)
- **L-F:** `recommended_history` schema v2 with append-only outcome rows
- **L-G:** Two-run integration test as acceptance bar

This unlocks **every** future model simultaneously. Survival, affinity, uplift, churn — none can produce a defensible `measured` claim without it. With it, each new ML emitter is a 2–4 week ticket, not a platform rewrite.

**Why this is the right unifier:** the founder's intuition ("2–3 plays at a time, not a giant ML rewrite") is correctly resisting platform expansion. But the prerequisite for *any* "play at a time" approach is the substrate that lets a play graduate evidence_class based on observation. Without lifecycle, every new model is unfalsifiable — exactly the failure mode the engine just dismantled.

---

## Biggest Technical Risks

DS-led, PM-confirmed:

1. **Audience-identity instability.** If `audience.id` churns across runs, lineage-keyed calibration is impossible, every "we recommended this last month" claim is wrong, the entire lifecycle loop is built on sand. Test before any other ML investment.
2. **Single-merchant N below model thresholds.** BG/NBD needs 1,000+ active customers; Cox PH needs hundreds of events per stratum. $1–2M Beauty brands won't clear those thresholds per stratum. Cross-merchant pooling has antitrust/privacy + multi-tenancy implications not yet scoped.
3. **Outcome ingestion gap → enum cap.** `would_be_measured_by` has only one locally computable enum (`REPEAT_PURCHASE_IN_30D`); the others require Klaviyo / control groups. Caps how many plays can ever graduate to `measured`.
4. **Calibration before lifecycle is back-to-front.** Adding survival models before the calibration consumer exists means models produce predictions the system has no path to validate.
5. **FDR + window-overlap unresolved.** Adding ML emitters without resolving family scope and window independence multiplies false positives. External statistical reviewer catches this immediately; trust contract collapses publicly.
6. **Pricing tier coupling.** Doc proposes $1.5K–$8K/mo tied to "% of measured incremental revenue." Without holdout framework + outcome ingestion operational across paying merchants, this pricing structure is unlandable.

---

## Biggest Product Risks

PM-led, DS-confirmed:

1. **Trust collapse from "+$38K predicted incremental revenue" framing** (the research doc's literal language). Directly violates frozen trust contract. Adopting it regresses every gain from M0–M6B. **Reject explicitly.** The honest version is post-hoc ("we held out 5%; observed delta vs control"), not predictive.
2. **Demo-vs-production gap on non-supported verticals.** Beauty fixture is pinned and honest. Supplements has partial constants but no pinned slate. **Apparel/food/home/wellness are out of scope permanently — engine must HARD REFUSE these with `VERTICAL_NOT_SUPPORTED`, not absorb them via `mixed` fallback.** Today's silent fallback is a Beta-blocker: a non-supported merchant gets a slate built on beauty+supplements priors that looks legitimate but is fabricated.
3. **Anemic-output ceiling.** ~3 measured plays for healthy stores caps perceived value before any model is added. Adding a 4th model-backed play does not solve this if the structural pattern stays "few measured plays per healthy run." Solve by making existing measured plays fire more reliably and by giving lifecycle weight to Considered/Watching cards over time — not by adding more plays.
4. **Overpromise on "AI growth team" without lifecycle.** Without memory + calibration, the pitch is dishonest. Pitching it anyway burns the credibility moat the slate architecture earned.
5. **Model-merchant data mismatch.** Doc's BG/NBD assumes non-contractual purchases; supplement subscription brands violate this. Defer model commitment until non-Beauty fixtures expose actual data envelopes.
6. **Cross-tenant privacy hazard.** Today `data/recommended_history.json` is shared. Two pilot merchants on the same machine = data leak. More urgent than its tier suggests.
7. **Klaviyo publish gap.** "AI growth team" implies the engine acts. Today it briefs. Until the publish loop closes, every merchant manually copies segments and writes the campaign. Massive friction the demo doesn't show.

---

## Biggest Strategic Moats

Reconciled (DS-named, PM-confirmed):

1. **The abstain-honest, typed-evidence trust contract.** Stronger than the doc's claimed "incrementality" moat. Klaviyo/Triple Whale/Lifetimely *could* add holdouts — they will eventually. They will **not** adopt abstain-honest output because it is commercially painful. Klaviyo will never tell a $2M brand "we have nothing to recommend this month." Postures are harder to copy than features.
2. **Lineage-keyed memory** — once L-A through L-G ship, Beacon has per-merchant calibration that no horizontal vendor can replicate without per-tenant model state.
3. **Measurement-design discipline** — `would_be_measured_by` enum is a pre-registration commitment the rest of the category does not make.
4. **Frozen JSON ↔ Agent Swarm boundary** — Beacon can swap LLM copy generators while preserving evidence integrity. Architectural discipline that compounds.
5. **Incrementality framework** is the *visible* differentiator. Trust contract is the *defensible* one. Both are real moats; they operate on different timescales.

---

## What Competitors Still Do Better

PM-led:
- **Klaviyo:** flow execution, segment activation, send infrastructure. Beacon will not out-build this. The right relationship is publish-into-Klaviyo, not replace.
- **Triple Whale:** attribution dashboards, daily-glance metrics, ad-platform integration. Different surface; not where Beacon competes.
- **Lifetimely:** cohort LTV reporting, RFM views. Tells you what's true; doesn't tell you what to do. Beacon's structural advantage is "what to do" but Lifetimely's reporting polish on the "what's true" side is real.
- **Klaviyo's Predictive Analytics:** exists, has data scale, retrains weekly. Don't dismiss it. Beacon's differentiation is global-vs-personalized + causal/holdout layer + abstain-honest framing — not "Klaviyo has nothing."

---

## What Beacon Could Become Best-In-Class At

Reconciled:

1. **Honest measurement of incremental impact** for $1–10M consumable DTC brands (uplift + holdout, framed as receipts not projections).
2. **Per-merchant calibrated recommendations** that demonstrably improve over time as the engine accumulates outcome rows. The "tool that remembers" position no horizontal vendor can structurally hold.
3. **Trust-contract discipline** — saying "we don't know" honestly when the data doesn't support a recommendation. Sophisticated buyer signal.
4. **Replenishment-timing intelligence** for consumables with per-SKU expected-reorder-date pushed as a Klaviyo profile property.
5. **Considered-list density** (typed reason codes for plays held back) as a credibility surface no competitor offers.

---

## What NOT To Build Yet

Both reviewers explicitly reject:

- **Quiz contextual bandits** (research doc P2; should be P4 — quiz-heavy brands are <15% of segment, bandit infra is months for narrow applicability)
- **VIP/loyalty tier optimization** (rules-based is fine for now)
- **Launch targeting** (every brand thinks this is hard; few will pay separately)
- **BG/NBD-based LTV claims for subscription brands** (model-data mismatch)
- **Quiz funnel personalization before P4**
- **"Predicted incremental revenue +$X" framing** (violates trust contract)
- **Model-name-led positioning** (T-learner, BG/NBD, Cox PH belong in engineering blog, not slate)
- **$8K/mo pricing tier within first 12 months** (price requires evidence requires lifecycle running 6+ months)
- **Hierarchical cross-merchant pooling** without legal/privacy review
- **Klaviyo publish automation** before the recommendations are demonstrably good (automation of bad recommendations destroys trust faster than no automation)
- **Survival models before outcome ingestion exists** (predictions with no validation path)
- **Uplift modeling before K outcome rows accumulate** (wide CIs that have to be hidden, violating trust contract)
- **Replacing the engine architecture** to "be more ML-native" (rebuilds trust rails for no gain)

---

## Recommended 12–18 Month Roadmap

Reconciled (PM commercial order × DS technical fit):

### Months 0–3: Substrate (no new ML)
- **Beta blockers from post-6B audit** (anomaly auto-register, Considered typed payload, hardcoded-fallback regression test, per-merchant history scoping, Berkson invariant test). Required for first 5 paid Beauty merchants.
- **Audience-identity stability investigation** (L-B, one-day spike).
- **Lifecycle loop on `REPEAT_PURCHASE_IN_30D`** (L-A, L-C, L-D #1, L-E, L-F, L-G). Single largest perceived-value lever per engineering hour.

### Months 3–6: Vertical expansion + measurement substrate
- **Pin a non-Beauty slate fixture** (supplements first; G-1 from audit). Commercial gating ticket. Surfaces real bug list.
- **Address the bug list** (empty_bottle parser, supplements priors, Phase 4.2 reclassifications, overlap-window leakage if external review pressure arrives).
- **Holdout/incrementality framework** as production-grade infrastructure (5–10% holdout per Recommended Experiment, observed delta vs control with CI, post-hoc only).

### Months 6–9: First model-backed play
- **Affinity emitter** (FP-growth + ALS) behind Recommended Experiment. Lowest-friction first ML insertion. Stays `targeting` until calibration matures. Tests the seam.
- Calibration option-1 begins accumulating outcome rows.

### Months 9–12: Replenishment timing
- **Survival emitter** (gradient-boosted hazard) for replenishment timing. Publishes as `directional` with `REPEAT_PURCHASE_IN_30D`. Scoped narrowly: "profile property the merchant uses."
- Klaviyo publish seam (engine + Agent Swarm side; engine emits typed payload only).

### Months 12–18: Promotion mechanism + churn defense
- **Uplift / T-learner** as calibration consumer once K outcome rows per cohort have accumulated. Promotes affinity + replenishment plays from `directional` to `measured`.
- **Subscription churn defense** (Cox PH / DeepSurv) — only if Recharge/Bold/Skio integration lands; otherwise `REQUIRES_INTEGRATION`.
- **Discount elasticity** (double-ML) for `discount_hygiene` permanent promotion.
- Mixed-vertical pinned fixture (the only remaining vertical in scope; mixed = beauty+supplements blend).

### Deferred to year 2+
- Bundle combinatorial optimization
- Quiz contextual bandits
- VIP tier optimization
- Hierarchical cross-merchant pooling
- $8K pricing tier

---

## Phase 6B vs Future Phases

**Phase 6B closes with the post-6B audit's Beta-blocker list** (5 items: anomaly auto-register, Considered typed payload, hardcoded-fallback regression test, per-merchant history scoping, Berkson invariant test). These are correctness + trust hygiene fixes within the frozen contract, not new scope. **Phase 6B does NOT include any new ML.** Phase 6B does NOT include lifecycle ingestion build.

**Phase 7 (proposed name: "Lifecycle Substrate")** ships the audit's L-A through L-G as one milestone. This is the smallest-honest-form learning loop. No new models. Single largest perceived-value jump in the entire 18-month roadmap.

**Phase 8 (proposed name: "Vertical Expansion + Measurement")** pins the supplements fixture, addresses the surfaced bug list, and ships the holdout/incrementality framework as production infrastructure. No new ML emitters yet — the framework is the substrate that ML emitters will plug into.

**Phase 9 (proposed name: "First ML Emitter")** ships the affinity model behind Recommended Experiment. Tests the architectural seam. Calibration begins accumulating outcome rows.

**Phase 10+** as in the 12–18 month roadmap above.

---

## Final Recommendation

**Direction:** Evolve, do not rewrite. The current architecture is the right foundation. The research doc's plays are mostly correct. The phasing the doc proposes is wrong on both technical and commercial axes.

**Sequence:**
1. Close Phase 6B with the audit's Beta blockers.
2. Ship lifecycle substrate (L-A through L-G) before any new ML model. This is non-negotiable.
3. Pin a non-Beauty fixture before claiming to support non-Beauty merchants. Commercial gating, not engineering.
4. Build affinity as the first ML emitter (architecture-fit argument from DS).
5. Build replenishment timing as the flagship merchant-facing model-backed play (commercial argument from PM).
6. Build uplift as the calibration consumer (not as a parallel ML system).
7. Defer everything else — including most of the research doc's P2/P3 list — past month 18.

**Trust constraints preserved throughout:** no fabricated p/confidence/projections; evidence_class hierarchy intact; abstain-honest output unchanged; forbidden-token contract intact; engine emits typed structure only; Agent Swarm owns rendered copy.

**The one phrase to ban from any merchant-facing surface:** "predicted incremental revenue $X." The honest version is "observed delta vs holdout: $X (CI: ...)." This requires the lifecycle loop to exist. Until it does, no incrementality language ships.

**The one moat both reviewers want amplified:** the abstain-honest, typed-evidence trust contract is the structural defense. Incrementality is the visible defense. Build the visible one; never compromise the structural one.

---

## Inventory: Pending Work vs Intelligence-Layer Enhancements

A reconciled inventory of every action item surfaced across the audit + this review, partitioned into the two buckets the founder asked for.

### Bucket A: Pending Work (Fix what exists; Beta + GA hygiene)
*From the post-6B audit. Required for trust + addressable market. Not new ML.*

**Beta blockers (Beauty pilot):**
- B-1: AnomalousWindow auto-registration → ABSTAIN routing
- B-2: Considered-card typed evidence_snapshot under ABSTAIN_SOFT (reason-code fan-out + internal measurement mirror)
- B-3: Hardcoded-fallback regression test on engine_run.json
- B-4: Per-merchant history scoping + lineage-keyed fatigue (correctness now, behavior later)
- B-5: Berkson-class invariant test
- B-6: Multi-window combiner universality on V2 path

**GA blockers (non-Beauty):**
- G-1: Pin synthetic supplements slate fixture (commercial gating)
- G-2: `empty_bottle` parser unit-coherence (vertical-dispatched)
- G-3: Supplements priors hardening + `mixed` semantic formalization (NOT expansion to other verticals; engine scope hard-locked at {beauty, supplements, mixed})
- G-4: Phase 4.2: reclassify `subscription_nudge` and `routine_builder` permanently as targeting
- G-5: FDR family scope documented
- G-6: Overlap-window leakage L28/L56/L90 fix
- G-7: Cross-run byte-identical determinism CI
- G-8: Cannibalization-overlap key existence test

**M10 prerequisites:** as listed in audit §4.

### Bucket B: Intelligence-Layer Enhancements (Build what's new; ML evolution)
*From this reconciled review. Builds Beacon's data-science capability.*

**ML substrate (must land first — both reviewers converge):**
- L-A: Per-merchant history path resolution (overlaps with B-4)
- L-B: Audience-identity stability investigation (one-day spike; gates everything else in Bucket B)
- L-C: `compute_realized_outcome` for `REPEAT_PURCHASE_IN_30D`
- L-D #1: Calibration consumer option-1 (trailing-window mean)
- L-E: Pre-registered expectation at recommendation time
- L-F: `recommended_history` schema v2 with append-only outcome rows
- L-G: Two-run integration test (acceptance bar for substrate)
- L-H: Klaviyo / Shopify outcome ingestion seam contract (engine reads if present, never writes)

**ML emitters (in priority order, after substrate):**
- I-1: FP-growth + ALS affinity emitter behind Recommended Experiment
- I-2: Discrete-time survival / replenishment timing emitter
- I-3: Subscription churn (Cox PH / DeepSurv) — gated on Recharge/Bold/Skio integration
- I-4: Uplift / T-learner as calibration consumer (promotes directional → measured)
- I-5: Discount elasticity (double-ML) for `discount_hygiene` permanent promotion
- I-6: BG/NBD + Gamma-Gamma LTV as RevenueRange sizing input (one-time-buyer cards only)

**ML infrastructure (as needed, deferred):**
- I-7: FDR family scope policy (overlaps with G-5)
- I-8: Window-overlap correction in combiner (overlaps with G-6)
- I-9: Hierarchical / cross-merchant pooling (gated on legal + privacy review)
- I-10: Reproducibility / cross-run determinism (overlaps with G-7)

**Explicit deferrals (do not build yet):**
- Quiz contextual bandits
- VIP/loyalty tier optimization
- Launch targeting model
- Bundle combinatorial optimization
- Stockout prediction / inventory-driven marketing
- Cause/limited-edition → core conversion

### Sequencing summary

```
Phase 6B close      → Bucket A Beta blockers (B-1 through B-6)
Phase 7: Substrate  → Bucket B substrate (L-A through L-G)
Phase 8: Verticals  → Bucket A GA blockers (G-1 through G-4)
Phase 9: First ML   → Bucket B emitter I-1 (affinity)
Phase 10+: ML graph → Bucket B emitters I-2 → I-4 → I-5 → I-3, plus G-5/G-6/G-7 hardening
```

The two buckets are not independent. Bucket B is unbuildable without Bucket A's correctness fixes (especially per-merchant scoping + audience-identity stability). The founder's instinct that "intelligence" and "engineering hygiene" feel like two different programs is correct — but they share a critical path.

---

---

# ADDENDUM: Campaign Memory Substrate (Phase 7 Reframing)

**Added:** 2026-05-09 (post initial reconciliation)
**Trigger:** Founder reframed the next implementation phase explicitly: Beacon evolves from "recommendation engine" → **"campaign memory and learning system."** The engine becomes one consumer of memory; it is not the owner. Other consumers: Agent Swarm (copy generation), monitoring workers, merchant UI (historical review), future calibration consumer.

**Hard constraints reaffirmed:** No distributed ML platform. No massive-scale design yet. No engine architecture rewrite. No coupling of lifecycle state to renderer/UI logic. Engine is NOT the owner of campaign truth. Frozen JSON contract preserved. Trust contract preserved (no fabricated p/CI/projections, no "predicted lift").

---

## Why this reframing is correct (PM)

> "The 'recommendation engine' framing was always a trap. Every analytics-adjacent vendor at $1–10M Beauty/Supplements is a 'recommendation engine' — Klaviyo Predictive, Triple Whale, Lifetimely, Black Crow, Repeat. The category is overcrowded and undifferentiated because the unit of value is a single output (a list, a score, an alert)... Reframing Beacon as **the campaign memory and learning system** changes the unit of value from 'this month's slate' to 'the per-merchant evidence base that every consumer (engine, swarm, monitor, UI) reads from.'"

**Commercial unlock:**
- $2M persona: WTP $200 → $800 unlocked by "the thing that remembers what we tried." Largest perceived-intelligence jump per engineering hour.
- $5M persona: WTP $800 → $2K+ unlocked by the *receipts* posture — "we said X in March, here is what we observed in April, here is how we updated for May."

**Where it overreaches:**
- "Memory" is a loaded merchant word. Merchants will hear "memory" and assume the engine remembers what they *did* (sent in Klaviyo). It only remembers what *it recommended* and what *it can locally observe in CSV* (REPEAT_PURCHASE_IN_30D today). Police this distinction in copy.
- It moves Beacon closer to "AI growth team" only AFTER L-A through L-G ship. Pitching the reframing before substrate is live makes the overpromise *worse* because you've now publicly anchored on "learning system."
- Failure mode: substrate work expands to "let's design event sourcing properly." Hold the line at the seven primitives. Do not let "campaign execution lineage" pull in Klaviyo poll workers prematurely.

---

## Substrate Architecture (DS spec)

### Storage model: SQLite, single file per merchant

`data/<store_id>/memory.db` with one event-sourced `events` table + a small number of materialized read-views. Defended against alternatives:

- **Not JSONL:** every "what did we recommend last 6 months" UI query becomes O(N) full-file parse; brittle to concurrent writers.
- **Not per-event-type files:** fragments lineage join across files; consumer reinvents joins.
- **Not Postgres:** violates "no distributed platform" constraint; multi-tenant SaaS is months out.
- **SQLite gives:** single-file portability (matches local-CSV ergonomics), WAL-mode concurrency, free indexes for lineage key, free SQL for read-views, schema migrations via `PRAGMA user_version`, zero ops. Smallest defensible thing that survives until Postgres is needed.

`recommended_history.json` remains as a legacy mirror for one phase, then retires. `engine_run.json` remains the frozen per-run artifact, **referenced by path** from the `recommendation_emitted` event row.

### Stable ID shape

```
lineage_id = sha1(store_id | play_id | audience_definition_id | audience_definition_version)
```

40-char hex string, computed deterministically once at recommendation time, never recomputed downstream.

**Defense:**
- NOT `(store_id, play_id, audience_definition_id, anchor_date)` — including anchor_date defeats the purpose; lineage must survive across runs.
- NOT `play_id` alone — current [src/guardrails.py:604](../src/guardrails.py#L604) bug; over-suppresses across distinct audiences.
- NOT customer-id-set hash — cohorts roll; under-suppresses MoM; privacy-hostile.
- `audience_definition_version` is non-negotiable: if M3 builders change ("now we include orders from gift cards"), prior version's outcome rows are no longer comparable. Version bumps create a new lineage_id by construction.

### Event schema

```sql
events (
  event_id            TEXT PRIMARY KEY,    -- ulid; sortable + unique
  event_type          TEXT NOT NULL,
  event_version       INT  NOT NULL,       -- per-event-type schema version, additive only
  occurred_at         TEXT NOT NULL,       -- ISO-8601 UTC
  ingested_at         TEXT NOT NULL,
  store_id            TEXT NOT NULL,
  lineage_id          TEXT,                -- nullable for store-level events
  run_id              TEXT,                -- ties back to engine_run.json snapshot
  source              TEXT NOT NULL,       -- "engine" | "agent_swarm" | "monitor" | "merchant_ui" | "calibration"
  payload_json        TEXT NOT NULL
)
INDEX (store_id, lineage_id, occurred_at)
INDEX (store_id, event_type, occurred_at)
```

**v1 event types (single-writer-per-type discipline):**

| Event | Writer | Payload (high-level) |
|---|---|---|
| `recommendation_emitted` | engine only | lineage_id, evidence_class, would_be_measured_by, audience_size, internal Measurement diagnostics, revenue_range, pre-registered expectation `{expected_direction, min_interesting_effect_size, expected_observation_window_days}`, snapshot path |
| `recommendation_considered` | engine only | RejectedPlay with reason_code, held_reason_detail, typed evidence_snapshot |
| `campaign_sent` | Agent Swarm / merchant_ui / manual_import (NEVER engine) | lineage_id, klaviyo_campaign_id (or null), sent_at, audience_size_at_send, holdout_size, channel |
| `outcome_observed` | monitor workers only | lineage_id, would_be_measured_by enum, observed_value, baseline_value, baseline_method, computed_by_function_version, observation_window |
| `calibration_updated` | calibration consumer only | lineage_id_pattern (partial key), prior_overrides_delta, evidence_thresholds_delta, materiality_overrides_delta, K (rollup count), method_version |

**Versioning policy:** strictly additive within an event_type. New optional fields land via `event_version++`. Field removals forbidden. Field semantics changes require a new event_type.

### Read contracts (the public API)

Three SQL views in `src/memory/views.sql`. Consumers query views, never raw events. View definitions ship in version control. New views are additive.

| View | Consumed by |
|---|---|
| `v_lineage_timeline(lineage_id)` | merchant UI "what happened to this recommendation" panel; Agent Swarm continuity narration |
| `v_calibration_state(store_id, vertical)` | engine (priors); future calibration consumer |
| `v_open_recommendations(store_id, as_of)` | monitor worker polling; merchant "still pending" UI view |

### How the engine reads from memory

**The engine reads exactly one derived view: `v_calibration_state`.** Built on top of `calibration_updated` events by replaying the latest non-superseded calibration row per `(play_id, vertical, store_id)` partition. This is the seam `calibration_stub.load_realization_factors` already declares.

**The engine does NOT read its own past `recommendation_emitted` events as state.** That coupling is what makes the engine the owner of memory; it must not own memory. The fatigue gate apparent exception is handled by reading `v_lineage_recent_emissions(lineage_id, count_in_last_28d)` — a function of the events log, not state owned by the engine.

---

## Merchant-Visible Value (PM)

Three honest visibility surfaces, in priority. **Substrate by itself is invisible — JSON files, lineage keys, append-only outcome rows. The merchant does not buy substrate. The merchant buys what the substrate makes possible.**

**1. The "previously recommended" badge** (smallest UI surface, biggest perception jump, ships in Phase 7):
Agent Swarm reads `v_lineage_timeline` for the lineage. On any card whose lineage matches a prior run, swarm renders: *"Recommended in March 2026; same audience definition; reason held: AUDIENCE_TOO_SMALL."* No projection, no claim. Just acknowledgement that the engine saw itself.

**2. The "what we observed" line** (the receipts posture, ships in Phase 8 + ~3 months of accumulation):
After K=3 outcome rows for a `(play_id, vertical, store_id)`, swarm renders: *"We've recommended this 3 times. Locally observed REPEAT_PURCHASE_IN_30D: 8.2% (baseline prior was 6.5%)."* No predicted lift, no projection, no CI theater. Observed-vs-baseline with sample size visible. **This is the demo moment.**

**3. Historical-review surface** (consumed by UI, not built by engine):
Per-merchant page: rows = months, columns = plays, cells = `{evidence_class, action_taken_status, observed_outcome_if_any}`. Most cells sparse for first 3 months — that is honest. By month 6 the page reads like a marketing journal. **30-second sales-page screenshot.**

**Ban list (substrate does NOT make these visible):**
- "Predicted incremental revenue $X" — banned (frozen contract)
- "We learned that play Y outperforms" — requires holdout, not just memory
- "Last month you sent the campaign" — requires Klaviyo poll; engine does not own this
- "Calibrated confidence" — banned

---

## What the founder needs to decide

Consolidated across DS + PM. Each item: what's needed → why → default if no answer.

### DS-side decisions (substrate mechanics)

1. **`store_id` derivation rule.** Folder-name vs Shopify shop subdomain hash vs explicit `--store-id` CLI arg. → Becomes the partition key, hard to change later. → **Default:** basename of orders-CSV parent dir, with `STORE_ID` env override.

2. **Per-merchant directory layout from day 1, vs aliased migration later.** → Defer is cheap to write but expensive to migrate when a second merchant lands on the same machine. Privacy hazard ships to production. → **Default:** per-merchant from day 1.

3. **Where `campaign_sent` events come from in v1.** Manual JSON import vs Klaviyo poll vs merchant-UI form. → Determines whether `campaign_execution_lineage` is real or stubbed. → **Default:** manual JSON import (`data/<store_id>/inbox/campaigns/*.json`) with documented schema. Smallest thing that lets the substrate be tested end-to-end without waiting for Klaviyo.

4. **Retention policy.** → **Default:** keep everything (recs + considered + outcomes); revisit at 12 months. Disk is not the constraint.

5. **`audience_definition_version` bump policy.** When does an M3 builder change count as a version bump vs a bug fix? → Open question from post-6B audit. → **Default:** any change to the SQL/Python that produces an audience definition increments `audience_definition_version` by 1; old lineages remain readable but no longer accrue new events (they fork to a new lineage_id).

6. **Snapshot directory layout.** Flat vs date-partitioned. → **Default:** flat with run_id (ULIDs sort by time anyway).

7. **Whether the engine writes `campaign_sent` for itself in dev/test.** → Discipline says no. → **Default:** separate `tools/dev_seed_campaign_sent.py` script outside the engine module. Discipline preserved by file boundary, not social convention.

8. **Internal naming.** "Campaign memory" vs "play memory" vs "lineage memory." → Wrong word locks in wrong mental model. → **DS recommendation:** the atomic unit is the **lineage**, not the recommendation, not the campaign. Call it the **lineage memory layer** internally.

### PM-side decisions (commercial framing)

9. **Canonical user of historical-review UI.** Founder vs ops manager vs CMO/agency. → Drives information density and vocabulary. → **Default:** design for the $2M founder (skim-first, one-screen-per-month, no statistical jargon). Re-skin for ops manager later.

10. **Campaign-execution-truth source for the agentic future.** Manual import / Klaviyo poll / merchant declaration / "not in v1." → Determines whether `campaign_execution_lineage` is a real primitive. → **Default:** merchant declaration ("did you run this? yes / no / partial") rendered by swarm, written into a separate `campaign_outcomes_<store_id>.json`. Klaviyo poll deferred to Phase 10+.

11. **WTP target the substrate is meant to unlock.** Defending $800 vs justifying a price *raise* to $1.5K. → Defense and offense need different demo moments. → **Default:** defense first (badge in Phase 7), offense once K=3 hits across 3+ pilot merchants.

12. **Open or closed substrate.** Beacon-agents-only vs export/API for merchant or 3rd-party. → "You own your data" is a strong $5M CMO sales line; opening API commits to a public schema. → **Default:** closed in Phase 7 (Beacon agents only); merchant-readable JSON export by Phase 9; no third-party API in year 1.

13. **Merchant deletion rights.** Full wipe vs partial deletes. → GDPR/CCPA + calibration nightmare risk. → **Default:** merchant can delete their entire per-store history (one button, full wipe, no partial deletes). Sales feature, not a footnote.

14. **Export ownership.** Full per-store JSON export from day 1? → Cheap commitment, big trust signal. → **Default:** yes — "your data, always exportable, no lock-in."

15. **Single-merchant vs cross-merchant pooling.** $1–2M brands won't clear N thresholds individually; pooling has antitrust + privacy implications. → Positioning decision before engineering. → **Default:** single-merchant only in year 1. Revisit with legal in year 2. Do NOT promise pooling-derived intelligence to merchants in the meantime.

16. **Merchant-facing naming.** "Memory," "history," "ledger," "evidence base." → Defines the category. → **PM recommendation:** "evidence ledger" internally, "recommendation history" merchant-facing. Avoid "memory" merchant-facing because it implies the engine knows things it does not.

17. **Pilot merchant briefing on substrate.** What do the first 5 Beauty Beta merchants get told? → Overpromise risk highest in first 5 conversations. → **Default:** tell them about the badge and "we will start showing observed outcomes around month 3 or 4 once we have enough data per recommendation." Do NOT mention uplift, calibration, or future model-backed plays.

### What is NOT a founder call (DS owns)

- SQLite vs JSONL choice
- lineage_id formula
- Single-writer-per-event-type discipline
- Additive versioning policy
- View definitions

---

## Phase 7 Substrate Ticket Plan (substrate-only; no ML emitters)

DS-spec, ordered. Each ticket ships independently, leaves the engine runnable, does not couple to any ML emitter.

### S-1. Per-merchant directory + store_id resolution
**Scope:** Resolve `store_id` per founder rule (default: basename of orders-CSV parent dir, env override). Re-route `data/foo` → `data/<store_id>/foo`. Migrate `recommended_history.json` by copy-with-attribution (idempotent).
**Acceptance:** Two-merchant smoke test (run engine on merchant_A then merchant_B in same checkout; zero file overlap, zero leakage). M0 Beauty goldens still byte-identical.
**Unblocks:** Beta blocker B-4. Precondition for everything else.

### S-2. SQLite memory.db + events table + lineage_id helper
**Scope:** `src/memory/store.py` exposing `open_memory(store_id) -> MemoryStore` with `append_event(...)`. WAL-mode SQLite. Migrations via `PRAGMA user_version`. `compute_lineage_id(store_id, play_id, audience_definition_id, audience_definition_version)` helper. `tools/inspect_memory.py` for hand-debugging.
**Acceptance:** Append 1000 events; query by lineage_id, assert ordering. Concurrent-write test (2 processes × 100 events) leaves 200 distinct event_ids, zero corruption. Schema migration test idempotent re-run.
**No engine code changes yet.** Substrate exists in isolation.

### S-3. Engine writes `recommendation_emitted` + `recommendation_considered`
**Scope:** At end of `decide()`, after `engine_run.json` is written, append one `recommendation_emitted` per PlayCard in `recommendations` and `recommended_experiments`, one `recommendation_considered` per RejectedPlay. Payload includes internal Measurement diagnostics, typed evidence_snapshot (overlaps with B-2), pre-registered expectation block (audit L-E), snapshot path. Lineage_id via S-2 helper. **Engine never reads from events table in this ticket.** [src/outcome_log.py:285](../src/outcome_log.py#L285) continues writing the legacy file in parallel for one phase. Grep test: no other module writes to events table.
**Acceptance:** Run Beauty fixture twice with 30 days of synthetic delta; assert (a) lineage_id for `first_to_second_purchase` byte-identical across runs (this IS audit L-B run as a regression now), (b) two `recommendation_emitted` rows with same lineage_id and different run_id, (c) snapshot files referenced by event payload still exist on disk.
**Bundles:** audit L-B + L-E + half of L-F.

### S-4. Immutable snapshot discipline + run_id contract
**Scope:** Move `engine_run.json` write target from mutable `receipts/engine_run.json` (overwritten each run) to `data/<store_id>/runs/<run_id>.json` (immutable, never overwritten). Keep `receipts/engine_run.json` as symlink/copy of latest for backward compat with current Agent Swarm consumers. Add `snapshot_sha256` field to `recommendation_emitted` payload computed at write time.
**Acceptance:** Run engine 5 times → 5 distinct snapshot files; each file's sha256 matches event log value. Mutation test: hand-edit a snapshot, rerun verification script, assert mismatch detected.
**Implements:** primitive 1 (immutable recommendation snapshots) concretely.

### S-5. Read-views for consumers
**Scope:** `v_lineage_timeline`, `v_calibration_state`, `v_open_recommendations` in `src/memory/views.sql` + Python helpers. **Only public read API for the substrate.** Rewire `calibration_stub.load_realization_factors` to call `get_calibration_state` and project into existing `{prior_overrides, evidence_thresholds, materiality_overrides}` dict shape. **No behavior change** because no `calibration_updated` events exist yet — view returns empty, stub returns same empty-shape dict it returns today ([src/calibration_stub.py:59](../src/calibration_stub.py#L59)). Document contract in `docs/memory_substrate.md`.
**Acceptance:** Seed events fixture (10 lineages, 30 events); each view returns expected shape. Forbidden-write test: attempt INSERT into a view, assert SQLite rejects.
**Implements:** primitive 8 (future agent interoperability).

### S-6. Manual `campaign_sent` import path + merchant-input contract
**Scope:** `tools/import_campaign_sent.py` CLI that reads documented JSON schema from `data/<store_id>/inbox/campaigns/*.json` and writes `campaign_sent` events. JSON schema is the contract that Agent Swarm and any future Klaviyo poller will conform to. Engine does not call this tool; it lives outside the engine module. Define `outcome_observed` JSON schema in same doc but do not implement importer (deferred until `REPEAT_PURCHASE_IN_30D` computation is its own ticket).
**Acceptance:** Two-run integration test (audit L-G as substrate-only): T0 produces 3 `recommendation_emitted` events; manual import drops `campaign_sent` JSON for one of them; T1's `v_lineage_timeline` for that lineage_id returns `[recommendation_emitted, campaign_sent]` in order; T1 engine still runs identically because it does not read `campaign_sent` events.
**Closes:** the seam the play-lifecycle-discussion-reconciled doc names as discipline boundary, without requiring Agent Swarm or Klaviyo integration.

### Out of scope for Phase 7 (explicit deferrals)
- The `outcome_observed` *computation* (audit L-C). Schema is defined; computation is its own ticket gated on `REPEAT_PURCHASE_IN_30D` being honestly definable from CSV alone.
- The calibration *consumer* (audit L-D). Substrate writes events; the consumer that reads outcomes and emits `calibration_updated` is a separate ticket — ships AFTER substrate, BEFORE any ML emitter.
- Any ML emitter (affinity, survival, uplift). Substrate-only per founder constraint.
- Multi-tenant SaaS Postgres migration. Single-merchant SQLite is the right substrate for at least 12 months.
- UI rendering of `v_lineage_timeline`. UI is downstream; consumes the view, doesn't define it.

---

## Pricing & Positioning Implications

**Pricing tier shift: yes, but not yet.** Substrate by itself does not justify a price change at signing. Substrate justifies a price *raise at renewal* — month 4–6, after the receipts surface lights up.

| Phase | Substrate state | New-merchant pricing | Existing-pilot pricing |
|---|---|---|---|
| Today | not live | $500–800/mo | (signed price holds) |
| Phase 7 | badge live, no observed outcomes | $800/mo | (no change) |
| Phase 8 (~3mo after P7, K=3 outcomes accumulated) | receipts page live | $1.5K/mo | renewal conversation: "we've now observed N campaigns, here's what we learned, here's the new tier" |
| Phase 9+ | first ML emitter live, holdout receipts | $3K/mo | renewal at receipts evidence |
| Year 2 | model-backed plays + uplift consumer in production | $5K+ | as evidence supports |

$8K/mo destination is 12–18 months out at minimum. Reconciled-review §137 holds.

**Persona target:** marginally tighter, not changed. $1–10M Beauty/Supplements remains the wedge. Substrate value compounds → sells best to merchants who plan to be around in 12 months. Founders thinking in quarters, not weeks. **Sales qualifying question:** "are you optimizing for this month or next year?" If this month, walk.

**Demo script (two parts):**
1. *Today:* "Here is your slate this month. See this 'recommended in March' badge? The engine remembers what it told you and acknowledges it explicitly when the same situation comes up again."
2. *Forward-looking, honestly framed:* "By month 4 this page will show you what actually happened on the campaigns we recommended. Here is a screenshot from a brand 3 months ahead of you" — using a synthetic-but-honest fixture, NOT real merchant data dressed up.

**Beta merchant briefing (concrete script):**
- "Beacon now keeps a per-store recommendation history. Every play we recommend, every play we hold back, gets logged with the audience definition and the reason."
- "Starting month 2, your monthly slate will show which plays we already recommended in prior months and whether the situation has changed."
- "Around month 3 or 4, once we have enough observed data, we'll start showing you outcomes for the plays we recommended that you ran. The first outcome we'll measure is repeat-purchase rate within 30 days, because that's what we can compute reliably from your Shopify data."
- "Your data stays yours; you can export everything Beacon remembers about your store at any time, and you can wipe it entirely if you need to."

**Ban list (do NOT tell pilots yet):**
- "Beacon learns from your campaigns" (it learns from REPEAT_PURCHASE_IN_30D, one signal, not "your campaigns")
- "Beacon predicts incremental revenue" (banned, frozen contract)
- "Beacon will publish to Klaviyo for you" (Agent Swarm + future integration, not Phase 7)
- "Beacon's recommendations get better every month" (true eventually, unproven for ~6 months → replace with "Beacon shows you what happened on what it recommended" — same merchant value, no overpromise)
- Model names (Cox PH, BG/NBD, T-learner) — engineering blog, not slate
- Promise the historical-review UI before Phase 8 — promise the badge

---

## How this updates the 12–18 month roadmap

Phase numbering from §"Recommended 12–18 Month Roadmap" above is now sharpened:

| Phase | Name | Scope | Visible artifact |
|---|---|---|---|
| Close 6B | Stop-Coding hygiene | Audit Beta blockers B-1 through B-6 | (none new — trust hardening) |
| **Phase 7** | **Lineage Memory Substrate** | **S-1 through S-6 above. No new ML.** | **"Previously recommended" badge** |
| Phase 8 | Vertical Expansion + Outcome Computation | G-1 (supplements pinned fixture), G-2/G-3 (parser + priors), implement L-C `compute_realized_outcome(REPEAT_PURCHASE_IN_30D)`, ship calibration consumer option-1 | Receipts page (after K=3 accumulation) |
| Phase 9 | First ML Emitter | Affinity (FP-growth + ALS) behind Recommended Experiment | Named SKU pairs in slate |
| Phase 10 | Replenishment Timing | Survival emitter, Klaviyo publish seam | Per-customer expected reorder date as Klaviyo profile property |
| Phase 11+ | Promotion Mechanism (verticals stay locked) | Uplift consumer, churn defense, discount elasticity. NO new vertical work — scope hard-locked at {beauty, supplements, mixed}. | Holdout receipts |

---

## Updated Two-Bucket Inventory (revised)

**Bucket A — Pending Work** (unchanged from above; trust + addressable-market hygiene)

**Bucket B — Intelligence-Layer Enhancements** is now refined into TWO sub-buckets:

### Bucket B1 — Substrate (Phase 7; no models)
- S-1 through S-6 (DS plan above)
- Implements audit L-A, L-B, L-E, L-F, L-G, L-H
- Defers audit L-C (outcome computation) and L-D (calibration consumer) to Phase 8

### Bucket B2 — Calibration Consumer + Outcome Computation (Phase 8)
- L-C: `compute_realized_outcome(card, next_run_csv)` for `REPEAT_PURCHASE_IN_30D`
- L-D #1: trailing-window mean per `(play_id, vertical, store_id)`
- Both write `outcome_observed` and `calibration_updated` events into the substrate built in B1

### Bucket B3 — ML Emitters (Phase 9+; what most people call "the ML work")
- I-1 affinity → I-2 timing → I-3 churn → I-4 uplift → I-5 discount elasticity → I-6 LTV sizing

**Critical insight (revised):** what the founder originally called "lifecycle" is actually three distinct buckets. B1 is substrate (pure infrastructure, ships with no models), B2 is the calibration consumer (the missing bridge), B3 is the ML emitter ladder. Conflating them is what produced the doc's "platform rewrite trap" risk. Separating them lets each ship in 4–8 weeks instead of as a quarter-long monolith.

---

## File References

- [agent_outputs/_input-beacon-product-strategy-research.md](./_input-beacon-product-strategy-research.md) — input under review
- [agent_outputs/ecommerce-ds-architect-ml-roadmap-review.md](./ecommerce-ds-architect-ml-roadmap-review.md) — DS independent review
- [agent_outputs/product-strategy-pm-ml-roadmap-review.md](./product-strategy-pm-ml-roadmap-review.md) — PM independent review
- [agent_outputs/post-6b-stop-coding-audit.md](./post-6b-stop-coding-audit.md) — current ground truth on what's left
- [agent_outputs/play-lifecycle-discussion-reconciled.md](./play-lifecycle-discussion-reconciled.md) — lifecycle scope source; seam-discipline source
- [agent_outputs/phase6a-final-review.md](./phase6a-final-review.md) — caveats 1–13 reference
- [src/outcome_log.py:285](../src/outcome_log.py#L285) — current legacy writer; gains parallel events-table write in S-3
- [src/calibration_stub.py:37](../src/calibration_stub.py#L37) — empty consumer socket; rewired in S-5
- [src/engine_run.py](../src/engine_run.py) — frozen contract; does NOT change
- [src/guardrails.py:604](../src/guardrails.py#L604) — current play_id-only fatigue key; replaced by lineage_id in S-3
- [src/main.py:860](../src/main.py#L860) — current history writer call site; gains parallel events-table write in S-3
- [CLAUDE.md](../CLAUDE.md), [ENGINE.md](../ENGINE.md)

---

# ADDENDUM 2: Parallel Tracks + Swarm-as-Loop-Closer (Restructured Plan)

**Added:** 2026-05-09 (post substrate addendum)
**Triggers:** Founder pushback on three points: (1) lifecycle being dependent on Agent Swarm; (2) intelligence as the differentiator — visible data-backed plays sooner; (3) Agent Swarm role clarified as the campaign-execution + outcome-ingestion layer (packages Klaviyo plays, gets merchant approval, deploys, monitors, closes the loop).

This addendum supersedes the linear "Phase 7 → 8 → 9" sequencing in the prior addendum. **Substrate plan (S-1 through S-6) is unchanged.** What changes: the *order of work*, the *track structure*, the *role of the manual import path*, the *visible artifacts*, and the *pricing bundle*.

---

## What changed vs the original linear roadmap

### Change 1: Sequential → Two parallel tracks
**Was:** Substrate → Vertical Expansion → First ML emitter, in that order. ~9 months to first visible model-derived play.
**Now:** Beacon team builds substrate + ships I-1 affinity emitter in parallel; Swarm team builds deploy/monitor against frozen S-6 schemas in parallel. Only 3 cross-ticket coupling points (G-7→S-3, B-2 bundled with S-3, B-4=S-1).

**Why:** the founder's premise that "lifecycle depends on Swarm" was wrong. Substrate doesn't depend on Swarm — Swarm consumes the substrate. Both can ship independently against frozen schemas.

### Change 2: Manual JSON import: v1 production → permanent debug seam
**Was:** S-6 manual import was the v1 default writer for `campaign_sent` until Swarm arrives "later."
**Now:** Swarm IS the production writer from Phase 8 (Swarm Deploy Agent writes `campaign_sent`; Swarm Monitor Agent writes `outcome_observed`). Manual import survives as the **permanent test/reproducibility tool**.

**Discipline (3 rules):**
1. Schemas are versioned and additive-only — Swarm pins to `event_version`, Beacon never breaks a pinned version
2. Manual import remains green permanently — every Phase 7 acceptance test runs through `tools/import_campaign_sent.py`, NEVER through the Swarm
3. **Substrate definition-of-done is "manual import passes," NOT "Swarm in production"** — decouple explicitly so a Swarm slip cannot reopen Phase 7

### Change 3: Hero artifact shifts from "badge" to "approval queue"
**Was:** Phase 7 visible artifact = "previously recommended" badge in the slate
**Now:**
- Phase 7 (substrate live, Swarm not yet): badge is still the artifact
- Phase 8 (Swarm live): **approval queue** becomes the hero — *"3 plays packaged, awaiting your approval, deploys to Klaviyo on click"*. Badge demotes to "trust receipt" inside each card.

A merchant feels the product as **an operator, not a report.**

### Change 4: First model-backed play moves up
**Was:** I-1 affinity emitter ships in Phase 9 (~month 9)
**Now:** I-1 affinity ships in parallel with substrate, gated to `targeting` evidence_class — visible model-derived audience in slate by **month 3–4**. The smallest honest unit of "data-backed": *"Send to 1,247 customers who bought SKU-A but not SKU-B (lift ratio 3.2x base co-occurrence in your store)."* No model name, no projection — **the audience itself is the artifact.**

### Change 5: Pricing bundle splits into two SKUs
**Was:** single tier ladder $800 → $1.5K → $3K → $8K based on engine maturity. **NOTE:** superseded by Addendum 3 — narrower-than-assumed TAM (hard-locked verticals) justifies higher prices, not lower. Revised ladder: $1.5K → $3K → $5K → $12K. See Addendum 3.
**Now:** two SKUs run in parallel:

| Tier | Brief-only (entry) | Brief + Swarm (bundled) |
|---|---|---|
| Phase 7 | $800 | n/a (Swarm not live) |
| Phase 8 | $1.5K | $2K → $3.5K |
| Phase 9 | $3K | $6K |
| Year 2 | $5K | $12K |

Brief-only stays as entry SKU so substrate value is provable independent of Swarm reliability. LLM costs (~$40–80/merchant/month) eat ~5% of bundled headroom — survivable. **Year-1 = human-in-loop approval is the only honest default**; auto-pilot graduation is year 2 per play type (plays with N≥20 substrate observations + CI-bounded outcomes).

---

## Restructured Two-Track Roadmap

```
                 BEACON TRACK                         SWARM TRACK
                 (substrate + engine)                 (deploy / approve / monitor)
                 ───────────────────                  ──────────────────────────

Months 0–3       S-1 (per-merchant scoping)           Schema review of S-6 contract;
(Phase 7)        S-2 (SQLite + lineage_id)             Swarm team builds against frozen
                 Bucket A Beta blockers                schemas (parallel, no live data)
                 (B-1, B-2, B-3, B-5, B-6)
                                                      
                 ↓ Schemas FREEZE end of S-3 ↑
                                                      
Months 3–6       S-3 (engine writes events)           Swarm Deploy + Approval agents
(Phase 8)        S-4 (immutable snapshots)            land. Reads v_open_recommendations.
                 S-5 (read views)                     Writes campaign_sent on Klaviyo
                 S-6 (manual import + schemas)        deploy-success.
                 I-1 affinity emitter (targeting)
                 G-1 supplements pinned fixture
                                                      
                 → Phase 8 visible artifact: APPROVAL QUEUE with packaged plays
                   + previously-recommended badge inside each card
                                                      
Months 6–12      L-C compute_realized_outcome         Swarm Monitor Agent writes
(Phase 9)        L-D #1 calibration consumer          outcome_observed events
                 (trailing-window mean)               
                 I-2 replenishment timing             
                 G-3 supplements priors hardening + mixed semantic formalization
                                                      
                 → Phase 9 visible artifact: RECEIPTS PAGE
                   "We recommended this 3 times. Observed: 8.2% (prior baseline: 6.5%)"
                                                      
Months 12–18     I-4 uplift consumer                  Auto-pilot graduation per
(Phase 10+)      I-3 churn defense                    play type (plays with N≥20)
                 I-5 discount elasticity              
                 Apparel/food vertical pinning        
                                                      
                 → Year-1 destination: CALIBRATION DRIFT CHART
                   "Your Beacon is now tuned to your store"
```

---

## What's Startable NOW (Engine Track — no Swarm dependency)

The Swarm being 2–3 weeks out is not a blocker for any engine work. Tier ranking by startable-on-day-1:

### Tier 1 — Parallel-startable on day 1 (zero coupling)

| Ticket | Scope | Effort |
|---|---|---|
| **B-1** Anomaly auto-register → ABSTAIN routing | Wire `AnomalousWindowCheck` into `apply_guardrails`; populate reserved `anomaly_flags` slot; pin `promo_anomaly_240d` to slate test lane | 1–3 days |
| **B-3** Hardcoded-fallback regression test | Grep-assert no `{0.02..0.40}` constants appear as `measurement.effect_abs` / `measurement.p_internal` | 1 day |
| **B-5** Berkson invariant test | Property test pinning cohort/measurement-window invariant; assert `subscription_nudge` + `routine_builder` ship `measurement=None` | 1–2 days |
| **B-6** Multi-window combiner universality test | One-time test asserting Beauty `measurement` for `evidence_class=measured` produced by `combine_multiwindow_statistics`, not min-p merge | 1 day |
| **G-2** `empty_bottle` parser unit-coherence | Vertical-dispatched parser OR gate via `vertical_applicable` filter | 2–3 days |

### Tier 2 — Day 1 start, but bundle-as-one-ticket due to file overlap

| Bundle | Why bundled |
|---|---|
| **B-4 = S-1** Per-merchant directory + `store_id` resolution | Same code paths; treat as one ticket |
| **B-2 with S-3** Considered typed evidence_snapshot | S-3 writes `recommendation_considered` events with the typed payload — if B-2 ships standalone, contract migrates twice |

### Tier 3 — Day 1 start; prerequisite for substrate acceptance

| Ticket | Why critical-path |
|---|---|
| **G-7** Cross-run byte-identical determinism CI | S-3's "lineage_id byte-identical across runs" assertion is unverifiable without this |

### Week 2+ — Sequenced after Tier 2 lands

After **B-4/S-1** lands:
- **S-2** SQLite memory.db + events table + lineage_id helper (substrate in isolation, no engine code changes yet)
- **G-1** Pin synthetic supplements slate fixture (precondition for substrate two-run test in S-6)
- **G-3** Vertical priors expansion (start with supplements coverage gaps)
- **G-4** Reclassify `subscription_nudge` + `routine_builder` permanently as targeting

After **S-2** lands:
- **S-3** Engine writes `recommendation_emitted` + `recommendation_considered` events (bundles B-2 typed payload work) — **end of S-3 is when S-6 schemas FREEZE**, unblocking Swarm team
- **S-4** Immutable snapshot discipline + run_id contract

After **S-3** lands:
- **S-5** Read views (`v_lineage_timeline`, `v_calibration_state`, `v_open_recommendations`); rewires `calibration_stub.load_realization_factors`
- **S-6** Manual `campaign_sent` import path + the JSON schema docs (the **Swarm integration contract**; high schema-review bar)
- **I-1 spike** affinity emitter prototype (feature branch; ships at `targeting` class with no calibration claims)

### Genuinely blocked on Swarm (don't start on Beacon track)

- Rendering the "previously recommended" badge merchant-facing (Swarm reads `v_lineage_timeline` and writes the line into slate copy)
- Production `campaign_sent` event population (Swarm Deploy Agent on Klaviyo deploy-success)
- Production `outcome_observed` event population (Swarm Monitor Agent)
- Approval queue UX
- Klaviyo deployment

These are Swarm-track scope. Engine team doesn't touch them.

### Don't start until substrate is live AND outcome events exist

- **L-C** `compute_realized_outcome(REPEAT_PURCHASE_IN_30D)` — needs `outcome_observed` events to compute against
- **L-D #1** Calibration consumer (trailing-window mean) — reads outcome events, emits `calibration_updated`

Both are Phase 9 / month 6+.

---

## Suggested 2-Week Sprint Plan (~2 engineers)

**Week 1:**
- **Engineer A:** B-4/S-1 (per-merchant scoping) + G-7 (determinism CI) — critical path
- **Engineer B:** B-1 (anomaly auto-register) + B-3 (hardcoded-fallback regression test) — pure parallel work

**Week 2:**
- **Engineer A:** S-2 (SQLite + lineage helper) — substrate foundation
- **Engineer B:** B-5 (Berkson invariant) + B-6 (multi-window universality test) + G-2 (empty_bottle parser)

**End of week 2 deliverable:** all 5 Bucket A Beta blockers landed, per-merchant scoping live, substrate foundation (SQLite + lineage helper) ready for S-3. Engine is in materially better shape AND ready to write events as soon as S-3 ships in week 3.

When Swarm infra catches up in 2–3 weeks, hand them the frozen S-6 schemas and let them build deploy/monitor in parallel while Beacon team pushes S-3 → S-4 → S-5 → S-6 + I-1 affinity prototype.

---

## Critical Architectural Discipline (preserve under all restructuring)

The restructured plan keeps these contracts unchanged:

1. **Engine writes only its own event types** (`recommendation_emitted`, `recommendation_considered`). Engine never writes `campaign_sent`, `outcome_observed`, or `calibration_updated`.
2. **Engine reads only `v_calibration_state`** (and the fatigue-gate-supporting `v_lineage_recent_emissions`). Engine does NOT read its own past recommendations as state.
3. **Single-writer-per-event-type discipline** preserved: Swarm Deploy Agent owns `campaign_sent`; Swarm Monitor Agent owns `outcome_observed`; calibration consumer owns `calibration_updated`.
4. **Approval is Swarm-internal state**, not a substrate primitive — does not write events.
5. **Manual import path stays green permanently** as the substrate's reproducibility tool.
6. **Substrate definition-of-done = "manual import passes,"** not "Swarm in production."
7. **Frozen JSON contract preserved.** Trust contract preserved (no fabricated p/CI/projections, no "predicted lift").
8. **Engine is NOT the owner of campaign truth.** Engine emits recommendations; campaign truth lives in the memory layer.

---

## Demo Script (revised for restructured plan)

3 artifacts, 3 months:

- **Month 1 screenshot:** approval queue with 3 packaged plays, "Approve and deploy to Klaviyo" CTA visible. Engine reasoning collapsed under each card. (Requires Swarm Phase 8.)
- **Month 3 screenshot:** same queue, but each card now shows a "Previously recommended in March; same audience definition" badge sourced from substrate. Loop visible.
- **Month 6 screenshot:** receipts page showing N plays shipped, M outcomes measured, calibration drift chart. *"Your Beacon is now tuned to your store."*

**Beauty Beta merchants (concrete script update):**
- "Beacon now keeps a per-store recommendation history."
- "Starting month 2, your monthly slate will show which plays we already recommended in prior months and whether the situation has changed."
- "Around month 3 or 4, once we have enough observed data, we'll start showing you outcomes for the plays we recommended that you ran."
- "By Phase 8 (target month 4), the Swarm will package, route for your approval, and deploy to Klaviyo on your one-click approval."
- "Your data stays yours; you can export everything Beacon remembers about your store at any time."

**Ban list (do NOT promise):**
- Auto-pilot deployment in year 1 (graduation is year 2 per play type)
- "Beacon learns from your campaigns" (it learns from REPEAT_PURCHASE_IN_30D)
- "Beacon predicts incremental revenue" (banned, frozen contract)
- "Recommendations get better every month" (replace with "Beacon shows you what happened on what it recommended")
- Any model names (Cox PH, BG/NBD, T-learner)

---

## Bottom Line: What Changed vs the Original Linear Plan

In one paragraph:

The original plan was sequential (lifecycle → vertical expansion → first ML emitter), implying ~9 months before any visible intelligence. The restructured plan is two parallel tracks: Beacon team ships substrate + the I-1 affinity emitter + Bucket A Beta blockers in parallel; Swarm team builds deploy/monitor against frozen S-6 schemas in parallel. Only 3 cross-coupling points (G-7→S-3, B-2 bundled with S-3, B-4=S-1) — everything else parallelizes. First model-derived audience visible in slate at month 3–4 (not month 9). Approval queue replaces the badge as the Phase 8 hero artifact. Pricing splits into brief-only entry SKU vs Brief+Swarm bundled SKU. Manual JSON import is preserved as the permanent test seam — substrate definition-of-done is "manual import passes," not "Swarm in production." All trust contracts and substrate primitives unchanged.

---

# ADDENDUM 3: Vertical Scope Hard-Lock (Correction)

**Added:** 2026-05-09 (post implementation-plan commit)
**Trigger:** Founder surfaced a critical scoping error that the DS architect, PM, and Implementation Manager all missed: the engine is permanently scoped to **{beauty, supplements, mixed}**, where `mixed` = the literal beauty+supplements blend (NOT a fallback for unknown verticals). Apparel, food/bev, home goods, and wellness are **out of scope permanently** — refused, not deferred.

**Code source of truth:** [src/play_registry.py:142](../src/play_registry.py#L142): `_ALL_VERTICALS = frozenset({"beauty", "supplements", "mixed"})`

## What changed in framing

Where prior addenda said "vertical priors expansion to apparel/food/home/wellness" or "second non-Beauty vertical," the corrected position is:

> **Vertical scope is a moat, not a beachhead constraint.** Beacon is purpose-built for the consumables economic substrate (replenishment cycles, subscription mechanics, routine/regimen building, post-purchase windows tied to consumption rate). Apparel (size/return-driven), food/bev (perishability), home goods (one-shot durables), and wellness (services-heavy) do not share this substrate, which is exactly why the engine cannot and should not serve them.

## Commercial implications (PM)

**TAM math (revised):**
- ~2.0M Shopify stores × ~7–9% beauty + ~2–3% supplements × top 8–12% in $1–10M band ≈ **40k–70k global addressable merchants**
- ~15k–25k US/EU English-speaking and structurally addressable
- 2–4% steady-state penetration ≈ **300–1,000 paying merchants**
- $12K ACV ceiling × Brief+Swarm bundle ≈ **$10M–$40M ARR ceiling** with full agentic expansion
- Realistic outcome: **bootstrap / Series-A friendly, not venture-decacorn.** Deck, pricing, and hiring plan must reflect this.

**Pricing — revised UP (not down):**
Narrower TAM justifies higher prices because (a) every account matters more (high-touch onboarding sustainable), (b) depth-of-vertical-priors is the moat (genuinely more valuable than horizontal tools), (c) no logo-grab phase to subsidize.

| Tier | Brief-only (entry) | Brief + Swarm (bundled) |
|---|---|---|
| Phase 7 | $1.5K | n/a (Swarm not live) |
| Phase 8 | $3K | $5K |
| Phase 9 | $5K | $8K |
| Year 2 | $8K | $12K |

**Kill the $800 tier.** No expansion-path math justifies a low-end loss-leader.

**Persona narrative (locked):** *"The AI growth team for consumables DTC."* Strength through specificity, not apology for narrowness.

**Sales qualifying gate-1:** *"Is your store primarily Beauty, Supplements, or both?"* If no → instant disqualify, polite refusal, no demo. Protects (a) demo win-rate, (b) engine reputation.

## Architectural implications (DS)

The vertical lock is a **DS gift, not a constraint:**
- `lineage_id` partition cardinality is now bounded at 3 (beauty/supplements/mixed) — calibration math becomes tractable
- **Cross-merchant pooling within {beauty, supplements} is much more defensible** than the previously-discussed "all verticals" pool (apparel AOV ≠ supplements LTV dynamics). Hierarchical priors with `vertical` as a 3-level grouping factor becomes a viable Year-2 design instead of a pipe dream.
- K=3 outcome accumulation per `(play_id, vertical, store_id)` partition reachable on a smaller install base.

## "Mixed" semantic formalization

The code today treats `mixed` as a `vertical_mode` value but never asserts what it means. Going forward, all three of these ship together (DS recommendation):

1. **Runtime assertion** at engine entry: `assert vertical_mode in {"beauty", "supplements", "mixed"}`
2. **Comment** at [src/play_registry.py:142](../src/play_registry.py#L142): "mixed = literal beauty+supplements blend, NOT an unknown-vertical fallback"
3. **Frozen-contract test:** `assert _ALL_VERTICALS == frozenset({"beauty", "supplements", "mixed"})` — any future PR adding a vertical breaks the test, forcing a founder-level scope decision

## Doc edits applied

- L145 Demo-vs-production gap text: corrected from "Apparel/food/home/wellness don't exist" to "Apparel/food/home/wellness are out of scope permanently — engine must HARD REFUSE"
- L234 "Second non-Beauty vertical" → "Mixed-vertical pinned fixture"
- L298 G-3 framing: "vertical priors expansion" → "supplements priors hardening + mixed semantic formalization"
- L621 Phase 11+ row: dropped "second non-Beauty vertical" — verticals stay locked
- L746 Gantt row: corrected
- Pricing tier section: cross-referenced this addendum

## The trap to avoid

> *"The reconciled-review doc reads, in places, as if vertical narrowness is something to be managed or eventually overcome. That framing should be inverted explicitly: 'Hard-locked to Beauty + Supplements' is the moat statement, not the limitation statement. A horizontal 'AI growth team for any Shopify merchant' tool is what 50 YC companies are building badly; Beacon's defensibility is that the priors, the play library, the gates, the seasonal adjustments, and the audience archetypes are tuned to the consumables economic substrate to a depth no horizontal tool will match."* — PM

If the docs frame this as a constraint to escape, the strategy gets watered down on the first investor pushback. Treat it as moat-statement, not limitation-statement.
