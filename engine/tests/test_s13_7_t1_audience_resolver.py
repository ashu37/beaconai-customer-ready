"""S13.7-T1 — Audience CSV materializer tests.

Three required tests per ticket spec:
1. test_materialize_audience_csvs_happy_path
2. test_materialize_audience_csvs_substrate_refused
3. test_audience_csv_header_row_always_present

Plus structural checks:
- CustomerIdsNullReason enum existence and member count.
- segments.py retirement guard.
"""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from typing import Set


# ---------------------------------------------------------------------------
# Helpers — minimal synthetic EngineRun + PlayCard for testing
# ---------------------------------------------------------------------------


def _make_minimal_engine_run(play_id: str = "winback_dormant_cohort"):
    """Return a minimal EngineRun with one recommendation PlayCard."""
    from src.engine_run import (
        Audience,
        EngineRun,
        PlayCard,
    )

    pc = PlayCard(
        play_id=play_id,
        audience=Audience(id=play_id, definition="dormant 60-120d", size=100),
    )
    er = EngineRun(
        run_id="test-run-001",
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
            "m_quintile": [4] * len(customer_ids),  # rank_score = (4-1)/4 = 0.75
            "segment_name": ["Champions"] * len(customer_ids),
            "parquet_schema_version": [1] * len(customer_ids),
        }
    )
    df.to_parquet(str(parquet_path), index=False)
    return parquet_path


# ---------------------------------------------------------------------------
# Test 1: happy path — parquet present, resolver provided
# ---------------------------------------------------------------------------


def test_materialize_audience_csvs_happy_path(tmp_path):
    """CSV is written at the correct path with correct columns and at least one data row."""
    from src.audience_resolver import materialize_audience_csvs

    store_id = "test_store"
    run_id = "run-abc-123"
    play_id = "winback_dormant_cohort"

    # Synthetic customer IDs in the audience.
    audience_ids = {"cust_001", "cust_002", "cust_003"}

    # Build parquet with those + some extra customers not in audience.
    all_ids = list(audience_ids) + ["cust_999", "cust_998"]
    _make_synthetic_rfm_parquet(tmp_path, store_id, all_ids)

    engine_run = _make_minimal_engine_run(play_id)

    def _resolver(pid: str) -> Set[str]:
        if pid == play_id:
            return audience_ids
        return set()

    materialize_audience_csvs(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
        audience_ids_resolver=_resolver,
    )

    # Verify file exists at expected path.
    expected_path = tmp_path / store_id / "runs" / run_id / "audiences" / f"{play_id}.csv"
    assert expected_path.exists(), (
        f"Expected audience CSV at {expected_path} but it does not exist"
    )

    # Read and verify columns + data rows.
    with open(expected_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == [
            "customer_id",
            "aov_individual",
            "predicted_segment",
            "rank_score",
        ], f"Unexpected columns: {reader.fieldnames}"
        rows = list(reader)

    # Only audience_ids should be in the CSV (3 customers, not 5).
    assert len(rows) >= 1, "Expected at least one data row in happy path"
    assert len(rows) == len(audience_ids), (
        f"Expected {len(audience_ids)} rows (filtered to audience), got {len(rows)}"
    )

    returned_customer_ids = {r["customer_id"] for r in rows}
    assert returned_customer_ids == audience_ids, (
        f"Returned customer IDs {returned_customer_ids} != expected {audience_ids}"
    )

    # rank_score should be derived from m_quintile=4: (4-1)/4 = 0.75.
    for row in rows:
        assert float(row["rank_score"]) == 0.75, (
            f"Expected rank_score=0.75 (m_quintile=4), got {row['rank_score']}"
        )
        assert row["predicted_segment"] == "Champions", (
            f"Expected predicted_segment=Champions, got {row['predicted_segment']}"
        )
        # aov_individual is 0.0 (parquet schema v1 has no per-customer AOV).
        assert float(row["aov_individual"]) == 0.0, (
            f"Expected aov_individual=0.0 (unavailable), got {row['aov_individual']}"
        )


# ---------------------------------------------------------------------------
# Test 2: SUBSTRATE_REFUSED — parquet missing → empty CSV with header
# ---------------------------------------------------------------------------


def test_materialize_audience_csvs_substrate_refused(tmp_path):
    """When parquet is absent, CSV exists at expected path with ONLY the header row."""
    from src.audience_resolver import materialize_audience_csvs

    store_id = "test_store_refused"
    run_id = "run-refused-001"
    play_id = "winback_dormant_cohort"

    # Do NOT create the parquet — this is the SUBSTRATE_REFUSED path.
    engine_run = _make_minimal_engine_run(play_id)

    materialize_audience_csvs(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
        audience_ids_resolver=None,
    )

    expected_path = tmp_path / store_id / "runs" / run_id / "audiences" / f"{play_id}.csv"
    assert expected_path.exists(), (
        f"SUBSTRATE_REFUSED: expected empty CSV at {expected_path} but it does not exist. "
        "The resolver must emit the file even on refusal — silent absence is incorrect."
    )

    # Must have ONLY the header row — no data rows.
    with open(expected_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    assert len(rows) == 1, (
        f"SUBSTRATE_REFUSED: expected exactly 1 row (header only), got {len(rows)}"
    )


# ---------------------------------------------------------------------------
# Test 3: header row always present in both paths
# ---------------------------------------------------------------------------


def test_audience_csv_header_row_always_present(tmp_path):
    """Header row MUST be present in both the happy path and the refused path."""
    from src.audience_resolver import materialize_audience_csvs

    EXPECTED_HEADER = ["customer_id", "aov_individual", "predicted_segment", "rank_score"]

    # --- Happy path ---
    store_id = "test_store_header_happy"
    run_id = "run-header-happy"
    play_id = "winback_dormant_cohort"
    _make_synthetic_rfm_parquet(tmp_path, store_id, ["cust_1", "cust_2"])
    engine_run = _make_minimal_engine_run(play_id)

    def _resolver_all(pid: str) -> Set[str]:
        return {"cust_1", "cust_2"}

    materialize_audience_csvs(
        engine_run, store_id, run_id, str(tmp_path), audience_ids_resolver=_resolver_all
    )
    happy_path = tmp_path / store_id / "runs" / run_id / "audiences" / f"{play_id}.csv"
    assert happy_path.exists()
    with open(happy_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
    assert header == EXPECTED_HEADER, (
        f"Happy path: expected header {EXPECTED_HEADER}, got {header}"
    )

    # --- Refused path ---
    store_id_ref = "test_store_header_refused"
    run_id_ref = "run-header-refused"
    # No parquet created.
    engine_run_ref = _make_minimal_engine_run(play_id)
    materialize_audience_csvs(
        engine_run_ref, store_id_ref, run_id_ref, str(tmp_path)
    )
    refused_path = tmp_path / store_id_ref / "runs" / run_id_ref / "audiences" / f"{play_id}.csv"
    assert refused_path.exists()
    with open(refused_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header_ref = next(reader)
    assert header_ref == EXPECTED_HEADER, (
        f"Refused path: expected header {EXPECTED_HEADER}, got {header_ref}"
    )


# ---------------------------------------------------------------------------
# Structural: CustomerIdsNullReason declared and correct shape
# ---------------------------------------------------------------------------


def test_customer_ids_null_reason_enum_declared():
    """CustomerIdsNullReason is declared in engine_run with 2 members (S13.7-T1 spec)."""
    from src import engine_run

    assert hasattr(engine_run, "CustomerIdsNullReason"), (
        "CustomerIdsNullReason must be declared in src/engine_run.py at S13.7-T1"
    )
    enum_cls = engine_run.CustomerIdsNullReason
    assert len(enum_cls) == 2, (
        f"CustomerIdsNullReason must have 2 members; got {len(enum_cls)}: {list(enum_cls)}"
    )
    member_values = {m.value for m in enum_cls}
    assert "substrate_refused" in member_values, (
        "CustomerIdsNullReason must have SUBSTRATE_REFUSED member"
    )
    assert "audience_resolver_not_invoked" in member_values, (
        "CustomerIdsNullReason must have AUDIENCE_RESOLVER_NOT_INVOKED member"
    )
    # Must be in __all__
    assert "CustomerIdsNullReason" in engine_run.__all__, (
        "CustomerIdsNullReason must be in engine_run.__all__ (DS R6 single-file authority)"
    )


# ---------------------------------------------------------------------------
# Structural: segments.py retirement guard
# ---------------------------------------------------------------------------


def test_segments_py_raises_not_implemented():
    """segments.py must raise NotImplementedError on import (retirement guard S13.7-T1)."""
    import importlib
    import sys

    # Remove any cached module to force fresh import attempt.
    for key in list(sys.modules.keys()):
        if "segments" in key and "beaconai" not in key.lower():
            pass  # only remove beaconai-relative entries
    for key in list(sys.modules.keys()):
        if key in ("src.segments",):
            del sys.modules[key]

    try:
        import src.segments  # noqa: F401
        raise AssertionError(
            "Expected src.segments to raise NotImplementedError on import "
            "(retired at S13.7-T1)"
        )
    except NotImplementedError as e:
        assert "Retired at S13.7-T1" in str(e) or "audience_resolver" in str(e), (
            f"NotImplementedError message does not mention retirement: {e}"
        )
    except Exception as e:
        raise AssertionError(
            f"Expected NotImplementedError from src.segments import, got {type(e).__name__}: {e}"
        )


# ---------------------------------------------------------------------------
# Test: degraded-mode fallback — resolver=None with parquet present
# ---------------------------------------------------------------------------


def test_no_resolver_with_parquet_writes_empty_not_materialized(tmp_path):
    """
    DS lock 4, route (a) (2026-06-01): when audience_ids_resolver=None and the
    parquet exists, the resolver MUST NOT write the full substrate. It writes
    an empty header-only CSV and reports NOT_MATERIALIZED. Emitting the whole
    base under a targeted play (wrong customers, green light) is the
    merchant-reputation killer this hardening removes.

    This supersedes the pre-hardening behavior (full-substrate fallback),
    which produced a MISLABELED MATERIALIZED full-substrate CSV.
    """
    import pandas as pd
    from src.audience_resolver import materialize_audience_csvs

    store_id = "test_store_degraded"
    run_id = "run-degraded-001"
    play_id = "winback_dormant_cohort"

    # Create a minimal parquet with 3 rows and no aov_individual column.
    predictive_dir = tmp_path / store_id / "predictive"
    predictive_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = predictive_dir / "rfm.parquet"

    df = pd.DataFrame(
        {
            "customer_id": ["cust_a", "cust_b", "cust_c"],
            "r_quintile": [2, 3, 4],
            "f_quintile": [2, 3, 4],
            "m_quintile": [2, 3, 4],
            "segment_name": ["At Risk", "Loyal Customers", "Champions"],
        }
    )
    # Explicitly no aov_individual column — matches parquet schema v1.
    assert "aov_individual" not in df.columns
    df.to_parquet(str(parquet_path), index=False)

    engine_run = _make_minimal_engine_run(play_id)

    # Call with no resolver — exercises the hardened degraded branch.
    statuses = materialize_audience_csvs(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
        audience_ids_resolver=None,
    )

    expected_path = tmp_path / store_id / "runs" / run_id / "audiences" / f"{play_id}.csv"
    assert expected_path.exists(), (
        f"Resolver-absent: expected empty CSV at {expected_path} but it does not exist. "
        "Silent absence is incorrect — empty + header is the correct degrade."
    )

    with open(expected_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Exactly the header row, no data rows — full substrate must NOT leak.
    assert rows[0] == ["customer_id", "aov_individual", "predicted_segment", "rank_score"], (
        f"Resolver-absent: unexpected header row: {rows[0]}"
    )
    assert len(rows) == 1, (
        f"Resolver-absent: expected exactly 1 row (header only, NO substrate leak), "
        f"got {len(rows)} rows: {rows}"
    )

    # Status MUST be NOT_MATERIALIZED (not MATERIALIZED, not
    # SUPPRESSED_SUBSTRATE_REFUSED — the parquet was present).
    assert statuses.get(play_id) == "NOT_MATERIALIZED", (
        f"Resolver-absent: expected NOT_MATERIALIZED, got {statuses.get(play_id)!r}"
    )


def test_resolver_raises_writes_empty_not_materialized(tmp_path):
    """
    DS lock 4, route (a): when the resolver IS passed but RAISES for a play,
    the fall-through must NOT write the full substrate. Same failure as the
    resolver-absent branch, different trigger — both write empty +
    NOT_MATERIALIZED.
    """
    import pandas as pd
    from src.audience_resolver import materialize_audience_csvs

    store_id = "test_store_raises"
    run_id = "run-raises-001"
    play_id = "winback_dormant_cohort"

    predictive_dir = tmp_path / store_id / "predictive"
    predictive_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        {
            "customer_id": ["cust_a", "cust_b", "cust_c"],
            "m_quintile": [2, 3, 4],
            "segment_name": ["At Risk", "Loyal Customers", "Champions"],
        }
    )
    df.to_parquet(str(predictive_dir / "rfm.parquet"), index=False)

    engine_run = _make_minimal_engine_run(play_id)

    def _raising_resolver(pid: str) -> Set[str]:
        raise RuntimeError("simulated resolver failure")

    statuses = materialize_audience_csvs(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
        audience_ids_resolver=_raising_resolver,
    )

    expected_path = tmp_path / store_id / "runs" / run_id / "audiences" / f"{play_id}.csv"
    assert expected_path.exists(), (
        "Resolver-raises: expected empty CSV to still be written (non-fatal degrade)."
    )

    with open(expected_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows[0] == ["customer_id", "aov_individual", "predicted_segment", "rank_score"]
    assert len(rows) == 1, (
        f"Resolver-raises: expected header-only CSV (no substrate leak), got {len(rows)} rows"
    )
    assert statuses.get(play_id) == "NOT_MATERIALIZED", (
        f"Resolver-raises: expected NOT_MATERIALIZED, got {statuses.get(play_id)!r}"
    )


def test_happy_path_status_is_materialized(tmp_path):
    """
    Happy path (parquet present, resolver returns an audience set) reports
    MATERIALIZED with data rows — unchanged by the hardening.
    """
    from src.audience_resolver import materialize_audience_csvs

    store_id = "test_store_happy_status"
    run_id = "run-happy-status"
    play_id = "winback_dormant_cohort"
    audience_ids = {"cust_001", "cust_002"}
    _make_synthetic_rfm_parquet(tmp_path, store_id, list(audience_ids) + ["cust_999"])

    engine_run = _make_minimal_engine_run(play_id)

    def _resolver(pid: str) -> Set[str]:
        return audience_ids if pid == play_id else set()

    statuses = materialize_audience_csvs(
        engine_run, store_id, run_id, str(tmp_path), audience_ids_resolver=_resolver
    )

    expected_path = tmp_path / store_id / "runs" / run_id / "audiences" / f"{play_id}.csv"
    with open(expected_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert len(rows) == len(audience_ids) + 1, "header + one row per audience member"
    assert statuses.get(play_id) == "MATERIALIZED", (
        f"Happy path: expected MATERIALIZED, got {statuses.get(play_id)!r}"
    )


def test_parquet_missing_status_is_substrate_refused(tmp_path):
    """
    Parquet missing branch keeps its existing behavior: empty header-only CSV
    and SUPPRESSED_SUBSTRATE_REFUSED (NOT NOT_MATERIALIZED — that distinction
    is the whole point of DS lock 4's two-branch carve-out).
    """
    from src.audience_resolver import materialize_audience_csvs

    store_id = "test_store_no_parquet"
    run_id = "run-no-parquet"
    play_id = "winback_dormant_cohort"

    # No parquet created. Pass a working resolver to prove the status comes
    # from substrate-refusal, not from resolver absence.
    engine_run = _make_minimal_engine_run(play_id)

    def _resolver(pid: str) -> Set[str]:
        return {"cust_001"}

    statuses = materialize_audience_csvs(
        engine_run, store_id, run_id, str(tmp_path), audience_ids_resolver=_resolver
    )

    expected_path = tmp_path / store_id / "runs" / run_id / "audiences" / f"{play_id}.csv"
    assert expected_path.exists()
    with open(expected_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert len(rows) == 1, "parquet-missing: header-only CSV"
    assert statuses.get(play_id) == "SUPPRESSED_SUBSTRATE_REFUSED", (
        f"Parquet-missing: expected SUPPRESSED_SUBSTRATE_REFUSED, got {statuses.get(play_id)!r}"
    )


def test_resolver_returns_empty_set_status_is_substrate_refused(tmp_path):
    """
    Zero-match contract pin (DS review round 2): when the resolver returns an
    EMPTY set (set()) and the parquet is present, resolution DID run and
    succeed — it simply matched zero customers. This falls through to the
    filter (NOT the audience_ids-is-None degraded branch), writes a
    header-only CSV, and the caller's row-count fallback maps the empty result
    to SUPPRESSED_SUBSTRATE_REFUSED (current code behavior — pinned as-is, not
    changed here).

    This test guards against a future "simplify" that collapses
    `if resolved is not None` into `if resolved:` — which would route every
    zero-match audience into the NOT_MATERIALIZED degraded branch and silently
    relabel "resolution ran, matched nobody" as "resolution could not run."
    """
    from src.audience_resolver import materialize_audience_csvs

    store_id = "test_store_empty_set"
    run_id = "run-empty-set-001"
    play_id = "winback_dormant_cohort"

    # Parquet present with customers, but resolver returns an EMPTY set:
    # resolution ran and succeeded, matching zero customers.
    _make_synthetic_rfm_parquet(tmp_path, store_id, ["cust_1", "cust_2", "cust_3"])
    engine_run = _make_minimal_engine_run(play_id)

    def _empty_resolver(pid: str) -> Set[str]:
        return set()

    statuses = materialize_audience_csvs(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
        audience_ids_resolver=_empty_resolver,
    )

    expected_path = tmp_path / store_id / "runs" / run_id / "audiences" / f"{play_id}.csv"
    assert expected_path.exists(), (
        "Empty-set zero-match: expected a header-only CSV to be written."
    )

    with open(expected_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows[0] == ["customer_id", "aov_individual", "predicted_segment", "rank_score"]
    assert len(rows) == 1, (
        f"Empty-set zero-match: expected header-only CSV (zero matched rows), "
        f"got {len(rows)} rows"
    )
    # Current row-count fallback maps zero matched rows to
    # SUPPRESSED_SUBSTRATE_REFUSED. Pinned as-is — NOT NOT_MATERIALIZED.
    assert statuses.get(play_id) == "SUPPRESSED_SUBSTRATE_REFUSED", (
        f"Empty-set zero-match: expected SUPPRESSED_SUBSTRATE_REFUSED "
        f"(resolution ran, matched nobody), got {statuses.get(play_id)!r}. "
        "If this changed to NOT_MATERIALIZED, a zero-match audience was "
        "silently relabeled as 'resolution could not run'."
    )


def test_empty_play_id_status_is_not_materialized(tmp_path):
    """
    Empty-play_id third trigger (DS review round 2): a card with a falsy
    play_id, a present resolver, and a present parquet must yield a
    header-only CSV + NOT_MATERIALIZED. An empty play_id means resolution
    cannot run (no play id to resolve), so audience_ids stays None and the
    card falls into the degraded branch — never the full substrate.
    """
    from src.audience_resolver import materialize_audience_csvs
    from src.engine_run import Audience, EngineRun, PlayCard

    store_id = "test_store_empty_pid"
    run_id = "run-empty-pid-001"

    # Parquet present with customers — proves the status comes from the
    # empty play_id, not substrate refusal.
    _make_synthetic_rfm_parquet(tmp_path, store_id, ["cust_1", "cust_2"])

    # Falsy play_id. aud.id is also falsy, so aud_def_id falls back to
    # `play_id or "unknown"` == "unknown" (the CSV is keyed on "unknown").
    pc = PlayCard(
        play_id="",
        audience=Audience(id="", definition="degenerate card", size=0),
    )
    engine_run = EngineRun(
        run_id="test-run-empty-pid",
        recommendations=[pc],
        recommended_experiments=[],
        considered=[],
        watching=[],
        data_quality_flags=[],
        abstain=None,
    )

    def _resolver(pid: str) -> Set[str]:
        # Should never be called for an empty play_id, but return a real set
        # so a regression that DID call it would leak substrate and fail.
        return {"cust_1", "cust_2"}

    statuses = materialize_audience_csvs(
        engine_run,
        store_id,
        run_id,
        str(tmp_path),
        audience_ids_resolver=_resolver,
    )

    aud_def_id = "unknown"
    expected_path = (
        tmp_path / store_id / "runs" / run_id / "audiences" / f"{aud_def_id}.csv"
    )
    assert expected_path.exists(), (
        f"Empty play_id: expected header-only CSV at {expected_path}."
    )

    with open(expected_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows[0] == ["customer_id", "aov_individual", "predicted_segment", "rank_score"]
    assert len(rows) == 1, (
        f"Empty play_id: expected header-only CSV (no substrate leak), "
        f"got {len(rows)} rows"
    )
    assert statuses.get(aud_def_id) == "NOT_MATERIALIZED", (
        f"Empty play_id: expected NOT_MATERIALIZED (resolution cannot run "
        f"without a play id), got {statuses.get(aud_def_id)!r}"
    )


# ---------------------------------------------------------------------------
# Structural: no mutation of engine_run by resolver
# ---------------------------------------------------------------------------


def test_materialize_audience_csvs_does_not_mutate_engine_run(tmp_path):
    """Resolver must not mutate engine_run.recommendations or other fields."""
    from src.audience_resolver import materialize_audience_csvs

    store_id = "test_store_mutation"
    run_id = "run-mutation-check"
    play_id = "winback_dormant_cohort"

    engine_run = _make_minimal_engine_run(play_id)
    rec_before = list(engine_run.recommendations)

    # No parquet — SUBSTRATE_REFUSED path.
    materialize_audience_csvs(engine_run, store_id, run_id, str(tmp_path))

    assert list(engine_run.recommendations) == rec_before, (
        "materialize_audience_csvs must not mutate engine_run.recommendations"
    )
