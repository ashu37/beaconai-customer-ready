"""Sprint 12 Ticket T2.5 — Retention curves orchestration rollback contract.

T2.5 atomically flips ``ENGINE_V2_ML_RETENTION`` default ON and wires
``fit_retention`` into ``src/main.py`` orchestration immediately after the
RFM PREDICTIVE_FIT block. The rollback contract is: with
``ENGINE_V2_ML_RETENTION=false`` at runtime, the engine reproduces the
pre-T2.5 shape exactly — no retention fit attempted, no RetentionCard
written, ``"retention"`` absent from ``engine_run.cohort_diagnostics``.
BG/NBD, Gamma-Gamma, survival, CF, and RFM may still be present per their
own flags.

With the flag ON (T2.5 default), the orchestration step fires and the
RetentionCard lands on ``engine_run.cohort_diagnostics["retention"]``.

**Architectural separation:** retention lives in
``cohort_diagnostics`` (NEW typed slot from S12-T2), NOT
``predictive_models`` (which is contractually a per-customer ranker
shape). This test pins both slots independently.

**Independence pin (DS-locked, S12 plan review §C; mirrors CF + RFM):**
Retention is INDEPENDENT of BG/NBD. The orchestration wire passes NO
``bgnbd_model_card`` argument. Retention must produce its own state
based on its own data even when BG/NBD is OFF, and
``chained_bgnbd_refusal`` (survival-only) must NEVER appear in
retention's ``fit_warnings``.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
    retention_flag: bool,
    bgnbd_flag: bool = True,
    gg_flag: bool = True,
    survival_flag: bool = True,
    cf_flag: bool = True,
    rfm_flag: bool = True,
) -> dict:
    env = dict(_BEAUTY_ENV_BASE)
    env["ENGINE_V2_ML_RETENTION"] = "true" if retention_flag else "false"
    env["ENGINE_V2_ML_BGNBD"] = "true" if bgnbd_flag else "false"
    env["ENGINE_V2_ML_GAMMA_GAMMA"] = "true" if gg_flag else "false"
    env["ENGINE_V2_ML_SURVIVAL"] = "true" if survival_flag else "false"
    env["ENGINE_V2_ML_CF"] = "true" if cf_flag else "false"
    env["ENGINE_V2_ML_RFM"] = "true" if rfm_flag else "false"
    # S13-T2.5 (2026-05-29): ENGINE_V2_PLAY_PREDICTED_SEGMENT flipped
    # default-ON. The T2.5 retention-only rollback contract explicitly
    # disables the consumer-wiring flag here so the PlayCard
    # ``predicted_segment`` / ``model_card_ref`` mutation pass does not
    # run alongside this test's retention-specific assertions. S13-T2.5's
    # own rollback test (``tests/test_s13_t2_5_predicted_segment_rollback.py``)
    # pins predicted_segment's rollback contract independently.
    env["ENGINE_V2_PLAY_PREDICTED_SEGMENT"] = "false"
    # S13-T3.5 (2026-05-29): ENGINE_V2_MONTH_2_DELTA flipped default-ON.
    # The T2.5 retention-only rollback contract explicitly disables the
    # month_2_delta detector here so the per-store prior-run lookup +
    # MonthDelta typed-slot population pass does not run alongside this
    # test's retention-specific assertions. S13-T3.5's own rollback test
    # (``tests/test_s13_t3_5_month_2_delta_rollback.py``) pins
    # month_2_delta's rollback contract independently.
    env["ENGINE_V2_MONTH_2_DELTA"] = "false"
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "s12_t2_5"
        result = run_scenario(
            _SCENARIO_NAME,
            out_dir,
            env_overrides=env,
            timeout_sec=600,
        )
        assert result.returncode == 0, (
            f"harness failed rc={result.returncode} retention={retention_flag} "
            f"bg={bgnbd_flag} gg={gg_flag} surv={survival_flag} cf={cf_flag} "
            f"rfm={rfm_flag}; stderr (last 500): {result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), f"engine_run.json missing at {receipts}"
        return json.loads(receipts.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Case A: rollback — retention OFF, others ON
# ---------------------------------------------------------------------------


def test_flag_off_rollback_retention_absent():
    """Case A — Rollback contract: ENGINE_V2_ML_RETENTION=false
    reproduces pre-T2.5 engine_run.json shape — ``"retention"`` absent
    from ``cohort_diagnostics``. BG/NBD, Gamma-Gamma, survival, CF, and
    RFM may still be present in ``predictive_models`` per their own
    flags. The retention orchestration block at ``src/main.py`` must be
    a no-op when the retention flag is OFF.
    """
    pytest.importorskip("lifetimes")
    er = _run_and_load(
        retention_flag=False,
        bgnbd_flag=True,
        gg_flag=True,
        survival_flag=True,
        cf_flag=True,
        rfm_flag=True,
    )
    cd = er.get("cohort_diagnostics") or {}
    assert "retention" not in cd, (
        f"flag-OFF rollback violation: cohort_diagnostics['retention'] "
        f"present (keys={list(cd.keys())}). The orchestration block at "
        f"src/main.py must be a no-op when ENGINE_V2_ML_RETENTION=false."
    )


# ---------------------------------------------------------------------------
# Case B: all 6 ML flags ON, retention RetentionCard populated on Beauty
# ---------------------------------------------------------------------------


def test_flag_on_populates_retention_on_beauty():
    """Case B — Flag-ON contract: all 6 ML flags ON causes the retention
    orchestration step to fire and write a RetentionCard to
    ``engine_run.cohort_diagnostics["retention"]``. ``fit_status`` MUST
    be one of the documented four-state vocabulary
    {VALIDATED, PROVISIONAL, REFUSED, INSUFFICIENT_DATA}.

    Per S12-T2.5 dispatch (DS T2 verdict §I): Beauty (~259 days
    ≈ 8-9 first-purchase months) is expected to land **PROVISIONAL**
    (below MATURE 12-cohort VALIDATED floor; clears the 6-cohort
    PROVISIONAL relaxation floor at 0.5× multiplier).

    This test asserts the four-state vocabulary and the additive
    retention-specific fields (cohort_count + bootstrap_ci_width_at_month_3
    + cumulative_retention_monotonicity_violation). It does NOT pin a
    specific status — that is captured in the summary file VERBATIM per
    fixture.

    **Architectural pin:** retention lives in ``cohort_diagnostics``,
    NOT ``predictive_models``. The card carries ``model_name="retention"``.
    """
    pytest.importorskip("lifetimes")
    er = _run_and_load(
        retention_flag=True,
        bgnbd_flag=True,
        gg_flag=True,
        survival_flag=True,
        cf_flag=True,
        rfm_flag=True,
    )
    cd = er.get("cohort_diagnostics") or {}
    assert "retention" in cd, (
        f"flag-ON: expected cohort_diagnostics['retention'] populated; "
        f"got keys={list(cd.keys())}. The orchestration block at "
        f"src/main.py S12-T2.5 step did not run."
    )
    # ARCHITECTURAL PIN: retention must NOT appear in predictive_models.
    pm = er.get("predictive_models") or {}
    assert "retention" not in pm, (
        f"ARCHITECTURAL VIOLATION: 'retention' present in "
        f"predictive_models ({list(pm.keys())!r}). Retention is a "
        f"COHORT-AGGREGATE diagnostic and lives in cohort_diagnostics "
        f"per DS S12 plan review §C — NOT predictive_models."
    )

    card = cd["retention"]
    assert isinstance(card, dict)
    assert card.get("model_name") == "retention"
    status = card.get("fit_status")
    assert status in {
        "VALIDATED",
        "PROVISIONAL",
        "REFUSED",
        "INSUFFICIENT_DATA",
    }, f"fit_status out of vocabulary: {status!r}"

    # Additive retention-specific fields must be present.
    for required_field in (
        "cohort_count",
        "min_cohort_size",
        "bootstrap_ci_width_at_month_3",
        "cumulative_retention_monotonicity_violation",
        "months_horizon",
        "cohorts",
        "bootstrap_iterations",
        "seed",
        "fit_timestamp",
    ):
        assert required_field in card, (
            f"RetentionCard schema missing field {required_field!r}; "
            f"got keys={sorted(card.keys())!r}"
        )


# ---------------------------------------------------------------------------
# Case C: all 6 ML flags OFF — predictive_models AND cohort_diagnostics empty
# ---------------------------------------------------------------------------


def test_all_flags_off_both_slots_empty():
    """Case C — All 6 ML flags OFF: no orchestration block writes to
    either ``predictive_models`` or ``cohort_diagnostics``. Reproduces
    the pre-S10 / pre-S12-T2 shape exactly.
    """
    er = _run_and_load(
        retention_flag=False,
        bgnbd_flag=False,
        gg_flag=False,
        survival_flag=False,
        cf_flag=False,
        rfm_flag=False,
    )
    pm = er.get("predictive_models")
    assert pm == {} or pm is None, (
        f"All-flags-off rollback violation: predictive_models={pm!r} "
        f"(expected {{}} or None). No orchestration block may run."
    )
    cd = er.get("cohort_diagnostics")
    assert cd == {} or cd is None, (
        f"All-flags-off rollback violation: cohort_diagnostics={cd!r} "
        f"(expected {{}} or None). No orchestration block may run."
    )


# ---------------------------------------------------------------------------
# Case D: INDEPENDENCE PIN — retention on, BG/NBD off; retention must fit
# ---------------------------------------------------------------------------


def test_retention_runs_independently_when_bgnbd_off():
    """Case D — INDEPENDENCE PIN (DS-locked S12 plan review §C; mirrors
    CF + RFM independence posture).

    With ``ENGINE_V2_ML_RETENTION=true`` and all other ML substrates OFF
    (BG/NBD / G-G / survival / CF / RFM), retention must still fit
    independently. The orchestration wire MUST NOT pass a
    ``bgnbd_model_card`` argument to ``fit_retention`` (this contract is
    also pinned at the API surface via T2's
    ``test_fit_retention_signature_does_not_accept_bgnbd_model_card``).

    Retention's fit_status must be determined by its own data (not by a
    chained refusal). The survival-only warning ``chained_bgnbd_refusal``
    must NEVER appear in retention's ``fit_warnings`` — that warning
    belongs to ``fit_survival`` only. Retention has its own four-state
    classifier based on bootstrap_ci_width_at_month_3 (PRIMARY) +
    cohort_count (SECONDARY) + cumulative_retention_monotonicity_violation
    (REFUSED gate).

    This is the LOAD-BEARING NEGATIVE ASSERTION pinning the
    INDEPENDENT (CF-/RFM-style) orchestration wire shape and forbidding
    any accidental copy-paste of the survival/G-G chained-refusal
    pattern.
    """
    er = _run_and_load(
        retention_flag=True,
        bgnbd_flag=False,
        gg_flag=False,
        survival_flag=False,
        cf_flag=False,
        rfm_flag=False,
    )
    cd = er.get("cohort_diagnostics") or {}
    assert "retention" in cd, (
        f"flag-ON retention with BG/NBD-OFF: expected "
        f"cohort_diagnostics['retention'] populated even when BG/NBD "
        f"is OFF; got keys={list(cd.keys())}. Retention is INDEPENDENT "
        f"of BG/NBD — the orchestration block must run on the retention "
        f"flag alone."
    )
    pm = er.get("predictive_models") or {}
    assert "bgnbd" not in pm, (
        f"BG/NBD flag OFF but predictive_models['bgnbd'] present: "
        f"{list(pm.keys())!r}."
    )
    card = cd["retention"]
    assert isinstance(card, dict)
    assert card.get("model_name") == "retention"
    status = card.get("fit_status")
    # INDEPENDENCE PIN: fit_status is determined by retention's own data
    # and gates. It must be one of the four documented states (not a
    # chained-refusal artifact).
    assert status in {
        "VALIDATED",
        "PROVISIONAL",
        "REFUSED",
        "INSUFFICIENT_DATA",
    }, f"fit_status out of vocabulary: {status!r}"

    # CRITICAL INDEPENDENCE ASSERTION: chained_bgnbd_refusal is a
    # survival-only warning. Retention MUST NOT emit it under any
    # circumstance — its presence here would indicate someone
    # copy-pasted the survival/G-G chained input pattern into the
    # retention orchestration wire.
    warnings_list = card.get("fit_warnings") or []
    assert "chained_bgnbd_refusal" not in warnings_list, (
        f"INDEPENDENCE VIOLATION: retention's fit_warnings contains "
        f"'chained_bgnbd_refusal' ({warnings_list!r}). Retention is "
        f"INDEPENDENT of BG/NBD (DS-locked); this warning is "
        f"survival-only. The orchestration wire at src/main.py "
        f"S12-T2.5 has incorrectly chained retention on BG/NBD."
    )
