from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import numpy as np, pandas as pd, json
import datetime
import os

# stats & scoring
from .stats import (
    two_proportion_z_test,   # p-value only
    welch_t_test,            # p-value only
    benjamini_hochberg,      # returns q-values list
    required_n_for_proportion,
    # Enhanced multi-window statistical methods
    MultiWindowResult,
    combine_multiwindow_statistics,
    fishers_combined_probability,
    inverse_variance_weighted_mean,
    # Action-specific statistical analysis
    calculate_frequency_stats_single_window,
    calculate_retention_stats_single_window,
    calculate_journey_stats_single_window,
    calculate_aov_momentum_stats_single_window,
)
from .scoring import (
    compute_score,
    significance_to_score,
    effect_to_score,
    audience_to_score,
    confidence_from_ci,
    financial_to_score,
)

# utils
from .utils import write_json
from .utils import get_interaction_factors
from .utils import subscription_threshold_for_product, categorize_product
from .utils import get_window_weights, get_seasonal_multiplier, detect_customer_cohorts, pool_cohort_results, get_vertical_mode, get_subvertical
from .features import compute_repeat_curve, build_g_items


DEFAULT_DEBUG_CATEGORIES: set[str] = set()
_ENV_DEBUG = (os.getenv('ENGINE_DEBUG_CATEGORIES') or '').strip()
if _ENV_DEBUG:
    lowered = _ENV_DEBUG.lower()
    if lowered in {'none', '0', 'false', 'off'}:
        DEBUG_CATEGORIES = set()
    else:
        DEBUG_CATEGORIES = {cat.strip().lower() for cat in _ENV_DEBUG.split(',') if cat.strip()}
else:
    DEBUG_CATEGORIES = DEFAULT_DEBUG_CATEGORIES


def debug_log(category: str, message: str) -> None:
    if category.lower() in DEBUG_CATEGORIES:
        print(message)

# Vertical-specific conversion rates and incrementality based on industry benchmarks
def get_business_stage_from_revenue(annual_revenue: float) -> str:
    """Classify business by annual revenue for realistic scaling."""
    if annual_revenue < 200_000:
        return "startup"      # <200K: Early stage, lower conversion/bundle capabilities
    elif annual_revenue < 1_000_000:
        return "growth"       # 200K-1M: Established but still building
    elif annual_revenue < 5_000_000:
        return "mature"       # 1M-5M: Mature operations, higher capabilities
    else:
        return "enterprise"   # 5M+: Enterprise level operations

def get_business_stage() -> str:
    """Get business stage from environment with revenue-based fallback."""
    import os
    # Check explicit env var first
    stage = os.getenv('BUSINESS_STAGE', '').strip().lower()
    if stage in ['startup', 'growth', 'mature', 'enterprise']:
        return stage

    # Fallback: estimate from revenue if available
    try:
        annual_revenue = float(os.getenv('ANNUAL_REVENUE', 0))
        if annual_revenue > 0:
            return get_business_stage_from_revenue(annual_revenue)
    except (ValueError, TypeError):
        pass

    return "growth"  # Default to growth stage


def get_business_health_saturation_thresholds(business_metrics: dict) -> dict:
    """
    Adjust market saturation thresholds based on business health.

    Healthy businesses with strong retention can target higher percentages of customers
    without diminishing returns, while struggling businesses should use lower thresholds.

    Returns:
        Dict of adjusted saturation thresholds for each action type
    """
    base_thresholds = MARKET_SATURATION_THRESHOLDS

    if not business_metrics:
        return base_thresholds

    # Primary signal: returning customer share
    returning_share = business_metrics.get('returning_share', 0.5)

    if returning_share > 0.9:        # 90%+ = exceptional business
        multiplier = 2.5             # Much higher thresholds (more customers can be targeted)
    elif returning_share > 0.8:      # 80%+ = strong business
        multiplier = 2.0             # Higher thresholds
    elif returning_share > 0.6:      # 60%+ = good business
        multiplier = 1.5             # Moderately higher thresholds
    else:                            # <60% = struggling business
        multiplier = 1.0             # Keep conservative thresholds

    # Apply multiplier but cap at 100%
    if multiplier >= 2.5:
        cap = 1.5  # exceptionally healthy businesses can reach deeper into the base
    elif multiplier >= 2.0:
        cap = 1.25
    else:
        cap = 1.0

    adjusted_thresholds = {k: min(v * multiplier, cap) for k, v in base_thresholds.items()}

    return adjusted_thresholds

def get_business_health_decay_adjustment(business_metrics: dict) -> float:
    """
    Adjust decay factors based on business health.

    Healthy businesses with strong retention should have minimal decay since their
    customers are more engaged and actions have longer-lasting impact.

    Returns:
        Decay adjustment multiplier (0.5-1.0):
        - 1.0 = No additional decay (healthy business)
        - 0.8 = Moderate additional decay (average business)
        - 0.5 = Aggressive decay (struggling business)
    """
    if not business_metrics:
        return 0.8  # Default moderate decay for unknown businesses

    # Primary signal: returning customer share
    returning_share = business_metrics.get('returning_share', 0.5)

    if returning_share > 0.9:        # 90%+ = exceptional business
        adjustment = 1.0  # No additional decay - use base decay factors
        debug_log('metrics_detail', f"Exceptional retention ({returning_share:.1%}) → minimal decay")
    elif returning_share > 0.8:      # 80%+ = strong business
        adjustment = 0.95  # Very light additional decay
        debug_log('metrics_detail', f"Strong retention ({returning_share:.1%}) → light decay")
    elif returning_share > 0.6:      # 60%+ = good business
        adjustment = 0.85  # Moderate additional decay
        debug_log('metrics_detail', f"Good retention ({returning_share:.1%}) → moderate decay")
    else:                            # <60% = struggling business
        adjustment = 0.7   # More aggressive decay
        debug_log('metrics_detail', f"Low retention ({returning_share:.1%}) → aggressive decay")

    return adjustment

def get_performance_multiplier(business_metrics: dict) -> float:
    """
    Scale conversion rates based on actual business performance signals.

    High-performing businesses (94%+ returning customers, strong AOV growth) should get
    significantly higher conversion rates than struggling businesses.

    Args:
        business_metrics: Dict containing performance indicators
            - returning_share: % of orders from returning customers (0.0-1.0)
            - aov_growth: Recent AOV growth rate (0.05 = 5% growth)
            - repeat_rate: % customers making repeat purchases (0.0-1.0)
            - monthly_revenue: Monthly revenue for scale assessment

    Returns:
        Multiplier for conversion rates (0.5x to 2.0x)
    """
    multiplier = 1.0  # Base multiplier for average businesses

    # 1. Returning customer share (strongest signal of business health)
    returning_share = business_metrics.get('returning_share', 0.5)
    if returning_share > 0.9:        # 90%+ = exceptional business (1.5x rates)
        multiplier *= 1.5
        debug_log('metrics_detail', f"Exceptional retention ({returning_share:.1%}) → 1.5x conversion boost")
    elif returning_share > 0.8:      # 80%+ = strong business (1.3x rates)
        multiplier *= 1.3
        debug_log('metrics_detail', f"Strong retention ({returning_share:.1%}) → 1.3x conversion boost")
    elif returning_share > 0.6:      # 60%+ = good business (1.1x rates)
        multiplier *= 1.1
        debug_log('metrics_detail', f"Good retention ({returning_share:.1%}) → 1.1x conversion boost")
    elif returning_share < 0.4:      # <40% = struggling (0.8x rates)
        multiplier *= 0.8
        debug_log('metrics_detail', f"Low retention ({returning_share:.1%}) → 0.8x conversion penalty")

    # 2. AOV growth trend (indicates upsell momentum)
    aov_growth = business_metrics.get('aov_growth', 0.0)
    if aov_growth > 0.05:            # 5%+ growth = strong upsell momentum
        aov_boost = 1.2
        multiplier *= aov_boost
        debug_log('metrics_detail', f"Strong AOV growth ({aov_growth:+.1%}) → {aov_boost}x upsell boost")
    elif aov_growth > 0.02:          # 2%+ growth = moderate momentum
        aov_boost = 1.1
        multiplier *= aov_boost
        debug_log('metrics_detail', f"Moderate AOV growth ({aov_growth:+.1%}) → {aov_boost}x upsell boost")
    elif aov_growth < -0.02:         # Declining AOV = harder to upsell
        aov_penalty = 0.9
        multiplier *= aov_penalty
        debug_log('metrics_detail', f"Declining AOV ({aov_growth:+.1%}) → {aov_penalty}x upsell penalty")

    # 3. Repeat rate (frequency opportunity)
    repeat_rate = business_metrics.get('repeat_rate', 0.2)
    if repeat_rate > 0.4:            # 40%+ = high frequency business
        freq_boost = 1.2
        multiplier *= freq_boost
        debug_log('metrics_detail', f"High repeat rate ({repeat_rate:.1%}) → {freq_boost}x frequency boost")
    elif repeat_rate > 0.25:         # 25%+ = good frequency
        freq_boost = 1.1
        multiplier *= freq_boost
        debug_log('metrics_detail', f"Good repeat rate ({repeat_rate:.1%}) → {freq_boost}x frequency boost")

    # 4. Revenue scale (larger businesses typically execute better)
    monthly_revenue = business_metrics.get('monthly_revenue', 50000)
    if monthly_revenue > 200000:     # $200K+/month = enterprise execution
        scale_boost = 1.15
        multiplier *= scale_boost
        debug_log('metrics_detail', f"Enterprise scale (${monthly_revenue/1000:.0f}K/mo) → {scale_boost}x execution boost")
    elif monthly_revenue > 100000:   # $100K+/month = mature execution
        scale_boost = 1.05
        multiplier *= scale_boost
        debug_log('metrics_detail', f"Mature scale (${monthly_revenue/1000:.0f}K/mo) → {scale_boost}x execution boost")

    # Cap multiplier for sanity (0.5x to 2.5x range)
    final_multiplier = max(0.5, min(multiplier, 2.5))

    if final_multiplier != multiplier:
        debug_log('metrics_detail', f"Performance multiplier capped: {multiplier:.2f} → {final_multiplier:.2f}")

    debug_log('metrics', f"Performance multiplier: {final_multiplier:.2f}x vs baseline")
    return final_multiplier

def extract_business_metrics(aligned: dict) -> dict:
    """Extract business performance metrics from aligned data for conversion scaling."""
    business_metrics = {}

    # Get the primary analysis window (usually L28)
    primary_window = None
    for window in ['L28', 'L56', 'L90', 'L7']:
        if window in aligned:
            primary_window = aligned[window]
            break

    if not primary_window and 'window_days' in aligned:
        # Single-window dict; treat it as the primary window directly
        primary_window = {
            'returning_customer_share': aligned.get('returning_customer_share'),
            'repeat_rate_within_window': aligned.get('repeat_rate_within_window'),
            'net_sales': aligned.get('net_sales'),
            'delta': aligned.get('delta', {}),
            'meta': aligned.get('meta', {})
        }

    if not primary_window:
        return {}

    def _numeric_metric(value, fallback):
        try:
            if value is None:
                return fallback
            parsed = float(value)
            if pd.isna(parsed):
                return fallback
            return parsed
        except (TypeError, ValueError):
            return fallback

    # Extract key performance indicators. Sparse merchant exports can carry
    # None for these fields; keep candidate generation alive so downstream
    # data-quality gates can abstain instead of crashing the run.
    business_metrics['returning_share'] = _numeric_metric(primary_window.get('returning_customer_share'), 0.5)
    business_metrics['repeat_rate'] = _numeric_metric(primary_window.get('repeat_rate_within_window'), 0.2)
    business_metrics['monthly_revenue'] = _numeric_metric(primary_window.get('net_sales'), 50000)

    # Observed customer counts for saturation logic
    meta = primary_window.get('meta', {}) if isinstance(primary_window.get('meta'), dict) else {}
    identified_recent = meta.get('identified_recent')
    if identified_recent:
        business_metrics['customer_base_recent'] = float(identified_recent)

    # Calculate AOV growth from delta analysis if available
    delta = primary_window.get('delta', {})
    try:
        aov_delta = float(delta.get('aov', 0.0) or 0.0)
    except (TypeError, ValueError):
        aov_delta = 0.0
    business_metrics['aov_growth'] = aov_delta

    # Add some debug info
    debug_log(
        'metrics',
        (
            "Business metrics | returning={:.1%}, repeat={:.1%}, monthly=${:,.0f}, aov_growth={:+.1%}".format(
                business_metrics['returning_share'],
                business_metrics['repeat_rate'],
                business_metrics['monthly_revenue'],
                business_metrics['aov_growth'],
            )
        ),
    )

    return business_metrics

def get_conversion_rates(vertical_mode: str = "mixed") -> dict:
    """Return baseline mature-stage conversion rates for the requested vertical."""
    base_rates = {
        'beauty': {
            'winback_21_45': 0.08,
            'bestseller_amplify': 0.18,
            'discount_hygiene': 1.0,
            'routine_builder': 0.15,
            'subscription_nudge': 0.12,
            'frequency_accelerator': 0.22,
            'aov_momentum': 0.20,
            'retention_mastery': 0.85,
            'journey_optimization': 0.35,
            'category_expansion': 0.45,
            'default': 0.05,
        },
        'supplements': {
            'winback_21_45': 0.12,
            'bestseller_amplify': 0.14,
            'discount_hygiene': 1.0,
            'routine_builder': 0.08,
            'subscription_nudge': 0.18,
            'frequency_accelerator': 0.18,
            'aov_momentum': 0.16,
            'retention_mastery': 0.90,
            'journey_optimization': 0.25,
            'category_expansion': 0.25,
            'default': 0.05,
        },
        'mixed': {
            'winback_21_45': 0.06,
            'bestseller_amplify': 0.15,
            'discount_hygiene': 1.0,
            'routine_builder': 0.10,
            'subscription_nudge': 0.10,
            'frequency_accelerator': 0.16,
            'aov_momentum': 0.14,
            'retention_mastery': 0.75,
            'journey_optimization': 0.25,
            'category_expansion': 0.30,
            'default': 0.05,
        }
    }
    return base_rates.get(vertical_mode.lower(), base_rates['mixed'])


def compute_conversion_multiplier(play_id: str, business_stage: str, business_metrics: dict | None,
                                  vertical_mode: str = "mixed") -> float:
    """Combine stage, performance, and execution factors into a single multiplier."""
    if play_id == 'discount_hygiene':
        # Margin actions rely on discount depth; keep conversion neutral aside from execution confidence.
        base_stage_multiplier = 1.0
        performance_multiplier = 1.0
        health_conversion_boost = 1.0
    else:
        stage_multipliers = {
            'startup': 0.6,
            'growth': 0.8,
            'mature': 1.0,
            'enterprise': 1.2,
        }
        base_stage_multiplier = stage_multipliers.get(str(business_stage).lower(), 1.0)
        health_conversion_boost = 1.0
        performance_multiplier = get_performance_multiplier(business_metrics) if business_metrics else 1.0

        if business_metrics and base_stage_multiplier <= 1.0:
            returning_share = business_metrics.get('returning_share', 0.0) or 0.0
            repeat_rate = business_metrics.get('repeat_rate', 0.0) or 0.0
            if returning_share >= 0.95 and repeat_rate >= 0.30:
                base_stage_multiplier = max(base_stage_multiplier, 1.15)
                debug_log('metrics_detail', "Elevating stage multiplier for elite retention")
            elif returning_share >= 0.90 and repeat_rate >= 0.25:
                base_stage_multiplier = max(base_stage_multiplier, 1.05)
                debug_log('metrics_detail', "Elevating stage multiplier for strong retention")
            elif returning_share >= 0.85 and repeat_rate >= 0.20:
                base_stage_multiplier = max(base_stage_multiplier, 1.0)

            if returning_share >= 0.95 and repeat_rate >= 0.30:
                health_conversion_boost = 1.35
            elif returning_share >= 0.90 and repeat_rate >= 0.25:
                health_conversion_boost = 1.20
            elif returning_share >= 0.85 and repeat_rate >= 0.20:
                health_conversion_boost = 1.10

    execution_map = EXECUTION_CAPABILITY_MULTIPLIERS.get(str(business_stage).lower(), {})
    execution_base = execution_map.get(play_id, 1.0)

    health_execution_boost = 1.0
    if business_metrics:
        returning_share = business_metrics.get('returning_share', 0.0) or 0.0
        repeat_rate = business_metrics.get('repeat_rate', 0.0) or 0.0
        if returning_share >= 0.93 and repeat_rate >= 0.30:
            health_execution_boost = 1.25
        elif returning_share >= 0.85 and repeat_rate >= 0.25:
            health_execution_boost = 1.12
        elif returning_share >= 0.75:
            health_execution_boost = 1.05

    if play_id == 'discount_hygiene':
        combined = execution_base * health_execution_boost
    else:
        combined = base_stage_multiplier * performance_multiplier * health_conversion_boost * execution_base * health_execution_boost

    final_multiplier = max(0.5, min(combined, 2.5))
    debug_log('metrics', f"Conversion multiplier for {play_id}: {combined:.2f} → {final_multiplier:.2f}")
    return final_multiplier

def get_incrementality_factors(vertical_mode: str = "mixed", business_stage: str = "growth") -> dict:
    """Get base incrementality factors by vertical."""
    base_factors = {
        'beauty': {
            'winback_21_45': 0.75,
            'bestseller_amplify': 0.85,
            'discount_hygiene': 1.0,
            'routine_builder': 0.80,
            'subscription_nudge': 0.90,
            'frequency_accelerator': 0.88,
            'aov_momentum': 0.85,
            'retention_mastery': 1.0,
            'journey_optimization': 0.80,
            'category_expansion': 0.75,
            'default': 0.75,
        },
        'supplements': {
            'winback_21_45': 0.85,
            'bestseller_amplify': 0.70,
            'discount_hygiene': 1.0,
            'routine_builder': 0.65,
            'subscription_nudge': 0.95,
            'frequency_accelerator': 0.92,
            'aov_momentum': 0.75,
            'retention_mastery': 1.0,
            'journey_optimization': 0.70,
            'category_expansion': 0.60,
            'default': 0.75,
        },
        'mixed': {
            'winback_21_45': 0.65,
            'bestseller_amplify': 0.75,
            'discount_hygiene': 1.0,
            'routine_builder': 0.70,
            'subscription_nudge': 0.80,
            'frequency_accelerator': 0.75,
            'aov_momentum': 0.70,
            'retention_mastery': 1.0,
            'journey_optimization': 0.65,
            'category_expansion': 0.60,
            'default': 0.70,
        }
    }
    return base_factors.get(vertical_mode.lower(), base_factors['mixed'])


def adjust_incrementality(play_id: str, base_incrementality: float, business_metrics: dict | None, optimistic: bool = False) -> float:
    """Adapt incrementality based on business health and optimism."""
    inc = float(base_incrementality or 0.75)

    if business_metrics:
        returning_share = float(business_metrics.get('returning_share', 0.5) or 0.5)
        repeat_rate = float(business_metrics.get('repeat_rate', 0.2) or 0.2)

        if returning_share >= 0.95 and repeat_rate >= 0.30:
            inc += 0.12
        elif returning_share >= 0.90 and repeat_rate >= 0.25:
            inc += 0.08
        elif returning_share >= 0.80 and repeat_rate >= 0.20:
            inc += 0.04
        elif returning_share < 0.60:
            inc -= 0.08
        elif returning_share < 0.70:
            inc -= 0.04

        if play_id in {'frequency_accelerator', 'retention_mastery', 'journey_optimization'} and repeat_rate >= 0.30:
            inc += 0.02

    if optimistic:
        inc += 0.05

    return max(0.45, min(1.0, inc))


def get_effect_params(play_id: str, vertical_mode: str, business_stage: str, business_metrics: dict | None) -> dict:
    """Return action-specific effect assumptions with base and optimistic values."""
    vertical = str(vertical_mode).lower()
    stage = str(business_stage).lower()
    returning_share = (business_metrics or {}).get('returning_share', 0.5) or 0.5
    repeat_rate = (business_metrics or {}).get('repeat_rate', 0.2) or 0.2

    stage_scaler = {
        'startup': 0.85,
        'growth': 1.0,
        'mature': 1.1,
        'enterprise': 1.2,
    }.get(stage, 1.0)

    health_boost = 1.0
    if returning_share >= 0.95 and repeat_rate >= 0.30:
        health_boost = 1.25
    elif returning_share >= 0.90 and repeat_rate >= 0.25:
        health_boost = 1.15
    elif returning_share >= 0.80 and repeat_rate >= 0.20:
        health_boost = 1.05
    elif returning_share < 0.60:
        health_boost = 0.90

    params: dict[str, float] = {}

    if play_id == 'frequency_accelerator':
        base_map = {'beauty': 0.25, 'supplements': 0.18, 'mixed': 0.21}
        base_lift = base_map.get(vertical, base_map['mixed']) * stage_scaler * health_boost
        base_lift = max(0.12, min(0.45, base_lift))
        params['frequency_lift'] = base_lift
        params['frequency_lift_opt'] = min(0.55, base_lift * 1.35)

    elif play_id == 'retention_mastery':
        base_map = {'beauty': 0.09, 'supplements': 0.08, 'mixed': 0.075}
        churn_reduction = base_map.get(vertical, base_map['mixed']) * stage_scaler * health_boost
        churn_reduction = max(0.04, min(0.18, churn_reduction))
        params['churn_reduction'] = churn_reduction
        params['churn_reduction_opt'] = min(0.25, churn_reduction * 1.5)

    elif play_id == 'journey_optimization':
        base_map = {'beauty': 0.35, 'supplements': 0.28, 'mixed': 0.30}
        conversion_improvement = base_map.get(vertical, base_map['mixed']) * stage_scaler * health_boost
        conversion_improvement = max(0.15, min(0.55, conversion_improvement))
        params['conversion_improvement'] = conversion_improvement
        params['conversion_improvement_opt'] = min(0.70, conversion_improvement * 1.4)

    elif play_id == 'winback_21_45':
        base_orders = 1.3 * stage_scaler
        if returning_share >= 0.90:
            base_orders = max(base_orders, 1.55)
        elif returning_share >= 0.80:
            base_orders = max(base_orders, 1.45)
        params['orders_per_customer'] = min(1.8, base_orders)
        params['orders_per_customer_opt'] = min(2.2, params['orders_per_customer'] * 1.2)

    elif play_id == 'aov_momentum':
        growth_multiplier = 1.5 if vertical == 'beauty' else 1.4
        params['growth_acceleration'] = growth_multiplier * health_boost
        params['growth_acceleration_opt'] = params['growth_acceleration'] * 1.25

    elif play_id == 'discount_hygiene':
        base_rate = 0.0075 if vertical == 'beauty' else 0.005
        base_rate *= stage_scaler * health_boost
        params['margin_recovery_rate'] = base_rate
        params['margin_recovery_rate_opt'] = base_rate * 1.4

    elif play_id == 'category_expansion':
        base_rate = 0.40 if vertical == 'beauty' else 0.32
        base_rate *= stage_scaler * health_boost
        params['expansion_rate'] = max(0.18, min(0.55, base_rate))
        params['expansion_rate_opt'] = min(0.70, params['expansion_rate'] * 1.35)

    elif play_id == 'routine_builder':
        base_bundle = 85.0 if vertical == 'beauty' else 65.0
        adjusted = base_bundle * stage_scaler * health_boost
        params['bundle_value'] = adjusted
        params['bundle_value_opt'] = adjusted * 1.15

    elif play_id == 'subscription_nudge':
        multiplier = 1.18 if vertical == 'beauty' else 1.12
        multiplier *= health_boost
        params['subscription_multiplier'] = multiplier
        params['subscription_multiplier_opt'] = multiplier * 1.1

    return params


def compute_decay_multiplier(play_id: str, source_window: int, business_metrics: dict | None, optimistic: bool = False) -> float:
    """Return decay multiplier adjusted for business health and scenario."""
    window_decay = ACTION_SPECIFIC_DECAY.get(source_window, {})
    base_decay = window_decay.get(play_id, window_decay.get('default', 1.0))

    if not business_metrics:
        adjusted = min(1.0, base_decay if not optimistic else (base_decay + 0.1))
        debug_log('revenue_detail', f"Decay adjustment for {play_id}: {base_decay:.2f} → {adjusted:.2f}")
        return adjusted

    health_adjustment = get_business_health_decay_adjustment(business_metrics)
    adjusted = base_decay + (1.0 - base_decay) * health_adjustment
    if optimistic and adjusted < 1.0:
        adjusted = min(1.0, adjusted + 0.1)
    debug_log('revenue_detail', f"Decay adjustment for {play_id}: {base_decay:.2f} → {adjusted:.2f}")
    return adjusted


def _estimate_customer_base(audience: int, aov: float, business_metrics: dict | None) -> float:
    """Estimate the active customer base used for saturation checks."""
    if business_metrics:
        base = float(business_metrics.get('customer_base_recent') or 0)
        if base <= 0:
            monthly_revenue = float(business_metrics.get('monthly_revenue') or 0)
            base = monthly_revenue / max(aov * 1.5, 1e-6)
    else:
        base = 1000.0

    base = max(base, float(audience))
    return max(base, 1.0)


def apply_saturation_penalty(play_id: str, audience: int, aov: float, revenue: float,
                             business_metrics: dict | None, optimistic: bool = False) -> float:
    """Apply market saturation penalty based on audience penetration."""
    if revenue <= 0 or audience <= 0:
        return revenue

    customer_base = _estimate_customer_base(audience, aov, business_metrics)
    penetration = min(audience / customer_base, 1.0)

    thresholds = get_business_health_saturation_thresholds(business_metrics) if business_metrics else MARKET_SATURATION_THRESHOLDS
    threshold = thresholds.get(play_id, thresholds.get('default', 0.3))

    safe_zone = threshold + 0.05
    if business_metrics:
        returning_share = business_metrics.get('returning_share', 0.5)
        if returning_share >= 0.90:
            safe_zone += 0.05
        elif returning_share >= 0.80:
            safe_zone += 0.03

    if optimistic:
        safe_zone += 0.05

    if penetration <= safe_zone:
        return revenue

    oversaturation_ratio = (penetration - safe_zone) / max(1e-6, (1.0 - safe_zone))
    penalty_strength = 0.6
    min_effectiveness = 0.2

    if business_metrics:
        returning_share = business_metrics.get('returning_share', 0.5)
        if returning_share >= 0.95:
            penalty_strength = 0.25
            min_effectiveness = 0.60
        elif returning_share >= 0.90:
            penalty_strength = 0.30
            min_effectiveness = 0.50
        elif returning_share >= 0.80:
            penalty_strength = 0.40
            min_effectiveness = 0.35

    if optimistic:
        penalty_strength *= 0.75
        min_effectiveness = max(min_effectiveness, 0.5)

    effectiveness = max(min_effectiveness, 1.0 - penalty_strength * oversaturation_ratio)
    penalized = revenue * effectiveness
    debug_log('revenue_detail', f"Saturation penalty: {play_id} penetration={penetration:.2f}, threshold={threshold:.2f}, factor={effectiveness:.2f}")
    return penalized

# Phase 4: Action-specific time decay factors for realistic projections
# Different actions have different sustainability patterns
ACTION_SPECIFIC_DECAY = {
    28: {  # 28-day baseline (no decay)
        'default': 1.0,
    },
    56: {  # 56-day projections
        # Campaign-driven actions (front-loaded impact)
        'winback_21_45': 0.7,           # Marketing campaigns fade
        'bestseller_amplify': 0.7,      # Upsell campaigns fade
        'routine_builder': 0.75,        # Bundle campaigns somewhat persistent
        'aov_momentum': 0.6,            # Growth acceleration is temporary
        'category_expansion': 0.65,     # Cross-sell campaigns fade

        # Structural improvements (more persistent)
        'frequency_accelerator': 0.85,  # Habit changes stick better
        'retention_mastery': 0.9,       # Retention improvements are structural
        'journey_optimization': 0.9,    # Funnel fixes are persistent

        # Default for unknown actions
        'default': 0.7,
    },
    90: {  # 90-day projections
        # Campaign-driven actions (significant decay)
        'winback_21_45': 0.5,           # Marketing impact fades significantly
        'bestseller_amplify': 0.5,      # Upsell fatigue sets in
        'routine_builder': 0.6,         # Bundle interest wanes
        'aov_momentum': 0.4,            # Growth acceleration very temporary
        'category_expansion': 0.45,     # Cross-sell novelty wears off

        # Structural improvements (still strong)
        'frequency_accelerator': 0.75,  # Habits take time but stick
        'retention_mastery': 0.85,      # Retention tools remain effective
        'journey_optimization': 0.8,    # Funnel improvements persist

        # Default for unknown actions
        'default': 0.5,
    }
}

# Legacy decay factors (kept for backward compatibility)
DECAY_FACTORS = {
    28: 1.0,    # No decay needed for 28-day window
    56: 0.7,    # 70% of impact happens in first 28 days (conservative default)
    90: 0.5,    # 50% of impact happens in first 28 days (conservative default)
}

# Phase 3: Material Impact Thresholds
#
# CALIBRATION REASONING:
# The original system was recommending actions with tiny effect sizes (0.43% discount improvement)
# that would generate minimal revenue and fail to justify $300+/month pricing. This was a critical
# problem because:
#
# 1. BUSINESS CREDIBILITY: Recommending 0.5% improvements makes the platform look amateur
# 2. PRICING JUSTIFICATION: Can't charge $300+/month for marginal optimizations
# 3. RESOURCE ALLOCATION: Teams waste time on insignificant changes
# 4. CUSTOMER SATISFACTION: Clients expect substantial, measurable improvements
# 5. COMPETITIVE DIFFERENTIATION: Need to deliver meaningful value vs basic analytics
#
# These thresholds should adapt to vertical and business maturity.
BASE_MATERIAL_IMPACT_THRESHOLDS = {
    'beauty': {
        'aov_change': 0.02,
        'frequency_change': 0.12,
        'retention_change': 0.025,
        'conversion_change': 0.08,
        'discount_change': 0.015,
        'revenue_impact': 3000,
        'audience_minimum': 80,
        'confidence_minimum': 0.30,
    },
    'supplements': {
        'aov_change': 0.025,
        'frequency_change': 0.10,
        'retention_change': 0.020,
        'conversion_change': 0.07,
        'discount_change': 0.012,
        'revenue_impact': 3200,
        'audience_minimum': 65,
        'confidence_minimum': 0.50,
    },
    'mixed': {
        'aov_change': 0.03,
        'frequency_change': 0.11,
        'retention_change': 0.022,
        'conversion_change': 0.075,
        'discount_change': 0.014,
        'revenue_impact': 3600,
        'audience_minimum': 75,
        'confidence_minimum': 0.52,
    },
}


def get_material_thresholds(vertical_mode: str, business_stage: str, business_metrics: dict | None, cfg: dict | None = None) -> dict:
    """Derive material impact thresholds tailored to vertical and business scale."""
    vertical = str(vertical_mode or 'mixed').lower()
    stage = str(business_stage or 'growth').lower()
    base = dict(BASE_MATERIAL_IMPACT_THRESHOLDS.get(vertical, BASE_MATERIAL_IMPACT_THRESHOLDS['mixed']))

    # Stage-based scaling for effect requirements (early-stage businesses should pass with smaller deltas).
    stage_scale = {'startup': 0.7, 'growth': 0.85, 'mature': 1.0, 'enterprise': 1.15}.get(stage, 1.0)
    for key in ['aov_change', 'frequency_change', 'retention_change', 'conversion_change', 'discount_change']:
        base[key] = max(0.01, base[key] * stage_scale)

    metrics = business_metrics or {}
    monthly_revenue = float(metrics.get('monthly_revenue') or 0.0)
    # Use MATERIALITY_PCT from config (default 2.5% per research recommendations)
    default_pct = (cfg or {}).get('MATERIALITY_PCT', 0.025)
    target_pct = {'beauty': default_pct, 'supplements': default_pct, 'mixed': default_pct}.get(vertical, default_pct)
    if monthly_revenue > 0:
        dynamic_floor = monthly_revenue * target_pct
        min_floor = 1200.0 if stage in {'startup', 'growth'} else base['revenue_impact'] * 0.75
        max_floor = base['revenue_impact'] * 1.4
        revenue_floor = max(min_floor, min(max_floor, dynamic_floor))
        if stage == 'enterprise':
            revenue_floor = max(revenue_floor, monthly_revenue * (target_pct + 0.01))
        base['revenue_impact'] = revenue_floor
    else:
        base['revenue_impact'] = base['revenue_impact'] * stage_scale

    # Audience minimum scales with observed customer base when available.
    customer_base = float(metrics.get('customer_base_recent') or 0.0)
    if customer_base <= 0 and monthly_revenue > 0:
        assumed_aov = float(metrics.get('aov') or 75.0)
        customer_base = monthly_revenue / max(assumed_aov * 1.5, 1e-6)
    if customer_base > 0:
        if stage in {'startup', 'growth'}:
            dynamic_audience = customer_base * 0.08
        else:
            dynamic_audience = customer_base * 0.10
        base['audience_minimum'] = int(max(50, min(base['audience_minimum'], dynamic_audience)))
        if stage == 'enterprise':
            base['audience_minimum'] = int(max(base['audience_minimum'], customer_base * 0.12))

    confidence = base.get('confidence_minimum', 0.55)
    if stage == 'startup':
        confidence = max(0.40, confidence - 0.15)
    elif stage == 'growth':
        confidence = max(0.48, confidence - 0.07)
    elif stage == 'enterprise':
        confidence = min(0.75, confidence + 0.08)
    base['confidence_minimum'] = confidence

    return base


def has_material_impact(action_type: str, effect_size: float = None, audience: int = 0,
                       projected_revenue: float = 0, confidence: float = 0,
                       thresholds: dict | None = None) -> tuple[bool, str]:
    """
    Phase 3: Validate that an action meets material impact thresholds.

    Args:
        action_type: Type of action (aov, frequency, retention, conversion, discount)
        effect_size: The measured effect size (as decimal, e.g., 0.05 for 5%)
        audience: Target audience size
        projected_revenue: Monthly revenue projection
        confidence: Pre-gate confidence estimate (0.0-1.0)

    Returns:
        (is_material, reason) - Boolean and explanatory string
    """
    thresholds = thresholds or BASE_MATERIAL_IMPACT_THRESHOLDS['mixed']

    # Check minimum audience size
    if audience < thresholds['audience_minimum']:
        return False, f"Audience too small: {audience} < {thresholds['audience_minimum']} minimum"

    # Check minimum confidence (when provided)
    if confidence is not None and confidence < thresholds['confidence_minimum']:
        return False, f"Confidence too low: {confidence:.1%} < {thresholds['confidence_minimum']:.1%} minimum"

    # Check minimum revenue impact
    if projected_revenue < thresholds['revenue_impact']:
        return False, f"Revenue impact too low: ${projected_revenue:,.0f} < ${thresholds['revenue_impact']:,.0f} minimum"

    # Check effect size thresholds by action type
    if effect_size is not None:
        threshold_map = {
            'aov': 'aov_change',
            'frequency': 'frequency_change',
            'retention': 'retention_change',
            'conversion': 'conversion_change',
            'discount': 'discount_change'
        }

        threshold_key = threshold_map.get(action_type)
        if threshold_key:
            min_threshold = thresholds[threshold_key]
            if abs(effect_size) < min_threshold:
                return False, f"Effect size too small: {effect_size:+.1%} < {min_threshold:+.1%} minimum for {action_type}"

    # Format effect size properly (handle None case)
    effect_str = f"{effect_size:+.1%}" if effect_size is not None else "N/A"
    return True, f"Material impact confirmed: {effect_str} effect, {audience:,} audience, ${projected_revenue:,.0f} revenue"

def get_action_type_from_play_id(play_id: str) -> str:
    """Map play_id to action type for effect size validation."""
    action_type_mapping = {
        'bestseller_amplify': 'aov',
        'routine_builder': 'aov',
        'aov_momentum': 'aov',
        'frequency_accelerator': 'frequency',
        'winback_21_45': 'frequency',
        'retention_mastery': 'retention',
        'journey_optimization': 'conversion',
        'category_expansion': 'conversion',
        'discount_hygiene': 'discount',
        'subscription_nudge': 'conversion'
    }
    return action_type_mapping.get(play_id, 'conversion')  # Default to conversion

# Phase 4: Market Saturation and Execution Capability Constants
# Market saturation thresholds (max % of customer base that can be effectively targeted)
MARKET_SATURATION_THRESHOLDS = {
    'frequency_accelerator': 0.15,    # 15% max can be meaningfully accelerated
    'aov_momentum': 0.25,             # 25% max suitable for AOV momentum
    'retention_mastery': 0.20,        # 20% max are typically at-risk for retention
    'journey_optimization': 0.35,     # 35% max have significant conversion gaps
    'category_expansion': 0.40,       # 40% max are single-category customers
    'bestseller_amplify': 0.30,       # 30% max suitable for upsells
    'routine_builder': 0.25,          # 25% max need routine completion
    'subscription_nudge': 0.20,       # 20% max subscription-ready
    'winback_21_45': 0.12,           # 12% max in winback window at any time
    'discount_hygiene': 1.0,          # Margin improvement applies universally
    'default': 0.30,
}

# Execution capability multipliers by business stage (beyond basic conversion scaling)
# These represent sophisticated campaign execution, not basic business operations
EXECUTION_CAPABILITY_MULTIPLIERS = {
    'startup': {
        # Limited marketing automation and personalization capabilities
        'frequency_accelerator': 0.7,    # Basic email automation
        'aov_momentum': 0.8,              # Simple upsell processes
        'retention_mastery': 0.6,         # Basic retention tools
        'journey_optimization': 0.5,      # Limited funnel optimization
        'category_expansion': 0.7,        # Basic cross-sell capabilities
        'bestseller_amplify': 0.8,        # Simple product promotion
        'routine_builder': 0.75,          # Basic bundling logic
        'subscription_nudge': 0.7,        # Simple subscription flows
        'winback_21_45': 0.8,            # Basic email campaigns
        'discount_hygiene': 1.0,          # Pricing changes don't require sophistication
    },
    'growth': {
        # Good automation and segmentation capabilities
        'frequency_accelerator': 0.9,     # Decent automation
        'aov_momentum': 0.95,             # Good upsell processes
        'retention_mastery': 0.8,         # Solid retention infrastructure
        'journey_optimization': 0.75,     # Good funnel capabilities
        'category_expansion': 0.85,       # Solid cross-sell processes
        'bestseller_amplify': 0.9,        # Good promotion capabilities
        'routine_builder': 0.85,          # Solid bundling logic
        'subscription_nudge': 0.85,       # Good subscription flows
        'winback_21_45': 0.9,            # Good campaign automation
        'discount_hygiene': 1.0,          # Pricing sophistication not required
    },
    'mature': {
        # Baseline sophisticated operations (1.0x baseline)
        # No additional adjustments needed - already handled by upstream scaling
    },
    'enterprise': {
        # Advanced automation, AI-powered personalization, omnichannel execution
        'frequency_accelerator': 1.2,     # Advanced lifecycle automation
        'aov_momentum': 1.15,             # AI-powered upsell engines
        'retention_mastery': 1.3,         # Enterprise retention platforms
        'journey_optimization': 1.25,     # Advanced funnel optimization
        'category_expansion': 1.2,        # AI-powered cross-sell
        'bestseller_amplify': 1.15,       # Dynamic promotion optimization
        'routine_builder': 1.1,           # Smart bundling algorithms
        'subscription_nudge': 1.2,        # Advanced subscription intelligence
        'winback_21_45': 1.1,            # Predictive campaign optimization
        'discount_hygiene': 1.0,          # Pricing changes remain straightforward
    }
}

def calculate_28d_revenue(audience: int, play_id: str, aov: float, source_window: int = 28, effect_size: float | None = None, vertical_mode: str = "mixed", business_stage: str = "growth", business_metrics: dict | None = None) -> dict:
    """Calculate 28-day revenue projections (base and optimistic scenarios)."""
    if audience <= 0 or aov <= 0:
        debug_log('revenue', f"[{play_id}] audience={audience}, aov={aov} → $0")
        return {"base": 0.0, "optimistic": 0.0, "details": {}}

    vertical = str(vertical_mode).lower()
    base_rates = get_conversion_rates(vertical)
    base_rate = base_rates.get(play_id, base_rates.get('default', 0.05))

    conversion_multiplier = compute_conversion_multiplier(play_id, business_stage, business_metrics, vertical)
    conversion_rate = base_rate * conversion_multiplier

    metrics = business_metrics or {}
    debug_log(
        'revenue_detail',
        f"[{play_id}] audience={audience}, base_rate={base_rate:.2f}, multiplier={conversion_multiplier:.2f}, conversion={conversion_rate:.1%}, aov=${aov:.2f}"
    )

    bundle_scale = {
        'startup': 0.6,
        'growth': 0.8,
        'mature': 1.0,
        'enterprise': 1.1,
    }.get(str(business_stage).lower(), 0.8)

    effect_params = get_effect_params(play_id, vertical, business_stage, business_metrics)
    base_revenue = 0.0
    opt_revenue = 0.0

    if play_id == 'bestseller_amplify':
        base_bundle = effect_params.get('bundle_value') or (45.0 if vertical == 'beauty' else 35.0) * bundle_scale
        base_bundle = min(base_bundle, aov * 0.8)
        opt_bundle = effect_params.get('bundle_value_opt', base_bundle * 1.12)
        opt_bundle = min(opt_bundle, aov)
        affected_orders = audience * conversion_rate
        base_revenue = affected_orders * base_bundle
        opt_revenue = affected_orders * opt_bundle
        debug_log('revenue_detail', f"[{play_id}] bundle_value=${base_bundle:.2f} (opt=${opt_bundle:.2f}), affected_orders={affected_orders:.1f}")

    elif play_id == 'discount_hygiene':
        monthly_order_frequency = 1.8 if vertical == 'beauty' else 1.2
        monthly_orders = audience * monthly_order_frequency
        base_margin_rate = effect_params.get('margin_recovery_rate', abs(effect_size) if effect_size else 0.005)
        opt_margin_rate = effect_params.get('margin_recovery_rate_opt', base_margin_rate * 1.4)
        base_revenue = monthly_orders * aov * base_margin_rate * conversion_multiplier
        opt_revenue = monthly_orders * aov * opt_margin_rate * conversion_multiplier

    elif play_id == 'routine_builder':
        base_bundle = effect_params.get('bundle_value') or (85.0 if vertical == 'beauty' else 65.0) * bundle_scale
        base_bundle = min(base_bundle, aov * 1.3)
        opt_bundle = effect_params.get('bundle_value_opt', base_bundle * 1.12)
        opt_bundle = min(opt_bundle, aov * 1.5)
        converted = audience * conversion_rate
        base_revenue = converted * base_bundle
        opt_revenue = converted * opt_bundle

    elif play_id == 'subscription_nudge':
        first_month_multiplier = effect_params.get('subscription_multiplier', 1.15)
        first_month_opt = effect_params.get('subscription_multiplier_opt', first_month_multiplier * 1.1)
        converted = audience * conversion_rate
        base_revenue = converted * aov * first_month_multiplier
        opt_revenue = converted * aov * first_month_opt

    elif play_id == 'frequency_accelerator':
        current_frequency = metrics.get('repeat_rate', 0.3) + 0.5
        freq_lift = effect_params.get('frequency_lift', 0.20 if vertical == 'beauty' else 0.16)
        freq_lift_opt = effect_params.get('frequency_lift_opt', freq_lift * 1.35)
        orders_base = audience * conversion_rate * current_frequency * freq_lift
        orders_opt = audience * conversion_rate * current_frequency * freq_lift_opt
        base_revenue = orders_base * aov
        opt_revenue = orders_opt * aov

    elif play_id == 'aov_momentum':
        order_frequency = 1.2
        aov_growth_rate = metrics.get('aov_growth', 0.02)
        growth_accel = effect_params.get('growth_acceleration', 1.5)
        growth_accel_opt = effect_params.get('growth_acceleration_opt', growth_accel * 1.2)
        aov_improvement = aov * aov_growth_rate * growth_accel
        aov_improvement_opt = aov * aov_growth_rate * growth_accel_opt
        monthly_orders = audience * conversion_rate * order_frequency
        base_revenue = monthly_orders * aov_improvement
        opt_revenue = monthly_orders * aov_improvement_opt

    elif play_id == 'retention_mastery':
        churn_rate = effect_params.get('churn_reduction', 0.07 if vertical == 'beauty' else 0.06)
        churn_rate_opt = effect_params.get('churn_reduction_opt', churn_rate * 1.35)
        customer_ltv = aov * 4.5
        retained_base = audience * conversion_rate * churn_rate
        retained_opt = audience * conversion_rate * churn_rate_opt
        base_revenue = retained_base * customer_ltv * 0.25
        opt_revenue = retained_opt * customer_ltv * 0.35

    elif play_id == 'journey_optimization':
        improvement = effect_params.get('conversion_improvement', 0.30 if vertical == 'beauty' else 0.25)
        improvement_opt = effect_params.get('conversion_improvement_opt', improvement * 1.35)
        conversions_base = audience * conversion_rate * improvement
        conversions_opt = audience * conversion_rate * improvement_opt
        base_revenue = conversions_base * aov
        opt_revenue = conversions_opt * aov

    elif play_id == 'category_expansion':
        expansion_rate = effect_params.get('expansion_rate', 0.40 if vertical == 'beauty' else 0.32)
        expansion_rate_opt = effect_params.get('expansion_rate_opt', expansion_rate * 1.35)
        cross_aov = aov * 0.75
        base_revenue = audience * conversion_rate * expansion_rate * cross_aov
        opt_revenue = audience * conversion_rate * expansion_rate_opt * cross_aov

    elif play_id == 'winback_21_45':
        orders_per_customer = effect_params.get('orders_per_customer', 1.3)
        orders_per_customer_opt = effect_params.get('orders_per_customer_opt', orders_per_customer * 1.15)
        converted = audience * conversion_rate
        base_revenue = converted * orders_per_customer * aov
        opt_revenue = converted * orders_per_customer_opt * aov

    else:
        converted_customers = audience * conversion_rate
        orders_per_customer = 1.3
        base_revenue = converted_customers * orders_per_customer * aov
        opt_revenue = base_revenue * 1.2

    incrementality_factors = get_incrementality_factors(vertical, business_stage)
    base_inc = adjust_incrementality(play_id, incrementality_factors.get(play_id, incrementality_factors.get('default', 0.75)), business_metrics, optimistic=False)
    opt_inc = adjust_incrementality(play_id, incrementality_factors.get(play_id, incrementality_factors.get('default', 0.75)), business_metrics, optimistic=True)

    base_incremental = base_revenue * base_inc
    opt_incremental = opt_revenue * opt_inc
    debug_log('revenue_detail', f"[{play_id}] base=${base_revenue:.0f}, inc={base_inc:.0%} → ${base_incremental:.0f} | opt=${opt_revenue:.0f}, inc_opt={opt_inc:.0%}")

    decay_base = 1.0 if play_id in {'discount_hygiene', 'subscription_nudge'} else compute_decay_multiplier(play_id, source_window, business_metrics, optimistic=False)
    decay_opt = 1.0 if play_id in {'discount_hygiene', 'subscription_nudge'} else compute_decay_multiplier(play_id, source_window, business_metrics, optimistic=True)

    base_after_decay = base_incremental * decay_base
    opt_after_decay = opt_incremental * decay_opt

    final_base = apply_saturation_penalty(play_id, audience, aov, base_after_decay, business_metrics, optimistic=False)
    final_opt = apply_saturation_penalty(play_id, audience, aov, opt_after_decay, business_metrics, optimistic=True)

    final_opt = max(final_base, final_opt)
    debug_log('revenue', f"[{play_id}] base=${final_base:.0f}, optimistic=${final_opt:.0f}, audience={audience}, conversion={conversion_rate:.1%}")

    details = {
        'conversion_rate': conversion_rate,
        'base_pre_incrementality': base_revenue,
        'optimistic_pre_incrementality': opt_revenue,
        'incrementality_base': base_inc,
        'incrementality_opt': opt_inc,
        'decay_base': decay_base,
        'decay_opt': decay_opt,
    }

    return {
        'base': float(final_base),
        'optimistic': float(final_opt),
        'details': details,
    }



def _compute_multiwindow_candidates(
    g: pd.DataFrame, 
    aligned_dict: Dict[str, Any], 
    cfg: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generate candidates using multi-window analysis with vertical-aware weighting.
    
    Args:
        g: Transaction dataframe
        aligned_dict: Dict containing L7, L28, L56, L90 window data
        cfg: Configuration dict with VERTICAL_MODE
    
    Returns:
        List of weighted candidates from all available windows
    """
    vertical_mode = get_vertical_mode()
    window_weights = get_window_weights(vertical_mode)

    # Extract business performance metrics for adaptive conversion scaling
    business_metrics = extract_business_metrics(aligned_dict)

    all_candidates = []
    available_windows = []
    
    # Generate candidates from each available window
    for window_key, weight in window_weights.items():
        if window_key in aligned_dict:
            # Skip windows with zero weight (e.g. L7 removed from analysis)
            # NOTE: This can be reverted by removing this check if L7 needs to be re-enabled
            if weight == 0.0:
                debug_log('multiwindow_detail', f"{window_key}: skipped (weight=0.0)")
                continue
            try:
                # Create properly formatted aligned data for this window
                window_data = aligned_dict[window_key]
                window_days = int(window_key[1:])  # Extract days from L7, L28, etc.
                
                debug_log('multiwindow', f"{window_key}: orders={window_data.get('orders', 0)}, net_sales=${window_data.get('net_sales', 0):.0f}, weight={weight:.2f}")
                
                # Convert multi-window format to single-window format expected by _compute_candidates
                single_window_aligned = {
                    'window_days': window_days,
                    'orders': window_data.get('orders', 0),
                    'net_sales': window_data.get('net_sales', 0.0),
                    'aov': window_data.get('aov', 0.0),
                    'discount_rate': window_data.get('discount_rate', 0.0),
                    'repeat_rate_within_window': window_data.get('repeat_rate_within_window', 0.0),
                    'returning_customer_share': window_data.get('returning_customer_share', 0.0),
                    'new_customer_rate': window_data.get('new_customer_rate', 0.0),
                    # Prior period data
                    'prior_orders': window_data.get('prior', {}).get('orders', 0),
                    'prior_net_sales': window_data.get('prior', {}).get('net_sales', 0.0),
                    'prior_aov': window_data.get('prior', {}).get('aov', 0.0),
                    'prior_discount_rate': window_data.get('prior', {}).get('discount_rate', 0.0),
                    'prior_repeat_rate': window_data.get('prior', {}).get('repeat_rate_within_window', 0.0),
                    # Significance data
                    'p': window_data.get('p', {}),
                    'sig': window_data.get('sig', {}),
                    'delta': window_data.get('delta', {}),
                    'meta': window_data.get('meta', {}),
                }
                
                # Generate candidates using single-window logic
                candidates = _compute_candidates(g, single_window_aligned, cfg)
                
                # Enhance with cohort analysis (if enabled)
                candidates = _enhance_candidates_with_cohorts(g, candidates, cfg)
                
                for c in candidates:
                    # Add window metadata
                    c['source_window'] = window_key
                    c['window_weight'] = weight
                    c['base_score'] = c.get('score', 0.0)
                    
                    # Apply seasonal adjustment if anchor date available
                    if 'anchor' in aligned_dict:
                        vertical_mode = get_vertical_mode()
                        subvertical = get_subvertical()
                        seasonal_mult, season_name = get_seasonal_multiplier(aligned_dict['anchor'], vertical_mode, subvertical)
                        c['seasonal_multiplier'] = seasonal_mult
                        c['seasonal_period'] = season_name
                        c['score'] = c['base_score'] * seasonal_mult
                    else:
                        c['score'] = c['base_score']

                    # Store weight for confidence calculation, not score penalty
                    c['signal_confidence'] = weight
                
                all_candidates.extend(candidates)
                available_windows.append(window_key)
                
            except Exception as e:
                # If window analysis fails, continue with other windows
                debug_log('multiwindow', f"Failed to analyze window {window_key}: {e}")
                import traceback
                if 'multiwindow_detail' in DEBUG_CATEGORIES:
                    traceback.print_exc()
                continue
    
    # M4b T4b.2: route the multi-window merge through
    # ``combine_multiwindow_statistics`` for measured/directional plays
    # (replaces the legacy min-p window-shopping in
    # ``_merge_multiwindow_candidates``). Targeting candidates skip
    # combination entirely. The reroute is gated on BOTH M4b flags being
    # on so the legacy path is preserved when either flag is off.
    _stats_nan_flag = bool(cfg.get("STATS_NAN_FOR_HARDCODED", False))
    _evidence_class_flag = bool(cfg.get("EVIDENCE_CLASS_ENFORCED", False))
    if _stats_nan_flag and _evidence_class_flag:
        merged_candidates = _combine_multiwindow_candidates_v2(all_candidates)
    else:
        merged_candidates = _merge_multiwindow_candidates(all_candidates)

    # Enhance template actions with real multi-window statistics
    if cfg.get('ENABLE_ENHANCED_STATISTICS', True):
        enhanced_candidates = []

        for candidate in merged_candidates:
            # Check if we should enhance this candidate
            enhanced_candidate = enhance_template_action_with_real_stats(
                candidate, g, aligned_dict, window_weights
            )
            enhanced_candidates.append(enhanced_candidate)

        debug_log('stats', f"Enhanced {len([c for c in enhanced_candidates if c.get('statistical_method') == 'enhanced_multiwindow'])} template actions with real statistics")

        return enhanced_candidates

    return merged_candidates


def _merge_multiwindow_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge candidates with same play_id and metric from different windows.
    Uses weighted average for scores and combines evidence.
    """
    merged = {}
    
    for c in candidates:
        key = (c.get('play_id'), c.get('metric'))
        
        if key not in merged:
            merged[key] = c.copy()
            merged[key]['contributing_windows'] = [c['source_window']]
            merged[key]['window_scores'] = {c['source_window']: c.get('p', 1.0)}
        else:
            # Combine scores by addition (already weighted)
            existing = merged[key]
            existing['score'] += c['score']
            existing['contributing_windows'].append(c['source_window'])
            existing['window_scores'][c['source_window']] = c.get('p', 1.0)

            # Update source_window to the one with strongest signal (lowest p-value).
            # M4a T4a.2: NaN-safe min selection. If existing.p is NaN and new.p is
            # finite, prefer the finite value; if both are NaN both miss; if new is
            # NaN, keep existing. Comparisons with NaN evaluate False, so we promote
            # a finite value over a NaN deterministically.
            current_p = existing.get('p', 1.0)
            new_p = c.get('p', 1.0)
            current_is_nan = (current_p is None) or (isinstance(current_p, float) and current_p != current_p)
            new_is_nan = (new_p is None) or (isinstance(new_p, float) and new_p != new_p)
            replace = False
            if current_is_nan and not new_is_nan:
                replace = True
            elif (not new_is_nan) and (not current_is_nan) and (new_p < current_p):
                replace = True
            if replace:
                # This window has a stronger signal, make it the source_window
                existing['source_window'] = c['source_window']
                existing['window_weight'] = c.get('window_weight', existing.get('window_weight'))
                existing['p'] = new_p
                existing['q'] = c.get('q', existing.get('q'))
                existing['n'] = c.get('n', existing.get('n'))
                existing['effect_abs'] = c.get('effect_abs', existing.get('effect_abs'))

            # Keep the best confidence/significance metrics across windows
            for key_metric in ['confidence', 'p_value', 'effect_size']:
                if key_metric in c and key_metric in existing:
                    if key_metric == 'p_value':
                        # Lower p-value is better
                        existing[key_metric] = min(existing[key_metric], c[key_metric])
                    else:
                        # Higher confidence/effect is better
                        existing[key_metric] = max(existing[key_metric], c[key_metric])

    return list(merged.values())


def _combine_multiwindow_candidates_v2(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """M4b T4b.2: route per-window candidates through the proper combiner.

    Replaces ``_merge_multiwindow_candidates`` for the V2 path (both M4b
    flags on). Behavior:

    * **Measured / directional** candidates with multiple per-window rows
      are combined using ``stats.combine_multiwindow_statistics`` (inverse
      variance weighted effect, Fisher's combined p, propagated CI). The
      old min-p window shopping is bypassed entirely.
    * **Targeting** candidates skip combination. We collapse the per-window
      rows into a single dict by keeping the first window's data and
      recording ``contributing_windows`` for traceability. No measurement
      is produced; the EngineRun mapper drops the measurement block when
      ``evidence_class == "targeting"``.
    * **consistency_across_windows** is computed (pre-combination
      sign-agreement count, |t|>1) and stamped on the merged candidate as
      a robustness signal. It is NOT used to upgrade evidence class and is
      NOT multiplied into confidence.

    The function takes a flat list of per-window candidate dicts (one per
    window per play, as built by ``_compute_multiwindow_candidates``) and
    returns a list of merged candidates (one per ``(play_id, metric)``
    key). Candidates whose evidence_class is missing default to the
    measured/directional combiner path; the targeting reclassification
    elsewhere in ``_compute_candidates`` ensures the right value is on
    each candidate before this function runs.
    """
    from .evidence import compute_consistency_across_windows
    from .stats import combine_multiwindow_statistics

    merged: Dict[Any, Dict[str, Any]] = {}
    groups: Dict[Any, List[Dict[str, Any]]] = {}

    # Group by (play_id, metric), preserving insertion order.
    for c in candidates:
        key = (c.get('play_id'), c.get('metric'))
        groups.setdefault(key, []).append(c)

    for key, window_cands in groups.items():
        if not window_cands:
            continue

        # Seed merged candidate from the first window. We will overwrite
        # statistical fields below for measured/directional plays.
        seed = window_cands[0].copy()
        contributing = [c['source_window'] for c in window_cands if c.get('source_window')]
        seed['contributing_windows'] = list(contributing)
        # Preserve ``window_scores`` for downstream debug; carry per-window
        # p-values rather than resetting to 1.0.
        seed['window_scores'] = {
            c.get('source_window'): c.get('p', 1.0)
            for c in window_cands
            if c.get('source_window') is not None
        }
        # Sum scores in line with the legacy merger (already-weighted).
        seed['score'] = sum(float(c.get('score', 0.0) or 0.0) for c in window_cands)

        evidence_class = str(seed.get('evidence_class') or '').lower()

        if evidence_class == 'targeting':
            # T4b.2: targeting plays SKIP combination. We keep the seed
            # values but explicitly null out the measurement-style fields
            # — the engine_run mapper drops the measurement block for
            # targeting plays anyway, but we also want the legacy
            # ``actions_log.json`` shape to stop carrying a fake combined
            # p/effect/CI for these plays.
            seed['p'] = float('nan')
            seed['q'] = float('nan')
            seed['effect_abs'] = float('nan')
            seed['ci_low'] = float('nan')
            seed['ci_high'] = float('nan')
            seed['statistical_method'] = 'targeting_no_combination'
            # consistency_across_windows is not meaningful for a
            # targeting play (no signed combiner effect to agree with);
            # set to None so the renderer / EngineRun mapper sees absence
            # rather than a misleading 0.
            seed['consistency_across_windows'] = None
            merged[key] = seed
            continue

        # Measured / directional / unknown → route through the combiner.
        window_results: List[Dict[str, Any]] = []
        for c in window_cands:
            effect = c.get('effect_abs')
            p_val = c.get('p')
            n = c.get('n')
            try:
                effect_f = float(effect) if effect is not None else float('nan')
            except (TypeError, ValueError):
                effect_f = float('nan')
            try:
                p_f = float(p_val) if p_val is not None else float('nan')
            except (TypeError, ValueError):
                p_f = float('nan')
            try:
                n_i = int(n) if n is not None else 0
            except (TypeError, ValueError):
                n_i = 0

            # Skip windows whose effect or p is NaN — they carry no
            # statistical content. (Hardcoded plays that escaped the M4a
            # NaN gate will simply not contribute, leaving the combiner
            # to operate on whatever real per-window stats are present.)
            if effect_f != effect_f or p_f != p_f:
                continue

            # Derive a per-window standard error from the CI when
            # available; fall back to the effect / |z| approximation
            # using the p-value. ``combine_multiwindow_statistics`` is
            # the authoritative combiner; we only need a defensible SE
            # to feed it (matches the same heuristic the existing
            # ``calculate_*_stats_single_window`` helpers use elsewhere).
            ci_lo = c.get('ci_low')
            ci_hi = c.get('ci_high')
            std_error: float
            if (
                ci_lo is not None and ci_hi is not None
                and (isinstance(ci_lo, (int, float)) and isinstance(ci_hi, (int, float)))
                and not (ci_lo != ci_lo or ci_hi != ci_hi)
                and ci_hi > ci_lo
            ):
                std_error = float(ci_hi - ci_lo) / (2.0 * 1.959963984540054)
            else:
                # Approximate SE from p-value via the inverse-normal
                # mapping. Conservative if the test was something other
                # than a two-sided z; for the V2 path the goal is "use
                # the combiner instead of min-p shopping", not to
                # re-derive every per-window test.
                from math import sqrt, log
                if p_f <= 0.0 or p_f >= 1.0:
                    std_error = float('inf')
                else:
                    # Two-sided z magnitude approximation:
                    #   p = 2 * (1 - Phi(|z|))  =>  |z| ~= sqrt(-2 ln(p/2))
                    try:
                        z_abs = sqrt(max(-2.0 * log(p_f / 2.0), 0.0))
                    except Exception:
                        z_abs = 0.0
                    if z_abs <= 0.0 or effect_f == 0.0:
                        std_error = float('inf')
                    else:
                        std_error = abs(effect_f) / z_abs

            window_results.append({
                'window': c.get('source_window'),
                'effect_abs': effect_f,
                'p_value': p_f,
                'std_error': std_error,
                'n': n_i,
            })

        if not window_results:
            # Nothing combinable. Keep seed with NaN stats; do not
            # silently use min-p selection.
            seed['p'] = float('nan')
            seed['effect_abs'] = float('nan')
            seed['ci_low'] = float('nan')
            seed['ci_high'] = float('nan')
            seed['statistical_method'] = 'combiner_no_valid_windows'
            seed['consistency_across_windows'] = 0
            merged[key] = seed
            continue

        # Use vertical-aware business weights (matches the rest of the
        # multi-window pipeline). Pulling the weights here keeps the
        # function side-effect free.
        from .utils import get_window_weights as _get_window_weights
        biz_weights = _get_window_weights(get_vertical_mode())

        combined = combine_multiwindow_statistics(window_results, biz_weights)

        # B-6: tag the (play_id, metric) pair with the combiner trace
        # so the universality test can verify every measured PlayCard
        # flowed through this branch (vs the legacy min-p merge in
        # ``_merge_multiwindow_candidates``). No-op in production -- the
        # trace is dormant outside an active test context.
        try:
            from .stats import record_combine_multiwindow_call as _rec
            _rec(seed.get('play_id'), seed.get('metric'))
        except Exception:
            pass

        seed['p'] = float(combined.p_value)
        seed['effect_abs'] = float(combined.effect_abs)
        seed['ci_low'] = float(combined.ci_low)
        seed['ci_high'] = float(combined.ci_high)
        seed['n'] = int(combined.n_total) if combined.n_total else int(seed.get('n', 0) or 0)
        seed['statistical_method'] = 'combine_multiwindow_statistics'
        seed['contributing_windows'] = list(combined.contributing_windows)
        seed['window_effects'] = dict(combined.window_effects)

        # T4b.2 robustness signal: pre-combination sign-agreement count.
        seed['consistency_across_windows'] = compute_consistency_across_windows(
            window_results, combined.effect_abs
        )

        # Pick a representative ``source_window`` for downstream code that
        # still keys on a single window (e.g. legacy debug log lines).
        # Use the first contributing window deterministically; this is
        # NOT a min-p selection.
        if seed['contributing_windows']:
            seed['source_window'] = seed['contributing_windows'][0]

        merged[key] = seed

    return list(merged.values())


def _load_actions_log(receipts_dir: str) -> list[dict]:
    """Load action log for cooldown tracking."""
    p = Path(receipts_dir) / "actions_log.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


# Primary implementation for action selection (inventory-aware)
def _select_actions_impl(
    g,
    aligned,
    cfg,
    playbooks_path: str,
    receipts_dir: str,
    policy_path: str | None = None,
    inventory_metrics: pd.DataFrame | None = None,
) -> Dict[str, Any]:
    """Select top actions, backlog, and pilot based on candidates and policy.

    This consolidates gating, scoring, variant expansion, cooldowns, inventory-awareness,
    overlap adjustments, and interaction effects into a single implementation.
    """
    # Load playbooks and build quick lookup by id
    try:
        plays_list = load_playbooks(playbooks_path)
    except Exception:
        plays_list = []
    plays: Dict[str, Any] = {str(p.get("id")): p for p in plays_list if isinstance(p, dict)}

    # Compute base candidates from recent performance signals
    # Check if aligned data has multi-window structure (L7, L28, L56, L90 keys)
    window_keys = ['L7', 'L28', 'L56', 'L90']
    has_multiwindow = any(key in aligned for key in window_keys)
    
    # Check if we're in forced single-window mode
    force_single_window = cfg.get('_FORCE_SINGLE_WINDOW', False)
    
    if not force_single_window and has_multiwindow and cfg.get('ENABLE_MULTIWINDOW_SCORING', True):
        # Use multi-window analysis with vertical-aware weighting
        debug_log('multiwindow', f"Using multi-window analysis with {[k for k in window_keys if k in aligned]}")
        debug_log('multiwindow', f"Vertical mode: {get_vertical_mode()}")
        base_cands: List[Dict[str, Any]] = _compute_multiwindow_candidates(g, aligned, cfg)
        debug_log('multiwindow', f"Generated {len(base_cands)} candidates from multi-window analysis")
        # Show first few candidates for debugging
        for i, cand in enumerate(base_cands[:3]):
            debug_log(
                'multiwindow_detail',
                f"Candidate {i+1}: {cand.get('play_id')} confidence={cand.get('confidence_score', 'N/A')} windows={cand.get('contributing_windows', [cand.get('source_window', 'unknown')])}"
            )
    else:
        # Fall back to traditional single-window analysis  
        debug_log('multiwindow', f"Using single-window analysis (multiwindow={has_multiwindow}, enabled={cfg.get('ENABLE_MULTIWINDOW_SCORING', True)})")
        if 'window_days' in aligned:
            debug_log('multiwindow_detail', f"Single-window data: {aligned.get('window_days')} days, {aligned.get('orders', 'N/A')} orders")
        base_cands: List[Dict[str, Any]] = _compute_candidates(g, aligned, cfg)
        debug_log('multiwindow', f"Generated {len(base_cands)} candidates from single-window analysis")
        
        # Enhance candidates with cohort-based significance pooling
        base_cands = _enhance_candidates_with_cohorts(g, base_cands, cfg)

    # LTV signal (non-gating): store-level and top-decile for receipts and tie-breakers
    ltv_info = compute_repeat_curve(g, horizon_days=[60, 90]) if g is not None else {"store": {}, "per_customer": []}
    store_ltv90 = float(((ltv_info or {}).get("store", {}) or {}).get(90, {}).get("ltv", 0.0) or 0.0)
    try:
        arr = np.array([float(x.get("ltv90", 0.0) or 0.0) for x in (ltv_info.get("per_customer", []) or [])], dtype=float)
        ltv90_p90 = float(np.quantile(arr, 0.9)) if arr.size > 0 else 0.0
    except Exception:
        ltv90_p90 = 0.0

    # FDR adjust (q-values) across base candidates only
    pvals = [c.get("p", np.nan) for c in base_cands]
    if any([not np.isnan(p) for p in pvals]):
        qvals, _ = benjamini_hochberg([p if not np.isnan(p) else 1.0 for p in pvals], cfg["FDR_ALPHA"])
        for i, c in enumerate(base_cands):
            c["q"] = qvals[i]

    # Gate + score + attach playbook metadata
    final: List[Dict[str, Any]] = []
    for c in base_cands:
        meta = plays.get(c.get("play_id"), {}) or {}
        c = c.copy()
        c["category"] = meta.get("category", "general")
        c["title"] = meta.get("title", c.get("play_id"))
        for k in [
            "do_this","targeting","channels","cadence","offer","copy_snippets","assets",
            "how_to_launch","success_criteria","risks_mitigations","owner_suggested",
            "time_to_set_up_minutes","holdout_plan"
        ]:
            if k in meta:
                c[k] = meta.get(k)

        cand = _gate_and_score(c, cfg)

        # Confidence label + expected range
        if len(cand["failed"]) == 0:
            cand["confidence_label"] = "High"
        elif ("min_n" in cand["passed"]) and ("significance" in cand["failed"]) and ("effect_floor" not in cand["failed"]) and ("financial_floor" not in cand["failed"]):
            cand["confidence_label"] = "Medium"
        else:
            cand["confidence_label"] = "Low"

        expv = float(cand.get("expected_$") or 0.0)
        expv_opt = float(cand.get("expected_$_optimistic") or expv * 1.35)
        cand["expected_range"] = [round(expv * 0.7, 2), round(max(expv, expv_opt), 2)]

        # attach LTV estimates (non-gating)
        cand["audience_ltv90"] = store_ltv90
        cand["ltv90_top_decile"] = ltv90_p90
        final.append(cand)

    # Variant expansion + policy eligibility + cooldown/novelty + inventory-aware adjustments
    try:
        from .policy import load_policy as _lp, is_eligible as _ie  # optional dependency
        _load_pol = _lp
        _is_el = _ie
    except Exception:
        def _load_pol(_=None):
            return {"allow_free_shipping": True, "max_discount_pct": 15, "channel_caps": {"email_per_week": 2, "sms_per_week": 1}}
        def _is_el(expr, policy):
            return True

    # Anchor date for week-aware cooldown
    anchor_dt = None
    try:
        val = aligned.get("anchor")
        if val:
            anchor_dt = val.date() if hasattr(val, "date") else datetime.date.fromisoformat(str(val)[:10])
    except Exception:
        anchor_dt = None

    policy = _load_pol(policy_path)
    log = _load_actions_log(receipts_dir)

    variant_cands: List[Dict[str, Any]] = []

    # Inventory helpers (soft enforcement by default)
    inv_df = None
    try:
        inv_df = inventory_metrics.copy() if inventory_metrics is not None else None
    except Exception:
        inv_df = None

    def _inv_summary():
        if inv_df is None or inv_df.empty:
            return None
        tmp = {}
        try:
            tmp['in_stock_ratio14'] = float((inv_df['cover_days'] >= 14).mean()) if 'cover_days' in inv_df.columns else 1.0
            tmp['cover_min'] = float(inv_df['cover_days'].min()) if 'cover_days' in inv_df.columns else float('inf')
            tmp['cover_p25'] = float(inv_df['cover_days'].quantile(0.25)) if 'cover_days' in inv_df.columns else float('inf')
            tf = inv_df.get('trust_factor')
            tmp['trust_mean'] = float(tf.mean()) if tf is not None else 1.0
        except Exception:
            tmp = None
        return tmp

    inv_sum = _inv_summary()
    inv_mode = str(cfg.get('INVENTORY_ENFORCEMENT_MODE','soft') or 'soft').lower()
    cover_map = cfg.get('INVENTORY_MIN_COVER_DAYS') or {}
    default_cover = int(float((cover_map.get('default') or 21))) if cover_map else 21

    def _targeted_skus_for_play(vc: Dict[str, Any]) -> list[str]:
        try:
            play_id = str(vc.get('play_id') or '').lower()
            if inv_df is None or inv_df.empty:
                return []
            if 'lineitem_any' not in g.columns and 'SKU' not in g.columns:
                return []
            maxd = pd.to_datetime(g["Created at"]).max()
            start = maxd - pd.Timedelta(days=int(aligned.get("window_days") or 28) - 1)
            gg = g[g['Created at'] >= start].copy()
            def top_n_from(col: str, n: int = 3):
                ser = gg[col].astype(str)
                units = pd.to_numeric(gg.get('Lineitem quantity', pd.Series(1, index=gg.index)), errors='coerce').fillna(1)
                cnt = units.groupby(ser).sum().sort_values(ascending=False)
                return [str(x) for x in cnt.head(n).index.tolist()]
            if 'bestseller' in play_id or 'amplify' in play_id:
                # Prefer g_items for robust per-product targeting
                try:
                    gi = build_g_items(gg)
                    if gi is not None and not gi.empty:
                        rank = gi.groupby('product_key')['orders_product'].sum().sort_values(ascending=False)
                        return [str(x) for x in rank.head(3).index.tolist()]
                except Exception:
                    pass
                # Choose a column that exists in gg (orders frame)
                if 'sku' in gg.columns:
                    return top_n_from('sku', 3)
                return top_n_from('lineitem_any', 3)
            if 'subscription_nudge' in play_id:
                start90 = maxd - pd.Timedelta(days=90)
                ww = g[g['Created at'] >= start90].copy()
                try:
                    rep = build_g_items(ww)
                    if rep is not None and not rep.empty:
                        use_col = 'product_key_base' if 'product_key_base' in rep.columns and bool(cfg.get('FEATURES_PRODUCT_NORMALIZATION', False)) else 'product_key'
                        subs = rep[rep['orders_product'] >= 3][use_col].astype(str).unique().tolist()
                        return subs[:5]
                except Exception:
                    pass
                if 'lineitem_any' in ww.columns:
                    rep = (ww.groupby(['customer_id','lineitem_any'])['Name']
                             .nunique().reset_index(name='orders_product'))
                    subs = rep[rep['orders_product'] >= 3]['lineitem_any'].astype(str).unique().tolist()
                    return subs[:5]
                return []
            if 'empty_bottle' in play_id:
                # G-2: vertical-dispatched parser. The Beauty / mixed
                # regex is preserved verbatim from the pre-G-2 inline
                # version (M0 byte-identical contract). Supplements
                # returns None until Sprint 4 G-3 ships a unit-coherent
                # count / lb / mg / serving-per-container parser; in
                # that case the play is simultaneously filtered out
                # upstream by ``play_registry.empty_bottle.vertical_applicable``,
                # so this branch returns an empty SKU list as a defensive
                # fallback only.
                from .replenishment_parser import (
                    get_size_regex as _get_size_regex,
                    get_case_insensitive as _get_case_ins,
                )

                _vertical = (
                    cfg.get('VERTICAL_MODE') or cfg.get('VERTICAL') or 'beauty'
                )
                _rx = _get_size_regex(_vertical)
                if not _rx:
                    return []
                _names = gg.get('lineitem_any', pd.Series([], dtype=str)).astype(str)
                if _get_case_ins(_vertical):
                    _names = _names.str.lower()
                mask = _names.str.contains(_rx, regex=True, na=False)
                return list(gg.loc[mask, 'lineitem_any'].astype(str).value_counts().head(5).index)
        except Exception:
            return []
        return []

    def _apply_inventory_to_variant(vc: Dict[str, Any]):
        if inv_df is None or inv_df.empty:
            return
        play_id = str(vc.get('play_id') or '').lower()
        min_cover = int(float(cover_map.get(play_id, default_cover))) if cover_map else default_cover
        aov = float(aligned.get('recent_aov') or aligned.get('L28_aov') or 0.0)
        gm = float(cfg.get('GROSS_MARGIN', 0.70) or 0.70)
        expected = float(vc.get('expected_$') or 0.0)
        expected_opt = float(vc.get('expected_$_optimistic') or max(expected * 1.3, expected))
        denom = max(aov * gm, 1e-6)
        required_units = expected / denom
        skus = _targeted_skus_for_play(vc)
        if not skus:
            return
        rows = inv_df[inv_df['sku'].astype(str).isin([str(s) for s in skus])].copy()
        if rows.empty and 'product' in inv_df.columns:
            # Fallback: match by product title if SKUs are not available in orders
            rows = inv_df[inv_df['product'].astype(str).isin([str(s) for s in skus])].copy()
        if rows.empty:
            return
        available_cap = float(rows.get('available_net', pd.Series(dtype=float)).sum())
        cover_min = float(rows.get('cover_days', pd.Series([float('inf')])).min())
        trust_mean = float(rows.get('trust_factor', pd.Series([1.0])).mean())
        fulfillment = 1.0
        if required_units > 0:
            fulfillment = min(1.0, available_cap / max(1.0, required_units))
        fulfillment *= max(0.5, min(1.0, trust_mean))
        vc['inv_fulfillment'] = round(fulfillment, 2)
        vc['inv_cover_min'] = round(cover_min, 1)
        vc['inv_skus_count'] = int(len(rows))
        vc['expected_$'] = max(0.0, expected * fulfillment)
        vc['expected_$_optimistic'] = max(vc['expected_$'], expected_opt * fulfillment)
        if cover_min < min_cover:
            if inv_mode == 'hard':
                vc['__skip_due_inventory__'] = True
            else:
                vc.setdefault('notes', []).append(f"Low coverage for targeted SKUs (min≈{cover_min:.0f}d < {min_cover}d)")
                vc['score'] = (vc.get('score') or 0.0) * 0.9

    for cand in final:
        pmeta = plays.get(cand.get("play_id"), {})
        variants = pmeta.get("variants", [{"id": "base", "offer_type": "no_discount", "lift_multiplier": 1.0}])
        cooldown_weeks = int(pmeta.get("cooldown_weeks", 1))

        for v in variants:
            if not _is_el(v.get("eligible_if", "True"), policy):
                continue

            vc = cand.copy()
            vc.setdefault("variant_id", v.get("id", "base"))
            vc["variant_id"] = v.get("id", vc["variant_id"]) or "base"
            # Expected impact adjustment by variant lift
            lift = float(v.get("lift_multiplier", 1.0) or 1.0)
            expected_base = float(vc.get("expected_$") or 0.0)
            expected_opt = float(vc.get("expected_$_optimistic") or max(expected_base * 1.3, expected_base))
            expected_base *= lift
            expected_opt = max(expected_base, expected_opt * lift)
            vc["expected_$"] = expected_base
            vc["expected_$_optimistic"] = expected_opt
            # Soft monthly scaling fallback if needed
            try:
                if (aligned.get('window_days') or 28) < 28:
                    scale = (28.0 / max(1.0, float(aligned.get('window_days') or 28)))
                    vc["expected_$"] *= scale
                    vc["expected_$_optimistic"] *= scale
            except Exception:
                vc["expected_$"] *= 4.0
                vc["expected_$_optimistic"] *= 4.0

            # High-LTV nudge toward no-discount
            try:
                aud_ltv = float(cand.get("audience_ltv90") or 0.0)
                top_dec = float(cand.get("ltv90_top_decile") or 0.0)
                high_ltv = (aud_ltv >= top_dec) and (top_dec > 0)
            except Exception:
                high_ltv = False
            offer_type = str(v.get("offer_type", "")).lower()
            if high_ltv and ("discount" in offer_type or "percent_of_aov" in str(v.get("cost_type",""))):
                vc["expected_$"] *= 0.97
                vc["expected_$_optimistic"] *= 0.97
            elif high_ltv and (offer_type == "no_discount"):
                vc["expected_$"] *= 1.03
                vc["expected_$_optimistic"] *= 1.03

            # Novelty & cooldown (week-aware)
            weeks_variant = _weeks_since_used(log, vc["play_id"], vc["variant_id"], asof_date=anchor_dt)
            weeks_family  = _weeks_since_used(log, vc["play_id"], None,           asof_date=anchor_dt)

            penalty = 0.0
            if weeks_variant == 0: penalty = 0.25
            elif weeks_variant == 1: penalty = 0.15
            elif weeks_variant == 2: penalty = 0.05

            # Cooldown applies across weeks (>=1)
            if (weeks_family is not None) and (weeks_family >= 1) and (weeks_family < cooldown_weeks):
                continue

            # Inventory-aware adjustments (soft by default)
            if inv_sum is not None:
                play_id = str(vc.get('play_id') or '').lower()
                min_cover = int(float(cover_map.get(play_id, default_cover))) if cover_map else default_cover
                cover_health = inv_sum.get('cover_min', float('inf'))
                trust_mean = float(inv_sum.get('trust_mean', 1.0))
                vc["expected_$"] *= trust_mean
                vc["expected_$_optimistic"] *= trust_mean
                vc['inv_trust'] = round(trust_mean, 2)
                if 'discount_hygiene' in play_id:
                    v_id = str(vc.get('variant_id') or '').lower()
                    if v_id.startswith('targeted'):
                        skus = _targeted_skus_for_play(vc)
                        if skus:
                            rows = inv_df[inv_df['sku'].astype(str).isin([str(s) for s in skus])].copy()
                            if not rows.empty and 'cover_days' in rows.columns:
                                total = int(len(rows)) or 1
                                low = int((rows['cover_days'] < 14).sum())
                                keep_ratio = max(0.0, min(1.0, (total - low) / total))
                                vc['expected_$'] *= keep_ratio
                                vc['expected_$_optimistic'] *= keep_ratio
                                vc.setdefault('notes', []).append(f"Discount scope: product-specific — excluded {low}/{total} low-stock SKUs (≥14d cover required)")
                    else:
                        in_stock_ratio = float(inv_sum.get('in_stock_ratio14', 1.0))
                        vc['inv_in_stock_ratio14'] = round(in_stock_ratio, 2)
                        vc["expected_$"] *= in_stock_ratio
                        vc["expected_$_optimistic"] *= in_stock_ratio
                        vc.setdefault('notes', []).append(f"Discount scope: sitewide — in-stock≥14d ratio≈{in_stock_ratio:.0%}")
                if cover_health < min_cover:
                    if inv_mode == 'hard':
                        continue
                    vc.setdefault('notes', []).append(f"Inventory cover low (min≈{cover_health:.0f}d < {min_cover}d)")
                    vc['score'] = (vc.get('score') or 0.0) * 0.9
                    vc['inv_cover_min'] = float(cover_health)

            _apply_inventory_to_variant(vc)
            if vc.get('__skip_due_inventory__'):
                continue

            vc["score"] = (vc.get("score") or 0.0) * (1.0 - penalty)
            variant_cands.append(vc)

    # If cooldown filtered everything, fall back to base candidates (ignore cooldown)
    if not variant_cands:
        for cand in final:
            if cand.get("failed"):
                continue
            vc = cand.copy()
            vc.setdefault("variant_id", "base")
            variant_cands.append(vc)

    finals_for_selection = variant_cands if variant_cands else final

    # Partition & select (soft diversity + effort budget)
    budget = cfg.get("EFFORT_BUDGET", 8)
    top_actions, backlog, watchlist = _partition_candidates(finals_for_selection, effort_budget=budget)

    out = {
        "actions": top_actions,
        "watchlist": [c for c in final if c.get("failed")],
        "no_call": [],
        "backlog": [],
        "pilot_actions": [],
    }

    # Backlog: passed all gates but deferred
    for b in backlog:
        out["backlog"].append({
            **b,
            "reason": b.get("defer_reason", "ranked below top actions"),
        })

    # Confidence Mode: conservative (default), aggressive, learning
    mode = str((cfg or {}).get("CONFIDENCE_MODE", "conservative")).strip().lower()

    def _mk_pilot(pilot: dict, note: str) -> dict:
        n_needed = pilot.get("min_n", 0)
        if pilot.get("metric") in ("repeat_rate", "discount_rate"):
            p = pilot.get("baseline_rate", 0.15) or 0.15
            delta = pilot.get("effect_floor", 0.02) or 0.02
            n_needed = required_n_for_proportion(p, delta, alpha=0.05, power=0.8)
        exp = float(pilot.get("expected_$", 0.0) or 0.0)
        exp_opt = float(pilot.get("expected_$_optimistic", exp * 1.3) or exp * 1.3)
        return {
            **pilot,
            "tier": "Pilot",
            "pilot_audience_fraction": cfg.get("PILOT_AUDIENCE_FRACTION", 0.2),
            "pilot_budget_cap": cfg.get("PILOT_BUDGET_CAP", 200.0),
            "n_needed": int(n_needed),
            "decision_rule": "Graduate if CI excludes 0 or q ≤ α at 28 days; else rollback.",
            "confidence_label": pilot.get("confidence_label", "Low"),
            "expected_$": exp,
            "expected_$_optimistic": max(exp, exp_opt),
            "expected_range": [round(exp * 0.7, 2), round(max(exp, exp_opt), 2)],
            "notes": (pilot.get("notes") or []) + [note],
        }

    finals_pool = finals_for_selection if finals_for_selection else final

    if mode == 'conservative':
        # Pilot fallback only if no actions
        if len(out["actions"]) == 0 and len(final) > 0:
            pilot = sorted(final, key=lambda x: x.get("score", 0), reverse=True)[0]
            out["pilot_actions"] = [_mk_pilot(pilot, "Conservative fallback pilot")]
    elif mode == 'aggressive':
        # Include up to 2 medium-confidence items (fails significance only; min_n + effect + financial pass)
        meds = []
        for c in finals_pool:
            failed = set(c.get('failed', [])); passed = set(c.get('passed', []))
            if ('significance' in failed) and ('min_n' in passed) and ('effect_floor' not in failed) and ('financial_floor' not in failed):
                meds.append(c)
        meds = sorted(meds, key=lambda x: x.get('score', 0), reverse=True)[:2]
        out["pilot_actions"] = [_mk_pilot(m, "Aggressive mode: medium-confidence (fails significance only)") for m in meds]
        if not out["pilot_actions"] and len(out["actions"]) == 0 and len(final) > 0:
            pilot = sorted(final, key=lambda x: x.get("score", 0), reverse=True)[0]
            out["pilot_actions"] = [_mk_pilot(pilot, "Aggressive fallback pilot")]
    elif mode == 'learning':
        # Show up to 3 directional candidates as pilots
        dir_list = []
        for c in finals_pool:
            n_ok = c.get('n', 0) >= 0.5 * (c.get('min_n', 0) or 0)
            p_ok = (c.get('p') is not None) and (not np.isnan(c.get('p'))) and (c.get('p') < 0.25)
            eff_ok = abs(c.get('effect_abs', 0.0)) >= 0.5 * (c.get('effect_floor', 0.0) or 0.0)
            fin_ok = (c.get('expected_$', 0.0) or 0.0) >= 0.5 * float(cfg.get('FINANCIAL_FLOOR', 0.0) or 0.0)
            if n_ok or p_ok or eff_ok or fin_ok:
                dir_list.append(c)
        dir_list = sorted(dir_list, key=lambda x: x.get('score', 0), reverse=True)[:3]
        out["pilot_actions"] = [_mk_pilot(d, "Learning mode: experimental candidate") for d in dir_list]
        # If none found, provide a fallback pilot regardless of Actions presence
        if not out["pilot_actions"] and len(final) > 0:
            pilot = sorted(final, key=lambda x: x.get("score", 0), reverse=True)[0]
            out["pilot_actions"] = [_mk_pilot(pilot, "Learning fallback pilot")]

    out["confidence_mode"] = mode

    # Relaxed pilot fallback (concierge MVP): propose Pilots when min_n passed,
    # but only for plays that do NOT already have an Action; also dedupe by (play_id, variant_id)
    if not out.get("pilot_actions"):
        actions_pairs = {(str(a.get('play_id')), str(a.get('variant_id', 'base'))) for a in out.get('actions', [])}
        actions_plays = {str(a.get('play_id')) for a in out.get('actions', [])}
        backlog_pairs = {(str(b.get('play_id')), str(b.get('variant_id', 'base'))) for b in out.get('backlog', [])}

        eligible_min_n = []
        for c in finals_pool:
            passed = set(c.get('passed', []))
            has_basic = (c.get('n', 0) or 0) > 0 and bool(c.get('metric'))
            pid = str(c.get('play_id'))
            vid = str(c.get('variant_id', 'base'))
            if not has_basic:
                continue
            if 'min_n' not in passed:
                continue
            # Skip plays already selected as Actions, and skip exact pairs already in Actions/Backlog
            if pid in actions_plays:
                continue
            if (pid, vid) in actions_pairs or (pid, vid) in backlog_pairs:
                continue
            eligible_min_n.append(c)

        if eligible_min_n:
            eligible_min_n = sorted(eligible_min_n, key=lambda x: x.get('score', 0), reverse=True)[:2]
            pilots = [_mk_pilot(c, "Concierge MVP: min_n met; significance shown as confidence badge") for c in eligible_min_n]
            # Final self-dedupe across pilots by (play_id, variant_id)
            seen: set[tuple[str, str]] = set()
            deduped = []
            for p in pilots:
                key = (str(p.get('play_id')), str(p.get('variant_id', 'base')))
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(p)
            out["pilot_actions"] = deduped

    # Global dedupe rule: remove any pilots that duplicate Actions/Backlog by play or exact variant pair
    if out.get("pilot_actions"):
        actions_pairs = {(str(a.get('play_id')), str(a.get('variant_id', 'base'))) for a in out.get('actions', [])}
        actions_plays = {str(a.get('play_id')) for a in out.get('actions', [])}
        backlog_pairs = {(str(b.get('play_id')), str(b.get('variant_id', 'base'))) for b in out.get('backlog', [])}
        new_pilots = []
        seen_pairs: set[tuple[str, str]] = set()
        for p in out.get('pilot_actions', []):
            pid = str(p.get('play_id'))
            vid = str(p.get('variant_id', 'base'))
            pair = (pid, vid)
            if pid in actions_plays:
                continue
            if pair in actions_pairs or pair in backlog_pairs:
                continue
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            new_pilots.append(p)
        # Collapse to at most one variant per play: keep highest-score variant
        best_by_play: dict[str, dict] = {}
        for p in new_pilots:
            pid = str(p.get('play_id'))
            if pid not in best_by_play:
                best_by_play[pid] = p
            else:
                if float(p.get('score', 0) or 0) > float(best_by_play[pid].get('score', 0) or 0):
                    best_by_play[pid] = p
        out['pilot_actions'] = list(best_by_play.values())

    # MVP Guardrails: Channel caps and hard conflicts (applied before overlap adjustment)
    policy_notes: list[str] = []

    def _parse_caps(val) -> dict:
        if not val:
            return {}
        if isinstance(val, dict):
            return {str(k).lower(): int(v) for k, v in val.items() if v is not None}
        try:
            data = json.loads(str(val))
            if isinstance(data, dict):
                return {str(k).lower(): int(v) for k, v in data.items() if v is not None}
        except Exception:
            pass
        return {}

    def _parse_conflicts(val) -> set[tuple[str, str]]:
        pairs: set[tuple[str, str]] = set()
        if not val:
            return pairs
        items = None
        if isinstance(val, (list, tuple)):
            items = val
        else:
            try:
                data = json.loads(str(val))
                if isinstance(data, list):
                    items = data
            except Exception:
                pass
        if items is None:
            items = [x.strip() for x in str(val).split(',') if '->' in x]
        for it in items:
            try:
                if isinstance(it, str) and '->' in it:
                    a, b = it.split('->', 1)
                    pairs.add((a.strip().lower(), b.strip().lower()))
            except Exception:
                continue
        return pairs

    channel_caps = _parse_caps(cfg.get('CHANNEL_CAPS'))
    if channel_caps:
        kept: list[dict] = []
        demoted: list[dict] = []
        used: dict[str, int] = {k: 0 for k in channel_caps.keys()}
        for a in out.get("actions", []):
            ch = a.get('channels') or []
            if isinstance(ch, dict):
                ch = [k for k, v in ch.items() if v]
            ch = [str(x).lower() for x in ch] if isinstance(ch, (list, tuple)) else []
            exceeds = any((used.get(c, 0) >= int(channel_caps.get(c, 999))) for c in ch)
            if exceeds:
                a.setdefault('notes', []).append('Demoted due to channel caps')
                demoted.append(a)
            else:
                for c in ch:
                    if c in channel_caps:
                        used[c] = used.get(c, 0) + 1
                kept.append(a)
        if demoted:
            policy_notes.append(f"Channel caps applied; demoted {len(demoted)} actions")
        out["actions"] = kept
        for a in demoted:
            out["backlog"].append({**a, "reason": "channel_cap"})

    conflict_pairs = _parse_conflicts(cfg.get('CONFLICT_PAIRS'))
    if conflict_pairs:
        by_pid: dict[str, dict] = {str(a.get('play_id')).lower(): a for a in out.get("actions", [])}
        to_demote: set[str] = set()
        for a, b in conflict_pairs:
            if a in by_pid and b in by_pid:
                x, y = by_pid[a], by_pid[b]
                ax = float(x.get('score', 0) or 0.0)
                ay = float(y.get('score', 0) or 0.0)
                loser = a if ax < ay else b
                to_demote.add(loser)
        if to_demote:
            new_actions = []
            for act in out.get("actions", []):
                pid = str(act.get('play_id')).lower()
                if pid in to_demote:
                    act.setdefault('notes', []).append('Demoted due to conflict pair')
                    out["backlog"].append({**act, "reason": "conflict"})
                else:
                    new_actions.append(act)
            policy_notes.append(f"Conflicts enforced; demoted {len(to_demote)} actions")
            out["actions"] = new_actions

    # Audience overlap adjustment for Top Actions (conservative)
    try:
        segments_dir = Path(receipts_dir).parent / "segments"
        seen_customers: set[str] = set()

        def _load_segment_customers(attachment: str) -> set[str]:
            if not attachment:
                return set()
            p = segments_dir / attachment
            if not p.exists():
                return set()
            try:
                df = pd.read_csv(p)
                col = None
                for c in df.columns:
                    if str(c).lower() in {"customer_id", "customer", "email", "id"}:
                        col = c; break
                if col is None:
                    return set()
                return set(df[col].astype(str).tolist())
            except Exception:
                return set()

        overlap_max_ratio = float(cfg.get('OVERLAP_MAX_RATIO', 0.6) or 0.6)
        min_unique_audience = int(cfg.get('MIN_UNIQUE_AUDIENCE', 500) or 500)
        demote_high_overlap: list[dict] = []
        kept_actions: list[dict] = []
        for idx, a in enumerate(out.get("actions", [])):
            att = a.get("attachment")
            aud = _load_segment_customers(att)
            total = len(aud)
            if total == 0:
                kept_actions.append(a)
                continue
            overlap_n = len(aud & seen_customers)
            overlap_ratio = (overlap_n / total) if total > 0 else 0.0
            if overlap_ratio > 0:
                exp0 = float(a.get("expected_$") or 0.0)
                exp_opt0 = float(a.get("expected_$_optimistic") or exp0)
                factor = max(0.0, 1.0 - overlap_ratio)
                exp1 = exp0 * factor
                exp_opt1 = max(exp1, exp_opt0 * factor)
                a["expected_$"] = round(exp1, 2)
                a["expected_$_optimistic"] = round(exp_opt1, 2)
                a["expected_range"] = [round(a["expected_$"] * 0.7, 2), round(a["expected_$_optimistic"], 2)]
                a["audience_size_effective"] = total - overlap_n
                a["overlap_with_prior"] = round(overlap_ratio, 3)
            if (overlap_ratio >= overlap_max_ratio) and ((total - overlap_n) < min_unique_audience):
                a.setdefault('notes', []).append('Demoted due to high audience overlap')
                demote_high_overlap.append(a)
            else:
                kept_actions.append(a)
                seen_customers |= aud
        if demote_high_overlap:
            policy_notes.append(f"High-overlap demotions: {len(demote_high_overlap)}")
            for a in demote_high_overlap:
                out["watchlist"].append({**a, "reason": "high_overlap"})
        out["actions"] = kept_actions
    except Exception:
        pass

    # Campaign interaction effects (pairwise dampening, env-configurable)
    try:
        interaction_factors = get_interaction_factors(cfg or {})
        prior_play_ids: list[str] = []
        for a in out["actions"]:
            pid = str(a.get("play_id") or "")
            factor = 1.0
            notes: list[str] = []
            for prior in prior_play_ids:
                f = interaction_factors.get((prior, pid))
                if f is not None and f < 1.0:
                    factor *= float(f)
                    notes.append(f"{prior}→{pid} x{f:.2f}")
            if factor < 1.0:
                exp0 = float(a.get("expected_$") or 0.0)
                exp_opt0 = float(a.get("expected_$_optimistic") or exp0)
                a["expected_$"] = round(exp0 * factor, 2)
                a["expected_$_optimistic"] = round(max(a["expected_$"], exp_opt0 * factor), 2)
                a["expected_range"] = [round(a["expected_$"] * 0.7, 2), round(a["expected_$_optimistic"], 2)]
                a["interaction_factor"] = round(factor, 3)
                a["interaction_notes"] = notes
            prior_play_ids.append(pid)
    except Exception:
        pass

    # Optional: log selections for cooldown tracking
    try:
        write_actions_log(receipts_dir, out.get("actions", []))
    except Exception:
        pass

    # Phase 0: emit candidate_debug.json for observability (no behavior change)
    try:
        # Check if multi-window analysis was used
        window_keys = ['L7', 'L28', 'L56', 'L90']
        has_multiwindow = any(key in aligned for key in window_keys)
        used_multiwindow = has_multiwindow and cfg.get('ENABLE_MULTIWINDOW_SCORING', True)
        
        debug = {
            "window_days": int(aligned.get("window_days") or 28),
            "confidence_mode": mode,
            "policy_notes": policy_notes,
            "multiwindow_analysis": {
                "enabled": used_multiwindow,
                "available_windows": [k for k in window_keys if k in aligned],
                "vertical_mode": get_vertical_mode(),
                "window_weights": get_window_weights(get_vertical_mode()) if used_multiwindow else None
            },
            "counts": {
                "base_candidates": int(len(final)),
                "variants": int(len(finals_for_selection)),
                "actions": int(len(out.get("actions", []))),
                "pilots": int(len(out.get("pilot_actions", []))),
                "watchlist": int(len(out.get("watchlist", []))),
            },
            "candidates": [
                {
                    k: c.get(k)
                    for k in (
                        "id","play_id","metric","n","effect_abs","p","q","ci_low","ci_high",
                        "expected_$","min_n","effect_floor","audience_size","passed","failed","score","tier","reasons",
                        "confidence_score","engine_tier","source_window","contributing_windows","window_scores",
                        "seasonal_multiplier","seasonal_period","base_score","window_weight"
                    )
                }
                for c in final
            ],
            "actions": [
                {
                    k: a.get(k)
                    for k in (
                        "id","play_id","variant_id","metric","expected_$","score","notes","confidence_label"
                    )
                }
                for a in out.get("actions", [])
            ],
            "pilot_actions": [
                {
                    k: p.get(k)
                    for k in (
                        "id","play_id","variant_id","metric","expected_$","score","notes","confidence_label","pilot_audience_fraction","pilot_budget_cap"
                    )
                }
                for p in out.get("pilot_actions", [])
            ],
        }
        from .utils import write_json as _wj
        _wj(str(Path(receipts_dir) / "candidate_debug.json"), debug)
    except Exception:
        pass

    return out


def _weeks_since_used(
    log: list[dict],
    play_id: str,
    variant_id: str | None,
    asof_date: datetime.date | None = None
) -> int | None:
    """
    Return how many whole ISO weeks since this play/variant was last used,
    relative to `asof_date` (default: today). 0 = same ISO week.
    """
    ts_list: list[datetime.date] = []
    for r in log:
        if r.get("play_id") != play_id: 
            continue
        if variant_id is not None and r.get("variant_id") != variant_id:
            continue
        try:
            d = datetime.datetime.fromisoformat(r["ts"].replace("Z","")).date()
            ts_list.append(d)
        except Exception:
            pass
    if not ts_list:
        return None
    last = max(ts_list)
    ref = asof_date or datetime.date.today()
    # ISO week difference (calendar weeks), not just 7-day buckets:
    last_iso_year, last_iso_week, _ = last.isocalendar()
    ref_iso_year, ref_iso_week, _ = ref.isocalendar()
    return (ref_iso_year - last_iso_year) * 52 + (ref_iso_week - last_iso_week)


# ---- Section partition helper (single source of truth for sections) ----
def _partition_candidates(final: list[dict], effort_budget: int = 8):
    """
    Sections:
      - Watchlist := failed ≥1 gate
      - Pool      := passed all gates
      - Top       := up to 3 from Pool under effort budget,
                     *one variant per play_id*,
                     and soft category diversity (try to include ≥2 categories).
      - Backlog   := remaining Pool items (all passed gates) with a defer reason
    """
    # 1) Classify
    watchlist = [c for c in final if c.get("failed")]          # failed at least one gate
    pool      = [c for c in final if not c.get("failed")]      # passed all gates

    # 2) Rank pool by score (desc) with LTV-aware tiebreaker (non-gating)
    pool_sorted = sorted(
        pool,
        key=lambda x: (x.get("score", 0), x.get("audience_ltv90", 0.0)),
        reverse=True
    )

    top: list[dict] = []
    used_cats: set   = set()
    used_plays: set  = set()
    used_effort: int = 0

    # --- First pass: enforce play-level uniqueness + category diversity ---
    for c in pool_sorted:
        if len(top) >= 3:
            break

        pid = c.get("play_id")
        cat = c.get("category")
        eff = int(c.get("effort", 2))

        # one-per-play family
        if pid in used_plays:
            c.setdefault("defer_reason", "another variant of this play selected")
            continue

        # soft category diversity: until we have ≥2 categories, avoid duplicates
        if cat in used_cats and len(used_cats) < 2:
            c.setdefault("defer_reason", "category diversity")
            continue

        # effort budget
        if used_effort + eff > effort_budget:
            c.setdefault("defer_reason", "effort budget")
            continue

        top.append(c)
        used_plays.add(pid)
        if cat:
            used_cats.add(cat)
        used_effort += eff

    # --- Second pass: if we still have <3, relax category diversity (but keep one-per-play & budget) ---
    if len(top) < 3:
        for c in pool_sorted:
            if len(top) >= 3:
                break

            pid = c.get("play_id")
            eff = int(c.get("effort", 2))

            # skip items already chosen
            if any((c.get("play_id"), c.get("variant_id")) == (t.get("play_id"), t.get("variant_id")) for t in top):
                continue

            # still enforce one-per-play family
            if pid in used_plays:
                c.setdefault("defer_reason", "another variant of this play selected")
                continue

            # budget
            if used_effort + eff > effort_budget:
                c.setdefault("defer_reason", "effort budget")
                continue

            top.append(c)
            used_plays.add(pid)
            used_effort += eff

    # 3) Build backlog: all pool items not chosen (they passed gates)
    chosen_keys = {(t.get("play_id"), t.get("variant_id")) for t in top}
    backlog: list[dict] = []
    for c in pool_sorted:
        key = (c.get("play_id"), c.get("variant_id"))
        if key not in chosen_keys:
            c.setdefault("defer_reason", "ranked below top actions")
            backlog.append(c)

    return top, backlog, watchlist




def load_playbooks(path: str) -> List[Dict[str, Any]]:
    import yaml
    return yaml.safe_load(Path(path).read_text()).get("playbooks", [])

def _calculate_calibrated_confidence(candidate: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    """Calculate calibrated confidence score using multi-window, seasonal, and cohort signals
    
    Enhanced to incorporate:
    - Multi-window signal strength aggregation
    - Seasonal period confidence boosts  
    - Cohort-enhanced statistical pooling
    """
    import numpy as np
    
    # Input hygiene - clamp all inputs to safe ranges
    p = max(min(candidate.get('p', 1.0), 1.0), 1e-8)  # Clamp p to [1e-8, 1.0]
    n = max(candidate.get('n', 0), 0)  # Ensure n >= 0
    effect = candidate.get('effect_abs', 0)
    expected_revenue = max(candidate.get('expected_$', 0), 0)  # Ensure >= 0
    
    mode = str(cfg.get("CONFIDENCE_MODE", "learning")).strip().lower()
    
    # 1. Multi-window signal strength aggregation
    window_scores = candidate.get('window_scores', {})
    contributing_windows = candidate.get('contributing_windows', [])
    
    if window_scores and contributing_windows and any(score > 0 for score in window_scores.values()):
        # Use weighted multi-window signal strength
        total_weighted_signal = 0.0
        total_weight = 0.0
        
        # Use dynamic window weights from vertical configuration
        from .utils import get_window_weights
        vertical_mode = get_vertical_mode()
        window_weights = get_window_weights(vertical_mode)

        for window in contributing_windows:
            if window in window_scores and window_scores[window] > 0:
                weight = window_weights.get(window, 0.25)  # Default weight if not found
                signal = min(-np.log10(max(window_scores[window], 1e-8)), 4.0)
                total_weighted_signal += signal * weight
                total_weight += weight

        if total_weight > 0:
            raw_signal = total_weighted_signal / total_weight
        else:
            # Fallback to single-window signal
            raw_signal = min(-np.log10(p), 4.0)

        # Apply non-significance penalty to multi-window signal
        if p >= 1.0:
            signal_strength = 0.0  # Completely non-significant gets zero confidence
        elif p > 0.8:
            signal_strength = raw_signal * 0.1  # Very weak signal gets 90% penalty
        elif p > 0.5:
            signal_strength = raw_signal * 0.3  # Weak signal gets 70% penalty
        else:
            signal_strength = raw_signal
    else:
        # Fallback to single-window signal strength with non-significance penalty
        raw_signal = min(-np.log10(p), 4.0)

        # Apply severe penalty for non-significant results
        if p >= 1.0:
            signal_strength = 0.0  # Completely non-significant gets zero confidence
        elif p > 0.8:
            signal_strength = raw_signal * 0.1  # Very weak signal gets 90% penalty
        elif p > 0.5:
            signal_strength = raw_signal * 0.3  # Weak signal gets 70% penalty
        else:
            signal_strength = raw_signal
    
    # 2. Effect direction and magnitude handling
    if effect >= 0:
        direction_mult = 1.0
        # Gentle effect size boost for larger positive effects
        effect_mult = min(1.15, 1.0 + abs(effect) * cfg.get('EFFECT_BOOST_FACTOR', 0.3))
    else:
        # Severe penalty for harmful effects - 99% reduction to prevent dangerous actions
        direction_mult = 0.01  # Near-disqualifying penalty for harmful effects
        effect_mult = 1.0      # No boost for negative effects
    
    # 3. Sample size adequacy (configurable scale, diminishing returns)
    n_scale = cfg.get('N_SCALE', 100)  # Default for store-wide analysis
    adequacy = min(np.log1p(n / n_scale) / np.log1p(10), 1.0)  # 0-1 range, smooth
    
    # 4. Seasonal multiplier integration
    seasonal_multiplier = candidate.get('seasonal_multiplier', 1.0)
    seasonal_period = candidate.get('seasonal_period', 'unknown')
    
    # Apply seasonal confidence boost based on timing appropriateness
    seasonal_boost = 1.0
    if seasonal_multiplier > 1.0:
        # Positive seasonal periods get confidence boost
        seasonal_boost = min(1.15, 1.0 + (seasonal_multiplier - 1.0) * 0.5)
    elif seasonal_multiplier < 1.0:
        # Negative seasonal periods get confidence penalty  
        seasonal_boost = max(0.85, seasonal_multiplier)
    
    # 5. Cohort enhancement factor
    cohort_boost = 1.0
    # Check if candidate has been enhanced with cohort pooling
    base_score = candidate.get('base_score', 0.0)
    if base_score > 0:
        # If cohort pooling improved statistical power, boost confidence
        cohort_boost = min(1.1, 1.0 + base_score * 0.2)
    
    # 6. Mode-specific base confidence mapping (explicit ranges)
    def map_signal_to_range(signal, lo, hi):
        """Map 0-4 signal strength to explicit [lo, hi] range"""
        normalized = min(signal / 4.0, 1.0)  # Normalize to [0, 1]
        return lo + normalized * (hi - lo)
        
    if mode == 'learning':
        # PMF-friendly: 30-95% range for faster learning
        base_conf = map_signal_to_range(signal_strength, 0.30, 0.95)
    elif mode == 'conservative':
        # High rigor: 20-85% range for established businesses
        base_conf = map_signal_to_range(signal_strength, 0.20, 0.85)
    else:  # aggressive
        # Broad acceptance: 35-95% range for growth/exploration
        base_conf = map_signal_to_range(signal_strength, 0.35, 0.95)
    
    # 7. Final calibrated confidence with all enhancements (always bounded [0,1])
    confidence = (base_conf * direction_mult * effect_mult * (0.7 + 0.3 * adequacy) * 
                  seasonal_boost * cohort_boost)
    return max(0.0, min(1.0, confidence))

# Legacy function for backward compatibility during transition
def _calculate_engine_confidence_score(candidate: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    """LEGACY: Use _calculate_business_confidence instead"""
    return _calculate_business_confidence(candidate, cfg)

# NEW UNIFIED CONFIDENCE SYSTEM
def _nan_safe_float(value: Any, default: float) -> float:
    """M4a T4a.2 helper: coerce a possibly-NaN value to a safe default.

    None and NaN map to ``default``; everything else is float()-coerced. The
    default is the "no measured evidence" sentinel — ``1.0`` for p-values
    (no significance), ``0.0`` for effects/financials. This keeps scoring,
    gate, and confidence math NaN-safe without changing behavior on
    candidates whose stats are real numbers.
    """
    if value is None:
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f != f:  # NaN check without np.isnan import dance
        return default
    return f


def _calculate_gate_performance_score(candidate: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    """Predict likelihood of passing business gates (0-100 points)"""
    thresholds = _get_mode_adjusted_thresholds(cfg)
    score = 0.0

    # Sample Size Gate (25 points max)
    n_ratio = candidate["n"] / max(1, candidate["min_n"] * thresholds["min_n_factor"])
    score += min(25.0, 15.0 + 10.0 * min(n_ratio, 2.0))

    # Significance Gate (25 points max). M4a T4a.2: coerce NaN p-values to 1.0
    # ("no significance") so a fabricated/NaN'd p does not propagate NaN
    # through `25.0 * (1.0 - p / threshold)`.
    p = _nan_safe_float(candidate.get("p", 1.0), default=1.0)
    if p < thresholds["p_threshold"]:
        score += 25.0
    else:
        score += max(0.0, 25.0 * (1.0 - p / max(thresholds["p_threshold"], 0.01)))

    # Effect Size Gate (25 points max). M4a T4a.2: NaN effect → 0 ("no effect").
    effect_floor = max(0.001, candidate["effect_floor"] * thresholds["effect_factor"])
    effect_abs_safe = _nan_safe_float(candidate.get("effect_abs", 0.0), default=0.0)
    effect_ratio = abs(effect_abs_safe) / effect_floor
    score += min(25.0, 15.0 + 10.0 * min(effect_ratio, 2.0))

    # Financial Gate (25 points max)
    financial_floor = max(1.0, cfg["FINANCIAL_FLOOR"] * thresholds["financial_factor"])
    revenue_ratio = _nan_safe_float(candidate.get("expected_$", 0.0), default=0.0) / financial_floor
    score += min(25.0, 15.0 + 10.0 * min(revenue_ratio, 2.0))

    return score

def _calculate_signal_strength_bonus(candidate: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    """Additional confidence from strong statistical signals (0-25 points)"""
    window_scores = candidate.get('window_scores', {})
    contributing_windows = candidate.get('contributing_windows', [])

    if window_scores and contributing_windows:
        total_weighted_signal = 0.0
        total_weight = 0.0

        from .utils import get_window_weights
        window_weights = get_window_weights(get_vertical_mode())

        for window in contributing_windows:
            ws = window_scores.get(window)
            ws_safe = _nan_safe_float(ws, default=0.0)
            if ws_safe > 0:
                weight = window_weights.get(window, 0.25)
                signal = min(-np.log10(max(ws_safe, 1e-8)), 4.0)
                total_weighted_signal += signal * weight
                total_weight += weight

        avg_signal = total_weighted_signal / total_weight if total_weight > 0 else 0.0
    else:
        # M4a T4a.2: NaN p collapses to 1.0 → -log10(1)=0 → zero bonus.
        p = _nan_safe_float(candidate.get("p", 1.0), default=1.0)
        avg_signal = min(-np.log10(max(p, 1e-8)), 4.0)

    return (avg_signal / 4.0) * 25.0

def _calculate_context_multiplier(candidate: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    """Business context adjustments (0.5x to 1.5x)"""
    multiplier = 1.0

    # Sample Size Quality
    n = candidate.get("n", 0)
    n_scale = cfg.get('N_SCALE', 100)
    adequacy = min(np.log1p(n / n_scale) / np.log1p(10), 1.0)
    multiplier *= (0.8 + 0.4 * adequacy)

    # Seasonal Timing
    seasonal_multiplier = candidate.get('seasonal_multiplier', 1.0)
    if seasonal_multiplier > 1.0:
        seasonal_factor = min(1.15, 1.0 + (seasonal_multiplier - 1.0) * 0.3)
    else:
        seasonal_factor = max(0.85, 0.85 + (seasonal_multiplier - 0.85) * 0.5)
    multiplier *= seasonal_factor

    # Effect Size Quality. M4a T4a.2: NaN effect collapses to 0.0 (no boost).
    effect = _nan_safe_float(candidate.get("effect_abs", 0), default=0.0)
    if effect >= 0:
        effect_factor = min(1.3, 1.0 + abs(effect) * 0.6)
        multiplier *= effect_factor

    # Cohort Enhancement
    base_score = candidate.get('base_score', 0.0)
    if base_score > 0:
        cohort_factor = min(1.1, 1.0 + base_score * 0.1)
        multiplier *= cohort_factor

    return max(0.5, min(1.5, multiplier))

def _calculate_safety_multiplier(candidate: Dict[str, Any]) -> float:
    """Hard penalties for dangerous conditions (0.01x to 1.0x)"""
    multiplier = 1.0

    # Harmful Effects. M4a T4a.2: NaN effect → 0.0 (not "negative", not "harmful").
    effect = _nan_safe_float(candidate.get("effect_abs", 0), default=0.0)
    if effect < 0:
        multiplier *= 0.01

    # Non-Significance Penalties. M4a T4a.2: NaN p → 1.0 ("no significance"), so
    # a fabricated/NaN'd targeting candidate gets the full no-evidence penalty.
    p = _nan_safe_float(candidate.get("p", 1.0), default=1.0)
    if p >= 1.0:
        multiplier *= 0.05
    elif p > 0.8:
        multiplier *= 0.2
    elif p > 0.5:
        multiplier *= 0.6

    return multiplier

def _calculate_statistical_confidence(candidate: Dict[str, Any]) -> float:
    """Calculate statistical confidence based on p-value (mode-independent)"""
    # M4a T4a.2: NaN p maps to "no significance". The bucketed thresholds
    # below already returned 0.05 for p>=0.20, but `if p < 0.01` on a NaN
    # silently evaluates False, which on every comparison flows down to the
    # 0.05 branch — accidentally correct for measured/directional, but for
    # targeting we want the same outcome explicitly.
    p = _nan_safe_float(candidate.get("p", 1.0), default=1.0)

    # Statistical confidence based on p-value significance levels
    if p < 0.01:
        return 0.95  # Very high confidence
    elif p < 0.05:
        return 0.80  # High confidence
    elif p < 0.10:
        return 0.50  # Moderate confidence
    elif p < 0.20:
        # Linear interpolation between 50% and 10% for p-values 0.10-0.20
        # p=0.188 should give ~12% confidence
        return 0.50 - (0.40 * (p - 0.10) / 0.10)
    else:
        return 0.05  # Very low confidence

def _calculate_business_confidence(candidate: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    """Calculate unified business confidence score using statistical significance.

    M4b T4b.3 (confidence collapse). When ``EVIDENCE_CLASS_ENFORCED=true``,
    confidence is the **single** ``_calculate_statistical_confidence(p)``
    term. The legacy formula triple-counted the same p-value through
    ``gate_score`` (significance gate), ``signal_bonus`` (-log10(p)), and
    ``safety_multiplier`` (non-significance penalty) — three independent
    re-bakes of the same statistic. The collapse keeps the bucketed
    p→confidence mapping (0.95 / 0.80 / 0.50 / linear / 0.05) and drops
    the multiplied business-context terms.

    With the flag off, the legacy 60/40 blend is preserved (M0/M4a
    parity).
    """
    import numpy as np

    # M4b T4b.3: collapse confidence to a single p-derived term.
    if bool(cfg.get("EVIDENCE_CLASS_ENFORCED", False)):
        return _calculate_statistical_confidence(candidate)

    # --- Legacy path (flag off) ---
    # Use statistical confidence as primary signal (60% weight)
    statistical_confidence = _calculate_statistical_confidence(candidate)

    # Business context adjustments (40% weight)
    gate_score = _calculate_gate_performance_score(candidate, cfg)
    signal_bonus = _calculate_signal_strength_bonus(candidate, cfg)
    context_multiplier = _calculate_context_multiplier(candidate, cfg)
    safety_multiplier = _calculate_safety_multiplier(candidate)

    business_context = (gate_score + signal_bonus) / 125.0 * context_multiplier * safety_multiplier

    # Weighted combination: 60% statistical + 40% business context
    final_confidence = (0.6 * statistical_confidence) + (0.4 * business_context)

    return max(0.0, min(1.0, final_confidence))

def _get_mode_adjusted_thresholds(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Get mode-adjusted gate thresholds for PMF/learning vs mature business needs"""
    mode = str(cfg.get("CONFIDENCE_MODE", "learning")).strip().lower()
    
    if mode == "learning":
        # PMF/MVP friendly - lower barriers for faster experimentation
        return {
            "p_threshold": 0.20,           # Accept weaker signals (vs 0.05 normally)
            "min_n_factor": 0.5,           # Half the sample size requirement
            "effect_factor": 0.5,          # Half the effect size requirement  
            "financial_factor": 0.3        # Lower financial barrier (30% of normal)
        }
    elif mode == "conservative":
        # High rigor for established businesses
        return {
            "p_threshold": 0.01,           # Stricter significance
            "min_n_factor": 1.2,           # 20% higher sample requirement
            "effect_factor": 1.0,          # Full effect requirement
            "financial_factor": 1.0        # Full financial requirement
        }
    else:  # aggressive
        # Balanced approach
        return {
            "p_threshold": 0.10,           # Moderate significance
            "min_n_factor": 0.8,           # Slightly lower sample requirement
            "effect_factor": 0.8,          # Slightly lower effect requirement
            "financial_factor": 0.7        # Lower financial barrier
        }

def _gate_and_score(candidate: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    passed, failed = [], []
    
    # Get mode-adjusted thresholds
    thresholds = _get_mode_adjusted_thresholds(cfg)
    
    # Sample size gate (mode-adjusted)
    adjusted_min_n = candidate["min_n"] * thresholds["min_n_factor"]
    if candidate["n"] >= adjusted_min_n: passed.append("min_n")
    else: failed.append("min_n")
    # Significance gate: (CI excludes 0) OR (p < mode_threshold) OR (q < FDR_ALPHA) 
    q = candidate.get("q", np.nan)
    p = candidate.get("p", np.nan)
    ci_ok = (
        (candidate.get("ci_low") is not None)
        and (candidate.get("ci_high") is not None)
        and (candidate["ci_low"] * candidate["ci_high"] > 0)
    )
    # Use mode-adjusted p-value threshold (learning=0.20, conservative=0.01, aggressive=0.10)
    sig_ok = ci_ok or (not np.isnan(p) and p < thresholds["p_threshold"]) or (not np.isnan(q) and q < cfg["FDR_ALPHA"])

    if sig_ok: passed.append("significance")
    else: failed.append("significance")
    
    # Effect floor gate (mode-adjusted)
    adjusted_effect_floor = candidate["effect_floor"] * thresholds["effect_factor"]
    if abs(candidate["effect_abs"]) >= adjusted_effect_floor: passed.append("effect_floor")
    else: failed.append("effect_floor")
    
    # Financial floor gate (mode-adjusted, on revenue for MVP/PMF)
    expected_revenue = candidate["expected_$"]
    adjusted_financial_floor = cfg["FINANCIAL_FLOOR"] * thresholds["financial_factor"]
    if expected_revenue >= adjusted_financial_floor: passed.append("financial_floor")
    else: failed.append("financial_floor")

    significance_score = significance_to_score(candidate.get("p", np.nan), candidate.get("q", np.nan), cfg["FDR_ALPHA"])
    effect_score = effect_to_score(candidate["effect_abs"], candidate["effect_floor"])
    audience_score = audience_to_score(candidate["n"], candidate["min_n"])
    confidence_score = confidence_from_ci(candidate.get("ci_low", np.nan), candidate.get("ci_high", np.nan))
    financial_score = financial_to_score(candidate["expected_$"], cfg["FINANCIAL_FLOOR"])
    total = compute_score(financial_score, significance_score, effect_score, confidence_score, audience_score)
    
    # Calculate unified business confidence score for tier assignment
    engine_confidence_score = _calculate_business_confidence(candidate, cfg)

    cand = candidate.copy()
    cand["passed"], cand["failed"], cand["score"] = passed, failed, total
    cand["confidence_score"] = engine_confidence_score
    cand["scores_breakdown"] = {
        "financial": financial_score, "significance": significance_score, "effect_size": effect_score,
        "confidence": confidence_score, "audience_size": audience_score,
    }
        # --- Tiering: Actions / Watchlist / No call ---
    # Current: Actions = all gates pass
    # New: Watchlist = directional signal but fails at least one gate
    #  - any of these qualifies as "directional":
    #    (a) n >= 0.5*min_n, OR
    #    (b) p < 0.25 (raw) OR
    #    (c) abs(effect) >= 0.5*effect_floor OR
    #    (d) expected_$ >= 0.5*FINANCIAL_FLOOR
    directional = (
        (cand["n"] >= 0.5 * candidate["min_n"]) or
        ((candidate.get("p") is not None) and (not np.isnan(candidate.get("p"))) and (candidate["p"] < 0.25)) or
        (abs(candidate["effect_abs"]) >= 0.5 * candidate["effect_floor"]) or
        (candidate["expected_$"] >= 0.5 * cfg["FINANCIAL_FLOOR"])
    )

    # Legacy tier assignment (maintain compatibility)
    if len(failed) == 0:
        tier = "Actions"
    elif directional:
        tier = "Watchlist"
    else:
        tier = "No call"

    cand["tier"] = tier
    
    # ENGINE.md tier assignment using gates + confidence
    mode = str(cfg.get("CONFIDENCE_MODE", "learning")).strip().lower()
    
    # Calibrated confidence thresholds (aligned with actual confidence ranges produced)
    if mode == 'learning':
        # Learning/PMF: Lower thresholds for faster experimentation
        # Based on observed confidence range: ~30-95%
        primary_threshold, quick_wins_threshold, experiments_threshold = 0.65, 0.50, 0.35
    elif mode == 'conservative':
        # Conservative: Higher bar for established businesses
        # Stricter requirements for confidence
        primary_threshold, quick_wins_threshold, experiments_threshold = 0.80, 0.65, 0.45
    else:  # aggressive
        # Aggressive: Moderate thresholds for growth/exploration
        # Balanced approach between learning and conservative
        primary_threshold, quick_wins_threshold, experiments_threshold = 0.75, 0.60, 0.40
    
    # ENGINE.md unified tier assignment
    if len(failed) == 0 and engine_confidence_score >= primary_threshold:
        engine_tier = "PRIMARY"
    elif (len(failed) <= 1 or 'significance' in passed) and engine_confidence_score >= quick_wins_threshold:
        engine_tier = "QUICK_WINS"
    elif directional and engine_confidence_score >= experiments_threshold:
        engine_tier = "EXPERIMENTS"
    elif directional:
        engine_tier = "WATCHLIST"
    else:
        engine_tier = "NO_CALL"

    cand["engine_tier"] = engine_tier

    # --- Human-readable reasons for Watchlist/Backlog cards ---
    reasons = []
    if "min_n" in failed:
        adjusted_min_n = candidate["min_n"] * thresholds["min_n_factor"]
        need = max(0, int(adjusted_min_n - candidate["n"]))
        reasons.append(f"needs ~{need} more orders (adjusted min_n={adjusted_min_n:.0f} for {mode} mode)")
    if "significance" in failed:
        p = candidate.get("p", np.nan)
        q = candidate.get("q", np.nan)
        p_thresh = thresholds["p_threshold"]
        reasons.append(f"not yet significant (p={p:.3f}, q={q:.3f}, needs p<{p_thresh:.2f} for {mode} mode)")
    if "effect_floor" in failed:
        adjusted_effect_floor = candidate["effect_floor"] * thresholds["effect_factor"]
        reasons.append(f"effect below floor (Δ={candidate['effect_abs']:+.3%} vs adjusted floor {adjusted_effect_floor:.1%} for {mode} mode)")
    if "financial_floor" in failed:
        expected_revenue = candidate['expected_$']
        adjusted_financial_floor = cfg['FINANCIAL_FLOOR'] * thresholds["financial_factor"]
        short = max(0.0, float(adjusted_financial_floor - expected_revenue))
        reasons.append(f"fails revenue floor by ${short:,.0f} (needs ≥ ${adjusted_financial_floor:,.0f} revenue for {mode} mode, got ${expected_revenue:,.0f})")

    cand["reasons"] = reasons

    return cand


def _enhance_candidates_with_cohorts(g: pd.DataFrame, candidates: List[Dict[str, Any]], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Enhance candidate statistical significance using cohort-based pooling.
    
    Args:
        g: Transaction dataframe
        candidates: List of candidate actions with statistical results
        cfg: Configuration dictionary
        
    Returns:
        Enhanced candidates with cohort-pooled statistics where applicable
    """
    if not cfg.get('ENABLE_COHORT_POOLING', False):
        return candidates
    
    try:
        # Detect customer cohorts
        cohorts = detect_customer_cohorts(g)
        
        if len(cohorts) <= 1:
            # Not enough cohorts for meaningful pooling
            return candidates
        
        debug_log('actions', f"Cohort analysis detected {len(cohorts)} cohorts: {list(cohorts.keys())}")
        
        enhanced_candidates = []
        
        for candidate in candidates:
            try:
                # For each candidate, run statistical test on each cohort
                cohort_results = {}
                play_id = candidate.get('play_id', '')
                
                for cohort_name, cohort_df in cohorts.items():
                    if len(cohort_df) < 20:  # Skip very small cohorts
                        continue
                        
                    # Run simplified statistical test on this cohort
                    # This is a simplified version - in practice you'd want to run the full
                    # candidate generation logic on each cohort
                    cohort_result = _run_cohort_statistical_test(cohort_df, play_id, candidate.get('metric', ''))
                    
                    if cohort_result and cohort_result.get('n', 0) > 0:
                        cohort_results[cohort_name] = cohort_result
                
                # Pool results across cohorts
                if len(cohort_results) >= 2:
                    pooled_result = pool_cohort_results(cohort_results, min_cohort_size=20)
                    
                    if pooled_result.get('cohort_count', 0) >= 2:
                        # Enhance candidate with cohort-pooled statistics
                        enhanced_candidate = candidate.copy()
                        
                        # Update statistical measures
                        original_p = enhanced_candidate.get('p', 1.0)
                        pooled_p = pooled_result.get('p', 1.0)
                        
                        if pooled_p < original_p:  # Only improve, never worsen
                            enhanced_candidate['p'] = pooled_p
                            enhanced_candidate['p_original'] = original_p
                            enhanced_candidate['cohort_enhanced'] = True
                            enhanced_candidate['cohort_count'] = pooled_result.get('cohort_count', 0)
                            enhanced_candidate['cohort_consistency'] = pooled_result.get('cohort_consistency', 0.0)
                            enhanced_candidate['cohorts_used'] = pooled_result.get('cohorts_used', [])
                            
                            debug_log('actions', f"Cohort enhancement: {play_id} p-value {original_p:.3f} → {pooled_p:.3f} using {pooled_result['cohort_count']} cohorts")
                
                enhanced_candidates.append(candidate)
                
            except Exception as e:
                # If cohort analysis fails for this candidate, keep original
                enhanced_candidates.append(candidate)
        
        return enhanced_candidates
        
    except Exception as e:
        debug_log('actions', f"Cohort analysis failed: {e}")
        return candidates


def _run_cohort_statistical_test(cohort_df: pd.DataFrame, play_id: str, metric: str) -> dict:
    """
    Run simplified statistical test on a single cohort.
    
    Args:
        cohort_df: Cohort dataframe
        play_id: Play identifier
        metric: Metric to test
        
    Returns:
        Dictionary with statistical results
    """
    try:
        # This is a simplified version - you'd implement the specific statistical test
        # based on the metric and play_id
        
        n = len(cohort_df['customer_id'].unique())
        if n < 20:
            return None
            
        # For demo purposes, return basic structure
        # In practice, you'd implement the actual statistical calculations here
        result = {
            'n': n,
            'effect_abs': 0.0,  # Would calculate actual effect
            'p': 1.0,  # Would calculate actual p-value
            'metric': metric
        }
        
        return result
        
    except Exception:
        return None


def _get_window_matched_aov(aligned: Dict[str, Any], window_days: int) -> float:
    """
    Get AOV from the appropriate window data structure for accurate revenue calculation.
    
    Args:
        aligned: Multi-window or single-window aligned data
        window_days: Window size being analyzed (7, 28, 56, 90)
    
    Returns:
        AOV value from the most appropriate data source
    """
    window_key = f"L{window_days}"
    
    # Try to get AOV from the specific window being analyzed
    if window_key in aligned:
        window_data = aligned[window_key]
        
        # Prefer prior AOV (more stable for revenue projection)
        prior_aov = window_data.get("prior", {}).get("aov")
        if prior_aov and not np.isnan(prior_aov):
            return float(prior_aov)
            
        # Fallback to recent AOV from same window
        recent_aov = window_data.get("aov")
        if recent_aov and not np.isnan(recent_aov):
            return float(recent_aov)
    
    # Fallback to other reliable windows (prioritize L28 as baseline)
    fallback_windows = ["L28", "L56", "L90", "L7"]
    if window_key in fallback_windows:
        # Remove current window to avoid duplicate checking
        fallback_windows.remove(window_key)
    
    for fallback_window in fallback_windows:
        if fallback_window in aligned:
            window_data = aligned[fallback_window]
            # Require minimum order volume for reliability
            if window_data.get("orders", 0) >= 10:
                aov = window_data.get("aov")
                if aov and not np.isnan(aov):
                    return float(aov)
    
    # Final fallback: look for legacy single-window AOV fields
    legacy_aov = aligned.get("prior_aov") or aligned.get("recent_aov")
    if legacy_aov and not np.isnan(legacy_aov):
        return float(legacy_aov)
    
    return 0.0




def _compute_candidates(g: pd.DataFrame, aligned: Dict[str, Any], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    cands: List[Dict[str, Any]] = []

    # ----------------------------------------------------------------
    # M4a T4a.1/T4a.2/T4a.3: NaN-out fabricated stats and stamp evidence_class.
    #
    # Two flag-gated transforms are applied to candidate dicts BEFORE they
    # leave _compute_candidates:
    #
    #   STATS_NAN_FOR_HARDCODED=true  -> for plays whose registry default class
    #     is "targeting" (and therefore whose p/effect/CI today come from
    #     hardcoded constants in this function), replace those stats with NaN
    #     so downstream scoring / FDR / CI-based confidence sees "no measured
    #     evidence" instead of a fabricated value. Empirically-computed plays
    #     (winback, discount_hygiene, repeat-rate analyses) are untouched.
    #
    #   EVIDENCE_CLASS_ENFORCED=true  -> attach the deterministic
    #     evidence_class lookup from src.evidence.classify_evidence so M5-M8
    #     can read it. Default off in M4a; M4b flips on. T4a.3.
    #
    # When both flags are off (the M4a default), behavior is byte-identical
    # to the M3 baseline — the helpers are no-ops and no new keys are stamped.
    # ----------------------------------------------------------------
    _stats_nan_flag = bool(cfg.get("STATS_NAN_FOR_HARDCODED", False))
    _evidence_class_flag = bool(cfg.get("EVIDENCE_CLASS_ENFORCED", False))

    # Lazy imports keep action_engine free of M2/M4a deps when the flags are
    # off (preserves the "no behavior change with flags off" invariant).
    _classify_evidence = None
    _PLAYS_REG = None
    _TARGETING_RECLASSIFY: frozenset = frozenset()
    if _stats_nan_flag or _evidence_class_flag:
        try:
            from .evidence import classify_evidence as _classify_evidence
            from .evidence import TARGETING_RECLASSIFY_PLAYS as _TARGETING_RECLASSIFY
            from .play_registry import PLAYS as _PLAYS_REG
        except Exception:
            _classify_evidence = None
            _PLAYS_REG = None
            _TARGETING_RECLASSIFY = frozenset()

    # T4a.1: explicit list of legacy plays whose p/effect/CI today come from
    # hardcoded inline literals in _compute_candidates rather than from data.
    # This is the audit list from memory.md and the implementation plan
    # (M4a, T4a.1). The list is intentionally play_id-explicit (not registry-
    # class-derived) so a play whose registry default is "measured" but whose
    # current emitter still uses fabricated constants (e.g.,
    # frequency_accelerator) is also covered.
    _PLAYS_WITH_FABRICATED_STATS = frozenset({
        "frequency_accelerator",
        "aov_momentum",
        "retention_mastery",
        "journey_optimization",
        "category_expansion",
        "subscription_nudge",
        "routine_builder",
        "empty_bottle",
    })

    def _maybe_nan_fabricated_stats(cand: Dict[str, Any]) -> Dict[str, Any]:
        """Replace fabricated p/effect/CI with NaN.

        Behind STATS_NAN_FOR_HARDCODED. Operates in-place on ``cand`` and
        returns it for convenience. Plays not in the audit list (e.g.,
        winback_21_45 and discount_hygiene, which compute their stats
        empirically) are untouched.
        """
        if not _stats_nan_flag:
            return cand
        play_id = str(cand.get("play_id") or "")
        if play_id not in _PLAYS_WITH_FABRICATED_STATS:
            return cand
        cand["p"] = float("nan")
        cand["q"] = float("nan")
        cand["effect_abs"] = float("nan")
        cand["ci_low"] = float("nan")
        cand["ci_high"] = float("nan")
        return cand

    def _maybe_attach_evidence_class(cand: Dict[str, Any]) -> Dict[str, Any]:
        """Stamp ``evidence_class`` on the candidate per src.evidence.

        Behind EVIDENCE_CLASS_ENFORCED. The classifier raises on a NaN-p
        candidate whose registry default is measured/directional; we let that
        bubble (it is the engine-bug invariant from DS Architect QA Change 3).

        M4b T4b.1: plays in ``TARGETING_RECLASSIFY_PLAYS`` are deterministically
        reclassified to ``targeting`` regardless of any computed p/effect/CI.
        For these plays we do NOT call ``classify_evidence`` (which would
        raise on a directional play with NaN p, e.g. ``empty_bottle``); we
        write the targeting class directly. Their ``measurement.*`` block
        becomes ``None`` in the EngineRun mapper because the mapper drops
        measurement when ``evidence_class == "targeting"`` (see
        ``engine_run_adapter._build_measurement_from_legacy``).
        """
        if not _evidence_class_flag or _classify_evidence is None:
            return cand
        play_id = str(cand.get("play_id") or "")
        if play_id in _TARGETING_RECLASSIFY:
            # T4b.1: deterministic targeting. Skip the classifier — the
            # registry default for some of these (e.g. empty_bottle) is
            # ``directional`` and a NaN-p directional input would raise.
            cand["evidence_class"] = "targeting"
            return cand
        ec = _classify_evidence(cand, _PLAYS_REG)
        # Store the string value for round-trip with engine_run.EvidenceClass.
        cand["evidence_class"] = getattr(ec, "value", str(ec))
        return cand

    def _finalize_candidate(cand: Dict[str, Any]) -> Dict[str, Any]:
        """Apply both M4a transforms to a candidate dict."""
        _maybe_nan_fabricated_stats(cand)
        _maybe_attach_evidence_class(cand)
        return cand

    # Extract business performance metrics for adaptive conversion scaling
    business_metrics = extract_business_metrics(aligned)

    # Helper: recent window and weekly scalars
    maxd_all = pd.to_datetime(g["Created at"]).max()
    win_days = int(aligned.get("window_days") or 28)
    recent_start_win = maxd_all - pd.Timedelta(days=win_days - 1)
    weeks_in_window = max(1.0, win_days / 7.0)
    # Weekly baseline from recent window net_sales to cap unrealistic lifts
    try:
        grw = g[(g["Created at"] >= recent_start_win)].copy()
        weekly_baseline = float(grw.get("net_sales", pd.Series(dtype=float)).sum()) / weeks_in_window
    except Exception:
        weekly_baseline = 0.0

    # Repeat rate (in-window definition: share of customers with 2+ orders within the window)
    # Build recent/prior windows aligned with win_days
    recent_end = maxd_all
    recent_start = recent_end - pd.Timedelta(days=win_days - 1)
    prior_end = recent_start - pd.Timedelta(seconds=1)
    prior_start = prior_end - pd.Timedelta(days=win_days - 1)

    def _repeat_share_in_window(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp):
        w = df[(df["Created at"] >= start) & (df["Created at"] <= end)].copy()
        if w.empty:
            return 0, 0, 0.0
        per = (w.groupby("customer_id")["Name"].nunique() if 'Name' in w.columns else w.groupby("customer_id").size())
        x = int((per > 1).sum())
        n = int(per.shape[0])
        rate = float(x / n) if n > 0 else 0.0
        return x, n, rate

    x1, n1, rate_recent = _repeat_share_in_window(g, recent_start, recent_end)
    x2, n2, rate_prior  = _repeat_share_in_window(g, prior_start, prior_end)

    pval = two_proportion_z_test(x1, n1, x2, n2) if (n1 and n2) else 1.0
    # Wilson CI for each period; derive conservative CI for difference
    try:
        from .stats import wilson_ci
        r1_lo, r1_hi = wilson_ci(x1, n1, alpha=0.05) if n1 else (0.0, 0.0)
        r0_lo, r0_hi = wilson_ci(x2, n2, alpha=0.05) if n2 else (0.0, 0.0)
        ci_lo_diff = r1_lo - r0_hi
        ci_hi_diff = r1_hi - r0_lo
    except Exception:
        ci_lo_diff = None; ci_hi_diff = None
    effect_pts  = rate_recent - rate_prior  # absolute delta in points (e.g., +0.024)

    # Simplified realistic revenue calculation using conversion rates
    prior_repeat_baseline = rate_prior if rate_prior > 0 else 0.15  # retained for receipts/backward compat
    source_window = aligned.get("window_days", 28)
    revenue_per_order = _get_window_matched_aov(aligned, source_window)

    # Use simplified conversion rate approach instead of complex historical calculations
    projection_winback = calculate_28d_revenue(
        audience=n1,
        play_id="winback_21_45",
        aov=revenue_per_order,
        source_window=source_window,
        vertical_mode=get_vertical_mode(),
        business_stage=get_business_stage(),
        business_metrics=business_metrics
    )

    expected = projection_winback['base']
    expected_opt = projection_winback['optimistic']

    debug_log('revenue', f"Winback {n1} audience → ${expected:.0f} (opt ${expected_opt:.0f})")

    cands.append({
        "id": "repeat_rate_improve",
        "play_id": "winback_21_45",
        "metric": "repeat_rate",
        "n": n1 + n2,
        "effect_abs": effect_pts,
        "p": pval,
        "q": np.nan,                     # set later by BH
        "ci_low": ci_lo_diff, "ci_high": ci_hi_diff,
        "expected_$": expected,
        "expected_$_optimistic": expected_opt,
        "revenue_breakdown": projection_winback.get('details', {}),
        "min_n": cfg["MIN_N_WINBACK"],
        "effect_floor": cfg["REPEAT_PTS_FLOOR"],
        "rationale": f"Repeat share {rate_recent:.1%} vs {rate_prior:.1%} (Δ {effect_pts:+.1%}).",
        "audience_size": n1,
        "attachment": "segment_winback_21_45.csv",
        "baseline_rate": prior_repeat_baseline,
    })


    # Order Size Comparison
    # Statistical test comparing individual order amounts between periods (Welch t-test)
    # Note: This tests whether individual order sizes differ, not true period-level AOV
    maxd = pd.to_datetime(g["Created at"]).max()
    start = maxd - pd.Timedelta(days=aligned["window_days"] - 1)
    rec = g[g["Created at"] >= start]["net_sales"].astype(float).values
    pri = g[(g["Created at"] < start) & (g["Created at"] >= start - pd.Timedelta(days=aligned["window_days"]))]["net_sales"].astype(float).values

    if rec.size > 0 and pri.size > 0:
        pval = welch_t_test(rec, pri)
        m1, m2 = float(np.mean(rec)), float(np.mean(pri))
        effect_pct = (m1 - m2) / m2 if m2 else 0.0
        # Simplified realistic AOV increase calculation using conversion rates
        source_window = aligned.get("window_days", 28)
        recent_start = maxd - pd.Timedelta(days=source_window)
        recent_customers = g[g["Created at"] >= recent_start]["customer_id"].nunique()

        # Use percentage effect for AOV calculation with conversion rate approach
        projection_bestseller = calculate_28d_revenue(
            audience=recent_customers,
            play_id="bestseller_amplify",
            aov=m2,  # Prior period AOV as baseline
            source_window=source_window,
            effect_size=abs(effect_pct),  # Use percentage effect
            vertical_mode=get_vertical_mode(),
            business_stage=get_business_stage(),
            business_metrics=business_metrics
        )

        expected = projection_bestseller['base']
        expected_opt = projection_bestseller['optimistic']

        debug_log('revenue', f"AOV momentum {recent_customers} audience → ${expected:.0f} (opt ${expected_opt:.0f})")

        cands.append({
            "id": "aov_increase",
            "play_id": "bestseller_amplify",
            "metric": "aov",
            "n": int(rec.size + pri.size),
            "effect_abs": effect_pct,
            "p": pval,
            "q": np.nan,
            "ci_low": None, "ci_high": None,
            "expected_$": expected,
            "expected_$_optimistic": expected_opt,
            "revenue_breakdown": projection_bestseller.get('details', {}),
            "min_n": cfg["MIN_N_SKU"],
            "effect_floor": cfg["AOV_EFFECT_FLOOR"],
            "rationale": f"Order sizes {m1:.2f} vs {m2:.2f} (Δ {effect_pct:+.1%}) - amplifying bestseller to increase AOV.",
            "audience_size": int(rec.size),
            "attachment": "segment_bestseller_amplify.csv",
            "baseline_rate": aligned["prior_repeat_rate"] or 0.15,
        })


    # Discount rate depth (average discount per order): Welch t-test on per-order discount rates
    rec_dr = g[g["Created at"] >= start]["discount_rate"].astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    pri_dr = g[(g["Created at"] < start) & (g["Created at"] >= start - pd.Timedelta(days=aligned["window_days"]))]["discount_rate"].astype(float).replace([np.inf, -np.inf], np.nan).dropna()

    # Clean discount rate outliers: cap at reasonable bounds (0-80%)
    rec_dr_original = rec_dr.copy()
    pri_dr_original = pri_dr.copy()
    rec_dr = rec_dr[(rec_dr >= 0) & (rec_dr <= 0.8)].values
    pri_dr = pri_dr[(pri_dr >= 0) & (pri_dr <= 0.8)].values

    n1, n2 = int(rec_dr.size), int(pri_dr.size)
    if n1 > 0 and n2 > 0:
        m1, m2 = float(np.mean(rec_dr)), float(np.mean(pri_dr))
        # Positive effect means reduction in discount depth (prior - recent)
        effect_pts = m2 - m1

        # Debug discount rate calculation
        debug_log('revenue_detail', f"Discount rates recent={m1:.4f} ({len(rec_dr):,}), prior={m2:.4f} ({len(pri_dr):,}), effect={effect_pts*100:.2f}% pts")
        debug_log('revenue_detail', f"Discount outliers removed: recent={len(rec_dr_original) - len(rec_dr)}, prior={len(pri_dr_original) - len(pri_dr)}")
        # p-value via Welch t-test where possible
        try:
            pval_dr = welch_t_test(rec_dr, pri_dr) if (n1 > 1 and n2 > 1) else np.nan
        except Exception:
            pval_dr = np.nan
        # Simplified discount hygiene calculation using conversion rates
        source_window = aligned.get("window_days", 28)
        recent_aov = _get_window_matched_aov(aligned, source_window)

        # Use simplified conversion rate approach for margin improvement
        projection_discount = calculate_28d_revenue(
            audience=n1,
            play_id="discount_hygiene",
            aov=recent_aov,
            source_window=source_window,
            effect_size=abs(effect_pts),  # Discount reduction percentage
            vertical_mode=get_vertical_mode(),
            business_stage=get_business_stage(),
            business_metrics=business_metrics
        )

        expected_dr = projection_discount['base']
        expected_dr_opt = projection_discount['optimistic']

        debug_log('revenue', f"Discount hygiene {n1} audience → ${expected_dr:.0f} (opt ${expected_dr_opt:.0f})")

        cands.append({
            "id": "discount_hygiene",
            "play_id": "discount_hygiene",
            "metric": "discount_rate",
            "n": n1 + n2,
            "effect_abs": effect_pts,
            "p": pval_dr,
            "q": np.nan,
            "ci_low": None, "ci_high": None,
            "expected_$": expected_dr,
            "expected_$_optimistic": expected_dr_opt,
            "revenue_breakdown": projection_discount.get('details', {}),
            "min_n": cfg["MIN_N_SKU"],
            "effect_floor": cfg["DISCOUNT_PTS_FLOOR"],
            "rationale": f"Avg discount depth {m1:.1%} vs {m2:.1%} (Δ reduction {effect_pts:+.1%}).",
            "audience_size": n1,
            "attachment": "segment_discount_hygiene.csv",
            "baseline_rate": aligned["prior_repeat_rate"] or 0.15,
        })

    # --- Subscription nudge: customers with ≥3 orders of the same product in 90 days ---
    try:
        maxd2 = maxd_all
        start90 = maxd2 - pd.Timedelta(days=90)
        gg = g[g["Created at"] >= start90].copy()
        if ("lineitem_any" in gg.columns) or ("products_concat" in gg.columns) or ("Lineitem name" in gg.columns):
            rep = build_g_items(gg)
            # Choose product column: prefer base when normalization is enabled
            prod_col = 'product_key'
            try:
                if bool(cfg.get('FEATURES_PRODUCT_NORMALIZATION', False)) and 'product_key_base' in rep.columns:
                    prod_col = 'product_key_base'
            except Exception:
                pass
            # Per-product threshold using vertical + product detection
            rep["_thr"] = rep[prod_col].astype(str).apply(lambda s: subscription_threshold_for_product(s, cfg))
            cohort = rep[rep['orders_product'] >= rep["_thr"]]
            audience = int(cohort['customer_id'].nunique())
            aov_recent = float(aligned.get("recent_aov") or aligned.get("L28_aov") or np.nan)
            if np.isnan(aov_recent):
                aov_recent = float(np.nanmean(g.get("AOV", []))) if "AOV" in g.columns else 0.0
            # Recent orders by audience in window
            aud_ids = set(cohort['customer_id'].astype(str))
            recent_orders_aud = g[(g["Created at"] >= recent_start_win) & (g["customer_id"].astype(str).isin(aud_ids))]
            weekly_orders = float(recent_orders_aud['Name'].nunique() if 'Name' in recent_orders_aud.columns else len(recent_orders_aud)) / weeks_in_window
            # Conservative weekly uplift rate for subscription (spread over ~12 weeks)
            sub_weekly_uplift = 0.25 / 12.0
            window_expected = max(0.0, weekly_orders * (aov_recent or 0.0) * sub_weekly_uplift)

            # Apply decay factor for window size instead of linear normalization
            source_window = aligned.get("window_days", 28)
            if source_window == 28:
                expected = window_expected
            else:
                # Apply decay factor for multi-window projections
                decay = DECAY_FACTORS.get(source_window, 0.5)
                expected = window_expected * decay
            # Compliance-aware adjustment for supplements: dampen expected if observed intervals imply poor compliance
            try:
                # products in cohort
                products = cohort[prod_col].astype(str).unique().tolist()
                comp_factors = []
                for p_name in products:
                    ptype, supply_days = categorize_product(p_name)
                    if ptype != 'supplement':
                        continue
                    orders_p = gg[gg['lineitem_any'].astype(str) == p_name].copy()
                    orders_p = orders_p.sort_values('Created at')
                    med_ipi = orders_p['Created at'].diff().dt.days.median()
                    if pd.isna(med_ipi):
                        continue
                    if med_ipi > supply_days * 1.5:
                        comp_factors.append(0.5)
                    elif med_ipi > supply_days * 1.2:
                        comp_factors.append(0.75)
                    else:
                        comp_factors.append(1.0)
                if comp_factors:
                    expected *= float(np.mean(comp_factors))
            except Exception:
                pass
            # Cap at 25% of weekly baseline to avoid spikes
            if weekly_baseline > 0:
                expected = min(expected, 0.25 * weekly_baseline)
            # Empirical baseline + power check for conversion in next 28d
            p_sub = np.nan
            baseline_conv = None
            try:
                A_start = maxd2 - pd.Timedelta(days=180)
                A_end   = maxd2 - pd.Timedelta(days=90)
                B_start = maxd2 - pd.Timedelta(days=270)
                B_end   = maxd2 - pd.Timedelta(days=180)
                def _conv_next28(start, end):
                    w = g[(g["Created at"] >= start) & (g["Created at"] <= end)].copy()
                    if w.empty or "lineitem_any" not in w.columns:
                        return (0, 0)
                    r = (w.groupby(["customer_id", "lineitem_any"])['Name']
                           .nunique().reset_index(name='orders_product'))
                    aud_ids_local = set(r[r['orders_product'] >= 3]['customer_id'].astype(str))
                    if not aud_ids_local:
                        return (0, 0)
                    after = g[(g["Created at"] > end) & (g["Created at"] <= end + pd.Timedelta(days=28))]
                    conv_set = set(after['customer_id'].astype(str)) if not after.empty else set()
                    nloc = len(aud_ids_local)
                    xloc = sum(1 for c in aud_ids_local if c in conv_set)
                    return (xloc, nloc)
                xA, nA = _conv_next28(A_start, A_end)
                xB, nB = _conv_next28(B_start, B_end)
                if (nA>0 and nB>0):
                    baseline_conv = (xA + xB) / max(1, (nA + nB))
                    p_sub = two_proportion_z_test(xA, nA, xB, nB)
            except Exception:
                baseline_conv = None

            # Power requirement: ensure audience meets minimum to detect an absolute +5pt lift
            expected_delta = 0.05
            baseline_for_power = float(baseline_conv) if baseline_conv is not None else 0.15
            try:
                n_needed = int(required_n_for_proportion(baseline_for_power, expected_delta, alpha=0.05, power=0.8))
            except Exception:
                n_needed = int(cfg.get("MIN_N_SKU", 60))

            if audience >= max(50, int(cfg.get("MIN_N_SKU", 60) // 2)):
                # G-4 (2026-05-10): subscription_nudge is permanently a
                # targeting play. The historical inline ``effect_abs=0.05``
                # / ``effect_floor=0.05`` / fabricated p-value constants
                # were placeholders that surfaced as if measured under
                # tight gates (audit §B-3, KI-24). They are removed
                # structurally here, NOT behind a flag. The candidate
                # carries ``evidence_class="targeting"`` so the
                # EngineRun mapper drops the measurement block
                # (``_build_measurement_from_legacy`` short-circuits on
                # ``evidence_class == "targeting"``). NaN fabricated
                # stat fields keep B-3 hardcoded-fallback scanner happy
                # and stay aligned with the M4b flag-on shape.
                cands.append({
                    "id": "subscription_nudge",
                    "play_id": "subscription_nudge",
                    "metric": "subscription",
                    "n": audience,
                    "effect_abs": float("nan"),
                    "p": float("nan"),
                    "q": np.nan,
                    "ci_low": None, "ci_high": None,
                    "expected_$": expected,
                    # Use power-based minimum N if higher than config minimum
                    "min_n": max(int(cfg.get("MIN_N_SKU", 60)), n_needed),
                    "effect_floor": float("nan"),
                    "rationale": f"Found {audience} customers with ≥3 purchases of the same product in 90d — ideal for subscription.",
                    "audience_size": audience,
                    "attachment": "segment_subscription_nudge.csv",
                    "baseline_rate": None,
                    "evidence_class": "targeting",
                })
    except Exception:
        pass


    # --- Routine builder: skincare single-product purchasers (bundle opportunity) ---
    try:
        anchor = pd.to_datetime(g["Created at"]).max()
        recent_start = anchor - pd.Timedelta(days=60)
        lookback_start = anchor - pd.Timedelta(days=90)
        gr = g[(g["Created at"] >= recent_start)].copy()
        # Focus on skincare category
        if "category" in gr.columns:
            gr_skin = gr[gr["category"].astype(str).str.lower() == "skincare"].copy()
        else:
            gr_skin = gr.copy()
        # Candidates: customers in skincare recently
        cand_ids = set(gr_skin["customer_id"].astype(str))
        if cand_ids:
            gl = g[(g["Created at"] >= lookback_start)].copy()
            gl["customer_id"] = gl["customer_id"].astype(str)
            # Distinct products in lookback per customer (prefer g_items)
            try:
                gi2 = build_g_items(gl)
                if gi2 is not None and not gi2.empty:
                    k = gi2.groupby("customer_id")["product_key"].nunique()
                    single_prod_ids = set(k[k <= 1].index)
                else:
                    raise ValueError('g_items empty')
            except Exception:
                if "lineitem_any" in gl.columns:
                    k = gl.groupby("customer_id")["lineitem_any"].nunique()
                    single_prod_ids = set(k[k <= 1].index)
                else:
                    single_prod_ids = set()
            targets = list(cand_ids.intersection(single_prod_ids))
            audience_rb = int(len(targets))
            if audience_rb > 0:
                # Get AOV using window-matched logic for multi-window compatibility
                source_window = aligned.get("window_days", 28)
                aov_recent = _get_window_matched_aov(aligned, source_window)
                # G-4 (2026-05-10): the prior ``rb_ids = set(targets)`` line
                # was a setup for the Welch-t p-value path on AOV cohorts,
                # which has been removed (routine_builder is permanently
                # targeting; no measurement object emitted). Sizing below
                # continues to use ``audience_rb`` / ``aov_recent`` only.

                # Simplified routine builder calculation using conversion rates
                source_window = aligned.get("window_days", 28)

                # Use simplified conversion rate approach for bundling
                projection_rb = calculate_28d_revenue(
                    audience=audience_rb,
                    play_id="routine_builder",
                    aov=aov_recent or 0.0,
                    source_window=source_window,
                    vertical_mode=get_vertical_mode(),
                    business_stage=get_business_stage(),
                    business_metrics=business_metrics
                )

                expected_rb = projection_rb['base']
                expected_rb_opt = projection_rb['optimistic']

                debug_log('revenue', f"Routine builder {audience_rb} audience → ${expected_rb:.0f} (opt ${expected_rb_opt:.0f})")
                # G-4 (2026-05-10): routine_builder is permanently a
                # targeting play. The historical inline ``effect_abs=0.08``
                # constant and the Welch-t p-value-only path (no
                # measured effect; see project_phase4_routine_builder_open.md)
                # are removed structurally here, NOT behind a flag.
                # Audience builder + AOV projection remain (used for
                # sizing context); the fabricated measurement object
                # is gone. The EngineRun mapper drops measurement when
                # ``evidence_class == "targeting"``.
                cands.append({
                    "id": "routine_builder",
                    "play_id": "routine_builder",
                    "metric": "bundle_aov",
                    "n": audience_rb,
                    "effect_abs": float("nan"),
                    "p": float("nan"),
                    "q": np.nan,
                    "ci_low": None, "ci_high": None,
                    "expected_$": expected_rb,
                    "expected_$_optimistic": expected_rb_opt,
                    "revenue_breakdown": projection_rb.get('details', {}),
                    "min_n": int(cfg.get("MIN_N_SKU", 60)),
                    "effect_floor": float("nan"),
                    "rationale": f"{audience_rb} skincare single-product buyers — bundle to complete routine.",
                    "audience_size": audience_rb,
                    "attachment": "segment_routine_builder.csv",
                    "baseline_rate": None,
                    "evidence_class": "targeting",
                })
    except Exception:
        pass


    # --- Empty bottle reminder: size-based depletion window ---
    try:
        # Last purchase per customer
        last = g.sort_values("Created at").groupby("customer_id").tail(1).copy()
        if "lineitem_any" in last.columns and "days_since_last" in last.columns:
            names = last["lineitem_any"].astype(str).str.lower()
            dsl = last["days_since_last"].astype(float)
            # crude size parsing
            size_days = []
            for s in names:
                if "100ml" in s or "3.4 oz" in s or "3.4oz" in s:
                    size_days.append(75)
                elif "50ml" in s or "1.7 oz" in s or "1.7oz" in s:
                    size_days.append(40)
                elif "30ml" in s or "1 oz" in s or "1oz" in s:
                    size_days.append(25)
                else:
                    size_days.append(None)
            last = last.assign(_deplete_days=size_days)
            window = last[~pd.isna(last["_deplete_days"])].copy()
            # Target if within +/- 3 days of depletion
            m = (window["days_since_last"] >= (window["_deplete_days"] - 3)) & (window["days_since_last"] <= (window["_deplete_days"] + 3))
            targets_eb = window.loc[m, "customer_id"].astype(str).unique().tolist()
            audience_eb = int(len(targets_eb))
            if audience_eb > 0:
                aov_recent = float(aligned.get("recent_aov") or aligned.get("L28_aov") or np.nan)
                if np.isnan(aov_recent):
                    aov_recent = float(np.nanmean(g.get("AOV", []))) if "AOV" in g.columns else 0.0
                # Assume ~10% weekly conversion on timely reminders
                weekly_reminders = audience_eb  # approximate per week at steady-state
                conv_weekly = 0.10
                window_expected_eb = max(0.0, weekly_reminders * conv_weekly * (aov_recent or 0.0))

                # Apply decay factor for window size instead of linear normalization
                source_window = aligned.get("window_days", 28)
                if source_window == 28:
                    expected_eb = window_expected_eb
                else:
                    # Apply decay factor for multi-window projections
                    decay = DECAY_FACTORS.get(source_window, 0.5)
                    expected_eb = window_expected_eb * decay

                if weekly_baseline > 0:
                    # Convert weekly baseline to monthly using 4x multiplier
                    monthly_baseline = weekly_baseline * 4.0
                    expected_eb = min(expected_eb, 0.25 * monthly_baseline)
                # Empirical p-value: near-depletion reorder within 14 days for two historic cohorts
                try:
                    def _deplete_conv(start, end):
                        ww = g[(g["Created at"] >= start) & (g["Created at"] <= end)].copy()
                        if ww.empty or "lineitem_any" not in ww.columns or "days_since_last" not in ww.columns:
                            return (0, 0)
                        nm = ww["lineitem_any"].astype(str).str.lower()
                        size_days = np.where(nm.str.contains("100ml|3.4 oz|3.4oz"), 75,
                                     np.where(nm.str.contains("50ml|1.7 oz|1.7oz"), 40,
                                     np.where(nm.str.contains("30ml|1 oz|1oz"), 25, np.nan)))
                        ww = ww.assign(_deplete_days=size_days)
                        w2 = ww[~pd.isna(ww["_deplete_days"])].copy()
                        if w2.empty:
                            return (0, 0)
                        m2 = (w2["days_since_last"] >= (w2["_deplete_days"] - 3)) & (w2["days_since_last"] <= (w2["_deplete_days"] + 3))
                        custs = set(w2.loc[m2, "customer_id"].astype(str))
                        if not custs:
                            return (0, 0)
                        after = g[(g["Created at"] > end) & (g["Created at"] <= end + pd.Timedelta(days=14))]
                        conv = set(after["customer_id"].astype(str)) if not after.empty else set()
                        return (sum(1 for c in custs if c in conv), len(custs))
                    A_start = maxd_all - pd.Timedelta(days=120)
                    A_end   = maxd_all - pd.Timedelta(days=60)
                    B_start = maxd_all - pd.Timedelta(days=180)
                    B_end   = maxd_all - pd.Timedelta(days=120)
                    xA, nA = _deplete_conv(A_start, A_end)
                    xB, nB = _deplete_conv(B_start, B_end)
                    if (nA>0 and nB>0):
                        p_eb = two_proportion_z_test(xA, nA, xB, nB)
                        try:
                            from .stats import wilson_ci
                            eA_lo, eA_hi = wilson_ci(xA, nA, alpha=0.05)
                            eB_lo, eB_hi = wilson_ci(xB, nB, alpha=0.05)
                            ci_eb_lo, ci_eb_hi = eA_lo - eB_hi, eA_hi - eB_lo
                        except Exception:
                            ci_eb_lo = None; ci_eb_hi = None
                    else:
                        p_eb = 0.06 if audience_eb<80 else 0.05
                        ci_eb_lo = None; ci_eb_hi = None
                except Exception:
                    p_eb = 0.06 if audience_eb<80 else 0.05
                    ci_eb_lo = None; ci_eb_hi = None
                cands.append({
                    "id": "empty_bottle",
                    "play_id": "empty_bottle",
                    "metric": "reorder",
                    "n": audience_eb,
                    "effect_abs": conv_weekly,
                    "p": p_eb,
                    "q": np.nan,
                    "ci_low": ci_eb_lo, "ci_high": ci_eb_hi,
                    "expected_$": expected_eb,
                    "min_n": int(cfg.get("MIN_N_SKU", 60)),
                    "effect_floor": 0.03,
                    "rationale": f"{audience_eb} customers near predicted depletion — timely reorder reminder.",
                    "audience_size": audience_eb,
                    "attachment": "segment_empty_bottle.csv",
                    "baseline_rate": None,
                })
    except Exception:
        pass

    # Phase 2: Generate High-Impact Action Portfolio candidates with segments
    debug_log('actions', "Phase 2: generating high-impact action portfolio")

    # Helper function to create segment CSV
    def _create_phase2_segment(customer_ids: list, segment_name: str, baseline_rate: float, gross_margin: float = 0.3):
        """Create segment CSV for Phase 2 actions"""
        try:
            import os
            segments_dir = "analysis/segments"
            os.makedirs(segments_dir, exist_ok=True)

            segment_df = pd.DataFrame({
                "customer_id": customer_ids,
                "segment": segment_name,
                "segment_n": len(customer_ids),
                "baseline_rate": baseline_rate,
                "gross_margin": gross_margin
            })

            filepath = f"{segments_dir}/segment_{segment_name}.csv"
            segment_df.to_csv(filepath, index=False)
            debug_log('actions', f"Segment {segment_name} created with {len(customer_ids)} customers")
            return filepath
        except Exception as e:
            debug_log('actions', f"Failed to create segment {segment_name}: {e}")
            return f"segment_{segment_name}.csv"

    # 1. frequency_accelerator: Customers with 2+ orders in L90, exclude recent orders last 14d
    try:
        l90_start = maxd_all - pd.Timedelta(days=90)
        l14_start = maxd_all - pd.Timedelta(days=14)

        # Find customers with 2+ orders in L90
        l90_orders = g[g["Created at"] >= l90_start]
        customer_order_counts = l90_orders["customer_id"].value_counts()
        repeat_customers = customer_order_counts[customer_order_counts >= 2].index.tolist()

        # Exclude customers with recent orders (last 14 days)
        recent_customers = set(g[g["Created at"] >= l14_start]["customer_id"].unique())
        eligible_frequency = [c for c in repeat_customers if c not in recent_customers]

        if len(eligible_frequency) >= 50:  # Minimum viable audience
            audience_freq = len(eligible_frequency)
            recent_aov = _get_window_matched_aov(aligned, win_days)

            # Create segment CSV
            segment_file = _create_phase2_segment(
                eligible_frequency,
                "frequency_accelerator",
                business_metrics.get('repeat_rate', 0.3)
            )

            projection_freq = calculate_28d_revenue(
                audience=audience_freq,
                play_id="frequency_accelerator",
                aov=recent_aov,
                source_window=win_days,
                vertical_mode=get_vertical_mode(),
                business_stage=get_business_stage(),
                business_metrics=business_metrics
            )

            expected_freq = projection_freq['base']
            expected_freq_opt = projection_freq['optimistic']

            cands.append({
                "id": "frequency_accelerator",
                "play_id": "frequency_accelerator",
                "metric": "frequency",
                "n": audience_freq,
                "effect_abs": 0.20,  # 20% frequency increase
                "p": 0.03,  # Assume good significance for proven repeat customers
                "q": np.nan,
                "ci_low": 0.15, "ci_high": 0.25,  # 15-25% range
                "expected_$": expected_freq,
                "expected_$_optimistic": expected_freq_opt,
                "revenue_breakdown": projection_freq.get('details', {}),
                "min_n": 50,
                "effect_floor": 0.10,  # 10% minimum frequency lift
                "rationale": f"Target {audience_freq} repeat customers (2+ orders L90) to accelerate purchase frequency.",
                "audience_size": audience_freq,
                "attachment": segment_file,
                "baseline_rate": business_metrics.get('repeat_rate', 0.3),
            })
            debug_log('actions', f"frequency_accelerator audience={audience_freq} eligible repeat customers")
        else:
            debug_log('actions', f"frequency_accelerator insufficient audience ({len(eligible_frequency)} < 50)")
    except Exception as e:
        debug_log('actions', f"frequency_accelerator generation error: {e}")

    # 2. aov_momentum: Recent customers in growth segments (AOV increasing), orders 7-30d ago
    try:
        l30_start = maxd_all - pd.Timedelta(days=30)
        l7_start = maxd_all - pd.Timedelta(days=7)

        # Find customers with orders 7-30 days ago
        momentum_period = g[(g["Created at"] >= l30_start) & (g["Created at"] < l7_start)]
        recent_customers_segment = momentum_period["customer_id"].unique().tolist()

        # Only generate if business shows AOV growth potential
        aov_growth_rate = business_metrics.get('aov_growth', 0.0)
        if aov_growth_rate > 0.02 and len(recent_customers_segment) >= 30:  # Need 2%+ AOV growth
            audience_aov = len(recent_customers_segment)
            recent_aov = _get_window_matched_aov(aligned, win_days)

            # Create segment CSV
            segment_file = _create_phase2_segment(
                recent_customers_segment,
                "aov_momentum",
                recent_aov
            )

            projection_aov = calculate_28d_revenue(
                audience=audience_aov,
                play_id="aov_momentum",
                aov=recent_aov,
                source_window=win_days,
                vertical_mode=get_vertical_mode(),
                business_stage=get_business_stage(),
                business_metrics=business_metrics
            )

            expected_aov = projection_aov['base']
            expected_aov_opt = projection_aov['optimistic']

            cands.append({
                "id": "aov_momentum",
                "play_id": "aov_momentum",
                "metric": "aov",
                "n": audience_aov,
                "effect_abs": aov_growth_rate * 1.5,  # Amplify existing growth by 50%
                "p": 0.04,  # Good significance for growth momentum
                "q": np.nan,
                "ci_low": aov_growth_rate * 1.2, "ci_high": aov_growth_rate * 1.8,
                "expected_$": expected_aov,
                "expected_$_optimistic": expected_aov_opt,
                "revenue_breakdown": projection_aov.get('details', {}),
                "min_n": 30,
                "effect_floor": 0.05,  # 5% minimum AOV improvement
                "rationale": f"Amplify AOV growth trend ({aov_growth_rate:+.1%}) for {audience_aov} recent customers.",
                "audience_size": audience_aov,
                "attachment": segment_file,
                "baseline_rate": recent_aov,
            })
            debug_log('actions', f"aov_momentum audience={audience_aov}, aov_growth={aov_growth_rate:+.1%}")
        else:
            debug_log('actions', f"aov_momentum insufficient growth ({aov_growth_rate:+.1%}) or audience ({len(recent_customers_segment)})")
    except Exception as e:
        debug_log('actions', f"aov_momentum generation error: {e}")

    # 3. retention_mastery: Customers at risk based on purchase timing patterns
    try:
        # Find customers with purchase patterns indicating churn risk
        customer_last_orders = g.groupby("customer_id")["Created at"].max()
        days_since_last = (maxd_all - customer_last_orders).dt.days

        # At-risk: haven't ordered in 45+ days
        at_risk_customers_series = days_since_last[days_since_last >= 45]
        at_risk_customers = at_risk_customers_series.index.tolist()

        # Filter for valuable customers (2+ historical orders)
        customer_order_counts = g["customer_id"].value_counts()
        valuable_at_risk = [c for c in at_risk_customers if customer_order_counts.get(c, 0) >= 2]

        if len(valuable_at_risk) >= 25:  # Minimum viable retention audience
            audience_retention = len(valuable_at_risk)
            recent_aov = _get_window_matched_aov(aligned, win_days)

            # Create segment CSV
            segment_file = _create_phase2_segment(
                valuable_at_risk,
                "retention_mastery",
                business_metrics.get('repeat_rate', 0.3)
            )

            projection_retention = calculate_28d_revenue(
                audience=audience_retention,
                play_id="retention_mastery",
                aov=recent_aov,
                source_window=win_days,
                vertical_mode=get_vertical_mode(),
                business_stage=get_business_stage(),
                business_metrics=business_metrics
            )

            expected_retention = projection_retention['base']
            expected_retention_opt = projection_retention['optimistic']

            cands.append({
                "id": "retention_mastery",
                "play_id": "retention_mastery",
                "metric": "retention",
                "n": audience_retention,
                "effect_abs": 0.07,  # 7% churn reduction
                "p": 0.02,  # Strong significance for retention impact
                "q": np.nan,
                "ci_low": 0.05, "ci_high": 0.10,  # 5-10% churn reduction range
                "expected_$": expected_retention,
                "expected_$_optimistic": expected_retention_opt,
                "revenue_breakdown": projection_retention.get('details', {}),
                "min_n": 25,
                "effect_floor": 0.03,  # 3% minimum churn reduction
                "rationale": f"Prevent churn for {audience_retention} at-risk valuable customers (45+ days since last order).",
                "audience_size": audience_retention,
                "attachment": segment_file,
                "baseline_rate": business_metrics.get('repeat_rate', 0.3),
            })
            debug_log('actions', f"retention_mastery audience={audience_retention} at-risk valuable customers")
        else:
            debug_log('actions', f"retention_mastery insufficient audience ({len(valuable_at_risk)} < 25)")
    except Exception as e:
        debug_log('actions', f"retention_mastery generation error: {e}")

    # 4. journey_optimization: Based on business health indicators
    try:
        # Generate based on business performance indicators
        returning_share = business_metrics.get('returning_share', 0.5)
        monthly_revenue = business_metrics.get('monthly_revenue', 50000)

        # High-performing businesses with good scale have funnel optimization potential
        if monthly_revenue > 75000 and returning_share > 0.7:
            # Estimate customers with funnel optimization potential (heuristic)
            estimated_customers = monthly_revenue / (recent_aov * 1.5)
            potential_optimization_customers = max(50, int(estimated_customers * 0.3))  # 30% optimization potential

            # For segmentation, take recent browsers/browsers who didn't convert (simplified heuristic)
            # Use recent non-repeat customers as proxy for funnel optimization opportunity
            recent_customers = g[g["Created at"] >= maxd_all - pd.Timedelta(days=60)]["customer_id"].unique()
            funnel_customers = recent_customers[:potential_optimization_customers].tolist()

            audience_journey = len(funnel_customers)

            if audience_journey >= 50:
                # Create segment CSV
                segment_file = _create_phase2_segment(
                    funnel_customers,
                    "journey_optimization",
                    0.15  # Baseline conversion rate
                )

                projection_journey = calculate_28d_revenue(
                    audience=audience_journey,
                    play_id="journey_optimization",
                    aov=recent_aov,
                    source_window=win_days,
                    vertical_mode=get_vertical_mode(),
                    business_stage=get_business_stage(),
                    business_metrics=business_metrics
                )

                expected_journey = projection_journey['base']
                expected_journey_opt = projection_journey['optimistic']

                cands.append({
                    "id": "journey_optimization",
                    "play_id": "journey_optimization",
                    "metric": "conversion",
                    "n": audience_journey,
                    "effect_abs": 0.30,  # 30% conversion improvement in funnels
                    "p": 0.05,  # Moderate significance for funnel improvements
                    "q": np.nan,
                    "ci_low": 0.20, "ci_high": 0.40,  # 20-40% conversion improvement range
                    "expected_$": expected_journey,
                    "expected_$_optimistic": expected_journey_opt,
                    "revenue_breakdown": projection_journey.get('details', {}),
                    "min_n": 50,
                    "effect_floor": 0.10,  # 10% minimum conversion improvement
                    "rationale": f"Optimize conversion funnels for {audience_journey} customers with drop-off patterns.",
                    "audience_size": audience_journey,
                    "attachment": segment_file,
                    "baseline_rate": 0.15,  # Assumed baseline conversion rate
                })
                debug_log('actions', f"journey_optimization audience={audience_journey} funnel opportunity")
            else:
                debug_log('actions', f"journey_optimization insufficient audience ({audience_journey} < 50)")
        else:
            debug_log('actions', "journey_optimization skipped: business metrics do not indicate funnel opportunity")
    except Exception as e:
        debug_log('actions', f"journey_optimization generation error: {e}")

    # 5. category_expansion: Single-category customers with 2+ orders
    try:
        # Find customers with 2+ orders but only in one category
        if 'lineitem_any' in g.columns:
            customer_stats = g.groupby('customer_id').agg({
                'lineitem_any': 'nunique',  # Number of unique categories
                'Name': 'count'  # Number of orders
            }).rename(columns={'lineitem_any': 'categories', 'Name': 'orders'})

            # Single-category customers with 2+ orders
            single_category_mask = (customer_stats['categories'] == 1) & (customer_stats['orders'] >= 2)
            single_category_customers = customer_stats[single_category_mask].index.tolist()

            if len(single_category_customers) >= 40:  # Minimum viable cross-sell audience
                audience_expansion = len(single_category_customers)
                recent_aov = _get_window_matched_aov(aligned, win_days)

                # Create segment CSV
                segment_file = _create_phase2_segment(
                    single_category_customers,
                    "category_expansion",
                    0.0  # Currently single-category
                )

                projection_expansion = calculate_28d_revenue(
                    audience=audience_expansion,
                    play_id="category_expansion",
                    aov=recent_aov,
                    source_window=win_days,
                    vertical_mode=get_vertical_mode(),
                    business_stage=get_business_stage(),
                    business_metrics=business_metrics
                )

                expected_expansion = projection_expansion['base']
                expected_expansion_opt = projection_expansion['optimistic']

                cands.append({
                    "id": "category_expansion",
                    "play_id": "category_expansion",
                    "metric": "conversion",
                    "n": audience_expansion,
                    "effect_abs": 0.40,  # 40% category expansion rate
                    "p": 0.04,  # Good significance for cross-sell
                    "q": np.nan,
                    "ci_low": 0.30, "ci_high": 0.50,  # 30-50% expansion rate range
                    "expected_$": expected_expansion,
                    "expected_$_optimistic": expected_expansion_opt,
                    "revenue_breakdown": projection_expansion.get('details', {}),
                    "min_n": 40,
                    "effect_floor": 0.20,  # 20% minimum expansion rate
                    "rationale": f"Cross-sell to {audience_expansion} single-category customers with 2+ orders.",
                    "audience_size": audience_expansion,
                    "attachment": segment_file,
                    "baseline_rate": 0.0,  # Currently single-category
                })
                debug_log('actions', f"category_expansion audience={audience_expansion} single-category repeat customers")
            else:
                debug_log('actions', f"category_expansion insufficient audience ({len(single_category_customers)} < 40)")
        else:
            debug_log('actions', "category_expansion skipped: category data unavailable")
    except Exception as e:
        debug_log('actions', f"category_expansion generation error: {e}")

    phase2_count = len([c for c in cands if c.get('play_id') in ['frequency_accelerator', 'aov_momentum', 'retention_mastery', 'journey_optimization', 'category_expansion']])
    debug_log('actions', f"Phase 2 complete: added {phase2_count} candidates")

    # M4a: apply NaN-ing of fabricated stats and stamp evidence_class on the
    # full candidate set. Both transforms are no-ops with M4a flags off, so
    # the M0 golden tree is byte-identical when STATS_NAN_FOR_HARDCODED and
    # EVIDENCE_CLASS_ENFORCED are both false.
    if _stats_nan_flag or _evidence_class_flag:
        for _c in cands:
            _finalize_candidate(_c)

    # Phase 3: Filter candidates by material impact thresholds
    debug_log('actions', "Phase 3: Material impact filtering")
    debug_log('actions', f"Original candidates: {len(cands)}")

    vertical_mode_env = get_vertical_mode()
    business_stage_env = get_business_stage()
    material_thresholds = get_material_thresholds(vertical_mode_env, business_stage_env, business_metrics, cfg)

    filtered_cands = []
    for cand in cands:
        play_id = cand.get('play_id', '')
        audience = cand.get('audience_size') or cand.get('n', 0)
        effect_size = cand.get('effect_abs', 0)

        # Calculate projected revenue for this candidate
        aov = aligned.get('aov', 85.0)  # Default AOV fallback
        vertical_mode = vertical_mode_env
        business_stage = business_stage_env

        projection_summary = calculate_28d_revenue(
            audience=audience,
            play_id=play_id,
            aov=aov,
            vertical_mode=vertical_mode,
            business_stage=business_stage,
            business_metrics=business_metrics
        )

        projected_revenue = projection_summary['base']
        projected_revenue_opt = projection_summary['optimistic']

        # Estimate confidence using the calibrated business confidence model
        try:
            confidence = _calculate_business_confidence(cand, cfg)
        except Exception:
            confidence = None

        # Determine action type and validate material impact
        action_type = get_action_type_from_play_id(play_id)
        is_material, reason = has_material_impact(
            action_type=action_type,
            effect_size=effect_size,
            audience=audience,
            projected_revenue=projected_revenue,
            confidence=confidence,
            thresholds=material_thresholds
        )

        if is_material:
            cand['material_impact_validated'] = True
            cand['projected_revenue'] = projected_revenue
            cand['projected_revenue_optimistic'] = projected_revenue_opt
            cand['revenue_breakdown'] = projection_summary.get('details', {})
            cand['material_thresholds'] = dict(material_thresholds)
            cand['validation_reason'] = reason
            filtered_cands.append(cand)
            debug_log('actions', f"ACCEPT {play_id}: {reason}")
        else:
            cand['material_impact_validated'] = False
            cand['rejection_reason'] = reason
            debug_log('actions', f"REJECT {play_id}: {reason}")

    debug_log('actions', f"Filtered candidates: {len(filtered_cands)} (removed {len(cands) - len(filtered_cands)})")

    # Only return candidates that meet material impact thresholds
    return filtered_cands

    

def _normalize_aligned(aligned: dict, cfg: dict) -> dict:
    """Accept nested KPI snapshot {L7:{...}, L28:{...}} or flat aligned, return appropriate structure.
    
    If ENABLE_MULTIWINDOW_SCORING=True: preserve multi-window structure for multi-window analysis
    Otherwise: flatten to single window from cfg['CHOSEN_WINDOW'] (default L28).
    """
    if aligned is None:
        return {}
    # If already flat, return as-is
    if 'window_days' in aligned and 'recent_n' in aligned:
        return aligned
    
    # Check if multi-window analysis is enabled
    enable_multiwindow = cfg.get('ENABLE_MULTIWINDOW_SCORING', True)
    window_keys = ['L7', 'L28', 'L56', 'L90']
    has_multiwindow = any(key in aligned for key in window_keys)
    
    # Check if we're forcing single-window mode (temporary debugging)
    force_single_window = cfg.get('_FORCE_SINGLE_WINDOW', False)
    
    if enable_multiwindow and has_multiwindow and not force_single_window:
        # Preserve multi-window structure - just return the nested data as-is
        debug_log('multiwindow_detail', '_normalize_aligned preserving multi-window structure')
        return aligned
    
    # If nested, flatten according to chosen window
    lbl = 'L7' if str((cfg or {}).get('CHOSEN_WINDOW', 'L28')).upper() == 'L7' else 'L28'
    block = (aligned.get(lbl) or {})
    prior = (block.get('prior') or {})
    days = 7 if lbl == 'L7' else 28
    anchor = aligned.get('anchor')
    # Compute bounds from anchor for completeness
    rs = re = ps = pe = None
    try:
        if anchor is not None:
            anchor_ts = pd.Timestamp(anchor)
            re = anchor_ts.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
            rs = re.normalize() - pd.Timedelta(days=days - 1)
            pe = rs - pd.Timedelta(seconds=1)
            ps = pe.normalize() - pd.Timedelta(days=days - 1)
    except Exception:
        pass
    return {
        'window_days': days,
        'recent_start': str(rs.date()) if rs is not None else None,
        'recent_end': str(re.date()) if re is not None else None,
        'prior_start': str(ps.date()) if ps is not None else None,
        'prior_end': str(pe.date()) if pe is not None else None,
        'recent_n': int(block.get('orders') or 0),
        'prior_n': int(prior.get('orders') or 0),
        # Prefer new metric keys; fallback to legacy aliases for safety during migration
        'recent_repeat_rate': float(
            (block.get('repeat_rate_within_window') if block.get('repeat_rate_within_window') is not None else block.get('repeat_rate'))
            or 0.0
        ),
        'prior_repeat_rate': float(
            (prior.get('repeat_rate_within_window') if prior.get('repeat_rate_within_window') is not None else prior.get('repeat_rate'))
            or 0.0
        ),
        'recent_aov': float(block.get('aov') or 0.0) if block.get('aov') is not None else 0.0,
        'prior_aov': float(prior.get('aov') or 0.0) if prior.get('aov') is not None else 0.0,
        'recent_discount_rate': float(block.get('discount_rate') or 0.0) if block.get('discount_rate') is not None else 0.0,
        'prior_discount_rate': float(prior.get('discount_rate') or 0.0) if prior.get('discount_rate') is not None else 0.0,
        'anchor': anchor,
    }


def select_actions(g, aligned, cfg, playbooks_path: str, receipts_dir: str, policy_path: str | None = None,
                   inventory_metrics: pd.DataFrame | None = None) -> Dict[str, Any]:
    """Public entry: normalize aligned input then delegate to core implementation."""
    # M0 cleanup (was: hardcoded `cfg['_FORCE_SINGLE_WINDOW'] = False` debug line).
    # Behavior preserved: default is False (multi-window enabled). The key is now
    # an explicit cfg surface so M4 has a clean handle to flip during decision-
    # logic surgery. utils.DEFAULTS owns the canonical default; setdefault here
    # is a belt-and-suspenders guard for callers that hand us a cfg dict that
    # bypassed get_config().
    cfg = cfg or {}
    cfg.setdefault('_FORCE_SINGLE_WINDOW', False)

    aligned_norm = _normalize_aligned(aligned, cfg)
    return _select_actions_impl(g, aligned_norm, cfg, playbooks_path, receipts_dir, policy_path, inventory_metrics)


def write_actions_log(receipts_dir: str, actions: list[dict]) -> None:
    log_path = Path(receipts_dir) / "actions_log.json"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log = []
    if log_path.exists():
        try: log = json.loads(log_path.read_text())
        except Exception: log = []
    for a in actions:
        log.append({
            "ts": now,
            "play_id": a.get("play_id"),
            "variant_id": a.get("variant_id"),
            "title": a.get("title"),
        })
    write_json(str(log_path), log)

## Removed unused tipover helpers (financial/significance) — never referenced

# --- Evidence builder (drop-in) --- #
def _pct(x, digits=1):
    return f"{x*100:.{digits}f}%" if (x is not None) else "—"

def _money(x):
    try:
        return f"${float(x):,.0f}"
    except Exception:
        return "—"

def _num(x):
    try:
        return f"{int(x)}"
    except Exception:
        return "—"

def _safe_get(al, path, default=None):
    cur = al
    try:
        for k in path:
            cur = cur[k]
        return cur
    except Exception:
        return default

def _receipt_discount_hygiene(al, a):
    dr1 = _safe_get(al, ["L28","discount_rate"])
    dr0 = _safe_get(al, ["L28","prior","discount_rate"])
    ddr = _safe_get(al, ["L28","delta","discount_rate"])
    p   = _safe_get(al, ["L28","p","discount_rate"])
    sig = _safe_get(al, ["L28","sig","discount_rate"])
    aov_delta = _safe_get(al, ["L28","delta","aov"])
    est = _money(a.get("expected_$"))
    msg = []
    if dr1 is not None and dr0 is not None:
        msg.append(
            f"Average discount depth {_pct(dr1)} vs {_pct(dr0)} ({_pct(ddr)} vs prior)"
            f"{' [significant]' if sig else ''}."
        )
    if aov_delta is not None:
        msg.append(f"AOV {_pct(aov_delta)} vs prior.")
    msg.append(f"Guardrail expected to recover ≈ {est}.")
    return " ".join(msg)

def _receipt_winback(al, a):
    rr1 = _safe_get(al, ["L28","repeat_rate_within_window"]) 
    rr0 = _safe_get(al, ["L28","prior","repeat_rate_within_window"]) 
    drr = _safe_get(al, ["L28","delta","repeat_rate_within_window"]) 
    p   = _safe_get(al, ["L28","p","repeat_rate_within_window"]) 
    sig = _safe_get(al, ["L28","sig","repeat_rate_within_window"]) 
    idn = _safe_get(al, ["L28","meta","identified_recent"], 0)
    est = _money(a.get("expected_$"))
    parts = []
    if rr1 is not None and rr0 is not None:
        parts.append(f"Repeat share {_pct(rr1)} (was {_pct(rr0)}; {_pct(drr)} vs prior){' [significant]' if sig else ''}.")
    parts.append(f"Identified customers this period: {_num(idn)}.")
    parts.append(f"Win-back cohort expected value ≈ {est}.")
    return " ".join(parts)

def _receipt_bestseller(al, a):
    aov_d = _safe_get(al, ["L28","delta","aov"])
    orders_d = _safe_get(al, ["L28","delta","orders"])
    est = _money(a.get("expected_$"))
    msg = []
    if aov_d is not None:
        msg.append(f"AOV {_pct(aov_d)} vs prior; bundling/hero placement aims to extend this lift.")
    if orders_d is not None:
        msg.append(f"Orders {_pct(orders_d)}; amplifying top seller targets attach rate.")
    msg.append(f"Expected impact ≈ {est}.")
    return " ".join(msg)

def _receipt_dormant(al, a):
    rr0 = _safe_get(al, ["L28","prior","repeat_rate_within_window"]) 
    rr1 = _safe_get(al, ["L28","repeat_rate_within_window"]) 
    est = _money(a.get("expected_$"))
    msg = []
    if rr1 is not None and rr0 is not None:
        msg.append(f"Store repeat share {_pct(rr1)} vs {_pct(rr0)} prior; reactivating multi-buyers should lift frequency.")
    msg.append(f"Expected impact ≈ {est}.")
    return " ".join(msg)

def evidence_for_action(action: dict, aligned: dict) -> list[str]:
    """Return a few concise, numeric reasons for this specific action.

    M4b T4b.4: when the action's ``evidence_class == "targeting"``, every
    bullet is suffixed with ``(targeting recommendation)`` so the merchant
    receipts consistently signal "no measured lift" for targeting plays.
    The legacy ``(heuristic)`` suffix on ``subscription_nudge`` is replaced
    by this consistent label when the M4b flag is on.
    """
    pid = (action.get("play_id") or "").lower()
    is_targeting = (
        str(action.get("evidence_class") or "").lower() == "targeting"
    )
    bullets: list[str] = []
    if "discount_hygiene" in pid:
        bullets.append(_receipt_discount_hygiene(aligned, action))
    elif "winback" in pid:
        bullets.append(_receipt_winback(aligned, action))
    elif "bestseller" in pid or "amplify" in pid:
        bullets.append(_receipt_bestseller(aligned, action))
    elif "dormant" in pid:
        bullets.append(_receipt_dormant(aligned, action))
    elif "subscription" in pid:
        aud = action.get("audience_size") or action.get("n")
        est = _money(action.get("expected_$"))
        bullets.append(f"{int(aud or 0)} customers bought the same product ≥3 times in 90d — prime for subscription.")
        # T4b.4: when targeting, drop the legacy "(heuristic)" suffix here;
        # the consistent "(targeting recommendation)" suffix is appended
        # uniformly below. With the flag off, preserve legacy "(heuristic)"
        # exactly.
        if is_targeting:
            bullets.append(f"Expected LTV lift cohort ≈ {est}.")
        else:
            bullets.append(f"Expected LTV lift cohort ≈ {est} (heuristic).")
    elif "routine_builder" in pid:
        aud = action.get("audience_size") or action.get("n")
        est = _money(action.get("expected_$"))
        bullets.append(f"{int(aud or 0)} skincare single-product buyers identified in the last 60d.")
        bullets.append(f"Bundle complementary items to lift AOV; expected impact ≈ {est}.")
    else:
        # fallback: use rationale/effect
        eff = action.get("effect_abs")
        bullets.append(action.get("rationale") or f"Effect delta {_pct(eff)} vs prior; expected ≈ {_money(action.get('expected_$'))}.")

    # T4b.4: uniformly suffix every targeting play's bullets with
    # "(targeting recommendation)". Preserves legacy text otherwise.
    if is_targeting:
        suffix = " (targeting recommendation)"
        labeled: list[str] = []
        for b in bullets:
            if not b:
                labeled.append(b)
                continue
            if "(targeting recommendation)" in b:
                labeled.append(b)
                continue
            stripped = b.rstrip()
            if stripped.endswith("."):
                labeled.append(stripped[:-1] + suffix + ".")
            else:
                labeled.append(stripped + suffix)
        bullets = labeled

    # Append LTV note if available (applies to any play)
    if action.get("audience_ltv90") is not None:
        try:
            ltv = float(action.get("audience_ltv90") or 0.0)
            topd = float(action.get("ltv90_top_decile") or 0.0)
            # Hide if effectively zero to keep receipts crisp
            if ltv >= 1.0:
                decile_note = "top-decile LTV prioritized; no-discount variant" if (topd > 0 and ltv >= topd) else None
                s = f"LTV90 (contrib) ≈ {_money(ltv)}"
                if decile_note:
                    s += f"; {decile_note}"
                bullets.append(s)
        except Exception:
            pass
    return bullets

def build_receipts(aligned: dict, actions_bundle: dict) -> list[str]:
    """
    Take selected actions (and pilot if any) and produce 3–5 'why this will work' bullets.
    """
    out = []
    # Top actions first
    for a in actions_bundle.get("actions", []):
        out += evidence_for_action(a, aligned)
    # If still sparse, include pilot rationale
    for p in actions_bundle.get("pilot_actions", []):
        out += evidence_for_action(p, aligned)
    # Keep it tight
    uniq = []
    seen = set()
    for s in out:
        k = s.strip()
        if k and k not in seen:
            uniq.append(k); seen.add(k)
        if len(uniq) >= 5:
            break
    return uniq
# --- end evidence builder --- #

# ----------------- Enhanced Multi-Window Statistical Analysis -----------------

def calculate_multiwindow_action_stats(g: pd.DataFrame, aligned_dict: Dict[str, Any],
                                     play_id: str, business_weights: Dict[str, float] = None) -> MultiWindowResult:
    """
    Calculate real statistics for template actions across multiple windows.

    Args:
        g: Transaction dataframe
        aligned_dict: Multi-window aligned data (L28, L56, L90)
        play_id: Action identifier (frequency_accelerator, retention_mastery, etc.)
        business_weights: Window weights from get_window_weights()

    Returns:
        MultiWindowResult with combined statistics
    """

    # Map play_id to statistical calculation function
    stat_functions = {
        'frequency_accelerator': calculate_frequency_stats_single_window,
        'retention_mastery': calculate_retention_stats_single_window,
        'journey_optimization': calculate_journey_stats_single_window,
        'aov_momentum': calculate_aov_momentum_stats_single_window,
    }

    if play_id not in stat_functions:
        debug_log('stats', f"No enhanced statistics available for {play_id}")
        return None

    stat_function = stat_functions[play_id]
    window_results = []

    # Calculate statistics for each available window
    for window_key in ['L28', 'L56', 'L90']:
        if window_key in aligned_dict:
            window_days = int(window_key[1:])  # L28 -> 28

            try:
                stats = stat_function(g, window_days)
                if stats:
                    window_results.append({
                        'window': window_key,
                        **stats
                    })
                    debug_log('stats_detail', f"{play_id} {window_key}: effect={stats['effect_abs']:.3f}, p={stats['p_value']:.3f}")
            except Exception as e:
                debug_log('stats', f"Statistical calculation failed for {play_id} {window_key}: {e}")
                continue

    if not window_results:
        debug_log('stats', f"No valid statistics calculated for {play_id}")
        return None

    # Combine results using meta-analysis
    combined_result = combine_multiwindow_statistics(window_results, business_weights)

    # B-6: tag the (play_id, metric) pair with the combiner trace.
    # Metric is unknown at this call site; record None so the universality
    # test can still see "this play_id flowed through the combiner."
    try:
        from .stats import record_combine_multiwindow_call as _rec
        _rec(play_id, None)
    except Exception:
        pass

    debug_log('stats', f"{play_id} combined: effect={combined_result.effect_abs:.3f}, p={combined_result.p_value:.3f}, windows={combined_result.contributing_windows}")

    return combined_result

def enhance_template_action_with_real_stats(candidate: Dict[str, Any], g: pd.DataFrame,
                                          aligned_dict: Dict[str, Any],
                                          business_weights: Dict[str, float] = None) -> Dict[str, Any]:
    """
    Replace template action assumptions with real multi-window statistics.

    Args:
        candidate: Template candidate with assumed stats
        g: Transaction dataframe
        aligned_dict: Multi-window aligned data
        business_weights: Window weights for combination

    Returns:
        Enhanced candidate with real statistics, or original if analysis fails
    """

    play_id = candidate.get('play_id', '')

    # Only enhance template actions that use assumptions
    template_actions = {'frequency_accelerator', 'retention_mastery', 'journey_optimization', 'aov_momentum'}

    if play_id not in template_actions:
        return candidate

    # Calculate real statistics
    try:
        real_stats = calculate_multiwindow_action_stats(g, aligned_dict, play_id, business_weights)

        if real_stats is None:
            debug_log('stats', f"Could not calculate real stats for {play_id}, keeping template values")
            return candidate

        # Replace assumed values with real statistics
        enhanced_candidate = candidate.copy()
        enhanced_candidate.update({
            'effect_abs': real_stats.effect_abs,
            'p': real_stats.p_value,
            'ci_low': real_stats.ci_low,
            'ci_high': real_stats.ci_high,
            'n': real_stats.n_total,
            'contributing_windows': real_stats.contributing_windows,
            'window_effects': real_stats.window_effects,
            'statistical_method': 'enhanced_multiwindow',
            'rationale': f"{candidate.get('rationale', '')} [Enhanced with real multi-window statistics: {', '.join(real_stats.contributing_windows)}]"
        })

        debug_log('stats', f"Enhanced {play_id}: assumed p={candidate.get('p', 'N/A')} → real p={real_stats.p_value:.3f}")

        return enhanced_candidate

    except Exception as e:
        debug_log('stats', f"Failed to enhance {play_id} with real statistics: {e}")
        return candidate

def get_enhanced_window_weights(vertical_mode: str, window_results: List[Dict] = None) -> Dict[str, float]:
    """
    Get window weights enhanced with statistical evidence quality.

    Args:
        vertical_mode: Business vertical (beauty, supplements, mixed)
        window_results: Optional list of window statistical results

    Returns:
        Dict of enhanced window weights
    """
    from .utils import get_window_weights

    # Start with business-based weights
    base_weights = get_window_weights(vertical_mode)

    if not window_results:
        return base_weights

    # Enhance weights based on statistical evidence quality
    enhanced_weights = {}
    total_enhancement = 0

    for window, base_weight in base_weights.items():
        if base_weight == 0:
            enhanced_weights[window] = 0
            continue

        # Find matching window result
        window_result = next((r for r in window_results if r.get('window') == window), None)

        if window_result:
            # Enhancement based on statistical quality
            p_value = window_result.get('p_value', 1.0)
            sample_size = window_result.get('n', 0)

            # Quality score: strong p-value and decent sample size
            p_quality = max(0, (0.1 - p_value) / 0.1) if p_value <= 0.1 else 0
            n_quality = min(1.0, sample_size / 100)  # Cap at 100 samples

            evidence_quality = (p_quality + n_quality) / 2
            enhancement_factor = 1.0 + (evidence_quality * 0.5)  # Up to 50% boost

            enhanced_weights[window] = base_weight * enhancement_factor
            total_enhancement += enhanced_weights[window]
        else:
            enhanced_weights[window] = base_weight
            total_enhancement += base_weight

    # Renormalize to sum to 1.0
    if total_enhancement > 0:
        for window in enhanced_weights:
            enhanced_weights[window] /= total_enhancement

    debug_log('stats_detail', f"Enhanced weights for {vertical_mode}: {enhanced_weights}")

    return enhanced_weights
