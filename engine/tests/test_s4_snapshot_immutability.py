"""S-4 — Immutable snapshot discipline + snapshot_sha256 acceptance tests.

Pins the four contracts S-4 owns:

1. **Immutable per-run snapshot path** — each engine run writes
   ``data/<store_id>/runs/<run_id>.json`` and never overwrites a prior
   run's file. Five runs of the Beauty fixture produce five distinct
   snapshot files.

2. **snapshot_sha256 on every emitted event** — the sha256 stored on
   each ``recommendation_emitted`` / ``recommendation_considered`` event
   payload matches the on-disk sha256 of the immutable snapshot file
   referenced by ``snapshot_path``.

3. **Mutation detection** — hand-edit a snapshot byte; the
   ``verify_snapshot`` helper detects the mismatch.

4. **Mutable mirror is byte-identical** — ``receipts/engine_run.json``
   matches the latest immutable run byte-for-byte.

The S-3 schema freeze is preserved: ``snapshot_sha256`` already lived in
the typed payload as ``Optional[str]`` (S-3 emitted ``None``); S-4 only
populates the field. ``event_version`` remains ``1`` (additive field).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.synthetic_harness import run_scenario  # noqa: E402


SCENARIO_NAME: str = "healthy_beauty_240d"

_S4_ENV_OVERRIDES: Dict[str, str] = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "VERTICAL_MODE": "beauty",
    "WINDOW_POLICY": "auto",
}

# Number of repeat runs for the per-run uniqueness contract.
_N_RUNS: int = 5


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _events_for(store_dir: Path) -> List[Dict[str, Any]]:
    db = store_dir / "memory.db"
    if not db.exists():
        return []
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT event_type, run_id, payload_json FROM events "
            "WHERE event_type IN "
            "('recommendation_emitted', 'recommendation_considered') "
            "ORDER BY created_seq ASC"
        ).fetchall()
    finally:
        conn.close()
    return [
        {"event_type": r[0], "run_id": r[1], "payload": json.loads(r[2])}
        for r in rows
    ]


def _run_once(label: str) -> Dict[str, Any]:
    """Execute one Beauty harness run; return discovered store_dir +
    receipts mirror path + emitted events for that run."""
    td = tempfile.mkdtemp(prefix=f"s4_{label}_")
    out_dir = Path(td) / label
    res = run_scenario(
        SCENARIO_NAME,
        out_dir,
        env_overrides=_S4_ENV_OVERRIDES,
        timeout_sec=300,
    )
    assert res.returncode == 0, res.stderr[-500:]

    dbs = list(Path(td).rglob("memory.db"))
    assert dbs, f"no memory.db produced under {td}"
    store_dir = dbs[0].parent

    receipts_mirror = out_dir / "receipts" / "engine_run.json"
    assert receipts_mirror.exists(), (
        f"receipts/engine_run.json not produced at {receipts_mirror}"
    )

    return {
        "td": td,
        "out_dir": out_dir,
        "store_dir": store_dir,
        "receipts_mirror": receipts_mirror,
        "events": _events_for(store_dir),
    }


@pytest.fixture(scope="module")
def five_run_artifacts() -> List[Dict[str, Any]]:
    return [_run_once(f"run_{i}") for i in range(_N_RUNS)]


def test_each_run_writes_distinct_immutable_snapshot(
    five_run_artifacts: List[Dict[str, Any]],
) -> None:
    """Five runs → five distinct ``data/<store_id>/runs/<run_id>.json``
    files. The immutable snapshot is never overwritten."""
    snapshot_paths: List[Path] = []
    for art in five_run_artifacts:
        runs_dir = Path(art["store_dir"]) / "runs"
        # Each isolated tempdir holds exactly one run; the runs/ dir
        # therefore contains exactly one snapshot file (the contract is
        # "per-run uniqueness," verified by collecting all five and
        # checking distinctness on filename + sha256).
        files = sorted(runs_dir.glob("*.json"))
        assert len(files) == 1, (
            f"expected exactly one immutable snapshot under {runs_dir}, "
            f"got {len(files)}: {files}"
        )
        snapshot_paths.append(files[0])

    distinct_names = {p.name for p in snapshot_paths}
    assert len(distinct_names) == _N_RUNS, (
        f"snapshot filenames collided across runs: {distinct_names}"
    )
    distinct_shas = {_sha256_file(p) for p in snapshot_paths}
    # Five Beauty runs against the same fixture produce identical bytes
    # (G-7 determinism); the filename is what guarantees per-run
    # immutability, not the content. We only assert filename
    # distinctness here.
    assert len(distinct_shas) >= 1, "at least one sha256 expected"


def test_event_snapshot_sha256_matches_on_disk_file(
    five_run_artifacts: List[Dict[str, Any]],
) -> None:
    """For every emitted event in every run, the
    ``payload.snapshot_sha256`` field equals the sha256 of the file at
    ``payload.snapshot_path``. This is the load-bearing audit
    invariant — a downstream consumer can re-hash the snapshot and
    verify."""
    for art in five_run_artifacts:
        events = art["events"]
        assert events, "expected at least one substrate event per run"
        for e in events:
            payload = e["payload"]
            sp = payload.get("snapshot_path")
            ss = payload.get("snapshot_sha256")
            assert sp, (
                f"event {e['event_type']} for run_id={e['run_id']} "
                f"missing snapshot_path"
            )
            assert ss, (
                f"event {e['event_type']} for run_id={e['run_id']} "
                f"missing snapshot_sha256"
            )
            on_disk = Path(sp)
            assert on_disk.exists(), (
                f"snapshot_path {sp} referenced by event does not exist"
            )
            actual = _sha256_file(on_disk)
            assert actual == ss, (
                f"snapshot_sha256 mismatch for run_id={e['run_id']}: "
                f"event payload claims {ss} but on-disk file hashes to "
                f"{actual}"
            )


def test_mutation_is_detected(tmp_path: Path) -> None:
    """Hand-edit a snapshot byte; ``verify_snapshot`` returns False.

    This is the mutation acceptance criterion. We do NOT run the engine
    here — we exercise the helper directly so the test is fast and
    hermetic."""
    from src.memory.snapshot import verify_snapshot, write_immutable_snapshot

    store_dir = tmp_path / "store"
    receipts_dir = tmp_path / "receipts"
    payload = {"hello": "world", "n": 42}
    immutable_path, sha = write_immutable_snapshot(
        engine_run_dict=payload,
        store_dir=store_dir,
        receipts_dir=receipts_dir,
        run_id="test-run-001",
    )
    assert verify_snapshot(immutable_path, sha) is True

    # Mutate one byte: append a single space (preserves valid JSON for
    # most tools but changes sha256).
    with open(immutable_path, "ab") as f:
        f.write(b" ")
    assert verify_snapshot(immutable_path, sha) is False


def test_receipts_mirror_byte_identical_to_immutable(
    five_run_artifacts: List[Dict[str, Any]],
) -> None:
    """``receipts/engine_run.json`` must be byte-identical to the
    latest immutable run snapshot. Backward-compat for current Swarm
    consumers depends on this."""
    for art in five_run_artifacts:
        runs_dir = Path(art["store_dir"]) / "runs"
        snapshots = sorted(runs_dir.glob("*.json"))
        assert snapshots, f"no immutable snapshots under {runs_dir}"
        immutable = snapshots[-1]
        mirror = Path(art["receipts_mirror"])
        with open(immutable, "rb") as a, open(mirror, "rb") as b:
            assert a.read() == b.read(), (
                f"receipts mirror {mirror} is not byte-identical to "
                f"immutable snapshot {immutable}"
            )


def test_immutable_path_refuses_overwrite(tmp_path: Path) -> None:
    """Re-using a run_id raises ``FileExistsError``. Pins the
    "never overwritten" contract at the helper layer."""
    from src.memory.snapshot import write_immutable_snapshot

    store_dir = tmp_path / "store"
    receipts_dir = tmp_path / "receipts"
    write_immutable_snapshot(
        engine_run_dict={"k": 1},
        store_dir=store_dir,
        receipts_dir=receipts_dir,
        run_id="dup-run-id",
    )
    with pytest.raises(FileExistsError):
        write_immutable_snapshot(
            engine_run_dict={"k": 2},
            store_dir=store_dir,
            receipts_dir=receipts_dir,
            run_id="dup-run-id",
        )


def test_empty_run_id_rejected(tmp_path: Path) -> None:
    """A missing/empty ``run_id`` is a caller bug; surface it loudly."""
    from src.memory.snapshot import write_immutable_snapshot

    with pytest.raises(ValueError):
        write_immutable_snapshot(
            engine_run_dict={"k": 1},
            store_dir=tmp_path / "store",
            receipts_dir=tmp_path / "receipts",
            run_id="",
        )
