"""Per-merchant SQLite event log (S-2).

WAL-mode SQLite with ``PRAGMA user_version`` migrations. One database
file per store at ``data/<store_id>/memory.db``. The schema is purely
additive — Sprint 3+ migrations bump ``user_version`` and never remove
columns or tables (founder decision D-2: keep everything forever).

Substrate stands alone in S-2; no engine code calls into it. S-3 wires
writers in ``src/decide.py`` for ``recommendation_emitted`` and
``recommendation_considered`` events.

Concurrency contract:
    - WAL journal mode + ``busy_timeout=5000`` survive concurrent writers
      from multiple processes (e.g. parallel pytest workers, ad-hoc CLI
      while engine runs).
    - ``append_event`` opens its own transaction; the test-suite proves
      2 procs × 100 events → 200 distinct event_ids, zero corruption.

Deletion contract (D-3): per-store ``data/<store_id>/`` directory is the
unit of deletion. Drop the directory; no row-level delete API exists.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional

from ..store_id import ensure_store_dir, store_data_dir

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
#
# user_version: 1
#
# events
#   event_id                       TEXT PRIMARY KEY     -- uuid4 hex
#   event_type                     TEXT NOT NULL
#   lineage_id                     TEXT                 -- nullable; not all events have one
#   run_id                         TEXT
#   store_id                       TEXT NOT NULL
#   play_id                        TEXT
#   audience_definition_id         TEXT
#   audience_definition_version    INTEGER
#   event_version                  INTEGER NOT NULL DEFAULT 1
#   created_at                     TEXT NOT NULL        -- ISO-8601 UTC, microsecond precision
#   created_seq                    INTEGER NOT NULL     -- monotonic insertion order, AUTOINCREMENT
#   payload_json                   TEXT NOT NULL        -- canonical JSON (sort_keys, separators)
#
# Index on (lineage_id, created_seq) for the chief query pattern
# "timeline for one lineage_id in insertion order".
#
# created_seq is the source of truth for ordering. created_at is
# wall-clock and may collide on fast systems; created_seq cannot.

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS events (
    event_id                    TEXT PRIMARY KEY,
    event_type                  TEXT NOT NULL,
    lineage_id                  TEXT,
    run_id                      TEXT,
    store_id                    TEXT NOT NULL,
    play_id                     TEXT,
    audience_definition_id      TEXT,
    audience_definition_version INTEGER,
    event_version               INTEGER NOT NULL DEFAULT 1,
    created_at                  TEXT NOT NULL,
    created_seq                 INTEGER NOT NULL,
    payload_json                TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_lineage_seq  ON events (lineage_id, created_seq);
CREATE INDEX IF NOT EXISTS ix_events_run          ON events (run_id);
CREATE INDEX IF NOT EXISTS ix_events_type_seq     ON events (event_type, created_seq);

CREATE TABLE IF NOT EXISTS event_seq (
    rowid INTEGER PRIMARY KEY CHECK (rowid = 1),
    next_seq INTEGER NOT NULL
);
INSERT OR IGNORE INTO event_seq (rowid, next_seq) VALUES (1, 1);
"""

def _load_views_sql() -> str:
    """Load the read-views DDL bundled with the package (S-5).

    The SQL lives in ``views.sql`` next to this module so the contract
    text is reviewable as SQL, not embedded as a Python string. Loaded
    once at import time; views are created via ``CREATE VIEW IF NOT
    EXISTS`` so the v1→v2 migration is idempotent.
    """
    sql_path = Path(__file__).with_name("views.sql")
    return sql_path.read_text(encoding="utf-8")


_SCHEMA_V2_VIEWS = _load_views_sql()

CURRENT_USER_VERSION = 2

# Migration registry. Each entry runs the schema needed to migrate FROM
# (key) TO (key+1). Idempotent — every statement uses ``IF NOT EXISTS``
# or equivalent so re-running on an already-upgraded DB is a no-op.
_MIGRATIONS: Dict[int, str] = {
    0: _SCHEMA_V1,
    1: _SCHEMA_V2_VIEWS,
}


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------


class MemoryStore:
    """Append-only event log for one store.

    Open via :func:`open_memory`. Not thread-safe across instances on the
    same db file from a single process — open one ``MemoryStore`` per
    thread, or serialise through ``self._lock``. Across processes, WAL
    mode + ``busy_timeout`` handle concurrency.
    """

    _BUSY_TIMEOUT_MS = 5000

    def __init__(self, store_id: str, db_path: Path) -> None:
        self.store_id = store_id
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._open_and_migrate()

    # ----- lifecycle -----

    def _open_and_migrate(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # ``isolation_level=None`` would force autocommit; we want explicit
        # transactions so concurrent appenders never half-write. Default
        # level (deferred) is correct.
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=self._BUSY_TIMEOUT_MS / 1000.0,
            isolation_level="DEFERRED",
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute(f"PRAGMA busy_timeout = {self._BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        self._conn = conn
        self._run_migrations()

    def _run_migrations(self) -> None:
        assert self._conn is not None
        cur = self._conn.execute("PRAGMA user_version")
        current = int(cur.fetchone()[0])
        if current > CURRENT_USER_VERSION:
            raise RuntimeError(
                f"memory.db at {self.db_path} has user_version={current} "
                f"but this build only knows up to v{CURRENT_USER_VERSION}. "
                f"Refusing to downgrade — run a newer Beacon build."
            )
        target = CURRENT_USER_VERSION
        while current < target:
            sql = _MIGRATIONS.get(current)
            if sql is None:
                raise RuntimeError(
                    f"missing migration step from v{current} to v{current + 1}"
                )
            with self._conn:
                self._conn.executescript(sql)
                self._conn.execute(f"PRAGMA user_version = {current + 1}")
            current += 1

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ----- writers -----

    def append_event(
        self,
        *,
        event_type: str,
        payload: Mapping[str, Any],
        lineage_id: Optional[str] = None,
        run_id: Optional[str] = None,
        play_id: Optional[str] = None,
        audience_definition_id: Optional[str] = None,
        audience_definition_version: Optional[int] = None,
        event_version: int = 1,
        event_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> str:
        """Append one event. Returns the assigned ``event_id``.

        ``payload`` is serialised with ``sort_keys=True`` and tight
        separators so two equivalent dicts produce byte-identical JSON
        (matters for export round-trip + future content-hashing).
        """
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("event_type must be a non-empty str")
        if not isinstance(payload, Mapping):
            raise ValueError("payload must be a Mapping")
        if event_version < 1:
            raise ValueError("event_version must be >= 1")

        eid = event_id or uuid.uuid4().hex
        ts = created_at or _utc_iso_now()
        payload_json = json.dumps(
            dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )

        with self._lock:
            assert self._conn is not None
            try:
                with self._conn:  # transaction
                    cur = self._conn.execute(
                        "UPDATE event_seq SET next_seq = next_seq + 1 WHERE rowid = 1 "
                        "RETURNING next_seq - 1"
                    )
                    row = cur.fetchone()
                    if row is None:
                        # Should never happen — the v1 migration seeds rowid=1.
                        # Recreate defensively rather than crash.
                        self._conn.execute(
                            "INSERT OR REPLACE INTO event_seq (rowid, next_seq) VALUES (1, 2)"
                        )
                        seq = 1
                    else:
                        seq = int(row[0])
                    self._conn.execute(
                        "INSERT INTO events ("
                        "event_id, event_type, lineage_id, run_id, store_id, play_id, "
                        "audience_definition_id, audience_definition_version, "
                        "event_version, created_at, created_seq, payload_json"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            eid,
                            event_type,
                            lineage_id,
                            run_id,
                            self.store_id,
                            play_id,
                            audience_definition_id,
                            audience_definition_version,
                            event_version,
                            ts,
                            seq,
                            payload_json,
                        ),
                    )
            except sqlite3.IntegrityError as e:
                raise ValueError(f"event_id collision or constraint: {e}") from e
        return eid

    # ----- readers -----

    def query_events(
        self,
        *,
        lineage_id: Optional[str] = None,
        event_type: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return events ordered by ``created_seq`` ascending.

        Insertion order is the canonical order for substrate consumers
        (no relying on wall-clock collisions).
        """
        sql = "SELECT * FROM events WHERE 1=1"
        params: List[Any] = []
        if lineage_id is not None:
            sql += " AND lineage_id = ?"
            params.append(lineage_id)
        if event_type is not None:
            sql += " AND event_type = ?"
            params.append(event_type)
        if run_id is not None:
            sql += " AND run_id = ?"
            params.append(run_id)
        sql += " ORDER BY created_seq ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))

        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute(sql, params)
            rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]

    def iter_events(
        self,
        *,
        lineage_id: Optional[str] = None,
        event_type: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        for row in self.query_events(
            lineage_id=lineage_id, event_type=event_type, run_id=run_id
        ):
            yield row

    def count_events(self) -> int:
        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute("SELECT COUNT(*) FROM events")
            return int(cur.fetchone()[0])

    def user_version(self) -> int:
        with self._lock:
            assert self._conn is not None
            cur = self._conn.execute("PRAGMA user_version")
            return int(cur.fetchone()[0])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def open_memory(
    store_id: str, *, base: Optional[Path | str] = None
) -> MemoryStore:
    """Open (creating if missing) the per-store memory.db.

    ``base`` defaults to ``src.store_id.DEFAULT_BASE`` (i.e. ``data/``).
    """
    if base is None:
        ensure_store_dir(store_id)
        db_path = store_data_dir(store_id) / "memory.db"
    else:
        ensure_store_dir(store_id, base=base)
        db_path = store_data_dir(store_id, base=base) / "memory.db"
    return MemoryStore(store_id=store_id, db_path=db_path)


def _utc_iso_now() -> str:
    """Microsecond-precision UTC ISO timestamp.

    Uses ``time.time()`` directly to avoid the ``datetime.now(timezone.utc)``
    deprecation churn between Python 3.10 and 3.12+. We don't depend on
    monotonicity here — ``created_seq`` is the ordering key.
    """
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


_ROW_FIELDS = (
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
    "payload_json",
)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    out = {k: row[k] for k in _ROW_FIELDS}
    # Decode JSON payload eagerly — callers always want it.
    payload_json = out.pop("payload_json")
    try:
        out["payload"] = json.loads(payload_json)
    except json.JSONDecodeError:
        # Keep raw if somehow corrupted; surface clearly rather than crash readers.
        out["payload"] = {"_raw": payload_json, "_decode_error": True}
    return out


__all__ = ["MemoryStore", "open_memory", "CURRENT_USER_VERSION"]
