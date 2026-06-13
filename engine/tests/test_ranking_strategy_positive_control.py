"""Positive-control synthetic tests — ranking_strategy chain walk (S13-T1).

DS-mandated at S13-T0 review §D.5: the T1 chain-walker MUST ship with a
positive-control synthetic test that exercises the 5 most-meaningful
fall-through paths plus the load-bearing PROVISIONAL-never-falls-through
invariant plus the 3 AudienceIntent chain orderings.

Synthetic ModelCard fixtures are hand-constructed in-test with
``fit_status`` set directly — no engine run needed, no substrate fit
performed. This validates the chain selection logic in isolation.
"""

from __future__ import annotations

import pytest

from src.engine_run import FitWarning, FitWarningLevel
from src.predictive.model_card import ModelCard, ModelFitStatus
from src.predictive.ranking_strategy import (
    AudienceIntent,
    RankingStrategyResult,
    rank_audience,
)


# S13.6-T4 (D-S13-4 structural): fit_warnings now carries typed
# FitWarning instances. Helper to keep test assertions concise.
def _fw(level: FitWarningLevel, substrate: str) -> FitWarning:
    return FitWarning(level=level, substrate=substrate)


_INSUF = FitWarningLevel.MODEL_FIT_INSUFFICIENT_DATA
_REFUSED = FitWarningLevel.MODEL_FIT_REFUSED
_PROV = FitWarningLevel.PROVISIONAL_SELECTED


def _mc(status: ModelFitStatus, name: str = "") -> ModelCard:
    """Construct a synthetic ModelCard with the requested fit_status."""
    return ModelCard(model_name=name, fit_status=status)


# ---------------------------------------------------------------------------
# 5 fall-through paths (DS S13-T0 review §D.5)
# ---------------------------------------------------------------------------


def test_path_1_bgnbd_validated_stops_chain() -> None:
    """Path 1: BG/NBD VALIDATED → stop at position 0; no warnings."""
    predictive_models = {
        "bgnbd": _mc(ModelFitStatus.VALIDATED, "bgnbd"),
        "cf": _mc(ModelFitStatus.VALIDATED, "cf"),
        "survival": _mc(ModelFitStatus.VALIDATED, "survival"),
        "rfm": _mc(ModelFitStatus.VALIDATED, "rfm"),
    }
    result = rank_audience(predictive_models, AudienceIntent.GENERAL)
    assert result.strategy_used == "BGNBD"
    assert result.fit_status_chain == [("bgnbd", "VALIDATED")]
    assert result.fit_warnings == []
    assert result.intent == AudienceIntent.GENERAL


def test_path_2_bgnbd_insufficient_falls_to_cf_validated() -> None:
    """Path 2: BG/NBD INSUF → CF VALIDATED. One INSUFFICIENT_DATA warning."""
    predictive_models = {
        "bgnbd": _mc(ModelFitStatus.INSUFFICIENT_DATA, "bgnbd"),
        "cf": _mc(ModelFitStatus.VALIDATED, "cf"),
        "survival": _mc(ModelFitStatus.VALIDATED, "survival"),
        "rfm": _mc(ModelFitStatus.VALIDATED, "rfm"),
    }
    result = rank_audience(predictive_models, AudienceIntent.GENERAL)
    assert result.strategy_used == "CF"
    assert result.fit_status_chain == [
        ("bgnbd", "INSUFFICIENT_DATA"),
        ("cf", "VALIDATED"),
    ]
    assert result.fit_warnings == [_fw(_INSUF, "bgnbd")]


def test_path_3_bgnbd_refused_cf_insufficient_survival_validated() -> None:
    """Path 3: REFUSED + INSUF distinction preserved in warnings grammar."""
    predictive_models = {
        "bgnbd": _mc(ModelFitStatus.REFUSED, "bgnbd"),
        "cf": _mc(ModelFitStatus.INSUFFICIENT_DATA, "cf"),
        "survival": _mc(ModelFitStatus.VALIDATED, "survival"),
        "rfm": _mc(ModelFitStatus.VALIDATED, "rfm"),
    }
    result = rank_audience(predictive_models, AudienceIntent.GENERAL)
    assert result.strategy_used == "SURVIVAL"
    assert result.fit_status_chain == [
        ("bgnbd", "REFUSED"),
        ("cf", "INSUFFICIENT_DATA"),
        ("survival", "VALIDATED"),
    ]
    assert result.fit_warnings == [
        _fw(_REFUSED, "bgnbd"),
        _fw(_INSUF, "cf"),
    ]


def test_path_4_all_ml_insufficient_falls_to_rfm() -> None:
    """Path 4: 3 ML substrates INSUF → RFM VALIDATED."""
    predictive_models = {
        "bgnbd": _mc(ModelFitStatus.INSUFFICIENT_DATA, "bgnbd"),
        "cf": _mc(ModelFitStatus.INSUFFICIENT_DATA, "cf"),
        "survival": _mc(ModelFitStatus.INSUFFICIENT_DATA, "survival"),
        "rfm": _mc(ModelFitStatus.VALIDATED, "rfm"),
    }
    result = rank_audience(predictive_models, AudienceIntent.GENERAL)
    assert result.strategy_used == "RFM"
    assert result.fit_warnings == [
        _fw(_INSUF, "bgnbd"),
        _fw(_INSUF, "cf"),
        _fw(_INSUF, "survival"),
    ]
    assert result.fit_status_chain[-1] == ("rfm", "VALIDATED")


def test_path_5_all_refused_falls_through_to_recency() -> None:
    """Path 5: all 4 substrates REFUSED → recency last-resort floor."""
    predictive_models = {
        "bgnbd": _mc(ModelFitStatus.REFUSED, "bgnbd"),
        "cf": _mc(ModelFitStatus.REFUSED, "cf"),
        "survival": _mc(ModelFitStatus.REFUSED, "survival"),
        "rfm": _mc(ModelFitStatus.REFUSED, "rfm"),
    }
    result = rank_audience(predictive_models, AudienceIntent.GENERAL)
    assert result.strategy_used == "RECENCY"
    assert result.fit_warnings == [
        _fw(_REFUSED, "bgnbd"),
        _fw(_REFUSED, "cf"),
        _fw(_REFUSED, "survival"),
        _fw(_REFUSED, "rfm"),
    ]
    # Recency does NOT contribute to fit_status_chain (no ModelCard read).
    assert len(result.fit_status_chain) == 4
    assert all(status == "REFUSED" for _, status in result.fit_status_chain)


# ---------------------------------------------------------------------------
# PROVISIONAL invariant (load-bearing — DS S13 plan review §D.1).
# ---------------------------------------------------------------------------


def test_provisional_selected_does_not_fall_through_to_validated() -> None:
    """PROVISIONAL BG/NBD must STOP the chain, NOT fall through to VALIDATED CF.

    Load-bearing invariant from DS-LOCKED selection rule: "PROVISIONAL
    never falls through to a downstream VALIDATED".
    """
    predictive_models = {
        "bgnbd": _mc(ModelFitStatus.PROVISIONAL, "bgnbd"),
        "cf": _mc(ModelFitStatus.VALIDATED, "cf"),
        "survival": _mc(ModelFitStatus.VALIDATED, "survival"),
        "rfm": _mc(ModelFitStatus.VALIDATED, "rfm"),
    }
    result = rank_audience(predictive_models, AudienceIntent.GENERAL)
    assert result.strategy_used == "BGNBD"
    assert result.fit_status_chain == [("bgnbd", "PROVISIONAL")]
    assert result.fit_warnings == [_fw(_PROV, "bgnbd")]


# ---------------------------------------------------------------------------
# Intent-conditional chain ordering (DS-LOCKED §D.1).
# ---------------------------------------------------------------------------


def test_replenishment_timing_intent_orders_survival_first() -> None:
    """REPLENISHMENT_TIMING intent must consult survival at position 0."""
    predictive_models = {
        "bgnbd": _mc(ModelFitStatus.VALIDATED, "bgnbd"),
        "cf": _mc(ModelFitStatus.VALIDATED, "cf"),
        "survival": _mc(ModelFitStatus.VALIDATED, "survival"),
        "rfm": _mc(ModelFitStatus.VALIDATED, "rfm"),
    }
    result = rank_audience(predictive_models, AudienceIntent.REPLENISHMENT_TIMING)
    assert result.strategy_used == "SURVIVAL"
    assert result.fit_status_chain[0] == ("survival", "VALIDATED")


def test_lookalike_expansion_intent_orders_cf_first() -> None:
    """LOOKALIKE_EXPANSION intent must consult CF at position 0."""
    predictive_models = {
        "bgnbd": _mc(ModelFitStatus.VALIDATED, "bgnbd"),
        "cf": _mc(ModelFitStatus.VALIDATED, "cf"),
        "survival": _mc(ModelFitStatus.VALIDATED, "survival"),
        "rfm": _mc(ModelFitStatus.VALIDATED, "rfm"),
    }
    result = rank_audience(predictive_models, AudienceIntent.LOOKALIKE_EXPANSION)
    assert result.strategy_used == "CF"
    assert result.fit_status_chain[0] == ("cf", "VALIDATED")


def test_general_intent_orders_bgnbd_first() -> None:
    """GENERAL intent must consult BG/NBD at position 0 (default chain)."""
    predictive_models = {
        "bgnbd": _mc(ModelFitStatus.VALIDATED, "bgnbd"),
        "cf": _mc(ModelFitStatus.VALIDATED, "cf"),
        "survival": _mc(ModelFitStatus.VALIDATED, "survival"),
        "rfm": _mc(ModelFitStatus.VALIDATED, "rfm"),
    }
    result = rank_audience(predictive_models, AudienceIntent.GENERAL)
    assert result.strategy_used == "BGNBD"
    assert result.fit_status_chain[0] == ("bgnbd", "VALIDATED")


# ---------------------------------------------------------------------------
# Edge cases.
# ---------------------------------------------------------------------------


def test_missing_substrate_treated_as_insufficient_data() -> None:
    """Empty predictive_models dict → 4 INSUFFICIENT_DATA warnings + RECENCY."""
    result = rank_audience({}, AudienceIntent.GENERAL)
    assert result.strategy_used == "RECENCY"
    assert result.fit_warnings == [
        _fw(_INSUF, "bgnbd"),
        _fw(_INSUF, "cf"),
        _fw(_INSUF, "survival"),
        _fw(_INSUF, "rfm"),
    ]
    # Missing cards do NOT contribute to fit_status_chain (no card to read).
    assert result.fit_status_chain == []


def test_rank_audience_pure_function_no_side_effects() -> None:
    """Two calls with equal arguments must return equal results (stateless)."""
    predictive_models = {
        "bgnbd": _mc(ModelFitStatus.REFUSED, "bgnbd"),
        "cf": _mc(ModelFitStatus.PROVISIONAL, "cf"),
        "survival": _mc(ModelFitStatus.VALIDATED, "survival"),
        "rfm": _mc(ModelFitStatus.VALIDATED, "rfm"),
    }
    a = rank_audience(predictive_models, AudienceIntent.GENERAL)
    b = rank_audience(predictive_models, AudienceIntent.GENERAL)
    assert a.strategy_used == b.strategy_used
    assert a.fit_status_chain == b.fit_status_chain
    assert a.fit_warnings == b.fit_warnings
    assert a.intent == b.intent
    # Same input dict, same intent, called twice — pure.
    assert a == b


def test_partial_models_dict_treats_missing_as_insufficient_data() -> None:
    """If only BG/NBD is in dict (REFUSED), the rest fall through as INSUF."""
    predictive_models = {
        "bgnbd": _mc(ModelFitStatus.REFUSED, "bgnbd"),
    }
    result = rank_audience(predictive_models, AudienceIntent.GENERAL)
    assert result.strategy_used == "RECENCY"
    assert result.fit_warnings == [
        _fw(_REFUSED, "bgnbd"),
        _fw(_INSUF, "cf"),
        _fw(_INSUF, "survival"),
        _fw(_INSUF, "rfm"),
    ]


def test_result_is_dataclass_with_4_fields() -> None:
    """RankingStrategyResult contract: strategy_used, fit_status_chain,
    fit_warnings, intent."""
    result = rank_audience({}, AudienceIntent.GENERAL)
    assert isinstance(result, RankingStrategyResult)
    assert hasattr(result, "strategy_used")
    assert hasattr(result, "fit_status_chain")
    assert hasattr(result, "fit_warnings")
    assert hasattr(result, "intent")


def test_audience_intent_enum_has_exactly_three_values() -> None:
    """AudienceIntent is a closed 3-value enum (DS-locked)."""
    assert {i.value for i in AudienceIntent} == {
        "GENERAL",
        "REPLENISHMENT_TIMING",
        "LOOKALIKE_EXPANSION",
    }


@pytest.mark.parametrize(
    "intent,expected_first",
    [
        (AudienceIntent.GENERAL, "bgnbd"),
        (AudienceIntent.REPLENISHMENT_TIMING, "survival"),
        (AudienceIntent.LOOKALIKE_EXPANSION, "cf"),
    ],
)
def test_chain_order_position_zero_per_intent(intent, expected_first) -> None:
    """Position-0 substrate must match the DS-LOCKED chain head per intent."""
    predictive_models = {
        "bgnbd": _mc(ModelFitStatus.INSUFFICIENT_DATA, "bgnbd"),
        "cf": _mc(ModelFitStatus.INSUFFICIENT_DATA, "cf"),
        "survival": _mc(ModelFitStatus.INSUFFICIENT_DATA, "survival"),
        "rfm": _mc(ModelFitStatus.INSUFFICIENT_DATA, "rfm"),
    }
    result = rank_audience(predictive_models, intent)
    # The first warning emitted is for the position-0 substrate.
    assert result.fit_warnings[0] == _fw(_INSUF, expected_first)
    assert result.fit_status_chain[0][0] == expected_first
