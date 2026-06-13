"""Sprint 12 Ticket T1.5 — RFM (Recency × Frequency × Monetary) orchestration rollback contract.

T1.5 atomically flips ``ENGINE_V2_ML_RFM`` default ON and wires
``fit_rfm`` into ``src/main.py`` orchestration immediately after the
CF PREDICTIVE_FIT block. The rollback contract is: with
``ENGINE_V2_ML_RFM=false`` at runtime, the engine reproduces the
pre-T1.5 shape exactly — no RFM fit attempted, no parquet written,
``"rfm"`` absent from ``engine_run.predictive_models``. BG/NBD,
Gamma-Gamma, survival, and CF may still be present per their own flags.

With the flag ON (T1.5 default), the orchestration step fires and the
RFM ModelCard lands on ``engine_run.predictive_models["rfm"]``.

**Independence pin (DS-locked, S12 plan review §F; mirrors CF
S11 plan review §A.6, NOT survival/G-G chained-refusal pattern):** RFM
is INDEPENDENT of BG/NBD. The orchestration wire passes NO
``bgnbd_model_card`` argument. RFM must produce its own state based on
its own data even when BG/NBD is OFF, and ``chained_bgnbd_refusal``
(survival-only) must NEVER appear in RFM's ``fit_warnings``.
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
    rfm_flag: bool,
    bgnbd_flag: bool = True,
    gg_flag: bool = True,
    survival_flag: bool = True,
    cf_flag: bool = True,
) -> dict:
    env = dict(_BEAUTY_ENV_BASE)
    env["ENGINE_V2_ML_RFM"] = "true" if rfm_flag else "false"
    env["ENGINE_V2_ML_BGNBD"] = "true" if bgnbd_flag else "false"
    env["ENGINE_V2_ML_GAMMA_GAMMA"] = "true" if gg_flag else "false"
    env["ENGINE_V2_ML_SURVIVAL"] = "true" if survival_flag else "false"
    env["ENGINE_V2_ML_CF"] = "true" if cf_flag else "false"
    # S12-T2.5 (2026-05-28): ENGINE_V2_ML_RETENTION flipped default-ON.
    # The S12-T1.5 RFM-only rollback contract explicitly disables the
    # retention flag here so the per-test assertions (particularly
    # ``predictive_models == {}`` in test_all_flags_off and the
    # INDEPENDENCE PIN in test_rfm_runs_independently_when_bgnbd_off)
    # continue to pin RFM's rollback contract specifically.
    # S12-T2.5's own rollback test
    # (``tests/test_s12_t2_5_retention_rollback.py``) pins retention's
    # rollback contract independently.
    env["ENGINE_V2_ML_RETENTION"] = "false"
    # S13-T2.5 (2026-05-29): ENGINE_V2_PLAY_PREDICTED_SEGMENT flipped
    # default-ON. The T1.5 RFM-only rollback contract explicitly disables
    # the consumer-wiring flag here so the PlayCard
    # ``predicted_segment`` / ``model_card_ref`` mutation pass does not
    # run alongside this test's RFM-specific assertions. S13-T2.5's own
    # rollback test (``tests/test_s13_t2_5_predicted_segment_rollback.py``)
    # pins predicted_segment's rollback contract independently.
    env["ENGINE_V2_PLAY_PREDICTED_SEGMENT"] = "false"
    # S13-T3.5 (2026-05-29): ENGINE_V2_MONTH_2_DELTA flipped default-ON.
    # The T1.5 RFM-only rollback contract explicitly disables the
    # month_2_delta detector here so the per-store prior-run lookup +
    # MonthDelta typed-slot population pass does not run alongside this
    # test's RFM-specific assertions. S13-T3.5's own rollback test
    # (``tests/test_s13_t3_5_month_2_delta_rollback.py``) pins
    # month_2_delta's rollback contract independently.
    env["ENGINE_V2_MONTH_2_DELTA"] = "false"
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "s12_t1_5"
        result = run_scenario(
            _SCENARIO_NAME,
            out_dir,
            env_overrides=env,
            timeout_sec=600,
        )
        assert result.returncode == 0, (
            f"harness failed rc={result.returncode} rfm={rfm_flag} "
            f"bg={bgnbd_flag} gg={gg_flag} surv={survival_flag} cf={cf_flag}; "
            f"stderr (last 500): {result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), f"engine_run.json missing at {receipts}"
        return json.loads(receipts.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Case A: rollback — RFM OFF, others ON
# ---------------------------------------------------------------------------


def test_flag_off_rollback_rfm_absent():
    """Case A — Rollback contract: ENGINE_V2_ML_RFM=false reproduces
    pre-T1.5 engine_run.json shape — ``"rfm"`` absent from
    ``predictive_models``. BG/NBD, Gamma-Gamma, survival, and CF may
    still be present per their own flags. The RFM orchestration block at
    ``src/main.py`` must be a no-op when the RFM flag is OFF.
    """
    pytest.importorskip("lifetimes")
    er = _run_and_load(
        rfm_flag=False,
        bgnbd_flag=True,
        gg_flag=True,
        survival_flag=True,
        cf_flag=True,
    )
    pm = er.get("predictive_models") or {}
    assert "rfm" not in pm, (
        f"flag-OFF rollback violation: predictive_models['rfm'] present "
        f"(keys={list(pm.keys())}). The orchestration block at "
        f"src/main.py must be a no-op when ENGINE_V2_ML_RFM=false."
    )


# ---------------------------------------------------------------------------
# Case B: all 5 ML flags ON, RFM ModelCard populated on Beauty
# ---------------------------------------------------------------------------


def test_flag_on_populates_rfm_on_beauty():
    """Case B — Flag-ON contract: all 5 ML flags ON causes the RFM
    orchestration step to fire and write an RFM ModelCard to
    ``engine_run.predictive_models["rfm"]``. ``fit_status`` MUST be one
    of the documented four-state vocabulary
    {VALIDATED, PROVISIONAL, REFUSED, INSUFFICIENT_DATA}.

    Per S12-T1.5 dispatch (DS T1 review §I): Beauty (3,844 repeat
    customers on the synthetic fixture, well above MATURE 500 floor) is
    expected to VALIDATE — Pivot-5-consistent structural correctness of
    deterministic segmentation, NOT predictive overfit. RFM is the
    first sprint where synthetic fixtures may legitimately VALIDATE.

    This test asserts the four-state vocabulary and the additive
    internal-consistency fields (segment_monotonicity_spearman +
    quintile_coverage_min). It does NOT pin a specific status — that is
    observed in this commit and reported in the summary file.
    """
    pytest.importorskip("lifetimes")
    er = _run_and_load(
        rfm_flag=True,
        bgnbd_flag=True,
        gg_flag=True,
        survival_flag=True,
        cf_flag=True,
    )
    pm = er.get("predictive_models") or {}
    assert "rfm" in pm, (
        f"flag-ON: expected predictive_models['rfm'] populated; "
        f"got keys={list(pm.keys())}. The orchestration block at "
        f"src/main.py S12-T1.5 step did not run."
    )
    card = pm["rfm"]
    assert isinstance(card, dict)
    assert card.get("model_name") == "rfm"
    status = card.get("fit_status")
    assert status in {
        "VALIDATED",
        "PROVISIONAL",
        "REFUSED",
        "INSUFFICIENT_DATA",
    }, f"fit_status out of vocabulary: {status!r}"

    # segment_monotonicity_spearman + quintile_coverage_min must be
    # present via the ``metrics`` dict (S13-T0 refactor: per-substrate
    # ModelCard metrics are stored in ``ModelCard.metrics`` and serialize
    # to JSON as a dict; legacy typed Optional fields are read-only
    # ``__getattr__`` shims that do NOT appear at the JSON level). When
    # INSUFFICIENT_DATA / REFUSED they may be absent or None; otherwise
    # must be numeric.
    assert "metrics" in card, (
        "ModelCard schema missing metrics dict "
        "(S13-T0 authoritative metric storage)"
    )
    if status not in {"INSUFFICIENT_DATA", "REFUSED"}:
        assert card["metrics"].get("segment_monotonicity_spearman") is not None, (
            f"fit_status={status!r} but metrics['segment_monotonicity_spearman'] "
            f"is None; non-INSUFFICIENT_DATA/REFUSED states must report a "
            f"measured Spearman."
        )
        assert card["metrics"].get("quintile_coverage_min") is not None, (
            f"fit_status={status!r} but metrics['quintile_coverage_min'] is None."
        )


# ---------------------------------------------------------------------------
# Case C: all 5 ML flags OFF — predictive_models empty
# ---------------------------------------------------------------------------


def test_all_flags_off_predictive_models_empty():
    """Case C — All 5 ML flags OFF: no orchestration block writes to
    ``predictive_models``. Reproduces the pre-S10 shape exactly.
    """
    er = _run_and_load(
        rfm_flag=False,
        bgnbd_flag=False,
        gg_flag=False,
        survival_flag=False,
        cf_flag=False,
    )
    pm = er.get("predictive_models")
    assert pm == {} or pm is None, (
        f"All-flags-off rollback violation: predictive_models={pm!r} "
        f"(expected {{}} or None). No orchestration block may run."
    )


# ---------------------------------------------------------------------------
# Case D: INDEPENDENCE PIN — RFM on, BG/NBD off; RFM must fit independently
# ---------------------------------------------------------------------------


def test_rfm_runs_independently_when_bgnbd_off():
    """Case D — INDEPENDENCE PIN (DS-locked S12 plan review §F).

    With ``ENGINE_V2_ML_RFM=true`` and ``ENGINE_V2_ML_BGNBD=false``,
    RFM must still fit independently. The orchestration wire MUST NOT
    pass a ``bgnbd_model_card`` argument to ``fit_rfm`` (this contract
    is also pinned at the API surface via
    ``test_fit_rfm_signature_does_not_accept_bgnbd_model_card``).

    RFM's fit_status must be determined by its own data (not by a
    chained refusal). The survival-only warning ``chained_bgnbd_refusal``
    must NEVER appear in RFM's ``fit_warnings`` — that warning belongs
    to ``fit_survival`` only. RFM has its own four-state classifier
    based on internal-consistency metrics
    (segment_monotonicity_spearman + quintile_coverage_min).

    This is the LOAD-BEARING NEGATIVE ASSERTION pinning the
    INDEPENDENT (CF-style) orchestration wire shape and forbidding any
    accidental copy-paste of the survival/G-G chained-refusal pattern.
    """
    er = _run_and_load(
        rfm_flag=True,
        bgnbd_flag=False,
        gg_flag=False,
        survival_flag=False,
        cf_flag=False,
    )
    pm = er.get("predictive_models") or {}
    assert "rfm" in pm, (
        f"flag-ON RFM with BG/NBD-OFF: expected "
        f"predictive_models['rfm'] populated even when BG/NBD is OFF; "
        f"got keys={list(pm.keys())}. RFM is INDEPENDENT of BG/NBD — "
        f"the orchestration block must run on the RFM flag alone."
    )
    assert "bgnbd" not in pm, (
        f"BG/NBD flag OFF but predictive_models['bgnbd'] present: "
        f"{list(pm.keys())!r}."
    )
    card = pm["rfm"]
    assert isinstance(card, dict)
    assert card.get("model_name") == "rfm"
    status = card.get("fit_status")
    # INDEPENDENCE PIN: fit_status is determined by RFM's own data and
    # gates. It must be one of the four documented states (not a
    # chained-refusal artifact).
    assert status in {
        "VALIDATED",
        "PROVISIONAL",
        "REFUSED",
        "INSUFFICIENT_DATA",
    }, f"fit_status out of vocabulary: {status!r}"

    # CRITICAL INDEPENDENCE ASSERTION: chained_bgnbd_refusal is a
    # survival-only warning. RFM MUST NOT emit it under any
    # circumstance — its presence here would indicate someone
    # copy-pasted the survival/G-G chained input pattern into the RFM
    # orchestration wire.
    warnings_list = card.get("fit_warnings") or []
    assert "chained_bgnbd_refusal" not in warnings_list, (
        f"INDEPENDENCE VIOLATION: RFM's fit_warnings contains "
        f"'chained_bgnbd_refusal' ({warnings_list!r}). RFM is "
        f"INDEPENDENT of BG/NBD (DS-locked); this warning is "
        f"survival-only. The orchestration wire at src/main.py "
        f"S12-T1.5 has incorrectly chained RFM on BG/NBD."
    )
