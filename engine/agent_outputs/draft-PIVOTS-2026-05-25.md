# PIVOTS — Journey-Critical Belief Changes

This doc captures the moments where what we *thought* was true got *proven* wrong, and what changed as a result. It is not a chronology (see memory.md), not current state (see STATE.md), not what's next (see ROADMAP.md). Append-only — one entry per pivot, rare.

A pivot earns an entry here only if:
1. A prior model was actively held (not just absent), and
2. Disconfirming evidence reversed it, and
3. The reversal locked a load-bearing invariant in code or process.

Mechanical refinements, additive architecture, and deferrals belong in memory.md or ROADMAP.md.

---

## Pivot 1 — Decision Core (V2) reframe
**Locked:** 2026-05-01
**Before:** The engine's job is to surface metrics and recommend plays based on weighted statistical votes. More signal = more output. Silence is failure.
**Learned:** A healthy ~$2M-ARR brand produced one actionable PRIMARY recommendation. The structural cap was plays-without-measurement-design, not gate tightness. Dashboards optimize for *coverage*; decision engines optimize for *defensibility*.
**Now:** The engine is a decision engine that abstains. Each play card carries an evidence class (Tier A/B/C/D), and abstention is a first-class output (ABSTAIN_SOFT, Considered/Watching lanes).
**Lock-in:** Evidence-class invariants; ABSTAIN_SOFT contract; Considered list as first-class output; no fabricated revenue projections to fill empty slates.
**Sources:** `agent_outputs/legacy-vs-v2-final-recommendation.md`, `agent_outputs/m0-m9-final-review-reconciled.md`, `memory.md` L42-74 (Reconciled Direction)

---

## Pivot 2 — Stop-Coding Line
**Locked:** 2026-05-05
**Before:** The engine owns the merchant-facing surface. `briefing.html` is the product; the engine's job includes phrasing, narration, copy, and visual rendering.
**Learned:** Embedding narration in the engine couples decision logic to presentation, and forces the engine to ship rhetorical commitments (projected lift language, copy templates) it cannot defend statistically. The agentic AI swarm needs typed inputs, not formatted HTML.
**Now:** `engine_run.json` is the product contract. The engine emits typed PlayCard fields (evidence, mechanism, audience definition, revenue range when defensible). `briefing.html` is debug-only and will retire when the frontend app ships. Narration is downstream.
**Lock-in:** Stop-Coding Line — no engine commits add copy, phrasing, or rendering logic. PlayCard schema in `src/engine_run.py` is the contract surface.
**Sources:** `agent_outputs/phase6b-stop-coding-line-reconciled.md`, `memory.md` L154-166

---

## Pivot 3 — Tier-B reframe (state_statistic is not evidence)
**Locked:** 2026-05-16
**Before:** Cohort-state statistics like `returning_customer_share` are valid Tier-B signals. If the number is high, the play is warranted.
**Learned:** A state statistic describes the store's *shape*, not the *effect* of an intervention. Recommending a winback play because "30% of customers are returning" confuses prevalence with causal opportunity — it scores the *substrate*, not the *action*. Plays must be grounded in intervention-shaped metrics (cohorts that received or could receive the intervention, with a measurable behavioral delta).
**Now:** `state_statistic` is forbidden as a Tier-B builder's `signal_kind`. Five new Tier-B builders ground evidence in cohort-level intervention metrics (winback_dormant, replenishment_due, aov_bundle, first_to_second, etc.).
**Lock-in:** Tier-B builder contract enforces intervention-shaped evidence; signal_kind enum rejects state_statistic at construction.
**Sources:** `ARCHITECTURE_PLAN.md` Part I §A and §B, `memory.md` S6 / S7 closeouts

---

## Pivot 4 — Priors validation gate (S7.5)
**Locked:** 2026-05-17
**Before:** If a prior is well-formed YAML with a source citation, it is admissible to the Empirical-Bayes blend. The math wraps around whatever number we provide.
**Learned:** Several priors had source citations that traced to industry-average rule-of-thumb numbers — not empirical anchors. Wrapping a heuristic in EB math produced posteriors that *looked* statistical but were the heuristic, laundered. The math compounds the lie.
**Now:** A `SOFT_PRIOR_UNVALIDATED` abstain status routes the play to Considered when its prior lacks an empirical anchor. Heuristic priors refuse the EB blend.
**Lock-in:** No fabricated priors dressed as math. Priors validation is a gate, not a label. Posterior pipelines reject unvalidated priors at blend time.
**Sources:** `ARCHITECTURE_PLAN.md` Part III-1, `memory.md` S7.5 entries L403-530

---

## Pivot 5 — Synthetic-fixture honesty rule
**Locked:** 2026-05-22
**Before:** When a builder didn't fire on the test fixture, reshape the fixture so the builder fires. The goal of fixtures is coverage — exercise every code path.
**Learned:** A fixture reshaped to make a builder fire is no longer a fixture of a real store; it's a fixture of a store that *needs* this builder. The engine then optimizes against a store that doesn't exist. The S7.6 T2.5 escalation surfaced this: honest dormancy of `replenishment_due` on a Beauty fixture is a *product signal*, not a test gap.
**Now:** Honest dormancy is the product. When a builder doesn't fire on a real-shaped fixture, that's the answer — the store doesn't have the opportunity. Don't reshape fixtures to fire builders.
**Lock-in:** Fixtures derive from real Shopify export shapes; builder dormancy on a fixture is information, not a bug. Test design prefers an honest miss over a synthetic hit.
**Sources:** `memory.md` L1615-1632 (T2.5 escalation verdict)

---

## Pivot 6 — Instrumentation-over-prediction
**Locked:** 2026-05-22 / 2026-05-23
**Before:** When debugging a refactor, agents reason from a mental model of the code: predict where the card dies, fix that gate, move on.
**Learned:** The S7.6 T7.5 spiral: three consecutive predictions about where a Tier-B card was being dropped were each wrong. Each "fix" addressed a gate that wasn't the actual gate. Only direct in-process instrumentation (logging at every checkpoint in the live pipeline) found the real failure. Mental-model debugging compounds error; instrumentation collapses it. When two docs or two mental-models disagree, the running code is the tiebreaker.
**Now:** Two failed predictions = stop guessing, instrument. Subagents do not commit a fix based on a third mental-model guess. Production code is the third witness when documents disagree.
**Lock-in:** Subagent Handoff Discipline Rules 1, 2, 5 in `CLAUDE.md` L27-46. "Never assume. If a prediction conflicts with what the code does, instrument and verify before committing a fix."
**Sources:** `CLAUDE.md` L37-46, `memory.md` S7.6 key learnings L1764-1775, `agent_outputs/ecommerce-ds-architect-s8-t0-scipy-percentile-followup-2026-05-24.md`

---

## Pivot 7 — Single-demote-channel invariant
**Locked:** 2026-05-22
**Before:** Multiple injection blocks in `src/main.py` could append to `engine_run.recommendations` after `apply_guardrails` ran — each block adding its own demotions, fallbacks, or load-bearing pins post-hoc.
**Learned:** Post-guardrails injection re-introduced cards that guardrails had explicitly removed, and bypassed the contract that every recommendation pass through the same gating. Three orthogonal demote channels were ad-hoc reinventing each other. The guardrail wasn't a guardrail — it was a suggestion.
**Now:** All demote paths route through `apply_guardrails_to_injected` (introduced S7.6 C2). `priority_prepend` covers the three demote channels uniformly. No new injection blocks at `src/main.py:1380-1597` without founder + DS sign-off documented in the architectural plan.
**Lock-in:** Single-demote-channel invariant (DS-locked). Pinned by `tests/test_s7_6_c1_priority_prepend_invariant.py`. CLAUDE.md L41-46 enforces sign-off.
**Sources:** `ARCHITECTURE_PLAN.md` 2026-05-22 LOAD-BEARING UPDATE block, `memory.md` S7.6 close L1645-1708

---

## Pivot 8 — Beta success reframe (month-1-wow → month-2-return)
**Locked:** 2026-05-17
**Before:** Beta success = a 6-month outcome calibration loop that proves the engine's recommendations produced revenue lift. Phase 9 (outcome import + recalibration) is the gate to PMF.
**Learned:** No merchant returns to month 6 to validate month 1. The first 30 days must produce visible, defensible value (month-1-wow), and month 2 must produce *new* value derived from 30 more days of data — not from realized outcomes the merchant hasn't even imported yet. The outcome loop is the *causal proof*, not the *retention engine*.
**Now:** Beta success = month-1-wow (defensible slate on first run) + month-2-return (ML refit on 30 more days produces materially different/better recommendations). Phase 9 outcome loop is deferred post-beta. ML predictive layer (audience ranking, not play sourcing) is pulled into beta scope.
**Lock-in:** Sprint sequence prioritizes ML-as-audience-ranking over Phase 9. ModelFitStatus gate; ML never adds plays, only ranks customers within a play's audience.
**Sources:** `ENGINE_OVERVIEW.md` §6 and §10, `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md`

---

## Dropped candidates (why these aren't entries)

Four candidates from the audit's original 12 were dropped per the Revisions section's "belief-changes only" criterion:

- **Store Profile Layer** — an *additive* architectural step (PROFILE-first pipeline), not a reversed prior. Nothing was disconfirmed; we added a layer. Belongs in STATE.md as pipeline description. Source `agent_outputs/ds-architect-store-profile-layer-proposal.md` cited from STATE.md.
- **i1-spike-findings / D-7 affinity** — a deferral pointer, not a belief-change. Belongs in ROADMAP.md as a deferred-spec reference. Source `agent_outputs/i1-spike-findings.md` cited from ROADMAP.md.
- **S14-readiness lens** — a methodological *rubric* for evaluating priors verdicts. A refinement of how to apply Pivots 1 + 4, not a new pivot. Lives in the originating verdict (S8 pseudo_N verdict).
- **Production code is the third witness** — the same belief as Pivot 6 (Instrumentation-over-prediction), expressed for the documents-disagree case. Folded into Pivot 6 rather than double-counted.

---

# Sources

Consolidated list of files cited in the entries above:
- `agent_outputs/legacy-vs-v2-final-recommendation.md`
- `agent_outputs/m0-m9-final-review-reconciled.md`
- `agent_outputs/phase6b-stop-coding-line-reconciled.md`
- `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md`
- `agent_outputs/ecommerce-ds-architect-s8-t0-scipy-percentile-followup-2026-05-24.md`
- `ARCHITECTURE_PLAN.md` (Part I §A/§B; Part III-1; 2026-05-22 LOAD-BEARING UPDATE block)
- `ENGINE_OVERVIEW.md` (§6, §10)
- `CLAUDE.md` (L27-46)
- `memory.md` (L42-74, L154-166, L403-530, L1615-1632, L1645-1708, L1764-1775)
- `tests/test_s7_6_c1_priority_prepend_invariant.py`
- `src/engine_run.py` (PlayCard schema, contract surface)
- `src/main.py` (L1380-1597, injection-block forbidden zone)
