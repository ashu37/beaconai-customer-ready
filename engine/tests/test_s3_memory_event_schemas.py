"""S-3 prep — typed payload schema smoke tests.

Pins the shape of ``RecommendationEmittedPayload``,
``RecommendationConsideredPayload``, ``EvidenceSnapshot``, and
``ExpectedOutcome``. The substrate writer (``append_event``) doesn't
exist yet — these schemas are the frozen contract S-3 will emit.

Tests verify:
- Round-trip ``to_dict`` produces the documented JSON shape.
- ``RECOMMENDATION_EVENT_VERSION`` is pinned at ``1`` (any bump is a
  Swarm-team coordination event).
- All required fields exist; defaults behave as documented.
"""

from __future__ import annotations

from src.memory.events import (
    EvidenceSnapshot,
    ExpectedOutcome,
    RECOMMENDATION_EVENT_VERSION,
    RecommendationConsideredPayload,
    RecommendationEmittedPayload,
)


def test_event_version_pinned_at_one():
    """Pinned at 1 for the Sprint 2 freeze. Bumping is a frozen-contract
    change that requires updating ``docs/memory_substrate.md`` and
    coordinating with the Swarm team."""

    assert RECOMMENDATION_EVENT_VERSION == 1


def test_expected_outcome_to_dict_shape():
    eo = ExpectedOutcome(
        expected_direction="increase",
        min_interesting_effect_size=0.02,
        expected_observation_window_days=30,
    )
    d = eo.to_dict()
    assert d == {
        "expected_direction": "increase",
        "min_interesting_effect_size": 0.02,
        "expected_observation_window_days": 30,
    }


def test_evidence_snapshot_required_and_default_fields():
    es = EvidenceSnapshot(
        evidence_class="measured",
        window_label="L28",
        effect_abs=0.034,
        p_internal=0.012,
        sample_size=842,
    )
    d = es.to_dict()
    # Required fields
    assert d["evidence_class"] == "measured"
    assert d["window_label"] == "L28"
    assert d["effect_abs"] == 0.034
    assert d["p_internal"] == 0.012
    assert d["sample_size"] == 842
    # Defaults
    assert d["multiwindow_agreement"] is None
    assert d["data_quality_flags"] == []
    assert d["measurement_design_version"] == 1


def test_evidence_snapshot_targeting_class_allows_none_stats():
    """``targeting`` plays carry None for ``effect_abs`` and ``p_internal``
    per Phase 6A discipline. The schema must accept this."""

    es = EvidenceSnapshot(
        evidence_class="targeting",
        window_label="multiwindow",
        effect_abs=None,
        p_internal=None,
        sample_size=None,
    )
    d = es.to_dict()
    assert d["effect_abs"] is None
    assert d["p_internal"] is None
    assert d["sample_size"] is None


def test_recommendation_emitted_payload_to_dict():
    es = EvidenceSnapshot(
        evidence_class="measured",
        window_label="L28",
        effect_abs=0.05,
        p_internal=0.01,
        sample_size=500,
    )
    eo = ExpectedOutcome(
        expected_direction="increase",
        min_interesting_effect_size=0.02,
        expected_observation_window_days=30,
    )
    p = RecommendationEmittedPayload(
        event_version=RECOMMENDATION_EVENT_VERSION,
        run_id="run-uuid-001",
        lineage_id="abc123",
        store_id="beauty_alpha",
        play_id="discount_hygiene",
        audience_definition_id="aud-disc-v1",
        audience_definition_version=1,
        role="recommendation",
        expected_outcome=eo,
        snapshot_path="data/beauty_alpha/runs/run-uuid-001.json",
        snapshot_sha256="deadbeef" * 8,
    )
    d = p.to_dict()
    assert d["event_version"] == 1
    assert d["role"] == "recommendation"
    assert d["lineage_id"] == "abc123"
    assert d["store_id"] == "beauty_alpha"
    assert d["audience_definition_version"] == 1
    assert d["evidence_snapshot"]["evidence_class"] == "measured"
    assert d["expected_outcome"]["expected_direction"] == "increase"
    assert d["snapshot_sha256"] == "deadbeef" * 8


def test_recommendation_considered_payload_supports_null_evidence():
    """A play held for AUDIENCE_TOO_SMALL may not have run a measurement;
    evidence_snapshot / expected_outcome must accept None."""

    p = RecommendationConsideredPayload(
        event_version=RECOMMENDATION_EVENT_VERSION,
        run_id="run-uuid-002",
        lineage_id="def456",
        store_id="beauty_alpha",
        play_id="winback_campaign",
        audience_definition_id="aud-win-v1",
        audience_definition_version=1,
        reason_code="audience_too_small",
        expected_outcome=None,
    )
    d = p.to_dict()
    assert d["reason_code"] == "audience_too_small"
    assert d["evidence_snapshot"] is None
    assert d["expected_outcome"] is None
    assert d["snapshot_path"] is None
    assert d["snapshot_sha256"] is None
