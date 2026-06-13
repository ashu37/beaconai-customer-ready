# DS Architect Verdict — S10 ML Part 1 Plan

**Date:** 2026-05-25
**Plan under review:** `agent_outputs/implementation-manager-s10-ml-part1-plan.md`
**Reviewer:** ecommerce-ds-architect (dispatched by orchestrator)
**Verdict:** **PASS-WITH-CHANGES**

The plan is structurally sound, faithful to the new active read path (PRODUCT/STATE/PIVOTS/ROADMAP), respects Pivot 5 (no fixture-gaming), Pivot 7 (single-demote-channel), and the S8 schema-additive discipline. Three classes of changes are required before code dispatch:

1. Tighten the ModelFitStatus threshold story so it is honestly labeled as speculative-until-S14, not validated.
2. Reframe the Gamma-Gamma Pearson-r test as a structural sanity check rather than an authoritative independence test.
3. Remove the implicit promise that Beauty will fit VALIDATED at T1.5 — Pivot 5 forces (b) PROVISIONAL, not (a) fixture expansion (unless a pre-T1 measurement spike confirms VALIDATED naturally).

---

## A. Documentation framing findings

**A1. New active read path citation — PASS.** Plan header L8 cites "Parent active read path: PRODUCT.md, STATE.md, PIVOTS.md, ROADMAP.md" and does not reference `ENGINE.md` or `ARCHITECTURE_PLAN.md` as live sources. All Part A framing claims are sourced to PRODUCT/STATE/PIVOTS/ROADMAP. NIT: Part L still names `briefing.html` without re-confirming "debug-only retires when frontend ships" — minor; STATE.md §2 already pins that. NIT: Sources section L573–581 cites `ARCHITECTURE_PLAN.md` derivatives via `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md`; that is legitimate (parent plan is still the authoritative S6-S14 execution doc per ROADMAP §6), but the plan should add a sentence acknowledging ENGINE.md is retired to `docs/legacy/`.

**A2. Documentation Discipline (verbatim quotes, addenda, immutable identifiers, cross-refs) — PASS-WITH-NIT.** Verbatim-quote discipline is honored (ROADMAP L20–25, PIVOTS L84–90, play-lifecycle-discussion-reconciled L47, parent plan L131 carve-out, memory.md L1921). Sprint/KI identifiers (S10, S13, S13.5, S14-T3, KI-NEW-L/M/N) preserved exactly. **Addendum 2 acknowledgment is weak**: Sources cites Addendum 2 L665–715 but the plan body never explicitly states the linear-sequencing supersession or how S10 sits inside the two-track structure. Add one sentence in Part A.1 acknowledging "Addendum 2 supersedes the linear Phase 7→8→9 sequencing; S10 sits on the BEACON-TRACK substrate side, and the SWARM track consumes the S10 ModelCard schemas as frozen contracts."

**A3. memory.md template-shape rule — PASS.** Plan Part D L201 and Part K L493 explicitly route narrative into `agent_outputs/code-refactor-engineer-s10-t{...}-summary.md` and route memory.md to template-shape entries only. Part N L551 reiterates "memory.md — entries only at sprint close, template-shape per CLAUDE.md rule."

**A4. Per-ticket load-bearing invariant pins — PASS-WITH-NIT.** Pins are present (T1 closed-enum + event_version=1, T1.5 atomic-flip + rollback, T2 chained refusal, T3 three-orthogonal-gate). The **single-demote-channel invariant** is acknowledged at E.1 L325 ("S10 does not inject anything to `engine_run.recommendations`") but T0's fatigue fix needs a one-line explicit confirmation. T0 modifies `src/guardrails.py:632` (the `gate_recently_run` function, not L604 as both the plan and reconciled review say — L604 is a stale comment header; the real callsite of the fatigue match logic is L632–716). Re-keying the match is upstream of `apply_guardrails`; it does NOT append to `engine_run.recommendations` post-guardrails. T0 must carry: "Deviation check: none. Single-demote-channel invariant unaffected — gate_recently_run runs inside the guardrails pass and produces a RejectedPlay, not a post-guardrails injection." Add this verbatim to T0 acceptance.

**A5. Deviation-check discipline — PARTIAL PASS.** T0 carries "Deviation check: none" (L168). T1–T3 do not. Add the line per ticket; founder-locked work (T0 fatigue is DS-locked correctness) requires the per-commit line per CLAUDE.md L42.

---

## B. DS architecture findings

**B1. `lifetimes` library choice — PASS-WITH-RISK-ACKNOWLEDGED.** `lifetimes` is the right *math surface* (Fader/Hardie BG/NBD + Schmittlein-Morrison-Colombo Gamma-Gamma); the underlying derivations are 2005-2010, the math is stable, and the package is small enough to vendor-fork. The "in maintenance mode, last release ~2020" risk is real but containable (§C.1, §E.3). `pymc-marketing` would buy posterior credible intervals at heavy-dep cost (PyMC + PyTensor + macOS-ARM build pain) for no operational gain in S10 — ModelCards do not surface CIs at S10 close anyway. **Recommendation: ship `lifetimes`.** Lock the `scipy<1.13` pin pre-emptively as a follow-up dependency note (§E.3 L344 flags this); make it a hard pin in T1's `requirements.txt`, not a "verify."

**B2. Gamma-Gamma Pearson-r independence check — PASS-WITH-CHANGES (REQUIRED).** The Fader-Hardie-Lee 2005 derivation assumes monetary value is independent of purchase frequency *at the customer level*. Pearson-r on (frequency, monetary) per customer is a directionally correct sanity check, **but it is not the formal independence test**. It catches the gross-failure case (high systematic correlation) and misses subtle non-linear dependence. Required changes:
- Reframe in the plan and ModelCard `fit_warnings` from "independence check" to **"frequency-monetary correlation sanity check"** — label-only.
- Threshold `|r| > 0.3 → PROVISIONAL` and `|r| > 0.5 → REFUSED` are defensible *as conservative cutoffs*, not as theoretical thresholds. Document them in the ModelCard schema as advisory.
- Chained refusal of Gamma-Gamma when BG/NBD is REFUSED is non-negotiable and correctly stated (L262).

**B3. ModelFitStatus as third orthogonal gate — PASS.** The gate is genuinely orthogonal to the existing two:
- Cohort p-value gate (MEASUREMENT) tests whether *this store* shows a signal for an *intervention-shaped cohort*.
- Validation-status gate (SIZING) tests whether the *prior* is empirically anchored.
- ModelFitStatus (AUDIENCE) tests whether *per-customer scores* from the predictive model are trustworthy on this merchant's data.

The three failure modes do not collapse into each other. A store can clear cohort-p, clear priors-validation, and still REFUSE on ModelFitStatus (cold-start) or vice versa. **Concern: a small store will tend to fail multiple gates simultaneously (audience floor + cohort-p + ModelFitStatus all reflect "not enough data"), which is correlation, not redundancy.** The gate-precedence test in T3 (Part G acceptance #4) is the right mitigation — when multiple gates fail, ReasonCode emits exactly one, matched to highest precedence. Confirm precedence order is (1) audience-floor → (2) cohort p-value → (3) prior-validation → (4) ML-fit. The plan asserts this at L284; it must match what `src/decide.py` actually returns. Verify before T3 lands.

**B4. Cold-start risk on Beauty fixture — PASS-WITH-CHANGES (REQUIRED).** The plan correctly recommends path (b) — accept PROVISIONAL on Beauty rather than expand the fixture — per Pivot 5 (§J Q4 L460–465). However, **§G.1 L380 contradicts this** by listing as a month-1-wow deliverable: `predictive_models.bgnbd.fit_status="VALIDATED"` on Beauty. Either:
- (i) Demote G.1 L380 to read `fit_status="PROVISIONAL"` and re-pin Beauty acceptance criterion #1 (L399) to `test_beauty_provisional`, OR
- (ii) Conduct a pre-T1 measurement spike on the existing Beauty fixture (sha `f8676c9f…`) to count repeat customers + orders, document the result, and only then choose VALIDATED vs PROVISIONAL — but if measurement returns "≥500 repeat / ≥1500 orders" naturally without fixture reshape, VALIDATED is honest.

**Recommend (ii) — a 30-minute measurement before T1 design** rather than ship a contradiction. Whatever the measurement returns is the honest pin. If Beauty cannot clear VALIDATED naturally, accept PROVISIONAL and adjust §G.1.

**On the broader question (is REFUSED the correct cold-start default?):** PROVISIONAL is correct as the middle band when a fit *converges* but the data envelope is thin. REFUSED should be reserved for: (a) fit raises ConvergenceWarning, (b) holdout MAPE > 40%, (c) below the absolute floor (3 months / 200 repeat customers / 500 orders). The plan's tri-state threshold table at §C.3 L111–116 is defensible. Required change: explicitly state in the ModelCard that PROVISIONAL means **"fit converged, envelope thin, ranking may be ordered correctly but absolute LTV magnitudes should not be quoted to merchant."** This is load-bearing for S13 audience-builder consumption — a PROVISIONAL fit is usable for ranking, REFUSED is not.

**B5. Lineage-keyed fatigue (T0) — PASS.** Verified that `src/memory/lineage.py::compute_lineage_id` (L28–63) already requires four components: `store_id`, `play_id`, `audience_definition_id`, `audience_definition_version`. All four are REQUIRED args (raises ValueError on missing). The S3 lineage schema is honored. Adding `audience_definition_version` to the fatigue match key is the correct shape and collapses cleanly with S3.

**Byte-identity on existing fixtures:** `RECENTLY_RUN_FATIGUE_ENABLED` defaults OFF (STATE.md §6); `gate_recently_run` is called only when the flag is on. T0 is byte-identical by construction because the flag stays OFF — the modified code path is not exercised in pinned fixture runs. The test plan (§F L156–161) correctly notes this. **NIT:** Confirm in T0 acceptance that no `recommended_history.json` file exists in the pinned fixtures' working directory at run time (existence of an empty file would still no-op via `_read_recommended_history` L610–629, so this is belt-and-braces).

**Real callsite note (already flagged in A4):** The plan references `src/guardrails.py:604` from the reconciled review. The actual `gate_recently_run` body starts at L632; L604 is a stale comment header. T0 should target L632–716 and the match-key tuple inside.

**B6. Atomic flip cadence + byte-identity contract — PASS.** Two separate flips (T1.5 for BG/NBD, T2.5 for G-G) is the right granularity, not a single combined flip:
- BG/NBD can succeed standalone; G-G can fail independently via the Pearson sanity check even when BG/NBD passes.
- The chained-refusal contract (G-G REFUSED when BG/NBD REFUSED) is asserted at the *model* layer, not at the *flag* layer — flag independence preserves operator escape hatches.
- This mirrors S8's three independent additive PlayCard fields, each its own flag (STATE.md §6 L116).

**B7. Month-1-wow / month-2-return acceptance — PASS.** The plan correctly states S10 ships substrate (ModelCards + parquet), not visible-in-card month-1-wow (§G.1 L386). Visible artifacts land at S13-T1/T3. **However**, the plan should commit to one visible artifact at S10 close: the **ModelCard surfaced inside `engine_run.json.predictive_models`** is itself a visible artifact for a frontend or operator inspection. Operator-facing tooling could read ModelCards today without S13. Recommend a one-line clarification in G.1: "S10 ships ModelCards as the first visible model-derived JSON object; PlayCard-level visibility lands at S13." This protects the wow story without overpromising.

**B8. PlayCard additive contract — PASS.** Verified at the code level (Part A.3 grep findings L40–48). `PlayCard.predicted_segment` and `PlayCard.model_card_ref` already exist as `Optional[...]=None` on disk. T1 *populates* the existing `ModelCardRef` dataclass at `src/engine_run.py:771` rather than introducing it. No `event_version` bump required. `predictive_models` lands on `engine_run` (not `PlayCard`), so the S8 DS invariant 12 trust-surface PlayCard field cap is not breached (E.4 L355 correctly notes this).

**B9. Three KI candidates P/Q/R — PASS-WITH-NIT.**
- **KI-NEW-P (ModelFitStatus thresholds speculative until S14):** legitimate, parallel to KI-NEW-C (`pseudo_n_default` per-stage recalibration). File it. Same shape as KI-NEW-C — a calibration that waits for real-merchant data.
- **KI-NEW-Q (no operator query CLI for parquet):** legitimate, but might already be covered by post-beta tooling deferrals (ROADMAP §4 "Trust-math operator tooling"). Confirm scope before opening.
- **KI-NEW-R (`lifetimes` maintenance risk):** legitimate, file it. The vendor-fork escape hatch should be a documented procedure, not just a comment.

None duplicate an existing KI. Recommend opening all three at S10-T3 close (before sprint review), not pre-dispatch.

---

## C. Open-question recommendations (Part J)

**J.1 Q1 — Lineage-keyed fatigue in S10-T0.** Confirm: do it at T0. The DS-locked language "correctness bug regardless of broader lifecycle scope" (`agent_outputs/play-lifecycle-discussion-reconciled.md:47`) is not soft. Bundling at T0 avoids a stranded correctness ticket in S12. The 1-day envelope and OFF-flag dormancy make it cheap. **DS confirms.**

**J.2 Q2 — `lifetimes` over `pymc-marketing`.** Confirm `lifetimes`. PyMC posterior is overkill for S10 (no CI consumer until S13+). Heavy-dep risk on macOS-ARM is real. **DS confirms.**

**J.3 Q3 — ModelFitStatus thresholds.** **Founder + DS sign-off required before T1 dispatch.** Recommended thresholds (refined from §C.3):
- VALIDATED: ≥6 months data ∧ ≥500 repeat customers ∧ ≥1500 orders ∧ holdout MAPE < 25% ∧ no ConvergenceWarning
- PROVISIONAL: (3–6 months) ∨ (200–499 repeat) ∨ (500–1499 orders) ∨ (holdout MAPE 25–40%) — any one disqualifier from VALIDATED while above the floor
- REFUSED: < 3 months ∨ < 200 repeat ∨ < 500 orders ∨ holdout MAPE > 40% ∨ ConvergenceWarning raised

File the thresholds as KI-NEW-P (calibration speculative until S14). Document explicitly that thresholds are *operator-tightenable via YAML*, not hardcoded — matches the `pseudo_n_default` pattern from S8.

**J.4 Q4 — Beauty fixture cold-start clearance.** Per Pivot 5: **path (b) PROVISIONAL** unless a pre-T1 measurement spike shows the existing Beauty fixture (sha `f8676c9f…`) naturally carries ≥500 repeat customers + ≥1500 orders. If it does, ship VALIDATED honestly. If it doesn't, accept PROVISIONAL. **Do not reshape the fixture.** Run the measurement spike before T1 design — 30 minutes — to resolve §G.1 L380 contradiction with §J Q4 L463.

**J.5 Q5 — Privacy envelope.** Confirm: per-customer scores stay in parquet, only ModelCards in JSON. Load-bearing for D-2 / D-3 deletion semantics. The store-wipe unit (per-store `data/<store_id>/`) cleanly subsumes parquet artifacts. **DS confirms.**

**J.6 Q6 — Parquet schema versioning.** Confirm: ship `parquet_schema_version=1` at T1.5. S11 (survival) and S12 (CF) will add columns; explicit version makes forward-compat assertions trivial. Cost is one int column; benefit is the only honest way to evolve a binary on-disk schema without break.

---

## Required changes before code dispatch

1. **A2.** Add explicit one-sentence acknowledgment of Addendum 2 supersession of linear sequencing in Part A.1.
2. **A4.** T0 ticket carries verbatim "Deviation check: none. Single-demote-channel invariant unaffected — `gate_recently_run` runs inside the guardrails pass and produces a `RejectedPlay`, not a post-guardrails injection."
3. **A5.** Add "Deviation check: none" line to T1, T1.5, T2, T2.5, T3 ticket bodies.
4. **A4 / B5.** Correct `src/guardrails.py:604` reference to `src/guardrails.py:632` (function body) in the plan. The reconciled review's L604 is a stale section header.
5. **B2.** Relabel Pearson-r as "frequency-monetary correlation sanity check" in plan §C.2 L107 and in ModelCard `fit_warnings` value (`"frequency_monetary_correlation"` is already directionally good — keep). Threshold values stay.
6. **B4.** Resolve §G.1 L380 ↔ §J Q4 L463 contradiction: run a pre-T1 measurement spike on Beauty fixture to count repeat customers + orders. Pin acceptance criterion #1 (L399) to whichever fit_status the measurement honestly returns. Default if measurement uncertain: PROVISIONAL.
7. **B4.** Add to ModelCard schema definition: PROVISIONAL semantics = "fit converged, envelope thin, ranking usable, absolute magnitudes not quotable."
8. **B7.** Add one-line clarification at §G.1 L386: ModelCards in `engine_run.predictive_models` are themselves the first visible model-derived JSON object — operator-readable at S10 close.
9. **J.3.** Founder sign-off on ModelFitStatus thresholds before T1 dispatch. File KI-NEW-P alongside.

---

## Recommendations (non-blocking)

- **R1.** Document the `lifetimes` vendor-fork escape hatch as a one-page procedure in `docs/` (not just a comment in T1 summary). Names the fork branch, the smoke-test command, the rollback path. Cheap insurance.
- **R2.** Pre-commit hard-pin `scipy<1.13` in `requirements.txt` as part of T1, not just "verify" per §E.3 L344.
- **R3.** Consider adding a `model_card.fit_diagnostics` block carrying (BG/NBD r/α/s/β; G-G p/q/γ) at S10-T1, even if no consumer yet. Operator audit value is high; cost is one dict. The plan already plumbs `parameters: Dict[str, float]` (L181) — good.
- **R4.** Pre-S11 forward-compat: name the parquet columns now with the S11/S12 additive columns in mind (e.g., `expected_purchases_30d` not `expected_purchases`). The plan does this (L210, L240). Confirm S11 (survival hazard at 30d/180d) and S12 (RFM quintile) name-mate cleanly.
- **R5.** Briefing.html should be byte-identical pre/post-S10 in all tickets. T1.5 acceptance L223 says so; confirm by sha. The renderer does not yet read `predictive_models`.
- **R6.** S10-T3's `MODEL_FIT_REFUSED` enum value lands dormant. Recommend a comment in `src/engine_run.py` flagging "reserved for S13-T1 audience-builder ranking_strategy refusal path; do not consume in S10–S12."

---

## Summary

**Verdict: PASS-WITH-CHANGES.** The S10 plan is structurally sound and faithfully tracks the new active read path (PRODUCT/STATE/PIVOTS/ROADMAP). It correctly retires implicit references to ENGINE.md / ARCHITECTURE_PLAN.md, preserves immutable sprint and KI identifiers (S10, S13, S13.5, S14-T3, KI-NEW-L/M/N), routes narrative to summary files per memory.md template-shape discipline, and honors load-bearing invariants (Pivot 5 fixture-honesty, Pivot 7 single-demote-channel, S8 schema-additive cap). Addendum 2 (L665–715) is cited but needs one-sentence in-body acknowledgment of the supersession of linear sequencing. The plan correctly populates the existing `predicted_segment` / `model_card_ref` stubs at `src/engine_run.py` rather than introducing them, preserving the `event_version=1` additive contract.

**Top three DS concerns.** **(1) Gamma-Gamma "independence check" is a Pearson-r sanity check, not a theoretical independence test** — relabel; thresholds stay. **(2) The §G.1 "Beauty VALIDATED" wow claim contradicts §J Q4's Pivot-5-correct PROVISIONAL recommendation** — run a 30-minute pre-T1 measurement spike on Beauty fixture `f8676c9f…` and pin acceptance to whatever it honestly returns; do not reshape the fixture. **(3) ModelFitStatus thresholds are speculative-until-S14 and need explicit founder sign-off plus KI-NEW-P filing** before T1 dispatch — the numbers feed the audit story directly, and they should be YAML-overrideable per the `pseudo_n_default` pattern, not hardcoded.

**Resolution of the six open questions in Part J.** Q1 (T0 vs S12 fatigue): confirm T0 — DS-locked correctness bug, 1-day envelope, lineage helper exists. Q2 (`lifetimes` vs `pymc-marketing`): confirm `lifetimes` with hard `scipy<1.13` pin. Q3 (ModelFitStatus thresholds): defer to founder; recommended values above; file KI-NEW-P. Q4 (Beauty cold-start): default PROVISIONAL per Pivot 5; run pre-T1 measurement to confirm-or-promote-to-VALIDATED honestly. Q5 (per-customer scores in parquet only): confirm — required for D-2/D-3 deletion semantics. Q6 (parquet schema version): confirm `parquet_schema_version=1` at T1.5.

**Single-demote-channel invariant compliance for T0:** verified — `gate_recently_run` runs inside the guardrails pass and produces a `RejectedPlay`; T0 does not append to `engine_run.recommendations` post-guardrails. Add the Deviation-check line per ticket.
