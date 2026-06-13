"""Per-run manifest writer — S13.7-T2.

Writes ``data/<store_id>/runs/<run_id>/manifest.json`` immediately after
``src.audience_resolver.materialize_audience_csvs`` completes.

The manifest enumerates every artifact produced by a single engine run so
downstream agents (narration MCP, assembly MCP) can locate all relevant
files from a single JSON without scanning the filesystem themselves.

Single-demote-channel invariant
================================

This module is a pure side-effect writer.  It reads ``engine_run`` fields
to build the artifact list; it **never**:

- Appends to or mutates ``engine_run.recommendations``.
- Appends to or mutates any other EngineRun list.
- Calls ``apply_guardrails_to_injected`` or any guardrails path.
- Sets any ``ReasonCode`` on any ``RejectedPlay``.

Pivot 7 (single-demote-channel invariant) is preserved structurally.

Manifest schema (v1.0.0)
=========================

.. code-block:: json

    {
        "schema_version": "1.0.0",
        "run_id": "<run_id>",
        "store_id": "<store_id>",
        "created_at": "<ISO-8601 UTC timestamp>",
        "artifacts": {
            "engine_run": "../<run_id>.json",
            "audiences": [
                {
                    "audience_definition_id": "<aud_def_id>",
                    "path": "audiences/<aud_def_id>.csv",
                    "play_id": "<play_id>",
                    "audience_materialization_status": "MATERIALIZED"
                }
            ],
            "parquets": [
                {
                    "name": "<filename>",
                    "path": "../../predictive/<filename>"
                }
            ],
            "retention": "../../predictive/retention.json"
        }
    }

Audience materialization status values
=======================================

- ``"MATERIALIZED"`` — CSV written with at least one data row.
- ``"SUPPRESSED_SUBSTRATE_REFUSED"`` — empty CSV written (parquet
  missing or unreadable; per DS R4).
- ``"NOT_MATERIALIZED"`` — CSV not written (resolver not invoked or
  run skipped).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .engine_run import EngineRun

# Manifest format version — bump if the top-level manifest shape changes.
_MANIFEST_SCHEMA_VERSION = "1.0.0"


def write_run_manifest(
    engine_run: "EngineRun",
    store_id: str,
    run_id: str,
    data_dir: str,
    audience_statuses: Dict[str, str],
) -> None:
    """Write ``manifest.json`` for the run.

    Note:
        ``artifacts.engine_run`` is a path relative to the manifest's own
        directory. The immutable snapshot lives at
        ``data/<store_id>/runs/<run_id>.json`` (sibling file, one dir up
        from the manifest), so the relative pointer is ``../<run_id>.json``.

    Args:
        engine_run: finalized EngineRun (after guardrails + audience CSV
            materialization). Read-only — this function does NOT mutate it.
        store_id: per-merchant store identifier.
        run_id: run UUID from ``engine_run.run_id``.
        data_dir: root data directory (e.g. "data"). The manifest is
            written to ``<data_dir>/<store_id>/runs/<run_id>/manifest.json``.
        audience_statuses: mapping ``audience_definition_id -> status`` as
            returned by ``src.audience_resolver.materialize_audience_csvs``.
            Status values: ``"MATERIALIZED"`` | ``"SUPPRESSED_SUBSTRATE_REFUSED"``
            | ``"NOT_MATERIALIZED"``.
    """
    data_path = Path(data_dir)
    run_dir = data_path / store_id / "runs" / run_id

    try:
        run_dir.mkdir(parents=True, exist_ok=True)
    except Exception as _mkd_err:
        print(
            f"[RunManifest] Warning: could not create run dir {run_dir}: {_mkd_err}"
        )
        return

    manifest = _build_manifest(
        engine_run=engine_run,
        store_id=store_id,
        run_id=run_id,
        data_path=data_path,
        audience_statuses=audience_statuses,
    )

    manifest_path = run_dir / "manifest.json"
    try:
        with open(manifest_path, "w", encoding="utf-8") as _f:
            json.dump(manifest, _f, indent=2, ensure_ascii=False)
    except Exception as _write_err:
        print(
            f"[RunManifest] Warning: failed to write manifest.json at "
            f"{manifest_path}: {_write_err}"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_manifest(
    *,
    engine_run: "EngineRun",
    store_id: str,
    run_id: str,
    data_path: Path,
    audience_statuses: Dict[str, str],
) -> dict:
    """Build the manifest dict (pure, no file I/O)."""

    created_at = datetime.now(tz=timezone.utc).isoformat()

    audiences = _build_audience_entries(engine_run=engine_run, audience_statuses=audience_statuses)
    parquets = _enumerate_parquets(data_path=data_path, store_id=store_id)
    retention = _retention_path(data_path=data_path, store_id=store_id)

    return {
        "schema_version": _MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "store_id": store_id,
        "created_at": created_at,
        "artifacts": {
            "engine_run": f"../{run_id}.json",
            "audiences": audiences,
            "parquets": parquets,
            "retention": retention,
        },
    }


def _build_audience_entries(
    *,
    engine_run: "EngineRun",
    audience_statuses: Dict[str, str],
) -> List[dict]:
    """Build the ``artifacts.audiences`` list from PlayCards and status dict."""

    entries: List[dict] = []
    seen: set = set()

    cards = list(getattr(engine_run, "recommendations", []) or [])
    cards += list(getattr(engine_run, "recommended_experiments", []) or [])

    for pc in cards:
        play_id = str(getattr(pc, "play_id", "") or "")
        aud = getattr(pc, "audience", None)
        aud_id_raw = getattr(aud, "id", None) if aud is not None else None
        aud_def_id = (
            str(aud_id_raw)
            if isinstance(aud_id_raw, str) and aud_id_raw
            else play_id or "unknown"
        )

        if aud_def_id in seen:
            continue
        seen.add(aud_def_id)

        status = audience_statuses.get(aud_def_id, "NOT_MATERIALIZED")
        entries.append(
            {
                "audience_definition_id": aud_def_id,
                "path": f"audiences/{aud_def_id}.csv",
                "play_id": play_id,
                "audience_materialization_status": status,
            }
        )

    return entries


def _enumerate_parquets(*, data_path: Path, store_id: str) -> List[dict]:
    """Enumerate parquet files under ``data/<store_id>/predictive/``.

    Returns a list of ``{"name": "<filename>", "path": "../../predictive/<filename>"}``
    dicts (path is relative to the run directory).
    """
    predictive_dir = data_path / store_id / "predictive"
    if not predictive_dir.is_dir():
        return []

    parquet_files = sorted(predictive_dir.glob("*.parquet"))
    return [
        {
            "name": pf.name,
            "path": f"../../predictive/{pf.name}",
        }
        for pf in parquet_files
    ]


def _retention_path(*, data_path: Path, store_id: str) -> Optional[str]:
    """Return ``"../../predictive/retention.json"`` if the file exists, else None."""
    retention_json = data_path / store_id / "predictive" / "retention.json"
    if retention_json.exists():
        return "../../predictive/retention.json"
    return None


__all__ = ["write_run_manifest"]
