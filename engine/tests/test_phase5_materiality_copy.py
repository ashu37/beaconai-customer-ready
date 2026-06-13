"""Phase 5.4 — Make materiality footer merchant-readable.

The V2 briefing must NOT show the engineering string "Materiality floor:
$10,000". It must either explain the threshold in merchant English or
hide it. Internal `debug.html` may still show the exact numeric value
for engineering review.
"""
from __future__ import annotations

from src.debug_renderer import render_debug_html
from src.engine_run import (
    Abstain,
    DecisionState,
    EngineRun,
    Scale,
)
from src.storytelling_v2 import render_engine_run


def _engine_run_with_floor(floor: float = 10_000.0) -> EngineRun:
    return EngineRun(
        store_id="phase5",
        scale=Scale(monthly_revenue=120_000.0, materiality_floor=floor),
        abstain=Abstain(state=DecisionState.ABSTAIN_SOFT),
        recommendations=[],
    )


def test_v2_briefing_does_not_show_raw_materiality_floor_jargon():
    er = _engine_run_with_floor(10_000.0)
    html = render_engine_run(er)
    assert "Materiality floor:" not in html
    assert "Materiality floor: $10,000" not in html


def test_v2_briefing_explains_materiality_threshold_in_merchant_language():
    er = _engine_run_with_floor(10_000.0)
    html = render_engine_run(er)
    # Merchant-readable copy includes the dollar amount inline so the
    # merchant sees the actual floor number, but framed as a sentence.
    assert "We only recommend primary plays" in html
    assert "$10,000" in html
    assert "for a store your size" in html


def test_v2_briefing_hides_materiality_floor_when_scale_unset():
    er = EngineRun(
        store_id="phase5",
        scale=Scale(monthly_revenue=120_000.0, materiality_floor=None),
        abstain=Abstain(state=DecisionState.ABSTAIN_SOFT),
    )
    html = render_engine_run(er)
    # When the floor is None, neither the jargon string nor the
    # explanation should render.
    assert "Materiality floor" not in html
    assert "We only recommend primary plays" not in html


def test_debug_html_still_shows_exact_internal_materiality_floor():
    """Phase 5.4 contract: internal debug.html still surfaces the raw
    numeric floor for engineering review."""
    er = _engine_run_with_floor(10_000.0)
    debug_html = render_debug_html(er)
    assert "materiality_floor" in debug_html
    assert "$10,000" in debug_html
