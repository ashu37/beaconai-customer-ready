"""
Enhanced charts for Beauty/Supplements stores
Focuses on actionable insights rather than generic comparisons
"""
from __future__ import annotations
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
import os
import re

from .utils import get_vertical_mode, get_window_weights
try:
    import seaborn as sns
    sns.set_palette("husl")
except Exception:
    sns = None  # Seaborn is optional; fall back to Matplotlib defaults

# Set beautiful defaults for Beauty vertical
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'axes.titlesize': 14,
    'axes.labelsize': 12,
    'axes.titlepad': 12,
    'xtick.labelsize': 11,
    'ytick.labelsize': 11,
    'legend.fontsize': 11,
    'figure.autolayout': False,
})

ACTION_METRIC_MAP: Dict[str, Dict[str, Any]] = {
    'repeat_rate': {
        'fields': ['repeat_rate_within_window', 'repeat_share', 'repeat_rate'],
        'label': 'Repeat Purchase Rate',
        'unit': 'pct',
    },
    'frequency': {
        'fields': ['repeat_rate_within_window', 'repeat_share', 'repeat_rate'],
        'label': 'Repeat Purchase Rate',
        'unit': 'pct',
    },
    'retention': {
        'fields': ['returning_customer_share', 'repeat_rate_within_window'],
        'label': 'Returning Customer Share',
        'unit': 'pct',
    },
    'aov': {
        'fields': ['aov'],
        'label': 'Average Order Value',
        'unit': 'currency',
    },
    'bundle_aov': {
        'fields': ['aov'],
        'label': 'Average Order Value',
        'unit': 'currency',
    },
    'discount_rate': {
        'fields': ['discount_rate'],
        'label': 'Discount Rate',
        'unit': 'pct',
    },
    'subscription': {
        'fields': ['repeat_rate_within_window', 'returning_customer_share'],
        'label': 'Repeat Purchase Readiness',
        'unit': 'pct',
    },
    'reorder': {
        'fields': ['repeat_rate_within_window', 'returning_customer_share'],
        'label': 'Reorder Readiness',
        'unit': 'pct',
    },
    'conversion': {
        'fields': ['new_customer_rate', 'conversion_rate'],
        'label': 'Conversion Rate',
        'unit': 'pct',
    },
}

ACTION_COLLECTION_KEYS: List[str] = [
    'actions',
    'primary',
    'quick_wins',
    'experiments',
    'watchlist',
    'backlog',
    'pilot_actions',
]


def _slugify(value: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '_', str(value).lower()).strip('_')
    return slug or 'action'


def _format_value(val: Optional[float], unit: str) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return '—'
    if unit == 'pct':
        return f"{val * 100:.1f}%"
    if unit == 'currency':
        return f"${val:,.0f}"
    return f"{val:,.0f}"


def _get_metric_from_fields(data: Dict[str, Any], fields: List[str]) -> Optional[float]:
    if not data:
        return None
    for field in fields:
        if field in data and data[field] is not None:
            try:
                return float(data[field])
            except (TypeError, ValueError):
                continue
    return None


def _collect_window_metric_rows(
    aligned: Dict[str, Any],
    windows: List[str],
    metric_fields: List[str],
    window_scores: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for window in windows:
        block = aligned.get(window, {}) or {}
        if not block:
            continue
        current = _get_metric_from_fields(block, metric_fields)
        prior = _get_metric_from_fields(block.get('prior', {}) or {}, metric_fields)
        delta = _get_metric_from_fields(block.get('delta', {}) or {}, metric_fields)
        p_val = None
        if block.get('p'):
            p_val = _get_metric_from_fields(block['p'], metric_fields)
        if p_val is None and window_scores:
            try:
                raw = window_scores.get(window)
                if raw is not None:
                    p_val = float(raw)
            except (TypeError, ValueError):
                p_val = None
        rows.append({
            'window': window,
            'recent': current,
            'prior': prior,
            'delta': delta,
            'p_value': p_val,
        })
    return rows


def _weighted_average(rows: List[Dict[str, Any]], key: str, weights: Dict[str, float]) -> Optional[float]:
    numerator = 0.0
    denominator = 0.0
    for row in rows:
        value = row.get(key)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            continue
        w = float(weights.get(row['window'], 0.0))
        if w <= 0:
            continue
        numerator += value * w
        denominator += w
    if denominator == 0:
        # Fallback to simple average ignoring weights
        values = [row.get(key) for row in rows if row.get(key) is not None]
        if not values:
            return None
        return float(np.mean(values))
    return numerator / denominator


def _set_axis_formatter(ax, unit: str) -> None:
    if unit == 'pct':
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    elif unit == 'currency':
        ax.yaxis.set_major_formatter(mtick.StrMethodFormatter('${x:,.0f}'))
    else:
        ax.yaxis.set_major_formatter(mtick.StrMethodFormatter('{x:,.0f}'))


def _ensure_path(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _create_placeholder_action_chart(action: Dict[str, Any], out_path: Path) -> str:
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.axis('off')
    title = action.get('title') or action.get('play_id') or 'Action'
    notes = [
        "This play is driven by behavioral heuristics rather than window-based KPIs.",
        f"Audience size: {action.get('audience_size', '—')}",
    ]
    if action.get('rationale'):
        notes.append(str(action['rationale']))
    ax.text(
        0.02,
        0.95,
        title,
        ha='left',
        va='top',
        fontsize=14,
        fontweight='bold'
    )
    ax.text(
        0.02,
        0.70,
        '\n'.join(notes),
        ha='left',
        va='top',
        fontsize=11,
        wrap=True
    )
    _ensure_path(out_path)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    return str(out_path)


def create_action_multiwindow_chart(
    action: Dict[str, Any],
    aligned: Dict[str, Any],
    window_weights: Dict[str, float],
    out_dir: Path,
    sequence: int
) -> Optional[str]:
    metric_key = str(action.get('metric') or '').lower()
    metric_info = ACTION_METRIC_MAP.get(metric_key)

    windows = action.get('contributing_windows') or []
    if not windows and action.get('source_window'):
        windows = [action['source_window']]

    ordered_windows: List[str] = []
    seen = set()
    for w in windows:
        if w in aligned and w not in seen:
            ordered_windows.append(w)
            seen.add(w)

    if not ordered_windows:
        out_path = out_dir / f"action_placeholder_{_slugify(action.get('play_id', 'action'))}_{sequence}.png"
        return _create_placeholder_action_chart(action, out_path)

    if not metric_info:
        out_path = out_dir / f"action_no_metric_{_slugify(action.get('play_id', 'action'))}_{sequence}.png"
        return _create_placeholder_action_chart(action, out_path)

    rows = _collect_window_metric_rows(
        aligned,
        ordered_windows,
        metric_info['fields'],
        action.get('window_scores', {}) or {},
    )

    if not rows:
        out_path = out_dir / f"action_no_data_{_slugify(action.get('play_id', 'action'))}_{sequence}.png"
        return _create_placeholder_action_chart(action, out_path)

    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    x = np.arange(len(rows))
    width = 0.35

    recent = [row.get('recent') for row in rows]
    prior = [row.get('prior') for row in rows]

    # Fix 1 (synthetic blocker): matplotlib's bar() raises TypeError when an
    # element is None (common on cold-start / thin-history merchants). Filter
    # None values per-series with a paired x index. Use `is not None`, NOT a
    # truthiness check — zero is a legitimate metric value and must not be
    # dropped. The architectural reorder (V2 ABSTAIN_HARD upstream of chart
    # rendering) is deferred to Phase 6 per the synthetic blocker-fix plan.
    recent_x = [x[i] - width / 2 for i, v in enumerate(recent) if v is not None]
    recent_vals = [v for v in recent if v is not None]
    prior_x = [x[i] + width / 2 for i, v in enumerate(prior) if v is not None]
    prior_vals = [v for v in prior if v is not None]

    if recent_vals:
        ax.bar(recent_x, recent_vals, width, label='Recent', color='#3B82F6')
    if prior_vals:
        ax.bar(prior_x, prior_vals, width, label='Prior', color='#BFDBFE')

    delta_unit = 'pct' if metric_info['unit'] == 'pct' else metric_info['unit']
    for idx, row in enumerate(rows):
        delta = row.get('delta')
        if delta is None or (isinstance(delta, float) and np.isnan(delta)):
            continue
        y_base = max([v for v in [recent[idx], prior[idx]] if v is not None], default=0)
        if metric_info['unit'] != 'pct':
            offset = abs(y_base) * 0.08 if y_base else 0.5
        else:
            offset = 0.04
        ax.text(
            x[idx],
            (y_base + offset) if y_base else offset,
            f"Δ {_format_value(delta, delta_unit)}",
            ha='center',
            va='bottom',
            fontsize=12,
            color='#1f2937',
            fontweight='bold'
        )

    window_weight_subset = {w: window_weights.get(w, 0.0) for w in ordered_windows}
    weighted_recent = _weighted_average(rows, 'recent', window_weight_subset)
    weighted_prior = _weighted_average(rows, 'prior', window_weight_subset)

    _set_axis_formatter(ax, metric_info['unit'])
    ax.set_xticks(x)
    ax.set_xticklabels(ordered_windows, fontsize=12, fontweight='bold')
    ax.set_ylabel(metric_info['label'], fontsize=12)
    ax.tick_params(labelsize=12)
    action_title = action.get('title') or action.get('play_id') or 'Action'
    ax.set_title(f"{action_title} — Multi-Window Evidence", fontsize=16, fontweight='bold', loc='left')
    ax.legend(frameon=True, fontsize=12)
    ax.margins(y=0.18)

    if weighted_recent is not None:
        recent_text = _format_value(weighted_recent, metric_info['unit'])
        if weighted_prior is not None:
            prior_text = _format_value(weighted_prior, metric_info['unit'])
            summary = f"Weighted recent {recent_text} vs prior {prior_text}"
        else:
            summary = f"Weighted recent {recent_text}"
        ax.text(
            0.02,
            0.97,
            summary,
            transform=ax.transAxes,
            ha='left',
            va='top',
            fontsize=12,
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8)
        )

    if any(row.get('p_value') is not None for row in rows):
        pv_text = ", ".join(
            f"{row['window']}: p={row['p_value']:.3f}" if row.get('p_value') is not None else f"{row['window']}: p=—"
            for row in rows
        )
        ax.text(
            0.02,
            0.02,
            pv_text,
            transform=ax.transAxes,
            ha='left',
            va='bottom',
            fontsize=11,
            color='#4B5563'
        )

    out_path = _ensure_path(
        out_dir / (
            f"action_metric_{_slugify(action.get('play_id', 'action'))}_{_slugify(action.get('variant_id', 'base'))}_{sequence}.png"
        )
    )
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches='tight')
    plt.close(fig)
    return str(out_path)


def _flatten_actions(actions: Any) -> List[Dict[str, Any]]:
    if actions is None:
        return []
    if isinstance(actions, list):
        return actions
    flattened: List[Dict[str, Any]] = []
    seen_ids: set[int] = set()
    if isinstance(actions, dict):
        for key in ACTION_COLLECTION_KEYS:
            items = actions.get(key)
            if not isinstance(items, list):
                continue
            for item in items:
                if id(item) in seen_ids:
                    continue
                flattened.append(item)
                seen_ids.add(id(item))
    return flattened

def repurchase_curve_chart(g: pd.DataFrame, aligned: dict, out_path: str) -> str:
    """
    Shows customer repurchase timeline - critical for Beauty
    Highlights the 21-45 day winback window and 60-120 dormant period
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Calculate days since last purchase distribution
    if 'days_since_last' in g.columns:
        days = g['days_since_last'].dropna()
        
        # Create bins for visualization
        bins = [0, 7, 14, 21, 30, 45, 60, 90, 120, 180, 365]
        labels = ['0-7', '8-14', '15-21', '22-30', '31-45', '46-60', '61-90', '91-120', '121-180', '180+']
        
        # Categorize and count
        binned = pd.cut(days, bins=bins, labels=labels, include_lowest=True)
        counts = binned.value_counts().sort_index()
        
        # Create bar chart with action zones highlighted
        colors = []
        for label in counts.index:
            if label in ['22-30', '31-45']:  # Winback zone
                colors.append('#3b82f6')  # Blue - primary action
            elif label in ['61-90', '91-120']:  # Dormant zone
                colors.append('#f59e0b')  # Amber - secondary action
            else:
                colors.append('#e5e7eb')  # Gray - neutral
        
        bars = ax.bar(range(len(counts)), counts.values, color=colors)
        ax.set_xticks(range(len(counts)))
        ax.set_xticklabels(counts.index, rotation=45, ha='right')
        
        # Add action zone annotations
        ax.axvspan(2.5, 4.5, alpha=0.1, color='blue', label='Winback Zone')
        ax.axvspan(6.5, 7.5, alpha=0.1, color='orange', label='Dormant Zone')
        
        # Styling
        ax.set_xlabel('Days Since Last Purchase', fontsize=11)
        ax.set_ylabel('Number of Customers', fontsize=11)
        ax.set_title('Customer Repurchase Timeline & Action Zones', fontsize=13, fontweight='bold')
        ax.legend(loc='upper right', frameon=True, fancybox=True)
        
        # Add insight text
        total = float(counts.sum())
        winback_base = float(counts.get('22-30', 0) + counts.get('31-45', 0))
        winback_pct = (winback_base / total * 100.0) if total > 0 else 0.0
        ax.text(0.02, 0.98, f'{winback_pct:.0f}% in winback zone', 
                transform=ax.transAxes, fontsize=10, va='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    else:
        # Fallback if no days_since_last data
        ax.text(
            0.5,
            0.5,
            "Repurchase timeline needs 'days_since_last' (derived from Created at + Customer Email/customer_id)",
            ha='center', va='center', transform=ax.transAxes, wrap=True
        )
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches='tight')
    plt.close()
    return out_path


def product_velocity_chart(g: pd.DataFrame, aligned: dict, out_path: str, df: Optional[pd.DataFrame] = None) -> str:
    """
    Enhanced version with replenishment cycle detection.
    Top-left: product velocity; Top-right: product repeat rates;
    Bottom-left: replenishment cycles; Bottom-right: subscription readiness.
    """
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
    
    top_index = []
    if 'Created at' in g.columns:
        # Calculate product velocity (units per month)
        g['Created at'] = pd.to_datetime(g['Created at'])
        recent_30 = g[g['Created at'] >= g['Created at'].max() - pd.Timedelta(days=30)]
        # Top products by volume (prefer raw line items if available)
        if df is not None and all(c in df.columns for c in ['Lineitem name','Lineitem quantity','Created at']):
            d = df.copy()
            d['Created at'] = pd.to_datetime(d['Created at'], errors='coerce')
            recent_li = d[d['Created at'] >= d['Created at'].max() - pd.Timedelta(days=30)]
            # Choose identity column dynamically for customer counts
            id_col = 'Customer Email' if 'Customer Email' in recent_li.columns else ('customer_id' if 'customer_id' in recent_li.columns else None)
            if id_col is not None:
                product_counts = recent_li.groupby('Lineitem name').agg({
                    'Lineitem quantity': 'sum',
                    id_col: 'nunique'
                }).rename(columns={id_col: 'customers'}).sort_values('Lineitem quantity', ascending=False).head(8)
            else:
                product_counts = recent_li.groupby('Lineitem name').agg({
                    'Lineitem quantity': 'sum'
                }).sort_values('Lineitem quantity', ascending=False).head(8)
            top_index = product_counts.index
        elif 'lineitem_any' in g.columns:
            product_counts = recent_30.groupby('lineitem_any').agg({
                'units_per_order': 'sum',
                'customer_id': 'nunique'
            }).sort_values('units_per_order', ascending=False).head(8)
            top_index = product_counts.index
        else:
            product_counts = pd.DataFrame()
            top_index = []
        
        # Chart 1: Product velocity
        if df is not None and 'Lineitem quantity' in product_counts.columns:
            units = product_counts['Lineitem quantity'].values
        else:
            units = product_counts['units_per_order'].values if 'units_per_order' in product_counts.columns else []
        products = [str(p)[:15] + '...' if len(str(p)) > 15 else str(p) for p in top_index]
        
        bars1 = ax1.barh(range(len(products)), units, color='#8b5cf6')
        ax1.set_yticks(range(len(products)))
        ax1.set_yticklabels(products)
        ax1.set_xlabel('Units Sold (30 days)', fontsize=11)
        ax1.set_title('Top Products by Velocity', fontsize=12, fontweight='bold')
        
        # Add values on bars
        for i, (bar, val) in enumerate(zip(bars1, units)):
            ax1.text(val, bar.get_y() + bar.get_height()/2, f'{int(val)}', 
                    ha='left', va='center', fontsize=9, color='black')
        
        # Chart 2: Repeat purchase rate by product
        # Compute repeat rates for top 5 products
        repeat_rates = []
        # Use email or customer_id for repeat rate computation
        id_col = None
        if df is not None:
            if 'Customer Email' in df.columns:
                id_col = 'Customer Email'
            elif 'customer_id' in df.columns:
                id_col = 'customer_id'
        if df is not None and id_col is not None and all(c in df.columns for c in ['Lineitem name','Name','Created at']):
            d_all = df.copy()
            d_all['Created at'] = pd.to_datetime(d_all['Created at'], errors='coerce')
            # Use a 180-day horizon to measure repeats; adjust if needed
            horizon_start = d_all['Created at'].max() - pd.Timedelta(days=180)
            d_win = d_all[d_all['Created at'] >= horizon_start]
            for product in list(top_index)[:5]:
                sub = d_win[d_win['Lineitem name'] == product]
                # Count unique orders per customer for this product
                per_cust_orders = sub.groupby(id_col)['Name'].nunique()
                if per_cust_orders.shape[0] == 0:
                    rr = 0.0
                else:
                    rr = float((per_cust_orders > 1).mean() * 100.0)
                repeat_rates.append(rr)
        elif 'lineitem_any' in g.columns:
            # Fallback to order-level proxy (less accurate)
            for product in list(top_index)[:5]:
                product_customers = g[g['lineitem_any'] == product]['customer_id'].value_counts()
                repeat_rate = (product_customers > 1).mean() * 100 if product_customers.shape[0] > 0 else 0.0
                repeat_rates.append(float(repeat_rate))
        else:
            repeat_rates = [0.0] * min(5, len(top_index))
        
        colors2 = ['#10b981' if r > 30 else '#f59e0b' if r > 20 else '#ef4444' 
                  for r in repeat_rates]
        
        bars2 = ax2.bar(range(len(repeat_rates)), repeat_rates, color=colors2)
        ax2.set_xticks(range(len(repeat_rates)))
        ax2.set_xticklabels([str(p)[:10] + '...' if len(str(p)) > 10 else str(p) 
                             for p in list(top_index)[:5]], rotation=45, ha='right')
        ax2.set_ylabel('Repeat Purchase Rate (%)', fontsize=11)
        ax2.set_title('Subscription Potential', fontsize=12, fontweight='bold')
        ax2.axhline(y=30, color='gray', linestyle='--', alpha=0.5, label='Good for subscription')
        ax2.legend(loc='upper right', fontsize=9)
        
        # Add values on bars
        for bar, val in zip(bars2, repeat_rates):
            ax2.text(bar.get_x() + bar.get_width()/2, val + 1, f'{val:.0f}%', 
                    ha='center', va='bottom', fontsize=9)
    
    else:
        ax1.text(0.5, 0.5, 'No product data available', 
                ha='center', va='center', transform=ax1.transAxes)
        ax2.axis('off')

    # NEW: ax3 - Replenishment Cycles by Product
    try:
        if df is not None and 'Lineitem name' in df.columns and 'Created at' in df.columns:
            dfx = df.copy()
            dfx['Created at'] = pd.to_datetime(dfx['Created at'], errors='coerce')
            id_col = 'Customer Email' if 'Customer Email' in dfx.columns else ('customer_id' if 'customer_id' in dfx.columns else None)
            group_keys = [id_col, 'Lineitem name'] if id_col is not None else ['Lineitem name']
            grp = dfx.dropna(subset=['Created at']).groupby(group_keys)['Created at'].apply(list)

            replenishment_data = []
            for key, dates in grp.items():
                # key may be a tuple (customer, product) or just product if id_col missing
                product = key[1] if isinstance(key, tuple) else key
                if len(dates) > 1:
                    dates_sorted = sorted(pd.to_datetime(dates))
                    intervals = [(dates_sorted[i+1] - dates_sorted[i]).days for i in range(len(dates_sorted)-1)]
                    if intervals:
                        replenishment_data.append({
                            'product': product,
                            'median_days': float(np.median(intervals)),
                            'std_days': float(np.std(intervals))
                        })

            if replenishment_data:
                repl_df = pd.DataFrame(replenishment_data)
                top_products_repl = repl_df.groupby('product').agg({
                    'median_days': 'median',
                    'std_days': 'mean'
                }).sort_values('median_days').head(10)

                y_pos = range(len(top_products_repl))
                ax3.barh(y_pos, top_products_repl['median_days'],
                         xerr=top_products_repl['std_days'],
                         color='#6366f1', alpha=0.7)
                ax3.set_yticks(y_pos)
                ax3.set_yticklabels([str(p)[:20] for p in top_products_repl.index])
                ax3.set_xlabel('Days Between Purchases')
                ax3.set_title('Product Replenishment Cycles', fontweight='bold')
                ax3.axvline(x=30, color='red', linestyle='--', alpha=0.5, label='Monthly')
                ax3.axvline(x=60, color='orange', linestyle='--', alpha=0.5, label='Bi-monthly')
                ax3.legend()
            else:
                ax3.text(0.5, 0.5, 'Insufficient replenishment data', ha='center', va='center', transform=ax3.transAxes)
        else:
            ax3.text(0.5, 0.5, 'Raw line-item data required', ha='center', va='center', transform=ax3.transAxes)
    except Exception as e:
        ax3.text(0.5, 0.5, f'Error computing cycles: {e}', ha='center', va='center', transform=ax3.transAxes)

    # NEW: ax4 - Subscription Readiness Score
    try:
        subscription_scores: List[float] = []
        prod_labels: List[str] = []
        if df is not None and 'Lineitem name' in df.columns and 'Created at' in df.columns:
            dfx2 = df.copy()
            dfx2['Created at'] = pd.to_datetime(dfx2['Created at'], errors='coerce')
            # Determine identity and order columns
            id_col_sr = 'Customer Email' if 'Customer Email' in dfx2.columns else ('customer_id' if 'customer_id' in dfx2.columns else None)
            order_col_sr = 'Name' if 'Name' in dfx2.columns else ('order_id' if 'order_id' in dfx2.columns else None)
            if id_col_sr is not None and order_col_sr is not None:
                for product in list(top_index)[:5]:
                    product_data = dfx2[dfx2['Lineitem name'] == product]
                    if product_data.empty:
                        continue
                    # Repeat rate based on unique orders per customer for this product
                    repeat_rate = float((product_data.groupby(id_col_sr)[order_col_sr].nunique() > 1).mean())
                    intervals: List[float] = []
                    customers_iter = product_data[id_col_sr].dropna().unique()
                    for customer in customers_iter:
                        cust_dates = pd.to_datetime(product_data[product_data[id_col_sr] == customer]['Created at']).dropna()
                        if cust_dates.shape[0] > 1:
                            cust_intervals = cust_dates.sort_values().diff().dt.days.dropna()
                            intervals.extend(cust_intervals.tolist())
                    if intervals and np.mean(intervals) > 0:
                        consistency = 1 - (np.std(intervals) / np.mean(intervals))
                        consistency = float(max(0.0, min(1.0, consistency)))
                    else:
                        consistency = 0.0
                    score = (repeat_rate * 0.6 + consistency * 0.4) * 100.0
                    subscription_scores.append(float(score))
                    prod_labels.append(str(product))
        colors4 = ['#10b981' if s > 60 else '#f59e0b' if s > 40 else '#ef4444' for s in subscription_scores]
        ax4.bar(range(len(subscription_scores)), subscription_scores, color=colors4)
        ax4.set_xticks(range(len(subscription_scores)))
        ax4.set_xticklabels([str(p)[:12] for p in prod_labels], rotation=45, ha='right')
        ax4.set_ylabel('Subscription Readiness Score')
        ax4.set_title('Products Ready for Subscription', fontweight='bold')
        ax4.axhline(y=60, color='green', linestyle='--', alpha=0.5, label='Ready')
        ax4.axhline(y=40, color='orange', linestyle='--', alpha=0.5, label='Maybe')
        ax4.legend()
    except Exception as e:
        ax4.text(0.5, 0.5, f'Error computing readiness: {e}', ha='center', va='center', transform=ax4.transAxes)
    
    plt.suptitle('Product Performance & Subscription Opportunities', fontsize=14, fontweight='bold', y=0.99)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches='tight')
    plt.close()
    return out_path


def product_performance_compact_chart(g: pd.DataFrame, aligned: dict, out_path: str,
                                      df: Optional[pd.DataFrame] = None,
                                      top_n: int = 5) -> str:
    """
    Compact Product Performance chart: focuses on the two highest-signal visuals.
    Left: Top products by 30D velocity (units). Right: Subscription readiness score.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Compute top products by 30D units
    top_index = []
    units = []
    try:
        if df is not None and all(c in df.columns for c in ['Lineitem name','Lineitem quantity','Created at']):
            d = df.copy(); d['Created at'] = pd.to_datetime(d['Created at'], errors='coerce')
            recent_li = d[d['Created at'] >= d['Created at'].max() - pd.Timedelta(days=30)]
            product_counts = recent_li.groupby('Lineitem name').agg({'Lineitem quantity': 'sum'})
            product_counts = product_counts.sort_values('Lineitem quantity', ascending=False).head(top_n)
            top_index = product_counts.index.tolist()
            units = product_counts['Lineitem quantity'].tolist()
        elif 'Created at' in g.columns and 'lineitem_any' in g.columns and 'units_per_order' in g.columns:
            gg = g.copy(); gg['Created at'] = pd.to_datetime(gg['Created at'], errors='coerce')
            recent_30 = gg[gg['Created at'] >= gg['Created at'].max() - pd.Timedelta(days=30)]
            product_counts = recent_30.groupby('lineitem_any')['units_per_order'].sum().sort_values(ascending=False).head(top_n)
            top_index = product_counts.index.tolist(); units = product_counts.values.tolist()
    except Exception:
        pass

    # Left panel: velocity
    products = [str(p)[:18] + '…' if len(str(p)) > 18 else str(p) for p in top_index]
    ax1.barh(range(len(products)), units, color='#6366f1')
    ax1.set_yticks(range(len(products)))
    ax1.set_yticklabels(products)
    ax1.invert_yaxis()
    ax1.set_xlabel('Units (30 days)')
    ax1.set_title('Top Products by Velocity', fontsize=12, fontweight='bold')

    # Right panel: subscription readiness (repeat + consistency proxy)
    subscription_scores: List[float] = []
    prod_labels: List[str] = []
    if df is not None and 'Lineitem name' in df.columns and 'Created at' in df.columns:
        dfx2 = df.copy(); dfx2['Created at'] = pd.to_datetime(dfx2['Created at'], errors='coerce')
        id_col_comp = 'Customer Email' if 'Customer Email' in dfx2.columns else ('customer_id' if 'customer_id' in dfx2.columns else None)
        order_col_comp = 'Name' if 'Name' in dfx2.columns else ('order_id' if 'order_id' in dfx2.columns else None)
        if id_col_comp is not None and order_col_comp is not None:
            for product in list(top_index)[:top_n]:
                product_data = dfx2[dfx2['Lineitem name'] == product]
                if product_data.empty:
                    continue
                repeat_rate = float((product_data.groupby(id_col_comp)[order_col_comp].nunique() > 1).mean())
                intervals: List[float] = []
                customers_iter = product_data[id_col_comp].dropna().unique()
                for customer in customers_iter:
                    cust_dates = pd.to_datetime(product_data[product_data[id_col_comp] == customer]['Created at']).dropna()
                    if cust_dates.shape[0] > 1:
                        cust_intervals = cust_dates.sort_values().diff().dt.days.dropna()
                        intervals.extend(cust_intervals.tolist())
                if intervals and np.mean(intervals) > 0:
                    consistency = 1 - (np.std(intervals) / np.mean(intervals))
                    consistency = float(max(0.0, min(1.0, consistency)))
                else:
                    consistency = 0.0
                score = (repeat_rate * 0.6 + consistency * 0.4) * 100.0
                subscription_scores.append(float(score))
                prod_labels.append(str(product))
    colors = ['#10b981' if s > 60 else '#f59e0b' if s > 40 else '#ef4444' for s in subscription_scores]
    ax2.bar(range(len(subscription_scores)), subscription_scores, color=colors)
    ax2.set_xticks(range(len(subscription_scores)))
    ax2.set_xticklabels([str(p)[:12] + ('…' if len(str(p))>12 else '') for p in prod_labels], rotation=45, ha='right')
    ax2.set_ylabel('Readiness Score')
    ax2.set_title('Subscription Readiness', fontsize=12, fontweight='bold')
    ax2.axhline(y=60, color='green', linestyle='--', alpha=0.4)
    ax2.axhline(y=40, color='orange', linestyle='--', alpha=0.3)

    plt.suptitle('Product Performance (Compact)', fontsize=13, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches='tight')
    plt.close()
    return out_path


def customer_value_segments_chart(g: pd.DataFrame, aligned: dict, out_path: str) -> str:
    """
    RFM-style segmentation showing where value sits
    Helps justify winback and VIP actions
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    if g is None or g.empty:
        ax.text(0.5, 0.5, 'Insufficient data for segmentation',
                ha='center', va='center', transform=ax.transAxes)
        plt.tight_layout()
        plt.savefig(out_path, dpi=120, bbox_inches='tight')
        plt.close()
        return out_path

    df = g.copy()
    column_lookup = {str(col).strip().lower(): col for col in df.columns}

    def resolve_column(options: List[str]) -> Optional[str]:
        for opt in options:
            resolved = column_lookup.get(opt.lower())
            if resolved is not None:
                return resolved
        return None

    id_col = resolve_column([
        'customer_id', 'customer id', 'customer_email', 'customer email',
        'email', 'shopify_customer_id', 'customer'
    ])
    created_col = resolve_column([
        'created at', 'created_at', 'order_created_at', 'order created at',
        'order date', 'order_date', 'processed at', 'processed_at', 'date'
    ])

    if not id_col or not created_col:
        ax.text(0.5, 0.5, 'Insufficient data for segmentation',
                ha='center', va='center', transform=ax.transAxes)
        plt.tight_layout()
        plt.savefig(out_path, dpi=120, bbox_inches='tight')
        plt.close()
        return out_path

    df[created_col] = pd.to_datetime(df[created_col], errors='coerce')
    df = df.dropna(subset=[created_col])
    if df.empty:
        ax.text(0.5, 0.5, 'Insufficient data for segmentation',
                ha='center', va='center', transform=ax.transAxes)
        plt.tight_layout()
        plt.savefig(out_path, dpi=120, bbox_inches='tight')
        plt.close()
        return out_path

    order_id_col = resolve_column([
        'name', 'order_name', 'order id', 'order_id', 'order number', 'order_number'
    ])

    value_candidates = [
        'aov', 'net_sales', 'net sale', 'subtotal', 'sub_total', 'total', 'total price',
        'total_price', 'gross_sales', 'gross sale', 'order_amount', 'order amount',
        'revenue', 'sales', 'amount'
    ]
    value_col = resolve_column(value_candidates)

    if value_col:
        df[value_col] = pd.to_numeric(df[value_col], errors='coerce')

    if value_col is None or df[value_col].dropna().empty:
        fallback_aov = None
        aligned_dict = aligned if isinstance(aligned, dict) else {}
        for window in ['L28', 'L56', 'L90']:
            block = aligned_dict.get(window) or {}
            window_aov = block.get('aov') or block.get('AOV')
            if window_aov:
                fallback_aov = float(window_aov)
                break
        if fallback_aov is not None:
            df['__fallback_value'] = float(fallback_aov)
            value_col = '__fallback_value'
        else:
            ax.text(0.5, 0.5, 'Insufficient data for segmentation',
                    ha='center', va='center', transform=ax.transAxes)
            plt.tight_layout()
            plt.savefig(out_path, dpi=120, bbox_inches='tight')
            plt.close()
            return out_path

    if order_id_col:
        order_level = df.drop_duplicates(subset=[order_id_col]).copy()
        order_counts = df.groupby(id_col)[order_id_col].nunique()
    else:
        order_level = df.drop_duplicates(subset=[id_col, created_col]).copy()
        order_counts = order_level.groupby(id_col).size()

    last_order = df.groupby(id_col)[created_col].max()
    avg_values = order_level.groupby(id_col)[value_col].mean().dropna()

    customer_summary = pd.DataFrame({
        'order_count': order_counts,
        'last_order': last_order,
        'AOV': avg_values
    }).dropna(subset=['AOV'])

    if customer_summary.empty:
        ax.text(0.5, 0.5, 'Insufficient data for segmentation',
                ha='center', va='center', transform=ax.transAxes)
        plt.tight_layout()
        plt.savefig(out_path, dpi=120, bbox_inches='tight')
        plt.close()
        return out_path

    max_date = customer_summary['last_order'].max()
    customer_summary['recency_days'] = (max_date - customer_summary['last_order']).dt.days

    def segment_customers(row):
        if row['order_count'] >= 3 and row['recency_days'] <= 30:
            return 'Champions'
        elif row['order_count'] >= 3 and row['recency_days'] <= 90:
            return 'Loyal'
        elif row['order_count'] == 1 and row['recency_days'] <= 30:
            return 'New'
        elif row['order_count'] >= 2 and row['recency_days'] > 60:
            return 'At Risk'
        elif row['recency_days'] > 90:
            return 'Lost'
        else:
            return 'Developing'

    customer_summary['segment'] = customer_summary.apply(segment_customers, axis=1)

    segment_stats = customer_summary.groupby('segment').agg({
        'AOV': 'mean',
        'order_count': 'count'
    }).rename(columns={'order_count': 'count'})

    segment_stats['total_value'] = segment_stats['AOV'] * segment_stats['count']
    segment_stats = segment_stats.sort_values('total_value', ascending=True)

    if segment_stats.empty:
        ax.text(0.5, 0.5, 'Insufficient data for segmentation',
                ha='center', va='center', transform=ax.transAxes)
        plt.tight_layout()
        plt.savefig(out_path, dpi=120, bbox_inches='tight')
        plt.close()
        return out_path

    colors_map = {
        'Champions': '#10b981',
        'Loyal': '#3b82f6',
        'At Risk': '#f59e0b',
        'Lost': '#ef4444',
        'New': '#8b5cf6',
        'Developing': '#6b7280'
    }

    colors = [colors_map.get(seg, '#6b7280') for seg in segment_stats.index]
    ax.barh(range(len(segment_stats)), segment_stats['total_value'], color=colors)

    for i, (idx, row) in enumerate(segment_stats.iterrows()):
        ax.text(row['total_value'], i, f" ${row['total_value']:.0f}",
               va='center', fontsize=11, fontweight='bold')
        ax.text(0, i, f"{idx} ({row['count']:.0f})",
               ha='right', va='center', fontsize=11, fontweight='bold')

    ax.set_yticks([])
    ax.set_xlabel('Total Segment Value ($)', fontsize=12)
    ax.set_title('Customer Value Segments — Where to Focus', fontsize=14, fontweight='bold')

    if 'At Risk' in segment_stats.index:
        at_risk_count = segment_stats.loc['At Risk', 'count']
        ax.text(0.98, 0.02, f'🎯 {at_risk_count:.0f} customers need winback',
               transform=ax.transAxes, ha='right', fontsize=11,
               bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.25))
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches='tight')
    plt.close()
    return out_path


def action_impact_forecast_chart(actions: List[Dict], aligned: dict, out_path: str, chosen_window: Optional[str] = None) -> str:
    """
    Shows expected impact of recommended actions
    Makes the "why" clear visually
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    
    if actions and len(actions) > 0:
        # Determine monthly baseline and leave action impacts in monthly units
        cw = (chosen_window or '').upper()
        if cw == 'L7':
            # Approximate month as 4x L7
            baseline_monthly = float(aligned.get('L7', {}).get('net_sales') or 0.0) * 4.0
            baseline_label = '4× L7 (monthly)'
        elif cw == 'L56':
            # 56d ~ 8 weeks ~ 2 months; use L56 directly but scale to monthly
            base_window = aligned.get('L56', {})
            baseline_monthly = float((base_window.get('net_sales') or 0.0)) / 2.0
            baseline_label = 'L56 ÷ 2 (monthly)'
        else:
            # Default: L28 is already ~monthly
            base_window = aligned.get('L28', {})
            baseline_monthly = float(base_window.get('net_sales') or 0.0)
            baseline_label = 'L28 (monthly)'
        
        # Build cumulative impact (adjusted for diminishing returns and channel overlap)
        action_names = []
        impacts = [baseline_monthly]
        cumulative = baseline_monthly
        used_channels = set()
        # Position-based diminishing schedule (top 3)
        pos_schedule = [1.00, 0.90, 0.80]
        # Global portfolio cap to avoid overstating combined lift
        portfolio_cap = 0.50 * baseline_monthly if baseline_monthly > 0 else float('inf')
        
        for idx, action in enumerate(actions[:3]):  # Top 3 actions
            # expected_$ has been scaled to monthly in the engine
            expected = float(action.get('expected_$', 0) or 0.0)

            # Channel-overlap interference: penalize by prior-used channel overlap
            chans = set()
            try:
                meta_ch = action.get('channels') or []
                if isinstance(meta_ch, dict):
                    # if structured, take keys truthy
                    meta_ch = [k for k, v in meta_ch.items() if v]
                chans = set(str(c).lower() for c in meta_ch)
            except Exception:
                chans = set()
            overlap = len(chans & used_channels)
            channel_factor = (0.90 ** overlap) if overlap > 0 else 1.0

            # Position-based diminishing factor
            pos_factor = pos_schedule[idx] if idx < len(pos_schedule) else 0.75

            adjusted = expected * channel_factor * pos_factor

            # Apply portfolio cap across combined lifts
            current_lift = cumulative - baseline_monthly
            remaining_cap = portfolio_cap - current_lift
            if remaining_cap < float('inf'):
                adjusted = max(0.0, min(adjusted, remaining_cap))

            cumulative += adjusted
            impacts.append(cumulative)
            
            # Shorten action names
            name = action.get('title', 'Unknown')
            if len(name) > 20:
                name = name[:17] + '...'
            action_names.append(name)

            # Accumulate used channels for interference on subsequent actions
            used_channels |= chans
        
        # Create waterfall chart
        x = range(len(impacts))
        
        # Baseline bar
        ax.bar(0, baseline_monthly, color='#6b7280', label=f'Baseline ({baseline_label})')
        
        # Action bars (stacked)
        bottom = baseline_monthly
        colors = ['#3b82f6', '#10b981', '#8b5cf6']
        for i, (name, impact) in enumerate(zip(action_names, impacts[1:])):
            height = impact - bottom
            ax.bar(i+1, height, bottom=bottom, color=colors[i % 3], label=name)
            
            # Add impact label
            ax.text(i+1, bottom + height/2, f'+${height:.0f}', 
                   ha='center', va='center', fontsize=10, fontweight='bold', color='white')
            
            bottom = impact
        
        # Styling
        ax.set_xticks(x)
        ax.set_xticklabels(['Current'] + [f'+ Action {i+1}' for i in range(len(action_names))])
        ax.set_ylabel('Expected Monthly Revenue ($)', fontsize=11)
        ax.set_title('Revenue Impact Forecast - This Month\'s Actions', fontsize=13, fontweight='bold')
        # Clarify units and interaction assumptions
        ax.text(0.5, -0.12, f'Units: monthly. Baseline source: {baseline_label}. Combined impact adjusted for channel overlap and diminishing returns; capped at 50% of baseline.',
                transform=ax.transAxes, ha='center', va='top', fontsize=9, color='#6b7280')
        
        # Add total impact annotation
        total_lift = impacts[-1] - baseline_monthly
        lift_pct = (total_lift / baseline_monthly * 100) if baseline_monthly > 0 else 0
        ax.text(0.98, 0.98, f'Total Expected Lift: +${total_lift:.0f} ({lift_pct:.1f}%)', 
               transform=ax.transAxes, ha='right', va='top', fontsize=11,
               bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))
        
        ax.legend(loc='upper left', frameon=True, fancybox=True)
        ax.grid(axis='y', alpha=0.3)
    
    else:
        ax.text(0.5, 0.5, 'No actions to forecast', 
                ha='center', va='center', transform=ax.transAxes)
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches='tight')
    plt.close()
    return out_path


def stock_vs_demand_chart(inventory_metrics: pd.DataFrame, out_path: str, top_n: int = 10) -> str:
    """Visualize stock (available_net) vs projected monthly demand for top SKUs by velocity.
    - Colors indicate coverage: green (>=28d), amber (14-28d), red (<14d).
    - Adds shortfall labels where demand exceeds stock.
    Expects columns: sku, product, available_net, daily_velocity, cover_days.
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    try:
        inv = inventory_metrics.copy()
        if inv is None or inv.empty:
            ax.text(0.5, 0.5, 'No inventory data', ha='center', va='center', transform=ax.transAxes)
        else:
            # Compute projected monthly demand (28 days)
            inv['proj_demand'] = pd.to_numeric(inv.get('daily_velocity', 0), errors='coerce').fillna(0) * 28.0
            inv['available_net'] = pd.to_numeric(inv.get('available_net', 0), errors='coerce').fillna(0)
            inv['cover_days'] = pd.to_numeric(inv.get('cover_days', np.inf), errors='coerce')
            # Top by highest projected demand
            top = inv.sort_values('proj_demand', ascending=False).head(top_n).copy()
            labels = [str(x)[:18] + ('…' if len(str(x))>18 else '') for x in (top.get('product').fillna(top.get('sku')))]
            x = np.arange(len(top))
            width = 0.4
            bars1 = ax.bar(x - width/2, top['available_net'], width=width, label='Available (net)', color='#10b981')
            bars2 = ax.bar(x + width/2, top['proj_demand'], width=width, label='Projected Demand (28d)', color='#3b82f6')
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.set_ylabel('Units')
            ax.set_title('Stock vs Projected Monthly Demand (Top SKUs)', fontsize=13, fontweight='bold')
            ax.legend()
            # Coverage color markers atop bars
            for i, (cv, an, dm) in enumerate(zip(top['cover_days'], top['available_net'], top['proj_demand'])):
                color = '#10b981' if cv >= 28 else ('#f59e0b' if cv >= 14 else '#ef4444')
                ax.plot([x[i], x[i]], [max(an, dm) * 1.02, max(an, dm) * 1.06], color=color, linewidth=4)
                # Shortfall annotation
                if dm > an:
                    short = float(dm - an)
                    ax.text(x[i] + width/2, dm + max(1.0, dm*0.02), f'-{int(short)}', ha='center', va='bottom', fontsize=9, color='#ef4444')
            ax.margins(y=0.2)
    except Exception as e:
        ax.text(0.5, 0.5, f'Error: {e}', ha='center', va='center', transform=ax.transAxes)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches='tight')
    plt.close()
    return out_path


def cohort_retention_chart(df: pd.DataFrame, out_path: str) -> str:
    """
    Shows cohort retention — essential for Beauty/Supplements LTV.
    Left: monthly cohort retention heatmap (last 6 cohorts, first 6 months).
    Right: average retention curve (first 12 months).
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    try:
        required_any_id = ['Customer Email', 'customer_id']
        required_common = ['Created at']
        if df is not None and all(c in df.columns for c in required_common) and any(c in df.columns for c in required_any_id):
            d = df.copy()
            d['Created at'] = pd.to_datetime(d['Created at'], errors='coerce')
            d = d.dropna(subset=['Created at'])
            if d.empty:
                raise ValueError('no dates')

            # Use email if available; else customer_id
            id_col = 'Customer Email' if 'Customer Email' in d.columns else 'customer_id'
            # First purchase (cohort) per customer
            first = d.groupby(id_col)['Created at'].min().reset_index()
            first.columns = [id_col, 'cohort_date']
            first['cohort'] = first['cohort_date'].dt.to_period('M')
            dc = d.merge(first, on=id_col, how='left')
            dc['order_month'] = dc['Created at'].dt.to_period('M')
            # Months since first purchase as integer (robust to pandas period arithmetic)
            try:
                dc['months_since'] = (dc['order_month'].astype(int) - dc['cohort'].astype(int)).astype(int)
            except Exception:
                # Fallback: compute via start-of-month timestamps
                om_start = dc['order_month'].dt.start_time
                co_start = dc['cohort'].dt.start_time
                dc['months_since'] = ((om_start.dt.year - co_start.dt.year) * 12 + (om_start.dt.month - co_start.dt.month)).astype(int)

            # Retention matrix
            ret = dc.groupby(['cohort', 'months_since'])[id_col].nunique().reset_index()
            cohort_sizes = dc.groupby('cohort')[id_col].nunique()
            ret = ret.merge(cohort_sizes.rename('cohort_size'), left_on='cohort', right_index=True)
            # Use the same ID column for counts to avoid KeyError on 'Customer Email'
            ret['retention_rate'] = ret[id_col] / ret['cohort_size']

            pivot = ret.pivot(index='cohort', columns='months_since', values='retention_rate').fillna(0.0)

            # Heatmap: last 6 cohorts, first 6 months
            rows = list(pivot.index)[-6:]
            # Ensure integer-like month offsets
            def _to_int_safe(x):
                try:
                    return int(x)
                except Exception:
                    return None
            cols = [c for c in pivot.columns if (_to_int_safe(c) is not None and 0 <= _to_int_safe(c) <= 5)]
            data = pivot.loc[rows, cols] if rows else pivot.iloc[[], :]

            if sns is not None and not data.empty:
                sns.heatmap(data, annot=True, fmt='.0%', cmap='YlOrRd', ax=ax1, vmin=0, vmax=1)
                ax1.set_title('Monthly Cohort Retention', fontweight='bold')
                ax1.set_xlabel('Months Since First Purchase')
                ax1.set_ylabel('Cohort')
            else:
                # Fallback simple image
                if data.empty:
                    ax1.text(0.5, 0.5, 'Insufficient cohort data', ha='center', va='center', transform=ax1.transAxes)
                else:
                    im = ax1.imshow(data.values, aspect='auto', cmap='YlOrRd', vmin=0, vmax=1)
                    ax1.set_xticks(range(len(data.columns))); ax1.set_xticklabels(data.columns)
                    ax1.set_yticks(range(len(data.index))); ax1.set_yticklabels([str(i) for i in data.index])
                    ax1.set_title('Monthly Cohort Retention', fontweight='bold')
                    fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)

            # Average retention curve (first 12 months)
            avg_ret = pivot.mean(axis=0)
            xs = []
            ys = []
            for c, v in avg_ret.items():
                ci = _to_int_safe(c)
                if ci is not None and 0 <= ci <= 11:
                    xs.append(ci)
                    ys.append(float(v) * 100.0)
            xs, ys = (list(zip(*sorted(zip(xs, ys)))) if xs else ([], []))
            ax2.plot(xs, ys, marker='o', linewidth=2, markersize=6, color='#6366f1')
            ax2.fill_between(xs, [0]*len(xs), ys, alpha=0.25, color='#6366f1')
            ax2.set_xlabel('Months Since First Purchase')
            ax2.set_ylabel('Average Retention Rate (%)')
            ax2.set_title('Average Retention Curve', fontweight='bold')
            ax2.grid(True, alpha=0.3)
            ax2.axhline(y=20, color='red', linestyle='--', alpha=0.5, label='Industry Avg')
            ax2.axhline(y=30, color='green', linestyle='--', alpha=0.5, label='Good')
            ax2.legend()

            for month in [1, 3, 6]:
                if month in xs:
                    val = ys[xs.index(month)]
                    ax2.annotate(f'{val:.0f}%', xy=(month, val), xytext=(month, val + 5), ha='center', fontweight='bold')
        else:
            missing = []
            if df is not None:
                if 'Created at' not in df.columns:
                    missing.append('Created at')
                if ('Customer Email' not in df.columns) and ('customer_id' not in df.columns):
                    missing.append('Customer Email or customer_id')
            msg = 'Missing columns: ' + ', '.join(missing) if missing else 'Missing required columns'
            ax1.text(0.5, 0.5, f"{msg}. Use exact column names.", ha='center', va='center', transform=ax1.transAxes, wrap=True)
            ax2.axis('off')
    except Exception as e:
        ax1.text(0.5, 0.5, f'Error: {e}', ha='center', va='center', transform=ax1.transAxes)
        ax2.axis('off')

    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches='tight')
    plt.close()
    return out_path


def first_to_second_purchase_chart(df: pd.DataFrame, out_path: str) -> str:
    """
    Critical for Beauty: Shows time to second purchase and conversion rate.
    Left: distribution of days to second purchase with median.
    Right: simple funnel of 2+ and 3+ orders.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    try:
        id_col = 'Customer Email' if (df is not None and 'Customer Email' in df.columns) else ('customer_id' if (df is not None and 'customer_id' in df.columns) else None)
        order_col = 'order_id' if (df is not None and 'order_id' in df.columns) else ('Name' if (df is not None and 'Name' in df.columns) else None)
        if df is not None and id_col is not None and 'Created at' in df.columns:
            d = df.copy()
            d['Created at'] = pd.to_datetime(d['Created at'], errors='coerce')
            d = d.dropna(subset=['Created at'])

            # Optional recent windowing via env (days). Example: F2S_WINDOW_DAYS=365
            try:
                win_days = int(os.getenv('F2S_WINDOW_DAYS', '0') or '0')
            except Exception:
                win_days = 0
            if win_days and win_days > 0:
                cutoff = d['Created at'].max() - pd.Timedelta(days=win_days)
                d = d[d['Created at'] >= cutoff]

            # De-duplicate to one record per order per customer to avoid line-item duplicates
            if order_col is not None and order_col in d.columns:
                # Keep the first timestamp per (customer, order)
                d = (
                    d[[id_col, order_col, 'Created at']]
                    .sort_values(['Created at'])
                    .groupby([id_col, order_col], as_index=False)['Created at']
                    .min()
                )
            else:
                # Fallback: drop duplicates on (customer, timestamp)
                d = d[[id_col, 'Created at']].drop_duplicates([id_col, 'Created at'])

            # Purchase sequences per customer using de-duplicated orders
            seq = (
                d.sort_values('Created at')
                 .groupby(id_col)['Created at']
                 .apply(list)
                 .reset_index()
            )

            days_to_second: List[float] = []
            for _, row in seq.iterrows():
                dates = row['Created at']
                if isinstance(dates, list) and len(dates) >= 2:
                    days = (dates[1] - dates[0]).days
                    days_to_second.append(days)

            if days_to_second:
                ax1.hist(days_to_second, bins=30, color='#6366f1', alpha=0.7, edgecolor='black')
                med = float(np.median(days_to_second))
                ax1.axvline(x=med, color='red', linestyle='--', label=f'Median: {med:.0f} days')
                ax1.set_xlabel('Days to Second Purchase')
                ax1.set_ylabel('Number of Customers')
                ax1.set_title('Time to Second Purchase Distribution', fontweight='bold')
                ax1.legend()
            else:
                ax1.text(0.5, 0.5, 'No second purchases observed', ha='center', va='center', transform=ax1.transAxes)

            # Funnel: 2+ and 3+
            total_customers = int(seq.shape[0])
            two_plus = int((seq['Created at'].apply(lambda x: len(x) if isinstance(x, list) else 0) >= 2).sum())
            three_plus = int((seq['Created at'].apply(lambda x: len(x) if isinstance(x, list) else 0) >= 3).sum())

            stages = ['All\nCustomers', '2+\nOrders', '3+\nOrders']
            values = [total_customers, two_plus, three_plus]
            colors = ['#e5e7eb', '#6366f1', '#10b981']
            bars = ax2.bar(stages, values, color=colors)
            ax2.set_ylabel('Number of Customers')
            ax2.set_title('Customer Order Frequency Funnel', fontweight='bold')

            for i, (stage, val) in enumerate(zip(stages, values)):
                ax2.text(i, val, f'{val}', ha='center', va='bottom', fontweight='bold')
                if i > 0 and values[i-1] > 0:
                    conv_rate = (val / values[i-1] * 100)
                    ax2.text(i - 0.5, values[i-1] / 2, f'{conv_rate:.0f}%',
                             ha='center', va='center', fontweight='bold', color='red', fontsize=12)
        else:
            need = []
            if df is not None:
                if 'Created at' not in df.columns:
                    need.append('Created at')
                if ('Customer Email' not in df.columns) and ('customer_id' not in df.columns):
                    need.append('Customer Email or customer_id')
            msg = 'Missing columns: ' + ', '.join(need) if need else 'Missing required columns'
            ax1.text(0.5, 0.5, f"{msg}. Use exact column names.", ha='center', va='center', transform=ax1.transAxes, wrap=True)
            ax2.axis('off')
    except Exception as e:
        ax1.text(0.5, 0.5, f'Error: {e}', ha='center', va='center', transform=ax1.transAxes)
        ax2.axis('off')

    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches='tight')
    plt.close()
    return out_path


# =============================================================================
# PLAY-SPECIFIC CHART GENERATORS
# =============================================================================

def journey_optimization_chart(
    action: Dict[str, Any],
    aligned: Dict[str, Any],
    df: Optional[pd.DataFrame],
    out_path: Path
) -> str:
    """
    Journey Optimization: Shows customer journey funnel with drop-off points.
    Visualizes where customers stall in the purchase journey.
    """
    fig, ax = plt.subplots(figsize=(12, 7))

    try:
        # Build funnel from customer purchase patterns
        id_col = None
        if df is not None:
            if 'Customer Email' in df.columns:
                id_col = 'Customer Email'
            elif 'customer_id' in df.columns:
                id_col = 'customer_id'

        if df is not None and id_col is not None and 'Created at' in df.columns:
            d = df.copy()
            d['Created at'] = pd.to_datetime(d['Created at'], errors='coerce')
            d = d.dropna(subset=['Created at', id_col])

            # Get unique orders per customer (dedupe line items)
            order_col = 'Name' if 'Name' in d.columns else 'order_id' if 'order_id' in d.columns else None
            if order_col:
                customer_orders = d.groupby(id_col)[order_col].nunique().reset_index(name='order_count')
            else:
                customer_orders = d.groupby(id_col).size().reset_index(name='order_count')

            # Build funnel stages
            total = len(customer_orders)
            one_only = len(customer_orders[customer_orders['order_count'] == 1])
            two_plus = len(customer_orders[customer_orders['order_count'] >= 2])
            three_plus = len(customer_orders[customer_orders['order_count'] >= 3])
            five_plus = len(customer_orders[customer_orders['order_count'] >= 5])

            # Funnel data
            stages = ['All Customers', '2+ Orders', '3+ Orders', '5+ Orders']
            values = [total, two_plus, three_plus, five_plus]
            colors = ['#E5E7EB', '#60A5FA', '#34D399', '#8B5CF6']

            # Create horizontal bar chart (funnel style)
            y_pos = np.arange(len(stages))
            bars = ax.barh(y_pos, values, color=colors, height=0.65, edgecolor='white', linewidth=2)

            # Add value labels on bars
            for i, (bar, val) in enumerate(zip(bars, values)):
                # Value inside bar
                ax.text(val - max(values) * 0.02, i, f'{val:,}',
                       ha='right', va='center', fontweight='bold', fontsize=16, color='white' if val > max(values) * 0.3 else '#1F2937')

                # Conversion rate to right of bar
                if i > 0 and values[i-1] > 0:
                    conv_rate = val / values[i-1] * 100
                    ax.text(val + max(values) * 0.03, i, f'{conv_rate:.0f}% converted',
                           ha='left', va='center', fontsize=14, color='#059669', fontweight='bold')

            # Add drop-off callouts
            for i in range(len(values) - 1):
                if values[i] > 0:
                    dropped = values[i] - values[i + 1]
                    drop_pct = dropped / values[i] * 100
                    mid_y = i + 0.5
                    ax.annotate(
                        f'↓ {dropped:,} dropped ({drop_pct:.0f}%)',
                        xy=(values[i + 1], mid_y),
                        xytext=(max(values) * 0.7, mid_y),
                        fontsize=13,
                        color='#DC2626',
                        fontweight='bold',
                        ha='center',
                        arrowprops=dict(arrowstyle='->', color='#DC2626', lw=2)
                    )

            ax.set_yticks(y_pos)
            ax.set_yticklabels(stages, fontsize=14, fontweight='bold')
            ax.set_xlabel('Number of Customers', fontsize=14, fontweight='bold')
            ax.set_xlim(0, max(values) * 1.3)

            # Title with impact
            expected_rev = action.get('expected_$', 0)
            ax.set_title(f'Customer Journey — Converting drop-offs adds ${expected_rev:,.0f}/month',
                        fontsize=16, fontweight='bold', loc='left', pad=15)

            # Key insight box
            if two_plus > 0 and total > 0:
                first_to_second = two_plus / total * 100
                opportunity = one_only  # Customers stuck at 1 order
                ax.text(0.98, 0.02,
                       f'🎯 {opportunity:,} customers stuck at 1 order\nFirst→Second conversion: {first_to_second:.1f}%',
                       transform=ax.transAxes, ha='right', va='bottom',
                       fontsize=13, fontweight='bold',
                       bbox=dict(boxstyle='round,pad=0.5', facecolor='#FEF3C7', edgecolor='#F59E0B', linewidth=2))
        else:
            # Fallback: show opportunity summary with visual
            audience = action.get('audience_size', action.get('n', 0))
            expected_rev = action.get('expected_$', 0)

            # Create a simple visual even without full data
            stages = ['Target Audience', 'Expected Converts', 'Revenue Impact']
            # Estimate 30% conversion from target audience
            converts = int(audience * 0.3)
            values = [audience, converts, 1]  # Use 1 as placeholder for revenue bar

            colors = ['#60A5FA', '#34D399', '#8B5CF6']
            y_pos = np.arange(len(stages))

            ax.barh(y_pos[:2], values[:2], color=colors[:2], height=0.5)
            ax.text(values[0] + 10, 0, f'{audience:,} customers', fontsize=14, fontweight='bold', va='center')
            ax.text(values[1] + 10, 1, f'~{converts:,} converts (est.)', fontsize=14, fontweight='bold', va='center')

            ax.set_yticks(y_pos[:2])
            ax.set_yticklabels(stages[:2], fontsize=14, fontweight='bold')

            ax.set_title(f'Journey Optimization — ${expected_rev:,.0f} opportunity in 28 days',
                        fontsize=16, fontweight='bold', loc='left')

    except Exception as e:
        ax.text(0.5, 0.5, f'Chart generation error: {e}', ha='center', va='center', transform=ax.transAxes, fontsize=14)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_linewidth(1.5)
    ax.spines['left'].set_linewidth(1.5)
    plt.tight_layout()
    plt.savefig(str(out_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    return str(out_path)


def frequency_accelerator_chart(
    action: Dict[str, Any],
    aligned: Dict[str, Any],
    df: Optional[pd.DataFrame],
    out_path: Path
) -> str:
    """
    Frequency Accelerator: Shows repeat rate trend and 28-day opportunity.
    Focus on what accelerating repeat purchases will achieve.
    """
    fig, ax = plt.subplots(figsize=(12, 7))

    try:
        # Get repeat rates from aligned windows
        windows = ['L7', 'L28', 'L56', 'L90']
        window_labels = ['Last 7 days', 'Last 28 days', 'Last 56 days', 'Last 90 days']
        recent_rates = []
        prior_rates = []
        valid_windows = []
        valid_labels = []

        for w, label in zip(windows, window_labels):
            wdata = aligned.get(w, {})
            if not isinstance(wdata, dict):
                continue
            recent = wdata.get('repeat_rate_within_window')
            prior_data = wdata.get('prior', {})
            prior = prior_data.get('repeat_rate_within_window') if isinstance(prior_data, dict) else None

            if recent is not None:
                recent_rates.append(recent * 100)
                prior_rates.append(prior * 100 if prior is not None else None)
                valid_windows.append(w)
                valid_labels.append(label)

        if valid_windows:
            x = np.arange(len(valid_windows))
            width = 0.35

            # Plot recent vs prior
            bars1 = ax.bar(x - width/2, recent_rates, width, label='Current Period', color='#3B82F6', edgecolor='white', linewidth=2)
            prior_clean = [p if p is not None else 0 for p in prior_rates]
            bars2 = ax.bar(x + width/2, prior_clean, width, label='Prior Period', color='#BFDBFE', edgecolor='white', linewidth=2)

            # Add value labels on bars
            for i, (r, p) in enumerate(zip(recent_rates, prior_rates)):
                ax.text(i - width/2, r + 1, f'{r:.1f}%', ha='center', va='bottom', fontsize=14, fontweight='bold', color='#1E40AF')
                if p:
                    ax.text(i + width/2, p + 1, f'{p:.1f}%', ha='center', va='bottom', fontsize=13, color='#6B7280')

            # Add change indicators
            for i, (r, p) in enumerate(zip(recent_rates, prior_rates)):
                if p is not None and p > 0:
                    delta_pts = r - p  # percentage points change
                    color = '#059669' if delta_pts > 0 else '#DC2626'
                    arrow = '↑' if delta_pts > 0 else '↓'
                    ax.annotate(
                        f'{arrow} {abs(delta_pts):.1f} pts',
                        xy=(i, max(r, p) + 4),
                        ha='center',
                        fontsize=13,
                        fontweight='bold',
                        color=color
                    )

            ax.set_xticks(x)
            ax.set_xticklabels(valid_labels, fontsize=13, fontweight='bold')
            ax.set_ylabel('Repeat Purchase Rate', fontsize=14, fontweight='bold')
            ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))

            # Title with 28-day impact
            expected_rev = action.get('expected_$', 0)
            audience = action.get('audience_size', action.get('n', 0))
            ax.set_title(f'Repeat Purchase Trend — Accelerating {audience:,} buyers adds ${expected_rev:,.0f}/month',
                        fontsize=16, fontweight='bold', loc='left', pad=15)

            ax.legend(frameon=True, fontsize=13, loc='upper left')
            ax.set_ylim(0, max(recent_rates + prior_clean) * 1.3)

            # Key insight box
            l28_rate = recent_rates[1] if len(recent_rates) > 1 else recent_rates[0]
            ax.text(0.98, 0.98,
                   f'🎯 Current repeat rate: {l28_rate:.1f}%\nTarget: +15% frequency lift',
                   transform=ax.transAxes, ha='right', va='top',
                   fontsize=13, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='#EFF6FF', edgecolor='#3B82F6', linewidth=2))
        else:
            # Fallback
            audience = action.get('audience_size', action.get('n', 0))
            expected_rev = action.get('expected_$', 0)
            ax.text(0.5, 0.5, f'Frequency Accelerator\n\nTarget: {audience:,} repeat buyers\n28-Day Opportunity: ${expected_rev:,.0f}',
                   ha='center', va='center', transform=ax.transAxes, fontsize=16, fontweight='bold')

    except Exception as e:
        ax.text(0.5, 0.5, f'Chart generation error: {e}', ha='center', va='center', transform=ax.transAxes, fontsize=14)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_linewidth(1.5)
    ax.spines['left'].set_linewidth(1.5)
    plt.tight_layout()
    plt.savefig(str(out_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    return str(out_path)


def retention_mastery_chart(
    action: Dict[str, Any],
    aligned: Dict[str, Any],
    df: Optional[pd.DataFrame],
    out_path: Path
) -> str:
    """
    Retention Mastery: Shows returning customer share and 28-day protection opportunity.
    Focus on what retaining at-risk customers will protect.
    """
    fig, ax = plt.subplots(figsize=(12, 7))

    try:
        windows = ['L7', 'L28', 'L56', 'L90']
        window_labels = ['Last 7 days', 'Last 28 days', 'Last 56 days', 'Last 90 days']
        returning_shares = []
        new_shares = []
        valid_windows = []
        valid_labels = []

        for w, label in zip(windows, window_labels):
            wdata = aligned.get(w, {})
            if not isinstance(wdata, dict):
                continue
            returning = wdata.get('returning_customer_share')
            if returning is not None:
                returning_shares.append(returning * 100)
                new_shares.append((1 - returning) * 100)
                valid_windows.append(w)
                valid_labels.append(label)

        if valid_windows:
            x = np.arange(len(valid_windows))
            width = 0.6

            # Stacked bar: returning vs new
            bars1 = ax.bar(x, returning_shares, width, label='Returning Customers', color='#22C55E', edgecolor='white', linewidth=2)
            bars2 = ax.bar(x, new_shares, width, bottom=returning_shares, label='New Customers', color='#F59E0B', edgecolor='white', linewidth=2)

            # Add percentage labels
            for i, (ret, new) in enumerate(zip(returning_shares, new_shares)):
                ax.text(i, ret / 2, f'{ret:.0f}%', ha='center', va='center', fontweight='bold', color='white', fontsize=16)
                if new > 8:
                    ax.text(i, ret + new / 2, f'{new:.0f}%', ha='center', va='center', fontweight='bold', color='white', fontsize=14)

            ax.set_xticks(x)
            ax.set_xticklabels(valid_labels, fontsize=13, fontweight='bold')
            ax.set_ylabel('Customer Share', fontsize=14, fontweight='bold')
            ax.set_ylim(0, 108)

            # Title with 28-day impact
            expected_rev = action.get('expected_$', 0)
            audience = action.get('audience_size', action.get('n', 0))
            ax.set_title(f'Customer Retention Mix — Protecting {audience:,} at-risk customers saves ${expected_rev:,.0f}/month',
                        fontsize=16, fontweight='bold', loc='left', pad=15)

            ax.legend(loc='upper right', frameon=True, fontsize=13)

            # Key insight box
            l28_returning = returning_shares[1] if len(returning_shares) > 1 else returning_shares[0]
            health = 'Strong' if l28_returning >= 70 else 'Moderate' if l28_returning >= 50 else 'At Risk'
            health_color = '#F0FDF4' if l28_returning >= 70 else '#FEF3C7' if l28_returning >= 50 else '#FEE2E2'
            health_border = '#22C55E' if l28_returning >= 70 else '#F59E0B' if l28_returning >= 50 else '#EF4444'

            ax.text(0.02, 0.98,
                   f'🎯 Retention Health: {health}\nReturning share: {l28_returning:.0f}%',
                   transform=ax.transAxes, ha='left', va='top',
                   fontsize=13, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor=health_color, edgecolor=health_border, linewidth=2))
        else:
            # Fallback
            audience = action.get('audience_size', action.get('n', 0))
            expected_rev = action.get('expected_$', 0)
            ax.text(0.5, 0.5, f'Retention Mastery\n\nTarget: {audience:,} at-risk customers\n28-Day Protection: ${expected_rev:,.0f}',
                   ha='center', va='center', transform=ax.transAxes, fontsize=16, fontweight='bold')

    except Exception as e:
        ax.text(0.5, 0.5, f'Chart generation error: {e}', ha='center', va='center', transform=ax.transAxes, fontsize=14)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_linewidth(1.5)
    ax.spines['left'].set_linewidth(1.5)
    plt.tight_layout()
    plt.savefig(str(out_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    return str(out_path)


def aov_optimizer_chart(
    action: Dict[str, Any],
    aligned: Dict[str, Any],
    df: Optional[pd.DataFrame],
    out_path: Path
) -> str:
    """
    AOV Optimizer: Shows AOV trend and distribution.
    Highlights AOV growth opportunity with 28-day forward impact.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))

    # Extract 28-day opportunity metrics
    audience = action.get('audience_size', action.get('n', 0))
    expected_rev = action.get('expected_$', 0)

    try:
        # Left panel: AOV trend across windows
        windows = ['L7', 'L28', 'L56', 'L90']
        window_labels = ['Last 7 days', 'Last 28 days', 'Last 56 days', 'Last 90 days']
        recent_aovs = []
        prior_aovs = []
        valid_windows = []
        valid_labels = []

        for w, label in zip(windows, window_labels):
            wdata = aligned.get(w, {})
            if not isinstance(wdata, dict):
                continue
            recent = wdata.get('aov')
            prior_data = wdata.get('prior', {})
            prior = prior_data.get('aov') if isinstance(prior_data, dict) else None

            if recent is not None:
                recent_aovs.append(recent)
                prior_aovs.append(prior)
                valid_windows.append(w)
                valid_labels.append(label)

        if valid_windows:
            x = np.arange(len(valid_windows))
            width = 0.35

            bars1 = ax1.bar(x - width/2, recent_aovs, width, label='Current Period', color='#8B5CF6')
            prior_clean = [p if p is not None else 0 for p in prior_aovs]
            bars2 = ax1.bar(x + width/2, prior_clean, width, label='Previous Period', color='#DDD6FE', alpha=0.8)

            # Add AOV values on bars with larger fonts
            for i, (r, p) in enumerate(zip(recent_aovs, prior_aovs)):
                ax1.text(i - width/2, r + 1, f'${r:.0f}', ha='center', va='bottom', fontsize=12, fontweight='bold')
                if p:
                    delta_pct = ((r - p) / p) * 100
                    color = '#22C55E' if delta_pct > 0 else '#EF4444'
                    ax1.text(i, max(r, p) + 4, f'{delta_pct:+.1f}%', ha='center', fontsize=12, fontweight='bold', color=color)

            ax1.set_xticks(x)
            ax1.set_xticklabels(valid_labels, fontsize=12, fontweight='bold', rotation=15, ha='right')
            ax1.set_ylabel('Average Order Value ($)', fontsize=14)
            ax1.set_title('AOV Trend', fontsize=16, fontweight='bold', loc='left')
            ax1.legend(frameon=True, fontsize=12)
            ax1.spines['top'].set_visible(False)
            ax1.spines['right'].set_visible(False)

        # Right panel: AOV distribution if df available
        if df is not None and 'Subtotal' in df.columns:
            order_totals = df.groupby('Name' if 'Name' in df.columns else df.index)['Subtotal'].sum()
            order_totals = order_totals[order_totals > 0]

            if len(order_totals) > 10:
                ax2.hist(order_totals, bins=30, color='#8B5CF6', alpha=0.7, edgecolor='black')
                median_aov = order_totals.median()
                mean_aov = order_totals.mean()
                ax2.axvline(x=median_aov, color='#EF4444', linestyle='--', linewidth=2, label=f'Median: ${median_aov:.0f}')
                ax2.axvline(x=mean_aov, color='#22C55E', linestyle='--', linewidth=2, label=f'Average: ${mean_aov:.0f}')
                ax2.set_xlabel('Order Value ($)', fontsize=14)
                ax2.set_ylabel('Number of Orders', fontsize=14)
                ax2.set_title('Order Value Distribution', fontsize=16, fontweight='bold', loc='left')
                ax2.legend(frameon=True, fontsize=12)

                # Add opportunity insight box
                gap = mean_aov - median_aov
                if gap > 0:
                    ax2.text(0.98, 0.98, f'Opportunity: ${gap:.0f} gap between\naverage and median order',
                            transform=ax2.transAxes, ha='right', va='top', fontsize=12,
                            bbox=dict(boxstyle='round', facecolor='#EDE9FE', edgecolor='#8B5CF6'))
            else:
                ax2.text(0.5, 0.5, 'Insufficient order data', ha='center', va='center',
                        transform=ax2.transAxes, fontsize=14)
        else:
            # Show opportunity summary
            ax2.text(0.5, 0.5, f'AOV Optimization\n\nTarget: {audience:,} customers\n28-Day Opportunity: ${expected_rev:,.0f}',
                    ha='center', va='center', transform=ax2.transAxes, fontsize=16, fontweight='bold')
            ax2.set_title('28-Day Impact', fontsize=16, fontweight='bold', loc='left')

        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)

    except Exception as e:
        ax1.text(0.5, 0.5, f'Error: {e}', ha='center', va='center', transform=ax1.transAxes)

    # Add main title with 28-day focus
    fig.suptitle(f'AOV Optimization — Increasing basket size for {audience:,} customers adds ${expected_rev:,.0f}/month',
                fontsize=16, fontweight='bold', y=1.02)

    plt.tight_layout()
    plt.savefig(str(out_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    return str(out_path)


def winback_campaign_chart(
    action: Dict[str, Any],
    aligned: Dict[str, Any],
    df: Optional[pd.DataFrame],
    out_path: Path
) -> str:
    """
    Winback Campaign: Shows lapsed customer distribution by days since last order.
    Identifies winback timing opportunities with 28-day forward impact.
    """
    fig, ax = plt.subplots(figsize=(12, 7))

    # Extract 28-day opportunity metrics
    audience = action.get('audience_size', action.get('n', 0))
    expected_rev = action.get('expected_$', 0)

    try:
        # Detect customer ID column
        id_col = None
        if df is not None:
            if 'Customer Email' in df.columns:
                id_col = 'Customer Email'
            elif 'customer_id' in df.columns:
                id_col = 'customer_id'

        if df is not None and id_col is not None and 'Created at' in df.columns:
            d = df.copy()
            d['Created at'] = pd.to_datetime(d['Created at'], errors='coerce')
            d = d.dropna(subset=['Created at', id_col])

            # Get last order date per customer
            anchor = d['Created at'].max()
            last_orders = d.groupby(id_col)['Created at'].max().reset_index()
            last_orders['days_since'] = (anchor - last_orders['Created at']).dt.days

            # Create buckets with human-readable labels
            bins = [0, 30, 60, 90, 120, 180, 365, float('inf')]
            bucket_labels = ['Active\n(0-30 days)', 'At Risk\n(31-60 days)', 'Lapsing\n(61-90 days)',
                           'Lapsed\n(91-120 days)', 'Dormant\n(4-6 months)', 'Lost\n(6-12 months)', 'Gone\n(1yr+)']
            last_orders['bucket'] = pd.cut(last_orders['days_since'], bins=bins, labels=bucket_labels, right=True)

            # Count per bucket
            bucket_counts = last_orders['bucket'].value_counts().reindex(bucket_labels, fill_value=0)

            # Color gradient: green (recent) to red (lapsed)
            colors = ['#22C55E', '#84CC16', '#EAB308', '#F97316', '#EF4444', '#DC2626', '#991B1B']

            bars = ax.bar(range(len(bucket_labels)), bucket_counts.values, color=colors, edgecolor='black', linewidth=0.5)

            # Add count labels with larger font
            for bar, count in zip(bars, bucket_counts.values):
                if count > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                           f'{count:,}', ha='center', va='bottom', fontsize=13, fontweight='bold')

            ax.set_xticks(range(len(bucket_labels)))
            ax.set_xticklabels(bucket_labels, fontsize=11, fontweight='bold')
            ax.set_xlabel('Customer Status', fontsize=14)
            ax.set_ylabel('Number of Customers', fontsize=14)

            # Add winback zone annotation
            at_risk_count = bucket_counts.iloc[1:4].sum()  # At Risk, Lapsing, Lapsed
            ax.axvspan(0.5, 3.5, alpha=0.15, color='#F97316', label=f'Prime Winback Zone: {at_risk_count:,} customers')
            ax.legend(loc='upper right', frameon=True, fontsize=12)

            # Add insight box with 28-day opportunity
            ax.text(0.02, 0.98, f'28-Day Opportunity: ${expected_rev:,.0f}\nTarget: {audience:,} winnable customers',
                   transform=ax.transAxes, ha='left', va='top', fontsize=13, fontweight='bold',
                   bbox=dict(boxstyle='round', facecolor='#FEF3C7', edgecolor='#F97316'))

            # Main title with 28-day focus
            ax.set_title(f'Customer Recency — Re-engaging {audience:,} customers recovers ${expected_rev:,.0f}/month',
                        fontsize=16, fontweight='bold', loc='left', pad=15)
        else:
            # Fallback with 28-day focus
            ax.text(0.5, 0.5, f'Winback Campaign\n\nTarget: {audience:,} lapsed customers\n28-Day Opportunity: ${expected_rev:,.0f}',
                   ha='center', va='center', transform=ax.transAxes, fontsize=16, fontweight='bold')
            ax.set_title('Customer Winback Opportunity', fontsize=16, fontweight='bold', loc='left')

    except Exception as e:
        ax.text(0.5, 0.5, f'Chart generation error: {e}', ha='center', va='center', transform=ax.transAxes, fontsize=14)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    plt.savefig(str(out_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    return str(out_path)


def discount_optimization_chart(
    action: Dict[str, Any],
    aligned: Dict[str, Any],
    df: Optional[pd.DataFrame],
    out_path: Path
) -> str:
    """
    Discount Optimization: Shows discount rate trend and margin impact.
    Highlights discount discipline opportunities with 28-day forward impact.
    """
    fig, ax = plt.subplots(figsize=(12, 7))

    # Extract 28-day opportunity metrics
    audience = action.get('audience_size', action.get('n', 0))
    expected_rev = action.get('expected_$', 0)

    try:
        windows = ['L7', 'L28', 'L56', 'L90']
        window_labels = ['Last 7 days', 'Last 28 days', 'Last 56 days', 'Last 90 days']
        discount_rates = []
        valid_windows = []
        valid_labels = []
        prior_rates = []

        for w, label in zip(windows, window_labels):
            wdata = aligned.get(w, {})
            if not isinstance(wdata, dict):
                continue
            rate = wdata.get('discount_rate')
            prior_data = wdata.get('prior', {})
            prior = prior_data.get('discount_rate') if isinstance(prior_data, dict) else None

            if rate is not None:
                discount_rates.append(rate * 100)
                prior_rates.append(prior * 100 if prior is not None else None)
                valid_windows.append(w)
                valid_labels.append(label)

        if valid_windows:
            x = np.arange(len(valid_windows))
            width = 0.35

            # Plot recent vs prior
            bars1 = ax.bar(x - width/2, discount_rates, width, label='Current Period', color='#EF4444')
            prior_clean = [p if p is not None else 0 for p in prior_rates]
            bars2 = ax.bar(x + width/2, prior_clean, width, label='Previous Period', color='#FECACA', alpha=0.8)

            # Add values and deltas with larger fonts
            for i, (r, p) in enumerate(zip(discount_rates, prior_rates)):
                ax.text(i - width/2, r + 0.2, f'{r:.1f}%', ha='center', va='bottom', fontsize=12, fontweight='bold')
                if p is not None and p > 0:
                    delta = r - p
                    color = '#22C55E' if delta < 0 else '#EF4444'  # Lower discount is better
                    arrow = '↓' if delta < 0 else '↑'
                    ax.text(i, max(r, p) + 0.5, f'{arrow} {abs(delta):.1f}pp',
                           ha='center', fontsize=12, fontweight='bold', color=color)

            ax.set_xticks(x)
            ax.set_xticklabels(valid_labels, fontsize=12, fontweight='bold', rotation=15, ha='right')
            ax.set_ylabel('Discount Rate (%)', fontsize=14)
            ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=1))
            ax.legend(frameon=True, fontsize=12)

            # Calculate margin impact
            avg_rate = np.mean(discount_rates)
            monthly_rev = aligned.get('L28', {}).get('net_sales', 100000)
            current_margin_loss = monthly_rev * (avg_rate / 100)

            # Determine trend
            direction = aligned.get('direction', {})
            trend = direction.get('discount_rate', 'stable')
            if trend == 'down':
                trend_text = '↓ Improving'
                trend_color = '#22C55E'
            elif trend == 'up':
                trend_text = '↑ Watch closely'
                trend_color = '#EF4444'
            else:
                trend_text = '→ Stable'
                trend_color = '#6B7280'

            # Add insight box with 28-day opportunity
            insight_text = (f"Current discount cost: ${current_margin_loss:,.0f}/month\n"
                          f"28-Day Margin Opportunity: ${expected_rev:,.0f}\n"
                          f"Trend: {trend_text}")
            ax.text(0.98, 0.98, insight_text,
                   transform=ax.transAxes, ha='right', va='top', fontsize=13, fontweight='bold',
                   bbox=dict(boxstyle='round', facecolor='#FEF2F2' if avg_rate > 3 else '#F0FDF4',
                            edgecolor=trend_color))

            # Main title with 28-day focus
            ax.set_title(f'Discount Rate Trend — Tightening discounts saves ${expected_rev:,.0f}/month',
                        fontsize=16, fontweight='bold', loc='left', pad=15)
        else:
            # Fallback
            ax.text(0.5, 0.5, f'Discount Optimization\n\nTarget: {audience:,} discount-heavy orders\n28-Day Margin Opportunity: ${expected_rev:,.0f}',
                   ha='center', va='center', transform=ax.transAxes, fontsize=16, fontweight='bold')
            ax.set_title('Discount Optimization Opportunity', fontsize=16, fontweight='bold', loc='left')

    except Exception as e:
        ax.text(0.5, 0.5, f'Chart generation error: {e}', ha='center', va='center', transform=ax.transAxes, fontsize=14)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    plt.savefig(str(out_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    return str(out_path)


# Play-specific chart dispatcher
PLAY_CHART_GENERATORS: Dict[str, callable] = {
    'journey_optimization': journey_optimization_chart,
    'frequency_accelerator': frequency_accelerator_chart,
    'retention_mastery': retention_mastery_chart,
    'aov_optimizer': aov_optimizer_chart,
    'aov_momentum': aov_optimizer_chart,  # alias
    'winback_campaign': winback_campaign_chart,
    'winback': winback_campaign_chart,  # alias
    'discount_optimization': discount_optimization_chart,
    'discount_hygiene': discount_optimization_chart,  # alias
}


def create_play_specific_chart(
    action: Dict[str, Any],
    aligned: Dict[str, Any],
    df: Optional[pd.DataFrame],
    out_dir: Path,
    sequence: int
) -> Optional[str]:
    """
    Create a play-specific chart if a generator exists for this play.
    Falls back to multiwindow chart if no specific generator.
    """
    play_id = action.get('play_id', '').lower()
    generator = PLAY_CHART_GENERATORS.get(play_id)

    if generator is None:
        return None  # Fall back to default multiwindow chart

    variant = action.get('variant_id', 'base')
    out_path = out_dir / f"action_metric_{_slugify(play_id)}_{_slugify(variant)}_{sequence}.png"

    try:
        return generator(action, aligned, df, out_path)
    except Exception as e:
        print(f"Warning: Play-specific chart failed for {play_id}: {e}")
        return None


def generate_charts(g: pd.DataFrame, aligned: dict, actions: List[Dict], out_dir: str,
                   df: Optional[pd.DataFrame] = None,
                   chosen_window: Optional[str] = None,
                   charts_mode: Optional[str] = None,
                   inventory_metrics: Optional[pd.DataFrame] = None) -> Dict[str, str]:
    """Enhanced chart generation for Beauty/Supplements"""
    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)
    charts = {}
    
    # Generate each chart
    try:
        charts['repurchase_timeline'] = repurchase_curve_chart(
            g, aligned, str(out_dir_path / "repurchase_timeline.png")
        )
    except Exception as e:
        print(f"Warning: Could not generate repurchase timeline chart: {e}")
    
    try:
        mode = (charts_mode or os.getenv('CHARTS_MODE', 'detailed') or 'detailed')
        mode = str(mode).strip().lower()
        if mode in {'compact','minimal'}:
            charts['product_velocity'] = product_performance_compact_chart(
                g, aligned, str(out_dir_path / "product_velocity.png"), df=df, top_n=5
            )
        else:
            charts['product_velocity'] = product_velocity_chart(
                g, aligned, str(out_dir_path / "product_velocity.png"), df=df
            )
    except Exception as e:
        print(f"Warning: Could not generate product velocity chart: {e}")
    
    try:
        charts['customer_segments'] = customer_value_segments_chart(
            g, aligned, str(out_dir_path / "customer_segments.png")
        )
    except Exception as e:
        print(f"Warning: Could not generate customer segments chart: {e}")
    
    # Inventory: Stock vs Demand chart
    try:
        if inventory_metrics is not None and not getattr(inventory_metrics, 'empty', False):
            charts['stock_vs_demand'] = stock_vs_demand_chart(
                inventory_metrics, str(out_dir_path / "stock_vs_demand.png"), top_n=10
            )
    except Exception as e:
        print(f"Warning: Could not generate stock vs demand chart: {e}")

    if df is not None:
        try:
            charts['cohort_retention'] = cohort_retention_chart(
                df, str(out_dir_path / "cohort_retention.png")
            )
        except Exception as e:
            print(f"Warning: Could not generate cohort retention chart: {e}")
        try:
            charts['first_to_second'] = first_to_second_purchase_chart(
                df, str(out_dir_path / "first_to_second.png")
            )
        except Exception as e:
            print(f"Warning: Could not generate first-to-second purchase chart: {e}")
    try:
        vertical_mode = get_vertical_mode()
    except Exception:
        vertical_mode = 'mixed'
    window_weights = get_window_weights(vertical_mode) or {}

    action_list = _flatten_actions(actions)
    for idx, action in enumerate(action_list):
        if not isinstance(action, dict):
            continue
        action['supporting_charts'] = []

        # Try play-specific chart first, then fall back to multiwindow
        chart_path = create_play_specific_chart(action, aligned, df, out_dir_path, idx)
        if chart_path is None:
            # Fall back to generic multiwindow chart
            chart_path = create_action_multiwindow_chart(action, aligned, window_weights, out_dir_path, idx)

        if chart_path:
            chart_key = f"action_metric_{_slugify(action.get('play_id', 'action'))}_{idx}"
            charts[chart_key] = chart_path
            action['supporting_charts'].append(chart_key)

    return charts
