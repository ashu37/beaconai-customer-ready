# Implementation Manager — S13.5 + S13.6 + S13.7 Plan

## REVISION HISTORY

- **v1 — 2026-05-30** — initial plan from `agent_outputs/implementation-manager-s13.5-s13.6-s13.7-plan.md` first draft.
- **v2 — 2026-05-30** — applied DS APPROVE-WITH-CHANGES verdict (`agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md`): R1 NonLiftAtom wrapper at T3; R2 MechanismType closed enum locked at T6 per DS §(d); R3 Optional-by-Optional triage table at T7 per DS §(e); R4 RFM-REFUSED branch at S13.7-T1; R5 T1 split into T1a + T1b; R6 re-export source-of-truth note at T2; R7 NEW S13.6-T7.5 null-reason enum registry. Adjudicated 6 IM open questions per DS §(b); surfaced 5 founder-level open questions per DS §(f).
- **v2.1 — 2026-05-30** — S13.6-T1a Option D approved (DS adjudication + founder approval): drop briefing.html byte-identity pin; bundle renderer-side cleanup (`storytelling_v2.py`, `briefing.py`, `debug_renderer.py`) + `decide.py` `_apply_copy_ladder` deletion in the same atomic commit as the dataclass strip; canary shifts to `engine_run.json` SHA + S13.7-T2 JSON-Schema round-trip. §11 acceptance, §13 risk, §15/§16 RESOLVED notes, Pivot 2 addendum timing (T1a, not T8) revised inline.

---

**Date:** 2026-05-30
**Branch:** `post-6b-restructured-roadmap`
**Author role:** Implementation Manager (plan-only — no dispatch, no src/ edits)
**Scope:** 3 sequential sprints between S13-T4-CLOSE and S14 real-merchant beta.
**Input verdicts driving this plan:**
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ds-architect-engine-readiness-for-agents.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ds-architect-end-to-end-flow-readiness.md`
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md` (v2 driver — APPROVE-WITH-CHANGES)

**Founder lock-ins applied (2026-05-30):**
1. Strip ALL engine-authored prose fields (Option a for every field).
2. Keep 4 slate lists (no merged-discriminator shape).
3. Hard freeze contract at `schema_version="2.0.0"` after S13.6.
4. Engine ships structured atoms only; narration agents render copy.
5. Sequence: S13.5 → S13.6 → S13.7 → handoff → S14.
6. Strip `klaviyo_brief_inputs` entirely.

**Load-bearing founder rules (apply to every ticket below):**
- **RULE A — Agent never assumes.** Engine is the agent's only source of information. Absence-of-data must be a typed signal (explicit `null` + reason), never a silent gap.
- **RULE B — Segments must be absolutely trustworthy.** Every `customer_id` in every audience CSV must be traceable through (i) substrate `ModelCard` that ranked them, (ii) audience-builder definition that included them, (iii) `audience_definition_version` pinned at that run. Deterministic, reproducible, audit-traceable.

---

## 1. Implementation verdict

Three sprints. **16 tickets total** across S13.5 (1) + S13.6 (10 = 9 work + 1 close) + S13.7 (5 = 4 work + 1 close). Engine remains runnable and useful after every ticket. `briefing.html` byte-identity holds across the entire 3-sprint window (renderer does not consume the prose fields being stripped — verified at S13 close). `engine_run.json` SHA values WILL change at S13.6 — pinned fixtures re-pinned via the existing ledger pattern.

After S13.7, the engine is **handoff-ready** for the founder/team's narration MCP + assembly MCP + frontend build. S14 (real-merchant beta) gates on agent build, not further engine work.

---

## 2. Target architecture (post-S13.7 end state)

**Pipeline (unchanged):** `PROFILE → AUDIENCE → MEASUREMENT → SIZING → DECIDE`. Six predictive substrates with consumers. Four orthogonal gates LIVE.

**Contract surface (`src/engine_run.py` at v2.0.0, frozen):**
- Zero engine-authored prose fields.
- Zero `Any`-typed slots on the public contract surface.
- Every `Optional[X]` field paired with a typed `<field>_null_reason: Optional[<Enum>]` per RULE A (T7 pattern A, DS-confirmed).
- `MechanismIntent` typed atom replaces `mechanism: str` per founder decision #4; `MechanismType` is a DS-locked **closed** enum (see §5 T6 + DS §(d)).
- `OpportunityContext` carries a typed `NonLiftAtom` wrapper field (DS R1) — the highest-single-risk guardrail expressed AT THE TYPE, not via a sibling bool flag.
- `FitWarning(level: FitWarningLevel, substrate: str)` dataclass replaces `List[str]` grammar.
- Single source-of-truth null-reason enum registry block at top of `engine_run.py` (T7.5) — agents read one place.
- CHANGELOG block at top of `engine_run.py` documents S8 → S13.6 additive growth.

**Filesystem handoff (post-S13.7, per run):**
```
data/<store_id>/runs/<run_id>/
├── engine_run.json              (v2.0.0 typed contract)
├── manifest.json                (artifact enumeration + audience_materialization_status per PlayCard)
├── audiences/<aud_def_id>.csv   (customer_id resolver output, RULE B; empty-header-only under SUBSTRATE_REFUSED)
├── predictive/*.parquet         (substrate artifacts)
└── cohort_diagnostics/retention.json
```

**Schema validation:** `schemas/engine_run.v2.json` published; `tools/validate_engine_run.py` round-trips every pinned fixture.

**Mechanism contract:** `MechanismType` enum (closed set, DS-locked) + per-type `parameters` dict shape documented at `docs/mechanism_contract.md` — the contract the narration agent codes against. Send-time logic OWNED BY NARRATION AGENT (per DS rec #3); engine emits intent only.

**Legacy retirement:** `src/segments.py::segments/*.csv` writer RETIRED at S13.7-T1 with `raise NotImplementedError("Retired at S13.7-T1; use audience_resolver")` (DS-locked — no silent deprecation).

---

## 3. Milestone plan

| Sprint | Theme | Tickets | Risk |
|---|---|---|---|
| **S13.5** | KI-NEW-L collapse (structural cleanup) | T1 (1 ticket) | Low — invariant-preserving refactor; byte-identical engine behavior |
| **S13.6** | engine_run.json agent-contract cleanup | T1a, T1b, T2, T3, T4, T5, T6, T7, T7.5, T8 (9 work + 1 close = 10) | Highest — T3 (NonLiftAtom wrapper) is HIGHEST contract-shape risk per DS; T7 (RULE A absence pattern) is most architecturally novel; T6 audits closed mechanism set |
| **S13.7** | Agent handoff completion | T1, T2, T3, T4 (4 tickets — 3 work + 1 close) | Highest single ticket: T1 audience resolver carries RULE B reputation-killer risk; RFM-REFUSED branch required (DS R4) |

Per-ticket loop (every ticket in all 3 sprints): **refactor-engineer dispatch → DS review → orchestrator commits & pushes → next ticket.** Every dispatch brief MUST require `agent_outputs/code-refactor-engineer-s13.X-tY-summary.md` per S6/S7 precedent (per `memory/MEMORY.md::feedback_refactor_dispatch_includes_summary_file.md`). Every commit body MUST carry `Deviation check: none.` (or `Deviation check: [describe] — <prior approval>`).

---

## 4. Phase 1 — S13.5 tickets (KI-NEW-L collapse)

### S13.5-T1 — Collapse 5 V2 prior-anchored injection blocks → single `dispatch_prior_anchored_builders`

**Source:** `KNOWN_ISSUES.md::KI-NEW-L` (L411–420): *"Collapse the five blocks into a single `dispatch_prior_anchored_builders` function keyed by the `_PRIOR_ANCHORED` registry at `src/measurement_builder.py:717`. The function takes the builder result, runs `apply_guardrails_to_injected` once, and appends to `engine_run.recommendations` via the single demote channel."*

**Files affected:**
- `src/main.py:1380-1597` — collapse 5 injection blocks → 1 dispatch function.
- `src/measurement_builder.py:717` — `_PRIOR_ANCHORED` registry (read-only; serves as dispatch key).
- `src/guardrails.py::apply_guardrails_to_injected` — single demote channel (unchanged).

**Behavior:** byte-identical. The collapse is a refactor, not a semantic change.

**Invariants preserved (DS-locked):**
1. Single-demote-channel (Pivot 7) — all paths route through `apply_guardrails_to_injected`.
2. Three-channel `priority_prepend` — `eligibility_rejects`, `prior_unvalidated_rejects`, `window_disagreement_rejects`.
3. Observed-effect surfacing at `src/measurement_builder.py:2252-2270`.
4. Per-builder byte-identity on pinned slates (Beauty + supplements fixtures).

**Tests:**
- All existing pinned-fixture tests pass unchanged.
- `tests/test_s7_6_c1_priority_prepend_invariant.py` — observed-effect tripwire + 3-channel prepend.
- **NEW** `tests/test_s13_5_single_emission_point.py` — asserts the new dispatch function is the single emission point for V2 prior-anchored builders (AST-aware: no other call site appends to `engine_run.recommendations` for prior-anchored builders).

**Acceptance criteria:**
- Beauty fixture SHA unchanged.
- Supplements fixture SHA unchanged.
- M0 goldens byte-identical.
- Full suite pass (target: existing 1100+ tests + new test).
- Deviation check: none.

**Artifacts:**
- `agent_outputs/code-refactor-engineer-s13.5-t1-summary.md` (REQUIRED per founder protocol).
- Commit body: `Deviation check: none`.

**Risk:** Low. Invariant-preserving structural cleanup; DS-locked predicate.

---

## 5. Phase 2 — S13.6 tickets (engine_run.json agent-contract cleanup)

This is the largest of the 3 sprints. **10 tickets** (9 work + 1 close).

### S13.6-T1a — Strip prose bundle (everything except `Observation.text`) (DS R5 split)

**Per DS R5:** *"Founder decision #1 says strip-all, but T1 dispatch must verify renderer non-consumption per stripped field before the strip lands, not as a single bundle. Two commits, two atomic flips."*

**Strip from contract surface (T1a bundle):**
- `PlayCard.recommendation_text` → STRIP.
- `PlayCard.why_now` → STRIP.
- `RejectedPlay.reason_text` → STRIP. Narration agent reads `reason_code` enum + `held_reason_detail` structured numerics.
- `RejectedPlay.evidence_snapshot` → STRIP.
- `RejectedPlay.would_fire_if` → STRIP (founder decision #1 = Option a strip).
- `Abstain.reason` → STRIP. Keep `state` + `mode` enums.
- All `notes: List[str]` debris on S6+ dataclasses (`PredictedSegment.notes`, `ModelCardRef.notes`, `Provenance.notes`, `Sensitivity.notes`, etc.) → STRIP from JSON serialization (move to debug-only mode behind `INCLUDE_DEBUG_FIELDS=true`).

**Files affected:**
- `src/engine_run.py` — dataclass field removals + `to_dict()` exclusions.
- All builders that populate stripped fields — remove population code.

**Pivot 2 alignment:** Per `PIVOTS.md` Pivot 2 L24-30: *"engine_run.json is the product contract."* These prose fields are the literal violations the DS verdict flagged.

**Pre-strip verification (per DS R5):** AST-grep renderer (`src/briefing.py` and all jinja templates) for each stripped field name BEFORE the strip lands. Document non-consumption in the summary file.

**Tests:**
- **NEW** `tests/test_s13_6_t1a_prose_bundle_strip.py` — asserts every stripped field absent from `engine_run.to_dict()` and emitted JSON.
- `briefing.html` byte-identity tests pass unchanged.
- `engine_run.json` SHA — re-pin via existing fixture ledger.

**Acceptance criteria** (REVISED 2026-05-30 per DS Option D adjudication + founder approval — see REVISION HISTORY v2.1 below):
- `engine_run.json` SHAs schema-validated and re-pinned post-strip.
- `briefing.html` byte-identity pin RETIRED at T1a per DS Option D + founder approval 2026-05-30. The renderer stays runnable for local dev (no `AttributeError`) but is no longer load-bearing on the contract.
- Canary shifts to `engine_run.json` SHA + S13.7-T2 JSON-Schema round-trip.
- Renderer-side cleanup (`storytelling_v2.py`, `briefing.py`, `debug_renderer.py`) and decide.py `_apply_copy_ladder` deletion BUNDLED into the same atomic commit per DS Option D.
- `INCLUDE_DEBUG_FIELDS=False` (DEFAULTS, env-overridable) gates `notes: List[str]` debris from emitted JSON.
- Deviation check: one (Option D scope expansion — renderer cleanup + canary shift — approved DS+founder 2026-05-30, documented in PIVOTS.md addendum).

**Artifact:** `agent_outputs/code-refactor-engineer-s13.6-t1a-summary.md`.

---

### S13.6-T1b — Strip `Observation.text` (DS R5 split)

**Per DS R5:** `Observation.text` carries some downstream renderer consumption in older Tier-B paths per S6 history. Separate atomic flip.

**Strip:**
- `Observation.text` → STRIP. Keep typed numerics: `supporting_metric`, `change_magnitude`, `classification`, `current`, `prior`, `delta_pct`, `anomaly_flags`, `n_days_observed`, `n_days_expected`.

**Files affected:**
- `src/engine_run.py` — `Observation` dataclass field removal.
- Tier-B builders that populate `Observation.text` — remove population.

**Pre-strip verification:** AST-grep renderer for `Observation.text` consumption sites. Document each non-consumption (or surface real consumption and ESCALATE before strip).

**Tests:**
- **NEW** `tests/test_s13_6_t1b_observation_text_strip.py`.
- `briefing.html` byte-identity.

**Acceptance criteria:**
- `Observation.text` absent from emitted JSON.
- `briefing.html` byte-identical.
- Deviation check: none.

**Artifact:** `agent_outputs/code-refactor-engineer-s13.6-t1b-summary.md`.

---

### S13.6-T2 — Type the 4 `Any` slots (DS P0 + founder decision #4) — re-export source-of-truth (DS R6)

**Re-type:**
- `EngineRun.store_profile: Optional[Any]` → typed dataclass `StoreProfile` re-exported from `src/engine_run.py`.
- `EngineRun.predictive_models: Dict[str, Any]` → `Dict[str, ModelCard]` re-exported from `src/engine_run.py`.
- `EngineRun.cohort_diagnostics: Dict[str, Any]` → `Dict[str, RetentionCard]` re-exported.
- `PlayCard.klaviyo_brief_inputs: Dict[str, Any]` → **REMOVE ENTIRELY** (founder decision #6).

**Per DS R6 — Re-export source-of-truth note (MUST appear in dispatch brief verbatim):**
> Schema authority = `src/engine_run.py`; re-export resolves to canonical type. `StoreProfile` (canonical at `src/profile/types.py`), `ModelCard` (canonical at `src/predictive/model_card.py`), and `RetentionCard` MUST be re-exported at `src/engine_run.py` so agents read ONE file. The contract boundary is the re-export, not the canonical definition file.

**Files affected:**
- `src/engine_run.py` — type annotations + re-exports.
- `src/profile/types.py` — confirm `StoreProfile` shape stable.
- `src/predictive/model_card.py` — confirm export-ready.
- `src/predictive/retention.py` — confirm `RetentionCard` export-ready.

**Tests:**
- **NEW** `tests/test_s13_6_t2_typed_any_slots.py` — runtime introspection + re-export imports resolve through `src/engine_run.py`.
- Pinned-fixture round-trip tests verify typed serialization.

**Acceptance criteria:**
- No `Any` annotations on the 4 named slots.
- `klaviyo_brief_inputs` absent from contract.
- All re-exports importable from `src/engine_run.py`.
- Pinned fixtures re-pin cleanly.
- Deviation check: none.

**Artifact:** `agent_outputs/code-refactor-engineer-s13.6-t2-summary.md`.

---

### S13.6-T3 — OpportunityContext: NonLiftAtom wrapper (DS R1 — HIGHEST SINGLE RISK)

**DS verdict §(c) R1 verbatim:** *"A `bool _do_not_narrate_as_lift = True` field on the dataclass is type-safety theatre. An agent that ignores it sees the numbers and narrates them. Replace with a wrapper dataclass at the field type level."*

**DS-flagged HIGHEST SINGLE RISK on the contract — guardrail expressed at type, not at field.**

**Work:**

Introduce the wrapper dataclass per DS §(c) R1 verbatim:

```python
@dataclass
class NonLiftAtom:
    value: float
    semantic: Literal["addressable_opportunity"]  # not lift, not p50, not forecast
    aov_used: float
    monthly_revenue_estimate: float
```

The wrapper *names* the constraint at the type system. Schema consumers see `NonLiftAtom`, not a number with a "please don't narrate as lift" sticker.

**Dedup decisions (DS-locked):**
- KEEP `aov_used` (more explicit about provenance); STRIP `aov`.
- KEEP `monthly_revenue_estimate` (the actual semantic); STRIP `addressable_value`.

**OpportunityContext re-shape:** The previously-dup'd numeric fields fold into the typed `NonLiftAtom` payload. Class-level docstring: *"OpportunityContext describes addressable opportunity, NOT projected lift / NOT p50 / NOT forecast. Narration agent reads `NonLiftAtom` — type itself names the constraint."*

**Files affected:**
- `src/engine_run.py:759-768` — `OpportunityContext` dataclass + new `NonLiftAtom` wrapper + class-level docstring.
- `_build_opportunity_context` in `src/main.py` — emit `NonLiftAtom`; drop dup'd fields.
- Renderer (`src/briefing.py`) — point at the wrapper's `monthly_revenue_estimate`.

**Tests:**
- **NEW** `tests/test_s13_6_t3_non_lift_atom_wrapper.py` — every emitted `OpportunityContext` carries `NonLiftAtom` with `semantic="addressable_opportunity"`; dup fields (`aov`, `addressable_value`) absent.
- Existing `tests/test_phase6a_b2_opportunity_context.py` forbidden-token sweep updated.

**Acceptance criteria:**
- One AOV field (`aov_used`); one revenue field (`monthly_revenue_estimate`); both inside `NonLiftAtom`.
- `NonLiftAtom` wrapper present on every emitted `OpportunityContext`.
- briefing.html byte-identical.
- Deviation check: none.

**Artifact:** `agent_outputs/code-refactor-engineer-s13.6-t3-summary.md`.

**Risk:** HIGHEST contract-shape risk per DS. Wrapper migration changes JSON shape of `opportunity_context` — re-pin SHAs and reconfirm renderer mapping.

---

### S13.6-T4 — `fit_warnings` typed grammar contract

**Current:** `model_card_ref.fit_warnings: List[str]` with `"{LEVEL}:{substrate}"` prefix grammar (per `docs/DECISIONS.md::D-S13-4`).

**Change:**
- Add `FitWarningLevel` enum: `PROVISIONAL_SELECTED`, `MODEL_FIT_INSUFFICIENT_DATA`, `MODEL_FIT_REFUSED`.
- Add `FitWarning` dataclass: `level: FitWarningLevel`, `substrate: str`.
- Change `ModelCardRef.fit_warnings: List[str]` → `List[FitWarning]`.

**Files affected:**
- `src/engine_run.py` — `ModelCardRef`, new enum, new dataclass.
- `src/predictive/consumer_wiring.py` — populate typed `FitWarning` instead of strings.
- `tests/test_s13_ml_fit_never_demotes.py` — update assertion shape.
- `tests/test_reason_code_precedence_invariant.py` (AST-aware) — verify still pinned.

**Tests:**
- **NEW** `tests/test_s13_6_t4_fit_warning_typed.py` — `fit_warnings` is `List[FitWarning]` and round-trips through JSON.

**Acceptance criteria:**
- Q-S13-4 LOCK preserved (ML-fit emits ONLY on `fit_warnings`, NEVER on `RejectedPlay.reason_code`).
- ML-fit-never-demotes 5-fixture runtime test passes.
- Deviation check: none.

**Artifact:** `agent_outputs/code-refactor-engineer-s13.6-t4-summary.md`.

---

### S13.6-T5 — `schema_version` bump 1.0.0 → 2.0.0 + CHANGELOG block

**Work:**
- Bump `EngineRun.schema_version` literal from `"1.0.0"` to `"2.0.0"`.
- Add CHANGELOG block at top of `src/engine_run.py` documenting S8 → S13.6 additions:
  - S8: `evidence_source` chip, `Sensitivity`, `Provenance`.
  - S10: `ModelCard`, `ModelFitStatus` 4-state enum.
  - S11: survival + CF substrate fields on `ModelCard`.
  - S12: `RetentionCard`, `cohort_diagnostics` top-level slot.
  - S13: `predicted_segment`, `model_card_ref`, `month_2_delta`, `MonthDelta`, Q-S13-4 LOCK at L167-183.
  - S13.6: prose-strip, `Any`-slot typing, `OpportunityContext` `NonLiftAtom` wrapper, typed `FitWarning`, `MechanismIntent` atom (closed enum), RULE A absence pattern + null-reason enum registry, `klaviyo_brief_inputs` removal.
- After S13.6: schema FROZEN at 2.x.x — additive in 2.x patch; breaking → 3.0.0.

**Files affected:** `src/engine_run.py`.

**Tests:**
- **NEW** `tests/test_s13_6_t5_schema_version_2_0_0.py`.
- Re-pin fixture SHAs.

**Acceptance criteria:**
- Schema version on emitted JSON = `2.0.0`.
- CHANGELOG block present.
- Deviation check: none.

**Artifact:** `agent_outputs/code-refactor-engineer-s13.6-t5-summary.md`.

---

### S13.6-T6 — `MechanismType` closed enum + `MechanismIntent` atomic typing (DS R2 + §(d) lock)

**Per DS §(c) R2:** T6 dispatch brief MUST cite the DS verdict §(d) enum list as the audit anchor. Refactor-engineer audits emission sites and verifies completeness/no-extras. **Any extra mechanism string outside the closed set escalates to DS, NOT a refactor-engineer call.**

**DS §(d) DS-locked MechanismType enum (MUST appear verbatim in dispatch brief):**

```
WINBACK_REACTIVATION_EMAIL    # winback_dormant_cohort
FIRST_TO_SECOND_NUDGE         # first_to_second_purchase, cohort_journey_first_to_second
THRESHOLD_BUNDLE_OFFER        # aov_lift_via_threshold_bundle
DISCOUNT_DEPENDENCY_HYGIENE   # discount_dependency_hygiene (suppression-style)
REPLENISHMENT_REMINDER        # replenishment_due
BESTSELLER_AMPLIFY            # bestseller_amplify (Tier-B)
CATEGORY_EXPANSION            # category_expansion (Tier-B)
SUBSCRIPTION_NUDGE            # subscription_nudge (Tier-B)
ROUTINE_BUILDER               # routine_builder (Tier-B)
LOOKALIKE_HIGH_VALUE_PROSPECT # high-value lookalike play
```

**Work:**
- Audit current `mechanism: str` emission sites: `_PRIOR_ANCHORED` registry (5 builders), Tier-B builders, legacy builders, Beauty+supplements fixtures.
- Define `MechanismType(str, Enum)` with **exactly** the values above. If any current emission produces a string outside this set, ESCALATE (do not silently extend).
- Replace `PlayCard.mechanism: str` with:
  ```python
  @dataclass
  class MechanismIntent:
      mechanism_type: MechanismType
      parameters: Dict[str, Any]  # per-mechanism_type structured; spec at docs/mechanism_contract.md
  ```
- Engine ships intent only — NO send-time, NO copy. Per DS rec #3, send-time logic owned by narration agent.

**Files affected:**
- `src/engine_run.py` — `MechanismType` enum, `MechanismIntent` dataclass, `PlayCard.mechanism` re-type.
- All builders emitting `mechanism: str` — convert.
- `src/measurement_builder.py`, `src/audience_builders.py`.

**Tests:**
- **NEW** `tests/test_s13_6_t6_mechanism_intent_closed_enum.py` — every emitted `PlayCard.mechanism.mechanism_type` is a member of `MechanismType`; exhaustive closed-set assertion; emission audit fixture pinned.
- Pinned fixtures re-pinned.

**Acceptance criteria:**
- All emission sites produce `MechanismIntent` (no `str` mechanisms remain).
- briefing.html byte-identical.
- Closed enum exactly matches DS §(d) set.
- No mechanism emitted outside the closed set (runtime exhaustive test).
- Deviation check: none.

**Artifact:** `agent_outputs/code-refactor-engineer-s13.6-t6-summary.md`.

---

### S13.6-T7 — RULE A application: absence-of-data as typed signal (DS R3 — most architecturally novel)

**Per founder RULE A:** *"Agent NEVER assumes a number ... Schema must be complete enough that absence-of-data is itself a typed signal."*

**Per DS R3:** Replace v1's "walk every Optional" with the explicit per-field classification table below. T7 dispatch brief MUST carry this Optional-by-Optional triage table verbatim.

**Pattern A confirmed by DS §(b):** Every `Optional[X]` field gets a paired `<field>_null_reason: Optional[<Enum>] = None`. When `<field>` is `None`, the paired reason MUST be populated.

**DS §(e) RULE A triage table (MUST appear verbatim in T7 dispatch brief):**

| Field | Needs null_reason? | Reason enum |
|---|---|---|
| `PlayCard.predicted_segment` | YES | `PredictedSegmentNullReason` = `MODAL_FLOOR_NOT_CLEARED \| SUBSTRATE_REFUSED \| AUDIENCE_TOO_SMALL` |
| `PlayCard.model_card_ref.strategy_used` | YES | `StrategyUsedNullReason` = `CHAIN_ABSTAINED \| NO_SUBSTRATE_VALIDATED` |
| `PlayCard.revenue_range` (when suppressed) | YES | `RevenueRangeSuppressionReason` = `PRIOR_UNVALIDATED \| COLD_START_NO_N_OBSERVED \| AUDIENCE_TOO_SMALL` |
| `PlayCard.audience.customer_ids` (S13.7) | YES | `CustomerIdsNullReason` = `SUBSTRATE_REFUSED \| AUDIENCE_RESOLVER_NOT_INVOKED` |
| `EngineRun.month_2_delta` | YES | `MonthDeltaNullReason` = `UNDER_21D_FLOOR \| LINEAGE_CHANGED \| NO_PRIOR_RUN` |
| `EngineRun.predictive_models[*]` (when absent for a key) | YES | `ModelCardAbsenceReason` = `SUBSTRATE_NOT_RUN \| SUBSTRATE_REFUSED \| INSUFFICIENT_DATA` |
| `EngineRun.cohort_diagnostics[*]` | YES | `CohortDiagnosticsAbsenceReason` = `INSUFFICIENT_COHORT_DEPTH \| SUBSTRATE_REFUSED` |
| `EngineRun.abstain` (when absent) | NO — unambiguous | None means "engine did not abstain"; structurally clear |
| `RejectedPlay.held_reason_detail` keys | per-key check | Most can stay bare-Optional; `observed_effect=None` is itself a typed signal |
| `EngineRun.store_profile` | YES (low priority) | `StoreProfileNullReason` = `PROFILE_NOT_LOADED \| ONBOARDING_INCOMPLETE` |
| `EngineRun.prior_run_id` / backref fields | NO — unambiguous | Absence = no prior run; not a suppression decision |
| `Sensitivity` / `Provenance` fields when debug-stripped | NO | Strip is flag-level, not null_reason concern |

**Files affected:**
- `src/engine_run.py` — paired `_null_reason` per applicable Optional field.
- All producers — populate `_null_reason` enum at every `None`-assignment site.
- New enums per field (see triage table).

**Tests:**
- **NEW** `tests/test_s13_6_t7_no_silent_nulls.py` — runtime: every emitted PlayCard / ModelCard / EngineRun with `None` on a triage-flagged Optional has paired `_null_reason` populated.
- **AST sweep enforcement (per DS R3):** AST-aware test asserts any new `Optional[X]` added to `src/engine_run.py` either (a) has paired `_null_reason`, or (b) is annotated `# null_reason_exempt: <justification>`.
- Pinned fixtures re-pinned.

**Acceptance criteria:**
- No silent `None` on triage-flagged contract surface — every flagged absence has typed reason.
- AST sweep + runtime test pin the invariant.
- briefing.html byte-identical.
- Deviation check: none.

**Risk:** Most architecturally novel ticket of S13.6. Per CLAUDE.md Subagent Handoff Discipline: instrument before fix on unclear absence-source; two failed predictions = stop, instrument, escalate.

**Artifact:** `agent_outputs/code-refactor-engineer-s13.6-t7-summary.md`.

---

### S13.6-T7.5 — RULE A null-reason enum registry (NEW per DS R7)

**Per DS §(c) R7:** *"T7 introduces ~6-10 new enums ... These deserve a single source-of-truth comment block in `engine_run.py` and a coverage test that the union of declared enums covers every Optional contract field. Small ticket; large agent ergonomic win."*

**Work:**
- Add a single source-of-truth comment block at the top of `src/engine_run.py` enumerating all RULE-A null-reason enums introduced at T7:
  - `PredictedSegmentNullReason` (also covers `SegmentNameNullReason` synonym if introduced)
  - `RevenueRangeSuppressionReason`
  - `StrategyUsedNullReason`
  - `MonthDeltaNullReason`
  - `CustomerIdsNullReason`
  - `ModelCardAbsenceReason`
  - `CohortDiagnosticsAbsenceReason`
  - `StoreProfileNullReason`
- Each enum lists its field-of-application and members. Agents read ONE block.

**Files affected:**
- `src/engine_run.py` — registry comment block + enum re-grouping.

**Tests:**
- **NEW** `tests/test_s13_6_t7_5_null_reason_enum_registry.py` — coverage test: the union of declared null-reason enums covers every Optional contract field that the §(e) triage table classifies as needing a reason. AST-aware: parse the registry block and the triage-flagged fields; assert 1:1 coverage.

**Acceptance criteria:**
- Registry block present in `src/engine_run.py`.
- Coverage test passes.
- Deviation check: none.

**Artifact:** `agent_outputs/code-refactor-engineer-s13.6-t7.5-summary.md`.

---

### S13.6-T8 — Sprint-close docs

**Work:**
- `memory.md` template entries (≤15 lines each per CLAUDE.md template-shape rule) for T1a, T1b, T2, T3, T4, T5, T6, T7, T7.5.
- `KNOWN_ISSUES.md` — consolidate `NEW-KI-AGENT-1..7`; extend KI-NEW-P with S13.6 contract-shape calibration cells.
- `STATE.md` §4 — contract surface frozen at v2.0.0; prose stripped; `Any` slots typed; mechanism atomic (closed enum); `NonLiftAtom` wrapper; RULE A pattern + null-reason registry.
- `docs/engine_flags.md` — `INCLUDE_DEBUG_FIELDS` (default OFF).
- `docs/DECISIONS.md` — new locked decisions:
  - `D-S13.6-1` Prose-strip policy (Option a for all fields; split T1a + T1b).
  - `D-S13.6-2` `Any`-slot typing policy + re-export source-of-truth at `src/engine_run.py`.
  - `D-S13.6-3` `klaviyo_brief_inputs` removal.
  - `D-S13.6-4` `MechanismIntent` atom + DS-locked closed `MechanismType` enum.
  - `D-S13.6-5` RULE A Pattern A (paired `_null_reason`); §(e) triage table is the canonical scope.
  - `D-S13.6-6` `NonLiftAtom` wrapper on `OpportunityContext` (DS R1; type-level guardrail).
  - `D-S13.6-7` Schema freeze at 2.0.0 (additive 2.x.x; breaking → 3.0.0).
  - `D-S13.6-8` Null-reason enum registry block (T7.5).
- `ROADMAP.md` — S13.6 → SHIPPED; S13.7 queued.
- `PIVOTS.md` — Pivot 2 clarifier appended (per DS §(f) #5): contract-as-typed-atoms-only, no prose; "S13.6 ratified the strip."

**Artifact:** `agent_outputs/code-refactor-engineer-s13.6-t8-summary.md`.

---

## 6. Phase 3 — S13.7 tickets (Agent handoff completion)

**5 tickets** (4 work + 1 close). Per DS end-to-end-flow verdict: post-S13.7 the engine is handoff-ready.

| Ticket | Theme | Risk |
|---|---|---|
| S13.7-T1 | Audience customer_id resolver (RULE B + DS R4 RFM-REFUSED branch) | **HIGHEST single ticket of the 3-sprint window** |
| S13.7-T2 | JSON-Schema export + per-run filesystem manifest | Medium |
| S13.7-T3 | `MechanismType` parameters spec at `docs/mechanism_contract.md` | Low (doc) |
| S13.7-T4 | Sprint-close docs | Low |

(Per §6 milestone risk-column update: T3 NonLiftAtom = HIGHEST contract-shape risk in S13.6; T7 RULE A = most architecturally novel; S13.7-T1 = HIGHEST single ticket overall.)

### S13.7-T1 — Audience customer_id resolver (RULE B critical, P0) + RFM-REFUSED branch (DS R4)

**Per founder RULE B:** *"Wrong customer in a segment = merchant reputation killer."*

**Per DS verdict §Critical gap #1:** Materialize `data/<store_id>/runs/<run_id>/audiences/<aud_def_id>.csv`.

**Per DS R4 (REQUIRED branch):** When the substrate that ranks a PlayCard's audience is REFUSED:
1. Resolver emits an **empty CSV with the standard header row** (auditable absence, not silent absence).
2. Manifest records `audience_materialization_status: SUPPRESSED_SUBSTRATE_REFUSED` for that PlayCard's audience entry.
3. PlayCard's `audience.customer_ids_null_reason = SUBSTRATE_REFUSED` per RULE A.

The merchant-reputation killer is wrong customers, not zero customers. Empty audit-traceable CSV is correct behavior; silent absence is not.

**Work (normal path):**
- For each `PlayCard` in `EngineRun.recommendations` + `recommended_experiments`, materialize:
  ```
  data/<store_id>/runs/<run_id>/audiences/<audience_definition_id>.csv
  ```
  Columns: `customer_id`, `aov_individual`, `predicted_segment`, `rank_score`, `audience_definition_version`.
- Keys off `audience_definition_id` for D-1 lineage stability.
- Source data: substrate parquets + audience-builder definitions.
- **RULE B traceability lock:** every `customer_id` derivable through (i) substrate `ModelCard` parquet, (ii) audience-builder definition, (iii) `audience_definition_version` pinned at run.

**Legacy retirement (DS-locked):** `src/segments.py::segments/*.csv` writer **RETIRED**. Per DS §(b) Q4 and R4: AST-grep all importers of `src.segments` FIRST; remove call sites or fail loudly. Replace `src.segments` writer with `raise NotImplementedError("Retired at S13.7-T1; use audience_resolver")` — no silent deprecation.

**Files affected:**
- **NEW** `src/audience_resolver.py` — materializer module.
- `src/main.py` — wire resolver into per-run output path (AFTER `apply_guardrails_to_injected`).
- `src/segments.py` — RETIRE with raise-on-call.
- `src/audience_builders.py` — confirm `audience_definition_id` + `audience_definition_version` stably exposed.

**Tests:**
- **NEW** `tests/test_s13_7_audience_resolver_traceability.py` — RULE B (i)(ii)(iii) trace.
- **NEW** `tests/test_s13_7_audience_resolver_reproducibility.py` — same input → bit-identical CSV across two runs.
- **NEW** `tests/test_s13_7_audience_resolver_rfm_refused_branch.py` — under SUBSTRATE_REFUSED: empty CSV with header, manifest annotation, PlayCard `customer_ids_null_reason=SUBSTRATE_REFUSED`.
- **NEW** `tests/test_s13_7_segments_writer_retired.py` — legacy raises `NotImplementedError` on call.
- Pinned-fixture audience CSVs registered in the fixture ledger.

**Acceptance criteria:**
- Audience CSVs materialize at the documented path.
- RFM-REFUSED branch emits empty-header CSV + manifest + null_reason.
- RULE B traceability + reproducibility tests pass.
- Legacy writer retired with raise-on-call.
- briefing.html byte-identical.
- Deviation check: none.

**Risk:** HIGHEST single ticket of the 3-sprint window. Per CLAUDE.md: instrument before fix; two failed predictions = stop, escalate.

**Artifact:** `agent_outputs/code-refactor-engineer-s13.7-t1-summary.md`.

---

### S13.7-T2 — JSON-Schema export + per-run filesystem manifest

**Per DS verdict §Critical gap #2** + DS §(b) Q6: hand-written generator.

**Work:**
- Generate `schemas/engine_run.v2.json` from `src/engine_run.py` dataclasses via hand-written generator (DS-locked at §(b) Q6).
- Emit `data/<store_id>/runs/<run_id>/manifest.json` enumerating per run:
  - `engine_run.json` path.
  - `audiences/*.csv` paths + `audience_materialization_status` per PlayCard (per DS R4).
  - `predictive/*.parquet` paths.
  - `cohort_diagnostics/retention.json` path.
  - Parquet schema version.
  - Run metadata: `run_id`, `store_id`, `anchor_date`, `schema_version`.
- Ship `tools/validate_engine_run.py` — round-trip validates against `schemas/engine_run.v2.json`.

**Files affected:**
- **NEW** `schemas/engine_run.v2.json`.
- **NEW** `tools/generate_schema.py` (hand-written).
- **NEW** `tools/validate_engine_run.py`.
- **NEW** `src/manifest.py`.
- `src/main.py` — wire manifest at run-close.
- `tools/export_store.py` — align with new manifest shape.

**Tests:**
- **NEW** `tests/test_s13_7_schema_export_roundtrip.py`.
- **NEW** `tests/test_s13_7_manifest_enumerates_all_artifacts.py` — includes `audience_materialization_status` field check per PlayCard.

**Acceptance criteria:**
- Schema round-trip on all pinned fixtures.
- Manifest enumerates all artifacts + per-PlayCard materialization status.
- Validator ships and works.
- Deviation check: none.

**Artifact:** `agent_outputs/code-refactor-engineer-s13.7-t2-summary.md`.

---

### S13.7-T3 — `MechanismType` parameters spec lock at `docs/mechanism_contract.md`

**Per DS §(c) R2 + §(d) per-type parameters lock:** S13.7-T3 ships the LOCKED spec doc inline with the per-type `parameters` shape from DS §(d).

**Work:**
- New file `docs/mechanism_contract.md`:
  - Closed `MechanismType` enum (verbatim from DS §(d), per T6).
  - Per-type `parameters` dict shape (verbatim from DS §(d)):
    - `WINBACK_REACTIVATION_EMAIL`: `{ dormancy_window_days: int, offer_type: Literal["percent_off","dollar_off","none"], measurement_window_days: int }`
    - `FIRST_TO_SECOND_NUDGE`: `{ days_since_first_order_window: [int,int], measurement_window_days: int }`
    - `THRESHOLD_BUNDLE_OFFER`: `{ threshold_aov: float, current_median_aov: float }`
    - `DISCOUNT_DEPENDENCY_HYGIENE`: `{ current_discount_share: float, target_discount_share: float }`
    - `REPLENISHMENT_REMINDER`: `{ replenishment_window_days: int, sku_class: str }`
    - Tier-B types: `parameters` empty dict acceptable for v2.0.0; flesh out at S14+ when builders are promoted out of Tier-B.
  - Narration-agent contract: per `MechanismType`, what business-context inputs (brand voice, discount policy) feed copy rendering.
  - Send-time logic ownership: **NARRATION AGENT**.

**Files affected:**
- **NEW** `docs/mechanism_contract.md`.
- `docs/DECISIONS.md` — `D-S13.7-1 mechanism contract locked at docs/mechanism_contract.md`.

**Tests:**
- **NEW** `tests/test_s13_7_mechanism_contract_coverage.py` — every `MechanismType` value has a corresponding section.

**Acceptance criteria:**
- `docs/mechanism_contract.md` ships with one section per `MechanismType`.
- Per-type parameters shape matches DS §(d) verbatim.
- Decision recorded.
- Deviation check: none.

**Artifact:** `agent_outputs/code-refactor-engineer-s13.7-t3-summary.md`.

---

### S13.7-T4 — Sprint-close docs

**Work:**
- `PRODUCT.md` — per DS rec #5: "Engine produces immutable runs; approval state is agent-DB concern" seam (one paragraph).
- `ROADMAP.md` — S13.7 → SHIPPED; S14 queued.
- `STATE.md` — sprint-close; document new artifacts (`audiences/*.csv`, `manifest.json`, `schemas/engine_run.v2.json`).
- `memory.md` — template entries for S13.7-T1..T3.
- `KNOWN_ISSUES.md` — close KIs resolved; file any new ones.
- `docs/DECISIONS.md` — `D-S13.7-2 audience resolver retirement of src/segments.py (hard cut + raise NotImplementedError)`, `D-S13.7-3 filesystem-only handoff`, `D-S13.7-4 RFM-REFUSED empty-CSV-with-header policy`.

**Artifact:** `agent_outputs/code-refactor-engineer-s13.7-t4-summary.md`.

---

## 7. Later / ML-readiness tickets (post-S13.7, S14+ scope)

Not in this 3-sprint window:
- S14 real-merchant private beta (gated on agent/frontend build).
- KI-NEW-P closure (calibration on real merchants).
- KI-NEW-W (stale-parquet across REFUSED runs).
- KI-NEW-Y (intent-mapping YAML promotion).
- Phase 9 outcome ingestion loop (post-beta).
- Causal uplift modeling.
- Klaviyo / Shopify API integration (post-AWS).

---

## 8. Files / functions affected (consolidated)

### S13.5
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py:1380-1597` — collapse 5 blocks → 1 dispatch.
- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py:717` — `_PRIOR_ANCHORED` registry (read-only).
- `/Users/atul.jena/Projects/Personal/beaconai/src/guardrails.py` — unchanged.

### S13.6
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` — every ticket touches this 1,285-line contract surface.
- `/Users/atul.jena/Projects/Personal/beaconai/src/profile/types.py` — re-export source for `StoreProfile`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/model_card.py` — re-export source for `ModelCard`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/retention.py` — re-export source for `RetentionCard`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/consumer_wiring.py` — emit typed `FitWarning`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/month_2_delta.py` — RULE A null-reason for `month_2_delta=None`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py` — `MechanismIntent` emission.
- `/Users/atul.jena/Projects/Personal/beaconai/src/audience_builders.py` — `MechanismIntent` emission.
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py:1972-2038` — T2 consumer-wiring callsite (RULE A).
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py:2040+` — T3 month_2_delta callsite (RULE A).
- `/Users/atul.jena/Projects/Personal/beaconai/src/briefing.py` — T1a/T1b renderer non-consumption verification target.
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py` — `INCLUDE_DEBUG_FIELDS` flag default.

### S13.7
- **NEW** `/Users/atul.jena/Projects/Personal/beaconai/src/audience_resolver.py`.
- **NEW** `/Users/atul.jena/Projects/Personal/beaconai/src/manifest.py`.
- **NEW** `/Users/atul.jena/Projects/Personal/beaconai/schemas/engine_run.v2.json`.
- **NEW** `/Users/atul.jena/Projects/Personal/beaconai/tools/generate_schema.py`.
- **NEW** `/Users/atul.jena/Projects/Personal/beaconai/tools/validate_engine_run.py`.
- **NEW** `/Users/atul.jena/Projects/Personal/beaconai/docs/mechanism_contract.md`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/segments.py` — RETIRED with raise-on-call.
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py` — wire resolver + manifest (post-guardrails).
- `/Users/atul.jena/Projects/Personal/beaconai/tools/export_store.py` — align with manifest.
- `/Users/atul.jena/Projects/Personal/beaconai/docs/DECISIONS.md`.
- `/Users/atul.jena/Projects/Personal/beaconai/PRODUCT.md` — approval-state seam paragraph.

---

## 9. New artifacts produced

### S13.5
- Updated `src/main.py` block (no new files).
- 1 new test file.

### S13.6
- 9 new test files (T1a, T1b, T2, T3, T4, T5, T6, T7, T7.5).
- CHANGELOG block at top of `src/engine_run.py`.
- Null-reason enum registry block at top of `src/engine_run.py`.
- 8 new `D-S13.6-*` entries in `docs/DECISIONS.md`.
- 9 sprint summary files (one per work ticket) + 1 close summary in `agent_outputs/`.

### S13.7
- `schemas/engine_run.v2.json`.
- `tools/validate_engine_run.py`, `tools/generate_schema.py`.
- `docs/mechanism_contract.md`.
- Per-run filesystem artifacts (runtime, not checked in):
  - `data/<store_id>/runs/<run_id>/manifest.json` (with `audience_materialization_status` per PlayCard).
  - `data/<store_id>/runs/<run_id>/audiences/<aud_def_id>.csv` (empty-header-only under SUBSTRATE_REFUSED).
- 4 new `D-S13.7-*` entries in `docs/DECISIONS.md`.
- 4 sprint summary files + 1 close in `agent_outputs/`.

---

## 10. Feature flag strategy

**Net reduction in flag count expected** across this 3-sprint window.

**New flags (S13.6):**
- `INCLUDE_DEBUG_FIELDS` (default OFF) — gates `notes: List[str]` and operator-only-audit fields from contract JSON. Per DS §(f) Q3: internal-dev runs flip ON; merchant-handoff runs leave OFF.

**No new flags at S13.5 or S13.7.**

**Sunset candidates (S14 timeframe, NOT this window):**
- `ENGINE_V2_DECIDE`, `ENGINE_V2_OUTPUT`, `ENGINE_V2_SLATE` — all default-ON; sunset post-S13.6 freeze; defer to S14.

**Flag discipline:** Atomic flip pattern (S10–S13 precedent) preserved. `docs/engine_flags.md` updated at S13.6-T8.

---

## 11. Acceptance criteria (consolidated, per-sprint)

### S13.5 acceptance
- Beauty + supplements pinned-fixture SHAs byte-identical.
- M0 goldens byte-identical.
- Single-demote-channel invariant pinned by new AST-aware test.
- All 4 DS-locked invariants preserved.
- Deviation check: none.

### S13.6 acceptance
- All engine-authored prose fields absent (T1a + T1b atomic flips, verified per-field renderer non-consumption).
- All 4 `Any` slots typed; `klaviyo_brief_inputs` removed; re-exports resolve through `src/engine_run.py`.
- `OpportunityContext` carries `NonLiftAtom` wrapper (DS R1); dup fields stripped.
- `FitWarning` typed dataclass replaces `List[str]` grammar.
- `schema_version="2.0.0"` + CHANGELOG block.
- `MechanismIntent` atomic typing; `MechanismType` closed enum exactly matches DS §(d) lock; emission audit verifies no extras.
- RULE A absence-of-data pattern (Pattern A, DS-confirmed) applied per §(e) triage table; AST sweep + runtime test green.
- Null-reason enum registry block present (T7.5); coverage test passes.
- ~~briefing.html byte-identical on Beauty + supplements.~~ — REVISED 2026-05-30 per DS Option D + founder approval: `engine_run.json` schema-validated and SHA-pinned; **`briefing.html` unpinned post-T1a per DS Option D + founder approval 2026-05-30** (canary shifts to engine_run.json SHA + S13.7-T2 JSON-Schema round-trip).
- `engine_run.json` SHAs re-pinned in fixture ledger.
- All 9 new test files pass.

### S13.7 acceptance
- Audience CSV materializes per PlayCard with RULE B traceability + reproducibility tests passing.
- RFM-REFUSED branch: empty-header CSV + manifest annotation + PlayCard `customer_ids_null_reason=SUBSTRATE_REFUSED`.
- Legacy `src/segments.py` writer retired (raise `NotImplementedError`).
- `schemas/engine_run.v2.json` published; round-trip on all pinned fixtures.
- Per-run `manifest.json` emits + enumerates all artifacts + per-PlayCard `audience_materialization_status`.
- `docs/mechanism_contract.md` ships with one section per `MechanismType`; per-type parameters match DS §(d).
- Founder can run synthetic-validation and get all expected artifacts.

---

## 12. Test strategy

Mirrors S10–S13 substrate + atomic-flip + rollback patterns.

### Byte-identity gates
- **briefing.html SHA** byte-identical across the ENTIRE 3-sprint window.
- **engine_run.json SHA** unchanged at S13.5; WILL change at S13.6 (re-pin via ledger).
- **engine_run.json SHA** at S13.7: re-pin if manifest path emitted into JSON (likely sibling file).

### New test files (count by sprint)
- S13.5: **1** (`test_s13_5_single_emission_point.py`).
- S13.6: **9** (T1a + T1b + T2 + T3 + T4 + T5 + T6 + T7 + T7.5).
- S13.7: **7** (T1 traceability + T1 reproducibility + T1 RFM-REFUSED branch + T1 segments retired + T2 schema roundtrip + T2 manifest enumerate + T3 contract coverage).

**Total new tests across window: 17.**

### Invariant pins (must remain pinned across the entire window)
- Single-demote-channel (Pivot 7).
- 3-channel `priority_prepend`.
- Observed-effect surfacing (`src/measurement_builder.py:2252-2270`).
- Role-uniqueness in slate (Phase 6A B4).
- Q-S13-4 LOCK (ML-fit emits ONLY on `fit_warnings`, NEVER on `RejectedPlay.reason_code`).
- pseudo_N table locked at {30, 15, 10}.

### RULE A test pattern (S13.6-T7 + T7.5)
- AST-aware sweep over `src/engine_run.py` per §(e) triage table.
- Runtime test — every emitted `None` on triage-flagged Optional has paired `_null_reason`.
- T7.5 coverage test — union of registry enums covers every triage-flagged field.

### RULE B test pattern (S13.7-T1)
- Traceability + reproducibility on Beauty + supplements.
- RFM-REFUSED branch test on a synthetic fixture where ranking substrate REFUSED.
- Retirement test: legacy raises on call.

### Per-ticket loop discipline
- Per-ticket: refactor → DS review → orchestrator commits + pushes → next ticket.
- Every dispatch brief REQUIRES `agent_outputs/code-refactor-engineer-<ticket>-summary.md` (per `memory/MEMORY.md::feedback_refactor_dispatch_includes_summary_file.md`). **Reaffirmed.**
- Commit body carries `Deviation check: none` or `Deviation check: [describe + prior approval]`. **Reaffirmed.**

---

## 13. Risks and rollback strategy

### Risk surface by sprint

**S13.5 (LOW):**
- Single risk: collapse silently bypasses `apply_guardrails_to_injected`. Mitigation: new AST-aware test pins single emission point.
- Rollback: single ticket, single commit, single revert.

**S13.6 (HIGHEST sprint risk):**
- **T3 (NonLiftAtom wrapper) = HIGHEST contract-shape risk** per DS. Risk mitigated VIA the wrapper itself (not via a sibling flag); the type system names the constraint. JSON shape of `opportunity_context` changes — re-pin SHAs + reconfirm renderer mapping. Forbidden-token sweep updated.
- **T7 (RULE A pattern) = most architecturally novel.** Risk mitigated VIA the §(e) triage table embedded in the dispatch brief — refactor-engineer does not "walk every Optional" blind. AST sweep + runtime test pin invariant.
- **T6 (closed enum audit).** Miss any emission site → enum violation at runtime. Mitigation: AST audit + exhaustive runtime test; any extra mechanism string escalates to DS.
- **T1a/T1b (prose strip).** REVISED 2026-05-30 per DS Option D + founder approval: T1a halt + DS adjudication retracted the renderer non-consumption premise of R5 (consumption is in `storytelling_v2.py`, not `briefing.py`). Bundled renderer-side cleanup (`storytelling_v2.py`, `briefing.py`, `debug_renderer.py`) + `decide.py` `_apply_copy_ladder` deletion ship in the same atomic commit as the dataclass strip. **`briefing.html` byte-identity pin retired at T1a**; canary shifts to `engine_run.json` SHA + S13.7-T2 JSON-Schema round-trip. T1b (`Observation.text`) remains a separate ticket per DS Q7 #6 (smaller blast radius).
- Rollback: per-ticket atomic flips; each independently revertable.

**S13.7 (HIGHEST single ticket risk: T1):**
- **T1 carries RULE B reputation-killer risk.** Mitigation: traceability + reproducibility + RFM-REFUSED branch tests on Beauty + supplements before any merchant-facing run.
- **T1 also retires `src/segments.py`.** Mitigation: AST grep for all importers FIRST (per DS R4 + §(b) Q4); raise `NotImplementedError` on call.
- **T2 (schema export).** Drift between hand-written generator and dataclasses. Mitigation: round-trip on every pinned fixture.
- Rollback: T1 audience resolver is additive; retirement is the non-additive change → `git revert` of that commit.

### Rollback strategy (general)

- **Per-ticket atomic commits.** Each ticket = one commit = independently revertable.
- **briefing.html byte-identity** WAS the canary across the entire window — RESOLVED 2026-05-30 per S13.6-T1a Option D adjudication: canary shifts to `engine_run.json` SHA + S13.7-T2 JSON-Schema round-trip; `briefing.html` SHA pins dropped from the ledger at T1a.
- **Fixture ledger** retains pre-S13.6 SHAs; re-pin happens AT commit, not earlier.

---

## 14. What not to touch yet

Out of scope:
- **No Shopify / Klaviyo API integration** (D-5; founder lock).
- **No frontend app build inside engine scope** (Pivot 2).
- **No narration agent build** (founder decision #4).
- **No outcome calibration loop** (Phase 9).
- **No causal uplift modeling**.
- **No cross-merchant pooling** (D-2).
- **No KI-NEW-M / KI-NEW-N** — both anchored to S14-T3.
- **No KI-NEW-P closure**.
- **No KI-NEW-W** (stale-parquet across REFUSED runs).
- **No KI-NEW-Y** (intent-mapping YAML).
- **No new ML substrates** (six locked).
- **No Play Library wave 2+ migration**.
- **No legacy V2 cleanup workstream**.
- **No `ENGINE_V2_*` flag sunset** (defer to S14).
- **No PRODUCT.md / PIVOTS.md edits beyond the documented surgical ones** (PRODUCT approval-state paragraph at S13.7-T4; PIVOTS Pivot 2 clarifier at S13.6-T8 per DS §(f) #5).

---

## 15. Adjudicated IM open questions (v1 §15) — DS §(b) verdicts

All 6 v1 questions are now **resolved** by DS §(b):

1. **(T7 — RULE A pattern choice)** — **RESOLVED. Pattern A (paired `_null_reason`) confirmed by DS.** Rationale: additive; preserves current JSON shape; AST-aware test sufficient. Pattern B migration cost not justified pre-beta.
2. **(T6 — mechanism enum scope)** — **RESOLVED. Closed set, audited at T6, confirmed by DS** (§(d) enum lock). Rationale: RULE A demands typed atoms; open set defers the audit.
3. **(T3 — mechanism contract doc location)** — **RESOLVED. Standalone `docs/mechanism_contract.md`, confirmed by DS.** Rationale: narration agent codes against this file; `docs/DECISIONS.md` is for the decision, not the spec.
4. **(S13.7-T1 — `src/segments.py` retirement)** — **RESOLVED. Hard cut at S13.7-T1, confirmed by DS** with AST-grep prerequisite + `raise NotImplementedError("Retired at S13.7-T1; use audience_resolver")` (no silent deprecation).
5. **(S13.6 vs S13.7 ordering of MechanismType)** — **RESOLVED. Keep split, confirmed by DS.** Enum lives in `engine_run.py` (typed surface) at T6; spec doc at T3 of S13.7.
6. **(Schema generator tooling)** — **RESOLVED. Hand-written generator at `tools/generate_schema.py`, confirmed by DS.** Preserves dataclass-native posture; round-trip test on pinned fixtures is the canonical correctness check.

---

## 16. Founder-level open questions (NEW — per DS §(f))

Surfaced for explicit founder call before S13.6 dispatch:

1. **NonLiftAtom wrapper (DS R1).** Contract-shape decision with downstream agent implications. Wrapper changes JSON shape of `opportunity_context` more than a flag does. **DS recommends wrapper.** Founder: approve wrapper, OR accept weaker `_do_not_narrate_as_lift` flag and own agent-misnarration risk on first run?

2. **Empty audience CSV vs no CSV under SUBSTRATE_REFUSED (DS R4).** Operator-facing UX call. **DS recommends empty CSV with header row + manifest annotation** (auditable absence > silent absence). Founder confirm operator UX.

3. **`INCLUDE_DEBUG_FIELDS` default.** Plan defaults OFF. Confirm: internal-dev runs flip ON; merchant-handoff runs leave OFF. Documented in `docs/engine_flags.md` at T8.

4. **`audience_definition_version` source.** S13.7-T1 RULE B trace anchor. **DS recommends code-version (`git sha` of `src/audience_builders.py` at run time).** Founder confirm vs run-time config-snapshot. Has merchant-reproducibility implications if builder code evolves.

5. **`recommendation_text` strip = Pivot 2 reaffirmation.** **RESOLVED 2026-05-30** per S13.6-T1a Option D + founder approval: Pivot 2 addendum lands at PIVOTS.md AT S13.6-T1a (not deferred to T8). Founder-approved text reads: *"S13.6-T1a ratified the strip — engine emits zero merchant-facing prose on contract surface; briefing.html byte-identity pin retired; canary shifts to engine_run.json SHA + S13.7-T2 JSON-Schema round-trip."*

---

## 17. Handoff at S13.7 close

After S13.7 ships, the engine is **handoff-ready**:

**What the founder/team can build against (post-S13.7):**

```bash
python -m src.main --csv data/synthetic_beauty/orders.csv --brand synthetic_beauty --out runs/
```

produces in `data/synthetic_beauty/runs/<run_id>/`:
- `engine_run.json` — typed v2.0.0; no prose; no `Any`; every triage-flagged Optional carries `_null_reason`; `MechanismIntent` atoms (closed enum); `OpportunityContext` with `NonLiftAtom` wrapper; typed `FitWarning` grammar.
- `manifest.json` — enumerates all artifacts + per-PlayCard `audience_materialization_status`.
- `audiences/<aud_def_id>.csv` — per emitted PlayCard, RULE B traceable + reproducible; empty-header-only under SUBSTRATE_REFUSED.
- `predictive/*.parquet` — substrate artifacts.
- `cohort_diagnostics/retention.json` — retention curves.

And founder/team has on disk:
- `schemas/engine_run.v2.json` — published schema.
- `tools/validate_engine_run.py` — round-trip validator.
- `docs/mechanism_contract.md` — contract narration agent codes against (with per-type parameters spec from DS §(d)).

**What the narration MCP agent does:**
Reads `engine_run.json` + business context (discount policy, brand voice) → produces narration. Engine prose contributes zero. The `NonLiftAtom` type tells the agent these numbers are NOT lift. The closed `MechanismType` tells the agent exactly which template to render.

**What the assembly MCP agent does:**
Validates `engine_run.json` against `schemas/engine_run.v2.json`. Reads typed atoms only. Per RULE A: never infers an absent number; reads `_null_reason` (consulting the registry block at top of `engine_run.py`) to understand the gap.

**What the frontend does:**
Renders narrated cards. On approval, operator opens `audiences/` folder, uploads matching CSVs to Klaviyo manually (D-5). Loop closed on filesystem-only handoff (DS rec #6).

**What S14 requires:**
Real-merchant onboarding (not gated on more engine work). Engine contract is frozen at v2.0.0 per founder decision #3.

---

## Sources

- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md` (v2 driver — APPROVE-WITH-CHANGES; R1–R7 + §(d) + §(e) + §(b) + §(f)).
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ds-architect-engine-readiness-for-agents.md` (P0/P1 cleanup audit driving S13.5 + S13.6).
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ds-architect-end-to-end-flow-readiness.md` (6-stage flow gap analysis driving S13.7).
- `/Users/atul.jena/Projects/Personal/beaconai/CLAUDE.md` (Subagent Handoff Discipline; Documentation Discipline; single-demote-channel invariant).
- `/Users/atul.jena/Projects/Personal/beaconai/STATE.md` §1, §4 (pipeline, four orthogonal gates).
- `/Users/atul.jena/Projects/Personal/beaconai/PIVOTS.md` Pivot 2 L24-30, Pivot 7 L76-82, Pivot 8 L86-92.
- `/Users/atul.jena/Projects/Personal/beaconai/ROADMAP.md` §1.
- `/Users/atul.jena/Projects/Personal/beaconai/KNOWN_ISSUES.md::KI-NEW-L` L411-420.
- `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/code-refactor-engineer-s13-t4-close-summary.md`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py` (1,285-line contract surface).
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py:1380-1597` (S13.5 collapse target).
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py:1972-2038` (T2 consumer-wiring callsite).
- `/Users/atul.jena/Projects/Personal/beaconai/src/main.py:2040+` (T3 month_2_delta callsite).
- `/Users/atul.jena/Projects/Personal/beaconai/src/predictive/{model_card.py, consumer_wiring.py, ranking_strategy.py, month_2_delta.py}`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/segments.py` (S13.7-T1 retirement target).
- `/Users/atul.jena/Projects/Personal/beaconai/src/audience_builders.py`.
- `/Users/atul.jena/Projects/Personal/beaconai/src/utils.py`.
- `/Users/atul.jena/Projects/Personal/beaconai/tools/export_store.py`.
- `/Users/atul.jena/Projects/Personal/beaconai/docs/DECISIONS.md`.
- `/Users/atul.jena/Projects/Personal/beaconai/docs/engine_flags.md`.

*End of plan (v2).*
