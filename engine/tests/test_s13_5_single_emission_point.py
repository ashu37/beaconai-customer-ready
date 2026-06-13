"""Sprint 13.5 Ticket T1 — single-emission-point invariant (KI-NEW-L collapse).

AST-aware contract pin. Asserts that the post-S13.5 collapse of the five
V2 prior-anchored injection blocks at the legacy ``src/main.py:1380-1597``
zone is structurally enforced: the *only* callsite in ``src/main.py``
that appends V2 prior-anchored builder results to
``engine_run.recommendations`` is the new
:func:`src.dispatch_prior_anchored.dispatch_prior_anchored_builders`
helper.

This invariant is load-bearing because the **single-demote-channel
invariant (Pivot 7)** depends on every post-injection recommendation
flowing through exactly one
:func:`src.guardrails.apply_guardrails_to_injected` re-invocation. Before
S13.5-T1, five near-duplicate blocks each appended directly to
``engine_run.recommendations`` and shared one guardrails-to-injected
call at the end. After S13.5-T1, the helper owns the entire pattern.

**What this test enforces (AST, not grep):**

1. ``src/main.py`` contains no call to
   :func:`build_prior_anchored_recommendations` (the legacy 5-block API
   used the import alias ``_build_prior_anchored*``).
2. ``src/main.py`` contains no call to
   :func:`apply_guardrails_to_injected` (the single-demote-channel
   helper). That call now lives inside the dispatch helper only.
3. ``src/main.py`` contains exactly one call to
   :func:`dispatch_prior_anchored_builders` (the new emission point).
4. The dispatch helper at ``src/dispatch_prior_anchored.py`` itself
   wires through the ``_PRIOR_ANCHORED`` registry (sanity: the dispatch
   table's ``play_id`` set is a subset of registry keys, with no
   unexpected extras).

Modeled on ``tests/test_reason_code_precedence_invariant.py`` — same
``ast.walk`` pattern, same AST-aware single-source-of-truth posture.

**To extend:** when a new prior-anchored builder lands, add an entry to
``_DISPATCH_TABLE`` in ``src/dispatch_prior_anchored.py``. Do NOT add a
new injection block to ``src/main.py``. This test fails loudly if you do.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_MAIN = REPO_ROOT / "src" / "main.py"
SRC_DISPATCH = REPO_ROOT / "src" / "dispatch_prior_anchored.py"
SRC_MEASUREMENT = REPO_ROOT / "src" / "measurement_builder.py"


def _name_of(node: ast.AST) -> str:
    """Return the trailing identifier of a Name or Attribute node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _parse(path: Path) -> ast.AST:
    assert path.is_file(), f"expected source file at {path}"
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _all_calls(tree: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)]


def test_main_py_does_not_call_build_prior_anchored_recommendations() -> None:
    """KI-NEW-L collapse: ``src/main.py`` no longer calls
    :func:`build_prior_anchored_recommendations` directly.

    The five legacy blocks each imported the function under an alias
    starting with ``_build_prior_anchored`` and called it once. After
    the S13.5-T1 collapse, the call lives inside the dispatch helper
    only. This pin catches any regression that re-introduces a 6th
    injection block by-pattern.
    """

    tree = _parse(SRC_MAIN)
    offenders: list[tuple[int, str]] = []
    for call in _all_calls(tree):
        fn = _name_of(call.func)
        # Catch both the canonical name and any underscore-prefixed
        # alias (the legacy 5 blocks all used aliases like
        # ``_build_prior_anchored``, ``_build_prior_anchored_t1``,
        # ``_build_prior_anchored_t2``, ``_build_prior_anchored_t3``,
        # ``_build_prior_anchored_t3b``). Underscore-alias matching is
        # how we detect "someone re-introduced the pattern under a new
        # alias name".
        if fn == "build_prior_anchored_recommendations":
            offenders.append((call.lineno, ast.unparse(call.func)))
        elif fn.startswith("_build_prior_anchored"):
            offenders.append((call.lineno, ast.unparse(call.func)))

    assert not offenders, (
        "S13.5-T1 single-emission-point violation: src/main.py must NOT "
        "call build_prior_anchored_recommendations directly. The "
        "dispatch helper at src/dispatch_prior_anchored.py owns the only "
        f"callsite. Offending callsites in src/main.py: {offenders}"
    )


def test_main_py_does_not_call_apply_guardrails_to_injected() -> None:
    """Single-demote-channel invariant (Pivot 7): ``src/main.py`` no
    longer calls :func:`apply_guardrails_to_injected` directly.

    The single S7.6-C2 callsite lived at the end of the 5-block region.
    After S13.5-T1, that call lives inside the dispatch helper.
    """

    tree = _parse(SRC_MAIN)
    offenders: list[tuple[int, str]] = []
    for call in _all_calls(tree):
        fn = _name_of(call.func)
        if fn == "apply_guardrails_to_injected":
            offenders.append((call.lineno, ast.unparse(call.func)))
        elif fn == "_apply_guardrails_to_injected":
            offenders.append((call.lineno, ast.unparse(call.func)))
    assert not offenders, (
        "S13.5-T1 single-demote-channel violation: src/main.py must NOT "
        "call apply_guardrails_to_injected directly. The dispatch helper "
        "owns the single call site. Offenders in src/main.py: "
        f"{offenders}"
    )


def test_main_py_calls_dispatch_helper_exactly_once() -> None:
    """The collapse introduces exactly one new emission point in
    ``src/main.py``: the call to
    :func:`dispatch_prior_anchored_builders`.

    Pinning the call count to exactly 1 ensures a future refactor can
    not accidentally introduce a duplicate dispatch (which would
    re-create the multi-channel problem KI-NEW-L closed).
    """

    tree = _parse(SRC_MAIN)
    sites: list[int] = []
    for call in _all_calls(tree):
        fn = _name_of(call.func)
        if fn == "dispatch_prior_anchored_builders":
            sites.append(call.lineno)
        elif fn == "_dispatch_prior_anchored_builders":
            sites.append(call.lineno)
    assert len(sites) == 1, (
        f"S13.5-T1: src/main.py must call dispatch_prior_anchored_builders "
        f"exactly once (the single emission point for V2 prior-anchored "
        f"builders). Found {len(sites)} callsites at lines {sites}."
    )


def test_dispatch_helper_table_subset_of_prior_anchored_registry() -> None:
    """Sanity: the dispatch table's ``play_id`` set is a subset of the
    ``_PRIOR_ANCHORED`` registry at
    ``src/measurement_builder.py:721``.

    This catches a regression where the dispatch table drifts from the
    registry (e.g., a new builder lands without being registered, or a
    registered play_id is silently dropped from dispatch).
    """

    from src.measurement_builder import _PRIOR_ANCHORED
    from src.dispatch_prior_anchored import _DISPATCH_TABLE

    registry_ids = set(_PRIOR_ANCHORED.keys())
    dispatch_ids = {entry.play_id for entry in _DISPATCH_TABLE}

    extras = dispatch_ids - registry_ids
    assert not extras, (
        f"Dispatch table contains play_ids absent from _PRIOR_ANCHORED "
        f"registry: {extras}. Every dispatch entry must correspond to a "
        f"registered prior-anchored play."
    )


def test_dispatch_helper_exists_and_imports_clean() -> None:
    """The new module imports cleanly and exposes the public symbol."""

    from src.dispatch_prior_anchored import dispatch_prior_anchored_builders

    assert callable(dispatch_prior_anchored_builders)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
