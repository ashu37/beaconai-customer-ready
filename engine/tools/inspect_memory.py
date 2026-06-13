"""``tools/inspect_memory.py`` — hand-inspect a per-store memory.db (S-2).

Usage:

    python -m tools.inspect_memory <store_id> [--lineage-id ID] [--type T]
                                              [--run-id R] [--limit N]
                                              [--base data] [--json]

Default output is a human-readable column list. ``--json`` emits one
event per line (NDJSON) with the ``payload`` dict inlined.

Substrate stands alone in S-2; this CLI is the only consumer until S-3
wires the writers.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

from src.memory.store import open_memory


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="inspect_memory",
        description="Inspect events in data/<store_id>/memory.db",
    )
    p.add_argument("store_id")
    p.add_argument("--lineage-id", default=None)
    p.add_argument("--type", dest="event_type", default=None)
    p.add_argument("--run-id", default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument(
        "--base",
        default=None,
        help="data root (defaults to 'data'); useful for tests",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="emit NDJSON instead of the human-readable table",
    )
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    store = open_memory(
        args.store_id, base=Path(args.base) if args.base else None
    )
    try:
        events = store.query_events(
            lineage_id=args.lineage_id,
            event_type=args.event_type,
            run_id=args.run_id,
            limit=args.limit,
        )
        user_version = store.user_version()
    finally:
        store.close()

    if args.json:
        for ev in events:
            print(json.dumps(ev, sort_keys=True, ensure_ascii=False))
        return 0

    if not events:
        print(
            f"(no events for store_id={args.store_id!r} "
            f"lineage_id={args.lineage_id!r} type={args.event_type!r} "
            f"run_id={args.run_id!r})"
        )
        return 0

    print(
        f"{'seq':>5}  {'event_type':<28}  {'lineage_id':<14}  "
        f"{'play_id':<24}  {'created_at':<27}  event_id"
    )
    print("-" * 120)
    for ev in events:
        lid = (ev.get("lineage_id") or "")[:12]
        pid = (ev.get("play_id") or "")[:22]
        print(
            f"{ev['created_seq']:>5}  "
            f"{ev['event_type']:<28}  "
            f"{lid:<14}  "
            f"{pid:<24}  "
            f"{ev['created_at']:<27}  "
            f"{ev['event_id']}"
        )
    print(f"\n{len(events)} event(s); user_version={user_version}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
