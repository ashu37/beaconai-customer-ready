"""S13.7-T2 — Per-run manifest.json tests.

Four required tests per ticket spec:
1. test_manifest_written_after_run
2. test_manifest_audience_status_materialized
3. test_manifest_audience_status_substrate_refused
4. test_manifest_parquets_enumerated

Plus structural checks:
- Return type of materialize_audience_csvs is dict.
"""

from __future__ import annotations

import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_engine_run(play_id: str = "winback_dormant_cohort"):
    """Return a minimal EngineRun with one recommendation PlayCard."""
    from src.engine_run import Audience, EngineRun, PlayCard

    pc = PlayCard(
        play_id=play_id,
        audience=Audience(id=play_id, definition="dormant 60-120d", size=100),
    )
    er = EngineRun(
        run_id="test-run-t2-001",
        store_id="test_store",
        recommendations=[pc],
        recommended_experiments=[],
        considered=[],
        watching=[],
        data_quality_flags=[],
        abstain=None,
    )
    return er


def _make_synthetic_rfm_parquet(tmp_dir: Path, store_id: str, customer_ids: list) -> Path:
    """Write a minimal RFM parquet with the given customer_ids."""
    import pandas as pd

    predictive_dir = tmp_dir / store_id / "predictive"
    predictive_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = predictive_dir / "rfm.parquet"

    df = pd.DataFrame(
        {
            "customer_id": [str(c) for c in customer_ids],
            "r_quintile": [3] * len(customer_ids),
            "f_quintile": [3] * len(customer_ids),
            "m_quintile": [4] * len(customer_ids),
            "segment_name": ["Champions"] * len(customer_ids),
            "parquet_schema_version": [1] * len(customer_ids),
        }
    )
    df.to_parquet(str(parquet_path), index=False)
    return parquet_path


# ---------------------------------------------------------------------------
# Test 1: manifest is written at the correct path with the correct shape
# ---------------------------------------------------------------------------


def test_manifest_written_after_run(tmp_path):
    """manifest.json is written with correct schema_version, run_id, store_id,
    created_at (ISO format), and artifacts keys."""
    from src.run_manifest import write_run_manifest

    store_id = "test_store_t2"
    run_id = "run-manifest-001"
    engine_run = _make_minimal_engine_run()
    engine_run.store_id = store_id
    engine_run.run_id = run_id

    write_run_manifest(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
        audience_statuses={},
    )

    manifest_path = tmp_path / store_id / "runs" / run_id / "manifest.json"
    assert manifest_path.exists(), (
        f"manifest.json not found at {manifest_path}"
    )

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # schema_version
    assert manifest.get("schema_version") == "1.0.0", (
        f"Expected schema_version='1.0.0', got {manifest.get('schema_version')!r}"
    )

    # run_id + store_id
    assert manifest.get("run_id") == run_id, (
        f"Expected run_id={run_id!r}, got {manifest.get('run_id')!r}"
    )
    assert manifest.get("store_id") == store_id, (
        f"Expected store_id={store_id!r}, got {manifest.get('store_id')!r}"
    )

    # created_at is ISO 8601 (contains 'T' separator as UTC)
    created_at = manifest.get("created_at", "")
    assert "T" in created_at, (
        f"created_at does not look like ISO-8601: {created_at!r}"
    )

    # artifacts keys
    artifacts = manifest.get("artifacts", {})
    assert "engine_run" in artifacts, "artifacts must contain 'engine_run' key"
    assert "audiences" in artifacts, "artifacts must contain 'audiences' key"
    assert "parquets" in artifacts, "artifacts must contain 'parquets' key"
    assert "retention" in artifacts, "artifacts must contain 'retention' key"

    assert artifacts["engine_run"] == f"../{run_id}.json", (
        f"Expected engine_run='../{run_id}.json', got {artifacts['engine_run']!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: MATERIALIZED status recorded when CSV has data rows
# ---------------------------------------------------------------------------


def test_manifest_audience_status_materialized(tmp_path):
    """MATERIALIZED status is recorded when the audience CSV has data rows."""
    from src.run_manifest import write_run_manifest

    store_id = "test_store_materialized"
    run_id = "run-mat-001"
    play_id = "winback_dormant_cohort"

    engine_run = _make_minimal_engine_run(play_id)
    engine_run.store_id = store_id
    engine_run.run_id = run_id

    # Simulate that the audience CSV was materialized with data rows.
    audience_statuses = {play_id: "MATERIALIZED"}

    write_run_manifest(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
        audience_statuses=audience_statuses,
    )

    manifest_path = tmp_path / store_id / "runs" / run_id / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    audiences = manifest["artifacts"]["audiences"]
    assert len(audiences) == 1, f"Expected 1 audience entry, got {len(audiences)}"

    entry = audiences[0]
    assert entry["audience_definition_id"] == play_id, (
        f"Expected aud_def_id={play_id!r}, got {entry['audience_definition_id']!r}"
    )
    assert entry["audience_materialization_status"] == "MATERIALIZED", (
        f"Expected MATERIALIZED, got {entry['audience_materialization_status']!r}"
    )
    assert entry["path"] == f"audiences/{play_id}.csv", (
        f"Expected path='audiences/{play_id}.csv', got {entry['path']!r}"
    )
    assert entry["play_id"] == play_id, (
        f"Expected play_id={play_id!r}, got {entry['play_id']!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: SUPPRESSED_SUBSTRATE_REFUSED status when CSV is empty (header only)
# ---------------------------------------------------------------------------


def test_manifest_audience_status_substrate_refused(tmp_path):
    """SUPPRESSED_SUBSTRATE_REFUSED status recorded when parquet is missing."""
    from src.run_manifest import write_run_manifest

    store_id = "test_store_refused"
    run_id = "run-refused-002"
    play_id = "winback_dormant_cohort"

    engine_run = _make_minimal_engine_run(play_id)
    engine_run.store_id = store_id
    engine_run.run_id = run_id

    # Simulate that the substrate was refused.
    audience_statuses = {play_id: "SUPPRESSED_SUBSTRATE_REFUSED"}

    write_run_manifest(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
        audience_statuses=audience_statuses,
    )

    manifest_path = tmp_path / store_id / "runs" / run_id / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    audiences = manifest["artifacts"]["audiences"]
    assert len(audiences) == 1
    entry = audiences[0]
    assert entry["audience_materialization_status"] == "SUPPRESSED_SUBSTRATE_REFUSED", (
        f"Expected SUPPRESSED_SUBSTRATE_REFUSED, got {entry['audience_materialization_status']!r}"
    )


# ---------------------------------------------------------------------------
# Test 4: parquets list is populated when parquet files exist
# ---------------------------------------------------------------------------


def test_manifest_parquets_enumerated(tmp_path):
    """Parquets list in manifest is populated from data/<store_id>/predictive/*.parquet."""
    import pandas as pd
    from src.run_manifest import write_run_manifest

    store_id = "test_store_parquets"
    run_id = "run-parquets-001"

    # Plant two synthetic parquet files.
    predictive_dir = tmp_path / store_id / "predictive"
    predictive_dir.mkdir(parents=True, exist_ok=True)
    for fname in ["rfm.parquet", "bgnbd.parquet"]:
        df = pd.DataFrame({"dummy": [1, 2, 3]})
        df.to_parquet(str(predictive_dir / fname), index=False)

    engine_run = _make_minimal_engine_run()
    engine_run.store_id = store_id
    engine_run.run_id = run_id

    write_run_manifest(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
        audience_statuses={},
    )

    manifest_path = tmp_path / store_id / "runs" / run_id / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    parquets = manifest["artifacts"]["parquets"]
    assert len(parquets) == 2, (
        f"Expected 2 parquet entries, got {len(parquets)}: {parquets}"
    )

    names = {p["name"] for p in parquets}
    assert "rfm.parquet" in names, f"rfm.parquet missing from parquets: {names}"
    assert "bgnbd.parquet" in names, f"bgnbd.parquet missing from parquets: {names}"

    for p in parquets:
        assert p["path"] == f"../../predictive/{p['name']}", (
            f"Unexpected path for {p['name']!r}: {p['path']!r}"
        )


# ---------------------------------------------------------------------------
# Structural: materialize_audience_csvs returns a dict
# ---------------------------------------------------------------------------


def test_materialize_audience_csvs_returns_dict(tmp_path):
    """materialize_audience_csvs must return a dict (S13.7-T2 return-type change)."""
    from src.audience_resolver import materialize_audience_csvs

    store_id = "test_store_rettype"
    run_id = "run-rettype-001"
    play_id = "winback_dormant_cohort"

    engine_run = _make_minimal_engine_run(play_id)

    result = materialize_audience_csvs(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
    )

    assert isinstance(result, dict), (
        f"materialize_audience_csvs must return dict, got {type(result).__name__}"
    )


def test_materialize_audience_csvs_returns_status_for_each_card(tmp_path):
    """Status dict from materialize_audience_csvs has one entry per PlayCard."""
    from src.audience_resolver import materialize_audience_csvs

    store_id = "test_store_status_dict"
    run_id = "run-status-001"
    play_id = "winback_dormant_cohort"

    engine_run = _make_minimal_engine_run(play_id)

    result = materialize_audience_csvs(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
    )

    # No parquet → SUPPRESSED_SUBSTRATE_REFUSED
    assert play_id in result, (
        f"Expected '{play_id}' in status dict, got keys: {list(result.keys())}"
    )
    assert result[play_id] == "SUPPRESSED_SUBSTRATE_REFUSED", (
        f"Expected SUPPRESSED_SUBSTRATE_REFUSED (no parquet), got {result[play_id]!r}"
    )


def test_materialize_audience_csvs_materialized_status(tmp_path):
    """Status MATERIALIZED is returned when the parquet exists and has matching rows."""
    from src.audience_resolver import materialize_audience_csvs

    store_id = "test_store_mat_status"
    run_id = "run-mat-status-001"
    play_id = "winback_dormant_cohort"

    _make_synthetic_rfm_parquet(tmp_path, store_id, ["cust_a", "cust_b"])

    engine_run = _make_minimal_engine_run(play_id)

    def _resolver(pid: str):
        return {"cust_a", "cust_b"}

    result = materialize_audience_csvs(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
        audience_ids_resolver=_resolver,
    )

    assert play_id in result, (
        f"Expected '{play_id}' in status dict, got: {list(result.keys())}"
    )
    assert result[play_id] == "MATERIALIZED", (
        f"Expected MATERIALIZED, got {result[play_id]!r}"
    )


# ---------------------------------------------------------------------------
# Contract fix: manifest.artifacts.engine_run must resolve (relative to the
# manifest's own directory) to the actual immutable snapshot file at
# data/<store_id>/runs/<run_id>.json — a sibling file one dir up from the
# manifest.
# ---------------------------------------------------------------------------


def test_manifest_engine_run_pointer_resolves_to_snapshot_file(tmp_path):
    """artifacts.engine_run, resolved relative to the manifest's directory,
    must point at the immutable snapshot file at
    data/<store_id>/runs/<run_id>.json."""
    from src.run_manifest import write_run_manifest

    store_id = "test_store_pointer"
    run_id = "run-pointer-001"

    # Create the runs/ directory and plant a fake snapshot file at the
    # canonical immutable path: data/<store_id>/runs/<run_id>.json.
    runs_dir = tmp_path / store_id / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = runs_dir / f"{run_id}.json"
    snapshot_path.write_text("{}", encoding="utf-8")

    engine_run = _make_minimal_engine_run()
    engine_run.store_id = store_id
    engine_run.run_id = run_id

    write_run_manifest(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
        audience_statuses={},
    )

    manifest_path = tmp_path / store_id / "runs" / run_id / "manifest.json"
    assert manifest_path.exists(), f"manifest.json not at {manifest_path}"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    pointer = manifest["artifacts"]["engine_run"]

    # Resolve the pointer relative to the manifest's own directory.
    resolved = (manifest_path.parent / pointer).resolve()
    expected = snapshot_path.resolve()

    assert resolved == expected, (
        f"manifest.artifacts.engine_run resolved to {resolved}, "
        f"expected {expected} (pointer was {pointer!r})"
    )
    assert resolved.exists(), (
        f"resolved snapshot path does not exist on disk: {resolved}"
    )
