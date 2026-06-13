# DS Architect — S13 Plan Review

**Reviewer:** ecommerce-ds-architect
**Date:** 2026-05-28
**Reviewing:** `agent_outputs/implementation-manager-s13-consumer-wiring-plan.md` v1
**Verdict:** **APPROVE-WITH-CHANGES**
**Required actions:** 11 v2 changes (§(e) below) before code dispatch. Q-S13-4 lock to (A) only is the load-bearing decision.

---

## A. Headline

S13's architecture is sound and faithful to the four-state vocabulary, ranking-vs-prediction framing, ML-fit-lowest-precedence pin, and Pivot 7 single-demote-channel invariant. The 3 atomic-flip pairs + conditional T0 + close shape mirrors S10–S12 cadence cleanly. The plan correctly avoids new injection blocks at `src/main.py:1380-1597` and routes consumer wiring through `build_prior_anchored_play_card`, not through a new path that would multiply the demote channels.

The required changes are not architectural reframes — they are (1) Q-S13-4 lock, (2) ranking-chain selection-rule lock, (3) modal-segment-stability floor lock, (4) the comment at `src/engine_run.py:167-171` (which the IM correctly flagged as speculative) needs explicit revision at T2, (5) one positive-control synthetic that does not yet exist in the plan, (6) clarification on `INSUFFICIENT_DATA` vs `REFUSED` consumer behavior in fit_warnings emission.

S13 is the load-bearing payoff sprint and worth not rushing. v2 IM revision is required before code dispatch.

---

## B. Q-S13-4 LOCK — ML-fit ReasonCode emission scope

**Verdict: (A) ONLY. `RejectedPlay.reason_code` MUST NOT carry `MODEL_FIT_*` codes. Ever.**

The comment at `src/engine_run.py:165-166` is load-bearing and verbatim: *"ML-fit NEVER demotes a card between slate roles. Only gates (1)-(3) route to Considered."* The follow-on comment at L167-171 mentioning `RejectedPlay.reason_code` is **speculative scaffolding** the IM flagged correctly — it predates the S10 cold-start verdict's lock of the precedence semantics and must be revised at S13-T2.

Reasoning:
1. If a card stays in Recommended/Experiment, there is no `RejectedPlay` to attach to — (B) is structurally incoherent for the path that actually fires.
2. (B) would conceptually re-open a fourth demote channel and threaten Pivot 7 single-demote-channel.
3. The audit story belongs with the consumed strategy (the chain that selected/fell-through), which lives on `model_card_ref` on the consuming PlayCard.
4. "Both" is the worst outcome — it creates two truths about why ML didn't rank and invites downstream consumers to disagree.

**Required:** Add an invariant test (the plan proposes one in §E.3; lock it as REQUIRED, not optional): `tests/test_s13_ml_fit_never_demotes.py` asserts no `RejectedPlay.reason_code in {MODEL_FIT_INSUFFICIENT_DATA, MODEL_FIT_REFUSED}` across all 5 pinned fixtures + the new synthetic month-2 fixture. T2 must also revise the `src/engine_run.py:167-171` comment block to remove the speculative `RejectedPlay` reference and replace with the locked `model_card_ref.fit_warnings` channel.

---

## C. Adjudication summary Q-S13-1 through Q-S13-6

| # | Verdict | Reasoning |
|---|---|---|
| **Q-S13-1** ModelCard refactor at T0 | **DO at T0** | IM's 5–6 projected `if model_card.<field> is not None` consumer call-sites exceed the S12 §H ≥4-site trigger. The `metrics: Dict[str, float]` + namespaced keys + `@property` shim shape is the right contract. Deferring forces T2 consumers to write `if card.holdout_rank_spearman is not None` checks that get rewritten in S14/S15. |
| **Q-S13-2** Re-pin contract | **Option α (atomic per-ticket)** | Mirrors S10/S11/S12 atomic-flip discipline; cleaner audit trail; matches the new `pinned_sha_ledger.json` design. Confirm that `briefing.html` sha-unchanged assertion is part of every T*.5 acceptance, with `engine_run.json` sha confined to PlayCard `predicted_segment` + `model_card_ref` keys at T2.5 and `month_2_delta` only at T3.5. |
| **Q-S13-3** month_2_delta merchant-facing copy | **Operator-only at S13** | Pivot 2 Stop-Coding Line holds. `engine_run.json` carries the typed surface; the downstream renderer / Klaviyo agent narrates later. Optional debug print under `ENGINE_DEBUG_CATEGORIES` is fine but must not be a default. |
| **Q-S13-4** ML-fit emission scope | **(A) only — see (B) above** | Load-bearing. |
| **Q-S13-5** Code location | **New `src/predictive/ranking_strategy.py`** | Confirmed. Coupling ranking to `audience_builders.py` would conflate audience-definition logic with consumption-strategy logic and complicate the AudienceIntent enum's future expansion. The `RankingStrategyResult` typed object is the right surface. |
| **Q-S13-6** KI-NEW-L disposition | **OPEN with explicit S13.5 commitment** | KI-NEW-L L411–420 (verbatim) commits to S13.5 collapse between S13-T4 and S14-T1. S13 plan correctly excludes it. T4-CLOSE memory.md entry must restate the S13.5 commitment date. |

---

## D. DS-domain thresholds and locks

### D.1 Ranking-strategy chain selection rule (LOCKED)

The plan implies the rule but does not state it. **Lock at v2:**

> The chain consults substrates in published intent-conditional order (GENERAL: BG/NBD → CF → survival → RFM → recency; REPLENISHMENT_TIMING: survival → BG/NBD → CF → RFM → recency; LOOKALIKE_EXPANSION: CF → BG/NBD → survival → RFM → recency). For each position, the strategy is **SELECTED** iff `fit_status in {VALIDATED, PROVISIONAL}`. Otherwise (REFUSED or INSUFFICIENT_DATA) the chain advances. **PROVISIONAL never falls through to a downstream VALIDATED** — a VALIDATED CF does not override a PROVISIONAL BG/NBD that already cleared its position. Rationale: chain position encodes object-relevance for the intent (BG/NBD is the right model for general LTV ranking even when thin); cross-position quality-comparison would re-introduce the conflation the four-state vocabulary was built to prevent.
>
> **PROVISIONAL emits a `model_card_ref.fit_warnings` entry** of shape `"PROVISIONAL_SELECTED:bgnbd"`. **INSUFFICIENT_DATA and REFUSED both emit fall-through entries** (`"MODEL_FIT_INSUFFICIENT_DATA:bgnbd"` / `"MODEL_FIT_REFUSED:bgnbd"`) — the difference matters for operator audit (INSUFFICIENT_DATA = expected on thin merchants; REFUSED = model-health issue warranting review) per S10 cold-start verdict §4.2.

### D.2 month_2_delta detection threshold (LOCKED)

**21-day floor APPROVED.** Lineage-keyed (not wall-clock) is correct per `STATE.md` §8 substrate map. **Add one constraint:** if `prior_run.audience_definition_version != current_run.audience_definition_version` (D-1), `month_2_delta.segment_shifts` MUST be None and `notes` MUST carry `"lineage_changed_segment_shift_incomparable"`. Substrate fit-status changes remain comparable; retention CI delta remains comparable; only customer-level segment shifts are lineage-sensitive.

### D.3 PlayCard.fit_warnings shape (LOCKED)

**List[str] with structured prefix grammar**, NOT Dict. Reason: the warnings are ordered (they describe chain fall-through in order) and a List preserves that; a Dict requires arbitrary key choice. Grammar: `"{LEVEL}:{substrate}"` where LEVEL ∈ {`PROVISIONAL_SELECTED`, `MODEL_FIT_INSUFFICIENT_DATA`, `MODEL_FIT_REFUSED`}. The strategy_used and fit_status_chain on `model_card_ref` give the structured form; `fit_warnings` is the operator-readable summary.

### D.4 Modal-segment-stability floor (NEW — LOCKED)

Risk 2 in the plan (modal segment unstable on small audiences) needs a numerical floor, not just "document in DS review." **Lock:** `predicted_segment.segment_name = None` when `n_audience < 50` OR `audience_modal_share < 0.30`. Rationale:
- n<50: RFM segments below 50 customers are statistically unstable per S12 RFM `absolute_customers_floor`.
- modal_share<0.30: a "modal" segment with <30% of the audience is not really a modal characterization; it indicates the audience is segment-heterogeneous and the segment_name claim would mislead.
- Below either floor, ranking still proceeds (chain falls through normally); only the surfaced `segment_name` suppresses.

### D.5 Positive-control consumer test (NEW — REQUIRED)

S10/S11/S12 each shipped a load-bearing positive-control synthetic. S13's analog must exercise the consumer surface, not the substrate. **Required at T1:**

A `tests/test_ranking_strategy_positive_control.py` fixture with hand-set ModelCard `fit_status` matrices covering the 5 most-meaningful fall-through paths (BG/NBD VAL stop; BG/NBD INSUF → CF VAL; BG/NBD REFUSED → CF INSUF → survival VAL; all four ML INSUF → RFM VAL; all REFUSED → recency last-resort), each asserting `strategy_used` + `fit_status_chain` content + correct `fit_warnings` grammar.

At T3, a synthetic 2-run sequence on `small_sm` (proposed in the plan §G — confirm) asserting `month_2_delta` substrate-fit-status-change detection AND segment_shifts AND retention_ci delta sign correctness on a constructed cohort where the delta is known by construction.

### D.6 Renderer-non-consumption pin

Plan §L mentions this; lock it as a REQUIRED test at T2.5 not optional: `grep -rn "predicted_segment\|model_card_ref" src/briefing.py` returns empty. This guarantees the `briefing.html` sha-unchanged claim is structural, not coincidental.

---

## E. Required v2 IM changes (numbered)

1. **Lock Q-S13-4 to (A) only.** Promote §B.8 from "recommendation" to "LOCKED — DS verdict 2026-05-28." Add explicit `tests/test_s13_ml_fit_never_demotes.py` as REQUIRED at T2.
2. **Revise `src/engine_run.py:167-171` comment block at T2** to remove the speculative `RejectedPlay.reason_code` channel and replace with the `model_card_ref.fit_warnings` channel + precedence-pin reaffirmation.
3. **Add the locked chain selection rule (D.1) to Part B preamble** with the PROVISIONAL-never-falls-through statement and the three-LEVEL fit_warnings grammar.
4. **Add the modal-segment stability floor (D.4)** to Part B.5 and T2 acceptance (`n_audience < 50` OR `audience_modal_share < 0.30` → `segment_name = None`).
5. **Add the lineage-change constraint (D.2)** to Part C.2 `MonthDelta` schema (segment_shifts suppressed across lineage bumps; typed note).
6. **Promote the positive-control synthetic tests (D.5) to REQUIRED** at T1 and T3 acceptance criteria. Name the 5 fall-through paths the matrix must cover.
7. **Lock fit_warnings shape (D.3)** as `List[str]` in §B.8 + the T2 PredictedSegment/ModelCardRef extension block.
8. **Promote renderer-non-consumption grep to REQUIRED T2.5 acceptance** (currently only mentioned in §L).
9. **Add intent-conditional chain ordering to ranking_strategy.py module surface (T1):** AudienceIntent enum currently mentions GENERAL/REPLENISHMENT_TIMING/LOOKALIKE_EXPANSION but the per-intent reorderings are not in the spec — lock them.
10. **T4-CLOSE: revise STATE.md §4 carefully.** "DORMANT (substrate live ... emitter wired at S13)" → "LIVE — emitter wired at S13; ML-fit NEVER demotes (precedence-pin)." Cite the new test as the contract anchor.
11. **Optional but recommended:** Rename `RankingStrategyResult.strategy_used: str` → `Optional[Literal["BGNBD", "CF", "SURVIVAL", "RFM", "RECENCY"]]` for type safety. Free strings are how enums quietly leak.

---

## F. Retrospective bullets from S10–S12 (≤5)

1. **Four-state vocabulary held cleanly across 6 substrates.** No revisions needed at S13. The INSUFFICIENT_DATA vs REFUSED audit-story distinction (cold-start verdict §4.2) is now the single most-load-bearing semantic in the consumer wiring — surface explicitly in fit_warnings grammar (different LEVEL prefix per S13's D.1 lock above).
2. **IM-drafted thresholds systematically come in too lenient.** S10 c-index, S12 RFM Spearman, S12 retention CI — all revised UP by DS. S13's "21-day floor for month_2_delta" feels right but is untested — flag in KI-NEW-P consumer-side cells for S14 real-merchant validation.
3. **Positive-control synthetics caught no bugs but unlocked shipping confidence.** Keep the pattern. S13's two synthetics (chain fall-through matrix + 2-run sequence) are non-negotiable.
4. **Library substitutions (lifelines → scikit-survival; declining lifelines for retention) succeeded by asking "what is the actual operational object?"** S13 has the same question for the chain selection rule — see D.1; intent-conditional ordering preserves the per-substrate object-relevance.
5. **The S6-T1 forward-scaffolding pattern (PredictedSegment / ModelCardRef stubs added 7 sprints before producers) is paying off at S13 — schema is already in place, only field-extension and population to do.** Confirms the additive-within-`event_version=1` discipline. Worth restating in PIVOTS as a clarifier-to-Pivot-2.

---

## G. Product-level escalations for the founder

1. **The `briefing.html` byte-identity claim is preserved at S13 (renderer doesn't consume), but the JSON-level break is the first multi-sprint sequence of intentional sha changes.** The ledger file is the right answer. Founder should acknowledge that S13-T2.5 + T3.5 close ships PlayCards with non-None `predicted_segment` / `model_card_ref` on real fixtures — the data layer expands measurably even though no merchant prose changes.

2. **Pivot 8 month-2-return is implemented as substrate-state-delta, NOT as realized-outcome delta.** This is honest, defensible, and the only thing achievable pre-Phase 9 — but it means "month-2 wow" for cold-start merchants comes through EB (`n_observed` shift in `bayesian_blend`), not through ML (ML refusal degrades silently). The S10 cold-start verdict §5 made this load-bearing; S13 plan does not surface it. Consider adding to T3-CLOSE memory.md entry: "month-2-return for cold-start preserved through EB path, not ML."

3. **The `predicted_segment` population on `small_sm` (the only synthetic that will VALIDATE RFM) is structural correctness per Pivot 5, NOT predictive accuracy.** Real predictive validation lands at KI-NEW-P closure (S14). T4-CLOSE docs MUST mark this explicitly — there is real risk that a downstream reader sees a populated `segment_name = "At Risk"` on a synthetic and treats it as proof of merchant value.

4. **Q-S13-3: keep the `month_2_delta` debug print operator-only at S13.** No merchant copy. The frontend / Klaviyo agent is the right place — Stop-Coding Line holds.

5. **The Q-S13-4 lock (A only) means the `src/engine_run.py:167-171` comment must be revised in code at T2.** This is a small code change but it is the single most-load-bearing semantic clarification in S13. Founder should expect to see a deliberate one-line `Deviation check: comment-revision-per-DS-lock-Q-S13-4` on the T2 commit.
