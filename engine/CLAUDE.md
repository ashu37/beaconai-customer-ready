# BeaconAI — Claude Code Instructions

## Project Context

This is the BeaconAI Action Engine — a Shopify-app DTC e-commerce decision engine that emits a monthly slate of typed Play Thesis cards for beauty / supplements / mixed merchants.

**Status (post-S13.7):** Schema v2.0.0 frozen. Engine produces immutable runs. Pivot 2 (Stop-Coding Line) ratified — engine emits typed atoms only, narration agents author all merchant-facing language. End-to-end flow: synthetic CSV → engine → typed `engine_run.json` + `manifest.json` + audience CSVs → MCP agents (narration + assembly, in-build) → frontend → Klaviyo upload.

For the product framing read `PRODUCT.md`. For the engine's current pipeline read `STATE.md`.

## Key files

### Decision layers (legacy 7-layer pipeline)
- `src/main.py` — orchestration; per-play dispatch loop
- `src/store_profile.py` — PROFILE layer
- `src/audience_builders.py` — AUDIENCE layer
- `src/measurement_builder.py` — MEASUREMENT layer
- `src/sizing.py` — SIZING layer (`PSEUDO_N_BY_STATUS`, `bayesian_blend`)
- `src/decide.py` — DECIDE layer (slate assembly, role-uniqueness, `_PLAY_ID_TO_MECHANISM_TYPE`, `_build_mechanism_intent`)
- `src/guardrails.py` — `apply_guardrails_to_injected` (single-demote-channel helper, Pivot 7)

### Schema authority + agent handoff (S13.6 + S13.7)
- `src/engine_run.py` — **single-file schema authority** (D-S13.6-2). All contract types + enums + `__all__`. NULL-REASON ENUM REGISTRY comment block enumerates RULE A enums.
- `src/audience_resolver.py` — S13.7-T1: materializes `data/<store_id>/runs/<run_id>/audiences/<aud_def_id>.csv` per PlayCard. SUBSTRATE_REFUSED writes empty CSV + header row (RULE B).
- `src/run_manifest.py` — S13.7-T2: writes per-run `manifest.json` enumerating all artifacts. `artifacts.engine_run` is a path relative to manifest's own directory (`../<run_id>.json`).
- `schemas/engine_run.v2.json` — S13.7-T2: published JSON Schema (draft-07) generated from `src/engine_run.py` dataclasses + enums.
- `tools/generate_schema.py` — hand-written schema generator (no `pydantic`, no `dataclasses-jsonschema`)
- `tools/validate_engine_run.py` — round-trip validator (soft-imports `jsonschema`)
- `docs/mechanism_contract.md` — S13.7-T3: DS-locked narration-agent spec for all 10 `MechanismType` values + their `parameters` shapes

### Predictive substrate consumers (S13)
- `src/predictive/consumer_wiring.py` — S13-T2: populates `PlayCard.predicted_segment` + `PlayCard.model_card_ref`. **Q-S13-4 LOCK** lives at `src/engine_run.py:167-183`.
- `src/predictive/month_2_delta.py` — S13-T3: `EngineRun.month_2_delta` (Pivot 8 substrate-state-delta, NOT realized-outcome). 21-day floor + lineage-change constraint.
- `src/predictive/ranking_strategy.py` — S13-T1: `AudienceIntent` str-Enum (`GENERAL` / `REPLENISHMENT_TIMING` / `LOOKALIKE_EXPANSION`); intent-conditional substrate chains.

## Engine output filesystem layout (post-S13.7)

After `python -m src.main --orders <csv> --brand <store_id>`:

```
data/<store_id>/
  predictive/
    rfm.parquet                          ← RFM substrate (when fit VALIDATED)
    bgnbd.parquet, gamma_gamma.parquet, ...
    retention.json
  runs/
    <run_id>.json                        ← engine_run snapshot (FILE, immutable)
    <run_id>/                            ← run dir (DIR)
      manifest.json                      ← artifact pointer index
      audiences/
        <audience_definition_id>.csv     ← per-PlayCard customer list

receipts/
  engine_run.json                        ← mutable mirror (legacy Swarm consumer)
```

**Critical pointer-resolution rule (MCP agents):** `manifest.artifacts.engine_run` is `"../<run_id>.json"` (relative to manifest's own directory). Agents MUST resolve via `(manifest_path.parent / manifest["artifacts"]["engine_run"]).resolve()`. Do NOT hardcode paths. Do NOT read `receipts/engine_run.json` (mutable mirror; legacy).

## Doc Map

| Agent question | Doc |
|---|---|
| What is BeaconAI as a product? | `PRODUCT.md` (§8 = approval-state seam) |
| What does the engine do right now? | `STATE.md` |
| Why is X invariant locked? What changed our minds? | `PIVOTS.md` |
| What is next? | `ROADMAP.md` |
| What founder/DS decisions bound the design space? | `docs/DECISIONS.md` (authoritative D-letter ledger) |
| What happened in sprint X? (chronology stream) | `memory.md` |
| What ticket shipped what? (receipt detail) | `agent_outputs/code-refactor-engineer-<ticket>-summary.md` |
| What open issues exist? | `KNOWN_ISSUES.md` |
| What is the current flag default? | `docs/engine_flags.md` |
| What does each MechanismType mean? (narration agents) | `docs/mechanism_contract.md` |
| What constitutes a play's evidence (incl. visualization)? | `docs/evidence_layer.md` (L-EV-1..12; 9 members; viz is a first-class member) |
| What is the engine→MCP→frontend handoff architecture? | `docs/handoff_architecture.md` (§7 = the 8 DS locks) |
| Where is the JSON Schema? (agent contract consumers) | `schemas/engine_run.v2.json` |
| Which agent_outputs file should I read? | `agent_outputs/INDEX.md` |

## Load-bearing invariants

These are non-negotiable. Patches that breach them require explicit founder + DS sign-off.

| Invariant | Where locked |
|---|---|
| **Pivot 2 — Stop-Coding Line** — engine emits zero merchant-facing prose on contract surface; narration agents author language | `PIVOTS.md::Pivot 2` (T1a/T6/T8 addenda); `docs/DECISIONS.md::D-S13.6-1` |
| **Pivot 5 §G.3 — three-precondition clarifier** — `predicted_segment.segment_name` populates only when (a) RFM VALIDATED, (b) modal-segment floor cleared, (c) DECIDE produces ≥1 PlayCard | `PIVOTS.md::Pivot 5` + `KI-NEW-X` |
| **Pivot 7 — single-demote-channel** — no code path appends to `engine_run.recommendations` after `apply_guardrails` without routing through `apply_guardrails_to_injected`; no new injection blocks at `src/main.py:1380-1597` without founder + DS sign-off | DS-locked 2026-05-22; S7.6 C2 |
| **Pivot 8 — substrate-state-delta** — `month_2_delta` is substrate-state-delta, NOT realized-outcome; cold-start month-2 flows through EB n_observed shift | `PIVOTS.md::Pivot 8`; `src/predictive/month_2_delta.py` |
| **Q-S13-4 LOCK — ML-fit gate** — ML-fit ReasonCodes emit ONLY on `model_card_ref.fit_warnings`, NEVER on `RejectedPlay.reason_code`; never demotes between slate roles | `src/engine_run.py:167-183`; `tests/test_s13_ml_fit_never_demotes.py` |
| **RULE A — typed absence** — Optional fields needing typed absence reasons have paired `_null_reason` (Pattern A); flag-OFF defaults exempt via `# null_reason_exempt:` annotation; no `Dict[k, AbsenceReason]` parallel-dict | `docs/DECISIONS.md::D-S13.6-5`; NULL-REASON ENUM REGISTRY in `src/engine_run.py` |
| **RULE B — segment trustworthiness** — audience customer_ids must be audit-traceable; SUBSTRATE_REFUSED writes empty CSV + header row, never silent absence | DS R4 (S13.7-T1); `src/audience_resolver.py` |
| **Schema v2.0.0 freeze** — additive changes within 2.x.x allowed; breaking changes go to 3.0.0; new Optional fields require paired `_null_reason` or `null_reason_exempt` | `src/engine_run.py` CHANGELOG; `docs/DECISIONS.md::D-S13.6-5` |
| **MechanismType closed set** — 10 members, DS-audited; new types require DS review + version bump | `docs/DECISIONS.md::D-S13.6-4`; `docs/mechanism_contract.md` |
| **briefing.html canary retired** — `engine_run.json` SHA is the canary now; `briefing.html` is debug-only | `docs/DECISIONS.md::D-S13.6-1` (Option D at T1a) |
| **Schema authority = `src/engine_run.py`** — all contract types re-exported from this single file | `docs/DECISIONS.md::D-S13.6-2` (DS R6) |
| **Filesystem-only handoff** — no Postgres / API layer between engine and agents through synthetic validation | `docs/DECISIONS.md::D-S13.7-5` |
| **Immutable runs** — engine writes immutable snapshots; approval state lives in agent DB, not engine | `PRODUCT.md` §8 (Approval-State Seam); `docs/DECISIONS.md::D-S13.7-5` |

## memory.md template-shape rule

`memory.md` entries are template-shaped only (≤15 lines, fields per the template at `memory.md` L20–36). Narrative — file change tables, test counts, risk paragraphs, key learnings — goes in the corresponding `agent_outputs/code-refactor-engineer-<ticket>-summary.md`. A pre-commit lint rejects new entries that exceed the template envelope.

## General Conventions

- Python 3.10+
- Config via `.env`: `VERTICAL_MODE`, `BUSINESS_STAGE`, `CONFIDENCE_MODE`, `INCLUDE_DEBUG_FIELDS` (default OFF per S13.6-T1a; internal-dev/DS runs flip ON)
- For full v2 slate shape: `ENGINE_V2_DECIDE=1`, `ENGINE_V2_OUTPUT=1`, `ENGINE_V2_SLATE=1` (see `docs/engine_flags.md` for current defaults; many are now default-ON post-S12/S13)
- Engine CLI: `python -m src.main --orders <csv> --brand <store_id>` (`--csv` is deprecated)
- No breaking changes to output file formats without flagging explicitly + DS sign-off + schema version bump

## Orchestrator-Subagent Operating Model

The orchestrator (you, the top-level Claude Code session) is **non-coding**. The orchestrator dispatches specialist subagents, reviews their output, routes feedback, and commits/pushes. The orchestrator never writes or edits source code, tests, or docs directly — except for trivial one-line fixes flagged by a DS review that don't justify a roundtrip dispatch.

### Per-ticket loop (S10+ locked 2026-05-26)

```
1. orchestrator dispatches code-refactor-engineer with full brief
2. refactor-engineer ships patch + summary file
3. orchestrator routes to ecommerce-ds-architect for review
4. DS produces APPROVE / APPROVE-WITH-CHANGES / REJECT verdict
5. if APPROVE → orchestrator commits + pushes → next ticket
   if APPROVE-WITH-CHANGES → orchestrator routes required changes back to refactor-engineer
   if REJECT → orchestrator escalates to founder
```

Founder is flagged ONLY for product-level questions (merchant UX, brand voice, scope expansion, version-bump policy). Engineering and DS-coherence questions stay inside the loop.

### Required protocols

- **Refactor dispatch must include summary file path.** Every dispatch brief MUST require `agent_outputs/code-refactor-engineer-<ticket>-summary.md` per S6/S7 precedent. Regressed silently in S7.6+S8; 11 files backfilled 2026-05-25. Do not regress again.
- **DS consult on agent pause.** When refactor/IM agent escalates mid-ticket (e.g., dispatch brief contradicts producer surface, multiple options exist), orchestrator invokes DS architect with full engine context + relevant verdict lens. DS adjudicates; orchestrator passes verdict back to paused agent. Founder approval only for genuinely founder-domain decisions.
- **Don't redo prior reviews.** If mid-implementation of a prior review's plan, do not re-run the review on slash-command invocation. Confirm intent first.
- **`Deviation check: none`** required on every commit body for founder-locked or DS-locked work. Use `Deviation check: [describe]` only with prior approval.

## Subagent Handoff Discipline (load-bearing, founder-locked 2026-05-22)

Every refactor / DS / IM dispatch MUST begin by understanding the current state of the engine before acting.

**Read first.** `PRODUCT.md`, `STATE.md`, `PIVOTS.md`, `ROADMAP.md`, `KNOWN_ISSUES.md`, `docs/DECISIONS.md`, and the relevant sprint's `memory.md` entries before any dispatch. Use `agent_outputs/INDEX.md` to find specific verdicts / reviews / closeouts. For V2 work, follow the INDEX's "Recently closed sprints" section into the relevant DS verdicts and code-refactor summaries.

**Never assume.** If a prediction conflicts with what the code does, instrument and verify before committing a fix. The S7.6 T7.5 spiral happened because three consecutive predictions about where a card died were each wrong; only direct in-process instrumentation found the actual gate.

**Prove pipeline-death claims before fixing them.** Any hypothesis of the form "the value dies at X" / "the card is dropped at Y" / "the data doesn't reach Z" requires a print/log/breakpoint at that location showing the actual state *before* any code edit is written. No fix-on-a-guess for data-loss bugs.

**Two failed predictions = stop guessing.** If your second fix attempt on the same bug fails, the third move cannot be another fix. It must be (a) instrumentation, (b) reading code you have not yet read, or (c) escalation to founder/DS. No third-attempt-from-the-same-mental-model.

**Only follow the path that's decided.** Once an option has been chosen by the founder (e.g., "Option 1, C1+C2+C3"), do not silently expand scope, do not add band-aids "for safety," do not skip steps. If a step appears unnecessary or a different shape seems better, STOP and escalate before deviating.

**memory.md is template-shape only.** Narrative goes in the summary file.

## Agent inventory

Specialist agents live at `.claude/agents/<name>.md`. Current roster:

| Agent | Role |
|---|---|
| `ecommerce-ds-architect` | DS gatekeeper on frozen contract surface; produces APPROVE/APPROVE-WITH-CHANGES/REJECT verdicts; adjudicates founder-pause questions; retracts and revises prior triage when producer surface contradicts |
| `code-refactor-engineer` | Implements approved code edits; preserves invariants; adds tests; writes summary files |
| `implementation-manager` | Converts DS verdicts + product direction into phased, low-risk implementation plans |
| `statistical-code-reviewer` | Audits codebase for invalid statistics, fabricated p-values, leakage, misleading revenue claims |
| `skeptic-red-team-reviewer` | Challenges ecommerce recommendations, revenue assumptions, merchant trust, cannibalization |
| `product-strategy-pm` | Translates Shopify-app vision into product requirements; merchant-facing Play Thesis UX |
| `narration-mcp-engineer` | (in-build) MCP agent that consumes `engine_run.json` + brand context → produces merchant-facing prose per PlayCard |
| `assembly-mcp-engineer` | (in-build) MCP agent that post-approval assembles Klaviyo upload bundle from `manifest.json` audience CSVs |
| `mcp-integration-engineer` | (in-build) Wires MCP agents + frontend |

### Agent Review Panel

When asked to run a review panel or `/review-panel` is invoked:
- Read `STATE.md` and `PIVOTS.md` for current engine context (the prior pointer to `ENGINE.md` is retired; that doc now lives in `docs/legacy/`).
- Use `git diff HEAD` or the files the user specifies.
- Spawn the relevant subagents in parallel (typically `ecommerce-ds-architect`, `statistical-code-reviewer`, `skeptic-red-team-reviewer`, `product-strategy-pm`, `implementation-manager`).
- Each subagent should be opinionated, rigorous, direct.
- Collect all reports and present with a final synthesis.

## Documentation Discipline

1. **Verbatim-quote load-bearing claims.** Sprint numbers, KI IDs, D-N decision identifiers, sequence assertions, and other constraints get quoted from source verbatim with a citation. Paraphrase is allowed only for prose context.

2. **Read superseding addenda.** Any source doc with `UPDATE`, `ADDENDUM`, `AMENDMENT`, or dated header blocks at the top — those override earlier sections by their stated scope. Writers acknowledge which addendum they're reading.

3. **Cross-reference reconciliation is a mandatory gate** between draft and cutover for any doc set > 3 docs. Every citation must resolve, every cross-doc identifier must match, every superseded section must be reflected.

4. **Sprint and KI names are immutable identifiers.** Once committed to `memory.md` / `KNOWN_ISSUES.md`, they don't get renamed/renumbered in active docs. References must match exactly.

5. **D-letters are sprint-close artifacts.** DS proposes locks in verdicts; code-refactor-engineer writes D-letter entries at sprint close. Do not assign D-letter numbers mid-sprint.
