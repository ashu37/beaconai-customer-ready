"""S10-T0 — Lineage-keyed fatigue correctness fix.

Re-keys the ``gate_recently_run`` fatigue match in ``src/guardrails.py``
from the 3-tuple ``(play_id, audience_definition_id, store_id)`` to the
**four-component lineage tuple**

    (play_id, audience_definition_id, store_id, audience_definition_version)

aligning with ``src/memory/lineage.py::compute_lineage_id`` (which
already requires all four args per founder decision D-1).

The fix is DS-locked correctness; per
``agent_outputs/play-lifecycle-discussion-reconciled.md:47``:

    Engine-fatigue gating should be lineage-keyed (play_id ×
    audience_definition_id × store_id), not play_id-keyed. M5's current
    keying is a correctness bug regardless of broader lifecycle scope.

The ``RECENTLY_RUN_FATIGUE_ENABLED`` flag stays OFF — these tests exercise
the gate function directly (the same surface used by
``tests/test_per_merchant_isolation.py`` and ``tests/test_guardrails.py``).
Behavior under the live flag-OFF default is unchanged: byte-identical on
existing pinned fixtures by construction.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.engine_run import (
    Audience,
    EvidenceClass,
    PlayCard,
    ReasonCode,
)
from src.guardrails import gate_recently_run


def _make_card(play_id: str, audience_id: str) -> PlayCard:
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.MEASURED,
        audience=Audience(id=audience_id, definition=audience_id, size=100),
    )


def _recent_ts() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()


# ---------------------------------------------------------------------------
# 4-tuple positive match
# ---------------------------------------------------------------------------


def test_four_tuple_match_fires_when_all_components_match(tmp_path: Path):
    """Same lineage tuple (all four components equal) within the fatigue
    window must fire a ``RECENTLY_RUN_FATIGUE`` demotion."""
    path = tmp_path / "recommended_history.json"
    path.write_text(
        json.dumps(
            [
                {
                    "store_id": "store_alpha",
                    "play_id": "winback_21_45",
                    "audience_id": "winback_21_45_inactive",
                    "audience_definition_version": 1,
                    "ts": _recent_ts(),
                }
            ]
        )
    )
    cand = _make_card("winback_21_45", "winback_21_45_inactive")
    rej = gate_recently_run(
        cand,
        str(path),
        store_id="store_alpha",
        audience_definition_version=1,
    )
    assert rej is not None
    assert rej.reason_code == ReasonCode.RECENTLY_RUN_FATIGUE


# ---------------------------------------------------------------------------
# 4-tuple negative cases — each component, varied independently
# ---------------------------------------------------------------------------


def test_audience_definition_version_mismatch_does_not_fire(tmp_path: Path):
    """The S10-T0 correctness fix: bumping ``audience_definition_version``
    (per D-1) forks to a new lineage; the old fatigue record must NOT
    match the new lineage."""
    path = tmp_path / "recommended_history.json"
    path.write_text(
        json.dumps(
            [
                {
                    "store_id": "store_alpha",
                    "play_id": "winback_21_45",
                    "audience_id": "winback_21_45_inactive",
                    "audience_definition_version": 1,
                    "ts": _recent_ts(),
                }
            ]
        )
    )
    cand = _make_card("winback_21_45", "winback_21_45_inactive")
    # Candidate ran on v=2; the history record was emitted on v=1. New
    # lineage — fatigue must NOT fire.
    assert (
        gate_recently_run(
            cand,
            str(path),
            store_id="store_alpha",
            audience_definition_version=2,
        )
        is None
    )


def test_store_id_mismatch_does_not_fire(tmp_path: Path):
    path = tmp_path / "recommended_history.json"
    path.write_text(
        json.dumps(
            [
                {
                    "store_id": "store_alpha",
                    "play_id": "winback_21_45",
                    "audience_id": "winback_21_45_inactive",
                    "audience_definition_version": 1,
                    "ts": _recent_ts(),
                }
            ]
        )
    )
    cand = _make_card("winback_21_45", "winback_21_45_inactive")
    assert (
        gate_recently_run(
            cand,
            str(path),
            store_id="store_beta",
            audience_definition_version=1,
        )
        is None
    )


def test_play_id_mismatch_does_not_fire(tmp_path: Path):
    path = tmp_path / "recommended_history.json"
    path.write_text(
        json.dumps(
            [
                {
                    "store_id": "store_alpha",
                    "play_id": "winback_21_45",
                    "audience_id": "winback_21_45_inactive",
                    "audience_definition_version": 1,
                    "ts": _recent_ts(),
                }
            ]
        )
    )
    # Different play_id.
    cand = _make_card("discount_hygiene", "winback_21_45_inactive")
    assert (
        gate_recently_run(
            cand,
            str(path),
            store_id="store_alpha",
            audience_definition_version=1,
        )
        is None
    )


def test_audience_definition_id_mismatch_does_not_fire(tmp_path: Path):
    path = tmp_path / "recommended_history.json"
    path.write_text(
        json.dumps(
            [
                {
                    "store_id": "store_alpha",
                    "play_id": "winback_21_45",
                    "audience_id": "winback_21_45_inactive",
                    "audience_definition_version": 1,
                    "ts": _recent_ts(),
                }
            ]
        )
    )
    # Different audience_definition_id (via Audience.id).
    cand = _make_card("winback_21_45", "winback_60_120_inactive")
    assert (
        gate_recently_run(
            cand,
            str(path),
            store_id="store_alpha",
            audience_definition_version=1,
        )
        is None
    )


# ---------------------------------------------------------------------------
# Defensive backward-compat: legacy history records lack the version field
# ---------------------------------------------------------------------------


def test_record_without_version_still_matches_under_defensive_policy(
    tmp_path: Path,
):
    """Legacy records pre-dating ``audience_definition_version`` must
    still match on the available components — mirrors the existing
    defensive policy applied to ``store_id`` (see
    ``tests/test_per_merchant_isolation.py::test_record_without_store_id_still_matches``).
    """
    path = tmp_path / "recommended_history.json"
    path.write_text(
        json.dumps(
            [
                {
                    "store_id": "store_alpha",
                    "play_id": "winback_21_45",
                    "audience_id": "winback_21_45_inactive",
                    # No ``audience_definition_version`` field.
                    "ts": _recent_ts(),
                }
            ]
        )
    )
    cand = _make_card("winback_21_45", "winback_21_45_inactive")
    rej = gate_recently_run(
        cand,
        str(path),
        store_id="store_alpha",
        audience_definition_version=1,
    )
    assert rej is not None
    assert rej.reason_code == ReasonCode.RECENTLY_RUN_FATIGUE


# ---------------------------------------------------------------------------
# Flag-OFF path: no fatigue match attempted regardless of history state
# ---------------------------------------------------------------------------


def test_flag_off_no_fatigue_match_in_apply_guardrails(tmp_path: Path):
    """When ``RECENTLY_RUN_FATIGUE_ENABLED`` is OFF (the live default),
    ``apply_guardrails`` must not invoke the lineage match — even with a
    history file present that would otherwise trigger a 4-tuple match.

    Verifies the fix is truly dormant on the OFF path (the byte-identity
    invariant on pinned fixtures rests on this).
    """
    from src.engine_run import EngineRun
    from src.guardrails import apply_guardrails

    path = tmp_path / "recommended_history.json"
    path.write_text(
        json.dumps(
            [
                {
                    "store_id": "store_alpha",
                    "play_id": "winback_21_45",
                    "audience_id": "winback_21_45_inactive",
                    "audience_definition_version": 1,
                    "ts": _recent_ts(),
                }
            ]
        )
    )

    cand = _make_card("winback_21_45", "winback_21_45_inactive")
    er = EngineRun(
        run_id="test-s10-t0-flag-off",
        store_id="store_alpha",
        anchor_date="2026-05-25",
        recommendations=[cand],
    )

    # Flag explicitly OFF (the live default; included here for clarity).
    cfg = {"RECENTLY_RUN_FATIGUE_ENABLED": False}
    out = apply_guardrails(
        er,
        history_path=str(path),
        store_id="store_alpha",
        cfg=cfg,
    )

    # Candidate survives — no fatigue demotion was attempted.
    surviving_play_ids = [c.play_id for c in (out.recommendations or [])]
    assert "winback_21_45" in surviving_play_ids
    considered_codes = [
        getattr(r.reason_code, "value", r.reason_code)
        for r in (out.considered or [])
    ]
    assert ReasonCode.RECENTLY_RUN_FATIGUE.value not in considered_codes
