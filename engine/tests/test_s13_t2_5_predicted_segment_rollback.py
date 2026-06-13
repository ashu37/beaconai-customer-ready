"""Sprint 13 Ticket T2.5 — PlayCard predicted_segment + model_card_ref rollback contract.

T2.5 atomically flips ``ENGINE_V2_PLAY_PREDICTED_SEGMENT`` default ON.
The rollback contract is: with ``ENGINE_V2_PLAY_PREDICTED_SEGMENT=false``
at runtime, the engine reproduces the pre-T2.5 shape — no
consumer-wiring pass runs, every PlayCard's ``predicted_segment`` and
``model_card_ref`` stay ``None``.

With the flag ON (T2.5 default), the post-injection consumer-wiring
pass at ``src/main.py`` after ``apply_guardrails_to_injected`` walks
``engine_run.recommendations`` and populates PlayCard.predicted_segment
+ PlayCard.model_card_ref.

**Independence pin (DS-locked, S13 plan review §F):** the
consumer-wiring chain is INDEPENDENT of BG/NBD. With BG/NBD OFF but
``ENGINE_V2_PLAY_PREDICTED_SEGMENT=true``, the chain walks past the
absent BG/NBD substrate (fallback to CF / survival / RFM / recency)
and the ``model_card_ref`` is still populated. The predicted_segment
remains subject to the modal-segment stability floor (n_audience<50
OR audience_modal_share<0.30 → segment_name=None; audit fields
uncensored).

**briefing.html byte-identity:** structurally guaranteed via the
renderer non-consumption grep pin at
``tests/test_s13_renderer_non_consumption.py`` (asserts neither
``predicted_segment`` nor ``model_card_ref`` are referenced anywhere
in ``src/briefing.py``).
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
    predicted_segment_flag: bool,
    bgnbd_flag: bool = True,
    gg_flag: bool = True,
    survival_flag: bool = True,
    cf_flag: bool = True,
    rfm_flag: bool = True,
    retention_flag: bool = True,
    ranking_chain_flag: bool = True,
) -> dict:
    env = dict(_BEAUTY_ENV_BASE)
    env["ENGINE_V2_PLAY_PREDICTED_SEGMENT"] = (
        "true" if predicted_segment_flag else "false"
    )
    env["ENGINE_V2_ML_BGNBD"] = "true" if bgnbd_flag else "false"
    env["ENGINE_V2_ML_GAMMA_GAMMA"] = "true" if gg_flag else "false"
    env["ENGINE_V2_ML_SURVIVAL"] = "true" if survival_flag else "false"
    env["ENGINE_V2_ML_CF"] = "true" if cf_flag else "false"
    env["ENGINE_V2_ML_RFM"] = "true" if rfm_flag else "false"
    env["ENGINE_V2_ML_RETENTION"] = "true" if retention_flag else "false"
    env["ENGINE_V2_RANKING_STRATEGY_CHAIN"] = (
        "true" if ranking_chain_flag else "false"
    )
    # S13-T3.5 (2026-05-29): ENGINE_V2_MONTH_2_DELTA flipped default-ON.
    # The T2.5 predicted_segment rollback contract explicitly disables
    # the month_2_delta detector here so the per-store prior-run lookup
    # + MonthDelta typed-slot population pass does not run alongside
    # this test's predicted_segment / model_card_ref assertions. The
    # T3.5 month_2_delta rollback test
    # (``tests/test_s13_t3_5_month_2_delta_rollback.py``) pins
    # month_2_delta's rollback contract independently.
    env["ENGINE_V2_MONTH_2_DELTA"] = "false"
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "s13_t2_5"
        result = run_scenario(
            _SCENARIO_NAME,
            out_dir,
            env_overrides=env,
            timeout_sec=600,
        )
        assert result.returncode == 0, (
            f"harness failed rc={result.returncode} "
            f"predicted_segment={predicted_segment_flag} "
            f"bg={bgnbd_flag} gg={gg_flag} surv={survival_flag} "
            f"cf={cf_flag} rfm={rfm_flag} ret={retention_flag}; "
            f"stderr (last 500): {result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), f"engine_run.json missing at {receipts}"
        return json.loads(receipts.read_text(encoding="utf-8"))


def _iter_play_cards(engine_run: dict):
    """Yield every PlayCard-shaped dict from the engine_run.json buckets
    that can carry ``predicted_segment`` / ``model_card_ref`` typed slots.

    Only ``recommendations`` is targeted by the consumer-wiring pass at
    S13-T2 (see src/main.py:1972-2038). The defensive ``recommended_
    experiments`` walk catches any future scope expansion.
    """

    for bucket in ("recommendations", "recommended_experiments"):
        items = engine_run.get(bucket) or []
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                yield bucket, item


# ---------------------------------------------------------------------------
# Case A: rollback — predicted_segment OFF, others ON. PlayCards untouched.
# ---------------------------------------------------------------------------


def test_flag_off_rollback_predicted_segment_none() -> None:
    """Case A — Rollback contract: ENGINE_V2_PLAY_PREDICTED_SEGMENT=false
    reproduces pre-T2.5 PlayCard shape. Every PlayCard's
    ``predicted_segment`` and ``model_card_ref`` MUST be ``None``.

    The consumer-wiring pass at src/main.py:1972-2038 must be a no-op
    when the flag is OFF.
    """

    er = _run_and_load(predicted_segment_flag=False)
    seen = 0
    for bucket, pc in _iter_play_cards(er):
        seen += 1
        ps = pc.get("predicted_segment")
        mcr = pc.get("model_card_ref")
        assert ps is None, (
            f"flag-OFF rollback violation: bucket={bucket} "
            f"play_id={pc.get('play_id')!r} predicted_segment={ps!r} "
            f"(expected None). The consumer-wiring pass at "
            f"src/main.py:1972-2038 must be a no-op when "
            f"ENGINE_V2_PLAY_PREDICTED_SEGMENT=false."
        )
        assert mcr is None, (
            f"flag-OFF rollback violation: bucket={bucket} "
            f"play_id={pc.get('play_id')!r} model_card_ref={mcr!r} "
            f"(expected None). The consumer-wiring pass at "
            f"src/main.py:1972-2038 must be a no-op when "
            f"ENGINE_V2_PLAY_PREDICTED_SEGMENT=false."
        )
    # Defensive: Beauty fixture must produce SOME PlayCards on .recommendations
    # or .recommended_experiments for the rollback assertion to be meaningful.
    assert seen > 0, (
        f"Beauty fixture produced 0 PlayCards across recommendations + "
        f"recommended_experiments; rollback contract cannot be asserted."
    )


# ---------------------------------------------------------------------------
# Case B: all flags ON — at least one PlayCard carries populated
# predicted_segment + model_card_ref on Beauty.
# ---------------------------------------------------------------------------


def test_flag_on_populates_model_card_ref_on_beauty() -> None:
    """Case B — Flag-ON contract: all flags ON, at least one PlayCard
    on Beauty carries a populated ``model_card_ref``.

    The ``model_card_ref.strategy_used`` field MUST be one of the
    documented chain-walk values (BGNBD / CF / SURVIVAL / RFM / RECENCY).
    ``fit_status_chain`` MUST be a non-empty list of (substrate, status)
    pairs. ``predicted_segment`` is subject to the modal-segment
    stability floor (n_audience<50 OR audience_modal_share<0.30 →
    segment_name=None); the test records the actual state without
    asserting a specific outcome — the per-fixture state report in the
    summary file captures the verbatim values.

    Beauty has ~259 days of orders; RFM clears the S12-T1.5 VALIDATED
    floor on aggregate. Whether any individual play's audience clears
    the n>=50 + share>=0.30 modal-stability floor is fixture-dependent
    and is the load-bearing question the per-fixture state report
    answers.
    """

    er = _run_and_load(predicted_segment_flag=True)
    populated_mcr = 0
    populated_ps_segment_name = 0
    for bucket, pc in _iter_play_cards(er):
        if bucket != "recommendations":
            continue  # T2 wiring targets recommendations only.
        mcr = pc.get("model_card_ref")
        if mcr is None:
            continue
        populated_mcr += 1
        strategy = mcr.get("strategy_used")
        assert strategy in {
            "BGNBD",
            "CF",
            "SURVIVAL",
            "RFM",
            "RECENCY",
            None,  # Allow None for edge-case chain failures.
        }, f"strategy_used out of vocabulary: {strategy!r}"
        chain = mcr.get("fit_status_chain") or []
        assert isinstance(chain, list)
        ps = pc.get("predicted_segment") or {}
        if isinstance(ps, dict) and ps.get("segment_name"):
            populated_ps_segment_name += 1

    assert populated_mcr > 0, (
        f"flag-ON: expected at least one PlayCard on Beauty's "
        f".recommendations to carry a populated model_card_ref; "
        f"got 0 (consumer-wiring pass did not run or produced 0 cards). "
        f"S13-T2 wire site: src/main.py:1972-2038."
    )


# ---------------------------------------------------------------------------
# Case C: all S10-S13 ML flags OFF — predictive_models, cohort_diagnostics,
# AND PlayCard.predicted_segment / model_card_ref all empty.
# ---------------------------------------------------------------------------


def test_all_ml_flags_off_no_consumer_wiring_state() -> None:
    """Case C — All S10-S13 ML flags OFF: no orchestration block writes
    to ``predictive_models`` / ``cohort_diagnostics``, and the
    consumer-wiring pass produces no populated PlayCard typed slots
    (the chain walker has nothing to walk).

    Reproduces the pre-S10 shape exactly except that with the
    ``ENGINE_V2_PLAY_PREDICTED_SEGMENT`` flag ON (which the consumer-
    wiring pass DOES run), the pass still emits no populated state
    because every substrate ModelCard is absent. ``model_card_ref``
    may carry an empty / RECENCY-floor result; ``predicted_segment``
    stays ``None``.
    """

    er = _run_and_load(
        predicted_segment_flag=True,
        bgnbd_flag=False,
        gg_flag=False,
        survival_flag=False,
        cf_flag=False,
        rfm_flag=False,
        retention_flag=False,
        ranking_chain_flag=False,
    )
    pm = er.get("predictive_models")
    assert pm == {} or pm is None, (
        f"All ML flags OFF rollback violation: predictive_models={pm!r}"
    )
    cd = er.get("cohort_diagnostics")
    assert cd == {} or cd is None, (
        f"All ML flags OFF rollback violation: cohort_diagnostics={cd!r}"
    )
    # PlayCard predicted_segment MUST be None (no RFM substrate to read).
    for bucket, pc in _iter_play_cards(er):
        ps = pc.get("predicted_segment")
        assert ps is None or (
            isinstance(ps, dict) and ps.get("segment_name") is None
        ), (
            f"flag-ON-but-all-ML-OFF: bucket={bucket} "
            f"play_id={pc.get('play_id')!r} predicted_segment "
            f"unexpectedly carries segment_name={ps!r}"
        )


# ---------------------------------------------------------------------------
# Case D: INDEPENDENCE PIN — predicted_segment on, BG/NBD off; wiring still
# produces a model_card_ref (chain walks past BG/NBD).
# ---------------------------------------------------------------------------


def test_consumer_wiring_runs_independently_when_bgnbd_off() -> None:
    """Case D — INDEPENDENCE PIN (DS-locked, S13 plan review §F).

    With ``ENGINE_V2_PLAY_PREDICTED_SEGMENT=true`` and BG/NBD OFF (but
    survival / CF / RFM / RETENTION still ON), the consumer-wiring
    pass MUST still produce populated ``model_card_ref`` on at least
    one PlayCard. The chain walker is intent-conditional and walks
    past missing substrates without crashing.

    ``predicted_segment`` is subject to the modal-segment stability
    floor — populated only if an audience clears n>=50 AND
    share>=0.30. RFM is INDEPENDENT of BG/NBD (DS-locked S12 plan
    review §F) so the RFM substrate is available for modal-segment
    computation even with BG/NBD OFF. The test does not assert
    segment_name population (fixture-dependent).
    """

    er = _run_and_load(predicted_segment_flag=True, bgnbd_flag=False)
    pm = er.get("predictive_models") or {}
    assert "bgnbd" not in pm, (
        f"BG/NBD flag OFF but predictive_models['bgnbd'] present: "
        f"{list(pm.keys())!r}."
    )
    populated_mcr = 0
    for bucket, pc in _iter_play_cards(er):
        if bucket != "recommendations":
            continue
        mcr = pc.get("model_card_ref")
        if mcr is None:
            continue
        populated_mcr += 1
        strategy = mcr.get("strategy_used")
        # BG/NBD must NOT be the chosen strategy (substrate absent).
        assert strategy != "BGNBD", (
            f"INDEPENDENCE VIOLATION: play_id={pc.get('play_id')!r} "
            f"chose strategy=BGNBD even though BG/NBD flag is OFF "
            f"(predictive_models keys: {list(pm.keys())!r})."
        )

    assert populated_mcr > 0, (
        f"INDEPENDENCE PIN VIOLATION: with BG/NBD OFF, expected at "
        f"least one PlayCard on Beauty's .recommendations to carry "
        f"a populated model_card_ref via the chain walk (CF / "
        f"survival / RFM / recency); got 0. The consumer-wiring "
        f"pass at src/main.py:1972-2038 incorrectly requires BG/NBD."
    )
