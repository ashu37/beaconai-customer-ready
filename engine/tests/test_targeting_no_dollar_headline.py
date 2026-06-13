"""DS Architect QA Change 4 — targeting cards must not display a standalone
``$X,XXX`` p50 dollar headline (M8 T8.5).

This test is the mechanical forcing function that pins the M8 contract.

Hard rules under test:

- A targeting card MUST NOT contain any ``$X,XXX`` pattern *outside* the
  range chip element. The range chip wraps any allowed dollar mention
  with the ``play-card-range-chip`` class so the renderer can be both
  human-readable and machine-checked.
- A range chip may appear ONLY when ``revenue_range.suppressed=False``
  AND the chip is clearly labeled with its source.
- When ``revenue_range.suppressed=True`` (cold-start, non-causal prior,
  default for current targeting plays), NO dollar amount may appear on
  the card.
"""
from __future__ import annotations

import re
from typing import List

import pytest

from src.engine_run import (
    Audience,
    EngineRun,
    EvidenceClass,
    PlayCard,
    RevenueRange,
    RevenueRangeSource,
    Scale,
)
from src.storytelling_v2 import (
    RANGE_CHIP_CLASS,
    TARGETING_CARD_CLASS,
    TARGETING_CARD_DISCLAIMER,
    render_engine_run,
    render_play_card,
)


# Match any standalone dollar amount with at least one digit after $.
# Examples that match: $5,000   $123   $1,234,567
_DOLLAR_RE = re.compile(r"\$[\d][\d,]*")


def _extract_targeting_cards(html: str) -> List[str]:
    """Pull each targeting card's HTML substring out of the rendered page.

    The renderer wraps every targeting card with
    ``<article class="play-card play-card--targeting" ...>``. We split on
    ``<article`` and keep substrings that include the targeting class.
    """
    pieces = []
    parts = html.split("<article")
    for raw in parts[1:]:
        opening_close = raw.find(">")
        if opening_close < 0:
            continue
        attrs = raw[:opening_close]
        if TARGETING_CARD_CLASS not in attrs:
            continue
        # Card body ends at the matching </article>. We don't have nested
        # articles so a simple find is safe.
        end = raw.find("</article>")
        if end < 0:
            continue
        pieces.append("<article" + raw[: end + len("</article>")])
    return pieces


def _strip_range_chips(card_html: str) -> str:
    """Return the card HTML with any ``play-card-range-chip`` span removed.

    The chip class is a single inline span. We remove every span whose
    opening tag carries the chip class (and its inner content), so any
    dollar text inside the chip is excluded from the headline check.
    """
    out = card_html
    while True:
        idx = out.find(RANGE_CHIP_CLASS)
        if idx < 0:
            break
        # Walk backwards to the opening "<span" of this chip.
        open_idx = out.rfind("<span", 0, idx)
        if open_idx < 0:
            break
        # And forward to the matching closing </span>. Chips are simple
        # (no nested <span>); a linear find is safe.
        close_idx = out.find("</span>", idx)
        if close_idx < 0:
            break
        out = out[:open_idx] + out[close_idx + len("</span>") :]
    return out


def _make_card(
    *,
    play_id: str = "bestseller_amplify",
    suppressed: bool = True,
    p10: float = None,
    p50: float = None,
    p90: float = None,
) -> PlayCard:
    rr = RevenueRange(
        p10=p10,
        p50=p50,
        p90=p90,
        source=RevenueRangeSource.STORE_OBSERVED,
        drivers=[{"name": "audience", "value": 1500}],
        suppressed=suppressed,
    )
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.TARGETING,
        confidence_label="Targeting",
        audience=Audience(
            id="aud_bestseller",
            definition="L28 buyers who purchased the top SKU",
            size=1500,
            fraction_of_base=0.12,
        ),
        revenue_range=rr,
    )


# ---------------------------------------------------------------------------
# Direct render_play_card tests
# ---------------------------------------------------------------------------


def test_suppressed_targeting_card_has_no_dollar_amount_at_all():
    """When suppressed=True, NO $ may appear anywhere on the card."""
    card = _make_card(suppressed=True, p50=999_999, p10=1000, p90=2_000_000)
    html = render_play_card(card, scale=Scale(monthly_revenue=120000))
    # Targeting class wrapper present.
    assert TARGETING_CARD_CLASS in html
    # Disclaimer present.
    assert TARGETING_CARD_DISCLAIMER in html
    # No range chip present.
    assert RANGE_CHIP_CLASS not in html
    # Strict: no dollar pattern anywhere.
    assert not _DOLLAR_RE.search(html), (
        f"Suppressed targeting card unexpectedly contains a dollar amount: {html!r}"
    )


def test_unsuppressed_targeting_card_renders_chip_but_no_headline():
    """Range chip is allowed when suppressed=False; no $ outside the chip."""
    card = _make_card(suppressed=False, p10=1000, p50=2500, p90=4000)
    html = render_play_card(card, scale=Scale(monthly_revenue=120000))
    assert TARGETING_CARD_CLASS in html
    assert RANGE_CHIP_CLASS in html
    # The chip's source label must be present (clearly labeled).
    assert "Estimated range" in html
    # No standalone $ headline outside the chip.
    stripped = _strip_range_chips(html)
    assert not _DOLLAR_RE.search(stripped), (
        "Targeting card has a $ amount outside the range chip element. "
        "Per DS Architect QA Change 4 the chip is the only allowed dollar "
        "mention on a targeting card."
    )


def test_targeting_card_disclaimer_is_fixed_text():
    card = _make_card()
    html = render_play_card(card, scale=Scale())
    assert TARGETING_CARD_DISCLAIMER in html
    assert "who-to-send-to" in html


# ---------------------------------------------------------------------------
# End-to-end: render full EngineRun and walk every targeting card
# ---------------------------------------------------------------------------


def test_full_engine_run_targeting_cards_pass_invariant():
    """Render a multi-card EngineRun; assert every targeting card complies."""
    er = EngineRun(
        store_id="invariant_test",
        recommendations=[
            _make_card(play_id="bestseller_amplify", suppressed=True),
            _make_card(
                play_id="category_expansion",
                suppressed=False,
                p10=500,
                p50=900,
                p90=1500,
            ),
            _make_card(play_id="subscription_nudge", suppressed=True),
        ],
        scale=Scale(monthly_revenue=200000, materiality_floor=4000),
    )
    html = render_engine_run(er)
    cards = _extract_targeting_cards(html)
    assert len(cards) == 3, f"Expected 3 targeting cards rendered, got {len(cards)}"
    for card_html in cards:
        # Disclaimer always present.
        assert TARGETING_CARD_DISCLAIMER in card_html
        # No standalone $ outside the chip.
        stripped = _strip_range_chips(card_html)
        leftover = _DOLLAR_RE.search(stripped)
        assert leftover is None, (
            f"Targeting card has a $ headline outside the range chip "
            f"element: {leftover.group(0)!r} in {card_html!r}"
        )


def test_briefing_html_has_no_pvalue_qvalue_ci_confidence_score_or_finalscore():
    """Page-wide invariant: forbidden statistical strings must not appear."""
    er = EngineRun(
        store_id="invariant_test",
        recommendations=[
            _make_card(play_id="bestseller_amplify", suppressed=True),
            _make_card(
                play_id="category_expansion",
                suppressed=False,
                p10=500,
                p50=900,
                p90=1500,
            ),
        ],
        scale=Scale(monthly_revenue=200000, materiality_floor=4000),
    )
    html = render_engine_run(er)
    forbidden = [
        "p =",
        "q =",
        "p-value",
        "q-value",
        "p_value",
        "q_value",
        "confidence_score",
        "final_score",
    ]
    for needle in forbidden:
        assert needle not in html, (
            f"Forbidden statistical string {needle!r} appeared in V2 briefing HTML"
        )
    # CI tokens should not appear; allow case-insensitive guarding to catch
    # both "CI [", "CI:", and "ci_internal" if the renderer ever leaks them.
    assert "CI [" not in html
    assert "CI:" not in html
    assert "ci_internal" not in html
    assert "p_internal" not in html


def test_no_numeric_confidence_percentage_string():
    """Numeric confidence percentages must not appear (e.g. 'confidence: 95%')."""
    er = EngineRun(
        store_id="invariant_test",
        recommendations=[_make_card(play_id="bestseller_amplify", suppressed=True)],
        scale=Scale(monthly_revenue=200000),
    )
    html = render_engine_run(er).lower()
    # The phrase "X% confidence" in any casing must not appear.
    confidence_pattern = re.compile(r"\d+\s*%\s*confidence")
    assert not confidence_pattern.search(html)
    # The phrase "confidence: 95" must not appear.
    confidence_kv = re.compile(r"confidence\s*[:=]\s*\d")
    assert not confidence_kv.search(html)
