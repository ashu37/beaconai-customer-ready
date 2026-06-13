"""Ranking-strategy fallback-chain module (Sprint 13 — T1).

DS-locked intent-conditional chain walker that selects ONE ranking
substrate (BG/NBD, CF, survival, RFM, recency-floor) from the per-store
``EngineRun.predictive_models`` dict, based on the audience's intent.

Module is FLAG-OFF at T1: it ships behind ``ENGINE_V2_RANKING_STRATEGY_CHAIN``
(default ``false``) and is NOT yet wired into any consumer
(``src/main.py`` / ``src/audience_builders.py``). T2+ wires this module
as the consumer side per IM S13 plan §D.

Selection rule (DS-LOCKED — S13 plan review §D.1, v2 §B.0)
==========================================================

Chain order is intent-conditional:

- **GENERAL:** BG/NBD → CF → survival → RFM → recency.
- **REPLENISHMENT_TIMING:** survival → BG/NBD → CF → RFM → recency.
- **LOOKALIKE_EXPANSION:** CF → BG/NBD → survival → RFM → recency.

For each chain position the substrate is **SELECTED** iff
``fit_status in {VALIDATED, PROVISIONAL}``. Otherwise (REFUSED or
INSUFFICIENT_DATA) the chain advances to the next position.

**PROVISIONAL never falls through to a downstream VALIDATED** — a
VALIDATED CF does not override a PROVISIONAL BG/NBD that already cleared
its position. Load-bearing invariant: once a substrate clears its
position with PROVISIONAL it terminates the chain.

``"recency"`` is the non-ML last-resort floor — when reached, it is
always selected. No ``predictive_models`` lookup is performed for it.

fit_warnings grammar (List[FitWarning], LOCKED — S13.6-T4 typed)
================================================================

S13.6-T4 (D-S13-4 structural): the grammar that historically lived as
``List[str]`` of the form ``"{LEVEL}:{substrate}"`` is now expressed
structurally as ``List[FitWarning]`` (each entry is a
:class:`src.engine_run.FitWarning` with
``level: FitWarningLevel`` + ``substrate: str``). Pre-T4 callers that
parsed colons MUST read ``.level`` and ``.substrate`` instead.

Per-position fall-through warnings (one per position walked past, in
chain order):

- ``FitWarning(MODEL_FIT_INSUFFICIENT_DATA, substrate)`` — chain
  advanced past this position because the substrate's ``fit_status``
  was ``INSUFFICIENT_DATA`` (engine declined to fit; expected on thin
  merchants per S10 cold-start verdict §4.2).
- ``FitWarning(MODEL_FIT_REFUSED, substrate)`` — chain advanced past
  this position because the substrate's ``fit_status`` was ``REFUSED``
  (engine tried and the fit failed; model-health issue worth operator
  attention).

Plus one terminal warning when applicable:

- ``FitWarning(PROVISIONAL_SELECTED, substrate)`` — chain stopped at
  this position with PROVISIONAL. Surfaces the "ranking usable,
  absolute magnitudes not quotable to merchant" caveat.

VALIDATED selection emits **no fit_warning** for the selected position
(happy path; no surfacing needed). A full fall-through to ``"recency"``
emits only the per-position fall-through warnings (no terminal warning
on the recency floor).

The INSUFFICIENT_DATA vs REFUSED distinction matters for operator audit
per S10 cold-start verdict §4.2 and is preserved across the warnings
grammar (separate prefixes).

Forward-compat (DS S13-T0 review §F)
====================================

This module reads ``card.fit_status`` directly (a real ``ModelCard``
dataclass field) — NOT through the legacy ``__getattr__`` shim. Metric
access (if added later) MUST use ``card.metrics.get(<key>)``, not the
shim. The shim is back-compat only and slated for S15+ removal.

Consumer pattern (T2+)
======================

::

    from src.predictive.ranking_strategy import (
        AudienceIntent,
        rank_audience,
    )
    result = rank_audience(engine_run.predictive_models, AudienceIntent.GENERAL)
    # result.strategy_used in {"BGNBD", "CF", "SURVIVAL", "RFM", "RECENCY"}
    # result.fit_warnings: operator-readable per-position trace
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Literal, Optional, Tuple

from src.engine_run import FitWarning, FitWarningLevel
from src.predictive.model_card import ModelCard, ModelFitStatus


# ---------------------------------------------------------------------------
# AudienceIntent — closed enum (3 values; DS-locked S13 plan v2 §B.1).
# ---------------------------------------------------------------------------


class AudienceIntent(str, Enum):
    """Intent label that determines the substrate-chain order.

    Closed set. Adding a fourth intent requires DS sign-off (each new
    intent must come with a published intent-conditional chain order).
    """

    GENERAL = "GENERAL"
    REPLENISHMENT_TIMING = "REPLENISHMENT_TIMING"
    LOOKALIKE_EXPANSION = "LOOKALIKE_EXPANSION"


# ---------------------------------------------------------------------------
# Intent → chain-order mapping (DS-LOCKED — see module docstring).
# ---------------------------------------------------------------------------

_CHAIN_ORDER_BY_INTENT: Dict[AudienceIntent, Tuple[str, ...]] = {
    AudienceIntent.GENERAL: ("bgnbd", "cf", "survival", "rfm", "recency"),
    AudienceIntent.REPLENISHMENT_TIMING: ("survival", "bgnbd", "cf", "rfm", "recency"),
    AudienceIntent.LOOKALIKE_EXPANSION: ("cf", "bgnbd", "survival", "rfm", "recency"),
}


# ---------------------------------------------------------------------------
# RankingStrategyResult dataclass.
# ---------------------------------------------------------------------------


_StrategyName = Literal["BGNBD", "CF", "SURVIVAL", "RFM", "RECENCY"]


@dataclass
class RankingStrategyResult:
    """Typed return value of :func:`rank_audience`.

    Fields:

    - ``strategy_used``: uppercase canonical name of the substrate
      selected ("BGNBD" / "CF" / "SURVIVAL" / "RFM" / "RECENCY"). ``None``
      only if the chain was not run (defensive default; not produced by
      ``rank_audience`` since every chain ends at the "recency" floor).
    - ``fit_status_chain``: ordered list of ``(substrate_name,
      fit_status_value)`` tuples for every chain position visited up to
      and including the selected one. ``recency`` does NOT contribute
      (no ModelCard lookup is performed for it). Empty list when no
      walking occurred (defensive).
    - ``fit_warnings``: operator-readable summary per the LOCKED grammar
      (see module docstring). S13.6-T4: typed ``List[FitWarning]``.
      Order matches walk order: one ``MODEL_FIT_...`` entry per
      fall-through, then optionally one ``PROVISIONAL_SELECTED`` entry
      at the end.
    - ``intent``: the ``AudienceIntent`` used (audit traceability).
    """

    intent: AudienceIntent
    strategy_used: Optional[_StrategyName] = None
    fit_status_chain: List[Tuple[str, str]] = field(default_factory=list)
    fit_warnings: List[FitWarning] = field(default_factory=list)


# ---------------------------------------------------------------------------
# rank_audience — pure function.
# ---------------------------------------------------------------------------


def rank_audience(
    predictive_models: Dict[str, ModelCard],
    intent: AudienceIntent,
) -> RankingStrategyResult:
    """Walk the intent-conditional fallback chain; return the selection.

    Pure function. No side effects. Stateless. Two calls with equal
    arguments return equal results.

    Args:
        predictive_models: ``engine_run.predictive_models`` (the per-
            substrate ``Dict[str, ModelCard]``). RetentionCard is NOT in
            this dict (retention lives in ``cohort_diagnostics`` and is
            not a ranker), so the chain never consults it. A substrate
            name missing from this dict is treated as ``INSUFFICIENT_DATA``
            (same warning prefix, same advance behavior).
        intent: the ``AudienceIntent`` driving the chain order.

    Returns:
        :class:`RankingStrategyResult`. ``strategy_used`` is always one
        of the 5 ``_StrategyName`` values (the recency floor guarantees
        termination).

    Note: at T1 this function does NOT take an audience_df argument —
    customer-ranking-WITHIN-audience using the selected strategy is the
    T2 consumer concern. T1 builds the strategy-selection logic only.
    """

    chain_order = _CHAIN_ORDER_BY_INTENT[intent]
    result = RankingStrategyResult(intent=intent)

    for substrate_name in chain_order:
        if substrate_name == "recency":
            # Non-ML last-resort floor. Always selects; no ModelCard
            # lookup. Does NOT append to fit_status_chain (there is no
            # fit_status for the recency floor).
            result.strategy_used = "RECENCY"
            return result

        card = predictive_models.get(substrate_name)
        if card is None:
            # Missing ModelCard → treated as INSUFFICIENT_DATA (engine
            # didn't even produce a card for this substrate). Same audit
            # story as INSUFFICIENT_DATA: "we didn't try" (well, the
            # producer didn't even register a card; semantically
            # equivalent for the consumer).
            result.fit_warnings.append(
                FitWarning(
                    level=FitWarningLevel.MODEL_FIT_INSUFFICIENT_DATA,
                    substrate=substrate_name,
                )
            )
            continue

        # Direct dataclass-field read (NOT through the legacy
        # __getattr__ shim — fit_status is a real field). Forward-compat
        # for S15+ shim removal per DS S13-T0 review §F.
        status: ModelFitStatus = card.fit_status
        result.fit_status_chain.append((substrate_name, status.value))

        if status == ModelFitStatus.VALIDATED:
            # SELECT. No fit_warning emitted for VALIDATED (happy path).
            result.strategy_used = _to_strategy_name(substrate_name)
            return result

        if status == ModelFitStatus.PROVISIONAL:
            # SELECT. Emit the PROVISIONAL_SELECTED terminal warning.
            # PROVISIONAL does NOT fall through to a downstream
            # VALIDATED — load-bearing invariant.
            result.fit_warnings.append(
                FitWarning(
                    level=FitWarningLevel.PROVISIONAL_SELECTED,
                    substrate=substrate_name,
                )
            )
            result.strategy_used = _to_strategy_name(substrate_name)
            return result

        if status == ModelFitStatus.INSUFFICIENT_DATA:
            result.fit_warnings.append(
                FitWarning(
                    level=FitWarningLevel.MODEL_FIT_INSUFFICIENT_DATA,
                    substrate=substrate_name,
                )
            )
            continue

        if status == ModelFitStatus.REFUSED:
            result.fit_warnings.append(
                FitWarning(
                    level=FitWarningLevel.MODEL_FIT_REFUSED,
                    substrate=substrate_name,
                )
            )
            continue

        # Defensive: any future ModelFitStatus value not enumerated
        # above is treated as a hard fall-through with a REFUSED-style
        # surfacing (model-health issue worth operator attention).
        result.fit_warnings.append(
            FitWarning(
                level=FitWarningLevel.MODEL_FIT_REFUSED,
                substrate=substrate_name,
            )
        )

    # Unreachable in practice (the "recency" sentinel terminates every
    # chain), but defensive: if a future intent's chain order omits
    # "recency", strategy_used remains None and the caller can detect it.
    return result


def _to_strategy_name(substrate_name: str) -> _StrategyName:
    """Canonical uppercase strategy name for a substrate dict key.

    Matches the per-substrate ModelCard naming pattern. Recency is
    handled inline by the caller (no ModelCard lookup).
    """

    # Closed mapping; mypy-friendly via the Literal annotation.
    if substrate_name == "bgnbd":
        return "BGNBD"
    if substrate_name == "cf":
        return "CF"
    if substrate_name == "survival":
        return "SURVIVAL"
    if substrate_name == "rfm":
        return "RFM"
    # Defensive: any unknown substrate gets surfaced as its uppercase
    # form (won't pass the Literal type check at the call site under
    # strict mypy, but the function will not crash at runtime).
    return substrate_name.upper()  # type: ignore[return-value]


__all__ = [
    "AudienceIntent",
    "RankingStrategyResult",
    "rank_audience",
]
