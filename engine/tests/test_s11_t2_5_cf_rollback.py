"""Sprint 11 Ticket T2.5 — Collaborative Filtering (implicit ALS) orchestration rollback contract.

T2.5 atomically flips ``ENGINE_V2_ML_CF`` default ON and wires
``fit_cf`` into ``src/main.py`` orchestration immediately after the
survival PREDICTIVE_FIT block. The rollback contract is: with
``ENGINE_V2_ML_CF=false`` at runtime, the engine reproduces the
pre-T2.5 shape exactly — no CF fit attempted, no parquet written,
``"cf"`` absent from ``engine_run.predictive_models``. BG/NBD,
Gamma-Gamma, and survival may still be present per their own flags.

With the flag ON (T2.5 default), the orchestration step fires and the
CF ModelCard lands on ``engine_run.predictive_models["cf"]``.

**Independence pin (DS-locked, S11 plan review §A.6):** CF is
INDEPENDENT of BG/NBD. The orchestration wire passes NO
``bgnbd_model_card`` argument. CF must produce its own state based on
its own data even when BG/NBD is OFF, and ``chained_bgnbd_refusal``
(survival-only) must NEVER appear in CF's ``fit_warnings``.
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
    cf_flag: bool,
    bgnbd_flag: bool = True,
    gg_flag: bool = True,
    survival_flag: bool = True,
) -> dict:
    env = dict(_BEAUTY_ENV_BASE)
    env["ENGINE_V2_ML_CF"] = "true" if cf_flag else "false"
    env["ENGINE_V2_ML_BGNBD"] = "true" if bgnbd_flag else "false"
    env["ENGINE_V2_ML_GAMMA_GAMMA"] = "true" if gg_flag else "false"
    env["ENGINE_V2_ML_SURVIVAL"] = "true" if survival_flag else "false"
    # S12-T1.5 (2026-05-28): ENGINE_V2_ML_RFM flipped default-ON. The
    # S11-T2.5 CF-only rollback contract explicitly disables the RFM
    # flag here so the per-test assertions (particularly
    # ``predictive_models == {}`` in test_all_flags_off) continue to pin
    # CF's rollback contract specifically. S12-T1.5's own rollback test
    # (``tests/test_s12_t1_5_rfm_rollback.py``) pins RFM's rollback
    # contract independently.
    env["ENGINE_V2_ML_RFM"] = "false"
    # S12-T2.5 (2026-05-28): ENGINE_V2_ML_RETENTION flipped default-ON.
    # The S11-T2.5 CF-only rollback contract explicitly disables the
    # retention flag here so the per-test assertions continue to pin CF's
    # rollback contract specifically. S12-T2.5's own rollback test
    # (``tests/test_s12_t2_5_retention_rollback.py``) pins retention's
    # rollback contract independently.
    env["ENGINE_V2_ML_RETENTION"] = "false"
    # S13-T2.5 (2026-05-29): ENGINE_V2_PLAY_PREDICTED_SEGMENT flipped
    # default-ON. The T2.5 CF-only rollback contract explicitly disables
    # the consumer-wiring flag here so the PlayCard
    # ``predicted_segment`` / ``model_card_ref`` mutation pass does not
    # run alongside this test's CF-specific assertions. S13-T2.5's own
    # rollback test (``tests/test_s13_t2_5_predicted_segment_rollback.py``)
    # pins predicted_segment's rollback contract independently.
    env["ENGINE_V2_PLAY_PREDICTED_SEGMENT"] = "false"
    # S13-T3.5 (2026-05-29): ENGINE_V2_MONTH_2_DELTA flipped default-ON.
    # The T2.5 CF-only rollback contract explicitly disables the
    # month_2_delta detector here so the per-store prior-run lookup +
    # MonthDelta typed-slot population pass does not run alongside this
    # test's CF-specific assertions. S13-T3.5's own rollback test
    # (``tests/test_s13_t3_5_month_2_delta_rollback.py``) pins
    # month_2_delta's rollback contract independently.
    env["ENGINE_V2_MONTH_2_DELTA"] = "false"
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "s11_t2_5"
        result = run_scenario(
            _SCENARIO_NAME,
            out_dir,
            env_overrides=env,
            timeout_sec=600,
        )
        assert result.returncode == 0, (
            f"harness failed rc={result.returncode} cf={cf_flag} "
            f"bg={bgnbd_flag} gg={gg_flag} surv={survival_flag}; "
            f"stderr (last 500): {result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), f"engine_run.json missing at {receipts}"
        return json.loads(receipts.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Case A: rollback — CF OFF, others ON
# ---------------------------------------------------------------------------


def test_flag_off_rollback_cf_absent():
    """Case A — Rollback contract: ENGINE_V2_ML_CF=false reproduces
    pre-T2.5 engine_run.json shape — ``"cf"`` absent from
    ``predictive_models``. BG/NBD, Gamma-Gamma, and survival may still
    be present per their own flags. The CF orchestration block at
    ``src/main.py`` must be a no-op when the CF flag is OFF.
    """
    pytest.importorskip("lifetimes")
    er = _run_and_load(
        cf_flag=False, bgnbd_flag=True, gg_flag=True, survival_flag=True
    )
    pm = er.get("predictive_models") or {}
    assert "cf" not in pm, (
        f"flag-OFF rollback violation: predictive_models['cf'] present "
        f"(keys={list(pm.keys())}). The orchestration block at "
        f"src/main.py must be a no-op when ENGINE_V2_ML_CF=false."
    )


# ---------------------------------------------------------------------------
# Case B: all 4 ML flags ON, CF ModelCard populated on Beauty
# ---------------------------------------------------------------------------


def test_flag_on_populates_cf_on_beauty():
    """Case B — Flag-ON contract: all 4 ML flags ON causes the CF
    orchestration step to fire and write a CF ModelCard to
    ``engine_run.predictive_models["cf"]``. ``fit_status`` MUST be one
    of the documented four-state vocabulary
    {VALIDATED, PROVISIONAL, REFUSED, INSUFFICIENT_DATA}.

    Per S11-T2.5 dispatch (DS T2 review §G): Beauty (~9,400 customers
    on the synthetic fixture) clears INSUFFICIENT floors; recall@10 is
    the open question. The synthetic DGP was built for gap-time
    signal, not co-purchase, so PROVISIONAL or REFUSED is most likely.
    VALIDATED is acceptable IF the math honestly recovers signal
    (surface honestly under Pivot 5).

    This test asserts only the four-state vocabulary and structural
    fields (``recall@10`` present unless INSUFFICIENT_DATA). It does
    NOT pin a specific status — that is observed in this commit and
    reported in the summary file.
    """
    pytest.importorskip("lifetimes")
    pytest.importorskip("implicit")
    er = _run_and_load(
        cf_flag=True, bgnbd_flag=True, gg_flag=True, survival_flag=True
    )
    pm = er.get("predictive_models") or {}
    assert "cf" in pm, (
        f"flag-ON: expected predictive_models['cf'] populated; "
        f"got keys={list(pm.keys())}. The orchestration block at "
        f"src/main.py S11-T2.5 step did not run."
    )
    card = pm["cf"]
    assert isinstance(card, dict)
    assert card.get("model_name") == "cf"
    status = card.get("fit_status")
    assert status in {
        "VALIDATED",
        "PROVISIONAL",
        "REFUSED",
        "INSUFFICIENT_DATA",
    }, f"fit_status out of vocabulary: {status!r}"

    # holdout_top_k_recall and coverage_at_k must be present via the
    # ``metrics`` dict (S13-T0 refactor: per-substrate ModelCard metrics
    # are stored in ``ModelCard.metrics`` and serialize to JSON as a
    # dict; legacy typed Optional fields are read-only ``__getattr__``
    # shims that do NOT appear at the JSON level). When INSUFFICIENT_DATA
    # the keys may be absent or None; otherwise must be numeric.
    assert "metrics" in card, (
        "ModelCard schema missing metrics dict "
        "(S13-T0 authoritative metric storage)"
    )
    if status != "INSUFFICIENT_DATA":
        assert card["metrics"].get("holdout_top_k_recall") is not None, (
            f"fit_status={status!r} but metrics['holdout_top_k_recall'] is "
            "None; non-INSUFFICIENT_DATA states must report a measured "
            "recall."
        )
        # ``coverage_at_k`` is operator-diagnostic; required to be present
        # whenever a fit was attempted (non-INSUFFICIENT_DATA).
        assert "coverage_at_k" in card["metrics"], (
            "ModelCard.metrics missing coverage_at_k diagnostic"
        )


# ---------------------------------------------------------------------------
# Case C: all 4 ML flags OFF — predictive_models empty
# ---------------------------------------------------------------------------


def test_all_flags_off_predictive_models_empty():
    """Case C — All 4 ML flags OFF: no orchestration block writes to
    ``predictive_models``. Reproduces the pre-S10 shape exactly.
    """
    er = _run_and_load(
        cf_flag=False, bgnbd_flag=False, gg_flag=False, survival_flag=False
    )
    pm = er.get("predictive_models")
    assert pm == {} or pm is None, (
        f"All-flags-off rollback violation: predictive_models={pm!r} "
        f"(expected {{}} or None). No orchestration block may run."
    )


# ---------------------------------------------------------------------------
# Case D: INDEPENDENCE PIN — CF on, BG/NBD off; CF must fit independently
# ---------------------------------------------------------------------------


def test_cf_runs_independently_when_bgnbd_off():
    """Case D — INDEPENDENCE PIN (DS-locked S11 plan review §A.6).

    With ``ENGINE_V2_ML_CF=true`` and ``ENGINE_V2_ML_BGNBD=false``,
    CF must still fit independently. The orchestration wire MUST NOT
    pass a ``bgnbd_model_card`` argument to ``fit_cf`` (this contract
    is also pinned at the API surface via
    ``test_fit_cf_signature_does_not_accept_bgnbd_model_card``).

    CF's fit_status must be determined by its own data (not by a
    chained refusal). The survival-only warning ``chained_bgnbd_refusal``
    must NEVER appear in CF's ``fit_warnings`` — that warning belongs
    to ``fit_survival`` only. CF has its own four-state classifier
    based on holdout recall@10.
    """
    pytest.importorskip("implicit")
    er = _run_and_load(
        cf_flag=True, bgnbd_flag=False, gg_flag=False, survival_flag=False
    )
    pm = er.get("predictive_models") or {}
    assert "cf" in pm, (
        f"flag-ON CF with BG/NBD-OFF: expected "
        f"predictive_models['cf'] populated even when BG/NBD is OFF; "
        f"got keys={list(pm.keys())}. CF is INDEPENDENT of BG/NBD — "
        f"the orchestration block must run on the CF flag alone."
    )
    assert "bgnbd" not in pm, (
        f"BG/NBD flag OFF but predictive_models['bgnbd'] present: "
        f"{list(pm.keys())!r}."
    )
    card = pm["cf"]
    assert isinstance(card, dict)
    assert card.get("model_name") == "cf"
    status = card.get("fit_status")
    # INDEPENDENCE PIN: fit_status is determined by CF's own data and
    # gates. It must be one of the four documented states (not a
    # chained-refusal artifact).
    assert status in {
        "VALIDATED",
        "PROVISIONAL",
        "REFUSED",
        "INSUFFICIENT_DATA",
    }, f"fit_status out of vocabulary: {status!r}"

    # CRITICAL INDEPENDENCE ASSERTION: chained_bgnbd_refusal is a
    # survival-only warning. CF MUST NOT emit it under any
    # circumstance — its presence here would indicate someone
    # copy-pasted the survival/G-G chained input pattern into the CF
    # orchestration wire.
    warnings_list = card.get("fit_warnings") or []
    assert "chained_bgnbd_refusal" not in warnings_list, (
        f"INDEPENDENCE VIOLATION: CF's fit_warnings contains "
        f"'chained_bgnbd_refusal' ({warnings_list!r}). CF is "
        f"INDEPENDENT of BG/NBD (DS-locked); this warning is "
        f"survival-only. The orchestration wire at src/main.py "
        f"S11-T2.5 has incorrectly chained CF on BG/NBD."
    )
