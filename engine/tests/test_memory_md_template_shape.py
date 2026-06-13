"""Lint test: enforce memory.md template-shape per founder-locked migration 2026-05-25.

Per CLAUDE.md "memory.md template-shape rule" and the doc-migration Phase 2
cutover (founder-approved 20-line cap), each per-ticket entry must be
template-shaped only. Verbose content (file change tables, test counts,
risk paragraphs, key learnings) belongs in
agent_outputs/code-refactor-engineer-<ticket>-summary.md.

Exemptions:
- The Founder Decisions block (D-1..D-8) at memory.md L173-182 is locked
  verbatim and is exempt by content (heading "Founder Decisions").
- Non-per-ticket structural headings under the introductory walls
  (Decision Core / M0-M9 / Phase 5 / Phase 6A / Phase 6B preamble) and
  the template header itself are exempt.
- Sprint-rollup headings ("Sprint <N> ... CLOSED" / "Sprint <N> ... rollup")
  are allowed to exceed the cap with a TODO note for future migration to
  dedicated rollup files.
"""
from __future__ import annotations

import pathlib
import re

MAX_LINES_PER_ENTRY = 20

# Headings that are NOT per-ticket entries. Match by startswith().
EXEMPT_HEADING_PREFIXES = (
    "How to use this file",
    "<Ticket-ID>",  # template literal
    "Accepted diagnosis",
    "Architecture",
    "Load-bearing invariants",
    "Permanently out of scope",
    "STOP-CODING LINE",
    "Engineer A track",
    "Engineer B track",
    "Founder Decisions",
)

# Sprint-rollup pattern: a heading like "Sprint 6 — CLOSED ..." (literal CLOSED in caps),
# or any heading whose body text starts with "Sprint" and ends in "rollup".
# Per-ticket entries titled "Sprint 6.5 Ticket T1 closeout" are NOT exempt — they're
# per-ticket and must conform to the cap.
SPRINT_ROLLUP_RE = re.compile(
    r"^Sprint\s+\d+(\.\d+)?\b(?!\s+Ticket)(.*\bCLOSED\b|.*\brollup\b)"
)


def _iter_entry_blocks(lines):
    """Yield (start_line_1indexed, heading_text, body_line_count) for each ## block."""
    headers = [(i, lines[i][3:].strip()) for i, line in enumerate(lines) if line.startswith("## ")]
    headers.append((len(lines), "__EOF__"))
    for (start, title), (end, _) in zip(headers, headers[1:]):
        size = end - start
        yield (start + 1, title, size)


def _is_exempt(title: str) -> bool:
    if any(title.startswith(p) for p in EXEMPT_HEADING_PREFIXES):
        return True
    if SPRINT_ROLLUP_RE.match(title):
        # TODO: migrate sprint rollups (S6-CLOSED, S7.6 close, etc.) into
        # dedicated agent_outputs/code-refactor-engineer-<sprint>-close-summary.md
        # files. Until then they are exempt from the 20-line cap.
        return True
    return False


def test_memory_md_entries_under_template_cap():
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    memory_path = repo_root / "memory.md"
    assert memory_path.exists(), f"memory.md not found at {memory_path}"
    lines = memory_path.read_text().splitlines()

    violations = []
    for start_line, title, size in _iter_entry_blocks(lines):
        if _is_exempt(title):
            continue
        if size > MAX_LINES_PER_ENTRY:
            violations.append(
                f"  memory.md L{start_line} '## {title}': {size} lines "
                f"(cap {MAX_LINES_PER_ENTRY})"
            )

    if violations:
        msg = (
            "memory.md entries exceed the template-shape cap of "
            f"{MAX_LINES_PER_ENTRY} lines per per-ticket block.\n\n"
            "Push verbose content (file change tables, test counts, risk "
            "paragraphs, key learnings, DS verdict transcripts) into the "
            "corresponding agent_outputs/code-refactor-engineer-<ticket>-summary.md "
            "under a `## Backfill from memory.md (migration trim 2026-05-25)` "
            "section. Leave only the template fields in memory.md.\n\n"
            "Offending blocks:\n" + "\n".join(violations)
        )
        raise AssertionError(msg)


def test_memory_md_founder_decisions_block_intact():
    """D-1..D-8 + storage backend note must survive every commit (D-N immutability)."""
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    text = (repo_root / "memory.md").read_text()
    for marker in ("**D-1**", "**D-2**", "**D-3**", "**D-4**", "**D-5**", "**D-6**", "**D-7**", "**D-8**"):
        assert marker in text, f"Founder Decision marker {marker!r} missing from memory.md"
    assert "Storage backend note (founder, 2026-05-10)" in text, (
        "Storage backend note (founder, 2026-05-10) missing from memory.md"
    )
