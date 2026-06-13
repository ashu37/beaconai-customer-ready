"""Legacy adapter: build an EngineRun from the existing actions bundle.

Milestone 1, T1.3.

This is a *receipts-only* adapter. The current engine returns an
``actions_bundle`` dict shaped roughly as::

    {
        "actions":         [...],   # PRIMARY actions
        "watchlist":       [...],
        "pilot_actions":   [...],
        "backlog":         [...],
        "confidence_mode": str,
    }

M1 maps the bundle into the typed ``EngineRun`` schema (see
``src.engine_run``) so downstream milestones can read a uniform contract.
The adapter is intentionally *lossy*:

- It does not invent measurements. If a legacy action carries fabricated
  p/effect/CI (which M4a will NaN out), those values are kept on
  ``Measurement`` as-is for the receipts file. M4a's tests will catch
  fabricated values; M1 does not pre-empt them.
- ``evidence_class`` is mapped conservatively. If the legacy candidate
  exposes one, we use it; otherwise we default to ``TARGETING``. M4a
  introduces the canonical classifier.
- ``revenue_range`` is best-effort: legacy ``expected_$`` becomes p50.
  M6 replaces this with audience-economics-derived ranges and proper
  p10/p90.
- The ``Considered`` (rejected) list is empty in M1; M5 produces it.

Hard rule (M1): nothing in this adapter changes the legacy
``actions_bundle`` shape, the legacy ``actions_log.json`` write, or
the rendered briefing. The adapter is read-only of legacy outputs.
"""

from __future__ import annotations

import datetime
import os
import uuid
from typing import Any, Dict, List, Optional

import pandas as pd

from .anomaly import detect_anomalous_windows
from .engine_run import (
    Abstain,
    Audience,
    BriefingMeta,
    DataQualityFlag,
    DataWindow,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Inventory,
    LaunchWindow,
    Measurement,
    PlayCard,
    RevenueRange,
    RevenueRangeSource,
    Scale,
)
from .state_of_store import build_observations


_VALID_EVIDENCE = {ec.value for ec in EvidenceClass}


def _coerce_evidence(value: Any) -> EvidenceClass:
    if value is None:
        return EvidenceClass.TARGETING
    s = str(value).strip().lower()
    if s in _VALID_EVIDENCE:
        return EvidenceClass(s)
    return EvidenceClass.TARGETING


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN guard
        return None
    return f


def _safe_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _build_measurement_from_legacy(action: Dict[str, Any]) -> Optional[Measurement]:
    """Carry whatever stats the legacy candidate exposes.

    M1 does not invent fields and does not classify. M4a is the boundary
    where fabricated stats are NaN'd and ``evidence_class`` is enforced.

    M4b T4b.1: when ``evidence_class == "targeting"``, the contract is
    ``measurement is None`` (see ``engine_run.PlayCard``). Returning
    ``None`` here for targeting candidates keeps the EngineRun output in
    sync with the renderer-facing rule "targeting cards have no measured
    p / effect / CI / consistency".
    """
    if str(action.get("evidence_class") or "").lower() == "targeting":
        return None
    p = _safe_float(action.get("p"))
    effect = _safe_float(action.get("effect_abs") or action.get("effect"))
    n = _safe_int(action.get("n") or action.get("audience_size"))
    ci_low = _safe_float(action.get("ci_low"))
    ci_high = _safe_float(action.get("ci_high"))
    metric = action.get("metric") or action.get("primary_metric")
    primary_window = action.get("source_window") or action.get("primary_window")
    consistency = _safe_int(action.get("consistency_across_windows"))

    have_any = any(
        v is not None for v in (p, effect, n, ci_low, ci_high, metric, primary_window, consistency)
    )
    if not have_any:
        return None

    ci_internal = None
    if ci_low is not None and ci_high is not None:
        ci_internal = [ci_low, ci_high]

    return Measurement(
        metric=str(metric) if metric is not None else None,
        observed_effect=effect,
        n=n,
        primary_window=str(primary_window) if primary_window is not None else None,
        consistency_across_windows=consistency,
        p_internal=p,
        ci_internal=ci_internal,
    )


def _build_audience_from_legacy(action: Dict[str, Any]) -> Optional[Audience]:
    size = _safe_int(action.get("audience_size") or action.get("n"))
    aid = action.get("audience_id") or action.get("segment_id")
    definition = action.get("audience_definition") or action.get("segment_definition")
    fraction = _safe_float(action.get("fraction_of_base"))
    if size is None and aid is None and definition is None and fraction is None:
        return None
    return Audience(
        id=str(aid) if aid is not None else None,
        definition=str(definition) if definition is not None else None,
        size=size,
        fraction_of_base=fraction,
        overlap_with=list(action.get("overlap_with") or []),
    )


def _build_revenue_range_from_legacy(action: Dict[str, Any]) -> Optional[RevenueRange]:
    """Map legacy ``expected_$`` into ``revenue_range.p50``.

    M1 does not synthesize p10/p90. M6 will replace this entirely with
    audience-economics-derived ranges.
    """
    p50 = _safe_float(action.get("expected_$"))
    if p50 is None:
        return None
    drivers: List[Dict[str, Any]] = [{"name": "legacy_expected_dollars", "value": p50}]
    return RevenueRange(
        p10=None,
        p50=p50,
        p90=None,
        source=None,
        drivers=drivers,
        suppressed=False,
    )


def _build_inventory_from_legacy(action: Dict[str, Any]) -> Optional[Inventory]:
    skus = action.get("inventory_skus") or action.get("skus")
    cover = _safe_float(action.get("days_of_cover"))
    if not skus and cover is None:
        return None
    return Inventory(
        skus=list(skus) if skus else [],
        days_of_cover=cover,
        gate_passed=action.get("inventory_gate_passed"),
    )


def _build_launch_window_from_legacy(action: Dict[str, Any]) -> Optional[LaunchWindow]:
    rec = action.get("launch_window") or action.get("recommended_launch_window")
    if rec is None:
        return None
    return LaunchWindow(
        recommended=str(rec) if rec is not None else None,
        reason=action.get("launch_window_reason"),
    )


def _action_to_play_card(action: Dict[str, Any]) -> PlayCard:
    play_id = str(action.get("play_id") or action.get("title") or "unknown")
    # S13.6-T1a (Option D): ``recommendation_text`` / ``why_now`` stripped
    # per Pivot 2. Legacy ``do_this`` / ``why_now`` keys are ignored.
    # S13.6-T6: typed MechanismIntent atom. Lazy import keeps adapter
    # import ordering clean. Returns None for unmapped legacy play_ids.
    from .decide import _build_mechanism_intent as _build_mech_intent
    card = PlayCard(
        play_id=play_id,
        evidence_class=_coerce_evidence(action.get("evidence_class")),
        confidence_label=action.get("confidence_label"),
        audience=_build_audience_from_legacy(action),
        measurement=_build_measurement_from_legacy(action),
        revenue_range=_build_revenue_range_from_legacy(action),
        inventory=_build_inventory_from_legacy(action),
        conflicts=None,  # M5 cannibalization gate populates this
        launch_window=_build_launch_window_from_legacy(action),
        # S13.6-T2: klaviyo_brief_inputs removed (founder lock-in #6).
        receipts_ref=action.get("receipts_ref"),
        # S13.6-T6: typed MechanismIntent atom; None for unmapped play_ids.
        mechanism_intent=_build_mech_intent(play_id),
    )
    # Synthetic Blocker Fix 2: targeting-measurement structural invariant.
    #
    # Memory invariant: ``evidence_class == "targeting"`` ⇒
    # ``measurement is None``.
    #
    # ``_build_measurement_from_legacy`` already short-circuits when the
    # legacy action explicitly stamps ``evidence_class == "targeting"``
    # on the action dict. The leak path is candidates that arrive
    # WITHOUT that stamp: ``_coerce_evidence(None)`` defaults the
    # PlayCard's ``evidence_class`` to TARGETING, but the measurement
    # builder does not see a "targeting" string upstream and happily
    # constructs a full ``Measurement`` (sometimes with saturated
    # ``p_internal`` like 1.6e-72 from the synthetic ``promo_anomaly``
    # fixture).
    #
    # The renderer hides ``measurement`` on targeting cards via M8.
    # Hiding is not safety. This post-hoc clear enforces the invariant
    # structurally on ``EngineRun`` / receipts so internal artifacts
    # (engine_run.json, debug.html, outcome log) cannot carry the
    # leak.
    if card.evidence_class == EvidenceClass.TARGETING:
        card.measurement = None
        assert card.measurement is None, (
            "Targeting PlayCard structural invariant violated for play_id="
            f"{card.play_id!r}: measurement must be None after the "
            "post-hoc clear. This indicates a programming error in the "
            "adapter terminal step."
        )
    return card


def _scale_from_aligned(aligned: Optional[Dict[str, Any]]) -> Scale:
    """Approximate monthly revenue from L28 net_sales. Conservative.

    Synthetic Blocker Fix 5: stamp ``materiality_floor`` unconditionally
    using the existing scale-aware function so the merchant-readable
    materiality footer line ("We only recommend primary plays that
    could realistically add at least $X this month for a store your
    size.") is always available to the V2 renderer on every
    non-ABSTAIN_HARD briefing. Previously the floor was set to ``None``
    here and only stamped later by ``apply_guardrails`` when the
    ``MATERIALITY_FLOOR_SCALE_AWARE`` flag was on. With the flag off
    (the synthetic e2e configuration), the floor never reached the
    renderer and the line was silently dropped.

    This change does NOT alter floor values: ``scale_aware_materiality_floor``
    is the same function ``apply_guardrails._recompute_floor`` uses.
    The M5 ``gate_materiality`` rejection path still requires its own
    flag and is unaffected. Decision logic is unchanged; we only make
    the floor available for rendering.
    """
    # Local import to avoid a top-of-module dependency on the M5
    # guardrails module from the M1-era adapter.
    from .guardrails import scale_aware_materiality_floor

    aligned = aligned or {}
    l28 = aligned.get("L28") or {}
    monthly_rev = None
    try:
        v = l28.get("net_sales")
        monthly_rev = float(v) if v is not None else None
    except (TypeError, ValueError):
        monthly_rev = None
    customer_base = None
    try:
        c = (l28.get("meta") or {}).get("identified_recent")
        customer_base = int(c) if c is not None else None
    except (TypeError, ValueError):
        customer_base = None
    materiality_floor = scale_aware_materiality_floor(monthly_rev)
    return Scale(
        monthly_revenue=monthly_rev,
        customer_base_est=customer_base,
        materiality_floor=materiality_floor,
    )


def _briefing_meta_from_cfg(cfg: Optional[Dict[str, Any]]) -> BriefingMeta:
    cfg = cfg or {}
    return BriefingMeta(
        confidence_mode=cfg.get("CONFIDENCE_MODE"),
        vertical=cfg.get("VERTICAL_MODE") or cfg.get("VERTICAL"),
        subvertical=cfg.get("SUBVERTICAL"),
        stage=cfg.get("BUSINESS_STAGE"),
        seasonality_tag=cfg.get("SEASONALITY_TAG"),
    )


def _data_window_from_cfg(cfg: Optional[Dict[str, Any]]) -> DataWindow:
    cfg = cfg or {}
    primary = cfg.get("CHOSEN_WINDOW") or "L28"
    return DataWindow(
        primary_window=str(primary),
        available_windows=["L7", "L28", "L56", "L90"],
        anchor_quality=None,
    )


def _coerce_anchor_iso(anchor: Any) -> Optional[str]:
    if anchor is None:
        return None
    try:
        ts = pd.to_datetime(anchor, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.isoformat()
    except Exception:
        return None


def build_engine_run_from_legacy(
    actions_bundle: Dict[str, Any],
    aligned: Optional[Dict[str, Any]],
    df: Optional[pd.DataFrame],
    cfg: Optional[Dict[str, Any]] = None,
    *,
    store_id: Optional[str] = None,
    run_id: Optional[str] = None,
    anchor_date: Optional[Any] = None,
) -> EngineRun:
    """Build an EngineRun receipts object from the legacy actions bundle.

    Inputs:
    - ``actions_bundle``: dict returned by ``select_actions``.
    - ``aligned``: KPI snapshot (used for state-of-store + scale).
    - ``df``: order-level dataframe (used for anomaly detection).
    - ``cfg``: engine config (briefing meta).
    - ``store_id``, ``run_id``, ``anchor_date``: optional overrides.

    Returns:
    - ``EngineRun`` populated from legacy outputs. The recommendations
      list mirrors ``actions_bundle["actions"]`` only (PRIMARY).
      Watchlist/pilot/backlog are NOT mapped to ``considered`` in M1
      because their semantics are different from the M5 RejectedPlay
      reason-coded list. M5 will produce ``considered`` properly.
    """
    actions_bundle = actions_bundle or {}
    aligned = aligned or {}
    cfg = cfg or {}

    rid = run_id or str(uuid.uuid4())
    sid = store_id or os.getenv("STORE_ID") or os.getenv("BRAND") or "unknown"
    anchor = anchor_date if anchor_date is not None else aligned.get("anchor")
    anchor_iso = _coerce_anchor_iso(anchor)

    # ---- recommendations ---------------------------------------------------
    primary = list(actions_bundle.get("actions") or [])
    play_cards: List[PlayCard] = [_action_to_play_card(a) for a in primary]

    # ---- anomaly detection (receipts-only in M1) ---------------------------
    flags: List[DataQualityFlag] = []
    try:
        flags = detect_anomalous_windows(df, anchor)
    except Exception:
        flags = []

    # ---- B-1: compute observed/expected day counts for typed slots --------
    # ``n_days_expected`` is the analysis_window_days from the anomaly
    # config (default 28). ``n_days_observed`` is the count of distinct
    # calendar days inside that window that carry at least one order.
    # Both are populated on per-flag Observations in ``state_of_store``.
    n_days_observed_val = 0
    n_days_expected_val = 0
    try:
        from .anomaly import load_anomaly_thresholds as _load_thresh

        _th = _load_thresh()
        n_days_expected_val = int((_th or {}).get("analysis_window_days", 28))
        if df is not None and not df.empty and "Created at" in df.columns and anchor is not None:
            import pandas as _pd

            _anchor_ts = _pd.to_datetime(anchor, errors="coerce")
            try:
                _anchor_ts = _anchor_ts.tz_localize(None) if _anchor_ts.tzinfo else _anchor_ts
            except (AttributeError, TypeError):
                pass
            if _pd.notna(_anchor_ts):
                _end = _pd.Timestamp(_anchor_ts).normalize() + _pd.Timedelta(hours=23, minutes=59, seconds=59)
                _start = _end.normalize() - _pd.Timedelta(days=n_days_expected_val - 1)
                _ts = _pd.to_datetime(df["Created at"], errors="coerce")
                try:
                    _ts = _ts.dt.tz_localize(None)
                except (AttributeError, TypeError):
                    pass
                _mask = (_ts >= _start) & (_ts <= _end)
                _in = _ts[_mask].dropna()
                n_days_observed_val = int(_in.dt.normalize().nunique()) if len(_in) else 0
    except Exception:
        # Defensive: typed slots default to 0 when computation is impossible.
        n_days_observed_val = 0
        n_days_expected_val = n_days_expected_val or 0

    # ---- state of store ----------------------------------------------------
    state_of_store = build_observations(
        aligned=aligned,
        scale=None,
        data_quality_flags=[f.value for f in flags],
        n_days_observed=n_days_observed_val,
        n_days_expected=n_days_expected_val,
    )

    # ---- abstain -----------------------------------------------------------
    # M1: do not change behavior. Default state is PUBLISH unless legacy
    # already produced no actions, in which case ABSTAIN_SOFT is a more
    # honest label for the receipts file. Critically: this does not change
    # any merchant-facing output — only what is written to engine_run.json.
    abstain_state = DecisionState.PUBLISH if play_cards else DecisionState.ABSTAIN_SOFT
    # S13.6-T1a (Option D): ``Abstain.reason`` stripped per Pivot 2; the
    # legacy "legacy actions list is empty" sentence is retired with it.

    return EngineRun(
        run_id=rid,
        store_id=str(sid),
        anchor_date=anchor_iso,
        data_window=_data_window_from_cfg(cfg),
        cold_start=False,  # M3 wires the cold-start detector
        data_quality_flags=flags,
        abstain=Abstain(state=abstain_state),
        state_of_store=state_of_store,
        recommendations=play_cards,
        considered=[],  # M5 produces this
        watching=[],  # M7 T7.9 produces this
        scale=_scale_from_aligned(aligned),
        briefing_meta=_briefing_meta_from_cfg(cfg),
    )


def legacy_actions_from_engine_run(engine_run: EngineRun) -> Dict[str, Any]:
    """T8.7 — Inverse adapter: produce a minimal legacy ``actions_bundle``.

    Lets downstream consumers that still read the legacy bundle shape
    (``actions_log.json`` writer, ``copykit.render_copy_for_actions``,
    console summary) keep working when the V2 renderer is enabled.

    The returned bundle is intentionally minimal:

    - ``actions``: one dict per :class:`PlayCard` in
      ``engine_run.recommendations`` mapping back to the legacy fields
      (``play_id``, ``title``, ``do_this``, ``why_now``, ``audience_size``,
      ``expected_$``, ``evidence_class``).
    - ``watchlist``: empty.
    - ``pilot_actions``: empty.
    - ``backlog``: one dict per :class:`RejectedPlay` in
      ``engine_run.considered`` mapping back to a minimal
      legacy-shaped dict that downstream loggers can serialize safely.
    - ``confidence_mode``: copied through from briefing meta when set.

    This adapter is lossy (the legacy shape does not have first-class
    fields for ``measurement.consistency_across_windows`` or
    ``revenue_range.drivers``); when V2 is the canonical path (M10),
    the adapter and the consumers will be deleted together.

    The function is pure: it does not mutate the input EngineRun.
    """
    if engine_run is None:
        return {
            "actions": [],
            "watchlist": [],
            "pilot_actions": [],
            "backlog": [],
            "confidence_mode": None,
        }

    def _card_to_legacy(card: PlayCard) -> Dict[str, Any]:
        rr = card.revenue_range
        expected = None
        if rr is not None and not rr.suppressed:
            expected = rr.p50
        aud = card.audience
        ev_class = (
            card.evidence_class.value
            if hasattr(card.evidence_class, "value")
            else str(card.evidence_class or "")
        )
        # S13.6-T1a (Option D): ``recommendation_text`` / ``why_now``
        # stripped from PlayCard per Pivot 2. Legacy actions JSON keeps
        # its keys (``title`` / ``do_this`` / ``why_now``) for back-compat
        # but they now carry empty strings (or fall through to play_id
        # for ``title``). Downstream narration owns these slots.
        return {
            "play_id": card.play_id,
            "title": card.play_id,
            "do_this": "",
            "why_now": "",
            "audience_size": aud.size if aud is not None else None,
            "audience_definition": aud.definition if aud is not None else None,
            "expected_$": expected,
            "evidence_class": ev_class,
            "confidence_label": card.confidence_label,
            "how_to_launch": [],
            "attachment": "",
        }

    def _rejection_to_legacy(rej) -> Dict[str, Any]:
        code = (
            rej.reason_code.value
            if rej.reason_code is not None and hasattr(rej.reason_code, "value")
            else None
        )
        # S13.6-T1a (Option D): ``reason_text`` / ``would_fire_if``
        # stripped per Pivot 2. Legacy backlog keys retained (empty)
        # for back-compat with downstream callers.
        return {
            "play_id": rej.play_id,
            "title": rej.play_id,
            "reason": "",
            "reason_code": code,
            "would_fire_if": "",
        }

    confidence_mode = None
    if engine_run.briefing_meta is not None:
        confidence_mode = engine_run.briefing_meta.confidence_mode

    return {
        "actions": [_card_to_legacy(c) for c in (engine_run.recommendations or [])],
        "watchlist": [],
        "pilot_actions": [],
        "backlog": [_rejection_to_legacy(r) for r in (engine_run.considered or [])],
        "confidence_mode": confidence_mode,
    }


__all__ = ["build_engine_run_from_legacy", "legacy_actions_from_engine_run"]
