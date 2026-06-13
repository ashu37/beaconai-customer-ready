# Sprint 13 — Consumer Wiring & Audience-Ranking Integration — Implementation Plan

**Author:** implementation-manager
**Date:** 2026-05-28 (v1) / 2026-05-29 (v2)
**Branch baseline:** `post-6b-restructured-roadmap` (post-S12 close 2026-05-28)
**Status:** v2 — DS-revised (ds-architect-s13-plan-review.md APPROVE-WITH-CHANGES), founder-acked 2026-05-29 for all 11 DS-required revisions + 6 Q&A adjudications; dispatchable (per founder protocol — plan-only; code-refactor-engineer dispatch for S13-T0 pending orchestrator action).
**Supersedes:** none. Extends `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` Part B §"Sprint 13" with ticket-level detail.
**Parent active read path:** `PRODUCT.md`, `STATE.md`, `PIVOTS.md`, `ROADMAP.md`, `KNOWN_ISSUES.md`
**Pattern parents:** `agent_outputs/implementation-manager-s10-ml-part1-plan.md` (v2), `agent_outputs/implementation-manager-s11-ml-part2-plan.md` (v2), `agent_outputs/implementation-manager-s12-rfm-retention-plan.md` (v2). Cadence inherited; consumer-side scope NEW.
**Discipline:** Subagent Handoff Discipline (`CLAUDE.md` L27–46); Documentation Discipline (`CLAUDE.md` L68–80); per-ticket loop is refactor → DS review → orchestrator commits+pushes → next ticket (founder-locked 2026-05-25); each refactor dispatch MUST require `agent_outputs/code-refactor-engineer-s13-<ticket>-summary.md`.

---

## REVISION HISTORY

```
REVISION HISTORY
- 2026-05-28 v1 — initial dispatch draft. 8 tickets (T0 conditional + T1/T1.5 + T2/T2.5 + T3/T3.5 + T4-CLOSE). First sprint that intentionally breaks engine_run.json byte-identity on pinned fixtures at T2.5. Surfaces 6 open founder/DS questions (Q-S13-1 .. Q-S13-6). Plan-only — DS verdict required before code dispatch.
- 2026-05-29 v2 — Q-S13-4 LOCKED (A) only (model_card_ref.fit_warnings ONLY; never RejectedPlay.reason_code); ranking-chain selection rule LOCKED with intent-conditional ordering + PROVISIONAL-never-falls-through + List[str] fit_warnings grammar; modal-segment stability floor LOCKED (n_audience<50 OR modal_share<0.30 → segment_name=None); lineage-change constraint LOCKED for month_2_delta (segment_shifts suppressed when audience_definition_version bumps); positive-control synthetic tests PROMOTED to REQUIRED at T1 + T3; renderer-non-consumption grep PROMOTED to REQUIRED T2.5; T2 ticket gains `src/engine_run.py:167-171` comment revision + explicit Deviation-check line; ModelCard refactor at T0 CONFIRMED DO (5+ field-presence sites). Per ds-architect-s13-plan-review.md and founder ack 2026-05-29.
```

---

## Part A — Scope clarification

### A.1 What S13 is — the consumer sprint

S10–S12 produced **substrate**: six predictive ModelCards / RetentionCard land on `engine_run.predictive_models` / `engine_run.cohort_diagnostics`. **No PlayCard consumes any of it today.** `briefing.py` does not read `predictive_models`, `cohort_diagnostics`, `predicted_segment`, `model_card_ref`, or `ranking_strategy` (grep verified 2026-05-28).

S13 wires the **consumer side**:

1. `PlayCard.predicted_segment` (was `Optional[PredictedSegment] = None`) populated from RFM's per-customer named-segment output, on the wired Tier-B builders' audiences.
2. `PlayCard.model_card_ref` populated with a typed reference to the ModelCards consumed for that PlayCard's audience ranking.
3. **Ranking-strategy fallback chain ACTIVATED:** intent-conditional published order per `docs/engine_flags.md` L144 verbatim:
   > `BG/NBD → CF → survival → RFM (floor) → recency`. **RFM is the explicit floor of the chain — the last deterministic-segmentation strategy before the recency last-resort.**
4. **ML-fit gate ACTIVATED** — the two dormant ReasonCodes added at S10-T3 (`MODEL_FIT_INSUFFICIENT_DATA`, `MODEL_FIT_REFUSED`; pinned at `src/engine_run.py:172-173`) start emitting per DS S10 cold-start verdict §Part 4.3:
   > Two codes, not one. **Recommend adding both at S10-T3.**
   Per `src/engine_run.py:165-166` verbatim:
   > ML-fit NEVER demotes a card between slate roles. Only gates (1)-(3) route to Considered.
   **v2 LOCK (per Q-S13-4):** Emission is via `PlayCard.model_card_ref.fit_warnings` ONLY. **NEVER** via `RejectedPlay.reason_code`.
5. `EngineRun.month_2_delta` typed slot — new field for the month-2-return wow story (Pivot 8).

### A.2 What S13 is NOT

- **Not a substrate sprint.** No new fits, no new libraries, no new threshold tables in `config/gate_calibration.yaml` outside the ranking-strategy chain documentation row.
- **Not a copy / phrasing sprint.** Stop-Coding Line (Pivot 2) holds: engine emits typed fields; downstream renders. `briefing.py` may surface `predicted_segment` / chosen strategy in a minimal debug block for operator verification (founder-facing only), but no merchant-facing copy. **v2 LOCK (per Q-S13-3):** `month_2_delta` is operator-only at S13. No merchant-facing copy; deferred to future frontend / Klaviyo agent.
- **Not a Phase 9 outcome-loop sprint.** No realized-outcome ingestion; the `month_2_delta` is structural (substrate-fit-status changes, segment shifts, retention CI tightening), NOT realized-vs-predicted (per `PRODUCT.md` §5 — "month-2-return value comes from the ML predictive layer refit on 30 more days of data, not from realized outcomes").
- **Not S13.5 / KI-NEW-L collapse.** Per `ROADMAP.md` §3 L74 verbatim:
  > KI-NEW-L collapses 5 V2 prior-anchored injection blocks at `src/main.py:1380-1597` into a single PRIOR_ANCHORED dispatch — scheduled S13.5 per memory.md L1921 commitment (between S13-T4 atomic flip and S14-T1 beta-launch dispatch).
  KI-NEW-L stays a separate scheduled-S13.5 ticket; S13 does NOT touch it. T4-CLOSE memory.md entry MUST restate the S13.5 commitment date.

### A.3 The Pivot-5 / Pivot-8 lens for S13 outputs

Pivot 5 S12-T2.5 clarifier (`PIVOTS.md` L61 verbatim):
> Synthetic VALIDATED outcomes at S12 (RFM `small_sm` Spearman=0.93; retention `healthy_supplements_240d` via degenerate bootstrap n=38) are **structural-correctness signals**, NOT predictive-accuracy claims.

S13 must extend this honesty: when a synthetic fixture's RFM substrate VALIDATED (e.g. `small_sm`), the PlayCard surfacing it will carry a `predicted_segment` populated by structurally-correct math on a synthetic. Operator-facing audit must continue to mark this as structural correctness, not predictive accuracy. Real predictive validation lands at S14 (KI-NEW-P closure).

**v2 addition (per DS §G.3):** T4-CLOSE PIVOTS.md clarifier on Pivot 5 — verbatim:
> `predicted_segment.segment_name` populated on `small_sm` (the only synthetic that VALIDATES RFM) is structural-correctness per Pivot 5, NOT predictive accuracy. Downstream readers MUST NOT treat synthetic VALIDATED outcomes as proof of merchant value. Closure remains S14 real-merchant calibration per KI-NEW-P.

Pivot 8 (`PIVOTS.md` L86-91 verbatim):
> Beta success = month-1-wow (defensible slate on first run) + month-2-return (ML refit on 30 more days produces materially different/better recommendations).

`month_2_delta` is the typed surface that makes "different/better" auditable.

**v2 addition (per DS §G.2):** T3-CLOSE memory.md entry MUST carry: "**month-2-return for cold-start merchants preserved through EB path (`n_observed` shift in `bayesian_blend`), NOT through ML.** ML refusal degrades silently within audience ranking."

---

## Part B — Consumer mapping (6 substrates × consumer behavior)

Per `STATE.md` §4 (verbatim, L74 + L78):

> **ML-fit gate precedence (when activated at S13):** ML-fit is the **lowest precedence** of the four — it never demotes between slate roles. It only triggers a silent fallback **within audience ranking**: `BG/NBD → CF → survival → RFM (floor) → recency` (RFM = floor; recency = last-resort).

Per the DS S10 cold-start verdict §1 Case A (verbatim):
> S13's `ranking_strategy` chain consumer reads `predictive_models[*].fit_status`. A REFUSED model means the audience builder's `ranking_strategy` falls back to RFM quintile (S12) or — if S12 also REFUSED — to recency-order.

### B.0 LOCKED — Ranking-chain selection rule (v2, per DS §D.1)

The chain consults substrates in published **intent-conditional** order:

- **GENERAL:** BG/NBD → CF → survival → RFM → recency.
- **REPLENISHMENT_TIMING:** survival → BG/NBD → CF → RFM → recency.
- **LOOKALIKE_EXPANSION:** CF → BG/NBD → survival → RFM → recency.

For each position, the strategy is **SELECTED** iff `fit_status in {VALIDATED, PROVISIONAL}`. Otherwise (REFUSED or INSUFFICIENT_DATA) the chain advances. **PROVISIONAL never falls through to a downstream VALIDATED** — a VALIDATED CF does not override a PROVISIONAL BG/NBD that already cleared its position. Rationale: chain position encodes object-relevance for the intent; cross-position quality-comparison would re-introduce the conflation the four-state vocabulary was built to prevent.

**fit_warnings emission grammar (List[str], ordered by chain position):**
- **PROVISIONAL emits** a `model_card_ref.fit_warnings` entry of shape `"PROVISIONAL_SELECTED:bgnbd"`.
- **INSUFFICIENT_DATA emits** a fall-through entry `"MODEL_FIT_INSUFFICIENT_DATA:bgnbd"`.
- **REFUSED emits** a fall-through entry `"MODEL_FIT_REFUSED:bgnbd"`.

The `INSUFFICIENT_DATA` vs `REFUSED` distinction matters for operator audit (INSUFFICIENT_DATA = expected on thin merchants; REFUSED = model-health issue warranting review) per S10 cold-start verdict §4.2.

### B.1 BG/NBD (`predictive_models["bgnbd"]`)
- **Produces:** per-customer `pred_total` (expected purchase count over forecast horizon) + `pred_alive` (P(alive)). Parquet at `data/<store_id>/predictive/bgnbd.parquet` only when `fit_status in {VALIDATED, PROVISIONAL}`.
- **Consumer:** ranking-strategy chain head for GENERAL intent. When `fit_status in {VALIDATED, PROVISIONAL}`, audience builder consults the BG/NBD parquet and orders the audience by `pred_total DESC`.
- **REFUSED / INSUFFICIENT_DATA:** silent fallback to next position per chain. Emit appropriate LEVEL-prefixed entry on `model_card_ref.fit_warnings` (NOT a ReasonCode on the PlayCard's RejectedPlay — the card stays in its assigned slate role).

### B.2 Gamma-Gamma (`predictive_models["gamma_gamma"]`)
- **Produces:** per-customer `pred_avg_monetary` × `pred_total` → `pred_total_revenue`. Chains BG/NBD (REFUSED if BG/NBD REFUSED).
- **Consumer:** WHEN BG/NBD is the active ranker AND `gamma_gamma.fit_status in {VALIDATED, PROVISIONAL}`, the BG/NBD strategy upgrades from `pred_total` to `pred_total_revenue`. G-G alone does NOT independently rank — it's a magnitude multiplier on the BG/NBD ranker.
- **REFUSED:** BG/NBD strategy falls back to bare `pred_total`. (No fallback chain step for G-G alone — it lives on top of BG/NBD.)

### B.3 Survival (`predictive_models["survival"]`)
- **Produces:** per-customer Cox PH hazard ranking; useful for replenishment-timing-driven audiences (notably `replenishment_due`).
- **Consumer:** First position for REPLENISHMENT_TIMING intent; third position for GENERAL. When selected, audience is ordered by predicted hazard (higher hazard = more likely to need replenishment soon).
- **Chained on BG/NBD:** REFUSED automatically when BG/NBD REFUSED. This is the chained-refusal pin per S11 — survival cannot independently rank when BG/NBD failed.

### B.4 CF (`predictive_models["cf"]`)
- **Produces:** per-customer ALS top-K look-alikes. Parquet at `data/<store_id>/predictive/cf.parquet`.
- **Consumer:** First position for LOOKALIKE_EXPANSION intent; second for GENERAL. **CF is INDEPENDENT of BG/NBD** (S11-T2 pin), so its VALIDATED status is genuinely orthogonal.
- **REFUSED / INSUFFICIENT_DATA:** silent fallback per chain.

### B.5 RFM (`predictive_models["rfm"]`)
- **Produces:** per-customer `segment_name` (1-of-11 from `SEGMENT_LTV_RANK_ORDER`, see `src/predictive/rfm.py:116-128`) + raw `r_score`, `f_score`, `m_score`. Parquet at `data/<store_id>/predictive/rfm.parquet`.
- **Consumer (dual role):**
  1. **Ranking-chain floor:** last position before recency across all intents. When selected, audience is ordered by `_SEGMENT_RANK` (1 = Champions = top).
  2. **`PlayCard.predicted_segment` population:** when RFM is VALIDATED/PROVISIONAL the per-audience-modal-segment is surfaced on the PlayCard.

**v2 LOCKED — Modal-segment stability floor (per DS §D.4):**
- `predicted_segment.segment_name = None` when `n_audience < 50` OR `audience_modal_share < 0.30`.
- Below either floor: ranking still proceeds (chain falls through normally per B.0); only the surfaced `segment_name` suppresses.
- Rationale (DS §D.4 verbatim): n<50 = RFM segments below 50 customers are statistically unstable per S12 `absolute_customers_floor`; modal_share<0.30 = audience is segment-heterogeneous and the segment_name claim would mislead.

- **REFUSED / INSUFFICIENT_DATA:** chain falls through to recency; `predicted_segment` stays None.

### B.6 Retention (`cohort_diagnostics["retention"]`)
- **Produces:** cohort × month retention curves + bootstrap CIs. NOT a per-customer ranker.
- **Consumer:** NOT in the ranking chain. Consumed by `month_2_delta` (CI band tightening across months) and by an operator-only `cohort_diagnostics` summary section (founder-internal). NOT consumed by any audience builder for ranking.
- **REFUSED / INSUFFICIENT_DATA:** `month_2_delta.retention_ci_at_month_3_delta` stays None.

### B.7 Recency (non-ML last-resort)
- **Produces:** trivial sort by `last_order_date DESC`. Always available.
- **Consumer:** last-resort. Always succeeds. When the chain reaches recency, `model_card_ref.strategy_used = "RECENCY"` and `model_card_ref.fit_status_chain` enumerates the four upstream statuses so the operator can audit why nothing better ranked.

### B.8 ML-fit ReasonCode emission scope — **LOCKED — DS verdict 2026-05-28**

**Per DS verdict (Q-S13-4 lock, ds-architect-s13-plan-review.md §B):**

> Verdict: (A) ONLY. `RejectedPlay.reason_code` MUST NOT carry `MODEL_FIT_*` codes. Ever.

ML-fit ReasonCodes (`MODEL_FIT_INSUFFICIENT_DATA`, `MODEL_FIT_REFUSED`) emit ONLY on `PlayCard.model_card_ref.fit_warnings` per PlayCard. **NEVER on `RejectedPlay.reason_code`.**

Reasoning (DS verbatim):
> 1. If a card stays in Recommended/Experiment, there is no `RejectedPlay` to attach to — (B) is structurally incoherent for the path that actually fires.
> 2. (B) would conceptually re-open a fourth demote channel and threaten Pivot 7 single-demote-channel.
> 3. The audit story belongs with the consumed strategy (the chain that selected/fell-through), which lives on `model_card_ref` on the consuming PlayCard.
> 4. "Both" is the worst outcome — it creates two truths about why ML didn't rank and invites downstream consumers to disagree.

**fit_warnings shape (v2 LOCKED, per DS §D.3):**
- `fit_warnings: List[str]` (NOT Dict). Reason: warnings are ordered (chain fall-through order); List preserves; Dict requires arbitrary key choice.
- Prefix grammar: `"{LEVEL}:{substrate}"` where LEVEL ∈ {`PROVISIONAL_SELECTED`, `MODEL_FIT_INSUFFICIENT_DATA`, `MODEL_FIT_REFUSED`}.
- `strategy_used` and `fit_status_chain` on `model_card_ref` give the structured form; `fit_warnings` is the operator-readable summary.

**Required invariant test at T2:** `tests/test_s13_ml_fit_never_demotes.py` asserts no `RejectedPlay.reason_code in {MODEL_FIT_INSUFFICIENT_DATA, MODEL_FIT_REFUSED}` across all 5 pinned fixtures + the new synthetic month-2 fixture.

**Required code revision at T2:** the comment block at `src/engine_run.py:167-171` (which currently mentions the speculative `RejectedPlay.reason_code` channel) MUST be revised to remove the speculative reference and replace with the locked `model_card_ref.fit_warnings` channel + precedence-pin reaffirmation. T2 commit body MUST carry a deliberate one-line: `Deviation check: comment-revision-per-DS-lock-Q-S13-4` (per DS founder escalation §G.5).

---

## Part C — `month_2_delta` design

### C.1 Where it lives

New top-level slot `EngineRun.month_2_delta: Optional[MonthDelta] = None` (additive within `event_version=1`, mirrors `predictive_models` / `cohort_diagnostics` precedent at `src/engine_run.py:1006` + L1023). `Optional[...]=None` means the round-trip stays byte-identical for month-1 fixtures.

### C.2 What `MonthDelta` carries

```
@dataclass
class MonthDelta:
    detected_via: str               # "PER_STORE_MEMORY_LOOKUP" (only mode in S13)
    prior_run_lineage_id: Optional[str] = None     # month-1 EngineRun lineage
    days_between_runs: Optional[int] = None
    substrate_fit_status_changes: Dict[str, FitStatusChange] = field(default_factory=dict)
        # keys: "bgnbd", "gamma_gamma", "survival", "cf", "rfm", "retention"
        # value: {from: ModelFitStatus, to: ModelFitStatus, n_observed_delta: int}
    segment_shifts: Optional[SegmentShiftSummary] = None
        # populated only when RFM was VALIDATED/PROVISIONAL in both runs:
        # {n_customers_moved_up: int, n_moved_down: int, top_movers: List[...]}
        # v2 LOCK: also None when lineage changes (see below).
    retention_ci_at_month_3_delta: Optional[float] = None
        # Negative = CIs tightened = more confidence; populated only when both
        # runs had retention VALIDATED/PROVISIONAL.
    notes: Optional[str] = None
```

**v2 LOCKED — Lineage-change constraint (per DS §D.2):**
- If `prior_run.audience_definition_version != current_run.audience_definition_version` (D-1):
  - `month_2_delta.segment_shifts` MUST be None.
  - `notes` MUST carry `"lineage_changed_segment_shift_incomparable"`.
- Substrate fit-status changes remain comparable; retention CI delta remains comparable; only customer-level segment shifts are lineage-sensitive.

### C.3 How "month-2" is detected

Per `STATE.md` §8 (substrate map): per-merchant SQLite at `src/memory/events.py`. The lookup is:

1. On engine start, read the previous successful `EngineRun` snapshot from `data/<store_id>/runs/` (or from the immutable snapshot index in `memory.db`).
2. If a prior run exists AND `days_since(prior_run.run_timestamp) >= 21` (founder-tunable; default 21d guards against intra-month re-runs), populate `month_2_delta`.
3. Otherwise leave `month_2_delta = None`.

No wall-clock comparison; lineage-keyed.

### C.4 Wow moment (operator-only at S13 — **LOCKED per Q-S13-3**)

S13 surface is operator-only. The downstream renderer / Klaviyo agent will, in a future sprint, turn `month_2_delta` into merchant-facing copy. For S13, founder-internal `briefing.py` may print a debug section under `ENGINE_DEBUG_CATEGORIES` only:

```
Month-2 delta (vs run 2026-04-28, 30 days ago):
  • BG/NBD: REFUSED → PROVISIONAL (n_observed: 412 → 587)
  • RFM: VALIDATED → VALIDATED (Spearman 0.71 → 0.78)
  • Retention CI at month 3: 0.21 → 0.16 (tightened)
  • 142 customers moved up an RFM segment; 38 moved down
```

Stop-Coding Line (Pivot 2) holds.

---

## Part D — Ticket decomposition

### S13-T0 — ModelCard refactor to `Dict[str, float] metrics` **(LOCKED DO per Q-S13-1)**

**Trigger condition** per DS S12 plan review §H verbatim:
> If S13 wires consumers without organic pressure, defer further. If S13 wiring touches 4+ read sites with `if model_card.holdout_X is not None`, refactor there.

**Projected consumer field-presence checks confirmed:** 5+ projected `if model_card.<field> is not None` consumer call-sites at minimum (likely 8–10 once month_2_delta SegmentShiftSummary lands). **DS §C verdict: DO at T0.**

**Refactor shape (per DS S12 §H):** `ModelCard.metrics: Dict[str, float]` with namespaced keys (`bgnbd.holdout_rank_spearman`, `cf.holdout_top_k_recall`, `rfm.segment_monotonicity_spearman`, …). RetentionCard gets the same treatment. Optional typed-field surface preserved for back-compat via `@property` shim.

**Acceptance criteria:**
- New `metrics: Dict[str, float]` field on `ModelCard` + `RetentionCard`. Old typed fields preserved via property shim returning `metrics.get(<key>)`.
- All existing tests pass byte-identical (round-trip preserves the same keys; `_to_jsonable` emits the metrics dict alphabetized).
- M0 + pinned-fixture goldens byte-identical at flag-OFF (T0 is substrate-side, not consumer-side, so no `briefing.html` impact).
- Sprint 10/11/12 fit functions write to `metrics` dict; legacy typed-field assignments removed in T0.
- `Deviation check: none.` on commit body.

**Files touched:** `src/predictive/model_card.py` (~80 lines refactored), `src/predictive/{bgnbd,gamma_gamma,survival,cf,rfm,retention}.py` (assignment sites: ~6 × ~3 lines = ~18 lines), `tests/test_predictive_model_card.py` (new round-trip test on the metrics dict shape).

**Test plan:** existing rollback tests for S10/S11/S12 must pass byte-identical. New T0 test: `tests/test_model_card_metrics_dict_shape.py` — assert `metrics["bgnbd.holdout_rank_spearman"]` ≡ legacy `holdout_rank_spearman`; round-trip via `to_dict()` / `from_dict()` byte-identical.

**Required summary file:** `agent_outputs/code-refactor-engineer-s13-t0-summary.md`.

### S13-T1 — Ranking-strategy fallback chain implementation (FLAG-OFF)

**Goal:** Implement the chain `BG/NBD → CF → survival → RFM → recency` as a single module that audience builders consult.

**Code location (LOCKED per Q-S13-5):** NEW module `src/predictive/ranking_strategy.py`.

**Module surface (v2 LOCKED — intent enum + Literal type safety per DS §9 + §11):**
```
class AudienceIntent(Enum):
    GENERAL = "GENERAL"
    REPLENISHMENT_TIMING = "REPLENISHMENT_TIMING"
    LOOKALIKE_EXPANSION = "LOOKALIKE_EXPANSION"

@dataclass
class RankingStrategyResult:
    strategy_used: Optional[Literal["BGNBD", "CF", "SURVIVAL", "RFM", "RECENCY"]]
    fit_status_chain: List[Tuple[str, str]]
    fit_warnings: List[str]
    ranked_audience: pd.DataFrame

def rank_audience(
    audience_df: pd.DataFrame,
    intent: AudienceIntent,
    model_cards: Dict[str, ModelCard],
    *,
    store_id: str,
    data_dir: Path,
) -> RankingStrategyResult:
    ...
```

Per-intent reorderings LOCKED per §B.0 / DS §D.1 verbatim.

**Flag:** `ENGINE_V2_RANKING_STRATEGY_CHAIN` defaulting OFF. When OFF, builders use the today-behavior recency sort.

**Acceptance criteria:**
- New module `src/predictive/ranking_strategy.py` ships flag-OFF.
- `AudienceIntent` enum surfaced; `strategy_used` typed as `Optional[Literal[...]]`.
- Per-intent reorderings (GENERAL / REPLENISHMENT_TIMING / LOOKALIKE_EXPANSION) hardcoded per §B.0; unit tests pin them.
- **REQUIRED positive-control test (per DS §D.5):** `tests/test_ranking_strategy_positive_control.py` — hand-set ModelCard `fit_status` matrices covering the 5 most-meaningful fall-through paths:
  1. BG/NBD VAL stop (chain stops at position 1).
  2. BG/NBD INSUF → CF VAL.
  3. BG/NBD REFUSED → CF INSUF → survival VAL.
  4. All four ML INSUF → RFM VAL.
  5. All REFUSED → recency last-resort.
  Each path asserts: `strategy_used` + `fit_status_chain` content + correct `fit_warnings` grammar (PROVISIONAL_SELECTED / MODEL_FIT_INSUFFICIENT_DATA / MODEL_FIT_REFUSED prefixes).
- Per-fixture validation: for each of the 5 pinned fixtures, calling `rank_audience` returns the expected `strategy_used` matching the substrate ModelCard states from S12-close.
- M0 + pinned briefing.html byte-identical (flag OFF).
- `Deviation check: none.`

**Files touched:** NEW `src/predictive/ranking_strategy.py` (~250 lines), NEW `tests/test_ranking_strategy.py` (~10 tests), NEW `tests/test_ranking_strategy_positive_control.py`, `src/utils.py` DEFAULTS (add `ENGINE_V2_RANKING_STRATEGY_CHAIN=false`).

**Required summary file:** `agent_outputs/code-refactor-engineer-s13-t1-summary.md`.

### S13-T1.5 — Ranking-strategy atomic flip + per-fixture validation

**Goal:** Flip `ENGINE_V2_RANKING_STRATEGY_CHAIN=false → true` atomically with rollback contract test.

**Acceptance criteria:**
- Flag default flipped in `src/utils.py`.
- New rollback test `tests/test_s13_t1_5_ranking_strategy_rollback.py` asserts that with `ENGINE_V2_RANKING_STRATEGY_CHAIN=false` set explicitly via override, the engine produces byte-identical output to S12-close pinned fixtures.
- New positive test on pinned fixtures: assert which strategy was selected per fixture, and that the audit chain is non-empty when fallback fires.
- **M0 byte-identical at flag-OFF override.** Per-fixture briefing.html still byte-identical at T1.5 (since nothing consumes the ranking-strategy chain yet — T1.5 only flips the flag; T2 wires consumers).
- `Deviation check: none.`

**Files touched:** `src/utils.py` (flag default flip), NEW `tests/test_s13_t1_5_ranking_strategy_rollback.py`, fixture goldens unchanged.

**Required summary file:** `agent_outputs/code-refactor-engineer-s13-t1-5-summary.md`.

### S13-T2 — PlayCard `predicted_segment` + `model_card_ref` wiring + ML-fit fit_warnings activation (FLAG-OFF) + **`src/engine_run.py:167-171` comment revision**

**Goal:** wire the four Tier-B builders to consume `rank_audience` and populate `PlayCard.predicted_segment` + `PlayCard.model_card_ref`. ML-fit `MODEL_FIT_*` audit entries emit on the `model_card_ref.fit_warnings` per Part B.8 LOCK.

**v2 LOAD-BEARING: comment revision at `src/engine_run.py:167-171`** (per DS §E.2 / DS §G.5):
- Current L167-171 comment block contains speculative reference to `RejectedPlay.reason_code` channel.
- T2 MUST revise this comment block to remove the speculative reference and replace with: the locked `model_card_ref.fit_warnings` channel + reaffirmation of precedence-pin (ML-fit never demotes).
- **T2 commit body MUST carry:** `Deviation check: comment-revision-per-DS-lock-Q-S13-4`.

**Wiring location:**

`build_prior_anchored_play_card` in `src/measurement_builder.py` extends to:
1. Call `rank_audience(audience_df, intent, model_cards, store_id=..., data_dir=...)`.
2. Populate `play_card.model_card_ref` with `strategy_used`, `fit_status_chain`, `fit_warnings`, consumed-card pointers.
3. When `strategy_used == "RFM"` OR RFM VALIDATED/PROVISIONAL regardless of strategy chosen, populate `play_card.predicted_segment` with the **modal segment** among the audience, gated by the modal-segment stability floor (§B.5).

**`PredictedSegment` schema extension at T2:**
```
@dataclass
class PredictedSegment:
    segment_name: Optional[str] = None       # e.g. "At Risk", "Champions" — None if stability floor not met
    audience_modal_share: Optional[float] = None  # fraction of audience in segment_name
    n_audience: Optional[int] = None              # audience size at evaluation
    rfm_fit_status: Optional[str] = None     # mirror of consumed ModelCard fit_status
    notes: Optional[str] = None              # legacy
```

**`ModelCardRef` schema extension at T2 (v2 — List[str] grammar locked):**
```
@dataclass
class ModelCardRef:
    strategy_used: Optional[str] = None             # "BGNBD" | "CF" | "SURVIVAL" | "RFM" | "RECENCY"
    fit_status_chain: List[Tuple[str, str]] = field(default_factory=list)
        # e.g. [("bgnbd","REFUSED"),("cf","INSUFFICIENT_DATA"),("survival","REFUSED"),("rfm","VALIDATED")]
    fit_warnings: List[str] = field(default_factory=list)
        # LOCKED List[str] grammar "{LEVEL}:{substrate}"
        # e.g. ["MODEL_FIT_REFUSED:bgnbd", "MODEL_FIT_INSUFFICIENT_DATA:cf", "PROVISIONAL_SELECTED:rfm"]
    notes: Optional[str] = None
```

**Flag:** `ENGINE_V2_PLAY_PREDICTED_SEGMENT` defaulting OFF.

**Acceptance criteria:**
- `PredictedSegment` + `ModelCardRef` extended additively; round-trip preserves new fields.
- Per builder (winback_dormant_cohort, discount_dependency_hygiene, cohort_journey_first_to_second, aov_lift_via_threshold_bundle): wire ranking + segment population; flag-OFF behavior byte-identical (test pins).
- Modal-segment stability floor enforced: `predicted_segment.segment_name = None` when `n_audience < 50` OR `audience_modal_share < 0.30` even when RFM VALIDATED.
- ML-fit audit warnings appear on `model_card_ref.fit_warnings` (List[str], LOCKED grammar) when ranking falls back to a non-primary strategy OR selects a PROVISIONAL.
- **REQUIRED invariant test (per DS §B):** `tests/test_s13_ml_fit_never_demotes.py` asserts no `RejectedPlay.reason_code in {MODEL_FIT_INSUFFICIENT_DATA, MODEL_FIT_REFUSED}` across all 5 pinned fixtures + the new synthetic month-2 fixture (from T3).
- **REQUIRED code revision:** `src/engine_run.py:167-171` comment block revised per above.
- M0 + 5 pinned briefing.html byte-identical at flag-OFF.
- `Deviation check: comment-revision-per-DS-lock-Q-S13-4` (the ONLY non-"none" deviation-check in S13).

**Files touched:** `src/engine_run.py` (extend PredictedSegment + ModelCardRef dataclasses + revise L167-171 comment block, ~35 lines), `src/measurement_builder.py::build_prior_anchored_play_card` (~40 lines for ranking call + populate + stability floor), 4 Tier-B builders in `src/audience_builders.py` (~5 lines each — provide `AudienceIntent` per builder), `src/utils.py` (flag default), NEW `tests/test_s13_ml_fit_never_demotes.py`.

**Test plan:**
- Unit: PredictedSegment / ModelCardRef round-trip tests.
- Per-fixture: with flag ON, assert `predicted_segment.segment_name` matches the expected modal segment for fixtures where RFM VALIDATED (currently only `small_sm`).
- Stability-floor test: synthetic audience n=30 with RFM VALIDATED → `segment_name = None`.
- Rollback: `tests/test_s13_t2_predicted_segment_rollback.py` — flag OFF reproduces S13-T1.5 close byte-identical.
- ML-fit warning emission: assert `model_card_ref.fit_warnings` is non-empty when ranking-strategy chain falls back past a REFUSED model.
- ML-fit-never-demotes invariant pin.

**Required summary file:** `agent_outputs/code-refactor-engineer-s13-t2-summary.md`.

### S13-T2.5 — PlayCard consumer atomic flip + per-fixture validation + **first intentional engine_run.json re-pin**

**Goal:** Flip `ENGINE_V2_PLAY_PREDICTED_SEGMENT=false → true`. **THIS IS THE FIRST SPRINT THAT INTENTIONALLY BREAKS engine_run.json BYTE-IDENTITY on pinned fixtures.** `briefing.html` byte-identity is preserved (renderer doesn't consume).

**Re-pin protocol (atomic per-ticket, LOCKED per Q-S13-2):**
1. Pre-flip: run engine with flag OFF on all 5 pinned fixtures; capture `engine_run.json` + `briefing.html` shas → `pinned_fixtures_pre_s13_t2_5.txt`.
2. Flip the flag.
3. Run engine with flag ON on all 5 pinned fixtures; capture new `engine_run.json` + `briefing.html` shas → `pinned_fixtures_post_s13_t2_5.txt`.
4. Assert: `briefing.html` sha **unchanged**; `engine_run.json` sha **changed in a confined way** — diff confined to PlayCard `predicted_segment` / `model_card_ref` keys; all other keys byte-identical.
5. New ledger file `tests/fixtures/pinned_sha_ledger.json` tracks `pre_s13` and `post_s13` shas for each fixture per artifact.
6. Rollback contract: with flag OFF, `engine_run.json` sha matches `pre_s13_t2_5` entry.

**Acceptance criteria:**
- Flag default flipped.
- New rollback test `tests/test_s13_t2_5_predicted_segment_rollback.py` asserts flag-OFF byte-identical to T1.5 close on `engine_run.json` AND `briefing.html`.
- New positive test asserts flag-ON: `briefing.html` byte-identical to T1.5 close (renderer unchanged); `engine_run.json` differs only in PlayCard `predicted_segment` / `model_card_ref` keys.
- **REQUIRED renderer-non-consumption pin (per DS §D.6, promoted from §L mention):** `grep -rn "predicted_segment\|model_card_ref" src/briefing.py` returns empty. Guarantees `briefing.html` sha-unchanged claim is structural, not coincidental.
- Synthetic fixture VALIDATED on RFM (`small_sm`) carries a non-None `predicted_segment` on its PlayCards (subject to stability floor). Pivot-5-honest: structural correctness, not predictive accuracy.
- M0 (no PlayCards → no consumer impact): still byte-identical.
- `Deviation check: none.`

**Files touched:** `src/utils.py` (flag flip), NEW `tests/test_s13_t2_5_predicted_segment_rollback.py`, NEW `tests/fixtures/pinned_sha_ledger.json`, 5 fixture goldens NOT re-pinned at the HTML level (sha unchanged per design); JSON-level goldens at `tests/fixtures/<fixture>/engine_run.json` re-pinned atomically with this ticket per Option α.

**Required summary file:** `agent_outputs/code-refactor-engineer-s13-t2-5-summary.md`.

### S13-T3 — `month_2_delta` typed slot + detection logic (FLAG-OFF)

**Goal:** introduce `EngineRun.month_2_delta` + `MonthDelta` dataclass + detection logic from per-merchant memory.

**Flag:** `ENGINE_V2_MONTH_2_DELTA` defaulting OFF.

**Acceptance criteria:**
- New dataclasses in `src/engine_run.py`: `MonthDelta`, `FitStatusChange`, `SegmentShiftSummary`. Additive within `event_version=1`; default `None` keeps every existing fixture round-trip byte-identical.
- New module `src/month_delta.py` carrying `compute_month_delta(current_engine_run, prior_engine_run) -> Optional[MonthDelta]`.
- Detection: read prior `EngineRun` from per-merchant SQLite (`src/memory/events.py`) by lineage. Days-since-prior gate at 21d default.
- **Lineage-change constraint enforced (v2 LOCK per DS §D.2):** when `prior_run.audience_definition_version != current_run.audience_definition_version`, `month_2_delta.segment_shifts = None` AND `notes` carries `"lineage_changed_segment_shift_incomparable"`.
- Unit tests on `compute_month_delta`: 6 substrates' fit_status_change matrix; segment_shift summary; retention_ci delta; lineage-change suppression.
- **REQUIRED positive-control synthetic (per DS §D.5):** synthetic 2-run sequence on `small_sm` asserting:
  - `month_2_delta` substrate-fit-status-change detection.
  - `segment_shifts` correctness on a constructed cohort.
  - `retention_ci_at_month_3_delta` sign correctness.
  All by construction. Lives at `tests/test_month_delta_positive_control.py`.
- M0 + pinned briefing.html byte-identical at flag-OFF (T3 substrate-side; no rendering consumer).
- `Deviation check: none.`

**Files touched:** `src/engine_run.py` (3 new dataclasses + 1 new optional field, ~80 lines), NEW `src/month_delta.py` (~150 lines), NEW `tests/test_month_delta.py` (~12 tests), NEW `tests/test_month_delta_positive_control.py`, `src/utils.py` (flag default OFF), NEW synthetic month-2 fixture.

**T3-CLOSE memory.md addition (per DS §G.2):** "**month-2-return for cold-start merchants preserved through EB path (`n_observed` shift in `bayesian_blend`), NOT through ML.** ML refusal degrades silently within audience ranking."

**Required summary file:** `agent_outputs/code-refactor-engineer-s13-t3-summary.md`.

### S13-T3.5 — `month_2_delta` atomic flip + per-fixture validation

**Goal:** flip `ENGINE_V2_MONTH_2_DELTA=false → true`.

**Acceptance criteria:**
- Flag default flipped.
- Rollback test asserts flag-OFF reproduces T3-close byte-identical.
- On the synthetic month-2 fixture, `engine_run.json` carries non-None `month_2_delta` with expected substrate changes.
- 5 standard pinned fixtures (single-run only, no prior in memory.db): `month_2_delta = None`; `briefing.html` sha unchanged; ledger entry for any `engine_run.json` additive-key shift.
- `Deviation check: none.`

**Files touched:** `src/utils.py` (flag flip), NEW `tests/test_s13_t3_5_month_delta_rollback.py`.

**Required summary file:** `agent_outputs/code-refactor-engineer-s13-t3-5-summary.md`.

### S13-T4-CLOSE — Sprint-close documentation receipts + KI-NEW-L S13.5 anchor + KI-NEW-P extension + memory.md + INDEX + ROADMAP + STATE + **STATE.md §4 revision spec**

**Goal:** sprint-close docs (mirror S10-CLOSE / S11-T3 / S12-T3-CLOSE patterns).

**Documents touched (no code changes):**
- `memory.md` — S13-CLOSE template-shape entry (≤15 lines, fields per L20–36 template). MUST restate:
  - Month-2-via-EB note (per DS §G.2): "month-2-return for cold-start merchants preserved through EB path, NOT through ML."
  - KI-NEW-L S13.5 commitment date (per Q-S13-6 lock).
- `STATE.md` — **§4 ML-fit gate row revision (LOCKED per DS §E.10):**
  - Current §4 reads: ML-fit gate "DORMANT (substrate live ... emitter wired at S13)."
  - T4-CLOSE revises to: "**LIVE — emitter wired at S13; ML-fit NEVER demotes (precedence-pin)**" with citation to `tests/test_s13_ml_fit_never_demotes.py` as contract anchor.
  - Add new T2.5 briefing.html-byte-identity-preserved-via-renderer-non-consumption invariant to §5 if it earns it.
- `ROADMAP.md` — S13 row CLOSED, S13.5 row anchored (KI-NEW-L), S14 row promoted to active.
- `KNOWN_ISSUES.md`:
  - Extend KI-NEW-P with **consumer-side calibration cells** (does the consumer correctly select fallback strategy when given each fit_status combination? does ML-fit warning emission match expected? does `month_2_delta` correctly detect across runs?). ~6 new sub-bullets per substrate × consumer-behavior.
  - KI-NEW-L: confirm S13.5 disposition (OPEN with S13.5 commitment-date set; not closed at S13 close).
  - Possibly new KI-NEW-W (engine_run.json re-pin contract — ledger-keyed approach as the new norm for consumer-wiring sprints).
- `agent_outputs/INDEX.md` — S13 closed-sprint section with all 9 receipts (T0 + 6 implementation + T4-CLOSE + any DS verdicts).
- `agent_outputs/code-refactor-engineer-s13-t4-close-summary.md` — sprint-close receipt.
- `PIVOTS.md` — **clarifier-to-Pivot-5 addition (per DS §G.3):** "`predicted_segment.segment_name` populated on `small_sm` (the only synthetic that VALIDATES RFM) is structural-correctness per Pivot 5, NOT predictive accuracy. Downstream readers MUST NOT treat synthetic VALIDATED outcomes as proof of merchant value. Closure remains S14 real-merchant calibration per KI-NEW-P."

**Acceptance criteria:**
- All docs updated; cross-references resolve (Documentation Discipline gate).
- `KI-NEW-P` extension cites all 6 substrates × consumer-side calibration cells.
- `STATE.md` §4 ML-fit gate row reads "LIVE — emitter wired at S13; ML-fit NEVER demotes (precedence-pin)" with citation to `tests/test_s13_ml_fit_never_demotes.py`.
- `PIVOTS.md` Pivot 5 clarifier landed.
- `memory.md` entry restates both month-2-via-EB note AND KI-NEW-L S13.5 commitment date.
- `Deviation check: none.`

**Required summary file:** `agent_outputs/code-refactor-engineer-s13-t4-close-summary.md`.

---

## Part E — Cross-cutting risks (significant at S13)

### E.1 briefing.html byte-identity preserved; engine_run.json byte-identity intentionally broken at T2.5

**Plan stance:** briefing.html byte-identity is **preserved** at T2.5 (the renderer does NOT consume the new PlayCard fields — REQUIRED grep pin at T2.5 acceptance per DS §D.6). The break is JSON-side only.

**JSON byte-identity break:** intentional at T2.5. Managed via the new pinned-sha ledger file `tests/fixtures/pinned_sha_ledger.json` carrying `pre_s13` and `post_s13` shas keyed per fixture per artifact.

**Re-pin contract (LOCKED Option α per Q-S13-2):** atomic per-ticket. Each ticket that changes JSON shas re-pins the goldens, with rollback test asserting flag-OFF reproduces previous ledger entry. Mirrors S10/S11/S12 atomic-flip discipline.

### E.2 First sprint where PlayCard schema additions are POPULATED

At S6-T1 the stubs were added (`Optional[...] = None` default). At S13-T2.5 the producer arrives. The Sprint-2 schema-freeze contract holds (additive within `event_version=1`) but downstream consumers now have to expect populated fields. Stop-Coding-Line discipline holds — engine emits typed; renderer narrates downstream.

### E.3 First sprint where ML-fit ReasonCodes emit — **invariant pin REQUIRED**

The dormant `MODEL_FIT_INSUFFICIENT_DATA` and `MODEL_FIT_REFUSED` codes (added at S10-T3 per `src/engine_run.py:172-173`) start emitting. Per Q-S13-4 LOCK, emission is ONLY via `model_card_ref.fit_warnings`, NEVER via `RejectedPlay.reason_code`.

**REQUIRED invariant test (DS §B, §E.1):** `tests/test_s13_ml_fit_never_demotes.py` asserts no `RejectedPlay` carries `MODEL_FIT_*` reason codes across all 5 pinned fixtures + the new synthetic month-2 fixture. T4-CLOSE STATE.md §4 cites this test as contract anchor.

### E.4 Synthetic-fixture realism shift (Pivot 5 honest extension)

After S13-T2.5 the per-fixture engine_run.json reflects which substrates were CONSUMED. Specifically:
- 4 fixtures (Beauty, Supplements, mid_shopify, micro_coldstart) carry RFM REFUSED via `quintile_collapse` → PlayCard `predicted_segment` stays None; `model_card_ref.strategy_used = "RECENCY"`.
- 1 fixture (`small_sm`) carries RFM VALIDATED → `predicted_segment.segment_name = <modal>` (subject to stability floor); `model_card_ref.strategy_used = "RFM"` with full fit_status_chain showing BG/NBD + CF + survival upstream REFUSED.

PIVOTS.md Pivot 5 clarifier at T4-CLOSE marks `small_sm`'s populated `predicted_segment` as structural correctness, NOT predictive accuracy. **NOT a beta-readiness shift.**

### E.5 Modal-segment stability floor (v2 NEW)

**Risk:** modal-segment computation unstable on small or heterogeneous audiences.
**Mitigation (LOCKED per DS §D.4):** `predicted_segment.segment_name = None` when `n_audience < 50` OR `audience_modal_share < 0.30`. Ranking still proceeds; only the surfaced `segment_name` suppresses. Unit-tested at T2.

### E.6 Determinism comparator extension

Need to verify whether `predicted_segment` / `model_card_ref` / `month_2_delta` carry any wall-clock fields (they should not — `fit_timestamp` lives inside ModelCard, not on the references). Plan: explicit no-op test confirming the new fields are wall-clock-free. If wall-clock surfaces (e.g., `month_2_delta.days_between_runs`), it must enter the determinism comparator's normalized-paths list at T3.

### E.7 KI-NEW-L disposition at S13.5

Per `ROADMAP.md` §3 L74 — KI-NEW-L stays OPEN through S13 close, **collapses at S13.5** as a separate ticket between S13-T4-CLOSE and S14-T1. S13 plan does NOT include KI-NEW-L collapse (scope discipline). T4-CLOSE memory.md entry MUST restate the S13.5 commitment date.

---

## Part F — KI filing posture for S13 close

1. **KI-NEW-P extension** with consumer-side calibration cells (~6 sub-bullets covering: ranking-strategy chain fallback selection accuracy; ML-fit warning emission correctness; `predicted_segment.segment_name` audience-modal-correctness; modal-segment stability floor calibration on real merchants; `month_2_delta` detection robustness across days_between_runs edge cases; substrate-fit-status-change correctness; SegmentShiftSummary mover-detection sensitivity; lineage-change suppression). Closure remains S14 real-merchant.

2. **KI-NEW-L** — re-anchored at S13.5; NOT closed at S13 close. Stays open with explicit S13.5 commitment date in T4-CLOSE memory.md entry (per Q-S13-6 LOCK).

3. **NEW KI-NEW-W (likely)** — engine_run.json re-pin ledger contract. Carries the pre_s13 → post_s13 sha-tracking pattern as the new norm for consumer-wiring sprints. Closure trigger: post-beta documentation pass OR first time a S14 consumer-wiring ticket follows the same pattern.

4. **Sub-bullets for edge cases:**
   - Merchant with all 6 substrates REFUSED on month-1: PlayCard `model_card_ref.strategy_used = "RECENCY"` on every card; `predicted_segment = None`; `month_2_delta` carries only fit-status-changes (no segment_shifts, no retention_ci_delta).
   - Merchant with month-2 between 21d and 35d: detection fires; SegmentShiftSummary may be unstable on small N.
   - Merchant whose lineage changed between runs (per D-1): `month_2_delta.prior_run_lineage_id` carries the prior lineage; `substrate_fit_status_changes` proceeds; `segment_shifts = None` with `notes = "lineage_changed_segment_shift_incomparable"` (v2 LOCK).

---

## Part G — Open questions resolved at v2

All 6 founder-domain questions LOCKED per founder ack 2026-05-29:

| # | Question | Verdict | Anchor |
|---|---|---|---|
| Q-S13-1 | S13-T0 ModelCard refactor — defer further or do now? | **LOCKED — DO at T0.** 5+ projected field-presence sites trigger fires. | DS §C, founder ack 2026-05-29 |
| Q-S13-2 | engine_run.json re-pin contract — atomic per-ticket vs sprint-close? | **LOCKED — Option α (atomic per-ticket).** Mirrors S10–S12 atomic-flip discipline. | DS §C, founder ack 2026-05-29 |
| Q-S13-3 | `month_2_delta` merchant-facing copy — at S13 or deferred? | **LOCKED — operator-only at S13.** Pivot 2 Stop-Coding Line. Optional debug print under `ENGINE_DEBUG_CATEGORIES`. | DS §C, founder ack 2026-05-29 |
| Q-S13-4 | ML-fit ReasonCode emission scope — (A) `model_card_ref.fit_warnings`, (B) `RejectedPlay.reason_code`, or both? | **LOCKED — (A) ONLY.** `RejectedPlay.reason_code` MUST NOT carry `MODEL_FIT_*` codes. Ever. T2 revises `src/engine_run.py:167-171` comment. | DS §B (load-bearing), founder ack 2026-05-29 |
| Q-S13-5 | Ranking-strategy chain code location — new module or extend `audience_builders.py`? | **LOCKED — NEW `src/predictive/ranking_strategy.py`.** Cleanly separated from audience-definition logic. | DS §C, founder ack 2026-05-29 |
| Q-S13-6 | KI-NEW-L disposition at S13.5 — status? | **LOCKED — OPEN with explicit S13.5 commitment** (collapse between S13-T4 and S14-T1). T4-CLOSE memory.md restates commitment date. | DS §C, founder ack 2026-05-29 |

---

## Part H — Cadence summary

**8 tickets total** (unchanged from v1; acceptance criteria expanded per DS §E):

| Ticket | Kind | Flag | Behavior |
|---|---|---|---|
| S13-T0 | Correctness debt refactor (LOCKED DO) | none | Substrate-side ModelCard metrics refactor; FLAG-OFF-equivalent |
| S13-T1 | Mechanism | `ENGINE_V2_RANKING_STRATEGY_CHAIN`=OFF | Ranking chain module + AudienceIntent enum + positive-control synthetic |
| S13-T1.5 | Atomic flip | `ENGINE_V2_RANKING_STRATEGY_CHAIN`=ON | Chain available; no consumer yet |
| S13-T2 | Mechanism + comment revision | `ENGINE_V2_PLAY_PREDICTED_SEGMENT`=OFF | PlayCard consumer wiring + `:167-171` comment revision + ML-fit-never-demotes invariant pin + modal-segment stability floor |
| S13-T2.5 | Atomic flip + first intentional engine_run.json re-pin | `ENGINE_V2_PLAY_PREDICTED_SEGMENT`=ON | PlayCard predicted_segment + model_card_ref populated; renderer-non-consumption grep REQUIRED |
| S13-T3 | Mechanism | `ENGINE_V2_MONTH_2_DELTA`=OFF | MonthDelta + detection + lineage-change constraint + positive-control synthetic |
| S13-T3.5 | Atomic flip | `ENGINE_V2_MONTH_2_DELTA`=ON | month_2_delta populated for returning merchants |
| S13-T4-CLOSE | Sprint-close docs | none | KIs / ROADMAP / STATE §4 revision / memory.md / INDEX / PIVOTS Pivot-5 clarifier |

Three mechanism / atomic-flip pairs + T0 (LOCKED DO) + T4-CLOSE.

---

## Part I — Files / functions touched (consolidated map)

**Schema (`src/engine_run.py`):**
- `PredictedSegment` — extend to `{segment_name, audience_modal_share, n_audience, rfm_fit_status, notes}`.
- `ModelCardRef` — extend to `{strategy_used, fit_status_chain, fit_warnings: List[str] (LOCKED), notes}`.
- NEW `MonthDelta`, `FitStatusChange`, `SegmentShiftSummary` dataclasses.
- NEW `EngineRun.month_2_delta: Optional[MonthDelta] = None`.
- `_from_dict_predicted_segment` / `_from_dict_model_card_ref` round-trip extensions.
- NEW `_from_dict_month_delta`.
- **REVISED COMMENT BLOCK at L167-171 (T2, per Q-S13-4 LOCK).**

**Substrate (`src/predictive/model_card.py`):**
- S13-T0: `ModelCard.metrics: Dict[str, float]` + `RetentionCard.metrics`; legacy typed fields preserved via `@property` shim.

**New modules:**
- `src/predictive/ranking_strategy.py` (NEW; T1) with `AudienceIntent` enum + `RankingStrategyResult` (strategy_used: `Optional[Literal[...]]`).
- `src/month_delta.py` (NEW; T3).

**Orchestration (`src/main.py`):**
- Post-S12 predictive blocks at L1156+ remain unchanged.
- NEW: at end of per-store dispatch loop, before final `engine_run` write, call `compute_month_delta(...)` (T3).
- Chain consumption lives inside `build_prior_anchored_play_card` (no main.py change for chain consumption).

**Measurement (`src/measurement_builder.py`):**
- `build_prior_anchored_play_card` — call `rank_audience`; populate PlayCard.predicted_segment + model_card_ref; enforce modal-segment stability floor (T2).

**Audience (`src/audience_builders.py`):**
- 4 Tier-B builders: provide `AudienceIntent` per builder (T2).

**Sizing (`src/sizing.py`):** NOT TOUCHED.

**Guardrails (`src/guardrails.py`):** NOT TOUCHED (Pivot 7).

**Decide (`src/decide.py`):** Possibly extended with an assert that no `RejectedPlay` carries `MODEL_FIT_*` reason codes.

**Renderer (`src/briefing.py`):** NOT TOUCHED at T2.5 (REQUIRED grep pin verifies). Optional `month_2_delta` debug section may land at T3.5 under `ENGINE_DEBUG_CATEGORIES` (per Q-S13-3 lock — operator-only).

**Config (`config/gate_calibration.yaml`):** NEW `ranking_strategy_chain` block (documentation-only).

**Docs (`docs/engine_flags.md`):** Three new flag rows.

**Flag defaults (`src/utils.py::DEFAULTS`):** `ENGINE_V2_RANKING_STRATEGY_CHAIN`, `ENGINE_V2_PLAY_PREDICTED_SEGMENT`, `ENGINE_V2_MONTH_2_DELTA`.

---

## Part J — New artifacts produced

- `engine_run.json` keys:
  - `play_cards[*].predicted_segment` (populated; was always None pre-S13; subject to stability floor).
  - `play_cards[*].model_card_ref` (populated; was always None pre-S13).
  - `play_cards[*].model_card_ref.fit_warnings` (List[str] with LOCKED grammar).
  - `month_2_delta` (populated only for returning merchants ≥21d since prior run; None on first run).
- Parquet: no new files.
- NEW `tests/fixtures/pinned_sha_ledger.json`.
- NEW synthetic month-2 fixture for T3 positive control.

---

## Part K — Acceptance criteria roll-up

For sprint close:
1. All 8 tickets shipped; per-ticket DS verdict; per-ticket `code-refactor-engineer-s13-<ticket>-summary.md` receipt.
2. Flag defaults flipped: `ENGINE_V2_RANKING_STRATEGY_CHAIN` + `ENGINE_V2_PLAY_PREDICTED_SEGMENT` + `ENGINE_V2_MONTH_2_DELTA` all ON.
3. All 5 pinned fixtures: `briefing.html` sha unchanged at S13 close (renderer-non-consumption pin verifies). `engine_run.json` sha changed in confined ways per ledger.
4. Rollback contract: every flag explicitly set OFF reproduces the prior-ticket byte-identical state.
5. M0 byte-identical end-to-end.
6. **ML-fit precedence invariant pinned via `tests/test_s13_ml_fit_never_demotes.py`** — no `RejectedPlay` carries `MODEL_FIT_*` reason codes.
7. **`src/engine_run.py:167-171` comment revised** per Q-S13-4 LOCK; T2 commit carries `Deviation check: comment-revision-per-DS-lock-Q-S13-4`.
8. **Positive-control synthetics shipped:** `tests/test_ranking_strategy_positive_control.py` (5 fall-through paths) + `tests/test_month_delta_positive_control.py` (2-run sequence).
9. **Renderer-non-consumption grep** REQUIRED at T2.5 returns empty.
10. **Modal-segment stability floor** enforced (n<50 OR modal_share<0.30 → segment_name=None).
11. **Lineage-change constraint** enforced for `month_2_delta.segment_shifts`.
12. STATE.md §4 updated to "LIVE — emitter wired at S13; ML-fit NEVER demotes (precedence-pin)" with citation to invariant test.
13. ROADMAP.md S13 row CLOSED; S13.5 row anchored with KI-NEW-L collapse commitment date.
14. PIVOTS.md Pivot 5 clarifier landed (small_sm `predicted_segment` is structural, not predictive).

---

## Part L — Test strategy

**Per-ticket:**
- Unit tests for each new dataclass / function (round-trip, fall-through, detection).
- Rollback contract test for each atomic-flip ticket (flag-OFF reproduces previous ledger state).
- Per-fixture validation on the 5 pinned fixtures.
- **REQUIRED positive-control synthetics:**
  - T1: `tests/test_ranking_strategy_positive_control.py` covering 5 fall-through paths (per DS §D.5).
  - T3: `tests/test_month_delta_positive_control.py` covering substrate-fit-status-change + segment_shifts + retention_ci delta on a constructed 2-run sequence on `small_sm`.

**Cross-cutting:**
- **REQUIRED ML-fit-never-demotes invariant pin** at T2 (`tests/test_s13_ml_fit_never_demotes.py`).
- **REQUIRED renderer-non-consumption grep** at T2.5 (`grep -rn "predicted_segment\|model_card_ref" src/briefing.py` returns empty).
- Determinism comparator extension (verify no new wall-clock leaks).
- briefing.html sha-unchanged assertion across all 5 fixtures at every atomic-flip.
- ledger sha tracking on `engine_run.json`.
- Modal-segment stability-floor unit tests (n<50, modal_share<0.30 boundary cases).
- Lineage-change suppression test for `month_2_delta.segment_shifts`.

---

## Part M — Risks and rollback

**Risk 1 — ranking-strategy chain selects wrong fallback for an edge fit-status combination.** Mitigation: T1 positive-control matrix covers 5 most-meaningful paths (DS §D.5 REQUIRED); abbreviated assertion table on the 16 most-meaningful combinations.

**Risk 2 — `predicted_segment` modal-segment computation is unstable for small/heterogeneous audiences.** **v2 MITIGATED:** stability floor LOCKED (`n_audience < 50` OR `audience_modal_share < 0.30` → `segment_name = None`) per DS §D.4. Unit-tested at T2.

**Risk 3 — `month_2_delta` detection misfires on edge calendar cases.** Mitigation: lineage-keyed (not wall-clock); 21d floor preserves intent. **v2 ADDITION:** lineage-change constraint suppresses `segment_shifts` when `audience_definition_version` bumps; typed note `"lineage_changed_segment_shift_incomparable"`.

**Risk 4 — JSON byte-identity break cascades into downstream consumers.** Mitigation: NEW `KI-NEW-W` filing carrying the ledger pattern; renderer-non-consumption grep REQUIRED at T2.5 ensures `briefing.html` stays byte-identical.

**Risk 5 (v2 NEW) — `:167-171` comment revision interpreted as unrelated drift.** Mitigation: T2 commit body MUST carry `Deviation check: comment-revision-per-DS-lock-Q-S13-4`. DS founder escalation §G.5 surfaces this expectation.

**Risk 6 (v2 NEW) — Downstream reader treats `small_sm` populated `predicted_segment` as predictive accuracy.** Mitigation: T4-CLOSE PIVOTS.md Pivot 5 clarifier explicitly marks synthetic VALIDATED outcomes as structural-correctness only.

**Rollback strategy:** every flag flip is independently revertable. The T0 refactor is harder to roll back — the `metrics` dict is the canonical store. Mitigation: legacy typed-field property shim preserves old reads, so consumer code remains forward-compat through T0.

---

## Part N — What NOT to touch

- `src/sizing.py` (PSEUDO_N table locked through S14 per STATE.md §5 invariant 5).
- `src/guardrails.py` (single-demote-channel invariant — Pivot 7).
- `src/main.py:1380-1597` (5 V2 prior-anchored injection blocks — KI-NEW-L S13.5 territory).
- 6 substrate fit functions in `src/predictive/*.py` beyond the T0 metrics-dict refactor.
- `config/priors.yaml` (S8-T0 SciPy-authoritative percentiles).
- `tests/test_s7_6_c1_priority_prepend_invariant.py` (observed-effect tripwire).
- `briefing.py` (Stop-Coding-Line — Pivot 2). Renderer-non-consumption grep is the REQUIRED structural verification.
- Phase 9 outcome-loop scaffolding (deferred post-beta per `ROADMAP.md` §4).
- KI-NEW-L collapse (S13.5 separate ticket).
- Klaviyo/Shopify network calls (D-5).
- Any non-{beauty, supplements, mixed} vertical scope (D-8).
- `RejectedPlay.reason_code` for `MODEL_FIT_*` codes — **NEVER, per Q-S13-4 LOCK.**

---

## Sources

- `PRODUCT.md` §5 (month-1-wow / month-2-return); §6 D-1..D-8.
- `STATE.md` §4 (gates + ML-fit dormant→S13); §5 invariants (esp. 2, 5, 6); §8 file map.
- `PIVOTS.md` Pivot 2 (Stop-Coding Line), Pivot 5 + S12-T2.5 clarifier, Pivot 7 (single-demote-channel), Pivot 8 (month-1-wow / month-2-return).
- `ROADMAP.md` §1 (S13 scope queued); §2 (S13 row); §3 (KI-NEW-L S13.5 anchor).
- `KNOWN_ISSUES.md::KI-NEW-L` (S13.5 collapse), `::KI-NEW-P` (3-shape closure criteria), `::KI-NEW-T` / `::KI-NEW-U` / `::KI-NEW-V` (S12 backlog).
- `agent_outputs/INDEX.md` §2 Sprints 10/11/12 sections.
- `agent_outputs/ds-architect-s10-cold-start-and-eb-interaction.md` (load-bearing ranking-vs-prediction framing; ML-fit lowest precedence; INSUFFICIENT_DATA vs REFUSED audit-story distinction).
- `agent_outputs/ds-architect-s13-plan-review.md` (v2 driver — all 11 required changes + 6 Q&A locks).
- `agent_outputs/ds-architect-s10-plan-review.md`, `ds-architect-s11-plan-review.md`, `ds-architect-s12-plan-review.md`.
- `agent_outputs/implementation-manager-s10-ml-part1-plan.md` (v2), `s11-ml-part2-plan.md` (v2), `s12-rfm-retention-plan.md` (v2).
- `src/engine_run.py` PlayCard / EngineRun schema; ReasonCode at L172-173 (dormant); precedence comment at L159-171.
- `src/predictive/model_card.py` — ModelCard, RetentionCard, ModelFitStatus, threshold loader.
- `src/predictive/rfm.py` — SEGMENT_LTV_RANK_ORDER + 11 named segments.
- `src/main.py` L1040-L1244 — 5 wired predictive blocks.
- `docs/engine_flags.md` L138-148 (gate row + ranking-strategy chain), L161-165 (chain DS-locked statement).

*End of plan (v2).*
