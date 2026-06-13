"""Milestone 4a T4a.4: NaN-handling invariant in evidence.classify_evidence.

This is the DS Architect QA Change 3 invariant frozen in memory.md:

* A NaN p-value combined with ``evidence_class_default == "targeting"`` is
  EXPECTED. The classifier maps such candidates to ``EvidenceClass.TARGETING``
  deterministically.
* A NaN p-value combined with ``evidence_class_default == "measured"`` is
  an ENGINE BUG. The classifier MUST raise so the engine surfaces the
  failure rather than render a "measured" card with no statistic behind it.
* Directional plays with NaN p are treated like measured-NaN (raise),
  because directional implies an observed effect; the no-measurement case
  must surface, not hide.
* The legacy fabricated targeting plays (subscription_nudge,
  routine_builder, journey_optimization, category_expansion,
  bestseller_amplify) all map cleanly to TARGETING under NaN — that is the
  whole point of the M4a fabricated-stat removal.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engine_run import EvidenceClass  # noqa: E402
from src.evidence import (  # noqa: E402
    EvidenceClassificationError,
    EvidenceContext,
    classify_evidence,
)
from src.play_registry import PLAYS  # noqa: E402


# ---------------------------------------------------------------------------
# Branch 1: NaN-p targeting → deterministic Targeting (expected, safe)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "play_id",
    [
        "subscription_nudge",
        "routine_builder",
        "journey_optimization",
        "category_expansion",
        "bestseller_amplify",
        "retention_mastery",
        "at_risk_repeat_buyer_rescue",
        "onsite_funnel_watch",
    ],
)
def test_nan_p_targeting_maps_to_targeting(play_id: str):
    """A targeting play with NaN p stays targeting. Expected M4a state."""

    # Sanity: confirm the registry actually says targeting for this id.
    assert PLAYS[play_id].evidence_class_default == "targeting", (
        f"test fixture out of sync with registry for {play_id!r}"
    )
    cand = {
        "play_id": play_id,
        "p": math.nan,
        "effect_abs": math.nan,
        "ci_low": math.nan,
        "ci_high": math.nan,
    }
    assert classify_evidence(cand) == EvidenceClass.TARGETING


def test_nan_p_targeting_via_evidence_context():
    ctx = EvidenceContext(
        play_id="subscription_nudge",
        p_value=math.nan,
        effect_abs=math.nan,
    )
    assert classify_evidence(ctx) == EvidenceClass.TARGETING


# ---------------------------------------------------------------------------
# Branch 2: NaN-p measured → raises (engine bug)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "play_id",
    [
        "winback_21_45",
        "discount_hygiene",
        "frequency_accelerator",
        "first_to_second_purchase",
    ],
)
def test_nan_p_measured_raises(play_id: str):
    """A measured play with NaN p is an engine bug; classifier must raise."""

    assert PLAYS[play_id].evidence_class_default == "measured", (
        f"test fixture out of sync with registry for {play_id!r}"
    )
    cand = {
        "play_id": play_id,
        "p": math.nan,
        "effect_abs": 0.05,  # could be finite or NaN; the p NaN is what raises
    }
    with pytest.raises(EvidenceClassificationError):
        classify_evidence(cand)


def test_nan_p_measured_via_evidence_context_raises():
    ctx = EvidenceContext(play_id="winback_21_45", p_value=math.nan)
    with pytest.raises(EvidenceClassificationError):
        classify_evidence(ctx)


# ---------------------------------------------------------------------------
# Branch 3: NaN-p directional → raises (M4a treats like measured)
# ---------------------------------------------------------------------------


def test_nan_p_directional_raises_aov_momentum():
    """Directional plays with NaN p also raise in M4a.

    The directional class still implies an observed effect; a NaN p with
    no statistic underneath is an engine bug and must surface, not silently
    downgrade.
    """

    assert PLAYS["aov_momentum"].evidence_class_default == "directional"
    cand = {
        "play_id": "aov_momentum",
        "p": math.nan,
        "effect_abs": 0.04,
    }
    with pytest.raises(EvidenceClassificationError):
        classify_evidence(cand)


def test_nan_p_directional_raises_empty_bottle():
    assert PLAYS["empty_bottle"].evidence_class_default == "directional"
    cand = {
        "play_id": "empty_bottle",
        "p": math.nan,
    }
    with pytest.raises(EvidenceClassificationError):
        classify_evidence(cand)


# ---------------------------------------------------------------------------
# Negative controls: finite p does NOT raise even on measured plays
# ---------------------------------------------------------------------------


def test_finite_p_measured_classifies_as_measured():
    cand = {
        "play_id": "winback_21_45",
        "p": 0.02,
        "effect_abs": 0.06,
    }
    assert classify_evidence(cand) == EvidenceClass.MEASURED


def test_high_finite_p_measured_still_classifies_as_measured():
    cand = {
        "play_id": "winback_21_45",
        "p": 0.95,  # high but finite -> the test-was-run, just not significant
    }
    assert classify_evidence(cand) == EvidenceClass.MEASURED


def test_zero_p_measured_classifies_as_measured():
    cand = {"play_id": "discount_hygiene", "p": 0.0}
    assert classify_evidence(cand) == EvidenceClass.MEASURED


# ---------------------------------------------------------------------------
# Sanity: invariant message includes the play_id and the class
# ---------------------------------------------------------------------------


def test_raise_message_carries_play_id():
    cand = {"play_id": "winback_21_45", "p": math.nan}
    with pytest.raises(EvidenceClassificationError) as exc_info:
        classify_evidence(cand)
    msg = str(exc_info.value)
    assert "winback_21_45" in msg
    assert "measured" in msg or "directional" in msg
    assert "NaN" in msg
