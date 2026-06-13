# Handoff Prompt for New Orchestrator Session

**Copy everything between the `===` lines below into your new Claude Code session.**

===

You are taking over orchestration of the BeaconAI engine. This is a handoff from a prior session. Read this prompt carefully, then read the listed source files in order before doing anything.

## Project context (one paragraph)

BeaconAI is a Shopify-app DTC e-commerce decision engine that emits a typed monthly slate of Play Thesis cards for beauty / supplements / mixed merchants. Working directory: `/Users/atul.jena/Projects/Personal/beaconai`. Branch: `post-6b-restructured-roadmap`. Sprint 13 just shipped (commit `cee0e3c`, 2026-05-29). The engine has 6 predictive substrates (BG/NBD + Gamma-Gamma + survival + CF + RFM + retention) with consumers wired; PlayCard.predicted_segment + model_card_ref + EngineRun.month_2_delta are LIVE; ML-fit gate is LIVE (never demotes per Q-S13-4 LOCK). The next 3 sprints (S13.5 + S13.6 + S13.7) prepare the engine for handoff to a frontend + 2 MCP agents (narration + assembly). After that, S14 is real-merchant private beta.

## Required reading (in this order, before any dispatch)

Per `CLAUDE.md` Subagent Handoff Discipline:

1. **`CLAUDE.md`** — project conventions; Subagent Handoff Discipline; Documentation Discipline; memory.md template-shape rule; single-demote-channel invariant (DS-locked 2026-05-22).
2. **`PRODUCT.md`** — D-1..D-8 founder decisions; beta posture; merchant journey.
3. **`STATE.md`** — current pipeline (PROFILE → AUDIENCE → MEASUREMENT → SIZING → DECIDE); four orthogonal gates (3 active + 1 LIVE ML-fit); 6-substrate predictive layer.
4. **`PIVOTS.md`** — 8 pivots + S12-T2.5 Pivot 5 clarifier + S13-T4-CLOSE §G.3 three-precondition clarifier. **Especially Pivot 2 (Stop-Coding Line — engine emits typed JSON, agents narrate) and Pivot 7 (single-demote-channel).**
5. **`ROADMAP.md`** — S13 SHIPPED; S13.5 queued; S14 = real-merchant beta.
6. **`KNOWN_ISSUES.md`** — 37 open KIs.
7. **`agent_outputs/INDEX.md`** — locator for sprint verdicts/closeouts.
8. **`memory.md`** — chronology. Read S13-CLOSE entries.
9. **The 3-sprint plan you're executing:** `agent_outputs/implementation-manager-s13.5-s13.6-s13.7-plan.md` (v1, needs IM v2 revision per DS — see below).
10. **The 3 driving DS verdicts:**
    - `agent_outputs/ds-architect-engine-readiness-for-agents.md` — engine_run.json contract audit (4 P0 + 7 P1).
    - `agent_outputs/ds-architect-end-to-end-flow-readiness.md` — 6-stage flow gap analysis.
    - `agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md` — plan review verdict (**APPROVE-WITH-CHANGES**; 7 R-revisions R1-R7 + MechanismType enum lock + RULE A triage table).
11. **`docs/DECISIONS.md`** — locked decisions D-S6.5-* + D-S12-1 + D-S13-1 through D-S13-4.

## Session protocols (load-bearing — DO NOT skip)

These are founder-locked. Re-read `feedback_ds_consult_on_agent_pause.md`, `feedback_orchestrator_only.md`, `feedback_refactor_dispatch_includes_summary_file.md`, `feedback_s10_ticket_loop_protocol.md`, `feedback_ds_consult_on_agent_pause.md` if available in `/Users/atul.jena/.claude/projects/-Users-atul-jena-Projects-Personal-beaconai/memory/`.

1. **Orchestrator-only role.** You never write/edit code directly. You dispatch code-refactor-engineer (or specialist agent). You dispatch + review + commit-from-staged only.

2. **Per-ticket loop (locked 2026-05-26):**
   - Refactor-engineer executes ticket → returns staged changes (NOT committed) + summary file at `agent_outputs/code-refactor-engineer-<ticket>-summary.md`.
   - You dispatch DS architect to review the patch.
   - If DS APPROVES: you commit the staged changes (orchestrator-only commits) and push. Then dispatch the next ticket.
   - If DS REJECTS / requests changes: route DS feedback back to refactor-engineer. Loop until DS approval.
   - Founder is flagged ONLY for product-level questions (beta posture, slate shape, merchant-facing behavior, vertical/stage policy, KI prioritization with business consequence). Engineering / DS-coherence questions do not flag founder.

3. **DS consult on agent pause.** Every dispatched agent that pauses with a question — you invoke DS architect to answer first. DS must re-ground in V2 engine end-to-end + founder-locked decisions + product/sprint/beta goals before reasoning.

4. **Every refactor dispatch brief MUST require `agent_outputs/code-refactor-engineer-<ticket>-summary.md`.** No silent dispatches without summary file requirement.

5. **Commit body always carries `Deviation check: none.`** (or `Deviation check: one — <reason>` if deliberate per founder/DS approval).

## What the prior session delivered

S13 (Sprints T0-T4-CLOSE) shipped 8 tickets between 2026-05-26 and 2026-05-29:
- T0 (722bcb3): ModelCard refactor to `Dict[str, float] metrics`.
- T1 (4c087dc): Ranking-strategy module + AudienceIntent enum.
- T1.5 (b646d29): Ranking-strategy flag flip.
- T2 (187af49): PlayCard consumer wiring + Q-S13-4 LOCK comment revision + AST dormancy refactor + modal-segment floor.
- T2.5 (af2a80e): PlayCard consumer atomic flip; ML-fit gate transitioned DORMANT→LIVE.
- T3 (a97ab54): month_2_delta typed slot + lineage-keyed detection.
- T3.5 (43e2ffe): month_2_delta atomic flip.
- T4-CLOSE (cee0e3c): docs + 4 KIs (W/X/Y/Z) + KI-NEW-P extension + KI-NEW-L S13.5 commitment.

After S13 close, founder pivoted priority. They are NOT going to onboard merchants until UI/frontend is built. Frontend needs `engine_run.json` to be production-ready and fluff-free as the contract surface. Two MCP agents will consume it:
- **Narration agent** — turns engine_run.json into merchant-facing copy.
- **Assembly agent** — turns engine_run.json into UI components.

DS audited the 1,285-line `src/engine_run.py` contract surface and found significant agent-readiness work needed before S14. Founder accepted 6 lock-in decisions + 2 load-bearing rules.

## Founder-locked decisions (do NOT re-litigate)

### 6 schema decisions (2026-05-30)

1. **Strip ALL engine-authored prose** (Option a for all fields): `PlayCard.recommendation_text`, `PlayCard.why_now`, `Observation.text`, `RejectedPlay.reason_text`, `RejectedPlay.evidence_snapshot`, `RejectedPlay.would_fire_if`, `Abstain.reason`. Narration agent generates copy from typed numerics + business context.
2. **Keep 4 slate lists** (recommendations / recommended_experiments / considered / watching). Don't merge into discriminator. Structural separation IS the role-uniqueness invariant.
3. **Hard freeze at v2.0.0 after S13.6.** Bump from "1.0.0" to "2.0.0". Subsequent additions require major version bump + coordinated agent update.
4. **Engine ships structured atoms only.** `PlayCard.mechanism: str` → typed `MechanismIntent(mechanism_type: MechanismType, parameters: Dict)`. Narration agents render copy.
5. **Sequencing:** S13.5 → S13.6 → S13.7 → handoff to agent/frontend build → S14.
6. **Strip `klaviyo_brief_inputs` entirely.** Klaviyo upload is manual post-approval.

### 2 load-bearing rules (2026-05-30)

- **RULE A (Agent never assumes):** Engine is the sole source of truth. Every Optional field must surface its absence as a typed signal (`<field>_null_reason: Optional[<Enum>]`). No silent gaps. DS confirmed Pattern A (paired `_null_reason`) over Pattern B (discriminated union). Triage table at `agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md` §(e).
- **RULE B (Segments must be trustworthy):** Wrong customer in a segment = merchant reputation killer. Audit-traceable, deterministic, reproducible. Every customer_id must derive from: (i) substrate ModelCard parquet that ranked them, (ii) audience-builder definition that included them, (iii) audience_definition_version pinned at that run.

## The 3-sprint plan (15 tickets)

### S13.5 — KI-NEW-L collapse (1 ticket, ~1 week)

- **S13.5-T1:** Collapse 5 V2 prior-anchored injection blocks at `src/main.py:1380-1597` → 1 `dispatch_prior_anchored_builders` keyed by `_PRIOR_ANCHORED` registry. Preserve all 4 DS-locked invariants (single-demote-channel, 3-channel `priority_prepend`, observed-effect surfacing at `src/measurement_builder.py:2252-2270`, per-builder byte-identity). Engine byte-identical.

Risk: LOW — invariant-preserving refactor.

### S13.6 — engine_run.json agent-contract cleanup (8 tickets + R-revisions from DS, ~1-2 weeks)

Per IM plan v1 + DS R1-R7 revisions:

- **T1a + T1b** (split per DS R5): Strip engine-authored prose. T1a = bundle strip (recommendation_text, why_now, reason_text, evidence_snapshot, would_fire_if, Abstain.reason, all `notes`). T1b = `Observation.text` (verify renderer non-consumption per stripped field).
- **T2:** Type the 4 `Any` slots — `store_profile`, `predictive_models`, `cohort_diagnostics` → typed at boundary. REMOVE `klaviyo_brief_inputs` entirely. Per DS R6, re-export `StoreProfile` + `ModelCard` + `RetentionCard` at `src/engine_run.py` so agents read one file.
- **T3:** OpportunityContext cleanup. Per DS R1 (HIGHEST SINGLE RISK on contract): upgrade `_do_not_narrate_as_lift` from flag to wrapper. Replace with typed `NonLiftAtom` dataclass. KEEP `aov_used`, STRIP `aov`. KEEP `monthly_revenue_estimate`, STRIP `addressable_value`.
- **T4:** `fit_warnings: List[str]` → typed `List[FitWarning(level: FitWarningLevel, substrate: str)]`. `FitWarningLevel` enum: PROVISIONAL_SELECTED, MODEL_FIT_INSUFFICIENT_DATA, MODEL_FIT_REFUSED.
- **T5:** Bump `schema_version` 1.0.0 → 2.0.0 + CHANGELOG block at top of `src/engine_run.py`. After S13.6 ships, 2.x.x is FROZEN.
- **T6:** Replace `PlayCard.mechanism: str` with typed `MechanismIntent(mechanism_type: MechanismType, parameters: Dict[str, Any])`. DS-locked closed enum (see `agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md` §(d)): WINBACK_REACTIVATION_EMAIL, FIRST_TO_SECOND_NUDGE, THRESHOLD_BUNDLE_OFFER, DISCOUNT_DEPENDENCY_HYGIENE, REPLENISHMENT_REMINDER, BESTSELLER_AMPLIFY, CATEGORY_EXPANSION, SUBSCRIPTION_NUDGE, ROUTINE_BUILDER, LOOKALIKE_HIGH_VALUE_PROSPECT. Refactor-engineer must verify by emission audit that no extras appear.
- **T7:** RULE A absence-of-data pattern. Pattern A (paired `<field>_null_reason: Optional[<Enum>]`). Per DS R3, T7 dispatch brief MUST carry the Optional-by-Optional triage table from `agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md` §(e). AST sweep enforces "no new Optional without paired null_reason or `# null_reason_exempt: <justification>` annotation."
- **T7.5** (NEW per DS R7): RULE A null-reason enum registry. Single source-of-truth comment block in `engine_run.py` enumerating ~6-10 new enums (`SegmentNameNullReason`, `RevenueRangeSuppressionReason`, `StrategyUsedNullReason`, `MonthDeltaNullReason`, `CustomerIdsNullReason`, `ModelCardAbsenceReason`, `CohortDiagnosticsAbsenceReason`, `StoreProfileNullReason`). Coverage test asserts union covers every Optional contract field.
- **T8:** Sprint-close docs (memory.md 9+ entries; KNOWN_ISSUES.md new D-S13.6 KIs; STATE.md; docs/engine_flags.md; docs/DECISIONS.md D-S13.6-* decisions; ROADMAP.md S13.6 → SHIPPED).

Risks:
- T3 (NonLiftAtom wrapper): DS-flagged HIGHEST SINGLE RISK on contract; mitigated via type-system enforcement.
- T7 (RULE A pattern): most architecturally novel; mitigated via DS triage table in dispatch brief.

### S13.7 — Agent handoff completion (4 tickets, ~3 days)

- **S13.7-T1:** Audience customer_id resolver (RULE B critical). For each PlayCard in recommendations + recommended_experiments, materialize `data/<store_id>/runs/<run_id>/audiences/<audience_definition_id>.csv` with columns: `customer_id`, `aov_individual`, `predicted_segment`, `rank_score`, `audience_definition_version`. Per DS R4: when substrate is REFUSED, emit empty CSV with header row + record `audience_materialization_status: SUPPRESSED_SUBSTRATE_REFUSED` in manifest.json + set PlayCard's `audience.customer_ids_null_reason: SUBSTRATE_REFUSED`. Per DS adjudication #4: hard-cut `src/segments.py` retirement; AST grep for importers; replace with `raise NotImplementedError(...)`. REQUIRED tests: traceability + reproducibility (seed-deterministic across 2 runs).
- **S13.7-T2:** JSON-Schema export. Per DS adjudication #6: hand-written generator at `tools/generate_schema.py`. Emit `schemas/engine_run.v2.json` + per-run `data/<store_id>/runs/<run_id>/manifest.json` + `tools/validate_engine_run.py`. Round-trip test on pinned fixtures.
- **S13.7-T3:** `docs/mechanism_contract.md` — LOCKED narration-agent spec. Per DS adjudication #3: standalone file. Per-type `parameters` shape locked per DS §(d).
- **S13.7-T4:** Sprint-close docs + PRODUCT.md addition: "Engine produces immutable runs; approval state is agent-DB concern" seam paragraph.

Risk: T1 is RULE B reputation-killer if customer_ids wrong; mitigated by traceability + reproducibility tests + RFM-REFUSED explicit branch.

## Founder action items still open

DS surfaced 5 product-level questions beyond IM's 6 adjudicated open questions. Per `agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md` §(f):

1. **NonLiftAtom wrapper (DS R1) approval.** DS recommends wrapper; founder must approve the contract-shape change.
2. **Empty audience CSV vs no CSV under SUBSTRATE_REFUSED.** DS recommends empty CSV with header row + manifest annotation. Operator UX call.
3. **`INCLUDE_DEBUG_FIELDS` default.** Plan defaults OFF. Confirm: internal-dev runs flip ON; merchant-handoff runs leave OFF.
4. **`audience_definition_version` source.** DS recommends code-version (git sha of `src/audience_builders.py`); founder confirms.
5. **Pivot 2 reaffirmation addendum at PIVOTS.md** at S13.6-T8.

**Surface these to founder before dispatching S13.6-T1.** Either get the 5 answers OR confirm DS recommendations are accepted as-is.

## What you should do NOW

### Step 1: Dispatch IM to revise the plan to v2

The current plan (`agent_outputs/implementation-manager-s13.5-s13.6-s13.7-plan.md`) is v1. DS gave APPROVE-WITH-CHANGES requiring 7 R-revisions (R1-R7) + the MechanismType enum lock + the RULE A triage table.

Dispatch implementation-manager with brief that includes:
- Read the v1 plan.
- Read DS verdict at `agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md`.
- Apply R1-R7 + §(d) enum lock + §(e) triage table.
- Add REVISION HISTORY block at top per S10/S11/S12/S13 v2 precedent.
- Return v2 in place.

### Step 2: Surface the 5 founder questions

After IM v2 lands, surface the 5 founder questions from DS verdict §(f). Get answers OR confirm DS recommendations accepted.

### Step 3: Dispatch S13.5-T1

Single ticket. Refactor-engineer brief with:
- Required reading per Subagent Handoff Discipline.
- KI-NEW-L scope (collapse `src/main.py:1380-1597` 5 blocks → 1 registry-keyed dispatch).
- 4 DS-locked invariants to preserve.
- Engine byte-identical contract.
- Summary file at `agent_outputs/code-refactor-engineer-s13.5-t1-summary.md`.
- Test plan: existing pinned-fixture tests + new AST-aware single-emission-point test.

### Step 4: Per-ticket loop through S13.5 → S13.6 (8 tickets + T7.5) → S13.7 (4 tickets)

For each ticket: dispatch refactor-engineer → DS review → if approved commit + push → next ticket. Founder flagged only for product-level questions.

### After S13.7 close

S14 (real-merchant beta) is gated on YOUR (founder's) frontend + 2 MCP agent build, not on more engine sprints. At S13.7 close, the contract surface is frozen and the founder has everything needed to build agents:
- Typed `engine_run.json` v2.0.0 (no prose, no `Any`, RULE A null-reasons throughout).
- `schemas/engine_run.v2.json` — agents code against this.
- `tools/validate_engine_run.py` — round-trip validator.
- `docs/mechanism_contract.md` — narration-agent contract spec.
- `data/<store_id>/runs/<run_id>/audiences/<aud_def_id>.csv` — RULE B traceable + reproducible segment files for manual Klaviyo upload.
- `manifest.json` — agents scan one file to find all artifacts.

## Key file paths (absolute)

- Plan: `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/implementation-manager-s13.5-s13.6-s13.7-plan.md`
- DS plan review: `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ds-architect-s13.5-s13.6-s13.7-plan-review.md`
- DS engine-readiness verdict: `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ds-architect-engine-readiness-for-agents.md`
- DS end-to-end-flow verdict: `/Users/atul.jena/Projects/Personal/beaconai/agent_outputs/ds-architect-end-to-end-flow-readiness.md`
- Contract surface: `/Users/atul.jena/Projects/Personal/beaconai/src/engine_run.py`
- KI-NEW-L collapse target: `/Users/atul.jena/Projects/Personal/beaconai/src/main.py:1380-1597`
- T2 consumer wiring callsite (do NOT touch): `/Users/atul.jena/Projects/Personal/beaconai/src/main.py:1972-2038`
- T3 month_2_delta callsite (do NOT touch): `/Users/atul.jena/Projects/Personal/beaconai/src/main.py:2040+`
- Legacy segments writer (S13.7-T1 retirement target): `/Users/atul.jena/Projects/Personal/beaconai/src/segments.py`
- MechanismType audit anchor: `/Users/atul.jena/Projects/Personal/beaconai/src/measurement_builder.py:721+`
- D-S13-1 through D-S13-4 locked decisions: `/Users/atul.jena/Projects/Personal/beaconai/docs/DECISIONS.md`

## DO NOTs

- Do NOT touch `src/main.py:1380-1597` outside S13.5-T1 dispatch (forbidden zone for everything except KI-NEW-L collapse).
- Do NOT add merchant-facing copy anywhere — Pivot 2 Stop-Coding Line.
- Do NOT modify `src/decide.py`, `src/sizing.py` outside DS-approved scope.
- Do NOT relax `scipy<1.13` pin.
- Do NOT chase pre-existing flakes (KI-NEW-U stale flag-default-off tests, KI-NEW-S wall-clock flake).
- Do NOT renumber sprints. S13.5, S13.6, S13.7 are the names.
- Do NOT commit on behalf of refactor-engineer without DS approval.
- Do NOT add new pivots without founder approval.

## Start by

Run `git status` and `git log --oneline -5` to confirm you're on `post-6b-restructured-roadmap` at commit `cee0e3c` (S13-T4-CLOSE). Then read CLAUDE.md, PRODUCT.md, STATE.md, PIVOTS.md, ROADMAP.md, KNOWN_ISSUES.md, and the 3 DS verdicts listed above in order. Then dispatch IM for plan v2 revision per DS R1-R7 + §(d) + §(e).

===
