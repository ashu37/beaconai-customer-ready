"""Phase 6A Ticket B5 — Recommended Experiment cannibalization gate tests.

This file pins the cannibalization gate that protects Recommended Now
(Recommended) cards from being shadowed by Recommended Experiment cards
that target heavily overlapping audiences.

Contract (per ``agent_outputs/campaign-slate-contract-final.md`` and
``agent_outputs/implementation-manager-campaign-slate-plan.md`` Ticket
B5):

1.  Threshold: ``RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD = 0.30``
    (Jaccard / pairwise audience-overlap fraction).
2.  A candidate is **eligible** iff its overlap with EVERY Recommended
    Now card is strictly less than 0.30.
3.  29% overlap survives. 30% or 31% overlap is excluded.
4.  Overlap is checked pairwise against EVERY Recommended Now card,
    not just the first one.
5.  A demoted candidate's ``play_id`` does NOT appear in
    ``recommended_experiments``.
6.  Under PUBLISH the cap remains <= 2 and role-uniqueness across
    ``recommendations`` / ``recommended_experiments`` / ``considered``
    is preserved.
7.  Demoted experiment-side candidates that already surface in
    ``considered`` (e.g. via the upstream Phase 5.2 candidate-routing)
    keep their typed reason; B5 does NOT fabricate a new
    ``ReasonCode.AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY`` entry under
    PUBLISH today (see ``Demotion routing`` notes below). Tests
    document the current behavior so a future agent can tighten this
    intentionally rather than by accident.

Demotion routing (current behavior):
    The selector excludes overlap-heavy candidates by short-circuit and
    does NOT itself append a Considered entry. Under PUBLISH, the
    upstream ``populate_considered_from_candidates`` path stamps the
    candidate with its prelim reason / registry default, so the play
    will typically surface in Considered through that path. Under
    ABSTAIN_SOFT, the publish-shadow B3 routing only catches
    publish-eligible candidates, so an overlap-heavy candidate will
    NOT route via B3 either.

The contract guidance for B5 says: "If current architecture cannot
route these without broad changes, document and keep B5 as
selection-hardening only." This file follows that guidance — the
demotion behavior is selection-hardening (no route into Considered
with a new typed reason at the selector seam), and the routing-side
tests document the structural behavior rather than asserting a new
reason code.
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
    RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD,
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
)


@pytest.fixture(autouse=True)
def _reset_priors_cache():
    PL.clear_cache()
    yield
    PL.clear_cache()


# ---------------------------------------------------------------------------
# Light Candidate stand-in (matches the duck-typed contract the selector
# expects: play_id, audience_size, segment_definition,
# preliminary_rejection_reason, audience_overlap).
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
# Threshold sentinels: 29% allowed, 30% rejected, 31% rejected.
# ---------------------------------------------------------------------------


def test_threshold_constant_is_30pct():
    assert RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD == 0.30


def test_candidate_with_29pct_overlap_survives():
    rec = _rec_card("first_to_second_purchase")
    cand = _Cand(
        "discount_hygiene",
        5000,
        audience_overlap={"first_to_second_purchase": 0.29},
    )
    out = _select([cand], recommendations=[rec])
    assert len(out) == 1
    assert out[0].play_id == "discount_hygiene"


def test_candidate_with_exactly_30pct_overlap_is_demoted():
    """The threshold is strict: ``overlap >= 0.30`` rejects."""

    rec = _rec_card("first_to_second_purchase")
    cand = _Cand(
        "discount_hygiene",
        5000,
        audience_overlap={"first_to_second_purchase": 0.30},
    )
    out = _select([cand], recommendations=[rec])
    assert out == []


def test_candidate_with_31pct_overlap_is_demoted():
    rec = _rec_card("first_to_second_purchase")
    cand = _Cand(
        "discount_hygiene",
        5000,
        audience_overlap={"first_to_second_purchase": 0.31},
    )
    out = _select([cand], recommendations=[rec])
    assert out == []


def test_candidate_with_50pct_overlap_is_demoted():
    rec = _rec_card("first_to_second_purchase")
    cand = _Cand(
        "discount_hygiene",
        5000,
        audience_overlap={"first_to_second_purchase": 0.50},
    )
    out = _select([cand], recommendations=[rec])
    assert out == []


def test_candidate_with_zero_overlap_survives():
    """Explicit zero overlap is well below threshold and must survive."""

    rec = _rec_card("first_to_second_purchase")
    cand = _Cand(
        "discount_hygiene",
        5000,
        audience_overlap={"first_to_second_purchase": 0.0},
    )
    out = _select([cand], recommendations=[rec])
    assert len(out) == 1


def test_candidate_with_missing_overlap_entry_treated_as_zero():
    """If the candidate's overlap map has no entry for a Recommended Now
    play_id, the selector treats the overlap as 0.0 (permissive, current
    behavior). Test pinned so any tightening of this default is
    intentional.
    """

    rec = _rec_card("first_to_second_purchase")
    cand = _Cand("discount_hygiene", 5000, audience_overlap={})
    out = _select([cand], recommendations=[rec])
    assert len(out) == 1


# ---------------------------------------------------------------------------
# Pairwise check: overlap must be checked against EVERY Recommended Now
# card, not just the first one.
# ---------------------------------------------------------------------------


def test_overlap_checked_against_every_recommended_now_card_first_one_overlaps():
    """Two Recommended Now cards. Candidate overlaps the first one above
    threshold; it must be demoted regardless of low overlap with the
    second.
    """

    rec1 = _rec_card("first_to_second_purchase")
    rec2 = _rec_card("winback_21_45")
    cand = _Cand(
        "discount_hygiene",
        5000,
        audience_overlap={
            "first_to_second_purchase": 0.45,
            "winback_21_45": 0.05,
        },
    )
    out = _select([cand], recommendations=[rec1, rec2])
    assert out == []


def test_overlap_checked_against_every_recommended_now_card_second_one_overlaps():
    """Same setup but the OFFENDING overlap is on the SECOND Recommended
    Now card. The selector must still reject — checking only the first
    card would let this candidate through.
    """

    rec1 = _rec_card("first_to_second_purchase")
    rec2 = _rec_card("winback_21_45")
    cand = _Cand(
        "discount_hygiene",
        5000,
        audience_overlap={
            "first_to_second_purchase": 0.05,
            "winback_21_45": 0.45,
        },
    )
    out = _select([cand], recommendations=[rec1, rec2])
    assert out == []


def test_overlap_checked_against_every_recommended_now_card_third_one_overlaps():
    """Three Recommended Now cards. Candidate overlaps the third one
    only. Selector must still reject.
    """

    rec1 = _rec_card("first_to_second_purchase")
    rec2 = _rec_card("winback_21_45")
    rec3 = _rec_card("subscription_nudge")
    cand = _Cand(
        "discount_hygiene",
        5000,
        audience_overlap={
            "first_to_second_purchase": 0.10,
            "winback_21_45": 0.10,
            "subscription_nudge": 0.40,
        },
    )
    out = _select([cand], recommendations=[rec1, rec2, rec3])
    assert out == []


def test_candidate_below_threshold_against_all_recommended_now_cards_survives():
    rec1 = _rec_card("first_to_second_purchase")
    rec2 = _rec_card("winback_21_45")
    cand = _Cand(
        "discount_hygiene",
        5000,
        audience_overlap={
            "first_to_second_purchase": 0.10,
            "winback_21_45": 0.20,
        },
    )
    out = _select([cand], recommendations=[rec1, rec2])
    assert len(out) == 1
    assert out[0].play_id == "discount_hygiene"


# ---------------------------------------------------------------------------
# Cap and role-uniqueness invariants under cannibalization.
# ---------------------------------------------------------------------------


def test_cap_preserved_under_overlap_demotion():
    """One allowlisted candidate is demoted by overlap; the other
    survives. Output cap remains <= 2 and the demoted candidate is
    excluded.
    """

    rec = _rec_card("first_to_second_purchase")
    cands = [
        _Cand(
            "discount_hygiene",
            5000,
            audience_overlap={"first_to_second_purchase": 0.45},
        ),
        _Cand(
            "bestseller_amplify",
            5000,
            audience_overlap={"first_to_second_purchase": 0.05},
        ),
    ]
    out = _select(cands, recommendations=[rec])
    assert len(out) == 1
    assert out[0].play_id == "bestseller_amplify"
    assert len(out) <= MAX_RECOMMENDED_EXPERIMENT


def test_no_duplicate_play_id_across_roles_under_cannibalization_demotion():
    """End-to-end ``decide()`` call: a candidate that gets demoted by
    overlap must not appear in both roles. The post-decide EngineRun
    must satisfy the role-uniqueness invariant.
    """

    cands = [
        _Cand(
            "discount_hygiene",
            5000,
            audience_overlap={"first_to_second_purchase": 0.45},
        ),
        _Cand(
            "bestseller_amplify",
            5000,
            audience_overlap={"first_to_second_purchase": 0.10},
        ),
    ]
    run = EngineRun(
        recommendations=[_rec_card("first_to_second_purchase")],
        briefing_meta=BriefingMeta(vertical="beauty"),
    )
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
    # The demoted play must not appear in recommended_experiments.
    assert "discount_hygiene" not in exp_ids


# ---------------------------------------------------------------------------
# Demotion routing notes: pin current behavior. The selector excludes
# overlap-heavy candidates by short-circuit and does NOT itself stamp a
# new typed Considered reason.
# ---------------------------------------------------------------------------


def test_overlap_demoted_candidate_excluded_from_recommended_experiments():
    """The selector excludes the demoted candidate. This is the
    selection-hardening contract for B5; routing into Considered with a
    new typed reason code is documented as out-of-scope (the existing
    upstream candidate-routing path handles surfacing it through the
    Considered list when applicable).
    """

    rec = _rec_card("first_to_second_purchase")
    cand = _Cand(
        "discount_hygiene",
        5000,
        audience_overlap={"first_to_second_purchase": 0.50},
    )
    out = _select([cand], recommendations=[rec])
    assert all(c.play_id != "discount_hygiene" for c in out)


# ---------------------------------------------------------------------------
# Property-style invariants over randomized candidate sets.
# ---------------------------------------------------------------------------


def test_property_no_output_overlaps_recommended_now_above_threshold():
    """For any randomized candidate set, the selector output:

    - has at most ``MAX_RECOMMENDED_EXPERIMENT`` cards;
    - never includes a candidate whose overlap with any Recommended Now
      play_id is ``>= RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD``.
    """

    rng = random.Random(20260505)
    rec_play_ids = ["first_to_second_purchase", "winback_21_45"]
    recs = [_rec_card(pid) for pid in rec_play_ids]
    allow = ["discount_hygiene", "bestseller_amplify"]

    for _ in range(64):
        n = rng.randint(0, 4)
        cands: List[_Cand] = []
        for _i in range(n):
            pid = rng.choice(allow)
            audience = rng.randint(100, 9000)
            overlap_map = {
                rpid: round(rng.random(), 4) for rpid in rec_play_ids
            }
            cands.append(
                _Cand(
                    pid,
                    audience,
                    audience_overlap=overlap_map,
                )
            )
        out = _select(cands, recommendations=recs)
        assert len(out) <= MAX_RECOMMENDED_EXPERIMENT

        # Every output card's source candidate (matched on play_id) must
        # have all overlaps strictly below the threshold against every
        # Recommended Now play_id.
        for card in out:
            # Find any candidate matching this play_id; if multiple
            # candidates share a play_id, the selector picks one
            # deterministically — for the purpose of this property test
            # it is enough to require that AT LEAST ONE matching
            # candidate satisfies the overlap rule (the one the selector
            # actually picked).
            matching = [c for c in cands if c.play_id == card.play_id]
            ok = False
            for mc in matching:
                violations = [
                    mc.audience_overlap.get(rpid, 0.0)
                    for rpid in rec_play_ids
                ]
                if all(
                    v < RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD
                    for v in violations
                ):
                    ok = True
                    break
            assert ok, (
                f"output card {card.play_id} has no source candidate with "
                f"all overlaps < {RECOMMENDED_EXPERIMENT_OVERLAP_THRESHOLD}; "
                f"matching={[mc.audience_overlap for mc in matching]}"
            )
