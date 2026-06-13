"""Outcome logging — Milestone 9, T9.1.

Append one record per engine run to a local JSON history file so that a
future calibration / realized-vs-predicted layer (M9 T9.4 stub, Phase 2+
implementation) has structured data to learn from. **No ML happens here.**
This module only writes the record.

Design intent (per implementation-manager-overhaul-plan-final.md M9):

- Pure function ``write_recommended_history(engine_run, history_path)``;
  no I/O outside the supplied path.
- The history file is a JSON list of records. New runs append. If the
  file does not exist it is created. If the file exists but is malformed
  (truncated JSON, hand-edited, etc.), the run does NOT crash; we move
  the broken file aside as ``<path>.corrupt-<timestamp>.bak`` and start a
  fresh list. The caller is given a structured warning code via the
  return value; the rest of the engine continues normally.
- Records do NOT contain raw customer PII. We persist the
  ``audience.id`` and ``audience.size`` only. We do NOT persist the
  audience customer IDs themselves (those live in ``segments/`` zips
  by-design, not in a long-lived history file).
- Records DO contain the internal evidence-class diagnostics
  (``measurement.p_internal``, ``measurement.ci_internal``, observed
  effect, n) so a future calibration agent can compare what we said vs
  what happened. These fields are merchant-invisible by contract.
- Records DO contain the rejected-play list so a future fatigue /
  diversity layer has the full per-run footprint, not just the
  recommended set.
- Schema is versioned (``schema_version="1.0.0"``) so a future migration
  can detect old records and adapt rather than refuse to read them.

Hard NOT-IN-SCOPE (do NOT do here):

- Do NOT write raw customer IDs.
- Do NOT write order-line PII.
- Do NOT call any network resource.
- Do NOT introduce uplift / lift / treatment-effect terminology.
- Do NOT mutate the EngineRun.
- Do NOT block the merchant briefing on a write failure: every error is
  swallowed and reported through the return-status dict.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .engine_run import EngineRun


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"


# Status codes returned by ``write_recommended_history``. Documented so the
# caller (``main.py``) can log a structured warning rather than guessing.
STATUS_OK = "ok"
STATUS_DISABLED = "disabled"
STATUS_NO_ENGINE_RUN = "no_engine_run"
STATUS_RECOVERED_FROM_CORRUPT = "recovered_from_corrupt"
STATUS_WRITE_ERROR = "write_error"


# ---------------------------------------------------------------------------
# Privacy-safe extractors
# ---------------------------------------------------------------------------


def _audience_summary(audience) -> Optional[Dict[str, Any]]:
    """Persist only audience metadata, never raw customer IDs."""
    if audience is None:
        return None
    out: Dict[str, Any] = {}
    if audience.id is not None:
        out["id"] = str(audience.id)
    if audience.size is not None:
        try:
            out["size"] = int(audience.size)
        except (TypeError, ValueError):
            pass
    if audience.fraction_of_base is not None:
        try:
            out["fraction_of_base"] = float(audience.fraction_of_base)
        except (TypeError, ValueError):
            pass
    if audience.overlap_with:
        out["overlap_with"] = [str(x) for x in audience.overlap_with]
    return out or None


def _measurement_summary(measurement) -> Optional[Dict[str, Any]]:
    """Carry internal evidence diagnostics. Merchant-invisible by contract."""
    if measurement is None:
        return None
    out: Dict[str, Any] = {}
    for k in (
        "metric",
        "observed_effect",
        "n",
        "primary_window",
        "consistency_across_windows",
        "p_internal",
    ):
        v = getattr(measurement, k, None)
        if v is not None:
            out[k] = v
    if measurement.ci_internal is not None:
        try:
            out["ci_internal"] = [float(x) for x in measurement.ci_internal]
        except (TypeError, ValueError):
            pass
    return out or None


def _revenue_range_summary(revenue_range) -> Optional[Dict[str, Any]]:
    """Persist range provenance for future calibration but not merchant copy."""
    if revenue_range is None:
        return None
    src = revenue_range.source
    return {
        "p10": revenue_range.p10,
        "p50": revenue_range.p50,
        "p90": revenue_range.p90,
        "source": src.value if hasattr(src, "value") and src is not None else src,
        "suppressed": bool(revenue_range.suppressed),
        # Drivers are name+source dicts already; safe to copy through.
        "drivers": [dict(d) for d in (revenue_range.drivers or [])],
    }


def _play_card_summary(card) -> Dict[str, Any]:
    ec = getattr(card.evidence_class, "value", card.evidence_class)
    return {
        "play_id": card.play_id,
        "evidence_class": str(ec) if ec is not None else None,
        "confidence_label": card.confidence_label,
        "audience": _audience_summary(card.audience),
        "measurement": _measurement_summary(card.measurement),
        "revenue_range": _revenue_range_summary(card.revenue_range),
    }


def _synthesize_reason_text(reason_code, held_reason_detail) -> Optional[str]:
    """S13.6-T1a (Option D): synthesize a textual ``reason_text`` locally
    from the typed ``reason_code`` enum + structured ``held_reason_detail``
    dict at outcome-log write time.

    ``RejectedPlay.reason_text`` was stripped from the engine contract
    surface per Pivot 2 (engine emits typed surface only). The outcome
    log's JSON schema must stay stable (D-2 forever-retention of
    already-written records), so we compose a short text rendering here
    rather than dropping the field. Pure function; no I/O.

    Synthesis grammar: ``"{REASON_CODE}: {k1=v1, k2=v2, ...}"`` when a
    detail dict is present; plain ``"{REASON_CODE}"`` otherwise. Returns
    ``None`` when ``reason_code`` is itself ``None`` (defensive — should
    not happen on a well-formed RejectedPlay).
    """
    if reason_code is None:
        return None
    rc = getattr(reason_code, "value", reason_code)
    rc_str = str(rc) if rc is not None else "UNKNOWN"
    if isinstance(held_reason_detail, dict) and held_reason_detail:
        # Stable key order for deterministic JSON serialization.
        kv = ", ".join(
            f"{k}={held_reason_detail[k]}"
            for k in sorted(held_reason_detail.keys())
        )
        return f"{rc_str}: {kv}"
    return rc_str


def _rejected_summary(rejected) -> Dict[str, Any]:
    rc = getattr(rejected.reason_code, "value", rejected.reason_code)
    # S13.6-T1a (Option D): ``RejectedPlay.reason_text`` stripped from
    # engine contract surface. Synthesize locally from ``reason_code`` +
    # ``held_reason_detail`` so the outcome-log JSON schema stays stable.
    held_detail = getattr(rejected, "held_reason_detail", None)
    return {
        "play_id": rejected.play_id,
        "reason_code": str(rc) if rc is not None else None,
        "reason_text": _synthesize_reason_text(rejected.reason_code, held_detail),
    }


def build_record(engine_run: EngineRun) -> Dict[str, Any]:
    """Build the per-run history record. Pure; no I/O.

    The shape is intentionally minimal: store/run identity, decision state,
    plays recommended (with internal evidence diagnostics), plays
    rejected (reason-coded), and aggregate revenue / evidence metadata.
    """
    abstain = engine_run.abstain
    abstain_state = (
        abstain.state.value if (abstain is not None and abstain.state is not None) else None
    )
    # S13.6-T1a (Option D): ``Abstain.reason`` stripped per Pivot 2. The
    # outcome-log JSON ``abstain_reason`` field stays in the schema for
    # D-2 forever-retention compatibility, but is now always ``None``.
    abstain_reason = None

    flags = [
        f.value if hasattr(f, "value") else str(f)
        for f in (engine_run.data_quality_flags or [])
    ]

    scale = engine_run.scale
    scale_summary: Dict[str, Any] = {}
    if scale is not None:
        if scale.monthly_revenue is not None:
            scale_summary["monthly_revenue"] = scale.monthly_revenue
        if scale.customer_base_est is not None:
            scale_summary["customer_base_est"] = scale.customer_base_est
        if scale.materiality_floor is not None:
            scale_summary["materiality_floor"] = scale.materiality_floor

    recs = [_play_card_summary(c) for c in (engine_run.recommendations or [])]
    rejected = [_rejected_summary(r) for r in (engine_run.considered or [])]

    # Aggregate p50 across recommendations for a quick "what we sized" line.
    sum_p50: Optional[float] = None
    try:
        vals = [
            float(c.revenue_range.p50)
            for c in (engine_run.recommendations or [])
            if (
                c.revenue_range is not None
                and c.revenue_range.p50 is not None
                and not c.revenue_range.suppressed
            )
        ]
        if vals:
            sum_p50 = round(sum(vals), 2)
    except (TypeError, ValueError):
        sum_p50 = None

    return {
        "schema_version": SCHEMA_VERSION,
        "ts": datetime.now(timezone.utc).isoformat(),
        "store_id": engine_run.store_id,
        "run_id": engine_run.run_id,
        "anchor_date": engine_run.anchor_date,
        "decision_state": abstain_state,
        "abstain_reason": abstain_reason,
        "data_quality_flags": flags,
        "cold_start": bool(engine_run.cold_start),
        "scale": scale_summary or None,
        "recommended": recs,
        "rejected": rejected,
        "summary": {
            "n_recommended": len(recs),
            "n_rejected": len(rejected),
            "sum_recommended_p50": sum_p50,
        },
    }


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def _read_existing(path: Path) -> Tuple[List[Dict[str, Any]], bool]:
    """Read the existing history list. Returns (records, was_corrupt).

    Missing file -> returns ([], False).
    Empty file -> returns ([], False) (treat as fresh).
    Malformed file -> returns ([], True). The corrupt file is moved aside
    by the caller so the next run does not keep tripping on it.
    """
    if not path.exists():
        return [], False
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return [], True
    if not raw.strip():
        return [], False
    try:
        loaded = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return [], True
    if not isinstance(loaded, list):
        # Malformed at the structural level (someone wrote a dict).
        return [], True
    cleaned = [r for r in loaded if isinstance(r, dict)]
    return cleaned, False


def _move_corrupt_aside(path: Path) -> Optional[Path]:
    """Rename a malformed history file out of the way.

    Returns the new path or ``None`` on failure. Failure is non-fatal —
    we still continue with a fresh list.
    """
    try:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_suffix(path.suffix + f".corrupt-{ts}.bak")
        shutil.move(str(path), str(backup))
        return backup
    except OSError:
        return None


def _flag_on(value: Any) -> bool:
    """Coerce a config flag to bool. Accept bool or string."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def write_recommended_history(
    engine_run: Optional[EngineRun],
    history_path: str | Path,
    *,
    enabled: bool = True,
) -> Dict[str, Any]:
    """Append a per-run record to the history file at ``history_path``.

    Args:
        engine_run: the typed EngineRun to log. ``None`` is a no-op.
        history_path: absolute or relative path. Parent dir is created
            if missing. The file itself is created if missing.
        enabled: when False, the function is a no-op (returns
            ``{"status": disabled}``). Lets the caller tie the write to
            ``OUTCOME_LOG_ENABLED`` without thinking about it.

    Returns:
        A status dict. Keys:
            ``status``: one of the STATUS_* constants above.
            ``path``: resolved string path.
            ``records_after``: int count after the write (0 on no-op).
            ``corrupt_backup``: optional path of moved-aside malformed
                file, when status == STATUS_RECOVERED_FROM_CORRUPT.
            ``error``: optional string detail when status == write_error.

    The function never raises — every failure is reported through the
    status dict. The merchant briefing must not be blocked by a logger.
    """
    p = Path(history_path)
    if not enabled:
        return {"status": STATUS_DISABLED, "path": str(p), "records_after": 0}
    if engine_run is None:
        return {"status": STATUS_NO_ENGINE_RUN, "path": str(p), "records_after": 0}

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {
            "status": STATUS_WRITE_ERROR,
            "path": str(p),
            "records_after": 0,
            "error": f"could not create parent dir: {e}",
        }

    existing, was_corrupt = _read_existing(p)
    corrupt_backup: Optional[Path] = None
    if was_corrupt:
        corrupt_backup = _move_corrupt_aside(p)

    record = build_record(engine_run)
    existing.append(record)

    try:
        p.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")
    except OSError as e:
        return {
            "status": STATUS_WRITE_ERROR,
            "path": str(p),
            "records_after": 0,
            "error": f"could not write file: {e}",
            **({"corrupt_backup": str(corrupt_backup)} if corrupt_backup else {}),
        }

    out: Dict[str, Any] = {
        "status": STATUS_RECOVERED_FROM_CORRUPT if was_corrupt else STATUS_OK,
        "path": str(p),
        "records_after": len(existing),
    }
    if corrupt_backup is not None:
        out["corrupt_backup"] = str(corrupt_backup)
    return out


# ---------------------------------------------------------------------------
# Schema invariant — T9.3: drivers are required for non-suppressed ranges
# ---------------------------------------------------------------------------


def assert_drivers_present_for_non_suppressed(engine_run: EngineRun) -> List[str]:
    """T9.3 — return a list of play_ids whose ``revenue_range`` violates the
    drivers-required invariant.

    Locked schema rule: any non-suppressed ``RevenueRange`` MUST carry at
    least one provenance entry in ``drivers``. The M6 sizing module
    already populates this; M9 only locks the schema down so a future
    call site cannot regress.

    The function returns the offending play_ids rather than raising so
    the caller (test or runtime) can decide. Callers that want a hard
    assertion should wrap with ``assert not assert_drivers_present_for_non_suppressed(...)``.
    """
    offenders: List[str] = []
    for c in engine_run.recommendations or []:
        rr = c.revenue_range
        if rr is None:
            continue
        if rr.suppressed:
            continue
        if not rr.drivers:
            offenders.append(c.play_id)
    return offenders


__all__ = [
    "SCHEMA_VERSION",
    "STATUS_DISABLED",
    "STATUS_NO_ENGINE_RUN",
    "STATUS_OK",
    "STATUS_RECOVERED_FROM_CORRUPT",
    "STATUS_WRITE_ERROR",
    "assert_drivers_present_for_non_suppressed",
    "build_record",
    "write_recommended_history",
]
