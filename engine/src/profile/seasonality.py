"""Active seasonality calendar lookup (Sprint 6.5 Ticket T3).

Reads ``config/seasonality_calendars.yaml`` and returns the active
window (if any) for a given (run_date, vertical, subvertical).

CRITICAL — Part III §8 discipline: ``expected_lift_range`` is an
OBSERVATIONAL ANNOTATION ONLY. It is NEVER multiplied into a revenue
estimate, never used to adjust a p-value, never used as a slate-ordering
multiplier. Consumers may surface the range to merchants as context;
they may NOT consume it as a numerical scalar.

Founder Q3 (2026-05-17): the 5 named windows in the YAML are accepted
verbatim. Every cell is tagged ``validation_status:
heuristic_unvalidated``.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .types import SeasonalityContext


_SEASONALITY_YAML_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "config"
    / "seasonality_calendars.yaml"
)
_SEASONALITY_CACHE: Optional[Dict[str, Any]] = None


def load_seasonality_calendars(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load ``config/seasonality_calendars.yaml`` once and cache it.

    Pass an explicit ``path`` to bypass the cache (used by tests).
    """

    global _SEASONALITY_CACHE
    if path is None:
        if _SEASONALITY_CACHE is not None:
            return _SEASONALITY_CACHE
        target = _SEASONALITY_YAML_PATH
    else:
        target = Path(path)

    if not target.exists():
        data: Dict[str, Any] = {"windows": []}
    else:
        with open(target, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    if path is None:
        _SEASONALITY_CACHE = data
    return data


def _coerce_date(run_date: Any) -> date:
    if isinstance(run_date, date) and not isinstance(run_date, datetime):
        return run_date
    if isinstance(run_date, datetime):
        return run_date.date()
    if isinstance(run_date, str):
        return datetime.strptime(run_date[:10], "%Y-%m-%d").date()
    raise TypeError(f"Unsupported run_date type: {type(run_date)!r}")


def _md_in_window(run_md: Tuple[int, int], start_md: str, end_md: str) -> bool:
    """Return True if ``run_md`` (month, day) is inside ``[start_md, end_md]``
    (MM-DD inclusive). Handles wrap-around (e.g. 12-15 → 01-15)."""

    smm, sdd = (int(p) for p in start_md.split("-"))
    emm, edd = (int(p) for p in end_md.split("-"))
    start_key = (smm, sdd)
    end_key = (emm, edd)
    if start_key <= end_key:
        return start_key <= run_md <= end_key
    # Wrap-around (e.g. 12-15 → 01-15): inside if run is >= start OR <= end.
    return run_md >= start_key or run_md <= end_key


def _window_applies(
    window: Dict[str, Any], vertical: str, subvertical: Optional[str]
) -> bool:
    applies = window.get("applies_to") or []
    for entry in applies:
        if not isinstance(entry, dict):
            continue
        v = entry.get("vertical")
        s = entry.get("subvertical")
        if v != vertical:
            continue
        # ``subvertical: null`` in YAML => matches any subvertical of this vertical.
        if s is None:
            return True
        if s == subvertical:
            return True
    return False


def lookup_active_seasonality(
    run_date: Any,
    vertical: Optional[str],
    subvertical: Optional[str],
    calendars: Optional[Dict[str, Any]] = None,
) -> SeasonalityContext:
    """Return the active seasonality window for ``(run_date, vertical,
    subvertical)`` (or an inactive context if no window matches).

    The result is descriptive — the returned ``expected_lift_range`` is
    annotation only and must never be consumed as a revenue or
    significance multiplier (Part III §8).
    """

    if not vertical or vertical in ("mixed", "other_refused"):
        return SeasonalityContext(detection_status="NOT_APPLICABLE")

    try:
        rd = _coerce_date(run_date)
    except (TypeError, ValueError):
        return SeasonalityContext(detection_status="INVALID_RUN_DATE")

    cfg = calendars if calendars is not None else load_seasonality_calendars()
    windows: List[Dict[str, Any]] = (cfg or {}).get("windows") or []

    run_md = (rd.month, rd.day)
    for window in windows:
        if not isinstance(window, dict):
            continue
        # Optional valid_for_year guard.
        vfy = window.get("valid_for_year")
        if vfy is not None and int(vfy) != rd.year:
            continue
        start_md = window.get("start_md")
        end_md = window.get("end_md")
        if not (isinstance(start_md, str) and isinstance(end_md, str)):
            continue
        if not _md_in_window(run_md, start_md, end_md):
            continue
        if not _window_applies(window, vertical, subvertical):
            continue

        raw_range = window.get("expected_lift_range")
        lift_range: Optional[List[float]] = None
        if isinstance(raw_range, (list, tuple)) and len(raw_range) == 2:
            try:
                lift_range = [float(raw_range[0]), float(raw_range[1])]
            except (TypeError, ValueError):
                lift_range = None
        return SeasonalityContext(
            active_window_name=str(window.get("name")),
            expected_lift_direction=window.get("expected_lift_direction"),
            expected_lift_range=lift_range,
            source_artifact=window.get("source_artifact"),
            detection_status="ACTIVE",
        )

    return SeasonalityContext(detection_status="NO_ACTIVE_WINDOW")
