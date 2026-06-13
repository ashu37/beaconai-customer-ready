"""S13.6-T4 — FitWarning typed grammar (D-S13-4 structural) pin.

Per ``docs/DECISIONS.md::D-S13-4`` the LEVEL grammar that historically
lived in code comments only (``"{LEVEL}:{substrate}"`` string format)
is replaced by typed
:class:`src.engine_run.FitWarning(level: FitWarningLevel, substrate: str)`.
This test pins the structural surface, the producer rewire, and the
round-trip serialization.

Q-S13-4 LOCK (DS-locked invariant) is enforced by
``tests/test_s13_ml_fit_never_demotes.py`` and the AST-aware
``tests/test_reason_code_precedence_invariant.py``; this test pins the
typed-grammar shape that those two tests depend on.
"""
from __future__ import annotations

import ast
import sys
import typing
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import (  # noqa: E402
    EngineRun,
    FitWarning,
    FitWarningLevel,
    ModelCardRef,
    PlayCard,
)
from src.predictive.model_card import ModelCard, ModelFitStatus  # noqa: E402
from src.predictive.ranking_strategy import (  # noqa: E402
    AudienceIntent,
    rank_audience,
)


# ---------------------------------------------------------------------------
# 1. FitWarningLevel — closed 3-member str enum.
# ---------------------------------------------------------------------------


def test_fit_warning_level_is_str_enum_with_exactly_three_members() -> None:
    assert issubclass(FitWarningLevel, str)
    assert issubclass(FitWarningLevel, Enum)
    members = {m.name for m in FitWarningLevel}
    assert members == {
        "PROVISIONAL_SELECTED",
        "MODEL_FIT_INSUFFICIENT_DATA",
        "MODEL_FIT_REFUSED",
    }
    # Values are exact uppercase string match (consumed by JSON
    # serialization + cross-doc reads).
    assert FitWarningLevel.PROVISIONAL_SELECTED.value == "PROVISIONAL_SELECTED"
    assert FitWarningLevel.MODEL_FIT_INSUFFICIENT_DATA.value == "MODEL_FIT_INSUFFICIENT_DATA"
    assert FitWarningLevel.MODEL_FIT_REFUSED.value == "MODEL_FIT_REFUSED"


# ---------------------------------------------------------------------------
# 2. FitWarning — dataclass with (level, substrate) fields.
# ---------------------------------------------------------------------------


def test_fit_warning_is_dataclass_with_level_and_substrate() -> None:
    assert is_dataclass(FitWarning)
    field_map = {f.name: f for f in fields(FitWarning)}
    assert set(field_map.keys()) == {"level", "substrate"}
    # Type annotation pin (we read .type which is the annotation expression).
    hints = typing.get_type_hints(FitWarning)
    assert hints["level"] is FitWarningLevel
    assert hints["substrate"] is str


# ---------------------------------------------------------------------------
# 3. ModelCardRef.fit_warnings is now List[FitWarning].
# ---------------------------------------------------------------------------


def test_model_card_ref_fit_warnings_typed_to_list_of_fit_warning() -> None:
    hints = typing.get_type_hints(ModelCardRef)
    fw_hint = hints["fit_warnings"]
    # ``List[FitWarning]`` resolves via typing.get_type_hints to a
    # generic alias whose origin is list and whose args are (FitWarning,).
    assert typing.get_origin(fw_hint) is list
    args = typing.get_args(fw_hint)
    assert args == (FitWarning,), (
        f"ModelCardRef.fit_warnings expected List[FitWarning]; got {fw_hint!r}"
    )


# ---------------------------------------------------------------------------
# 4. Re-export surface — single-file schema authority (DS R6).
# ---------------------------------------------------------------------------


def test_fit_warning_and_level_reexported_from_engine_run() -> None:
    from src import engine_run as er
    assert "FitWarning" in er.__all__
    assert "FitWarningLevel" in er.__all__
    assert er.FitWarning is FitWarning
    assert er.FitWarningLevel is FitWarningLevel


# ---------------------------------------------------------------------------
# 5. Producer — rank_audience emits typed FitWarning instances.
# ---------------------------------------------------------------------------


def _mc(status: ModelFitStatus, name: str = "") -> ModelCard:
    return ModelCard(model_name=name, fit_status=status)


def test_rank_audience_produces_typed_fit_warning_instances() -> None:
    predictive_models = {
        "bgnbd": _mc(ModelFitStatus.REFUSED, "bgnbd"),
        "cf": _mc(ModelFitStatus.INSUFFICIENT_DATA, "cf"),
        "survival": _mc(ModelFitStatus.REFUSED, "survival"),
        "rfm": _mc(ModelFitStatus.PROVISIONAL, "rfm"),
    }
    result = rank_audience(predictive_models, AudienceIntent.GENERAL)
    assert result.strategy_used == "RFM"
    # Every entry is a typed FitWarning.
    for fw in result.fit_warnings:
        assert isinstance(fw, FitWarning), (
            f"S13.6-T4 typed producer pin: got {type(fw).__name__}: {fw!r}"
        )
    # Walk order matches DS-LOCKED grammar.
    assert result.fit_warnings == [
        FitWarning(FitWarningLevel.MODEL_FIT_REFUSED, "bgnbd"),
        FitWarning(FitWarningLevel.MODEL_FIT_INSUFFICIENT_DATA, "cf"),
        FitWarning(FitWarningLevel.MODEL_FIT_REFUSED, "survival"),
        FitWarning(FitWarningLevel.PROVISIONAL_SELECTED, "rfm"),
    ]


# ---------------------------------------------------------------------------
# 6. JSON serialization — FitWarning becomes {"level": ..., "substrate": ...}.
# ---------------------------------------------------------------------------


def test_engine_run_serializes_fit_warning_as_typed_object() -> None:
    er = EngineRun(
        recommendations=[
            PlayCard(
                play_id="winback_dormant_cohort",
                model_card_ref=ModelCardRef(
                    strategy_used="RFM",
                    fit_status_chain=[("bgnbd", "REFUSED"), ("rfm", "PROVISIONAL")],
                    fit_warnings=[
                        FitWarning(FitWarningLevel.MODEL_FIT_REFUSED, "bgnbd"),
                        FitWarning(FitWarningLevel.PROVISIONAL_SELECTED, "rfm"),
                    ],
                ),
            )
        ]
    )
    d = er.to_dict()
    fws = d["recommendations"][0]["model_card_ref"]["fit_warnings"]
    assert isinstance(fws, list)
    assert fws == [
        {"level": "MODEL_FIT_REFUSED", "substrate": "bgnbd"},
        {"level": "PROVISIONAL_SELECTED", "substrate": "rfm"},
    ]
    # Defensive: NO entry is a bare string (the pre-T4 shape).
    for entry in fws:
        assert not isinstance(entry, str), (
            f"S13.6-T4 JSON pin: legacy string shape detected: {entry!r}"
        )


def test_engine_run_roundtrip_preserves_typed_fit_warnings() -> None:
    er = EngineRun(
        recommendations=[
            PlayCard(
                play_id="winback_dormant_cohort",
                model_card_ref=ModelCardRef(
                    fit_warnings=[
                        FitWarning(FitWarningLevel.MODEL_FIT_REFUSED, "bgnbd"),
                        FitWarning(FitWarningLevel.PROVISIONAL_SELECTED, "rfm"),
                    ],
                ),
            )
        ]
    )
    back = EngineRun.from_dict(er.to_dict())
    fws = back.recommendations[0].model_card_ref.fit_warnings
    assert fws == [
        FitWarning(FitWarningLevel.MODEL_FIT_REFUSED, "bgnbd"),
        FitWarning(FitWarningLevel.PROVISIONAL_SELECTED, "rfm"),
    ]
    for fw in fws:
        assert isinstance(fw, FitWarning)
        assert isinstance(fw.level, FitWarningLevel)


# ---------------------------------------------------------------------------
# 7. Strict deserialization — legacy List[str] shape → empty list.
# ---------------------------------------------------------------------------


def test_legacy_string_shape_deserializes_to_empty_list() -> None:
    """Pre-T4 snapshots carry ``fit_warnings: List[str]`` of the form
    ``"{LEVEL}:{substrate}"``. Per strict cutover (T3 precedent per DS
    Q12, operator-only audit field), these deserialize to an empty
    list — no rehydration needed."""
    from src.engine_run import _from_dict_model_card_ref
    legacy = {
        "strategy_used": "RFM",
        "fit_status_chain": [["bgnbd", "REFUSED"], ["rfm", "PROVISIONAL"]],
        "fit_warnings": [
            "MODEL_FIT_REFUSED:bgnbd",
            "PROVISIONAL_SELECTED:rfm",
        ],
    }
    mcr = _from_dict_model_card_ref(legacy)
    assert mcr is not None
    assert mcr.strategy_used == "RFM"
    assert mcr.fit_warnings == []  # strict cutover: legacy strings dropped


# ---------------------------------------------------------------------------
# 8. AST sweep — no producer in src/ constructs the legacy "{LEVEL}:" shape.
# ---------------------------------------------------------------------------


_LEGACY_LEVEL_PREFIXES = (
    "PROVISIONAL_SELECTED:",
    "MODEL_FIT_INSUFFICIENT_DATA:",
    "MODEL_FIT_REFUSED:",
)


def test_no_src_module_constructs_legacy_fit_warning_string_grammar() -> None:
    """Walk every ``src/`` .py file's AST; assert no string-literal of
    the form ``"{LEVEL}:{...}"`` or ``f"{LEVEL}:{...}"`` is constructed
    where LEVEL is one of the 3 FitWarningLevel names.

    The grammar lives in code comments / docstrings (allowed — those
    are not AST string-literals at expression position) but no
    production code path may construct a fit_warning string of that
    shape after T4.
    """
    src_dir = REPO_ROOT / "src"
    assert src_dir.is_dir()
    offenders: list[tuple[str, int, str]] = []
    for py_path in src_dir.rglob("*.py"):
        try:
            source = py_path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            tree = ast.parse(source, filename=str(py_path))
        except SyntaxError:
            continue
        rel = str(py_path.relative_to(REPO_ROOT))

        for node in ast.walk(tree):
            # Plain string-literal: "LEVEL:..."
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for prefix in _LEGACY_LEVEL_PREFIXES:
                    if node.value.startswith(prefix):
                        offenders.append((rel, node.lineno, node.value))
                        break
            # f-string: f"LEVEL:{...}" — first FormattedValue / Constant
            # piece starts with "LEVEL:".
            elif isinstance(node, ast.JoinedStr):
                if not node.values:
                    continue
                first = node.values[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    for prefix in _LEGACY_LEVEL_PREFIXES:
                        if first.value.startswith(prefix):
                            offenders.append(
                                (rel, node.lineno, ast.unparse(node))
                            )
                            break

    # Allow-list: the docstring of ranking_strategy.py contains the
    # historical "LEVEL:..." shape inside a docstring AST string
    # literal — those are top-of-module docstrings (NOT load-bearing
    # producers). Filter them by checking the offender comes from
    # outside docstring-bearing positions. Simpler: scope-allow the
    # tests directory (none should hit anyway) and docstring lines.
    # Since docstrings ARE ast.Constant string literals at module/class/
    # function position, we re-walk and prune those.
    real_offenders = []
    for rel, lineno, text in offenders:
        # Read the surrounding context to check if this is a docstring.
        # Conservative: any Constant whose value starts with a LEVEL: but
        # is the .body[0] of a Module / FunctionDef / ClassDef is a
        # docstring and allowed.
        path = REPO_ROOT / rel
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            real_offenders.append((rel, lineno, text))
            continue
        is_docstring = False
        for parent in ast.walk(tree):
            if isinstance(
                parent,
                (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                body = getattr(parent, "body", None) or []
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                    and body[0].value.lineno == lineno
                ):
                    is_docstring = True
                    break
        if not is_docstring:
            real_offenders.append((rel, lineno, text))

    assert not real_offenders, (
        "S13.6-T4 AST pin: no production code path may construct the "
        "legacy '{LEVEL}:{substrate}' fit-warning string grammar. Use "
        "typed FitWarning(level=FitWarningLevel.X, substrate='...') "
        f"instead. Offenders: {real_offenders}"
    )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
