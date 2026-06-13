"""Sprint 13 Ticket T2 — runtime invariant: ML-fit never demotes.

**Q-S13-4 LOCK (DS verdict 2026-05-28, S13 plan review §B):**

> ML-fit ReasonCodes (``MODEL_FIT_INSUFFICIENT_DATA``, ``MODEL_FIT_REFUSED``)
> emit ONLY on ``PlayCard.model_card_ref.fit_warnings`` per PlayCard.
> **NEVER on ``RejectedPlay.reason_code``. Ever.**

Reasoning (DS verbatim):
- If a card stays in Recommended/Experiment (which ML-fit MUST always
  allow per "ML-fit never demotes between slate roles"), there is no
  ``RejectedPlay`` to attach to. The audit story belongs with the
  consumed strategy on ``model_card_ref``.

This test complements the AST contract pin at
``tests/test_reason_code_precedence_invariant.py::test_model_fit_codes_not_emitted_in_s10_close``
with the *runtime* contract pin: actually run the engine on the 5
pinned fixtures with ``ENGINE_V2_PLAY_PREDICTED_SEGMENT=true`` (T2
consumer-wiring ON), then walk the produced ``engine_run.json`` and
assert no ML-fit ``ReasonCode`` value appears on any ``RejectedPlay``
across ``engine_run.considered`` or any other slate bucket.

S13-T2 scope note
=================

At T2 the new synthetic month-2 fixture has NOT yet landed (T3
introduces it). This test covers the 5 currently-pinned fixtures only;
the month-2 fixture is added at T3.5 per IM plan §D-T3.5.

Pinned fixtures covered:

1. ``healthy_beauty_240d`` — primary Beauty pinned slate (B6 contract).
2. ``healthy_supplements_240d`` — Supplements pinned slate.
3. ``small_store_240d`` — small-merchant fixture (the only one that
   currently VALIDATES RFM).
4. ``cold_start_45d`` — cold-start posture; expected ML refusals.
5. ``healthy_beauty_low_inventory_240d`` — inventory-edge variant.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Iterable

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.synthetic_harness import run_scenario  # noqa: E402


# The two forbidden ReasonCode string values per Q-S13-4 LOCK. These
# are the lowercase enum-value strings (matching
# :data:`src.engine_run.ReasonCode.MODEL_FIT_INSUFFICIENT_DATA.value`
# and ``MODEL_FIT_REFUSED.value``), NOT the uppercase fit_warnings
# grammar prefixes (those are allowed inside ``fit_warnings`` lists).
_FORBIDDEN_REASON_CODES = frozenset(
    {
        "model_fit_insufficient_data",
        "model_fit_refused",
    }
)

_PINNED_FIXTURES = (
    "healthy_beauty_240d",
    "healthy_supplements_240d",
    "small_store_240d",
    "cold_start_45d",
    "healthy_beauty_low_inventory_240d",
)

_BASE_ENV: dict[str, str] = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "WINDOW_POLICY": "auto",
    # S13-T2: turn the consumer-wiring flag ON so the new
    # populate_play_card_consumers pass runs (the failure mode under
    # test is that a future regression starts emitting MODEL_FIT_*
    # codes onto RejectedPlay.reason_code from any callsite — the
    # contract MUST hold whether the wiring pass runs or not).
    "ENGINE_V2_PLAY_PREDICTED_SEGMENT": "true",
}


def _scenario_env(scenario: str) -> dict[str, str]:
    env = dict(_BASE_ENV)
    if scenario.startswith("healthy_supplements"):
        env["VERTICAL_MODE"] = "supplements"
    elif scenario.startswith("healthy_beauty") or scenario.startswith(
        "winback_activation_beauty"
    ):
        env["VERTICAL_MODE"] = "beauty"
    # Other fixtures: rely on the scenario YAML's category.
    return env


def _iter_reason_codes(engine_run: dict) -> Iterable[tuple[str, str, str]]:
    """Yield ``(bucket, play_id, reason_code_value)`` for every rejected play.

    Walks the standard buckets that can carry ``RejectedPlay`` records:

    - ``engine_run["considered"]`` — primary RejectedPlay bucket.
    - ``engine_run["watching"]`` — Watching cards are NOT RejectedPlay
      records (they live elsewhere on the schema). Defensive guard: if
      any future schema places ``reason_code`` on a card in
      ``recommendations``, this walk catches it too.
    """

    for bucket in ("considered", "watching", "recommendations"):
        items = engine_run.get(bucket) or []
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            rc = item.get("reason_code")
            if isinstance(rc, str) and rc:
                yield bucket, str(item.get("play_id", "")), rc


@pytest.mark.parametrize("scenario", _PINNED_FIXTURES)
def test_ml_fit_codes_never_appear_on_rejected_play(scenario: str) -> None:
    """Q-S13-4 LOCK runtime pin: no MODEL_FIT_* on RejectedPlay.reason_code.

    Run the engine on each pinned fixture with the T2 consumer-wiring
    flag ON; load ``engine_run.json``; walk every RejectedPlay-bearing
    bucket; assert no ``reason_code`` string equals one of the two
    forbidden lowercase enum-value strings.
    """

    env = _scenario_env(scenario)
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "s13_t2_ml_fit_never_demotes"
        result = run_scenario(
            scenario,
            out_dir,
            env_overrides=env,
            timeout_sec=600,
        )
        assert result.returncode == 0, (
            f"synthetic harness for {scenario!r} failed (rc={result.returncode}). "
            f"stderr (last 500 chars): {result.stderr[-500:]}"
        )
        receipts = out_dir / "receipts" / "engine_run.json"
        assert receipts.exists(), f"engine_run.json missing at {receipts}"
        engine_run = json.loads(receipts.read_text(encoding="utf-8"))

    offenders = [
        (bucket, play_id, code)
        for bucket, play_id, code in _iter_reason_codes(engine_run)
        if code in _FORBIDDEN_REASON_CODES
    ]
    assert not offenders, (
        "Q-S13-4 LOCK violation on fixture "
        f"{scenario!r}: MODEL_FIT_* ReasonCodes must NEVER appear on "
        "RejectedPlay.reason_code (audit surface is "
        "PlayCard.model_card_ref.fit_warnings). Offenders: "
        f"{offenders}"
    )


_MONTH_2_FIXTURE_STORE_ID = "ml_fit_never_demotes_month_2_synthetic"


def _month_1_run_with_refused_substrates() -> dict:
    """Construct a month-1 engine_run dict with all ML substrates REFUSED.

    This is the "stale" prior run the month-2 detector will read. Per
    Q-S13-4 LOCK, even though substrates were REFUSED last month, no
    MODEL_FIT_* ReasonCode appears on any RejectedPlay across either
    month-1 or month-2 — the audit story belongs on
    PlayCard.model_card_ref.fit_warnings, not on
    RejectedPlay.reason_code.
    """

    return {
        "run_id": "ml_fit_never_demotes_month_1",
        "store_id": _MONTH_2_FIXTURE_STORE_ID,
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
        # Honest report: zero RejectedPlay entries carrying MODEL_FIT_*
        # codes (the Q-S13-4 LOCK contract that this test pins).
        "considered": [],
        "watching": [],
        "recommendations": [],
    }


def _month_2_engine_run_with_validated_substrates():
    """Construct a month-2 ``EngineRun`` with all substrates VALIDATED.

    Mirrors the "merchant onboarded more orders; refit cleared the
    validation floor" scenario the DS §F month-2 fixture targets.
    """

    from src.engine_run import EngineRun

    er = EngineRun(
        run_id="ml_fit_never_demotes_month_2",
        store_id=_MONTH_2_FIXTURE_STORE_ID,
        anchor_date="2025-01-30T00:00:00",
        predictive_models={
            "bgnbd": {"fit_status": "VALIDATED"},
            "gamma_gamma": {"fit_status": "VALIDATED"},
            "survival": {"fit_status": "VALIDATED"},
            "cf": {"fit_status": "VALIDATED"},
            "rfm": {
                "fit_status": "VALIDATED",
                "segment_by_customer": {"cust_001": "Champions"},
            },
        },
        cohort_diagnostics={
            "retention": {
                "fit_status": "VALIDATED",
                "bootstrap_ci_width_at_month_3": 0.14,
            },
        },
    )
    er.briefing_meta.audience_definition_version = 1
    return er


def test_ml_fit_codes_never_appear_on_rejected_play_across_month_2_sequence() -> None:
    """Q-S13-4 LOCK runtime pin extended to month-2 (DS S13 §F REQUIRED).

    Construct a 2-run synthetic sequence:

    - **Month-1:** all 6 ML substrates REFUSED (cold-start posture).
    - **Month-2:** all 6 ML substrates VALIDATED (refit cleared the
      floor after 30 more days of orders).

    Run the month_2_delta detector on the pair; assert that NEITHER
    engine_run's ``considered`` / ``watching`` / ``recommendations``
    buckets carry any ``reason_code`` equal to ``MODEL_FIT_*``. The
    Q-S13-4 LOCK contract holds across the month-2 dimension:

    > ML-fit ReasonCodes emit ONLY on
    > ``PlayCard.model_card_ref.fit_warnings``. NEVER on
    > ``RejectedPlay.reason_code``. Ever.

    The detector itself MUST NOT inject MODEL_FIT_* into either
    engine_run during the substrate-state-delta computation. The
    substrate-fit-status changes surface on
    ``EngineRun.month_2_delta.substrate_fit_status_changes`` (typed
    audit field) — NOT on RejectedPlay records.

    This pins the contract at the detector boundary in addition to
    the per-fixture harness-level pin (the parametric test above).

    DS §F intent (verbatim): "construct a 2-run sequence where
    month-1's substrate was REFUSED and month-2's is VALIDATED; assert
    no ML-fit ReasonCode leaks into engine_run.considered.reason_code"
    across the sequence.
    """

    from src.predictive.month_2_delta import detect_month_2_delta

    month_1 = _month_1_run_with_refused_substrates()
    month_2 = _month_2_engine_run_with_validated_substrates()

    def _loader(_store_id: str):
        return month_1

    md, _ = detect_month_2_delta(month_2, _MONTH_2_FIXTURE_STORE_ID, _loader)

    # Positive control: the detector DID populate the substrate-state-
    # delta. If md is None the assertion below is vacuously true and
    # the test loses its load-bearing meaning.
    assert md is not None, (
        "Detector returned None on the 2-run REFUSED → VALIDATED "
        "synthetic; the month-2 sequence is structurally invalid "
        "(check 21-day floor / anchor_date parse)."
    )
    assert md.days_between == 30
    # The REFUSED → VALIDATED transition surfaces honestly on the
    # typed audit field — NOT as a RejectedPlay code.
    for substrate in ("bgnbd", "gamma_gamma", "survival", "cf", "rfm"):
        entry = md.substrate_fit_status_changes.get(substrate)
        assert entry == ("REFUSED", "VALIDATED"), (
            f"substrate {substrate} expected (REFUSED, VALIDATED); got {entry!r}"
        )
    ret_entry = md.substrate_fit_status_changes.get("retention")
    assert ret_entry == ("REFUSED", "VALIDATED"), (
        f"retention expected (REFUSED, VALIDATED); got {ret_entry!r}"
    )

    # Q-S13-4 LOCK invariant — month-1 side. Walk every RejectedPlay-
    # bearing bucket on the constructed month-1 dict and assert no
    # MODEL_FIT_* reason_code appears.
    for bucket, play_id, code in _iter_reason_codes(month_1):
        assert code not in _FORBIDDEN_REASON_CODES, (
            "Q-S13-4 LOCK violation on month-1 side: bucket="
            f"{bucket!r} play_id={play_id!r} code={code!r}. ML-fit "
            "ReasonCodes must NEVER appear on RejectedPlay.reason_code."
        )

    # Q-S13-4 LOCK invariant — month-2 side. Walk the constructed
    # month-2 EngineRun's RejectedPlay buckets via to_dict (canonical
    # serialization shape).
    month_2_dict = month_2.to_dict()
    for bucket, play_id, code in _iter_reason_codes(month_2_dict):
        assert code not in _FORBIDDEN_REASON_CODES, (
            "Q-S13-4 LOCK violation on month-2 side: bucket="
            f"{bucket!r} play_id={play_id!r} code={code!r}. ML-fit "
            "ReasonCodes must NEVER appear on RejectedPlay.reason_code."
        )

    # Detector did NOT mutate month_2.considered / .watching /
    # .recommendations as a side effect of the substrate-state-delta
    # computation. Pivot 7 single-demote-channel invariant preserved.
    assert getattr(month_2, "considered", []) == []
    assert getattr(month_2, "watching", []) == []
    assert getattr(month_2, "recommendations", []) == []


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
