# BeaconAI — Claude Code Instructions

## Project Context

This is the BeaconAI Action Engine — a Shopify-app DTC e-commerce decision engine that emits a monthly slate of typed Play Thesis cards for beauty / supplements / mixed merchants. For the product framing read `PRODUCT.md`. For the engine's current pipeline read `STATE.md`.

Key files:
- `src/main.py` — orchestration; per-play dispatch loop
- `src/store_profile.py` — PROFILE layer
- `src/audience_builders.py` — AUDIENCE layer
- `src/measurement_builder.py` — MEASUREMENT layer
- `src/sizing.py` — SIZING layer (`PSEUDO_N_BY_STATUS`, `bayesian_blend`)
- `src/decide.py` — DECIDE layer (slate assembly, role-uniqueness)
- `src/guardrails.py` — `apply_guardrails_to_injected` (single-demote-channel helper)
- `src/engine_run.py` — typed PlayCard schema

## Doc Map

| Agent question | Doc |
|---|---|
| What is BeaconAI as a product? | `PRODUCT.md` |
| What does the engine do right now? | `STATE.md` |
| Why is X invariant locked? What changed our minds? | `PIVOTS.md` |
| What is next? | `ROADMAP.md` |
| What happened in sprint X? (chronology stream) | `memory.md` |
| What ticket shipped what? (receipt detail) | `agent_outputs/code-refactor-engineer-<ticket>-summary.md` |
| What open issues exist? | `KNOWN_ISSUES.md` |
| What is the current flag default? | `docs/engine_flags.md` |
| Which founder decisions bound the design space? | `memory.md` § Founder Decisions (L173–182); cross-refs in `docs/DECISIONS.md` |
| Which agent_outputs file should I read? | `agent_outputs/INDEX.md` |

## memory.md template-shape rule

`memory.md` entries are template-shaped only (≤15 lines, fields per the template at `memory.md` L20–36). Narrative — file change tables, test counts, risk paragraphs, key learnings — goes in the corresponding `agent_outputs/code-refactor-engineer-<ticket>-summary.md`. A pre-commit lint rejects new entries that exceed the template envelope.

## Agent Review Panel

When asked to run a review panel or `/review-panel` is invoked:
- Read `STATE.md` and `PIVOTS.md` for current engine context (the prior pointer to `ENGINE.md` is retired; that doc now lives in `docs/legacy/`).
- Use `git diff HEAD` or the files the user specifies.
- Spawn all 5 subagents in parallel.
- Each subagent should be opinionated, rigorous, direct.
- Collect all reports and present with a final synthesis.

## General Conventions

- Python 3.10+
- Config via `.env` (`VERTICAL_MODE`, `BUSINESS_STAGE`, `CONFIDENCE_MODE`, `ENGINE_DEBUG_CATEGORIES`)
- No breaking changes to output file formats without flagging explicitly

## Subagent Handoff Discipline (load-bearing, founder-locked 2026-05-22)

Every refactor / DS / IM dispatch MUST begin by understanding the current state of the engine before acting. Concretely:

Read `PRODUCT.md`, `STATE.md`, `PIVOTS.md`, `ROADMAP.md`, `KNOWN_ISSUES.md`, and the relevant sprint's `memory.md` entries before any dispatch. Use `agent_outputs/INDEX.md` to find specific verdicts / reviews / closeouts. For V2 work, follow the INDEX's "Recently closed sprints" section into the relevant DS verdicts and code-refactor summaries.

**Never assume.** If a prediction conflicts with what the code does, instrument and verify before committing a fix. The S7.6 T7.5 spiral happened because three consecutive predictions about where a card died were each wrong; only direct in-process instrumentation found the actual gate.

**Prove pipeline-death claims before fixing them.** Any hypothesis of the form "the value dies at X" / "the card is dropped at Y" / "the data doesn't reach Z" requires a print/log/breakpoint at that location showing the actual state *before* any code edit is written. No fix-on-a-guess for data-loss bugs.

**Two failed predictions = stop guessing.** If your second fix attempt on the same bug fails, the third move cannot be another fix. It must be (a) instrumentation, (b) reading code you have not yet read, or (c) escalation to founder/DS. No third-attempt-from-the-same-mental-model.

**Only follow the path that's decided.** Once an option has been chosen by the founder (e.g., "Option 1, C1+C2+C3"), do not silently expand scope, do not add band-aids "for safety," do not skip steps. If a step appears unnecessary or a different shape seems better, STOP and escalate before deviating. On founder-locked or DS-locked work, the commit body must carry a one-line `Deviation check: none` (or `Deviation check: [describe]` with prior approval).

**memory.md is template-shape only.** Narrative goes in the summary file.

**Single-demote-channel invariant (DS-locked 2026-05-22):**
No code path may append to `engine_run.recommendations` after `apply_guardrails` without routing through the `apply_guardrails_to_injected` helper (introduced in S7.6 C2). New builders use the existing post-injection guardrails re-invocation; new injection blocks at `src/main.py:1380-1597` are forbidden without explicit founder + DS sign-off documented in `PIVOTS.md`.
