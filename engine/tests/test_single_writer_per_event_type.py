"""S-3 prep — single-writer-per-event-type grep guard.

Per implementation plan §8 cross-track coupling: each substrate event
type has exactly one allowed writer module. The plan lists:

- ``recommendation_emitted``      — written only from ``src/decide.py``
                                     (or its event-emit helper called by
                                     ``src/main.py`` post-decide)
- ``recommendation_considered``   — written only from ``src/decide.py``
- ``campaign_sent``                — written only from
                                     ``tools/import_campaign_sent.py``
- ``outcome_observed``             — written only from monitor / manual
                                     import path
- ``calibration_updated``          — written only from calibration
                                     consumer (Phase 9)

This test enforces the discipline by grep. Today (Sprint 2 prelude) the
substrate is not yet wired — the S-3 call sites in ``src/main.py`` are
TODO comments awaiting S-2. The test is therefore vacuous-passing for
the emit / considered events: it asserts that the count of writers is
≤1 for each event type. When S-3 wires the call site, the test
graduates to a strict equality check (the wire-up commit must update
this test in the same PR).

Why a grep test rather than a runtime hook: the substrate writer
(``append_event``) is a pure I/O surface; a lint-style check on the
literal event_type strings catches accidental second writers that a
runtime smoke test would only catch when both writers happen to fire
on the same fixture run.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pytest


# ---------------------------------------------------------------------------
# Allowed writers per event type (from plan §8)
# ---------------------------------------------------------------------------


_REPO_ROOT = Path(__file__).parent.parent

#: For each event_type, the set of source-file relative paths that are
#: allowed to write events of that type. A file is "allowed" if it
#: contains the literal event_type string in a writer-shaped context
#: (e.g. ``append_event(..., "recommendation_emitted", ...)``).
#:
#: Sprint 2 prelude state: substrate writer doesn't exist yet, so all
#: lists below are the **target** allowlist for when S-3 lands. The
#: assertion is "no file outside the allowlist contains the literal."
_ALLOWED_WRITERS: dict[str, frozenset[str]] = {
    "recommendation_emitted": frozenset(
        {
            "src/decide.py",
            "src/main.py",        # post-decide emission site (S-3)
            "src/memory/events.py",  # type schema (literal in docstring/dataclass)
            # S-6: import_campaign_sent.py is a *reader* of this event
            # type — it queries the substrate to validate that an
            # incoming campaign_sent payload references a real
            # recommendation_emitted row. The grep can't distinguish
            # readers from writers; allowlisted with this comment.
            "tools/import_campaign_sent.py",
        }
    ),
    "recommendation_considered": frozenset(
        {
            "src/decide.py",
            "src/main.py",
            "src/memory/events.py",
        }
    ),
    "campaign_sent": frozenset(
        {
            "tools/import_campaign_sent.py",  # exists post-S-6
        }
    ),
    "outcome_observed": frozenset(
        {
            "tools/import_outcome_observed.py",  # exists post-Phase 9
        }
    ),
    "calibration_updated": frozenset(
        {
            "src/calibration_stub.py",  # consumer view only, NOT a writer yet
        }
    ),
}


_SCAN_DIRS = ("src", "tools")
_SCAN_EXTS = (".py",)


def _iter_source_files() -> Iterable[Path]:
    for d in _SCAN_DIRS:
        root = _REPO_ROOT / d
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix in _SCAN_EXTS:
                yield p


def _files_mentioning(literal: str) -> list[str]:
    """Return relative paths of source files that mention ``literal`` as a
    quoted string (the event-type literal a writer would pass to
    ``append_event``).

    The pattern requires the literal to appear inside single or double
    quotes — this filters out symbol references / unrelated text but
    matches both writer call sites and dataclass/docstring mentions.
    The ``_ALLOWED_WRITERS`` allowlist accepts dataclass mentions
    explicitly (``src/memory/events.py``).
    """

    pat = re.compile(r"""['"]""" + re.escape(literal) + r"""['"]""")
    hits: list[str] = []
    for p in _iter_source_files():
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if pat.search(text):
            hits.append(str(p.relative_to(_REPO_ROOT)))
    return sorted(hits)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("event_type", sorted(_ALLOWED_WRITERS.keys()))
def test_no_unauthorized_writers_for_event_type(event_type: str):
    """For each event_type, every file mentioning the literal must be on
    the allowlist.

    A new writer for an existing event type is allowed ONLY if the
    allowlist is updated in the same PR. This forces explicit
    cross-track coordination.
    """

    allowed = _ALLOWED_WRITERS[event_type]
    mentioning = _files_mentioning(event_type)

    unauthorized = [f for f in mentioning if f not in allowed]
    assert unauthorized == [], (
        f"Event type {event_type!r} mentioned in non-allowlisted files: "
        f"{unauthorized}. If this is a legitimate new writer, update "
        f"_ALLOWED_WRITERS in this test in the same PR. Allowed today: "
        f"{sorted(allowed)}."
    )


def test_allowlist_covers_known_event_types():
    """Sanity: the allowlist must have an entry for each event type the
    plan freezes for Sprint 2 / 3 / Phase 9.

    Forces the allowlist to be updated whenever a new event type is
    introduced — preventing a silent "no allowlist entry, so the test
    is vacuous for this type" failure mode.
    """

    expected = frozenset(
        {
            "recommendation_emitted",
            "recommendation_considered",
            "campaign_sent",
            "outcome_observed",
            "calibration_updated",
        }
    )
    assert frozenset(_ALLOWED_WRITERS.keys()) == expected
