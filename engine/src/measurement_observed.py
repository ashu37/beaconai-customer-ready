"""Sprint 7.6 Ticket T0 — shared observed-effect helper.

Pure-function module exporting recent-vs-prior observed-effect primitives
used by Tier-B builders (B-1 winback, B-2 replenishment, B-3 discount
hygiene, B-4 journey, B-5 aov_bundle) to compute per-store observed
``(observed_k, observed_n)`` for the prior-anchored card seam.

What this module IS:
    - A typed, side-effect-free helper. Inputs are caller-supplied
      recent / prior cell counts (or value arrays for Welch). Output is
      a typed result the caller threads into
      ``measurement_builder.build_prior_anchored_play_card`` via the
      existing ``observed_k`` / ``observed_n`` parameters.
    - Multi-window aware: a thin wrapper computes sign-agreement across
      a caller-supplied ``{window_label: result}`` map.

What this module is NOT:
    - It does not introduce an EB blend (``src.sizing.bayesian_blend``
      remains the single source of truth for posterior math).
    - It does not introduce a new card field or render surface.
    - It does not gate eligibility, downgrade cards, or rotate copy
      (those live behind ``ENGINE_V2_OBSERVED_ELIGIBILITY_GATE`` in T6).
    - It does not call any priors or sizing function.

Sign convention: ``effect = recent_rate - prior_rate``. ``sign`` is
``+1`` when ``effect > 0``, ``-1`` when ``effect < 0``, ``0`` when
effect is exactly zero or undefined.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import erfc, sqrt
from typing import Dict, Mapping, Optional, Sequence

import numpy as np
from scipy.stats import fisher_exact, ttest_ind


# Small-cell threshold below which we route through Fisher's exact
# rather than the normal-approx z-test for proportions. Matches the
# convention used by :func:`src.stats.two_proportion_z_test` (any cell
# with count < 5 falls back to Fisher).
_SMALL_CELL_THRESHOLD: int = 5

# Per-cell sample threshold below which we route Welch through scipy's
# ``ttest_ind`` directly (no large-n short-circuit). Caller may treat
# results with ``n < 30`` per cell with extra skepticism; we still
# compute and return them honestly.
_WELCH_MIN_PER_CELL: int = 2


@dataclass(frozen=True)
class ObservedEffectResult:
    """Recent-vs-prior observed-effect summary.

    Attributes:
        effect: ``recent_rate - prior_rate`` (or mean difference for
            Welch). ``None`` when either window has ``n=0`` (z-test) or
            ``n<2`` (Welch); never fabricated.
        n: Recent-window sample size (the ``n`` callers thread into the
            prior-anchored card as ``observed_n``).
        k: Recent-window success count (the ``k`` callers thread into
            the prior-anchored card as ``observed_k``). ``None`` for
            Welch-t (continuous metric).
        p_value: Two-sided p-value. ``None`` when undefined (zero-n,
            zero-variance, etc).
        sign: ``+1`` / ``-1`` / ``0`` per the sign convention above.
        method: ``"z_pooled"``, ``"fisher_exact"``, or ``"welch_t"`` —
            which test produced ``p_value``.
        recent_rate: ``recent_k / recent_n`` (or recent mean for Welch);
            ``None`` if undefined.
        prior_rate: ``prior_k / prior_n`` (or prior mean for Welch);
            ``None`` if undefined.
    """

    effect: Optional[float]
    n: int
    k: Optional[int]
    p_value: Optional[float]
    sign: int
    method: str
    recent_rate: Optional[float] = None
    prior_rate: Optional[float] = None


@dataclass(frozen=True)
class MultiWindowAgreement:
    """Sign-agreement summary across a small fixed window set.

    Attributes:
        sign_agreement_count: Number of windows whose ``sign`` matches
            the ``dominant_sign``. Computed only over windows with a
            non-zero ``sign`` (``n>0`` and ``effect != 0``).
        dominant_sign: Majority sign across non-zero-sign windows;
            ``0`` if there is no majority (tie) or all windows had
            ``sign=0``.
        windows: Per-window ``ObservedEffectResult`` keyed by window
            label (``"L28"``, ``"L56"``, ``"L90"``, ...). Pass-through.
    """

    sign_agreement_count: int
    dominant_sign: int
    windows: Mapping[str, ObservedEffectResult] = field(default_factory=dict)


def _sign(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def _two_sided_p_from_z(z: float) -> float:
    # erfc(|z|/sqrt(2)) == 2 * (1 - Phi(|z|))
    return float(erfc(abs(z) / sqrt(2.0)))


def compute_two_proportion_observed(
    recent_k: int,
    recent_n: int,
    prior_k: int,
    prior_n: int,
) -> ObservedEffectResult:
    """Two-proportion observed-effect for recent-vs-prior windows.

    Routes through Fisher's exact when any cell count is below
    ``_SMALL_CELL_THRESHOLD`` (mirrors :func:`src.stats.two_proportion_z_test`
    small-cell discipline). Pooled SE for the normal-approx p-value.

    Returns ``effect=None, n=0, p_value=None, sign=0`` when either
    window has ``n <= 0`` (honest zero-data short-circuit; the caller
    must NOT thread these into the prior-anchored card as observed
    data — pass ``observed_k=observed_n=0`` and let the posterior
    collapse to the prior).
    """

    rn = int(recent_n or 0)
    pn = int(prior_n or 0)
    rk = int(recent_k or 0)
    pk = int(prior_k or 0)

    if rn <= 0 or pn <= 0:
        return ObservedEffectResult(
            effect=None,
            n=0,
            k=None,
            p_value=None,
            sign=0,
            method="z_pooled",
            recent_rate=None,
            prior_rate=None,
        )

    # Clamp k into [0, n] to defend against caller bugs without
    # fabricating data.
    rk = max(0, min(rk, rn))
    pk = max(0, min(pk, pn))

    p_recent = rk / rn
    p_prior = pk / pn
    effect = p_recent - p_prior

    small_cell = min(rk, rn - rk, pk, pn - pk) < _SMALL_CELL_THRESHOLD

    if small_cell:
        table = [[rk, rn - rk], [pk, pn - pk]]
        try:
            _, p_value = fisher_exact(table, alternative="two-sided")
            p_value = float(p_value)
        except Exception:
            p_value = None
        method = "fisher_exact"
    else:
        p_pool = (rk + pk) / (rn + pn)
        se = sqrt(max(p_pool * (1.0 - p_pool), 0.0) * (1.0 / rn + 1.0 / pn))
        if se == 0.0:
            p_value = None
        else:
            z = effect / se
            p_value = _two_sided_p_from_z(z)
        method = "z_pooled"

    return ObservedEffectResult(
        effect=float(effect),
        n=int(rn),
        k=int(rk),
        p_value=p_value,
        sign=_sign(effect),
        method=method,
        recent_rate=float(p_recent),
        prior_rate=float(p_prior),
    )


def compute_welch_t_observed(
    recent_values: Sequence[float],
    prior_values: Sequence[float],
) -> ObservedEffectResult:
    """Welch-t observed-effect for continuous metric (e.g. AOV).

    Returns ``effect=None, n=0, p_value=None`` when either window has
    fewer than ``_WELCH_MIN_PER_CELL`` observations or zero variance
    in both windows.
    """

    rx = np.asarray(list(recent_values or []), dtype=float)
    px = np.asarray(list(prior_values or []), dtype=float)

    if rx.size < _WELCH_MIN_PER_CELL or px.size < _WELCH_MIN_PER_CELL:
        return ObservedEffectResult(
            effect=None,
            n=int(rx.size),
            k=None,
            p_value=None,
            sign=0,
            method="welch_t",
            recent_rate=None,
            prior_rate=None,
        )

    mean_recent = float(rx.mean())
    mean_prior = float(px.mean())
    effect = mean_recent - mean_prior

    if rx.var(ddof=1) == 0.0 and px.var(ddof=1) == 0.0:
        p_value: Optional[float] = None
    else:
        try:
            _, p = ttest_ind(rx, px, equal_var=False)
            p_value = float(p) if not np.isnan(p) else None
        except Exception:
            p_value = None

    return ObservedEffectResult(
        effect=float(effect),
        n=int(rx.size),
        k=None,
        p_value=p_value,
        sign=_sign(effect),
        method="welch_t",
        recent_rate=mean_recent,
        prior_rate=mean_prior,
    )


def compute_multi_window_sign_agreement(
    per_window: Mapping[str, ObservedEffectResult],
) -> MultiWindowAgreement:
    """Compute sign-agreement count across a caller-supplied window map.

    Only windows with a non-zero ``sign`` (i.e. ``n>0`` and a non-zero
    observed effect) count toward agreement. ``dominant_sign`` is the
    majority among non-zero-sign windows; on a tie or when all windows
    are sign-zero, ``dominant_sign=0`` and ``sign_agreement_count=0``.
    """

    pos = 0
    neg = 0
    for res in (per_window or {}).values():
        if res is None:
            continue
        if res.sign > 0:
            pos += 1
        elif res.sign < 0:
            neg += 1

    if pos == 0 and neg == 0:
        dominant = 0
        agreement = 0
    elif pos > neg:
        dominant = 1
        agreement = pos
    elif neg > pos:
        dominant = -1
        agreement = neg
    else:
        # tie -> no majority
        dominant = 0
        agreement = 0

    return MultiWindowAgreement(
        sign_agreement_count=int(agreement),
        dominant_sign=int(dominant),
        windows=dict(per_window or {}),
    )


__all__ = [
    "ObservedEffectResult",
    "MultiWindowAgreement",
    "compute_two_proportion_observed",
    "compute_welch_t_observed",
    "compute_multi_window_sign_agreement",
]
