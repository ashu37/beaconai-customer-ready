"""Candidate detection (Milestone 3).

Pure-function detector. Iterates the M2 :data:`src.play_registry.PLAYS`
registry, calls the matching audience builder from
:mod:`src.audience_builders`, and emits a :class:`Candidate` per play.
M3 is shadow-only; nothing here gates, scores, or otherwise affects
the legacy briefing output. The :func:`detect_candidates` entrypoint
is invoked from :mod:`src.main` only when ``ENGINE_V2_SHADOW=true``.

Hard scope (M3):

- No statistics. ``Candidate`` does NOT carry ``p_value``, ``q_value``,
  ``confidence``, ``revenue``, ``ci_low``, ``ci_high``, ``measured_effect``,
  ``score``, ``rank``, or ``recommended``. The schema is intentionally
  thin so that M4a/M4b cannot accidentally smuggle fabricated values
  through this surface.
- No filtering. Candidates with a ``preliminary_rejection_reason`` are
  emitted, not dropped. M5 is the milestone that turns rejections into
  hard gates.
- No registry mutation. M2 owns ``PLAYS``; M3 only reads it.
- ``cold_start`` is logged-only per T3.4.
- ``audience_overlap`` is computed pairwise per T3.5 and attached to
  each candidate.

Outputs are JSON-serializable via :meth:`Candidate.to_dict`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set

import pandas as pd

from .audience_builders import AudienceResult, get_builder


# ---------------------------------------------------------------------------
# Candidate schema (M3-only contract).
# ---------------------------------------------------------------------------


# Forbidden field names on Candidate. Listed here as the forcing function
# enforced by ``tests/test_detect_candidates.py`` so M4a/M4b cannot
# silently re-introduce statistics on the detector surface.
FORBIDDEN_CANDIDATE_FIELDS = frozenset(
    {
        "p_value",
        "p",
        "q_value",
        "q",
        "confidence",
        "confidence_label",
        "confidence_score",
        "revenue",
        "expected_$",
        "expected_dollars",
        "ci_low",
        "ci_high",
        "ci_internal",
        "measured_effect",
        "observed_effect",
        "effect_abs",
        "effect_size",
        "score",
        "final_score",
        "rank",
        "recommended",
    }
)


@dataclass
class Candidate:
    """Slim candidate object emitted by :func:`detect_candidates`.

    Fields:
        play_id: stable identifier of the registered play.
        audience_size: number of unique customers matched by the
            audience builder.
        segment_definition: short human-readable rule description.
        data_used: list of field/window names the builder referenced.
        preliminary_rejection_reason: ``None`` if the audience cleared
            the minimum-N predicate; otherwise a short rejection code.
        cold_start: logged-only flag (T3.4). Present for downstream
            milestones; M3 does not gate or filter on it.
        audience_overlap: per-other-play overlap (Jaccard) keyed by
            ``play_id``. Populated by :func:`compute_audience_overlap`
            after all candidates have been built. Shadow-only.
    """

    play_id: str
    audience_size: int
    segment_definition: str
    data_used: List[str] = field(default_factory=list)
    preliminary_rejection_reason: Optional[str] = None
    cold_start: bool = False
    audience_overlap: Dict[str, float] = field(default_factory=dict)
    # S-FE-descriptive-distribution: internal stash carried from the
    # builder's AudienceResult so the prior-anchored producer can bind a
    # typed DescriptiveDistribution. None for non-distributional plays.
    # Not serialized in ``to_dict`` (raw discarded series, mirrors the
    # AudienceResult stash; the binned atom lives on the Audience atom).
    descriptive_kind: Optional[str] = None
    descriptive_series: Optional[List[float]] = None
    descriptive_marker: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "play_id": self.play_id,
            "audience_size": int(self.audience_size),
            "segment_definition": self.segment_definition,
            "data_used": list(self.data_used),
            "preliminary_rejection_reason": self.preliminary_rejection_reason,
            "cold_start": bool(self.cold_start),
            "audience_overlap": {k: float(v) for k, v in self.audience_overlap.items()},
        }


# ---------------------------------------------------------------------------
# Cold-start detection (T3.4) — logged-only.
# ---------------------------------------------------------------------------


def detect_cold_start(g: Optional[pd.DataFrame], cfg: Optional[Dict[str, Any]] = None) -> bool:
    """Return True if the store has fewer than 90 days of clean data.

    Per the M3 ticket: ``cold_start = days_of_clean_data < 90``. This
    is computed from the order-level frame ``g`` by taking the date
    range between the earliest and latest ``Created at``. If the frame
    is empty or missing the column, we conservatively flag cold-start
    True (insufficient data to disprove cold-start).

    The threshold can be overridden via ``cfg["COLD_START_DAYS"]`` for
    future flexibility; default 90.
    """

    threshold = 90
    try:
        if cfg and "COLD_START_DAYS" in cfg:
            threshold = int(cfg["COLD_START_DAYS"])
    except (TypeError, ValueError):
        threshold = 90

    if g is None or getattr(g, "empty", True):
        return True
    if "Created at" not in g.columns:
        return True

    s = pd.to_datetime(g["Created at"], errors="coerce").dropna()
    if s.empty:
        return True
    days = int((s.max() - s.min()).days)
    return days < threshold


# ---------------------------------------------------------------------------
# Audience overlap (T3.5) — pure function on customer-id sets.
# ---------------------------------------------------------------------------


def jaccard(a: Set[str], b: Set[str]) -> float:
    """Jaccard coefficient: |A ∩ B| / |A ∪ B|.

    Returns 0.0 when both sets are empty (the conventional convention
    used here; alternative would be NaN, but downstream JSON
    serialization is simpler with a numeric 0.0). Pure and
    deterministic.
    """

    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return float(inter) / float(union)


def compute_audience_overlap(
    audiences: Mapping[str, Set[str]]
) -> Dict[str, Dict[str, float]]:
    """Pairwise Jaccard overlap per (play_id_a, play_id_b).

    Input: mapping ``play_id -> set of customer_ids``.
    Output: mapping ``play_id_a -> {play_id_b: jaccard}`` for every
        ordered pair where ``a != b``. Self-pairs are omitted.

    Pure and unit-tested in ``tests/test_audience_overlap.py``.
    """

    out: Dict[str, Dict[str, float]] = {}
    keys = list(audiences.keys())
    for a in keys:
        a_set = audiences.get(a) or set()
        row: Dict[str, float] = {}
        for b in keys:
            if a == b:
                continue
            b_set = audiences.get(b) or set()
            row[b] = jaccard(a_set, b_set)
        out[a] = row
    return out


# ---------------------------------------------------------------------------
# Detector entrypoint.
# ---------------------------------------------------------------------------


def _min_cover_days_from_metrics(inventory_metrics: Any) -> Optional[float]:
    """Return the minimum ``cover_days`` value across all SKUs.

    Mirrors the M5 ``gate_inventory`` 'no inventory data => no-op' rule:
    returns ``None`` when ``inventory_metrics`` is absent / empty / does
    not carry a ``cover_days`` column.

    Pure / defensive. Used by :func:`detect_candidates` to stamp
    ``preliminary_rejection_reason="inventory_blocked"`` on SKU-pushing
    candidates without re-implementing the M5 cover-days computation.
    """

    if inventory_metrics is None:
        return None
    try:
        if getattr(inventory_metrics, "empty", True):
            return None
        if "cover_days" not in inventory_metrics.columns:
            return None
        cover_min = inventory_metrics["cover_days"].min()
    except Exception:
        return None

    try:
        return float(cover_min)
    except (TypeError, ValueError):
        return None


def _resolve_inventory_threshold(cfg: Optional[Mapping[str, Any]]) -> int:
    """Resolve the inventory cover-days threshold from cfg.

    Mirrors ``src.guardrails._coerce_min_cover_days`` so the M3 stamp
    and the M5 gate use the same threshold without M3 importing
    guardrails (keeps M3 import-light per the M3 contract).
    """

    default = 21  # matches src.guardrails.DEFAULT_MIN_COVER_DAYS
    if not cfg:
        return default
    raw = cfg.get("INVENTORY_MIN_COVER_DAYS") or {}
    if isinstance(raw, dict):
        try:
            v = raw.get("default")
            if v is not None:
                return int(float(v))
        except (TypeError, ValueError):
            pass
    return default


# Synthetic Blocker Fix 4: SKU-pushing plays that can be held by
# inventory. Mirrors ``src.guardrails.SKU_PUSH_PLAYS`` so the M3 stamp
# uses the same set as the M5 gate. Kept locally instead of imported
# to keep the M3 module import-light per the M3 contract (M3 is
# shadow-only and must not pull in M5 guardrail wiring at import time).
_SKU_PUSH_PLAYS: frozenset[str] = frozenset(
    {
        "bestseller_amplify",
        "routine_builder",
        "category_expansion",
        "overstock_demand_push",
    }
)


def detect_candidates(
    g: pd.DataFrame,
    aligned: Optional[Dict[str, Any]],
    cfg: Optional[Dict[str, Any]],
    registry: Optional[Mapping[str, Any]] = None,
    *,
    inventory_metrics: Optional[Any] = None,
) -> List[Candidate]:
    """Iterate the registry and emit a :class:`Candidate` per play.

    Args:
        g: order-level features dataframe (output of
            ``compute_features``). Read-only.
        aligned: KPI snapshot dict (from ``kpi_snapshot_with_deltas``
            or ``aligned_periods_summary``). Read-only.
        cfg: engine config dict (from ``get_config``). Read-only.
        registry: mapping ``play_id -> PlayDef``. Defaults to the M2
            ``src.play_registry.PLAYS`` registry.
        inventory_metrics: optional pandas DataFrame from
            ``src.load.compute_inventory_metrics``. When provided AND
            the minimum ``cover_days`` across SKUs falls below the
            threshold (default 21, overridable via
            ``cfg["INVENTORY_MIN_COVER_DAYS"]["default"]``), SKU-pushing
            candidates with non-zero audience are stamped with
            ``preliminary_rejection_reason="inventory_blocked"`` so the
            V2 considered list can surface the hold via
            :data:`src.decide._PRELIM_REASON_MAP`. Synthetic Blocker
            Fix 4. When ``inventory_metrics is None`` this is a no-op
            (mirrors ``gate_inventory``'s 'no inventory data => no-op'
            rule).

    Returns:
        A list of :class:`Candidate` objects, one per registered play
        the detector could resolve a builder for. Plays with no
        registered builder are emitted with
        ``preliminary_rejection_reason="no_builder"``.

    The list is NOT filtered. Candidates with rejection reasons are
    kept so downstream debug tooling and M5 gates can see them.
    """

    if registry is None:
        from .play_registry import PLAYS as _PLAYS

        registry = _PLAYS

    cs_flag = detect_cold_start(g, cfg)
    cands: List[Candidate] = []
    audiences: Dict[str, Set[str]] = {}

    # Synthetic Blocker Fix 4: pre-compute the min cover-days so the
    # per-candidate stamp is cheap and deterministic.
    min_cover_days = _min_cover_days_from_metrics(inventory_metrics)
    inventory_threshold = _resolve_inventory_threshold(cfg)
    inventory_blocked = (
        min_cover_days is not None
        and float(min_cover_days) < float(inventory_threshold)
    )

    for play_id, play_def in registry.items():
        builder_ref = getattr(play_def, "audience_builder_ref", None)
        builder = get_builder(builder_ref) if builder_ref else None
        if builder is None:
            cand = Candidate(
                play_id=play_id,
                audience_size=0,
                segment_definition=f"no builder registered for {builder_ref!r}",
                data_used=[],
                preliminary_rejection_reason="no_builder",
                cold_start=cs_flag,
            )
            cands.append(cand)
            audiences[play_id] = set()
            continue

        try:
            res: AudienceResult = builder(g, aligned or {}, cfg or {})
        except Exception as exc:  # defensive — builders should not raise
            cand = Candidate(
                play_id=play_id,
                audience_size=0,
                segment_definition=f"builder error: {type(exc).__name__}",
                data_used=[],
                preliminary_rejection_reason="builder_error",
                cold_start=cs_flag,
            )
            cands.append(cand)
            audiences[play_id] = set()
            continue

        prelim_reason = res.preliminary_rejection_reason

        # Synthetic Blocker Fix 4: stamp inventory_blocked on
        # SKU-pushing plays when backing inventory is below the
        # cover-days threshold. Only stamp when:
        #   - inventory_metrics is provided (no-op without data),
        #   - the play is in the SKU-pushing set,
        #   - the candidate has a non-zero audience (otherwise the
        #     audience-zero / data-missing reason wins; inventory is
        #     not why the play is being held),
        #   - the audience builder did not already produce a more
        #     specific rejection reason (we never overwrite an upstream
        #     reason — preserves audience_too_small / data_missing).
        if (
            inventory_blocked
            and prelim_reason is None
            and play_id in _SKU_PUSH_PLAYS
            and int(res.audience_size or 0) > 0
        ):
            prelim_reason = "inventory_blocked"

        cand = Candidate(
            play_id=play_id,
            audience_size=int(res.audience_size),
            segment_definition=res.segment_definition,
            data_used=list(res.data_used),
            preliminary_rejection_reason=prelim_reason,
            cold_start=cs_flag,
            # S-FE-descriptive-distribution: carry the discarded builder
            # series stash (DORMANCY_DAYS / AOV_GAP / REORDER_GAP_DAYS /
            # DISCOUNT_FRACTION) from the AudienceResult onto the Candidate
            # so the producer (measurement_builder._maybe_build_descriptive_
            # distribution) can bind the typed atom. Without this hop the
            # stash is dropped here and Audience.descriptive_distribution is
            # None for every play. Descriptive-only string VALUE; the
            # producer coerces it to DistributionKind (builders stay pure).
            descriptive_kind=getattr(res, "descriptive_kind", None),
            descriptive_series=getattr(res, "descriptive_series", None),
            descriptive_marker=getattr(res, "descriptive_marker", None),
        )
        cands.append(cand)
        audiences[play_id] = set(res.audience_ids or set())

    # Pairwise overlap (Jaccard) over the customer-id sets.
    overlap_map = compute_audience_overlap(audiences)
    for c in cands:
        c.audience_overlap = overlap_map.get(c.play_id, {})

    return cands


def candidates_to_jsonable(cands: Iterable[Candidate]) -> List[Dict[str, Any]]:
    """Materialize candidates to a list of dicts for JSON serialization."""

    return [c.to_dict() for c in cands]


__all__ = [
    "Candidate",
    "FORBIDDEN_CANDIDATE_FIELDS",
    "detect_candidates",
    "detect_cold_start",
    "jaccard",
    "compute_audience_overlap",
    "candidates_to_jsonable",
]
