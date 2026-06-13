"""Phase 5.3 — Extend Watching schema and soften filtering.

Tests:
- ``returning_customer_share`` can produce a WatchedSignal.
- ``net_sales`` can produce a WatchedSignal.
- Flat orders / load-bearing metrics produce a stable-watch entry.
- Watching renders at least one item on a healthy synthetic fixture.
- Repeat rate is suppressed / labeled as "not computed" when no
  identified customers exist (no misleading "0.0%").
- Cap holds at 4 watching signals.
"""
from __future__ import annotations

from src.decide import build_watching, MAX_WATCHING_SIGNALS
from src.engine_run import (
    Observation,
    ObservationClassification,
)
from src.state_of_store import build_observations


# ---------------------------------------------------------------------------
# Build_watching: returning_customer_share + net_sales recognized
# ---------------------------------------------------------------------------


def test_returning_customer_share_produces_watching_signal():
    obs = [
        Observation(
            supporting_metric="returning_customer_share",
            change_magnitude=0.02,
            classification=ObservationClassification.HELD,
        ),
    ]
    watching = build_watching(obs)
    assert len(watching) == 1
    sig = watching[0]
    assert sig.metric == "returning_customer_share"
    assert sig.threshold_to_act
    assert "retention" in sig.threshold_to_act.lower()


def test_net_sales_produces_watching_signal():
    obs = [
        Observation(
            supporting_metric="net_sales",
            change_magnitude=0.04,
            classification=ObservationClassification.HELD,
        ),
    ]
    watching = build_watching(obs)
    assert len(watching) == 1
    sig = watching[0]
    assert sig.metric == "net_sales"
    assert sig.threshold_to_act is not None


# ---------------------------------------------------------------------------
# Build_watching: load-bearing metrics with zero change still surface
# ---------------------------------------------------------------------------


def test_flat_orders_produces_stable_watching_entry():
    """Phase 5.3: flat (zero-change) orders is load-bearing -> shows as
    a 'stable, watching' entry rather than being filtered out."""
    obs = [
        Observation(
            supporting_metric="orders",
            change_magnitude=0.0,
            classification=ObservationClassification.HELD,
        ),
    ]
    watching = build_watching(obs)
    assert len(watching) == 1
    assert watching[0].metric == "orders"
    assert watching[0].trend == "flat"


def test_flat_returning_customer_share_produces_stable_watching_entry():
    obs = [
        Observation(
            supporting_metric="returning_customer_share",
            change_magnitude=0.0,
            classification=ObservationClassification.HELD,
        ),
    ]
    watching = build_watching(obs)
    assert len(watching) == 1
    assert watching[0].metric == "returning_customer_share"
    assert watching[0].trend == "flat"


def test_non_load_bearing_zero_change_metric_still_excluded():
    """A non-load-bearing flat metric stays excluded.

    Phase 6A Ticket A1 added ``aov`` to the load-bearing set per the
    contract-final spec, so the original AOV-based assertion no longer
    holds. The base contract -- "non-load-bearing flat metrics belong
    nowhere in Watching" -- is preserved here using a generic
    non-load-bearing metric.
    """
    obs = [
        Observation(
            supporting_metric="click_through_rate",
            change_magnitude=0.0,
            classification=ObservationClassification.HELD,
        ),
    ]
    watching = build_watching(obs)
    assert watching == []


# ---------------------------------------------------------------------------
# Build_watching cap holds at 4
# ---------------------------------------------------------------------------


def test_watching_cap_at_four_signals():
    obs = [
        Observation(
            supporting_metric=f"metric_{i}",
            change_magnitude=0.01 * (i + 1),
            classification=ObservationClassification.HELD,
        )
        for i in range(8)
    ]
    watching = build_watching(obs)
    assert len(watching) <= MAX_WATCHING_SIGNALS == 4


# ---------------------------------------------------------------------------
# state_of_store now emits returning_customer_share + net_sales
# ---------------------------------------------------------------------------


def test_state_of_store_emits_returning_customer_share():
    aligned = {
        "L28": {
            "aov": 70.0,
            "repeat_rate_within_window": 0.34,
            "orders": 1000,
            "net_sales": 70000.0,
            "returning_customer_share": 0.91,
            "delta": {
                "aov": 0.01,
                "repeat_rate_within_window": -0.01,
                "orders": 0.0,
                "net_sales": 0.05,
                "returning_customer_share": 0.06,
            },
            "meta": {"identified_recent": 800},
        }
    }
    obs = build_observations(aligned)
    metrics = {o.supporting_metric for o in obs}
    assert "returning_customer_share" in metrics
    assert "net_sales" in metrics


def test_state_of_store_suppresses_repeat_rate_when_no_identified_customers():
    """Phase 5.3: when meta.identified_recent == 0, repeat_rate_within_window
    is structurally not computed -> render a clear "not computed" label
    rather than a misleading "0.0%"."""
    aligned = {
        "L28": {
            "aov": 70.0,
            "repeat_rate_within_window": 0.0,
            "orders": 100,
            "net_sales": 7000.0,
            "delta": {"aov": 0.0, "repeat_rate_within_window": 0.0},
            "meta": {"identified_recent": 0},
        }
    }
    obs = build_observations(aligned)
    rr = next(o for o in obs if o.supporting_metric == "repeat_rate_within_window")
    # S13.6-T1b: Observation.text was stripped per Pivot 2. The
    # "not computed" suppression is now structural: classification is
    # HELD and the typed numerics (current/prior/delta_pct) stay None
    # so the renderer never advertises "0.0%" as a real reading.
    from src.engine_run import ObservationClassification
    assert rr.classification == ObservationClassification.HELD
    assert rr.change_magnitude is None
    assert rr.current is None
    assert rr.delta_pct is None


# ---------------------------------------------------------------------------
# End-to-end on a healthy synthetic fixture
# ---------------------------------------------------------------------------


def test_healthy_store_observations_yield_at_least_one_watching_signal():
    """Healthy store with all-load-bearing flat metrics still yields at
    least one Watching entry (Phase 5.3 acceptance)."""
    aligned = {
        "L28": {
            "aov": 70.0,
            "repeat_rate_within_window": 0.34,
            "orders": 1000,
            "net_sales": 70000.0,
            "returning_customer_share": 0.91,
            "delta": {
                "aov": 0.001,  # below 1% threshold -> HELD
                "repeat_rate_within_window": 0.0,  # flat -> HELD
                "orders": 0.0,  # flat orders -> stable-watch (load-bearing)
                "net_sales": 0.0,  # flat -> stable-watch (load-bearing)
                "returning_customer_share": 0.0,  # flat -> stable-watch
            },
            "meta": {"identified_recent": 800},
        }
    }
    obs = build_observations(aligned)
    watching = build_watching(obs)
    assert len(watching) >= 1
    metrics = {sig.metric for sig in watching}
    # At least one of the load-bearing metrics surfaces.
    assert any(m in metrics for m in ("orders", "net_sales", "returning_customer_share"))
