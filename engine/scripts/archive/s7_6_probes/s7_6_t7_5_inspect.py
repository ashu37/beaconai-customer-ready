"""S7.6-T7.5 direct builder inspection on Beauty + Supplements fixtures.

Bypasses the slate pipeline to call aov_lift_via_threshold_bundle_candidates
directly so we can see: L90 order count, computed threshold, threshold_source,
audience_size, and reason. No engine run, no side effects.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402
from src import audience_builders as ab  # noqa: E402


def _probe(label: str, orders_csv: str, vertical: str, flag_on: bool):
    print(f"\n=== {label} (vertical={vertical}, flag={'ON' if flag_on else 'OFF'}) ===")
    df = pd.read_csv(orders_csv)
    print(f"orders csv rows: {len(df)}")
    print(f"columns: {list(df.columns)}")
    # Mirror engine canonicalization minimally — the builder expects
    # Created at, customer_id, net_sales.
    # Try to find/coerce columns.
    g = df.copy()
    # most fixtures already use lowercase + standard names; check
    if "Created at" not in g.columns:
        for c in ("created_at", "Created At", "created at"):
            if c in g.columns:
                g = g.rename(columns={c: "Created at"})
                break
    if "customer_id" not in g.columns:
        for c in ("Customer Email", "Email", "email", "Customer ID"):
            if c in g.columns:
                g = g.rename(columns={c: "customer_id"})
                break
    if "net_sales" not in g.columns:
        for c in ("Subtotal", "Total", "subtotal", "total", "Net Sales"):
            if c in g.columns:
                g = g.rename(columns={c: "net_sales"})
                break
    g["Created at"] = pd.to_datetime(g["Created at"], errors="coerce")
    g["net_sales"] = pd.to_numeric(g["net_sales"], errors="coerce")
    g = g[~g["Created at"].isna() & ~g["net_sales"].isna()]
    maxd = g["Created at"].max()
    l90_start = maxd - pd.Timedelta(days=90)
    gl90 = g[g["Created at"] >= l90_start]
    print(f"L90 order rows: {len(gl90)}")
    if len(gl90) >= 200:
        import numpy as np
        p60 = float(np.percentile(gl90["net_sales"].to_numpy(), 60))
        print(f"L90 P60 net_sales: {p60:.4f}")
        print(f"band would be: [{p60-15:.2f}, {p60-5:.2f}]")

    cfg = {
        "VERTICAL_MODE": vertical,
        "ENGINE_V2_AOV_THRESHOLD_FROM_DATA": flag_on,
        # No cfg threshold — force data-derived path
    }
    res = ab.aov_lift_via_threshold_bundle_candidates(g, {}, cfg)
    print(f"audience_size       : {res.audience_size}")
    print(f"rejection_reason    : {res.preliminary_rejection_reason}")
    print(f"threshold_source    : {res.threshold_source}")
    print(f"segment_definition  : {res.segment_definition}")


def main():
    _probe(
        "healthy_beauty_240d",
        "tests/fixtures/synthetic/healthy_beauty_240d_orders.csv",
        "beauty",
        True,
    )
    _probe(
        "healthy_supplements_240d",
        "tests/fixtures/synthetic/healthy_supplements_240d_orders.csv",
        "supplements",
        True,
    )
    # Also OFF for Beauty as a baseline
    _probe(
        "healthy_beauty_240d",
        "tests/fixtures/synthetic/healthy_beauty_240d_orders.csv",
        "beauty",
        False,
    )


if __name__ == "__main__":
    main()
