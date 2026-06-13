# Documentation Migration — Phase 0 Pre-Cleanup Gates

**Date:** 2026-05-25
**Mode:** Read-only audit. No files were edited, moved, or committed.
**Audit reference:** `agent_outputs/ecommerce-ds-architect-doc-audit-2026-05-24.md` (Revisions section at L254-307 supersedes §B/§C/§D).
**Founder constraint:** nothing gets lost.

The revised plan keeps memory.md (template-only, lint-enforced), archives ARCHITECTURE_PLAN.md, and introduces PRODUCT/STATE/PIVOTS/ROADMAP + an agent_outputs/INDEX. This document evaluates whether executing that plan today would break references or lose content.

---

## Gate 1 — D-1..D-8 founder decisions canonical home

**Findings.**

- `memory.md` L173-182 carries the full canonical text of D-1 through D-8 plus the 2026-05-10 storage backend addendum. This is the authoritative content.
- `docs/DECISIONS.md` is a 500-line registry of *operational* decisions (D-S6.5-1 .. D-FLOOR-aov_lift_via_threshold_bundle .. D-S7.5-3, etc.) using a `D-<sprint>-<n>` ID scheme. It does NOT carry D-1..D-8 entries.
- Worse: DECISIONS.md L13 explicitly delegates D-1..D-8 OUT of itself: *"What stays OUT: ... founder strategy axioms (lives in memory.md D-1 through D-8); unresolved bugs (lives in KNOWN_ISSUES.md)."*
- memory.md L14 inversely points TO DECISIONS.md for "Locked decisions / per-play floors / per-vertical defaults" but says nothing about D-1..D-8 being canonical in DECISIONS.md.
- The two files agree: **D-1..D-8 are canonical in memory.md, not DECISIONS.md.**

**Reference inventory (D-1..D-8 across the repo):**

| ID | src/ | tests/ | docs/ | agent_outputs | root .md |
|---|---|---|---|---|---|
| D-1 | `main.py:62,69,93,107,1861`, `memory/events.py:153,213`, `memory/lineage.py:3` | `test_s3_substrate_emission.py`, `test_lineage.py`, `test_export_roundtlip.py` | `memory_substrate.md:269` | many (incl. KI-29 cross-ref) | memory.md, memory_archive.md, ARCHITECTURE_PLAN.md |
| D-2 | `memory/store.py:6,19` | — | `memory_substrate.md:5,21` | — | KNOWN_ISSUES.md KI-10/KI-13, ARCHITECTURE_PLAN.md KI-13 row |
| D-3 | `store_id.py:99`, `memory/store.py:19` | `test_store_id.py:97`, `test_export_roundtrip.py:102` | `memory_substrate.md:21` | — | memory_archive.md |
| D-4 | `tools/export_store.py` (implicit) | `test_export_roundtrip.py:1` | — | — | ARCHITECTURE_PLAN.md:1624 |
| D-5 | `memory/events.py:387` | — | — | KI-29 in KNOWN_ISSUES.md L221,232 | ARCHITECTURE_PLAN.md:933,1031,1609,1633 |
| D-6 | `profile/cadence.py:6` | `test_s6_5_t3_cadence_seasonality.py:12,160` | `DECISIONS.md:388,391` | KI-29 L221 | ARCHITECTURE_PLAN.md:142,1610,1634; memory_archive.md:2011 |
| D-7 | — | — | — | (mentioned in memory_archive) | — |
| D-8 | `priors_loader.py:363,801,963,979,1009` | `test_vertical_hard_refuse.py:65`, `test_g3_supplements_priors.py` (multiple) | — | — | KNOWN_ISSUES.md KI-10,KI-28,KI-29; ARCHITECTURE_PLAN.md:972,1611,1635,1639; memory_archive.md |

Total: 50+ load-bearing references across code, tests, root docs, and KIs. D-N strings appear in CI assertion messages (`test_s3_substrate_emission.py:167` quotes `"violates D-1"`).

**Risk if memory.md is archived without content migration.** Every D-N citation in code/tests is implicitly a pointer to memory.md L173-182. Archiving memory.md doesn't break links (none are URLs), but a future agent searching for the canonical D-N text needs an active read-path home for it.

**The revised plan KEEPS memory.md (trimmed, template-only).** That preserves D-1..D-8 in their canonical home — IF the retroactive-trim mechanical pass does not touch the L169-182 Founder Decisions block. That block is NOT a per-ticket entry, so the template-shape lint (≤20 lines per `^## ` marker) should not touch it. Confirm by inspecting the trim ruleset before running it.

**Verdict: FLAG.** The migration as written is safe ONLY if (a) the retroactive memory.md trim explicitly preserves the `# Founder Decisions (2026-05-09)` section verbatim, and (b) one line is added to `docs/DECISIONS.md` L13 changing "lives in memory.md D-1 through D-8" to a specific section anchor (e.g., "lives in `memory.md#founder-decisions-2026-05-09`"). Without those two guards, the trim could quietly delete D-N text on a future Friday-night closeout, and 50+ code references would silently lose their canonical referent.

---

## Gate 2 — KI status drift between KNOWN_ISSUES.md and memory.md

**Findings.** KNOWN_ISSUES.md is 469 lines and carries 47 KIs (extracted via `### KI-` headers). Status legend declared at L8: `open | tracked | accepted | resolved`. memory.md references KIs in dozens of places, mostly in sprint-close entries. Sampled drift below:

| KI | KNOWN_ISSUES.md status | memory.md latest mention | Drift? |
|---|---|---|---|
| KI-1 | open | not re-mentioned (Phase 9 entry condition) | no |
| KI-2 | open | not re-mentioned | no |
| KI-3 | resolved (S5-T1, 2026-05-11) | "KI-3 + KI-26 both flipped open → resolved" (memory.md L359) | no |
| KI-18 | resolved (S6-T2, 2026-05-18) | "KI-18 closed" (memory.md L637,830) | no |
| KI-19 | resolved (G-3) | "KI-19 flipped to resolved" (memory.md L336) | no |
| KI-20 | resolved (S5-T2) | "KI-20 supplements first_to_second_purchase typed honest abstain" (L371) | no |
| KI-21 | open | not re-mentioned recently; "Likely closes KI-21 + KI-23" (L1374, aspirational) | no — explicit "likely" |
| KI-22 | resolved (S5-T3) | "S5-T3 — KI-22 supplements repeat-rate metric incoherence" (L386) | no |
| KI-23 | open | tracked at L1374 as "likely closes" — not actually closed | no |
| KI-24 | open (G-4 surface tightened, Phase 4.2 redesign still pending) | memory.md L351 "KI-24 stays open" | no |
| KI-25 | tracked | memory.md L336 "KI-25 flipped open → tracked" | no |
| KI-26 | resolved (S5-T1) | memory.md L359 "KI-3 + KI-26 both flipped open → resolved" | no |
| KI-27 | accepted | memory.md L644,663,691 — extensively documented as "KEEP ACCEPTED" | no |
| KI-28 | tracked | memory.md L336 "KI-28 stays tracked" | no |
| KI-NEW-G | open (T2.5 sub-thread RESOLVED-AS-DOCUMENTED) | memory.md L1736 "KI-NEW-G updated"; L1787 status synced | no |
| KI-NEW-J | open (defer to S14, locked resume trigger 2026-05-24) | memory.md L1839 carries 2026-05-24 update | no |
| KI-NEW-K | RESOLVED 2026-05-24 (S8-T0) | memory.md L1822-1843 (S8-T0 entry documents resolution) | no |
| KI-NEW-L/M/N | open, deferred per S8 Q3 verdict 2026-05-24 | memory.md L1849-1860 syncs S13.5 / S14-driven deferrals | no |
| KI-NEW-O | open (filed 2026-05-23) | memory.md L1759,1805 (caveat) | no |

**No status drift found.** memory.md and KNOWN_ISSUES.md are tightly synced — the founder's discipline of bundling KI updates into the same sprint-close commit as the engine change has paid off. The "Last updated" footer on KNOWN_ISSUES.md L469 also matches memory.md's most-recent S8 close.

Open count breakdown from KNOWN_ISSUES.md L457-467:

| Category | Open | Tracked | Accepted |
|---|---|---|---|
| Phase 9 entry conditions | 4 | 0 | 0 |
| Deferred edge cases | 1 | 0 | 3 |
| Documented & accepted | 0 | 0 | 5 |
| Schema / contract risks | 1 | 0 | 1 |
| Supplements & vertical | 3 | 3 | 1 |
| Architectural limitations | 18 | 0 | 0 |
| **Total** | **27** | **3** | **10** |

40 KIs total (27+3+10 = 40, plus the 7 already resolved = 47 raw header count). Reconciliation: a 30-minute spot-check, not a multi-hour project.

**Verdict: PASS.** KI registry is in good shape. The migration does not need to reconcile statuses; just preserve KNOWN_ISSUES.md as-is in the active read path (the audit already plans this).

---

## Gate 3 — docs/ folder load-bearing scope

**Inventory:**

| File | Purpose | Load-bearing? | Audit "keep" list? |
|---|---|---|---|
| `DECISIONS.md` | 500-line registry of D-S6.5-x / D-FLOOR-x operational decisions (per-play floors, per-vertical windows, hard-stops) | YES — sole canonical home for these | Yes (implicitly — audit doesn't move it) |
| `memory_substrate.md` | Substrate schema reference (event types, views, lineage_id) | YES — Swarm consumer doc | Yes |
| `play_registry.md` | Play registry reference | YES (referenced by Sprint 5+ Swarm work) | Yes |
| `engine_validation_guide.md` | Validation / pinned-fixture authoring guide | YES (referenced by sprint closeouts) | Yes |
| `engine_flags.md` | ENGINE_V2_* flag table | YES — single source of truth for flag stack | **NOT in audit's keep list** |
| `onboarding-optimization-guide.md` | Onboarding UX writeup | Likely vestigial (UX-design memo, no code reference) | Not mentioned |
| `PILOT_UPLOAD_GUIDE.md` | Pilot data upload instructions | UNKNOWN — possibly load-bearing for beta operator | Not mentioned |
| `beacon-brand-identity.html` | Brand identity asset | Asset, not doc | Not mentioned |
| `demo_briefing.html` | Demo briefing asset | Asset, not doc | Not mentioned |
| `legacy/` | (empty per ls error — appears to not exist yet) | n/a | n/a |

**Findings.**

- `docs/engine_flags.md` is referenced 0 times in src/tests grep, but it's the table-of-truth for the ENGINE_V2_* flag stack which is itself load-bearing across the codebase. The audit's omission is likely an oversight — should be in the "keep" list.
- `onboarding-optimization-guide.md` — vestigial UX memo; safe to move to a `docs/legacy/` sub-tree.
- `PILOT_UPLOAD_GUIDE.md` — title implies beta-operator-facing instructions. Founder should confirm intent before relocating.
- `beacon-brand-identity.html` and `demo_briefing.html` are deliverable assets, not docs. They aren't in scope for a doc-migration but should not be touched.

**Verdict: FLAG.** Three issues for founder decision before Phase 1:
1. Add `docs/engine_flags.md` to the audit's explicit "keep" list (it's load-bearing).
2. Decide whether `PILOT_UPLOAD_GUIDE.md` is current or stale — if current, it's load-bearing for beta operators; if stale, move to `docs/legacy/`.
3. Confirm `onboarding-optimization-guide.md` is vestigial before relocating.

---

## Gate 4 — agent_outputs/ inventory by type

**Counts (146 files total):**

| Pattern | Count |
|---|---|
| `code-refactor-engineer-*-summary.md` | 85 |
| `ecommerce-ds-architect-*.md` (verdicts + reviews + memos) | 22 |
| `implementation-manager-*-plan.md` | 14 |
| `product-strategy-pm-*-review.md` | 11 |
| `*-reconciled.md` | 5 (`beacon-ml-roadmap-reconciled-review`, `m0-m9-final-review-reconciled`, `phase6b-stop-coding-line-reconciled`, `play-lifecycle-discussion-reconciled`, `legacy-vs-v2-final-recommendation` is *-recommendation not *-reconciled but topically reconciliation) |
| `skeptic-red-team-reviewer-*` / `statistical-code-reviewer-*` | 2 (both `-initial.md`) |
| **Misc / orphans** | 11 |
| **Sub-directories** (excluded from md count) | 3 (`m6_sample_run`, `m8_parity_review`, `phase5_samples`, `synthetic_fixes_8_11_samples`) |

**Orphan files (need a home in the INDEX):**

1. `beacon-ml-roadmap-reconciled-review.md` — reconciled (load-bearing)
2. `campaign-slate-contract-final.md` — Sprint 2 contract document (likely load-bearing, no prefix)
3. `ds-architect-store-profile-layer-proposal.md` — DS proposal (load-bearing, used 'ds-architect-' prefix not 'ecommerce-ds-architect-')
4. `i1-spike-findings.md` — Sprint 3 spike memo (D-7 deferred — referenced in D-7)
5. `legacy-vs-v2-final-recommendation.md` — reconciliation (load-bearing)
6. `m0-m9-final-review-reconciled.md` — reconciled (load-bearing)
7. `phase6a-final-review.md` — review (load-bearing per memory.md project_phase6a_final_review)
8. `phase6b-stop-coding-line-reconciled.md` — reconciled (load-bearing, established Stop-Coding Line)
9. `play-lifecycle-discussion-reconciled.md` — reconciled
10. `synthetic-fixture-generator-summary.md` — generator summary
11. `synthetic-phase5-e2e-final-review.md` — review

All 11 orphans are load-bearing. The naming convention drift (e.g., `ds-architect-` vs `ecommerce-ds-architect-`) is the cause. **The audit's pattern-matched INDEX will miss these unless the INDEX is built by hand-classifying once, not by glob.**

**Duplicate-topic candidates:**

- `ecommerce-ds-architect-baseline-and-campaign-slate.md` + `product-strategy-pm-baseline-and-campaign-slate.md` + `campaign-slate-contract-final.md` — three docs on the same topic; intentional (DS verdict + PM review + final contract), but the INDEX must group them.
- `ecommerce-ds-architect-phase5-response.md` + `product-strategy-pm-phase5-review.md` — paired.
- `ecommerce-ds-architect-phase6a-final-review.md` + `product-strategy-pm-phase6a-final-review.md` + `phase6a-final-review.md` — three; the last is likely the reconciled output.
- `legacy-vs-v2-final-recommendation.md` + `ecommerce-ds-architect-legacy-vs-v2-response.md` + `product-strategy-pm-legacy-vs-v2-review.md` — three on legacy-vs-v2.
- `play-lifecycle-discussion-reconciled.md` + `ecommerce-ds-architect-play-lifecycle-discussion.md` + `product-strategy-pm-play-lifecycle-discussion.md` — three.
- `synthetic-phase5-e2e-final-review.md` + `ecommerce-ds-architect-synthetic-phase5-e2e-review.md` + `product-strategy-pm-synthetic-phase5-e2e-review.md` — three.

Pattern: ~6 multi-agent topics each have 3 files (DS + PM + reconciled). All intentional, but the INDEX must show them as topic-groups.

**Verdict: FLAG.** The audit's pattern-glob plan for INDEX generation will systematically miss the 11 orphans and obscure the 6 reconciliation topic-groups. The Phase 1 INDEX build must be hand-classified for the first pass, then a script can maintain it.

---

## Gate 5 — CLAUDE.md handoff references that will break

CLAUDE.md L27-46 names the following docs as "MUST" reads for every dispatch:

| Reference | Migration target |
|---|---|
| `ARCHITECTURE_PLAN.md` (L31, including LOAD-BEARING UPDATE blocks) | **ARCHIVED** per revised plan |
| `memory.md` (L32) | **KEPT** (template-trimmed) |
| `memory_archive.md` (L32) | **KEPT** (cold-storage rollover) |
| `KNOWN_ISSUES.md` (L33) | **KEPT** |
| `agent_outputs/*-summary.md` (L34) | **KEPT** + new INDEX.md |
| `agent_outputs/implementation-manager-s7_6-observed-effect-wiring-plan.md` (L35) | **KEPT** (specific file path) |

**Issues:**

1. **ARCHITECTURE_PLAN.md archival breaks L31.** CLAUDE.md L31 mandates reading ARCHITECTURE_PLAN.md "start-to-finish, including all LOAD-BEARING UPDATE blocks ... Part III-1 priors validation reframe, Part IV Store Profile Layer, and the 2026-05-22 amendment locking the single-demote-channel invariant." All three referenced sections are load-bearing for current code (the 2026-05-22 amendment is cited in 5 src/ files: `decide.py:2209,2479`, `guardrails.py:973`, `main.py:1618`). If ARCHITECTURE_PLAN.md moves out of the active read path, those code citations point at archived content. **The migration MUST replace L27-46 with pointers to the new docs that take over each function** (PRODUCT.md / STATE.md / PIVOTS.md / ROADMAP.md / memory.md / KNOWN_ISSUES.md / INDEX.md).

2. **The "load-bearing single-demote-channel invariant" needs a new home.** It's referenced in 5 src/ files and is the kind of architectural invariant that PIVOTS.md is designed to carry. The audit's revised PIVOTS.md scope ("6-8 belief-changing moments") explicitly lists it, so this is handled — but the citations in src/ comments will then point at archived ARCHITECTURE_PLAN.md text. Two options: (a) update the 5 src/ comments in the migration commit to cite `PIVOTS.md`; (b) leave the comments pointing at the archive location and add a redirect note at the top of the archived ARCHITECTURE_PLAN.md.

3. **L35 (`agent_outputs/implementation-manager-s7_6-observed-effect-wiring-plan.md`)** — specific file path, unaffected by archival.

4. **No orphan references in CLAUDE.md** beyond the ARCHITECTURE_PLAN.md issue.

**Verdict: FLAG.** Two blocking items for Phase 1:
- Rewrite CLAUDE.md Subagent Handoff Discipline section (L27-46) to point at the new active read path. This is a single commit and must land atomically with the doc moves.
- Decide whether the 5 src/ comments citing `ARCHITECTURE_PLAN.md` are updated in the migration commit or remain as historical citations to the archived doc. Founder's nothing-gets-lost constraint suggests an archive header redirect is safer than mass-rewriting code comments.

---

## Gate 6 — Subagent prompts that reference docs

**.claude/agents/** contents:
- `code-refactor-engineer.md`
- `ecommerce-ds-architect.md`
- `implementation-manager.md`
- `product-strategy-pm.md`
- `skeptic-red-team-reviewer.md`
- `statistical-code-reviewer.md`

Grep for `architecture_plan|memory\.md|memory_archive|engine\.md|engine_overview|known_issues|agent_outputs|decisions\.md|claude\.md` across all six files: **zero matches.**

The subagent prompts do not name specific doc files. The Subagent Handoff Discipline content lives only in CLAUDE.md (which is consulted by Claude Code, not embedded in the subagent prompts).

**Verdict: PASS.** No subagent prompt updates required in the migration commit.

---

## Gate 7 — Tests / code references to doc files

**Code references to doc filenames** (grep `ARCHITECTURE_PLAN|memory_archive|ENGINE_OVERVIEW|KNOWN_ISSUES\.md|ENGINE\.md` in src/, tests/, config/):

| File | Line | Reference |
|---|---|---|
| `src/priors_loader.py` | 96 | ARCHITECTURE_PLAN.md Part III-1 §III-1 Step 1 |
| `src/engine_run.py` | 307,308,334 | ENGINE_OVERVIEW.md §8, ARCHITECTURE_PLAN.md Part I §A |
| `src/action_engine.py` | 2833,2850 | ENGINE.md tier assignment |
| `src/decide.py` | 2209,2479 | ARCHITECTURE_PLAN.md 2026-05-22 single-demote-channel invariant |
| `src/measurement_builder.py` | 1297 | ARCHITECTURE_PLAN.md §III B-3:244-246 |
| `src/guardrails.py` | 973 | ARCHITECTURE_PLAN.md 2026-05-22 single-demote-channel invariant |
| `src/utils.py` | 538,943 | ARCHITECTURE_PLAN.md Part III-1, :248-257 |
| `src/main.py` | 1618 | ARCHITECTURE_PLAN.md 2026-05-22 single-demote-channel |
| `src/audience_builders.py` | 197,993,1014,1043 | ARCHITECTURE_PLAN.md Part I §B-1, :248, :249/254, :254 |
| `src/sizing.py` | 71 | ARCHITECTURE_PLAN.md Part III-1 §III-1 |
| `tests/test_s8_t1_evidence_source_chip.py` | 13,83 | ENGINE_OVERVIEW.md §8, ARCHITECTURE_PLAN.md Part I §A |
| `tests/test_s6_t3_z_considered_render.py` | 306 | ARCHITECTURE_PLAN.md §III B-5 |
| `tests/test_slate_regression_supplements_brand.py` | 13,110,285 | KNOWN_ISSUES.md, ARCHITECTURE_PLAN.md §III B-5 |
| `tests/test_s7_5_t1_priors_validation_fields.py` | 9 | ARCHITECTURE_PLAN.md Part III-1 §III-1 Step 1 |
| `tests/test_s6_t1_5_winback_dormant_repin.py` | 47 | ARCHITECTURE_PLAN.md §III B-5 |
| `tests/test_determinism_cross_run.py` | 35 | CLAUDE.md / ENGINE.md |

**Count: 18 code/test files contain ARCHITECTURE_PLAN.md citations**, 3 contain ENGINE.md, 3 contain ENGINE_OVERVIEW.md, 1 contains KNOWN_ISSUES.md.

None are runtime-load references (no `open("ARCHITECTURE_PLAN.md")`); all are comments / docstrings citing line numbers and section paths.

**Risk:** when ARCHITECTURE_PLAN.md archives, line numbers in these comments become brittle (the archived file is frozen but the comments still claim line numbers that mean nothing if the reader can't easily find the archived doc). The audit revises to keep ARCHITECTURE_PLAN.md in `agent_outputs/` or archive root — those line numbers stay accurate, just one click away.

**Verdict: FLAG.** Add an explicit redirect header to the archived ARCHITECTURE_PLAN.md naming its new path (e.g., `docs/archive/ARCHITECTURE_PLAN.md`) and noting that line-number citations in src/tests still apply (file is frozen). No code/test rewrites required.

---

## Phase 0 Summary

**Light: YELLOW.**

Migration is mostly safe — the Revisions section's "keep memory.md trimmed" call removes the biggest risk (D-1..D-8 displacement). KI sync is clean. Subagent prompts are untouched. Code/test citations are all comments, not runtime loads.

**Blocking items that must be resolved before Phase 1 starts:**

1. **(Gate 1)** Document in `docs/DECISIONS.md` L13 (or its successor) the exact anchor where D-1..D-8 live in trimmed memory.md. Pin a test that asserts the `# Founder Decisions` block exists in memory.md (the retroactive-trim lint must NOT remove it).
2. **(Gate 3)** Founder calls on `docs/engine_flags.md` (add to keep list), `PILOT_UPLOAD_GUIDE.md` (current or stale?), `onboarding-optimization-guide.md` (vestigial?).
3. **(Gate 4)** First INDEX build must be hand-classified, not glob-driven, to capture the 11 orphan filenames and 6 reconciliation topic-groups.
4. **(Gate 5)** Rewrite CLAUDE.md L27-46 atomically with the doc moves. Decide whether the 5 src/ comments citing `ARCHITECTURE_PLAN.md 2026-05-22` get updated in the same commit or stay pointing at the archive (recommend: archive-header redirect, no code rewrites).
5. **(Gate 7)** Add an archive-header redirect at top of archived ARCHITECTURE_PLAN.md naming its new path and noting that line-number citations in 18 src/test files remain accurate.

**Non-blocking observations:**

- KI registry is in good shape (Gate 2).
- Subagent prompts need no edits (Gate 6).
- ENGINE.md and ENGINE_OVERVIEW.md are referenced by code but neither is in the audit's keep list nor explicitly archived. **Founder should confirm whether these are folded into STATE.md / PRODUCT.md content, or also archived alongside ARCHITECTURE_PLAN.md.** Currently 4 src/test files cite them (engine_run.py x3, action_engine.py x2, tests x4).

**Recommendation.** Resolve the five blocking items in a single pre-Phase-1 founder review (~30 min), then Phase 1 can proceed when "Sprint 8 first ticket lands" per the audit's migration trigger (L307).
