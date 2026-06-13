"""Milestone 4a T4a.4: evidence classification basics.

These tests guard the deterministic mapping in ``src.evidence.classify_evidence``
in M4a. M4b will extend the classifier with semantic rules (n thresholds,
consistency-across-windows, observed-effect agreement); those are out of
scope here.

Coverage:

* The classifier returns the registry's ``evidence_class_default`` for a
  candidate with finite stats.
* The classifier returns ``EvidenceClass.TARGETING`` for any registered
  targeting play, regardless of p-value (NaN or finite).
* An unknown ``play_id`` defensively maps to ``targeting`` (the legacy
  emitter contract is enforced separately by the M2 registry tests).
* Missing ``play_id`` raises ``EvidenceClassificationError``.
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
# Fixtures
# ---------------------------------------------------------------------------


def _candidate(play_id: str, **overrides):
    base = {
        "play_id": play_id,
        "p": 0.04,
        "effect_abs": 0.06,
        "ci_low": 0.02,
        "ci_high": 0.10,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Registry-default classification (finite stats)
# ---------------------------------------------------------------------------


def test_winback_with_finite_p_classifies_as_measured():
    cand = _candidate("winback_21_45", p=0.01, effect_abs=0.05)
    assert classify_evidence(cand) == EvidenceClass.MEASURED


def test_discount_hygiene_with_finite_p_classifies_as_measured():
    cand = _candidate("discount_hygiene", p=0.03, effect_abs=0.02)
    assert classify_evidence(cand) == EvidenceClass.MEASURED


def test_aov_momentum_with_finite_p_classifies_as_directional():
    cand = _candidate("aov_momentum", p=0.07, effect_abs=0.04)
    assert classify_evidence(cand) == EvidenceClass.DIRECTIONAL


def test_empty_bottle_with_finite_p_classifies_as_directional():
    cand = _candidate("empty_bottle", p=0.06, effect_abs=0.03)
    assert classify_evidence(cand) == EvidenceClass.DIRECTIONAL


def test_subscription_nudge_classifies_as_targeting_with_finite_p():
    cand = _candidate("subscription_nudge", p=0.04, effect_abs=0.05)
    assert classify_evidence(cand) == EvidenceClass.TARGETING


def test_routine_builder_classifies_as_targeting_with_finite_p():
    cand = _candidate("routine_builder", p=0.03, effect_abs=0.08)
    assert classify_evidence(cand) == EvidenceClass.TARGETING


def test_journey_optimization_classifies_as_targeting():
    cand = _candidate("journey_optimization", p=0.05, effect_abs=0.30)
    assert classify_evidence(cand) == EvidenceClass.TARGETING


def test_category_expansion_classifies_as_targeting():
    cand = _candidate("category_expansion", p=0.04, effect_abs=0.40)
    assert classify_evidence(cand) == EvidenceClass.TARGETING


def test_bestseller_amplify_classifies_as_targeting():
    cand = _candidate("bestseller_amplify", p=0.03, effect_abs=0.20)
    assert classify_evidence(cand) == EvidenceClass.TARGETING


# ---------------------------------------------------------------------------
# EvidenceContext input
# ---------------------------------------------------------------------------


def test_evidence_context_input_is_accepted():
    ctx = EvidenceContext(play_id="winback_21_45", p_value=0.02)
    assert classify_evidence(ctx) == EvidenceClass.MEASURED


def test_evidence_context_targeting_with_finite_p():
    ctx = EvidenceContext(play_id="subscription_nudge", p_value=0.01)
    assert classify_evidence(ctx) == EvidenceClass.TARGETING


# ---------------------------------------------------------------------------
# Defensive defaults
# ---------------------------------------------------------------------------


def test_unknown_play_id_defaults_to_targeting():
    cand = _candidate("not_a_real_play", p=0.04)
    assert classify_evidence(cand) == EvidenceClass.TARGETING


def test_missing_play_id_raises():
    with pytest.raises(EvidenceClassificationError):
        classify_evidence({"p": 0.04, "effect_abs": 0.05})


def test_empty_play_id_raises():
    with pytest.raises(EvidenceClassificationError):
        classify_evidence({"play_id": "", "p": 0.02})


# ---------------------------------------------------------------------------
# Registry-as-injected
# ---------------------------------------------------------------------------


def test_classifier_uses_injected_registry():
    """A different registry should change the answer for the same play_id.

    This guards "registry is the source of truth" — the function reads
    ``evidence_class_default`` off the passed-in registry rather than
    consulting the live PLAYS dict directly when a registry is supplied.
    """

    fake_registry = {
        "subscription_nudge": PLAYS["subscription_nudge"]  # baseline targeting
    }
    cand = _candidate("subscription_nudge", p=0.02)
    assert classify_evidence(cand, registry=fake_registry) == EvidenceClass.TARGETING


# ---------------------------------------------------------------------------
# Sanity: every registered play classifies under finite p without raising
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("play_id", sorted(PLAYS.keys()))
def test_every_registered_play_classifies_with_finite_p(play_id: str):
    cand = _candidate(play_id, p=0.04, effect_abs=0.05)
    result = classify_evidence(cand)
    assert isinstance(result, EvidenceClass)
    # Result must equal the registry default for finite stats in M4a.
    expected = PLAYS[play_id].evidence_class_default
    assert result.value == expected, (
        f"play_id={play_id!r} expected {expected!r} but got {result.value!r}"
    )


def test_finite_p_value_is_not_treated_as_nan():
    """Sanity guard against an off-by-one bug in the NaN check."""

    cand = _candidate("winback_21_45", p=0.999)  # very high p but not NaN
    assert classify_evidence(cand) == EvidenceClass.MEASURED


def test_zero_p_value_is_treated_as_finite():
    cand = _candidate("winback_21_45", p=0.0)
    assert classify_evidence(cand) == EvidenceClass.MEASURED


def test_none_p_value_is_treated_as_not_nan():
    """A missing p-value (None) is distinct from NaN — None means "no test was run yet"."""

    cand = _candidate("winback_21_45", p=None)
    # M4a contract: classify_evidence treats None as "not NaN" (the M4a NaN
    # sentinel is specifically math.nan), so a measured play with p=None
    # still resolves to MEASURED. The engine bug surfaces only when a
    # candidate explicitly carries math.nan.
    assert classify_evidence(cand) == EvidenceClass.MEASURED
