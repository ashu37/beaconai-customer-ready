"""Synthetic Blocker Fix 5 — Materiality footer line restoration.

The merchant-readable materiality footer must appear on every
non-ABSTAIN_HARD V2 briefing:

    "We only recommend primary plays that could realistically add at
    least $X this month for a store your size."

The exact dollar amount must match ``EngineRun.scale.materiality_floor``.
The raw engineering jargon ``"Materiality floor:"`` must NEVER appear in
``briefing.html`` (Phase 5.4 contract).

Pre-Fix-5 root cause: ``engine_run_adapter._scale_from_aligned`` set
``materiality_floor=None`` and the floor was only stamped later by
``apply_guardrails`` when the ``MATERIALITY_FLOOR_SCALE_AWARE`` flag was
on. With the flag off (the synthetic e2e configuration), the renderer
silently dropped the line.

Fix 5 stamps the floor unconditionally in the legacy adapter so the
sentence is always available to the V2 renderer regardless of which
guardrail flags are on. Floor *values* are unchanged.
"""
from __future__ import annotations

from src.engine_run import (
    Abstain,
    DataQualityFlag,
    DecisionState,
    EngineRun,
    Scale,
)
from src.engine_run_adapter import _scale_from_aligned, build_engine_run_from_legacy
from src.storytelling_v2 import render_engine_run


# The merchant-readable substring the renderer must produce.
MATERIALITY_SENTENCE = (
    "We only recommend primary plays that could realistically add at least"
)
# The engineering jargon the V2 renderer must NEVER produce (Phase 5.4
# contract; the precise number stays in receipts/debug.html).
JARGON = "Materiality floor:"


# ---------------------------------------------------------------------------
# Adapter-side: floor is stamped unconditionally.
# ---------------------------------------------------------------------------


def test_scale_from_aligned_stamps_materiality_floor_when_revenue_known():
    """Adapter must populate ``Scale.materiality_floor`` even when no
    guardrail flag is set, so the renderer can always render the
    merchant-readable sentence.

    ARR-tier sanity: ``$94,405`` monthly => ARR ~= $1.13M => tier-2
    (``$1-5M``) => ``max($10k, 3% of monthly_revenue)`` = ``$10,000``.
    """
    aligned = {
        "L28": {
            "net_sales": 94_405.0,
            "meta": {"identified_recent": 286},
        }
    }
    scale = _scale_from_aligned(aligned)
    assert scale.materiality_floor is not None
    assert scale.materiality_floor > 0
    # Tier-2 (ARR $1M-5M): max($10k, 3% of monthly).
    assert scale.materiality_floor == 10_000.0


def test_scale_from_aligned_stamps_floor_for_higher_revenue_tiers():
    aligned_mid = {"L28": {"net_sales": 200_000.0}}  # ~$2.4M ARR; tier-2.
    scale_mid = _scale_from_aligned(aligned_mid)
    # Tier-2 floor: max($10k, 3%); 3% of 200k = $6k => $10k wins.
    assert scale_mid.materiality_floor == 10_000.0

    aligned_big = {"L28": {"net_sales": 1_000_000.0}}  # tier-3.
    scale_big = _scale_from_aligned(aligned_big)
    # Tier-3 floor: max($25k, 5%); 5% of 1M = $50k.
    assert scale_big.materiality_floor == 50_000.0


def test_scale_from_aligned_stamps_floor_when_revenue_missing():
    """No revenue available -> default tier-1 floor ($5k); the line still
    renders rather than silently dropping."""
    scale = _scale_from_aligned({})
    assert scale.materiality_floor == 5_000.0


# ---------------------------------------------------------------------------
# Renderer-side: sentence appears on every non-ABSTAIN_HARD layout.
# ---------------------------------------------------------------------------


def _engine_run(state: DecisionState, *, floor: float = 10_000.0,
                monthly_revenue: float = 120_000.0) -> EngineRun:
    return EngineRun(
        store_id="fix5",
        scale=Scale(monthly_revenue=monthly_revenue, materiality_floor=floor),
        abstain=Abstain(state=state),
    )


def test_publish_briefing_renders_merchant_readable_materiality_sentence():
    html = render_engine_run(_engine_run(DecisionState.PUBLISH))
    assert MATERIALITY_SENTENCE in html
    assert "$10,000" in html
    assert "for a store your size" in html


def test_abstain_soft_briefing_renders_merchant_readable_materiality_sentence():
    html = render_engine_run(_engine_run(DecisionState.ABSTAIN_SOFT))
    assert MATERIALITY_SENTENCE in html
    assert "$10,000" in html
    assert "for a store your size" in html


def test_v2_briefing_never_renders_raw_materiality_jargon_string():
    """Phase 5.4 contract: ``"Materiality floor:"`` is forbidden in
    merchant briefings. Fix 5 must not regress this contract."""
    for state in (DecisionState.PUBLISH, DecisionState.ABSTAIN_SOFT,
                  DecisionState.ABSTAIN_HARD):
        html = render_engine_run(_engine_run(state))
        assert JARGON not in html, (
            f"V2 briefing for {state.value} must not contain the raw "
            f"jargon string {JARGON!r}; only the merchant-readable "
            "Phase 5.4 copy is allowed."
        )


def test_materiality_amount_in_html_matches_scale_materiality_floor():
    """The sentence must carry the EngineRun.scale.materiality_floor
    value verbatim (formatted as money)."""
    er = _engine_run(DecisionState.ABSTAIN_SOFT, floor=12_345.0,
                     monthly_revenue=400_000.0)
    html = render_engine_run(er)
    assert MATERIALITY_SENTENCE in html
    # Check the formatted amount is the exact floor value.
    assert "$12,345" in html


# ---------------------------------------------------------------------------
# End-to-end: floor lands on Scale via the legacy adapter and renders.
# ---------------------------------------------------------------------------


def test_engine_run_from_legacy_stamps_materiality_floor_for_renderer():
    """Without any guardrail flag set, the adapter alone must populate
    ``Scale.materiality_floor`` so the V2 footer line renders."""
    aligned = {"L28": {"net_sales": 94_405.0,
                       "meta": {"identified_recent": 286}}}
    actions_bundle = {"actions": [], "watchlist": [], "pilot_actions": [],
                      "backlog": [], "confidence_mode": "balanced"}
    er = build_engine_run_from_legacy(
        actions_bundle=actions_bundle,
        aligned=aligned,
        df=None,
        cfg={},  # no guardrail flags
        store_id="fix5_e2e",
        anchor_date=None,
    )
    assert er.scale is not None
    assert er.scale.materiality_floor is not None
    # Adapter computed ARR-tier floor must match what the renderer shows.
    expected_floor = er.scale.materiality_floor
    # Floor amount survives into the rendered HTML.
    er.abstain = Abstain(state=DecisionState.ABSTAIN_SOFT)
    html = render_engine_run(er)
    assert MATERIALITY_SENTENCE in html
    # $94,405/month -> ARR $1.13M -> tier-2 -> $10k.
    assert expected_floor == 10_000.0
    assert "$10,000" in html


# ---------------------------------------------------------------------------
# ABSTAIN_HARD layout: not asserted to suppress the line, but must not
# leak the jargon string. The brief allows ABSTAIN_HARD to omit the
# sentence; current behavior preserves it when scale is populated. We
# only pin the no-jargon invariant here so a future Fix-5-adjacent
# refactor cannot regress it.
# ---------------------------------------------------------------------------


def test_abstain_hard_briefing_does_not_leak_materiality_jargon():
    er = _engine_run(DecisionState.ABSTAIN_HARD)
    er.data_quality_flags = [DataQualityFlag.BFCM_OVERLAP]
    html = render_engine_run(er)
    assert JARGON not in html
