"""Sprint 13 Ticket T3 — month_2_delta detection (Pivot 8 month-2-return).

Substrate-state-delta computation between the current ``EngineRun`` and
a prior month-1 ``EngineRun`` loaded via an injected loader. Lives
behind ``ENGINE_V2_MONTH_2_DELTA`` (default OFF at T3; T3.5 owns the
atomic flip). The orchestration callsite is at ``src/main.py`` AFTER
the T2 consumer-wiring pass — NOT a new injection block at the
forbidden ``src/main.py:1380-1597`` zone.

Design choices (DS S13 plan review):

- **21-day floor (DS §D.2 LOCKED).** Lineage-keyed, NOT calendar-gated:
  the floor applies to the temporal distance between the prior run and
  the current run, not to wall-clock month boundaries.
- **Lineage constraint (DS §D.2 LOCKED).** When the audience-definition
  version bumps between runs (D-1), ``segment_shifts`` MUST be ``None``
  and ``notes`` MUST carry the typed string
  ``"lineage_changed_segment_shift_incomparable"``. Substrate fit-status
  changes and retention CI delta remain comparable.
- **Substrate-state-delta, NOT realized-outcome delta (DS §G.2).** The
  month-2-return wow story for cold-start merchants flows through the
  EB path (``n_observed`` shift in ``bayesian_blend``), NOT through ML.
  ML refusal degrades silently within audience ranking.
- **Pure detector + injected loader.** The detector takes a callable
  ``prior_engine_run_loader(store_id) -> Optional[dict]`` so the SQLite
  read path stays out of this module (testability + isolation). The
  concrete loader is supplied at the orchestration callsite.

Schema-additive within ``event_version=1``. No new ReasonCodes. No
mutation of any field other than ``EngineRun.month_2_delta``. Pivot 7
single-demote-channel invariant preserved structurally — this module
does NOT append to ``recommendations`` or ``considered``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

from ..engine_run import EngineRun, MonthDelta, MonthDeltaNullReason


# DS §D.2 LOCKED: lineage-keyed 21-day floor for month-2 detection.
MONTH_2_DAY_FLOOR: int = 21

# DS §D.2 LOCKED: typed note value when the D-1 lineage key bumps
# between prior and current run. ``segment_shifts`` is suppressed to
# ``None``; substrate fit-status changes and retention CI delta remain
# comparable across lineage bumps.
LINEAGE_CHANGED_NOTE: str = "lineage_changed_segment_shift_incomparable"

# Substrates we surface in ``substrate_fit_status_changes``. Order is
# preserved in the dict for operator-readability.
_SUBSTRATES_PER_CUSTOMER: Tuple[str, ...] = (
    "bgnbd",
    "gamma_gamma",
    "survival",
    "cf",
    "rfm",
)
_SUBSTRATES_COHORT: Tuple[str, ...] = ("retention",)


# Type aliases for clarity.
PriorEngineRunLoader = Callable[[str], Optional[Dict[str, Any]]]


def _extract_fit_status(substrate_blob: Any) -> Optional[str]:
    """Pull ``fit_status`` off a substrate dict or dataclass-like obj.

    Tolerates the multiple shapes ``EngineRun.predictive_models[*]`` /
    ``EngineRun.cohort_diagnostics[*]`` can carry across substrates
    (ModelCard, RetentionCard, plain dict from a re-hydrated JSON). The
    canonical key is ``fit_status``; falls back to ``status`` for
    defensive symmetry.
    """

    if substrate_blob is None:
        return None
    if isinstance(substrate_blob, dict):
        val = substrate_blob.get("fit_status")
        if val is None:
            val = substrate_blob.get("status")
        return None if val is None else str(val)
    # Dataclass-like — try getattr.
    val = getattr(substrate_blob, "fit_status", None)
    if val is None:
        val = getattr(substrate_blob, "status", None)
    if val is None:
        return None
    # Enums expose ``.value``; fall back to ``str()``.
    return str(getattr(val, "value", val))


def _extract_audience_definition_version(run_blob: Any) -> Optional[int]:
    """Extract the D-1 audience_definition_version from an EngineRun.

    Production EngineRun does not surface this as a top-level field
    (it's per-PlayCard via the lineage helper). For month-2-delta
    purposes we read the value via three accepted shapes (in priority
    order):

    1. ``run_blob["audience_definition_version"]`` — explicit top-level
       set by the loader (preferred shape; the loader knows the run's
       version from the substrate event payload).
    2. ``run_blob["briefing_meta"]["audience_definition_version"]`` —
       defensive fallback for callers that stash it there.
    3. First PlayCard's audience-definition lineage — last-resort.

    Returns ``None`` if no version can be read; treated as
    "lineage unknown → conservatively suppress segment_shifts" by the
    detector.
    """

    if run_blob is None:
        return None
    if isinstance(run_blob, dict):
        v = run_blob.get("audience_definition_version")
        if isinstance(v, int) and not isinstance(v, bool) and v >= 1:
            return v
        meta = run_blob.get("briefing_meta") or {}
        if isinstance(meta, dict):
            v = meta.get("audience_definition_version")
            if isinstance(v, int) and not isinstance(v, bool) and v >= 1:
                return v
        return None
    # Dataclass.
    v = getattr(run_blob, "audience_definition_version", None)
    if isinstance(v, int) and not isinstance(v, bool) and v >= 1:
        return v
    meta = getattr(run_blob, "briefing_meta", None)
    if meta is not None:
        v = getattr(meta, "audience_definition_version", None)
        if isinstance(v, int) and not isinstance(v, bool) and v >= 1:
            return v
    return None


def _parse_iso_to_epoch_days(value: Any) -> Optional[float]:
    """Parse an ISO-8601 anchor_date or run timestamp to epoch days.

    Returns ``None`` on parse failure. We use day-precision because the
    DS-locked floor is 21 days; sub-day precision is not contractually
    meaningful.
    """

    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Already epoch seconds.
        return float(value) / 86400.0
    s = str(value).strip()
    if not s:
        return None
    # Accept ``YYYY-MM-DD`` or full ISO. ``datetime.fromisoformat`` does
    # both since Python 3.11; for 3.10 compatibility we strip a trailing
    # ``Z`` and try ``fromisoformat`` first then fall back.
    from datetime import datetime, timezone

    candidate = s.rstrip("Z").replace("Z", "")
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError:
        try:
            dt = datetime.strptime(candidate[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    epoch = dt.timestamp()
    return epoch / 86400.0


def _days_between(prior_blob: Any, current: EngineRun) -> Optional[int]:
    """Days between prior run and current run via ``anchor_date``.

    Returns ``None`` if either side lacks a parseable anchor.
    """

    if isinstance(prior_blob, dict):
        prior_anchor = prior_blob.get("anchor_date")
    else:
        prior_anchor = getattr(prior_blob, "anchor_date", None)
    current_anchor = getattr(current, "anchor_date", None)
    p_days = _parse_iso_to_epoch_days(prior_anchor)
    c_days = _parse_iso_to_epoch_days(current_anchor)
    if p_days is None or c_days is None:
        return None
    return int(round(c_days - p_days))


def _diff_substrate_fits(
    prior_blob: Any, current: EngineRun
) -> Dict[str, Tuple[str, str]]:
    """Compute ``{substrate: (prior_status, current_status)}`` map.

    Substrates not present on EITHER side are skipped. Substrates
    present on one side only surface with ``"ABSENT"`` for the missing
    side — operator-readable, no silent swallow.
    """

    out: Dict[str, Tuple[str, str]] = {}

    if isinstance(prior_blob, dict):
        prior_models = prior_blob.get("predictive_models") or {}
        prior_diag = prior_blob.get("cohort_diagnostics") or {}
    else:
        prior_models = getattr(prior_blob, "predictive_models", {}) or {}
        prior_diag = getattr(prior_blob, "cohort_diagnostics", {}) or {}

    current_models = current.predictive_models or {}
    current_diag = current.cohort_diagnostics or {}

    for substrate in _SUBSTRATES_PER_CUSTOMER:
        p = _extract_fit_status(prior_models.get(substrate)) if isinstance(prior_models, dict) else None
        c = _extract_fit_status(current_models.get(substrate)) if isinstance(current_models, dict) else None
        if p is None and c is None:
            continue
        out[substrate] = (p or "ABSENT", c or "ABSENT")

    for substrate in _SUBSTRATES_COHORT:
        p = _extract_fit_status(prior_diag.get(substrate)) if isinstance(prior_diag, dict) else None
        c = _extract_fit_status(current_diag.get(substrate)) if isinstance(current_diag, dict) else None
        if p is None and c is None:
            continue
        out[substrate] = (p or "ABSENT", c or "ABSENT")

    return out


def _retention_ci_width(diag_blob: Any) -> Optional[float]:
    """Extract month-3 retention CI WIDTH from a retention substrate blob.

    Returns ``None`` if the substrate is absent, REFUSED, or the
    month-3 CI is not present in the expected shape. The canonical
    shape is one of:

    - ``{"bootstrap_ci_width_at_month_3": float}``
    - ``{"ci_at_month_3": [lo, hi]}`` (width = hi - lo)
    - ``{"retention_curve": {"month_3": {"ci": [lo, hi]}}}``

    We probe in priority order; the first found wins.
    """

    if diag_blob is None:
        return None
    if not isinstance(diag_blob, dict):
        # Best-effort: dataclass-like.
        return _retention_ci_width(getattr(diag_blob, "__dict__", None))
    retention = diag_blob.get("retention")
    if retention is None:
        # The diagnostic map IS the retention substrate.
        retention = diag_blob
    if not isinstance(retention, dict):
        return None
    val = retention.get("bootstrap_ci_width_at_month_3")
    if val is not None:
        try:
            return float(val)
        except (TypeError, ValueError):
            pass
    ci = retention.get("ci_at_month_3")
    if isinstance(ci, (list, tuple)) and len(ci) == 2:
        try:
            return float(ci[1]) - float(ci[0])
        except (TypeError, ValueError):
            pass
    curve = retention.get("retention_curve") or {}
    if isinstance(curve, dict):
        m3 = curve.get("month_3") or {}
        if isinstance(m3, dict):
            sub_ci = m3.get("ci")
            if isinstance(sub_ci, (list, tuple)) and len(sub_ci) == 2:
                try:
                    return float(sub_ci[1]) - float(sub_ci[0])
                except (TypeError, ValueError):
                    pass
    return None


def _retention_ci_delta(prior_blob: Any, current: EngineRun) -> Optional[float]:
    """Signed delta ``current_ci_width - prior_ci_width`` for retention."""

    if isinstance(prior_blob, dict):
        prior_diag = prior_blob.get("cohort_diagnostics") or {}
    else:
        prior_diag = getattr(prior_blob, "cohort_diagnostics", {}) or {}
    p_width = _retention_ci_width(prior_diag)
    c_width = _retention_ci_width(current.cohort_diagnostics or {})
    if p_width is None or c_width is None:
        return None
    return float(c_width - p_width)


def _compute_segment_shifts(
    prior_blob: Any, current: EngineRun
) -> Optional[Dict[str, Dict[str, str]]]:
    """Compute per-customer RFM segment shifts.

    Reads the prior + current RFM segment maps from the substrate
    blob's ``segment_by_customer`` (DS-canonical shape:
    ``{customer_id: segment_name}``). When either side lacks a usable
    map, returns ``{}`` (no shifts) — NOT ``None``. ``None`` is reserved
    for the lineage-changed suppression case and is set by the caller.
    """

    if isinstance(prior_blob, dict):
        prior_models = prior_blob.get("predictive_models") or {}
    else:
        prior_models = getattr(prior_blob, "predictive_models", {}) or {}
    prior_rfm = prior_models.get("rfm") if isinstance(prior_models, dict) else None
    current_rfm = (current.predictive_models or {}).get("rfm")

    def _segment_map(blob: Any) -> Dict[str, str]:
        if blob is None:
            return {}
        if isinstance(blob, dict):
            sbc = blob.get("segment_by_customer")
        else:
            sbc = getattr(blob, "segment_by_customer", None)
        if not isinstance(sbc, dict):
            return {}
        return {str(k): str(v) for k, v in sbc.items() if v is not None}

    prior_map = _segment_map(prior_rfm)
    current_map = _segment_map(current_rfm)
    if not prior_map and not current_map:
        return {}

    shifts: Dict[str, Dict[str, str]] = {}
    for cust_id in set(prior_map) & set(current_map):
        p = prior_map[cust_id]
        c = current_map[cust_id]
        if p != c:
            shifts[cust_id] = {"prior": p, "current": c}
    return shifts


def detect_month_2_delta(
    current_engine_run: EngineRun,
    store_id: str,
    prior_engine_run_loader: PriorEngineRunLoader,
) -> Tuple[Optional[MonthDelta], Optional[MonthDeltaNullReason]]:
    """Compute the Pivot 8 month-2 substrate-state-delta.

    Returns a 2-tuple ``(value, null_reason)``:

    - ``(None, MonthDeltaNullReason.NO_STORE_ID)`` if no ``store_id``.
    - ``(None, MonthDeltaNullReason.NO_PRIOR_RUN)`` if the loader returns
      no prior run (merchant's first month — nothing to compare).
    - ``(None, MonthDeltaNullReason.ANCHOR_DATE_UNPARSEABLE)`` if either
      side's anchor_date fails to parse (defensive).
    - ``(None, MonthDeltaNullReason.UNDER_21D_FLOOR)`` if the 21-day
      floor (DS §D.2 LOCKED) is not yet cleared.
    - ``(MonthDelta(...), None)`` on success.

    S13.6-T7a (DS adjudication 2026-06-01 + founder approved
    2026-06-01): tuple-return enforces always-paired
    (value, null_reason) emission at the seam per the revised flag-
    aware RULE A. The caller in ``src/main.py`` assigns both fields to
    ``engine_run.month_2_delta`` and ``engine_run.month_2_delta_null_reason``
    atomically.

    The lineage constraint (DS §D.2) suppresses ``segment_shifts`` to
    ``None`` and appends the typed note
    ``"lineage_changed_segment_shift_incomparable"`` when the audience-
    definition version bumps; substrate fit-status changes and retention
    CI delta remain comparable. ``MonthDeltaNullReason.LINEAGE_CHANGED``
    is reserved as forward-compat (a future ticket may promote lineage-
    bump to whole-MonthDelta suppression; today the inner
    ``segment_shifts`` carries the lineage signal).

    Pure function modulo the injected loader. Does NOT mutate
    ``current_engine_run``.
    """

    if not store_id:
        return None, MonthDeltaNullReason.NO_STORE_ID
    prior_blob = prior_engine_run_loader(store_id)
    if prior_blob is None:
        return None, MonthDeltaNullReason.NO_PRIOR_RUN

    days_between = _days_between(prior_blob, current_engine_run)
    if days_between is None:
        return None, MonthDeltaNullReason.ANCHOR_DATE_UNPARSEABLE
    if days_between < MONTH_2_DAY_FLOOR:
        return None, MonthDeltaNullReason.UNDER_21D_FLOOR

    substrate_changes = _diff_substrate_fits(prior_blob, current_engine_run)
    retention_delta = _retention_ci_delta(prior_blob, current_engine_run)

    prior_adv = _extract_audience_definition_version(prior_blob)
    current_adv = _extract_audience_definition_version(current_engine_run)

    notes: list = []
    segment_shifts: Optional[Dict[str, Dict[str, str]]]
    if (
        prior_adv is not None
        and current_adv is not None
        and prior_adv != current_adv
    ):
        # DS §D.2 LOCKED: lineage bump → segment_shifts is incomparable.
        segment_shifts = None
        notes.append(LINEAGE_CHANGED_NOTE)
    else:
        segment_shifts = _compute_segment_shifts(prior_blob, current_engine_run)

    prior_run_id = (
        prior_blob.get("run_id") if isinstance(prior_blob, dict) else getattr(prior_blob, "run_id", "")
    ) or ""
    current_run_id = getattr(current_engine_run, "run_id", "") or ""

    return (
        MonthDelta(
            prior_run_id=str(prior_run_id),
            current_run_id=str(current_run_id),
            days_between=int(days_between),
            substrate_fit_status_changes=substrate_changes,
            segment_shifts=segment_shifts,
            retention_ci_at_month_3_delta=retention_delta,
            notes=notes,
        ),
        None,
    )


__all__ = [
    "MONTH_2_DAY_FLOOR",
    "LINEAGE_CHANGED_NOTE",
    "PriorEngineRunLoader",
    "detect_month_2_delta",
]
