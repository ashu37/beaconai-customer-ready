from __future__ import annotations
import os
import json
import math
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import pandas as pd
from datetime import timedelta
from datetime import datetime
import numpy as np
import pandas as pd
import re
from .stats import welch_t_test, two_proportion_test, benjamini_hochberg, seasonal_adjustment

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv is not available, manually load .env file.
    # S-1.7: setdefault semantics — exported env vars must win over .env
    # values so test harnesses / shell overrides aren't silently clobbered.
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

# ---------------- Growth Stage Detection & Dynamic Chart Selection ----------------

def detect_growth_stage(aligned):
    """Determine store's growth stage based on key metrics"""
    try:
        l28_data = aligned.get('L28', {})
        l28_orders = int(l28_data.get('orders', 0) or 0)
        returning_rate = float(l28_data.get('returning_customer_share', 0) or 0)
        repeat_rate = float(l28_data.get('repeat_rate_within_window', 0) or 0)
        
        # Early stage: Low order volume, mostly new customers
        if l28_orders < 150:
            return 'early_stage'
        
        # Scaling: Good volume but still acquiring new customers
        elif returning_rate < 0.40 or repeat_rate < 0.15:
            return 'scaling'
        
        # Mature: Higher volume with established customer base
        else:
            return 'mature'
            
    except Exception:
        # Default fallback
        return 'scaling'

def select_priority_charts(aligned, actions, charts_map):
    """Select 2-3 most relevant charts based on growth stage and recommended actions"""
    try:
        growth_stage = detect_growth_stage(aligned)
        priority_charts = []
        available_charts = charts_map or {}
        
        # Growth stage determines primary chart selection
        if growth_stage == 'early_stage':
            # Focus on customer acquisition and first purchase behavior
            if 'first_to_second' in available_charts:
                priority_charts.append(('first_to_second', 'First-to-Second Purchase Journey'))
            if 'customer_segments' in available_charts and any('winback' in str(a.get('play_id', '')).lower() for a in (actions or [])):
                priority_charts.append(('customer_segments', 'Customer Opportunity Segments'))
                
        elif growth_stage == 'scaling':
            # Focus on retention and product performance
            if 'cohort_retention' in available_charts:
                priority_charts.append(('cohort_retention', 'Customer Retention Analysis'))
            if 'product_velocity' in available_charts or 'velocity' in available_charts:
                chart_key = 'product_velocity' if 'product_velocity' in available_charts else 'velocity'
                priority_charts.append((chart_key, 'Product Performance Analysis'))
                
        else:  # mature
            # Focus on customer value and lifecycle
            if 'customer_segments' in available_charts:
                priority_charts.append(('customer_segments', 'Customer Value Segments'))
            if 'repurchase' in available_charts:
                priority_charts.append(('repurchase', 'Customer Repurchase Patterns'))
        
        # Limit to max 3 charts for story focus
        return priority_charts[:3]
        
    except Exception:
        # Fallback to first 3 available charts
        available = list((charts_map or {}).items())
        return [(k, k.replace('_', ' ').title()) for k, v in available[:3]]

def generate_growth_insights(aligned, growth_stage, actions):
    """Generate growth-stage specific insights and recommendations"""
    try:
        l28_data = aligned.get('L28', {})
        l28_orders = int(l28_data.get('orders', 0) or 0)
        returning_rate = float(l28_data.get('returning_customer_share', 0) or 0)
        repeat_rate = float(l28_data.get('repeat_rate_within_window', 0) or 0)
        aov_delta = float(l28_data.get('delta', {}).get('aov', 0) or 0)
        
        insights = {
            'growth_stage': growth_stage,
            'stage_title': '',
            'diagnosis_title': '',
            'diagnosis_text': '',
            'opportunity_value': 0,
            'primary_lever': '',
            'secondary_levers': []
        }
        
        if growth_stage == 'early_stage':
            insights.update({
                'stage_title': 'Early Growth Stage',
                'diagnosis_title': '🚀 Focus: Customer Acquisition & First Impressions',
                'diagnosis_text': f'With {l28_orders} orders last month, you\'re in the critical early growth phase. Your primary opportunity is converting first-time buyers into repeat customers and optimizing their initial experience.',
                'primary_lever': 'First-to-Second Purchase Optimization',
                'secondary_levers': ['New Customer Experience', 'Sample Strategy', 'Follow-up Sequences']
            })
        elif growth_stage == 'scaling':
            insights.update({
                'stage_title': 'Scaling Growth Stage', 
                'diagnosis_title': '📈 Focus: Customer Retention & Product Mix',
                'diagnosis_text': f'You\'re acquiring customers well ({l28_orders} orders) but only {returning_rate:.0%} are returning customers. Your growth lever is building customer loyalty and optimizing your product portfolio.',
                'primary_lever': 'Customer Retention Optimization',
                'secondary_levers': ['Winback Campaigns', 'Product Recommendations', 'Loyalty Programs']
            })
        else:  # mature
            insights.update({
                'stage_title': 'Mature Growth Stage',
                'diagnosis_title': '💎 Focus: Customer Value & Lifecycle Optimization', 
                'diagnosis_text': f'With strong retention ({returning_rate:.0%} returning customers), focus on maximizing customer lifetime value and expanding purchase frequency.',
                'primary_lever': 'Customer Lifetime Value Optimization',
                'secondary_levers': ['Premium Product Strategy', 'Subscription Conversion', 'Cross-selling']
            })
        
        # Calculate growth opportunity value
        if actions:
            insights['opportunity_value'] = sum(float(a.get('expected_$', 0) or 0) for a in actions)
        
        return insights
        
    except Exception:
        return {
            'growth_stage': 'scaling',
            'stage_title': 'Growth Analysis',
            'diagnosis_title': 'Strategic Growth Opportunities',
            'diagnosis_text': 'Based on your performance data, we\'ve identified key growth opportunities.',
            'opportunity_value': sum(float(a.get('expected_$', 0) or 0) for a in (actions or [])),
            'primary_lever': 'Customer Growth',
            'secondary_levers': ['Revenue Optimization']
        }

# ---------------- Phase 2: Beauty/Supplement Vertical Intelligence ----------------

def analyze_beauty_patterns(aligned, actions, vertical_mode='mixed'):
    """Analyze beauty-specific patterns and generate insights"""
    try:
        l28_data = aligned.get('L28', {})
        l28_orders = int(l28_data.get('orders', 0) or 0)
        returning_rate = float(l28_data.get('returning_customer_share', 0) or 0)
        aov = float(l28_data.get('aov', 0) or 0)
        
        # Beauty industry benchmarks and patterns
        insights = {
            'product_lifecycle_stage': 'trial-focused',
            'seasonal_factor': 1.0,
            'sample_conversion_opportunity': 0,
            'skincare_cycle_days': 45,
            'sample_conversion_rate': 0,
            'seasonal_multiplier': 1.0,
            'routine_building_score': 0
        }
        
        # Determine product lifecycle stage
        if returning_rate > 0.4:
            insights['product_lifecycle_stage'] = 'routine-building'
            insights['routine_building_score'] = min(100, int(returning_rate * 100))
        elif returning_rate > 0.2:
            insights['product_lifecycle_stage'] = 'loyalty-developing'
            
        # Seasonal analysis for beauty
        current_month = aligned.get('anchor')
        if current_month:
            month_num = current_month.month if hasattr(current_month, 'month') else 1
            # Beauty seasonality: higher in Q4 (holidays) and Q2 (summer prep)
            seasonal_multipliers = {1: 0.9, 2: 0.85, 3: 1.1, 4: 1.2, 5: 1.15, 6: 1.05, 
                                  7: 0.95, 8: 0.9, 9: 1.0, 10: 1.1, 11: 1.25, 12: 1.3}
            insights['seasonal_multiplier'] = seasonal_multipliers.get(month_num, 1.0)
            
        # Sample-to-full conversion analysis
        routine_actions = [a for a in (actions or []) if 'routine' in str(a.get('play_id', '')).lower()]
        if routine_actions:
            insights['sample_conversion_opportunity'] = len(routine_actions)
            # Estimate conversion rate based on AOV and action potential
            if aov > 60:  # Higher AOV suggests full-size purchases
                insights['sample_conversion_rate'] = min(25, int((aov - 40) / 2))
            
        # Skincare repurchase cycle estimation
        if aov > 80:  # Premium skincare
            insights['skincare_cycle_days'] = 60
        elif aov > 50:  # Mid-tier skincare
            insights['skincare_cycle_days'] = 45
        else:  # Entry-level or mixed
            insights['skincare_cycle_days'] = 30
            
        return insights
        
    except Exception:
        return {
            'product_lifecycle_stage': 'trial-focused',
            'seasonal_factor': 1.0,
            'sample_conversion_opportunity': 0,
            'skincare_cycle_days': 45,
            'sample_conversion_rate': 0,
            'seasonal_multiplier': 1.0,
            'routine_building_score': 0
        }

def analyze_supplement_patterns(aligned, actions, vertical_mode='mixed'):
    """Analyze supplement-specific patterns and generate insights"""
    try:
        l28_data = aligned.get('L28', {})
        l28_orders = int(l28_data.get('orders', 0) or 0)
        returning_rate = float(l28_data.get('returning_customer_share', 0) or 0)
        repeat_rate = float(l28_data.get('repeat_rate_within_window', 0) or 0)
        aov = float(l28_data.get('aov', 0) or 0)
        
        insights = {
            'depletion_timing': 'standard_30_day',
            'subscription_readiness': 0,
            'compliance_urgency': 'moderate',
            'compliance_days': 90,
            'depletion_count': 0,
            'subscription_ready_count': 0,
            'supply_duration_estimate': 30
        }
        
        # Supply duration estimation based on AOV
        if aov > 120:  # Bulk/premium supplements
            insights['supply_duration_estimate'] = 90
            insights['depletion_timing'] = 'extended_90_day'
        elif aov > 80:  # Standard multi-month
            insights['supply_duration_estimate'] = 60
            insights['depletion_timing'] = 'standard_60_day'
        else:  # Single month supply
            insights['supply_duration_estimate'] = 30
            
        # Subscription readiness analysis
        if repeat_rate > 0.1:  # 10%+ repeat rate suggests subscription potential
            insights['subscription_ready_count'] = max(1, int(l28_orders * repeat_rate * 0.5))
            insights['subscription_readiness'] = min(100, int(repeat_rate * 500))  # Scale to percentage
            
        # Depletion alerts estimation
        winback_actions = [a for a in (actions or []) if 'winback' in str(a.get('play_id', '')).lower()]
        if winback_actions:
            # Estimate customers approaching depletion
            insights['depletion_count'] = sum(int(a.get('n', 0) or 0) for a in winback_actions)
            
        # Compliance urgency (regulatory/health timeline pressure)
        if returning_rate < 0.1:  # Low retention suggests compliance issues
            insights['compliance_urgency'] = 'high'
            insights['compliance_days'] = 60
        elif returning_rate > 0.3:  # Good retention suggests good compliance
            insights['compliance_urgency'] = 'low'
            insights['compliance_days'] = 120
        else:
            insights['compliance_urgency'] = 'moderate'
            insights['compliance_days'] = 90
            
        return insights
        
    except Exception:
        return {
            'depletion_timing': 'standard_30_day',
            'subscription_readiness': 0,
            'compliance_urgency': 'moderate',
            'compliance_days': 90,
            'depletion_count': 0,
            'subscription_ready_count': 0,
            'supply_duration_estimate': 30
        }

def generate_vertical_insights(aligned, actions, vertical_mode='mixed'):
    """Generate vertical-specific insights for beauty/supplement stores"""
    insights = {
        'vertical_mode': vertical_mode,
        'vertical_title': get_vertical_display_title(vertical_mode),
        'vertical_icon': get_vertical_icon(vertical_mode),
        'show_vertical_section': vertical_mode in ['beauty', 'supplements', 'mixed']
    }
    
    if vertical_mode in ['beauty', 'mixed']:
        insights['beauty'] = analyze_beauty_patterns(aligned, actions, vertical_mode)
        
    if vertical_mode in ['supplements', 'mixed']:
        insights['supplements'] = analyze_supplement_patterns(aligned, actions, vertical_mode)
        
    return insights

def get_vertical_display_title(vertical_mode):
    """Get display title for vertical"""
    titles = {
        'beauty': 'Beauty & Skincare Intelligence',
        'supplements': 'Health & Wellness Intelligence', 
        'mixed': 'Beauty & Wellness Intelligence'
    }
    return titles.get(vertical_mode, 'Industry Intelligence')

def get_vertical_icon(vertical_mode):
    """Get emoji icon for vertical"""
    icons = {
        'beauty': '🌸',
        'supplements': '💊',
        'mixed': '✨'
    }
    return icons.get(vertical_mode, '📊')

def select_priority_kpis(aligned, growth_stage, vertical_mode='mixed'):
    """Select 1 primary + 2 secondary KPIs based on growth stage and vertical"""
    try:
        kpi_priorities = {
            'early_stage': {
                'primary': ('L28', 'new_customer_rate', 'Customer Acquisition Rate'),
                'secondary': [('L28', 'aov', 'Average Order Value'), ('L28', 'repeat_rate_within_window', 'Repeat Purchase Rate')]
            },
            'scaling': {
                'primary': ('L28', 'repeat_rate_within_window', 'Customer Retention'),  
                'secondary': [('L28', 'returning_customer_share', 'Returning Customer Mix'), ('L28', 'aov', 'Average Order Value')]
            },
            'mature': {
                'primary': ('L28', 'aov', 'Revenue Per Customer'),
                'secondary': [('L28', 'discount_rate', 'Discount Efficiency'), ('L28', 'repeat_rate_within_window', 'Loyalty Depth')]
            }
        }
        
        stage_kpis = kpi_priorities.get(growth_stage, kpi_priorities['scaling'])
        
        # Vertical adjustments
        if vertical_mode == 'supplements' and growth_stage == 'scaling':
            # Supplements focus more on subscription conversion
            stage_kpis['primary'] = ('L28', 'repeat_rate_within_window', 'Subscription Momentum')
        elif vertical_mode == 'beauty' and growth_stage == 'mature':
            # Beauty focuses on routine building and LTV
            stage_kpis['primary'] = ('L28', 'returning_customer_share', 'Routine Loyalty')
            
        return stage_kpis['primary'], stage_kpis['secondary']
        
    except Exception:
        return ('L28', 'net_sales', 'Revenue Growth'), [('L28', 'orders', 'Order Volume')]

# ---------------- Vertical config (Beauty/Supplements/Mixed) ----------------
# These tune audience windows and subscription rules per vertical.
VERTICAL_CONFIG: Dict[str, Dict[str, Any]] = {
    'beauty': {
        'subscription_threshold': 3,           # orders before pushing subscription
        'winback_window': (21, 45),
        'dormant_window': (60, 120),
        'seasonal_adjustment': True,
        'gift_period_detection': True,
        'compliance_tracking': False,
    },
    'supplements': {
        'subscription_threshold': 2,           # push subscription faster
        'winback_window': (35, 50),            # slightly later (after 30-day supply)
        'dormant_window': (45, 90),            # tighter window
        'seasonal_adjustment': False,          # less seasonal
        'gift_period_detection': False,
        'compliance_tracking': True,           # unique to supplements
    },
    'mixed': {                                 # many stores sell both
        'use_product_detection': True,
        'apply_category_rules': True,
        # Fallback windows if product type can't be determined
        'winback_window': (21, 45),
        'dormant_window': (60, 120),
        'subscription_threshold': 3,
        'compliance_tracking': True,
    },
}

def get_vertical_mode() -> str:
    """Return vertical mode from env, lowercased and trimmed.

    S-1.7: pass through unknown verticals as-is rather than laundering them
    into ``'mixed'``. The B-7 vertical_guard at the engine entry boundary is
    the single point of refusal for unsupported verticals; if this function
    silently mapped (e.g.) ``'apparel'`` to ``'mixed'``, the guard would
    never fire and the engine would run on mixed priors instead of refusing.

    Default when no env var is set remains ``'mixed'`` (the literal
    beauty+supplements blend, NOT a fallback for unknown inputs).
    """
    v = os.getenv('VERTICAL_MODE') or os.getenv('VERTICAL') or 'mixed'
    return str(v).strip().lower()


def get_subvertical() -> str:
    """Return subvertical from env for seasonality adjustments.

    Valid values: fitness, wellness, sports_nutrition, skincare, haircare, makeup, general
    Only affects seasonal multipliers, not weights or thresholds.
    """
    v = os.getenv('SUBVERTICAL', 'general')
    return str(v).strip().lower() if v else 'general'


def get_vertical(cfg: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Get effective vertical configuration, merged into provided cfg if present."""
    mode = (cfg or {}).get('VERTICAL_MODE') or get_vertical_mode()
    return VERTICAL_CONFIG.get(str(mode).lower(), VERTICAL_CONFIG['mixed'])

def categorize_product(product_name: str) -> tuple[str, int]:
    """Returns (category, typical_days_supply) based on basic token rules.

    Categories: 'supplement' | 'skincare' | 'cosmetics' | 'unknown'
    """
    if not product_name:
        return ('unknown', 60)
    product_lower = str(product_name).lower()

    # Supplements patterns
    if any(term in product_lower for term in ['vitamin', 'supplement', 'protein', 'collagen', 'probiotic', 'omega']):
        if '90' in product_lower or '3 month' in product_lower:
            return ('supplement', 90)
        elif '60' in product_lower or '2 month' in product_lower:
            return ('supplement', 60)
        else:  # Default 30-day supply
            return ('supplement', 30)

    # Beauty patterns
    if any(term in product_lower for term in ['serum', 'cream', 'cleanser', 'moisturizer']):
        return ('skincare', 45)
    if any(term in product_lower for term in ['mascara', 'liner', 'brow']):
        return ('cosmetics', 90)
    if any(term in product_lower for term in ['foundation', 'concealer']):
        return ('cosmetics', 180)

    return ('unknown', 60)

## Removed unused supplement-specific helpers (subscription urgency/compliance)

def subscription_threshold_for_product(product_name: str, cfg: Dict[str, Any] | None = None) -> int:
    """Return per-product subscription threshold (orders) using vertical + product detection."""
    vmode = (cfg or {}).get('VERTICAL_MODE') or get_vertical_mode()
    v = VERTICAL_CONFIG.get(str(vmode).lower(), VERTICAL_CONFIG['mixed'])
    if str(vmode).lower() == 'mixed' and v.get('use_product_detection', False):
        ptype, _ = categorize_product(product_name or '')
        if ptype == 'supplement':
            return 2
        return 3
    # pure verticals
    return int(v.get('subscription_threshold', 3))

DEFAULTS: Dict[str, Any] = {
    # S13.6-T1a (Option D, founder + DS approved 2026-05-30): gate the
    # operator-debug ``notes: List[str]`` debris on S6+ typed dataclasses
    # (Sensitivity, Provenance, PredictedSegment, ModelCardRef,
    # MonthDelta) at engine_run.json serialization time. Default OFF per
    # Pivot 2 — engine emits typed contract surface only. Flip ON via
    # ``INCLUDE_DEBUG_FIELDS=true`` env var for local debug only.
    "INCLUDE_DEBUG_FIELDS": os.getenv("INCLUDE_DEBUG_FIELDS", "false").lower() == "true",
    # thresholds & knobs (sane defaults; .env can override)
    "MIN_N_WINBACK": 75,
    "MIN_N_SKU": 30,
    "AOV_EFFECT_FLOOR": 0.02,
    "REPEAT_PTS_FLOOR": 0.02,
    "DISCOUNT_PTS_FLOOR": 0.02,
    "FDR_ALPHA": 0.15,
    "FINANCIAL_FLOOR": 300.0,           # used when FINANCIAL_FLOOR_MODE=fixed
    "FINANCIAL_FLOOR_MODE": "auto",     # auto|fixed
    "FINANCIAL_FLOOR_FIXED": 300.0,
    # M4a T4a.8: defaults flipped to False. Both code paths remain in tree
    # (deletion is M10) but they no longer turn on by default. Cohort pooling
    # uses a placeholder p=1.0 path; the bias correction is a hardcoded
    # window-specific multiplier {7:1.0, 28:0.95, 56:0.90, 90:0.85} that the
    # statistical-code-reviewer flagged as fabricated.
    "ENABLE_COHORT_POOLING": os.getenv("ENABLE_COHORT_POOLING", "false").lower() == "true",  # Enable cohort-based significance pooling
    "ENABLE_REPEAT_RATE_BIAS_CORRECTION": os.getenv("ENABLE_REPEAT_RATE_BIAS_CORRECTION", "false").lower() == "true",  # Apply window-specific bias correction
    # M4a feature flags. Default OFF in M4a so the Milestone 0 golden tree is
    # not perturbed when the flags are unset. The implementation manager plan
    # flips STATS_NAN_FOR_HARDCODED on at the end of M4a's bake-in window and
    # EVIDENCE_CLASS_ENFORCED on in M4b. Both are removed in M10 once the
    # behavior becomes unconditional.
    "STATS_NAN_FOR_HARDCODED": os.getenv("STATS_NAN_FOR_HARDCODED", "false").lower() == "true",
    "EVIDENCE_CLASS_ENFORCED": os.getenv("EVIDENCE_CLASS_ENFORCED", "false").lower() == "true",
    # M5 Guardrail-engine flags. All default OFF so the engine is byte-identical
    # to M4b when no guardrail flag is set. Each gate is independently
    # enable-able so the M5 reviewer can flip them on individually behind a
    # canonical flag set; M10 deletes the flags once each becomes the default.
    "INVENTORY_GATE_ENABLED": os.getenv("INVENTORY_GATE_ENABLED", "false").lower() == "true",
    # B-1: ANOMALY_GATE_ENABLED defaults to ON. The detector already runs
    # in the engine_run adapter; this flip auto-routes a populated
    # ``data_quality_flags`` list into ABSTAIN_HARD (hard flags) or
    # ABSTAIN_SOFT (soft POST_PROMO_WINDOW) inside ``apply_guardrails``.
    # Healthy fixtures (e.g. Beauty pinned) produce zero flags, so the
    # M0 byte-identical contract is preserved. Set the env var to "false"
    # to keep the legacy no-op behavior.
    "ANOMALY_GATE_ENABLED": os.getenv("ANOMALY_GATE_ENABLED", "true").lower() == "true",
    "CANNIBALIZATION_GATE_ENABLED": os.getenv("CANNIBALIZATION_GATE_ENABLED", "false").lower() == "true",
    "MATERIALITY_FLOOR_SCALE_AWARE": os.getenv("MATERIALITY_FLOOR_SCALE_AWARE", "false").lower() == "true",
    "RECENTLY_RUN_FATIGUE_ENABLED": os.getenv("RECENTLY_RUN_FATIGUE_ENABLED", "false").lower() == "true",
    # M6 Conservative-economic-sizing flag. Default OFF so the M5 EngineRun
    # output is byte-identical when the flag is unset. When ON, the V2 path
    # in the adapter replaces ``revenue_range`` on EngineRun.recommendations
    # with ``sizing.size_play(...)`` output and writes a shadow-compare
    # artifact to ``receipts/v2_sizing_shadow.json``. The legacy
    # ``calculate_28d_revenue`` is NOT touched (T6.5 / M10 deletes it).
    "ENGINE_V2_SIZING": os.getenv("ENGINE_V2_SIZING", "false").lower() == "true",
    # M7 V2 Decision Selector flag. Default OFF so the EngineRun output is
    # byte-identical to M6 when the flag is unset. When ON, ``src.main``
    # invokes ``src.decide.decide(engine_run, cfg=cfg)`` after the M5/M6
    # blocks, replacing the EngineRun's recommendations / considered /
    # abstain / watching with the M7 decision layer. The renderer is NOT
    # touched (M8 owns the renderer flip). The legacy CSV->HTML workflow,
    # ``actions_log.json``, and the briefing template are unchanged.
    "ENGINE_V2_DECIDE": os.getenv("ENGINE_V2_DECIDE", "false").lower() == "true",
    # M8 V2 Renderer flag. Default OFF so the merchant-facing briefing.html
    # is byte-identical to M7 when the flag is unset. When ON, ``src.main``
    # routes ``render_briefing(...)`` through ``src.storytelling_v2`` and
    # renders the new three-section Play Thesis layout (state-of-store +
    # Recommended + Considered + Watching + data-quality footer) plus the
    # ABSTAIN_HARD data-quality memo and the ABSTAIN_SOFT callout. The
    # legacy renderer (``src.storytelling.build_briefing_story`` + the Jinja
    # briefing template) remains in the repo as the flag-off path until M10.
    "ENGINE_V2_OUTPUT": os.getenv("ENGINE_V2_OUTPUT", "false").lower() == "true",
    # Phase 6A Ticket A4 — Recommended Experiment slate flag. Default OFF.
    # When ON, ``src.decide.decide`` invokes
    # ``_select_recommended_experiments`` and populates
    # ``EngineRun.recommended_experiments``. With the flag OFF the field
    # is always ``[]`` and no slate logic runs. Renderer is unchanged in
    # A4 (Ticket B1 owns the renderer for the new section).
    "ENGINE_V2_SLATE": os.getenv("ENGINE_V2_SLATE", "false").lower() == "true",
    # Sprint 7.5 Ticket T3 — cold-start blend refusal flag.
    # Default OFF: sizing keeps the legacy ``source_class != causal ->
    # suppressed`` rule and decide() does not emit SOFT_PRIOR_UNVALIDATED
    # nor PRIOR_UNVALIDATED. When ON (T3.5 flips the default), sizing
    # refuses to blend on priors carrying
    # ``validation_status in {heuristic_unvalidated, placeholder}``,
    # decide() emits ``AbstainMode.SOFT_PRIOR_UNVALIDATED`` when zero
    # firing Tier-B builders + zero validated Tier-C plays, and the
    # considered fan-out routes refused plays with
    # ``ReasonCode.PRIOR_UNVALIDATED``. ARCHITECTURE_PLAN.md Part III-1
    # is the design source; ``config/priors_sources/`` holds the per-prior
    # validation memos. Set ``ENGINE_V2_PRIORS_VALIDATION=true`` in env
    # to flip per-process; founder beta cut is T3.5's atomic flip.
    # Sprint 7.5 Ticket T3.5: default flipped from OFF to ON. The
    # cold-start blend-refusal rule is now the engine's default posture
    # (beta cut). Operator override via env var
    # ``ENGINE_V2_PRIORS_VALIDATION=false`` still works for rollback if
    # a beta merchant trips on the tighter rule. See Part III-1 §III-1
    # Step 5 ("Honest abstain fallback") for the design rationale and
    # the T3.5 summary doc for the per-fixture diff.
    "ENGINE_V2_PRIORS_VALIDATION": os.getenv(
        "ENGINE_V2_PRIORS_VALIDATION", "true"
    ).lower() == "true",
    # Sprint 6 Ticket T1 — winback_dormant_cohort Tier-B builder flag.
    # Sprint 6 Ticket T1.5 (2026-05-17): default flipped from OFF to ON.
    # The builder is now invoked by default; ``src.main.run`` routes the
    # winback_dormant_cohort candidate (when its 3-part cohort definition
    # fires) through ``measurement_builder.build_prior_anchored_play_card``,
    # which anchors the PlayCard posterior on ``winback_21_45.base_rate``
    # via ``bayesian_blend``. Validated-prior verticals (beauty Klaviyo)
    # emit a non-suppressed BLEND range when the audience clears 500;
    # heuristic-unvalidated verticals (supplements, mixed) route to
    # Considered with PRIOR_UNVALIDATED via decide.py's
    # ``_route_prior_unvalidated_holds`` seam.
    #
    # Per T1.5 fixture probe (2026-05-17): on the pinned synthetic
    # fixtures the cohort audience is below the 500 floor (Beauty=356,
    # supplements=0), so the candidate routes to ``audience_too_small``
    # via the M3 preliminary_rejection_reason path and is then trimmed
    # by the existing populate_considered_from_candidates cap. Briefings
    # and engine_run.json content (modulo the random run_id UUID) are
    # byte-identical pre/post flip — NO fixture re-pin required at T1.5.
    # The Klaviyo validated_external prior activation moment is
    # technically deferred to whenever a beta brand with >=500 lapsed
    # repeat-buyers in the 21-45d window runs the engine.
    #
    # Operator override: set ``ENGINE_V2_BUILDER_WINBACK_DORMANT=false``
    # in env to roll back to the T1 default.
    "ENGINE_V2_BUILDER_WINBACK_DORMANT": os.getenv(
        "ENGINE_V2_BUILDER_WINBACK_DORMANT", "true"
    ).lower() == "true",
    # Sprint 7.6 Ticket T1 — B-1 winback observed-effect wiring flag.
    # Default OFF at T1 (impl + tests only; no merchant-facing change;
    # all pinned fixtures byte-identical because cold-start path
    # observed_k=observed_n=0 remains in force). T1.5 (separate ticket)
    # flips to ON atomically with the Beauty pinned-slate re-pin per
    # Sprint 2 Risk #4 discipline. When ON, the prior-anchored builder
    # for ``winback_dormant_cohort`` computes per-store
    # lapse_recovery_rate recent-vs-prior across {L28, L56, L90} using
    # the shared T0 helper (src/measurement_observed.py) and threads
    # the L28 (k, n) into the existing bayesian_blend seam in
    # src/sizing.py. EB blend math is UNTOUCHED — this flag only changes
    # what (k, n) flows into ``bayesian_blend(observed_k, observed_n)``.
    # S7.6-T1.5 (2026-05-21): default flipped OFF -> ON. Tripwire probe
    # on healthy_beauty_240d:
    #   observed_k=55, observed_n=334, posterior_value=0.159887
    #   (prior 0.08, pseudo_n=20), posterior_ratio=store_dominant,
    #   sign_agreement=3/3 (L28 p=0.001, L56 p=0.065, L90 p=0.48).
    # The Beauty winback_dormant_cohort card now posts with a
    # store-dominant posterior; Beauty fixture re-pinned atomically in
    # this commit per Sprint 2 Risk #4 discipline. Supplements still has
    # the heuristic_unvalidated winback_21_45.base_rate prior (suppressed
    # with prior_unvalidated reason) so supplements winback card never
    # reaches the prior-anchored emit path; supplements fixture stays
    # byte-identical (confirmed in commit verification).
    "ENGINE_V2_OBSERVED_EFFECT_WINBACK": os.getenv(
        "ENGINE_V2_OBSERVED_EFFECT_WINBACK", "true"
    ).lower() == "true",
    # Sprint 7.6 Ticket T2 — B-2 replenishment_due observed-effect wiring
    # flag. Default OFF at T2 (impl + tests only; no merchant-facing
    # change; all pinned fixtures byte-identical because cold-start path
    # observed_k=observed_n=0 remains in force). T2.5 (separate ticket)
    # flips to ON atomically with the Beauty pinned-slate re-pin per
    # Sprint 2 Risk #4 discipline, conditional on the tripwire probe
    # showing observed_n >= 30 on healthy_beauty_240d. Supplements is
    # blocked on KI-27 (replenishment_parser returns None for
    # vertical=supplements); when ON, the helper short-circuits for
    # supplements and passes observed_k=observed_n=0 so the cold-start
    # path remains in force on supplements until KI-27 lands.
    "ENGINE_V2_OBSERVED_EFFECT_REPLENISHMENT": os.getenv(
        "ENGINE_V2_OBSERVED_EFFECT_REPLENISHMENT", "false"
    ).lower() == "true",
    # Sprint 7.6 Ticket T3 — B-3 discount_dependency_hygiene observed-effect
    # wiring flag. Default OFF at T3 (impl + tests only; no merchant-facing
    # change; all pinned fixtures byte-identical because cold-start path
    # observed_k=observed_n=0 remains in force). T3.5 (separate ticket)
    # flips to ON atomically with the Beauty pinned-slate re-pin per
    # Sprint 2 Risk #4 discipline, conditional on the tripwire probe
    # showing observed_n >= 30 on healthy_beauty_240d. Supplements is
    # blocked by DS Memo-4 REJECT (no supplements prior block by design);
    # the helper short-circuits for supplements and passes
    # observed_k=observed_n=0 so the cold-start path remains in force on
    # supplements unconditionally (Path-D dormant).
    # S7.6-T3.5 (2026-05-23): default flipped OFF -> ON atomically with the
    # Beauty pinned-slate re-pin. Tripwire probe (scripts/s7_6_t3_5_probe.py)
    # on healthy_beauty_240d returned observed_n=148451, observed_k=17353,
    # posterior_value 0.022 -> 0.116881 (store_dominant), sign_agreement=3/3
    # across {L28,L56,L90}, dominant_sign=+1. Supplements card absent
    # (helper short-circuits per Path-D Memo-4 REJECT), supplements pinned
    # briefing byte-identical post-flip.
    "ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE": os.getenv(
        "ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE", "true"
    ).lower() == "true",
    # Sprint 7.6 Ticket T4 — B-4 cohort_journey_first_to_second observed-effect
    # wiring flag. Default OFF at T4 (impl + tests only; no merchant-facing
    # change). T4.5 (separate ticket) will flip the default to ``true``
    # atomically with the Beauty + Supplements pinned-slate re-pin per
    # Sprint 2 Risk #4 discipline, conditional on the tripwire probe
    # showing observed_n >= 30 on healthy_beauty_240d. Vertical scope per
    # plan B-4: applies to "*" (all verticals) — the validated_external
    # first_to_second_purchase.base_rate prior is wildcard-vertical (S7.5-T2).
    # The helper enforces the BERKSON INVARIANT (early-half-window cohort
    # denominators only); see tests/test_berkson_invariant.py +
    # project_journey_p_zero.md memory 2026-04-30 (original fix 554960d /
    # Phase 4.1).
    # T4.5 flipped default OFF -> ON (2026-05-23): probe on Beauty fixture showed
    # observed_n=392, sign_agreement=3/3, dominant_sign=+1, store_dominant. Berkson
    # early-half-window invariant preserved (tests/test_berkson_invariant.py
    # still passing). Supplements lands in Considered with no blend_provenance
    # (thin first-to-second signal; KI-20 contract preserved).
    "ENGINE_V2_OBSERVED_EFFECT_JOURNEY": os.getenv(
        "ENGINE_V2_OBSERVED_EFFECT_JOURNEY", "true"
    ).lower() == "true",
    # Sprint 7.6 Ticket T5 --- B-5 aov_lift_via_threshold_bundle observed-effect
    # wiring flag. Default OFF at T5 (impl + tests only; no merchant-facing
    # change; pinned fixtures byte-identical because cold-start path
    # observed_k=observed_n=0 remains in force). T5.5 (separate ticket)
    # flips atomically with the Beauty pinned-slate re-pin per Sprint 2
    # Risk #4 discipline. Vertical scope per plan B-5:248: BEAUTY ONLY ---
    # supplements is unconditionally vertical-excluded (mirrors the
    # audience-builder gate at audience_builders.py:997-1007 under
    # ENGINE_V2_AOV_THRESHOLD_FROM_DATA). The helper computes a DUAL
    # statistical test: Welch-t on order-level AOV + two-proportion z-test
    # on near-threshold band share, BOTH must reach p<0.10 jointly to
    # drive T6 eligibility.
    # S7.6-T5.5 (this commit): flipped default OFF -> ON now that the full
    # T5 -> T6 -> T6.5 -> T5.6 pipeline is in place (compute -> gate ->
    # demote -> preserve Tier-B -> priority_prepend protection). Joint-fail
    # on Beauty aov_bundle (Welch p~0.876, z-prop p~0.877) honestly demotes
    # to Considered[0] with SIGNAL_INCONSISTENT_ACROSS_WINDOWS reason +
    # would_be_measured_by preserved. Supplements helper short-circuits
    # per vertical_excluded_per_b5_248.
    "ENGINE_V2_OBSERVED_EFFECT_AOV_BUNDLE": os.getenv(
        "ENGINE_V2_OBSERVED_EFFECT_AOV_BUNDLE", "true"
    ).lower() == "true",
    # Sprint 8 Ticket T1 — typed EvidenceSourceChip on PlayCard.
    # Default OFF at T1 (impl + tests only; no merchant-facing change;
    # all pinned fixtures byte-identical because every
    # ``PlayCard.evidence_source`` stays ``None`` under flag OFF). T1.5
    # (separate atomic ticket) flips the default to ``true`` with the
    # Beauty + Supplements pinned-fixture re-pin per S7.6 atomic-flip
    # discipline (memory.md S7.6 T*N*.5 pattern). When ON, the four
    # wired Tier-B builders (winback_dormant_cohort,
    # discount_dependency_hygiene, cohort_journey_first_to_second,
    # aov_lift_via_threshold_bundle) populate
    # ``evidence_source = EvidenceSourceChip.STORE_OBSERVED`` via the
    # single :func:`measurement_builder.build_prior_anchored_play_card`
    # construction site. Tier-A / Tier-C / Tier-D / legacy plays are
    # NOT populated in S8-T1 scope (per IM plan + DS verdict §5
    # invariant 12 capping S8 PlayCard additive surface). The
    # ``ENGINE_V2_SENSITIVITY`` flag (S8-T2, separate ticket) is
    # intentionally distinct per DS Q7 verdict 2026-05-24.
    "ENGINE_V2_TIER_CHIP": os.getenv(
        "ENGINE_V2_TIER_CHIP", "true"
    ).lower() == "true",
    # Sprint 8 Ticket T2 — typed Sensitivity block on PlayCard.
    # SEPARATE flag from ``ENGINE_V2_TIER_CHIP`` per DS Q7 verdict
    # 2026-05-24 §4 (atomic per-ticket flip discipline; the S7.6-T7.5
    # spiral happened because bundled flag flips hid which sub-change
    # caused drift). Default OFF at T2 (impl + tests only; no merchant-
    # facing change; all pinned fixtures byte-identical because every
    # ``PlayCard.sensitivity`` stays ``None`` under flag OFF). T2.5
    # (separate atomic ticket) flips the default to ``true`` with the
    # Beauty + Supplements pinned-fixture re-pin per S7.6 atomic-flip
    # discipline (memory.md S7.6 T*N*.5 pattern). When ON, the four
    # wired Tier-B builders (winback_dormant_cohort,
    # discount_dependency_hygiene, cohort_journey_first_to_second,
    # aov_lift_via_threshold_bundle) populate
    # ``sensitivity = Sensitivity(...)`` via the single
    # :func:`measurement_builder.build_prior_anchored_play_card`
    # construction site — but only on the validated, non-suppressed
    # BLEND path (suppressed and prior-unvalidated paths leave the
    # field ``None`` per IM plan Part B S8-T2). Tier-A / Tier-C / Tier-D
    # / legacy plays are NOT populated in S8-T2 scope (per IM plan + DS
    # verdict §5 invariant 12 capping S8 PlayCard additive surface at
    # 3 fields: evidence_source [done], sensitivity [this commit],
    # provenance [T3]).
    "ENGINE_V2_SENSITIVITY": os.getenv(
        "ENGINE_V2_SENSITIVITY", "true"
    ).lower() == "true",
    # Sprint 8 Ticket T3 — typed Provenance audit object on PlayCard
    # (third and final S8 additive PlayCard field per DS verdict
    # 2026-05-24 §5 invariant 12; chip done at T1.5, sensitivity done at
    # T2.5, provenance lands here). SEPARATE flag from
    # ``ENGINE_V2_TIER_CHIP`` and ``ENGINE_V2_SENSITIVITY`` per S7.6
    # atomic-flip discipline (the S7.6-T7.5 spiral happened because
    # bundled flag flips hid which sub-change caused drift). Default OFF
    # at T3 (impl + tests only; no merchant-facing change; all pinned
    # fixtures byte-identical because every ``PlayCard.provenance`` stays
    # ``None`` under flag OFF). T3.5 (separate atomic ticket) flips the
    # default to ``true`` with the Beauty + Supplements pinned-fixture
    # re-pin per S7.6 atomic-flip discipline (memory.md S7.6 T*N*.5
    # pattern). When ON, the four wired Tier-B builders
    # (winback_dormant_cohort, discount_dependency_hygiene,
    # cohort_journey_first_to_second, aov_lift_via_threshold_bundle)
    # populate ``provenance = Provenance(...)`` via the single
    # :func:`measurement_builder.build_prior_anchored_play_card`
    # construction site — but only on the validated, non-suppressed BLEND
    # path (suppressed and prior-unvalidated paths leave the field
    # ``None``; HEURISTIC_UNVALIDATED + PLACEHOLDER refusal is the DS §5
    # invariant 2 enforcement — no audit object for a refused status).
    #
    # Per DS verdict 2026-05-24 §1 + §2: the empirical-Bayes blend math
    # is ALREADY SHIPPED at ``src/sizing.py`` (S7.5-T3 ``bayesian_blend``
    # + ``effective_pseudo_n`` + ``PSEUDO_N_BY_STATUS`` table). S8-T3
    # formalizes the audit contract surface; the blend math is unchanged.
    # NO new pseudo_N numbers, NO ``Prior.pseudo_N`` per-prior override
    # field (§6 F2 rejected), NO new ``RevenueRange.source`` literal (Q5
    # closed — reuse ``blend``).
    "ENGINE_V2_EB_BLEND": os.getenv(
        "ENGINE_V2_EB_BLEND", "true"
    ).lower() == "true",
    # Sprint 8 Ticket T4 — Play Library wave 1 (refactor-only).
    #
    # Wave 1 = {winback_dormant_cohort, replenishment_due,
    # discount_dependency_hygiene} per DS verdict 2026-05-24 §3 Q6
    # (CONCUR with IM default; including the dormant ``replenishment_due``
    # is load-bearing because it is the only wave-1 test case that
    # verifies the migration template handles dormant plays correctly,
    # preserving KI-NEW-G honest-dormancy).
    #
    # The wave-1 plays migrate to ``plays/<play_id>/`` first-class
    # directory layout (spec.yaml + audience.py re-export + builder.py
    # re-export + copy.md). At flag OFF (default at T4 impl) the
    # ``plays/`` directory is not consulted; legacy ``src/play_registry.py``
    # entries + ``src/audience_builders.py`` callables + ``_PRIOR_ANCHORED``
    # entries serve all traffic. At flag ON (deferred T4.5 atomic flip)
    # the registry consults ``plays.get_play_definition(play_id)`` first
    # for the 3 wave-1 plays and asserts the spec.yaml-resolved callables
    # are identity-equal to the legacy registry's callables; falls back
    # to legacy for the 11 unmigrated plays. The consult-and-verify
    # design preserves the byte-identical contract at BOTH flag states
    # (zero re-pin target per IM Part I) — flag ON only activates an
    # integrity check, not a behavior change.
    #
    # NO new PlayCard fields (S8 additive surface capped at 3 per DS §5
    # invariant 12: evidence_source [T1.5] + sensitivity [T2.5] +
    # provenance [T3.5]). NO touches to src/main.py:1380-1597 injection
    # blocks (KI-NEW-L deferred to S13.5). NO HTML renderer changes.
    #
    # T4.5 is dispatched as a separate atomic flag-flip commit per S7.6
    # T*N*.5 discipline (memory.md). The acceptance pin
    # (tests/test_s8_t4_play_library_wave1_migration.py) asserts exactly
    # these three play_ids have a plays/<play_id>/spec.yaml artifact AND
    # that ``replenishment_due`` produces zero audience on the Beauty
    # pinned fixture at BOTH flag states (honest-dormancy preserved).
    "ENGINE_V2_PLAY_LIBRARY_WAVE1": os.getenv(
        "ENGINE_V2_PLAY_LIBRARY_WAVE1", "true"
    ).lower() == "true",
    # Sprint 7.6 Ticket T6 — observed-effect eligibility gate + 3-state
    # copy ladder. Default OFF at T6 (impl + tests only; no merchant-
    # facing change). T6.5 (separate atomic ticket) flips the default to
    # ``true`` with Beauty + Supplements pinned-fixture re-pin.
    #
    # When ON, the prior-anchored card seam consumes the
    # ``MultiWindowAgreement`` stash on ``blend_provenance`` and:
    #
    #  (1) downgrades cards with ``observed_n > OBSERVED_MIN_ELIGIBILITY_N``
    #      AND ``sign_agreement_count < 2`` to Considered with
    #      ``ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS``;
    #  (2) for builders that stash ``*_band`` windows (currently only
    #      ``aov_lift_via_threshold_bundle``) enforces a joint
    #      ``p < 0.10`` on BOTH ``L28`` AND ``L28_band`` windows (DS
    #      architect verdict 2026-05-23 amendment to the T6 spec);
    #  (3) rewrites ``why_now`` per the 3-state copy ladder
    #      (cold-start / accumulating / mature) keyed off
    #      ``posterior_ratio = observed_n / (observed_n + pseudo_n)``.
    #
    # Flag-OFF path: gate routing is a no-op, copy ladder is a no-op;
    # M0 + Beauty + Supplements pinned briefings stay byte-identical.
    # T6.5 (2026-05-23): default flipped to ``true`` atomically with Beauty +
    # Supplements pinned re-pin (Beauty re-pins to encode the 3-state copy
    # ladder mature prefix on the three active observed-effect cards;
    # Supplements stays byte-identical because no card carries observed-effect
    # data under current flag set — T5 aov_bundle remains OFF pending T5.5).
    "ENGINE_V2_OBSERVED_ELIGIBILITY_GATE": os.getenv(
        "ENGINE_V2_OBSERVED_ELIGIBILITY_GATE", "true"
    ).lower() == "true",
    # Sprint 7.6 Ticket T6 — minimum ``observed_n`` below which the
    # eligibility gate is a no-op (cold-start path stays prior-only).
    "OBSERVED_MIN_ELIGIBILITY_N": int(
        os.getenv("OBSERVED_MIN_ELIGIBILITY_N", "30")
    ),
    # Sprint 10 Ticket T1 — BG/NBD predictive layer (flag-OFF land).
    #
    # When ON (deferred to S10-T1.5 atomic flag flip), the engine fits
    # BG/NBD via ``src/predictive/bgnbd.py::fit_bgnbd`` per merchant and
    # writes a ``ModelCard`` to ``engine_run.predictive_models["bgnbd"]``.
    # Per-customer ``p_alive`` + expected purchases land at
    # ``data/<store_id>/predictive/bgnbd.parquet`` **only when
    # fit_status in {VALIDATED, PROVISIONAL}**.
    #
    # Flag-OFF (S10-T1 default): no module-level side effects, no parquet
    # writes, no ModelCard in engine_run.json. Pinned fixtures
    # byte-identical by construction.
    #
    # S10 is operator-only — no PlayCard / briefing.html consumption of
    # the fit output at T1. PlayCard.predicted_segment + model_card_ref
    # stay ``None`` at S10 close; S13 wires the populating producers.
    "ENGINE_V2_ML_BGNBD": os.getenv(
        "ENGINE_V2_ML_BGNBD", "true"
    ).lower() == "true",
    # Sprint 10 Ticket T2 — Gamma-Gamma predictive layer (flag-OFF land).
    #
    # When ON (deferred to S10-T2.5 atomic flag flip), the engine fits
    # Gamma-Gamma via ``src/predictive/gamma_gamma.py::fit_gamma_gamma``
    # per merchant — taking the same-run BG/NBD ModelCard as a
    # chained-refusal input — and writes a ``ModelCard`` to
    # ``engine_run.predictive_models["gamma_gamma"]``. Per-customer
    # expected average spend lands at
    # ``data/<store_id>/predictive/gamma_gamma.parquet`` **only when
    # fit_status in {VALIDATED, PROVISIONAL}**.
    #
    # Flag-OFF (S10-T2 default): no module-level side effects, no
    # parquet writes, no Gamma-Gamma ModelCard in engine_run.json.
    # Pinned fixtures byte-identical by construction.
    #
    # Chained-refusal contract (IM plan §C.2): when the same engine_run's
    # BG/NBD ModelCard is REFUSED or INSUFFICIENT_DATA, Gamma-Gamma
    # short-circuits to REFUSED with ``chained_bgnbd_refusal`` warning.
    # Rationale: cannot rank monetary value if cannot rank customer
    # aliveness at all.
    #
    # S10 is operator-only — no PlayCard / briefing.html consumption of
    # the fit output at T2. PlayCard.predicted_segment + model_card_ref
    # stay ``None`` at S10 close; S13 wires the populating producers.
    "ENGINE_V2_ML_GAMMA_GAMMA": os.getenv(
        "ENGINE_V2_ML_GAMMA_GAMMA", "true"
    ).lower() == "true",
    # Sprint 11 Ticket T1 — Cox PH survival predictive layer (flag-OFF land).
    #
    # When ON (deferred to S11-T1.5 atomic flag flip), the engine fits
    # Cox PH via ``src/predictive/survival.py::fit_survival`` per merchant
    # — taking the same-run BG/NBD ModelCard as a chained-refusal input —
    # and writes a ``ModelCard`` to
    # ``engine_run.predictive_models["survival"]``. Per-customer
    # ``p_survival_90d`` + ``expected_days_to_next_purchase`` lands at
    # ``data/<store_id>/predictive/survival.parquet`` **only when
    # fit_status in {VALIDATED, PROVISIONAL}**.
    #
    # Flag-OFF (S11-T1 default): no module-level side effects, no parquet
    # writes, no survival ModelCard in engine_run.json. Pinned fixtures
    # byte-identical by construction.
    #
    # Chained-refusal contract (S11-T1): when the same engine_run's
    # BG/NBD ModelCard is REFUSED or INSUFFICIENT_DATA, survival
    # short-circuits to REFUSED with ``chained_bgnbd_refusal`` warning.
    # Rationale: Cox PH hazard transforms the same gap-time signal BG/NBD
    # evaluates — uninformative gap distribution cannot yield a better
    # Cox fit.
    #
    # DS-locked library substitution (2026-05-26): uses ``scikit-survival``
    # (NOT ``lifelines``). sklearn-ecosystem-backed, better-maintained for
    # the new Cox PH surface. Substitution rationale in
    # ``agent_outputs/ds-architect-s11-plan-review.md`` §(b).
    #
    # S11 is operator-only — no PlayCard / briefing.html consumption of
    # the fit output at T1. PlayCard.predicted_segment + model_card_ref
    # stay ``None`` at S11 close; S13 wires the populating producers.
    "ENGINE_V2_ML_SURVIVAL": os.getenv(
        "ENGINE_V2_ML_SURVIVAL", "true"
    ).lower() == "true",
    # Sprint 11 Ticket T2 — Collaborative Filtering (implicit ALS) predictive
    # layer (flag-OFF land).
    #
    # When ON (deferred to S11-T2.5 atomic flag flip), the engine fits
    # implicit ALS via ``src/predictive/cf.py::fit_cf`` per merchant — CF
    # is INDEPENDENT of BG/NBD (no chained refusal) — and writes a
    # ``ModelCard`` to ``engine_run.predictive_models["cf"]``. Per-customer
    # top-N look-alikes lands at
    # ``data/<store_id>/predictive/cf.parquet`` **only when fit_status in
    # {VALIDATED, PROVISIONAL}**.
    #
    # Flag-OFF (S11-T2 default): no module-level side effects, no parquet
    # writes, no CF ModelCard in engine_run.json. Pinned fixtures
    # byte-identical by construction.
    #
    # CF independence contract (DS-locked 2026-05-26, per DS S11 plan
    # review §A.6): CF's customer×item co-occurrence signal does NOT
    # structurally depend on the gap-time signal that BG/NBD/survival
    # evaluate. CF fits independently when BG/NBD is OFF or REFUSED. DO
    # NOT chain CF on BG/NBD. Deliberate architectural divergence from
    # survival.
    #
    # Validation metrics (DS-locked):
    # - PRIMARY gate: top-K recall @ K=10 (stage-keyed VALIDATED floors
    #   {startup 0.05, growth 0.06, mature 0.08, enterprise 0.10};
    #   PROVISIONAL floor 0.03; below or convergence failure → REFUSED).
    # - SECONDARY diagnostic: coverage @ 10 (operator-visible; does NOT
    #   gate).
    #
    # S11 is operator-only — no PlayCard / briefing.html consumption of
    # the fit output at T2. PlayCard.predicted_segment + model_card_ref
    # stay ``None`` at S11 close; S13 wires the populating producers.
    # S11-T2.5 (2026-05-28): default flipped "false" -> "true". Atomic
    # flip lands the CF (implicit ALS) orchestration wire-up at
    # ``src/main.py`` immediately after the survival PREDICTIVE_FIT block.
    # CF is INDEPENDENT of BG/NBD (DS-locked) — the orchestration wire
    # passes NO ``bgnbd_model_card`` argument. On the synthetic pinned
    # fixtures the resulting ``fit_status`` lands in the four-state
    # vocabulary {VALIDATED, PROVISIONAL, REFUSED, INSUFFICIENT_DATA}
    # without chained-refusal coupling. briefing.html is byte-identical
    # to pre-T2.5 (renderer does NOT read predictive_models["cf"]).
    "ENGINE_V2_ML_CF": os.getenv(
        "ENGINE_V2_ML_CF", "true"
    ).lower() == "true",
    # Sprint 12 Ticket T1 — RFM (Recency × Frequency × Monetary)
    # segmentation predictive substrate (flag-OFF land).
    #
    # When ON (deferred to S12-T1.5 atomic flag flip), the engine fits
    # deterministic RFM via ``src/predictive/rfm.py::fit_rfm`` per
    # merchant — RFM is INDEPENDENT of BG/NBD (no chained refusal,
    # mirrors CF posture) — and writes a ``ModelCard`` to
    # ``engine_run.predictive_models["rfm"]``. Per-customer R/F/M
    # quintile + named-segment assignment lands at
    # ``data/<store_id>/predictive/rfm.parquet`` **only when fit_status
    # in {VALIDATED, PROVISIONAL}**.
    #
    # Flag-OFF (S12-T1 default): no module-level side effects, no
    # parquet writes, no RFM ModelCard in engine_run.json. Pinned
    # fixtures byte-identical by construction.
    #
    # Validation metrics (DS-locked 2026-05-28):
    # - PRIMARY gate: segment_monotonicity_spearman (Spearman between
    #   named-segment LTV-rank-order and observed monetary value;
    #   stage-keyed VALIDATED floors {startup 0.60, growth 0.65,
    #   mature 0.70, enterprise 0.70}; PROVISIONAL floor 0.40).
    # - SECONDARY REFUSED guard: quintile_coverage_min (below 0.05 →
    #   REFUSED, indicates pd.qcut bin collapse).
    # - INSUFFICIENT_DATA: n_customers < 50 (absolute floor).
    #
    # S12 is operator-only — no PlayCard / briefing.html consumption
    # of the fit output at T1. PlayCard.predicted_segment +
    # model_card_ref stay ``None`` at S12 close; S13 wires the
    # populating producers.
    # S12-T1.5 (2026-05-28): atomic flip of ``ENGINE_V2_ML_RFM`` default
    # ``false`` -> ``true``. Wires ``fit_rfm`` into ``src/main.py``
    # orchestration immediately after the CF PREDICTIVE_FIT block. **RFM
    # is INDEPENDENT of BG/NBD (DS-locked S12 plan review §F).** The
    # orchestration wire passes NO ``bgnbd_model_card`` argument — mirrors
    # the CF (S11-T2.5) architectural posture, NOT the survival/G-G
    # chained-refusal shape. ModelCard lands on
    # ``engine_run.predictive_models["rfm"]``. Per DS verdict §I, Beauty
    # (3,844 repeat customers on the synthetic fixture) is expected to
    # VALIDATE — Pivot-5-consistent structural correctness of
    # deterministic segmentation, NOT predictive overfit. Renderer does
    # NOT consume; briefing.html byte-identical for all 5 fixtures.
    "ENGINE_V2_ML_RFM": os.getenv(
        "ENGINE_V2_ML_RFM", "true"
    ).lower() == "true",
    # Sprint 12 Ticket T2 — retention curves substrate flag.
    # S12-T2.5 (2026-05-28): atomic flip of ``ENGINE_V2_ML_RETENTION``
    # default ``false`` -> ``true``. Wires ``fit_retention`` into
    # ``src/main.py`` orchestration immediately after the RFM
    # PREDICTIVE_FIT block.
    #
    # Retention is a COHORT-AGGREGATE diagnostic, NOT a per-customer
    # ranker. RetentionCard lands on ``engine_run.cohort_diagnostics["retention"]``
    # (NEW top-level slot added at T2) — NOT ``predictive_models`` (DS S12
    # plan review §C). Retention is INDEPENDENT — no chained refusal on
    # BG/NBD or any other substrate (mirrors CF + RFM independence posture).
    # ``fit_retention`` takes no ``bgnbd_model_card`` argument. No
    # parquet artifact (the curves dict is JSON-shaped and lives in
    # cohort_diagnostics directly).
    #
    # Per DS T2 verdict §I, Beauty (~259 days / ~8-9 first-purchase
    # months) is expected to land PROVISIONAL (below MATURE 12-cohort
    # VALIDATED floor; clears the 6-cohort PROVISIONAL relaxation floor).
    # Renderer does NOT consume; briefing.html byte-identical for all 5
    # fixtures (grep src/render_* pin holds — empty).
    "ENGINE_V2_ML_RETENTION": os.getenv(
        "ENGINE_V2_ML_RETENTION", "true"
    ).lower() == "true",
    # Sprint 13 Ticket T1 — ranking-strategy fallback-chain consumer flag.
    # Default OFF at S13-T1 (module + AudienceIntent enum + positive-control
    # synthetic only; no orchestration wire-up). T2 wires
    # ``rank_audience`` into the audience-builder consumer side; T1.5 will
    # flip the default to ``true`` atomically with the consumer wiring per
    # the S10/S11/S12 atomic-flip-with-content-pin precedent (Sprint 2
    # Risk #4 discipline).
    #
    # The module reads ``EngineRun.predictive_models[<substrate>].fit_status``
    # for BG/NBD, CF, survival, RFM and walks an intent-conditional fallback
    # chain (DS-LOCKED, S13 plan review §D.1). PROVISIONAL never falls
    # through to a downstream VALIDATED. The "recency" non-ML floor is the
    # always-selectable last-resort terminal. RetentionCard is NOT in the
    # chain (retention is cohort_diagnostic, not a ranker).
    "ENGINE_V2_RANKING_STRATEGY_CHAIN": os.getenv(
        "ENGINE_V2_RANKING_STRATEGY_CHAIN", "true"
    ).lower() == "true",
    # Sprint 13 Ticket T2 — PlayCard predicted_segment + model_card_ref
    # consumer wiring flag. S13-T2 introduced the substrate flag-OFF
    # (consumer code lands but no PlayCard is mutated at runtime). S13-T2.5
    # (2026-05-29) atomically flipped the default ON (first intentional
    # engine_run.json re-pin in S13; per-fixture sha changes recorded in
    # ``tests/fixtures/pinned_sha_ledger.json``). When ON, the post-
    # injection consumer-wiring pass at src/main.py (after
    # apply_guardrails_to_injected) walks engine_run.recommendations and
    # populates PlayCard.predicted_segment + PlayCard.model_card_ref from
    # ``rank_audience()`` (T1 module) + the RFM parquet's modal segment.
    # ML-fit ReasonCodes emit ONLY on ``model_card_ref.fit_warnings``
    # (Q-S13-4 LOCK; never on RejectedPlay.reason_code). Modal-segment
    # stability floor (DS §D.4): segment_name = None when n_audience<50
    # OR audience_modal_share<0.30. briefing.html stays byte-identical at
    # the T2.5 flip (renderer non-consumption pinned via grep test in
    # ``tests/test_s13_renderer_non_consumption.py``); only
    # engine_run.json shas change, confined to the PlayCard.predicted_
    # segment + PlayCard.model_card_ref keys.
    "ENGINE_V2_PLAY_PREDICTED_SEGMENT": os.getenv(
        "ENGINE_V2_PLAY_PREDICTED_SEGMENT", "true"
    ).lower() == "true",
    # Sprint 13 Ticket T3 — month_2_delta typed slot + lineage-keyed
    # detection (Pivot 8 month-2-return substrate-state-delta). FLAG-OFF
    # at T3 (impl + tests + isolated module only; no engine_run.json
    # change at default-OFF). T3.5 owns the atomic flip + rollback
    # contract + pinned_sha_ledger re-pin per the S10-T1.5 /
    # S10-T2.5 / S11-T1.5 / S11-T2.5 / S12-T1.5 / S12-T2.5 / S13-T1.5 /
    # S13-T2.5 cadence. When ON: ``src.predictive.month_2_delta.
    # detect_month_2_delta`` runs after the T2 consumer-wiring pass and
    # populates ``EngineRun.month_2_delta`` with a typed ``MonthDelta``
    # carrying substrate_fit_status_changes, segment_shifts (lineage-
    # gated per DS §D.2), and retention_ci_at_month_3_delta. 21-day
    # floor enforced (DS §D.2 LOCKED). Lineage-change suppresses
    # segment_shifts to None with the typed note
    # ``"lineage_changed_segment_shift_incomparable"``. Substrate fit-
    # status changes and retention CI delta remain comparable across
    # lineage bumps. month-2-return for cold-start preserved through the
    # EB path (``n_observed`` shift in ``bayesian_blend``), NOT through
    # ML refit (ML refusal degrades silently within audience ranking).
    # S13-T3.5 (2026-05-29): atomic flip from default "false" → "true".
    # Second intentional engine_run.json schema change in S13 (T2.5 was
    # first with predicted_segment + model_card_ref). The month_2_delta
    # typed slot now populates by default whenever a prior engine_run
    # exists at data/<store_id>/runs/ AND ≥ 21 days have elapsed since
    # the prior anchor_date (DS §D.2 LOCKED 21-day floor). briefing.html
    # byte-identity is preserved structurally — src/briefing.py does not
    # reference ``month_2_delta`` (renderer non-consumption grep pin
    # extended at T3 in tests/test_s13_renderer_non_consumption.py).
    "ENGINE_V2_MONTH_2_DELTA": os.getenv(
        "ENGINE_V2_MONTH_2_DELTA", "true"
    ).lower() == "true",
    # Sprint 6 Ticket T3 — replenishment_due audience builder flag.
    # Default OFF at T3 (impl + tests only; no merchant-facing change).
    # T3.5 (separate ticket) will flip the default to ``true`` atomically
    # with the Beauty pinned-slate + supplements G-1 fixture re-pin per
    # Sprint 2 Risk #4 discipline.
    "ENGINE_V2_BUILDER_REPLENISHMENT_DUE": os.getenv(
        "ENGINE_V2_BUILDER_REPLENISHMENT_DUE", "false"
    ).lower() == "true",
    # Sprint 7 Ticket T2 — cohort_journey_first_to_second audience builder
    # flag. Default OFF at S7-T2 (impl + tests only; no merchant-facing
    # change). S7-T2.5 (separate ticket) will flip the default to ``true``
    # atomically with the Beauty pinned-slate + supplements G-1 fixture
    # re-pin per Sprint 2 Risk #4 discipline.
    #
    # The builder anchors on the validated_external
    # first_to_second_purchase.base_rate prior (wildcard vertical) — the
    # only S7 builder that reuses an existing validated prior without a
    # new research memo (IM plan Section 2). Retires the Phase 5.6
    # first_to_second_purchase directional proxy when flipped (S7-T2.5).
    "ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND": os.getenv(
        "ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND", "true"
    ).lower() == "true",
    # Sprint 7 Ticket T1 — discount_dependency_hygiene audience builder
    # flag. Default OFF at S7-T1 (impl + tests only; no merchant-facing
    # change). S7-T1.5 (separate ticket) will flip the default to
    # ``true`` atomically with the Beauty pinned-slate + supplements G-1
    # + 3 M0 goldens fixture re-pin per Sprint 2 Risk #4 discipline.
    #
    # The builder anchors on the validated_external Beauty-only
    # ``discount_dependency_hygiene.base_rate.beauty`` prior (DS-validated
    # 2026-05-20; Klaviyo H&B 2026 omnichannel benchmark; KI-NEW-K
    # envelope re-fit deferred to Sprint 8). Beauty-only activation by
    # design — supplements rejects per DS Memo-4 verdict (no priors
    # block, no gate_calibration cell). Legacy ``discount_hygiene``
    # play_id stays untouched in play_registry.PLAYS for the M2
    # measured-margin pathway (KI-21 Recommended Experiment allowlist).
    # S7-T1.5 (2026-05-21): default flipped OFF -> ON. DS verdict (c) —
    # heavy-promo conditional bump stays DORMANT (base grid 40/100/250/750
    # beauty + 1.5x mixed_beauty only; ``commerce_posture.discount_fraction``
    # intentionally absent, T18 pins the absence). Supplements stays
    # Path-D dormant (no priors block, no gate_calibration cell per Memo-4
    # REJECT) — supplements fixture MUST stay byte-identical under this
    # flip. Beauty fixture re-pins atomically in this commit
    # (Sprint 2 Risk #4 discipline). Activation moment: Beauty
    # ``discount_dependency_hygiene`` posts to Recommended Now under the
    # Memo-1 validated_external prior (pseudo_n=30).
    "ENGINE_V2_BUILDER_DISCOUNT_HYGIENE": os.getenv(
        "ENGINE_V2_BUILDER_DISCOUNT_HYGIENE", "true"
    ).lower() == "true",
    # Sprint 7 Ticket T3 — aov_lift_via_threshold_bundle audience builder
    # flag. Default OFF at S7-T3 (impl + tests only; no merchant-facing
    # change). S7-T3.5 (separate ticket) will flip the default to ``true``
    # atomically with the Beauty pinned-slate + supplements G-1 + 3 M0
    # goldens fixture re-pin per Sprint 2 Risk #4 discipline.
    #
    # The builder anchors on the dual-tier
    # ``aov_lift_via_threshold_bundle.base_rate`` prior (S7 priors-wiring,
    # validated by DS 2026-05-20): Beauty validated_external Memo 2
    # (pseudo_n=30); supplements elicited_expert Memo 3 DOWNGRADED per
    # DS verdict + KI-NEW-J cross-vertical evidence laundering safeguard
    # (pseudo_n=10, brand's own data dominates within ~20 observed
    # conversions). Both verticals activate as Recommended Now under the
    # blend-permitted contract; supplements floor falls back to
    # ``_default_by_stage`` (no per-play supplements cell per D-FLOOR).
    # The legacy ``bestseller_amplify`` play is operationally distinct
    # (static pre-purchase bundle; M2 measured-margin pathway via
    # Recommended Experiment allowlist) and preserved untouched.
    # S7-T3.5 (2026-05-21): default flipped OFF -> ON. Atomic with
    # Beauty + supplements pinned slate re-pin (Sprint 2 Risk #4
    # discipline). Activation moment: aov_lift_via_threshold_bundle
    # surfaces END-TO-END on BOTH verticals' synthetic fixtures.
    # Beauty anchors on Memo-2 validated_external prior (pseudo_n=30);
    # supplements anchors on Memo-3 elicited_expert DOWNGRADED prior
    # (pseudo_n=10, alpha=0.095, beta=9.905) per DS verdict + KI-NEW-J
    # cross-vertical evidence laundering safeguard. Supplements is the
    # FIRST non-ABSTAIN-only Recommended Now play to ship for the
    # supplements vertical (its fixture re-pins). M0 goldens
    # byte-identical (their cohort sizing does not trigger the builder).
    "ENGINE_V2_BUILDER_AOV_BUNDLE": os.getenv(
        "ENGINE_V2_BUILDER_AOV_BUNDLE", "true"
    ).lower() == "true",
    # Sprint 6.5 Ticket T1 — Store Profile layer flag (default OFF).
    # When ON, ``src.main.run`` calls ``src.profile.build_store_profile``
    # under the V2 decide branch and attaches the typed ``StoreProfile``
    # to ``EngineRun.store_profile``. T1 ships detection only; no
    # downstream gate consumes the profile until T4 wires consumers.
    # The flag default flips to ON in T5 atomic with Beauty + supplements
    # fixture re-pin (Sprint 2 Risk #4 discipline).
    # S6.5-T5 (2026-05-18): default flipped OFF -> ON. Atomic with Beauty
    # pinned slate re-pin + supplements G-1 sha re-affirm in the same
    # commit (Sprint 2 Risk #4 discipline). Activation moment: the
    # Klaviyo validated_external Beauty winback prior anchors a
    # posterior on the synthetic Beauty fixture for the FIRST TIME.
    "ENGINE_V2_STORE_PROFILE": os.getenv(
        "ENGINE_V2_STORE_PROFILE", "true"
    ).lower() == "true",
    # Sprint 7 Ticket T4 — 4-state ABSTAIN_SOFT mode migration. When ON,
    # ``_compute_abstain_mode`` applies the DS-locked Gap F majority-with-
    # tiebreak precedence over four modes (SOFT_AWAITING_MEASUREMENT,
    # SOFT_PRIOR_UNVALIDATED, SOFT_BELOW_FLOOR, SOFT_AUDIENCE_TOO_SMALL)
    # with the TARGETING_HELD_UNDER_ABSTAIN self-contamination guard
    # excluded from the count. When OFF, the legacy S7.5-T3 2-state
    # mapping (SOFT_AWAITING_MEASUREMENT + SOFT_PRIOR_UNVALIDATED) is
    # preserved. Mode is contract surface, not renderer surface (per
    # D-S6.5-20 Stop-Coding adjacency), so the flip is pure-contract and
    # all 5 pinned fixtures stay byte-identical under flag-ON.
    # S7-T4.5 (2026-05-21): default flipped OFF -> ON atomically.
    "ENGINE_V2_ABSTAIN_4STATE": os.getenv(
        "ENGINE_V2_ABSTAIN_4STATE", "true"
    ).lower() == "true",
    # S7.6-T7 — B-5 aov_lift_via_threshold_bundle threshold-from-data
    # primary + supplements re-disable, per ARCHITECTURE_PLAN.md:248-257
    # (founder Path A, 2026-05-21). When ON, the builder:
    #   - Returns empty with reason ``vertical_excluded_per_b5_248`` when
    #     ``VERTICAL_MODE == "supplements"`` (reverts S7-T3.5 supplements
    #     activation; supplements is unconditionally excluded from B-5).
    #   - Computes threshold from L90 P60 of net_sales when L90 order
    #     count >= 200 (stable percentile, plan B-5:254); falls back to
    #     ``cfg["AOV_BUNDLE_THRESHOLD_USD"]``; refuses ``data_missing``
    #     when neither resolves.
    #   - Emits ``threshold_source`` provenance on the AudienceResult
    #     (``l90_p60_data_derived`` | ``cfg_merchant_declared`` |
    #     ``vertical_excluded`` | ``data_missing``).
    # When OFF, preserves S7-T3.5 behavior verbatim (cfg-only resolution,
    # no vertical gate). The default flips to ON in S7.6-T7.5 atomic with
    # Beauty + Supplements fixture re-pin (Sprint 2 Risk #4 discipline).
    "ENGINE_V2_AOV_THRESHOLD_FROM_DATA": os.getenv(
        "ENGINE_V2_AOV_THRESHOLD_FROM_DATA", "true"
    ).lower() == "true",
    # M9 outcome-log writer flag. Default ON because writes are local,
    # deterministic, and gitignored (``data/recommended_history.json``).
    # The writer never raises: on a missing file it creates one; on a
    # malformed file it moves the broken copy aside as
    # ``.corrupt-<ts>.bak`` and starts fresh; on permission/IO errors it
    # reports through a status dict but never breaks the briefing run.
    # Set ``OUTCOME_LOG_ENABLED=false`` to fully disable. Override the
    # path with ``OUTCOME_LOG_PATH`` (e.g., for tests).
    "OUTCOME_LOG_ENABLED": os.getenv("OUTCOME_LOG_ENABLED", "true").lower() == "true",
    "OUTCOME_LOG_PATH": os.getenv("OUTCOME_LOG_PATH", ""),
    "GROSS_MARGIN": 0.70,
    "EFFORT_BUDGET": 8,
    # adaptive window policy
    "WINDOW_POLICY": "auto",            # auto|l7|l28|l56|l90
    "L7_MIN_ORDERS": 150,
    "L28_MIN_ORDERS": 250,
    "L56_MIN_ORDERS": 350,
    "L90_MIN_ORDERS": 400,
    "ENABLE_MULTIWINDOW_SCORING": True,  # enable multi-window analysis
    # Force single-window analysis path even when multi-window data is available.
    # Default False = current behavior. Exposed as an explicit cfg key in M0 so
    # M4 (decision-logic surgery) has a clean handle; do not flip without a
    # decision-logic ticket explicitly authorizing it.
    "_FORCE_SINGLE_WINDOW": False,
    # enhanced statistical methods
    "ENABLE_ENHANCED_STATISTICS": True,   # replace template assumptions with real data analysis
    "MIN_SAMPLE_SIZE_FREQUENCY": 20,      # minimum sample for frequency analysis
    "MIN_SAMPLE_SIZE_RETENTION": 15,      # minimum sample for retention analysis
    "MIN_SAMPLE_SIZE_JOURNEY": 15,        # minimum sample for journey analysis
    "MIN_SAMPLE_SIZE_AOV": 4,             # minimum sample for AOV momentum analysis
    "STATISTICAL_SIGNIFICANCE_THRESHOLD": 0.1,  # p-value threshold for statistical significance
    # pilot knobs
    "PILOT_AUDIENCE_FRACTION": 0.3,
    "PILOT_BUDGET_CAP": 150.0,
    # seasonality knobs
    "SEASONAL_ADJUST": True,
    "SEASONAL_PERIOD": 7,
    # display/vertical knobs (read also via os.getenv in components)
    "VERTICAL_MODE": "mixed",     # beauty|supplements|mixed
    "SUBVERTICAL": "general",     # Optional: fitness|wellness|skincare|haircare|makeup|general (affects seasonality only)
    "CHARTS_MODE": "detailed",    # detailed|compact
    "SHOW_L7": True,               # show L7 KPI card
    # confidence selection mode for actions: conservative|aggressive|learning
    "CONFIDENCE_MODE": "learning",
    # interactions (env-driven). Example formats:
    #  - JSON: {"discount_hygiene->winback_21_45":0.9, "winback_21_45->dormant_multibuyers_60_120":0.92}
    #  - CSV:  discount_hygiene->winback_21_45:0.9, bestseller_amplify->winback_21_45:0.95
    "INTERACTION_FACTORS": "",
    # Channel caps & conflicts for concierge MVP (parsed in engine)
    "CHANNEL_CAPS": {"email": 2, "sms": 1},
    "CONFLICT_PAIRS": ["discount_hygiene->winback_21_45", "winback_21_45->discount_hygiene"],
    # Overlap demotion thresholds
    "OVERLAP_MAX_RATIO": 0.6,
    "MIN_UNIQUE_AUDIENCE": 400,
    # Inventory knobs
    "INVENTORY_ENFORCEMENT_MODE": "soft",   # soft|hard
    "INVENTORY_MAX_AGE_DAYS": 7,
    "INVENTORY_SAFETY_STOCK": 0,
    "INVENTORY_LEAD_TIME_DAYS": 14,
    "INVENTORY_SAFETY_Z": 1.64,            # ~90% service level
    # JSON/CSV map: {"subscription_nudge":60,"default":21}
    "INVENTORY_MIN_COVER_DAYS_MAP": "",
    "INVENTORY_ALLOW_BACKORDER": True,
    # Concierge mode flags (informational by default)
    "CONCIERGE_MODE": True,
    "MANUAL_VALIDATION_THRESHOLD": 5,
    "CUSTOMER_FEEDBACK_REQUIRED": True,
    "VALIDATION_ALERT_CRITICAL": True,
    # Feature flags (Phase 1 shims)
    "FEATURES_DYNAMIC_PRODUCTS": False,
    # Product normalization (base + size parsing)
    "FEATURES_PRODUCT_NORMALIZATION": False,
    # Confidence calibration parameters
    "N_SCALE": 100,                    # Sample size scaling factor (100=store-wide, 50=SKU-level)
    "EFFECT_BOOST_FACTOR": 0.3,        # Gentle boost for larger positive effects (0.0-1.0)
    # Materiality threshold (% of monthly revenue for action to be material)
    "MATERIALITY_PCT": 0.025,          # Research recommends 2.5% (was hardcoded 4.5%)
}


def normalize_product_name(name: str) -> tuple[str, str]:
    """Return (base_product, size_token) from a product title.

    Examples:
      "Vitamin C Serum 30ml" -> ("vitamin c serum", "30ml")
      "Protein Powder (5 lb)" -> ("protein powder", "5lb")
      "Omega-3 90 ct" -> ("omega-3", "90ct")
    """
    if not isinstance(name, str):
        return ("", "")
    s = name.strip().lower()
    # Remove brackets content that often carries size
    import re
    paren = re.findall(r"\(([^)]+)\)", s)
    size = ""
    # Common size patterns
    patterns = [
        r"\b(\d+\s?ml)\b",
        r"\b(\d+(?:\.\d+)?\s?oz)\b",
        r"\b(\d+\s?lb)s?\b",
        r"\b(\d+\s?g)\b",
        r"\b(\d+\s?kg)\b",
        r"\b(\d+\s?ct)\b",
        r"\b(\d+\s?(?:pack|pk))\b",
        r"\b(\d+\s?(?:day|month))\b",
        r"\b((?:1|1\.7|3\.4)\s?oz)\b",  # common beauty sizes
    ]
    # Check parentheses first
    for p in paren:
        ps = p.strip()
        for pat in patterns:
            m = re.search(pat, ps)
            if m:
                size = m.group(1).replace(" ", "")
                break
        if size:
            break
    # If no size found, scan full string
    if not size:
        for pat in patterns:
            m = re.search(pat, s)
            if m:
                size = m.group(1).replace(" ", "")
                break
    # Remove size token from base
    base = s
    if size:
        base = base.replace(size, "")
    # Remove parentheses and extra spaces/punctuation around sizes
    base = re.sub(r"\([^)]*\)", " ", base)
    base = re.sub(r"\s+", " ", base).strip()
    return (base, size)


def _parse_bool(v: str) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def _coerce(k: str, v: str) -> Any:
    # Strip inline comments and quotes
    if isinstance(v, str):
        v = v.split('#', 1)[0].strip().strip('"').strip("'")

    if k in {"MIN_N_WINBACK", "MIN_N_SKU", "EFFORT_BUDGET", "L7_MIN_ORDERS", "L28_MIN_ORDERS", "L56_MIN_ORDERS", "L90_MIN_ORDERS", "MANUAL_VALIDATION_THRESHOLD", "MIN_UNIQUE_AUDIENCE", "MIN_SAMPLE_SIZE_FREQUENCY", "MIN_SAMPLE_SIZE_RETENTION", "MIN_SAMPLE_SIZE_JOURNEY", "MIN_SAMPLE_SIZE_AOV", "OBSERVED_MIN_ELIGIBILITY_N"}:
        return int(float(v))
    if k in {"AOV_EFFECT_FLOOR", "REPEAT_PTS_FLOOR", "DISCOUNT_PTS_FLOOR", "FDR_ALPHA", "GROSS_MARGIN",
             "FINANCIAL_FLOOR", "FINANCIAL_FLOOR_FIXED", "PILOT_AUDIENCE_FRACTION", "PILOT_BUDGET_CAP",
             "STATISTICAL_SIGNIFICANCE_THRESHOLD", "N_SCALE", "EFFECT_BOOST_FACTOR", "MATERIALITY_PCT", "OVERLAP_MAX_RATIO"}:
        return float(v)
    if k in {"SEASONAL_ADJUST", "SHOW_L7", "INVENTORY_ALLOW_BACKORDER", "CONCIERGE_MODE", "CUSTOMER_FEEDBACK_REQUIRED", "VALIDATION_ALERT_CRITICAL", "ENABLE_MULTIWINDOW_SCORING", "ENABLE_REPEAT_RATE_BIAS_CORRECTION", "ENABLE_COHORT_POOLING", "ENABLE_ENHANCED_STATISTICS", "_FORCE_SINGLE_WINDOW", "STATS_NAN_FOR_HARDCODED", "EVIDENCE_CLASS_ENFORCED", "INVENTORY_GATE_ENABLED", "ANOMALY_GATE_ENABLED", "CANNIBALIZATION_GATE_ENABLED", "MATERIALITY_FLOOR_SCALE_AWARE", "RECENTLY_RUN_FATIGUE_ENABLED", "ENGINE_V2_SIZING", "ENGINE_V2_DECIDE", "ENGINE_V2_OUTPUT", "ENGINE_V2_SLATE", "ENGINE_V2_PRIORS_VALIDATION", "ENGINE_V2_BUILDER_WINBACK_DORMANT", "ENGINE_V2_OBSERVED_EFFECT_WINBACK", "ENGINE_V2_OBSERVED_EFFECT_REPLENISHMENT", "ENGINE_V2_OBSERVED_EFFECT_DISCOUNT_HYGIENE", "ENGINE_V2_OBSERVED_EFFECT_JOURNEY", "ENGINE_V2_OBSERVED_EFFECT_AOV_BUNDLE", "ENGINE_V2_OBSERVED_ELIGIBILITY_GATE", "ENGINE_V2_BUILDER_REPLENISHMENT_DUE", "ENGINE_V2_BUILDER_JOURNEY_FIRST_TO_SECOND", "ENGINE_V2_BUILDER_DISCOUNT_HYGIENE", "ENGINE_V2_BUILDER_AOV_BUNDLE", "ENGINE_V2_STORE_PROFILE", "ENGINE_V2_ABSTAIN_4STATE", "ENGINE_V2_AOV_THRESHOLD_FROM_DATA", "ENGINE_V2_TIER_CHIP", "ENGINE_V2_SENSITIVITY", "ENGINE_V2_EB_BLEND", "ENGINE_V2_PLAY_LIBRARY_WAVE1", "ENGINE_V2_ML_BGNBD", "ENGINE_V2_ML_GAMMA_GAMMA", "ENGINE_V2_ML_SURVIVAL", "ENGINE_V2_ML_CF", "ENGINE_V2_ML_RFM", "ENGINE_V2_ML_RETENTION", "ENGINE_V2_RANKING_STRATEGY_CHAIN", "ENGINE_V2_PLAY_PREDICTED_SEGMENT", "ENGINE_V2_MONTH_2_DELTA", "OUTCOME_LOG_ENABLED", "INCLUDE_DEBUG_FIELDS"}:
        return _parse_bool(v)
    if k in {"WINDOW_POLICY", "FINANCIAL_FLOOR_MODE", "CHARTS_MODE", "VERTICAL_MODE",
             "INVENTORY_ENFORCEMENT_MODE", "CONFIDENCE_MODE"}:
        return str(v).strip().lower()
    return v


def get_config(env_path: str | None = None) -> Dict[str, Any]:
    """
    Load defaults and override with .env if present.
    .env format: KEY=VALUE per line; ignores comments and blanks.
    """
    cfg = dict(DEFAULTS)
    # Resolve .env path
    env_file = env_path or str(Path(".env"))
    if Path(env_file).exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                t = line.strip()
                if not t or t.startswith("#") or "=" not in t:
                    continue
                k, v = t.split("=", 1)
                k, v = k.strip(), v.strip()
                if k in DEFAULTS:
                    cfg[k] = _coerce(k, v)

    # Allow environment variables to override (useful for containers)
    for k in DEFAULTS.keys():
        if k in os.environ:
            cfg[k] = _coerce(k, os.environ[k])

    # Attach vertical mode + config
    if not cfg.get('VERTICAL_MODE'):
        cfg['VERTICAL_MODE'] = get_vertical_mode()
    cfg['VERTICAL'] = get_vertical(cfg)
    # Parse interaction factors into structured mapping
    cfg['INTERACTION_FACTORS_PARSED'] = parse_interaction_factors(cfg.get('INTERACTION_FACTORS', ''))
    # Parse inventory cover days map
    cfg['INVENTORY_MIN_COVER_DAYS'] = parse_cover_days_map(cfg.get('INVENTORY_MIN_COVER_DAYS_MAP', ''))
    return cfg


def parse_interaction_factors(value: str | dict | None) -> dict[tuple[str, str], float]:
    """Parse campaign interaction dampening factors from env or dict.
    Accepts:
      - JSON string: {"a->b":0.9, "c->d":0.95} or nested {"a":{"b":0.9}}
      - CSV string:  "a->b:0.9, c->d:0.95"
      - Dict already parsed
    Returns dict with keys (prior, current) -> factor (float in (0,1]).
    """
    out: dict[tuple[str, str], float] = {}
    if not value:
        return out
    try:
        if isinstance(value, dict):
            items = []
            # nested dict case
            for k, v in value.items():
                if isinstance(v, dict):
                    for k2, f in v.items():
                        items.append((str(k), str(k2), float(f)))
                else:
                    # flat key like "a->b"
                    prior, curr = str(k).split("->", 1)
                    items.append((prior.strip(), curr.strip(), float(v)))
            for prior, curr, f in items:
                if f <= 0 or f > 1: continue
                out[(prior, curr)] = float(f)
            return out
        # Try JSON
        import json as _json
        try:
            parsed = _json.loads(str(value))
            return parse_interaction_factors(parsed)
        except Exception:
            pass
        # Fallback: CSV style "a->b:0.9, c->d:0.95"
        s = str(value)
        for part in s.split(','):
            t = part.strip()
            if not t:
                continue
            if ':' not in t or '->' not in t:
                continue
            left, f = t.split(':', 1)
            prior, curr = left.split('->', 1)
            try:
                factor = float(f.strip())
            except Exception:
                continue
            if factor <= 0 or factor > 1:
                continue
            out[(prior.strip(), curr.strip())] = factor
    except Exception:
        return {}
    return out

def get_interaction_factors(cfg: dict) -> dict[tuple[str, str], float]:
    """Return parsed interaction mapping, falling back to a conservative default matrix."""
    parsed = cfg.get('INTERACTION_FACTORS_PARSED') or {}
    if parsed:
        return parsed
    # Defaults used if no env provided
    return {
        ("discount_hygiene", "winback_21_45"): 0.90,
        ("discount_hygiene", "bestseller_amplify"): 0.95,
        ("discount_hygiene", "subscription_nudge"): 0.95,
        ("winback_21_45", "dormant_multibuyers_60_120"): 0.92,
        ("bestseller_amplify", "winback_21_45"): 0.95,
    }

def parse_cover_days_map(value: str | dict | None) -> dict[str, int]:
    """Parse per-play minimum cover days mapping from JSON/CSV or dict.
    Returns dict like {"subscription_nudge": 60, "default": 21}.
    """
    out: dict[str, int] = {}
    if not value:
        return out
    try:
        if isinstance(value, dict):
            for k, v in value.items():
                try:
                    out[str(k)] = int(float(v))
                except Exception:
                    continue
            return out
        import json as _json
        try:
            parsed = _json.loads(str(value))
            return parse_cover_days_map(parsed)
        except Exception:
            pass
        # CSV form: key:val, key:val
        s = str(value)
        for part in s.split(','):
            t = part.strip()
            if not t or ':' not in t:
                continue
            k, v = t.split(':', 1)
            try:
                out[k.strip()] = int(float(v.strip()))
            except Exception:
                continue
    except Exception:
        return {}
    return out


def safe_make_dirs(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def _json_sanitize_nonfinite(obj: Any) -> Any:
    """Recursively replace non-finite floats (NaN / +Inf / -Inf) with None.

    Python's ``json.dump`` defaults to ``allow_nan=True`` and emits the bare
    tokens ``NaN`` / ``Infinity`` / ``-Infinity`` — which are NOT valid JSON and
    make downstream ``JSON.parse`` (the Node API's ``readJson``) throw
    ``Unexpected token 'N' ... is not valid JSON``. Rate/ratio fields legitimately
    come out NaN on sparse stores (empty denominators), so we map them to JSON
    ``null`` (which JS parses as ``null``) rather than crash. NumPy float NaN is
    caught by ``math.isnan`` after the ``float`` cast in the isinstance check.
    """
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _json_sanitize_nonfinite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_sanitize_nonfinite(v) for v in obj]
    return obj


def write_json(path: str, payload: Dict[str, Any]) -> None:
    """Write JSON with safe defaults for Pandas/NumPy types.
    - Falls back to str() for objects like pd.Timestamp, Path, etc.
    - Non-finite floats (NaN/Inf) are converted to null (valid JSON).
    - Keeps indentation for readability.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    safe_payload = _json_sanitize_nonfinite(payload)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(safe_payload, f, indent=2, default=str, allow_nan=False)

# ---------------- Identity helpers (Phase 0 observability) ---------------- #
def standardize_order_key(df: pd.DataFrame) -> pd.Series:
    """Return a robust order key Series mapped to 'Name' semantics.
    Priority: 'Name' -> 'order_id' -> 'Order ID' -> index as string.
    Does not mutate input; safe for logging/coverage only.
    """
    if df is None or df.empty:
        return pd.Series([], dtype=str)
    cols = {str(c).strip().lower(): c for c in df.columns}
    if 'name' in cols:
        return df[cols['name']].astype(str)
    for k in ('order_id', 'order id', 'order number'):
        if k in cols:
            return df[cols[k]].astype(str)
    return pd.Series(df.index.astype(str), index=df.index)

def standardize_customer_key(df: pd.DataFrame) -> pd.Series:
    """Return a robust customer key Series used for customer-level metrics.
    Priority: email (lowercased, stripped; supports aliases) -> explicit customer_id -> fallback name|province.
    """
    if df is None or df.empty:
        return pd.Series([], dtype=str)
    idx = df.index
    # Accept common aliases for email: 'Customer Email' | 'customer_email' | 'email'
    email_series = None
    for cand in ['Customer Email', 'customer_email', 'email']:
        if cand in df.columns:
            email_series = df[cand]
            break
    em = email_series.astype(str).str.strip().str.lower() if email_series is not None else pd.Series(np.nan, index=idx)
    em = em.replace({'': np.nan})
    cid = df['customer_id'].astype(str).str.strip().str.lower() if 'customer_id' in df.columns else pd.Series(np.nan, index=idx)
    cid = cid.replace({'': np.nan})
    name = df['Billing Name'].astype(str).str.strip().str.lower() if 'Billing Name' in df.columns else pd.Series('', index=idx)
    prov = df['Shipping Province'].astype(str).str.strip().str.lower() if 'Shipping Province' in df.columns else pd.Series('', index=idx)
    combined = name.fillna('') + '|' + prov.fillna('')
    fallback = combined.replace({'|': np.nan}).infer_objects(copy=False)
    key = em.where(em.notna(), cid.where(cid.notna(), fallback))
    return key

def identity_coverage(df: pd.DataFrame) -> dict:
    """Basic coverage indicators for identities and product presence.
    Returns: {customer_key_coverage: float, order_key_coverage: float}
    """
    if df is None or df.empty:
        return {"customer_key_coverage": 0.0, "order_key_coverage": 0.0}
    ck = standardize_customer_key(df)
    ok = standardize_order_key(df)
    ck_cov = float((ck.notna() & (ck.astype(str).str.strip() != '')).mean()) if len(ck) else 0.0
    ok_cov = float((ok.notna() & (ok.astype(str).str.strip() != '')).mean()) if len(ok) else 0.0
    return {"customer_key_coverage": ck_cov, "order_key_coverage": ok_cov}


def read_yaml(path: str) -> dict:
    try:
        import yaml
    except Exception:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return yaml.safe_load(p.read_text()) or {}
    except Exception:
        return {}


def load_category_map(default_dir: Optional[str] = None) -> dict[str, list[str]]:
    """
    Load token lists per category from templates/category_map.yml.
    Returns {category: [token,...]}, all lowercased.
    """
    base = Path(default_dir) if default_dir else Path(__file__).resolve().parent.parent / 'templates'
    yml = base / 'category_map.yml'
    data = read_yaml(str(yml)) if yml.exists() else {}
    out: dict[str, list[str]] = {}
    for cat, tokens in (data or {}).items():
        try:
            out[str(cat).lower()] = [str(t).lower() for t in (tokens or [])]
        except Exception:
            continue
    return out


def dominant_category_for_order(rows: pd.DataFrame, cat_map: dict[str, list[str]]) -> str:
    """
    Given all line-items (rows) for a single order, choose a dominant category by token match.
    """
    if not cat_map:
        return 'unknown'
    counts: dict[str, int] = {k: 0 for k in cat_map.keys()}
    token_to_cat: list[tuple[str, str]] = []
    for c, toks in cat_map.items():
        for t in toks:
            token_to_cat.append((t, c))
    # compile simple word tokenizer
    word_re = re.compile(r"[A-Za-z]+")
    names = rows.get('Lineitem name') if 'Lineitem name' in rows.columns else None
    if names is None:
        return 'unknown'
    for name in names.astype(str).str.lower().tolist():
        for w in word_re.findall(name):
            for t, c in token_to_cat:
                if t in w:
                    counts[c] = counts.get(c, 0) + 1
    # pick max count category
    best = 'unknown'
    best_ct = 0
    for c, ct in counts.items():
        if ct > best_ct:
            best, best_ct = c, ct
    return best if best_ct > 0 else 'unknown'


def estimate_expected_orders(H: int, p_repeat: float, median_ipi: float) -> float:
    """Simple expected orders over horizon H using repeat probability and median IPI."""
    H = int(max(H, 0))
    p = float(max(min(p_repeat or 0.0, 1.0), 0.0))
    ipi = float(max(median_ipi or 0.0, 1.0))
    return float(p * (H / ipi))


def choose_window(l7_orders: int, l28_orders: int, l56_orders: int = 0, l90_orders: int = 0, policy: str = "auto") -> str:
    """
    Choose analysis window based on volume.
    """
    policy = (policy or "auto").lower()
    if policy == "l7":
        return "L7"
    if policy == "l28":
        return "L28"
    if policy == "l56":
        return "L56"
    if policy == "l90":
        return "L90"
    # auto policy
    l7_min = DEFAULTS["L7_MIN_ORDERS"]
    l28_min = DEFAULTS["L28_MIN_ORDERS"]
    l56_min = DEFAULTS["L56_MIN_ORDERS"]
    l90_min = DEFAULTS["L90_MIN_ORDERS"]
    try:
        l7_min = int(os.getenv("L7_MIN_ORDERS", l7_min))
        l28_min = int(os.getenv("L28_MIN_ORDERS", l28_min))
        l56_min = int(os.getenv("L56_MIN_ORDERS", l56_min))
        l90_min = int(os.getenv("L90_MIN_ORDERS", l90_min))
    except Exception:
        pass
    
    # Progressive fallback: start with shortest window, fall back to longer ones if insufficient data
    if l7_orders >= l7_min:
        return "L7"
    if l28_orders >= l28_min:
        return "L28"
    if l56_orders >= l56_min:
        return "L56"
    if l90_orders >= l90_min:
        return "L90"
    
    # Final fallback: use longest available window
    return "L90"


def get_window_weights(vertical_mode: str = "mixed") -> dict[str, float]:
    """
    Return window weights based on business vertical for multi-window scoring.
    
    Args:
        vertical_mode: 'supplements', 'beauty', or 'mixed'
    
    Returns:
        Dict mapping window names (L7, L28, L56, L90) to weights (sum to 1.0)
    """
    vertical_mode = str(vertical_mode).lower()
    
    if vertical_mode == 'supplements':
        # Supplements: favor longer windows due to 30-90 day repurchase cycles
        # L7 removed - redistributed to L56/L90 (longer cycles)
        return {
            'L7': 0.0,
            'L28': 0.2,
            'L56': 0.5,
            'L90': 0.3
        }
    elif vertical_mode == 'beauty':
        # Beauty: favor L56 window (45-60 day skincare repurchase cycles)
        # L7 removed - L56 gets primary weight for beauty vertical
        return {
            'L7': 0.0,
            'L28': 0.3,
            'L56': 0.6,
            'L90': 0.1
        }
    else:  # mixed or unknown
        # Conservative mixed approach
        # L7 removed - redistributed to L28/L56/L90
        return {
            'L7': 0.0,
            'L28': 0.5,
            'L56': 0.3,
            'L90': 0.2
        }


def get_seasonal_multiplier(anchor_date, vertical_mode: str = "mixed", subvertical: str = "general") -> tuple[float, str]:
    """
    Adjust expectations based on retail calendar periods with vertical-specific adjustments.

    Args:
        anchor_date: Date to check for seasonal period
        vertical_mode: Business vertical ("beauty", "supplements", "mixed")
        subvertical: Optional sub-vertical for more precise seasonality ("fitness", "wellness", "skincare", etc.)

    Returns:
        Tuple of (multiplier, period_name)
    """
    try:
        if isinstance(anchor_date, str):
            anchor_date = pd.Timestamp(anchor_date)
        elif not hasattr(anchor_date, 'month'):
            anchor_date = pd.Timestamp(anchor_date)

        month = anchor_date.month
        day = anchor_date.day

        # Base seasonal periods with default multipliers
        base_multiplier, period = _get_base_seasonal_period(month, day)

        # Check for subvertical override first (most specific)
        subvertical_override = _get_subvertical_seasonal_override(period, subvertical)
        if subvertical_override is not None:
            return subvertical_override, period

        # Fall back to vertical-specific adjustments
        vertical_adjustment = _get_vertical_seasonal_adjustment(period, vertical_mode)

        final_multiplier = base_multiplier * vertical_adjustment

        return final_multiplier, period

    except Exception:
        return 1.0, "normal"


# Sub-vertical specific seasonal overrides
# These are FINAL multipliers (not adjustments) for cases where sub-verticals
# behave very differently from their parent vertical
SUBVERTICAL_SEASONAL_OVERRIDES = {
    'fitness': {
        'january_detox': 1.8,      # New Year resolution spike - fitness is huge
        'spring_reset': 1.5,       # Summer body prep
        'routine_building': 1.3,   # Back to gym season
    },
    'sports_nutrition': {
        'january_detox': 1.8,      # Same as fitness
        'spring_reset': 1.5,
    },
    'wellness': {
        'january_detox': 1.4,      # Health reset but less extreme than fitness
        'spring_reset': 1.3,
    },
    'skincare': {
        'spring_reset': 1.4,       # Skincare refresh season
        'summer_slowdown': 1.1,    # SPF season actually strong
    },
    'haircare': {
        'spring_reset': 1.2,
        'summer_slowdown': 0.9,    # Summer hair damage = treatment season
    },
    'makeup': {
        'BFCM': 1.6,               # Gift-heavy category
        'holiday_season': 1.4,     # Party season
        'summer_slowdown': 0.7,    # Minimal makeup in summer
    },
}


def _get_subvertical_seasonal_override(period: str, subvertical: str) -> float | None:
    """
    Get subvertical-specific seasonal override if one exists.

    Returns None if no override exists (fall back to vertical adjustment).
    """
    if subvertical == "general" or not subvertical:
        return None

    overrides = SUBVERTICAL_SEASONAL_OVERRIDES.get(subvertical, {})
    return overrides.get(period)  # Returns None if period not in overrides


def _get_base_seasonal_period(month: int, day: int) -> tuple[float, str]:
    """Get base seasonal multiplier and period name."""
    # BFCM period (Nov 15 - Dec 5) - Extended window
    if (month == 11 and day >= 15) or (month == 12 and day <= 5):
        return 1.4, "BFCM"
    # Post-BFCM holiday period (Dec 6 - Dec 31) - Gift cards, returns prep
    elif (month == 12 and day >= 6):
        return 1.1, "holiday_season"
    # January detox/returns (Jan 1 - Feb 15) - New Year health focus
    elif (month == 1) or (month == 2 and day <= 15):
        return 0.7, "january_detox"
    # Spring reset (Mar 1 - May 15) - Health & beauty surge
    elif (month == 3) or (month == 4) or (month == 5 and day <= 15):
        return 1.1, "spring_reset"
    # Summer slowdown (Jun 15 - Aug 15) - Vacation period
    elif (month == 6 and day >= 15) or (month == 7) or (month == 8 and day <= 15):
        return 0.8, "summer_slowdown"
    # Back-to-school/routine building (Aug 16 - Sep 30)
    elif (month == 8 and day >= 16) or (month == 9):
        return 1.2, "routine_building"
    # Holiday prep (Oct 1 - Nov 14) - Pre-BFCM anticipation
    elif (month == 10) or (month == 11 and day <= 14):
        return 1.0, "holiday_prep"
    else:
        return 1.0, "normal"


def _get_vertical_seasonal_adjustment(period: str, vertical_mode: str) -> float:
    """Apply vertical-specific adjustments to seasonal periods."""
    
    # Vertical-specific seasonal adjustments
    adjustments = {
        'beauty': {
            'BFCM': 1.1,           # Beauty brands do well during BFCM
            'holiday_season': 1.0,  # Steady holiday gift giving
            'january_detox': 0.9,   # Less affected by detox trends
            'spring_reset': 1.2,    # Strong spring beauty refresh
            'summer_slowdown': 1.0, # Beauty less affected by summer
            'routine_building': 1.1, # Back-to-school skincare routines
            'holiday_prep': 1.0,
            'normal': 1.0
        },
        'supplements': {
            'BFCM': 1.0,           # Less discount-driven
            'holiday_season': 0.8,  # Lower focus on health during holidays
            'january_detox': 1.5,   # Massive New Year health surge  
            'spring_reset': 1.3,    # Spring cleaning/health focus
            'summer_slowdown': 0.9, # Vacation disrupts routines
            'routine_building': 1.2, # Back-to-routine supplement habits
            'holiday_prep': 0.8,    # Pre-holiday focus elsewhere
            'normal': 1.0
        },
        'mixed': {
            'BFCM': 1.0,           # Balanced approach
            'holiday_season': 1.0,  # Balanced holiday performance
            'january_detox': 1.1,   # Moderate health focus
            'spring_reset': 1.1,    # General seasonal uptick
            'summer_slowdown': 1.0, # Mixed results
            'routine_building': 1.0, # Balanced
            'holiday_prep': 1.0,
            'normal': 1.0
        }
    }
    
    return adjustments.get(vertical_mode, adjustments['mixed']).get(period, 1.0)


def detect_customer_cohorts(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Detect customer cohorts based on behavioral characteristics for pooled statistical testing.
    
    Args:
        df: Transaction dataframe with customer data
        
    Returns:
        Dictionary of cohort names to filtered dataframes
    """
    cohorts = {}
    
    try:
        # Ensure required columns exist
        if 'customer_id' not in df.columns or 'net_sales' not in df.columns:
            return {'all': df}
            
        # Calculate customer-level metrics for cohort detection
        customer_metrics = df.groupby('customer_id').agg({
            'net_sales': ['sum', 'count', 'mean'],
            'order_date': ['min', 'max'],
            'discount_amount': 'sum'
        }).reset_index()
        
        # Flatten column names
        customer_metrics.columns = ['customer_id', 'total_spent', 'total_orders', 'avg_order_value', 
                                   'first_order_date', 'last_order_date', 'total_discount']
        
        # Calculate days since first order (tenure)
        anchor_date = df['order_date'].max()
        customer_metrics['days_since_first_order'] = (anchor_date - customer_metrics['first_order_date']).dt.days
        
        # Calculate estimated LTV (simple heuristic)
        customer_metrics['ltv_estimate'] = customer_metrics['total_spent'] * (
            1 + (customer_metrics['total_orders'] - 1) * 0.5
        )
        
        # Define cohorts based on behavioral patterns
        
        # New customers (first order within 30 days)
        new_customers = customer_metrics[customer_metrics['days_since_first_order'] <= 30]['customer_id']
        if len(new_customers) > 0:
            cohorts['new_customers'] = df[df['customer_id'].isin(new_customers)]
            
        # Loyal customers (5+ orders) 
        loyal_customers = customer_metrics[customer_metrics['total_orders'] >= 5]['customer_id']
        if len(loyal_customers) > 0:
            cohorts['loyal_customers'] = df[df['customer_id'].isin(loyal_customers)]
            
        # High-value customers (top 20% by LTV)
        ltv_threshold = customer_metrics['ltv_estimate'].quantile(0.8)
        high_value = customer_metrics[customer_metrics['ltv_estimate'] >= ltv_threshold]['customer_id']
        if len(high_value) > 0:
            cohorts['high_value'] = df[df['customer_id'].isin(high_value)]
            
        # Discount-sensitive customers (high discount usage)
        discount_threshold = customer_metrics['total_discount'].quantile(0.7)
        discount_sensitive = customer_metrics[customer_metrics['total_discount'] >= discount_threshold]['customer_id']
        if len(discount_sensitive) > 0:
            cohorts['discount_sensitive'] = df[df['customer_id'].isin(discount_sensitive)]
            
        # Recent customers (ordered within 60 days)
        recent_threshold = anchor_date - pd.Timedelta(days=60)
        recent_customers = customer_metrics[customer_metrics['last_order_date'] >= recent_threshold]['customer_id']
        if len(recent_customers) > 0:
            cohorts['recent_active'] = df[df['customer_id'].isin(recent_customers)]
            
        # If no meaningful cohorts detected, return entire dataset
        if not cohorts:
            cohorts['all'] = df
            
        return cohorts
        
    except Exception as e:
        # Fallback to entire dataset if cohort detection fails
        return {'all': df}


def pool_cohort_results(cohort_results: dict[str, dict], min_cohort_size: int = 50) -> dict:
    """
    Pool statistical results across customer cohorts for improved significance testing.
    
    Args:
        cohort_results: Dictionary of cohort_name -> statistical results
        min_cohort_size: Minimum cohort size to include in pooling
        
    Returns:
        Pooled statistical results with confidence adjustments
    """
    valid_cohorts = {}
    total_weight = 0.0
    
    # Filter cohorts by minimum size and extract valid results
    for cohort_name, results in cohort_results.items():
        n = results.get('n', 0)
        if n >= min_cohort_size and results.get('effect_abs') is not None:
            # Weight by sample size (larger cohorts get more influence)
            weight = min(n / 1000, 1.0)  # Cap at 1.0 for very large cohorts
            valid_cohorts[cohort_name] = {
                'weight': weight,
                'n': n,
                'effect': results.get('effect_abs', 0.0),
                'p_value': results.get('p', 1.0)
            }
            total_weight += weight
    
    if not valid_cohorts or total_weight == 0:
        return {'effect_abs': 0.0, 'p': 1.0, 'n': 0, 'cohort_count': 0}
    
    # Calculate weighted average effect
    weighted_effect = sum(
        cohort['effect'] * cohort['weight'] for cohort in valid_cohorts.values()
    ) / total_weight
    
    # Pool p-values using Fisher's method (simplified)
    # More sophisticated methods could use Stouffer's Z-score method
    pooled_n = sum(cohort['n'] for cohort in valid_cohorts.values())
    
    # Simple conservative p-value pooling (take maximum to be safe)
    pooled_p = max(cohort['p_value'] for cohort in valid_cohorts.values())
    
    # Apply cohort consistency bonus (if multiple cohorts show similar effects)
    effect_consistency = _calculate_effect_consistency(valid_cohorts)
    consistency_bonus = min(0.2, effect_consistency * 0.1)  # Up to 20% p-value improvement
    
    adjusted_p = max(0.001, pooled_p * (1 - consistency_bonus))
    
    return {
        'effect_abs': weighted_effect,
        'p': adjusted_p,
        'n': pooled_n,
        'cohort_count': len(valid_cohorts),
        'cohort_consistency': effect_consistency,
        'cohorts_used': list(valid_cohorts.keys())
    }


def _calculate_effect_consistency(cohorts: dict) -> float:
    """Calculate how consistent effects are across cohorts (0-1 scale)."""
    if len(cohorts) < 2:
        return 0.0
        
    effects = [cohort['effect'] for cohort in cohorts.values()]
    
    # Calculate coefficient of variation (lower = more consistent)
    mean_effect = sum(effects) / len(effects)
    if mean_effect == 0:
        return 0.0
        
    variance = sum((e - mean_effect) ** 2 for e in effects) / len(effects)
    std_dev = variance ** 0.5
    cv = std_dev / abs(mean_effect)
    
    # Convert to consistency score (1 = perfect consistency, 0 = highly variable)
    consistency = max(0.0, 1.0 - min(cv, 1.0))
    
    return consistency


def financial_floor(l28_net_sales: float, gross_margin: float) -> float:
    """
    Adaptive financial floor ≈ 0.5% of L28 net sales × gross margin, floored at $150.
    """
    mode = str(os.getenv("FINANCIAL_FLOOR_MODE", "auto")).lower()
    if mode == "fixed":
        return float(os.getenv("FINANCIAL_FLOOR_FIXED", DEFAULTS["FINANCIAL_FLOOR"]))
    base = 0.005 * max(l28_net_sales, 0.0) * max(gross_margin, 0.0)
    return max(base, 150.0)

def read_json(path: str) -> dict:
    """
    Safe JSON reader. Returns {} if file doesn't exist or is empty/invalid.
    """
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def winsorize_series(
    s: pd.Series,
    lower_quantile: float = 0.01,
    upper_quantile: float = 0.99,
    skipna: bool = True,
) -> pd.Series:
    """
    Clip a numeric series at given lower/upper quantiles (winsorization).
    Keeps index and name. Non-numeric values are ignored (left as-is if possible).
    """
    # Ensure numeric dtype (coerce errors to NaN)
    s_num = pd.to_numeric(s, errors="coerce")
    q_low = s_num.quantile(lower_quantile, interpolation="linear") if skipna else s_num.quantile(lower_quantile)
    q_hi  = s_num.quantile(upper_quantile, interpolation="linear") if skipna else s_num.quantile(upper_quantile)
    clipped = s_num.clip(lower=q_low, upper=q_hi)
    clipped.name = s.name
    return clipped

def aligned_windows(
    anchor_or_df,
    window_days: int | None = None,
    date_col: str = "Created at",
    multi_windows: tuple[int, ...] = (7, 28, 56, 90),
    anchor_ts: datetime | None = None,
):
    """
    Polymorphic helper:

    1) If first arg is a timestamp-like (pd.Timestamp/datetime/str/np.datetime64), and window_days is not None:
       Returns a 4-tuple: (recent_start, recent_end, prior_start, prior_end)

    2) If first arg is a DataFrame:
       Returns a dict with keys 'anchor', 'L7', 'L28', 'L56' (or whatever in multi_windows),
       where each has 'recent' and 'prior' start/end timestamps.
    """
    # ---- Case 1: timestamp-like input -> single-window tuple ----
    ts_like = (pd.Timestamp, datetime, np.datetime64, str)
    if isinstance(anchor_or_df, ts_like):
        anchor = pd.Timestamp(anchor_or_df)
        w = int(window_days or 7)
        recent_end = anchor.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
        recent_start = anchor.normalize() - pd.Timedelta(days=w - 1)
        prior_end = recent_start - pd.Timedelta(seconds=1)
        prior_start = recent_start - pd.Timedelta(days=w)
        return recent_start, recent_end, prior_start, prior_end

    # ---- Case 2: DataFrame input -> multi-window dict ----
    df = anchor_or_df
    if df is None or getattr(df, "empty", True):
        raise ValueError("aligned_windows: input DataFrame is empty")

    s = pd.to_datetime(df[date_col], errors="coerce").dropna()
    if s.empty:
        raise ValueError(f"aligned_windows: no valid timestamps in column '{date_col}'")

    anchor = pd.Timestamp(anchor_ts) if anchor_ts is not None else s.max()

    out: dict = {"anchor": anchor}
    for w in multi_windows:
        recent_end = anchor.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
        recent_start = anchor.normalize() - pd.Timedelta(days=w - 1)
        prior_end = recent_start - pd.Timedelta(seconds=1)
        prior_start = recent_start - pd.Timedelta(days=w)
        out[f"L{w}"] = {
            "window_days": w,
            "recent": {"start": recent_start, "end": recent_end},
            "prior": {"start": prior_start, "end": prior_end},
        }
    return out

## normalize_aligned removed (engine uses src/action_engine.py:_normalize_aligned)

## kpi_snapshot_nested removed (superseded by kpi_snapshot_with_deltas)

# --- add near other imports ---
from typing import Optional, Tuple
from .stats import welch_t_test, two_proportion_test, benjamini_hochberg

def kpi_snapshot_with_deltas(df: pd.DataFrame, anchor_ts: datetime | None = None,
                             min_identified:int=10, discount_positive_is_bad:bool=True,
                             alpha:float=0.05,
                             seasonally_adjust: bool = False,
                             seasonal_period: int = 7, cfg: dict = None) -> dict:
    """
    Returns nested structure with recent/prior KPIs for L7/L28, deltas and significance.
    
    FIXED: Seasonal adjustments are now stored in metadata, never override actual metrics.
    
    Values:
      aligned["L7"]["net_sales"|"orders"|"aov"|"discount_rate"|
                    "repeat_rate_within_window"|"returning_customer_share"|"new_customer_rate"|
                    "repeat_share" (alias) | "repeat_rate" (alias) | "returning_rate" (alias)]
      aligned["L7"]["prior"][same keys]
      aligned["L7"]["delta"][metric]  -> relative change (e.g., +0.062 = +6.2%)
      aligned["L7"]["p"][metric]      -> p-value where applicable (aov, discount_rate, repeat_share)
      aligned["L7"]["sig"][metric]    -> True if p<=alpha and sample floors OK
      aligned["L7"]["seasonal_expected"] -> Dict with expected values if seasonal adjustment enabled
    Same for "L28".
    """

    if df is None or df.empty:
        return {"anchor": None, "L7": {}, "L28": {}, "L56": {}, "L90": {}}

    d = df.copy()
    d["Created at"] = pd.to_datetime(d["Created at"], errors="coerce")
    d = d.dropna(subset=["Created at"])
    if d.empty:
        return {"anchor": None, "L7": {}, "L28": {}, "L56": {}, "L90": {}}

    # Exclude cancelled/refunded for KPI calc (use raw d for first_seen to avoid censoring)
    d_kpi = d.copy()
    if "Cancelled at" in d_kpi.columns:
        canc = pd.to_datetime(d_kpi["Cancelled at"], errors="coerce")
        d_kpi = d_kpi[canc.isna()]
    if "Financial Status" in d_kpi.columns:
        d_kpi = d_kpi[~d_kpi["Financial Status"].astype(str).str.contains("refunded", case=False, na=False)]

    # brutal money cleaner (same as your robust_read_csv)
    def _money(s: pd.Series | None) -> pd.Series:
        if s is None: return pd.Series(dtype=float)
        raw = s.astype(str)
        neg_mask = raw.str.contains(r"^\s*\(.*\)\s*$", na=False)
        cleaned = raw.str.replace(r"[^\d\.\-]", "", regex=True)
        out = pd.to_numeric(cleaned, errors="coerce")
        out.loc[neg_mask] = -out.loc[neg_mask].abs()
        return out

    def _order_level_net(row: pd.Series) -> Optional[float]:
        # Prefer Subtotal - Total Discount; else Total - Shipping - Taxes; else None
        if pd.notna(row.get("Subtotal", np.nan)):
            sub = float(row["Subtotal"]); disc = float(row.get("Total Discount", 0.0) or 0.0)
            return sub - disc
        if pd.notna(row.get("Total", np.nan)):
            tot = float(row["Total"]); ship = float(row.get("Shipping", 0.0) or 0.0); tax = float(row.get("Taxes", 0.0) or 0.0)
            return tot - ship - tax
        return None

    # Pre-coerce monetary columns once for performance
    for c in ["Subtotal", "Total Discount", "Shipping", "Taxes", "Total", "Lineitem price", "Lineitem discount"]:
        if c in d_kpi.columns: d_kpi[c] = _money(d_kpi[c])

    # Per-order netsales (for AOV distribution)
    d_kpi["_order_net"] = d_kpi.apply(_order_level_net, axis=1)
    # Dedupe orders by Name for order-level calcs
    d_kpi_ord = d_kpi.drop_duplicates(subset=["Name"]) if "Name" in d_kpi.columns else d_kpi.copy()

    def _identity_key(frame: pd.DataFrame) -> pd.Series:
        """Construct a robust customer identity key.
        Priority: Customer Email, then explicit customer_id if present,
        then Billing Name | Shipping Province fallback. Returns a Series aligned to frame.index.
        """
        idx = frame.index
        # email (primary)
        em = frame["Customer Email"].astype(str).str.strip().str.lower() if "Customer Email" in frame.columns else pd.Series(np.nan, index=idx)
        em = em.replace({"": np.nan})
        # explicit customer_id (secondary)
        cid = frame["customer_id"].astype(str).str.strip().str.lower() if "customer_id" in frame.columns else pd.Series(np.nan, index=idx)
        cid = cid.replace({"": np.nan})
        # name/province fallback
        name_s = frame["Billing Name"].astype(str).str.strip().str.lower() if "Billing Name" in frame.columns else pd.Series("", index=idx)
        prov_s = frame["Shipping Province"].astype(str).str.strip().str.lower() if "Shipping Province" in frame.columns else pd.Series("", index=idx)
        fallback = name_s.fillna("") + "|" + prov_s.fillna("")
        # Avoid FutureWarning for silent downcasting; keep types stable
        fallback = fallback.replace({"|": np.nan}).infer_objects(copy=False)
        key = em.where(em.notna(), cid.where(cid.notna(), fallback))
        return key

    # Use the FULL raw df (d) for first_seen so prior history isn't censored by refunds
    all_keys = _identity_key(d)
    first_seen = (
        pd.DataFrame({"key": all_keys, "ts": d["Created at"]})
          .dropna(subset=["key"])
          .groupby("key")["ts"].min()
    )

    anchor = pd.Timestamp(anchor_ts) if anchor_ts is not None else d_kpi_ord["Created at"].max()

        
    def _window(anchor: pd.Timestamp, days:int) -> Tuple[pd.Timestamp,pd.Timestamp,pd.Timestamp,pd.Timestamp]:
        recent_end = anchor.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
        recent_start = recent_end.normalize() - pd.Timedelta(days=days-1)
        prior_end = recent_start - pd.Timedelta(seconds=1)
        prior_start = prior_end.normalize() - pd.Timedelta(days=days-1)
        return recent_start, recent_end, prior_start, prior_end

    def _summarize(days:int) -> dict:
        rs, re, ps, pe = _window(anchor, days)

        rec = d_kpi_ord[(d_kpi_ord["Created at"]>=rs) & (d_kpi_ord["Created at"]<=re)].copy()
        pri = d_kpi_ord[(d_kpi_ord["Created at"]>=ps) & (d_kpi_ord["Created at"]<=pe)].copy()

        # ACTUAL orders - what really happened
        o1_actual = int(rec["Name"].nunique()) if "Name" in rec.columns else int(len(rec))
        o0_actual = int(pri["Name"].nunique()) if "Name" in pri.columns else int(len(pri))

        # Canonical net sales + debug of alternative methods
        def _netsales_debug(frame_orders: pd.DataFrame) -> dict:
            """
            Always use the same canonical method for net sales and record which method was used:
            - Primary: sum of per-order net ("_order_net") which is computed as Subtotal-Discount,
              falling back to Total-Shipping-Taxes at the per-order level.
            - Fallback: line-items aggregation restricted to the same orders/time window.

            Returns a dict with keys: value, method, alt (dict of alternative computations).
            """
            out: dict = {"value": float("nan"), "method": None, "alt": {}}
            # Canonical: per-order net if available
            if "_order_net" in frame_orders.columns and frame_orders["_order_net"].notna().any():
                val = float(frame_orders["_order_net"].dropna().sum())
                out["value"] = val
                out["method"] = "order_net"
            else:
                # Fallback: aggregate line items per order, restricted to the same orders
                val = float("nan")
                if all(c in d_kpi.columns for c in ["Lineitem price", "Lineitem quantity"]):
                    if "Name" in frame_orders.columns and "Name" in d_kpi.columns:
                        order_names = set(frame_orders["Name"].astype(str))
                        li = d_kpi[d_kpi["Name"].astype(str).isin(order_names)].copy()
                    else:
                        # last resort: time-range filter
                        li = d_kpi[(d_kpi["Created at"] >= frame_orders["Created at"].min()) & (d_kpi["Created at"] <= frame_orders["Created at"].max())].copy()
                    li_price = _money(li["Lineitem price"]) if "Lineitem price" in li.columns else pd.Series(dtype=float)
                    li_qty = pd.to_numeric(li["Lineitem quantity"], errors="coerce") if "Lineitem quantity" in li.columns else pd.Series(dtype=float)
                    li_disc = _money(li["Lineitem discount"]) if "Lineitem discount" in li.columns else pd.Series(0.0, index=li.index)
                    li["_line_net"] = (li_price * li_qty) - li_disc
                    if "Name" in li.columns:
                        per_order = li.groupby("Name")["_line_net"].sum()
                        val = float(per_order.dropna().sum())
                    else:
                        val = float(li["_line_net"].dropna().sum())
                out["value"] = val
                out["method"] = "line_items"

            # Alternatives for validation/debug
            try:
                if "Subtotal" in frame_orders.columns:
                    sub = _money(frame_orders["Subtotal"]).sum(skipna=True)
                    disc = _money(frame_orders["Total Discount"]).sum(skipna=True) if "Total Discount" in frame_orders.columns else 0.0
                    out["alt"]["subtotal_minus_discount"] = float(sub - disc)
            except Exception:
                pass
            try:
                if "Total" in frame_orders.columns:
                    tot = _money(frame_orders["Total"]).sum(skipna=True)
                    ship = _money(frame_orders["Shipping"]).sum(skipna=True) if "Shipping" in frame_orders.columns else 0.0
                    tax = _money(frame_orders["Taxes"]).sum(skipna=True) if "Taxes" in frame_orders.columns else 0.0
                    out["alt"]["total_minus_shipping_taxes"] = float(tot - ship - tax)
            except Exception:
                pass
            # Line-items aggregate as explicit alternative if canonical wasn't line_items
            try:
                if out.get("method") != "line_items" and all(c in d_kpi.columns for c in ["Lineitem price", "Lineitem quantity"]):
                    if "Name" in frame_orders.columns and "Name" in d_kpi.columns:
                        order_names = set(frame_orders["Name"].astype(str))
                        li = d_kpi[d_kpi["Name"].astype(str).isin(order_names)].copy()
                    else:
                        li = d_kpi[(d_kpi["Created at"] >= frame_orders["Created at"].min()) & (d_kpi["Created at"] <= frame_orders["Created at"].max())].copy()
                    li_price = _money(li["Lineitem price"]) if "Lineitem price" in li.columns else pd.Series(dtype=float)
                    li_qty = pd.to_numeric(li["Lineitem quantity"], errors="coerce") if "Lineitem quantity" in li.columns else pd.Series(dtype=float)
                    li_disc = _money(li["Lineitem discount"]) if "Lineitem discount" in li.columns else pd.Series(0.0, index=li.index)
                    li["_line_net"] = (li_price * li_qty) - li_disc
                    if "Name" in li.columns:
                        per_order = li.groupby("Name")["_line_net"].sum()
                        out["alt"]["line_items_aggregate"] = float(per_order.dropna().sum())
                    else:
                        out["alt"]["line_items_aggregate"] = float(li["_line_net"].dropna().sum())
            except Exception:
                pass
            return out

        # ACTUAL net sales - what really happened
        ns1_dbg = _netsales_debug(rec)
        ns0_dbg = _netsales_debug(pri)
        ns1_actual = ns1_dbg.get("value", float("nan"))
        ns0_actual = ns0_dbg.get("value", float("nan"))

        # Use ACTUAL values for all calculations
        o1 = o1_actual
        o0 = o0_actual
        ns1 = ns1_actual
        ns0 = ns0_actual


        # AOV based on ACTUAL values
        aov1 = float(ns1/o1) if (o1 and not np.isnan(ns1)) else None
        aov0 = float(ns0/o0) if (o0 and not np.isnan(ns0)) else None

        # discount rate: total discount / subtotal (order-level); fallback to line-items (same window)
        def _disc_rate(frame_orders: pd.DataFrame) -> Optional[float]:
            if "Subtotal" in frame_orders.columns:
                sub = _money(frame_orders["Subtotal"]).sum(skipna=True)
                disc = _money(frame_orders["Total Discount"]).sum(skipna=True) if "Total Discount" in frame_orders.columns else 0.0
                if not np.isnan(sub) and sub>0:
                    return float(disc/(sub+1e-9))
            return None

        def _disc_rate_window(start: pd.Timestamp, end: pd.Timestamp, rec_orders: pd.DataFrame) -> Optional[float]:
            # Try order-level first
            val = _disc_rate(rec_orders)
            if val is not None:
                return val
            # Fallback: use line-items restricted to the same window/orders
            try:
                if all(c in d_kpi.columns for c in ["Lineitem price","Lineitem quantity"]):
                    if "Name" in rec_orders.columns and "Name" in d_kpi.columns:
                        order_names = set(rec_orders["Name"].astype(str))
                        li = d_kpi[d_kpi["Name"].astype(str).isin(order_names)].copy()
                    else:
                        li = d_kpi[(d_kpi["Created at"] >= start) & (d_kpi["Created at"] <= end)].copy()
                    if li.empty:
                        return None
                    li_price = _money(li["Lineitem price"]) if "Lineitem price" in li.columns else pd.Series(dtype=float)
                    li_qty = pd.to_numeric(li["Lineitem quantity"], errors="coerce") if "Lineitem quantity" in li.columns else pd.Series(dtype=float)
                    li_disc = _money(li["Lineitem discount"]) if "Lineitem discount" in li.columns else pd.Series(0.0, index=li.index)
                    denom = (li_price * li_qty).sum(skipna=True)
                    num = li_disc.sum(skipna=True)
                    if pd.notna(denom) and denom > 0:
                        return float(num / (denom + 1e-9))
            except Exception:
                return None
            return None

        dr1 = _disc_rate_window(rs, re, rec)
        dr0 = _disc_rate_window(ps, pe, pri)

        # Customer metrics: repeat within window and returning before window
        def _customer_metrics(frame_orders: pd.DataFrame, window_start: pd.Timestamp) -> Tuple[Optional[float], Optional[float], int]:
            keys = _identity_key(frame_orders).dropna()
            if keys.empty:
                return None, None, 0
            # Unique identified customers in this window
            unique = keys.dropna().unique()
            total = int(len(unique))
            if total < int(min_identified or 0):
                return None, None, total
            # Repeat purchase rate within window: customers with 2+ orders in this window
            counts = keys.value_counts()
            repeat_customers = int((counts > 1).sum())
            repeat_rate = float(repeat_customers / len(counts)) if len(counts) > 0 else None

            # Apply window-specific bias correction if enabled
            # M5 T5.6: bias correction default is OFF (the correction factor
            # was a fabricated multiplier {7:1.0, 28:0.95, 56:0.90, 90:0.85}
            # the statistical reviewer flagged in audit). The DEFAULTS in
            # this module already set ``ENABLE_REPEAT_RATE_BIAS_CORRECTION``
            # to ``False``; this call site previously defaulted to ``True``
            # when the cfg key was missing, which bypassed the M4a flip.
            # The bypass is removed: missing key -> False (off).
            if repeat_rate is not None and cfg and cfg.get("ENABLE_REPEAT_RATE_BIAS_CORRECTION", False):
                # Window-specific bias correction factors
                # Longer windows have more time bias, so apply larger corrections
                bias_corrections = {7: 1.0, 28: 0.95, 56: 0.90, 90: 0.85}
                correction_factor = bias_corrections.get(days, 1.0)
                repeat_rate = repeat_rate * correction_factor
            # Returning customer rate: had any order before the window start
            returning = int(sum((first_seen.get(k, window_start) < window_start) for k in unique))
            returning_rate = float(returning / total) if total > 0 else None
            return repeat_rate, returning_rate, total

        rep1, ret1, id1 = _customer_metrics(rec, rs)
        rep0, ret0, id0 = _customer_metrics(pri, ps)
        # New explicit metrics
        rrw1 = rep1  # repeat rate within window
        rrw0 = rep0
        rcs1 = ret1  # returning customer share (pre-window history)
        rcs0 = ret0
        ncr1 = (1.0 - rcs1) if (rcs1 is not None) else None
        ncr0 = (1.0 - rcs0) if (rcs0 is not None) else None

        # deltas based on ACTUAL values
        def _rel_delta(x1, x0):
            if x1 is None or x0 is None: return None
            if isinstance(x1,float) and (np.isnan(x1) or np.isnan(x0)): return None
            if x0 == 0: return None
            return float((x1 - x0) / abs(x0))

        delta = {
            "net_sales": _rel_delta(ns1, ns0),
            "orders":    _rel_delta(o1, o0),
            "aov":       _rel_delta(aov1, aov0),
            "discount_rate": _rel_delta(dr1, dr0),
            # New metrics
            "repeat_rate_within_window": _rel_delta(rrw1, rrw0),
            "returning_customer_share":  _rel_delta(rcs1, rcs0),
            "new_customer_rate":         _rel_delta(ncr1, ncr0),
        }

        # significance testing on ACTUAL values
        p = {
            "aov": None, "discount_rate": None,
            "repeat_rate_within_window": None,
            "returning_customer_share": None,
            "new_customer_rate": None,
        }
        
        # AOV: Welch t on per-order net values
        a1 = rec["_order_net"].dropna().values if "_order_net" in rec.columns else np.array([])
        a0 = pri["_order_net"].dropna().values if "_order_net" in pri.columns else np.array([])

        def _extract_p(val):
            if val is None:
                return None
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, dict):
                v = val.get("p_value")
                return float(v) if v is not None else None
            v = getattr(val, "p_value", None)
            return float(v) if v is not None else None

        if len(a1) > 1 and len(a0) > 1:
            mt = welch_t_test(a1, a0)
            p_aov = _extract_p(mt)
            p["aov"] = p_aov

        # Discount rate: Welch t-test on per-order discount rates
        # Aligns test with the metric reported (average discount depth), not just share of discounted orders.
        def _per_order_discount_rates(frame_orders: pd.DataFrame) -> np.ndarray:
            if ("Total Discount" not in frame_orders.columns) or ("Subtotal" not in frame_orders.columns):
                return np.array([])
            sub = _money(frame_orders["Subtotal"]).astype(float)
            disc = _money(frame_orders["Total Discount"]).astype(float)
            valid = sub.notna() & disc.notna() & (sub > 0)
            if not valid.any():
                return np.array([])
            rates = (disc[valid] / sub[valid]).clip(lower=0.0, upper=1.0)
            return rates.astype(float).values

        try:
            r1 = _per_order_discount_rates(rec)
            r0 = _per_order_discount_rates(pri)
            if (r1.size > 1) and (r0.size > 1):
                mt_dr = welch_t_test(r1, r0)
                p_dr = _extract_p(mt_dr)
                p["discount_rate"] = p_dr
        except Exception:
            pass

        # Repeat rate: two-proportion on identified customers within window
        if rep1 is not None and rep0 is not None and id1>=min_identified and id0>=min_identified:
            x1 = int(round(rep1*id1)); n1 = id1
            x0 = int(round(rep0*id0)); n0 = id0
            pr_rep = two_proportion_test(x1,n1,x0,n0)
            pval_rep = float(pr_rep.p_value)
            p["repeat_rate_within_window"] = pval_rep
        # Returning rate: two-proportion on identified customers
        if ret1 is not None and ret0 is not None and id1>=min_identified and id0>=min_identified:
            x1r = int(round(ret1*id1)); n1r = id1
            x0r = int(round(ret0*id0)); n0r = id0
            pr_ret = two_proportion_test(x1r,n1r,x0r,n0r)
            pval_ret = float(pr_ret.p_value)
            p["returning_customer_share"] = pval_ret
            # M4a T4a.6: new_customer_rate is mathematically 1 - returning_customer_share, so
            # mirroring its p-value into the BH list double-counts the same hypothesis test
            # and shrinks every other metric's q-value share. Behind STATS_NAN_FOR_HARDCODED
            # we drop the duplicate entry (still surface the rate itself in the result body
            # below). Flag-off path is unchanged from M3 to preserve M0 goldens.
            _drop_ncr_from_bh = bool(cfg.get("STATS_NAN_FOR_HARDCODED", False)) if isinstance(cfg, dict) else False
            if not _drop_ncr_from_bh:
                # legacy behavior (pre-M4a): mirror returning p into new_customer_rate
                p["new_customer_rate"] = pval_ret

        # FDR on available p's
        p_list = []
        p_keys = list(p.keys())
        for k in p_keys:
            v = p[k]
            if v is None or (isinstance(v, float) and np.isnan(v)):
                p_list.append(1.0)
            else:
                p_list.append(float(v))

        # q-values via safe wrapper
        if any(v < 1.0 for v in p_list):
            qvals = _bh_adjust(p_list, alpha=alpha)
            q = {k: float(qvals[i]) if qvals[i] is not None else None for i, k in enumerate(p_keys)}
        else:
            q = {k: None for k in p_keys}

        # significance: prefer q ≤ alpha if available, else p ≤ alpha
        sig = {}
        for i, k in enumerate(p_keys):
            qk = q.get(k)
            pk = p.get(k)
            if qk is not None and not (isinstance(qk, float) and np.isnan(qk)):
                sig[k] = (qk <= alpha)
            else:
                sig[k] = (pk is not None and pk <= alpha)

        # Build result body
        result = {
            "net_sales": None if np.isnan(ns1) else float(ns1),
            "orders": o1,
            "aov": aov1,
            "discount_rate": dr1,
            # New explicit metrics
            "repeat_rate_within_window": rrw1,
            "returning_customer_share": rcs1,
            "new_customer_rate": ncr1,
            "prior": {
                "net_sales": None if np.isnan(ns0) else float(ns0),
                "orders": o0,
                "aov": aov0,
                "discount_rate": dr0,
                # New explicit metrics
                "repeat_rate_within_window": rrw0,
                "returning_customer_share": rcs0,
                "new_customer_rate": ncr0,
            },
            "delta": delta,
            "p": p,
            "q": q,
            "sig": sig,
            "meta": {
                "identified_recent": id1,
                "identified_prior": id0
            }
        }
        # Record method used + debug comparisons for transparency
        try:
            def _consistency(meta_key_prefix: str, dbg: dict):
                result.setdefault("meta", {})[f"{meta_key_prefix}_netsales_method"] = dbg.get("method")
                # compute diffs vs alternatives
                val = dbg.get("value")
                alts = dbg.get("alt", {}) or {}
                diffs = {}
                for k, v in alts.items():
                    try:
                        if v is None or val is None or np.isnan(val):
                            continue
                        if val == 0:
                            continue
                        diffs[k] = float((val - float(v)) / abs(val))
                    except Exception:
                        continue
                result["meta"][f"{meta_key_prefix}_netsales_alt_diffs"] = diffs
                # flag if any alternative differs >10%
                if any(abs(x) > 0.10 for x in diffs.values()):
                    result["meta"][f"{meta_key_prefix}_netsales_consistency_flag"] = True
            _consistency("recent", ns1_dbg)
            _consistency("prior", ns0_dbg)
        except Exception:
            # keep snapshot robust even if debug calc fails
            pass
        

        return result

    out = {"anchor": anchor, "L7": _summarize(7), "L28": _summarize(28), "L56": _summarize(56), "L90": _summarize(90)}
    out["meta"] = {
        "seasonal_adjusted": bool(seasonally_adjust),
        "seasonal_period": int(seasonal_period) if seasonally_adjust else None,
        "seasonal_method": None,
        "metric_version": "v2_repeat_metrics",
    }
    
    # convenience: top-level recent values for backward compatibility
    for label in ("L7","L28"):
        for k in (
            "net_sales","orders","aov","discount_rate",
            # New explicit metrics
            "repeat_rate_within_window","returning_customer_share","new_customer_rate",
            # Back-compat aliases
            "repeat_share","repeat_rate","returning_rate"
        ):
            out[label][k] = out[label].get(k)
    
    # include direction rule hint for UI
    out["direction"] = {"discount_rate": ("down" if discount_positive_is_bad else "up")}
    
    return out
# --- Safe BH wrapper + fallback (put near top-level helpers in utils.py) ---

def _bh_fallback(pvals: list[float]) -> list[float]:
    """Benjamini–Hochberg q-values (independent/positive dependence). No alpha needed."""
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    order = np.argsort(p)
    p_sorted = p[order]
    q_sorted = np.empty(m, dtype=float)
    prev = 1.0
    for i in range(m - 1, -1, -1):
        rank = i + 1
        q_i = (m / rank) * p_sorted[i]
        prev = min(prev, q_i)
        q_sorted[i] = prev
    q = np.empty(m, dtype=float)
    q[order] = np.clip(q_sorted, 0.0, 1.0)
    return q.tolist()

def _bh_adjust(p_list: list[float], alpha: float = 0.05) -> list[float]:
    """
    Try benjamini_hochberg with keyword, then positional, else fall back to local impl.
    Always returns a list of q-values aligned to p_list.
    """
    try:
        # try keyword
        out = benjamini_hochberg(p_list, alpha=alpha)  # type: ignore[arg-type]
        return list(out[0] if isinstance(out, tuple) else out)
    except TypeError:
        try:
            # try positional alpha
            out = benjamini_hochberg(p_list, alpha)  # type: ignore[misc]
            return list(out[0] if isinstance(out, tuple) else out)
        except Exception:
            # pure p->q implementation (no alpha arg)
            return _bh_fallback(p_list)

# ---------------- Unified Tier System ----------------

def get_confidence_display_data(outputs):
    """Legacy compatibility function for confidence display data"""
    # Simple passthrough since engine now handles confidence directly
    return {
        'mode': 'engine',
        'total_actions': len(outputs.get('actions', [])) + len(outputs.get('pilot_actions', [])),
        'tier_distribution': organize_by_engine_tiers(outputs)['confidence_tiers']
    }

def organize_by_engine_tiers(outputs):
    """Organize actions by their engine_tier assignments (replaces enhance_actions_with_confidence_tiers)"""
    try:
        # Initialize tier buckets
        tiers = {
            'primary': [],
            'quick_wins': [], 
            'experiments': [],
            'watchlist': []
        }
        
        # Collect all candidates with deduplication by play_id
        seen_plays = set()
        all_candidates = []
        
        # Process all action sources
        for source in ['actions', 'pilot_actions', 'watchlist', 'backlog']:
            for item in outputs.get(source, []):
                play_id = item.get('play_id')
                if play_id and play_id not in seen_plays:
                    all_candidates.append(item)
                    seen_plays.add(play_id)
        
        # Group candidates by their engine_tier
        for candidate in all_candidates:
            engine_tier = candidate.get('engine_tier', 'watchlist').lower()
            
            # Map engine tier names to display tier names
            tier_mapping = {
                'primary': 'primary',
                'quick_wins': 'quick_wins',
                'experiments': 'experiments', 
                'watchlist': 'watchlist'
            }
            
            display_tier = tier_mapping.get(engine_tier, 'watchlist')
            tiers[display_tier].append(candidate)
        
        cfg = outputs.get('cfg', {}) or {}
        mode = str(cfg.get('CONFIDENCE_MODE', 'learning')).strip().lower()
        if mode == 'learning':
            primary_threshold, quick_wins_threshold, experiments_threshold = 0.65, 0.50, 0.35
        elif mode == 'conservative':
            primary_threshold, quick_wins_threshold, experiments_threshold = 0.80, 0.65, 0.45
        else:  # aggressive
            primary_threshold, quick_wins_threshold, experiments_threshold = 0.75, 0.60, 0.40

        def pct(value: float) -> int:
            return int(round(value * 100))

        primary_pct = pct(primary_threshold)
        quick_pct = pct(quick_wins_threshold)
        experiments_pct = pct(experiments_threshold)

        tier_metadata = {
            'primary': {
                'icon': '🎯',
                'label': 'PRIMARY ACTION',
                'confidence_range': f"≥{primary_pct}% confidence",
                'min_pct': primary_pct,
                'max_pct': 100
            },
            'quick_wins': {
                'icon': '⚡',
                'label': 'QUICK WINS',
                'confidence_range': f"{quick_pct}–{max(primary_pct - 1, quick_pct)}% confidence",
                'min_pct': quick_pct,
                'max_pct': max(primary_pct - 1, quick_pct)
            },
            'experiments': {
                'icon': '🔬',
                'label': 'EXPERIMENTS',
                'confidence_range': f"{experiments_pct}–{max(quick_pct - 1, experiments_pct)}% confidence",
                'min_pct': experiments_pct,
                'max_pct': max(quick_pct - 1, experiments_pct)
            },
            'watchlist': {
                'icon': '👁️',
                'label': 'WATCHLIST',
                'confidence_range': f"< {experiments_pct}% confidence",
                'min_pct': 0,
                'max_pct': max(experiments_pct - 1, 0)
            }
        }

        # Return enhanced outputs with tier organization
        enhanced_outputs = outputs.copy()
        enhanced_outputs['confidence_tiers'] = tiers
        enhanced_outputs['tier_metadata'] = tier_metadata
        enhanced_outputs['confidence_mode'] = mode
        enhanced_outputs['tier_thresholds'] = {
            'primary': primary_threshold,
            'quick_wins': quick_wins_threshold,
            'experiments': experiments_threshold
        }
        enhanced_outputs['_enhanced'] = True
        enhanced_outputs['_tier_system'] = 'engine'

        return enhanced_outputs
        
    except Exception:
        # Fallback: return original outputs
        return outputs

# ---------------- beacon Score Implementation (Phase 1) ----------------

def calculate_aura_score(aligned_data):
    """Calculate business health score 0-100 with multi-window analysis and component breakdown"""
    try:
        # Check for multi-window data structure
        has_multiwindow = any(key.startswith('L') and key[1:].isdigit() for key in aligned_data.keys())
        
        if has_multiwindow:
            # Use enhanced multi-window analysis
            return _calculate_multiwindow_aura_score(aligned_data)
        else:
            # Fallback to L28 single-window analysis
            return _calculate_single_window_aura_score(aligned_data)
            
    except Exception as e:
        print(f"beacon Score calculation error: {e}")
        return _default_aura_score()

def _calculate_multiwindow_aura_score(aligned_data):
    """Enhanced beacon Score using multi-window analysis"""
    # Window weights for different metrics
    # L7 removed from beacon score calculation
    window_weights = {
        'L7': 0.0,   # Removed - too volatile for reliable scoring
        'L28': 0.4,  # Short-term business cycle
        'L56': 0.4,  # Primary medium-term trends (beauty/supplement cycles)
        'L90': 0.2   # Long-term patterns
    }
    
    # Aggregate metrics across windows
    aggregated_metrics = _aggregate_multiwindow_metrics(aligned_data, window_weights)
    
    # Calculate components with enhanced multi-window signals
    components = {}
    
    # Revenue Health (30% weight) - Multi-window momentum
    revenue_momentum = _calculate_revenue_momentum(aligned_data, window_weights)
    components['revenue_health'] = min(100, max(0, revenue_momentum))
    
    # Customer Health (25% weight) - Cross-window retention patterns
    customer_momentum = _calculate_customer_momentum(aligned_data, window_weights)
    components['customer_health'] = min(100, max(0, customer_momentum))
    
    # Margin Health (20% weight) - AOV and discount trends across windows
    margin_momentum = _calculate_margin_momentum(aligned_data, window_weights)
    components['margin_health'] = min(100, max(0, margin_momentum))
    
    # Growth Health (15% weight) - Multi-window growth acceleration
    growth_momentum = _calculate_growth_momentum(aligned_data, window_weights)
    components['growth_health'] = min(100, max(0, growth_momentum))
    
    # LTV Health (10% weight) - Long-term value indicators
    ltv_momentum = _calculate_ltv_momentum(aligned_data, window_weights)
    components['ltv_health'] = min(100, max(0, ltv_momentum))
    
    # Calculate weighted overall score
    weights = {
        'revenue_health': 0.30,
        'customer_health': 0.25, 
        'margin_health': 0.20,
        'growth_health': 0.15,
        'ltv_health': 0.10
    }
    
    overall = sum(components[k] * weights[k] for k in components.keys())
    overall = max(0, min(100, int(round(overall))))
    
    # Multi-window trend indicator
    trend = _calculate_multiwindow_trend(aligned_data, window_weights)
    
    # Determine tier
    if overall >= 80:
        tier = "excellent"
    elif overall >= 65:
        tier = "healthy"
    elif overall >= 50:
        tier = "moderate"
    elif overall >= 35:
        tier = "concerning"
    else:
        tier = "critical"

    return {
        'overall': overall,
        'tier': tier,
        'trend': trend,
        'components': components,
        'analysis_method': 'multi_window',
        'windows_analyzed': list(window_weights.keys())
    }

def _calculate_single_window_aura_score(aligned_data):
    """Fallback single-window beacon Score calculation"""
    # Get L28 data as primary source
    l28_data = aligned_data.get('L28', {})
    if not l28_data:
        return _default_aura_score()
    
    # Extract core metrics with safe defaults
    orders = float(l28_data.get('orders', 0) or 0)
    net_sales = float(l28_data.get('net_sales', 0) or 0)
    aov = float(l28_data.get('aov', 0) or 0)
    returning_customer_share = float(l28_data.get('returning_customer_share', 0) or 0)
    repeat_rate = float(l28_data.get('repeat_rate_within_window', 0) or 0)
    discount_rate = float(l28_data.get('discount_rate', 0) or 0)
    
    # Get deltas for trend calculation
    deltas = l28_data.get('delta', {})
    orders_delta = float(deltas.get('orders', 0) or 0)
    net_sales_delta = float(deltas.get('net_sales', 0) or 0)
    aov_delta = float(deltas.get('aov', 0) or 0)
    
    # Component calculations (0-100 scale) - legacy single-window method
    components = {}
    
    # Revenue Health (30% weight)
    # Based on order volume and growth trend
    if orders >= 500:
        revenue_base = 85
    elif orders >= 250:
        revenue_base = 75
    elif orders >= 100:
        revenue_base = 65
    elif orders >= 50:
        revenue_base = 50
    else:
        revenue_base = 30
    
    # Apply growth delta bonus/penalty
    growth_bonus = min(15, max(-15, orders_delta * 50))
    components['revenue_health'] = max(0, min(100, revenue_base + growth_bonus))
    
    # Customer Health (25% weight) 
    # Based on returning customer share and repeat behavior
    customer_base = min(100, returning_customer_share * 100)
    repeat_bonus = min(10, repeat_rate * 50)
    components['customer_health'] = max(0, min(100, customer_base + repeat_bonus))
    
    # Margin Health (20% weight)
    # Based on AOV and discount efficiency
    if aov >= 100:
        margin_base = 80
    elif aov >= 75:
        margin_base = 70
    elif aov >= 50:
        margin_base = 60
    elif aov >= 25:
        margin_base = 45
    else:
        margin_base = 25
    
    # Discount penalty (high discount rate hurts margin health)
    discount_penalty = min(20, discount_rate * 40)
    components['margin_health'] = max(0, min(100, margin_base - discount_penalty))
    
    # Growth Health (15% weight)
    # Based on recent performance trends
    if net_sales_delta > 0.2:
        growth_score = 90
    elif net_sales_delta > 0.1:
        growth_score = 80
    elif net_sales_delta > 0.05:
        growth_score = 70
    elif net_sales_delta >= 0:
        growth_score = 60
    elif net_sales_delta > -0.05:
        growth_score = 45
    elif net_sales_delta > -0.1:
        growth_score = 30
    else:
        growth_score = 15
    components['growth_health'] = growth_score
    
    # LTV Health (10% weight)
    # Based on AOV trends and customer retention
    ltv_base = min(80, aov / 2)  # AOV contributes to LTV potential
    if aov_delta > 0:
        ltv_bonus = min(15, aov_delta * 30)
    else:
        ltv_bonus = max(-10, aov_delta * 20)
    retention_bonus = min(10, returning_customer_share * 15)
    components['ltv_health'] = max(0, min(100, ltv_base + ltv_bonus + retention_bonus))
    
    # Calculate weighted overall score
    weights = {
        'revenue_health': 0.30,
        'customer_health': 0.25, 
        'margin_health': 0.20,
        'growth_health': 0.15,
        'ltv_health': 0.10
    }
    
    overall = sum(components[k] * weights[k] for k in components.keys())
    overall = max(0, min(100, int(round(overall))))
    
    # Calculate trend indicator
    trend_factors = [orders_delta, net_sales_delta, aov_delta]
    avg_trend = sum(t for t in trend_factors if t is not None) / len([t for t in trend_factors if t is not None])
    
    if avg_trend > 0.1:
        trend = f"+{int(avg_trend * 100)}"
    elif avg_trend < -0.05:
        trend = f"{int(avg_trend * 100)}"
    else:
        trend = "0"
    
    # Determine tier
    if overall >= 80:
        tier = "excellent"
    elif overall >= 65:
        tier = "healthy"
    elif overall >= 50:
        tier = "moderate"
    elif overall >= 35:
        tier = "concerning"
    else:
        tier = "critical"
    
    # Generate diagnostic insights instead of recommendations
    insights = []
    if components['revenue_health'] < 60:
        insights.append(f"Your Revenue Health ({int(components['revenue_health'])}/100) indicates {int(orders)} monthly orders need growth acceleration")
    elif components['revenue_health'] < 80:
        insights.append(f"Your Revenue Health ({int(components['revenue_health'])}/100) shows solid volume with room for optimization")
    else:
        insights.append(f"Your Revenue Health ({int(components['revenue_health'])}/100) demonstrates strong order volume and growth momentum")
        
    if components['customer_health'] < 60:
        insights.append(f"Your Customer Health ({int(components['customer_health'])}/100) reflects {returning_customer_share:.0%} returning customers - focus area for retention")
    elif components['customer_health'] < 80:
        insights.append(f"Your Customer Health ({int(components['customer_health'])}/100) shows moderate customer loyalty with improvement potential")
    else:
        insights.append(f"Your Customer Health ({int(components['customer_health'])}/100) demonstrates excellent customer retention and repeat behavior")
        
    if components['margin_health'] < 60:
        insights.append(f"Your Margin Health ({int(components['margin_health'])}/100) indicates ${aov:.0f} AOV with {discount_rate:.0%} discount dependency")
    elif components['margin_health'] < 80:
        insights.append(f"Your Margin Health ({int(components['margin_health'])}/100) shows healthy pricing with some discount optimization opportunity")
    else:
        insights.append(f"Your Margin Health ({int(components['margin_health'])}/100) reflects excellent pricing efficiency and value capture")
    
    return {
        "overall": overall,
        "tier": tier,
        "trend": trend,
        "components": {k: int(round(v)) for k, v in components.items()},
        "insights": insights[:3]  # Limit to top 3 diagnostic insights
    }

def _default_aura_score():
    """Default beacon Score when calculation fails"""
    return {
        "overall": 50,
        "tier": "moderate", 
        "trend": "0",
        "components": {
            "revenue_health": 50,
            "customer_health": 50,
            "margin_health": 50,
            "growth_health": 50,
            "ltv_health": 50
        },
        "insights": ["Ensure data quality for accurate health scoring"]
    }

# ---------------- Phase 3: Action-to-Health Impact Prediction ----------------

def predict_action_health_impact(action, current_aura_components=None):
    """Predict how an action will impact beacon Score health components"""
    try:
        if current_aura_components is None:
            current_aura_components = {}
            
        # Extract action metadata
        play_id = str(action.get('play_id', '')).lower()
        title = str(action.get('title', '')).lower()
        expected_revenue = float(action.get('expected_$', 0) or 0)
        audience_size = int(action.get('n', 0) or 0)
        
        # Initialize impact predictions
        impacts = {}
        primary_impact = ""
        
        # Map action types to health component impacts
        if any(keyword in play_id or keyword in title for keyword in ['winback', 'retention', 'repeat']):
            # Customer retention focused actions
            primary_impact = "customer_health"
            base_impact = min(15, audience_size / 100)  # Scale with audience
            impacts['customer_health'] = int(base_impact + (expected_revenue / 1000))
            impacts['revenue_health'] = int(base_impact * 0.6)  # Secondary benefit
            
        elif any(keyword in play_id or keyword in title for keyword in ['discount', 'pricing', 'margin']):
            # Margin/pricing focused actions  
            primary_impact = "margin_health"
            base_impact = min(12, expected_revenue / 500)
            impacts['margin_health'] = int(base_impact)
            impacts['revenue_health'] = int(base_impact * 0.4)  # May reduce revenue short-term
            
        elif any(keyword in play_id or keyword in title for keyword in ['acquisition', 'new_customer', 'growth']):
            # Growth/acquisition focused actions
            primary_impact = "revenue_health"  
            base_impact = min(18, audience_size / 150)
            impacts['revenue_health'] = int(base_impact)
            impacts['growth_health'] = int(base_impact * 0.7)
            
        elif any(keyword in play_id or keyword in title for keyword in ['bestseller', 'upsell', 'cross_sell', 'bundle']):
            # Revenue optimization actions
            primary_impact = "ltv_health"
            base_impact = min(10, expected_revenue / 800)
            impacts['ltv_health'] = int(base_impact)
            impacts['margin_health'] = int(base_impact * 0.5)
            impacts['revenue_health'] = int(base_impact * 0.8)
            
        elif any(keyword in play_id or keyword in title for keyword in ['subscription', 'recurring']):
            # LTV focused actions
            primary_impact = "ltv_health" 
            base_impact = min(20, expected_revenue / 400)  # Subscriptions have high LTV impact
            impacts['ltv_health'] = int(base_impact)
            impacts['customer_health'] = int(base_impact * 0.6)
            impacts['revenue_health'] = int(base_impact * 0.4)
            
        else:
            # General revenue actions
            primary_impact = "revenue_health"
            base_impact = min(8, expected_revenue / 1000)
            impacts['revenue_health'] = int(base_impact)
            
        # Remove zero impacts and ensure minimum impact for primary
        impacts = {k: v for k, v in impacts.items() if v > 0}
        if primary_impact and primary_impact not in impacts:
            impacts[primary_impact] = 3  # Minimum impact
            
        # Calculate projected overall improvement 
        if impacts and current_aura_components:
            weights = {
                'revenue_health': 0.30,
                'customer_health': 0.25, 
                'margin_health': 0.20,
                'growth_health': 0.15,
                'ltv_health': 0.10
            }
            overall_impact = sum(impacts.get(k, 0) * weights.get(k, 0) for k in weights.keys())
            overall_impact = int(round(overall_impact))
        else:
            overall_impact = sum(impacts.values()) // 5 if impacts else 0
        
        return {
            "impacts": impacts,
            "primary_impact": primary_impact,
            "overall_impact": max(1, overall_impact) if impacts else 0,
            "impact_summary": _format_health_impact_summary(impacts, primary_impact)
        }
        
    except Exception:
        # Fallback to minimal impact
        return {
            "impacts": {"revenue_health": 2},
            "primary_impact": "revenue_health", 
            "overall_impact": 2,
            "impact_summary": "Will contribute to overall business health"
        }

def _format_health_impact_summary(impacts, primary_impact):
    """Format impact summary for display"""
    if not impacts:
        return "Will contribute to overall business health"
        
    # Create readable component names
    readable_names = {
        'revenue_health': 'Revenue Health',
        'customer_health': 'Customer Health', 
        'margin_health': 'Margin Health',
        'growth_health': 'Growth Health',
        'ltv_health': 'LTV Health'
    }
    
    # Sort by impact value, highest first
    sorted_impacts = sorted(impacts.items(), key=lambda x: x[1], reverse=True)
    
    # Format the summary
    impact_parts = []
    for component, points in sorted_impacts:
        name = readable_names.get(component, component.replace('_', ' ').title())
        impact_parts.append(f"{name} +{points}")
    
    if len(impact_parts) == 1:
        return f"Will improve: {impact_parts[0]} points"
    elif len(impact_parts) == 2:
        return f"Will improve: {impact_parts[0]} and {impact_parts[1]} points"
    else:
        return f"Will improve: {', '.join(impact_parts[:-1])}, and {impact_parts[-1]} points"

def enhance_actions_with_health_impact(actions, current_aura_components=None):
    """Add health impact predictions to a list of actions"""
    if not actions:
        return actions
        
    enhanced_actions = []
    for action in actions:
        enhanced_action = action.copy()
        health_impact = predict_action_health_impact(action, current_aura_components)
        enhanced_action['health_impact'] = health_impact
        
        # Debug: Verify health impact was added correctly
        if not health_impact.get('impact_summary'):
            print(f"[DEBUG] Action '{action.get('title', 'Unknown')}' has empty impact_summary")
        
        enhanced_actions.append(enhanced_action)
    
    return enhanced_actions

# ========== Multi-Window beacon Score Helper Functions ==========

def _aggregate_multiwindow_metrics(aligned_data, window_weights):
    """Aggregate metrics across multiple windows with weighting"""
    aggregated = {}
    
    for window, weight in window_weights.items():
        if window in aligned_data:
            window_data = aligned_data[window]
            for metric in ['orders', 'net_sales', 'aov', 'returning_customer_share', 'repeat_rate_within_window', 'discount_rate']:
                if metric in window_data:
                    if metric not in aggregated:
                        aggregated[metric] = 0
                    aggregated[metric] += float(window_data.get(metric, 0) or 0) * weight
    
    return aggregated

def _calculate_revenue_momentum(aligned_data, window_weights):
    """Calculate revenue health using multi-window weighted average + global growth"""
    # Calculate weighted average orders across windows (current state)
    total_weighted_orders = 0
    total_weight = 0
    
    for window, weight in window_weights.items():
        if window in aligned_data:
            window_data = aligned_data[window]
            orders = float(window_data.get('orders', 0) or 0)
            total_weighted_orders += orders * weight
            total_weight += weight
    
    if total_weight == 0:
        return 30
    
    avg_orders = total_weighted_orders / total_weight
    
    # Base score from weighted average order volume
    if avg_orders >= 500:
        revenue_base = 85
    elif avg_orders >= 250:
        revenue_base = 75
    elif avg_orders >= 100:
        revenue_base = 65
    elif avg_orders >= 50:
        revenue_base = 50
    else:
        revenue_base = 30
    
    # Growth bonus from global orders delta (business trajectory)
    global_growth = float(aligned_data.get('orders_delta', 0) or 0)
    growth_bonus = min(20, max(-20, global_growth * 100))
    
    return revenue_base + growth_bonus

def _calculate_customer_momentum(aligned_data, window_weights):
    """Calculate customer health using weighted retention metrics + global growth"""
    # Calculate weighted average retention metrics across windows (current state)
    total_weighted_retention = 0
    total_weighted_repeat = 0
    total_weight = 0
    
    for window, weight in window_weights.items():
        if window in aligned_data:
            window_data = aligned_data[window]
            retention = float(window_data.get('returning_customer_share', 0) or 0)
            repeat_rate = float(window_data.get('repeat_rate_within_window', 0) or 0)
            
            total_weighted_retention += retention * weight
            total_weighted_repeat += repeat_rate * weight
            total_weight += weight
    
    if total_weight == 0:
        return 0
    
    avg_retention = total_weighted_retention / total_weight
    avg_repeat = total_weighted_repeat / total_weight
    
    # Base score from weighted average retention metrics
    customer_base = min(100, avg_retention * 100)
    repeat_bonus = min(15, avg_repeat * 75)
    
    # Growth bonus from global retention delta (business trajectory)
    global_retention_growth = float(aligned_data.get('returning_customer_share_delta', 0) or 0)
    retention_trend_bonus = min(10, max(-10, global_retention_growth * 200))
    
    return customer_base + repeat_bonus + retention_trend_bonus

def _calculate_margin_momentum(aligned_data, window_weights):
    """Calculate margin health using weighted AOV/discount + global trends"""
    # Calculate weighted average margin metrics across windows (current state)
    total_weighted_aov = 0
    total_weighted_discount = 0
    total_weight = 0
    
    for window, weight in window_weights.items():
        if window in aligned_data:
            window_data = aligned_data[window]
            aov = float(window_data.get('aov', 0) or 0)
            discount_rate = float(window_data.get('discount_rate', 0) or 0)
            
            total_weighted_aov += aov * weight
            total_weighted_discount += discount_rate * weight
            total_weight += weight
    
    if total_weight == 0:
        return 25
    
    avg_aov = total_weighted_aov / total_weight
    avg_discount = total_weighted_discount / total_weight
    
    # Base score from weighted average AOV
    if avg_aov >= 100:
        margin_base = 80
    elif avg_aov >= 75:
        margin_base = 70
    elif avg_aov >= 50:
        margin_base = 60
    elif avg_aov >= 25:
        margin_base = 45
    else:
        margin_base = 25
    
    # Discount penalty from current state
    discount_penalty = min(25, avg_discount * 50)
    
    # AOV growth bonus from global trend (business trajectory)
    global_aov_growth = float(aligned_data.get('aov_delta', 0) or 0)
    aov_trend_bonus = min(15, max(-15, global_aov_growth * 300))
    
    return margin_base - discount_penalty + aov_trend_bonus

def _calculate_growth_momentum(aligned_data, window_weights):
    """Calculate growth health using global business trajectory"""
    # Pure momentum metric using global deltas (not per-window)
    orders_growth = float(aligned_data.get('orders_delta', 0) or 0)
    sales_growth = float(aligned_data.get('net_sales_delta', 0) or 0)
    
    # Combined growth signal
    avg_growth = (orders_growth + sales_growth) / 2
    
    # Growth health scoring based on overall business trajectory
    if avg_growth > 0.2:
        return 95
    elif avg_growth > 0.1:
        return 85
    elif avg_growth > 0.05:
        return 75
    elif avg_growth >= 0:
        return 65
    elif avg_growth > -0.05:
        return 50
    elif avg_growth > -0.1:
        return 35
    else:
        return 20

def _calculate_ltv_momentum(aligned_data, window_weights):
    """Calculate LTV health using long-term weighted metrics + global trends"""
    # Emphasize longer windows for LTV assessment
    ltv_weights = {
        'L7': 0.1,   # Recent behavior
        'L28': 0.2,  # Short-term value
        'L56': 0.35, # Medium-term patterns
        'L90': 0.35  # Long-term value indicators
    }
    
    total_weighted_aov = 0
    total_weighted_retention = 0
    total_weight = 0
    
    for window, weight in ltv_weights.items():
        if window in aligned_data:
            window_data = aligned_data[window]
            aov = float(window_data.get('aov', 0) or 0)
            retention = float(window_data.get('returning_customer_share', 0) or 0)
            
            total_weighted_aov += aov * weight
            total_weighted_retention += retention * weight
            total_weight += weight
    
    if total_weight == 0:
        return 41
    
    avg_aov = total_weighted_aov / total_weight
    avg_retention = total_weighted_retention / total_weight
    
    # LTV base score from long-term weighted metrics
    ltv_base = min(80, avg_aov / 2)
    retention_bonus = min(15, avg_retention * 20)
    
    # Future value projection from global trends
    global_aov_growth = float(aligned_data.get('aov_delta', 0) or 0)
    global_retention_growth = float(aligned_data.get('returning_customer_share_delta', 0) or 0)
    
    aov_trend_bonus = min(10, max(-10, global_aov_growth * 200))
    retention_trend_bonus = min(10, max(-5, global_retention_growth * 100))
    
    return ltv_base + retention_bonus + aov_trend_bonus + retention_trend_bonus

def _calculate_multiwindow_trend(aligned_data, window_weights):
    """Calculate overall trend indicator using global deltas"""
    # Use global deltas for overall business trajectory
    orders_delta = float(aligned_data.get('orders_delta', 0) or 0)
    sales_delta = float(aligned_data.get('net_sales_delta', 0) or 0)
    aov_delta = float(aligned_data.get('aov_delta', 0) or 0)
    
    # Average the key trend signals
    overall_trend = (orders_delta + sales_delta + aov_delta) / 3
    
    if overall_trend > 0.1:
        return f"+{int(overall_trend * 100)}"
    elif overall_trend < -0.05:
        return f"{int(overall_trend * 100)}"
    else:
        return "0"
