"""Milestone 5 T5.7 — seasonality decoupled from confidence.

The M5 plan calls for moving ``get_seasonal_multiplier`` out of
``_calculate_business_confidence`` and into sizing/timing fields.

The semantic decoupling already happened in M4b T4b.3: when
``EVIDENCE_CLASS_ENFORCED=true``, ``_calculate_business_confidence``
short-circuits to ``_calculate_statistical_confidence(p)``, which is
seasonality-agnostic. T5.7 pins this contract with a forcing-function
test so a future agent who re-introduces seasonality into confidence
breaks the suite.

The legacy flag-off path retains the seasonality term (M10 owns
deletion); we deliberately do NOT remove the function body.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.action_engine import (  # noqa: E402
    _calculate_business_confidence,
    _calculate_statistical_confidence,
)


def test_confidence_independent_of_seasonality_when_evidence_class_enforced():
    cfg_on = {"EVIDENCE_CLASS_ENFORCED": True, "CONFIDENCE_MODE": "learning"}

    cand_neutral = {"p": 0.04, "n": 200, "effect_abs": 0.03, "seasonal_multiplier": 1.0}
    cand_high_season = {"p": 0.04, "n": 200, "effect_abs": 0.03, "seasonal_multiplier": 1.5}
    cand_low_season = {"p": 0.04, "n": 200, "effect_abs": 0.03, "seasonal_multiplier": 0.5}

    c_neutral = _calculate_business_confidence(cand_neutral, cfg_on)
    c_high = _calculate_business_confidence(cand_high_season, cfg_on)
    c_low = _calculate_business_confidence(cand_low_season, cfg_on)

    assert c_neutral == c_high == c_low, (
        "Confidence MUST not depend on seasonal_multiplier when "
        "EVIDENCE_CLASS_ENFORCED=true. T4b.3/T5.7 contract."
    )


def test_confidence_collapses_to_statistical_only_when_flag_on():
    cfg_on = {"EVIDENCE_CLASS_ENFORCED": True}
    cand = {"p": 0.04, "n": 200, "effect_abs": 0.03, "seasonal_multiplier": 1.4}
    expected = _calculate_statistical_confidence(cand)
    actual = _calculate_business_confidence(cand, cfg_on)
    assert actual == expected


def test_flag_off_path_still_in_tree_for_legacy_parity():
    """Smoke check that the legacy code path still exists in the source.

    M5 does not delete legacy code (M10 owns deletion). T5.7 only pins
    that the M4b on-path is seasonality-decoupled. With the flag off the
    legacy 60/40 blend is preserved as-is for parity; we don't pin any
    specific number here because the legacy formula has many candidate-
    dict prerequisites that vary by play_id.
    """
    import inspect

    from src.action_engine import _calculate_business_confidence  # noqa: WPS433

    src = inspect.getsource(_calculate_business_confidence)
    assert "EVIDENCE_CLASS_ENFORCED" in src, (
        "_calculate_business_confidence must short-circuit when the M4b "
        "evidence-class flag is set; the short-circuit is the contract "
        "between M4b confidence collapse and M5 T5.7 seasonality "
        "decoupling."
    )
