"""Milestone 1 T1.4: state-of-store Observation builder tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import Observation, ObservationClassification  # noqa: E402
from src.state_of_store import build_observations  # noqa: E402


def _aligned_canned():
    """A small but representative ``aligned`` dict (KPI snapshot shape)."""
    return {
        "anchor": "2025-08-25T12:00:00",
        "L28": {
            "aov": 80.0,
            "orders": 220,
            "net_sales": 17600.0,
            "repeat_rate_within_window": 0.18,
            "delta": {
                "aov": 0.05,  # +5% AOV
                "orders": -0.03,
                "repeat_rate_within_window": 0.01,
            },
            "prior": {
                "aov": 76.2,
                "orders": 227,
                "repeat_rate_within_window": 0.17,
            },
            "meta": {"identified_recent": 1500},
        },
    }


def test_returns_at_least_three_observations():
    obs = build_observations(_aligned_canned())
    assert len(obs) >= 3
    assert all(isinstance(o, Observation) for o in obs)


def test_returns_at_most_seven_observations():
    """Phase 5.3: relaxed cap from 5 to 7 to support more Watching slots
    (returning_customer_share + net_sales were added)."""
    obs = build_observations(
        _aligned_canned(),
        data_quality_flags=["bfcm_overlap", "refund_storm", "test_order_anomaly", "insufficient_clean_history"],
    )
    assert len(obs) <= 7


def test_metric_keys_present_for_each_observation():
    obs = build_observations(_aligned_canned())
    metrics = {o.supporting_metric for o in obs}
    # Three core metrics must all be present.
    assert "aov" in metrics
    assert "repeat_rate_within_window" in metrics
    assert "orders" in metrics


def test_classification_moved_when_delta_exceeds_threshold():
    obs = build_observations(_aligned_canned())
    aov_obs = next(o for o in obs if o.supporting_metric == "aov")
    # +5% > 1% AOV threshold -> MOVED.
    assert aov_obs.classification == ObservationClassification.MOVED
    assert aov_obs.change_magnitude == pytest.approx(0.05)


def test_classification_held_when_delta_below_threshold():
    aligned = _aligned_canned()
    aligned["L28"]["delta"]["aov"] = 0.001  # below 1% threshold
    obs = build_observations(aligned)
    aov_obs = next(o for o in obs if o.supporting_metric == "aov")
    assert aov_obs.classification == ObservationClassification.HELD


def test_anomaly_flags_surface_as_anomalous_observations():
    obs = build_observations(_aligned_canned(), data_quality_flags=["bfcm_overlap"])
    anomalous = [o for o in obs if o.classification == ObservationClassification.ANOMALOUS]
    assert len(anomalous) == 1
    # S13.6-T1b: Observation.text stripped; flag now carried on the
    # typed ``anomaly_flags`` list + ``supporting_metric`` slot.
    assert anomalous[0].anomaly_flags == ["bfcm_overlap"]
    assert anomalous[0].supporting_metric == "bfcm_overlap"


def test_handles_missing_aligned_gracefully():
    obs = build_observations(None)
    # Always returns >=3 even when input is empty (HELD classification).
    assert len(obs) >= 3
    assert all(isinstance(o, Observation) for o in obs)
    # All observations should have HELD classification (no data => no movement).
    assert all(o.classification == ObservationClassification.HELD for o in obs)


def test_handles_partial_aligned_gracefully():
    obs = build_observations({"L28": {"aov": 50.0}})
    assert len(obs) >= 3
    aov_obs = next(o for o in obs if o.supporting_metric == "aov")
    # AOV value present but delta missing -> HELD.
    assert aov_obs.classification == ObservationClassification.HELD
