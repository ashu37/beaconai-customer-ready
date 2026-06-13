"""Vertical hard-refuse guard (Sprint 1 Ticket B-7, post-6B restructured plan).

Beacon's engine scope is hard-locked at ``{beauty, supplements, mixed}``.
A merchant whose resolved ``vertical_mode`` is outside this set is refused
at engine entry. The refusal short-circuits BEFORE the priors loader, the
feature builder, and the play registry run; otherwise the priors loader's
``mixed``-fallback would silently mask the refusal.

Design notes:

- This module is **leaf-only**: it imports nothing from
  ``src.action_engine``, ``src.decide``, ``src.guardrails``, or any
  feature/play module. It only depends on the typed engine_run schema
  (``src.engine_run``) and the canonical supported set
  (``src.play_registry._ALL_VERTICALS``). That keeps the guard usable at
  the orchestration boundary in ``src.main`` without dragging in the
  rest of the engine.
- The merchant-facing reason text lives in
  :data:`MERCHANT_FACING_REFUSAL_COPY`. Renderers (storytelling_v2)
  surface this string verbatim; the engine emits it as
  ``Abstain.reason`` on the refusal :class:`EngineRun`.
- The :class:`DataQualityFlag.VERTICAL_NOT_SUPPORTED` enum member is the
  typed ``data_quality_flag`` value for this refusal. It reuses the
  existing ``EngineRun.data_quality_flags`` slot — the schema is NOT
  extended.

Per the implementation plan, the supported set is sourced from
``src.play_registry._ALL_VERTICALS`` (single source of truth). A
frozen-contract test (in ``tests/test_vertical_hard_refuse.py``) pins
that set; any future PR that adds a vertical breaks the test, forcing a
founder-level scope decision.
"""

from __future__ import annotations

from typing import FrozenSet, Optional

from .engine_run import (
    Abstain,
    DataQualityFlag,
    DataWindow,
    DecisionState,
    EngineRun,
)
from .play_registry import _ALL_VERTICALS


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

#: Canonical supported set, re-exported for callers that don't want to reach
#: into ``src.play_registry`` directly. Identity-equal to
#: ``play_registry._ALL_VERTICALS``.
SUPPORTED_VERTICALS: FrozenSet[str] = _ALL_VERTICALS


#: Merchant-facing copy carried on the ABSTAIN_HARD payload's
#: ``Abstain.reason`` field. Verbatim from the B-7 ticket. The Agent
#: Swarm / renderer surfaces it as-is — no further string formatting.
MERCHANT_FACING_REFUSAL_COPY: str = (
    "Beacon currently supports Beauty and Supplements brands. "
    "Your store profile is outside our supported scope and we won't "
    "generate recommendations rather than guess."
)


def _normalize(vertical_mode: Optional[str]) -> Optional[str]:
    """Lowercase / strip the ``vertical_mode``; ``None`` / empty stay ``None``.

    Matches the casing convention used elsewhere in the engine
    (``priors_loader._matches_scope`` lowercases both sides). A blank
    string and ``None`` both fail the supported-set check; the guard
    refuses both rather than treating empty as ``mixed``.
    """

    if vertical_mode is None:
        return None
    s = str(vertical_mode).strip().lower()
    if not s:
        return None
    return s


def is_supported(vertical_mode: Optional[str]) -> bool:
    """Return True iff ``vertical_mode`` is in the supported set.

    ``None`` and empty strings return False — the guard refuses an
    unresolved vertical_mode rather than silently mapping it to ``mixed``.
    """

    norm = _normalize(vertical_mode)
    if norm is None:
        return False
    return norm in SUPPORTED_VERTICALS


def build_vertical_refusal_engine_run(
    *,
    store_id: Optional[str],
    vertical_mode: Optional[str],
) -> EngineRun:
    """Construct the minimal ABSTAIN_HARD :class:`EngineRun` for a refusal.

    Carries:

    - ``abstain.state = ABSTAIN_HARD``
    - ``abstain.reason = MERCHANT_FACING_REFUSAL_COPY``
    - ``data_quality_flags = [VERTICAL_NOT_SUPPORTED]``
    - empty ``recommendations`` and ``recommended_experiments``
    - empty ``considered`` and ``watching``

    The caller is responsible for serializing the returned EngineRun via
    ``to_dict`` (e.g. writing ``receipts/engine_run.json``) and for
    rendering an appropriate refusal briefing or skipping the briefing
    entirely.
    """

    del vertical_mode  # captured at the call site for logging if needed.

    return EngineRun(
        store_id=store_id,
        data_window=DataWindow(),
        cold_start=False,
        data_quality_flags=[DataQualityFlag.VERTICAL_NOT_SUPPORTED],
        # S13.6-T1a (Option D): ``Abstain.reason`` stripped per Pivot 2.
        # ``MERCHANT_FACING_REFUSAL_COPY`` is preserved as a module-level
        # constant for downstream narration / docs reference but no
        # longer ships on the typed contract surface.
        abstain=Abstain(state=DecisionState.ABSTAIN_HARD),
        recommendations=[],
        recommended_experiments=[],
        considered=[],
        watching=[],
    )


__all__ = [
    "SUPPORTED_VERTICALS",
    "MERCHANT_FACING_REFUSAL_COPY",
    "is_supported",
    "build_vertical_refusal_engine_run",
]
