"""Per-merchant ``store_id`` resolution and per-store data directory layout.

B-4/S-1. Resolves a single canonical ``store_id`` per engine run and routes
all tenant-data writes/reads under ``data/<store_id>/``.

Resolution precedence (first non-empty wins):

    1. ``STORE_ID`` env override
    2. ``--brand`` CLI arg (passed in as ``brand_arg``)
    3. basename of the orders-CSV's parent directory
    4. literal ``"unknown"`` (matches existing engine_run_adapter fallback)

The resolved value is sanitized to ``[a-z0-9_-]+`` so a hostile or
unexpected basename can never escape the per-store directory.

The substrate (Sprint 2 onwards) lives at ``data/<store_id>/memory.db``;
Sprint 1 only relocates ``recommended_history.json`` and any future
tenant-data artifacts under the same root.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

DEFAULT_BASE = Path("data")
FALLBACK_STORE_ID = "unknown"

_SAFE_CHAR = re.compile(r"[^a-z0-9_-]+")


def _sanitize(value: str) -> str:
    """Lowercase + strip to ``[a-z0-9_-]+``; empty result becomes the fallback."""
    if not value:
        return FALLBACK_STORE_ID
    out = _SAFE_CHAR.sub("-", value.strip().lower()).strip("-_")
    return out or FALLBACK_STORE_ID


def resolve_store_id(
    orders_csv_path: Optional[str | Path] = None,
    *,
    brand_arg: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> str:
    """Resolve a canonical ``store_id`` for this engine run.

    See module docstring for precedence. Returns a sanitized, non-empty
    string suitable for use as a directory name.
    """
    env = env if env is not None else os.environ
    raw = env.get("STORE_ID") or brand_arg
    if not raw and orders_csv_path is not None:
        try:
            raw = Path(orders_csv_path).resolve().parent.name
        except (OSError, ValueError):
            raw = None
    return _sanitize(raw or FALLBACK_STORE_ID)


def store_data_dir(store_id: str, base: Path | str = DEFAULT_BASE) -> Path:
    """Return ``<base>/<store_id>``. Does NOT create the directory."""
    return Path(base) / _sanitize(store_id)


def ensure_store_dir(store_id: str, base: Path | str = DEFAULT_BASE) -> Path:
    """Create ``<base>/<store_id>/`` if missing, return the path."""
    p = store_data_dir(store_id, base=base)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _sha256_of(p: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def migrate_legacy_recommended_history(
    store_id: str,
    base: Path | str = DEFAULT_BASE,
) -> Dict[str, Any]:
    """Idempotent copy-with-attribution of the legacy shared history file.

    If ``<base>/recommended_history.json`` exists AND
    ``<base>/<store_id>/recommended_history.json`` does NOT, copy the
    legacy file into the per-store path and write a sibling
    ``.migration.json`` recording (source, timestamp, sha256). Never
    deletes the legacy file (deletion is D-3 "full wipe only", out of
    scope here). All failures are reported via the returned status dict;
    nothing raises.
    """
    base = Path(base)
    legacy = base / "recommended_history.json"
    dest_dir = store_data_dir(store_id, base=base)
    dest = dest_dir / "recommended_history.json"

    status: Dict[str, Any] = {
        "store_id": store_id,
        "legacy_path": str(legacy),
        "dest_path": str(dest),
    }

    if not legacy.exists() or not legacy.is_file():
        status["status"] = "no_legacy"
        return status
    if dest.exists():
        status["status"] = "dest_exists"
        return status

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, dest)
        sidecar = {
            "source_path": str(legacy),
            "copied_at": datetime.now(timezone.utc).isoformat(),
            "source_sha256": _sha256_of(legacy),
            "store_id": store_id,
        }
        (dest_dir / ".migration.json").write_text(
            json.dumps(sidecar, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        status["status"] = "migrated"
    except OSError as e:
        status["status"] = "error"
        status["error"] = str(e)
    return status


__all__ = [
    "DEFAULT_BASE",
    "FALLBACK_STORE_ID",
    "resolve_store_id",
    "store_data_dir",
    "ensure_store_dir",
    "migrate_legacy_recommended_history",
]
