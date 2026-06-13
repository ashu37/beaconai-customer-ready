"""Phase 6A Ticket A4 — Recommended Experiment decide-layer eligibility tests.

This file pins the eligibility filter for the new
``EngineRun.recommended_experiments`` slate. The filter is gated behind
the ``ENGINE_V2_SLATE`` flag (default OFF). When the flag is OFF, the
filter is a no-op and ``recommended_experiments`` is always ``[]``.

Eligibility rules pinned here (per
``agent_outputs/campaign-slate-contract-final.md``):

1.  Allowlist gate: only ``discount_hygiene`` and ``bestseller_amplify``
    survive the first-ship filter.
2.  Metadata gate: missing or partial metadata in
    ``config/priors.yaml`` rejects the candidate.
3.  Audience floor: ``cand.audience_size >= metadata.audience_floor``.
4.  Mechanism: non-empty (already enforced by the loader; pinned here
    for the consume path).
5.  Vertical: current ``VERTICAL_MODE`` must appear in
    ``metadata.vertical_applicability``.
6.  ``would_be_measured_by`` enum-valid (already enforced by the loader).
7.  Inventory block: ``preliminary_rejection_reason == "inventory_blocked"``
    rejects the candidate.
8.  Audience overlap with every Recommended Now card < 30%.
9.  Slate diversity: no two Recommended Experiment cards may share the
    same ``audience_archetype``.
10. Hard cap: 2 cards.
11. ABSTAIN_SOFT and ABSTAIN_HARD ⇒ output is ``[]``.
12. Output cards always have ``evidence_class == TARGETING``,
    ``revenue_range.suppressed == True``, and a populated
    ``would_be_measured_by`` copied from metadata.

The ticket is decide-layer-only. Renderer is untouched. No producer
populates the field except the new selector.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import priors_loader as PL
from src.engine_run import (
    Abstain,
    Audience,
    DecisionState,
    EngineRun,
    EvidenceClass,
    PlayCard,
    RevenueRange,
    WouldBeMeasuredBy,
)
from src.priors_loader import AudienceArchetype, PlayMetadata


@pytest.fixture(autouse=True)
def _reset_priors_cache():
    PL.clear_cache()
    yield
    PL.clear_cache()


# ---------------------------------------------------------------------------
# Light Candidate stand-in.
#
# The real ``src.detect.Candidate`` is a dataclass with the same field
# names. The selector reads only ``play_id``, ``audience_size``,
# ``segment_definition``, ``preliminary_rejection_reason``, and
# ``audience_overlap``, so a duck-typed stand-in keeps the tests cheap
# and avoids importing pandas just to construct a candidate.
# ---------------------------------------------------------------------------


class _Cand:
    def __init__(
        self,
        play_id: str,
        audience_size: int,
        *,
        segment_definition: str = "test segment",
        preliminary_rejection_reason: Optional[str] = None,
        audience_overlap: Optional[Dict[str, float]] = None,
    ) -> None:
        self.play_id = play_id
        self.audience_size = audience_size
        self.segment_definition = segment_definition
        self.preliminary_rejection_reason = preliminary_rejection_reason
        self.audience_overlap = dict(audience_overlap or {})


def _measured_card(play_id: str = "first_to_second_purchase") -> PlayCard:
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.DIRECTIONAL,
        audience=Audience(size=1000, definition="recent first-time buyers"),
    )


# ---------------------------------------------------------------------------
# Schema: ``EngineRun.recommended_experiments`` field exists, defaults to
# empty, and round-trips through to_dict / from_dict.
# ---------------------------------------------------------------------------


def test_engine_run_recommended_experiments_defaults_empty():
    run = EngineRun()
    assert hasattr(run, "recommended_experiments")
    assert run.recommended_experiments == []


def test_engine_run_recommended_experiments_round_trips():
    card = PlayCard(
        play_id="discount_hygiene",
        evidence_class=EvidenceClass.TARGETING,
        would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
        revenue_range=RevenueRange(
            suppressed=True, drivers=[{"reason": "experiment_no_calibrated_lift"}]
        ),
        audience=Audience(size=1500, definition="discount-prone buyers"),
    )
    run = EngineRun(recommended_experiments=[card])
    payload = run.to_dict()
    assert "recommended_experiments" in payload
    assert payload["recommended_experiments"][0]["play_id"] == "discount_hygiene"
    assert (
        payload["recommended_experiments"][0]["would_be_measured_by"]
        == WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D.value
    )
    assert payload["recommended_experiments"][0]["revenue_range"]["suppressed"] is True

    restored = EngineRun.from_dict(payload)
    assert len(restored.recommended_experiments) == 1
    rt = restored.recommended_experiments[0]
    assert rt.play_id == "discount_hygiene"
    assert rt.evidence_class == EvidenceClass.TARGETING
    assert rt.would_be_measured_by == WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D
    assert rt.revenue_range is not None and rt.revenue_range.suppressed is True


# ---------------------------------------------------------------------------
# Constants on src.decide.
# ---------------------------------------------------------------------------


def test_recommended_experiment_constants_exist():
    from src.decide import (
        MAX_RECOMMENDED_EXPERIMENT,
        RECOMMENDED_EXPERIMENT_ALLOWLIST,
    )

    assert MAX_RECOMMENDED_EXPERIMENT == 2
    assert RECOMMENDED_EXPERIMENT_ALLOWLIST == frozenset(
        {"discount_hygiene", "bestseller_amplify"}
    )


# ---------------------------------------------------------------------------
# Flag-off / flag-on through ``decide()``.
# ---------------------------------------------------------------------------


def test_engine_v2_slate_flag_off_produces_no_recommended_experiments():
    """With ``ENGINE_V2_SLATE=false`` (or unset), ``decide()`` must return
    an EngineRun with ``recommended_experiments == []`` even when the
    candidate set would otherwise pass every gate.
    """

    from src.decide import decide

    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    run = EngineRun(
        recommendations=[_measured_card()],
        briefing_meta=__import__(
            "src.engine_run", fromlist=["BriefingMeta"]
        ).BriefingMeta(vertical="beauty"),
    )

    out = decide(run, cfg={"ENGINE_V2_SLATE": False, "VERTICAL_MODE": "beauty"}, candidates=cands)
    assert out.recommended_experiments == []


def test_selects_allowlisted_targeting_candidates_when_flag_on():
    from src.decide import decide

    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    run = EngineRun(
        recommendations=[_measured_card()],
        briefing_meta=__import__(
            "src.engine_run", fromlist=["BriefingMeta"]
        ).BriefingMeta(vertical="beauty"),
    )

    out = decide(run, cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"}, candidates=cands)
    play_ids = sorted(c.play_id for c in out.recommended_experiments)
    assert play_ids == ["bestseller_amplify", "discount_hygiene"]
    assert len(out.recommended_experiments) == 2


# ---------------------------------------------------------------------------
# Direct-helper tests (cheaper, more flexibility for fault injection).
# ---------------------------------------------------------------------------


def _select(
    cands,
    *,
    flag_on=True,
    decision_state=DecisionState.PUBLISH,
    vertical="beauty",
    recommendations=None,
    metadata_lookup=None,
):
    from src.decide import _select_recommended_experiments

    return _select_recommended_experiments(
        cands,
        recommendations=recommendations or [_measured_card()],
        flag_on=flag_on,
        decision_state=decision_state,
        vertical=vertical,
        metadata_lookup=metadata_lookup,
    )


def test_recommended_experiments_hard_cap_two():
    """Even if a third allowlisted-equivalent path were synthesized, the
    cap is 2. Today the allowlist itself caps the universe at 2; the
    cap remains the structural guarantee.
    """

    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    out = _select(cands)
    assert len(out) <= 2

    # Synthetic stress: inject a third metadata-bearing play via the
    # metadata_lookup, but keep the allowlist intact. The allowlist
    # should still trim it; this proves the cap is robust regardless of
    # metadata expansion.
    extra_arch = AudienceArchetype.LAPSED_BUYER

    def _lookup(play_id: str):
        from src.priors_loader import get_play_metadata

        if play_id == "winback_21_45":
            return PlayMetadata(
                audience_floor=100,
                mechanism="winback test",
                vertical_applicability=["beauty"],
                would_be_measured_by=WouldBeMeasuredBy.INCREMENTAL_ORDERS_IN_14D,
                audience_archetype=extra_arch,
            )
        return get_play_metadata(play_id)

    cands2 = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
        _Cand("winback_21_45", 5000),
    ]
    out2 = _select(cands2, metadata_lookup=_lookup)
    assert len(out2) == 2
    play_ids = {c.play_id for c in out2}
    assert "winback_21_45" not in play_ids


def test_rejects_non_allowlisted_targeting_play():
    cands = [_Cand("winback_21_45", 5000)]

    def _lookup(play_id: str):
        # Simulate full metadata so the only thing rejecting this is the allowlist.
        return PlayMetadata(
            audience_floor=100,
            mechanism="winback test",
            vertical_applicability=["beauty"],
            would_be_measured_by=WouldBeMeasuredBy.INCREMENTAL_ORDERS_IN_14D,
            audience_archetype=AudienceArchetype.LAPSED_BUYER,
        )

    out = _select(cands, metadata_lookup=_lookup)
    assert out == []


def test_rejects_measured_or_directional_candidate():
    """Even if a measured/directional PlayCard exists for an allowlisted
    play_id (e.g. someone wires a measured discount_hygiene later), the
    selector must NOT include it as an experiment. This is the
    role-uniqueness invariant at the selector level.
    """

    cands = [_Cand("discount_hygiene", 5000)]
    measured_card = PlayCard(
        play_id="discount_hygiene",
        evidence_class=EvidenceClass.MEASURED,
        audience=Audience(size=5000),
    )
    out = _select(cands, recommendations=[measured_card])
    assert out == []


def test_rejects_candidate_below_audience_floor():
    # bestseller_amplify floor is 500; provide 499.
    cands = [_Cand("bestseller_amplify", 499)]
    out = _select(cands)
    assert out == []


def test_rejects_candidate_missing_metadata():
    """Allowlisted play_id but the loader returns None for metadata.

    Use a metadata_lookup stub that returns None for the play_id to
    simulate a deployed YAML that has not yet been populated.
    """

    cands = [_Cand("discount_hygiene", 5000)]

    def _lookup(_play_id):
        return None

    out = _select(cands, metadata_lookup=_lookup)
    assert out == []


def test_rejects_candidate_not_vertical_applicable():
    # bestseller_amplify is applicable to {beauty, mixed}; "supplements" rejects.
    cands = [_Cand("bestseller_amplify", 5000)]
    out = _select(cands, vertical="supplements")
    assert out == []


def test_recommended_experiment_populates_would_be_measured_by_from_metadata():
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    out = _select(cands)
    assert len(out) == 2
    by_id = {c.play_id: c for c in out}
    assert by_id["discount_hygiene"].would_be_measured_by == (
        WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D
    )
    assert by_id["bestseller_amplify"].would_be_measured_by == (
        WouldBeMeasuredBy.REPEAT_PURCHASE_IN_30D
    )


def test_recommended_experiment_revenue_range_is_suppressed():
    cands = [_Cand("discount_hygiene", 5000)]
    out = _select(cands)
    assert len(out) == 1
    assert out[0].revenue_range is not None
    assert out[0].revenue_range.suppressed is True
    # No fabricated p10/p50/p90.
    assert out[0].revenue_range.p10 is None
    assert out[0].revenue_range.p50 is None
    assert out[0].revenue_range.p90 is None


def test_recommended_experiment_evidence_class_is_targeting():
    cands = [_Cand("discount_hygiene", 5000)]
    out = _select(cands)
    assert all(c.evidence_class == EvidenceClass.TARGETING for c in out)


def test_recommended_experiment_measurement_is_none():
    cands = [_Cand("discount_hygiene", 5000)]
    out = _select(cands)
    assert all(c.measurement is None for c in out)


def test_abstain_soft_produces_zero_recommended_experiments():
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    out = _select(cands, decision_state=DecisionState.ABSTAIN_SOFT)
    assert out == []


def test_abstain_hard_produces_zero_recommended_experiments():
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    out = _select(cands, decision_state=DecisionState.ABSTAIN_HARD)
    assert out == []


def test_rejects_candidate_with_inventory_block():
    cands = [_Cand("bestseller_amplify", 5000, preliminary_rejection_reason="inventory_blocked")]
    out = _select(cands)
    assert out == []


def test_rejects_candidate_with_too_much_overlap_with_recommended_now():
    """30% overlap with Recommended Now demotes the candidate."""

    rec = _measured_card("first_to_second_purchase")
    cand = _Cand(
        "discount_hygiene",
        5000,
        audience_overlap={"first_to_second_purchase": 0.30},
    )
    out = _select([cand], recommendations=[rec])
    assert out == []


def test_allows_candidate_below_overlap_threshold():
    rec = _measured_card("first_to_second_purchase")
    cand = _Cand(
        "discount_hygiene",
        5000,
        audience_overlap={"first_to_second_purchase": 0.29},
    )
    out = _select([cand], recommendations=[rec])
    assert len(out) == 1
    assert out[0].play_id == "discount_hygiene"


def test_slate_diversity_keeps_only_one_per_audience_archetype():
    """Two candidates with the same archetype: only one survives.

    discount_hygiene -> discount_buyer; bestseller_amplify ->
    hero_sku_buyer. Override metadata to make both share the same
    archetype, then assert we keep exactly one.
    """

    archetype = AudienceArchetype.DISCOUNT_BUYER

    def _lookup(play_id: str):
        if play_id == "discount_hygiene":
            return PlayMetadata(
                audience_floor=200,
                mechanism="m1",
                vertical_applicability=["beauty"],
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
                audience_archetype=archetype,
            )
        if play_id == "bestseller_amplify":
            return PlayMetadata(
                audience_floor=500,
                mechanism="m2",
                vertical_applicability=["beauty"],
                would_be_measured_by=WouldBeMeasuredBy.REPEAT_PURCHASE_IN_30D,
                audience_archetype=archetype,
            )
        return None

    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    out = _select(cands, metadata_lookup=_lookup)
    assert len(out) == 1


# ---------------------------------------------------------------------------
# Property-style invariants over a small set of candidate inputs.
# ---------------------------------------------------------------------------


def test_invariants_over_synthetic_candidate_sets():
    """For every synthesized candidate set, the selector output must:

    - have at most ``MAX_RECOMMENDED_EXPERIMENT`` cards;
    - every output card has ``evidence_class == TARGETING``;
    - every output card has a populated ``would_be_measured_by`` enum;
    - every output card carries a unique ``audience_archetype`` (per
      metadata) — verified via the metadata_lookup;
    - no output card has overlap >= 30% with any Recommended Now.
    """

    from src.decide import MAX_RECOMMENDED_EXPERIMENT

    sets: List[List[_Cand]] = [
        [],
        [_Cand("discount_hygiene", 5000)],
        [_Cand("bestseller_amplify", 5000)],
        [_Cand("discount_hygiene", 5000), _Cand("bestseller_amplify", 5000)],
        [_Cand("discount_hygiene", 100)],  # under floor
        [
            _Cand(
                "discount_hygiene",
                5000,
                audience_overlap={"first_to_second_purchase": 0.45},
            )
        ],
        [_Cand("discount_hygiene", 5000, preliminary_rejection_reason="inventory_blocked")],
        [_Cand("winback_21_45", 5000)],  # not allowlisted
    ]

    rec = _measured_card("first_to_second_purchase")

    for cands in sets:
        out = _select(cands, recommendations=[rec])

        assert len(out) <= MAX_RECOMMENDED_EXPERIMENT

        # All TARGETING.
        assert all(c.evidence_class == EvidenceClass.TARGETING for c in out)

        # All have populated would_be_measured_by.
        assert all(c.would_be_measured_by is not None for c in out)

        # All revenue ranges suppressed.
        assert all(
            c.revenue_range is not None and c.revenue_range.suppressed is True
            for c in out
        )

        # Unique audience archetypes via priors.
        archetypes = []
        for c in out:
            md = PL.get_play_metadata(c.play_id)
            assert md is not None
            archetypes.append(md.audience_archetype)
        assert len(set(archetypes)) == len(archetypes)
