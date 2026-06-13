"""Phase 6A Ticket B1.5 — Recommended Experiment opportunity_context tests.

Pin the contract that ``_select_recommended_experiments`` populates
``opportunity_context`` on every Recommended Experiment PlayCard when a
defensible store-observed AOV is available, and omits it (None) when it
is not. The math is the same Phase 5.1 formula
(``audience_size * aov``) used by the Phase 5.6 directional path; no new
math, no causal priors, no multipliers.

Hard rules under test:

- AOV source/window is identical to the Phase 5.1 path
  (``kpi_snapshot_with_deltas[L28].aov`` with L56/L90 fallback).
- ``opportunity_context.non_lift.value == audience_size * aov_used`` (S13.6-T3).
- ``opportunity_context.aov_source == "store_observed"``.
- ``opportunity_context.aov_window`` is the resolved window label.
- When AOV is missing (no aligned, empty aligned, missing window, NaN,
  zero), ``opportunity_context is None``.
- ``revenue_range.suppressed=True`` remains unchanged on every
  experiment card regardless of opportunity_context state.

This file is the red-first forcing function for B1.5. Pre-fix, every
test that asserts ``opportunity_context`` is populated by the real
selector MUST fail because the A4 selector does not stamp the field.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import priors_loader as PL
from src.engine_run import (
    Audience,
    BriefingMeta,
    DecisionState,
    EngineRun,
    EvidenceClass,
    PlayCard,
    RevenueRange,
    WouldBeMeasuredBy,
)


@pytest.fixture(autouse=True)
def _reset_priors_cache():
    PL.clear_cache()
    yield
    PL.clear_cache()


# ---------------------------------------------------------------------------
# Light Candidate stand-in (matches the surface used by the real selector).
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


def _aligned_with_aov(aov: float, *, window: str = "L28") -> Dict[str, Any]:
    """Build an aligned dict that mirrors the Phase 5.1 source shape.

    Phase 5.1 reads ``aligned[window]['aov']`` from
    ``utils.kpi_snapshot_with_deltas``. The selector must read the same
    field from the same dict.
    """
    return {window: {"aov": aov}}


def _select(
    cands,
    *,
    flag_on=True,
    decision_state=DecisionState.PUBLISH,
    vertical="beauty",
    recommendations=None,
    metadata_lookup=None,
    aligned=None,
):
    from src.decide import _select_recommended_experiments

    return _select_recommended_experiments(
        cands,
        recommendations=recommendations or [_measured_card()],
        flag_on=flag_on,
        decision_state=decision_state,
        vertical=vertical,
        metadata_lookup=metadata_lookup,
        aligned=aligned,
    )


# ---------------------------------------------------------------------------
# Direct-helper coverage on _select_recommended_experiments.
# ---------------------------------------------------------------------------


def test_real_selector_populates_opportunity_context_when_aov_available():
    """Phase 6A Ticket B1.5 — when ``aligned`` carries a defensible L28
    AOV, every output card must have ``opportunity_context`` populated.
    """

    aligned = _aligned_with_aov(69.0)
    cands = [
        _Cand("discount_hygiene", 2000),
        _Cand("bestseller_amplify", 1500),
    ]

    out = _select(cands, aligned=aligned)
    assert len(out) == 2
    for card in out:
        opp = card.opportunity_context
        assert opp is not None, (
            f"Expected opportunity_context on Recommended Experiment card "
            f"{card.play_id}; got None"
        )
        assert opp.audience_size == card.audience.size
        # S13.6-T3: monetary numerics live inside the NonLiftAtom wrapper.
        assert opp.non_lift.aov_used == pytest.approx(69.0)
        assert opp.non_lift.value == pytest.approx(card.audience.size * 69.0)
        assert opp.non_lift.semantic == "addressable_opportunity"
        assert opp.aov_window == "L28"
        assert opp.aov_source == "store_observed"


def test_real_selector_omits_opportunity_context_when_aligned_is_none():
    """When ``aligned`` is None (e.g. cold-start or producer fallback),
    every output card must have ``opportunity_context is None`` — the
    selector MUST NOT fabricate an addressable value."""

    cands = [_Cand("discount_hygiene", 2000)]
    out = _select(cands, aligned=None)
    assert len(out) == 1
    assert out[0].opportunity_context is None


def test_real_selector_omits_opportunity_context_when_aligned_empty():
    cands = [_Cand("discount_hygiene", 2000)]
    out = _select(cands, aligned={})
    assert len(out) == 1
    assert out[0].opportunity_context is None


def test_real_selector_omits_opportunity_context_when_aov_zero():
    """A zero AOV is not defensible. Phase 5.1's ``_resolve_aov_for_context``
    treats ``aov <= 0`` as missing; the selector must follow the same
    contract.
    """

    cands = [_Cand("discount_hygiene", 2000)]
    out = _select(cands, aligned=_aligned_with_aov(0.0))
    assert len(out) == 1
    assert out[0].opportunity_context is None


def test_real_selector_omits_opportunity_context_when_aov_nan():
    cands = [_Cand("discount_hygiene", 2000)]
    out = _select(cands, aligned=_aligned_with_aov(float("nan")))
    assert len(out) == 1
    assert out[0].opportunity_context is None


def test_real_selector_falls_back_to_l56_then_l90():
    """Same fallback chain as Phase 5.1: L28 -> L56 -> L90."""

    aligned = {
        "L28": {"aov": 0.0},  # unusable
        "L56": {"aov": 75.0},
        "L90": {"aov": 999.0},
    }
    cands = [_Cand("discount_hygiene", 2000)]
    out = _select(cands, aligned=aligned)
    assert len(out) == 1
    opp = out[0].opportunity_context
    assert opp is not None
    assert opp.non_lift.aov_used == pytest.approx(75.0)
    assert opp.aov_window == "L56"


def test_addressable_value_equals_audience_size_times_aov():
    """Pin the math: ``audience_size * aov`` exactly, no multipliers."""

    aov = 49.50
    audience = 3217
    aligned = _aligned_with_aov(aov)
    cands = [_Cand("discount_hygiene", audience)]
    out = _select(cands, aligned=aligned)
    assert len(out) == 1
    opp = out[0].opportunity_context
    assert opp is not None
    # S13.6-T3: monetary numerics live inside the NonLiftAtom wrapper.
    assert opp.non_lift.value == pytest.approx(float(audience) * aov)
    # Also pin the formula end-to-end through the audience field.
    assert opp.audience_size == audience
    assert opp.audience_size * opp.non_lift.aov_used == pytest.approx(opp.non_lift.value)


def test_aov_window_and_source_match_phase5_1_directional_builder():
    """The selector must use the same AOV source the Phase 5.6 directional
    builder uses for Recommended Now — ``kpi_snapshot_with_deltas[L28]['aov']``
    via ``measurement_builder._build_opportunity_context``. Pin via a
    differential: build a directional opportunity_context from the same
    aligned dict via the public Phase 5.1 helper, then compare to the
    selector output.
    """

    from src.measurement_builder import _build_opportunity_context

    aov = 88.0
    audience = 2000
    aligned = _aligned_with_aov(aov)

    expected = _build_opportunity_context(audience, aligned, primary_window="L28")
    assert expected is not None  # sanity for the comparator

    cands = [_Cand("discount_hygiene", audience)]
    out = _select(cands, aligned=aligned)
    assert len(out) == 1
    actual = out[0].opportunity_context
    assert actual is not None
    assert actual.aov_window == expected.aov_window
    assert actual.aov_source == expected.aov_source
    assert actual.non_lift.aov_used == pytest.approx(expected.non_lift.aov_used)
    assert actual.non_lift.value == pytest.approx(expected.non_lift.value)


# ---------------------------------------------------------------------------
# revenue_range.suppressed invariant.
# ---------------------------------------------------------------------------


def test_revenue_range_remains_suppressed_after_opportunity_context_added_aov_present():
    aligned = _aligned_with_aov(69.0)
    cands = [_Cand("discount_hygiene", 2000), _Cand("bestseller_amplify", 1500)]
    out = _select(cands, aligned=aligned)
    assert len(out) == 2
    for card in out:
        assert card.revenue_range is not None
        assert card.revenue_range.suppressed is True
        # Drivers preserve the experiment-suppression rationale.
        drivers = card.revenue_range.drivers or []
        assert any(
            (d or {}).get("reason") == "experiment_no_calibrated_lift"
            for d in drivers
        )


def test_revenue_range_remains_suppressed_after_opportunity_context_added_aov_missing():
    cands = [_Cand("discount_hygiene", 2000)]
    out = _select(cands, aligned=None)
    assert len(out) == 1
    card = out[0]
    assert card.opportunity_context is None
    assert card.revenue_range is not None
    assert card.revenue_range.suppressed is True


# ---------------------------------------------------------------------------
# decide() plumbing: ``aligned`` flows from kwarg through to the selector.
# ---------------------------------------------------------------------------


def test_decide_plumbs_aligned_into_selector_when_slate_flag_on():
    """When ``decide()`` is called with ``aligned=...``, the selector
    receives it and stamps ``opportunity_context`` on every output card.
    """

    from src.decide import decide

    aligned = _aligned_with_aov(69.0)
    cands = [
        _Cand("discount_hygiene", 5000),
        _Cand("bestseller_amplify", 5000),
    ]
    run = EngineRun(
        recommendations=[_measured_card()],
        briefing_meta=BriefingMeta(vertical="beauty"),
    )

    out = decide(
        run,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
        aligned=aligned,
    )
    assert len(out.recommended_experiments) == 2
    for card in out.recommended_experiments:
        opp = card.opportunity_context
        assert opp is not None
        assert opp.non_lift.aov_used == pytest.approx(69.0)
        assert opp.non_lift.value == pytest.approx(card.audience.size * 69.0)


def test_decide_with_no_aligned_kwarg_omits_opportunity_context():
    """Default ``aligned=None`` mirrors callers that have not yet been
    plumbed; the selector must omit ``opportunity_context`` rather than
    raise.
    """

    from src.decide import decide

    cands = [_Cand("discount_hygiene", 5000)]
    run = EngineRun(
        recommendations=[_measured_card()],
        briefing_meta=BriefingMeta(vertical="beauty"),
    )
    out = decide(
        run,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert len(out.recommended_experiments) == 1
    assert out.recommended_experiments[0].opportunity_context is None


def test_decide_flag_off_keeps_recommended_experiments_empty_even_with_aligned():
    """Flag-off invariant: passing ``aligned`` with the slate flag off
    must NOT silently surface experiments.
    """

    from src.decide import decide

    aligned = _aligned_with_aov(69.0)
    cands = [_Cand("discount_hygiene", 5000)]
    run = EngineRun(
        recommendations=[_measured_card()],
        briefing_meta=BriefingMeta(vertical="beauty"),
    )
    out = decide(
        run,
        cfg={"ENGINE_V2_SLATE": False, "VERTICAL_MODE": "beauty"},
        candidates=cands,
        aligned=aligned,
    )
    assert out.recommended_experiments == []


# ---------------------------------------------------------------------------
# End-to-end render: when the real selector populates opportunity_context,
# the renderer's already-implemented block must surface it.
# ---------------------------------------------------------------------------


def test_render_surfaces_opportunity_context_from_real_selector():
    """End-to-end: build an EngineRun, call decide() with aligned, render
    the result, assert the opportunity-context block renders the
    addressable-value sentence and the negation disclaimer.
    """

    from src.decide import decide
    from src.engine_run import DataWindow, Scale
    from src.storytelling_v2 import (
        OPPORTUNITY_CONTEXT_CLASS,
        OPPORTUNITY_CONTEXT_DISCLAIMER,
        render_engine_run,
    )

    aligned = _aligned_with_aov(69.0)
    cands = [_Cand("discount_hygiene", 1500), _Cand("bestseller_amplify", 800)]
    run = EngineRun(
        store_id="b1_5_test",
        anchor_date="2026-04-30T00:00:00",
        data_window=DataWindow(primary_window="L28"),
        recommendations=[_measured_card()],
        scale=Scale(monthly_revenue=200_000.0, materiality_floor=10_000.0),
        briefing_meta=BriefingMeta(vertical="beauty"),
    )
    out = decide(
        run,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
        aligned=aligned,
    )
    assert len(out.recommended_experiments) == 2

    html = render_engine_run(out)

    # The block class appears for each experiment card.
    assert html.count(f'"{OPPORTUNITY_CONTEXT_CLASS}"') >= 2
    # The disclaimer appears for each experiment card (the directional /
    # measured cards above the slate may also render their own copy; we
    # just assert it appears at least twice for the two experiment cards).
    assert html.count(OPPORTUNITY_CONTEXT_DISCLAIMER) >= 2
    # Audience x AOV sentence appears.
    assert "1,500" in html or "1500" in html
    assert "$69" in html


def test_render_no_opportunity_context_block_when_aligned_missing():
    """When ``decide()`` is called WITHOUT ``aligned``, the renderer's
    opportunity-context block on experiment cards must NOT render.
    """

    from src.decide import decide
    from src.engine_run import DataWindow, Scale
    from src.storytelling_v2 import (
        OPPORTUNITY_CONTEXT_CLASS,
        render_engine_run,
    )

    cands = [_Cand("discount_hygiene", 1500)]
    run = EngineRun(
        store_id="b1_5_test_no_aov",
        anchor_date="2026-04-30T00:00:00",
        data_window=DataWindow(primary_window="L28"),
        recommendations=[_measured_card()],
        scale=Scale(monthly_revenue=200_000.0, materiality_floor=10_000.0),
        briefing_meta=BriefingMeta(vertical="beauty"),
    )
    out = decide(
        run,
        cfg={"ENGINE_V2_SLATE": True, "VERTICAL_MODE": "beauty"},
        candidates=cands,
    )
    assert len(out.recommended_experiments) == 1
    assert out.recommended_experiments[0].opportunity_context is None

    html = render_engine_run(out)
    # The Recommended Experiment section is present.
    assert 'class="recommended-experiment"' in html
    # But the opportunity-context block must not render on the experiment
    # card. The directional Recommended Now card above may still render
    # one if its own opportunity_context is populated; we scope by extracting
    # the experiment section.
    section_match = re.search(
        r'<section class="recommended-experiment".*?</section>', html, re.DOTALL
    )
    assert section_match is not None
    section_html = section_match.group(0)
    assert OPPORTUNITY_CONTEXT_CLASS not in section_html
