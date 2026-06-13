"""Sprint 11 Ticket T1.5 — Cox PH survival orchestration rollback contract.

T1.5 atomically flips ``ENGINE_V2_ML_SURVIVAL`` default ON and wires
``fit_survival`` into ``src/main.py`` orchestration immediately after
the Gamma-Gamma block. The rollback contract is: with
``ENGINE_V2_ML_SURVIVAL=false`` at runtime, the engine reproduces the
pre-T1.5 shape exactly — no survival fit attempted, no parquet written,
``"survival"`` absent from ``engine_run.predictive_models``. BG/NBD and
Gamma-Gamma may still be present per their own flags.

With the flag ON (T1.5 default), the orchestration step fires and the
survival ModelCard lands on ``engine_run.predictive_models["survival"]``.
On the synthetic pinned fixtures the resulting ``fit_status`` is
expected to be ``REFUSED`` via the chained-refusal short-circuit
(BG/NBD already REFUSED or INSUFFICIENT_DATA on every fixture; per S11-T1
module contract / DS Option γ extends 2026-05-26).
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
    survival_flag: bool,
    bgnbd_flag: bool = True,
    gg_flag: bool = True,
) -> dict:
    env = dict(_BEAUTY_ENV_BASE)
    env["ENGINE_V2_ML_SURVIVAL"] = "true" if survival_flag else "false"
    env["ENGINE_V2_ML_BGNBD"] = "true" if bgnbd_flag else "false"
    env["ENGINE_V2_ML_GAMMA_GAMMA"] = "true" if gg_flag else "false"
    # S11-T2.5 (2026-05-28): ENGINE_V2_ML_CF flipped default-ON. The
    # S11-T1.5 survival-only rollback contract explicitly disables the
    # CF flag here so the per-test assertions (particularly
    # ``predictive_models == {}`` in test_all_flags_off) continue to pin
    # survival's rollback contract specifically. S11-T2.5's own
    # rollback test pins CF's rollback contract independently.
    env["ENGINE_V2_ML_CF"] = "false"
    # S12-T1.5 (2026-05-28): ENGINE_V2_ML_RFM flipped default-ON. The
    # S11-T1.5 survival-only rollback contract explicitly disables the
    # RFM flag here so the per-test assertions (particularly
    # ``predictive_models == {}`` in test_all_flags_off) continue to pin
    # survival's rollback contract specifically. S12-T1.5's own
    # rollback test (``tests/test_s12_t1_5_rfm_rollback.py``) pins RFM's
    # rollback contract independently.
    env["ENGINE_V2_ML_RFM"] = "false"
    # S12-T2.5 (2026-05-28): ENGINE_V2_ML_RETENTION flipped default-ON.
    # The S11-T1.5 survival-only rollback contract explicitly disables
    # the retention flag here so the per-test assertions continue to pin
    # survival's rollback contract specifically. S12-T2.5's own rollback
    # test (``tests/test_s12_t2_5_retention_rollback.py``) pins
    # retention's rollback contract independently.
    env["ENGINE_V2_ML_RETENTION"] = "false"
    # S13-T2.5 (2026-05-29): ENGINE_V2_PLAY_PREDICTED_SEGMENT flipped
    # default-ON. The T1.5 survival-only rollback contract explicitly
    # disables the consumer-wiring flag here so the PlayCard
    # ``predicted_segment`` / ``model_card_ref`` mutation pass does not
    # run alongside this test's survival-specific assertions. S13-T2.5's
    # own rollback test (``tests/test_s13_t2_5_predicted_segment_rollback.py``)
    # pins predicted_segment's rollback contract independently.
    env["ENGINE_V2_PLAY_PREDICTED_SEGMENT"] = "false"
    # S13-T3.5 (2026-05-29): ENGINE_V2_MONTH_2_DELTA flipped default-ON.
    # The T1.5 survival-only rollback contract explicitly disables the
    # month_2_delta detector here so the per-store prior-run lookup +
    # MonthDelta typed-slot population pass does not run alongside this
    # test's survival-specific assertions. S13-T3.5's own rollback test
    # (``tests/test_s13_t3_5_month_2_delta_rollback.py``) pins
    # month_2_delta's rollback contract independently.
    env["ENGINE_V2_MONTH_2_DELTA"] = "false"
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "s11_t1_5"
        result = run_scenario(
            _SCENARIO_NAME,
            out_dir,
            env_overrides=env,
            timeout_sec=600,
        )
        assert result.returncode == 0, (
            f"harness failed rc={result.returncode} surv={survival_flag} "
            f"bg={bgnbd_flag} gg={gg_flag}; stderr (last 500): "
            f"{result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), f"engine_run.json missing at {receipts}"
        return json.loads(receipts.read_text(encoding="utf-8"))


def test_flag_off_rollback_survival_absent():
    """Rollback contract: ENGINE_V2_ML_SURVIVAL=false reproduces pre-T1.5
    engine_run.json shape — ``"survival"`` absent from
    ``predictive_models``. BG/NBD and Gamma-Gamma may still be present
    per their own flags. The survival orchestration block at
    ``src/main.py`` must be a no-op when the survival flag is OFF.
    """
    pytest.importorskip("lifetimes")
    er = _run_and_load(survival_flag=False, bgnbd_flag=True, gg_flag=True)
    pm = er.get("predictive_models") or {}
    assert "survival" not in pm, (
        f"flag-OFF rollback violation: predictive_models['survival'] "
        f"present (keys={list(pm.keys())}). The orchestration block at "
        f"src/main.py must be a no-op when ENGINE_V2_ML_SURVIVAL=false."
    )


def test_flag_on_populates_survival_chained_refusal_on_beauty():
    """Flag-ON contract: ENGINE_V2_ML_SURVIVAL=true causes the
    orchestration step to fire and write a survival ModelCard to
    ``engine_run.predictive_models["survival"]``. On synthetic Beauty
    the expected fit_status is REFUSED with ``chained_bgnbd_refusal``
    (per S11-T1 module contract / DS Option γ extends): BG/NBD is
    already REFUSED on Beauty, so survival short-circuits."""
    pytest.importorskip("lifetimes")
    er = _run_and_load(survival_flag=True, bgnbd_flag=True, gg_flag=True)
    pm = er.get("predictive_models") or {}
    assert "survival" in pm, (
        f"flag-ON: expected predictive_models['survival'] populated; "
        f"got keys={list(pm.keys())}. The orchestration block at "
        f"src/main.py S11-T1.5 step did not run."
    )
    card = pm["survival"]
    assert isinstance(card, dict)
    assert card.get("model_name") == "survival"
    assert card.get("fit_status") == "REFUSED", (
        f"Unexpected fit_status on synthetic Beauty: "
        f"{card.get('fit_status')!r}. Beauty's BG/NBD is REFUSED on "
        f"synthetic data (Pivot 5); survival must chain-refuse."
    )
    warnings = card.get("fit_warnings") or []
    assert "chained_bgnbd_refusal" in warnings, (
        f"Expected 'chained_bgnbd_refusal' in fit_warnings on synthetic "
        f"Beauty; got {warnings!r}. BG/NBD ModelCard input to "
        f"fit_survival was not recognized as REFUSED/INSUFFICIENT_DATA."
    )


def test_all_flags_off_predictive_models_empty():
    """All three flags OFF: neither BG/NBD nor Gamma-Gamma nor survival
    writes to ``predictive_models``. Reproduces the pre-S10 shape exactly.
    """
    er = _run_and_load(survival_flag=False, bgnbd_flag=False, gg_flag=False)
    pm = er.get("predictive_models")
    assert pm == {} or pm is None, (
        f"All-flags-off rollback violation: predictive_models={pm!r} "
        f"(expected {{}} or None). No orchestration block may run."
    )


def test_survival_on_bgnbd_off_handles_missing_bgnbd_card():
    """Edge case: ENGINE_V2_ML_BGNBD=false but ENGINE_V2_ML_SURVIVAL=true.
    Survival must still produce a ModelCard without crashing — the
    BG/NBD chained input is None. Per ``fit_survival`` Step 1 contract
    (``src/predictive/survival.py``), ``bgnbd_model_card is None`` is
    treated as REFUSED and short-circuits to a REFUSED ModelCard with
    ``chained_bgnbd_refusal`` (rationale: no upstream signal at all).
    T1.5 must not change survival semantics; this test pins ONLY that
    the orchestration handles ``bgnbd_model_card=None`` cleanly (no
    exception, ModelCard populated on engine_run).
    """
    pytest.importorskip("lifetimes")
    er = _run_and_load(survival_flag=True, bgnbd_flag=False, gg_flag=False)
    pm = er.get("predictive_models") or {}
    assert "survival" in pm, (
        f"flag-ON survival with BG/NBD-OFF: expected "
        f"predictive_models['survival'] populated even when the "
        f"BG/NBD ModelCard input is absent; got keys={list(pm.keys())}."
    )
    assert "bgnbd" not in pm, (
        f"BG/NBD flag OFF but predictive_models['bgnbd'] present: "
        f"{list(pm.keys())!r}."
    )
    card = pm["survival"]
    assert isinstance(card, dict)
    assert card.get("model_name") == "survival"
    # Survival semantics unchanged: with bgnbd_model_card=None the
    # ``fit_survival`` chained-refusal gate fires (None treated as
    # REFUSED). fit_status must be one of the four documented states.
    assert card.get("fit_status") in {
        "VALIDATED",
        "PROVISIONAL",
        "REFUSED",
        "INSUFFICIENT_DATA",
    }, f"fit_status out of vocabulary: {card.get('fit_status')!r}"
