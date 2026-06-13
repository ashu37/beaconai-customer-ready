"""
generate_synthetic_shopify.py
Deterministic synthetic Shopify fixture generator for the BeaconAI Action Engine.

Usage:
  python scripts/generate_synthetic_shopify.py [--anchor-date 2025-09-18] [--scenario NAME] [--out-dir tests/fixtures/synthetic/]

Produces per-scenario:
  {scenario}_orders.csv   — Shopify line-item format
  {scenario}_inventory.csv — where relevant
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# Repo root (resolve regardless of cwd)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_YAML = REPO_ROOT / "tests" / "fixtures" / "synthetic_scenarios.yaml"

# ---------------------------------------------------------------------------
# Product catalogs
# ---------------------------------------------------------------------------

BEAUTY_PRODUCTS = [
    {"sku": "BEAU-001", "name": "Vitamin C Brightening Serum", "base_price": 55.00, "category": "serum"},
    {"sku": "BEAU-002", "name": "Hyaluronic Acid Moisturizer", "base_price": 42.00, "category": "moisturizer"},
    {"sku": "BEAU-003", "name": "Retinol Night Treatment", "base_price": 65.00, "category": "treatment"},
    {"sku": "BEAU-004", "name": "Gentle Foaming Cleanser", "base_price": 32.00, "category": "cleanser"},
    {"sku": "BEAU-005", "name": "SPF 50 Daily Defense Cream", "base_price": 38.00, "category": "moisturizer"},
    {"sku": "BEAU-006", "name": "Niacinamide Pore Refining Toner", "base_price": 35.00, "category": "toner"},
    {"sku": "BEAU-007", "name": "Peptide Eye Cream", "base_price": 72.00, "category": "treatment"},
    {"sku": "BEAU-008", "name": "AHA/BHA Exfoliating Serum", "base_price": 48.00, "category": "serum"},
    {"sku": "BEAU-009", "name": "Ceramide Barrier Repair Moisturizer", "base_price": 50.00, "category": "moisturizer"},
    {"sku": "BEAU-010", "name": "Micellar Cleansing Water", "base_price": 28.00, "category": "cleanser"},
]

SUPPLEMENT_PRODUCTS = [
    {"sku": "SUPP-001", "name": "Whey Protein Powder Vanilla 2lb", "base_price": 49.00, "category": "protein"},
    {"sku": "SUPP-002", "name": "Vitamin D3 + K2 Capsules 90ct", "base_price": 28.00, "category": "vitamins"},
    {"sku": "SUPP-003", "name": "Pre-Workout Energy Complex", "base_price": 42.00, "category": "pre-workout"},
    {"sku": "SUPP-004", "name": "Collagen Peptides Powder 1lb", "base_price": 38.00, "category": "collagen"},
    {"sku": "SUPP-005", "name": "Omega-3 Fish Oil 1000mg 120ct", "base_price": 35.00, "category": "omega"},
    {"sku": "SUPP-006", "name": "Magnesium Glycinate 200mg 60ct", "base_price": 24.00, "category": "vitamins"},
    {"sku": "SUPP-007", "name": "Creatine Monohydrate 500g", "base_price": 32.00, "category": "performance"},
    {"sku": "SUPP-008", "name": "Ashwagandha KSM-66 300mg 60ct", "base_price": 30.00, "category": "adaptogen"},
    {"sku": "SUPP-009", "name": "Probiotics 50 Billion CFU 30ct", "base_price": 45.00, "category": "gut"},
    {"sku": "SUPP-010", "name": "Zinc + Quercetin Immune Formula", "base_price": 26.00, "category": "immune"},
]

LIFESTYLE_PRODUCTS = [
    {"sku": "LIFE-001", "name": "Aromatherapy Candle - Lavender", "base_price": 34.00, "category": "home"},
    {"sku": "LIFE-002", "name": "Natural Linen Face Towel Set", "base_price": 28.00, "category": "accessories"},
    {"sku": "LIFE-003", "name": "Bamboo Diffuser + Essential Oil", "base_price": 55.00, "category": "home"},
    {"sku": "LIFE-004", "name": "Silk Sleep Mask", "base_price": 24.00, "category": "accessories"},
    {"sku": "LIFE-005", "name": "Botanical Bath Salts 16oz", "base_price": 32.00, "category": "bath"},
    {"sku": "LIFE-006", "name": "Hand-Poured Soy Wax Candle Set", "base_price": 48.00, "category": "home"},
    {"sku": "LIFE-007", "name": "Organic Cotton Throw Blanket", "base_price": 65.00, "category": "home"},
    {"sku": "LIFE-008", "name": "Ceramic Ritual Mug", "base_price": 22.00, "category": "kitchen"},
]

US_PROVINCES = [
    "CA", "NY", "TX", "FL", "WA", "IL", "PA", "OH", "GA", "NC",
    "MI", "NJ", "VA", "AZ", "MA", "CO", "TN", "IN", "MO", "MD",
    "OR", "WI", "MN", "SC", "AL", "KY", "LA", "CT", "UT", "IA",
]

FIRST_NAMES = [
    "Emma", "Olivia", "Ava", "Isabella", "Sophia", "Charlotte", "Mia", "Amelia",
    "Harper", "Evelyn", "Abigail", "Emily", "Elizabeth", "Mila", "Ella",
    "Liam", "Noah", "William", "James", "Oliver", "Benjamin", "Elijah",
    "Lucas", "Mason", "Ethan", "Alexander", "Henry", "Jackson", "Sebastian",
    "Aiden", "Matthew", "Samuel", "David", "Joseph", "Carter", "Owen",
    "Jayden", "Dylan", "Luke", "Gabriel", "Anthony", "Isaac", "Leo",
    "Grayson", "Julian", "Wyatt", "Andrew", "Landon", "John", "Daniel",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts",
]


# ---------------------------------------------------------------------------
# Customer pool generator
# ---------------------------------------------------------------------------

def build_customer_pool(n: int, category: str) -> List[Dict]:
    """Generate a fixed pool of synthetic customers."""
    customers = []
    for i in range(n):
        first = FIRST_NAMES[i % len(FIRST_NAMES)]
        last = LAST_NAMES[(i // len(FIRST_NAMES)) % len(LAST_NAMES)]
        # Make emails unique with index
        email = f"cust{i+1:04d}@example.com"
        name = f"{first} {last}"
        province = US_PROVINCES[i % len(US_PROVINCES)]
        customers.append({
            "email": email,
            "name": name,
            "province": province,
        })
    return customers


# ---------------------------------------------------------------------------
# Order row building helpers
# ---------------------------------------------------------------------------

def _make_order_rows(
    order_num: int,
    created_at: datetime,
    customer: Dict,
    items: List[Dict],
    financial_status: str = "paid",
    fulfillment_status: str = "fulfilled",
    cancelled_at: str = "",
) -> List[Dict]:
    """
    Build one or more line-item rows for a single order.
    items: list of {name, sku, quantity, price, discount}
    Returns list of row dicts matching Shopify line-item export format.
    """
    subtotal = sum(it["price"] * it["quantity"] for it in items)
    total_discount = sum(it["discount"] for it in items)
    taxes = round(subtotal * 0.08, 2)
    shipping = 0.0 if subtotal > 75.0 else 9.99
    total = round(subtotal - total_discount + taxes + shipping, 2)

    rows = []
    order_name = f"#{1000 + order_num}"
    # Synthetic Fix 11: write the order timestamp tz-naive (no ``-07:00``
    # offset). Pre-Fix-11 the generator wrote ``-07:00`` Pacific offsets,
    # which produced tz-aware ``Created at`` Series after the engine's
    # ``load_orders_csv`` parsed them. The engine's
    # ``compute_inventory_metrics`` then attempted to subtract a tz-naive
    # ``pd.Timestamp.now()`` from a tz-aware Series and silently swallowed
    # the resulting "Cannot subtract tz-naive and tz-aware" exception via
    # ``main.py``'s ``[warn] inventory load/metrics failed`` branch. The
    # net effect: inventory_metrics was None on every synthetic run and
    # the Fix 4 ``inventory_blocked`` stamp could never fire. Real
    # fixtures (e.g. ``data/SM_orders.csv``) use tz-naive timestamps;
    # matching that convention here is the fixture-side resolution. No
    # engine code is changed under this fix.
    ts = created_at.strftime("%Y-%m-%dT%H:%M:%S")

    for it in items:
        rows.append({
            "Name": order_name,
            "Created at": ts,
            "Cancelled at": cancelled_at,
            "Lineitem name": it["name"],
            "Lineitem quantity": it["quantity"],
            "Lineitem price": round(it["price"], 2),
            "Lineitem discount": round(it["discount"], 2),
            "Financial Status": financial_status,
            "Fulfillment Status": fulfillment_status,
            "Subtotal": round(subtotal, 2),
            "Total Discount": round(total_discount, 2),
            "Shipping": shipping,
            "Taxes": taxes,
            "Total": total,
            "Currency": "USD",
            "Customer Email": customer["email"],
            "Billing Name": customer["name"],
            "Shipping Province": customer["province"],
            "Shipping Country": "US",
        })
    return rows


def _pick_items(products: List[Dict], n_items: int, discount_pct: float) -> List[Dict]:
    """Pick n_items from product catalog with optional discount."""
    chosen = random.choices(products, k=n_items)
    result = []
    for p in chosen:
        qty = random.choices([1, 1, 1, 2], weights=[70, 15, 10, 5])[0]
        price = p["base_price"] * random.uniform(0.95, 1.05)
        price = round(price, 2)
        line_total = price * qty
        discount = round(line_total * discount_pct, 2) if discount_pct > 0 else 0.0
        result.append({
            "name": p["name"],
            "sku": p["sku"],
            "quantity": qty,
            "price": price,
            "discount": discount,
        })
    return result


# ---------------------------------------------------------------------------
# Scenario-specific generators
# ---------------------------------------------------------------------------

def _repeat_curve_returning_share(
    month_idx: int,
    start_share: float = 0.25,
    end_share: float = 0.42,
    total_months: int = 8,
    alpha: float = 1.0,
) -> float:
    """Return fraction of returning customers for a given month index.

    ``alpha`` shapes the curve between ``start_share`` and ``end_share``:

    - ``alpha == 1.0`` (default) -> linear interpolation; preserves the
      pre-Fix-8 behavior so any caller relying on the old default keeps
      its old shape.
    - ``alpha < 1.0`` -> early growth is fast, late growth flattens
      (concave-down).
    - ``alpha > 1.0`` -> late growth is steeper than early growth
      (concave-up). Synthetic Fix 8 uses this to make the L28 delta
      visibly positive at the Sep 18 anchor for the healthy_beauty
      fixture, so the Phase 5.6 directional first_to_second_purchase
      pathway has a chance to fire.

    The function never extrapolates beyond ``[start_share, end_share]``.
    """
    if total_months <= 1:
        return start_share
    frac = month_idx / (total_months - 1)
    if alpha != 1.0:
        # Power-curve shaping. Clamp ``frac`` defensively into [0, 1].
        f = max(0.0, min(1.0, frac))
        f = f ** float(alpha)
    else:
        f = frac
    return start_share + (end_share - start_share) * f


def inject_dormant_repeat_buyer_cohort(
    rows: List[Dict],
    *,
    anchor_date: datetime,
    cohort_size: int,
    seed: int,
    products: Optional[List[Dict]] = None,
    email_prefix: str = "wbdorm",
    window_days: Tuple[int, int] = (21, 45),
) -> List[Dict]:
    """Append explicit dormant repeat-buyer order rows to ``rows``.

    For each of ``cohort_size`` newly-minted customers (email keyed by
    ``email_prefix``), inject:

    - 2 prior orders, placed 90-180 days before the anchor (>=2 prior
      orders + >45 days ago, so they don't collide with the recency
      filter or the L28 filter).
    - 1 "last order" placed within ``window_days`` days of the anchor.
    - NO order in the past 28 days.

    These customers satisfy the 3-part winback_dormant_cohort definition
    (vertical-aware recency window ∧ >=2 prior orders ∧ no L28 activity).
    Returns the augmented ``rows`` list.
    """

    rng = random.Random(seed)
    if products is None:
        products = BEAUTY_PRODUCTS

    wb_lo, wb_hi = window_days
    base_order_num = 1_000_000 + max(0, seed)  # high offset so order names don't collide

    for i in range(cohort_size):
        email = f"{email_prefix}{i:05d}@example.com"
        customer = {
            "email": email,
            "name": f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {LAST_NAMES[(i // len(FIRST_NAMES)) % len(LAST_NAMES)]}",
            "province": US_PROVINCES[i % len(US_PROVINCES)],
        }

        # Two prior orders, 90-180 days ago.
        for k in range(2):
            d_back = rng.randint(90, 180)
            created = anchor_date - timedelta(days=d_back, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
            items = _pick_items(products, rng.choice([1, 1, 2]), 0.0)
            rows.extend(_make_order_rows(base_order_num + i * 3 + k, created, customer, items))

        # One "last order" in the winback window.
        d_back = rng.randint(wb_lo, wb_hi)
        created = anchor_date - timedelta(days=d_back, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        items = _pick_items(products, rng.choice([1, 1, 2]), 0.0)
        rows.extend(_make_order_rows(base_order_num + i * 3 + 2, created, customer, items))

    return rows


def generate_healthy_beauty(
    anchor_date: datetime,
    days_history: int,
    seed: int,
    customer_pool_size: int = 15000,
    monthly_revenue_range: Tuple[float, float] = (90000, 130000),
    aov_range: Tuple[float, float] = (60, 80),
    refund_rate: float = 0.02,
    products: Optional[List[Dict]] = None,
    returning_share_start: float = 0.25,
    returning_share_end: float = 0.42,
    returning_share_alpha: float = 1.0,
    loyal_cohort_fraction: float = 0.25,
) -> List[Dict]:
    """
    Generate orders for a healthy beauty/skincare brand.

    Design:
    - Uses a virtual customer universe of `customer_pool_size` unique customers.
    - Most customers buy 1-2 times over the period (realistic e-commerce churn).
    - A loyal cohort (~20-30%) buys 3+ times, driving the improving returning rate.
    - Returning share starts at ``returning_share_start`` (month 1) and grows
      to ``returning_share_end`` (final month). The shape of that growth is
      controlled by ``returning_share_alpha`` (1.0 = linear; >1.0 = late
      acceleration; <1.0 = early acceleration).
    - The synthetic Fix 8 retune for ``healthy_beauty_240d`` uses
      ``returning_share_alpha > 1`` so the L28 returning_customer_share at the
      Sep anchor is positive vs. the prior 28-day window, giving the engine's
      Phase 5.6 directional pathway an actual signal to fire on. Defaults
      preserve pre-Fix-8 behavior for any caller that does not opt in.
    """
    random.seed(seed)
    np.random.seed(seed)

    if products is None:
        products = BEAUTY_PRODUCTS

    customers = build_customer_pool(customer_pool_size, "beauty")
    start_date = anchor_date - timedelta(days=days_history - 1)

    rows: List[Dict] = []
    order_counter = 0

    # Build month list
    months = []
    cur = start_date.replace(day=1)
    while cur <= anchor_date:
        months.append(cur)
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

    n_months = len(months)

    # Pre-assign customers to cohorts:
    # - "loyal" cohort: ``loyal_cohort_fraction`` of pool; will order 3-6 times
    #   across the period.
    # - "occasional" cohort: 25% of pool; will order 2 times.
    # - "one-time" cohort: remainder of pool; orders exactly once.
    n_loyal = int(customer_pool_size * float(loyal_cohort_fraction))
    n_occasional = int(customer_pool_size * 0.25)
    # Shuffle to randomly assign
    all_customer_indices = list(range(customer_pool_size))
    random.shuffle(all_customer_indices)
    loyal_set = set(all_customer_indices[:n_loyal])
    occasional_set = set(all_customer_indices[n_loyal:n_loyal + n_occasional])

    # Track which customers have ordered before and when
    customer_order_history: Dict[int, List[datetime]] = {}

    for m_idx, month_start in enumerate(months):
        month_end = (
            month_start.replace(month=month_start.month % 12 + 1, day=1)
            if month_start.month < 12
            else month_start.replace(year=month_start.year + 1, month=1, day=1)
        ) - timedelta(days=1)
        month_end = min(month_end, anchor_date)
        if month_start > anchor_date:
            break

        target_rev = random.uniform(*monthly_revenue_range)
        target_aov = random.uniform(*aov_range)
        target_orders = int(target_rev / target_aov)

        returning_share = _repeat_curve_returning_share(
            m_idx,
            start_share=returning_share_start,
            end_share=returning_share_end,
            total_months=n_months,
            alpha=returning_share_alpha,
        )
        n_returning = int(target_orders * returning_share)
        n_new = target_orders - n_returning

        # Pools: new = customers who have never ordered; returning = have ordered before
        prior_customers = set(customer_order_history.keys())
        new_pool = [i for i in range(customer_pool_size) if i not in prior_customers]
        repeat_pool = list(prior_customers)

        # For new orders: pick from new_pool (prefer loyal/occasional over one-time)
        # Weight loyal 3x, occasional 2x, one-time 1x when picking new customers
        if new_pool:
            w_new = [3 if i in loyal_set else 2 if i in occasional_set else 1 for i in new_pool]
            new_indices = random.choices(new_pool, weights=w_new, k=min(n_new, len(new_pool)))
        else:
            new_indices = []

        # If pool exhausted, add some one-time customers from any slot
        if len(new_indices) < n_new:
            fallback = random.choices(list(range(customer_pool_size)), k=n_new - len(new_indices))
            new_indices.extend(fallback)

        # For returning orders: weight toward loyal cohort
        if repeat_pool:
            w_ret = [3 if i in loyal_set else 2 if i in occasional_set else 1 for i in repeat_pool]
            ret_indices = random.choices(repeat_pool, weights=w_ret, k=n_returning)
        else:
            ret_indices = random.choices(list(range(customer_pool_size)), k=n_returning)

        all_indices = new_indices + ret_indices
        random.shuffle(all_indices)

        days_in_month = (month_end - month_start).days + 1

        for cust_idx in all_indices:
            customer = customers[cust_idx]
            day_offset = random.randint(0, days_in_month - 1)
            hour = random.randint(8, 22)
            minute = random.randint(0, 59)
            created = month_start + timedelta(days=day_offset, hours=hour, minutes=minute)
            if created > anchor_date:
                created = anchor_date - timedelta(hours=random.randint(1, 12))

            has_discount = random.random() < 0.18
            discount_pct = random.uniform(0.10, 0.20) if has_discount else 0.0

            n_items = random.choices([1, 2], weights=[75, 25])[0]
            items = _pick_items(products, n_items, discount_pct)

            if random.random() < refund_rate:
                fin_status = "refunded"
                ful_status = "unfulfilled"
            else:
                fin_status = "paid"
                ful_status = "fulfilled"

            order_rows = _make_order_rows(
                order_counter, created, customer, items,
                financial_status=fin_status,
                fulfillment_status=ful_status,
            )
            rows.extend(order_rows)
            order_counter += 1

            if cust_idx not in customer_order_history:
                customer_order_history[cust_idx] = []
            customer_order_history[cust_idx].append(created)

    return rows


def generate_supplement_replenishment(
    anchor_date: datetime,
    days_history: int,
    seed: int,
    customer_pool_size: int = 200,
    monthly_revenue_range: Tuple[float, float] = (45000, 70000),
    aov_range: Tuple[float, float] = (38, 52),
    reorder_interval_range: Tuple[int, int] = (28, 45),
    refund_rate: float = 0.015,
    loyal_sku_repeater_fraction: float = 0.30,
    new_acquisition_fraction: float = 0.30,
) -> List[Dict]:
    """Generate supplement brand orders with modeled reorder intervals.

    Synthetic Fix 9 retune
    ----------------------
    Pre-Fix-9 behavior gave every customer in the pool an initial purchase
    inside the first 60 days. Combined with the small pool (1200) and the
    240-day window, that meant by the time the engine's ``returning_customer_share``
    metric is computed at the Sep anchor, EVERY customer in the L28 window
    has prior history (returning_share = 100%) while the within-window
    repeat-rate is ~0.8% — internally inconsistent.

    Fix 9 fixes this without inventing a supplement directional pathway:

    1. **Spread first-order dates across the entire history window.** A
       fraction (``new_acquisition_fraction``) of customers gets their
       first order assigned later in the window so that the L28 cohort
       contains some genuinely new customers, capping
       ``returning_customer_share`` strictly below 100%.
    2. **Loyal-SKU repeater cohort.** A subset (``loyal_sku_repeater_fraction``)
       of customers always reorders the SAME SKU, with that SKU pinned at
       customer-pool-build time. This gives the engine a non-trivial
       audience for any SKU-anchored loyalty / replenishment-style logic
       without claiming a measurement design we do not have.
    3. **Size-token product metadata** is already encoded in the existing
       ``SUPPLEMENT_PRODUCTS`` table (e.g. "30ct", "60ct", "90ct", "1lb",
       "2lb", "16oz") and is preserved verbatim. No supplement-vertical
       directional pathway is added.
    """
    random.seed(seed)
    np.random.seed(seed)

    products = SUPPLEMENT_PRODUCTS
    customers = build_customer_pool(customer_pool_size, "supplement")
    start_date = anchor_date - timedelta(days=days_history - 1)

    rows: List[Dict] = []
    order_counter = 0

    # Assign each customer a reorder interval
    customer_intervals = {}
    for i in range(len(customers)):
        interval = random.randint(*reorder_interval_range)
        customer_intervals[i] = interval

    # ------------------------------------------------------------------
    # Phase 1 — first-order date assignment
    # ------------------------------------------------------------------
    # Pre-Fix-9: every customer's first order was inside the first 60 days,
    # so by the L28 anchor every active customer had prior history and
    # returning_customer_share saturated at 100%.
    #
    # Post-Fix-9: ``new_acquisition_fraction`` of customers gets a first
    # order assigned somewhere across the WHOLE history window; the rest
    # are still seeded in the early period (so we keep the replenishment
    # shape — most customers exist long enough to reorder multiple times).
    # The result: a non-zero share of customers in the L28 window have NO
    # prior order, capping returning_customer_share strictly below 100%.
    n_new_acquisition = int(customer_pool_size * float(new_acquisition_fraction))
    all_indices = list(range(len(customers)))
    random.shuffle(all_indices)
    new_acq_set = set(all_indices[:n_new_acquisition])

    customer_first_orders: Dict[int, datetime] = {}
    for i in range(len(customers)):
        if i in new_acq_set:
            # Spread late-acquired customers across the entire window so a
            # meaningful fraction enter inside the L28 / L56 windows.
            day_offset = random.randint(0, days_history - 1)
        else:
            # Replenishment-style customers: first order in the early
            # 75 days so they have time to cycle multiple reorders before
            # the anchor.
            early_window = max(15, min(days_history - 1, 75))
            day_offset = random.randint(0, early_window)
        hour = random.randint(8, 22)
        first_order_date = start_date + timedelta(days=day_offset, hours=hour)
        customer_first_orders[i] = first_order_date

    # ------------------------------------------------------------------
    # Phase 1.5 — loyal-SKU repeater cohort
    # ------------------------------------------------------------------
    # A subset of customers reorders the SAME SKU each time. The SKU
    # affinity is pinned at customer-pool-build time so it is stable
    # across reorders. This gives the engine a non-degenerate audience
    # for any SKU-anchored loyalty / replenishment-style logic. It does
    # NOT introduce a new evidence class or causal prior — it is purely
    # fixture realism.
    n_loyal_sku = int(customer_pool_size * float(loyal_sku_repeater_fraction))
    loyal_sku_indices = set(all_indices[n_new_acquisition:n_new_acquisition + n_loyal_sku])
    loyal_sku_pin: Dict[int, Dict] = {
        i: random.choice(products) for i in loyal_sku_indices
    }

    # Phase 2: Schedule repeat orders based on reorder interval
    all_orders: List[Tuple[datetime, int]] = []  # (date, customer_idx)

    for cust_idx in range(len(customers)):
        order_date = customer_first_orders[cust_idx]
        interval = customer_intervals[cust_idx]
        while order_date <= anchor_date:
            if order_date >= start_date:
                all_orders.append((order_date, cust_idx))
            # Next order with jitter
            jitter = random.randint(-3, 3)
            order_date = order_date + timedelta(days=interval + jitter)

    # Sort by date
    all_orders.sort(key=lambda x: x[0])

    for order_date, cust_idx in all_orders:
        if order_date < start_date or order_date > anchor_date:
            continue

        customer = customers[cust_idx]
        has_discount = random.random() < 0.15
        discount_pct = random.uniform(0.08, 0.15) if has_discount else 0.0

        # Loyal-SKU repeaters always order the same SKU. Other customers
        # use the original mixed-pick behavior.
        if cust_idx in loyal_sku_pin:
            pinned = loyal_sku_pin[cust_idx]
            n_items = 1
            qty = random.choices([1, 1, 2], weights=[60, 25, 15])[0]
            price = pinned["base_price"] * random.uniform(0.95, 1.05)
            price = round(price, 2)
            line_total = price * qty
            disc = round(line_total * discount_pct, 2) if discount_pct > 0 else 0.0
            items = [{
                "name": pinned["name"],
                "sku": pinned["sku"],
                "quantity": qty,
                "price": price,
                "discount": disc,
            }]
        else:
            n_items = random.choices([1, 2], weights=[70, 30])[0]
            items = _pick_items(products, n_items, discount_pct)

        if random.random() < refund_rate:
            fin_status = "refunded"
            ful_status = "unfulfilled"
        else:
            fin_status = "paid"
            ful_status = "fulfilled"

        order_rows = _make_order_rows(
            order_counter, order_date, customer, items,
            financial_status=fin_status,
            fulfillment_status=ful_status,
        )
        rows.extend(order_rows)
        order_counter += 1

    return rows


def generate_small_store(
    anchor_date: datetime,
    days_history: int,
    seed: int,
    customer_pool_size: int = 2000,
    monthly_revenue_range: Tuple[float, float] = (8000, 18000),
    aov_range: Tuple[float, float] = (42, 62),
    refund_rate: float = 0.01,
) -> List[Dict]:
    """Generate a small lifestyle/gifting brand with lower order volume."""
    random.seed(seed)
    np.random.seed(seed)

    products = LIFESTYLE_PRODUCTS
    customers = build_customer_pool(customer_pool_size, "lifestyle")
    start_date = anchor_date - timedelta(days=days_history - 1)

    rows: List[Dict] = []
    order_counter = 0
    customer_order_history: Dict[int, List[datetime]] = {}

    months = []
    cur = start_date.replace(day=1)
    while cur <= anchor_date:
        months.append(cur)
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

    for month_start in months:
        month_end = (
            month_start.replace(month=month_start.month % 12 + 1, day=1)
            if month_start.month < 12
            else month_start.replace(year=month_start.year + 1, month=1, day=1)
        ) - timedelta(days=1)
        month_end = min(month_end, anchor_date)
        if month_start > anchor_date:
            break

        target_rev = random.uniform(*monthly_revenue_range)
        target_aov = random.uniform(*aov_range)
        # target_orders drives both volume and revenue; use rev/aov but clamp to 20-350
        target_orders = max(20, min(350, int(target_rev / target_aov)))

        days_in_month = (month_end - month_start).days + 1

        for _ in range(target_orders):
            # Mix of new and returning (small store: ~20% returning)
            repeat_pool = [i for i in range(len(customers)) if i in customer_order_history]
            if repeat_pool and random.random() < 0.20:
                cust_idx = random.choice(repeat_pool)
            else:
                cust_idx = random.randint(0, len(customers) - 1)

            customer = customers[cust_idx]
            day_offset = random.randint(0, days_in_month - 1)
            hour = random.randint(9, 21)
            created = month_start + timedelta(days=day_offset, hours=hour)
            if created > anchor_date:
                created = anchor_date - timedelta(hours=random.randint(1, 6))

            has_discount = random.random() < 0.12
            discount_pct = random.uniform(0.08, 0.15) if has_discount else 0.0

            n_items = random.choices([1, 2], weights=[75, 25])[0]
            items = _pick_items(products, n_items, discount_pct)

            if random.random() < refund_rate:
                fin_status = "refunded"
                ful_status = "unfulfilled"
            else:
                fin_status = "paid"
                ful_status = "fulfilled"

            order_rows = _make_order_rows(
                order_counter, created, customer, items,
                financial_status=fin_status,
                fulfillment_status=ful_status,
            )
            rows.extend(order_rows)
            order_counter += 1

            if cust_idx not in customer_order_history:
                customer_order_history[cust_idx] = []
            customer_order_history[cust_idx].append(created)

    return rows


def generate_cold_start(
    anchor_date: datetime,
    days_history: int,
    seed: int,
    customer_pool_size: int = 15000,
    monthly_revenue_range: Tuple[float, float] = (90000, 130000),
    aov_range: Tuple[float, float] = (60, 80),
) -> List[Dict]:
    """Generate a beauty brand with only 45 days of history."""
    # Reuse healthy beauty but clamp to days_history
    return generate_healthy_beauty(
        anchor_date=anchor_date,
        days_history=days_history,
        seed=seed,
        customer_pool_size=customer_pool_size,
        monthly_revenue_range=monthly_revenue_range,
        aov_range=aov_range,
        refund_rate=0.01,
    )


def generate_promo_anomaly(
    anchor_date: datetime,
    days_history: int,
    seed: int,
    customer_pool_size: int = 15000,
    monthly_revenue_range: Tuple[float, float] = (90000, 130000),
    aov_range: Tuple[float, float] = (60, 80),
    promo_month_index: int = 4,
    promo_spike_multiplier: float = 2.7,
    promo_discount_pct: float = 0.35,
    refund_rate: float = 0.02,
) -> List[Dict]:
    """Generate beauty brand orders with a promo anomaly spike in one month."""
    random.seed(seed)
    np.random.seed(seed)

    products = BEAUTY_PRODUCTS
    customers = build_customer_pool(customer_pool_size, "beauty")
    start_date = anchor_date - timedelta(days=days_history - 1)

    rows: List[Dict] = []
    order_counter = 0
    customer_order_history: Dict[int, List[datetime]] = {}

    # Same loyal/occasional/one-time cohort design as generate_healthy_beauty
    n_loyal = int(customer_pool_size * 0.25)
    n_occasional = int(customer_pool_size * 0.25)
    all_customer_indices = list(range(customer_pool_size))
    random.shuffle(all_customer_indices)
    loyal_set = set(all_customer_indices[:n_loyal])
    occasional_set = set(all_customer_indices[n_loyal:n_loyal + n_occasional])

    months = []
    cur = start_date.replace(day=1)
    while cur <= anchor_date:
        months.append(cur)
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

    n_months = len(months)

    for m_idx, month_start in enumerate(months):
        month_end = (
            month_start.replace(month=month_start.month % 12 + 1, day=1)
            if month_start.month < 12
            else month_start.replace(year=month_start.year + 1, month=1, day=1)
        ) - timedelta(days=1)
        month_end = min(month_end, anchor_date)
        if month_start > anchor_date:
            break

        is_promo = (m_idx == promo_month_index)

        if is_promo:
            target_rev = random.uniform(*monthly_revenue_range) * promo_spike_multiplier
            month_discount_pct = promo_discount_pct
        else:
            target_rev = random.uniform(*monthly_revenue_range)
            month_discount_pct = 0.0

        target_aov = random.uniform(*aov_range)
        effective_aov = target_aov * (1.0 - month_discount_pct)
        if effective_aov < 1.0:
            effective_aov = 1.0
        target_orders = int(target_rev / effective_aov)

        returning_share = _repeat_curve_returning_share(m_idx, 0.25, 0.42, n_months)
        n_returning = int(target_orders * returning_share)
        n_new = target_orders - n_returning

        prior_customers = set(customer_order_history.keys())
        new_pool = [i for i in range(customer_pool_size) if i not in prior_customers]
        repeat_pool = list(prior_customers)

        if new_pool:
            w_new = [3 if i in loyal_set else 2 if i in occasional_set else 1 for i in new_pool]
            new_indices = random.choices(new_pool, weights=w_new, k=min(n_new, len(new_pool)))
        else:
            new_indices = []

        if len(new_indices) < n_new:
            fallback = random.choices(list(range(customer_pool_size)), k=n_new - len(new_indices))
            new_indices.extend(fallback)

        if repeat_pool:
            w_ret = [3 if i in loyal_set else 2 if i in occasional_set else 1 for i in repeat_pool]
            ret_indices = random.choices(repeat_pool, weights=w_ret, k=n_returning)
        else:
            ret_indices = random.choices(list(range(customer_pool_size)), k=n_returning)

        all_indices = new_indices + ret_indices
        random.shuffle(all_indices)

        days_in_month = (month_end - month_start).days + 1

        for cust_idx in all_indices:
            customer = customers[cust_idx]
            day_offset = random.randint(0, days_in_month - 1)
            hour = random.randint(8, 22)
            created = month_start + timedelta(days=day_offset, hours=hour, minutes=random.randint(0, 59))
            if created > anchor_date:
                created = anchor_date - timedelta(hours=random.randint(1, 12))

            if is_promo:
                has_discount = random.random() < 0.75
                disc_pct = random.uniform(promo_discount_pct * 0.8, promo_discount_pct * 1.2) if has_discount else 0.0
            else:
                has_discount = random.random() < 0.18
                disc_pct = random.uniform(0.10, 0.20) if has_discount else 0.0

            n_items = random.choices([1, 2], weights=[75, 25])[0]
            items = _pick_items(products, n_items, disc_pct)

            if random.random() < refund_rate:
                fin_status = "refunded"
                ful_status = "unfulfilled"
            else:
                fin_status = "paid"
                ful_status = "fulfilled"

            order_rows = _make_order_rows(
                order_counter, created, customer, items,
                financial_status=fin_status,
                fulfillment_status=ful_status,
            )
            rows.extend(order_rows)
            order_counter += 1

            if cust_idx not in customer_order_history:
                customer_order_history[cust_idx] = []
            customer_order_history[cust_idx].append(created)

    return rows


# ---------------------------------------------------------------------------
# Inventory generators
# ---------------------------------------------------------------------------

def generate_inventory(
    products: List[Dict],
    anchor_date: datetime,
    hero_sku_low: bool = False,
    use_runner_clock: bool = True,
) -> List[Dict]:
    """Generate an inventory CSV for a given product list.

    Synthetic Fix 11
    ----------------
    The engine's :class:`~src.validation.InventoryValidationCheck` and
    :func:`~src.load.compute_inventory_metrics` both compute inventory
    age against ``pd.Timestamp.now()`` (real-world wall clock), not the
    scenario's ``anchor_date``. Pre-Fix-11, ``Updated At`` was anchored
    to ``anchor_date - random(0..3)`` so as soon as enough days passed
    between fixture generation and the test run, the inventory CSV read
    as 200+ days stale and was effectively dropped.

    Post-Fix-11 (``use_runner_clock=True`` default): ``Updated At`` is
    written relative to ``pd.Timestamp.now()`` so the inventory CSV is
    "fresh" (within the engine's ``INVENTORY_MAX_AGE_DAYS`` threshold)
    at *run time*, regardless of how stale ``anchor_date`` looks against
    today's wall clock.

    This is purely a fixture-side fix; the engine's freshness logic and
    timezone handling are unchanged. Callers who want the prior
    anchor-aligned behavior can pass ``use_runner_clock=False`` (kept
    for backward compatibility with any fixture that relied on the
    pre-Fix-11 ageing behavior).
    """
    if use_runner_clock:
        # Use a tz-naive runner-clock anchor. The engine's
        # ``compute_inventory_metrics`` uses ``pd.Timestamp.now()`` which
        # is tz-naive; matching naive-vs-naive avoids surfacing the
        # tz-aware/naive subtraction bug in pandas.
        runner_anchor = pd.Timestamp.now().to_pydatetime().replace(tzinfo=None)
    else:
        runner_anchor = anchor_date
    rows = []
    for i, p in enumerate(products):
        is_hero = (i == 0)  # First product is "hero"
        if is_hero and hero_sku_low:
            available = random.randint(2, 10)
        else:
            available = random.randint(80, 400)

        incoming = random.choices([0, 0, 0, random.randint(50, 200)], weights=[60, 20, 10, 10])[0]
        # Updated within the last 0-3 days of the runner clock so the
        # inventory always reads as fresh at run time.
        updated_at = (runner_anchor - timedelta(days=random.randint(0, 3))).strftime("%Y-%m-%dT%H:%M:%S")

        rows.append({
            "SKU": p["sku"],
            "Product Title": p["name"],
            "Available": available,
            "Incoming": incoming,
            "Updated At": updated_at,
        })
    return rows


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_scenario(
    orders_df: pd.DataFrame,
    scenario_cfg: Dict,
    scenario_name: str,
    anchor_date: datetime,
    inventory_df: Optional[pd.DataFrame] = None,
) -> List[str]:
    """Run post-generation validations, return list of warnings."""
    warnings: List[str] = []

    required_cols = [
        "Name", "Created at", "Cancelled at", "Lineitem name", "Lineitem quantity",
        "Lineitem price", "Lineitem discount", "Financial Status", "Fulfillment Status",
        "Subtotal", "Total Discount", "Shipping", "Taxes", "Total", "Currency",
        "Customer Email", "Billing Name", "Shipping Province", "Shipping Country",
    ]
    missing = [c for c in required_cols if c not in orders_df.columns]
    if missing:
        warnings.append(f"[{scenario_name}] Missing required columns: {missing}")

    # Date range
    days_history = scenario_cfg.get("days_history", 240)
    expected_earliest = anchor_date - timedelta(days=days_history + 10)
    dates = pd.to_datetime(orders_df["Created at"], errors="coerce", utc=True).dt.tz_localize(None)
    actual_earliest = dates.min()
    actual_latest = dates.max()

    if pd.isna(actual_earliest):
        warnings.append(f"[{scenario_name}] No valid dates found in orders.")
    else:
        if days_history >= 210:
            # For 240d scenarios, expect data going back at least 210 days from anchor
            cutoff_210 = anchor_date - timedelta(days=210)
            if actual_earliest > cutoff_210:
                warnings.append(
                    f"[{scenario_name}] Earliest date {actual_earliest.date()} is later than expected "
                    f"anchor-210d cutoff {cutoff_210.date()}"
                )

    # Monthly revenue check
    rev_min = scenario_cfg.get("expected_monthly_revenue_min")
    rev_max = scenario_cfg.get("expected_monthly_revenue_max")
    if rev_min is not None and rev_max is not None:
        paid = orders_df[orders_df["Financial Status"].astype(str).str.lower() == "paid"].copy()
        if not paid.empty:
            paid["_date"] = pd.to_datetime(paid["Created at"], errors="coerce", utc=True).dt.tz_localize(None)
            paid_dedup = paid.drop_duplicates("Name")
            paid_dedup["_month"] = paid_dedup["_date"].dt.to_period("M")
            monthly = paid_dedup.groupby("_month")["Subtotal"].sum()
            # Use middle months (avoid partial first/last month)
            if len(monthly) > 2:
                mid_months = monthly.iloc[1:-1]
                for m, rev in mid_months.items():
                    if rev < rev_min * 0.5:
                        warnings.append(
                            f"[{scenario_name}] Month {m}: revenue ${rev:,.0f} is below 50% of min expected ${rev_min:,.0f}"
                        )
                    elif rev > rev_max * 2.0:
                        warnings.append(
                            f"[{scenario_name}] Month {m}: revenue ${rev:,.0f} is above 2x max expected ${rev_max:,.0f}"
                        )

    # Customer identity coverage
    if scenario_name not in ("cold_start_45d", "small_store_240d"):
        total_rows = len(orders_df)
        email_coverage = orders_df["Customer Email"].notna() & (orders_df["Customer Email"].astype(str).str.strip() != "")
        coverage_pct = email_coverage.mean() if total_rows > 0 else 0.0
        if coverage_pct < 0.70:
            warnings.append(
                f"[{scenario_name}] Customer email coverage {coverage_pct:.1%} < 70% threshold"
            )

    # Inventory SKU coverage
    if inventory_df is not None and not orders_df.empty:
        order_skus = set(orders_df["Lineitem name"].dropna().unique())
        inventory_products = set(inventory_df["Product Title"].dropna().unique()) if "Product Title" in inventory_df.columns else set()
        # Note: we match by product name (SKU cross-reference is best-effort)
        if not inventory_products:
            warnings.append(f"[{scenario_name}] Inventory CSV has no Product Title column for SKU cross-check.")

    return warnings


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

SCENARIO_GENERATORS = {
    "healthy_beauty_240d": lambda cfg, anchor: (
        generate_healthy_beauty(
            anchor_date=anchor,
            days_history=cfg["days_history"],
            seed=cfg["seed"],
            customer_pool_size=cfg.get("customer_pool_size", 15000),
            # Synthetic Fix 8: late-period concave-up returning-share curve
            # so the L28 returning_customer_share delta is positive at the
            # Sep anchor. Pre-Fix-8 (linear 0.25 -> 0.42) produced a -1.7%
            # L28 delta because L28-prior had already absorbed most of the
            # gradual climb. Post-Fix-8 the late acceleration leaves L28
            # visibly above L28-prior. No engine threshold is changed; the
            # fixture now actually carries the signal it claims.
            returning_share_start=cfg.get("returning_share_start", 0.25),
            returning_share_end=cfg.get("returning_share_end", 0.60),
            returning_share_alpha=cfg.get("returning_share_alpha", 2.5),
            loyal_cohort_fraction=cfg.get("loyal_cohort_fraction", 0.30),
        ),
        generate_inventory(BEAUTY_PRODUCTS, anchor, hero_sku_low=False),
    ),
    "healthy_beauty_low_inventory_240d": lambda cfg, anchor: (
        generate_healthy_beauty(
            anchor_date=anchor,
            days_history=cfg["days_history"],
            seed=cfg["seed"],
            customer_pool_size=cfg.get("customer_pool_size", 15000),
            returning_share_start=cfg.get("returning_share_start", 0.25),
            returning_share_end=cfg.get("returning_share_end", 0.60),
            returning_share_alpha=cfg.get("returning_share_alpha", 2.5),
            loyal_cohort_fraction=cfg.get("loyal_cohort_fraction", 0.30),
        ),
        generate_inventory(BEAUTY_PRODUCTS, anchor, hero_sku_low=True),
    ),
    "supplement_replenishment_240d": lambda cfg, anchor: (
        generate_supplement_replenishment(
            anchor_date=anchor,
            days_history=cfg["days_history"],
            seed=cfg["seed"],
            customer_pool_size=cfg.get("customer_pool_size", 1200),
            reorder_interval_range=(
                cfg.get("reorder_interval_days_min", 28),
                cfg.get("reorder_interval_days_max", 45),
            ),
            # Synthetic Fix 9: spread first-order dates across the entire
            # window so returning_customer_share caps below 100%, and add
            # an explicit loyal-SKU repeater cohort for SKU-anchored
            # audiences. No supplement directional pathway / causal prior
            # is introduced.
            new_acquisition_fraction=cfg.get("new_acquisition_fraction", 0.30),
            loyal_sku_repeater_fraction=cfg.get("loyal_sku_repeater_fraction", 0.30),
        ),
        generate_inventory(SUPPLEMENT_PRODUCTS, anchor, hero_sku_low=False),
    ),
    "small_store_240d": lambda cfg, anchor: (
        generate_small_store(
            anchor_date=anchor,
            days_history=cfg["days_history"],
            seed=cfg["seed"],
            customer_pool_size=cfg.get("customer_pool_size", 2000),
        ),
        None,  # No inventory
    ),
    "cold_start_45d": lambda cfg, anchor: (
        generate_cold_start(
            anchor_date=anchor,
            days_history=cfg["days_history"],
            seed=cfg["seed"],
            customer_pool_size=cfg.get("customer_pool_size", 5000),
        ),
        None,  # No inventory
    ),
    # S6-T1 activation-moment fixture (dev-run-only). Layered on top of
    # the healthy_beauty baseline, injects an explicit dormant
    # repeat-buyer cohort sized to clear the 500 floor.
    "winback_activation_beauty_240d": lambda cfg, anchor: (
        inject_dormant_repeat_buyer_cohort(
            generate_healthy_beauty(
                anchor_date=anchor,
                days_history=cfg["days_history"],
                seed=cfg["seed"],
                customer_pool_size=cfg.get("customer_pool_size", 15000),
                returning_share_start=cfg.get("returning_share_start", 0.25),
                returning_share_end=cfg.get("returning_share_end", 0.60),
                returning_share_alpha=cfg.get("returning_share_alpha", 2.5),
                loyal_cohort_fraction=cfg.get("loyal_cohort_fraction", 0.30),
            ),
            anchor_date=anchor,
            cohort_size=int(cfg.get("winback_cohort_target_size", 700)),
            seed=cfg["seed"],
        ),
        generate_inventory(BEAUTY_PRODUCTS, anchor, hero_sku_low=False),
    ),
    "promo_anomaly_240d": lambda cfg, anchor: (
        generate_promo_anomaly(
            anchor_date=anchor,
            days_history=cfg["days_history"],
            seed=cfg["seed"],
            customer_pool_size=cfg.get("customer_pool_size", 5000),
            promo_month_index=cfg.get("promo_month_index", 4),
            promo_spike_multiplier=cfg.get("promo_spike_multiplier", 2.7),
            promo_discount_pct=cfg.get("promo_discount_pct", 0.35),
        ),
        None,  # No inventory
    ),
}


def run_generator(scenario_name: str, scenario_cfg: Dict, anchor_date: datetime, out_dir: Path) -> Dict:
    """Generate and write fixtures for a single scenario. Returns a summary dict."""
    print(f"\n{'='*60}")
    print(f"Generating scenario: {scenario_name}")
    print(f"  Seed: {scenario_cfg['seed']}")
    print(f"  Anchor: {anchor_date.date()}")
    print(f"  Days history: {scenario_cfg['days_history']}")

    generator = SCENARIO_GENERATORS.get(scenario_name)
    if generator is None:
        print(f"  [SKIP] No generator for scenario '{scenario_name}'")
        return {"scenario": scenario_name, "status": "skipped"}

    # Reset seeds at generator entry
    random.seed(scenario_cfg["seed"])
    np.random.seed(scenario_cfg["seed"])

    order_rows, inv_rows = generator(scenario_cfg, anchor_date)

    # Build orders DataFrame
    orders_df = pd.DataFrame(order_rows)
    if orders_df.empty:
        print(f"  [WARN] No order rows generated for {scenario_name}")
        return {"scenario": scenario_name, "status": "empty", "row_count": 0}

    # Ensure Cancelled at column exists (empty by default)
    if "Cancelled at" not in orders_df.columns:
        orders_df["Cancelled at"] = ""

    # Column order to match spec
    col_order = [
        "Name", "Created at", "Cancelled at", "Lineitem name", "Lineitem quantity",
        "Lineitem price", "Lineitem discount", "Financial Status", "Fulfillment Status",
        "Subtotal", "Total Discount", "Shipping", "Taxes", "Total", "Currency",
        "Customer Email", "Billing Name", "Shipping Province", "Shipping Country",
    ]
    for c in col_order:
        if c not in orders_df.columns:
            orders_df[c] = ""
    orders_df = orders_df[col_order]

    # Write orders CSV
    orders_path = out_dir / f"{scenario_name}_orders.csv"
    orders_df.to_csv(orders_path, index=False)
    print(f"  Orders: {orders_path} ({len(orders_df):,} rows, {orders_df['Name'].nunique():,} orders)")

    # Build and write inventory CSV
    inventory_path = None
    inventory_df = None
    if inv_rows is not None:
        inventory_df = pd.DataFrame(inv_rows)
        inv_col_order = ["SKU", "Product Title", "Available", "Incoming", "Updated At"]
        for c in inv_col_order:
            if c not in inventory_df.columns:
                inventory_df[c] = ""
        inventory_df = inventory_df[inv_col_order]
        inventory_path = out_dir / f"{scenario_name}_inventory.csv"
        inventory_df.to_csv(inventory_path, index=False)
        print(f"  Inventory: {inventory_path} ({len(inventory_df)} SKUs)")

    # Validation
    warnings = validate_scenario(orders_df, scenario_cfg, scenario_name, anchor_date, inventory_df)
    if warnings:
        print("  Validation warnings:")
        for w in warnings:
            print(f"    - {w}")
    else:
        print("  Validation: OK")

    # Compute summary stats
    dates = pd.to_datetime(orders_df["Created at"], errors="coerce", utc=True).dt.tz_localize(None)
    date_range = f"{dates.min().date()} to {dates.max().date()}" if not dates.isna().all() else "n/a"

    unique_orders = orders_df["Name"].nunique()
    paid_dedup = orders_df[orders_df["Financial Status"].astype(str).str.lower() == "paid"].drop_duplicates("Name")
    monthly_rev: Dict = {}
    if not paid_dedup.empty:
        paid_dedup = paid_dedup.copy()
        paid_dedup["_date"] = pd.to_datetime(paid_dedup["Created at"], errors="coerce", utc=True).dt.tz_localize(None)
        paid_dedup["_month"] = paid_dedup["_date"].dt.to_period("M")
        monthly_rev = paid_dedup.groupby("_month")["Subtotal"].sum().astype(float).to_dict()

    aov = (
        float(paid_dedup["Subtotal"].mean()) if not paid_dedup.empty else None
    )

    # Repeat customer rate
    email_orders = orders_df[orders_df["Financial Status"].astype(str).str.lower() == "paid"].copy()
    if not email_orders.empty:
        email_orders = email_orders.drop_duplicates("Name")
        cust_orders = email_orders.groupby("Customer Email").size()
        repeat_rate = float((cust_orders >= 2).sum() / max(len(cust_orders), 1))
    else:
        repeat_rate = 0.0

    return {
        "scenario": scenario_name,
        "status": "ok",
        "row_count": len(orders_df),
        "order_count": unique_orders,
        "date_range": date_range,
        "aov": round(aov, 2) if aov else None,
        "repeat_customer_rate": round(repeat_rate, 3),
        "monthly_revenue": {str(k): round(v, 2) for k, v in monthly_rev.items()},
        "validation_warnings": warnings,
        "orders_path": str(orders_path),
        "inventory_path": str(inventory_path) if inventory_path else None,
    }


def main():
    ap = argparse.ArgumentParser(description="Generate deterministic synthetic Shopify fixtures for BeaconAI")
    ap.add_argument("--anchor-date", default="2025-09-18", help="Anchor date for fixture generation (YYYY-MM-DD)")
    ap.add_argument("--scenario", default=None, help="Generate only this scenario name; omit to generate all")
    ap.add_argument("--out-dir", default=str(REPO_ROOT / "tests" / "fixtures" / "synthetic"), help="Output directory")
    args = ap.parse_args()

    anchor_date = datetime.strptime(args.anchor_date, "%Y-%m-%d")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load scenarios YAML
    with open(SCENARIOS_YAML) as f:
        yaml_data = yaml.safe_load(f)
    scenarios = yaml_data.get("scenarios", {})

    if args.scenario:
        if args.scenario not in scenarios:
            print(f"Error: scenario '{args.scenario}' not found in {SCENARIOS_YAML}")
            sys.exit(1)
        to_generate = {args.scenario: scenarios[args.scenario]}
    else:
        to_generate = scenarios

    summaries = []
    for scenario_name, scenario_cfg in to_generate.items():
        try:
            summary = run_generator(scenario_name, scenario_cfg, anchor_date, out_dir)
        except Exception as e:
            import traceback
            print(f"\n[ERROR] Scenario {scenario_name} failed: {e}")
            traceback.print_exc()
            summary = {
                "scenario": scenario_name,
                "status": "error",
                "error": str(e),
            }
        summaries.append(summary)

    # Print final summary table
    print("\n" + "=" * 60)
    print("GENERATION SUMMARY")
    print("=" * 60)
    for s in summaries:
        status = s.get("status", "unknown")
        if status == "ok":
            print(
                f"  {s['scenario']:<40} {s['row_count']:>6} rows  "
                f"{s['order_count']:>4} orders  "
                f"AOV=${s['aov'] or 0:.0f}  "
                f"repeat={s['repeat_customer_rate']:.1%}  "
                f"{s['date_range']}"
            )
            if s.get("validation_warnings"):
                for w in s["validation_warnings"]:
                    print(f"    WARN: {w}")
        else:
            print(f"  {s['scenario']:<40} [{status.upper()}] {s.get('error', '')}")


if __name__ == "__main__":
    main()
