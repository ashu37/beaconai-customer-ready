# ROADMAP — BeaconAI

**Cadence:** live; refreshed per sprint plan / sprint close.
**Last refresh:** 2026-05-25 (post-S8 close, pre-S9 dispatch).
**Replaces:** `ARCHITECTURE_PLAN.md` Part II sequencing + "What This Plan Does NOT Do" L88-98.

For "why this sequence" see `PIVOTS.md`. For open behavior/contract issues see `KNOWN_ISSUES.md`. For the present-tense engine description see `STATE.md`.

---

## 1. Current sprint

**Sprint 10 — ML Predictive Layer Part 1.** PAUSED pending completion of the docs migration (PRODUCT / STATE / PIVOTS / ROADMAP / INDEX). IM dispatch will fire once the new active read path lands and CLAUDE.md Doc Map is updated.

**S8 just closed.** Sprint 8 shipped:
- Typed `evidence_source` chip + typed `sensitivity` block + typed `provenance` object on `PlayCard` (additive within `event_version=1`).
- EB blend layer in `sizing.py` — contract live; full payoff dormant until outcome ingestion (S15+).
- Play Library wave 1 — 3 of 14 plays folded into `plays/<play_id>/` layout. Byte-identical behavior.

**S10 anchor goals (queued, not yet dispatched):**
1. BG/NBD model fit per merchant (Fader/Hardie classical) producing per-customer P(alive) + expected-transactions.
2. Gamma-Gamma monetary-value fit producing per-customer expected-revenue, gated on BG/NBD acceptance.
3. `ModelFitStatus` 3rd-gate (VALIDATED / PROVISIONAL / REFUSED) — joins cohort-p and priors-validation as the third orthogonal gate.

ML predictive layer lives in the AUDIENCE step of the pipeline — it does not add plays; it ranks customers within each play's audience.

---

## 2. Beta-blocking sequence (S9 → S14)

Refreshed post-S8 from `ENGINE_OVERVIEW.md` §6 and `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md`. Target: private beta launch at S14 close, ~12 wall-clock weeks from S9 kickoff.

| Sprint | Scope (one line) | Beta-critical? |
|---|---|---|
| **S9** | post-beta lifecycle/cleanup (deferred) — store-profile-as-learned-artifact, Play Library wave 2, play lifecycle prerequisite | no — post-beta deferred (out of beta-critical sequence; picks up after S14) |
| **S10** | ML Predictive Layer Part 1 — BG/NBD + Gamma-Gamma + `ModelFitStatus` 3rd-gate | yes — month-1 wow surface |
| **S11** | ML Predictive Layer Part 2 — survival (`lifelines`) + collaborative filtering (`implicit`) | yes — drives `replenishment_due` ranking |
| **S12** | ML Predictive Layer Part 3 — statistical RFM + cohort retention curves with bootstrapped CIs | yes — month-2 return surface |
| **S13** | Integration — ML feeds AUDIENCE via `ranking_strategy`; `predicted_segment` + `model_card_ref` on PlayCard; `month_2_delta` typed slot | yes — last beta-critical sprint |
| **S14** | Private beta launch — onboard 1–2 hand-picked merchants; calibration report; KI-30-class fixes | yes — gating |

**Ordering rationale (load-bearing):** affinity-then-survival-then-uplift sequencing per `agent_outputs/beacon-ml-roadmap-reconciled-review.md`. ML predictive layer (S10-S13) is the beta-blocking sequence. Lifecycle work in S9 is the post-beta learning loop that compounds month-over-month — month-2-return value comes from the ML refit on 30 more days of data, not from lifecycle infrastructure. ML predictive layer lives in the AUDIENCE step of the pipeline — it does not add plays; it ranks customers within each play's audience.

**Three orthogonal gates** preserved across the sequence: cohort p-value (per builder), priors `validation_status` (per prior, S7.5 contract), `ModelFitStatus` (per model, S10+).

---

## 3. Carry-forward items from S8

Per DS S8-scope verdict on the S8 plan (`agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md`) these are NOT process residue — they carry into S9 / S10 work:

1. **EB blend full payoff gated on Phase 9 outcome ingestion (S15+).** S8 shipped the contract; the math earns its keep only with multi-month feedback. Documented honestly in the S8 close.
2. **Play Library wave 2+ migration — post-beta.** S8 wave 1 covered 3 of 14 plays. Waves 2+ fold into the S9 post-beta lifecycle/cleanup window alongside KI-NEW-L (registry-driven dispatch replaces 5 injection blocks organically).
3. **KI-NEW-L / M / N — anchored S13.5 + S14-T3.** KI-NEW-L collapses 5 V2 prior-anchored injection blocks at `src/main.py:1380-1597` into a single PRIOR_ANCHORED dispatch — scheduled S13.5 per memory.md L1921 commitment (between S13-T4 atomic flip and S14-T1 beta-launch dispatch). KI-NEW-M/N — `_dedupe_rejections` typed-code priority policy and experiment-promotion provenance preserve — both deferred to S14-T3 post-beta-merchant-feedback.
4. **`evidence_source` chip + `sensitivity` block frontend consumption deferred.** Both ship in `engine_run.json` at S8 close. The renderer surface (debug HTML today, future frontend app) does not yet display either. Deferred until the frontend app activates.
5. **S10–S13 ML predictive layer extends `predicted_segment` + `model_card_ref` stubs additively** on the S8 typed surface. The S8 chip / sensitivity / provenance contract is the substrate the ML cards pattern-match against.

---

## 4. Post-beta deferrals (S15+)

Confirmed deferred — not part of the beta-blocking sequence:

- **Phase 9 outcome ingestion loop** (`outcome_observed` importer + calibration writer + last-month-outcome briefing surface). Entry conditions tracked at `KNOWN_ISSUES.md::KI-1` through `KI-5`. Was the previous plan's S10; reframed post-beta. Payoff window is month 3+ of installed-base data.
- **Causal uplift modeling.** Requires accumulated Phase 9 outcome rows. Post-PMF.
- **Klaviyo API / Shopify network calls.** D-5 forbids in v1. Manual JSON import only. AWS migration is the right moment to revisit.
- **Trust-math operator tooling** (replay CLI, backtest, sensitivity-audit CLIs). Founder-internal, not merchant-facing.
- **Portfolio optimization** (S22+).
- **LLM mechanism generation** (S26+).
- **Multi-channel / federated learning.** Far post-PMF.
- **V2 legacy cleanup workstream.** Until the legacy pipeline becomes a maintenance burden — not before.
- **Cross-merchant pooling for sub-threshold-N merchants** (BG/NBD / Cox PH cold-start floor). Privacy + multi-tenancy implications unscoped.
- **Substrate disk growth optimization / TTLs.** No retention limits today (per D-2 forever-retention). AWS migration time.

---

## 5. What we are NOT building

Distilled from `ARCHITECTURE_PLAN.md` "What This Plan Does NOT Do" L88-98, founder decisions D-1..D-8, and the reconciled ML-roadmap review. These are permanent non-goals within the beta scope.

**Vertical and product scope:**
- **No vertical expansion.** Hard-locked at `{beauty, supplements, mixed}` per D-8. `mixed` means literal beauty+supplements blend, NOT unknown-vertical fallback. Refused at engine entry.
- **No frontend app inside engine scope.** Engine emits typed `engine_run.json`; the frontend renderer is downstream. `briefing.html` is debug-only and retires when the frontend activates.
- **No agentic narration / copy generation in the engine.** Per the Phase 6B Stop-Coding Line — framing, narration, mechanism phrasing is the downstream agent swarm's job. Engine emits typed fields.

**Statistical / claim discipline:**
- **No fabricated outcome inference.** Engine cannot claim a recommendation "worked" or "didn't work" without realized campaign data. See `play-lifecycle-discussion-reconciled.md` §"Product / Science Boundary".
- **No "calibrated" or uplift terminology in merchant-facing copy** absent measured holdout data.
- **No `confidence_score`, `final_score`, BeaconAI score**, or numeric confidence percentages in V2 surface.
- **No multi-window min-p cherry-picking.** Replaced by sign-agreement + combined statistics.
- **No "learning" `CONFIDENCE_MODE`** that relaxes thresholds.

**ML scope (D-N banned use cases):**
- **No ML for outcome claims** without realized outcome data. ML scores per customer feed AUDIENCE ranking, not measured-effect claims.
- **No neural / RL / uplift models in beta.** Classical Fader/Hardie + Kaplan-Meier + Cox PH + ALS + RFM only — the D-6 carve-out is peer-reviewed-classical only.
- **No cross-merchant pooling.** Per-merchant, per-vertical fits only. Privacy posture per D-2.
- **No per-customer scores in `engine_run.json`.** Parquet artifacts under `data/<store_id>/predictive/` only. Audience-aggregate summaries reach the JSON.

**Integration scope:**
- **No Klaviyo / Shopify network calls** in the local engine path. D-5 manual import only.
- **No automatic campaign send.** Merchant approval gate is hard, even post-integration.
- **No PII in predictive artifacts.** `customer_id` only.

**Process scope:**
- **No big-bang rewrites.** Every sprint ships a runnable engine.
- **No reshaping synthetic fixtures to fire builders.** Honest dormancy is the product (S7.6 synthetic-fixture honesty rule).

---

## 6. Pointers

- **Open behavior / contract issues:** `KNOWN_ISSUES.md` (KI-1..KI-5 = Phase 9 entry conditions; KI-NEW-L anchored at S13.5; KI-NEW-M/N anchored at S14-T3 post-beta-merchant-feedback).
- **Why this sequence (founder bends in the river):** `PIVOTS.md` — especially the beta success reframe (month-1-wow + month-2-return), the ML-as-audience-ranking pivot, and the lifecycle-before-ML ordering.
- **Present-tense engine description:** `STATE.md`.
- **Product / merchant journey / future state:** `PRODUCT.md`.
- **Active execution roadmap (authoritative parent):** `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md`.
- **S9 lifecycle prerequisite framing:** `agent_outputs/play-lifecycle-discussion-reconciled.md`.
- **ML sprint ordering rationale:** `agent_outputs/beacon-ml-roadmap-reconciled-review.md`.
- **S8 carry-forward source verdict:** `agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md`.

---

## Sources

- `ENGINE_OVERVIEW.md` §6 redesign plan + table (lines 88-117).
- `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` — authoritative S6–S14 roadmap (current execution plan).
- `agent_outputs/implementation-manager-s8-trust-surface-eb-blend-plan.md` — S8 plan with the 6 carry-forward items above.
- `agent_outputs/beacon-ml-roadmap-reconciled-review.md` — load-bearing for ML sprint ordering (affinity-then-survival-then-uplift; lifecycle ships before ML).
- `agent_outputs/play-lifecycle-discussion-reconciled.md` — load-bearing for Sprint 9 lifecycle prerequisite (audience-stability + lineage-key + outcome-seam discipline).
- `ARCHITECTURE_PLAN.md` "What This Plan Does NOT Do" L88-98 — distilled into the deferrals + non-goals sections.
- `KNOWN_ISSUES.md` for KI-NEW-L/M/N and Phase 9 entry conditions (KI-1..KI-5).
- `memory.md` last two sprints (S7.6, S8) for active sprint status; founder decisions D-1..D-8 at L173-182.
- `agent_outputs/ecommerce-ds-architect-doc-audit-2026-05-24.md` — Revisions section for the doc-migration trigger that paused S9 dispatch.
