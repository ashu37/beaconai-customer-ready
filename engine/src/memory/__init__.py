"""Lineage memory substrate (Sprint 2, S-2).

Per-merchant SQLite event log at ``data/<store_id>/memory.db``. Substrate
stands alone — no engine code consumes it in S-2. S-3 will wire writers
in ``src/decide.py``.

Public surface:

    from src.memory import open_memory, compute_lineage_id, MemoryStore
"""
from __future__ import annotations

from .lineage import compute_lineage_id
from .store import MemoryStore, open_memory
from .events import (
    CAMPAIGN_SENT_ALLOWED_CHANNELS,
    CAMPAIGN_SENT_EVENT_VERSION,
    CAMPAIGN_SENT_OPTIONAL_FIELDS,
    CAMPAIGN_SENT_REQUIRED_FIELDS,
    CampaignSentPayload,
    RECOMMENDATION_EVENT_VERSION,
    EvidenceSnapshot,
    ExpectedOutcome,
    RecommendationConsideredPayload,
    RecommendationEmittedPayload,
)
from .snapshot import verify_snapshot, write_immutable_snapshot
from .views import (
    empty_calibration_state,
    read_calibration_state,
    read_lineage_recent_emissions,
    read_lineage_timeline,
    read_open_recommendations,
)

__all__ = [
    "MemoryStore",
    "open_memory",
    "compute_lineage_id",
    "RECOMMENDATION_EVENT_VERSION",
    "EvidenceSnapshot",
    "ExpectedOutcome",
    "RecommendationConsideredPayload",
    "RecommendationEmittedPayload",
    "CAMPAIGN_SENT_ALLOWED_CHANNELS",
    "CAMPAIGN_SENT_EVENT_VERSION",
    "CAMPAIGN_SENT_OPTIONAL_FIELDS",
    "CAMPAIGN_SENT_REQUIRED_FIELDS",
    "CampaignSentPayload",
    "verify_snapshot",
    "write_immutable_snapshot",
    "empty_calibration_state",
    "read_calibration_state",
    "read_lineage_recent_emissions",
    "read_lineage_timeline",
    "read_open_recommendations",
]
