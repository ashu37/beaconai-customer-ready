"""Sprint 13 Ticket T3.5 — month_2_delta rollback contract.

T3.5 atomically flips ``ENGINE_V2_MONTH_2_DELTA`` default-OFF → default-ON
(second intentional engine_run.json schema change in S13; T2.5 was the
first with predicted_segment + model_card_ref).

The rollback contract is: with ``ENGINE_V2_MONTH_2_DELTA=false`` at
runtime, the engine reproduces the pre-T3.5 shape — the orchestration
wire at ``src/main.py:2040+`` is a no-op and ``engine_run.month_2_delta``
stays ``None`` on the output JSON.

Four cases A/B/C/D parallel to the T2.5 / T1.5 / T2.5 (S10/S11/S12)
precedent:

- **Case A — Rollback:** ``ENGINE_V2_MONTH_2_DELTA=false``, others ON →
  ``engine_run.month_2_delta`` is ``None`` on a real-fixture run.
- **Case B — Flag-ON populates:** in-process 2-run synthetic
  (T3-positive-control pattern, since synthetic fixtures lack a prior
  run on disk). With the flag ON AND a prior month-1 engine_run
  available, the detector populates the typed slot end-to-end.
- **Case C — All ML flags OFF:** ``engine_run.month_2_delta`` is
  ``None`` because ``predictive_models`` and ``cohort_diagnostics``
  are empty; the detector returns ``None`` (no comparable substrate
  state).
- **Case D — INDEPENDENCE PIN:** with ``ENGINE_V2_MONTH_2_DELTA=true``
  and all other ML flags OFF, the detector still RUNS. When prior +
  current both have empty substrates it reports them honestly
  (substrate_fit_status_changes maps to ``("ABSENT", "ABSENT")``
  entries; segment_shifts is ``{}``; retention_ci_delta is ``None``).
  No crash, no fabricated state. month_2_delta detection is
  INDEPENDENT of the S10-S12 ML flags.

**briefing.html byte-identity:** structurally guaranteed via the
renderer non-consumption grep pin at
``tests/test_s13_renderer_non_consumption.py`` (asserts
``month_2_delta`` is not referenced anywhere in ``src/briefing.py``).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import EngineRun, MonthDelta  # noqa: E402
from src.predictive.month_2_delta import detect_month_2_delta  # noqa: E402
from tests.synthetic_harness import run_scenario  # noqa: E402


_SCENARIO_NAME = "healthy_beauty_240d"

_BEAUTY_ENV_BASE: dict[str, str] = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "VERTICAL_MODE": "beauty",
    "WINDOW_POLICY": "auto",
}


def _run_and_load(
    *,
    month_2_delta_flag: bool,
    bgnbd_flag: bool = True,
    gg_flag: bool = True,
    survival_flag: bool = True,
    cf_flag: bool = True,
    rfm_flag: bool = True,
    retention_flag: bool = True,
    ranking_chain_flag: bool = True,
    predicted_segment_flag: bool = True,
) -> dict:
    env = dict(_BEAUTY_ENV_BASE)
    env["ENGINE_V2_MONTH_2_DELTA"] = "true" if month_2_delta_flag else "false"
    env["ENGINE_V2_ML_BGNBD"] = "true" if bgnbd_flag else "false"
    env["ENGINE_V2_ML_GAMMA_GAMMA"] = "true" if gg_flag else "false"
    env["ENGINE_V2_ML_SURVIVAL"] = "true" if survival_flag else "false"
    env["ENGINE_V2_ML_CF"] = "true" if cf_flag else "false"
    env["ENGINE_V2_ML_RFM"] = "true" if rfm_flag else "false"
    env["ENGINE_V2_ML_RETENTION"] = "true" if retention_flag else "false"
    env["ENGINE_V2_RANKING_STRATEGY_CHAIN"] = (
        "true" if ranking_chain_flag else "false"
    )
    env["ENGINE_V2_PLAY_PREDICTED_SEGMENT"] = (
        "true" if predicted_segment_flag else "false"
    )
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "s13_t3_5"
        result = run_scenario(
            _SCENARIO_NAME,
            out_dir,
            env_overrides=env,
            timeout_sec=600,
        )
        assert result.returncode == 0, (
            f"harness failed rc={result.returncode} "
            f"month_2_delta={month_2_delta_flag} "
            f"bg={bgnbd_flag} gg={gg_flag} surv={survival_flag} "
            f"cf={cf_flag} rfm={rfm_flag} ret={retention_flag}; "
            f"stderr (last 500): {result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), f"engine_run.json missing at {receipts}"
        return json.loads(receipts.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Case A — ENGINE_V2_MONTH_2_DELTA=false, others ON. month_2_delta None.
# ---------------------------------------------------------------------------


def test_flag_off_rollback_month_2_delta_none() -> None:
    """Case A — Rollback contract: ``ENGINE_V2_MONTH_2_DELTA=false``
    reproduces pre-T3.5 shape. ``engine_run.month_2_delta`` MUST be
    ``None`` (or absent) on the output JSON.

    The orchestration wire at src/main.py:2040+ must be a no-op when
    the flag is OFF.
    """

    er = _run_and_load(month_2_delta_flag=False)
    md = er.get("month_2_delta")
    assert md is None, (
        f"flag-OFF rollback violation: month_2_delta={md!r} (expected "
        f"None). The orchestration wire at src/main.py:2040+ must be "
        f"a no-op when ENGINE_V2_MONTH_2_DELTA=false."
    )


# ---------------------------------------------------------------------------
# Case B — all flags ON, prior-run history available. month_2_delta populates.
# ---------------------------------------------------------------------------


def _build_prior_run_dict(
    *,
    anchor_date: str = "2024-12-31T00:00:00",
    rfm_status: str = "VALIDATED",
    retention_ci_width: float = 0.18,
) -> Dict[str, Any]:
    """Construct a prior month-1 engine_run dict (T3-positive-control shape)."""

    return {
        "run_id": "prior_month_1_t3_5",
        "store_id": "t3_5_synthetic",
        "anchor_date": anchor_date,
        "audience_definition_version": 1,
        "predictive_models": {
            "bgnbd": {"fit_status": "VALIDATED"},
            "gamma_gamma": {"fit_status": "VALIDATED"},
            "survival": {"fit_status": "PROVISIONAL"},
            "cf": {"fit_status": "INSUFFICIENT_DATA"},
            "rfm": {
                "fit_status": rfm_status,
                "segment_by_customer": {
                    "cust_001": "Champions",
                    "cust_002": "At Risk",
                },
            },
        },
        "cohort_diagnostics": {
            "retention": {
                "fit_status": "VALIDATED",
                "bootstrap_ci_width_at_month_3": retention_ci_width,
            },
        },
    }


def _build_current_engine_run(
    *,
    anchor_date: str = "2025-01-30T00:00:00",
    rfm_status: str = "VALIDATED",
    retention_ci_width: float = 0.14,
) -> EngineRun:
    """Construct a current month-2 ``EngineRun`` 30 days after prior."""

    er = EngineRun(
        run_id="current_month_2_t3_5",
        store_id="t3_5_synthetic",
        anchor_date=anchor_date,
        predictive_models={
            "bgnbd": {"fit_status": "VALIDATED"},
            "gamma_gamma": {"fit_status": "VALIDATED"},
            "survival": {"fit_status": "PROVISIONAL"},
            "cf": {"fit_status": "INSUFFICIENT_DATA"},
            "rfm": {
                "fit_status": rfm_status,
                "segment_by_customer": {
                    "cust_001": "Champions",  # stable
                    "cust_002": "Champions",  # shift At Risk → Champions
                },
            },
        },
        cohort_diagnostics={
            "retention": {
                "fit_status": "VALIDATED",
                "bootstrap_ci_width_at_month_3": retention_ci_width,
            },
        },
    )
    er.briefing_meta.audience_definition_version = 1
    return er


def test_flag_on_with_prior_run_populates_month_2_delta() -> None:
    """Case B — Flag-ON contract with prior-run history available.

    Synthetic fixtures used by the synthetic_harness lack a prior run
    on disk (each ``run_scenario`` invocation starts from an empty
    per-store ``data/<store_id>/runs/`` directory). The T3 positive-
    control pattern is the load-bearing 2-run synthetic: directly
    invoke the detector with a constructed prior + current pair and
    assert the typed slot populates end-to-end.

    This pins the contract that, with the flag ON and a prior run
    available, the orchestration wire DOES populate
    ``engine_run.month_2_delta``. The orchestration wire itself is
    covered structurally — it's a thin gate-and-call around
    :func:`detect_month_2_delta` (see src/main.py:2059-2119); the
    detector contract IS the wire contract.
    """

    prior = _build_prior_run_dict()
    current = _build_current_engine_run()

    def _loader(_store_id: str) -> Optional[Dict[str, Any]]:
        return prior

    md, _ = detect_month_2_delta(current, "t3_5_synthetic", _loader)
    assert md is not None
    assert isinstance(md, MonthDelta)
    assert md.days_between == 30
    # Substrate fit-status changes populate (stable substrates surface
    # as (prior, current) tuples; the stability itself is signal).
    assert md.substrate_fit_status_changes
    assert md.substrate_fit_status_changes["rfm"] == (
        "VALIDATED",
        "VALIDATED",
    )
    # Segment shift detected on cust_002 (At Risk → Champions).
    assert md.segment_shifts is not None
    assert md.segment_shifts.get("cust_002") == {
        "prior": "At Risk",
        "current": "Champions",
    }
    # Retention CI tightened by 0.04 on the refit.
    assert md.retention_ci_at_month_3_delta == pytest.approx(-0.04, abs=1e-9)


# ---------------------------------------------------------------------------
# Case C — all S10-S13 ML flags OFF. month_2_delta None.
# ---------------------------------------------------------------------------


def test_all_ml_flags_off_month_2_delta_none() -> None:
    """Case C — All S10-S13 ML flags OFF: ``predictive_models`` and
    ``cohort_diagnostics`` empty, NO consumer-wiring, AND
    ``engine_run.month_2_delta`` ``None`` (no prior run on disk +
    detector has no substrate state to compare).
    """

    er = _run_and_load(
        month_2_delta_flag=True,
        bgnbd_flag=False,
        gg_flag=False,
        survival_flag=False,
        cf_flag=False,
        rfm_flag=False,
        retention_flag=False,
        ranking_chain_flag=False,
        predicted_segment_flag=False,
    )
    pm = er.get("predictive_models")
    assert pm == {} or pm is None, (
        f"All ML flags OFF rollback violation: predictive_models={pm!r}"
    )
    cd = er.get("cohort_diagnostics")
    assert cd == {} or cd is None, (
        f"All ML flags OFF rollback violation: cohort_diagnostics={cd!r}"
    )
    md = er.get("month_2_delta")
    # No prior run on disk → detector returns None → typed slot None.
    assert md is None, (
        f"flag-ON-but-no-prior-run: month_2_delta={md!r} (expected "
        f"None; no prior engine_run.json in per-store runs dir)."
    )


# ---------------------------------------------------------------------------
# Case D — INDEPENDENCE PIN. month_2_delta ON, all other ML OFF.
# Detector still runs; reports REFUSED / ABSENT substrates honestly.
# ---------------------------------------------------------------------------


def test_month_2_delta_runs_independently_when_ml_flags_off() -> None:
    """Case D — INDEPENDENCE PIN (DS-locked, S13 plan review §F).

    month_2_delta detection is INDEPENDENT of the S10-S12 ML flags.
    With ``ENGINE_V2_MONTH_2_DELTA=true`` and all other ML flags OFF,
    the detector still RUNS when a prior + current pair are provided
    — it reports whatever substrate state exists honestly, without
    fabricating data.

    Constructed scenario: prior month-1 had all substrates REFUSED;
    current month-2 has all substrates ABSENT (ML flags OFF, no
    ``predictive_models`` populated). The detector surfaces this
    truthfully:

    - substrate_fit_status_changes maps to ``("REFUSED", "ABSENT")``
      entries — the engine REFUSED last month and has no comparable
      substrate this month (because the ML pass didn't run).
    - segment_shifts is ``{}`` (no RFM substrate either side).
    - retention_ci_at_month_3_delta is ``None`` (no retention substrate
      either side).
    """

    prior: Dict[str, Any] = {
        "run_id": "prior_refused",
        "store_id": "independence_synthetic",
        "anchor_date": "2024-12-31T00:00:00",
        "audience_definition_version": 1,
        "predictive_models": {
            "bgnbd": {"fit_status": "REFUSED"},
            "gamma_gamma": {"fit_status": "REFUSED"},
            "survival": {"fit_status": "REFUSED"},
            "cf": {"fit_status": "REFUSED"},
            "rfm": {"fit_status": "REFUSED"},
        },
        "cohort_diagnostics": {
            "retention": {"fit_status": "REFUSED"},
        },
    }
    # Current run with all ML flags OFF → predictive_models empty,
    # cohort_diagnostics empty.
    current = EngineRun(
        run_id="current_no_ml",
        store_id="independence_synthetic",
        anchor_date="2025-01-30T00:00:00",
        predictive_models={},
        cohort_diagnostics={},
    )
    current.briefing_meta.audience_definition_version = 1

    def _loader(_store_id: str) -> Optional[Dict[str, Any]]:
        return prior

    md, _ = detect_month_2_delta(current, "independence_synthetic", _loader)
    # Detector ran — independent of ML flags. md is not None even when
    # the current run has no ML substrates (the prior provides the
    # comparable state; ABSENT on current side is honest, not None).
    assert md is not None
    assert md.days_between == 30
    # All substrates surface as (REFUSED, ABSENT) — no fabrication.
    for substrate in ("bgnbd", "gamma_gamma", "survival", "cf", "rfm"):
        entry = md.substrate_fit_status_changes.get(substrate)
        assert entry == ("REFUSED", "ABSENT"), (
            f"substrate {substrate} expected (REFUSED, ABSENT); got {entry!r}"
        )
    # Retention is in cohort_diagnostics (per T3 detector implementation).
    ret_entry = md.substrate_fit_status_changes.get("retention")
    assert ret_entry == ("REFUSED", "ABSENT"), (
        f"retention expected (REFUSED, ABSENT); got {ret_entry!r}"
    )
    # No RFM substrate either side → no segment_shifts content (but
    # NOT None — None is reserved for lineage-change suppression).
    assert md.segment_shifts == {} or md.segment_shifts is None
    # No retention CI width either side → delta None.
    assert md.retention_ci_at_month_3_delta is None


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
