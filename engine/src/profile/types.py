"""Typed StoreProfile dataclass + 9 sub-dataclasses (Sprint 6.5-T1).

All dataclasses are ``frozen=True`` (the profile is descriptive of the store
at run time; once built it must not mutate). All fields carry safe defaults
so a pre-S6.5 ``engine_run.json`` (no ``store_profile`` key, or a partial
payload from a T1/T2/T3 build) round-trips cleanly through
``from_dict`` / ``to_dict``.

Fields populated at T1: ``Taxonomy.vertical`` + override metadata,
``BusinessStage``, ``BusinessModel``, ``DataDepth``, ``ProfileProvenance``.
``Taxonomy.subvertical`` is populated at T2. ``CadenceBaseline`` +
``SeasonalityContext`` are populated at T3. ``GateCalibration`` +
``MeasurementContext`` are populated at T4 and consumed by audience /
measurement / decide / sizing under the ``ENGINE_V2_STORE_PROFILE`` flag.

Schema-additive within the Sprint 2 ``event_version=1`` frozen contract:
``StoreProfile`` lives in an optional ``EngineRun.store_profile`` slot
that defaults to ``None`` (pre-flag and flag-OFF behavior).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Taxonomy:
    """Vertical + sub-vertical assignment with provenance.

    T1 populates ``vertical`` + override metadata; ``subvertical`` is set
    at T2 via the token classifier. ``REFUSED`` is used when the engine
    declines to assert a sub-vertical (mixed or unknown verticals).
    """

    vertical: str = "mixed"  # "beauty" | "supplements" | "mixed" | "other_refused"
    subvertical: Optional[str] = None  # populated at T2
    vertical_confidence: str = "MEDIUM"  # HIGH | MEDIUM | LOW | REFUSED
    subvertical_confidence: str = "REFUSED"  # populated at T2
    detection_method: str = "env_var_override"
    operator_override_used: bool = True
    # The detected vertical regardless of operator override. Allows
    # ``override_disagrees`` audits to flag silent mismatches.
    detected_vertical: Optional[str] = None
    override_disagrees: bool = False


@dataclass(frozen=True)
class BusinessStage:
    """Annualized-GMV stage band with band-boundary uncertainty.

    Founder Q2 (2026-05-17): stores within ±25% of a band boundary get
    ``uncertainty=HIGH`` and a broader (more conservative, smaller-store)
    floor downstream via ``conservative_floor_applied=True``.
    """

    stage: str = "STARTUP"  # STARTUP | GROWTH | MATURE | ENTERPRISE
    annualized_gmv_usd: float = 0.0
    detection_method: str = "insufficient_history"  # env_var_override | l90_x4 | l180_x2 | ttm | insufficient_history
    operator_override_used: bool = False
    uncertainty: str = "LOW"  # LOW | HIGH
    conservative_floor_applied: bool = False
    # The detected stage regardless of operator override.
    detected_stage: Optional[str] = None


@dataclass(frozen=True)
class BusinessModel:
    """One-time-led vs subscription-led vs hybrid.

    T1 detects and emits; no consumer wires this in S6.5 (Q5 deferred
    the slate-ordering change to S6-T3).
    """

    model: str = "ONE_TIME_LED"  # ONE_TIME_LED | SUBSCRIPTION_LED | HYBRID
    subscription_fraction: float = 0.0
    detection_confidence: str = "LOW"  # HIGH | MEDIUM | LOW


@dataclass(frozen=True)
class DataDepth:
    """Direct counts from the orders DataFrame."""

    history_days: int = 0
    n_customers: int = 0
    n_orders: int = 0
    n_repeat_customers: int = 0  # >=2 orders
    n_subscription_orders: int = 0  # heuristic; near-constant inter-order gaps


@dataclass(frozen=True)
class CadenceBaseline:
    """Right-censored empirical median reorder cadence per SKU class.

    T3 populates ``median_reorder_days_by_sku_class`` +
    ``global_median_reorder_days``. T1 ships the empty dataclass with
    ``detection_status="DEFERRED_TO_T3"``.

    ``method_by_sku_class`` records the per-class outcome:
    ``"empirical_median"`` (≥30 customers with ≥2 in-class purchases) or
    ``"INSUFFICIENT_DATA"`` (fewer). K-M lifts to a real survival
    estimator at S11.
    """

    median_reorder_days_by_sku_class: Dict[str, int] = field(default_factory=dict)
    method_by_sku_class: Dict[str, str] = field(default_factory=dict)
    global_median_reorder_days: Optional[int] = None
    detection_status: str = "DEFERRED_TO_T3"


@dataclass(frozen=True)
class SeasonalityContext:
    """Active calendar window lookup.

    T3 populates ``active_window_name`` + lift range + source_artifact.
    Per Part III §8 discipline: annotations only, NEVER revenue
    multipliers. ``expected_lift_range`` is always a ``[low, high]``
    pair, never a point estimate.
    """

    active_window_name: Optional[str] = None
    expected_lift_direction: Optional[str] = None  # "+", "-", "none"
    expected_lift_range: Optional[List[float]] = None  # always [low, high] or None
    source_artifact: Optional[str] = None
    detection_status: str = "DEFERRED_TO_T3"


@dataclass(frozen=True)
class GateCalibration:
    """Per-(play, vertical, subvertical, stage) audience + materiality floors.

    T4 populates ``audience_floor_by_play_id`` + ``materiality_floor_usd``
    + ``pseudo_n_default`` from ``config/gate_calibration.yaml`` keyed on
    the detected profile. Consumers (``audience_builders``, ``decide``,
    ``sizing``) read these when ``ENGINE_V2_STORE_PROFILE`` is ON and
    fall back to today's hardcoded constants when OFF.
    """

    audience_floor_by_play_id: Dict[str, int] = field(default_factory=dict)
    materiality_floor_usd: Optional[float] = None
    pseudo_n_default: Optional[int] = None
    # Per-stage scalar floor on the PER-SKU contributing-customer count
    # inside ``replenishment_due_candidates`` (S7.6-T2.5-fix; DS architect
    # scope card 2026-05-22). Distinct from the COHORT-level audience
    # floor under ``audience_floor_by_play_id["replenishment_due"]``.
    # ``None`` => consumer falls back to env override / module default.
    replenishment_due_per_sku_floor: Optional[int] = None
    # Source-paths consumed: maps a logical seam name
    # (e.g. ``"audience_floor.winback_dormant_cohort"``) to the YAML
    # cell-path it was sourced from. Consumers cite these on
    # ``PlayCard.drivers[].profile_field_ref``. Empty dict pre-T4.
    profile_field_refs: Dict[str, str] = field(default_factory=dict)
    detection_status: str = "DEFERRED_TO_T4"


@dataclass(frozen=True)
class MeasurementContext:
    """Primary + agreement windows per (vertical, subvertical).

    T4 populates from ``config/gate_calibration.yaml`` (fallback) AND
    from cadence (R2). ``primary_window`` is cadence-derived for
    non-subscription-led stores when the cadence baseline is populated
    for the relevant SKU class; otherwise it falls back to the static
    YAML cell. ``agreement_windows`` is always
    ``{L28, L56, L90} \\ primary_window`` (R1).

    ``primary_window_source`` records the derivation rule:
    ``"cadence_derived"`` / ``"subscription_led_static"`` /
    ``"cadence_fallback_static"`` / ``"default"``. Consumers branch on
    the value for audit / debugging; the value is also persisted via
    ``profile.provenance.rules_fired``.
    """

    primary_window: str = "L28"
    agreement_windows: List[str] = field(default_factory=lambda: ["L56", "L90"])
    primary_window_source: str = "default"
    detection_status: str = "DEFERRED_TO_T4"


@dataclass(frozen=True)
class ProfileProvenance:
    """Audit trail for one ``build_store_profile`` invocation.

    ``rules_fired`` is the typed log of every detection rule + override
    interaction (e.g. ``{"rule": "stage_boundary_uncertainty",
    "annualized_gmv_usd": 2800000.0, "boundary": "growth_mature"}``).
    Reviewers read this to trace any profile-driven gate decision.
    """

    profile_version: int = 1
    profiled_at: str = ""  # ISO datetime
    rules_fired: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class StoreProfile:
    """Descriptive store profile produced by ``build_store_profile``.

    A pure function of (orders DataFrame, cfg, store_id). Same inputs
    produce the same profile so cell lookups + provenance traces are
    reproducible across runs.
    """

    store_id: str = ""
    taxonomy: Taxonomy = field(default_factory=Taxonomy)
    business_stage: BusinessStage = field(default_factory=BusinessStage)
    business_model: BusinessModel = field(default_factory=BusinessModel)
    cadence: CadenceBaseline = field(default_factory=CadenceBaseline)
    seasonality: SeasonalityContext = field(default_factory=SeasonalityContext)
    data_depth: DataDepth = field(default_factory=DataDepth)
    gate_calibration: GateCalibration = field(default_factory=GateCalibration)
    measurement: MeasurementContext = field(default_factory=MeasurementContext)
    provenance: ProfileProvenance = field(default_factory=ProfileProvenance)


# ---------------------------------------------------------------------------
# Serialization helpers (mirror the engine_run.py round-trip pattern)
# ---------------------------------------------------------------------------


def _from_dict_taxonomy(d: Optional[Dict[str, Any]]) -> Taxonomy:
    if not d:
        return Taxonomy()
    return Taxonomy(
        vertical=str(d.get("vertical", "mixed")),
        subvertical=d.get("subvertical"),
        vertical_confidence=str(d.get("vertical_confidence", "MEDIUM")),
        subvertical_confidence=str(d.get("subvertical_confidence", "REFUSED")),
        detection_method=str(d.get("detection_method", "env_var_override")),
        operator_override_used=bool(d.get("operator_override_used", True)),
        detected_vertical=d.get("detected_vertical"),
        override_disagrees=bool(d.get("override_disagrees", False)),
    )


def _from_dict_business_stage(d: Optional[Dict[str, Any]]) -> BusinessStage:
    if not d:
        return BusinessStage()
    return BusinessStage(
        stage=str(d.get("stage", "STARTUP")),
        annualized_gmv_usd=float(d.get("annualized_gmv_usd", 0.0) or 0.0),
        detection_method=str(d.get("detection_method", "insufficient_history")),
        operator_override_used=bool(d.get("operator_override_used", False)),
        uncertainty=str(d.get("uncertainty", "LOW")),
        conservative_floor_applied=bool(d.get("conservative_floor_applied", False)),
        detected_stage=d.get("detected_stage"),
    )


def _from_dict_business_model(d: Optional[Dict[str, Any]]) -> BusinessModel:
    if not d:
        return BusinessModel()
    return BusinessModel(
        model=str(d.get("model", "ONE_TIME_LED")),
        subscription_fraction=float(d.get("subscription_fraction", 0.0) or 0.0),
        detection_confidence=str(d.get("detection_confidence", "LOW")),
    )


def _from_dict_data_depth(d: Optional[Dict[str, Any]]) -> DataDepth:
    if not d:
        return DataDepth()
    return DataDepth(
        history_days=int(d.get("history_days", 0) or 0),
        n_customers=int(d.get("n_customers", 0) or 0),
        n_orders=int(d.get("n_orders", 0) or 0),
        n_repeat_customers=int(d.get("n_repeat_customers", 0) or 0),
        n_subscription_orders=int(d.get("n_subscription_orders", 0) or 0),
    )


def _from_dict_cadence(d: Optional[Dict[str, Any]]) -> CadenceBaseline:
    if not d:
        return CadenceBaseline()
    raw = d.get("median_reorder_days_by_sku_class") or {}
    parsed: Dict[str, int] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                parsed[str(k)] = int(v)
            except (TypeError, ValueError):
                continue
    raw_method = d.get("method_by_sku_class") or {}
    parsed_method: Dict[str, str] = {}
    if isinstance(raw_method, dict):
        for k, v in raw_method.items():
            parsed_method[str(k)] = str(v)
    gmrd = d.get("global_median_reorder_days")
    try:
        gmrd_int = int(gmrd) if gmrd is not None else None
    except (TypeError, ValueError):
        gmrd_int = None
    return CadenceBaseline(
        median_reorder_days_by_sku_class=parsed,
        method_by_sku_class=parsed_method,
        global_median_reorder_days=gmrd_int,
        detection_status=str(d.get("detection_status", "DEFERRED_TO_T3")),
    )


def _from_dict_seasonality(d: Optional[Dict[str, Any]]) -> SeasonalityContext:
    if not d:
        return SeasonalityContext()
    raw_range = d.get("expected_lift_range")
    parsed_range: Optional[List[float]] = None
    if isinstance(raw_range, (list, tuple)) and len(raw_range) == 2:
        try:
            parsed_range = [float(raw_range[0]), float(raw_range[1])]
        except (TypeError, ValueError):
            parsed_range = None
    return SeasonalityContext(
        active_window_name=d.get("active_window_name"),
        expected_lift_direction=d.get("expected_lift_direction"),
        expected_lift_range=parsed_range,
        source_artifact=d.get("source_artifact"),
        detection_status=str(d.get("detection_status", "DEFERRED_TO_T3")),
    )


def _from_dict_gate_calibration(d: Optional[Dict[str, Any]]) -> GateCalibration:
    if not d:
        return GateCalibration()
    raw = d.get("audience_floor_by_play_id") or {}
    parsed: Dict[str, int] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                parsed[str(k)] = int(v)
            except (TypeError, ValueError):
                continue
    floor = d.get("materiality_floor_usd")
    try:
        floor_f = float(floor) if floor is not None else None
    except (TypeError, ValueError):
        floor_f = None
    pn = d.get("pseudo_n_default")
    try:
        pn_i = int(pn) if pn is not None else None
    except (TypeError, ValueError):
        pn_i = None
    rsku = d.get("replenishment_due_per_sku_floor")
    try:
        rsku_i = int(rsku) if rsku is not None else None
    except (TypeError, ValueError):
        rsku_i = None
    raw_refs = d.get("profile_field_refs") or {}
    parsed_refs: Dict[str, str] = {}
    if isinstance(raw_refs, dict):
        for k, v in raw_refs.items():
            parsed_refs[str(k)] = str(v)
    return GateCalibration(
        audience_floor_by_play_id=parsed,
        materiality_floor_usd=floor_f,
        pseudo_n_default=pn_i,
        replenishment_due_per_sku_floor=rsku_i,
        profile_field_refs=parsed_refs,
        detection_status=str(d.get("detection_status", "DEFERRED_TO_T4")),
    )


def _from_dict_measurement(d: Optional[Dict[str, Any]]) -> MeasurementContext:
    if not d:
        return MeasurementContext()
    raw_windows = d.get("agreement_windows")
    if isinstance(raw_windows, list):
        windows = [str(w) for w in raw_windows if isinstance(w, str)]
    else:
        windows = ["L56", "L90"]
    return MeasurementContext(
        primary_window=str(d.get("primary_window", "L28")),
        agreement_windows=windows,
        primary_window_source=str(d.get("primary_window_source", "default")),
        detection_status=str(d.get("detection_status", "DEFERRED_TO_T4")),
    )


def _from_dict_provenance(d: Optional[Dict[str, Any]]) -> ProfileProvenance:
    if not d:
        return ProfileProvenance()
    raw_rules = d.get("rules_fired") or []
    rules: List[Dict[str, Any]] = []
    if isinstance(raw_rules, list):
        for r in raw_rules:
            if isinstance(r, dict):
                rules.append(dict(r))
    return ProfileProvenance(
        profile_version=int(d.get("profile_version", 1) or 1),
        profiled_at=str(d.get("profiled_at", "")),
        rules_fired=rules,
    )


def store_profile_from_dict(d: Optional[Dict[str, Any]]) -> Optional[StoreProfile]:
    """Inverse of ``EngineRun.to_dict()['store_profile']``.

    Returns ``None`` for a missing / null payload so pre-S6.5 fixtures
    round-trip with ``store_profile=None``.
    """

    if d is None:
        return None
    return StoreProfile(
        store_id=str(d.get("store_id", "")),
        taxonomy=_from_dict_taxonomy(d.get("taxonomy")),
        business_stage=_from_dict_business_stage(d.get("business_stage")),
        business_model=_from_dict_business_model(d.get("business_model")),
        cadence=_from_dict_cadence(d.get("cadence")),
        seasonality=_from_dict_seasonality(d.get("seasonality")),
        data_depth=_from_dict_data_depth(d.get("data_depth")),
        gate_calibration=_from_dict_gate_calibration(d.get("gate_calibration")),
        measurement=_from_dict_measurement(d.get("measurement")),
        provenance=_from_dict_provenance(d.get("provenance")),
    )
