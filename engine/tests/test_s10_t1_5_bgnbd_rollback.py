"""Sprint 10 Ticket T1.5 — BG/NBD orchestration rollback contract.

T1.5 atomically flips ``ENGINE_V2_ML_BGNBD`` default ON and wires
``fit_bgnbd`` into ``src/main.py`` orchestration. The rollback contract
is: with ``ENGINE_V2_ML_BGNBD=false`` at runtime, the engine reproduces
the pre-T1.5 shape exactly — no fit attempted, no parquet written,
``engine_run.predictive_models == {}``.

With the flag ON (T1.5 default), the orchestration step fires and the
ModelCard for BG/NBD lands on ``engine_run.predictive_models["bgnbd"]``.
On the synthetic pinned fixtures the resulting ``fit_status`` is
expected to be REFUSED or INSUFFICIENT_DATA per Pivot 5 / Option γ
(synthetic fixtures lack latent-rate heterogeneity by construction).
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


def _run_and_load(ml_flag: bool) -> dict:
    env = dict(_BEAUTY_ENV_BASE)
    env["ENGINE_V2_ML_BGNBD"] = "true" if ml_flag else "false"
    # T2.5 (2026-05-26): ENGINE_V2_ML_GAMMA_GAMMA flipped default-ON.
    # The T1.5 rollback contract (BG/NBD-only) explicitly disables the
    # G-G flag here so the assertion on
    # ``predictive_models == {}`` continues to pin BG/NBD's rollback
    # contract specifically. T2.5's own rollback test
    # (``tests/test_s10_t2_5_gamma_gamma_rollback.py``) pins the G-G
    # rollback contract independently.
    env["ENGINE_V2_ML_GAMMA_GAMMA"] = "false"
    # S11-T1.5 (2026-05-26): ENGINE_V2_ML_SURVIVAL flipped default-ON.
    # The T1.5 BG/NBD-only rollback contract explicitly disables the
    # survival flag here so the assertion on ``predictive_models == {}``
    # continues to pin BG/NBD's rollback contract specifically. S11-T1.5's
    # own rollback test (``tests/test_s11_t1_5_survival_rollback.py``)
    # pins the survival rollback contract independently.
    env["ENGINE_V2_ML_SURVIVAL"] = "false"
    # S11-T2.5 (2026-05-28): ENGINE_V2_ML_CF flipped default-ON. The
    # T1.5 BG/NBD-only rollback contract explicitly disables the CF
    # flag here so the assertion on ``predictive_models == {}``
    # continues to pin BG/NBD's rollback contract specifically.
    # S11-T2.5's own rollback test
    # (``tests/test_s11_t2_5_cf_rollback.py``) pins CF's rollback
    # contract independently.
    env["ENGINE_V2_ML_CF"] = "false"
    # S12-T1.5 (2026-05-28): ENGINE_V2_ML_RFM flipped default-ON. The
    # T1.5 BG/NBD-only rollback contract explicitly disables the RFM
    # flag here so the assertion on ``predictive_models == {}``
    # continues to pin BG/NBD's rollback contract specifically.
    # S12-T1.5's own rollback test
    # (``tests/test_s12_t1_5_rfm_rollback.py``) pins RFM's rollback
    # contract independently.
    env["ENGINE_V2_ML_RFM"] = "false"
    # S12-T2.5 (2026-05-28): ENGINE_V2_ML_RETENTION flipped default-ON.
    # The T1.5 BG/NBD-only rollback contract explicitly disables the
    # retention flag here so the assertion on
    # ``predictive_models == {}`` (and ``cohort_diagnostics == {}``)
    # continues to pin BG/NBD's rollback contract specifically.
    # S12-T2.5's own rollback test
    # (``tests/test_s12_t2_5_retention_rollback.py``) pins retention's
    # rollback contract independently.
    env["ENGINE_V2_ML_RETENTION"] = "false"
    # S13-T2.5 (2026-05-29): ENGINE_V2_PLAY_PREDICTED_SEGMENT flipped
    # default-ON. The T1.5 BG/NBD-only rollback contract explicitly
    # disables the consumer-wiring flag here so the PlayCard
    # ``predicted_segment`` / ``model_card_ref`` mutation pass does not
    # run alongside this test's BG/NBD-specific assertions. S13-T2.5's
    # own rollback test (``tests/test_s13_t2_5_predicted_segment_rollback.py``)
    # pins predicted_segment's rollback contract independently.
    env["ENGINE_V2_PLAY_PREDICTED_SEGMENT"] = "false"
    # S13-T3.5 (2026-05-29): ENGINE_V2_MONTH_2_DELTA flipped default-ON.
    # The T1.5 BG/NBD-only rollback contract explicitly disables the
    # month_2_delta detector here so the per-store prior-run lookup +
    # MonthDelta typed-slot population pass does not run alongside this
    # test's BG/NBD-specific assertions. S13-T3.5's own rollback test
    # (``tests/test_s13_t3_5_month_2_delta_rollback.py``) pins
    # month_2_delta's rollback contract independently.
    env["ENGINE_V2_MONTH_2_DELTA"] = "false"
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "t1_5"
        result = run_scenario(
            _SCENARIO_NAME,
            out_dir,
            env_overrides=env,
            timeout_sec=600,
        )
        assert result.returncode == 0, (
            f"harness failed rc={result.returncode} ml_flag={ml_flag}; "
            f"stderr (last 500): {result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), f"engine_run.json missing at {receipts}"
        return json.loads(receipts.read_text(encoding="utf-8"))


def test_flag_off_rollback_predictive_models_empty():
    """Rollback contract: ENGINE_V2_ML_BGNBD=false reproduces pre-T1.5
    engine_run.json shape — predictive_models is the empty dict and no
    BG/NBD code path ran in orchestration."""
    er = _run_and_load(ml_flag=False)
    pm = er.get("predictive_models")
    assert pm == {} or pm is None, (
        f"flag-OFF rollback violation: predictive_models={pm!r} "
        f"(expected {{}} or None). The orchestration PREDICTIVE_FIT "
        f"block at src/main.py must be a no-op when "
        f"ENGINE_V2_ML_BGNBD=false."
    )


def test_flag_on_populates_predictive_models_bgnbd():
    """Flag-ON contract: ENGINE_V2_ML_BGNBD=true causes the
    orchestration step to fire and write a BG/NBD ModelCard to
    engine_run.predictive_models["bgnbd"]. On synthetic Beauty the
    expected fit_status is REFUSED (Option γ, Pivot 5)."""
    pytest.importorskip("lifetimes")
    er = _run_and_load(ml_flag=True)
    pm = er.get("predictive_models") or {}
    assert "bgnbd" in pm, (
        f"flag-ON: expected predictive_models['bgnbd'] populated; "
        f"got keys={list(pm.keys())}. The orchestration block at "
        f"src/main.py PREDICTIVE_FIT step did not run."
    )
    card = pm["bgnbd"]
    # Defensive shape: ModelCard serializes as a dict with these keys.
    assert isinstance(card, dict)
    assert card.get("model_name") == "bgnbd"
    assert "fit_status" in card
    # Pivot 5 + Option γ: synthetic Beauty cannot land VALIDATED.
    assert card["fit_status"] in {"REFUSED", "INSUFFICIENT_DATA"}, (
        f"Unexpected fit_status on synthetic Beauty: "
        f"{card['fit_status']!r}. Synthetic fixtures lack latent-rate "
        f"heterogeneity (Pivot 5 / DS Option γ 2026-05-26) — "
        f"VALIDATED on synthetic data would indicate the metric "
        f"regressed back to MAPE or the fixture was reshaped."
    )
