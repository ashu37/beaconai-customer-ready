"""S-2 acceptance: 2 processes × 100 events → 200 distinct event_ids,
zero corruption.

Uses ``multiprocessing`` via ``spawn`` so the child re-imports the module
cleanly (no shared sqlite connection inherited via fork).
"""
from __future__ import annotations

import multiprocessing as mp
import os
from pathlib import Path

from src.memory import open_memory


def _worker(base_str: str, store_id: str, n: int, marker: str) -> None:
    base = Path(base_str)
    store = open_memory(store_id, base=base)
    try:
        for i in range(n):
            store.append_event(
                event_type="recommendation_emitted",
                payload={"marker": marker, "i": i, "pid": os.getpid()},
            )
    finally:
        store.close()


def test_two_processes_one_hundred_events_each(tmp_path: Path):
    base = tmp_path / "data"
    store_id = "beauty_alpha"

    # Pre-create the db so both children are pure-appenders (matches the
    # production shape: per-store dir already exists at first write).
    pre = open_memory(store_id, base=base)
    pre.close()

    ctx = mp.get_context("spawn")
    procs = [
        ctx.Process(target=_worker, args=(str(base), store_id, 100, "A")),
        ctx.Process(target=_worker, args=(str(base), store_id, 100, "B")),
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=45)
        assert p.exitcode == 0, f"worker failed: exitcode={p.exitcode}"

    store = open_memory(store_id, base=base)
    try:
        events = store.query_events()
        # 200 events, all distinct event_ids
        assert len(events) == 200
        assert len({e["event_id"] for e in events}) == 200
        markers = {e["payload"]["marker"] for e in events}
        assert markers == {"A", "B"}
        # Workers ran in distinct processes, not the parent.
        pids = {e["payload"]["pid"] for e in events}
        assert len(pids) == 2, f"expected 2 worker pids, got {pids}"
        assert os.getpid() not in pids
        # 100 from A, 100 from B
        assert sum(1 for e in events if e["payload"]["marker"] == "A") == 100
        assert sum(1 for e in events if e["payload"]["marker"] == "B") == 100
        # created_seq is unique and strictly increasing
        seqs = [e["created_seq"] for e in events]
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == 200
    finally:
        store.close()
