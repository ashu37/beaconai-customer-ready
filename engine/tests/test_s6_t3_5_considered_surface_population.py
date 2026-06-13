"""S6-T3.5 Prereq 1 tests — Considered-routing seams populate the T3.z
``RejectedPlay`` surface fields (``audience_size``, ``audience_definition``,
``mechanism``).

T3.z added the schema-additive fields; the renderer field-presence-gates
each branch. This ticket wires the three Considered-routing seams in
``src/decide.py`` so the renderer has values to read on the validated
path:

  - ``_route_window_disagreement_holds`` (PlayCard → RejectedPlay)
  - ``_route_prior_unvalidated_holds`` (PlayCard → RejectedPlay)
  - ``populate_considered_from_candidates`` (Candidate → RejectedPlay)

Graceful-render contract: when source data is genuinely unavailable
(no Audience attached, no mechanism authored), the seam emits ``None``
and the renderer falls through to the legacy / pre-T3.z shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set

import pytest

from src.decide import (
    _route_prior_unvalidated_holds,
    _route_window_disagreement_holds,
    populate_considered_from_candidates,
)
from src.engine_run import (
    Audience,
    EngineRun,
    EvidenceClass,
    Measurement,
    MechanismIntent,
    PlayCard,
    ReasonCode,
    RevenueRange,
    RevenueRangeSource,
    WindowCorroboration,
)


@dataclass
class _StubCandidate:
    play_id: str
    audience_size: int = 0
    segment_definition: str = ""
    audience_ids: Set[str] = field(default_factory=set)


def _make_card(
    *,
    play_id: str,
    audience: Optional[Audience],
    measurement: Optional[Measurement] = None,
    revenue_range: Optional[RevenueRange] = None,
) -> PlayCard:
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.MEASURED,
        confidence_label="Strong",
        audience=audience,
        measurement=measurement,
        revenue_range=revenue_range,
    )


# ---------------------------------------------------------------------------
# _route_window_disagreement_holds — PlayCard → RejectedPlay
# ---------------------------------------------------------------------------


def test_window_disagreement_populates_surface_fields_from_card():
    aud = Audience(id="aud-1", definition="Per-SKU cadence-due cohort", size=412)
    meas = Measurement(
        metric="returning_customer_share",
        window_corroboration=WindowCorroboration.CONTRADICTED,
    )
    # replenishment_due carries a metadata.mechanism block in priors.yaml.
    card = _make_card(play_id="replenishment_due", audience=aud, measurement=meas)

    kept, refused = _route_window_disagreement_holds([card], flag_on=True)

    assert kept == []
    assert len(refused) == 1
    rej = refused[0]
    assert rej.reason_code == ReasonCode.WINDOW_DISAGREEMENT
    assert rej.audience_size == 412
    assert rej.audience_definition == "Per-SKU cadence-due cohort"
    # S13.6-T6: mechanism is now Optional[MechanismIntent] (was str).
    assert isinstance(rej.mechanism, MechanismIntent)


def test_window_disagreement_mechanism_none_for_play_without_metadata():
    """winback_21_45 has no metadata block in priors.yaml → mechanism = None."""

    aud = Audience(id="aud-x", definition="x", size=100)
    meas = Measurement(window_corroboration=WindowCorroboration.CONTRADICTED)
    card = _make_card(play_id="winback_21_45", audience=aud, measurement=meas)

    _, refused = _route_window_disagreement_holds([card], flag_on=True)
    assert len(refused) == 1
    assert refused[0].audience_size == 100
    assert refused[0].audience_definition == "x"
    assert refused[0].mechanism is None


def test_window_disagreement_renders_gracefully_without_audience():
    """No ``Audience`` attached → audience_size / audience_definition stay None."""

    meas = Measurement(
        metric="returning_customer_share",
        window_corroboration=WindowCorroboration.CONTRADICTED,
    )
    card = _make_card(play_id="some_unknown_play_id", audience=None, measurement=meas)

    _, refused = _route_window_disagreement_holds([card], flag_on=True)
    assert len(refused) == 1
    rej = refused[0]
    assert rej.audience_size is None
    assert rej.audience_definition is None
    # No metadata in priors.yaml for an unknown play_id → mechanism stays None.
    assert rej.mechanism is None


def test_window_disagreement_flag_off_no_op():
    aud = Audience(id="aud-1", definition="x", size=100)
    meas = Measurement(window_corroboration=WindowCorroboration.CONTRADICTED)
    card = _make_card(play_id="winback_21_45", audience=aud, measurement=meas)

    kept, refused = _route_window_disagreement_holds([card], flag_on=False)
    assert kept == [card]
    assert refused == []


# ---------------------------------------------------------------------------
# _route_prior_unvalidated_holds — PlayCard → RejectedPlay
# ---------------------------------------------------------------------------


def test_prior_unvalidated_populates_surface_fields_from_card():
    aud = Audience(id="aud-2", definition="Per-SKU cadence-due cohort", size=158)
    rr = RevenueRange(
        suppressed=True,
        source=RevenueRangeSource.STORE_OBSERVED,
        drivers=[{"reason": "prior_unvalidated"}],
    )
    card = _make_card(
        play_id="replenishment_due",
        audience=aud,
        revenue_range=rr,
    )

    kept, refused = _route_prior_unvalidated_holds([card], flag_on=True)

    assert kept == []
    assert len(refused) == 1
    rej = refused[0]
    assert rej.reason_code == ReasonCode.PRIOR_UNVALIDATED
    assert rej.audience_size == 158
    assert rej.audience_definition == "Per-SKU cadence-due cohort"
    # replenishment_due gained a metadata block at S6-T3; mechanism must be authored.
    # S13.6-T6: mechanism is now Optional[MechanismIntent] (was str).
    assert isinstance(rej.mechanism, MechanismIntent)


def test_prior_unvalidated_flag_off_no_op():
    rr = RevenueRange(
        suppressed=True,
        source=RevenueRangeSource.STORE_OBSERVED,
        drivers=[{"reason": "prior_unvalidated"}],
    )
    card = _make_card(play_id="replenishment_due", audience=None, revenue_range=rr)
    kept, refused = _route_prior_unvalidated_holds([card], flag_on=False)
    assert kept == [card]
    assert refused == []


# ---------------------------------------------------------------------------
# populate_considered_from_candidates — Candidate → RejectedPlay
# ---------------------------------------------------------------------------


def test_populate_considered_lifts_fields_from_candidate():
    cand = _StubCandidate(
        play_id="replenishment_due",
        audience_size=523,
        segment_definition="Per-SKU cadence-due cohort (vertical=beauty, N>=30)",
    )

    run = EngineRun(recommendations=[], considered=[])
    out = populate_considered_from_candidates(run, [cand], vertical="beauty")

    assert len(out.considered) == 1
    rej = out.considered[0]
    assert rej.play_id == "replenishment_due"
    assert rej.audience_size == 523
    assert rej.audience_definition.startswith("Per-SKU cadence-due cohort")
    # S13.6-T6: mechanism is now Optional[MechanismIntent] (was str).
    assert isinstance(rej.mechanism, MechanismIntent)


def test_populate_considered_none_when_candidate_missing_fields():
    """Empty segment_definition + zero audience_size still parses gracefully."""

    cand = _StubCandidate(
        play_id="winback_21_45",
        audience_size=0,
        segment_definition="",
    )

    run = EngineRun(recommendations=[], considered=[])
    out = populate_considered_from_candidates(run, [cand], vertical="beauty")

    # The candidate is still appended (no recommended_ids overlap; no existing considered).
    assert len(out.considered) == 1
    rej = out.considered[0]
    # audience_size=0 is a valid int; legitimate cohort signal even when small.
    assert rej.audience_size == 0
    # Empty segment_definition coerces to None so the renderer omits the row.
    assert rej.audience_definition is None
    # winback_21_45 has no metadata block in priors.yaml → mechanism stays None.
    assert rej.mechanism is None
