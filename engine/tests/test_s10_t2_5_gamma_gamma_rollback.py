"""Sprint 10 Ticket T2.5 — Gamma-Gamma orchestration rollback contract.

T2.5 atomically flips ``ENGINE_V2_ML_GAMMA_GAMMA`` default ON and wires
``fit_gamma_gamma`` into ``src/main.py`` orchestration immediately after
the BG/NBD block. The rollback contract is: with
``ENGINE_V2_ML_GAMMA_GAMMA=false`` at runtime, the engine reproduces
the pre-T2.5 shape exactly — no G-G fit attempted, no parquet written,
``"gamma_gamma"`` absent from ``engine_run.predictive_models``. BG/NBD
may still be present per its own flag.

With the flag ON (T2.5 default), the orchestration step fires and the
G-G ModelCard lands on ``engine_run.predictive_models["gamma_gamma"]``.
On the synthetic pinned fixtures the resulting ``fit_status`` is
expected to be ``REFUSED`` via the chained-refusal short-circuit
(BG/NBD already REFUSED or INSUFFICIENT_DATA on every fixture; per IM
plan §C.2 / DS Option γ).
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
    *, gg_flag: bool, bgnbd_flag: bool = True
) -> dict:
    env = dict(_BEAUTY_ENV_BASE)
    env["ENGINE_V2_ML_GAMMA_GAMMA"] = "true" if gg_flag else "false"
    env["ENGINE_V2_ML_BGNBD"] = "true" if bgnbd_flag else "false"
    # S11-T1.5 (2026-05-26): ENGINE_V2_ML_SURVIVAL flipped default-ON.
    # The T2.5 G-G-only rollback contract explicitly disables the
    # survival flag here so the per-test assertions (particularly
    # ``predictive_models == {}`` in test_both_flags_off) continue to
    # pin G-G's rollback contract specifically. S11-T1.5's own rollback
    # test (``tests/test_s11_t1_5_survival_rollback.py``) pins the
    # survival rollback contract independently.
    env["ENGINE_V2_ML_SURVIVAL"] = "false"
    # S11-T2.5 (2026-05-28): ENGINE_V2_ML_CF flipped default-ON. The
    # T2.5 G-G-only rollback contract explicitly disables the CF flag
    # here so the assertion on ``predictive_models == {}`` continues to
    # pin G-G's rollback contract specifically. S11-T2.5's own rollback
    # test pins CF's rollback contract independently.
    env["ENGINE_V2_ML_CF"] = "false"
    # S12-T1.5 (2026-05-28): ENGINE_V2_ML_RFM flipped default-ON. The
    # T2.5 G-G-only rollback contract explicitly disables the RFM flag
    # here so the assertion on ``predictive_models == {}`` continues to
    # pin G-G's rollback contract specifically. S12-T1.5's own rollback
    # test (``tests/test_s12_t1_5_rfm_rollback.py``) pins RFM's
    # rollback contract independently.
    env["ENGINE_V2_ML_RFM"] = "false"
    # S12-T2.5 (2026-05-28): ENGINE_V2_ML_RETENTION flipped default-ON.
    # The T2.5 G-G-only rollback contract explicitly disables the
    # retention flag here so the assertion on
    # ``predictive_models == {}`` continues to pin G-G's rollback
    # contract specifically. S12-T2.5's own rollback test
    # (``tests/test_s12_t2_5_retention_rollback.py``) pins retention's
    # rollback contract independently.
    env["ENGINE_V2_ML_RETENTION"] = "false"
    # S13-T2.5 (2026-05-29): ENGINE_V2_PLAY_PREDICTED_SEGMENT flipped
    # default-ON. The T2.5 G-G-only rollback contract explicitly disables
    # the consumer-wiring flag here so the PlayCard
    # ``predicted_segment`` / ``model_card_ref`` mutation pass does not
    # run alongside this test's G-G-specific assertions. S13-T2.5's own
    # rollback test (``tests/test_s13_t2_5_predicted_segment_rollback.py``)
    # pins predicted_segment's rollback contract independently.
    env["ENGINE_V2_PLAY_PREDICTED_SEGMENT"] = "false"
    # S13-T3.5 (2026-05-29): ENGINE_V2_MONTH_2_DELTA flipped default-ON.
    # The T2.5 G-G-only rollback contract explicitly disables the
    # month_2_delta detector here so the per-store prior-run lookup +
    # MonthDelta typed-slot population pass does not run alongside this
    # test's G-G-specific assertions. S13-T3.5's own rollback test
    # (``tests/test_s13_t3_5_month_2_delta_rollback.py``) pins
    # month_2_delta's rollback contract independently.
    env["ENGINE_V2_MONTH_2_DELTA"] = "false"
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "t2_5"
        result = run_scenario(
            _SCENARIO_NAME,
            out_dir,
            env_overrides=env,
            timeout_sec=600,
        )
        assert result.returncode == 0, (
            f"harness failed rc={result.returncode} gg={gg_flag} "
            f"bg={bgnbd_flag}; stderr (last 500): "
            f"{result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), f"engine_run.json missing at {receipts}"
        return json.loads(receipts.read_text(encoding="utf-8"))


def test_flag_off_rollback_gamma_gamma_absent():
    """Rollback contract: ENGINE_V2_ML_GAMMA_GAMMA=false reproduces
    pre-T2.5 engine_run.json shape — ``"gamma_gamma"`` absent from
    ``predictive_models``. BG/NBD may still be present per its own flag.
    The G-G orchestration block at src/main.py must be a no-op when
    the G-G flag is OFF.
    """
    er = _run_and_load(gg_flag=False, bgnbd_flag=True)
    pm = er.get("predictive_models") or {}
    assert "gamma_gamma" not in pm, (
        f"flag-OFF rollback violation: predictive_models['gamma_gamma'] "
        f"present (keys={list(pm.keys())}). The orchestration block at "
        f"src/main.py must be a no-op when ENGINE_V2_ML_GAMMA_GAMMA=false."
    )


def test_flag_on_populates_gamma_gamma_chained_refusal_on_beauty():
    """Flag-ON contract: ENGINE_V2_ML_GAMMA_GAMMA=true causes the
    orchestration step to fire and write a Gamma-Gamma ModelCard to
    ``engine_run.predictive_models["gamma_gamma"]``. On synthetic Beauty
    the expected fit_status is REFUSED with ``chained_bgnbd_refusal``
    (per IM plan §C.2 / DS Option γ): BG/NBD is already REFUSED on
    Beauty, so G-G short-circuits."""
    pytest.importorskip("lifetimes")
    er = _run_and_load(gg_flag=True, bgnbd_flag=True)
    pm = er.get("predictive_models") or {}
    assert "gamma_gamma" in pm, (
        f"flag-ON: expected predictive_models['gamma_gamma'] populated; "
        f"got keys={list(pm.keys())}. The orchestration block at "
        f"src/main.py T2.5 step did not run."
    )
    card = pm["gamma_gamma"]
    assert isinstance(card, dict)
    assert card.get("model_name") == "gamma_gamma"
    assert card.get("fit_status") == "REFUSED", (
        f"Unexpected fit_status on synthetic Beauty: "
        f"{card.get('fit_status')!r}. Beauty's BG/NBD is REFUSED on "
        f"synthetic data (Pivot 5); G-G must chain-refuse."
    )
    warnings = card.get("fit_warnings") or []
    assert "chained_bgnbd_refusal" in warnings, (
        f"Expected 'chained_bgnbd_refusal' in fit_warnings on synthetic "
        f"Beauty; got {warnings!r}. BG/NBD ModelCard input to "
        f"fit_gamma_gamma was not recognized as REFUSED/INSUFFICIENT_DATA."
    )


def test_both_flags_off_predictive_models_empty():
    """Both flags OFF: neither BG/NBD nor Gamma-Gamma writes to
    ``predictive_models``. Reproduces the pre-S10 shape exactly."""
    er = _run_and_load(gg_flag=False, bgnbd_flag=False)
    pm = er.get("predictive_models")
    assert pm == {} or pm is None, (
        f"Both-flags-off rollback violation: predictive_models={pm!r} "
        f"(expected {{}} or None). Neither orchestration block may run."
    )


def test_gamma_gamma_on_bgnbd_off_handles_missing_bgnbd_card():
    """Edge case: ENGINE_V2_ML_BGNBD=false but ENGINE_V2_ML_GAMMA_GAMMA=true.
    Gamma-Gamma must still produce a ModelCard without crashing — the
    BG/NBD chained input is None, so fit_gamma_gamma falls through its
    own INSUFFICIENT_DATA / fit path. T2.5 must not change G-G
    semantics; this test pins ONLY that the orchestration handles
    ``bgnbd_model_card=None`` cleanly (no exception, ModelCard
    populated on engine_run).
    """
    pytest.importorskip("lifetimes")
    er = _run_and_load(gg_flag=True, bgnbd_flag=False)
    pm = er.get("predictive_models") or {}
    assert "gamma_gamma" in pm, (
        f"flag-ON G-G with BG/NBD-OFF: expected "
        f"predictive_models['gamma_gamma'] populated even when the "
        f"BG/NBD ModelCard input is absent; got keys={list(pm.keys())}."
    )
    assert "bgnbd" not in pm, (
        f"BG/NBD flag OFF but predictive_models['bgnbd'] present: "
        f"{list(pm.keys())!r}."
    )
    card = pm["gamma_gamma"]
    assert isinstance(card, dict)
    assert card.get("model_name") == "gamma_gamma"
    # G-G semantics unchanged: with bgnbd_model_card=None, the
    # chained-refusal short-circuit does NOT fire; G-G falls through to
    # its INSUFFICIENT_DATA gate (or further). Either way the ModelCard
    # must surface cleanly and fit_status is one of the four documented
    # states.
    assert card.get("fit_status") in {
        "VALIDATED",
        "PROVISIONAL",
        "REFUSED",
        "INSUFFICIENT_DATA",
    }, f"fit_status out of vocabulary: {card.get('fit_status')!r}"
