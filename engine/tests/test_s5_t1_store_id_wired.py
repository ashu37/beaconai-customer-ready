"""S5-T1 (KI-3) — ``store_id`` wired into ``load_realization_factors``
from ``src/main.py``.

Before S5-T1, S-5 had added an optional ``store_id`` kwarg to
``calibration_stub.load_realization_factors`` but no call site passed
it; ``v_calibration_state`` was unreachable in production. KI-3 closes
that gap with a single call from ``main.py`` after the
``resolve_store_id`` line, so the substrate read path is reachable
end-to-end (dormant today because no live ``calibration_updated``
writer ships before Phase 9).

This test is structural — it inspects the source text of ``src/main.py``
to pin that the kwarg is passed. Behavioral check: with an empty
substrate, the projected dict matches the canonical empty-shape
contract (legacy behavior preserved).
"""
from __future__ import annotations

import inspect
import re
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.main as engine_main  # noqa: E402
from src.calibration_stub import load_realization_factors  # noqa: E402
from src.memory.views import empty_calibration_state  # noqa: E402


def test_main_py_calls_load_realization_factors_with_store_id() -> None:
    """Structural source-text test: ``src/main.py`` must contain a call
    to ``load_realization_factors`` that passes ``store_id=store_id``
    (the resolved per-merchant scope from
    ``src.store_id.resolve_store_id``).

    The single-line wiring is the KI-3 acceptance contract. Renaming
    the local import alias is allowed (e.g. ``_load_calib`` is in
    today's source) but the kwarg shape must persist.
    """
    src = inspect.getsource(engine_main)
    # Find a call shape: <name>(store_id=store_id) where <name> ends in
    # ``load_realization_factors`` OR is an alias known to bind to it.
    # The canonical surfaces:
    pattern_direct = re.compile(
        r"load_realization_factors\s*\(\s*store_id\s*=\s*store_id\s*\)"
    )
    pattern_aliased = re.compile(
        r"_load_calib\s*\(\s*store_id\s*=\s*store_id\s*\)"
    )
    assert pattern_direct.search(src) or pattern_aliased.search(src), (
        "src/main.py must call load_realization_factors with "
        "``store_id=store_id`` (KI-3 acceptance). If the alias name "
        "changed, update this test in the same commit."
    )


def test_main_py_imports_calibration_stub_loader() -> None:
    """The loader must be imported in ``src/main.py`` (either eagerly
    or lazily). This pins the import surface so a future refactor that
    deletes the call site can't quietly slip past the structural test
    above by removing the import."""
    src = inspect.getsource(engine_main)
    assert "load_realization_factors" in src, (
        "src/main.py must reference load_realization_factors (KI-3)."
    )


# ---------------------------------------------------------------------------
# Behavioral check: empty-substrate parity with pre-S-5 contract
# ---------------------------------------------------------------------------


def test_load_realization_factors_with_store_id_empty_substrate_matches_legacy_shape(
    tmp_path, monkeypatch,
) -> None:
    """KI-3 contract: when ``store_id`` is plumbed but no
    ``calibration_updated`` events exist (today's state), the returned
    dict is byte-identical to the canonical empty-shape contract — i.e.
    engine behavior is unchanged versus the pre-KI-3 call site that
    didn't pass ``store_id``.
    """
    # Redirect the substrate root to a temp dir so this test is hermetic
    # and doesn't touch any real merchant data dir.
    monkeypatch.chdir(tmp_path)
    # Empty memory.db at the expected per-store location
    store_id = "s5_t1_test_store"
    store_dir = tmp_path / "data" / store_id
    store_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(store_dir / "memory.db"))
    conn.close()

    # First call: with a (newly-opened, empty) substrate
    out_with_store_id = load_realization_factors(store_id=store_id)
    # Reference: the canonical empty-shape contract anchor
    expected = empty_calibration_state()
    assert out_with_store_id == expected, (
        f"With store_id passed and zero calibration_updated events present, "
        f"load_realization_factors must return the canonical empty-shape "
        f"dict. Got {out_with_store_id!r}; expected {expected!r}."
    )


def test_load_realization_factors_with_store_id_missing_db_matches_legacy_shape(
    tmp_path, monkeypatch,
) -> None:
    """KI-3 fresh-install path: with ``store_id`` plumbed but no
    ``data/<store_id>/memory.db`` on disk yet (the fresh-install state),
    the function must return the empty-shape dict — the engine MUST
    keep running on a fresh merchant directory."""
    monkeypatch.chdir(tmp_path)
    out = load_realization_factors(store_id="never_existed_store_for_ki3")
    expected = empty_calibration_state()
    assert out == expected, (
        f"On a fresh install (no memory.db), load_realization_factors must "
        f"return the empty-shape dict. Got {out!r}."
    )
