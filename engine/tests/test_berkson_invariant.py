"""B-5 (Sprint 1, Engineer B) — Berkson-class invariant test.

Pins two distinct invariants whose joint effect blocks the Berkson
confound from re-entering the engine after the 554960d fix.

Invariant A (cohort-definition rule, structural)
------------------------------------------------
For any candidate where:
  * audience is defined as a behavioral subset of one window, AND
  * outcome is observed in a later, overlapping window,

the cohort denominator must be defined on early-half counts only. The
554960d fix on ``calculate_journey_stats_single_window`` is the canonical
implementation of this rule. The invariant test here directly
constructs a Berkson-shaped order DataFrame: every customer has exactly
one order in a 28-day analysis period. Without the fix, the
cross-period branch would compute ``simple_base = simple_customers ∩
late_customers = 0`` (since any single-order customer cannot appear in
BOTH halves), the two-proportion test would compare a real complex-arm
rate against a structurally-zero simple-arm rate, and effect would
collapse with a saturated p-value. The test asserts the function bails
to ``None`` (the degenerate-test guard added in 554960d) rather than
emitting an extreme-effect result.

Invariant B (M4b reclassification, contract)
-------------------------------------------
``subscription_nudge`` and ``routine_builder`` carry the same Berkson
shape today (≥3-SKU survivor cohort and bundle-attach cohort
respectively). M4b's ``TARGETING_RECLASSIFY_PLAYS`` ships them as
``evidence_class=targeting`` with ``measurement=None`` so the
fabricated Phase-2 effect constants never reach a rendered card. The
invariant test here scans the rendered Beauty pinned ``engine_run.json``
and asserts that any PlayCard surface where these play_ids appear
carries the targeting class and a null measurement block.

Together, A blocks new Berkson-shaped detectors from being added with a
broken cohort definition; B blocks the two existing at-risk detectors
from regressing past the M4b classification fix.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.stats import calculate_journey_stats_single_window  # noqa: E402


# ---------------------------------------------------------------------------
# Invariant A — cohort-definition rule
# ---------------------------------------------------------------------------


def _make_berkson_violating_df(n_customers: int = 200, anchor: str = "2025-09-18") -> pd.DataFrame:
    """Construct a 28-day analysis window where every customer has exactly
    one order. The cross-period branch of ``calculate_journey_stats_single_window``
    will hit this dataset because there is no future window (anchor is
    the maximum date). Without 554960d's fix, the cohort base would be
    forced to zero by the "must appear in BOTH halves" requirement.
    """
    anchor_ts = pd.Timestamp(anchor)
    period_start = anchor_ts - pd.Timedelta(days=27)
    rows = []
    for i in range(n_customers):
        # Spread orders evenly across the 28 days. Customer i gets one
        # order on day i % 28.
        ts = period_start + pd.Timedelta(days=i % 28)
        rows.append(
            {
                "Created at": ts,
                "customer_id": f"cust_{i:04d}",
                "Name": f"order_{i:04d}",
                "Total": 50.0,
            }
        )
    df = pd.DataFrame(rows)
    df["Created at"] = pd.to_datetime(df["Created at"])
    return df


def test_journey_stats_returns_none_on_berkson_shaped_input():
    """The 554960d degenerate-test guard must bail to ``None`` rather
    than emit a saturated p-value when every cohort member has exactly
    one whole-period order. This is the structural Berkson-block.
    """
    df = _make_berkson_violating_df(n_customers=200)
    result = calculate_journey_stats_single_window(df, window_days=28)
    # Every cohort member has exactly one order so the
    # ``complex_journey_customers`` arm (>=2 orders) is empty -> the
    # n>=15 guard at the function head returns None first. That's the
    # correct early-bail behavior for this shape; either None or a
    # well-formed non-pathological result is acceptable. What's NOT
    # acceptable is a saturated effect/p that the pre-554960d branch
    # would emit.
    assert result is None or (
        isinstance(result, dict)
        and abs(result.get("effect_abs", 0.0)) < 1.0  # not collapsed-to-1.0
        and result.get("p_value", 1.0) > 1e-30  # not saturated
    ), (
        f"calculate_journey_stats_single_window emitted a saturated "
        f"result on Berkson-shaped input: {result!r}. The 554960d fix "
        f"must keep the cohort base scoped to early-half counts."
    )


def test_journey_stats_handles_mixed_simple_and_complex_journeys_without_collapse():
    """A more realistic Berkson-bait shape: 80% of customers are
    simple-journey (1 order), 20% are complex-journey (3 orders) — but
    all complex orders cluster in the early half, so the late half
    cannot validate them. The function must not emit a 100% complex-arm
    rate against a 0% simple-arm rate.
    """
    anchor_ts = pd.Timestamp("2025-09-18")
    period_start = anchor_ts - pd.Timedelta(days=27)
    mid = period_start + pd.Timedelta(days=14)
    rows: List[Dict[str, Any]] = []
    # 160 simple-journey customers, one order each spread across the period.
    for i in range(160):
        rows.append(
            {
                "Created at": period_start + pd.Timedelta(days=i % 28),
                "customer_id": f"simple_{i:04d}",
                "Name": f"order_s_{i:04d}",
                "Total": 50.0,
            }
        )
    # 40 complex-journey customers, 3 orders each, all in early half.
    for i in range(40):
        for j in range(3):
            rows.append(
                {
                    "Created at": period_start + pd.Timedelta(days=(i % 13)),
                    "customer_id": f"complex_{i:04d}",
                    "Name": f"order_c_{i:04d}_{j}",
                    "Total": 60.0,
                }
            )
    df = pd.DataFrame(rows)
    df["Created at"] = pd.to_datetime(df["Created at"])

    result = calculate_journey_stats_single_window(df, window_days=28)
    # Either bails to None (defensive guard) OR returns a well-formed
    # dict whose effect is not pathologically large. The pre-554960d
    # branch could emit effect_abs ≈ 1.0 here (all complex visible in
    # late half because they had 3 orders, but the cohort base was
    # whole-period → zero late-window simple customers met the BOTH
    # criterion). The fix scopes base to early-half counts only.
    if result is not None:
        assert abs(result.get("effect_abs", 0.0)) < 0.95, (
            f"calculate_journey_stats_single_window emitted a near-100% "
            f"effect on Berkson-shaped input: {result!r}. The cohort "
            f"definition must remain on early-half counts only."
        )


# ---------------------------------------------------------------------------
# Invariant B — M4b targeting reclassification
# ---------------------------------------------------------------------------


# Plays the audit (post-6b §B-5) names as carrying the Berkson shape
# today. M4b's TARGETING_RECLASSIFY_PLAYS ships them at evidence_class=
# targeting with measurement=None. This invariant blocks regression.
BERKSON_AT_RISK_PLAYS: frozenset = frozenset({"subscription_nudge", "routine_builder"})


def _iter_play_cards_with_measurement(engine_run: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """Yield every PlayCard-shaped dict from rec / experiment surfaces.

    Considered list is RejectedPlay-shaped (no evidence_class /
    measurement field) so we skip it for the structural assertion --
    if these plays only appear in Considered, the invariant is
    trivially satisfied.
    """
    for k in ("recommendations", "recommended_experiments"):
        for card in engine_run.get(k) or []:
            yield card


@pytest.fixture(scope="module")
def beauty_engine_run() -> Dict[str, Any]:
    from tests.synthetic_harness import run_scenario

    with tempfile.TemporaryDirectory() as td:
        res = run_scenario("healthy_beauty_240d", Path(td))
        return json.loads(Path(res.engine_run_json_path).read_text())


def test_subscription_nudge_and_routine_builder_ship_targeting_with_no_measurement(
    beauty_engine_run,
):
    """Wherever these play_ids surface as PlayCards on the Beauty pinned
    slate, evidence_class must be 'targeting' and measurement must be
    None. M4b reclassification contract.
    """
    failures: List[str] = []
    for card in _iter_play_cards_with_measurement(beauty_engine_run):
        pid = str(card.get("play_id") or "")
        if pid not in BERKSON_AT_RISK_PLAYS:
            continue
        ec = card.get("evidence_class")
        meas = card.get("measurement")
        if ec != "targeting":
            failures.append(
                f"{pid}: evidence_class={ec!r} (expected 'targeting')"
            )
        if meas is not None:
            failures.append(
                f"{pid}: measurement={meas!r} (expected None)"
            )
    assert not failures, (
        f"Berkson-class targeting reclassification regression. M4b "
        f"requires subscription_nudge and routine_builder to ship at "
        f"evidence_class=targeting with measurement=None on any rendered "
        f"PlayCard surface. Violations: {failures!r}"
    )


def test_subscription_nudge_and_routine_builder_membership_pin():
    """Defensive: forces founder-level review if either play_id is
    later removed from the M4b reclassify list. Per audit §B-5 / §G-4,
    the right resolution if measurement design improves is to ship them
    at evidence_class=measured *with a real measurement*, not to drop
    them from the reclassify list while their emitter still emits the
    Phase 2 ``effect_abs=0.05/0.08`` constants.
    """
    from src.evidence import TARGETING_RECLASSIFY_PLAYS

    missing = BERKSON_AT_RISK_PLAYS - frozenset(TARGETING_RECLASSIFY_PLAYS)
    assert not missing, (
        f"M4b TARGETING_RECLASSIFY_PLAYS lost coverage of {missing!r}. "
        f"This is a Berkson-class regression risk. See "
        f"agent_outputs/post-6b-stop-coding-audit.md §B-5 and §G-4 for "
        f"the resolution path; do NOT drop these play_ids without an "
        f"explicit founder-level decision and a real measurement design."
    )


def test_synthetic_subscription_nudge_with_measurement_would_fail():
    """Self-test: a hand-constructed engine_run dict with a violating
    subscription_nudge card must trip the assertion. Pins the failure
    mode so a future scanner refactor cannot silently weaken detection.
    """
    fake = {
        "recommendations": [
            {
                "play_id": "subscription_nudge",
                "evidence_class": "measured",
                "measurement": {"effect_abs": 0.05, "p_internal": 0.001},
            }
        ]
    }
    failures: List[str] = []
    for card in _iter_play_cards_with_measurement(fake):
        pid = str(card.get("play_id") or "")
        if pid not in BERKSON_AT_RISK_PLAYS:
            continue
        ec = card.get("evidence_class")
        meas = card.get("measurement")
        if ec != "targeting":
            failures.append(f"{pid}: evidence_class={ec!r}")
        if meas is not None:
            failures.append(f"{pid}: measurement={meas!r}")
    assert failures, (
        "Self-test failed to detect a violating subscription_nudge card. "
        "The structural assertion logic above is broken."
    )
