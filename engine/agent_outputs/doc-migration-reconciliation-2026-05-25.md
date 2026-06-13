# Doc-Migration Reconciliation Pass — 2026-05-25

*Step 2 of the three-step minimum corrective. Read-only verification across the 7 drafts. No fixes applied — report only.*

---

## Inline summary (≤300 words)

Five Phase-1 drafts (PRODUCT, STATE, PIVOTS, ROADMAP) plus three Phase-1-prep drafts (CLAUDE-md, INDEX, memory-trim-plan) were cross-referenced against `memory.md` L173–182 (D-1..D-8), `KNOWN_ISSUES.md` (KI inventory), `docs/engine_flags.md` (flag SoT), and current `CLAUDE.md`. Most identifiers (D-1..D-8 founder decisions, sprint chronology S6..S8, pivot inventory, KI-1..KI-5 Phase 9 entry conditions) reconcile cleanly across drafts. The Stop-Coding Line, single-demote-channel invariant, pseudo_N {30,15,10} lock, evidence-tier vocabulary, four-lane slate caps, and S10–S13 ML beta-blocking framing are all internally consistent.

**Four FIX-BEFORE-CUTOVER items found, all in `draft-ROADMAP-2026-05-25.md` and `draft-STATE-2026-05-25.md`:**

1. **ROADMAP §3 carry-forward L54 + §6 pointer L112** lump `KI-NEW-L/M/N` under "S9 post-beta structural cleanup", contradicting memory.md L1921 (the canonical L1921 KI-NEW-L→S13.5 / KI-NEW-M/N→S14-T3 sequencing the founder context explicitly load-bears). The same paragraph at L54 contains both claims — internal contradiction within one bullet.
2. **ROADMAP §6 source list L131** still mentions `KI-NEW-L/M/N/P/Q` — P and Q were stricken in the fix-list pass; this is a stale leftover.
3. **ROADMAP §4 deferral L73** says "no retention limits today (per D-1 forever-retention)". D-1 is the `audience_definition_version` policy. Forever-retention is D-2. Same draft cites D-2 correctly at L96 — internal contradiction.
4. **STATE §6 L123** says `docs/engine_flags.md "Last updated: 2026-05-03" predates S6/S7/...` — the live file at `docs/engine_flags.md` L3 actually reads "Last updated: 2026-05-25 (post-S8 close...)". The premise STATE asserts is false; the "needs its own refresh" caveat is stale.

Two OK-FOR-FOLLOW-UP items (INDEX draft count off-by-three; trim-plan `docs/DECISIONS.md` line citation not independently verified) are non-load-bearing.

---

## Cross-reference table

| Identifier | Appears in | Consistent across all mentions? | Action |
|---|---|---|---|
| **D-1** (`audience_definition_version`) | PRODUCT:91; ROADMAP:73 ("per D-1 forever-retention"); memory-trim-plan:21,60-70,150,159,177 | **NO**. PRODUCT:91 verbatim from memory.md L173 ("audience_definition_version policy..."). ROADMAP:73 attributes "forever-retention" to D-1, which is D-2's content (memory.md L174). Quote ROADMAP:73 verbatim: "No retention limits today (per D-1 forever-retention). AWS migration time." Quote memory.md L173: "**D-1** — `audience_definition_version` policy." | **FIX-BEFORE-CUTOVER** — change ROADMAP:73 D-1→D-2. |
| **D-2** (retention forever) | PRODUCT:92,116; ROADMAP:96 ("Privacy posture per D-2") | YES across PRODUCT + ROADMAP:96 (correctly cites D-2). | KEEP (independent of #1 above). |
| **D-3..D-4** | PRODUCT:93-94 | YES (verbatim from memory.md L175-176). | KEEP. |
| **D-5** (manual JSON import) | PRODUCT:28,95,126; STATE:192; ROADMAP:66,100; PIVOTS:n/a | YES across all 6 mentions. | KEEP. |
| **D-6** (ML banned use-cases) | PRODUCT:96,123; ROADMAP:93 ("D-6 carve-out"); | YES. | KEEP. |
| **D-7** (I-1 affinity deferred) | PRODUCT:97; PIVOTS:99; INDEX:174 | YES — all cite as a deferral pointer. | KEEP. |
| **D-8** (vertical scope locked) | PRODUCT:98,122; ROADMAP:82; STATE:n/a | YES — `{beauty, supplements, mixed}`, `mixed` literal-blend not fallback. | KEEP. |
| **D-1..D-8 block** (verbatim) | PRODUCT:91-98 (full); memory-trim-plan:21,60-70 (exemption) | YES — PRODUCT block is verbatim copy of memory.md L173-180. trim-plan exempts it. | KEEP. |
| **S6** | INDEX:33,96-106; STATE (implicit via S8 lineage); ROADMAP:31 (S6–S14 plan ref) | YES (historical refs only). | KEEP. |
| **S6.5** | INDEX:87-94 | YES. | KEEP. |
| **S7 / S7.5 / S7.6** | INDEX:47-86; STATE:§5 invariants 1-3 cite S7.6 + S7.5; PIVOTS Pivot 3/4/5/6/7; ROADMAP:48 (S7.5 contract); CLAUDE-md:57 (T7.5 spiral) | YES — all historical references to closed sprints. | KEEP. |
| **S8** | ROADMAP:13-19 ("S8 just closed"); STATE:passim ("post-S8"); INDEX:31-46; PIVOTS:n/a; memory-trim-plan:11,88-92 | YES — all drafts agree S8 closed 2026-05-25 with the 3 listed shipped items (evidence_source chip + sensitivity + provenance, EB blend layer, Play Library wave 1). | KEEP. |
| **S9** | ROADMAP:13,29,35,53-54,112,117,133; STATE:n/a; INDEX:20 ("Sprint 9 not yet started"); PIVOTS:88 | **NO** — internal to ROADMAP. ROADMAP:35 row says S9 = "post-beta lifecycle/cleanup (deferred)" (correct, matches founder context). ROADMAP:54 says "**KI-NEW-L / M / N — post-beta (S9).** Collapse 5 V2 prior-anchored injection blocks..." then in the same bullet adds "KI-NEW-L stays at S13.5 per memory.md L1921 commitment". Quote: "KI-NEW-L / M / N — post-beta (S9). Collapse 5 V2 prior-anchored injection blocks at `src/main.py:1380-1597`; typed-code priority policy for `_dedupe_rejections`; experiment-promotion provenance preserve. KI-NEW-L stays at S13.5..." memory.md L1921 verbatim: "KI-NEW-L → S13.5 (between S13-T4 atomic flip and S14-T1 dispatch); KI-NEW-M/N → S14-T3 beta-merchant feedback resolution window". ROADMAP:112 also repeats "KI-NEW-L/M/N = S9 post-beta structural cleanup". | **FIX-BEFORE-CUTOVER** — ROADMAP:54 and :112 must reflect L→S13.5, M/N→S14-driven (NOT S9). |
| **S10 / S11 / S12 / S13** | ROADMAP:20,29,33-39,42,44,56; STATE:73,145,149,190,195; PRODUCT:79; PIVOTS:89 | YES — all drafts agree S10-S13 = ML predictive layer, beta-blocking, ML lives in AUDIENCE step, no plays added. | KEEP. |
| **S13.5** | ROADMAP:54 (KI-NEW-L); STATE:165,196; INDEX:40 | YES — all agree KI-NEW-L collapses at S13.5 between S13-T4 and S14-T1. (S13.5 reference at ROADMAP:54 is correct; the contradictory framing is elsewhere in same bullet — see S9 row.) | KEEP. |
| **S14** | ROADMAP:31,40,54; STATE:149; INDEX:40 | YES — private-beta launch at S14, gated by S10-S13 ML. | KEEP. |
| **S15+** | ROADMAP:17,52,60 | YES (Phase 9 + EB-blend payoff deferred to S15+). | KEEP. |
| **KI-1..KI-5** (Phase 9 entry conditions) | ROADMAP:64,112 | YES. | KEEP. |
| **KI-7** | PRODUCT:140 | YES (single mention, citation to KNOWN_ISSUES.md L68-73). | KEEP. |
| **KI-13** | n/a in drafts | N/A. | KEEP. |
| **KI-NEW-G** (`replenishment_due` dormancy) | STATE:119,136 | YES — "honest dormancy preserved, RESOLVED-AS-DOCUMENTED". Matches KNOWN_ISSUES.md L358. | KEEP. |
| **KI-NEW-J** | n/a in drafts (memory.md only) | N/A. | KEEP. |
| **KI-NEW-K** (Beta envelope re-fit) | STATE:147 (implicit via Beauty Beta re-fit S8-T0); INDEX:39 | YES — RESOLVED in S8-T0 per memory.md L1822-1844. | KEEP. |
| **KI-NEW-L** | ROADMAP:35,53-54,112,131; STATE:165,196; INDEX:n/a | NO — see S9 row. ROADMAP gives two different sprint anchors in same bullet (S9 vs S13.5). STATE correctly anchors L at S13.5 (lines 165, 196). | **FIX-BEFORE-CUTOVER** (rolled up under S9 row). |
| **KI-NEW-M / KI-NEW-N** | ROADMAP:35,54,112 | NO — ROADMAP groups with L under S9. Per memory.md L1921: "M/N → S14-driven resolution window". | **FIX-BEFORE-CUTOVER** (rolled up under S9 row). |
| **KI-NEW-O** | n/a in drafts | N/A. | KEEP. |
| **KI-NEW-P / KI-NEW-Q** | ROADMAP:131 (cite list: "KI-NEW-L/M/N/P/Q") | **NO** — P and Q were stricken per the fix-list pass; KNOWN_ISSUES.md inventory ends at KI-NEW-O (L445). Quote ROADMAP:131: "`KNOWN_ISSUES.md` for KI-NEW-L/M/N/P/Q and Phase 9 entry conditions (KI-1..KI-5)." | **FIX-BEFORE-CUTOVER** — drop P/Q from this citation. |
| **KI-30** | ROADMAP:40 | YES (single mention, "KI-30-class fixes" at S14). | KEEP. |
| **`PRODUCT.md`** (active doc) | CLAUDE-md Doc Map L21; INDEX:174,176; ROADMAP:115; STATE:n/a | YES. | KEEP. |
| **`STATE.md`** | CLAUDE-md L22,40,56; INDEX:182,183; ROADMAP:7,114; PIVOTS:6 | YES. | KEEP. |
| **`PIVOTS.md`** | CLAUDE-md L23,40,56; INDEX:175,176,183; ROADMAP:7,113; PRODUCT:n/a (sources only); CLAUDE-md L68 ("documented in PIVOTS.md") | YES. | KEEP. |
| **`ROADMAP.md`** | CLAUDE-md L24,56; INDEX:181,184; STATE:6,186; PIVOTS:3,10 | YES. | KEEP. |
| **`memory.md`** | CLAUDE-md L25,29,34; INDEX:45; PRODUCT:89,136,137; ROADMAP:54,132; PIVOTS:passim; STATE:n/a; memory-trim-plan:passim | YES — chronology stream + Founder Decisions L173-182 + L1921 KI sequencing. | KEEP. |
| **`KNOWN_ISSUES.md`** | CLAUDE-md L27,55; INDEX:passim; PRODUCT:140; ROADMAP:7,112,131; STATE:n/a | YES (modulo P/Q stale ref above). | KEEP. |
| **`docs/engine_flags.md`** | CLAUDE-md L28; STATE:111,123,211 | **NO** — STATE:123 verbatim: `**Note:** docs/engine_flags.md "Last updated: 2026-05-03" predates S6/S7/S7.5/S7.6/S8 — it needs its own refresh before STATE.md's reference to it is fully accurate. Flagged as a follow-up doc task.` Actual `docs/engine_flags.md` L3 verbatim: `_Last updated: 2026-05-25 (post-S8 close — covers S6, S6.5, S7, S7.5, S7.6, S8)_`. Note's premise is false. | **FIX-BEFORE-CUTOVER** — remove or rewrite the STATE:123 note. |
| **`docs/DECISIONS.md`** | CLAUDE-md L29; STATE:91,212; memory-trim-plan:66 | YES across STATE + CLAUDE-md (both treat as cross-ref repository for pseudo_N lock + D-1..D-8 pointer). trim-plan:66 cites "L13" without independent verification but assertion (delegates D-1..D-8 OUT to memory.md) is consistent with how STATE + CLAUDE-md treat the relationship. | KEEP. |
| **`agent_outputs/INDEX.md`** | CLAUDE-md L30,55,68 (sign-off destination); INDEX (self) | YES — CLAUDE-md draft consistently references INDEX as the verdicts/closeouts pointer. | KEEP. |
| **`agent_outputs/code-refactor-engineer-<ticket>-summary.md`** | CLAUDE-md L26,34; memory-trim-plan:passim | YES. | KEEP. |
| **`ARCHITECTURE_PLAN.md`** | CLAUDE-md (absent from Doc Map by design — replaced by STATE/PIVOTS/ROADMAP); PIVOTS:113; PRODUCT:135; ROADMAP:5,79,130 | YES — all drafts treat ARCHITECTURE_PLAN.md as the predecessor doc being replaced by ROADMAP §1-2 + PIVOTS + STATE. | KEEP. |
| **`ENGINE.md` / `ENGINE_OVERVIEW.md`** | CLAUDE-md L39 ("ENGINE.md is retired"); PRODUCT:134; STATE:203; ROADMAP:31,125; PIVOTS:114 | YES — all drafts treat ENGINE.md as retired (moved to `docs/legacy/`); ENGINE_OVERVIEW.md cited as a current historical source where needed. | KEEP. |
| **INDEX draft-count footer** | INDEX L4 ("4 active doc-migration drafts"); L26-28 (lists PRODUCT, STATE, PIVOTS, ROADMAP only) | NO — actual in-scope drafts are 7 (also CLAUDE-md, INDEX self, memory-trim-plan) plus 2 audit files at §1 (doc-audit, phase0-gates). Either count off, or list incomplete. Non-load-bearing for engine state. | **OK-FOR-FOLLOW-UP**. |

---

## Conclusion

**Four FIX-BEFORE-CUTOVER items** (all in ROADMAP + one in STATE):

1. ROADMAP:73 — `D-1` → `D-2` in "per D-1 forever-retention".
2. ROADMAP:54 + ROADMAP:112 — KI-NEW-L/M/N attribution to "S9" contradicts memory.md L1921 (canonical: L→S13.5, M/N→S14-driven). The contradiction also exists inside the ROADMAP:54 bullet itself.
3. ROADMAP:131 — stale `KI-NEW-L/M/N/P/Q` citation; P/Q were stricken per the just-landed fix-list pass.
4. STATE:123 — `docs/engine_flags.md "Last updated: 2026-05-03"` claim is false; live file reads 2026-05-25.

**One OK-FOR-FOLLOW-UP item:** INDEX:4 draft count vs. INDEX:26-28 list mismatch (4 vs. actual 7 drafts in-scope). Non-load-bearing; INDEX will regenerate at cutover anyway.

All other identifiers (8 D-decisions × 7 drafts, ~30 sprint references, ~10 KI IDs in active drafts, 11 doc-map files) reconcile cleanly. Stop-Coding Line, single-demote-channel invariant, four-lane slate, three orthogonal gates, evidence-tier chip vocabulary, pseudo_N {30,15,10} lock, ML-as-audience-ranking framing, S10-S13 beta-blocking sequence, S14 private-beta gate, S15+ post-beta deferrals — all internally consistent across the 7 drafts.

Recommend founder review of the four FIX-BEFORE-CUTOVER items above and choose:
- **(a)** tight fix-list dispatch for just those four edits (estimated ≤30 min — all are 1–3 line edits in ROADMAP/STATE), OR
- **(b)** accept and proceed (especially viable for #4 — STATE's stale-flag note is a self-flagged caveat already).

*End of reconciliation pass.*
