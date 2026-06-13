"""Lock-aware projection of a PlayCard into the atoms fed to the LLM.

This module is the FIRST half of the lock enforcement: it decides exactly
which typed atoms cross the boundary into the prompt. The guards module
(``guards.py``) is the SECOND half — it verifies the LLM's *output*.

Why both halves: the DS locks are output-validation guarantees, but the
cheapest way to keep the prompt honest is to never feed the LLM a footgun
field in the first place. We project a narrow, lock-clean atom bundle.

Locks enforced AT THIS INPUT BOUNDARY:

- L1 — ``evidence_class`` is NEVER copied into the projection. Only
  ``evidence_source`` (the merchant-facing chip) is surfaced.
- L3 — ``model_card_ref.fit_warnings`` is NEVER copied into the
  projection (audit-only).
- L6 — no CSV-derived ``aov_individual`` / CSV ``predicted_segment``
  (we read only ``PlayCard.predicted_segment.segment_name``, which honors
  the D-S13-2 floor; the CSV columns are not on the EngineRun anyway).
- L7 / RULE A — ``mechanism_intent is None`` projects ``mechanism=None``
  (no mechanism line); a populated ``.type`` with empty/None params
  projects the type name with ONLY the non-None params.
- L8 — a dollar figure is projected ONLY from a non-suppressed
  ``revenue_range`` whose ``source == BLEND`` and whose p10/p50/p90 are
  non-None. Otherwise ``dollar_figures`` is empty and ``revenue_note``
  explains the suppression/absence.

The projection is a plain dict (JSON-safe) so it can be embedded in the
prompt and logged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ...engine_run import (
    MechanismIntent,
    PlayCard,
    RejectedPlay,
    RevenueRange,
    RevenueRangeSource,
)

# Mechanism types whose parameters are TODO(S14) None-valued (L7). Named
# explicitly per the brief. Even when ``.parameters`` carries the keys,
# the values are None and must not produce a dollar/share figure.
_NONE_PARAM_TYPES = {
    "THRESHOLD_BUNDLE_OFFER",
    "DISCOUNT_DEPENDENCY_HYGIENE",
    "REPLENISHMENT_REMINDER",
}

# Tier-B types whose parameters are {} (empty) in v2.0.0 (L7). Name the
# mechanism; invent zero params.
_TIER_B_EMPTY_PARAM_TYPES = {
    "BESTSELLER_AMPLIFY",
    "CATEGORY_EXPANSION",
    "SUBSCRIPTION_NUDGE",
    "ROUTINE_BUILDER",
    "LOOKALIKE_HIGH_VALUE_PROSPECT",
}


@dataclass
class CardAtoms:
    """The lock-clean projection of one card, ready for the prompt.

    ``allowed_dollar_figures`` is the SINGLE source of truth for which
    dollar numbers may appear in the output — the guards reject any other.
    """

    play_id: str
    role: str  # "recommendation" | "recommended_experiment" | "considered"
    evidence_source: Optional[str] = None  # the chip, never the class
    confidence_label: Optional[str] = None
    audience: Dict[str, Any] = field(default_factory=dict)
    measurement: Dict[str, Any] = field(default_factory=dict)
    mechanism: Optional[Dict[str, Any]] = None  # None => RULE A, no mechanism line
    segment_name: Optional[str] = None  # only from PlayCard.predicted_segment (L6)
    would_be_measured_by: Optional[str] = None
    # L8: the ONLY dollar figures that may appear in output prose.
    allowed_dollar_figures: List[float] = field(default_factory=list)
    revenue_note: str = ""  # explains suppression / non-BLEND absence
    # Considered-only:
    reason_code: Optional[str] = None
    held_reason_detail: Optional[Dict[str, Any]] = None

    def to_prompt_dict(self) -> Dict[str, Any]:
        """JSON-safe dict for embedding in the prompt. evidence_class,
        fit_warnings, and CSV-derived fields are structurally absent."""
        d: Dict[str, Any] = {
            "play_id": self.play_id,
            "role": self.role,
            "evidence_source": self.evidence_source,
            "confidence_label": self.confidence_label,
            "audience": self.audience,
            "mechanism": self.mechanism,
            "segment_name": self.segment_name,
            "allowed_dollar_figures": self.allowed_dollar_figures,
            "revenue_note": self.revenue_note,
        }
        if self.measurement:
            d["measurement"] = self.measurement
        if self.would_be_measured_by:
            d["would_be_measured_by"] = self.would_be_measured_by
        if self.role == "considered":
            d["reason_code"] = self.reason_code
            d["held_reason_detail"] = self.held_reason_detail
        return d


def _enum_value(v: Any) -> Optional[str]:
    if v is None:
        return None
    return getattr(v, "value", v)


def _project_mechanism(mi: Optional[MechanismIntent]) -> Optional[Dict[str, Any]]:
    """Project mechanism_intent to a lock-clean dict, or None (RULE A).

    - ``mi is None`` => return None (no mechanism line; RULE A / L7).
    - populated type => return ``{"type": <name>, "parameters": {only
      non-None params}}``. None-valued params (the TODO(S14) types) are
      dropped so the LLM cannot see — and therefore cannot launder — a
      fabricated value. Empty-param Tier-B types yield ``parameters={}``.
    """
    if mi is None:
        return None

    type_name = _enum_value(mi.type)
    params_in = mi.parameters or {}
    # Drop None-valued params entirely (L7 None-param types). Keep only
    # concretely-present scalars/lists the engine actually emitted.
    params_out: Dict[str, Any] = {
        k: v for k, v in params_in.items() if v is not None
    }
    return {"type": type_name, "parameters": params_out}


def _project_revenue(rr: Optional[RevenueRange]) -> tuple[List[float], str]:
    """Return (allowed_dollar_figures, revenue_note) per L8.

    A dollar figure is allowed ONLY when:
      - rr is not None
      - rr.suppressed is False
      - rr.source == BLEND
      - the p10/p50/p90 values are non-None
    Otherwise no dollar figure is allowed and the note explains why.
    """
    if rr is None:
        return [], "No revenue range was sized for this play; narrate audience + context only."

    if rr.suppressed:
        reason = _enum_value(rr.suppression_reason) or "suppressed"
        return [], (
            f"Revenue range is SUPPRESSED ({reason}); do NOT state any dollar "
            "figure — narrate audience + real context only."
        )

    source = _enum_value(rr.source)
    if source != RevenueRangeSource.BLEND.value:
        # L8: only source=BLEND ranges are emittable. STORE_OBSERVED /
        # VERTICAL_PRIOR / None are NOT merchant-facing dollar figures.
        return [], (
            "Revenue range is not a BLEND-sourced posterior "
            f"(source={source}); do NOT state any dollar figure for this "
            "play — narrate audience + context only."
        )

    figures: List[float] = []
    for v in (rr.p10, rr.p50, rr.p90):
        if isinstance(v, (int, float)):
            figures.append(float(v))
    if not figures:
        return [], (
            "Revenue range is BLEND-sourced but carries no p10/p50/p90 "
            "values; do NOT state any dollar figure."
        )
    return figures, ""


def _is_store_measured(evidence_source: Optional[str]) -> bool:
    return evidence_source == "STORE_MEASURED"


def project_play_card(card: PlayCard, role: str) -> CardAtoms:
    """Project a recommendation / experiment PlayCard to lock-clean atoms."""
    evidence_source = _enum_value(card.evidence_source)

    audience: Dict[str, Any] = {}
    if card.audience is not None:
        audience = {
            "size": card.audience.size,
            "fraction_of_base": card.audience.fraction_of_base,
            "definition": card.audience.definition,
        }

    measurement: Dict[str, Any] = {}
    if card.measurement is not None:
        # Surface only merchant-safe measurement atoms. p_internal /
        # ci_internal are NEVER rendered (M9 hook) — omit them.
        measurement = {
            "metric": card.measurement.metric,
            "observed_effect": card.measurement.observed_effect,
            "n": card.measurement.n,
            "primary_window": card.measurement.primary_window,
        }

    segment_name = None
    if card.predicted_segment is not None:
        # Only the floor-honoring PlayCard.predicted_segment.segment_name
        # (L6). May be None when the modal-segment floor was not cleared.
        segment_name = card.predicted_segment.segment_name

    allowed_dollars, revenue_note = _project_revenue(card.revenue_range)

    # L2: a non-STORE_MEASURED card's range is NOT lift. Today every card
    # is non-STORE_MEASURED. Even when a BLEND dollar figure is allowed,
    # it must be framed as a baseline-rate posterior, never as lift. We
    # carry an explicit framing flag for the prompt + the guard.
    is_lift_claimable = _is_store_measured(evidence_source)

    if allowed_dollars and not is_lift_claimable:
        revenue_note = (
            "Dollar figures are a prior-anchored posterior on a baseline "
            "rate — NOT lift, NOT incremental, NOT 'expected from sending'. "
            "Frame them as a sizing of the opportunity, never as a promised "
            "gain from running the play."
        )

    return CardAtoms(
        play_id=card.play_id,
        role=role,
        evidence_source=evidence_source,
        confidence_label=card.confidence_label,
        audience=audience,
        measurement=measurement,
        mechanism=_project_mechanism(card.mechanism_intent),
        segment_name=segment_name,
        would_be_measured_by=_enum_value(card.would_be_measured_by),
        allowed_dollar_figures=allowed_dollars,
        revenue_note=revenue_note,
    )


def project_rejected_play(rp: RejectedPlay, role: str = "considered") -> CardAtoms:
    """Project a Considered (RejectedPlay) entry to lock-clean atoms.

    Considered cards have no revenue_range; no dollar figure is allowed.
    L3: the reason is the typed ``reason_code`` + ``held_reason_detail``
    only — never a fit_warning.
    """
    return CardAtoms(
        play_id=rp.play_id,
        role=role,
        mechanism=_project_mechanism(rp.mechanism),
        audience={
            "size": rp.audience_size,
            "definition": rp.audience_definition,
        },
        would_be_measured_by=_enum_value(rp.would_be_measured_by),
        allowed_dollar_figures=[],
        revenue_note="Considered (held) play — no revenue figure to state.",
        reason_code=_enum_value(rp.reason_code),
        held_reason_detail=rp.held_reason_detail,
    )


__all__ = [
    "CardAtoms",
    "project_play_card",
    "project_rejected_play",
]
