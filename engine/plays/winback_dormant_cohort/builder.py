"""Measurement signal re-export (wave 1 — no behavior moved).

``measurement_signal_entry`` is the exact same ``_PriorAnchoredSignal``
dataclass instance stored under ``src.measurement_builder._PRIOR_ANCHORED``
for this play_id. The shared prior-anchored builder
(``build_prior_anchored_play_card``) continues to be the single
construction site; wave 1 does not split that function.
"""
from __future__ import annotations

from src.measurement_builder import (
    _PRIOR_ANCHORED,
    build_prior_anchored_play_card as build_card,
)

PLAY_ID = "winback_dormant_cohort"
measurement_signal_entry = _PRIOR_ANCHORED[PLAY_ID]

__all__ = ["PLAY_ID", "measurement_signal_entry", "build_card"]
