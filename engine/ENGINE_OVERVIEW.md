# BeaconAI Engine — Plain-English Overview

**Purpose:** A single document to read when you've lost track of what the engine does and how it got here. No jargon. No timeline pressure.

**Status:** Snapshot as of 2026-05-16. Update when major phases close.

---

## 1. What the engine is, in 30 seconds

BeaconAI is a **monthly action engine** for DTC e-commerce brands.

Once a month, it reads a brand's Shopify data (CSV export) and produces one thing: a **typed JSON file** that says *"send this email to this audience, here's the evidence, here's why now."* Some future UI will display this. You don't have a UI yet, and you don't need one to find out whether the engine is good.

The engine is not a dashboard. It does not show "metrics that moved." It makes **decisions** — and it refuses to make a decision when the evidence is weak.

---

## 2. The one mental model

The engine is a pipeline. Every play passes through 4 steps:

```
  AUDIENCE        →   MEASUREMENT     →   SIZING        →   DECIDE
  (who qualifies?)    (what evidence?)   (what $ range?)   (publish?)
```

- **Audience builder** — given a CSV, who are the customers this play targets? (e.g., "everyone who bought a hydration SKU 28–45 days ago")
- **Measurement builder** — what *evidence* does this store actually show? (e.g., "the cohort exists, n=1,842, sign-consistent across L28/L56")
- **Sizing** — given audience size, AOV, and priors, what revenue range could this realistically produce?
- **Decide** — does this clear the gates (audience floor, materiality floor, evidence threshold)? Where does it land in the slate?

**The whole engine is this pipeline run 14 times** (once per play in the registry), then ranked into a slate.

---

## 3. The slate (what the engine emits)

For each run, the engine outputs four lanes:

| Lane | What it means | Today's cap |
|---|---|---|
| **Recommended Now** | "Send this. The evidence is on your store." | up to 3 |
| **Recommended Experiment** | "Try this. Industry pattern + your audience fits. We'll measure after." | up to 2 |
| **Considered** | "We looked at this. Here's why we didn't recommend it." | unbounded |
| **Watching** | "Not ready yet, but we're tracking the signal that would trigger it." | up to 4 |

If nothing clears the gates: **ABSTAIN**. The engine emits a typed reason and watches. This is a feature, not a bug.

---

## 4. The journey — how we got here

| Phase | What it added | Why |
|---|---|---|
| **Legacy engine** | First-gen recommendations | Initial product. Had fabricated p-values, generic confidence claims, no rule for when *not* to recommend. |
| **V2 Phase 1 (Decision Core)** | Typed contracts. Refuses to fake stats. Abstains when evidence is weak. 4 evidence classes (`measured`, `directional`, `targeting`, `weak`). | Honesty. The legacy engine couldn't be trusted by a skeptical merchant DS. |
| **V2 Phase 4** | Removed fabricated effect sizes. Cleaned up Berkson confounds. | Outcome log needed to be uncontaminated for future calibration. |
| **V2 Phase 5/6A/6B (the slate)** | Recommended Now / Experiment / Considered / Watching lanes. PlayCard typed schema. `OPPORTUNITY_CONTEXT_DISCLAIMER` to prevent "projected lift" overclaims. | Give merchants a clean, structured monthly briefing surface. |
| **Sprints 1–5 (substrate)** | Per-merchant data folders. SQLite event log (recommendation_emitted, campaign_sent, calibration_updated, outcome_observed). Single-writer discipline. | The plumbing that lets the engine *remember* across runs. Foundation for the future learning loop. |

Each phase added something good. The cost is **cumulative complexity**: today's `decide.py` carries Phase 5 allowlists, Phase 6A pins, Phase 6B fan-out, Sprint 5 advisory flags. All honest scaffolding, but it adds up.

---

## 5. Where the engine is right now

### What works
- ✅ Scientifically honest. No more fabricated p-values or hallucinated lifts.
- ✅ Substrate works. Per-merchant memory, event log, single-writer discipline.
- ✅ The slate structure is clean and the typed contracts are stable.
- ✅ Local development end-to-end. CSV in → `engine_run.json` out → debug `briefing.html` for inspection.

### What doesn't
- ❌ **The engine is too quiet to be a product.**
  - **Beauty store** (pinned fixture): 1 weak Recommended Now (uses a state-statistic proxy) + 0–2 Experiments. **1–3 cards.**
  - **Supplements store** (pinned fixture): **0 Recommended Now, 0 Experiments, ABSTAIN_SOFT.** Nothing shown above the Considered fold.

### Why it's quiet
Look at [src/measurement_builder.py:108](src/measurement_builder.py#L108). The `_SUPPORTED` registry of measurement builders has **exactly one entry**: `first_to_second_purchase`. And even that one uses `returning_customer_share` — a state statistic — as a proxy for intervention lift. The rationale comment at lines 122–128 admits this.

**Every other play has no way to produce evidence on a real store.** So they all fall to Considered or ABSTAIN.

You have 14 plays in the registry. Only 1 can produce Tier-B evidence today. 2 more can ship as Tier-C experiments. That's a pool of 3 — and supplements gets zero of them.

---

## 6. What the redesign changes (the architecture plan)

Same engine philosophy. Fixes the silence. **Reframed 2026-05-17:** beta success = "merchant tries month 1 → returns for month 2," not "6-month outcome calibration loop." This shifted what's beta-critical.

See [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md) + [implementation-manager-s6-s14-revised-plan-ml-layer.md](agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md) for the full plan. The short version:

**Beta-critical (Sprints 6-14, ~15 weeks):**

1. **Build 5 cohort builders** (Tier-B) — the missing piece. Winback dormant cohort, predicted replenishment, discount-dependency hygiene, KM-survival first-to-second, AOV threshold bundles. Each is structured the same: cohort definition + intervention-shaped supporting metric + multi-window consistency check.
2. **Validate priors first** (Sprint 7.5) — your `priors.yaml` is mostly unvalidated guesses. Add a `validation_status` field. *Refuse the Bayesian blend on unvalidated priors* so the math never launders fabricated anchors as rigor.
3. **Add the Bayesian blend** (Sprint 8) — once priors are validated, revenue ranges become defensible posteriors instead of suppressed whiskers.
4. **Refactor into a Play Library** (Sprint 8) — collapse scattered play definitions into one folder per play. Makes future plays cheap.
5. **Build the ML Predictive Layer** (Sprints 10-13) — **NEW**. Five classical ML models running on the merchant's existing CSV data, no outcome history required:
   - **BG/NBD + Gamma-Gamma** probabilistic LTV per customer (Fader/Hardie's models via the `lifetimes` package)
   - **Survival analysis** on reorder gaps (Kaplan-Meier + Cox PH via `lifelines`) for replenishment timing
   - **Collaborative filtering** on co-purchases for bundle composition
   - **RFM segmentation** with statistical confidence bands
   - **Cohort retention curves** with bootstrapped CIs
   - All gated by a new `ModelFitStatus` enum (VALIDATED / PROVISIONAL / REFUSED). When fit quality fails on small merchants, audiences fall back to RFM quintile ranking.
6. **No UI work.** Engine output is typed JSON. `briefing.html` stays as debug-only. Future UI is out of scope.

**Deferred to post-beta:**

- **Phase 9 outcome loop** — was Sprint 10, now post-beta. The "month-2 outcome calibration" story doesn't matter for month-1-wow + month-2-return. Phase 9's payoff window is month 3+.
- **Causal uplift modeling** — needs accumulated Phase 9 outcomes. Post-PMF.
- **Trust-math operator tooling** (replay, backtest, sensitivity CLIs) — founder tools, not merchant-facing.
- **V2 cleanup workstream, portfolio optimization, LLM mechanism generation, multi-channel** — far post-PMF polish.

~15 weeks. 9 sprints (S6 → S14). Every commit ships a runnable engine.

---

## 7. Plays — pool vs. per-run

| | Today | After S14 (beta-ready) |
|---|---|---|
| Plays in registry | 14 | 14 (Play Library refactor folds them in, doesn't add new ones) |
| **Pool: Recommended Now-eligible** | **1** (weak proxy) | **5** (intervention-shaped Tier-B builders) |
| **Pool: Recommended Experiment-eligible** | **2** | **2–4** (depends on priors validation) |
| **Pool total (recommendable)** | **3** | **7–9** |
| **Per-run max cards** | 3 + 2 = 5 (rarely hit) | 3 + 2 = 5 (frequently hit; supplements goes from 0 to 2–3) |
| Supplements briefing | ABSTAIN_SOFT (0 cards) | 2–3 cards, primarily from `replenishment_due` + winback |

**ML doesn't add plays — it ranks audiences.** The 5 ML models (LTV, P(alive), survival, CF, RFM) make EACH play's audience smarter (top-decile-LTV-ranked, expected-recovered-revenue-quantified, etc.) but don't expand the play pool. A supplements winback in month 1 surfaces as a card with ~600 ML-ranked top-decile customers instead of 1,842 unranked customers.

**Pool vs per-run** is the important distinction:
- The **pool** is how many plays can theoretically produce evidence — the engine's *vocabulary*.
- The **per-run cap** is how many cards the engine surfaces in a given month — the engine's *judgment*.

You want the pool to be **wider than the cap** so the engine has options to pick from per store, per month. Different stores fire different plays. Today's pool of 3 is too thin for this; after the redesign, a pool of 7–9 gives proper selection room.

The Play Library refactor in Sprint 8 makes the post-beta growth cheap: every new measurement design = one folder + one builder + one priors entry. Pool can grow to 15+ over the following quarters without architectural work.

---

## 8. Evidence tiers (the redesign's core vocabulary)

After the redesign, every PlayCard carries a typed `evidence_source` chip:

| Tier | Means | Slate lane | Example |
|---|---|---|---|
| **A (Causal)** | Lift measured on your store via a counterfactual | Recommended Now | Phase-9 outcome confirms a prior campaign worked |
| **B (Directional)** | Store shows the condition; industry-prior effect size applies | Recommended Now | `winback_dormant_cohort` fires; your store has N lapsed customers with prior repeat signal |
| **C (Prior)** | Industry pattern + your audience fits; no store evidence yet | Recommended Experiment | `discount_hygiene` with a validated Klaviyo benchmark |
| **D (Observational)** | Audience identified, no effect claim | Considered | Anything that doesn't clear A/B/C bars |

**Today's engine** uses a muddled `measured | directional | targeting | weak` enum that conflates two axes. The redesign cleans this up.

---

## 8.5. The three orthogonal gates

A merchant DS asking "what makes a play surface?" sees three independent quality gates, each protecting a different failure mode. Two exist today; one is new.

| Gate | Question | Layer | Status |
|---|---|---|---|
| **Cohort p-value gate** | Is the cohort-level signal real, or is it noise? | MEASUREMENT (p < 0.05 on supporting metric + sign-agreement across L28/L56/L90) | Existing |
| **Validation status gate** | Can we defend the prior anchoring this play's revenue range? | SIZING (validation_status ∈ {validated_external, validated_internal, elicited_expert} → blend allowed; otherwise revenue suppressed) | Shipped in Sprint 7.5 |
| **ModelFitStatus gate** | Can we trust the ML model's per-customer scores on this merchant? | AUDIENCE (VALIDATED / PROVISIONAL / REFUSED based on holdout MAPE; on REFUSED, audience falls back to RFM quintile ranking) | New in Sprint 10-13 |

All three are independent. A play with strong cohort signal + heuristic_unvalidated prior surfaces in Recommended Now with suppressed revenue range. A play with validated prior + REFUSED ML fit surfaces with revenue range but RFM-ranked audience (no ML ranking). A play with everything passing surfaces fully — audience ranked by predicted LTV, revenue range with Bayesian-blended posterior, evidence chain auditable end-to-end.

**The p-value gate doesn't go away when ML is added.** ML scores measure per-customer prediction quality; p-values measure cohort-level signal stability. Different questions, different gates.

---

## 9. Which .md to read, for what

| File | What it is | Read when |
|---|---|---|
| **ENGINE_OVERVIEW.md** | This file — plain-English orientation | When you've lost the thread |
| **ENGINE.md** | Current architecture, technical | Reference for current code |
| **ARCHITECTURE_PLAN.md** | The redesign plan (Parts I, II, III) | Planning the next sprint or ticket |
| **agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md** | Revised Sprint 6-14 plan with ML layer + Phase 9 deferred | The current execution roadmap |
| **memory.md** | Chronological journal of every commit/decision | *Why* something is the way it is |
| **KNOWN_ISSUES.md** | Open gaps (KI-1 through KI-30) | What's broken and what's deferred |
| **docs/memory_substrate.md** | Sprint 1–5 SQLite event substrate spec | Substrate work |
| **docs/play_registry.md** | The 14 plays today | Play inventory |
| **docs/engine_validation_guide.md** | M0–M10 invariants enforced in tests | Test discipline |
| **CLAUDE.md** | Claude assistant config | Not a design doc |

If you only have time for one read: the **implementation-manager-s6-s14-revised-plan-ml-layer.md** is the most current execution roadmap. **ARCHITECTURE_PLAN.md** Part III is the design-level strategic state. This file (ENGINE_OVERVIEW.md) is the next-best orientation.

---

## 10. The honest summary

You have an **honest engine that doesn't say enough**. The fix is not to loosen its honesty — that would reintroduce the legacy problems. The fix is **two structural changes:**

1. **Give it more honest things to say at the cohort level** — build the 5 Tier-B measurement designs (Sprints 6-8).
2. **Give it more honest things to say at the customer level** — build the 5 ML predictive models running on existing CSV data (Sprints 10-13).

The other items (Bayes blend, Play Library, priors validation, JSON-only scope) make these two core changes safe, maintainable, and defensible.

**Beta success criterion: "month 1 wow → month 2 return."** Not 6-month outcome calibration. The merchant who tries the engine in month 1 sees a dense, ML-ranked slate grounded in their real data; in month 2 the engine refits on 30 more days of data and the slate evolves visibly. Phase 9 outcome calibration is the post-beta upgrade path, not the beta gate.

~15 weeks. 9 sprints (S6 → S14). After it, the engine speaks classical-ML language on the merchant's own data, ranks every audience, refuses to recommend when gates fail, and emits an audit-grade JSON contract that a skeptical merchant DS can trace from headline to feature.
