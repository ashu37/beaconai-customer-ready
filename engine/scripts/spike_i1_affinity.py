"""i1-spike Day 1 risk check: 2-pair co-occurrence on Beauty fixture.

Hand-rolled (stdlib + pandas only). For each of the 45 pairs over 10 SKUs:
- support, lift, "bought-A-not-B" audience size (by customer)
Picks top 3 by lift where consequent is the top-revenue SKU AND
audience size >= 500. Then computes Jaccard overlap of the strongest
candidate's "bought-A-not-B" audience against the legacy
``bestseller_buyers`` audience (top-SKU buyers).

Spike-only. Not wired into engine. Reproduces memo §3 viability check.
"""

from __future__ import annotations

import csv
import itertools
from collections import defaultdict
from pathlib import Path
from typing import Dict, FrozenSet, Set, Tuple

ROOT = Path("/Users/atul.jena/Projects/Personal/beaconai")
ORDERS = ROOT / "tests/fixtures/synthetic/healthy_beauty_240d_orders.csv"


def load_customer_sku_sets() -> Tuple[Dict[str, Set[str]], Dict[str, float]]:
    """Return {customer_email -> set(sku_name)} and {sku_name -> revenue}."""
    cust_to_skus: Dict[str, Set[str]] = defaultdict(set)
    sku_revenue: Dict[str, float] = defaultdict(float)
    with ORDERS.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            cust = (row.get("Customer Email") or "").strip()
            sku = (row.get("Lineitem name") or "").strip()
            if not cust or not sku:
                continue
            cust_to_skus[cust].add(sku)
            try:
                qty = float(row.get("Lineitem quantity") or 0)
                price = float(row.get("Lineitem price") or 0)
                sku_revenue[sku] += qty * price
            except ValueError:
                pass
    return cust_to_skus, sku_revenue


def main() -> None:
    cust_to_skus, sku_revenue = load_customer_sku_sets()
    n_customers = len(cust_to_skus)
    skus = sorted({s for skus in cust_to_skus.values() for s in skus})
    print(f"Customers (with email): {n_customers}")
    print(f"Distinct SKUs: {len(skus)}")
    top_sku = max(sku_revenue.items(), key=lambda kv: kv[1])[0]
    print(f"Top revenue SKU: {top_sku}  (rev=${sku_revenue[top_sku]:,.0f})")
    print()

    # Buyers of each SKU (customer set).
    sku_buyers: Dict[str, Set[str]] = {s: set() for s in skus}
    for cust, sset in cust_to_skus.items():
        for s in sset:
            sku_buyers[s].add(cust)

    # All 45 ordered pairs (we evaluate both directions A->B, B->A as
    # "consequent" candidacy is asymmetric; legacy slot uses top SKU).
    rows = []
    for a, b in itertools.combinations(skus, 2):
        for ant, cons in ((a, b), (b, a)):
            ant_set = sku_buyers[ant]
            cons_set = sku_buyers[cons]
            both = ant_set & cons_set
            n_both = len(both)
            n_ant = len(ant_set)
            n_cons = len(cons_set)
            support_pair = n_both / n_customers if n_customers else 0.0
            p_ant = n_ant / n_customers if n_customers else 0.0
            p_cons = n_cons / n_customers if n_customers else 0.0
            # Lift = P(ant ^ cons) / (P(ant)*P(cons))
            lift = (
                support_pair / (p_ant * p_cons)
                if (p_ant > 0 and p_cons > 0)
                else 0.0
            )
            audience = ant_set - cons_set  # bought ant, NOT cons
            rows.append(
                {
                    "antecedent": ant,
                    "consequent": cons,
                    "n_ant": n_ant,
                    "n_cons": n_cons,
                    "n_both": n_both,
                    "support_pair": support_pair,
                    "lift": lift,
                    "audience_size": len(audience),
                    "audience_set": audience,
                }
            )

    # Filter: consequent must be top-revenue SKU AND audience_size >= 500.
    qualified = [
        r
        for r in rows
        if r["consequent"] == top_sku and r["audience_size"] >= 500
    ]
    qualified.sort(key=lambda r: r["lift"], reverse=True)
    print(f"Qualifying pairs (consequent={top_sku}, audience>=500): {len(qualified)}")
    print()
    print(
        f"{'antecedent':<35} {'consequent':<35} "
        f"{'support':>8} {'lift':>6} {'aud_size':>9} {'n_ant':>6} {'n_cons':>6}"
    )
    for r in qualified[:10]:
        print(
            f"{r['antecedent']:<35} {r['consequent']:<35} "
            f"{r['support_pair']:>8.4f} {r['lift']:>6.3f} "
            f"{r['audience_size']:>9d} {r['n_ant']:>6d} {r['n_cons']:>6d}"
        )

    # Also report the strongest pairs unrestricted by consequent.
    print()
    print("Top 5 pairs by lift overall (any consequent):")
    rows_sorted = sorted(rows, key=lambda r: r["lift"], reverse=True)
    seen = set()
    for r in rows_sorted:
        key = frozenset({r["antecedent"], r["consequent"]})
        if key in seen:
            continue
        seen.add(key)
        print(
            f"  {r['antecedent']} <-> {r['consequent']}: "
            f"lift={r['lift']:.3f} support={r['support_pair']:.4f} "
            f"aud(A-not-B)={r['audience_size']}"
        )
        if len(seen) >= 5:
            break

    # Jaccard vs legacy bestseller_buyers (top-SKU buyer set).
    legacy_audience = sku_buyers[top_sku]
    print()
    print(f"Legacy bestseller_buyers audience size (buyers of {top_sku}): {len(legacy_audience)}")
    if qualified:
        strongest = qualified[0]
        a = strongest["audience_set"]
        b = legacy_audience
        jacc = len(a & b) / len(a | b) if (a | b) else 0.0
        print(
            f"Strongest qualifying candidate: "
            f"ant={strongest['antecedent']} cons={strongest['consequent']} "
            f"lift={strongest['lift']:.3f} aud={strongest['audience_size']}"
        )
        print(f"Jaccard vs legacy bestseller_buyers: {jacc:.4f}")
        # By construction, a = buyers(ant) - buyers(top_sku); b = buyers(top_sku).
        # a ∩ b = empty by construction. So Jaccard = 0/(|a|+|b|) = 0.
        # That's the *desired* outcome for overlap gate (< 0.30) but it
        # also tells us the audiences are disjoint by construction.
    else:
        print("No qualifying pair; halt criterion #1 fires.")


if __name__ == "__main__":
    main()
