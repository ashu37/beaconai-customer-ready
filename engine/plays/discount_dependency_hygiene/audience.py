"""Audience builder re-export (wave 1 — no behavior moved)."""
from __future__ import annotations

from src.audience_builders import (
    discount_dependency_hygiene_candidates as build_audience,
)

__all__ = ["build_audience"]
