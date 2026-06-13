"""S-4 — Immutable snapshot discipline + sha256 helper.

Every engine run writes its ``engine_run.json`` to an immutable per-run
path::

    data/<store_id>/runs/<run_id>.json

This file is never overwritten. ``receipts/engine_run.json`` is kept as
a **byte-identical** mutable mirror of the latest immutable snapshot so
existing Swarm consumers see no change.

The sha256 of the immutable snapshot file (computed at write time, on
the bytes actually written to disk) is recorded on every
``recommendation_emitted`` / ``recommendation_considered`` event payload
emitted from that run via :data:`RecommendationEmittedPayload.snapshot_sha256`.
That field is the load-bearing surface for downstream verification: a
later auditor can re-hash the snapshot file and assert it matches the
sha256 stored on the event row.

Hard rules:
  * The immutable snapshot path is the *single* source of truth for the
    sha256. We hash the on-disk bytes after writing, not the in-memory
    dict, so we hash exactly what the auditor will hash.
  * If the immutable file already exists we refuse rather than
    overwrite (raises ``FileExistsError``). Per-run uuid4 ``run_id``
    makes accidental collisions astronomically unlikely; an actual
    collision points to a bug we want to surface, not paper over.
  * The mutable mirror is written by ``shutil.copyfile`` to guarantee
    byte-identity — never re-serialised.
  * No new dependencies; ``hashlib.sha256`` from stdlib only.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, Dict, Tuple

from ..utils import write_json


def write_immutable_snapshot(
    *,
    engine_run_dict: Dict[str, Any],
    store_dir: Path,
    receipts_dir: Path,
    run_id: str,
) -> Tuple[Path, str]:
    """Write the slate JSON to an immutable per-run path and mirror it
    byte-identically into ``receipts/engine_run.json``.

    Returns ``(immutable_path, sha256_hex)``.

    ``immutable_path`` is ``<store_dir>/runs/<run_id>.json``. Caller is
    responsible for passing a non-empty ``run_id``; we raise
    ``ValueError`` rather than silently inventing one.
    """

    if not run_id:
        raise ValueError(
            "write_immutable_snapshot requires a non-empty run_id; "
            "engine_run.run_id was empty/None"
        )

    # Resolve to an absolute path so the value stored on event payloads
    # remains valid regardless of the consumer's cwd. The engine and
    # tests run with different cwds; the on-disk substrate is the single
    # source of truth and must self-locate.
    runs_dir = (Path(store_dir) / "runs").resolve()
    runs_dir.mkdir(parents=True, exist_ok=True)
    immutable_path = runs_dir / f"{run_id}.json"

    if immutable_path.exists():
        # Per-run uuid4 collision is effectively impossible; this points
        # to a bug (e.g. caller re-using a run_id across runs) we want
        # to surface, not paper over.
        raise FileExistsError(
            f"refusing to overwrite immutable snapshot at {immutable_path}; "
            "run_id collision indicates a caller bug"
        )

    # Write via the existing JSON writer so the on-disk shape is
    # identical to the legacy receipts/engine_run.json (indent=2,
    # default=str) — the M0 byte-identity contract depends on this.
    write_json(str(immutable_path), engine_run_dict)

    # Hash the bytes actually written, not the in-memory dict.
    sha256_hex = _sha256_file(immutable_path)

    # Mirror byte-identically to receipts/engine_run.json.
    Path(receipts_dir).mkdir(parents=True, exist_ok=True)
    mirror_path = Path(receipts_dir) / "engine_run.json"
    shutil.copyfile(str(immutable_path), str(mirror_path))

    return immutable_path, sha256_hex


def verify_snapshot(snapshot_path: Path | str, expected_sha256: str) -> bool:
    """Return True iff the file's sha256 matches ``expected_sha256``.

    Used by the S-4 mutation acceptance test: hand-edit a snapshot byte,
    rerun this helper, assert mismatch raised by the caller. We
    deliberately DO NOT raise here; the caller decides the failure mode
    (test asserts ``False``; production audit raises). Keeping this
    function pure-comparison makes it safe to import from anywhere.
    """

    p = Path(snapshot_path)
    if not p.exists():
        return False
    return _sha256_file(p) == expected_sha256


def _sha256_file(path: Path) -> str:
    """Return the hex sha256 of the file at ``path``.

    Streams the file in 64 KiB chunks so an outsized snapshot doesn't
    blow memory. Today's snapshots are tens of KB; the chunking is
    defensive rather than necessary.
    """

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


__all__ = [
    "write_immutable_snapshot",
    "verify_snapshot",
]
