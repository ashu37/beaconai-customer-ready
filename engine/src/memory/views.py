"""S-5 — Substrate read-views: typed Python helpers.

Thin read-side facade over the four views defined in
``src/memory/views.sql`` (loaded into the DB via the v1→v2 migration in
``src/memory/store.py``). Each helper takes an open :class:`MemoryStore`
and returns a typed Python value — ``list[dict]`` for row sets,
``dict[str, dict]`` for the projected calibration state.

Hard rules (load-bearing for downstream consumers):

  * Helpers are **read-only**. SQLite rejects INSERT/UPDATE/DELETE
    against a view by default; we never define INSTEAD OF triggers. The
    forbidden-write acceptance test
    (``tests/test_s5_views.py::test_views_reject_writes``) pins this.

  * Ordering is the SQL ordering (see ``views.sql`` header comments).
    Helpers do NOT re-sort; consumers can rely on view order.

  * With an empty events table, every helper returns an empty container
    of the right shape. ``read_calibration_state`` in particular returns
    the **same three-key empty-shape dict** the calibration stub used to
    return pre-S-5 — that's the contract anchor for the rewire.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional

from .store import MemoryStore


# ---------------------------------------------------------------------------
# Empty-shape contract for calibration state
# ---------------------------------------------------------------------------

# The three keys ``load_realization_factors`` has returned since
# Milestone 9 (DS Architect QA Required Change 5). The S-5 rewire MUST
# preserve this exact shape when the events table contains zero
# ``calibration_updated`` rows.
_CALIBRATION_SECTIONS: tuple[str, ...] = (
    "prior_overrides",
    "evidence_thresholds",
    "materiality_overrides",
)


def empty_calibration_state() -> Dict[str, Dict[str, Any]]:
    """Return the canonical empty-shape calibration dict.

    Freshly constructed on every call so callers can mutate safely.
    """
    return {section: {} for section in _CALIBRATION_SECTIONS}


# ---------------------------------------------------------------------------
# v_lineage_timeline
# ---------------------------------------------------------------------------


def read_lineage_timeline(
    store: MemoryStore, *, lineage_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Return ordered timeline rows.

    If ``lineage_id`` is given, only rows for that lineage are returned;
    otherwise all timeline rows for all lineages are returned (still in
    ``(lineage_id, created_seq)`` order per the view).

    Each row dict has keys: ``lineage_id``, ``created_seq``,
    ``event_type``, ``payload`` (decoded from ``payload_json``).
    """
    if lineage_id is not None:
        sql = (
            "SELECT lineage_id, created_seq, event_type, payload_json "
            "FROM v_lineage_timeline WHERE lineage_id = ? "
            "ORDER BY created_seq ASC"
        )
        params: tuple = (lineage_id,)
    else:
        sql = (
            "SELECT lineage_id, created_seq, event_type, payload_json "
            "FROM v_lineage_timeline"
        )
        params = ()
    rows = _exec(store, sql, params)
    return [_decode_row(r, payload_field="payload_json") for r in rows]


# ---------------------------------------------------------------------------
# v_calibration_state
# ---------------------------------------------------------------------------


def read_calibration_state(store: MemoryStore) -> Dict[str, Dict[str, Any]]:
    """Project ``calibration_updated`` events into the contract dict.

    The view returns one row per ``calibration_updated`` event in
    ``created_seq`` ascending order. We walk them last-write-wins per
    ``(section, key)`` pair, where each event payload is expected to
    carry one or more of the three section keys (``prior_overrides``,
    ``evidence_thresholds``, ``materiality_overrides``) mapping to a
    nested dict of overrides.

    With zero rows present, the return value is byte-equal to
    :func:`empty_calibration_state` — preserving the exact contract the
    pre-S-5 stub anchored.

    Payload shape contract (for the future Phase 9 calibration consumer
    that will write these events):

        {
          "prior_overrides":       {prior_key: override_value},
          "evidence_thresholds":   {play_id: {threshold_name: value}},
          "materiality_overrides": {scale_band: {floor_param: value}},
        }

    Any keys outside the three known sections are ignored (forward-
    compatibility shim — additive payload growth must not crash this
    reader).
    """
    sql = (
        "SELECT created_seq, play_id, payload_json "
        "FROM v_calibration_state ORDER BY created_seq ASC"
    )
    rows = _exec(store, sql, ())

    out = empty_calibration_state()
    for row in rows:
        payload = _safe_json(row["payload_json"])
        if not isinstance(payload, dict):
            continue
        for section in _CALIBRATION_SECTIONS:
            block = payload.get(section)
            if not isinstance(block, dict):
                continue
            # last-write-wins per inner key
            for k, v in block.items():
                out[section][k] = v
    return out


# ---------------------------------------------------------------------------
# v_open_recommendations
# ---------------------------------------------------------------------------


def read_open_recommendations(store: MemoryStore) -> List[Dict[str, Any]]:
    """Return the most-recent ``recommendation_emitted`` per lineage_id
    that has no later ``outcome_observed`` row.

    Each row dict has keys: ``lineage_id``, ``run_id``, ``play_id``,
    ``emitted_seq``, ``emitted_at``, ``payload``.
    """
    sql = (
        "SELECT lineage_id, run_id, play_id, emitted_seq, emitted_at, "
        "       payload_json "
        "FROM v_open_recommendations ORDER BY emitted_seq ASC"
    )
    rows = _exec(store, sql, ())
    return [_decode_row(r, payload_field="payload_json") for r in rows]


# ---------------------------------------------------------------------------
# v_lineage_recent_emissions
# ---------------------------------------------------------------------------


def read_lineage_recent_emissions(store: MemoryStore) -> List[Dict[str, Any]]:
    """Return per-lineage emission counts within the trailing 28-day
    window (anchor = ``MAX(created_at)`` of the events table).

    Each row dict has keys: ``lineage_id``, ``count_in_last_28d``.
    Lineages with zero emissions in the window are excluded.
    """
    sql = (
        "SELECT lineage_id, count_in_last_28d "
        "FROM v_lineage_recent_emissions ORDER BY lineage_id ASC"
    )
    rows = _exec(store, sql, ())
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _exec(store: MemoryStore, sql: str, params: tuple) -> List[sqlite3.Row]:
    """Execute a read-only query against the store's underlying conn.

    Uses the store's existing lock for thread-safety parity with
    ``MemoryStore.query_events``.
    """
    with store._lock:  # noqa: SLF001 — intentional, see contract above
        assert store._conn is not None
        cur = store._conn.execute(sql, params)
        return cur.fetchall()


def _decode_row(row: sqlite3.Row, *, payload_field: str) -> Dict[str, Any]:
    out = {k: row[k] for k in row.keys()}
    raw = out.pop(payload_field, None)
    out["payload"] = _safe_json(raw) if raw is not None else None
    return out


def _safe_json(raw: Any) -> Any:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"_raw": raw, "_decode_error": True}


__all__ = [
    "empty_calibration_state",
    "read_calibration_state",
    "read_lineage_timeline",
    "read_lineage_recent_emissions",
    "read_open_recommendations",
]
