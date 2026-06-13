"""Sprint 7.6 Ticket T0 — unit tests for the shared observed-effect helper."""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.stats import fisher_exact, ttest_ind

from src.measurement_observed import (
    MultiWindowAgreement,
    ObservedEffectResult,
    compute_multi_window_sign_agreement,
    compute_two_proportion_observed,
    compute_welch_t_observed,
)


# ---------------------------------------------------------------------------
# compute_two_proportion_observed
# ---------------------------------------------------------------------------


def test_two_proportion_positive_effect_large_cells():
    # recent 200/1000 = 0.20; prior 150/1000 = 0.15; effect +0.05
    res = compute_two_proportion_observed(200, 1000, 150, 1000)
    assert res.method == "z_pooled"
    assert res.n == 1000
    assert res.k == 200
    assert res.sign == 1
    assert res.effect == pytest.approx(0.05, abs=1e-9)
    assert res.recent_rate == pytest.approx(0.20)
    assert res.prior_rate == pytest.approx(0.15)
    # scipy-independent sanity bound: z is well above 2, so p << 0.05
    assert res.p_value is not None and res.p_value < 0.01


def test_two_proportion_negative_effect_large_cells():
    res = compute_two_proportion_observed(80, 1000, 150, 1000)
    assert res.sign == -1
    assert res.effect == pytest.approx(-0.07, abs=1e-9)
    assert res.p_value is not None and res.p_value < 0.01


def test_two_proportion_zero_n_short_circuit_recent():
    res = compute_two_proportion_observed(0, 0, 50, 100)
    assert res.effect is None
    assert res.n == 0
    assert res.k is None
    assert res.p_value is None
    assert res.sign == 0


def test_two_proportion_zero_n_short_circuit_prior():
    res = compute_two_proportion_observed(5, 100, 0, 0)
    assert res.effect is None
    assert res.n == 0
    assert res.p_value is None
    assert res.sign == 0


def test_two_proportion_small_cell_routes_to_fisher():
    # one cell count < 5 -> Fisher exact
    res = compute_two_proportion_observed(1, 20, 4, 20)
    assert res.method == "fisher_exact"
    assert res.n == 20
    assert res.k == 1
    # cross-check against scipy directly
    _, expected_p = fisher_exact([[1, 19], [4, 16]], alternative="two-sided")
    assert res.p_value == pytest.approx(float(expected_p), abs=1e-9)


def test_two_proportion_k_clamped_to_n():
    # caller bug-defense: k > n should not blow up; clamps without
    # fabricating data
    res = compute_two_proportion_observed(50, 10, 5, 100)
    assert res.k == 10
    assert res.recent_rate == pytest.approx(1.0)


def test_two_proportion_zero_effect_sign_zero():
    res = compute_two_proportion_observed(100, 1000, 100, 1000)
    assert res.sign == 0
    assert res.effect == pytest.approx(0.0)


def test_two_proportion_p_value_matches_scipy_reference():
    # Cross-check the z-pooled branch against scipy where possible.
    # For large cells we use the same pooled-SE formula; verify the
    # two-sided p matches a hand-computed reference.
    res = compute_two_proportion_observed(60, 500, 40, 500)
    # effect = 0.12 - 0.08 = 0.04; p_pool = 100/1000 = 0.10
    # se = sqrt(0.10*0.90*(2/500)) = sqrt(0.00036)
    se = math.sqrt(0.10 * 0.90 * (2.0 / 500.0))
    z = 0.04 / se
    expected_p = math.erfc(abs(z) / math.sqrt(2.0))
    assert res.p_value == pytest.approx(expected_p, abs=1e-9)


# ---------------------------------------------------------------------------
# compute_welch_t_observed
# ---------------------------------------------------------------------------


def test_welch_t_positive_effect():
    rng = np.random.default_rng(42)
    recent = rng.normal(loc=110.0, scale=20.0, size=200)
    prior = rng.normal(loc=100.0, scale=20.0, size=200)
    res = compute_welch_t_observed(recent.tolist(), prior.tolist())
    assert res.method == "welch_t"
    assert res.n == 200
    assert res.k is None
    assert res.sign == 1
    assert res.effect is not None and res.effect > 0
    # cross-check vs scipy
    _, expected = ttest_ind(recent, prior, equal_var=False)
    assert res.p_value == pytest.approx(float(expected), abs=1e-9)


def test_welch_t_small_cell_short_circuit():
    res = compute_welch_t_observed([1.0], [1.0, 2.0, 3.0])
    assert res.effect is None
    assert res.p_value is None
    assert res.n == 1


def test_welch_t_zero_variance_both_short_circuit():
    res = compute_welch_t_observed([5.0, 5.0, 5.0], [5.0, 5.0, 5.0])
    assert res.effect == pytest.approx(0.0)
    assert res.sign == 0
    assert res.p_value is None


# ---------------------------------------------------------------------------
# compute_multi_window_sign_agreement
# ---------------------------------------------------------------------------


def _mk_result(sign: int, n: int = 100) -> ObservedEffectResult:
    return ObservedEffectResult(
        effect=0.05 * sign if sign != 0 else 0.0,
        n=n,
        k=int(0.1 * n),
        p_value=0.04,
        sign=sign,
        method="z_pooled",
        recent_rate=0.1,
        prior_rate=0.05,
    )


def test_multi_window_agreement_three_positive():
    per = {"L28": _mk_result(1), "L56": _mk_result(1), "L90": _mk_result(1)}
    agg = compute_multi_window_sign_agreement(per)
    assert agg.sign_agreement_count == 3
    assert agg.dominant_sign == 1


def test_multi_window_agreement_two_of_three():
    per = {"L28": _mk_result(1), "L56": _mk_result(1), "L90": _mk_result(-1)}
    agg = compute_multi_window_sign_agreement(per)
    assert agg.sign_agreement_count == 2
    assert agg.dominant_sign == 1


def test_multi_window_agreement_one_only_sign_zero_dominant():
    # one positive, one negative, one zero -> tie among non-zero => no majority
    per = {"L28": _mk_result(1), "L56": _mk_result(-1), "L90": _mk_result(0)}
    agg = compute_multi_window_sign_agreement(per)
    assert agg.sign_agreement_count == 0
    assert agg.dominant_sign == 0


def test_multi_window_agreement_all_sign_zero():
    per = {"L28": _mk_result(0), "L56": _mk_result(0), "L90": _mk_result(0)}
    agg = compute_multi_window_sign_agreement(per)
    assert agg.sign_agreement_count == 0
    assert agg.dominant_sign == 0


def test_multi_window_agreement_empty_input():
    agg = compute_multi_window_sign_agreement({})
    assert agg.sign_agreement_count == 0
    assert agg.dominant_sign == 0
    assert agg.windows == {}


def test_multi_window_agreement_preserves_windows_payload():
    per = {"L28": _mk_result(1), "L56": _mk_result(1)}
    agg = compute_multi_window_sign_agreement(per)
    assert set(agg.windows.keys()) == {"L28", "L56"}
    assert agg.windows["L28"].sign == 1
