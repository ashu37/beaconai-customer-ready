#!/usr/bin/env python3
"""One-shot trim script for memory.md per founder-locked migration 2026-05-25.

Run once during the Phase 2 cutover commit, then delete (this file is archived
to scripts/archive/ as provenance only).

For each per-ticket entry exceeding the 20-line cap (excluding exemptions):
  1. Find the matching agent_outputs/code-refactor-engineer-*-summary.md file
     from the entry's `**Summary:**` link.
  2. Append the full original block to that summary file under a new
     `## Backfill from memory.md (migration trim 2026-05-25)` section.
  3. Rewrite the memory.md entry in template-shape form.

A missing summary file is reported, not force-trimmed; the entry stays
untouched.
"""
from __future__ import annotations

import pathlib
import re

REPO = pathlib.Path("/Users/atul.jena/Projects/Personal/beaconai")
MEM = REPO / "memory.md"
MAX_LINES = 20

EXEMPT_PREFIXES = (
    "How to use this file",
    "<Ticket-ID>",
    "Accepted diagnosis",
    "Architecture",
    "Load-bearing invariants",
    "Permanently out of scope",
    "STOP-CODING LINE",
    "Engineer A track",
    "Engineer B track",
    "Founder Decisions",
)
SPRINT_ROLLUP_RE = re.compile(
    r"^Sprint\s+\d+(\.\d+)?\b(?!\s+Ticket)(.*\bCLOSED\b|.*\brollup\b)"
)

SUMMARY_LINK_RE = re.compile(r"\*\*Summary:\*\*\s*\[.*?\]\((agent_outputs/[^)]+)\)")

# Explicit overrides: title -> agent_outputs/...summary.md relative path.
# Used when the entry has no `**Summary:**` link inside its body.
EXPLICIT_SUMMARY = {
    "S6-T1 closeout (2026-05-17)": "agent_outputs/code-refactor-engineer-s6-t1-summary.md",
    "Sprint 6.5 Ticket T4.x closeout (2026-05-18)": "agent_outputs/code-refactor-engineer-s6_5-t4-summary.md",
    "Sprint 6.5 Ticket T4.x.1 closeout (2026-05-18)": "agent_outputs/code-refactor-engineer-s6_5-t4-summary.md",
    "Sprint 6.5 Ticket T4.y.1 closeout (2026-05-18)": "agent_outputs/code-refactor-engineer-s6_5-t4-summary.md",
    "Sprint 6.5 Ticket T5 closeout (2026-05-18)": "agent_outputs/code-refactor-engineer-s6_5-t5-summary.md",
    "S7-T2 closeout — `cohort_journey_first_to_second` builder (2026-05-20)": "agent_outputs/code-refactor-engineer-s7-t2-summary.md",
    "S7.6-T1.5 — Winback observed-effect activation (2026-05-21)": "agent_outputs/code-refactor-engineer-s7_6-t1-summary.md",
    "S7.6 — Synthetic-fixture philosophy (load-bearing, 2026-05-22)": "agent_outputs/code-refactor-engineer-s7_6-c3-summary.md",
    "S7.6-C3 — Sprint 7.6 closed (2026-05-22)": "agent_outputs/code-refactor-engineer-s7_6-c3-summary.md",
    "S7.6-continuation — sprint close (2026-05-23)": "agent_outputs/code-refactor-engineer-s7_6-c3-summary.md",
    "S8-T0 — KI-NEW-K Beauty Beta envelope re-fit (2026-05-24)": "agent_outputs/code-refactor-engineer-s8-t0-summary.md",
    "S8 Q3/Q6/Q7 — DS verdict + founder ack: sprint shape locked (2026-05-24)": "agent_outputs/code-refactor-engineer-s8-t1-summary.md",
    "S8-T1 + T1.6 + T1.5 trio — EvidenceSourceChip live in production (2026-05-24)": "agent_outputs/code-refactor-engineer-s8-t1-summary.md",
    "S8-T2 + T2.5 + T3 + T3.5 + T4 + T4.5 — Sprint 8 CLOSE (2026-05-25)": "agent_outputs/code-refactor-engineer-s8-t4_5-summary.md",
}


def is_exempt(title: str) -> bool:
    if any(title.startswith(p) for p in EXEMPT_PREFIXES):
        return True
    if SPRINT_ROLLUP_RE.match(title):
        return True
    return False


def extract_field_block(body, field):
    pattern = re.compile(rf"^\*\*{re.escape(field)}:\*\*", re.IGNORECASE)
    start = None
    for i, ln in enumerate(body):
        if pattern.match(ln):
            start = i
            break
    if start is None:
        return []
    end = len(body)
    for j in range(start + 1, len(body)):
        if re.match(r"^\*\*[A-Z][A-Za-z /_-]+:\*\*", body[j]):
            end = j
            break
    return body[start:end]


def split_entries(lines):
    headers = [(i, lines[i][3:].strip()) for i, line in enumerate(lines) if line.startswith("## ")]
    headers.append((len(lines), "__EOF__"))
    for (start, title), (end, _) in zip(headers, headers[1:]):
        yield start, title, end


def find_summary_path(body_lines):
    for ln in body_lines:
        m = SUMMARY_LINK_RE.search(ln)
        if m:
            return REPO / m.group(1)
    return None


def make_short_block(title, body, summary_link):
    def first_n_bullets(field, n):
        block = extract_field_block(body, field)
        if not block:
            return []
        out = [block[0].rstrip()]
        bullet_count = 0
        for ln in block[1:]:
            s = ln.rstrip()
            if not s:
                continue
            if s.startswith("- ") and bullet_count < n:
                if len(s) > 240:
                    s = s[:237].rstrip() + "..."
                out.append(s)
                bullet_count += 1
                if bullet_count >= n:
                    break
            elif not s.startswith("- ") and bullet_count == 0:
                if len(s) > 240:
                    s = s[:237].rstrip() + "..."
                out.append(s)
                break
        return out

    def field_one_line(field):
        block = extract_field_block(body, field)
        if not block:
            return None
        joined = " ".join(ln.strip() for ln in block if ln.strip())
        if len(joined) > 280:
            joined = joined[:277].rstrip() + "..."
        return joined

    parts = [f"## {title}", ""]
    shipped = first_n_bullets("Shipped", 2)
    if shipped:
        parts.extend(shipped)
        parts.append("")
    invariants = first_n_bullets("Load-bearing invariants", 2)
    if invariants:
        parts.extend(invariants)
        parts.append("")
    caveats = (
        field_one_line("Caveats / dormant behavior")
        or field_one_line("Caveats / next milestones")
        or field_one_line("Caveats")
    )
    if caveats:
        parts.append(caveats)
        parts.append("")
    schema = field_one_line("Schema")
    if schema:
        parts.append(schema)
    suite = field_one_line("Suite")
    if suite:
        parts.append(suite)
    parts.append(
        f"**Summary:** [{summary_link}]({summary_link}) — full receipt in summary file under `## Backfill from memory.md (migration trim 2026-05-25)`."
    )
    parts.append("")
    return parts


def main():
    text = MEM.read_text()
    lines = text.splitlines()
    entries = list(split_entries(lines))
    rewrites = []
    skipped = []
    for start, title, end in entries:
        if is_exempt(title):
            continue
        size = end - start
        if size <= MAX_LINES:
            continue
        block = lines[start:end]
        body = block[1:]
        summary_path = find_summary_path(body)
        if (summary_path is None or not summary_path.exists()) and title in EXPLICIT_SUMMARY:
            summary_path = REPO / EXPLICIT_SUMMARY[title]
        if summary_path is None or not summary_path.exists():
            skipped.append((title, start + 1, str(summary_path)))
            continue
        rel = summary_path.relative_to(REPO).as_posix()
        new_block = make_short_block(title, body, rel)
        rewrites.append((start, end, block, summary_path, title, new_block))

    # Pre-pass: for every summary file we'll touch, strip any existing
    # "## Backfill from memory.md (migration trim 2026-05-25)" section so
    # re-runs are idempotent.
    touched_summaries = {sp for (_, _, _, sp, _, _) in rewrites}
    backfill_marker = "## Backfill from memory.md (migration trim 2026-05-25)"
    for sp in touched_summaries:
        existing = sp.read_text()
        idx = existing.find(backfill_marker)
        if idx != -1:
            # Trim everything from the marker onward (including the section header line).
            # Walk back to the start of the line containing the marker.
            line_start = existing.rfind("\n", 0, idx) + 1
            sp.write_text(existing[:line_start].rstrip() + "\n")

    for start, end, original_block, summary_path, title, new_block in reversed(rewrites):
        original_text = "\n".join(original_block).rstrip() + "\n"
        existing = summary_path.read_text()
        if backfill_marker not in existing:
            summary_path.write_text(
                existing.rstrip() + "\n\n" + backfill_marker + "\n\n" + original_text
            )
        else:
            summary_path.write_text(existing.rstrip() + "\n\n" + original_text)
        lines[start:end] = new_block

    MEM.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else ""))

    print(f"Rewrote {len(rewrites)} entries; skipped {len(skipped)}.")
    for t, ln, sp in skipped:
        print(f"  SKIP L{ln} '{t}' -> {sp}")
    print(f"memory.md: {len(MEM.read_text().splitlines())} lines after trim.")


if __name__ == "__main__":
    main()
