"""Sprint 13.6 Ticket T2 — typed Any slots + klaviyo_brief_inputs removal.

Founder + DS approved 2026-05-30 (DS R6 schema-authority lock; founder
lock-in #6 manual-Klaviyo-only). See
``agent_outputs/code-refactor-engineer-s13.6-t2-summary.md``.

Pins four invariants:

1. ``EngineRun.store_profile`` is typed ``Optional[StoreProfile]``
   (was ``Optional[Any]`` pre-T2).
2. ``EngineRun.predictive_models`` is typed ``Dict[str, ModelCard]``
   (was ``Dict[str, Any]`` pre-T2).
3. ``EngineRun.cohort_diagnostics`` is typed ``Dict[str, RetentionCard]``
   (was ``Dict[str, Any]`` pre-T2).
4. ``PlayCard.klaviyo_brief_inputs`` REMOVED entirely (founder lock-in #6
   — manual Klaviyo upload post-approval per D-5). Field is absent from
   the dataclass, ``to_dict()`` serialization, emitted JSON, and AST
   producer-call surface.

Plus:

- Re-export assertion: the three canonical types are importable directly
  from ``src.engine_run`` (DS R6 — single-file schema authority).
- Round-trip assertion: legacy dicts carrying a stale
  ``klaviyo_brief_inputs`` key are accepted without error (the key is
  silently dropped by ``_from_dict_play_card``).
"""
from __future__ import annotations

import ast
import json
from dataclasses import fields
from pathlib import Path
from typing import Dict, Optional, get_type_hints

import pytest

# DS R6: schema authority = src/engine_run.py. The three canonical types
# MUST be importable from this one module.
from src.engine_run import (
    EngineRun,
    PlayCard,
    ModelCard,
    ModelFitStatus,
    RetentionCard,
    StoreProfile,
    _from_dict_play_card,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"


# ---------------------------------------------------------------------------
# 1. Typed-annotation assertions on EngineRun (the three previously-Any slots).
# ---------------------------------------------------------------------------


def test_engine_run_store_profile_is_typed_optional_storeprofile():
    hints = get_type_hints(EngineRun)
    assert hints["store_profile"] == Optional[StoreProfile], (
        f"S13.6-T2: EngineRun.store_profile MUST be Optional[StoreProfile] "
        f"(DS R6 schema-authority lock); got {hints['store_profile']!r}."
    )


def test_engine_run_predictive_models_is_typed_dict_str_modelcard():
    hints = get_type_hints(EngineRun)
    assert hints["predictive_models"] == Dict[str, ModelCard], (
        f"S13.6-T2: EngineRun.predictive_models MUST be Dict[str, ModelCard]; "
        f"got {hints['predictive_models']!r}."
    )


def test_engine_run_cohort_diagnostics_is_typed_dict_str_retentioncard():
    hints = get_type_hints(EngineRun)
    assert hints["cohort_diagnostics"] == Dict[str, RetentionCard], (
        f"S13.6-T2: EngineRun.cohort_diagnostics MUST be Dict[str, "
        f"RetentionCard] (D-S12-1 architecturally distinct from "
        f"predictive_models); got {hints['cohort_diagnostics']!r}."
    )


# ---------------------------------------------------------------------------
# 2. Re-export assertion (DS R6).
# ---------------------------------------------------------------------------


def test_canonical_types_reexported_from_engine_run():
    """Agents read one file (src/engine_run.py) for all four typed slots.

    Asserts via fresh import that the re-export at the top of
    ``src/engine_run.py`` resolves to the canonical class objects from
    the producer modules (NOT a renamed proxy).
    """
    from src.profile.types import StoreProfile as CanonicalStoreProfile
    from src.predictive.model_card import (
        ModelCard as CanonicalModelCard,
        ModelFitStatus as CanonicalModelFitStatus,
        RetentionCard as CanonicalRetentionCard,
    )
    assert StoreProfile is CanonicalStoreProfile
    assert ModelCard is CanonicalModelCard
    assert ModelFitStatus is CanonicalModelFitStatus
    assert RetentionCard is CanonicalRetentionCard


# ---------------------------------------------------------------------------
# 3. PlayCard.klaviyo_brief_inputs — total removal.
# ---------------------------------------------------------------------------


def test_play_card_has_no_klaviyo_brief_inputs_field():
    """``PlayCard.klaviyo_brief_inputs`` MUST be removed entirely (no flag,
    no default-empty stub). Re-addition post-AWS-migration is out of v1
    scope and requires founder + DS sign-off documented in PIVOTS.md."""
    present = {f.name for f in fields(PlayCard)}
    assert "klaviyo_brief_inputs" not in present, (
        "S13.6-T2: founder lock-in #6 (2026-05-30) — klaviyo_brief_inputs "
        "MUST be removed from PlayCard entirely. Manual Klaviyo upload "
        "post-approval per D-5."
    )


def test_engine_run_to_dict_emits_no_klaviyo_brief_inputs_key():
    """``EngineRun.to_dict()`` MUST NOT surface ``klaviyo_brief_inputs``
    on any serialized PlayCard."""
    er = EngineRun(recommendations=[PlayCard(play_id="winback_dormant_cohort")])
    d = er.to_dict()
    pc_serialized = d["recommendations"][0]
    assert "klaviyo_brief_inputs" not in pc_serialized, (
        f"S13.6-T2: PlayCard.klaviyo_brief_inputs leaked into to_dict(): "
        f"{pc_serialized!r}"
    )


def test_emitted_json_contains_no_klaviyo_brief_inputs_substring():
    """End-to-end JSON serialization MUST NOT carry the literal
    ``klaviyo_brief_inputs`` substring. Beauty-shaped fixture covers
    PUBLISH recommendations + considered branches."""
    er = EngineRun(
        recommendations=[
            PlayCard(play_id="winback_dormant_cohort"),
            PlayCard(play_id="discount_dependency_hygiene"),
        ],
    )
    payload = json.dumps(er.to_dict())
    assert "klaviyo_brief_inputs" not in payload, (
        "S13.6-T2: emitted JSON still references klaviyo_brief_inputs."
    )


# ---------------------------------------------------------------------------
# 4. AST sweep — no remaining PlayCard(klaviyo_brief_inputs=...) producers
#    anywhere in src/.
# ---------------------------------------------------------------------------


def _walk_python_files(root: Path):
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


def test_ast_no_remaining_klaviyo_brief_inputs_kwarg_in_src():
    """No ``klaviyo_brief_inputs=`` kwarg may remain anywhere in ``src/``.

    Mirrors the T1b producer sweep pattern. Catches any constructor or
    function call that still carries the removed kwarg, regardless of
    which dataclass it targets (PlayCard is the only known consumer but
    the sweep is broad by design)."""
    offenders = []
    for f in _walk_python_files(SRC_DIR):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords or []:
                if kw.arg == "klaviyo_brief_inputs":
                    offenders.append(
                        f"{f.relative_to(SRC_DIR.parent)}:{kw.lineno} "
                        f"klaviyo_brief_inputs= kwarg"
                    )
    assert not offenders, (
        "S13.6-T2 strip incomplete — klaviyo_brief_inputs= kwarg "
        "producers found:\n" + "\n".join(offenders)
    )


def test_grep_sweep_no_klaviyo_brief_inputs_in_src():
    """Belt-and-braces grep sweep over ``src/`` for any textual occurrence
    of ``klaviyo_brief_inputs``. The AST sweep above catches kwargs; this
    one catches attribute reads, dict-key strings, or any other leak."""
    hits = []
    for f in _walk_python_files(SRC_DIR):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "klaviyo_brief_inputs" not in line:
                continue
            stripped = line.strip()
            # Allow comment-only breadcrumbs noting the removal.
            if stripped.startswith("#"):
                continue
            hits.append(f"{f.relative_to(SRC_DIR.parent)}:{i}: {stripped}")
    assert not hits, (
        "S13.6-T2: klaviyo_brief_inputs still appears in src/ outside "
        "comment breadcrumbs:\n" + "\n".join(hits)
    )


# ---------------------------------------------------------------------------
# 5. Round-trip — legacy dicts with klaviyo_brief_inputs are accepted silently.
# ---------------------------------------------------------------------------


def test_from_dict_play_card_drops_legacy_klaviyo_brief_inputs_key():
    """A legacy dict carrying a stale ``klaviyo_brief_inputs`` key must
    round-trip into a PlayCard without raising — the key is dropped
    silently (mirrors the T1a/T1b strip pattern)."""
    legacy = {
        "play_id": "winback_dormant_cohort",
        "evidence_class": "directional",
        "klaviyo_brief_inputs": {"audience": "winback_21_45"},
    }
    pc = _from_dict_play_card(legacy)
    assert pc.play_id == "winback_dormant_cohort"
    assert not hasattr(pc, "klaviyo_brief_inputs"), (
        "S13.6-T2: legacy klaviyo_brief_inputs key must not resurrect "
        "the slot."
    )


# ---------------------------------------------------------------------------
# 6. Round-trip via EngineRun.from_dict re-hydrates typed StoreProfile.
# ---------------------------------------------------------------------------


def test_engine_run_round_trip_rehydrates_typed_store_profile():
    """``EngineRun.from_dict(EngineRun(store_profile=<sp>).to_dict())``
    returns a typed ``StoreProfile`` (NOT a dict). Confirms the DS R6
    re-export resolves to the canonical class used at round-trip time."""
    sp = StoreProfile(store_id="round_trip_smoke")
    er = EngineRun(store_profile=sp)
    rehydrated = EngineRun.from_dict(er.to_dict())
    assert isinstance(rehydrated.store_profile, StoreProfile), (
        f"S13.6-T2: round-trip dropped StoreProfile typing; got "
        f"{type(rehydrated.store_profile).__name__}"
    )
    assert rehydrated.store_profile.store_id == "round_trip_smoke"
