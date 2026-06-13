"""Tests for ``compute_consistency_across_windows`` (M4b T4b.2 / DS QA Change 1).

The function is a robustness signal that sits alongside
``combine_multiwindow_statistics``. It is a **pre-combination sign-agreement
count**, NOT a post-combination p-vote. The default formula is

    count of windows where
        sign(observed_effect) == sign(combiner.effect) AND |t-stat| > 1

These tests pin the formula on synthetic per-window stats covering the
edge cases listed in the spec: mixed signs, |t|=1 boundary, NaN inputs,
zero combiner effect, derived-from-CI t-stat fallback.
"""

from __future__ import annotations

import math

import pytest

from src.evidence import compute_consistency_across_windows


# ---------------------------------------------------------------------------
# Sign-agreement semantics
# ---------------------------------------------------------------------------


def test_all_windows_agree_high_t_all_count():
    """4 windows all sign-agree with combiner, all |t|>1 -> count==4."""
    windows = [
        {"effect_abs": 0.10, "t_stat": 2.5},
        {"effect_abs": 0.05, "t_stat": 1.8},
        {"effect_abs": 0.20, "t_stat": 3.0},
        {"effect_abs": 0.08, "t_stat": 1.2},
    ]
    assert compute_consistency_across_windows(windows, combined_effect=0.10) == 4


def test_two_windows_disagree_in_sign_excluded():
    """Two windows have opposite sign from combiner -> excluded."""
    windows = [
        {"effect_abs": 0.10, "t_stat": 2.0},   # agrees
        {"effect_abs": -0.05, "t_stat": 2.0},  # disagrees
        {"effect_abs": 0.15, "t_stat": 3.0},   # agrees
        {"effect_abs": -0.20, "t_stat": 4.0},  # disagrees
    ]
    assert compute_consistency_across_windows(windows, combined_effect=0.10) == 2


def test_negative_combiner_negative_windows_count():
    """Combiner sign is negative; windows that match negative count."""
    windows = [
        {"effect_abs": -0.10, "t_stat": 2.0},
        {"effect_abs": -0.05, "t_stat": 1.5},
        {"effect_abs": 0.20, "t_stat": 4.0},  # disagrees
    ]
    assert compute_consistency_across_windows(windows, combined_effect=-0.05) == 2


# ---------------------------------------------------------------------------
# |t-stat| > 1 boundary semantics
# ---------------------------------------------------------------------------


def test_t_stat_exactly_1_excluded_strict_inequality():
    """|t|=1 must NOT contribute (strict inequality per spec)."""
    windows = [
        {"effect_abs": 0.05, "t_stat": 1.0},   # boundary, excluded
        {"effect_abs": 0.05, "t_stat": 1.0001},  # included
    ]
    assert compute_consistency_across_windows(windows, combined_effect=0.05) == 1


def test_low_t_stat_windows_excluded():
    """Windows with |t|<1 don't contribute even if signs agree."""
    windows = [
        {"effect_abs": 0.10, "t_stat": 0.5},   # excluded
        {"effect_abs": 0.05, "t_stat": 0.9},   # excluded
        {"effect_abs": 0.20, "t_stat": 1.5},   # included
    ]
    assert compute_consistency_across_windows(windows, combined_effect=0.10) == 1


def test_negative_t_stat_uses_absolute_value():
    """|t-stat| matters; negative t with magnitude > 1 still counts."""
    windows = [
        {"effect_abs": 0.10, "t_stat": -2.0},  # |t|=2, sign agrees -> included
    ]
    assert compute_consistency_across_windows(windows, combined_effect=0.10) == 1


# ---------------------------------------------------------------------------
# NaN handling — windows with NaN content do not contribute
# ---------------------------------------------------------------------------


def test_nan_effect_excluded():
    windows = [
        {"effect_abs": float("nan"), "t_stat": 2.0},
        {"effect_abs": 0.05, "t_stat": 2.0},
    ]
    assert compute_consistency_across_windows(windows, combined_effect=0.05) == 1


def test_nan_t_stat_falls_back_to_effect_over_se():
    """If t_stat is NaN, fall back to effect/std_error derivation."""
    windows = [
        # NaN t_stat -> derive from effect/se = 0.10/0.02 = 5
        {"effect_abs": 0.10, "t_stat": float("nan"), "std_error": 0.02},
    ]
    assert compute_consistency_across_windows(windows, combined_effect=0.10) == 1


def test_zero_std_error_window_excluded():
    """Zero SE prevents t-derivation; window is excluded (conservative)."""
    windows = [
        {"effect_abs": 0.10, "std_error": 0.0},
    ]
    assert compute_consistency_across_windows(windows, combined_effect=0.10) == 0


def test_missing_t_and_se_excluded():
    windows = [
        {"effect_abs": 0.10},  # no t_stat, no std_error
    ]
    assert compute_consistency_across_windows(windows, combined_effect=0.10) == 0


# ---------------------------------------------------------------------------
# Combiner-side edge cases
# ---------------------------------------------------------------------------


def test_combiner_effect_zero_returns_zero():
    """No direction to agree with -> count is 0."""
    windows = [
        {"effect_abs": 0.10, "t_stat": 5.0},
        {"effect_abs": -0.10, "t_stat": 5.0},
    ]
    assert compute_consistency_across_windows(windows, combined_effect=0.0) == 0


def test_combiner_effect_nan_returns_zero():
    windows = [{"effect_abs": 0.10, "t_stat": 3.0}]
    assert compute_consistency_across_windows(windows, combined_effect=float("nan")) == 0


def test_zero_effect_window_does_not_contribute():
    """A window with exactly 0.0 observed effect is sign-neutral -> excluded."""
    windows = [
        {"effect_abs": 0.0, "t_stat": 5.0},
        {"effect_abs": 0.10, "t_stat": 2.0},
    ]
    assert compute_consistency_across_windows(windows, combined_effect=0.10) == 1


# ---------------------------------------------------------------------------
# Empty / degenerate input
# ---------------------------------------------------------------------------


def test_empty_window_list_returns_zero():
    assert compute_consistency_across_windows([], combined_effect=0.10) == 0


def test_non_mapping_entries_skipped():
    """Non-dict entries in iterable do not raise; they are skipped."""
    windows = [
        None,
        {"effect_abs": 0.10, "t_stat": 2.0},
        "not a dict",
    ]
    assert compute_consistency_across_windows(windows, combined_effect=0.10) == 1


# ---------------------------------------------------------------------------
# Pinning the spec example: 4 mixed windows, sign-only, t-threshold
# ---------------------------------------------------------------------------


def test_spec_example_mixed_signs_and_t_stats():
    """Spec text: '4 windows with mixed signs and t-stats verify the count
    is sign-agreement-only and that windows below |t|=1 are excluded.'

    Combiner effect is +0.05 (positive). We construct:
      win1: +effect, |t|=3.0   -> counted
      win2: -effect, |t|=4.0   -> sign disagrees, excluded
      win3: +effect, |t|=0.8   -> below threshold, excluded
      win4: +effect, |t|=2.0   -> counted

    Expected count = 2.
    """
    windows = [
        {"effect_abs": 0.10, "t_stat": 3.0},
        {"effect_abs": -0.20, "t_stat": 4.0},
        {"effect_abs": 0.07, "t_stat": 0.8},
        {"effect_abs": 0.05, "t_stat": 2.0},
    ]
    count = compute_consistency_across_windows(windows, combined_effect=0.05)
    assert count == 2, (
        "spec example expected 2 (sign-agreement + |t|>1); "
        f"got {count}. This is sign-only, NOT a p-vote."
    )


# ---------------------------------------------------------------------------
# Robustness contract: it is NOT a p-vote
# ---------------------------------------------------------------------------


def test_not_a_p_value_vote():
    """A window whose p-value is significant but whose sign disagrees with
    the combiner does NOT contribute. This pins the contract that the
    function is NOT a 'p < 0.05 vote'."""
    windows = [
        # Highly significant per its own p, but sign disagrees with combiner.
        {"effect_abs": -0.50, "t_stat": 10.0, "p_value": 0.0001},
        # Modest |t|, sign agrees -> counted.
        {"effect_abs": 0.05, "t_stat": 1.5, "p_value": 0.13},
    ]
    assert compute_consistency_across_windows(windows, combined_effect=0.05) == 1


def test_used_only_as_robustness_not_evidence_class_upgrade():
    """The function returns a non-negative int. It does NOT return a class.

    This pins the contract that downstream code must not synthesize an
    evidence_class from this number.
    """
    windows = [
        {"effect_abs": 0.10, "t_stat": 5.0},
        {"effect_abs": 0.10, "t_stat": 5.0},
        {"effect_abs": 0.10, "t_stat": 5.0},
        {"effect_abs": 0.10, "t_stat": 5.0},
    ]
    out = compute_consistency_across_windows(windows, combined_effect=0.10)
    assert isinstance(out, int)
    assert out == 4
    # No EvidenceClass-like value is returned. The caller is expected to
    # use this only as a robustness signal.


# ---------------------------------------------------------------------------
# Custom threshold parameter
# ---------------------------------------------------------------------------


def test_custom_t_threshold_lower():
    windows = [
        {"effect_abs": 0.10, "t_stat": 0.6},   # below default 1.0 threshold
        {"effect_abs": 0.10, "t_stat": 1.5},
    ]
    # With default threshold=1.0 only the second contributes.
    assert compute_consistency_across_windows(windows, combined_effect=0.10) == 1
    # With a relaxed threshold (0.5), both contribute.
    assert (
        compute_consistency_across_windows(
            windows, combined_effect=0.10, t_stat_threshold=0.5
        )
        == 2
    )


def test_custom_t_threshold_higher():
    windows = [
        {"effect_abs": 0.10, "t_stat": 1.5},
        {"effect_abs": 0.10, "t_stat": 3.0},
    ]
    # With a stricter threshold (2.5), only the second contributes.
    assert (
        compute_consistency_across_windows(
            windows, combined_effect=0.10, t_stat_threshold=2.5
        )
        == 1
    )
