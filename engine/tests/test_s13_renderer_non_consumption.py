"""Sprint 13.6 Ticket T1a (Option D) — post-strip renderer grep pin.

Founder + DS approved 2026-05-30. Repurposed at S13.6-T1a from the
S13-T2.5 ``briefing.py``-only ``predicted_segment`` / ``model_card_ref``
/ ``month_2_delta`` non-consumption pin to a broader post-strip pin
covering the six prose field NAMES stripped at T1a:

- ``recommendation_text``
- ``why_now``
- ``reason_text``
- ``evidence_snapshot``
- ``would_fire_if``
- ``Abstain.reason`` (asserted via the pattern ``abstain.reason``)

across ``src/storytelling_v2.py`` AND ``src/briefing.py`` AND
``src/debug_renderer.py``. Per Pivot 2 the engine emits typed contract
surface only; downstream narration owns the merchant copy. The renderers
are kept runnable for local dev convenience (no AttributeError) but must
not re-introduce the stripped field reads.

If any future commit re-introduces one of these names inside the listed
renderer modules, this test MUST fail; the author MUST either re-strip
or update the allow-list with explicit founder + DS sign-off.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BRIEFING_PY = REPO_ROOT / "src" / "briefing.py"
STORYTELLING_PY = REPO_ROOT / "src" / "storytelling_v2.py"
DEBUG_RENDERER_PY = REPO_ROOT / "src" / "debug_renderer.py"

RENDERER_MODULES = [
    ("briefing.py", BRIEFING_PY),
    ("storytelling_v2.py", STORYTELLING_PY),
    ("debug_renderer.py", DEBUG_RENDERER_PY),
]

# The six stripped prose field names. Each value is (label, regex). The
# regex matches the NAME as an actual attribute / kwarg read — bare
# ``re.search(name)`` would also flag the in-comment S13.6-T1a strip
# notes, so we look for either ``.<name>`` or ``<name>=`` (attribute
# read or kwarg) plus a guard against the comment-only strip notes.
STRIPPED_PATTERNS = [
    ("recommendation_text", re.compile(r"\.recommendation_text\b|\brecommendation_text\s*=")),
    ("why_now", re.compile(r"\.why_now\b|\bwhy_now\s*=")),
    ("reason_text", re.compile(r"\.reason_text\b|\breason_text\s*=")),
    ("evidence_snapshot", re.compile(r"\.evidence_snapshot\b|\bevidence_snapshot\s*=")),
    ("would_fire_if", re.compile(r"\.would_fire_if\b|\bwould_fire_if\s*=")),
    # Abstain.reason: only the attribute-read pattern; the typed
    # ``Abstain.mode`` enum is the contract surface.
    ("Abstain.reason", re.compile(r"\babstain\.reason\b")),
    # Sprint 13.6 Ticket T1b (founder + DS approved 2026-05-31):
    # ``Observation.text`` stripped per Pivot 2. Renderers MUST NOT
    # re-introduce a prose read on the Observation contract surface.
    # Patterns scanned: ``ob.text`` / ``obs.text`` / ``observation.text``
    # / ``Observation(text=...)``. Sentence synthesis lives in
    # ``_synthesize_observation_sentence`` and reads only typed
    # numerics + classification + anomaly_flags.
    (
        "Observation.text",
        re.compile(
            r"\bob\.text\b|\bobs\.text\b|\bobservation\.text\b"
            r"|\bObservation\s*\([^)]*\btext\s*="
        ),
    ),
    # Sprint 13.6 Ticket T2 (founder lock-in #6, 2026-05-30):
    # ``PlayCard.klaviyo_brief_inputs`` REMOVED entirely. Klaviyo upload is
    # manual post-approval per D-5; the engine emits no Klaviyo-specific
    # payload. Renderers MUST NOT re-introduce this slot under any name.
    # Pattern catches attribute-reads (``.klaviyo_brief_inputs``) and
    # kwarg-writes (``klaviyo_brief_inputs=``).
    (
        "klaviyo_brief_inputs",
        re.compile(r"\bklaviyo_brief_inputs\b"),
    ),
    # Sprint 13.6 Ticket T3 (DS R1, founder approved 2026-05-30):
    # ``OpportunityContext.aov`` and ``.addressable_value`` STRIPPED as
    # duplicates of ``non_lift.aov_used`` and ``non_lift.value`` /
    # ``non_lift.monthly_revenue_estimate``. Renderers MUST NOT re-introduce
    # reads on these names; the four monetary numerics are reached only
    # through the typed ``NonLiftAtom`` wrapper.
    # Patterns scoped to OpportunityContext-flavored reads: ``opp.aov`` /
    # ``opp.addressable_value`` / ``.addressable_value`` (attribute read or
    # kwarg). Bare ``.aov`` is too permissive (Inputs dataclass in sizing
    # carries an unrelated ``aov`` field), so we anchor to ``opp.``.
    (
        "OpportunityContext.aov",
        re.compile(r"\bopp\.aov\b(?!_)"),
    ),
    (
        "OpportunityContext.addressable_value",
        re.compile(r"\.addressable_value\b|\baddressable_value\s*="),
    ),
    # Sprint 13.6 Ticket T4 (D-S13-4 structural, founder + DS approved
    # 2026-05-31): the legacy ``"{LEVEL}:{substrate}"`` string grammar
    # for ``ModelCardRef.fit_warnings`` is REPLACED by typed
    # ``FitWarning(level: FitWarningLevel, substrate: str)``. Renderers
    # MUST NOT re-introduce the string-grammar substrings (which would
    # be load-bearing evidence of a regression to string-parsing the
    # old shape). Each pattern catches the literal LEVEL-prefix-with-
    # colon substring; the FitWarningLevel enum VALUES themselves are
    # the same names but the colon-prefix only ever appeared in the
    # legacy string grammar.
    (
        "FitWarning string-grammar PROVISIONAL_SELECTED:",
        re.compile(r'"PROVISIONAL_SELECTED:|\'PROVISIONAL_SELECTED:'),
    ),
    (
        "FitWarning string-grammar MODEL_FIT_INSUFFICIENT_DATA:",
        re.compile(r'"MODEL_FIT_INSUFFICIENT_DATA:|\'MODEL_FIT_INSUFFICIENT_DATA:'),
    ),
    (
        "FitWarning string-grammar MODEL_FIT_REFUSED:",
        re.compile(r'"MODEL_FIT_REFUSED:|\'MODEL_FIT_REFUSED:'),
    ),
]


def _scan(module_path: Path, pattern: re.Pattern) -> list[str]:
    """Return list of "lineno: line" hits for the pattern in the file,
    excluding lines that are pure comments referencing the S13.6-T1a
    strip notes (those are intentional docstring / inline-comment
    breadcrumbs and not load-bearing consumption)."""
    out = []
    if not module_path.exists():
        return out
    for i, line in enumerate(module_path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        # Skip comment-only breadcrumb lines.
        if stripped.startswith("#"):
            continue
        # Skip docstring lines that are just narrating the strip.
        if "S13.6-T1a" in line and "strip" in line.lower():
            continue
        if pattern.search(line):
            out.append(f"{i}: {line.strip()}")
    return out


@pytest.mark.parametrize("field_name, pattern", STRIPPED_PATTERNS)
@pytest.mark.parametrize("module_label, module_path", RENDERER_MODULES)
def test_renderer_does_not_consume_stripped_field(
    field_name, pattern, module_label, module_path
):
    """Each renderer module MUST NOT carry a load-bearing read of any
    stripped prose field. Comment-only breadcrumbs are allowed (the
    scanner ignores them)."""
    hits = _scan(module_path, pattern)
    assert not hits, (
        f"FORBIDDEN: src/{module_label} consumes stripped field "
        f"'{field_name}' at line(s):\n  " + "\n  ".join(hits)
        + f"\n\nS13.6-T1a (Option D, founder + DS approved 2026-05-30) "
        f"stripped this slot from the engine contract surface per "
        f"Pivot 2. Renderers stay runnable but must not re-introduce "
        f"the prose reads. If re-introduction is intentional, you MUST "
        f"obtain explicit founder + DS sign-off documented in PIVOTS.md "
        f"and update this allow-list."
    )
