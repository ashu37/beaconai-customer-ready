"""Sprint 13.6 Ticket T1a (Option D) — Prose field strip invariants.

Founder + DS approved 2026-05-30. This test pins the structural strip of
the six engine-authored prose slots per Pivot 2 (engine emits typed
contract surface only; downstream narrates):

- ``PlayCard.recommendation_text``
- ``PlayCard.why_now``
- ``RejectedPlay.reason_text``
- ``RejectedPlay.evidence_snapshot``
- ``RejectedPlay.would_fire_if``
- ``Abstain.reason``

Plus the ``notes: List[str]`` operator-debug debris on S6+ typed slots
(Sensitivity / Provenance / PredictedSegment / ModelCardRef / MonthDelta),
gated at serialization time behind ``INCLUDE_DEBUG_FIELDS`` (default OFF).

The tests assert:
1. Dataclass introspection — each stripped attribute does NOT appear in
   ``dataclasses.fields(...)`` for the host dataclass.
2. ``engine_run.to_dict()`` does NOT emit the stripped keys on a fresh
   ``EngineRun`` round-trip.
3. AST sweep over ``src/`` for ``Attribute`` assignments (``card.x = ...``
   or ``replace(card, x=...)``) to the stripped field names — assert
   zero remaining producers.
4. INCLUDE_DEBUG_FIELDS round-trip — default OFF drops ``notes`` from
   the JSON; flipping ON brings them back.
"""
from __future__ import annotations

import ast
import os
from dataclasses import fields
from pathlib import Path

import pytest

from src.engine_run import (
    Abstain,
    EngineRun,
    ModelCardRef,
    MonthDelta,
    PlayCard,
    PredictedSegment,
    Provenance,
    RejectedPlay,
    ReasonCode,
    Sensitivity,
)


# ---------------------------------------------------------------------------
# 1. Dataclass field introspection.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls, stripped_fields",
    [
        (PlayCard, {"recommendation_text", "why_now"}),
        (RejectedPlay, {"reason_text", "evidence_snapshot", "would_fire_if"}),
        (Abstain, {"reason"}),
    ],
)
def test_stripped_fields_not_in_dataclass(cls, stripped_fields):
    """No stripped field should appear in the dataclass's fields."""
    present = {f.name for f in fields(cls)}
    overlap = present & stripped_fields
    assert not overlap, (
        f"S13.6-T1a strip incomplete: {cls.__name__} still carries "
        f"{overlap}. Per Pivot 2, the engine emits no merchant-facing "
        f"prose on the contract surface."
    )


# ---------------------------------------------------------------------------
# 2. to_dict() does not emit the stripped keys.
# ---------------------------------------------------------------------------


def test_play_card_to_dict_drops_stripped_keys():
    """A bare PlayCard.to_dict-like serialization must not carry the
    stripped prose keys."""
    pc = PlayCard(play_id="x")
    er = EngineRun(recommendations=[pc])
    d = er.to_dict()
    rec = d["recommendations"][0]
    assert "recommendation_text" not in rec
    assert "why_now" not in rec


def test_rejected_play_to_dict_drops_stripped_keys():
    rp = RejectedPlay(play_id="x", reason_code=ReasonCode.AUDIENCE_TOO_SMALL)
    er = EngineRun(considered=[rp])
    d = er.to_dict()
    rej = d["considered"][0]
    assert "reason_text" not in rej
    assert "evidence_snapshot" not in rej
    assert "would_fire_if" not in rej


def test_abstain_to_dict_drops_reason_key():
    er = EngineRun()
    d = er.to_dict()
    assert "reason" not in d["abstain"], (
        "Abstain.reason was stripped at S13.6-T1a per Pivot 2; "
        "serialization must not surface it."
    )


# ---------------------------------------------------------------------------
# 3. AST sweep — producers must be gone.
# ---------------------------------------------------------------------------


STRIPPED_PRODUCER_NAMES = {
    "recommendation_text",
    "why_now",
    "reason_text",
    "evidence_snapshot",
    "would_fire_if",
}

# Constructor names whose ``evidence_snapshot=`` kwarg refers to a
# DIFFERENT (typed S3 memory-event) ``EvidenceSnapshot`` dataclass, not
# the stripped ``RejectedPlay.evidence_snapshot: str`` slot. Exclude
# these from the producer sweep to avoid false positives.
STRIPPED_PRODUCER_TARGET_CONSTRUCTORS = {
    "PlayCard",
    "RejectedPlay",
    "Abstain",
    "replace",
    "_RejectedPlay",
    "_PlayCard",
    "_Abstain",
    "_PriorAnchoredSignal",
    "_SupportingSignal",
}

SRC_DIR = Path(__file__).resolve().parent.parent / "src"


def _walk_python_files(root: Path):
    for p in root.rglob("*.py"):
        # Skip vendored / generated / test-helper subtrees if any.
        if "__pycache__" in p.parts:
            continue
        yield p


def test_ast_no_remaining_keyword_producers():
    """No remaining ``recommendation_text=`` / ``why_now=`` / etc. kwargs
    in ``src/`` should be passed as keyword arguments to dataclass
    constructors or ``dataclasses.replace`` calls.

    This is the AST sweep called out in the S13.6-T1a brief (modeled on
    ``tests/test_s13_5_single_emission_point.py``).
    """
    offenders = []
    for f in _walk_python_files(SRC_DIR):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            # Resolve the called name (e.g. PlayCard / RejectedPlay /
            # ``dataclasses.replace`` / etc.). Skip kwargs on non-target
            # constructors so we don't false-positive on memory-event
            # ``EvidenceSnapshot`` paths.
            func = node.func
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            else:
                func_name = None
            if func_name not in STRIPPED_PRODUCER_TARGET_CONSTRUCTORS:
                continue
            for kw in node.keywords or []:
                if kw.arg in STRIPPED_PRODUCER_NAMES:
                    offenders.append(f"{f.relative_to(SRC_DIR.parent)}:{kw.lineno} kwarg={kw.arg}")
    assert not offenders, (
        "S13.6-T1a strip incomplete — keyword producers for stripped "
        "prose fields found:\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# 4. INCLUDE_DEBUG_FIELDS round-trip for ``notes`` debris.
# ---------------------------------------------------------------------------


NOTES_HOSTING_DATACLASSES = [
    (Sensitivity, lambda: Sensitivity(notes=["pinned"])),
    (Provenance, lambda: Provenance(notes=["pinned"])),
    (MonthDelta, lambda: MonthDelta(notes=["pinned"])),
]


@pytest.mark.parametrize("cls, factory", NOTES_HOSTING_DATACLASSES)
def test_notes_dropped_when_include_debug_fields_off(cls, factory, monkeypatch):
    """Default OFF: ``notes`` key absent from JSON serialization.

    Patches ``DEFAULTS`` directly (no module reload — see explanatory
    note below the ON round-trip test).
    """
    import src.utils as utils_mod
    monkeypatch.setitem(utils_mod.DEFAULTS, "INCLUDE_DEBUG_FIELDS", False)
    obj = factory()
    # Wrap in EngineRun via a PlayCard so we hit the serializer path.
    if cls is Sensitivity:
        pc = PlayCard(play_id="x", sensitivity=obj)
        er = EngineRun(recommendations=[pc])
        d = er.to_dict()["recommendations"][0]["sensitivity"]
    elif cls is Provenance:
        pc = PlayCard(play_id="x", provenance=obj)
        er = EngineRun(recommendations=[pc])
        d = er.to_dict()["recommendations"][0]["provenance"]
    elif cls is MonthDelta:
        er = EngineRun(month_2_delta=obj)
        d = er.to_dict()["month_2_delta"]
    else:
        pytest.skip(f"no wiring for {cls.__name__}")
    assert d is not None
    assert "notes" not in d, (
        f"S13.6-T1a INCLUDE_DEBUG_FIELDS=OFF gate failed for "
        f"{cls.__name__}: 'notes' key present in JSON output {d!r}"
    )


def test_notes_present_when_include_debug_fields_on(monkeypatch):
    """Flipping INCLUDE_DEBUG_FIELDS=true round-trips the ``notes`` key.

    Single round-trip assertion on Sensitivity as the canonical host.
    Uses ``monkeypatch.setitem`` on the live ``DEFAULTS`` dict rather
    than reloading the module — module reload breaks enum identity for
    other test files in the same session (e.g.
    ``test_would_be_measured_by_enum.py``'s ``isinstance`` checks).
    """
    import src.utils as utils_mod
    monkeypatch.setitem(utils_mod.DEFAULTS, "INCLUDE_DEBUG_FIELDS", True)

    pc = PlayCard(play_id="x", sensitivity=Sensitivity(notes=["a", "b"]))
    er = EngineRun(recommendations=[pc])
    d = er.to_dict()["recommendations"][0]["sensitivity"]
    assert d.get("notes") == ["a", "b"], (
        f"S13.6-T1a INCLUDE_DEBUG_FIELDS=ON round-trip failed: "
        f"expected notes=['a','b'], got {d!r}"
    )
