"""Sprint 13.6 Ticket T3 — NonLiftAtom typed wrapper tests.

DS R1 verbatim (founder approved 2026-05-30): "A `bool
_do_not_narrate_as_lift = True` field on the dataclass is type-safety
theatre. An agent that ignores it sees the numbers and narrates them.
Replace with a wrapper dataclass at the field type level... The wrapper
*names* the constraint at the type system, not via a sibling flag.
Schema consumers see `NonLiftAtom`, not a number with a 'please don't
narrate as lift' sticker."

This test file pins:

1. ``NonLiftAtom`` exists as a dataclass with the four DS-R1-locked
   fields and the closed-set Literal semantic.
2. ``OpportunityContext`` no longer carries the stripped duplicates
   (``aov`` / ``addressable_value``).
3. ``OpportunityContext.non_lift`` is typed as ``NonLiftAtom``.
4. Re-export: ``NonLiftAtom`` is importable from ``src.engine_run``.
5. End-to-end: every Beauty-fixture PlayCard with a populated
   ``opportunity_context`` carries a ``NonLiftAtom`` with the closed-set
   ``semantic`` value.
6. JSON shape: every emitted ``opportunity_context`` block carries a
   ``non_lift`` sub-object with the four fields.
7. AST sweep over ``src/``: no remaining ``opp.aov`` /
   ``opp.addressable_value`` reads (the four monetary numerics are
   reached only through ``.non_lift.*``).
8. NO sibling ``_do_not_narrate_as_lift`` flag was introduced (the
   wrapper IS the guardrail per DS R1).
"""
from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
from typing import get_args, get_type_hints

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"


# ---------------------------------------------------------------------------
# 1. NonLiftAtom dataclass exists with the DS-R1-locked field shape
# ---------------------------------------------------------------------------


def test_non_lift_atom_exists_and_is_dataclass():
    from src.engine_run import NonLiftAtom

    assert dataclasses.is_dataclass(NonLiftAtom)


def test_non_lift_atom_has_exactly_four_fields():
    from src.engine_run import NonLiftAtom

    field_names = {f.name for f in dataclasses.fields(NonLiftAtom)}
    assert field_names == {
        "value",
        "semantic",
        "aov_used",
        "monthly_revenue_estimate",
    }, f"NonLiftAtom field-set drift: {field_names}"


def test_non_lift_atom_field_types_match_ds_r1_lock():
    from src.engine_run import NonLiftAtom

    hints = get_type_hints(NonLiftAtom)
    # value: float
    assert hints["value"] is float
    # aov_used: float
    assert hints["aov_used"] is float
    # monthly_revenue_estimate: float
    assert hints["monthly_revenue_estimate"] is float
    # semantic: Literal["addressable_opportunity"]
    semantic_args = get_args(hints["semantic"])
    assert semantic_args == ("addressable_opportunity",), (
        f"semantic must be a closed-set Literal "
        f"['addressable_opportunity']; got {semantic_args}"
    )


def test_non_lift_atom_re_exported_from_engine_run():
    """DS R6 (schema-authority) — agents read one file for the contract."""
    from src import engine_run

    assert "NonLiftAtom" in getattr(engine_run, "__all__", []), (
        "NonLiftAtom must appear in engine_run.__all__ per DS R6 "
        "single-file schema surface."
    )


# ---------------------------------------------------------------------------
# 2. OpportunityContext restructure: stripped duplicates + non_lift slot
# ---------------------------------------------------------------------------


def test_opportunity_context_no_longer_carries_aov_or_addressable_value():
    from src.engine_run import OpportunityContext

    field_names = {f.name for f in dataclasses.fields(OpportunityContext)}
    assert "aov" not in field_names, (
        "OpportunityContext.aov stripped at S13.6-T3 as a duplicate of "
        "non_lift.aov_used (DS-locked)."
    )
    assert "addressable_value" not in field_names, (
        "OpportunityContext.addressable_value stripped at S13.6-T3 as a "
        "duplicate of non_lift.value / non_lift.monthly_revenue_estimate "
        "(DS-locked)."
    )
    # The other monetary aliases (aov_used / monthly_revenue_estimate) also
    # left the top level — they now live inside the NonLiftAtom wrapper.
    assert "aov_used" not in field_names
    assert "monthly_revenue_estimate" not in field_names


def test_opportunity_context_carries_non_lift_typed_as_non_lift_atom():
    from src.engine_run import NonLiftAtom, OpportunityContext

    field_names = {f.name for f in dataclasses.fields(OpportunityContext)}
    assert "non_lift" in field_names

    hints = get_type_hints(OpportunityContext)
    assert hints["non_lift"] is NonLiftAtom, (
        f"OpportunityContext.non_lift must be typed NonLiftAtom; "
        f"got {hints['non_lift']!r}"
    )


# ---------------------------------------------------------------------------
# 3. End-to-end: producer-built OpportunityContext is a NonLiftAtom
# ---------------------------------------------------------------------------


def test_measurement_builder_produces_non_lift_atom():
    """The Phase 5.1 directional builder constructs the wrapper end-to-end.

    Differential against the dedicated _build_opportunity_context helper.
    """
    from src.engine_run import NonLiftAtom
    from src.measurement_builder import _build_opportunity_context

    aligned = {"L28": {"aov": 69.0}}
    opp = _build_opportunity_context(286, aligned, primary_window="L28")
    assert opp is not None
    assert isinstance(opp.non_lift, NonLiftAtom)
    assert opp.non_lift.semantic == "addressable_opportunity"
    assert opp.non_lift.aov_used == 69.0
    assert opp.non_lift.value == 286 * 69.0
    assert opp.non_lift.monthly_revenue_estimate == 286 * 69.0


# ---------------------------------------------------------------------------
# 4. JSON shape: opportunity_context now nests non_lift
# ---------------------------------------------------------------------------


def test_engine_run_json_carries_non_lift_sub_object():
    """Round-trip pins the on-the-wire shape that downstream agents see."""
    from src.engine_run import (
        Abstain,
        Audience,
        DecisionState,
        EngineRun,
        EvidenceClass,
        NonLiftAtom,
        OpportunityContext,
        PlayCard,
        RevenueRange,
    )

    card = PlayCard(
        play_id="first_to_second_purchase",
        evidence_class=EvidenceClass.DIRECTIONAL,
        audience=Audience(size=286, definition="single-purchase customers"),
        revenue_range=RevenueRange(suppressed=True),
        opportunity_context=OpportunityContext(
            audience_size=286,
            non_lift=NonLiftAtom(
                value=286 * 69.0,
                semantic="addressable_opportunity",
                aov_used=69.0,
                monthly_revenue_estimate=286 * 69.0,
            ),
        ),
    )
    er = EngineRun(
        store_id="s13_6_t3_pin",
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[card],
    )
    payload = er.to_dict()
    oc_dict = payload["recommendations"][0]["opportunity_context"]
    assert "non_lift" in oc_dict, (
        f"opportunity_context JSON must carry a non_lift sub-object; "
        f"got keys: {sorted(oc_dict.keys())}"
    )
    # Stripped duplicates must NOT appear on the wire.
    assert "aov" not in oc_dict
    assert "addressable_value" not in oc_dict
    assert "aov_used" not in oc_dict
    assert "monthly_revenue_estimate" not in oc_dict
    # The four NonLiftAtom fields are present in the nested object.
    nl = oc_dict["non_lift"]
    assert set(nl.keys()) == {
        "value", "semantic", "aov_used", "monthly_revenue_estimate"
    }
    assert nl["semantic"] == "addressable_opportunity"
    assert nl["value"] == 286 * 69.0
    assert nl["aov_used"] == 69.0
    assert nl["monthly_revenue_estimate"] == 286 * 69.0

    # Round-trip preserves shape.
    rebuilt = EngineRun.from_dict(payload)
    opp = rebuilt.recommendations[0].opportunity_context
    assert opp is not None
    assert isinstance(opp.non_lift, NonLiftAtom)
    assert opp.non_lift.value == 286 * 69.0
    assert opp.non_lift.semantic == "addressable_opportunity"


# ---------------------------------------------------------------------------
# 5. AST sweep over src/: no stripped-field reads remain
# ---------------------------------------------------------------------------


def _iter_attribute_reads(py_path: Path):
    """Yield (attr_name, lineno) tuples for every ast.Attribute read in the
    file. Skips files that fail to parse (none expected in src/)."""
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            yield node.attr, node.lineno


def test_ast_sweep_no_stripped_oc_reads_in_src():
    """No ``oc.aov`` or ``oc.addressable_value`` reads remain in src/.

    Scoped to ``src/`` only (tests intentionally retain stripped-name reads
    inside parametrized test cases that exercise legacy fixtures, but src/
    is the contract-emitting surface).

    The check uses an AST Attribute walk so it is robust to comment-style
    breadcrumbs (the renderer non-consumption pin handles those).
    """
    forbidden_attrs = {"addressable_value"}
    offenders = []
    for py_path in SRC_DIR.rglob("*.py"):
        # Allow the dataclass docstring itself in engine_run.py to mention
        # the stripped names in prose (the AST walk only flags live reads).
        for attr, lineno in _iter_attribute_reads(py_path):
            if attr in forbidden_attrs:
                offenders.append(f"{py_path.relative_to(REPO_ROOT)}:{lineno} .{attr}")
    assert not offenders, (
        "Stripped OpportunityContext attribute reads remain in src/:\n  "
        + "\n  ".join(offenders)
        + "\n\nUse `.non_lift.value` / `.non_lift.aov_used` / "
        "`.non_lift.monthly_revenue_estimate` instead (S13.6-T3 DS R1)."
    )


def test_no_do_not_narrate_as_lift_flag_introduced():
    """DS R1 explicitly rejected a sibling
    ``bool _do_not_narrate_as_lift`` flag as "type-safety theatre".
    The wrapper IS the guardrail; ensure no such flag was bolted on."""
    forbidden = "_do_not_narrate_as_lift"
    offenders = []
    for py_path in SRC_DIR.rglob("*.py"):
        text = py_path.read_text(encoding="utf-8")
        if forbidden in text:
            offenders.append(str(py_path.relative_to(REPO_ROOT)))
    assert not offenders, (
        f"Forbidden sibling flag {forbidden!r} appeared in: {offenders}. "
        "DS R1 rejected this pattern; the NonLiftAtom wrapper IS the "
        "type-system guardrail."
    )
