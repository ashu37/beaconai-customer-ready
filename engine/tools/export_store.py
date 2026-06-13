"""``tools/export_store.py`` — full per-store JSON export (S-2, D-4).

Founder decision D-4 (2026-05-09):

    Full per-store JSON export from Day 1. No selective field filtering,
    no PII redaction toggle (everything-or-nothing).

Bundle structure (top-level keys, sorted):

    {
      "_format": "beaconai.memory_export",
      "_format_version": 1,
      "events": [ <ordered events as ``MemoryStore.query_events`` returns> ],
      "exported_at": "<UTC ISO>",
      "recommended_history": <verbatim parsed JSON, or null>,
      "snapshot_index": [ <listing of data/<store_id>/runs/*.json relpaths if present> ],
      "store_id": "<store_id>",
      "user_version": <int>
    }

Round-trip contract (acceptance test): ``export_store`` then
``import_store`` into an empty ``data/<store_id>/`` yields a
byte-identical export when re-exported.

CLI usage:

    python -m tools.export_store <store_id> --out path.json [--base data]
    python -m tools.export_store <store_id> --import path.json [--base data]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.memory.store import open_memory
from src.store_id import ensure_store_dir, store_data_dir

FORMAT_NAME = "beaconai.memory_export"
FORMAT_VERSION = 1


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


def export_store(
    store_id: str,
    *,
    base: Optional[Path | str] = None,
    exported_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the export bundle for one store. Pure function (no side effects)."""
    store_dir = (
        store_data_dir(store_id, base=base)
        if base is not None
        else store_data_dir(store_id)
    )

    store = (
        open_memory(store_id, base=base)
        if base is not None
        else open_memory(store_id)
    )
    try:
        events = store.query_events()
        user_version = store.user_version()
    finally:
        store.close()

    rec_history_path = store_dir / "recommended_history.json"
    rec_history: Any = None
    if rec_history_path.is_file():
        try:
            rec_history = json.loads(rec_history_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Preserve as raw text if it isn't JSON; round-trip remains stable.
            rec_history = {
                "_raw": rec_history_path.read_text(encoding="utf-8"),
                "_decode_error": True,
            }

    runs_dir = store_dir / "runs"
    snapshot_index: List[str] = []
    snapshots: Dict[str, Any] = {}
    if runs_dir.is_dir():
        for child in sorted(runs_dir.glob("*.json")):
            snapshot_index.append(child.name)
            text = child.read_text(encoding="utf-8")
            try:
                snapshots[child.name] = json.loads(text)
            except json.JSONDecodeError:
                snapshots[child.name] = {"_raw": text, "_decode_error": True}

    return {
        "_format": FORMAT_NAME,
        "_format_version": FORMAT_VERSION,
        "events": events,
        "exported_at": exported_at or _utc_iso_now(),
        "recommended_history": rec_history,
        "snapshot_index": snapshot_index,
        "snapshots": snapshots,
        "store_id": store_id,
        "user_version": user_version,
    }


def export_store_to_file(
    store_id: str,
    out_path: Path | str,
    *,
    base: Optional[Path | str] = None,
    exported_at: Optional[str] = None,
) -> Path:
    bundle = export_store(store_id, base=base, exported_at=exported_at)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_canon(bundle), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------


def import_store(
    bundle: Dict[str, Any],
    *,
    base: Optional[Path | str] = None,
) -> str:
    """Restore a previously-exported bundle into ``data/<store_id>/``.

    Refuses to overwrite an existing populated store: the destination
    ``memory.db`` must be empty (zero events). This prevents an accidental
    import from clobbering live merchant data — D-3's "full wipe only"
    is upstream of this CLI; the operator is responsible for it.

    Returns the ``store_id`` that was restored.
    """
    if bundle.get("_format") != FORMAT_NAME:
        raise ValueError(
            f"unsupported export format: {bundle.get('_format')!r}"
        )
    fv = bundle.get("_format_version")
    if fv != FORMAT_VERSION:
        raise ValueError(
            f"unsupported _format_version: {fv!r} (this build supports {FORMAT_VERSION})"
        )
    store_id = bundle["store_id"]
    if not isinstance(store_id, str) or not store_id:
        raise ValueError("bundle.store_id is missing or empty")

    if base is not None:
        ensure_store_dir(store_id, base=base)
        store_dir = store_data_dir(store_id, base=base)
    else:
        ensure_store_dir(store_id)
        store_dir = store_data_dir(store_id)

    store = (
        open_memory(store_id, base=base)
        if base is not None
        else open_memory(store_id)
    )
    try:
        if store.count_events() != 0:
            raise RuntimeError(
                f"refusing to import: data/{store_id}/memory.db is non-empty "
                f"({store.count_events()} events). Wipe the per-store directory "
                f"first (D-3: full wipe only)."
            )
        for ev in bundle.get("events") or []:
            store.append_event(
                event_id=ev["event_id"],
                event_type=ev["event_type"],
                lineage_id=ev.get("lineage_id"),
                run_id=ev.get("run_id"),
                play_id=ev.get("play_id"),
                audience_definition_id=ev.get("audience_definition_id"),
                audience_definition_version=ev.get("audience_definition_version"),
                event_version=ev.get("event_version", 1),
                created_at=ev["created_at"],
                payload=ev.get("payload") or {},
            )
    finally:
        store.close()

    snapshots = bundle.get("snapshots") or {}
    if snapshots:
        runs_dir = store_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        for name, content in snapshots.items():
            (runs_dir / name).write_text(
                json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                encoding="utf-8",
            )

    rec = bundle.get("recommended_history")
    if rec is not None:
        # Preserve canonical sort_keys=True formatting so two consecutive
        # export → import → export cycles are byte-identical at the bundle
        # layer regardless of original whitespace.
        (store_dir / "recommended_history.json").write_text(
            json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )

    return store_id


def import_store_from_file(
    bundle_path: Path | str, *, base: Optional[Path | str] = None
) -> str:
    bundle = json.loads(Path(bundle_path).read_text(encoding="utf-8"))
    return import_store(bundle, base=base)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _canon(bundle: Dict[str, Any]) -> str:
    return json.dumps(
        bundle, sort_keys=True, indent=2, ensure_ascii=False
    ) + "\n"


def _utc_iso_now() -> str:
    t = time.time()
    secs = int(t)
    micros = int(round((t - secs) * 1_000_000))
    if micros >= 1_000_000:
        secs += 1
        micros -= 1_000_000
    tm = time.gmtime(secs)
    return (
        f"{tm.tm_year:04d}-{tm.tm_mon:02d}-{tm.tm_mday:02d}T"
        f"{tm.tm_hour:02d}:{tm.tm_min:02d}:{tm.tm_sec:02d}.{micros:06d}Z"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="export_store",
        description="Export or import a per-store memory bundle (D-4)",
    )
    p.add_argument("store_id", nargs="?")
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--out", help="export to this path")
    grp.add_argument(
        "--import", dest="import_path", help="import from this path"
    )
    p.add_argument("--base", default=None, help="data root (defaults to 'data')")
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    base = Path(args.base) if args.base else None

    if args.import_path:
        store_id = import_store_from_file(args.import_path, base=base)
        print(f"imported store_id={store_id} from {args.import_path}")
        return 0

    if not args.store_id:
        print("error: store_id is required for --out", file=sys.stderr)
        return 2
    out = export_store_to_file(args.store_id, args.out, base=base)
    print(f"exported store_id={args.store_id} → {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "FORMAT_NAME",
    "FORMAT_VERSION",
    "export_store",
    "export_store_to_file",
    "import_store",
    "import_store_from_file",
]
