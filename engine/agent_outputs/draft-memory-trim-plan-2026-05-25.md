# memory.md — Retroactive Trim Plan

*Draft for founder review. This document is a plan; it does not perform the trim.*
*Author: doc-migration Phase 1 prep, 2026-05-25.*

---

## 1. Scope

- Current `memory.md`: **1,935 lines** (per `wc -l`; the audit at 1,820 lines is one sprint stale).
- Entry count (`^## ` markers): **~58 entries** spanning M0/M9 reconciled-direction → S8 close cleanup (2026-05-25).
- Entry-size distribution (sampled by header offsets): the template cap is **≤15 lines per ticket**; observed entries routinely run 30–90 lines, with the worst offenders (S6-T3, Sprint 6.5 T4/T5, S7.6 close, S7.6 continuation, S8-T2..T4.5) at 60–110+ lines.
- The non-entry preamble (file purpose, template, intro) at L1–40, the Decision Core Phase 1 reconciled direction at L42–73, the M0–M9 milestone wall at L77–103, the Phase 5 paragraph at L107–122, the Phase 6A wall at L124–142, the Phase 6B wall at L146–166, and the **Founder Decisions block at L169–182** are NOT per-ticket entries and are excluded from template-shape trim.

**Post-trim target.**

| Block | Before | After | Notes |
|---|---|---|---|
| Preamble + how-to-use | ~40 | ~40 | Unchanged. |
| Decision Core / M0–M9 / Phase 5 / Phase 6A / Phase 6B summary sections | ~120 | ~120 | Already narrative-summary shaped, not per-ticket; leave as-is. |
| Founder Decisions D-1..D-8 + storage backend note | 14 | 14 | **Exempt from trim — verbatim preservation required.** |
| Per-ticket entries (S-1 → S8 close, ~50 entries) | ~1,750 | ~50 × 13 = **~650** | Apply template envelope. |
| **Total** | **~1,935** | **~825** | Roughly 57% reduction; 1,100 lines pushed to per-ticket summary files. |

Target post-trim memory.md is **800–900 lines**. Chronology stream remains intact; receipt detail moves to its canonical home.

---

## 2. Trim methodology — what stays, what moves

The template at L20–36 defines six required fields. Apply them ruthlessly.

**Keep in `memory.md` (per entry):**

1. Header line: `## <Ticket-ID> — <one-line scope> (YYYY-MM-DD)` — exactly as today.
2. **Shipped:** 2–3 bullets, what's now true that wasn't before. ≤ 4 lines total.
3. **Load-bearing invariants:** the 1–3 must-not-break rules a future agent needs at-a-glance. ≤ 4 lines.
4. **Caveats / dormant behavior:** one sentence.
5. **Schema:** one-word status (`unchanged | event_version=1 additive | user_version bump N→M`).
6. **Suite:** one line — `N passed (was M)`.
7. **Summary:** link to `agent_outputs/code-refactor-engineer-<ticket>-summary.md`.

Total: 12–15 lines per entry. Hard cap 20 lines (lint threshold).

**Move to summary file (per entry):**

- File-change tables (which file gained which function on which line).
- Per-test-suite pass counts.
- Implementation notes / branch shape / merge order.
- Risk paragraphs, sensitivity analyses, debug instrumentation transcripts.
- Commit hashes (git log carries these natively).
- "Key learnings" prose blocks.
- DS verdict transcripts inlined into closeouts (these should be a *link* to the DS verdict file, not a copy).
- Sprint-wide retrospectives (the closing entries like "S7.6 — sprint discipline" and "S7.6 sprint close" carry hundreds of lines of retro — these go to a sprint-level summary file `code-refactor-engineer-s7_6-close-summary.md`).

**Inline link replacing the moved content:** the `**Summary:**` field already points at the summary file. Trim leaves that pointer as the only handle to the verbose content.

---

## 3. D-1..D-8 exemption (load-bearing boundary)

**Lines L169–182 of memory.md are EXEMPT from trim.** This boundary is non-negotiable per the Phase 0 gate audit:

- The block carries the canonical text of D-1..D-8 plus the 2026-05-10 storage backend addendum.
- It is referenced 50+ times across `src/`, `tests/`, `docs/`, `KNOWN_ISSUES.md`, and `agent_outputs/`.
- `docs/DECISIONS.md` L13 explicitly delegates D-1..D-8 OUT of itself and points back to memory.md.

**Mechanical guard:** the pre-commit lint (§5 below) MUST recognize the `# Founder Decisions (2026-05-09)` header as exempt — entries under that section are not per-ticket entries, the 20-line cap does not apply, and the trim pass must not touch them.

**Belt-and-braces test:** add `tests/test_memory_founder_decisions_block_present.py` asserting that the literal strings `**D-1**`, `**D-2**`, … `**D-8**` plus `Storage backend note (founder, 2026-05-10)` all appear in `memory.md` after any commit. This catches accidental deletion regardless of how the trim is performed.

---

## 4. Entries that need a new summary file BEFORE trim can land safely

Spot-check of recent entries against the existing `agent_outputs/code-refactor-engineer-*-summary.md` inventory:

| memory.md entry | Existing summary file? | Action before trim |
|---|---|---|
| S7.6-T1.5 (winback observed-effect) | not located by `s7_6-t1` glob | **Write `code-refactor-engineer-s7_6-t1_5-summary.md`** carrying current memory.md L1549–1572 content. |
| S7.6-T2 (replenishment_due wiring partial) | not located | **Write `code-refactor-engineer-s7_6-t2-summary.md`** carrying L1573–1596. |
| S7.6 sprint discipline (predict-observed_n-first rule) | conceptual / not located | **Write `code-refactor-engineer-s7_6-discipline-summary.md`** capturing the rule + the 3-failed-predictions retro now in memory.md L1597–1614. |
| S7.6 synthetic-fixture philosophy | partially in `code-refactor-engineer-s7_6-t2_5-deferred-summary.md` | Verify coverage; if synthetic-fixture honesty rule prose isn't captured, write `code-refactor-engineer-s7_6-fixture-philosophy-summary.md`. |
| S7.6-C3 sprint close (L1645–1709) | not located as a single sprint-close summary | **Write `code-refactor-engineer-s7_6-close-summary.md`.** |
| S7.6-continuation sprint close (L1710–1790) | not located | **Write `code-refactor-engineer-s7_6-continuation-close-summary.md`.** |
| S7.6-CLI-FIX (L1791–1810) | not located | **Write `code-refactor-engineer-s7_6-cli-fix-summary.md`** (or fold into the close summary above). |
| S7.6-cleanup (probe archive, L1811–1821) | trivial | Fold one-liner into the cleanup commit message; no summary file needed. |
| S8-T0 KI-NEW-K envelope re-fit (L1822–1844) | not located | **Write `code-refactor-engineer-s8-t0-summary.md`.** |
| S8 Q3/Q6/Q7 verdict ack (L1845–1865) | DS verdict exists (`ecommerce-ds-architect-s8-q3-q6-q7-verdict-2026-05-24.md`) | memory.md entry should reference the verdict file; no new summary required. |
| S8-T1 + T1.6 + T1.5 trio (L1866–1889) | not located as a single rolled-up summary | **Write `code-refactor-engineer-s8-t1-trio-summary.md`.** |
| S8 cleanup (L1890–1895) | trivial | Fold into commit message. |
| S8-T2 + T2.5 + T3 + T3.5 + T4 + T4.5 close (L1896–1930) | not located | **Write `code-refactor-engineer-s8-close-summary.md`** carrying the rolled-up six-ticket receipt. |
| S8-close cleanup (L1931–end) | trivial | Fold. |

**Net new summary files to author before trim: 8 substantive + 4 trivial fold-ins.** Estimated 30–45 min per substantive summary (most of the content already exists in memory.md and is just being relocated). Total: **4–6 hours of new-summary authoring** before trim can run safely.

For older entries (M0–M9, Phase 5/6A/6B, S1–S7): the inventory in §2 of `agent_outputs/INDEX.md` confirms summary files exist for every per-ticket M0–M9, Phase 5, Phase 6A B1–B6, Phase 6B C1–C4, S1–S7 ticket. Older trims are net-safe; only the S7.6 / S8 tail above needs new summaries.

---

## 5. Pre-commit lint design

**The constraint to enforce:** a per-ticket entry — defined as content between two `^## ` markers anywhere below the `# Founder Decisions (2026-05-09)` exemption boundary — does not exceed 20 lines, blank lines inclusive.

**Recommended check shape (Python, runnable both as a `pytest` test and as a Git hook):**

```python
# tests/test_memory_md_template_shape.py
import re, pathlib

MAX_LINES_PER_ENTRY = 20
EXEMPT_SECTIONS = {
    "Founder Decisions (2026-05-09)",
    "How to use this file",
    "Accepted diagnosis",
    "Architecture",
    "Load-bearing invariants (must hold across V2)",
    "Permanently out of scope (Phase 1)",
    "STOP-CODING LINE (load-bearing for all future work)",
    "Engineer A track",
    "Engineer B track",
}

def test_memory_md_entries_under_template_cap():
    text = pathlib.Path("memory.md").read_text().splitlines()
    # Split on ^## headers, locate offsets
    headers = [(i, text[i][3:].strip()) for i, line in enumerate(text) if line.startswith("## ")]
    headers.append((len(text), "EOF"))
    violations = []
    for (start, title), (end, _) in zip(headers, headers[1:]):
        if any(title.startswith(s) for s in EXEMPT_SECTIONS):
            continue
        size = end - start
        if size > MAX_LINES_PER_ENTRY:
            violations.append(f"L{start+1} '{title}': {size} lines (max {MAX_LINES_PER_ENTRY})")
    assert not violations, "memory.md entries over template cap:\n" + "\n".join(violations)
```

**Where to wire it:**

**Recommendation: run as a `pytest` test executed in CI, NOT as a `.git/hooks/pre-commit` hook.**

Reasoning:
1. Git pre-commit hooks live in `.git/hooks/` which is not version-controlled. Engineers who clone fresh skip the check unless onboarding installs the hook (a `pre-commit` framework dance). Brittle.
2. `pytest` discovery picks the test up automatically; CI runs every PR; every contributor's local `pytest` run also catches it. Single enforcement surface.
3. The S7.6 spiral memo (CLAUDE.md L37–46) demonstrates that load-bearing rules belong in test files where they survive a Friday-night closeout. The `tests/test_v2_harness_cfg_gated_fields.py` pattern is precedent.
4. If a true "block the commit" experience is wanted, a one-line wrapper in `pre-commit-config.yaml` (the standardized framework, not raw `.git/hooks/`) can call the same pytest. Optional belt-and-braces, but the pytest is the canonical home.

**Two additional companion tests (cheap belt-and-braces):**
- `test_memory_founder_decisions_block_present.py` — D-1..D-8 string presence (§3 above).
- `test_memory_md_no_orphan_summary_links.py` — every `agent_outputs/code-refactor-engineer-...summary.md` path mentioned in memory.md resolves to an existing file.

---

## 6. Risk

| Risk | Impact | Mitigation |
|---|---|---|
| D-1..D-8 block silently truncated | 50+ code/test references point at memory.md; loss is catastrophic | §3 exemption + `test_memory_founder_decisions_block_present.py` |
| Verbose content moved to summary file diverges from the trimmed memory.md entry | Two-source drift over time | Trim is a *one-way* relocation — the verbose content already existed only in memory.md before trim; the summary file becomes the sole home. Lint blocks re-bloating memory.md. |
| Older summary files don't exist for some S7.6 / S8 entries | Trim deletes content that has no other home | §4 — author the 8 substantive summary files BEFORE the trim commit. |
| Cross-references from agent_outputs → memory.md line numbers go stale | Stale line numbers in DS verdicts citing "memory.md L693–820" | The DS verdicts citing memory.md by line number are themselves frozen historical docs; their line citations were already stale relative to each subsequent sprint. Migration adds no incremental harm. |
| Cross-references from code/tests → memory.md by D-N number | None — D-N strings remain stable (§3) | n/a |
| Pre-commit lint is too strict and rejects legitimate sprint-rollup entries (S6 close, S7.6 close) | Rollup entries naturally exceed 20 lines | Treat sprint-close rollups as a distinct shape: header `^## Sprint <N> — CLOSED` triggers a higher cap (e.g., 40 lines). Or push the rollup body into a sprint-summary file and keep only the close-headline in memory.md. Recommendation: latter — keeps the lint uniform. |
| Trim commit clobbers in-flight sprint work | Engineer mid-write loses content | Migration trigger (per audit L307) is "Sprint 8 first ticket lands" — already satisfied. Pick a quiet window between sprints. |
| Old memory.md anchor links (e.g., from `memory_archive.md`) break | Anchors are line-number free (Markdown anchors are header-text-based); they survive trim if headers are preserved | Trim preserves all `^## ` headers verbatim. Anchors stable. |

---

## 7. Effort estimate

| Step | Hours |
|---|---|
| Author 8 missing S7.6 / S8 summary files (§4) | 4–6 |
| Mechanical trim pass on ~50 per-ticket entries (memory.md) | 3–4 |
| Author the 3 lint tests (§5) and verify on a clone | 1–2 |
| Verify D-1..D-8 block intact + run full test suite + spot-check 5 random summary files for coverage | 1 |
| Founder review pass on trimmed memory.md (read top-to-bottom, sanity check) | 1 |
| **Total** | **10–14 hours** |

Recommend single focused session over 2 days: day 1 = summary-file authoring (4–6h), day 2 = trim + lint + verify (4–6h + founder review).

---

## 8. Sequencing (not part of plan, but required before trim runs)

1. Phase 0 founder calls land (5 flagged items from `doc-migration-phase0-gates-2026-05-25.md`).
2. Phase 1 draft docs (PRODUCT, STATE, PIVOTS, ROADMAP) land in active read path.
3. Phase 1 CLAUDE.md slim + INDEX.md land (this prep task's outputs).
4. Phase 1 summary-file backfill (§4 above).
5. Phase 1 pre-commit lint tests land (passing on the un-trimmed memory.md so they validate the harness, not the trim).
6. Phase 1 retroactive trim runs (one commit).
7. Verification dispatch — fresh subagent reads from the new docs only, succeeds at a representative task without consulting the archive.

*End of plan.*
