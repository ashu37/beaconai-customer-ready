"""Run discovery + manifest-pointer resolution (handoff_architecture.md §2a).

The ONLY entry point is ``data/<store_id>/runs/<run_id>/manifest.json``.
The snapshot is located via the manifest's ``artifacts.engine_run`` pointer
resolved relative to the manifest's own directory:

    (manifest_dir / artifacts.engine_run).resolve()

Since ``artifacts.engine_run == "../<run_id>.json"`` this resolves one
level **up** — a sibling of the run directory. We NEVER hardcode the
snapshot path and NEVER read ``receipts/engine_run.json`` (the mutable
mirror is not authoritative — KI-FE-6).

Parsing is done by importing the schema authority (``src.engine_run``);
no hand-rolled types.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ...engine_run import EngineRun


class RunLocatorError(Exception):
    """Raised when a run cannot be located/resolved via the manifest."""


@dataclass(frozen=True)
class ResolvedRun:
    """A located run: the manifest, the resolved snapshot path, and the
    parsed (immutable) EngineRun."""

    store_id: str
    run_id: str
    manifest_path: Path
    snapshot_path: Path
    engine_run: EngineRun


def manifest_path_for(data_root: Path, store_id: str, run_id: str) -> Path:
    """Compute the canonical manifest path for a (store_id, run_id)."""
    return Path(data_root) / store_id / "runs" / run_id / "manifest.json"


def resolve_snapshot_path(manifest_path: Path) -> Path:
    """Resolve the engine_run snapshot path from a manifest file.

    Reads the manifest, then resolves ``artifacts.engine_run`` relative to
    the manifest's own directory. Source of truth is the pointer — never a
    hardcoded sibling path.
    """
    manifest_path = Path(manifest_path)
    if not manifest_path.is_file():
        raise RunLocatorError(f"manifest.json not found at {manifest_path}")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:  # noqa: BLE001 — surface a clean error
        raise RunLocatorError(f"could not parse manifest at {manifest_path}: {e}") from e

    artifacts = manifest.get("artifacts") or {}
    pointer = artifacts.get("engine_run")
    if not pointer or not isinstance(pointer, str):
        raise RunLocatorError(
            f"manifest at {manifest_path} has no artifacts.engine_run pointer"
        )

    # Guard against ever consuming the mutable mirror.
    if "receipts" in pointer:
        raise RunLocatorError(
            "manifest engine_run pointer points at a receipts/ mirror; "
            "the receipts mirror is NOT authoritative (KI-FE-6)"
        )

    manifest_dir = manifest_path.parent
    snapshot_path = (manifest_dir / pointer).resolve()
    return snapshot_path


def load_run_from_manifest(manifest_path: Path) -> ResolvedRun:
    """Load + parse the EngineRun pointed to by a manifest.

    Returns a :class:`ResolvedRun`. Parsing uses ``EngineRun.from_dict``
    (the schema authority); we never hand-roll types.
    """
    manifest_path = Path(manifest_path)
    snapshot_path = resolve_snapshot_path(manifest_path)

    if not snapshot_path.is_file():
        raise RunLocatorError(
            f"engine_run snapshot not found at resolved path {snapshot_path}"
        )

    try:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:  # noqa: BLE001
        raise RunLocatorError(
            f"could not parse engine_run snapshot at {snapshot_path}: {e}"
        ) from e

    engine_run = EngineRun.from_dict(payload)

    store_id = str(engine_run.store_id or payload.get("store_id") or "unknown")
    run_id = str(engine_run.run_id or payload.get("run_id") or "unknown")

    return ResolvedRun(
        store_id=store_id,
        run_id=run_id,
        manifest_path=manifest_path,
        snapshot_path=snapshot_path,
        engine_run=engine_run,
    )


def load_run(data_root: Path, store_id: str, run_id: str) -> ResolvedRun:
    """Convenience: locate by (store_id, run_id) under a data root."""
    mp = manifest_path_for(Path(data_root), store_id, run_id)
    return load_run_from_manifest(mp)


def validate_snapshot(snapshot_path: Path) -> Optional[str]:
    """Validate the snapshot against schemas/engine_run.v2.json.

    Returns ``None`` on PASS, or a short error string on FAIL. Uses the
    repo validator (``tools/validate_engine_run.validate``). If jsonschema
    is not installed the validator returns False with a clear message; we
    surface that as a non-fatal warning string (the caller decides whether
    to proceed — narration can still run on a parsed EngineRun).
    """
    try:
        import importlib.util

        repo_root = Path(__file__).resolve().parents[3]
        tool_path = repo_root / "tools" / "validate_engine_run.py"
        spec = importlib.util.spec_from_file_location("_ber_validate_engine_run", tool_path)
        if spec is None or spec.loader is None:
            return "validator module could not be loaded"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        ok = mod.validate(Path(snapshot_path))
        return None if ok else "snapshot failed v2.0.0 schema validation"
    except Exception as e:  # noqa: BLE001
        return f"validation could not run: {e}"


__all__ = [
    "ResolvedRun",
    "RunLocatorError",
    "manifest_path_for",
    "resolve_snapshot_path",
    "load_run_from_manifest",
    "load_run",
    "validate_snapshot",
]
