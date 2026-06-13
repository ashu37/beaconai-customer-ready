"""S-5 — Substrate read-views acceptance tests.

Covers:
  * Migration bumps user_version to 2 and creates the four views; re-open
    is a no-op; downgrade refusal still in force.
  * Seed fixture (10 lineages, 30 events spanning recommendation_emitted
    and recommendation_considered): each view returns the expected shape
    and row count.
  * Forbidden-write: attempting INSERT/UPDATE/DELETE against any view
    raises ``sqlite3.OperationalError``.
  * Empty event log → ``v_calibration_state`` returns zero rows →
    ``load_realization_factors`` returns the same empty-shape dict the
    pre-S-5 stub returned.
  * ``v_calibration_state`` projection: last-write-wins per (section, key).
  * ``v_open_recommendations`` excludes lineages with later
    ``outcome_observed`` rows; surfaces "most recent emission" only.
  * ``v_lineage_recent_emissions`` counts within trailing 28-day window
    anchored on MAX(created_at) of the events table.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

import pytest

from src.calibration_stub import load_realization_factors
from src.memory import (
    compute_lineage_id,
    open_memory,
    read_calibration_state,
    read_lineage_recent_emissions,
    read_lineage_timeline,
    read_open_recommendations,
)
from src.memory.store import CURRENT_USER_VERSION
from src.memory.views import empty_calibration_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_store(store, n_lineages: int = 10) -> List[str]:
    """Append a deterministic mix totalling 30 events across n_lineages.

    Layout (when n_lineages == 10):
      * lineages 0..9 each get one ``recommendation_emitted`` (10 rows)
      * lineages 0..9 each get one ``recommendation_considered`` (10 rows)
      * lineages 0..4 get a second ``recommendation_emitted`` (5 rows)
      * lineages 0..4 get an ``outcome_observed`` (5 rows)
    Total: 30.
    """
    lineage_ids = [
        compute_lineage_id("acme", f"play_{i:02d}", f"aud_{i:02d}", 1)
        for i in range(n_lineages)
    ]
    # 10 emissions
    for i, lid in enumerate(lineage_ids):
        store.append_event(
            event_type="recommendation_emitted",
            lineage_id=lid,
            run_id="run_a",
            play_id=f"play_{i:02d}",
            payload={"role": "recommendation", "i": i},
        )
    # 10 considered
    for i, lid in enumerate(lineage_ids):
        store.append_event(
            event_type="recommendation_considered",
            lineage_id=lid,
            run_id="run_a",
            play_id=f"play_{i:02d}",
            payload={"reason_code": "no_measured_signal", "i": i},
        )
    # second emissions for first half (capped by n_lineages)
    half = max(1, n_lineages // 2)
    for i in range(half):
        store.append_event(
            event_type="recommendation_emitted",
            lineage_id=lineage_ids[i],
            run_id="run_b",
            play_id=f"play_{i:02d}",
            payload={"role": "recommendation", "i": i, "rerun": True},
        )
    # outcomes for first half (after the second emission)
    for i in range(half):
        store.append_event(
            event_type="outcome_observed",
            lineage_id=lineage_ids[i],
            run_id="run_b",
            play_id=f"play_{i:02d}",
            payload={"realized": 0.0, "i": i},
        )
    return lineage_ids


@pytest.fixture
def base(tmp_path: Path) -> Path:
    return tmp_path / "data"


# ---------------------------------------------------------------------------
# Migration / schema
# ---------------------------------------------------------------------------


def test_migration_bumps_user_version_to_2_and_creates_views(base: Path):
    store = open_memory("acme", base=base)
    try:
        assert store.user_version() == CURRENT_USER_VERSION
        assert CURRENT_USER_VERSION >= 2

        # Each view name must be present in sqlite_master.
        with store._lock:  # noqa: SLF001
            cur = store._conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='view' ORDER BY name"
            )
            names = [r["name"] for r in cur.fetchall()]
        assert names == [
            "v_calibration_state",
            "v_lineage_recent_emissions",
            "v_lineage_timeline",
            "v_open_recommendations",
        ]
    finally:
        store.close()


def test_migration_is_idempotent_through_v2(base: Path):
    s1 = open_memory("acme", base=base)
    s1.append_event(event_type="recommendation_emitted", lineage_id="L", payload={"a": 1})
    s1.close()

    s2 = open_memory("acme", base=base)
    try:
        assert s2.user_version() == CURRENT_USER_VERSION
        assert s2.count_events() == 1
    finally:
        s2.close()


def test_downgrade_is_refused(base: Path, monkeypatch: pytest.MonkeyPatch):
    """Opening a db with user_version > CURRENT_USER_VERSION must raise."""
    s1 = open_memory("acme", base=base)
    db_path = s1.db_path
    s1.close()

    # Hand-bump user_version above the build's known max.
    conn = sqlite3.connect(str(db_path))
    conn.execute(f"PRAGMA user_version = {CURRENT_USER_VERSION + 5}")
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError, match="Refusing to downgrade"):
        open_memory("acme", base=base)


# ---------------------------------------------------------------------------
# Seed-fixture shape / row counts
# ---------------------------------------------------------------------------


def test_v_lineage_timeline_returns_per_lineage_ordered_rows(base: Path):
    store = open_memory("acme", base=base)
    try:
        lineage_ids = _seed_store(store, n_lineages=10)
        assert store.count_events() == 30

        # All-lineages call returns 30 rows (every event has a lineage_id
        # in this fixture).
        all_rows = read_lineage_timeline(store)
        assert len(all_rows) == 30
        assert {r["event_type"] for r in all_rows} == {
            "recommendation_emitted",
            "recommendation_considered",
            "outcome_observed",
        }

        # Per-lineage scope: lineage 0 has 4 rows (emit + considered +
        # rerun-emit + outcome), in created_seq order.
        per_lineage = read_lineage_timeline(store, lineage_id=lineage_ids[0])
        assert len(per_lineage) == 4
        seqs = [r["created_seq"] for r in per_lineage]
        assert seqs == sorted(seqs)
        assert [r["event_type"] for r in per_lineage] == [
            "recommendation_emitted",
            "recommendation_considered",
            "recommendation_emitted",
            "outcome_observed",
        ]
        # Lineage 9 has only the initial emission + considered.
        per_lineage_9 = read_lineage_timeline(store, lineage_id=lineage_ids[9])
        assert len(per_lineage_9) == 2
    finally:
        store.close()


def test_v_open_recommendations_excludes_those_with_later_outcomes(base: Path):
    store = open_memory("acme", base=base)
    try:
        lineage_ids = _seed_store(store, n_lineages=10)
        rows = read_open_recommendations(store)

        # Lineages 0..4 had outcome_observed AFTER their last emission →
        # excluded. Lineages 5..9 had only one emission and no outcome →
        # included.
        seen = {r["lineage_id"] for r in rows}
        assert seen == set(lineage_ids[5:10])
        assert len(rows) == 5

        # Each surviving row is the most recent emission for that lineage.
        for r in rows:
            assert r["payload"]["role"] == "recommendation"
            assert r["run_id"] == "run_a"
    finally:
        store.close()


def test_v_open_recommendations_picks_most_recent_when_no_outcome(base: Path):
    """When two emissions exist and no outcome follows, surface the latest."""
    store = open_memory("acme", base=base)
    try:
        lid = compute_lineage_id("acme", "p", "a", 1)
        store.append_event(
            event_type="recommendation_emitted",
            lineage_id=lid,
            run_id="run_a",
            play_id="p",
            payload={"role": "recommendation", "n": 1},
        )
        store.append_event(
            event_type="recommendation_emitted",
            lineage_id=lid,
            run_id="run_b",
            play_id="p",
            payload={"role": "recommendation", "n": 2},
        )
        rows = read_open_recommendations(store)
        assert len(rows) == 1
        assert rows[0]["run_id"] == "run_b"
        assert rows[0]["payload"]["n"] == 2
    finally:
        store.close()


def test_v_lineage_recent_emissions_counts_per_lineage(base: Path):
    store = open_memory("acme", base=base)
    try:
        lineage_ids = _seed_store(store, n_lineages=10)
        rows = read_lineage_recent_emissions(store)
        # Every lineage has at least one emission; first half have two.
        by_lid = {r["lineage_id"]: r["count_in_last_28d"] for r in rows}
        assert len(by_lid) == 10
        for i in range(5):
            assert by_lid[lineage_ids[i]] == 2
        for i in range(5, 10):
            assert by_lid[lineage_ids[i]] == 1
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Forbidden-write contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "view_name",
    [
        "v_lineage_timeline",
        "v_calibration_state",
        "v_open_recommendations",
        "v_lineage_recent_emissions",
    ],
)
def test_views_reject_writes(base: Path, view_name: str):
    """SQLite must reject INSERT/UPDATE/DELETE on every view by
    construction (no INSTEAD OF triggers defined)."""
    store = open_memory("acme", base=base)
    try:
        _seed_store(store, n_lineages=2)  # populate so views resolve
        with store._lock:  # noqa: SLF001
            for stmt in (
                f"INSERT INTO {view_name} DEFAULT VALUES",
                f"UPDATE {view_name} SET lineage_id = 'x'",
                f"DELETE FROM {view_name}",
            ):
                with pytest.raises(sqlite3.OperationalError):
                    store._conn.execute(stmt)
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Calibration stub rewire — empty-shape parity
# ---------------------------------------------------------------------------


def test_load_realization_factors_no_store_id_returns_empty_shape():
    """Pre-S-5 contract: with no store scope, return three-key empty dict."""
    out = load_realization_factors()
    assert out == {
        "prior_overrides": {},
        "evidence_thresholds": {},
        "materiality_overrides": {},
    }


def test_load_realization_factors_legacy_history_path_arg_no_op():
    """Legacy M9 contract: arbitrary history_path values must not raise."""
    for path in (None, "", "/nonexistent", 42, ["weird"]):
        out = load_realization_factors(path)
        assert set(out.keys()) == {
            "prior_overrides",
            "evidence_thresholds",
            "materiality_overrides",
        }


def test_load_realization_factors_empty_substrate_returns_empty_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """With store_id pointing at a freshly-opened (empty) memory.db, the
    helper still returns the three-key empty-shape dict — byte-equal to
    the pre-S-5 stub return value."""
    # Run from a tmp cwd so the relative DEFAULT_BASE = Path("data")
    # resolves under tmp_path/data/, not the repo root.
    monkeypatch.chdir(tmp_path)
    open_memory("acme_empty").close()

    out = load_realization_factors(store_id="acme_empty")
    assert out == empty_calibration_state()
    assert out == {
        "prior_overrides": {},
        "evidence_thresholds": {},
        "materiality_overrides": {},
    }


def test_load_realization_factors_missing_substrate_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A store_id that has no memory.db on disk yet must short-circuit
    to the empty-shape dict, never raise."""
    monkeypatch.chdir(tmp_path)
    out = load_realization_factors(store_id="never_existed")
    assert out == empty_calibration_state()


# ---------------------------------------------------------------------------
# Calibration stub rewire — projects calibration_updated events
# ---------------------------------------------------------------------------


def test_v_calibration_state_projects_last_write_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    store = open_memory("acme_cal")
    try:
        # Two updates to prior_overrides; second wins on key "x".
        store.append_event(
            event_type="calibration_updated",
            lineage_id=None,
            payload={
                "prior_overrides": {"x": 0.10, "y": 0.20},
                "evidence_thresholds": {},
                "materiality_overrides": {},
            },
        )
        store.append_event(
            event_type="calibration_updated",
            lineage_id=None,
            payload={
                "prior_overrides": {"x": 0.99},
                "evidence_thresholds": {"discount_hygiene": {"min_n": 100}},
                "materiality_overrides": {"sub_1m": {"floor_pct": 0.02}},
            },
        )

        view_dict = read_calibration_state(store)
        assert view_dict == {
            "prior_overrides": {"x": 0.99, "y": 0.20},
            "evidence_thresholds": {"discount_hygiene": {"min_n": 100}},
            "materiality_overrides": {"sub_1m": {"floor_pct": 0.02}},
        }
    finally:
        store.close()

    # And the calibration stub returns the same projection.
    out = load_realization_factors(store_id="acme_cal")
    assert out == {
        "prior_overrides": {"x": 0.99, "y": 0.20},
        "evidence_thresholds": {"discount_hygiene": {"min_n": 100}},
        "materiality_overrides": {"sub_1m": {"floor_pct": 0.02}},
    }


def test_v_calibration_state_ignores_unknown_payload_sections(base: Path):
    """Forward-compat: payload may grow new keys; reader must not crash."""
    store = open_memory("acme_fwd", base=base)
    try:
        store.append_event(
            event_type="calibration_updated",
            lineage_id=None,
            payload={
                "prior_overrides": {"a": 1},
                "future_section_added_in_phase_10": {"whatever": True},
            },
        )
        view_dict = read_calibration_state(store)
        assert view_dict == {
            "prior_overrides": {"a": 1},
            "evidence_thresholds": {},
            "materiality_overrides": {},
        }
    finally:
        store.close()
