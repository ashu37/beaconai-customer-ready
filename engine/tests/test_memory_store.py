"""S-2 — MemoryStore acceptance tests.

Covers:
- 1000-event append + query-by-lineage_id ordering
- Migration idempotency (re-open is a no-op)
- Forbidden / required argument shapes
- ``query_events`` filters compose
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.memory import compute_lineage_id, open_memory
from src.memory.store import CURRENT_USER_VERSION, MemoryStore


@pytest.fixture
def base(tmp_path: Path) -> Path:
    return tmp_path / "data"


def test_open_creates_db_and_dir(base: Path):
    store = open_memory("beauty_alpha", base=base)
    try:
        assert store.db_path.exists()
        assert store.db_path.parent.name == "beauty_alpha"
        assert store.user_version() == CURRENT_USER_VERSION
        assert store.count_events() == 0
    finally:
        store.close()


def test_append_and_query_by_lineage_preserves_insertion_order(base: Path):
    """Acceptance: 1000 events appended, query-by-lineage_id returns
    them in insertion order."""
    store = open_memory("beauty_alpha", base=base)
    try:
        lid = compute_lineage_id("beauty_alpha", "first_to_second_purchase", "ftsp", 1)
        other_lid = compute_lineage_id(
            "beauty_alpha", "discount_hygiene", "discount_v1", 1
        )
        # Interleave two lineages so the per-lineage ordering test
        # actually proves something.
        for i in range(1000):
            store.append_event(
                event_type="recommendation_emitted",
                lineage_id=lid if i % 2 == 0 else other_lid,
                run_id=f"run_{i // 100}",
                play_id="first_to_second_purchase" if i % 2 == 0 else "discount_hygiene",
                payload={"i": i, "marker": f"event_{i}"},
            )

        assert store.count_events() == 1000

        ordered = store.query_events(lineage_id=lid)
        assert len(ordered) == 500
        markers = [e["payload"]["i"] for e in ordered]
        assert markers == list(range(0, 1000, 2)), "insertion order not preserved"

        ordered_other = store.query_events(lineage_id=other_lid)
        assert len(ordered_other) == 500
        assert [e["payload"]["i"] for e in ordered_other] == list(range(1, 1000, 2))
    finally:
        store.close()


def test_migration_is_idempotent(base: Path):
    """Re-opening an existing db must not crash, must not reset events,
    must not bump user_version."""
    s1 = open_memory("beauty_alpha", base=base)
    s1.append_event(event_type="t", payload={"a": 1})
    v1 = s1.user_version()
    s1.close()

    s2 = open_memory("beauty_alpha", base=base)
    try:
        assert s2.user_version() == v1
        assert s2.count_events() == 1
    finally:
        s2.close()

    # Third open just to triple-check.
    s3 = open_memory("beauty_alpha", base=base)
    try:
        assert s3.user_version() == v1
        assert s3.count_events() == 1
    finally:
        s3.close()


def test_user_version_downgrade_refused(base: Path, monkeypatch):
    """If a future build wrote user_version=99, today's build must refuse
    to open rather than silently downgrade."""
    store = open_memory("beauty_alpha", base=base)
    db_path = store.db_path
    store.close()

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA user_version = 99")
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError, match="user_version=99"):
        MemoryStore(store_id="beauty_alpha", db_path=db_path)


def test_query_filters_compose(base: Path):
    store = open_memory("beauty_alpha", base=base)
    try:
        lid_a = compute_lineage_id("beauty_alpha", "p1", "a1", 1)
        lid_b = compute_lineage_id("beauty_alpha", "p2", "a2", 1)
        store.append_event(event_type="A", lineage_id=lid_a, run_id="r1", payload={})
        store.append_event(event_type="B", lineage_id=lid_a, run_id="r1", payload={})
        store.append_event(event_type="A", lineage_id=lid_b, run_id="r2", payload={})

        assert len(store.query_events(event_type="A")) == 2
        assert len(store.query_events(lineage_id=lid_a)) == 2
        assert len(store.query_events(lineage_id=lid_a, event_type="A")) == 1
        assert len(store.query_events(run_id="r2")) == 1
        assert len(store.query_events(limit=2)) == 2
    finally:
        store.close()


def test_payload_canonicalization(base: Path):
    """Two equivalent dicts with different key insertion order serialize
    the same — matters for export round-trip and any future content hash."""
    store = open_memory("beauty_alpha", base=base)
    try:
        store.append_event(event_type="t", payload={"b": 2, "a": 1})
        store.append_event(event_type="t", payload={"a": 1, "b": 2})
        evs = store.query_events()
        assert evs[0]["payload"] == evs[1]["payload"]
    finally:
        store.close()


def test_invalid_event_type_rejected(base: Path):
    store = open_memory("beauty_alpha", base=base)
    try:
        with pytest.raises(ValueError):
            store.append_event(event_type="", payload={})
        with pytest.raises(ValueError):
            store.append_event(event_type=None, payload={})  # type: ignore[arg-type]
    finally:
        store.close()


def test_invalid_payload_rejected(base: Path):
    store = open_memory("beauty_alpha", base=base)
    try:
        with pytest.raises(ValueError):
            store.append_event(event_type="t", payload="not a dict")  # type: ignore[arg-type]
    finally:
        store.close()


def test_per_store_isolation(base: Path):
    """Two stores under different store_ids never share a database file."""
    a = open_memory("beauty_alpha", base=base)
    b = open_memory("beauty_beta", base=base)
    try:
        a.append_event(event_type="t", payload={"who": "alpha"})
        b.append_event(event_type="t", payload={"who": "beta"})
        assert a.count_events() == 1
        assert b.count_events() == 1
        assert a.db_path != b.db_path
        assert a.query_events()[0]["payload"]["who"] == "alpha"
        assert b.query_events()[0]["payload"]["who"] == "beta"
    finally:
        a.close()
        b.close()


def test_context_manager(base: Path):
    with open_memory("beauty_alpha", base=base) as store:
        store.append_event(event_type="t", payload={})
        assert store.count_events() == 1


def test_event_id_unique_per_call(base: Path):
    store = open_memory("beauty_alpha", base=base)
    try:
        ids = {store.append_event(event_type="t", payload={"i": i}) for i in range(50)}
        assert len(ids) == 50
    finally:
        store.close()


def test_explicit_event_id_collision_rejected(base: Path):
    store = open_memory("beauty_alpha", base=base)
    try:
        eid = "fixed_id_001"
        store.append_event(event_type="t", payload={}, event_id=eid)
        with pytest.raises(ValueError):
            store.append_event(event_type="t", payload={}, event_id=eid)
    finally:
        store.close()


def test_created_seq_is_strictly_monotonic(base: Path):
    store = open_memory("beauty_alpha", base=base)
    try:
        for i in range(20):
            store.append_event(event_type="t", payload={"i": i})
        seqs = [e["created_seq"] for e in store.query_events()]
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == len(seqs)
    finally:
        store.close()
