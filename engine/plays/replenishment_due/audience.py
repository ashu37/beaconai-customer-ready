"""Audience builder re-export (wave 1 — no behavior moved).

``build_audience`` is the exact same Python callable as
``src.audience_builders.replenishment_due_candidates``. Identity-verified
at startup by ``plays._registry.assert_identity_with_legacy()`` when
``ENGINE_V2_PLAY_LIBRARY_WAVE1`` is ON.
"""
from __future__ import annotations

from src.audience_builders import (
    replenishment_due_candidates as build_audience,
)

__all__ = ["build_audience"]
