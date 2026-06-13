"""V2 Play Thesis renderer (Milestone 8).

This module is the merchant-facing V2 renderer that consumes the typed
:class:`src.engine_run.EngineRun` produced by the M1-M7 V2 pipeline and emits
HTML.

Layout (per ``agent_outputs/implementation-manager-overhaul-plan-final.md``
Milestone 8):

1. **State-of-store paragraph** — assembled from typed ``Observation`` records.
2. **Recommended** — 0-3 PlayCards, class-aware visual treatment.
3. **Considered, not recommended** — up to 6 RejectedPlay cards with reason
   text, evidence snapshot, and would_fire_if text.
4. **Watching** — up to 4 deterministic WatchedSignal entries.
5. **Data-quality footer** — anomaly flags, window metadata, anchor quality.

Two abstain modes are rendered distinctly:

- ``ABSTAIN_HARD`` -> a "Data quality memo" with no plays.
- ``ABSTAIN_SOFT`` -> the standard layout with an explicit "no measured
  opportunities cleared" callout. Recommended renders zero cards
  (Synthetic Blocker Fix 3, PM-resolved contract). Held targeting
  cards from ``decide()`` are re-routed into Considered with the
  typed ``TARGETING_HELD_UNDER_ABSTAIN`` reason. Watching / Considered
  render where available so the page still feels useful, not like an
  error page.

Hard contract (DS Architect QA Change 4 + PM contract):

- The rendered HTML MUST NOT contain ``p =``, ``q =``, ``CI``,
  ``confidence_score``, ``final_score``, or any numeric confidence
  percentage.
- Targeting cards MUST NOT display a standalone ``$X,XXX`` p50 dollar
  headline. A range chip may appear ONLY if
  ``revenue_range.suppressed=False``. The ``tests/test_targeting_no_dollar_headline.py``
  test mechanically enforces this.
- Targeting cards include a fixed disclaimer: "This is a who-to-send-to
  recommendation, not a measured-lift forecast."
- ``revenue_range.suppressed=True`` MUST hide all dollar values; render the
  audience size + AOV + context instead.
- Cold-start suppressed dollar projections remain hidden.

This is the smallest safe implementation of the M8 contract. The legacy
:mod:`src.storytelling` renderer remains the default; the router in
:mod:`src.briefing` chooses V2 only when ``ENGINE_V2_OUTPUT=true``.

The renderer is a pure function: input EngineRun -> HTML string. No I/O.
The caller (``briefing.render_briefing``) writes the file.
"""

from __future__ import annotations

import html
from typing import Any, Dict, Iterable, List, Optional

from .engine_run import (
    Abstain,
    DataQualityFlag,
    DataWindow,
    DecisionState,
    EngineRun,
    EvidenceClass,
    MechanismIntent,
    Observation,
    ObservationClassification,
    OpportunityContext,
    PlayCard,
    ReasonCode,
    RejectedPlay,
    RevenueRange,
    Scale,
    WatchedSignal,
    WouldBeMeasuredBy,
)


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Maximum targeting cards rendered under ABSTAIN_SOFT.
#:
#: Synthetic Blocker Fix 3 (PM-resolved): tightened from 2 to 0. The
#: PM contract is now: ABSTAIN_SOFT means zero Recommended cards. Any
#: held targeting cards that ``decide()`` would have ranked into the
#: head are re-routed into ``considered`` with
#: :class:`ReasonCode.TARGETING_HELD_UNDER_ABSTAIN` so the merchant
#: sees them in the Considered section. This removes the contradiction
#: between the "No primary play this month" callout and a non-empty
#: Recommended section.
MAX_ABSTAIN_SOFT_TARGETING_CARDS: int = 0

#: Fixed disclaimer for every targeting card. Stable text; the
#: ``tests/test_targeting_no_dollar_headline.py`` invariant relies on
#: this card-class wrapper to reliably scope dollar-headline checks.
TARGETING_CARD_DISCLAIMER: str = (
    "This is a who-to-send-to recommendation, not a measured-lift forecast."
)

#: Wrapper class used on every targeting card. Tests grep for this class
#: to scope their dollar-headline assertion.
TARGETING_CARD_CLASS: str = "play-card play-card--targeting"

#: Wrapper class used on every recommended (non-targeting) card.
MEASURED_CARD_CLASS: str = "play-card play-card--measured"
DIRECTIONAL_CARD_CLASS: str = "play-card play-card--directional"

#: Maximum number of ``li.watching-row`` rows the renderer emits in the
#: Watching section. Single source of truth for the renderer-side cap.
#:
#: Phase 6A Ticket A1: lowered from 7 (Phase 5.3 builder cap) to 4. The
#: builder-side cap (:data:`src.decide.MAX_WATCHING_SIGNALS`) was already
#: 4 since M7; this constant pins the renderer-side cap so a future
#: change in either place is caught mechanically.
MAX_WATCHING_RENDERED: int = 4

#: Wrapper class used on every rejected/considered card.
REJECTED_CARD_CLASS: str = "play-card play-card--rejected"

#: Wrapper class used on the optional revenue-range chip. Tests use this
#: class to distinguish "range chip" dollar mentions from "headline" dollar
#: mentions when scanning targeting cards.
RANGE_CHIP_CLASS: str = "play-card-range-chip"

#: Wrapper class used on the optional Phase 5.1 opportunity-context block.
#: This block is BODY COPY only. It is rendered only when
#: ``revenue_range.suppressed=True`` AND ``PlayCard.opportunity_context`` is
#: set. It carries audience-size x recent-AOV addressable order value with
#: an explicit "not projected lift" disclaimer. It is NOT a hero/headline.
OPPORTUNITY_CONTEXT_CLASS: str = "play-card-opportunity"

#: Verbatim merchant-facing disclaimer for the opportunity-context block.
#: Tests do a loose substring check on "not projected lift" to keep
#: brittleness low while pinning the load-bearing meaning.
OPPORTUNITY_CONTEXT_DISCLAIMER: str = (
    "This is not projected lift; it shows the size of the audience if "
    "the play converts."
)


# ---------------------------------------------------------------------------
# Phase 6A Ticket B1 — Recommended Experiment section constants
# ---------------------------------------------------------------------------

#: Section CSS class used by the Recommended Experiment renderer. DOM-only
#: tests target this literal class name; do NOT rename without updating the
#: B1 contract test (``tests/test_render_recommended_experiment.py``).
RECOMMENDED_EXPERIMENT_SECTION_CLASS: str = "recommended-experiment"

#: Verbatim merchant-facing lede framing for the Recommended Experiment
#: section. Phrased as send-and-measure, NEVER as proven lift. The word
#: "experiment" deliberately frames each card as a hypothesis to test, not
#: as a forecasted outcome.
RECOMMENDED_EXPERIMENT_LEDE: str = (
    "Plays we'd run as experiments. We will measure the result and learn "
    "whether they work for your store."
)

#: Approved merchant-readable mapping for ``WouldBeMeasuredBy`` enum values.
#: The renderer MUST use these literal strings; free-text rendering of the
#: enum is forbidden by the campaign-slate contract. Three strings only.
#: Built lazily inside the helper to avoid an import-time enum dependency
#: at module import (the enum is imported at module top, but the dict is
#: populated lazily so a future refactor can split modules safely).
_WOULD_BE_MEASURED_BY_DISPLAY_COPY: Dict[str, str] = {
    "INCREMENTAL_ORDERS_IN_14D": "We will measure incremental orders in 14 days.",
    "EMAIL_ATTRIBUTED_REVENUE_IN_7D": "We will measure email-attributed revenue in 7 days.",
    "REPEAT_PURCHASE_IN_30D": "We will measure repeat purchase in 30 days.",
}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _esc(value: Optional[Any]) -> str:
    """HTML-escape a value, returning an empty string for None."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _fmt_money(value: Optional[float]) -> str:
    if value is None:
        return ""
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return ""


def _fmt_int(value: Optional[float]) -> str:
    if value is None:
        return ""
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return ""


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value) * 100:+.1f}%"
    except (TypeError, ValueError):
        return ""


def _humanize_play_id(play_id: str) -> str:
    """Turn ``bestseller_amplify`` into ``Bestseller Amplify``."""
    if not play_id:
        return "Untitled play"
    return play_id.replace("_", " ").title()


# Sprint 13.6 Ticket T1b: ``Observation.text`` was stripped from the
# contract surface per Pivot 2. The state-of-store paragraph is now
# synthesized at render time from typed numerics + classification +
# anomaly flags. The synthesis is deliberately terse (one short clause
# per observation) — downstream narration owns the rich merchant copy.
_METRIC_LABEL_OVERRIDES = {
    "aov": "AOV",
    "repeat_rate_within_window": "Repeat rate",
    "returning_customer_share": "Returning-customer share",
    "net_sales": "Net sales",
    "orders": "Orders",
    "ctr": "CTR",
}


def _metric_label(supporting_metric: Optional[str]) -> str:
    if not supporting_metric:
        return "State"
    return _METRIC_LABEL_OVERRIDES.get(
        supporting_metric, supporting_metric.replace("_", " ").capitalize()
    )


def _synthesize_observation_sentence(ob: "Observation") -> str:
    """Compose a short sentence about an Observation from typed fields.

    Replaces the stripped ``Observation.text`` field. Grammar:

    - ANOMALOUS  -> ``"Data quality flag: {flag}"`` (uses
      ``anomaly_flags[0]`` if present, else ``supporting_metric``).
    - MOVED      -> ``"{Metric label} moved {fmt_pct(delta_pct)}"``
      (omits the delta clause when not present).
    - HELD       -> ``"{Metric label} held"``.

    The renderer caller HTML-escapes the result; this function returns
    a plain string with no markup.
    """
    cls = ob.classification
    metric_label = _metric_label(ob.supporting_metric)
    if cls == ObservationClassification.ANOMALOUS:
        flag = None
        if ob.anomaly_flags:
            flag = ob.anomaly_flags[0]
        elif ob.supporting_metric:
            flag = ob.supporting_metric
        if flag:
            return f"Data quality flag: {flag}"
        return "Data quality flag noted"
    if cls == ObservationClassification.MOVED:
        delta_str = _fmt_pct(ob.delta_pct) if ob.delta_pct is not None else ""
        if delta_str:
            return f"{metric_label} moved {delta_str}"
        return f"{metric_label} moved"
    # HELD (default).
    return f"{metric_label} held"


def _card_title_for(play_id: Optional[str]) -> str:
    """Return the merchant-facing card title for ``play_id``.

    Phase 6B Ticket C3: prefers
    :data:`src.play_registry.PLAYS[play_id].display_name` when the
    play_id is registered AND its ``display_name`` is a non-empty
    string; otherwise falls back to :func:`_humanize_play_id` (the
    existing snake_case-derived title-case behavior). The fallback
    keeps unknown / future play_ids from crashing the renderer and
    pins the minimum quality bar at "title-cased label".

    The play_registry import is lazy (mirrors the lazy
    :func:`_mechanism_for_play` priors-loader pattern from C1) so
    M0 / legacy code paths where ``ENGINE_V2_OUTPUT=false`` and the
    V2 renderer is never invoked do not import-couple the registry.

    Render-only helper. Internal logic, ``data-play-id`` HTML
    attributes, and ``recommended_history.json`` keys all continue
    to read the original snake_case ``play_id`` as the stable
    identifier.
    """
    if not play_id:
        return _humanize_play_id(play_id or "")
    try:
        from .play_registry import PLAYS as _PLAYS
    except Exception:
        return _humanize_play_id(play_id)
    try:
        play_def = _PLAYS.get(str(play_id))
    except Exception:
        return _humanize_play_id(play_id)
    if play_def is None:
        return _humanize_play_id(play_id)
    name = getattr(play_def, "display_name", None)
    if not isinstance(name, str) or not name.strip():
        return _humanize_play_id(play_id)
    return name


def _round_addressable_value(value: float) -> str:
    """Phase 5.1 follow-up: round addressable order value sensibly.

    Uses "about" framing so the merchant does not read it as a precise
    dollar projection. Rounds to:

    - nearest $100 below $10k (e.g. ``about $4,200``)
    - one decimal of $1k between $10k and $1M (e.g. ``about $19.7k``)
    - one decimal of $1M at $1M+ (e.g. ``about $1.2M``)

    Returns ``""`` for non-positive or non-numeric input.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    if v <= 0 or v != v:  # non-positive or NaN
        return ""
    if v < 10_000:
        rounded = int(round(v / 100.0) * 100)
        return f"about ${rounded:,}"
    if v < 1_000_000:
        return f"about ${v / 1000.0:.1f}k"
    return f"about ${v / 1_000_000.0:.1f}M"


def _render_opportunity_context_block(
    opp: Optional[OpportunityContext],
    *,
    revenue_range: Optional[RevenueRange],
) -> str:
    """Phase 5.1 follow-up: render the addressable opportunity context.

    The block is BODY COPY only. It renders ONLY when:

    - ``opp`` is non-None AND
    - ``revenue_range`` is suppressed (or absent). When the engine has a
      calibrated range it should surface that instead, not this block.

    Hard rules:

    - Never headline / hero / per-card dollar headline.
    - Always include the "not projected lift" disclaimer.
    - Use rounded "about $X" framing, never a precise dollar number.
    """
    if opp is None:
        return ""
    # Only render alongside a suppressed (or absent) revenue range. If the
    # engine sized this play, surface that instead.
    if revenue_range is not None and not revenue_range.suppressed:
        return ""

    audience_str = _fmt_int(opp.audience_size)
    # S13.6-T3 (DS R1, 2026-05-30): the four monetary numerics live in the
    # ``NonLiftAtom`` wrapper. ``aov_used`` replaces the stripped ``aov``
    # duplicate; ``value`` replaces the stripped ``addressable_value``
    # duplicate. NO fallbacks — strict cutover, fail loudly if upstream
    # ever omits the wrapper.
    aov_str = _fmt_money(opp.non_lift.aov_used)
    addressable_str = _round_addressable_value(opp.non_lift.value)
    if not (audience_str and aov_str and addressable_str):
        return ""

    sentence = (
        f"Opportunity context: <strong>{_esc(audience_str)}</strong> "
        f"eligible customers &times; <strong>{_esc(aov_str)}</strong> "
        f"recent AOV ({_esc(opp.aov_window or 'L28')}) = "
        f"<strong>{_esc(addressable_str)}</strong> addressable order value."
    )
    return (
        f'<div class="{OPPORTUNITY_CONTEXT_CLASS}" '
        f'data-aov-source="{_esc(opp.aov_source)}" '
        f'data-aov-window="{_esc(opp.aov_window)}">'
        f'<p class="{OPPORTUNITY_CONTEXT_CLASS}__line">{sentence}</p>'
        f'<p class="{OPPORTUNITY_CONTEXT_CLASS}__disclaimer">'
        f'{_esc(OPPORTUNITY_CONTEXT_DISCLAIMER)}'
        '</p>'
        '</div>'
    )


def _humanize_metric(metric: Optional[str]) -> str:
    if not metric:
        return ""
    return metric.replace("_", " ").lower()


# ---------------------------------------------------------------------------
# Phase 6B Ticket C1 — "What we'd send:" mechanism line
# ---------------------------------------------------------------------------


#: CSS class for the "What we'd send:" line. Tests pin this literal class;
#: do NOT rename without updating ``tests/test_what_we_send_render.py``.
WHAT_WE_SEND_CLASS: str = "play-card__what-we-send"

#: Verbatim merchant-facing label. Strong-tagged.
WHAT_WE_SEND_LABEL: str = "What we'd send:"


def _render_what_we_send(mechanism: Optional[str]) -> str:
    """Render the optional "What we'd send:" line for a Recommended card.

    S13.6-T8: callers pass ``mechanism_intent.type.value`` (the
    :class:`~src.engine_run.MechanismType` enum string) when
    ``PlayCard.mechanism_intent`` is populated, or ``None`` when absent.
    The YAML-lookup fallback (``_mechanism_for_play``) has been retired;
    the renderer reads the typed contract atom directly.

    Render conditions:

    - Returns the empty string when ``mechanism`` is ``None``, not a
      string, or empty / whitespace-only. Silence is preferable to
      hallucination — we never emit an empty box or placeholder copy
      for a play that has no mechanism on the contract surface.
    - Otherwise returns a single ``<p>`` with the
      :data:`WHAT_WE_SEND_CLASS` class, the strong-tagged
      :data:`WHAT_WE_SEND_LABEL` label, and the HTML-escaped mechanism
      string.
    """
    if mechanism is None:
        return ""
    if not isinstance(mechanism, str):
        return ""
    text = mechanism.strip()
    if not text:
        return ""
    return (
        f'<p class="{WHAT_WE_SEND_CLASS}">'
        f"<strong>{_esc(WHAT_WE_SEND_LABEL)}</strong> {_esc(text)}"
        "</p>"
    )



def _humanize_reason_code(code: Optional[ReasonCode]) -> str:
    """Plain-English summary of a reason code (no jargon)."""
    if code is None:
        return "Held back."
    mapping = {
        ReasonCode.AUDIENCE_TOO_SMALL: "Audience is too small to send.",
        ReasonCode.AUDIENCE_OVERLAP_WITH_HIGHER_PRIORITY: (
            "Audience overlaps too much with a higher-priority play."
        ),
        ReasonCode.INVENTORY_BLOCKED: "Inventory is too low to push demand.",
        ReasonCode.NO_MEASURED_SIGNAL: (
            "No measured signal cleared the threshold yet."
        ),
        ReasonCode.SIGNAL_INCONSISTENT_ACROSS_WINDOWS: (
            "Signal direction disagrees across data windows."
        ),
        ReasonCode.ANOMALOUS_WINDOW: (
            "The analysis window is anomalous; results not trustworthy."
        ),
        ReasonCode.COLD_START_INSUFFICIENT_DATA: (
            "Not enough clean order history to recommend confidently."
        ),
        ReasonCode.CANNIBALIZATION_DEMOTED: (
            "Demoted to keep the portfolio from cannibalizing itself."
        ),
        ReasonCode.RECENTLY_RUN_FATIGUE: (
            "Recently sent to this audience; held to avoid fatigue."
        ),
        ReasonCode.MATERIALITY_BELOW_FLOOR: (
            "Expected impact is below the materiality floor for this store."
        ),
        ReasonCode.DATA_QUALITY_FLAG: (
            "Held due to a data-quality flag on the analysis window."
        ),
        ReasonCode.CAP_EXCEEDED: (
            "Outside the top three this month; deferred."
        ),
        # Sprint 5 Ticket S5-T2 (resolves KI-20): supplements
        # first-to-second purchase honest abstain. Merchant-facing
        # phrasing avoids jargon ("L28", "p-value", "cadence") while
        # preserving the structural reason.
        ReasonCode.SUPPLEMENT_CADENCE_OUTSIDE_WINDOW: (
            "Supplement reorder timing sits on the edge of our analysis "
            "window; the first-to-second purchase signal is too quiet to "
            "act on this month."
        ),
    }
    return mapping.get(code, "Held back.")


def _humanize_data_quality_flag(flag: Optional[DataQualityFlag]) -> str:
    if flag is None:
        return ""
    mapping = {
        DataQualityFlag.BFCM_OVERLAP: (
            "Window overlaps Black Friday / Cyber Monday."
        ),
        DataQualityFlag.POST_PROMO_WINDOW: (
            "Window sits in a post-promotion period; baselines are skewed."
        ),
        DataQualityFlag.REFUND_STORM: (
            "Unusual refund volume in the window."
        ),
        DataQualityFlag.TEST_ORDER_ANOMALY: (
            "Likely test orders contaminated the window."
        ),
        DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY: (
            "Not enough clean order history yet."
        ),
        # Sprint 1 Ticket B-7: vertical hard-refuse — merchant-facing copy.
        DataQualityFlag.VERTICAL_NOT_SUPPORTED: (
            "Beacon currently supports Beauty and Supplements brands. Your "
            "store profile is outside our supported scope and we won't "
            "generate recommendations rather than guess."
        ),
    }
    return mapping.get(flag, str(flag.value))


# ---------------------------------------------------------------------------
# State-of-store paragraph (T8.4)
# ---------------------------------------------------------------------------


def render_state_of_store(
    observations: Iterable[Observation], *, store_id: Optional[str] = None
) -> str:
    """Render the state-of-store lead paragraph from typed Observations.

    The paragraph is template-assembled, not LLM-generated:

    - One sentence per observation in input order, capped at 5.
    - MOVED observations come first (the "what changed").
    - HELD observations follow (the "what's stable").
    - ANOMALOUS observations are rendered last with a muted tone.
    - If the list is empty, a fallback sentence is emitted so the page is
      not empty.

    Numeric confidence percentages, p-values, q-values, CIs, and
    final_score / confidence_score are NEVER emitted. The Observation
    schema does not carry them.
    """
    obs_list = list(observations or [])
    if not obs_list:
        body = (
            "Not enough clean signal in the most recent window to summarize "
            "the state of the store this month."
        )
    else:
        moved = [o for o in obs_list if o.classification == ObservationClassification.MOVED]
        held = [o for o in obs_list if o.classification == ObservationClassification.HELD]
        anomalous = [
            o for o in obs_list if o.classification == ObservationClassification.ANOMALOUS
        ]
        ordered: List[Observation] = []
        ordered.extend(moved[:3])
        ordered.extend(held[: max(0, 5 - len(ordered))])
        ordered.extend(anomalous[: max(0, 5 - len(ordered))])

        sentences: List[str] = []
        for ob in ordered:
            text = _synthesize_observation_sentence(ob).strip()
            if not text:
                continue
            if not text.endswith((".", "!", "?")):
                text = text + "."
            sentences.append(_esc(text))
        body = " ".join(sentences) if sentences else (
            "State-of-store observations recorded; see receipts for detail."
        )

    store_label = _esc(store_id) if store_id else "This store"
    return (
        '<section class="state-of-store" aria-label="State of store">'
        f'<h2 class="state-of-store__title">State of store</h2>'
        f'<p class="state-of-store__lead"><strong>{store_label}.</strong> {body}</p>'
        "</section>"
    )


# ---------------------------------------------------------------------------
# Targeting card visual treatment (T8.5)
# ---------------------------------------------------------------------------


def _render_revenue_range_chip(rr: Optional[RevenueRange]) -> str:
    """Render the optional source-labeled range chip.

    Per the M8 contract:

    - Suppressed range -> empty string (no chip, no dollar amount).
    - Non-suppressed range with a numeric span -> a chip containing the
      ``$low - $high`` text, the source label (store-observed / vertical-
      prior / blend), and a class hook so the test invariant can scope.

    The chip never renders a single ``$XX,XXX`` p50 headline. The chip
    text is the range, not the median.
    """
    if rr is None or rr.suppressed:
        return ""
    p10, p90 = rr.p10, rr.p90
    if p10 is None and p90 is None:
        return ""
    lo = _fmt_money(p10)
    hi = _fmt_money(p90)
    if lo and hi:
        span = f"{lo} - {hi}"
    else:
        span = lo or hi or ""
    if not span:
        return ""
    src_label = ""
    if rr.source is not None:
        src_label = rr.source.value.replace("_", " ")
    return (
        f'<span class="{RANGE_CHIP_CLASS}" data-source="{_esc(src_label)}">'
        f"<span class=\"play-card-range-chip__label\">Estimated range "
        f"({_esc(src_label) or 'source: n/a'}):</span> "
        f'<span class="play-card-range-chip__value">{_esc(span)}</span>'
        "</span>"
    )


def _find_audience_floor_sensitivity_driver(
    rr: Optional[Any],
) -> Optional[Dict[str, Any]]:
    """Return the ``audience_floor_sensitivity`` driver value dict, or None.

    The driver is appended onto ``revenue_range.drivers`` by S6-T3.y on
    validated-path prior-anchored PlayCards only. T3.z is a pure reader
    — it does NOT recompute the band. When the driver is absent
    (directional / heuristic_unvalidated / flag-OFF), this returns None
    and the renderer falls through to the pre-T3.z shape — preserving
    byte-identity on the 5 pinned fixtures.
    """
    if rr is None:
        return None
    drivers = getattr(rr, "drivers", None) or []
    for d in drivers:
        if not isinstance(d, dict):
            continue
        if d.get("name") != "audience_floor_sensitivity":
            continue
        value = d.get("value")
        if isinstance(value, dict):
            return value
    return None


def _render_audience_floor_sensitivity(
    rr: Optional[Any],
) -> str:
    """Render the S6-T3.y sensitivity band on a Recommended Now card.

    Three branches (T3.z spec §2):

    - **Robust** (``p50_low == p50_high``): OMIT entirely. The collapsed
      band carries no new information; we do not surface "robust to
      +/-25%" microcopy.
    - **Floor-fragile** (``p50_low == 0.0`` with non-zero ``p50_high``):
      render the edge-warning paragraph
      :data:`FLOOR_FRAGILE_SENSITIVITY_COPY`.
    - **Typical band**: render the ``Floor sensitivity: $X-$Y`` chip
      span alongside the existing revenue range chip.

    T3.z is render-only — the driver value is the single source of
    truth. When the driver is absent (validated-path NOT taken,
    directional pathway, or flag-OFF), this returns the empty string
    and the pre-T3.z render shape is preserved.
    """
    value = _find_audience_floor_sensitivity_driver(rr)
    if value is None:
        return ""
    p50_low = value.get("p50_low")
    p50_high = value.get("p50_high")
    if p50_low is None or p50_high is None:
        return ""
    try:
        lo = float(p50_low)
        hi = float(p50_high)
    except (TypeError, ValueError):
        return ""
    # Robust collapse — omit entirely.
    if lo == hi:
        return ""
    # Floor-fragile edge case — render the edge warning, no chip.
    if lo == 0.0:
        return (
            '<p class="play-card__sensitivity-edge">'
            f"{_esc(FLOOR_FRAGILE_SENSITIVITY_COPY)}"
            "</p>"
        )
    # Typical band — chip-style render alongside existing revenue chip.
    lo_str = _fmt_money(lo) or ""
    hi_str = _fmt_money(hi) or ""
    if not lo_str or not hi_str:
        return ""
    return (
        '<span class="play-card-range-chip__sensitivity">'
        f"Floor sensitivity: {_esc(lo_str)}-{_esc(hi_str)}"
        "</span>"
    )


def _audience_summary_html(card: PlayCard) -> str:
    """Render the audience block (size + definition + overlap)."""
    aud = card.audience
    if aud is None:
        return ""
    parts: List[str] = []
    if aud.size is not None:
        parts.append(
            f'<span class="play-card-aud__size"><strong>{_fmt_int(aud.size)}</strong> people</span>'
        )
    if aud.definition:
        parts.append(
            f'<span class="play-card-aud__def">{_esc(aud.definition)}</span>'
        )
    if aud.overlap_with:
        overlap = ", ".join(_esc(x) for x in aud.overlap_with)
        parts.append(
            f'<span class="play-card-aud__overlap">Overlap: {overlap}</span>'
        )
    if not parts:
        return ""
    return '<div class="play-card-aud">' + "".join(parts) + "</div>"


def _render_targeting_card(card: PlayCard, *, scale: Optional[Scale]) -> str:
    """Render a TARGETING-class PlayCard.

    Hard rules (T8.5 / DS Architect QA Change 4):

    - No standalone $ p50 headline.
    - Optional source-labeled range chip ONLY when
      ``revenue_range.suppressed=False`` and the chip clearly labels its
      source.
    - Disclaimer sentence is fixed and always present.
    - Audience + AOV (from Scale.monthly_revenue or context) shows
      instead of a dollar projection when the range is suppressed.
    """
    title = _esc(_card_title_for(card.play_id))
    # S13.6-T1a (Option D): ``recommendation_text`` / ``why_now`` stripped
    # from PlayCard per Pivot 2. Renderer is kept runnable for dev
    # convenience (no AttributeError) but no longer surfaces engine-
    # authored prose. Downstream narration agents own the merchant copy.
    audience_html = _audience_summary_html(card)
    range_chip_html = _render_revenue_range_chip(card.revenue_range)

    # When the range is suppressed (e.g. cold-start, non-causal prior),
    # surface audience + monthly-revenue context instead of dollar values.
    suppressed_context = ""
    rr = card.revenue_range
    if (rr is None or rr.suppressed) and scale is not None and scale.monthly_revenue:
        suppressed_context = (
            '<div class="play-card-context">'
            "<span class=\"play-card-context__label\">Why no $ projection:</span> "
            "Targeting plays are sized only when the engine has a calibrated "
            "lift estimate for this store. Today the recommendation is "
            "<em>who to send to</em>, not <em>how much it will lift</em>."
            "</div>"
        )

    body_parts = [
        f'<h3 class="play-card__title">{title}</h3>',
        '<div class="play-card__class-badge play-card__class-badge--targeting">Targeting</div>',
    ]
    if audience_html:
        body_parts.append(audience_html)
    if range_chip_html:
        body_parts.append(range_chip_html)
    if suppressed_context:
        body_parts.append(suppressed_context)
    body_parts.append(
        f'<p class="play-card__disclaimer">{_esc(TARGETING_CARD_DISCLAIMER)}</p>'
    )

    return (
        f'<article class="{TARGETING_CARD_CLASS}" data-play-id="{_esc(card.play_id)}" '
        f'data-evidence-class="targeting">'
        + "".join(body_parts)
        + "</article>"
    )


def _render_measured_card(
    card: PlayCard, *, evidence_class: EvidenceClass
) -> str:
    """Render a MEASURED or DIRECTIONAL PlayCard.

    Measured/directional cards show:

    - Title + class badge.
    - Recommendation text.
    - "Why now" line.
    - Audience block.
    - Revenue range chip (allowed for measured/directional).
    - The qualitative observed metric label (e.g. "AOV moved").
      No p-value, no q-value, no CI, no confidence_score, no
      final_score, no numeric confidence percentage.
    """
    title = _esc(_card_title_for(card.play_id))
    klass = (
        MEASURED_CARD_CLASS
        if evidence_class == EvidenceClass.MEASURED
        else DIRECTIONAL_CARD_CLASS
    )
    badge_label = (
        "Strong" if evidence_class == EvidenceClass.MEASURED else "Emerging"
    )
    badge_class = (
        "play-card__class-badge play-card__class-badge--measured"
        if evidence_class == EvidenceClass.MEASURED
        else "play-card__class-badge play-card__class-badge--directional"
    )
    # S13.6-T1a (Option D): ``recommendation_text`` / ``why_now`` stripped.
    audience_html = _audience_summary_html(card)
    range_chip_html = _render_revenue_range_chip(card.revenue_range)

    metric_summary = ""
    meas = card.measurement
    if meas is not None:
        metric_label = _humanize_metric(meas.metric) or "the underlying metric"
        consistency_n = meas.consistency_across_windows
        consistency_text = ""
        if consistency_n is not None and consistency_n >= 2:
            consistency_text = (
                f" (direction agrees across {int(consistency_n)} windows)"
            )
        metric_summary = (
            '<div class="play-card-metric">'
            f"Observed: <strong>{_esc(metric_label)}</strong>{_esc(consistency_text)}."
            "</div>"
        )

    # Phase 5.1 follow-up: addressable opportunity context. Renders only
    # when the revenue range is suppressed AND the card carries a
    # populated OpportunityContext. Body copy only — never headline.
    opportunity_context_html = _render_opportunity_context_block(
        card.opportunity_context, revenue_range=card.revenue_range
    )

    # S13.6-T8: "What we'd send:" mechanism line for Recommended Now
    # (directional / measured) cards. Reads ``PlayCard.mechanism_intent``
    # typed atom directly — no YAML-lookup fallback (Pivot 2 ratification).
    # When ``mechanism_intent`` is None, renders nothing for this slot.
    _mi = card.mechanism_intent
    what_we_send_html = _render_what_we_send(
        _mi.type.value if isinstance(_mi, MechanismIntent) else None
    )

    body_parts = [
        f'<h3 class="play-card__title">{title}</h3>',
        f'<div class="{badge_class}">{badge_label}</div>',
    ]
    # S13.6-T1a: ``recommendation_text`` / ``why_now`` rendering removed.
    if audience_html:
        body_parts.append(audience_html)
    if what_we_send_html:
        body_parts.append(what_we_send_html)
    if metric_summary:
        body_parts.append(metric_summary)
    if opportunity_context_html:
        body_parts.append(opportunity_context_html)
    if range_chip_html:
        body_parts.append(range_chip_html)
    # S6-T3.z: surface T3.y's ``audience_floor_sensitivity`` driver as a
    # merchant-readable band. Render-only — the driver value is the
    # single source of truth (no math in the renderer). Returns "" when
    # the driver is absent (validated-path NOT taken, directional
    # pathway, heuristic_unvalidated, or flag-OFF), preserving
    # byte-identity on the pinned fixtures.
    sensitivity_html = _render_audience_floor_sensitivity(card.revenue_range)
    if sensitivity_html:
        body_parts.append(sensitivity_html)

    return (
        f'<article class="{klass}" data-play-id="{_esc(card.play_id)}" '
        f'data-evidence-class="{_esc(evidence_class.value)}">'
        + "".join(body_parts)
        + "</article>"
    )


def _coerce_evidence_class(value) -> EvidenceClass:
    if isinstance(value, EvidenceClass):
        return value
    if value is None:
        return EvidenceClass.TARGETING
    try:
        return EvidenceClass(str(value).strip().lower())
    except ValueError:
        return EvidenceClass.TARGETING


def render_play_card(card: PlayCard, *, scale: Optional[Scale]) -> str:
    """Dispatch to the targeting / measured / directional renderer."""
    ec = _coerce_evidence_class(card.evidence_class)
    if ec == EvidenceClass.TARGETING or ec == EvidenceClass.WEAK:
        return _render_targeting_card(card, scale=scale)
    return _render_measured_card(card, evidence_class=ec)


# ---------------------------------------------------------------------------
# Recommended section (T8.1)
# ---------------------------------------------------------------------------


def render_recommended_section(
    cards: Iterable[PlayCard],
    *,
    scale: Optional[Scale],
    abstain: Optional[Abstain] = None,
) -> str:
    cards = list(cards or [])
    state = abstain.state if abstain is not None else DecisionState.PUBLISH

    if state == DecisionState.ABSTAIN_HARD:
        # ABSTAIN_HARD owns its own renderer; nothing to do here.
        return ""

    callout_html = ""
    if state == DecisionState.ABSTAIN_SOFT:
        # PM contract: 0-2 targeting cards under ABSTAIN_SOFT.
        cards = cards[:MAX_ABSTAIN_SOFT_TARGETING_CARDS]
        # S13.6-T1a (Option D): ``Abstain.reason`` stripped per Pivot 2.
        # Renderer falls back to the static merchant-readable copy when
        # rendering an abstain-soft state for dev convenience. Local
        # variable is named ``soft_callout_copy`` (not ``reason_text``)
        # to keep the renderer non-consumption grep pin honest.
        soft_callout_copy = (
            "Your store is healthy this month. We did not find a play "
            "with strong enough evidence to recommend as a primary "
            "action. Here is what we evaluated and what we are watching."
        )
        callout_html = (
            '<div class="abstain-callout abstain-callout--soft" role="note">'
            '<strong class="abstain-callout__label">No primary play this month.</strong> '
            f'<span class="abstain-callout__reason">{_esc(soft_callout_copy)}</span>'
            "</div>"
        )

    if not cards:
        empty_msg = (
            "No recommendations to publish this run."
            if state != DecisionState.ABSTAIN_SOFT
            else "No targeting plays met audience-floor and overlap rules this run."
        )
        return (
            '<section class="recommended" aria-label="Recommended">'
            '<h2 class="section__title">Recommended</h2>'
            + callout_html
            + f'<p class="section__empty">{_esc(empty_msg)}</p>'
            "</section>"
        )

    cards_html = "".join(render_play_card(c, scale=scale) for c in cards)
    return (
        '<section class="recommended" aria-label="Recommended">'
        '<h2 class="section__title">Recommended</h2>'
        + callout_html
        + '<div class="play-card-grid">'
        + cards_html
        + "</div>"
        "</section>"
    )


# ---------------------------------------------------------------------------
# Recommended Experiment section (Phase 6A Ticket B1)
# ---------------------------------------------------------------------------


def _would_be_measured_by_display(
    value: Optional[WouldBeMeasuredBy],
) -> str:
    """Map a ``WouldBeMeasuredBy`` enum to merchant-readable display copy.

    Phase 6A Ticket B1 contract: free-text rendering of the enum is
    forbidden. The renderer must use one of three approved literal
    strings or omit the line entirely. Returns ``""`` when ``value`` is
    ``None`` or not a recognized enum member.
    """
    if value is None:
        return ""
    # Accept either the enum or its value string. The selector stamps the
    # enum directly; defensive coercion guards against future producers
    # that might pass the raw string.
    key = (
        value.value
        if isinstance(value, WouldBeMeasuredBy)
        else str(value).strip()
    )
    return _WOULD_BE_MEASURED_BY_DISPLAY_COPY.get(key, "")


def _render_recommended_experiment_card(card: PlayCard) -> str:
    """Render a single Recommended Experiment PlayCard.

    Rules (per ``agent_outputs/campaign-slate-contract-final.md``):

    - Title (humanized play_id).
    - "Run as experiment" framing badge.
    - Recommendation text (existing field).
    - Audience block reused verbatim (``N people`` framing).
    - Phase 5.1 opportunity-context block reused verbatim via
      :func:`_render_opportunity_context_block`. Hides itself when the
      card has no populated ``opportunity_context``.
    - ``would_be_measured_by`` displayed as one of three approved strings.
    - ``revenue_range.suppressed=True`` is a structural invariant
      enforced by Ticket A4; the renderer never emits a $ headline here.
    - The "This is not projected lift" disclaimer is carried inside the
      opportunity-context block.
    """
    title = _esc(_card_title_for(card.play_id))
    # S13.6-T1a (Option D): ``recommendation_text`` stripped per Pivot 2.
    audience_html = _audience_summary_html(card)

    # Phase 5.1 opportunity-context block. Reused verbatim. The block
    # auto-hides when the card has no populated ``opportunity_context``
    # OR when the revenue range is unsuppressed (invariant: experiment
    # cards always have ``revenue_range.suppressed=True``, so the second
    # branch never fires here).
    opportunity_context_html = _render_opportunity_context_block(
        card.opportunity_context, revenue_range=card.revenue_range
    )

    measured_by_text = _would_be_measured_by_display(card.would_be_measured_by)
    measured_by_html = ""
    if measured_by_text:
        measured_by_html = (
            '<p class="play-card__measured-by">'
            f'{_esc(measured_by_text)}'
            "</p>"
        )

    # S13.6-T8: "What we'd send:" mechanism line for Recommended
    # Experiment cards. Reads ``PlayCard.mechanism_intent`` typed atom
    # directly — no YAML-lookup fallback (Pivot 2 ratification).
    # When ``mechanism_intent`` is None, renders nothing for this slot.
    _mi_exp = card.mechanism_intent
    what_we_send_html = _render_what_we_send(
        _mi_exp.type.value if isinstance(_mi_exp, MechanismIntent) else None
    )

    body_parts = [
        f'<h3 class="play-card__title">{title}</h3>',
        '<div class="play-card__class-badge play-card__class-badge--experiment">'
        "Run as experiment"
        "</div>",
    ]
    # S13.6-T1a: ``recommendation_text`` rendering removed.
    if audience_html:
        body_parts.append(audience_html)
    if what_we_send_html:
        body_parts.append(what_we_send_html)
    if measured_by_html:
        body_parts.append(measured_by_html)
    if opportunity_context_html:
        body_parts.append(opportunity_context_html)

    return (
        '<article class="play-card play-card--experiment" '
        f'data-play-id="{_esc(card.play_id)}" '
        'data-evidence-class="targeting">'
        + "".join(body_parts)
        + "</article>"
    )


def render_recommended_experiment_section(
    cards: Iterable[PlayCard],
) -> str:
    """Render the Recommended Experiment section (Phase 6A Ticket B1).

    Returns an empty string when ``cards`` is empty so the caller can
    safely concatenate the result. The DOM contract is "no section node
    when the list is empty"; the upstream Ticket A4 contract guarantees
    the list is empty when ``ENGINE_V2_SLATE`` is off and under both
    abstain branches, so the section is implicitly gated by data.

    Args:
        cards: the ``engine_run.recommended_experiments`` list.

    Returns:
        A complete ``<section>...</section>`` HTML string when the list
        is non-empty; the empty string otherwise.
    """
    items = list(cards or [])
    if not items:
        return ""

    cards_html = "".join(_render_recommended_experiment_card(c) for c in items)
    return (
        f'<section class="{RECOMMENDED_EXPERIMENT_SECTION_CLASS}" '
        'aria-label="Recommended Experiment">'
        '<h2 class="section__title">Recommended Experiment</h2>'
        f'<p class="section__lede">{_esc(RECOMMENDED_EXPERIMENT_LEDE)}</p>'
        '<div class="play-card-grid">'
        + cards_html
        + "</div>"
        "</section>"
    )


# ---------------------------------------------------------------------------
# Considered section (T8.2)
# ---------------------------------------------------------------------------


#: S6-T3.z lede copy. The legacy lede is preserved when no Considered card
#: carries any of the new T3.z merchant-facing fields (``audience_size``,
#: ``audience_definition``, ``mechanism``). Producers wired by T3.5 populate
#: these fields and trip the new lede; today's pinned fixtures do not, so
#: byte-identity holds under flag OFF.
CONSIDERED_LEDE_LEGACY: str = (
    "These plays were evaluated and held back for the reasons below."
)
CONSIDERED_LEDE_T3Z: str = (
    "These plays have a real cohort on your store but aren't ready to "
    "recommend yet. Each card shows what we'd activate once measurement "
    "is in place."
)

#: S6-T3.z PRIOR_UNVALIDATED honest-dollar microcopy. Verbatim merchant copy.
PRIOR_UNVALIDATED_NO_PROJECTION_COPY: str = (
    "We're not projecting dollars on this play until we measure outcomes "
    "from a campaign on your store."
)

#: S6-T3.z floor-fragile edge-warning microcopy.
FLOOR_FRAGILE_SENSITIVITY_COPY: str = (
    "Today's dollar estimate sits at a heuristic edge — under a "
    "25%-higher audience floor, this cohort would not have surfaced."
)


def _rej_has_t3z_fields(rej: RejectedPlay) -> bool:
    """Return True iff ``rej`` carries any S6-T3.z merchant-surface field.

    Used by :func:`render_considered_section` to decide between the legacy
    lede and the T3.z lede. Today's producers populate none of these
    fields, so the legacy lede holds under flag OFF and the pinned
    fixtures stay byte-identical.
    """
    if getattr(rej, "audience_size", None) is not None:
        return True
    if (getattr(rej, "audience_definition", None) or "").strip():
        return True
    # S13.6-T8: ``rej.mechanism`` is ``Optional[MechanismIntent]`` (typed
    # atom, per T6 contract). Section-scope rule preserved: when the
    # producer leaves ``mechanism is None``, the T3.z lede does NOT
    # activate. Only the producer's typed atom triggers the lede.
    # YAML-lookup fallback retired at T8.
    mech = getattr(rej, "mechanism", None)
    if mech is not None:
        return True
    return False


def _render_considered_cohort_row(rej: RejectedPlay) -> str:
    """Render the S6-T3.z cohort row on a Considered card.

    Renders only when ``rej.audience_size`` is a positive int. When the
    field is None or 0 the function returns the empty string (graceful
    fallback to the pre-T3.z card shape — byte-identity preserved on
    today's pinned fixtures).

    Uses the ``play-card-aud play-card-aud--considered`` class pair so
    the considered-cohort row visually reads as "this cohort exists but
    we're not acting on it" rather than "this cohort is being
    recommended against" (the existing ``play-card-aud`` styling is
    tuned for Recommended Now cards).
    """
    size = getattr(rej, "audience_size", None)
    if size is None:
        return ""
    try:
        size_int = int(size)
    except (TypeError, ValueError):
        return ""
    if size_int <= 0:
        return ""
    definition = (getattr(rej, "audience_definition", None) or "").strip()
    parts: List[str] = [
        f'<span class="play-card-aud__size"><strong>{_fmt_int(size_int)}</strong> people</span>'
    ]
    if definition:
        parts.append(
            f'<span class="play-card-aud__def">{_esc(definition)}</span>'
        )
    return (
        '<div class="play-card-aud play-card-aud--considered">'
        + "".join(parts)
        + "</div>"
    )


def _render_considered_no_projection(rej: RejectedPlay) -> str:
    """Render the PRIOR_UNVALIDATED honest-dollar microcopy line.

    Renders only when ``rej.reason_code == ReasonCode.PRIOR_UNVALIDATED``.
    On any other reason code the function returns the empty string —
    we don't broadcast the no-projection disclaimer on holds that are
    about audience-floor / data-quality / window-disagreement etc.
    """
    code = getattr(rej, "reason_code", None)
    code_value = code.value if hasattr(code, "value") else code
    if code_value != ReasonCode.PRIOR_UNVALIDATED.value:
        return ""
    return (
        '<p class="play-card__no-projection">'
        f"{_esc(PRIOR_UNVALIDATED_NO_PROJECTION_COPY)}"
        "</p>"
    )


def render_rejected_card(rej: RejectedPlay) -> str:
    """Render a single considered-but-rejected play card.

    S13.6-T8 + S6-T3.z merchant-facing render pass:

    - Title (humanized play_id).
    - One-line plain-English reason text from ``reason_code``.
    - **S6-T3.z** cohort row when ``audience_size`` is a positive int.
    - **S6-T3.z** "What we'd send:" mechanism line when
      ``mechanism`` is a typed :class:`~src.engine_run.MechanismIntent`
      atom (``mechanism.type.value`` surfaced). When ``mechanism``
      is ``None``, the line is omitted. YAML-lookup fallback retired
      at T8 (Pivot 2 ratification).
    - **S6-T3.z** "We're not projecting dollars" honest-dollar line
      ONLY when ``reason_code == PRIOR_UNVALIDATED``.
    - Visual treatment muted vs Recommended (CSS class hook).

    The S6-T3.z branches are render-conditional on the
    :class:`RejectedPlay` fields being populated. Payloads with
    ``mechanism=None`` fall through to the legacy render shape (no
    mechanism line).
    """
    title = _esc(_card_title_for(rej.play_id))
    # S13.6-T1a (Option D): ``RejectedPlay.reason_text`` /
    # ``evidence_snapshot`` / ``would_fire_if`` stripped per Pivot 2.
    # Renderer surfaces only the humanized ``reason_code`` summary;
    # downstream narration owns the detail + snapshot + would-fire-if
    # prose composition.
    reason_summary = _humanize_reason_code(rej.reason_code)

    cohort_html = _render_considered_cohort_row(rej)
    # S13.6-T8: ``rej.mechanism`` is ``Optional[MechanismIntent]`` (typed
    # atom). The YAML-lookup fallback path is retired here (Pivot 2
    # ratification). Section-scope rule preserved: when the producer
    # leaves ``mechanism is None``, the "What we'd send" line does NOT
    # render. When the producer populated a typed ``MechanismIntent``,
    # surface ``type.value`` (the enum string). No YAML lookup; no
    # engine-authored prose.
    mechanism_raw = getattr(rej, "mechanism", None)
    if isinstance(mechanism_raw, MechanismIntent):
        mechanism: Optional[str] = mechanism_raw.type.value
    else:
        # None or any legacy str shape (post-T6 strict deserialization
        # means str should not appear, but treat as no-op).
        mechanism = None
    what_we_send_html = _render_what_we_send(mechanism)
    no_projection_html = _render_considered_no_projection(rej)

    parts: List[str] = [
        f'<h3 class="play-card__title">{title}</h3>',
        f'<p class="play-card__reason"><strong>Why held:</strong> {_esc(reason_summary)}</p>',
    ]
    if cohort_html:
        parts.append(cohort_html)
    if what_we_send_html:
        parts.append(what_we_send_html)
    if no_projection_html:
        parts.append(no_projection_html)
    code_attr = (
        rej.reason_code.value
        if rej.reason_code is not None and hasattr(rej.reason_code, "value")
        else ""
    )
    return (
        f'<article class="{REJECTED_CARD_CLASS}" data-play-id="{_esc(rej.play_id)}" '
        f'data-reason-code="{_esc(code_attr)}">'
        + "".join(parts)
        + "</article>"
    )


def render_considered_section(rejected: Iterable[RejectedPlay]) -> str:
    items = list(rejected or [])
    if not items:
        return (
            '<section class="considered" aria-label="Considered, not recommended">'
            '<h2 class="section__title">Considered, not recommended</h2>'
            '<p class="section__empty">No plays were considered and held this run.</p>'
            "</section>"
        )
    rendered_items = items[:6]
    cards_html = "".join(render_rejected_card(r) for r in rendered_items)
    # S6-T3.z: flip to the new lede only when at least one Considered card
    # carries a T3.z merchant-surface field (cohort row, mechanism, or
    # audience definition). Today's producers populate none of these, so
    # the legacy lede holds and the pinned fixtures stay byte-identical
    # under flag OFF. T3.5 owns the atomic re-pin at activation.
    if any(_rej_has_t3z_fields(r) for r in rendered_items):
        lede = CONSIDERED_LEDE_T3Z
    else:
        lede = CONSIDERED_LEDE_LEGACY
    return (
        '<section class="considered" aria-label="Considered, not recommended">'
        '<h2 class="section__title">Considered, not recommended</h2>'
        f'<p class="section__lede">{_esc(lede)}</p>'
        '<div class="play-card-grid play-card-grid--muted">'
        + cards_html
        + "</div>"
        "</section>"
    )


# ---------------------------------------------------------------------------
# Watching section (T8.1)
# ---------------------------------------------------------------------------

#: Copy used in the never-empty fallback row for mature stores.
_WATCHING_FALLBACK_TEXT: str = (
    "Trend signals are firming up; we'll surface specific watch items here"
    " as your run-over-run history accumulates."
)


def _has_directional_observation(engine_run: "EngineRun") -> bool:
    """Return True if at least one state_of_store Observation has a non-zero
    directional delta (change_magnitude is non-None and != 0).

    Private helper — do not export.  Used only by the C4 fallback gate.
    """
    for obs in (engine_run.state_of_store or []):
        if obs.change_magnitude is not None and obs.change_magnitude != 0:
            return True
    return False


def render_watching_section(signals: Iterable[WatchedSignal]) -> str:
    items = list(signals or [])
    if not items:
        return (
            '<section class="watching" aria-label="Watching">'
            '<h2 class="section__title">Watching</h2>'
            '<p class="section__empty">No deterministic signals to watch this run.</p>'
            "</section>"
        )

    rows: List[str] = []
    for sig in items[:MAX_WATCHING_RENDERED]:
        metric = _esc(_humanize_metric(sig.metric) or "metric")
        trend = sig.trend or ""
        arrow = "&uarr;" if trend == "up" else "&darr;" if trend == "down" else "&rarr;"
        threshold = _esc(sig.threshold_to_act or "")
        threshold_html = (
            f'<span class="watching-row__threshold">Threshold to act: {threshold}</span>'
            if threshold
            else ""
        )
        rows.append(
            f'<li class="watching-row" data-metric="{_esc(sig.metric)}">'
            f'<span class="watching-row__metric"><strong>{metric}</strong></span>'
            f'<span class="watching-row__trend" data-trend="{_esc(trend)}">{arrow} {_esc(trend)}</span>'
            f"{threshold_html}"
            "</li>"
        )

    return (
        '<section class="watching" aria-label="Watching">'
        '<h2 class="section__title">Watching</h2>'
        '<p class="section__lede">Trending signals not yet ready to recommend.</p>'
        '<ul class="watching-list">'
        + "".join(rows)
        + "</ul>"
        "</section>"
    )


def _render_watching_section_for_run(engine_run: "EngineRun") -> str:
    """Phase 6B Ticket C4: watching section renderer with never-empty fallback.

    Delegates to ``render_watching_section`` when signals are present.

    When ``engine_run.watching`` is empty, checks three conditions before
    emitting a fallback row:
    1. ``decision_state`` is PUBLISH or ABSTAIN_SOFT.
    2. The store is NOT cold-start AND has no INSUFFICIENT_CLEAN_HISTORY flag
       (proxy for >=180 days of clean history on the EngineRun schema, which
       carries no numeric history-days field).
    3. At least one state_of_store Observation has a non-zero directional delta.

    Cold-start stores, ABSTAIN_HARD, and stores with INSUFFICIENT_CLEAN_HISTORY
    receive the existing ``<p class="section__empty">`` text unchanged.

    Private — do not export.  Called only from ``render_engine_run``.
    """
    # If watching has rows, delegate to the standard renderer.
    if engine_run.watching:
        return render_watching_section(engine_run.watching)

    # Determine decision_state (mirrors the pattern used in render_engine_run).
    abstain = engine_run.abstain
    state = abstain.state if abstain is not None else DecisionState.PUBLISH

    # Condition 1: only PUBLISH or ABSTAIN_SOFT qualify for the fallback.
    fallback_eligible_state = state in (DecisionState.PUBLISH, DecisionState.ABSTAIN_SOFT)

    # Condition 2: not cold-start, no INSUFFICIENT_CLEAN_HISTORY quality flag.
    sufficient_history = (
        not engine_run.cold_start
        and DataQualityFlag.INSUFFICIENT_CLEAN_HISTORY not in engine_run.data_quality_flags
    )

    # Condition 3: at least one directional Observation.
    has_directional = _has_directional_observation(engine_run)

    if fallback_eligible_state and sufficient_history and has_directional:
        fallback_row = (
            f'<li class="watching-row watching-row--fallback">'
            f"{_esc(_WATCHING_FALLBACK_TEXT)}"
            f"</li>"
        )
        return (
            '<section class="watching" aria-label="Watching">'
            '<h2 class="section__title">Watching</h2>'
            '<p class="section__lede">Trending signals not yet ready to recommend.</p>'
            '<ul class="watching-list">'
            + fallback_row
            + "</ul>"
            "</section>"
        )

    # Default: render the existing empty-section copy (cold-start, ABSTAIN_HARD,
    # insufficient history).
    return render_watching_section([])


# ---------------------------------------------------------------------------
# Data-quality footer (T8.1)
# ---------------------------------------------------------------------------


def render_data_quality_footer(
    flags: Iterable[DataQualityFlag],
    *,
    data_window: Optional[DataWindow],
    scale: Optional[Scale],
) -> str:
    flag_items: List[str] = []
    for flag in flags or []:
        text = _humanize_data_quality_flag(flag)
        if not text:
            continue
        flag_items.append(
            f'<li class="dq-footer__flag" data-flag="{_esc(flag.value)}">{_esc(text)}</li>'
        )

    window_bits: List[str] = []
    if data_window is not None:
        if data_window.primary_window:
            window_bits.append(f"Primary window: {_esc(data_window.primary_window)}")
        if data_window.available_windows:
            window_bits.append(
                "Available windows: "
                + _esc(", ".join(data_window.available_windows))
            )
        if data_window.anchor_quality:
            window_bits.append(f"Anchor quality: {_esc(data_window.anchor_quality)}")

    scale_bits: List[str] = []
    if scale is not None:
        if scale.monthly_revenue is not None:
            scale_bits.append(
                f"Monthly revenue est.: {_esc(_fmt_money(scale.monthly_revenue))}"
            )
        if scale.materiality_floor is not None:
            # Phase 5.4: replace the engineering jargon "Materiality floor:
            # $10,000" with a merchant-readable explanation. The exact
            # numeric floor is preserved verbatim in receipts/debug.html
            # for internal review.
            floor_money = _esc(_fmt_money(scale.materiality_floor))
            scale_bits.append(
                "We only recommend primary plays that could realistically "
                f"add at least {floor_money} this month for a store your "
                "size."
            )

    flags_html = (
        f'<ul class="dq-footer__flags">{"".join(flag_items)}</ul>'
        if flag_items
        else '<p class="dq-footer__no-flags">No data-quality flags on this run.</p>'
    )
    window_html = (
        '<ul class="dq-footer__window">'
        + "".join(f"<li>{w}</li>" for w in window_bits)
        + "</ul>"
        if window_bits
        else ""
    )
    scale_html = (
        '<ul class="dq-footer__scale">'
        + "".join(f"<li>{s}</li>" for s in scale_bits)
        + "</ul>"
        if scale_bits
        else ""
    )

    return (
        '<footer class="dq-footer" aria-label="Data quality">'
        '<h2 class="dq-footer__title">Data quality</h2>'
        + flags_html
        + window_html
        + scale_html
        + "</footer>"
    )


# ---------------------------------------------------------------------------
# Abstain renderers (T8.3)
# ---------------------------------------------------------------------------


def render_abstain_hard_memo(engine_run: EngineRun) -> str:
    """Render the Data Quality Memo for ABSTAIN_HARD.

    PM contract: ABSTAIN_HARD shows no plays. The page is a focused
    memo explaining the data-quality issue and what the merchant should
    check.
    """
    flags_html = "".join(
        f'<li class="abstain-hard__flag" data-flag="{_esc(f.value)}">'
        f"{_esc(_humanize_data_quality_flag(f))}"
        "</li>"
        for f in engine_run.data_quality_flags or []
    )
    if not flags_html:
        flags_html = (
            '<li class="abstain-hard__flag">'
            "Decision engine paused; see receipts for the underlying flag."
            "</li>"
        )

    # S13.6-T1a (Option D): ``Abstain.reason`` stripped per Pivot 2.
    # Renderer falls back to the static abstain-hard copy.
    reason = (
        "The engine cannot recommend reliably on this analysis window. "
        "No plays are published this run."
    )

    state_of_store_html = render_state_of_store(
        engine_run.state_of_store, store_id=engine_run.store_id
    )
    dq_footer_html = render_data_quality_footer(
        engine_run.data_quality_flags,
        data_window=engine_run.data_window,
        scale=engine_run.scale,
    )

    return (
        '<main class="briefing-v2 briefing-v2--abstain-hard">'
        '<header class="briefing-v2__header">'
        f'<h1 class="briefing-v2__title">Data quality memo</h1>'
        '<p class="briefing-v2__subtitle">'
        "The decision engine paused for this run."
        "</p>"
        "</header>"
        + state_of_store_html
        + '<section class="abstain-hard" aria-label="Data quality memo">'
        '<h2 class="section__title">Why no plays this run</h2>'
        f'<p class="abstain-hard__reason">{_esc(reason)}</p>'
        '<ul class="abstain-hard__flags">'
        + flags_html
        + "</ul>"
        '<p class="abstain-hard__guidance">'
        "What to check before re-running: confirm the analysis window is not "
        "contaminated by promotions, refunds, or test orders, and that the "
        "store has at least 90 days of clean order history."
        "</p>"
        "</section>"
        + dq_footer_html
        + "</main>"
    )


# ---------------------------------------------------------------------------
# Top-level renderer (T8.1 / T8.6)
# ---------------------------------------------------------------------------


def render_engine_run(engine_run: EngineRun) -> str:
    """Render an EngineRun to a complete HTML document string.

    Args:
        engine_run: a fully-populated EngineRun (typically the output of
            ``decide()``).

    Returns:
        A complete HTML string. The caller is responsible for writing
        the file. No I/O is performed here.
    """
    if engine_run is None:
        engine_run = EngineRun()

    abstain = engine_run.abstain
    state = abstain.state if abstain is not None else DecisionState.PUBLISH

    # S6-T3.z: conditionally append the T3.z CSS rules only when the
    # EngineRun being rendered actually uses a T3.z surface. Keeps the
    # legacy CSS block byte-identical when no T3.z fields are populated
    # (pre-activation / flag OFF).
    css = _BRIEFING_CSS
    if _engine_run_has_t3z_surfaces(engine_run):
        css = css + _BRIEFING_CSS_T3Z

    head = (
        "<!DOCTYPE html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        f"<title>BeaconAI briefing - {_esc(engine_run.store_id or 'store')}</title>"
        "<style>"
        + css
        + "</style>"
        "</head>"
        "<body>"
    )
    tail = "</body></html>"

    if state == DecisionState.ABSTAIN_HARD:
        body = render_abstain_hard_memo(engine_run)
        return head + body + tail

    state_of_store_html = render_state_of_store(
        engine_run.state_of_store, store_id=engine_run.store_id
    )
    recommended_html = render_recommended_section(
        engine_run.recommendations,
        scale=engine_run.scale,
        abstain=abstain,
    )
    # Phase 6A Ticket B1: Recommended Experiment renders BETWEEN
    # Recommended Now and Watching. The section is implicitly gated by
    # data: ``recommended_experiments`` is only populated when
    # ``ENGINE_V2_SLATE=true`` (per Ticket A4), and is forced to ``[]``
    # under both ABSTAIN_SOFT and ABSTAIN_HARD. ABSTAIN_HARD never
    # reaches this branch because the memo path returns earlier.
    recommended_experiment_html = render_recommended_experiment_section(
        engine_run.recommended_experiments,
    )
    considered_html = render_considered_section(engine_run.considered)
    watching_html = _render_watching_section_for_run(engine_run)
    dq_footer_html = render_data_quality_footer(
        engine_run.data_quality_flags,
        data_window=engine_run.data_window,
        scale=engine_run.scale,
    )

    header_subtitle = (
        "What we evaluated this month and what we are watching."
        if state == DecisionState.ABSTAIN_SOFT
        else "Recommended plays for the upcoming month."
    )

    # Phase 6B Ticket C2: Watching renders BEFORE Considered. The merchant
    # reads "what to do now -> what to test -> what to monitor -> what we
    # held" so the held-back / muted section sits last before the data-
    # quality footer. Order: Recommended -> Recommended Experiment ->
    # Watching -> Considered -> DQ footer.
    body = (
        '<main class="briefing-v2">'
        '<header class="briefing-v2__header">'
        f'<h1 class="briefing-v2__title">BeaconAI Action Brief</h1>'
        f'<p class="briefing-v2__subtitle">{_esc(header_subtitle)}</p>'
        "</header>"
        + state_of_store_html
        + recommended_html
        + recommended_experiment_html
        + watching_html
        + considered_html
        + dq_footer_html
        + "</main>"
    )

    return head + body + tail


# ---------------------------------------------------------------------------
# CSS (kept inline so the renderer is self-contained; M10 may extract)
# ---------------------------------------------------------------------------


_BRIEFING_CSS: str = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; color: #1a1a1a; background: #fafafa; margin: 0; padding: 0; }
.briefing-v2 { max-width: 960px; margin: 0 auto; padding: 32px 24px 64px; }
.briefing-v2__header { margin-bottom: 24px; }
.briefing-v2__title { font-size: 28px; margin: 0 0 8px; }
.briefing-v2__subtitle { color: #555; margin: 0; }
.section__title { font-size: 20px; margin: 32px 0 12px; }
.section__lede { color: #555; margin: 0 0 12px; }
.section__empty { color: #888; font-style: italic; }
.state-of-store__lead { background: #fff; border-left: 4px solid #2c5282; padding: 12px 16px; }
.play-card-grid { display: grid; grid-template-columns: 1fr; gap: 16px; }
.play-card { background: #fff; border: 1px solid #d8d8d8; border-radius: 8px; padding: 16px 20px; }
.play-card--measured { border-left: 6px solid #2f855a; }
.play-card--directional { border-left: 6px solid #b7791f; }
.play-card--targeting { border-left: 6px solid #4a5568; border-style: dashed; }
.play-card--rejected { background: #f4f4f4; border-left: 6px solid #a0aec0; opacity: 0.92; }
.play-card__title { margin: 0 0 4px; font-size: 18px; }
.play-card__class-badge { display: inline-block; font-size: 12px; padding: 2px 8px; border-radius: 999px; margin-bottom: 8px; font-weight: 600; }
.play-card__class-badge--measured { background: #c6f6d5; color: #22543d; }
.play-card__class-badge--directional { background: #faf089; color: #744210; }
.play-card__class-badge--targeting { background: #e2e8f0; color: #2d3748; }
.play-card__recommendation { margin: 8px 0; }
.play-card__why-now { margin: 4px 0; color: #444; }
.play-card__what-we-send { margin: 8px 0 8px 4px; font-size: 14px; color: #2d3748; line-height: 1.4; }
.play-card-aud { margin: 8px 0; font-size: 14px; color: #2d3748; }
.play-card-aud > span { display: inline-block; margin-right: 12px; }
.play-card-range-chip { display: inline-block; background: #ebf4ff; color: #2c5282; padding: 4px 10px; border-radius: 6px; font-size: 13px; margin-top: 8px; }
.play-card-range-chip__label { font-weight: 600; margin-right: 4px; }
.play-card-context { margin-top: 8px; font-size: 13px; color: #555; }
.play-card-context__label { font-weight: 600; }
.play-card-metric { margin-top: 8px; font-size: 14px; color: #2f855a; }
.play-card-opportunity { margin-top: 10px; padding: 8px 10px; background: #f0f4f8; border-left: 3px solid #4a5568; border-radius: 4px; }
.play-card-opportunity__line { margin: 0 0 4px; font-size: 13px; color: #2d3748; }
.play-card-opportunity__disclaimer { margin: 0; font-size: 12px; color: #718096; font-style: italic; }
.play-card__disclaimer { margin: 10px 0 0; font-size: 12px; color: #555; font-style: italic; border-top: 1px dashed #cbd5e0; padding-top: 8px; }
.play-card__reason { margin: 6px 0; }
.play-card__reason-detail { margin: 4px 0; color: #444; font-size: 14px; }
.play-card__evidence-snapshot { margin: 4px 0; color: #4a5568; font-size: 13px; }
.play-card__would-fire-if { margin: 6px 0; font-size: 13px; color: #2c5282; }
.abstain-callout { padding: 12px 16px; border-radius: 6px; margin: 0 0 12px; }
.abstain-callout--soft { background: #fffaf0; border-left: 4px solid #b7791f; color: #744210; }
.abstain-callout__label { display: block; margin-bottom: 4px; }
.abstain-hard__reason { background: #fff; padding: 12px 16px; border-left: 4px solid #c53030; }
.abstain-hard__flags { margin: 12px 0 0; padding-left: 20px; }
.abstain-hard__flag { margin: 4px 0; }
.abstain-hard__guidance { margin-top: 12px; color: #4a5568; }
.watching-list { list-style: none; padding: 0; margin: 0; }
.watching-row { background: #fff; border: 1px solid #e2e8f0; padding: 10px 14px; border-radius: 6px; margin-bottom: 8px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.watching-row__metric { flex: 0 0 auto; }
.watching-row__trend { flex: 0 0 auto; color: #4a5568; }
.watching-row__threshold { flex: 1 1 auto; color: #4a5568; font-size: 13px; }
.dq-footer { margin-top: 32px; background: #f7fafc; border: 1px solid #e2e8f0; padding: 16px; border-radius: 6px; }
.dq-footer__title { font-size: 16px; margin: 0 0 8px; }
.dq-footer__flags, .dq-footer__window, .dq-footer__scale { padding-left: 20px; margin: 4px 0; }
"""


# S6-T3.z merchant-facing CSS additions. Localized so the M0 / Beauty /
# supplements pinned fixtures stay byte-identical: this block is
# appended to ``_BRIEFING_CSS`` ONLY when the EngineRun being rendered
# contains at least one T3.z surface (a Considered card with new
# merchant fields, or a Recommended Now card with the
# ``audience_floor_sensitivity`` driver attached). Today's pinned
# fixtures carry neither, so the extra CSS is suppressed and bytes
# match. T3.5 owns activation.
_BRIEFING_CSS_T3Z: str = (
    ".play-card-aud--considered { color: #4a5568; font-size: 13px; }\n"
    ".play-card-aud--considered > span { color: #4a5568; }\n"
    ".play-card__no-projection { margin: 6px 0; font-size: 13px; color: #4a5568; font-style: italic; }\n"
    ".play-card__sensitivity-edge { margin: 6px 0; font-size: 13px; color: #744210; font-style: italic; }\n"
    ".play-card-range-chip__sensitivity { display: inline-block; background: #fef5e7; color: #744210; padding: 3px 8px; border-radius: 6px; font-size: 12px; margin-left: 8px; margin-top: 8px; }\n"
)


def _engine_run_has_t3z_surfaces(engine_run: Optional[EngineRun]) -> bool:
    """Return True iff ``engine_run`` will actually render any T3.z DOM.

    Used by :func:`render_engine_run` to decide whether to append the
    T3.z-specific CSS rules. The check is RENDER-aware: it returns True
    only when at least one of the new render branches will produce
    visible HTML (cohort row, mechanism, no-projection, or a non-empty
    audience_floor_sensitivity render). The mere presence of the
    ``audience_floor_sensitivity`` driver is NOT enough — the robust
    branch (p50_low == p50_high) renders nothing and must not trip
    the CSS. This keeps the 5 pinned fixtures byte-identical under
    flag OFF where the driver is present but collapses to robust.
    """
    if engine_run is None:
        return False
    for rej in engine_run.considered or []:
        if _rej_has_t3z_fields(rej):
            return True
    for card in engine_run.recommendations or []:
        rr = getattr(card, "revenue_range", None)
        if _render_audience_floor_sensitivity(rr):
            return True
    return False
