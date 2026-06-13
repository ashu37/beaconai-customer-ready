"""Audience builders for the Milestone 3 candidate detector.

These are pure functions that, given the prepared multi-window data
``g`` / ``aligned`` and config ``cfg``, return an :class:`AudienceResult`
describing the audience for a play. They contain ONLY the audience
selection rules (who is in the audience and how many of them there
are). They do NOT compute statistics, effects, p-values, CIs, or
revenue.

Source rules ported from the legacy ``_compute_candidates`` and
``build_segments`` functions in ``src.action_engine`` and
``src.segments``. Each builder returns the same minimal contract:

- ``segment_definition``: a short string describing the cohort rule.
- ``audience_size``: the number of unique customers that match.
- ``data_used``: the data fields/windows the rule referenced.
- ``audience_ids``: the set of customer ids that match (used by
  ``compute_audience_overlap``). May be empty if the rule could not
  resolve customer ids (rare; documented per builder).
- ``preliminary_rejection_reason``: ``None`` if the audience cleared
  the minimum-N predicate; otherwise a short string code such as
  ``"audience_too_small"`` or ``"data_missing"``.

Hard scope (M3): no scoring, no statistics, no revenue, no evidence,
no merchant-facing changes. Builders are read-only on ``g``,
``aligned``, and ``cfg``. They never mutate inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# AudienceResult — the value returned by every builder.
# ---------------------------------------------------------------------------


@dataclass
class AudienceResult:
    """Output of a per-play audience builder.

    Attributes:
        play_id: stable identifier of the play this audience targets.
        segment_definition: short human-readable rule description.
        audience_size: number of unique customers matched.
        audience_ids: set of customer-id strings; used for overlap math.
            May be empty if the rule cannot resolve to ids (e.g., no
            customer_id column on the data); in that case
            ``audience_size`` may still be non-zero (counted from a
            non-customer projection, e.g., row count) but downstream
            overlap math will treat the set as empty.
        data_used: list of field/window names the rule referenced.
        preliminary_rejection_reason: ``None`` if the audience cleared
            the minimum-N gate; else a short code.
    """

    play_id: str
    segment_definition: str
    audience_size: int
    audience_ids: Set[str] = field(default_factory=set)
    data_used: List[str] = field(default_factory=list)
    preliminary_rejection_reason: Optional[str] = None
    # S7.6-T7: optional provenance for builder-specific resolution paths
    # (currently used by aov_lift_via_threshold_bundle to record where the
    # AOV threshold was sourced from: l90_p60_data_derived |
    # cfg_merchant_declared | data_missing). Always None for builders that
    # do not opt in. Renderer-irrelevant; pure receipts surface.
    threshold_source: Optional[str] = None
    # S-FE-descriptive-distribution (L-EV-18/19): the discarded observed
    # series the four distributional builders already compute. These carry
    # the RAW series out of the pure M3 layer; the producer
    # (measurement_builder.build_prior_anchored_play_card) bins them via the
    # engine_run.build_descriptive_distribution helper and attaches a typed
    # DescriptiveDistribution to Audience. Kept pure: audience_builders does
    # NOT import engine_run, so the kind is carried as the enum's string
    # VALUE ("DORMANCY_DAYS" / "AOV_GAP" / "REORDER_GAP_DAYS" /
    # "DISCOUNT_FRACTION"); the producer coerces it to DistributionKind.
    # All None for builders that do not opt in. DESCRIPTIVE-ONLY: an observed
    # past series, never a projected rate / dollar / lift (L-EV-20).
    descriptive_kind: Optional[str] = None
    descriptive_series: Optional[List[float]] = None
    # descriptive_marker: the real window/threshold annotation when the
    # builder has one (winback dormancy-window upper bound); None when the
    # underlying parameter is None/TODO(S14) (threshold_aov /
    # replenishment_window_days / target_discount_share) per L-EV-20.
    descriptive_marker: Optional[float] = None


# ---------------------------------------------------------------------------
# Helpers (private, defensive).
# ---------------------------------------------------------------------------


def _safe_int_cfg(cfg: Optional[Dict[str, Any]], key: str, default: int) -> int:
    if not cfg:
        return int(default)
    try:
        v = cfg.get(key, default)
        return int(v)
    except (TypeError, ValueError):
        return int(default)


def _max_created_at(g: pd.DataFrame) -> Optional[pd.Timestamp]:
    if g is None or g.empty or "Created at" not in g.columns:
        return None
    s = pd.to_datetime(g["Created at"], errors="coerce")
    if s.dropna().empty:
        return None
    return s.max()


def _ids_as_str_set(series: pd.Series) -> Set[str]:
    if series is None:
        return set()
    try:
        return set(series.dropna().astype(str).unique().tolist())
    except Exception:
        return set()


def _empty(
    play_id: str,
    *,
    reason: str,
    segment_definition: str,
    data_used: List[str],
) -> AudienceResult:
    return AudienceResult(
        play_id=play_id,
        segment_definition=segment_definition,
        audience_size=0,
        audience_ids=set(),
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


# ---------------------------------------------------------------------------
# Per-play audience builders.
#
# Each takes (g, aligned, cfg) and returns AudienceResult. They do NOT
# rely on side effects in the legacy candidate emitters; their rules
# are ported as faithfully as possible from the data-presence
# predicates the legacy emitters use BEFORE any statistical step.
# ---------------------------------------------------------------------------


def winback_21_45(
    g: pd.DataFrame, aligned: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None
) -> AudienceResult:
    """Customers with last purchase 21-45 days ago.

    Source: ``src.segments.build_segments`` winback cohort + the
    ``winback_window`` vertical config in ``src.utils.get_vertical``.
    The legacy ``_compute_candidates`` `repeat_rate_improve` candidate
    is the test surface for the audience size; we reuse the same
    days_since_last cohort definition.
    """

    play_id = "winback_21_45"
    data_used = ["g.days_since_last", "g.customer_id", "cfg.winback_window"]
    seg_def = "last purchase 21-45 days before anchor"

    if g is None or g.empty or "customer_id" not in g.columns or "days_since_last" not in g.columns:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    # Use vertical-aware window if available; fall back to plan default.
    wb_lo, wb_hi = 21, 45
    try:
        from .utils import get_vertical

        vcfg = get_vertical(cfg or {})
        lo, hi = vcfg.get("winback_window", (21, 45))
        wb_lo, wb_hi = int(lo), int(hi)
    except Exception:
        pass

    # last-purchase-per-customer cohort
    last = g.sort_values("Created at").groupby("customer_id").tail(1)
    cohort = last[
        (last["days_since_last"].astype(float) >= wb_lo)
        & (last["days_since_last"].astype(float) <= wb_hi)
    ]
    ids = _ids_as_str_set(cohort["customer_id"])
    audience_size = len(ids)
    seg_def = f"last purchase {wb_lo}-{wb_hi} days before anchor"

    min_n = _safe_int_cfg(cfg, "MIN_N_WINBACK", 75)
    reason = "audience_too_small" if audience_size < min_n else None
    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


def winback_dormant_cohort_candidates(
    g: pd.DataFrame,
    aligned: Dict[str, Any],
    cfg: Optional[Dict[str, Any]] = None,
    *,
    ranking_strategy: Optional[str] = None,
) -> AudienceResult:
    """Sprint 6 Tier-B builder — dormant repeat-buyers in the winback window.

    Three-part cohort definition (per ARCHITECTURE_PLAN.md Part I §B-1
    and Sprint 6 founder Q1):

    1. Most recent order placed in the vertical-specific dormancy window
       (Beauty: 21–45 days ago; Supplements: 60–120 days ago).
    2. Has at least 2 prior orders (repeat-buyer signal).
    3. No order placed in the past 28 days (eliminates customers who
       already self-reactivated without a nudge).

    The cohort's existence IS the directional signal — there is no
    Welch-t or z-test here. The measurement-builder pathway anchors the
    PlayCard's posterior on the winback_21_45.base_rate prior (Beauty
    validated_external Klaviyo; supplements heuristic_unvalidated).

    Args:
        ranking_strategy: forward-scaffolding hook for the Sprint 10-13
            ML AUDIENCE layer. Default ``None`` (today's behavior:
            arrival-order audience, no ML ranking). Sprint 13 will
            populate this with a typed enum value from
            ``{"predicted_ltv_desc", "p_alive_x_value_desc",
            "rfm_quintile"}`` to rank the cohort BEFORE the audience
            floor / materiality gates apply. The parameter is reserved
            now so the builder signature is stable across the Sprint 13
            cut; today the value is ignored.
    """

    # Reserved for Sprint 13 — accepted, validated for type only, and
    # ignored at runtime. Logged via a no-op so the signature is
    # observably unused but lint-clean.
    if ranking_strategy is not None and not isinstance(ranking_strategy, str):
        ranking_strategy = None

    play_id = "winback_dormant_cohort"
    data_used = [
        "g.Created at",
        "g.customer_id",
        "cfg.VERTICAL_MODE",
    ]
    seg_def = "dormant repeat-buyers in winback window"

    if g is None or g.empty or "customer_id" not in g.columns or "Created at" not in g.columns:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    # Vertical-aware window. Founder Q1 (2026-05-17): Beauty 21–45d,
    # Supplements 60–120d. Mixed defaults to Beauty's tighter window
    # (the more conservative cohort definition); the prior-side mixed
    # blend is independently gated by resolve_mixed_prior's KI-19
    # conservative-min rule, which already refuses heuristic-unvalidated
    # blends at the sizing seam.
    vertical = str((cfg or {}).get("VERTICAL_MODE") or "mixed").strip().lower()
    if vertical == "supplements":
        wb_lo, wb_hi = 60, 120
    else:
        wb_lo, wb_hi = 21, 45
    seg_def = (
        f"last order {wb_lo}-{wb_hi}d ago, >=2 prior orders, no order in last 28d"
    )

    maxd = _max_created_at(g)
    if maxd is None:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    gg = g.copy()
    gg["Created at"] = pd.to_datetime(gg["Created at"], errors="coerce")
    gg = gg[~gg["Created at"].isna()]
    if gg.empty:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    # Part 1: last-order recency in [wb_lo, wb_hi] days.
    last_by_cust = gg.groupby("customer_id")["Created at"].max()
    days_since = (maxd - last_by_cust).dt.days
    recency_ids = set(
        days_since[(days_since >= wb_lo) & (days_since <= wb_hi)].index.astype(str)
    )
    if not recency_ids:
        return AudienceResult(
            play_id=play_id,
            segment_definition=seg_def,
            audience_size=0,
            audience_ids=set(),
            data_used=data_used,
            preliminary_rejection_reason="audience_too_small",
        )

    # Part 2: >=2 prior orders historically.
    order_counts = gg["customer_id"].astype(str).value_counts()
    repeat_ids = set(order_counts[order_counts >= 2].index)

    # Part 3: no order in the past 28 days (already self-reactivated).
    l28_start = maxd - pd.Timedelta(days=28)
    l28_active_ids = _ids_as_str_set(gg[gg["Created at"] >= l28_start]["customer_id"])

    ids = (recency_ids & repeat_ids) - l28_active_ids
    audience_size = len(ids)

    # S-FE-descriptive-distribution (L-EV-19): the dormancy days-since-last
    # series for the FINAL resolved cohort. ``days_since`` is indexed by
    # customer_id (built above); subset to ``ids``. Marker = the dormancy
    # window upper bound (a real builder-derived value: 45 Beauty/mixed, 120
    # supplements). DESCRIPTIVE-ONLY (observed past gaps). Empty/absent
    # series is typed downstream by build_descriptive_distribution.
    descriptive_series: List[float] = []
    try:
        if ids:
            _ds = days_since[days_since.index.astype(str).isin(ids)]
            descriptive_series = [
                float(v) for v in _ds.tolist() if v is not None and float(v) >= 0.0
            ]
    except Exception:
        descriptive_series = []

    # Audience floor:
    # - Default 500 (Sprint 6 anchor / today's behavior).
    # - Sprint 6.5 Ticket T4: when ``ENGINE_V2_STORE_PROFILE`` is ON AND
    #   the caller passes a typed ``StoreProfile`` via
    #   ``cfg["_store_profile"]``, read the floor from
    #   ``profile.gate_calibration.audience_floor_by_play_id[play_id]``.
    #   Falls back to today's 500 default when flag is OFF, profile is
    #   None, or the per-play cell is missing (in which case the
    #   profile's ``_default`` cell is also consulted; cells with the
    #   architecture default already record a ``rules_fired`` audit log).
    min_n = _safe_int_cfg(cfg, "MIN_N_WINBACK_DORMANT", 500)
    if cfg and bool(cfg.get("ENGINE_V2_STORE_PROFILE", False)):
        store_profile = cfg.get("_store_profile") if isinstance(cfg, dict) else None
        if store_profile is not None:
            gate = getattr(store_profile, "gate_calibration", None)
            if gate is not None:
                floors = getattr(gate, "audience_floor_by_play_id", None) or {}
                profile_floor = floors.get(play_id)
                if profile_floor is None:
                    profile_floor = floors.get("_default")
                if profile_floor is not None:
                    try:
                        min_n = int(profile_floor)
                    except (TypeError, ValueError):
                        pass
    if audience_size == 0:
        reason = "audience_too_small"
    elif audience_size < min_n:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
        descriptive_kind="DORMANCY_DAYS",
        descriptive_series=descriptive_series,
        descriptive_marker=float(wb_hi),
    )


def replenishment_due_candidates(
    g: pd.DataFrame,
    aligned: Dict[str, Any],
    cfg: Optional[Dict[str, Any]] = None,
    *,
    ranking_strategy: Optional[str] = None,
) -> AudienceResult:
    """Sprint 6 Tier-B builder — per-SKU cadence-due cohort.

    Algorithm (per IM plan §S6-T3 + founder decisions Q2/Q3/Q5
    locked in memory.md commit e87e431):

    1. For each customer × SKU, compute inter-purchase gaps in days
       over the in-class product set. Customers with <2 repeat
       purchases of an SKU are right-censored (excluded) per the
       S6.5-T3 cadence-baseline convention. Pure right-censoring,
       NOT cross-period cohort comparison (B-5 Berkson invariant).
    2. Per SKU: if ≥30 customers contributed at least one inter-purchase
       gap, the empirical median of those gaps is the SKU's cadence.
       SKUs below the N=30 floor contribute zero audience and the SKU
       is silently skipped (no crash). N=30 is a founder decision (Q2);
       do not lower unilaterally.
    3. Audience = customers whose most-recent in-class purchase of an
       SKU is within ``cadence_median ± half_cadence`` days of the
       reference anchor (``max(Created at)``). Tolerance = floor(cadence/2).
    4. Vertical dispatch:
         - beauty: ``get_size_regex("beauty")`` selects in-class SKUs.
         - supplements: ``parse_unit_coherent("supplements", text)``
           gives a unit-coherent key per SKU. SKUs returning ``None``
           are excluded entirely (S6-T2 5/10 G-1 coverage outcome).
         - mixed: 50/50 blend per G-3 (loader-unit-test-pinned per
           KI-19/KI-28; no e2e mixed fixture).

    Determinism (G-7 seed-all): sort customers / SKUs in stable order
    before reducing; never depend on dict ordering of groupby keys.

    Args:
        ranking_strategy: forward-scaffolding hook for the Sprint 10-13
            ML AUDIENCE layer. Default ``None``. Accepted, type-checked,
            and ignored at runtime. Sprint 13 will populate this to
            rank the cohort BEFORE the audience floor / materiality
            gates apply.

    M3 contract: no stats, no revenue, no p-values, no effects.
    """

    # Reserved for Sprint 13 — accepted, validated for type only, and
    # ignored at runtime (mirrors winback_dormant_cohort_candidates).
    if ranking_strategy is not None and not isinstance(ranking_strategy, str):
        ranking_strategy = None

    play_id = "replenishment_due"
    data_used = [
        "g.customer_id",
        "g.Created at",
        "g.lineitem_any",
        "cfg.VERTICAL_MODE",
    ]
    seg_def = "customers whose most-recent in-class purchase has reached cadence +/- half-cadence"

    if (
        g is None
        or g.empty
        or "customer_id" not in g.columns
        or "Created at" not in g.columns
        or "lineitem_any" not in g.columns
    ):
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    maxd = _max_created_at(g)
    if maxd is None:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    gg = g.copy()
    gg["Created at"] = pd.to_datetime(gg["Created at"], errors="coerce")
    gg = gg[~gg["Created at"].isna()]
    if gg.empty:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    gg["customer_id"] = gg["customer_id"].astype(str)
    gg["lineitem_any"] = gg["lineitem_any"].astype(str)

    vertical = str((cfg or {}).get("VERTICAL_MODE") or "mixed").strip().lower()

    # Per-SKU minimum customers contributing to cadence. Below floor →
    # SKU silently skipped, no crash.
    #
    # S7.6-T2.5-fix (DS architect scope card 2026-05-22): default lowered
    # from N=30 to N=10. The legacy N=30 was imported as a textbook
    # median-stability rule of thumb without ICP validation; <20% of
    # representative small-DTC merchants (~50 SKUs, ~1,200 customers)
    # clear N=30 per SKU class. Audience-level floor (line 559 below)
    # remains the binding sample-size gate downstream; N=10 only
    # governs WHICH SKUs contribute to the cadence median, not whether
    # the assembled cohort is large enough to act on.
    #
    # Resolution order (mirrors ``_default_by_stage`` pattern below):
    #   1. Profile cell ``cfg["_store_profile"].gate_calibration
    #      .replenishment_due_per_sku_floor`` (per-stage, resolved at
    #      profile-build time) when ``ENGINE_V2_STORE_PROFILE`` is ON.
    #   2. Env override ``MIN_N_REPLENISHMENT_DUE_PER_SKU``.
    #   3. Default ``10``.
    min_customers_per_sku = _safe_int_cfg(
        cfg, "MIN_N_REPLENISHMENT_DUE_PER_SKU", 10
    )
    if cfg and bool(cfg.get("ENGINE_V2_STORE_PROFILE", False)):
        store_profile = cfg.get("_store_profile") if isinstance(cfg, dict) else None
        if store_profile is not None:
            gate = getattr(store_profile, "gate_calibration", None)
            if gate is not None:
                profile_per_sku_floor = getattr(
                    gate, "replenishment_due_per_sku_floor", None
                )
                if profile_per_sku_floor is not None:
                    try:
                        min_customers_per_sku = int(profile_per_sku_floor)
                    except (TypeError, ValueError):
                        pass

    # Build per-vertical SKU-classifier: a callable mapping SKU text →
    # canonical "in-class" key or None. For beauty/mixed beauty side
    # this is "matched / not matched" via the legacy size regex. For
    # supplements this is the coherent-unit key (e.g., ("count", 60)).
    def _beauty_key(text: str) -> Optional[str]:
        try:
            from .replenishment_parser import get_size_regex
            rx = get_size_regex("beauty")
            if not rx:
                return None
            import re as _re
            m = _re.search(rx, text or "", flags=_re.IGNORECASE)
            if m is None:
                return None
            # Use the matched substring as the in-class key. This keeps
            # the SKU's parsed size token as the bucket — e.g. all
            # "50ml" SKUs share one cadence. Falls back to full text
            # when no group is captured.
            try:
                return str(m.group(0))
            except IndexError:
                return text
        except Exception:
            return None

    def _supplements_key(text: str) -> Optional[str]:
        try:
            from .replenishment_parser import parse_unit_coherent
            res = parse_unit_coherent("supplements", text)
            if res is None:
                return None
            ck, val = res
            return f"{ck}={int(val)}"
        except Exception:
            return None

    if vertical == "beauty":
        sku_keyer = _beauty_key
        blend_supplements_weight = 0.0
    elif vertical == "supplements":
        sku_keyer = _supplements_key
        blend_supplements_weight = 1.0
    else:
        # mixed: 50/50 blend per G-3. We compute audiences for both
        # paths and union the resulting customer-id sets.
        sku_keyer = None
        blend_supplements_weight = 0.5

    # S-FE-descriptive-distribution (L-EV-19): accumulate the reorder-gap
    # (days-since-last in-class purchase) for each customer ADDED to the
    # audience, across keyer calls (mixed unions both). The producer bins
    # this into a REORDER_GAP_DAYS DescriptiveDistribution. Marker = None
    # today (replenishment_window_days is None/TODO(S14) per L-EV-20).
    reorder_gap_by_cust: Dict[str, float] = {}

    def _audience_for_keyer(keyer) -> Set[str]:
        # Sort for determinism (G-7). lineitem_any sort keeps SKU group
        # order stable; customer_id sort keeps inter-purchase gap
        # computation stable when timestamps tie.
        local = gg.sort_values(["lineitem_any", "customer_id", "Created at"])
        # Map each row's lineitem to its in-class bucket key.
        keys = local["lineitem_any"].map(lambda s: keyer(s) if keyer is not None else None)
        local = local.assign(_sku_key=keys)
        local = local[local["_sku_key"].notna() & (local["_sku_key"] != "")]
        if local.empty:
            return set()

        audience: Set[str] = set()
        # Iterate SKU buckets in sorted order (determinism).
        sku_keys = sorted(local["_sku_key"].unique().tolist())
        for sku_key in sku_keys:
            sub = local[local["_sku_key"] == sku_key]
            # Per-customer inter-purchase gaps in days.
            gaps_by_cust: Dict[str, List[float]] = {}
            most_recent_by_cust: Dict[str, pd.Timestamp] = {}
            for cust_id, cust_rows in sub.groupby("customer_id", sort=True):
                ts = (
                    pd.to_datetime(cust_rows["Created at"], errors="coerce")
                    .dropna()
                    .sort_values()
                    .reset_index(drop=True)
                )
                if len(ts) < 2:
                    # Right-censored per S6.5-T3 convention.
                    continue
                diffs = ts.diff().dropna().dt.total_seconds() / 86400.0
                if diffs.empty:
                    continue
                gaps_by_cust[str(cust_id)] = [float(x) for x in diffs.tolist()]
                most_recent_by_cust[str(cust_id)] = ts.iloc[-1]

            if len(gaps_by_cust) < min_customers_per_sku:
                # SKU below floor — zero audience contribution, no crash.
                continue

            # Empirical median cadence across all contributing gaps.
            all_gaps: List[float] = []
            for vals in gaps_by_cust.values():
                all_gaps.extend(vals)
            if not all_gaps:
                continue
            cadence_median = float(np.median(np.asarray(all_gaps, dtype=float)))
            if cadence_median <= 0:
                continue
            tolerance = max(1.0, float(int(cadence_median // 2)))

            lower = cadence_median - tolerance
            upper = cadence_median + tolerance

            # For each contributing customer, check whether their MOST
            # RECENT in-class purchase has reached the cadence window
            # measured against the anchor.
            for cust_id in sorted(gaps_by_cust.keys()):
                last_ts = most_recent_by_cust.get(cust_id)
                if last_ts is None:
                    continue
                days_since = float((maxd - last_ts).total_seconds() / 86400.0)
                if lower <= days_since <= upper:
                    audience.add(cust_id)
                    # Keep the smallest gap when a customer qualifies via
                    # multiple SKU buckets (deterministic; observed value).
                    prev = reorder_gap_by_cust.get(cust_id)
                    if prev is None or days_since < prev:
                        reorder_gap_by_cust[cust_id] = days_since
        return audience

    if vertical == "mixed":
        ids_beauty = _audience_for_keyer(_beauty_key)
        ids_suppl = _audience_for_keyer(_supplements_key)
        # G-3 50/50 blend: union the two cohorts. The 50/50 weighting
        # applies at the prior-blend layer (resolve_mixed_prior),
        # not at the audience layer. Per KI-19/KI-28 there is no e2e
        # mixed fixture; the loader unit tests pin the prior blend.
        ids = ids_beauty | ids_suppl
    else:
        ids = _audience_for_keyer(sku_keyer)

    seg_def = (
        f"per-SKU cadence-due cohort (vertical={vertical}, "
        f"N>={min_customers_per_sku} customers/SKU, tolerance=floor(cadence/2))"
    )

    audience_size = len(ids)

    # Audience floor: same store-profile pattern as winback_dormant_cohort
    # (S6.5-T4 gate_calibration._default_by_stage = 50/150/400/1200).
    min_n = _safe_int_cfg(cfg, "MIN_N_REPLENISHMENT_DUE", 0)
    if cfg and bool(cfg.get("ENGINE_V2_STORE_PROFILE", False)):
        store_profile = cfg.get("_store_profile") if isinstance(cfg, dict) else None
        if store_profile is not None:
            gate = getattr(store_profile, "gate_calibration", None)
            if gate is not None:
                floors = getattr(gate, "audience_floor_by_play_id", None) or {}
                profile_floor = floors.get(play_id)
                if profile_floor is None:
                    profile_floor = floors.get("_default")
                if profile_floor is not None:
                    try:
                        min_n = int(profile_floor)
                    except (TypeError, ValueError):
                        pass

    if audience_size == 0:
        reason = "audience_too_small"
    elif min_n > 0 and audience_size < min_n:
        reason = "audience_too_small"
    else:
        reason = None

    # S-FE-descriptive-distribution: reorder-gap series for the resolved
    # cohort (observed days-since-last in-class purchase). Marker None per
    # L-EV-20 (replenishment_window_days is None/TODO(S14)).
    descriptive_series = [
        float(reorder_gap_by_cust[c])
        for c in sorted(ids)
        if c in reorder_gap_by_cust
    ]

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
        descriptive_kind="REORDER_GAP_DAYS",
        descriptive_series=descriptive_series,
        descriptive_marker=None,
    )


def cohort_journey_first_to_second_candidates(
    g: pd.DataFrame,
    aligned: Dict[str, Any],
    cfg: Optional[Dict[str, Any]] = None,
    *,
    ranking_strategy: Optional[str] = None,
) -> AudienceResult:
    """Sprint 7 Ticket T2 — cohort_journey_first_to_second Tier-B builder.

    Targets first-time buyers whose first (and only) purchase fell in the
    age window ``(now - 90d, now - 30d)``, i.e. customers who are 30-90
    days into their post-first-purchase journey and have not yet placed a
    second order. Window is fixed at 30-90d per DS architect 2026-05-19
    (first-to-second is a longer-window constraint than near-threshold or
    replenishment-cadence cohorts; the symmetric wildcard prior in
    ``first_to_second_purchase.base_rate`` carries no per-vertical
    argument for tightening).

    Cohort definition:
      1. Customer's order history contains exactly ONE order.
      2. That order's ``Created at`` is between ``maxd - 90d`` and
         ``maxd - 30d`` (inclusive of the 30d edge; exclusive at the
         90d edge keeps the cohort age <= 90 days as a hard ceiling).

    The cohort's existence IS the directional signal — there is no Welch
    or z-test here. The measurement-builder pathway anchors the
    PlayCard's posterior on ``first_to_second_purchase.base_rate.*``
    (validated_external bsandco, effective_n=156110, wildcard vertical)
    via ``measurement_builder.build_prior_anchored_play_card``.

    Determinism (G-7): customer-id ordering is stable via the underlying
    pandas dtype + ``unique()`` projection; the audience set is unordered
    and audience_size is a pure count.

    Args:
        ranking_strategy: forward-scaffolding hook for the Sprint 10-13
            ML AUDIENCE layer. Default ``None``. Accepted, type-checked,
            and ignored at runtime (mirrors winback_dormant_cohort +
            replenishment_due precedent). Sprint 13 will populate this to
            rank the cohort BEFORE the audience floor / materiality
            gates apply.

    M3 contract: no stats, no revenue, no p-values, no effects.
    """

    # Reserved for Sprint 13 — accepted, validated for type only, and
    # ignored at runtime.
    if ranking_strategy is not None and not isinstance(ranking_strategy, str):
        ranking_strategy = None

    play_id = "cohort_journey_first_to_second"
    data_used = [
        "g.customer_id",
        "g.Created at",
    ]
    seg_def = (
        "first-time buyers whose only order is 30-90 days before anchor"
    )

    if g is None or g.empty or "customer_id" not in g.columns or "Created at" not in g.columns:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    maxd = _max_created_at(g)
    if maxd is None:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    gg = g.copy()
    gg["Created at"] = pd.to_datetime(gg["Created at"], errors="coerce")
    gg = gg[~gg["Created at"].isna()]
    if gg.empty:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    gg["customer_id"] = gg["customer_id"].astype(str)

    # Part 1: customers whose total order count is exactly 1.
    counts = gg["customer_id"].value_counts()
    one_order_ids = set(counts[counts == 1].index.astype(str))
    if not one_order_ids:
        return AudienceResult(
            play_id=play_id,
            segment_definition=seg_def,
            audience_size=0,
            audience_ids=set(),
            data_used=data_used,
            preliminary_rejection_reason="audience_too_small",
        )

    # Part 2: that single order's age in (30d, 90d]. We use:
    #   30 <= days_since <= 90
    # to align with the 30-90d window framing in the ticket. The upper
    # bound is inclusive (a customer exactly 90 days post-purchase is
    # still in window); the lower bound is inclusive at 30 days (a
    # customer just past the typical winback near-threshold window).
    last_by_cust = gg.groupby("customer_id")["Created at"].max()
    days_since = (maxd - last_by_cust).dt.days
    in_window_ids = set(
        days_since[(days_since >= 30) & (days_since <= 90)].index.astype(str)
    )

    ids = one_order_ids & in_window_ids
    audience_size = len(ids)

    # Audience floor:
    # - Default 0 (cohort existence IS the directional signal, like the
    #   replenishment_due builder default).
    # - Sprint 6.5 Ticket T4 store-profile pattern: when
    #   ``ENGINE_V2_STORE_PROFILE`` is ON and the caller passes a typed
    #   ``StoreProfile`` via ``cfg["_store_profile"]``, read the floor
    #   from ``profile.gate_calibration.audience_floor_by_play_id[play_id]``
    #   (per the D-FLOOR-cohort_journey_first_to_second grid; symmetric
    #   across verticals because S7.5-T2 prior is wildcard).
    min_n = _safe_int_cfg(cfg, "MIN_N_COHORT_JOURNEY_FIRST_TO_SECOND", 0)
    if cfg and bool(cfg.get("ENGINE_V2_STORE_PROFILE", False)):
        store_profile = cfg.get("_store_profile") if isinstance(cfg, dict) else None
        if store_profile is not None:
            gate = getattr(store_profile, "gate_calibration", None)
            if gate is not None:
                floors = getattr(gate, "audience_floor_by_play_id", None) or {}
                profile_floor = floors.get(play_id)
                if profile_floor is None:
                    profile_floor = floors.get("_default")
                if profile_floor is not None:
                    try:
                        min_n = int(profile_floor)
                    except (TypeError, ValueError):
                        pass

    if audience_size == 0:
        reason = "audience_too_small"
    elif min_n > 0 and audience_size < min_n:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


def discount_dependency_hygiene_candidates(
    g: pd.DataFrame,
    aligned: Dict[str, Any],
    cfg: Optional[Dict[str, Any]] = None,
    *,
    ranking_strategy: Optional[str] = None,
) -> AudienceResult:
    """Sprint 7 Ticket T1 — discount_dependency_hygiene Tier-B builder.

    Targets customers whose purchase history is heavily discount-conditioned:
    at least 50% of their historical orders carried a non-zero discount
    (``discount_rate > 0``). The downstream play mechanism is a 14-day
    discount-suppression window followed by a value-led, no-urgency,
    full-price email send. The audience builder ONLY computes the cohort;
    the 14-day suppression-of-other-discount-channels logic lives in the
    upstream campaign-config layer (out of scope here per Memo 1 scope).

    Cohort definition (Memo 1 canonical threshold ≥50%):
      1. Customer has at least 1 historical order on file (``Total orders``
         proxy = count of rows for that customer_id).
      2. Of the customer's historical orders, the fraction with
         ``discount_rate > 0`` is ≥ 0.5.

    The cohort's existence IS the directional signal — the measurement
    builder anchors the PlayCard's posterior on the validated_external
    Beauty-only ``discount_dependency_hygiene.base_rate.beauty`` prior
    (DS Memo-1, validated 2026-05-20; KI-NEW-K envelope re-fit deferred
    to Sprint 8) via ``measurement_builder.build_prior_anchored_play_card``.
    Supplements path falls through to PRIOR_UNVALIDATED Considered (no
    supplements prior block by design per DS Memo-4 REJECT verdict).

    Determinism (G-7): customer-id ordering is stable via the underlying
    pandas dtype + ``unique()`` projection; the audience set is unordered
    and audience_size is a pure count.

    Args:
        ranking_strategy: forward-scaffolding hook for the Sprint 10-13
            ML AUDIENCE layer. Default ``None``. Accepted, type-checked,
            and ignored at runtime (mirrors winback_dormant_cohort +
            replenishment_due + cohort_journey_first_to_second precedent).

    M3 contract: no stats, no revenue, no p-values, no effects.
    """

    # Reserved for Sprint 13 — accepted, validated for type only, and
    # ignored at runtime.
    if ranking_strategy is not None and not isinstance(ranking_strategy, str):
        ranking_strategy = None

    play_id = "discount_dependency_hygiene"
    data_used = [
        "g.customer_id",
        "g.discount_rate",
    ]
    seg_def = (
        "customers whose >=50% of historical orders carried a discount"
    )

    if (
        g is None
        or g.empty
        or "customer_id" not in g.columns
        or "discount_rate" not in g.columns
    ):
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    gg = g.copy()
    gg["customer_id"] = gg["customer_id"].astype(str)
    gg["discount_rate"] = pd.to_numeric(gg["discount_rate"], errors="coerce")
    # Coerce NaNs to 0.0 (treat unknown discount as no discount; the
    # alternative — dropping rows — would inflate the fraction toward 1.0
    # for customers whose order history happens to carry incomplete
    # discount instrumentation, which is the opposite of the safe
    # default).
    gg["discount_rate"] = gg["discount_rate"].fillna(0.0)

    if gg.empty:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    # Per-customer aggregates: total orders + count of discounted orders.
    is_discounted = (gg["discount_rate"] > 0.0).astype(int)
    per_cust = pd.DataFrame({
        "customer_id": gg["customer_id"].values,
        "is_discounted": is_discounted.values,
    })
    grouped = per_cust.groupby("customer_id")["is_discounted"].agg(
        total_orders="count", discounted_orders="sum"
    )
    if grouped.empty:
        return AudienceResult(
            play_id=play_id,
            segment_definition=seg_def,
            audience_size=0,
            audience_ids=set(),
            data_used=data_used,
            preliminary_rejection_reason="audience_too_small",
        )

    grouped["frac"] = grouped["discounted_orders"] / grouped["total_orders"]
    eligible = grouped[grouped["frac"] >= 0.5]
    ids: Set[str] = set(eligible.index.astype(str).tolist())
    audience_size = len(ids)

    # S-FE-descriptive-distribution (L-EV-19): per-customer discount fraction
    # for the resolved cohort (observed share of historical orders that
    # carried a discount; in [0.5, 1.0] for the eligible set). Marker None
    # per L-EV-20 (target_discount_share is None/TODO(S14)).
    descriptive_series: List[float] = []
    try:
        descriptive_series = [
            float(v) for v in eligible["frac"].tolist() if v is not None
        ]
    except Exception:
        descriptive_series = []

    # Audience floor:
    # - Default 0 (cohort existence IS the directional signal).
    # - Sprint 6.5 store-profile pattern: when ``ENGINE_V2_STORE_PROFILE``
    #   is ON and the caller passes a typed ``StoreProfile`` via
    #   ``cfg["_store_profile"]``, read the floor from
    #   ``profile.gate_calibration.audience_floor_by_play_id[play_id]``
    #   (per the D-FLOOR-discount_dependency_hygiene base grid;
    #   beauty-only — supplements omits the key by design and the
    #   strict resolver returns None, leaving the play un-floored).
    # - Conditional heavy-promo bump rule (DS architect 2026-05-20):
    #   when store-level discount-fraction > 40% (heavy-promo posture),
    #   floor BUMPS UP from base {40/100/250/750} to heavy-promo
    #   {80/200/500/1500}. This bump is currently DORMANT in the
    #   resolver because ``StoreProfile`` does not yet carry the
    #   ``commerce_posture.discount_fraction`` attribute. Tracked as
    #   founder Q surfaced at S7-T1 closeout — bump logic will land
    #   alongside the profile attribute, not invented here.
    min_n = _safe_int_cfg(cfg, "MIN_N_DISCOUNT_DEPENDENCY_HYGIENE", 0)
    if cfg and bool(cfg.get("ENGINE_V2_STORE_PROFILE", False)):
        store_profile = cfg.get("_store_profile") if isinstance(cfg, dict) else None
        if store_profile is not None:
            gate = getattr(store_profile, "gate_calibration", None)
            if gate is not None:
                floors = getattr(gate, "audience_floor_by_play_id", None) or {}
                profile_floor = floors.get(play_id)
                if profile_floor is None:
                    profile_floor = floors.get("_default")
                if profile_floor is not None:
                    try:
                        min_n = int(profile_floor)
                    except (TypeError, ValueError):
                        pass

    if audience_size == 0:
        reason = "audience_too_small"
    elif min_n > 0 and audience_size < min_n:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
        descriptive_kind="DISCOUNT_FRACTION",
        descriptive_series=descriptive_series,
        descriptive_marker=None,
    )


def aov_lift_via_threshold_bundle_candidates(
    g: pd.DataFrame,
    aligned: Dict[str, Any],
    cfg: Optional[Dict[str, Any]] = None,
    *,
    ranking_strategy: Optional[str] = None,
) -> AudienceResult:
    """Sprint 7 Ticket T3 — aov_lift_via_threshold_bundle Tier-B builder.

    Targets customers whose current cart or typical AOV sits exactly
    ``$5-$15 BELOW`` a merchant-defined AOV threshold (free-shipping tier,
    "spend X get Y" milestone, tiered bundle-pricing threshold) at
    engine-run time. Per the S7-T3 spec + DS Memo 2 / Memo 3 scope, this
    is a SNAPSHOT constraint (instantaneous near-threshold), NOT a
    look-back-window cohort.

    Cohort-source dispatch:

    1. **Cart-state path (preferred).** When the dataframe carries a
       ``cart_state_total`` or ``current_cart_total`` numeric column
       (Sprint 9+ Shopify cart export; not part of today's standard CSV),
       use per-customer cart totals directly. Customer qualifies iff
       ``threshold - 15 <= cart_total <= threshold - 5`` (inclusive).
    2. **Avg-AOV fallback (today's default).** When no cart-state column
       is present, compute each customer's typical AOV across their last
       ``N`` days (config key ``AOV_BUNDLE_LOOKBACK_DAYS``, default 90)
       using ``net_sales``. Customer qualifies on the same
       ``threshold - 15`` to ``threshold - 5`` inclusive band against
       their typical AOV. Documented fallback per the S7-T3 ticket spec;
       founder Q surfaced if neither path is feasible.

    Threshold source: ``cfg["AOV_BUNDLE_THRESHOLD_USD"]`` (merchant-
    configured per Klaviyo flow / Shopify shipping-tier integration;
    Sprint 9 will plumb this from the store profile). When unset the
    cohort cannot resolve and the builder returns ``data_missing`` (we
    will NOT invent a default threshold from data).

    The cohort's existence IS the directional signal — there is no
    Welch or z-test here. The measurement-builder pathway anchors the
    PlayCard's posterior on the dual-tier
    ``aov_lift_via_threshold_bundle.base_rate`` prior (Beauty
    validated_external Memo 2 pseudo_n=30; supplements elicited_expert
    Memo 3 DOWNGRADED pseudo_n=10 per KI-NEW-J cross-vertical evidence
    laundering safeguard) via
    ``measurement_builder.build_prior_anchored_play_card``.

    Args:
        ranking_strategy: forward-scaffolding hook for the Sprint 10-13
            ML AUDIENCE layer. Default ``None``. Accepted, type-checked,
            and ignored at runtime (mirrors winback_dormant_cohort +
            replenishment_due + cohort_journey_first_to_second precedent).

    M3 contract: no stats, no revenue, no p-values, no effects.
    """

    # Reserved for Sprint 13 — accepted, validated for type only.
    if ranking_strategy is not None and not isinstance(ranking_strategy, str):
        ranking_strategy = None

    play_id = "aov_lift_via_threshold_bundle"
    data_used = [
        "g.customer_id",
        "g.net_sales",
        "g.Created at",
        "cfg.AOV_BUNDLE_THRESHOLD_USD",
        "cfg.AOV_BUNDLE_LOOKBACK_DAYS",
    ]
    seg_def = "customers $5-$15 below merchant AOV threshold (snapshot)"

    # S7.6-T7: Path A supplements re-disable + threshold-from-data primary,
    # gated by ENGINE_V2_AOV_THRESHOLD_FROM_DATA (default OFF in S7.6-T7;
    # flipped ON in S7.6-T7.5 atomic with Beauty + Supplements fixture
    # re-pin). When OFF, preserves S7-T3.5 behavior verbatim (cfg-only
    # resolution, no vertical gate).
    flag_threshold_from_data = bool((cfg or {}).get("ENGINE_V2_AOV_THRESHOLD_FROM_DATA", False))

    # ARCHITECTURE_PLAN.md:248 + :257(c) — supplements is unconditionally
    # excluded from B-5 aov_lift_via_threshold_bundle. The S7-T3.5
    # activation (which never fired on the synthetic Supplements fixture
    # anyway) is reverted here under flag-ON per founder Path A decision.
    if flag_threshold_from_data:
        vertical = str((cfg or {}).get("VERTICAL_MODE") or "mixed").strip().lower()
        if vertical == "supplements":
            res = _empty(
                play_id,
                reason="vertical_excluded_per_b5_248",
                segment_definition=seg_def,
                data_used=data_used,
            )
            res.threshold_source = "vertical_excluded"
            return res

    if g is None or g.empty or "customer_id" not in g.columns:
        res = _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)
        res.threshold_source = "data_missing"
        return res

    # Threshold resolution order (flag-ON, per ARCHITECTURE_PLAN.md:249/254):
    #   1. L90 P60 from data (if L90 order count >= 200 for stable percentile)
    #   2. cfg["AOV_BUNDLE_THRESHOLD_USD"] (merchant-declared override)
    #   3. data_missing refuse
    # Flag-OFF: legacy cfg-only path.
    threshold: Optional[float] = None
    threshold_source: str = "data_missing"

    cfg_threshold_raw = (cfg or {}).get("AOV_BUNDLE_THRESHOLD_USD")
    try:
        cfg_threshold = float(cfg_threshold_raw) if cfg_threshold_raw is not None else None
    except (TypeError, ValueError):
        cfg_threshold = None
    if cfg_threshold is not None and cfg_threshold <= 0:
        cfg_threshold = None

    if flag_threshold_from_data:
        # Try L90 P60 computation first.
        try:
            if "Created at" in g.columns and "net_sales" in g.columns:
                maxd_l90 = _max_created_at(g)
                if maxd_l90 is not None:
                    l90_start = maxd_l90 - pd.Timedelta(days=90)
                    gl90 = g.copy()
                    gl90["Created at"] = pd.to_datetime(gl90["Created at"], errors="coerce")
                    gl90 = gl90[~gl90["Created at"].isna()]
                    gl90 = gl90[gl90["Created at"] >= l90_start]
                    gl90["net_sales"] = pd.to_numeric(gl90["net_sales"], errors="coerce")
                    gl90 = gl90[~gl90["net_sales"].isna()]
                    # Per ARCHITECTURE_PLAN.md:254, require L90 order count >= 200
                    # for stable P60. "Order" = one row in the orders CSV.
                    l90_order_count = int(len(gl90))
                    if l90_order_count >= 200:
                        p60 = float(np.percentile(gl90["net_sales"].to_numpy(), 60))
                        if p60 > 0:
                            threshold = p60
                            threshold_source = "l90_p60_data_derived"
        except Exception:
            threshold = None
            threshold_source = "data_missing"

        if threshold is None and cfg_threshold is not None:
            threshold = cfg_threshold
            threshold_source = "cfg_merchant_declared"
    else:
        # Flag OFF — preserve S7-T3.5 cfg-only behavior.
        if cfg_threshold is not None:
            threshold = cfg_threshold
            threshold_source = "cfg_merchant_declared"

    if threshold is None or threshold <= 0:
        res = _empty(
            play_id,
            reason="data_missing",
            segment_definition=seg_def,
            data_used=data_used,
        )
        res.threshold_source = "data_missing"
        return res

    lower_band = float(threshold) - 15.0
    upper_band = float(threshold) - 5.0
    seg_def = (
        f"customers with cart/typical AOV in [${lower_band:.2f}, ${upper_band:.2f}] "
        f"(${threshold:.2f} threshold minus $5-$15 band, snapshot)"
    )

    cart_col: Optional[str] = None
    for c in ("cart_state_total", "current_cart_total"):
        if c in g.columns:
            cart_col = c
            break

    ids: Set[str] = set()
    # S-FE-descriptive-distribution (L-EV-19): per-customer typical AOV for
    # the resolved in-band cohort (the AOV-gap series — the band the
    # threshold sits above). Marker None per L-EV-20 (threshold_aov as the
    # annotation parameter is None/TODO(S14); the builder's internal
    # ``threshold`` is a band-derivation input, not the marker annotation).
    aov_by_cust_band: Dict[str, float] = {}
    if cart_col is not None:
        try:
            gg = g.copy()
            gg[cart_col] = pd.to_numeric(gg[cart_col], errors="coerce")
            gg = gg[~gg[cart_col].isna()]
            cart_by_cust = gg.groupby("customer_id")[cart_col].max()
            in_band = cart_by_cust[
                (cart_by_cust >= lower_band) & (cart_by_cust <= upper_band)
            ]
            ids = set(in_band.index.astype(str))
            aov_by_cust_band = {
                str(k): float(v) for k, v in in_band.items() if v is not None
            }
        except Exception:
            ids = set()
            aov_by_cust_band = {}
    else:
        if "net_sales" not in g.columns or "Created at" not in g.columns:
            return _empty(
                play_id,
                reason="data_missing",
                segment_definition=seg_def,
                data_used=data_used,
            )
        maxd = _max_created_at(g)
        if maxd is None:
            return _empty(
                play_id,
                reason="data_missing",
                segment_definition=seg_def,
                data_used=data_used,
            )
        lookback_days = _safe_int_cfg(cfg, "AOV_BUNDLE_LOOKBACK_DAYS", 90)
        lb_start = maxd - pd.Timedelta(days=lookback_days)
        gg = g.copy()
        gg["Created at"] = pd.to_datetime(gg["Created at"], errors="coerce")
        gg = gg[~gg["Created at"].isna()]
        gg = gg[gg["Created at"] >= lb_start]
        if gg.empty:
            return AudienceResult(
                play_id=play_id,
                segment_definition=seg_def,
                audience_size=0,
                audience_ids=set(),
                data_used=data_used,
                preliminary_rejection_reason="audience_too_small",
            )
        gg["customer_id"] = gg["customer_id"].astype(str)
        gg["net_sales"] = pd.to_numeric(gg["net_sales"], errors="coerce")
        gg = gg[~gg["net_sales"].isna()]
        if gg.empty:
            return AudienceResult(
                play_id=play_id,
                segment_definition=seg_def,
                audience_size=0,
                audience_ids=set(),
                data_used=data_used,
                preliminary_rejection_reason="audience_too_small",
            )
        avg_by_cust = gg.groupby("customer_id")["net_sales"].mean()
        in_band = avg_by_cust[
            (avg_by_cust >= lower_band) & (avg_by_cust <= upper_band)
        ]
        ids = set(in_band.index.astype(str))
        aov_by_cust_band = {
            str(k): float(v) for k, v in in_band.items() if v is not None
        }

    audience_size = len(ids)

    # S-FE-descriptive-distribution: AOV-gap series for the resolved cohort.
    descriptive_series: List[float] = [
        aov_by_cust_band[c] for c in sorted(ids) if c in aov_by_cust_band
    ]

    min_n = _safe_int_cfg(cfg, "MIN_N_AOV_BUNDLE", 0)
    if cfg and bool(cfg.get("ENGINE_V2_STORE_PROFILE", False)):
        store_profile = cfg.get("_store_profile") if isinstance(cfg, dict) else None
        if store_profile is not None:
            gate = getattr(store_profile, "gate_calibration", None)
            if gate is not None:
                floors = getattr(gate, "audience_floor_by_play_id", None) or {}
                profile_floor = floors.get(play_id)
                if profile_floor is None:
                    profile_floor = floors.get("_default")
                if profile_floor is not None:
                    try:
                        min_n = int(profile_floor)
                    except (TypeError, ValueError):
                        pass

    if audience_size == 0:
        reason = "audience_too_small"
    elif min_n > 0 and audience_size < min_n:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
        threshold_source=threshold_source,
        descriptive_kind="AOV_GAP",
        descriptive_series=descriptive_series,
        descriptive_marker=None,
    )


def bestseller_buyers(
    g: pd.DataFrame, aligned: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None
) -> AudienceResult:
    """Customers who have bought the top product (by orders or net_sales).

    Source: ``src.segments.build_segments`` bestseller_amplify cohort.
    The legacy ``_compute_candidates`` AOV-comparison candidate uses
    the count of recent orders as ``audience_size``; here we follow the
    SEGMENT-based definition (top-product buyers) because that is what
    the audience attachment CSV actually contains.
    """

    play_id = "bestseller_amplify"
    data_used = ["g.lineitem_any", "g.net_sales", "g.customer_id"]
    seg_def = "buyers of top-revenue product"

    if g is None or g.empty or "customer_id" not in g.columns:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    ids: Set[str] = set()
    if "lineitem_any" in g.columns and "net_sales" in g.columns:
        try:
            top_sku_series = (
                g.groupby("lineitem_any")["net_sales"].sum().sort_values(ascending=False).head(1)
            )
            sku_name = top_sku_series.index[0] if len(top_sku_series) > 0 else None
            if sku_name is not None:
                buyers = g[g["lineitem_any"] == sku_name]["customer_id"]
                ids = _ids_as_str_set(buyers)
        except Exception:
            ids = set()

    audience_size = len(ids)
    min_n = _safe_int_cfg(cfg, "MIN_N_SKU", 30)
    if audience_size == 0:
        reason = "data_missing"
    elif audience_size < min_n:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


def discount_dependent_buyers(
    g: pd.DataFrame, aligned: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None
) -> AudienceResult:
    """Customers with sufficient discounted-order history in the recent window.

    Source: ``_compute_candidates`` discount-rate Welch test. The
    audience there is the number of recent orders with a finite
    ``discount_rate`` value (the Welch test gates on ``n1 > 0``); we
    expose that same precondition as a customer-id set for overlap math.
    """

    play_id = "discount_hygiene"
    data_used = ["g.discount_rate", "g.customer_id", "aligned.window_days"]
    seg_def = "customers with discounted recent orders"

    if (
        g is None
        or g.empty
        or "customer_id" not in g.columns
        or "discount_rate" not in g.columns
        or "Created at" not in g.columns
    ):
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    win = int((aligned or {}).get("window_days") or 28)
    maxd = _max_created_at(g)
    if maxd is None:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    start = maxd - pd.Timedelta(days=win - 1)
    rec = g[g["Created at"] >= start].copy()
    rec["discount_rate"] = pd.to_numeric(rec["discount_rate"], errors="coerce")
    rec = rec[(rec["discount_rate"] >= 0) & (rec["discount_rate"] <= 0.8)]
    ids = _ids_as_str_set(rec["customer_id"])
    audience_size = len(ids)
    seg_def = f"customers with discounted orders in last {win} days"

    min_n = _safe_int_cfg(cfg, "MIN_N_SKU", 30)
    if audience_size == 0:
        reason = "data_missing"
    elif audience_size < min_n:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


def subscription_candidates(
    g: pd.DataFrame, aligned: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None
) -> AudienceResult:
    """Customers with >= subscription-threshold orders of the same product in 90 days.

    Source: ``_compute_candidates`` subscription_nudge block + the
    same cohort builder used by ``src.segments.build_segments``.
    """

    play_id = "subscription_nudge"
    data_used = ["g.lineitem_any", "g.customer_id", "g.Created at"]
    seg_def = "customers with >=3 same-product orders in last 90 days"

    if g is None or g.empty or "customer_id" not in g.columns or "Created at" not in g.columns:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    maxd = _max_created_at(g)
    if maxd is None:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    start90 = maxd - pd.Timedelta(days=90)
    gg = g[g["Created at"] >= start90].copy()
    if gg.empty or not any(c in gg.columns for c in ("lineitem_any", "products_concat", "Lineitem name")):
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    try:
        from .features import build_g_items
        from .utils import subscription_threshold_for_product

        rep = build_g_items(gg)
    except Exception:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    if rep is None or rep.empty:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    prod_col = "product_key"
    try:
        if (cfg or {}).get("FEATURES_PRODUCT_NORMALIZATION") and "product_key_base" in rep.columns:
            prod_col = "product_key_base"
    except Exception:
        pass

    try:
        rep["_thr"] = rep[prod_col].astype(str).apply(
            lambda s: subscription_threshold_for_product(s, cfg)
        )
        cohort = rep[rep["orders_product"] >= rep["_thr"]]
        ids = _ids_as_str_set(cohort["customer_id"])
    except Exception:
        ids = set()

    audience_size = len(ids)
    # Legacy emitter requires audience >= max(50, MIN_N_SKU//2).
    floor = max(50, int(_safe_int_cfg(cfg, "MIN_N_SKU", 60) // 2))
    if audience_size == 0:
        reason = "data_missing"
    elif audience_size < floor:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


def routine_completion_candidates(
    g: pd.DataFrame, aligned: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None
) -> AudienceResult:
    """Single-product skincare buyers in the recent 60-day window.

    Source: ``_compute_candidates`` routine_builder block. Filters to
    skincare category if available, then to customers with <=1 distinct
    product across the lookback 90-day window.
    """

    play_id = "routine_builder"
    data_used = ["g.category", "g.lineitem_any", "g.customer_id", "g.Created at"]
    seg_def = "skincare single-product buyers in last 60 days"

    if g is None or g.empty or "customer_id" not in g.columns or "Created at" not in g.columns:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    maxd = _max_created_at(g)
    if maxd is None:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    recent_start = maxd - pd.Timedelta(days=60)
    lookback_start = maxd - pd.Timedelta(days=90)
    gr = g[g["Created at"] >= recent_start].copy()
    if "category" in gr.columns:
        gr_skin = gr[gr["category"].astype(str).str.lower() == "skincare"].copy()
    else:
        gr_skin = gr.copy()

    cand_ids = _ids_as_str_set(gr_skin["customer_id"])
    if not cand_ids:
        return AudienceResult(
            play_id=play_id,
            segment_definition=seg_def,
            audience_size=0,
            audience_ids=set(),
            data_used=data_used,
            preliminary_rejection_reason="audience_too_small",
        )

    gl = g[g["Created at"] >= lookback_start].copy()
    gl["customer_id"] = gl["customer_id"].astype(str)

    single_prod_ids: Set[str] = set()
    try:
        from .features import build_g_items

        gi2 = build_g_items(gl)
        if gi2 is not None and not gi2.empty:
            k = gi2.groupby("customer_id")["product_key"].nunique()
            single_prod_ids = set(k[k <= 1].index.astype(str))
        else:
            raise ValueError("g_items empty")
    except Exception:
        if "lineitem_any" in gl.columns:
            k = gl.groupby("customer_id")["lineitem_any"].nunique()
            single_prod_ids = set(k[k <= 1].index.astype(str))

    ids = cand_ids.intersection(single_prod_ids)
    audience_size = len(ids)

    min_n = _safe_int_cfg(cfg, "MIN_N_SKU", 60)
    if audience_size == 0:
        reason = "audience_too_small"
    elif audience_size < min_n:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


def depletion_window_buyers(
    g: pd.DataFrame, aligned: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None
) -> AudienceResult:
    """Customers near predicted depletion of their last purchased size.

    Source: ``_compute_candidates`` empty_bottle block. Targets if
    ``days_since_last`` is within +/- 3 days of a parsed-size depletion
    horizon (25/40/75 days for 30ml/50ml/100ml or 1oz/1.7oz/3.4oz).
    """

    play_id = "empty_bottle"
    data_used = ["g.lineitem_any", "g.days_since_last", "g.customer_id"]
    seg_def = "customers within +/-3d of depletion based on size token"

    if (
        g is None
        or g.empty
        or "customer_id" not in g.columns
        or "lineitem_any" not in g.columns
        or "days_since_last" not in g.columns
    ):
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    last = g.sort_values("Created at").groupby("customer_id").tail(1).copy()
    names = last["lineitem_any"].astype(str).str.lower()
    size_days: List[Optional[int]] = []
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
    if window.empty:
        return AudienceResult(
            play_id=play_id,
            segment_definition=seg_def,
            audience_size=0,
            audience_ids=set(),
            data_used=data_used,
            preliminary_rejection_reason="data_missing",
        )

    dsl = window["days_since_last"].astype(float)
    dep = window["_deplete_days"].astype(float)
    m = (dsl >= (dep - 3)) & (dsl <= (dep + 3))
    cohort = window.loc[m]
    ids = _ids_as_str_set(cohort["customer_id"])
    audience_size = len(ids)

    min_n = _safe_int_cfg(cfg, "MIN_N_SKU", 60)
    if audience_size == 0:
        reason = "audience_too_small"
    elif audience_size < min_n:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


def repeat_cohort(
    g: pd.DataFrame, aligned: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None
) -> AudienceResult:
    """Customers with 2+ orders in L90, excluding the most recent 14 days.

    Source: ``_compute_candidates`` frequency_accelerator block (Phase 2).
    """

    play_id = "frequency_accelerator"
    data_used = ["g.customer_id", "g.Created at"]
    seg_def = "2+ orders in L90 excluding orders in the last 14 days"

    if g is None or g.empty or "customer_id" not in g.columns or "Created at" not in g.columns:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    maxd = _max_created_at(g)
    if maxd is None:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    l90_start = maxd - pd.Timedelta(days=90)
    l14_start = maxd - pd.Timedelta(days=14)
    l90_orders = g[g["Created at"] >= l90_start]
    counts = l90_orders["customer_id"].value_counts()
    repeat_ids = set(counts[counts >= 2].index.astype(str))
    recent_ids = _ids_as_str_set(g[g["Created at"] >= l14_start]["customer_id"])
    ids = {c for c in repeat_ids if c not in recent_ids}
    audience_size = len(ids)

    # Legacy threshold: >= 50 customers.
    if audience_size == 0:
        reason = "audience_too_small"
    elif audience_size < 50:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


def aov_growth_cohort(
    g: pd.DataFrame, aligned: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None
) -> AudienceResult:
    """Customers active 7-30 days ago.

    Source: ``_compute_candidates`` aov_momentum block (Phase 2). The
    legacy emitter additionally gates on a business-level
    ``aov_growth > 2%``; we keep that gate as a preliminary rejection
    reason rather than a hard exclusion of the audience set.
    """

    play_id = "aov_momentum"
    data_used = ["g.customer_id", "g.Created at"]
    seg_def = "customers active 7-30 days before anchor"

    if g is None or g.empty or "customer_id" not in g.columns or "Created at" not in g.columns:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    maxd = _max_created_at(g)
    if maxd is None:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    l30_start = maxd - pd.Timedelta(days=30)
    l7_start = maxd - pd.Timedelta(days=7)
    momentum = g[(g["Created at"] >= l30_start) & (g["Created at"] < l7_start)]
    ids = _ids_as_str_set(momentum["customer_id"])
    audience_size = len(ids)

    # Legacy threshold: >= 30 customers.
    if audience_size == 0:
        reason = "audience_too_small"
    elif audience_size < 30:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


def retention_at_risk(
    g: pd.DataFrame, aligned: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None
) -> AudienceResult:
    """Valuable customers (2+ historical orders) who are 45+ days inactive.

    Source: ``_compute_candidates`` retention_mastery block (Phase 2).
    """

    play_id = "retention_mastery"
    data_used = ["g.customer_id", "g.Created at"]
    seg_def = "customers >=45d inactive with 2+ historical orders"

    if g is None or g.empty or "customer_id" not in g.columns or "Created at" not in g.columns:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    maxd = _max_created_at(g)
    if maxd is None:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    last_orders = g.groupby("customer_id")["Created at"].max()
    days_since_last = (maxd - last_orders).dt.days
    at_risk = set(days_since_last[days_since_last >= 45].index.astype(str))
    counts = g["customer_id"].value_counts()
    valuable = set(counts[counts >= 2].index.astype(str))
    ids = at_risk.intersection(valuable)
    audience_size = len(ids)

    # Legacy threshold: >= 25 customers.
    if audience_size == 0:
        reason = "audience_too_small"
    elif audience_size < 25:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


def journey_one_purchase_cohort(
    g: pd.DataFrame, aligned: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None
) -> AudienceResult:
    """Customers active in the last 60 days. Heuristic stand-in for funnel.

    Source: ``_compute_candidates`` journey_optimization block (Phase 2).
    The legacy emitter additionally gates on monthly revenue and a
    returning_share threshold; we expose only the audience-size rule
    here. The min-N gate matches the legacy ``audience_journey >= 50``.
    """

    play_id = "journey_optimization"
    data_used = ["g.customer_id", "g.Created at"]
    seg_def = "customers active in the last 60 days"

    if g is None or g.empty or "customer_id" not in g.columns or "Created at" not in g.columns:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    maxd = _max_created_at(g)
    if maxd is None:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    recent = g[g["Created at"] >= maxd - pd.Timedelta(days=60)]
    ids = _ids_as_str_set(recent["customer_id"])
    audience_size = len(ids)

    if audience_size == 0:
        reason = "audience_too_small"
    elif audience_size < 50:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


def single_category_buyers(
    g: pd.DataFrame, aligned: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None
) -> AudienceResult:
    """Single-category customers with 2+ orders.

    Source: ``_compute_candidates`` category_expansion block (Phase 2).
    Note: legacy emitter uses ``lineitem_any.nunique`` as the "category"
    proxy, not the actual ``category`` column. We mirror that.
    """

    play_id = "category_expansion"
    data_used = ["g.lineitem_any", "g.customer_id", "g.Name"]
    seg_def = "single-product customers with 2+ orders (legacy proxy)"

    if g is None or g.empty or "customer_id" not in g.columns or "lineitem_any" not in g.columns:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    try:
        order_col = "Name" if "Name" in g.columns else "lineitem_any"
        stats = g.groupby("customer_id").agg({"lineitem_any": "nunique", order_col: "count"})
        stats = stats.rename(columns={"lineitem_any": "categories", order_col: "orders"})
        mask = (stats["categories"] == 1) & (stats["orders"] >= 2)
        ids = set(stats[mask].index.astype(str))
    except Exception:
        ids = set()

    audience_size = len(ids)
    if audience_size == 0:
        reason = "audience_too_small"
    elif audience_size < 40:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


def single_purchase_cohort(
    g: pd.DataFrame, aligned: Dict[str, Any], cfg: Optional[Dict[str, Any]] = None
) -> AudienceResult:
    """Customers with exactly one historical order (first->second pool).

    Source: M2 reserved registry entry ``first_to_second_purchase``
    (preferred replacement for journey_optimization). The audience is
    the natural cohort for measuring first->second conversion: every
    customer whose total order count is exactly 1.
    """

    play_id = "first_to_second_purchase"
    data_used = ["g.customer_id", "g.Name"]
    seg_def = "customers with exactly one historical order"

    if g is None or g.empty or "customer_id" not in g.columns:
        return _empty(play_id, reason="data_missing", segment_definition=seg_def, data_used=data_used)

    counts = g["customer_id"].value_counts()
    ids = set(counts[counts == 1].index.astype(str))
    audience_size = len(ids)

    # Conservative min-N: 50 (matches journey_optimization since this is
    # the preferred replacement; legacy frequency_accelerator also uses 50).
    min_n = 50
    if audience_size == 0:
        reason = "audience_too_small"
    elif audience_size < min_n:
        reason = "audience_too_small"
    else:
        reason = None

    return AudienceResult(
        play_id=play_id,
        segment_definition=seg_def,
        audience_size=audience_size,
        audience_ids=ids,
        data_used=data_used,
        preliminary_rejection_reason=reason,
    )


# ---------------------------------------------------------------------------
# Builder registry — keyed by ``audience_builder_ref`` from PlayDef.
# ---------------------------------------------------------------------------


BUILDERS: Dict[str, Any] = {
    "audience.winback_21_45_inactive": winback_21_45,
    "audience.winback_dormant_cohort": winback_dormant_cohort_candidates,
    "audience.replenishment_due": replenishment_due_candidates,
    "audience.cohort_journey_first_to_second": cohort_journey_first_to_second_candidates,
    "audience.aov_lift_via_threshold_bundle": aov_lift_via_threshold_bundle_candidates,
    "audience.discount_dependency_hygiene": discount_dependency_hygiene_candidates,
    "audience.bestseller_buyers": bestseller_buyers,
    "audience.discount_dependent_buyers": discount_dependent_buyers,
    "audience.subscription_candidates": subscription_candidates,
    "audience.routine_completion_candidates": routine_completion_candidates,
    "audience.depletion_window_buyers": depletion_window_buyers,
    "audience.repeat_cohort": repeat_cohort,
    "audience.aov_growth_cohort": aov_growth_cohort,
    "audience.retention_at_risk": retention_at_risk,
    "audience.journey_one_purchase_cohort": journey_one_purchase_cohort,
    "audience.single_category_buyers": single_category_buyers,
    "audience.single_purchase_cohort": single_purchase_cohort,
}


def get_builder(ref: str):
    """Return the builder callable for an ``audience_builder_ref``.

    Returns ``None`` if no builder is registered. Callers (M3 detector)
    should record this as ``preliminary_rejection_reason="no_builder"``.
    """

    return BUILDERS.get(ref)


__all__ = [
    "AudienceResult",
    "BUILDERS",
    "get_builder",
    # Builders
    "winback_21_45",
    "winback_dormant_cohort_candidates",
    "replenishment_due_candidates",
    "cohort_journey_first_to_second_candidates",
    "aov_lift_via_threshold_bundle_candidates",
    "discount_dependency_hygiene_candidates",
    "bestseller_buyers",
    "discount_dependent_buyers",
    "subscription_candidates",
    "routine_completion_candidates",
    "depletion_window_buyers",
    "repeat_cohort",
    "aov_growth_cohort",
    "retention_at_risk",
    "journey_one_purchase_cohort",
    "single_category_buyers",
    "single_purchase_cohort",
]
