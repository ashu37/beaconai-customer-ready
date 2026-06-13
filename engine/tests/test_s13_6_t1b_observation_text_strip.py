"""Sprint 13.6 Ticket T1b (Option D) — Observation.text strip invariants.

Founder + DS approved 2026-05-31 (atomic-split sibling of T1a per DS R5;
see ``agent_outputs/code-refactor-engineer-s13.6-t1b-summary.md`` and the
PIVOTS.md Pivot 2 addendum).

This test pins the structural strip of ``Observation.text`` per Pivot 2
(the engine emits typed numerics on the contract surface; downstream
narration / renderers synthesize merchant-readable sentences from the
typed fields). The state-of-store paragraph in
:mod:`src.storytelling_v2` now composes its sentences from
``supporting_metric`` + ``classification`` + ``delta_pct`` +
``anomaly_flags`` — no prose field is read from the typed Observation.

Tests:

1. Dataclass introspection — ``text`` MUST NOT appear in
   ``dataclasses.fields(Observation)``.
2. ``EngineRun.to_dict()`` MUST NOT emit a ``text`` key on any
   serialized Observation.
3. AST sweep over ``src/`` for ``Observation(... text=...)`` kwarg
   producers — assert zero remaining.
4. Round-trip — legacy dicts carrying a stale ``text`` key are accepted
   without error (the key is dropped silently) and the resulting
   dataclass does not expose ``.text``.
"""
from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

import pytest

from src.engine_run import (
    EngineRun,
    Observation,
    ObservationClassification,
    _from_dict_observation,
)


# ---------------------------------------------------------------------------
# 1. Dataclass field introspection.
# ---------------------------------------------------------------------------


def test_observation_dataclass_has_no_text_field():
    """``Observation.text`` MUST NOT appear in the dataclass's fields."""
    present = {f.name for f in fields(Observation)}
    assert "text" not in present, (
        "S13.6-T1b strip incomplete: Observation still carries 'text'. "
        "Per Pivot 2, the engine emits typed numerics only; downstream "
        "renderers synthesize the merchant-readable sentence from the "
        "typed fields (supporting_metric, classification, delta_pct, "
        "anomaly_flags)."
    )


def test_observation_typed_numerics_preserved():
    """T1b strips ``text`` only — every other typed slot is preserved."""
    present = {f.name for f in fields(Observation)}
    required = {
        "supporting_metric",
        "change_magnitude",
        "classification",
        "current",
        "prior",
        "delta_pct",
        "anomaly_flags",
        "n_days_observed",
        "n_days_expected",
    }
    missing = required - present
    assert not missing, (
        f"S13.6-T1b stripped Observation.text but accidentally removed "
        f"additional typed slots: {missing}. T1b is the smallest-blast "
        f"sibling of T1a; only 'text' is in scope."
    )


# ---------------------------------------------------------------------------
# 2. to_dict() does not emit ``text``.
# ---------------------------------------------------------------------------


def test_engine_run_to_dict_drops_observation_text_key():
    """``EngineRun.to_dict()`` MUST NOT emit a ``text`` key on any
    serialized Observation, even when the legacy dict round-trip path
    carries one."""
    ob = Observation(
        supporting_metric="aov",
        delta_pct=0.042,
        classification=ObservationClassification.MOVED,
    )
    er = EngineRun(state_of_store=[ob])
    d = er.to_dict()
    serialized = d["state_of_store"][0]
    assert "text" not in serialized, (
        f"S13.6-T1b: Observation.text was stripped per Pivot 2; "
        f"serialization must not surface it. Got: {serialized!r}"
    )


def test_engine_run_emitted_json_drops_observation_text_key():
    """End-to-end JSON serialization (the engine_run.json payload) must
    not carry an ``Observation.text`` key for any state-of-store entry.

    Beauty-shaped fixture: one MOVED, one HELD, one ANOMALOUS so all
    three classification branches are covered.
    """
    import json
    er = EngineRun(
        state_of_store=[
            Observation(
                supporting_metric="aov",
                delta_pct=0.042,
                classification=ObservationClassification.MOVED,
            ),
            Observation(
                supporting_metric="repeat_rate_within_window",
                classification=ObservationClassification.HELD,
            ),
            Observation(
                supporting_metric="bfcm_overlap",
                anomaly_flags=["bfcm_overlap"],
                classification=ObservationClassification.ANOMALOUS,
            ),
        ],
    )
    payload = json.dumps(er.to_dict())
    # The literal substring ``"text":`` must not appear inside any
    # state-of-store entry. Other dataclasses (e.g. WatchedSignal /
    # OpportunityContext) do not carry a ``text`` field, so a literal
    # substring check across the whole payload is sound.
    for obs_dict in er.to_dict()["state_of_store"]:
        assert "text" not in obs_dict, (
            f"S13.6-T1b: Observation.text appeared in JSON payload: "
            f"{obs_dict!r}"
        )
    # Belt-and-braces: the substring sweep on the full payload.
    assert '"text"' not in payload or payload.count('"text"') == 0, (
        "S13.6-T1b: JSON payload still references a 'text' key. "
        "Confirm no Observation has accidentally re-acquired the slot."
    )


# ---------------------------------------------------------------------------
# 3. AST sweep — Observation(text=...) producers must be gone.
# ---------------------------------------------------------------------------


SRC_DIR = Path(__file__).resolve().parent.parent / "src"
OBSERVATION_CONSTRUCTORS = {"Observation"}


def _walk_python_files(root: Path):
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


def test_ast_no_remaining_observation_text_kwarg_producers():
    """No ``Observation(text=...)`` kwarg may remain anywhere in ``src/``.

    This is the AST sweep called out in the S13.6-T1b brief, modeled on
    the T1a producer sweep in
    ``tests/test_s13_6_t1a_prose_field_strip.py``.
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
            func = node.func
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            else:
                func_name = None
            if func_name not in OBSERVATION_CONSTRUCTORS:
                continue
            for kw in node.keywords or []:
                if kw.arg == "text":
                    offenders.append(
                        f"{f.relative_to(SRC_DIR.parent)}:{kw.lineno} "
                        f"Observation(text=...)"
                    )
    assert not offenders, (
        "S13.6-T1b strip incomplete — Observation(text=...) producers "
        "found:\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# 4. Round-trip — legacy ``text`` keys are dropped silently.
# ---------------------------------------------------------------------------


def test_from_dict_observation_drops_legacy_text_key_silently():
    """A legacy dict carrying a stale ``text`` key must round-trip into
    an Observation without raising — the key is dropped silently."""
    legacy = {
        "text": "AOV (L28): $58 (+4.2% vs prior)",
        "supporting_metric": "aov",
        "change_magnitude": 0.042,
        "classification": "moved",
        "current": 58.0,
        "prior": 55.6,
        "delta_pct": 0.042,
    }
    ob = _from_dict_observation(legacy)
    assert ob.supporting_metric == "aov"
    assert ob.delta_pct == pytest.approx(0.042)
    assert ob.classification == ObservationClassification.MOVED
    assert not hasattr(ob, "text"), (
        "S13.6-T1b: legacy ``text`` key must not resurrect the slot."
    )
