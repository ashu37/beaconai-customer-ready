"""In-process probe: parse the engine_run.json from the harness run and
look for the candidate-stage audience_size for replenishment_due, which
is captured BEFORE the audience-level floor is applied. Also dump
per-SKU bucket repeater distribution from the raw Beauty orders CSV.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.synthetic_harness import run_scenario  # noqa: E402

ENV = {
    "ENGINE_V2_OUTPUT": "true",
    "ENGINE_V2_DECIDE": "true",
    "ENGINE_V2_SLATE": "true",
    "ENGINE_V2_SIZING": "true",
    "ENGINE_V2_PRIORS_VALIDATION": "true",
    "ENGINE_V2_STORE_PROFILE": "true",
    "VERTICAL_MODE": "beauty",
    "WINDOW_POLICY": "auto",
    "ENGINE_V2_OBSERVED_EFFECT_REPLENISHMENT": "true",
    "ENGINE_V2_BUILDER_REPLENISHMENT_DUE": "true",
}


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td) / "probe"
        r = run_scenario("healthy_beauty_240d", out_dir, env_overrides=ENV, timeout_sec=300)
        if r.returncode != 0:
            print(r.stderr[-1500:])
            return 1
        run = json.loads((out_dir / "receipts" / "engine_run.json").read_text())

        # Look in candidates pool for replenishment_due
        for key in ("candidates", "candidate_audiences", "audience_candidates", "audiences"):
            cands = run.get(key)
            if cands:
                print(f"--- {key} ({len(cands)}) ---")
                for c in cands:
                    pid = c.get("play_id") or c.get("id") or "?"
                    if "replen" in str(pid).lower():
                        print(f"  {pid}: {json.dumps(c, default=str)[:600]}")
                break

        # Try to find replenishment_due across recommendations + considered + experiments + watching with full payload
        for sec_name in ("recommendations", "considered", "experiments", "watching", "recommended_experiments"):
            for item in (run.get(sec_name) or []):
                pid = item.get("play_id") or ""
                if "replen" in str(pid).lower():
                    print(f"\n--- in {sec_name}: {pid} ---")
                    # Show audience-related keys
                    for k in ("audience_size", "audience", "audience_definition", "preliminary_rejection_reason",
                              "reason", "reason_code", "segment_definition", "data_used"):
                        if k in item:
                            print(f"  {k}: {item[k]}")

        # Direct SKU diagnostics from raw CSV
        print("\n--- Direct SKU repeater diagnostics from Beauty orders CSV ---")
        import pandas as pd
        from src.replenishment_parser import get_size_regex
        import re as _re

        orders_csv = REPO_ROOT / "tests/fixtures/synthetic/healthy_beauty_240d_orders.csv"
        if not orders_csv.exists():
            # Try alternate paths
            for cand in REPO_ROOT.glob("tests/fixtures/**/healthy_beauty_240d*orders*.csv"):
                orders_csv = cand
                break
        print(f"orders_csv = {orders_csv}")
        df = pd.read_csv(orders_csv)
        # find SKU/lineitem col
        cols = [c for c in df.columns if "ineitem" in c.lower() or "sku" in c.lower() or "product" in c.lower()]
        print(f"line-item-ish columns: {cols}")
        sku_col = None
        for c in ("Lineitem name", "Lineitem sku", "Lineitem", "lineitem_name"):
            if c in df.columns:
                sku_col = c
                break
        if sku_col is None and cols:
            sku_col = cols[0]
        print(f"using sku_col = {sku_col}")
        cust_col = "Email" if "Email" in df.columns else ("customer_id" if "customer_id" in df.columns else None)
        for c in ("Customer ID", "customer id"):
            if c in df.columns and cust_col is None:
                cust_col = c
        print(f"using cust_col = {cust_col}")

        rx = get_size_regex("beauty")
        def _key(text):
            if not rx:
                return None
            m = _re.search(rx, text or "", flags=_re.IGNORECASE)
            if m is None:
                return None
            try:
                return str(m.group(0))
            except IndexError:
                return text

        df["_sku_key"] = df[sku_col].astype(str).map(_key)
        valid = df[df["_sku_key"].notna() & (df["_sku_key"] != "")]
        print(f"matched-rows={len(valid)} unique-keys={valid['_sku_key'].nunique()}")
        floors = [3, 5, 8, 10, 12, 15, 20, 30]
        by_floor = {f: 0 for f in floors}
        repeater_counts = []
        for sku, sub in valid.groupby("_sku_key"):
            cust_counts = sub.groupby(cust_col).size()
            repeaters = int((cust_counts >= 2).sum())
            repeater_counts.append((sku, repeaters))
            for f in floors:
                if repeaters >= f:
                    by_floor[f] += 1
        print(f"per-SKU bucket SKUs clearing each floor: {by_floor}")
        repeater_counts.sort(key=lambda x: -x[1])
        print("top 20 SKU buckets by repeater count:")
        for sku, rc in repeater_counts[:20]:
            print(f"  {sku!r}: {rc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
