"""S-2 — D-4 export → import → re-export round-trip.

Acceptance contract: events list, recommended_history, snapshot_index,
store_id, and user_version all survive a full round trip byte-identical
(modulo the inherently-changing ``exported_at`` timestamp, which we pin
explicitly in the test).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.memory import compute_lineage_id, open_memory
from tools.export_store import (
    FORMAT_NAME,
    FORMAT_VERSION,
    export_store,
    export_store_to_file,
    import_store,
    import_store_from_file,
)


def _seed_store(base: Path, store_id: str = "beauty_alpha") -> None:
    store = open_memory(store_id, base=base)
    try:
        lid_a = compute_lineage_id(store_id, "first_to_second_purchase", "ftsp", 1)
        lid_b = compute_lineage_id(store_id, "discount_hygiene", "discount_v1", 1)
        store.append_event(
            event_type="recommendation_emitted",
            lineage_id=lid_a,
            run_id="r0",
            play_id="first_to_second_purchase",
            audience_definition_id="ftsp",
            audience_definition_version=1,
            payload={"projected_lift": 0.12, "audience_size": 1247},
        )
        store.append_event(
            event_type="recommendation_considered",
            lineage_id=lid_b,
            run_id="r0",
            play_id="discount_hygiene",
            audience_definition_id="discount_v1",
            audience_definition_version=1,
            payload={"reason_code": "MATERIALITY_BELOW_FLOOR"},
        )
    finally:
        store.close()


def _seed_recommended_history(base: Path, store_id: str = "beauty_alpha") -> None:
    from src.store_id import ensure_store_dir, store_data_dir

    ensure_store_dir(store_id, base=base)
    p = store_data_dir(store_id, base=base) / "recommended_history.json"
    p.write_text(
        json.dumps([{"play_id": "winback", "ts": "2026-05-09"}], sort_keys=True),
        encoding="utf-8",
    )


def _seed_snapshot_runs(base: Path, store_id: str = "beauty_alpha") -> None:
    from src.store_id import ensure_store_dir, store_data_dir

    ensure_store_dir(store_id, base=base)
    runs = store_data_dir(store_id, base=base) / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "20260509T120000Z.json").write_text("{}", encoding="utf-8")
    (runs / "20260509T130000Z.json").write_text("{}", encoding="utf-8")


def test_export_bundle_shape(tmp_path: Path):
    base = tmp_path / "data"
    _seed_store(base)
    bundle = export_store("beauty_alpha", base=base, exported_at="FIXED")
    assert bundle["_format"] == FORMAT_NAME
    assert bundle["_format_version"] == FORMAT_VERSION
    assert bundle["store_id"] == "beauty_alpha"
    assert bundle["exported_at"] == "FIXED"
    assert isinstance(bundle["events"], list)
    assert len(bundle["events"]) == 2
    assert bundle["user_version"] >= 1
    assert bundle["recommended_history"] is None
    assert bundle["snapshot_index"] == []


def test_round_trip_byte_identical(tmp_path: Path):
    """Export → wipe → import → re-export. The events list and metadata
    must come back byte-identical (modulo exported_at, pinned)."""
    base = tmp_path / "data"
    _seed_store(base)
    _seed_recommended_history(base)
    _seed_snapshot_runs(base)

    out = tmp_path / "bundle.json"
    export_store_to_file("beauty_alpha", out, base=base, exported_at="T0")

    bundle1 = json.loads(out.read_text(encoding="utf-8"))

    # Wipe (D-3: full wipe only) — drop the per-store directory.
    import shutil

    shutil.rmtree(base / "beauty_alpha")

    import_store_from_file(out, base=base)

    # Re-export with the same pinned timestamp.
    out2 = tmp_path / "bundle2.json"
    export_store_to_file("beauty_alpha", out2, base=base, exported_at="T0")

    bundle2 = json.loads(out2.read_text(encoding="utf-8"))

    # Top-level metadata identical.
    assert bundle1["_format"] == bundle2["_format"]
    assert bundle1["_format_version"] == bundle2["_format_version"]
    assert bundle1["store_id"] == bundle2["store_id"]
    assert bundle1["user_version"] == bundle2["user_version"]
    assert bundle1["exported_at"] == bundle2["exported_at"]
    assert bundle1["snapshot_index"] == bundle2["snapshot_index"]
    assert bundle1.get("snapshots", {}) == bundle2.get("snapshots", {})
    assert bundle1["recommended_history"] == bundle2["recommended_history"]

    # Events list: every field that round-trips MUST be byte-identical.
    assert len(bundle1["events"]) == len(bundle2["events"])
    for e1, e2 in zip(bundle1["events"], bundle2["events"]):
        for field in (
            "event_id",
            "event_type",
            "lineage_id",
            "run_id",
            "store_id",
            "play_id",
            "audience_definition_id",
            "audience_definition_version",
            "event_version",
            "created_at",
            "created_seq",
            "payload",
        ):
            assert e1[field] == e2[field], f"mismatch on {field}"


def test_import_refuses_to_overwrite_populated_store(tmp_path: Path):
    base = tmp_path / "data"
    _seed_store(base)

    bundle = export_store("beauty_alpha", base=base, exported_at="T0")
    # Don't wipe — try to import on top of the live store.
    with pytest.raises(RuntimeError, match="non-empty"):
        import_store(bundle, base=base)


def test_import_rejects_bad_format(tmp_path: Path):
    base = tmp_path / "data"
    with pytest.raises(ValueError, match="format"):
        import_store({"_format": "wrong", "store_id": "x"}, base=base)


def test_import_rejects_bad_format_version(tmp_path: Path):
    base = tmp_path / "data"
    with pytest.raises(ValueError, match="_format_version"):
        import_store(
            {
                "_format": FORMAT_NAME,
                "_format_version": 999,
                "store_id": "x",
                "events": [],
            },
            base=base,
        )


def test_recommended_history_preserved(tmp_path: Path):
    base = tmp_path / "data"
    _seed_store(base)
    _seed_recommended_history(base)
    bundle = export_store("beauty_alpha", base=base, exported_at="T0")
    assert bundle["recommended_history"] == [
        {"play_id": "winback", "ts": "2026-05-09"}
    ]
