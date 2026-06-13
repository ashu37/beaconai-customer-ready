"""Guardrail engine (Milestone 5).

Five gates that turn structurally-invalid candidates into ``RejectedPlay``
records on the typed ``EngineRun`` object. Each gate is a pure function;
the orchestrator ``apply_guardrails`` composes them.

Design intent (per implementation-manager-overhaul-plan-final.md M5):

- Guardrails MUST produce ``RejectedPlay`` objects with reason codes, not
  silently filter. The merchant-facing rendering of the considered list is
  M8's job; M5 only owns the data.
- Gates are structurally additive on top of the M4b EngineRun. A run with
  every guardrail flag OFF is byte-identical to the M4b run.
- M6 sizing is not yet built. The materiality and portfolio-cap gates
  read whatever ``revenue_range.p50`` is present (in M4b that field comes
  from legacy ``expected_$``). When ``p50 is None`` the gate cannot fire
  and is a no-op for that candidate; this keeps the contract M6-stable.
- Inventory data is optional. With no inventory data the gate is a no-op
  and emits a structured warning (caller decides whether to log).
- Any HARD data-quality flag on the EngineRun causes ``apply_guardrails``
  to set ``abstain.state = ABSTAIN_HARD`` and clear recommendations
  (per the architecture invariant in ``engine_run.py``).
- Audience overlap >50% demotes the lower-priority play. Priority is the
  candidate's index in ``recommendations`` (the engine's existing rank).
  M7 will replace this with class-aware ranking; M5's job is purely to
  surface the rejection reason.
- The portfolio-cap rule (sum of p50 <= 25% of monthly revenue) is the
  M5 stub for the M6 sizing layer. Implemented as a gate today; M6
  refines once ``size_play()`` exists. **Backoff:** if the cap demotes
  every candidate, retain the top-1 with a "constrained_by_portfolio_cap"
  annotation. Do not synthesize an ABSTAIN_SOFT for cap reasons alone
  (per plan T5.4).

Hard NOT-IN-SCOPE (do NOT do here, per the M5 ticket):
- Do NOT implement decision-state transitions other than the explicit
  HARD-flag path. ABSTAIN_SOFT for "0 measured/directional after
  gating" is M7 T7.4.
- Do NOT change the renderer.
- Do NOT delete legacy code.
- Do NOT introduce M6 sizing economics.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
)

from .engine_run import (
    Abstain,
    Conflicts,
    DataQualityFlag,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Inventory,
    PlayCard,
    ReasonCode,
    RejectedPlay,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# DataQualityFlags that should trigger ABSTAIN_HARD per the plan + the
# engine_run.py architecture invariant ("Any populated data_quality_flags
# ⇒ abstain.state = abstain_hard"). T5.2 calls out the four hard codes;
# POST_PROMO_WINDOW is treated as a soft-warning-only flag (the M1 detector
# fires it as a contextual note, not a HARD abstain trigger). The plan's
# "any data_quality_flag => ABSTAIN_HARD" rule and the M5 T5.2 list agree
# on the four below.
HARD_DATA_QUALITY_FLAGS: frozenset[DataQualityFlag] = frozenset(
    {
        DataQualityFlag.BFCM_OVERLAP,
        DataQualityFlag.REFUND_STORM,
        DataQualityFlag.TEST_ORDER_ANOMALY,
        DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY,
    }
)


# Plays that push specific SKUs and therefore must clear an inventory check
# before the engine recommends demand generation. Mirrors the registry's
# ``requires_inventory`` flag for ``bestseller_amplify`` and adds the three
# additional plays the M5 plan calls out explicitly: ``routine_builder``,
# ``category_expansion``, ``overstock_demand_push``.
#
# ``overstock_demand_push`` is a forward-looking play_id (not yet in the
# legacy emitter); it is included here so the gate is ready when M6/M7 wire
# it. The set is the source of truth for inventory-gating, NOT the
# registry, because the registry's ``requires_inventory`` is per-PlayDef
# and may evolve independently. Both must agree for ``bestseller_amplify``.
SKU_PUSH_PLAYS: frozenset[str] = frozenset(
    {
        "bestseller_amplify",
        "routine_builder",
        "category_expansion",
        "overstock_demand_push",
    }
)


# Default cover threshold below which an inventory-dependent play is blocked.
# Matches the M5 T5.1 plan ("require days_of_cover >= 21").
DEFAULT_MIN_COVER_DAYS: int = 21

# Default cannibalization overlap threshold (Jaccard or simple ratio).
# Matches the M5 T5.4 plan (>50%).
DEFAULT_OVERLAP_THRESHOLD: float = 0.5

# Portfolio cap as a fraction of monthly revenue.
# Matches the M5 T5.4 plan (sum of p50 <= 25%).
DEFAULT_PORTFOLIO_CAP_FRACTION: float = 0.25

# Recently-run-fatigue lookback (days). Matches M5 T5.5 plan ("28 days").
DEFAULT_FATIGUE_DAYS: int = 28


# ---------------------------------------------------------------------------
# Scale-aware materiality floor (T5.3)
# ---------------------------------------------------------------------------


def scale_aware_materiality_floor(monthly_revenue: Optional[float]) -> float:
    """Return the scale-aware materiality floor for one merchant.

    Tiers (per PM-Q3 + M5 T5.3):

    - ``< $1M ARR``: ``max($5,000, 2% of monthly_revenue)``
    - ``$1M-$5M ARR``: ``max($10,000, 3% of monthly_revenue)``
    - ``> $5M ARR``: ``max($25,000, 5% of monthly_revenue)``

    ``monthly_revenue`` is the L28 net_sales proxy from
    ``EngineRun.scale.monthly_revenue``. ARR is approximated as
    ``monthly_revenue * 12``. When ``monthly_revenue`` is ``None`` or
    non-positive the smallest tier's absolute floor ($5k) is returned;
    this conservatively blocks tiny-impact plays while not falsely
    suppressing them on a missing scale.
    """

    if monthly_revenue is None:
        return 5_000.0
    try:
        mr = float(monthly_revenue)
    except (TypeError, ValueError):
        return 5_000.0
    if mr <= 0:
        return 5_000.0

    arr = mr * 12.0
    if arr < 1_000_000.0:
        return max(5_000.0, 0.02 * mr)
    if arr < 5_000_000.0:
        return max(10_000.0, 0.03 * mr)
    return max(25_000.0, 0.05 * mr)


# ---------------------------------------------------------------------------
# Inventory gate (T5.1)
# ---------------------------------------------------------------------------


def _is_sku_push(play_id: str) -> bool:
    return str(play_id or "").strip().lower() in SKU_PUSH_PLAYS


def _coerce_min_cover_days(cfg: Optional[Mapping[str, Any]]) -> int:
    """Resolve the per-play minimum cover days from cfg or fall back."""

    if not cfg:
        return DEFAULT_MIN_COVER_DAYS
    raw = cfg.get("INVENTORY_MIN_COVER_DAYS") or {}
    if isinstance(raw, dict):
        try:
            v = raw.get("default")
            if v is not None:
                return int(float(v))
        except (TypeError, ValueError):
            pass
    return DEFAULT_MIN_COVER_DAYS


def gate_inventory(
    candidate: PlayCard,
    inventory_metrics: Optional[Any],
    *,
    min_cover_days: Optional[int] = None,
    cfg: Optional[Mapping[str, Any]] = None,
) -> Optional[RejectedPlay]:
    """Block SKU-pushing plays whose backing SKUs lack adequate cover.

    Args:
        candidate: a typed PlayCard. Reads ``play_id`` and (if present)
            ``inventory.skus``/``inventory.days_of_cover``. M5 does not
            re-query CSVs.
        inventory_metrics: a pandas DataFrame from
            ``load.compute_inventory_metrics`` OR ``None``. When ``None``
            the gate is a NO-OP — see "no inventory data" branch below.
        min_cover_days: override the threshold (default 21).
        cfg: optional engine cfg; consulted for ``INVENTORY_MIN_COVER_DAYS``
            (per-play threshold map). Falls back to ``min_cover_days`` /
            ``DEFAULT_MIN_COVER_DAYS``.

    Returns:
        ``RejectedPlay`` with ``reason_code = INVENTORY_BLOCKED`` if the
        gate fires, else ``None``.

    Behavior matrix:
        - Play not in ``SKU_PUSH_PLAYS``: returns ``None`` (gate not
          applicable to non-SKU-pushing plays).
        - ``inventory_metrics is None`` (or empty/no ``cover_days`` col):
          NO-OP. Returns ``None`` and does not raise. Caller should log a
          warning. This implements the plan's "no inventory data => gate
          is no-op, log warning, do not block plays" rule.
        - Play is SKU-pushing AND inventory data is present AND minimum
          cover_days across SKUs is below the threshold: fires
          ``INVENTORY_BLOCKED``.
    """

    if not _is_sku_push(candidate.play_id):
        return None

    threshold = (
        int(min_cover_days)
        if min_cover_days is not None
        else _coerce_min_cover_days(cfg)
    )

    # Cover candidate-level inventory first (already populated by M1
    # adapter or hand-built tests).
    cand_inv = candidate.inventory
    if cand_inv is not None and cand_inv.days_of_cover is not None:
        if float(cand_inv.days_of_cover) < float(threshold):
            return RejectedPlay(
                play_id=candidate.play_id,
                reason_code=ReasonCode.INVENTORY_BLOCKED,
            )

    # Otherwise consult inventory_metrics directly.
    if inventory_metrics is None:
        return None
    try:
        # pandas-DataFrame check without importing pandas at module level
        # (so the module remains import-light).
        if getattr(inventory_metrics, "empty", True):
            return None
        if "cover_days" not in inventory_metrics.columns:
            return None
        cover_min_val = inventory_metrics["cover_days"].min()
    except Exception:
        return None

    try:
        cover_min = float(cover_min_val)
    except (TypeError, ValueError):
        return None

    if cover_min >= float(threshold):
        return None

    return RejectedPlay(
        play_id=candidate.play_id,
        reason_code=ReasonCode.INVENTORY_BLOCKED,
    )


# ---------------------------------------------------------------------------
# Anomalous-window gate (T5.2)
# ---------------------------------------------------------------------------


def gate_anomaly(
    data_quality_flags: Iterable[DataQualityFlag],
) -> Optional[Tuple[DecisionState, str, List[DataQualityFlag]]]:
    """Decide abstain state from data-quality flags (B-1 routing).

    Returns:
        ``None`` if no flag warrants any abstain.
        ``(ABSTAIN_HARD, reason, hard_flags)`` when any HARD flag is set
        (whole-run abstain; recommendations are cleared by caller).
        ``(ABSTAIN_SOFT, reason, soft_flags)`` when only the soft
        ``POST_PROMO_WINDOW`` flag is present (load-bearing window;
        per-play hold; recommendations are routed into ``considered``
        with ``ReasonCode.ANOMALOUS_WINDOW``).

    HARD flags always win over the soft path.

    The caller is responsible for clearing recommendations and writing
    the new state into the EngineRun (see ``apply_guardrails``).
    """

    flags = list(data_quality_flags or [])
    hard = [f for f in flags if f in HARD_DATA_QUALITY_FLAGS]
    if hard:
        reason = (
            "Hard data-quality flag(s) detected: "
            + ", ".join(sorted({f.value for f in hard}))
        )
        return DecisionState.ABSTAIN_HARD, reason, hard

    soft = [f for f in flags if f == DataQualityFlag.POST_PROMO_WINDOW]
    if soft:
        reason = (
            "Load-bearing window anomaly detected: "
            + ", ".join(sorted({f.value for f in soft}))
        )
        return DecisionState.ABSTAIN_SOFT, reason, soft
    return None


# ---------------------------------------------------------------------------
# Materiality gate (T5.3)
# ---------------------------------------------------------------------------


def gate_materiality(
    candidate: PlayCard,
    monthly_revenue: Optional[float],
    *,
    profile_floor_usd: Optional[float] = None,
) -> Optional[RejectedPlay]:
    """Block plays whose ``revenue_range.p50`` is below the scale-aware floor.

    No-op when ``revenue_range`` is ``None``, ``revenue_range.p50`` is
    ``None``, ``revenue_range.suppressed == True`` (M6 cold-start rule),
    or ``monthly_revenue`` is unknown/non-positive — in those cases there
    is no comparable estimate to gate on.

    Sprint 6.5 Ticket T4: when ``profile_floor_usd`` is provided (caller
    threads it from ``profile.gate_calibration.materiality_floor_usd``
    under ``ENGINE_V2_STORE_PROFILE`` flag-ON), the profile-driven
    stage-banded floor overrides ``scale_aware_materiality_floor``.
    Flag-OFF behavior is unchanged.
    """

    rr = candidate.revenue_range
    if rr is None or rr.p50 is None:
        return None
    if rr.suppressed:
        # Targeting/cold-start cards have no merchant-facing $ headline.
        # The materiality gate should not fire on a suppressed range.
        return None
    if monthly_revenue is None and profile_floor_usd is None:
        return None
    try:
        mr = float(monthly_revenue) if monthly_revenue is not None else 0.0
    except (TypeError, ValueError):
        return None
    if mr <= 0 and profile_floor_usd is None:
        return None

    if profile_floor_usd is not None:
        try:
            floor = float(profile_floor_usd)
        except (TypeError, ValueError):
            floor = scale_aware_materiality_floor(mr)
    else:
        floor = scale_aware_materiality_floor(mr)
    try:
        p50 = float(rr.p50)
    except (TypeError, ValueError):
        return None

    if p50 >= floor:
        return None

    return RejectedPlay(
        play_id=candidate.play_id,
        reason_code=ReasonCode.MATERIALITY_BELOW_FLOOR,
    )


# ---------------------------------------------------------------------------
# Cannibalization / overlap gate (T5.4)
# ---------------------------------------------------------------------------


def gate_cannibalization(
    candidates: List[PlayCard],
    overlap_map: Mapping[str, Mapping[str, float]],
    *,
    threshold: float = DEFAULT_OVERLAP_THRESHOLD,
) -> Tuple[List[PlayCard], List[RejectedPlay]]:
    """Demote a lower-priority play whose audience overlaps a higher-priority one.

    Args:
        candidates: list of PlayCards in priority order. Index 0 is the
            highest-priority candidate. Priority is the caller's
            responsibility — M5 does not re-rank. M7 introduces
            class-aware ranking; until then ``recommendations`` already
            arrives ranked by the legacy scorer.
        overlap_map: ``{play_id_a: {play_id_b: overlap_pct}}``. Pairwise
            overlap (e.g., Jaccard) computed by
            ``src.detect.compute_audience_overlap``. May be empty.
        threshold: overlap fraction above which the lower-priority play
            is demoted (default 0.5 = 50%).

    Returns:
        ``(kept, rejected)`` — ``kept`` are the candidates that survived
        the gate (same dataclass instances or replaced with a
        ``conflicts`` annotation if they cannibalized lower-priority
        candidates). ``rejected`` are RejectedPlay records keyed by
        ``play_id``.

    Each RejectedPlay carries ``reason_code = AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY``
    and a ``reason_text`` referencing the higher-priority play and the
    overlap percentage.

    The function is order-stable: when iterating candidates in priority
    order, a candidate is dropped iff some earlier kept candidate
    overlaps it above threshold.
    """

    kept: List[PlayCard] = []
    rejected: List[RejectedPlay] = []

    # Track which kept candidates need a conflicts annotation update.
    # We mutate via dataclasses.replace so the caller's input list is
    # never mutated in place.
    conflicts_to_attach: Dict[str, Dict[str, float]] = {}

    for cand in candidates or []:
        cand_id = cand.play_id
        offender_id: Optional[str] = None
        offender_pct: float = 0.0

        for prior in kept:
            prior_id = prior.play_id
            row = overlap_map.get(prior_id) or {}
            try:
                pct = float(row.get(cand_id, 0.0))
            except (TypeError, ValueError):
                pct = 0.0
            if pct >= float(threshold) and pct > offender_pct:
                offender_id = prior_id
                offender_pct = pct

        if offender_id is None:
            kept.append(cand)
            continue

        rejected.append(
            RejectedPlay(
                play_id=cand_id,
                reason_code=ReasonCode.AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY,
            )
        )
        # Annotate the offender so M8 can render "this play is the
        # cannibalizer of X".
        conflicts_to_attach.setdefault(offender_id, {})[cand_id] = offender_pct

    # Apply conflicts annotations to the kept list without mutating
    # dataclass inputs (we replace with a new instance carrying a
    # populated ``conflicts``).
    annotated: List[PlayCard] = []
    for cand in kept:
        extra = conflicts_to_attach.get(cand.play_id) or {}
        if not extra:
            annotated.append(cand)
            continue
        prev = cand.conflicts or Conflicts()
        new_list = list(prev.cannibalized_by)
        for victim in extra.keys():
            if victim not in new_list:
                new_list.append(victim)
        max_overlap = max(extra.values()) if extra else prev.audience_overlap_pct
        new_conf = Conflicts(
            cannibalized_by=new_list,
            audience_overlap_pct=(
                max_overlap if max_overlap is not None else prev.audience_overlap_pct
            ),
        )
        annotated.append(replace(cand, conflicts=new_conf))

    return annotated, rejected


def enforce_portfolio_cap(
    candidates: List[PlayCard],
    monthly_revenue: Optional[float],
    *,
    cap_fraction: float = DEFAULT_PORTFOLIO_CAP_FRACTION,
) -> Tuple[List[PlayCard], List[RejectedPlay]]:
    """Cap sum of ``revenue_range.p50`` at ``cap_fraction * monthly_revenue``.

    Backoff (per plan T5.4): if the cap would demote everything, retain
    the top-1 candidate with no rejection (the engine refuses to
    "constrained_by_portfolio_cap" itself out of all recommendations).

    Returns:
        ``(kept, rejected)``. Rejected entries carry
        ``reason_code = CANNIBALIZATION_DEMOTED``.
    """

    kept: List[PlayCard] = []
    rejected: List[RejectedPlay] = []

    if not candidates:
        return kept, rejected

    if monthly_revenue is None:
        return list(candidates), rejected
    try:
        mr = float(monthly_revenue)
    except (TypeError, ValueError):
        return list(candidates), rejected
    if mr <= 0:
        return list(candidates), rejected

    cap_dollars = cap_fraction * mr

    running = 0.0
    for idx, cand in enumerate(candidates):
        rr = cand.revenue_range
        if rr is None or rr.p50 is None:
            kept.append(cand)
            continue
        try:
            p50 = float(rr.p50)
        except (TypeError, ValueError):
            kept.append(cand)
            continue
        if (running + p50) <= cap_dollars + 1e-9:
            kept.append(cand)
            running += p50
            continue

        # If we would demote everything, keep top-1 (backoff).
        if not kept and idx == 0:
            kept.append(cand)
            running += p50
            continue

        rejected.append(
            RejectedPlay(
                play_id=cand.play_id,
                reason_code=ReasonCode.CANNIBALIZATION_DEMOTED,
            )
        )
    return kept, rejected


# ---------------------------------------------------------------------------
# Recently-run-fatigue stub (T5.5)
# ---------------------------------------------------------------------------


def _read_recommended_history(
    history_path: Optional[str],
) -> List[Dict[str, Any]]:
    """Read ``data/recommended_history.json`` if present. Return [] otherwise.

    M9 owns writing this file. M5 only reads it; the file is optional.
    """

    if not history_path:
        return []
    p = Path(history_path)
    if not p.exists() or not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text() or "[]")
    except Exception:
        return []
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    return []


def _card_audience_definition_version(card: PlayCard) -> int:
    """Return the ``audience_definition_version`` for a candidate (D-1).

    Mirrors the policy in ``src/main.py::_audience_definition_version``:
    defaults to ``1`` until the Audience dataclass carries an explicit
    integer field. The founder-defined gap is documented in ``memory.md``
    under D-1.

    Local-helper duplication is intentional — calling into ``src.main``
    from ``src.guardrails`` would introduce an import cycle, and the
    policy is one line of code stably anchored on D-1.
    """

    return 1


def gate_recently_run(
    candidate: PlayCard,
    history_path: Optional[str],
    *,
    fatigue_days: int = DEFAULT_FATIGUE_DAYS,
    now: Optional[datetime] = None,
    store_id: Optional[str] = None,
    audience_definition_version: Optional[int] = None,
) -> Optional[RejectedPlay]:
    """Demote a candidate already recommended for the same lineage tuple
    within ``fatigue_days``.

    S10-T0 (DS-locked correctness fix): match key is the **four-component
    lineage tuple**

        (play_id, audience_definition_id, store_id, audience_definition_version)

    aligned to the S3 lineage schema enforced by
    ``src/memory/lineage.py::compute_lineage_id`` (which already requires
    all four args per founder decision D-1). The prior 3-tuple key
    ``(play_id, audience_definition_id, store_id)`` was a correctness bug
    regardless of broader lifecycle scope; see
    ``agent_outputs/play-lifecycle-discussion-reconciled.md:47``.

    Each component is matched with the same defensive policy (only
    enforce when both sides carry the field), so existing history
    records (which may pre-date the per-store directory layout or the
    ``audience_definition_version`` lineage field) keep matching on
    whatever subset of components they do carry. ``audience_definition_id``
    falls back to ``audience.id`` until the Audience dataclass carries an
    explicit field. ``audience_definition_version`` is provided by the
    caller (typically via ``_audience_definition_version(card)`` in
    ``src/main.py``) and defaults to ``None`` (no version constraint).

    The history file is a JSON list of records:

        [
          {"store_id": "...",
           "play_id": "winback_21_45",
           "audience_id": "winback_21_45_inactive",
           "audience_definition_version": 1,
           "anchor_date": "2026-04-01",
           "ts": "2026-04-01T00:00:00Z"},
           ...
        ]

    No-op when the file is missing/empty (M5 plan: "If file absent, no-op.")
    """

    history = _read_recommended_history(history_path)
    if not history:
        return None

    cand_id = str(candidate.play_id or "").strip().lower()
    cand_audience: Optional[str] = None
    if candidate.audience is not None and candidate.audience.id:
        cand_audience = str(candidate.audience.id)
    cand_store = str(store_id).strip() if store_id else None
    cand_adv: Optional[int] = None
    if audience_definition_version is not None:
        try:
            cand_adv = int(audience_definition_version)
        except (TypeError, ValueError):
            cand_adv = None

    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=int(fatigue_days))

    for rec in history:
        rec_play = str(rec.get("play_id") or "").strip().lower()
        if rec_play != cand_id:
            continue
        rec_aud = rec.get("audience_id")
        if cand_audience and rec_aud and str(rec_aud) != cand_audience:
            continue
        rec_store = rec.get("store_id")
        if cand_store and rec_store and str(rec_store).strip() != cand_store:
            continue
        # S10-T0: 4th lineage component — audience_definition_version.
        # Defensive: only enforce when both sides carry the field, mirroring
        # the policy used for store_id/audience_id above. This keeps
        # history records that pre-date the field from spuriously matching
        # or spuriously failing to match.
        rec_adv_raw = rec.get("audience_definition_version")
        if cand_adv is not None and rec_adv_raw is not None:
            try:
                rec_adv = int(rec_adv_raw)
            except (TypeError, ValueError):
                rec_adv = None
            if rec_adv is not None and rec_adv != cand_adv:
                continue
        ts_raw = rec.get("ts") or rec.get("anchor_date")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts < cutoff:
            continue
        # Match within the fatigue window.
        return RejectedPlay(
            play_id=candidate.play_id,
            reason_code=ReasonCode.RECENTLY_RUN_FATIGUE,
        )
    return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _flag_on(cfg: Optional[Mapping[str, Any]], key: str) -> bool:
    if not cfg:
        return False
    v = cfg.get(key)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "on"}
    return False


def apply_guardrails(
    engine_run: EngineRun,
    *,
    inventory_metrics: Optional[Any] = None,
    audience_overlap: Optional[Mapping[str, Mapping[str, float]]] = None,
    history_path: Optional[str] = None,
    cfg: Optional[Mapping[str, Any]] = None,
    store_id: Optional[str] = None,
) -> EngineRun:
    """Apply all M5 guardrails to an EngineRun.

    Returns a NEW EngineRun. Inputs are not mutated. Each gate is
    individually flag-gated:

        - ``ANOMALY_GATE_ENABLED``       => HARD-flag check
        - ``INVENTORY_GATE_ENABLED``     => inventory cover check
        - ``MATERIALITY_FLOOR_SCALE_AWARE`` => scale-aware $ floor
        - ``CANNIBALIZATION_GATE_ENABLED`` => overlap demotion + portfolio cap
        - ``RECENTLY_RUN_FATIGUE_ENABLED`` => 28d fatigue lookback

    With every flag OFF, ``apply_guardrails`` is a deep-copy no-op:
    returns the input EngineRun unchanged in semantics.

    Hard-flag handling: when the anomaly gate fires, ``recommendations``
    is cleared and ``abstain.state = ABSTAIN_HARD``. Already-rejected
    candidates and existing ``data_quality_flags`` are preserved.
    """

    cfg = cfg or {}

    # Snapshot inputs.
    recs = list(engine_run.recommendations or [])
    considered: List[RejectedPlay] = list(engine_run.considered or [])
    flags = list(engine_run.data_quality_flags or [])
    monthly_revenue = (
        engine_run.scale.monthly_revenue if engine_run.scale else None
    )

    # ---- T5.2 / B-1: anomalous-window gate -------------------------------
    abstain = engine_run.abstain
    if _flag_on(cfg, "ANOMALY_GATE_ENABLED"):
        outcome = gate_anomaly(flags)
        if outcome is not None:
            state, reason, abstain_flags = outcome
            # S13.6-T1a (Option D): ``reason_text`` / ``evidence_snapshot``
            # / ``would_fire_if`` / ``Abstain.reason`` stripped per Pivot 2.
            # The typed ``reason_code`` + ``data_quality_flags`` carry the
            # contract surface; downstream narration recomposes prose.
            for r in recs:
                considered.append(
                    RejectedPlay(
                        play_id=r.play_id,
                        reason_code=ReasonCode.ANOMALOUS_WINDOW,
                    )
                )
            recs = []
            abstain = Abstain(state=state)
            return _build_updated(
                engine_run,
                recommendations=recs,
                considered=considered,
                abstain=abstain,
                scale_floor=_recompute_floor(engine_run, cfg),
            )

    # ---- T5.1: inventory gate -------------------------------------------
    if _flag_on(cfg, "INVENTORY_GATE_ENABLED"):
        survivors: List[PlayCard] = []
        for cand in recs:
            rej = gate_inventory(cand, inventory_metrics, cfg=cfg)
            if rej is None:
                survivors.append(cand)
            else:
                considered.append(rej)
        recs = survivors

    # ---- T5.3: scale-aware materiality floor ----------------------------
    if _flag_on(cfg, "MATERIALITY_FLOOR_SCALE_AWARE"):
        # Sprint 6.5 Ticket T4: when ENGINE_V2_STORE_PROFILE is ON and
        # the engine_run carries a typed StoreProfile, the profile's
        # ``gate_calibration.materiality_floor_usd`` (stage-banded)
        # overrides the scale-aware $ floor. Flag-OFF preserves today's
        # ``scale_aware_materiality_floor`` behavior — byte-identical on
        # every pinned fixture.
        profile_floor: Optional[float] = None
        if _flag_on(cfg, "ENGINE_V2_STORE_PROFILE"):
            sp = getattr(engine_run, "store_profile", None)
            if sp is not None:
                gc = getattr(sp, "gate_calibration", None)
                if gc is not None:
                    profile_floor = getattr(gc, "materiality_floor_usd", None)
        survivors = []
        for cand in recs:
            rej = gate_materiality(
                cand, monthly_revenue, profile_floor_usd=profile_floor
            )
            if rej is None:
                survivors.append(cand)
            else:
                considered.append(rej)
        recs = survivors

    # ---- T5.5: recently-run fatigue stub --------------------------------
    # S10-T0: fatigue is now lineage-keyed (4-tuple
    # play_id × audience_definition_id × store_id × audience_definition_version).
    if _flag_on(cfg, "RECENTLY_RUN_FATIGUE_ENABLED"):
        survivors = []
        for cand in recs:
            rej = gate_recently_run(
                cand,
                history_path,
                store_id=store_id,
                audience_definition_version=_card_audience_definition_version(cand),
            )
            if rej is None:
                survivors.append(cand)
            else:
                considered.append(rej)
        recs = survivors

    # ---- T5.4: cannibalization + portfolio cap --------------------------
    if _flag_on(cfg, "CANNIBALIZATION_GATE_ENABLED"):
        overlap = audience_overlap or {}
        survivors, rej_overlap = gate_cannibalization(
            recs, overlap, threshold=DEFAULT_OVERLAP_THRESHOLD
        )
        considered.extend(rej_overlap)
        recs = survivors
        # Then enforce portfolio cap on the remaining set.
        survivors, rej_cap = enforce_portfolio_cap(
            recs, monthly_revenue, cap_fraction=DEFAULT_PORTFOLIO_CAP_FRACTION
        )
        considered.extend(rej_cap)
        recs = survivors

    return _build_updated(
        engine_run,
        recommendations=recs,
        considered=considered,
        abstain=abstain,
        scale_floor=_recompute_floor(engine_run, cfg),
    )


# ---------------------------------------------------------------------------
# Helpers for orchestrator
# ---------------------------------------------------------------------------


def _recompute_floor(
    engine_run: EngineRun, cfg: Optional[Mapping[str, Any]]
) -> Optional[float]:
    """Recompute Scale.materiality_floor using the scale-aware function.

    Active only when ``MATERIALITY_FLOOR_SCALE_AWARE`` is on. Otherwise
    returns the existing floor (None preserved).
    """

    if not _flag_on(cfg, "MATERIALITY_FLOOR_SCALE_AWARE"):
        return engine_run.scale.materiality_floor if engine_run.scale else None
    mr = engine_run.scale.monthly_revenue if engine_run.scale else None
    if mr is None:
        return engine_run.scale.materiality_floor if engine_run.scale else None
    return scale_aware_materiality_floor(mr)


def _build_updated(
    base: EngineRun,
    *,
    recommendations: List[PlayCard],
    considered: List[RejectedPlay],
    abstain: Abstain,
    scale_floor: Optional[float],
) -> EngineRun:
    """Return a new EngineRun with the post-guardrail fields applied."""

    new_scale = base.scale
    if scale_floor != (base.scale.materiality_floor if base.scale else None):
        new_scale = replace(base.scale, materiality_floor=scale_floor)

    return replace(
        base,
        recommendations=recommendations,
        considered=considered,
        abstain=abstain,
        scale=new_scale,
    )


# ---------------------------------------------------------------------------
# S7.6-C2: apply_guardrails_to_injected
# ---------------------------------------------------------------------------


def apply_guardrails_to_injected(
    engine_run: EngineRun,
    *,
    pre_injection_play_ids: Set[str],
    inventory_metrics: Optional[Any] = None,
    audience_overlap: Optional[Mapping[str, Mapping[str, float]]] = None,
    history_path: Optional[str] = None,
    cfg: Optional[Mapping[str, Any]] = None,
    store_id: Optional[str] = None,
) -> EngineRun:
    """Re-run guardrails on post-injection cards (S7.6-C2).

    Restores the day-1 single-demote-channel invariant: every drop
    produces a typed ``RejectedPlay`` routed through the same gates as
    :func:`apply_guardrails`. Called once after the last V2
    prior-anchored builder injection block at
    ``src/main.py:1380-1597``.

    ``pre_injection_play_ids`` is the snapshot of
    ``engine_run.recommendations[*].play_id`` taken BEFORE the V2
    prior-anchored builder blocks ran (i.e., the set that already faced
    :func:`apply_guardrails` at ``src/main.py:994``). Cards whose
    ``play_id`` is in this set are passed through untouched.

    Gates fired (matching :func:`apply_guardrails` order; anomaly +
    targeting validation are intentionally excluded — anomaly already
    fired at run-level before injection, targeting validation already
    fired per-card at builder time):

    1. ``gate_inventory`` (``INVENTORY_GATE_ENABLED``)
    2. ``gate_materiality`` (``MATERIALITY_FLOOR_SCALE_AWARE``) — with
       store-profile floor override under ``ENGINE_V2_STORE_PROFILE``.
    3. ``gate_recently_run`` (``RECENTLY_RUN_FATIGUE_ENABLED``) — today
       OFF by default; included so flag-flip does not reintroduce
       bypass.
    4. ``gate_cannibalization`` + :func:`enforce_portfolio_cap`
       (``CANNIBALIZATION_GATE_ENABLED``) — fired on the FULL
       recommendations list so pre-existing cards retain their priority
       index; only injected cards (later index) may be demoted.

    Per ARCHITECTURE_PLAN.md 2026-05-22 single-demote-channel invariant.
    """

    cfg = cfg or {}

    recs = list(engine_run.recommendations or [])
    considered: List[RejectedPlay] = list(engine_run.considered or [])
    monthly_revenue = (
        engine_run.scale.monthly_revenue if engine_run.scale else None
    )

    def _is_injected(card: PlayCard) -> bool:
        return str(card.play_id or "") not in pre_injection_play_ids

    # ---- inventory (injected only) ------------------------------------
    if _flag_on(cfg, "INVENTORY_GATE_ENABLED"):
        survivors: List[PlayCard] = []
        for cand in recs:
            if not _is_injected(cand):
                survivors.append(cand)
                continue
            rej = gate_inventory(cand, inventory_metrics, cfg=cfg)
            if rej is None:
                survivors.append(cand)
            else:
                considered.append(rej)
        recs = survivors

    # ---- materiality (injected only) ----------------------------------
    if _flag_on(cfg, "MATERIALITY_FLOOR_SCALE_AWARE"):
        profile_floor: Optional[float] = None
        if _flag_on(cfg, "ENGINE_V2_STORE_PROFILE"):
            sp = getattr(engine_run, "store_profile", None)
            if sp is not None:
                gc = getattr(sp, "gate_calibration", None)
                if gc is not None:
                    profile_floor = getattr(gc, "materiality_floor_usd", None)
        survivors = []
        for cand in recs:
            if not _is_injected(cand):
                survivors.append(cand)
                continue
            rej = gate_materiality(
                cand, monthly_revenue, profile_floor_usd=profile_floor
            )
            if rej is None:
                survivors.append(cand)
            else:
                considered.append(rej)
        recs = survivors

    # ---- recently-run fatigue (injected only) -------------------------
    # S10-T0: fatigue is now lineage-keyed (4-tuple
    # play_id × audience_definition_id × store_id × audience_definition_version).
    if _flag_on(cfg, "RECENTLY_RUN_FATIGUE_ENABLED"):
        survivors = []
        for cand in recs:
            if not _is_injected(cand):
                survivors.append(cand)
                continue
            rej = gate_recently_run(
                cand,
                history_path,
                store_id=store_id,
                audience_definition_version=_card_audience_definition_version(cand),
            )
            if rej is None:
                survivors.append(cand)
            else:
                considered.append(rej)
        recs = survivors

    # ---- cannibalization + portfolio cap (full list, but only inject-
    # ed cards can be newly demoted because pre-existing cards already
    # passed these gates at apply_guardrails time and their priority
    # index in the list is unchanged) -----------------------------------
    if _flag_on(cfg, "CANNIBALIZATION_GATE_ENABLED"):
        overlap = audience_overlap or {}
        survivors, rej_overlap = gate_cannibalization(
            recs, overlap, threshold=DEFAULT_OVERLAP_THRESHOLD
        )
        # Pre-existing cards already cleared cannibalization in
        # apply_guardrails; any "rejection" of a pre-existing card here
        # would indicate the prior caller missed it — we still surface
        # via the typed channel, so do not filter.
        considered.extend(rej_overlap)
        recs = survivors
        survivors, rej_cap = enforce_portfolio_cap(
            recs, monthly_revenue, cap_fraction=DEFAULT_PORTFOLIO_CAP_FRACTION
        )
        considered.extend(rej_cap)
        recs = survivors

    return _build_updated(
        engine_run,
        recommendations=recs,
        considered=considered,
        abstain=engine_run.abstain,
        scale_floor=_recompute_floor(engine_run, cfg),
    )


__all__ = [
    "DEFAULT_FATIGUE_DAYS",
    "DEFAULT_MIN_COVER_DAYS",
    "DEFAULT_OVERLAP_THRESHOLD",
    "DEFAULT_PORTFOLIO_CAP_FRACTION",
    "HARD_DATA_QUALITY_FLAGS",
    "SKU_PUSH_PLAYS",
    "apply_guardrails",
    "apply_guardrails_to_injected",
    "enforce_portfolio_cap",
    "gate_anomaly",
    "gate_cannibalization",
    "gate_inventory",
    "gate_materiality",
    "gate_recently_run",
    "scale_aware_materiality_floor",
]
