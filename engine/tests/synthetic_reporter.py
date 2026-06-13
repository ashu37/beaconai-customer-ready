"""
tests/synthetic_reporter.py

Synthetic-matrix reporter for the BeaconAI Action Engine.

Purpose
-------
A small, isolated test utility that summarises what each synthetic scenario
*actually shows the merchant* by parsing the rendered ``briefing.html`` DOM.

Why this module exists
----------------------
The synthetic Phase 5 e2e review found that the prior matrix reporter was
inferring "pilot" / "PRIMARY" / "actions" status by reading internal artifacts
(``candidate_debug.json::pilot_actions``, ``engine_run.json::recommendations[]``)
even when ``briefing.html`` -- the only thing the merchant can see -- showed
zero Recommended cards. That misrepresented results and undermined trust in
the harness.

Synthetic blocker Fix 7 makes ``briefing.html`` the *single source of truth*
for merchant-visible state on each scenario. The reporter:

* Parses the rendered briefing DOM via BeautifulSoup.
* Counts visible Recommended / Considered / Watching cards/rows.
* Detects the ABSTAIN_SOFT callout, the ABSTAIN_HARD memo, and the
  Phase 5.4 materiality footer line as rendered.
* Does NOT consult any internal artifact for merchant-visible state.

Internal artifacts NOT read for state inference
----------------------------------------------
* ``receipts/candidate_debug.json``
* ``engine_run.recommendations[]``
* ``engine_run.considered[]``
* ``engine_run.watching[]``
* ``v2_sizing_shadow.json``
* ``receipts/debug.html``
* ``actions_log.json``

The reporter MAY read ``receipts/engine_run.json::briefing_meta`` for context
fields only (declared vertical, scenario id) and MAY read
``engine_run.decision_state`` strictly as a sanity-check counterpoint to
DOM-derived state. It MUST NOT use any of those JSON fields to set the
merchant-visible counts/flags.

Selectors
---------
The selectors below were verified against the renderer
(``src/storytelling_v2.py``) and the pinned Phase 5 sample
(``agent_outputs/phase5_samples/beauty_brand_v2_briefing.html``):

* Recommended cards: ``section.recommended article.play-card`` excluding any
  with class ``play-card--rejected``.
* Considered cards: ``section.considered article.play-card.play-card--rejected``.
* Watching rows: ``section.watching ul.watching-list li.watching-row``.
* ABSTAIN_SOFT callout: ``div.abstain-callout.abstain-callout--soft`` (also
  matches ``div.abstain-callout--soft`` to be lenient).
* ABSTAIN_HARD memo: ``main.briefing-v2--abstain-hard`` exists OR any
  ``p.abstain-hard__reason`` / ``li.abstain-hard__flag`` is present.
* Materiality footer: substring ``"We only recommend primary plays that
  could realistically add at least"`` within ``footer.dq-footer``
  (or anywhere if the footer is missing -- still a valid presence signal).

Scope (Fix 7 only)
------------------
* Pure harness/reporter code. No engine source files modified.
* No engine decision logic, renderer behavior, or V2 product contract change.
* No re-baselining of goldens.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Constants -- selector & substring contracts
# ---------------------------------------------------------------------------

#: Substring used to detect the Phase 5.4 merchant-facing materiality footer.
#: This is the load-bearing copy that tells the merchant *why* the page is
#: honest about not having a recommendation.
MATERIALITY_FOOTER_SUBSTRING: str = (
    "We only recommend primary plays that could realistically add at least"
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioReport:
    """Per-scenario reporter row.

    Every merchant-visible field is DOM-derived. ``declared_vertical`` and
    ``decision_state_internal`` are read from ``engine_run.json`` for context
    only (sanity-check / labelling) and are explicitly NOT used to drive any
    of the visible counts / flags.
    """

    # Identity
    scenario_name: str
    briefing_html_path: str

    # Context (engine_run.json) -- NEVER used to infer merchant-visible state
    declared_vertical: Optional[str]
    rendered_vertical: Optional[str]
    decision_state_internal: Optional[str]

    # DOM-derived merchant-visible state -- ONLY from briefing.html
    visible_recommended_count: int
    visible_considered_count: int
    visible_watching_count: int
    abstain_soft_callout_present: bool
    abstain_hard_memo_present: bool
    materiality_footer_present: bool

    # Optional product contract pass/fail (only if encoded in briefing_meta).
    # None means "not encoded; reporter does not have a verdict".
    product_contract_pass: Optional[bool] = None

    # Free-form notes (deviations, missing files, etc.).
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "briefing_html_path": self.briefing_html_path,
            "declared_vertical": self.declared_vertical,
            "rendered_vertical": self.rendered_vertical,
            "decision_state_internal": self.decision_state_internal,
            "visible_recommended_count": self.visible_recommended_count,
            "visible_considered_count": self.visible_considered_count,
            "visible_watching_count": self.visible_watching_count,
            "abstain_soft_callout_present": self.abstain_soft_callout_present,
            "abstain_hard_memo_present": self.abstain_hard_memo_present,
            "materiality_footer_present": self.materiality_footer_present,
            "product_contract_pass": self.product_contract_pass,
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# DOM parsing helpers (PRIMARY: briefing.html only)
# ---------------------------------------------------------------------------


def _parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def count_recommended_cards(soup: BeautifulSoup) -> int:
    """Count visible Recommended cards.

    Recommended cards are ``article.play-card`` directly inside
    ``section.recommended``, excluding any rejected card (those live in
    Considered, not Recommended -- but be defensive in case future
    renderers nest them).
    """
    section = soup.select_one("section.recommended")
    if section is None:
        return 0
    cards = section.select("article.play-card")
    visible = [c for c in cards if "play-card--rejected" not in (c.get("class") or [])]
    return len(visible)


def count_considered_cards(soup: BeautifulSoup) -> int:
    """Count visible Considered cards.

    Considered cards are ``article.play-card.play-card--rejected`` inside
    ``section.considered``.
    """
    section = soup.select_one("section.considered")
    if section is None:
        return 0
    cards = section.select("article.play-card.play-card--rejected")
    return len(cards)


def count_watching_rows(soup: BeautifulSoup) -> int:
    """Count visible Watching rows.

    Watching rows are ``li.watching-row`` inside
    ``section.watching ul.watching-list``. The renderer uses ``ul.watching-list``;
    fall back to any ``li.watching-row`` inside ``section.watching`` if the
    list class drifts in a future revision.
    """
    section = soup.select_one("section.watching")
    if section is None:
        return 0
    rows = section.select("ul.watching-list li.watching-row")
    if not rows:
        rows = section.select("li.watching-row")
    return len(rows)


def detect_abstain_soft_callout(soup: BeautifulSoup) -> bool:
    """Return True iff a soft abstain callout is rendered."""
    el = soup.select_one("div.abstain-callout.abstain-callout--soft")
    if el is not None:
        return True
    # Lenient fallback in case the renderer drops one of the wrapper classes.
    el = soup.select_one(".abstain-callout--soft")
    return el is not None


def detect_abstain_hard_memo(soup: BeautifulSoup) -> bool:
    """Return True iff the ABSTAIN_HARD data-quality memo is rendered."""
    # Primary marker: top-level ``main.briefing-v2--abstain-hard`` wrapper
    # emitted by ``render_abstain_hard_memo`` in src/storytelling_v2.py.
    el = soup.select_one("main.briefing-v2--abstain-hard")
    if el is not None:
        return True
    # Secondary markers used by the same renderer.
    if soup.select_one("p.abstain-hard__reason") is not None:
        return True
    if soup.select_one("li.abstain-hard__flag") is not None:
        return True
    if soup.select_one("section.abstain-hard") is not None:
        return True
    return False


def detect_materiality_footer(soup: BeautifulSoup) -> bool:
    """Return True iff the Phase 5.4 materiality footer line is rendered.

    Looks for the exact load-bearing substring inside ``footer.dq-footer``.
    Falls back to the entire document text if the footer is absent so a
    misplaced rendering is still surfaced as "present" (test of merchant
    visibility, not structural location).
    """
    footer = soup.select_one("footer.dq-footer")
    haystack = footer.get_text(" ", strip=True) if footer is not None else soup.get_text(" ", strip=True)
    return MATERIALITY_FOOTER_SUBSTRING in haystack


# ---------------------------------------------------------------------------
# Context fields (CONTEXT-ONLY: engine_run.json::briefing_meta)
# ---------------------------------------------------------------------------


def _read_engine_run_context(engine_run_json_path: Path) -> Dict[str, Any]:
    """Read CONTEXT-ONLY fields from engine_run.json.

    Returns a dict with ``rendered_vertical`` and ``decision_state_internal``
    when readable. Never reads ``recommendations[]``, ``considered[]``,
    ``watching[]``, or ``candidate_debug.json``. Failures yield ``{}`` -- the
    reporter still produces a row using DOM-only fields.
    """
    if not engine_run_json_path.exists():
        return {}
    try:
        with open(engine_run_json_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    out: Dict[str, Any] = {}
    meta = data.get("briefing_meta") or {}
    if isinstance(meta, dict):
        v = meta.get("vertical")
        if v is not None:
            out["rendered_vertical"] = str(v)

    abstain = data.get("abstain") or {}
    if isinstance(abstain, dict):
        s = abstain.get("state")
        if s is not None:
            out["decision_state_internal"] = str(s)
    return out


# ---------------------------------------------------------------------------
# Public reporter API
# ---------------------------------------------------------------------------


def report_briefing(
    *,
    scenario_name: str,
    briefing_html_path: Path,
    engine_run_json_path: Optional[Path] = None,
    declared_vertical: Optional[str] = None,
) -> ScenarioReport:
    """Build a :class:`ScenarioReport` from a rendered briefing.html.

    Parameters
    ----------
    scenario_name:
        Free-form scenario identifier (e.g. ``"healthy_beauty_240d"``).
    briefing_html_path:
        Path to the rendered ``briefing.html`` for the scenario.
    engine_run_json_path:
        Optional. When provided, the reporter reads ``briefing_meta.vertical``
        and ``abstain.state`` for CONTEXT only. Never used to infer
        merchant-visible state.
    declared_vertical:
        Optional. The scenario's YAML-declared vertical (e.g. mapped via
        :func:`tests.synthetic_harness.vertical_for_scenario`). Surfaced
        as-is on the report so callers can compare declared vs. rendered.

    Returns
    -------
    ScenarioReport
        A dataclass row whose merchant-visible fields are DOM-derived from
        ``briefing.html`` exclusively.
    """
    notes: List[str] = []

    # --- DOM parse -- merchant-visible state ------------------------------
    if not briefing_html_path.exists():
        notes.append(f"briefing.html not found at {briefing_html_path}")
        return ScenarioReport(
            scenario_name=scenario_name,
            briefing_html_path=str(briefing_html_path),
            declared_vertical=declared_vertical,
            rendered_vertical=None,
            decision_state_internal=None,
            visible_recommended_count=0,
            visible_considered_count=0,
            visible_watching_count=0,
            abstain_soft_callout_present=False,
            abstain_hard_memo_present=False,
            materiality_footer_present=False,
            product_contract_pass=None,
            notes=notes,
        )

    html = briefing_html_path.read_text(encoding="utf-8")
    soup = _parse_html(html)

    visible_recommended = count_recommended_cards(soup)
    visible_considered = count_considered_cards(soup)
    visible_watching = count_watching_rows(soup)
    soft_callout = detect_abstain_soft_callout(soup)
    hard_memo = detect_abstain_hard_memo(soup)
    materiality_footer = detect_materiality_footer(soup)

    # --- Context-only fields (engine_run.json) ----------------------------
    rendered_vertical: Optional[str] = None
    decision_state_internal: Optional[str] = None
    if engine_run_json_path is not None:
        ctx = _read_engine_run_context(engine_run_json_path)
        rendered_vertical = ctx.get("rendered_vertical")
        decision_state_internal = ctx.get("decision_state_internal")

    # --- Cross-contract sanity hints (notes only; not state-inference) ----
    if soft_callout and visible_recommended > 0:
        notes.append(
            "DOM contradiction: ABSTAIN_SOFT callout present AND "
            f"{visible_recommended} Recommended cards visible."
        )
    if hard_memo and (visible_recommended > 0 or visible_considered > 0):
        notes.append(
            "DOM contradiction: ABSTAIN_HARD memo present AND "
            f"recommended={visible_recommended} considered={visible_considered}."
        )
    if (
        declared_vertical is not None
        and rendered_vertical is not None
        and declared_vertical != rendered_vertical
    ):
        notes.append(
            f"vertical mismatch: declared={declared_vertical!r} "
            f"rendered={rendered_vertical!r}"
        )

    return ScenarioReport(
        scenario_name=scenario_name,
        briefing_html_path=str(briefing_html_path),
        declared_vertical=declared_vertical,
        rendered_vertical=rendered_vertical,
        decision_state_internal=decision_state_internal,
        visible_recommended_count=visible_recommended,
        visible_considered_count=visible_considered,
        visible_watching_count=visible_watching,
        abstain_soft_callout_present=soft_callout,
        abstain_hard_memo_present=hard_memo,
        materiality_footer_present=materiality_footer,
        product_contract_pass=None,  # not encoded in DOM/briefing_meta today
        notes=notes,
    )


def report_run_dir(
    *,
    scenario_name: str,
    out_dir: Path,
    declared_vertical: Optional[str] = None,
    brand: Optional[str] = None,
) -> ScenarioReport:
    """Convenience wrapper -- build a report from a scenario ``out_dir``.

    The synthetic harness writes briefings under
    ``<out_dir>/briefings/<brand>_briefing.html`` (see
    ``src/main.py``). When ``brand`` is None, the wrapper picks the first
    ``*_briefing.html`` it finds under the briefings dir.
    """
    briefing_dir = Path(out_dir) / "briefings"
    if brand is not None:
        briefing_html = briefing_dir / f"{brand}_briefing.html"
    else:
        candidates = sorted(briefing_dir.glob("*_briefing.html"))
        briefing_html = candidates[0] if candidates else briefing_dir / "missing.html"

    engine_run_json = Path(out_dir) / "receipts" / "engine_run.json"
    return report_briefing(
        scenario_name=scenario_name,
        briefing_html_path=briefing_html,
        engine_run_json_path=engine_run_json if engine_run_json.exists() else None,
        declared_vertical=declared_vertical,
    )


def format_report_table(rows: Sequence[ScenarioReport]) -> str:
    """Format a Sequence of reports as a plain-text table.

    Used by the harness CLI / debug section. Counts and flags come from the
    DOM-only fields; ``rendered_vertical`` and ``decision_state_internal``
    are labelled DEBUG/CONTEXT in the output to make their non-authoritative
    role explicit.
    """
    headers = [
        "scenario",
        "vert(declared)",
        "vert(rendered:DBG)",
        "rec",
        "con",
        "watch",
        "soft",
        "hard",
        "matfoot",
        "state(DBG)",
    ]
    lines: List[str] = []
    lines.append(" | ".join(headers))
    lines.append(" | ".join("-" * len(h) for h in headers))
    for r in rows:
        cells = [
            r.scenario_name,
            r.declared_vertical or "-",
            r.rendered_vertical or "-",
            str(r.visible_recommended_count),
            str(r.visible_considered_count),
            str(r.visible_watching_count),
            "Y" if r.abstain_soft_callout_present else "N",
            "Y" if r.abstain_hard_memo_present else "N",
            "Y" if r.materiality_footer_present else "N",
            r.decision_state_internal or "-",
        ]
        lines.append(" | ".join(cells))
    return "\n".join(lines)


__all__ = [
    "MATERIALITY_FOOTER_SUBSTRING",
    "ScenarioReport",
    "count_considered_cards",
    "count_recommended_cards",
    "count_watching_rows",
    "detect_abstain_hard_memo",
    "detect_abstain_soft_callout",
    "detect_materiality_footer",
    "format_report_table",
    "report_briefing",
    "report_run_dir",
]
