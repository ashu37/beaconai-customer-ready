from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime

from .utils import (
    detect_growth_stage,
    generate_growth_insights,
    organize_by_engine_tiers,
    select_priority_charts,
    get_seasonal_multiplier,
    get_vertical_mode,
    get_subvertical,
)
from .execution_templates import build_execution_plan, get_execution_template

CHART_SUMMARY_MAP = {
    'repurchase_timeline': "Returning customers flatten after the winback window—perfect timing for lifecycle plays.",
    'product_velocity': "Hero SKUs are outpacing the catalog, so doubling down protects margin while boosting AOV.",
    'customer_segments': "Customer value tiers show which cohorts are primed for the next purchase ladder.",
    'cohort_retention': "Retention by cohort reveals where loyalty programs need reinforcement.",
    'impact_forecast': "The combined roadmap quantifies how each action compounds monthly revenue.",
    'stock_vs_demand': "Inventory coverage highlights where merchandising or demand planning needs attention.",
    'first_to_second': "Tracking first-to-second conversions proves where onboarding journeys convert best.",
}

# Seasonal period callout messages for briefing
# Show when multiplier deviates significantly from 1.0
SEASONAL_CALLOUTS = {
    'BFCM': {
        'title': 'BFCM Peak Season',
        'message': 'This period is seasonally elevated (Black Friday/Cyber Monday). Gains may reflect seasonal demand rather than campaign effectiveness.',
        'type': 'elevated',
    },
    'holiday_season': {
        'title': 'Holiday Season',
        'message': 'Holiday gift-giving season is active. Interpret metrics with seasonal context in mind.',
        'type': 'elevated',
    },
    'january_detox': {
        'title': 'January Health Focus',
        'message': 'This period sees elevated health/wellness activity (New Year resolutions). Fitness and supplement brands typically see higher demand.',
        'type': 'mixed',  # Elevated for some, depressed for others
    },
    'spring_reset': {
        'title': 'Spring Reset Season',
        'message': 'Spring refresh period shows elevated beauty and wellness activity. Interpret gains cautiously.',
        'type': 'elevated',
    },
    'summer_slowdown': {
        'title': 'Summer Slowdown',
        'message': 'Summer vacation period typically shows reduced e-commerce activity. Lower metrics may reflect seasonality.',
        'type': 'depressed',
    },
    'routine_building': {
        'title': 'Back-to-Routine Season',
        'message': 'Back-to-school and routine-building period shows elevated subscription and replenishment activity.',
        'type': 'elevated',
    },
}


TIER_DESCRIPTIONS = {
    'primary': 'Foundational moves to activate immediately for the biggest impact.',
    'quick_wins': 'Fast lifts that stabilize supporting metrics while primary plays execute.',
    'experiments': 'Directional bets worth testing at smaller scale to unlock future upside.',
    'watchlist': 'Emerging ideas that need more signal or capacity before scaling.',
}

WRAPUP_PREFS = [
    ('creative', 'Creative'),
    ('merch', 'Creative'),
    ('merchandising', 'Creative'),
    ('lifecycle', 'Lifecycle'),
    ('crm', 'Lifecycle'),
    ('retention', 'Lifecycle'),
    ('measurement', 'Measurement'),
    ('analytics', 'Measurement'),
    ('growth', 'Measurement'),
]

FAILURE_MAPPINGS = {
    'min_n': 'needs a larger audience to hit the sample-size gate',
    'significance': 'statistical confidence is still building',
    'effect_floor': 'observed lift is below the minimum effect size',
    'financial_floor': 'expected revenue is below the required floor'
}

# Play-specific storytelling templates
PLAY_TEMPLATES = {
    'frequency_accelerator': {
        'why_now': 'Repeat rate flattened over {window} while lapsed share grew.',
        'primary_metric': 'repeat_rate',
        'reasoning': {
            'label_1': 'Audience', 'metric_1': 'audience_size',
            'label_2': 'Trend', 'metric_2': 'repeat_rate_delta', 'is_trend': True,
            'label_3': 'At Risk', 'metric_3': 'at_risk_revenue',
        },
        'chart_conclusion': 'Repeat buyers are stalling after {days} days',
        'evidence_keys': ['recent_vs_prior', 'top_cohort', 'trigger_window'],
    },
    'journey_optimization': {
        'why_now': 'First-to-second conversion dropped {delta} in {window}.',
        'primary_metric': 'conversion_rate',
        'reasoning': {
            'label_1': 'New Buyers', 'metric_1': 'new_customer_count',
            'label_2': 'Drop-off', 'metric_2': 'conversion_delta', 'is_trend': True,
            'label_3': 'Lost Rev', 'metric_3': 'lost_revenue',
        },
        'chart_conclusion': 'New customers drop off before their second purchase',
        'evidence_keys': ['conversion_rate', 'avg_days_to_second', 'best_channel'],
    },
    'retention_mastery': {
        'why_now': 'Returning customer share is {value}—{direction} from prior period.',
        'primary_metric': 'returning_share',
        'reasoning': {
            'label_1': 'Returning', 'metric_1': 'returning_share',
            'label_2': 'Trend', 'metric_2': 'returning_delta', 'is_trend': True,
            'label_3': 'Rev Share', 'metric_3': 'returning_revenue_share',
        },
        'chart_conclusion': 'Returning customers drive {pct}% of revenue',
        'evidence_keys': ['retention_rate', 'churn_risk', 'loyalty_score'],
    },
    'aov_optimizer': {
        'why_now': 'AOV shifted {delta} vs. prior {window}—room to ladder up.',
        'primary_metric': 'aov',
        'reasoning': {
            'label_1': 'Avg Order', 'metric_1': 'aov',
            'label_2': 'Change', 'metric_2': 'aov_delta', 'is_trend': True,
            'label_3': 'Upside', 'metric_3': 'aov_upside',
        },
        'chart_conclusion': 'AOV growth unlocks {value} in monthly revenue',
        'evidence_keys': ['current_aov', 'target_aov', 'bundle_opportunity'],
    },
    'winback_campaign': {
        'why_now': '{count} customers lapsed in the last {window}.',
        'primary_metric': 'lapsed_count',
        'reasoning': {
            'label_1': 'Lapsed', 'metric_1': 'lapsed_count',
            'label_2': 'Winback %', 'metric_2': 'winback_rate',
            'label_3': 'Revenue', 'metric_3': 'winback_revenue',
        },
        'chart_conclusion': 'Lapsed customers represent {value} in recoverable revenue',
        'evidence_keys': ['days_since_purchase', 'prior_ltv', 'win_probability'],
    },
    'hero_product_push': {
        'why_now': 'Hero SKU velocity is {direction}—{pct}% of recent orders.',
        'primary_metric': 'hero_share',
        'reasoning': {
            'label_1': 'Hero SKU', 'metric_1': 'hero_product',
            'label_2': 'Share', 'metric_2': 'hero_share',
            'label_3': 'Margin', 'metric_3': 'hero_margin',
        },
        'chart_conclusion': 'Doubling down on hero SKUs protects margin',
        'evidence_keys': ['hero_velocity', 'margin_contribution', 'stock_level'],
    },
    'discount_optimization': {
        'why_now': 'Discount rate hit {rate}%—{delta} from baseline.',
        'primary_metric': 'discount_rate',
        'reasoning': {
            'label_1': 'Disc Rate', 'metric_1': 'discount_rate',
            'label_2': 'Trend', 'metric_2': 'discount_delta', 'is_trend': True,
            'label_3': 'Margin Hit', 'metric_3': 'margin_erosion',
        },
        'chart_conclusion': 'Discount discipline recovers {value} in margin',
        'evidence_keys': ['current_rate', 'optimal_rate', 'margin_impact'],
    },
    'cross_sell': {
        'why_now': 'Cross-sell attach rate is {rate}%—below category benchmark.',
        'primary_metric': 'attach_rate',
        'reasoning': {
            'label_1': 'Attach', 'metric_1': 'attach_rate',
            'label_2': 'Gap', 'metric_2': 'attach_gap',
            'label_3': 'Upside', 'metric_3': 'cross_sell_revenue',
        },
        'chart_conclusion': 'Cross-sell adds {value} per order on average',
        'evidence_keys': ['top_pair', 'attach_rate', 'revenue_per_order'],
    },
    'loyalty_program': {
        'why_now': 'Loyal customers generate {pct}% of revenue but churn is rising.',
        'primary_metric': 'loyalty_revenue_share',
        'reasoning': {
            'label_1': 'Loyal Rev', 'metric_1': 'loyalty_revenue_share',
            'label_2': 'Churn', 'metric_2': 'loyalty_churn', 'is_trend': True,
            'label_3': 'At Risk', 'metric_3': 'loyalty_at_risk',
        },
        'chart_conclusion': 'Loyalty program protects {value} in annual revenue',
        'evidence_keys': ['member_count', 'avg_ltv', 'churn_rate'],
    },
    'vip_program': {
        'why_now': 'Top {pct}% of customers drive {rev_share}% of revenue.',
        'primary_metric': 'vip_concentration',
        'reasoning': {
            'label_1': 'VIP Count', 'metric_1': 'vip_count',
            'label_2': 'Rev Share', 'metric_2': 'vip_revenue_share',
            'label_3': 'Avg LTV', 'metric_3': 'vip_ltv',
        },
        'chart_conclusion': 'VIP retention compounds to {value} annually',
        'evidence_keys': ['vip_count', 'avg_order_value', 'purchase_frequency'],
    },
}

# Generic fallback template when play-specific data is missing
FALLBACK_TEMPLATE = {
    'why_now': 'Recent data shows opportunity in {metric_name}.',
    'reasoning': {
        'label_1': 'Audience', 'metric_1': 'audience_size',
        'label_2': 'Impact', 'metric_2': 'expected_$',
        'label_3': 'Confidence', 'metric_3': 'confidence_score',
    },
    'chart_conclusion': 'This pattern triggered the recommendation',
    'evidence_keys': ['source_window', 'effect_size', 'p_value'],
}

LAUNCH_PLAN_LIMIT = 6


def _fmt_money(value: Optional[float]) -> str:
    if value is None:
        return '—'
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return '—'


def _fmt_delta(value: Optional[float]) -> str:
    if value is None:
        return '—'
    try:
        return f"{float(value) * 100:+.1f}%"
    except (TypeError, ValueError):
        return '—'


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return '—'
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return '—'


def _fmt_audience(value: Optional[float]) -> str:
    if value is None:
        return '—'
    try:
        num = float(value)
    except (TypeError, ValueError):
        return '—'
    if num >= 1000000:
        return f"{num/1_000_000:.1f}M"
    if num >= 1000:
        return f"{num/1000:.1f}K"
    return f"{int(num):,}"


def _fmt_trend(value: Optional[float], is_pct: bool = True) -> str:
    """Format a trend value with direction arrow."""
    if value is None:
        return '—'
    try:
        num = float(value)
    except (TypeError, ValueError):
        return '—'
    arrow = '↑' if num > 0 else '↓' if num < 0 else '→'
    if is_pct:
        return f"{arrow} {abs(num):.1f}%"
    return f"{arrow} {abs(num):.1f}"


def _get_action_value(action: Dict[str, Any], key: str) -> Any:
    """Extract a value from action, checking multiple possible locations."""
    # Direct key
    if key in action:
        return action[key]
    # Check in metrics dict
    metrics = action.get('metrics', {})
    if key in metrics:
        return metrics[key]
    # Check in deltas
    deltas = action.get('deltas', {})
    if key in deltas:
        return deltas[key]
    # Check in evidence list
    evidence = action.get('evidence', [])
    for ev in evidence:
        if isinstance(ev, dict) and ev.get('key') == key:
            return ev.get('value')
    # Check in health_impact
    health = action.get('health_impact', {})
    if key in health:
        return health[key]
    return None


def _format_reasoning_value(value: Any, is_trend: bool = False, is_money: bool = False) -> str:
    """Format a value for display in reasoning badge."""
    if value is None:
        return '—'
    if is_money:
        return _fmt_money(value)
    if is_trend:
        return _fmt_trend(value)
    if isinstance(value, float):
        if abs(value) < 1:
            return f"{value * 100:.1f}%"
        return f"{value:.1f}"
    if isinstance(value, int):
        return _fmt_audience(value)
    return str(value)


def _generate_play_specific_fields(action: Dict[str, Any], aligned: Dict[str, Any]) -> Dict[str, Any]:
    """Generate play-specific storytelling fields with fallback.

    Focus on 28-day forward impact: what happens if they implement this action.
    """
    play_id = action.get('play_id', '')
    template = PLAY_TEMPLATES.get(play_id, FALLBACK_TEMPLATE)

    # Get source window info
    source_window = action.get('source_window', 'L28')

    # Get window data from aligned for additional context
    window_data = aligned.get(source_window, {}) if aligned else {}
    window_delta = window_data.get('delta', {}) if isinstance(window_data, dict) else {}

    # Get primary metric value and its delta
    primary_metric = template.get('primary_metric', 'metric')

    # Map play metrics to aligned data keys
    metric_to_aligned_key = {
        'repeat_rate': 'repeat_rate_within_window',
        'conversion_rate': 'returning_customer_share',
        'returning_share': 'returning_customer_share',
        'aov': 'aov',
        'discount_rate': 'discount_rate',
    }
    aligned_key = metric_to_aligned_key.get(primary_metric, primary_metric)

    # Get primary value from action or aligned
    primary_value = _get_action_value(action, primary_metric)
    if primary_value is None:
        primary_value = window_data.get(aligned_key)

    # Get delta from aligned data (the actual observed change)
    delta_from_aligned = window_delta.get(aligned_key, 0)

    # Get key metrics
    audience_size = action.get('audience_size') or action.get('n', 0)
    expected_rev = action.get('expected_$', 0)
    confidence = action.get('confidence_score', 0)

    # Build human-readable metric description
    metric_labels = {
        'repeat_rate': 'repeat purchases',
        'conversion_rate': 'conversion rate',
        'returning_share': 'returning customers',
        'aov': 'average order value',
        'discount_rate': 'discount usage',
        'frequency': 'purchase frequency',
        'retention': 'customer retention',
        'conversion': 'conversion rate',
    }
    metric_label = metric_labels.get(primary_metric, primary_metric.replace('_', ' '))

    # Build why_now - focus on the opportunity, not technical metrics
    # Format delta as percentage points or percentage change
    if delta_from_aligned and abs(delta_from_aligned) > 0:
        if abs(delta_from_aligned) < 0.5:  # Likely a rate (0.03 = 3%)
            delta_display = f"{delta_from_aligned * 100:+.1f}%"
        else:
            delta_display = f"{delta_from_aligned:+.1f}%"
        direction_word = 'up' if delta_from_aligned > 0 else 'down'
    else:
        delta_display = ''
        direction_word = 'stable'

    # Safely convert primary_value to float for templates
    try:
        primary_value_pct = abs(float(primary_value) * 100) if primary_value and isinstance(primary_value, (int, float)) else 0
    except (TypeError, ValueError):
        primary_value_pct = 0

    # Generate why_now based on play type with forward-looking language
    why_now_templates = {
        'journey_optimization': f"Customers are dropping off before their second purchase. Target {_fmt_audience(audience_size)} customers to recover {_fmt_money(expected_rev)} in the next 28 days.",
        'frequency_accelerator': f"Repeat rate is {direction_word} {abs(delta_from_aligned * 100):.1f}%. Accelerating {_fmt_audience(audience_size)} repeat buyers could add {_fmt_money(expected_rev)} this month.",
        'retention_mastery': f"Returning customer share is at {primary_value_pct:.0f}%. Retaining {_fmt_audience(audience_size)} at-risk customers protects {_fmt_money(expected_rev)} monthly.",
        'aov_optimizer': f"AOV opportunity identified. Upselling to {_fmt_audience(audience_size)} customers could add {_fmt_money(expected_rev)} in the next 28 days.",
        'winback_campaign': f"{_fmt_audience(audience_size)} customers haven't purchased recently. Win them back to recover {_fmt_money(expected_rev)} this month.",
        'discount_optimization': f"Discount rate is impacting margins. Optimizing could save {_fmt_money(expected_rev)} in the next 28 days.",
    }

    why_now = why_now_templates.get(play_id)
    if not why_now:
        why_now = f"Data shows opportunity in {metric_label}. Acting on {_fmt_audience(audience_size)} customers could generate {_fmt_money(expected_rev)} in the next 28 days."

    # Build reasoning badges - SIMPLIFIED to just Target + Impact
    # Badge 1: Target Audience (who to act on)
    # Badge 2: 28-Day Impact (forecasted revenue outcome)
    reasoning = {
        'label_1': 'Target',
        'value_1': f"{_fmt_audience(audience_size)} customers",
        'label_2': '28-Day Impact',
        'value_2': _fmt_money(expected_rev),
    }

    # Build chart conclusion - forward-looking impact statement
    chart_conclusions = {
        'journey_optimization': f"Converting these customers adds {_fmt_money(expected_rev)} monthly",
        'frequency_accelerator': f"Accelerating repeat purchases adds {_fmt_money(expected_rev)} monthly",
        'retention_mastery': f"Retaining these customers protects {_fmt_money(expected_rev)} monthly",
        'aov_optimizer': f"Increasing AOV adds {_fmt_money(expected_rev)} monthly",
        'winback_campaign': f"Winning back lapsed customers recovers {_fmt_money(expected_rev)} monthly",
        'discount_optimization': f"Optimizing discounts saves {_fmt_money(expected_rev)} monthly",
    }
    chart_conclusion = chart_conclusions.get(play_id, f"Implementing this adds {_fmt_money(expected_rev)} in 28 days")

    # Build evidence chips - business-friendly, not technical
    evidence_chips = []

    # Chip 1: Confidence level (how sure we are)
    if confidence >= 0.8:
        conf_label = 'High confidence'
    elif confidence >= 0.5:
        conf_label = 'Moderate confidence'
    else:
        conf_label = 'Early signal'
    evidence_chips.append({
        'label': 'Signal',
        'value': conf_label,
    })

    # Chip 2: Revenue range (conservative to optimistic)
    expected_low = action.get('expected_range', [expected_rev * 0.7, expected_rev * 1.3])[0] if action.get('expected_range') else expected_rev * 0.7
    expected_high = action.get('expected_range', [expected_rev * 0.7, expected_rev * 1.3])[1] if action.get('expected_range') else expected_rev * 1.3
    evidence_chips.append({
        'label': 'Range',
        'value': f"{_fmt_money(expected_low)}–{_fmt_money(expected_high)}",
    })

    # Chip 3: Time to implement (from action data)
    setup_mins = action.get('time_to_set_up_minutes', 45)
    if setup_mins <= 30:
        time_label = 'Quick setup'
    elif setup_mins <= 60:
        time_label = '~1 hour setup'
    else:
        time_label = f'~{setup_mins // 60}h setup'
    evidence_chips.append({
        'label': 'Effort',
        'value': time_label,
    })

    return {
        'why_now': why_now,
        'reasoning': reasoning,
        'chart_conclusion': chart_conclusion,
        'evidence_chips': evidence_chips[:3],
    }


def _confidence_label(action: Dict[str, Any]) -> str:
    score = action.get('confidence_score')
    if score is None:
        return 'Confidence —'
    try:
        pct = int(round(float(score) * 100))
        return f"{pct}% Confidence"
    except (TypeError, ValueError):
        return 'Confidence —'


def _extract_action_metric(action: Dict[str, Any]) -> Dict[str, str]:
    impact = _fmt_money(action.get('expected_$'))
    audience = _fmt_audience(action.get('audience_size') or action.get('n'))
    return {
        'impact_label': '28-Day Impact',
        'impact_value': f"{impact} incremental" if impact != '—' else 'Impact —',
        'audience_label': 'Audience',
        'audience_value': f"{audience} customers" if audience != '—' else 'Audience —',
    }


def _first_sentence(text: str, max_len: int = 160) -> str:
    if not text:
        return ''
    stripped = text.strip()
    if len(stripped) <= max_len:
        return stripped
    cut = stripped[:max_len]
    if '.' in cut:
        return cut.rsplit('.', 1)[0] + '.'
    return cut + '…'


def _chart_summary(chart_key: str, growth_stage: str) -> str:
    base = CHART_SUMMARY_MAP.get(chart_key)
    if base:
        return base
    if 'frequency' in chart_key:
        return 'Frequency cohorts clarify which segments are ready for acceleration.'
    if 'aov' in chart_key:
        return 'AOV trends illustrate how premium mixes are shifting.'
    return 'This visualization captures the signal that triggered the recommendation.'


def _resolve_action_charts(action: Dict[str, Any], charts_map: Dict[str, str]) -> List[Dict[str, str]]:
    chart_refs: List[Dict[str, str]] = []
    for key in action.get('supporting_charts', []) or []:
        path = charts_map.get(key)
        if not path:
            continue
        chart_refs.append({
            'key': key,
            'path': path,
            'title': action.get('title', 'Action Insight')
        })
    return chart_refs


def _action_narrative(action: Dict[str, Any]) -> str:
    health_summary = (action.get('health_impact') or {}).get('impact_summary')
    if health_summary:
        return _first_sentence(health_summary, 280)
    rationale = action.get('rationale')
    if rationale:
        return _first_sentence(rationale, 280)
    do_this = action.get('do_this')
    if do_this:
        return _first_sentence(do_this, 280)
    return 'This play is recommended based on recent performance patterns.'


def _build_wrapups(actions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {'Creative': [], 'Lifecycle': [], 'Measurement': []}
    for action in actions:
        owner = str(action.get('owner_suggested', '') or '').lower()
        matched = False
        for needle, bucket in WRAPUP_PREFS:
            if needle in owner:
                buckets[bucket].append(action)
                matched = True
                break
        if not matched and action.get('do_this'):
            buckets['Measurement'].append(action)
    wrapups: List[Dict[str, str]] = []
    titles = {
        'Creative': '01 • Creative',
        'Lifecycle': '02 • Lifecycle',
        'Measurement': '03 • Measurement'
    }
    order = ['Creative', 'Lifecycle', 'Measurement']
    slot = 1
    used_ids: set[str] = set()

    def pick_action(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for candidate in candidates:
            key = str(candidate.get('play_id') or id(candidate))
            if key in used_ids:
                continue
            used_ids.add(key)
            return candidate
        return None

    for key in order:
        actions_in_bucket = buckets.get(key) or []
        action = pick_action(actions_in_bucket)
        if not action and slot-1 < len(actions):
            action = pick_action(actions[slot-1:])
        body = 'Keep teams aligned on this month\'s roadmap.'
        if action:
            headline = action.get('title') or action.get('play_id') or 'This play'
            narrative = _action_narrative(action)
            owner = action.get('owner_suggested')
            if owner:
                body = f"{headline}: {narrative} Assign to {owner}."
            else:
                body = f"{headline}: {narrative}"
        wrapups.append({'title': titles.get(key, f"0{slot} • Next Step"), 'body': body})
        slot += 1
    return wrapups[:3]




def _launch_owner_hint(action: Dict[str, Any]) -> str:
    owner = action.get('owner_suggested')
    if owner:
        return owner
    channels = action.get('channels') or []
    if isinstance(channels, dict):
        channels = [k for k, v in channels.items() if v]
    if channels:
        return ', '.join(str(c).title() for c in channels)
    return 'Assign owner'


def _build_launch_plan(confidence_tiers: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Legacy launch plan builder - kept for backwards compatibility."""
    plan: List[Dict[str, Any]] = []
    tier_order = ['primary', 'quick_wins', 'experiments']

    for tier in tier_order:
        for action in confidence_tiers.get(tier, []) or []:
            steps = action.get('how_to_launch') or []
            first_step = steps[0] if steps else None
            next_step = steps[1] if len(steps) > 1 else None
            metrics = _extract_action_metric(action)
            plan.append({
                'tier': tier,
                'tier_label': TIER_DESCRIPTIONS.get(tier, tier.replace('_', ' ').title()),
                'title': action.get('title', action.get('play_id', 'Action')),
                'owner': _launch_owner_hint(action),
                'why_now': _action_narrative(action),
                'impact': metrics['impact_value'],
                'audience': metrics['audience_value'],
                'first_step': first_step,
                'next_step': next_step,
                'steps': steps,
            })
            if len(plan) >= LAUNCH_PLAN_LIMIT:
                return plan
    return plan


def _build_sprint_plan(confidence_tiers: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Build an action summary table grouped by tier.
    """
    tier_labels = {
        'primary': 'Primary',
        'quick_wins': 'Quick Win',
        'experiments': 'Experiment',
        'watchlist': 'Watchlist',
    }

    tier_order = ['primary', 'quick_wins', 'experiments', 'watchlist']

    # Collect all actions grouped by tier
    all_actions: List[Dict[str, Any]] = []
    total_opportunity = 0.0

    for tier_id in tier_order:
        actions_in_tier = confidence_tiers.get(tier_id, []) or []

        for action in actions_in_tier:
            expected_rev = action.get('expected_$', 0) or 0

            all_actions.append({
                'tier': tier_id,
                'tier_label': tier_labels.get(tier_id, tier_id),
                'title': action.get('title', action.get('play_id', 'Action')),
                'owner': _launch_owner_hint(action),
                'impact': _fmt_money(expected_rev) if tier_id != 'watchlist' else '—',
            })

            # Only count actionable tiers toward opportunity
            if tier_id in ['primary', 'quick_wins', 'experiments']:
                total_opportunity += float(expected_rev)

    # Group by tier for rendering
    tiers: List[Dict[str, Any]] = []
    for tier_id in tier_order:
        tier_actions = [a for a in all_actions if a['tier'] == tier_id]
        if tier_actions:
            tiers.append({
                'tier': tier_id,
                'label': tier_labels.get(tier_id, tier_id),
                'actions': tier_actions,
            })

    return {
        'total_opportunity': _fmt_money(total_opportunity),
        'total_actions': len([a for a in all_actions if a['tier'] != 'watchlist']),
        'tiers': tiers,
    }

def _signal_strength(action: Dict[str, Any]) -> str:
    """Convert confidence score to qualitative label."""
    confidence = action.get('confidence_score')
    if not isinstance(confidence, (int, float)):
        return 'Signal pending'
    conf_pct = confidence * 100
    if conf_pct >= 80:
        return 'Strong signal'
    elif conf_pct >= 50:
        return 'Moderate signal'
    else:
        return 'Weak signal'


def _tier_reason(action: Dict[str, Any], tier_id: str, thresholds: Dict[str, float], mode: str) -> str:
    """Return a simple, plain-language reason for tier placement."""
    failed = action.get('failed') or []

    # Plain language failure reasons
    failure_labels = {
        'effect_floor': 'effect not large enough yet',
        'significance': 'needs more data to confirm',
        'min_n': 'audience too small',
        'financial_floor': 'impact below threshold',
    }

    if tier_id == 'primary':
        return 'Strong evidence, ready to launch.'
    elif tier_id == 'quick_wins':
        return 'Good opportunity with lower effort.'
    elif tier_id == 'experiments':
        return 'Promising signal, worth testing at small scale.'
    elif tier_id == 'watchlist':
        if failed:
            reason = failure_labels.get(failed[0], 'needs validation')
            return f'Monitoring — {reason}.'
        return 'Needs more data before committing.'

    return ''


def build_briefing_story(brand: str, aligned: Dict[str, Any], outputs: Dict[str, Any]) -> Dict[str, Any]:
    charts_map = outputs.get('charts_map', {}) or {}
    enhanced_outputs = organize_by_engine_tiers(outputs)
    confidence_tiers = enhanced_outputs.get('confidence_tiers', {})
    tier_metadata = enhanced_outputs.get('tier_metadata', {})
    tier_thresholds = enhanced_outputs.get('tier_thresholds', {}) or {}
    confidence_mode = enhanced_outputs.get('confidence_mode', 'learning')
    thresholds_pct = {
        key: int(round(value * 100))
        for key, value in tier_thresholds.items()
        if isinstance(value, (int, float))
    }

    growth_stage = detect_growth_stage(aligned)
    primary_actions = confidence_tiers.get('primary', []) if confidence_tiers else outputs.get('actions', [])
    quick_actions = confidence_tiers.get('quick_wins', []) if confidence_tiers else outputs.get('watchlist', [])

    growth_insights = generate_growth_insights(aligned, growth_stage, primary_actions)

    opportunity_total = sum(float(a.get('expected_$', 0) or 0) for a in (primary_actions + quick_actions))
    total_recommendations = len(primary_actions) + len(quick_actions)
    hero_cards = [
        {
            'label': 'Monthly Growth Opportunity',
            'value': _fmt_money(opportunity_total),
            'note': 'Combined incremental revenue from this month\'s priority plays.'
        },
        {
            'label': 'Growth Stage',
            'value': growth_insights.get('stage_title', 'Growth Stage'),
            'note': _first_sentence(growth_insights.get('diagnosis_text', ''), 160)
        },
        {
            'label': 'Plays Recommended',
            'value': f"{len(primary_actions)} Primary • {len(quick_actions)} Quick Wins",
            'note': 'Each action carries confidence scoring, revenue impact, and ready-to-launch assets.'
        },
    ]

    anchor = aligned.get('anchor')
    if isinstance(anchor, datetime):
        month_label = anchor.strftime('%B %Y')
    elif hasattr(anchor, 'strftime'):
        month_label = anchor.strftime('%B %Y')
    else:
        month_label = 'Current Month'

    aura_score = outputs.get('aura_score') or aligned.get('aura_score') or {}
    components = aura_score.get('components', {})
    component_rows = []
    for key, label in [
        ('revenue_health', 'Revenue Health'),
        ('customer_health', 'Customer Health'),
        ('margin_health', 'Margin Health'),
        ('growth_health', 'Growth Health'),
        ('ltv_health', 'LTV Health'),
    ]:
        value = components.get(key)
        component_rows.append({
            'name': label,
            'score': int(value) if value is not None else '—',
            'delta': aura_score.get('trend') if key == 'revenue_health' else None,
        })

    aura_summary = aura_score.get('insights', [])
    score_summary = aura_summary[0] if aura_summary else 'Beacon score blends revenue, customer, margin, growth, and LTV signals.'

    tier_list: List[Dict[str, Any]] = []
    for tier_id in ['primary', 'quick_wins', 'experiments', 'watchlist']:
        actions_in_tier = confidence_tiers.get(tier_id, []) if confidence_tiers else []
        if not actions_in_tier:
            continue
        metadata = tier_metadata.get(tier_id, {}) if tier_metadata else {}
        story_actions: List[Dict[str, Any]] = []
        for idx, action in enumerate(actions_in_tier):
            metrics = _extract_action_metric(action)
            # Generate play-specific storytelling fields
            play_fields = _generate_play_specific_fields(action, aligned)

            # Build execution plan from templates
            play_id = action.get('play_id', '')
            segment_path = action.get('attachment', f"segments/segment_{play_id}.csv")
            segment_label = action.get('title', play_id.replace('_', ' ').title())
            audience_size = action.get('audience_size') or action.get('n', 0)
            expected_rev = action.get('expected_$', 0)

            execution = build_execution_plan(
                play_id=play_id,
                segment_path=segment_path,
                segment_label=segment_label,
                audience_size=audience_size,
                expected_revenue=expected_rev,
                platform="Email ESP",  # Default, can be overridden
                month=month_label[:3] + month_label[-2:] if month_label else None,
            )

            story_actions.append({
                'title': action.get('title', action.get('play_id', 'Action')),
                'signal_strength': _signal_strength(action),
                'impact_label': metrics['impact_label'],
                'impact_value': metrics['impact_value'],
                'audience_label': metrics['audience_label'],
                'audience_value': metrics['audience_value'],
                'narrative': _action_narrative(action),
                'evidence': action.get('evidence', []),
                'charts': _resolve_action_charts(action, charts_map),
                'targeting': action.get('targeting') or action.get('do_this'),
                'health_impact': (action.get('health_impact') or {}).get('impact_summary'),
                'steps': action.get('how_to_launch') or [],
                'tier_reason': _tier_reason(action, tier_id, tier_thresholds, confidence_mode),
                # New play-specific fields
                'why_now': play_fields.get('why_now'),
                'reasoning': play_fields.get('reasoning', {}),
                'chart_conclusion': play_fields.get('chart_conclusion'),
                'evidence_chips': play_fields.get('evidence_chips', []),
                # Execution plan
                'execution': execution,
            })
        tier_list.append({
            'id': tier_id,
            'title': metadata.get('label', tier_id.replace('_', ' ').title()),
            'badge': metadata.get('icon', ''),
            'confidence_range': metadata.get('confidence_range', ''),
            'confidence_band': {
                'min': metadata.get('min_pct'),
                'max': metadata.get('max_pct'),
            },
            'description': TIER_DESCRIPTIONS.get(tier_id, ''),
            'actions': story_actions,
        })

    priority_chart_defs = select_priority_charts(aligned, outputs.get('actions', []), charts_map)
    chart_cards: List[Dict[str, Any]] = []
    for key, title in priority_chart_defs:
        path = charts_map.get(key)
        if not path:
            continue
        chart_cards.append({
            'key': key,
            'title': title,
            'path': path,
            'summary': _chart_summary(key, growth_stage),
        })

    launch_plan = _build_launch_plan(confidence_tiers)
    sprint_plan = _build_sprint_plan(confidence_tiers)

    # Build seasonal note if we're in a notable seasonal period
    seasonal_note = None
    if anchor:
        try:
            vertical_mode = get_vertical_mode()
            subvertical = get_subvertical()
            seasonal_mult, season_period = get_seasonal_multiplier(anchor, vertical_mode, subvertical)

            # Show callout if multiplier deviates significantly from 1.0 (>15% either direction)
            if abs(seasonal_mult - 1.0) > 0.15 and season_period in SEASONAL_CALLOUTS:
                callout = SEASONAL_CALLOUTS[season_period]
                seasonal_note = {
                    'show': True,
                    'period': season_period,
                    'title': callout['title'],
                    'message': callout['message'],
                    'type': callout['type'],
                    'multiplier': seasonal_mult,
                }
        except Exception:
            pass  # Don't fail story generation if seasonal calc fails

    story = {
        'hero': {
            'brand': brand,
            'month_label': month_label,
            'stage_title': growth_insights.get('stage_title', ''),
            'subtitle': growth_insights.get('diagnosis_title', ''),
            'cards': hero_cards,
        },
        'score': {
            'value': aura_score.get('overall', '—'),
            'tier': aura_score.get('tier', '').title() if aura_score.get('tier') else '—',
            'trend': aura_score.get('trend', '0'),
            'summary': _first_sentence(score_summary, 220),
            'components': component_rows,
        },
        'charts': chart_cards,
        'tiers': tier_list,
        'launch_plan': launch_plan,  # Legacy, kept for compatibility
        'sprint_plan': sprint_plan,  # New timeline-based plan
        'confidence': {
            'mode': confidence_mode,
            'thresholds': tier_thresholds,
            'thresholds_pct': thresholds_pct,
        },
        'seasonal_note': seasonal_note,
    }

    return story
