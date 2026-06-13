# BeaconAI Documentation Audit — Recommendation
*ecommerce-ds-architect, 2026-05-24*

> **REVISION 2026-05-24 (later same day):** Sections B, C, D, G, H below are superseded in part by the founder pushback round captured in the **Revisions** section at the end of this doc. Read the Revisions section first — it overrides the original calls on (1) memory.md retention and (2) agent_outputs/ retention-by-type. The original audit is preserved below for context.
>
> **Migration trigger:** do not start the cleanup until the parallel Sprint 8 first ticket lands.

## A. Current doc landscape diagnosis

**What works:**
- `ENGINE_OVERVIEW.md` is the single best doc in the repo. It's the only place that says, in plain English, what the engine is, the pipeline, the slate, the journey, the redesign — in 204 lines. It is structurally what `STATE.md` should become.
- `KNOWN_ISSUES.md` works as a registry: ID'd, statused, sourced. The format is sound.
- `CLAUDE.md`'s "Subagent Handoff Discipline" section (lines 27-46) is short and load-bearing.
- `memory.md` entry template (lines 20-36) is well-designed — the problem isn't the template, it's that nobody trims.

**What's broken:**
- `ARCHITECTURE_PLAN.md` (2,334 lines) has **eight stacked LOAD-BEARING UPDATE blocks at lines 9-56** before the Executive Summary even begins. The supersession chain is now: 2026-05-16 baseline → 2026-05-17 Part IV → 2026-05-22 S7.6 → 2026-05-22 T5.6 → 2026-05-22 S7.6 close → 2026-05-23 S7.6 continuation → 2026-05-23 T5.6 priority_prepend → 2026-05-24 CLI fix. A new agent must mentally diff six update blocks against three "Parts" (I/II/III/IV) to know what's true. This is the central pathology.
- `memory.md` is 1,820 lines and growing per-ticket. The ≤15-line cap (memory.md L20) is violated regularly — S7.6 entries run 60+ lines each, S6-T3 closeouts run 90+ lines (see L693-820). Triage information (what shipped) is mixed with implementation receipts (file paths, commit hashes, sha256s) that belong in agent_outputs summary files.
- `ENGINE.md` (310 lines) and `ENGINE_OVERVIEW.md` (204 lines) overlap heavily. `ENGINE.md` documents the **legacy** engine (multi-window weighted-vote scoring, confidence_score/final_score, BeaconAI score, Aura — see L40-104, L181-191) which is largely superseded. `ENGINE_OVERVIEW.md` describes the **V2** engine. A new agent reading both gets two contradictory mental models.
- `README.md` is stale demo-copy for an older PM-Action-First UX framing. Doesn't mention V2, the slate, abstain modes, store_id, substrate, or any current architecture.
- `TESTING_GUIDE.md` (875 lines) documents legacy KPIs/formulas (Net Sales, AOV, repeat rate, multi-window stats — L23-100). Useful as reference but not the current engine's decision logic. It's mistitled — "manual tester KPI cheatsheet" would be more accurate.
- `memory_archive.md` (2,021 lines) duplicates content already preserved in git. Its only unique value is the M0-M9 reconciliation at the top.
- **agent_outputs/** has 143 files, zero index, mixed naming conventions: `ecommerce-ds-architect-<topic>.md` (verdicts), `implementation-manager-<sprint>-<scope>-plan.md` (plans), `code-refactor-engineer-<ticket>-summary.md` (closeouts), `<sprint>-final-review-reconciled.md` (reconciliations). The dispatch instruction in CLAUDE.md L34 says read "the most recent" — undefined.

**What's redundant:**
- Sprint closeouts now live in three places: `memory.md` entry, `agent_outputs/code-refactor-engineer-<ticket>-summary.md`, and inline in `ARCHITECTURE_PLAN.md` LOAD-BEARING UPDATE blocks. The S7.6 close is duplicated across memory.md L1645-1708, ARCHITECTURE_PLAN.md L13-26, and `agent_outputs/code-refactor-engineer-s7_6-*-summary.md`. They diverge.
- KI status drift: `KNOWN_ISSUES.md` flips KI status to `resolved`, then mentions same closeout in `memory.md`. Either source could be stale; today neither is authoritative on KI lifecycle.
- D-1..D-8 founder decisions appear in `memory.md` L173-182 AND `docs/DECISIONS.md` (per CLAUDE.md reference). One is canonical; the docs don't say which.

**What's missing entirely:**
- No doc tells you this is a **Shopify app** with a planned Klaviyo integration. The word "Shopify" appears only in import context (`STORE_DATA_REQUIREMENTS.md`). The word "Klaviyo" appears only in priors-source memos (`config/priors_sources/`) and a few D-5 references.
- No doc describes the **end-to-end merchant journey**: CSV in → engine_run.json → (today: HTML debug) → (future: frontend app rendering Play Thesis cards) → Klaviyo bundles → approval → publish → outcome import → calibration. Pieces are scattered.
- No doc says **what a Play Thesis card looks like to the merchant** or what the beta UX is. The reader has to infer from the typed PlayCard schema in `src/engine_run.py`.
- No "current state" doc. To answer "what does the engine do right now?" you must resolve the supersession chain across ARCHITECTURE_PLAN.md updates plus latest memory.md entries.

---

## B. Proposed structure

Six docs in the active read path, two archive layers, one index. Total active surface ~1,400 lines (down from ~8,254).

| File | Lines | Purpose | Cadence |
|---|---|---|---|
| **PRODUCT.md** | ≤200 | The Shopify app: merchant journey, what users see, beta posture, Klaviyo/Shopify future state, ML readiness story. The doc that survives even if the engine pivots. | Stable (monthly review at most) |
| **STATE.md** | ≤500 | What is true RIGHT NOW in the code: engine pipeline today (PROFILE→AUDIENCE→MEASUREMENT→SIZING→DECIDE), what plays produce evidence, what the slate emits, current beta-readiness, current flag defaults. Replaces ENGINE.md + ENGINE_OVERVIEW.md. | Live (updated per sprint close) |
| **PIVOTS.md** | ≤400 | The 8-12 journey-critical decisions that shaped the engine and *why*. Each pivot: what we believed before → what we learned → what changed → what that locks in. Stop-Coding Line, V2 evidence-class refactor, Tier-B reframe, Single-demote-channel invariant, Synthetic-fixture honesty rule, S7.5 priors validation, Beta success criterion reframe (month-1-wow), ML-as-audience-ranking-not-play-source. | Append-only (one entry per pivot) |
| **ROADMAP.md** | ≤300 | What's next: current sprint, beta-blocking sequence (the S6→S14 table from ENGINE_OVERVIEW §6), explicit deferrals (Phase 9 post-beta, causal uplift post-PMF). Replaces ARCHITECTURE_PLAN.md "Part II" sequencing and "what this plan does NOT do" sections. | Live (updated per sprint plan) |
| **KNOWN_ISSUES.md** | ≤500 | Stays as-is structurally; trim resolved entries older than 2 sprints into KI_ARCHIVE.md. | Live (append + trim) |
| **CLAUDE.md** | ≤80 | Slim. Subagent Handoff Discipline section (existing L27-46) + a Doc Map block telling agents which of the 5 active docs to read first. | Stable |
| **agent_outputs/INDEX.md** | ≤200 | Index of agent outputs by sprint and by document type. Sections: "Active sprint outputs" / "Recent closed sprints" / "Historical". | Live (regenerated quarterly) |
| **memory.md** | (archive) | Frozen as `memory_archive_2026-05-24.md`. New per-ticket micro-receipts move to `agent_outputs/code-refactor-engineer-<ticket>-summary.md` only. The pattern of "ticket → memory.md entry" is retired. | Archive |
| **ARCHITECTURE_PLAN.md** | (archive) | Frozen as `archive/ARCHITECTURE_PLAN_2026-05-24.md`. New design specs live in `agent_outputs/ecommerce-ds-architect-*.md` and are referenced from STATE.md or PIVOTS.md when they become load-bearing. | Archive |

**Docs to delete:** None. Founder's biggest stated fear is losing load-bearing context; archive-don't-delete.

**Docs to retire from active path (move to docs/legacy/):** `ENGINE.md` (legacy-engine reference), `TESTING_GUIDE.md` (legacy-KPI cheatsheet), `README.md` (rewrite as a 30-line product elevator + pointer to PRODUCT.md).

**Docs to keep at root unchanged:** `STORE_DATA_REQUIREMENTS.md` (merchant onboarding spec; orthogonal to engine docs; useful as-is).

---

## C. Content map (where each new doc gets its content)

### PRODUCT.md sources
- `ENGINE_OVERVIEW.md` §1 (30-second description, but reframed for the *product* not the engine)
- `ARCHITECTURE_PLAN.md` Executive Summary L75-87 "What This Plan Delivers" → reframe as product capabilities
- `memory.md` D-5 (manual JSON import, manual Klaviyo posture)
- `memory.md` D-8 (vertical scope hard-lock: beauty/supplements/mixed only)
- `memory.md` "Beta success criterion: month-1-wow → month-2-return" (ENGINE_OVERVIEW §10, lines 194-202)
- The "Storage backend note" 2026-05-10 founder note in memory.md L181-182 (AWS/S3 migration is future)
- `ENGINE_OVERVIEW.md` §6 ML Predictive Layer description (lines 100-106) → reframed as product story not sprint scope
- **NEW content (no source in repo):** Shopify app posture, what Play Thesis cards look like to the merchant, Klaviyo bundle workflow, approval flow, frontend frame. See §F below.

### STATE.md sources
- `ENGINE_OVERVIEW.md` §2 (pipeline) — almost verbatim, add PROFILE step from S6.5
- `ENGINE_OVERVIEW.md` §3 (slate lanes) — verbatim
- `ENGINE_OVERVIEW.md` §5 (current state, what works/doesn't, beauty/supplements counts) — refresh post-S7.6
- `ENGINE_OVERVIEW.md` §8 (evidence tiers A/B/C/D) — verbatim
- `ENGINE_OVERVIEW.md` §8.5 (three orthogonal gates) — verbatim
- `ARCHITECTURE_PLAN.md` Part I §A (Tier definitions) — distilled
- `ARCHITECTURE_PLAN.md` Part IV (Store Profile Layer) — distilled into pipeline section
- The S7.6 close LOAD-BEARING UPDATE blocks at ARCHITECTURE_PLAN.md L13-56 — distilled to one paragraph: "Today, four of five Tier-B builders fire honestly on Beauty fixtures; replenishment_due dormant by design"
- Current flag defaults: `ENGINE_V2_BUILDER_WINBACK_DORMANT=ON`, `ENGINE_V2_BUILDER_REPLENISHMENT_DUE=OFF`, `ENGINE_V2_BUILDER_AOV_BUNDLE=ON`, etc. — assembled from memory.md S6/S7/S7.6 closeouts
- Key files list — derived from CLAUDE.md L6-11 + ARCHITECTURE_PLAN.md "Relevant file paths" L909-921

### PIVOTS.md sources (one entry per pivot, each ~30-40 lines)
1. **Decision Core (V2) reframe — 2026-05-01.** Source: `agent_outputs/m0-m9-final-review-reconciled.md` L1-30, `memory.md` L42-74 "Reconciled Direction." What changed: dashboard → decision engine that abstains. Lock-in: evidence-class invariants, ABSTAIN_SOFT contract.
2. **Phase 5 — operational-inert recognition.** Source: `memory.md` L107-122. What changed: shipped Considered list + directional builder. Lock-in: rejected plays are first-class output.
3. **Phase 6A/B Stop-Coding Line — 2026-05-05.** Source: `agent_outputs/phase6b-stop-coding-line-reconciled.md`, `memory.md` L154-166. What changed: engine emits typed JSON; renderer is a downstream agent. Lock-in: engine_run.json is the product surface; briefing.html is debug-only.
4. **Single-demote-channel invariant — 2026-05-22.** Source: `ARCHITECTURE_PLAN.md` 2026-05-22 LOAD-BEARING UPDATE block, `memory.md` S7.6 close L1645-1708. What changed: all demote paths route through `apply_guardrails_to_injected`; `priority_prepend` covers three channels. Lock-in: founder + DS sign-off required to bypass.
5. **Priors validation gate (S7.5) — 2026-05-17.** Source: `ARCHITECTURE_PLAN.md` Part III-1, `memory.md` S7.5 entries L403-530. What changed: heuristic-unvalidated priors refuse the EB blend; SOFT_PRIOR_UNVALIDATED abstain. Lock-in: no fabricated priors dressed as math.
6. **Synthetic-fixture honesty rule — 2026-05-22.** Source: `memory.md` L1615-1632, T2.5 escalation verdict. What changed: don't reshape fixtures to fire builders. Lock-in: honest dormancy is the product.
7. **Instrumentation-over-prediction rule — 2026-05-22/05-23.** Source: `CLAUDE.md` L37-43, `memory.md` S7.6 key learnings L1764-1775. What changed: two failed predictions = stop guessing, instrument. Lock-in: subagent handoff discipline.
8. **Beta success reframe (month-1-wow → month-2-return) — 2026-05-17.** Source: `ENGINE_OVERVIEW.md` L88-117 and §10, `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md`. What changed: Phase 9 outcome loop deferred post-beta; ML predictive layer pulled into beta scope. Lock-in: month-2 value comes from ML refit on 30 more days, not outcome calibration.
9. **ML as audience-ranking, not play-source — 2026-05-17.** Source: `ENGINE_OVERVIEW.md` §7 lines 130-140. What changed: ML doesn't add plays; it ranks customers within each play's audience. Lock-in: ModelFitStatus gate.
10. **Vertical hard-lock — D-8 (2026-05-09).** Source: `memory.md` L180. Lock-in: beauty/supplements/mixed only, refused at engine entry.
11. **D-5 manual import (no Klaviyo network calls) — 2026-05-09.** Source: `memory.md` L177, KI-7. Lock-in: AWS migration is the right time to revisit.
12. **Tier-B reframe — 2026-05-16.** Source: `ARCHITECTURE_PLAN.md` Part I §A and §B. What changed: `returning_customer_share` is a state statistic, not intervention-shaped; five new Tier-B builders ground evidence in cohort-level intervention metrics. Lock-in: state_statistic is forbidden as a Tier-B builder's signal_kind.

### ROADMAP.md sources
- `ENGINE_OVERVIEW.md` §6 redesign plan + table (lines 88-117)
- `agent_outputs/implementation-manager-s6-s14-revised-plan-ml-layer.md` (current execution roadmap per ENGINE_OVERVIEW L92)
- `ARCHITECTURE_PLAN.md` "What This Plan Does NOT Do" L88-98 — distilled to a deferrals section
- `KNOWN_ISSUES.md` Phase 9 entry conditions (KI-1..KI-5) — pointer only
- Active sprint status from `memory.md` last 2 sprints

### CLAUDE.md (slim)
- Current L1-26 (Project Context, Agent Review Panel, General Conventions) — keep
- Current L27-46 (Subagent Handoff Discipline) — keep verbatim; this is load-bearing
- **NEW:** "Doc Map" block: which active doc to read for which question
- Drop the reference to ENGINE.md (now legacy/)

### agent_outputs/INDEX.md
- Generated index, three sections: Active Sprint (S8+ currently), Recently Closed (S6, S6.5, S7, S7.5, S7.6 — last 3 months), Historical (everything older)
- Within each section, group by type: `*-plan.md` (IM), `*-verdict.md` / `*-review.md` (DS architect, PM), `*-summary.md` (code-refactor closeouts), `*-reconciled.md` (multi-agent reconciliations)
- Each entry: filename + one-line scope. No body content.

---

## D. Archive vs delete vs keep-as-is

| File | Recommendation | Justification |
|---|---|---|
| `ARCHITECTURE_PLAN.md` | **Archive** to `archive/ARCHITECTURE_PLAN_2026-05-24.md` | Massive load-bearing content but the supersession chain has made it unreadable as a live doc. Archive preserves every LOAD-BEARING UPDATE block. New design specs go to `agent_outputs/ecommerce-ds-architect-*.md`. |
| `memory.md` | **Archive** to `archive/memory_2026-05-24.md` | The per-ticket-receipts pattern is the antipattern. Closeouts already live in `agent_outputs/code-refactor-engineer-<ticket>-summary.md`. Founder decisions D-1..D-8 must be migrated into PIVOTS.md or `docs/DECISIONS.md` (already exists per memory.md L14) BEFORE archive. **Risk: D-1..D-8 are referenced by ~30 places in code/docs — must verify DECISIONS.md is canonical first.** |
| `memory_archive.md` | **Keep as archive** in `archive/` | Already labeled archive. Move to `archive/` folder. |
| `KNOWN_ISSUES.md` | **Keep as-is** (active) | Format works. Trim resolved-older-than-2-sprints into KI_ARCHIVE.md. |
| `TESTING_GUIDE.md` | **Move to `docs/legacy/`** | Legacy-engine KPI cheatsheet. Useful reference, not active path. |
| `ENGINE.md` | **Move to `docs/legacy/`** | Documents legacy multi-window weighted-vote engine (V1). Contradicts V2 architecture. Preserve for context. |
| `ENGINE_OVERVIEW.md` | **Source-of-truth for STATE.md; then archive** | This is the best doc in the repo. Its content is the seed for STATE.md. Archive original once STATE.md ships. |
| `STORE_DATA_REQUIREMENTS.md` | **Keep at root** | Orthogonal to engine docs; merchant-facing onboarding spec. Useful as-is. |
| `README.md` | **Rewrite** to 30 lines: one-paragraph product description + 5 doc pointers (PRODUCT/STATE/PIVOTS/ROADMAP/KNOWN_ISSUES) + run command | Current content is stale and demo-flavored. |
| `CLAUDE.md` | **Trim + add Doc Map** | Already short. Subagent Handoff Discipline is load-bearing — keep verbatim. |
| `docs/DECISIONS.md` | **Verify canonical, promote in CLAUDE.md** | Per memory.md L14 this is supposed to be the source-of-truth for founder-locked heuristics. Confirm before archiving memory.md. |
| `docs/memory_substrate.md` | **Keep as-is** | Substrate spec; consumed by Swarm team. Schema contract reference. |
| `docs/play_registry.md` | **Keep as-is** | Play inventory reference. |
| `docs/engine_validation_guide.md` | **Keep as-is** | M0-M10 invariants. Active test discipline reference. |

**What gets lost if executed naively:**
- The LOAD-BEARING UPDATE blocks at the top of ARCHITECTURE_PLAN.md (L9-56) carry invariants that are referenced in CLAUDE.md ("Pay attention to Part III-1 priors validation reframe, Part IV Store Profile Layer, and the 2026-05-22 amendment locking the single-demote-channel invariant"). These MUST be migrated into PIVOTS.md verbatim before ARCHITECTURE_PLAN.md is archived.
- D-1..D-8 founder decisions in memory.md L173-182. Must verify they're in `docs/DECISIONS.md` first.
- The exact filename pinning in tests — `tests/test_s7_6_c1_priority_prepend_invariant.py` is referenced repeatedly; CI doesn't break if docs move, but the conceptual linkage does.

---

## E. agent_outputs/ strategy

**Index format (`agent_outputs/INDEX.md`):**

Generated index, regenerated by hand (or eventually by a script) quarterly. Three sections:

1. **Active sprint outputs** (last sprint + current sprint). Bold the most recent. CLAUDE.md L34 "the most recent" now has a concrete referent.
2. **Recent closed sprints** (last 3 months / last 4 closed sprints). Subgrouped by sprint. Each entry: filename + one-line scope.
3. **Historical** (everything older). Just a flat list with sprint tag if inferable; no descriptions.

Within each section, group by agent type:
- `implementation-manager-*-plan.md` — sprint plans (the "what we're going to do" docs)
- `ecommerce-ds-architect-*-verdict.md` / `*-review.md` — DS verdicts and reviews (the "is this defensible" docs)
- `product-strategy-pm-*-review.md` — PM reviews (the "does this serve the merchant" docs)
- `code-refactor-engineer-*-summary.md` — ticket closeouts (the "what shipped" docs)
- `*-reconciled.md` — multi-agent reconciliations (the "founder review packet" docs)

**Retention policy:**
- All agent_outputs files preserved indefinitely (founder fear of losing context).
- Index regenerated at end of each sprint.
- No file movement; just index curation.

**Promotion to active docs:**
- A `ds-architect-*-verdict.md` that introduces a new invariant → PIVOTS.md entry references it.
- A `*-plan.md` that becomes the current execution roadmap → ROADMAP.md references it as "current sprint sequence."
- A `*-summary.md` is never promoted; closeouts stay in agent_outputs/.

**The CLAUDE.md L34 instruction ("read relevant agent_outputs/*-summary.md for the most recent sprints") gets concretized by the index** — the index defines "most recent" and "relevant."

---

## F. Missing PRODUCT context (currently scattered, must consolidate)

These facts agents must know but currently must infer from code/scattered notes. They belong in **PRODUCT.md**:

1. **This is a Shopify app for DTC merchants in beauty/supplements/mixed verticals.** Today it runs locally on Shopify CSV exports. (Inferred from `STORE_DATA_REQUIREMENTS.md`, D-8 vertical lock, README L10.)
2. **The local CSV→HTML workflow is scaffolding.** The future product is a hosted Shopify app where merchants connect their store and Klaviyo, and the engine runs monthly to produce a slate of action cards that merchants review and approve. (Inferred from D-5, memory.md storage backend note L181-182, AWS migration note.)
3. **The merchant-facing surface is Play Thesis cards (Recommended Now / Recommended Experiment / Considered / Watching).** Each card carries a typed evidence chip, a mechanism description ("What we'd send"), an audience definition, and a revenue range when defensible. (Inferred from `src/engine_run.py` PlayCard schema + Stop-Coding Line.)
4. **`engine_run.json` is the product contract.** The frontend app (out of scope for v2 engine) reads it and renders Play Thesis cards. `briefing.html` is debug-only and will retire when the frontend app ships. (Per `ARCHITECTURE_PLAN.md` 2026-05-24 LOAD-BEARING UPDATE block.)
5. **Klaviyo is the publish surface.** After merchant approval, the engine's intent is to bundle a Klaviyo campaign (audience CSV + flow definition + send time) and publish it through Klaviyo. Today this is manual; D-5 forbids Klaviyo API calls in v1. (Inferred from KI-7 provider enum discussion, S6 campaign_sent import path, AWS migration note.)
6. **The outcome loop is import-driven, not API-driven.** Merchants (or the founder) manually import `campaign_sent` events and later `outcome_observed` events; the engine recalibrates priors monthly. Phase 9 (outcome loop) is post-beta. (Per ARCHITECTURE_PLAN.md Part D, memory.md D-5.)
7. **Beta success = month-1-wow + month-2-return.** Not 6-month outcome calibration loop. Month 2 value comes from the ML predictive layer refitting on 30 more days of data, not from realized outcomes. (Per ENGINE_OVERVIEW.md §10.)
8. **The agentic AI interface is downstream.** Per the Stop-Coding Line, narration/framing/phrasing is the downstream agent swarm's job — the engine emits typed fields. (Per `agent_outputs/phase6b-stop-coding-line-reconciled.md`.)
9. **D-1..D-8 founder decisions bound the design space.** Notably: forever retention, full-wipe-only deletion, manual import only, ML explicitly banned for specific use-cases, vertical hard-lock. (Per memory.md L173-182.)
10. **Storage today is local SQLite per merchant; future is S3 + managed Postgres on AWS.** No disk-growth optimization, no TTLs. (Per memory.md L181-182.)
11. **There is currently no frontend app rendering Play Thesis cards.** `briefing.html` is a debug renderer. The merchant-facing UI is unbuilt; the engine ships typed JSON ready for it. (Inferred from ARCHITECTURE_PLAN.md L96, S7.6 CLI fix block.)

Where this lives: **PRODUCT.md** is the home for all of this. STATE.md describes engine internals; PRODUCT.md describes the product wrapping the engine.

---

## G. Migration risk

**What could go wrong:**

1. **D-1..D-8 disappear from active read path if memory.md is archived without first verifying `docs/DECISIONS.md` is canonical.** Today memory.md L14 says DECISIONS.md is the canonical registry, but tests and code reference founder decisions by D-N number. Need a 30-minute audit of "where is each D-N referenced" before archiving memory.md.

2. **Subagent handoff regresses.** CLAUDE.md L27-46 tells agents to read ARCHITECTURE_PLAN.md, memory.md, memory_archive.md, KNOWN_ISSUES.md, and agent_outputs/*-summary.md. If we archive ARCHITECTURE_PLAN.md and memory.md, the handoff instruction goes stale. Must update CLAUDE.md Doc Map in the same commit as the archive move.

3. **LOAD-BEARING UPDATE blocks lose their carrying context.** Each block at ARCHITECTURE_PLAN.md L9-56 supersedes specific items in Parts I-IV. If we extract pivots into PIVOTS.md without preserving the supersession context (what they replaced), an agent reading PIVOTS.md learns the *current* state but not *why the prior state was wrong* — which is exactly what the founder asked PIVOTS.md to communicate.

4. **The "Never assume; instrument and verify" rule (CLAUDE.md L37-43) gets diluted if it moves around.** It's load-bearing because of the S7.6-T7.5 spiral (three wrong predictions). Must stay in CLAUDE.md verbatim, not migrate to PIVOTS.md.

5. **Sprint closeout micro-receipts (commit hashes, sha256s, file paths) disappear from memory.md without a new home.** These live in `agent_outputs/code-refactor-engineer-<ticket>-summary.md` today, but if memory.md was the consolidated read for "what shipped," agents may not find sprint-by-sprint receipts easily. The agent_outputs/INDEX.md addresses this — but the INDEX must ship in the same commit.

6. **KI status drift.** If KI-N is "resolved" per memory.md but "tracked" per KNOWN_ISSUES.md (this has happened — e.g., KI-25 history), archiving memory.md without reconciling open KIs into KNOWN_ISSUES.md leaves stale state. One-time reconciliation pass needed.

7. **agent_outputs/INDEX.md goes stale immediately if not regenerated.** Quarterly cadence is the minimum.

**Mitigation:**
- Two-commit migration. Commit 1: ship new docs (PRODUCT/STATE/PIVOTS/ROADMAP/INDEX) AND update CLAUDE.md AND verify DECISIONS.md AND reconcile KIs. Old docs stay in place but unreferenced. Commit 2 (a week later, after agent verification): move old docs to archive/.
- Hard-stop: do not start the migration if `docs/DECISIONS.md` doesn't already canonicalize D-1..D-8.

---

## H. One-time vs ongoing cost

**One-time cost (rough estimate):**

| Task | Hours |
|---|---|
| Draft PRODUCT.md (new content for items 1-11 in §F + light extraction) | 4-6 |
| Draft STATE.md (~70% extraction from ENGINE_OVERVIEW + light refresh + flag-default audit) | 3-4 |
| Draft PIVOTS.md (12 pivots × 30 lines, mostly extraction with reframing) | 6-8 |
| Draft ROADMAP.md (extraction + current sprint update) | 2-3 |
| Slim CLAUDE.md + add Doc Map | 1 |
| Generate agent_outputs/INDEX.md (manual first pass, 143 files) | 3-4 |
| Reconcile open KIs from memory.md into KNOWN_ISSUES.md | 2 |
| Verify D-1..D-8 in docs/DECISIONS.md | 1 |
| Move legacy docs (ENGINE.md, TESTING_GUIDE.md, README.md rewrite) | 1 |
| Archive ARCHITECTURE_PLAN.md, memory.md, ENGINE_OVERVIEW.md | 0.5 |
| Verification pass with a fresh subagent dispatch | 1-2 |
| **Total** | **~25-35 hours** |

This is one focused founder + one DS architect dispatch over a week.

**Ongoing cost (steady-state):**

- **Per sprint close:** Update STATE.md if any pipeline / flag-default / current-state fact changed (~15 min). Append entry to ROADMAP.md if sprint sequence shifted (~5 min). Reconcile new KIs into KNOWN_ISSUES.md (~10 min). **Total: ~30 min/sprint.**
- **Per architectural pivot:** Append entry to PIVOTS.md (~30 min). Rare — maybe one per 2-3 sprints.
- **Per ticket close:** Write `agent_outputs/code-refactor-engineer-<ticket>-summary.md` as today; no separate memory.md entry. **Net reduction vs. today: ~10 min/ticket.**
- **Quarterly:** Regenerate agent_outputs/INDEX.md (~30 min).
- **PRODUCT.md cadence:** Touch monthly at most. Real product pivots only.

**Net steady-state effect:** ~20-30 min less doc work per ticket close (no more memory.md double-entry); ~30 min more per sprint close (STATE/ROADMAP refresh). Roughly a wash, but with vastly higher *signal* per minute of doc time.

---

# Revisions — Founder Pushback Round (2026-05-24, same day)

Founder challenged two calls. DS agrees with the founder on Q1 (reverses prior recommendation) and refines Q2 (differentiates by document type). Calls below override the corresponding sections above.

## Revised Q1 — Keep memory.md (trimmed), don't archive it

**Reversed.** The original "archive memory.md entirely" call was right about the pathology (1,820 lines, per-ticket bloat, double-write with agent_outputs/) but wrong about the function. memory.md is the **only** doc that gives top-to-bottom narrative chronology. PIVOTS.md captures the bends in the river; agent_outputs/ captures depth per ticket; neither captures the **stream**. Losing the stream means a new agent can answer "what happened in S7.6" but not "how did we get from M0 to S7.6." That arc is load-bearing for orientation.

**Critical structural shift — make the cap a SHAPE constraint, not a length constraint.** memory.md has violated its own 15-line cap for six straight months because self-discipline at write-time has failed. Replace with mechanical enforcement:

- memory.md entries are restricted to the **template at L20-36 only** — fixed fields, no free-form narrative paragraphs, no risk discussion, no "key learnings" sections.
- The closeout commit is forbidden from including prose. All narrative goes in the corresponding `agent_outputs/code-refactor-engineer-<ticket>-summary.md` (which already exists for nearly every ticket — the verbose content is currently duplicated).
- **Pre-commit lint check:** reject any new memory.md entry exceeding ~20 lines between `^## ` markers. This is the only enforcement that survives a Friday-night closeout.
- Add one line to CLAUDE.md Subagent Handoff Discipline: *"memory.md entries are template-shaped only. Narrative goes in the summary file."*

**Retroactive trim:** 2-3 hour mechanical pass, not a multi-day project. For each existing entry: keep the template fields, push the verbose content into the corresponding `code-refactor-engineer-*-summary.md` (which already carries it as a duplicate). Risk is small — nothing is deleted, content moves from a duplicate location to its canonical home.

**Cascading effect — PIVOTS.md scope narrows.** If memory.md narrates chronology and STATE.md narrates the present, PIVOTS.md no longer needs to carry "what shipped when." It becomes a narrower doc: the **~6-8 belief-changing moments** where what we thought was true got proven wrong (V2 reframe, Tier-B reframe, single-demote-channel, priors validation, synthetic-fixture honesty, instrumentation-over-prediction, beta success reframe). Mechanical-shipped pivots like Stop-Coding Line can be referenced from memory.md chronology rather than carrying a full PIVOTS.md entry.

PRODUCT.md and STATE.md are unaffected by this revision.

## Revised Q2 — agent_outputs/ retention is type-dependent, not uniform

Original audit said "all agent_outputs files preserved indefinitely." That's right *for storage*, wrong *for the index*. Different document types have different decay curves. Treating them uniformly is what got us to 143 unindexed files. The fix is the INDEX — nothing is deleted; the index separates load-bearing types from process-residue.

**Per-type calls:**

| Document type | Verdict | Rule |
|---|---|---|
| `implementation-manager-*-plan.md` | **Process residue** | Useful before/during execution; superseded by the closeout summary the moment the sprint closes. Don't delete — occasionally shows "what we believed we'd do vs. what we did." **Demote to "Historical" in the INDEX after sprint close.** Exception: the current sprint's plan is load-bearing until close. |
| `ecommerce-ds-architect-*-verdict.md` / `*-review.md` | **Load-bearing until superseded** | These introduce invariants (single-demote-channel, joint-p<0.10, priors validation gate, Tier-B reframe). Practical rule: every DS verdict that locks an invariant gets one line in PIVOTS.md citing the file path. Exploratory verdicts and second-opinion reviews that didn't lock anything demote to Historical after the sprint closes. |
| `product-strategy-pm-*-review.md` | **Load-bearing only when it changes scope** | PM reviews that pushed the beta-success reframe, Stop-Coding Line, or vertical hard-lock are load-bearing — they reshape what the product is. PM reviews that approved a sprint's UX shape are process-residue. Rule: if a PM review cites a founder decision (D-N) or changes a doc in the active read path, it's load-bearing and gets cited from PRODUCT.md or PIVOTS.md. Otherwise demote to Historical. |
| `code-refactor-engineer-*-summary.md` | **Load-bearing forever (as receipts)** | These are commits, sha256s, file paths, test counts. Nobody reads them top-to-bottom; they're looked up by ticket ID. Keep all in place indefinitely. With memory.md staying as chronology, each memory.md entry's `Summary: [link]` line becomes the lookup path. No promotion to active docs needed — memory.md is the index. |
| `*-reconciled.md` (multi-agent reconciliations) | **Load-bearing forever** | The founder-review decision packets where DS + PM + IM converged on a direction (legacy-vs-V2, Stop-Coding Line, m0-m9 reconciled, synthetic-phase5-e2e). ~6-8 exist across the project — small surface, high signal. Cited from PIVOTS.md. Never demote. |
| `statistical-code-reviewer-*` / `skeptic-red-team-reviewer-*` | **Historical exploratory** | Only two exist (both `-initial.md`). One-time external-perspective passes. Index as "Historical exploratory reviews" and leave them be. |

**Key reframe on founder's "fear of losing context":** the fear is correct, but "keep everything in the active read path" is the wrong response — that's what produced 143 unindexed files. The fix is the **INDEX**, not deletion. Nothing dies. The index, regenerated quarterly, surfaces load-bearing types (verdicts, reconciliations, current-sprint plan, all summaries) and buries process-residue (closed-sprint IM plans, sprint-completed PM reviews) under a "Historical" heading. CLAUDE.md L34's "the most recent" becomes a defined pointer into the index, not an `ls -lt` invitation.

## Revised active read path (supersedes §B above)

- **PRODUCT.md** (≤200) — Shopify app, merchant journey, future state
- **STATE.md** (≤500) — what's true RIGHT NOW
- **PIVOTS.md** (≤300, narrowed) — 6-8 belief-changes only
- **ROADMAP.md** (≤300) — what's next
- **memory.md** *(kept, template-only, lint-enforced)* — chronology stream
- **KNOWN_ISSUES.md** — open KIs
- **CLAUDE.md** (slim + Doc Map + template-shape rule)
- **agent_outputs/INDEX.md** — by-type, by-recency, Historical section hides residue

ARCHITECTURE_PLAN.md still archives (supersession chain is unfixable). memory_archive.md continues as cold-storage rollover for memory.md.

## Migration trigger

Cleanup begins when the parallel Sprint 8 first ticket lands. Do not start before — keeps doc churn out of in-flight refactor work.
