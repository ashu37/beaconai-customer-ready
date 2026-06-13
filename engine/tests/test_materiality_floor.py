"""Milestone 5 T5.3 — scale-aware materiality floor tests.

The plan calls for "three ARR tiers tested":
- < $1M ARR: max($5k, 2% of monthly_revenue)
- $1M-$5M ARR: max($10k, 3% of monthly_revenue)
- > $5M ARR: max($25k, 5% of monthly_revenue)

Tests pin the formula on representative monthly_revenue values plus
boundary behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.guardrails import scale_aware_materiality_floor  # noqa: E402


@pytest.mark.parametrize(
    "monthly_revenue, expected",
    [
        # Tier 1: <$1M ARR. Floor = max($5k, 2% * monthly_revenue).
        (10_000, 5_000.0),  # 2% = $200 < $5k -> $5k
        (50_000, 5_000.0),  # 2% = $1k < $5k -> $5k
        (80_000, 5_000.0),  # 2% = $1.6k < $5k -> $5k
        # Tier 2: $1M-$5M ARR. Floor = max($10k, 3% * monthly_revenue).
        (90_000, 10_000.0),  # 3% = $2.7k < $10k -> $10k. ARR ~$1.08M.
        (200_000, 10_000.0),  # 3% = $6k < $10k -> $10k.
        (350_000, 10_500.0),  # 3% = $10.5k -> $10.5k.
        (400_000, 12_000.0),  # 3% = $12k -> $12k.
        # Tier 3: >$5M ARR. Floor = max($25k, 5% * monthly_revenue).
        (500_000, 25_000.0),  # 5% = $25k -> $25k. ARR=$6M.
        (700_000, 35_000.0),  # 5% = $35k -> $35k.
        (1_000_000, 50_000.0),  # 5% = $50k -> $50k.
    ],
)
def test_three_arr_tiers(monthly_revenue, expected):
    assert scale_aware_materiality_floor(monthly_revenue) == pytest.approx(
        expected, rel=1e-9
    )


def test_unknown_monthly_revenue_returns_minimum_floor():
    # Per the contract: unknown / nonpositive => return $5k (smallest tier).
    assert scale_aware_materiality_floor(None) == 5_000.0
    assert scale_aware_materiality_floor(0) == 5_000.0
    assert scale_aware_materiality_floor(-1) == 5_000.0


def test_lower_tier_boundary():
    # ARR = $1M => mr = $1M / 12. ARR is NOT < 1M (boundary), so falls
    # into tier 2.
    mr_1m = 1_000_000.0 / 12.0
    assert scale_aware_materiality_floor(mr_1m) == 10_000.0

    # ARR just below $1M => mr = $999,999/12. Falls into tier 1.
    mr_under_1m = 999_999.0 / 12.0
    # 2% * mr ≈ $1,666 < $5k => $5k.
    assert scale_aware_materiality_floor(mr_under_1m) == 5_000.0


def test_upper_tier_boundary():
    # ARR = $5M => mr = $5M/12. ARR not < $5M => tier 3.
    mr_5m = 5_000_000.0 / 12.0
    # 5% * mr ≈ $20,833 < $25k => $25k.
    assert scale_aware_materiality_floor(mr_5m) == 25_000.0

    # ARR just below $5M => tier 2.
    mr_under_5m = 4_999_999.0 / 12.0
    # 3% * mr ≈ $12,500 -> > $10k => $12,500.
    assert scale_aware_materiality_floor(mr_under_5m) == pytest.approx(
        0.03 * mr_under_5m, rel=1e-9
    )


def test_pct_dominates_when_above_minimum():
    # On a tier-2 store the percentage dominates the absolute floor.
    # mr = $400k => ARR=$4.8M (tier 2). 3% = $12k > $10k absolute.
    assert scale_aware_materiality_floor(400_000) == 12_000.0
    # On tier-3, pct dominates above $25k. mr=$700k => ARR=$8.4M; 5%=$35k > $25k.
    assert scale_aware_materiality_floor(700_000) == 35_000.0


def test_floor_monotonic_in_revenue():
    # Increasing monthly revenue must never decrease the floor.
    seq = [50_000, 100_000, 250_000, 500_000, 750_000, 1_000_000]
    floors = [scale_aware_materiality_floor(x) for x in seq]
    for i in range(len(floors) - 1):
        assert floors[i + 1] >= floors[i]
