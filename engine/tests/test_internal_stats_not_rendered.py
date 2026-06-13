"""Internal stats appear in receipts/debug.html but NOT in briefing.html.

Hard contract for M9 (T9.5):

- ``receipts/debug.html`` is merchant-INVISIBLE. It MAY contain
  ``p_internal``, ``ci_internal``, ``observed_effect``, ``n``, drivers,
  suppression reasons.
- ``briefing.html`` is merchant-FACING. It MUST NOT contain
  ``p_internal``, ``ci_internal``, ``p =``, ``q =``, ``confidence_score``,
  or ``final_score``.
- The debug page MUST NOT be linked from ``briefing.html``.
"""

from __future__ import annotations

from src.engine_run import (
    Abstain,
    Audience,
    DataQualityFlag,
    DataWindow,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Measurement,
    Observation,
    ObservationClassification,
    PlayCard,
    ReasonCode,
    RejectedPlay,
    RevenueRange,
    RevenueRangeSource,
    Scale,
    WatchedSignal,
)
from src.debug_renderer import INTERNAL_BANNER, render_debug_html
from src.storytelling_v2 import render_engine_run


# ---------------------------------------------------------------------------
# Fixture EngineRun with measured + targeting plays
# ---------------------------------------------------------------------------


def _measured_card() -> PlayCard:
    return PlayCard(
        play_id="winback_21_45",
        evidence_class=EvidenceClass.MEASURED,
        confidence_label="Strong",
        audience=Audience(id="winback_21_45_inactive", definition="Inactive 21-45d", size=412),
        measurement=Measurement(
            metric="reactivation_rate",
            observed_effect=0.12,
            n=412,
            primary_window="L28",
            consistency_across_windows=2,
            p_internal=0.014,
            ci_internal=[0.04, 0.20],
        ),
        revenue_range=RevenueRange(
            p10=2400.0,
            p50=4800.0,
            p90=7200.0,
            source=RevenueRangeSource.STORE_OBSERVED,
            drivers=[
                {"name": "audience_size", "value": 412, "source": "store_observed"},
                {"name": "reactivation_rate", "value": 0.12, "source": "store_observed", "n": 412},
            ],
            suppressed=False,
        ),
    )


def _targeting_card() -> PlayCard:
    return PlayCard(
        play_id="category_expansion",
        evidence_class=EvidenceClass.TARGETING,
        confidence_label="Targeting",
        audience=Audience(id="cat_exp", definition="Existing customers", size=900),
        measurement=None,
        revenue_range=RevenueRange(
            drivers=[
                {"name": "suppression_reason", "source": "sizing_v2", "reason": "targeting_non_causal_prior"},
            ],
            suppressed=True,
        ),
    )


def _engine_run() -> EngineRun:
    return EngineRun(
        run_id="run-1",
        store_id="store-x",
        anchor_date="2026-05-03",
        data_window=DataWindow(primary_window="L28", available_windows=["L7", "L28"], anchor_quality="good"),
        cold_start=False,
        data_quality_flags=[],
        abstain=Abstain(state=DecisionState.PUBLISH),
        state_of_store=[Observation(classification=ObservationClassification.HELD)],
        recommendations=[_measured_card(), _targeting_card()],
        considered=[
            RejectedPlay(
                play_id="overstock_demand_push",
                reason_code=ReasonCode.INVENTORY_BLOCKED,
            )
        ],
        watching=[WatchedSignal(metric="repeat_rate_within_window", trend="up", threshold_to_act="hits 18%")],
        scale=Scale(monthly_revenue=120_000.0, customer_base_est=4500, materiality_floor=5000.0),
    )


# ---------------------------------------------------------------------------
# Debug page MUST surface internal stats
# ---------------------------------------------------------------------------


def test_debug_html_contains_internal_diagnostics():
    debug_html = render_debug_html(_engine_run())
    # Internal-only labels.
    assert "p_internal" in debug_html
    assert "ci_internal" in debug_html
    # Numeric diagnostics flow through as code spans.
    assert "0.014" in debug_html
    assert "0.04" in debug_html
    assert "0.20" in debug_html
    # Drivers provenance is exposed for review.
    assert "audience_size" in debug_html
    assert "reactivation_rate" in debug_html
    # Targeting card with suppressed range surfaces a reason.
    assert "targeting_non_causal_prior" in debug_html
    # Considered/rejected are shown with reason codes.
    assert "inventory_blocked" in debug_html


def test_debug_html_carries_internal_only_banner():
    debug_html = render_debug_html(_engine_run())
    assert INTERNAL_BANNER in debug_html
    # Banner mentions "INTERNAL" and "NOT FOR MERCHANT" so a casual reader
    # cannot mistake it for the briefing.
    assert "INTERNAL" in debug_html
    assert "NOT FOR MERCHANT" in debug_html


def test_debug_html_renders_handle_empty_engine_run():
    """No fixture data still renders a complete document."""
    er = EngineRun(run_id="r", store_id="s")
    debug_html = render_debug_html(er)
    assert "<html" in debug_html
    assert "</html>" in debug_html
    assert INTERNAL_BANNER in debug_html


# ---------------------------------------------------------------------------
# Merchant-facing briefing MUST NOT surface internal stats
# ---------------------------------------------------------------------------


_FORBIDDEN_IN_BRIEFING = [
    "p_internal",
    "ci_internal",
    "p =",
    "q =",
    "confidence_score",
    "final_score",
]


def test_briefing_v2_html_does_not_contain_p_internal_or_ci_internal():
    briefing_html = render_engine_run(_engine_run())
    for bad in _FORBIDDEN_IN_BRIEFING:
        assert bad not in briefing_html, f"forbidden token {bad!r} found in briefing.html"


def test_briefing_v2_html_does_not_link_to_debug_html():
    briefing_html = render_engine_run(_engine_run())
    # Merchant-facing page must not advertise the internal page.
    assert "debug.html" not in briefing_html
    assert "receipts/debug.html" not in briefing_html
    # Defensive: also no anchor href containing the literal string.
    assert "href=\"debug" not in briefing_html
    assert "href='debug" not in briefing_html


def test_briefing_v2_html_does_not_carry_internal_only_banner():
    briefing_html = render_engine_run(_engine_run())
    assert INTERNAL_BANNER not in briefing_html
    assert "NOT FOR MERCHANT" not in briefing_html


def test_briefing_html_has_no_observed_effect_numeric():
    """Belt-and-braces: the observed_effect 0.12 from the measurement should
    not be rendered as a string by the V2 briefing path. The V2 renderer is
    intentionally opaque about internal numerics; the audit trail lives in
    debug.html."""
    briefing_html = render_engine_run(_engine_run())
    # We do not forbid all 0.12 tokens (they could appear in other contexts);
    # we forbid the explicit internal label paired with the value.
    assert "observed_effect=0.12" not in briefing_html
    assert "p_internal=0.014" not in briefing_html
