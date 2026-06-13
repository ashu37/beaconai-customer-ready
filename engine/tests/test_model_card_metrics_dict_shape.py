"""S13-T0: ModelCard ``metrics: Dict[str, float]`` shape tests.

T0 refactor moved per-substrate metric storage from typed Optional
fields to a ``metrics: Dict[str, float]`` dict on ``ModelCard``. The
legacy typed Optional names (``holdout_rank_spearman``,
``holdout_agg_ratio``, ``holdout_mape``, ``holdout_c_index``,
``holdout_brier_score_90d``, ``holdout_top_k_recall``, ``coverage_at_k``,
``segment_monotonicity_spearman``, ``quintile_coverage_min``) remain
readable on the dataclass instance via a ``__getattr__`` shim that
delegates to ``metrics.get(<key>)``. The legacy keys do NOT appear at
the engine_run.json level (JSON carries ``metrics`` only); JSON
consumers must read from ``metrics``.

Pinning these contracts here so the refactor (and the S15+ deprecation
of the shim) does not silently regress.
"""

from __future__ import annotations

import json

from src.engine_run import EngineRun
from src.predictive.model_card import ModelCard, ModelFitStatus


# ---------------------------------------------------------------------------
# Field-level shape pins
# ---------------------------------------------------------------------------


def test_metrics_dict_default_empty():
    """A freshly-constructed ModelCard with no metrics has ``metrics == {}``."""
    card = ModelCard(
        model_name="bgnbd",
        fit_status=ModelFitStatus.INSUFFICIENT_DATA,
    )
    assert card.metrics == {}


def test_metrics_dict_write_read_round_trip():
    """Write to ``metrics`` directly; read back via property shim works."""
    card = ModelCard(
        model_name="bgnbd",
        fit_status=ModelFitStatus.VALIDATED,
        metrics={
            "holdout_rank_spearman": 0.42,
            "holdout_agg_ratio": 0.91,
            "holdout_mape": 0.18,
        },
    )
    # Direct dict reads.
    assert card.metrics["holdout_rank_spearman"] == 0.42
    assert card.metrics["holdout_agg_ratio"] == 0.91
    assert card.metrics["holdout_mape"] == 0.18
    # Shim reads.
    assert card.holdout_rank_spearman == 0.42
    assert card.holdout_agg_ratio == 0.91
    assert card.holdout_mape == 0.18


def test_legacy_typed_field_reads_from_metrics():
    """``card.holdout_X`` returns ``metrics["holdout_X"]`` (and None when absent)."""
    card = ModelCard(
        model_name="survival",
        fit_status=ModelFitStatus.VALIDATED,
        metrics={"holdout_c_index": 0.71, "holdout_brier_score_90d": 0.18},
    )
    assert card.holdout_c_index == 0.71
    assert card.holdout_brier_score_90d == 0.18
    # Keys absent from metrics: shim returns None (no AttributeError).
    assert card.holdout_rank_spearman is None
    assert card.holdout_mape is None
    assert card.holdout_top_k_recall is None
    assert card.coverage_at_k is None
    assert card.segment_monotonicity_spearman is None
    assert card.quintile_coverage_min is None


def test_legacy_constructor_kwargs_back_compat_route_into_metrics():
    """Pre-S13 callers passing ``holdout_X=value`` kwargs still work; the
    value lands inside ``metrics[<key>]`` and the typed-shim read returns it.
    """
    card = ModelCard(
        model_name="bgnbd",
        fit_status=ModelFitStatus.VALIDATED,
        holdout_mape=0.21,
        holdout_rank_spearman=0.55,
        holdout_agg_ratio=0.92,
    )
    assert card.metrics == {
        "holdout_mape": 0.21,
        "holdout_rank_spearman": 0.55,
        "holdout_agg_ratio": 0.92,
    }
    # Shim still returns the same values.
    assert card.holdout_mape == 0.21
    assert card.holdout_rank_spearman == 0.55
    assert card.holdout_agg_ratio == 0.92


def test_metrics_dict_kwarg_wins_over_legacy_kwarg():
    """If a caller passes BOTH ``metrics={...}`` AND a legacy kwarg for
    the same key, the explicit ``metrics`` value wins. Legacy kwargs only
    fill keys not already supplied via the dict.
    """
    card = ModelCard(
        model_name="bgnbd",
        fit_status=ModelFitStatus.VALIDATED,
        metrics={"holdout_rank_spearman": 0.5},
        holdout_rank_spearman=0.99,  # ignored; metrics already had key
        holdout_agg_ratio=0.88,  # filled in; metrics had no agg_ratio
    )
    assert card.metrics["holdout_rank_spearman"] == 0.5
    assert card.metrics["holdout_agg_ratio"] == 0.88


# ---------------------------------------------------------------------------
# Engine_run.json serialization contract
# ---------------------------------------------------------------------------


def test_engine_run_json_serializes_metrics_dict():
    """Round-trip through ``EngineRun.to_dict`` / ``from_dict`` preserves
    the metrics dict and its values.
    """
    er = EngineRun()
    card = ModelCard(
        model_name="bgnbd",
        fit_status=ModelFitStatus.VALIDATED,
        metrics={
            "holdout_rank_spearman": 0.42,
            "holdout_agg_ratio": 0.91,
            "holdout_mape": 0.18,
        },
        parameters={"r": 0.5, "alpha": 8.0, "a": 0.2, "b": 2.1},
    )
    er.predictive_models["bgnbd"] = card
    out = er.to_dict()
    payload = json.loads(json.dumps(out))
    bg = payload["predictive_models"]["bgnbd"]
    assert "metrics" in bg
    assert bg["metrics"]["holdout_rank_spearman"] == 0.42
    assert bg["metrics"]["holdout_agg_ratio"] == 0.91
    assert bg["metrics"]["holdout_mape"] == 0.18


def test_engine_run_json_does_not_carry_legacy_typed_keys():
    """Metrics-only-in-JSON decision: the 9 legacy metric-field names do
    NOT appear as top-level keys on a serialized ModelCard. JSON consumers
    must read from ``card["metrics"]``. The shim is Python-object-level
    only.
    """
    er = EngineRun()
    card = ModelCard(
        model_name="bgnbd",
        fit_status=ModelFitStatus.VALIDATED,
        metrics={
            "holdout_rank_spearman": 0.42,
            "holdout_agg_ratio": 0.91,
            "holdout_mape": 0.18,
        },
    )
    er.predictive_models["bgnbd"] = card
    out = er.to_dict()
    payload = json.loads(json.dumps(out))
    bg = payload["predictive_models"]["bgnbd"]
    legacy_keys = {
        "holdout_mape",
        "holdout_rank_spearman",
        "holdout_agg_ratio",
        "holdout_c_index",
        "holdout_brier_score_90d",
        "holdout_top_k_recall",
        "coverage_at_k",
        "segment_monotonicity_spearman",
        "quintile_coverage_min",
    }
    assert legacy_keys.isdisjoint(bg.keys()), (
        f"Legacy typed-metric keys leaked into JSON top-level: "
        f"{legacy_keys & bg.keys()}"
    )


def test_engine_run_json_preserves_metrics_when_all_none():
    """Refusal / INSUFFICIENT_DATA states: empty metrics dict serializes
    as ``{}`` (no spurious legacy keys, no missing ``metrics`` slot).
    """
    er = EngineRun()
    card = ModelCard(
        model_name="bgnbd",
        fit_status=ModelFitStatus.INSUFFICIENT_DATA,
    )
    er.predictive_models["bgnbd"] = card
    out = er.to_dict()
    payload = json.loads(json.dumps(out))
    bg = payload["predictive_models"]["bgnbd"]
    assert bg["metrics"] == {}
