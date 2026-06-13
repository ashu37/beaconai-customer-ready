"""Sprint 13.6 Ticket T1a (Option D) — outcome_log reason_text synthesis.

Founder + DS approved 2026-05-30. ``RejectedPlay.reason_text`` was
stripped from the engine contract surface per Pivot 2. The outcome log's
JSON schema must stay stable for D-2 forever-retention, so
``outcome_log.py`` synthesizes a non-empty textual ``reason_text``
locally at write time from the typed ``reason_code`` enum plus the
structured ``held_reason_detail`` dict.

This test pins the synthesis grammar:

- ``reason_code`` only           → ``"{REASON_CODE}"``.
- ``reason_code`` + detail dict  → ``"{REASON_CODE}: k1=v1, k2=v2, ..."``
  (keys sorted alphabetically for deterministic JSON serialization).
- ``reason_code is None``        → ``None`` (defensive — should not occur
  on well-formed RejectedPlay).
"""
from __future__ import annotations

from src.engine_run import EngineRun, RejectedPlay, ReasonCode
from src.outcome_log import _synthesize_reason_text, build_record


def test_synthesize_reason_text_code_only():
    out = _synthesize_reason_text(ReasonCode.AUDIENCE_TOO_SMALL, None)
    assert out == "audience_too_small"


def test_synthesize_reason_text_code_plus_detail():
    out = _synthesize_reason_text(
        ReasonCode.AUDIENCE_TOO_SMALL,
        {"observed": 312, "floor": 500},
    )
    # Keys sorted alphabetically for determinism.
    assert out == "audience_too_small: floor=500, observed=312"


def test_synthesize_reason_text_none_returns_none():
    assert _synthesize_reason_text(None, None) is None


def test_synthesize_reason_text_empty_detail_treated_as_no_detail():
    out = _synthesize_reason_text(ReasonCode.PRIOR_UNVALIDATED, {})
    assert out == "prior_unvalidated"


def test_build_record_emits_non_empty_synthesized_reason_text():
    """Round-trip: a RejectedPlay with typed reason_code +
    held_reason_detail produces a non-empty ``reason_text`` field on the
    outcome-log record (schema stability per D-2)."""
    rp = RejectedPlay(
        play_id="winback_dormant_cohort",
        reason_code=ReasonCode.AUDIENCE_TOO_SMALL,
        held_reason_detail={"observed": 42, "floor": 100},
    )
    er = EngineRun(considered=[rp])
    rec = build_record(er)
    assert len(rec["rejected"]) == 1
    rej_out = rec["rejected"][0]
    assert rej_out["reason_code"] == "audience_too_small"
    assert (
        rej_out["reason_text"]
        == "audience_too_small: floor=100, observed=42"
    )


def test_build_record_synthesized_reason_text_without_detail():
    rp = RejectedPlay(
        play_id="x",
        reason_code=ReasonCode.PRIOR_UNVALIDATED,
    )
    er = EngineRun(considered=[rp])
    rec = build_record(er)
    rej_out = rec["rejected"][0]
    assert rej_out["reason_text"] == "prior_unvalidated"
