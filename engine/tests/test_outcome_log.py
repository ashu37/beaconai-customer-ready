"""Tests for src.outcome_log (Milestone 9, T9.1).

Covers:
- Append-then-re-read.
- Missing-file create-on-first-write.
- Malformed-file safe handling (no crash; corrupt copy moved aside).
- Disabled flag short-circuits with no I/O.
- Privacy: no raw customer IDs persisted.
- Idempotent shape: schema_version + ts + store_id + run_id present.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.engine_run import (
    Abstain,
    Audience,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Measurement,
    PlayCard,
    ReasonCode,
    RejectedPlay,
    RevenueRange,
    RevenueRangeSource,
    Scale,
)
from src.outcome_log import (
    SCHEMA_VERSION,
    STATUS_DISABLED,
    STATUS_NO_ENGINE_RUN,
    STATUS_OK,
    STATUS_RECOVERED_FROM_CORRUPT,
    assert_drivers_present_for_non_suppressed,
    build_record,
    write_recommended_history,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _measured_card_with_internal_stats() -> PlayCard:
    return PlayCard(
        play_id="winback_21_45",
        evidence_class=EvidenceClass.MEASURED,
        confidence_label="Strong",
        audience=Audience(id="winback_21_45_inactive", size=412, fraction_of_base=0.07),
        measurement=Measurement(
            metric="reactivation_rate",
            observed_effect=0.12,
            n=412,
            primary_window="L28",
            consistency_across_windows=2,
            p_internal=0.014,
            ci_internal=[0.04, 0.20],
        ),
        revenue_range=RevenueRange(
            p10=2400.0,
            p50=4800.0,
            p90=7200.0,
            source=RevenueRangeSource.STORE_OBSERVED,
            drivers=[{"name": "audience_size", "value": 412, "source": "store_observed"}],
            suppressed=False,
        ),
    )


def _targeting_suppressed_card() -> PlayCard:
    return PlayCard(
        play_id="category_expansion",
        evidence_class=EvidenceClass.TARGETING,
        confidence_label="Targeting",
        audience=Audience(id="cat_exp_audience", size=900),
        measurement=None,
        revenue_range=RevenueRange(
            p10=None,
            p50=None,
            p90=None,
            source=None,
            drivers=[
                {"name": "suppression_reason", "source": "sizing_v2", "reason": "targeting_non_causal_prior"},
            ],
            suppressed=True,
        ),
    )


def _engine_run() -> EngineRun:
    return EngineRun(
        run_id="run-123",
        store_id="store-abc",
        anchor_date="2026-05-03",
        cold_start=False,
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[_measured_card_with_internal_stats(), _targeting_suppressed_card()],
        considered=[
            RejectedPlay(
                play_id="overstock_demand_push",
                reason_code=ReasonCode.INVENTORY_BLOCKED,
            )
        ],
        scale=Scale(monthly_revenue=120_000.0, customer_base_est=4500, materiality_floor=5000.0),
    )


# ---------------------------------------------------------------------------
# build_record
# ---------------------------------------------------------------------------


def test_build_record_has_required_top_level_keys():
    rec = build_record(_engine_run())
    assert rec["schema_version"] == SCHEMA_VERSION
    assert rec["store_id"] == "store-abc"
    assert rec["run_id"] == "run-123"
    assert rec["anchor_date"] == "2026-05-03"
    assert rec["decision_state"] == "publish"
    assert isinstance(rec["recommended"], list)
    assert isinstance(rec["rejected"], list)
    assert "ts" in rec
    assert rec["summary"]["n_recommended"] == 2
    assert rec["summary"]["n_rejected"] == 1
    assert rec["summary"]["sum_recommended_p50"] == 4800.0


def test_build_record_persists_internal_evidence_diagnostics():
    rec = build_record(_engine_run())
    measured = next(r for r in rec["recommended"] if r["play_id"] == "winback_21_45")
    assert measured["measurement"]["p_internal"] == 0.014
    assert measured["measurement"]["ci_internal"] == [0.04, 0.20]
    assert measured["measurement"]["observed_effect"] == 0.12
    assert measured["measurement"]["n"] == 412


def test_build_record_persists_drivers_provenance():
    rec = build_record(_engine_run())
    measured = next(r for r in rec["recommended"] if r["play_id"] == "winback_21_45")
    assert measured["revenue_range"]["suppressed"] is False
    assert isinstance(measured["revenue_range"]["drivers"], list)
    assert len(measured["revenue_range"]["drivers"]) >= 1


def test_build_record_targeting_card_carries_no_measurement():
    rec = build_record(_engine_run())
    targeting = next(r for r in rec["recommended"] if r["play_id"] == "category_expansion")
    assert targeting["measurement"] is None
    assert targeting["revenue_range"]["suppressed"] is True


def test_build_record_does_not_persist_raw_customer_ids():
    """Privacy safeguard: audience.id is metadata; no raw customer-id list."""
    rec = build_record(_engine_run())
    s = json.dumps(rec)
    # No "customer_id" or "Customer Email" or PII-shaped keys.
    forbidden_keys = ["customer_id", "Customer Email", "Customer ID", "email"]
    for k in forbidden_keys:
        assert k not in s, f"forbidden key {k!r} appeared in outcome record"


# ---------------------------------------------------------------------------
# write_recommended_history — happy path / append
# ---------------------------------------------------------------------------


def test_write_recommended_history_creates_missing_file(tmp_path: Path):
    target = tmp_path / "deeper" / "recommended_history.json"
    assert not target.exists()

    status = write_recommended_history(_engine_run(), target)

    assert status["status"] == STATUS_OK
    assert status["records_after"] == 1
    assert target.exists()
    data = json.loads(target.read_text())
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["store_id"] == "store-abc"


def test_write_recommended_history_appends_existing_records(tmp_path: Path):
    target = tmp_path / "recommended_history.json"

    # Three consecutive runs.
    s1 = write_recommended_history(_engine_run(), target)
    s2 = write_recommended_history(_engine_run(), target)
    s3 = write_recommended_history(_engine_run(), target)

    assert s1["status"] == STATUS_OK
    assert s2["status"] == STATUS_OK
    assert s3["status"] == STATUS_OK
    assert s1["records_after"] == 1
    assert s2["records_after"] == 2
    assert s3["records_after"] == 3

    data = json.loads(target.read_text())
    assert len(data) == 3
    assert all(r["store_id"] == "store-abc" for r in data)


def test_write_recommended_history_disabled_flag_short_circuits(tmp_path: Path):
    target = tmp_path / "should_not_exist.json"
    status = write_recommended_history(_engine_run(), target, enabled=False)
    assert status["status"] == STATUS_DISABLED
    assert not target.exists()


def test_write_recommended_history_no_engine_run(tmp_path: Path):
    target = tmp_path / "nope.json"
    status = write_recommended_history(None, target)
    assert status["status"] == STATUS_NO_ENGINE_RUN
    assert not target.exists()


# ---------------------------------------------------------------------------
# write_recommended_history — malformed-file safe handling
# ---------------------------------------------------------------------------


def test_write_recommended_history_recovers_from_truncated_json(tmp_path: Path):
    target = tmp_path / "recommended_history.json"
    target.write_text('[{"truncated": tru')  # invalid JSON

    status = write_recommended_history(_engine_run(), target)

    assert status["status"] == STATUS_RECOVERED_FROM_CORRUPT
    assert status["records_after"] == 1
    assert "corrupt_backup" in status
    backup_path = Path(status["corrupt_backup"])
    assert backup_path.exists()
    # Fresh file is valid JSON list with one entry.
    data = json.loads(target.read_text())
    assert isinstance(data, list)
    assert len(data) == 1


def test_write_recommended_history_recovers_when_file_is_dict_not_list(tmp_path: Path):
    target = tmp_path / "recommended_history.json"
    target.write_text(json.dumps({"not": "a list"}))

    status = write_recommended_history(_engine_run(), target)

    assert status["status"] == STATUS_RECOVERED_FROM_CORRUPT
    data = json.loads(target.read_text())
    assert isinstance(data, list)
    assert len(data) == 1


def test_write_recommended_history_treats_empty_file_as_fresh(tmp_path: Path):
    target = tmp_path / "recommended_history.json"
    target.write_text("")  # empty (allowed)

    status = write_recommended_history(_engine_run(), target)
    # Empty is treated as "no records yet", not corrupt.
    assert status["status"] == STATUS_OK
    data = json.loads(target.read_text())
    assert len(data) == 1


def test_write_recommended_history_skips_non_dict_entries_in_existing_list(tmp_path: Path):
    target = tmp_path / "recommended_history.json"
    target.write_text(json.dumps([{"store_id": "old"}, "not-a-dict", 42, None]))

    status = write_recommended_history(_engine_run(), target)
    assert status["status"] == STATUS_OK
    data = json.loads(target.read_text())
    # Only the dict entry from before plus the newly appended one survive.
    assert len(data) == 2
    assert data[0]["store_id"] == "old"
    assert data[1]["store_id"] == "store-abc"


# ---------------------------------------------------------------------------
# T9.3 — drivers required for non-suppressed revenue ranges
# ---------------------------------------------------------------------------


def test_drivers_required_for_non_suppressed_range_passes():
    er = _engine_run()
    offenders = assert_drivers_present_for_non_suppressed(er)
    assert offenders == []


def test_drivers_required_for_non_suppressed_range_catches_violation():
    er = EngineRun(
        recommendations=[
            PlayCard(
                play_id="bad_play",
                evidence_class=EvidenceClass.MEASURED,
                revenue_range=RevenueRange(
                    p10=10.0, p50=20.0, p90=30.0,
                    source=RevenueRangeSource.STORE_OBSERVED,
                    drivers=[],  # invalid: non-suppressed but no drivers
                    suppressed=False,
                ),
            )
        ]
    )
    offenders = assert_drivers_present_for_non_suppressed(er)
    assert offenders == ["bad_play"]


def test_drivers_required_skips_suppressed_ranges():
    er = EngineRun(
        recommendations=[
            PlayCard(
                play_id="cold_start_targeting",
                evidence_class=EvidenceClass.TARGETING,
                revenue_range=RevenueRange(
                    drivers=[],  # acceptable when suppressed
                    suppressed=True,
                ),
            )
        ]
    )
    offenders = assert_drivers_present_for_non_suppressed(er)
    assert offenders == []
