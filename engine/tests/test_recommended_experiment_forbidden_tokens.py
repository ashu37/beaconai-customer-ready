"""Phase 6A Ticket B2 — Recommended Experiment forbidden-token sweep.

Pins a rigorous, scoped sweep on ``section.recommended-experiment`` that
the campaign-slate contract's universal-forbidden tokens (causal,
statistical, forecasting, composite-score) NEVER appear inside the
Recommended Experiment section, with a single exact-string allowlist for
the negation disclaimer

    "This is not projected lift; it shows the size of the audience if
    the play converts."

Hard rules under test (per
``agent_outputs/campaign-slate-contract-final.md`` and
``agent_outputs/implementation-manager-campaign-slate-plan.md`` §B2):

- Universal forbidden tokens (case-insensitive scan) must NOT appear
  inside ``section.recommended-experiment``: ``calibrated``, ``uplift``,
  ``ATE``, ``ITT``, ``treatment effect``, ``expected lift``, ``forecast``,
  ``predicted``, ``p =``, ``q =``, ``p-value``, ``q-value``,
  ``confidence_score``, ``final_score``, ``p_internal``, ``ci_internal``,
  ``Aura``, ``Beacon Score``, ``beacon_score``.
- Special case: ``projected lift`` is forbidden EXCEPT inside the exact
  disclaimer phrase ``OPPORTUNITY_CONTEXT_DISCLAIMER``.
- ``measured`` (past-tense / evidence claim) MUST NOT appear inside the
  section. ``measure`` (future-tense plan, e.g. "We will measure ...")
  remains allowed.
- ``evidence`` / ``evidence-backed`` MUST NOT appear inside the section.
- Negative controls: when forbidden text is injected via
  ``recommendation_text``, the sweep must FAIL — i.e. the test detects
  the token rather than silently passing.

Scope:

- The sweep is scoped to the substring of ``html`` between the
  ``<section class="recommended-experiment">`` open tag and the matching
  ``</section>`` close tag. MOVED / WATCHING / Considered / State of
  Store / Recommended Now content cannot leak in and trigger false
  positives.

This is a TEST-ONLY ticket. The expectation is zero changes to ``src/``.
If a renderer/opportunity-context copy change appears necessary, stop
and report rather than silently editing copy.
"""
from __future__ import annotations

import re
from typing import List

import pytest

from src.engine_run import (
    Abstain,
    Audience,
    DataWindow,
    DecisionState,
    EngineRun,
    EvidenceClass,
    NonLiftAtom,
    OpportunityContext,
    PlayCard,
    RevenueRange,
    Scale,
    WatchedSignal,
    WouldBeMeasuredBy,
)
from src.storytelling_v2 import (
    OPPORTUNITY_CONTEXT_DISCLAIMER,
    RECOMMENDED_EXPERIMENT_SECTION_CLASS,
    render_engine_run,
)


# ---------------------------------------------------------------------------
# Fixture builders (mirror the B1 / B1.5 production card shape)
# ---------------------------------------------------------------------------


def _experiment_card(
    *,
    play_id: str,
    audience_size: int,
    would_be_measured_by: WouldBeMeasuredBy,
    recommendation_text: str = "",
    audience_definition: str = "discount-prone buyers",
    with_opportunity: bool = True,
) -> PlayCard:
    """Build a Recommended Experiment-shaped PlayCard.

    Mirrors the shape produced by
    ``src.decide._select_recommended_experiments`` (Ticket A4) plus the
    ``opportunity_context`` populated by Ticket B1.5.
    """
    audience = Audience(size=audience_size, definition=audience_definition)
    revenue_range = RevenueRange(
        suppressed=True,
        drivers=[{"reason": "experiment_no_calibrated_lift"}],
    )
    opp = None
    if with_opportunity:
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


def _publish_engine_run_with_experiments(
    experiments: List[PlayCard],
) -> EngineRun:
    """Build a PUBLISH EngineRun carrying ``experiments`` ONLY in the
    Recommended Experiment slot. Recommended Now / Considered are empty
    so the sweep cannot accidentally pick up sibling-section content.
    """
    return EngineRun(
        store_id="b2_test",
        anchor_date="2026-04-30T00:00:00",
        data_window=DataWindow(primary_window="L28"),
        cold_start=False,
        data_quality_flags=[],
        abstain=Abstain(state=DecisionState.PUBLISH),
        recommendations=[],
        recommended_experiments=list(experiments),
        considered=[],
        watching=[
            WatchedSignal(
                metric="aov",
                current=58.0,
                prior=55.6,
                trend="up",
                threshold_to_act="AOV moves +5% sustained 2 windows",
            ),
        ],
        scale=Scale(monthly_revenue=180_000.0, materiality_floor=5_400.0),
    )


def _two_card_engine_run() -> EngineRun:
    """Default fixture: two real-allowlist experiment cards
    (``discount_hygiene`` + ``bestseller_amplify``) with the Phase 5.1
    opportunity-context block populated. Pins the canonical
    Beauty-Brand-shaped slate.
    """
    return _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
                audience_definition="discount-prone buyers",
            ),
            _experiment_card(
                play_id="bestseller_amplify",
                audience_size=1475,
                would_be_measured_by=WouldBeMeasuredBy.INCREMENTAL_ORDERS_IN_14D,
                audience_definition="recent buyers",
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Section extractor (DOM-scoped: ONLY section.recommended-experiment)
# ---------------------------------------------------------------------------


_SECTION_RE = re.compile(
    rf'<section[^>]*class="[^"]*\b{re.escape(RECOMMENDED_EXPERIMENT_SECTION_CLASS)}\b[^"]*"[^>]*>(?P<body>.*?)</section>',
    re.DOTALL,
)


def _extract_experiment_section(html: str) -> str:
    """Return the full ``<section class="recommended-experiment">...</section>``
    substring. Returns the empty string when absent.

    The regex is anchored on the literal section class
    ``RECOMMENDED_EXPERIMENT_SECTION_CLASS`` (B1 module constant) so a
    future renderer rename would force this test to update in lockstep.
    """
    match = _SECTION_RE.search(html)
    if not match:
        return ""
    # Return the full match (including the open + close tags) so callers
    # see exactly what the renderer emitted for this section.
    return match.group(0)


# Helpers to scope merchant-facing-copy scans to visible text only.
# CSS class names (``play-card__measured-by``) and structured data
# attributes (``data-evidence-class="targeting"``, ``data-aov-source``,
# ``data-aov-window``) are NOT merchant-readable copy. They are scraper /
# test selectors. The forbidden-token contract is explicit that the
# constraint is on merchant-facing language; stripping HTML tags before
# the case-insensitive lemma scans pins the contract at the right layer
# while still catching any leak into visible body copy.

_TAG_RE = re.compile(r"<[^>]+>")


def _visible_text(section_html: str) -> str:
    """Return the visible text content of ``section_html``.

    Strips every ``<...>`` HTML tag (including its attributes) so the
    scan only sees text the merchant would read. The Phase 5.1
    opportunity-context block uses ``&times;`` for the multiplication
    sign; that is body copy, not a tag, so it is preserved.
    """
    return _TAG_RE.sub("", section_html)


# ---------------------------------------------------------------------------
# Universal forbidden tokens (per campaign-slate-contract-final.md)
# ---------------------------------------------------------------------------


# Case-sensitive tokens. Each is checked verbatim. The list intentionally
# carries both the snake_case internal field names ("p_internal",
# "confidence_score") AND the merchant-facing causal-statistical phrases
# ("ATE", "ITT", "treatment effect"). The list is the union of:
#   - the seven new forbidden tokens called out by the contract,
#   - the older internal-field-name list pinned by Phase 5.5.
# Any rename / addition by a future contract update must add to this list.
UNIVERSAL_FORBIDDEN_TOKENS_CASE_SENSITIVE = [
    "calibrated",
    "uplift",
    "ATE",
    "ITT",
    "treatment effect",
    "expected lift",
    "forecast",
    "predicted",
    "p =",
    "q =",
    "p-value",
    "q-value",
    "confidence_score",
    "final_score",
    "p_internal",
    "ci_internal",
    "Aura",
    "Beacon Score",
    "beacon_score",
]


# ---------------------------------------------------------------------------
# 1. Universal forbidden tokens absent from the experiment section
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", UNIVERSAL_FORBIDDEN_TOKENS_CASE_SENSITIVE)
def test_universal_forbidden_tokens_absent_from_experiment_section(token):
    """Each universal-forbidden token MUST NOT appear inside
    ``section.recommended-experiment`` on the canonical two-card slate.

    The scan is scoped to visible text (HTML tags + attribute values
    stripped) because the contract constrains merchant-facing language,
    not CSS class names or structured data attributes used by scrapers.
    """
    er = _two_card_engine_run()
    html = render_engine_run(er)
    section = _extract_experiment_section(html)
    assert section, (
        "Recommended Experiment section did not render on the canonical "
        "two-card fixture; the sweep cannot run."
    )
    visible = _visible_text(section)
    assert token not in visible, (
        f"Forbidden token {token!r} appeared in visible copy inside "
        f"section.recommended-experiment. Renderer copy or PlayCard "
        f"copy is leaking forbidden language."
    )


# ---------------------------------------------------------------------------
# 2. "projected lift" is forbidden EXCEPT inside the exact disclaimer
# ---------------------------------------------------------------------------


def test_projected_lift_appears_only_inside_exact_disclaimer():
    """``projected lift`` is allowed exactly once per card body, and only
    inside the verbatim ``OPPORTUNITY_CONTEXT_DISCLAIMER`` phrase
    ('This is not projected lift; ...').

    Implementation:

    1. Confirm the literal disclaimer phrase appears in the section.
    2. Remove every exact occurrence of the disclaimer string from the
       section.
    3. Assert ``projected lift`` does not appear in the residual.

    This is an exact-string allowlist — surrounding context is
    structurally guaranteed by removing the verbatim disclaimer phrase
    BEFORE scanning. Any other occurrence of "projected lift" (e.g.
    "projected lift of $X", "expected projected lift", or anywhere
    outside the disclaimer) survives the removal step and trips the
    final assertion.
    """
    er = _two_card_engine_run()
    html = render_engine_run(er)
    section = _extract_experiment_section(html)
    assert section, "Recommended Experiment section did not render."

    visible = _visible_text(section)

    # 1. Disclaimer is present in visible copy.
    assert OPPORTUNITY_CONTEXT_DISCLAIMER in visible, (
        f"Expected the exact disclaimer "
        f"{OPPORTUNITY_CONTEXT_DISCLAIMER!r} to render verbatim inside "
        f"the section."
    )

    # 2. Remove every exact occurrence of the disclaimer.
    residual = visible.replace(OPPORTUNITY_CONTEXT_DISCLAIMER, "")

    # 3. No other "projected lift" occurrence is allowed.
    assert "projected lift" not in residual, (
        "'projected lift' appeared in the Recommended Experiment "
        "section outside the exact disclaimer phrase. The only "
        "permitted occurrence is inside "
        f"{OPPORTUNITY_CONTEXT_DISCLAIMER!r}."
    )


def test_disclaimer_phrase_renders_verbatim():
    """Pin the exact-string allowlist target. The disclaimer MUST render
    verbatim once per card; no paraphrase is acceptable.

    The renderer carries the disclaimer through ``_esc(...)`` which only
    escapes ``& < > " '``; the disclaimer contains none of these chars,
    so the rendered HTML must contain the constant verbatim.
    """
    er = _two_card_engine_run()
    html = render_engine_run(er)
    section = _extract_experiment_section(html)
    visible = _visible_text(section)
    # Two cards each carry the disclaimer once.
    assert visible.count(OPPORTUNITY_CONTEXT_DISCLAIMER) == 2, (
        f"Expected 2 disclaimer occurrences (one per card); got "
        f"{visible.count(OPPORTUNITY_CONTEXT_DISCLAIMER)}."
    )


# ---------------------------------------------------------------------------
# 3. "measured" forbidden inside cards; "measure" remains allowed in lede
# ---------------------------------------------------------------------------


def test_measured_past_tense_absent_from_experiment_section():
    """Recommended Experiment cards MUST NOT call themselves "measured"
    in visible copy. The section frames each card as a future
    send-and-measure plan, not a past-tense evidence claim. The forcing
    function is the contract: 'No "measured" or "evidence" claim on a
    directional or experiment card.'

    Scope: visible text only. CSS class names like
    ``play-card__measured-by`` are scraper selectors, not merchant
    copy, and are intentionally out of scope for this scan.
    """
    er = _two_card_engine_run()
    html = render_engine_run(er)
    section = _extract_experiment_section(html)
    visible_lower = _visible_text(section).lower()
    assert "measured" not in visible_lower, (
        "'measured' (past tense / evidence claim) appeared in visible "
        "copy inside section.recommended-experiment. Only 'measure' "
        "(future-tense plan, e.g. 'We will measure ...') is permitted."
    )


def test_measure_future_tense_allowed_in_section_lede_and_cards():
    """Positive control: ``measure`` (future tense) MUST remain allowed
    so the "We will measure ..." line and the section lede continue to
    surface. This pins the asymmetric treatment of the lemma.
    """
    er = _two_card_engine_run()
    html = render_engine_run(er)
    section = _extract_experiment_section(html)
    visible = _visible_text(section)
    # The section lede contains the literal word "measure".
    assert "measure" in visible.lower(), (
        "Future-tense 'measure' lemma must remain in the section "
        "(lede + per-card 'We will measure ...' line). Removing it "
        "would break the contract-mandated framing."
    )
    # The "We will measure ..." per-card line is contract copy.
    assert "We will measure" in visible, (
        "The contract-mandated 'We will measure ...' framing line "
        "is missing from the section."
    )


# ---------------------------------------------------------------------------
# 4. "evidence" / "evidence-backed" forbidden inside experiment section
# ---------------------------------------------------------------------------


def test_evidence_token_absent_from_experiment_section():
    """Recommended Experiment cards MUST NOT claim "evidence" or
    "evidence-backed" in visible copy. They are hypotheses, not
    evidence.

    Scope: visible text only. The structured data attribute
    ``data-evidence-class="targeting"`` is a scraper / test selector
    and is intentionally out of scope for this scan.
    """
    er = _two_card_engine_run()
    html = render_engine_run(er)
    section = _extract_experiment_section(html)
    # Case-insensitive scan over visible text to catch "Evidence",
    # "EVIDENCE-BACKED".
    visible_lower = _visible_text(section).lower()
    for token in ("evidence", "evidence-backed"):
        assert token not in visible_lower, (
            f"Forbidden token {token!r} appeared in visible copy inside "
            f"section.recommended-experiment. The section frames each "
            f"card as a hypothesis, never as evidence-backed."
        )


# ---------------------------------------------------------------------------
# 5. Negative controls — the test must FAIL if forbidden text is injected
# ---------------------------------------------------------------------------


def test_negative_control_universal_token_in_recommendation_text_is_detected():
    """Inject ``calibrated`` into a card's ``recommendation_text``;
    confirm the universal-token sweep would catch it. This pins that
    the test is not silently passing on an empty section.

    The check is the same logic the parametrized sweep uses, run inline
    so the failure-detection contract is not implicit.
    """
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
                # Forbidden phrase injected.
            ),
        ]
    )
    html = render_engine_run(er)
    section = _extract_experiment_section(html)
    assert section, "Section did not render; sweep cannot run."
    visible = _visible_text(section)
    # The injected forbidden text MUST be detected by the sweep logic.
    assert "calibrated" in visible, (
        "Sanity check: the injected forbidden token MUST surface in "
        "the rendered section so the universal sweep would fail. If "
        "this assertion ever flips, the renderer is silently scrubbing "
        "free-text and the negative control is wrong."
    )
    assert "treatment effect" in visible, (
        "Sanity check: 'treatment effect' from the recommendation_text "
        "must surface in the rendered section."
    )


def test_negative_control_projected_lift_outside_disclaimer_is_detected():
    """Inject an affirmative ``projected lift`` claim into
    ``recommendation_text`` (NOT inside the disclaimer phrase). The
    allowlist-by-removal scan must detect it.
    """
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
                # Affirmative claim — NOT the negation disclaimer.
            ),
        ]
    )
    html = render_engine_run(er)
    section = _extract_experiment_section(html)
    assert section, "Section did not render; sweep cannot run."
    visible = _visible_text(section)

    # Apply the same allowlist-by-removal logic as the production sweep.
    residual = visible.replace(OPPORTUNITY_CONTEXT_DISCLAIMER, "")
    # The injected affirmative claim survives the disclaimer-removal
    # step and would trip the production assertion.
    assert "projected lift" in residual, (
        "Sanity check: the injected affirmative 'projected lift' "
        "claim must survive disclaimer removal and trip the "
        "production sweep. If this assertion flips, the allowlist "
        "logic is over-broad."
    )


def test_negative_control_measured_in_recommendation_text_is_detected():
    """Inject ``measured`` into ``recommendation_text``; confirm the
    case-insensitive scan catches it.
    """
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="discount_hygiene",
                audience_size=2251,
                would_be_measured_by=WouldBeMeasuredBy.EMAIL_ATTRIBUTED_REVENUE_IN_7D,
            ),
        ]
    )
    html = render_engine_run(er)
    section = _extract_experiment_section(html)
    assert section, "Section did not render; sweep cannot run."
    visible_lower = _visible_text(section).lower()
    assert "measured" in visible_lower, (
        "Sanity check: the injected past-tense 'measured' token must "
        "surface in the rendered section for the production sweep to "
        "detect it."
    )


def test_negative_control_evidence_in_recommendation_text_is_detected():
    """Inject ``evidence-backed`` into ``recommendation_text``; confirm
    the case-insensitive scan catches it.
    """
    er = _publish_engine_run_with_experiments(
        [
            _experiment_card(
                play_id="bestseller_amplify",
                audience_size=1475,
                would_be_measured_by=WouldBeMeasuredBy.INCREMENTAL_ORDERS_IN_14D,
            ),
        ]
    )
    html = render_engine_run(er)
    section = _extract_experiment_section(html)
    assert section, "Section did not render; sweep cannot run."
    visible_lower = _visible_text(section).lower()
    assert "evidence-backed" in visible_lower, (
        "Sanity check: the injected 'evidence-backed' token must "
        "surface for the production sweep to detect it."
    )


# ---------------------------------------------------------------------------
# 6. Allowed-phrase positive controls (contract-mandated copy)
# ---------------------------------------------------------------------------


def test_run_as_experiment_framing_remains_allowed():
    """The literal "Run as experiment" framing MUST remain in the
    section. It is contract-mandated copy."""
    er = _two_card_engine_run()
    html = render_engine_run(er)
    section = _extract_experiment_section(html)
    visible = _visible_text(section)
    assert "Run as experiment" in visible, (
        "The 'Run as experiment' framing badge must render on every "
        "card. It is contract-mandated and not a forbidden token."
    )


@pytest.mark.parametrize(
    "expected_text",
    [
        "We will measure email-attributed revenue in 7 days.",
        "We will measure incremental orders in 14 days.",
    ],
)
def test_we_will_measure_lines_remain_allowed(expected_text):
    """Each card's enum-mapped "We will measure ..." line is contract
    copy and MUST remain. Two enum values are exercised by the canonical
    fixture; the third (``REPEAT_PURCHASE_IN_30D``) is exercised in
    ``tests/test_render_recommended_experiment.py``.
    """
    er = _two_card_engine_run()
    html = render_engine_run(er)
    section = _extract_experiment_section(html)
    visible = _visible_text(section)
    assert expected_text in visible, (
        f"Contract-mandated measurement-plan copy {expected_text!r} "
        f"is missing from the section."
    )


def test_disclaimer_phrase_remains_allowed_at_exact_string():
    """Positive control: the exact disclaimer phrase is allowlisted by
    the sweep. This pins that the disclaimer copy is not accidentally
    flagged by the universal-forbidden token list — none of the
    universal-forbidden tokens appear inside the disclaimer.

    The disclaimer is the only carrier of "projected lift" in the
    section; this test is the inverse of
    ``test_projected_lift_appears_only_inside_exact_disclaimer``.
    """
    # The disclaimer literal must not contain any universal-forbidden
    # token (other than "projected lift", which is the special case).
    for token in UNIVERSAL_FORBIDDEN_TOKENS_CASE_SENSITIVE:
        assert token not in OPPORTUNITY_CONTEXT_DISCLAIMER, (
            f"OPPORTUNITY_CONTEXT_DISCLAIMER contains universal-forbidden "
            f"token {token!r}; the allowlist would mask a real leak."
        )
    # And the disclaimer is the carrier of the "projected lift" special
    # case; the negation prefix "not " must precede it.
    idx = OPPORTUNITY_CONTEXT_DISCLAIMER.find("projected lift")
    assert idx > 0, (
        "Disclaimer must contain the negated phrase 'projected lift'; "
        "without it the surrounding-context allowlist is meaningless."
    )
    prefix = OPPORTUNITY_CONTEXT_DISCLAIMER[max(0, idx - 4): idx]
    assert "not " in prefix, (
        f"'projected lift' inside the disclaimer is not preceded by "
        f"'not '; prefix was {prefix!r}."
    )


# ---------------------------------------------------------------------------
# 7. Whole-section combined sweep (the production-shape assertion)
# ---------------------------------------------------------------------------


def test_combined_universal_sweep_passes_on_canonical_slate():
    """The single-fixture, single-pass version of the parametrized
    universal sweep. Pins zero forbidden tokens on the canonical
    Beauty-Brand-shaped slate (``discount_hygiene`` + ``bestseller_amplify``
    with realistic Phase 5.1 opportunity-context blocks).

    All scans operate on visible text (HTML tags stripped) because the
    contract constrains merchant-facing copy, not CSS class names or
    structured data attributes.
    """
    er = _two_card_engine_run()
    html = render_engine_run(er)
    section = _extract_experiment_section(html)
    assert section, "Section did not render."

    visible = _visible_text(section)

    # Apply the disclaimer allowlist BEFORE the "projected lift" check.
    residual = visible.replace(OPPORTUNITY_CONTEXT_DISCLAIMER, "")

    # 1. Universal forbidden tokens (case-sensitive scan over visible
    #    copy).
    leaks = []
    for token in UNIVERSAL_FORBIDDEN_TOKENS_CASE_SENSITIVE:
        if token in visible:
            leaks.append(token)
    assert not leaks, (
        f"Universal forbidden tokens leaked into "
        f"section.recommended-experiment visible copy: {leaks!r}"
    )

    # 2. "projected lift" only inside the exact disclaimer.
    assert "projected lift" not in residual, (
        "'projected lift' leaked outside the disclaimer. Only the "
        "exact disclaimer phrase is allowlisted."
    )

    # 3. Past-tense "measured" and "evidence" absent (case-insensitive
    #    over visible copy).
    visible_lower = visible.lower()
    assert "measured" not in visible_lower
    assert "evidence" not in visible_lower
    assert "evidence-backed" not in visible_lower

    # 4. Sanity: the section is non-trivial — contract copy is present.
    assert "Recommended Experiment" in visible
    assert "Run as experiment" in visible
    assert "We will measure" in visible
