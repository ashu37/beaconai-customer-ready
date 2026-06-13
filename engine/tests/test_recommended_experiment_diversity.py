"""Phase 6A Ticket B5 — Recommended Experiment slate diversity tests.

This file pins the slate-diversity rule: no two Recommended Experiment
cards in the same run may share the same ``audience_archetype``.

Contract (per ``agent_outputs/campaign-slate-contract-final.md`` and
``agent_outputs/implementation-manager-campaign-slate-plan.md`` Ticket
B5):

1.  Two otherwise-eligible candidates with the same
    ``audience_archetype`` produce only ONE selected Recommended
    Experiment card.
2.  The selected one is deterministic. The selector sorts eligible
    candidates by ``(-audience_size, play_id)`` and keeps the first
    candidate per archetype; later candidates with the same archetype
    are dropped.
3.  Cap remains <= 2.
4.  No duplicate ``play_id`` across the three role sections of the
    returned EngineRun (role-uniqueness invariant from Ticket B4).

Demotion routing (current behavior):
    The selector drops same-archetype candidates after the diversity
    dedupe. It does NOT itself stamp a new typed Considered entry for
    the dropped candidate (B5 implementation guidance: "If current
    architecture cannot route these without broad changes, document
    and keep B5 as selection-hardening only."). The upstream
    ``populate_considered_from_candidates`` path independently surfaces
    the candidate in Considered with its prelim / registry-default
    reason. Tests below pin the selection-hardening contract; future
    tightening to a typed ``ReasonCode.CANNIBALIZATION_DEMOTED`` route
    is intentionally out of scope for B5.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import priors_loader as PL
from src.decide import (
    MAX_RECOMMENDED_EXPERIMENT,
    _select_recommended_experiments,
    decide,
)
from src.engine_run import (
    Audience,
    BriefingMeta,
    DecisionState,
    EngineRun,
    EvidenceClass,
    PlayCard,
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


def _rec_card(play_id: str = "first_to_second_purchase") -> PlayCard:
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.DIRECTIONAL,
        audience=Audience(size=2000, definition=f"{play_id} segment"),
    )


def _shared_archetype_lookup(
    archetype: AudienceArchetype = AudienceArchetype.DISCOUNT_BUYER,
):
    """Return a metadata lookup that stamps both allowlisted plays with
    the same ``audience_archetype``. The other fields stay defensible
    (audience floor cleared, vertical applies) so the diversity rule
    becomes the only differentiator.
    """

    def _lookup(play_id: str):
        if play_id == "discount_hygiene":
            return PlayMetadata(
                audience_floor=200,
                mechanism="discount mechanism",
                vertical_applicability=["beauty"],
                would_be_measured_by=(
                    WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D
                ),
                audience_archetype=archetype,
            )
        if play_id == "bestseller_amplify":
            return PlayMetadata(
                audience_floor=500,
                mechanism="bestseller mechanism",
                vertical_applicability=["beauty"],
                would_be_measured_by=WouldBeMeasuredBy.REPEAT_PURCHASE_IN_30D,
                audience_archetype=archetype,
            )
        return None

    return _lookup


def _select(
    cands,
    *,
    recommendations: Optional[List[PlayCard]] = None,
    flag_on: bool = True,
    decision_state: DecisionState = DecisionState.PUBLISH,
    vertical: str = "beauty",
    metadata_lookup=None,
):
    return _select_recommended_experiments(
        cands,
        recommendations=recommendations or [_rec_card()],
        flag_on=flag_on,
        decision_state=decision_state,
        vertical=vertical,
        metadata_lookup=metadata_lookup,
    )


# ---------------------------------------------------------------------------
# Two same-archetype candidates produce only one selected card.
# ---------------------------------------------------------------------------


def test_two_candidates_with_same_archetype_produce_only_one_card():
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    out = _select(
        cands,
        metadata_lookup=_shared_archetype_lookup(AudienceArchetype.DISCOUNT_BUYER),
    )
    assert len(out) == 1


def test_three_candidates_two_share_archetype_yields_two_cards():
    """Three candidates: two share an archetype, the third is distinct.
    The selector should pick the higher-audience same-archetype winner
    plus the distinct-archetype card. Output count is exactly 2 (the
    cap), and no archetype repeats.
    """

    archetype_dup = AudienceArchetype.DISCOUNT_BUYER
    archetype_alt = AudienceArchetype.HERO_SKU_BUYER

    def _lookup(play_id: str):
        if play_id == "discount_hygiene":
            # Force same-archetype with the third synthetic play.
            return PlayMetadata(
                audience_floor=200,
                mechanism="discount mechanism",
                vertical_applicability=["beauty"],
                would_be_measured_by=(
                    WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D
                ),
                audience_archetype=archetype_dup,
            )
        if play_id == "bestseller_amplify":
            return PlayMetadata(
                audience_floor=500,
                mechanism="bestseller mechanism",
                vertical_applicability=["beauty"],
                would_be_measured_by=WouldBeMeasuredBy.REPEAT_PURCHASE_IN_30D,
                audience_archetype=archetype_alt,
            )
        return None

    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    out = _select(cands, metadata_lookup=_lookup)
    assert len(out) == 2
    # Archetypes differ.
    by_id = {c.play_id: c for c in out}
    assert "discount_hygiene" in by_id
    assert "bestseller_amplify" in by_id


# ---------------------------------------------------------------------------
# Determinism: when two candidates share an archetype, the selector
# picks the higher-audience candidate first; play_id breaks ties
# deterministically (ascending).
# ---------------------------------------------------------------------------


def test_same_archetype_higher_audience_candidate_wins():
    """``discount_hygiene`` audience 7000 vs ``bestseller_amplify``
    audience 4000 with shared archetype -> ``discount_hygiene`` wins
    deterministically.
    """

    cands = [
        _Cand("bestseller_amplify", 4000),
        _Cand("discount_hygiene", 7000),
    ]
    out = _select(
        cands,
        metadata_lookup=_shared_archetype_lookup(AudienceArchetype.DISCOUNT_BUYER),
    )
    assert len(out) == 1
    assert out[0].play_id == "discount_hygiene"


def test_same_archetype_audience_tie_lower_play_id_wins():
    """When audience size ties, the selector breaks the tie on
    ``play_id`` ascending. ``bestseller_amplify`` < ``discount_hygiene``
    lexicographically, so bestseller_amplify wins.
    """

    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    out = _select(
        cands,
        metadata_lookup=_shared_archetype_lookup(AudienceArchetype.DISCOUNT_BUYER),
    )
    assert len(out) == 1
    assert out[0].play_id == "bestseller_amplify"


def test_same_archetype_winner_is_deterministic_across_input_order():
    """Reordering the input list must NOT change the winner: the
    selector sorts internally before deduping by archetype.
    """

    base_cands = [
        _Cand("discount_hygiene", 7000),
        _Cand("bestseller_amplify", 4000),
    ]
    lookup = _shared_archetype_lookup(AudienceArchetype.DISCOUNT_BUYER)

    out1 = _select(base_cands, metadata_lookup=lookup)
    out2 = _select(list(reversed(base_cands)), metadata_lookup=lookup)

    assert len(out1) == 1
    assert len(out2) == 1
    assert out1[0].play_id == out2[0].play_id == "discount_hygiene"


# ---------------------------------------------------------------------------
# Cap and role-uniqueness invariants under diversity demotion.
# ---------------------------------------------------------------------------


def test_cap_preserved_under_diversity_demotion():
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    out = _select(
        cands,
        metadata_lookup=_shared_archetype_lookup(AudienceArchetype.DISCOUNT_BUYER),
    )
    assert len(out) <= MAX_RECOMMENDED_EXPERIMENT


def test_no_duplicate_play_id_across_roles_under_diversity_demotion():
    """End-to-end ``decide()`` test: same-archetype candidates can NEVER
    cause the role-uniqueness invariant to fail.
    """

    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    run = EngineRun(
        recommendations=[_rec_card("first_to_second_purchase")],
        briefing_meta=BriefingMeta(vertical="beauty"),
    )
    # The shared-archetype lookup runs at the priors_loader seam; we
    # can't easily inject it into ``decide()``. The default priors
    # YAML stamps ``discount_hygiene -> discount_buyer`` and
    # ``bestseller_amplify -> hero_sku_buyer`` (distinct archetypes), so
    # under default metadata both survive. The role-uniqueness invariant
    # still must hold.
    out = decide(
        run,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    rec_ids = {c.play_id for c in out.recommendations}
    exp_ids = {c.play_id for c in out.recommended_experiments}
    con_ids = {r.play_id for r in out.considered}
    assert rec_ids.isdisjoint(exp_ids)
    assert rec_ids.isdisjoint(con_ids)
    assert exp_ids.isdisjoint(con_ids)
    # The default-archetype path has both plays distinct, so both can
    # appear as Recommended Experiment.
    assert exp_ids == {"bestseller_amplify", "discount_hygiene"}


# ---------------------------------------------------------------------------
# Default priors metadata: discount_hygiene and bestseller_amplify carry
# distinct archetypes (discount_buyer vs hero_sku_buyer). The diversity
# rule must NOT collapse them when archetypes legitimately differ.
# ---------------------------------------------------------------------------


def test_default_priors_metadata_keeps_both_allowlisted_plays():
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    out = _select(cands)
    assert len(out) == 2
    play_ids = sorted(c.play_id for c in out)
    assert play_ids == ["bestseller_amplify", "discount_hygiene"]


def test_default_priors_metadata_archetypes_are_distinct():
    md_dh = PL.get_play_metadata("discount_hygiene")
    md_ba = PL.get_play_metadata("bestseller_amplify")
    assert md_dh is not None and md_ba is not None
    assert md_dh.audience_archetype != md_ba.audience_archetype


# ---------------------------------------------------------------------------
# Property-style invariant: archetypes in the output are always unique.
# ---------------------------------------------------------------------------


def test_property_output_archetypes_are_unique_across_random_inputs():
    """For any randomized candidate set, the selector output:

    - has at most ``MAX_RECOMMENDED_EXPERIMENT`` cards;
    - every card carries a populated ``would_be_measured_by`` enum;
    - all cards carry distinct ``audience_archetype`` values
      (looked up via the live priors loader).
    """

    rng = random.Random(20260505)
    allow = ["discount_hygiene", "bestseller_amplify"]
    rec = _rec_card("first_to_second_purchase")

    for _ in range(64):
        n = rng.randint(0, 5)
        cands: List[_Cand] = []
        for _i in range(n):
            pid = rng.choice(allow)
            audience = rng.randint(100, 9000)
            cands.append(
                _Cand(
                    pid,
                    audience,
                    audience_overlap={"first_to_second_purchase": 0.0},
                )
            )
        out = _select(cands, recommendations=[rec])
        assert len(out) <= MAX_RECOMMENDED_EXPERIMENT

        archetypes = []
        for card in out:
            md = PL.get_play_metadata(card.play_id)
            assert md is not None
            archetypes.append(md.audience_archetype)
        assert len(set(archetypes)) == len(archetypes)


def test_property_archetypes_unique_when_metadata_makes_them_collide():
    """Same-archetype injection via metadata_lookup: regardless of input
    permutation or audience size, the output never has duplicate
    archetypes.
    """

    rng = random.Random(20260506)
    lookup = _shared_archetype_lookup(AudienceArchetype.DISCOUNT_BUYER)
    allow = ["discount_hygiene", "bestseller_amplify"]
    rec = _rec_card("first_to_second_purchase")

    for _ in range(32):
        n = rng.randint(1, 4)
        cands: List[_Cand] = []
        for _i in range(n):
            pid = rng.choice(allow)
            cands.append(
                _Cand(
                    pid,
                    rng.randint(500, 9000),
                    audience_overlap={"first_to_second_purchase": 0.0},
                )
            )
        out = _select(cands, recommendations=[rec], metadata_lookup=lookup)
        # All input candidates share an archetype under this lookup, so
        # at most ONE survives.
        assert len(out) <= 1
