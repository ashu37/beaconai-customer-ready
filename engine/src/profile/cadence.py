"""Right-censored empirical median reorder cadence per SKU class
(Sprint 6.5 Ticket T3).

MVP: pure-pandas empirical-median inter-purchase-gap estimate per
sub-vertical-tagged SKU class. K-M lifts the censored-customers
contribution at S11. The D-6 invariant forbids ``lifelines`` /
``sklearn`` / ``statsmodels`` / ``implicit`` / ``lightfm`` in this
module — pandas + numpy + builtins only.

Algorithm (per IM plan §S6.5-T3):

1. Each order line is tagged with a SKU class (sub-vertical token-vote
   from the T2 taxonomy assignment, e.g. ``skincare`` / ``cosmetics``
   / ``protein`` / ``multivitamin``). The caller passes
   ``subvertical_sku_assignment``, a map ``{product_title -> sku_class}``.
2. Per customer × SKU class: order timestamps in ascending order.
3. Inter-purchase gaps (days) per consecutive pair within the same
   class.
4. Customers with **only 1** purchase in a SKU class are right-censored:
   they do NOT contribute to the empirical median (K-M will recover them
   in S11).
5. If a SKU class has fewer than 30 customers contributing ≥1 gap,
   method=``"INSUFFICIENT_DATA"``, baseline=``None`` for that class.
6. Otherwise: ``median_reorder_days[class] = int(round(median(gaps)))``,
   method=``"empirical_median"``.
7. ``global_median_reorder_days`` = pooled median across all classes
   that produced a baseline, else ``None``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from .types import CadenceBaseline


_MIN_CUSTOMERS_PER_CLASS = 30


def _tokenize(title: str) -> str:
    if not isinstance(title, str):
        return ""
    return " ".join(title.lower().split())


def _assign_sku_class_via_taxonomy(
    title: str,
    vertical_cfg: Dict[str, Any],
) -> Optional[str]:
    """Vote one product title to its argmax sub-vertical (positive scores
    only; ties drop). Mirrors ``detect_subvertical`` per-SKU scoring."""

    tokenized = _tokenize(title)
    if not tokenized:
        return None
    best: Optional[str] = None
    best_score = 0
    tie = False
    for subv, block in (vertical_cfg or {}).items():
        if not isinstance(block, dict):
            continue
        tokens = block.get("tokens") or []
        excluded = block.get("excluded_tokens") or []
        pos = sum(
            1
            for tok in tokens
            if isinstance(tok, str) and tok and tok.lower() in tokenized
        )
        neg = sum(
            1
            for tok in excluded
            if isinstance(tok, str) and tok and tok.lower() in tokenized
        )
        score = pos - neg
        if score <= 0:
            continue
        if score > best_score:
            best = subv
            best_score = score
            tie = False
        elif score == best_score:
            tie = True
    if tie or best is None:
        return None
    return best


def build_subvertical_sku_assignment(
    g: pd.DataFrame,
    vertical: str,
    taxonomy_config: Dict[str, Any],
) -> Dict[str, str]:
    """Build ``{product_title -> sub_vertical}`` for the orders DataFrame.

    Only titles with a unique positive-score sub-vertical are returned;
    untaggable titles are omitted.
    """

    if g is None or len(g) == 0:
        return {}
    title_col = None
    for c in ("product", "lineitem_any", "Lineitem name"):
        if c in g.columns:
            title_col = c
            break
    if title_col is None:
        return {}

    verticals_cfg = (taxonomy_config or {}).get("verticals") or {}
    vertical_cfg = verticals_cfg.get(vertical) or {}
    if not vertical_cfg:
        return {}

    assignment: Dict[str, str] = {}
    for t in g[title_col].astype(str).unique():
        klass = _assign_sku_class_via_taxonomy(t, vertical_cfg)
        if klass is not None:
            assignment[t] = klass
    return assignment


def compute_cadence_baseline(
    aligned: pd.DataFrame,
    subvertical_sku_assignment: Dict[str, str],
) -> CadenceBaseline:
    """Pure-pandas right-censored empirical-median cadence per SKU class.

    Args:
        aligned: orders DataFrame; must contain ``customer_id``,
            ``Created at``, and a product-title column
            (``product`` / ``lineitem_any`` / ``Lineitem name``).
        subvertical_sku_assignment: ``{product_title -> sku_class}``.
            Order lines whose title is not in the map do not contribute
            to any class.

    Returns:
        ``CadenceBaseline`` with ``detection_status="COMPUTED"``
        (or ``"INSUFFICIENT_DATA"`` if no class crossed the N=30 floor).
    """

    if aligned is None or len(aligned) == 0 or not subvertical_sku_assignment:
        return CadenceBaseline(detection_status="INSUFFICIENT_DATA")

    title_col = None
    for c in ("product", "lineitem_any", "Lineitem name"):
        if c in aligned.columns:
            title_col = c
            break
    if title_col is None or "Created at" not in aligned.columns or "customer_id" not in aligned.columns:
        return CadenceBaseline(detection_status="INSUFFICIENT_DATA")

    titles = aligned[title_col].astype(str)
    classes = titles.map(subvertical_sku_assignment)
    mask = classes.notna()
    if not mask.any():
        return CadenceBaseline(detection_status="INSUFFICIENT_DATA")

    sub = pd.DataFrame({
        "customer_id": aligned.loc[mask, "customer_id"].astype(str).values,
        "created": pd.to_datetime(aligned.loc[mask, "Created at"], errors="coerce").values,
        "sku_class": classes.loc[mask].astype(str).values,
    })
    sub = sub.dropna(subset=["created"])
    if len(sub) == 0:
        return CadenceBaseline(detection_status="INSUFFICIENT_DATA")

    median_by_class: Dict[str, int] = {}
    method_by_class: Dict[str, str] = {}
    all_gap_days: list = []

    for klass, grp in sub.groupby("sku_class"):
        # Customers with >=2 in-class purchases contribute gaps; singletons
        # are right-censored and dropped from the median.
        per_cust_counts = grp.groupby("customer_id").size()
        contributing_customers = per_cust_counts[per_cust_counts >= 2].index
        if len(contributing_customers) < _MIN_CUSTOMERS_PER_CLASS:
            method_by_class[klass] = "INSUFFICIENT_DATA"
            continue

        gaps_days: list = []
        contrib = grp[grp["customer_id"].isin(contributing_customers)].sort_values(
            ["customer_id", "created"]
        )
        for _, cust_grp in contrib.groupby("customer_id"):
            ts = cust_grp["created"].sort_values().values
            if len(ts) < 2:
                continue
            diffs = np.diff(ts).astype("timedelta64[D]").astype(int)
            diffs = diffs[diffs > 0]
            if len(diffs) > 0:
                gaps_days.extend(diffs.tolist())

        if not gaps_days:
            method_by_class[klass] = "INSUFFICIENT_DATA"
            continue

        median_days = int(round(float(np.median(gaps_days))))
        median_by_class[klass] = median_days
        method_by_class[klass] = "empirical_median"
        all_gap_days.extend(gaps_days)

    global_median: Optional[int] = (
        int(round(float(np.median(all_gap_days)))) if all_gap_days else None
    )
    detection_status = "COMPUTED" if median_by_class else "INSUFFICIENT_DATA"

    return CadenceBaseline(
        median_reorder_days_by_sku_class=median_by_class,
        method_by_sku_class=method_by_class,
        global_median_reorder_days=global_median,
        detection_status=detection_status,
    )
