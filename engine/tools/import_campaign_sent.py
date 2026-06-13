"""``tools/import_campaign_sent.py`` — manual ``campaign_sent`` import (S-6).

Reads JSON files from ``data/<store_id>/inbox/campaigns/*.json``,
validates each against the v1 ``CampaignSentPayload`` schema, and
appends one ``campaign_sent`` event per validated file to the per-store
substrate (``data/<store_id>/memory.db``).

This module is the **single writer** for the ``campaign_sent`` event
type — enforced by ``tests/test_single_writer_per_event_type.py``. The
engine NEVER calls this tool. File boundary is the discipline (D-5
manual JSON import only).

Validation contract (strict for v1):

  * malformed JSON → file refused, no event appended
  * missing any required field → file refused
  * any unknown top-level key → file refused (strict mode)
  * ``audience_size`` not a non-negative int → file refused
  * ``channel`` outside ``CAMPAIGN_SENT_ALLOWED_CHANNELS`` → file refused
  * ``lineage_id`` does not match any ``recommendation_emitted`` event
    in this store → file refused (orphan campaigns are rejected)
  * ``recommendation_event_id`` does not exist in this store → file
    refused
  * ``campaign_id`` already used by a prior ``campaign_sent`` event in
    this store → file refused (within-store dedupe is the importer's
    responsibility, not the engine's)

Each validation outcome is reported on stdout (one line per file) and
the process exits non-zero if any file failed and ``--strict`` is set
(default).

Usage:

    python -m tools.import_campaign_sent <store_id> [--inbox PATH]
                                                    [--base data]
                                                    [--dry-run]
                                                    [--no-strict]

Default inbox is ``data/<store_id>/inbox/campaigns/`` (auto-created on
first run if missing). On successful import, files are NOT moved or
deleted — the operator is responsible for cleanup. Re-running the
importer over the same file will refuse it on the duplicate-
``campaign_id`` check, so re-runs are safe.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.memory.events import (
    CAMPAIGN_SENT_ALLOWED_CHANNELS,
    CAMPAIGN_SENT_EVENT_VERSION,
    CAMPAIGN_SENT_OPTIONAL_FIELDS,
    CAMPAIGN_SENT_REQUIRED_FIELDS,
    CampaignSentPayload,
)
from src.memory.store import MemoryStore, open_memory
from src.store_id import ensure_store_dir, store_data_dir


CAMPAIGN_SENT_EVENT_TYPE = "campaign_sent"
"""Single literal for this event type. Lives here so the
single-writer grep guard sees this file and only this file mentioning
the literal among ``src/`` and ``tools/``."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImportOutcome:
    """One result row per inbox file processed."""

    path: Path
    status: str  # "imported" | "refused" | "dry_run_ok"
    reason: Optional[str] = None
    event_id: Optional[str] = None


def _validate_payload_shape(
    raw: Any,
) -> Tuple[Optional[CampaignSentPayload], Optional[str]]:
    """Validate one parsed-JSON object against the v1 schema.

    Returns ``(payload, None)`` on success or ``(None, reason)`` on
    refusal. Pure function — no I/O.
    """
    if not isinstance(raw, dict):
        return None, "top-level JSON must be an object"

    keys = set(raw.keys())
    missing = CAMPAIGN_SENT_REQUIRED_FIELDS - keys
    if missing:
        return None, f"missing required field(s): {sorted(missing)}"

    allowed = CAMPAIGN_SENT_REQUIRED_FIELDS | CAMPAIGN_SENT_OPTIONAL_FIELDS
    unknown = keys - allowed
    if unknown:
        return None, (
            f"unknown field(s) (strict v1 mode): {sorted(unknown)}; "
            f"allowed: {sorted(allowed)}"
        )

    # Type / value checks on required fields.
    for k in ("lineage_id", "recommendation_event_id", "campaign_id",
              "sent_at", "channel"):
        v = raw[k]
        if not isinstance(v, str) or not v:
            return None, f"field {k!r} must be a non-empty string"

    audience_size = raw["audience_size"]
    if isinstance(audience_size, bool) or not isinstance(audience_size, int):
        return None, "field 'audience_size' must be an int"
    if audience_size < 0:
        return None, "field 'audience_size' must be >= 0"

    if raw["channel"] not in CAMPAIGN_SENT_ALLOWED_CHANNELS:
        return None, (
            f"field 'channel' = {raw['channel']!r} not in "
            f"{sorted(CAMPAIGN_SENT_ALLOWED_CHANNELS)}"
        )

    # Optional field type checks (only if present).
    for k in ("campaign_name", "provider", "provider_message_id", "notes"):
        if k in raw:
            v = raw[k]
            if v is not None and (not isinstance(v, str) or v == ""):
                return None, f"optional field {k!r} must be a non-empty string or omitted"

    payload = CampaignSentPayload(
        event_version=CAMPAIGN_SENT_EVENT_VERSION,
        lineage_id=raw["lineage_id"],
        recommendation_event_id=raw["recommendation_event_id"],
        campaign_id=raw["campaign_id"],
        sent_at=raw["sent_at"],
        audience_size=audience_size,
        channel=raw["channel"],
        campaign_name=raw.get("campaign_name"),
        provider=raw.get("provider"),
        provider_message_id=raw.get("provider_message_id"),
        notes=raw.get("notes"),
    )
    return payload, None


def _validate_against_substrate(
    payload: CampaignSentPayload, store: MemoryStore
) -> Optional[str]:
    """Cross-check payload against the live substrate.

    Returns ``None`` on success or a refusal reason on failure.
    Performs three queries:

    1. ``lineage_id`` exists on at least one ``recommendation_emitted``
       event in this store.
    2. ``recommendation_event_id`` is the ``event_id`` of an event
       in this store (additionally that event has the matching
       ``lineage_id`` — otherwise the operator stitched a wrong pair).
    3. ``campaign_id`` is not already used by a prior ``campaign_sent``
       event in this store.
    """
    # 1. lineage_id matches at least one recommendation_emitted event.
    rec_rows = store.query_events(
        lineage_id=payload.lineage_id,
        event_type="recommendation_emitted",
        limit=1,
    )
    if not rec_rows:
        return (
            f"lineage_id {payload.lineage_id!r} does not match any "
            f"recommendation_emitted event in this store"
        )

    # 2. recommendation_event_id is a known event_id in this store and
    # its lineage_id matches.
    assert store._conn is not None  # noqa: SLF001
    with store._lock:  # noqa: SLF001
        cur = store._conn.execute(
            "SELECT event_type, lineage_id FROM events WHERE event_id = ?",
            (payload.recommendation_event_id,),
        )
        row = cur.fetchone()
    if row is None:
        return (
            f"recommendation_event_id {payload.recommendation_event_id!r} "
            f"does not exist in this store"
        )
    if row["event_type"] != "recommendation_emitted":
        return (
            f"recommendation_event_id {payload.recommendation_event_id!r} "
            f"refers to a {row['event_type']!r} event, not "
            f"recommendation_emitted"
        )
    if row["lineage_id"] != payload.lineage_id:
        return (
            f"recommendation_event_id {payload.recommendation_event_id!r} "
            f"has lineage_id {row['lineage_id']!r} but payload claims "
            f"{payload.lineage_id!r}"
        )

    # 3. campaign_id not already used.
    existing = store.query_events(event_type=CAMPAIGN_SENT_EVENT_TYPE)
    for ev in existing:
        prior = ev.get("payload", {}) or {}
        if isinstance(prior, dict) and prior.get("campaign_id") == payload.campaign_id:
            return (
                f"duplicate campaign_id {payload.campaign_id!r}; already "
                f"recorded by event_id {ev['event_id']!r}"
            )

    return None


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> Tuple[Optional[Any], Optional[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return None, f"could not read file: {e}"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"malformed JSON: {e}"


def import_one(
    path: Path, store: MemoryStore, *, dry_run: bool = False
) -> ImportOutcome:
    """Validate and (unless dry-run) append one ``campaign_sent`` event.

    Pure with respect to the filesystem outside the substrate; never
    moves or deletes the inbox file.
    """
    raw, err = _read_json(path)
    if err is not None:
        return ImportOutcome(path=path, status="refused", reason=err)
    payload, err = _validate_payload_shape(raw)
    if err is not None or payload is None:
        return ImportOutcome(path=path, status="refused", reason=err)
    err = _validate_against_substrate(payload, store)
    if err is not None:
        return ImportOutcome(path=path, status="refused", reason=err)
    if dry_run:
        return ImportOutcome(path=path, status="dry_run_ok")
    event_id = store.append_event(
        event_type=CAMPAIGN_SENT_EVENT_TYPE,
        payload=payload.to_dict(),
        lineage_id=payload.lineage_id,
        event_version=payload.event_version,
    )
    return ImportOutcome(path=path, status="imported", event_id=event_id)


def import_inbox(
    store_id: str,
    *,
    inbox: Optional[Path] = None,
    base: Optional[Path | str] = None,
    dry_run: bool = False,
) -> List[ImportOutcome]:
    """Import every ``*.json`` file from the inbox directory.

    Files are processed in lexicographic name order so behaviour is
    deterministic across filesystems with arbitrary ``readdir`` order.
    """
    ensure_store_dir(store_id, base=base) if base is not None else ensure_store_dir(store_id)
    store_dir = (
        store_data_dir(store_id, base=base)
        if base is not None
        else store_data_dir(store_id)
    )
    inbox_dir = inbox if inbox is not None else (store_dir / "inbox" / "campaigns")
    inbox_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in inbox_dir.glob("*.json") if p.is_file())
    if not files:
        return []

    store = open_memory(store_id, base=base) if base is not None else open_memory(store_id)
    try:
        return [import_one(p, store, dry_run=dry_run) for p in files]
    finally:
        store.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_outcome(o: ImportOutcome) -> str:
    if o.status == "imported":
        return f"[ok]      {o.path.name}  event_id={o.event_id}"
    if o.status == "dry_run_ok":
        return f"[dry-run] {o.path.name}  (would import)"
    return f"[refused] {o.path.name}  reason={o.reason}"


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="import_campaign_sent",
        description=(
            "Validate and import campaign_sent JSON files from "
            "data/<store_id>/inbox/campaigns/ into the per-store substrate."
        ),
    )
    p.add_argument("store_id")
    p.add_argument(
        "--inbox",
        default=None,
        help="override the default inbox directory",
    )
    p.add_argument(
        "--base",
        default=None,
        help="data root (defaults to 'data'); useful for tests",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="validate only; do not append events",
    )
    p.add_argument(
        "--no-strict",
        action="store_true",
        help=(
            "exit 0 even if some files were refused; default is exit 1 "
            "if any refusal occurred"
        ),
    )
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    outcomes = import_inbox(
        args.store_id,
        inbox=Path(args.inbox) if args.inbox else None,
        base=Path(args.base) if args.base else None,
        dry_run=args.dry_run,
    )
    if not outcomes:
        print(f"(no JSON files found in inbox for store_id={args.store_id!r})")
        return 0
    for o in outcomes:
        print(_format_outcome(o))
    refused = [o for o in outcomes if o.status == "refused"]
    print(
        f"\n{len(outcomes)} file(s) processed; "
        f"{sum(1 for o in outcomes if o.status == 'imported')} imported, "
        f"{sum(1 for o in outcomes if o.status == 'dry_run_ok')} dry-run-ok, "
        f"{len(refused)} refused."
    )
    if refused and not args.no_strict:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
