"""Play Library entry — winback_dormant_cohort (S6-T2 Tier-B builder).

Wave 1 migration target (S8-T4). Re-exports the audience builder + the
prior-anchored measurement signal entry from the legacy locations without
moving behavior. See ``plays/__init__.py`` for the byte-identical contract.
"""
from __future__ import annotations

from .audience import build_audience
from .builder import measurement_signal_entry

__all__ = ["build_audience", "measurement_signal_entry"]
