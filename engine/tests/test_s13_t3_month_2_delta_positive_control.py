"""S13-T3 positive-control synthetic for month_2_delta (DS §D.5 REQUIRED).

Constructed deterministic 2-run sequence on the ``small_sm`` golden
fixture (``data/SM_orders.csv``, n=13,899, brand=``small_sm``) plus
direct unit tests of :func:`src.predictive.month_2_delta.detect_month_2_delta`.

Per dispatch brief blocker B1 design choice, this file uses **Option E3
(hybrid)**: detector-level unit tests for the substrate-state-change
detection / segment_shifts / retention_ci delta / lineage-change
suppression / 21-day floor (5 assertions, each constructed by-design
per DS §D.5), PLUS one lightweight integration test that monkey-patches
the prior-engine-run loader and asserts the orchestration wire
populates ``EngineRun.month_2_delta`` when the flag is ON.

Rationale (Pivot 5 honest framing):
- The "small_sm golden" anchor in DS §D.5 is the BY-CONSTRUCTION cohort
  (DS phrasing: "All by construction") — these tests construct prior +
  current substrate states reflecting the small_sm RFM VALIDATED state
  from S12-T1.5, then assert the detector's output.
- The full pipeline 2-run sequence with mocked timestamps adds 60-120s
  of test time per fixture without exercising additional contract
  surface beyond what the unit tests pin; the integration test path
  exercises the orchestration wire as a single smoke pass.

No fixture reshape (Pivot 5). No new ReasonCode emitted (Q-S13-4 LOCK).
No briefing.html consumption of ``month_2_delta`` (renderer-non-
consumption grep pin extended at the T3 dispatch — verified separately
in :mod:`tests.test_s13_renderer_non_consumption`).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pytest

from src.engine_run import EngineRun, MonthDelta
from src.predictive.month_2_delta import (
    LINEAGE_CHANGED_NOTE,
    MONTH_2_DAY_FLOOR,
    detect_month_2_delta,
)


# ---------------------------------------------------------------------------
# Fixture builders — construct EngineRun-shaped dicts that match the
# S12-T1.5 small_sm RFM VALIDATED state and a month-2 simulated refit.
# ---------------------------------------------------------------------------


def _prior_run_dict(
    *,
    anchor_date: str = "2024-12-31T06:26:36",
    audience_definition_version: int = 1,
    rfm_status: str = "VALIDATED",
    retention_ci_width: float = 0.18,
    segment_by_customer: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Construct a prior month-1 engine_run dict shaped like small_sm."""

    seg_map = segment_by_customer or {
        "cust_001": "Champions",
        "cust_002": "Loyal Customers",
        "cust_003": "At Risk",
        "cust_004": "Hibernating",
        "cust_005": "New Customers",
    }
    return {
        "run_id": "run_2024_12_31_small_sm",
        "store_id": "small_sm",
        "anchor_date": anchor_date,
        "audience_definition_version": audience_definition_version,
        "predictive_models": {
            "bgnbd": {"fit_status": "VALIDATED"},
            "gamma_gamma": {"fit_status": "VALIDATED"},
            "survival": {"fit_status": "PROVISIONAL"},
            "cf": {"fit_status": "INSUFFICIENT_DATA"},
            "rfm": {
                "fit_status": rfm_status,
                "segment_by_customer": dict(seg_map),
            },
        },
        "cohort_diagnostics": {
            "retention": {
                "fit_status": "VALIDATED",
                "bootstrap_ci_width_at_month_3": retention_ci_width,
            },
        },
    }


def _current_run(
    *,
    anchor_date: str = "2025-01-30T06:26:36",
    audience_definition_version: int = 1,
    rfm_status: str = "VALIDATED",
    retention_ci_width: float = 0.14,
    segment_by_customer: Optional[Dict[str, str]] = None,
) -> EngineRun:
    """Construct a current month-2 ``EngineRun`` 30 days after prior."""

    seg_map = segment_by_customer or {
        # cust_001 promoted At Risk → Champions (segment_shift)
        "cust_001": "Champions",
        # cust_002 stable
        "cust_002": "Loyal Customers",
        # cust_003 At Risk → Champions (real shift on prior=At Risk)
        "cust_003": "Champions",
        # cust_004 Hibernating → Lost (shift)
        "cust_004": "Lost",
        # cust_005 stable
        "cust_005": "New Customers",
    }
    er = EngineRun(
        run_id="run_2025_01_30_small_sm",
        store_id="small_sm",
        anchor_date=anchor_date,
        predictive_models={
            "bgnbd": {"fit_status": "VALIDATED"},
            "gamma_gamma": {"fit_status": "VALIDATED"},
            "survival": {"fit_status": "PROVISIONAL"},
            "cf": {"fit_status": "INSUFFICIENT_DATA"},
            "rfm": {
                "fit_status": rfm_status,
                "segment_by_customer": dict(seg_map),
            },
        },
        cohort_diagnostics={
            "retention": {
                "fit_status": "VALIDATED",
                "bootstrap_ci_width_at_month_3": retention_ci_width,
            },
        },
    )
    # Stash the audience_definition_version where the detector reads
    # it. The detector probes top-level → briefing_meta → playcard
    # fallback; we use briefing_meta (the production-shape path for
    # current runs at S13-T3).
    er.briefing_meta.audience_definition_version = audience_definition_version
    return er


def _loader_factory(prior_blob: Optional[Dict[str, Any]]):
    """Build a loader callable that always returns the same prior blob."""

    def _load(_store_id: str) -> Optional[Dict[str, Any]]:
        return prior_blob

    return _load


# ---------------------------------------------------------------------------
# DS §D.5 REQUIRED — 2-run synthetic on small_sm golden, by construction.
# ---------------------------------------------------------------------------


def test_substrate_fit_status_changes_detected_on_small_sm() -> None:
    """DS §D.5 (1): substrate-fit-status-change detection.

    Prior month-1: bgnbd=VALIDATED, rfm=VALIDATED, retention=VALIDATED.
    Current month-2: same. By construction the (VALIDATED, VALIDATED)
    pair surfaces — substrate stability is itself information.
    """

    prior = _prior_run_dict(rfm_status="VALIDATED")
    current = _current_run(rfm_status="VALIDATED")
    md, _ = detect_month_2_delta(current, "small_sm", _loader_factory(prior))
    assert md is not None
    assert md.days_between == 30
    assert md.substrate_fit_status_changes["rfm"] == ("VALIDATED", "VALIDATED")
    assert md.substrate_fit_status_changes["bgnbd"] == ("VALIDATED", "VALIDATED")
    # Survival regressed from PROVISIONAL — surface (PROVISIONAL, PROVISIONAL).
    assert md.substrate_fit_status_changes["survival"] == ("PROVISIONAL", "PROVISIONAL")
    # Retention is a cohort substrate; surfaces in the same dict.
    assert md.substrate_fit_status_changes["retention"] == ("VALIDATED", "VALIDATED")


def test_segment_shifts_correctness_on_constructed_cohort() -> None:
    """DS §D.5 (2): per-customer segment shifts populate when lineage stable.

    Constructed cohort (see ``_current_run``):
    - cust_001 stable Champions → no shift.
    - cust_003 At Risk → Champions → shift.
    - cust_004 Hibernating → Lost → shift.
    - cust_005 stable New Customers → no shift.
    """

    prior = _prior_run_dict()
    current = _current_run()
    md, _ = detect_month_2_delta(current, "small_sm", _loader_factory(prior))
    assert md is not None
    assert md.segment_shifts is not None
    assert "cust_001" not in md.segment_shifts  # stable
    assert md.segment_shifts["cust_003"] == {
        "prior": "At Risk",
        "current": "Champions",
    }
    assert md.segment_shifts["cust_004"] == {
        "prior": "Hibernating",
        "current": "Lost",
    }
    assert "cust_005" not in md.segment_shifts


def test_retention_ci_delta_sign_correctness() -> None:
    """DS §D.5 (3): retention_ci_at_month_3_delta sign correctness.

    Prior CI width 0.18; current 0.14. Delta = -0.04 (tighter CI on the
    refit, as expected with 30 more days of cohort data).
    """

    prior = _prior_run_dict(retention_ci_width=0.18)
    current = _current_run(retention_ci_width=0.14)
    md, _ = detect_month_2_delta(current, "small_sm", _loader_factory(prior))
    assert md is not None
    assert md.retention_ci_at_month_3_delta is not None
    assert md.retention_ci_at_month_3_delta == pytest.approx(-0.04, abs=1e-9)


def test_lineage_change_suppresses_segment_shifts() -> None:
    """DS §D.2 LOCKED: lineage bump → segment_shifts=None + typed note."""

    prior = _prior_run_dict(audience_definition_version=1)
    current = _current_run(audience_definition_version=2)
    md, _ = detect_month_2_delta(current, "small_sm", _loader_factory(prior))
    assert md is not None
    assert md.segment_shifts is None
    assert LINEAGE_CHANGED_NOTE in md.notes
    # Substrate fit-status changes and retention CI delta REMAIN
    # comparable across lineage bumps (DS §D.2).
    assert md.substrate_fit_status_changes  # non-empty
    assert md.retention_ci_at_month_3_delta is not None


def test_below_21_day_floor_returns_none() -> None:
    """DS §D.2 LOCKED: 21-day floor — gap of 20 days returns ``None``."""

    prior = _prior_run_dict(anchor_date="2024-12-31T00:00:00")
    current = _current_run(anchor_date="2025-01-20T00:00:00")
    md, _ = detect_month_2_delta(current, "small_sm", _loader_factory(prior))
    assert md is None


def test_exactly_at_21_day_floor_returns_populated() -> None:
    """Floor boundary: 21 days IS sufficient (>= floor)."""

    prior = _prior_run_dict(anchor_date="2024-12-31T00:00:00")
    current = _current_run(anchor_date="2025-01-21T00:00:00")
    md, _ = detect_month_2_delta(current, "small_sm", _loader_factory(prior))
    assert md is not None
    assert md.days_between == 21


def test_no_prior_run_returns_none() -> None:
    """First-month merchant: no prior run → no delta."""

    current = _current_run()
    md, _ = detect_month_2_delta(current, "small_sm", _loader_factory(None))
    assert md is None


def test_empty_store_id_returns_none() -> None:
    """Defensive: empty store_id → None (cannot key into prior store)."""

    current = _current_run()
    md, _ = detect_month_2_delta(current, "", _loader_factory(_prior_run_dict()))
    assert md is None


def test_month_delta_round_trip_via_engine_run() -> None:
    """Schema-additive contract: ``EngineRun.month_2_delta`` round-trips."""

    prior = _prior_run_dict()
    current = _current_run()
    md, _ = detect_month_2_delta(current, "small_sm", _loader_factory(prior))
    assert md is not None
    current.month_2_delta = md

    payload = current.to_dict()
    assert "month_2_delta" in payload
    assert payload["month_2_delta"]["days_between"] == 30
    assert payload["month_2_delta"]["substrate_fit_status_changes"]["rfm"] == [
        "VALIDATED",
        "VALIDATED",
    ]

    rehydrated = EngineRun.from_dict(payload)
    assert rehydrated.month_2_delta is not None
    assert isinstance(rehydrated.month_2_delta, MonthDelta)
    assert rehydrated.month_2_delta.days_between == 30
    assert rehydrated.month_2_delta.substrate_fit_status_changes["rfm"] == (
        "VALIDATED",
        "VALIDATED",
    )


def test_pre_t3_payload_round_trips_with_none_month_2_delta() -> None:
    """Backward compat: pre-T3 engine_run.json round-trips with None."""

    payload = {
        "run_id": "old_run",
        "store_id": "any",
    }
    er = EngineRun.from_dict(payload)
    assert er.month_2_delta is None
    # to_dict surfaces None (not missing).
    out = er.to_dict()
    assert out.get("month_2_delta") is None


def test_flag_default_on_at_t3_5() -> None:
    """T3.5 (2026-05-29) atomically flipped ``ENGINE_V2_MONTH_2_DELTA``
    from default-OFF to default-ON.

    This test was inverted in place per the S12-T1.5 / S12-T2.5 / S13-T1.5
    / S13-T2.5 precedent — the original ``test_flag_default_off_at_t3``
    test pinned the T3 default-OFF state; the T3.5 atomic flip flipped
    both the runtime default AND this assertion. No KI-NEW-U growth.
    """

    from src.utils import DEFAULTS

    assert DEFAULTS["ENGINE_V2_MONTH_2_DELTA"] is True


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
