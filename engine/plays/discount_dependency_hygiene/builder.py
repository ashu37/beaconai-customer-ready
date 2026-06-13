"""Measurement signal re-export (wave 1 — no behavior moved)."""
from __future__ import annotations

from src.measurement_builder import (
    _PRIOR_ANCHORED,
    build_prior_anchored_play_card as build_card,
)

PLAY_ID = "discount_dependency_hygiene"
measurement_signal_entry = _PRIOR_ANCHORED[PLAY_ID]

__all__ = ["PLAY_ID", "measurement_signal_entry", "build_card"]
