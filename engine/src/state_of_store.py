"""State-of-store typed Observation builder (Milestone 1, T1.4).

The PM-Q2 contract specifies a typed list of facts for the briefing's
"state of store" paragraph. M1 produces 3-5 ``Observation`` records as
typed data only — no prose templating, no rendering. M8 will assemble
English copy from this list; a future LLM-narrator (Phase 3+) will read
the same list.

Inputs:
- ``aligned``: the L7/L28/L56/L90 KPI snapshot from
  ``utils.kpi_snapshot_with_deltas``. Values may be missing/None.
- ``scale``: the merchant scale dict (monthly_revenue, customer base,
  etc.). Optional, used for Observation framing.

Outputs:
- ``list[Observation]``: 3-5 entries, deterministic in order. Always
  produces at least 3 even when data is sparse (uses ``classification =
  HELD`` for unknown deltas to keep the contract stable).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .engine_run import Observation, ObservationClassification


def _safe_get(d: Optional[Dict[str, Any]], path: List[str], default: Any = None) -> Any:
    if not isinstance(d, dict):
        return default
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _classify_delta(delta: Optional[float], threshold: float = 0.01) -> ObservationClassification:
    """Tiny helper: any delta beyond ``threshold`` is MOVED, else HELD.

    M1 keeps this simple. M5+ will introduce the anomalous classification
    when paired with anomaly detector output.
    """
    if delta is None:
        return ObservationClassification.HELD
    try:
        return (
            ObservationClassification.MOVED
            if abs(float(delta)) > float(threshold)
            else ObservationClassification.HELD
        )
    except (TypeError, ValueError):
        return ObservationClassification.HELD


def _fmt_pct(x: Optional[float]) -> str:
    if x is None:
        return "—"
    try:
        return f"{float(x) * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_money(x: Optional[float]) -> str:
    if x is None:
        return "—"
    try:
        return f"${float(x):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _has_identified_customers(aligned: Optional[Dict[str, Any]]) -> bool:
    """True if the L28 window has at least 1 identified customer.

    Phase 5.3: when no customers are identified in the window the
    repeat_rate metric is structurally ``None``-or-``0`` because the
    denominator is empty. We surface a "not computed" label rather than
    rendering a misleading "0.0%".
    """
    meta = _safe_get(aligned, ["L28", "meta"])
    if not isinstance(meta, dict):
        return True  # default to not-suppressing if the meta block is absent
    try:
        return int(meta.get("identified_recent") or 0) > 0
    except (TypeError, ValueError):
        return True


def build_observations(
    aligned: Optional[Dict[str, Any]],
    scale: Optional[Dict[str, Any]] = None,
    data_quality_flags: Optional[List[str]] = None,
    *,
    n_days_observed: int = 0,
    n_days_expected: int = 0,
) -> List[Observation]:
    """Produce 3-5 typed Observations for the EngineRun.state_of_store list.

    M1 contract:
    - Always returns >= 3 Observations when ``aligned`` is non-empty.
    - Uses HELD classification for unknown/no-change facts.
    - Surfaces data quality flags as ANOMALOUS observations when present.
    - No prose templating; only typed numerics (S13.6-T1b stripped the
      ``Observation.text`` slot per Pivot 2; renderer synthesizes the
      state-of-store sentence from typed fields).

    Phase 5.3 additions:
    - Adds ``returning_customer_share`` and ``net_sales`` observations
      so the watching section has more than three slots to choose from.
    - Suppresses or clearly labels ``repeat_rate_within_window`` when
      the L28 window has zero identified customers (the metric would
      otherwise render as a misleading "0.0%").
    """
    aligned = aligned or {}
    flags = list(data_quality_flags or [])
    obs: List[Observation] = []

    # ---- AOV delta ---------------------------------------------------------
    aov_now = _safe_get(aligned, ["L28", "aov"])
    aov_delta = _safe_get(aligned, ["L28", "delta", "aov"])
    # KI-26 fix: prior values live at ``aligned["L28"]["prior"][<metric>]``
    # (produced by ``utils.kpi_snapshot_with_deltas``), NOT under a
    # top-level ``L28_prior`` key. The previous read path returned
    # ``None`` on every fixture; the typed Observation slot ``prior``
    # was effectively dormant. Fix populates the reserved 6B C2/C3 slot
    # for both Beauty and supplements consistently — no merchant-facing
    # HTML change (renderer never read ``Observation.prior``).
    aov_prior = _safe_get(aligned, ["L28", "prior", "aov"])
    obs.append(
        Observation(
            supporting_metric="aov",
            change_magnitude=float(aov_delta) if isinstance(aov_delta, (int, float)) else None,
            classification=_classify_delta(aov_delta, threshold=0.01),
            current=float(aov_now) if isinstance(aov_now, (int, float)) else None,
            prior=float(aov_prior) if isinstance(aov_prior, (int, float)) else None,
            delta_pct=float(aov_delta) if isinstance(aov_delta, (int, float)) else None,
        )
    )

    # ---- Repeat-rate delta -------------------------------------------------
    # Phase 5.3: when no identified customers exist in the window, repeat
    # rate is structurally not computable. Surface a "not computed" label
    # instead of a misleading "0.0%" reading.
    rr_now = _safe_get(aligned, ["L28", "repeat_rate_within_window"])
    rr_delta = _safe_get(aligned, ["L28", "delta", "repeat_rate_within_window"])
    if not _has_identified_customers(aligned) or rr_now is None:
        obs.append(
            Observation(
                supporting_metric="repeat_rate_within_window",
                change_magnitude=None,
                classification=ObservationClassification.HELD,
            )
        )
    else:
        rr_prior = _safe_get(aligned, ["L28", "prior", "repeat_rate_within_window"])
        obs.append(
            Observation(
                supporting_metric="repeat_rate_within_window",
                change_magnitude=float(rr_delta) if isinstance(rr_delta, (int, float)) else None,
                classification=_classify_delta(rr_delta, threshold=0.005),
                current=float(rr_now) if isinstance(rr_now, (int, float)) else None,
                prior=float(rr_prior) if isinstance(rr_prior, (int, float)) else None,
                delta_pct=float(rr_delta) if isinstance(rr_delta, (int, float)) else None,
            )
        )

    # ---- Top-product velocity (orders proxy in M1) ------------------------
    # We don't have a top-product channel in `aligned` directly; we use orders
    # as a velocity proxy here. M2/M3 will refine to a per-SKU observation
    # once the play registry is wired.
    orders_now = _safe_get(aligned, ["L28", "orders"])
    orders_delta = _safe_get(aligned, ["L28", "delta", "orders"])
    orders_prior = _safe_get(aligned, ["L28", "prior", "orders"])
    obs.append(
        Observation(
            supporting_metric="orders",
            change_magnitude=float(orders_delta) if isinstance(orders_delta, (int, float)) else None,
            classification=_classify_delta(orders_delta, threshold=0.05),
            current=float(orders_now) if isinstance(orders_now, (int, float)) else None,
            prior=float(orders_prior) if isinstance(orders_prior, (int, float)) else None,
            delta_pct=float(orders_delta) if isinstance(orders_delta, (int, float)) else None,
        )
    )

    # ---- Returning-customer-share delta (Phase 5.3) -----------------------
    # Strong retention signal on most ecommerce stores; load-bearing for
    # the Watching section even when stable. Suppressed when not computed.
    rcs_now = _safe_get(aligned, ["L28", "returning_customer_share"])
    rcs_delta = _safe_get(aligned, ["L28", "delta", "returning_customer_share"])
    if rcs_now is not None and _has_identified_customers(aligned):
        rcs_prior = _safe_get(aligned, ["L28", "prior", "returning_customer_share"])
        obs.append(
            Observation(
                supporting_metric="returning_customer_share",
                change_magnitude=(
                    float(rcs_delta) if isinstance(rcs_delta, (int, float)) else None
                ),
                classification=_classify_delta(rcs_delta, threshold=0.01),
                current=float(rcs_now) if isinstance(rcs_now, (int, float)) else None,
                prior=float(rcs_prior) if isinstance(rcs_prior, (int, float)) else None,
                delta_pct=float(rcs_delta) if isinstance(rcs_delta, (int, float)) else None,
            )
        )

    # ---- Net-sales delta (Phase 5.3, load-bearing) ------------------------
    ns_now = _safe_get(aligned, ["L28", "net_sales"])
    ns_delta = _safe_get(aligned, ["L28", "delta", "net_sales"])
    if ns_now is not None:
        ns_prior = _safe_get(aligned, ["L28", "prior", "net_sales"])
        obs.append(
            Observation(
                supporting_metric="net_sales",
                change_magnitude=(
                    float(ns_delta) if isinstance(ns_delta, (int, float)) else None
                ),
                classification=_classify_delta(ns_delta, threshold=0.05),
                current=float(ns_now) if isinstance(ns_now, (int, float)) else None,
                prior=float(ns_prior) if isinstance(ns_prior, (int, float)) else None,
                delta_pct=float(ns_delta) if isinstance(ns_delta, (int, float)) else None,
            )
        )

    # ---- Anomaly notes (one Observation per flag, capped at 2) ------------
    # B-1: populate the reserved typed slots (anomaly_flags,
    # n_days_observed, n_days_expected) when an anomaly Observation is
    # emitted. Each per-flag Observation carries the originating flag in
    # its anomaly_flags list so downstream agents can reason about the
    # specific anomaly without re-parsing the prose ``text`` field.
    for f in list(flags)[:2]:
        obs.append(
            Observation(
                supporting_metric=str(f),
                change_magnitude=None,
                classification=ObservationClassification.ANOMALOUS,
                anomaly_flags=[str(f)],
                n_days_observed=int(n_days_observed or 0),
                n_days_expected=int(n_days_expected or 0),
            )
        )

    # Phase 5.3: relax the cap so downstream watching builders have more
    # candidates. Hard cap at 7 to keep the state-of-store paragraph
    # readable; the renderer caps the rendered set independently.
    return obs[:7]
