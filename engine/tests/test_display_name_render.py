"""Phase 6B Ticket C3 — Customer-facing play-title relabel.

Pins the V2 renderer contract for card ``<h3>`` titles. Per Phase 6B
Ticket C3 (see
``agent_outputs/implementation-manager-phase6b-founder-feedback-plan.md``
§4 / §5 / §6) the renderer reads
:data:`src.play_registry.PLAYS[play_id].display_name` for the title and
falls back to :func:`src.storytelling_v2._humanize_play_id` only when
the play_id is unknown to the registry.

Hard rules under test:

- The ``<h3>`` text on Recommended Now / Recommended Experiment /
  Considered cards equals the registry display_name verbatim when
  the play_id is registered.
- The ``<h3>`` text falls back to the ``_humanize_play_id`` derivation
  when the play_id is NOT in the registry. Unknown / future play_ids
  must never crash the renderer.
- The ``data-play-id`` HTML attribute on the article tag continues to
  emit the original snake_case ``play_id`` byte-for-byte (engineering-
  readable, log-stable identifier).
- Specific pinned plays — ``winback_21_45``, ``bestseller_amplify``,
  ``empty_bottle`` — match the IM-plan exemplar copy verbatim.
"""
from __future__ import annotations

import pytest

from src.engine_run import (
    Abstain,
    Audience,
    DataWindow,
    DecisionState,
    EngineRun,
    EvidenceClass,
    Measurement,
    NonLiftAtom,
    OpportunityContext,
    PlayCard,
    ReasonCode,
    RejectedPlay,
    RevenueRange,
    Scale,
    WatchedSignal,
    WouldBeMeasuredBy,
)
from src.play_registry import PLAYS
from src.storytelling_v2 import _humanize_play_id, render_engine_run


# ---------------------------------------------------------------------------
# Helpers — mirror the fixture builders used by tests/test_what_we_send_render.py
# so the only contract the new tests pin is the title / data-play-id contract.
# ---------------------------------------------------------------------------


def _extract_section(html: str, section_class: str) -> str:
    """Return the substring of ``html`` for the section with the given class."""
    needle = f'class="{section_class}"'
    idx = html.find(needle)
    if idx < 0:
        return ""
    open_idx = html.rfind("<section", 0, idx)
    if open_idx < 0:
        return ""
    close_idx = html.find("</section>", idx)
    if close_idx < 0:
        return ""
    return html[open_idx : close_idx + len("</section>")]


def _article_for_play_id(html: str, play_id: str) -> str:
    """Return the `<article ...>...</article>` substring whose
    ``data-play-id`` attribute equals ``play_id``.
    """
    needle = f'data-play-id="{play_id}"'
    idx = html.find(needle)
    if idx < 0:
        return ""
    open_idx = html.rfind("<article", 0, idx)
    if open_idx < 0:
        return ""
    close_idx = html.find("</article>", idx)
    if close_idx < 0:
        return ""
    return html[open_idx : close_idx + len("</article>")]


def _h3_text(article_html: str) -> str:
    """Return the unescaped text inside the first ``<h3 class="play-card__title">``.

    The renderer escapes via :func:`html.escape` (single-quote = ``&#x27;``).
    Tests compare against the raw display_name for the pinned-plays smoke;
    this helper returns the escaped text and the test does the comparison
    against the rendered string directly.
    """
    needle = '<h3 class="play-card__title">'
    idx = article_html.find(needle)
    if idx < 0:
        return ""
    start = idx + len(needle)
    end = article_html.find("</h3>", start)
    if end < 0:
        return ""
    return article_html[start:end]


def _directional_card(*, play_id: str, audience_size: int = 2251) -> PlayCard:
    audience = Audience(
        size=audience_size,
        definition="single-purchase customers",
    )
    revenue_range = RevenueRange(suppressed=True)
    opp = OpportunityContext(
        audience_size=audience_size,
        non_lift=NonLiftAtom(
            value=float(audience_size) * 59.0,
            semantic="addressable_opportunity",
            aov_used=59.0,
            monthly_revenue_estimate=float(audience_size) * 59.0,
        ),
        aov_window="L28",
        aov_source="store_observed",
    )
    measurement = Measurement(
        metric="returning_customer_share",
        consistency_across_windows=3,
    )
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.DIRECTIONAL,
        audience=audience,
        measurement=measurement,
        revenue_range=revenue_range,
        opportunity_context=opp,
    )


def _experiment_card(
    *,
    play_id: str,
    audience_size: int = 1475,
    would_be_measured_by: WouldBeMeasuredBy = WouldBeMeasuredBy.REPEAT_PURCHASE_IN_30D,
) -> PlayCard:
    audience = Audience(
        size=audience_size,
        definition="recent buyers in eligible segment",
    )
    revenue_range = RevenueRange(
        suppressed=True,
        drivers=[{"reason": "experiment_no_calibrated_lift"}],
    )
    opp = OpportunityContext(
        audience_size=audience_size,
        non_lift=NonLiftAtom(
            value=float(audience_size) * 69.0,
            semantic="addressable_opportunity",
            aov_used=69.0,
            monthly_revenue_estimate=float(audience_size) * 69.0,
        ),
        aov_window="L28",
        aov_source="store_observed",
    )
    return PlayCard(
        play_id=play_id,
        evidence_class=EvidenceClass.TARGETING,
        audience=audience,
        measurement=None,
        revenue_range=revenue_range,
        opportunity_context=opp,
        would_be_measured_by=would_be_measured_by,
    )


def _publish_engine_run(
    *,
    recommendations=None,
    recommended_experiments=None,
    considered=None,
    watching=None,
) -> EngineRun:
    return EngineRun(
        store_id="c3_test",
        anchor_date="2026-04-30T00:00:00",
        data_window=DataWindow(primary_window="L28"),
        cold_start=False,
        data_quality_flags=[],
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=list(recommendations or []),
        recommended_experiments=list(recommended_experiments or []),
        considered=list(considered or []),
        watching=list(
            watching
            or [
                WatchedSignal(
                    metric="aov",
                    current=58.0,
                    prior=55.6,
                    trend="up",
                    threshold_to_act="AOV moves +5% sustained 2 windows",
                ),
            ]
        ),
        scale=Scale(monthly_revenue=180_000.0, materiality_floor=5_400.0),
    )


# ---------------------------------------------------------------------------
# Required tests
# ---------------------------------------------------------------------------


def test_renderer_uses_play_registry_display_name() -> None:
    """The card ``<h3>`` text MUST equal
    :data:`PLAYS[play_id].display_name` verbatim when the play_id is in
    the registry, and the article's ``data-play-id`` MUST still be the
    snake_case identifier.

    Uses ``first_to_second_purchase`` because it carries both a registry
    entry (with a merchant-readable display_name post-C3) and a
    config/priors.yaml metadata block (so the rest of the card render
    path is exercised end-to-end with realistic data).
    """
    play_id = "first_to_second_purchase"
    play_def = PLAYS.get(play_id)
    assert play_def is not None, (
        "Test fixture sanity: first_to_second_purchase must be registered."
    )
    expected_title = play_def.display_name
    assert expected_title and expected_title.strip(), (
        "Test fixture sanity: first_to_second_purchase must have a "
        "non-empty display_name in the registry."
    )

    er = _publish_engine_run(
        recommendations=[_directional_card(play_id=play_id)],
    )
    html = render_engine_run(er)
    article = _article_for_play_id(html, play_id)
    assert article, (
        f"Expected an <article data-play-id={play_id!r}> in the rendered HTML."
    )

    title_text = _h3_text(article)
    assert title_text == expected_title, (
        f"Expected <h3> text {expected_title!r}; got {title_text!r}. "
        f"Phase 6B Ticket C3: the renderer must pull display_name from the "
        f"play registry, not derive it from play_id."
    )

    # Defensive: the snake_case identifier is still present on the article.
    assert f'data-play-id="{play_id}"' in article


def test_renderer_falls_back_to_humanize_for_unknown_play_id() -> None:
    """For a play_id that is NOT registered, the renderer MUST fall back
    to the existing :func:`_humanize_play_id` behavior (snake_case ->
    Title Case). This pins the safety contract: an unknown / future
    play_id never crashes the renderer and at minimum reads as a
    title-cased label.
    """
    play_id = "mystery_play"
    assert play_id not in PLAYS, (
        "Test fixture sanity: mystery_play must NOT be in the registry."
    )
    expected_title = _humanize_play_id(play_id)
    assert expected_title == "Mystery Play", (
        "Sanity: _humanize_play_id('mystery_play') must equal 'Mystery Play'."
    )

    er = _publish_engine_run(
        recommendations=[_directional_card(play_id=play_id)],
    )
    html = render_engine_run(er)
    article = _article_for_play_id(html, play_id)
    assert article, (
        f"Expected an <article data-play-id={play_id!r}> in the rendered HTML."
    )
    title_text = _h3_text(article)
    assert title_text == expected_title, (
        f"Fallback contract: unknown play_id {play_id!r} should render as "
        f"{expected_title!r}; got {title_text!r}."
    )

    # Defensive: the snake_case identifier is still present on the article.
    assert f'data-play-id="{play_id}"' in article


def test_data_play_id_attribute_is_internal_snake_case() -> None:
    """The ``data-play-id`` HTML attribute MUST carry the original
    snake_case ``play_id`` on Recommended Now, Recommended Experiment,
    and Considered cards regardless of the merchant-facing
    ``display_name``. Internal logic / log analysis / history files
    (recommended_history.json) all rely on snake_case as the stable
    identifier.
    """
    rec_play_id = "first_to_second_purchase"
    exp_play_id = "bestseller_amplify"
    considered_play_id = "discount_hygiene"

    er = _publish_engine_run(
        recommendations=[_directional_card(play_id=rec_play_id)],
        recommended_experiments=[_experiment_card(play_id=exp_play_id)],
        considered=[
            RejectedPlay(
                play_id=considered_play_id,
                reason_code=ReasonCode.NO_MEASURED_SIGNAL,
            )
        ],
    )
    html = render_engine_run(er)

    # Each play_id must appear verbatim in a data-play-id attribute on
    # an article inside its expected section.
    rec_section = _extract_section(html, "recommended")
    exp_section = _extract_section(html, "recommended-experiment")
    considered_section = _extract_section(html, "considered")
    assert rec_section, "section.recommended did not render"
    assert exp_section, "section.recommended-experiment did not render"
    assert considered_section, "section.considered did not render"

    assert f'data-play-id="{rec_play_id}"' in rec_section, (
        f"Expected data-play-id={rec_play_id!r} inside section.recommended."
    )
    assert f'data-play-id="{exp_play_id}"' in exp_section, (
        f"Expected data-play-id={exp_play_id!r} inside "
        "section.recommended-experiment."
    )
    assert f'data-play-id="{considered_play_id}"' in considered_section, (
        f"Expected data-play-id={considered_play_id!r} inside "
        "section.considered."
    )

    # Defensive: the merchant-facing display_name must NOT replace the
    # snake_case identifier in the data attribute. Compare each
    # display_name to the snake_case key to make sure they differ.
    for pid in (rec_play_id, exp_play_id, considered_play_id):
        display = PLAYS[pid].display_name
        assert display != pid, (
            f"Sanity: display_name and play_id should differ post-C3 for "
            f"{pid!r}; got {display!r}."
        )
        assert f'data-play-id="{display}"' not in html, (
            f"Regression: display_name {display!r} must not leak into "
            f"data-play-id; expected {pid!r} as the attribute value."
        )


@pytest.mark.parametrize(
    "play_id, expected_display_name",
    [
        # Verbatim from the IM plan §6 acceptance criteria.
        ("winback_21_45", "Lapsed-buyer reactivation (3–6 weeks since last order)"),
        ("bestseller_amplify", "Top-product re-targeting"),
        ("empty_bottle", "Replenishment timing"),
    ],
)
def test_display_name_is_merchant_readable_for_pinned_plays(
    play_id: str, expected_display_name: str
) -> None:
    """Pin the IM-plan exemplar copy verbatim. If a future change re-words
    these three display_name strings, this test forces an explicit
    update plus a corresponding update to the IM plan / acceptance memo.
    """
    play_def = PLAYS.get(play_id)
    assert play_def is not None, f"{play_id} must be registered."
    assert play_def.display_name == expected_display_name, (
        f"Phase 6B Ticket C3 acceptance: PLAYS[{play_id!r}].display_name "
        f"must equal {expected_display_name!r} (verbatim from the IM plan); "
        f"got {play_def.display_name!r}."
    )
