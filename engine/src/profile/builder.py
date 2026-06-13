"""Store profile detection orchestrator + 4 skeleton detectors (Sprint 6.5-T1).

T1 ships:

- ``detect_taxonomy``  — vertical-only (env_var override authoritative;
  detected-vertical fallback via revenue-weighted token scan over product
  titles). ``subvertical`` stays ``None`` at T1; T2 fills it.
- ``detect_business_stage`` — annualized-GMV banding with conservative
  band-boundary uncertainty per founder Q2 (±25%).
- ``detect_business_model`` — subscription-led / one-time-led / hybrid
  via near-constant inter-order gap detection. Emit-only at T1; consumers
  wired in S6-T3 (founder Q5).
- ``detect_data_depth`` — direct counts from the orders DataFrame.

The orchestrator ``build_store_profile`` is a pure function: same inputs
always produce the same profile.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

from .cadence import build_subvertical_sku_assignment, compute_cadence_baseline
from .seasonality import lookup_active_seasonality
from .types import (
    BusinessModel,
    BusinessStage,
    CadenceBaseline,
    DataDepth,
    GateCalibration,
    MeasurementContext,
    ProfileProvenance,
    SeasonalityContext,
    StoreProfile,
    Taxonomy,
)


# ---------------------------------------------------------------------------
# Stage band thresholds (founder envelope; Part IV §2.3 + IM plan §2)
# ---------------------------------------------------------------------------

_STAGE_BOUNDARIES = [
    ("STARTUP", 0, 500_000),
    ("GROWTH", 500_000, 3_000_000),
    ("MATURE", 3_000_000, 20_000_000),
    ("ENTERPRISE", 20_000_000, float("inf")),
]

# Founder Q2: ±25% of a band boundary -> uncertainty=HIGH + conservative
# (smaller-store / broader) floor downstream.
_BOUNDARY_UNCERTAINTY_FRACTION = 0.25

_VALID_VERTICALS = {"beauty", "supplements", "mixed", "other_refused"}
_SUPPORTED_DETECTED = {"beauty", "supplements"}

# Sprint 6.5 Ticket T2: sub-vertical token classifier.
_TAXONOMY_YAML_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "subvertical_taxonomy.yaml"
)
_TAXONOMY_CACHE: Optional[Dict[str, Any]] = None


def load_subvertical_taxonomy(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load ``config/subvertical_taxonomy.yaml`` once and cache it.

    The cache is keyed implicitly on the default path; pass an explicit
    ``path`` to bypass the cache (used by tests).
    """

    global _TAXONOMY_CACHE
    if path is None:
        if _TAXONOMY_CACHE is not None:
            return _TAXONOMY_CACHE
        target = _TAXONOMY_YAML_PATH
    else:
        target = Path(path)

    if not target.exists():
        data: Dict[str, Any] = {"verticals": {}}
    else:
        with open(target, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    if path is None:
        _TAXONOMY_CACHE = data
    return data


def _tokenize(title: str) -> str:
    """Lowercase + collapse whitespace. ``token in tokenized_title`` substring
    match is fine for this MVP — no NLP."""
    if not isinstance(title, str):
        return ""
    return " ".join(title.lower().split())


def _score_title_against_subverticals(
    title: str, vertical_cfg: Dict[str, Any]
) -> Dict[str, int]:
    """Return ``{subvertical: net_score}`` for the given title.

    Net score = sum(token_matches) − sum(excluded_token_matches). Matches
    are substring (case-insensitive). Excluded tokens act as anti-signal
    so that e.g. a "Hair Vitamin" SKU is not classified as supplements.
    """

    tokenized = _tokenize(title)
    scores: Dict[str, int] = {}
    for subv, block in (vertical_cfg or {}).items():
        if not isinstance(block, dict):
            continue
        tokens = block.get("tokens") or []
        excluded = block.get("excluded_tokens") or []
        pos = 0
        for tok in tokens:
            if isinstance(tok, str) and tok and tok.lower() in tokenized:
                pos += 1
        neg = 0
        for tok in excluded:
            if isinstance(tok, str) and tok and tok.lower() in tokenized:
                neg += 1
        scores[subv] = pos - neg
    return scores


def detect_subvertical(
    g: pd.DataFrame,
    vertical: str,
    taxonomy_config: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], str]:
    """Revenue-weighted argmax with 2x / 3x gap check.

    Returns ``(subvertical, confidence)`` where confidence is
    ``HIGH | MEDIUM | LOW | REFUSED``.

    Algorithm (DS architect §8.1):
    1. Per-SKU title is tokenized lowercase.
    2. Per-SKU score per sub-vertical = sum(positive) − sum(excluded).
    3. SKU votes for the argmax sub-vertical (ties → no vote, drop the SKU).
    4. Aggregate revenue-share per sub-vertical across SKUs.
    5. Confidence:
       - HIGH if leader / runner-up ≥ 3.0 revenue-share ratio
       - MEDIUM if ≥ 2.0
       - LOW if ≥ 1.3
       - REFUSED → return ``mixed_<vertical>`` (LOW confidence)
    """

    if vertical not in _SUPPORTED_DETECTED:
        return None, "REFUSED"

    cfg = taxonomy_config if taxonomy_config is not None else load_subvertical_taxonomy()
    verticals_cfg = (cfg or {}).get("verticals") or {}
    vertical_cfg = verticals_cfg.get(vertical) or {}
    if not vertical_cfg:
        return f"mixed_{vertical}", "LOW"

    if g is None or len(g) == 0:
        return f"mixed_{vertical}", "LOW"

    title_col = None
    for c in ("product", "lineitem_any", "Lineitem name"):
        if c in g.columns:
            title_col = c
            break
    if title_col is None:
        return f"mixed_{vertical}", "LOW"

    weight_col = "net_sales" if "net_sales" in g.columns else None
    titles = g[title_col].astype(str).fillna("")
    weights = (
        pd.to_numeric(g[weight_col], errors="coerce").fillna(0.0)
        if weight_col is not None
        else pd.Series(np.ones(len(g)), index=g.index)
    )

    # Score each unique title once.
    unique_titles = titles.unique()
    sku_to_subv: Dict[str, Optional[str]] = {}
    for t in unique_titles:
        scores = _score_title_against_subverticals(t, vertical_cfg)
        if not scores:
            sku_to_subv[t] = None
            continue
        # Filter to positive scores only.
        positives = {s: v for s, v in scores.items() if v > 0}
        if not positives:
            sku_to_subv[t] = None
            continue
        # Argmax (ties -> None to avoid arbitrary assignment).
        max_score = max(positives.values())
        leaders = [s for s, v in positives.items() if v == max_score]
        sku_to_subv[t] = leaders[0] if len(leaders) == 1 else None

    # Revenue-share per sub-vertical.
    total_weight = float(weights.sum())
    if total_weight <= 0:
        return f"mixed_{vertical}", "LOW"

    subv_weight: Dict[str, float] = {}
    for title, w in zip(titles, weights):
        subv = sku_to_subv.get(title)
        if subv is None:
            continue
        subv_weight[subv] = subv_weight.get(subv, 0.0) + float(w)

    if not subv_weight:
        return f"mixed_{vertical}", "LOW"

    sorted_subvs = sorted(subv_weight.items(), key=lambda kv: kv[1], reverse=True)
    leader, leader_w = sorted_subvs[0]
    leader_share = leader_w / total_weight

    if len(sorted_subvs) == 1:
        # Only one sub-vertical had any positive matches; confidence depends
        # on absolute share of revenue covered.
        if leader_share >= 0.50:
            return leader, "HIGH"
        if leader_share >= 0.25:
            return leader, "MEDIUM"
        return leader, "LOW"

    runner, runner_w = sorted_subvs[1]
    runner_share = runner_w / total_weight if total_weight > 0 else 0.0
    ratio = (leader_share / runner_share) if runner_share > 0 else float("inf")

    if ratio >= 3.0:
        return leader, "HIGH"
    if ratio >= 2.0:
        return leader, "MEDIUM"
    if ratio >= 1.3:
        return leader, "LOW"
    return f"mixed_{vertical}", "LOW"


# ---------------------------------------------------------------------------
# Lightweight detected-vertical token scan (real classifier ships at T2)
# ---------------------------------------------------------------------------

_BEAUTY_HINT_TOKENS = (
    "serum", "moisturizer", "cleanser", "toner", "spf", "sunscreen",
    "shampoo", "conditioner", "lipstick", "mascara", "foundation",
    "eye cream", "face mask", "body wash", "body lotion", "skin",
    "retinol", "niacinamide", "hyaluronic", "cream",
)

_SUPPLEMENT_HINT_TOKENS = (
    "protein", "whey", "vitamin", "multivitamin", "probiotic",
    "creatine", "bcaa", "collagen", "omega", "ashwagandha", "magnesium",
    "zinc", "iron", "fish oil", "amino", "capsule", "tablet",
)


def _detected_vertical_from_titles(g: pd.DataFrame) -> Tuple[Optional[str], str]:
    """Revenue-weighted hint scan over product titles.

    Returns ``(detected_vertical, confidence)`` where confidence is
    ``HIGH | MEDIUM | LOW | REFUSED``. This is a T1 stub; the real
    revenue-weighted token classifier ships at T2.
    """

    if g is None or len(g) == 0:
        return None, "REFUSED"
    title_col = None
    for c in ("product", "lineitem_any", "Lineitem name"):
        if c in g.columns:
            title_col = c
            break
    if title_col is None:
        return None, "REFUSED"

    weight_col = "net_sales" if "net_sales" in g.columns else None
    titles = g[title_col].astype(str).str.lower().fillna("")
    weights = (
        pd.to_numeric(g[weight_col], errors="coerce").fillna(0.0)
        if weight_col is not None
        else pd.Series(np.ones(len(g)), index=g.index)
    )
    total_weight = float(weights.sum())
    if total_weight <= 0:
        return None, "REFUSED"

    def _score(tokens: Tuple[str, ...]) -> float:
        mask = pd.Series(False, index=titles.index)
        for tok in tokens:
            mask = mask | titles.str.contains(tok, regex=False, na=False)
        return float(weights[mask].sum())

    beauty_w = _score(_BEAUTY_HINT_TOKENS)
    supplement_w = _score(_SUPPLEMENT_HINT_TOKENS)
    beauty_share = beauty_w / total_weight
    supplement_share = supplement_w / total_weight

    if beauty_share < 0.05 and supplement_share < 0.05:
        return None, "REFUSED"

    if beauty_share > supplement_share:
        leader, leader_share = "beauty", beauty_share
        runner = supplement_share
    else:
        leader, leader_share = "supplements", supplement_share
        runner = beauty_share

    if runner <= 0.0:
        # Avoid division-by-zero; treat leader_share alone.
        if leader_share >= 0.30:
            return leader, "HIGH"
        if leader_share >= 0.15:
            return leader, "MEDIUM"
        return leader, "LOW"

    ratio = leader_share / runner
    if ratio >= 3.0 and leader_share >= 0.30:
        return leader, "HIGH"
    if ratio >= 2.0:
        return leader, "MEDIUM"
    return leader, "LOW"


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


def detect_taxonomy(
    g: pd.DataFrame,
    cfg: Dict[str, Any],
    rules_fired: list,
) -> Taxonomy:
    """Vertical detection. Operator override (``VERTICAL_MODE``) wins.

    T1 only sets ``vertical``. ``subvertical`` stays ``None`` until T2's
    token classifier ships.
    """

    detected, detected_conf = _detected_vertical_from_titles(g)

    raw_override = (cfg or {}).get("VERTICAL_MODE")
    override = str(raw_override).strip().lower() if raw_override else None

    if override and override in _VALID_VERTICALS:
        vertical = override
        operator_override_used = True
        detection_method = "env_var_override"
        vertical_confidence = "HIGH" if vertical in _SUPPORTED_DETECTED else "REFUSED"
    elif detected and detected in _SUPPORTED_DETECTED:
        vertical = detected
        operator_override_used = False
        detection_method = "token_scan"
        vertical_confidence = detected_conf
    else:
        vertical = "mixed"
        operator_override_used = False
        detection_method = "fallback_mixed"
        vertical_confidence = "LOW"

    override_disagrees = bool(
        detected
        and operator_override_used
        and detected in _SUPPORTED_DETECTED
        and detected != vertical
    )

    if override_disagrees:
        rules_fired.append({
            "rule": "vertical_override_disagrees",
            "detected": detected,
            "override": vertical,
            "detected_confidence": detected_conf,
        })

    rules_fired.append({
        "rule": "taxonomy_detected",
        "vertical": vertical,
        "detected_vertical": detected,
        "method": detection_method,
        "confidence": vertical_confidence,
    })

    # Sprint 6.5 Ticket T2: sub-vertical token classifier.
    subvertical: Optional[str] = None
    subvertical_confidence = "REFUSED"
    if vertical in _SUPPORTED_DETECTED:
        try:
            subvertical, subvertical_confidence = detect_subvertical(g, vertical)
        except Exception as e:
            rules_fired.append({
                "rule": "subvertical_classification_failed",
                "error": str(e),
            })
            subvertical, subvertical_confidence = None, "REFUSED"
        rules_fired.append({
            "rule": "subvertical_detected",
            "subvertical": subvertical,
            "confidence": subvertical_confidence,
        })

    return Taxonomy(
        vertical=vertical,
        subvertical=subvertical,
        vertical_confidence=vertical_confidence,
        subvertical_confidence=subvertical_confidence,
        detection_method=detection_method,
        operator_override_used=operator_override_used,
        detected_vertical=detected,
        override_disagrees=override_disagrees,
    )


def _annualized_gmv_from_orders(
    g: pd.DataFrame, history_days: int
) -> Tuple[float, str]:
    """Compute annualized GMV from the orders DataFrame.

    Returns ``(annualized_gmv_usd, detection_method)``.
    """

    if g is None or len(g) == 0 or "Created at" not in g.columns or "net_sales" not in g.columns:
        return 0.0, "insufficient_history"
    created = pd.to_datetime(g["Created at"], errors="coerce")
    net_sales = pd.to_numeric(g["net_sales"], errors="coerce").fillna(0.0)
    if created.isna().all():
        return 0.0, "insufficient_history"
    anchor = created.max()

    def _sum_last_n(days: int) -> float:
        cutoff = anchor - pd.Timedelta(days=days)
        return float(net_sales[created >= cutoff].sum())

    if history_days >= 360:
        gmv_l365 = _sum_last_n(365)
        return gmv_l365, "ttm"
    if history_days >= 180:
        gmv_l180 = _sum_last_n(180)
        return gmv_l180 * 2.0, "l180_x2"
    if history_days >= 90:
        gmv_l90 = _sum_last_n(90)
        return gmv_l90 * 4.0, "l90_x4"
    return 0.0, "insufficient_history"


def _band_for_gmv(gmv: float) -> str:
    for name, lo, hi in _STAGE_BOUNDARIES:
        if lo <= gmv < hi:
            return name
    return "STARTUP"


def _is_near_band_boundary(gmv: float) -> Tuple[bool, Optional[str]]:
    """Return ``(near_boundary, boundary_label)``.

    Within ±25% of any band boundary triggers ``uncertainty=HIGH``.
    """

    boundaries = [
        ("startup_growth", 500_000),
        ("growth_mature", 3_000_000),
        ("mature_enterprise", 20_000_000),
    ]
    for label, threshold in boundaries:
        lo = threshold * (1.0 - _BOUNDARY_UNCERTAINTY_FRACTION)
        hi = threshold * (1.0 + _BOUNDARY_UNCERTAINTY_FRACTION)
        if lo <= gmv <= hi:
            return True, label
    return False, None


def _conservative_broader_stage(stage: str) -> str:
    """Founder Q2: HIGH uncertainty -> use the smaller-store (broader)
    floor band. ``GROWTH`` near the GROWTH/MATURE boundary -> GROWTH still
    (already the smaller side); ``MATURE`` near the same boundary ->
    GROWTH (broader).
    """

    order = ["STARTUP", "GROWTH", "MATURE", "ENTERPRISE"]
    if stage not in order:
        return stage
    idx = order.index(stage)
    return order[max(0, idx - 1)]


_VALID_STAGE_OVERRIDES = {"STARTUP", "GROWTH", "MATURE", "ENTERPRISE"}


def detect_business_stage(
    g: pd.DataFrame,
    data_depth: DataDepth,
    cfg: Dict[str, Any],
    rules_fired: list,
) -> BusinessStage:
    """Annualized-GMV stage band with operator override + boundary uncertainty."""

    raw_override = (cfg or {}).get("BUSINESS_STAGE")
    override = str(raw_override).strip().upper() if raw_override else None

    gmv, detection_method = _annualized_gmv_from_orders(
        g, history_days=data_depth.history_days
    )
    detected_stage = _band_for_gmv(gmv) if detection_method != "insufficient_history" else "STARTUP"

    near_boundary, boundary_label = _is_near_band_boundary(gmv)
    uncertainty = "HIGH" if near_boundary else "LOW"
    conservative_floor_applied = False

    if override and override in _VALID_STAGE_OVERRIDES:
        stage = override
        operator_override_used = True
        detection_method_out = "env_var_override"
        rules_fired.append({
            "rule": "business_stage_override",
            "override": override,
            "detected": detected_stage,
            "annualized_gmv_usd": gmv,
        })
    else:
        stage = detected_stage
        operator_override_used = False
        detection_method_out = detection_method
        if uncertainty == "HIGH":
            broader = _conservative_broader_stage(detected_stage)
            downgrade_applies = broader != detected_stage
            if downgrade_applies:
                stage = broader
                conservative_floor_applied = True
            # Founder Q2 contract: stage_boundary_uncertainty rule fires
            # whenever GMV is within ±25% of ANY boundary (symmetric, both
            # sides). conservative_floor_applied is a SEPARATE flag that is
            # True only when a smaller-band downgrade is available (i.e.
            # NOT at the STARTUP floor).
            rules_fired.append({
                "rule": "stage_boundary_uncertainty",
                "boundary": boundary_label,
                "annualized_gmv_usd": gmv,
                "detected_stage": detected_stage,
                "applied_stage": stage,
                "conservative_floor_applied": conservative_floor_applied,
            })

    rules_fired.append({
        "rule": "business_stage_detected",
        "stage": stage,
        "detected_stage": detected_stage,
        "annualized_gmv_usd": gmv,
        "method": detection_method_out,
        "uncertainty": uncertainty,
    })

    return BusinessStage(
        stage=stage,
        annualized_gmv_usd=float(gmv),
        detection_method=detection_method_out,
        operator_override_used=operator_override_used,
        uncertainty=uncertainty,
        conservative_floor_applied=conservative_floor_applied,
        detected_stage=detected_stage,
    )


def detect_business_model(
    g: pd.DataFrame, data_depth: DataDepth, rules_fired: list
) -> BusinessModel:
    """Subscription-led / one-time-led / hybrid detection.

    Heuristic: customers with >=3 orders at near-constant inter-order gap
    (sigma/mu < 0.3) contribute their L180 orders to the subscription
    bucket. Subscription fraction = bucket_orders / L180_orders.
    """

    if g is None or len(g) == 0 or "Created at" not in g.columns or "customer_id" not in g.columns:
        rules_fired.append({"rule": "business_model_insufficient_data"})
        return BusinessModel()

    created = pd.to_datetime(g["Created at"], errors="coerce")
    anchor = created.max()
    if pd.isna(anchor):
        rules_fired.append({"rule": "business_model_insufficient_data"})
        return BusinessModel()
    cutoff_180 = anchor - pd.Timedelta(days=180)
    in_window = created >= cutoff_180
    l180_orders = int(in_window.sum())
    if l180_orders == 0:
        rules_fired.append({"rule": "business_model_no_l180_orders"})
        return BusinessModel()

    n_subscription_orders = 0
    df_sorted = g.assign(_created=created).sort_values(["customer_id", "_created"])
    for cust_id, group in df_sorted.groupby("customer_id"):
        ts = group["_created"].dropna()
        if len(ts) < 3:
            continue
        gaps = ts.diff().dropna().dt.days.astype(float)
        gaps = gaps[gaps > 0]
        if len(gaps) < 2:
            continue
        mu = float(gaps.mean())
        sigma = float(gaps.std(ddof=0))
        if mu <= 0:
            continue
        cv = sigma / mu
        if cv < 0.3:
            cust_in_window = ((ts >= cutoff_180) & (ts <= anchor)).sum()
            n_subscription_orders += int(cust_in_window)

    sub_fraction = float(n_subscription_orders) / float(l180_orders)
    sub_fraction = max(0.0, min(1.0, sub_fraction))

    if sub_fraction > 0.40:
        model = "SUBSCRIPTION_LED"
        confidence = "HIGH" if sub_fraction > 0.55 else "MEDIUM"
    elif sub_fraction < 0.10:
        model = "ONE_TIME_LED"
        confidence = "HIGH" if sub_fraction < 0.03 else "MEDIUM"
    else:
        model = "HYBRID"
        confidence = "MEDIUM"

    rules_fired.append({
        "rule": "business_model_detected",
        "model": model,
        "subscription_fraction": sub_fraction,
        "l180_orders": l180_orders,
    })

    return BusinessModel(
        model=model,
        subscription_fraction=sub_fraction,
        detection_confidence=confidence,
    )


def detect_data_depth(g: pd.DataFrame, rules_fired: list) -> DataDepth:
    """Direct counts from the orders DataFrame."""

    if g is None or len(g) == 0 or "Created at" not in g.columns:
        return DataDepth()
    created = pd.to_datetime(g["Created at"], errors="coerce").dropna()
    if len(created) == 0:
        return DataDepth()
    history_days = int((created.max() - created.min()).days)
    n_orders = int(len(g))
    n_customers = int(g["customer_id"].nunique()) if "customer_id" in g.columns else 0

    if "customer_id" in g.columns:
        counts = g["customer_id"].value_counts()
        n_repeat_customers = int((counts >= 2).sum())
    else:
        n_repeat_customers = 0

    # n_subscription_orders is co-computed inside detect_business_model;
    # we recompute the count here so DataDepth is self-contained.
    n_subscription_orders = 0
    if "customer_id" in g.columns:
        df_sorted = g.assign(_created=created.reindex(g.index)).sort_values(
            ["customer_id", "_created"]
        )
        anchor = created.max()
        cutoff_180 = anchor - pd.Timedelta(days=180)
        for _, group in df_sorted.groupby("customer_id"):
            ts = group["_created"].dropna()
            if len(ts) < 3:
                continue
            gaps = ts.diff().dropna().dt.days.astype(float)
            gaps = gaps[gaps > 0]
            if len(gaps) < 2:
                continue
            mu = float(gaps.mean())
            sigma = float(gaps.std(ddof=0))
            if mu <= 0:
                continue
            if sigma / mu < 0.3:
                cust_in_window = ((ts >= cutoff_180) & (ts <= anchor)).sum()
                n_subscription_orders += int(cust_in_window)

    rules_fired.append({
        "rule": "data_depth_computed",
        "history_days": history_days,
        "n_orders": n_orders,
        "n_customers": n_customers,
    })

    return DataDepth(
        history_days=history_days,
        n_customers=n_customers,
        n_orders=n_orders,
        n_repeat_customers=n_repeat_customers,
        n_subscription_orders=n_subscription_orders,
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def build_store_profile(
    g: pd.DataFrame,
    cfg: Optional[Dict[str, Any]] = None,
    store_id: str = "unknown",
) -> StoreProfile:
    """Build a typed ``StoreProfile`` from the orders DataFrame.

    Pure function: same inputs always produce the same profile (modulo
    ``provenance.profiled_at`` which is the build wall-clock).

    T1 populates taxonomy (vertical only), business_stage,
    business_model, and data_depth. cadence + seasonality default to
    T3 stubs; gate_calibration + measurement default to T4 stubs.
    """

    cfg = cfg or {}
    rules_fired: list = []

    data_depth = detect_data_depth(g, rules_fired)
    taxonomy = detect_taxonomy(g, cfg, rules_fired)
    business_stage = detect_business_stage(g, data_depth, cfg, rules_fired)
    business_model = detect_business_model(g, data_depth, rules_fired)

    # Sprint 6.5 Ticket T3: cadence baseline + seasonality lookup.
    cadence = _build_cadence(g, taxonomy, rules_fired)
    seasonality = _build_seasonality(g, taxonomy, cfg, rules_fired)

    # Sprint 6.5 Ticket T4: gate calibration + measurement context (R2).
    gate_calibration, measurement = derive_gate_calibration(
        taxonomy=taxonomy,
        stage=business_stage,
        cadence=cadence,
        data_depth=data_depth,
        business_model=business_model,
        rules_fired=rules_fired,
    )

    provenance = ProfileProvenance(
        profile_version=1,
        profiled_at=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        rules_fired=rules_fired,
    )

    return StoreProfile(
        store_id=str(store_id),
        taxonomy=taxonomy,
        business_stage=business_stage,
        business_model=business_model,
        cadence=cadence,
        seasonality=seasonality,
        data_depth=data_depth,
        gate_calibration=gate_calibration,
        measurement=measurement,
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# T3 helpers
# ---------------------------------------------------------------------------


_SUPPORTED_FOR_CADENCE = {"beauty", "supplements"}


# ---------------------------------------------------------------------------
# Sprint 6.5 Ticket T4 — Gate calibration loader + derivation
# ---------------------------------------------------------------------------

_GATE_CALIBRATION_YAML_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "gate_calibration.yaml"
)
_GATE_CALIBRATION_CACHE: Optional[Dict[str, Any]] = None
_GATE_CALIBRATION_WINDOWS: Tuple[str, ...] = ("L28", "L56", "L90")
_GATE_CALIBRATION_WINDOW_DAYS: Dict[str, int] = {"L28": 28, "L56": 56, "L90": 90}

# Conservative architecture defaults (DS architect §2.8). Used when a
# cell is missing AND the YAML's _default_by_stage row is also missing.
_DEFAULT_AUDIENCE_FLOOR_BY_STAGE: Dict[str, int] = {
    "STARTUP": 50,
    "GROWTH": 150,
    "MATURE": 400,
    "ENTERPRISE": 1200,
}
_DEFAULT_MATERIALITY_FLOOR_BY_STAGE: Dict[str, float] = {
    "STARTUP": 800.0,
    "GROWTH": 2000.0,
    "MATURE": 4500.0,
    "ENTERPRISE": 12000.0,
}
_DEFAULT_PSEUDO_N_BY_STAGE: Dict[str, int] = {
    "STARTUP": 10,
    "GROWTH": 20,
    "MATURE": 30,
    "ENTERPRISE": 50,
}

# Ordering for the stage-uncertainty broader-cell fallback. HIGH
# uncertainty walks one position to the left.
_STAGE_ORDER: Tuple[str, ...] = ("STARTUP", "GROWTH", "MATURE", "ENTERPRISE")


def load_gate_calibration(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load ``config/gate_calibration.yaml`` once and cache it.

    Pass an explicit ``path`` to bypass the cache (used by tests).
    """

    global _GATE_CALIBRATION_CACHE
    if path is None:
        if _GATE_CALIBRATION_CACHE is not None:
            return _GATE_CALIBRATION_CACHE
        target = _GATE_CALIBRATION_YAML_PATH
    else:
        target = Path(path)

    if not target.exists():
        data: Dict[str, Any] = {}
    else:
        with open(target, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    if path is None:
        _GATE_CALIBRATION_CACHE = data
    return data


def _stage_key_lower(stage: str) -> str:
    return str(stage).strip().lower()


def _broader_stage(stage: str) -> Optional[str]:
    """Return the next-smaller stage in ``_STAGE_ORDER`` or ``None`` at floor."""
    s = str(stage).strip().upper()
    if s not in _STAGE_ORDER:
        return None
    idx = _STAGE_ORDER.index(s)
    if idx == 0:
        return None
    return _STAGE_ORDER[idx - 1]


def _resolve_audience_floor_cell(
    yaml_block: Dict[str, Any],
    *,
    play_id: str,
    vertical: str,
    subvertical: Optional[str],
    stage: str,
    rules_fired: list,
) -> Tuple[int, str]:
    """Return ``(floor, source_path)`` for one (play, vertical, subv, stage).

    Cascade:
    1. ``audience_floors.<play_id>.<vertical>.<subvertical>.<stage>``
    2. ``audience_floors.<play_id>.mixed_<vertical>.<stage>`` (REFUSED subv)
    3. ``audience_floors._default_by_stage.<stage>``
    4. ``_DEFAULT_AUDIENCE_FLOOR_BY_STAGE`` constant.

    ``rules_fired`` accumulates a typed audit log of each fallback.
    """

    floors = (yaml_block or {}).get("audience_floors") or {}
    play_block = floors.get(play_id) if isinstance(floors, dict) else None
    stage_key = _stage_key_lower(stage)

    if isinstance(play_block, dict):
        v_block = play_block.get(vertical)
        if isinstance(v_block, dict):
            # First: typed sub-vertical cell.
            if subvertical and subvertical not in {"mixed", "other_refused"}:
                sv_block = v_block.get(subvertical)
                if isinstance(sv_block, dict) and stage_key in sv_block:
                    return (
                        int(sv_block[stage_key]),
                        f"gate_calibration.audience_floors.{play_id}.{vertical}.{subvertical}.{stage_key}",
                    )
            # Second: REFUSED subvertical → ``mixed_<vertical>`` row.
            mixed_block = play_block.get(f"mixed_{vertical}")
            if isinstance(mixed_block, dict) and stage_key in mixed_block:
                rules_fired.append({
                    "rule": "gate_calibration_mixed_vertical_fallback",
                    "play_id": play_id,
                    "vertical": vertical,
                    "subvertical": subvertical,
                    "stage": stage_key,
                })
                return (
                    int(mixed_block[stage_key]),
                    f"gate_calibration.audience_floors.{play_id}.mixed_{vertical}.{stage_key}",
                )

    # Third: yaml _default_by_stage row.
    default_row = floors.get("_default_by_stage") if isinstance(floors, dict) else None
    if isinstance(default_row, dict) and stage_key in default_row:
        rules_fired.append({
            "rule": "gate_calibration_default_floor_used",
            "play_id": play_id,
            "vertical": vertical,
            "subvertical": subvertical,
            "stage": stage_key,
        })
        return (
            int(default_row[stage_key]),
            f"gate_calibration.audience_floors._default_by_stage.{stage_key}",
        )

    # Fourth: hard-coded conservative default.
    rules_fired.append({
        "rule": "gate_calibration_cell_missing",
        "seam": "audience_floor",
        "play_id": play_id,
        "vertical": vertical,
        "subvertical": subvertical,
        "stage": stage_key,
    })
    return (
        int(_DEFAULT_AUDIENCE_FLOOR_BY_STAGE.get(str(stage).upper(), 500)),
        "gate_calibration.audience_floors._architecture_default",
    )


def _resolve_audience_floor_cell_strict(
    yaml_block: Dict[str, Any],
    *,
    play_id: str,
    vertical: str,
    subvertical: Optional[str],
    stage: str,
    rules_fired: list,
) -> Tuple[Optional[int], Optional[str]]:
    """Strict variant of ``_resolve_audience_floor_cell``: returns
    ``(None, None)`` when no per-play cell covers (vertical, subvertical,
    stage). NEVER cascades to ``_default_by_stage`` or to the
    architecture default.

    Introduced for S6-T3.5 Commit B (``replenishment_due``). The
    asymmetric posture (beauty has a validated prior; supplements
    deliberately does NOT) means a silently-applied default would mask
    the "no cell" signal at the consumer. Returning None forces the
    consumer to treat the play as un-floored for that (vertical,
    subvertical), matching the prior coverage gap by design.

    Cascade:
    1. ``audience_floors.<play_id>.<vertical>.<subvertical>.<stage>``
    2. ``audience_floors.<play_id>.mixed_<vertical>.<stage>`` (REFUSED subv)
    3. ``(None, None)``  — NO default fallback.
    """

    floors = (yaml_block or {}).get("audience_floors") or {}
    play_block = floors.get(play_id) if isinstance(floors, dict) else None
    stage_key = _stage_key_lower(stage)

    if isinstance(play_block, dict):
        v_block = play_block.get(vertical)
        if isinstance(v_block, dict):
            if subvertical and subvertical not in {"mixed", "other_refused"}:
                sv_block = v_block.get(subvertical)
                if isinstance(sv_block, dict) and stage_key in sv_block:
                    return (
                        int(sv_block[stage_key]),
                        f"gate_calibration.audience_floors.{play_id}.{vertical}.{subvertical}.{stage_key}",
                    )
            mixed_block = play_block.get(f"mixed_{vertical}")
            if isinstance(mixed_block, dict) and stage_key in mixed_block:
                rules_fired.append({
                    "rule": "gate_calibration_mixed_vertical_fallback",
                    "play_id": play_id,
                    "vertical": vertical,
                    "subvertical": subvertical,
                    "stage": stage_key,
                })
                return (
                    int(mixed_block[stage_key]),
                    f"gate_calibration.audience_floors.{play_id}.mixed_{vertical}.{stage_key}",
                )

    rules_fired.append({
        "rule": "gate_calibration_cell_missing_strict",
        "seam": "audience_floor",
        "play_id": play_id,
        "vertical": vertical,
        "subvertical": subvertical,
        "stage": stage_key,
    })
    return (None, None)


def _resolve_materiality_floor(
    yaml_block: Dict[str, Any], *, stage: str, rules_fired: list,
) -> Tuple[float, str]:
    cells = (yaml_block or {}).get("materiality_floors_usd") or {}
    stage_key = _stage_key_lower(stage)
    if isinstance(cells, dict) and stage_key in cells:
        try:
            return (
                float(cells[stage_key]),
                f"gate_calibration.materiality_floors_usd.{stage_key}",
            )
        except (TypeError, ValueError):
            pass
    rules_fired.append({
        "rule": "gate_calibration_cell_missing",
        "seam": "materiality_floor",
        "stage": stage_key,
    })
    return (
        float(_DEFAULT_MATERIALITY_FLOOR_BY_STAGE.get(str(stage).upper(), 5000.0)),
        "gate_calibration.materiality_floors_usd._architecture_default",
    )


def _resolve_pseudo_n_default(
    yaml_block: Dict[str, Any], *, stage: str, rules_fired: list,
) -> Tuple[int, str]:
    cells = (yaml_block or {}).get("pseudo_n_default") or {}
    stage_key = _stage_key_lower(stage)
    if isinstance(cells, dict) and stage_key in cells:
        try:
            return (
                int(cells[stage_key]),
                f"gate_calibration.pseudo_n_default.{stage_key}",
            )
        except (TypeError, ValueError):
            pass
    rules_fired.append({
        "rule": "gate_calibration_cell_missing",
        "seam": "pseudo_n_default",
        "stage": stage_key,
    })
    return (
        int(_DEFAULT_PSEUDO_N_BY_STAGE.get(str(stage).upper(), 20)),
        "gate_calibration.pseudo_n_default._architecture_default",
    )


def _resolve_replenishment_due_per_sku_floor(
    yaml_block: Dict[str, Any], *, stage: str, rules_fired: list,
) -> Tuple[Optional[int], Optional[str]]:
    """S7.6-T2.5-fix — per-stage scalar floor for the per-SKU contributing-
    customer count inside ``replenishment_due_candidates``. Mirrors the
    ``_resolve_pseudo_n_default`` shape (per-stage scalar, no
    vertical/subvertical axis). Missing cell => return ``(None, None)``
    so the consumer falls back to env override / module default per the
    documented resolution order. See DS architect scope card 2026-05-22.
    """

    cells = (yaml_block or {}).get("replenishment_due_per_sku_floor") or {}
    stage_key = _stage_key_lower(stage)
    if isinstance(cells, dict) and stage_key in cells:
        try:
            return (
                int(cells[stage_key]),
                f"gate_calibration.replenishment_due_per_sku_floor.{stage_key}",
            )
        except (TypeError, ValueError):
            pass
    rules_fired.append({
        "rule": "gate_calibration_cell_missing",
        "seam": "replenishment_due_per_sku_floor",
        "stage": stage_key,
    })
    return (None, None)


def _resolve_static_primary_window(
    yaml_block: Dict[str, Any], *, vertical: str, subvertical: Optional[str],
) -> Tuple[str, str]:
    cells = (yaml_block or {}).get("primary_window") or {}
    v_block = cells.get(vertical) if isinstance(cells, dict) else None
    if isinstance(v_block, dict):
        sv_key = subvertical if subvertical else "mixed"
        if sv_key in v_block:
            return (
                str(v_block[sv_key]),
                f"gate_calibration.primary_window.{vertical}.{sv_key}",
            )
        if "mixed" in v_block:
            return (
                str(v_block["mixed"]),
                f"gate_calibration.primary_window.{vertical}.mixed",
            )
    return ("L28", "gate_calibration.primary_window._architecture_default")


def _resolve_static_agreement_windows(
    yaml_block: Dict[str, Any], *, vertical: str, subvertical: Optional[str],
    primary_window: str,
) -> Tuple[List[str], str]:
    cells = (yaml_block or {}).get("agreement_windows") or {}
    v_block = cells.get(vertical) if isinstance(cells, dict) else None
    if isinstance(v_block, dict):
        sv_key = subvertical if subvertical else "mixed"
        for key in (sv_key, "mixed"):
            raw = v_block.get(key)
            if isinstance(raw, list):
                windows = [str(w) for w in raw if isinstance(w, str)]
                # Defensive: always exclude primary from its own agreement set.
                windows = [w for w in windows if w != primary_window]
                if windows:
                    return windows, f"gate_calibration.agreement_windows.{vertical}.{key}"
    # Architecture default: all windows except primary.
    windows = [w for w in _GATE_CALIBRATION_WINDOWS if w != primary_window]
    return windows, "gate_calibration.agreement_windows._architecture_default"


def _round_cadence_to_window(median_days: int) -> str:
    """R2 round-to-nearest of ``{L28, L56, L90}`` for a cadence median."""
    best = "L28"
    best_dist = abs(median_days - _GATE_CALIBRATION_WINDOW_DAYS["L28"])
    for win in _GATE_CALIBRATION_WINDOWS:
        dist = abs(median_days - _GATE_CALIBRATION_WINDOW_DAYS[win])
        if dist < best_dist:
            best = win
            best_dist = dist
    return best


def derive_gate_calibration(
    taxonomy: Taxonomy,
    stage: BusinessStage,
    cadence: CadenceBaseline,
    data_depth: DataDepth,
    business_model: BusinessModel,
    *,
    yaml_block: Optional[Dict[str, Any]] = None,
    rules_fired: Optional[list] = None,
) -> Tuple[GateCalibration, MeasurementContext]:
    """Pure derivation of ``GateCalibration`` + ``MeasurementContext``.

    Same inputs → same outputs. Provenance is appended to
    ``rules_fired`` (caller's list); pass a fresh list to keep the
    function output-only.

    Stage-uncertainty rule (DS architect §2.3): when
    ``stage.uncertainty == "HIGH"``, the broader (next-smaller) stage's
    cell is consulted across audience_floor + materiality_floor +
    pseudo_n_default. The conservative posture: smaller stores have
    tighter floors, so reading the broader cell errors toward NOT
    surfacing a noise card on a boundary-uncertain store.

    R2 primary_window derivation:
    - ``business_model == SUBSCRIPTION_LED`` → static cell ALWAYS;
      fires ``subscription_led_static_window``.
    - cadence has a per-class median for the resolved sub-vertical
      AND status is not INSUFFICIENT_DATA → round-to-nearest of
      ``{L28, L56, L90}``; fires ``cadence_derived_primary_window``.
    - Otherwise → static cell; fires ``cadence_fallback_static_window``.
    """

    rules_fired = rules_fired if rules_fired is not None else []
    yaml_block = yaml_block if yaml_block is not None else load_gate_calibration()

    vertical = (taxonomy.vertical or "").strip().lower() or "mixed"
    subvertical = taxonomy.subvertical
    detected_stage = (stage.stage or "").strip().upper() or "STARTUP"

    # Stage-uncertainty broader-cell fallback (DS architect §2.3).
    if stage.uncertainty == "HIGH":
        broader = _broader_stage(detected_stage)
        if broader is not None:
            rules_fired.append({
                "rule": "gate_calibration_stage_uncertainty_broader_cell",
                "detected_stage": detected_stage,
                "applied_stage": broader,
            })
            applied_stage = broader
        else:
            applied_stage = detected_stage
    else:
        applied_stage = detected_stage

    # --- audience_floor_by_play_id (winback_dormant_cohort is the only
    # play with a fully-populated cell table at S6.5; other plays use
    # _default_by_stage via the same resolver).
    audience_floors: Dict[str, int] = {}
    profile_field_refs: Dict[str, str] = {}
    for play_id in ("winback_dormant_cohort",):
        floor, source_path = _resolve_audience_floor_cell(
            yaml_block,
            play_id=play_id,
            vertical=vertical,
            subvertical=subvertical,
            stage=applied_stage,
            rules_fired=rules_fired,
        )
        audience_floors[play_id] = floor
        profile_field_refs[f"audience_floor.{play_id}"] = source_path

    # --- Strict-cell plays: per-play floors that MUST NOT cascade to
    # ``_default_by_stage``. When a cell is missing the play key is
    # omitted from ``audience_floors`` entirely (consumers reading
    # ``floors.get(play_id)`` see ``None`` and treat the play as
    # un-floored for that taxonomy cell). See
    # ``_resolve_audience_floor_cell_strict`` docstring for rationale.
    for play_id in (
        "replenishment_due",
        "cohort_journey_first_to_second",
        "discount_dependency_hygiene",
        "aov_lift_via_threshold_bundle",
    ):
        strict_floor, strict_source = _resolve_audience_floor_cell_strict(
            yaml_block,
            play_id=play_id,
            vertical=vertical,
            subvertical=subvertical,
            stage=applied_stage,
            rules_fired=rules_fired,
        )
        if strict_floor is not None:
            audience_floors[play_id] = strict_floor
            profile_field_refs[f"audience_floor.{play_id}"] = strict_source
        # else: deliberately omit (None) — consumers see "no cell".

    # Also resolve the default-by-stage so consumers without a per-play
    # cell can read profile.gate_calibration.audience_floor_by_play_id
    # via "_default" key.
    default_floor, default_source = _resolve_audience_floor_cell(
        yaml_block,
        play_id="_default",
        vertical=vertical,
        subvertical=subvertical,
        stage=applied_stage,
        rules_fired=rules_fired,
    )
    audience_floors["_default"] = default_floor
    profile_field_refs["audience_floor._default"] = default_source

    # --- materiality_floor_usd
    materiality_floor, mat_source = _resolve_materiality_floor(
        yaml_block, stage=applied_stage, rules_fired=rules_fired,
    )
    profile_field_refs["materiality_floor"] = mat_source

    # --- pseudo_n_default
    pseudo_n, pn_source = _resolve_pseudo_n_default(
        yaml_block, stage=applied_stage, rules_fired=rules_fired,
    )
    profile_field_refs["pseudo_n_default"] = pn_source

    # --- replenishment_due_per_sku_floor (S7.6-T2.5-fix; DS 2026-05-22)
    rsku_floor, rsku_source = _resolve_replenishment_due_per_sku_floor(
        yaml_block, stage=applied_stage, rules_fired=rules_fired,
    )
    if rsku_source is not None:
        profile_field_refs["replenishment_due_per_sku_floor"] = rsku_source

    gate = GateCalibration(
        audience_floor_by_play_id=audience_floors,
        materiality_floor_usd=materiality_floor,
        pseudo_n_default=pseudo_n,
        replenishment_due_per_sku_floor=rsku_floor,
        profile_field_refs=profile_field_refs,
        detection_status="DERIVED",
    )

    # --- R2 primary_window derivation
    static_window, static_source = _resolve_static_primary_window(
        yaml_block, vertical=vertical, subvertical=subvertical,
    )

    primary_window = static_window
    primary_source = "default"

    sub_led = (business_model.model == "SUBSCRIPTION_LED")
    if sub_led:
        primary_window = static_window
        primary_source = "subscription_led_static"
        rules_fired.append({
            "rule": "subscription_led_static_window",
            "primary_window": primary_window,
            "subscription_fraction": business_model.subscription_fraction,
        })
    else:
        cadence_median = None
        if subvertical and cadence.median_reorder_days_by_sku_class:
            cadence_median = cadence.median_reorder_days_by_sku_class.get(subvertical)
        if cadence_median is not None and cadence.detection_status == "COMPUTED":
            primary_window = _round_cadence_to_window(int(cadence_median))
            primary_source = "cadence_derived"
            rules_fired.append({
                "rule": "cadence_derived_primary_window",
                "subvertical": subvertical,
                "cadence_median_days": int(cadence_median),
                "primary_window": primary_window,
            })
        else:
            primary_window = static_window
            primary_source = "cadence_fallback_static"
            rules_fired.append({
                "rule": "cadence_fallback_static_window",
                "subvertical": subvertical,
                "cadence_detection_status": cadence.detection_status,
                "primary_window": primary_window,
                "source_path": static_source,
            })

    # R2 agreement_windows: always {L28, L56, L90} \ primary_window.
    agreement_windows = [w for w in _GATE_CALIBRATION_WINDOWS if w != primary_window]

    measurement = MeasurementContext(
        primary_window=primary_window,
        agreement_windows=agreement_windows,
        primary_window_source=primary_source,
        detection_status="DERIVED",
    )

    return gate, measurement


def _build_cadence(
    g: pd.DataFrame, taxonomy: Taxonomy, rules_fired: list
) -> CadenceBaseline:
    """Populate ``CadenceBaseline`` from the subvertical-tagged SKU classes."""

    if taxonomy.vertical not in _SUPPORTED_FOR_CADENCE:
        rules_fired.append({"rule": "cadence_skipped_unsupported_vertical",
                            "vertical": taxonomy.vertical})
        return CadenceBaseline(detection_status="NOT_APPLICABLE")
    try:
        taxonomy_cfg = load_subvertical_taxonomy()
    except Exception as e:
        rules_fired.append({"rule": "cadence_taxonomy_load_failed", "error": str(e)})
        return CadenceBaseline(detection_status="INSUFFICIENT_DATA")
    assignment = build_subvertical_sku_assignment(g, taxonomy.vertical, taxonomy_cfg)
    cadence = compute_cadence_baseline(g, assignment)
    rules_fired.append({
        "rule": "cadence_computed",
        "detection_status": cadence.detection_status,
        "classes": sorted(cadence.median_reorder_days_by_sku_class.keys()),
        "global_median_reorder_days": cadence.global_median_reorder_days,
    })
    return cadence


def _resolve_run_date(g: pd.DataFrame, cfg: Dict[str, Any]) -> Optional[date]:
    raw = (cfg or {}).get("RUN_DATE")
    if raw:
        try:
            return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            pass
    if g is None or len(g) == 0 or "Created at" not in g.columns:
        return None
    created = pd.to_datetime(g["Created at"], errors="coerce").dropna()
    if len(created) == 0:
        return None
    return created.max().date()


def _build_seasonality(
    g: pd.DataFrame,
    taxonomy: Taxonomy,
    cfg: Dict[str, Any],
    rules_fired: list,
) -> SeasonalityContext:
    run_date = _resolve_run_date(g, cfg)
    if run_date is None:
        return SeasonalityContext(detection_status="INVALID_RUN_DATE")
    seasonality = lookup_active_seasonality(
        run_date, taxonomy.vertical, taxonomy.subvertical
    )
    rules_fired.append({
        "rule": "seasonality_lookup",
        "run_date": run_date.isoformat(),
        "active_window_name": seasonality.active_window_name,
        "detection_status": seasonality.detection_status,
    })
    return seasonality
