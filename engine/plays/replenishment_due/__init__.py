"""Play Library entry — replenishment_due (S6-T3 Tier-B builder).

Wave 1 migration target (S8-T4). Re-exports the audience builder + the
prior-anchored measurement signal entry from the legacy locations without
moving behavior.

**KI-NEW-G honest-dormancy preserved:** this play is dormant on the Beauty
pinned fixture by design (per-SKU repeat-buyer distribution sits below the
D-S6-4 N>=30 floor). The migration does not alter the audience builder;
``replenishment_due`` continues to produce zero audience on Beauty at
both flag states. Including this play in wave 1 is load-bearing — per DS
verdict 2026-05-24 §3 Q6, it is the only wave-1 test case that verifies
the migration template handles dormant plays correctly.
"""
from __future__ import annotations

from .audience import build_audience
from .builder import measurement_signal_entry

__all__ = ["build_audience", "measurement_signal_entry"]
