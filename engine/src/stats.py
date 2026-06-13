
from __future__ import annotations
from typing import Tuple, List, NamedTuple, Optional
import contextlib
import pandas as pd
import math
import numpy as np
import threading
from scipy.stats import norm, fisher_exact, ttest_ind, chi2, ttest_rel
from math import sqrt, erfc, log


# ---------------------------------------------------------------------------
# B-6 — multi-window combiner trace (test-only instrumentation)
# ---------------------------------------------------------------------------
#
# A thread-local set of ``(play_id, metric)`` keys that have flowed through
# ``combine_multiwindow_statistics`` since the trace was last reset. Used by
# ``tests/test_multiwindow_combiner_universality.py`` (B-6) to assert that
# every measured PlayCard on the Beauty pinned slate had its measurement
# block produced by the proper meta-analysis combiner, not the legacy
# min-p merge that the audit (post-6b §B-6) names as a defensibility hole.
#
# Production code MUST NOT read this trace -- it is purely diagnostic and
# the trace is empty unless a test has explicitly entered the
# ``multiwindow_combiner_trace`` context manager. Outside the context
# manager, ``record_combine_multiwindow_call`` is a no-op so production
# pays zero overhead.

_combine_trace_lock = threading.Lock()
_combine_trace_local = threading.local()


def _trace_state():
    """Per-thread (active_flag, set_of_keys). Lazy-init."""
    if not hasattr(_combine_trace_local, "active"):
        _combine_trace_local.active = False
        _combine_trace_local.keys = set()
    return _combine_trace_local


def record_combine_multiwindow_call(play_id: Optional[str], metric: Optional[str]) -> None:
    """Record that ``combine_multiwindow_statistics`` was called for the
    given ``(play_id, metric)`` key. Caller is responsible for passing a
    canonical pair; the trace stores ``(str(play_id), str(metric))`` to
    avoid type-mismatch lookups in tests.

    No-op outside an active ``multiwindow_combiner_trace`` context.
    """
    state = _trace_state()
    if not state.active:
        return
    state.keys.add((str(play_id) if play_id is not None else None,
                    str(metric) if metric is not None else None))


@contextlib.contextmanager
def multiwindow_combiner_trace():
    """Context manager that activates the trace for the current thread,
    yields the underlying set so the test can read it directly, and
    deactivates + clears the trace on exit. Re-entrant by accident is
    harmless: the same set is shared within the thread.
    """
    state = _trace_state()
    state.active = True
    state.keys = set()
    try:
        yield state.keys
    finally:
        state.active = False
        state.keys = set()

class TwoProportionResult(NamedTuple):
    diff: float        # p1 - p2 (absolute difference in proportions)
    p_value: float     # two-sided p-value (normal approx)
    ci_low: float      # CI low for (p1 - p2)
    ci_high: float     # CI high for (p1 - p2)

def _zcrit(alpha: float = 0.05) -> float:
    """
    Two-sided z critical value. Precomputed for common alphas.
    Falls back to 1.96 if an uncommon alpha is passed.
    """
    a = float(alpha)
    if abs(a - 0.05) < 1e-9:  # 95% CI
        return 1.959963984540054
    if abs(a - 0.10) < 1e-9:  # 90% CI
        return 1.6448536269514722
    if abs(a - 0.01) < 1e-9:  # 99% CI
        return 2.5758293035489004
    return 1.959963984540054

def _phi(z: float) -> float:
    """Standard normal CDF via erf: Phi(z) = 0.5 * erfc(-z / sqrt(2))."""
    return 0.5 * erfc(-z / sqrt(2.0))

def two_proportion_test(
    x1: int, n1: int, x2: int, n2: int, alpha: float = 0.05, continuity: bool = False
) -> TwoProportionResult:
    """
    Z test for difference in proportions (two-sided), with 1-α CI for (p1 - p2).
    - p1 = x1/n1, p2 = x2/n2
    - p-value uses pooled SE (classical two-proportion z-test).
    - CI uses unpooled SE (Wald CI for difference).
    - 'continuity': optional Yates correction for z numerator (rarely needed here).
    """
    n1 = int(n1); n2 = int(n2)
    x1 = int(x1); x2 = int(x2)
    if n1 <= 0 or n2 <= 0:
        return TwoProportionResult(diff=np.nan, p_value=1.0, ci_low=np.nan, ci_high=np.nan)

    p1 = x1 / n1
    p2 = x2 / n2
    diff = p1 - p2

    # pooled proportion for hypothesis test
    p_pool = (x1 + x2) / (n1 + n2)
    se_pooled = sqrt(max(p_pool * (1.0 - p_pool), 0.0) * (1.0 / n1 + 1.0 / n2))

    # continuity correction (optional)
    num = diff
    if continuity:
        # subtract 0.5/n from absolute difference
        cc = 0.5 * (1.0 / n1 + 1.0 / n2)
        num = np.sign(diff) * max(abs(diff) - cc, 0.0)

    # z and two-sided p-value using normal approx
    if se_pooled == 0.0:
        p_value = 1.0
    else:
        z = num / se_pooled
        # two-sided p = 2 * (1 - Phi(|z|)) = erfc(|z|/sqrt(2))
        p_value = float(erfc(abs(z) / sqrt(2.0)))

    # CI for difference uses unpooled SE
    se_unpooled = sqrt(
        max(p1 * (1.0 - p1), 0.0) / n1 + max(p2 * (1.0 - p2), 0.0) / n2
    )
    zc = _zcrit(alpha)
    if se_unpooled == 0.0:
        ci_low = ci_high = diff
    else:
        ci_low = diff - zc * se_unpooled
        ci_high = diff + zc * se_unpooled

    return TwoProportionResult(diff=float(diff), p_value=float(p_value),
                               ci_low=float(ci_low), ci_high=float(ci_high))
# --- end block ---
# ----------------- Proportions: CI and tests -----------------

def wilson_ci(successes: int, n: int, alpha: float = 0.05) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    n = max(0, int(n))
    if n == 0:
        return (0.0, 1.0)
    z = norm.ppf(1 - alpha / 2)
    phat = successes / n
    denom = 1 + z**2 / n
    center = (phat + z**2 / (2 * n)) / denom
    half = (z * math.sqrt((phat * (1 - phat) + z**2 / (4 * n)) / n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def two_proportion_z_test(s1: int, n1: int, s2: int, n2: int) -> float:
    """Two-proportion z-test (two-sided), returns p-value. Falls back to Fisher if near-zero counts."""
    n1, n2 = int(n1), int(n2)
    s1, s2 = int(s1), int(s2)
    if min(n1, n2) == 0:
        return 1.0
    # Fisher fallback if extreme counts
    if min(s1, s2, n1 - s1, n2 - s2) < 5:
        # construct 2x2 table
        a, b = s1, n1 - s1
        c, d = s2, n2 - s2
        _, p = fisher_exact([[a, b], [c, d]], alternative="two-sided")
        return float(p)
    p1, p2 = s1 / n1, s2 / n2
    p_pool = (s1 + s2) / (n1 + n2)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = (p1 - p2) / se
    p = 2 * (1 - norm.cdf(abs(z)))
    return float(p)


# ----------------- Means: Welch t-test (basic) -----------------

def welch_t_test(x: np.ndarray, y: np.ndarray) -> float:
    """Two-sided Welch t-test p-value (uses scipy.stats.ttest_ind with equal_var=False)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) == 0 or len(y) == 0:
        return 1.0
    _, p = ttest_ind(x, y, equal_var=False)
    return float(p)


# ----------------- Multiple testing (BH-FDR) -----------------


def benjamini_hochberg(pvals, alpha: float = 0.10):
    """
    Benjamini–Hochberg FDR correction.
    Args:
      pvals: iterable of p-values (NaNs allowed; treated as 1.0)
      alpha: target FDR level for reject mask (q <= alpha)
    Returns:
      qvals: list of BH-adjusted p-values (same order as input)
      reject: list[bool] where q <= alpha
    """
    if pvals is None:
        return [], []
    pv = np.asarray([1.0 if (x is None or (isinstance(x, float) and np.isnan(x))) else float(x) for x in pvals], dtype=float)
    n = pv.size
    if n == 0:
        return [], []

    order = np.argsort(pv)
    ranked = pv[order]

    q = np.empty(n, dtype=float)
    prev = 1.0
    # Compute monotone BH q-values backward
    for i in range(n - 1, -1, -1):
        rank = i + 1
        val = ranked[i] * n / rank
        if val > prev:
            val = prev
        prev = val
        q[order[i]] = min(1.0, max(0.0, val))

    reject = (q <= float(alpha))
    return q.tolist(), reject.tolist()



# ----------------- Power / MDE helpers -----------------

def needed_n_for_proportion_delta(p_base: float, delta_abs: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """
    Approx per-group sample size to detect an ABSOLUTE delta in proportions with two-sided z-test.
    """
    p = float(max(min(p_base, 1 - 1e-9), 1e-9))
    d = float(abs(delta_abs))
    if d <= 1e-9:
        return 10**9
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)
    se_needed = d / (z_alpha + z_beta)
    n = 2 * p * (1 - p) / (se_needed**2)
    return int(math.ceil(n))


# Compatibility alias if your code calls this name
def required_n_for_proportion(p_base: float, delta_abs: float, alpha: float = 0.05, power: float = 0.8) -> int:
    return needed_n_for_proportion_delta(p_base, delta_abs, alpha, power)


def mde_proportion(p_base: float, n_per_group: int, alpha: float = 0.05, power: float = 0.8) -> float:
    """
    Minimal detectable absolute delta in a two-sample proportion test
    for a given baseline proportion and per-group sample size.

    Mirrors the sample-size formula used in required_n_for_proportion.
    """
    p = float(max(min(p_base, 1 - 1e-9), 1e-9))
    n = int(max(n_per_group, 1))
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)
    se = math.sqrt(2.0 * p * (1.0 - p) / n)
    d = (z_alpha + z_beta) * se
    return float(d)


# ----------------- Seasonality Adjustment -----------------

# ----------------- Enhanced Multi-Window Statistical Methods -----------------

class MultiWindowResult(NamedTuple):
    """Result from multi-window statistical analysis."""
    effect_abs: float          # Combined effect size
    p_value: float            # Combined p-value
    std_error: float          # Combined standard error
    ci_low: float             # Confidence interval lower bound
    ci_high: float            # Confidence interval upper bound
    n_total: int              # Total sample size across windows
    contributing_windows: List[str]  # Which windows contributed
    window_effects: dict      # Individual window effects for transparency

def paired_t_test(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """
    Paired t-test for comparing matched samples.

    Returns:
        Tuple of (effect_size, p_value)
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if len(x) != len(y) or len(x) == 0:
        return 0.0, 1.0

    differences = x - y
    mean_diff = np.mean(differences)

    if len(differences) < 2:
        return mean_diff, 1.0

    _, p_value = ttest_rel(x, y)

    # Effect size as mean difference relative to baseline
    baseline_mean = np.mean(y)
    effect_size = mean_diff / baseline_mean if baseline_mean != 0 else 0.0

    return float(effect_size), float(p_value)

def fishers_combined_probability(p_values: List[float], weights: List[float] = None) -> float:
    """
    Combine p-values using Fisher's method.

    Args:
        p_values: List of p-values to combine
        weights: Optional weights for each p-value (not used in standard Fisher's method)

    Returns:
        Combined p-value
    """
    # Filter out invalid p-values
    valid_p_values = [p for p in p_values if p > 0 and p <= 1 and not np.isnan(p)]

    if not valid_p_values:
        return 1.0

    if len(valid_p_values) == 1:
        return valid_p_values[0]

    # Fisher's method: -2 * sum(ln(p_i)) ~ Chi2(2k)
    chi_squared = -2 * sum(log(p) for p in valid_p_values)
    df = 2 * len(valid_p_values)

    # Calculate combined p-value
    combined_p = 1 - chi2.cdf(chi_squared, df)

    return float(max(combined_p, 1e-10))  # Avoid exact zero

def inverse_variance_weighted_mean(effects: List[float], std_errors: List[float],
                                 business_weights: List[float] = None) -> Tuple[float, float]:
    """
    Combine effect sizes using inverse variance weighting (meta-analysis standard).

    Args:
        effects: List of effect sizes
        std_errors: List of standard errors for each effect
        business_weights: Optional business weights to combine with statistical weights

    Returns:
        Tuple of (combined_effect, combined_std_error)
    """
    if len(effects) != len(std_errors) or len(effects) == 0:
        return 0.0, float('inf')

    if len(effects) == 1:
        return float(effects[0]), float(std_errors[0])

    # Calculate precision (inverse variance) weights
    precisions = []
    for se in std_errors:
        if se > 0:
            precisions.append(1.0 / (se ** 2))
        else:
            precisions.append(1e6)  # Very high precision for zero std error

    # Combine with business weights if provided
    if business_weights and len(business_weights) == len(effects):
        # Normalize business weights
        total_bw = sum(business_weights)
        if total_bw > 0:
            normalized_bw = [w / total_bw for w in business_weights]
            # Combine statistical precision with business intelligence
            combined_weights = [p * bw for p, bw in zip(precisions, normalized_bw)]
        else:
            combined_weights = precisions
    else:
        combined_weights = precisions

    # Weighted average
    total_weight = sum(combined_weights)
    if total_weight == 0:
        return 0.0, float('inf')

    combined_effect = sum(e * w for e, w in zip(effects, combined_weights)) / total_weight
    combined_std_error = sqrt(1.0 / total_weight)

    return float(combined_effect), float(combined_std_error)

def combine_multiwindow_statistics(window_results: List[dict],
                                 business_weights: dict = None) -> MultiWindowResult:
    """
    Combine statistical results from multiple windows using proper meta-analysis.

    Args:
        window_results: List of dicts with keys: window, effect_abs, p_value, std_error, n
        business_weights: Dict mapping window names to business weights

    Returns:
        MultiWindowResult with combined statistics
    """
    if not window_results:
        return MultiWindowResult(
            effect_abs=0.0, p_value=1.0, std_error=float('inf'),
            ci_low=0.0, ci_high=0.0, n_total=0,
            contributing_windows=[], window_effects={}
        )

    if len(window_results) == 1:
        result = window_results[0]
        effect = result['effect_abs']
        std_err = result['std_error']
        return MultiWindowResult(
            effect_abs=effect, p_value=result['p_value'], std_error=std_err,
            ci_low=effect - 1.96 * std_err, ci_high=effect + 1.96 * std_err,
            n_total=result['n'], contributing_windows=[result['window']],
            window_effects={result['window']: effect}
        )

    # Extract data for combination
    effects = [r['effect_abs'] for r in window_results]
    std_errors = [r['std_error'] for r in window_results]
    p_values = [r['p_value'] for r in window_results]
    windows = [r['window'] for r in window_results]

    # Get business weights for these windows
    biz_weights = None
    if business_weights:
        biz_weights = [business_weights.get(w, 0.25) for w in windows]

    # Combine effect sizes using inverse variance weighting
    combined_effect, combined_std_error = inverse_variance_weighted_mean(
        effects, std_errors, biz_weights
    )

    # Combine p-values using Fisher's method
    combined_p_value = fishers_combined_probability(p_values)

    # Calculate confidence interval
    ci_margin = 1.96 * combined_std_error
    ci_low = combined_effect - ci_margin
    ci_high = combined_effect + ci_margin

    # Total sample size
    n_total = sum(r['n'] for r in window_results)

    # Window effects for transparency
    window_effects = {r['window']: r['effect_abs'] for r in window_results}

    return MultiWindowResult(
        effect_abs=combined_effect,
        p_value=combined_p_value,
        std_error=combined_std_error,
        ci_low=ci_low,
        ci_high=ci_high,
        n_total=n_total,
        contributing_windows=windows,
        window_effects=window_effects
    )

# ----------------- Action-Specific Statistical Analysis -----------------

def calculate_frequency_stats_single_window(g: pd.DataFrame, window_days: int) -> dict:
    """
    Calculate frequency acceleration statistics for a single window.

    Compares customer purchase frequencies between recent and prior periods.
    """
    maxd = pd.to_datetime(g["Created at"]).max()

    # Define periods
    recent_start = maxd - pd.Timedelta(days=window_days)
    prior_start = recent_start - pd.Timedelta(days=window_days)
    prior_end = recent_start - pd.Timedelta(seconds=1)

    # Get orders for each period
    recent_orders = g[g["Created at"] >= recent_start]
    prior_orders = g[(g["Created at"] >= prior_start) & (g["Created at"] <= prior_end)]

    if recent_orders.empty or prior_orders.empty:
        return None

    # Calculate customer frequencies (orders per customer per period)
    recent_freq = recent_orders.groupby("customer_id")["Name"].nunique()
    prior_freq = prior_orders.groupby("customer_id")["Name"].nunique()

    # Only include customers present in both periods
    common_customers = set(recent_freq.index) & set(prior_freq.index)

    if len(common_customers) < 20:  # Minimum sample size
        return None

    recent_values = recent_freq.loc[list(common_customers)].values
    prior_values = prior_freq.loc[list(common_customers)].values

    # Paired t-test for frequency differences
    effect_pct, p_value = paired_t_test(recent_values, prior_values)

    # Calculate standard error for effect size
    differences = recent_values - prior_values
    mean_prior = np.mean(prior_values)

    if len(differences) > 1 and mean_prior > 0:
        std_diff = np.std(differences, ddof=1)
        std_error = (std_diff / sqrt(len(differences))) / mean_prior
    else:
        std_error = float('inf')

    return {
        'effect_abs': effect_pct,
        'p_value': p_value,
        'std_error': std_error,
        'n': len(common_customers),
        'mean_recent_freq': np.mean(recent_values),
        'mean_prior_freq': np.mean(prior_values)
    }

def calculate_retention_stats_single_window(g: pd.DataFrame, window_days: int) -> dict:
    """
    Calculate retention improvement statistics for a single window.

    Compares retention rates between customer cohorts.
    """
    maxd = pd.to_datetime(g["Created at"]).max()

    # Define cohorts for retention analysis
    cohort1_start = maxd - pd.Timedelta(days=window_days + 30)
    cohort1_end = maxd - pd.Timedelta(days=30)
    cohort2_start = cohort1_start - pd.Timedelta(days=window_days)
    cohort2_end = cohort1_start - pd.Timedelta(seconds=1)

    # Get cohort customers
    cohort1_customers = g[(g["Created at"] >= cohort1_start) &
                         (g["Created at"] <= cohort1_end)]["customer_id"].unique()
    cohort2_customers = g[(g["Created at"] >= cohort2_start) &
                         (g["Created at"] <= cohort2_end)]["customer_id"].unique()

    if len(cohort1_customers) < 15 or len(cohort2_customers) < 15:
        return None

    # Calculate retention (customers still active in last 30 days)
    recent_active_start = maxd - pd.Timedelta(days=30)
    recent_active = set(g[g["Created at"] >= recent_active_start]["customer_id"].unique())

    cohort1_retained = len(set(cohort1_customers) & recent_active)
    cohort2_retained = len(set(cohort2_customers) & recent_active)

    # Two-proportion test for retention rates
    result = two_proportion_test(cohort1_retained, len(cohort1_customers),
                               cohort2_retained, len(cohort2_customers))

    # Effect size: reduction in churn rate
    cohort1_churn = 1 - (cohort1_retained / len(cohort1_customers))
    cohort2_churn = 1 - (cohort2_retained / len(cohort2_customers))
    churn_reduction = cohort2_churn - cohort1_churn  # Positive = improvement

    # Standard error from two-proportion test result
    std_error = (result.ci_high - result.ci_low) / 3.92  # 95% CI = ±1.96 SE

    return {
        'effect_abs': churn_reduction,
        'p_value': result.p_value,
        'std_error': std_error,
        'n': len(cohort1_customers) + len(cohort2_customers),
        'cohort1_retention': 1 - cohort1_churn,
        'cohort2_retention': 1 - cohort2_churn
    }

def calculate_journey_stats_single_window(g: pd.DataFrame, window_days: int) -> dict:
    """
    Calculate journey optimization statistics for a single window.

    Compares conversion rates between different customer journey patterns.
    """
    maxd = pd.to_datetime(g["Created at"]).max()

    # Define analysis period
    period_start = maxd - pd.Timedelta(days=window_days)
    period_orders = g[g["Created at"] >= period_start]

    if period_orders.empty:
        return None

    # Segment customers by journey complexity
    customer_order_counts = period_orders.groupby("customer_id")["Name"].nunique()

    simple_journey_customers = customer_order_counts[customer_order_counts == 1].index
    complex_journey_customers = customer_order_counts[customer_order_counts >= 2].index

    if len(simple_journey_customers) < 15 or len(complex_journey_customers) < 15:
        return None

    # Look at next period conversion (proxy for journey optimization potential)
    future_start = maxd + pd.Timedelta(days=1)
    future_end = maxd + pd.Timedelta(days=min(window_days, 28))  # Cap at 28 days
    future_orders = g[(g["Created at"] >= future_start) & (g["Created at"] <= future_end)]

    if future_orders.empty:
        # Use cross-period analysis instead
        mid_point = period_start + pd.Timedelta(days=window_days//2)
        early_period = period_orders[period_orders["Created at"] < mid_point]
        late_period = period_orders[period_orders["Created at"] >= mid_point]

        early_customers = set(early_period["customer_id"].unique())
        late_converters = set(late_period["customer_id"].unique())

        simple_conversions = len(set(simple_journey_customers) & early_customers & late_converters)
        complex_conversions = len(set(complex_journey_customers) & early_customers & late_converters)

        simple_base = len(set(simple_journey_customers) & early_customers)
        complex_base = len(set(complex_journey_customers) & early_customers)
    else:
        future_converters = set(future_orders["customer_id"].unique())
        simple_conversions = len(set(simple_journey_customers) & future_converters)
        complex_conversions = len(set(complex_journey_customers) & future_converters)
        simple_base = len(simple_journey_customers)
        complex_base = len(complex_journey_customers)

    if simple_base < 10 or complex_base < 10:
        return None

    # Two-proportion test for conversion improvement potential
    result = two_proportion_test(complex_conversions, complex_base,
                               simple_conversions, simple_base)

    # Standard error from two-proportion test
    std_error = (result.ci_high - result.ci_low) / 3.92  # 95% CI = ±1.96 SE

    return {
        'effect_abs': result.diff,  # Conversion improvement (complex - simple)
        'p_value': result.p_value,
        'std_error': std_error,
        'n': simple_base + complex_base,
        'simple_conversion_rate': simple_conversions / simple_base,
        'complex_conversion_rate': complex_conversions / complex_base
    }

def calculate_aov_momentum_stats_single_window(g: pd.DataFrame, window_days: int) -> dict:
    """
    Calculate AOV momentum statistics for a single window.

    Analyzes AOV growth trends to determine acceleration potential.
    """
    maxd = pd.to_datetime(g["Created at"]).max()

    # Create weekly AOV time series within the window
    weekly_aovs = []
    dates = []

    weeks_in_window = max(4, window_days // 7)  # At least 4 weeks

    for week in range(weeks_in_window):
        week_end = maxd - pd.Timedelta(days=week*7)
        week_start = week_end - pd.Timedelta(days=6)

        week_orders = g[(g["Created at"] >= week_start) & (g["Created at"] <= week_end)]

        if len(week_orders) > 0:
            week_aov = week_orders.groupby("Name")["net_sales"].first().mean()
            weekly_aovs.append(week_aov)
            dates.append(week_end)

    if len(weekly_aovs) < 4:  # Need sufficient data points
        return None

    # Reverse to get chronological order
    weekly_aovs = weekly_aovs[::-1]

    # Linear regression for growth trend
    from scipy.stats import linregress
    x = np.arange(len(weekly_aovs))
    slope, intercept, r_value, p_value, std_err = linregress(x, weekly_aovs)

    # Calculate growth rate and effect size
    baseline_aov = weekly_aovs[0]
    if baseline_aov <= 0:
        return None

    # Weekly growth rate as effect size
    weekly_growth_rate = slope / baseline_aov

    # Monthly acceleration potential (4 weeks)
    effect_abs = weekly_growth_rate * 4

    # Standard error for growth rate
    growth_std_error = std_err / baseline_aov if baseline_aov > 0 else float('inf')

    return {
        'effect_abs': effect_abs,
        'p_value': p_value,
        'std_error': growth_std_error * 4,  # Monthly std error
        'n': len(weekly_aovs),
        'weekly_growth_rate': weekly_growth_rate,
        'r_squared': r_value ** 2,
        'baseline_aov': baseline_aov,
        'current_aov': weekly_aovs[-1]
    }

def seasonal_adjustment(df: pd.DataFrame, metric: str = 'orders', seasonal: int = 7) -> Tuple[pd.Series, str]:
    """
    Return a seasonally adjusted daily time series for the given metric using STL.

    Args:
      df: DataFrame containing at least 'Created at' and the fields to derive the metric.
      metric: 'orders' (unique Name per day) or 'net_sales' (Subtotal-Total Discount per day).
      seasonal: STL seasonal period (days). Weekly=7 by default.

    Returns:
      pd.Series indexed by day (timestamp at 00:00) with trend+resid (i.e., with seasonal component removed).

    Notes:
      - Ignores cancelled/refunded rows if those columns exist.
      - Fills missing days with zeros before decomposition for stability.
    """
    try:
        from statsmodels.tsa.seasonal import STL
        stl_available = True
    except Exception:
        stl_available = False

    if df is None or df.empty:
        return pd.Series(dtype=float), "None"

    d = df.copy()
    d['Created at'] = pd.to_datetime(d['Created at'], errors='coerce')
    d = d.dropna(subset=['Created at'])
    if d.empty:
        return pd.Series(dtype=float), "None"

    # Exclude cancelled orders; keep refunds as negative values if present
    if 'Cancelled at' in d.columns:
        canc = pd.to_datetime(d['Cancelled at'], errors='coerce')
        d = d[canc.isna()]

    # Build daily metric
    grouper = pd.Grouper(key='Created at', freq='D')
    if metric == 'orders':
        if 'Name' in d.columns:
            ts = d.drop_duplicates('Name').groupby(grouper)['Name'].count()
        else:
            ts = d.groupby(grouper).size().astype(float)
    elif metric == 'net_sales':
        # Prefer Subtotal - Total Discount; fallback to Total - Shipping - Taxes
        def money(s: pd.Series | None) -> pd.Series:
            if s is None:
                return pd.Series(dtype=float)
            raw = s.astype(str)
            neg = raw.str.contains(r"^\s*\(.*\)\s*$", na=False)
            cleaned = raw.str.replace(r"[^\d\.\-]", "", regex=True)
            out = pd.to_numeric(cleaned, errors='coerce')
            out.loc[neg] = -out.loc[neg].abs()
            return out
        for c in ['Subtotal','Total Discount','Total','Shipping','Taxes']:
            if c in d.columns:
                d[c] = money(d[c])
        if {'Subtotal','Total Discount'}.issubset(d.columns):
            d['_net'] = d['Subtotal'] - d['Total Discount']
        elif {'Total','Shipping','Taxes'}.issubset(d.columns):
            d['_net'] = d['Total'] - d['Shipping'] - d['Taxes']
        else:
            d['_net'] = 0.0
        ts = d.groupby(grouper)['_net'].sum()
    else:
        # Generic: sum the provided numeric column per day
        if metric in d.columns:
            ts = pd.to_numeric(d[metric], errors='coerce').groupby(grouper).sum()
        else:
            return pd.Series(dtype=float)

    ts = ts.astype(float).fillna(0.0)
    # Ensure continuous daily index
    if not ts.empty:
        full_idx = pd.date_range(ts.index.min().normalize(), ts.index.max().normalize(), freq='D')
        ts = ts.reindex(full_idx, fill_value=0.0)

    # Data sufficiency guardrail
    n = int(ts.dropna().shape[0])
    if (not stl_available) or (n < 4 * int(seasonal)):
        # Fallback: centered moving average removal of seasonal component
        ma = ts.rolling(int(seasonal), min_periods=1, center=True).mean()
        adj = (ts - ma).rename(f"{metric}_adj")
        method = "MovingAverage"
    else:
        stl = STL(ts, seasonal=int(seasonal), robust=True)
        res = stl.fit()
        adj = (res.trend + res.resid).rename(f"{metric}_adj")
        method = "STL"

    # Clamp counts to non-negative
    if metric == 'orders':
        import numpy as np
        adj = pd.Series(np.clip(adj.values, 0.0, None), index=adj.index, name=adj.name)

    return adj, method
